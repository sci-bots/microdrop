import cPickle as pickle
import threading

from pygtkhelpers.gthreads import gtk_threadsafe
from pygtkhelpers.schema import schema_dialog
from zmq_plugin.plugin import Plugin as ZmqPlugin
from zmq_plugin.schema import decode_content_data
import zmq

from ...app_context import get_app, get_hub_uri
from ...plugin_helpers import hub_execute, hub_execute_async
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

        .. versionchanged:: 2.25
            Emit ``on_dmf_device_changed`` in main GTK thread to ensure
            thread-safety.
        '''
        data = decode_content_data(request)
        app = get_app()
        modified = (app.dmf_device
                    .set_electrode_channels(data['electrode_id'],
                                            data['channels']))
        if modified:
            gtk_threadsafe(emit_signal)("on_dmf_device_changed",
                                        [app.dmf_device])
        return modified

    def on_execute__dumps(self, request):
        app = get_app()
        return pickle.dumps(app.dmf_device)

    def on_execute__edit_electrode_channels(self, request):
        '''
        Display dialog to edit the channels mapped to the specified electrode.

        Parameters
        ----------
        request : dict
            Request with decoded data field:
            - ``electrode_id``: electrode identifier (``str``).
              - e.g., ``"electrode028"``

        .. versionadded:: 2.25
        '''
        data = decode_content_data(request)
        electrode_id = data['electrode_id']
        app = get_app()

        # Create schema to only accept a well-formed comma-separated list
        # of integer channel numbers.  Default to list of channels
        # currently mapped to electrode.
        if electrode_id in app.dmf_device.channels_by_electrode.index:
            # If there is a single channel mapped to the electrode, the
            # `...ix[electrode_id]` lookup below returns a `pandas.Series`.
            # However, if multiple channels are mapped to the electrode the
            # `...ix[electrode_id]` lookup returns a `pandas.DataFrame`.
            # Calling `.values.ravel()` returns data in the same form in either
            # situation.
            current_channels = (app.dmf_device.channels_by_electrode
                                .ix[[electrode_id]].values.ravel().tolist())
        else:
            # Electrode has no channels currently mapped to it.
            current_channels = []
        schema = {'type': 'object',
                  'properties': {'channels':
                                 {'type': 'string', 'pattern':
                                  r'^(\d+\s*(,\s*\d+\s*)*)?$',
                                  'default': ','.join(map(str,
                                                          current_channels))}}}

        @gtk_threadsafe
        def _dialog():
            try:
                # Prompt user to enter a list of channel numbers (or nothing).
                result = schema_dialog(schema, device_name=False,
                                       parent=app.main_window_controller.view)
            except ValueError:
                pass
            else:
                # Well-formed (according to schema pattern) comma-separated
                # list of channels was provided.
                channels = sorted(set(map(int, filter(len, result['channels']
                                                        .split(',')))))
                hub_execute(self.name, 'set_electrode_channels',
                            electrode_id=electrode_id, channels=channels)
        _dialog()


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
        .. versionchanged:: 2.11.2
            Use :func:`gtk_threadsafe` decorator to wrap thread-related code
            to ensure GTK/GDK are initialized properly for a threaded
            application.
        .. versionchanged:: 2.15.2
            Once enabled, do not stop socket listening thread.  Re-enabling the
            plugin will cause the listening thread to be restarted.

            This ensures that calls to
            :func:`microdrop.plugin_manager.hub_execute` continue to work as
            expected even after ``on_app_exit`` signal is emitted.
        .. versionchanged:: 2.25
            Register ``"Edit electrode channels..."`` command with command
            plugin.
        """
        if self.plugin is not None:
            self.cleanup()

        self.plugin = DeviceInfoZmqPlugin(self.name, get_hub_uri())

        zmq_ready = threading.Event()

        def _check_command_socket(wait_duration_s):
            '''
            Process each incoming message on the ZeroMQ plugin command socket.

            Stop listening if :attr:`stopped` event is set.
            '''
            # Initialize sockets.
            self.plugin.reset()
            zmq_ready.set()
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

        thread = threading.Thread(target=_check_command_socket, args=(0.01, ))
        thread.daemon = True
        thread.start()
        zmq_ready.wait()

        hub_execute_async('microdrop.command_plugin', 'register_command',
                          command_name='edit_electrode_channels',
                          namespace='electrode', plugin_name=self.name,
                          title='Edit electrode _channels...')

    def cleanup(self):
        self.stopped.set()
        if self.plugin is not None:
            self.plugin = None

    @gtk_threadsafe
    def on_dmf_device_changed(self, device):
        '''
        Notify other plugins that device has been modified.

        .. versionadded:: 2.25
        '''
        hub_execute(self.name, 'get_device')

    @gtk_threadsafe
    def on_dmf_device_swapped(self, old_device, new_device):
        '''
        Notify other plugins that device has been swapped.
        '''
        hub_execute(self.name, 'get_device')

    def get_schedule_requests(self, function_name):
        """
        Returns a list of scheduling requests (i.e., ScheduleRequest instances)
        for the function specified by function_name.


        .. versionchanged:: 2.25
            Enable _after_ command plugin and zmq hub to ensure commands can be
            registered.
        """
        if function_name == 'on_dmf_device_swapped':
            return [ScheduleRequest('microdrop.app', self.name)]
        elif function_name == 'on_plugin_enable':
            return [ScheduleRequest('microdrop.zmq_hub_plugin', self.name),
                    ScheduleRequest('microdrop.command_plugin', self.name)]
        return []


PluginGlobals.pop_env()
