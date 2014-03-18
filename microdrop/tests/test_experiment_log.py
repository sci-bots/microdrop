from path_helpers import path
from nose.tools import raises

from experiment_log import ExperimentLog
from microdrop_utility import Version

def test_load_experiment_log():
    """
    test loading experiment log files
    """

    # version 0.0.0 files
    for i in [0]:
        yield load_experiment_log, (path(__file__).parent /
                            path('experiment_logs') /
                            path('experiment log %d v%s' % (i, Version(0,0,0))))

    # version 0.1.0 files
    for i in [0]:
        yield load_experiment_log, (path(__file__).parent /
                            path('experiment_logs') /
                            path('experiment log %d v%s' % (i, Version(0,1,0))))

def load_experiment_log(name):
    ExperimentLog.load(name)
    assert True


@raises(IOError)
def test_load_non_existant_experiment_log():
    """
    test loading experiment log file that doesn't exist
    """
    ExperimentLog.load(path(__file__).parent /
                       path('experiment_logs') /
                       path('no log'))
