
from datetime import datetime
import collections

import Log 

class FPS(object):

    def __init__(self):
        self.q = collections.deque()
        self.qSize = 0.0
        self.Frames = 0
        self.Value = 1

    def clear(self):
        pass

    def AverageKB(self):
        return (self.qSize / max(1, len(self.q))) / (2 ** 10)

    def BandwidthMbps(self):

        if len(self.q) < 2: 
            return 0

        duration = (self.q[-1][0] - self.q[0][0]).total_seconds()
        if duration == 0:
            return 0

        return 8 * (self.qSize / duration) / (2 ** 20) 


    def Update(self, size):
        now = datetime.utcnow()

        self.qSize += size

        item = (now, size)
        self.q.append(item)

        self.Frames += 1


        while True:
            item = self.q[0]
            if (now - item[0]).total_seconds() < 10:
                break
            self.qSize -= item[1]
            self.q.popleft()

        value = self.Value = max(1, len(self.q) / 10.0)

        return value
    

