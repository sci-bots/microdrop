# -*- coding: utf-8; fill-column: 78 -*-
from collections import defaultdict
import re

from flatland.util import (
    Unspecified,
    assignable_class_property,
    autodocument_from_superclasses,
    class_cloner,
    keyslice_pairs,
    re_uescape,
    to_pairs,
    )
from flatland.schema.base import Element, Unevaluated, Slot, validate_element
from flatland.schema.scalars import Scalar


__all__ = (
    'Array',
    'Container',
    'Dict',
    'List',
    'Mapping',
    'MultiValue',
    'Sequence',
    )


class Container(Element):
    """Holds other schema items.

    Base class for elements that can contain other elements, such as
    :class:`List` and :class:`Dict`.

    :param descent_validators: optional, a sequence of validators that
      will be run before contained elements are validated.

    :param validators: optional, a sequence of validators that will be
      run after contained elements are validated.

    :param \*\*kw: other arguments common to
      :class:`~flatland.schema.base.FieldSchema`.

    """

    validates_down = 'descent_validators'

    validates_up = 'validators'

    descent_validators = ()
    """TODO: doc descent_validators"""

    @class_cloner
    def descent_validated_by(cls, *validators):
        """Return a class with descent validators set to *\*validators*.

        :param \*validators: one or more validator functions, replacing any
          descent validators present on the class.

        :returns: a new class
        """
        for validator in validators:
            # metaclass gymnastics can fool this assertion. don't do that.
            if isinstance(validator, type):
                raise TypeError(
                    "Validator %r is a type, not a callable or instance of a"
                    "validator class.  Did you mean %r()?" % (
                        validator, validator))
        cls.descent_validators = list(validators)
        return cls

    @class_cloner
    def including_descent_validators(cls, *validators, **kw):
        """Return a class with additional descent *\*validators*.

        :param \*validators: one or more validator functions

        :param position: defaults to -1.  By default, additional validators
          are placed after existing descent validators.  Use 0 for before, or
          any other list index to splice in *validators* at that point.

        :returns: a new class
        """
        position = kw.pop('position', -1)
        if kw:
            raise TypeError('including_validators() got an '
                            'unexpected keyword argument %r' % (
                                kw.popitem()[0]))
        mutable = list(cls.descent_validators)
        if position < 0:
            position = len(mutable) + 1 + position
        mutable[position:position] = list(validators)
        cls.descent_validators = mutable
        return cls

    def validate_element(self, element, state, descending):
        """Validates on the first (downward) and second (upward) pass.

        If :attr:`descent_validators` are defined on the schema, they
        will be evaluated before children are validated.  If a
        validation function returns :obj:`flatland.SkipAll` or
        :obj:`flatland.SkipFalse`, downward validation will halt on
        this container and children will not be validated.

        If :attr:`validators` are defined, they will be evaluated
        after children are validated.

        See :meth:`FieldSchema.validate_element`.

        """
        if descending:
            if self.descent_validators:
                return validate_element(
                    element, state, self.descent_validators)
            else:
                return None
        else:
            return validate_element(element, state, self.validators)

    def _validate(self, state, descending):
        """Run validation, transforming None into success. Internal."""
        # FIXME: refactor this to allow for this logic ("Don't apply default
        # validation on downward pass") to be defined declaratively.
        if descending:
            if self.validates_down:
                validators = getattr(self, self.validates_down, None)
                if not validators:
                    return Unevaluated
                return validate_element(self, state, validators)
        else:
            if self.validates_up:
                validators = getattr(self, self.validates_up, None)
                return validate_element(self, state, validators)
        return Unevaluated


