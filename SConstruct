import re
import os
import sys

from git_util import GitUtil
from path_find import path_find

env = Environment(ENV=os.environ)
Export('env')

SConscript('doc/SConstruct')

if os.name == 'nt':
    g = GitUtil(None)
    m = re.match('v(\d+)\.(\d+)-(\d+)', g.describe())
    SOFTWARE_VERSION = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
    Export('SOFTWARE_VERSION')

    pyinstaller_path = path_find('Build.py')
    if pyinstaller_path is None:
        raise IOError, 'Cannot find PyInstaller on PATH.'
    BUILD_PATH = pyinstaller_path.joinpath('Build.py')

    version_target = Command('microdrop/version.txt', None,
                            'echo %s > $TARGET' % SOFTWARE_VERSION)
    exe = Command('microdrop/dist/microdrop.exe', 'microdrop.spec',
                            '%s %s -y $SOURCE' % (sys.executable, BUILD_PATH))
    wxs = Command('microdrop.wxs', exe,
                            'generate_wxs.py -v %s > $TARGET' % SOFTWARE_VERSION)
    wixobj = Command('microdrop.wixobj', wxs,
                            'candle -o $TARGET $SOURCE')
    Clean(wixobj, 'microdrop.wixpdb') 

    msi = Command('microdrop.msi', wixobj,
            'light -ext WixUIExtension -cultures:en-us $SOURCE -out $TARGET')
    AlwaysBuild(version_target)
    Default(msi)
