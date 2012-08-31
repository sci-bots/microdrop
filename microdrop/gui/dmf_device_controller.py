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
from datetime import datetime
import logging

import gtk
import numpy as np
from xml.etree import ElementTree as et
from pyparsing import Literal, Combine, Optional, Word, Group, OneOrMore, nums
from flatland import Form, Integer, String, Boolean
from flatland.validation import ValueAtLeast, ValueAtMost
from utility.gui import yesno
from path import path
import yaml
import gst

from dmf_device_view import DmfDeviceView, DeviceRegistrationDialog, Dims
from dmf_device import DmfDevice
from protocol import Protocol
from experiment_log import ExperimentLog
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin,\
        implements, PluginGlobals, ScheduleRequest, emit_signal
from app_context import get_app
from logger import logger
from opencv.safe_cv import cv
from plugin_helpers import AppDataController
from pygtkhelpers.ui.extra_widgets import Directory
from pygtkhelpers.ui.extra_dialogs import text_entry_dialog
from utility import is_float, copytree


PluginGlobals.push_env('microdrop')

class DmfDeviceOptions(object):
    def __init__(self, state_of_channels=None):
        app = get_app()
        if state_of_channels is None:
            self.state_of_channels = np.zeros(app.dmf_device.max_channel()+1)
        else:
            self.state_of_channels = deepcopy(state_of_channels)


from video_mode_dialog import get_video_mode_map, GstVideoSourceManager, create_video_source


