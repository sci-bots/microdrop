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

import time
try:
    import cPickle as pickle
except ImportError:
    import pickle
import warnings
from math import sqrt

from logger import logger
import numpy as np
import yaml
from microdrop_utility import Version, FutureVersionError
from svg_model.geo_path import Path, ColoredPath, Loop
from svg_model.svgload.path_parser import LoopTracer, ParseError
from svg_model.svgload.svg_parser import parse_warning
from svg_model.path_group import PathGroup
from svg_model.body_group import BodyGroup
import svgwrite
from svgwrite.shapes import Polygon


class DeviceScaleNotSet(Exception):
    pass


class DmfDevice():
    class_version = str(Version(0,3,0))
    def __init__(self):
        self.electrodes = {}
        self.x_min = np.Inf
        self.x_max = 0
        self.y_min = np.Inf
        self.y_max = 0
        self.name = None
        self.scale = None
        self.path_group = None  # svg_model.path_group.PathGroup
        self.version = self.class_version
        self.body_group = None
        self.electrode_name_map = {}
        self.name_electrode_map = {}

    def init_body_group(self):
        if self.path_group is None:
            return
        # Initialize a BodyGroup() containing a 2D pymunk space to detect events
        # and perform point queries based on device.
        # Note that we cannot (can't be pickled) and do not want to save a
        # pymunk space, since it represents state information from the device.
        self.body_group = BodyGroup(self.path_group.paths)

    def add_path_group(self, path_group):
        self.path_group = path_group
        self.electrode_name_map = {}
        self.name_electrode_map = {}
        for name, p in self.path_group.paths.iteritems():
            eid = self.add_electrode_path(p)
            self.electrode_name_map[eid] = name
            self.name_electrode_map[name] = eid

    def get_electrode_from_body(self, body):
        name = self.body_group.get_name(body)
        eid = self.name_electrode_map[name]
        return self.electrodes[eid]

    @classmethod
    def load_svg(cls, svg_path):
        with warnings.catch_warnings(record=True) as warning_list:
            path_group = PathGroup.load_svg(svg_path, on_error=parse_warning)
        if warning_list:
            logger.warning('The following paths could not be parsed properly '
                           'and have been ignored:\n%s' % \
                           '\n'.join([str(w.message) for w in warning_list]))
        # Assign the color blue to all paths that have no colour assigned
        for p in path_group.paths.values():
            if p.color is None:
                p.color = (0, 0, 255)

            # If the first and last vertices in a loop are too close together,
            # it can cause tessellation to fail (Ticket # 106).
            for loop in p.loops:
                # distance between first and last point in a loop
                d = sqrt((loop.verts[0][0] - loop.verts[-1][0])**2 + \
                    (loop.verts[0][1] - loop.verts[-1][1])**2)

                # diagonal across device bounding box
                device_diag = sqrt(path_group.get_bounding_box()[2]**2 + \
                     path_group.get_bounding_box()[3]**2)

                # If the distance between the vertices is below a threshold,
                # remove the last vertex (the threshold is scaled by the device
                # diagonal so that we are insensitive to device size).
                if d/device_diag < 1e-3:
                    loop.verts.pop()

        dmf_device = DmfDevice()
        dmf_device.add_path_group(path_group)
        dmf_device.init_body_group()
        return dmf_device

    @classmethod
    def load(cls, filename):
        """
        Load a DmfDevice from a file.

        Args:
            filename: path to file.
        Raises:
            TypeError: file is not a DmfDevice.
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[DmfDevice].load(\"%s\")" % filename)
        logger.info("Loading DmfDevice from %s" % filename)
        start_time = time.time()
        out=None
        with open(filename, 'rb') as f:
            try:
                out = pickle.load(f)
                logger.debug("Loaded object from pickle.")
            except Exception, e:
                logger.debug("Not a valid pickle file. %s." % e)
        if out==None:
            with open(filename, 'rb') as f:
                try:
                    out = yaml.load(f)
                    logger.debug("Loaded object from YAML file.")
                except Exception, e:
                    logger.debug("Not a valid YAML file. %s." % e)
        if out==None:
            raise TypeError
        # check type
        #if not isinstance(out, cls):
            #print out.__class__, cls
            #raise TypeError
        if not hasattr(out, 'version'):
            out.version = '0'
        out._upgrade()
        out.init_body_group()
        logger.debug("[DmfDevice].load() loaded in %f s." % \
                     (time.time()-start_time))
        return out

    def _upgrade(self):
        """
        Upgrade the serialized object if necessary.

        Raises:
            FutureVersionError: file was written by a future version of the
                software.
        """
        logger.debug("[DmfDevice]._upgrade()")
        version = Version.fromstring(self.version)
        logger.debug('[DmfDevice] version=%s, class_version=%s' % (str(version), self.class_version))
        if version > Version.fromstring(self.class_version):
            logger.debug('[DmfDevice] version>class_version')
            raise FutureVersionError
        elif version < Version.fromstring(self.class_version):
            if version < Version(0,1):
                self.version = str(Version(0,1))
                self.scale = None
                logger.info('[DmfDevice] upgrade to version %s' % self.version)
            if version < Version(0,2):
                self.version = str(Version(0,2))
                for id, e in self.electrodes.items():
                    if hasattr(e, "state"):
                        del self.electrodes[id].state
                logger.info('[DmfDevice] upgrade to version %s' % self.version)
            if version < Version(0,3):
                # Upgrade to use pymunk
                self.version = str(Version(0,3))

                x_min = min([e.x_min for e in self.electrodes.values()])
                x_max = max([e.x_max for e in self.electrodes.values()])
                y_min = min([e.y_min for e in self.electrodes.values()])
                y_max = max([e.y_max for e in self.electrodes.values()])

                boundary = Path([Loop([(x_min, y_min), (x_min, y_max),
                        (x_max, y_max), (x_max, y_min)])])

                traced_paths = {}
                tracer = LoopTracer()
                for id, e in self.electrodes.iteritems():
                    try:
                        path_tuples = []
                        for command in e.path:
                            keys_ok = True
                            for k in ['command', 'x', 'y']:
                                if k not in command:
                                    # Missing a parameter, skip
                                    keys_ok = False
                            if not keys_ok:
                                continue
                            path_tuples.append(
                                (command['command'], float(command['x']),
                                float(command['y'])))
                        path_tuples.append(('Z',))
                        loops = tracer.to_loops(path_tuples)
                        p = ColoredPath(loops)
                        p.color = (0, 0, 255)
                        traced_paths[str(id)] = p
                    except ParseError:
                        pass
                    except KeyError:
                        pass
                path_group = PathGroup(traced_paths, boundary)
                electrodes = self.electrodes
                self.electrodes = {}
                self.add_path_group(path_group)

                for id, e in electrodes.iteritems():
                    if str(id) in self.name_electrode_map:
                        eid = self.name_electrode_map[str(id)]
                        self.electrodes[eid].channels = e.channels
                del electrodes
                logger.info('[DmfDevice] upgrade to version %s' % self.version)
        # else the versions are equal and don't need to be upgraded

    def save(self, filename, format='pickle'):
        body_group = self.body_group
        try:
            del self.body_group
            with open(filename, 'wb') as f:
                if format=='pickle':
                    pickle.dump(self, f, -1)
                elif format=='yaml':
                    yaml.dump(self, f)
                else:
                    raise TypeError
        finally:
            self.body_group = body_group

    def get_bounding_box(self):
        return self.path_group.get_bounding_box()

    def add_electrode_path(self, path):
        e = Electrode(path)
        self.electrodes[e.id] = e
        return e.id

    def add_electrode_rect(self, x, y, width, height=None):
        if height is None:
            height = width
        path = []
        path.append({'command':'M','x':x,'y':y})
        path.append({'command':'L','x':x+width,'y':y})
        path.append({'command':'L','x':x+width,'y':y+height})
        path.append({'command':'L','x':x,'y':y+height})
        path.append({'command':'Z'})
        return self.add_electrode_path(path)

    def max_channel(self):
        max_channel = 0
        for electrode in self.electrodes.values():
            if electrode.channels and max(electrode.channels) > max_channel:
                max_channel = max(electrode.channels)
        return max_channel
    
    def actuated_area(self, state_of_all_channels):    
        if self.scale is None:
            raise DeviceScaleNotSet()
        area = 0
        for id, electrode in self.electrodes.iteritems():
            channels = self.electrodes[id].channels
            if channels:
                # Get the state(s) of the channel(s) connected to this
                # electrode.
                states = state_of_all_channels[channels]
                if len(np.nonzero(states > 0)[0]):
                    area += electrode.area() * self.scale
        return area

    def to_svg(self):
        minx, miny, w, h = self.get_bounding_box()
        dwg = svgwrite.Drawing(size=(w,h))
        for i, e in self.electrodes.iteritems():
            c = e.path.color
            color = 'rgb(%d,%d,%d)' % (c[0],c[1],c[2])
            p = Polygon([(x-minx,y-miny) \
                         for x,y in e.path.loops[0].verts], fill=color)
            dwg.add(p)
        return dwg.tostring()
    

class Electrode:
    next_id = 0
    def __init__(self, path):
        self.id = Electrode.next_id
        Electrode.next_id += 1
        self.path = path
        self.channels = []

    def area(self):
        return self.path.get_area()
