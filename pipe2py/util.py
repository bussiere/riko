"""Utility functions"""
# vim: sw=4:ts=4:expandtab

import string

from urllib2 import quote
from operator import itemgetter

DATE_FORMAT = "%m/%d/%Y"
ALTERNATIVE_DATE_FORMATS = (
    "%m-%d-%Y",
    "%m/%d/%y",
    "%m/%d/%Y",
    "%m-%d-%y",
    "%Y-%m-%dt%H:%M:%Sz",
    # todo more: whatever Yahoo can accept
)

DATETIME_FORMAT = DATE_FORMAT + " %H:%M:%S"
URL_SAFE = "%/:=&?~#+!$,;'@()*[]"


def pythonise(id):
    """Return a Python-friendly id"""
    if id:
        id = id.replace("-", "_").replace(":", "_")

        if id[0] in string.digits:
            id = "_" + id

        return id.encode('ascii')


def xml_to_dict(element):
    """Convert xml into dict"""
    i = dict(element.items())
    if element.getchildren():
        if element.text and element.text.strip():
            i['content'] = element.text
        for child in element.getchildren():
            if str(child)[:4] == '<!--':
                continue
            tag = child.tag.split('}', 1)[-1]
            i[tag] = xml_to_dict(child)
    else:
        if not i.keys():
            if element.text and element.text.strip():
                i = element.text
        else:
            if element.text and element.text.strip():
                i['content'] = element.text

    return i


def etree_to_pipes(element):
    """Convert ETree xml into dict imitating how Yahoo Pipes does it.

    todo: further investigate white space and multivalue handling
    """
    # start as a dict of attributes
    i = dict(element.items())
    if len(element):  # if element has child elements
        if element.text and element.text.strip():  # if element has text
            i['content'] = element.text

        for child in element:
            if str(child)[:4] == '<!--':
                continue
            tag = child.tag.split('}', 1)[-1]

            # process child recursively and append it to parent dict
            subtree = etree_to_pipes(child)
            content = i.get(tag)
            if content is None:
                content = subtree
            elif isinstance(content, list):
                content = content + [subtree]
            else:
                content = [content, subtree]
            i[tag] = content

            if child.tail and child.tail.strip():  # if text after child
                # append to text content of parent
                text = child.tail
                content = i.get('content')
                if content is None:
                    content = text
                elif isinstance(content, list):
                    content = content + [text]
                else:
                    content = [content, text]
                i['content'] = content
    else:  # element is leaf node
        if not i.keys():  # if element doesn't have attributes
            if element.text and element.text.strip():  # if element has text
                i = element.text
        else:  # element has attributes
            if element.text and element.text.strip():  # if element has text
                i['content'] = element.text

    return i


def get_subkey(subkey, item):
    """Return a value via a subkey reference
        Note: subkey values use dot notation and we map onto nested
            dictionaries, e.g. 'a.content' -> ['a']['content']
        Note: we first remove any trailing. (i.e.
            'item.loop:stringtokenizer.1.content.' should just match 'item.
            loop:stringtokenizer.1.content')
    """
    subtree = item
    for key in subkey.rstrip('.').split('.'):
        if hasattr(subtree, 'get') and key in subtree:
            subtree = subtree.get(key)
        elif (
            key.isdigit()
            and isinstance(subtree, list)
            and int(key) < len(subtree)
        ):
            subtree = subtree[int(key)]
        elif key == 'value' or key == 'content' or key == 'utime':
            subtree = subtree
        else:
            subtree = None

        # silently returns None if any part is not found
        # unless 'value' or 'utime' is the part in which case we return the
        # parent (to cope with y:id.value -> y:id and
        # item.endtime.utime -> item.endtime)
    return subtree


def get_value(_item, _loop_item=None, **kwargs):
    """Return either:
           a literal value
           a value via a terminal (then kwargs must contain the terminals)
           a value via a subkey reference (then _loop_item must be passed)
       Note: subkey values use dot notation and we map onto nested
       dictionaries, e.g. 'a.content' -> ['a']['content']
    """
    if 'value' in _item:  # simple value
        return _item['value']
    elif 'terminal' in _item:  # value fed in from another module
        return kwargs[pythonise(_item['terminal'])].next()
    elif 'subkey' in _item:  # reference to current loop item
        return get_subkey(_item['subkey'], _loop_item)


def set_value(item, key, value):
    """Set a key's value in the item
       Note: keys use dot notation and we map onto nested dictionaries, e.g.
       'a.content' -> ['a']['content']
    """
    reduce(lambda i, k: i.setdefault(k, {}), key.split('.')[:-1], item)[
        key.split('.')[-1]] = value


def del_value(item, key):
    """Remove a value (and its key) from the item
       Note: keys use dot notation and we map onto nested dictionaries, e.g. '
       a.content' -> ['a']['content']
    """
    ks = key.split('.')
    if ks[-1].isdigit():
        # if the sub-index looks like a number, then we're indexing into a list
        # so convert it to an integer
        # todo: this most likely only works for the last element of the subkey
        # todo: should make this more robust for the different subkey types,
        # todo: like get_subkey above is
        ks[-1] = int(ks[-1])
    try:
        del reduce(lambda i, k: i.get(k), [item] + ks[:-1])[ks[-1]]
    except:
        # if an error occurs, don't delete anything
        pass


def multikeysort(items, columns):
    """Sorts a list of items by the columns

       (columns precedeed with a '-' will sort descending)
    """
    comparers = [
        (
            (itemgetter(col[1:].strip()), -1) if col.startswith('-') else (
                itemgetter(col.strip()), 1
            )
        ) for col in columns
    ]

    def comparer(left, right):
        for fn, mult in comparers:
            try:
                result = cmp(fn(left), fn(right))
            except KeyError:
                # todo: perhaps care more if only one side has the missing key
                result = 0
            except TypeError:  # todo: handle bool better?
                # todo: perhaps care more if only one side has the missing key
                result = 0
            if result:
                return mult * result
        else:
            return 0
    return sorted(items, cmp=comparer)


def get_input(context, conf):
    """Gets a user parameter, either from the console or from an outer
        submodule/system

       Assumes conf has name, default, prompt and debug
    """
    name = conf['name']['value']
    default = conf['default']['value']
    prompt = conf['prompt']['value']
    # debug = conf['debug']['value']

    value = None

    if context.submodule:
        value = context.inputs.get(name, default)
    elif context.test:
        # we skip user interaction during tests
        # note: docs say debug is used, but doesn't seem to be
        value = default
    elif context.console:
        value = raw_input(
            prompt.encode('utf-8') + (
                " (default=%s) " % default.encode('utf-8')
            )
        )
        if value == "":
            value = default
    else:
        value = context.inputs.get(name, default)

    return value


def rreplace(s, find, replace, count=None):
    li = s.rsplit(find, count)
    return replace.join(li)


def url_quote(url):
    """Ensure url is valid"""
    try:
        return quote(url, safe=URL_SAFE)
    except KeyError:
        return quote(url.encode('utf-8'), safe=URL_SAFE)


def listize(item):
    return item if isinstance(item, list) else [item]
