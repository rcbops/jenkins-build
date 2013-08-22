import sys
from chef import Node, autoconfigure
from cStringIO import StringIO
from paramiko import SSHClient, AutoAddPolicy


class OSnode:
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


class ProvisionedNode(OSNode):
    pass


class RazorNode(ProvisionedNode):
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password


class ChefNode(OSNode):
    def __init__(self, name, remote_api=None):
        self.name = name
        self.api = autoconfigure()
        self.remote_api = remote_api
        node = Node(self.name, self.api)
        super(ChefNode, self).__init__(node['ipaddress'], None, None)
