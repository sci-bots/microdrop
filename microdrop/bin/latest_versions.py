from collections import OrderedDict
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO

from application_repository.application.proxy import AppRepository
from application_repository.plugins.proxy import PluginRepository


DEFAULT_SERVER_URL = 'http://microfluidics.utoronto.ca/update'


def get_latest_version_content(server_url=DEFAULT_SERVER_URL):
    app_repo = AppRepository(server_url)

    plugin_repo = PluginRepository(server_url)

    plugin_info = OrderedDict([(p, (plugin_repo.latest_version(p),
                                    plugin_repo.latest_package_url(p)))
                               for p in plugin_repo.available_packages()])

    content = StringIO()

    # # Microdrop application #
    print >> content, '# Microdrop application installer #\n'

    app_info = (app_repo.latest_version('microdrop'),
                app_repo.latest_package_url('microdrop'))
    app_name = 'microdrop'

    print >> content, ' * [`%s` *(%s.%s.%s)*][%s]' % (app_name,
                                                      app_info[0]['major'],
                                                      app_info[0]['minor'],
                                                      app_info[0]['micro'],
                                                      app_name)

    print >> content, '\n[%s]: %s%s' % (app_name, app_repo.server_url,
                                        app_info[1])

    print >> content, ''

    # # Microdrop plugins #
    print >> content, '# Plugins #\n'
    for name, info in plugin_info.iteritems():
        print >> content, ' * [`%s` *(%s.%s.%s)*][%s]' % (name,
                                                          info[0]['major'],
                                                          info[0]['minor'],
                                                          info[0]['micro'],
                                                          name)
    print >> content, ''
    for name, info in plugin_info.iteritems():
        print >> content, '[%s]: %s%s' % (name, plugin_repo.server_url,
                                          info[1])

    return content.getvalue()


if __name__ == '__main__':
    print get_latest_version_content()
