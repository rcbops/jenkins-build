import sys
from cStringIO import StringIO
from paramiko import SSHClient, AutoAddPolicy
from subprocess import check_call, CalledProcessError


def run_cmd(command):
    """
    @param cmd
    @return A map based on pass / fail run info
    """
    try:
        ret = check_call(command, shell=True)
        return {'success': True, 'return': ret, 'exception': None}
    except CalledProcessError, cpe:
        return {'success': False,
                'return': None,
                'exception': cpe,
                'command': command}


def ssh_cmd(ip, remote_cmd, user='root', password=None, quiet=False):
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
    ssh.connect(ip, username=user, password=password)
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


def scp_to(ip, local_path, user='root', password=None, remote_path=""):
    """
    @param to_copy
    @return A map based on pass / fail run info
    """
    command = ("sshpass -p %s scp "
               "-o Self.UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s %s@%s:%s") % (password,
                                 local_path,
                                 user, ip,
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


def scp_from(ip, remote_path, user=None, password=None, local_path=""):
    """
    @param path_to_file: file to copy
    @param copy_location: place on localhost to place file
    """

    command = ("sshpass -p %s scp "
               "-o Self.UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s@%s:%s %s") % (password,
                                 user, ip,
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
