import argh
import gevent
from modules.rpcsqa_helper import rpcsqa_helper


def main():
    rpcsqa = rpcsqa_helper("198.101.133.3")
    nodes = rpcsqa.node_search("name:*centos*")
    events = [gevent.spawn(rpcsqa.set_kernel, node) for node in nodes
              if 'kernel' in node]
    gevent.joinall(events)

argh.dispatch(main)
