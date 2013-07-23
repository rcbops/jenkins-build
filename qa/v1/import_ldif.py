#!/usr/bin/python
import os
import json
import time
import argparse
from chef import *
from razor_api import razor_api
from subprocess import check_call, CalledProcessError

# Parse the cmd line arguments
parser = argparse.ArgumentParser()

parser.add_argument('--razor_ip', action="store", dest="razor_ip", required=True, help="IP of the Razor server.")

parser.add_argument('--policy', action="store", dest="policy", required=True, help="Razor policy.")

parser.add_argument('--role', action="store", dest="role", required=True, help="Chef role to run chef-client on")

parser.add_argument('--chef_url', action="store", dest="chef_url", default="http://198.101.133.4:4000", required=False, help="client for chef")

parser.add_argument('--chef_client', action="store", dest="chef_client", default="jenkins", required=False, help="client for chef")

parser.add_argument('--chef_client_pem', action="store", dest="chef_client_pem", default="/var/lib/jenkins/rpcsqa/.chef/jenkins.pem", required=False,                help="client pem for chef")

parser.add_argument('--display_only', action="store", dest="display_only", default="true", required=False, 
                    help="Display the node information only (will not reboot or teardown am)")

# Save the parsed arguments
results = parser.parse_args()

# converting string display only into boolean
if results.display_only == 'true':
    display_only = True
else:
    display_only = False

def get_chef_name(data):
    try:
        name = "%s%s.%s" % (data['hostname_prefix'], data['bind_number'], data['domain'])
        return name
    except Exception, e:
        return ''

def get_root_pass(data):
    if 'root_password' in data:
        return data['root_password']
    else:
        return ''

#############################################################
#Collect active models that match policy from given input
#############################################################

razor = razor_api(results.razor_ip)
policy = results.policy

print "!!## -- Attempting to import ldif for role %s -- ##!!" % results.role
print "!!## -- Display only: %s -- ##!!" % results.display_only

active_models = razor.simple_active_models(policy)
to_run_list = []

if active_models:
     # Gather all of the active models for the policy and get information about them
     for active in active_models:
          data = active_models[active]
          chef_name = get_chef_name(data)
          root_password = get_root_pass(data)

          with ChefAPI(results.chef_url, results.chef_client_pem, results.chef_client):
               node = Node(chef_name)

               if 'role[%s]' % results.role in node.run_list:
                    ip = node['ipaddress']
               
                    if display_only:
                         print "!!## -- Role %s found, would run scp ldif on %s with ip %s -- ##!!" % (results.role, node, ip)
                    else:
                         print "!!## -- Role %s found, runnning scp of ldif files on %s with ip %s -- ##!!" % (results.role, node, ip)
                         to_run_list.append({'node': node, 'ip': ip, 'root_password': root_password})

     if not display_only:
          for server in to_run_list:
               print "!!## -- Trying to import ldif on %s with ip %s...." % (server['node'], server['ip'])
               try:
                    print "!!## -- Trying to scp ldif files  -- ##!!"
                    check_call_return = subprocess.check_call("sshpass -p %s scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet  /var/lib/jenkins/source_files/ldif/*.ldif root@%s:/root" % (server['root_password'], server['ip']), shell=True)
                except CalledProcessError, cpe:
                    print "!!## -- Failed to copy ldif files  -- ##!!"
                    print "!!## -- Return Code: %s  -- ##!!" % cpe.returncode
                    #print "!!## -- Command: %s -- ##!!" % cpe.cmd
                    print "!!## -- Output: %s -- ##!!" % cpe.output
                
                try:
                    print "!!## -- Trying to import ldif files on ldap server  -- ##!!"
                    check_call_return = subprocess.check_call("sshpass -p %s ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet -l root %s 'ldapadd -x -D \"cn=admin,dc=dev,dc=rcbops,dc=me\" -f base.ldif -w@privatecloud'" % (server['root_password'], server['ip']), shell=True)
                except CalledProcessError, cpe:
                    print "!!## -- Failed to import ldif files on ldap server -- ##!!"
                    print "!!## -- Return Code: %s..." % cpe.returncode
                    #print "!!## -- Command: %s" % cpe.cmd
                    print "!!## -- Output: %s..." % cpe.output
else:
    # No active models for the policy present, exit.
    print "!!## -- Razor Policy %s has no active models -- ##!!" % results.policy
    sys.exit(1)
