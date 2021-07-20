import time
import random
import math
import threading
import asyncio
import datetime

from models import Employee
from db_utils import DB


class HX711:
    def __init__(self, dout, pd_sck, gain=128):
        self.PD_SCK = pd_sck

        self.DOUT = dout

        # Last time we've been read.
        self.lastReadTime = time.time()
        self.sampleRateHz = 80.0
        self.resetTimeStamp = time.time()
        self.sampleCount = 0
        self.simulateTare = False

        # Mutex for reading from the HX711, in case multiple threads in client
        # software try to access get values from the class at the same time.
        self.readLock = threading.Lock()
        
        self.GAIN = 0
        self.REFERENCE_UNIT_A = 1
        self.REFERENCE_UNIT_B = 1
        
        self.OFFSET_A = 1
        self.OFFSET_B = 1
        self.lastVal = int(0)

        self.DEBUG_PRINTING = True
        
        self.byte_format = 'MSB'
        self.bit_format = 'MSB'

        self.set_gain(gain)




        # Think about whether this is necessary.
        time.sleep(1)

    def convertToTwosComplement24bit(self, inputValue):
       # HX711 has saturating logic.
       if inputValue >= 0x7fffff:
          return 0x7fffff

       # If it's a positive value, just return it, masked with our max value.
       if inputValue >= 0:
          return inputValue & 0x7fffff

       if inputValue < 0:
          # HX711 has saturating logic.
          if inputValue < -0x800000:
             inputValue = -0x800000

          diff = inputValue + 0x800000

          return 0x800000 + diff

        
    def convertFromTwosComplement24bit(self, inputValue):
        return -(inputValue & 0x800000) + (inputValue & 0x7fffff)

    
    def is_ready(self):
        # Calculate how long we should be waiting between samples, given the
        # sample rate.
        sampleDelaySeconds = 1.0 / self.sampleRateHz

        return time.time() >= self.lastReadTime + sampleDelaySeconds

    
    def set_gain(self, gain):
        if gain == 128:
            self.GAIN = 1
        elif gain == 64:
            self.GAIN = 3
        elif gain == 32:
            self.GAIN = 2

        # Read out a set of raw bytes and throw it away.
        self.readRawBytes()

        
    def get_gain(self):
        if self.GAIN == 1:
            return 128
        if self.GAIN == 3:
            return 64
        if self.GAIN == 2:
            return 32

        # Shouldn't get here.
        return 0
        

    def readRawBytes(self):
        # Wait for and get the Read Lock, incase another thread is already
        # driving the virtual HX711 serial interface.
        self.readLock.acquire()

        # Wait until HX711 is ready for us to read a sample.
        while not self.is_ready():
           pass

        self.lastReadTime = time.time()

        # Generate a 24bit 2s complement sample for the virtual HX711.
        rawSample = self.convertToTwosComplement24bit(self.generateFakeSample())
        
        # Read three bytes of data from the HX711.
        firstByte  = (rawSample >> 16) & 0xFF
        secondByte = (rawSample >> 8)  & 0xFF
        thirdByte  = rawSample & 0xFF

        # Release the Read Lock, now that we've finished driving the virtual HX711
        # serial interface.
        self.readLock.release()           

        # Depending on how we're configured, return an orderd list of raw byte
        # values.
        if self.byte_format == 'LSB':
           return [thirdByte, secondByte, firstByte]
        else:
           return [firstByte, secondByte, thirdByte]


    def read_long(self):
        # Get a sample from the HX711 in the form of raw bytes.
        dataBytes = self.readRawBytes()


        # if self.DEBUG_PRINTING:
        #     print(dataBytes,)
        
        # Join the raw bytes into a single 24bit 2s complement value.
        twosComplementValue = ((dataBytes[0] << 16) |
                               (dataBytes[1] << 8)  |
                               dataBytes[2])

        # if self.DEBUG_PRINTING:
        #     print("Twos: 0x%06x" % twosComplementValue)
        
        # Convert from 24bit twos-complement to a signed value.
        signedIntValue = self.convertFromTwosComplement24bit(twosComplementValue)

        # Record the latest sample value we've read.
        self.lastVal = signedIntValue

        # Return the sample value we've read from the HX711.
        return int(signedIntValue)

    
    def read_average(self, times=3):
        # Make sure we've been asked to take a rational amount of samples.
        if times <= 0:
            print("HX711().read_average(): times must >= 1!!  Assuming value of 1.")
            times = 1

        # If we're only average across one value, just read it and return it.
        if times == 1:
            return self.read_long()

        # If we're averaging across a low amount of values, just take an
        # arithmetic mean.
        if times < 5:
            values = int(0)
            for i in range(times):
                values += self.read_long()

            return values / times

        # If we're taking a lot of samples, we'll collect them in a list, remove
        # the outliers, then take the mean of the remaining set.
        valueList = []

        for x in range(times):
            valueList += [self.read_long()]

        valueList.sort()

        # We'll be trimming 20% of outlier samples from top and bottom of collected set.
        trimAmount = int(len(valueList) * 0.2)

        # Trim the edge case values.
        valueList = valueList[trimAmount:-trimAmount]

        # Return the mean of remaining samples.
        return sum(valueList) / len(valueList)


    def get_value_A(self, times=3):
        return self.read_average(times) - self.OFFSET_A


    def get_value_B(self, times=3):
        return self.read_average(times) - self.OFFSET_B


    def get_weight_A(self, times=3):
        value = self.get_value_A(times)
        value = value / self.REFERENCE_UNIT_A
        return value


    def get_weight_B(self, times=3):
        value = self.get_value_B(times)
        value = value / self.REFERENCE_UNIT_B
        return value


    def tare_A(self, times=15):
        # If we aren't simulating Taring because it takes too long, just skip it.
        if not self.simulateTare:
            return 0

        # Backup REFERENCE_UNIT value
        reference_unit = self.REFERENCE_UNIT_A
        self.set_reference_unit_A(1)

        value = self.read_average(times)

        if self.DEBUG_PRINTING:
            print("Tare A value:", value)
        
        self.set_offset_A(value)

        # Restore the reference unit, now that we've got our offset.
        self.set_reference_unit_A(reference_unit)

        return value


    def tare_B(self, times=15):
        # If we aren't simulating Taring because it takes too long, just skip it.
        if not self.simulateTare:
            return 0

        # Backup REFERENCE_UNIT value
        reference_unit = self.REFERENCE_UNIT_B
        self.set_reference_unit_B(1)

        value = self.read_average(times)

        if self.DEBUG_PRINTING:
            print("Tare B value:", value)
        
        self.set_offset_B(value)

        # Restore the reference unit, now that we've got our offset.
        self.set_reference_unit_B(reference_unit)

        return value

    
    def set_reading_format(self, byte_format="LSB", bit_format="MSB"):

        if byte_format == "LSB":
            self.byte_format = byte_format
        elif byte_format == "MSB":
            self.byte_format = byte_format
        else:
            print("Unrecognised byte_format: \"%s\"" % byte_format)

        if bit_format == "LSB":
            self.bit_format = bit_format
        elif bit_format == "MSB":
            self.bit_format = bit_format
        else:
            print("Unrecognised bit_format: \"%s\"" % bit_format)


    def set_offset_A(self, offset):
        self.OFFSET_A = offset


    def set_offset_B(self, offset):
        self.OFFSET_B = offset


    def get_offset_A(self):
        return self.OFFSET_A


    def get_offset_B(self):
        return self.OFFSET_B


    def set_reference_unit_A(self, reference_unit):
        # Make sure we aren't asked to use an invalid reference unit.
        if reference_unit == 0:
            print("HX711().set_reference_unit_A(): Can't use 0 as a reference unit!!")
            return

        self.REFERENCE_UNIT_A = reference_unit


    def set_reference_unit_B(self, reference_unit):
        # Make sure we aren't asked to use an invalid reference unit.
        if reference_unit == 0:
            print("HX711().set_reference_unit_B(): Can't use 0 as a reference unit!!")
            return

        self.REFERENCE_UNIT_B = reference_unit


    def get_reference_unit_A(self):
        return get_reference_unit_A()


    def get_reference_unit_B(self):
        return get_reference_unit_B()


    def power_down(self):
        # Wait for and get the Read Lock, incase another thread is already
        # driving the HX711 serial interface.
        self.readLock.acquire()

        # Wait 100us for the virtual HX711 to power down.
        time.sleep(0.0001)

        # Release the Read Lock, now that we've finished driving the HX711
        # serial interface.
        self.readLock.release()           


    def power_up(self):
        # Wait for and get the Read Lock, incase another thread is already
        # driving the HX711 serial interface.
        self.readLock.acquire()

        # Wait 100 us for the virtual HX711 to power back up.
        time.sleep(0.0001)

        # Release the Read Lock, now that we've finished driving the HX711
        # serial interface.
        self.readLock.release()

        # HX711 will now be defaulted to Channel A with gain of 128.  If this
        # isn't what client software has requested from us, take a sample and
        # throw it away, so that next sample from the HX711 will be from the
        # correct channel/gain.
        if self.get_gain() != 128:
            self.readRawBytes()


    def reset(self):
        # self.power_down()
        # self.power_up()

        # Mark time when we were reset.  We'll use this for sample generation.
        self.resetTimeStamp = time.time()


    def generateFakeSample(self):
        init_val = 80000
        fluctuation = random.randrange(-100,100)
        new_val = 80000 + fluctuation
        
        return new_val
        # return int(sample)


