import time
import json
import requests
from pysolarmanv5 import PySolarmanV5

# -------------------- CONFIG --------------------
LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601
SOLARMAN_API = "https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send"
ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwX2FkaWw2MjQ1QGdtYWlsLmNvbV8yIiwibW9kaWZ5X3Bhc3N3b3JkIjoxLCJzY29wZSI6WyJhbGwiXSwiZGV0YWlsIjp7Im9yZ2FuaXphdGlvbklkIjowLCJ0b3BHcm91cElkIjpudWxsLCJncm91cElkIjpudWxsLCJyb2xlSWQiOi0xLCJ1c2VySWQiOjkzODc0MywidmVyc2lvbiI6MTAwMCwiaWRlbnRpZmllciI6ImFkaWw2MjQ1QGdtYWlsLmNvbSIsImlkZW50aXR5VHlwZSI6MiwibWRjIjoiRk9SRUlHTl8xIiwiYXBwSWQiOm51bGx9LCJleHAiOjE3NjA5NDg1OTQsIm1kYyI6IkZPUkVJR05fMSIsImF1dGhvcml0aWVzIjpbImFsbCJdLCJqdGkiOiJlOTkyNjllOS1kMmM0LTQzYTctYjhhZS1iZTAyMmE4NWQxNjMiLCJjbGllbnRfaWQiOiJ0ZXN0In0.VVHUOls_VgG88a8BMfPhqC9FVEzGuW9ARqiS7YEyO7703w1uy9tD76ehqx3UKfA3l2fe_04oUCe66WDBlqHuA7Vt56W0DFMDrv6zoTi3PdMz_7aFgue0c5jiCHFtyjKycx9PnMPt2kZlpBfIJ0nVP0YwFMoxSGevg4Eh4vHUyKoHKBzjFL9jfbvSpWI6axCtpowQ_eu6AByL3Oaa9MCABt9xI89Zu1VBgorCm3vg_YiY8pbIAVSAsqtNjnBVrvdGPKK2SRNMbOAstzSbmKwrVJd3fBxXvItf6QFjVPoQJBP9kylyB7WEe2U4z4NEULt1IVuSFnStvMXDPCn7to0ZhQ"  # Replace with your valid token

# Device-specific values
DEVICE_SN = "2203274322"
DEVICE_ID = "217113889"
GATEWAY_ID = 212907181
GATEWAY_SN = "2331491601"

# Limits & thresholds
MAX_LIMIT = 5000        # Max export limit
VOLTAGE_UPPER = 269     # Upper voltage threshold
VOLTAGE_LOWER = 267     # Lower voltage threshold
INCREMENT = 100         # Watts to increase
DECREMENT = 200         # Watts to decrease
SUN_THRESHOLD = 500     # Max difference allowed between limit and actual power
MIN_LIMIT = 1800  # safety floor
SUN_THRESHOLD = 500     # max difference to allow increasing
SUN_DIFF_MAX = 600      # if difference exceeds this, reduce
SUN_DIFF_DECREASE = 300 # amount to reduce when sun not enough

# Polling interval
SLEEP_TIME = 5          # seconds

# -------------------- INIT CLIENT --------------------
client = PySolarmanV5(LOGGER_IP, LOGGER_SN)

def read_voltage():
    raw = client.read_holding_registers(150, 1)[0]
    return raw / 10.0

def read_register(reg):
    return client.read_holding_registers(reg, 1)[0]

def send_limit_request(new_limit):
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
                "00F4": {"v": "0"},
                "00F8-1": {"v": "0000000"},
                "00F5": {"v": "2100"},   # Keep as placeholder
                "0035": {"v": new_limit}, # Desired limit
                "00F3": {"v": "1"},
                "00CE": {"v": "20"},
                "00F8": {"v": "0"}
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
        else:
            print(f"Failed to set limit. Status code: {r.status_code}, Response: {r.text}")
    except Exception as e:
        print("Error sending request:", e)

# -------------------- MAIN LOOP --------------------
previous_power = 0
while True:
    try:
        grid_voltage = read_voltage()
        current_limit = read_register(53)   # Reg 53 = current export limit
        inverter_power = read_register(136) # Reg 136 = actual inverter power

        ideal_limit = current_limit
        print(f"Grid Voltage: {grid_voltage:.1f} V | Current Limit: {current_limit} W | Inverter Power: {inverter_power} W | Ideal Limit: {ideal_limit} W")
        # Increase logic
        if grid_voltage < VOLTAGE_LOWER and inverter_power > previous_power:
            if (current_limit - inverter_power) <= SUN_THRESHOLD:
                ideal_limit = min(current_limit + INCREMENT, MAX_LIMIT)

        # Decrease logic if voltage too high
        if grid_voltage > VOLTAGE_UPPER:
            ideal_limit = max(current_limit - DECREMENT, MIN_LIMIT)

        # Reduce if sun not enough
        if (ideal_limit - inverter_power) > SUN_DIFF_MAX:
            ideal_limit = max(ideal_limit - SUN_DIFF_DECREASE, MIN_LIMIT)

        # Only send request if ideal limit changed
        if ideal_limit != current_limit:
            send_limit_request(ideal_limit)

        previous_power = inverter_power
        time.sleep(SLEEP_TIME)

    except Exception as e:
        print("Error:", e)
        time.sleep(SLEEP_TIME)
