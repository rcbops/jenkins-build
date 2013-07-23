#!/bin/sh

#################################################################################
# This script will cycle the power of servers using ipmi
#################################################################################

USAGE="usage: $0 [-h help] -u user -p pass [-f address_file]"

while getopts ":u:p:f:h:" OPTIONS; do
    case $OPTIONS in
	u ) user=$OPTARG;;
	p ) password=$OPTARG;;
	f ) file=$OPTARG;;
	h )  echo $USAGE
	    exit;;
	* )  echo $USAGE >&2
	    exit 1;;
    esac
done

if [ -z $user ] || [ -z $password ]; then
    echo $USAGE
    exit 1
fi

# If file not specified then drac_ips in the same directory used
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ ! $file ]; then
    file="$DIR/drac_ips"
fi
if [ ! -e $file ]; then
    echo "$file does not exist"
    exit 1
fi

# Support OS X
cmd="ipmipower -c -u $user -p $password -h"
if [[ `uname` == "Darwin" ]]; then
    cmd="ipmiutil power -c -U $user -P $password -N"
fi

for address in `awk '{if($2 == "working"){print $1;}}' $file`; do 
    echo "$cmd $address" | bash -x
done
