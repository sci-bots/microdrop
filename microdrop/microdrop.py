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

try:
    import utility as utility
except ImportError:
    from path import path
    import microdrop

    sys.path.append(path(microdrop.__file__).parent)
    import utility as utility

# The following imports ensure that the corresponding modules are processed
# by PyInstaller when generating an EXE.
import blinker
import matplotlib
import utility.uuid_minimal


def except_handler(*args, **kwargs):
    import traceback

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
