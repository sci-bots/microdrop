# -*- coding: utf-8; fill-column: 78 -*-
import re
#import string
import sys

try:
    import threading
except ImportError:                                           # pragma:nocover
    import dummy_threading as threading


# derived from ASPN Cookbook (#36302)
class lazy_property(object):
    """An @property that is only calculated once.

    The results of the decorated function are stored in the instance
    dictionary after the first access.  Subsequent accesses are serviced out
    of the __dict__ by Python at native attribute access speed.

    """

    def __init__(self, deferred):
        self._deferred = deferred

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = self._deferred(obj)
        setattr(obj, self._deferred.func_name, value)
        return value


class assignable_property(object):
    """A @property, computed by default but assignable on a per-instance basis.

    Similar to ``property``, except that the attribute may be assigned to and
    assignments may be deleted.

    May be used as a decorator.

    """

    def __init__(self, fget, name=None, doc=None):
        self.name = name or fget.__name__
        self.fget = fget
        self.__doc__ = doc or fget.__doc__

    def __get__(self, instance, cls):
        if instance is None:
            # Class.prop == None
            return None
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        else:
            return self.fget(instance)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

    def __delete__(self, instance):
        try:
            del instance.__dict__[self.name]
        except KeyError:
            raise AttributeError("%r object has no overriden attribute %r" % (
                type(instance).__name__, self.name))


class assignable_class_property(object):
    """A read/write property for access on a class or an instance.

    Similar to :class:`assignable_property`, except that access as a class
    attribute will also return a computed value.

    The decorated function will be passed two arguments: ``instance`` and
    ``class`` (the same signature as the descriptor __get__ protocol).
    Instance will be ``None`` if the attribute access was against the class.

    Note that assignments at the class level are not intercepted by this
    property.  They will replace the property on the class.

    May be used as a decorator.

    """

    def __init__(self, fget, name=None, doc=None):
        self.name = name or fget.__name__
        self.fget = fget
        self.__doc__ = doc or fget.__doc__

    def __get__(self, instance, cls):
        if instance is None:
            return self.fget(None, cls)
        if self.name in instance.__dict__:
            return instance.__dict__[self.name]
        else:
            return self.fget(instance, cls)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

    def __delete__(self, instance):
        try:
            del instance.__dict__[self.name]
        except KeyError:
            raise AttributeError("%r object has no overridden attribute %r" % (
                type(instance).__name__, self.name))


class class_cloner(object):
    """A class-copying ``classmethod``.

    Calls the decorated method as a classmethod, passing a copy of the class.
    The copy will be a direct subclass of the class the method is invoked on.

    The class_cloner is only visible at the class level.  Instance access is
    proxied to the instance dictionary.

    """

    def __init__(self, fn):
        self.name = fn.__name__
        self.cloner = classmethod(fn)
        self.__doc__ = fn.__doc__

    def __get__(self, instance, cls):
        if instance is not None:
            try:
                return instance.__dict__[self.name]
            except KeyError:
                raise AttributeError(self.name)
        members = {'__doc__': getattr(cls, '__doc__', '')}
        try:
            members['__module__'] = \
              sys._getframe(1).f_globals['__name__']
        except (AttributeError, KeyError, TypeError):  # pragma: nocover
            members['__module__'] = cls.__module__
        clone = type(cls.__name__, (cls,), members)
        return self.cloner.__get__(None, clone)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

    def __delete__(self, instance):
        try:
            del instance.__dict__[self.name]
        except KeyError:
            raise AttributeError("%r object has no attribute %r" % (
                type(instance).__name__, self.name))


class as_mapping(object):
    """Provide a mapping view of an instance.

    Similar to vars(), but effective on extension types and will invoke
    descriptors on access.

    """

    __slots__ = 'target',

    def __init__(self, target):
        self.target = target

    def __getitem__(self, item):
        try:
            if isinstance(item, unicode):
                return getattr(self.target, item.encode('ascii'))
            return getattr(self.target, item)
        except (AttributeError, UnicodeError):
            raise KeyError(item)

    def __contains__(self, item):
        if isinstance(item, unicode):
            try:
                return hasattr(self.target, item.encode('ascii'))
            except UnicodeError:
                return False
        return hasattr(self.target, item)

    def __iter__(self):
        return iter(dir(self.target))


class adict(dict):
    """Allow dict keys to be accessed with getattr()."""

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(attr)


def re_ucompile(pattern, flags=0):
    """Compile a regex with re.UNICODE on by default."""
    return re.compile(pattern, flags | re.UNICODE)


