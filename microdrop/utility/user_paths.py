import os
import logging

from path import path

def app_data_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        app_dir = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
    else:
        app_dir = path('~').expand()
    logging.debug('app_data_dir()=%s' % app_dir)
    return path(app_dir)


def home_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        dir = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, 0, 0)
    else:
        dir = path('~').expand()
    logging.debug('home_dir()=%s' % dir)
    return path(dir)


def common_app_data_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        app_dir = path(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0))
    else:
        app_dir = None
    logging.debug('common_app_data_dir()=%s' % app_dir)
    return app_dir
