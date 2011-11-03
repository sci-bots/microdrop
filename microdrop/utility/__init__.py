"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import gtk

from utility.path import path


def is_float(s):
    try: return (float(s), True)[1]
    except (ValueError, TypeError), e: return False


def is_int(s):
    try: return (int(s), True)[1]
    except (ValueError, TypeError), e: return False


def wrap_string(string, line_length=80, wrap_characters="\n"):    
    chars = 0
    wrapped_string = ""
    for word in string.split():
        if chars + len(word) > line_length:
            wrapped_string += wrap_characters + word + " "
            chars = len(word + wrap_characters)
        else:
            wrapped_string += word + " "
            chars += len(word) + 1
    return wrapped_string


def check_textentry(textentry, prev_value, type):
    val = textentry.get_text()
    if val and type is float:
        if is_float(val):
            return float(val)
    elif val and type is int:
        if is_int(val):
            return int(val)
    else:
        print "error" # TODO dialog error
        textentry.set_text(str(prev_value))
        return prev_value


def base_path():
    try:
        script = path(__file__)
    except NameError:
        import sys

        script = path(sys.argv[0])
    return script.parent.parent


def combobox_set_model_from_list (cb, items):
    """Setup a ComboBox or ComboBoxEntry based on a list of strings."""           
    model = gtk.ListStore(str)
    for i in items:
        model.append([i])
    cb.set_model(model)
    if type(cb) == gtk.ComboBoxEntry:
        cb.set_text_column(0)
    elif type(cb) == gtk.ComboBox:
        cell = gtk.CellRendererText()
        cb.pack_start(cell, True)
        cb.add_attribute(cell, 'text', 0)


def combobox_get_active_text(cb):
    model = cb.get_model()
    active = cb.get_active()
    if active < 0:
        return None
    return model[active][0]


def textview_get_text(textview):
    buffer = textview.get_buffer()
    start = buffer.get_start_iter()
    end = buffer.get_end_iter()
    return buffer.get_text(start, end)    
