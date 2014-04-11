#!/usr/bin/env python

# Copyright 2014, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Author Kevin.Carter@Rackspace.com

import base64
import ConfigParser
import json
import logging
from logging import handlers
import os
import stat
import sys

import httplib2


class ConfigurationSetup(object):
    """Parse arguments from a Configuration file.

    Note that anything can be set as a 'Section' in the argument file.
    """
    def __init__(self):
        # System configuration file
        sys_config = os.path.join('/etc', APPNAME, '%s.conf' % APPNAME)

        # User configuration file
        user_config = os.path.join(HOME, '.%s.conf' % APPNAME)

        if os.path.exists(user_config):
            self.config_file = user_config
        elif os.path.exists(sys_config):
            self.config_file = sys_config
        else:
            msg = (
                'Configuration file for "%s" was not found. Valid'
                ' configuration files are [ %s ] or [ %s ]'
                % (APPNAME, user_config, sys_config)
            )
            exit_failure(msg)

        self.check_perms()

    def check_perms(self):
        """Check the permissions of the config file.

        Permissions must be 0600 or 0400.
        """
        # If config file is specified, confim proper permissions
        if os.path.isfile(self.config_file):
            confpath = self.config_file
            if os.path.isfile(os.path.realpath(confpath)):
                mode = oct(stat.S_IMODE(os.stat(confpath).st_mode))
                if not any([mode == '0600', mode == '0400']):
                    raise SystemExit(
                        'To use a configuration file the permissions'
                        ' need to be "0600" or "0400"'
                    )
        else:
            msg = 'Config file %s not found,' % self.config_file
            exit_failure(msg)

    def config_args(self, section='default'):
        """Loop through the configuration file and set all of our values.

        :param section: ``str``
        :return: ``dict``
        """
        if sys.version_info >= (2, 7, 0):
            parser = ConfigParser.SafeConfigParser(allow_no_value=True)
        else:
            parser = ConfigParser.SafeConfigParser()

        # Set to preserve Case
        parser.optionxform = str
        args = {}

        try:
            parser.read(self.config_file)
            for name, value in parser.items(section):
                name = name.encode('utf8')

                if any([value == 'False', value == 'false']):
                    args[name] = False
                elif any([value == 'True', value == 'true']):
                    args[name] = True
                else:
                    args[name] = value

        except Exception:
            return {}
        else:
            return args


def logger_setup(name, debug):
    """Setup logging for your application

    :param name: ``str``
    :return: ``object``
    """

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s:%(levelname)s => %(message)s'
    )

    log = logging.getLogger(name)

    filehandler = handlers.RotatingFileHandler(
        filename=return_logfile(filename='%s.log' % name),
        maxBytes=51200000,
        backupCount=5
    )

    streamhandler = logging.StreamHandler()

    if debug is True:
        log.setLevel(logging.DEBUG)
        filehandler.setLevel(logging.DEBUG)
        streamhandler.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
        filehandler.setLevel(logging.INFO)
        streamhandler.setLevel(logging.INFO)

    streamhandler.setFormatter(formatter)
    filehandler.setFormatter(formatter)

    log.addHandler(streamhandler)
    log.addHandler(filehandler)

    return log


def return_logfile(filename):
    """Return a path for logging file.

    IF '/var/log/' does not exist, or you don't have write permissions to
    '/var/log/' the log file will be in your working directory
    Check for ROOT user if not log to working directory.

    :param filename: ``str``
    :return: ``str``
    """

    if os.path.isfile(filename):
        return filename
    else:
        user = os.getuid()
        log_loc = '/var/log'
        if not user == 0:
            return os.path.join(HOME, filename)
        else:
            return os.path.join(log_loc, filename)


def exit_failure(msg):
    """On failure log error and exit 1."""
    LOG.error(msg)
    raise SystemExit(msg)


def get_config():
    """Return a string with the git creds.

    From the local configuration file load the git creds.
    """

    sys_config = ConfigurationSetup()
    irc_args = sys_config.config_args(section='irc')
    LOG.debug(irc_args)

    git_repos = sys_config.config_args(section='git_repo')
    LOG.debug(git_repos)

    return irc_args, git_repos


