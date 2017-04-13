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
import inspect
import os
import subprocess
import sys
import platform
import logging
from shutil import ignore_patterns
from zipfile import ZipFile
import tarfile
import tempfile
import warnings

import gtk
import logging_helpers as lh
import mpm.api
import path_helpers as ph
import yaml
from jsonrpc.proxy import JSONRPCException
from jsonrpc.json import JSONDecodeException
from application_repository.plugins.proxy import PluginRepository
from microdrop_utility import Version
from microdrop_utility.gui import yesno

from ..app_context import get_app, APP_VERSION
from ..plugin_helpers import get_plugin_info
from ..plugin_manager import (IPlugin, implements, SingletonPlugin,
                              PluginGlobals, get_service_instance,
                              get_plugin_package_name, enable as
                              enable_service, disable as disable_service)
from ..gui.plugin_manager_dialog import PluginManagerDialog

logger = logging.getLogger(__name__)


class PluginController(object):
    '''
    Manage an installed plugin.
    '''
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugin_class = self.e.plugin_registry[name]
        self.service = get_service_instance(self.plugin_class)
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
        self.box.pack_end(self.button_enable, expand=False, fill=False, padding=5)
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

        Notes
        -----
        An error is reported if the plugin is a Conda MicroDrop plugin
        (uninstall for Conda plugins is not currently supported).
        '''
        # TODO
        # ----
        #
        #  - [t] Implement Conda MicroDrop plugin uninstall behaviour using
        #    `mpm.api` API.
        #  - [ ] Deprecate MicroDrop 2.0 plugins support (i.e., only support
        #    Conda MicroDrop plugins)
        package_name = self.get_plugin_package_name()
        # Prompt user to confirm uninstall.
        response = yesno('Uninstall plugin %s?' % package_name)
        if response != gtk.RESPONSE_YES:
            return

        if self.is_conda_plugin:
            # Plugin in a Conda MicroDrop plugin.
            try:
                uninstall_json_log = mpm.api.uninstall(package_name)
            except RuntimeError, exception:
                if 'CondaHTTPError' in exception:
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
            # Assume MicroDrop 2.0 plugin

            # remove the plugin from he enabled list
            app = get_app()
            if package_name in app.config["plugins"]["enabled"]:
                app.config["plugins"]["enabled"].remove(package_name)

            plugin_path = self.get_plugin_path()
            if plugin_path.isdir():
                self.controller.uninstall_plugin(plugin_path)
                self.controller.restart_required = True
                self.controller.update()
                app.main_window_controller.info('%s plugin successfully '
                                                'removed.' % package_name,
                                                'Uninstall plugin')
        # Update dialog.
        self.controller.dialog.update()

    def on_button_update_clicked(self, widget, data=None):
        '''
        Handler for ``"Update"`` button.

        Notes
        -----
        An error is reported if the plugin is a Conda MicroDrop plugin (update
        for Conda plugins is not currently supported).
        '''
        # TODO
        # ----
        #
        #  - [t] Implement Conda MicroDrop plugin update behaviour using
        #    `mpm.api` API.
        #  - [ ] Deprecate MicroDrop 2.0 plugins support (i.e., only support
        #    Conda MicroDrop plugins)

        if self.is_conda_plugin:
            # Plugin in a Conda MicroDrop plugin.  Update Conda package.
            package_name = self.get_plugin_package_name()

            # XXX Disable default logging handlers to prevent `logging.error`
            # calls from popping up error dialogs while attempting to update.
            # TODO Avoid `conda_helpers` error log messages using [logging
            # filters][filter] instead.
            #
            # [filter]: https://docs.python.org/2/library/logging.html#filter-objects
            log_messages = []
            with lh.logging_restore(clear_handlers=True):
                try:
                    update_json_log = mpm.api.update(package_name)
                except RuntimeError, exception:
                    if 'CondaHTTPError' in str(exception):
                        # Error accessing Conda server.
                        log_messages.append(('warning', 'Could not connect to '
                                             'update server.'))
                    else:
                        raise
                else:
                    log_messages.append(('info', 'Update %s: %s', package_name,
                                         update_json_log))
                    if not update_json_log.get('success'):
                        log_messages.append(('error', 'Error updating %s',
                                             package_name))
            # Log messages queued while log handlers were disabled.
            for message_i in log_messages:
                getattr(logger, message_i[0])(*message_i[1:])
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

    def get_plugin_package_name(self):
        '''
        Returns
        -------
        str
            Relative module name (e.g., ``'dmf_control_board_plugin'``)
        '''
        return get_plugin_package_name(self.plugin_class.__module__)

    def get_plugin_path(self, package_name=None):
        '''
        Parameters
        ----------
        package_name : str, optional
            Relative module name (e.g., ``'dmf_control_board_plugin'``)

        Returns
        -------
        path_helpers.path
            Path to plugin directory.
        '''
        if package_name is None:
            package_name = self.get_plugin_package_name()

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
     - :meth:`install_from_archive`
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
        self.e = PluginGlobals.env('microdrop.managed')
        self.dialog = PluginManagerDialog()

    def download_and_install_plugin(self, package_name, force=False):
        '''
        Parameters
        ----------
        package_name : str
            Plugin Python module name (e.g., ``dmf_control_board_plugin``).

            Corresponds to ``package_name`` key in plugin ``properties.yml`` file.
        force : bool, deprecated
            Ignored.

        Returns
        -------
        bool
            ``True`` if plugin was installed or upgraded, otherwise, ``False``.
        '''
        # Install Conda plugin package.
        return mpm.api.install(package_name).get('success')

    def get_plugin_names(self):
        '''
        Returns
        -------
        list(str)
            List of plugin class names (e.g., ``['StepLabelPlugin', ...]``).
        '''
        return list(self.e.plugin_registry.keys())

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
        try:
            install_log = mpm.api.update()
            return 'actions' in install_log
        except RuntimeError, exception:
            if "CondaHTTPError" in str(exception):
                logger.debug(str(exception))

    def install_from_archive(self, archive_path, **kwargs):
        '''
        Install a plugin from an archive (i.e., `.tar.bz2`).

        ..note::

            Installing a plugin from an archive **does not install
            dependencies**.

        Parameters
        ----------
        archive_path : str
            Path to plugin archive file.

        Returns
        -------
        bool
            ``True`` if plugin was installed or upgraded, otherwise, ``False``.
        '''
        if kwargs:
            warnings.warn('The `install_from_archive` method no longer accepts'
                          ' `force` keyword', DeprecationWarning)
        try:
            mpm.api.install('--offline', '--file', archive_path)
        except ValueError, exception:
            # XXX Note that `--json` flag is erroneously ignored when executing
            # `conda install` with `tar.bz2` archive (see [here][conda-4879]).
            #
            # As a workaround, if command fails with a JSON decoding error,
            # assume that the install completed successfully.
            #
            # TODO Check status of [related Conda issue][conda-4879] and remove
            # workaround once the bug is fixed.
            #
            # [conda-4879]: https://github.com/conda/conda/issues/4879
            if 'No JSON object could be decoded' in str(exception):
                return True
            else:
                raise

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
                    except:
                        raise
                        return False
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
