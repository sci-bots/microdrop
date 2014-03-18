from path_helpers import path
from nose.tools import raises

from protocol import Protocol
from microdrop_utility import Version

def test_load_protocol():
    """
    test loading protocol files
    """

    # version 0.0.0 files
    for i in [0]:
        yield load_protocol, (path(__file__).parent /
                            path('protocols') /
                            path('protocol %d v%s' % (i, Version(0,0,0))))

    # version 0.1.0 files
    for i in [0]:
        yield load_protocol, (path(__file__).parent /
                            path('protocols') /
                            path('protocol %d v%s' % (i, Version(0,1,0))))


def load_protocol(name):
    Protocol.load(name)
    assert True


@raises(IOError)
def test_load_non_existant_protocol():
    """
    test loading protocol file that doesn't exist
    """
    Protocol.load(path(__file__).parent /
                   path('protocols') /
                   path('no protocol'))
