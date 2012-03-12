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

import numpy as np
import gtk
from path import path
from flatland import Form, Dict, String, Integer, Boolean, Float
from flatland.validation import ValueAtLeast, ValueAtMost
from pygtkhelpers.ui.objectlist import ObjectList
from pygtkhelpers.ui.objectlist.column import Column

import protocol
from protocol import Protocol
from utility import is_float, is_int
from utility.gui import textentry_validate
import utility.uuid_minimal as uuid
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
        self._full_field_to_field_def = {}
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
                self._full_field_to_field_def[name] = f
        logging.debug('[CombinedFields] columns=%s' % self._columns)
        super(CombinedFields, self).__init__(self._columns, *args, **kwargs)
        s = self.get_selection()
        s.set_mode(gtk.SELECTION_MULTIPLE)
        self.connect('item-changed', self._on_item_changed)
        self.connect('selection-changed', self._on_selection_changed)
        self.connect('item-right-clicked', self._on_right_clicked)
        app = get_app()
        app.combined_fields = self

    def _set_rows_attr(self, row_ids, column_title, value, prompt=False):
        title_map = dict([(c.title, c.attr) for c in self.columns])
        attr = title_map.get(column_title)
        if prompt:
            from protocol_grid_dialog import ProtocolGridDialog
            from flatland import Form

            Fields = Form.of(self._full_field_to_field_def[attr])

            temp = ProtocolGridDialog()
            response_ok, value = temp.run(Fields, value)
            if not response_ok:
                return
        else:
            title_map = dict([(c.title, c.attr) for c in self.columns])
            attr = title_map.get(column_title)

        for i in row_ids:
            setattr(self[i], attr, value)
        logging.debug('Set rows attr: row_ids=%s column_title=%s value=%s'\
            % (row_ids, column_title, value))
        self._on_multiple_changed(attr)
        return True

    def _deselect_all(self, *args, **kwargs):
        s = self.get_selection()
        s.unselect_all()

    def _select_all(self, *args, **kwargs):
        s = self.get_selection()
        s.select_all()

    def _invert_rows(self, row_ids):
        self._select_all()
        s = self.get_selection()
        for i in row_ids:
            s.unselect_path(i)

    def _get_popup_menu(self, item, column_title, value, row_ids):
        popup = gtk.Menu()
        def set_attr_value(*args, **kwargs):
            logging.debug('[set_attr_value] args=%s kwargs=%s' % (args, kwargs))
            self._set_rows_attr(row_ids, column_title, value)
        def set_attr(*args, **kwargs):
            logging.debug('[set_attr] args=%s kwargs=%s' % (args, kwargs))
            self._set_rows_attr(row_ids, column_title, value, prompt=True)
        def invert_rows(*args, **kwargs):
            self._invert_rows(row_ids)
        menu_items = []
        menu_items += [(gtk.MenuItem('Invert row selection'), invert_rows), ]
        if len(row_ids) < len(self):
            menu_items += [(gtk.MenuItem('Select all rows'), self._select_all), ]
        if len(row_ids) > 0:
            menu_items += [(gtk.MenuItem('Deselect all rows'), self._deselect_all), ]

        item_id = [r for r in self].index(item)
        if item_id not in row_ids:
            logging.debug('[ProtocolGridController] _on_right_clicked(): '\
                            'clicked item is not selected')
        elif len(row_ids) > 1:
            menu_items += [
                (gtk.MenuItem('''Set selected [%s] to "%s"'''\
                            % (column_title, value)), set_attr_value),
                (gtk.MenuItem('''Set selected [%s] to...''' % column_title),
                set_attr),
            ]
        for item, callback in menu_items:
            popup.add(item)
            item.connect('activate', callback)
        popup.show_all()
        return popup

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
        if not rows:
            return False
        row_ids = zip(*rows)[0]
        value = getattr(item, attr)

        self.grab_focus()
        popup = self._get_popup_menu(item, column_title, value, row_ids)
        popup.popup(None, None, None, event.button, event.time)
        del popup
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
        self.update(combined_step)
        logging.debug('[CombinedFields] _on_step_options_changed(): '\
                'plugin_name=%s step_number=%s attrs=%s' % (plugin_name, step_number, attrs))

    def _on_multiple_changed(self, attr, **kwargs):
        selection = self.get_selection()
        model, rows = selection.get_selected_rows()
        row_ids = zip(*rows)[0]
        logging.debug('[CombinedFields] _on_multiple_changed(): attr=%s selected_rows=%s' % (attr, row_ids))
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

    def _on_item_changed(self, widget, step_data, name, value, **kwargs):
        logging.debug('[CombinedFields] _on_item_changed(): name=%s value=%s' % (name, value))
        for form_name, uuid_code in self.uuid_mapping.iteritems():
            field_set_prefix = self.field_set_prefix % uuid_code
            step_number = [r for r in self].index(step_data)
            if name.startswith(field_set_prefix):
                form_step = step_data.get_fields_step(form_name)
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
        self.window = gtk.ScrolledWindow()
        self.window.show_all()
        self.parent.add(self.window)
        
    def test(self, *args, **kwargs):
        print 'args=%s, kwargs=%s' % (args, kwargs)
        print 'attrs=%s' % args[1].attrs

    def on_step_options_changed(self, plugin, step_number):
        if self.widget is None:
            return
        self.widget._on_step_options_changed(plugin, step_number)

    def on_step_run(self):
        """
        Handler called whenever a step is executed.

        Returns:
            True if the step should be run again (e.g., if a feedback
            plugin wants to signal that the step should be repeated)
        """
        app = get_app()
        logging.debug('[ProtocolGridController] on_step_run():')
        logging.debug('[ProtocolGridController]   plugin_fields=%s' % app.protocol.plugin_fields)
        forms = emit_signal('get_step_form_class')

        steps = app.protocol.steps
        logging.debug('[ProtocolGridController]   forms=%s steps=%s' % (forms, steps))
            
        combined_fields = CombinedFields(forms)

        for i, step in enumerate(steps):
            values = emit_signal('get_step_values', [i])
            logging.debug('[ProtocolGridController]   Step[%d]=%s values=%s' % (i, step, values))

            attributes = dict()
            for form_name, form in combined_fields.forms.iteritems():
                attr_values = values[form_name]
                logging.debug('[CombinedStep] attr_values=%s' % attr_values)
                attributes[form_name] = FieldsStep(**attr_values)
            c = CombinedStep(combined_fields, attributes=attributes)
            combined_fields.append(c)
        if self.widget:
            self.window.remove(self.widget)
            del self.widget
        self.widget = combined_fields
        s = self.widget.get_selection()
        model, rows = s.get_selected_rows()
        if rows:
            selected_row_id = rows[0][0]
        else:
            selected_row_id = -1
        if selected_row_id != app.protocol.current_step_number:
            s.select_path(app.protocol.current_step_number)
        self.widget.show_all()
        self.window.add(self.widget)


PluginGlobals.pop_env()
