#!/usr/bin/python
# -*- coding: utf-8 -*-


import utils

import Log


import time
import errno
import socket
import threading
import urlparse
import random
import socket
from datetime import datetime
import psutil
import os

from fps import FPS


import picamera



import numpy as np
import cv2
import collections

import Adafruit_DHT
import SSD1306


# super slow to load
import dropbox



import Queue


# Helper class. Called Listener as it listened only initially
# Listen on a specified port, and when a connection is made, call the serve() function
# OR connect to the given address, and when a connection is made, call the serve() function
# when the connection is lost the class tries to re-establish it (by listening or connecting again)
class Listener(object):
    def __init__(self, port = None, host = None):
        self.port = port
        self.host = host

        self.hostName = utils.GetHostName()

        self.Name = '%s-%s' % (self.hostName.lower(), self.__class__.__name__.lower())

    def serve(self, connection, param):
        raise(ValueError('undefined function'))

    def listen(self):
        self._listen(self.serve, name = 'serve')        

    def _listen(self, handler, backlog = 1, port = None, name = None, param = None):
        if port is None: port = self.port

        sock = utils.socket_create(reuse = True)

        sock.bind(('', port))

        sock.listen(backlog)
        
        while True:
            Log.Write('waiting on %u' % port)

            try:
                connection, addr = sock.accept()
                connection.settimeout(5)

                Log.Write('connected to %s' % str(addr))        

                def thread():
                    try:
                        handler(connection, param)
                    except (IOError, OSError) as e:
                        Log.Write('IO error %s' % str(e))
                    finally:
                        Log.Write('closing %s' % str(addr))
                        connection.close()

                if name is None: name = 'listen-handler'

                utils.StartThread(thread, self.Name+':'+name, restart = False, exitOnException = False)

            except:
                Log.Log_Exception()
                utils.Exit()
                    
        sock.close()


    def connect(self, param = None, restart = True):
        self._connect((self.host, self.port), self.serve, param = param, restart = restart)

    def _connect(self, addr, handler, sleepTimeAfterError = 10, param = None, restart = True):
        while True:
            connection = utils.socket_create()
            connection.settimeout(5)

            try:
                Log.Write('connecting to %s' % str(addr))

                connection.connect(addr)

                Log.Write('connected to %s' % str(addr))

                handler(connection, param)

                if not restart:
                    return

            except (IOError, OSError) as e:
                Log.Write('IO error %s' % str(e))

                if not restart:
                    return

                if e.errno == errno.EPIPE:
                    continue

            finally:
                Log.Write('closing')
                connection.close()
            
            time.sleep(sleepTimeAfterError)


        

        

# a sensor is device whose purpose is to detect changes in its environment, and if 'armed', send alarms and records those changes
# in this implementation the sensor value is read (continously and indefinitely) in another thread (by the poll function)
# this class also listens on a specified port (or connects to an external address) and continuously send the data it reads from the sensor over the connection
# the sensor can be 'armed' or 'disarmed' remotely with the appropriate commands


