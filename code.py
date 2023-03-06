import supervisor
import time
import wifimgr

# disable auto reload to stop unexpected reloads
supervisor.set_next_code_file(filename = 'code.py', reload_on_error = False, reload_on_success = False)
supervisor.runtime.autoreload = False

wlan = wifimgr.get_connection()
if wlan is None:
    print("Could not initialize the network connection.")
    while True:
        pass

# put your code below this line, example below to keep it running,
# otherwise it will not respond to ping
print("WifiManager routines has ended")
while True:
    time.sleep(1)
