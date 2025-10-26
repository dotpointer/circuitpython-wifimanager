import re
import socketpool
import storage
import time
import wifi
import json

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

    data = strip_headers(request)
    data = json.loads(data)

    if "ssid" not in data or "password" not in data or len(str(data["ssid"])) < 1:
        send_response(client, json.dumps({'status': False, 'data': "Parameters not found" }), status_code=400)
        print('Handle configure aborted, missing parameters')
        return False

    ssid = data["ssid"]
    password = data["password"]

    if len(ssid) == 0:
        send_response(client, json.dumps({'status': False, 'data': "SSID must be provided" }), status_code=400)
        print('Handling configure aborted, no SSID provided')
        return False

    if do_connect(ssid, password):
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = password
        response = "Successfully connected to the WiFi network " + ssid

        write_result = write_profiles(profiles)
        # write_result = False # DEBUG
        if write_result is False:
            print('Failed to save changes')
            response = response + " Failed to save changes."

        send_response(client, json.dumps({'status': True, 'data': response }))
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
        send_response(client, json.dumps({'status': False, 'data': "Could not connect to the WiFi network " + ssid }), status_code=500)
        print('Handle configure ended, no connection')
        return False

def handle_not_found(client, url):
    print('Handle not found start')
    send_response(client, json.dumps({'status': False, 'data': "Path not found: {}".format(url) }) , status_code=404)
    print('Handle not found end')

def handle_root(client):
    print('Handle / start')
    send_header(client)
    try:
        with open("/wifimgr-template.html", "r") as fp:
            while True:
                line = fp.readline()
                if not line:
                    break
                sendall(client, line)

    except OSError as e:
        print("Exception", str(e))

    client.close()
    print('Handle / end')

def handle_data(client):
    global AP_SSID
    print('Handle list SSID:s')
    wifi.radio.enabled = True

    networks = []
    for n in wifi.radio.start_scanning_networks():
        print("Found \"%s\", #%s" % (n.ssid, n.channel))
        networks.append({'ssid': n.ssid, 'channel': n.channel})

    wifi.radio.stop_scanning_networks()

    send_header(client, content_type='application/json')
    sendall(client, json.dumps({'ap_ssid': AP_SSID, 'readonly': storage.getmount('/').readonly, 'file_network_profiles': FILE_NETWORK_PROFILES, 'networks': networks}))

def sendall(client, data):
    data = data.replace('  ', ' ')
    # print('Sending: ' + str(len(data)) + ' b')
    while len(data):
        # split data in chunks to avoid EAGAIN exception
        part = data[0:512]
        data = data[len(part):len(data)]
        # print('Sending: ' + str(len(part)) + 'b')
        # EAGAIN too much data exception catcher
        while True:
            try:
                client.sendall(part)
            except OSError as e:
                print("Exception", str(e))
                time.sleep(0.25)
                pass
            break

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

def send_header(client, status_code=200, content_type="text/html; charset=UTF-8", content_length=None):
    sendall(client, "HTTP/1.0 {} OK\r\n".format(status_code))
    sendall(client, "Content-Type: " + content_type + "\r\n")
    if content_length is not None:
        sendall(client, "Content-Length: {}\r\n".format(content_length))
    sendall(client, "\r\n")

def send_response(client, payload, status_code=200):
    content_length = len(payload)
    content_type = "application/json"
    send_header(client, status_code, content_type, content_length)
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
    try:
        server_socket.bind(addr)
    except OSError as e:
        print("Exception", str(e))
        return;
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
            elif url == "/data":
                handle_data(client)
            else:
                handle_not_found(client, url)

        finally:
            client.close()

def strip_headers(s):
    if s.find("\r\n\r\n") != -1:
        s = s[s.find("\r\n\r\n") + 4:]
    return s

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
