#!/bin/bash

#****************************
# Check for Alamo install 
#****************************

#check to make sure user can be root

if [ `whoami` != "root" ] ; then
    echo "Can only run script as root"; exit;
fi

#Check for file installed by alamo. 
echo -ne "Checking for alamo install."

if [ ! -f /root/.novarc ] ; then
    echo "No .novarc  .....  "; exit;
fi
if [ ! -f /root/.novarc ] ; then
    echo "No .novarc  .....  "; exit;
fi

echo "...OK"


#****************************
#Start gathering info
#****************************
echo "Gathering info...."

#Get ip address for eth0 (hopefully public ip) 
ip=`ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | awk '{ print $1}'`
echo "eth0 ip address: $ip"


#Source the .novarc for credentails for keystone and nova client
cd /root
source /root/.novarc


#[nova]
auth_url="http://$ip:5000/v2.0/tokens"
auth_url=`cat .novarc | grep 'export OS_AUTH_URL' | cut -d"=" -f 2 | sed 's/$/tokens/'`

admin_username=`cat .novarc | grep 'export OS_USERNAME' | cut -d"=" -f 2`
admin_password=`cat .novarc | grep 'export OS_PASSWORD' | cut -d"=" -f 2`
admin_tenant=`cat .novarc | grep 'export OS_TENANT_NAME' | cut -d"=" -f 2`
admin_tenant_id=`keystone user-list | grep $admin_tenant | awk '{print $2}'`

auth_strategy=`cat .novarc | grep 'export OS_AUTH_STRATEGY' | cut -d"=" -f 2`
region=`cat .novarc | grep 'export NOVA_REGION_NAME' | cut -d"=" -f 2`

other_user_name="demo"
other_user_password="demo"
other_tenant_name="demo"
other_region="RegionOne"

#[environment]
mysqlusername=`cat .my.cnf | grep user= | cut -d'=' -f 2`
mysqlpassword=`cat .my.cnf | grep password= | cut -d'=' -f 2`
mysql_conn_string="$mysqlusername:$mysqlpassword@$ip/nova"

compute_endpoint_name=`keystone service-list | grep Compute | awk '{print $4}'`

image_ref="cirros-image"
image_ref_alt="precise-image"
cirros_image_id=`glance index --limit=10000 | grep cirros-image | awk '{print $1}'`

flavor_ref="1"
flavor_ref_alt="2"

cd /root


##############################
## Starting to write config
##############################


# Write nova section of config
###############################

rm zodiac.conf

echo "[nova]" > zodiac.conf
echo "" >> zodiac.conf


echo "auth_url=$auth_url" >> zodiac.conf

#Admin User Info 
echo "admin_user=$admin_username" >> zodiac.conf
echo "admin_api_key=$admin_password" >> zodiac.conf
echo "admin_tenant_id=$admin_tenant_id" >> zodiac.conf
echo "admin_tenant_name=$admin_tenant" >> zodiac.conf
echo "region=$region" >> zodiac.conf
echo "" >> zodiac.conf

#User Info
echo "user=$admin_username" >> zodiac.conf
echo "api_key=$admin_password" >> zodiac.conf
echo "tenant_name=$admin_tenant" >> zodiac.conf
echo "tenant_id=$admin_tenant_id" >> zodiac.conf
echo "region=$region" >> zodiac.conf
echo "" >> zodiac.conf

#Other user info
echo "other_user=$other_user_name" >> zodiac.conf
echo "other_api_key=$other_user_password" >> zodiac.conf
echo "other_tenant_name=$other_tenant_name" >> zodiac.conf
echo "other_region=$other_region" >> zodiac.conf
echo "" >> zodiac.conf

#Timeouts
echo "ssh_timeout=45" >> zodiac.conf
echo "build_interval=8" >> zodiac.conf
echo "build_timeout=200" >> zodiac.conf
echo "create_limit=300" >> zodiac.conf
echo "" >> zodiac.conf




# Write environment section of config
########################################
echo "" >> zodiac.conf
echo "[environment]" >> zodiac.conf
echo "" >> zodiac.conf


echo "mysql_conn_string=$mysql_conn_string" >> zodiac.conf
echo "authentication=$auth_strategy" >> zodiac.conf
echo "compute_endpoint_name=$compute_endpoint_name" >> zodiac.conf
echo "" >> zodiac.conf

echo "image_ref=$image_ref" >> zodiac.conf
echo "image_ref_alt=$image_ref_alt" >> zodiac.conf
echo "windows_image_ref=$cirros_image_id" >> zodiac.conf
echo "" >> zodiac.conf

echo "os_type=linux" >> zodiac.conf
echo "flavor_ref=1" >> zodiac.conf >> zodiac.conf
echo "flavor_ref_alt=2" >> zodiac.conf
echo "" >> zodiac.conf

# Other options for env.
echo "env_name=preprod" >> zodiac.conf
echo "ip_address_version_for_ssh=4" >> zodiac.conf
echo "create_image_enabled=true" >> zodiac.conf
echo "resize_available=true" >> zodiac.conf
echo "use_xml_format=False" >> zodiac.conf
echo "" >> zodiac.conf




#Hardware Info

rm hwinfo.txt
sudo lshw >> hwinfo.txt


#Nova Version
rm nova-version.txt
nova-manage version list >> nova-version.txt

sudo apt-get install python-MySQLdb -qq -y

rm dbupload-config.py
wget 198.61.203.76/zodiac/dbupload-config.py
python dbupload-config.py zodiac.conf hwinfo.txt nova-version.txt
rm dbupload-config.py


echo "HOST ID:  $ZODIAC_HOST_ID " 







