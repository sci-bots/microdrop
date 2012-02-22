from functools import update_wrapper
import operator

from flatland.exc import AdaptationError
from flatland.util import Unspecified, threading
from .containers import Array, Mapping
from .scalars import Date, Integer, Scalar, String


class _MetaCompound(type):
    """Adds a class-level initialization hook """

    _lock = threading.RLock()

    def __new__(self, name, bases, members):
        members['_compound_prepared'] = False
        if '__compound_init__' in members:
            members['__compound_init__'] = \
              _wrap_compound_init(members['__compound_init__'])
        return type.__new__(self, name, bases, members)

    def __call__(cls, value=Unspecified, **kw):
        """Run __compound_init__ on first instance construction."""

        # Find **kw that would override existing class properties and
        # remove them from kw.
        overrides = {}
        for key in kw.keys():
            if hasattr(cls, key):
                overrides[key] = kw.pop(key)

        if overrides:
            # If there are overrides, construct a subtype on the fly
            # so that __compound_init__ has a chance to run again with
            # this new configuration.
            cls = cls.using(**overrides)
            cls.__compound_init__()
        elif not cls.__dict__.get('_compound_prepared'):
            # If this class hasn't been prepared yet, prepare it.
            lock = cls._lock
            lock.acquire()
            try:
                if not cls.__dict__.get('_compound_prepared'):
                    cls.__compound_init__()
            finally:
                lock.release()

        # Finally, implement type.__call__, invoking __init__ with the
        # members of kw that were not class overrides.
        self = cls.__new__(cls, value, **kw)
        if self.__class__ is cls:
            if value is Unspecified:
                self.__init__(**kw)
            else:
                self.__init__(value, **kw)
        return self


def _wrap_compound_init(fn):
    """Decorate __compound_init__ with a status setter & classmethod."""
    if isinstance(fn, classmethod):
        fn = fn.__get__(str).im_func  # type doesn't matter here
    def __compound_init__(cls):
        res = fn(cls)
        cls._compound_prepared = True
        return res
    update_wrapper(__compound_init__, fn)
    return classmethod(__compound_init__)


class Compound(Mapping, Scalar):
    """A mapping container that acts like a scalar value.

    Compound fields are dictionary-like fields that can assemble a
    :attr:`.u` and :attr:`.value` from their children, and can
    decompose a structured value passed to a :meth:`.set` into values
    for its children.

    A simple example is a logical calendar date field composed of 3
    separate Integer component fields, year, month and day.  The
    Compound can wrap the 3 parts up into a single logical field that
    handles :class:`datetime.date` values.  Set a ``date`` on the
    logical field and its component fields will be set with year,
    month and day; alter the int value of the year component field and
    the logical field updates the ``date`` to match.

    :class:`Compound` is an abstract class.  Subclasses must implement
    :meth:`compose` and :meth:`explode`.

    Composites run validation after their children.

    """

    __metaclass__ = _MetaCompound

    def __compound_init__(cls):
        """TODO: doc

        Gist: runs *once* per class, at the time the first element is
        constructed.  You can run it by hand if you want to finalize
        the construction (see TODO above).

        Changing class params on instance construction will cause this
        to run again.

        """

    def compose(self):
        """Return a unicode, native tuple built from children's state.

        :returns: a 2-tuple of unicode representation, native value.
           These correspond to the :meth:`Scalar.serialize_element`
           and :meth:`Scalar.adapt_element` methods of :class:`Scalar`
           objects.

        For example, a compound date field may return a '-' delimited
        string of year, month and day digits and a
        :class:`datetime.date`.

        """
        raise NotImplementedError()

    def explode(self, value):
        """Given a compound value, assign values to children.

        :param value: a value to be adapted and exploded

        For example, a compound date field may read attributes from a
        :class:`datetime.date` value and :meth:`.set()` them on child
        fields.

        The decision to perform type checking on *value* is completely
        up to you and you may find you want different rules for
        different compound types.

        """
        raise NotImplementedError()

    def serialize(self, value):
        raise TypeError("Not implemented for Compound types.")

    def u(self):
        uni, value = self.compose()
        return uni

    def set_u(self, value):
        self.explode(value)

    u = property(u, set_u)
    del set_u

    def value(self):
        uni, value = self.compose()
        return value

    def set_value(self, value):
        self.explode(value)

    value = property(value, set_value)
    del set_value

    def set(self, value):
        try:
            # TODO: historically explode() did not need to have a return value
            # but it would be nice to return it form set() as below.
            res = self.explode(value)
            return True if res is None else res
        except (SystemExit, KeyboardInterrupt, NotImplementedError):
            raise
        except Exception:
            # not wild about quashing here, but set() doesn't allow
            # adaptation exceptions to bubble up.
            return False

    def _set_flat(self, pairs, sep):
        Mapping._set_flat(self, pairs, sep)

    def __repr__(self):
        try:
            return Scalar.__repr__(self)
        except Exception, exc:
            return '<%s %r; value raised %s>' % (
                type(self).__name__, self.name, type(exc).__name__)

    @property
    def is_empty(self):
        """True if all subfields are empty."""
        return reduce(operator.and_, (c.is_empty for c in self.children))


