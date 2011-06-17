from gui.main_window import MainWindow

class App:
   def __init__(self):
        self.main_window = MainWindow(self)
        self.func_gen = None
        self.controller = None

if __name__ == '__main__':
    app = App()
