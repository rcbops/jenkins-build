#!/usr/bin/python
import argparse
from modules.rpcsqa_helper import *

print "Starting up..."
# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False,
                    default="autotest",
                    help="Name for the Open Stack chef environment")

parser.add_argument('--vm', action="store_true", dest="vm",
                    required=False, default=False,
                    help="Use libvirt to test instead of physical??")

parser.add_argument('--public_cloud', action="store_true", dest="public_cloud",
                    required=False, default=False,
                    help="Use public cloud to test instead of physical??")

parser.add_argument('--baremetal', action="store_true", dest="baremetal",
                    required=False, default=True,
                    help="Test using baremetal")

parser.add_argument('--destroy', action="store_true", dest="destroy",
                    required=False, default=False,
                    help="Destroy and only destroy the openstack build?")

parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='precise',
                    help="Operating System Distribution to build OpenStack on")

parser.add_argument('--branch', action="store", dest="branch", required=False,
                    default="grizzly",
                    help="The rcbops cookbook branch")

parser.add_argument('--cluster_size', action="store", dest="cluster_size",
                    required=False, default=1,
                    help="Size of the Open Stack cluster.")

parser.add_argument('--ha', action='store_true', dest='ha',
                    required=False, default=False,
                    help="Do you want to HA this environment?")

parser.add_argument('--quantum', action='store_true', dest='quantum',
                    required=False, default=False,
                    help="Do you want quantum networking")

parser.add_argument('--openldap', action='store_true', dest='openldap',
                    required=False, default=False,
                    help="Do you want openldap keystone?")

parser.add_argument('--remote_chef', action="store_true", dest="remote_chef",
                    required=False, default=False,
                    help="Build a new chef server for this deploy")

parser.add_argument('--log_level', action="store", dest="log_level",
                    default="error", required=False,
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
feature_list = ['openldap', 'quantum', 'ha']
features = [x for x in feature_list if args.__dict__[x] is True]
if features == []:
    features = ['default']

# Setup the helper class ( Chef / Razor )
rpcsqa = rpcsqa_helper()


def _run_commands(name, commands):
    print "#" * 70
    print "Running {0} chef-client commands....".format(name)
    for command in commands:
        print "Running:  %s" % command
        #If its a string run on remote server
        if isinstance(command, str):
            rpcsqa.run_command_on_node(node, command)
        if isinstance(command, dict):
            func = command['function']
            func(**command['kwargs'])
            #elif function run the function
        elif hasattr(command, '__call__'):
            command()
    print "#" * 70

cookbooks = [
    {
        "url": "https://github.com/rcbops/chef-cookbooks.git",
        "branch": args.branch
    }
]

#Prepare environment
env = rpcsqa.prepare_environment(args.name,
                                 args.os_distro,
                                 args.branch,
                                 features)


# Set the cluster size
cluster_size = int(args.cluster_size)


nodes = None
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
    rpcsqa.enable_razor(args.razor_ip)
    print "Starting baremetal...."
    print "Removing broker fails and interfacing nodes that need it....(razor api is slow)"
    rpcsqa.remove_broker_fail("qa-%s-pool" % args.os_distro)
    rpcsqa.interface_physical_nodes(args.os_distro)
    try:
        print "Cleaning up old enviroment (deleting nodes) "
        # Clean up the current running environment (delete old servers)
        rpcsqa.cleanup_environment(env)

        print "Gather nodes..."
        nodes = rpcsqa.gather_razor_nodes(args.os_distro, env, cluster_size)

    except Exception, e:
        print e
        rpcsqa.cleanup_environment(env)
        sys.exit(1)


#####################
#   BUILD
#####################
if nodes is None:
    print "You have no nodes!"
    sys.exit(1)
else:
    # These builds would be nice as a class
    build = []
    try:

        if args.remote_chef:
            build.append({'name': nodes.pop(),
                          'in_use': 'chef_server',
                          'post_commands': [{'function': rpcsqa.build_chef_server,
                                            'kwargs': {'cookbooks': cookbooks,
                                                       'env': env}}]})

        if args.openldap:
            build.append({'name': nodes.pop(),
                          'in_use': 'directory_server',
                          'run_list': ['role[qa-openldap-%s]' % args.os_distro],
                          'post_commands': ['ldapadd -x -D "cn=admin,dc=rcb,dc=me" -wostackdemo -f /root/base.ldif',
                                            {'function': rpcsqa.update_openldap_environment, 'kwargs': {'env': env}}]
                          })

        if args.quantum:
            build.append({'name': nodes.pop(),
                          'in_use': 'quantum',
                          'run_list': ['role[single-network-node]']})

        #Controller
        if args.ha:
            build.append({'name': nodes.pop(),
                          'in_use': 'ha_controller1',
                          'run_list': ['role[ha-controller1]']})
            build.append({'name': nodes.pop(),
                          'in_use': 'ha_controller2',
                          'run_list': ['role[ha-controller2]']})
        else:
            build.append({'name': nodes.pop(),
                          'in_use': 'single-controller',
                          'run_list': ['role[single-controller]']})

        #Compute with whatever is left
        for n in nodes:
            build.append({'name': n,
                          'in_use': 'single-compute',
                          'run_list': ['role[single-compute]']})

    except IndexError, e:
        print "*** Not enough nodes for your setup (%s) ....try increasing cluster_size" % cluster_size
        rpcsqa.cleanup_environment(env)
        rpcsqa.delete_environment(env)
        sys.exit(1)

    print build
    #Build out cluster
    print "Going to build.....%s" % json.dumps(build, indent=4,  default=lambda o: o.__name__)
    print "#" * 70
    success = True

    try:
        for b in build:
            node = Node(b['name'])
            node['in_use'] = b['in_use']
            node.save()

            if 'run_list' in b:
                node = Node(node.name, api=rpcsqa.remote_chef_client(env)) if args.remote_chef else node
                node.run_list = b['run_list']
                node.save()
                print "Running chef client for %s" % node
                chef_client = rpcsqa.run_chef_client(node, num_times=2, log_level=args.log_level)
                if not chef_client['success']:
                    print "chef-client run failed"
                    success = False
                    break

            if 'post_commands' in b:
                _run_commands("post", b['post_commands'])

    except Exception, e:
        print e
        sys.exit(1)


if success:
    print "Welcome to the cloud..."
    print env
    print "Your cloud:   %s" % json.dumps(build, indent=4,  default=lambda o: o.__name__)
    print "#" * 70
else:
    print "Sorry....no cloud for you...."

if args.destroy:
    print "Destroying your cloud now!!!"
    rpcsqa.cleanup_environment(env)
    rpcsqa.delete_environment(env)

print "DONE!"
