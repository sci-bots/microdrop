"""
Copyright 2011 Ryan Fobel

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
import gobject
import os
import math
import time
import logging
from StringIO import StringIO
from contextlib import closing
import re
from copy import deepcopy

import numpy as np
import gtk
from path import path

import protocol
from protocol import Protocol
from utility import is_float, is_int
from utility.gui import textentry_validate
from utility.pygtkhelpers_combined_fields import CombinedFields, CombinedRow,\
        RowFields
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, PluginGlobals, ScheduleRequest, emit_signal
from gui.textbuffer_with_undo import UndoableBuffer
from app_context import get_app


class ProtocolGridView(CombinedFields):
    def __init__(self, forms, enabled_attrs, *args, **kwargs):
        super(ProtocolGridView, self).__init__(forms, enabled_attrs, *args,
                **kwargs)
        self.connect('row-changed', self.on_row_changed)
        self.connect('rows-changed', self.on_rows_changed)
        self.connect('selection-changed', self.on_selection_changed)

    def _on_step_options_changed(self, form_name, step_number):
        observers = ExtensionPoint(IPlugin)
        # Get the instance of the specified plugin
        service = observers.service(form_name)
        # Get the step option values from the plugin instance
        attrs = service.get_step_values(step_number=step_number)
        self._update_fields_step(form_name, step_number, attrs)
        logging.debug('[ProtocolGridView] _on_step_options_changed(): '\
                'plugin_name=%s step_number=%s attrs=%s' % (form_name,
                        step_number, attrs))

    def _get_popup_menu(self, item, column_title, value, row_ids, menu_items=None):
        if menu_items is None:
            # Use list of tuples (menu label, callback) rather than a dict to
            # allow ordering.
            menu_items = []
        def request_field_filter(*args, **kwargs):
            from .field_filter_controller import FieldFilterController

            ffc = FieldFilterController()
            response = ffc.run(self.forms, self.enabled_fields_by_form_name)
            if response == gtk.RESPONSE_OK:
                self.emit('fields-filter-request',
                        ffc.enabled_fields_by_plugin)
        # Add menu entry to select enabled fields for each plugin
        menu_items += [('Select fields...', request_field_filter)]
        return super(ProtocolGridView, self)._get_popup_menu(item, column_title, value,
                row_ids, menu_items)

    def on_row_changed(self, list_, row_id, row, field_name, value):
        for form_name, uuid_code in self.uuid_mapping.iteritems():
            field_set_prefix = self.field_set_prefix % uuid_code
            if field_name.startswith(field_set_prefix):
                form_step = row.get_fields_step(form_name)
                observers = ExtensionPoint(IPlugin)
                service = observers.service(form_name)
                service.set_step_values(form_step.attrs, step_number=row_id)

    def on_rows_changed(self, list_, row_ids, rows, attr):
        app = get_app()
        for step_number, step in [(i, self[i]) for i in row_ids]:
            for form_name, uuid_code in self.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                if attr.startswith(field_set_prefix):
                    form_step = step.get_fields_step(form_name)
                    observers = ExtensionPoint(IPlugin)
                    service = observers.service(form_name)
                    service.set_step_values(form_step.attrs, step_number=step_number)

    def on_selection_changed(self, grid_view):
        selection = self.get_selection()
        model, rows = selection.get_selected_rows()
        if not rows:
            return
        row_ids = zip(*rows)[0]
        logging.debug('[CombinedFields] selection changed: %s %s' % (selection, row_ids))
        if len(row_ids) == 1:
            # A single row is selected
            selected_row_id = row_ids[0]
            app = get_app()
            if selected_row_id != app.protocol.current_step_number:
                logging.debug('[CombinedFields] selected_row_id=%d' % selected_row_id)
                app.protocol.goto_step(selected_row_id)
                emit_signal('on_step_run')


PluginGlobals.push_env('microdrop')

class ProtocolGridController(SingletonPlugin):
    implements(IPlugin)
    
    def __init__(self):
        self.name = "microdrop.gui.protocol_grid_controller"
        self.builder = None
        self.widget = None
        self._enabled_fields = None
        # e.g., 'wheelerlab.dmf_control_board_1.2':\
                #set(['duration', 'voltage'])}

    @property
    def enabled_fields(self):
        return self._enabled_fields

    @enabled_fields.setter
    def enabled_fields(self, data):
        self._enabled_fields = deepcopy(data)
        self.update_grid()

    def on_plugin_enable(self):
        app = get_app()
        self.parent = app.builder.get_object("vbox2")
        self.window = gtk.ScrolledWindow()
        self.window.show_all()
        self.parent.add(self.window)
        
    def test(self, *args, **kwargs):
        print 'args=%s, kwargs=%s' % (args, kwargs)
        print 'attrs=%s' % args[1].attrs

    def on_step_options_swapped(self, plugin, step_number):
        self.update_grid()
        self.select_current_step()

    def on_step_options_changed(self, plugin, step_number):
        if self.widget is None:
            return
        self.widget._on_step_options_changed(plugin, step_number)

    def on_protocol_swapped(self, old_protocol, protocol):
        self.on_protocol_created(protocol)

    def on_protocol_created(self, protocol):
        self.update_grid()

    def set_fields_filter(self, combined_fields, enabled_fields_by_plugin):
        self.enabled_fields = enabled_fields_by_plugin
        logging.debug('[ProtocolGridController] set_fields_filter: %s' % self.enabled_fields)
        self.update_grid()

    def update_grid(self):
        app = get_app()
        if not app.protocol:
            return 
        logging.debug('[ProtocolGridController] on_step_run():')
        logging.debug('[ProtocolGridController]   plugin_fields=%s' % app.protocol.plugin_fields)
        forms = emit_signal('get_step_form_class')

        steps = app.protocol.steps
        logging.debug('[ProtocolGridController]   forms=%s steps=%s' % (forms, steps))
            
        if self.enabled_fields is None:
            self.enabled_fields = dict([(form_name,
                    set(form.field_schema_mapping.keys()))
                            for form_name, form in forms.items()])
        # The step ID column can be hidden by changing show_ids to False
        combined_fields = ProtocolGridView(forms, self.enabled_fields, show_ids=True)
        combined_fields.connect('fields-filter-request', self.set_fields_filter)

        for i, step in enumerate(steps):
            values = emit_signal('get_step_values', [i])
            logging.debug('[ProtocolGridController]   Step[%d]=%s values=%s' % (i, step, values))

            attributes = dict()
            for form_name, form in combined_fields.forms.iteritems():
                attr_values = values[form_name]
                logging.debug('[CombinedRow] attr_values=%s' % attr_values)
                attributes[form_name] = RowFields(**attr_values)
            c = CombinedRow(combined_fields, attributes=attributes)
            combined_fields.append(c)
        if self.widget:
            self.window.remove(self.widget)
            del self.widget
        self.widget = combined_fields
        self.widget.show_all()
        self.window.add(self.widget)

    def select_current_step(self): 
        app = get_app()
        s = self.widget.get_selection()
        model, rows = s.get_selected_rows()
        if rows:
            selected_row_id = rows[0][0]
        else:
            selected_row_id = -1
        if selected_row_id != app.protocol.current_step_number:
            s.select_path(app.protocol.current_step_number)
        self.widget.show_all()

    def get_schedule_requests(self, function_name):
        """

        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.main_window_controller', self.name)]
        return []


PluginGlobals.pop_env()
