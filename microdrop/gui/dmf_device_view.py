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

from __future__ import division
from collections import namedtuple
from datetime import datetime

import gtk
import gobject
import cairo
import numpy as np
from pygst_utils.video_view.gtk_view import GtkVideoView
from pygst_utils.video_pipeline.window_service_proxy import WindowServiceProxy
from pygst_utils.elements.draw_queue import DrawQueue
from geo_util import CartesianSpace
from pygtkhelpers.utils import gsignal
from pygtkhelpers.delegates import SlaveView
from opencv_helpers.registration_dialog import RegistrationDialog, cv
from microdrop_utility.gui import text_entry_dialog
from microdrop_utility import is_float

from ..app_context import get_app
from ..logger import logger
from ..plugin_manager import emit_signal, IPlugin
from .. import base_path


Dims = namedtuple('Dims', 'x y width height')


class ElectrodeContextMenu(SlaveView):
    '''
    Slave view for context-menu for an electrode in the DMF device
    view.

    The signal 'registration-request' is triggered when registration is
    selected from the menu.
    '''

    builder_path = base_path().joinpath('gui', 'glade',
                                        'dmf_device_view_context_menu.glade')

    gsignal('registration-request')

    def disable_video_background(self):
        self.last_frame = None
        self.background = None

    def on_edit_electrode_channels__activate(self, widget, data=None):
        # TODO: set default value
        channel_list = ','.join([str(i) for i in self.last_electrode_clicked.channels])
        app = get_app()
        options = self.model.controller.get_step_options()
        state = options.state_of_channels
        channel_list = text_entry_dialog('Channels', channel_list, 'Edit electrode channels')
        if channel_list:
            channels = channel_list.split(',')
            try: # convert to integers
                if len(channels[0]):
                    for i in range(0,len(channels)):
                        channels[i] = int(channels[i])
                else:
                    channels = []
                if channels and max(channels) >= len(state):
                    # zero-pad channel states for all steps
                    for i in range(len(app.protocol)):
                        options = self.model.controller.get_step_options(i)
                        options.state_of_channels = \
                            np.concatenate([options.state_of_channels, \
                                np.zeros(max(channels) - \
                                len(options.state_of_channels)+1, int)])
                        # don't emit signal for current step, we will do that after
                        if i != app.protocol.current_step_number:
                            emit_signal('on_step_options_changed',
                                        [self.model.controller.name, i],
                                        interface=IPlugin)
                self.last_electrode_clicked.channels = channels
                emit_signal('on_step_options_changed',
                            [self.model.controller.name,
                             app.protocol.current_step_number],
                            interface=IPlugin)
                emit_signal('on_dmf_device_changed')
            except:
                logger.error("Invalid channel.")

    def on_edit_electrode_area__activate(self, widget, data=None):
        app = get_app()
        if app.dmf_device.scale is None:
            area = ""
        else:
            area = self.last_electrode_clicked.area() * app.dmf_device.scale
        area = text_entry_dialog("Area of electrode in mm<span "
                "rise=\"5000\" font_size=\"smaller\">2</span>:", str(area),
                        "Edit electrode area")
        if area:
            if is_float(area):
                app.dmf_device.scale = \
                    float(area)/self.last_electrode_clicked.area()
            else:
                logger.error("Area value is invalid.")
        emit_signal('on_dmf_device_changed')

    def on_register_device__activate(self, widget, data=None):
        self.emit('registration-request')

    def popup(self, state_of_channels, electrode, button, time,
            register_enabled=True):
        self.last_electrode_clicked = electrode
        self.state_of_channels = state_of_channels
        self.register_device.set_property('sensitive', register_enabled)
        self.menu_popup.popup(None, None, None, button, time, None)

    def add_item(self, menu_item):
        self.menu_popup.append(menu_item)
        menu_item.show()


first_dim = 0
second_dim = 1


