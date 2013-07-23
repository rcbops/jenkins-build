#!/usr/bin/python
import sys
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

parser.add_argument('--ha_enabled', action='store_true', dest='ha_enabled',
                    required=False, default=False,
                    help="Do you want to HA this environment?")

parser.add_argument('--quantum', action='store_true', dest='quantum',
                    required=False, default=False,
                    help="Do you want quantum networking")

parser.add_argument('--dir_service', action='store_true', dest='dir_service',
                    required=False, default=False,
                    help="Use a directory management?")

parser.add_argument('--dir_version', action='store', dest='dir_version',
                    required=False, default='openldap',
                    help="Which directory management to use? (openldap/389)")

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

# Set the cluster size
cluster_size = int(results.cluster_size)

cookbooks = [
    {
        "url": "https://github.com/rcbops/chef-cookbooks.git",
        "branch": "{0}".format(results.branch),
        "tag": "{0}".format(results.repo_tag)
    }
]

# Build a new cluster
if results.action == "build":

    # Clean up the current running environment
    rpcsqa.cleanup_environment(env)

    # If either HA is enabled or Dir Service is enabled and the cluster
    # size is < 3, set the cluster size to 3
    if (results.dir_service or results.ha_enabled or results.quantum) and cluster_size < 3:
        print "Either HA / Directory Service / Quantum was requested, resizing cluster to 3."
        cluster_size = 3

    # If remote_chef is enabled, add one to the cluster size
    if results.remote_chef:
        print "You wanted a remote chef server, adding 1 to cluster size"
        cluster_size += 1

    print "Cluster size is %i." % cluster_size

    # Collect the amount of servers we need for the openstack install
    rpcsqa.check_cluster_size(all_nodes, cluster_size)

    # Gather the nodes and set there environment
    openstack_list = rpcsqa.gather_size_nodes(results.os_distro,
                                              env,
                                              cluster_size)

    # If there were no nodes available, exit
    if not openstack_list:
        print "No nodes available..."
        sys.exit(1)

    # If ha and dir are selected, exit (not supported)
    if results.ha_enabled and results.dir_service:
        print "No support currently enabled for ha and dir service in the same build. Sorry :("
        sys.exit(1)

    # Remote Chef Server Builds
    if results.remote_chef:

        # Build OpenStack cluster with LDAP keystone service
        if results.dir_service:

            # Set each servers roles
            dir_server = openstack_list[0]
            chef_server = openstack_list[1]
            controller = openstack_list[2]
            computes = openstack_list[3:]

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Directory Service Server: %s" % (
                rpcsqa.print_server_info(dir_server))
            print "Controller: %s" % (
                rpcsqa.print_server_info(controller))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            ###################################################################
            # Set up LDAP Server
            ###################################################################
            # Build the dir server
            rpcsqa.set_node_in_use(dir_server, 'dir_server')
            rpcsqa.build_dir_server(dir_server,
                                    results.dir_version,
                                    results.os_distro)

            ###################################################################
            # Set up Chef Server
            ###################################################################

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
            rpcsqa.install_cookbooks(chef_server,
                                     results.branch,
                                     results.repo_tag)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)
            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make controller
            rpcsqa.set_node_in_use(controller, 'controller')
            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(controller)
            rpcsqa.remove_chef(controller)
            rpcsqa.bootstrap_chef(controller, chef_server)
            rpcsqa.build_controller(controller,
                                    env,
                                    remote=results.remote_chef,
                                    chef_config_file=config_file)
            # Make computes
            for compute in computes:
                rpcsqa.set_node_in_use(compute, 'compute')
                # Need to prep centos boxes
                if results.os_distro == 'centos':
                    rpcsqa.prepare_server(compute)
                rpcsqa.remove_chef(compute)
                rpcsqa.bootstrap_chef(compute, chef_server)
                rpcsqa.build_compute(compute,
                                     env,
                                     remote=results.remote_chef,
                                     chef_config_file=config_file)

            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Directory Service Server: %s" % (
                rpcsqa.print_server_info(dir_server))
            print "Controller: %s" % (
                rpcsqa.print_server_info(controller))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        # Build OpenStack HA cluster
        elif results.ha_enabled:

            # Set each servers roles
            chef_server = openstack_list[0]
            ha_controller_1 = openstack_list[1]
            ha_controller_2 = openstack_list[2]
            computes = openstack_list[3:]

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            ###################################################################
            # Set up Chef Server
            ###################################################################

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
            rpcsqa.install_cookbooks(chef_server, cookbooks)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)

            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make the controllers
            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(ha_controller_1)
            rpcsqa.set_node_in_use(ha_controller_1, 'controller')
            rpcsqa.remove_chef(ha_controller_1)
            rpcsqa.bootstrap_chef(ha_controller_1, chef_server)
            rpcsqa.build_controller(ha_controller_1,
                                    environment=env,
                                    ha_num=1,
                                    remote=True,
                                    chef_config_file=config_file)
            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(ha_controller_2)
            rpcsqa.set_node_in_use(ha_controller_2, 'controller')
            rpcsqa.remove_chef(ha_controller_2)
            rpcsqa.bootstrap_chef(ha_controller_2, chef_server)
            rpcsqa.build_controller(ha_controller_2,
                                    environment=env,
                                    ha_num=2,
                                    remote=True,
                                    chef_config_file=config_file)

            # Have to run chef client on controller 1 again
            ha_controller_1_node = Node(ha_controller_1, api=rpcsqa.chef)
            print "HA Setup...run chef client on %s again " % ha_controller_1
            rpcsqa.run_chef_client(ha_controller_1_node)

            # build computes
            for compute in computes:
                rpcsqa.set_node_in_use(compute, 'compute')

                # Need to prep centos boxes
                if results.os_distro == 'centos':
                    rpcsqa.prepare_server(compute)

                rpcsqa.remove_chef(compute)
                rpcsqa.bootstrap_chef(compute, chef_server)
                rpcsqa.build_compute(compute,
                                     env,
                                     remote=results.remote_chef,
                                     chef_config_file=config_file)

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        # Build OpenStack cluster with quantum networking
        elif results.quantum:
            chef_server = openstack_list[0]
            controller = openstack_list[1]
            quantum = openstack_list[2]
            computes = openstack_list[3:]

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller %s" % rpcsqa.print_server_info(controller)
            print "Quantum %s" % rpcsqa.print_server_info(quantum)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            ###################################################################
            # Set up Chef Server
            ###################################################################

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
            rpcsqa.install_cookbooks(chef_server, cookbooks)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)

            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make controller
            rpcsqa.set_node_in_use(controller, 'controller')

            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(controller)

            rpcsqa.remove_chef(controller)
            rpcsqa.bootstrap_chef(controller, chef_server)
            rpcsqa.build_controller(controller,
                                    env,
                                    remote=results.remote_chef,
                                    chef_config_file=config_file)

            # Make Quantum Node
            rpcsqa.set_node_in_use(quantum, 'quantum')

            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(quantum)

            rpcsqa.remove_chef(quantum)
            rpcsqa.bootstrap_chef(quantum, chef_server)
            rpcsqa.build_quantum_network_node(quantum,
                                              env,
                                              remote=results.remote_chef,
                                              chef_config_file=config_file)

            # Make computes
            for compute in computes:
                rpcsqa.set_node_in_use(compute, 'compute')

                # Need to prep centos boxes
                if results.os_distro == 'centos':
                    rpcsqa.prepare_server(compute)

                rpcsqa.remove_chef(compute)
                rpcsqa.bootstrap_chef(compute, chef_server)
                rpcsqa.build_compute(compute,
                                     env,
                                     remote=results.remote_chef,
                                     chef_config_file=config_file)

            # Setup the Quantum Network
            rpcsqa.setup_quantum_network(env)

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller %s" % rpcsqa.print_server_info(controller)
            print "Quantum %s" % rpcsqa.print_server_info(quantum)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        # Build base OpenStack cluster
        else:

            # Set each servers roles
            chef_server = openstack_list[0]
            controller = openstack_list[1]
            computes = openstack_list[2:]

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller: %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            ###################################################################
            # Set up Chef Server
            ###################################################################

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
            rpcsqa.install_cookbooks(chef_server, cookbooks)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)

            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make controller
            rpcsqa.set_node_in_use(controller, 'controller')

            # Need to prep centos boxes
            if results.os_distro == 'centos':
                rpcsqa.prepare_server(controller)

            rpcsqa.remove_chef(controller)
            rpcsqa.bootstrap_chef(controller, chef_server)
            rpcsqa.build_controller(controller,
                                    env,
                                    remote=results.remote_chef,
                                    chef_config_file=config_file)

            # Make computes
            for compute in computes:
                rpcsqa.set_node_in_use(compute, 'compute')

                # Need to prep centos boxes
                if results.os_distro == 'centos':
                    rpcsqa.prepare_server(compute)

                rpcsqa.remove_chef(compute)
                rpcsqa.bootstrap_chef(compute, chef_server)
                rpcsqa.build_compute(compute,
                                     env,
                                     remote=results.remote_chef,
                                     chef_config_file=config_file)

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller: %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

    # NON REMOTE CHEF SERVER BUILDS
    else:

        if results.dir_service:

            # Set each servers roles
            dir_server = openstack_list[0]
            controller = openstack_list[1]
            computes = openstack_list[2:]

            # Build the dir server
            rpcsqa.build_dir_server(dir_server,
                                    results.dir_version,
                                    results.os_distro)

            # Build controller
            rpcsqa.build_controller(controller)

            # Build computes
            rpcsqa.build_computes(computes)

            # print all servers info
            print "***********************************************************"
            print "Directory Service Server: %s" % (
                rpcsqa.print_server_info(dir_server))
            print "Controller: %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        elif results.ha_enabled:

            # Set each servers roles
            ha_controller_1 = openstack_list[0]
            ha_controller_2 = openstack_list[1]
            computes = openstack_list[2:]

            # print all servers info
            print "***********************************************************"
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            # Make the controllers
            rpcsqa.build_controller(ha_controller_1, True, 1)
            rpcsqa.build_controller(ha_controller_2, True, 2)

            # Have to run chef client on controller 1 again
            ha_controller_1_node = Node(ha_controller_1)
            print "HA Setup...have to run chef client on %s again cause it is ha-controller1..." % ha_controller_1
            rpcsqa.run_chef_client(ha_controller_1_node)

            # build computes
            rpcsqa.build_computes(computes)

            # print all servers info
            print "***********************************************************"
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        else:

            # Set each servers roles
            controller = openstack_list[0]
            computes = openstack_list[1:]

            # print all servers info
            print "***********************************************************"
            print "Controller: %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

            # Make servers
            rpcsqa.build_controller(controller)
            rpcsqa.build_computes(computes, env)

            # print all servers info
            print "***********************************************************"
            print "Controller: %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

# We want to add more nodes to the environment
elif results.action == 'add':

    # make sure there is a controller
    if rpcsqa.environment_has_controller(env):

        # make sure we have enough nodes
        rpcsqa.check_cluster_size(all_nodes, cluster_size)

        # set all nodes to compute in the requested environment
        computes = rpcsqa.gather_nodes(all_nodes, env, cluster_size)

        # If there were no nodes available, exit
        if not computes:
            print "No nodes available..."
            sys.exit(1)

        # Build out the computes
        rpcsqa.build_computes(computes)
        rpcsqa.print_computes_info(computes)

    else:
        print "Chef Environment %s doesnt have a controller, cant take action %s" % (env, results.action)
        sys.exit(1)

# Destroy the enviornment (teardown cluster, free up nodes)
elif results.action == 'destroy':
    print "Destroying environment: %s" % env
    rpcsqa.cleanup_environment(env)
    Environment(env, api=rpcsqa.chef).delete()

# Bad action, try again
else:
    print "Action %s is not supported..." % results.action
    sys.exit(1)
