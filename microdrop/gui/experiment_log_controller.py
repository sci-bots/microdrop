'''
.. versionchanged:: 2.32.1
    Remove experiment log window.
'''
import hashlib
import json
import logging
import zipfile

from logging_helpers import _L
from markdown2pango import markdown2pango
from path_helpers import path
from pygtkhelpers.gthreads import gtk_threadsafe
import deepdiff
import gtk

from .. import __version__
from ..app_context import get_app
from ..default_paths import EXPERIMENT_LOG_DIR
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, get_service_names,
                              get_service_instance_by_name)
from .dmf_device_controller import DEVICE_FILENAME

logger = logging.getLogger(__name__)


def experiment_info():
    '''
    .. versionadded:: 2.34

    Returns
    -------
    dict
        MicroDrop state, including application version, plugin versions, and
        device and protocol names.
    '''
    app = get_app()

    data = {'software version': __version__}
    if hasattr(app.dmf_device, 'name'):
        data['device name'] = app.dmf_device.name
    if hasattr(app.protocol, 'name'):
        data['protocol name'] = app.protocol.name

    plugin_versions = {}
    for name in get_service_names(env='microdrop.managed'):
        service = get_service_instance_by_name(name)
        if service._enable:
            plugin_versions[name] = str(service.version)
    data['plugins'] = plugin_versions
    return data


PluginGlobals.push_env('microdrop')


def archive_dialog(**kwargs):
    '''
    .. versionadded:: 2.34

    Returns
    -------
    path_helpers.path
        Path to selected experiment archive output path.

    Raises
    ------
    IOError
        If dialog was closed without selecting an output path.
    '''
    dialog = gtk.FileChooserDialog(**kwargs)
    dialog.props.do_overwrite_confirmation = True

    file_filter = gtk.FileFilter()
    file_filter.set_name('MicroDrop experiment (*.zip)')
    file_filter.add_pattern('*.zip')
    file_filter.add_pattern('*.ZIP')

    dialog.add_filter(file_filter)
    return dialog


def select_output_archive(default_path=None, **kwargs):
    '''
    .. versionadded:: 2.34

    Returns
    -------
    path_helpers.path
        Path to selected experiment archive output path.

    Raises
    ------
    IOError
        If dialog was closed without selecting an output path.
    '''
    dialog = archive_dialog(action=gtk.FILE_CHOOSER_ACTION_SAVE,
                            buttons=(gtk.STOCK_SAVE, gtk.RESPONSE_OK,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL),
                            **kwargs)
    dialog.props.do_overwrite_confirmation = True

    if default_path is not None:
        default_path = path(default_path).realpath()
        if default_path.parent:
            dialog.set_current_folder(default_path.parent.abspath())
        dialog.set_current_name(default_path.name)
    else:
        dialog.set_current_name('New experiment.zip')

    try:
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            return dialog.get_filename()
        else:
            raise IOError('No filename selected.')
    finally:
        dialog.destroy()


def save_experiment(log_dir, output_path):
    '''
    .. versionadded:: 2.34
        Save experiment log directory to output archive.

    Parameters
    ----------
    log_dir : str
        Path to log directory to save to archive.
    output_path : str
        Output path for zip archive.
    '''
    log_dir = path(log_dir)
    app = get_app()

    # Export protocol as JSON.
    protocol_json = app.protocol.to_json()

    # Convert device to SVG string.
    svg_unicode = app.dmf_device.to_svg()

    logger = _L()
    with zipfile.ZipFile(output_path, 'w') as output:
        for file_i in log_dir.walkfiles():
            logger.debug('write `%s` to `%s`', file_i.realpath(), output_path)
            output.write(file_i, log_dir.relpathto(file_i))

        # Save the device to the archive.
        output.writestr(DEVICE_FILENAME, svg_unicode)
        # Save the protocol to the archive.
        output.writestr('protocol.json', protocol_json)
        # Save MicroDrop, plugin, etc. metadata to archive.
        output.writestr('info.json', json.dumps(experiment_info(), indent=4))


class CancelledError(Exception):
    '''
    .. versionadded:: 2.34

    Exception indicating user has cancelled/closed dialog.
    '''
    pass


