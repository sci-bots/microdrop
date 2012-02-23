import gtk

from logger import logger
from . import is_float, is_int


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