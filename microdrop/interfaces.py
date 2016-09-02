from pyutilib.component.core import Interface, PluginGlobals
import threading

print '[interfaces] %s' % threading.current_thread()

PluginGlobals.push_env('microdrop.managed')
PluginGlobals.pop_env()


PluginGlobals.push_env('microdrop')


if 'IFoo' in PluginGlobals.interface_registry:
    IFoo = PluginGlobals.interface_registry['IFoo']
else:
    class IFoo(Interface):
        pass


if 'ILoggingPlugin' in PluginGlobals.interface_registry:
    ILoggingPlugin = PluginGlobals.interface_registry['ILoggingPlugin']
else:
    class ILoggingPlugin(Interface):
        def on_debug(self, record):
            pass

        def on_info(self, record):
            pass

        def on_warning(self, record):
            pass

        def on_error(self, record):
            pass

        def on_critical(self, record):
            pass


if 'IWaveformGenerator' in PluginGlobals.interface_registry:
    IWaveformGenerator = PluginGlobals.interface_registry['IWaveformGenerator']
else:
    class IWaveformGenerator(Interface):
        def set_voltage(self, voltage):
            """
            Set the waveform voltage.

            Parameters:
                voltage : RMS voltage
            """
            pass

        def set_frequency(self, frequency):
            """
            Set the waveform frequency.

            Parameters:
                frequency : frequency in Hz
            """
            pass


if 'IPlugin' in PluginGlobals.interface_registry:
    IPlugin = PluginGlobals.interface_registry['IPlugin']
