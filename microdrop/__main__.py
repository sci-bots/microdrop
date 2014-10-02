import sys
import runpy
from path_helpers import path


def base_path():
    return path(__file__).abspath().parent

sys.path.insert(0, str(base_path().parent))

runpy.run_module("microdrop.microdrop", run_name="__main__")
