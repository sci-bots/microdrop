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
                    'microdrop-device-converter>=0.1.post4',
                    'microdrop_utility>=0.4', 'networkx', 'pandas>=0.17.1',
                    'path-helpers>=0.2', 'paver>=1.2.4', 'pip-helpers>=0.5',
                    'pygtk_textbuffer_with_undo', 'pyparsing',
                    'pyutilib==3.9.2706', 'pyyaml', 'pyzmq', 'run-exe>=0.5',
                    'si-prefix', 'scipy', 'svgwrite', 'svg-model>=0.5.post21',
                    'task_scheduler', 'tornado',
                    'wheeler.pygtkhelpers>=0.12.post6',
                    'zmq-plugin>=0.1.post10']

if platform.system() == 'Windows':
    install_requires += ['matplotlib>=1.5.0', 'pycairo-gtk2-win', 'pygtk2-win',
                         'pywin32']
else:
    install_requires += ['cairo']
    try:
        import gtk
    except ImportError:
        print >> sys.err, ('Please install Python bindings for Gtk 2 using '
                           'your systems package manager.')


setup(name='microdrop',
      version=version.getVersion(),
      description='Microdrop is a graphical user interface for the DropBot '
                  'Digital Microfluidics control system',
      keywords='digital microfluidics dmf automation dropbot microdrop',
      author='Ryan Fobel and Christian Fobel',
      author_email='ryan@fobel.net, christian@fobel.net',
      url='http://microfluidics.utoronto.ca/microdrop',
      license='GPL',
      long_description='\n%s\n' % open('README.md', 'rt').read(),
      packages=['microdrop'],
      include_package_data=True,
      install_requires=install_requires)


@task
def create_requirements():
    package_list = [p.split('==')[0] for p in install_requires]
    requirements_path = os.path.join('microdrop', 'requirements.txt')
    with open(requirements_path, 'wb') as output:
        output.write('\n'.join(['%s==%s' %
                                (p, pkg_resources.get_distribution(p).version)
                                for p in package_list]))

@task
@needs('generate_setup', 'minilib', 'create_requirements',
       'setuptools.command.sdist')
def sdist():
    """Overrides sdist to make sure that our setup.py is generated."""
    pass
