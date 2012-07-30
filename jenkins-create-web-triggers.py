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

path = "https://api.github.com/orgs/rcbops-cookbooks/repos"

response, content = http.request(path, 'GET', headers=headers)

push_hook_url = "http://build.monkeypuppetlabs.com/gitpost/posthook/"
push_data = {"events": [ "push" ]}
push_config_data = {
    "name": "web",
    "active": True,
    "config": {
        "url": push_hook_url
    }
}

pull_hook_url = "http://build.monkeypuppetlabs.com/gitpost/pullreq/"
pull_data = {"events": [ "pull_request" ]}
pull_config_data = {
    "name": "web",
    "active": True,
    "config": {
        "url": push_hook_url
    }
}

repo_list = json.loads(content)
for repo in repo_list:
    print "Fetching hooks for repo: %s" % repo['name']
    hook_path = "%s/hooks" % repo['url']
    response, content = http.request(hook_path, 'GET', headers=headers)

    hook_list = json.loads(content)
    #pprint(hook_list)

    has_push_hook = False
    has_pull_hook = False

    for hook in hook_list:
#        # pprint(hook)
        if hook['name'] == "web" and hook['config']['url'] == push_hook_url:
            has_push_hook = True
            # Make sure push hook is config'd for push event
            if "push" not in hook['events']:
                print ".. Push Hook not configured for push events.. FIXING"
                response, content = http.request(hook['url'], 'PATCH', headers=headers, body=json.dumps(push_data)) 
                if response.status != 200:
                    print ".... FAILED TO UPDATE PUSH HOOK FOR %s" % (repo['name'])
                    sys.exit(1)
            else:
                print ".. Push Hook is configured for push events"
        if hook['name'] == "web" and hook['config']['url'] == pull_hook_url:
            has_pull_hook = True
            # Make sure pull hook is config'd for pull_request event
            if "pull_request" not in hook['events']:
                print ".. Pull_Request Hook not configured for pull_request events.. FIXING"
                response, content = http.request(hook['url'], 'PATCH', headers=headers, body=json.dumps(pull_data)) 
                if response.status != 200:
                    print ".... FAILED TO UPDATE PULL_REQUEST HOOK FOR %s" % (repo['name'])
                    sys.exit(1)
            else:
                print ".. Pull_Request Hook is configured for pull_request events"

    if not has_push_hook:
        print ".. %s does not have PUSH hook configured.... FIXING" % repo['name']
        response, content = http.request(hook_path, 'POST', headers=headers, body=json.dumps(push_config_data))
        if response.status != 201:
            print ".... FAILED TO ADD PUSH HOOK FOR %s" % (repo['name'])
            sys.exit(1)
    if not has_pull_hook:
        print ".. %s does not have PULL hook configured.... FIXING" % repo['name']
        response, content = http.request(hook_path, 'POST', headers=headers, body=json.dumps(pull_config_data))
        if response.status != 201:
            print ".... FAILED TO ADD PULL_REQUEST HOOK FOR %s" % (repo['name'])
            sys.exit(1)

sys.exit(0)
