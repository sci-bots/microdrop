import sys
import logging

import gtk
from path import path
from pygtkhelpers.utils import gsignal
from pygtkhelpers.forms import view_widgets, element_views, ElementBuilder, widget_for, FormView, IntegerBuilder
from pygtkhelpers.proxy import widget_proxies, GObjectProxy, proxy_for
from flatland.schema import String, Form, Integer, Float


VIEW_FILEPATH = 'filepath'
VIEW_DIRECTORY = 'directory'


def get_type_from_schema(schema):
        return type(schema(0).value)


class Filepath(String):
    pass


class Directory(String):
    pass


class FilepathWidget(gtk.HBox):
    gsignal('content-changed')
    mode = 'file'

    def __init__(self):
        gtk.HBox.__init__(self, spacing=3)
        self.set_border_width(6)
        self.set_size_request(250, -1)
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
                starting_dir = path(self.value)
                if starting_dir.isdir():
                    pass
                elif starting_dir.isfile():
                    starting_dir = starting_dir.abspath().parent
                else:
                    starting_dir = None
            except:
                starting_dir = None
        else:
            starting_dir = None
        if self.mode == 'file':
            response, filepath = self.browse_for_file('Select file path',
                        starting_dir=starting_dir)
        elif self.mode == 'directory':
            response, filepath = self.browse_for_file('Select directory',
                        action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                        starting_dir=starting_dir)
        else:
            raise ValueError, '[Filepath] Invalid mode: %s' % self.mode
        if response == gtk.RESPONSE_OK:
            logging.info('got new filepath: %s' % filepath)
            self.value = path(filepath).abspath()
            self.emit('content-changed')

    def on_btn_data_dir_browse_clicked(self, widget, data=None):
        app = get_app()
        response, options_dir = self.browse_for_file('Select data directory',
                    action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                    starting_dir=self.txt_data_dir.get_text())
        if response == gtk.RESPONSE_OK:
            logger.info('got new options_dir: %s' % options_dir)
            self.txt_data_dir.set_text(options_dir)

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


class DirectoryWidget(FilepathWidget):
    mode = 'directory'


class FilepathBuilder(ElementBuilder):
    default_style = 'browse'

    styles = {
        # <textbox> <browse button>
        'browse': FilepathWidget,
    }

    def build(self, widget, style, element, options):
        if style == 'browse':
            widget.set_size_request(-1, -1)
        return widget


class DirectoryBuilder(FilepathBuilder):
    default_style = 'browse'

    styles = {
        # <textbox> <browse button>
        'browse': DirectoryWidget,
    }


class FloatBuilder(IntegerBuilder):
    default_style = 'spin'

    styles = {
        'spin': gtk.SpinButton,
        'slider': gtk.HScale,
    }

    def build(self, widget, style, element, options):
        widget.set_digits(2)
        adj = widget.get_adjustment()
        min, max = sys.float_info.min, sys.float_info.max
        for v in element.validators:
            if hasattr(v, 'minimum'):
                min = v.minimum
            elif hasattr(v, 'maximum'):
                max = v.maximum
        args = (min, min, max, 0.1, 10.0)
        adj.set_all(*args)
        return widget


class FilepathProxy(GObjectProxy):
    """Proxy for a pygtkhelpers.ui.widgets.StringList.
    """
    signal_name = 'content-changed'

    def get_widget_value(self):
        return self.widget.value

    def set_widget_value(self, value):
        self.widget.value = value


VIEW_FLOAT = 'float'


#: Map of flatland element types to view types
element_views.update({
    Filepath: VIEW_FILEPATH,
    Directory: VIEW_DIRECTORY,
    Float: VIEW_FLOAT,
})


#: map of view types to flatland element types
view_widgets.update({
    VIEW_FILEPATH: FilepathBuilder(),
    VIEW_DIRECTORY: DirectoryBuilder(),
    VIEW_FLOAT: FloatBuilder(),
})


widget_proxies.update({
    FilepathWidget: FilepathProxy,
    DirectoryWidget: FilepathProxy,
})


if __name__ == '__main__':
    window = gtk.Window()
    form = Form.of(
        Integer.named('overlay_opacity').using(default=20, optional=True),
        Float.named('float_value').using(default=10.37, optional=True),
        Filepath.named('log_filepath').using(default='', optional=True),
        Directory.named('devices_directory').using(default='', optional=True)
    )
    FormView.schema_type = form
    view = FormView()
    for field in view.form.fields.values():
        field.proxy.set_widget_value(field.element.default_value)
    expander = gtk.Expander()
    expander.add(view.widget)
    window.add(expander)
    window.show_all()
