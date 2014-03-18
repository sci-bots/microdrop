from path_helpers import path


def base_path():
    return path(__file__).abspath().parent


def glade_path():
    '''
    Return path to `.glade` files used by `gtk` to construct views.
    '''
    return base_path().joinpath('gui', 'glade')