class DateYYYYMMDD(Compound, Date):

    @classmethod
    def __compound_init__(cls):
        assert len(cls.field_schema) < 4
        if len(cls.field_schema) == 3:
            return

        fields = list(cls.field_schema)
        optional = cls.optional

        if len(fields) == 0:
            fields.append(Integer.named(u'year').using(format=u'%04i',
                                                       optional=optional))
        if len(fields) == 1:
            fields.append(Integer.named(u'month').using(format=u'%02i',
                                                        optional=optional))
        if len(fields) == 2:
            fields.append(Integer.named(u'day').using(format=u'%02i',
                                                      optional=optional))

        cls.field_schema = fields

    #if any(not field.name for field in fields):
    #    raise TypeError("Child fields of %s %r must be named." %
    #                    type(self).__name__, name)

    def compose(self):
        try:
            data = dict([(label, self[child_schema.name].value)
                         for label, child_schema
                         in zip(self.used, self.field_schema)])
            as_str = self.format % data
            value = Date.adapt(self, as_str)

            return as_str, value
        except (AdaptationError, TypeError):
            return u'', None

    def explode(self, value):
        try:
            value = Date.adapt(self, value)

            for attrib, child_schema in zip(self.used, self.field_schema):
                self[child_schema.name].set(
                    getattr(value, attrib.encode('ascii')))
        except (AdaptationError, TypeError):
            for child_schema in self.field_schema:
                self[child_schema.name].set(None)


class JoinedString(Array, String):
    """A sequence container that acts like a compounded string such as CSV.

    Marshals child element values to and from a single string:

    .. doctest::

      >>> from flatland import JoinedString
      >>> el = JoinedString(['x', 'y', 'z'])
      >>> el.value
      u'x,y,z'
      >>> el2 = JoinedString('foo,bar')
      >>> el2[1].value
      u'bar'
      >>> el2.value
      u'foo,bar'

    Only the joined representation is considered when flattening or restoring
    with :meth:`set_flat`.  JoinedStrings run validation after their children.

    """
    #: The string used to join children's :attr:`u` representations.  Will
    #: also be used to split incoming strings, unless :attr:`separator_regex`
    #: is also defined.
    separator = u','

    #: Optional, a regular expression, used preferentially to split an
    #: incoming separated value into components.  Used in combination with
    #: :attr:`separator`, a permissive parsing policy can be combined with
    #: a normalized representation, e.g.:
    #:
    #: .. doctest::
    #:
    #:   >>> import re
    #:   >>> schema = JoinedString.using(separator=', ',
    #:   ...                             separator_regex=re.compile('\s*,\s*'))
    #:   ...
    #:   >>> schema('a  ,  b,c,d').value
    #:   u'a, b, c, d'
    separator_regex = None

    #: The default child type is :class:`~flatland.schema.scalars.String`,
    #: but can be customized with
    #: :class:`~flatland.schema.scalars.Integer` or any other type.
    member_schema = String

    flattenable = True
    children_flattenable = False

    def set(self, value):
        if isinstance(value, (list, tuple)):
            values = value
        elif not isinstance(value, basestring):
            values = list(value)
        elif self.separator_regex:
            # a basestring, regexp separator
            values = self.separator_regex.split(value)
        else:
            # a basestring, static separator
            values = value.split(self.separator)

        del self[:]
        prune = self.prune_empty
        success = []
        for value in values:
            if prune and not value:
                continue
            child = self.member_schema()
            success.append(child.set(value))
            self.append(child)
        return all(success)

    def _set_flat(self, pairs, sep):
        return Scalar._set_flat(self, pairs, sep)

    @property
    def value(self):
        """A read-only :attr:`separator`-joined string of child values."""
        return self.separator.join(child.u for child in self)

    @property
    def u(self):
        """A read-only :attr:`separator`-joined string of child values."""
        return self.value
