from distutils.core import setup


setup(name='microdrop',
      version='0.0.1',
      description='Microdrop is a graphical user interface for the DropBot '
                  'Digital Microfluidics control system',
      keywords='digital microfluidics dmf automation dropbot microdrop',
      author='Ryan Fobel and Christian Fobel',
      url='http://microfluidics.utoronto.ca/microdrop',
      license='GPL',
      long_description='''
Microdrop is a graphical user interface for the [DropBot][1] digital
microfluidics control system (described in detail in [Fobel et al., Appl.
Phys. Lett. 102, 193513 (2013)][2]). If you use this information in work that
you publish, please cite as appropriate.

[1]: http://microfluidics.utoronto.ca/microdrop
[2]: http://dx.doi.org/10.1063/1.4807118'''.strip(),
      packages=['microdrop',
                'microdrop.gui',
                'microdrop.tests'],
      package_data={'microdrop.tests': ['devices/*', 'experiment_logs/*',
                                        'protocols/*', 'svg_files/*.svg',
                                        'buildbot/master.cfg'],
                    'microdrop.gui': ['glade/*.glade']})
