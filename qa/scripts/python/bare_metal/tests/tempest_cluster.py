import sys
import json
import time
import argparse
import requests
from pprint import pprint
from string import Template
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
parser.add_argument('--environment_branch', action="store", dest="environment_branch",
                    required=False,
                    default="folsom")
parser.add_argument('--tempest_version', action="store",
                    dest="tempest_version", required=False,
                    default="grizzly")
parser.add_argument('--keystone_admin_pass', action="store",
                    dest="keystone_admin_pass", required=False,
                    default="ostackdemo")
results = parser.parse_args()

# Gather information of cluster
qa = rpcsqa_helper()
env = qa.cluster_environment(name=results.name, os_distro=results.os_distro,
                             feature_set=results.feature_set,
                             branch=results.environment_branch)
if not env.exists:
    print "Error: Environment %s doesn't exist" % env.name
    sys.exit(1)

controller, ip = qa.cluster_controller(env)

if not controller:
    print "Controller not found for env: %s" % env.name
    sys.exit(1)

ip = controller['ipaddress']
url = "http://%s:5000/v2.0" % ip
token_url = "%s/tokens" % url
print "##### URL: %s #####" % url
auth = {
    'auth': {
        'tenantName': 'admin',
        'passwordCredentials': {
            'username': 'admin',
            'password': '%s' % results.keystone_admin_pass
        }
    }
}

# Gather cluster information from the cluster
username = 'demo'
password = results.keystone_admin_pass
tenant = 'demo'
admin_username = 'admin'
admin_password = results.keystone_admin_pass
admin_tenant = 'admin'
cluster = {'host': ip,
           'username': username,
           'password': password,
           'tenant': tenant,
           'alt_username': username,
           'alt_password': password,
           'alt_tenant': tenant}
if results.tempest_version == 'grizzly':
    cluster['admin_username'] = admin_username
    cluster['admin_password'] = admin_password
    cluster['admin_tenant'] = admin_tenant
r = requests.post(token_url, data=json.dumps(auth),
                  headers={'Content-type': 'application/json'})
ans = json.loads(r.text)
if 'error' in ans.keys():
    print "##### Error authenticating with Keystone: #####"
    pprint(ans['error'])
    sys.exit(1)
token = ans['access']['token']['id']
images_url = "http://%s:9292/v2/images" % ip
response = requests.get(images_url, headers={'X-Auth-Token': token}).text
print response
images = json.loads(response)
image_ids = (image['id'] for image in images['images']
             if image['visibility'] == "public")
cluster['image_id'] = next(image_ids)
cluster['alt_image_id'] = next(image_ids, cluster['image_id'])
print "##### Image 1: %s #####" % cluster['image_id']
print "##### Image 2: %s #####" % cluster['alt_image_id']

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