#_alphanum = set((string.digits + string.letters).decode('ascii'))
_alphanum = set(('0123456789' + 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ').decode('ascii'))


def re_uescape(pattern):
    """A unicode-friendly version of re.escape."""
    mutable = list(pattern)
    for idx, char in enumerate(pattern):
        if char not in _alphanum:
            if char == u"\000":
                mutable[idx] = u"\\000"
            else:
                mutable[idx] = u"\\" + char
    return u''.join(mutable)


def luhn10(number):
    """Return True if the number passes the Luhn checksum algorithm."""

    sum = 0
    while number:
        r = number % 100
        number //= 100
        z = r % 10
        r = r // 10 * 2
        sum += r // 10 + r % 10 + z

    return 0 == sum % 10


def to_pairs(dictlike):
    """Yield (key, value) pairs from any dict-like object.

    Implements an optimized version of the dict.update() definition of
    "dictlike".

    """
    if hasattr(dictlike, 'iteritems'):
        return dictlike.iteritems()
    elif hasattr(dictlike, 'keys'):
        return ((key, dictlike[key]) for key in dictlike.keys())
    elif hasattr(dictlike, '_asdict'): # namedtuple interface
        return dictlike._asdict().iteritems()
    else:
        return ((key, value) for key, value in dictlike)


def keyslice_pairs(pairs, include=None, omit=None, rename=None, key=None):
    """Filter (key, value) pairs by key and return a subset.

    :param pairs: an iterable of ``(key, value)`` pairs (2-tuples).

    :param include: optional, a sequence of key values.  If supplied, only
        pairs whose key is a member of this sequence will be returned.

    :param omit: optional, a sequence of key values. If supplied, all pairs
        will be returned, save those whose key is a member of this sequence.

    :param rename: optional, a mapping or sequence of 2-tuples specifying a
        key-to-key translation.  A pair whose key has been renamed by this
        translation will always be emitted, regardless of *include* or *omit*
        rules.  The mapping will be converted to a dict internally, and keys
        must be hashable.

    :param key: optional, a function of one argument that is used to extract a
        comparison key from the first item of each pair.  Similar to the
        ``key`` parameter to Python's ``sort`` and ``sorted``.  Useful for
        transforming unicode keys to bytestrings with ```key=str``, adding or
        removing prefixes en masse, etc.

    :returns: yields ``(key, value)`` pairs.

    """
    if include and omit:
        raise TypeError('received include and omit, specify only one')

    include = set(include) if include else False
    omit = set(omit) if omit else False
    rename = dict(to_pairs(rename)) if rename else False
    keyfunc = key
    del key

    for key, value in pairs:
        if keyfunc:
            key = keyfunc(key)
        if rename and key in rename:
            yield (rename[key], value)
            continue
        if include:
            if key not in include:
                continue
        elif omit:
            if key in omit:
                continue
        yield key, value


class Maybe(object):
    """A ternary logic value, bitwise-comparable to bools"""

    def __and__(self, other):
        if other is True or other is self:
            return self
        elif other is False:
            return False
        return NotImplemented
    __rand__ = __and__

    def __or__(self, other):
        if other is False or other is self:
            return self
        elif other is True:
            return True
        return NotImplemented
    __ror__ = __or__

    def not_(self, other):
        """Negate a ternary value.

        (Python doesn't allow useful overriding of ``not``.)

        """
        if other is self:
            return other
        elif other is True:
            return False
        elif other is False:
            return True
        else:
            raise TypeError(type(other).__name__)

    def truth(self, other):
        if other is self:
            return True
        elif other is True:
            return True
        elif other is False:
            return False
        else:
            raise TypeError(type(other).__name__)

    def __nonzero__(self):
        raise NotImplementedError()

    def __str__(self):
        return 'Maybe'
    __repr__ = __str__


Maybe = Maybe()


def named_int_factory(name, value, doc=''):
    """Return a unique integer *value* with a str() and repr() of *name*."""
    report_name = lambda self: name
    cls = type(name, (int,), dict(
        __doc__=doc, __str__=report_name, __repr__=report_name))
    return cls(value)


def autodocument_from_superclasses(cls):
    """Fill in missing documentation on overridden methods.

    Can be used as a class decorator.
    """
    undocumented = []
    for name, attribute in cls.__dict__.items():
        # is it a method on the class that is locally undocumented?
        if hasattr(attribute, '__call__') and not attribute.__doc__:
            # don't muck with builtins
            if not hasattr(attribute, '__module__'):
                continue
            # find docs on a superclass
            for supercls in cls.__bases__:
                try:
                    superdoc = getattr(supercls, name).__doc__
                    if superdoc:
                        setattr(attribute, '__doc__', superdoc)
                        break
                except (AttributeError, TypeError):
                    pass
    return cls


# derived from SQLAlchemy (http://www.sqlalchemy.org/); MIT License
class _symbol(object):

    def __init__(self, name):
        """Construct a new named symbol."""
        assert isinstance(name, str)
        self.__name__ = self.name = name

    def __reduce__(self):
        return symbol, (self.name,)

    def __repr__(self):
        return self.name
_symbol.__name__ = 'symbol'


# derived from SQLAlchemy (http://www.sqlalchemy.org/); MIT License
class symbol(object):
    """A constant symbol.

    >>> symbol('foo') is symbol('foo')
    True
    >>> symbol('foo')
    foo

    A slight refinement of the MAGICCOOKIE=object() pattern.  The primary
    advantage of symbol() is its repr().  They are also singletons.

    Repeated calls of symbol('name') will all return the same instance.

    """
    symbols = {}
    _lock = threading.Lock()

    def __new__(cls, name):
        cls._lock.acquire()
        try:
            sym = cls.symbols.get(name)
            if sym is None:
                cls.symbols[name] = sym = _symbol(name)
            return sym
        finally:
            symbol._lock.release()


Unspecified = symbol('Unspecified')
