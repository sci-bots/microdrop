"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

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
import os
import traceback
import shutil
from copy import deepcopy
import logging

import gtk
import numpy as np
import pandas as pd
from flatland import Form
from path_helpers import path
from pygtkhelpers.ui.notebook import add_filters
from pygtkhelpers.ui.extra_widgets import Directory
from pygtkhelpers.ui.extra_dialogs import text_entry_dialog
from microdrop_device_converter import convert_device_to_svg
from microdrop_utility.gui import yesno
from microdrop_utility import copytree

from .dmf_device_view import DmfDeviceView
from ..app_context import get_app
from ..dmf_device import DmfDevice
from ..plugin_helpers import AppDataController
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ScheduleRequest, emit_signal)
from .. import base_path

logger = logging.getLogger(__name__)

PluginGlobals.push_env('microdrop')

# Define name of device file.  Name of device is inferred from name of parent
# directory when device is loaded.
OLD_DEVICE_FILENAME = 'device'
DEVICE_FILENAME = 'device.svg'


class DmfDeviceOptions(object):
    def __init__(self, state_of_channels=None):
        app = get_app()
        if state_of_channels is None:
            self.state_of_channels = np.zeros(app.dmf_device.max_channel() + 1)
        else:
            self.state_of_channels = deepcopy(state_of_channels)
        self._drop_routes = None

    def reset_drop_routes(self):
        # Empty table of drop routes.
        self._drop_routes = pd.DataFrame(None, columns=['route_i',
                                                        'transition_i',
                                                        'electrode_i'],
                                         dtype=int)

    @property
    def drop_routes(self):
        if not hasattr(self, '_drop_routes') or self._drop_routes is None:
            # Empty table of drop routes.
            self.reset_drop_routes()
        return self._drop_routes

    @drop_routes.setter
    def drop_routes(self, value):
        self._drop_routes = value