class Sensor(Listener):
    def __init__(self, config, port, url, host = None):
        super(Sensor, self).__init__(port, host)

        self.config = config
        self.url = url

        self.dataReadyEvent = threading.Event()
        self.log = True
        self.data = None

        self.contentType = 'text'

        self.netInfo = None

        self.fps = FPS()
        self.stopWatch = utils.StopWatch()

        self.alarm = False
        self.armed = False

        self.command_port = self.config.command_port
        
        

    def poll(self):
        try:
            self.start()

            while True:
                if self.log:
                    Log.Write('%s reading' % self.Name)

                self.wait()

                if not self.read():
                    continue

                self.fps.Update(len(self.data))

                self.dataReadyEvent.set()

                if self.log:
                    Log.Write('%s read = %s' % (self.Name, str(self)))

        finally:
            self.exit()


    def Run(self, listen = True):
        utils.StartThread(self.poll, self.Name+':sensor-poll')

        if listen:
            if self.host:
                utils.StartThread(self.connect, self.Name+':sensor-connect')
            else:
                utils.StartThread(self.listen, self.Name+':sensor-listen')

        if self.command_port:
            utils.StartThread(self.wait_command, self.Name+':sensor-wait-command')

        self.run()

    def run(self):
        pass


    def armed_status(self):
        return 'armed' if self.armed else 'disarmed'


    def wait_command(self):
        self._listen(self.handle_command, port = self.command_port)

    def handle_command(self, connection, param):

        # get ID from the other end
        id = utils.socket_recv(connection)

        # send own ID
        utils.socket_send(connection, self.Name)

        command = utils.socket_recv(connection)

        Log.Write('received command %s from %s' % (command, id))

        if command == 'arm' and not self.armed:
            self.armed = True
            Log.Write('arming')
        elif command == 'disarm' and self.armed:
            self.armed = False
            Log.Write('disarming')
        elif command == 'status':
            pass

        status = self.armed_status()

        utils.socket_send(connection, '%s' % status)

        Log.Write('command status: %s' % status)



    # call this function to get the latest sensor value returned by the sensor. it might block momentarily if a new value has to be read
    def Read(self):
        self.dataReadyEvent.wait()
        self.dataReadyEvent.clear()
        
        return self.data


    # this is the function that reads the sensor data and which should be redefined
    def read(self):
        return False

    def start(self):
        pass

    def wait(self):
        pass

    def exit(self):
        pass

    # used for displaying debug information
    def __str__(self):
        return str(self.data)


    # this is to avoid brute force attacks or whatever in case someone tries to connect to our server 
    # TODO: use key authentication
    def sleep(self):
        time.sleep(1.0 + 60 * random.random())


    def serve(self, connection, param):

        if self.validateRequest(connection):
            self.sendMultiPartResponse(connection)


    def validateRequest(self, connection):
        request = utils.socket_recv(connection)

        #'GET uri HTTP/1.x' followed by CRLF and other headers
        request = request.split()

        Log.Write(request)

        if len(request) < 3: 
            self.sleep()
            return False

        url = urlparse.urlparse(request[1])
        #query = urlparse.parse_qs(url.query)

        if url.path != self.url:
            self.sleep()
            return False


        return True

        
    def sendMultiPartResponse(self, connection):

        headers = ''\
            'HTTP/1.0 200 OK\r\n' \
            'Server: Microsoft-IIS/6.0\r\n' \
            'Date: %s\r\n' \
            'Connection: close\r\n' \
            'Content-Type: multipart/x-mixed-replace; boundary=image\r\n' \
            '\r\n' % utils.HttpDateTime()
        
        utils.socket_send(connection, headers)

        fps = FPS()

        while True:

            data = self.Read()
            data_size = len(data)
            
            utils.socket_send(connection, '--image\r\nContent-Type: %s\r\nContent-Length: %u\r\n\r\n' % (self.contentType, data_size), True)

            utils.socket_send(connection, data)
            #Log.Write(data[:100])

            # this measures the number of 'frames' sent per seconds over the network but a 'frame' can  be anything actually
            # since the sensor can return anything, not just images
            fps.Update(data_size)

            if self.stopWatch.Elapsed(15):
                self.netInfo = 'net %0.1ffps | avg %0.1fKB | %.01fMbps' % (fps.Value, fps.AverageKB(), fps.BandwidthMbps())

        
        
# humidity and temperature sensor
class DHT22(Sensor):
    def __init__(self, config):
        super(DHT22, self).__init__(config, config.dht22_port, config.dht22_url)
        self.log = False

        self.command_port = 0 # do not listen for commands


    def wait(self):
        time.sleep(60)

    def read(self):
        # TODO verify CPU usage
        data = Adafruit_DHT.read(Adafruit_DHT.DHT22, self.config.dht22_pin)
        if data is None or type(data) != tuple or len(data) != 2 or data[0] is None or data[1] is None:
            return False

        self.alarm = data[1] > self.config.max_relative_humidity or data[0] < self.config.min_temperature_celsius
            
        self.data = data
        return True

    def __str__(self):
        return 'rh %.01f | tc %.01f' % self.data



