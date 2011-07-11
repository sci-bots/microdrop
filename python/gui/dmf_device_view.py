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

    def fit_device(self, padding=None):
        if padding is None:
            padding = 10
        widget = self.widget.get_allocation()
        device = self.model.geometry()
        scale_x = (widget[2]-2*padding)/device[2]
        scale_y = (widget[3]-2*padding)/device[3]
        self.scale = min(scale_x, scale_y)
        if scale_x < scale_y: # center device vertically
            self.offset = (-device[0]+padding/self.scale,
                           -device[1]+padding/self.scale+ \
                           ((widget[3]-2*padding)/self.scale-device[3])/2)
        else:  # center device horizontally
            self.offset = (-device[0]+padding/self.scale+ \
                           ((widget[2]-2*padding)/self.scale-device[2])/2,
                           -device[1]+padding/self.scale)

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
                cr.scale(self.scale, self.scale)
                cr.translate(x,y)
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