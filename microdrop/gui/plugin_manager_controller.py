"""
Copyright 2012 Ryan Fobel and Christian Fobel

This file is part of MicroDrop.

MicroDrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

MicroDrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with MicroDrop.  If not, see <http://www.gnu.org/licenses/>.
"""
from shutil import ignore_patterns
import inspect
import logging
import os
import platform
import subprocess
import sys
import threading
import types
import warnings

from microdrop_utility.gui import yesno
import conda_helpers as ch
import gobject
import gtk
import mpm.api
import mpm.ui.gtk
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
        self.button_uninstall = gtk.Button('Uninstall')
        self.button_uninstall.connect('clicked',
                                      self.on_button_uninstall_clicked, None)
        self.button_update = gtk.Button('Update')
        self.button_update.connect('clicked', self.on_button_update_clicked,
                                   None)
        self.button_enable = gtk.Button('Enable')
        self.button_enable.connect('clicked', self.on_button_enable_clicked,
                                   None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_end(self.button_enable, expand=False, fill=False,
                          padding=5)
        self.box.pack_end(self.button_update, expand=False, fill=False,
                          padding=5)
        self.box.pack_end(self.button_uninstall, expand=False, fill=False,
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
    def is_conda_plugin(self):
        return (self.get_plugin_path().parent.realpath() ==
                mpm.api.MICRODROP_CONDA_ETC.joinpath('plugins', 'enabled'))

    def on_button_uninstall_clicked(self, widget, data=None):
        '''
        Handler for ``"Uninstall"`` button.

        Prompt user to confirm before uninstalling plugin.

        .. versionchanged:: 2.10.3
            Fix handling of Conda HTTP error.

            Notify after uninstall is completed and restart MicroDrop.
        '''
        package_name = self.get_plugin_info().package_name
        # Prompt user to confirm uninstall.
        response = yesno('Uninstall plugin %s?' % package_name)
        if response != gtk.RESPONSE_YES:
            return

        if self.is_conda_plugin:
            # Plugin is a Conda MicroDrop plugin.
            try:
                uninstall_json_log = mpm.api.uninstall(package_name)
            except RuntimeError, exception:
                if 'CondaHTTPError' in str(exception):
                    # Error accessing Conda server.
                    logger.warning('Could not connect to server.')
                else:
                    raise
            else:
                logger.info('Uninstall %s: %s', package_name,
                            uninstall_json_log)
                if not uninstall_json_log.get('success'):
                    logger.error('Error uninstalling %s', package_name)
                else:
                    self.controller.restart_required = True
                    # Display dialog notifying user that plugin was
                    # successfully uninstalled.
                    dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_OK)
                    dialog.set_title('Plugin uninstalled')
                    dialog.props.text = ('The `{}` plugin was uninstalled '
                                         'successfully.'.format(package_name))
                    dialog.run()
                    dialog.destroy()
        # Update dialog.
        self.controller.dialog.update()

    def on_button_update_clicked(self, widget, data=None):
        '''
        Handler for ``"Update"`` button.

        .. versionchanged:: 2.10.3
            Use :func:`plugin_helpers.get_plugin_info` function to retrieve
            package name.

            Prior to version ``2.10.3``, package name was inferred from name of
            plugin Python module.

            Use :func:`mpm.ui.gtk.update_plugin_dialog` to update plugin.

            Launch update plugin dialog using :func:`gobject.idle_add` to
            ensure it is executed in the main GTK thread.
        '''
        if self.is_conda_plugin:
            def _update_plugin():
                # Plugin in a Conda MicroDrop plugin.  Update Conda package.
                package_name = self.get_plugin_info().package_name
                logger.info('Update `%s`', package_name)
                update_args = ['--no-update' '-dependencies']
                install_response = \
                    mpm.ui.gtk.update_plugin_dialog(package_name,
                                                    update_args=update_args)
                self.controller.update_dialog_running.clear()
                if install_response:
                    unlinked, linked = ch.install_info(install_response)
                    if linked:
                        self.controller.restart_required = True
            if not self.controller.update_dialog_running.is_set():
                # Indicate that the update dialog is running to prevent a
                # second update dialog from running at the same time.
                self.controller.update_dialog_running.set()
                gobject.idle_add(_update_plugin)
            else:
                gobject.idle_add(logger.error, 'Still busy processing previous'
                                 ' update request.  Please wait.')
        else:
            # Assume MicroDrop 2.0 plugin
            logger.warning('Plugin appears to be a MicroDrop 2.0 plugin. Only '
                           'Conda MicroDrop plugins support updating.')
            return False
        return True

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

    Methods include:

     - :meth:`uninstall_plugin`
     - :meth:`install_plugin`
     - :meth:`download_and_install_plugin`
     - :meth:`update_plugin`
     - :meth:`uninstall_plugin`
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

    def download_and_install_plugin(self, package_name, *args):
        '''
        .. versionchanged:: 2.10.3
            Remove deprecated :data:`force` keyword argument.

            Pass additional args to :func:`mpm.api.install`.

            Display (and return) list of removed and list of installed Conda
            packages.

        Parameters
        ----------
        package_name : str
            Plugin Python module name (e.g., ``microdrop.step-label-plugin``).

            Corresponds to ``package_name`` key in plugin ``properties.yml``
            file.

        Returns
        -------
        unlinked_packages, linked_packages : list, list
            If no packages were installed or removed:
             - :data:`unlinked_packages` is set to ``None``.
             - :data:`linked_packages` is set to ``None``.

            If any packages are installed or removed:
             - :data:`unlinked_packages` is a list of tuples corresponding to
               the packages that were uninstalled/replaced.
             - :data:`linked_packages` is a list of ``(<package name and
               version>, <channel>)`` tuples corresponding to the packages that
               were installed/upgraded.

            Each package tuple in :data:`unlinked_packages`` and
            :data:`link_packages` is of the form ``(<package name>, <version>,
            <channel>)``
        '''
        if isinstance(package_name, types.StringTypes):
            # Coerce singleton package name to list.
            package_name = [package_name]
        # Install Conda plugin package(s).
        install_response = mpm.api.install(package_name,
                                           '--no-update-dependencies', *args)
        # Get list of unlinked packages and list of linked packages as tuples
        # of the form `(<package name>, <version>, <channel>)`.
        unlinked, linked = ch.install_info(install_response,
                                           split_version=True)
        if linked:
            # Find installed (i.e., linked) packages that correspond to
            # installed plugin packages.
            linked_plugin_packages = set(name_i for name_i, version_i,
                                         channel_i in
                                         linked).intersection(package_name)

            for plugin_package_i in linked_plugin_packages:
                # Extract importable Python module name from Conda package name.
                #
                # XXX Plugins are currently Python modules, which means that the
                # installed plugin directory must be a valid module name.
                # However, Conda package name conventions may include `.` and
                # `-` characters.
                module_name = plugin_package_i.split('.')[-1].replace('-', '_')
                mpm.api.enable_plugin(module_name)
        return unlinked, linked

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

    def update_all_plugins(self, **kwargs):
        '''
        Upgrade each plugin to the latest version available (if not already
        installed).

        .. versionchanged:: 2.10.3
            Use :func:`mpm.ui.gtk.update_plugin_dialog`.

        Returns
        -------
        bool
            ``True`` if any plugin was upgraded, otherwise, ``False``.
        '''
        if kwargs:
            warnings.warn('The `update_all_plugins` method no longer accepts '
                          '`force` keyword', DeprecationWarning)
        self.update()
        # Update all plugins to latest versions.
        # XXX Disable logging handlers to prevent `conda-helpers` error/warning
        # log messages from popping up a dialog.
        # Only update dependencies if it is necessary to meet package
        # requirements.
        install_response = \
            mpm.ui.gtk\
            .update_plugin_dialog(update_args=['--no-update-dependencies'])
        if install_response is None:
            linked = []
        else:
            unlinked, linked = ch.install_info(install_response)
        # Return `True` if at least one package was updated.
        return (linked and True)

    def uninstall_plugin(self, plugin_path):
        '''
        Uninstall a plugin.

        Parameters
        ----------
        plugin_path : str
            Path to installed plugin directory.

        Raises
        ------
        RuntimeError
            If plugin directory is a Conda MicroDrop plugin (uninstall for
            Conda plugins is not currently supported).
        '''
        # TODO
        # ----
        #
        #  - [ ] Deprecate MicroDrop 2.0 plugins support (i.e., only support
        #    Conda MicroDrop plugins)

        # XXX For now, only support MicroDrop 2.0 plugins (no support for Conda
        # MicroDrop plugins).
        is_conda_plugin = (ph.path(plugin_path).realpath().parent ==
                           mpm.api.MICRODROP_CONDA_ETC.joinpath('plugins',
                                                                'enabled'))
        if is_conda_plugin:
            raise RuntimeError('Uninstall of Conda MicroDrop plugins is not '
                               'currently supported.')

        # Add plugin to list of requested deletions.
        self.requested_deletions.append(plugin_path)
        self.update()

    def install_plugin(self, plugin_root, install_path):
        '''
        Install a plugin from a directory.

        Parameters
        ----------
        plugin_root : str
            Path to (extracted) plugin directory.
        install_path : str
            Path to install plugin to.
        '''
        plugin_root = ph.path(plugin_root)
        plugin_root.copytree(install_path, symlinks=True,
                             ignore=ignore_patterns('*.pyc'))
        self.restart_required = True

    def post_uninstall(self, uninstall_path):
        '''
        Execute post-uninstall hook.

        Parameters
        ----------
        uninstall_path : str
            Path to uninstalled plugin directory.
        '''
        uninstall_path = ph.path(uninstall_path)
        # __NB__ The `cwd` directory ["is not considered when searching the
        # executable, so you can't specify the program's path relative to
        # `cwd`."][cwd].  Therefore, we manually change to the directory
        # containing the hook script and change back to the original working
        # directory when we're done.
        #
        # [cwd]: https://docs.python.org/2/library/subprocess.html#popen-constructor
        cwd = os.getcwd()
        if platform.system() in ('Linux', 'Darwin'):
            system_name = platform.system()
            hooks_path = uninstall_path.joinpath('hooks',
                                                 system_name).abspath()
            on_uninstall_path = hooks_path.joinpath('on_plugin_uninstall.sh')
            if on_uninstall_path.isfile():
                # There is an `on_plugin_uninstall` script to run.
                try:
                    os.chdir(hooks_path)
                    subprocess.check_call(['sh', on_uninstall_path.name,
                                           sys.executable], cwd=hooks_path)
                finally:
                    os.chdir(cwd)
        elif platform.system() == 'Windows':
            hooks_path = uninstall_path.joinpath('hooks', 'Windows').abspath()
            on_uninstall_path = hooks_path.joinpath('on_plugin_uninstall.bat')
            if on_uninstall_path.isfile():
                # There is an `on_plugin_uninstall` script to run.
                try:
                    os.chdir(hooks_path)
                    subprocess.check_call([on_uninstall_path.name,
                                           sys.executable], cwd=hooks_path)
                finally:
                    os.chdir(cwd)

    def verify_and_install_new_plugin(self, plugin_root, force=False):
        '''
        Parameters
        ----------
        plugin_root : str
            Path to plugin directory.
        force : bool, optional
            If ``True`` and a different version of the plugin is already
            installed, upgrade without prompting for confirmation.

        Returns
        -------
        bool
            ``True`` if plugin was installed or upgraded, otherwise, ``False``.
        '''
        plugin_metadata = get_plugin_info(plugin_root)
        if plugin_metadata is None:
            logger.error('%s does not contain a valid plugin.', plugin_root)
            return False
        logger.info('Installing: %s', plugin_metadata)

        app = get_app()
        installed_plugin_path = (ph.path(app.config.data['plugins']
                                         ['directory'])
                                 .joinpath(plugin_metadata.package_name))
        installed_metadata = get_plugin_info(installed_plugin_path)

        if installed_metadata:
            logger.info('Currently installed: %s', installed_metadata)
            if all([installed_metadata.version.tags ==
                    plugin_metadata.version.tags,
                    installed_metadata.version >= plugin_metadata.version]):
                # Installed version is up-to-date
                logger.info('Plugin %s is up-to-date (version %s).  Skipping '
                            'installation.', installed_metadata.plugin_name,
                            installed_metadata.version)
                return
            else:
                message = ('A newer version (%s) of the %s plugin is available'
                           ' (current version=%s).' % (plugin_metadata.version,
                                                       plugin_metadata
                                                       .plugin_name,
                                                       installed_metadata
                                                       .version))
                logger.info(message)
                if not force:
                    response = yesno('''%s Would you like to upgrade?''' %
                                     message)
                    if response == gtk.RESPONSE_YES:
                        force = True
                    else:
                        return False
                if force:
                    try:
                        self.uninstall_plugin(installed_plugin_path)
                        count = 1
                        target_path = installed_plugin_path
                        while installed_plugin_path.exists():
                            installed_plugin_path = \
                                ph.path('%s%d' % (installed_plugin_path,
                                                  count))
                        if target_path != installed_plugin_path:
                            self.rename_queue.append((installed_plugin_path,
                                                      target_path))
                    except Exception:
                        raise
        else:
            # There is no valid version of this plugin currently installed.
            logger.info('%s is not currently installed',
                        plugin_metadata.plugin_name)

            # enable new plugins by default
            app.config["plugins"]["enabled"].append(plugin_metadata
                                                    .package_name)
        try:
            self.install_plugin(plugin_root, installed_plugin_path)
            logger.info('%s installed successfully',
                        plugin_metadata.plugin_name)
        except Exception, why:
            logger.error('Error installing plugin. %s.', why)
        app.main_window_controller.info('%s plugin installed successfully.'
                                        % plugin_metadata.plugin_name,
                                        'Install plugin')
        return True


PluginGlobals.pop_env()
