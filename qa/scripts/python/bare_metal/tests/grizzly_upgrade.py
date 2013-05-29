import argparse
import sys
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

env = "%s-%s-%s-%s" % (results.name, results.os_distro, branch,
                       results.feature_set)
if not rpcsqa.environment_exists(env):
    print "environment %s not found" % env
    sys.exit(1)
chef_config = "/var/lib/jenkins/rcbops-qa/remote-chef-clients/%s/.chef/knife.rb" % env
remote_chef = ChefAPI.from_config_file(chef_config)
print "##### Updating %s to Grizzly #####" % env

print "Uploading grizzly cookbooks and roles to chef server"
query = "chef_environment:%s AND run_list:*network-interfaces*" % env
search = rpcsqa.node_search(query=query)
chef_server = next(search)
commands = ["git clone https://github.com/rcbops/chef-cookbooks -b grizzly --recursive",
            "knife cookbook upload --all -o chef-cookbooks/cookbooks; knife cookbook upload --all -o chef-cookbooks/cookbooks",
            "knife role from file chef-cookbooks/roles/*rb"]
for command in commands:
    rpcsqa.run_cmd_on_node(node=chef_server, cmd=command)

print "Editing environment to run package upgrades"
environment = Environment(env, api=remote_chef)
environment.override_attributes['osops']['do_package_upgrades'] = True
environment.override_attributes['glance']['image_upload'] = False
environment.save()

print "Running chef client on all compute nodes"
query = "chef_environment:%s AND NOT run_list:*network-interfaces*" % env
nodes = rpcsqa.node_search(query=query, api=remote_chef)
for node in nodes:
        rpcsqa.run_chef_client(node)
