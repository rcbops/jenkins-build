import sys
import time
from chef import Node, autoconfigure, Client
from cStringIO import StringIO
from paramiko import SSHClient, AutoAddPolicy
from subprocess import check_call, CalledProcessError


class OSNode:
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        """
        @param server_ip
        @param user
        @param password
        @param remote_cmd
        @return A map based on pass / fail run info
        """
        output = StringIO()
        error = StringIO()
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        user = user or self.user
        password = password or self.password
        ssh.connect(self.ip, username=user, password=password)
        stdin, stdout, stderr = ssh.exec_command(remote_cmd)
        stdin.close()
        for line in stdout.xreadlines():
            if not quiet:
                sys.stdout.write(line)
                output.write(line)
        for line in stderr.xreadlines():
            sys.stdout.write(line)
            error.write(line)
            exit_status = stdout.channel.recv_exit_status()
        return {'success': True if exit_status == 0 else False,
                'return': output.getvalue(),
                'exit_status': exit_status,
                'error': error.getvalue()}

    def scp_to(self, local_path, remote_path=""):
        """
        @param to_copy
        @return A map based on pass / fail run info
        """
        command = ("sshpass -p %s scp "
                   "-o Self.UserKnownHostsFile=/dev/null "
                   "-o StrictHostKeyChecking=no "
                   "-o LogLevel=quiet "
                   "%s %s@%s:%s") % (self.password,
                                     local_path,
                                     self.user,
                                     self.ip,
                                     remote_path)
        try:
            ret = check_call(command, shell=True)
            return {'success': True,
                    'return': ret,
                    'exception': None}
        except CalledProcessError, cpe:
            return {'success': False,
                    'return': None,
                    'exception': cpe,
                    'command': command}

    def scp_from(self, remote_path, local_path=""):
        """
        @param path_to_file: file to copy
        @param copy_location: place on localhost to place file
        """

        command = ("sshpass -p %s scp "
                   "-o Self.UserKnownHostsFile=/dev/null "
                   "-o StrictHostKeyChecking=no "
                   "-o LogLevel=quiet "
                   "%s@%s:%s %s") % (self.password,
                                     self.user,
                                     self.ip,
                                     remote_path,
                                     local_path)

        try:
            ret = check_call(command, shell=True)
            return {'success': True,
                    'return': ret,
                    'exception': None}
        except CalledProcessError, cpe:
            return {'success': False,
                    'return': None,
                    'exception': cpe,
                    'command': command}

    def __str__(self):
        return "Node: %s" % self.ip

    def teardown(self):
        raise NotImplementedError


class OSCluster:
    def __init__(self, nodes):
        self.nodes = nodes


class ProvisionedNode(OSNode):
    pass


class RazorNode(ProvisionedNode):
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password

    def __str__(self):
        return "Node: %s" % self.ip

    def teardown(self):
        map(super(OSCluster, self).teardown, next())


class ChefOSNode(OSNode):
    def __init__(self, ip, user, password, name, remote_api=None):
        self.chef_name = name


class ChefNode(OSNode):
    def __init__(self, name, remote_api=None):
        self.name = name
        self.api = autoconfigure()
        self.remote_api = remote_api
        node = Node(self.name, self.api)
        super(ChefOSNode, self).__init__(node['ipaddress'], user, password)

    def __str__(self):
        return "Chef Node: %s - %s" % (self.name, self.ip)

    def teardown(self):
        node = Node(self.name, self.api)
        Client(self.name).delete()
        node.delete()


class RazorOSNode(OSNode):
    def __init__(self, client, id):
        self.client = client
        self._id = id

    def teardown(self):
        self.client.remove_active_model(self._id)
        run = self.run_cmd("reboot 0")
        if not run['success']:
            raise Exception("Error rebooting: " % self.__str__)
        time.sleep(15)
