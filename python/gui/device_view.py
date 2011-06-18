import gtk
import math

class DeviceView:
    def __init__(self, app, builder):
        self.app = app
        self.widget = builder.get_object("device_view")
        x, y, width, height = self.widget.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.widget.window, width, height)
        self.pixmap.draw_rectangle(self.widget.get_style().black_gc,
                                   True, 0, 0, width, height)

        self.scale = 10
        self.electrodes = [Electrode(6,0,5.9), # 25
                           Electrode(6,6,5.9), # 19
                           Electrode(8,12,1.9), # 18
                           Electrode(8,14,1.9), # 17
                           Electrode(8,16,1.9), # 14
                           Electrode(10,16,1.9), # 15
                           Electrode(12,16,1.9), # 16
                           Electrode(14,16,1.9), # 13

                           Electrode(16,9,1.9,0.9), # 24
                           Electrode(16,10,1.9,0.9), # 23
                           Electrode(16,11,1.9,0.9), # 22
                           Electrode(16,12,1.9,0.9), # 21
                           Electrode(16,13,1.9,0.9), # 20
                           Electrode(16,14,1.9), # 11
                           
                           Electrode(16,16,1.9), # 12
                           Electrode(18,16,1.9), # 10
                           Electrode(20,16,1.9), # 26
                           Electrode(22,16,1.9), # 27
                           Electrode(24,16,1.9), # 32
                           Electrode(24,14,1.9), # 31
                           Electrode(24,12,1.9), # 30
                           Electrode(22,0,5.9), # 28
                           Electrode(22,6,5.9), # 29

                           Electrode(16,18,1.9), # 9
                           Electrode(16,20,1.9), # 8
                           Electrode(16,22,1.9), # 7
                           Electrode(16,24,1.9), # 5

                           Electrode(14.5,24.25,1.4), # 6
                           Electrode(13,24.25,1.4), # 3
                           Electrode(7,22,5.9), # 2
                           Electrode(1,22,5.9), # 1
                           Electrode(18,24.25,1.4), # 6
                           Electrode(19.5,24.25,1.4), # 3
                           Electrode(21,22,5.9), # 2
                           Electrode(27,22,5.9), # 1
                          ]

        for i in range(0,len(self.electrodes)):
            self.electrodes[i].x += 5 # x offset
            self.electrodes[i].y += 5 # y offset
        self.update()

    # device view events
    def on_expose(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().white_gc,
                                    self.pixmap, x, y, x, y, width, height)
        return False

    def on_button_press(self, widget, event):
        self.widget.grab_focus()
        state = self.app.state_of_all_electrodes()
        for i in range(0,len(self.electrodes)):
            if self.electrodes[i].contains(event.x, event.y, self.scale):
                if event.button == 1:
                    if state[i]>0:
                        state[i] = 0
                    else:
                        state[i] = 1
        self.app.set_state_of_all_electrodes(state)
        self.update()
        return True

    def on_key_press(self):
        pass

    def update(self):
        state = self.app.state_of_all_electrodes()
        cr = self.pixmap.cairo_create()
        for i in range(0,len(self.electrodes)):
            if state[i]==0:
                self.draw_electrode(self.electrodes[i], cr)
        cr.set_source_rgb(0, 0, 1)
        cr.fill()

        cr = self.pixmap.cairo_create()
        for i in range(0,len(self.electrodes)):
            if state[i]>0:
                self.draw_electrode(self.electrodes[i], cr)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
        self.widget.queue_draw()

    def draw_electrode(self, e, cr):
        x, y, w, h = e.get_x_y_w_h()
        cr.rectangle(self.scale*x, self.scale*y,
                     self.scale*w, self.scale*h)

class Electrode:
    def __init__(self, x, y, width, height=None):
        self.x = x
        self.y = y
        self.width = width
        if height is None:
            self.height = width
        else:
            self.height = height

    def get_x_y_w_h(self):
        return (self.x, self.y, self.width, self.height)

    def contains(self, x, y, scale):
        if x>scale*self.x and x<scale*(self.x+self.width) and \
           y>scale*self.y and y<scale*(self.y+self.height):
            return True
        else:
            return False
