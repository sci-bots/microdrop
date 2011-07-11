import os, gtk
import numpy as np
from xml.etree import ElementTree as et
from pyparsing import Literal, Combine, Optional, Word, Group, OneOrMore, nums
from dmf_device_view import DmfDeviceView

class EditElectrodeDialog:
    def __init__(self, electrode):
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "edit_electrode_dialog.glade"))
        self.dialog = builder.get_object("edit_electrode_dialog")
        self.textentry_channels = builder.get_object("textentry_channels")
        self.electrode = electrode

        # TODO: set default value

        channel_list = ""
        for i in electrode.channels:
            channel_list += str(i) + ','
        channel_list = channel_list[:-1]
        self.textentry_channels.set_text(channel_list)
        
    def run(self):
        response = self.dialog.run()
        if response == gtk.RESPONSE_OK:
            channel_list = self.textentry_channels.get_text()
            channels = channel_list.split(',')

            try: # convert to integers
                for i in range(0,len(channels)):
                    channels[i] = int(channels[i])
                self.electrode.channels = channels
            except:
                print "error"
        self.dialog.hide()
        return response

class DmfDeviceController:
    def __init__(self, app, builder, signals):
        self.app = app
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "right_click_popup.glade"))
        self.view = DmfDeviceView(builder.get_object("dmf_device_view"),
                                  self.app.dmf_device)
        self.model = self.app.dmf_device
        self.popup = builder.get_object("popup")
        self.last_electrode_clicked = None

        signals["on_dmf_device_view_button_press_event"] = self.on_button_press
        signals["on_dmf_device_view_key_press_event"] = self.on_key_press
        signals["on_dmf_device_view_expose_event"] = self.view.on_expose
        signals["on_menu_load_dmf_device_activate"] = self.on_load_dmf_device
        signals["on_menu_import_from_svg_file_activate"] = \
                self.on_import_from_svg_file
        signals["on_menu_edit_electrode_activate"] = self.on_edit_electrode

        self.model.add_electrode_rect(24,16,1.9) #32
        self.model.add_electrode_rect(24,14,1.9) # 31
        self.model.add_electrode_rect(24,12,1.9) # 30
        self.model.add_electrode_rect(22,6,5.9) # 29
        self.model.add_electrode_rect(22,0,5.9) # 28
        self.model.add_electrode_rect(22,16,1.9) # 27
        self.model.add_electrode_rect(20,16,1.9) # 26
        self.model.add_electrode_rect(6,0,5.9) # 25
        self.model.add_electrode_rect(16,9,1.9,0.9) # 24
        self.model.add_electrode_rect(16,10,1.9,0.9) # 23
        self.model.add_electrode_rect(16,11,1.9,0.9) # 22
        self.model.add_electrode_rect(16,12,1.9,0.9) # 21
        self.model.add_electrode_rect(16,13,1.9,0.9) # 20
        self.model.add_electrode_rect(6,6,5.9) # 19
        self.model.add_electrode_rect(8,12,1.9) # 18
        self.model.add_electrode_rect(8,14,1.9) # 17
        self.model.add_electrode_rect(12,16,1.9) # 16
        self.model.add_electrode_rect(10,16,1.9) # 15
        self.model.add_electrode_rect(8,16,1.9) # 14
        self.model.add_electrode_rect(14,16,1.9) # 13
        self.model.add_electrode_rect(16,16,1.9) # 12
        self.model.add_electrode_rect(16,14,1.9) # 11
        self.model.add_electrode_rect(18,16,1.9) # 10
        self.model.add_electrode_rect(16,18,1.9) # 9
        self.model.add_electrode_rect(16,20,1.9) # 8
        self.model.add_electrode_rect(16,22,1.9) # 7
        self.model.add_electrode_rect(14.5,24.25,1.4) # 6
        self.model.add_electrode_rect(16,24,1.9) # 5
        self.model.add_electrode_rect(18,24.25,1.4) # 4
        self.model.add_electrode_rect(13,24.25,1.4) # 3
        self.model.add_electrode_rect(19.5,24.25,1.4) # 3
        self.model.add_electrode_rect(21,22,5.9) # 2
        self.model.add_electrode_rect(7,22,5.9) # 2
        self.model.add_electrode_rect(1,22,5.9) # 1
        self.model.add_electrode_rect(27,22,5.9) # 1

        k = 29
        for i in range(0, k):
            self.model.connect(i,i)
        self.model.connect(k, k)
        self.model.connect(k+1, k)
        self.model.connect(k+2, k+1)
        self.model.connect(k+3, k+1)
        self.model.connect(k+4, k+2)
        self.model.connect(k+5, k+2)
        self.view.fit_device()

    def on_button_press(self, widget, event):
        self.view.widget.grab_focus()
        for electrode in self.model.electrodes.values():
            if electrode.contains(event.x/self.view.scale-self.view.offset[0],
                                  event.y/self.view.scale-self.view.offset[1]):
                self.last_electrode_clicked = electrode
                if event.button == 1:
                    state = self.app.protocol.state_of_all_channels()
                    if len(electrode.channels): 
                        for channel in electrode.channels:
                            if state[channel]>0:
                                self.app.protocol.set_state_of_channel(channel, 0)
                            else:
                                self.app.protocol.set_state_of_channel(channel, 1)
                    else:
                        #TODO error box
                        print "error (no channel assigned to electrode)"
                elif event.button == 3:
                    self.popup.popup(None, None, None, event.button,
                                     event.time, data=None)
                break
        self.app.main_window_controller.update()
        return True

    def on_key_press(self, widget, data=None):
        pass
    
    def on_load_dmf_device(self, widget, data=None):
        pass
        
    def on_import_from_svg_file(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title=None,
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            
            # Pyparsing grammar for svg:
            #
            # This code is based on Don C. Ingle's svg2py program, available at:
            # http://annarchy.cairographics.org/svgtopycairo/
            dot = Literal(".")
            comma = Literal(",").suppress()
            floater = Combine(Optional("-") + Word(nums) + dot + Word(nums))
            couple = floater + comma + floater
            M_command = "M" + Group(couple)
            C_command = "C" + Group(couple + couple + couple)
            L_command = "L" + Group(couple)
            Z_command = "Z"
            svgcommand = M_command | C_command | L_command | Z_command
            phrase = OneOrMore(Group(svgcommand))
            
            try:
                tree = et.parse(filename)
                self.model.clear()

                ns = "http://www.w3.org/2000/svg" #The XML namespace.
                for group in tree.getiterator('{%s}g' % ns):
                    for e in group.getiterator('{%s}path' % ns):
                        is_closed = False
                        p = e.get("d")

                        tokens = phrase.parseString(p.upper())
                        
                        # check if the path is closed
                        if tokens[-1][0]=='Z':
                            is_closed = True
                        else: # or if the start/end points are the same
                            try:
                                start_point = tokens[0][1].asList()
                                end_point = tokens[-1][1].asList()
                                if start_point==end_point:
                                    is_closed = True
                            except ValueError:
                                print "ValueError"
                        if is_closed:
                            path = []
                            for step in tokens:
                                command = step[0]
                                if command=="M" or command=="L":
                                    x,y = step[1].asList()
                                    path.append({'command':step[0],
                                                 'x':x, 'y':y})
                                elif command=="Z":
                                    path.append({'command':step[0]})
                                else:
                                    print "error"
                            self.model.add_electrode_path(path)
                self.view.fit_device()
            except:
                #TODO: error box
                print "error"
                        
        dialog.destroy()
        self.app.main_window_controller.update()
        
    def on_edit_electrode(self, widget, data=None):
        EditElectrodeDialog(self.last_electrode_clicked).run()
        self.app.main_window_controller.update()
    
    def update(self):
        state_of_all_channels = self.app.protocol.state_of_all_channels()
        for id, electrode in self.model.electrodes.iteritems():
            channels = self.model.electrodes[id].channels
            if channels:
                # get the state(s) of the channel(s) connected to this electrode
                states = state_of_all_channels[channels]
    
                # if all of the states are the same
                if len(np.nonzero(states==states[0])[0])==len(states):
                    electrode.state = states[0]
                    if states[0]>0:
                        self.view.electrode_color[id] = (1,1,1)
                    else:
                        self.view.electrode_color[id] = (0,0,1)
                else:
                    #TODO: this could be used for resistive heating 
                    print "error, not supported yet"
            else:
                self.view.electrode_color[id] = (1,0,0)
                
        self.view.update()