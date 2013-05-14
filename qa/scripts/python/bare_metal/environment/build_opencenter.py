#!/usr/bin/python
import sys
import time
import json
import requests
import argparse
from rpcsqa_helper import *
from chef import Search, Environment, Node

"""
This script will automatically build a OpenCenter cluster
@param name         Name of the cluster
@param cluster_size Size of the cluster
@param server_vms   Whether or not to install OpenCenter Server and
                    Chef Server on VM's on the Controller node
@param os           The operating system to install on (Ubuntu, Centos)
@param repo_url     The URL of the OpenCenter install script
@param action       What to do with the cluster (build, destroy)
"""
script = ("https://raw.github.com/rcbops/opencenter-install-scripts/"
          "sprint/install-dev.sh")
# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False,
                    default="test",
                    help="Name for the opencenter chef environment")

parser.add_argument('--cluster_size', action="store", dest="cluster_size",
                    required=False, default=1,
                    help="Size of the OpenCenter cluster to build")

parser.add_argument('--server_vms', action="store_true", dest="server_vms",
                    required=False, default=False,
                    help=("Whether or not to install opencenter server and"
                          "chef server on vms on the controller"))

parser.add_argument('--os', action="store", dest="os", required=False,
                    default='ubuntu',
                    help="Operating System to use for opencenter")

parser.add_argument('--repo_url', action="store", dest="repo", required=False,
                    default=script,
                    help="URL of the OpenCenter install scripts")

parser.add_argument('--action', action="store", dest="action", required=False,
                    default="build",
                    help="Action to do for opencenter (build/destroy)")

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

parser.add_argument('--clear_pool', action="store_true", dest="clear_pool",
                    default=True, required=False)

# Save the parsed arguments
results = parser.parse_args()

# If we want vms, assign them ips, these ips are static which means we can only
# have 1 ubuntu and 1 centos cluster running vms when testing.
# We may need to change this later but as this is a matrix for support only 1
# cluster testing should be needed. Maybe not?
# If not we need a more clever way of assigning ips to the vms

if results.server_vms:
    vm_bridge = 'ocbr0'
    if results.os == 'ubuntu':
        oc_server_ip = '198.101.133.150'
        chef_server_ip = '198.101.133.151'
        vm_bridge_device = 'eth0'
    else:
        print "%s isn't supported for vm deploy, try Ubuntu" % results.os
        sys.exit(1)
        # !!!When CentOS gets support, turn these on!!!
        # oc_server_ip = '198.101.133.152'
        # chef_server_ip = '198.101.133.153'
        # vm_bridge_device = 'em1'

"""
Steps
1. Make an environment for {{name}}-{{os}}-opencenter
2. Grab (cluster_size) amount of active models and change their env to
   {{name}}-{{os}}
3. Remove chef from all boxes
4. Pick one for server and install opencenter-server
5. Install opencenter-agent on the rest of the boxes.
"""

rpcsqa = rpcsqa_helper(results.razor_ip)

# Set the cluster size
cluster_size = int(results.cluster_size)

# Remove broker fails for qa-%os-pool
rpcsqa.remove_broker_fail("qa-%s-pool" % results.os)

# Prepare environment
name = '%s-opencenter' % results.name
env = rpcsqa.prepare_environment(results.os, name)

# Gather all the nodes for the os
all_nodes = rpcsqa.gather_all_nodes(results.os)

# Clean up the current running environment
rpcsqa.cleanup_environment(env)

