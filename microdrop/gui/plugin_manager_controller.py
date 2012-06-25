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

import re
import logging
from shutil import ignore_patterns
from zipfile import ZipFile
import tarfile
import tempfile
from collections import namedtuple

import gtk
from path import path
import yaml
from flatland import Form, String
from jsonrpc.proxy import JSONRPCException

from plugin_repository import PluginRepository
import plugin_manager
from app_context import get_app
from utility import Version
from utility.gui import yesno
from plugin_helpers import AppDataController
from plugin_manager import get_service_instance_by_name, IPlugin, implements,\
        SingletonPlugin


class PluginController(object):
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.e = plugin_manager.PluginGlobals.env('microdrop.managed')
        self.plugin_class = self.e.plugin_registry[name]
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        self.box = gtk.HBox()
        self.label = gtk.Label('%s' % self.service.name)
        self.label.set_alignment(0, 0.5)
        self.label_version = gtk.Label(str(self.version))
        self.label_version.set_alignment(0, 0.5)
        self.button_uninstall = gtk.Button('Uninstall')
        self.button_uninstall.connect('clicked',
                self.on_button_uninstall_clicked, None)
        self.button_update = gtk.Button('Update')
        self.button_update.connect('clicked',
                self.on_button_update_clicked, None)
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
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        if self.enabled():
            self.button.set_label('Disable')
        else:
            self.button.set_label('Enable')

    def toggle_enabled(self):
        if not self.enabled():
            plugin_manager.enable(self.service.name)
        else:
            plugin_manager.disable(self.service.name)
        self.update()

    def get_widget(self):
        return self.box

    def on_button_uninstall_clicked(self, widget, data=None):
        plugin_name = self.get_plugin_module_name()
        response = yesno('Uninstall plugin %s?' % plugin_name)
        if response == gtk.RESPONSE_YES:
            plugin_path = self.get_plugin_path()
            if plugin_path.isdir():
                self.controller.uninstall_plugin(plugin_path)
                self.controller.restart_required = True
                self.controller.update()

    def on_button_update_clicked(self, widget, data=None):
        plugin_name = self.get_plugin_module_name()
        try:
            self.controller.update_plugin(plugin_name, verbose=True)
        except JSONRPCException:
            logging.info('Plugin %s not available on plugin server %s' % (
                    plugin_name, self.controller.get_app_value('server_url')))
            return True
        return True

    def get_plugin_module_name(self):
        cre_plugin_name = re.compile(r'^plugins\.(?P<name>.*?)\.')
        match = cre_plugin_name.search(self.plugin_class.__module__)
        if match is None:
            logging.error('Could not determine plugin name from: %s'\
                    % self.plugin_class.__module__)
            return True
        return match.group('name')

    def get_plugin_path(self, plugin_name=None):
        if plugin_name is None:
            plugin_name = self.get_plugin_module_name()
        app = get_app()

        app.config.data['plugins']['directory']
        return path(app.config.data['plugins']['directory'])\
                .joinpath(plugin_name)

    def on_button_clicked(self, widget, data=None):
        self.toggle_enabled()


class PluginManagerController(SingletonPlugin, AppDataController):
    implements(IPlugin)

    AppFields = Form.of(
        String.named('server_url').using(default='http://localhost:8000',
                optional=True, properties=dict(show_in_gui=False)),
    )

    def __init__(self):
        self.name = 'microdrop.gui.plugin_manager_controller'
        self.plugins = []
        # Maintain a list of path deletions to be processed on next app launch
        self.requested_deletions = []
        self.rename_queue = []
        self.restart_required = False
        self.e = plugin_manager.PluginGlobals.env('microdrop.managed')

    def update_plugin(self, plugin_controller, verbose=False):
        server_url = self.get_app_value('server_url')
        plugin_name = plugin_controller.get_plugin_module_name()
        p = PluginRepository(server_url)
        latest_version = Version(**p.latest_version(plugin_name))
        if plugin_controller.version < latest_version:
            temp_dir = path(tempfile.mkdtemp(
                    prefix='microdrop_plugin_update'))
            try:
                p.download_latest(plugin_name, temp_dir)
                archive_path = temp_dir.files()[0]
                self.install_from_archive(archive_path)
                return True
            finally:
                temp_dir.rmtree()
        else:
            message = 'Plugin %s is up to date (version %s)' % (plugin_name,
                    plugin_controller.version)
            if verbose:
                logging.warning(message)
            logging.info(message)
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
        requested_deletion_path = path(app.config.data['plugins']['directory'])\
                .joinpath('requested_deletions.yml')
        requested_deletion_path.write_bytes(yaml.dump(
                [p.abspath() for p in self.requested_deletions]))
        rename_queue_path = path(app.config.data['plugins']['directory'])\
                .joinpath('rename_queue.yml')
        rename_queue_path.write_bytes(yaml.dump(
                [(p1.abspath(), p2.abspath()) for p1, p2 in self.rename_queue]))

    def install_from_archive(self, archive_path):
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
            self.verify_new_plugin(temp_dir)
        finally:
            # Post-pone deletion until next program launch
            self.requested_deletions.append(temp_dir)
            self.update()
        return True

    def uninstall_plugin(self, plugin_path):
        self.requested_deletions.append(plugin_path)
        self.update()

    def install_plugin(self, plugin_root, install_path):
        plugin_root.copytree(install_path, symlinks=True,
                ignore=ignore_patterns('*.pyc'))
        app = get_app()
        logging.info('%s installed successfully' % plugin_root.name)
        info('%s installed successfully' % plugin_root.name)
        self.restart_required = True

    def verify_new_plugin(self, extracted_path):
        assert(len(extracted_path.dirs()) == 1)
        plugin_root = path(extracted_path.dirs()[0])
        plugin_metadata = self.get_plugin_info(plugin_root)
        if plugin_metadata is None:
            logging.error('%s does not contain a valid plugin.' % (plugin_root))
            return False
        logging.info('Installing: %s' % (plugin_metadata, ))

        app = get_app()
        installed_plugin_path = path(app.config.data['plugins']['directory'])\
                .joinpath(plugin_root.name)
        installed_metadata = self.get_plugin_info(installed_plugin_path)
        
        if installed_metadata:
            logging.info('Currently installed: %s' % (installed_metadata,))
            if installed_metadata.version >= plugin_metadata.version:
                # Installed version is up-to-date
                message = 'Plugin %s is up-to-date (version %s). '\
                        'Skipping installation.' % installed_metadata
                logging.info(message)
                info(message)
                return
            else:
                message = 'Plugin %s version %s is newer than currently '\
                        'installed version (%s)' % (plugin_metadata.name,
                        plugin_metadata.version, installed_metadata.version)
                logging.info(message)
                response = yesno('''\
%s
Would you like to uninstall the previous version and install the new \
version?''' % message)
                if response == gtk.RESPONSE_NO:
                    return
                else:
                    try:
                        self.uninstall_plugin(installed_plugin_path)
                        count = 1
                        target_path = installed_plugin_path
                        while installed_plugin_path.exists():
                            installed_plugin_path = path('%s%d'\
                                    % (installed_plugin_path, count))
                        if target_path != installed_plugin_path:
                            self.rename_queue.append((installed_plugin_path,
                                    target_path))
                    except:
                        raise
                        return
        else:
            # There is no valid version of this plugin currently installed.
            logging.info('%s is not currently installed' % plugin_root.name)
        self.install_plugin(plugin_root, installed_plugin_path)

