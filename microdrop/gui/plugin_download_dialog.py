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
from path import path
import yaml
from flatland import Form, String
from jsonrpc.proxy import JSONRPCException

from plugin_repository import PluginRepository
import plugin_manager
from app_context import get_app
from utility import Version
from utility.gui import yesno
from utility.gui.list_select import ListSelectView
from plugin_manager import get_service_instance_by_name


class PluginDownloadDialog(object):
    def __init__(self):
        builder = gtk.Builder()
        builder.add_from_file(path('gui').joinpath('glade',
                'plugin_download_dialog.glade'))
        self.window = builder.get_object('plugin_manager')
        self.vbox_plugins = builder.get_object('vbox_plugins')
        self.list_select_view = None
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

        server_url = self.controller.get_app_value('server_url')
        p = PluginRepository(server_url)
        available = set(p.available_plugins())
        installed = set([p.get_plugin_package_name()
                for p in self.controller.plugins])
        to_install = available.difference(installed)
        if not to_install:
            return None
        self.list_select_view = ListSelectView(sorted(to_install),
                'plugin_name')
        self.vbox_plugins.pack_start(self.list_select_view.widget)
        self.vbox_plugins.show_all()
        return True

    def selected_items(self):
        return self.list_select_view.selected_items()

    def run(self):
        app = get_app()
        if self.update() is None:
            logging.warning('All available plugins are already installed')
            return gtk.RESPONSE_CANCEL
        response = self.window.run()
        self.window.hide()
        return response
