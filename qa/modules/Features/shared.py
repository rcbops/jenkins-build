def remove_chef(node):
    """ Removes chef from the given node
    """

    if node.os == "precise":
        commands = ["apt-get remove --purge -y chef",
                    "rm -rf /etc/chef"]
    if node.os in ["centos", "rhel"]:
        commands = ["yum remove -y chef",
                    "rm -rf /etc/chef /var/chef"]

    command = "; ".join(commands)

    return node.run_cmd(command, quiet=True)
