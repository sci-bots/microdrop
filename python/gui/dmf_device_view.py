import gtk

class DmfDeviceView:
    def __init__(self, widget, model):
        self.widget = widget
        self.model = model
        x, y, width, height = self.widget.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.widget.window, width, height)
        self.pixmap.draw_rectangle(self.widget.get_style().black_gc,
                                   True, 0, 0, width, height)
        self.scale = 1
        self.offset = (0,0)
        self.electrode_color = {}

    # device view events
    def on_expose(self, widget, event):
        x , y, width, height = event.area
        widget.window.draw_drawable(widget.get_style().white_gc,
                                    self.pixmap, x, y, x, y, width, height)
        return False

    def update(self):
        x, y, width, height = self.widget.get_allocation()
        self.pixmap.draw_rectangle(self.widget.get_style().black_gc,
                                   True, 0, 0, width, height)
        for id, electrode in self.model.electrodes.iteritems():
            if self.electrode_color.keys().count(id):
                cr = self.pixmap.cairo_create()
                x,y = self.offset
                cr.translate(x,y)
                cr.scale(self.scale, self.scale)
                self.draw_electrode(electrode, cr)
                r, g, b = self.electrode_color[id]
                cr.set_source_rgb(r, g, b)
                cr.fill()
        self.widget.queue_draw()

    def draw_electrode(self, electrode, cr):
        cairo_commands = ""

        # TODO: make this work for relative paths (small letter commands)
        for step in electrode.path:
            if step['command'] == "M":
                cairo_commands += "cr.move_to(%s,%s);" % (step['x'],step['y'])
            #TODO: curves
            """
            if step['command'] == "C":
                 
                cairo_commands += "cr.curve_to(%s,%s,%s,%s,%s,%s);" % (c[0],c[1],c[2],c[3],c[4],c[5])
                pass
            """
            if step['command'] == "L":
                cairo_commands += "cr.line_to(%s,%s);" % (step['x'],step['y'])
            if step['command'] == "Z":
                cairo_commands += "cr.close_path();"
        exec(cairo_commands)