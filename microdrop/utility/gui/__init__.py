from functools import partial
import os

import gtk
from pygtkhelpers.ui.dialogs import simple, yesno as _yesno

from logger import logger
from .form_view_dialog import FormViewDialog
from .. import is_float, is_int
from flatland.schema import String, Form, Integer

def register_shortcuts(window, shortcuts, enabled_widgets=None,
                        disabled_widgets=None):
    logger.debug('register_shortcuts()...')
    if enabled_widgets and disabled_widgets:
        raise ValueError, '''Only an enabled list OR a disabled list of'''\
                            ''' widgets is permitted.'''
    accelgroup = gtk.AccelGroup()

    def action_wrapper(action, enabled, disabled, *args, **kwargs):
        active = window.get_focus()
        if (enabled and active in enabled) or \
            (enabled is None and (disabled is None or active not in disabled)):
            # Perform associated action and stop propagation of key event
            action(*args, **kwargs)
            return True
        else:
            # Ignore shortcut and pass control to default handlers
            return False

    for shortcut, action in shortcuts.iteritems():
        key, modifier = gtk.accelerator_parse(shortcut)
        accelgroup.connect_group(key, modifier, gtk.ACCEL_VISIBLE,
            lambda a, b, c, d, action=action: \
                action_wrapper(action, enabled_widgets, disabled_widgets))
    window.add_accel_group(accelgroup)
    logger.debug('DONE')
    return accelgroup


def textentry_validate(textentry, prev_value, type):
    val = textentry.get_text()
    if val and type is float:
        if is_float(val):
            return float(val)
    elif val and type is int:
        if is_int(val):
            return int(val)
    textentry.set_text(str(prev_value))
    return prev_value


def combobox_set_model_from_list(cb, items):
    """Setup a ComboBox or ComboBoxEntry based on a list of strings."""
    cb.clear()           
    model = gtk.ListStore(str)
    for i in items:
        model.append([i])
    cb.set_model(model)
    if type(cb) == gtk.ComboBoxEntry:
        cb.set_text_column(0)
    elif type(cb) == gtk.ComboBox:
        cell = gtk.CellRendererText()
        cb.pack_start(cell, True)
        cb.add_attribute(cell, 'text', 0)


def combobox_get_active_text(cb):
    model = cb.get_model()
    active = cb.get_active()
    if active < 0:
        return None
    return model[active][0]


def textview_get_text(textview):
    buffer = textview.get_buffer()
    start = buffer.get_start_iter()
    end = buffer.get_end_iter()
    return buffer.get_text(start, end)


#:  A yes/no question dialog, see :func:`~pygtkhelpers.ui.dialogs.simple` parameters
if os.name == 'nt':
    yesno = partial(_yesno, alt_button_order=(gtk.RESPONSE_YES, gtk.RESPONSE_NO))
else:
    yesno = _yesno


def field_entry_dialog(field, value=None, title='Input value'):
    form = Form.of(field)
    dialog = FormViewDialog(title=title)
    if value is not None:
        values = {field.name: value}
    else:
        values = None
    valid, response =  dialog.run(form, values)
    return valid, response.values()[0]


def integer_entry_dialog(name, value=0, title='Input value', min_value=None,
        max_value=None):
    field = Integer.named('name')
    validators = []
    if min_value is not None:
        ValueAtLeast(minimum=min_value)
    if max_value is not None:
        ValueAtMost(maximum=max_value)

    valid, response = field_entry_dialog(Integer.named(name)\
            .using(validators=validators), value, title)
    if valid:
        return response
    return None 


def text_entry_dialog(name, value='', title='Input value'):
    valid, response = field_entry_dialog(String.named(name), value, title)
    if valid:
        return response
    return None 
