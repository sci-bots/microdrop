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
from pygtkhelpers.ui.dialogs import open_filechooser, info
from path_helpers import path
import yaml
from flatland import Form, String
from jsonrpc.proxy import JSONRPCException
from application_repository.plugins.proxy import PluginRepository
from microdrop_utility import Version
from microdrop_utility.gui import yesno

from ..gui.plugin_download_dialog import PluginDownloadDialog
from ..app_context import get_app
from ..plugin_manager import (get_service_instance_by_name,
                              get_plugin_package_name)
from .. import glade_path


class PluginManagerDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(glade_path()
                              .joinpath('plugin_manager_dialog.glade'))
        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        builder.connect_signals(self)

    def clear_plugin_list(self):
        self.vbox_plugins.foreach(lambda x: self.vbox_plugins.remove(x))

    @property
    def controller(self):
        service = get_service_instance_by_name(
                'microdrop.gui.plugin_manager_controller', env='microdrop')
        return service

    def update(self):
        self.clear_plugin_list()
        self.controller.update()
        for p in self.controller.plugins:
            self.vbox_plugins.pack_start(p.get_widget())

    def run(self):
        app = get_app()
        self.update()
        response = self.window.run()
        self.window.hide()
        for p in self.controller.plugins:
            package_name = p.get_plugin_package_name()
            if p.enabled():
                if package_name not in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].append(package_name)
            else:
                if package_name in app.config["plugins"]["enabled"]:
                    app.config["plugins"]["enabled"].remove(package_name)
        app.config.save()
        if self.controller.restart_required:
            logging.warning('''\
Plugins were installed/uninstalled.
Program needs to be closed.
Please start program again for changes to take effect.''')
            app.main_window_controller.on_destroy(None)
            return response
        return response

    def on_button_download_clicked(self, *args, **kwargs):
        d = PluginDownloadDialog()
        response = d.run()

        if response == gtk.RESPONSE_OK:
            for p in d.selected_items():
                print 'installing: %s' % p
                self.controller.download_and_install_plugin(p)

    def on_button_install_clicked(self, *args, **kwargs):
        response = open_filechooser('Select plugin file',
                action=gtk.FILE_CHOOSER_ACTION_OPEN,
                patterns=['*.tar.gz', '*.tgz', '*.zip'])
        if response is None:
            return True

        return self.controller.install_from_archive(response)

    def on_button_update_all_clicked(self, *args, **kwargs):
        self.controller.update_all_plugins()


if __name__ == '__main__':
    pm = PluginManagerView()
