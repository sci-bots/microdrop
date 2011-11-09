# -*- mode: python -*-
from path import path

extra_py = [str(p) for p in path('microdrop\\plugins').walkfiles('*.py') if p.find('site_scons') < 0]
a = Analysis([os.path.join(HOMEPATH,'support\\_mountzlib.py'), os.path.join(HOMEPATH,'support\\useUnicode.py'), 'microdrop\\microdrop.py'] + extra_py,
             pathex=['Z:\\Documents\\dev\\udrop\\microdrop'])

a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\gui').walkfiles('*.glade')]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\plugins').walkfiles()]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\devices').walkfiles()]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\etc').walkfiles()]
a.datas += [(str(path('microdrop').relpathto(p)), str(p.abspath()), 'DATA')\
            for p in path('microdrop\\share').walkfiles()]

pyz = PYZ(a.pure)
exe = EXE(pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            exclude_binaries=False,
            name=os.path.join('build\\pyi.win32\\microdrop', 'microdrop.exe'),
            debug=False,
            strip=False,
            upx=True,
            console=False,
            icon='microdrop.ico')
coll = COLLECT(exe,
               a.datas,
               upx=True,
               name=os.path.join('dist', 'microdrop'))
