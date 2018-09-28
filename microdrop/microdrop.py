#!/usr/bin/env python
import os
import platform
import sys
import traceback


# Disable Intel Fortran default console event handler.
#
# Without doing this, [`Control-C` causes abrupt termination with the following
# message][i905]:
#
#     forrtl: error (200): program aborting due to control-C event
#
# [i905]: https://github.com/ContinuumIO/anaconda-issues/issues/905#issuecomment-330678890
#: ..versionadded:: 2.15.2
os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'


if platform.system() == 'Windows':
    # When loading Portable MicroDrop on Windows 8.1, the following error
    # occurs when trying to import `win32com`, etc.:
    #
    #     ImportError: DLL load failed: The specified module could not be
    #     found.
    #
    # Importing `pythoncom` *(as done below)* prior to `win32com`, etc. seems
    # to work around the issue.
    # See ticket #174.
    import pythoncom


def except_handler(*args, **kwargs):
    print args, kwargs
    traceback.print_tb(args[2])


def initialize_core_plugins():
    # These imports automatically load (and initialize) core singleton plugins.
    from .core_plugins import zmq_hub_plugin
    from .core_plugins import command_plugin
    from .core_plugins import device_info_plugin
    from .core_plugins.electrode_controller_plugin import pyutilib
    from .core_plugins import prompt_plugin
    from .gui import experiment_log_controller
    from .gui import config_controller
    from .gui import main_window_controller
    from .gui import dmf_device_controller
    from .core_plugins import protocol_controller
    from .gui import protocol_grid_controller
    from .gui import plugin_manager_controller
    from .gui import app_options_controller


def main():
    import logging

    import gtk

    settings = gtk.settings_get_default()
    # Use a button ordering more consistent with Windows
    print 'Use a button ordering more consistent with Windows'
    settings.set_property('gtk-alternative-button-order', True)

    logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(levelname)s:%(name)s]: '
                        '%(message)s', datefmt=r'%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    initialize_core_plugins()

    # XXX Import from `app` module automatically instantiates instance of `App`
    # class.
    from app import App
    from app_context import get_app

    gtk.threads_init()
    gtk.gdk.threads_init()
    my_app = get_app()
    sys.excepthook = except_handler
    my_app.run()


if __name__ == "__main__":
    import multiprocessing

    import matplotlib

    matplotlib.use('Agg')
    multiprocessing.freeze_support()

    main()
