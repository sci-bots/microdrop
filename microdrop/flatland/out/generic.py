import re

from flatland.out.util import parse_trool
from flatland.schema import Array, Boolean
from flatland.util import Maybe, to_pairs


__all__ = ('transform', 'Context')
_transforms = []
_default_context = {}
_auto_tags = {}
_id_invalid_re = re.compile(r'[^A-Za-z0-9_:.\-]')


def transform(tagname, attributes, contents, context, bind):
    """Transform tag *attributes* in-place & return transformed *contents*"""
    for fn in _transforms:
        contents = fn(tagname, attributes, contents, context, bind)
    return contents


class Context(object):
    """A stacked key/value mapping."""

    # These methods are public but undocumented.  For friendly, user-facing
    # versions, see the Generator subclass.

    def __init__(self):
        self._frames = [dict(_default_context)]

    def push(self, **options):
        # for this size dict & usage pattern, copying turns out to be cheaper
        # than directing __getitem__ down through a stack of sparse frames.
        self._frames.append(self._frames[-1].copy())
        try:
            self.update(**options)
        except KeyError:
            self.pop()
            raise

    def pop(self):
        if len(self._frames) == 1:
            raise RuntimeError("Can not pop() the base context frame.")
        self._frames.pop()

    def __getitem__(self, key):
        return self._frames[-1][key]

    def __setitem__(self, key, value):
        if key not in self:
            raise KeyError("%r not permitted in this %s" % (
                key, self.__class__.__name__))
        self._frames[-1][key] = value

    def __contains__(self, key):
        return key in self._frames[-1]

    def update(self, *iterable, **kwargs):
        if len(iterable):
            if len(iterable) > 1:
                raise TypeError(
                    "update expected at most 1 arguments, got %s" % (
                    len(iterable)))
            source = to_pairs(iterable[0])
            for key, value in source:
                self[key] = value
        for key, value in kwargs.iteritems():
            self[key.decode('ascii')] = value

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._frames[-1])


class Markup(unicode):
    """A unicode string of HTML markup that should not be escaped in output."""
    __slots__ = ()

    # Not a full featured implementation.

    def __html__(self):
        return self

_default_context['markup_wrapper'] = Markup


def transformer(name, tags):
    def decorator(fn):
        _transforms.append(fn)
        _auto_tags[name] = set(tags)
        return fn
    return decorator


def defaults(data):
    def decorator(fn):
        _default_context.update(data)
        return fn
    return decorator


