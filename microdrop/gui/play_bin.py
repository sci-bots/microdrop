import gst

from opencv.safe_cv import cv
from warp_perspective import warp_perspective
from cairo_draw import CairoDrawBase


class PlayBin(gst.Bin):
    def __init__(self, name, video_src, cairo_draw, fps=15, width=640, height=480,
            time_overlay=False):
        super(PlayBin, self).__init__(name)

        width_text = ',width=%s' % width
        height_text = ',height=%s' % height
        fps_text = ',framerate=%s/1' % fps
        caps_str = 'video/x-raw-yuv%s%s%s' % (width_text, height_text, fps_text)

        # -- setup video_src --
        video_caps = gst.Caps(caps_str)
        self.video_caps_filter = gst.element_factory_make('capsfilter', 'caps_filter')
        self.video_caps_filter.set_property('caps', video_caps)
        video_tee = gst.element_factory_make('tee', 'video_tee')
        #Feed branch
        feed_queue = gst.element_factory_make('queue', 'feed_queue')
        _time_overlay = gst.element_factory_make('timeoverlay', 'time_overlay')
        warp_in_color = gst.element_factory_make('ffmpegcolorspace', 'warp_in_color')
        self.warper = warp_perspective()
        warp_out_color = gst.element_factory_make('ffmpegcolorspace', 'warp_out_color')
        cairo_color_in = gst.element_factory_make('ffmpegcolorspace', 'cairo_color_in')
        cairo_color_out = gst.element_factory_make('ffmpegcolorspace', 'cairo_color_out')
        video_sink = gst.element_factory_make('autovideosink', 'video_sink')
        video_scale = gst.element_factory_make('videoscale', 'video_scale')
        self.scale_caps_filter = gst.element_factory_make('capsfilter',
                'scale_caps_filter')

        self.text_overlay = gst.element_factory_make('textoverlay', 'text_overlay')

        video_rate = gst.element_factory_make('videorate', 'video_rate')
        rate_caps = gst.Caps(caps_str)
        rate_caps_filter = gst.element_factory_make('capsfilter', 'rate_caps_filter')
        rate_caps_filter.set_property('caps', rate_caps)

        self.app_sink = gst.element_factory_make('appsink', 'app_sink')
        self.app_sink.set_property('drop', True)
        self.app_sink.set_property('max-buffers', 1)
        app_sink_color_in = gst.element_factory_make('ffmpegcolorspace', 'app_sink_color_in')
        self.app_sink.set_property('caps',
                gst.caps_from_string('video/x-raw-rgb,depth=24'))

        app_sink_queue = gst.element_factory_make('queue', 'app_sink_queue')
        capture_queue = gst.element_factory_make('queue', 'capture_queue')
        test_queue = gst.element_factory_make('queue', 'test_queue')

        self.add(self.video_caps_filter, video_rate,
                rate_caps_filter, video_tee,

                app_sink_queue,
                app_sink_color_in,
                self.app_sink,
                feed_queue,

                video_scale, self.scale_caps_filter,
                # Elements for drawing cairo overlay on video
                cairo_draw, cairo_color_out, cairo_color_in,

                # Elements for applying OpenCV warp-perspective transformation
                self.warper, warp_in_color, warp_out_color,
                self.text_overlay,
                video_sink, capture_queue)
        if time_overlay:
            self.add(_time_overlay)

        gst.element_link_many(self.video_caps_filter, feed_queue)
        gst.element_link_many(video_tee,
                warp_in_color, self.warper, warp_out_color,
                video_rate, rate_caps_filter, 
                video_scale, self.scale_caps_filter,
                cairo_color_in, cairo_draw, cairo_color_out,
                self.text_overlay,
                video_sink)

        if time_overlay:
            gst.element_link_many(feed_queue, _time_overlay, video_tee)
        else:
            gst.element_link_many(feed_queue, video_tee)

        video_tee.link(capture_queue)
        gst.element_link_many(video_tee, app_sink_queue, app_sink_color_in,
                self.app_sink)

        # Add ghost 'src' pad 
        self.play_bin_src_gp = gst.GhostPad("src", capture_queue.get_pad('src'))
        self.add_pad(self.play_bin_src_gp)

        self._video_src = None
        self.video_src = video_src

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

    def grab_frame(self):
        buffer_ = self.app_sink.emit('pull-buffer')
        if buffer_ is None:
            return None
        struct = buffer_.caps[0]
        #y = np.fromstring(inbuf.data, dtype='uint8', count=len(inbuf))
        #width, height = struct['width'], struct['height']
        #y.shape = (height, width, 3)
        width, height = struct['width'], struct['height']
        cv_img = cv.CreateMat(height, width, cv.CV_8UC3)
        cv.SetData(cv_img, buffer_.data, width * 3)
        cv.CvtColor(cv_img, cv_img, cv.CV_BGR2RGB)
        return cv_img
