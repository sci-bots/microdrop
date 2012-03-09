"""
Copyright 2011 Ryan Fobel and Christian Fobel

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
from pygtkhelpers.ui.dialogs import open_filechooser, info, yesno
from path import path
import yaml

from plugin_manager import PluginGlobals
from app_context import get_app, plugin_manager
from utility import Version


PluginMetaData = namedtuple('PluginMetaData', 'name version')
PluginMetaData.as_dict = lambda self: dict([(k, str(v)) for k, v in zip(self._fields, self)])
#PluginMetaData.from_dict = staticmethod(lambda data: PluginMetaData(data['name'], Version.fromstring(data['version'])))

def from_dict(data):
    name = data['name']
    version = Version.fromstring(data['version'])
    return PluginMetaData(name, version)


PluginMetaData.from_dict = staticmethod(from_dict)


class PluginController(object):
    def __init__(self, dialog, name):
        self.dialog = dialog
        self.name = name
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugin_class = self.e.plugin_registry[name]
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        self.box = gtk.HBox()
        self.label = gtk.Label('%s' % self.name)
        self.label.set_alignment(0, 0.5)
        self.label_version = gtk.Label(str(self.version))
        self.label_version.set_alignment(0, 0.5)
        self.button_uninstall = gtk.Button('uninstall')
        self.button_uninstall.connect('clicked',
                self.on_button_uninstall_clicked, None)
        self.button = gtk.Button('disabled')
        self.button.connect('clicked', self.on_button_clicked, None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_end(self.button, expand=False, fill=False, padding=5)
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
            self.button.set_label('enabled')
        else:
            self.button.set_label('disabled')

    def toggle_enabled(self):
        if not self.enabled():
            plugin_manager.enable(self.name)
        else:
            plugin_manager.disable(self.name)
        self.update()

    def get_widget(self):
        return self.box

    def on_button_uninstall_clicked(self, widget, data=None):
        plugin_name = self.get_plugin_module_name()
        yesno('Uninstall plugin %s?' % plugin_name)

        plugin_path = self.get_plugin_path()
        if plugin_path.isdir():
            self.dialog.uninstall_plugin(plugin_path)
            self.dialog.restart_required = True
            self.dialog.update()

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


class PluginManagerDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(path('gui').joinpath('glade', 'plugin_manager_dialog.glade'))
        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugins = []
        self.restart_required = False
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    def update(self):
        self.clear_plugin_list()
        plugin_names = self.get_plugin_names()
        del self.plugins
        self.plugins = []
        for name in plugin_names:
            p = PluginController(self, name)
            if not p.get_plugin_path().isdir():
                continue
            self.plugins.append(p)
            self.vbox_plugins.pack_start(p.get_widget())

    def get_plugin_names(self):
        return list(self.e.plugin_registry.keys())

    def run(self):
        app = get_app()
        self.update()
        response = self.window.run()
        self.window.hide()
        enabled_plugins = [p.name for p in self.plugins if p.enabled()]
        app.config.set_plugins(enabled_plugins)
        app.config.save()
        if self.restart_required:
            logging.warning('''\
Plugins were installed/uninstalled.
Program needs to be closed.
Please start program again for changes to take effect.''')
            app.main_window_controller.on_destroy(None)
            return response
        return response

    def on_button_install_clicked(self, *args, **kwargs):
        response = open_filechooser('Select plugin file',
                action=gtk.FILE_CHOOSER_ACTION_OPEN,
                patterns=['*.tar.gz', '*.tgz', '*.zip'])
        if response is None:
            return True

        temp_dir = path(tempfile.mkdtemp(prefix='microdrop_'))
        logging.debug('extracting to: %s' % temp_dir)
        response = path(response)

        try:
            if response.ext == '.zip':
                zip_file = ZipFile(response)
                zip_file.extractall(temp_dir)
                zip_file.close()
            else:
                # extension must be .tar.gz or .tgz
                tar_file = tarfile.open(response, 'r:gz')
                tar_file.extractall(temp_dir)
                tar_file.close()
            self.verify_new_plugin(temp_dir)
        finally:
            temp_dir.rmtree()
        return True

    def verify_new_plugin(self, extracted_path):
        assert(len(extracted_path.dirs()) == 1)
        plugin_root = path(extracted_path.dirs()[0])
        plugin_metadata = self.get_plugin_info(plugin_root)
        if plugin_metadata is None:
            logging.error('%s does not contain a valid plugin.\n'\
                    '(missing %s)' % (response, p))
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
                    except:
                        raise
                        return
        else:
            # There is no valid version of this plugin currently installed.
            logging.info('%s is not currently installed' % plugin_root.name)
        self.install_plugin(plugin_root, installed_plugin_path)

    def uninstall_plugin(self, plugin_path):
        # Remove the old version.
        copy_finished = False
        try:
            # Temporarily copy old plugin to /tmp
            temp_dir = path(tempfile.mkdtemp(prefix='microdrop_backup'))
            plugin_path.copytree(
                    temp_dir.joinpath(plugin_path.name),
                    symlinks=True,
                    ignore=ignore_patterns('*.pyc'))
            copy_finished = True
            plugin_path.rmtree()
        except:
            if copy_finished:
                logging.error('''\
Error uninstalling %s from %s.
Please try removing the directory manually and try again.
Note: originally installed version available in %s''' % (plugin_path.name,
                        plugin_path, temp_dir))
            raise
        else:
            temp_dir.rmtree()

    def install_plugin(self, plugin_root, install_path):
        plugin_root.copytree(install_path, symlinks=True,
                ignore=ignore_patterns('*.pyc'))
        # Reload plugins to include newly installed plugin.
        plugin_manager.load_plugins()
        self.update()
        logging.info('%s installed successfully' % plugin_root.name)
        info('%s installed successfully' % plugin_root.name)
        self.restart_required = True

    def get_plugin_info(self, plugin_root):
        '''
        Return a tuple:
            (installed_version, metadata)
        If plugin is not installed, installed_version will be None.
        If plugin is not valid, metadata will be None.
        '''
        required_paths = [path('microdrop').joinpath('__init__.py'),
                path('properties.yml')]

        for p in required_paths:
            if not (plugin_root / p).isfile():
                return None

        # Load the plugin properties into a PluginMetaData object
        properties = plugin_root / required_paths[-1]
        plugin_metadata = PluginMetaData.from_dict(\
                yaml.load(properties.bytes()))
        return plugin_metadata


if __name__ == '__main__':
    pm = PluginManagerView()
