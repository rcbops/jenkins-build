#!/usr/bin/env python

from optparse import OptionParser
import json
import sys
import datetime


def main():
    usage = "usage: %prog manifest version url"
    parser = OptionParser(usage)

    try:
        (options, args) = parser.parse_args(sys.argv[1:])

        if len(args) != 4:
            parser.error("manifest, version, url, and md5 are required")

        source = open(args[0], 'r+')

        manifest = json.load(source)

        add_version(manifest, args[1], args[2], args[3])

        source.seek(0)
        source.write(json.dumps(manifest, sort_keys=True, indent=2))
        source.truncate()
        source.close()

    except IOError as e:
        print >> sys.stderr, e


def add_version(manifest, version, url, md5):
    manifest['current'] = version
    manifest['versions'][version] = {
        "url": url,
        "md5": md5,
        "updated": datetime.datetime.utcnow().isoformat()
    }

    return

if __name__ == '__main__':
    main()
