class DictAsAttrProxy(object):
    '''
    >>> d = dict(A=1, B=2)
    >>> dp = DictAsAttrProxy(d)
    >>> dp.A
    1
    >>> dp.B
    2
    >>> dp.C
    Traceback (most recent call last):
        ...
    KeyError: 'C'
    >>> dp.A = 10
    >>> dp.B = 20
    >>> dp.C = 100
    >>> d
    {'A': 10, 'C': 100, 'B': 20}
    '''
    def __init__(self, dict_, none_on_not_found=False):
        object.__setattr__(self, '_dict', dict_)
        object.__setattr__(self, '_none_on_not_found', none_on_not_found)

    def __setattr__(self, name, value):
        dict_ = object.__getattribute__(self, '_dict')
        dict_[name] = value

    def __getattr__(self, name):
        dict_ = object.__getattribute__(self, '_dict')
        none_on_not_found = object.__getattribute__(self, '_none_on_not_found')
        if none_on_not_found:
            return dict_.get(name)
        else:
            return dict_[name]

    @property
    def as_dict(self):
        dict_ = object.__getattribute__(self, '_dict')
        return dict_
