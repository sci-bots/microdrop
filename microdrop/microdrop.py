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

import sys
import traceback

import gtk

settings = gtk.settings_get_default()
# Use a button ordering more consistent with Windows
print 'Use a button ordering more consistent with Windows'
settings.set_property('gtk-alternative-button-order', True)


def except_handler(*args, **kwargs):
    print args, kwargs
    traceback.print_tb(args[2])


if __name__ == "__main__":
    from app import App
    from app_context import get_app

    gtk.threads_init()
    gtk.gdk.threads_init()
    gtk.gdk.threads_enter()
    my_app = get_app()
    sys.excepthook = except_handler
    my_app.run()
    gtk.gdk.threads_leave()
