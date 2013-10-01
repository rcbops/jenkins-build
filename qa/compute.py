#! /usr/bin/env python
import sys
import json
import argh
import traceback
from modules.rpcsqa_helper import rpcsqa_helper
from chef import Environment
from modules.Builds import ChefBuild, ChefDeploymentBuild, Builds


@argh.arg('-f', "--features", nargs="+", type=str)
def build(name="autotest", os="precise", branch="4.1.2", computes=1,
          remote_chef=True, razor_ip="198.101.133.3", features=[]):
    features = features or ['default']
    branch_name = "grizzly"
    if branch in ["3.0.0", "3.0.1", "3.1.0", "folsom"]:
        branch_name = "folsom"

    # Setup the helper class ( Chef )
    qa = rpcsqa_helper()

    #Prepare environment
    env = qa.prepare_environment(name,
                                 os,
                                 branch_name,
                                 features,
                                 branch)
    print json.dumps(Environment(env).override_attributes, indent=4)

    qa.enable_razor(razor_ip)
    print "Starting baremetal...."
    print "Removing broker fails"
    qa.remove_broker_fail("qa-%s-pool" % os)
    print "Interfacing nodes that need it"
    qa.interface_physical_nodes(os)
    try:
        print "Cleaning up old environment (deleting nodes) "
        # Clean up the current running environment (delete old servers)
        qa.cleanup_environment(env)
    except Exception, e:
        print e
        qa.cleanup_environment(env)
        sys.exit(1)

    #####################
    #   BUILD
    #####################

    build = ChefDeploymentBuild(env, is_remote=remote_chef)
    try:
        if "openldap" in features:
            node = qa.get_razor_node(os, env)
            post_commands = ['ldapadd -x -D "cn=admin,dc=rcb,dc=me" '
                             '-wostackdemo -f /root/base.ldif',
                             {'function': "update_openldap_environment",
                              'kwargs': {'env': 'environment'}}]
            build.append(ChefBuild(node.name, Builds.directory_server, qa,
                                   branch, env, api=build.api,
                                   post_commands=post_commands))

        if remote_chef:
            node = qa.get_razor_node(os, env)
            pre_commands = [{'function': "build_chef_server",
                             'kwargs': {'cookbooks': 'cookbooks',
                                        'env': 'environment',
                                        'api': 'api'}}]
            build.append(ChefBuild(node.name, Builds.chef_server, qa,
                                   branch, env, api=build.api,
                                   pre_commands=pre_commands))

        if "neutron" in features:
            node = qa.get_razor_node(os, env)
            build.append(ChefBuild(node.name, Builds.neutron, qa,
                                   branch, env, api=build.api,
                                   post_commands=post_commands))

        if "ha" in features:
            pre_commands = [{'function': "prepare_cinder",
                             'kwargs': {'name': 'name', 'api': 'api'}}]
            node = qa.get_razor_node(os, env)
            build.append(ChefBuild(node.name, Builds.controller1, qa,
                                   branch, env, api=build.api,
                                   pre_commands=pre_commands))

            node = qa.get_razor_node(os, env)
            build.append(ChefBuild(node.name, Builds.controller2, qa,
                                   branch, env, api=build.api))

        else:
            pre_commands = [{'function': "prepare_cinder",
                             'kwargs': {'name': 'name', 'api': 'api'}}]
            node = qa.get_razor_node(os, env)
            build.append(ChefBuild(node.name, Builds.controller1, qa,
                                   branch, env, api=build.api,
                                   pre_commands=pre_commands))

        for n in xrange(computes):
            node = qa.get_razor_node(os, env)
            build.append(ChefBuild(node.name, Builds.compute, qa,
                                   branch, env, api=build.api))

    except IndexError, e:
        print "*** Error: Not enough nodes for your setup"
        qa.cleanup_environment(env)
        qa.delete_environment(env)
        sys.exit(1)

    print "#" * 70
    success = True

    try:
        print str(build)
        build.build()
    except Exception, e:
        print traceback.print_exc()
        sys.exit(1)

    if success:
        print "Welcome to the cloud..."
        print str(build)
    else:
        print "!!## -- Failed to build OpenStack Cloud -- ##!!"


@argh.arg('-f', "--features", nargs="+", type=str)
def destroy(name="autotest", os="precise", branch="grizzly",
            razor_ip="198.101.133.3", features=[]):
    features = features or ['default']
    print "Destroying your cloud now!!!"
    qa = rpcsqa_helper()
    env = qa.prepare_environment(name,
                                 os,
                                 branch,
                                 features,
                                 branch)
    qa.cleanup_environment(env)
    qa.delete_environment(env)

if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy])
    parser.dispatch()
