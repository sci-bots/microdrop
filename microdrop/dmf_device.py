"""
Copyright 2011-2015 Ryan Fobel and Christian Fobel

This file is part of MicroDrop.

MicroDrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

MicroDrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MicroDrop.  If not, see <http://www.gnu.org/licenses/>.
"""
import logging

from droplet_planning.connections import get_adjacency_matrix
from lxml import etree
from lxml.etree import XPathEvaluator
from path_helpers import path
from svg_model import (INKSCAPE_NSMAP, svg_shapes_to_df, INKSCAPE_PPmm,
                       compute_shape_centers)
from svg_model.connections import extract_connections
from svg_model.shapes_canvas import ShapesCanvas
import networkx as nx
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

# Only read interpret SVG paths and polygons from `Device` layer as electrodes.
ELECTRODES_XPATH = (r'//svg:g[@inkscape:label="Device"]//svg:path | '
                    r'//svg:g[@inkscape:label="Device"]//svg:polygon')


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

        # Read SVG paths and polygons from `Device` layer into data frame, one
        # row per polygon vertex.
        self.df_shapes = svg_shapes_to_df(svg_filepath, xpath=ELECTRODES_XPATH)

        # Add SVG file path as attribute.
        self.svg_filepath = svg_filepath
        self.shape_i_columns = 'id'

        # Create temporary shapes canvas with same scale as original shapes
        # frame.  This canvas is used for to conduct point queries to detect
        # which shape (if any) overlaps with the endpoint of a connection line.
        svg_canvas = ShapesCanvas(self.df_shapes, self.shape_i_columns)

        # Detect connected shapes based on lines in "Connection" layer of the
        # SVG.
        self.df_shape_connections = extract_connections(self.svg_filepath,
                                                        svg_canvas)

        # Scale coordinates to millimeter units.
        self.df_shapes[['x', 'y']] -= self.df_shapes[['x', 'y']].min().values
        self.df_shapes[['x', 'y']] /= INKSCAPE_PPmm.magnitude

        self.df_shapes = compute_shape_centers(self.df_shapes,
                                               self.shape_i_columns)

        self.df_electrode_channels = self.get_electrode_channels()

        self.graph = nx.Graph()
        for index, row in self.df_shape_connections.iterrows():
            self.graph.add_edge(row['source'], row['target'])

        # Get data frame, one row per electrode, indexed by electrode path id,
        # each row denotes electrode center coordinates.
        self.df_shape_centers = (self.df_shapes.drop_duplicates(subset=['id'])
                                 .set_index('id')[['x_center', 'y_center']])
        (self.adjacency_matrix, self.indexed_shapes,
         self.shape_indexes) = get_adjacency_matrix(self.df_shape_connections)
        self.df_indexed_shape_centers = (self.df_shape_centers
                                         .loc[self.shape_indexes.index]
                                         .reset_index())
        self.df_indexed_shape_centers.rename(columns={'index': 'shape_id'},
                                             inplace=True)

        self.df_shape_connections_indexed = self.df_shape_connections.copy()
        self.df_shape_connections_indexed['source'] = \
            map(str, self.shape_indexes[self.df_shape_connections['source']])
        self.df_shape_connections_indexed['target'] \
            = map(str, self.shape_indexes[self.df_shape_connections
                                          ['target']])

        self.df_shapes_indexed = self.df_shapes.copy()
        self.df_shapes_indexed['id'] = map(str, self.shape_indexes
                                           [self.df_shapes['id']])
        # Modified state (`True` if electrode channels have been updated).
        self._dirty = False

    @property
    def df_electrode_channels(self):
        return self._df_electrode_channels

    @df_electrode_channels.setter
    def df_electrode_channels(self, value):
        self._df_electrode_channels = value
        self.electrodes_by_channel = (self.df_electrode_channels
                                      .set_index('channel')['electrode_id'])
        self.channels_by_electrode = (self.df_electrode_channels
                                      .set_index('electrode_id')['channel'])
        self.electrode_areas = self.get_electrode_areas()
        self.channel_areas = pd.Series([self.electrode_areas
                                        [self.electrodes_by_channel.ix[c]]
                                        .sum() for c in
                                        self.electrodes_by_channel.index],
                                       index=self.electrodes_by_channel.index)

    @property
    def dirty(self):
        return self._dirty

    def set_electrode_channels(self, electrode_id, channels):
        '''
        Set channels for electrode `electrode_id` to `channels`.

        This includes updating `self.df_electrode_channels`.

        .. note:: Existing channels assigned to electrode are overwritten.

        Parameters
        ----------
        electrode_id : str
            Electrode identifier.
        channels : list
            List of channel identifiers assigned to the electrode.

        Returns
        -------
        bool
            ``True`` if channel mappings have changed.
        '''
        # Get electrode channels frame for all electrodes except
        # `electrode_id`.
        df_electrode_channels = (self.df_electrode_channels
                                 .loc[self.df_electrode_channels.electrode_id
                                      != electrode_id])
        if len(channels) > 0:
            # Add new list of channels for electrode.
            df_electrode_channels_i = pd.DataFrame([[electrode_id, channel]
                                                    for channel in
                                                    channels],
                                                   columns=['electrode_id',
                                                            'channel'])
            self.df_electrode_channels = (pd.concat([df_electrode_channels,
                                                     df_electrode_channels_i])
                                          .reset_index(drop=True))
        else:
            # No channels assigned to electrode.
            self.df_electrode_channels = df_electrode_channels

        # If the channels mappings have changed, update modified state.
        df_diff_channels = self.diff_electrode_channels()
        if df_diff_channels.shape[0] > 0:
            self._dirty = True
        return self.dirty

    @property
    def electrodes(self):
        return self.electrode_areas.index.copy()

    def get_electrode_areas(self):
        '''
        Returns
        -------
        pandas.Series
            Area of each electrode in square millimeters, indexed by electrode
            identifier.
        '''
        from svg_model.data_frame import get_shape_areas

        return get_shape_areas(self.df_shapes, self.shape_i_columns)

    def get_svg_frame(self):
        '''
        Return a :class:`pandas.DataFrame` containing the vertices for
        electrode paths.

        Each row of the frame corresponds to a single path vertex.  The
        :meth:`groupby` method may be used, for example, to apply operations to
        vertices on a per-path basis, such as calculating the bounding box.
        '''
        return self.df_shapes.copy()

    def get_electrode_channels(self):
        '''
        Load the channels associated with each electrode from the device layer
        of an SVG source.

        For each electrode polygon, the channels are read as a comma-separated
        list from the `"data-channels"` attribute.

        Returns
        -------
        pandas.DataFrame
            Each row corresponds to a channel connected to an electrode, where
            the ``"electrode_id"`` column corresponds to the ``"id"`` attribute
            of the corresponding SVG polygon.

        Notes
        -----

         - Each electrode corresponds to a closed path in the device drawing.
         - Each channel index corresponds to a DMF device channel that may be
           actuated independently.
        '''
        return extract_channels(self.df_shapes)

    def get_bounding_box(self):
        '''
        Returns
        -------
        tuple
            Tuple containing origin-`x`, origin-`y`, width and height,
            respectively.
        '''
        xmin, ymin = self.df_shapes[['x', 'y']].min().values
        xmax, ymax = self.df_shapes[['x', 'y']].max().values
        return xmin, ymin, (xmax - xmin), (ymax - ymin)

    def max_channel(self):
        '''
        Returns:

            int : Maximum channel index.
        '''
        return self.df_electrode_channels.channel.max()

    def get_actuated_electrodes_area(self, electrode_states):
        '''
        Compute area of actuated electrodes.

        Args:

            electrode_states (pandas.Series) : Electrode states, indexed by
                electrode identifier.  Any state greater than zero is
                considered actuated.

        Returns:

            float : Area of actuated electrodes in square millimeters.
        '''
        actuated_electrodes = electrode_states[electrode_states > 0]
        # Look up the area of each actuated electrode.
        actuated_electrode_areas = (self.electrode_areas
                                    .ix[actuated_electrodes.index])
        # Compute the total actuated electrode area and scale by device scale.
        return actuated_electrode_areas.sum()

    def actuated_area(self, state_of_all_channels):
        '''
        Compute area of all actuated electrodes.

        Args:

            state_of_all_channels (np.array) : An array-like instance
                containing an actuation level for each respective channel.

        Returns:

            float : Area of actuated electrodes in square millimeters.
        '''
        if state_of_all_channels.max() == 0:
            # No channels are actuated.
            return 0

        # Get the index of all actuated channels.
        actuated_channels_index = np.where(state_of_all_channels > 0)[0]
        # Based on the actuated channels, look up the electrodes that are
        # actuated.
        actuated_electrodes = self.actuated_electrodes(actuated_channels_index)
        # Look up the area of each actuated electrode.
        actuated_electrode_areas = (self.electrode_areas
                                    .ix[actuated_electrodes.values])
        # Compute the total actuated electrode area and scale by device scale.
        return actuated_electrode_areas.sum()

    def actuated_electrodes(self, actuated_channels_index):
        '''
        Parameters
        ----------
        actuated_channels_index : list or array-like
            Actuated channel indexes.

        Returns
        -------
        pandas.Series
            Actuated electrode identifiers, indexed by channel index.
        '''
        return self.electrodes_by_channel.ix[actuated_channels_index]

    def actuated_channels(self, actuated_electrodes_index):
        '''
        Parameters
        ----------
        actuated_electrodes_index : list or array-like
            Actuated electrode identifiers.

        Returns
        -------
        pandas.Series
            Actuated channel index values, indexed by electrode identifier.
        '''
        # Get `pd.Series` of channels corresponding to electrodes.
        return self.channels_by_electrode.ix[actuated_electrodes_index]

    def find_path(self, source_id, target_id):
        '''
        Returns
        -------
        list
            A list of nodes on the shortest path from source to target.
        '''
        if source_id == target_id:
            shortest_path = [source_id]
        else:
            shortest_path = nx.dijkstra_path(self.graph, source_id, target_id,
                                             'cost')
        return shortest_path

    def to_svg(self):
        '''
        Returns:

            unicode : SVG XML source with up-to-date electrode channel lists.
        '''
        xml_root = etree.parse(self.svg_filepath)

        # Identify electrodes with modified channel lists.
        df_diff_channels = self.diff_electrode_channels()

        # Update `svg:path` XML elements for electrodes with modified channel
        # lists.
        xpath = XPathEvaluator(xml_root, namespaces=INKSCAPE_NSMAP)
        for electrode_id, (orig_i, new_i) in df_diff_channels.iterrows():
            elements_i = xpath.evaluate('//svg:path[@id="%s"]' % electrode_id)
            for element_i in elements_i:
                element_i.attrib['data-channels'] = ','.join(map(str, new_i))
        return etree.tounicode(xml_root)

    def diff_electrode_channels(self):
        '''
        Identify electrodes with modified channel lists.

        Returns
        -------
        pandas.DataFrame
            Frame containing modified electrode channel lists.  The two columns
            contain a list for the original and new assigned channels,
            respectively, indexed by ``electrode_id``.
        '''
        original_channels = extract_channels(self.df_shapes)
        original_groups = original_channels.groupby('electrode_id').groups

        new_channels = self.df_electrode_channels.copy()
        new_groups = new_channels.groupby('electrode_id').groups

        rows = []

        for electrode_id, new_channel_indexes in new_groups.iteritems():
            if electrode_id not in original_groups:
                orig_i = []
            else:
                orig_i = (original_channels.channel
                        .values[original_groups[electrode_id]].tolist())
            new_i = new_channels.channel.values[new_channel_indexes].tolist()
            if not (orig_i == new_i):
                rows.append((electrode_id, orig_i, new_i))
        if not rows:
            rows = None
        return pd.DataFrame(rows, columns=['electrode_id', 'original',
                                           'new']).set_index('electrode_id')


def extract_channels(df_shapes):
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

    Returns
    -------
    pandas.DataFrame
        Each row corresponds to a channel connected to an electrode, where the
        ``"electrode_id"`` column corresponds to the ``"id"`` attribute of the
        corresponding SVG polygon.
    '''
    frames = []

    if 'data-channels' in df_shapes:
        shape_channel_lists = (df_shapes
                               .drop_duplicates(subset=['id', 'data-channels'])
                               .set_index('id')['data-channels']
                               .str.split(',').dropna())

        for shape_i, channels_i in shape_channel_lists.iteritems():
            frames.extend([[shape_i, int(channel)] for channel in channels_i])

    if frames:
        df_channels = pd.DataFrame(frames, columns=['electrode_id', 'channel'])
    else:
        df_channels = pd.DataFrame(None, columns=['electrode_id', 'channel'])
    df_channels['channel'] = df_channels['channel'].astype(int)
    return df_channels
