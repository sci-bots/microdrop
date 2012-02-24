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

import os

import gtk
from path import path

from app_context import get_app
from logger import logger


def copytree(src, dst, symlinks=False, ignore=None):
    import os
    from shutil import copy2, copystat, Error

    names = os.listdir(src)
    if ignore is not None:
        ignored_names = ignore(src, names)
    else:
        ignored_names = set()

    try:
        os.makedirs(dst)
    except OSError, exc:
        # XXX - this is pretty ugly
        if "file already exists" in exc[1]:  # Windows
            pass
        elif "File exists" in exc[1]:        # Linux
            pass
        else:
            raise

    errors = []
    for name in names:
        if name in ignored_names:
            continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks, ignore)
            else:
                copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except (IOError, os.error), why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
    try:
        copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError, why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Error, errors 



class OptionsController:
    def __init__(self):
        app = get_app()
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "configuration_dialog.glade"))
        self.dialog = builder.get_object("configuration_dialog")
        self.dialog.set_transient_for(app.main_window_controller.view)

        self.txt_data_dir = builder.get_object('txt_data_dir')
        self.btn_data_dir_browse = builder.get_object('btn_data_dir_browse')
        self.txt_data_dir.set_text(path(app.config['dmf_device']['directory']).abspath())

        self.btn_log_file_browse = builder.get_object('btn_log_file_browse')
        self.txt_log_file = builder.get_object('txt_log_file')
        self.chk_log_file_enabled = builder.get_object('chk_log_file_enabled')
        if app.config['logging']['file'] != None:
            self.txt_log_file.set_text(path(app.config['logging']['file']).abspath())
        if app.config['logging']['enabled']:
            self.chk_log_file_enabled.set_active(True)

        self.btn_ok = builder.get_object('btn_ok')
        self.btn_apply = builder.get_object('btn_apply')
        self.btn_cancel = builder.get_object('btn_cancel')

        builder.connect_signals(self)
        self.builder = builder

    def run(self):
        response = self.dialog.run()
        if response == gtk.RESPONSE_OK:
            self.apply()
        elif response == gtk.RESPONSE_CANCEL:
            pass
        self.dialog.hide()
        return response

    def on_btn_apply_clicked(self, widget, data=None):
        self.apply()

    def apply(self):
        updated = False
        updated = updated or self.apply_data_dir()
        updated = updated or self.apply_log_file_config()
        if updated:
            logger.info('saving options')
            app = get_app()
            app.config.save()

    def apply_data_dir(self):
        app = get_app()
        data_dir = path(self.txt_data_dir.get_text())
        if data_dir == app.config['dmf_device']['directory']:
            # If the data directory hasn't changed, we do nothing
            return False

        data_dir.makedirs_p()
        if data_dir.listdir():
            result = app.main_window_controller.question('Target directory is not empty.  Merge contents with current devices (overwriting common paths in the target directory)?')
            if not result == gtk.RESPONSE_YES:
                return False

        for d in app.config['dmf_device']['directory'].dirs():
            copytree(d, data_dir.joinpath(d.name))
        for f in app.config['dmf_device']['directory'].files():
            f.copyfile(data_dir.joinpath(f.name))
        app.config['dmf_device']['directory'].rmtree()
        
        app.config['dmf_device']['directory'] = data_dir
        return True

    def on_chk_log_file_enabled_clicked(self, widget, data=None):
        enabled = widget.get_active()
        log_file = self.txt_log_file.get_text().strip()
        if enabled and not log_file:
            logger.error('Logging can not be enabled without a path selected.')
            widget.set_active(False)

    def apply_log_file_config(self):
        app = get_app()
        enabled = self.chk_log_file_enabled.get_active()
        log_file = path(self.txt_log_file.get_text())
        if enabled and not log_file:
            logger.error('Log file can only be enabled if a path is selected.')
            return False
        app.config['logging']['file'] = log_file
        app.config['logging']['enabled'] = enabled
        app.update_log_file()
        return True

    def browse_for_file(self, title='Select file',
                            action=gtk.FILE_CHOOSER_ACTION_OPEN,
                            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OPEN, gtk.RESPONSE_OK),
                            starting_dir=None):
        dialog = gtk.FileChooserDialog(title=title, action=action,
                                        buttons=buttons)
        if starting_dir:
            dialog.set_current_folder(starting_dir)
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            value = dialog.get_filename()
        else:
            value = None
        dialog.destroy()
        return response, value

    def on_btn_data_dir_browse_clicked(self, widget, data=None):
        app = get_app()
        response, options_dir = self.browse_for_file('Select data directory',
                    action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                    starting_dir=self.txt_data_dir.get_text())
        if response == gtk.RESPONSE_OK:
            logger.info('got new options_dir: %s' % options_dir)
            self.txt_data_dir.set_text(options_dir)

    def on_btn_log_file_browse_clicked(self, widget, data=None):
        app = get_app()
        response, log_file = self.browse_for_file('Open log file',
                    starting_dir=self.txt_data_dir.get_text())
        if response == gtk.RESPONSE_OK:
            logger.info('got new log file path: %s' % log_file)
            self.txt_log_file.set_text(log_file)
