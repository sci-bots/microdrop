import time

from path_helpers import path
from nose.tools import raises, eq_

from dmf_device import DmfDevice
from microdrop_utility import Version
from svg_model.svgload.svg_parser import SvgParser, parse_warning
from svg_model.path_group import PathGroup


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


def _svg_parse(i, expected_paths_count):
    root = path(__file__).parent
    svg_parser = SvgParser()
    svg_path = root.joinpath('svg_files', 'test_device_%d.svg' % i)
    #with Silence():
    svg = svg_parser.parse_file(svg_path, on_error=parse_warning)
    eq_(len(svg.paths), expected_paths_count)
    time.sleep(1.0)


def _import_device(i, root):
    svg_path = root.joinpath('svg_files', 'test_device_%d.svg' % i)
    device = DmfDevice.load_svg(svg_path)
    time.sleep(1.0)


def test_svg_parser():
    expected_paths_count = [72, 57, 56, 131, 106]
    for i in range(5):
        yield _svg_parse, i, expected_paths_count[i]


def test_import_device(root=None):
    if root is None:
        root = path(__file__).parent
    else:
        root = path(root)
    for i in range(6):
        yield _import_device, i, root
