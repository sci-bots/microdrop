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
    print "Import error"
    sys.path.append(path(__file__).parent)
    import utility as utility

# Add gst binaries and plugins to the path/python path
GST_PATH = path(__file__).parent / path('gst')
os.environ['GST_PLUGIN_PATH'] = str((GST_PATH / path('plugins')).abspath())
sys.path.append(os.environ['GST_PLUGIN_PATH'])
os.environ['PATH'] += ";" + str((GST_PATH / path('bin')).abspath())

# The following imports ensure that the corresponding modules are processed
# by PyInstaller when generating an EXE.
import gtk
gtk.gdk.threads_init()
import blinker
import matplotlib
from PIL import Image, ImageFont, ImageDraw
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
