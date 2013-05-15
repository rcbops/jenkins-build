#!/bin/bash

function build_glance_cf() {

    echo "Building ${OS_DISTRO}-${FEATURE_SET} chef environment for OpenStack component $PACKAGE_COMPONENT"

    # set filenames
    template_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/templates/${OS_DISTRO}-${FEATURE_SET}.json"
    environment_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/${OS_DISTRO}-${FEATURE_SET}.json"
    
    # source our secret file with hidden info
    source ~/source_files/CLOUD_FILES_AUTH.sh

    ## copy the environment file to the proper directory
    echo "Copying template to environment..."
    cp $template_filename $environment_filename

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $environment_filename`
    result=`sed -i 's/<TENANT_ID>/'${TENANT_ID}'/g' $environment_filename`
    result=`sed -i 's/<TENANT_NAME>/'${TENANT_NAME}'/g' $environment_filename`
    result=`sed -i 's/<TENANT_PASSWORD>/'${TENANT_PASSWORD}'/g' $environment_filename`

    echo "Set Knife Environment..."
    knife environment from file $environment_filename
}

function build_keystone_ldap() {
    echo "Building ${OS_DISTRO}-${FEATURE_SET} chef environment for OpenStack component $PACKAGE_COMPONENT"

    # Source the file that has our environment variables
    source ~/source_files/LDAP.sh

    export LDAP_IP=`knife search node 'role:qa-openldap-ubuntu' | grep IP | awk '{print $2}'`

    # set filenames
    template_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/templates/${OS_DISTRO}-${FEATURE_SET}.json"
    environment_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/${OS_DISTRO}-${FEATURE_SET}.json"

    ## copy the environment file to the proper directory
    echo "Copying template to environment..."
    cp $template_filename $environment_filename


    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $environment_filename`
    result=`sed -i 's/<LDAP_IP>/'${LDAP_IP}'/g' $environment_filename`
    result=`sed -i 's/<LDAP_ADMIN_PASS>/'${LDAP_ADMIN_PASS}'/g' $environment_filename`

    echo "Set Knife Environment..."
    knife environment from file $environment_filename
}

function build_nova_quantum() {
    echo "NOT IMPLEMENTED"
}

function build_opencenter() {
    echo "Building ${OS_DISTRO}-${FEATURE_SET} chef environment for OpenStack component $PACKAGE_COMPONENT"
    # Set temp file and perm file
    template_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/templates/${OS_DISTRO}-${FEATURE_SET}.json"
    environment_filename="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/${OS_DISTRO}-${FEATURE_SET}.json"

    ## copy the environment file to the proper directory
    echo "Copying template to environment..."
    cp $template_filename $environment_filename

    echo "Set Knife Environment..."
    knife environment from file $environment_filename
}

if [[ "$#" -eq 0 ]]; then
    echo "Usage: $0 [-h help] -p package_component -d os_distro -f feature_set" >&2
    exit
fi

while getopts "p:d:f:h" OPTION;
do
    case $OPTION in
        p)  PACKAGE_COMPONENT=$OPTARG
            ;;
        d)  OS_DISTRO=$OPTARG
            ;;
        f)  FEATURE_SET=$OPTARG
            ;;
        h)  echo "Usage: $0" >&2
            echo "  -h   Return this help information" >&2
            echo "  -p   The package component for OpenStack (i.e. folsom, grizzly, etc). REQUIRED" >&2
            echo "  -d   The operating system distribution that OpenStack will be built on (i.e. precise, centos, redhat). REQUIRED" >&2
            echo "  -f   The feature set of OpenStack to build (i.e. glance-cf, keystone-ldap, etc). REQUIRED" >&2
            exit
            ;;
    esac
done

case $FEATURE_SET in
    'glance-cf')        build_glance_cf;;
    'keystone-ldap')    build_keystone_ldap;;
    'nova-quantum')     build_nova_quantum;;
    'opencenter')       build_opencenter;;
esac

echo "Done..."