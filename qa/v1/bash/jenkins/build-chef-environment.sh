#!/bin/bash

function set_environment_files(){
    echo "Building ${NAME}-${OS_DISTRO}-${FEATURE_SET} chef environment for OpenStack component $PACKAGE_COMPONENT"
    
    # set filenames
    TEMPLATE_FILENAME="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/templates/${OS_DISTRO}-${FEATURE_SET}.json"
    ENVIRONMENT_FILENAME="/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}.json"

    ## copy the environment file to the proper directory
    echo "Copying template to environment..."
    cp $TEMPLATE_FILENAME $ENVIRONMENT_FILENAME
}

function build_chef_environment() {
    echo "Set Knife Environment..."
    knife environment from file $ENVIRONMENT_FILENAME
}

function build_default() {

    # build environment files from templates
    set_environment_files

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_daily() {

    # build environment files from templates
    set_environment_files

    # source our secret file with hidden info
    source ~/source_files/CLOUD_FILES_AUTH.sh

    ## replace the lines we are looking for
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_ID>/'${TENANT_ID}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_NAME>/'${TENANT_NAME}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_PASSWORD>/'${TENANT_PASSWORD}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_ha() {

    # build environment files from templates
    set_environment_files

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_glance_cf() {

    # build environment files from templates
    set_environment_files
    
    # source our secret file with hidden info
    source ~/source_files/CLOUD_FILES_AUTH.sh

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_ID>/'${TENANT_ID}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_NAME>/'${TENANT_NAME}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<TENANT_PASSWORD>/'${TENANT_PASSWORD}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_keystone_ldap() {

    # build environment files from templates
    set_environment_files

    # Source the file that has our environment variables
    source ~/source_files/LDAP.sh

    export LDAP_IP=`knife search node 'role:qa-openldap-precise' | grep IP | awk '{print $2}'`

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<LDAP_IP>/'${LDAP_IP}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<LDAP_ADMIN_PASS>/'${LDAP_ADMIN_PASS}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_nova_quantum() {

    # build environment files from templates
    set_environment_files

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_swift() {

    # build environment files from templates
    set_environment_files

    # source our secret file with hidden info
    source ~/source_files/SWIFT_STUFF.sh

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<MANAGEMENT_NETWORK>/'${MANAGEMENT_NETWORK}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<EXTERNAL_NETWORK>/'${EXTERNAL_NETWORK}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<SWIFT_HASH_PREFIX>/'${SWIFT_HASH_PREFIX}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<SWIFT_HASH_SUFFIX>/'${SWIFT_HASH_SUFFIX}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

function build_opencenter() {

    # build environment files from templates
    set_environment_files

    ## replace the lines we are looking for
    echo "Replacing template values with real values..."
    result=`sed -i 's/<NAME>/'${NAME}-${OS_DISTRO}-${PACKAGE_COMPONENT}-${FEATURE_SET}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<PACKAGE_COMPONENT>/'${PACKAGE_COMPONENT}'/g' $ENVIRONMENT_FILENAME`
    result=`sed -i 's/<THEME>/'${THEME}'/g' $ENVIRONMENT_FILENAME`

    # build chef environment
    build_chef_environment
}

#BEGIN SCRIPT

if [[ "$#" -eq 0 ]]; then
    echo "Usage: $0 [-h help] -n name -p package_component -d os_distro -f feature_set -t theme" >&2
    exit
fi

while getopts "n:p:d:f:t:h" OPTION;
do
    case $OPTION in
        n)  NAME=$OPTARG
            ;;
        p)  PACKAGE_COMPONENT=$OPTARG
            ;;
        d)  OS_DISTRO=$OPTARG
            ;;
        f)  FEATURE_SET=$OPTARG
            ;;
        t)  THEME=$OPTARG
            ;;
        h)  echo "Usage: $0" >&2
            echo "  -h   Return this help information" >&2
            echo "  -n   The name to prepend to the environment (i.e. test, yourname, etc)"
            echo "  -p   The package component for OpenStack (i.e. folsom, grizzly, etc). REQUIRED" >&2
            echo "  -d   The operating system distribution that OpenStack will be built on (i.e. precise, centos, redhat). REQUIRED" >&2
            echo "  -f   The feature set of OpenStack to build (i.e. glance-cf, keystone-ldap, etc). REQUIRED" >&2
            echo "  -t   The CSS theme to use on Horizon. (Rackspace, default) REQUIRED" >&2 
            exit
            ;;
    esac
done

case $FEATURE_SET in
    'default')          build_default;;
    'daily')            build_daily;;
    'ha')               build_ha;;
    'glance-cf')        build_glance_cf;;
    'keystone-ldap')    build_keystone_ldap;;
    'nova-quantum')     build_nova_quantum;;
    'swift')            build_swift;;
    'opencenter')       build_opencenter;;
esac

echo "Done..."
