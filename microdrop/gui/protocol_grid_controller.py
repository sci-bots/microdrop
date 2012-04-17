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
import yaml
import gobject
from path import path

import protocol
from protocol import Protocol
from utility import is_float, is_int
from utility.gui import textentry_validate, register_shortcuts
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
        if hasattr(service, 'get_step_values'):
            # Get the step option values from the plugin instance
            attrs = service.get_step_values(step_number=step_number)
            self._update_row_fields(form_name, step_number, attrs)
            logging.debug('[ProtocolGridView] _on_step_options_changed(): '\
                    'plugin_name=%s step_number=%s attrs=%s' % (form_name,
                            step_number, attrs))

    def _get_popup_menu(self, item, column_title, value, row_ids, menu_items=None):
        app = get_app()
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
        # Add seperator
        menu_items += [(None, None)]
        menu_items += [('Insert', lambda x: app.protocol.insert_step())]
        menu_items += [('Delete', self.delete_rows)]
        menu_items += [('Cut', self.cut_rows)]
        menu_items += [('Copy', self.copy_rows)]
        menu_items += [('Paste before', self.paste_rows_before)]
        menu_items += [('Paste after', self.paste_rows_after)]
        # Add seperator
        menu_items += [(None, None)]

        # Uncomment lines below to add menu item for running pudb
        #def run_pudb(*args, **kwargs):
            #import pudb; pudb.set_trace()
        #menu_items += [('Run pudb...', run_pudb)]

        return super(ProtocolGridView, self)._get_popup_menu(item, column_title, value,
                row_ids, menu_items)

    def paste_rows_before(self, *args, **kwargs):
        app = get_app()
        app.paste_steps(app.protocol.current_step_number)

    def paste_rows_after(self, *args, **kwargs):
        app = get_app()
        app.paste_steps()

    def copy_rows(self, *args, **kwargs):
        app = get_app()
        app.copy_steps(self.selected_ids)

    def delete_rows(self, *args, **kwargs):
        app = get_app()
        app.delete_steps(self.selected_ids)

    def cut_rows(self, *args, **kwargs):
        app = get_app()
        app.cut_steps(self.selected_ids)

    def on_row_changed(self, list_, row_id, row, field_name, value):
        for form_name, uuid_code in self.uuid_mapping.iteritems():
            field_set_prefix = self.field_set_prefix % uuid_code
            if field_name.startswith(field_set_prefix):
                form_step = row.get_row_fields(form_name)
                observers = ExtensionPoint(IPlugin)
                service = observers.service(form_name)
                service.set_step_values(form_step.attrs, step_number=row_id)

    def on_rows_changed(self, list_, row_ids, rows, attr):
        app = get_app()
        for step_number, step in [(i, self[i]) for i in row_ids]:
            for form_name, uuid_code in self.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                if attr.startswith(field_set_prefix):
                    form_step = step.get_row_fields(form_name)
                    observers = ExtensionPoint(IPlugin)
                    service = observers.service(form_name)
                    service.set_step_values(form_step.attrs, step_number=step_number)

    def on_selection_changed(self, grid_view):
        logging.debug('[CombinedFields] selection changed')
        #import pudb; pudb.set_trace()
        selected_row_ids = self.selected_ids
        if selected_row_ids:
            # A single row is selected
            app = get_app()
            selected_row_id = selected_row_ids[0]
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
        self.select_current_step()

    def on_step_options_changed(self, plugin, step_number):
        if self.widget is None:
            return
        self.widget._on_step_options_changed(plugin, step_number)

    def on_protocol_swapped(self, old_protocol, protocol):
        self.on_protocol_created(protocol)

    def on_protocol_created(self, protocol):
        self.update_grid(protocol)

    def set_fields_filter(self, combined_fields, enabled_fields_by_plugin):
        app = get_app()
        self.enabled_fields = enabled_fields_by_plugin
        self.widget.selected_ids = [app.protocol.current_step_number]
        logging.debug('[ProtocolGridController] set_fields_filter: %s' % self.enabled_fields)

    def update_grid(self, protocol=None):
        app = get_app()
        if protocol is None:
            protocol = app.protocol
        if protocol is None:
            return
        logging.debug('[ProtocolGridController] on_step_run():')
        logging.debug('[ProtocolGridController]   plugin_fields=%s' % protocol.plugin_fields)
        forms = emit_signal('get_step_form_class')

        steps = protocol.steps
        logging.debug('[ProtocolGridController]   forms=%s steps=%s' % (forms, steps))
            
        if self.enabled_fields is None:
            # Assign directly to _enabled_fields to avoid recursive call into
            # update_grid()
            self._enabled_fields = dict([(form_name,
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
        if self.widget:
            self.widget.show_all()
            self.selected_ids = [app.protocol.current_step_number]
            self._register_shortcuts()
            self.window.add(self.widget)

    def _register_shortcuts(self):
        class FocusWrapper(object):
            '''
            This class allows for a function to be executed, restoring the
            focused state of the protocol grid view if necessary.
            '''
            def __init__(self, controller, func):
                self.controller = controller
                self.func = func

            def __call__(self):
                focused = self.controller.widget.has_focus()
                self.func()
                if focused:
                    self.controller.widget.grab_focus()

        app = get_app()
        view = app.main_window_controller.view
        shortcuts = {
            '<Control>c': self.widget.copy_rows,
            '<Control>x': FocusWrapper(self, self.widget.cut_rows),
            'Delete': FocusWrapper(self, self.widget.delete_rows),
            '<Control>v': FocusWrapper(self, self.widget.paste_rows_after),
            '<Control><Shift>v': FocusWrapper(self,
                    self.widget.paste_rows_before),
            '<Control><Shift>i': FocusWrapper(self,
                    lambda: app.protocol.insert_step()),
        }
        register_shortcuts(view, shortcuts, enabled_widgets=[self.widget])

    def select_current_step(self): 
        if self.widget is None:
            return
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

    def on_step_created(self, step_number):
        app = get_app()
        logging.debug('[ProtocolGridController] on_step_created[%d]', step_number)
        self.update_grid()
        self.widget.selected_ids = [app.protocol.current_step_number]

    def on_step_swapped(self, original_step_number, step_number):
        self.widget.selected_ids = [step_number]
        logging.debug('[ProtocolGridController] on_step_swapped[%d->%d]',
                original_step_number, step_number)

    def on_step_removed(self, step_number, step):
        app = get_app()
        logging.debug('[ProtocolGridController] on_step_removed[%d]',
                step_number)
        self.update_grid()
        if app.protocol.steps:
            self.widget.selected_ids = [min(len(app.protocol.steps) - 1,
                    app.protocol.current_step_number)]


PluginGlobals.pop_env()
