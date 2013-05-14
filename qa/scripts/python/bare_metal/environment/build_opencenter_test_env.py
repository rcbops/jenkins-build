#!/usr/bin/python
import os
import sys
import argparse
from chef import *
from razor_api import razor_api
from ssh_session import ssh_session
from subprocess import check_call, CalledProcessError

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()

parser.add_argument('--razor_ip', action="store", dest="razor_ip", required=True, help="IP for the Razor server")

parser.add_argument('--policy', action="store", dest="policy", required=True, help="Razor policy to use.")

parser.add_argument('--opencenter_user', action="store", dest="opencenter_user", required=True, help="OpenCenter user to use with authentication.", default="admin")

parser.add_argument('--opencenter_password', action="store", dest="opencenter_password", required=True, help="OpenCenter password to use with authentication.")

parser.add_argument('--chef_url', action="store", dest="chef_url", default="http://198.101.133.4:4000", required=True, help="client for chef")

parser.add_argument('--chef_client', action="store", dest="chef_client", default="jenkins", required=True, help="client for chef")

parser.add_argument('--chef_client_pem', action="store", dest="chef_client_pem", default="/var/lib/jenkins/rpcsqa/.chef/jenkins.pem", required=True,                help="Location of chef client pem file")

parser.add_argument('--opencenter_test_repo', action="store", dest="opencenter_test_repo", 
                    default="https://github.com/galstrom21/opencenter-testerator.git", required=True, help="URL of opencenter test git repo")

parser.add_argument('--display_only', action="store", dest="display_only", default="true", required=True, 
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
active_models = razor.simple_active_models(policy)
opencenter_user = results.opencenter_user
opencenter_password = results.opencenter_password
servers = []

if active_models:
    # Gather all of the active models for the policy and get information about them.
    for active in active_models:
        data = active_models[active]
        chef_name = get_chef_name(data)
        root_password = get_root_pass(data)

        with ChefAPI(results.chef_url, results.chef_client_pem, results.chef_client):
            node = Node(chef_name)
            run_list = node.run_list
            ip = node['ipaddress']
            
            if display_only:
                print "!!## -- Found server to run tests on with ip: %s and name: %s -- ##!!" % (ip, node)
            else:
                # append the server to the to run list.
                servers.append({'node': node, 'ip': ip, 'root_password': root_password, 'run_list': run_list})

    if not display_only and servers:
        # create test env dictionary for env.sh.
        opencenter_test_env = {'OPENCENTER_ENDPOINT': 'http://127.0.0.1:8080', 'OPENCENTER_USER': opencenter_user, 'OPENCENTER_PASSWORD': opencenter_password}
        
        # temporary list of servers that are clients.
        client_temp = []
        
        # Role list for env.sh.
        opencenter_role_list = ['INSTANCE_CHEF_HOSTNAME', 'INSTANCE_COMPUTE_HOSTNAME', 'INSTANCE_CONTROLLER_HOSTNAME']
        
        # opencenter Server IP
        opencenter_server_ip = ""
        
        # opencenter Server password
        opencenter_server_password = ""

        for server in servers:
            # If the role is opencenter-server, save the server information.
            print server['run_list']
            if 'role[qa-opencenter-server]' in server['run_list']:
                opencenter_test_env['INSTANCE_SERVER_HOSTNAME'] = server['node']
                opencenter_server_ip = server['ip']
                opencenter_server_password = server['root_password']
            # if the role is opencenter-client, add to temp list.
            elif 'role[qa-opencenter-agent]' in server['run_list']:
                client_temp.append(server['node'])
            else:
                print "!!## -- Server with name: %s doesnt have opencenter server or client in its run list  -- ##!!" % server['node']
                pass
                
        # assign a opencenter test role to each client server.
        if not client_temp:
            print "No clients in run list"
            sys.exit(1)

        for role in opencenter_role_list:
            opencenter_test_env['%s' % role] = client_temp.pop()

        # open and write env.sh based off of opencenter_test_env dict.
        try:
            # Open the file
            fo = open("/tmp/env-%s.sh" % opencenter_server_ip, "w")
        except IOError:
            print "!!## -- Failed to open file env.sh  -- ##!!"
        else:
            for k,v in opencenter_test_env.iteritems():
                to_write = "export %s=%s\n" % (k, v)
                fo.write(to_write)
            fo.close()
            print "!!## -- env.sh successfully saved -- ##!!"
        
        env_file = "/tmp/env-%s.sh" % opencenter_server_ip
        with open(env_file, "r") as fo:
            print fo.read()
            
        # SCP the env.sh to the opencenter server
        try:
            print "!!## -- Transfering the environment file to the server: %s -- ##!!" % opencenter_server_ip
            check_call_return = check_call("sshpass -p %s scp -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet %s root@%s:/root/env.sh" % (opencenter_server_password, env_file, opencenter_server_ip), shell=True)
        except CalledProcessError, cpe:
            print "!!## -- Failed to transfer environment file  -- ##!!"
            print "!!## -- Return Code: %s  -- ##!!" % cpe.returncode
            #print "!!## -- Command: %s -- ##!!" % cpe.cmd
            print "!!## -- Output: %s -- ##!!" % cpe.output
            
        
        # Delete env.sh from current file system
        print "!!## -- Removing environment from system -- ##!!"
        try:
            os.remove("/tmp/env-%s.sh" % opencenter_server_ip)
        except Exception, e:
            print "!!## -- Failed to remove file: %s  -- ##!!" % e
            sys.exit(1)


        # Run the proper steps to install and run opencenter-testerator
        print "!!## -- Running opencenter tests on server with ip %s  -- ##!!" % (opencenter_server_ip)
        commands=["apt-get install git python-pip -y", 
                  "if [ ! -d 'opencenter-testerator' ]; then git clone %s; fi" % results.opencenter_test_repo, 
                  "pip install -r /root/opencenter-testerator/tools/pip-requires", 
                  "cat /root/env.sh", 
                  "source /root/env.sh; nosetests /root/opencenter-testerator/tests/test_happy_path.py -v"]
        
        for command in commands: 
            try:
                check_call_return = check_call("sshpass -p %s ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet -l root %s '%s'" % (opencenter_server_password, opencenter_server_ip, command), shell=True)
                print "!!## -- command: %s on %s run successfully  -- ##!!" % (command, opencenter_server_ip)
            except CalledProcessError, cpe:
                print "!!## -- Command %s failed to run on server with ip: %s -- ##!!" % (command, opencenter_server_ip)
                print "!!## -- Return Code: %s -- ##!!" % cpe.returncode
                #print "!!## -- Command: %s -- ##!!" % cpe.cmd
                print "!!## -- Output: %s -- ##!!" % cpe.output
                sys.exit(1)
else:
    # No active models for the policy present, exit.
    print "!!## -- Razor Policy %s has no active models -- ##!!"
    sys.exit(1)
    
