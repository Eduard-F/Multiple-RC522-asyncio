# https://github.com/ondryaso/pi-rc522

import threading
import RPi.GPIO as GPIO
import asyncio
from rc522 import RC522


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
        self.pin_relay1 = 3
        self.pin_relay2 = 4
        
        # GPIO.setup(self.pin_relay1, GPIO.OUT)
        # GPIO.setup(self.pin_relay2, GPIO.OUT)

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
            # await asyncio.sleep(0.01)
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
                    await self.openRelay1()
                    await self.parent.restartRfidLoop()
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
                    await self.openRelay2()
                    await self.parent.restartRfidLoop()
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

    async def openRelay1(self):
        # GPIO.output(self.pin_relay1, 1)
        print('Turn gate clockwise')
        await asyncio.sleep(1)
        # GPIO.output(self.pin_relay1, 0)
        print('Ready for another tag')

    async def openRelay2(self):
        # GPIO.output(self.pin_relay2, 1)
        print('Turn gate anti-clockwise')
        await asyncio.sleep(1)
        # GPIO.output(self.pin_relay2, 0)
        print('Ready for another tag')
