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
import uuid
import re

import numpy as np
import gtk
from path import path
from flatland import Form, Dict, String, Integer, Boolean, Float
from flatland.validation import ValueAtLeast, ValueAtMost
from pygtkhelpers.ui.objectlist import ObjectList
from pygtkhelpers.ui.objectlist.column import Column

import protocol
from protocol import Protocol
from utility import check_textentry, is_float, is_int
from utility.gui import register_shortcuts
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, emit_signal, PluginGlobals
from gui.textbuffer_with_undo import UndoableBuffer
from app_context import get_app


class FieldsStep(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self):
        return self.__dict__

    def __getattr__(self, name):
        if not name in dir(self):
            setattr(self, name, None)
        return object.__getattribute__(self, name)

    @property
    def attrs(self):
        return self.__dict__


class CombinedFields(ObjectList):
    field_set_prefix = '_%s__'

    def __init__(self, forms, *args, **kwargs):
        self.first_selected = True
        self.forms = forms
        self.uuid_mapping = dict([(name, uuid.uuid4().get_hex()[:10]) for name in forms])
        self.uuid_reverse_mapping = dict([(v, k) for k, v in self.uuid_mapping.items()])
        self._columns = []
        for form_name, form in self.forms.iteritems():
            for f in form.field_schema:
                title = re.sub(r'_', ' ', f.name).capitalize()
                name = '%s%s'\
                    % (self.field_set_prefix % self.uuid_mapping[form_name],
                        f.name)
                val_type = type(f(0).value)
                d = dict(attr=name, type=val_type, title=title, resizable=True, editable=True, sorted=False)
                if val_type == bool:
                    # Use checkbox for boolean cells
                    d['use_checkbox'] = True
                elif val_type == int:
                    # Use spinner for integer cells
                    d['use_spin'] = True
                logging.debug('[CombinedFields] column attrs=%s' % d)
                self._columns.append(Column(**d))
        logging.debug('[CombinedFields] columns=%s' % self._columns)
        super(CombinedFields, self).__init__(self._columns, *args, **kwargs)
        s = self.get_selection()
        s.set_mode(gtk.SELECTION_MULTIPLE)
        self.connect('item-changed', self._on_item_changed)
        self.connect('selection-changed', self._on_selection_changed)
        self.connect('item-right-clicked', self._on_right_clicked)
        app = get_app()
        app.combined_fields = self

    def _on_button_press_event(self, treeview, event):
        item_spec = self.get_path_at_pos(int(event.x), int(event.y))
        if item_spec is not None:
            # clicked on an actual cell
            path, col, rx, ry = item_spec
            signal_map = {
                (1, gtk.gdk.BUTTON_PRESS): 'item-left-clicked',
                (3, gtk.gdk.BUTTON_PRESS): 'item-right-clicked',
                (2, gtk.gdk.BUTTON_PRESS): 'item-middle-clicked',
                (1, gtk.gdk._2BUTTON_PRESS): 'item-double-clicked',
            }
            signal_name = signal_map.get((event.button, event.type))
            if not signal_name == 'item-right-clicked':
                self._emit_for_path(path, event)
            else:
                item = self._object_at_sort_path(path)
                return self._on_right_clicked(self, item, event, col.get_title())

    def _on_right_clicked(self, list_, item, event, column_title):
        title_map = dict([(c.title, c.attr) for c in self.columns])
        attr = title_map.get(column_title)
        selection = self.get_selection()
        model, rows = selection.get_selected_rows()
        row_ids = zip(*rows)[0]
        value = getattr(item, attr)
        for i in row_ids:
            setattr(self[i], attr, value)
        print 'Right click: column_title=%s column_attr=%s value=%s'\
            % (column_title, attr, value)
        self._on_multiple_changed(attr)
        return True

    def _on_step_options_changed(self, plugin_name, step_number):
        '''
        -get step values for (plugin, step_number)
        -set affected objectlist item attributes based on step values
        '''
        if plugin_name not in self.forms\
            or step_number >= len(self):
            return
        app = get_app()
        step = app.protocol.current_step()
        combined_step = self[step_number]
        form_step = combined_step.get_fields_step(plugin_name)
        observers = ExtensionPoint(IPlugin)
        # Get the instance of the specified plugin
        service = observers.service(plugin_name)
        # Get the step option values from the plugin instance
        attrs = service.get_step_values(step_number=step_number)
        for attr, value in attrs.items():
            setattr(form_step, attr, value)
        #import pudb; pudb.set_trace()
        self.update(combined_step)
        print '[CombinedFields] _on_step_options_changed(): '\
                'plugin_name=%s step_number=%s attrs=%s' % (plugin_name, step_number, attrs)
        #logging.info('[CombinedFields] _on_step_options_changed(): '\
                #'plugin_name=%s step_number=%s attrs=%s' % (plugin_name, step_number, attrs))

    def _on_multiple_changed(self, attr, **kwargs):
        selection = self.get_selection()
        model, rows = selection.get_selected_rows()
        row_ids = zip(*rows)[0]
        logging.info('[CombinedFields] _on_multiple_changed(): attr=%s selected_rows=%s' % (attr, row_ids))
        app = get_app()
        for step_number, step in [(i, self[i]) for i in row_ids]:
            for form_name, uuid_code in self.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                if attr.startswith(field_set_prefix):
                    form_step = step.get_fields_step(form_name)
                    observers = ExtensionPoint(IPlugin)
                    service = observers.service(form_name)
                    service.set_step_values(form_step.attrs, step_number=step_number)

    def _on_selection_changed(self, selection, *args, **kwargs):
        model, rows = selection.get_selected_rows()
        row_ids = zip(*rows)[0]
        logging.info('[CombinedFields] selection changed: %s %s' % (selection, row_ids))
        if len(row_ids) == 1:
            # A single row is selected
            selected_row_id = row_ids[0]
            app = get_app()
            options = app.protocol.get_data('microdrop.gui.protocol_controller')
            if selected_row_id != options.current_step_number:
                logging.info('[CombinedFields] selected_row_id=%d' % selected_row_id)
                app.protocol.goto_step(selected_row_id)
                emit_signal('on_protocol_options_changed', interface=IPlugin)
                #emit_signal("on_protocol_update", None)

    def _on_item_changed(self, widget, step_data, name, value, **kwargs):
        logging.info('[CombinedFields] _on_item_changed(): name=%s value=%s' % (name, value))
        for form_name, uuid_code in self.uuid_mapping.iteritems():
            field_set_prefix = self.field_set_prefix % uuid_code
            step_number = [r for r in self].index(step_data)
            if name.startswith(field_set_prefix):
                form_step = step_data.get_fields_step(form_name)
                #print '%s, %s, %s attrs=%s' % (form_name, uuid_code, name, form_step.attrs)
                observers = ExtensionPoint(IPlugin)
                service = observers.service(form_name)
                service.set_step_values(form_step.attrs, step_number=step_number)