def process_hooks(hook_list, irc_data, git_hook_path, git_headers,
                  git_event_data, git_repo, irc_hook=False):
    """Iterate through the identified hooks and attempt to find IRC hooks.

    If this process does not find a predefined IRC hook it will attempt to
    fix the repository and setup an IRC hook for our application.

    :param hook_list: ``list``
    :param irc_data:  ``dict``
    :param git_hook_path: ``dict``
    :param git_headers: ``dict``
    :param git_event_data: ``dict``
    :param git_repo: ``dict``
    :param irc_hook: ``bol``
    """
    for hook in hook_list:
        if isinstance(hook, dict) and hook.get('name') == 'irc':
            irc_hook = True
            # Make sure irc_hook is configured for pull_req
            hook_events = hook['events']
            LOG.debug(
                'Found Events for [ %s ] : %s', git_repo['name'], hook_events
            )
            LOG.debug('webhook data in git %s', json.dumps(hook, indent=2))
            if 'pull_request' not in hook_events:
                LOG.warn(
                    'IRC Hook not configured for [ pull_req ]'
                    ' Attempting to FIXERATING'
                )
                resp, _content = HTTP.request(
                    hook['url'],
                    'PATCH',
                    headers=git_headers,
                    body=json.dumps(git_event_data)
                )
                if resp.status != 200:
                    LOG.error(
                        'FAILED TO UPDATE IRC HOOK FOR %s' % git_repo['name']
                    )
            else:
                hook_config = hook['config']
                if hook['active'] is not True:
                    LOG.warn('Hook not active')
                    _update_hook(
                        git_hook_path,
                        git_headers,
                        irc_data,
                        git_repo
                    )
                elif hook['events'] != git_event_data['events']:
                    LOG.warn('Events out of sync')
                    _update_hook(
                        git_hook_path,
                        git_headers,
                        irc_data,
                        git_repo
                    )
                else:
                    try:
                        for key, value in irc_data['config'].items():
                            if value != hook_config[key]:
                                LOG.warn('Key [ %s ] not set correctly', key)
                                _update_hook(
                                    git_hook_path,
                                    git_headers,
                                    irc_data,
                                    git_repo
                                )
                    except KeyError as exp:
                        LOG.warn(
                            'Configuration key [ %s ] seems to be missing', exp
                        )
                        _update_hook(
                            git_hook_path,
                            git_headers,
                            irc_data,
                            git_repo
                        )

    if not irc_hook:
        LOG.info(
            'Repo [ %s ] does not have IRC hook configured'
            ' CREATERATING a new hook.' % git_repo['name']
        )
        resp, _content = HTTP.request(
            git_hook_path,
            'POST',
            headers=git_headers,
            body=json.dumps(irc_data)
        )
        if resp.status != 201:
            LOG.error('FAILED TO ADD IRC HOOK FOR [ %s ]' % git_repo['name'])


def _update_hook(git_hook_path, git_headers, irc_data, git_repo):
    LOG.warn(
        'IRC hook is out of sync from known good config, UPDATERATING.'
    )
    response, update_content = HTTP.request(
        git_hook_path,
        'POST',
        headers=git_headers,
        body=json.dumps(irc_data)
    )
    if response.status >= 300:
        LOG.error(
            'FAILED TO ADD/MODIFY IRC HOOK FOR [ %s ] RETURN CODE [ %s ]',
            git_repo['name'], response.status
        )


def irc_json_data(irc_data):
    """Return a dict of the IRC configuration data.

    :param irc_data: ``dict``
    :return: ``dict``
    """
    data = {
        'name': irc_data.get('name', 'irc'),
        'active': irc_data.get('active', False)
    }

    config_data = [
        ('server', irc_data.get('server')),
        ('port', irc_data.get('port', '6667')),
        ('room', irc_data.get('room')),
        ('nick', irc_data.get('nick')),
        ('branch_regexes', irc_data.get('branch_regexes')),
        ('nickserv_password', irc_data.get('nickserv_password')),
        ('password', irc_data.get('password')),
        ('ssl', irc_data.get('ssl')),
        ('message_without_join', irc_data.get('message_without_join')),
        ('notice', irc_data.get('notice')),
        ('no_colors', irc_data.get('no_colors')),
        ('long_url', irc_data.get('long_url'))
    ]

    build_config_data = [
        (key, value) for key, value in config_data if value is not None
    ]

    data['config'] = dict(build_config_data)
    return data


