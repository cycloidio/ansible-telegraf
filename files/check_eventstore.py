#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import datetime
import requests

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
    parser.add_argument("-u", "--url",
                        help="Gossip url : http://127.0.0.1:2113/gossip",
                        required=True,
                        type=str)
    parser.add_argument("-v", "--verbose",
                        help="Provide SSL/TLS certificate expiration details even when OK",
                        action='store_true')
    return parser.parse_args()


def get_gossip(url):
    try:
        r = requests.get(url)
        return r.json()
    except:
        return None


def script_error(reason="Check internal error"):
    print "eventstore,reason=%s check_error=1"  % reason
    exit(0)
    

def check_nodes_alive(gossip):
    for node in gossip['members']:
        print "eventstore,node=%s isAlive=%d" % (node['internalTcpIp'], node['isAlive'])

if __name__ == "__main__":
    now = datetime.datetime.utcnow()
    args = init_argparse()
    log = init_logger(args.verbose)

    gossip = get_gossip(args.url)
    if gossip is None:
        # Not able to get gossip
        script_error("NotAbleToDecodeGossip")

    try:
        check_nodes_alive(gossip)
    except:
        script_error("GossipJsonKeyError")

