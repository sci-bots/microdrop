"""
Copyright 2014 Ryan Fobel

This file is part of analyst_remote_plugin.

analyst_remote_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with analyst_remote_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""

from path_helpers import path
from flatland import Integer, Boolean, Form, String
from flatland.validation import ValueAtLeast, ValueAtMost
from microdrop.logger import logger
from microdrop.plugin_helpers import (AppDataController, StepOptionsController,
                                      get_plugin_info)
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, emit_signal)
from microdrop.app_context import get_app
from analyst_remote_control import AnalystRemoteControl


PluginGlobals.push_env('microdrop.managed')

class AnalystRemotePlugin(Plugin, AppDataController, StepOptionsController):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    version = get_plugin_info(path(__file__).parent).version
    plugin_name = get_plugin_info(path(__file__).parent).plugin_name

    '''
    AppFields
    ---------

    A flatland Form specifying application options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed AppDataController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the app options dialog
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently in the microdrop
            config file, in a section named after this plugin's name attribute
    '''
    AppFields = Form.of(
        String.named('subscribe_uri').using(optional=True),
        String.named('request_uri').using(optional=True),
    )

    '''
    StepFields
    ---------

    A flatland Form specifying the per step options for the current plugin.
    Note that nested Form objects are not supported.

    Since we subclassed StepOptionsController, an API is available to access and
    modify these attributes.  This API also provides some nice features
    automatically:
        -all fields listed here will be included in the protocol grid view
            (unless properties=dict(show_in_gui=False) is used)
        -the values of these fields will be stored persistently for each step
    '''
    StepFields = Form.of(
        Boolean.named('acquire').using(default=False, optional=True),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.timeout_id = None
        self.remote = None

    def on_step_run(self):
        """
        Handler called whenever a step is executed. Note that this signal
        is only emitted in realtime mode or if a protocol is running.

        Plugins that handle this signal must emit the on_step_complete
        signal once they have completed the step. The protocol controller
        will wait until all plugins have completed the current step before
        proceeding.

        return_value can be one of:
            None
            'Repeat' - repeat the step
            or 'Fail' - unrecoverable error (stop the protocol)
        """
        app = get_app()
        logger.info('[AnalystRemotePlugin] on_step_run(): step #%d',
                    app.protocol.current_step_number)
        # If `acquire` is `True`, start acquisition
        options = self.get_step_options()
        if options['acquire']:
            app_values = self.get_app_values()
            try:
                if self.timeout_id is not None:
                    # Timer was already set, so cancel previous timer.
                    gobject.source_remove(self.timeout_id)
                self.remote = AnalystRemoteControl(app_values['subscribe_uri'],
                                                   app_values['request_uri'])
                self.remote.start_acquisition()
                self.timeout_id = gobject.timeout_add(options.duration,
                                                      self.remote_check_tick)
            except:
                # An error occurred while initializing Analyst remote control.
                emit_signal('on_step_complete', [self.name, 'Fail'])

    def remote_check_tick(self):
        if self.remote is not None:
            try:
                if self.remote.acquisition_complete():
                    # Acquisition is complete so notify step complete.
                    emit_signal('on_step_complete', [self.name, None])
                    self.timeout_id = None
                    return False
            except:
                emit_signal('on_step_complete', [self.name, 'Fail'])
                self.timeout_id = None
                return False
        return True

    def on_step_options_swapped(self, plugin, old_step_number, step_number):
        """
        Handler called when the step options are changed for a particular
        plugin.  This will, for example, allow for GUI elements to be
        updated based on step specified.

        Parameters:
            plugin : plugin instance for which the step options changed
            step_number : step number that the options changed for
        """
        pass

    def on_step_swapped(self, old_step_number, step_number):
        """
        Handler called when the current step is swapped.
        """


PluginGlobals.pop_env()
