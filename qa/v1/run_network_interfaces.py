#!/usr/bin/python
import argparse
from modules.rpcsqa_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

# Save the parsed arguments
results = parser.parse_args()

# Setup the helper class ( Chef / Razor )
rpcsqa = rpcsqa_helper(results.razor_ip)

distros = ['precise', 'centos']

for distro in distros:

    # Remove broker fails for qa-%distro-pool
    print "## -- Removing Broker Fails from Razor for qa-{0}-pool -- ##".format(distro)
    rpcsqa.remove_broker_fail("qa-{0}-pool".format(distro))

    # Gather all the nodes for the os_distro
    print "## -- Gathering all available nodes for {0} -- ##".format(distro)
    all_nodes = rpcsqa.gather_all_nodes(distro)

    for node in all_nodes:
        chef_node = Node(node['name'], api=rpcsqa.chef)
        rpcsqa.set_network_interface(chef_node)