# Collect environment and install opencenter.
if results.action == "build":

    count = 0
    opencenter_list = rpcsqa.gather_size_nodes(results.os, env, cluster_size)
    #Collect the amount of servers we need for the opencenter install

    if not opencenter_list:
        print "No nodes"
        sys.exit(1)

    # Install chef and opencenter on vms on the controller
    if results.server_vms:
        # Set the controller and compute lists
        controller = opencenter_list[0]
        computes = opencenter_list[1:]

        # Check to make sure the VMs ips dont ping
        # Ping the opencenter vm
        oc_ping = rpcsqa.ping_check_vm(oc_server_ip)
        if oc_ping['success']:
            print "OpenCenter VM pinged, tear down old vms before proceeding"
            sys.exit(1)

        # Ping the chef server vm
        cf_ping = rpcsqa.ping_check_vm(chef_server_ip)
        if cf_ping['success']:
            print "Chef Server VM pinged, tear down old vms before proceeding"
            sys.exit(1)

        # Open file containing vm login info, load into variable
        try:
            # Open the file
            fo = open("/var/lib/jenkins/source_files/vminfo.json", "r")
        except IOError:
            print "Failed to open /var/lib/jenkins/source_files/vminfo.json"
            sys.exit(1)
        else:
            # Write the json string
            vminfo = json.loads(fo.read())

            #close the file
            fo.close()

            # print message for debugging
            vminfo = "/var/lib/jenkins/source_files/vminfo.json"
            print "%s successfully open, read, and closed." % vminfo


        controller_ip = rpscqa.set_node_in_use(controller, "controller")

        #Remove chef on controller
        rpcsqa.remove_chef(controller)

        # Prepare the server by installing needed packages
        print "Preparing the VM host server"
        rpcsqa.prepare_vm_host(controller)

        # Get github user info
        github_user = vminfo['github_info']['user']
        github_user_pass = vminfo['github_info']['password']

        # Clone Repo onto controller
        print "Cloning setup script repo onto %s" % controller
        rpcsqa.clone_git_repo(controller, github_user, github_user_pass)

        # install the server vms and ping check them
        print "Setting up VMs on the host server"
        rpcsqa.install_server_vms(controller, oc_server_ip, chef_server_ip, vm_bridge, vm_bridge_device)

        # Need to sleep for 30 seconds to let virsh completely finish
        print "Sleeping for 30 seconds to let VM's complete..."
        time.sleep(30)

        # Ping the opencenter vm
        oc_ping = rpcsqa.ping_check_vm(oc_server_ip)
        if not oc_ping['success']:
            print "OpenCenter VM failed to ping..."
            print "Return Code: %s" % oc_ping['exception'].returncode
            print "Output: %s" % oc_ping['exception'].output
            sys.exit(1)
        else:
            print "OpenCenter Server VM set up and pinging..."

        # Ping the chef server vm
        cf_ping = rpcsqa.ping_check_vm(chef_server_ip)
        if not cf_ping['success']:
            print "OpenCenter VM failed to ping..."
            print "Return Code: %s" % cf_ping['exception'].returncode
            print "Output: %s" % cf_ping['exception'].output
            sys.exit(1)
        else:
            print "Chef Server VM set up and pinging..."

        # Get vm user info
        vm_user = vminfo['user_info']['user']
        vm_user_pass = vminfo['user_info']['password']

        # Install OpenCenter Server / Dashboard on VM
        rpcsqa.install_opencenter_vm(oc_server_ip, oc_server_ip, results.repo, 'server', vm_user, vm_user_pass)
        rpcsqa.install_opencenter_vm(oc_server_ip, oc_server_ip, results.repo, 'dashboard', vm_user, vm_user_pass)

        # Install OpenCenter Client on Chef VM
        rpcsqa.install_opencenter_vm(chef_server_ip, oc_server_ip, results.repo, 'agent', vm_user,vm_user_pass)

        # Install OpenCenter Client on Controller
        rpcsqa.install_opencenter(controller, results.repo, 'agent', oc_server_ip)

        # Install OpenCenter Client on Computes
        for compute in computes:
            compute_ip = rpcsqa.set_node_in_use(compute, "agent")
            rpcsqa.remove_chef(compute)
            rpcsqa.install_opencenter(compute, results.repo, 'agent', oc_server_ip)

        # Print Cluster Info
        print "************************************************************"
        print "2 VMs, 1 controller ( VM Host ), %i Agents" % len(computes)
        print "OpenCenter Server (VM) with IP: %s on Host: %s" % (oc_server_ip, controller)
        print "Chef Server (VM) with IP: %s on Host: %s" % (chef_server_ip, controller)
        print "Controller Node: %s with IP: %s" % (controller, controller_ip)
        for agent in computes:
            node = Node(agent)
            print "Agent Node: %s with IP: %s" % (agent, node['ipaddress'])
        print "************************************************************"

    else:
        #Pick an opencenter server, and rest for agents
        server = opencenter_list[0]
        dashboard = []
        clients = []
        if len(opencenter_list) > 1:
            dashboard = opencenter_list[1]
        if len(opencenter_list) > 2:
            agents = opencenter_list[2:]

        #Remove chef client...install opencenter server
        print "Making %s the server node" % server
        server_ip = rpcsqa.set_node_in_use(server, "server")
        rpcsqa.remove_chef(server)
        rpcsqa.install_opencenter(server, results.repo, 'server')

        if dashboard:
            dashboard_ip = rpcsqa.set_node_in_use(dashboard, "dashboard")
            rpcsqa.remove_chef(dashboard)
            rpcsqa.install_opencenter(dashboard, results.repo, 'dashboard', server_ip)

        for agent in agents:
            agent_ip = rpcsqa.set_node_in_use(agent, 'agent')
            rpcsqa.remove_chef(agent)
            rpcsqa.install_opencenter(agent, results.repo, 'agent', server_ip)

        print ""
        print ""
        print ""
        print ""

        dashboard_url = ""
        try:
            r = requests.get("https://%s" % dashboard_ip,
                             auth=('admin', 'password'),
                             verify=False)
            dashboard_url = "https://%s" % dashboard_ip
        except:
            dashboard_url = "http://%s:3000" % dashboard_ip
            pass

        print "***************************************************************"
        print "Server: %s - %s  " % (server, server_ip)
        print "Dashboard: %s - %s " % (dashboard, dashboard_url)
        rpcsqa.print_computes_info(agents)
        print "***************************************************************"
        print ""
        print ""
        print ""
        print ""
