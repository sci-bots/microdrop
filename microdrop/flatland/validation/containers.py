# -*- coding: utf-8; fill-column: 78 -*-
import operator
from ..schema import Slot
from . base import N_, P_, Validator


class NotDuplicated(Validator):
    """A sequence member validator that ensures all sibling values are unique.

    Marks the second and any subsequent occurrences of a value as
    invalid.  Only useful on immediate children of sequence fields
    such as :class:`flatland.List`.

    Example:

    .. testcode::

      import flatland
      from flatland.validation import NotDuplicated

      validator = NotDuplicated(failure="Please enter each color only once.")
      schema = List.of(String.named('favorite_color')).\
                    using(validators=[validator])

    **Attributes**

    .. attribute:: comparator

      A callable boolean predicate, by default ``operator.eq``.
      Called positionally with two arguments, *element* and *sibling*.

      Can be used as a filter, for example ignoring any siblings that
      have been marked as "deleted" by a checkbox in a web form:

      .. testcode::

        from flatland import Form, List, String, Integer, Boolean
        from flatland.validation import NotDuplicated

        def live_addrs(element, sibling):
            thisval, thatval = element.value, sibling.value
            # data marked as deleted is never considered a dupe
            if thisval['deleted'] or thatval['deleted']:
                return False
            # compare elements on 'street' & 'city', ignoring 'id'
            return (thisval['street'] == thatval['street'] and
                    thisval['city'] == thatval['city'])

        class Address(Form):
            validators = [NotDuplicated(comparator=live_addrs)]

            id = Integer.using(optional=True)
            deleted = Boolean
            street = String
            city = String

        schema = List.of(Address)

    .. testcode:: :hide:

        data = {'id': 1, 'deleted': False, 'street': 'a', 'city': 'b'}
        el = schema([data, data])
        assert not el.validate()
        del el[:]
        el.set([data, dict(data, deleted=True)])
        assert el.validate()

    **Messages**

    .. attribute:: failure

      Emitted on an element that has already appeared in a parent
      sequence.  ``container_label`` will substitute the label of the
      container.  ``position`` is the position of the element in the
      parent sequence, counting up from 1.

    """

    # TRANSLATORS: NotDuplicated.failure
    failure = N_(u'%(label)s may not be repeated within %(container_label)s.')

    comparator = operator.eq

    def validate(self, element, state):
        if element.parent is None:
            raise TypeError(
                "%s validator must be applied to a child of a Container "
                "type; %s has no parent." % (
                    type(self).__name__,
                    element.name))
        container = element.parent
        if isinstance(container, Slot):
            container = container.parent
        valid, position = True, 0
        op = self.comparator
        for idx, sibling in enumerate(container.children):
            if sibling is element:
                position = idx + 1
                break
            if valid and op(element, sibling):
                valid = False
        if not valid:
            return self.note_error(
                element, state, 'failure',
                position=position, container_label=container.label)
        return True


class HasAtLeast(Validator):
    """A sequence validator that ensures a minimum number of members.

    May be applied to a sequence type such as a :class:`~flatland.List`.

    Example:

    .. testcode::

      from flatland import List, String
      from flatland.validation import HasAtLeast

      schema = List.of(String.named('wish')).\
                    using(validators=[HasAtLeast(minimum=3)])

    **Attributes**

    .. attribute:: minimum

      Any positive integer.

    **Messages**

    .. attribute:: failure

      Emitted if the sequence contains less than :attr:`minimum` members.
      ``child_label`` will substitute the label of the child schema.

    """

    minimum = 1

    # TRANSLATORS: HasAtLeast.failure
    failure = P_("%(label)s must contain at least one %(child_label)s",
                 "%(label)s must contain at least %(minimum)s "
                 "%(child_label)ss",
                 'minimum')

    def validate(self, element, state):
        assert hasattr(element, 'member_schema'), (
            'container-length validator is only applicable to sequence types.')

        # stupid edge case
        if not self.minimum:
            return True

        if element.value is None or len(element.value) < self.minimum:
            child_label = element.member_schema.label
            return self.note_error(element, state, 'failure',
                                   child_label=child_label)
        return True


class HasAtMost(Validator):
    """A sequence validator that ensures a maximum number of members.

    May be applied to a sequence type such as a :class:`~flatland.List`.

    Example:

    .. testcode::

      from flatland import List, String
      from flatland.validation import HasAtMost

      schema = List.of(String.named('wish')).\
                    using(validators=[HasAtMost(maximum=3)])

    **Attributes**

    .. attribute:: maximum

      Any positive integer.

    **Messages**

    .. attribute:: failure

      Emitted if the sequence contains more than :attr:`maximum` members.
      ``child_label`` will substitute the label of the child schema.

    """

    maximum = 1

    # TRANSLATORS: HasAtMost.failure
    failure = P_("%(label)s must contain at most one %(child_label)s",
                 "%(label)s must contain at most %(maximum)s "
                 "%(child_label)ss",
                 'maximum')

    def validate(self, element, state):
        assert hasattr(element, 'member_schema'), (
            'container-length validator is only applicable to sequence types.')

        if element.value and len(element.value) > self.maximum:
            child_label = element.member_schema.label
            return self.note_error(element, state, 'failure',
                                   child_label=child_label)
        return True


class HasBetween(Validator):
    """Validates that the number of members of a sequence lies within a range.

    May be applied to a sequence type such as a :class:`~flatland.List`.

    Example:

    .. testcode::

      from flatland import List, String
      from flatland.validation import HasBetween

      schema = List.of(String.named('wish')).\
                    using(validators=[HasBetween(minimum=1, maximum=3)])


    **Attributes**

    .. attribute:: minimum

      Any positive integer.

    .. attribute:: maximum

      Any positive integer.

    **Messages**

    .. attribute:: range

      Emitted if the sequence contains fewer than :attr:`minimum` members or
      more than :attr:`maximum` members. ``child_label`` will substitute the
      label of the child schema.

    .. attribute:: exact

      Like :attr:`range`, however this message is emitted if :attr:`minimum`
      and :attr:`maximum` are the same.

      .. testcode::

        schema = List.of(String.named('wish')).\
                      using(validators=[HasBetween(minimum=3, maximum=3)])

    """

    minimum = 1
    maximum = 1

    # TRANSLATORS: HasBetween.range
    range = P_("%(label)s must contain at least %(minimum)s and at most "
               "%(maximum)s %(child_label)s",
               "%(label)s must contain at least %(minimum)s and at most "
               "%(maximum)s %(child_label)ss",
               'maximum')

    # TRANSLATORS: HasBetween.exact
    exact = P_("%(label)s must contain exactly one %(child_label)s",
               "%(label)s must contain exactly %(minimum)s %(child_label)ss",
               'minimum')

    def __init__(self, **kw):
        Validator.__init__(self, **kw)
        if not self.maximum >= self.minimum >= 0:
            raise TypeError("Nonsensical minimum & maximum values (%r, %r)" %
                            (self.minimum, self.maximum))

    def validate(self, element, state):
        assert hasattr(element, 'member_schema'), (
            'container-length validator is only applicable to sequence types.')

        length = len(element.value) if element.value is not None else 0
        if self.minimum <= length <= self.maximum:
            return True

        message = 'exact' if self.minimum == self.maximum else 'range'
        child_label = element.member_schema.label
        return self.note_error(element, state, message,
                               child_label=child_label)
