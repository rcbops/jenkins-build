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
                    help="Name of the featur set")
parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='ubuntu',
                    help="Operating System to use")
parser.add_argument('--url', action="store", dest="url",
                    required=False,
                    default='deb http://ubuntu-cloud.archive.canonical.com/ubuntu precise-updates/grizzly main',
                    help="Update Resource url")
parser.add_argument('--file', action="store", dest="file", required=False,
                    default="/etc/apt/sources.list.d/grizzly.list",
                    help="File to place new resource")
results = parser.parse_args()


print "##### Updating to Grizzly #####"
apt_source = "%s" % results.url
apt_file = results.file

if results.os_distro == "precise":
    print "##### Placing: #####\n"
    print "#####   %s #####" % apt_source
    print "##### In: #####"
    print "#####   %s #####" % apt_file
    commands = ["echo %s > %s" % (apt_source, apt_file),
                'apt-get update',
                'sudo DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade']
else:
    print "##### Placing centos repo in: /etc/yum.repos.d/epel-openstack-grizzly.repo #####"
    commands = ['yum install wget -y',
                'yum upgrade -y',
                'wget http://repos.fedorapeople.org/repos/openstack/openstack-grizzly/epel-openstack-grizzly.repo -O /etc/yum.repos.d/epel-openstack-grizzly.repo',
                'cat /etc/yum.repos.d/epel-openstack-grizzly.repo',
                "if [[ ! `rpm -V openstack-nova-volume` ]]; then rpm -e openstack-nova-volume --nodeps; fi",
                'yum upgrade -y']
rpcsqa = rpcsqa_helper()
# Make sure environment exists
env = "%s-%s-%s" % (results.name, results.os_distro, results.feature_set)
if not rpcsqa.environment_exists(env):
    print "environment %s not found" % env
    sys.exit(1)
query = "chef_environment:%s" % env
nodes = rpcsqa.node_search(query=query)
for node in nodes:
    print "##### Grizzifying: %s #####" % node.name
    for command in commands:
        rpcsqa.run_cmd_on_node(node=node, cmd=command)
environment = Environment(env)
environment.override_attributes['package_component'] = "grizzly"
environment.save()
for node in nodes:
    rpcsqa.run_chef_client(node)
