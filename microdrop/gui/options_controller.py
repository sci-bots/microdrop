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
    def __init__(self, app):
        self.app = app
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                                           "glade",
                                           "configuration_dialog.glade"))
        self.dialog = builder.get_object("configuration_dialog")
        self.dialog.set_transient_for(app.main_window_controller.view)
        self.txt_data_dir = builder.get_object('txt_data_dir')
        self.btn_data_dir_browse = builder.get_object('btn_data_dir_browse')
        self.btn_ok = builder.get_object('btn_ok')
        self.btn_apply = builder.get_object('btn_apply')
        self.btn_cancel = builder.get_object('btn_cancel')
        self.txt_data_dir.set_text(path(self.app.config.dmf_device_directory).abspath())

        builder.connect_signals(self)
        self.builder = builder

    def run(self):
        response = self.dialog.run()
        if response == gtk.RESPONSE_OK:
            print 'ok'
            self.apply()
        elif response == gtk.RESPONSE_CANCEL:
            print 'cancel'
        self.dialog.hide()
        return response

    def on_btn_apply_clicked(self, widget, data=None):
        self.apply()

    def apply(self):
        data_dir = path(self.txt_data_dir.get_text())
        if data_dir == self.app.config.dmf_device_directory:
            return

        print 'apply changes:', data_dir
        data_dir.makedirs_p()
        if data_dir.listdir():
            from standalone_message_dialog import MessageDialog

            m = MessageDialog()
            result = m.ques('Target directory is not empty.  Merge contents with current devices (overwriting common paths in the target directory)?')
            if not result == gtk.RESPONSE_OK:
                return

        for d in self.app.config.dmf_device_directory.dirs():
            copytree(d, data_dir.joinpath(d.name))
        for f in self.app.config.dmf_device_directory.files():
            f.copyfile(data_dir.joinpath(f.name))
        self.app.config.dmf_device_directory.rmtree()
        
        self.app.config.dmf_device_directory = data_dir
        self.app.config.save()

    def on_btn_data_dir_browse_clicked(self, widget, data=None):
        dialog = gtk.FileChooserDialog(title="Select data directory",
                                        action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                                        buttons=(gtk.STOCK_CANCEL,
                                                gtk.RESPONSE_CANCEL,
                                                gtk.STOCK_OPEN,
                                                gtk.RESPONSE_OK))
        dialog.set_current_folder(self.txt_data_dir.get_text())
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            options_dir = dialog.get_filename()
            print 'got new options_dir:', options_dir
            self.txt_data_dir.set_text(options_dir)
                        
        dialog.destroy()
        self.app.main_window_controller.update()
