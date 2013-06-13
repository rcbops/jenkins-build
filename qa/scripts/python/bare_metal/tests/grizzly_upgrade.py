import argparse
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
remote_chef = rpcsqa.remote_chef_api(env)
pprint(vars(remote_chef))

# Upgrade Process: https://github.com/rcbops/support-tools/blob/master/grizzly-upgrade/README.md
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

if 'vips' in environment.override_attributes:
    print "HA Environment: stopping controller2 services"
    ctrl2_command = ("for i in {monit,keystone,nova-api-ec2,"
                     "nova-api-os-compute,nova-cert,nova-consoleauth,"
                     "nova-novncproxy,nova-scheduler,glance-api,"
                     "glance-registry,cinder-api,cinder-scheduler,keepalived,"
                     "haproxy}; do service $i stop; done")
    query = "run_list:*ha-controller2*"
    controller2 = next(rpcsqa.node_search(query=query, api=remote_chef))
    rpcsqa.run_cmd_on_node(node=controller2, cmd=ctrl2_command)

    query = "run_list:*ha-controller1*"
    controller1 = next(rpcsqa.node_search(query=query, api=remote_chef))

    print "Fix for vrrp increments"
    vrrp_command = ("vrrp=`vrrps=(/etc/keepalived/conf.d/vrrp*); echo ${vrrps[-1]}`; "
                    "echo Before Fix:; cat $vrrp; "
                    "cat $vrrp | awk '/virtual_router_id/ {$2++} {print}' > $vrrp; "
                    "cat After Fix:; cat $vrrp")
    
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
