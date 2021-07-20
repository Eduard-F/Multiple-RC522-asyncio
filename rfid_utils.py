# https://github.com/ondryaso/pi-rc522

import threading
import RPi.GPIO as GPIO
import asyncio
import datetime

from rc522 import RC522
from db_utils import DB
from models import Employee


class RFID_UTIL():
    irq1 = threading.Event()
    irq2 = threading.Event()

    def __init__(self, parent):
        self.parent = parent  # Allows us to restart the rfid loop and do other stuff above

        # Initialize multiple rc522 readers that use a unique IRQ Callback function to lower cpu usage
        # See rc522.py to know which params to pass
        self.reader1 = RC522(self.irq_callback1, 8, 24, 25, 0)
        self.reader2 = RC522(self.irq_callback2, 7, 1, 0, 1)
        
        # Relay GPIO pins to open/close/turn gates
        self.pin_relay1 = 2
        self.pin_relay2 = 3
        self.pin_buzzer = 21
        GPIO.setup(self.pin_relay1, GPIO.OUT)
        GPIO.setup(self.pin_relay2, GPIO.OUT)
        GPIO.setup(self.pin_buzzer, GPIO.OUT)
        GPIO.output(self.pin_relay1, 1)
        GPIO.output(self.pin_relay2, 1)
        GPIO.output(self.pin_buzzer, 0)


        # EOT GPIO pins to notify end of transactions
        self.pin_eot1 = 17
        self.pin_eot2 = 27
        GPIO.setup(self.pin_eot1, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.pin_eot2, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def irq_callback1(self, pin):
        '''
            If a tag gets detected, it will trigger here first and then break the
            while loop "not self.irq1.wait(0.1)" inside "waiting_for_tag"
        '''
        self.irq1.set()

    def irq_callback2(self, pin):
        self.irq2.set()

    async def wait_for_tag(self):
        '''
            enable IRQ on detect
        '''
        self.reader1.init()
        self.irq1.clear()
        self.reader1.dev_write(0x04, 0x00)
        self.reader1.dev_write(0x02, 0xA0)

        self.reader2.init()
        self.irq2.clear()
        self.reader2.dev_write(0x04, 0x00)
        self.reader2.dev_write(0x02, 0xA0)

        # wait for it
        waiting1 = True
        waiting2 = True
        while waiting1 and waiting2:
            # asyncio.sleep helps with responsiveness if you have a UI loop running or other modules
            await asyncio.sleep(0.01)
            self.reader1.dev_write(0x09, 0x26)
            self.reader1.dev_write(0x01, 0x0C)
            self.reader1.dev_write(0x0D, 0x87)

            self.reader2.dev_write(0x09, 0x26)
            self.reader2.dev_write(0x01, 0x0C)
            self.reader2.dev_write(0x0D, 0x87)
            waiting1 = not self.irq1.wait(0.1)
            waiting2 = not self.irq2.wait(0.1)
        
        if not waiting1:
            # rfid 1 detected a tag
            self.irq1.clear()
            self.reader1.init()
            (error, tag_type) = self.reader1.request()
            if not error:
                (error, uid) = self.reader1.anticoll()
                if not error:
                    print('UID = ' + str(uid))
                    # do authentication
                    await self.checkTag(str(uid), 1)
                else:
                    print('anticoll error')
                    await self.parent.restartRfidLoop()
            else:
                print('request error')
                await self.parent.restartRfidLoop()
        
        if not waiting2:
            # rfid 2 detected a tag
            self.irq2.clear()
            self.reader2.init()
            (error, tag_type) = self.reader2.request()
            if not error:
                (error, uid) = self.reader2.anticoll()
                if not error:
                    print('UID = ' + str(uid))
                    await self.checkTag(str(uid), 2)
                else:
                    print('anticoll error')
                    await self.parent.restartRfidLoop()
            else:
                print('request error')
                await self.parent.restartRfidLoop()

    def cleanup(self):
        """
        Calls stop_crypto() if needed and cleanups GPIO.
        """
        self.irq1.clear()
        self.irq2.clear()
        if self.reader1.authed:
            self.reader1.stop_crypto()
        if self.reader2.authed:
            self.reader2.stop_crypto()
        GPIO.cleanup()

    async def checkTag(self, uid, direction):
        print('checkTag')
        res = DB.getFilterObjects(Employee, f"RfidCode == '{uid}' AND Termdate is NULL")
        if len(res) == 1:
            date = int(datetime.datetime.now().timestamp() * 1000)
            if direction == 1 and res[0]['LogType'] == 4:
                await self.openRelay(direction)
                await self.waitEOT(uid, direction)
            elif direction == 2 and res[0]['LogType'] == 3:
                await self.openRelay(direction)
                await self.waitEOT(uid, direction)
            elif direction == 1 and res[0]['LogType'] == 3:
                print('unauthorized 1')
                await self.failBeep()
                await asyncio.sleep(0.5)
            elif direction == 2 and res[0]['LogType'] == 4:
                print('unauthorized 2')
                await self.failBeep()
                await asyncio.sleep(0.5)
            elif res[0]['LogDateUTC'] + 30000 > date:
                print('unauthorized 3')
                await self.failBeep()
                await asyncio.sleep(0.5)
            else:
                await self.openRelay(direction)
                await self.waitEOT(uid, direction)
        elif len(res) == 0:
            print('unauthorized')
            await self.failBeep()
        await self.parent.restartRfidLoop()

    async def openRelay(self, direction):
        GPIO.output(self.pin_buzzer, 1)
        if direction == 1:
            GPIO.output(self.pin_relay1, 0)
            print('In relay triggered')
            await asyncio.sleep(0.5)
            GPIO.output(self.pin_relay1, 1)
        else:
            GPIO.output(self.pin_relay2, 0)
            print('Out relay triggered')
            await asyncio.sleep(0.5)
            GPIO.output(self.pin_relay2, 1)
        
        GPIO.output(self.pin_buzzer, 0)

    async def waitEOT(self, uid, direction):
        print('waitEOT')
        waiting = True
        count = 0
        while waiting:
            if GPIO.input(self.pin_eot1) == GPIO.HIGH or GPIO.input(self.pin_eot2) == GPIO.HIGH:
                waiting = False
                DB.addClock(uid, direction)
                print('Gate turned successfully')
            count += 1
            # after 10 seconds, gate will close itself and person didn't go through
            if count >= 100:
                waiting = False
                print('Gate closed without turning')
            await asyncio.sleep(0.1)

    async def failBeep(self):
        GPIO.output(self.pin_buzzer, 1)
        await asyncio.sleep(0.2)
        GPIO.output(self.pin_buzzer, 0)
        await asyncio.sleep(0.2)
        GPIO.output(self.pin_buzzer, 1)
        await asyncio.sleep(0.2)
        GPIO.output(self.pin_buzzer, 0)
