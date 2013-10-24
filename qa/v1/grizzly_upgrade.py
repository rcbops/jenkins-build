import argparse
from pprint import pprint
from modules.rpcsqa_helper import *

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name",
                    required=False, default="test",
                    help="Name for the chef environment")
parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False,
                    help="Name of the feature set")
parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='precise',
                    help="Operating System to use")
parser.add_argument('--old_branch', action="store",
                    dest="old_branch", required=False, default="grizzly",
                    help="Use this to upgrade to a specific branch.")
parser.add_argument('--upgrade_branch', action="store",
                    dest="upgrade_branch", required=False, default="v4.1.3rc",
                    help="Use this to upgrade to a specific branch.")
results = parser.parse_args()

rpcsqa = rpcsqa_helper()
env = rpcsqa.cluster_environment(name=results.name,
                                 os_distro=results.os_distro,
                                 branch=results.old_branch,
                                 feature_set=results.feature_set)
remote_chef = rpcsqa.remote_chef_api(env)
pprint(vars(remote_chef))

# Upgrade Process: https://github.com/rcbops/support-tools/blob/master/grizzly-upgrade/README.md
print "##### Updating %s to Grizzly #####" % env.name

print "Uploading grizzly cookbooks and roles to chef server"
query = "chef_environment:%s AND run_list:*network-interfaces*" % env.name
search = rpcsqa.node_search(query=query)
chef_server = next(search)

upgrades = "/opt/chef-upgrades"
cookbooks = "%s/chef-cookbooks" % upgrades
commands = ["mkdir -p %s" % upgrades,
            "git clone https://github.com/rcbops/chef-cookbooks %s " % cookbooks,
            "cd %s; git checkout %s" % (cookbooks, results.upgrade_branch),
            "cd %s; git submodule init" % cookbooks,
            "cd %s; git submodule sync" % cookbooks,
            "cd %s; git submodule update" % cookbooks,
            "knife cookbook upload -a -o %s/cookbooks" % cookbooks,
            "knife cookbook upload -a -o %s/cookbooks" % cookbooks,
            # "knife cookbook upload -a -o %s/cookbooks; knife cookbook upload --a -o %s/cookbooks" % cookbooks,
            "knife role from file %s/roles/*rb" % cookbooks]
for command in commands:
    rpcsqa.run_cmd_on_node(node=chef_server, cmd=command)

print "Editing environment to run package upgrades"
if results.os_distro == "centos":
    bridge_dev = "em1"
else:
    bridge_dev = "eth1"

new_networks = {"public": {
    "bridge": "br0",
    "label": "public",
    "dns1": "8.8.8.8",
    "dns2": "8.8.4.4",
    "bridge_dev": bridge_dev,
    "network_size": "254",
    "ipv4_cidr": "172.31.0.0/24"
}}

environment = Environment(env.name, api=remote_chef)
if results.upgrade_branch not in ["folsom", "v3.1.0", "v4.0.0"]:
    print "upgrading to new network schema"
    environment.override_attributes['nova']['networks'] = new_networks

environment.override_attributes['osops']['do_package_upgrades'] = True
environment.override_attributes['glance']['image_upload'] = False
environment.save()
pprint(vars(Environment(env.name, api=remote_chef)))

if 'vips' in environment.override_attributes:
    print "HA Environment: stopping controller2 services"
    if results.os_distro == 'precise':
        ctrl2_command = ("for i in {monit,keystone,nova-api-ec2,"
                         "nova-api-os-compute,nova-cert,nova-consoleauth,"
                         "nova-novncproxy,nova-scheduler,glance-api,"
                         "glance-registry,cinder-api,cinder-scheduler,keepalived,"
                         "haproxy}; do service $i stop; done")
    if results.os_distro == 'centos':
        ctrl2_command = ("for i in {monit,openstack-keystone,openstack-nova-api-ec2,"
                         "openstack-nova-api-os-compute,openstack-nova-cert,openstack-nova-consoleauth,"
                         "openstack-nova-novncproxy,openstack-nova-scheduler,openstack-glance-api,"
                         "openstack-glance-registry,openstack-cinder-api,openstack-cinder-scheduler,keepalived,"
                         "haproxy}; do service $i stop; done")
    query = "run_list:*ha-controller2*"
    controller2 = next(rpcsqa.node_search(query=query, api=remote_chef))
    rpcsqa.run_cmd_on_node(node=controller2, cmd=ctrl2_command)

    query = "run_list:*ha-controller1*"
    controller1 = next(rpcsqa.node_search(query=query, api=remote_chef))

    print "HA Environment: Running chef client on controller1"
    rpcsqa.run_chef_client(controller1)
    print "HA Environment: Running chef client on controller2"
    rpcsqa.run_chef_client(controller2)

else:
    print "Running chef client on controller node"
    query = "chef_environment:%s AND run_list:*controller*" % env.name
    controller = next(rpcsqa.node_search(query=query, api=remote_chef))
    rpcsqa.run_chef_client(controller)

print "Running chef client on all compute nodes"
query = "chef_environment:%s AND NOT run_list:*controller*" % env.name
computes = rpcsqa.node_search(query=query, api=remote_chef)
for compute in computes:
        rpcsqa.run_chef_client(compute)
