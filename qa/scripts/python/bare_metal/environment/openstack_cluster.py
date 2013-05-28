#!/usr/bin/python
import sys
import argparse
from rpcsqa_helper import *
from chef_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False,
                    default="test",
                    help="Name for the Open Stack chef environment")

parser.add_argument('--branch', action="store", dest="branch", required=False,
                    default="folsom",
                    help="The OpenStack Distribution (i.e. folsom, grizzly")

parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False, default="glance-cf",
                    help="Feature_set for the Open Stack chef environment")

parser.add_argument('--cluster_size', action="store", dest="cluster_size",
                    required=False, default=4,
                    help="Size of the Open Stack cluster.")

parser.add_argument('--ha_enabled', action='store_true', dest='ha_enabled',
                    required=False, default=False,
                    help="Do you want to HA this environment?")

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

# Remove broker fails for qa-%os_distro-pool
rpcsqa.remove_broker_fail("qa-%s-pool" % results.os_distro)

#Prepare environment
env = rpcsqa.prepare_environment(results.name,
                                 results.os_distro,
                                 results.feature_set,
                                 results.branch)

# Clean up the current running environment
rpcsqa.cleanup_environment(env)

# Set the cluster size
cluster_size = int(results.cluster_size)

# Gather all the nodes for the os_distro
all_nodes = rpcsqa.gather_all_nodes(results.os_distro)

if results.action == "build":

    # Check the cluster size, if < 5 and
    # results.dir_service is enabled, set to 4
    if cluster_size < 4 and results.dir_service:
        if results.ha_enabled:
            cluster_size = 5
            print "HA and Directory Services are requested, re-setting cluster size to %i." % cluster_size
        else:
            cluster_size = 4
            print "Directory Services are requested, re-setting cluster size to %i." % cluster_size
    elif cluster_size < 4 and results.ha_enabled:
        cluster_size = 4
        print "HA is enabled, re-setting cluster size to %i." % cluster_size
    else:
        print "Cluster size is %i." % cluster_size

    # If remote_chef is enabled, add one to the cluster size
    if results.remote_chef:
        print "You wanted a remote chef server, adding 1 to cluster size"
        cluster_size += 1

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

    # Remote Chef Server Builds
    if results.remote_chef:

        # Build cluster accordingly
        if results.dir_service and results.ha_enabled:

            # JOHN
            # REMOVE THIS WHEN YOU GET THIS WORKING
            print "Not Implemented....Talk to John Curran"
            sys.exit(1)

            # Set each servers roles
            dir_server = openstack_list[0]
            ha_controller_1 = openstack_list[1]
            ha_controller_2 = openstack_list[2]
            computes = openstack_list[3:]

            # Build directory service server
            rpcsqa.build_dir_server(dir_server, results.dir_version)

            # Build HA Controllers
            rpcsqa.build_controller(ha_controller_1, True, 1)
            rpcsqa.build_controller(ha_controller_2, True, 2)

            # Have to run chef client on controller 1 again
            ha_controller_1_node = Node(ha_controller_1)
            rpcsqa.run_chef_client(ha_controller_1_node)

            # Build computes
            rpcsqa.build_computes(computes)

            # print all servers info
            print "***********************************************************"
            print "Directory Service Server: %s" % (
                rpcsqa.print_server_info(dir_server))
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        elif results.dir_service:

            # JOHN
            # REMOVE THIS WHEN YOU GET THIS WORKING
            print "Not Implemented....Talk to John Curran"
            sys.exit(1)

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
            print "Controller: %s" % (
                rpcsqa.print_server_info(controller))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        elif results.ha_enabled:

            # Set each servers roles
            chef_server = openstack_list[0]
            ha_controller_1 = openstack_list[1]
            ha_controller_2 = openstack_list[2]
            computes = openstack_list[3:]

            ###################################################################
            # Set up Chef Server
            ###################################################################

            # Set the node to be chef server
            rpcsqa.set_node_in_use(chef_server, 'chef-server')

            # Remove Chef from chef_server Node
            rpcsqa.remove_chef(chef_server)

            # Build Chef Server
            rpcsqa.build_chef_server(chef_server)

            # Install the proper cookbooks
            rpcsqa.install_cookbooks(chef_server, results.branch)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)

            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make the controllers
            rpcsqa.build_controller(ha_controller_1,
                                    environment=env,
                                    ha_num=1,
                                    remote=True,
                                    chef_config_file=config_file)
            rpcsqa.build_controller(ha_controller_1,
                                    environment=env,
                                    ha_num=2,
                                    remote=True,
                                    chef_config_file=config_file)

            remote_chef_api = chef_helper(config_file)

            # Have to run chef client on controller 1 again
            ha_controller_1_node = Node(ha_controller_1,
                                        api=remote_chef_api.chef)
            print "HA Setup...run chef client on %s again " % ha_controller_1
            remote_chef_api.run_chef_client(ha_controller_1_node)

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
            chef_server = openstack_list[0]
            controller = openstack_list[1]
            computes = openstack_list[2:]

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
            rpcsqa.install_cookbooks(chef_server, results.branch)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(chef_server, env)

            # Setup Remote Client
            config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

            ###################################################################
            # Build Openstack Environment
            ###################################################################

            # Make controller
            rpcsqa.remove_chef(controller)
            rpcsqa.bootstrap_chef(controller, chef_server)
            rpcsqa.build_controller(controller,
                                    env,
                                    remote=results.remote_chef,
                                    chef_config_file=config_file)

            # Make computes
            for compute in computes:
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

        # Build cluster accordingly
        if results.dir_service and results.ha_enabled:

            # Set each servers roles
            dir_server = openstack_list[0]
            ha_controller_1 = openstack_list[1]
            ha_controller_2 = openstack_list[2]
            computes = openstack_list[3:]

            # Build directory service server
            rpcsqa.build_dir_server(dir_server, results.dir_version)

            # Build HA Controllers
            rpcsqa.build_controller(ha_controller_1, True, 1)
            rpcsqa.build_controller(ha_controller_2, True, 2)

            # Have to run chef client on controller 1 again
            ha_controller_1_node = Node(ha_controller_1)
            rpcsqa.run_chef_client(ha_controller_1_node)

            # Build computes
            rpcsqa.build_computes(computes)

            # print all servers info
            print "***********************************************************"
            print "Directory Service Server: %s" % (
                rpcsqa.print_server_info(dir_server))
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"

        elif results.dir_service:

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

elif results.action == 'destroy':
    rpcsqa.clear_pool(all_nodes, env)

else:
    print "Action %s is not supported..." % results.action
    sys.exit(1)