class DmfDeviceView(GtkVideoView):
    '''
    Slave view for DMF device view.

    This view contains a canvas where video is overlayed with a
    graphical rendering of the device.  The video can optionally be
    registered to align it to the device rendering.  The signal
    'transform-changed' is emitted whenever a video registration has
    been completed.

    The signal 'channel-state-changed' is emitted whenever the state of
    a channel has changed as a result of interaction with the device
    view.
    '''
    builder_path = base_path().joinpath('gui', 'glade',
                                        'dmf_device_view.glade')

    gsignal('channel-state-changed', object)
    gsignal('transform-changed', object)

    def __init__(self, dmf_device_controller, name):
        self.controller = dmf_device_controller
        self.last_frame_time = datetime.now()
        self.last_frame = None
        self.video_offset = (0, 0)
        self.display_offset = (0, 0)
        self.electrode_color = {}
        self.background = None
        self.overlay_opacity = None
        self.pixmap = None
        self._proxy = None
        self._set_window_title = False

        self.svg_space = None
        self.view_space = None
        self.drawing_space = None

        self.popup = ElectrodeContextMenu(self)
        self.popup.connect('registration-request', self.on_register)
        self.force_aspect_ratio = False
        self.sink = None
        self.window_xid = None
        SlaveView.__init__(self)

    def create_ui(self, *args, **kwargs):
        self.widget = self.device_area

    def grab_frame(self):
        #return self.play_bin.grab_frame()
        return None

    def update_draw_queue(self):
        if self.window_xid and self._proxy:
            if self.controller.video_enabled:
                overlay_opacity = self.overlay_opacity / 100.
            else:
                overlay_opacity = 1.
            x, y, width, height = self.device_area.get_allocation()
            draw_queue = self.get_draw_queue(width, height, overlay_opacity)
            self._proxy.set_draw_queue(draw_queue)

    def get_draw_queue(self, width, height, alpha=1.0):
        app = get_app()
        if app.dmf_device:
            d = DrawQueue()
            x, y, device_width, device_height = app.dmf_device.get_bounding_box()
            self.svg_space = CartesianSpace(device_width, device_height,
                    offset=(x, y))
            padding = 20
            if width/device_width < height/device_height:
                drawing_width = width - 2 * padding
                drawing_height = drawing_width * (device_height / device_width)
                drawing_x = padding
                drawing_y = (height - drawing_height) / 2
            else:
                drawing_height = height - 2 * padding
                drawing_width = drawing_height * (device_width / device_height)
                drawing_x = (width - drawing_width) / 2
                drawing_y = padding
            self.drawing_space = CartesianSpace(drawing_width, drawing_height,
                offset=(drawing_x, drawing_y))
            scale = np.array(self.drawing_space.dims) / np.array(
                    self.svg_space.dims)
            d.translate(*self.drawing_space._offset)
            d.scale(*scale)
            d.translate(*(-np.array(self.svg_space._offset)))
            for id, electrode in app.dmf_device.electrodes.iteritems():
                if self.electrode_color.keys().count(id):
                    r, g, b = self.electrode_color[id]
                    self.draw_electrode(electrode, d, (b, g, r, alpha))
            return d

    def draw_electrode(self, electrode, cr, color=None):
        p = electrode.path
        cr.save()
        if color is None:
            color = [v / 255. for v in p.color]
        if len(color) < 4:
            color += [1.] * (len(color) - 4)
        cr.set_source_rgba(*color)
        for loop in p.loops:
            cr.move_to(*loop.verts[0])
            for v in loop.verts[1:]:
                cr.line_to(*v)
            cr.close_path()
            cr.fill()
        cr.restore()

    def _initialize_video(self, device, caps_str, bitrate=None,
                          record_path=None):
        # Connect to JSON-RPC server and request to run the pipeline
        self._proxy = WindowServiceProxy(59000)
        self._proxy.window_xid(self.window_xid)

        x, y, width, height = self.widget.get_allocation()
        draw_queue = self.get_draw_queue(width, height)
        self._proxy.create(device, caps_str, bitrate=bitrate,
                           record_path=record_path, draw_queue=draw_queue,
                           with_scale=True, with_warp=True)
        self._proxy.scale(width, height)
        self._proxy.start()
        self.update_draw_queue()

    def destroy_video_proxy(self):
        if self._proxy is not None:
            print '[destroy_video_proxy]'
            try:
                self._proxy.stop()
                print '  \->SUCCESS'
            except:
                print '  \->ERROR'
                import traceback
                traceback.print_exc()
            finally:
                self._proxy.close()
                self._proxy = None
                print '  --- CLOSED ---'

    def on_device_area__realize(self, widget, *args):
        self.on_realize(widget)

    def on_device_area__size_allocate(self, *args):
        '''
        Called when the device DrawingArea widget has been realized.

        Here, we need to reset the CartesianSpace instance representing
        the drawing area.
        '''
        x, y, width, height = self.device_area.get_allocation()
        self.view_space = CartesianSpace(width, height)

    def on_device_area__destroy(self, *args):
        self.destroy_video_proxy()

    def get_clicked_electrode(self, event):
        app = get_app()
        if self.svg_space and self.drawing_space:
            # Get the click coordinates, normalized to the bounding box of the
            # DMF device drawing (NOT the entire device drawing area)
            normalized_coords = self.drawing_space.normalized_coords(
                    *event.get_coords())
            # Conduct a point query in the SVG space to see which electrode (if
            # any) was clicked.  Note that the normalized coordinates are
            # translated to get the coordinates relative to the SVG space.
            shape = app.dmf_device.body_group.space.point_query_first(
                    self.svg_space.translate_normalized(*normalized_coords))
            if shape:
                return app.dmf_device.get_electrode_from_body(shape.body)
        return None

    def on_device_area__button_press_event(self, widget, event):
        '''
        Modifies state of channel based on mouse-click.
        '''
        self.widget.grab_focus()
        # Determine which electrode was clicked (if any)
        electrode = self.get_clicked_electrode(event)
        if electrode:
            self.on_electrode_click(electrode, event)
        return True

    def on_electrode_click(self, electrode, event):
        options = self.controller.get_step_options()
        state = options.state_of_channels
        if event.button == 1:
            if len(electrode.channels):
                for channel in electrode.channels:
                    if state[channel] > 0:
                        state[channel] = 0
                    else:
                        state[channel] = 1
                self.emit('channel-state-changed', electrode.channels[:])
            else:
                logger.error("No channel assigned to electrode.")
        elif event.button == 3:
            self.popup.popup(state, electrode, event.button, event.time,
                    register_enabled=self.controller.video_enabled)
        return True

    def on_register(self, *args, **kwargs):
        if self._proxy is not None:
            self._proxy.request_frame()
            def process_frame(self):
                #draw_queue = self.get_draw_queue(*self.view_space.dims)
                frame = self._proxy.get_frame()
                if frame is not None:
                    cv_im = cv.CreateMat(frame.shape[0], frame.shape[1], cv.CV_8UC3)
                    cv.SetData(cv_im, frame.tostring(), frame.shape[1] * frame.shape[2])
                    cv_scaled = cv.CreateMat(500, 600, cv.CV_8UC3)
                    cv.Resize(cv_im, cv_scaled)
                    self._on_register_frame_grabbed(cv_scaled)
                    return False
                return True
            gtk.timeout_add(10, process_frame, self)

    def _on_register_frame_grabbed(self, cv_img):
        x, y, width, height = self.device_area.get_allocation()
        # Create a cairo surface to draw device on
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context(surface)
        draw_queue = self.get_draw_queue(width, height)
        draw_queue.render(cr)

        size = (width, height)
        # Write cairo surface to cv image in RGBA format
        alpha_image = cv.CreateImageHeader(size, cv.IPL_DEPTH_8U, 4)
        cv.SetData(alpha_image, surface.get_data(), 4 * width)

        # Convert RGBA image (alpha_image) to RGB image (device_image)
        device_image = cv.CreateImage(size, cv.IPL_DEPTH_8U, 3)
        cv.CvtColor(alpha_image, device_image, cv.CV_RGBA2RGB)

        video_image = cv.CreateImage(size, cv.IPL_DEPTH_8U, 3)

        cv.Resize(cv_img, video_image)

        def do_device_registration():
            # Since this function may have been called from outside the main
            # thread, we need to surround GTK code with threads_enter/leave()
            dialog = DeviceRegistrationDialog(device_image, video_image)
            results = dialog.run()
            if results:
                array = np.fromstring(results.tostring(), dtype='float32',
                        count=results.width * results.height)
                # If the transform matrix is the default, set it to the
                # identity matrix.  This will simply reset the transform.
                if array.flatten()[-1] == 1 and array.sum() == 1:
                    array = np.identity(results.width, dtype=np.float32)
                array.shape = (results.width, results.height)
                self.emit('transform-changed', array)
            return False
        gtk.threads_enter()
        do_device_registration()
        gtk.threads_leave()

    def on_device_area__key_press_event(self, widget, data=None):
        pass


class DeviceRegistrationDialog(RegistrationDialog):
    '''
    This dialog is used to register the video to the DMF device
    rendering.
    '''

    def __init__(self, device_image, video_image, *args, **kwargs):
        super(DeviceRegistrationDialog, self).__init__(*args, **kwargs)
        self.device_image = device_image
        self.video_image = video_image

    def get_glade_path(self):
        assert(False)  # See TODO.
        # TODO: Add `base_path` function to `opencv_helpers` and use it's path,
        # since `opencv_helpers` does not belong to `microdrop` package
        # anymore, so the following line is broken!
        return base_path().joinpath('opencv_helpers', 'glade',
                                    'registration_demo.glade')

    def get_original_image(self):
        return self.device_image

    def get_rotated_image(self):
        return self.video_image