class Sequence(Container, list):
    """Abstract base of sequence-like Containers.

    Instances of :class:`Sequence` hold other elements and operate like Python
    lists.  Each sequence member will be an instance of :attr:`member_schema`.

    Python list methods and operators may be passed instances of
    :attr:`member_schema` or plain Python values.  Using plain values is a
    shorthand for creating an :attr:`member_schema` instance and
    :meth:`set()ting<flatland.schema.base.Element.set>` it with the value:

    .. doctest::

      >>> from flatland import Array, Integer
      >>> Numbers = Array.of(Integer)
      >>> ones = Numbers()
      >>> ones.append(1)
      >>> ones
      [<Integer None; value=1>]
      >>> another_one = Integer()
      >>> another_one.set(1)
      True
      >>> ones.append(another_one)
      >>> ones
      [<Integer None; value=1>, <Integer None; value=1>]

    """

    member_schema = None
    """An :class:`~flatland.schema.base.Element` class for sequence members."""

    prune_empty = True
    """If true, skip missing index numbers in :meth:`set_flat`. Default True.

    See `Sequences`_ for more information.

    """

    def __init__(self, value=Unspecified, **kw):
        Container.__init__(self, value, **kw)
        if not self.member_schema:
            raise TypeError("Invalid schema: %r has no member_schema" %
                            type(self))

    @class_cloner
    def of(cls, *schema):
        """Declare the class to hold a sequence of *\*schema*.

        :params \*schema: one or more :class:`flatland.Element` classes
        :returns: *cls*

        Configures the :attr:`member_schema` of *cls* to hold instances of
        *\*schema*.

        .. doctest::

          >>> from flatland import Array, String
          >>> Names = Array.of(String.named('name'))
          >>> Names.member_schema
          <class 'flatland.schema.scalars.String'>
          >>> el = Names(['Bob', 'Biff'])
          >>> el
          [<String u'name'; value=u'Bob'>, <String u'name'; value=u'Biff'>]

        If more than one :class:`~flatland.Element` is specified in
        *\*schema*, an anonymous :class:`Dict` is created to hold them.

        .. doctest::

          >>> from flatland import Integer
          >>> Points = Array.of(Integer.named('x'), Integer.named('y'))
          >>> Points.member_schema
          <class 'flatland.schema.containers.Dict'>
          >>> el = Points([dict(x=1, y=2)])
          >>> el
          [{u'y': <Integer u'y'; value=2>, u'x': <Integer u'x'; value=1>}]

        """
        for field in schema:
            if isinstance(field, Element):
                raise TypeError("'of' must be initialized with types, got "
                                "instance %r" % field)
        if not schema:
            raise TypeError("One or more Element classes is required")
        elif len(schema) == 1:
            cls.member_schema = schema[0]
        else:
            cls.member_schema = Dict.of(*schema)
        return cls

    def set(self, iterable):
        """Assign the native and Unicode value.

        Attempts to adapt the given *iterable* and assigns this element's
        :attr:`value` and :attr:`u` attributes in tandem.  Returns True if the
        adaptation was successful.  See
        :meth:`Element.set()<flatland.schema.base.Element.set>`.

        Set must be supplied a Python sequence or iterable:

        .. doctest::

          >>> from flatland import Integer, List
          >>> Numbers = List.of(Integer)
          >>> nums = Numbers()
          >>> nums.set([1, 2, 3, 4])
          True
          >>> nums.value
          [1, 2, 3, 4]

        """

        del self[:]
        self.raw = iterable
        values, converted = [], True
        try:
            for v in iterable:
                el = self.member_schema()
                converted &= el.set(v)
                values.append(el)
            self.extend(values)
        except TypeError:
            return False
        else:
            return converted

    def set_default(self):
        default = self.default_value
        if default is not None and default is not Unspecified:
            del self[:]
            self.extend(default)

    def _set_flat(self, pairs, sep):
        raise NotImplementedError()

    @property
    def children(self):
        return iter(self)

    @property
    def is_empty(self):
        return not any(True for _ in self.children)

    def _index(self, name):
        try:
            idx = int(name)
        except ValueError:
            raise IndexError(name)
        return self[idx]

    def append(self, value):
        """Append *value* to end.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before appending.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        value.parent = self
        list.append(self, value)

    def extend(self, iterable):
        """Append *iterable* values to the end.

        If values of *iterable* are not instances of :attr:`member_schema`,
        they will be wrapped in a new element of that type before extending.

        """
        for value in iterable:
            self.append(value)

    def insert(self, index, value):
        """Insert *value* at *index*.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before inserting.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        value.parent = self
        list.insert(self, index, value)

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            as_elements = []
            for item in value:
                if not isinstance(item, Element):
                    item = self.member_schema(value=item)
                item.parent = self
                as_elements.append(item)
            value = as_elements
        else:
            if not isinstance(value, Element):
                value = self.member_schema(value=value)
                value.parent = self
        list.__setitem__(self, index, value)

    def __setslice__(self, i, j, value):
        self.__setitem__(slice(i, j), value)

    def remove(self, value):
        """Remove member with value *value*.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before searching for a matching
        element to remove.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        list.remove(self, value)

    def index(self, value):
        """Return first index of *value*.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before searching for a matching
        element in the sequence.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        return list.index(self, value)

    def count(self, value):
        """Return number of occurrences of *value*.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before searching for matching
        elements in the sequence.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        return list.count(self, value)

    def __contains__(self, value):
        """Return True if sequence contains *value*.

        If *value* is not an instance of :attr:`member_schema`, it will be
        wrapped in a new element of that type before searching for a matching
        element in the sequence.

        """
        if not isinstance(value, Element):
            value = self.member_schema(value=value)
        return list.__contains__(self, value)

    @property
    def value(self):
        return list(value.value for value in self.children)

    @property
    def u(self):
        return u'[%s]' % u', '.join(
            element.u if isinstance(element, Container)
                      else repr(element.u).decode('raw_unicode_escape')
            for element in self.children)


class ListSlot(Container, Slot):
    """Wraps elements of Lists & models their position in the list.

    :class:`List ` makes these mostly invisible to the outside, appearing only
    when flattening names.  The :attr:`name` is set by the List and will be a
    unicoded integer index.  Flattening a list name will join the parent's
    name with the slot's name with the child element's name:

      'listname_0_childname', 'listname_1_childname'

    """

    def __init__(self, name, parent, element):
        self.name = name
        self.parent = parent
        self.element = element
        element.parent = self

    @property
    def u(self):
        return self.element.u

    @property
    def value(self):
        return self.element.value

    def __repr__(self):
        return '<ListSlot[%r] for %r>' % (self.name, self.element)


class List(Sequence):
    """An ordered, homogeneous Sequence."""

    # TODO: clarify if descent_validators run on empty, optional sequences

    slot_type = ListSlot

    # Default definition duplicated for sphinx documentation purposes
    member_schema = ()
    """An :class:`~flatland.schema.base.Element` class for member elements.

    See also the :meth:`~Sequence.of` schema configuration method.

    """

    maximum_set_flat_members = 1024
    """Maximum list members set in a :meth:`set_flat` operation.

    Once this maximum of child members has been added, subsequent data will be
    dropped.  This ceiling prevents denial of service attacks when processing
    Lists with :attr:`prune_empty` set to False; without it remote attackers
    can trivially exhaust memory by specifying one low and one very high
    index.

    """

    def _as_element(self, value):
        """TODO"""
        if value is Unspecified:
            return self.member_schema()
        if isinstance(value, Element):
            return value
        else:
            return self.member_schema(value)

    def _new_slot(self, value=Unspecified):
        """Wrap *value* in a Slot named as the element's index in the list."""
        return self.slot_type(name=str(len(self)).decode('ascii'),
                              parent=self,
                              element=self._as_element(value))

    @property
    def _slots(self):
        """An iterator of the List's otherwise hidden Slots."""
        return list.__iter__(self)

    def append(self, value):
        list.append(self, self._new_slot(value))

    def extend(self, iterable):
        for v in iterable:
            self.append(v)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [item.element for item in list.__getitem__(self, index)]
        return list.__getitem__(self, index).element

    def __getslice__(self, i, j):
        return self.__getitem__(slice(i, j))

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            value = [self._new_slot(item) for item in value]
            list.__setitem__(self, index, value)
            self._renumber()
        else:
            slot = self[index]
            slot.set(value)

    def __setslice__(self, i, j, sequence):
        return self.__setitem__(slice(i, j), sequence)

    def __iter__(self):
        for i in list.__iter__(self):
            yield i.element

    def __delitem__(self, index):
        # Optimizing __delitem__ or pop when removing only the last item
        # doesn't seem worth it.
        list.__delitem__(self, index)  # slices ok
        self._renumber()

    def __delslice__(self, i, j):
        return self.__delitem__(slice(i, j))

    def pop(self, index=-1):
        value = list.pop(self, index)
        self._renumber()
        value.parent = None
        return value

    def insert(self, index, value):
        list.insert(self, index, self._new_slot(value))
        self._renumber()

    def remove(self, value):
        list.remove(self, self._as_element(value))
        self._renumber()

    def sort(self, cmp=None, key=None, reverse=False):
        list.sort(self, cmp, key, reverse)
        self._renumber()

    def reverse(self):
        list.reverse(self)
        self._renumber()

    def _renumber(self):
        for idx, slot in enumerate(self._slots):
            slot.name = str(idx).decode('ascii')

    @property
    def children(self):
        return iter(child.element for child in self._slots)

    def _set_flat(self, pairs, sep):
        del self[:]

        if not pairs:
            return

        if self.name:
            regex = re.compile(ur'^%s(\d+)(?:%s|$)' % (
                re_uescape(self.name + sep), re_uescape(sep)), re.UNICODE)
        else:
            regex = re.compile(ur'^(\d+)(?:%s|$)' % (
                re_uescape(sep)), re.UNICODE)

        indexes = defaultdict(list)
        prune = self.prune_empty

        for key, value in pairs:
            if value == u'' and prune:
                continue
            m = regex.match(key)
            if not m:
                continue
            try:
                index = long(m.group(1))
            except TypeError:
                # Ignore keys with outrageously large indexes- they
                # aren't valid data for us.
                pass
            else:
                child_key = key[len(m.group(0)):] or None
                indexes[index].append((child_key, value))

        if not indexes:
            return

        # lossy: missing (or empty-valued) indexes are omitted.
        #        the python indexes may not match the flat indexes
        if prune:
            for offset, index in enumerate(sorted(indexes)):
                if offset == self.maximum_set_flat_members:
                    break
                slot = self._new_slot()
                list.append(self, slot)
                slot.element.set_flat(indexes[index], sep)
        # lossless: elements are built up to the highest seen index or a
        #           schema-configured maximum. flat + python indexes match.
        else:
            max_index = min(max(indexes) + 1, self.maximum_set_flat_members)
            for index in xrange(0, max_index):
                slot = self._new_slot()
                list.append(self, slot)
                flat = indexes.get(index, None)
                if flat:
                    slot.element.set_flat(flat, sep)

    def set_default(self):
        """set() the element to the schema default.

        List's set_default supports two modes for
        :attr:`~flatland.schema.base.Element.default` values:

        - If default is an integer, the List will be filled with that many
          elements.  Each element will then have
          :meth:`~flatland.schema.base.Element.set_default` called on it.

        - Otherwise if default has a value, the list will be :meth:`set` with
          it.

        """
        default = self.default_value
        if default is None or default is Unspecified:
            return

        del self[:]
        if isinstance(default, int):
            for _ in xrange(0, default):
                slot = self._new_slot()
                list.append(self, slot)
                slot.element.set_default()
        else:
            self.set(default)

    def __repr__(self):
        # shield the slots from repr
        return repr(list(self))


