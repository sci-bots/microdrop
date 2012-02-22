from weakref import WeakKeyDictionary

from flatland.util import symbol


Deleted = symbol('deleted')


class DictLike(object):

    def iteritems(self):  # pragma: nocover
        raise NotImplementedError

    def items(self):
        return list(self.iteritems())

    def iterkeys(self):
        return (item[0] for item in self.iteritems())

    def keys(self):
        return list(self.iterkeys())

    def itervalues(self):
        return (item[1] for item in self.iteritems())

    def values(self):
        return list(self.itervalues())

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def copy(self):
        return dict(self.iteritems())

    def popitem(self):
        raise NotImplementedError

    def __contains__(self, key):
        return key in self.iterkeys()

    def __nonzero__(self):
        return bool(self.copy())

    def __eq__(self, other):
        return self.copy() == other

    def __ne__(self, other):
        return self.copy() != other

    def __repr__(self):
        return repr(self.copy())


class _TypeLookup(DictLike):
    __slots__ = 'base', 'map', 'descriptor_id'

    def __init__(self, cls, descriptor):
        self.base = cls
        self.map = descriptor.map
        self.descriptor_id = id(descriptor)

    def __getitem__(self, key):
        for frame in self._frames():
            try:
                value = frame[key]
            except KeyError:
                pass
            else:
                if value is Deleted:
                    raise KeyError(key)
                return value
        raise KeyError(key)

    def __setitem__(self, key, value):
        self._base_frame[key] = value

    def __delitem__(self, key):
        self[key]  # must exist to delete
        self._base_frame[key] = Deleted

    def clear(self):
        frame = self._base_frame
        for key in self.iterkeys():
            frame[key] = Deleted

    def pop(self, key, *default):
        try:
            current = self[key]
        except KeyError:
            if not default:
                raise KeyError(key)
            return default[0]
        self[key] = Deleted
        return current

    def setdefault(self, key, default):
        return self._base_frame.setdefault(key, default)

    def update(self, *iterable, **values):
        simplified = dict(*iterable, **values)
        self._base_frame.update(simplified)

    def iteritems(self):
        seen = set()
        for frame in self._frames():
            for key, value in frame.iteritems():
                if key not in seen:
                    seen.add(key)
                    if value is not Deleted:
                        yield (key, value)

    def _frames(self):
        for cls in self.base.__mro__:
            member = cls.__dict__.get('properties')
            if cls not in self.map:
                if member is None or id(member) != self.descriptor_id:
                    continue
                self.map.setdefault(cls, member.initial_set)
            yield self.map[cls]
            if member is not None and id(member) == self.descriptor_id:
                break

    @property
    def _base_frame(self):
        try:
            return self.map[self.base]
        except KeyError:
            pass
        if 'properties' in self.base.__dict__:
            member = self.base.__dict__['properties']
            if id(member) == self.descriptor_id:
                return self.map.setdefault(self.base, member.initial_set)
        return self.map.setdefault(self.base, {})


class local_storage(dict):
    """A marker type for local storage overlays."""


class _InstanceLookup(DictLike):
    __slots__ = 'local', 'class_lookup'

    def __init__(self, instance, class_lookup):
        try:
            local = instance.__dict__.setdefault('properties', local_storage())
        except AttributeError:
            # Descriptor not supported for slots types.
            raise AttributeError(
                "%s object has no attribute 'properties'" % (
                    instance.__class__))
        self.local = local
        self.class_lookup = class_lookup

    def __getitem__(self, key):
        try:
            value = self.local[key]
        except KeyError:
            pass
        else:
            if value is Deleted:
                raise KeyError(key)
            return value
        return self.class_lookup[key]

    def __setitem__(self, key, value):
        self.local[key] = value

    def __delitem__(self, key):
        self[key]  # must exist to delete
        self.local[key] = Deleted

    def clear(self):
        self.local.clear()
        for key in self.class_lookup.keys():
            self.local[key] = Deleted

    def pop(self, key, *default):
        try:
            return self.local.pop(key)
        except KeyError:
            return self.class_lookup.pop(key, *default)

    def setdefault(self, key, default):
        try:
            return self[key]
        except KeyError:
            return self.local.setdefault(key, default)

    def update(self, *iterable, **values):
        simplified = dict(*iterable, **values)
        self.local.update(simplified)

    def iteritems(self):
        seen = set()
        for key, value in self.local.iteritems():
            seen.add(key)
            if value is not Deleted:
                yield key, value
        for key, value in self.class_lookup.iteritems():
            if key not in seen:
                seen.add(key)
                if value is not Deleted:  # pragma: nocover  (coverage bug)
                    yield key, value


class Properties(object):

    def __init__(self, *iterable, **initial_set):
        simplified = dict(*iterable, **initial_set)
        self.initial_set = simplified
        self.map = WeakKeyDictionary()

    def __get__(self, instance, cls):
        class_lookup = _TypeLookup(cls, self)
        if instance is None:
            return class_lookup
        try:
            local = instance.__dict__['properties']
        except (KeyError, AttributeError):
            pass
        else:
            # wholesale assignments to instances replace the inheritance
            # routine entirely
            if type(local) is not local_storage:
                return local
        return _InstanceLookup(instance, class_lookup)

    def __set__(self, instance, value):
        instance.__dict__['properties'] = value