@transformer(u'name', (u'input', u'button', u'select', u'textarea', u'form'))
@defaults({u'auto_name': True})
def transform_name(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_name', attributes, context)
    if not proceed or bind is None:
        return contents

    bound_name = bind.flattened_name()
    if not bound_name:
        return contents

    current = attributes.get(u'name', None)
    if forced or current is None and tagname in _auto_tags[u'name']:
        attributes[u'name'] = bound_name
    return contents


@transformer(u'value', (u'button', u'input', u'option', u'textarea'))
@defaults({u'auto_value': True})
def transform_value(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_value', attributes, context)
    # Abort on unbound tags.
    if not proceed or bind is None:
        return contents

    if not forced and tagname not in _auto_tags[u'value']:
        return contents

    if tagname == u'input':
        subtype = attributes.get(u'type', u'')
        if subtype in (u'radio', u'checkbox'):
            if subtype == u'checkbox':
                current = attributes.get(u'value')
                if current is None and isinstance(bind, Boolean):
                    attributes[u'value'] = current = bind.true
            else:
                current = attributes.get(u'value', u'')

            if isinstance(bind, Array):
                toggle = current in bind
            else:
                toggle = current == bind.u
            if toggle:
                attributes[u'checked'] = u'checked'
            else:
                attributes.pop(u'checked', None)
        elif subtype in (u'password', u'file', u'image'):
            if forced:
                attributes[u'value'] = bind.u
        else:
            current = attributes.get(u'value')
            if current is None or forced:
                attributes[u'value'] = bind.u
    elif tagname == u'option':
        current = attributes.get(u'value')
        if current is not None:
            value = current
        elif isinstance(contents, unicode):
            value = contents.strip()
        elif contents is None:
            value = u''
        else:
            value = contents
        if isinstance(bind, Array):
            toggle = value in bind
        else:
            toggle = bind.u == value
        if toggle:
            attributes[u'selected'] = u'selected'
        else:
            attributes.pop(u'selected', None)
    elif tagname == u'textarea':
        if contents is None or forced:
            return context['markup_wrapper'](_markup_escape(bind.u))
    else:
        current = attributes.get(u'value')
        if current is None or forced:
            attributes[u'value'] = bind.u
    return contents


@transformer(u'id', (u'input', u'button', u'select', u'textarea'))
@defaults({u'auto_domid': False, u'domid_format': u'f_%s'})
def transform_domid(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_domid', attributes, context)
    if not proceed:
        return contents

    current = attributes.get(u'id')
    if forced or current is None and tagname in _auto_tags[u'id']:
        raw_id = _generate_raw_domid(tagname, attributes, bind)
        if raw_id:
            fmt = context[u'domid_format']
            attributes[u'id'] = fmt % raw_id
    return contents


@transformer(u'for', (u'label',))
@defaults({u'auto_for': False})
def transform_for(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_for', attributes, context)
    if not proceed or bind is None:
        return contents

    current = attributes.get(u'for')
    if forced or current is None and tagname in _auto_tags[u'for']:
        raw_id = _generate_raw_domid(tagname, attributes, bind)
        if raw_id:
            fmt = context[u'domid_format']
            attributes[u'for'] = fmt % raw_id
    return contents


@transformer(u'tabindex', (u'input', u'button', u'select', u'textarea'))
@defaults({u'auto_tabindex': False, u'tabindex': 0})
def transform_tabindex(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_tabindex', attributes, context)
    if not proceed:
        return contents

    tabindex = context[u'tabindex']
    if tabindex == 0:
        return contents

    current = attributes.get(u'tabindex')
    if forced or current is None and tagname in _auto_tags[u'tabindex']:
        attributes[u'tabindex'] = unicode(tabindex)
        if tabindex > 0:
            context[u'tabindex'] = tabindex + 1
    return contents


@defaults({u'auto_filter': False, u'filters': ()})
def transform_filters(tagname, attributes, contents, context, bind):
    proceed, forced = _pop_toggle(u'auto_filter', attributes, context)
    filters = context[u'filters']

    if not proceed:
        return contents

    for fn in filters:
        want = getattr(fn, 'tags', None)
        if want and tagname not in want:
            continue

        contents = fn(tagname, attributes, contents, context, bind)

    return contents

_transforms.append(transform_filters)


def _pop_toggle(key, attributes, context):
    """Remove *key* from *attributes*, if present and report its status.

    Returns the effective value of *key* by considering it's troolean value in
    relation to the default value in *context*.  If *key* is present in the
    attributes and was True, the setting is considered to be 'forced', a
    situation with higher weight than simply defaulting to True via the
    context.

    :returns: a 2-tuple of boolean effective value and boolean forced.

    """
    value = parse_trool(attributes.pop(key, Maybe))
    forced = value is True  # setting key="on" is a "forced" setting
    if value is Maybe:
        value = parse_trool(context[key])
    if value is Maybe:
        value = _default_context[key]
    return value, forced


def _generate_raw_domid(tagname, attributes, bind):
    if bind is not None:
        basis = bind.flattened_name()
    else:
        basis = attributes.get(u'name')
    if not basis:
        return

    # add the value="" to CHECKBOX and RADIO to produce a unique ID
    if (tagname == u'input' and
        attributes.get(u'type') in (u'checkbox', u'radio')):
        suffix = _sanitize_domid_suffix(attributes.get(u'value', u''))
        if suffix:
            basis += u'_' + suffix
    return basis


def _sanitize_domid_suffix(string):
    """Try to convert Unicode *string* into a valid non-leading NAME or ID.

      'ID and NAME tokens must begin with a letter ([A-Za-z]) and may be
       followed by any number of letters, digits ([0-9]), hyphens ("-"),
       underscores ("_"), colons (":"), and periods (".").'

    """
    # as this is suffix only, no need to test string[0] for validity
    return _id_invalid_re.sub(u'', string)


def _unpack(html_string):
    """Extract HTML unicode from a __html__() interface."""
    unpacked = html_string.__html__()
    if unpacked.__class__ is unicode:
        return unpacked
    return unicode(unpacked)


def _markup_escape(string):
    if not string:
        return u''
    elif hasattr(string, '__html__'):
        return _unpack(string)
    else:
        return string. \
               replace(u'&', u'&amp;'). \
               replace(u'<', u'&lt;'). \
               replace(u'>', u'&gt;')