class Array(Sequence):
    """A transparent homogeneous Container, for multivalued form elements.

    Arrays hold a collection of values under a single name, allowing
    all values of a repeated `(key, value)` pair to be captured and
    used.  Elements are sequence-like.

    """

    prune_empty = True
    flattenable = False

    def _set_flat(self, pairs, sep):
        del self[:]
        prune = self.prune_empty
        child_name = self.member_schema.name

        # TODO: some complexity snuck in below with the thought of supporting
        # arrays of containers.  they're *not* working yet.
        assert not issubclass(self.member_schema, Container), \
               "Flattened Arrays are only supported for scalar child types."

        if not self.name:
            child_prefix = child_name or u''
            for key, value in pairs:
                if prune and value == u'' and key == child_prefix:
                    continue
                if key == u'':
                    key = None
                if child_name and key != child_name:
                    continue
                member = self.member_schema.from_flat([(key, value)])
                self.append(member)
        else:
            regex = re.compile(ur'^(%s(?:%s|$))' % (
                re_uescape(self.name), re_uescape(sep)), re.UNICODE)
            for key, value in pairs:
                m = regex.match(key)
                if not m:
                    continue
                remainder = key[m.end():] or None
                if child_name and not remainder:
                    continue
                elif prune and value == u'' and remainder == child_name:
                    continue
                member = self.member_schema.from_flat([(remainder, value)])
                self.append(member)


