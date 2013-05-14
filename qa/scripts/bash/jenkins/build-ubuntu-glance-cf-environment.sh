#!/bin/bash

# Source the file that has our environment variables
source ~/source_files/CLOUD_FILES_AUTH.sh

template_filename='/var/lib/jenkins/rpcsqa/chef-cookbooks/environments/templates/ubuntu-glance-cf.json'
environment_filename='/var/lib/jenkins/rpcsqa/chef-cookbooks/environments/ubuntu-glance-cf.json'

## copy the environment file to the proper directory
echo "Copying template to environment..."
cp $template_filename $environment_filename

## replace the lines we are looking for
echo "Replacing template values with real values..."
result=`sed -i 's/<TENANT_ID>/'${TENANT_ID}'/g' $environment_filename`
result=`sed -i 's/<TENANT_NAME>/'${TENANT_NAME}'/g' $environment_filename`
result=`sed -i 's/<TENANT_PASSWORD>/'${TENANT_PASSWORD}'/g' $environment_filename`

echo "Set Knife Environment..."
knife environment from file $environment_filename

echo "Done..."