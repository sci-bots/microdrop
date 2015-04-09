"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os
import re
import subprocess

import gtk
from path_helpers import path
import yaml
import webbrowser
from jsonrpc.proxy import JSONRPCException
from jsonrpc.json import JSONDecodeException
from flatland import Integer, Form, String, Enum, Boolean
from pygtkhelpers.ui.extra_widgets import Filepath
from pygtkhelpers.ui.form_view_dialog import FormViewDialog

from microdrop_utility import Version
from microdrop_utility.gui import yesno
from protocol import Step
from config import Config
from plugin_manager import (ExtensionPoint, IPlugin, SingletonPlugin,
                            implements, PluginGlobals)
import plugin_manager
from plugin_helpers import AppDataController, get_plugin_info
from logger import (logger, CustomHandler, logging, DEBUG, INFO, WARNING,
                    ERROR, CRITICAL)
from application_repository.application.proxy import AppRepository
from . import base_path

PluginGlobals.push_env('microdrop')


# these imports automatically load (and initialize) core singleton plugins
from .gui import experiment_log_controller
from .gui import config_controller
from .gui import main_window_controller
from .gui import dmf_device_controller
from .gui import protocol_controller
from .gui import protocol_grid_controller
from .gui import plugin_manager_controller
from .gui import app_options_controller


def parse_args(args=None):
    """Parses arguments, returns (options, args)."""
    from argparse import ArgumentParser

    if args is None:
        args = sys.argv

    parser = ArgumentParser(description='Microdrop: graphical user interface '
                            'for the DropBot Digital Microfluidics control '
                            'system.')
    parser.add_argument('-c', '--config', type=path, default=None)

    args = parser.parse_args()
    return args


def test(*args, **kwargs):
    print 'args=%s\nkwargs=%s' % (args, kwargs)


