"""
Copyright 2012 Ryan Fobel and Christian Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

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
from path_helpers import path
import yaml
from jsonrpc.proxy import JSONRPCException
from jsonrpc.json import JSONDecodeException
from application_repository.plugins.proxy import PluginRepository
from microdrop_utility import Version
from microdrop_utility.gui import yesno

from ..app_context import get_app
from ..plugin_helpers import get_plugin_info
from ..plugin_manager import (IPlugin, implements, SingletonPlugin,
                              PluginGlobals, get_service_instance,
                              get_plugin_package_name, enable as
                              enable_service, disable as disable_service)
from ..gui.plugin_manager_dialog import PluginManagerDialog


class PluginController(object):
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
        self.box.show_all()

    @property
    def version(self):
        return getattr(self.plugin_class, 'version', None)

    def enabled(self):
        return not(self.service is None or not self.service.enabled())

    def update(self):
        self.service = get_service_instance(self.plugin_class)
        if self.enabled():
            self.button.set_label('Disable')
        else:
            self.button.set_label('Enable')

    def toggle_enabled(self):
        if not self.enabled():
            enable_service(self.service.name)
        else:
            disable_service(self.service.name)
        self.update()

    def get_widget(self):
        return self.box

    def on_button_uninstall_clicked(self, widget, data=None):
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
        app = get_app()
        try:
            self.controller.update_plugin(self, verbose=True)
        except IOError:
            logging.warning('Could not connect to plugin server: %s',
                            app.get_app_value('server_url'))
        except (JSONRPCException, JSONDecodeException):
            logging.warning('Plugin %s not available on plugin server' %
                            (app.get_app_value('server_url')))
            return True
        return True

    def get_plugin_info(self):
        return get_plugin_info(self.get_plugin_path())

    def get_plugin_package_name(self):
        return get_plugin_package_name(self.plugin_class.__module__)

    def get_plugin_path(self, packge_name=None):
        if packge_name is None:
            packge_name = self.get_plugin_package_name()
        app = get_app()
        return (path(app.config.data['plugins']['directory'])
                .joinpath(packge_name))

    def on_button_clicked(self, widget, data=None):
        self.toggle_enabled()


class PluginManagerController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = 'microdrop.gui.plugin_manager_controller'
        self.plugins = []
        # Maintain a list of path deletions to be processed on next app launch
        self.requested_deletions = []
        self.post_install_queue = []
        self.rename_queue = []
        self.restart_required = False
        self.e = PluginGlobals.env('microdrop.managed')
        self.dialog = PluginManagerDialog()

    def update_plugin(self, plugin_controller, verbose=False, force=False):
        app = get_app()
        server_url = app.get_app_value('server_url')
        plugin_metadata = plugin_controller.get_plugin_info()
        package_name = plugin_metadata.package_name
        plugin_name = plugin_metadata.plugin_name

        p = PluginRepository(server_url)
        latest_version = Version(**p.latest_version(package_name,
                                                    app_version={'major': 1,
                                                                 'minor': 0,
                                                                 'micro': 0}))

        # Check the plugin tag versus the tag of latest version from the
        # update respository. If they are different, it's a sign that they
        # the currently installed plugin may be incompatible.
        if plugin_controller.version.tags != latest_version.tags:
            if yesno('The currently installed plugin (%s-%s) is from a '
                     'different branch and may not be compatible with '
                     'this version of Microdrop. Would you like to download '
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
                logging.warning(message)
            logging.info(message)
            return False

    def download_and_install_plugin(self, package_name, force=False):
        temp_dir = path(tempfile.mkdtemp(prefix='microdrop_plugin_update'))
        try:
            app = get_app()
            server_url = app.get_app_value('server_url')
            p = PluginRepository(server_url)
            p.download_latest(package_name, temp_dir, app_version={'major': 1,
                                                                   'minor': 0,
                                                                   'micro': 0})
            archive_path = temp_dir.files()[0]
            return self.install_from_archive(archive_path, force=force)
        finally:
            temp_dir.rmtree()
        return False

    def get_plugin_names(self):
        return list(self.e.plugin_registry.keys())

    def update(self):
        plugin_names = self.get_plugin_names()
        del self.plugins
        self.plugins = []
        for name in plugin_names:
            p = PluginController(self, name)
            # Skip the plugin if it has been marked for uninstall, or no
            # longer exists
            if p.get_plugin_path().abspath() in self.requested_deletions\
                    or not p.get_plugin_path().isdir():
                continue
            self.plugins.append(p)

        # Save the list of path deletions to be processed on next app launch
        app = get_app()
        requested_deletion_path = (path(app.config.data['plugins']
                                        ['directory'])
                                   .joinpath('requested_deletions.yml'))
        requested_deletion_path.write_bytes(yaml.dump([p.abspath()
                                                       for p in self
                                                       .requested_deletions]))
        rename_queue_path = (path(app.config.data['plugins']['directory'])
                             .joinpath('rename_queue.yml'))
        rename_queue_path.write_bytes(yaml.dump([(p1.abspath(), p2.abspath())
                                                 for p1, p2 in
                                                 self.rename_queue]))
        post_install_queue_path = (path(app.config.data['plugins']['directory'])
                             .joinpath('post_install_queue.yml'))
        post_install_queue_path.write_bytes(yaml.dump([p.abspath()
                                                       for p in self
                                                       .post_install_queue]))

    def update_all_plugins(self, force=False):
        self.update()
        plugin_updated = False
        app = get_app()
        for p in self.plugins:
            plugin_name = p.get_plugin_info().plugin_name
            try:
                result = self.update_plugin(p, force=force)
                logging.info('[update_all_plugins] plugin_name=%s %s' %
                             (plugin_name, result))
                plugin_updated = plugin_updated or result
            except (JSONRPCException, JSONDecodeException):
                logging.info('Plugin %s not available on plugin server %s' % (
                    plugin_name, app.get_app_value('server_url')))
            except IOError:
                logging.info('Could not connect to plugin repository at: %s' %
                             app.get_app_value('server_url'))
        return plugin_updated

    def install_from_archive(self, archive_path, force=False):
        temp_dir = path(tempfile.mkdtemp(prefix='microdrop_'))
        logging.debug('extracting to: %s' % temp_dir)
        archive_path = path(archive_path)

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
        self.requested_deletions.append(plugin_path)
        self.update()

    def install_plugin(self, plugin_root, install_path):
        plugin_metadata = get_plugin_info(plugin_root)
        plugin_root.copytree(install_path, symlinks=True,
                             ignore=ignore_patterns('*.pyc'))
        self.post_install_queue.append(install_path)
        self.restart_required = True

    def post_uninstall(self, uninstall_path):
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
        plugin_metadata = get_plugin_info(plugin_root)
        if plugin_metadata is None:
            logging.error('%s does not contain a valid plugin.' % plugin_root)
            return False
        logging.info('Installing: %s' % (plugin_metadata, ))

        app = get_app()
        installed_plugin_path = (path(app.config.data['plugins']['directory'])
                                 .joinpath(plugin_metadata.package_name))
        installed_metadata = get_plugin_info(installed_plugin_path)

        if installed_metadata:
            logging.info('Currently installed: %s' % (installed_metadata,))
            if installed_metadata.version.tags == \
                    plugin_metadata.version.tags and \
                    installed_metadata.version >= plugin_metadata.version:
                # Installed version is up-to-date
                message = ('Plugin %s is up-to-date (version %s).  Skipping '
                           'installation.' % (installed_metadata.plugin_name,
                           installed_metadata.version))
                logging.info(message)
                return
            else:
                message = ('A newer version (%s) of the %s plugin is available'
                           ' (current version=%s).' % (plugin_metadata.version,
                                                       plugin_metadata
                                                       .plugin_name,
                                                       installed_metadata
                                                       .version))
                logging.info(message)
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
                            installed_plugin_path = path(
                                '%s%d' % (installed_plugin_path, count))
                        if target_path != installed_plugin_path:
                            self.rename_queue.append((installed_plugin_path,
                                                      target_path))
                    except:
                        raise
                        return False
        else:
            # There is no valid version of this plugin currently installed.
            logging.info('%s is not currently installed' %
                         plugin_metadata.plugin_name)

            # enable new plugins by default
            app.config["plugins"]["enabled"].append(plugin_metadata
                                                    .package_name)
        try:
            self.install_plugin(plugin_root, installed_plugin_path)
            logging.info('%s installed successfully' %
                         plugin_metadata.plugin_name)
        except Exception, why:
            logging.error('Error installing plugin. %s.', why)
        app.main_window_controller.info('%s plugin installed successfully.'
                                        % plugin_metadata.plugin_name,
                                        'Install plugin')
        return True
