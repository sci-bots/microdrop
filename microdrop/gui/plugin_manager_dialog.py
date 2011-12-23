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

import gtk
from path import path

from plugin_manager import PluginGlobals


class PluginController(object):
    def __init__(self, app, name, plugin_manager):
        self.app = app
        self.name = name
        self.plugin_manager = plugin_manager
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugin_class = self.e.plugin_registry[name]
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        self.box = gtk.HBox()
        self.label = gtk.Label('%s' % self.name)
        self.label.set_alignment(0, 0.5)
        self.button = gtk.Button('disabled')
        self.button.connect('clicked', self.on_button_clicked, None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_start(self.button, expand=False, fill=False, padding=5)
        self.update()
        self.box.show_all()

    def enabled(self):
        return not(self.service is None or not self.service.enabled())

    def update(self):
        if self.enabled():
            self.button.set_label('enabled')
        else:
            self.button.set_label('disabled')
        self.service = self.plugin_manager\
                        .get_service_instance(self.plugin_class)

    def toggle_enabled(self):
        if not self.enabled():
            self.plugin_manager.enable(self.app, self.name)
        else:
            self.plugin_manager.disable(self.name)
        self.update()

    def get_widget(self):
        return self.box

    def on_button_clicked(self, widget, data=None):
        self.toggle_enabled()


class PluginManagerDialog(object):
    def __init__(self, app):
        builder = gtk.Builder()
        builder.add_from_file(path('gui').joinpath('glade', 'plugin_manager_dialog.glade'))
        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        self.app = app
        self.plugin_manager = app.plugin_manager
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugins = []

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    def update(self):
        self.clear_plugin_list()
        plugin_names = self.get_plugin_names()
        del self.plugins
        self.plugins = []
        for name in plugin_names:
            p = PluginController(self.app, name, self.plugin_manager)
            self.plugins.append(p)
            self.vbox_plugins.pack_start(p.get_widget())

    def get_plugin_names(self):
        return list(self.e.plugin_registry.keys())

    def run(self):
        self.update()
        response = self.window.run()
        self.window.hide()
        enabled_plugins = [p.name for p in self.plugins if p.enabled()]
        self.app.config.set_plugins(enabled_plugins)
        self.app.config.save()
        return response


if __name__ == '__main__':
    pm = PluginManagerView()
