import gtk


def register_shortcuts(window, shortcuts, enabled_widgets=None,
                        disabled_widgets=None):
    print 'register_shortcuts()...'
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
    print 'DONE'
    return accelgroup
