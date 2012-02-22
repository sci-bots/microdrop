from __future__ import absolute_import
from collections import deque

from genshi.core import Namespace, QName, END, START, TEXT
from genshi.template.base import (
    DirectiveFactory,
    EXPR,
    SUB,
    TemplateSyntaxError,
    _eval_expr,
    )
from genshi.template.eval import Expression
from genshi.template.directives import Directive
from genshi.template.interpolation import interpolate


from flatland.out.generic import _unpack, transform, Context


__all__ = ('setup',)

NS = Namespace(u'http://ns.discorporate.us/flatland/genshi')

_static_attribute_order = [u'type', u'name', u'value']

_to_context = {}
for key in (u'auto-name', u'auto-value', u'auto-domid', u'auto-for',
            u'auto-tabindex', u'auto-filter', u'domid-format'):
    _to_context[key] = key.replace(u'-', u'_')

_bind_qname = NS.bind


def setup(template):
    """Register the flatland directives with a template.

    :param template: a `Template` instance
    """

    if not hasattr(template, 'add_directives'):
        raise RuntimeError("%s.setup requires Genshi 0.6 or higher." % (
            __name__,))
    template.add_directives(NS, FlatlandElements())


class EvaluatedLast(Directive):
    __slots__ = ()

    def __call__(self, stream, directives, ctxt, **vars):
        local, foreign = [], []
        for d in directives:
            if isinstance(d, EvaluatedLast):
                local.append(d)
            else:
                foreign.append(d)
        if foreign:
            foreign.append(self)
            foreign.extend(local)
            return foreign[0](stream, foreign[1:], ctxt, **vars)
        return self.process(stream, local, ctxt, vars)

    def process(self, stream, directives, ctxt, vars):
        raise NotImplementedError  # pragma: nocover


class TagOnly(EvaluatedLast):
    _name = None
    __slots__ = ('attributes',)

    @classmethod
    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is not dict:
            raise TemplateSyntaxError(
                "The %s directive must be an element" % cls._name,
                template.filepath, *pos[1:])
        return super(TagOnly, cls).attach(
            template, stream, value, namespaces, pos)

    def __init__(self, value, template=None, namespaces=None,
                 lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)
        self.attributes = value


class AttributeOnly(EvaluatedLast):
    _name = None
    __slots__ = ()

    @classmethod
    def attach(cls, template, stream, value, namespaces, pos):
        if type(value) is dict:
            raise TemplateSyntaxError(
                ("The %s directive may only be used as a "
                 "tag attribute" % cls._name),
                template.filepath, *pos[1:])
        return super(AttributeOnly, cls).attach(
            template, stream, value, namespaces, pos)


class ControlAttribute(AttributeOnly):
    __slots__ = ('raw_value')

    def __init__(self, value, template=None, namespaces=None,
                 lineno=-1, offset=-1):
        Directive.__init__(self, None, template, namespaces, lineno, offset)

        # allow interpolation inside control attributes
        raw_value = list(interpolate(value, lineno=lineno, offset=offset))
        if all(kind is TEXT for (kind, _, _) in raw_value):
            self.raw_value = u''.join(event[1] for event in raw_value)
        else:
            self.raw_value = raw_value

    def process(self, stream, directives, ctxt, vars):
        # unbound transformation.
        if not directives:
            directives = [self]
        else:
            directives = [self] + directives
        return _rewrite_stream(stream, directives, ctxt, vars, None)

    def inject(self, mapping, ctxt, vars):
        """Inject the translated key and interpolated value into *mapping*."""
        raw = self.raw_value
        if raw.__class__ is unicode:
            final_value = raw
        else:
            parts = []
            for kind, value, pos in raw:
                if kind is TEXT:
                    parts.append(value)
                else:
                    value = _eval_expr(value, ctxt, vars)
                    parts.append(unicode(value))
            final_value = u''.join(parts)
        mapping[_to_context.get(self._name, self._name)] = final_value


class AutoName(ControlAttribute):
    _name = 'auto-name'
    __slots__ = ()


class AutoValue(ControlAttribute):
    _name = 'auto-value'
    __slots__ = ()


class AutoDomID(ControlAttribute):
    _name = 'auto-domid'
    __slots__ = ()


class AutoFor(ControlAttribute):
    _name = 'auto-for'
    __slots__ = ()


class AutoTabindex(ControlAttribute):
    _name = 'auto-tabindex'
    __slots__ = ()


class AutoFilter(ControlAttribute):
    _name = 'auto-filter'
    __slots__ = ()


class Binding(AttributeOnly):
    _name = 'bind'
    __slots__ = ('bind',)

    def __init__(self, attributes, template=None, namespaces=None,
                 lineno=-1, offset=-1, bind=None):
        AttributeOnly.__init__(self, attributes, template, namespaces,
                               lineno, offset)
        self.bind = bind

    def process(self, stream, directives, ctxt, vars):
        if self.bind is not None:
            bind = self.bind
        elif self.expr is None:
            bind = None
        else:
            bind = _eval_expr(self.expr, ctxt, vars)
        return _rewrite_stream(stream, directives, ctxt, vars, bind)


class RenderContextManipulator(TagOnly):
    __slots__ = ()

    def __init__(self, attributes, template=None, namespaces=None,
                 lineno=-1, offset=-1):
        transformed = {}
        for key, value in attributes.items():
            key = _to_context.get(key, key)
            if key == u'tabindex':
                value = int(value)
            transformed[key] = value
        TagOnly.__init__(self, transformed, template, namespaces,
                         lineno, offset)


