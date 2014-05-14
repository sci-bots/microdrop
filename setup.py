from distutils.core import setup

import version


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
      packages=['microdrop',
                'microdrop.gui',
                'microdrop.tests'],
      package_data={'microdrop.tests': ['devices/*', 'experiment_logs/*',
                                        'protocols/*', 'svg_files/*.svg',
                                        'buildbot/master.cfg'],
                    'microdrop.gui': ['glade/*.glade']},
      install_requires=['wheeler.pygtkhelpers', 'blinker', 'path-helpers',
                        'ipython', 'pyutilib', 'pyparsing', 'configobj',
                        'pyyaml', 'pyzmq', 'opencv-helpers', 'pygst-utils',
                        'geo-util', 'flatland-fork', 'microdrop_utility',
                        'svg_model', 'task_scheduler',
                        'application_repository',
                        'pygtk_textbuffer_with_undo'])