class MultiValue(Array, Scalar):
    """A transparent homogeneous Container, for multivalued form elements.

    MultiValues combine aspects of :class:`Scalar` and
    :class:`Sequence` fields, allowing all values of a repeated `(key,
    value)` pair to be captured and used.

    MultiValues take on the name of their child and have no identity
    of their own when flattened.  Elements are mostly sequence-like
    and can be indexed and iterated. However the :attr:`.u` or
    :attr:`.value` are scalar-like, and return values from the first
    element in the sequence.

    """

    def u(self):
        """The .u of the first item in the sequence, or u''."""
        if not self:
            return u''
        else:
            return self[0].u

    def _set_u(self, value):
        if not self:
            self.append(None)
        self[0].u = value

    u = property(u, _set_u)
    del _set_u

    def value(self):
        """The .value of the first item in the sequence, or None."""
        if not self:
            return None
        else:
            return self[0].value

    def _set_value(self, value):
        if not self:
            self.append(None)
        self[0].value = value

    value = property(value, _set_value)
    del _set_value

    def __nonzero__(self):
        # this is a little troubling, given that it may not match the
        # appearance of the element in a scalar context.
        return len(self)


class Mapping(Container, dict):
    """Base of mapping-like Containers."""

    field_schema = ()
    """TODO: doc field_schema"""

    def __init__(self, value=Unspecified, **kw):
        Container.__init__(self, **kw)
        if not self.field_schema:
            raise TypeError("%r dictionary type has no fields defined" % (
                type(self).__name__))
        self._reset()
        if value is not Unspecified:
            self.set(value)

    def __setitem__(self, key, value):
        if not key in self:
            raise TypeError('May not set unknown key %r on %s %r' %
                            (key, type(self).__name__, self.name))
        self[key].set(value)

    def __delitem__(self, key):
        # this may be overly pedantic
        if key not in self:
            raise KeyError(key)
        raise TypeError('%s keys are immutable.' % type(self).__name__)

    def may_contain(self, key):
        """Return True if the element schema allows a field named **key**."""
        return key in self

    def clear(self):
        raise TypeError('%s keys are immutable.' % type(self).__name__)

    def _reset(self):
        """Place blank children in all fields."""
        for member_schema in self.field_schema:
            key = member_schema.name
            dict.__setitem__(
                self, key, member_schema(parent=self))

    def popitem(self):
        raise TypeError('%s keys are immutable.' % type(self).__name__)

    def pop(self, key):
        if key not in self:
            raise KeyError(key)
        raise TypeError('%s keys are immutable.' % type(self).__name__)

    def update(self, *dictish, **kwargs):
        """Update with keys from dict-like *\*dictish* and *\*\*kwargs*"""
        if len(dictish) > 1:
            raise TypeError(
                "update expected at most 1 arguments, got %s" % len(dictish))
        elif dictish:
            for key, value in to_pairs(dictish[0]):
                self[key] = value
        for key, value in kwargs.iteritems():
            self[key] = value

    def setdefault(self, key, default=None):
        # The key will always either be present or not creatable.
        raise TypeError('%s keys are immutable.' % type(self).__name__)

    def get(self, key, default=None):
        if key not in self:
            raise KeyError(
                'immutable %s %s schema does not contain key %r.' % (
                    type(self).__name__, self.name, key))
        # default will never be used.
        return self[key]

    @property
    def children(self):
        # order not guaranteed
        return self.itervalues()

    def set(self, value):
        """TODO: doc set()"""
        self.raw = value
        pairs = to_pairs(value)
        self._reset()

        seen = set()
        converted = True
        for key, value in pairs:
            if not self.may_contain(key):
                raise KeyError(
                    '%s %r schema does not allow key %r' % (
                        type(self).__name__, self.name, key))
            converted &= self[key].set(value)
            seen.add(key)
        required = set(self.iterkeys())
        if seen != required:
            missing = required - seen
            raise TypeError(
                'all keys required for a set() operation, missing %s.' % (
                    ','.join(repr(key) for key in missing)))
        return converted

    def _set_flat(self, pairs, sep):
        if self.name is None:
            possibles = pairs  # accept all
        else:
            possibles = []
            prefix = self.name + sep
            plen = len(prefix)
            for key, value in pairs:
                if key == prefix:
                    # No flat representation of mappings, ignore.
                    pass
                if key.startswith(prefix):
                    # accept child element
                    possibles.append((key[plen:], value))

        if not possibles:
            return

        for schema in self.field_schema:
            field = schema.name
            accum = []
            for key, value in possibles:
                if key.startswith(field):
                    accum.append((key, value))
            if accum:
                if dict.__contains__(self, field):
                    self[field].set_flat(accum, sep)
                else:
                    self[field] = schema()
                    self[field].set_flat(accum, sep=sep)

    def set_default(self):
        default = self.default_value
        if default is not None and default is not Unspecified:
            self.set(default)
        else:
            for child in self.children:
                child.set_default()

    def _index(self, name):
        return self[name]

    @property
    def u(self):
        """A string repr of the element."""
        pairs = ((key, value.u if isinstance(value, Container)
                               else repr(value.u).decode('raw_unicode_escape'))
                  for key, value in self.iteritems())
        return u'{%s}' % u', '.join(
            u"%s: %s" % (repr(k).decode('raw_unicode_escape'), v)
            for k, v in pairs)

    @property
    def value(self):
        """The element as a regular Python dictionary."""
        return dict((key, value.value) for key, value in self.iteritems())

    @property
    def is_empty(self):
        """Mappings are never empty."""
        return False

    @assignable_class_property
    def field_schema_mapping(instance, cls):
        """A name -> schema mapping generated from :attr:`field_schema`."""
        if instance is not None:
            field_schema = instance.field_schema
        else:
            field_schema = cls.field_schema
        return dict((schema.name, schema) for schema in field_schema)

    def _field_schema_for(self, key):
        """Return the schema for field ``*key* or None."""
        for schema in self.field_schema:
            if schema.name == key:
                return schema
        return None


