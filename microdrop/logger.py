import logging
import logging.handlers

from plugin_manager import emit_signal, ILoggingPlugin


class CustomHandler(logging.Handler):
    def __init__(self):
        # run the regular Handler __init__
        logging.Handler.__init__(self)

    def emit(self, record):
        if record.levelname == 'DEBUG':
            emit_signal('on_debug', [record], interface=ILoggingPlugin)
        elif record.levelname == 'INFO':
            emit_signal('on_info', [record], interface=ILoggingPlugin)
        elif record.levelname == 'WARNING':
            emit_signal('on_warning', [record], interface=ILoggingPlugin)
        elif record.levelname == 'ERROR':
            emit_signal('on_error', [record], interface=ILoggingPlugin)
        elif record.levelname == 'CRITICAL':
            emit_signal('on_critical', [record], interface=ILoggingPlugin)


#logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

logger = logging.getLogger()
