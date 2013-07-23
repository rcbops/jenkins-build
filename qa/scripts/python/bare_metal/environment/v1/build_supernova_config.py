#!/usr/bin/python
import os
import sys
import json
import argparse
from chef import *
from subprocess import check_call, CalledProcessError

# Parse the cmd line args
parser = argparse.ArgumentParser()

parser.add_argument('--role', action="store", dest="role", default="qa-single-controller", required=True, help="Chef role to set variables for.")

parser.add_argument('--username', action="store", dest="username", default="admin", required=True, help="Username to authenticate with OpenStack.")

parser.add_argument('--tenant', action="store", dest="tenant", default="demo", required=True, help="Tenant to authenticate with OpenStack.")

parser.add_argument('--chef_url', action="store", dest="chef_url", default="http://198.101.133.4:4000", required=False, help="client for chef")

parser.add_argument('--chef_client', action="store", dest="chef_client", default="jenkins", required=False, help="client for chef")

parser.add_argument('--chef_client_pem', action="store", dest="chef_client_pem", default="/var/lib/jenkins/rpcsqa/.chef/jenkins.pem",
                    required=False, help="client pem for chef")

parser.add_argument('--display_only', action="store", dest="display_only", default="true", required=False, 
                    help="Display the node information only (will not reboot or teardown am)")

# Save the parsed arguments
results = parser.parse_args()

# converting string display only into boolean
if results.display_only == 'true':
    display_only = True
else:
    display_only = False

#############################################################
#Collect nodes that match role from given input
#############################################################

role = results.role
username = results.username
environments = {}

print "!!## -- Attempting to build supernova conf for role %s -- ##!!" % results.role
print "!!## -- Display only: %s -- ##!!" % results.display_only

with ChefAPI(results.chef_url, results.chef_client_pem, results.chef_client):
    print "!!## -- Searching for node of role: %s -- ##!!" % role
    nodes = Search('node').query("role:%s" % role)
    for node in nodes:
        
        # # DEBUG
        
        # print json.dumps(node)
        env_name = node['chef_environment']
        print "!!## -- Saving environment for environment: %s -- ##!!" % env_name
        
        # Create nested dictionary for chef role
        environments[env_name] = {}
        
        # Save ip address of node
        environments[env_name]['OS_AUTH_URL'] = "http://" + node['automatic']['ipaddress'] + ":5000/v2.0/"

        # Obtain environment of node
        chef_environment = Environment(env_name).to_dict()
        
        # Check if username is in environment
        if username not in chef_environment['override_attributes']['keystone']['users']:
            print "!!## -- Error: username %s not in environment -- ##!!" % username
            sys.exit(1)
        environments[env_name]['OS_USERNAME'] = username
        
        # Save password of node
        environments[env_name]['OS_PASSWORD'] = chef_environment['override_attributes']['keystone']['users']["%s" % username]['password']
        
        # Save tenant of user exists in tenants
        if tenant in chef_environment['override_attributes']['keystone']['tenants']:
            environments[env_name]['OS_TENANT_NAME'] = tenant
        else:
            print "Tenant does not exist for %s" % tenant
            sys.exit(1)

    print "!!## -- Saved environment information for nodes: %s -- ##!!" % environments

if not display_only and environments:
    print "!!## -- Trying to write environments to /var/lib/jenkins/.supernova -- ##!!"
    # open and write .supernova based off of environments dict.
    try:
        # Open the file
        fo = open("/var/lib/jenkins/.supernova", "w")
    except IOError:
        print "!!## -- Failed to open file /var/lib/jenkins/.supernova  -- ##!!"
    else:
        for k, v in environments.iteritems():
            to_write = "[%s]\n" % k
            for k2, v2 in v.iteritems():
                to_write = to_write + "%s = %s\n" % (k2,v2)
            fo.write(to_write)
        fo.close()
        print "!!## -- /var/lib/jenkins/.supernova successfully saved -- ##!!"
