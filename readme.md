# Python multiple RC522 modules with simple relay
## Introduction
Allows multiple RFID-RC522 modules to be connected with each triggering their own relays.
Based on [pi-rc522](https://github.com/ondryaso/pi-rc522/blob/master/) who has nailed the IRQ await that allows for lower cpu usage while waiting for a tag. I only modified the code to allow for multiple reads and not for writing or anything else
## Connecting
Connecting RC522 module to SPI is pretty easy. You can use [this neat website](http://pi.gadgetoid.com/pinout) for reference.

| Board pin name | RPi pin name | Extra info                   |
| -------------- | ------------ | ---------------------------- |
| SDA            | GPIO8, CE0   | MUST BE A SPI PORT (CE0/CE1) |
| SCK            | GPIO11, SCKL | All RC522 share this pin     |
| MOSI           | GPIO10, MOSI | All RC522 share this pin     |
| MISO           | GPIO9, MISO  | All RC522 share this pin     |
| IRQ            | GPIO24       |                              |
| GND            | Ground       |                              |
| RST            | GPIO25       |                              |
| 3.3V           | 3V3          |                              |

## Connecting more RC522

| Board pin name | RPi pin name | Extra info                                            |
| -------------- | ------------ | ----------------------------------------------------- |
| SDA            | GPIO7, CE1   | MUST BE A SPI PORT (CE0/CE1) or create more SPI ports |
| SCK            | GPIO11, SCKL | All RC522 share this pin                              |
| MOSI           | GPIO10, MOSI | All RC522 share this pin                              |
| MISO           | GPIO9, MISO  | All RC522 share this pin                              |
| IRQ            | GPIO??       | Anything, just update rfid_utils.py line 19 +         |
| GND            | Ground       |                                                       |
| RST            | GPIO??       | Anything, just update rfid_utils.py line 19 +         |
| 3.3V           | 3V3          |                                                       |

`pip3 install -r requirements.txt` to install packages
`python3 main.py` to start example