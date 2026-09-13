import time
import json
import requests
from pysolarmanv5 import PySolarmanV5
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# tunya
import tinytuya
import base64

device = tinytuya.OutletDevice(
    "bf7955d069141119f4xctf",
    "192.168.18.75",
    "9Dz8Nn(cPoA~CS!I",
    connection_timeout=1,
    connection_retry_limit=1,     # don't let tinytuya block on its own retries
    connection_retry_delay=0,
)
device.set_version(3.5)
device.set_socketPersistent(True)
device.set_socketTimeout(1)


def decode_phase(b64):
    raw = base64.b64decode(b64)
    if len(raw) < 8:
        return None
    voltage = int.from_bytes(raw[0:2], "big") / 10.0
    current = int.from_bytes(raw[2:5], "big") / 1000.0
    power   = int.from_bytes(raw[5:8], "big")          # watts
    return voltage, current, power


state = {"dps": {}}
device.status(nowait=True)
last_poll = last_print = last_beat = 0.0

def _power_from(dps):
    """Pull watts out of a dps dict, or None if this packet has no power data."""
    if "6" in dps:                          # phase_a blob: volts, amps, watts
        raw = base64.b64decode(dps["6"])
        if len(raw) >= 8:
            return int.from_bytes(raw[5:8], "big")
    return dps.get("118")     


def _is_error(data):
    """True for tinytuya's error payloads, e.g. device unreachable."""
    return not isinstance(data, dict) or "Error" in data or "Err" in data

def read_power(timeout=6.0, skip=1, debug=False):
    """Return the breaker's power draw in watts, or None if it's unreachable or
    silent. Always returns within roughly `timeout` seconds — never blocks the
    caller, even during a blackout.

    Discards `skip` power-bearing packets before accepting one, since the first
    reply is the device's stored value and the recomputed one lands after.
    """
    deadline = time.time() + timeout

    try:
        device.cache_clear()

        # toss anything left from the last call, but never spin: stop on the
        # first empty read, on an error payload, or after a short window
        drain_until = time.time() + 0.6
        while time.time() < drain_until:
            data = device.receive()
            if not data:
                break
            if _is_error(data):
                if debug:
                    print(f"  device unreachable: {data}")
                return 0

        device.set_value(106, True, nowait=True)              # 'refresh sensors'
        device.updatedps(["6", "118"], nowait=True)
        device.status(nowait=True)

        seen = 0
        while time.time() < deadline:
            data = device.receive()
            if not data:
                continue
            if _is_error(data):
                if debug:
                    print(f"  device unreachable: {data}")
                return 0
            if "dps" not in data:
                continue

            watts = _power_from(data["dps"])
            if watts is None:
                continue

            seen += 1
            if debug:
                print(f"  packet {seen}: {watts} W  {data['dps']}")
            if seen > skip:
                return watts

    except Exception as e:                  # socket died, device vanished, etc.
        if debug:
            print(f"  read_power failed: {e}")
        return 0

    return 0


# -------------------- CONFIG --------------------
LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601
SOLARMAN_API = "https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send"
ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwX2FkaWw2MjQ1QGdtYWlsLmNvbV8yIiwibW9kaWZ5X3Bhc3N3b3JkIjoxLCJzY29wZSI6WyJhbGwiXSwiZGV0YWlsIjp7Im9yZ2FuaXphdGlvbklkIjowLCJyb2xlSWQiOi0xLCJ1c2VySWQiOjkzODc0MywidmVyc2lvbiI6MTAwMiwiaWRlbnRpZmllciI6ImFkaWw2MjQ1QGdtYWlsLmNvbSIsImlkZW50aXR5VHlwZSI6MiwibWRjIjoiRk9SRUlHTl8xIn0sImV4cCI6MTc4OTQwNzMzMiwibWRjIjoiRk9SRUlHTl8xIiwiYXV0aG9yaXRpZXMiOlsiYWxsIl0sImp0aSI6ImNiOTZkYjIzLTQzMDMtNDEzMi1hMDhkLWNjNzBjZjEwY2YxOCIsImNsaWVudF9pZCI6InRlc3QifQ.cxBXoF-vk4-VB-vHjiiSmgXad233n-AB9yvEb8chx8CT4-q0Epu_60Fn7mOuJJSS9rbnAGNTzV3x3gKoalAt1gNykt8jUA4otUl5UN0Chu88GUFjqN5x1SgDwOv5v7nLC614PmAy811qaWolYmy77D_UXYqnYRlKoqqbzVvnuorQ8oVFy71ojVRi8aMO_kr8wRUOnhSlH6erscKd2p1V8sUkTCRvcQctrh2Wc7nq0KteAI3DRNsd7e_EptpsZt5zDhO8vSOt_I9IEHpubeVD7Gss9JqAb2lqF48JJAqxmtH27PMGpVZ0s5Nu4lef4s93-22SlapR3SZGnWmup_T7wQ"  # Replace with your valid token

