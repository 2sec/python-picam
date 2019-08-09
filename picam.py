#!/usr/bin/python
# -*- coding: utf-8 -*-


import utils
import time
from config import Config
import sensor
import keypad


# this is the main module. 
# when launched, depending on the config, it will start a single surveillance cam (class Monitor), a keypad with a display, (class ArmingKeypadWithDisplay),
# a controller (class Merger) or a combination

       
# this class defines the configuration file and the configuration keys/values and their types

class CamConfig(Config):

    def init(self):
        super(CamConfig, self).init()

        self.getvalue('debug', False)

        # the URL used to access the camera. should be changed to something else and kept 'secret' (as there's no authentication currently and it's in http...)
        self.getvalue('default_url', '/change_url')
        self.getvalue('default_http_port', 8080)

        # lower the framerate if the network bandwith available is too low
        self.getvalue('framerate', 15) 
        self.getvalue('resolution', (1640, 1232))
        self.getvalue('resize', 4) # effective resolution becomes (resolution / resize)

        # round up to the nearest multiples
        # this is needed as we access the camera frame buffer directly
        resolution = (self.resolution[0] / self.resize, self.resolution[1] / self.resize)
        resolution = (((resolution[0] + 31) // 32) * 32, ((resolution[1] + 15) // 16) * 16)

        self.getvalue('real_resolution', resolution)

        

        self.getvalue('hflip', True)
        self.getvalue('vflip', True)
        self.getvalue('rotation', 0)

        self.getvalue('iso', 0)
        self.getvalue('shutter_speed', 0)
        self.getvalue('brightness', 50)
        self.getvalue('exposure_mode', 'auto')
        self.getvalue('contrast', 0)
        self.getvalue('awb_mode', 'auto')
        self.getvalue('awb_gains', (0.0, 0.0))


        self.getvalue('alarm_recipient', '')

        # monitor=True -> Monitor the local camera to detect movements
        self.getvalue('monitor', True)
        self.getvalue('monitor_port', self.default_http_port)
        self.getvalue('monitor_url', self.default_url)
        self.getvalue('monitor_host', '')

        self.getvalue('min_object_size', 10) # % of vertical resolution. minimum height or width of a object
        self.getvalue('min_seconds_before_triggering_alarm', 5)
        self.getvalue('min_area_size_before_triggering_alarm', 10) # % of vertical resolution^2
        
        self.getvalue('jpeg_quality', 60)


        # dht22=True > there's a local DHT22 sensor 
        self.getvalue('dht22', False)
        self.getvalue('dht22_port', 6622)
        self.getvalue('dht22_url', self.default_url)
        self.getvalue('dht22_pin', 2)

        # min temperature below which an alert is sent
        self.getvalue('min_temperature_celsius', 10)
        # max humidity above which an alert is sent
        self.getvalue('max_relative_humidity', 80)

        # Hall effect sensor
        self.getvalue('hall_port', 6623)
        self.getvalue('hall_url', self.default_url)
        self.getvalue('hall_pin', 2)




        # merge_multiple_sources=True -> read remote cameras (in merger_sources: list of comma separated host:port) and merge them into a single image
        self.getvalue('merge_multiple_sources', False)
        self.getvalue('merger_sources', [''])
        # merge_port: port on which the merged image is rendered
        self.getvalue('merger_port', 8100)
        self.getvalue('merger_url', self.default_url)
        #num_colums: number of images per row
        self.getvalue('merger_num_columns', 3)

        self.getvalue('armed', False)


        self.getvalue('smtp_server', 'smtp.gmail.com')
        self.getvalue('smtp_port', '465')
        self.getvalue('smtp_username', '')
        self.getvalue('smtp_password', '')

        # https://www.dropbox.com/developers/apps -> Create app (DropBox API, App folder, Name your app) -> then Generate Access Token
        self.getvalue('dropbox_key', '')  

        self.getvalue('dropbox_upload', True)
        self.getvalue('save_alarms', True)

        self.getvalue('gamma', 1.0)

        self.getvalue('command_port', 8101)
        self.getvalue('dispatch_port', 8102)
        self.getvalue('dispatcher_addr', '')
        
        




        # if the size exceeeds the given values the oldest files will be removed first
        self.getvalue('max_local_alarms_total_size', 5.0) # in GB. 0 means no cleaning
        self.getvalue('max_cloud_alarms_total_size', 1.0) # in GB. 0 means no cleaning

        self.getvalue('sendmail', True)

        # set to True if there's a LED displayed connected to the local machine
        self.getvalue('ssd1306', False)

        self.getvalue('keypad', False)
        self.getvalue('secret_code', '0')
        
        self.getvalue('version', '0.93d')






if __name__ == '__main__':

    config = CamConfig()
    config.Run()

    hostName = utils.GetHostName()

    utils.SendMail(config, config.alarm_recipient, '%s loading' % hostName, 'duh', None)


    if config.monitor:
        sensor.Monitor(config).Run()

    if config.merge_multiple_sources:     
        sensor.Merger(config).Run()

    if config.keypad:
        keypad.ArmingKeypadWithDisplay(config).Run()


    while True: time.sleep(1000)





# history
# 0.91 corrected issue where a reader wouldn't reconnect to its source
# 0.92 implemented cleaning of local and dropbox files
# 0.92b various changes related to exceptions in threads such as dropbox timeouts
# 0.92d videos are now saved as 'avi' files
# 0.92e videos cleaned less frequently by cleaning 20% more when the maximum size is reached
# 0.92g added SSD1306
# 0.92i added ArmingKeypad, gamma
# 2018-08-13 0.92j added a lock when initializing the random generator
# 2018-08-14 0.92h restructed the socket code a bit
# 2019-01-16 0.92k just moved the random seed initialisation at the very beginning.
# this proved not useful at all. rng-tools had to be installed to solve this problem
# 2019-01-25 0.93 reworked the way sensors connect together
# 2019-03-01 0.93b just added CPU temperature
# 2019-07-12 0.93c added various camera settings
# 2019-07-13 0.93d small change for debugging purposes
# 2019-08-09 various changes related to me testing DHT22 sensors. also added Hall sensors

