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
from functools import partial

import gtk
from path import path
from pygtkhelpers.forms import FormView
from pygtkhelpers.proxy import proxy_for

from app_context import get_app


class FormViewDialog(object):
    def __init__(self, title=None):
        builder = gtk.Builder()
        builder.add_from_file(path('utility').joinpath('gui', 'glade',
                'form_view_dialog.glade'))
        self.window = builder.get_object('form_view_dialog')
        self.vbox_form = builder.get_object('vbox_form')
        if title:
            self.window.set_title(title)

    def clear_form(self):
        self.vbox_form.foreach(lambda x: self.vbox_form.remove(x))

    def run(self, form, values=None):
        FormView.schema_type = form
        form_view = FormView()
        for name, field in form_view.form.fields.items():
            proxy = proxy_for(field.widget)
            value = values.get(name, field.element.default_value)
            proxy.set_widget_value(value)
            field.widget.set_activates_default(gtk.TRUE)
        self.clear_form()
        self.vbox_form.pack_start(form_view.widget)
        self.window.set_default_response(gtk.RESPONSE_OK)
        self.window.set_position(gtk.WIN_POS_CENTER_ON_PARENT)        
        self.window.set_transient_for(get_app().main_window_controller.view)
        self.window.show_all()
        response = self.window.run()
        self.window.hide()
        logging.debug('[FormViewDialog] response=%s value=%s'\
                % (response, proxy.get_widget_value()))
        return (response == 0), dict([(name, f.element.value)
                for name, f in form_view.form.fields.items()])
