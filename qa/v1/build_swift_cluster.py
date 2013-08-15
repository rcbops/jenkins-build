#!/usr/bin/python
import argparse
from modules.rpcsqa_helper import *
from modules.chef_helper import *

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
                    required=False, default=True,
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

# Set the cluster size
cluster_size = int(results.cluster_size)

# Build a new cluster
if results.action == "build":

    # Clean up the current running environment
    rpcsqa.cleanup_environment(env)

    # If we are testing swift, we need 1 controller, 1 proxy and 3 swift nodes
    if cluster_size < 5:
        print "Swift Selected, setting cluster size to 5 (minimum)"
        cluster_size = 5

    # If remote_chef is enabled, add one to the cluster size
    if results.remote_chef:
        print "You wanted a remote chef server, adding 1 to cluster size"
        cluster_size += 1

    # Collect the amount of servers we need for the swift install
    rpcsqa.check_cluster_size(all_nodes, cluster_size)

    # Gather the nodes and set there environment
    openstack_list = rpcsqa.gather_size_nodes(results.os_distro,
                                              env,
                                              cluster_size)

    # If there were no nodes available, exit
    if not openstack_list:
        print "No nodes available..."
        sys.exit(1)

    # Assign nodes to names
    chef_server = openstack_list[0]
    management_server = openstack_list[1]
    swift_proxy = openstack_list[2]
    swift_nodes = openstack_list[3:]

    # print all servers info
    print "***********************************************************"
    print "Chef Server: {0}".format(rpcsqa.print_server_info(chef_server))
    print "Keystone Server {0}".format(rpcsqa.print_server_info(management_server))
    print "Swift Proxy {0}".format(rpcsqa.print_server_info(swift_proxy))
    print "Swift Storage Nodes: "
    print [rpcsqa.print_server_info(node) for node in swift_nodes]
    print "***********************************************************"

    cookbooks = [
        {
            "url": "https://github.com/rcbops-cookbooks/swift-private-cloud.git",
            "branch": "master",
            "tag": results.repo_tag
        }
    ]

    swift_roles = {
        "controller": "spc-starter-controller",
        "proxy": "spc-starter-proxy",
        "storage": "spc-starter-storage"
    }

    # Get the IP of the proxy server and load it into environment
    keystone_ip = rpcsqa.get_node_ip(management_server)
    keystone = {
        "keystone": {
            "swift_admin_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip),
            "swift_public_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip),
            "swift_internal_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip)
        }
    }

    ###################################################################
    # Set up Chef Server
    ###################################################################

    # Override the keystone attributes
    rpcsqa.set_environment_variables(env, keystone, 'override')

    # Set the node to be chef server
    rpcsqa.set_node_in_use(chef_server, 'chef-server')

    # Need to prep centos boxes
    if results.os_distro == 'centos':
        rpcsqa.prepare_server(chef_server)

    # Remove Chef from chef_server Node
    rpcsqa.remove_chef(chef_server)

    # Build Chef Server
    rpcsqa.build_chef_server(chef_server)

    # Install Berkshelf , This is a convoluded mess, thanks ruby
    rpcsqa.install_berkshelf(chef_server)

    # Install the proper cookbooks
    rpcsqa.install_cookbooks(chef_server, cookbooks, '/opt/rcbops')

    # Gather Chef node
    chef_node = rpcsqa.get_server_info(chef_server)

    # Drop config.json onto berkshelf to overwrite verify
    command = ('cd .berkshelf; echo "{\"ssl\":{\"verify\":false}}" > config.json')
    rpcsqa.run_cmd_on_node(chef_node['node'], command)

    # Run berkshelf on server
    command = ('cd /opt/rcbops/swift-private-cloud; '
               'source /usr/local/rvm/scripts/rvm; '
               'berks install; '
               'berks upload')
    rpcsqa.run_cmd_on_node(chef_node['node'], command)

    # setup environment file to remote chef server
    rpcsqa.setup_remote_chef_environment(chef_server, env)

    # Setup Remote Client
    config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

    ###################################################################
    # Build Swift Management (keystone)
    ###################################################################

    # Make keystone server
    rpcsqa.set_node_in_use(management_server, swift_roles['controller'])

    # Need to prep centos boxes
    if results.os_distro == 'centos':
        rpcsqa.prepare_server(management_server)

    # Remove Razor/Chef chef and bootstrap to new chef server
    rpcsqa.remove_chef(management_server)
    rpcsqa.bootstrap_chef(management_server, chef_server)

    # Build Swift Keystone Node
    rpcsqa.build_swift_node(management_server,
                            swift_roles['controller'],
                            env,
                            remote=results.remove_chef,
                            chef_config_file=chef_config_file)

    ###################################################################
    # Build Swift Proxy
    ###################################################################

    # Make Swift Proxy Node
    rpcsqa.set_node_in_use(swift_proxy, swift_roles['proxy'])

    # Need to prep centos boxes
    if results.os_distro == 'centos':
        rpcsqa.prepare_server(swift_proxy)

    # Remove Razor/Chef and bootstrap to new chef server
    rpcsqa.remove_chef(swift_proxy)
    rpcsqa.bootstrap_chef(swift_proxy, chef_server)

    # Build Swift Proxy Node
    rpcsqa.build_swift_node(swift_proxy,
                            swift_roles['proxy'],
                            env,
                            remote=results.remote_chef,
                            chef_config_file=config_file)

    ###################################################################
    # Build Swift Object Storage Boxes
    ###################################################################

    for node in swift_nodes:

        # Make Swift Proxy Node
        rpcsqa.set_node_in_use(node, swift_roles['storage'])

        # Need to prep centos boxes
        if results.os_distro == 'centos':
            rpcsqa.prepare_server(node)

        # Remove Razor/Chef and bootstrap to new chef server
        rpcsqa.remove_chef(node)
        rpcsqa.bootstrap_chef(node, chef_server)

        # Build Swift Proxy Node
        rpcsqa.build_swift_node(node,
                                swift_roles['storage'],
                                env,
                                remote=results.remote_chef,
                                chef_config_file=config_file)

    #################################################################
    # Run chef on management server again
    #################################################################

    management_node = Node(management_server, api=self.chef)
    print "Swift Setup...running chef client on {0} to finish setup...".format(management_server)
    rpcsqa.run_chef_client(management_node)

    #################################################################
    # Successful Setup, exit
    #################################################################

    # print all servers info
    print "***********************************************************"
    print "Chef Server: {0}".format(rpcsqa.print_server_info(chef_server))
    print "Keystone Server {0}".format(rpcsqa.print_server_info(management_server))
    print "Swift Proxy {0}".format(rpcsqa.print_server_info(swift_proxy))
    print "Swift Storage Nodes: "
    print [rpcsqa.print_server_info(node) for node in swift_nodes]
    print "***********************************************************"
