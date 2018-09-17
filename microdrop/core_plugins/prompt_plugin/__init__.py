'''
.. versionadded:: 2.30
'''
from collections import OrderedDict
import functools as ft
import logging

from asyncio_helpers import sync
from markdown2pango import markdown2pango
from pygtkhelpers.forms import FormView
from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.schema import (get_fields_frame,
                                 fields_frame_to_flatland_form_class,
                                 expand_items, flatten_form)
from pygtkhelpers.utils import gsignal
import gtk
import jsonschema
import trollius as asyncio

from ...app_context import get_app, MODE_RUNNING_MASK, MODE_REAL_TIME_MASK
from ...interfaces import IApplicationMode
from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements)

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop')


class SchemaView(FormView):
    gsignal('invalid', object)
    gsignal('valid', object)

    def __init__(self, schema, values=None, **kwargs):
        self.validator = jsonschema.Draft4Validator(schema)
        self.df_fields = get_fields_frame(schema)
        self.df_fields.sort_values('field', inplace=True)
        self.schema_type = fields_frame_to_flatland_form_class(self.df_fields)
        if values is None:
            self.values = {}
        super(SchemaView, self).__init__()

    def create_ui(self):
        super(SchemaView, self).create_ui()
        self.label_error = gtk.Label()
        self.label_event_box = gtk.EventBox()
        self.label_event_box.add(self.label_error)
        self.vbox_errors = gtk.VBox()
        self.vbox_errors.add(self.label_event_box)
        self.widget.show_all()
        self.widget.add(self.vbox_errors)
        self.vbox_errors.show_all()
        self.vbox_errors.hide()
        self.connect('changed', self.on_changed)
        self.validate()

        for field_i in self.form.schema.field_schema:
            name_i = field_i.name
            form_field_i = self.form.fields[name_i]
            value = self.values.get(name_i,
                                    form_field_i.element.default_value)

            if not form_field_i.element.set(value):
                raise ValueError('"%s" is not a valid value for field "%s"' %
                                 (value, name_i))
            form_field_i.proxy.set_widget_value(value)
            if hasattr(form_field_i.widget, 'set_activates_default'):
                form_field_i.widget.set_activates_default(True)
            form_field_i.label_widget.set_use_markup(True)

    def on_changed(self, form_view, proxy_group, proxy, field_name, new_value):
        self.validate()

    def as_dict(self):
        return expand_items(flatten_form(self.form.schema).items())

    def validate(self):
        data_dict = self.as_dict()
        errors = OrderedDict([('.'.join(e.path), e)
                              for e in self.validator.iter_errors(data_dict)])

        # Light red color.
        light_red = gtk.gdk.Color(240 / 255., 126 / 255., 110 / 255.)

        for name_i, field_i in self.form.fields.iteritems():
            color_i = light_red if name_i in errors else None
            label_widget_i = (field_i.widget
                              .get_data('pygtkhelpers::label_widget'))
            label_widget_i.get_parent().modify_bg(gtk.STATE_NORMAL, color_i)

        if errors:
            message = '\n'.join(['[{}] {}'.format(name, error.message)
                                 for name, error in errors.iteritems()])
            self.label_event_box.modify_bg(gtk.STATE_NORMAL, light_red)
            self.label_error.set_markup(message)
            self.vbox_errors.show()
            self.emit('invalid', errors)
            return False
        else:
            self.label_error.set_markup('')
            self.vbox_errors.hide()
            self.emit('valid', data_dict)
            return True


def schema_dialog(schema, title=None, **kwargs):
    '''
    Display a dialog prompting for input based on specified JSON schema.

    Parameters
    ----------
    schema : dict
        JSON schema.
    title : str, optional
        Dialog title.
    **kwargs
        Keyword arguments passed to `gtk.MessageDialog()`.

    Returns
    -------
    dict or None
        Mapping from field name to entered value if ``OK`` button was pressed.
        Otherwise, ``None``.
    '''
    if 'buttons' not in kwargs:
        kwargs['buttons'] = gtk.BUTTONS_OK
    if 'message_format' not in kwargs:
        kwargs['message_format'] = '<b>Please fill in the fields below:</b>'
    dialog = gtk.MessageDialog(**kwargs)

    if title is not None:
        dialog.props.title = title
    dialog.props.use_markup = True

    if schema:
        ok_button = [b for b in dialog.get_action_area().get_children()
                     if b.get_label() == 'gtk-ok'][0]
        ok_button.props.has_default = True
        ok_button.props.has_focus = True

        view = SchemaView(schema)
        content_area, buttons_area = dialog.get_content_area().get_children()
        image, vbox = content_area.get_children()
        vbox.pack_end(view.widget)

        view.connect('valid', lambda *args: ok_button.set_sensitive(True))
        view.connect('invalid', lambda *args: ok_button.set_sensitive(False))

        view.validate()

    response = dialog.run()
    dialog.destroy()

    if response == gtk.RESPONSE_OK:
        return view.as_dict()


