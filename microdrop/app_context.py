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
def get_app():
    import plugin_manager

    class_ = plugin_manager.get_service_class('App', env='microdrop')
    return plugin_manager.get_service_instance(class_, env='microdrop')


def get_hub_uri():
    from plugin_manager import get_service_instance_by_name

    hub_plugin = get_service_instance_by_name('wheelerlab.zmq_hub_plugin',
                                              env='microdrop')
    hub_uri = hub_plugin.get_app_values().get('hub_uri')
    if hub_uri is not None:
        return hub_uri.replace('*', 'localhost')


# Application version used when querying update server for plugins, etc.
APP_VERSION = {'major': 2, 'minor': 0, 'micro': 0}