class ExperimentController(object):
    '''
    .. versionadded:: 2.34
    '''
    def __init__(self, working_dir):
        # Directory to store current experiment files.
        self.working_dir = path(working_dir)
        self.working_dir.makedirs_p()

    @property
    def modified(self):
        '''
        Difference between most-recently saved experiment archive
        '''
        app = get_app()
        now_contents = {}
        now_contents['device.svg'] = \
            hashlib.sha256(app.dmf_device.to_svg()).hexdigest()
        now_contents['protocol.json'] = \
            hashlib.sha256(app.protocol.to_json()).hexdigest()
        now_contents['info.json'] = \
            hashlib.sha256(json.dumps(experiment_info(),
                                        indent=4)).hexdigest()

        saved_checksums = now_contents.copy()

        directory_contents = {self.working_dir.relpathto(p):
                              p.read_hexhash('sha256')
                              for p in self.working_dir.walkfiles()}
        now_contents.update(directory_contents)

        return deepdiff.DeepDiff(saved_checksums, now_contents)

    def new(self):
        modifications = self.modified
        if modifications:
            # Get list of all added/changed/removed files.
            modified_files = [f.lstrip("root['").rstrip("']")
                              for s in modifications.values() for f in s]
            # Working directory contains unsaved changes.
            # Offer user option to save experiment log (yes/no)
            app = get_app()
            dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
                                       buttons=(gtk.BUTTONS_YES_NO),
                                       parent=app.main_window_controller.view)
            dialog.props.title = 'Save current experiment data?'
            messages = ['Modifications to the following files in the '
                        '[experiment log](%s) **_have not been saved_**:' %
                        self.working_dir,
                        '\n'.join('- `%s`' % f for f in modified_files),
                        '**Would you like to _save the existing log data_** '
                        'before creating a new experiment (_unsaved data_ will'
                        ' be _permanently_ lost)?']
            dialog.set_markup(markdown2pango('\n\n'.join(messages)).strip())

            def _on_link_clicked(widget, uri):
                '''
                Launch specified path using default OS viewer.
                '''
                path(uri).launch()
                return True

            # Use `activate-link` callback to manually handle action when hyperlink
            # is clicked/activated.
            dialog.label.connect("activate-link", _on_link_clicked)
            # Set default focus to **Yes** button.
            buttons = {b.props.label:
                       b for b in dialog.get_action_area().get_children()}
            yes_button = buttons['gtk-yes']
            yes_button.props.has_focus = True
            yes_button.props.has_default = True

            try:
                response = dialog.run()
            finally:
                dialog.destroy()

            if response == gtk.RESPONSE_YES:
                try:
                    # Prompt for output.
                    output_path = select_output_archive()
                    # Save experiment to output path.  **Do not** set active
                    # archive, since we are creating a new experiment.
                    save_experiment(self.working_dir, output_path)
                except IOError:
                    # User cancelled dialog.
                    raise CancelledError()
            elif response != gtk.RESPONSE_NO:
                raise CancelledError()

            # Delete contents of working directory.
            for file_i in self.working_dir.walkfiles():
                try:
                    file_i.remove()
                except Exception:
                    _L().debug('Error deleting: `%s`' % file_i.realpath(),
                               exc_info=True)
            for dir_i in sorted(self.working_dir.walkdirs())[::-1]:
                try:
                    dir_i.rmtree()
                except Exception:
                    _L().debug('Error deleting: `%s`' % dir_i.realpath(),
                               exc_info=True)


class ExperimentLogController(SingletonPlugin):
    '''
    .. versionchanged:: 2.21
        Read glade file using ``pkgutil`` to also support loading from ``.zip``
        files (e.g., in app packaged with Py2Exe).

    .. versionchanged:: 2.34
        Deprecate experiment log viewer.

    .. versionchanged:: 2.34
        Use a single experiment log directory, but offer to save modified
        contents to archive upon request to create new experiment.
    '''
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.experiment_log_controller"

    def on_plugin_enable(self):
        self.experiment_ctrl = ExperimentController(EXPERIMENT_LOG_DIR)
        app = get_app()
        app.experiment_log_controller = self

        @gtk_threadsafe
        def _on_new_menu_clicked(*args):
            try:
                self.experiment_ctrl.new()
            except CancelledError:
                # User cancelled creation of new experiment.
                pass

        app.signals["on_menu_new_experiment_activate"] = _on_new_menu_clicked

    def on_protocol_finished(self):
        '''
        .. versionadded:: 2.34

        Offer to create a new experiment if experiment data exists after
        protocol has completed.
        '''
        if self.experiment_ctrl.modified:
            app = get_app()
            dialog = gtk.Dialog(parent=app.main_window_controller.view,
                                title='Create new experiment?',
                                buttons=('_Continue', gtk.RESPONSE_NO, '_New',
                                         gtk.RESPONSE_YES))
            content_area = dialog.get_content_area()
            message = ('Protocol has completed successfully.\n\n'
                       'Would you like to **continue** the current experiment '
                       '_or_ **create a new one**?')
            align = gtk.Alignment()
            align.set_padding(padding_top=0, padding_bottom=0, padding_left=20,
                              padding_right=20)
            label = gtk.Label(markdown2pango(message))
            label.props.use_markup = True
            align.add(label)
            content_area.pack_start(align)
            content_area.show_all()
            try:
                response = dialog.run()
            finally:
                dialog.destroy()

            if response == gtk.RESPONSE_YES:
                try:
                    self.experiment_ctrl.new()
                except CancelledError:
                    # User cancelled creation of new experiment.
                    pass

PluginGlobals.pop_env()
