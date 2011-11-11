import gtk


class MessageDialog(gtk.Window): 
    def info(self, message):
        md = gtk.MessageDialog(self, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, 
            gtk.BUTTONS_CLOSE, message)
        result = md.run()
        md.destroy()
        return result
        
    
    def erro(self, message):
        md = gtk.MessageDialog(self, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, 
            gtk.BUTTONS_CLOSE, message)
        result = md.run()
        md.destroy()
        return result
    
    
    
    def ques(self, message):
        md = gtk.MessageDialog(self, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, 
            gtk.BUTTONS_OK_CANCEL, message)
        result = md.run()
        md.destroy()
        return result
    
    
    def warn(self, message):
        md = gtk.MessageDialog(self, 
            gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_WARNING, 
            gtk.BUTTONS_CLOSE, message)
        result = md.run()
        md.destroy()
        return result
