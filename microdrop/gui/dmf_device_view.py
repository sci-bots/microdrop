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

import gtk

from pygtkhelpers.utils import gsignal
from pygtkhelpers.delegates import SlaveView
from app_context import get_app
from opencv.safe_cv import cv
from opencv.registration_dialog import RegistrationDialog
from utility.gui import text_entry_dialog
from logger import logger
import app_state


Dims = namedtuple('Dims', 'x y width height')

class ElectrodeContextMenu(SlaveView):
    builder_file = 'right_click_popup.glade'

    def __init__(self, controller):
        self.controller = controller
        super(ElectrodeContextMenu, self).__init__()

    def on_edit_electrode_channels__activate(self, widget, data=None):
        # TODO: set default value
        channel_list = ','.join([str(i) for i in self.last_electrode_clicked.channels])
        app = get_app()
        channel_list = text_entry_dialog('Channels', channel_list, 'Edit electrode channels')
        if channel_list:
            channels = channel_list.split(',')
            #try: # convert to integers
            if len(channels[0]):
                for i in range(0,len(channels)):
                    channels[i] = int(channels[i])
            else:
                channels = []
            if channels and max(channels) >= len(self.state_of_channels):
                # zero-pad channel states for all steps
                for i in range(len(app.protocol)):
                    self.state_of_channels[:] = \
                        np.concatenate([self.state_of_channels,
                        np.zeros(max(channels) - \
                        len(self.state_of_channels)+1, int)])
            self.last_electrode_clicked.channels = channels
            app.state.trigger_event(app_state.DEVICE_CHANGED)
            #except:
                #logger.error("Invalid channel.")
        
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

    def on_register_device__activate(self, widget, data=None):
        self.controller.on_register()

    def popup(self, electrode, button, time):
        self.last_electrode_clicked = electrode
        options = self.controller.get_step_options()
        self.state_of_channels = options.state_of_channels
        self.menu_popup.popup(None, None, None, button, time, None)

    def add_item(self, menu_item):
        self.menu_popup.append(menu_item)
        menu_item.show()


class DmfDeviceView(SlaveView):
    builder_file = 'dmf_device_view.glade'

    gsignal('channel-state-changed', object)

    def __init__(self, dmf_device_controller):
        self.controller = dmf_device_controller
        super(DmfDeviceView, self).__init__()
        self.scale = 1
        self.offset = (0,0)
        self.electrode_color = {}
        self.background = None
        self.transform_matrix = None
        self.overlay_opacity = None
        self.pixmap = None
        self.popup = ElectrodeContextMenu(self.controller)

    def on_device_area__size_allocate(self, *args):
        x, y, width, height = self.device_area.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.device_area.window, width, height)
        print '[DmfDeviceView] on_device_area__realize: %s (%s, %s, %sx%s)'\
            % (args, x, y, width, height)

    #def set_widget(self, widget):
        #self.widget = widget
        #x, y, width, height = self.widget.get_allocation()
        #self.pixmap = gtk.gdk.Pixmap(self.widget.window, width, height)

    def fit_device(self, padding=None):
        app = get_app()
        if app.dmf_device and len(app.dmf_device.electrodes):
            if padding is None:
                padding = 10

            widget = Dims(*self.device_area.get_allocation())
            device = Dims(*app.dmf_device.get_bounding_box())
            scale_x = (widget.width - 2 * padding) / device.width
            scale_y = (widget.height - 2 * padding) / device.height
            self.scale = min(scale_x, scale_y)
            if scale_x < scale_y: # center device vertically
                self.offset = (-device.x + padding / self.scale,
                               -device.y + padding / self.scale + \
                               ((widget.height - 2 * padding)\
                                        / self.scale - device.height) / 2)
            else:  # center device horizontally
                self.offset = (-device.x + padding / self.scale +  \
                               ((widget.width - 2 * padding)\
                                    / self.scale - device.width) / 2,
                                - device.y + padding / self.scale)

    def update(self):
        if self.pixmap:
            x, y, width, height = self.device_area.get_allocation()
            if self.background is not None:
                self.pixmap, mask = self.background.render_pixmap_and_mask()
                if self.overlay_opacity:
                    alpha = self.overlay_opacity / 100
                else:
                    alpha = 1.
            else:
                alpha = 1.
                self.pixmap.draw_rectangle(self.device_area.get_style().black_gc,
                                        True, 0, 0, width, height)
            self.draw_on_pixmap(self.pixmap, alpha=alpha)

    def draw_on_pixmap(self, pixmap, alpha=1.0):
        app = get_app()
        cr = pixmap.cairo_create()
        self.draw_on_cairo(cr, alpha)
        self.device_area.queue_draw()

    def draw_on_cairo(self, cr, alpha=1.0):
        app = get_app()
        x,y = self.offset
        cr.scale(self.scale, self.scale)
        cr.translate(x,y)
        for id, electrode in app.dmf_device.electrodes.iteritems():
            if self.electrode_color.keys().count(id):
                r, g, b = self.electrode_color[id]
                self.draw_electrode(electrode, cr, (r, g, b, alpha))

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

    def translate_coords(self, x, y):
        return (x / self.scale - self.offset[0], y / self.scale - self.offset[1])

    def get_clicked_electrode(self, event):
        app = get_app()
        shape = app.dmf_device.body_group.space.point_query_first(
                self.translate_coords(*event.get_coords()))
        if shape:
            return app.dmf_device.get_electrode_from_body(shape.body)
        return None

    def on_electrode_click(self, electrode, event):
        app = get_app()
        options = self.controller.get_step_options()
        if event.button == 1:
            state = options.state_of_channels
            if len(electrode.channels): 
                for channel in electrode.channels:
                    if state[channel] > 0:
                        state[channel] = 0
                    else:
                        state[channel] = 1
                self.emit('channel-state-changed', electrode.channels[:])
            else:
                logger.error("no channel assigned to electrode.")
        elif event.button == 3:
            self.popup.popup(electrode, event.button, event.time)
        return True

    def on_device_area__key_press_event(self, widget, data=None):
        pass
    
    def on_device_area__button_press_event(self, widget, event):
        '''
        Modifies state of channel based on mouse-click.
        '''
        app = get_app()
        self.widget.grab_focus()
        # Determine which electrode was clicked (if any)
        electrode = self.get_clicked_electrode(event)
        if electrode:
            self.on_electrode_click(electrode, event)
        return True

    # device view events

    def on_device_area__expose_event(self, widget, event):
        if self.pixmap:
            x , y, width, height = event.area
            widget.window.draw_drawable(widget.get_style().white_gc,
                                        self.pixmap, x, y, x, y, width, height)
        return False

class DeviceRegistrationDialog(RegistrationDialog):
    def __init__(self, device_image, video_image, *args, **kwargs):
        super(DeviceRegistrationDialog, self).__init__(*args, **kwargs)
        self.device_image = device_image
        self.video_image = video_image

    def get_glade_path(self):
        from utility import base_path
        return base_path().joinpath('opencv', 'glade', 'registration_demo.glade')

    def get_original_image(self):
        return self.device_image

    def get_rotated_image(self):
        return self.video_image
