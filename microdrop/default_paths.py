'''
.. versionadded:: X.X.X
'''
import json
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


def update_recent(key, config, filename, n=5):
    '''
    Update ``'recent'`` list in specified config section with filename.

    Parameters
    ----------
    key : str
        Configuration section name (e.g., ``"protocol"``).
    config : microdrop.config.Config
    filename : str
        File path to insert/update in recent list.
    n : int, optional
        Maximum number of items to store in recent list.

    Returns
    -------
    list[str]
        List of recent locations.
    '''
    recent_locations = json.loads(config[key].get('recent', '[]'))
    if filename in recent_locations:
        recent_locations.remove(filename)
    recent_locations.insert(0, filename)
    recent_locations = recent_locations[:n]
    config[key]['recent'] = json.dumps(recent_locations)
    config.save()
    return recent_locations
