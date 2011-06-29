import gtk
from hardware.dmf_control_board import DmfControlBoard
from hardware.agilent_33220a import Agilent33220A
from gui.main_window_controller import MainWindowController
from gui.device_controller import DeviceController
from gui.protocol_controller import ProtocolController
from protocol import Protocol

class App:
    def __init__(self):
        self.realtime_mode = False
        self.control_board = DmfControlBoard()
        self.func_gen = None
        #self.func_gen = Agilent33220A()
        self.protocol = Protocol()
        self.builder = gtk.Builder()
        signals = {}
        self.main_window_controller = MainWindowController(self, self.builder, signals)
        self.device_controller = DeviceController(self, self.builder, signals)
        self.protocol_controller = ProtocolController(self, self.builder, signals)
        self.builder.connect_signals(signals)
        self.main_window_controller.main()

if __name__ == '__main__':
    app = App()