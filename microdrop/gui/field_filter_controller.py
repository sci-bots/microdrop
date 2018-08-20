import logging
import re

from flatland import Form, Boolean
from pygtkhelpers.forms import FormView
from pygtkhelpers.proxy import proxy_for
import gtk
import pkgutil

from ..app_context import get_app
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import IPlugin, ExtensionPoint


logger = logging.getLogger(__name__)


class FieldFilterController(object):
    def __init__(self):
        '''
        .. versionchanged:: 2.21
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).
        '''
        app = get_app()
        builder = gtk.Builder()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__,
                                     'glade/app_options_dialog.glade')
        builder.add_from_string(glade_str)
        self.dialog = builder.get_object("app_options_dialog")
        self.frame_core_plugins = builder.get_object("frame_core_plugins")
        self.core_plugins_vbox = builder.get_object("core_plugins_vbox")
        self.plugin_form_vbox = builder.get_object("plugin_form_vbox")
        self.dialog.set_transient_for(app.main_window_controller.view)

        self.btn_ok = builder.get_object('btn_ok')
        self.btn_apply = builder.get_object('btn_apply')
        self.btn_cancel = builder.get_object('btn_cancel')
        self.form_views = {}
        self.enabled_fields_by_plugin = {}

        builder.connect_signals(self)
        self.builder = builder

    def _get_app_values(self, plugin_name):
        observers = ExtensionPoint(IPlugin)
        service = observers.service(plugin_name)
        if not hasattr(service, 'get_app_values'):
            values = dict([(k, v.value) for k, v in
                           self.forms[plugin_name].from_defaults()
                           .iteritems()])
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

    def run(self, forms, initial_values=None):
        # Empty plugin form vbox
        # Get list of app option forms
        self.forms = forms
        self.form_views = {}
        self.clear_form()
        app = get_app()
        core_plugins_count = 0
        for name, form in self.forms.iteritems():
            # For each form, generate a pygtkhelpers formview and append the
            # view onto the end of the plugin vbox

            if len(form.field_schema) == 0:
                continue

            # Only include fields that do not have show_in_gui set to False in
            # 'properties' dictionary
            schema_entries = [f for f in form.field_schema
                              if f.properties.get('show_in_gui', True)]
            gui_form = Form.of(*[Boolean.named(s.name).using(default=True,
                                                             optional=True)
                                 for s in schema_entries])
            FormView.schema_type = gui_form
            if not schema_entries:
                continue
            self.form_views[name] = FormView()
            if name in app.core_plugins:
                self.core_plugins_vbox.pack_start(self.form_views[name].widget)
                core_plugins_count += 1
            else:
                expander = gtk.Expander()
                expander.set_label(name)
                expander.set_expanded(True)
                expander.add(self.form_views[name].widget)
                self.plugin_form_vbox.pack_start(expander)
        if core_plugins_count == 0:
            self.frame_core_plugins.hide()
            self.plugin_form_vbox.remove(self.frame_core_plugins)
        else:
            if self.frame_core_plugins not in self.plugin_form_vbox.children():
                self.plugin_form_vbox.pack_start(self.frame_core_plugins)
            self.frame_core_plugins.show()

        if not initial_values:
            initial_values = {}

        for form_name, form in self.forms.iteritems():
            if not form.field_schema:
                continue
            form_view = self.form_views[form_name]
            values = initial_values.get(form_name, {})
            for name, field in form_view.form.fields.items():
                if name in values or not initial_values:
                    value = True
                else:
                    value = False
                _L().debug('set %s to %s', name, value)
                proxy = proxy_for(getattr(form_view, name))
                proxy.set_widget_value(value)
                field.label_widget.set_text(
                        re.sub(r'_',  ' ', name).title())

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
        enabled_fields_by_plugin = {}
        for name, form_view in self.form_views.iteritems():
            enabled_fields = set([f for f, v in form_view.form.fields.items()
                                  if v.element.value])
            if enabled_fields:
                enabled_fields_by_plugin[name] = enabled_fields
        self.enabled_fields_by_plugin = enabled_fields_by_plugin
