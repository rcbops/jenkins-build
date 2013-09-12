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

parser.add_argument('--neutron', action='store_true', dest='neutron',
                    required=False, default=False,
                    help="Do you want neutron networking")

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
if results.action == 'build':
    rpcsqa.remove_broker_fail("qa-%s-pool" % results.os_distro)

# Prepare environment
env = rpcsqa.prepare_environment(results.name,
                                 results.os_distro,
                                 results.feature_set,
                                 results.branch)

if results.os_distro == "centos":
    bridge_dev = "em2"
else:
    bridge_dev = "eth1"

# replace networks with older schema for non neutron builds
if (results.branch in ["folsom"] or results.repo_tag in ["3.1.0", "4.0.0"]) and results.neutron is False:

    old_networks = [{
        "num_networks": "1",
        "bridge": "br0",
        "label": "public",
        "dns1": "8.8.8.8",
        "dns2": "8.8.4.4",
        "bridge_dev": bridge_dev,
        "network_size": "254",
        "ipv4_cidr": "172.31.0.0/24"
    }]

    print "reverting to old network schema"
    env_obj = Environment(env)
    env_obj.override_attributes['nova']['networks'] = old_networks
    env_obj.save()

# If we have a HA Environment with neutron networking,
# set the env properly
if results.ha_enabled and results.neutron:

    neutron_network = {"provider": "quantum"}
    quantum_network = {"ovs": { "network_type": "gre"}}

    print "Setting HA network to neutron"
    env_obj = Environment(env)

    # Change the nova network attribute to be neutron
    env_obj.override_attributes['nova']['network'] = neutron_network
    env_obj.override_attributes['quantum'] = quantum_network
    
    # Remove the networks attribute
    env_obj.override_attributes['nova'].pop("networks", None)
    
    # Save node
    env_obj.save()

# Gather all the nodes for the os_distro
all_nodes = rpcsqa.gather_all_nodes(results.os_distro)

# Set the cluster size
cluster_size = int(results.cluster_size)

cookbooks = [
    {
        "url": "https://github.com/rcbops/chef-cookbooks.git",
        "branch": "{0}".format(results.branch),
        "tag": results.repo_tag
    }
]

