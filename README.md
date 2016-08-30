MicroDrop
=========

MicroDrop is a graphical user interface for the [DropBot][1] digital
microfluidics control system (described in detail in [Fobel et al., Appl. Phys.
Lett. 102, 193513 (2013)][2]).

If you use this information in work that you publish, please cite as
appropriate.

Installation
============

MicroDrop can be installed using any of the methods below.

After installing, the directions in the **Configuration** section below can be
used to:

 - Create a MicroDrop user configuration
 - Launch MicroDrop

## No existing Python 2.7 32-bit Windows installation ##

Download installer for latest [MicroDrop 2.0 release][4].

This installer is a customized distribution of the popular [`Miniconda`][5]
Python.


## Existing `anaconda` (Python 2.7 32-bit Windows) installation ##

Run:

    conda install -c wheeler-microfluidics microdrop-2.0 microdrop-plugin-manager dmf-device-ui

**Note** *the `-c wheeler-microfluidics` flag allows installing conda packages
from  the `wheeler-microfluidics` channel*.


### Create a separate `conda` environment for MicroDrop 2.0 ###

Run:

    conda create -n microdrop-2.0 -c wheeler-microfluidics microdrop-2.0 microdrop-plugin-manager dmf-device-ui

To activate the MicroDrop 2.0 `conda` environment, run:

    activate microdrop-2.0

To deactivate the MicroDrop 2.0 `conda` environment, run:

    deactivate


## Other Python 2.7 32-bit Windows installation (using `pip`) ##

 1. Update `pip`:

        pip install -U pip

 2. Install microdrop (find latest version number on [PyPi][3], e.g.,
    `"microdrop>=2.0.post14.dev250849665"`):

        pip install --find-links http://192.99.4.95/wheels --trusted-host 192.99.4.95 "microdrop>=2.0,<3.0"

**Note** *`192.99.4.95` is the IP address of the official MicroDrop update
server where MicroDrop dependencies not available on PyPI are stored as
wheels*.


Configuration
=============

To create a new MicroDrop settings directory with a batch file launcher, run
the following command using the Python installation used to install MicroDrop:

    python -m microdrop.bin.create_portable_config <microdrop settings directory>

To launch MicroDrop, run:

    <microdrop settings directory>\microdrop.bat


Install plugins
===============

Plugins can either be installed using the MicroDrop plugin manager command-line
tool, or through the MicroDrop user interface.

## Install plugins through MicroDrop plugin manager (`mpm`) ##

Run:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install plugin [plugin [plugin ...]]

To install recommended plugins:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install dmf_control_board_plugin dmf_device_ui_plugin droplet_planning_plugin user_prompt_plugin step_label_plugin

## Install plugins through MicroDrop GUI ##

 1. Install plugins:

     ![Install MicroDrop plugins][install-plugins]

 2. Relaunch MicroDrop:

        <microdrop settings directory>\microdrop.bat


[1]: http://microfluidics.utoronto.ca/microdrop
[2]: http://dx.doi.org/10.1063/1.4807118
[3]: https://pypi.python.org/pypi/microdrop
[4]: https://github.com/wheeler-microfluidics/microdrop/releases/latest
[5]: http://conda.pydata.org/miniconda.html

[install-plugins]: microdrop/static/images/plugins-install.gif


Credits
=======

Ryan Fobel <ryan@fobel.net>
Christian Fobel <christian@fobel.net>
