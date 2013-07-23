#!/usr/bin/python
import sys
import argparse
from rpcsqa_helper import *
from chef_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False,
                    default="autotest",
                    help="Name for the Open Stack chef environment")

parser.add_argument('--branch', action="store", dest="branch", required=False,
                    default="grizzly",
                    help="The OpenStack Distribution (i.e. folsom, grizzly")

parser.add_argument('--repo_tag', action="store", dest="repo_tag",
                    required=False, default=None,
                    help="The tag for the version of cookbooks (i.e. 4.0.0")

parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False, default="glance-cf",
                    help="Feature_set for the Open Stack chef environment")

parser.add_argument('--cluster_size', action="store", dest="cluster_size",
                    required=False, default=4,
                    help="Size of the Open Stack cluster.")

parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='precise',
                    help="Operating System Distribution to build OpenStack on")

parser.add_argument('--action', action="store", dest="action",
                    required=False, default="build",
                    help="Action to do for Open Stack (build/destroy/add)")

parser.add_argument('--remote_chef', action="store_true", dest="remote_chef",
                    required=False, default=False,
                    help="Build a new chef server for this deploy")

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

# Save the parsed arguments
results = parser.parse_args()

# Setup the helper class ( Chef / Razor )
rpcsqa = rpcsqa_helper(results.razor_ip)

# Have to add check for empty string due to Jenkins parameters
if results.repo_tag is not None:
    if results.repo_tag == "None":
        results.repo_tag = None

# Remove broker fails for qa-%os_distro-pool
rpcsqa.remove_broker_fail("qa-%s-pool" % results.os_distro)

# Prepare environment
env = rpcsqa.prepare_environment(results.name,
                                 results.os_distro,
                                 results.feature_set,
                                 results.branch)

# Gather all the nodes for the os_distro
all_nodes = rpcsqa.gather_all_nodes(results.os_distro)

# If we are testing swift, we need 1 controller, 1 proxy and 3 swift nodes
if cluster_size < 5:
    print "Swift Selected, setting cluster size to 5 (minimum)"
    cluster_size = 5

# Set the cluster size
cluster_size = int(results.cluster_size)

# Assign nodes to names
chef_server = openstack_list[0]
keystone_server = openstack_list[1]
swift_proxy = openstack_list[2]
swift_nodes = openstack_list[3:]

# print all servers info
print "***********************************************************"
print "Chef Server: {0}".format(rpcsqa.print_server_info(chef_server))
print "Keystone Server {0}".format(rpcsqa.print_server_info(keystone_server))
print "Swift Proxy {0}".format(rpcsqa.print_server_info(swift_proxy))
print [rpcsqa.print_server_info(node) for node in swift_nodes]
print "***********************************************************"

###################################################################
# Set up Chef Server
###################################################################

cookbooks = [
    {
        "url": "https://github.com/rcbops/chef-cookbooks.git",
        "branch": "{0}".format(results.branch),
        "tag": "{0}".format(results.repo_tag)
    },
    {
        "url": "https://github.com/rcbops-cookbooks/swift-lite.git",
        "branch": "master"
    },
    {
        "url": "https://github.com/rcbops-cookbooks/swift-private-cloud.git",
        "branch": "master"
    }
]

# Set the node to be chef server
rpcsqa.set_node_in_use(chef_server, 'chef-server')

# Need to prep centos boxes
if results.os_distro == 'centos':
    rpcsqa.prepare_server(chef_server)

# Remove Chef from chef_server Node
rpcsqa.remove_chef(chef_server)

# Build Chef Server
rpcsqa.build_chef_server(chef_server)

# Install the proper cookbooks
for cookbook in cookbooks:
    rpcsqa.install_cookbook(chef_server, cookbook['url'], cookbook['branch'])

# setup environment file to remote chef server
rpcsqa.setup_remote_chef_environment(chef_server, env)

# Setup Remote Client
config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

###################################################################
# Build Swift Keystone
###################################################################

# Make controller
rpcsqa.set_node_in_use(keystone_server, 'swift_keystone')

# Need to prep centos boxes
if results.os_distro == 'centos':
    rpcsqa.prepare_server(keystone_server)

rpcsqa.remove_chef(keystone_server)
rpcsqa.bootstrap_chef(keystone_server, chef_server)
rpcsqa.build_controller(keystone_server,
                        env,
                        remote=results.remote_chef,
                        chef_config_file=config_file)
