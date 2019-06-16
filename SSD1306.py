#!/usr/bin/python
# -*- coding: utf-8 -*-

# SSD1306-based 128x64 OLED display

import utils

import Adafruit_SSD1306

import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw


class Display(object):


    def __init__(self):
    
        # (GND, VCC, SCL, SDA) connected to (GND, 3v3 , SCL 3, SDA 2)
        display = self.display = Adafruit_SSD1306.SSD1306_128_64(rst = None)
        display.begin()
        display.clear()
        display.display()

        #self.font = PIL.ImageFont.load_default()
        self.numberOfLines = 3
        self.numberOfChars = 10

        self.fontSize = 14
        self.lineHeight = 16
        self.font = PIL.ImageFont.truetype('cour.ttf', size = self.fontSize)

        self.image = PIL.Image.new('1', (display.width, display.height))
        self.draw = PIL.ImageDraw.Draw(self.image)

        self.stopWatch = utils.StopWatch()

        self.render = False
        self.top = 0
        self.left = 0

    
    def Clear(self, forceRendering = False):
        self.render = forceRendering or self.stopWatch.Elapsed(1)
        if self.render:
            self.top = 0
            self.draw.rectangle((0, 0, self.display.width, self.display.height), outline = 0, fill =0)


    def PutLine(self, text):
        if self.render:
            self.draw.text((0, self.top), text, font = self.font, fill = 255)
            self.top += self.lineHeight
            self.left = 0

    def PutChars(self, text):
        if self.render:
            self.draw.text((self.left, self.top), text, font = self.font, fill = 255)
            self.left += self.draw.textsize(text, font = self.font)[0]


    def Display(self):
        if self.render:
            self.display.image(self.image)
            self.display.display()


