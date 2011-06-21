import gtk
import os
from controllers.dmf_controller import DmfController
from device_view import DeviceView
from protocol_editor import ProtocolEditor

class MainWindow:
    def __init__(self, app):
        self.app = app
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "main_window.glade"))
        self.window = builder.get_object("window")
        self.label_connection_status = builder.get_object("label_connection_status")
        self.checkbutton_realtime_mode = builder.get_object("checkbutton_realtime_mode")

        signals = {}
        signals["on_menu_quit_activate"] = self.on_destroy
        signals["on_window_destroy"] = self.on_destroy
        signals["on_checkbutton_realtime_mode_toggled"] = \
                self.on_realtime_mode_toggled

        self.device_view = DeviceView(app, builder, signals)
        self.protocol_editor = ProtocolEditor(app, builder, signals)
        builder.connect_signals(signals)

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

    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def on_realtime_mode_toggled(self, widget, data=None):
        self.update()

    def update(self):
        self.device_view.update()
        self.protocol_editor.update()
        self.app.realtime_mode = self.checkbutton_realtime_mode.get_active()
