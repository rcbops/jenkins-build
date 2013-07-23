#!/bin/bash

#print usage and exit
if [ "$#" -eq 0 ]; then
        echo "Usage: private-ip-to-mac.sh -p root_pass" >&2
        exit
fi

# Get the root password from the box off the command line
while getopts "p:h" OPTION;
do
        case $OPTION in
                p) ROOT_PASS=$OPTARG
                   ;;
                h) echo "Usage: nmap_reboot.sh [-h]" >&2
                   echo " -h Return this help information" >&2
                   echo " -p The root password for the boxes to be rebooted" >&2
                   exit
                   ;;
        esac
done

# Run nmap to get the boxes that are alive
results=`nmap -sP -oG alive 10.0.0.0/24 | grep 10.0.0.* | awk '{print $5 $6}'`

# Loop through the alive boxes, grab the ip and then reboot them
IP_END=255
for item in ${results}
do
        if [[ $item =~ '10.0.0.' ]]; then
                ip=`echo "$item" | grep -o '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}'`
                if [[ $ip == '10.0.0.1' ]]; then
                        echo "This box is restricted infrastructure, ignore it."
                else
                        output=`sshpass -p $ROOT_PASS ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=quiet -l root $ip 'ip a | grep link/ether' | awk '{print $2}' | sed s/:/''/g`
                        i=0
                        for o in ${output}; do
                                mac_array[i++]=$o
                        done
                        new_array=`echo ${mac_array[@]} | sed -e 's/ /_/g' | tr '[:lower:]' '[:upper:]'`
                        echo "\"${new_array[@]}\": \"198.101.133.${IP_END}\","
                fi
        fi
    IP_END=`expr $IP_END - 1`
done