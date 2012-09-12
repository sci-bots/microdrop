import re
import os
import sys
import subprocess
import zipfile
import urllib2

from distutils.dir_util import copy_tree


PYTHON_VERSION = "%s.%s" % (sys.version_info[0],
                            sys.version_info[1])
CACHE_PATH = "download_cache"


if not os.path.isdir(CACHE_PATH):
    os.makedirs(CACHE_PATH)


def download_file(link, name, type):
    filepath_path = os.path.join(CACHE_PATH,"%s.%s" % (name,type))
    fp = open(filepath_path, 'wb')
    downloaded = 0
    print link
    resp = urllib2.urlopen(link)
    total_length = None
    try:
        if resp.info().getheaders("Content-Length"):
            total_length = int(resp.info().getheaders("Content-Length")[0])
            print('Downloading %s (%s kB): ' % (link, total_length/1024))
        else:
            print('Downloading %s (unknown size): ' % link)
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            downloaded += len(chunk)
            if not total_length:
                sys.stdout.write('\r%s kB' % (downloaded/1024))
            else:
                sys.stdout.write('\r%3i%%  %s kB' % (100*downloaded/total_length, downloaded/1024))
            sys.stdout.flush()
            fp.write(chunk)
    finally:
        fp.close()
        sys.stdout.write('\n');
        sys.stdout.flush()
    return filepath_path


def get_apt_packages():
    package_names = re.split('\s+', '''git python-dev python-pip
        python-pyparsing ipython scons python-gtk2 python libboost-all-dev
        python-matplotlib python-numpy python-scipy python-jinja2 avrdude''')
    return [(name, 'apt') for name in package_names]


def get_pip_packages():
    implicit = [("pyparsing", "pip"),
            ("pyutilib.component.core", "pip"),
            ("pyutilib.component.loader", "pip"),
            ("blinker", "pip"),
            ("configobj", "pip"),
            ("yaml", "pip", "pyyaml"),
            ("nose", "pip"),
            ("pathmunge", "pip", "nose-pathmunge"),
            ("IPython", "pip", "ipython"),
            ("sphinx", "pip"), ]

    explicit = [("pylint", "pip", "http://download.logilab.org/pub/pylint/pylint-0.25.1.tar.gz"),
            ("constraint", "pip", "https://github.com/cfobel/python___labix_constraint/tarball/master"),
            ("jsonrpc", "pip", "https://github.com/cfobel/python-jsonrpc/tarball/master"),
            ("pymunk", "pip", "https://github.com/cfobel/python___pymunk/tarball/chipmunk-6.0.2"),
            ("path", "pip", "http://microfluidics.utoronto.ca/git/path.py.git/snapshot/da43890764f1ee508fe6c32582acd69b87240365.zip"),
    ]

    force = [("pygtkhelpers", "pip", "https://github.com/cfobel/pygtkhelpers/"\
            "tarball/pre_object_tree"), 
            ('gst_video_source_caps_query', 'pip', 'https://github.com/cfobel/'\
            'python___gst_video_source_caps_query/tarball/master'), ]

    return implicit, explicit, force


def install(package):
    name = package[0]
    type = package[1]
    print "installing %s" % name

    if type=="pip":
        if len(p) > 2:
            subprocess.call("pip install --upgrade " + p[2], shell=True)
        else:
            subprocess.call("pip install --upgrade " + name, shell=True)
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
    else:
        raise Exception("Invalid type")


if __name__ == '__main__':
    import itertools

    apt_packages = get_apt_packages()
    subprocess.call("apt-get install %s" % ' '.join([p[0]
        for p in apt_packages]), shell=True)

    implicit, explicit, force = get_pip_packages()
    packages = force

    for p in itertools.chain(implicit, explicit):
        try:
            exec("import " + p[0])
        except:
            packages.append(p)

    for p in packages:
        install(p)

