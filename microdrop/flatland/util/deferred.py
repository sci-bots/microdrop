import sys
from types import ModuleType


__all__ = ['deferred_module']


class deferred_module(ModuleType):
    """A module whose __all__ members are loaded on first access."""

    @classmethod
    def shadow(cls, module_name, deferred, **attributes):
        """Replace *module_name* in ``sys.modules`` with a deferred clone."""
        module = sys.modules[module_name]
        sys.modules[module_name] = cls(module, deferred, **attributes)
        print '[deferred_module] shadow()'

    def __init__(self, module, deferred, **attributes):
        print '[deferred_module] __init__()'
        ModuleType.__init__(self, module.__name__, module.__doc__ or None)
        self.__dict__.update(attributes)
        self.__shadowing = module
        self.__all__ = []
        self.__pushed_up = {}
        self.__file__ = module.__file__
        self.__path__ = module.__path__

        for submodule, pushed_up in deferred.iteritems():
            self.__all__.append(submodule)
            if pushed_up:
                for member in pushed_up:
                    self.__pushed_up[member] = submodule
                self.__all__.extend(pushed_up)

    def __getattr__(self, key):
        if key in self.__pushed_up:
            owner = self.__pushed_up[key]
            value = getattr(getattr(self, owner), key)
            setattr(self, key, value)
            return value
        elif key in self.__all__:
            module = __import__(
                self.__name__ + '.' + key, None, None, [self.__name__])
            setattr(self, key, module)
            return module
        else:
            try:
                return ModuleType.__getattribute__(self, key)
            except AttributeError:
                raise AttributeError(
                    'module %r has no attribute %r' % (self.__name__, key))

    def __dir__(self):
        pool = sorted(set(self.__all__).union(self.__dict__.keys()))
        return [key for key in pool if not key.startswith('_deferred_module')]