# this class will output grayscale images from the PI Camera at the specified framerate and resolution
class Camera(Sensor):

    def __init__(self, config, port, url, host):
        super(Camera, self).__init__(config, port, url, host)

        camera = picamera.PiCamera(resolution = config.resolution, framerate = config.framerate)

        camera.iso = config.iso


        self.camera = camera

        self.captureEvent = threading.Event()

        Log.Write('resolution %s - framerate %u' % (str(camera.resolution), camera.framerate))

        self.rawFps = FPS()

        self.frame = None




    def start(self):
        resolution = self.config.real_resolution

        self.camera.hflip = self.config.hflip
        self.camera.vflip = self.config.vflip
        self.camera.rotation = self.config.rotation
        

        w = resolution[0]
        h = resolution[1]
        n = w * h


        class output_to_yuv:

            def write(self, b):
                #copy buffer just in case
                b = b[:]
                #then extract Y (luminance) only
                frame = np.frombuffer(b, dtype=np.uint8, count=n).reshape(h, w)

                send_frame(frame)


        def send_frame(frame):
            self.frame = frame
            self.captureEvent.set()
            self.rawFps.Update(len(frame))





        Log.Write('start_recording')
        self.camera.start_recording(output_to_yuv(), format = 'yuv', resize = resolution)

        self.log = False
        
    def exit(self):
        self.camera.stop_recording()


    def wait(self):
        self.captureEvent.wait()
        self.captureEvent.clear()


    def read(self):
        self.data = self.frame
        return True


    def __str__(self):
        return str(self.data.shape) 






