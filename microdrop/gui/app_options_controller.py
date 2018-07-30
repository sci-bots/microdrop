import logging
import re

from flatland.schema import Form
from pygtkhelpers.forms import FormView
from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.proxy import proxy_for
import gtk
import pkgutil

from ..app_context import get_app
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import IPlugin, ExtensionPoint, emit_signal

logger = logging.getLogger(__name__)


class AppOptionsController:
    def __init__(self):
        '''
        .. versionchanged:: 2.21
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).
        '''
        app = get_app()

        self.form_views = {}
        self.no_gui_names = set()

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

        builder.connect_signals(self)
        self.builder = builder

    def _get_app_values(self, plugin_name):
        observers = ExtensionPoint(IPlugin)
        service = observers.service(plugin_name)
        if not hasattr(service, 'get_app_values'):
            values = dict([(k, v.value) for k, v in self.forms[plugin_name]
                           .from_defaults().iteritems()])
        else:
            values = service.get_app_values()
        if not values:
            return {}
        else:
            return values

    def clear_form(self):
        '''
        .. versionchanged:: 2.11.2
            Make :func:`_remove_plugin_form` private local function.
        '''
        def _remove_plugin_form(x):
            if x != self.frame_core_plugins:
                self.plugin_form_vbox.remove(x)

        self.plugin_form_vbox.foreach(lambda x: _remove_plugin_form(x))

    def run(self):
        # Empty plugin form vbox
        # Get list of app option forms
        self.forms = emit_signal('get_app_form_class')
        self.form_views = {}
        self.clear_form()
        app = get_app()
        self.no_gui_names = set()
        for name, form in self.forms.iteritems():
            # For each form, generate a pygtkhelpers formview and append the
            # view onto the end of the plugin vbox

            if form is None:
                schema_entries = []
            else:
                # Only include fields that do not have show_in_gui set to False
                # in 'properties' dictionary
                schema_entries = [f for f in form.field_schema
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

    @gtk_threadsafe
    def on_btn_apply_clicked(self, widget, data=None):
        '''
        .. versionchanged:: 2.3.3
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.apply()

    def apply(self):
        for name, form_view in self.form_views.iteritems():
            fields = form_view.form.fields.keys()
            attrs = {}
            for field in fields:
                if form_view.form.fields[field].element.validate():
                    attrs[field] = form_view.form.fields[field].element.value
                else:
                    _L().error('Failed to set %s value for %s', field, name)
            if attrs:
                observers = ExtensionPoint(IPlugin)
                service = observers.service(name)
                service.set_app_values(attrs)