else:
    class IPlugin(Interface):
        def get_schedule_requests(self, function_name):
            """

            Args:

                function_name (str) : Plugin callback function name.

            Returns
            -------
            list
                List of scheduling requests (i.e., :class:`ScheduleRequest`
                instances) for the function specified by :data:`function_name`.
            """
            return []

        def on_plugin_disable(self):
            """
            Handler called once the plugin instance is disabled.
            """
            pass

        def on_plugin_enable(self):
            """
            Handler called once the plugin instance is enabled.

            Note: if you inherit your plugin from AppDataController and don't
            implement this handler, by default, it will automatically load all
            app options from the config file. If you decide to overide the
            default handler, you should call:

                AppDataController.on_plugin_enable(self)

            to retain this functionality.
            """
            pass

        def on_plugin_enabled(self, env, plugin):
            """
            Handler called to notify that a plugin has been enabled.

            Note that this signal is broadcast to all plugins implementing the
            :class:`IPlugin` interface, whereas the :meth:`on_plugin_enable`
            method is called directly on the plugin that is being enabled.

            Parameters
            ----------
            env : str
                :mod:`pyutilib` plugin environment.
            plugin : str
                Plugin name.
            """
            pass

        def on_plugin_disabled(self, env, plugin):
            """
            Handler called to notify that a plugin has been disabled.

            Note that this signal is broadcast to all plugins implementing the
            :class:`IPlugin` interface, whereas the :meth:`on_plugin_disable`
            method is called directly on the plugin that is being disabled.

            Parameters
            ----------
            env : str
                :mod:`pyutilib` plugin environment.
            plugin : str
                Plugin name.
            """
            pass

        def on_app_exit(self):
            """
            Handler called just before the Microdrop application exits.
            """
            pass

        def on_protocol_swapped(self, old_protocol, protocol):
            """
            Handler called when a different protocol is swapped in (e.g., when
            a protocol is loaded or a new protocol is created).

            Parameters
            ----------
            old_protocol : microdrop.protocol.Protocol
                Original protocol.
            protocol : microdrop.protocol.Protocol
                New protocol.
            """
            pass

        def on_protocol_changed(self):
            """
            Handler called when a protocol is modified.
            """
            pass

        def on_protocol_run(self):
            """
            Handler called when a protocol starts running.
            """
            pass

        def on_protocol_pause(self):
            """
            Handler called when a protocol is paused.
            """
            pass

        def on_dmf_device_swapped(self, old_dmf_device, dmf_device):
            """
            Handler called when a different DMF device is swapped in (e.g., when
            a new device is loaded).

            Parameters
            ----------
            old_dmf_device : microdrop.dmf_device.DmfDevice
                Original device.
            dmf_device : microdrop.dmf_device.DmfDevice
                New device.
            """
            pass

        def on_dmf_device_changed(self, dmf_device):
            """
            Handler called when a DMF device is modified (e.g., channel
            assignment, scaling, etc.).

            Args:

                dmf_device (microdrop.dmf_device.DmfDevice)
            """
            pass

        def on_dmf_device_saved(self, dmf_device):
            """
            Handler called when a DMF device is saved.

            Args:

                dmf_device (microdrop.dmf_device.DmfDevice)
            """
            pass

        def on_experiment_log_changed(self, experiment_log):
            """
            Handler called when the current experiment log changes (e.g., when a
            protocol finishes running.

            Parameters
            ----------
            experiment_log : microdrop.experiment_log.ExperimentLog
                Reference to new experiment log instance.
            """
            pass

        def on_experiment_log_selection_changed(self, data):
            """
            Handler called whenever the experiment log selection changes.

            Parameters:
                data : experiment log data (list of dictionaries, one per step)
                    for the selected steps
            """
            pass

        def on_app_options_changed(self, plugin_name):
            """
            Handler called when the app options are changed for a particular
            plugin.  This will, for example, allow for GUI elements to be
            updated.

            Parameters
            ----------
            plugin : str
                Plugin name for which the app options changed
            """
            pass

        def on_step_options_changed(self, plugin, step_number):
            """
            Handler called when the step options are changed for a particular
            plugin.  This will, for example, allow for GUI elements to be
            updated based on step specified.

            Parameters
            ----------
            plugin : SingletonPlugin
                Plugin instance for which the step options changed.
            step_number : int
                Step number that the options changed for.
            """
            pass

        def on_step_options_swapped(self, plugin, old_step_number, step_number):
            """
            Handler called when the step options are changed for a particular
            plugin.  This will, for example, allow for GUI elements to be
            updated based on step specified.

            Parameters
            ----------
            plugin : SingletonPlugin
                Plugin instance for which the step options changed.
            old_step_number : int
                Original step number.
            step_number : int
                New step number.
            """
            pass

        def on_step_swapped(self, old_step_number, step_number):
            """
            Handler called when the current step is swapped.

            Parameters
            ----------
            old_step_number : int
                Original step number.
            step_number : int
                New step number.
            """
            pass

        def on_step_run(self):
            """
            Handler called whenever a step is executed. Note that this signal
            is only emitted in realtime mode or if a protocol is running.

            Plugins that handle this signal must emit the
            :meth:`on_step_complete` signal once they have completed the step.
            The protocol controller will wait until all plugins have completed
            the current step before proceeding.

            Returns
            -------
            str or None

             - ``'Repeat'``: repeat the step
             - ``'Fail'``: unrecoverable error (stop the protocol)
            """
            pass

        def on_step_complete(self, plugin_name, return_value=None):
            """
            Handler called whenever a plugin completes a step.

            Returns
            -------
            str or None

             - ``'Repeat'``: repeat the step
             - ``'Fail'``: unrecoverable error (stop the protocol)
            """
            pass

        def on_step_created(self, step_number):
            """
            Handler called whenever a new step is created.

            Parameters
            ----------
            step_number : int
                New step number.
            """
            pass

        def get_step_form_class(self):
            pass

        def get_step_values(self, step_number=None):
            pass

        def on_metadata_changed(self, schema, original_metadata, metadata):
            '''
            Handler called each time the experiment metadata has changed.

            Parameters
            ----------
            schema : dict
                jsonschema schema definition for metadata.
            original_metadata
                Original metadata.
            metadata
                New metadata matching :data:`schema`
            '''
            pass
