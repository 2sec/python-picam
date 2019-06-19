#!/usr/bin/python
# -*- coding: utf-8 -*-

import utils
import sensor


from pad4pi import rpi_gpio

import time
from datetime import datetime 
import threading

import SSD1306

import Log
import Queue



def createKeypad(keyPressHandler):

  keys= [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
  ]

  # looking at the keypad, the row pins are the 4 left ones, and the col pins the 4 right ones
  keypad = rpi_gpio.KeypadFactory().create_keypad(keypad = keys, row_pins = [25,8,7,1], col_pins = [12,16,20,21])
  keypad.registerKeyPressHandler(keyPressHandler)  

  return keypad



# base class for a keypad that arms/disarms the cameras (beta).
# it connects to a 'dispatcher' and requests it to arm or disarm itself when the correct code is entered
#  the dispatcher then forwards the command to all the surveillance cams (or whatever the devices are) to which it is connected 

class ArmingKeypad(sensor.Listener):

    def __init__(self, config):
        super(ArmingKeypad, self).__init__()

        self.config = config

        self.armed = False

        self.state = self.idle

        self.time = datetime.utcnow()

        self.keypad = None

        self.timeout = None

        self.lock = threading.RLock()


        addr = config.dispatcher_addr.split(':')
        if len(addr) == 1: 
            addr.append(config.dispatch_port)
        elif len(addr) == 2:
            addr[1] = int(addr[1])
        else:
            raise(ValueError('Expecting ip_addr_or_host[:port]'))

        self.dispatcher_addr = (addr[0], addr[1])

        self.command_port = 0 # do not listen for commands


    def Run(self):
        self.armed = False # TODO read status instead

        self.keypad = createKeypad(self.keyPressHandler)

        utils.StartThread(self.timer, 'timer')

        self.changeState(self.ready)

        self.displayStatus()



    def sender(self, connection, param):
        command, onUpdate, onEnd, onError = param
        if onError is None: onError = self.defaultOnError

        # send own ID
        utils.socket_send(connection, self.Name)

        # get ID from the other end
        id = utils.socket_recv(connection)


        try:
            Log.Write('sending command %s to %s' % (command, id))
            utils.socket_send(connection, command)

            while True:
                response = utils.socket_recv(connection)
                Log.Write('response: %s' % response)

                if response == 'end':
                    break

                # 'id:status'
                response = response.split(':')

                onUpdate(*response)

            onEnd()
        except:
            onError()

    def send(self, param):
        def sender(): self._connect(self.dispatcher_addr, self.sender, restart = False, param = param)
        utils.StartThread(sender, restart = False)


    def Arm(self, onArming, onArmed, onError = None):
        self.send(('arm', onArming, onArmed, onError))

    def Status(self, onUpdate, onEnd, onError = None):
        self.send(('status', onUpdate, onEnd, onError))

    def Disarm(self, onDisarming, onDisarmed, onError = None):
        self.send(('disarm', onDisarming, onDisarmed, onError))



    def timer(self):
        while True:
            #print(self.state)
            time.sleep(1)

            diff = int((datetime.utcnow() - self.time).total_seconds())

            if self.timeout is None: continue

            if diff >= self.timeout[0]:
                self.changeState(self.timeout[1])


    def keyPressHandler(self, key):
        key = str(key)
        #print(key)
        with self.lock:
            self.key = key
            self.time = datetime.utcnow()
            self.state(key)


    def changeState(self, state, key = None, *args):
        with self.lock:
            self.state = state
            self.time = datetime.utcnow()
            self.state(key, *args)


    def defaultOnError(self):
        self.timeout = [2, self.ready]
        self.changeState(self.error)


    def idle(self, key):
        if key is None:
            self.timeout = None
            self.signalIdle()
        else: 
            self.changeState(self.ready)

    def ready(self, key):
        if key is None:
            self.timeout = [2, self._timeout]
            self.signalReady()
        elif key == '*':
            self.displayStatus()
        elif key == '#':
            self.changeState(self.enterCode)



    def _timeout(self, key):
        self.timeout = [1, self.idle]
        self.signalTimeout()

    def enterCode(self, key):
        if key is None:
            self.timeout = [3, self._timeout]
            self.code = []
            self.signalEnterCode()
        else:
            self.code.append(key)
            self.signalDigit(key)

            result = self.compareCode(self.config.secret_code)
            if result is None: 
                return
            if result: 
                self.changeState(self.arming if not self.armed else self.disarming)
            else:
                self.changeState(self.wrongCode)


    def compareCode(self, otherCode):
        code = ''.join(self.code)
        if len(code) != len(otherCode):
            return None
        if code == otherCode:
            return True
        return False



    def wrongCode(self, key):
        if key is None:
            self.timeout = [2, self.ready]
            self.signalWrongCode()


    def error(self, key):
        if key is None:
            self.timeout = [2, self.ready]
            self.signalError()


    def arming(self, key):
        if key is None:
            self.timeout = [10, self.error]
            def f(*args): self.changeState(self._armed, key, *args)
            self.Arm(self.signalStatus, f)

        #if key == 'C':
        #    self.changeState(self.cancelArming)


    def disarming(self, key):
        if key is None:
            self.timeout = [10, self.error]
            def f(*args): self.changeState(self._disarmed, key, *args)
            self.Disarm(self.signalStatus, f)

        #if key == 'C':
        #    self.changeState(self.cancelArming)


    def armedStatus(self):
        return 'armed' if self.armed else 'disarmed'


    def _armed(self, key, *args):
        if key is None:
            self.armed = True
            self.timeout = [2, self.idle]
            self.signalStatus('system', 'armed')


    def _disarmed(self, key, *args):
        if key is None:
            self.armed = False
            self.timeout = [2, self.idle]
            self.signalStatus('system', 'disarmed')

    #def cancelArming(self, key):
    #    if key is None:
    #        self.timeout = [5, self.idle]
    #        self.signalCancel()
    #        self.armHandler.Cancel()



    def signalIdle(self):
        pass

    def signalError(self):
        pass
        
    def signalReady(self):
        pass

    def signalTimeout(self):
        pass

    def displayStatus(self):
        pass
        
    def signalEnterCode(self):
        pass

    def signalDigit(self, key):
        pass

    def signalStatus(self, id, status):
        pass

    def signalCancel(self):
        pass

    def signalWrongCode(self):
        pass






