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

from .set_of_ints import SetOfInts

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


def copytree(src, dst, symlinks=False, ignore=None):
    import os
    from shutil import copy2, copystat, Error

    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    try:
        os.makedirs(dst)
    except OSError, exc:
        # XXX - this is pretty ugly
        if "file already exists" in exc[1]:  # Windows
            pass
        elif "File exists" in exc[1]:        # Linux
            pass
        else:
            raise

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
    try:
        copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error, errors 


class InvalidVersionStringError(Exception):
    pass


class VersionError(Exception):
    pass


class FutureVersionError(Exception):
    def __init__(self, current_version, future_version, *args, **kwargs):
        super(FutureVersionError, self).__init__(*args, **kwargs)
        self.current_version = current_version
        self.future_version = future_version


class Version:
    def __init__(self, major=0, minor=0, micro=0):
        if type(major)!=int or type(minor)!=int or type(micro)!=int:
            raise TypeError
        self.major = major
        self.minor = minor
        self.micro = micro

    @classmethod
    def fromstring(cls, string):
        """
        Initialize a Version object from a string of the form "x", "x.y", or
        "x.y.z" where x, y and z are integers representing the major, minor
        and micro versions.
        
        Raises:
            InvalidVersionStringError
        """
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
            raise InvalidVersionStringError

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
