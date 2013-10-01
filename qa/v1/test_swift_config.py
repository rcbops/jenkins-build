#!/usr/bin/python
'''
# Things to do #
# 1. Verify NTP is configured correctly on all nodes #
# 2. Verify DSH is configured on all the nodes #
# 3. Verify Swift - Recon <-- need to research what this is #
# 4. Verify SNMP configured correctly #
# 5. verify syslog consolidation configured correctly #
# 6. verify dispersion reports are configured correctly #
# 7. test mail configured correctly #
'''

import argparse
from modules.rpcsqa_helper import *
from modules.chef_helper import *
from swift_helper import *

parser = argparse.ArgumentParser()

parser.add_argument('--environment', action="store", dest="environment",
                    required=True,
                    help="Operating System Distribution to build OpenStack on")

# Save the parsed arguments
results = parser.parse_args()
rpcsqa = rpcsqa_helper()
swift = swift_helper()

# Gather all the nodes for the current environment and set variables for
# their current roles
nodes = rpcsqa.cluster_nodes(results.environment)
proxy = []
storage = []

# When we build monster the swift object will keep track of the nodes it is
# given so we dont have to do this, we will just call the nodes
for node in nodes:
    if node['in_use'] is swift.roles['controller']:
        management = node
    elif node['in_use'] is swift.roles['proxy']:
        proxy.append(node)
    elif node['in_use'] is swift.roles['storage']:
        storage.append(node)
    else:
        chef = node

