import os
import pkg_resources

from paver.easy import task, needs
from paver.setuputils import setup

import version


install_requires = ['application_repository', 'blinker', 'configobj',
                    'flatland-fork', 'geo-util', 'ipython',
                    'microdrop_utility', 'opencv-helpers', 'path-helpers',
                    'pygst-utils', 'pygtk_textbuffer_with_undo', 'pyparsing',
                    'pyutilib==3.9.2706', 'pyyaml', 'pyzmq', 'svg_model',
                    'svgwrite', 'task_scheduler', 'wheeler.pygtkhelpers',
                    'pip-helpers']


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
