# -- coding: utf-8 --
__author__ = "yelfathi"


import argparse
import glob
import os
import re
from jnpr.junos import Device
from multiprocessing import Process


class LSPtreetrace(Process):

    def __init__(self, device, user, passwd, hosts):
        self.device = device
        self.user = user
        self.passwd = passwd
        self.hosts = hosts
        Process.__init__(self)

    # Returns a list with next-hop and protocol-name
    def check_rtentry(self, dev, prefix):
        rtentry_result = ['False', 'False']
        rtentry = dev.rpc.get_route_information(destination=prefix)
        if rtentry.xpath('//nh'):
            rtentry_result = [rtentry.xpath('//nh')[0],
                              rtentry.xpath('//protocol-name')[0].text]
        return rtentry_result

    # LSP ping to prefix, returns the nb of packets received
    def ping_ldp(self, dev, prefix, count):
        ping_result = dev.rpc.request_ping_ldp_lsp(fec=prefix, count=count)
        pkts_rcved = ping_result.xpath('//lsping-packets-received')[0].\
            text.strip()
        return pkts_rcved

    # LSP traceroute to prefix, returns all the paths
    def trace_ldp(self, dev, prefix, ttl, wait, retries):
        trace_result = dev.rpc.traceroute_mpls_ldp(fec=prefix,
                                                   ttl=ttl,
                                                   wait=wait,
                                                   retries=retries)
        return trace_result

    def run(self):
        ''' Open the RPC connection to each device:
            - check the rt-entry and the LSP reachability
              because JUNOS RPC generates an exception for
              local or unreachable prefix
            - if OK retrieve all the paths
        '''
        dev = Device(host=self.device,
                     user=self.user,
                     password=self.passwd)
        try:
            dev.open()
            dev.timeout = 300
        except Exception as err:
            print 'Cannot connect to device:', err

        pelist = []
        with open(self.hosts, 'r') as hosts_file:
            for line in hosts_file:
                cleanedLine = line.strip()
                if cleanedLine:
                    pelist.append(cleanedLine)

        for pe in pelist:
            if self.check_rtentry(dev, pe)[0] == 'False':
                print 'Device {0}: no entry in routing table for prefix {1}'\
                    .format(self.device, pe)
            elif self.check_rtentry(dev, pe)[1] == 'Direct':
                print 'Device {0}: no test for local loopback {1}'\
                    .format(self.device, pe)
            elif self.ping_ldp(dev, pe, '1') == '1':
                with open('treetrace.'+self.device, 'a') as treetrace_file:
                    trace_result = self.trace_ldp(dev, pe, '5', '5', '1')
                    max_path = len(trace_result.xpath('//path-index'))
                    for path in range(max_path):
                        dest = trace_result.\
                            xpath('//probe-destination')[path].text
                        treetrace_file.write(pe + "," + dest + "\n")
            else:
                print "Device {0}: LSP ping failed to PE loopback {1}"\
                    .format(self.device, pe)

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
    parser.add_argument('--hosts',
                        help='destination loopback devices to check LSP:\
                        1.1.1.1/32\
                        2.2.2.2/32',
                        required=True)
    args = parser.parse_args()
    devlist = re.split('\+', args.devices)

    ''' The file "treetrace.device" will hold the tuple of the treetrace:
        - target PE loopback
        - destination multipath (127.0.0.x)
    '''
    filelist = glob.glob("treetrace.*")
    for f in filelist:
        os.remove(f)

    ''' The file "lock" is used to check
        if script is running or not (used by lsp_ping.py)
    '''
    with open('lock', 'a+') as lock_file:
        lock_file.write('1')

    # For each device, a different process is executed
    jobs = []
    for i in range(len(devlist)):
        jobs.append(LSPtreetrace(devlist[i],
                                 args.user,
                                 args.passwd,
                                 args.hosts))
    for job in jobs:
        job.start()

    os.remove('lock')
