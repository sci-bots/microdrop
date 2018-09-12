'''
.. versionadded:: X.X.X
'''
import functools as ft
import logging

from asyncio_helpers import sync
from markdown2pango import markdown2pango
from pygtkhelpers.gthreads import gtk_threadsafe
import gtk
import trollius as asyncio

from ...plugin_manager import (PluginGlobals, SingletonPlugin, IPlugin,
                               implements)

logger = logging.getLogger(__name__)


PluginGlobals.push_env('microdrop')


def ignorable_warning(**kwargs):
    '''
    Display warning dialog with checkbox to ignore further warnings.

    Returns
    -------
    dict
        Response with fields:

        - ``ignore``: ignore warning (`bool`).
        - ``always``: treat all similar warnings the same way (`bool`).


    .. versionadded:: X.X.X
    '''
    dialog = gtk.MessageDialog(buttons=gtk.BUTTONS_YES_NO,
                               type=gtk.MESSAGE_WARNING)

    for k, v in kwargs.items():
        setattr(dialog.props, k, v)

    content_area = dialog.get_content_area()
    vbox = content_area.get_children()[0].get_children()[-1]
    check_button = gtk.CheckButton(label='Let me _decide for each warning',
                                   use_underline=True)
    vbox.pack_end(check_button)
    check_button.show()

    dialog.set_default_response(gtk.RESPONSE_YES)

    dialog.props.secondary_use_markup = True
    dialog.props.secondary_text = ('<b>Would you like to ignore and '
                                   'continue?</b>')
    try:
        response = dialog.run()
        return {'ignore': (response == gtk.RESPONSE_YES),
                'always': not check_button.props.active}
    finally:
        dialog.destroy()


class PromptPlugin(SingletonPlugin):
    '''
    Plugin to query for input through prompt GUI dialogs.
    '''
    implements(IPlugin)
    plugin_name = 'microdrop.prompt_plugin'

    def __init__(self):
        self.name = self.plugin_name
        self.ignore_warnings = {}
        gtk.threads_init()

    @asyncio.coroutine
    def on_step_run(self, plugin_kwargs, signals):
        '''
        .. versionadded:: X.X.X

        Handler called whenever a step is executed.

        Parameters
        ----------
        plugin_kwargs : dict
            Plugin settings as JSON serializable dictionary.
        signals : blinker.Namespace
            Signals namespace.
        '''
        @asyncio.coroutine
        def _on_warning(message, key=None, title='Warning'):
            if key is None:
                key = message
            if key in self.ignore_warnings:
                ignore = self.ignore_warnings[key]
            else:
                text = markdown2pango(message)
                response = yield asyncio.From(sync(gtk_threadsafe)
                    (ft.partial(ignorable_warning, title=title, text=text,
                                use_markup=True))())
                ignore = response['ignore']
                if response['always']:
                    self.ignore_warnings[key] = ignore

            if not ignore:
                # Do not ignore warning.
                raise RuntimeWarning(message)

        signals.signal('warning').connect(_on_warning, weak=False)

PluginGlobals.pop_env()
