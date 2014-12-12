# -- coding: utf-8 --
__author__ = "yelfathi"


import argparse
import os
import re
import time
from jnpr.junos import Device
from multiprocessing import Process


class LSPping(Process):

    def __init__(self, device, user, passwd, treetrace):
        self.device = device
        self.user = user
        self.passwd = passwd
        self.treetrace = treetrace
        Process.__init__(self)

    # Returns a list with next-hop and protocol-name
    def check_rtentry(self, dev, prefix):
        ''' List with 2 entries:
             prefix present or not in the routing table
             the protocol name (Local, Direct ...)
        '''
        rtentry_result = ['False', 'False']
        rtentry = dev.rpc.get_route_information(destination=prefix)
        if rtentry.xpath('//nh'):
            rtentry_result = [rtentry.xpath('//nh')[0],
                              rtentry.xpath('//protocol-name')[0].text]
        return rtentry_result

    # LSP ping to prefix, returns the nb of packets received
    def ping_ldp(self, dev, prefix, dest, count):
        ping_result = dev.rpc.request_ping_ldp_lsp(fec=prefix,
                                                   destination=dest,
                                                   count=count)
        pkts_rcved = ping_result.xpath('//lsping-packets-received')[0].\
            text.strip()
        return pkts_rcved

    # LSP traceroute to prefix, returns all the paths
    def trace_ldp(self, dev, prefix, dest, ttl, wait, retries):
        trace_result = dev.rpc.traceroute_mpls_ldp(fec=prefix,
                                                   destination=dest,
                                                   ttl=ttl,
                                                   wait=wait,
                                                   retries=retries)
        return trace_result

    def run(self):
        ''' Open the RPC connection to each device:
            - check the rt-entry and the LSP reachability
              because JUNOS RPC generates an exception for
              local or unreachable prefix
            - if OK LSP Ping to each prefix through all multipath (127.0.0.x)
              multipath retrieved from lsp_treetrace.py script
        '''

        ''' The file "lock" is used to check
            if lsp-treetrace script is running
        '''
        if not os.path.isfile('lock'):
            dev = Device(host=self.device,
                         user=self.user,
                         password=self.passwd)
            try:
                dev.open()
                dev.timeout = 300
            except Exception as err:
                print 'Cannot connect to device:', err

        with open(self.treetrace, 'r') as my_file:
            result = my_file.read().splitlines()
            for line in result:
                [hopfail, lasthop, status] = ['', '', '']
                pe = line.split(',')[0]
                dest = line.split(',')[1]
                time.sleep(0.1)  # Wait 100 ms, avoiding false negative
                if self.check_rtentry(dev, pe)[0] == 'False':
                    print 'Device {0}: no entry in routing table for prefix {1}'\
                        .format(self.device, pe)
                elif self.check_rtentry(dev, pe)[1] == 'Direct':
                    print 'Device {0}: no test for local loopback {1}'\
                        .format(self.device, pe)
                elif self.ping_ldp(dev, pe, dest, '1') != '1':
                    trace_result = self.trace_ldp(dev, pe, dest, '5', '5', '1')
                    hop_count = len(trace_result.xpath('//depth'))
                    for hop in range(hop_count):
                        ipv4_patt =\
                            re.compile('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
                        address = trace_result.xpath('//address')[hop].text
                        if re.match(ipv4_patt, address):
                            hopfail = hop
                            lasthop = re.match(ipv4_patt, address).group()
                            status = trace_result.xpath('//status')[hop].text
                if [hopfail, lasthop, status] != ['', '', '']:
                    print 'Device {0}: LSP treetrace failed for prefix {1}, destination {2}, failure at hop:{3}, address:{4}, with status:\"{5}\"'\
                        .format(self.device, pe, dest,
                                hopfail, lasthop, status)
        dev.close()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='\
                        LSP Ping')
    parser.add_argument('--devices',
                        help='loopback devices separated by '+':\
                        1.1.1.1/32+2.2.2.2/32',
                        required=True)
    parser.add_argument('--user',
                        help='username',
                        required=True)
    parser.add_argument('--passwd',
                        help='password',
                        required=True)
    parser.add_argument('--treetrace',
                        help='treetrace file w/o the extension \
                        generated by lsp-treetrace.py',
                        required=True)
    args = parser.parse_args()
    devlist = re.split('\+', args.devices)

    # For each device, a different process is executed
    jobs = []
    for i in range(len(devlist)):
        jobs.append(LSPping(devlist[i],
                            args.user,
                            args.passwd,
                            args.treetrace+'.'+devlist[i]))
    for job in jobs:
        job.start()
