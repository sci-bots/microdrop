"""
Copyright 2011-12 Ryan Fobel and Christian Fobel

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

import os
from copy import deepcopy
import re

import gtk
from path_helpers import path
from pygtkhelpers.proxy import proxy_for
from pygtkhelpers.forms import FormView
from flatland.schema import Form

from app_context import get_app
from ..logger import logger
from plugin_manager import (IPlugin, SingletonPlugin, implements, IVideoPlugin,
                            ExtensionPoint, emit_signal)
from .. import glade_path


class AppOptionsController:
    def __init__(self):
        app = get_app()
        builder = gtk.Builder()
        builder.add_from_file(glade_path()
                              .joinpath("app_options_dialog.glade"))
        self.dialog = builder.get_object("app_options_dialog")
        self.frame_core_plugins = builder.get_object("frame_core_plugins")
        self.core_plugins_vbox = builder.get_object("core_plugins_vbox")
        self.plugin_form_vbox = builder.get_object("plugin_form_vbox")
        self.dialog.set_transient_for(app.main_window_controller.view)

        self.btn_ok = builder.get_object('btn_ok')
        self.btn_apply = builder.get_object('btn_apply')
        self.btn_cancel = builder.get_object('btn_cancel')
        self.form_views = {}
        self.no_gui_names = set()

        builder.connect_signals(self)
        self.builder = builder

    def _get_app_values(self, plugin_name):
        observers = ExtensionPoint(IPlugin)
        service = observers.service(plugin_name)
        if not hasattr(service, 'get_app_values'):
            values = dict([(k, v.value) for k,v in self.forms[plugin_name].from_defaults().iteritems()])
        else:
            values = service.get_app_values()
        if not values:
            return {}
        else:
            return values

    def remove_plugin_form(self, x):
        if x != self.frame_core_plugins:
            self.plugin_form_vbox.remove(x)

    def clear_form(self):
        self.plugin_form_vbox.foreach(lambda x: self.remove_plugin_form(x))

    def run(self):
        # Empty plugin form vbox
        # Get list of app option forms
        self.forms = emit_signal('get_app_form_class')
        self.form_views = {}
        self.clear_form()
        app = get_app()
        self.no_gui_names = set()
        for name, form in self.forms.iteritems():
            # For each form, generate a pygtkhelpers formview and append the view
            # onto the end of the plugin vbox
            
            if form is None:
                schema_entries = []
            else:
                # Only include fields that do not have show_in_gui set to False in
                # 'properties' dictionary
                schema_entries = [f for f in form.field_schema\
                        if f.properties.get('show_in_gui', True)]
            if not schema_entries:
                self.no_gui_names.add(name)
                continue
            gui_form = Form.of(*schema_entries)
            FormView.schema_type = gui_form
            self.form_views[name] = FormView()
            if name in app.core_plugins:
                self.core_plugins_vbox.pack_start(self.form_views[name].widget)
                self.frame_core_plugins.show()
            else:
                expander = gtk.Expander()
                expander.set_label(name)
                expander.set_expanded(True)
                expander.add(self.form_views[name].widget)
                self.plugin_form_vbox.pack_start(expander)
        for form_name, form in self.forms.iteritems():
            if form_name in self.no_gui_names:
                continue
            form_view = self.form_views[form_name]
            values = self._get_app_values(form_name)
            fields = set(values.keys()).intersection(form_view.form.fields)
            for field in fields:
                value = values[field]
                proxy = proxy_for(getattr(form_view, field))
                proxy.set_widget_value(value)
                form_field = form_view.form.fields[field]
                form_field.label_widget.set_text(
                        re.sub(r'_',  ' ', field).title())

        self.dialog.show_all()

        response = self.dialog.run()
        if response == gtk.RESPONSE_OK:
            self.apply()
        elif response == gtk.RESPONSE_CANCEL:
            pass
        self.dialog.hide()
        return response

    def on_btn_apply_clicked(self, widget, data=None):
        self.apply()

    def apply(self):
        for name, form_view in self.form_views.iteritems():
            fields = form_view.form.fields.keys()
            attrs = {}
            for field in fields:
                if form_view.form.fields[field].element.validate():
                    attrs[field] = form_view.form.fields[field].element.value
                else:
                    logger.error('Failed to set %s value for %s' % (field, name))
            if attrs:
                observers = ExtensionPoint(IPlugin)
                service = observers.service(name)
                service.set_app_values(attrs)
