REM Generate `setup.py` from `pavement.py` definition.
"%PYTHON%" -m paver generate_setup

REM **Workaround** `conda build` runs a copy of `setup.py` named
REM `conda-build-script.py` with the recipe directory as the only argument.
REM This causes paver to fail, since the recipe directory is not a valid paver
REM task name.
REM
REM We can work around this by wrapping the original contents of `setup.py` in
REM an `if` block to only execute during package installation.
"%PYTHON%" -c "input_ = open('setup.py', 'r'); data = input_.read(); input_.close(); output_ = open('setup.py', 'w'); output_.write('\n'.join(['import sys', 'import path_helpers as ph', '''if ph.path(sys.argv[0]).name == 'conda-build-script.py':''', '    sys.argv.pop()', 'else:', '\n'.join([('    ' + d) for d in data.splitlines()])])); output_.close(); print open('setup.py', 'r').read()"

REM Install source directory as Python package.
"%PYTHON%" -m pip install --no-cache --find-links http://192.99.4.95/wheels --trusted-host 192.99.4.95 .
if errorlevel 1 exit 1
