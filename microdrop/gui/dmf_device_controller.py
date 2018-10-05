import logging
import traceback

from flatland import Form
from lxml import etree
from microdrop_device_converter import convert_device_to_svg
from microdrop_utility import copytree
from microdrop_utility.gui import yesno
from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.ui.extra_widgets import Directory
from pygtkhelpers.ui.notebook import add_filters
import gtk
import path_helpers as ph
import pygtkhelpers as pgh
import pygtkhelpers.ui.dialogs
import svg_model as sm

from ..app_context import get_app
from ..default_paths import DEVICES_DIR, update_recent, update_recent_menu
from ..dmf_device import DmfDevice, ELECTRODES_XPATH
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_helpers import AppDataController
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ScheduleRequest, emit_signal)

logger = logging.getLogger(__name__)

PluginGlobals.push_env('microdrop')

# Define name of device file.  Name of device is inferred from name of parent
# directory when device is loaded.
OLD_DEVICE_FILENAME = 'device'
DEVICE_FILENAME = 'device.svg'


def select_device_output_path(default_path=None, **kwargs):
    '''
    .. versionadded:: X.X.X

    Returns
    -------
    path_helpers.path
        Path to selected DMF device file output path.

    Raises
    ------
    IOError
        If dialog was closed without selecting an output path.
    '''
    dialog = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                   buttons=(gtk.STOCK_SAVE, gtk.RESPONSE_OK,
                                            gtk.STOCK_CANCEL,
                                            gtk.RESPONSE_CANCEL), **kwargs)
    dialog.props.do_overwrite_confirmation = True

    if default_path is None:
        default_path = 'device.svg'
    default_path = ph.path(default_path).realpath()
    if default_path.parent:
        dialog.set_current_folder(default_path.parent.abspath())
    dialog.set_current_name(default_path.name)

    file_filter = gtk.FileFilter()
    file_filter.set_name('DMF device layout files (*.svg)')
    file_filter.add_pattern('*.svg')
    file_filter.add_pattern('*.SVG')

    dialog.add_filter(file_filter)

    try:
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            return dialog.get_filename()
        else:
            raise IOError('No filename selected.')
    finally:
        dialog.destroy()


def select_device_path(default_path=None, **kwargs):
    '''
    .. versionadded:: X.X.X

    Returns
    -------
    path_helpers.path
        Path to selected existing DMF device file.

    Raises
    ------
    IOError
        If dialog was closed without selecting a device file.
    '''
    dialog = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                   buttons=(gtk.STOCK_OPEN, gtk.RESPONSE_OK,
                                            gtk.STOCK_CANCEL,
                                            gtk.RESPONSE_CANCEL), **kwargs)
    if default_path is not None:
        default_path = ph.path(default_path).realpath()
        if default_path.isfile():
            dialog.select_filename(default_path)
        elif default_path.isdir():
            dialog.set_current_folder(default_path)

    file_filter = gtk.FileFilter()
    file_filter.set_name('DMF device layout files (*.svg)')
    file_filter.add_pattern('*.svg')
    file_filter.add_pattern('*.SVG')

    dialog.add_filter(file_filter)

    try:
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            return ph.path(dialog.get_filename())
        else:
            raise IOError('No filename selected.')
    finally:
        dialog.destroy()