class With(RenderContextManipulator):
    _name = 'with'
    __slots__ = ()

    def process(self, stream, directives, ctxt, vars):
        try:
            render_context = ctxt['flatland_render_context']
        except KeyError:
            ctxt['flatland_render_context'] = render_context = Context()

        if 'filters' not in self.attributes:
            attrs = self.attributes
        else:
            attrs = self.attributes.copy()
            attrs['filters'] = _eval_expr(Expression(attrs['filters']),
                                          ctxt, vars)

        render_context.push()
        render_context.update(attrs)
        assert not directives
        for event in stream:
            yield event
        render_context.pop()


class Set(RenderContextManipulator):
    _name = 'set'
    __slots__ = ()

    def process(self, stream, directives, ctxt, vars):
        try:
            render_context = ctxt['flatland_render_context']
        except KeyError:
            ctxt['flatland_render_context'] = render_context = Context()
        render_context.update(self.attributes)
        assert not directives
        return stream


class FlatlandElements(DirectiveFactory):

    NAMESPACE = NS

    directives = [
        ('with', With),
        ('set', Set),
        ('bind', Binding),
        ('auto-name', AutoName),
        ('auto-value', AutoValue),
        ('auto-domid', AutoDomID),
        ('auto-for', AutoFor),
        ('auto-tabindex', AutoTabindex),
        ('auto-filter', AutoFilter),
        ]


def _rewrite_stream(stream, directives, ctxt, vars, bind):
    stream = list(stream)
    mutable_attrs = {}

    for control_attribute in directives:
        control_attribute.inject(mutable_attrs, ctxt, vars)

    kind, (tagname, attrs), pos = stream[0]
    if len(stream) == 2:
        contents = None
    else:
        contents = _simplify_stream(stream[1:-1], ctxt, vars)

    existing_attributes = {}
    for qname, value in attrs:
        if qname.namespace is None:
            if not isinstance(value, unicode):
                value = _simplify_stream(value, ctxt, vars)
                attrs |= ((qname, value),)
            existing_attributes[qname.localname] = qname
            mutable_attrs[qname.localname] = value

    try:
        render_context = ctxt['flatland_render_context']
    except KeyError:
        ctxt['flatland_render_context'] = render_context = Context()

    new_contents = transform(tagname.localname, mutable_attrs, contents,
                             render_context, bind)

    if new_contents is None:
        new_contents = ()
    elif isinstance(new_contents, unicode):
        new_contents = [(TEXT, new_contents, (None, -1, -1))]

    pairs = sorted(mutable_attrs.iteritems(), key=_attribute_sort_key)
    for attribute_name, value in pairs:
        if attribute_name in existing_attributes:
            qname = existing_attributes.pop(attribute_name)
        else:
            qname = QName(attribute_name)
        attrs |= ((qname, value),)
    for qname in existing_attributes.values():
        attrs -= qname

    stream[0] = (kind, (tagname, attrs), pos)
    if new_contents and tagname.localname == u'select' and bind is not None:
        if tagname.namespace:
            sub_tag = Namespace(tagname.namespace).option
        else:  # pragma: nocover
            sub_tag = QName('option')
        new_contents = _bind_unbound_tags(new_contents, sub_tag, bind)
    if new_contents:
        stream[1:-1] = new_contents
    return iter(stream)


def _attribute_sort_key(item):
    try:
        return (0, _static_attribute_order.index(item[0]))
    except ValueError:
        return (1, item[0])


def _bind_unbound_tags(stream, qname, bind):
    stream = deque(stream)
    while stream:
        kind, data, pos = stream.popleft()
        if kind is SUB:
            directives, substream = data
            for d in directives:  # pragma: nocover   (coverage bug :()
                if isinstance(d, Binding):
                    break
            else:
                substream = list(_bind_unbound_tags(substream, qname, bind))
            yield kind, (directives, substream), pos
        elif kind is START:
            if data[0] != qname or qname in data[1]:
                yield kind, data, pos
                continue
            head = kind, data, pos
            substream = []
            stack = 1
            while stack:
                event = stream.popleft()
                substream.append(event)
                if event[0] is START and event[1][0] == qname:
                    stack += 1
                elif event[0] is END and event[1] == qname:
                    stack -= 1
            substream = [head] + list(
                _bind_unbound_tags(substream, qname, bind))
            # attaching the directive is sufficient; don't need to fabricate
            # a form:bind="" attribute
            yield SUB, ([Binding(u'', bind=bind)], substream), pos
        else:
            yield kind, data, pos


def _simplify_stream(stream, ctxt, vars):
    # consumes stream, send a list
    parts = []
    for idx, (kind, data, pos) in enumerate(stream):
        if kind is TEXT:
            parts.append(data)
        elif kind is EXPR:
            value = _eval_expr(data, ctxt, vars)
            if hasattr(value, '__html__'):
                value = _unpack(value)
            if hasattr(value, '__next__') or hasattr(value, 'next'):
                while hasattr(value, '__next__') or hasattr(value, 'next'):
                    value = list(value)
                    value = _simplify_stream(value, ctxt, vars)
                if not isinstance(value, unicode):
                    stream[idx:idx + 1] = value
                else:
                    stream[idx] = (TEXT, value, pos)
            elif not isinstance(value, unicode):
                value = unicode(value)
            parts.append(value)
        else:
            return stream
    return u''.join(parts)
