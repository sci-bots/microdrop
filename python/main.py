import gtk
from hardware.dmf_control_board import DmfControlBoard
from gui.main_window_controller import MainWindowController
from gui.device_controller import DeviceController
from gui.protocol_controller import ProtocolController
from protocol import Protocol

class App:
    def __init__(self):
        self.realtime_mode = False
        self.control_board = DmfControlBoard()
        self.func_gen = None
        self.protocol = Protocol()
        
        builder = gtk.Builder()
        signals = {}
        self.main_window_controller = MainWindowController(self, builder, signals)
        self.device_controller = DeviceController(self, builder, signals)
        self.protocol_controller = ProtocolController(self, builder, signals)

        builder.connect_signals(signals)
        self.main_window_controller.main()

if __name__ == '__main__':
    app = App()