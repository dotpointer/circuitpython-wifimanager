# CircuitPython WiFi Manager

A WiFi manager for CircuitPython. Opens an access point to allow the user to
configure the device to configure the device to connect to available WiFi
networks. When the device is configured it then connects to the first
available matching network and hands over the control to your code.

Based upon the original version in MicroPython, see the Original MicroPython
version authors section.

## Description

WiFi manager for CircuitPython 8+.

## Compatibility

Tested on WeMos/LOLIN S2 Mini/Adafruit Feather ESP32-S2 with CircuitPython 8.0.2.

Should be compatible with other CircuitPython 8+ devices too, please try it
out to find out.

The device must have CircuitPython WiFi hardware support.

## Main Features

- Brings up an access point with a web based connection manager
  located at http://192.168.4.1/ if no network as been configured
- Saves WiFi SSID:s and passwords in "wifi.dat" in CSV format
- Connects automatically to the first available matching network
- Easy to apply
- Reset settings GPIO button support to let the user reset WiFi settings
- USB write protected GPIO button support to try it out while connected to the computer

## Usage

Install CircuitPython 8+ on your device.

Upload boot.py, code.py and wifimgr.py to the file system of the device.

Write your code below the connection prodedure in code.py or import it from
code.py.

Setup a GPIO to GND jumper wire or button in boot.py to control when
CircuitPython or the connected computer can write to the file system.

Connect to the WifiManager_AABBCC network, the password is "password".
Visit http://192.168.4.1/ to configure.

## How it works

It scans for available networks and then checks "wifi.dat" for matching
network SSID:s and then it tries to connect the matching networks.

If that did not succeed then it opens an access point with a web page
to allow the user to configure WiFi client settings. Then it tries to
connect and saves the settings to "wifi.dat".

Then when a connection to an access point has been established it
hands over the control to your code.

## Important to know

Only the device or the USB host (like a computer) are allowed write-access
to the file system in CircuitPython - not both at the same time. Therefore
there are GPIO options in boot.py to setup a button to choose which one should
have write access. Connect the GPIO and GND (push the button) to give
CircuitPython write permission.

When the code.py has completed the connection stops. This is by CircuitPython
design. It is maybe obvious, but to keep the device responding to ping for
instance you need to have a simple loop preferably with a sleep timeout
running.

## How to regain write permission

If you loose write permission to the file system of the device then you can
do this to remove the file that locks it through a serial connection:

1. Make a backup of your files on the file system to a folder on your computer.

2. Open a serial connection. For example in Debian Linux you can use screen:
apt install screen, then ls /dev/ttyACM* to find the current serial port number -
note the number it is ending in, usually 0, then screen /dev/ttyACM0 - replace
0 with your number, then press Enter.

2. Press Ctrl+C, then Enter to get the REPL prompt.

3. Type import os, then os.listdir() to list files or os.unlink('boot.py') to
remove boot.py or another file that is doing the locking, then hard reset the
device by removing USB or power or connecting the EN pin to GND if available.

## Notable behaviour differences from the MicroPython version

It does not automatically connect to the first open network it finds,
because that did not seem secure nor usable.

It does not open an access point if none of the configured networks
are connectable because of security reasons.

## Issues and contributions

If you find an issue please also supply a possible solution if possible, maybe
as a pull request.

## Authors

* **Robert Klebe** - *Development* - [dotpointer](https://github.com/dotpointer)

## Original MicroPython version authors

* **Tayfun ULU** - *Original MicroPython version*  - [tayfunulu](https://github.com/tayfunulu/WiFiManager/)

* **CPOPP** - *Original MicroPython version - web server* - [CPOPP](https://github.com/cpopp/MicroPythonSamples)

## License

This project is licensed under the MIT License - see the
[LICENSE.md](LICENSE.md) file for details.
