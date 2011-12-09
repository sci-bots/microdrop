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

import urllib2
import subprocess
import sys
import tempfile
import os
import zipfile
import tarfile
import re
from distutils.dir_util import copy_tree

PYTHON_VERSION = "%s.%s" % (sys.version_info[0],
                            sys.version_info[1])
CACHE_PATH = "download_cache"

def get_version(path):
    current_path = os.getcwd()
    version = ""
    try:
        os.chdir(path)
        version = subprocess.Popen(['git','describe'], \
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   stdin=subprocess.PIPE).communicate()[0].rstrip()
        m = re.match('v(\d+)\.(\d+)-(\d+)', version)
        version = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
    finally:
        os.chdir(current_path)
    return version

def in_path(filename):
    for d in os.environ['PATH'].split(';'):
        if os.path.isfile(os.path.join(d, filename)):
            return True
    return False

def install(package):
    name = package[0]
    type = package[1]
    print "installing %s" % name

    if type=="py":
        file = download_file(p[2], name, type)
        subprocess.call("python " + file, shell=False)
    elif type=="msi":
        file = download_file(p[2], name, type)
        subprocess.call("msiexec /i " + file, shell=False)
    elif type=="exe":
        file = download_file(p[2], name, type)
        subprocess.call(file, shell=False)
    elif type=="easy_install":
        subprocess.call("easy_install " + name, shell=False)
    elif type=="zip":
        src = os.path.join(CACHE_PATH, name, p[3])
        dst = p[4]
        file = download_file(p[2], name, type)
        z = zipfile.ZipFile(file, 'r')
        try:
            print "extracting zip file..."
            z.extractall(os.path.join(CACHE_PATH, name))
        finally:
            z.close()
        print "copying extracted files to %s" % dst
        copy_tree(src, dst)
    elif type=="tar.gz":
        src = os.path.join(CACHE_PATH, name, p[3])
        dst = p[4]
        file = download_file(p[2], name, type)
        z = tarfile.open(file, 'r')
        try:
            print "extracting tar.gz file..."
            z.extractall(os.path.join(CACHE_PATH, name))
        finally:
            z.close()
        print "copying extracted files to %s" % dst
        copy_tree(src, dst)
    elif type=="pip":
        if len(p)>2:
            subprocess.call("pip install " + p[2], shell=False)
        else:
            subprocess.call("pip install " + name, shell=False)
    else:
        raise Exception("Invalid type")
        

def download_file(link, name, type):
    path = os.path.join(CACHE_PATH,"%s.%s" % (name,type))
    fp = open(path, 'wb')
    downloaded = 0
    print link
    resp = urllib2.urlopen(link)
    total_length = int(resp.info().getheaders("Content-Length")[0])
    try:
        if total_length:
            print('Downloading %s (%s kB): ' % (link, total_length/1024))
        else:
            print('Downloading %s (unknown size): ' % link)
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            downloaded += len(chunk)
            if not total_length:
                sys.stdout.write('\r%s kB' % downloaded/1024)
            else:
                sys.stdout.write('\r%3i%%  %s kB' % (100*downloaded/total_length, downloaded/1024))
            sys.stdout.flush()
            fp.write(chunk)
    finally:
        fp.close()
        sys.stdout.write('\n');
        sys.stdout.flush()
    return path