def get_repos(path, git_path, api_uri, headers):
    """Return a list of repositories from the provided github api.

    :param path: ``str``
    :param git_path: ``str``
    :param api_uri: ``str``
    :param headers: ``dict``
    :return: ``list``
    """
    response, content = HTTP.request(path, 'HEAD', headers=headers)

    if 'link' in response:
        repo_content = []
        links = response['link'].split(',')
        pages = [i.replace(' ', '') for i in links if 'last' in i]
        page_link = pages[0].split(';')[0]
        page_link = page_link.strip('>').strip('<')
        page_link = page_link.split('=')
        page_num = int(page_link[-1])
        for page in range(0, page_num):
            git_page_number = page + 1
            req_path = git_path % (api_uri, git_page_number)
            response, content = HTTP.request(req_path, 'GET', headers=headers)
            for repo in json.loads(content):
                repo_content.append(repo)
        else:
            return repo_content
    else:
        response, content = HTTP.request(path, 'GET', headers=headers)
        return json.loads(content)


def process_repos(repo_content, headers, irc_config_data, configured_events):
    """Iterate through the repos and ensure the IRC triggers are setup.

    :param repo_content: ``list``
    :param headers: ``dict``
    :param irc_config_data: ``dict``
    :param configured_events: ``dict``
    """
    for repo in repo_content:
        # Update all of the IRC data with our configured events
        irc_config_data.update(configured_events)

        LOG.info('Fetching hooks for repo: %s' % repo['name'])
        hook_path = '%s/hooks' % repo['url']
        response, content = HTTP.request(hook_path, 'GET', headers=headers)

        process_hooks(
            hook_list=json.loads(content),
            irc_data=irc_config_data,
            git_hook_path=hook_path,
            git_headers=headers,
            git_event_data=configured_events,
            git_repo=repo
        )


def main():
    """Run the main application."""
    # Get all of the configuration options from our configuration file.
    irc_args, git_repos = get_config()

    # Iterate through the repos and make sure the IRC notifier is working
    for git_repo in git_repos.keys():
        username, password, api_uri = git_repos[git_repo].split('||')

        # load and encode the git creds for API access
        git_creds = '%s:%s' % (username, password)
        git_creds = base64.encodestring(git_creds)
        headers = {
            'Authorization': 'Basic %s' % git_creds
        }

        # Load all of the repositories
        LOG.info('Grabbing all repos from %s' % api_uri)
        git_path = '%s/repos?page=%s'
        repo_content = get_repos(
            path=git_path % (api_uri, 1),
            git_path=git_path,
            api_uri=api_uri,
            headers=headers
        )
        LOG.info('Found [ %s ] repositories', len(repo_content))

        # Get the IRC data from config and format into a dict
        irc_config_data = irc_json_data(irc_data=irc_args)

        configured_events = {
            'events': irc_args.get('events', '').split(',')
        }
        process_repos(
            repo_content=repo_content,
            headers=headers,
            irc_config_data=irc_config_data,
            configured_events=configured_events
        )


APPNAME = 'jenkins_notify'
HOME = os.getenv('HOME')
HTTP = httplib2.Http()

if len(sys.argv) > 1 and sys.argv[1] == '--debug':
    DEBUG = True
elif len(sys.argv) > 1 and sys.argv[1] == '--help':
    print('Usage: %s [--debug]' % sys.argv[0])
    sys.exit(0)
else:
    DEBUG = False

logger_setup(name=APPNAME, debug=DEBUG)
LOG = logging.getLogger(APPNAME)


if __name__ == '__main__':
    main()
