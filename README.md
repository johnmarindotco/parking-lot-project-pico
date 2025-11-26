# minilab3-customer-service

This is part of an in class minilab project that requirs the use of a Raspberry Pi Pico Pinout.

It highlights the use of object oriented programming with Python.

The scope of this project is to create a "customer service" system" that demonstrates the importance of state handling.

A sensor can be tripped and after a count of bad reviews, logged via a button press, it will alert the manager via the buzzer component if there are too many bad reviews.

An LCD screen displays the message to the customer and alerts the manager along with a light component that will change based on review count, from green to red.

# PicoLibrary

A collection of classes around the Raspberry Pi Pico Hardware interface to make it easy to 
work with Lights (LEDs, RGB LEDs), Sound (active and passive buzzers), Displays (Dot matrix 
with Max7219, 7 segment displays bare and with TM 1637, 160x LCD modules with I2C backpacks
and without I2C, as well as OLED/LCD displays with I2C).

You can check out the YouTube Channel (https://youtube.com/@designwithpico) that covers many
of these classes, including an ongoing Tutorial series.

Also includes simple support for buttons and a basic implementation of a state model for
creating simple state machines.

Currently supported hardware - (more to be added)

* Buttons - both pulled-down and pulled-up buttons supported
* Buzzers - both active and passive buzzers supported
* LEDs - Basic LEDs (on/off) and Dimmable LEDs (setting brightness level)
* Composite lights - TrafficLight (red, yellow, green), Pixel (R, G, B) and NeoPixel (PIO)
* Displays - 160x displays (both I2C as well has GPIO)
* Displays - OLED displays (SSD1306 driver)
* LCD Displays - Currently ST7789 only supported
* Displays - 7 segment displays (both sda/scl controlled as well as bit-banged using PIO)
* LED matrix displays - (MAX7219 driver)
* Sensors - both ditigal (0/1) as well as Analog (ADC 16 bit) sensors
* Specialized Sensors - Ultrasonic Sensor, Temp sensor, DHT11/DHT12 temp/hum sensor and Tilt sensor
* I2S audio boards - currently only output supported via SoundPlayer, but input (microphone) coming soon.

Contact Dr. Sengupta if you need support for any other hardware
