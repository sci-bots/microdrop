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
import itertools
from collections import namedtuple
from datetime import datetime
import logging
import re

import gtk
import cairo
import numpy as np
import pandas as pd
from pygst_utils.elements.draw_queue import DrawQueue
from geo_util import CartesianSpace
from pygtkhelpers.utils import gsignal
from pygtkhelpers.delegates import SlaveView
from microdrop_utility.gui import text_entry_dialog
from microdrop_utility import is_float
from svg_model.shapes_canvas import ShapesCanvas

from ..app_context import get_app
from ..plugin_manager import emit_signal, IPlugin
from .. import base_path
from .cairo_view import GtkCairoView


logger = logging.getLogger(__name__)

Dims = namedtuple('Dims', 'x y width height')


class ElectrodeContextMenu(SlaveView):
    '''
    Slave view for context-menu for an electrode in the DMF device
    view.
    '''

    builder_path = base_path().joinpath('gui', 'glade',
                                        'dmf_device_view_context_menu.glade')

    gsignal('clear-drop-routes-request', object)
    gsignal('clear-all-drop-routes-request')

    def on_edit_electrode_channels__activate(self, widget, data=None):
        app = get_app()

        # Get `pd.Series`, indexed by `electrode_id`, where each entry
        # corresponds to a `channel`.
        channel_list = (app.dmf_device.df_electrode_channels
                        .loc[app.dmf_device.df_electrode_channels
                             .electrode_id == self.last_electrode_clicked]
                        .set_index('electrode_id').channel)

        channels_str = text_entry_dialog('Channels',
                                         ','.join(map(str, channel_list)),
                                         'Edit electrode channels')
        if channels_str is None:
            return

        if not channels_str:
            new_channel_list = []
        else:
            try:
                # Get proposed list of channels from text box.
                new_channel_list = map(int, re.split(r'\s*,\s*', channels_str))
            except:
                logger.error("Invalid channel.", exc_info=True)

        # Get current maximum channel index.
        max_channel = app.dmf_device.max_channel()

        if not np.array_equal(channel_list, new_channel_list):
            # Update channels for electrode `self.last_clicked_electrode` to
            # `new_channel_list`.
            # This includes updating `df_electrode_channels` and increasing
            # length of `state_of_channels` if number of total channels (i.e.,
            # max channel index) has changed.
            app.dmf_device\
                .update_electrode_channels(self.last_electrode_clicked,
                                           new_channel_list)
            new_max_channel = app.dmf_device.max_channel()
            if new_max_channel > max_channel:
                # Maximum channel index has changed, increase channel states
                # array length for all steps.
                for i in xrange(len(app.protocol)):
                    options = self.model.controller.get_step_options(i)
                    options.state_of_channels = \
                        np.concatenate([options.state_of_channels,
                                        np.zeros(new_max_channel -
                                                 len(options.state_of_channels)
                                                 + 1, dtype=int)])
                    # Don't emit signal for current step, we will do that
                    # after.
                    if i != app.protocol.current_step_number:
                        emit_signal('on_step_options_changed',
                                    [self.model.controller.name, i],
                                    interface=IPlugin)
                emit_signal('on_step_options_changed',
                            [self.model.controller.name,
                             app.protocol.current_step_number],
                            interface=IPlugin)
            emit_signal('on_dmf_device_changed')

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

    def on_clear_drop_routes__activate(self, widget, data=None):
        self.emit('clear-drop-routes-request', self.last_electrode_clicked)

    def on_clear_all_drop_routes__activate(self, widget, data=None):
        self.emit('clear-all-drop-routes-request')

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
        self.cairo_surface = None
        self._source_electrode_id = None
        self._target_electrode_id = None

        self.svg_space = None
        self.view_space = None
        self.drawing_space = None

        self.popup = ElectrodeContextMenu(self)
        self.popup.connect('clear-drop-routes-request',
                           self.on_clear_drop_routes)
        self.popup.connect('clear-all-drop-routes-request',
                           self.on_clear_all_drop_routes)
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
        draw_queue = self.get_draw_queue(*shape)
        self.reset_cairo_surface(*shape)
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
        d = DrawQueue()
        if app.dmf_device:
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
            d.save()
            d.render_callables += self.draw_transform_queue.render_callables

            # Draw electrodes.
            for electrode_id, df_shape_i in (app.dmf_device.df_shapes
                                             .groupby(app.dmf_device
                                                      .shape_i_columns)):
                r, g, b = self.electrode_color.get(electrode_id, [0, 0, 1])
                self.draw_electrode(df_shape_i, d, (r, g, b, alpha))

            # Draw paths.
            step_options = self.controller.get_step_options()
            for route_i, df_route in (step_options.drop_routes
                                      .groupby('route_i')):
                self.draw_drop_route(df_route, d, line_width=.25)
            d.restore()
        return d

    def set_electrode_color_by_index(self, electrode_index, rgb_color=None):
        '''
        Set electrode color by integer electrode index (*not* string electrode
        identifier).

        ## Electrode identifier versus electrode index ##

        In the SVG export of a device layout (through the `DmfDevice.to_svg()`
        method), the string identifier of each electrode is set from the "id"
        attribute of the corresponding SVG polygon.

        However, it is sometimes convenient to have electrodes indexed by a
        zero-based, contiguous range to, for example, store an attribute of
        each electrode in an array.

        The `DmfDevice` includes an attribute called `indexed_shapes`, which
        maps each electrode string identifier to an integer index.
        '''
        app = get_app()
        electrode_id = app.dmf_device.indexed_shapes[electrode_index]
        self.set_electrode_color(electrode_id, rgb_color=rgb_color)

    def set_electrode_color(self, electrode_id, rgb_color=None):
        '''
        Set electrode color by string electrode identifier.

        Args:

            electrode_id (str) : Electrode identifier.
            rgb_color (tuple) : A 3-tuple, corresponding to a value in the
                range [0, 1] for the red, green, and blue color channels,
                respectively.  If not set, electrode color is set to the
                corresponding default color.
        '''
        if rgb_color is None:
            # TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
            # TODO
            # TODO As of `svg_model==0.5.post10`, `svg_polygons_to_df` includes
            # TODO style (i.e., fill/stroke color) information.  Need to add
            # TODO fill/stroke support, but for now, just color non-actuated
            # TODO electrodes blue.
            # TODO
            # TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
            self.electrode_color[electrode_id] = np.array([0, 0, 1.])
        else:
            self.electrode_color[electrode_id] = rgb_color

    def draw_drop_route(self, df_route, cr, color=None, line_width=None):
        '''
        Draw a line between electrodes listed in a droplet route.

        Arguments
        ---------

         - `df_route`:
             * A `pandas.DataFrame` containing a column named `electrode_i`.
             * For each row, `electrode_i` corresponds to the integer index of
               the corresponding electrode.
         - `cr`: Cairo context.
         - `color`: Either a RGB or RGBA tuple, with each color channel in the
           range [0, 1].  If `color` is `None`, the electrode color is set to
           white.
        '''
        app = get_app()
        df_route_centers = (app.dmf_device.df_indexed_shape_centers
                            .iloc[df_route.electrode_i][['x_center',
                                                         'y_center']])
        df_endpoint_marker = (.6 * get_endpoint_marker(df_route_centers) +
                              df_route_centers.iloc[-1].values)

        # Save cairo context to restore after drawing route.
        cr.save()
        if color is None:
            color = []
        if len(color) < 4:
            color += [1.] * (4 - len(color))
        cr.set_source_rgba(*color)
        cr.move_to(*df_route_centers.iloc[0])
        for electrode_i, center_i in df_route_centers.iloc[1:].iterrows():
            cr.line_to(*center_i)
        if line_width is None:
            line_width = np.sqrt((df_endpoint_marker.max().values -
                                  df_endpoint_marker.min().values).prod()) * .1
        cr.set_line_width(line_width)
        cr.stroke()

        cr.move_to(*df_endpoint_marker.iloc[0])
        for electrode_i, center_i in df_endpoint_marker.iloc[1:].iterrows():
            cr.line_to(*center_i)
        cr.close_path()
        cr.fill()
        # Restore cairo context after drawing route.
        cr.restore()

    def draw_electrode(self, electrode, cairo_context, color=None):
        '''
        Draw the shape of an electrode.

        Arguments
        ---------

         - `electrode`:
             * An `Electrode` instance.
         - `cr`: Cairo context.
         - `color`: Either a RGB or RGBA tuple, with each color channel in the
           range [0, 255].  If `color` is `None`, the electrode color is set to
           white.
        '''
        cairo_context.save()
        if color is None:
            color = np.array([0, 0, 1.])
        if len(color) < 4:
            color += [1.] * (len(color) - 4)
        cairo_context.set_source_rgba(*color)

        # Use attribute lookup for `x` and `y`, since it is considerably faster
        # than `get`-based lookup using columns name strings.
        vertices_x = electrode.x.values
        vertices_y = electrode.y.values
        cairo_context.move_to(vertices_x[0], vertices_y[0])
        for x, y in itertools.izip(vertices_x[1:], vertices_y[1:]):
            cairo_context.line_to(x, y)
        cairo_context.close_path()
        cairo_context.clip_preserve()
        cairo_context.fill()
        cairo_context.restore()

    def on_device_area__expose_event(self, widget, *args):
        if self.cairo_surface is not None:
            self.draw()

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
            return self.device_canvas.find_shape(*svg_coords)
        return None

    def on_device_area__motion_notify_event(self, widget, event):
        self.widget.grab_focus()
        # Determine which electrode was clicked (if any)
        #electrode = self.get_clicked_electrode(event)
        if not (event.state & gtk.gdk.CONTROL_MASK):
            # Control is not being held down, so
            self._source_electrode_id = None

    def on_device_area__key_release_event(self, widget, event):
        '''
        If `<Ctrl>` key was released before releasing left mouse button during
        an electrode pair selection, cancel the electrode pair selection.
        '''
        key_name = gtk.gdk.keyval_name(event.keyval)
        if ((self._source_electrode_id is not None) and
            (key_name in ('Control_L', 'Control_R')) and
            not (event.state & gtk.gdk.CONTROL_MASK)):

            self.reset_pair_op()

    def reset_pair_op(self):
        '''
        Cancel an electrode pair selection.
        '''
        # Control is not being held down, so
        self._source_electrode_id = None
        print 'cancel pair op'

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

    def on_device_area__button_release_event(self, widget, event):
        '''
        If performing an electrode pair selection and left mouse button was
        released over an electrode, select target electrode accordingly and
        process electrode pair selection.
        '''
        self.widget.grab_focus()
        if event.button == 1:
            # Determine which electrode was clicked (if any)
            electrode_id = self.get_clicked_electrode(event)
            if electrode_id is None: return

            source_id = self._source_electrode_id
            if source_id is not None:
                target_id = electrode_id
                self._source_electrode_id = None
                print 'pair selected:', source_id, target_id
                self.on_electrode_pair_selected(source_id, target_id)

    def on_electrode_pair_selected(self, source_id, target_id):
        '''
        Process pair of selected electrodes.

        For now, this consists of finding the shortest path between the two
        electrodes and appending it to the list of droplet routes for the
        current step.

        Note that the droplet routes for a step are stored in a frame/table in
        the `DmfDeviceController` step options.
        '''
        import networkx as nx
        import pandas as pd

        app = get_app()
        if app.dmf_device is not None:
            try:
                shortest_path = app.dmf_device.find_path(source_id, target_id)
                step_options = self.controller.get_step_options()
                drop_routes = step_options.drop_routes
                route_i = (drop_routes.route_i.max() + 1
                           if drop_routes.shape[0] > 0 else 0)
                route_indexes = (app.dmf_device.shape_indexes[shortest_path]
                                 .tolist())
                drop_route = (pd.DataFrame(route_indexes,
                                           columns=['electrode_i'],
                                           dtype=int)
                              .reset_index().rename(columns={'index':
                                                             'transition_i'}))
                drop_route.insert(0, 'route_i', route_i)
                step_options.drop_routes = drop_routes.append(drop_route,
                                                              ignore_index
                                                              =True)
                gtk.idle_add(self.update_draw_queue)
            except nx.NetworkXNoPath:
                print 'no path found'

    def on_electrode_click(self, electrode, event):
        options = self.controller.get_step_options()
        state = options.state_of_channels
        app = get_app()
        if event.button == 1:
            try:
                # Get `pd.Series` of channels corresponding to `electrode`.
                electrode_channels = (app.dmf_device.df_electrode_channels
                                      .set_index('electrode_id')
                                      .channel).ix[[electrode]]
                if event.state & gtk.gdk.CONTROL_MASK:
                    # Control was pressed when electrode was clicked.
                    # Mark starting electrode.
                    if self._source_electrode_id is None:
                        self._source_electrode_id = electrode
                        print 'source selected:', self._source_electrode_id
                else:
                    self._source_electrode_id = None
                    for channel in electrode_channels:
                        if state[channel] > 0:
                            state[channel] = 0
                        else:
                            state[channel] = 1
                    self.emit('channel-state-changed', electrode_channels[:])
            except IndexError:
                logger.error("No channel assigned to electrode.")
        elif event.button == 3:
            self.popup.popup(state, electrode, event.button, event.time)
        return True

    def on_clear_drop_routes(self, context_menu, electrode_id, *args,
                             **kwargs):
        '''
        Clear all drop routes for current protocol step that include the
        specified electrode (identified by string identifier).
        '''
        self.controller.clear_drop_routes(electrode_id)
        gtk.idle_add(self.update_draw_queue)

    def on_clear_all_drop_routes(self, *args, **kwargs):
        '''
        Clear all drop routes for current protocol step.
        '''
        self.controller.clear_drop_routes()
        gtk.idle_add(self.update_draw_queue)

    def on_device_area__key_press_event(self, widget, data=None):
        pass

    def reset_canvas(self, shape=None):
        '''
        Create a new `ShapesCanvas` (from the `svg_model.shapes_canvas` module)
        based on the polygons/shapes of the current DMF device.

        The `find_shape` method of the `ShapesCanvas` class looks up the
        polygon/shape that surrounds a specified $(x, y)$ coordinate (or `None`
        if coordinate does not fall within any shape).

        Args:

            shape (tuple) : The width and height of the canvas to aspect fill
                the DMF device to.  Note that `find_shape` assumes coordinates
                are specified in the *scaled* space.
        '''
        if shape is None:
            x, y, width, height = self.device_area.get_allocation()
            shape = width, height
        app = get_app()
        if app.dmf_device:
            # Create shapes canvas with same scale as original shapes frame.
            # This canvas is used for to conduct point queries to detect
            # electrode clicks, etc.
            self.device_canvas = ShapesCanvas(app.dmf_device.df_shapes,
                                              app.dmf_device.shape_i_columns)


def get_endpoint_marker(df_route_centers):
    app = get_app()
    df_shapes = app.dmf_device.df_shapes
    df_endpoint_electrode = df_shapes.loc[df_shapes.id ==
                                          app.dmf_device.indexed_shapes
                                          [df_route_centers.index[-1]]]
    df_endpoint_bbox = (df_endpoint_electrode[['x_center_offset',
                                               'y_center_offset']]
                        .describe().loc[['min', 'max']])
    return pd.DataFrame([[df_endpoint_bbox.x_center_offset['min'],
                          df_endpoint_bbox.y_center_offset['min']],
                         [df_endpoint_bbox.x_center_offset['min'],
                          df_endpoint_bbox.y_center_offset['max']],
                         [df_endpoint_bbox.x_center_offset['max'],
                          df_endpoint_bbox.y_center_offset['max']],
                         [df_endpoint_bbox.x_center_offset['max'],
                          df_endpoint_bbox.y_center_offset['min']]],
                        columns=['x_center_offset', 'y_center_offset'])
