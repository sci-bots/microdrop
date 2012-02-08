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

import sys
import re

from path import path


PROGRAM_LAUNCHED = False


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
    print "error" # TODO dialog error
    textentry.set_text(str(prev_value))
    return prev_value


def base_path():
    # When executing from a frozen (pyinstaller) executable...
    if hasattr(sys, 'frozen'):
        print 'FROZEN!'
        return path(sys.executable).parent
    else:
        print 'NOT FROZEN!'

    # Otherwise...
    try:
        script = path(__file__)
    except NameError:
        script = path(sys.argv[0])
    return script.parent.parent

class InvalidVersionString(Exception):
    pass

class InvalidVersion(Exception):
    pass

class Version:
    InvalidVersionString(Exception)
    
    def __init__(self, major=0, minor=0, micro=0):
        if type(major)!=int or type(minor)!=int or type(micro)!=int:
            raise InvalidVersion
        self.major = major
        self.minor = minor
        self.micro = micro

    @classmethod
    def fromstring(cls, string):
        "Initialize Version from a string"
        major, minor, micro = ('0','0','0')
        match = False
        
        m = re.search('^(\d+)$', string)
        if m:
            major = m.groups()[0]
            match = True
        m = re.search('^(\d+)\.(\d+)$', string)
        if m:
            major, minor = m.groups()
            match = True
        m = re.search('^(\d+)\.(\d+)\.(\d+)$', string)
        if m:
            major, minor, micro = m.groups()
            match = True
            
        if match == False:
            raise InvalidVersionString

        return cls(int(major), int(minor), int(micro))
    
    def __repr__(self):
        return "%s(%d.%d.%d)" % (self.__class__,
                                 self.major,
                                 self.minor,
                                 self.micro)

    def __str__(self):
        return "%d.%d.%d" % (self.major,
                             self.minor,
                             self.micro)
        
    def __lt__(self, x):
        if self.major<x.major:
            return True
        elif self.major==x.major:
            if self.minor<x.minor:
                return True
            elif self.minor==x.minor:
                if self.micro<x.micro:
                    return True
        return False
    
    def __eq__(self, x):
        if (self.major, self.minor, self.micro) == (x.major, x.minor, x.micro):
            return True
        else:
            return False

    def __ne__(self, x):
        return not self==x
        
    def __le__(self, x):
        return self<x or self==x