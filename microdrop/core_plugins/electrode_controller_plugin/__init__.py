"""
Copyright 2015 Christian Fobel

This file is part of droplet_planning_plugin.

droplet_planning_plugin is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

dmf_control_board is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with droplet_planning_plugin.  If not, see <http://www.gnu.org/licenses/>.
"""
import sys, traceback
from datetime import datetime
from collections import OrderedDict

from path_helpers import path
from flatland import Integer, Boolean, Form, String
from flatland.validation import ValueAtLeast, ValueAtMost
from microdrop.logger import logger
from microdrop.plugin_helpers import (AppDataController, StepOptionsController,
                                      get_plugin_info)
from microdrop.plugin_manager import (PluginGlobals, Plugin, IPlugin,
                                      implements, emit_signal)
from microdrop.app_context import get_app
import gobject
import gtk

PluginGlobals.push_env('microdrop.managed')

class DropletPlanningPlugin(Plugin, AppDataController, StepOptionsController):
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
        Integer.named('transition_duration_ms').using(optional=True,
                                                      default=750),
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
        Integer.named('min_duration').using(default=0, optional=True),
    )

    def __init__(self):
        self.name = self.plugin_name
        self.timeout_id = None
        self.start_time = None
        self.transition_counter = 0

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
        logger.info('[DropletPlanningPlugin] on_step_run(): step #%d',
                    app.protocol.current_step_number)
        app_values = self.get_app_values()
        device_step_options = app.dmf_device_controller.get_step_options()
        try:
            if self.timeout_id is not None:
                # Timer was already set, so cancel previous timer.
                gobject.source_remove(self.timeout_id)

            drop_route_groups = (device_step_options.drop_routes
                                 .groupby('route_i'))
            # Look up the drop routes for the current step.
            self.step_drop_routes = OrderedDict([(route_i, df_route_i)
                                                 for route_i, df_route_i in
                                                 drop_route_groups])
            # Get the number of transitions in each drop route.
            self.step_drop_route_lengths = drop_route_groups['route_i'].count()
            self.transition_counter = 0
            self.start_time = datetime.now()
            gobject.idle_add(self.on_timer_tick, False)
            self.timeout_id = gobject.timeout_add(app_values
                                                  ['transition_duration_ms'],
                                                  self.on_timer_tick)
        except:
            print "Exception in user code:"
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60
            # An error occurred while initializing Analyst remote control.
            emit_signal('on_step_complete', [self.name, 'Fail'])

    def on_timer_tick(self, continue_=True):
        app = get_app()
        try:
            if self.transition_counter < self.step_drop_route_lengths.max():
                active_step_lengths = (self.step_drop_route_lengths
                                       .loc[self.step_drop_route_lengths >
                                            self.transition_counter])
                device_view = app.dmf_device_controller.view
                for route_i, length_i in active_step_lengths.iteritems():
                    # Remove custom coloring for previously active electrode.
                    if self.transition_counter > 0:
                        transition_i = (self.step_drop_routes[route_i]
                                        .iloc[self.transition_counter - 1])
                        device_view.set_electrode_color_by_index(transition_i
                                                                 .electrode_i)
                    # Add custom coloring to active electrode.
                    transition_i = (self.step_drop_routes[route_i]
                                    .iloc[self.transition_counter])
                    device_view.set_electrode_color_by_index(transition_i
                                                             .electrode_i,
                                                             (255, 255, 255))
                gtk.idle_add(app.dmf_device_controller.view.update_draw_queue)
                self.transition_counter += 1
            else:
                emit_signal('on_step_complete', [self.name, None])
                self.timeout_id = None
                self.start_time = None
                self.transition_counter = 0
                return False
        except:
            print "Exception in user code:"
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60
            emit_signal('on_step_complete', [self.name, 'Fail'])
            self.timeout_id = None
            self.remote = None
            return False
        return continue_

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