# Device-specific values
DEVICE_SN = "2203274322"
DEVICE_ID = "217113889"
GATEWAY_ID = 212907181
GATEWAY_SN = "2331491601"

# Limits & thresholds
MAX_LIMIT = 6000        # Max export limit
VOLTAGE_UPPER = 279     # Upper voltage threshold 268.5 for summer
VOLTAGE_LOWER = 273.5    # Lower voltage threshold 267 for summer
INCREMENT = 100         # Watts to increase
DECREMENT = 300         # Watts to decrease 200 prev
SUN_THRESHOLD = 300     # Max difference allowed between limit and actual power 300 before
MIN_LIMIT = 1000  # safety floor
MIN_LIMIT_AFTER = 2000
SUN_DIFF_MAX = 900      # if difference exceeds this, reduce
SUN_DIFF_DECREASE = 300 # amount to reduce when sun not enough

disableExport = False
tripEvent = False
toggleState = False
lastStateRaised = False


# Polling interval
SLEEP_TIME_DAY = 5          # seconds
SLEEP_TIME_NIGHT = 10          # seconds

# -------------------- GOOGLE SHEETS SETUP --------------------
# Define scope
scope = ["https://spreadsheets.google.com/feeds", 
         "https://www.googleapis.com/auth/drive"]

# Path to your downloaded credentials JSON file
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "service_account.json", scope
)

# Authorize client
client_gs = gspread.authorize(creds)

# Open sheet (make sure your service account email has edit access to it!)
sheet = client_gs.open_by_key("14lR66an_8AHzbQzT14iZO1A8Px2sxf83hHEwXADq67w").sheet1
# sheet2 = client_gs.open_by_key("14lR66an_8AHzbQzT14iZO1A8Px2sxf83hHEwXADq67w").worksheet("logs")
# -------------------------------------------------------------

# -------------------- FUNCTIONS --------------------
def init_client():
    """Initialize the Solarman client."""
    while True:
        try:
            client = PySolarmanV5(LOGGER_IP, LOGGER_SN)
            print("Client initialized successfully.")
            return client
        except Exception as e:
            print("Failed to initialize client:", e)
            print("Retrying in 5 seconds...")
            time.sleep(5)

def read_voltage(client):
    raw = client.read_holding_registers(150, 1)[0]
    return raw / 10.0

def read_register(client, reg):
    return client.read_holding_registers(reg, 1)[0]

def read_signed_register(client, reg):
    """Read a single 16-bit signed register."""
    raw = client.read_holding_registers(reg, 1)[0]
    if raw > 32767:
        raw -= 65536
    return raw

def get_min_limit():
    """Return time-adjusted minimum export limit."""
    now = datetime.datetime.now().time()
    if now.hour >= 16 or now.hour < 7:  # after 4 pm
        return MIN_LIMIT_AFTER
    return MIN_LIMIT

