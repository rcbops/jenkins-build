#!/usr/bin/env python

import base64
import ConfigParser
import httplib2
import json
import os
import sys

from pprint import pprint
from io import StringIO

config_file = ".rcbjenkins-git-creds"
file_path = os.path.abspath(os.path.join(os.getenv("HOME"), config_file))
config = StringIO(u'[default]\n%s' % open(file_path).read())
parser = ConfigParser.ConfigParser()
parser.readfp(config)
username, password = parser.get('default', 'user').split(':')

# httplib2.debuglevel = 4
http = httplib2.Http()
auth = base64.encodestring("%s:%s" % (username, password))
headers = {
  'Authorization': 'Basic ' + auth
}

print "Grabbing all repos from https://github.com/rcbops-cookbooks"

# github paginates, this will be an issue once we have ~100 repos
path = "https://api.github.com/orgs/rcbops-cookbooks/repos?per_page=100"

response, content = http.request(path, 'GET', headers=headers)

irc_config_data = {
    "name": "irc",
    "active": True,
    "config": {
        "branch_regexes": "",
        "long_url": "1",
        "no_colors": "1",
        "nick": "gitcheffoo",
        "nickserv_password": "secrete",
        "password": "",
        "port": "7000",
        "ssl": "1",
        "room": "#rcbops",
        "server": "irc.freenode.net"}
}

event_data = {"events": [ "push", "issues", "pull_request", "issue_comment" ]}

repo_list = json.loads(content)
for repo in repo_list:
    print "Fetching hooks for repo: %s" % repo['name']
    hook_path = "%s/hooks" % repo['url']
    response, content = http.request(hook_path, 'GET', headers=headers)

    hook_list = json.loads(content)
    has_irc_hook = False
    for hook in hook_list:
        # pprint(hook)
        if 'name' in hook and hook['name'] == "irc":
            has_irc_hook = True
            # Make sure irc_hook is config'd for pull_req
            if "pull_request" not in hook['events']:
                print ".. IRC Hook not configured for pull_req... FIXING"
                response, content = http.request(hook['url'], 'PATCH', headers=headers, body=json.dumps(event_data))
                if response.status != 200:
                    print ".... FAILED TO UPDATE IRC HOOK FOR %s" % (repo['name'])
                    sys.exit(1)
            else:
                print ".. IRC hook is configured for pull_req"
    if not has_irc_hook:
        print ".. %s does not have IRC hook configured.... FIXING" % repo['name']
        response, content = http.request(hook_path, 'POST', headers=headers, body=json.dumps(irc_config_data))
        if response.status != 201:
            print ".... FAILED TO ADD IRC HOOK FOR %s" % (repo['name'])
            sys.exit(1)

sys.exit(0)