if __name__ == "__main__":
    if os.name!='nt':
        print "This program only works on Windows."
        exit(1)

    warnings = []

    # get the microdrop root directory
    root_dir = os.path.dirname(os.path.abspath(__file__))

    packages = []

    if os.path.isdir(CACHE_PATH) == False:
        os.mkdir(CACHE_PATH)

    # package name, type, url
    for p in (("setuptools", "py", "http://python-distribute.org/distribute_setup.py"),
              ("pip", "easy_install"),
              ("pyvisa", "exe", "http://sourceforge.net/projects/pyvisa/files/PyVISA/1.3/PyVISA-1.3.win32.exe/download"),
              ("sympy", "exe", "http://sympy.googlecode.com/files/sympy-0.7.1.win32.exe"),
              ("pyparsing", "pip"),
              ("path", "pip", "http://microfluidics.utoronto.ca/git/path.py.git/snapshot/da43890764f1ee508fe6c32582acd69b87240365.zip"),
              ("pyutilib", "pip"),
              ):
        try:
            exec("import " + p[0])
        except:
            packages.append(p)

    # python 2.7 specific packages
    if PYTHON_VERSION=="2.7":
        for p in (("gtk", "msi", "http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.24/pygtk-all-in-one-2.24.0.win32-py2.7.msi"),
                  ("numpy", "exe", "http://sourceforge.net/projects/numpy/files/NumPy/1.6.1/numpy-1.6.1-win32-superpack-python2.7.exe/download"),
                  ("matplotlib", "exe", "http://sourceforge.net/projects/matplotlib/files/matplotlib/matplotlib-1.1.0/matplotlib-1.1.0.win32-py2.7.exe/download")):
            try:
                exec("import " + p[0])
            except:
                packages.append(p)

    # python 2.6 specific packages
    elif PYTHON_VERSION=="2.6":
        for p in (("gtk", "msi", "http://ftp.gnome.org/pub/GNOME/binaries/win32/pygtk/2.24/pygtk-all-in-one-2.24.0.win32-py2.6.msi"),
                  ("numpy", "exe", "http://sourceforge.net/projects/numpy/files/NumPy/1.3.0/numpy-1.3.0-win32-superpack-python2.6.exe/download"),
                  ("matplotlib", "exe", "http://sourceforge.net/projects/matplotlib/files/matplotlib/matplotlib-1.0.1/matplotlib-1.0.1.win32-py2.6.exe/download")):
            try:
                exec("import " + p[0])
            except:
                packages.append(p)
    else:
        print "Microdrop only supports Python 2.6 and 2.7."
        exit(1)

    # check if ipython is installed
    if in_path('ipython.exe')==False and in_path('ipython.bat')==False:
        packages.append(("ipython", "pip"))

    # check if pywin32 is installed
    try:
        exec("import " + "win32api")
    except:
        if PYTHON_VERSION=="2.6":
            packages.append(("pywin32", "exe", "http://sourceforge.net/projects/pywin32/files/pywin32/Build216/pywin32-216.win32-py2.6.exe/download"))
        elif PYTHON_VERSION=="2.7":
            packages.append(("pywin32", "exe", "http://sourceforge.net/projects/pywin32/files/pywin32/Build216/pywin32-216.win32-py2.7.exe/download"))

    # check if pyinstaller is installed
    if os.path.isdir("C:/pyinstaller")==False:
        packages.append(("pyinstaller",
                         "zip",
                         "http://files.zibricky.org/pyinst/pyinstaller-1.5.1.zip",
                         "pyinstaller-1.5.1",
                         "C:/pyinstaller"))

    # check if scons is installed
    if in_path('scons.bat')==False:
        packages.append(("scons", "exe", "http://prdownloads.sourceforge.net/scons/scons-2.1.0.win32.exe"))

    # check if sphinx is installed
    if in_path('sphinx-build.exe')==False:
        packages.append(("sphinx", "pip"))

    # check if WiX is installed
    path_exists = False
    for d in ["C:\\Program Files (x86)\\Windows Installer XML v3.5\\bin",
              "C:\\Program Files\\Windows Installer XML v3.5\\bin"]:
        if os.path.isdir(d):
            path_exists = True
            break
    if path_exists==False:
        packages.append(("WiX",
                         "msi",
                         "http://microfluidics.utoronto.ca/software/Wix35.msi"))

    # check if the dmf_control_board binaries have been installed
    dmf_control_board_path = os.path.join(root_dir,
                                          "microdrop",
                                          "plugins",
                                          "dmf_control_board")
    version = get_version(dmf_control_board_path)
    f = None
    try:
        f = open(os.path.join(dmf_control_board_path, "version.txt"), 'r')
        if f.readline().strip()!=version:
            raise Exception("wrong version")
    except:
        packages.append(("dmf_control_board",
                         "tar.gz",
                         "http://microfluidics.utoronto.ca/software/dmf_control_board-%s-py%s.tar.gz" % \
                             (version, PYTHON_VERSION),
                         "dmf_control_board-%s-py%s" % (version, PYTHON_VERSION),
                         "microdrop/plugins/dmf_control_board"))
    finally:
        if f:
            f.close()
        
    if len(packages)>0:
        print "The following packages need to be installed:"
        for p in packages:
            print "\t%s" % p[0]
        
        for p in packages:
            install(p)

    # configure pyinstaller
    print "configuring pyinstaller..."
    subprocess.call("python C:\pyinstaller\Configure.py")
 
    # extract data.zip
    if os.path.isdir(os.path.join("microdrop", "devices"))==False or \
       os.path.isdir(os.path.join("microdrop", "lib"))==False or \
       os.path.isdir(os.path.join("microdrop", "share"))==False or \
       os.path.isdir(os.path.join("microdrop", "etc"))==False:
        print "extracting data.zip..."
        z = zipfile.ZipFile(os.path.join("microdrop", "data.zip"), 'r')
        z.extractall("microdrop")

    # fix pyutilib for exporting
    PYTHON_PATH = os.path.dirname(sys.executable)
    if os.path.isdir(os.path.join(PYTHON_PATH, "Lib", "site-packages",
                                   "pyutilib"))==False:
        warnings.append("Warning: pyutilib looks like it may not be installed " \
                        "correctly. If you experience problems, try deleting " \
                        "it and running this script again.")
    elif os.path.isfile(os.path.join(PYTHON_PATH, "Lib", "site-packages",
                                   "pyutilib", "__init__.py"))==False:
        print "fixing pyutilib for exporting..."
        open(os.path.join(PYTHON_PATH, "Lib", "site-packages", "pyutilib",
             "__init__.py"), 'w').close()
        open(os.path.join(PYTHON_PATH, "Lib", "site-packages", "pyutilib",
             "component", "__init__.py"), 'w').close()

    # check that pyinstaller is in the path
    if in_path("pyinstaller.py")==False and os.path.isdir("C:\pyinstaller"):
        warnings.append("Warning: C:\\pyinstaller exists but you need to " \
                        "add it to your path.")

    # check that WiX is in the path
    if in_path("candle.exe")==False:
        for d in ["C:\\Program Files (x86)\\Windows Installer XML v3.5\\bin",
                  "C:\\Program Files\\Windows Installer XML v3.5\\bin"]:
            if os.path.isdir(d):
                warnings.append("Warning: %s exists but you need to "\
                      "add it to your path." % d)
                break
    
    print "\nAll dependencies are installed."

    if len(warnings)>0:
        print
        for w in warnings:
            print w
