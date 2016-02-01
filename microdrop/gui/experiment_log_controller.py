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
from collections import namedtuple
import logging
import os
import pkg_resources
import time

from flatland import Form
from microdrop_utility import copytree
from microdrop_utility.gui import (combobox_set_model_from_list,
                                   combobox_get_active_text, textview_get_text)
from path_helpers import path
from pygtkhelpers.delegates import SlaveView
from pygtkhelpers.ui.extra_dialogs import yesno
from pygtkhelpers.ui.extra_widgets import Directory
from pygtkhelpers.ui.notebook import NotebookManagerView
import gtk

from ..experiment_log import ExperimentLog
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, emit_signal, ScheduleRequest,
                              get_service_names, get_service_instance_by_name)
from ..plugin_helpers import AppDataController
from ..protocol import Protocol
from ..app_context import get_app
from ..dmf_device import DmfDevice
from .dmf_device_controller import DEVICE_FILENAME

logger = logging.getLogger(__name__)
from .. import glade_path


class ExperimentLogColumn():
    def __init__(self, name, type, format_string=None):
        self.name = name
        self.type = type
        self.format_string = format_string


class ExperimentLogContextMenu(SlaveView):
    """
    Slave view for context-menu for a row in the experiment log step grid view.
    """
    builder_path = glade_path().joinpath('experiment_log_context_menu.glade')

    def popup(self, event):
        for child in self.menu_popup.get_children():
            if child.get_visible():
                self.menu_popup.popup(None, None, None, event.button,
                                      event.time, None)
                break

    def add_item(self, menu_item):
        self.menu_popup.append(menu_item)
        menu_item.show()

PluginGlobals.push_env('microdrop')


