#! /bin/bash
#               OpenCenter(TM) is Copyright 2013 by Rackspace US, Inc.
##############################################################################
#
# OpenCenter is licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  This
# version of OpenCenter includes Rackspace trademarks and logos, and in
# accordance with Section 6 of the License, the provision of commercial
# support services in conjunction with a version of OpenCenter which includes
# Rackspace trademarks and logos is prohibited.  OpenCenter source code and
# details are available at: # https://github.com/rcbops/opencenter or upon
# written request.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 and a copy, including this
# notice, is available in the LICENSE file accompanying this software.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the # specific language governing permissions and limitations
# under the License.
#
##############################################################################
#

set -e
set -u
set -x
export DEBIAN_FRONTEND=noninteractive
#source "$OPENCENTER_BASH_DIR/opencenter.sh"

function id_OS {
    if [ -f "/etc/lsb-release" ]; then
      OS_TYPE=$(grep "DISTRIB_ID" /etc/lsb-release | cut -d"=" -f2 | tr "[:upper:]" "[:lower:]")
    elif [ -f "/etc/system-release-cpe" ]; then
      OS_TYPE=$(cat /etc/system-release-cpe | cut -d ":" -f 3)
    fi
}

OS_TYPE="undef"
id_OS

CHEF_SERVER_VERSION=${CHEF_SERVER_VERSION:-11.0.4-1}

if [[ $OS_TYPE = "debian"  ]] || [[ $OS_TYPE = "ubuntu" ]]; then
    locale-gen en_US.UTF-8
    apt-get install -y --force-yes pwgen lsb-release
    cp /etc/resolv.conf /tmp/rc
    apt-get remove --purge resolvconf -y --force-yes
    cp /tmp/rc /etc/resolv.conf
elif [[ $OS_TYPE = "redhat" ]] || [[ $OS_TYPE = "centos" ]] || [[ $OS_TYPE = "fedora" ]]; then
    yum -y install pwgen curl
else
    echo "Your distribution is not supported"
    exit 1
fi

PRIMARY_INTERFACE=$(ip route list match 0.0.0.0 | awk 'NR==1 {print $5}')
MY_IP=$(ip addr show dev ${PRIMARY_INTERFACE} | awk 'NR==3 {print $2}' | cut -d '/' -f1)
CHEF_UNIX_USER=${CHEF_UNIX_USER:-root}
# due to http://tickets.opscode.com/browse/CHEF-3849 CHEF_FE_PORT is not used yet
CHEF_FE_PORT=${CHEF_FE_PORT:-80}
CHEF_FE_SSL_PORT=${CHEF_FE_SSL_PORT:-443}
CHEF_URL=${CHEF_URL:-https://${MY_IP}:${CHEF_FE_SSL_PORT}}

if [ ! -e "/etc/chef-server/chef-server.rb" ]; then
  # defaults if not set
  CHEF_WEBUI_PASSWORD=${CHEF_WEBUI_PASSWORD:-$(pwgen -1)}
  CHEF_AMQP_PASSWORD=${CHEF_AMQP_PASSWORD:-$(pwgen -1)}
  CHEF_POSTGRESQL_PASSWORD=${CHEF_POSTGRESQL_PASSWORD:-$(pwgen -1)}
  CHEF_POSTGRESQL_RO_PASSWORD=${CHEF_POSTGRESQL_PASSWORD:-$(pwgen -1)}

  mkdir -p /etc/chef-server
  cat > /etc/chef-server/chef-server.rb <<EOF
node.override["chef_server"]["chef-server-webui"]["web_ui_admin_default_password"] = "${CHEF_WEBUI_PASSWORD}"
node.override["chef_server"]["rabbitmq"]["password"] = "${CHEF_AMQP_PASSWORD}"
node.override["chef_server"]["postgresql"]["sql_password"] = "${CHEF_POSTGRESQL_PASSWORD}"
node.override["chef_server"]["postgresql"]["sql_ro_password"] = "${CHEF_POSTGRESQL_RO_PASSWORD}"
node.override["chef_server"]["nginx"]["url"] = "${CHEF_URL}"
node.override["chef_server"]["nginx"]["ssl_port"] = ${CHEF_FE_SSL_PORT}
node.override["chef_server"]["nginx"]["non_ssl_port"] = ${CHEF_FE_PORT}
node.override["chef_server"]["nginx"]["enable_non_ssl"] = true
if (node['memory']['total'].to_i / 4) > ((node['chef_server']['postgresql']['shmmax'].to_i / 1024) - 2097152)
  # guard against setting shared_buffers > shmmax on hosts with installed RAM > 64GB
  # use 2GB less than shmmax as the default for these large memory machines
  node.override['chef_server']['postgresql']['shared_buffers'] = "14336MB"
else
  node.override['chef_server']['postgresql']['shared_buffers'] = "#{(node['memory']['total'].to_i / 4) / (1024)}MB"
end
EOF

    HOMEDIR=$(getent passwd ${CHEF_UNIX_USER} | cut -d: -f6)
    export HOME=${HOMEDIR}

    if [[ $OS_TYPE = "debian"  ]] || [[ $OS_TYPE = "ubuntu" ]]; then
        if ! dpkg -s chef-server &>/dev/null; then
            curl -L "http://www.opscode.com/chef/download-server?p=ubuntu&pv=12.04&m=x86_64&v=${CHEF_SERVER_VERSION}" > /tmp/chef-server.deb
            dpkg -i /tmp/chef-server.deb
            chef-server-ctl reconfigure
            rm -f /tmp/chef-server.deb
        fi
    else
        if ! rpm -q chef-server &>/dev/null; then
            curl -L "http://www.opscode.com/chef/download-server?p=el&pv=6&m=x86_64&v=${CHEF_SERVER_VERSION}" > /tmp/chef-server.rpm
            rpm -ivh /tmp/chef-server.rpm
            chef-server-ctl reconfigure
            rm -f /tmp/chef-server.rpm
        fi
    fi

    mkdir -p ${HOMEDIR}/.chef
    cp /etc/chef-server/{chef-validator.pem,chef-webui.pem,admin.pem} ${HOMEDIR}/.chef
    chown -R ${CHEF_UNIX_USER}: ${HOMEDIR}/.chef

    if [[ ! -e ${HOMEDIR}/.chef/knife.rb ]]; then
       cat <<EOF | /opt/chef-server/bin/knife configure -i
${HOMEDIR}/.chef/knife.rb
${CHEF_URL}
root
chef-webui
${HOMEDIR}/.chef/chef-webui.pem
chef-validator
${HOMEDIR}/.chef/chef-validator.pem

EOF
        # setup the path
        echo 'export PATH=${PATH}:/opt/chef-server/bin' >> ${HOMEDIR}/.profile
    fi

    # these are only returned on a run where we actually install chef-server
fi