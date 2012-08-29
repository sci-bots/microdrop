from pprint import pprint

try:
    import pygst
    pygst.require("0.10")
except ImportError:
    pass
import gst
import glib
from gst_video_source_caps_query import GstVideoSourceManager, FilteredInput

from utility.pygtkhelpers_widgets import Enum, Form
from utility.gui import field_entry_dialog
from utility.gui.form_view_dialog import FormViewDialog


def select_video_mode(video_modes):
    format_cap = lambda c: '[%s] ' % getattr(c['device'], 'name',
            c['device'])[:20] + '%(width)4d x%(height)4d %(framerate)3dfps '\
                    '(%(fourcc)s)' % c
    video_mode_map = dict([(format_cap(c), c) for c in video_modes]) 
    video_keys = sorted(video_mode_map.keys())
    valid, response = field_entry_dialog(Enum.named('video_mode').valued(
            *video_keys), value=video_keys[0])
    try:
        if valid:
            return video_mode_map[response]
    except:
        raise ValueError, 'No video mode matching: %s' % response


def select_video_caps():
    video_modes = GstVideoSourceManager.get_available_video_modes(format_='YUY2')
    selected_mode = select_video_mode(video_modes)
    if selected_mode:
        return selected_mode['device'], GstVideoSourceManager.get_caps_string(selected_mode)
    else:
        return None


def select_video_source():
    result = select_video_caps()    
    if result is None:
        return None
    device, caps_str = result
    video_source = GstVideoSourceManager.get_video_source()
    device_key, devices = GstVideoSourceManager.get_video_source_configs()
    video_source.set_property(device_key, device)
    filtered_input = FilteredInput('filtered_input', caps_str, video_source)
    return filtered_input


if __name__ == '__main__':
    pipeline = gst.Pipeline()
    video_sink = gst.element_factory_make('autovideosink', 'video_sink')
    video_source = select_video_source()
    pipeline.add(video_sink, video_source)
    video_source.link(video_sink)
    pipeline.set_state(gst.STATE_PLAYING)
    glib.MainLoop().run()
