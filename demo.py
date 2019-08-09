#!/usr/bin/python
# -*- coding: utf-8 -*-


import time
import sensor
import keypad
import SSD1306
import picam
import Log


config = picam.CamConfig()
config.Run()


#ArmingKeypad = keypad.ArmingKeypadWithDisplay(config)
#ArmingKeypad.Run()

dht22 = sensor.DHT22(config)
dht22.log = True
#dht22.wait_time = 10
dht22.Run()

hall = sensor.Hall(config)
hall.Run()

display =  SSD1306.Display()

Log.Write('starting..')

tc = rh = mag = 0


while True: 
    time.sleep(1)

    if dht22.data:
        data = dht22.data
        tc = data[0]
        rh = data[1]

    mag = hall.data
    
    display.Clear()
    display.PutLine('%.02f%c' % (rh, chr(176)))
    display.PutLine('%.02f%%' % tc)
    display.PutLine('%s' % str(mag))
    display.Display()



