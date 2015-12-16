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
from pygst_utils.elements.draw_queue import DrawQueue
from geo_util import CartesianSpace
from pygtkhelpers.utils import gsignal
from .cairo_view import GtkCairoView
from pygtkhelpers.delegates import SlaveView
from microdrop_utility.gui import text_entry_dialog
from microdrop_utility import is_float

from ..app_context import get_app
import logging

logger = logging.getLogger(__name__)
from ..plugin_manager import emit_signal, IPlugin
from .. import base_path


Dims = namedtuple('Dims', 'x y width height')


class ElectrodeContextMenu(SlaveView):
    '''
    Slave view for context-menu for an electrode in the DMF device
    view.
    '''

    builder_path = base_path().joinpath('gui', 'glade',
                                        'dmf_device_view_context_menu.glade')

    def on_edit_electrode_channels__activate(self, widget, data=None):
        # TODO: set default value
        channel_list = ','.join([str(i) for i in
                                 self.last_electrode_clicked.channels])
        app = get_app()
        options = self.model.controller.get_step_options()
        state = options.state_of_channels
        channel_list = text_entry_dialog('Channels', channel_list,
                                         'Edit electrode channels')
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
                        # Don't emit signal for current step, we will do that
                        # after.
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
        area = text_entry_dialog('Area of electrode in mm<span rise="5000"'
                                 'font_size="smaller">2</span>:', str(area),
                                 'Edit electrode area')
        if area:
            if is_float(area):
                app.dmf_device.scale = \
                    float(area)/self.last_electrode_clicked.area()
            else:
                logger.error("Area value is invalid.")
        emit_signal('on_dmf_device_changed')

    def on_ipython_shell__activate(self, widget, data=None):
        import IPython; IPython.embed()

    def popup(self, state_of_channels, electrode, button, time):
        self.last_electrode_clicked = electrode
        self.state_of_channels = state_of_channels
        self.menu_popup.popup(None, None, None, button, time, None)

    def add_item(self, menu_item):
        self.menu_popup.append(menu_item)
        menu_item.show()


first_dim = 0
second_dim = 1


