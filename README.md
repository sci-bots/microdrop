[![Documentation Status](https://readthedocs.org/projects/microdrop/badge/?version=dev)](http://microdrop.readthedocs.io/en/dev/?badge=dev)
[![Join the chat at https://gitter.im/wheeler-microfluidics/microdrop](https://badges.gitter.im/wheeler-microfluidics/microdrop.svg)](https://gitter.im/wheeler-microfluidics/microdrop?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

MicroDrop is a graphical user interface for the [DropBot][1] digital
microfluidics control system (described in detail in [Fobel et al., Appl. Phys.
Lett. 102, 193513 (2013)][2]).

If you use this information in work that you publish, please cite as
appropriate.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Installation](#installation)
    - [No existing Python 2.7 32-bit Windows installation](#no-existing-python-27-32-bit-windows-installation)
    - [Existing `anaconda` (Python 2.7 32-bit Windows) installation](#existing-anaconda-python-27-32-bit-windows-installation)
    - [Create a separate `conda` environment for MicroDrop 2.0](#create-a-separate-conda-environment-for-microdrop-20)
    - [Other Python 2.7 32-bit Windows installation (using `pip`)](#other-python-27-32-bit-windows-installation-using-pip)
- [Configuration](#configuration)
- [Install plugins](#install-plugins)
    - [Featured plugins](#featured-plugins)
    - [Install plugins through MicroDrop plugin manager (`mpm`)](#install-plugins-through-microdrop-plugin-manager-mpm)
    - [Install plugins through MicroDrop GUI](#install-plugins-through-microdrop-gui)
- [Credits](#credits)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Installation #

MicroDrop can be installed using any of the methods below.

After installing, the directions in the [Configuration section](#configuration)
below can be used to:

 - Create a MicroDrop user configuration
 - Launch MicroDrop

### No existing Python 2.7 32-bit Windows installation ###

Download installer for latest [MicroDrop 2.0 release][4].

This installer is a customized distribution of the popular [`Miniconda`][5]
Python.


### Existing `anaconda` (Python 2.7 32-bit Windows) installation ###

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


### Other Python 2.7 32-bit Windows installation (using `pip`) ###

 1. Update `pip`:

        pip install -U pip

 2. Install microdrop (find latest version number on [PyPi][3], e.g.,
    `"microdrop>=2.0.post14.dev250849665"`):

        pip install --find-links http://192.99.4.95/wheels --trusted-host 192.99.4.95 "microdrop>=2.0,<3.0"

**Note** *`192.99.4.95` is the IP address of the official MicroDrop update
server where MicroDrop dependencies not available on PyPI are stored as
wheels*.


# Configuration #

To create a new MicroDrop settings directory with a batch file launcher, run
the following command using the Python installation used to install MicroDrop:

    python -m microdrop.bin.create_portable_config <microdrop settings directory>

To launch MicroDrop, run:

    <microdrop settings directory>\microdrop.bat


# Install plugins #

Plugins can either be installed using the [MicroDrop plugin
manager](#install-plugins-through-microdrop-plugin-manager-mpm) command-line
tool, or through the [MicroDrop user
interface](#install-plugins-through-microdrop-gui).

### Featured plugins ###

 - [`device_quality_control_plugin`][6]:
     * Perform impedance scan across all channels on microfluidics chip.
     * Can be used to identify suspected broken electrode traces.
     * **Requires `dmf_control_board_plugin`**.
 - [`dmf_control_board_plugin`][7]
     * Control actuation parameters for the [DropBot][12] open-source Digital
       Microfluidic (DMF) automation system.
 - [`dmf_device_ui_plugin`][8]
     * Displays interactive DMF chip geometry.
     * Optional augmented reality interface, where device drawing is overlaid
       on live webcam video feed.
 - [**`droplet_planning_plugin`**][13]
     * Click and drag mouse over series of electrodes to create a route.
     * Hold <kbd>Alt</kbd>, click on source electrode, and drag to target
       electrode to automatically route between electrodes.
     * Finish route at starting point to form a cycle that may be repeated
       (i.e., mixing) either:
         - A set number of repetitions
         - A time duration
 - [`step_label_plugin`][10]
     * Optionally add text label to any step in protocol.
     * Most recent and next upcoming labelled steps are indicated while running
       protocol.
 - [`user_prompt_plugin`][11]
     * Add (optional) user prompt for each step in protocol (e.g., "Confirm
       sample is loaded.")
     * Protocol execution is paused until user confirms **OK** to proceed.
     * If user selects `Cancel`, protocol is stopped.

### Install plugins through MicroDrop plugin manager (`mpm`) ###

The Microdrop plugin manager is a command-line tool (inspired by `pip`) for
managing (e.g., install, uninstall) Microdrop plugins.

For full usage details, see the [project home page][14].

Basic usage to install a plugin:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install plugin [plugin [plugin ...]]

To install featured plugins:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install dmf_control_board_plugin dmf_device_ui_plugin droplet_planning_plugin user_prompt_plugin step_label_plugin

### Install plugins through MicroDrop GUI ###

 1. Install plugins:

     ![Install MicroDrop plugins][install-plugins]

 2. Relaunch MicroDrop:

        <microdrop settings directory>\microdrop.bat


[1]: http://microfluidics.utoronto.ca/microdrop
[2]: http://dx.doi.org/10.1063/1.4807118
[3]: https://pypi.python.org/pypi/microdrop
[4]: https://github.com/wheeler-microfluidics/microdrop/releases/latest
[5]: http://conda.pydata.org/miniconda.html
[6]: https://github.com/wheeler-microfluidics/device-quality-control-plugin
[7]: https://github.com/wheeler-microfluidics/dmf_control_board_plugin
[8]: https://github.com/wheeler-microfluidics/dmf_device_ui_plugin
[9]: https://github.com/wheeler-microfluidics/metadata_plugin
[10]: https://github.com/wheeler-microfluidics/step_label_plugin
[11]: https://github.com/wheeler-microfluidics/user_prompt_plugin
[12]: http://microfluidics.utoronto.ca/dropbot/
[13]: https://github.com/wheeler-microfluidics/droplet-planning-plugin
[14]: https://github.com/wheeler-microfluidics/mpm

[install-plugins]: microdrop/static/images/plugins-install.gif


Credits
=======

Ryan Fobel <ryan@fobel.net>

Christian Fobel <christian@fobel.net>
