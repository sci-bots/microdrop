MicroDrop
=========

Microdrop is a graphical user interface for the [DropBot][1] digital
microfluidics control system (described in detail in [Fobel et al., Appl. Phys.
Lett. 102, 193513 (2013)][2]). If you use this information in work that you
publish, please cite as appropriate.


Binary package dependencies
===========================

In addition to the package dependencies listed in `setup.py`, the MicroDrop
application requires the following Python packages to be installed:

 - `matplotlib`: Used to plot feedback results, etc.
 - `pygst`: Used for video-processing in the device view.
 - `pygtk`: [GTK][3] bindings for user-interface.
 - `pyopencv`: Used to transform incoming video feed to register the device in
   the device view to the overlay perspective.
 - `pymunk==2.1.0` _(*not* the latest)_: Used for detecting the electrode
   corresponding to each click on the device view
   _(i.e., [collision detection][4])_.

Note that these packages contain binary components that typically prevent them
from being installed using `easy_install` or `pip` without taking special care
to configure the appropriate build environment.  However, there are pre-built
binary packages available for both Windows and Linux, if you search for them.


[1]: http://microfluidics.utoronto.ca/microdrop
[2]: http://dx.doi.org/10.1063/1.4807118
[3]: http://www.pygtk.org/
[4]: http://chipmunk-physics.net/release/ChipmunkLatest-Docs/#CollisionDetection


Credits
=======

Ryan Fobel <ryan@fobel.net>
Christian Fobel <christian@fobel.net>
