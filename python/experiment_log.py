import time, os, pickle
from utility import is_int
from matplotlib import pyplot as plt

def load(filename):
    f = open(filename,"rb")
    log = pickle.load(f)
    f.close()
    return log

class ExperimentLog():
    def __init__(self):
        self.directory = "logs"
        self.experiment_id = None
        self.data = []

    def set_dir(self, dir):
        self.directory = dir
        self.experiment_id = None

    def get_id(self):
        if self.experiment_id is None:
            if(os.path.isdir(self.directory)==False):
                os.mkdir(self.directory)
            logs = os.listdir(self.directory)
            self.experiment_id = 0
            for i in logs:
                if is_int(i):
                    if int(i) >= self.experiment_id:
                        self.experiment_id = int(i) + 1
        return self.experiment_id 

    def get_path(self):
        log_path = os.path.join(self.directory,str(self.get_id()))
        if(os.path.isdir(log_path)==False):
            os.mkdir(log_path)
        return log_path
        
    def add_data(self, data):
        data["time"] = time.time()
        self.data.append(data)
        
    def save(self):
        log_path = self.get_path()
        output = open(os.path.join(log_path,"data"), 'wb')
        pickle.dump(self, output, -1)
        output.close()

    def plot(self):
        # plot the impedance
        for i in self.data:
            plt.plot(i["impedance"][0::2])
        plt.show()

    def clear(self):
        # reset the log data
        self.experiment_id = None
        self.data = []