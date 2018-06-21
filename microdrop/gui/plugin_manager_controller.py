import inspect
import logging
import sys
import threading

import gtk
import path_helpers as ph
import yaml

from ..app_context import get_app
from ..gui.plugin_manager_dialog import PluginManagerDialog
from ..plugin_helpers import get_plugin_info
from ..plugin_manager import (IPlugin, implements, SingletonPlugin,
                              PluginGlobals, get_service_instance,
                              enable as enable_service,
                              disable as disable_service)

logger = logging.getLogger(__name__)

PluginGlobals.push_env('microdrop')


class PluginController(object):
    '''
    Manage an installed plugin.
    '''
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.plugin_env = PluginGlobals.env('microdrop.managed')
        # Look up running instance of plugin (i.e., service) based on name of
        # plugin class.
        services_by_class_name = {s.__class__.__name__: s
                                  for s in self.plugin_env.services}
        self.service = services_by_class_name[name]
        self.plugin_class = self.service.__class__
        self.box = gtk.HBox()
        self.label = gtk.Label('%s' % self.service.name)
        self.label.set_alignment(0, 0.5)
        self.label_version = gtk.Label(str(self.version))
        self.label_version.set_alignment(0, 0.5)
        self.button_enable = gtk.Button('Enable')
        self.button_enable.connect('clicked', self.on_button_enable_clicked,
                                   None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_end(self.button_enable, expand=False, fill=False,
                          padding=5)
        self.box.pack_end(self.label_version, expand=True, fill=False)
        self.update()

        self.box.show_all()

    @property
    def version(self):
        return getattr(self.plugin_class, 'version', None)

    def enabled(self):
        '''
        Returns
        -------
        bool
            ``True`` if plugin instance is enabled.

            Otherwise, ``False``.
        '''
        return not(self.service is None or not self.service.enabled())

    def update(self):
        '''
        Update reference to plugin/service instance and update enable button
        state.
        '''
        self.service = get_service_instance(self.plugin_class)
        if self.enabled():
            self.button_enable.set_label('Disable')
        else:
            self.button_enable.set_label('Enable')

    def toggle_enabled(self):
        '''
        Toggle enable state of plugin/service instance.
        '''
        if not self.enabled():
            enable_service(self.service.name)
        else:
            disable_service(self.service.name)
        self.update()

    def get_widget(self):
        '''
        Returns
        -------
        gtk.HBox
            UI widget instance.
        '''
        return self.box

    @property
    def is_site_plugin(self):
        return (self.get_plugin_path().parent.realpath() ==
                ph.path(sys.prefix).joinpath('etc', 'microdrop', 'plugins',
                                             'enabled'))

    def get_plugin_info(self):
        '''
        Returns
        -------
        namedtuple
            Plugin metadata in the form
            ``(package_name, plugin_name, version)``.
        '''
        return get_plugin_info(self.get_plugin_path())

    def get_plugin_path(self):
        '''
        Returns
        -------
        path_helpers.path
            Path to plugin directory.
        '''
        # Find path to file where plugin/service class is defined.
        class_def_file = ph.path(inspect.getfile(self.service.__class__))

        return class_def_file.parent

    def on_button_enable_clicked(self, widget, data=None):
        '''
        Handler for ``"Enable"/"Disable"`` button.
        '''
        self.toggle_enabled()


class PluginManagerController(SingletonPlugin):
    '''
    Manage installed plugins.
    '''
    implements(IPlugin)

    def __init__(self):
        self.name = 'microdrop.gui.plugin_manager_controller'
        self.plugins = []
        # Maintain a list of path deletions to be processed on next app launch
        self.requested_deletions = []
        self.rename_queue = []
        self.restart_required = False
        self.plugin_env = PluginGlobals.env('microdrop.managed')
        self.dialog = PluginManagerDialog()
        # Event to indicate when update dialog is running to prevent another
        # dialog from being launched.
        self.update_dialog_running = threading.Event()

    def get_plugin_names(self):
        '''
        Returns
        -------
        list(str)
            List of plugin class names (e.g., ``['StepLabelPlugin', ...]``).
        '''
        return list(self.plugin_env.plugin_registry.keys())

    def update(self):
        '''
        Update list of plugin controllers (one controller for each imported
        plugin in the ``microdrop.managed`` environment).

        ..notes::
            Also update **deletion**, **rename**, and **post-install** queue
            files.
        '''
        plugin_names = self.get_plugin_names()
        del self.plugins
        self.plugins = []
        for name in plugin_names:
            plugin_controller = PluginController(self, name)
            # Skip the plugin if it has been marked for uninstall, or no
            # longer exists
            if (plugin_controller.get_plugin_path().abspath() in
                self.requested_deletions) or (not plugin_controller
                                              .get_plugin_path().isdir()):
                continue
            self.plugins.append(plugin_controller)

        # Save the list of path deletions to be processed on next app launch
        app = get_app()
        requested_deletion_path = (ph.path(app.config.data['plugins']
                                           ['directory'])
                                   .joinpath('requested_deletions.yml'))
        requested_deletion_path.write_bytes(yaml.dump([p.abspath()
                                                       for p in self
                                                       .requested_deletions]))
        rename_queue_path = (ph.path(app.config.data['plugins']['directory'])
                             .joinpath('rename_queue.yml'))
        rename_queue_path.write_bytes(yaml.dump([(p1.abspath(), p2.abspath())
                                                 for p1, p2 in
                                                 self.rename_queue]))


PluginGlobals.pop_env()
