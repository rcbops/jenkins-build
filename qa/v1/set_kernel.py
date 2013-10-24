import argh
import gevent
from modules.rpcsqa_helper import rpcsqa_helper


def main():
    rpcsqa = rpcsqa_helper("198.101.133.3")
    nodes = rpcsqa.node_search("name:*centos*")
    events = [gevent.spawn(rpcsqa.set_kernel, node) for node in nodes
              if 'kernel' in node.override]
    gevent.joinall(events)

parser = argh.ArghParser()
parser.add_commands([main])

if __name__ == '__main__':
    parser.dispatch()
