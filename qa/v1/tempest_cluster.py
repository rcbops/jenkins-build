import sys
import argh
import time
from pprint import pprint
from string import Template
from chef import Environment
from novaclient.v1_1 import client
from modules.rpcsqa_helper import rpcsqa_helper

qa = rpcsqa_helper()


def main(name="autotest", os="precise", feature_set="glance-cf",
         environment_branch="grizzly", tempest_version="grizzly",
         keystone_admin_pass="ostackdemo", jenkins_build=None):
    local_env = qa.cluster_environment(name=name, os_distro=os,
                                       feature_set=feature_set,
                                       branch=environment_branch)
    if not local_env.exists:
        print "Error: Environment %s doesn't exist" % local_env.name
        sys.exit(1)
    if 'remote_chef' in local_env.override_attributes:
        api = qa.remote_chef_api(local_env)
        env = Environment(local_env.name, api=api)
    else:
        env = local_env
        api = qa.chef

    # Gather information from the cluster
    controller, ip = qa.cluster_controller(env, api)
    if not controller:
        print "Controller not found for env: %s" % env.name
        sys.exit(1)
    username = 'demo'
    password = keystone_admin_pass
    tenant = 'demo'

    cluster = {
        'host': ip,
        'username': username,
        'password': password,
        'tenant': tenant,
        'alt_username': username,
        'alt_password': password,
        'alt_tenant': tenant,
        'admin_username': "admin",
        'admin_password': password,
        'admin_tenant': "admin",
        'nova_password': controller.attributes['nova']['db']['password']
    }
    if tempest_version == 'grizzly':
        # quantum is enabled, test it.
        if 'nova-quantum' in feature_set:
            cluster['api_version'] = 'v2.0'
            cluster['tenant_network_cidr'] = '10.0.0.128/25'
            cluster['tenant_network_mask_bits'] = '25'
            cluster['tenant_networks_reachable'] = True
            cluster['public_router_id'] = ''
            cluster['public_network_id'] = ''
            cluster['quantum_available'] = True
        else:
            cluster['api_version'] = 'v1.1'
            cluster['tenant_network_cidr'] = '10.100.0.0/16'
            cluster['tenant_network_mask_bits'] = '29'
            cluster['tenant_networks_reachable'] = False
            cluster['public_router_id'] = ''
            cluster['public_network_id'] = ''
            cluster['quantum_available'] = False

    if feature_set == "glance-cf":
        cluster["image_enabled"] = True
    else:
        cluster["image_enabled"] = False

    # Getting precise image id
    url = "http://%s:5000/v2.0" % ip
    print "##### URL: %s #####" % url
    compute = client.Client(cluster['admin_username'],
                            cluster['admin_password'],
                            cluster['admin_tenant'],
                            url,
                            service_type="compute")
    precise_id = (i.id for i in compute.images.list() if "precise" in i.name)
    cluster['image_id'] = next(precise_id)
    cluster['alt_image_id'] = cluster['image_id']

    pprint(cluster)

    # Write the config
    jenkins_build = jenkins_build
    tempest_dir = "%s/qa/metadata/tempest/config" % jenkins_build
    sample_path = "%s/base_%s.conf" % (tempest_dir, tempest_version)
    with open(sample_path) as f:
        tempest_config = Template(f.read()).substitute(cluster)
    tempest_config_path = "/tmp/%s.conf" % env.name
    with open(tempest_config_path, 'w') as w:
        print "####### Tempest Config #######"
        print tempest_config_path
        print tempest_config
        w.write(tempest_config)
    qa.scp_to_node(node=controller, path=tempest_config_path)

    # Setup tempest on chef server
    print "## Setting up tempest on chef server ##"
    if os == "precise":
        packages = ("apt-get install python-pip python-setuptools "
                    "libmysqlclient-dev libxml2-dev libxslt1-dev "
                    "python2.7-dev libpq-dev git -y")
    else:
        packages = ("yum install python-setuptools python-setuptools-devel "
                    "python-pip python-lxml gcc python-devel openssl-devel "
                    "mysql-devel postgresql-devel git -y; easy_install pip")
    commands = [packages,
                "rm -rf tempest",
                ("git clone https://github.com/openstack/tempest.git -b "
                 "stable/%s --recursive" % tempest_version),
                "easy_install -U distribute",
                "pip install -r tempest/tools/pip-requires",
                "pip install -r tempest/tools/test-requires",
                "pip install nose-progressive"]
    for command in commands:
        qa.run_cmd_on_node(node=controller, cmd=command)

    # Setup controller
    print "## Setting up and cleaning cluster ##"
    setup_cmd = ("sysctl -w net.ipv4.ip_forward=1; "
                 "source ~/openrc; "
                 "nova-manage floating list | grep eth0 > /dev/null || "
                 "nova-manage floating create 192.168.2.0/24; "
                 "nova-manage floating list;")
    qa.run_cmd_on_node(node=controller, cmd=setup_cmd)

    # Run tests
    print "## Running Tests ##"

    file = '%s-%s.xunit' % (
        time.strftime("%Y-%m-%d-%H:%M:%S",
                      time.gmtime()),
        env.name)
    xunit_flag = '--with-xunit --xunit-file=%s' % file

    exclude_flags = ["volume", "rescue"]  # Volumes
    if feature_set != "glance-cf":
        exclude_flags.append("image")
    exclude_flag = ' '.join('-e {0}'.format(x) for x in exclude_flags)

    command = ("export TEMPEST_CONFIG_DIR=/root; "
               "export TEMPEST_CONFIG=%s.conf; "
               "python -u `which nosetests` --with-progressive %s %s "
               "-a type=smoke tempest/tempest/tests; " % (
                   env.name, xunit_flag, exclude_flag))

    # run tests
    qa.run_cmd_on_node(node=controller, cmd=command)
    qa.scp_from_node(node=controller, path=file, destination=".")

    if feature_set == "ha":
        query = "chef_environment:%s-%s-%s-ha AND in_use:*controller*" % \
                (name, os, environment_branch)
        controllers = qa.node_search(query=query)
        print query
        disabled_controller = None
        for node in controllers:
            if disabled_controller:
                enable_controller(disabled_controller)
            disable_controller(node)
            disabled_controller = node
            qa.run_cmd_on_node(node=controller, cmd=command)
            qa.scp_from_node(node=controller, path=file, destination=".")


