#!/usr/bin/env python

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        description='Maintain chef release manifest')

    parser.add_argument('manifest', type=argparse.FileType('r+'),
                        help='the manifest file to maintain')

    parser.add_argument('version', type=str,
                        help='the version being recorded inthe manifest')

    parser.add_argument('url', type=str,
                        help='the location of the versions tarball download')
    try:
        args = parser.parse_args(sys.argv[1:])
        source = args.manifest

        manifest = json.load(source)

        add_version(manifest, args.version, args.url)

        source.seek(0)
        source.write(json.dumps(manifest, sort_keys=True, indent=2))
        source.truncate()
        source.close()

    except IOError as e:
        print >> sys.stderr, e


def add_version(manifest, version, url):
    manifest['current'] = version

    for existing_version in manifest['versions']:
        if version in existing_version:
            existing_version[version] = url
            return

    new_version = {}
    new_version[version] = url
    manifest['versions'].append(new_version)
    return

if __name__ == '__main__':
    main()
