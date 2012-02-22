"""Base functionality for fancy validation."""
from operator import attrgetter

from flatland.schema.util import find_i18n_function


N_ = lambda translatable: translatable
P_ = lambda *translatable: translatable
_ugettext_finder = attrgetter('ugettext')
_ungettext_finder = attrgetter('ungettext')


class Validator(object):
    """Base class for fancy validators."""

    def __init__(self, **kw):
        """Construct a validator.

        :param \*\*kw: override any extant class attribute on this instance.

        """
        cls = type(self)
        for attr, value in kw.iteritems():
            if hasattr(cls, attr):
                setattr(self, attr, value)
            else:
                raise TypeError("%s has no attribute %r, can not override." % (
                    cls.__name__, attr))

    def __call__(self, element, state):
        """Adapts Validator to the Element.validate callable interface."""
        return self.validate(element, state)

    def validate(self, element, state):
        """Validate an element returning True if valid.

        Abstract.

        :param element:
          an :class:`~flatland.schema.base.Element` instance.

        :param state:
          an arbitrary object.  Supplied by
          :meth:`Element.validate <flatland.schema.base.Element.validate>`.

        :returns: True if valid

        """
        return False

    def note_error(self, element, state, key=None, message=None, **info):
        """Record a validation error message on an element.

        :param element:
          An :class:`~flatland.schema.base.Element` instance.

        :param state:
          an arbitrary object.  Supplied by :meth:`Element.validate
          <flatland.schema.base.Element.validate>`.

        :param key: semi-optional, default None.
          The name of a message-holding attribute on this instance.  Will be
          used to ``message = getattr(self, key)``.

        :param message: semi-optional, default None.  A validation
          message.  Use to provide a specific message rather than look
          one up by *key*.

        :param \*\*info: optional.
          Additional data to make available to validation message
          string formatting.

        :returns: False

        Either *key* or *message* is required.  The message will have
        formatting expanded by :meth:`expand_message` and be appended to
        :attr:`element.errors <flatland.schema.base.Element.errors>`.

        Always returns False.  This enables a convenient shorthand when
        writing validators:

        .. testcode::

          from flatland.validation import Validator

          class MyValidator(Validator):
              my_message = 'Oh noes!'

              def validate(self, element, state):
                  if not element.value:
                      return self.note_error(element, state, 'my_message')
                  else:
                      return True

        .. testcode:: :hide:

          from flatland import String
          el = String()
          v = MyValidator()
          assert not v.validate(el, None)
          assert el.errors == ['Oh noes!']
          el.set('foo')
          assert v.validate(el, None)
          assert el.errors == ['Oh noes!']

        """
        message = message or getattr(self, key)
        if message:
            element.add_error(
                self.expand_message(element, state, message, **info))
        return False

    def note_warning(self, element, state, key=None, message=None, **info):
        """Record a validation warning message on an element.

        :param element:
          An :class:`~flatland.schema.base.Element` instance.

        :param state:
          an arbitrary object.  Supplied by :meth:`Element.validate
          <flatland.schema.base.Element.validate>`.

        :param key: semi-optional, default None.
          The name of a message-holding attribute on this instance.  Will be
          used to ``message = getattr(self, key)``.

        :param message: semi-optional, default None.  A validation
          message.  Use to provide a specific message rather than look
          one up by *key*.

        :param \*\*info: optional.
          Additional data to make available to validation message
          string formatting.

        :returns: False

        Either *key* or *message* is required.  The message will have
        formatting expanded by :meth:`expand_message` and be appended to
        :attr:`element.warnings <flatland.schema.base.Element.warnings>`.

        Always returns False.
        """
        message = message or getattr(self, key)
        if message:
            element.add_warning(
                self.expand_message(element, state, message, **info))
        return False

    def find_transformer(self, type, element, state, message):
        """Locate a message-transforming function, such as ugettext.

        Returns None or a callable.  The callable must return a
        message.  The call signature of the callable is expected to
        match ``ugettext`` or ``ungettext``:

        - If *type* is 'ugettext', the callable should take a message
          as a positional argument.

        - If *type* is 'ungettext', the callable should take three
          positional arguments: a message for the singular form, a
          message for the plural form, and an integer.

        Subclasses may override this method to provide advanced
        message transformation and translation functionality, on a
        per-element or per-message granularity if desired.

        The default implementation uses the following logic to locate
        a transformer:

        1.  If *state* has an attribute or item named *type*, return that.

        2.  If the *element* or any of its parents have an attribute
            named *type*, return that.

        3.  If the schema of *element* or the schema of any of its
            parents have an attribute named *type*, return that.

        4.  If *type* is in ``__builtin__``, return that.

        5.  Otherwise return ``None``.

        """
        if hasattr(state, type):
            return getattr(state, type)
        if hasattr(state, '__getitem__'):
            try:
                return state[type]
            except KeyError:
                pass

        if type == 'ugettext':
            finder = _ugettext_finder
        elif type == 'ungettext':
            finder = _ungettext_finder
        else:
            raise RuntimeError("Unknown transformation %r" % type)
        return find_i18n_function(element, finder)

    def expand_message(self, element, state, message, **extra_format_args):
        """Apply formatting to a validation message.

        :param element:
          an :class:`~flatland.schema.base.Element` instance.

        :param state:
          an arbitrary object.  Supplied by
          :meth:`Element.validate <flatland.schema.base.Element.validate>`.

        :param message: a string, 3-tuple or callable.
          If a 3-tuple, must be of the form ('single form', 'plural form',
          n_key).

          If callable, will be called with 2 positional arguments (*element*,
          *state*) and must return a string or 3-tuple.

        :param \*\*extra_format_args: optional.
          Additional data to make available to validation message
          string formatting.

        :returns: the formatted string

        See :ref:`Message Templating`, :ref:`Message Pluralization` and
        :ref:`Message Internationalization` for full information on how
        messages are expanded.

        """
        if callable(message):
            message = message(element, state)

        ugettext = self.find_transformer('ugettext', element, state, message)

        format_map = as_format_mapping(
            extra_format_args, state, self, element,
            transform=ugettext)

        if isinstance(message, tuple):
            ungettext = self.find_transformer(
                'ungettext', element, state, message)

            single, plural, n_key = message
            try:
                n = format_map[n_key]
                try:
                    n = int(n)
                except TypeError:
                    pass
            except KeyError:
                n = n_key

            if ungettext:
                message = ungettext(single, plural, n)
            else:
                if ugettext:
                    single = ugettext(single)
                    plural = ugettext(plural)
                message = single if n == 1 else plural
        elif ugettext:
            message = ugettext(message)

        return message % format_map


class as_format_mapping(object):
    """A unified, optionally transformed, mapping view over multiple instances.

    Allows regular instance attributes to be accessed by "%(attrname)s" in
    string formats.  Dictionaries may be included as well.  Optionally
    passes values through a ``transform`` (such ``gettext``) before
    returning.

    """

    __slots__ = 'targets', 'transform'

    def __init__(self, *targets, **kw):
        self.targets = [t for t in targets if t is not None]
        self.transform = kw.pop('transform', None)
        if kw:
            raise TypeError('unexpected keyword argument')

    def __getitem__(self, item):
        for target in self.targets:
            # try target[item] first
            if hasattr(target, '__getitem__'):
                try:
                    value = target[item]
                    break
                except (LookupError, TypeError):
                    pass
            # then target.item
            try:
                value = getattr(target, item)
                break
            except AttributeError:
                pass
        else:
            # not found on any target
            raise KeyError(item)

        if self.transform:
            return self.transform(value)
        else:
            return value

    def __contains__(self, item):
        try:
            self[item]
            return True
        except KeyError:
            return False

    def __iter__(self):
        keys = set()
        for target in self.targets:
            keys |= set(dir(target))
        return iter(keys)
