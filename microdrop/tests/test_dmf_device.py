from path import path
from nose.tools import raises

from dmf_device import DmfDevice
from utility import Version

def test_load_dmf_device():
    """
    test loading DMF device files
    """

    # version 0.2.0 files
    for i in [0, 1]:
        yield load_device, (path(__file__).parent /
                            path('devices') /
                            path('device %d v%s' % (i, Version(0,2,0))))

    # version 0.3.0 files
    for i in [0, 1]:
        yield load_device, (path(__file__).parent /
                            path('devices') /
                            path('device %d v%s' % (i, Version(0,3,0))))


def load_device(name):
    DmfDevice.load(name)
    assert True


@raises(IOError)
def test_load_non_existant_dmf_device():
    """
    test loading DMF device file that doesn't exist
    """
    DmfDevice.load(path(__file__).parent /
                   path('devices') /
                   path('no device'))