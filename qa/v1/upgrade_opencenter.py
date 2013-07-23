#!/usr/bin/python
import os
import sys
import argparse
from chef import *
from razor_api import razor_api
from subprocess import check_call, CalledProcessError

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--name', action="store", dest="name", required=False, default="test", 
                    help="This will be the name for the opencenter chef environment")

parser.add_argument('--os', action="store", dest="os", required=False, default='ubuntu', 
                    help="Operating System to use for opencenter")

parser.add_argument('--repo_url', action="store", dest="repo", required=False, 
                    default="http://build.monkeypuppetlabs.com/proposed-packages/rcb-utils", 
                    help="URL of the OpenCenter package repo")

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip", default="198.101.133.3",
                    help="IP for the Razor server")
parser.add_argument('--chef_url', action="store", dest="chef_url", default="http://198.101.133.3:4000", required=False, 
                    help="URL of the chef server")
parser.add_argument('--chef_client', action="store", dest="chef_client", default="jenkins", required=False, 
                    help="client for chef")
parser.add_argument('--chef_client_pem', action="store", dest="chef_client_pem", default="~/.chef/jenkins.pem", required=False, 
                    help="client pem for chef")

# Save the parsed arguments
results = parser.parse_args()
results.chef_client_pem = results.chef_client_pem.replace('~',os.getenv("HOME"))

def run_remote_ssh_cmd(server_ip, user, passwd, remote_cmd):
    command = "sshpass -p %s ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet -l %s %s \"%s\"" % (passwd, user, server_ip, remote_cmd)
    try:
        ret = check_call(command, shell=True)
        return {'success': True, 'return': ret, 'exception': None}
    except CalledProcessError, cpe:
        return {'success': False, 'return': None, 'exception': cpe, 'command': command}

"""
Find opencenter agents and update their repos
"""
with ChefAPI(results.chef_url, results.chef_client_pem, results.chef_client):
    razor = razor_api(results.razor_ip)
    env = "%s-%s-opencenter" % (results.name, results.os)
    nodes = Search('node').query("name:qa-%s-pool* AND chef_environment:%s" % (results.os, env))
    

    # Use the correct command to upgrade packages
    if results.os == "ubuntu":  # Ubuntu upgrade
        package = "deb %s precise rcb-utils" % results.repo
        commands = ["sed -i 's/\(.*\)/#\1/g' /etc/apt/sources.list.d/rcb-utils.list",
                    "echo '%s' >> /etc/apt/sources.list.d/rcb-utils.list" % package,
                    "apt-get update -q",
                    "apt-get upgrade -y -q"]
    else:                       
        commands = ["if [ -e /etc/yum.repos.d/rcb-utils.repo ]; then mv /etc/yum.repos.d/rcb-utils.repo /etc/yum.repos.d/rcb-utils.repo.old; fi",
"""echo '[rcb-utils-test]
name=RCB Utility packages for OpenCenter CentOS
baseurl=http://build.monkeypuppetlabs.com/repo-testing/RedHat/6/\$basearch/
enabled=1
gpgcheck=1
gpgkey=http://build.monkeypuppetlabs.com/repo-testing/RPM-GPG-RCB.key' > /etc/yum.repos.d/rcb-utils-test.repo""",
                    "rpm --import http://build.monkeypuppetlabs.com/repo-testing/RPM-GPG-RCB.key",
                    """for service in `initctl list | grep opencenter | awk '{print $1}'`; do initctl restart $service; done"""]
    
    # Run the commands to change packages on each node
    for n in nodes:
        node = Node(n['name'])
        password = razor.get_active_model_pass(node.attributes['razor_metadata']['razor_active_model_uuid'])['password']
        for command in commands: 
            print "!!## -- Running command: %s\n On server: %s for environment: %s -- ##!!" % (command, node['ipaddress'], env)
            run_remote_ssh_cmd(node['ipaddress'], 'root', password, command)
