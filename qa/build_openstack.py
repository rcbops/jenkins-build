#! /usr/bin/env python
import argparse
import traceback
from modules.rpcsqa_helper import *


def _run_commands(name, commands):
    print "#" * 70
    print "Running {0} chef-client commands....".format(name)
    for command in commands:
        print "Running:  %s" % command
        #If its a string run on remote server
        if isinstance(command, str):
            qa.run_command_on_node(node, command)
        if isinstance(command, dict):
            try:
                func = command['function']
                func(**command['kwargs'])
            except:
                print traceback.print_exc()

                sys.exit(1)

            #elif function run the function
        elif hasattr(command, '__call__'):
            command()
    print "#" * 70


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

    parser.add_argument('--quantum', action='store_true', dest='quantum',
                        required=False, default=False,
                        help="Do you want quantum networking")

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
    feature_list = ['openldap', 'quantum', 'ha']
    features = [x for x in feature_list if args.__dict__[x] is True]
    if features == []:
        features = ['default']
    computes = int(args.computes)

    # Setup the helper class ( Chef / Razor )
    qa = rpcsqa_helper(args.razor_ip)

    cookbooks = [
        {
            "url": "https://github.com/rcbops/chef-cookbooks.git",
            "branch": args.branch
        }
    ]

    #Prepare environment
    env = qa.prepare_environment(args.name,
                                 args.os_distro,
                                 args.branch,
                                 features)

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
        print "Starting baremetal...."
        print "Removing broker fails"
        qa.remove_broker_fail("qa-%s-pool" % args.os_distro)
        print "Interfacing nodes that need it"
        qa.interface_physical_nodes(args.os_distro)
        try:
            print "Cleaning up old enviroment (deleting nodes) "
            # Clean up the current running environment (delete old servers)
            qa.cleanup_environment(env)

            print "Gather nodes..."
            nodes = qa.gather_razor_nodes(args.os_distro, env)

        except Exception, e:
            print e
            qa.cleanup_environment(env)
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
                post_commands = [{'function': qa.build_chef_server,
                                  'kwargs': {'cookbooks': cookbooks,
                                             'env': env}}]
                build.append({'name': nodes.pop(),
                              'in_use': 'chef_server',
                              'post_commands': post_commands})

            if args.openldap:
                role = 'role[qa-openldap-%s]' % args.os_distro
                post_commands = ['ldapadd -x -D "cn=admin,dc=rcb,dc=me" -wostackdemo -f /root/base.ldif',
                                 {'function': qa.update_openldap_environment, 'kwargs': {'env': env}}]
                build.append({'name': nodes.pop(),
                              'in_use': 'directory_server',
                              'run_list': [role],
                              'post_commands': post_commands
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
                              'run_list': ['role[ha-controller1]']})

            #If no nodes left, run controller as compute
            if not nodes:
                build[-1]['run_list'] = build[-1]['run_list'] + ['role[single-compute]']

            #Compute with whatever is left
            for n in xrange(computes):
                build.append({'name': nodes.pop(),
                              'in_use': 'single-compute',
                              'run_list': ['role[single-compute]']})

        except IndexError, e:
            print "*** Error: Not enough nodes for your setup"
            qa.cleanup_environment(env)
            qa.delete_environment(env)
            sys.exit(1)

        #Build out cluster
        print "Going to build.....%s" % json.dumps(build,
                                                   indent=4,
                                                   default=lambda o: o.__name__)
        print "#" * 70
        success = True
        environment = Environment(env)
        try:
            for b in build:
                print "Building: %s" % b
                node = Node(b['name'])
                node['in_use'] = b['in_use']
                node.save()

                if args.remote_chef and not b['in_use'] is "chef_server":
                    qa.remove_chef(node)
                    query = "chef_environment:%s AND in_use:chef_server" % env
                    chef_server = next(qa.node_search(query))
                    qa.bootstrap_chef(node, chef_server)

                if 'run_list' in b:
                    # Reacquires node if using remote chef
                    node = Node(node.name,
                                # perhaps add remote chef to rpcsqa_helper
                                api=qa.remote_chef_client(environment)) if args.remote_chef else node
                    node.run_list = b['run_list']
                    node.save()
                    print "Running chef client for %s" % node
                    print node.run_list
                    chef_client = qa.run_chef_client(node,
                                                     num_times=2,
                                                     log_level=args.log_level)
                    if not chef_client['success']:
                        print "chef-client run failed"
                        success = False
                        break

                if 'post_commands' in b:
                    _run_commands("post", b['post_commands'])

        except Exception, e:
            print traceback.print_exc()
            sys.exit(1)

    if success:
        print "Welcome to the cloud..."
        print env
        print "Your cloud:   %s" % json.dumps(build,
                                              indent=4,
                                              default=lambda o: o.__name__)
        print "#" * 70
    else:
        print "Sorry....no cloud for you...."

    if args.destroy:
        print "Destroying your cloud now!!!"
        qa.cleanup_environment(env)
        qa.delete_environment(env)

    print "DONE!"

if __name__ == "__main__":
    main()