class App(SingletonPlugin, AppDataController):
    implements(IPlugin)
    '''
INFO:  <Plugin App 'microdrop.app'>
INFO:  <Plugin ConfigController 'microdrop.gui.config_controller'>
INFO:  <Plugin DmfDeviceController 'microdrop.gui.dmf_device_controller'>
INFO:  <Plugin ExperimentLogController
         'microdrop.gui.experiment_log_controller'>
INFO:  <Plugin MainWindowController 'microdrop.gui.main_window_controller'>
INFO:  <Plugin ProtocolController 'microdrop.gui.protocol_controller'>
INFO:  <Plugin ProtocolGridController 'microdrop.gui.protocol_grid_controller'>
    '''
    core_plugins = ['microdrop.app',
            'microdrop.gui.config_controller',
            'microdrop.gui.dmf_device_controller',
            'microdrop.gui.experiment_log_controller',
            'microdrop.gui.main_window_controller',
            'microdrop.gui.protocol_controller',
            'microdrop.gui.protocol_grid_controller',]

    AppFields = Form.of(
        Integer.named('width').using(default=1000, optional=True),
        Integer.named('height').using(default=600, optional=True),
        Enum.named('update_automatically' #pylint: disable-msg=E1101,E1120
            ).using(default=1, optional=True
            ).valued('auto-update',
                'check for updates, but ask before installing',
                '''don't check for updates'''),
        String.named('server_url').using( #pylint: disable-msg=E1120
            default='http://microfluidics.utoronto.ca/update',
            optional=True, properties=dict(show_in_gui=False)),
        Boolean.named('realtime_mode').using( #pylint: disable-msg=E1120
            default=False, optional=True,
            properties=dict(show_in_gui=False)),
        Filepath.named('log_file').using( #pylint: disable-msg=E1120
            default='', optional=True,
            properties={'action': gtk.FILE_CHOOSER_ACTION_SAVE}),
        Boolean.named('log_enabled').using( #pylint: disable-msg=E1120
            default=False, optional=True),
        Enum.named('log_level').using( #pylint: disable-msg=E1101, E1120
            default='info', optional=True
            ).valued('debug', 'info', 'warning', 'error', 'critical'),
    )

    def __init__(self):
        args = parse_args()

        print 'Arguments: %s' % args

        self.name = "microdrop.app"
        # get the version number
        self.version = ""
        try:
            raise Exception
            version = subprocess.Popen(['git','describe'],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       stdin=subprocess.PIPE).communicate()[0].rstrip()
            m = re.match('v(\d+)\.(\d+)-(\d+)', version)
            self.version = "%s.%s.%s" % (m.group(1), m.group(2), m.group(3))
            branch = subprocess.Popen(['git','rev-parse', '--abbrev-ref', 'HEAD'],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       stdin=subprocess.PIPE).communicate()[0].rstrip()
            if branch.strip() != 'master':
                self.version += "-%s" % branch
        except:
            import pkg_resources

            version = pkg_resources.get_distribution('microdrop').version

            dev = ('dev' in version)

            self.version = re.sub('\.dev.*', '',
                                  re.sub('post', '', version))
            if dev:
                self.version += "-dev"

        self.realtime_mode = False
        self.running = False
        self.builder = gtk.Builder()
        self.signals = {}
        self.plugin_data = {}

        # these members are initialized by plugins
        self.experiment_log_controller = None
        self.config_controller = None
        self.dmf_device_controller = None
        self.protocol_controller = None
        self.main_window_controller = None

        # Enable custom logging handler
        logger.addHandler(CustomHandler())
        self.log_file_handler = None

        # config model
        try:
            self.config = Config(args.config)
        except IOError:
            logging.error('Could not read configuration file, `%s`.  Make sure'
                          ' it exists and is readable.', args.config)
            raise SystemExit(-1)

        # set the log level
        if self.name in self.config.data and ('log_level' in
                                              self.config.data[self.name]):
            self._set_log_level(self.config.data[self.name]['log_level'])
        logger.info('Microdrop version: %s', self.version)
        logger.info('Running in working directory: %s', os.getcwd())

        # Run post install hooks for freshly installed plugins.
        # It is necessary to delay the execution of these hooks here due to
        # Windows file locking preventing the deletion of files that are in use.
        post_install_queue_path = \
            path(self.config.data['plugins']['directory']) \
            .joinpath('post_install_queue.yml')
        if post_install_queue_path.isfile():
            post_install_queue = yaml.load(post_install_queue_path.bytes())
            post_install_queue = map(path, post_install_queue)

            logger.info('[App] processing post install hooks.')
            for p in post_install_queue:
                try:
                    info = get_plugin_info(p)
                    logger.info("  running post install hook for %s" %
                                info.plugin_name)
                    plugin_manager.post_install(p)
                finally:
                    post_install_queue.remove(p)
            post_install_queue_path.write_bytes(yaml.dump(post_install_queue))

        # Delete paths that were marked during the uninstallation of a plugin.
        # It is necessary to delay the deletion until here due to Windows file
        # locking preventing the deletion of files that are in use.
        deletions_path = path(self.config.data['plugins']['directory'])\
                .joinpath('requested_deletions.yml')
        if deletions_path.isfile():
            requested_deletions = yaml.load(deletions_path.bytes())
            requested_deletions = map(path, requested_deletions)

            logger.info('[App] processing requested deletions.')
            for p in requested_deletions:
                try:
                    if p != p.abspath():
                        logger.info('    (warning) ignoring path %s since it '\
                            'is not absolute' % p)
                        continue
                    if p.isdir():
                        info = get_plugin_info(p)
                        if info:
                            logger.info('  deleting %s' % p)
                            cwd = os.getcwd()
                            os.chdir(p.parent)
                            try:
                                path(p.name).rmtree() #ignore_errors=True)
                            except Exception, why:
                                logger.warning('Error deleting path %s (%s)'\
                                        % (p, why))
                                raise
                            os.chdir(cwd)
                            requested_deletions.remove(p)
                    else: # if the directory doesn't exist, remove it from the
                          # list
                        requested_deletions.remove(p)
                except (AssertionError,):
                    logger.info('  NOT deleting %s' % (p))
                    continue
                except (Exception,):
                    logger.info('  NOT deleting %s' % (p))
                    continue
            deletions_path.write_bytes(yaml.dump(requested_deletions))

        rename_queue_path = path(self.config.data['plugins']['directory'])\
                .joinpath('rename_queue.yml')
        if rename_queue_path.isfile():
            rename_queue = yaml.load(rename_queue_path.bytes())
            requested_renames = [(path(src), path(dst)) for src, dst in rename_queue]
            logger.info('[App] processing requested renames.')
            remaining_renames = []
            for src, dst in requested_renames:
                try:
                    if src.exists():
                        src.rename(dst)
                        logger.info('  renamed %s -> %s' % (src, dst))
                except (AssertionError,):
                    logger.info('  rename unsuccessful: %s -> %s' % (src, dst))
                    remaining_renames.append((str(src), str(dst)))
                    continue
            rename_queue_path.write_bytes(yaml.dump(remaining_renames))

        # dmf device
        self.dmf_device = None

        # protocol
        self.protocol = None

    def get_data(self, plugin_name):
        logger.debug('[App] plugin_data=%s' % self.plugin_data)
        data = self.plugin_data.get(plugin_name)
        if data:
            return data
        else:
            return {}

    def set_data(self, plugin_name, data):
        self.plugin_data[plugin_name] = data

    def on_app_options_changed(self, plugin_name):
        if plugin_name == self.name:
            data = self.get_data(self.name)
            if 'realtime_mode' in data:
                if self.realtime_mode != data['realtime_mode']:
                    self.realtime_mode = data['realtime_mode']
                    if self.protocol_controller:
                        self.protocol_controller.run_step()
            if 'log_file' in data and 'log_enabled' in data:
                self.apply_log_file_config(data['log_file'],
                                           data['log_enabled'])
            if 'log_level' in data:
                self._set_log_level(data['log_level'])
            if 'width' in data and 'height' in data:
                self.main_window_controller.view.set_size_request(
                    data['width'], data['height'])
                # allow window to resize before other signals are processed
                while gtk.events_pending():
                    gtk.main_iteration()

    def apply_log_file_config(self, log_file, enabled):
        if enabled and not log_file:
            logger.error('Log file can only be enabled if a path is selected.')
            return False
        self.update_log_file()
        return True

    @property
    def plugins(self):
        return set(self.plugin_data.keys())

    def plugin_name_lookup(self, name, re_pattern=False):
        if not re_pattern:
            return name

        for plugin_name in self.plugins:
            if re.search(name, plugin_name):
                return plugin_name
        return None

    def _update_setting(self):
        if not self.config['microdrop.app'].get('update_automatically', None):
            self.config['microdrop.app']['update_automatically'] = \
                'check for updates, but ask before installing'
        return self.config['microdrop.app']['update_automatically']

    def update_check(self):
        if self._update_setting() not in ('auto-update',
                                          'check for updates, but ask before '
                                          'installing'):
            return

        app_update_server_url = self.config.data.get(self.name, {}).get(
                'server_url', 'http://microfluidics.utoronto.ca/update')
        logger.debug('[APP UPDATE SERVER] server url: %s' % app_update_server_url)
        app_repository = AppRepository(app_update_server_url)
        current_version = Version.fromstring(self.version)
        try:
            latest_version = Version(**app_repository.latest_version('microdrop'))
        except (JSONRPCException, JSONDecodeException, IOError):
            logger.warning('Could not connect to application update server: '
                           '%s', app_update_server_url)
            return
        if current_version < latest_version:
            logger.info('Current version: %s. There is a new version '
                        'available: %s %s' % (current_version, latest_version,
                                               app_repository.server_url +
                                               app_repository
                                               .latest_package_url(
                                                   'microdrop')))
            response = yesno('''
There is a new version of Microdrop available (%s, current version: %s).

Would you like to download the latest version in your browser?''' %
                             (latest_version, current_version))
            if response == gtk.RESPONSE_YES:
                latest_full_url = (app_repository.server_url + app_repository
                                   .latest_package_url('microdrop'))
                if webbrowser.open_new_tab(latest_full_url):
                    logger.info('Closing app after opening browser to latest '
                                'version (%s).' % latest_version)
                    try:
                        self.main_window_controller.on_destroy(None)
                    except AttributeError:
                        raise SystemExit, 'Closing app to allow upgrade installation'
        else:
            logger.info('[SUCCESS] software is up-to-date.\n (installed '
                        'version: %s, server version: %s)' % (current_version,
                                                              latest_version))

    def update_plugins(self):
        update_setting = self._update_setting()

        if update_setting == 'auto-update':
            # Auto-update
            update = True
            force = True
            logger.info('Auto-update')
        elif update_setting == 'check for updates, but ask before installing':
            # Check for updates, but ask before installing
            update = True
            force = False
            logger.info('Check for updates, but ask before installing')
        else:
            logger.info('Updates disabled')
            update = False

        if update:
            service = plugin_manager.get_service_instance_by_name(
                    'microdrop.gui.plugin_manager_controller', env='microdrop')
            if service.update_all_plugins(force=force):
                logger.warning('Plugins have been updated.  The application '
                               'must be restarted.')
                raise SystemExit, 'Closing app after plugins auto-upgrade'
            else:
                logger.info('No plugins have been updated')

    def run(self):
        # set realtime mode to false on startup
        if self.name in self.config.data and \
        'realtime_mode' in self.config.data[self.name]:
            self.config.data[self.name]['realtime_mode'] = False

        plugin_manager.emit_signal('on_plugin_enable')
        log_file = self.get_app_values()['log_file']
        if not log_file:
            self.set_app_values({'log_file':
                                 path(self.config['data_dir'])
                                 .joinpath('microdrop.log')})

        self.update_check()
        plugin_manager.load_plugins(self.config['plugins']['directory'])
        self.update_log_file()

        logger.info('User data directory: %s' % self.config['data_dir'])
        logger.info('Plugins directory: %s' %
                    self.config['plugins']['directory'])
        logger.info('Devices directory: %s' % self.get_device_directory())

        FormViewDialog.default_parent = self.main_window_controller.view
        self.builder.connect_signals(self.signals)
        self.update_plugins()

        observers = {}
        # Enable plugins according to schedule requests
        for package_name in self.config['plugins']['enabled']:
            try:
                service = plugin_manager. \
                    get_service_instance_by_package_name(package_name)
                observers[service.name] = service
            except Exception, e:
                self.config['plugins']['enabled'].remove(package_name)
                logger.error(e)
        schedule = plugin_manager.get_schedule(observers, "on_plugin_enable")

        # Load optional plugins marked as enabled in config
        for p in schedule:
            try:
                plugin_manager.enable(p)
            except KeyError:
                logger.warning('Requested plugin (%s) is not available.\n\n'
                    'Please check that it exists in the plugins '
                    'directory:\n\n    %s' % (p, self.config['plugins']['directory']))
        plugin_manager.log_summary()

        self.experiment_log = None

        # save the protocol name from the config file because it is
        # automatically overwritten when we load a new device
        protocol_name = self.config['protocol']['name']

        # if there is no device specified in the config file, try choosing one
        # from the device directory by default
        device_directory = path(self.get_device_directory())
        if not self.config['dmf_device']['name']:
            try:
                self.config['dmf_device']['name'] = \
                    device_directory.dirs()[0].name
            except:
                pass

        # load the device from the config file
        if self.config['dmf_device']['name']:
            if device_directory:
                device_path = os.path.join(device_directory,
                                           self.config['dmf_device']['name'],
                                           'device')
                self.dmf_device_controller.load_device(device_path)


        # if we successfully loaded a device
        if self.dmf_device:
            # reapply the protocol name to the config file
            self.config['protocol']['name'] = protocol_name

            # load the protocol
            if self.config['protocol']['name']:
                directory = self.get_device_directory()
                if directory:
                    filename = os.path.join(directory,
                        self.config['dmf_device']['name'],
                        "protocols",
                        self.config['protocol']['name'])
                    self.protocol_controller.load_protocol(filename)

        plugin_manager.emit_signal('on_gui_ready')
        self.main_window_controller.main()

    def _set_log_level(self, level):
        if level=='debug':
            logger.setLevel(DEBUG)
        elif level=='info':
            logger.setLevel(INFO)
        elif level=='warning':
            logger.setLevel(WARNING)
        elif level=='error':
            logger.setLevel(ERROR)
        elif level=='critical':
            logger.setLevel(CRITICAL)
        else:
            raise TypeError

    def _set_log_file_handler(self, log_file):
        if self.log_file_handler:
            self._destroy_log_file_handler()
        self.log_file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        self.log_file_handler.setFormatter(formatter)
        logger.addHandler(self.log_file_handler)
        logger.info('[App] added log_file_handler: %s' % log_file)

    def _destroy_log_file_handler(self):
        if self.log_file_handler is None:
            return
        logger.info('[App] closing log_file_handler')
        self.log_file_handler.close()
        del self.log_file_handler
        self.log_file_handler = None

    def update_log_file(self):
        plugin_name = 'microdrop.app'
        values = AppDataController.get_plugin_app_values(plugin_name)
        logger.debug('[App] update_log_file %s' % values)
        required = set(['log_enabled', 'log_file'])
        if values is None or required.intersection(values.keys()) != required:
            return
        # values contains both log_enabled and log_file
        log_file = values['log_file']
        log_enabled = values['log_enabled']
        if self.log_file_handler is None:
            if log_enabled:
                self._set_log_file_handler(log_file)
                logger.info('[App] logging enabled')
        else:
            # Log file handler already exists
            if log_enabled:
                if log_file != self.log_file_handler.baseFilename:
                    # Requested log file path has been changed
                    self._set_log_file_handler(log_file)
            else:
                self._destroy_log_file_handler()

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        self.dmf_device = dmf_device

    def on_protocol_swapped(self, old_protocol, new_protocol):
        self.protocol = new_protocol

    def on_experiment_log_changed(self, experiment_log):
        self.experiment_log = experiment_log

    def get_device_directory(self):
        observers = ExtensionPoint(IPlugin)
        plugin_name = 'microdrop.gui.dmf_device_controller'
        service = observers.service(plugin_name)
        values = service.get_app_values()
        if values and 'device_directory' in values:
            directory = path(values['device_directory'])
            if directory.isdir():
                return directory
        return None

    def paste_steps(self, step_number=None):
        if step_number is None:
            # Default to pasting after the current step
            step_number = self.protocol.current_step_number + 1
        clipboard = gtk.clipboard_get()
        try:
            new_steps = yaml.load(clipboard.wait_for_text())
            for step in new_steps:
                if not isinstance(step, Step):
                    # Invalid object type
                    return
        except (Exception,), why:
            logger.info('[paste_steps] invalid data: %s', why)
            return
        self.protocol.insert_steps(step_number, values=new_steps)

    def copy_steps(self, step_ids):
        steps = [self.protocol.steps[id] for id in step_ids]
        if steps:
            clipboard = gtk.clipboard_get()
            clipboard.set_text(yaml.dump(steps))

    def delete_steps(self, step_ids):
        self.protocol.delete_steps(step_ids)

    def cut_steps(self, step_ids):
        self.copy_steps(step_ids)
        self.delete_steps(step_ids)


PluginGlobals.pop_env()


if __name__ == '__main__':
    os.chdir(base_path())
