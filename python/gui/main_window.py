import gtk
import os
from controllers.dmf_controller import DmfController
from controllers.agilent_33220a import Agilent33220A
from device_view import DeviceView

class MainWindow:
    def on_destroy(self, widget, data=None):
        gtk.main_quit()

    def __init__(self, app):
        self.app = app
        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join("gui",
                                                "glade",
                                                "main_window.glade"))

        self.window = self.builder.get_object("window")
        self.label_connection_status = self.builder.get_object("label_connection_status")
        self.device_view = DeviceView(app, self.builder)

        signals = { "on_menu_quit_activate" :
                    self.on_destroy,
                    "on_window_destroy" :
                    self.on_destroy,
                    "on_device_view_button_press_event" :
                    self.device_view.on_button_press,
                    "on_device_view_key_press_event" :
                    self.device_view.on_key_press,
                    "on_device_view_expose_event" :
                    self.device_view.on_expose }
        self.builder.connect_signals(signals)

        #app.func_gen = Agilent33220A()
        app.controller = DmfController()
        if app.controller.Connect("COM3") == DmfController.RETURN_OK:
            self.label_connection_status.set_text(app.controller.name() +
                                                  " v" + app.controller.version())
        gtk.main()
