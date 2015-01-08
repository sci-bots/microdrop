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
import logging
import shutil

import gtk
from textbuffer_with_undo import UndoableBuffer
from microdrop_utility import is_float, is_int, FutureVersionError
from microdrop_utility.gui import (yesno, contains_pointer, register_shortcuts,
                                   textentry_validate, text_entry_dialog)

from ..protocol import Protocol
from ..plugin_manager import (ExtensionPoint, IPlugin, SingletonPlugin,
                              implements, PluginGlobals, ScheduleRequest,
                              emit_signal, get_service_class,
                              get_service_instance,
                              get_service_instance_by_name, get_observers,
                              get_service_names)
from ..app_context import get_app


PluginGlobals.push_env('microdrop')


class ProtocolController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.protocol_controller"
        self.builder = None
        self.waiting_for = []
        self.repeat_step = False
        self.label_step_number = None
        self.label_step_number = None
        self.button_first_step = None
        self.button_prev_step = None
        self.button_run_protocol = None
        self.button_next_step = None
        self.button_last_step = None
        self.textentry_protocol_repeats = None
        self._modified = False

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        self._modified = value
        self.menu_save_protocol.set_sensitive(value)

    def _register_shortcuts(self):
        app = get_app()
        view = app.main_window_controller.view
        shortcuts = {
            'space': self.on_run_protocol,
            'A': self.on_first_step,
            'S': self.on_prev_step,
            'D': self.on_next_step,
            'F': self.on_last_step,
            #'Delete': self.on_delete_step,
        }
        register_shortcuts(view, shortcuts,
                    disabled_widgets=[self.textentry_notes])

        notes_shortcuts = {
            '<Control>z': self.textentry_notes.get_buffer().undo,
            '<Control>y': self.textentry_notes.get_buffer().redo,
        }
        register_shortcuts(view, notes_shortcuts,
                    enabled_widgets=[self.textentry_notes])

    def load_protocol(self, filename):
        app = get_app()
        p = None
        try:
            p = Protocol.load(filename)
        except FutureVersionError, why:
            logging.error('''\
Could not open protocol:
    %s
It was created with a newer version of the software.
Protocol is version %s, but only up to version %s is supported with this version of the software.'''\
            % (filename, why.future_version, why.current_version))
        except Exception, why:
            logging.error("Could not open %s. %s" % (filename, why))
        if p:
            # check if the protocol contains data from plugins that are not
            # enabled
            enabled_plugins = get_service_names(env='microdrop.managed') + \
                get_service_names('microdrop')
            missing_plugins = []
            for k, v in p.plugin_data.items():
                if k not in enabled_plugins and k not in missing_plugins:
                    missing_plugins.append(k)
            for i in range(len(p)):
                for k, v in p[i].plugin_data.items():
                    if k not in enabled_plugins and k not in missing_plugins:
                        missing_plugins.append(k)
            if missing_plugins:
                logging.info('load protocol(%s): missing plugins: %s' %
                             (filename, ", ".join(missing_plugins)))
                result = yesno('Some data in the protocol "%s" requires '
                               'plugins that are not currently installed:'
                               '\n\t%s\nThis data will be ignored unless you '
                               'install and enable these plugins. Would you'
                               'like to permanently clear this data from the '
                               'protocol?' % (p.name,
                                            ",\n\t".join(missing_plugins)))
                if result == gtk.RESPONSE_YES:
                    logging.info('Deleting protocol data for missing items')
                    for k, v in p.plugin_data.items():
                        if k in missing_plugins:
                            del p.plugin_data[k]
                    for i in range(len(p)):
                        for k, v in p[i].plugin_data.items():
                            if k in missing_plugins:
                                del p[i].plugin_data[k]
                    self.save_protocol()
            self.modified = False
            emit_signal("on_protocol_swapped", [app.protocol, p])

    def create_protocol(self):
        old_protocol = get_app().protocol
        self.modified = True
        p = Protocol()
        emit_signal("on_protocol_swapped", [old_protocol, p])

    def on_protocol_swapped(self, old_protocol, protocol):
        protocol.plugin_fields = emit_signal('get_step_fields')
        logging.debug('[ProtocolController] on_protocol_swapped(): plugin_fields=%s' % protocol.plugin_fields)
        self.run_step()

    def on_plugin_enable(self):
        app = get_app()
        self.builder = app.builder

        self.textentry_notes = self.builder.get_object("textview_notes")
        self.textentry_notes.set_buffer(UndoableBuffer())
        self.label_step_number = self.builder.get_object("label_step_number")
        self.textentry_protocol_repeats = self.builder.get_object(
            "textentry_protocol_repeats")

        self.button_first_step = app.builder.get_object('button_first_step')
        self.button_prev_step = app.builder.get_object('button_prev_step')
        self.button_run_protocol = self.builder.get_object("button_run_protocol")
        self.button_next_step = app.builder.get_object('button_next_step')
        self.button_last_step = app.builder.get_object('button_last_step')

        self.menu_protocol = app.builder.get_object('menu_protocol')
        self.menu_new_protocol = app.builder.get_object('menu_new_protocol')
        self.menu_load_protocol = app.builder.get_object('menu_load_protocol')
        self.menu_rename_protocol = app.builder.get_object('menu_rename_protocol')
        self.menu_save_protocol = app.builder.get_object('menu_save_protocol')
        self.menu_save_protocol_as = app.builder.get_object('menu_save_protocol_as')

        app.signals["on_button_first_step_button_release_event"] = self.on_first_step
        app.signals["on_button_prev_step_button_release_event"] = self.on_prev_step
        app.signals["on_button_next_step_button_release_event"] = self.on_next_step
        app.signals["on_button_last_step_button_release_event"] = self.on_last_step
        app.signals["on_button_run_protocol_button_release_event"] = self.on_run_protocol
        app.signals["on_menu_new_protocol_activate"] = self.on_new_protocol
        app.signals["on_menu_load_protocol_activate"] = self.on_load_protocol
        app.signals["on_menu_rename_protocol_activate"] = self.on_rename_protocol
        app.signals["on_menu_save_protocol_activate"] = self.on_save_protocol
        app.signals["on_menu_save_protocol_as_activate"] = self.on_save_protocol_as
        app.signals["on_textentry_protocol_repeats_focus_out_event"] = \
                self.on_textentry_protocol_repeats_focus_out
        app.signals["on_textentry_protocol_repeats_key_press_event"] = \
                self.on_textentry_protocol_repeats_key_press
        app.protocol_controller = self
        self._register_shortcuts()

        self.menu_protocol.set_sensitive(False)
        self.menu_new_protocol.set_sensitive(False)
        self.menu_load_protocol.set_sensitive(False)
        self.button_first_step.set_sensitive(False)
        self.button_prev_step.set_sensitive(False)
        self.button_run_protocol.set_sensitive(False)
        self.button_next_step.set_sensitive(False)
        self.button_last_step.set_sensitive(False)

    def on_first_step(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            app.protocol.first_step()
            return True
        return False

    def on_prev_step(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            app.protocol.prev_step()
            return True
        return False

    def on_next_step(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            app.protocol.next_step()
            return True
        return False

    def on_last_step(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            app.protocol.last_step()
            return True
        return False

    def on_new_protocol(self, widget=None, data=None):
        self.save_check()
        self.create_protocol()

    def on_run_protocol(self, widget=None, data=None):
        if widget is None or contains_pointer(widget, data.get_coords()):
            app = get_app()
            if app.running:
                self.pause_protocol()
            else:
                self.run_protocol()
            return True
        return False

    def on_load_protocol(self, widget=None, data=None):
        app = get_app()
        self.save_check()
        dialog = gtk.FileChooserDialog(title="Load protocol",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(os.path.join(app.get_device_directory(),
                                               app.dmf_device.name,
                                               "protocols"))
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            self.load_protocol(filename)
        dialog.destroy()

    def on_rename_protocol(self, widget=None, data=None):
        self.save_protocol(rename=True)

    def on_save_protocol(self, widget=None, data=None):
        self.save_protocol()

    def on_save_protocol_as(self, widget=None, data=None):
        self.save_protocol(save_as=True)

    def on_textentry_protocol_repeats_focus_out(self, widget, data=None):
        self.on_protocol_repeats_changed()

    def on_textentry_protocol_repeats_key_press(self, widget, event):
        if event.keyval == gtk.gdk.keyval_from_name('Return'):
            # user pressed enter
            self.on_protocol_repeats_changed()

    def on_protocol_repeats_changed(self):
        app = get_app()
        if app.protocol:
            app.protocol.n_repeats = \
                textentry_validate(self.textentry_protocol_repeats,
                    app.protocol.n_repeats,
                    int)

    def save_check(self):
        app = get_app()
        if self.modified:
            result = yesno('Protocol %s has unsaved changes.  Save now?'\
                    % app.protocol.name)
            if result == gtk.RESPONSE_YES:
                self.save_protocol()

    def save_protocol(self, save_as=False, rename=False):
        app = get_app()
        name = app.protocol.name
        if app.dmf_device.name:
            if save_as or rename or app.protocol.name is None:
                # if the dialog is cancelled, name = ""
                if name is None:
                    name=''
                name = text_entry_dialog('Protocol name', name, 'Save protocol')
                if name is None:
                    name=''

            if name:
                path = os.path.join(app.get_device_directory(),
                                    app.dmf_device.name,
                                    "protocols")
                if os.path.isdir(path) == False:
                    os.mkdir(path)

                # current file name
                if app.protocol.name:
                    src = os.path.join(path, app.protocol.name)
                dest = os.path.join(path, name)

                # if the protocol name has changed
                if name != app.protocol.name:
                    app.protocol.name = name

                # if we're renaming
                if rename and os.path.isfile(src):
                    shutil.move(src, dest)
                else: # save the file
                    app.protocol.save(dest)
                self.modified = False
                emit_signal("on_protocol_changed")

    def run_protocol(self):
        app = get_app()
        app.running = True
        self.button_run_protocol.set_image(self.builder.get_object(
            "image_pause"))
        app.protocol.current_step_attempt = 0
        emit_signal("on_protocol_run")
        self.run_step()

    def pause_protocol(self):
        app = get_app()
        app.running = False
        app.protocol.current_step_attempt = 0
        self.button_run_protocol.set_image(self.builder.get_object(
            "image_play"))
        emit_signal("on_protocol_pause")

    def run_step(self):
        app = get_app()
        if app.protocol and app.dmf_device and \
        (app.realtime_mode or app.running):
            if app.experiment_log:
                app.experiment_log.add_step(app.protocol.current_step_number,
                                            app.protocol.current_step_attempt)

            self.waiting_for = get_observers("on_step_run", IPlugin).keys()
            logging.info("[ProcolController.run_step]: waiting for %s" %
                          ", ".join(self.waiting_for))
            emit_signal("on_step_run")

    def on_step_complete(self, plugin_name, return_value=None):
        app = get_app()
        logging.info("[ProcolController].on_step_complete: %s finished" %
                      plugin_name)
        if plugin_name in self.waiting_for:
            self.waiting_for.remove(plugin_name)

        # check retern value
        if return_value=='Fail':
            self.pause_protocol()
            logging.error("Protocol failed.")
        elif return_value=='Repeat':
            self.repeat_step = True
        else:
            self.repeat_step = False

        if len(self.waiting_for):
            logging.debug("[ProcolController].on_step_complete: still waiting "
                          "for %s" % ", ".join(self.waiting_for))
        # if all plugins have completed the current step, go to the next step
        elif app.running:
            if self.repeat_step:
                app.protocol.current_step_attempt += 1
                self.run_step()
            else:
                app.protocol.current_step_attempt = 0
                if app.protocol.current_step_number < len(app.protocol)-1:
                    self.on_next_step()
                elif app.protocol.current_repetition < app.protocol.n_repeats-1:
                    app.protocol.next_repetition()
                else: # we're on the last step
                    self.pause_protocol()

    def _get_dmf_control_fields(self, step_number):
        step = get_app().protocol.get_step(step_number)
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        service = get_service_instance_by_name(dmf_plugin_name)
        if service:
            return service.get_step_values(step_number)
        return None

    def on_step_options_changed(self, plugin, step_number):
        logging.debug('[ProtocolController.on_step_options_changed] plugin=%s, '
                      'step_number=%s' % (plugin, step_number))
        self.modified = True
        emit_signal('on_protocol_changed')
        self.run_step()

    def set_app_values(self, values_dict):
        logging.debug('[ProtocolController] set_app_values(): '\
                    'values_dict=%s' % (values_dict,))
        elements = self.AppFields(value=values_dict)
        if not elements.validate():
            raise ValueError('Invalid values: %s' % el.errors)
        values = dict([(k, v.value) for k, v in elements.iteritems() if v.value])
        if 'fps_limit' in values:
            self.grabber.set_fps_limit(values['fps_limit'])
        app = get_app()
        app.set_data(self.name, values)
        emit_signal('on_app_options_changed', [self.name], interface=IPlugin)

    def on_step_swapped(self, original_step_number, step_number):
        logging.debug('[ProtocolController.on_step_swapped] '
                      'original_step_number=%s, step_number=%s' %
                      (original_step_number, step_number))
        self._update_labels()
        self.run_step()

    def _update_labels(self):
        app = get_app()
        self.label_step_number.set_text("Step: %d/%d\tRepetition: %d/%d" %
            (app.protocol.current_step_number + 1,
            len(app.protocol.steps),
            app.protocol.current_repetition + 1,
            app.protocol.n_repeats))
        self.textentry_protocol_repeats.set_text(str(app.protocol.n_repeats))

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        if dmf_device:
            self.menu_protocol.set_sensitive(True)
            self.menu_new_protocol.set_sensitive(True)
            self.menu_load_protocol.set_sensitive(True)
            self.button_first_step.set_sensitive(True)
            self.button_prev_step.set_sensitive(True)
            self.button_run_protocol.set_sensitive(True)
            self.button_next_step.set_sensitive(True)
            self.button_last_step.set_sensitive(True)
            self.create_protocol()

    def on_app_exit(self):
        app = get_app()
        if self.modified:
            result = yesno('Protocol %s has unsaved changes.  Save now?'\
                    % app.protocol.name)
            if result == gtk.RESPONSE_YES:
                self.save_protocol()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        elif function_name == 'on_dmf_device_swapped':
            # make sure that the app gets a reference to the device before we
            # create a new protocol
            return [ScheduleRequest('microdrop.app', self.name)]
        return []

PluginGlobals.pop_env()
