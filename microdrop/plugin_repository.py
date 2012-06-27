import urllib

from path import path
from jsonrpc import ServiceProxy


class PluginRepository(object):
    def __init__(self, server_url):
        self.server_url = server_url
        self._proxy = None
        self.proxy

    @property
    def proxy(self):
        if self._proxy is None:
            proxy = ServiceProxy(self.server_url + '/json/')
            self._proxy = proxy
        return self._proxy

    def api_version(self):
        return self.proxy.repository.api_version()

    def available_plugins(self):
        return self.proxy.repository.available_plugins()

    def latest_version(self, plugin_name):
        return self.proxy.repository.plugin_latest_version(plugin_name)

    def versions(self, plugin_name):
        return self.proxy.repository.plugin_versions(plugin_name)

    def download_latest(self, plugin_name, output_dir):
        output_dir = path(output_dir)
        available_plugins = self.proxy.repository.available_plugins()
        if plugin_name not in available_plugins:
            raise ValueError, '''\
    Plugin %s is not available.
    Available plugins include: %s''' % (plugin_name, ', '.join(
                    available_plugins))
        latest_version = self.proxy.repository.plugin_latest_version(
                plugin_name)
        plugin_url = self.proxy.repository.plugin_url(plugin_name,
                latest_version)

        data = urllib.urlopen('%s%s' % (self.server_url, plugin_url)).read()
        local_path = output_dir.joinpath(path(plugin_url).name)
        if not local_path.isfile():
            local_path.write_bytes(data)
            print 'Saved latest %s to %s' % (plugin_name, local_path)
        else:
            print 'File %s already exists - skipping download' % (local_path)


