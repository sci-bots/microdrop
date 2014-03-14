import os

env = Environment(ENV=os.environ)
Export('env')

ARGUMENTS['genrst'] = 'python sphinx-autopackage-script/generate_modules.py ../microdrop -d . -s rst -f'
SConscript('doc/SConstruct')
