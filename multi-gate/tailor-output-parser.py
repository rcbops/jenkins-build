#!/usr/bin/python

import yaml
import sys
import os

f = sys.stdin
dataMap = yaml.safe_load(sys.stdin)

for x in dataMap:
  file_name =  os.path.join(os.path.basename(os.getcwd()),os.path.relpath(x,os.getcwd()))
  for y in dataMap[x]:
    print "%s : %s : %d : %s : %s" % (file_name, y[':level'][1:],
                                      y[':line'], y[':type'], y[':message'])
