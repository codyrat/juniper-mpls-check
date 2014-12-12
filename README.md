juniper-mpls-check
==================

LSP in-band monitoring

The goal is to detect blackhole on MPLS networks through LSP in-band monitoring (even with Layer 3 ECMP), before seamless-BFD will be available.
It uses the junos-pyez library.

- lsp_treetrace.py: for each host listed in hosts.txt, it will retrieve every LSP paths using multipath option (Layer 3 ECMP) and log it to treetrace.device_name
- lsp_ping.py: for each (host, path) listed in treetrace.device_name it will check the reachability

You can schedule the lsp_treetrace script every hour and the lsp_ping every five minutes (scalability reasons):
  - python lsp_treetrace.py --devices 'pe1+pe2+pe3' --user 'USERNAME' --passwd 'PASS' --hosts hosts.txt
  - python lsp_ping.py --devices 'pe1+pe2+pe3' --user 'USERNAME' --passwd 'PASS' --treetrace treetrace

Prerequisites:
- JUNOS PyEZ librabry: https://github.com/Juniper/py-junos-eznc
- On each devices you will need to authorize the 'ssh' and 'netconf ssh' services for the user who will run the scripts
