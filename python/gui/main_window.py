import gtk
import os
from controllers.dmf_controller import DmfController
from device_view import DeviceView
from protocol_editor import ProtocolEditor

class MainWindow:
    def __init__(self, app):
        self.app = app
        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join("gui",
                                                "glade",
                                                "main_window.glade"))

        self.window = self.builder.get_object("window")
        self.label_connection_status = self.builder.get_object("label_connection_status")
        self.checkbutton_realtime_mode = self.builder.get_object("checkbutton_realtime_mode")

        self.device_view = DeviceView(app, self.builder)
        self.protocol_editor = ProtocolEditor(app, self.builder)

        signals = { "on_menu_quit_activate" :
                    self.on_destroy,
                    "on_window_destroy" :
                    self.on_destroy,
                    "on_checkbutton_realtime_mode_toggled" :
                    self.on_realtime_mode_toggled,
                    "on_device_view_button_press_event" :
                    self.device_view.on_button_press,
                    "on_device_view_key_press_event" :
                    self.device_view.on_key_press,
                    "on_device_view_expose_event" :
                    self.device_view.on_expose,
                    "on_button_insert_step_clicked" :
                    self.protocol_editor.on_insert_step,
                    "on_button_delete_step_clicked" :
                    self.protocol_editor.on_delete_step,
                    "on_button_first_step_clicked" :
                    self.protocol_editor.on_first_step,
                    "on_button_prev_step_clicked" :
                    self.protocol_editor.on_prev_step,
                    "on_button_next_step_clicked" :
                    self.protocol_editor.on_next_step,
                    "on_button_last_step_clicked" :
                    self.protocol_editor.on_last_step,
                    "on_menu_new_protocol_activate" :
                    self.protocol_editor.on_new_protocol,
                    "on_menu_save_protocol_activate" :
                    self.protocol_editor.on_save_protocol,
                    "on_menu_save_protocol_as_activate" :
                    self.protocol_editor.on_save_protocol_as,
                    "on_menu_load_protocol_activate" :
                    self.protocol_editor.on_load_protocol,
                    "on_menu_run_protocol_activate" :
                    self.protocol_editor.on_run_protocol,
                  }

        self.builder.connect_signals(signals)

        for i in range(0,31):
            if app.controller.Connect("COM%d" % i) == DmfController.RETURN_OK:
                #TODO check protocol name/version
                self.label_connection_status.set_text(app.controller.name() +
                                                      " v" + app.controller.version())
                #app.controller.set_debug(True)
                self.device_view.update()
                break

    def main(self):
        self.update()
        gtk.main()

    def set_realtime_mode(self, is_active):
        self.checkbutton_realtime_mode.set_active(is_active)

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def on_realtime_mode_toggled(self, widget, data=None):
        self.app.toggle_realtime_mode()

    def update(self):
        self.device_view.update()
        self.protocol_editor.update()
