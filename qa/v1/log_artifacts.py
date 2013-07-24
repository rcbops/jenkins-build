import sys
import argparse
from modules.rpcsqa_helper import rpcsqa_helper
from modules.server_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False,
                    default="test",
                    help="Name for the Open Stack chef environment")

parser.add_argument('--branch', action="store", dest="branch", required=False,
                    default="folsom",
                    help="The OpenStack Distribution (i.e. folsom, grizzly")

parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False, default="glance-cf",
                    help="Feature_set for the Open Stack chef environment")

parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='precise',
                    help="Operating System Distribution to build OpenStack on")
results = parser.parse_args()

# Get nodes
qa = rpcsqa_helper()
env_dict = {"name": results.name,
            "os_distro": results.os_distro,
            "feature_set": results.feature_set,
            "branch": results.branch}
local_env = qa.cluster_environment(**env_dict)
if not local_env.exists:
    print "Error: Environment %s doesn't exist" % local_env.name
    sys.exit(1)
query = "chef_environment:%s" % local_env.name
nodes = qa.node_search(query)

# Files to archive
var_path = "var/log/"
etc_path = "etc/"
misc_path = "misc/"

archive = ((("apache2", "apt", "cinder", "daemon.log", "dist_upgrade", "dmesg",
             "glance", "keystone", "monit.log", "mysql", "mysql.err",
             "mysql.log", "nova", "rabbitmq", "rsyslog", "syslog", "quantum",
             "upstart"),
            var_path),
           (("apache2", "apt", "chef", "cinder", "collectd", "dhcp", "dpkg",
             "glance", "host.conf", "hostname", "hosts", "init", "init.d",
             "keystone", "ldap", "monit", "mysql", "network", "nova",
             "openstack-dashboard", "rabbitmq", "rsyslog.conf", "rsyslog.d",
             "sysctl.conf", "sysctl.d", "quantum", "ufw"),
            etc_path))

# Create misc folder and save platform stuff

networking = ["iptables-save", "ip a", "netstat -nt", "route",
              "brctl show", "ovs-vsctl show"]
processes = ["ps auxwww"]

if results.os_distro == 'precise':
    packages = ["dpkg -l"]
else:
    packages = ["rpm -qa"]

# Run commands to acquire artifacts
roles = {}
log_path = "logs"
# run_cmd("rm -rf %s; mkdir -p %s" % (log_path, log_path))
run_cmd("rm *.tar")
for node in nodes:
    role = node.attributes['in_use']
    if role in roles:
        roles[role] = roles[role] + 1
    else:
        roles[role] = 1
    node_name = "%s%s" % (role, roles[role])

    prepare_cmd = "; ".join("rm -rf {0}/{1}; mkdir -p {0}/{1}".format(node_name, path)
                            for path in (var_path, etc_path, misc_path))

    cp_format = "[ -e /{1}{0} ] && cp -r /{1}{0} %s/{1}{0}" % node_name
    archive_cmd = '; '.join(cp_format.format(f, path)
                            for x, path in archive
                            for f in x)

    network_cmd = "; ".join("%s >> %s/%s%s.txt" % (
        command, node_name, misc_path, 'networking')
        for command in networking)

    processes_cmd = "; ".join("%s >> %s/%s%s.txt" % (
        command, node_name, misc_path, 'processes')
        for command in processes)

    packages_cmd = "; ".join("%s >> %s/%s%s.txt" % (
        command, node_name, misc_path, 'packages')
        for command in packages)

    chef_cmd = "echo 'Not a Chef Server'"
    if 'chef' in role:
        chef_cmd = ('for i in `knife node list`;'
                    'do knife node show $i -l >> {0}/{1}/$i.knife;'
                    'done'.format(node_name, misc_path))

    tar_cmd = "tar -czf %s.tar %s" % (node_name, node_name)

    # Run all the commands at once.  SSH takes eternities
    cmd = '; '.join((prepare_cmd, archive_cmd, network_cmd,
                     processes_cmd, packages_cmd, chef_cmd,
                     tar_cmd))

    qa.run_cmd_on_node(node, cmd)

    qa.scp_from_node(node, path="%s.tar" % node_name, destination=".")

    # # transfer artifacts
    # qa.scp_from_node(node, path="%s.tar" % node_name, destination="./%s/" % log_path)

    # # extract artifacts
    # run_cmd("cd {1}; tar -xf {0}.tar; rm {0}.tar".format(node_name, log_path))