# Monitor the camera to detect movements. Also monitors the temperature/humidity if there a DHT22 sensor
class Monitor(Camera):

    def __init__(self, config):
        super(Monitor, self).__init__(config, config.monitor_port, config.monitor_url, config.monitor_host)

        self.contentType = 'image/jpeg'

        self.dht22 = None
        if config.dht22:
            self.dht22 = DHT22(config)
            self.dht22.Run(listen = False)

        self.ssd1306 = None
        if config.ssd1306:
            self.ssd1306 = SSD1306.Monitor()

        self.cpu = 0
        self.mem = 0

        self.previousFrame = None
        self.contours = []
        self.motionDetected = False
        self.motionTimeInit = self.motionTimeLast = datetime.utcnow()

        self.rawFpsValue = 0
        self.fpsValue = 0

        self.q = collections.deque([], config.framerate * 15) # keep 15 sec 

        self.alarmEvent = threading.Event()
        self.uploadAlarmEvent = threading.Event()

        self.uploads = collections.deque()
        

        self.jpeg = None

        self.gamma_table = None
        self.gamma = 0.0


        self.armed = config.armed


        
        self.alarmDir = './alarms'

        if config.save_alarms:
            utils.StartThread(self.saveAlarms, self.Name+':monitor-save-alarms', restartOnException=True)

        utils.StartThread(self.uploadAlarms, self.Name+':monitor-upload-alarms', restartOnException=True)
        utils.StartThread(self.cleanAlarms, self.Name+':monitor-clean-alarms', restartOnException=True)



    # display misc. data, CPU & mem usage, fps, etc
    def displayStatus(self, frame):

        config = self.config

        log = self.stopWatch.Elapsed(5 * 60)

        # updates values every 10 seconds
        if self.stopWatch.Elapsed(10):
            mem = psutil.virtual_memory()
            self.cpu = psutil.cpu_percent()
            self.mem = 100.0 * (1.0 - 1.0 * mem.available / mem.total)
            self.rawFpsValue = self.rawFps.Value
            self.fpsValue = self.fps.Value

        y = utils.cv2PutText(frame, '%s v%s %s' % (self.Name, config.version, utils.ShortDateTime()), log = log)
        y = utils.cv2PutText(frame, '%ux%u>%ux%u cpu %u%% | mem %u%% | temp %.1f' % (self.camera.resolution[0], self.camera.resolution[1], config.real_resolution[0], config.real_resolution[1], self.cpu, self.mem, utils.CPUTemp), y = y, log = log)
        y = utils.cv2PutText(frame, 'cam/mon/fix %.01f/%.01f/%.01ffps' % (self.rawFpsValue, self.fpsValue, self.camera.framerate), y = y, log = log)

        if self.ssd1306:
            self.ssd1306.PutLine('cpu %u%% | mem %u%%' % (self.cpu, self.mem))


        if self.netInfo:
            y = utils.cv2PutText(frame, self.netInfo, y = y, log = log)

        if self.dht22 and self.dht22.data:
            text = 'rh %.01f | tc %.01f' % self.dht22.data
            y = utils.cv2PutText(frame, text, y = y, log = log)
            if self.ssd1306:
                self.ssd1306.PutLine(text)
                


    def adjust_gamma(self, image):
        gamma = self.config.gamma
        
        if gamma == 1.0: return image

        if self.gamma != gamma:
            self.gamma = gamma
            gamma = 1.0 / gamma
            self.gamma_table = np.array([((i / 255.0) ** gamma) * 255 for i in np.arange(0, 256)]).astype('uint8')

        return cv2.LUT(image, self.gamma_table)


    def process_frame(self, frame):

        config = self.config        
        debug = self.config.debug

        # the frame is already grayscaled
        #frame = np.fromstring(frame, dtype=np.uint8)
        #frame = cv2.imdecode(frame, cv2.CV_LOAD_IMAGE_GRAYSCALE)

        frame = self.adjust_gamma(frame)


        originalFrame = frame
        originalFrameWidth = frame.shape[1]
        originalFrameHeight = frame.shape[0]

        minSize = originalFrameHeight * config.min_object_size / 100

        minSeconds = config.min_seconds_before_triggering_alarm
        minAreaSize = originalFrame.shape[0] * originalFrame.shape[0] * config.min_area_size_before_triggering_alarm / 100


        if True:
            # blur the frame first
            #frame = cv2.adaptiveThreshold(frame, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, (originalFrameWidth // 2) * 2 + 1, 1)

            
            frame = blurredFrame = cv2.blur(frame, (minSize/4+1, minSize/4+1))

            previousFrame = self.previousFrame

            #todo previousFrame -> average of last x mins instead?

            if self.stopWatch.Elapsed(2):
                #if self.previousFrame is None:
                #    self.previousFrame = np.float32(frame)
                self.previousFrame = frame
                     

            if previousFrame is not None:
                # compute the difference between this frame and the reference one

                #cv2.accumulateWeighted(frame, previousFrame, 0.01)
                #previousFrame =  cv2.convertScaleAbs(previousFrame)


                frame = diffFrame = cv2.absdiff(frame, previousFrame)
                
                # for a given pixel, when the difference computed in the previous step is greater than 10, replace it by white (255) otherwise by black
                # so the remaining image is only black and white
                frame = treshFrame = cv2.threshold(frame, 10, 255, cv2.THRESH_BINARY)[1]

                # now try to expand/merge the white areas
                frame = dilatedFrame = cv2.dilate(frame, None, iterations=2)

                if debug:
                    originalFrame = np.concatenate((originalFrame, previousFrame), axis=1)
                    originalFrame = np.concatenate((originalFrame, np.concatenate((blurredFrame, diffFrame), axis=1)), axis=0)
                    originalFrame = np.concatenate((originalFrame, np.concatenate((treshFrame, dilatedFrame), axis=1)), axis=0)

                self.motionDetected = False


                # find contours
                self.contours, _ = cv2.findContours(frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for countour in self.contours:
                    x, y, w, h = cv2.boundingRect(countour)
                    if w > minSize and h > minSize:
                        self.motionDetected = True

                
                now = datetime.utcnow()
                if self.motionDetected :
                    if (now - self.motionTimeLast).total_seconds() > 1:
                        self.motionTimeInit = now

                    self.motionTimeLast = now
                


        status = 'still'
        alarm = False


        if self.motionDetected:

            area_size = 0

            # draw contours
            for countour in self.contours:
                x, y, w, h = cv2.boundingRect(countour)
                if w > minSize and h > minSize:
                    area_size += w * h
                    cv2.rectangle(originalFrame, (x, y), (x+w, y+h), (255, 255, 255), 1)
                    if debug:
                        x += originalFrameWidth
                        y += 2 * originalFrameHeight
                        cv2.rectangle(originalFrame, (x, y), (x+w, y+h), (255, 255, 255), 1)

            # an alarm is triggered if something large enough is moving during a minimum time
            duration = (self.motionTimeLast - self.motionTimeInit).total_seconds()
            status = 'motion'

            if duration > minSeconds and area_size > minAreaSize:
                status = 'alarm'
                alarm = True

            status = '%s | %u second(s) | area size %u' % (status, duration, area_size)



        utils.cv2PutText(originalFrame, Log.os_info, y = originalFrame.shape[0] - 20)
        utils.cv2PutText(originalFrame, 'status: %s/%s' % (self.armed_status(), status), y = originalFrame.shape[0] - 40)


        if self.dht22 and self.dht22.alarm:
            utils.cv2PutText(originalFrame, 'H/T alarm', y = originalFrame.shape[0] - 60)
            alarm = True

        self.alarm = alarm


        return originalFrame



    def saveAlarms(self):
        dir = self.alarmDir
        if not os.path.exists(dir): os.mkdir(dir)

        config = self.config

        while True:
            self.alarmEvent.wait()

            now = datetime.utcnow()
            name = '/%04u-%02u-%02u-%02u-%02u-%02u-%s.avi' % (now.year, now.month, now.day, now.hour, now.minute, now.second, self.Name) 

            filename = dir + name

            #with open(filename, 'wb') as f:
            if True:

                Log.Write('saving to %s' % filename)
                f = cv2.VideoWriter(filename, cv2.cv.CV_FOURCC(*'MJPG') , config.framerate, config.real_resolution, False)

                while True:
                    q = self.q
                    while len(q) > 0:
                        Log.Write('writing')
                        e = q.popleft()
                        f.write(e)

                    if not self.alarmEvent.is_set():
                        break

                    time.sleep(0.5)

                Log.Write('closing %s' % filename)
                f.release()
                    

            self.uploads.append(name)
            self.uploadAlarmEvent.set()
            


    def uploadAlarms(self):

        dbx = dropbox.Dropbox(self.config.dropbox_key)
        Log.Write('dropbox %s' % str(dbx.users_get_current_account()))
        

        while True:
            self.uploadAlarmEvent.wait()
            self.uploadAlarmEvent.clear()

            while len(self.uploads) > 0:
                name = self.uploads.popleft()

                remove = False

                try:
                    if self.config.dropbox_upload:
                        with open(self.alarmDir + name, 'rb') as f:
                            Log.Write('uploading %s...' % name)
                            dbx.files_upload(f.read(), name)
                            remove = True
                except:
                    Log.Log_Exception()
                    Log.Write('file %s NOT uploaded/removed' % name)

                if remove:
                    os.remove(self.alarmDir + name)
                    Log.Write('uploaded %s' % name)


    def cleanAlarms(self):

        dir = self.alarmDir

        dbx = dropbox.Dropbox(self.config.dropbox_key)
        Log.Write('dropbox %s' % str(dbx.users_get_current_account()))
        

        def removeFiles(files, totSize, maxSize, prefix, remove):
            maxSize *= 2**30

            #sort by last modified
            files.sort(key=lambda t: t[1])

            #Log.Write('removeFiles %.02f/%.02gGB' % (totSize / 2**30, maxSize / 2**30))


            if totSize > maxSize:
                Log.Write('cleaning %s %.02fGB > %.02fGB' % (prefix, totSize / 2**30, maxSize / 2**30)  )

                # remove oldest files first
                while totSize > 0.8 * maxSize and len(files) > 0:
                    file = files.pop(0)
                    Log.Write('deleting %s:%s (%.02fMB)' % (prefix, file[0], file[2] / 2**20))
                    remove(file[0])
                    totSize -= file[2]

        while True:

            # local files
            if self.config.max_local_alarms_total_size > 0:
                files = []
                totSize = 0.0
                for file in os.listdir(dir):
                    file = dir + '/' + file
                    date = os.path.getmtime(file)
                    size = os.path.getsize(file)
                    files.append((file, date, size))
                    totSize += size

                removeFiles(files, totSize, self.config.max_local_alarms_total_size, 'loc', os.remove)

            # dropbox files
            if self.config.max_cloud_alarms_total_size > 0:
                files = []
                totSize = 0.0
                for file in dbx.files_list_folder('').entries:
                    files.append((file.path_lower, file.client_modified, file.size))
                    totSize += file.size

                removeFiles(files, totSize, self.config.max_cloud_alarms_total_size, 'dbx', dbx.files_delete)

            time.sleep(60)




    def read(self):
        if not super(Monitor, self).read():
            return False

        if self.ssd1306:
            self.ssd1306.Clear()
            
        frame = self.data

        frame = self.process_frame(frame)
        
        self.displayStatus(frame)

        if self.ssd1306:
            self.ssd1306.Display()

        
        

        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.config.jpeg_quality])

        jpeg = jpeg.tostring()

        # frame cannot be saved back in the self.data (or self.frame) variable as those can be overwritten 
        # anytime between the time this function returns and the time the call to the standard Read() is made
        self.jpeg = jpeg


        self.q.append(frame)


        is_set = self.alarmEvent.is_set()

        if self.alarm and not is_set and self.armed:
            utils.SendMail(self.config, self.config.alarm_recipient, 'alarm from %s' % (self.Name), 'duh', jpeg)
            self.alarmEvent.set()

        if not self.alarm and is_set:
            self.alarmEvent.clear()



        return True


    def Read(self):
        super(Monitor, self).Read()

        return self.jpeg






