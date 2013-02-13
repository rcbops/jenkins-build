#!/usr/bin/env python

from optparse import OptionParser
import json
import sys


def main():
    usage = "usage: %prog manifest version url"
    parser = OptionParser(usage)

    try:
        (options, args) = parser.parse_args(sys.argv[1:])

        if len(args) != 3:
            parser.error("manifest, version and url are required")

        source = open(args[0], 'r+')

        manifest = json.load(source)

        add_version(manifest, args[1], args[2])

        source.seek(0)
        source.write(json.dumps(manifest, sort_keys=True, indent=2))
        source.truncate()
        source.close()

    except IOError as e:
        print >> sys.stderr, e


def add_version(manifest, version, url):
    manifest['current'] = version
    manifest['versions'][version] = {"url": url}

    return

if __name__ == '__main__':
    main()
