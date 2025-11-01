import time
import json
import requests
from pysolarmanv5 import PySolarmanV5
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -------------------- CONFIG --------------------
LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601
SOLARMAN_API = "https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send"
ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwX2FkaWw2MjQ1QGdtYWlsLmNvbV8yIiwibW9kaWZ5X3Bhc3N3b3JkIjoxLCJzY29wZSI6WyJhbGwiXSwiZGV0YWlsIjp7Im9yZ2FuaXphdGlvbklkIjowLCJ0b3BHcm91cElkIjpudWxsLCJncm91cElkIjpudWxsLCJyb2xlSWQiOi0xLCJ1c2VySWQiOjkzODc0MywidmVyc2lvbiI6MTAwMiwiaWRlbnRpZmllciI6ImFkaWw2MjQ1QGdtYWlsLmNvbSIsImlkZW50aXR5VHlwZSI6MiwibWRjIjoiRk9SRUlHTl8xIiwiYXBwSWQiOm51bGx9LCJleHAiOjE3NjcxNjY1NDAsIm1kYyI6IkZPUkVJR05fMSIsImF1dGhvcml0aWVzIjpbImFsbCJdLCJqdGkiOiI4ZjUyYTAxYy1kOTZkLTQwMTUtYWE0Mi05Mjg5ZmQwNGMyMGUiLCJjbGllbnRfaWQiOiJ0ZXN0In0.UIhPzh0COS5et-yb6TWzfTBg7GtfLscXvakwHoJXFvHDiS-AbZBzDAzjQWswOC8qIpe2upokuN11wJHvZbklQJguAYON3W2bodBtfA8voaPQ1r8ku1P_R9UUEX2iC-SvcjmrGYt-AP3ohg1v08HY13ueG_XPQ8mwOilbeYplM58LFnbDidMyR65WnuWgXYRLJRK39fsdtLpMx1dfym_GmcVpsyFkfZPa--gjkNmcEBRdvzzjB6J2mvqaHxpG1LHaOQu_LP6eVKu52z9ZUuAmx8jrUsT02sJTgqDelgB8b9wtkKBSw3KiyJGBZdvKc8GN_fiPzmwuDUGxKRwoFcOGfg"  # Replace with your valid token

# Device-specific values
DEVICE_SN = "2203274322"
DEVICE_ID = "217113889"
GATEWAY_ID = 212907181
GATEWAY_SN = "2331491601"

# Limits & thresholds
MAX_LIMIT = 5000        # Max export limit
VOLTAGE_UPPER = 273.5     # Upper voltage threshold 268.5 for summer
VOLTAGE_LOWER = 267.5    # Lower voltage threshold 267 for summer
INCREMENT = 100         # Watts to increase
DECREMENT = 200         # Watts to decrease 200 prev
SUN_THRESHOLD = 500     # Max difference allowed between limit and actual power
MIN_LIMIT = 1000  # safety floor
MIN_LIMIT_AFTER = 2000
SUN_THRESHOLD = 700     # max difference to allow increasing
SUN_DIFF_MAX = 900      # if difference exceeds this, reduce
SUN_DIFF_DECREASE = 300 # amount to reduce when sun not enough

disableExport = False
tripEvent = False
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

        if ((current_export > -50 and grid_voltage > 260) or (grid_voltage > 270 and current_limit == MIN_LIMIT)) and not disableExport:
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

        sheet.append_row([timestamp, inverter_power, current_limit, current_export, grid_voltage, current_utl, current_action, battery_charge])
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
        print("Reinitializing client...")
        time.sleep(5)
        client = init_client()
