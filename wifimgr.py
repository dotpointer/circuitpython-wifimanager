import re
import socketpool
import storage
import time
import wifi

# extract access point mac address
mac_ap = ' '.join([hex(i) for i in wifi.radio.mac_address_ap])
mac_ap = mac_ap.replace('0x', '').replace(' ', '').upper()

# access point settings
AP_SSID = "WifiManager_" + mac_ap[5:10] + mac_ap[1:2]
AP_PASSWORD = "password"
# AP_AUTHMODES = [wifi.AuthMode.OPEN]
AP_AUTHMODES = [wifi.AuthMode.WPA2, wifi.AuthMode.PSK]

FILE_NETWORK_PROFILES = 'wifi.dat'
ap_enabled = False
server_socket = None

def do_connect(ssid, password):
    wifi.radio.enabled = True
    if wifi.radio.ap_info is not None:
        return None
    print('Trying to connect to "%s"...' % ssid)
    try:
        wifi.radio.connect(ssid, password)
    except Exception as e:
        print("Exception", str(e))
    for retry in range(200):
        connected = wifi.radio.ap_info is not None
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        t = []
        t.append(str(wifi.radio.ipv4_address))
        t.append(str(wifi.radio.ipv4_subnet))
        t.append(str(wifi.radio.ipv4_gateway))
        t.append(str(wifi.radio.ipv4_dns))
        print('\nConnected. Network config: IP: ', end='')
        print('%s, subnet: %s, gateway: %s, DNS: %s' % tuple(t))

    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


def get_connection():
    """return a working wifi.radio connection or None"""

    while wifi.radio.ap_info is None:
        # first check if there already is any connection:
        if wifi.radio.ap_info is not None:
            print('WiFi connection detected')
            return wifi.radio

        connected = False
        # connecting takes time, wait and retry
        time.sleep(3)
        if wifi.radio.ap_info is not None:
            print('WiFi connection detected')
            return wifi.radio

        # read known network profiles from file
        profiles = read_profiles()

        # search networks in range
        wifi.radio.enabled = True

        # networks are configured
        if (len(profiles)):
            networks = []
            for n in wifi.radio.start_scanning_networks():
                networks.append([n.ssid, n.bssid, n.channel, n.rssi, n.authmode])
            wifi.radio.stop_scanning_networks()

            for ssid, bssid, channel, rssi, authmodes in sorted(networks, key=lambda x: x[3], reverse=True):
                encrypted = 0
                authmodes_text = []
                for authmode in authmodes:
                    if (authmode == wifi.AuthMode.OPEN):
                        authmodes_text.append('Open')
                    elif (authmode == wifi.AuthMode.WEP):
                        authmodes_text.append('WEP')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.WEP):
                        authmodes_text.append('WPA')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.WPA):
                        authmodes_text.append('WPA')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.WPA2):
                        authmodes_text.append('WPA2')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.WPA3):
                        authmodes_text.append('WPA3')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.PSK):
                        authmodes_text.append('PSK')
                        encrypted = 1
                    elif (authmode == wifi.AuthMode.ENTERPRISE):
                        authmodes_text.append('ENTERPRISE')
                        encrypted = 1
                authmodes_text = ', '.join(authmodes_text)
                print("Found \"%s\", #%d, %d dB, %s" % (ssid, channel, rssi, authmodes_text), end='')
                if ssid in profiles:
                    print(", known")
                    if encrypted:
                        password = profiles[ssid]
                        connected = do_connect(ssid, password)
                    else:  # open
                        print(", open")
                        connected = do_connect(ssid, None)
                else:
                    print(", unknown")
                if connected:
                    break
        # no networks configured
        else:
            connected = start_ap()

        if connected:
            return wifi.radio

def handle_configure(client, request):
    global ap_enabled
    print('Handle configure start')
    print("Request:", request.strip())
    match = re.search("ssid=([^&]*)&password=(.*)", request)

    if match is None:
        send_response(client, "Parameters not found", status_code=400)
        print('Handle configure aborted, missing parameters')
        return False
    ssid = match.group(1).replace("%3F", "?").replace("%21", "!")
    password = match.group(2).replace("%3F", "?").replace("%21", "!")

    if len(ssid) == 0:
        send_response(client, "SSID must be provided", status_code=400)
        print('Handling configure aborted, no SSID provided')
        return False

    if do_connect(ssid, password):
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = password
        write_result = write_profiles(profiles)
        response = get_html_head() + """\
  <p>
        """
        response = response + """\
   Successfully connected to the WiFi network "%(ssid)s".
        """ % dict(ssid=ssid)

        if write_result is False:
            print('Failed to write changes')
            response = response + """\
    <br><br>
    Failed to save changes.
            """
        response = response + """\
  </p>
        """
        response = response + get_html_footer()
        send_response(client, response)
        time.sleep(30)
        if write_result:
            if ap_enabled:
                wifi.radio.stop_ap()
                ap_enabled = False
                print('Access point stopped')
            time.sleep(5)
            print('Handle configure end, connected')
        # to require write success:
        # else:
        #   wifi.radio.stop_station()
        #   print('Handle configure end, connected and disconnected')
        # return write_result
    else:

        response = get_html_head()
        response = response + """\
    <h1>Could not connect to the WiFi network "%(ssid)s".</h1>
     <form>
      <div>
       <input type="button" value="Go back" onclick="history.back()">
     </div>
    </form>
        """ % dict(ssid=ssid)
        response = response + get_html_footer()
        send_response(client, response)
        print('Handle configure ended, no connection')
        return False