def disable_controller(node):
    if 'precise' in node.name:
        command = ("for i in {monit,keystone,nova-api-ec2,"
                   "nova-api-os-compute,nova-cert,nova-consoleauth,"
                   "nova-novncproxy,nova-scheduler,glance-api,"
                   "glance-registry,cinder-api,cinder-scheduler,keepalived,"
                   "haproxy}; do service $i stop; done")
    if 'centos' in node.name:
        command = ("for i in {monit,openstack-keystone,openstack-nova-api-ec2,"
                   "openstack-nova-api-os-compute,openstack-nova-cert,"
                   "openstack-nova-consoleauth,openstack-nova-novncproxy,"
                   "openstack-nova-scheduler,openstack-glance-api,"
                   "openstack-glance-registry,openstack-cinder-api,"
                   "openstack-cinder-scheduler,keepalived,haproxy}; "
                   "do service $i stop; done")
    qa.run_cmd_on_node(node=node, cmd=command)


def enable_controller(node):
    if 'precise' in node.name:
        command = ("for i in {monit,keystone,nova-api-ec2,"
                   "nova-api-os-compute,nova-cert,nova-consoleauth,"
                   "nova-novncproxy,nova-scheduler,glance-api,"
                   "glance-registry,cinder-api,cinder-scheduler,keepalived,"
                   "haproxy}; do service $i start; done")
    if 'centos' in node.name:
        command = ("for i in {monit,openstack-keystone,openstack-nova-api-ec2,"
                   "openstack-nova-api-os-compute,openstack-nova-cert,"
                   "openstack-nova-consoleauth,openstack-nova-novncproxy,"
                   "openstack-nova-scheduler,openstack-glance-api,"
                   "openstack-glance-registry,openstack-cinder-api,"
                   "openstack-cinder-scheduler,keepalived,haproxy}; "
                   "do service $i start; done")
    qa.run_cmd_on_node(node=node, cmd=command)

argh.dispatch_command(main)
