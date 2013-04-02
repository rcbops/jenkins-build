#!/usr/bin/env python

import base64
import ConfigParser
import httplib2
import json
import os
import re
import sys

# from pprint import pprint
from io import StringIO


def _build_headers(user, passwd):
    auth = base64.encodestring("%s:%s" % (user, passwd))
    ret = {
        'Authorization': 'Basic ' + auth
    }
    return ret


def _check_for_rallyid(msg):
    pattern = '[Ii]ssue\s[A-Z][A-Z][0-9]{1,4}'
    match = re.match(pattern, msg)
    if match is not None:
        return match.group(0)
    else:
        return None


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
teams = dict((x['name'], x['id']) for x in json.loads(content))

# Build a list out of the users for the roush-devs team
member_path = base + '/teams/%s/members' % (teams['rcbops-devs'])
response, content = http.request(member_path, 'GET', headers=headers)
member_list = [x['login'] for x in json.loads(content)]

# Grab the environment variables
GIT_USER = os.environ.get('GIT_USER')
GIT_PULL_URL = os.environ.get('GIT_PULL_URL')
GIT_COMMENT_URL = os.environ.get('GIT_COMMENT_URL')
GIT_COMMIT_MSG_BODY = os.environ.get('GIT_COMMIT_MSG_BODY', '')

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
    # Submitter is a core member, lets make sure the commit msg is ok
    rallyid = _check_for_rallyid(GIT_COMMIT_MSG_BODY)
    if rallyid is not None:
        # TODO(shep): should probably update the rallyid here
        msg = 'Merged automatically by jenkins after successful gate test'
        body = {'commit_message': msg}
        response, content = http.request(GIT_PULL_URL + '/merge', 'PUT',
                                         headers=headers,
                                         body=json.dumps(body))
        # http://developer.github.com/v3/pulls/#merge-a-pull-\
        #   request-merge-buttontrade
        if response.status == 200:
            print ".... Merged successfully."
            sys.exit(0)
        elif response.status == 405:
            print ".... Unable to merge, most likely needs to be rebased."
            # Probably should post a comment back to github
            sys.exit(1)
        else:
            # unexpected failure
            print ".... Received an unexpected error when attempting merge."
            print "........ Status Code: %s" % response.status
            sys.exit(1)
    else:
        # Commit message does not contain a RallyID
        msg = 'Commit message does not contain a RallyID. ' \
              'Please update the body of the commit message with '\
              '"Issue AA1111", where AA1111 is a valid RallyID.'
        body = {'body': msg}
        response, content = http.request(GIT_COMMENT_URL,
                                         'POST', headers=headers,
                                         body=json.dumps(body))
        print ".... Not Merged, commit msg did not have RallyID."
        sys.exit(0)

else:
# http://developer.github.com/v3/issues/comments/#create-a-comment
    msg = 'Not automatically merged, %s is not an approved committer. ' \
          'Please leave pull request open for review and manual merge ' \
          'by a core team member.' % (GIT_USER)
    body = {'body': msg}
    response, content = http.request(GIT_COMMENT_URL, 'POST',
                                     headers=headers, body=json.dumps(body))
    print ".... Not Merged, non-core submitter."
    sys.exit(0)
