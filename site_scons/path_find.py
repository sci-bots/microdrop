import os

from path_helpers import path


def path_find(filename):
    for p in [path(d) for d in os.environ['PATH'].split(';')]:
        if p.isdir():
            if len(p.files(filename)):
                return p
    return None
