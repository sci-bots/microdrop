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
import time
from collections import namedtuple

import gtk
from path import path

from experiment_log import ExperimentLog, load as load_experiment_log
from utility import combobox_set_model_from_list, \
    combobox_get_active_text, textview_get_text
from plugin_manager import IPlugin, SingletonPlugin, implements, \
    ExtensionPoint, emit_signal, PluginGlobals
from protocol import load as load_protocol
from dmf_device import DmfDevice

class ExperimentLogColumn():
    def __init__(self, name, type, format_string=None):
        self.name = name
        self.type = type
        self.format_string = format_string


PluginGlobals.push_env('microdrop')


class ExperimentLogController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.experiment_log_controller" 
        self.app = None
        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join("gui","glade",
            "experiment_log_window.glade"))
        self.window = self.builder.get_object("window")
        self.combobox_log_files = self.builder.get_object("combobox_log_files")
        self.results = namedtuple('Results', ['log', 'protocol'])
        self.results.log = None
        self.results.protocol = None
        self.protocol_view = self.builder.get_object("treeview_protocol")
        self.protocol_view.get_selection().set_mode(gtk.SELECTION_MULTIPLE)        
        self.columns = [ExperimentLogColumn("Time (s)", float, "%.3f"),
                        ExperimentLogColumn("Step #", int),
                        ExperimentLogColumn("Duration (s)", float, "%.3f"),
                        ExperimentLogColumn("Voltage (VRMS)", int),
                        ExperimentLogColumn("Frequency (kHz)", float, "%.1f")]
        self.protocol_view.get_selection().connect("changed", self.on_treeview_selection_changed)

    def on_app_init(self, app):
        self.app = app
        self.app.experiment_log_controller = self
        self.window.set_title("Experiment logs")
        self.builder.connect_signals(self)

    def update(self):        
        try:
            id = combobox_get_active_text(self.combobox_log_files)
            f = path(self.app.experiment_log.directory) / path(id) / path("data")
            self.results.log = load_experiment_log(f)

            self.builder.get_object("button_load_device").set_sensitive(True)        
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
            data = self.results.log.get("control board name")
            for val in data:
                if val:
                    label += val
            data = self.results.log.get("control board hardware version")
            for val in data:
                if val:
                    label += " v%s" % val
            data = self.results.log.get("control board software version")
            for val in data:
                if val:
                    label += "\n\tFirmware version:%s" % val
            self.builder.get_object("label_control_board"). \
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

            f = path(self.app.experiment_log.directory) / path(id) / path("protocol")
            self.results.protocol = load_protocol(f)
            self._clear_list_columns()
            types = []
            for i, c in enumerate(self.columns):
                types.append(c.type)
                self._add_list_column(c.name, i, c.format_string)
            protocol_list = gtk.ListStore(*types)
            self.protocol_view.set_model(protocol_list)
            for d in self.results.log.data:
                if d.keys().count("step") and d.keys().count("time"):
                    step = self.results.protocol[d["step"]]
                    vals = []
                    for i, c in enumerate(self.columns):
                        if c.name=="Time (s)":
                            vals.append(d["time"])
                        elif c.name=="Step #":
                            vals.append(d["step"]+1)
                        elif c.name=="Duration (s)":
                            vals.append(step.duration/1000.0)
                        elif c.name=="Voltage (VRMS)":
                            vals.append(step.voltage)
                        elif c.name=="Frequency (kHz)":
                            vals.append(step.frequency/1000.0)
                        else:
                            vals.append(None)
                    protocol_list.append(vals)
        except Exception, why:
            print "ExperimentLogController.update(): %s" % why
            self.builder.get_object("button_load_device").set_sensitive(False)        
            self.builder.get_object("button_load_protocol").set_sensitive(False)    
            self.builder.get_object("textview_notes").set_sensitive(False)
    
    def save(self):
        data = {"software version":self.app.version}
        data["device name"] = self.app.dmf_device.name
        data["protocol name"] = self.app.protocol.name
        if self.app.control_board.connected():
            data["control board name"] = \
                self.app.control_board.name()
            data["control board hardware version"] = \
                self.app.control_board.hardware_version()
            data["control board software version"] = \
                self.app.control_board.software_version()
        data["notes"] = textview_get_text(self.app.protocol_controller. \
            builder.get_object("textview_notes"))
        self.app.experiment_log.add_data(data)
        log_path = self.app.experiment_log.save()

        # save the protocol and device
        emit_signal("on_protocol_save")
        self.app.protocol.save(os.path.join(log_path,"protocol"))
        self.app.dmf_device.save(os.path.join(log_path,"device"))
        self.app.experiment_log.clear()
        emit_signal("on_experiment_log_changed", self.app.experiment_log)
        self.app.main_window_controller.update()

    def on_window_show(self, widget, data=None):
        self.window.show()
        
    def on_window_delete_event(self, widget, data=None):
        self.window.hide()
        return True
        
    def on_combobox_log_files_changed(self, widget, data=None):
        self.update()
    
    def on_button_load_device_clicked(self, widget, data=None):
        filename = path(os.path.join(self.app.experiment_log.directory,
                                     str(self.results.log.experiment_id),
                                     'device')) 
        try:
            emit_signal("on_dmf_device_changed", [DmfDevice.load(filename)])
        except:
            self.app.main_window_controller.error("Could not open %s" % filename)
        self.app.main_window_controller.update()
        
    def on_button_load_protocol_clicked(self, widget, data=None):
        filename = path(os.path.join(self.app.experiment_log.directory,
                                     str(self.results.log.experiment_id),
                                     'protocol'))
        self.app.protocol_controller.load_protocol(filename)
        
    def on_textview_notes_focus_out_event(self, widget, data=None):
        if len(self.results.log.data[0])==0:
            self.results.log.data.append({})
        self.results.log.data[0]["notes"] = textview_get_text(self.builder. \
            get_object("textview_notes"))
        filename = os.path.join(self.results.log.directory,
                                str(self.results.log.experiment_id),
                                'data')
        self.results.log.save(filename)

    def on_dmf_device_changed(self, dmf_device):
        device_path = None
        if dmf_device.name:
            device_path = os.path.join(self.app.config.dmf_device_directory,
                                       dmf_device.name, "logs")
        experiment_log = ExperimentLog(device_path)
        emit_signal("on_experiment_log_changed", [experiment_log])
        
    def on_experiment_log_changed(self, dmf_device):
        log_files = []
        if path(self.app.experiment_log.directory).isdir():
            for d in path(self.app.experiment_log.directory).dirs():
                f = d / path("data")
                if f.isfile():
                    log_files.append(int(d.name))
            log_files.sort()
        self.combobox_log_files.clear()
        combobox_set_model_from_list(self.combobox_log_files, log_files)
        if len(log_files):
            self.combobox_log_files.set_active(len(log_files)-1)
        self.update()
    
    def on_treeview_selection_changed(self, widget, data=None):
        selection = self.protocol_view.get_selection().get_selected_rows()
        selected_data = []
        list_store = selection[0]
        for row in selection[1]:
            for d in self.results.log.data:
                if d.keys().count("time"):
                    if d["time"]==selection[0][row][0]:
                        selected_data.append(d)
        emit_signal("on_experiment_log_selection_changed", [selected_data])

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
