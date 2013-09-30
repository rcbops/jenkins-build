import sys
import json
import time
import itertools
from chef import *
import environments
from glob import glob
from server_helper import *
from razor_api import razor_api
from xml.etree import ElementTree


class rpcsqa_helper:

    def __init__(self, razor_ip=''):
        self.razor = razor_api(razor_ip)
        self.chef = autoconfigure()
        self.chef.set_default()

    def enable_razor(self, razor_ip=''):
        if razor_ip != '':
            self.razor = razor_api(razor_ip)

    def enable_public_cloud(self, username, api_key):
        import pyrax
        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(username, api_key)
        self.cloudservers = pyrax.cloudservers

    def gather_public_cloud_nodes(self, os, environment, cluster_size):
        cs = self.cloudservers
        if not hasattr(self, 'cloudservers'):
            print "No cloudservers setup"
            sys.exit(1)
        else:
            qa_servers = [n.name for n in cs.list() if "qa-cloud-%s-pool" % os in n.name]
            max_num_servers = cluster_size if cluster_size > 10 else 10
            num_servers = len(qa_servers)
            if num_servers < max_num_servers:
                print "Currently %s servers in pool. Adding %s servers." % (len(qa_servers), max_num_servers-len(qa_servers))

            if os == "precise":
                image = [img for img in cs.images.list() if "Ubuntu 12.04" in img.name][0]
            elif os == "centos":
                image = [img for img in cs.images.list() if "Centos 6.3" in img.name][0]
            flavor = [flavor for flavor in cs.flavors.list() if flavor.ram == 512][0]

            server = cs.servers.create("qa-cloud-%s-pool%s" % (os, num_servers+1), image.id, flavor.id)
            num_servers += 1

            print "Num servers: %s " % num_servers

    def __repr__(self):
        """ Print out current instance of razor_api"""
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl

    def prepare_environment(self, name, os_distro, branch, features, theme="default", branch_tag=None):
        """ If the environment doesnt exist in chef, make it. """
        env = "%s-%s-%s-%s" % (name, os_distro, branch, "-".join(features))
        chef_env = Environment(env, api=self.chef)
        if not chef_env.exists:
            print "Making environment: %s " % env
            chef_env.create(env, api=self.chef)

        env_json = chef_env.to_dict()
        env_json['override_attributes'].update(environments.base_env['override_attributes'])
        for feature in features:
            if feature in environments.__dict__:
                env_json['override_attributes'].update(environments.__dict__[feature])
        chef_env.override_attributes.update(env_json['override_attributes'])
        chef_env.override_attributes['package_component'] = branch

        if 'neutron' in features:
            chef_env.override_attributes['nova'].pop("networks", None)
        else:
            old_networks = [{"num_networks": "1", "bridge": "br0",
                             "label": "public", "dns1": "8.8.8.8",
                             "dns2": "8.8.4.4", "bridge_dev": "eth1",
                             "network_size": "254",
                             "ipv4_cidr": "172.31.0.0/24"}]

            if branch_tag in ["folsom", "v3.1.0", "v4.0.0"]:
                chef_env.override_attributes['nova']['networks'] = old_networks
                if os_distro == "centos":
                    chef_env.override_attributes['nova']['networks'][0]['bridge_dev'] = "em2"
            else:
                if os_distro == "centos":
                    chef_env.override_attributes['nova']['networks']['public']['bridge_dev'] = "em2"
        chef_env.save()
        return env

    def delete_environment(self, chef_environment):
        Environment(chef_environment, api=self.chef).delete()

    def cleanup_environment(self, chef_environment):
        """ Rekick nodes previously in use and reuse clean nodes. """
        query = "chef_environment:%s" % chef_environment
        nodes = self.node_search(query)
        for n in nodes:
            if n['in_use'] != 0:
                self.erase_node(n)
            else:
                n.chef_environment = "_default"
                n.save()

    def run_command_on_node(self, node, command, num_times=1, quiet=False,
                            private=False):
        chef_node = Node(node.name, api=self.chef)
        runs = []
        success = True
        ip = self.private_ip(node) if private else node['ipaddress']
        for i in xrange(0, num_times):
            user_pass = self.razor_password(chef_node)
            print "On {0}, Running: {1}".format(node.name, command)
            run = run_remote_ssh_cmd(ip, 'root', user_pass, command, quiet)
            if run['success'] is False:
                success = False
            runs.append(run)
        return {'success': success, 'runs': runs}

    def private_ip(self, node):
        iface = "eth0" if "precise" in node.name else "em1"
        addrs = node['network']['interfaces'][iface]['addresses']
        for addr in addrs.keys():
            if addrs[addr]['family'] is "inet":
                return addr

    def run_chef_client(self, chef_node, num_times=1, log_level='error',
                        quiet=False):
        # log level can be (debug, info, warn, error, fatal)
        return self.run_command_on_node(chef_node,
                                        'chef-client -l %s' % log_level,
                                        num_times,
                                        quiet)

    def interface_physical_nodes(self, os):
        #Make sure all network interfacing is set
        query = "name:*%s*" % os
        for node in self.node_search(query):
            if "role[qa-base]" in node.run_list:
                node.run_list = ["recipe[network-interfaces]"]
                node['in_use'] = 0
                node.save()
                print "Running network interfaces for %s" % node
                #Run chef client thrice
                run_chef_client = self.run_chef_client(node,
                                                       num_times=3,
                                                       quiet=True)
                if run_chef_client['success']:
                    print "Done running chef-client"
                else:
                    for index, run in enumerate(run_chef_client['runs']):
                        print "Run %s: %s" % (index+1, run)

    def get_razor_node(self, os, environment):
        nodes = self.node_search("name:qa-%s-pool*" % os)
        # Take a node from the default environment that has its network interfaces set.
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[network-interfaces]" in node.run_list
            if (is_default and iface_in_run_list):
                node.chef_environment = environment
                node['in_use'] = 0
                node.save()
                return node
        raise Exception("No more nodes!!")

    def remove_broker_fail(self, policy):
        active_models = self.razor.simple_active_models(policy)
        for active in active_models:
            data = active_models[active]
            if 'broker_fail' in data['current_state']:
                print "!!## -- Removing active model  (broker_fail) -- ##!!"
                user_pass = self.razor.get_active_model_pass(
                    data['am_uuid'])['password']
                ip = data['eth1_ip']
                run = run_remote_ssh_cmd(ip, 'root', user_pass, 'reboot 0')
                if run['success']:
                    self.razor.remove_active_model(data['am_uuid'])
                    time.sleep(15)
                else:
                    print "!!## -- Trouble removing broker fail -- ##!!"
                    print run

    def erase_node(self, chef_node):
        print "Deleting: %s" % str(chef_node)
        am_uuid = chef_node['razor_metadata'].to_dict()['razor_active_model_uuid']
        run = run_remote_ssh_cmd(chef_node['ipaddress'], 'root', self.razor_password(chef_node), "reboot 0", quiet=True)
        if not run['success']:
            raise Exception("Error rebooting server %s@%s " % (chef_node, chef_node['ipaddress']))
        #Knife node remove; knife client remove
        Client(str(chef_node)).delete()
        chef_node.delete()
        #Remove active model
        self.razor.remove_active_model(am_uuid)
        time.sleep(15)

    def get_environment_nodes(self, environment='', api=None):
        """Returns all the nodes of an environment"""
        api = api or self.chef
        query = "chef_environment:%s" % environment
        return self.node_search(query, api)

    def razor_password(self, chef_node):
        try:
            chef_node = Node(chef_node.name, api=self.chef)
            uuid = chef_node.attributes['razor_metadata']['razor_active_model_uuid']
        except:
            print dict(chef_node.attributes)
            raise Exception("Couldn't find razor_metadata/password")
        return self.razor.get_active_model_pass(uuid)['password']

    def remote_chef_client(self, env):
        # RSAifying key
        env = Environment(env)
        remote_dict = dict(env.override_attributes['remote_chef'])
        return ChefAPI(**remote_dict)

    def node_search(self, query=None, api=None, tries=10):
        api = api or self.chef
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            time.sleep(10)
            tries = tries - 1
        return (n.object for n in search)

    # Make these use run_command_on_node
    def scp_from_node(self, node=None, path=None, destination=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        return get_file_from_server(ip, user, password, path, destination)

    def scp_to_node(self, node=None, path=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        return run_remote_scp_cmd(ip, user, password, path)


    def disable_controller(self, node):
        iface = "eth0" if "precise" in node.name else "em1"
        command = ("ifdown {0}".format(iface))
        self.run_command_on_node(node, command, private=True)

    def enable_controller(self, node):
        iface = "eth0" if "precise" in node.name else "em1"
        command = ("ifup {0}".format(iface))
        self.run_command_on_node(node, command, private=True)

    def feature_test(self, node, env):
        feature_map = {"default": ["compute", "identity"],
                       "ha": ["compute", "identity"],
                       "glance-cf": ["compute/images", "image"],
                       "glance-local": ["compute/images", "image"],
                       "keystone-ldap": ["compute/admin",
                                         "compute/security_groups",
                                         "compute/test_authorization.py",
                                         "identity"],
                       "keystone-mysql": ["compute/admin",
                                          "compute/security_groups",
                                          "compute/test_authorization.py",
                                          "identity"],
                       "neutron": ["network"],
                       "cinder-local": ["compute/volumes", "volume"],
                       "swift": ["object_storage"]}
        featured = filter(lambda x: x in env, feature_map.keys())
        test_list = (feature_map[f] for f in featured)
        tests = list(itertools.chain.from_iterable(test_list))
        rm_xml = "rm -f *.xml"
        self.run_command_on_node(node, rm_xml)
        run_cmd(rm_xml)
        self.run_tests(node, env, tests)
        if "default" not in env:
            smoke_tag = ["type=smoke"]
            self.run_tests(node, "smoke", tags=smoke_tag)
        self.xunit_merge()


    def run_tests(self, node, name, tests=None, tags=None):
        """
        Runs tests with optional tags, transfers results to current dir
        @param tests: Name for the tests
        @type tests: String
        @param tests: Test locations to run as strings
        @type tests: Iterable
        @param tag: Tags to run
        @type tag: Iterable
        """
        xunit_file = "{0}.xml".format(name)
        xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file
        tempest_dir = "/opt/tempest/"
        tag_arg = "-a " + " -a ".join(tags) if tags else ""
        paths = " ".join(tests) if tests else ""
        command = ("{0}tools/with_venv.sh nosetests -w "
                   "{0}tempest/tests {1} {2} {3}".format(tempest_dir,
                                                         xunit_flag,
                                                         tag_arg,
                                                         paths))
        self.run_command_on_node(node, command)
        self.scp_from_node(node=node, path=xunit_file, destination=".")

    def update_tempest_cookbook(self, env):
        cmds = ["cd /opt/rcbops/chef-cookbooks/cookbooks/tempest",
                "git pull origin master",
                "knife cookbook upload -a -o /opt/rcbops/chef-cookbooks/cookbooks"]
        query = "chef_environment:{0} AND in_use:chef-server".format(env.name)
        chef_server = next(self.node_search(query))
        self.run_command_on_node(chef_server, "; ".join(cmds))['success']

    def xunit_merge(self, path="."):
        files = glob(path +"/*.xml")
        tree = None
        attrs = ["failures", "tests", "errors", "skip"]
        for file in files:
            data = ElementTree.parse(file).getroot()
            for testcase in data.iter('testsuite'):
                if tree is None:
                    tree = data
                    insertion_point = tree
                else:
                    for attr in attrs:
                        tree.attrib[attr] = str(int(tree.attrib[attr]) +
                                                int(data.attrib[attr]))
                    insertion_point.extend(testcase)
        if tree is not None:
            with open("results.xunit", "w") as f:
                f.write(ElementTree.tostring(tree))

    # MOVE BELOW COMMANDS OUT
    def update_openldap_environment(self, env):
            chef_env = Environment(env, api=self.chef)
            query = 'chef_environment:%s AND run_list:*qa-openldap*' % env
            ldap_name = list(self.node_search(query))
            if ldap_name:
                ldap_ip = ldap_name[0]['ipaddress']
                chef_env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % ldap_ip
                chef_env.override_attributes['keystone']['ldap']['password'] = 'ostackdemo'
                chef_env.save()
                print "Successfully updated openldap into environment!"
            else:
                raise Exception("Couldn't find ldap server: %s" % ldap_name)

    def build_chef_server(self, chef_node=None, cookbooks=None, env=None):
        '''
        This will build a chef server using the rcbops script and install git
        '''
        if not chef_node:
            query = "chef_environment:%s AND in_use:chef_server" % env
            chef_node = next(self.node_search(query))
        self.remove_chef(chef_node.name)

        install_chef_script = "https://raw.github.com/rcbops/jenkins-build/master/qa/bash/jenkins/install-chef-server.sh"

        # Run the install script
        cmds = ['curl %s >> install-chef-server.sh' % install_chef_script,
                'chmod u+x ~/install-chef-server.sh',
                './install-chef-server.sh']
        for cmd in cmds:
            ssh_run = self.run_command_on_node(chef_node, cmd)
            if ssh_run['success']:
                print "command: %s ran successfully on %s" % (cmd, chef_node)

        self.install_cookbooks(chef_node, cookbooks)
        if env:
            chef_env = Environment(env)
            self.add_remote_chef_locally(chef_node, chef_env)
            self.setup_remote_chef_environment(chef_env)

    def prepare_cinder(self, name, api):
        node = Node(name, api=api.api)
        cmds = ["vg=`vgdisplay 2> /dev/null | grep vg | awk '{print $3}'`",
                ("for i in `lvdisplay 2> /dev/null | grep 'LV Name' | grep lv"
                 " | awk '{print $3}'`; do lvremove $i; done"),
                "vgreduce $vg --removemissing"]
        self.run_command_on_node(node, "; ".join(cmds))
        cmd = "vgdisplay 2> /dev/null | grep vg | awk '{print $3}'"
        ret = self.run_command_on_node(node, cmd)['runs'][0]
        volume_group = ret['return']
        env = Environment(node.chef_environment, api=api.api)
        env.override_attributes["cinder"]["storage"]["lvm"]["volume_group"] = volume_group

    def remove_chef(self, name):
        """
        @param chef_node
        """
        chef_node = Node(name)
        print "removing chef on %s..." % chef_node
        if chef_node['platform_family'] == "debian":
            command = "apt-get remove --purge -y chef; rm -rf /etc/chef"
        elif chef_node['platform_family'] == "rhel":
            command = 'yum remove -y chef; rm -rf /etc/chef /var/chef'
        else:
            print "OS Distro not supported"
            sys.exit(1)

        run = self.run_command_on_node(chef_node, command)
        if run['success']:
            print "Removed Chef on %s" % chef_node
        else:
            print "Failed to remove chef on %s" % chef_node
            sys.exit(1)

    def install_cookbooks(self, chef_node, cookbooks, local_repo='/opt/rcbops'):
        '''
        @summary: This will pull the cookbooks down for git that you pass in cookbooks
        @param chef_server: The node that the chef server is installed on
        @type chef_server: String
        @param cookbooks A List of cookbook repos in dict form {url: 'asdf', branch: 'asdf'}
        @type cookbooks dict
        @param local_repo The location to place the cookbooks i.e. '/opt/rcbops'
        @type String
        '''
        # Make directory that the cookbooks will live in
        command = 'mkdir -p {0}'.format(local_repo)
        run_cmd = self.run_command_on_node(chef_node, command)
        if not run_cmd['success']:
            print "Command: %s failed to run on %s" % (command, chef_node)
            print run_cmd
            sys.exit(1)

        for cookbook in cookbooks:
            self.install_cookbook(chef_node, cookbook, local_repo)

    def install_cookbook(self, chef_node, cookbook, local_repo):
        # clone to cookbook
        cmds = ['cd {0}; git clone {1} -b {2} --recursive'.format(local_repo, cookbook['url'], cookbook['branch'])]

        cmds.append('cd /opt/rcbops/chef-cookbooks; git checkout %s' % cookbook['branch'])

        # Since we are installing from git, the urls are pretty much constant
        # Pulling the url apart to get the name of the cookbooks
        cookbook_name = cookbook['url'].split("/")[-1].split(".")[0]

        # Stupid logic to see if the repo name contains "cookbooks", if it does then
        # we need to load from cookbooks repo, not the repo itself.
        # I think this is stupid logic, there has to be a better way (jacob)
        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            cmds.append('cd /opt/rcbops/chef-cookbooks;'
                        'git submodule init;'
                        'git submodule sync;'
                        'git submodule update')
            cmds.append('knife cookbook upload --all --cookbook-path {0}/{1}/cookbooks'.format(local_repo, cookbook_name))
        else:
            cmds = ['knife cookbook upload --all --cookbook-path {0}/{1}'.format(local_repo, cookbook_name)]

        # Append role load to run list
        cmds.append('knife role from file {0}/{1}/roles/*.rb'.format(local_repo, cookbook_name))

        for cmd in cmds:
            run_cmd = self.run_command_on_node(chef_node, cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_node)
                print run_cmd
                sys.exit(1)

    def setup_remote_chef_environment(self, chef_environment):
        """
        @summary Duplicates the local chef environment remotely
        """
        print "Putting environment onto remote chef server"
        name = chef_environment.name
        remote_api = self.remote_chef_client(name)
        env = Environment(name, api=remote_api)
        env.override_attributes = dict(chef_environment.override_attributes)
        env.save()

    def add_remote_chef_locally(self, chef_server_node, env):
        print "Adding remote chef server credentials to local chef server"
        chef_server_node = Node(chef_server_node.name, api=self.chef)
        cmd = "cat ~/.chef/admin.pem"
        run = self.run_command_on_node(chef_server_node, cmd)
        if not run['success']:
            print "Error acquiring pem from %s" % (chef_server_node)
            print run
            sys.exit(1)
        admin_pem = run['runs'][0]['return']
        remote_dict = {"client": "admin",
                       "key": admin_pem,
                       "url": "https://%s:4443" %
                       chef_server_node['ipaddress']}
        env.override_attributes['remote_chef'] = remote_dict
        env.save()

    def bootstrap_chef(self, client_node, server_node):
        '''
        @summary: installs chef client on a node and bootstraps it to chef_server
        @param node: node to install chef client on
        @type node: String
        @param chef_server: node that is the chef server
        @type chef_server: String
        '''

        # install chef client and bootstrap
        client_node = Node(client_node.name)
        chef_client_ip = client_node['ipaddress']
        chef_client_password = self.razor_password(client_node)
        cmd = 'knife bootstrap %s -x root -P %s' % (chef_client_ip,
                                                    chef_client_password)
        ssh_run = self.run_command_on_node(server_node, cmd)

        if ssh_run['success']:
            print "Successfully bootstraped chef-client on %s to chef-server on %s" % (client_node, server_node)
