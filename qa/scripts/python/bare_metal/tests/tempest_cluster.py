import sys
import time
import argparse
from pprint import pprint
from string import Template
from novaclient.v1_1 import client
from subprocess import check_call, CalledProcessError
from rpcsqa_helper import rpcsqa_helper

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name",
                    required=False, default="test",
                    help="Name for the openstack chef environment")
parser.add_argument('--os_distro', action="store", dest="os_distro",
                    required=False, default='precise',
                    help="Operating System to use for openstack")
parser.add_argument('--feature_set', action="store", dest="feature_set",
                    required=False, default='default',
                    help="Openstack feature set to use")
parser.add_argument('--tempest_root', action="store", dest="tempest_root",
                    required=False,
                    default="/var/lib/jenkins/tempest")
parser.add_argument('--environment_branch', action="store",
                    dest="environment_branch",
                    required=False,
                    default="folsom")
parser.add_argument('--tempest_version', action="store",
                    dest="tempest_version", required=False,
                    default="grizzly")
parser.add_argument('--keystone_admin_pass', action="store",
                    dest="keystone_admin_pass", required=False,
                    default="ostackdemo")
results = parser.parse_args()

# Get cluster's environment
qa = rpcsqa_helper()
env_dict = {"name": results.name,
            "os_distro": results.os_distro,
            "feature_set": results.feature_set,
            "branch": results.environment_branch}
env = qa.cluster_environment(**env_dict)
if not env.exists:
    print "Error: Environment %s doesn't exist" % env.name
    sys.exit(1)
remote_chef = qa.remote_chef_api(env)
env = qa.cluster_environment(chef_api=remote_chef, **env_dict)


# Gather cluster information from the cluster
controller, ip = qa.cluster_controller(env, remote_chef)
if not controller:
    print "Controller not found for env: %s" % env.name
    sys.exit(1)
username = 'demo'
password = results.keystone_admin_pass
tenant = 'demo'
cluster = {'host': ip,
           'username': username,
           'password': password,
           'tenant': tenant,
           'alt_username': username,
           'alt_password': password,
           'alt_tenant': tenant}

if results.tempest_version == 'grizzly':
    cluster['admin_username'] = "admin"
    cluster['admin_password'] = password
    cluster['admin_tenant'] = "admin"

    # quantum is enabled, test it.
    if 'nova-quantum' in results.feature_set:
        cluster['tenant_network_cidr'] = '10.0.0.128/25'
        cluster['tenant_network_mask_bits'] = '25'
        cluster['tenant_networks_reachable'] = 'true'
        cluster['quantum_available'] = 'true'
    else:
        cluster['tenant_network_cidr'] = '10.100.0.0/16'
        cluster['tenant_network_mask_bits'] = '29'
        cluster['tenant_networks_reachable'] = 'false'
        cluster['quantum_available'] = 'false'

# Getting precise image id
url = "http://%s:5000/v2.0" % ip
print "##### URL: %s #####" % url
compute = client.Client(username,
                        password,
                        tenant,
                        url,
                        service_type="compute")
precise_id = (i.id for i in compute.images.list() if i.name == "precise-image")
cluster['image_id'] = next(precise_id)
cluster['alt_image_id'] = cluster['image_id']

pprint(cluster)

# Write the config
tempest_dir = "%s/%s/tempest" % (results.tempest_root, results.tempest_version)
sample_path = "%s/etc/base_%s.conf" % (tempest_dir, results.tempest_version)
with open(sample_path) as f:
    tempest_config = Template(f.read()).substitute(cluster)
tempest_config_path = "%s/etc/%s.conf" % (tempest_dir, env.name)
with open(tempest_config_path, 'w') as w:
    print "####### Tempest Config #######"
    print tempest_config_path
    print tempest_config
    w.write(tempest_config)

print "## Setting up and cleaning cluster ##"
setup_cmd = ("sysctl -w net.ipv4.ip_forward=1; "
             "source ~/openrc; "
             "nova-manage floating list | grep eth0 > /dev/null || nova-manage floating create 192.168.2.0/24; "
             "nova-manage floating list;")
qa.run_cmd_on_node(node=controller, cmd=setup_cmd)

# Run tests
file = '%s-%s.xunit' % (
    time.strftime("%Y-%m-%d-%H:%M:%S",
                  time.gmtime()),
    env.name)
xunit_flag = '--with-xunit --xunit-file=%s' % file
command = ("cd %s; git pull; cd -; "
           "export TEMPEST_CONFIG=%s; "
           "python -u /usr/local/bin/nosetests %s %s/tempest/tests; " % (
               tempest_dir,
               tempest_config_path,
               xunit_flag,
               tempest_dir))
try:
    print "!! ## -- Running tempest -- ## !!"
    print command
    check_call_return = check_call(command, shell=True)
    print "!!## -- Tempest tests ran successfully  -- ##!!"
except CalledProcessError, cpe:
    print "!!## -- Tempest tests failed -- ##!!"
    print "!!## -- Return Code: %s -- ##!!" % cpe.returncode
    print "!!## -- Output: %s -- ##!!" % cpe.output
