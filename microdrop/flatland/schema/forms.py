# -*- coding: utf-8; fill-column: 78 -*-
"""Class attribute-style declarative schema construction."""
from flatland.schema.base import Element
from flatland.schema.containers import Dict


__all__ = 'Form',


class _MetaForm(type):
    """Allows fields to be specified as class attribute declarations.

    Processes class declarations of the form:

      from flatland import Form, String

      class MyForm(Form):
          name = String
          favorite_color = String.using(optional=True)

    and converts them to a :attr:`~flatland.Dict.field_schema` specification
    at class construction time.  Forms may inherit from other Forms, with
    schema declarations following normal Python class property inheritance
    semantics.

    """

    def __new__(self, class_name, bases, members):
        fields = _ElementCollection()

        # collect existing fields from super classes in __mro__ order
        for base in bases:
            fields.add_unseen(getattr(base, 'field_schema', ()))

        # add / replace fields supplied in a field_schema on this class
        fields.add_and_overwrite(members.get('field_schema', ()))

        # add / replace fields declared as attributes on this class
        declared_fields = []
        for name, value in members.items():
            # TODO warn about instances found here?
            if isinstance(value, type) and issubclass(value, Element):
                if name != value.name:
                    value = value.named(name)
                declared_fields.append(value)
                del members[name]
        fields.add_and_overwrite(declared_fields)

        # the new type's field_schema is the final result of all this
        members['field_schema'] = fields.elements
        return type.__new__(self, class_name, bases, members)


class _ElementCollection(object):
    """Internal helper collection for calculating Form field inheritance."""

    def __init__(self):
        self.elements = []
        self.names = set()

    def add_unseen(self, iterable):
        """Add new items from *iterable*."""
        for field in iterable:
            if field.name in self.names:
                continue
            self.elements.append(field)
            self.names.add(field.name)

    def add_and_overwrite(self, iterable):
        """Add from *iterable*, replacing existing items of the same name."""
        for field in iterable:
            if field.name in self.names:
                for have in self.elements:
                    if have.name == field.name:
                        self.elements.remove(have)
                        break
            self.names.add(field.name)
            self.elements.append(field)


class Form(Dict):
    """A declarative collection of named fields.

    Forms behave like :class:`flatland.Dict`, but are defined with Python
    class syntax:

    .. doctest::

      >>> from flatland import Form, String
      >>> class HelloForm(Form):
      ...     hello = String
      ...     world = String
      ...

    Fields are assigned names from the declaration.  If a named schema is
    used, a renamed copy will be assigned to the Form.

    .. doctest::

      >>> class HelloForm(Form):
      ...     hello = String.named('hello')   # redundant
      ...     world = String.named('goodbye') # will be renamed 'world'
      ...
      >>> form = HelloForm()
      >>> sorted(form.keys())
      [u'hello', u'world']

    Forms may embed other container fields and other forms:

    .. doctest::

      >>> from flatland import List
      >>> class BigForm(Form):
      ...     main_hello = HelloForm
      ...     alt_hello = List.of(String.named('alt_name'),
      ...                         HelloForm.named('alt_hello'))
      ...

    This would create a form with one ``HelloForm`` embedded as
    ``main_hello``, and a list of zero or more dicts, each containing an
    ``alt_name`` and another ``HelloForm`` named ``alt_hello``.

    Forms may inherit from other Forms or Dicts.  Field declared in a subclass
    will override those of a superclass.  Multiple inheritance is supported.

    The special behavior of ``Form`` is limited to class construction time
    only.  After construction, the ``Form`` acts exactly like a
    :class:`~flatland.Dict`.  In particular, fields declared in class
    attribute style do **not** remain class attributes.  They are removed from
    the class dictionary and placed in the
    :attr:`~flatland.Dict.field_schema`:

    .. doctest::

      >>> hasattr(HelloForm, 'hello')
      False
      >>> sorted([field.name for field in HelloForm.field_schema])
      [u'hello', u'world']

    The order of ``field_schema`` after construction is undefined.

    """

    __metaclass__ = _MetaForm

    # TODO:
    #   some kind of validator merging helper?  or punt?
