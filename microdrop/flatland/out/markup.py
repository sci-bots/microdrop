from collections import defaultdict

from flatland.out.generic import Context, transform, _unpack
from flatland.out.util import parse_trool


_default_settings = {u'ordered_attributes': True}
_static_attribute_order = [u'type', u'name', u'value']


class Generator(Context):
    """General XML/HTML tag generator"""

    def __init__(self, markup='xhtml', **settings):
        """Create a generator.

        Accepts any :ref:`markupsettings`, as well as the following:

        :param markup: tag output style: 'xml', 'xhtml' or 'html'

        :param ordered_attributes: if True (default), output markup attributes
          in a predictable order.  Useful for tests and generally a little
          more pleasant to read.

        """
        Context.__init__(self)
        if markup == 'html':
            self.xml = False
        elif markup in ('xhtml', 'xml'):
            self.xml = True
        else:
            raise TypeError("Unknown markup type %r" % markup)
        self._tags = defaultdict(list)
        self._frames[-1].update(_default_settings)
        self.push()
        self.update(settings)

    def begin(self, **settings):
        """Begin a new :ref:`markupsettings` context.

        Puts \*\*settings into effect until a matching :meth:`end` is called.
        Each setting specified will mask the current value, reverting when
        :meth:`end` is called.

        """
        self.push(**settings)
        return self['markup_wrapper'](u'')

    def end(self):
        """End a :ref:`markupsettings` context.

        Restores the settings that were in effect before :meth:`begin`.

        """
        if len(self._frames) == 2:
            raise RuntimeError("end() without matching begin()")
        self.pop()
        return self['markup_wrapper'](u'')

    def set(self, **settings):
        """Change the :ref:`markupsettings` in effect.

        Change the \*\*settings in the current scope.  Changes remain in
        effect until another :meth:`set` or a :meth:`end` ends the current
        scope.

        """

        for key, value in settings.items():
            if key not in self:
                raise TypeError(
                    "%r is not a valid argument." % key)
            if key.startswith('auto_'):
                value = parse_trool(value)
            self[key] = value
        return self['markup_wrapper'](u'')

    @property
    def form(self):
        """Generate a <form/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, form tags can generate the *name* attribute.

        """
        return self._tag(u'form', False, True)

    @property
    def input(self):
        """Generate an <input/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, input tags can generate the *name*, *value*
        and *id* attributes.  Input tags support *tabindex* attributes.

        """
        return self._tag(u'input', True)

    @property
    def textarea(self):
        """Generate a <textarea/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, textarea tags can generate the *name* and
        *id* attributes.  If the bind has a value, it will be used as the tag
        body.  Textarea tags support *tabindex* attributes.  To provide an
        alternate tag body, either supply *contents* or use the
        :meth:`~Tag.open` and :meth:`~Tag.close` method of the returned tag.

        """
        return self._tag(u'textarea', False, True)

    @property
    def button(self):
        """Generate a <button/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, button tags can generate the *name*, *value*,
        and *id* attributes.  Button tags support *tabindex* attributes.

        """
        return self._tag(u'button')

    @property
    def select(self):
        """Generate a <select/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, select tags can generate the *name* and *id*
        attributes.  Select tags support *tabindex* attributes.

        """
        return self._tag(u'select', False, True)

    @property
    def option(self):
        """Generate a <option/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, option tags can generate the *value*
        attribute.  To provide tag body, either supply *contents* or use the
        :meth:`~Tag.open` and :meth:`~Tag.close` method of the returned tag::

           print generator.option.open(style='bold')
           print '<strong>contents</strong>'
           print generator.option.close()

        """
        return self._tag(u'option', False, True)

    @property
    def label(self):
        """Generate a <label/> tag.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        If provided with a bind, label tags can generate the *for* attribute
        and fill in the tag body with the element's
        :attr:`~flatland.Element.label`, if present.

        """
        return self._tag(u'label')

    def tag(self, tagname, bind=None, **attributes):
        """Generate any tag.

        :param tagname: the name of the tag.
        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired xml/html attributes.
        :returns: a printable :class:`Tag`

        The attribute rules appropriate for *tagname* will be applied.  For
        example, ``tag('input')`` is equivalent to ``input()``.

        """
        if isinstance(tagname, str):  # pragma: nocover
            tagname = unicode(tagname)
        tagname = tagname.lower()
        if bind is None and not attributes:
            return self._tag(tagname)
        else:
            return self._tag(tagname)(bind, **attributes)

    def _tag(self, tagname, empty_in_html=False, always_paired=False):
        if self._tags[tagname]:
            return self._tags[tagname][-1]
        return Tag(tagname, self, empty_in_html, always_paired)


