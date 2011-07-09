import numpy as np

class DmfDevice():
    def __init__(self):
        self.electrodes = {}

    def clear(self):
        self.electrodes = {}
        Electrode.next_id = 0
    
    def add_electrode_path(self, path):
        e = Electrode(path)
        self.electrodes[e.id] = e
        return e.id

    def add_electrode_rect(self, x, y, width, height=None):
        if height is None:
            height = width
        path = []
        path.append({'command':'M','x':x,'y':y})
        path.append({'command':'L','x':x+width,'y':y})
        path.append({'command':'L','x':x+width,'y':y+height})
        path.append({'command':'L','x':x,'y':y+height})
        path.append({'command':'Z'})
        return self.add_electrode_path(path)
    
    def connect(self, id, channel):
        if self.electrodes[id].channels.count(channel):
            pass
        else:
            self.electrodes[id].channels.append(channel)

    def disconnect(self, id, channel):
        if self.electrodes[id].channels.count(channel):
            self.electrodes[id].channels.remove(channel)
        
class Electrode:
    next_id = 0
    def __init__(self, path):
        self.id = Electrode.next_id
        Electrode.next_id += 1
        self.path = path
        self.state = 0
        self.channels = []
        self.x_min = np.Inf
        self.y_min = np.Inf
        self.x_max = 0
        self.y_max = 0
        for step in path:
            if step.has_key('x') and step.has_key('y'):
                if float(step['x'])<self.x_min:
                    self.x_min = float(step['x'])
                if float(step['x'])>self.x_max:
                    self.x_max = float(step['x'])
                if float(step['y'])<self.y_min:
                    self.y_min = float(step['y'])
                if float(step['y'])>self.y_max:
                    self.y_max = float(step['y'])

    def contains(self, x, y):
        if self.x_min < x < self.x_max and self.y_min < y < self.y_max:
            return True
        else:
            return False