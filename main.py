import asyncio
import signal
import sys

try:
    from rfid_utils import RFID_UTIL
except:
    from emulated import RFID_UTIL
from db_utils import DB
from app_auth import Issuer


class mainLoop():
    def __init__(self):
        self.rdr = RFID_UTIL(self)
        self.issuer = Issuer()
    
    async def restartRfidLoop(self):
        '''
        Here you can control when the loop needs to restart
        '''
        print('restartRfidLoop')
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
        await asyncio.create_task(main_loop.issuer.run())
        asyncio.create_task(DB.asyncAll())
        await asyncio.create_task(main_loop.rdr.wait_for_tag())
    except Exception as e:
        print(str(e))
        # do GPIO cleanup
        main_loop.end_read()

if __name__ == '__main__':
    asyncio.run(main())

