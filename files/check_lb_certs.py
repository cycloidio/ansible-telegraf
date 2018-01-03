#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
from os.path import join as path_join
import boto3
import OpenSSL
import datetime
from functools import wraps

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
        self.iam = boto3.client('iam', region_name=region)
        self.acm = boto3.client('acm', region_name=region)
        self.elb = boto3.client('elb', region_name=region)
        self.alb = boto3.client('elbv2', region_name=region)

def cache_result(func):
    " Used on methods to convert them to methods that replace themselves\
        with their return value once they are called. "
    cache = {}
    @wraps(func)
    def wrapper(*args, **kwargs):
        key = "%s-%s-%s" % (func.__name__, args, kwargs)
        try:
            ret = cache[key]
        except KeyError:
            ret = func(*args, **kwargs)
            cache[key] = ret
        return ret
    return wrapper


# The cache function could be replaced by @functools.lru_cache() if you are in python3
@cache_result
def iam_list_server_certificates(conn):
    "Split into func to put cache on it"
    return conn.iam.list_server_certificates()['ServerCertificateMetadataList']

@cache_result
def find_iam_cert_name(con, cert_arn):
    "Return an IAM cert name from ARN"
    for cert in iam_list_server_certificates(conn):
        #print iam_list_server_certificates.cache_info()
        if cert['Arn'] == cert_arn:
            return cert['ServerCertificateName']
    return None

@cache_result
def load_cert(conn, cert):
    """Load certificate.
    params:
        cert: could be IAM/ACM cert ARN
    """

    raw_cert = None

    if cert.startswith("arn:aws:iam:"):
        # Because BOTO don't offer a way to get the cert by ARN (only name)
        cert_id = find_iam_cert_name(conn, cert_arn=cert)
        raw_cert = conn.iam.get_server_certificate(ServerCertificateName=cert_id)['ServerCertificate']['CertificateBody']
    # In case of ACM cert
    elif cert.startswith("arn:aws:acm:"):
        raw_cert = conn.acm.get_certificate(CertificateArn=cert)['Certificate']

    if raw_cert is None:
        # Unable to load cert
        return None

    return OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, raw_cert)


if __name__ == "__main__":

    args = init_argparse()
    log = init_logger(args.verbose)
    conn = Conn(region=args.aws_region)
    now = datetime.datetime.now()
    output = []

    # ELB
    log.debug("### ELB")
    for lb in  conn.elb.describe_load_balancers()['LoadBalancerDescriptions']:
        log.debug("lb_name %s" % lb['LoadBalancerName'])

        for listener in lb['ListenerDescriptions']:
            # If https
            if listener['Listener'].get('SSLCertificateId') is None: continue

            log.debug("    cert : %s" % listener['Listener'].get('SSLCertificateId'))

            # Find cert arn
            cert = load_cert(conn, cert=listener['Listener'].get('SSLCertificateId'))

            # Get gap
            cert_nafter = datetime.datetime.strptime(cert.get_notAfter(),'%Y%m%d%H%M%SZ')
            output.append({
                'lb_name': lb['LoadBalancerName'],
                'ln_type': 'ELB',
                'cert_cn': '%s' % cert.get_subject().CN,
                'cert': listener['Listener'].get('SSLCertificateId'),
                'expire': (cert_nafter - now).days
            })


    # ALB
    log.debug("### ALB")
    for lb in  conn.alb.describe_load_balancers()['LoadBalancers']:
        log.debug("lb_name %s" % lb['DNSName'])

        for listener in conn.alb.describe_listeners(LoadBalancerArn=lb['LoadBalancerArn'])['Listeners']:
            listener_certs = listener.get('Certificates')

            if listener_certs is None: continue

            for listener_cert in listener_certs:
                log.debug("    cert : %s" % listener_cert["CertificateArn"])
                cert = load_cert(conn, cert=listener_cert["CertificateArn"])

                # Get gap
                cert_nafter = datetime.datetime.strptime(cert.get_notAfter(),'%Y%m%d%H%M%SZ')
                output.append({
                    'lb_name': lb['DNSName'],
                    'ln_type': 'ALB',
                    'cert_cn': '%s' % cert.get_subject().CN,
                    'cert': listener_cert["CertificateArn"],
                    'expire': (cert_nafter - now).days
                })

    # Output
    uniq = []
    for entry in output:
        # Filter to display only cert. Let see if we need later load balancer
        # information as labels
        if entry['cert'] in uniq: continue

        print "aws_lb_certs,cert_cn=%(cert_cn)s,cert=%(cert)s expire_days=%(expire)s" % entry
        uniq.append(entry['cert'])
