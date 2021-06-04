import asyncio
import signal
import sys

from rfid_utils import RFID_UTIL


class mainLoop():
    def __init__(self):
        self.rdr = RFID_UTIL(self)
    
    async def restartRfidLoop(self):
        '''
        Here you can control when the loop needs to restart
        '''
        await asyncio.create_task(self.rdr.wait_for_tag())
    
    def end_read(self):
        global run
        print("\nCtrl+C captured, ending read.")
        self.rdr.cleanup()
        sys.exit()

async def main():
    try:
        main_loop = mainLoop()
        
        signal.signal(signal.SIGINT, main_loop.end_read)  # Supposed to fire off when Ctrl+C is pressed :?
        print("Ready for tag")
        await asyncio.create_task(main_loop.rdr.wait_for_tag())
    except:
        # do GPIO cleanup
        main_loop.end_read()

if __name__ == '__main__':
    asyncio.run(main())

