"""
Copyright 2011 Ryan Fobel

This file is part of dmf_control_board.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import traceback

from pyutilib.component.core import Interface, ExtensionPoint, \
                                    SingletonPlugin, implements
import pyutilib.component.loader

from utility import path


class PluginManager():
    def __init__(self):
        print "Loading plugins:"
        for d in path("plugins").dirs():
            package = (d / path("microdrop"))
            if package.isdir(): 
                print "\t", package.abspath()
                exec("import plugins.%s.microdrop" % d.name) 
        observers = ExtensionPoint(IPlugin)
        print "Registered plugins:"
        for observer in observers:
            print "\t", observer
        observers = ExtensionPoint(IWaveformGenerator)
        print "Registered function generator plugins:"
        for observer in observers:
            print "\t", observer


class IWaveformGenerator(Interface):
    def set_voltage(self, voltage):
        """
        Set the waveform voltage.
        
        Parameters:
            voltage : RMS voltage
        """
        pass
    
    def set_frequency(self, frequency):
        """
        Set the waveform frequency.
        
        Parameters:
            frequency : frequency in Hz
        """
        pass


class IPlugin(Interface):    
    def on_app_init(app=None):
        """
        Handler called once when the Microdrop application starts.
        
        Plugins should store a reference to the app object if they need to
        access other components.
        """
        pass
    
    def on_app_exit(self):
        """
        Handler called just before the Microdrop application exists. 
        """
        pass

    def on_protocol_update(self, data):
        """
        Handler called whenever views of the protocol need to update.

        Parameters:
            data : dictionary to store experiment log data for the current step
        """
        pass

    def on_delete_protocol_step(self):
        """
        Handler called whenever a protocol step is deleted.
        """
        pass

    def on_insert_protocol_step(self):
        """
        Handler called whenever a protocol step is inserted.
        """
        pass

    def on_protocol_save(self):
        """
        Handler called when a protocol is saved.
        """
        pass
    
    def on_protocol_load(self, version, data):
        """
        Handler called when a protocol is loaded.
        """
        pass

    def on_protocol_run(self):
        """
        Handler called when a protocol starts running.
        """
        pass
    
    def on_protocol_pause(self):
        """
        Handler called when a protocol is paused.
        """
        pass

    def on_dmf_device_changed(self):
        """
        Handler called when the DMF device changes (e.g., when a new device is
        loaded).
        """
        pass

    def on_experiment_log_changed(self):
        """
        Handler called when the experiment log changes (e.g., when a protocol
        finishes running.
        """
        pass
    
    def on_experiment_log_selection_changed(self, data):
        """
        Handler called whenever the experiment log selection changes.

        Parameters:
            data : dictionary of experiment log data for the selected steps
        """
        pass


def emit_signal(function, args=[], interface=IPlugin):
    observers = ExtensionPoint(interface)
    for observer in observers:
        if hasattr(observer, function):
            try:
                if type(args) is not list:
                    args = [args]
                arg_list = []
                for i, arg in enumerate(args):
                    arg_list.append("arg%d" % i)
                    exec("arg%d=arg" % i)
                command = "observer.%s(%s)" % (function, ",".join(arg_list))
                exec(command)
            except Exception, why:
                if hasattr(observer, "name"):
                    print "%s plugin crashed." % observer.name  
                print why
                traceback.print_stack()