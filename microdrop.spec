# -*- mode: python -*-
from path import path
import pygtkhelpers

mod_path = path(pygtkhelpers.__file__).parent

extra_py = []
a = Analysis([os.path.join(HOMEPATH,'support\\_mountzlib.py'), os.path.join(HOMEPATH,'support\\useUnicode.py'), 'microdrop\\microdrop.py'] + extra_py,
             excludes=['opencv'])

a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\opencv').walkfiles(ignore=[r'\.git', r'site_scons', r'.*\.pyc'])]
a.datas += [(str(mod_path.parent.relpathto(p)), str(p.abspath()), 'DATA')\
            for p in mod_path.walkfiles(ignore=[r'\.git', r'site_scons', r'.*\.pyc'])]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\gui').walkfiles('*.glade')]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\plugins').walkfiles(ignore=[r'site_scons', r'.*\.pyc'])]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\devices').walkfiles()]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\etc').walkfiles()]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\share').walkfiles()]
a.datas += [(path('version.txt'),
            path('microdrop\\version.txt').abspath(),
            'DATA')]

pyz = PYZ(a.pure)
exe = EXE(pyz,
            a.scripts,
            exclude_binaries=True,
            name=os.path.join('build\\pyi.win32\\microdrop', 'microdrop.exe'),
            debug=True,
            strip=False,
            upx=True,
            console=True,
            icon='microdrop.ico')
coll = COLLECT(exe,
                a.datas,
                a.binaries,
                a.zipfiles,
                upx=True,
                name=os.path.join('dist', 'microdrop'))
