"""
Copyright 2011 Ryan Fobel and Christian Fobel

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

from datetime import datetime

from path import path

try:
    from plugins.video_recorder import VideoRecorder
    from plugin_manager import IPlugin, SingletonPlugin, implements


    class VideoRecorderPlugin(SingletonPlugin):
        implements(IPlugin)
        
        def __init__(self):
            self.video_recorder = VideoRecorder()
            self.video_path = None

        def on_app_init(self, app):
            self.app = app
        
        def on_protocol_pause(self):
            """
            Handler called when a protocol is paused.
            """
            self.video_recorder.stop()
        
        def on_protocol_run(self):
            log_dir = path(self.app.experiment_log.get_log_path())
            self.video_path = log_dir.joinpath('%s.avi' % log_dir.name)
            self.app.experiment_log.add_data({"video": self.video_path, "video start": datetime.now()})
            self.video_recorder.record(self.video_path)
except (ImportError, ), why:
    print 'VideoRecorderPlugin disabled: %s' % why
