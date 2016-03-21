MicroDrop
=========

Microdrop is a graphical user interface for the [DropBot][1] digital
microfluidics control system (described in detail in [Fobel et al., Appl. Phys.
Lett. 102, 193513 (2013)][2]).

If you use this information in work that you publish, please cite as
appropriate.

Installation
============

 1. Update `pip`:

        pip install -U pip

 2. Install microdrop:

        pip install --find-links http://192.99.4.95/wheels --trusted-host 192.99.4.95 microdrop

 3. Create new settings directory with batch file launcher:

        python -m microdrop.bin.create_portable_config <microdrop settings directory>

 4. Launch MicroDrop:

        <microdrop settings directory>\microdrop.bat

 5. Install plugins:

     ![Install MicroDrop plugins][install-plugins]

 6. Relaunch MicroDrop:

        <microdrop settings directory>\microdrop.bat


[1]: http://microfluidics.utoronto.ca/microdrop
[2]: http://dx.doi.org/10.1063/1.4807118
[3]: https://pypi.python.org/pypi/microdrop

[install-plugins]: microdrop/static/images/plugins-install.gif


Credits
=======

Ryan Fobel <ryan@fobel.net>
Christian Fobel <christian@fobel.net>
