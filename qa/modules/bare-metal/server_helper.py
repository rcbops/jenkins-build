import time
import sys
from subprocess import check_call, CalledProcessError

def run_remote_ssh_cmd(server_ip, user, passwd, remote_cmd):
    """
    @param server_ip
    @param user
    @param passwd
    @param remote_cmd
    @return A map based on pass / fail run info
    """
    command = ("sshpass -p %s ssh "
               "-o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "-l %s %s '%s'") % (passwd,
                                   user,
                                   server_ip,
                                   remote_cmd)
    try:
        ret = check_call(command, shell=True)
        return {'success': True, 'return': ret, 'exception': None}
    except CalledProcessError, cpe:
        return {'success': False,
                'retrun': None,
                'exception': cpe,
                'command': command}

def run_remote_scp_cmd(server_ip, user, passwd, to_copy):
    """
    @param server_ip
    @param user
    @param passwd
    @param to_copy
    @return A map based on pass / fail run info
    """
    command = ("sshpass -p %s scp "
               "-o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no "
               "-o LogLevel=quiet "
               "%s %s@%s:~/") % (passwd,
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

