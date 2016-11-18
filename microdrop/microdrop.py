#!/usr/bin/env python
"""
Copyright 2011 Ryan Fobel

This file is part of MicroDrop.

MicroDrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

MicroDrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MicroDrop.  If not, see <http://www.gnu.org/licenses/>.
"""
import sys
import traceback
import platform


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
    from .core_plugins import device_info_plugin
    from .core_plugins import command_plugin
    from .core_plugins import electrode_controller_plugin
    from .gui import experiment_log_controller
    from .gui import config_controller
    from .gui import main_window_controller
    from .gui import dmf_device_controller
    from .gui import protocol_controller
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

    logging.basicConfig(format='%(asctime)s [%(levelname)s:%(name)s]: '
                        '%(message)s', datefmt=r'%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    initialize_core_plugins()
    from app import App
    from app_context import get_app

    gtk.threads_init()
    gtk.gdk.threads_init()
    gtk.gdk.threads_enter()
    my_app = get_app()
    sys.excepthook = except_handler
    my_app.run()
    gtk.gdk.threads_leave()


if __name__ == "__main__":
    import matplotlib
    matplotlib.use('Agg')

    main()
