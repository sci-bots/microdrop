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
import time

import gtk
import numpy as np
from xml.etree import ElementTree as et
from pyparsing import Literal, Combine, Optional, Word, Group, OneOrMore, nums
from flatland import Form, Integer, String
from flatland.validation import ValueAtLeast, ValueAtMost
from utility.gui import yesno
from path import path
import yaml
import gst

from dmf_device_view import DmfDeviceView, DeviceRegistrationDialog
from dmf_device import DmfDevice
from protocol import Protocol
from experiment_log import ExperimentLog
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin,\
        implements, PluginGlobals, IVideoPlugin, ScheduleRequest, emit_signal,\
        IAppStatePlugin
from app_context import get_app
from logger import logger
from opencv.safe_cv import cv
from plugin_helpers import AppDataController
from utility.pygtkhelpers_widgets import Directory
from utility import is_float, copytree
from utility.gui import text_entry_dialog
import app_state


PluginGlobals.push_env('microdrop')

class DmfDeviceOptions(object):
    def __init__(self, state_of_channels=None):
        app = get_app()
        if state_of_channels is None:
            self.state_of_channels = np.zeros(app.dmf_device.max_channel()+1)
        else:
            self.state_of_channels = deepcopy(state_of_channels)


class DmfDeviceController(SingletonPlugin, AppDataController):
    implements(IPlugin)
    implements(IAppStatePlugin)
    implements(IVideoPlugin)
    
    AppFields = Form.of(
        Integer.named('overlay_opacity').using(default=30, optional=True,
            validators=[ValueAtLeast(minimum=1), ValueAtMost(maximum=100)]),
        Integer.named('display_fps').using(default=30, optional=True,
            validators=[ValueAtLeast(minimum=5), ValueAtMost(maximum=100)]),
        Directory.named('device_directory').using(default='', optional=True),
        String.named('transform_matrix').using(default='', optional=True,
            properties=dict(show_in_gui=False))
    )

    def __init__(self):
        self.name = "microdrop.gui.dmf_device_controller"        
        self.view = DmfDeviceView(self, 'device_view')
        self.view.connect('transform-changed', self.on_transform_changed)
        self.previous_device_dir = None
        
    def on_transform_changed(self, device_view, array):
        self.set_app_values(
            dict(transform_matrix=yaml.dump(array.tolist())))

    def on_app_options_changed(self, plugin_name):
        app = get_app()
        if plugin_name == self.name:
            values = self.get_app_values()
            if 'overlay_opacity' in values:
                self.view.overlay_opacity = int(values.get('overlay_opacity'))
            if 'display_fps' in values:
                self.view.display_fps_inv = 1. / int(values['display_fps'])
            if 'device_directory' in values:
                self.apply_device_dir(values['device_directory'])
            if 'transform_matrix' in values:
                matrix = yaml.load(values['transform_matrix'])
                if matrix:
                    matrix = np.array(matrix, dtype='float32')
                    self.view.transform_matrix = matrix

        elif plugin_name == 'microdrop.gui.video_controller':
            observers = ExtensionPoint(IPlugin)
            service = observers.service(plugin_name)
            values = service.get_app_values()
            video_enabled = values.get('video_enabled')
            if not video_enabled:
                self.disable_video_background()

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
                lambda x, y: self._notify_observers_step_options_swapped())

        self.menu_load_dmf_device = app.builder.get_object('menu_load_dmf_device')
        self.menu_import_dmf_device = app.builder.get_object('menu_import_dmf_device')
        self.menu_rename_dmf_device = app.builder.get_object('menu_rename_dmf_device')
        self.menu_save_dmf_device = app.builder.get_object('menu_save_dmf_device')
        self.menu_save_dmf_device_as = app.builder.get_object('menu_save_dmf_device_as')

        #app.signals["on_dmf_device_view_button_press_event"] = self.on_button_press
        #app.signals["on_dmf_device_view_key_press_event"] = self.on_key_press
        #app.signals["on_dmf_device_view_expose_event"] = self.view.on_expose
        #app.signals["on_menu_edit_electrode_channels_activate"] = self.on_edit_electrode_channels
        #app.signals["on_menu_edit_electrode_area_activate"] = self.on_edit_electrode_area
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
        self.view.pipeline.set_state(gst.STATE_PLAYING)

    def on_protocol_swapped(self, *args):
        self.set_overlay()

    def on_protocol_created(self, *args):
        self.set_overlay()

    def set_overlay(self):
        app = get_app()
        step_number = app.protocol.current_step_number + 1
        total_steps = len(app.protocol)
        self.view.play_bin.text_overlay.set_property('text',
                'Step: %s/%s' % (step_number, total_steps))

    def on_protocol_run(self):
        app = get_app()
        log_dir = path(app.experiment_log.get_log_path())
        video_path = log_dir.joinpath('%s.avi' % log_dir.name)

        self.view.pipeline.set_state(gst.STATE_READY)
        #self.view.record_bin.set_state(gst.STATE_NULL)
        self.view.record_bin.set_filepath(video_path)
        self.view.pipeline.add(self.view.record_bin)
        self.view.play_bin.link(self.view.record_bin)
        self.view.pipeline.set_state(gst.STATE_PLAYING)
        while self.view.pipeline.get_state()[1] != gst.STATE_PLAYING:
            time.sleep(0.001)
        logger.info('[VideoRecorderPlugin] recording to: %s' % video_path)

    def on_protocol_pause(self):
        self.view.pipeline.set_state(gst.STATE_READY)
        self.view.play_bin.unlink(self.view.record_bin)
        self.view.pipeline.remove(self.view.record_bin)
        self.view.pipeline.set_state(gst.STATE_PLAYING)
        while self.view.pipeline.get_state()[1] != gst.STATE_PLAYING:
            time.sleep(0.1)

    def on_post_event(self, state, event):
        if type(state) in [app_state.DirtyDeviceDirtyProtocol,
                app_state.DirtyDeviceProtocol, app_state.DirtyDeviceNoProtocol]:
            self.menu_save_dmf_device.set_property('sensitive', True)
        else:
            self.menu_save_dmf_device.set_property('sensitive', False)

    def on_app_exit(self):
        app = get_app()
        state = app.state.current_state
        if type(state) in [app_state.DirtyDeviceDirtyProtocol,
                app_state.DirtyDeviceProtocol, app_state.DirtyDeviceNoProtocol]:
            result = yesno('Device %s has unsaved changes.  Save now?' % app.dmf_device.name)
            if result == gtk.RESPONSE_YES:
                self.save_dmf_device()
        
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
            original_device = get_app().dmf_device
            if original_device is None:
                app.state.trigger_event(app_state.LOAD_DEVICE)
                emit_signal("on_dmf_device_created", DmfDevice.load(filename))
            else:
                app.state.trigger_event(app_state.LOAD_DEVICE)
                emit_signal("on_dmf_device_swapped", [original_device,
                        DmfDevice.load(filename)])
        except Exception, e:
            logger.error('Error loading device. %s: %s.' % (type(e), e))
            logger.debug(''.join(traceback.format_stack()))
    
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
                emit_signal("on_dmf_device_created", app.dmf_device)
            
            # save the device
            app.dmf_device.save(os.path.join(dest,"device"))
            app.state.trigger_event(app_state.DEVICE_SAVED)
                    
    def on_step_options_swapped(self, plugin_name, step_number):
        self.on_step_options_changed(plugin_name, step_number)

    def on_step_options_changed(self, plugin_name, step_number):
        '''
        The step options for the current step have changed.
        If the change was to options affecting this plugin, update state.
        '''
        app = get_app()
        if app.protocol.current_step_number == step_number\
                and plugin_name == self.name:
            self._update()

    def on_step_created(self, step_number):
        self.set_overlay()

    def on_step_swapped(self, original_step_number, step_number):
        self.set_overlay()

    def on_step_run(self):
        self._update()

    def _notify_observers_step_options_swapped(self):
        app = get_app()
        if not app.dmf_device:
            return
        emit_signal('on_step_options_swapped',
                    [self.name, app.protocol.current_step_number],
                    interface=IPlugin)

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
        self.view.update()

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
        elif function_name in ['on_dmf_device_swapped', 'on_dmf_device_created']:
            return [ScheduleRequest('microdrop.app', self.name),]
        return []

    # GUI callbacks

    def on_load_dmf_device(self, widget, data=None):
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
        self._notify_observers_step_options_swapped()
    
    def on_import_dmf_device(self, widget, data=None):
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
            app.dmf_device = DmfDevice.load_svg(filename)
            app.state.trigger_event(app_state.IMPORT_DEVICE)
            emit_signal("on_dmf_device_created", [app.dmf_device])
        dialog.destroy()
        self._notify_observers_step_options_swapped()
        
    def on_rename_dmf_device(self, widget, data=None):
        self.save_dmf_device(rename=True)
        
    def on_save_dmf_device(self, widget, data=None):
        self.save_dmf_device()

    def on_save_dmf_device_as(self, widget, data=None):
        self.save_dmf_device(save_as=True)

    def on_dmf_device_created(self, dmf_device):
        self.on_dmf_device_swapped(None, dmf_device)

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        self._notify_observers_step_options_changed()

    def on_new_frame(self, frame, depth, frame_time):
        self.view.on_new_frame(frame, depth, frame_time)

PluginGlobals.pop_env()
