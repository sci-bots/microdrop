from pyutilib.component.core import Interface, PluginGlobals
import threading

import trollius as asyncio


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
        '''
        .. versionchanged:: 2.29
            Deprecate `on_step_complete`.  Step completion is implied by each
            plugin returning from the respective :meth:`on_step_run` coroutine.
        '''
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
            Handler called just before the MicroDrop application exits.
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

        def on_protocol_finished(self):
            """
            Handler called when a protocol finishes (i.e., runs the last step of
            the final repetition).
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

        def on_export_experiment_log_data(self, experiment_log):
            """
            Handler called when the experiment log is exported.

            Parameters:
                log : experiment log data (list of dictionaries, one per step)
                    for the selected steps

            Returns:
                A dictionary of pandas.DataFrame objects containing any relevant
                data that should be exported by the plugin, each keyed by a unique
                name.
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

        @asyncio.coroutine
        def on_step_run(self, plugin_kwargs, signals):
            """
            XXX Coroutine XXX

            Handler called whenever a step is executed. Note that this signal
            is only emitted in realtime mode or if a protocol is running.
            The protocol controller will wait until all plugins have completed
            the current step before proceeding.

            Parameters
            ----------
            plugin_kwargs : dict
                Plugin settings as JSON serializable dictionary.
            signals : blinker.Namespace
                Signals namespace.
                .. warning::
                    Plugins **MUST**::
                    - connect blinker :data:`signals` callbacks before any
                      yielding call (e.g., ``yield asyncio.From(...)``) in the
                      ``on_step_run()`` coroutine; **_and_**
                    - wait for the ``'signals-connected'`` blinker signal to be
                      sent before sending any signal to ensure all other
                      plugins have had a chance to connect any relevant
                      callbacks.

            Returns
            -------
            object
                JSON serializable object.


            .. versionchanged:: 2.29
                Change to a coroutine.

            .. versionchanged:: 2.30
                Refactor to decouple from ``StepOptionsController`` by using
                :data:`plugin_kwargs` instead of reading parameters using
                :meth:`get_step_options()`.  Add :data:`signals` parameter as a
                signals namespace for plugins during step execution.
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


if 'IElectrodeActuator' in PluginGlobals.interface_registry:
    IElectrodeActuator = PluginGlobals.interface_registry['IElectrodeActuator']
else:
    class IElectrodeController(Interface):
        '''
        Interface to manage state of electrodes and issue actuation requests to
        `IElectrodeActuator` plugins.
        '''
        @asyncio.coroutine
        def request_electrode_states(self, electrode_states):
            '''
            XXX Coroutine XXX

            Request static electrode states.

            Parameters
            ----------
            electrode_states : pandas.Series
            '''
            pass

    class IElectrodeActuator(Interface):
        '''
        Execute electrode actuations from an `IElectrodeController`.
        '''
        @asyncio.coroutine
        def on_actuation_request(self, electrode_states, duration_s=0,
                                 volume_threshold=None):
            '''
            XXX Coroutine XXX

            Request actuation of electrodes according to specified states.

            Parameters
            ----------
            electrode_states : pandas.Series
            duration_s : float, optional
                If :data:`volume_threshold` is specified, maximum duration
                before timing out.  Otherwise, time to actuate before actuation
                is considered completed.
            volume_threshold : float, optional
                Fraction of expected volume before actuation should be
                considered completed.

            Returns
            -------
            actuated_electrodes : list
                List of actuated electrode IDs.
            '''
            pass

    class IElectrodeMutator(Interface):
        '''
        Generate dynamic actuation state(s) for `IElectrodeController`.
        '''
        def get_electrode_states_request(self):
            '''
            Return electrode states request or ``None`` if no electrode states
            are required.

            **Note that this may be called multiple times per step.**

            Returns
            -------
            electrode_states : pandas.Series
            '''
            pass

    class IApplicationMode(Interface):
        '''
        Interface for plugins for which behaviour depends on application mode.


        .. versionadded:: 2.25
        '''
        def on_mode_changed(self):
            '''
            Called when application mode has changed.

            See `microdrop.app` for modes (e.g., ``MODE_PROGRAMMING``, etc.).
            '''
            pass