class Dict(Mapping, dict):
    """A mapping Container with named members."""

    policy = 'subset'
    """One of 'strict', 'subset' or 'duck'.  Default 'subset'.

    See :ref:`set_policy`
    """

    @class_cloner
    def of(cls, *fields):
        """TODO: doc of()"""
        # TODO: doc
        # TODO: maybe accept **kw?
        for field in fields:
            if isinstance(field, Element):
                raise TypeError("'of' must be initialized with types, got "
                                "instance %r" % field)

        unique_names = set(field.name for field in fields)
        # TODO: ensure these are types, not instances
        if len(unique_names) != len(fields):
            names = [field.name for field in fields]
            dupes = [name for name in unique_names if names.count(name) > 1]
            raise TypeError(
                "All fields in a %s must have unique names. "
                "Duplicates of: %s " % (
                    cls.__name__,
                    ', '.join(repr(f) for f in dupes)))

        cls.field_schema = fields
        return cls

    @classmethod
    def from_object(cls, obj, include=None, omit=None, rename=None, **kw):
        """Return an element initialized with an object's attributes.

        :param obj: any object
        :param include: optional, an iterable of attribute names to pull from
            *obj*, if present on the object.  Only these attributes will be
            included.
        :param omit: optional, an iterable of attribute names to ignore on
            **obj**.  All other attributes matching a named field on the Form
            will be included.
        :param rename: optional, a mapping of attribute-to-field name
            transformations.  Attributes specified in the mapping will be
            included regardless of *include* or *omit*.
        :param \*\*kw: keyword arguments will be passed to the element's
            constructor.

        *include* and *omit* are mutually exclusive.

        This is a convenience constructor for :meth:`set_by_object`::

          element = cls(**kw)
          element.set_by_object(obj, include, omit, rename)

        """
        self = cls(**kw)
        self.set_by_object(obj=obj, include=include, omit=omit, rename=rename)
        return self

    def set(self, value, policy=None):
        """TODO: doc set()"""
        self.raw = value
        pairs = to_pairs(value)
        self._reset()

        if policy is not None:
            assert policy in ('strict', 'subset', 'duck')
        else:
            policy = self.policy

        fields = self.field_schema_mapping
        seen = set()
        converted = True
        for key, value in pairs:
            if key not in fields:
                if policy != 'duck':
                    raise KeyError(
                        'Dict %r schema does not allow key %r' % (
                            self.name, key))
                continue
            if dict.__contains__(self, key):
                converted &= self[key].set(value)
            else:
                self[key] = el = fields[key]()
                converted &= el.set(value)
            seen.add(key)

        if policy == 'strict':
            required = set(fields.iterkeys())
            if seen != required:
                missing = required - seen
                raise TypeError(
                    'strict-mode Dict requires all keys for '
                    'a set() operation, missing %s.' % (
                        ','.join(repr(key) for key in missing)))
        return converted

    def set_by_object(self, obj, include=None, omit=None, rename=None):
        """Set fields with an object's attributes.

        :param obj: any object
        :param include: optional, an iterable of attribute names to pull from
            *obj*, if present on the object.  Only these attributes will be
            included.
        :param omit: optional, an iterable of attribute names to ignore on
            **obj**.  All other attributes matching a named field on the Form
            will be included.
        :param rename: optional, a mapping of attribute-to-field name
            transformations.  Attributes specified in the mapping will be
            included regardless of *include* or *omit*.

        *include* and *omit* are mutually exclusive.

        Sets fields on *self*, using as many attributes as possible from
        *obj*.  Object attributes that do not correspond to field names are
        ignored.

        Mapping instances have two corresponding methods useful for
        round-tripping values in and out of your domain objects.

        .. testsetup::

          # FIXME
          from flatland import Form, String
          class UserForm(Form):
              login = String
              password = String
              verify_password = String

          class User(object):
              def __init__(self, login=None, password=None):
                  self.login = login
                  self.password = password

        :meth:`update_object` performs the inverse of :meth:`set_object`, and
        :meth:`slice` is useful for constructing new objects.

        .. doctest::

          >>> user = User('biff', 'secret')
          >>> form = UserForm()
          >>> form.set_by_object(user)
          >>> form['login'].value
          u'biff'
          >>> form['password'] = u'new-password'
          >>> form.update_object(user, omit=['verify_password'])
          >>> user.password
          u'new-password'
          >>> user_keywords = form.slice(omit=['verify_password'], key=str)
          >>> sorted(user_keywords.keys())
          ['login', 'password']
          >>> new_user = User(**user_keywords)

        """
        fields = set(self.iterkeys())
        attributes = fields.copy()
        if rename:
            rename = list(to_pairs(rename))
            attributes.update(key for key, value in rename
                                  if value in attributes)
        if omit:
            omit = list(omit)
            attributes.difference_update(omit)

        possible = ((attr, getattr(obj, attr))
                    for attr in attributes
                    if hasattr(obj, attr))

        sliced = keyslice_pairs(possible, include=include,
                                omit=omit, rename=rename)
        final = dict((key, value)
                     for key, value in sliced
                     if key in fields)
        self.set(final)

    def update_object(self, obj, include=None, omit=None, rename=None,
                      key=str):
        """Update an object's attributes using the element's values.

        Produces a :meth:`slice` using *include*, *omit*, *rename* and
        *key*, and sets the selected attributes on *obj* using
        ``setattr``.

        :returns: nothing. *obj* is modified directly.

        """
        data = self.slice(include=include, omit=omit, rename=rename, key=key)
        for attribute, value in data.iteritems():
            setattr(obj, attribute, value)

    def slice(self, include=None, omit=None, rename=None, key=None):
        """Return a ``dict`` containing a subset of the element's values."""
        return dict(
            keyslice_pairs(
                ((key, element.value) for key, element in self.iteritems()),
                include=include, omit=omit, rename=rename, key=key))


