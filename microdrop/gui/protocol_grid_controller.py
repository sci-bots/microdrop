from copy import deepcopy
import json

from flatland import Form, String
from microdrop.app_context import get_app
from microdrop.plugin_helpers import AppDataController
from microdrop.plugin_manager import (ExtensionPoint,
                                      IPlugin, SingletonPlugin, implements,
                                      PluginGlobals, ScheduleRequest,
                                      emit_signal)
from microdrop_utility.gui import get_accel_group
from pygtkhelpers.ui.objectlist.combined_fields import (CombinedFields,
                                                        CombinedRow, RowFields)
import gtk

from logging_helpers import _L  #: .. versionadded:: 2.20


def _get_title(column):
    '''
    Shortcut function to lookup column title from each
    :class:`gtk.TreeViewColumn`.

    Parameters
    ----------
    column : gtk.TreeViewColumn

    Returns
    -------
    str
        Title of specified :class:`gtk.TreeViewColumn`.
    '''
    return column.get_data('pygtkhelpers::column').title


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
            _L().debug('plugin_name=%s step_number=%s attrs=%s', form_name,
                           step_number, attrs)

    def _get_popup_menu(self, item, column_title, value, row_ids,
                        menu_items=None):
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

        return super(ProtocolGridView, self)._get_popup_menu(item,
                                                             column_title,
                                                             value, row_ids,
                                                             menu_items)

    def paste_rows_before(self, *args, **kwargs):
        app = get_app()
        step_number = app.protocol_controller.protocol_state['step_number']
        app.paste_steps(step_number)

    def paste_rows_after(self, *args, **kwargs):
        app = get_app()
        step_number = app.protocol_controller.protocol_state['step_number']
        app.paste_steps(step_number + 1)

    def copy_rows(self, *args, **kwargs):
        app = get_app()
        app.copy_steps(self.selected_ids)

    def delete_rows(self, *args, **kwargs):
        app = get_app()
        app.delete_steps(self.selected_ids)

    def cut_rows(self, *args, **kwargs):
        app = get_app()
        app.cut_steps(self.selected_ids)

    def select_row(self, row):
        if row not in self.selected_ids:
            self.set_cursor(row)

    def on_row_changed(self, list_, row_id, row, field_name, value):
        for form_name, uuid_code in self.uuid_mapping.iteritems():
            field_set_prefix = self.field_set_prefix % uuid_code
            if field_name.startswith(field_set_prefix):
                form_step = row.get_row_fields(form_name)
                observers = ExtensionPoint(IPlugin)
                service = observers.service(form_name)
                try:
                    service.set_step_values(form_step.attrs,
                                            step_number=row_id)
                except ValueError:
                    _L().error('Invalid value. %s', value)
                    self._on_step_options_changed(form_name, row_id)

    def on_rows_changed(self, list_, row_ids, rows, attr):
        for step_number, step in [(i, self[i]) for i in row_ids]:
            for form_name, uuid_code in self.uuid_mapping.iteritems():
                field_set_prefix = self.field_set_prefix % uuid_code
                if attr.startswith(field_set_prefix):
                    form_step = step.get_row_fields(form_name)
                    observers = ExtensionPoint(IPlugin)
                    service = observers.service(form_name)
                    service.set_step_values(form_step.attrs,
                                            step_number=step_number)

    def on_selection_changed(self, grid_view):
        if self.selected_ids:
            logger = _L()
            app = get_app()
            step_number = app.protocol_controller.protocol_state['step_number']
            logger.debug('selected_ids=%s', self.selected_ids)
            logger.debug('step number=%d', step_number)
            if step_number not in self.selected_ids:
                app.protocol_controller.goto_step(self.selected_ids[0])


PluginGlobals.push_env('microdrop')


