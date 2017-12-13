#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# In order to work correctly and not lose data, this script should be ideally
# executed every 15 minutes.
# More often = data duplication, less often = data loss

import argparse
import boto3
import datetime

def init_argparse():
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--aws-region",
                        help="AWS Region (defaults to eu-west-1).",
                        default="eu-west-1",
                        type=str)
    return parser.parse_args()

class Conn(object):

    def __init__(self, region):
        self.ses = boto3.client('ses', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)

reputation_levels = [
    {"days": 5, "period": 300},
    {"days": 15, "period": 900},
    {"days": 60, "period": 3600},
    {"days": 365, "period": 86400},
]
def get_reputation(name, level=0):
    """
    First try to get reputation data for a small period, then go for larger
    periods if there is no recent data
    """
    if level >= len(reputation_levels):
        return {
            u"Maximum": 0.0,
            u"Minimum": 0.0,
            u"Average": 0.0,
            u"Unit": "None",
            u"Timestamp": now
        }
    try:
        datapoints = conn.cloudwatch.get_metric_statistics(
            Namespace='AWS/SES',
            MetricName='Reputation.{}'.format(name),
            StartTime=now-datetime.timedelta(days=reputation_levels[level]["days"]),
            EndTime=now,
            Period=reputation_levels[level]["period"],
            Statistics=["Minimum", "Maximum", "Average"]
            )["Datapoints"]
    except:
        return get_reputation(name, level+1)
    if len(datapoints) == 0:
        return get_reputation(name, level+1)
    return datapoints[-1]
    
    
if __name__ == "__main__":
    args = init_argparse()
    conn = Conn(region=args.aws_region)
    now = datetime.datetime.utcnow()

    # Statistics
    enabled = conn.ses.get_account_sending_enabled()
    send_statistics = conn.ses.get_send_quota()
    try:
        live_statistics = sorted(conn.ses.get_send_statistics()['SendDataPoints'], key=lambda x: x[u'Timestamp'])[-1]
    except IndexError:
        live_statistics = {
            u'Complaints': 0,
            u'DeliveryAttempts': 0,
            u'Bounces': 0,
            u'Rejects': 0,
            u'Timestamp': now
        }
    if live_statistics[u'Timestamp'].replace(tzinfo=None) < now - datetime.timedelta(minutes=15):
        live_statistics = {
            u'Complaints': 0,
            u'DeliveryAttempts': 0,
            u'Bounces': 0,
            u'Rejects': 0,
            u'Timestamp': now
        }

    # Reputation dashboard
    bounce = get_reputation("BounceRate")
    complaint = get_reputation("ComplaintRate")

    print """ses enabled={enabled}
ses max_send_rate={send[MaxSendRate]}
ses,type=max quota={send[Max24HourSend]}
ses,type=sent quota={send[SentLast24Hours]}
ses,type=attempts delivery={live[DeliveryAttempts]}
ses,type=bounces delivery={live[Bounces]}
ses,type=complaints delivery={live[Complaints]}
ses,type=rejects delivery={live[Rejects]}
ses,type=bounces reputation={bounce[Average]}
ses,type=complaints reputation={complaint[Average]}""".format(
        enabled=int(enabled["Enabled"]),
        send=send_statistics,
        live=live_statistics,
        bounce=bounce,
        complaint=complaint
        )
