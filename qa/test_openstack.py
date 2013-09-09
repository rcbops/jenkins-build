import sys
import time
import argparse
from chef import Environment
from modules.rpcsqa_helper import rpcsqa_helper

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--env', action="store", dest="environment",
                    required=False,
                    default="autotest-precise-grizzly-openldap",
                    help="Name for the openstack chef environment")
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

parser.add_argument('--log_level', action="store", dest="log_level",
                    default="error", required=False,
                    help="Log level for chef client runs.")

args = parser.parse_args()

qa = rpcsqa_helper(razor_ip=args.razor_ip)


def disable_controller(node):
    iface = "eth0" if "precise" in node.name else "em1"
    command = ("ifdown {0}".format(iface))
    qa.run_cmd_on_node(node=node, cmd=command, private=True)


def enable_controller(node):
    iface = "eth0" if "precise" in node.name else "em1"
    command = ("ifup {0}".format(iface))
    qa.run_cmd_on_node(node=node, cmd=command, private=True)


def test(node, env):
    xunit_file = '%s-%s.xunit' % (time.strftime("%Y-%m-%d-%H:%M:%S",
                                                time.gmtime()),
                                  env)
    xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file
    commands = ["cd /opt/tempest",
                "python tools/install_venv.py",
                ("tools/with_venv.sh nosetests "
                 "--attr=type=smoke %s") % xunit_flag]
    qa.run_command_on_node(node, "; ".join(commands))
    qa.scp_from_node(node=controller, path=xunit_file, destination=".")


env = Environment(args.environment)
if 'remote_chef' in env.override_attributes:
    api = qa.remote_chef_client(env)
else:
    api = qa.chef

query = ("chef_environment:{0} AND "
         "run_list:*ha-controller*").format(args.environment)
controllers = list(qa.node_search(query, api=api))
if not controllers:
    print "No controllers in environment"
    sys.exit(1)

disabled_controller = None
for controller in controllers:
    print controller.run_list
    if 'recipe[tempest]' not in controller.run_list:
        print "Adding tempest to controller run_list"
        controller.run_list.append('recipe[tempest]')
        controller.save()
        print "Running chef-client"
    chef_client = qa.run_chef_client(controller, num_times=2,
                                     log_level=args.log_level)

test(controllers[0], args.environment)

if controllers > 1:
    for i, controller in enumerate(controllers):
        disable_controller(controller)
        time.sleep(180)
        test(controller[0], args.environment)
        enable_controller(controller)
