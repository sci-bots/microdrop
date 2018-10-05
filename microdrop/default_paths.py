'''
.. versionadded:: X.X.X
'''
import functools as ft
import json
import platform

from logging_helpers import _L
from pygtkhelpers.gthreads import gtk_threadsafe
import gtk
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


@gtk_threadsafe
def update_recent_menu(file_locations, menu_head, callback):
    '''
    Update recent files submenu.

    Parameters
    ----------
    file_locations : list[str]
        List of recent file locations.
    menu_head : gtk.MenuItem
        Menu item to which recent files submenu should be attached.
    callback : function
        Menu activation callback, with the following signature:
        ``callback(file_location, menu_item)``.
    '''
    menu_head.remove_submenu()
    recent_items = []

    i = 0
    for path_i in file_locations:
        path_i = ph.path(path_i)
        if path_i.isfile():
            item_i = gtk.MenuItem('_%d. %s' % (i + 1, path_i.name))
            item_i.set_tooltip_text(path_i)
            item_i.connect('activate', ft.partial(callback, path_i))
            recent_items.append(item_i)
            i += 1

    if recent_items:
        menu = gtk.Menu()

        for item in recent_items:
            menu.append(item)
        menu_head.set_submenu(menu)
        menu_head.show_all()
