import argparse
import sys
from pprint import pprint
from rpcsqa_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name",
                    required=False, default="test",
                    help="Name for the chef environment")
parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False,
                    help="Name of the feature set")
parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='ubuntu',
                    help="Operating System to use")
results = parser.parse_args()

rpcsqa = rpcsqa_helper()
branch = "folsom"

env = rpcsqa.cluster_environment(name=results.name, os_distro=results.os_distro,
                                 branch=branch, feature_set=results.feature_set)
if not env.exists:
    print "Error: Environment %s doesn't exist" % env.name
    sys.exit(1)
chef_config = "/var/lib/jenkins/rcbops-qa/remote-chef-clients/%s/.chef/knife.rb" % env.name
print chef_config
remote_chef = ChefAPI.from_config_file(chef_config)
pprint(vars(remote_chef))

print "##### Updating %s to Grizzly #####" % env.name

print "Uploading grizzly cookbooks and roles to chef server"
query = "chef_environment:%s AND run_list:*network-interfaces*" % env.name
search = rpcsqa.node_search(query=query)
chef_server = next(search)
commands = ["git clone https://github.com/rcbops/chef-cookbooks -b grizzly --recursive",
            "knife cookbook upload --all -o chef-cookbooks/cookbooks; knife cookbook upload --all -o chef-cookbooks/cookbooks",
            "knife role from file chef-cookbooks/roles/*rb"]
for command in commands:
    rpcsqa.run_cmd_on_node(node=chef_server, cmd=command)

print "Editing environment to run package upgrades"
environment = Environment(env.name, api=remote_chef)
environment.override_attributes['osops']['do_package_upgrades'] = True
environment.override_attributes['glance']['image_upload'] = False
environment.save()
pprint(vars(Environment(env.name, api=remote_chef)))

print "Running chef client on all controller nodes"
query = "chef_environment:%s AND run_list:*controller*" % env.name
controllers = (Node(i) for i in Node.list(api=remote_chef).names)
command = "glance-manage db_sync"
for node in controllers:
        rpcsqa.run_chef_client(node)
        rpcsqa.run_cmd_on_node(node=node, cmd=command)

print "Running chef client on all compute nodes"
query = "chef_environment:%s AND NOT run_list:*controller*" % env.name
computes = (Node(i) for i in Node.list(api=remote_chef).names)
for node in computes:
        rpcsqa.run_chef_client(node)
