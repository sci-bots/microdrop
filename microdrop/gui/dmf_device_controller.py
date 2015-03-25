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
try:
    import cPickle as pickle
except ImportError:
    import pickle

import gtk
import numpy as np
from flatland import Form, Integer, String, Boolean
from path_helpers import path
import yaml
from pygtkhelpers.ui.extra_widgets import Directory, Enum
from pygtkhelpers.ui.extra_dialogs import text_entry_dialog
from pygst_utils.video_pipeline.window_service_proxy import WindowServiceProxy
from pygst_utils.video_source import GstVideoSourceManager
from microdrop_utility.gui import yesno
from microdrop_utility import copytree

from ..app_context import get_app
from ..dmf_device import DmfDevice
from ..logger import logger
from ..plugin_helpers import AppDataController
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ScheduleRequest, emit_signal)
from .dmf_device_view import DmfDeviceView
from .. import base_path

PluginGlobals.push_env('microdrop')


class DmfDeviceOptions(object):
    def __init__(self, state_of_channels=None):
        app = get_app()
        if state_of_channels is None:
            self.state_of_channels = np.zeros(app.dmf_device.max_channel() + 1)
        else:
            self.state_of_channels = deepcopy(state_of_channels)


class DmfDeviceController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.dmf_device_controller"
        self.view = DmfDeviceView(self, 'device_view')
        self.view.connect('transform-changed', self.on_transform_changed)
        self.previous_device_dir = None
        self.recording_enabled = False
        self._modified = False
        self._video_initialized = False
        self._video_enabled = False
        self._gui_initialized = False
        self._bitrate = None
        self._record_path = None
        self._recording = False
        self._AppFields = None
        self._video_available = False

    @property
    def AppFields(self):
        if self._AppFields is None:
            self._AppFields = self._populate_app_fields()
        return self._AppFields

    def _populate_app_fields(self):
        with WindowServiceProxy(59000) as w:
            self.video_mode_map = w.get_video_mode_map()
            if self.video_mode_map:
                self._video_available = True
            else:
                self._video_available = False
            self.video_mode_keys = sorted(self.video_mode_map.keys())
            if self._video_available:
                self.device_key, self.devices = w.get_video_source_configs()

        field_list = [
            Integer.named('overlay_opacity').using(default=50, optional=True),
            Directory.named('device_directory').using(default='', optional=True),
            String.named('transform_matrix').using(default='', optional=True,
                                                properties={'show_in_gui':
                                                            False}), ]

        if self._video_available:
            video_mode_enum = Enum.named('video_mode').valued(
                *self.video_mode_keys).using(default=self.video_mode_keys[0],
                                             optional=True)
            video_enabled_boolean = Boolean.named('video_enabled').using(
                default=False, optional=True, properties={'show_in_gui': True})
            recording_enabled_boolean = Boolean.named('recording_enabled').using(
                default=False, optional=True, properties={'show_in_gui': False})
            field_list.append(video_mode_enum)
            field_list.append(video_enabled_boolean)
            field_list.append(recording_enabled_boolean)
        return Form.of(*field_list)

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value
        self.menu_save_dmf_device.set_sensitive(value)

    @property
    def video_enabled(self):
        return self._video_enabled

    @video_enabled.setter
    def video_enabled(self, value):
        if not self._video_available and value:
            raise ValueError('Video cannot be enabled with no sources.')
        self._video_enabled = value

    def on_video_started(self, device_view, start_time):
        self.set_app_values(
            dict(transform_matrix=self.get_app_value('transform_matrix')))

    def on_transform_changed(self, device_view, array):
        self.set_app_values(
            dict(transform_matrix=yaml.dump(array.tolist())))

    def on_gui_ready(self):
        self._gui_initialized = True
        gtk.timeout_add(50, self._initialize_video)

    def on_app_options_changed(self, plugin_name):
        try:
            if plugin_name == self.name:
                values = self.get_app_values()
                if self._video_available and 'video_enabled' in values:
                    video_enabled = values['video_enabled']
                    if not (self.video_enabled and video_enabled):
                        if video_enabled:
                            self.video_enabled = True
                        else:
                            self.video_enabled = False
                        self.reset_video()
                if 'device_directory' in values:
                    self.apply_device_dir(values['device_directory'])
                if self.video_enabled:
                    if'overlay_opacity' in values:
                        self.view.overlay_opacity = int(values.get('overlay_opacity'))
                if 'transform_matrix' in values:
                    matrix = yaml.load(values['transform_matrix'])
                    if matrix is not None and len(matrix):
                        matrix = np.array(matrix, dtype='float32')
                        def update_transform(self, matrix):
                            if self.view._proxy and self.view._proxy\
                                    .pipeline_available():
                                transform_str = ','.join([str(v)
                                        for v in matrix.flatten()])
                                self.view._proxy.set_warp_transform(transform_str)
                                return False
                            return True
                        gtk.timeout_add(10, update_transform, self, matrix)
                if 'recording_enabled' in values:
                    self.recording_enabled = values['recording_enabled']
                if 'video_mode' in values:
                    video_mode = values['video_mode']
                    if video_mode is not None\
                            and video_mode != self.video_mode:
                        self.video_mode = video_mode
        except (Exception,):
            logger.info(''.join(traceback.format_exc()))
            raise

    @property
    def video_mode(self):
        if not hasattr(self, '_video_mode'):
            self._video_mode = self.video_mode_keys[0]
        return self._video_mode

    @video_mode.setter
    def video_mode(self, value):
        '''
        When the video_mode are set, we must force the video
        pipeline to be re-initialized.
        '''
        self._video_mode = value
        self.reset_video()

    def reset_video(self):
        self.view.destroy_video_proxy()
        self._video_initialized = False

    def _initialize_video(self):
        '''
        Initialize video if necessary.

        Note that this function must only be called by the main GTK
        thread.  Otherwise, dead-lock will occur.  Currently, this is
        ensured by calling this function in a gtk.timeout_add() call.
        '''
        if not self._video_initialized:
            if self._gui_initialized and self._video_available\
                    and self.video_enabled and self.view.window_xid\
                            and self.video_mode:
                self._video_initialized = True
                selected_mode = self.video_mode_map[self.video_mode]
                caps_str = GstVideoSourceManager.get_caps_string(selected_mode)
                if self.recording_enabled:
                    bitrate = self._bitrate
                    record_path = self._record_path
                else:
                    bitrate = None
                    record_path = None
                self.view._initialize_video(str(selected_mode['device']),
                                            str(caps_str),
                                            record_path=record_path,
                                            bitrate=bitrate)
                self.set_app_values({'transform_matrix':
                                     self.get_app_value('transform_matrix')})
                if self.recording_enabled:
                    self._recording = True
            else:
                x, y, width, height = self.view.widget.get_allocation()
                self.view._initialize_video('',
                                            'video/x-raw-yuv,width={},height={}'
                                            .format(width, height))
                self._video_initialized = True
        return True

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

    def on_plugin_enable(self):
        app = get_app()

        self.event_box_dmf_device = app.builder.get_object(
                'event_box_dmf_device')
        self.event_box_dmf_device.add(self.view.device_area)
        self.event_box_dmf_device.show_all()
        self.view.connect('channel-state-changed',
                lambda x, y: self._notify_observers_step_options_changed())

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

    def stop_recording(self):
        self._bitrate = None
        self._record_path = None
        self.reset_video()
        self._recording = False
        logging.info('[DmfDeviceController] recording stopped')

    def start_recording(self, record_path):
        self._bitrate = 150000
        self._record_path = str(path(record_path).abspath())
        self._recording = False
        self.reset_video()
        logging.info('[DmfDeviceController] recording to: {}'.format(
                self._record_path))

    def on_protocol_run(self):
        app = get_app()
        log_dir = path(app.experiment_log.get_log_path())
        video_path = log_dir.joinpath('%s.avi' % log_dir.name)
        if self.recording_enabled:
            self.start_recording(video_path)

    def on_protocol_pause(self):
        if self._recording:
            self.stop_recording()

    def on_app_exit(self):
        self.save_check()
        self.view.destroy_video_proxy()

    def get_default_options(self):
        return DmfDeviceOptions()

    def get_step_options(self, step=None):
        """
        Return a FeedbackOptions object for the current step in the protocol.
        If none exists yet, create a new one.
        """
        app = get_app()
        options = app.protocol.current_step().get_data(self.name)
        if options is None:
            # No data is registered for this plugin (for this step).
            options = self.get_default_options()
            app.protocol.current_step().set_data(self.name, options)
        return options

    def load_device(self, filename):
        app = get_app()
        self.modified = False
        device = app.dmf_device
        try:
            logger.info('[DmfDeviceController].load_device: %s' % filename)
            device = DmfDevice.load(str(filename))
            if path(filename).parent.parent != app.get_device_directory():
                logger.info('[DmfDeviceController].load_device: Import new '
                            'device.')
                self.modified = True
            else:
                logger.info('[DmfDeviceController].load_device: load existing '
                            'device.')
            emit_signal("on_dmf_device_swapped", [app.dmf_device,
                                                  device])
        except Exception, e:
            logger.error('Error loading device: %s.' % e)
            logger.info(''.join(traceback.format_exc()))

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

            # If the device name has changed, update the application device
            # state.
            if name != app.dmf_device.name:
                app.dmf_device.name = name
                # Update GUI to reflect updated name.
                app.main_window_controller.update_device_name_label()

            # Save the device to the new target directory.
            app.dmf_device.save(os.path.join(dest, "device"))
            # Reset modified status, since save acts as a checkpoint.
            self.modified = False

    def on_step_options_changed(self, plugin_name, step_number):
        '''
        The step options for the current step have changed.
        If the change was to options affecting this plugin, update state.
        '''
        app = get_app()
        if (app.protocol.current_step_number == step_number and plugin_name ==
                self.name):
            self._update()

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
        self.reset_video()

    def _update(self):
        app = get_app()
        if not app.dmf_device:
            return
        options = self.get_step_options()
        state_of_channels = options.state_of_channels
        for id, electrode in app.dmf_device.electrodes.iteritems():
            channels = app.dmf_device.electrodes[id].channels
            if channels:
                # Get the state(s) of the channel(s) connected to this
                # electrode.
                states = state_of_channels[channels]

                # If all of the states are the same.
                if len(np.nonzero(states == states[0])[0]) == len(states):
                    if states[0] > 0:
                        self.view.electrode_color[id] = [1, 1, 1]
                    else:
                        color = app.dmf_device.electrodes[id].path.color
                        self.view.electrode_color[id] = [c / 255.
                                                         for c in color]
                else:
                    # TODO: This could be used for resistive heating.
                    logger.error("not supported yet")
            else:
                # Assign the color _red_ to any electrode that has no assigned
                # channels.
                self.view.electrode_color[id] = [1, 0, 0]
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
        filter = gtk.FileFilter()
        filter.set_name("*.svg")
        filter.add_pattern("*.svg")
        dialog.add_filter(filter)
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        if response == gtk.RESPONSE_OK:
            try:
                dmf_device = DmfDevice.load_svg(filename)
                self.modified = True
                emit_signal("on_dmf_device_swapped", [app.dmf_device,
                                                          dmf_device])
            except Exception, e:
                logger.error('Error importing device. %s' % e)
                logger.info(''.join(traceback.format_exc()))

    def on_rename_dmf_device(self, widget, data=None):
        self.save_dmf_device(rename=True)

    def on_save_dmf_device(self, widget, data=None):
        self.save_dmf_device()

    def on_save_dmf_device_as(self, widget, data=None):
        self.save_dmf_device(save_as=True)

    def on_dmf_device_swapped(self, old_device, new_device):
        self.menu_rename_dmf_device.set_sensitive(True)
        self.menu_save_dmf_device_as.set_sensitive(True)
        if old_device is None:
            # need to reset the video to display the device
            self.reset_video()
        self._update()

    def on_dmf_device_changed(self):
        self.modified = True

PluginGlobals.pop_env()
