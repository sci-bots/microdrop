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

import time

try:
    from opencv.recorder import Recorder, cv, CVCaptureProperties


    class VideoRecorder():
        def __init__(self):
            self.recorder = None
            self.out_file = None
            self.cap = None

        def record(self, out_file):
            self.out_file = out_file
            self.cap = cv.CaptureFromCAM(-1)
            if str(self.cap).find('nil') >= 0:
                raise ValueError, 'Could not connect to camera.'
            props = CVCaptureProperties(self.cap)
            if self.recorder is not None:
                del self.recorder
            self.recorder = Recorder(self.cap, self.out_file)
            self.recorder.record()

        def stop(self):
            if self.recorder is not None:
                self.recorder.stop()
            del(self.cap)
except (ImportError, ), why:
    pass
