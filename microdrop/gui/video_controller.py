"""
Copyright 2012 Ryan Fobel and Christian Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""
from time import sleep
from contextlib import closing
from StringIO import StringIO
import signal
import os
import logging
from multiprocessing import Process, Value

import numpy as np
import gtk
import gobject
from path import path
from flatland import Form, Dict, String, Integer, Boolean, Float
from flatland.validation import ValueAtLeast, ValueAtMost

import microdrop
from opencv.safe_cv import cv
from opencv.frame_grabber import FrameGrabber
from opencv.camera_capture import CameraCapture, CaptureError
from plugin_manager import IPlugin, SingletonPlugin, implements, \
    IVideoPlugin, PluginGlobals, ScheduleRequest, emit_signal
from app_context import get_app
from opencv.pixbuf import array2cv
from plugin_helpers import AppDataController


PluginGlobals.push_env('microdrop')


def array2cv(a):
    dtype2depth = {
            'uint8':   cv.IPL_DEPTH_8U,
            'int8':    cv.IPL_DEPTH_8S,
            'uint16':  cv.IPL_DEPTH_16U,
            'int16':   cv.IPL_DEPTH_16S,
            'int32':   cv.IPL_DEPTH_32S,
            'float32': cv.IPL_DEPTH_32F,
            'float64': cv.IPL_DEPTH_64F,
        }
    try:
        nChannels = a.shape[2]
    except:
        nChannels = 1
    cv_im = cv.CreateMat(a.shape[0], a.shape[1], cv.CV_8UC3)
    cv.SetData(cv_im, a.tostring(), a.shape[1] * nChannels)
    return cv_im


class VideoController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    AppFields = Form.of(
        Boolean.named('video_enabled').using(default=False, optional=True),
        Integer.named('fps_limit').using(default=30, optional=True,
            validators=[ValueAtLeast(minimum=1), ValueAtMost(maximum=100)]),
        Integer.named('camera_id').using(default=-1, optional=True,
            validators=[ValueAtLeast(minimum=-1), ValueAtMost(maximum=100)]),
    )

    def __init__(self):
        self.name = 'microdrop.gui.video_controller'
        self.grabber = None
        self.video_enabled = False
        self.cam_cap = None

    def on_app_options_changed(self, plugin_name):
        app = get_app()
        if plugin_name == self.name:
            app_data = app.get_data(self.name)
            if 'fps_limit' in app_data and self.grabber:
                self.grabber.set_fps_limit(app_data['fps_limit'])
            if 'video_enabled' in app_data:
                self.video_enabled = app_data['video_enabled']
            if 'camera_id' in app_data:
                if self.cam_cap is None or self.cam_cap\
                                and self.cam_cap.id != app_data['camera_id']:
                    self.reset_capture()

    def on_plugin_enable(self, *args, **kwargs):
        AppDataController.on_plugin_enable(self, *args, **kwargs)
        self.reset_capture()

    def _verify_camera(self, camera_id, verified):
        try:
            test_cap = CameraCapture(id=camera_id, auto_init=True)
            del test_cap
            verified.value = True
        except CaptureError, why:
            logging.debug('[verify_camera] error %s', why)

    def reset_capture(self):
        app = get_app()
        app_data = app.get_data(self.name)
        if self.grabber:
            self.grabber.stop()
            del self.grabber
            del self.cam_cap
            self.grabber = None
            self.cam_cap = None
        if app_data['video_enabled']:
            try:
                verified = Value('i', False)
                p = Process(target=self._verify_camera,
                        args=(app_data['camera_id'], verified))
                p.start()
                p.join(timeout=10)
                if p.is_alive() or not verified.value:
                    # Seems like camera test initialization has hung
                    p.terminate()
                    raise CaptureError, 'Could not connect to camera %s'\
                            % app_data['camera_id']
                self.cam_cap = CameraCapture(id=app_data['camera_id'], auto_init=False)
                self.grabber = FrameGrabber(self.cam_cap, auto_init=True)
                self.grabber.set_fps_limit(app_data['fps_limit'])
                self.grabber.frame_callback = self.update_frame_data
                self.grabber.start()
            except (CaptureError,), why:
                logging.warning(str(why))
                if app_data['video_enabled']:
                    self.set_app_values({'video_enabled': False})
                    emit_signal('on_app_options_changed', [self.name],
                            interface=IPlugin)

    def on_plugin_disable(self, *args, **kwargs):
        pass

    def update_frame_data(self, frame, frame_time):
        if self.video_enabled:
            # Process NumPy array frame data
            height, width, channels = frame.shape
            depth = {np.dtype('uint8'): 8}[frame.dtype]
            logging.debug('[update_frame_data] type(frame)=%s '\
                'height, width, channels, depth=(%s)'\
                % (type(frame), (height, width, channels, depth)))
            gtk_frame = array2cv(frame)
            cv.CvtColor(gtk_frame, gtk_frame, cv.CV_BGR2RGB)
            emit_signal('on_new_frame', [gtk_frame, depth, frame_time],
                        interface=IVideoPlugin)
        return True

    def __del__(self, *args, **kwargs):
        if self.grabber:
            results = self.grabber.stop()
            logging.debug(str(results))
            del self.cam_cap

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.config_controller',
                                    self.name)]
        return []
    
PluginGlobals.pop_env()
