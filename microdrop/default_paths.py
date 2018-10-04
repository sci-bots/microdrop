'''
.. versionadded:: X.X.X
'''
import platform

from logging_helpers import _L
import path_helpers as ph


USER_DATA_DIR = (ph.path('~/MicroDrop').expand() if platform.system() != 'Windows'
             else ph.path('~/Documents/MicroDrop').expand())
DEVICES_DIR = USER_DATA_DIR.joinpath('devices')
PROTOCOLS_DIR = USER_DATA_DIR.joinpath('protocols')

for dir_i in (DEVICES_DIR, PROTOCOLS_DIR):
    if not dir_i.isdir():
        _L().debug('Create default directory `%s` since it does not exist.',
                   dir_i)
        dir_i.makedirs_p()
