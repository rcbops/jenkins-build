#!/bin/bash

# Source the file that has our environment variables
source ~/source_files/LDAP.sh

export LDAP_IP=`knife search node 'role:qa-openldap-ubuntu' | grep IP | awk '{print $2}'`

template_filename='/var/lib/jenkins/rpcsqa/chef-cookbooks/environments/templates/ubuntu-keystone-ldap.json'
environment_filename='/var/lib/jenkins/rpcsqa/chef-cookbooks/environments/ubuntu-keystone-ldap.json'
filelines=`cat $filename`

## copy the environment file to the proper directory
echo "Copying template to environment..."
cp $template_filename $environment_filename


## replace the lines we are looking for
echo "Replacing template values with real values..."
result=`sed -i 's/<LDAP_IP>/'${LDAP_IP}'/g' $environment_filename`
result=`sed -i 's/<LDAP_ADMIN_PASS>/'${LDAP_ADMIN_PASS}'/g' $environment_filename`


echo "Set Knife Environment..."
knife environment from file $environment_filename

echo "Done..."