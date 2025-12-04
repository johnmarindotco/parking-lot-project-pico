import time
time.sleep(0.1) # Wait for USB to become ready

print("Hello, Pi Pico!")

from ParkingLotController import *

f = ParkingLotController()
f.run()