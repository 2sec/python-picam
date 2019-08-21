#!/usr/bin/python
# -*- coding: utf-8 -*-


import time
import sensor
import keypad
import SSD1306
import picam
import Log
import utils


config = picam.CamConfig()
config.Run()


#ArmingKeypad = keypad.ArmingKeypadWithDisplay(config)
#ArmingKeypad.Run()

dht22 = sensor.DHT22(config)
dht22.log = True
#dht22.wait_time = 10
dht22.Run()

bme = sensor.BME280(config)
bme.log = True
bme.Run()

hall = sensor.Hall(config)
hall.log = True
hall.Run()

ds18 = sensor.DS18B20(config)
ds18.log = True
ds18.Run()

display =  SSD1306.Display()

Log.Write('starting..')

while True: 
    time.sleep(0.1)

    display.Clear()
    #dt = utils.ShortDateTime()
    #display.PutLine(dt)
    display.PutLine(str(dht22))
    display.PutLine(str(bme))
    display.PutLine(str(ds18))

    display.Display()



