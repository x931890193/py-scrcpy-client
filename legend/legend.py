import time
import cv2


class Legend(object):
    fix_loc = (300, 1000)

    def __init__(self, parent):
        self.parent = parent
        self.client = parent.client

    def run(self):
        while self.parent.running and self.parent.client.alive:
            # TODO
            frame = self.parent.q.get()
            cv2.imwrite("111.png", frame)
            self.client.device.click(*self.fix_loc)
            time.sleep(2)
        self.parent.running = False
