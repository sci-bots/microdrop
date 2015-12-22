"""
Copyright 2011-2015 Ryan Fobel and Christian Fobel

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
from path_helpers import path
from svg_model import svg_polygons_to_df
from svg_model.connections import extract_connections
from svg_model.shapes_canvas import ShapesCanvas
from svgwrite.shapes import Polygon
import numpy as np
import pandas as pd
import svgwrite

class DeviceScaleNotSet(Exception):
    pass



class DmfDevice(object):
    @classmethod
    def load(cls, svg_filepath, **kwargs):
        """
        Load a DmfDevice from a file.

        Args:

            filename: path to file.

        Raises:

            TypeError: file is not a DmfDevice.
            FutureVersionError: file was written by a future version of the
                software.
        """
        return cls(svg_filepath, **kwargs)

    def __init__(self, svg_filepath, name=None, **kwargs):
        self.name = name or path(svg_filepath).namebase
        self.scale = None

        # Read SVG polygons into dataframe, one row per polygon vertex.
        df_shapes = svg_polygons_to_df(svg_filepath)

        # Add SVG file path as attribute.
        self.svg_filepath = svg_filepath
        self.df_shapes = df_shapes
        self.shape_i_columns = 'path_id'

        # Create temporary shapes canvas with same scale as original shapes
        # frame.  This canvas is used for to conduct point queries to detect
        # which shape (if any) overlaps with the endpoint of a connection line.
        svg_canvas = ShapesCanvas(self.df_shapes, 'path_id')
        # Detect connected shapes based on lines in "Connection" layer of the
        # SVG.
        self.df_shape_connections = extract_connections(self.svg_filepath,
                                                        svg_canvas)
        self.df_electrode_channels = self.get_electrode_channels()
        self.electrode_areas = self.get_electrode_areas()

    def update_electrode_channels(self, electrode_id, new_channel_list):
        # Update channels for electrode `electrode_id` to `new_channel_list`.
        # This includes updating `self.df_electrode_channels`.

        # Get electrode channels frame for all electrodes except
        # `electrode_id`.
        df_electrode_channels = (self.df_electrode_channels
                                 .loc[self.df_electrode_channels.electrode_id
                                      != electrode_id])
        if len(new_channel_list) > 0:
            # Add new list of channels for electrode.
            df_electrode_channels_i = pd.DataFrame([[electrode_id, channel]
                                                    for channel in
                                                    new_channel_list],
                                                   columns=['electrode_id',
                                                            'channel'])
            self.df_electrode_channels = (pd.concat([df_electrode_channels,
                                                     df_electrode_channels_i])
                                          .reset_index(drop=True))
        else:
            # No channels assigned to electrode.
            self.df_electrode_channels = df_electrode_channels

    @property
    def electrodes(self):
        return self.electrode_areas.index.copy()

    def get_electrode_areas(self):
        from svg_model.data_frame import get_shape_areas

        return get_shape_areas(self.df_shapes, 'path_id')

    def get_svg_frame(self):
        '''
        Return a `pandas.DataFrame` containing the vertices for electrode
        paths.

        Each row of the frame corresponds to a single path vertex.  The
        `groupby` method may be used, for example, to apply operations to
        vertices on a per-path basis, such as calculating the bounding box.
        '''
        return self.df_shapes

    def get_electrode_channels(self):
        '''
        Load the channels associated with each electrode from the device layer
        of an SVG source.

        For each electrode polygon, the channels are read as a comma-separated
        list from the `"data-channels"` attribute.

        Args:

            svg_source (filepath) : Input SVG file containing connection lines.
            shapes_canvas (shapes_canvas.ShapesCanvas) : Shapes canvas
                containing shapes to compare against connection endpoints.
            electrode_layer (str) : Name of layer in SVG containing electrodes.
            electrode_xpath (str) : XPath string to iterate throught
                electrodes.
            namespaces (dict) : SVG namespaces (compatible with `etree.parse`).

        Returns:

            (pandas.DataFrame) : Each row corresponds to a channel connected to
                an electrode, where the `"electrode_id"` column corresponds to
                the `"id"` attribute of the corresponding SVG polygon.

        Notes
        -----

         - Each electrode corresponds to a closed path in the device drawing.
         - Each channel index corresponds to a DMF device channel that may be
           actuated independently.
        '''
        return extract_channels(self.svg_filepath)

    def get_bounding_box(self):
        xmin, ymin = self.df_shapes[['x', 'y']].min().values
        xmax, ymax = self.df_shapes[['x', 'y']].max().values
        return xmin, ymin, (xmax - xmin), (ymax - ymin)

    def max_channel(self):
        return self.df_electrode_channels.channel.max()

    def actuated_area(self, state_of_all_channels):
        if state_of_all_channels.max() == 0:
            # No channels are actuated.
            return 0
        if self.scale is None:
            raise DeviceScaleNotSet()

        # Get the index of all actuated channels.
        actuated_channels_index = np.where(state_of_all_channels > 0)[0]
        # Based on the actuated channels, look up the electrodes that are
        # actuated.
        actuated_electrodes = self.actuated_electrodes(actuated_channels_index)
        # Look up the area of each actuated electrode.
        actuated_electrode_areas = (self.electrode_areas
                                    .ix[actuated_electrodes.values])
        # Compute the total actuated electrode area and scale by device scale.
        return self.scale * actuated_electrode_areas.sum()

    def actuated_electrodes(self, actuated_channels_index):
        return (self.df_electrode_channels.set_index('channel')
                ['electrode_id'].ix[actuated_channels_index])

    def to_svg(self):
        #minx, miny, w, h = self.get_bounding_box()
        #dwg = svgwrite.Drawing(size=(w,h))
        #for i, e in self.electrodes.iteritems():
            #c = e.path.color
            #color = 'rgb(%d,%d,%d)' % (c[0],c[1],c[2])
            #kwargs = {'data-channels': ','.join(map(str, e.channels))}
            #p = Polygon([(x-minx,y-miny)
                         #for x,y in e.path.loops[0].verts], fill=color,
                        #id='electrode%d' % i, debug=False, **kwargs)
            #dwg.add(p)
        #return dwg.tostring()
        with open(self.svg_filepath, 'rb') as input_:
            return input_.read()


def extract_channels(svg_source, electrode_layer='Device',
                     electrode_xpath=None, namespaces=None):
    '''
    Load the channels associated with each electrode from the device layer of
    an SVG source.

    For each electrode polygon, the channels are read as a comma-separated list
    from the `"data-channels"` attribute.

    Args:

        svg_source (filepath) : Input SVG file containing connection lines.
        shapes_canvas (shapes_canvas.ShapesCanvas) : Shapes canvas containing
            shapes to compare against connection endpoints.
        electrode_layer (str) : Name of layer in SVG containing electrodes.
        electrode_xpath (str) : XPath string to iterate throught electrodes.
        namespaces (dict) : SVG namespaces (compatible with `etree.parse`).

    Returns:

        (pandas.DataFrame) : Each row corresponds to a channel connected to an
            electrode, where the `"electrode_id"` column corresponds to the
            `"id"` attribute of the corresponding SVG polygon.
    '''
    from lxml import etree
    from svg_model import INKSCAPE_NSMAP

    if namespaces is None:
        namespaces = INKSCAPE_NSMAP

    e_root = etree.parse(svg_source)
    frames = []

    if electrode_xpath is None:
        electrode_xpath = ("//svg:g[@inkscape:label='%s']/svg:polygon"
                           % electrode_layer)

    for electrode_i in e_root.xpath(electrode_xpath, namespaces=namespaces):
        channels_i = map(int, electrode_i.attrib.get('data-channels',
                                                     '').split(','))
        frames.extend([[electrode_i.attrib['id'], channel]
                       for channel in channels_i])

    if frames:
        df_channels = pd.DataFrame(frames, columns=['electrode_id', 'channel'])
    else:
        df_channels = pd.DataFrame(None, columns=['electrode_id', 'channel'])
    return df_channels
