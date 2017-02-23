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

import gtk
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
        self.button = gtk.Button('Enable')
        self.button.connect('clicked', self.on_button_clicked, None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_end(self.button, expand=False, fill=False, padding=5)
        self.box.pack_end(self.button_update, expand=False, fill=False,
                          padding=5)
        self.box.pack_end(self.button_uninstall, expand=False, fill=False,
                          padding=5)
        self.box.pack_end(self.label_version, expand=True, fill=False)
        self.update()

        # TODO Remove this special handling after implementing full support for
        # Conda MicroDrop plugins.
        if self.is_conda_plugin:
            # Disable buttons for currently unsupported actions for Conda
            # MicroDrop plugins.
            for button_i in (self.button_uninstall, self.button_update):
                button_i.props.sensitive = False
                button_i.set_tooltip_text('Not currently supported for Conda '
                                          'MicroDrop plugins')

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
            self.button.set_label('Disable')
        else:
            self.button.set_label('Enable')

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
        #  - [ ] Implement Conda MicroDrop plugin uninstall behaviour using
        #    `mpm.api` API.
        #  - [ ] Deprecate MicroDrop 2.0 plugins support (i.e., only support
        #    Conda MicroDrop plugins)

        # XXX For now, only support MicroDrop 2.0 plugins (no support for Conda
        # MicroDrop plugins).
        if self.is_conda_plugin:
            logging.error('Uninstall of Conda MicroDrop plugins is not '
                          'currently supported.')
            return

        package_name = self.get_plugin_package_name()
        response = yesno('Uninstall plugin %s?' % package_name)
        if response == gtk.RESPONSE_YES:
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
        #  - [ ] Implement Conda MicroDrop plugin update behaviour using
        #    `mpm.api` API.
        #  - [ ] Deprecate MicroDrop 2.0 plugins support (i.e., only support
        #    Conda MicroDrop plugins)

        # XXX For now, only support MicroDrop 2.0 plugins (no support for Conda
        # MicroDrop plugins).
        if self.is_conda_plugin:
            logging.error('Update of Conda MicroDrop plugins is not currently '
                          'supported.')
            return

        app = get_app()
        try:
            self.controller.update_plugin(self, verbose=True)
        except IOError:
            logger.warning('Could not connect to plugin server: %s',
                           app.get_app_value('server_url'))
        except (JSONRPCException, JSONDecodeException):
            logger.warning('Plugin %s not available on plugin server',
                           app.get_app_value('server_url'))
            return True
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

    def on_button_clicked(self, widget, data=None):
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

    def update_plugin(self, plugin_controller, verbose=False, force=False):
        '''
        Parameters
        ----------
        plugin_controller : PluginController
            Controller for plugin to update.
        verbose : bool, optional
            If ``True``, log warning message if plugin is up-to-date.
        force : bool, optional
            If ``True``, update without prompting for confirmation.

        Returns
        -------
        bool
            ``True`` if plugin was upgraded, otherwise, ``False``.
        '''
        app = get_app()
        server_url = app.get_app_value('server_url')
        plugin_metadata = plugin_controller.get_plugin_info()
        package_name = plugin_metadata.package_name
        plugin_name = plugin_metadata.plugin_name

        plugin_repo = PluginRepository(server_url)
        latest_version = Version(**plugin_repo
                                 .latest_version(package_name,
                                                 app_version=APP_VERSION))

        # Check the plugin tag versus the tag of latest version from the
        # update respository. If they are different, it's a sign that they
        # the currently installed plugin may be incompatible.
        if plugin_controller.version.tags != latest_version.tags:
            if yesno('The currently installed plugin (%s-%s) is from a '
                     'different branch and may not be compatible with '
                     'this version of MicroDrop. Would you like to download '
                     'a compatible version?' % (plugin_name,
                                                plugin_controller.version)
                     ) == gtk.RESPONSE_YES:
                return self.download_and_install_plugin(package_name,
                                                        force=force)
        elif plugin_controller.version < latest_version:
            return self.download_and_install_plugin(package_name, force=force)
        else:
            message = 'Plugin %s is up to date (version %s)' % (
                plugin_name, plugin_controller.version)
            if verbose:
                logger.warning(message)
            logger.info(message)
            return False

    def download_and_install_plugin(self, package_name, force=False):
        '''
        Parameters
        ----------
        package_name : str
            Plugin Python module name (e.g., ``dmf_control_board_plugin``).

            Corresponds to ``package_name`` key in plugin ``properties.yml`` file.
        force : bool, optional
            If ``True``, install/update without prompting for confirmation.

        Returns
        -------
        bool
            ``True`` if plugin was installed or upgraded, otherwise, ``False``.
        '''
        temp_dir = ph.path(tempfile.mkdtemp(prefix='microdrop_plugin_update'))
        try:
            app = get_app()
            server_url = app.get_app_value('server_url')
            plugin_repo = PluginRepository(server_url)
            plugin_repo.download_latest(package_name, temp_dir,
                                        app_version=APP_VERSION)
            archive_path = temp_dir.files()[0]
            return self.install_from_archive(archive_path, force=force)
        finally:
            temp_dir.rmtree()
        return False

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

    def update_all_plugins(self, force=False):
        '''
        Upgrade each plugin to the latest version available (if not already
        installed).

        Parameters
        ----------
        force : bool, optional
            If ``True``, for each plugin, if a different version of the plugin
            is already installed, upgrade without prompting for confirmation.

        Returns
        -------
        bool
            ``True`` if any plugin was upgraded, otherwise, ``False``.
        '''
        self.update()
        plugin_updated = False
        app = get_app()
        for p in self.plugins:
            plugin_name = p.get_plugin_info().plugin_name
            try:
                result = self.update_plugin(p, force=force)
                logger.info('[update_all_plugins] plugin_name=%s %s',
                            plugin_name, result)
                plugin_updated = plugin_updated or result
            except (JSONRPCException, JSONDecodeException):
                logger.info('Plugin %s not available on plugin server %s',
                            plugin_name, app.get_app_value('server_url'))
            except IOError:
                logger.info('Could not connect to plugin repository at: %s',
                            app.get_app_value('server_url'))
        return plugin_updated

    def install_from_archive(self, archive_path, force=False):
        '''
        Install a plugin from an archive (i.e., `.tar.gz` or `.zip`).

        Parameters
        ----------
        archive_path : str
            Path to plugin archive file.
        force : bool, optional
            If ``True``, install/update without prompting for confirmation.

        Returns
        -------
        bool
            ``True`` if plugin was installed or upgraded, otherwise, ``False``.
        '''
        temp_dir = ph.path(tempfile.mkdtemp(prefix='microdrop_'))
        logger.debug('extracting to: %s', temp_dir)
        archive_path = ph.path(archive_path)

        try:
            if archive_path.ext == '.zip':
                zip_file = ZipFile(archive_path)
                zip_file.extractall(temp_dir)
                zip_file.close()
            else:
                # extension must be .tar.gz or .tgz
                tar_file = tarfile.open(archive_path, 'r:gz')
                tar_file.extractall(temp_dir)
                tar_file.close()
            return self.verify_and_install_new_plugin(temp_dir, force=force)
        finally:
            # Post-pone deletion until next program launch
            self.requested_deletions.append(temp_dir)
            self.update()

    def uninstall_plugin(self, plugin_path):
        '''
        Uninstall a plugin.

        Parameters
        ----------
        plugin_path : str
            Path to installed plugin directory.
        '''
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