class DmfDeviceController(SingletonPlugin, AppDataController):
    implements(IPlugin)
    implements(IAppStatePlugin)

    gtk.threads_enter()
    video_modes = GstVideoSourceManager.get_available_video_modes(
            format_='YUY2')
    video_mode_map = get_video_mode_map(video_modes)
    video_mode_keys = sorted(video_mode_map.keys())
    gtk.threads_leave()

    AppFields = Form.of(
        Boolean.named('video_enabled').using(default=False, optional=True,
                properties={'show_in_gui': False}),
        Integer.named('overlay_opacity').using(default=30, optional=True,
                validators=[ValueAtLeast(minimum=1),
                        ValueAtMost(maximum=100)]),
        Directory.named('device_directory').using(default='', optional=True),
        String.named('transform_matrix').using(default='', optional=True,
                properties={'show_in_gui': False}),
        Enum.named('video_settings').valued(*video_mode_keys).using(
                optional=True, default=video_mode_keys[0]),
    )

    def __init__(self):
        self.name = "microdrop.gui.dmf_device_controller"
        self.view = DmfDeviceView(self, 'device_view')
        self.view.connect('transform-changed', self.on_transform_changed)
        self.view.connect('video-started', self.on_video_started)
        self.previous_device_dir = None
        self.video_enabled = False
        self._modified = False
        self._video_initialized = False
        gtk.timeout_add(1000, self._initialize_video)

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value
        self.menu_save_dmf_device.set_sensitive(value)

    def on_video_started(self, device_view, start_time):
        self.set_app_values(
            dict(transform_matrix=self.get_app_value('transform_matrix')))

    def on_transform_changed(self, device_view, array):
        self.set_app_values(
            dict(transform_matrix=yaml.dump(array.tolist())))

    def on_app_options_changed(self, plugin_name):
        app = get_app()
        try:
            if plugin_name == self.name:
                values = self.get_app_values()
                if 'video_enabled' in values:
                    self.video_enabled = getattr(self, 'video_enabled', False)
                    video_enabled = values['video_enabled']
                    if not (self.video_enabled and video_enabled):
                        if video_enabled:
                            self.video_enabled = True
                        else:
                            self.video_enabled = False
                        self.set_toggle_state(self.video_enabled)
                if 'overlay_opacity' in values:
                    self.view.overlay_opacity = int(values.get('overlay_opacity'))
                if 'display_fps' in values:
                    self.view.display_fps = int(values['display_fps'])
                if 'device_directory' in values:
                    self.apply_device_dir(values['device_directory'])
                if 'transform_matrix' in values:
                    matrix = yaml.load(values['transform_matrix'])
                    if matrix is not None and len(matrix):
                        matrix = np.array(matrix, dtype='float32')
                        if self.view.pipeline:
                            self.view.transform_matrix = matrix
                if 'video_settings' in values:
                    video_settings = values['video_settings']
                    if video_settings is not None\
                            and video_settings != self.video_settings:
                        self.video_settings = video_settings
        except (Exception,), why:
            logger.info(''.join(traceback.format_exc()))
            raise

    @property
    def video_settings(self):
        if not hasattr(self, '_video_settings'):
            self._video_settings = self.video_mode_keys[0]
        return self._video_settings

    @video_settings.setter
    def video_settings(self, value):
        '''
        When the video_settings are set, we must force the video
        pipeline to be re-initialized.
        '''
        self._video_settings = value
        self._video_initialized = False

    def _initialize_video(self):
        '''
        Initialize video if necessary.

        Note that this function must only be called by the main GTK
        thread.  Otherwise, dead-lock will occur.  Currently, this is
        ensured by calling this function in a gtk.timeout_add() call.
        '''
        if not self._video_initialized and self.video_settings:
            selected_mode = self.video_mode_map[self.video_settings]
            caps_str = GstVideoSourceManager.get_caps_string(selected_mode)
            video_source = create_video_source(
                    selected_mode['device'], caps_str)
            self.view.set_source(video_source)
            self._video_initialized = True
            # Reset _prev_display_dims to force Cairo drawing to
            # scale to the new video settings.
            self.view._prev_display_dims = None
        return True

    def apply_device_dir(self, device_directory):
        app = get_app()
        if not device_directory or \
                (self.previous_device_dir and\
                device_directory == self.previous_device_dir):
            # If the data directory hasn't changed, we do nothing
            return False

        device_directory = path(device_directory)
        device_directory.makedirs_p()
        if self.previous_device_dir:
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

        self.menu_video = gtk.CheckMenuItem('Video enabled')
        self.menu_video.show_all()
        self.video_toggled_handler = self.menu_video.connect('toggled', self.on_menu_video__toggled)
        self.set_toggle_state(self.video_enabled)

        app.main_window_controller.menu_tools.append(self.menu_video)

        app.signals["on_menu_load_dmf_device_activate"] = self.on_load_dmf_device
        app.signals["on_menu_import_dmf_device_activate"] = \
                self.on_import_dmf_device
        app.signals["on_menu_rename_dmf_device_activate"] = self.on_rename_dmf_device
        app.signals["on_menu_save_dmf_device_activate"] = self.on_save_dmf_device
        app.signals["on_menu_save_dmf_device_as_activate"] = self.on_save_dmf_device_as
        app.dmf_device_controller = self
        defaults = self.get_default_app_options()
        data = app.get_data(self.name)
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        app.set_data(self.name, data)
        emit_signal('on_app_options_changed', [self.name])
        gtk.idle_add(self.init_pipeline)

        # disable menu items until a device is loaded
        self.menu_rename_dmf_device.set_sensitive(False)
        self.menu_save_dmf_device.set_sensitive(False)
        self.menu_save_dmf_device_as.set_sensitive(False)

    def init_pipeline(self):
        self.view.pipeline = self.view.get_pipeline()
        result = self.view.pipeline.set_state(gst.STATE_PLAYING)
        if result == gst.STATE_CHANGE_FAILURE and self.video_enabled:
            logger.warning(
                    'Error starting video.  Disabling video and restarting ' \
                            'the application.')
            self.set_app_values(dict(video_enabled=False))
            app = get_app()
            gtk.idle_add(app.main_window_controller.on_destroy, None)
        elif result == gst.STATE_CHANGE_ASYNC:
            while self.view.pipeline.get_state()[1] != gst.STATE_PLAYING:
                pass
        return False

    def request_frame(self):
        warp_bin = self.view.pipeline.get_by_name('warp_bin')
        warp_bin.grab_frame(self._on_new_frame)

    def on_menu_video__toggled(self, widget):
        app = get_app()
        enable = widget.get_active()
        result = yesno('To %s video, the application must be restarted.  '\
                '''Restart now?''' % ('enable' if enable else 'disable'))
        if result == gtk.RESPONSE_YES:
            self.set_app_values(dict(video_enabled=enable))
            app.main_window_controller.on_destroy(None)
        else:
            self.set_toggle_state(not enable)

    def set_toggle_state(self, value):
        if hasattr(self, 'menu_video'):
            self.menu_video.handler_block(self.video_toggled_handler)
            self.menu_video.set_active(value)
            self.menu_video.handler_unblock(self.video_toggled_handler)

    def grab_frame(self):
        return self.view.grab_frame()

    def on_protocol_run(self):
        app = get_app()
        log_dir = path(app.experiment_log.get_log_path())
        video_path = log_dir.joinpath('%s.avi' % log_dir.name)
        self.view.start_recording(video_path)

    def on_protocol_pause(self):
        self.view.stop_recording()

    def on_app_exit(self):
        app = get_app()
        self.save_check()
        if self.view.pipeline:
            result = self.view.pipeline.set_state(gst.STATE_NULL)
            if result == gst.STATE_CHANGE_ASYNC:
                while self.view.pipeline.get_state()[1] != gst.STATE_NULL:
                    pass

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
        try:
            device = DmfDevice.load(filename)
            if path(filename).parent.parent != app.get_device_directory():
                logger.info('[DmfDeviceController].load_device: '
                             'Import new device.')
                self.modified=True
            else:
                logger.info('[DmfDeviceController].load_device: '
                             'load existing device.')
                self.modified=False
            emit_signal("on_dmf_device_swapped", [app.dmf_device,
                                                  device])
        except Exception, e:
            logger.error('Error loading device. %s: %s.' % (type(e), e))
            logger.info(''.join(traceback.format_exc()))

    def save_check(self):
        app = get_app()
        if self.modified:
            result = yesno('Device %s has unsaved changes.  Save now?'\
                    % app.dmf_device.name)
            if result == gtk.RESPONSE_YES:
                self.save_dmf_device()

    def save_dmf_device(self, save_as=False, rename=False):
        app = get_app()

        name = app.dmf_device.name
        # if the device has no name, try to get one
        if save_as or rename or name is None:
            if name is None:
                name = ""
            name = text_entry_dialog('Device name', name, 'Save device')
            if name is None:
                name = ""

        if name:
            # current file name
            if app.dmf_device.name:
                src = os.path.join(app.get_device_directory(),
                                   app.dmf_device.name)
            dest = os.path.join(app.get_device_directory(), name)

            # if we're renaming, move the old directory
            if rename and os.path.isdir(src):
                if src == dest:
                    return
                if os.path.isdir(dest):
                    logger.error("A device with that "
                                 "name already exists.")
                    return
                shutil.move(src, dest)

            if os.path.isdir(dest) == False:
                os.mkdir(dest)

            # if the device name has changed
            if name != app.dmf_device.name:
                app.dmf_device.name = name

            # save the device
            app.dmf_device.save(os.path.join(dest,"device"))
            self.modified = False

    def on_step_options_changed(self, plugin_name, step_number):
        '''
        The step options for the current step have changed.
        If the change was to options affecting this plugin, update state.
        '''
        app = get_app()
        if app.protocol.current_step_number == step_number\
                and plugin_name == self.name:
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

    def _update(self):
        app = get_app()
        if not app.dmf_device:
            return
        options = self.get_step_options()
        state_of_channels = options.state_of_channels
        for id, electrode in app.dmf_device.electrodes.iteritems():
            channels = app.dmf_device.electrodes[id].channels
            if channels:
                # get the state(s) of the channel(s) connected to this electrode
                states = state_of_channels[channels]

                # if all of the states are the same
                if len(np.nonzero(states == states[0])[0]) == len(states):
                    if states[0] > 0:
                        self.view.electrode_color[id] = (1,1,1)
                    else:
                        color = app.dmf_device.electrodes[id].path.color
                        self.view.electrode_color[id] = [c / 255. for c in color]
                else:
                    #TODO: this could be used for resistive heating
                    logger.error("not supported yet")
            else:
                self.view.electrode_color[id] = (1,0,0)

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
            return [ScheduleRequest('microdrop.app', self.name),]
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
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            try:
                dmf_device = DmfDevice.load_svg(filename)
                self.modified = True
                emit_signal("on_dmf_device_swapped", [app.dmf_device,
                                                      dmf_device])
            except Exception, e:
                logger.error('Error importing device. %s: %s.' % (type(e), e))
                logger.info(''.join(traceback.format_exc()))
        dialog.destroy()

    def on_rename_dmf_device(self, widget, data=None):
        self.save_dmf_device(rename=True)

    def on_save_dmf_device(self, widget, data=None):
        self.save_dmf_device()

    def on_save_dmf_device_as(self, widget, data=None):
        self.save_dmf_device(save_as=True)

    def on_dmf_device_swapped(self, old_device, new_device):
        self.menu_rename_dmf_device.set_sensitive(True)
        self.menu_save_dmf_device_as.set_sensitive(True)
        self._update()

    def on_dmf_device_changed(self, dmf_device):
        self.modified = True

    def _on_new_frame(self, cv_img):
        emit_signal('on_new_frame', [cv_img])

PluginGlobals.pop_env()
