from subprocess import check_call, CalledProcessError
import argparse
import sys
import os
from chef import ChefAPI, Search, Node
from opencenterclient.client import OpenCenterEndpoint
from razor_api import razor_api

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name",
                    required=False, default="test",
                    help="Name for the opencenter chef environment")
parser.add_argument('--os', action="store", dest="os", required=False,
                    default='ubuntu',
                    help="Operating System to use for opencenter")
parser.add_argument('--url', action="store", dest="url",
                    required=False,
                    default='deb http://ubuntu-cloud.archive.canonical.com/ubuntu precise-updates/grizzly main',
                    help="Update Resource url")
parser.add_argument('--file', action="store", dest="file", required=False,
                    default="/etc/apt/sources.list.d/grizzly.list",
                    help="File to place new resource")

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")
parser.add_argument('--chef_url', action="store", dest="chef_url",
                    default="https://198.101.133.3:443", required=False,
                    help="client for chef")
parser.add_argument('--chef_client', action="store", dest="chef_client",
                    default="jenkins", required=False, help="client for chef")
parser.add_argument('--chef_client_pem', action="store",
                    dest="chef_client_pem",
                    default="%s/.chef/jenkins.pem" % os.getenv("HOME"),
                    required=False, help="client pem for chef")
results = parser.parse_args()


def run_remote_ssh_cmd(server_ip, user, passwd, remote_cmd):
    """Runs a command over an ssh connection"""
    command = "sshpass -p %s ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet -l %s %s '%s'" % (passwd, user, server_ip, remote_cmd)
    print "##### Running command: %s #####" % remote_cmd
    try:
        ret = check_call(command, shell=True)
        return {'success': True, 'return': ret, 'exception': None}
    except CalledProcessError, cpe:
        return {'success': False,
                'retrun': None,
                'exception': cpe,
                'command': command}

print "##### Updating agents to Grizzly #####"
apt_source = "%s" % results.url
apt_file = results.file

if results.os == "ubuntu":
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

razor = razor_api(results.razor_ip)
with ChefAPI(results.chef_url, results.chef_client_pem, results.chef_client):
    # Make sure environment exists
    env = "%s-%s-opencenter" % (results.name, results.os)
    if not Search("environment").query("name:%s" % env):
        print "environment %s not found" % env
        sys.exit(1)
    query = "in_use:\"server\" AND chef_environment:%s" % env
    opencenter_server = Node(next(node['name'] for node in
                                  Search('node').query(query)))
    opencenter_server_ip = opencenter_server.attributes['ipaddress']
    ep = OpenCenterEndpoint("https://%s:8443" % opencenter_server_ip,
                            user="admin",
                            password="password")
    chef_envs = []
    infrastructure_nodes = ep.nodes.filter('name = "Infrastructure"')
    for node_id in infrastructure_nodes.keys():
        chef_env = infrastructure_nodes[node_id].facts['chef_environment']
        chef_envs.append(chef_env)
    for node in ep.nodes.filter('facts.chef_environment = "test_cluster"'):
        if 'agent' in node.facts['backends']:
            chef_node = Node(node.name)
            ipaddress = chef_node.attributes['ipaddress']
            uuid = chef_node.attributes['razor_metadata']['razor_active_model_uuid']
            password = razor.get_active_model_pass(uuid)['password']
            print "##### Grizzifying: %s - %s #####" % (node.name, ipaddress)
            for command in commands:
                run_remote_ssh_cmd(ipaddress, 'root', password, command)
            # Run chef client?
