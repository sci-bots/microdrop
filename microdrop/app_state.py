from collections import namedtuple

# Import state machine package
import opencv.statepy.state as state


CANCEL = state.declareEventType('on_cancel')

LOAD_DEVICE = state.declareEventType('on_load_device')
IMPORT_DEVICE = state.declareEventType('on_import_device')
DEVICE_CHANGED = state.declareEventType('on_device_changed')
DEVICE_SAVED = state.declareEventType('on_device_saved')

LOAD_PROTOCOL = state.declareEventType('on_load_protocol')
NEW_PROTOCOL = state.declareEventType('on_new_protocol')
PROTOCOL_CHANGED = state.declareEventType('on_protocol_changed')
PROTOCOL_SAVED = state.declareEventType('on_protocol_saved')

END = state.declareEventType('on_end')


class StateWithCallback(state.State):
    def callback(self, event, *args):
        # Call callback function (if there is one)
        if hasattr(self, 'callback'):
            self.callback(*args)


class NoDeviceNoProtocol(StateWithCallback):
    def on_device_load(self, event):
        if not hasattr(event, 'app'):
            return

    def on_device_import(self, event):
        if not hasattr(event, 'app'):
            return

    @staticmethod
    def transitions():
        return {
            LOAD_DEVICE : DeviceNoProtocol, 
            IMPORT_DEVICE : DeviceNoProtocol, 
        }


class DeviceNoProtocol(StateWithCallback):
    def enter(self):
        # Enable device save, etc. in menu
        pass

    @staticmethod
    def transitions():
        return {
            LOAD_PROTOCOL : DeviceProtocol, 
            NEW_PROTOCOL : DeviceProtocol, 
            DEVICE_CHANGED : DirtyDeviceNoProtocol,

            LOAD_DEVICE : DeviceNoProtocol, 
            IMPORT_DEVICE : DeviceNoProtocol, 
        }


class DeviceProtocol(StateWithCallback):
    def enter(self):
        # Enable device save, etc. in menu
        pass

    @staticmethod
    def transitions():
        return {
            LOAD_DEVICE : DeviceNoProtocol, 
            IMPORT_DEVICE : DeviceNoProtocol, 

            LOAD_PROTOCOL : DeviceProtocol, 
            NEW_PROTOCOL : DeviceProtocol, 

            DEVICE_CHANGED : DirtyDeviceProtocol, 
            PROTOCOL_CHANGED : DeviceDirtyProtocol, 
        }


class DeviceDirtyProtocol(StateWithCallback):
    def enter(self):
        # Enable save in the menu
        pass

    @staticmethod
    def transitions():
        return {
            PROTOCOL_SAVED : DeviceProtocol, 
            LOAD_PROTOCOL : DeviceProtocol, 
            NEW_PROTOCOL : DeviceProtocol, 

            LOAD_DEVICE : DeviceNoProtocol, 
            IMPORT_DEVICE : DeviceNoProtocol, 
            DEVICE_CHANGED : DirtyDeviceDirtyProtocol,
        }


class DirtyDeviceNoProtocol(StateWithCallback):
    def enter(self):
        # Enable save device in the menu
        pass

    @staticmethod
    def transitions():
        return {
            LOAD_PROTOCOL : DirtyDeviceProtocol, 
            NEW_PROTOCOL : DirtyDeviceProtocol, 

            LOAD_DEVICE : DeviceNoProtocol, 
            IMPORT_DEVICE : DeviceNoProtocol, 
        }


class DirtyDeviceProtocol(StateWithCallback):
    def enter(self):
        # Enable save device in the menu
        # Enable save protocol in the menu
        pass

    @staticmethod
    def transitions():
        return {
            IMPORT_DEVICE : DeviceNoProtocol, 
            DEVICE_CHANGED : DeviceNoProtocol, 
            DEVICE_SAVED : DeviceProtocol, 

            PROTOCOL_CHANGED : DirtyDeviceDirtyProtocol, 
        }


class DirtyDeviceDirtyProtocol(StateWithCallback):
    def enter(self):
        # Enable save device in the menu
        # Enable save protocol in the menu
        pass

    @staticmethod
    def transitions():
        return {
            IMPORT_DEVICE : DeviceNoProtocol, 
            DEVICE_SAVED : DeviceDirtyProtocol, 
            DEVICE_CHANGED : DirtyDeviceDirtyProtocol, 

            NEW_PROTOCOL : DirtyDeviceProtocol, 
            PROTOCOL_SAVED : DirtyDeviceProtocol, 
            PROTOCOL_CHANGED : DirtyDeviceDirtyProtocol, 
        }


class Canceled(state.State):
    def enter(self):
        if self.on_canceled:
            self.on_canceled()


class Done(state.State):
    pass


class AppState(object):
    def __init__(self, on_pre_event=None, on_post_event=None):
        self.machine = state.Machine()
        self.machine.start(startState=NoDeviceNoProtocol)
        self.on_pre_event = on_pre_event
        self.on_post_event = on_post_event

    @property
    def current_state(self):
        return self.machine.currentState()

    def trigger_event(self, etype, **kwargs):
        if self.machine.currentState() is None:
            return None
        event = state.Event(etype)
        for key, value in kwargs.iteritems():
            setattr(event, key, value)
        if self.on_pre_event:
            self.on_pre_event(self.machine.currentState(), event)
        self.machine.injectEvent(event)
        if self.on_post_event:
            self.on_post_event(self.machine.currentState(), event)
        return event


if __name__ == '__main__':
    with open('app_state.dot', 'wb') as in_file:
        state.Machine.writeStateGraph(fileobj=in_file, startState=NoDeviceNoProtocol)
