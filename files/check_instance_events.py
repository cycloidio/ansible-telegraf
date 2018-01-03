#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import boto3

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
        self.ec2 = boto3.client('ec2', region_name=region)

if __name__ == "__main__":

    args = init_argparse()
    log = init_logger(args.verbose)
    conn = Conn(region=args.aws_region)
    event_instances = []
    instances = conn.ec2.describe_instance_status()['InstanceStatuses']
    for instance in instances:
        useful_events = []
        for event in instance.get('Events', {}):
            # Exclude completed reboots since the events API appearently returns these even after they have been completed:
            # Example:
            #  "events_set": [
            #     {
            #         "code": "system-reboot",
            #         "description": "[Completed] Scheduled reboot",
            #         "not_before": "2015-01-05 12:00:00 UTC",
            #         "not_after": "2015-01-05 18:00:00 UTC"
            #     }
            # ]
            if event['Code'] in ['system-reboot', 'instance-reboot', 'instance-stop', 'system-maintenance'] and event['Description'] in ['[Completed]', '[Canceled]']:
                continue
            useful_events.append(event)

        if useful_events:
            instance['event_count'] = len(useful_events)
            log.debug("Events found %s" % instance)
            event_instances.append(instance)

    for instance in event_instances:
        print "aws_ec2_instance,instance_id=%(InstanceId)s events=%(event_count)s" % instance