class ExperimentLogController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    Results = namedtuple('Results', ['log', 'protocol', 'dmf_device'])
    builder_path = glade_path().joinpath('experiment_log_window.glade')

    @property
    def AppFields(self):
        return Form.of(
            Directory.named('notebook_directory').using(default='', optional=True),
        )

    def __init__(self):
        self.name = "microdrop.gui.experiment_log_controller"
        self.builder = gtk.Builder()
        self.builder.add_from_file(self.builder_path)
        self.window = self.builder.get_object("window")
        self.combobox_log_files = self.builder.get_object("combobox_log_files")
        self.results = self.Results(None, None, None)
        self.protocol_view = self.builder.get_object("treeview_protocol")
        self.protocol_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.columns = [ExperimentLogColumn("Time (s)", float, "%.3f"),
                        ExperimentLogColumn("Step #", int),
                        ExperimentLogColumn("Duration (s)", float, "%.3f"),
                        ExperimentLogColumn("Voltage (VRMS)", int),
                        ExperimentLogColumn("Frequency (kHz)", float, "%.1f")]
        (self.protocol_view.get_selection()
         .connect("changed", self.on_treeview_selection_changed))
        self.popup = ExperimentLogContextMenu()
        self.notebook_manager_view = None
        self.previous_notebook_dir = None

    def apply_notebook_dir(self, notebook_directory):
        '''
        Set the notebook directory to the specified directory.

        If the specified directory is empty or `None`, use the default
        directory (i.e., in the default Microdrop user directory) as the new
        directory path.

        If no directory was previously set and the specified directory does not
        exist, copy the default set of notebooks from the `microdrop` package
        to the new notebook directory.

        If a directory was previously set, copy the contents of the previous
        directory to the new directory (prompting the user to overwrite if the
        new directory already exists).
        '''
        app = get_app()

        print '[{notebook_directory = "%s"}]' % notebook_directory
        if not notebook_directory:
            # The notebook directory is not set (i.e., empty or `None`), so set
            # a default.
            data_directory = path(app.config.data['data_dir'])
            notebook_directory = data_directory.joinpath( 'notebooks')
            print '[{new notebook_directory = "%s"}]' % notebook_directory
            app_values = self.get_app_values().copy()
            app_values['notebook_directory'] = notebook_directory
            self.set_app_values(app_values)

        if self.previous_notebook_dir and (notebook_directory ==
                                           self.previous_notebook_dir):
            # If the data directory hasn't changed, we do nothing
            return False

        notebook_directory = path(notebook_directory)
        if self.previous_notebook_dir:
            notebook_directory.makedirs_p()
            if notebook_directory.listdir():
                result = yesno('Merge?', '''\
Target directory [%s] is not empty.  Merge contents with
current notebooks [%s] (overwriting common paths in the target
directory)?''' % (notebook_directory, self.previous_notebook_dir))
                if not result == gtk.RESPONSE_YES:
                    return False

            original_directory = path(self.previous_notebook_dir)
            for d in original_directory.dirs():
                copytree(d, notebook_directory.joinpath(d.name))
            for f in original_directory.files():
                f.copyfile(notebook_directory.joinpath(f.name))
            original_directory.rmtree()
        elif not notebook_directory.isdir():
            # if the notebook directory doesn't exist, copy the skeleton dir
            if notebook_directory.parent:
                notebook_directory.parent.makedirs_p()
            skeleton_dir = path(pkg_resources.resource_filename('microdrop',
                                                                'static'))
            skeleton_dir.joinpath('notebooks').copytree(notebook_directory)
        self.previous_notebook_dir = notebook_directory
        # Set the default template directory of the IPython notebook manager
        # widget to the notebooks directory.
        self.notebook_manager_view.template_dir = notebook_directory

    def on_plugin_enable(self):
        super(ExperimentLogController, self).on_plugin_enable()
        app = get_app()
        app.experiment_log_controller = self
        self.window.set_title("Experiment logs")
        self.builder.connect_signals(self)

        app_values = self.get_app_values()

        # Create buttons to manage background IPython notebook sessions.
        # Sessions are killed when microdrop exits.
        self.notebook_manager_view = NotebookManagerView()
        self.apply_notebook_dir(app_values['notebook_directory'])

        vbox = self.builder.get_object('vbox1')
        hbox = gtk.HBox()
        label = gtk.Label('IPython notebook:')
        hbox.pack_start(label, False, False)
        hbox.pack_end(self.notebook_manager_view.widget, False, False)
        vbox.pack_start(hbox, False, False)
        vbox.reorder_child(hbox, 1)
        hbox.show_all()

    def on_treeview_protocol_button_press_event(self, widget, event):
        if event.button == 3:
            self.popup.popup(event)
            return True

    def get_selected_log_root(self):
        app = get_app()
        id = combobox_get_active_text(self.combobox_log_files)
        return path(app.experiment_log.directory) / path(id)

    def update(self):
        app = get_app()
        if not app.experiment_log:
            self._disable_gui_elements()
            return
        try:
            log_root = self.get_selected_log_root()
            log = log_root.joinpath("data")
            protocol = log_root.joinpath("protocol")
            dmf_device = log_root.joinpath(DEVICE_FILENAME)
            self.results = self.Results(ExperimentLog.load(log),
                                        Protocol.load(protocol),
                                        DmfDevice.load(dmf_device,
                                                       name=dmf_device.parent
                                                       .name))
            #self.builder.get_object("button_load_device").set_sensitive(True)
            self.builder.get_object("button_load_protocol").set_sensitive(True)
            self.builder.get_object("textview_notes").set_sensitive(True)

            label = "Software version: "
            data = self.results.log.get("software version")
            for val in data:
                if val:
                    label += val
            self.builder.get_object("label_software_version"). \
                set_text(label)

            label = "Device: "
            data = self.results.log.get("device name")
            for val in data:
                if val:
                    label += val
            self.builder.get_object("label_device"). \
                set_text(label)

            data = self.results.log.get("protocol name")

            label = "Protocol: None"
            for val in data:
                if val:
                    label = "Protocol: %s" % val

            self.builder.get_object("label_protocol"). \
                set_text(label)

            label = "Control board: "
            data = self.results.log.get("control board name")
            for val in data:
                if val:
                    label += val
            data = self.results.log.get("control board hardware version")
            for val in data:
                if val:
                    label += " v%s" % val
            serial_number = ""
            data = self.results.log.get("control board serial number")
            for val in data:
                if val:
                    serial_number = ", S/N %03d" % val
            data = self.results.log.get("control board software version")
            for val in data:
                if val:
                    label += "\n\t(Firmware: %s%s)" % (val, serial_number)
            data = self.results.log.get("i2c devices")
            for val in data:
                if val:
                    label += "\ni2c devices:"
                    for address, description in sorted(val.items()):
                        label += "\n\t%d: %s" % (address, description)
            self.builder.get_object("label_control_board"). \
                set_text(label)

            label = "Enabled plugins: "
            data = self.results.log.get("plugins")
            for val in data:
                if val:
                    for k, v in val.iteritems():
                        label += "\n\t%s %s" % (k, v)

            self.builder.get_object("label_plugins"). \
                set_text(label)

            label = "Time of experiment: "
            data = self.results.log.get("start time")
            for val in data:
                if val:
                    label += time.ctime(val)
            self.builder.get_object("label_experiment_time"). \
                set_text(label)

            label = ""
            data = self.results.log.get("notes")
            for val in data:
                if val:
                    label = val
            self.builder.get_object("textview_notes"). \
                get_buffer().set_text(label)

            self._clear_list_columns()
            types = []
            for i, c in enumerate(self.columns):
                types.append(c.type)
                self._add_list_column(c.name, i, c.format_string)
            protocol_list = gtk.ListStore(*types)
            self.protocol_view.set_model(protocol_list)
            for d in self.results.log.data:
                if 'step' in d['core'].keys() and 'time' in d['core'].keys():
                    # Only show steps that exist in the protocol (See:
                    # http://microfluidics.utoronto.ca/microdrop/ticket/153)
                    #
                    # This prevents "list index out of range" errors, if a step
                    # that was saved to the experiment log is deleted, but it is
                    # still possible to have stale data if the protocol is
                    # edited in real-time mode.
                    if d['core']['step'] < len(self.results.protocol):
                        step = self.results.protocol[d['core']['step']]
                        dmf_plugin_name = step.plugin_name_lookup(
                            r'wheelerlab.dmf_control_board', re_pattern=True)
                        options = step.get_data(dmf_plugin_name)
                        vals = []
                        if not options:
                            continue
                        for i, c in enumerate(self.columns):
                            if c.name=="Time (s)":
                                vals.append(d['core']['time'])
                            elif c.name=="Step #":
                                vals.append(d['core']['step'] + 1)
                            elif c.name=="Duration (s)":
                                vals.append(options.duration / 1000.0)
                            elif c.name=="Voltage (VRMS)":
                                vals.append(options.voltage)
                            elif c.name=="Frequency (kHz)":
                                vals.append(options.frequency / 1000.0)
                            else:
                                vals.append(None)
                        protocol_list.append(vals)
        except Exception, why:
            logger.info("[ExperimentLogController].update(): %s" % why)
            self._disable_gui_elements()

    def _disable_gui_elements(self):
        self.builder.get_object("button_load_device").set_sensitive(False)
        self.builder.get_object("button_load_protocol").set_sensitive(False)
        self.builder.get_object("textview_notes").set_sensitive(False)

    def save(self):
        app = get_app()

        # Only save the current log if it is not empty (i.e., it contains at
        # least one step).
        if (hasattr(app, 'experiment_log') and app.experiment_log and
                [x for x in app.experiment_log.get('step') if x is not None]):
            data = {'software version': app.version}
            data['device name'] = app.dmf_device.name
            data['protocol name'] = app.protocol.name
            data['notes'] = textview_get_text(app.protocol_controller.builder
                                              .get_object('textview_notes'))
            plugin_versions = {}
            for name in get_service_names(env='microdrop.managed'):
                service = get_service_instance_by_name(name)
                if service._enable:
                    plugin_versions[name] = str(service.version)
            data['plugins'] = plugin_versions
            app.experiment_log.add_data(data)
            log_path = app.experiment_log.save()

            # Save the protocol to experiment log directory.
            app.protocol.save(os.path.join(log_path, 'protocol'))

            # Convert device to SVG string.
            svg_unicode = app.dmf_device.to_svg()
            # Save the device to experiment log directory.
            with open(os.path.join(log_path, DEVICE_FILENAME), 'wb') as output:
                output.write(svg_unicode)

            # create a new log
            experiment_log = ExperimentLog(app.experiment_log.directory)
            emit_signal('on_experiment_log_changed', experiment_log)

    def get_selected_data(self):
        selection = self.protocol_view.get_selection().get_selected_rows()
        selected_data = []
        for row in selection[1]:
            for d in self.results.log.data:
                if 'time' in d['core'].keys():
                    if d['core']['time']==selection[0][row][0]:
                        selected_data.append(d)
        return selected_data

    def on_window_show(self, widget, data=None):
        self.window.show()

    def on_window_delete_event(self, widget, data=None):
        self.window.hide()
        return True

    def on_combobox_log_files_changed(self, widget, data=None):
        if self.notebook_manager_view is not None:
            # Update active notebook directory for notebook_manager_view.
            log_root = self.get_selected_log_root()
            self.notebook_manager_view.notebook_dir = log_root
        self.update()

    def on_button_load_device_clicked(self, widget, data=None):
        app = get_app()
        filename = path(os.path.join(app.experiment_log.directory,
                                     str(self.results.log.experiment_id),
                                     DEVICE_FILENAME))
        try:
            app.dmf_device_controller.load_device(filename)
        except:
            logger.error("Could not open %s" % filename)

    def on_button_load_protocol_clicked(self, widget, data=None):
        app = get_app()
        filename = path(os.path.join(app.experiment_log.directory,
                                     str(self.results.log.experiment_id),
                                     'protocol'))
        app.protocol_controller.load_protocol(filename)

    def on_textview_notes_focus_out_event(self, widget, data=None):
        if len(self.results.log.data[0])==0:
            self.results.log.data.append({})
        self.results.log.data[-1]['core']['notes'] = \
            textview_get_text(self.builder.get_object("textview_notes"))
        filename = os.path.join(self.results.log.directory,
                                str(self.results.log.experiment_id),
                                'data')
        self.results.log.save(filename)

    def on_protocol_run(self):
        self.save()

    def on_app_exit(self):
        self.save()
        logger.info('[ExperimentLogController] Killing IPython notebooks')
        if self.notebook_manager_view is not None:
            self.notebook_manager_view.stop()

    def on_protocol_pause(self):
        self.save()

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        app = get_app()
        experiment_log = None
        if dmf_device and dmf_device.name:
            device_path = os.path.join(app.get_device_directory(),
                                       dmf_device.name, "logs")
            experiment_log = ExperimentLog(device_path)
        emit_signal("on_experiment_log_changed", experiment_log)

    def on_experiment_log_changed(self, experiment_log):
        log_files = []
        if experiment_log and path(experiment_log.directory).isdir():
            for d in path(experiment_log.directory).dirs():
                f = d / path("data")
                if f.isfile():
                    log_files.append(int(d.name))
            log_files.sort()
        self.combobox_log_files.clear()
        combobox_set_model_from_list(self.combobox_log_files, log_files)
        # changing the combobox log files will force an update
        if len(log_files):
            self.combobox_log_files.set_active(len(log_files)-1)
        if self.notebook_manager_view is not None:
            # Update active notebook directory for notebook_manager_view.
            log_root = self.get_selected_log_root()
            self.notebook_manager_view.notebook_dir = log_root

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_experiment_log_changed':
            # ensure that the app's reference to the new experiment log gets set
            return [ScheduleRequest('microdrop.app', self.name)]
        elif function_name == 'on_plugin_enable':
            # We use the notebook directory path stored in the configuration in
            # the `on_plugin_enable` method.  Therefore, we need to schedule
            # the `config_controller` plugin to handle the `on_plugin_enable`
            # first, so the configuration will be loaded before reading the
            # notebook directory.
            return [ScheduleRequest('microdrop.gui.config_controller',
                                    self.name)]
        return []

    def on_treeview_selection_changed(self, widget, data=None):
        emit_signal("on_experiment_log_selection_changed", [self.get_selected_data()])

    def _clear_list_columns(self):
        while len(self.protocol_view.get_columns()):
            self.protocol_view.remove_column(self.protocol_view.get_column(0))

    def _add_list_column(self, title, columnId, format_string=None):
        """
        This function adds a column to the list view.
        First it create the gtk.TreeViewColumn and then set
        some needed properties
        """
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(title, cell, text=columnId)
        column.set_resizable(True)
        column.set_sort_column_id(columnId)
        if format_string:
            column.set_cell_data_func(cell,
                                      self._cell_renderer_format,
                                      format_string)
        self.protocol_view.append_column(column)

    def _cell_renderer_format(self, column, cell, model, iter, format_string):
        val = model.get_value(iter, column.get_sort_column_id())
        cell.set_property('text', format_string % val)


PluginGlobals.pop_env()
