import os

from path import path

def app_data_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        app_dir = shell.SHGetFolderPath(0, shellcon.CSIDL_APPDATA, 0, 0)
    else:
        app_dir = path('~').expand()
    return path(app_dir)


def home_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        dir = shell.SHGetFolderPath(0, shellcon.CSIDL_PERSONAL, 0, 0)
    else:
        dir = path('~').expand()
    return path(dir)


def common_app_data_dir():
    if os.name == 'nt':
        from win32com.shell import shell, shellcon

        app_dir = path(shell.SHGetFolderPath(0, shellcon.CSIDL_COMMON_APPDATA, 0, 0))
    else:
        app_dir = None
    return app_dir
