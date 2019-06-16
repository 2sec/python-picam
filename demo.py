import time

import keypad

from config import Config

config = Config()
config.getvalue('secret_code', '14569')

ArmingKeypad = keypad.ArmingKeypadWithDisplay(config)
ArmingKeypad.Run()


while True: time.sleep(1000)