class Tag(object):
    """A printable markup tag.

    Tags are generated by :class:`Generator` and are usually called
    immediately, returning a fully formed markup string::

      print generator.textarea(contents="hello!")

    For more fine-tuned control over your markup, you may instead choose to
    use the :meth:`open` and :meth:`close` methods of the tag::

      print generator.textarea.open()
      print "hello!"
      print generator.textarea.close()

    """

    __slots__ = ('tagname', 'contents', '_context',
                 '_html_dangle', '_always_paired')

    def __init__(self, tagname, context, dangle, paired):
        self.tagname = tagname
        self._context = context
        self._html_dangle = dangle
        self._always_paired = paired
        self.contents = None

    def open(self, bind=None, **attributes):
        """Return the opening half of the tag, e.g. <p>.

        :param bind: optional, a flatland element.
        :param \*\*attributes: any desired tag attributes.

        """
        if self not in self._context._tags[self.tagname]:
            self._context._tags[self.tagname].append(self)
        return self._markup(self._open(bind, attributes) + u'>')

    def close(self):
        """Return the closing half of the tag, e.g. </p>."""
        try:
            self._context._tags[self.tagname].remove(self)
        except ValueError:
            pass
        return self._markup(self._close())

    def _open(self, bind, kwargs):
        """Return a '<partial' opener tag with no terminator."""
        contents = kwargs.pop('contents', None)
        attributes = _unicode_keyed(kwargs)
        tagname = self.tagname
        new_contents = transform(
            tagname, attributes, contents, self._context, bind)

        if not new_contents:
            new_contents = u''
        elif hasattr(new_contents, '__html__'):
            new_contents = _unpack(new_contents)
        self.contents = self._markup(new_contents)

        if self._context['ordered_attributes']:
            pairs = sorted(attributes.items(), key=_attribute_sort_key)
        else:
            pairs = attributes.iteritems()
        guts = u' '.join(u'%s="%s"' % (k, _attribute_escape(v))
                         for k, v in pairs)
        if guts:
            return u'<' + tagname + u' ' + guts
        else:
            return u'<' + tagname

    def _close(self):
        return u'</' + self.tagname + u'>'

    def _markup(self, string):
        return self._context['markup_wrapper'](string)

    def __call__(self, bind=None, **attributes):
        """Return a complete, closed markup string."""
        header = self._open(bind, attributes)
        contents = self.contents
        if not contents:
            if not self._always_paired:
                if self._context.xml:
                    return self._markup(header + u' />')
                elif self._html_dangle:
                    return self._markup(header + u'>')
        if hasattr(contents, '__html__'):
            contents = _unpack(contents)
        return self._markup(header + u'>' + contents + self._close())

    def __html__(self):
        return self()


def _attribute_escape(string):
    if not string:
        return u''
    elif hasattr(string, '__html__'):
        return _unpack(string)
    else:
        return string. \
               replace(u'&', u'&amp;'). \
               replace(u'<', u'&lt;'). \
               replace(u'>', u'&gt;'). \
               replace(u'"', u'&quot;')


def _unicode_keyed(bytestring_keyed):
    rekeyed = {}
    for key, value in bytestring_keyed.items():
        as_unicode = key.rstrip('_').decode('ascii')
        rekeyed[as_unicode] = value
    return rekeyed


def _attribute_sort_key(item):
    try:
        return (0, _static_attribute_order.index(item[0]))
    except ValueError:
        return (1, item[0])