class DmfDeviceView(GtkCairoView):
    '''
    Slave view for DMF device view.

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
        self.display_offset = (0, 0)
        self.electrode_color = {}
        self.background = None
        self.pixmap = None
        self._set_window_title = False

        self.svg_space = None
        self.view_space = None
        self.drawing_space = None

        self.popup = ElectrodeContextMenu(self)
        super(DmfDeviceView, self).__init__()

    def on_device_area__configure_event(self, widget, event):
        gtk.idle_add(self.update_draw_queue, (event.width, event.height))

    def reset_cairo_surface(self, width, height):
        self.cairo_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width,
                                                height)

    def create_ui(self, *args, **kwargs):
        self.widget = self.device_area

    def render(self, shape=None):
        '''
        Render device electrodes onto in-memory Cairo surface.

        Args:

            shape (tuple) : Width and height to use for surface.  If `None`,
                use size allocated for `device_area` widget.
        '''
        if shape is None:
            x, y, width, height = self.device_area.get_allocation()
            shape = width, height
        draw_queue = self.get_draw_queue(width, height)
        self.reset_cairo_surface(width, height)
        cairo_context = cairo.Context(self.cairo_surface)

        # Clear background.
        cairo_context.rectangle(0, 0, *shape)
        cairo_context.set_source_rgb(0, 0, 0)
        cairo_context.fill()

        # Paint electrodes from pre-rendered Cairo surface.
        draw_queue.render(cairo_context)

    def draw(self):
        '''
        Paint pre-rendered device electrodes to UI drawing area.
        '''
        cairo_context = self.device_area.window.cairo_create()

        # Paint device from pre-rendered Cairo surface.
        cairo_context.set_source_surface(self.cairo_surface, 0, 0)
        cairo_context.paint()

    def update_draw_queue(self, shape=None):
        '''
        Render device electrodes *and* draw rendered electrodes to UI window.
        '''
        self.render(shape=shape)
        self.draw()

    def get_draw_queue(self, width, height, alpha=1.0):
        '''
        Get a recorded sequence of Cairo commands for drawing the device
        electrodes, which can later be rendered to a Cairo context.

        Args:

            width (int) : Width to scale device to while maintaining aspect
                ratio.
            height (int) : Height to scale device to while maintaining aspect
                ratio.
            alpha (float) : Alpha multiplier, in range $[0, 1]$ (inclusive).

        Returns:

            (pygst_utils.elements.draw_queue.DrawQueue) : Device Cairo draw
                queue; the `render(context)` method can be used to render to a
                Cairo context.
        '''
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
            scale = (np.array(self.drawing_space.dims) /
                     np.array(self.svg_space.dims))

            self.draw_transform_queue = DrawQueue()
            self.draw_transform_queue.translate(*self.drawing_space._offset)
            self.draw_transform_queue.scale(*scale)
            self.draw_transform_queue.translate(*(-np.array(self.svg_space
                                                            ._offset)))
            d.save()
            d.render_callables += self.draw_transform_queue.render_callables

            # Draw electrodes.
            for id, electrode in app.dmf_device.electrodes.iteritems():
                if self.electrode_color.keys().count(id):
                    r, g, b = self.electrode_color[id]
                    self.draw_electrode(electrode, d, (r, g, b, alpha))
            d.restore()
            return d

    def draw_electrode(self, electrode, cairo_context, color=None):
        p = electrode.path
        cairo_context.save()
        if color is None:
            color = [v / 255. for v in p.color]
        if len(color) < 4:
            color += [1.] * (len(color) - 4)
        cairo_context.set_source_rgba(*color)
        for loop in p.loops:
            cairo_context.move_to(*loop.verts[0])
            for v in loop.verts[1:]:
                cairo_context.line_to(*v)
            cairo_context.close_path()
            cairo_context.fill()
        cairo_context.restore()

    def on_device_area__expose_event(self, widget, *args):
        # Clear background to black.
        x, y, width, height = self.device_area.get_allocation()
        print '[expose]', x, y, width, height
        cairo_context = self.device_area.window.cairo_create()
        cairo_context.save()
        cairo_context.rectangle(x, y, width, height)
        cairo_context.set_source_rgb(0, 0, 0)
        cairo_context.fill()
        cairo_context.restore()

    def on_device_area__realize(self, widget, *args):
        pass

    def on_device_area__size_allocate(self, *args):
        '''
        Called when the device DrawingArea widget has been realized.

        Here, we need to reset the CartesianSpace instance representing
        the drawing area.
        '''
        x, y, width, height = self.device_area.get_allocation()
        self.view_space = CartesianSpace(width, height)
        print '[size_allocate]', x, y, width, height
        cairo_context = self.device_area.window.cairo_create()
        cairo_context.save()
        cairo_context.rectangle(x, y, width, height)
        cairo_context.set_source_rgb(0, 0, 0)
        cairo_context.fill()
        cairo_context.restore()
        self.device_area.queue_draw()

    def get_clicked_electrode(self, event):
        app = get_app()
        if self.svg_space and self.drawing_space:
            # Get the click coordinates, normalized to the bounding box of the
            # DMF device drawing (NOT the entire device drawing area)
            normalized_coords = (self.drawing_space
                                 .normalized_coords(*event.get_coords()))
            # Conduct a point query in the SVG space to see which electrode (if
            # any) was clicked.  Note that the normalized coordinates are
            # translated to get the coordinates relative to the SVG space.
            svg_coords = (self.svg_space
                          .translate_normalized(*normalized_coords))
            shape = (app.dmf_device.body_group.space
                     .point_query_first(svg_coords))
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
            self.popup.popup(state, electrode, event.button, event.time)
        return True

    def on_device_area__key_press_event(self, widget, data=None):
        pass
