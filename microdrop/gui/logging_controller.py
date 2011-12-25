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

from plugin_manager import SingletonPlugin, implements, ILoggingPlugin, IPlugin, PluginGlobals


PluginGlobals.push_env('microdrop')


class LoggingController(SingletonPlugin):
    implements(IPlugin)
    implements(ILoggingPlugin)
        
    def __init__(self):
        self.name = "microdrop.gui.logging_controller"

    def on_app_init(self, app):
        self.app = app

    def _default_handler(self, record):
        pass

    def on_debug(self, record):
        self._default_handler(record)

    def on_info(self, record):
        self._default_handler(record)

    def on_warning(self, record):
        self.app.main_window_controller.warning(record.message)

    def on_error(self, record):
        self.app.main_window_controller.error(record.message)

    def on_critical(self, record):
        self.app.main_window_controller.error(record.message)


PluginGlobals.pop_env()
