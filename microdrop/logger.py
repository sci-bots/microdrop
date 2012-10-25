import logging
import logging.handlers
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from plugin_manager import ILoggingPlugin
import plugin_manager

class CustomHandler(logging.Handler):
    def __init__(self):
        # run the regular Handler __init__
        logging.Handler.__init__(self)

    def emit(self, record):
        if record.levelname == 'DEBUG':
            plugin_manager.emit_signal('on_debug', [record], interface=ILoggingPlugin)
        elif record.levelname == 'INFO':
            plugin_manager.emit_signal('on_info', [record], interface=ILoggingPlugin)
        elif record.levelname == 'WARNING':
            plugin_manager.emit_signal('on_warning', [record], interface=ILoggingPlugin)
        elif record.levelname == 'ERROR':
            plugin_manager.emit_signal('on_error', [record], interface=ILoggingPlugin)
        elif record.levelname == 'CRITICAL':
            plugin_manager.emit_signal('on_critical', [record], interface=ILoggingPlugin)

#logging.basicConfig(format='[%(levelname)s-%(threadName)10s]: %(message)s', level=DEBUG)
logging.basicConfig(format='[%(levelname)s]: %(message)s', level=INFO)

logger = logging.getLogger()
