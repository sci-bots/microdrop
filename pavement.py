import os
import pkg_resources
import platform
import sys

from paver.easy import task, needs, path
from paver.setuputils import setup

root_dir = path(__file__).parent.abspath()
if root_dir not in sys.path:
    sys.path.insert(0, str(root_dir))
import version


install_requires = ['application_repository>=0.5', 'blinker', 'configobj',
                    'droplet-planning>=0.2', 'flatland-fork', 'geo-util',
                    'ipython', 'ipython-helpers>=0.4', 'jinja2',
                    'matplotlib>=1.5.0',
                    'microdrop-device-converter>=0.1.post5',
                    'microdrop-plugin-template>=1.1.post30',
                    'microdrop_utility>=0.4.post2', 'networkx',
                    'openpyxl', 'pandas>=0.17.1', 'path-helpers>=0.2.post4',
                    'paver>=1.2.4', 'pip-helpers>=0.6',
                    'pygtk_textbuffer_with_undo', 'pyparsing',
                    'pyutilib.component.core>=4.4.1',
                    'pyutilib.component.loader>=3.3.1', 'pyyaml', 'pyzmq',
                    'run-exe>=0.5', 'si-prefix>=0.4.post10', 'scipy',
                    'svgwrite', 'svg-model>=0.6', 'task_scheduler',
                    'tornado', 'wheeler.pygtkhelpers>=0.13.post17',
                    'zmq-plugin>=0.2.post2']

if platform.system() == 'Windows':
    install_requires += ['pycairo-gtk2-win', 'pywin32']
else:
    try:
        import gtk
    except ImportError:
        print >> sys.stderr, ("Please install Python bindings for Gtk 2 using "
                              "your system's package manager.")
    try:
        import cairo
    except ImportError:
        print >> sys.stderr, ("Please install Python bindings for cairo using "
                              "your system's package manager.")


setup(name='microdrop',
      version=version.getVersion(),
      description='MicroDrop is a graphical user interface for the DropBot '
                  'Digital Microfluidics control system',
      keywords='digital microfluidics dmf automation dropbot microdrop',
      author='Ryan Fobel and Christian Fobel',
      author_email='ryan@fobel.net and christian@fobel.net',
      url='http://microfluidics.utoronto.ca/microdrop',
      license='GPL',
      long_description='\n%s\n' % open('README.md', 'rt').read(),
      packages=['microdrop'],
      include_package_data=True,
      install_requires=install_requires,
      entry_points = {'console_scripts':
                      ['microdrop = microdrop.microdrop:main']})


@task
def create_requirements():
    package_list = [p.split('==')[0] for p in install_requires]
    requirements_path = os.path.join('microdrop', 'requirements.txt')
    with open(requirements_path, 'wb') as output:
        output.write('\n'.join(['%s==%s' %
                                (p, pkg_resources.get_distribution(p).version)
                                for p in package_list]))

@task
def build_installer():
    try:
        import constructor_git as cg
        import constructor_git.__main__
    except ImportError:
        print >> sys.stderr, ('`constructor-git` package not found.  Install '
                              'with `conda install constructor-git`.')
        raise SystemExit(-1)

    repo_path = path(__file__).parent.realpath()
    print repo_path
    cg.__main__.main(repo_path)


@task
@needs('generate_setup', 'minilib', 'create_requirements',
       'setuptools.command.sdist')
def sdist():
    """Overrides sdist to make sure that our setup.py is generated."""
    pass