def ignorable_warning(**kwargs):
    '''
    Display warning dialog with checkbox to ignore further warnings.

    Returns
    -------
    dict
        Response with fields:

        - ``ignore``: ignore warning (`bool`).
        - ``always``: treat all similar warnings the same way (`bool`).


    .. versionadded:: 2.30
    '''
    dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_YES_NO,
                               type=gtk.MESSAGE_WARNING)

    for k, v in kwargs.items():
        setattr(dialog.props, k, v)

    content_area = dialog.get_content_area()
    vbox = content_area.get_children()[0].get_children()[-1]
    check_button = gtk.CheckButton(label='Let me _decide for each warning',
                                   use_underline=True)
    vbox.pack_end(check_button)
    check_button.show()

    dialog.set_default_response(gtk.RESPONSE_YES)

    dialog.props.secondary_use_markup = True
    dialog.props.secondary_text = ('<b>Would you like to ignore and '
                                   'continue?</b>')
    try:
        response = dialog.run()
        return {'ignore': (response == gtk.RESPONSE_YES),
                'always': not check_button.props.active}
    finally:
        dialog.destroy()


@asyncio.coroutine
def schema_input(schema, message='**Please fill in the following fields:**',
                 description=None):
    '''
    Asynchronous GTK input dialog based on JSON schema.

    Parameters
    ----------
    schema : dict
        JSON schema.
    message : str, optional
        Message presented in dialog.
    description : str, optional
        Title of input dialog.

    Returns
    -------
    dict or None
        Mapping from field name to entered value if ``OK`` button was
        pressed. Otherwise, ``None``.
    '''
    # Wrap dialog function call in partial since `gtk_threadsafe` does
    # not support passing keyword arguments.
    dialog_func = ft.partial(schema_dialog, schema, title=description,
                             type=gtk.MESSAGE_OTHER,
                             message_format=markdown2pango(message),
                             buttons=gtk.BUTTONS_OK_CANCEL)
    # Queue dialog to be launched in GTK thread and wait for response.
    response = yield asyncio.From(sync(gtk_threadsafe)(dialog_func)())
    if response is None:
        raise RuntimeError('Cancelled in response to message `%s`.' % message)
    raise asyncio.Return(response)


@asyncio.coroutine
def acknowledge(message, description=None):
    '''
    Receiver for `'acknowledge'` signal.

    Displays a GTK dialog with **OK** and **Cancel** buttons.  If **Cancel** is
    pressed, a `RuntimeError` exception is raised.  If **OK** is pressed, the
    receiver returns `None`.

    Parameters
    ----------
    message : str
        Message displayed to user in dialog.
    description : str, optional
        Title of the prompt (if specified).

    Raises
    ------
    RuntimeError
        If **Cancel** button is pressed.
    '''
    def _acknowledge():
        app = get_app()
        parent_window = app.main_window_controller.view
        dialog = gtk.MessageDialog(parent=parent_window,
                                   message_format=message,
                                   type=gtk.MESSAGE_OTHER,
                                   buttons=gtk.BUTTONS_OK_CANCEL)
        # Increase default dialog size.
        dialog.set_size_request(250, 100)
        if description is not None:
            dialog.props.title = description
        dialog.props.use_markup = True

        response_code = dialog.run()
        dialog.destroy()
        return response_code
    # Queue dialog to be launched in GTK thread and wait for response.
    response = yield asyncio.From(sync(gtk_threadsafe)(_acknowledge)())
    if response != gtk.RESPONSE_OK:
        raise RuntimeError('Cancelled in response to message `%s`.' % message)


class PromptPlugin(SingletonPlugin):
    '''
    Plugin to query for input through prompt GUI dialogs.
    '''
    implements(IPlugin)
    implements(IApplicationMode)
    plugin_name = 'microdrop.prompt_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.ignore_warnings = {}
        gtk.threads_init()

    @asyncio.coroutine
    def on_step_run(self, plugin_kwargs, signals):
        '''
        .. versionadded:: 2.30

        Handler called whenever a step is executed.

        Parameters
        ----------
        plugin_kwargs : dict
            Plugin settings as JSON serializable dictionary.
        signals : blinker.Namespace
            Signals namespace.
        '''
        @asyncio.coroutine
        def _on_warning(message, key=None, title='Warning'):
            if key is None:
                key = message
            if key in self.ignore_warnings:
                ignore = self.ignore_warnings[key]
            else:
                text = markdown2pango(message)
                response = yield asyncio.From(sync(gtk_threadsafe)
                    (ft.partial(ignorable_warning, title=title, text=text,
                                use_markup=True))())
                ignore = response['ignore']
                if response['always']:
                    self.ignore_warnings[key] = ignore

            if not ignore:
                # Do not ignore warning.
                raise RuntimeWarning(message)

        signals.signal('acknowledge').connect(acknowledge)
        signals.signal('input').connect(schema_input)
        signals.signal('warning').connect(_on_warning, weak=False)

    def on_mode_changed(self, old_mode, new_mode):
        if (all([(old_mode & ~MODE_REAL_TIME_MASK),
                 (new_mode & MODE_REAL_TIME_MASK),
                 (new_mode & ~MODE_RUNNING_MASK)]) or
            all([(old_mode & ~MODE_RUNNING_MASK),
                 (new_mode & MODE_RUNNING_MASK)])):
            # Either real-time mode was enabled when it wasn't before or
            # protocol just started running.
            # Reset to not ignoring any warnings.
            self.ignore_warnings.clear()


PluginGlobals.pop_env()