class DmfDeviceController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.dmf_device_controller"
        self.view = DmfDeviceView(self, 'device_view')
        self.previous_device_dir = None
        self.recording_enabled = False
        self._modified = False
        self._bitrate = None
        self._record_path = None
        self._recording = False
        self._AppFields = None

    @property
    def AppFields(self):
        if self._AppFields is None:
            self._AppFields = self._populate_app_fields()
        return self._AppFields

    def _populate_app_fields(self):
        field_list = [Directory.named('device_directory').using(default='',
                                                                optional=True)]
        return Form.of(*field_list)

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value
        self.menu_save_dmf_device.set_sensitive(value)


    def on_app_options_changed(self, plugin_name):
        try:
            if plugin_name == self.name:
                values = self.get_app_values()
                if 'device_directory' in values:
                    self.apply_device_dir(values['device_directory'])
        except (Exception,):
            logger.info(''.join(traceback.format_exc()))
            raise

    def apply_device_dir(self, device_directory):
        app = get_app()

        # if the device directory is empty or None, set a default
        if not device_directory:
            device_directory = path(app.config.data['data_dir']).joinpath(
                'devices')
            self.set_app_values({'device_directory': device_directory})

        if self.previous_device_dir and (device_directory ==
                                         self.previous_device_dir):
            # If the data directory hasn't changed, we do nothing
            return False

        device_directory = path(device_directory)
        if self.previous_device_dir:
            device_directory.makedirs_p()
            if device_directory.listdir():
                result = yesno('Merge?', '''\
Target directory [%s] is not empty.  Merge contents with
current devices [%s] (overwriting common paths in the target
directory)?''' % (device_directory, self.previous_device_dir))
                if not result == gtk.RESPONSE_YES:
                    return False

            original_directory = path(self.previous_device_dir)
            for d in original_directory.dirs():
                copytree(d, device_directory.joinpath(d.name))
            for f in original_directory.files():
                f.copyfile(device_directory.joinpath(f.name))
            original_directory.rmtree()
        elif not device_directory.isdir():
            # if the device directory doesn't exist, copy the skeleton dir
            device_directory.parent.makedirs_p()
            base_path().joinpath('devices').copytree(device_directory)
        self.previous_device_dir = device_directory
        return True

    def clear_drop_routes(self, electrode_id=None, step_number=None):
        '''
        Clear all drop routes for current protocol step that include the
        specified electrode (identified by string identifier).
        '''
        app = get_app()
        step_options = self.get_step_options(step_number)

        if electrode_id is None:
            step_options.reset_drop_routes()
        else:
            drop_routes = step_options.drop_routes
            # Look up numeric index based on text electrode id.
            electrode_index = app.dmf_device.shape_indexes[electrode_id]

            # Find indexes of all routes that include electrode.
            routes_to_clear = drop_routes.loc[drop_routes.electrode_i ==
                                              electrode_index, 'route_i']
            # Remove all routes that include electrode.
            step_options.drop_routes = (drop_routes
                                        .loc[~drop_routes.route_i
                                             .isin(routes_to_clear
                                                   .tolist())].copy())

    def on_plugin_enable(self):
        app = get_app()

        self.event_box_dmf_device = app.builder.get_object(
                'event_box_dmf_device')
        self.event_box_dmf_device.add(self.view.device_area)
        self.event_box_dmf_device.show_all()
        self.view.connect('channel-state-changed', lambda x, y:
                          self._notify_observers_step_options_changed())

        self.menu_load_dmf_device = app.builder.get_object('menu_load_dmf_device')
        self.menu_import_dmf_device = app.builder.get_object('menu_import_dmf_device')
        self.menu_rename_dmf_device = app.builder.get_object('menu_rename_dmf_device')
        self.menu_save_dmf_device = app.builder.get_object('menu_save_dmf_device')
        self.menu_save_dmf_device_as = app.builder.get_object('menu_save_dmf_device_as')

        app.signals["on_menu_load_dmf_device_activate"] = self.on_load_dmf_device
        app.signals["on_menu_import_dmf_device_activate"] = \
                self.on_import_dmf_device
        app.signals["on_menu_rename_dmf_device_activate"] = self.on_rename_dmf_device
        app.signals["on_menu_save_dmf_device_activate"] = self.on_save_dmf_device
        app.signals["on_menu_save_dmf_device_as_activate"] = self.on_save_dmf_device_as
        app.signals["on_event_box_dmf_device_size_allocate"] = self.on_size_allocate
        app.dmf_device_controller = self
        defaults = self.get_default_app_options()
        data = app.get_data(self.name)
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        app.set_data(self.name, data)
        emit_signal('on_app_options_changed', [self.name])

        # disable menu items until a device is loaded
        self.menu_rename_dmf_device.set_sensitive(False)
        self.menu_save_dmf_device.set_sensitive(False)
        self.menu_save_dmf_device_as.set_sensitive(False)

    def on_protocol_pause(self):
        if self._recording:
            self.stop_recording()

    def on_app_exit(self):
        self.save_check()

    def get_default_options(self):
        return DmfDeviceOptions()

    def get_step_options(self, step_number=None):
        """
        Return a FeedbackOptions object for the current step in the protocol.
        If none exists yet, create a new one.
        """
        app = get_app()
        if step_number is None:
            step_number = app.protocol.current_step_number
        step = app.protocol.steps[step_number]
        options = step.get_data(self.name)
        if options is None:
            # No data is registered for this plugin (for this step).
            options = self.get_default_options()
            step.set_data(self.name, options)
        return options

    def load_device(self, file_path, **kwargs):
        app = get_app()
        self.modified = False
        device = app.dmf_device
        file_path = path(file_path)

        if not file_path.isfile():
            old_version_file_path = (file_path.parent
                                     .joinpath(OLD_DEVICE_FILENAME))
            if old_version_file_path:
                # SVG device file does not exist, but old-style (i.e., v0.3.0)
                # device file found.
                try:
                    # Try to import old-style device to new SVG format.
                    self.import_device(old_version_file_path)
                    logger.warning('Auto-converted old-style device to new SVG'
                                   ' device format.  Open in Inkscape to '
                                   'verify scale and adjacent electrode '
                                   'connections.')
                except Exception, e:
                    logger.error('Error importing device. %s' % e, exc_info=True)
                return
            else:
                logger.error('Error opening device.  Please ensure file '
                             'exists and is readable.', exc_info=True)
                return

        # SVG device file exists.  Load the device.
        try:
            logger.info('[DmfDeviceController].load_device: %s' % file_path)
            device = DmfDevice.load(file_path, name=file_path.parent.name,
                                    **kwargs)
            if file_path.parent.parent != app.get_device_directory():
                logger.info('[DmfDeviceController].load_device: Copy new '
                            'device to microdrop devices directory.')
                self.modified = True
            else:
                logger.info('[DmfDeviceController].load_device: load existing '
                            'device.')
            emit_signal("on_dmf_device_swapped", [app.dmf_device, device])
        except:
            logger.error('Error loading device.', exc_info=True)

    def save_check(self):
        app = get_app()
        if self.modified:
            result = yesno('Device %s has unsaved changes.  Save now?' %
                           app.dmf_device.name)
            if result == gtk.RESPONSE_YES:
                self.save_dmf_device()

    def save_dmf_device(self, save_as=False, rename=False):
        '''
        Save device configuration.

        If `save_as=True`, we are saving a copy of the current device with a
        new name.

        If `rename=True`, we are saving the current device with a new name _(no
        new copy is created)_.
        '''
        app = get_app()

        name = app.dmf_device.name
        # If the device has no name, try to get one.
        if save_as or rename or name is None:
            if name is None:
                name = ""
            name = text_entry_dialog('Device name', name, 'Save device')
            if name is None:
                name = ""

        if name:
            # Construct the directory name for the current device.
            if app.dmf_device.name:
                src = os.path.join(app.get_device_directory(),
                                   app.dmf_device.name)
            # Construct the directory name for the new device _(which is the
            # same as the current device, if we are not renaming or "saving
            # as")_.
            dest = os.path.join(app.get_device_directory(), name)

            # If we're renaming, move the old directory.
            if rename and os.path.isdir(src):
                if src == dest:
                    return
                if os.path.isdir(dest):
                    logger.error("A device with that "
                                 "name already exists.")
                    return
                shutil.move(src, dest)

            # Create the directory for the new device name, if it doesn't
            # exist.
            if not os.path.isdir(dest):
                os.mkdir(dest)

            # Convert device to SVG string.
            svg_unicode = app.dmf_device.to_svg()

            # Save the device to the new target directory.
            with open(os.path.join(dest, DEVICE_FILENAME), 'wb') as output:
                output.write(svg_unicode)

            # Reset modified status, since save acts as a checkpoint.
            self.modified = False

            # If the device name has changed, update the application device
            # state.
            if name != app.dmf_device.name:
                new_device_filepath = os.path.join(dest, DEVICE_FILENAME)
                self.load_device(new_device_filepath)

    def on_step_options_changed(self, plugin_name, step_number):
        '''
        The step options for the current step have changed.
        If the change was to options affecting this plugin, update state.
        '''
        app = get_app()
        if (plugin_name == self.name) and (app.protocol.current_step_number ==
                                           step_number):
            self._update()

    def on_step_inserted(self, step_number, *args):
        app = get_app()
        logging.info('[on_step_inserted] current step=%s, created step=%s',
                     app.protocol.current_step_number, step_number)
        self.clear_drop_routes(step_number=step_number)
        gtk.idle_add(self._update)

    def on_step_swapped(self, old_step_number, step_number):
        self._update()

    def _notify_observers_step_options_changed(self):
        app = get_app()
        if not app.dmf_device:
            return
        emit_signal('on_step_options_changed',
                    [self.name, app.protocol.current_step_number],
                    interface=IPlugin)

    def on_size_allocate(self, widget, data=None):
        pass  # TODO: resize device drawing

    def _update(self):
        app = get_app()
        if not app.dmf_device:
            return
        options = self.get_step_options()
        if options.state_of_channels.max() == 0:
            # No channels are actuated.
            actuated_channels_index = []
        else:
            actuated_channels_index = np.where(options
                                               .state_of_channels > 0)[0]
        actuated_electrodes = (app.dmf_device
                               .actuated_electrodes(actuated_channels_index))

        self.view.electrode_color = {}
        for electrode_id in actuated_electrodes:
            self.view.electrode_color[electrode_id] = [1, 1, 1]
        self.view.update_draw_queue()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.config_controller',
                                    self.name),
                    ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        elif function_name == 'on_dmf_device_swapped':
            return [ScheduleRequest('microdrop.app', self.name),
                    ScheduleRequest('microdrop.gui.protocol_controller',
                                    self.name)]
        return []

    # GUI callbacks

    def on_load_dmf_device(self, widget, data=None):
        self.save_check()
        app = get_app()
        directory = app.get_device_directory()
        dialog = gtk.FileChooserDialog(title="Load device",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        if directory:
            dialog.set_current_folder(directory)
        add_filters(dialog, [{'name': 'DMF device (*.svg)',
                              'pattern': '*.svg'}])
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.load_device(filename)
        dialog.destroy()

    def on_import_dmf_device(self, widget, data=None):
        self.save_check()
        app = get_app()
        dialog = gtk.FileChooserDialog(title="Import device",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        add_filters(dialog, [{'name': 'DMF device version 0.3.0 (device)',
                              'pattern': 'device'}])
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            try:
                self.import_device(filename)
            except Exception, e:
                logger.error('Error importing device. %s' % e, exc_info=True)

    def import_device(self, input_device_path):
        input_device_path = path(input_device_path).abspath()
        output_device_path = (input_device_path.parent
                              .joinpath(input_device_path.namebase + '.svg'))
        overwrite = False
        if output_device_path.isfile():
            result = yesno('Output file exists.  Overwrite?')
            if not result == gtk.RESPONSE_YES:
                return
            overwrite = True
        convert_device_to_svg(input_device_path, output_device_path,
                                use_svg_path=True,
                                detect_connections=True, extend_mm=.5,
                                overwrite=overwrite)
        self.load_device(output_device_path)

    def on_rename_dmf_device(self, widget, data=None):
        self.save_dmf_device(rename=True)

    def on_save_dmf_device(self, widget, data=None):
        self.save_dmf_device()

    def on_save_dmf_device_as(self, widget, data=None):
        self.save_dmf_device(save_as=True)

    def on_dmf_device_swapped(self, old_device, new_device):
        self.menu_rename_dmf_device.set_sensitive(True)
        self.menu_save_dmf_device_as.set_sensitive(True)
        self.view.reset_canvas()
        self._update()

    def on_dmf_device_changed(self):
        self.modified = True

PluginGlobals.pop_env()
