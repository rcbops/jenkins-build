import sys
import json
import argparse
import requests
from pprint import pprint
from string import Template
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
parser.add_argument('--tempest_version', action="store",
                    dest="tempest_version", required=False,
                    default="grizzly")
parser.add_argument('--keystone_admin_pass', action="store",
                    dest="keystone_admin_pass", required=False,
                    default="ostackdemo")
parser.add_argument('-xunit', action="store_true",
                    dest="xunit", required=False,
                    default=False)
results = parser.parse_args()

# Gather information of cluster
qa = rpcsqa_helper()
env = qa.cluster_environment(results.name, results.os_distro,
                             results.feature_set)
if not env.exists:
    print "Error: Environment %s doesn't exist" % env
    sys.exit(1)
controller = qa.cluster_controller(env)
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
username = 'admin'
password = results.keystone_admin_pass
tenant = 'admin'
cluster = {'host': ip,
           'username': username,
           'password': password,
           'tenant': tenant,
           'alt_username': username,
           'alt_password': password,
           'alt_tenant': tenant}
if results.tempest_version == 'grizzly':
    cluster['admin_username'] = username
    cluster['admin_password'] = password
    cluster['admin_tenant'] = tenant
try:
    r = requests.post(token_url, data=json.dumps(auth),
                      headers={'Content-type': 'application/json'})
    ans = json.loads(r.text)
    if 'error' in ans.keys():
        print "##### Error authenticating with Keystone: #####"
        pprint(ans['error'])
        sys.exit(1)
    token = ans['access']['token']['id']
    images_url = "http://%s:9292/v2/images" % ip
    images = json.loads(requests.get(images_url,
                        headers={'X-Auth-Token': token}).text)
    image_ids = (image['id'] for image in images['images'])
    cluster['image_id'] = next(image_ids)
    cluster['alt_image_id'] = next(image_ids, cluster['image_id'])
    print "##### Image 1: %s #####" % cluster['image_id']
    print "##### Image 2: %s #####" % cluster['alt_image_id']
except Exception, e:
    print "Failed to add keystone info. Exception: %s" % e
    sys.exit(1)

# Write the config
tempest_dir = "%s/%s/tempest" % (results.tempest_root, results.tempest_version)
sample_path = "%s/etc/base_%s.conf" % (tempest_dir, results.tempest_version)
with open(sample_path) as f:
    tempest_config = Template(f.read()).substitute(cluster)
tempest_config_path = "%s/etc/%s-%s.conf" % (tempest_dir, results.name,
                                             results.os)
with open(tempest_config_path, 'w') as w:
    print "####### Tempest Config #######"
    print tempest_config_path
    print tempest_config
    w.write(tempest_config)



# Do this in jenkins

# xunit = ' '
# if results.xunit:
#     file = '%s-%s-%s.xunit' % (
#         time.strftime("%Y-%m-%d-%H:%M:%S",
#                       time.gmtime()),
#         results.name,
#         results.os)
#     xunit = ' --with-xunit --xunit-file=%s ' % file
# command = ("export TEMPEST_CONFIG=%s; "
#            "python -u /usr/local/bin/nosetests%s%s/tempest/tests" % (
#                tempest_config_path,
#                xunit,
#                tempest_dir))

# # Run tests
# try:
#     print "!! ## -- Running tempest -- ## !!"
#     print command
#     check_call_return = check_call(command, shell=True)
#     print "!!## -- Tempest tests ran successfully  -- ##!!"
# except CalledProcessError, cpe:
#     print "!!## -- Tempest tests failed -- ##!!"
#     print "!!## -- Return Code: %s -- ##!!" % cpe.returncode
#     print "!!## -- Output: %s -- ##!!" % cpe.output
#     sys.exit(1)
