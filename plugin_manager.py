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

from pyutilib.component.core import Interface, ExtensionPoint, \
                                    SingletonPlugin, implements
import pyutilib.component.loader

class PluginManager():
    def __init__(self):
        pyutilib.component.loader.PluginGlobals.load_services(
            path="plugins", auto_disable=False)

class IPlugin(Interface):
    def edit_options():
        """
        Edit the options for this plugin. 
        """
        pass
    
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

    def on_protocol_update():
        """
        Handler called whenever the current protocol step changes.
        """
        pass

    def on_delete_protocol_step():
        """
        Handler called whenever a protocol step is deleted.
        """
        pass

    def on_insert_protocol_step():
        """
        Handler called whenever a protocol step is inserted.
        """
        pass

    def on_protocol_run():
        """
        Handler called when a protocol starts running.
        """
        pass
    
    def on_protocol_pause():
        """
        Handler called when a protocol is paused.
        """
        pass