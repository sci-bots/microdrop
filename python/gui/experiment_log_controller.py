import os

class ExperimentLogController:
    def __init__(self, app):
        self.app = app
        
    def save(self):
        data = {"software version":self.app.version}
        if self.app.control_board.connected():
            data["control board name"] = self.app.control_board.hardware_version()
            data["control board hardware version"] = self.app.control_board.hardware_version()
            data["control board software version"] = self.app.control_board.hardware_version()
        data["notes"] = self.app.main_window_controller.textview_notes.get_buffer()
        self.app.experiment_log.add_data(data)
        log_path = self.app.experiment_log.save()

        # save the protocol and device
        self.app.protocol.save(os.path.join(log_path,"protocol"))
        self.app.dmf_device.save(os.path.join(log_path,"device"))
        self.app.experiment_log.plot()
        self.app.experiment_log.clear()
        self.app.main_window_controller.update()