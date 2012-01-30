#!/usr/bin/env python

import os
import sys
from subprocess import call

# this should probably be pulled from the conf/distributions, but it can't be different across
# components anyway, so meh.
#
SIGNING_KEY='F87CBDE0'
BASE_DIR='/srv/packages'

class ReleaseInfo:
    def __init__(self):
        self.info={}
        self.order=[]
        pass

    def load(self, path):
        with open(path) as f:
            lastheader=''

            for line in f:
                line = line.rstrip()
                if line.startswith(' '):
                    # continuation
                    self.info[lastheader] = self.info[lastheader] + '\n' + line
                else:
                    (header, rest) = line.split(':',1)

                    header = header.strip()
                    rest = rest.strip()
                    
                    lastheader = header

                    self.order.append(header)
                    self.info[header] = rest

    def save(self, fp):
        for header in self.order:
            fp.write('%s: %s\n' % (header, self.info[header]))

    def dump(self):
        self.save(sys.stdout)

    def get_info(self):
        return self.info

    def get_order(self):
        return self.order

    def merge(self, other):
        otherinfo = other.get_info()

        if self.info == {}:
            self.info = otherinfo
            self.order = other.get_order()
        else:
            self.info['Components'] = ' '.join(merge_arrays(self.info['Components'].split(' '), 
                                                            otherinfo['Components'].split(' ')))

            self.info['Architectures'] = ' '.join(merge_arrays(self.info['Architectures'].split(' '), 
                                                               otherinfo['Architectures'].split(' ')))
            for param in [ 'MD5Sum', 'SHA1', 'SHA256' ]:
                self.info[param] = self.info[param] + otherinfo[param]

def merge_arrays(first, second):
    resulting_list = first + [i for i in second if i not in first ]
    return resulting_list
        
if len(sys.argv) > 1:
    BASE_DIR=sys.argv[1]

component_list=[ component for component in os.listdir(BASE_DIR) if component.find("-") >= 0 ]
merge_targets = {}

for component in component_list:
    codename_list=[ codename for codename in os.listdir(os.path.join(BASE_DIR, component, 'dists')) ]
    for codename in codename_list:
        # grab the release info
        info = ReleaseInfo()
        info.load(os.path.join(BASE_DIR, component, 'dists', codename, 'Release'))

        if not codename in merge_targets:
            merge_targets[codename] = []

        merge_targets[codename].append(info)

for codename in merge_targets:
    # natty, oneiric, etc
    merged_info = ReleaseInfo()

    for info in merge_targets[codename]:
        merged_info.merge(info)

    if not os.path.exists(os.path.join(BASE_DIR, 'dists')):
        os.mkdir(os.path.join(BASE_DIR, 'dists'))

    if not os.path.exists(os.path.join(BASE_DIR, 'dists', codename)):
        os.mkdir(os.path.join(BASE_DIR, 'dists', codename))

    with open(os.path.join(BASE_DIR, 'dists', codename, 'Release'), 'w') as f:
        merged_info.save(f)

    if os.path.exists(os.path.join(BASE_DIR, 'dists', codename, 'Release.gpg')):
        os.remove(os.path.join(BASE_DIR, 'dists', codename, 'Release.gpg'))

    if os.path.exists(os.path.join(BASE_DIR, 'dists', codename, 'InRelease')):
        os.remove(os.path.join(BASE_DIR, 'dists', codename, 'InRelease'))

    call(['gpg','--detach-sign', '--armor', '--default-key',
          SIGNING_KEY, '--output',
          os.path.join(BASE_DIR, 'dists', codename, 'Release.gpg'),
          os.path.join(BASE_DIR, 'dists', codename, 'Release') ])

    call(['gpg','--clearsign', '--default-key',
          SIGNING_KEY, '--output',
          os.path.join(BASE_DIR, 'dists', codename, 'InRelease'),
          os.path.join(BASE_DIR, 'dists', codename, 'Release') ])

                           
                                                                        
                                                                        

