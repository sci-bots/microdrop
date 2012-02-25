import logging

import gtk
from path import path
from pygtkhelpers.utils import gsignal
from pygtkhelpers.forms import view_widgets, element_views, ElementBuilder, widget_for, FormView
from pygtkhelpers.proxy import widget_proxies, GObjectProxy, proxy_for
from flatland.schema import String, Form, Integer


VIEW_FILEPATH = 'filepath'


class Filepath(String):
    pass


class FilepathWidget(gtk.HBox):
    gsignal('content-changed')

    def __init__(self):
        gtk.HBox.__init__(self, spacing=3)
        self.set_border_width(6)
        self.set_size_request(250, 250)
        self.filepath_entry = gtk.Entry()
        self.filepath_entry.set_editable(False)
        self.browse_button = gtk.Button(label='Browse...')
        self.browse_button.connect('clicked', self.on_button_clicked)
        self.pack_start(self.filepath_entry, expand=True, fill=True)
        self.pack_start(self.browse_button, expand=False, fill=False)
        self.widget = proxy_for(self.filepath_entry)
        self.widget.connect_widget()
        self.show_all()

    def on_button_clicked(self, widget, data=None):
        if self.value:
            try:
                starting_dir = path(self.value).parent
                if not starting_dir.isdir():
                    starting_dir = None
            except:
                starting_dir = None
        else:
            starting_dir = None
        response, filepath = self.browse_for_file('Select file path',
                    starting_dir=starting_dir)
        if response == gtk.RESPONSE_OK:
            logging.info('got new filepath: %s' % filepath)
            self.value = path(filepath).abspath()
            self.emit('content-changed')

    def browse_for_file(self, title='Select file',
                            action=gtk.FILE_CHOOSER_ACTION_OPEN,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OPEN, gtk.RESPONSE_OK),
                            starting_dir=None):
        dialog = gtk.FileChooserDialog(title=title, action=action,
                                        buttons=buttons)
        if starting_dir:
            dialog.set_current_folder(starting_dir)
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            value = dialog.get_filename()
        else:
            value = None
        dialog.destroy()
        return response, value

    @property
    def value(self):
        return self.widget.get_widget_value()

    @value.setter
    def value(self, v):
        self.widget.set_widget_value(v)


class FilepathBuilder(ElementBuilder):
    default_style = 'browse'

    styles = {
        # <label> <textbox> <browse button>
        'browse': FilepathWidget,
    }

    def build(self, widget, style, element, options):
        if style == 'browse':
            widget.set_size_request(-1, 100)
        return widget


class FilepathProxy(GObjectProxy):
    """Proxy for a pygtkhelpers.ui.widgets.StringList.
    """
    signal_name = 'content-changed'

    def get_widget_value(self):
        return self.widget.value

    def set_widget_value(self, value):
        self.widget.value = value


#: Map of flatland element types to view types
element_views.update({
    Filepath: VIEW_FILEPATH,
})


#: map of view types to flatland element types
view_widgets.update({
    VIEW_FILEPATH: FilepathBuilder(),
})


widget_proxies.update({
    FilepathWidget: FilepathProxy,
})


if __name__ == '__main__':
    window = gtk.Window()
    form = Form.of(
        Integer.named('overlay_opacity').using(default=20, optional=True),
        Filepath.named('log_filepath').using(default='', optional=True)
    )
    FormView.schema_type = form
    view = FormView()
    for field in view.form.fields.values():
        field.proxy.set_widget_value(field.element.default_value)
    window.add(view.widget)
    window.show_all()