class ProtocolGridController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    AppFields = Form.of(String.named('column_positions')
                        .using(default='{}', optional=True,
                               properties=dict(show_in_gui=False)))

    def __init__(self):
        self.name = "microdrop.gui.protocol_grid_controller"
        self.builder = None
        self.widget = None
        self._enabled_fields = None

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
        super(ProtocolGridController, self).on_plugin_enable()

    def on_plugin_enabled(self, env, plugin):
        self.update_grid()

    def on_plugin_disabled(self, env, plugin):
        self.update_grid()

    def test(self, *args, **kwargs):
        print 'args=%s, kwargs=%s' % (args, kwargs)
        print 'attrs=%s' % args[1].attrs

    def on_step_options_changed(self, plugin, step_number):
        if self.widget is None:
            return
        self.widget._on_step_options_changed(plugin, step_number)

    def on_protocol_run(self):
        self.widget.set_sensitive(False)

    def on_protocol_pause(self):
        self.widget.set_sensitive(True)

    def on_protocol_swapped(self, old_protocol, protocol):
        self.update_grid(protocol)

    def set_fields_filter(self, combined_fields, enabled_fields_by_plugin):
        app = get_app()
        self.enabled_fields = enabled_fields_by_plugin
        step_number = app.protocol_controller.protocol_state['step_number']
        self.widget.select_row(step_number)
        _L().debug('%s', self.enabled_fields)

    def update_grid(self, protocol=None):
        app = get_app()
        if protocol is None:
            protocol = app.protocol
        if protocol is None:
            return
        _L().debug('plugin_fields=%s', protocol.plugin_fields)
        forms = dict([(k, f) for k, f in
                      emit_signal('get_step_form_class').iteritems()
                      if f is not None])

        steps = protocol.steps
        _L().debug('forms=%s steps=%s', forms, steps)

        if self.enabled_fields is None:
            # Assign directly to _enabled_fields to avoid recursive call into
            # update_grid()
            self._enabled_fields = dict([(form_name,
                                          set(form.field_schema_mapping
                                              .keys()))
                                         for form_name, form in forms.items()])

        # The step ID column can be hidden by changing show_ids to False
        combined_fields = ProtocolGridView(forms, self.enabled_fields,
                                           show_ids=True)
        combined_fields.connect('fields-filter-request',
                                self.set_fields_filter)

        for i, step in enumerate(steps):
            values = emit_signal('get_step_values', [i])

            attributes = dict()
            for form_name, form in combined_fields.forms.iteritems():
                attr_values = values[form_name]
                attributes[form_name] = RowFields(**attr_values)
            combined_row = CombinedRow(combined_fields, attributes=attributes)
            combined_fields.append(combined_row)

        if self.widget:
            # Replacing a previously rendered widget.  Maintain original column
            # order.

            # Store the position of each column, keyed by column title.
            column_positions = dict([(_get_title(c), i)
                                     for i, c in enumerate(self.widget
                                                           .get_columns())])
            # Remove existing widget to replace with new widget.
            self.window.remove(self.widget)
            del self.widget
        else:
            # No previously rendered widget.  Used saved column positions (if
            # available).
            app_values = self.get_app_values()
            column_positions_json = app_values.get('column_positions', '{}')
            column_positions = json.loads(column_positions_json)

        if column_positions:
            # Explicit column positions are available, so reorder columns
            # accordingly.

            # Remove columns so we can reinsert them in an explicit order.
            columns = combined_fields.get_columns()
            for c in columns:
                combined_fields.remove_column(c)

            # Sort columns according to original order.
            ordered_column_info = sorted([(column_positions.get(_get_title(c),
                                                                len(columns)),
                                           _get_title(c), c) for c in columns])

            # Re-add columns in order (sorted according to existing column
            # order).
            for i, title_i, column_i in ordered_column_info:
                combined_fields.append_column(column_i)

        self.widget = combined_fields

        app = get_app()
        if self.widget:
            self.widget.show_all()
            step_number = app.protocol_controller.protocol_state['step_number']
            self.widget.select_row(step_number)
            self.window.add(self.widget)
            self.accel_group = self._create_accel_group(app
                                                        .main_window_controller
                                                        .view)
            app.main_window_controller.view.add_accel_group(self.accel_group)
        else:
            self.accel_group = None

        # Disable keyboard shortcuts when a cell edit has started.  Without
        # doing so, certain keys may not behave as expected in edit mode.  For
        # example, see [`step_label_plugin`][1].
        #
        # [1]: https://github.com/wheeler-microfluidics/step_label_plugin/issues/1
        self.widget.connect('editing-started', lambda *args:
                            app.main_window_controller
                            .disable_keyboard_shortcuts())
        # Re-enable keyboard shortcuts when a cell edit has completed.
        self.widget.connect('editing-done', lambda *args:
                            app.main_window_controller
                            .enable_keyboard_shortcuts())

    def _create_accel_group(self, widget):
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
        shortcuts = {
            '<Control>c': self.widget.copy_rows,
            '<Control>x': FocusWrapper(self, self.widget.cut_rows),
            'Delete': FocusWrapper(self, self.widget.delete_rows),
            '<Control>v': FocusWrapper(self, self.widget.paste_rows_after),
            '<Control><Shift>v': FocusWrapper(self,
                                              self.widget.paste_rows_before),
            '<Control><Shift>i': FocusWrapper(self, lambda:
                                              app.protocol.insert_step())}
        return get_accel_group(widget, shortcuts,
                               enabled_widgets=[self.widget])

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        elif function_name == 'on_protocol_swapped':
            # Ensure that the app's reference to the new protocol gets set
            return [ScheduleRequest('microdrop.app', self.name)]
        return []

    def on_step_default_created(self, step_number):
        self.update_grid()

    def on_step_created(self, step_number):
        self.update_grid()

    def on_step_swapped(self, original_step_number, step_number):
        _L().debug('%d -> %d', original_step_number, step_number)
        if self.widget:
            app = get_app()
            step_number = app.protocol_controller.protocol_state['step_number']
            self.widget.select_row(step_number)

    def on_step_removed(self, step_number, step):
        _L().debug('%d', step_number)
        self.update_grid()

    def on_app_exit(self):
        if self.widget:
            # Save column positions on exit.
            column_positions = dict([(_get_title(c), i)
                                     for i, c in enumerate(self.widget
                                                           .get_columns())])
            self.set_app_values({'column_positions':
                                 json.dumps(column_positions)})


PluginGlobals.pop_env()
