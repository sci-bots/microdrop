import cPickle as pickle
import threading

from pygtkhelpers.gthreads import gtk_threadsafe
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import zmq

from ...app_context import get_app, get_hub_uri
from ...plugin_manager import (IPlugin, PluginGlobals, ScheduleRequest,
                               SingletonPlugin, emit_signal, implements)


class DeviceInfoZmqPlugin(ZmqPlugin):
    def on_execute__get_device(self, request):
        app = get_app()
        return app.dmf_device

    def on_execute__get_svg_frame(self, request):
        app = get_app()
        return app.dmf_device.get_svg_frame()

    def on_execute__get_electrode_channels(self, request):
        app = get_app()
        return app.dmf_device.get_electrode_channels()

    def on_execute__set_electrode_channels(self, request):
        '''
        Set channels for electrode `electrode_id` to `channels`.

        This includes updating `self.df_electrode_channels`.

        .. note:: Existing channels assigned to electrode are overwritten.

        Parameters
        ----------
        electrode_id : str
            Electrode identifier.
        channels : list
            List of channel identifiers assigned to the electrode.
        '''
        data = decode_content_data(request)
        app = get_app()
        modified = (app.dmf_device
                    .set_electrode_channels(data['electrode_id'],
                                            data['channels']))
        if modified:
            emit_signal("on_dmf_device_changed", [app.dmf_device])
        return modified

    def on_execute__dumps(self, request):
        app = get_app()
        return pickle.dumps(app.dmf_device)


PluginGlobals.push_env('microdrop')


class DeviceInfoPlugin(SingletonPlugin):
    """
    This class is automatically registered with the PluginManager.
    """
    implements(IPlugin)
    plugin_name = 'microdrop.device_info_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.plugin = None
        self.stopped = threading.Event()

    def on_plugin_enable(self):
        """
        Handler called once the plugin instance is enabled.

        Note: if you inherit your plugin from AppDataController and don't
        implement this handler, by default, it will automatically load all
        app options from the config file. If you decide to overide the
        default handler, you should call:

            AppDataController.on_plugin_enable(self)

        to retain this functionality.

        .. versionchanged:: 2.11.2
            Use :func:`gtk_threadsafe` decorator to wrap thread-related code
            to ensure GTK/GDK are initialized properly for a threaded
            application.
        .. versionchanged:: X.X.X
            Once enabled, do not stop socket listening thread.  Re-enabling the
            plugin will cause the listening thread to be restarted.

            This ensures that calls to
            :func:`microdrop.plugin_manager.hub_execute` continue to work as
            expected even after ``on_app_exit`` signal is emitted.
        """
        if self.plugin is not None:
            self.cleanup()
        self.plugin = DeviceInfoZmqPlugin(self.name, get_hub_uri())
        # Initialize sockets.
        self.plugin.reset()

        def _check_command_socket(wait_duration_s):
            '''
            Process each incoming message on the ZeroMQ plugin command socket.

            Stop listening if :attr:`stopped` event is set.
            '''
            self.stopped.clear()
            while not self.stopped.wait(wait_duration_s):
                try:
                    msg_frames = (self.plugin.command_socket
                                  .recv_multipart(zmq.NOBLOCK))
                    self.plugin.on_command_recv(msg_frames)
                except zmq.Again:
                    # No message ready.
                    pass
                except ValueError:
                    # Message was empty or not valid JSON.
                    pass

        @gtk_threadsafe
        def _launch_socket_monitor_thread():
            '''
            Launch background thread to monitor plugin ZeroMQ command socket.
            '''
            thread = threading.Thread(target=_check_command_socket,
                                      args=(0.01, ))
            thread.daemon = True
            thread.start()

        _launch_socket_monitor_thread()

    def cleanup(self):
        self.stopped.set()
        if self.plugin is not None:
            self.plugin = None

    def on_dmf_device_swapped(self, old_device, new_device):
        if self.plugin is not None:
            # Notify other plugins that device has been swapped.
            self.plugin.execute_async(self.name, 'get_device')

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest instances)
        for the function specified by function_name.
        """
        if function_name == 'on_dmf_device_swapped':
            return [ScheduleRequest('microdrop.app', self.name)]
        return []


PluginGlobals.pop_env()
