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
import logging

import gtk
from path import path

from plugin_manager import PluginGlobals
from app_context import get_app, plugin_manager


class ProtocolGridDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(path('gui').joinpath('glade', 'protocol_grid_dialog.glade'))
        self.window = builder.get_object('protocol_grid_dialog')
        self.vbox_form = builder.get_object('vbox_form')

    def clear_form(self):
        self.vbox_form.foreach(lambda x: self.vbox_form.remove(x))

    def run(self, form, value=None):
        from pygtkhelpers.forms import FormView
        from pygtkhelpers.proxy import proxy_for

        FormView.schema_type = form
        form_view = FormView()
        proxy = proxy_for(getattr(form_view, form_view.form.fields.keys()[0]))
        self.clear_form()
        if value:
            proxy.set_widget_value(value)
        self.vbox_form.pack_start(form_view.widget)
        self.window.show_all()
        response = self.window.run()
        self.window.hide()
        logging.debug('[ProtocolGridDialog] response=%s value=%s'\
                % (response, proxy.get_widget_value()))
        return (response == 0), proxy.get_widget_value()


if __name__ == '__main__':
    pm = PluginManagerView()