class DmfDeviceController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    AppFields = Form.of(Directory.named('device_directory')
                        .using(default='', optional=True))

    def __init__(self):
        self.name = "microdrop.gui.dmf_device_controller"
        self.previous_device_dir = None
        self._modified = False

    @property
    def modified(self):
        return self._modified

    @modified.setter
    def modified(self, value):
        '''
        .. versionchanged:: X.X.X
            Do not change sensitivity of deprecated _device rename_ menu item.
        '''
        self._modified = value
        if getattr(self, 'menu_save_dmf_device', None):
            self.menu_save_dmf_device.set_sensitive(value)

    @gtk_threadsafe
    def on_app_options_changed(self, plugin_name):
        try:
            if plugin_name == self.name:
                values = self.get_app_values()
                if 'device_directory' in values:
                    self.apply_device_dir(values['device_directory'])
        except (Exception,):
            map(_L().info, traceback.format_exc().splitlines())
            raise

    def apply_device_dir(self, device_directory):
        '''
        .. versionchanged:: 2.21
            Use :func:`path_helpers.resource_copytree` to support when copying
            from a module stored in a ``.zip`` archive or ``.egg`` file.
        '''
        app = get_app()

        # if the device directory is empty or None, set a default
        if not device_directory:
            device_directory = (ph.path(app.config.data['data_dir'])
                                .joinpath('devices'))
            self.set_app_values({'device_directory': device_directory})

        if self.previous_device_dir and (device_directory ==
                                         self.previous_device_dir):
            # If the data directory hasn't changed, we do nothing
            return False

        device_directory = ph.path(device_directory)
        if self.previous_device_dir:
            device_directory.makedirs_p()
            if device_directory.listdir():
                result = yesno('Merge?', '''\
Target directory [%s] is not empty.  Merge contents with
current devices [%s] (overwriting common paths in the target
directory)?''' % (device_directory, self.previous_device_dir))
                if not result == gtk.RESPONSE_YES:
                    return False

            original_directory = ph.path(self.previous_device_dir)
            for d in original_directory.dirs():
                copytree(d, device_directory.joinpath(d.name))
            for f in original_directory.files():
                f.copyfile(device_directory.joinpath(f.name))
            original_directory.rmtree()
        elif not device_directory.isdir():
            # if the device directory doesn't exist, copy the skeleton dir
            if device_directory.parent:
                device_directory.parent.makedirs_p()
            # XXX Use `path_helpers.resource_copytree` to support when copying
            # from a module stored in a `.zip` archive or `.egg` file.
            ph.resource_copytree('microdrop', 'devices', device_directory)
        self.previous_device_dir = device_directory
        return True

    def on_plugin_enable(self):
        '''
        .. versionchanged:: 2.11.2
            Use :func:`gtk_threadsafe` decorator to wrap GTK code blocks,
            ensuring the code runs in the main GTK thread.

        .. versionchanged:: X.X.X
            Remove references to deprecated _device rename_ menu item.
        '''
        app = get_app()

        app.dmf_device_controller = self
        defaults = self.get_default_app_options()
        data = app.get_data(self.name)
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        app.set_data(self.name, data)
        emit_signal('on_app_options_changed', [self.name])

        self.menu_detect_connections = \
            app.builder.get_object('menu_detect_connections')
        self.menu_import_dmf_device = \
            app.builder.get_object('menu_import_dmf_device')
        self.menu_load_dmf_device = \
            app.builder.get_object('menu_load_dmf_device')
        self.menu_save_dmf_device = \
            app.builder.get_object('menu_save_dmf_device')
        self.menu_save_dmf_device_as = \
            app.builder.get_object('menu_save_dmf_device_as')

        app.signals["on_menu_detect_connections_activate"] = \
            self.on_detect_connections
        app.signals["on_menu_import_dmf_device_activate"] = \
            self.on_import_dmf_device
        app.signals["on_menu_load_dmf_device_activate"] = \
            self.on_load_dmf_device
        app.signals["on_menu_save_dmf_device_activate"] = \
            self.on_save_dmf_device
        app.signals["on_menu_save_dmf_device_as_activate"] = \
            self.on_save_dmf_device_as

        @gtk_threadsafe
        def _init_ui():
            # disable menu items until a device is loaded
            self.menu_detect_connections.set_sensitive(False)
            self.menu_save_dmf_device.set_sensitive(False)
            self.menu_save_dmf_device_as.set_sensitive(False)

        _init_ui()

    def on_protocol_pause(self):
        pass

    def on_app_exit(self):
        self.save_check()

    def _update_recent(self, recent_path):
        '''
        Update the recent devices list in the config and recent menu.

        Parameters
        ----------
        recent_path : str
            Path to device file to add to recent list.

        Returns
        -------
        list[str]
            List of recent device paths.
        '''
        app = get_app()
        recent_devices = update_recent('dmf_device', app.config, recent_path)

        @gtk_threadsafe
        def _on_menu_activate(device_path, *args):
            self.load_device(device_path)

        menu_head = app.builder.get_object('menu_recent_dmf_devices')
        update_recent_menu(recent_devices, menu_head, _on_menu_activate)
        return recent_devices

    def load_device(self, file_path, **kwargs):
        '''
        Load device file.

        Parameters
        ----------
        file_path : str
            A MicroDrop device `.svg` file or a (deprecated) MicroDrop 1.0
            device.


        .. versionchanged:: X.X.X
            Save path to loaded SVG device file in config file (rather than
            just the device name).
        '''
        logger = _L()  # use logger with method context
        app = get_app()
        self.modified = False
        device = app.dmf_device
        file_path = ph.path(file_path)
        try:
            logger.info('load_device: %s' % file_path)

            # Load device from SVG file.
            device = DmfDevice.load(file_path, name=file_path.namebase,
                                    **kwargs)
            if DEVICES_DIR.relpathto(file_path).splitall()[0] == '..':
                # Device is not in default devices directory. Store absolute
                # filepath.
                app.config['dmf_device']['filepath'] = str(file_path.abspath())
            else:
                # Device is within default devices directory.  Store filepath
                # relative to device directory.
                app.config['dmf_device']['filepath'] = \
                    str(DEVICES_DIR.relpathto(file_path))
            app.config.save()
            emit_signal("on_dmf_device_swapped", [app.dmf_device, device])
            # Set loaded device as first position in recent devices menu.
            self._update_recent(file_path)
        except Exception:
            logger.error('Error loading device.', exc_info=True)

    def save_check(self):
        app = get_app()
        if self.modified:
            result = yesno('Device %s has unsaved changes.  Save now?' %
                           app.dmf_device.name)
            if result == gtk.RESPONSE_YES:
                self.save_dmf_device()

    def save_dmf_device(self, save_as=False):
        '''
        Save device configuration.

        If `save_as=True`, we are saving a copy of the current device with a
        new name.


        .. versionchanged:: X.X.X
            Deprecate ``rename`` keyword argument.  Use standard file chooser
            dialog to select device output path.
        '''
        app = get_app()
        default_path = app.config['dmf_device'].get('filepath')

        if save_as or default_path is None:
            default_path = (DEVICES_DIR.joinpath(ph.path(default_path).name)
                            if default_path
                            else DEVICES_DIR.joinpath('New device.svg'))
            try:
                output_path = \
                    select_device_output_path(title='Please select location to'
                                              ' save device',
                                              default_path=default_path)
            except IOError:
                _L().debug('No output path was selected.')
                return
        else:
            output_path = default_path

        output_path = ph.path(output_path)

        # Convert device to SVG string.
        svg_unicode = app.dmf_device.to_svg()

        # Save the device to the new target directory.
        with output_path.open('wb') as output:
            output.write(svg_unicode)

        # Set saved device as first position in recent devices menu.
        self._update_recent(output_path)

        # Reset modified status, since save acts as a checkpoint.
        self.modified = False

        # Notify plugins that device has been saved.
        emit_signal('on_dmf_device_saved', [app.dmf_device,
                                            str(output_path)])

        self.load_device(output_path)
        return output_path

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.gui.config_controller',
                                    self.name),
                    ScheduleRequest('microdrop.gui.main_window_controller',
                                    self.name)]
        elif function_name == 'on_dmf_device_swapped':
            return [ScheduleRequest('microdrop.app', self.name),
                    ScheduleRequest('microdrop.gui.protocol_controller',
                                    self.name)]
        return []

    # GUI callbacks
    def on_load_dmf_device(self, widget, data=None):
        '''
        .. versionchanged:: X.X.X
            Use `select_device_path()` function to select device SVG file.
        '''
        self.save_check()
        try:
            device_path = select_device_path(title='Please select MicroDrop '
                                             'device to open',
                                             default_path=DEVICES_DIR)
            self.load_device(device_path)
        except IOError:
            # No device was selected to load.
            pass

    @gtk_threadsafe
    def on_import_dmf_device(self, widget, data=None):
        self.save_check()
        dialog = gtk.FileChooserDialog(title="Import device",
                                       action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                       buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        add_filters(dialog, [{'name': 'DMF device version 0.3.0 (device)',
                              'pattern': 'device'}])
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            try:
                self.import_device(filename)
            except Exception, e:
                _L().error('Error importing device. %s', e, exc_info=True)

    def import_device(self, input_device_path):
        '''
        .. versionchanged:: X.X.X
            Display file chooser dialog to select output path for imported
            device file.
        '''
        input_device_path = ph.path(input_device_path).realpath()
        default_path = (input_device_path.parent
                        .joinpath(input_device_path.namebase + '.svg'))
        try:
            output_path = \
                select_device_output_path(title='Please select output path for'
                                          ' imported device',
                                          default_path=default_path)
        except IOError:
            _L().debug('No output path was selected.')
        else:
            convert_device_to_svg(input_device_path, output_path,
                                  use_svg_path=True, detect_connections=True,
                                  extend_mm=.5, overwrite=True)
            self.load_device(output_path)

    def on_detect_connections(self, widget, data=None):
        '''
        Auto-detect adjacent electrodes in device and save updated SVG to
        device file path.
        '''
        app = get_app()
        svg_source = ph.path(app.dmf_device.svg_filepath)

        # Check for existing `Connections` layer.
        xml_root = etree.parse(svg_source)
        connections_xpath = '//svg:g[@inkscape:label="Connections"]'
        connections_groups = xml_root.xpath(connections_xpath,
                                            namespaces=sm.INKSCAPE_NSMAP)

        if connections_groups:
            # Existing "Connections" layer found in source SVG.
            # Prompt user to overwrite.
            response = pgh.ui.dialogs.yesno('"Connections" layer already '
                                            'exists in device file.\n\n'
                                            'Overwrite?',
                                            parent=app.main_window_controller
                                            .view)
            if response == gtk.RESPONSE_NO:
                return

        # Auto-detect adjacent electrodes from SVG paths and polygons from
        # `Device` layer.
        connections_svg = \
            sm.detect_connections\
            .auto_detect_adjacent_shapes(svg_source,
                                         shapes_xpath=ELECTRODES_XPATH)

        # Remove existing "Connections" layer and merge new "Connections" layer
        # with original SVG.
        output_svg = (sm.merge
                      .merge_svg_layers([sm.remove_layer(svg_source,
                                                         'Connections'),
                                         connections_svg]))

        with svg_source.open('w') as output:
            output.write(output_svg.getvalue())

    @gtk_threadsafe
    def on_save_dmf_device(self, widget, data=None):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.save_dmf_device()

    @gtk_threadsafe
    def on_save_dmf_device_as(self, widget, data=None):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.save_dmf_device(save_as=True)

    @gtk_threadsafe
    def on_dmf_device_changed(self, dmf_device):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.modified = True

    @gtk_threadsafe
    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        '''
        .. versionchanged:: 2.11.2
            Wrap with :func:`gtk_threadsafe` decorator to ensure the code runs
            in the main GTK thread.
        '''
        self.menu_detect_connections.set_sensitive(True)
        self.menu_save_dmf_device_as.set_sensitive(True)


PluginGlobals.pop_env()
