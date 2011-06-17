from protocol import Protocol, Step

class ProtocolEditor():
    def __init__(self, app, builder):
        self.app = app
        self.button_first_step = builder.get_object("button_first_step")
        self.button_prev_step = builder.get_object("button_prev_step")
        self.button_next_step = builder.get_object("button_next_step")
        self.button_last_step = builder.get_object("button_last_step")
        self.button_insert_step = builder.get_object("button_insert_step")
        self.button_delete_step = builder.get_object("button_delete_step")
        self.textbox_step_number = builder.get_object("textbox_step_number")
        self.textbox_step_time = builder.get_object("textbox_step_time")

    def on_insert_step(self, widget, data=None):
        self.app.protocol.insert_step()

    def on_delete_step(self, widget, data=None):
        pass

    def on_first_step(self, widget, data=None):
        pass

    def on_prev_step(self, widget, data=None):
        pass

    def on_next_step(self, widget, data=None):
        pass

    def on_last_step(self, widget, data=None):
        pass
