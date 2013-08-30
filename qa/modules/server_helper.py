import sys
import paramiko
from cStringIO import StringIO
from subprocess import check_call, CalledProcessError
import os


def run_remote_ssh_cmd(server_ip, user, password, remote_cmd, quiet=False):
    """
    @param server_ip
    @param user
    @param password
    @param remote_cmd
    @return A map based on pass / fail run info
    """
    output = StringIO()
    error = StringIO()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(server_ip, username=user, password=password)
    stdin, stdout, stderr = ssh.exec_command(remote_cmd)
    stdin.close()
    for line in stdout:
        if not quiet:
            sys.stdout.write(line)
        output.write(line)
    for line in stderr:
        sys.stdout.write(line)
        error.write(line)
    exit_status = stdout.channel.recv_exit_status()
    return {'success': True if exit_status == 0 else False,
            'return': output.getvalue(),
            'exit_status': exit_status,
            'error': error.getvalue()}


def run_remote_scp_cmd(server_ip, user, password, to_copy):
    """
    @param server_ip
    @param user
    @param password
    @param to_copy
    @return A map based on pass / fail run info
    """
    command = ("sshpass -p %s scp "
               "-o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s %s@%s:~/") % (password,
                                 to_copy,
                                 user,
                                 server_ip)
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


def get_file_from_server(server_ip, user, password, path_to_file, copy_location):
    """
    @param server_ip: The servers ip to get file from
    @param user: remote server user
    @param password: remote users password
    @param path_to_file: file to copy
    @param copy_location: place on localhost to place file
    """

    command = ("sshpass -p %s scp "
               "-o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s@%s:%s %s") % (password,
                                 user,
                                 server_ip,
                                 path_to_file,
                                 copy_location)

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


def disable_iptables(ip, user, password, logfile="STDOUT"):
        commands = '/etc/init.d/iptables save; \
                    /etc/init.d/iptables stop; \
                    /etc/init.d/iptables save'
        return run_remote_ssh_cmd(ip, user, password, commands)


def update(ip, platform, user, password):
        '''
        @summary: Updates the chef node
        @param ip: ip of the server to update
        @type ip: String
        @param platform: The servers platform
        @type platform: String
        @param user: user name on controller node
        @type user: String
        @param password: password for the user
        @type password: String
        '''
        if platform == "ubuntu":
            run_remote_ssh_cmd(ip, user, password,
                               'apt-get update -y; apt-get upgrade -y')
        elif platform == "rhel" or platform == 'centos':
            run_remote_ssh_cmd(ip, user, password, 'yum update -y')
        else:
            print "Platform %s is not supported." % platform
            sys.exit(1)
