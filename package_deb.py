import re
from glob import glob

from path import path
from py2deb import Py2deb

from site_scons.git_util import GitUtil

def generate_deb():
    g = GitUtil()
    version = g.describe()
    m = re.match('v(\d+)\.(\d+)-(\d+)', version)
    version = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))

    #changelog=open("changelog.txt","r").read()

    p = Py2deb("microdrop")
    p.author="Christian Fobel"
    p.mail="christian@fobel.net"
    p.description="""."""
    p.url = "http://microfluidics.utoronto.ca/microdrop"
    p.depends="python-gtk2, python, libboost-all-dev, python-matplotlib, python-numpy, python-jinja2, avrdude"
    p.license="gpl"
    p.section="utils"
    p.arch="all"

    m = path('microdrop')
    files = ['%s|%s' % (f, m.relpathto(f)) for f in list(m.walkfiles(ignore=['\.git', 'site_scons']))]

    p["/usr/lib/python2.7/dist-packages/microdrop"] = files
    p["/usr/bin"]=["microdrop/microdrop.py|microdrop"]

    p.generate(version)

if __name__ == '__main__':
    generate_deb()
