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