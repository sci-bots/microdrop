import re
import os
import sys

from git_util import GitUtil
from path_find import path_find

env = Environment(ENV=os.environ)
Export('env')

ARGUMENTS['genrst'] = 'sphinx-autopackage-script/generate_modules.py ../microdrop -d . -s rst'
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

    version_target = env.Command('microdrop/version.txt', None,
                            'echo %s > $TARGET' % SOFTWARE_VERSION)
    exe = env.Command('microdrop/dist/microdrop.exe', 'microdrop.spec',
                            '%s %s -y $SOURCE' % (sys.executable, BUILD_PATH))
    wxs = env.Command('microdrop.wxs', version_target,
                            'python generate_wxs.py -v %s > $TARGET' % SOFTWARE_VERSION)
    wixobj = env.Command('microdrop.wixobj', wxs,
                            'candle -o $TARGET $SOURCE')
    env.Clean(exe, 'dist') 
    env.Clean(exe, 'build') 
    env.Clean(wixobj, 'microdrop.wixpdb') 

    msi = env.Command('microdrop.msi', wixobj,
            'light -ext WixUIExtension -cultures:en-us $SOURCE -out $TARGET')
    AlwaysBuild(version_target)
    Depends(exe, version_target)
    Depends(wxs, exe)
    Depends(wxs, 'generate_wxs.py')
    Default(msi)