def handle_not_found(client, url):
    print('Handle not found start')
    send_response(client, "Path not found: {}".format(url), status_code=404)
    print('Handle not found end')

def get_html_footer():
    return """\
 <p class="footer">
  <a href="https://github.com/dotpointer/circuitpython_wifimanager"
   target="_blank" rel="noopener">dotpointer / circuitpython_wifimanager</a>
  <br>
  Based on <a href="https://github.com/tayfunulu/WiFiManager"
  target="_blank" rel="noopener">tayfunulu / WiFiManager</a> and
  <a href="https://github.com/cpopp/MicroPythonSamples"
   target="_blank" rel="noopener">cpopp / MicroPythonSamples</a>
  </p>
</body>
</html>
    """

def get_html_head():
    global AP_SSID
    return """\
<!DOCTYPE html>
<html>
<head>
<title>""" + AP_SSID + """ - Wi-Fi client setup</title>
<style>
  a {
  color:#fff;
  }
  a:hover {
  color:#ddd;
  }
  h1 {
  font-size: 28px;
  }
  body {
  background:#1e1e1e;
  border-bottom:10px solid #e71c8c;
  color:#fff;
  font-family:Arial, sans-serif;
  font-size:24px;
  margin:0;
  padding:5px;
  text-align:center;
  }
  button {
  background:transparent;
  border-radius:30px;
  border:3px solid #fff;
  color:#fff;
  cursor:pointer;
  font-weight:bold;
  padding:5px 20px;
  }
  button:hover {
  color:#000;
  background:#fff
  }
  button, label {
  cursor:pointer;
  font-size: 24px;
  }
  html {
  background-repeat:no-repeat;
  background:#333;
  height:100%;
  margin:0;
  }
  input.text {
  background:transparent;
  border-radius:30px;
  border:3px solid #fff;
  color:#fff;
  font-size: 24px;
  font-weight:bold;
  padding:3px 10px;
  }
  table {
  margin-left:auto;
  margin-right:auto;
  }
  .footer {
  font-size:18px;
  }
  .network {
  background:transparent;
  border-radius:30px;
  border:3px solid #fff;
  color:#fff;
  cursor:pointer;
  display:inline-block;
  font-weight:bold;
  margin: 5px auto;
  }
  .network input[type="radio"] {
  border:none;
  cursor:pointer;
  height: 17px;
  outline:3px;
  }
  .network label {
  display:inline-block;
  padding:5px 20px;
  }
</style>
</head>
<body>
<h1>""" + AP_SSID + """ - Wi-Fi client setup</h1>
"""

def sendall(client, data):
    data = data.replace('  ', ' ')
    while len(data):
        # split data in chunks to avoid EAGAIN exception
        part = data[0:512]
        data = data[len(part):len(data)]
        print('Sending: ' + str(len(part)) + 'b')
        # EAGAIN too much data exception catcher
        while True:
            try:
                client.sendall(part)
            except OSError as e:
                print("Exception", str(e))
                time.sleep(0.25)
                pass
            break

def handle_root(client):
    print('Handle / start')
    wifi.radio.enabled = True

    networks = []
    for n in wifi.radio.start_scanning_networks():
        print("Found \"%s\", #%s" % (n.ssid, n.channel))
        networks.append([n.ssid, n.channel])
    wifi.radio.stop_scanning_networks()
    send_header(client)
    sendall(client, get_html_head())
    sendall(client, """\
  <form action="configure" method="post">
    """)
    while len(networks):
        network = networks.pop(0)
        sendall(client, """\
   <div class="network">
    <input type="radio" id="ssid_{0}" name="ssid" value="{0}" />
    <label for="ssid_{0}">{0} (#{1})</label>
   </div>
   <br>
        """.format(network[0], network[1]))
    sendall(client, """\
   <div><label>Password:</label> <input class="text" name="password" type="password" ></div>
   <p><button>Connect</button></p>
  </form>
    """)

    if storage.getmount('/').readonly:
        sendall(client, """\
  <p>Warning, the file system is in read-only mode, settings will not be saved.</p>
        """)
    else:
        sendall(client, """\
  <p>
   The SSID and password will be saved in the
   "%(filename)s" on the device.
  </p>
        """ % dict(filename=FILE_NETWORK_PROFILES))
    sendall(client, get_html_footer())
    client.close()
    print('Handle / end')

