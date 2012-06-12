import gst
import gtk
import gobject

from .warp_perspective import warp_perspective
from .cairo_draw import CairoDrawBase
from .grab_frame import grab_frame


# We need to call threads_init() to ensure correct gtk operation with
# multi-threaded code (needed for GStreamer).
gobject.threads_init()
gtk.gdk.threads_init()


class WarpBin(gst.Bin):
    def __init__(self, name, draw_on=None):
        super(WarpBin, self).__init__(name)

        warp_in_color = gst.element_factory_make('ffmpegcolorspace', 'warp_in_color')
        video_scale = gst.element_factory_make('videoscale', 'video_scale')
        self.scale_caps_filter = gst.element_factory_make('capsfilter',
                'scale_caps_filter')
        self.frame_grab_callbacks = []
        self.scale(640, 480)
        self.warper = warp_perspective()
        warp_out_color = gst.element_factory_make('ffmpegcolorspace', 'warp_out_color')

        in_color = gst.element_factory_make('ffmpegcolorspace', 'in_color')
        self.frame_grabber = grab_frame(self.on_frame_grabbed)
        out_color = gst.element_factory_make('ffmpegcolorspace', 'out_color')

        self.add(in_color, self.frame_grabber, out_color,
                video_scale, self.scale_caps_filter, warp_in_color, self.warper,
                        warp_out_color)
        #gst.element_link_many(app_sink_queue, app_sink_color_in,
                #app_sink)
        gst.element_link_many(in_color, self.frame_grabber, out_color, video_scale,
                self.scale_caps_filter, warp_in_color, self.warper,
                        warp_out_color)
        if draw_on:
            self._draw_on = draw_on
            self.cairo = CairoDrawBase('cairo_draw', self._draw_on)
            cairo_out_color = gst.element_factory_make('ffmpegcolorspace',
                    'cairo_out_color')
            self.add(self.cairo, cairo_out_color)
            gst.element_link_many(warp_out_color, self.cairo, cairo_out_color)
            output_element = cairo_out_color
        else:
            self._draw_on = None
            output_element = warp_out_color

        sink_gp = gst.GhostPad('sink', in_color.get_pad('sink'))
        play_bin_src_gp = gst.GhostPad("src", output_element.get_pad('src'))
        self.add_pad(sink_gp)
        self.add_pad(play_bin_src_gp)

    def grab_frame(self, callback):
        self.frame_grab_callbacks.append(callback)
        self.frame_grabber.set_property('grab-requested', True)

    def on_frame_grabbed(self, cv_img):
        for callback in self.frame_grab_callbacks:
            callback(cv_img)
        self.frame_grab_callbacks = []

    def scale(self, width=None, height=None):
        if width is None and height is None:
            return
        if width:
            width_text = ',width=%s' % width
        else:
            width_text = ''
        if height:
            height_text = ',height=%s' % height
        else:
            height_text = ''
        scale_text = 'video/x-raw-yuv%s%s' % (width_text, height_text)
        scale_caps = gst.Caps(scale_text)
        self.scale_caps_filter.set_property('caps', scale_caps)
