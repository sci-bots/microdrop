import gtk
import gobject
from pygtkhelpers.delegates import WindowView, SlaveView
from pygtkhelpers.ui.objectlist import ObjectList, Column
from pygtkhelpers.utils import gsignal

# We need to call threads_init() to ensure correct gtk operation with
# multi-threaded code (needed for GStreamer).
gobject.threads_init()
gtk.gdk.threads_init()

from ..dict_as_attr_proxy import DictAsAttrProxy


class ListSelectView(SlaveView):
    """
    ListSelectView for selecting an item from a list.
    """
    gsignal('selection-changed', object)

    def __init__(self, items, column_name='name'):
        self.column_name = column_name
        self.items = items
        super(SlaveView, self).__init__()

    def create_ui(self):
        self.widget = gtk.VBox()
        columns = [Column(attr=self.column_name, sortable=True, editable=False,
                resizeable=True)]
        self.list_box = ObjectList(columns)
        for item in self.items:
            self.add_item(item)

        s = self.list_box.get_selection()
        s.set_mode(gtk.SELECTION_MULTIPLE)

        self.list_box.show_all()
        self.widget.pack_start(self.list_box)

    def add_item(self, item):
        item_object = DictAsAttrProxy({self.column_name: str(item)})
        self.list_box.append(item_object)

    def selected_items(self):
        return [i.as_dict.values()[0]
                for i in self.list_box.selected_items]

    def on_list_box__selection_changed(self, *args, **kwargs):
        self.emit('selection-changed', self.selected_items())


class TestWindow(WindowView):
    def create_ui(self):
        self.list_box = self.add_slave(ListSelectView(['hello', 'world']),
                'widget')

    def on_list_box__selection_changed(self, list_box, selected_items):
        print selected_items


if __name__ == '__main__':
    window_view = TestWindow()
    window_view.show_and_run()