def read_profiles():
    profiles = {}
    try:
        with open(FILE_NETWORK_PROFILES) as f:
            lines = f.readlines()
        for line in lines:
            ssid, password = line.strip("\n").split(";")
            profiles[ssid] = password
    except OSError:
        profiles = {}
    return profiles

def send_header(client, status_code=200, content_length=None):
    sendall(client, "HTTP/1.0 {} OK\r\n".format(status_code))
    sendall(client, "Content-Type: text/html\r\n")
    if content_length is not None:
        sendall(client, "Content-Length: {}\r\n".format(content_length))
    sendall(client, "\r\n")

def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        sendall(client, payload)
    client.close()

def start_ap(port=80):
    global ap_enabled, server_socket

    addr = socketpool.SocketPool(wifi.radio).getaddrinfo('0.0.0.0', port)[0][-1]

    if server_socket:
        server_socket.close()
        server_socket = None

    wifi.radio.enabled = True

    if ap_enabled is False:
        # to use encrypted AP, use authmode=[wifi.AuthMode.WPA2, wifi.AuthMode.PSK]
        if (AP_AUTHMODES[0] == wifi.AuthMode.OPEN):
            wifi.radio.start_ap(ssid=AP_SSID, authmode=AP_AUTHMODES)
        else:
            wifi.radio.start_ap(ssid=AP_SSID, password=AP_PASSWORD, authmode=AP_AUTHMODES)
        ap_enabled = True

    server_socket = socketpool.SocketPool(wifi.radio).socket()
    server_socket.bind(addr)
    server_socket.listen(1)
    if storage.getmount('/').readonly:
        print('File system is read only')
    else:
        print('File system is writeable')
    print('Access point started, connect to WiFi "' + AP_SSID + '"', end='')
    if (AP_AUTHMODES[0] != wifi.AuthMode.OPEN):
        print(', the password is "' + AP_PASSWORD + '"')
    else:
        print('')
    print('Visit http://' + str(wifi.radio.ipv4_address_ap) + '/ in your web browser')
    # print('Listening on:', addr)

    while True:
        if wifi.radio.ap_info is not None:
            print('WiFi connection detected')
            if ap_enabled:
                wifi.radio.stop_ap()
                ap_enabled = False
                print('Access point stopped')
            return True

        # EAGAIN exception catcher
        while True:
            try:
                client, addr = server_socket.accept()
            except OSError as e:
                print("Exception", str(e))
                time.sleep(0.25)
                pass
            break

        print('Client connected - %s:%s' % addr)
        try:
            client.settimeout(5)

            request = b""
            try:
                while "\r\n\r\n" not in request:
                    buffer = bytearray(512)
                    client.recv_into(buffer, 512)
                    request += buffer
                    print('Received data')
            except OSError:
                pass

            # Handle form data from Safari on macOS and iOS; it sends \r\n\r\nssid=<ssid>&password=<password>
            try:
                buffer = bytearray(1024)
                client.recv_into(buffer, 1024)
                request += buffer
                print("Received form data after \\r\\n\\r\\n(i.e. from Safari on macOS or iOS)")
            except OSError:
                pass

            request = request.decode().strip("\x00").replace('%23', '#')

            print("Request is: {}".format(request))
            if "HTTP" not in request:  # skip invalid requests
                continue

            url = re.search("(?:GET|POST) (.*?)(?:\\?.*?)? HTTP", request).group(1)
            print("URL is {}".format(url))

            if url == "/":
                handle_root(client)
            elif url == "/configure":
                handle_configure(client, request)
            else:
                handle_not_found(client, url)

        finally:
            client.close()

def write_profiles(profiles):
    print('Write profiles start')
    lines = []
    for ssid, password in profiles.items():
        print('Preparing line for "' + ssid + '"')
        lines.append("%s;%s\n" % (ssid, password))
    try:
        print('Writing ' + FILE_NETWORK_PROFILES)
        with open(FILE_NETWORK_PROFILES, "w") as f:
            f.write(''.join(lines))
        return True
    except OSError as e:
        print("Exception", str(e))
        return False
    print('Write profiles end')
