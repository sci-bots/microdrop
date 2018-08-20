import logging
import threading

import gtk
import gobject
import pkgutil

from ..app_context import get_app
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import get_service_instance_by_name


logger = logging.getLogger(__name__)


class PluginManagerDialog(object):
    '''
    List installed plugins with the following action buttons for each plugin:

     - Enable
     - Disable
     - **TODO** Uninstall
    '''
    def __init__(self):
        '''
        .. versionchanged:: 2.21
            Read glade file using ``pkgutil`` to also support loading from
            ``.zip`` files (e.g., in app packaged with Py2Exe).
        '''
        builder = gtk.Builder()
        # Read glade file using `pkgutil` to also support loading from `.zip`
        # files (e.g., in app packaged with Py2Exe).
        glade_str = pkgutil.get_data(__name__,
                                     'glade/plugin_manager_dialog.glade')
        builder.add_from_string(glade_str)

        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    @property
    def controller(self):
        plugin_name = 'microdrop.gui.plugin_manager_controller'
        service = get_service_instance_by_name(plugin_name, env='microdrop')
        return service

    def update(self):
        '''
        Update plugin list widget.
        '''
        self.clear_plugin_list()
        self.controller.update()
        for p in self.controller.plugins:
            self.vbox_plugins.pack_start(p.get_widget())

    def run(self):
        '''
        .. versionchanged:: 2.10.3
            Use :func:`plugin_helpers.get_plugin_info` function to retrieve
            package name.

        .. versionchanged:: 2.10.5
            Save Python module names of enabled plugins (**not** Conda package
            names) to ``microdrop.ini`` configuration file.
        '''
        # TODO
        # ----
        #
        #  - [ ] Remove all references to `app`
        #  - [ ] Use `MICRODROP_CONDA_ETC/plugins/enabled` to maintain enabled
        #    plugin references instead of MicroDrop profile `microdrop.ini`
        app = get_app()
        self.update()
        response = self.window.run()
        self.window.hide()
        for p in self.controller.plugins:
            package_name = p.get_plugin_info().package_name
            # Extract importable Python module name from Conda package name.
            #
            # XXX Plugins are currently Python modules, which means that the
            # installed plugin directory must be a valid module name. However,
            # Conda package name conventions may include `.` and `-`
            # characters.
            module_name = package_name.split('.')[-1].replace('-', '_')
            if p.enabled():
                if module_name not in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].append(module_name)
            else:
                if module_name in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].remove(module_name)
        app.config.save()
        if self.controller.restart_required:
            _L().warning('\n'.join(['Plugins and/or dependencies were '
                                    'installed/uninstalled.',
                                    'Program needs to be restarted for '
                                    'changes to take effect.']))
            # Use return code of `5` to signal program should be restarted.
            app.main_window_controller.on_destroy(None, return_code=5)
            return response
        return response


if __name__ == '__main__':
    pm = PluginManagerDialog()
