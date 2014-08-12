# pipecount.py
#

from pipe2py import util


def pipe_count(context=None, _INPUT=None, conf=None, **kwargs):
    """Count the number of items in a feed and yields it forever.

    Keyword arguments:
    context -- pipeline context
    _INPUT -- source generator
    kwargs -- other inputs, e.g. to feed terminals for rule values
    conf:

    Yields (_OUTPUT):
    a count on the number of items in the feed
    """

    count = sum(1 for item in _INPUT)
    # todo: check all operators (not placeable in loops)
    # read _INPUT once only & then serve - in case they serve multiple further
    # steps
    while True:
        yield count
