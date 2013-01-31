#!/usr/bin/env python
"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import sys
import multiprocessing
import traceback
import logging

from path import path

try:
    import utility as utility
except ImportError:
    sys.path.append(path(__file__).parent)
    import utility as utility
import cgi
import pygtk

# The following imports ensure that the corresponding modules are processed
# by PyInstaller when generating an EXE.
try:
    # this may not be necessary on all systems
    import pygst
    pygst.require('0.10')
except:
    pass
finally:
    import gst
import zmq
import zmq.utils.strtypes
import zmq.utils.jsonapi
import zmq.core.pysocket
import gobject
import glib
import gtk
glib.threads_init()
gobject.threads_init()
gtk.threads_init()
import blinker
import matplotlib
import utility.uuid_minimal
import scipy.optimize

settings = gtk.settings_get_default()
# Use a button ordering more consistent with Windows
print 'Use a button ordering more consistent with Windows'
settings.set_property('gtk-alternative-button-order', True)


def except_handler(*args, **kwargs):
    print args, kwargs
    traceback.print_tb(args[2])


if __name__ == '__main__':
    if hasattr(sys, 'frozen'):
        print 'Enabling multiprocessing freeze support.'
        multiprocessing.freeze_support()
    utility.PROGRAM_LAUNCHED = True
    # Change directory to where microdrop.py resides, so this program can be
    # run from any directory.
    root_dir = utility.base_path().abspath()
    from logger import logger
    logger.info('Root directory: %s' % root_dir)
    os.chdir(root_dir)

    from app import App
    from app_context import get_app

    my_app = get_app()
    sys.excepthook = except_handler
    my_app.run()