class CombinedStep(object):
    field_set_prefix = '_%s__'

    def __init__(self, combined_fields, step_id=None, attributes=None):
        self.combined_fields = combined_fields

        if attributes is None:
            self.attributes = dict()
            for form_name, form in combined_fields.forms.iteritems():
                temp = form.from_defaults()
                attr_values = dict([(k, v.value) for k, v in temp.iteritems()])
                logging.debug('[CombinedStep] attr_values=%s' % attr_values)
                self.attributes[form_name] = FieldsStep(**attr_values)
        else:
            self.attributes = attributes

    def get_fields_step(self, form_name):
        return self.attributes[form_name]
    
    def decode_form_name(self, mangled_form_name):
        return mangled_form_name.split('__')[-1]
    
    def set_step(self, step_id):
        if 'DefaultFields' in self.combined_fields.forms and step_id is not None:
            self.attributes['DefaultFields'].step = step_id

    def __getattr__(self, name):
        logging.debug('[CombinedStep] name=%r' % name)
        if not name in ['attributes', 'combined_fields']:
            for form_name, uuid_code in self.combined_fields.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                logging.debug('name=%s, field_set_prefix=%s' % (name, field_set_prefix))
                if name.startswith(field_set_prefix):
                    return getattr(self.attributes[form_name], name[len(field_set_prefix):])
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        logging.debug('[CombinedStep] set %s=%s' % (name, value))
        if not name in ['attributes', 'combined_fields']:
            for form_name, uuid_code in self.combined_fields.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                if name.startswith(field_set_prefix):
                    setattr(self.attributes[form_name], name[len(field_set_prefix):], value)
        self.__dict__[name] = value
        logging.debug(self.__dict__[name])

    def __str__(self):
        return '<CombinedStep attributes=%s>' % [(k, v.attrs) for k, v in self.attributes.iteritems()]


PluginGlobals.push_env('microdrop')


class ProtocolGridController(SingletonPlugin):
    implements(IPlugin)
    
    def __init__(self):
        self.name = "microdrop.gui.protocol_grid_controller"
        self.builder = None
        self.widget = None

    def on_app_init(self):
        app = get_app()
        self.parent = app.builder.get_object("vbox2")
        
    def test(self, *args, **kwargs):
        print 'args=%s, kwargs=%s' % (args, kwargs)
        print 'attrs=%s' % args[1].attrs

    def on_step_options_changed(self, plugin, step_number):
        if self.widget is None:
            return
        self.widget._on_step_options_changed(plugin, step_number)

    def on_protocol_update(self, data=None):
        """
        Handler called whenever the current step options change.
        """
        app = get_app()
        forms = emit_signal('get_step_form_class', by_observer=True)

        steps = app.protocol.steps
        logging.debug('[ProtocolGridController] on_protocol_update():')
        logging.debug('[ProtocolGridController]   plugin_fields=%s' % app.protocol.plugin_fields)
        logging.debug('[ProtocolGridController]   forms=%s steps=%s' % (forms, steps))
            
        combined_fields = CombinedFields(forms)

        for i, step in enumerate(steps):
            values = emit_signal('get_step_values', [i], by_observer=True)
            logging.debug('[ProtocolGridController]   Step[%d]=%s values=%s' % (i, step, values))

            attributes = dict()
            for form_name, form in combined_fields.forms.iteritems():
                attr_values = values[form_name]
                logging.debug('[CombinedStep] attr_values=%s' % attr_values)
                attributes[form_name] = FieldsStep(**attr_values)
            c = CombinedStep(combined_fields, attributes=attributes)
            combined_fields.append(c)
        if self.widget:
            self.parent.remove(self.widget)
            del self.widget
        self.widget = combined_fields
        s = self.widget.get_selection()
        model, rows = s.get_selected_rows()
        if rows:
            selected_row_id = rows[0][0]
        else:
            selected_row_id = -1
        protocol_options = app.protocol.get_data('microdrop.gui.protocol_controller')
        if selected_row_id != protocol_options.current_step_number:
            s.select_path(protocol_options.current_step_number)
        self.widget.show_all()
        self.parent.add(self.widget)


PluginGlobals.pop_env()
