#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import boto3
import datetime

def init_logger(verbose=False):
    # Init logger
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

    if verbose:
        # Stream handler
        hdl = logging.StreamHandler()
        hdl.setFormatter(logging.Formatter('%(asctime)s %(levelname)s -: %(message)s'))
    else:
        hdl = logging.NullHandler()

    log.addHandler(hdl)
    return log


def init_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--aws-region",
                        help="AWS Region (defaults to eu-west-1).",
                        default="eu-west-1",
                        type=str)
    parser.add_argument("-v", "--verbose",
                        help="Provide SSL/TLS certificate expiration details even when OK",
                        action='store_true')
    return parser.parse_args()

class Conn(object):
    "wrapper of multiple boto connections"

    def __init__(self, region):
        self.rds = boto3.client('rds', region_name=region)

if __name__ == "__main__":
    now = datetime.datetime.utcnow()
    args = init_argparse()
    log = init_logger(args.verbose)
    conn = Conn(region=args.aws_region)
    event_instances = []
    instances = conn.rds.describe_db_instances()['DBInstances']
    for instance in instances:
        useful_events = []
        # Note the original check don't iterate on events. Just look the last one https://github.com/sensu-plugins/sensu-plugins-aws/blob/master/bin/check-rds-events.rb
        for event in conn.rds.describe_events(StartTime=now-datetime.timedelta(minutes=20), SourceType='db-instance', SourceIdentifier=instance['DBInstanceIdentifier'])['Events']:
            # {u'': ['backup'], u'SourceType': 'db-instance', u'SourceArn': 'arn:aws:rds:eu-west-1:661913936052:db:cycloid-concourse-database-eu-we1-prod', u'Date': datetime.datetime(2017, 12, 22, 2, 15, 34, 356000, tzinfo=tzutc()), u'Message': 'Backing up DB instance', u'SourceIdentifier': 'cycloid-concourse-database-eu-we1-prod'}
            # we will need to filter out non-disruptive/basic operation events.
            # ie. the regular backup operations

            if event['Message'] in ['Backing up DB instance', 'Finished DB Instance backup', 'Restored from snapshot', 'Replication for the Read Replica resumed']: continue
            # ie. Replication resumed
            if event['Message'] in ['Replication for the Read Replica resumed']: continue
            # you can add more filters to skip more events.

            useful_events.append(event)

        if useful_events:
            instance['event_count'] = len(useful_events)
            log.debug("Events found %s" % instance)
            event_instances.append(instance)

    for instance in event_instances:
        print "aws_rds_instance,instance_id=%(DBInstanceIdentifier)s events=%(event_count)s" % instance
