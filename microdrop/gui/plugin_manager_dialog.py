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

import logging
from shutil import ignore_patterns
from zipfile import ZipFile
import tarfile
import tempfile

import gtk
from pygtkhelpers.ui.dialogs import open_filechooser, info
from path import path

from plugin_manager import PluginGlobals
from app_context import get_app, plugin_manager


class PluginController(object):
    def __init__(self, name):
        self.name = name
        self.e = PluginGlobals.env('microdrop.managed')
        self.plugin_class = self.e.plugin_registry[name]
        self.service = plugin_manager.get_service_instance(self.plugin_class)
        self.box = gtk.HBox()
        self.label = gtk.Label('%s' % self.name)
        self.label.set_alignment(0, 0.5)
        self.button = gtk.Button('disabled')
        self.button.connect('clicked', self.on_button_clicked, None)
        self.box.pack_start(self.label, expand=True, fill=True)
        self.box.pack_start(self.button, expand=False, fill=False, padding=5)
        self.update()
        self.box.show_all()

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
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    def update(self):
        self.clear_plugin_list()
        plugin_names = self.get_plugin_names()
        del self.plugins
        self.plugins = []
        for name in plugin_names:
            p = PluginController(name)
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
            
            assert(len(temp_dir.dirs()) == 1)

            plugin_root = path(temp_dir.dirs()[0])
            microdrop_path = path('microdrop').joinpath('__init__.py')
            if not (plugin_root / microdrop_path).isfile():
                logging.error('%s does not contain a valid plugin' % response)
                return True
            app = get_app()
            new_plugin_path = path(app.config.data['plugins']['directory'])\
                    .joinpath(plugin_root.name)
            if not (new_plugin_path / microdrop_path).isfile():
                plugin_root.copytree(new_plugin_path, symlinks=True,
                        ignore=ignore_patterns('*.pyc'))
                # Reload plugins to include newly installed plugin.
                plugin_manager.load_plugins()
                self.update()
                logging.info('%s installed successfully' % plugin_root.name)
                info('%s installed successfully' % plugin_root.name)
            else:
                logging.warning('Plugin %s already exists. '\
                        'Skipping installation.' % plugin_root.name)
        finally:
            temp_dir.rmtree()
        return True


if __name__ == '__main__':
    pm = PluginManagerView()
