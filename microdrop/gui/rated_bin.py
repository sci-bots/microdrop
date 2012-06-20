import gst
import gobject
gobject.threads_init()


class RatedBin(gst.Bin):
    def __init__(self, name, fps=15, width=640, height=480, video_src=None):
        super(RatedBin, self).__init__(name)

        width_text = ',width=%s' % width
        height_text = ',height=%s' % height
        fps_text = ',framerate=%s/1' % fps
        caps_str = 'video/x-raw-yuv,format=(fourcc)YUY2%s%s' % (width_text,
                height_text)
        native_fps_list = [15, 30]
        for native_fps in native_fps_list:
            if native_fps >= fps:
                break
        if fps <= native_fps:
            caps_str += ',framerate=%s/1' % native_fps
        print caps_str

        if video_src is None:
            video_src = gst.element_factory_make('autovideosrc', 'src')
        caps = gst.Caps(caps_str)
        caps_filter = gst.element_factory_make('capsfilter', 'caps_filter')
        caps_filter.set_property('caps', caps)

        caps_str = 'video/x-raw-yuv,format=(fourcc)YUY2%s%s%s' % (width_text, height_text, fps_text)

        rate_caps = gst.Caps(caps_str)
        rate_caps_filter = gst.element_factory_make('capsfilter', 'rate_caps_filter')
        rate_caps_filter.set_property('caps', rate_caps)
        video_rate = gst.element_factory_make('videorate', 'video_rate')

        self.add(video_src, caps_filter, video_rate, rate_caps_filter)
        video_src.link(caps_filter)
        caps_filter.link(video_rate)
        video_rate.link(rate_caps_filter)

        src_gp = gst.GhostPad("src", rate_caps_filter.get_pad('src'))
        self.add_pad(src_gp)