class RFID_UTIL(object):
    def __init__(self, window):
        self.OFFSET = 1
    
    async def wait_for_tag(self):
        while True:
            print('wait_for_tag')
            await asyncio.sleep(1)
    
    async def checkTag(self, uid, direction):
        print('checkTag')
        res = DB.getFilterObjects(Employee, f"RfidCode == '{uid}' AND Termdate is NULL")
        if len(res) == 1:
            date = int(datetime.datetime.now().timestamp() * 1000)
            if res[0]['LogDateUTC'] + 30000 > date:
                print('unauthorized')
            elif direction == 1 and res[0]['LogType'] == 3:
                print('unauthorized')
            elif direction == 2 and res[0]['LogType'] == 4:
                print('unauthorized')
            else:
                # await self.openRelay(direction)
                # await self.waitEOT(uid, direction)
                print('access allowed')
        elif len(res) == 0:
            print('unauthorized')
        await self.parent.restartRfidLoop()

    def request(self):
        # print('request')
        return (False, 'Tag type 1')

    def anticoll(self):
        # print('anticoll')
        return (False, 'uid1')

    def select_tag(self):
        print('select_tag')

    def card_auth(self):
        print('card_auth')

    def auth_a(self):
        print('auth_a')

    def read(self):
        print('read')

    def stop_crypto(self):
        print('stop_crypto')

    def cleanup(self):
        print('cleanup')
    
    async def asyncLoop(self, count=5):
        print('emulatedLoop start')
        await asyncio.sleep(count)
        print('emulatedLoop end')

# EOF - emulated.py
