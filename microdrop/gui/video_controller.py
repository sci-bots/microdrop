#!/usr/bin/env python
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

import numpy as np
import gtk
import gobject
from path import path

import microdrop
from opencv.safe_cv import cv
from opencv.frame_grabber import FrameGrabber
from opencv.camera_capture import CameraCapture
from plugin_manager import IPlugin, SingletonPlugin, implements, emit_signal, \
    IVideoPlugin


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


class VideoController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = 'microdrop.gui.video_controller'
        self.cam_cap = CameraCapture(auto_init=False)
        self.grabber = FrameGrabber(self.cam_cap, auto_init=True)
        self.grabber.frame_callback = self.update_frame_data
        self.grabber.start()
        self.video_enabled = False

    def on_app_init(self, *args, **kwargs):
        self.on_plugin_enable()

    def on_plugin_enable(self, *args, **kwargs):
        self.video_enabled = True

    def on_plugin_disable(self, *args, **kwargs):
        self.video_enabled = False

    def update_frame_data(self, frame):
        if self.video_enabled:
            # Process NumPy array frame data
            height, width, channels = frame.shape
            depth = {np.dtype('uint8'): 8}[frame.dtype]
            logging.debug('[update_frame_data] type(frame)=%s '\
                'height, width, channels, depth=(%s)'\
                % (type(frame), (height, width, channels, depth)))
            gtk_frame = array2cv(frame)
            cv.CvtColor(gtk_frame, gtk_frame, cv.CV_BGR2RGB)
            emit_signal('on_new_frame', [gtk_frame, depth],
                            interface=IVideoPlugin)
        return True

    def __del__(self, *args, **kwargs):
        results = self.grabber.stop()
        logging.debug(str(results))
        del self.cam_cap
