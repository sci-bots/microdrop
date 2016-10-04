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
    - [No existing Python 2.7 32-bit Windows installation **(recommended)**](#no-existing-python-27-32-bit-windows-installation-recommended)
    - [Existing `anaconda` (Python 2.7 32-bit Windows) installation **(recommended)**](#existing-anaconda-python-27-32-bit-windows-installation-recommended)
    - [Create a separate `conda` environment for MicroDrop](#create-a-separate-conda-environment-for-microdrop)
    - [Other Python 2.7 32-bit Windows installation (using `pip`)](#other-python-27-32-bit-windows-installation-using-pip)
  - [**Shortcuts**](#shortcuts)
  - [**Import** profile](#import-profile)
- [Profile Manager **(new)**](#profile-manager-new)
  - [Import profile](#import-profile)
  - [Remove profile](#remove-profile)
- [Install plugins](#install-plugins)
    - [Featured plugins](#featured-plugins)
    - [Install plugins through MicroDrop plugin manager (`mpm`)](#install-plugins-through-microdrop-plugin-manager-mpm)
    - [Install plugins through MicroDrop GUI](#install-plugins-through-microdrop-gui)
- [Credits](#credits)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Installation #

MicroDrop can be installed using any of the methods below.

### No existing Python 2.7 32-bit Windows installation **(recommended)** ###

Download installer for latest [MicroDrop 1.0 release][4].

This installer is a customized distribution of the popular [`Miniconda`][5]
Python.


### Existing `anaconda` (Python 2.7 32-bit Windows) installation **(recommended)** ###

Run:

    conda install -c wheeler-microfluidics "microdrop>=1.0,<2.0" microdrop-launcher

**Note** *the `-c wheeler-microfluidics` flag allows installing conda packages
from  the `wheeler-microfluidics` channel*.


### Create a separate `conda` environment for MicroDrop ###

Run:

    conda create -n microdrop -c wheeler-microfluidics "microdrop>=1.0,<2.0" microdrop-launcher

To activate the MicroDrop `conda` environment, run:

    activate microdrop

To deactivate the MicroDrop `conda` environment, run:

    deactivate

See ["Managing environments"][15] section of Conda documentation for more
information.


### Other Python 2.7 32-bit Windows installation (using `pip`, **not recommended**) ###

 1. Update `pip`:

        pip install -U pip

 2. Install microdrop from [PyPi][3]:

        pip install --find-links http://192.99.4.95/wheels --trusted-host 192.99.4.95 "microdrop>=1.0,<2.0"

**Note** *`192.99.4.95` is the IP address of the official MicroDrop update
server where MicroDrop dependencies not available on PyPI are stored as
wheels*.

<img align="right" src="https://github.com/wheeler-microfluidics/microdrop/wiki/images/microdrop-shortcuts.png" />

## **Shortcuts** ##

If MicroDrop is installed using a Conda Python distribution (including the [official installer][1])

 - **Documentation**: Open [online MicroDrop documentation][readthedocs].
 - **GitHub project**: Open MicroDrop [GitHub project page][github].
 - **MicroDrop Profile Manager**: Launch MicroDrop profile manager.
 - **MicroDrop environment prompt**: Launch Windows command prompt with
   MicroDrop Conda environment activated.
 - **MicroDrop**: Launch MicroDrop if only one **profile** is available
   *(default)*.  Otherwise, launch **MicroDrop Profile Manager** to select
   **profile** to launch.
     * **Tip**: Right-click on shortcut to **pin** to **taskbar** for easy
       access.

## **Import** profile ##

If existing **profile** directory is not automatically found, it can be
manually **imported** by launching the **"MicroDrop Profile Manager"**
shortcut.

See [Profile Manager](#profile-manager-new) section below.

# Profile Manager **(new)** #

In environments where, for example, multiple users are using the same computer
to perform MicroDrop experiments, it can be helpful to create separate
MicroDrop **profiles**.  Each MicroDrop **profile** contains **devices** and
**plugins**, as well as **experiment logs**.

The **MicroDrop Profile Manager** provides an interface to manage one or more
MicroDrop profiles.  Initially, the **default profile path** (i.e.,
`<Documents>\Microdrop`) is listed.

As shown below:

 - Profiles are **listed** according when they were last launched, with the
   **most recently used profile first**.
 - Existing profiles may be **imported**.
 - Listed profiles may be **removed** from the profile list (and optionally
   **deleted** entirely).
 - Listed profiles may be **opened** in the system file browser.
 - MicroDrop may be **launched** using any of the listed profiles.

![MicroDrop Profile Manager][microdrop-profile-manager]


## Import profile ##

When an existing **profile** is imported, **plugin** dependencies are installed
while the following dialog is displayed:

![MicroDrop Profile Manager - install dependencies][install-dependencies]

## Remove profile ##

The following **dialog** is displayed when the **Remove** button for a listed
profile is **clicked**:

![MicroDrop Profile Manager - remove profile][remove-profile]

Clicking the **Remove** button in the dialog removes the corresponding
**profile** from the list, but **does not** delete any files.  The **profile**
can be imported to add it back to the profile list.

**Warning:** Clicking the **Remove with data** button in the dialog removes the
corresponding **profile** from the list, **and deletes the profile directory**.
This **cannot be undone**.


# Install plugins #

Plugins can either be installed using the [MicroDrop plugin
manager](#install-plugins-through-microdrop-plugin-manager-mpm) command-line
tool, or through the [MicroDrop user
interface](#install-plugins-through-microdrop-gui).

### Featured plugins ###

 - [`dmf_control_board`][7]
     * Control actuation parameters for the [DropBot][12] open-source Digital
       Microfluidic (DMF) automation system.

### Install plugins through MicroDrop plugin manager (`mpm`) ###

The Microdrop plugin manager is a command-line tool (inspired by `pip`) for
managing (e.g., install, uninstall) Microdrop plugins.

For full usage details, see the [project home page][14].

Basic usage to install a plugin:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install plugin [plugin [plugin ...]]

To install featured plugins:

    python -m mpm -c <microdrop settings directory>\microdrop.ini install dmf_control_board

### Install plugins through MicroDrop GUI ###

 1. Install plugins:

     ![Install MicroDrop plugins][install-plugins]

 2. Relaunch MicroDrop.


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
[15]: http://conda.pydata.org/docs/using/envs.html

[github]: https://github.com/wheeler-microfluidics/microdrop/tree/release-1.0
[readthedocs]: http://microdrop.readthedocs.io/
[install-plugins]: microdrop/static/images/plugins-install.gif
[microdrop-profile-manager]: https://github.com/wheeler-microfluidics/microdrop/wiki/images/microdrop-plugin-manager-annotated.png
[install-dependencies]: https://github.com/wheeler-microfluidics/microdrop/wiki/images/plugin-manager-install-dependencies.png
[remove-profile]: https://github.com/wheeler-microfluidics/microdrop/wiki/images/plugin-manager-remove.png

Credits
=======

Ryan Fobel <ryan@fobel.net>

Christian Fobel <christian@fobel.net>