#class ArmingKeypadWithSpeaker(ArmingKeypad): TODO

class ArmingKeypadWithDisplay(ArmingKeypad):

    def __init__(self, config):
        self.display = SSD1306.Display()
        self.putLine('Loading')

        super(ArmingKeypadWithDisplay, self).__init__(config)


    def putLine(self, line):
        self.display.Clear(True)
        self.display.PutLine(line)
        self.display.Display()

    def putChars(self, chars):
        self.display.PutChars(chars)
        self.display.Display()



    def signalIdle(self):
        self.putLine('')

    def signalError(self):
        self.putLine('Error\nPlease try again')

    def signalReady(self):
        self.putLine('Ready')

    def signalTimeout(self):
        self.putLine('Turning off')

    def signalEnterCode(self):
        self.putLine('Enter code')

    def signalDigit(self, key):
        self.putChars('*')

    def signalStatus(self, id, status):
        self.putLine('%s\n%s' % (id, status))

    def signalCancel(self):
        self.putLine('Cancelled')

    def signalWrongCode(self):
        self.putLine('Wrong code')


    def displayStatus(self):
        dateTime = datetime.utcnow()
        status = '%04u-%02u-%02u\n%02u:%02u GMT\n%s' % (dateTime.year, dateTime.month, dateTime.day, dateTime.hour, dateTime.minute, self.armedStatus()) 
        self.putLine(status)