# connect to the given network address, and return the sensor data

class Reader(Listener):

    def __init__(self, config, addr, url):
        addr = addr.split(':')
        if len(addr) == 1: 
            addr.append(config.default_http_port)
        elif len(addr) == 2:
            addr[1] = int(addr[1])
        else:
            raise(ValueError('Expecting ip_addr_or_host[:port]'))

        super(Reader, self).__init__(addr[1], addr[0])

        self.config = config
        self.url = url

        self.dataReadyEvent = threading.Event()

        self.frame = None
        

    def Run(self):
        utils.StartThread(self.connect, self.Name+':reader-connect')


    def serve(self, connection, param):

        utils.socket_send(connection, 'GET %s HTTP/1.0\r\n' % self.url)


        # 'HTTP/1.0 OK ... Content-Type: multipart/etc\r\n\r\n'
        buffer = utils.socket_recv(connection, 4096)


        buffer_end = buffer.find('\r\n\r\n') + 4
        previous_buffer = buffer[buffer_end:]


        while True:

            if len(previous_buffer) > 128:
                buffer = previous_buffer
            else:
                buffer = previous_buffer + utils.socket_recv(connection, 4096)

            

            previous_buffer = ''

                        
            #Log.Write(buffer[:100])

            # --boundary\r\nContent-Type: ...\r\nContent-Length: XXX\r\n\r\n'

            if not buffer.startswith('--image'):
                Log.Write('Incorrect response')
                Log.Write(buffer[:100])
                break

            len_end = buffer.find('\r\n\r\n') 
            len_begin = buffer.rfind(' ', 0, len_end) + 1

            jpeg_start = len_end + 4
            jpeg_len = int(buffer[len_begin: len_end])




            frame = buffer[jpeg_start:]
            frame_len = len(frame)

            while frame_len < jpeg_len:
                buffer = utils.socket_recv(connection, 4096)

                frame_len += len(buffer)
                frame += buffer


            if frame_len > jpeg_len:

                buffer_len = frame_len - jpeg_len

                previous_buffer = frame[jpeg_len:]
                
                frame = frame[:jpeg_len]
                

            self.frame = frame
            self.dataReadyEvent.set()






