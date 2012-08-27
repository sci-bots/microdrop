from pprint import pprint

from gst_video_source_caps_query import GstVideoSourceManager

from utility.pygtkhelpers_widgets import Enum, Form
from utility.gui import field_entry_dialog
from utility.gui.form_view_dialog import FormViewDialog


def select_video_mode(video_modes):
    format_cap = lambda c: '[%s] ' % c['device'][:20]\
            + '%(width)4d x%(height)4d %(framerate)3dfps (%(fourcc)s)' % c
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
    return GstVideoSourceManager.get_caps_string(select_video_mode(video_modes))


if __name__ == '__main__':
    print select_video_caps()    
