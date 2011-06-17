class Electrode():
    def __init__(self, x, y, width, height=None):
        self.x = x
        self.y = y
        self.width = width
        if height is None:
            self.height = width
        else:
            self.height = height

    def contains(self, x, y):
        if x>self.scale*self.x and x<self.scale*(self.x+self.width) and \
           y>self.scale*self.y and y<self.scale*(self.y+self.height):
            return True
        else:
            return False