class SparseDict(Dict):
    """A Mapping which may contain a subset of the schema's allowed keys.

    This differs from :class:`Dict` in that new instances are not created with
    empty values for all possible keys.  In addition, mutating operations are
    allowed so long as the operations operate within the schema.  For example,
    you may :meth:`pop` and ``del`` members of the mapping.

    """

    #: The subset of fields to autovivify on instantiation.
    #:

    #: May be ``None`` or ``'required'``.  If ``None``, mappings will be
    #: created empty and mutation operations are unrestricted within the
    #: bounds of the :attr:`field_schema`.  If ``required``, fields with
    #: :attr:`optional` of ``False`` will always be present after
    #: instantiation, and attempts to remove them from the mapping with ``del``
    #: and friends will raise ``TypeError``.
    minimum_fields = None  # 'required'

    def may_contain(self, key):
        return key in self or self._field_schema_for(key) is not None

    def _reset(self):
        dict.clear(self)
        for member_schema in self.field_schema:
            key = member_schema.name
            if self.minimum_fields is None or member_schema.optional:
                continue
            dict.__setitem__(
                self, key, member_schema(parent=self))

    def __setitem__(self, key, value):
        schema = self._field_schema_for(key)
        if not dict.__contains__(self, key):
            if schema is None:
                raise TypeError('May not set unknown key %r on %s %r' %
                                (key, type(self).__name__, self.name))
            elif isinstance(value, schema):
                value.parent = self
                dict.__setitem__(self, key, value)
                return
            dict.__setitem__(self, key, schema(value, parent=self))
        elif isinstance(value, schema):
            value.parent = self
            dict.__setitem__(self, key, value)
        else:
            self[key].set(value)

    def __delitem__(self, key):
        if self.minimum_fields is None:
            try:
                dict.__delitem__(self, key)
                return
            except KeyError:
                if not self.may_contain(key):
                    raise TypeError(
                        'May not request del for unknown key %r on %s %r' %
                        (key, type(self).__name__, self.name))
                raise
        if key in self:
            optional = self[key].optional
        else:
            schema = self._field_schema_for(key)
            if schema is None:
                raise TypeError(
                    'May not request del for unknown key %r on %s %r' %
                    (key, type(self).__name__, self.name))
            optional = schema.optional
        if not optional:
            raise TypeError('May not delete required key %r on %s %r' %
                            (key, type(self).__name__, self.name))
        dict.__delitem__(self, key)

    def clear(self):
        self._reset()

    def popitem(self):
        raise NotImplementedError

    def pop(self, key):
        if key not in self:
            raise KeyError(key)
        if self.minimum_fields == 'required' and not self[key].optional:
            raise TypeError('May not pop required key %r on %s %r' %
                            (key, type(self).__name__, self.name))
        return dict.pop(self, key)

    def setdefault(self, key, default=None):
        if not self.may_contain(key):
            raise TypeError('Key %r not allowed in %s %r' %
                            (key, type(self).__name__, self.name))

        if key in self:
            child = self[key]
            if not child.is_empty:
                return child.value
        else:
            self[key] = child = self.field_schema_mapping[key]()
        child.set(default)
        return default

    @property
    def is_empty(self):
        for _ in self.iterkeys():
            return False
        return True

    def set_default(self):
        default = self.default_value
        if default is not None and default is not Unspecified:
            self.set(default)
        elif self.minimum_fields is None:
            self._reset()
        elif self.minimum_fields == 'required':
            self._reset()
            for schema in self.field_schema:
                if schema.optional:
                    continue
                self[schema.name] = schema.from_defaults()
        else:
            raise RuntimeError("Unknown minimum_fields setting %r" %
                               (self.minimum_fields,))


for cls_name in __all__:
    autodocument_from_superclasses(globals()[cls_name])
del cls_name
