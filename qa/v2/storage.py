#!/usr/bin/python
import sys
import argh
from modules.rpcsqa_helper import rpcsqa_helper
from modules.chef_helper import chef_helper
from modules.swift_helper import swift_helper

@argh.arg('-f', "--features", nargs="+", type=str)
def build(name='autotest', branch='grizzly', tag=None,
          cluster_size=4, os_distro='precise', build_rings=False,
          remote_chef=True, razor_ip='198.101.133.3', features=[]):

    # Setup the helper class ( Chef / Razor )
    rpcsqa = rpcsqa_helper(razor_ip)

    # Have to add check for empty string due to Jenkins parameters
    if tag is not None:
        if tag == "None":
            tag = None

    # Remove broker fails for qa-%os_distro-pool
    print "## -- Removing Broker Fails from Razor for qa-{0}-pool -- ##".format(
        os_distro)
    rpcsqa.remove_broker_fail("qa-{0}-pool".format(os_distro))

    # Prepare environment
    print "## -- Preparing chef environment -- ##"
    env = rpcsqa.prepare_environment(name,
                                     os_distro,
                                     features,
                                     branch)

    # Gather all the nodes for the os_distro
    print "## -- Gathering all available nodes for {0} -- ##".format(
        os_distro)
    all_nodes = rpcsqa.gather_all_nodes(os_distro)

    # Set the cluster size
    cluster_size = int(cluster_size)


    print "## -- Beginning build of new Swift Cluster -- ##"
    # Clean up the current running environment
    rpcsqa.cleanup_environment(env)

    # If we are testing swift, we need 1 controller, 1 proxy and 3 swift nodes
    if cluster_size < 6:
        print "Swift Selected, setting cluster size to 6 (minimum)"
        cluster_size = 6

    # If remote_chef is enabled, add one to the cluster size
    if remote_chef:
        print "You wanted a remote chef server, adding 1 to cluster size"
        cluster_size += 1

    # Collect the amount of servers we need for the swift install
    print "## -- Checking to see if {0} nodes are available -- ##".format(cluster_size)
    rpcsqa.check_cluster_size(all_nodes, cluster_size)

    # Gather the nodes and set there environment
    print "## -- Setting nodes environment to {0} -- ##".format(env)
    openstack_list = rpcsqa.gather_size_nodes(os_distro,
                                              env,
                                              cluster_size)

    # If there were no nodes available, exit
    if not openstack_list:
        print "## -- Not enough availble nodes...try again later...Exiting"
        sys.exit(1)

    # Assign nodes to names
    chef_server = openstack_list[0]
    swift_management = openstack_list[1]
    swift_proxy = openstack_list[2:4]
    swift_storage = openstack_list[4:]

    # print all servers info
    print "***********************************************************"
    print "Chef Server: {0}".format(rpcsqa.print_server_info(chef_server))
    print "Management Server {0}".format(rpcsqa.print_server_info(swift_management))
    print "Swift Proxy: "
    print [rpcsqa.print_server_info(node) for node in swift_proxy]
    print "Swift Storage Nodes: "
    print [rpcsqa.print_server_info(node) for node in swift_storage]
    print "***********************************************************"

    cookbooks = [
        {
            "url": "https://github.com/rcbops-cookbooks/swift-private-cloud.git",
            "branch": "master",
            "tag": tag
        }
    ]

    swift_roles = {
        "controller": "spc-starter-controller",
        "proxy": "spc-starter-proxy",
        "storage": "spc-starter-storage"
    }

    # Get the IP of the proxy server and load it into environment
    keystone_ip = rpcsqa.get_node_ip(swift_management)
    keystone = {
        "keystone": {
            "swift_admin_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip),
            "swift_public_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip),
            "swift_internal_url": "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(keystone_ip),
            "auth_password": "secrete",
            "admin_password": "secrete"
        }
    }

    #####################################################################
    # Set up Chef Server
    #####################################################################

    print '#' * 60
    print "################## Setting up Chef Server ###################"
    print '#' * 60
    # Override the keystone attributes
    rpcsqa.set_environment_variables(env, keystone, 'swift-private-cloud', 'override')

    # Set the node to be chef server
    rpcsqa.set_node_in_use(chef_server, 'chef-server')

    # Need to prep centos boxes
    if os_distro == 'centos':
        rpcsqa.prepare_server(chef_server)

    # Remove Chef from chef_server Node
    rpcsqa.remove_chef(chef_server)

    # Build Chef Server
    rpcsqa.build_chef_server(chef_server)

    # Install Berkshelf , This is a convoluded mess, thanks ruby
    print '#' * 60
    print "################# Installing Berkshelf ######################"
    print '#' * 60
    rpcsqa.install_berkshelf(chef_server)

    # Install the proper cookbooks
    rpcsqa.install_cookbooks(chef_server, cookbooks, '/opt/rcbops')

    # Gather Chef node
    chef_node = rpcsqa.get_server_info(chef_server)

    # Drop config.json onto berkshelf to overwrite verify
    command = ('mkdir -p .berkshelf; cd .berkshelf; echo "{\\"ssl\\":{\\"verify\\":false}}" > config.json')
    run = rpcsqa.run_cmd_on_node(chef_node['node'], command)
    if not run['success']:
        rpcsqa.failed_ssh_command_exit(command, chef_node['node'], run['error'])

    # Run berkshelf on server
    commands = ['cd /opt/rcbops/swift-private-cloud',
                'source /usr/local/rvm/scripts/rvm',
                'berks install',
                'berks upload']
    command = "; ".join(commands)
    run = rpcsqa.run_cmd_on_node(chef_node['node'], command)
    if not run['success']:
        rpcsqa.failed_ssh_command_exit(command, chef_node['node'], run['error'])

    # Add remote chef credentials to local chef server
    rpcsqa.add_remote_chef_locally(chef_server, env)

    # setup environment file to remote chef server
    rpcsqa.setup_remote_chef_environment(env)

    # Setup Remote Client
    config_file = rpcsqa.setup_remote_chef_client(chef_server, env)

    #####################################################################
    # Build Swift Management (keystone)
    #####################################################################

    print '#' * 60
    print "############# Building Swift Management Node ################"
    print '#' * 60

    # Make keystone server
    rpcsqa.set_node_in_use(swift_management, swift_roles['controller'])

    # Need to prep centos boxes
    if os_distro == 'centos':
        rpcsqa.prepare_server(swift_management)

    # Remove Razor/Chef chef and bootstrap to new chef server
    rpcsqa.remove_chef(swift_management)
    rpcsqa.bootstrap_chef(swift_management, chef_server)

    # Build Swift Keystone Node
    rpcsqa.build_swift_node(swift_management,
                            swift_roles['controller'],
                            env,
                            remote=remote_chef,
                            chef_config_file=config_file)

    #####################################################################
    # Build Swift Proxy
    #####################################################################

    print '#' * 60
    print "############### Building Swift Proxy Nodes ##################"
    print '#' * 60

    for proxy in swift_proxy:
        # Make Swift Proxy Node
        rpcsqa.set_node_in_use(proxy, swift_roles['proxy'])

        # Need to prep centos boxes
        if os_distro == 'centos':
            rpcsqa.prepare_server(proxy)

        # Remove Razor/Chef and bootstrap to new chef server
        rpcsqa.remove_chef(proxy)
        rpcsqa.bootstrap_chef(proxy, chef_server)

        # Build Swift Proxy Node
        rpcsqa.build_swift_node(proxy,
                                swift_roles['proxy'],
                                env,
                                remote=remote_chef,
                                chef_config_file=config_file)

    #####################################################################
    # Build Swift Object Storage Boxes
    #####################################################################

    print '#' * 60
    print "############## Building Swift Storage Nodes #################"
    print '#' * 60

    for node in swift_storage:

        # Make Swift Proxy Node
        rpcsqa.set_node_in_use(node, swift_roles['storage'])

        # Need to prep centos boxes
        if os_distro == 'centos':
            rpcsqa.prepare_server(node)

        # Remove Razor/Chef and bootstrap to new chef server
        rpcsqa.remove_chef(node)
        rpcsqa.bootstrap_chef(node, chef_server)

        # Build Swift Proxy Node
        rpcsqa.build_swift_node(node,
                                swift_roles['storage'],
                                env,
                                remote=remote_chef,
                                chef_config_file=config_file)

    #####################################################################
    ############### Run chef on management server again #################
    #####################################################################

    print '#' * 60
    print "############### Finishing Swift Chef Setup ##################"
    print '#' * 60
    
    # Gather Chef node
    management_node = rpcsqa.get_server_info(swift_management)
    rpcsqa.run_chef_client(management_node['node'])

    #####################################################################
    ######## Setup the disks and the swift rings on the cluster #########
    #####################################################################

    # Gather the chef node objects for the proxy nodes
    proxy_nodes = []
    for proxy in swift_proxy:
        proxy_nodes.append(rpcsqa.get_server_info(proxy))

    # Gather the chef node objects for the storage nodes
    storage_nodes = []
    for storage in swift_storage:
        storage_nodes.append(rpcsqa.get_server_info(storage))

    if build_rings:
        print '#' * 60
        print "################## Building Swift Rings #####################"
        print '#' * 60
        # Build baby build (and cross fingers)
        rpcsqa.build_swift_rings(True, management_node, proxy_nodes, storage_nodes, 3)

        #####################################################################
        ####### Re-run chef client on all the boxes post ring setup #########
        #####################################################################

        print '#' * 60
        print "######### Running Chef Client on Management Node ############"
        print '#' * 60

        rpcsqa.run_chef_client(management_node['node'])

        print '#' * 60
        print "########### Running Chef Client on Proxy Nodes ##############"
        print '#' * 60
        for proxy_node in proxy_nodes:
            rpcsqa.run_chef_client(proxy_node['node'])

        print '#' * 60
        print "########## Running Chef Client on Storage Nodes #############"
        print '#' * 60
        for storage_node in storage_nodes:
            rpcsqa.run_chef_client(storage_node['node'])
    else:
        print '#' * 60
        print "## To build swift rings, please do the following ##"
        rpcsqa.build_swift_rings(False, management_node, proxy_nodes, storage_nodes, 3)

        print '#' * 60
        print "## Then run chef-client on all nodes in the following order: "
        print "## Management Node: {0}".format(rpcsqa.print_server_info(swift_management))

        for proxy in swift_proxy:
            print "## Swift Proxy Server: {0} ##".format(rpcsqa.print_server_info(proxy))

        for storage in swift_storage:
            print "## Swift Storage Server: {0} ##".format(rpcsqa.print_server_info(storage))
    
    #####################################################################
    # Successful Setup, exit
    #####################################################################

    print '#' * 60
    print "############# Swift Cluster Build Successful ###############"
    print '#' * 60

def test(name='autotest'):
    raise NotImplementedError

def teardown(name='autotest'):
    raise NotImplementedError

if __name__ == "__main__":
    parser = argh.ArghParser()
    argh.add_commands([build, test, teardown])
    parser.dispatch()
