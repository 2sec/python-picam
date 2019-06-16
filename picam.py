#!/usr/bin/python
# -*- coding: utf-8 -*-


import utils
import time
from config import Config
import sensor
import keypad


       
class CamConfig(Config):

    def init(self):
        super(CamConfig, self).init()

        self.getvalue('debug', False)

        self.getvalue('default_url', '/change_url')
        self.getvalue('default_http_port', 8080)


        
        self.getvalue('framerate', 15)
        self.getvalue('resolution', (1640, 1232))
        self.getvalue('resize', 4) # effective resolution becomes (resolution / resize)

        resolution = (self.resolution[0] / self.resize, self.resolution[1] / self.resize)
        resolution = (((resolution[0] + 31) // 32) * 32, ((resolution[1] + 15) // 16) * 16)

        self.getvalue('real_resolution', resolution)

        

        self.getvalue('hflip', True)
        self.getvalue('vflip', True)
        self.getvalue('rotation', 0)

        self.getvalue('iso', 0)


        self.getvalue('alarm_recipient', '')

        self.getvalue('monitor', True)
        self.getvalue('monitor_port', self.default_http_port)
        self.getvalue('monitor_url', self.default_url)
        self.getvalue('monitor_host', '')

        self.getvalue('min_object_size', 10) # % of vertical resolution. minimum height or width of a object
        self.getvalue('min_seconds_before_triggering_alarm', 5)
        self.getvalue('min_area_size_before_triggering_alarm', 10) # % of vertical resolution^2
        
        self.getvalue('jpeg_quality', 60)


        self.getvalue('dht22', False)
        self.getvalue('dht22_port', 6622)
        self.getvalue('dht22_url', self.default_url)
        self.getvalue('dht22_pin', 2)

        self.getvalue('min_temperature_celsius', 10)
        self.getvalue('max_relative_humidity', 80)



        self.getvalue('merge_multiple_sources', False)
        self.getvalue('merger_sources', [''])
        self.getvalue('merger_port', 8100)
        self.getvalue('merger_url', self.default_url)
        self.getvalue('merger_num_columns', 3)

        self.getvalue('armed', False)


        config.getvalue('smtp_server', 'smtp.gmail.com')
        config.getvalue('smtp_port', '465')
        config.getvalue('smtp_username', '')
        config.getvalue('smtp_password', '')

        # https://www.dropbox.com/developers/apps -> Create app (DropBox API, App folder, Name your app) -> then Generate Access Token
        config.getvalue('dropbox_key', '')  

        config.getvalue('dropbox_upload', True)
        config.getvalue('save_alarms', True)

        config.getvalue('gamma', 2.0)

        config.getvalue('command_port', 8101)
        config.getvalue('dispatch_port', 8102)
        config.getvalue('dispatcher_addr', '')
        
        




        config.getvalue('max_local_alarms_total_size', 5.0) # in GB. 0 means no cleaning
        config.getvalue('max_cloud_alarms_total_size', 1.0) # in GB. 0 means no cleaning

        config.getvalue('sendmail', True)

        config.getvalue('ssd1306', False)

        config.getvalue('keypad', False)
        config.getvalue('secret_code', '0')
        
        config.getvalue('version', '0.93b')






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
