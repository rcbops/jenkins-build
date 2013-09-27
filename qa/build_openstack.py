#! /usr/bin/env python
import argparse
from modules.rpcsqa_helper import *
from modules.Builds import ChefBuild, ChefDeploymentBuild, Builds


def main():
    print "Starting up..."
    # Parse arguments from the cmd line
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', action="store", dest="name", required=False,
			default="autotest",
			help="Name for the Open Stack chef environment")

    parser.add_argument('--vm', action="store_true", dest="vm",
			required=False, default=False,
			help="Use libvirt to test instead of physical??")

    parser.add_argument('--public_cloud', action="store_true",
			dest="public_cloud", required=False, default=False,
			help="Use public cloud to test instead of physical??")

    parser.add_argument('--baremetal', action="store_true", dest="baremetal",
			required=False, default=True,
			help="Test using baremetal")

    parser.add_argument('--destroy', action="store_true", dest="destroy",
			required=False, default=False,
			help="Destroy and only destroy the openstack build?")

    parser.add_argument('--os_distro', action="store", dest="os_distro",
			required=False, default='precise',
			help="Operating System Distribution")

    parser.add_argument('--branch', action="store", dest="branch",
			required=False, default="grizzly",
			help="The rcbops cookbook branch")

    parser.add_argument('--computes', action="store", dest="computes",
			required=False, default=1,
			help="Number of computes.")

    parser.add_argument('--ha', action='store_true', dest='ha',
			required=False, default=False,
			help="Do you want to HA this environment?")

    parser.add_argument('--neutron', action='store_true', dest='neutron',
			required=False, default=False,
			help="Do you want neutron networking")

    parser.add_argument('--glance', action='store_true', dest='glance',
			required=False, default=False,
			help="Do you want glance in cloudfiles")

    parser.add_argument('--openldap', action='store_true', dest='openldap',
			required=False, default=False,
			help="Do you want openldap keystone?")

    parser.add_argument('--remote_chef', action="store_true",
			dest="remote_chef", required=False, default=False,
			help="Build a new chef server for this deploy")

    parser.add_argument('--log_level', action="store", dest="log_level",
			default="info", required=False,
			help="Log level for chef client runs.")

    #Testing
    parser.add_argument('--tempest', action="store_true", dest="tempest",
			required=False, default=False,
			help="Run tempest after installing openstack?")

    #Defaulted arguments
    parser.add_argument('--razor_ip', action="store", dest="razor_ip",
			default="198.101.133.3",
			help="IP for the Razor server")

    # Save the parsed arguments
    args = parser.parse_args()
    feature_list = ['openldap', 'neutron', 'ha', 'glance']
    features = [x for x in feature_list if args.__dict__[x] is True]
    if features == []:
	features = ['default']
    computes = int(args.computes)

    branch = "grizzly"
    if args.branch in ["4.1.1", "4.1.0"]:
	branch = "folsom"

    # Setup the helper class ( Chef )
    qa = rpcsqa_helper()

    cookbooks = [
	{
	    "url": "https://github.com/rcbops/chef-cookbooks.git",
	    "branch": args.branch
	}
    ]

    #Prepare environment
    env = qa.prepare_environment(args.name,
				 args.os_distro,
				 branch,
				 features,
				 args.branch)
    print json.dumps(Environment(env).override_attributes, indent=4)

    #####################
    #   GATHER NODES
    #####################
    if args.vm:
	print "VM's not yet supported..."
	sys.exit(1)

    if args.public_cloud:
	print "Public cloud not yet supported...."
	sys.exit(1)

    if args.baremetal:
	qa.enable_razor(args.razor_ip)
	print "Starting baremetal...."
	print "Removing broker fails"
	qa.remove_broker_fail("qa-%s-pool" % args.os_distro)
	print "Interfacing nodes that need it"
	qa.interface_physical_nodes(args.os_distro)
	try:
	    print "Cleaning up old environment (deleting nodes) "
	    # Clean up the current running environment (delete old servers)
	    qa.cleanup_environment(env)
	except Exception, e:
	    print e
	    qa.cleanup_environment(env)
	    sys.exit(1)


    #####################
    #   BUILD
    #####################

	# These builds would be nice as a class
	print "Building"
	build = ChefDeploymentBuild(env, is_remote=args.remote_chef)
	try:
	    if args.openldap:
		node = qa.get_razor_node(args.os_distro, env)
		post_commands = ['ldapadd -x -D "cn=admin,dc=rcb,dc=me" -wostackdemo -f /root/base.ldif',
				 {'function': "update_openldap_environment", 'kwargs': {'env': env}}]
		build.append(ChefBuild(node.name, 'openldap', qa, env, post_commands=post_commands))

	    if args.remote_chef:
		node = qa.get_razor_node(args.os_distro, env)
		post_commands = [{'function': build_chef_server,
				  'kwargs': {'cookbooks': cookbooks, 'env': env}}]
		build.append(ChefBuild(node.name, 'chef_server', qa, env, post_commands=post_commands))

	    if args.neutron:
		node = qa.get_razor_node(args.os_distro, env)
		build.append(ChefBuild(node.name, 'neutron', qa, env, post_commands=post_commands))

	    if args.ha:
		pre_commands = [{'function': prepare_cinder, 'kwargs': {'node': node, 'api': api}}]
		node = qa.get_razor_node(args.os_distro, env)
		build.append(ChefBuild(node.name, 'ha_controller1', qa, env, pre_commands=pre_commands))

		node = qa.get_razor_node(args.os_distro, env)
		build.append(ChefBuild(node.name, 'ha_controller2', qa, env))

	    else:
		pre_commands = [{'function': prepare_cinder, 'kwargs': {'node': node, 'api': api}}]
		node = qa.get_razor_node(args.os_distro, env)
		build.append(ChefBuild(node.name, Builds, qa, env, pre_commands=pre_commands))

	    for n in xrange(computes):
		node = qa.get_razor_node(args.os_distro, env)
		build.append(ChefBuild(node.name, Builds.single_controller, qa, env))

	except IndexError, e:
	    print "*** Error: Not enough nodes for your setup"
	    qa.cleanup_environment(env)
	    qa.delete_environment(env)
	    sys.exit(1)

	print "#" * 70
	success = True

	try:
	    build.build()
	except Exception, e:
	    print traceback.print_exc()
	    sys.exit(1)

    if success:
	print "Welcome to the cloud..."
	print env
    else:
	print "Sorry....no cloud for you...."

    if args.destroy:
	print "Destroying your cloud now!!!"
	qa.cleanup_environment(env)
	qa.delete_environment(env)

    print "DONE!"

if __name__ == "__main__":
    main()
