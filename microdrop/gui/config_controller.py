import logging

from ..app_context import get_app
from logging_helpers import _L  #: .. versionadded:: 2.20
from ..plugin_manager import (IPlugin, SingletonPlugin, implements,
                              PluginGlobals, ExtensionPoint, ScheduleRequest)

logger = logging.getLogger(__name__)

PluginGlobals.push_env('microdrop')


class ConfigController(SingletonPlugin):
    implements(IPlugin)

    def __init__(self):
        self.name = "microdrop.gui.config_controller"
        self.app = None

    def on_plugin_enable(self):
        self.app = get_app()
        self.app.config_controller = self

        # load all app options from the config file
        observers = ExtensionPoint(IPlugin)
        for section_name, values_dict in self.app.config.data.iteritems():
            service = observers.service(section_name)
            if service:
                if hasattr(service, 'set_app_values'):
                    service.set_app_values(values_dict)
                else:
                    _L().error('Invalid section in config file: [%s].',
                               section_name)
                    self.app.config.data.pop(section_name)

    def on_app_exit(self):
        self.app.config.save()

    def on_dmf_device_changed(self, dmf_device):
        device_name = None
        if dmf_device:
            device_name = dmf_device.name
        if self.app.config['dmf_device']['name'] != device_name:
            self.app.config['dmf_device']['name'] = device_name
            self.app.config.save()

    def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
        self.on_dmf_device_changed(dmf_device)

    def on_protocol_changed(self):
        if self.app.protocol.name != self.app.config['protocol']['name']:
            self.app.config['protocol']['name'] = self.app.protocol.name
            self.app.config.save()

    def on_protocol_swapped(self, old_protocol, protocol):
        self.on_protocol_changed()

    def on_app_options_changed(self, plugin_name):
        if self.app is None:
            return
        _L().debug('on_app_options_changed: %s' % plugin_name)
        observers = ExtensionPoint(IPlugin)
        service = observers.service(plugin_name)
        if service:
            if not hasattr(service, 'get_app_values'):
                return
            app_options = service.get_app_values()
            if app_options:
                if plugin_name not in self.app.config.data:
                    self.app.config.data[plugin_name] = {}
                self.app.config.data[plugin_name].update(app_options)
                self.app.config.save()

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest
        instances) for the function specified by function_name.
        """
        if function_name == 'on_plugin_enable':
            return [ScheduleRequest("microdrop.gui.main_window_controller",
                                    self.name)]
        elif function_name == 'on_protocol_swapped':
            # make sure that the app's protocol reference is valid
            return [ScheduleRequest("microdrop.app", self.name)]
        elif function_name == 'on_dmf_device_swapped':
            # make sure that the app's dmf device reference is valid
            return [ScheduleRequest("microdrop.app", self.name)]
        return []


PluginGlobals.pop_env()
