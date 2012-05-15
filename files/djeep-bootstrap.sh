#!/bin/bash

# cleanup
killall screen
rm -rf /opt/djeep
rm -rf /etc/rc.local && touch /etc/rc.local

# Please forgive me for this.. 
bash < <(curl -s https://raw.github.com/cloudbuilders/djeep/master/example_install.sh | sed -e 's|fetch_images.sh|fetch_images.sh\nsed -i "s,CHANGEME,10.127.52.107," \/opt\/djeep\/rolemapper\/fixtures\/initial_data.yaml|')

# Move the chef-server validation pem into place
cp /root/rcb-validator.pem /opt/djeep/media/chef_validators/jenkins-validation.pem

# Slam in our environment data
cd /opt/djeep/ && tools/with_venv.sh python manage.py loaddata /root/djeep-jenkins.yaml 

# Djeep templates dont get generated at startup.. need to poke it
curl http://0.0.0.0:8000/api/host/1 -H "Content-type: application/json" -d '{"local_boot": 1}' -X "PUT"
