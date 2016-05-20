from flatland import Form, Float
from flatland.validation import ValueAtLeast
from pygtkhelpers.ui.form_view_dialog import create_form_view
from pygtkhelpers.ui.views.select import ListSelect
import gtk
import pandas as pd
import pygtkhelpers.ui.extra_widgets  # Include widget for `Float` form fields


def get_channel_sweep_parameters(voltage=100, frequency=10e3, channels=None,
                                 parent=None):
    '''
    Show dialog to select parameters for a sweep across a selected set of
    channels.

    Args
    ----

        voltage (int) : Default actuation voltage.
        frequency (int) : Default actuation frequency.
        channels (pandas.Series) : Default channels selection, encoded as
            boolean array indexed by channel number, where `True` values
            indicate selected channel(s).
        parent (gtk.Window) : If not `None`, parent window for dialog.  For
            example, display dialog at position relative to the parent window.

    Returns
    -------

        (dict) : Values collected from widgets with the following keys:
            `'frequency'`, `voltage'`, and (optionally) `'channels'`.
    '''
    # Create a form view containing widgets to set the waveform attributes
    # (i.e., voltage and frequency).
    form = Form.of(Float.named('voltage')
                   .using(default=voltage,
                          validators=[ValueAtLeast(minimum=0)]),
                   Float.named('frequency')
                   .using(default=frequency,
                          validators=[ValueAtLeast(minimum=1)]))
    form_view = create_form_view(form)

    # If default channel selection was provided, create a treeview with one row
    # per channel, and a checkbox in each row to mark the selection status of
    # the corresponding channel.
    if channels is not None:
        df_channel_select = pd.DataFrame(channels.index, columns=['channel'])
        df_channel_select.insert(1, 'select', channels.values)
        view_channels = ListSelect(df_channel_select)

    # Create dialog window.
    dialog = gtk.Dialog(title='Channel sweep parameters',
                        buttons=(gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

    # Add waveform widgets to dialog window.
    frame_waveform = gtk.Frame('Waveform properties')
    frame_waveform.add(form_view.widget)
    dialog.vbox.pack_start(child=frame_waveform, expand=False, fill=False,
                           padding=5)

    # Add channel selection widgets to dialog window.
    if channels is not None:
        frame_channels = gtk.Frame('Select channels to sweep')
        frame_channels.add(view_channels.widget)
        dialog.vbox.pack_start(child=frame_channels, expand=True, fill=True,
                               padding=5)

    # Mark all widgets as visible.
    dialog.vbox.show_all()

    if parent is not None:
        dialog.window.set_transient_for(parent)

    response = dialog.run()
    dialog.destroy()

    if response != gtk.RESPONSE_OK:
        raise RuntimeError('Dialog cancelled.')

    # Collection waveform and channel selection values from dialog.
    form_values = {name: f.element.value
                   for name, f in form_view.form.fields.items()}

    if channels is not None:
        form_values['channels'] = (df_channel_select
                                   .loc[df_channel_select['select'],
                                        'channel'].values)

    return form_values
