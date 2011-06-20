from protocol import Protocol, Step
import gtk
import pickle

class ProtocolEditor():
    def __init__(self, app, builder):
        self.app = app
        self.button_first_step = builder.get_object("button_first_step")
        self.button_prev_step = builder.get_object("button_prev_step")
        self.button_next_step = builder.get_object("button_next_step")
        self.button_last_step = builder.get_object("button_last_step")
        self.button_insert_step = builder.get_object("button_insert_step")
        self.button_delete_step = builder.get_object("button_delete_step")
        self.textbox_step_time = builder.get_object("textbox_step_time")
        self.label_step_number = builder.get_object("label_step_number")
        self.menu_save_protocol = builder.get_object("menu_save_protocol")
        self.menu_load_protocol = builder.get_object("menu_load_protocol")

    def on_insert_step(self, widget, data=None):
        self.app.protocol.insert_step()
        self.update()

    def on_delete_step(self, widget, data=None):
        self.app.protocol.delete_step()
        self.update()

    def on_first_step(self, widget, data=None):
        self.app.protocol.first_step()
        self.update()

    def on_prev_step(self, widget, data=None):
        self.app.protocol.prev_step()
        self.update()

    def on_next_step(self, widget, data=None):
        self.app.protocol.next_step()
        self.update()

    def on_last_step(self, widget, data=None):
        self.app.protocol.last_step()
        self.update()

    def on_save_protocol(self, widget, data=None):
        print "save protcol"

    def on_save_protocol_as(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title=None,
                                       action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_SAVE_AS,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder("protocols")
        dialog.set_current_name("new")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            file_name = dialog.get_filename()
            output = open(file_name, 'wb')
            pickle.dump(self.app.protocol, output, -1)
            output.close()
        dialog.destroy()

    def on_load_protocol(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title=None,
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder("protocols")
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            file_name = dialog.get_filename()
            f = open(file_name, 'rb')
            self.app.protocol = pickle.load(f)
            f.close()
        dialog.destroy()
        self.app.main_window.update()

    def update(self):
        self.textbox_step_time.set_text(str(self.app.protocol.current_step().time))
        self.label_step_number.set_text("Step: %d/%d" % 
            (self.app.protocol.current_step_number+1, len(self.app.protocol.steps)))
        self.app.main_window.device_view.update()
