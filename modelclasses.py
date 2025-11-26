from LightStrip import *

class FeedbackStats:
    def __init__(self):
        self._positive = 0
        self._negative = 0
        self._lightstrip = LightStrip(pin=17, numleds=8)

    def getPercentage(self):
        total = self._positive + self._negative
        if total == 0:
            return 0.5

        v = self._positive / total
        return v

    def showStats(self):
        numleds = int(8 * self.getPercentage())
        if numleds > 5:
            self._lightstrip.setColor(GREEN, numleds)
        elif numleds > 3:
            self._lightstrip.setColor(YELLOW, numleds)
        else:
            self._lightstrip.setColor(RED, numleds)

    def happy(self):
        self._positive = self._positive + 1
        self.showStats()

    def sad(self):
        self. _negative = self._negative + 1
        self.showStats()