# Build a new cluster
if results.action == "build":

    # Clean up the current running environment
    rpcsqa.cleanup_environment(env)

    # If either HA is enabled or Dir Service is enabled and the cluster
    # size is < 3, set the cluster size to 3
    if (results.dir_service or results.ha_enabled) and cluster_size < 3:
        print "Either HA / Directory Service was requested, resizing cluster to 3."
        cluster_size = 3

    # If remote_chef is enabled, add one to the cluster size
    if results.remote_chef:
        print "You wanted a remote chef server, adding 1 to cluster size"
        cluster_size += 1

    print "Cluster size is %i." % cluster_size

    # Collect the amount of servers we need for the openstack install
    enough_nodes = rpcsqa.check_cluster_size(all_nodes, cluster_size)
    if enough_nodes is False:
        print "*****************************************************"
        print "Not enough nodes for the cluster_size given: {0}".format(cluster_size)
        print "*****************************************************"
        rpcsqa.cleanup_environment(env)
        sys.exit(1)


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

            # Add remote chef credentials to local chef server
            rpcsqa.add_remote_chef_locally(chef_server, env)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(env)
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
            sys.exit(0)

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

            # Add remote chef credentials to local chef server
            rpcsqa.add_remote_chef_locally(chef_server, env)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(env)

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
                                    neutron=results.neutron,
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
                                    neutron=results.neutron,
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

            # Do to kernel issues on 6.4, need to reboot all servers and rerun
            # chef client on all boxes, then setup networking
            if results.os_distro == 'centos':
                
                print "## OS is Centos, need to reboot cluster for kernel upgrades ##"
                # Reboot all nodes
                rpcsqa.reboot_cluster(env)
                
                # Logic to reboot and wait for online status to be true
                sleep_in_minutes = 5
                while rpcsqa.ping_check_cluster(env)['offline'] is True:
                    # Wait for nodes to come back online
                    print "## Current cluster online status: Offline ##"
                    print "## Sleeping for {0} minutes ##".format(str(sleep_in_minutes))
                    time.sleep(sleep_in_minutes * 60)
                    # subtract 1 each time, to prevent retarded loops
                    sleep_in_minutes -= 1

                    if sleep_in_minutes == 0:
                        print "## -- Failed to reboot cluster after 8 minutes -- ##"
                        print "## -- Please manually check -- ##"
                        sys.exit(1)

                # run chef client on all the nodes
                print "## Current cluster status is: Online ##"

                # bring up the routes
                nic_dev = 'em1'
                print "## Bringing up cluster routes on {0} ##".format(nic_dev)
                rpcsqa.bring_up_cluster_default_routes(env, nic_dev)

                # Controller 1
                print "## Running chef-client on {0} after reboot ##".format(ha_controller_1) 
                rpcsqa.run_chef_client(rpcsqa.get_server_info(ha_controller_1)['node'])
                
                # Controller 2
                print "## Running chef-client on {0} after reboot ##".format(ha_controller_2) 
                rpcsqa.run_chef_client(rpcsqa.get_server_info(ha_controller_2)['node'])

                # Computes
                for compute in computes:
                    print "## Running chef-client on {0} after reboot ##".format(compute)
                    rpcsqa.run_chef_client(rpcsqa.get_server_info(compute)['node'])

            # If Neutron enabled, setup network
            if results.neutron:
                rpcsqa.setup_neutron_network(env, results.ha_enabled)

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "HA-Controller 1: %s" % (
                rpcsqa.print_server_info(ha_controller_1))
            print "HA-Controller 2: %s" % (
                rpcsqa.print_server_info(ha_controller_2))
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"
            sys.exit(0)

        # Build OpenStack cluster with quantum networking
        elif results.neutron:
            chef_server = openstack_list[0]
            controller = openstack_list[1]
            computes = openstack_list[2:]

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller %s" % rpcsqa.print_server_info(controller)
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

            # Add remote chef credentials to local chef server
            rpcsqa.add_remote_chef_locally(chef_server, env)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(env)

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
                                    neutron=results.neutron,
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

            # Do to kernel issues on 6.4, need to reboot all servers and rerun
            # chef client on all boxes, then setup networking
            if results.os_distro == 'centos':
                
                print "## OS is Centos, need to reboot cluster for kernel upgrades ##"
                # Reboot all nodes
                rpcsqa.reboot_cluster(env)
                
                # Logic to reboot and wait for online status to be true
                sleep_in_minutes = 5
                while rpcsqa.ping_check_cluster(env)['offline'] is True:
                    # Wait for nodes to come back online
                    print "## Current cluster online status: Offline ##"
                    print "## Sleeping for {0} minutes ##".format(str(sleep_in_minutes))
                    time.sleep(sleep_in_minutes * 60)
                    # subtract 1 each time, to prevent retarded loops
                    sleep_in_minutes -= 1

                    if sleep_in_minutes == 0:
                        print "## -- Failed to reboot cluster after 8 minutes -- ##"
                        print "## -- Please manually check -- ##"
                        sys.exit(1)

                # run chef client on all the nodes
                # Controller
                print "## Current cluster status is: Online ##"
                print "## Running chef-client on {0} after reboot ##".format(controller) 
                rpcsqa.run_chef_client(rpcsqa.get_server_info(controller)['node'])
                # Computes
                for compute in computes:
                    print "## Running chef-client on {0} after reboot ##".format(compute)
                    rpcsqa.run_chef_client(rpcsqa.get_server_info(compute)['node'])

            # Setup the Quantum Network
            print "## Setting up neutron network ##"
            rpcsqa.setup_neutron_network(env)

            # print all servers info
            print "***********************************************************"
            print "Chef Server: %s" % rpcsqa.print_server_info(chef_server)
            print "Controller %s" % rpcsqa.print_server_info(controller)
            rpcsqa.print_computes_info(computes)
            print "***********************************************************"
            sys.exit(0)

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

            # Add remote chef credentials to local chef server
            rpcsqa.add_remote_chef_locally(chef_server, env)

            # setup environment file to remote chef server
            rpcsqa.setup_remote_chef_environment(env)

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
            sys.exit(0)

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


# Old Code that we no longer use but dont want to delete
'''

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
'''
