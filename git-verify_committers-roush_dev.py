#!/usr/bin/env python

import base64
import ConfigParser
import httplib2
import json
import os
import sys

from pprint import pprint
from io import StringIO


def _build_headers(user, passwd):
    auth = base64.encodestring("%s:%s" % (user, passwd))
    ret = {
        'Authorization': 'Basic ' + auth
    }
    return ret

config_file = ".rcbjenkins-git-creds"
file_path = os.path.abspath(os.path.join(os.getenv("HOME"), config_file))
config = StringIO(u'[default]\n%s' % open(file_path).read())
parser = ConfigParser.ConfigParser()
parser.readfp(config)
username, password = parser.get('default', 'user').split(':')

# httplib2.debuglevel = 4
http = httplib2.Http()
headers = _build_headers(username, password)

# base = "https://api.github.com"
# base = "https://developer.github.com"
base = "https://api.github.com"
team_path = base + "/orgs/rcbops/teams"

# Build a dict out of the teams for the rcbops organization
response, content = http.request(team_path, 'GET', headers=headers)
teams = dict((x['name'],x['id']) for x in json.loads(content))

print 'Looking up members for team: roush-devs'

# Build a list out of the users for the roush-devs team
member_path = base + '/teams/%s/members' % (teams['roush-devs'])
response, content = http.request(member_path, 'GET', headers=headers)
member_list = [x['login'] for x in json.loads(content)]
pprint(member_list)

# Grab the environment variables
GIT_USER = os.environ.get('GIT_USER')
GIT_PULL_URL = os.environ.get('GIT_PULL_URL')
GIT_COMMENT_URL = os.environ.get('GIT_COMMENT_URL')

if GIT_USER is None:
    print "Environment variable GIT_USER not found, aborting."
    sys.exit(1)

if GIT_PULL_URL is None:
    print "Environment variable GIT_PULL_URL not found, aborting."
    sys.exit(1)

if GIT_COMMENT_URL is None:
    print "Environment variable GIT_COMMENT_URL not found, aborting."
    sys.exit(1)

# Check if the user submitting the pull-req is part of the team
if GIT_USER in member_list:
# http://developer.github.com/v3/pulls/#merge-a-pull-request-merge-buttontrade
    msg = 'Merged automatically by jenkins after successful gate test'
    body = {'commit_message': msg}
    response, content = http.request(GIT_PULL_URL + '/merge', 'PUT',
                                     headers=headers, body=body)
    if response.status == 200:
        print "Merged successfully."
        sys.exit(0)
    elif response.status == 405:
        print "Unable to merge, most likely needs to be rebased."
        # Probably should post a comment back to github
        sys.exit(1)
    else:
        # unexpected failure
        print "Received an unexpected error while attempting to merge."
        print ".... Status Code: %s" % response.status
        sys.exit(1)
else:
# http://developer.github.com/v3/issues/comments/#create-a-comment
    msg = 'Not automatically merged, %s is not an approved committer. ' \
          'Please leave pull request open for review and manual merge ' \
          'by a core team member.' % (GIT_USER)
    body = {'body': msg}
    response, content = http.request(GIT_COMMENT_URL, 'POST',
                                     headers=headers, body=body)
    sys.exit(0)
