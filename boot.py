import digitalio
import microcontroller
import storage

# make the USB read only button, to allow CircuitPython to write to the file
# system
# usage: change the GPIO below, then connect a jumper wire or button between
# the GPIO and the GND pin
button_usb_readonly = digitalio.DigitalInOut(microcontroller.pin.GPIO38)
button_usb_readonly.direction = digitalio.Direction.INPUT
button_usb_readonly.pull = digitalio.Pull.UP
if not button_usb_readonly.value:
    storage.remount("/", False)

# reset settings button, to reset the wifi settings, useful to wire to a reset
# button on the physical hardware to allow the user to reset the wifi settings
# usage: change the GPIO below, then connect a jumper wire or button between
# the GPIO and the GND pin to empty the wifi.dat file, please note that
# CircuitPython needs write access, see the note above about this
button_reset_settings = digitalio.DigitalInOut(microcontroller.pin.GPIO40)
button_reset_settings.direction = digitalio.Direction.INPUT
button_reset_settings.pull = digitalio.Pull.UP
if not button_reset_settings.value:
    print('Emptying wifi.dat')
    try:
        with open('wifi.dat', 'w') as f:
          f.write('')
    except OSError as e:
        print("Exception", str(e))