def send_limit_request(new_limit, enable_selling="1"):
    global tripEvent
    payload = {
        "product": "0_5407_1",
        "deviceSn": DEVICE_SN,
        "deviceId": DEVICE_ID,
        "gatewayId": GATEWAY_ID,
        "gatewaySn": GATEWAY_SN,
        "code": "s_cnjgzms1",
        "codeGroup": "G1101",
        "operationType": 5,
        "extendWeb": json.dumps({
            "inputParam": {
                "00F4": {"v": "1"}, # selling or zero export
                "00F7":{"v":enable_selling},  # selling enabled or disabled
                "00F8-1": {"v": "0000000"},
                "00F5": {"v": "2100"},
                "0035": {"v": new_limit},
                "00F3": {"v": "1"},
                "00CE": {"v": "20"},
                "00F8": {"v": "0"}  # remove battery usage time of use
            }
        }),
        "orderTimeout": 60
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(SOLARMAN_API, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            print(f"Export limit successfully set to {new_limit} W")
            sheet.append_row([f"Export limit successfully set to {new_limit} W"])
        else:
            print(f"Failed to set limit. Status code: {r.status_code}, Response: {r.text}")
            tripEvent = False
            sheet.append_row([f"Failed to set limit. Status code: {r.status_code}, Response: {r.text}"])
    except Exception as e:
        tripEvent = False
        print("Error sending request:", e)


def toggle_beep(toggle=False):
    global toggleState
    if toggleState == toggle:
        return
    
    payload = {
        "product": "0_5407_1",
        "deviceSn": DEVICE_SN,
        "deviceId": DEVICE_ID,
        "gatewayId": GATEWAY_ID,
        "gatewaySn": GATEWAY_SN,
        "code": "s_dcsz2",
        "codeGroup": "G1101",
        "operationType": 5,
        "extendWeb": json.dumps({
        "inputParam": {
            "00D2": {"v": "20"},
            "00D3": {"v": "90"},
            "00DC": {"v": 52},
            "00DD": {"v": 58},
            "00DE": {"v": 56 if toggle else 52.2},
            "00D6": {"v": "1"},
            "0146-14": {"v": "0"},
            "0146": {"v": "0"},
            "000F": {"v": "0"}
        }
    }),
        "orderTimeout": 60
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(SOLARMAN_API, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            toggleState = toggle
            print(f"toggle set to {toggle}")
            sheet.append_row([f"toggle successfully set to {toggle}"])
        else:
            print(f"Failed to toggle. Status code: {r.status_code}, Response: {r.text}")
            sheet.append_row([f"Failed to toggle. Status code: {r.status_code}, Response: {r.text}"])
    except Exception as e:
        print("Error sending request:", e)


# -------------------- MAIN LOOP --------------------
previous_power = 0
client = init_client()

while True:
    try:
        grid_voltage = read_voltage(client)
        current_limit = read_register(client, 53)
        inverter_power = read_signed_register(client, 136)
        current_export = read_signed_register(client, 134)
        current_utl = read_signed_register(client, 176)
        battery_charge = read_signed_register(client, 190)
        ideal_limit = current_limit
        current_action = "Unchanged"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Grid Voltage: {grid_voltage:.1f} V | Inverter Power: {inverter_power} W | Current Limit: {current_limit} W | Current Export: {current_export} W | Battery Charge: {battery_charge} W")

# (current_export > -50 and grid_voltage > 260) or 
        if ((grid_voltage > 270 and current_limit == MIN_LIMIT)) and not disableExport:
            current_action = f"Disabling Export {current_limit}"
            disableExport = True
        else:
            # Increase logic
            if (grid_voltage < VOLTAGE_LOWER and inverter_power > previous_power) and not lastStateRaised:
                if (current_limit - (inverter_power - battery_charge)) <= SUN_THRESHOLD:
                    ideal_limit = min(current_limit + INCREMENT, MAX_LIMIT)
                    current_action = f"Increasing limit to {ideal_limit}"
                    lastStateRaised = True
            else:
                lastStateRaised = False
            # Decrease logic if voltage too high
            if grid_voltage > VOLTAGE_UPPER:
                ideal_limit = max(current_limit - DECREMENT, get_min_limit())
                current_action = f"Decreasing limit to {ideal_limit}"

            # Reduce if sun not enough commenting for now
            # if (ideal_limit - (inverter_power - battery_charge)) > SUN_DIFF_MAX:
            #     ideal_limit = max(ideal_limit - SUN_DIFF_DECREASE, get_min_limit())
            #     current_action = f"Decreasing limit to {ideal_limit}"

            if ideal_limit == current_limit:
                current_action = "Unchanged"
        power_w = read_power()  
        sheet.append_row([timestamp, inverter_power, current_limit, current_export, grid_voltage, current_utl, current_action, battery_charge, power_w,power_w + (current_export*2)])
        if power_w == 0 and grid_voltage > 100:
            toggle_beep(True)
        else:
            toggle_beep(False)
        
        if disableExport and not tripEvent:
            send_limit_request(ideal_limit, "0")
            tripEvent = True
        else:
            # Only send request if ideal limit changed
            # Enforce minimum based on time of day
            ideal_limit = max(ideal_limit, get_min_limit())
            if ideal_limit != current_limit:
                print(f"Setting Limit: {ideal_limit} W ")
                disableExport = False
                tripEvent = False
                send_limit_request(ideal_limit)

        previous_power = inverter_power
        now = datetime.datetime.now().time()
        if now.hour >= 16 or now.hour < 7:  # after 4 pm
            time.sleep(SLEEP_TIME_NIGHT)
        else:
            time.sleep(SLEEP_TIME_DAY)

    except Exception as e:
        print("Error encountered:", e)
        try:
                sheet.append_row([f"Error encountered: {e}"])
        except Exception as log_err:
                tripEvent = False
                print("Failed to log error:", log_err)
        # kill the previous client's threads
        try:
            client.disconnect()
            print("Client disconnected cleanly.")
        except Exception:
            print("Client disconnection failed (may already be closed).")
        print("Reinitializing client...")
        time.sleep(5)
        client = init_client()
