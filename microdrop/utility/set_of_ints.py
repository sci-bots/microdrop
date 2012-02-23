import re

class SetOfInts(set):
    def __init__(self, data=[]):
        if isinstance(data, str):
            str_list = data.split(",")
            data = []
            for i in str_list:
                m = re.match('\s*(-{,1}\d+)\s*-\s*(-{,1}\d+)\s*', i)
                if m:
                    min_value = self._validate(m.group(1))
                    max_value = self._validate(m.group(2))
                    if min_value>=max_value:
                        raise ValueError, ("Ranges must be declared in "
                        "increasing order (i.e., '%d-%d' instead of '%d-%d'" %
                        (max_value, min_value, min_value, max_value))
                    data.extend(range(min_value,max_value+1))            
                else:
                    data.append(self._validate(i))
        elif isinstance(data, list):
            # convert all members to integers
            for i in range(len(data)):
                data[i] = self._validate(data[i])
        elif isinstance(data, SetOfInts):
            pass
        else:
            raise TypeError
        set.__init__(self, data)

    def __str__(self):
        str_list = []
        last_val = None
        in_range = False
        for i in self:
            # first element
            if last_val is None:
                str_list.append(str(i))
                last_val = i
                continue
            if i==last_val+1:
                if in_range:
                    pass
                else:
                    in_range = True
            else:
                if in_range:
                    str_list[-1] += "-%d" % last_val
                    in_range = False
                str_list.append(str(i))
            last_val = i
        if in_range:
            str_list[-1] += "-%d" % last_val

        return ", ".join(str_list) 

    def _validate(self, value):
        value = int(value)
        return value
        
    def add(self, value):
        set.add(self, self._validate(value))
        
    def remove(self, value):
        set.remove(self, self._validate(value))
        
    def update(self, value):
        soi = SetOfInts(value)
        set.update(self, soi)
        
    def union(self, value):
        soi = SetOfInts(value)
        set.union(self, soi)