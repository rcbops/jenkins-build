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
                'return': None,
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

def disable_iptables(self, ip, user, password, logfile="STDOUT"):
        commands = '/etc/init.d/iptables save; \
                    /etc/init.d/iptables stop; \
                    /etc/init.d/iptables save'
        return self.run_remote_ssh_cmd(ip, user, password, commands)

def update(self, ip, platform, user, password):
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
        ip = chef_node['ipaddress']
        if platform == "ubuntu":
            self.run_remote_ssh_cmd(ip, 
                                    user, 
                                    password, 
                                    'apt-get update -y; apt-get upgrade -y')
        elif platform == "rhel" || platform == 'centos':
            self.run_remote_ssh_cmd(ip, 
                                    user, 
                                    password, 
                                    'yum update -y')
        else:
            print "Platform %s is not supported." % platform
            sys.exit(1)
