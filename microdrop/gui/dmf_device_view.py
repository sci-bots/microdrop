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

import gtk

from app_context import get_app
from opencv.safe_cv import cv


class DmfDeviceView:
    def __init__(self, widget):
        self.widget = widget
        x, y, width, height = self.widget.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.widget.window, width, height)
        #self.pixmap.draw_rectangle(self.widget.get_style().black_gc,
                                   #True, 0, 0, width, height)
        self.scale = 1
        self.offset = (0,0)
        self.electrode_color = {}
        self.background = None
        self.transform_matrix = None

    def fit_device(self, padding=None):
        app = get_app()
        if len(app.dmf_device.electrodes):
            if padding is None:
                padding = 10
            widget = self.widget.get_allocation()
            device = app.dmf_device.geometry()
            scale_x = (widget[2]-2*padding)/device[2]
            scale_y = (widget[3]-2*padding)/device[3]
            self.scale = min(scale_x, scale_y)
            if scale_x < scale_y: # center device vertically
                self.offset = (-device[0]+padding/self.scale,
                               -device[1]+padding/self.scale+ \
                               ((widget[3]-2*padding)/self.scale-device[3])/2)
            else:  # center device horizontally
                self.offset = (-device[0]+padding/self.scale+ \
                               ((widget[2]-2*padding)/self.scale-device[2])/2,
                               -device[1]+padding/self.scale)

    # device view events
    def on_expose(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().white_gc,
                                    self.pixmap, x, y, x, y, width, height)
        return False

    def update(self):
        x, y, width, height = self.widget.get_allocation()
        if self.background is not None:
            self.pixmap, mask = self.background.render_pixmap_and_mask()
            alpha = 0.3
        else:
            alpha = 1.
            self.pixmap.draw_rectangle(self.widget.get_style().black_gc,
                                   True, 0, 0, width, height)
        self.draw_on_pixmap(self.pixmap, alpha=alpha)

    def draw_on_pixmap(self, pixmap, alpha=1.0):
        app = get_app()
        cr = pixmap.cairo_create()
        self.draw_on_cairo(cr, alpha)
        self.widget.queue_draw()

    def draw_on_cairo(self, cr, alpha=1.0):
        app = get_app()
        x,y = self.offset
        cr.scale(self.scale, self.scale)
        cr.translate(x,y)
        for id, electrode in app.dmf_device.electrodes.iteritems():
            if self.electrode_color.keys().count(id):
                self.draw_electrode(electrode, cr)
                r, g, b = self.electrode_color[id]
                cr.set_source_rgba(r, g, b, alpha)
                cr.fill()

    def draw_electrode(self, electrode, cr):
        cairo_commands = ""

        # TODO: make this work for relative paths (small letter commands)
        for step in electrode.path:
            if step['command'] == "M":
                cairo_commands += "cr.move_to(%s,%s);" % (step['x'],step['y'])
            #TODO: curves
            """
            if step['command'] == "C":
                 
                cairo_commands += "cr.curve_to(%s,%s,%s,%s,%s,%s);" % (c[0],c[1],c[2],c[3],c[4],c[5])
                pass
            """
            if step['command'] == "L":
                cairo_commands += "cr.line_to(%s,%s);" % (step['x'],step['y'])
            if step['command'] == "Z":
                cairo_commands += "cr.close_path();"
        exec(cairo_commands)


from opencv.registration_dialog import RegistrationDialog


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
