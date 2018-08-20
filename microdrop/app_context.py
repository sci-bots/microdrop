def get_app():
    import plugin_manager

    class_ = plugin_manager.get_service_class('App', env='microdrop')
    return plugin_manager.get_service_instance(class_, env='microdrop')


def get_hub_uri():
    from plugin_manager import get_service_instance_by_name

    hub_plugin = get_service_instance_by_name('microdrop.zmq_hub_plugin',
                                              env='microdrop')
    hub_uri = hub_plugin.get_app_values().get('hub_uri')
    if hub_uri is not None:
        return hub_uri.replace('*', 'localhost')


# Application version used when querying update server for plugins, etc.
APP_VERSION = {'major': 2, 'minor': 0, 'micro': 0}

# Operating modes
# ===============
#: Programming mode
MODE_PROGRAMMING           = 1 << 0
#: Programming mode with real-time enabled
MODE_REAL_TIME_PROGRAMMING = 1 << 1
#: Protocol running
MODE_RUNNING               = 1 << 2
#: Protocol running with real-time enabled
MODE_REAL_TIME_RUNNING     = 1 << 3

MODE_REAL_TIME_MASK = MODE_REAL_TIME_PROGRAMMING | MODE_REAL_TIME_RUNNING
MODE_RUNNING_MASK = MODE_RUNNING | MODE_REAL_TIME_RUNNING
MODE_PROGRAMMING_MASK = MODE_PROGRAMMING | MODE_REAL_TIME_PROGRAMMING
