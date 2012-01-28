"""
Copyright 2012 Ryan Fobel and Christian Fobel

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
from app_context import get_app, plugin_manager


class DialogController(object):
    def __init__(self, name):
        self.name = name
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
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        if self.enabled():
            self.button.set_label('enabled')
        else:
            self.button.set_label('disabled')

    def toggle_enabled(self):
        if not self.enabled():
            plugin_manager.enable(self.name)
        else:
            plugin_manager.disable(self.name)
        self.update()

    def get_widget(self):
        return self.box

    def on_button_clicked(self, widget, data=None):
        self.toggle_enabled()


class ProtocolGridDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(path('gui').joinpath('glade', 'protocol_grid_dialog.glade'))
        self.window = builder.get_object('protocol_grid_dialog')
        self.vbox_form = builder.get_object('vbox_form')

    def clear_form(self):
        self.vbox_form.foreach(lambda x: self.vbox_form.remove(x))

    def run(self, form):
        from pygtkhelpers.forms import FormView
        from pygtkhelpers.proxy import proxy_for

        FormView.schema_type = form
        form_view = FormView()
        proxy = proxy_for(getattr(form_view, form_view.form.fields.keys()[0]))
        self.clear_form()
        self.vbox_form.pack_start(form_view.widget)
        self.window.show_all()
        response = self.window.run()
        self.window.hide()
        print '[ProtocolGridDialog] response=%s value=%s'\
                % (response, proxy.get_widget_value())
        return (response == 0), proxy.get_widget_value()


if __name__ == '__main__':
    pm = PluginManagerView()
