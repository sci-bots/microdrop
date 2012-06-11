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
class grab_frame(gst.BaseTransform):
    '''
    Grab a frame on request.
    '''
    __gstdetails__ = (
        "Grab a frame on request",
        "Filter",
        __doc__.strip(),
        __author__
    )
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
    __gproperties__ = {
        'grab-requested': (
            gobject.TYPE_BOOLEAN,
            'Frame grab requested',
            '',
            False,
            gobject.PARAM_READWRITE | gobject.PARAM_CONSTRUCT
        ),
    }

    def __init__(self, on_frame_grabbed):
        super(grab_frame, self).__init__()
        self.on_frame_grabbed = on_frame_grabbed

    def do_set_property(self, prop, val):
        """gobject->set_property virtual method."""
        if prop.name == 'grab-requested':
            self.grab_requested = True

    def do_start(self):
        """GstBaseTransform->start virtual method."""
        self.grab_requested = False
        return True

    def do_transform(self, inbuf, outbuf):
        """GstBaseTransform->transform virtual method."""
        if self.grab_requested:
            self.grab_requested = False
            struct = inbuf.caps[0]
            width, height = struct['width'], struct['height']
            cv_img = cv.CreateMat(height, width, cv.CV_8UC3)
            cv.SetData(cv_img, inbuf.data, width * 3)
            self.on_frame_grabbed(cv_img)
        outbuf[:len(inbuf)] = inbuf[:]
        # Done!
        return gst.FLOW_OK
