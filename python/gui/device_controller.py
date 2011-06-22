import os
import numpy as np
from device_view import DeviceView

class DeviceController:
    def __init__(self, app, builder, signals):
        self.app = app
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "right_click_popup.glade"))

        self.view = DeviceView(builder.get_object("device_view"))
        self.popup = builder.get_object("popup")
        signals["on_device_view_button_press_event"] = self.on_button_press
        signals["on_device_view_key_press_event"] = self.on_key_press
        signals["on_device_view_expose_event"] = self.view.on_expose

        self.map_electrode_id_to_channels = np.zeros(len(self.view.electrodes), int)
        k = 29
        for i in range(0, k):
            self.map_electrode_id_to_channels[i] = i
        self.map_electrode_id_to_channels[k] = k
        self.map_electrode_id_to_channels[k+1] = k
        self.map_electrode_id_to_channels[k+2] = k+1
        self.map_electrode_id_to_channels[k+3] = k+1
        self.map_electrode_id_to_channels[k+4] = k+2
        self.map_electrode_id_to_channels[k+5] = k+2

    def on_button_press(self, widget, event):
        self.view.widget.grab_focus()
        electrodes = self.view.electrodes
        for i in range(0,len(electrodes)):
            if electrodes[i].contains(event.x, event.y, self.view.scale):
                if event.button == 1:
                    state = self.app.protocol.state_of_all_channels()
                    channel = self.map_electrode_id_to_channels[i]
                    if state[channel]>0:
                        self.app.protocol.set_state_of_channel(channel, 0)
                    else:
                        self.app.protocol.set_state_of_channel(channel, 1)
                    self.update()
                    break
                elif event.button == 3:
                    self.popup.popup(None, None, None, event.button, event.time, data=None)
        return True

    def on_key_press(self, widget, data=None):
        pass
    
    def update(self):
        state = self.app.protocol.state_of_all_channels()
        for i in self.view.electrodes:
            channel = self.map_electrode_id_to_channels[i.id]
            if state[channel]>0:
                i.color = (1, 1, 1)
            else:
                i.color = (0, 0, 1)
        self.view.update()