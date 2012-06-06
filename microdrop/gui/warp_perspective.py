__author__ = 'Christian Fobel <christian@fobel.net>'


import gst
import gobject
gobject.threads_init()
import numpy as np
from opencv.safe_cv import cv


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


def registered_element(class_):
    """Class decorator for registering a Python element.  Note that decorator
    syntax was extended from functions to classes in Python 2.6, so until 2.6
    becomes the norm we have to invoke this as a function instead of by
    saying::

        @gstlal_element_register
        class foo(gst.Element):
            ...
    
    Until then, you have to do::

        class foo(gst.Element):
            ...
        gstlal_element_register(foo)
    """
    from inspect import getmodule
    gobject.type_register(class_)
    getmodule(class_).__gstelementfactory__ = (class_.__name__, gst.RANK_NONE,
            class_)
    return class_


@registered_element
class warp_perspective(gst.BaseTransform):
    '''
    Use OpenCV to apply a warp-perspective.
    '''
    __gstdetails__ = (
        "OpenCV warp-perspective",
        "Filter",
        __doc__.strip(),
        __author__
    )
    __gproperties__ = {
        'transform_matrix': (
            gobject.TYPE_STRING,
            'Transformation matrix',
            'Comma-separated transformation matrix values',
            '1,0,0,0,1,0,0,0,1',
            gobject.PARAM_READWRITE | gobject.PARAM_CONSTRUCT
        ),
    }
    __gsttemplates__ = (
        gst.PadTemplate("sink",
            gst.PAD_SINK, gst.PAD_ALWAYS,
            gst.caps_from_string('video/x-raw-rgb,depth=24')
        ),
        gst.PadTemplate("src",
            gst.PAD_SRC, gst.PAD_ALWAYS,
            gst.caps_from_string('video/x-raw-rgb,depth=24')
        )
    )

    default_transform = np.identity(3, dtype='float32')

    @property
    def transform_matrix(self):
        value = getattr(self, '_transform_matrix', None)
        if value is None:
            self._transform_matrix = self.default_transform.copy()
        return self._transform_matrix

    @transform_matrix.setter
    def transform_matrix(self, value):
        assert(value.shape == (3, 3))
        self._transform_matrix = value.copy()
        self._transform_matrix_cv = cv.fromarray(self._transform_matrix)

    @property
    def transform_matrix_cv(self):
        if not hasattr(self, '_transform_matrix_cv'):
            self._transform_matrix_cv = cv.fromarray(self.transform_matrix)
        return self._transform_matrix_cv

    def do_set_property(self, prop, val):
        """gobject->set_property virtual method."""
        if prop.name == 'transform-matrix':
            data = np.array([float(v.strip()) for v in val.split(',')],
                    dtype='float32')
            if len(data) != 9:
                raise ValueError, 'Error parsing transform matrix.  Must be a '\
                        'comma-separated list of real numbers'
            data.shape = (3, 3)
            self.transform_matrix = data

    def do_get_property(self, prop):
        """gobject->get_property virtual method."""
        if prop.name == 'transform-matrix':
            return ','.join([str(v)
                    for v in self.transform_matrix.flatten()])

    def do_start(self):
        """GstBaseTransform->start virtual method."""
        self.history = []
        value = self.transform_matrix
        return True

    def do_transform(self, inbuf, outbuf):
        """GstBaseTransform->transform virtual method."""
        struct = inbuf.caps[0]
        width, height = struct['width'], struct['height']
        cv_img = cv.CreateMat(height, width, cv.CV_8UC3)
        cv.SetData(cv_img, inbuf.data, width * 3)
        warped = cv.CreateMat(height, width, cv.CV_8UC3)
        cv.WarpPerspective(cv_img, warped, self.transform_matrix_cv,
                flags=cv.CV_WARP_INVERSE_MAP)
#
        #warped = cv.CreateMat(height, width, cv.CV_8UC3)
        #cv.WarpPerspective(cv_img, warped, self.transform_matrix_cv,
                #flags=cv.CV_WARP_INVERSE_MAP)
        #data = warped.tostring()
        #outbuf[:len(data)] = data
        outbuf[:width * height * 3] = warped.tostring()[:]

        # Done!
        return gst.FLOW_OK


class WarpBin(gst.Bin):
    def __init__(self, name):
        super(WarpBin, self).__init__(name)

        warp_in_color = gst.element_factory_make('ffmpegcolorspace', 'warp_in_color')
        self.warper = warp_perspective()
        warp_out_color = gst.element_factory_make('ffmpegcolorspace', 'warp_out_color')

        self.add(warp_in_color, self.warper, warp_out_color)
        gst.element_link_many(warp_in_color, self.warper, warp_out_color)

        sink_gp = gst.GhostPad('sink', warp_in_color.get_pad('sink'))
        play_bin_src_gp = gst.GhostPad("src", warp_out_color.get_pad('src'))
        self.add_pad(sink_gp)
        self.add_pad(play_bin_src_gp)