class Merger(Sensor):
    def __init__(self, config):
        super(Merger, self).__init__(config, config.merger_port, config.merger_url)

        self.command_port = 0 # do not listen for commands

        arr = []

        for addr in config.merger_sources:
            reader = Reader(config, addr, config.default_url)
            reader.Run()
            arr.append(reader)


        self.readers = arr

        self.log = False

        self.empty_frame = np.zeros((config.real_resolution[1], config.real_resolution[0]))
        utils.cv2PutText(self.empty_frame, 'no connection', 20)

        self.status_row = None

        self.q = None

        self.threads = []


    def run(self):
        if self.config.dispatch_port:
            def dispatch(): self._listen(self.dispatcher, port = self.config.dispatch_port, name = 'dispatcher')
            utils.StartThread(dispatch, self.Name + ':dispatcher')


    def dispatcher(self, connection, param):

        #read ID from the remote sensor
        id = utils.socket_recv(connection)

        # send own ID to the other end
        utils.socket_send(connection, self.Name)

        command = utils.socket_recv(connection)

        Log.Write('received command %s from %s' % (command, id))


        n = 0

        self.q = Queue.Queue()

        for reader in self.readers:
            def send(host = reader.host): 
                self._connect((host, self.config.command_port), self.sender, param = command, restart = False)
            utils.StartThread(send, name = 'sender%u' % n, restart = False)
            n += 1

        Log.Write('%d commands sent' % n)


        while n > 0:
            id, status = self.q.get()
            utils.socket_send(connection, '%s:%s' % (id, status))
            time.sleep(0.5)
            n -= 1

        utils.socket_send(connection, 'end')

        Log.Write('command dispatched')



    def sender(self, connection, param):
        command = param

        id = None

        try:
            # send own ID to the other end and read back its ID
            utils.socket_send(connection, self.Name)
            id = utils.socket_recv(connection)

            Log.Write('sending command %s to %s' % (command, id))

            utils.socket_send(connection, command)
            status = utils.socket_recv(connection)

            Log.Write('received from sensor %s status %s' % (id, status))

            self.q.put((id, status))
        except (IOError, OSError):
            self.q.put((id, 'timeout'))
            raise



        
    def wait(self):
        #make sure it does not go faster than needed
        #print(self.fps.Value)
        if self.fps.Value > self.config.framerate:
            seconds = 1.0 / self.config.framerate
            #Log.Write('sending too fast (%.02f / %u) - sleeping a bit for %.04fs' % (self.fps.Value, self.config.framerate, seconds))
            time.sleep(seconds)






    # todo: cette fonction peut utiliser un coeur à 100% sans arrêt en fait (et peut-être inutilement) -> à améliorer
    def read(self):

        config = self.config        

        num_readers = len(self.readers)

        cols = config.merger_num_columns

        rows = (num_readers + cols - 1) // cols
        cols = min(cols, num_readers)


        if self.status_row is None:
            self.status_row = np.zeros((40, (cols * config.real_resolution[0])))
            

        grid = [None] * rows

        # I used  grid [[xxx] * cols] * rows as an initalizer before but it gave a weird result, as if each row pointed to the same list instance
        # instead of having a different instance per row
        for i in range(rows):
            grid[i] = [self.empty_frame] * cols


        i = 0

        for reader in self.readers:
            frame = reader.frame

            if frame is not None:
                if type(frame) == str:
                    frame = np.fromstring(frame, np.uint8)
                    frame = cv2.imdecode(frame, cv2.CV_LOAD_IMAGE_GRAYSCALE)

                if frame is not None:
                    reader.frame = frame
                    grid[i / cols][i % cols] = frame

            i += 1

        

        frame = None
        for i in range(rows):
            cols = np.concatenate(grid[i], axis=1)
            if frame is None: 
                frame = cols
            else:
                frame = np.concatenate((frame, cols))


        frame = np.concatenate((frame, self.status_row))


        if self.stopWatch.Elapsed(15):
            fps = self.fps
            self.netInfo = 'net %0.1ffps | avg %0.1fKB | %.01fMbps' % (fps.Value, fps.AverageKB(), fps.BandwidthMbps())

        utils.cv2PutText(frame, self.netInfo, y = frame.shape[0] - 20)

        _, frame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality])

        self.data = frame

        #print((t2-t1).total_seconds())

        return True
            
