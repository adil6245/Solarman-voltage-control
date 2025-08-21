import time
import requests
from pysolarmanv5 import PySolarmanV5

# Solarman / inverter info
LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601
ACCESS_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX25hbWUiOiIwX2FkaWw2MjQ1QGdtYWlsLmNvbV8yIiwibW9kaWZ5X3Bhc3N3b3JkIjoxLCJzY29wZSI6WyJhbGwiXSwiZGV0YWlsIjp7Im9yZ2FuaXphdGlvbklkIjowLCJ0b3BHcm91cElkIjpudWxsLCJncm91cElkIjpudWxsLCJyb2xlSWQiOi0xLCJ1c2VySWQiOjkzODc0MywidmVyc2lvbiI6MTAwMCwiaWRlbnRpZmllciI6ImFkaWw2MjQ1QGdtYWlsLmNvbSIsImlkZW50aXR5VHlwZSI6MiwibWRjIjoiRk9SRUlHTl8xIiwiYXBwSWQiOm51bGx9LCJleHAiOjE3NjA5NDg1OTQsIm1kYyI6IkZPUkVJR05fMSIsImF1dGhvcml0aWVzIjpbImFsbCJdLCJqdGkiOiJlOTkyNjllOS1kMmM0LTQzYTctYjhhZS1iZTAyMmE4NWQxNjMiLCJjbGllbnRfaWQiOiJ0ZXN0In0.VVHUOls_VgG88a8BMfPhqC9FVEzGuW9ARqiS7YEyO7703w1uy9tD76ehqx3UKfA3l2fe_04oUCe66WDBlqHuA7Vt56W0DFMDrv6zoTi3PdMz_7aFgue0c5jiCHFtyjKycx9PnMPt2kZlpBfIJ0nVP0YwFMoxSGevg4Eh4vHUyKoHKBzjFL9jfbvSpWI6axCtpowQ_eu6AByL3Oaa9MCABt9xI89Zu1VBgorCm3vg_YiY8pbIAVSAsqtNjnBVrvdGPKK2SRNMbOAstzSbmKwrVJd3fBxXvItf6QFjVPoQJBP9kylyB7WEe2U4z4NEULt1IVuSFnStvMXDPCn7to0ZhQ"
DEVICE_ID = "217113889"

# Initialize Modbus client
client = PySolarmanV5(LOGGER_IP, LOGGER_SN)

# Read current export limit from register 53
export_limit = client.read_holding_registers(53, 1)[0]
last_requested_limit = export_limit  # Track last requested limit

# Helper to read grid voltage
def read_voltage():
    raw = client.read_holding_registers(150, 1)[0]
    return raw / 10.0

# Helper to read inverter power (current generation)
def read_inverter_power():
    raw = client.read_holding_registers(136, 1)[0]  # Reg 136 = actual generation
    return raw

# Helper to send new export limit to Solarman cloud
def set_export_limit(limit_w):
    payload = {
        "product": "0_5407_1",
        "deviceSn": "2203274322",
        "deviceId": DEVICE_ID,
        "gatewayId": 212907181,
        "gatewaySn": "2331491601",
        "code": "s_cnjgzms1",
        "codeGroup": "G1101",
        "operationType": 5,
        "extendWeb": f'{{"inputParam":{{"00F4":{{"v":"0"}},"00F8-1":{{"v":"0000000"}},"00F5":{{"v":"2100"}},"0035":{{"v":{limit_w}}},"00F3":{{"v":"1"}},"00CE":{{"v":"20"}},"00F8":{{"v":"0"}}}}}}',
        "orderTimeout": 60
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    r = requests.post("https://globaldc-pro.solarmanpv.com/order-s/order/action/control/send", json=payload, headers=headers)
    return r.status_code, r.text

# Control loop
previous_power = read_inverter_power()

while True:
    try:
        # Refresh current limit from inverter
        export_limit = client.read_holding_registers(53, 1)[0]

        voltage = read_voltage()
        inverter_power = read_inverter_power()
        print(f"Voltage: {voltage:.1f} V | Inverter Power: {inverter_power} W | Current Limit: {export_limit} W")

        new_desired_limit = export_limit

        # Increase limit if voltage safe and power is rising
        if voltage < 267 and inverter_power > previous_power:
            new_desired_limit += 100

        # Decrease limit if voltage too high
        elif voltage > 269:
            new_desired_limit -= 200

        # Only send request if the desired limit actually changed
        if new_desired_limit != last_requested_limit:
            print(f"Updating export limit to {new_desired_limit} W")
            set_export_limit(new_desired_limit)
            last_requested_limit = new_desired_limit

        previous_power = inverter_power
        time.sleep(10)  # check every 10 seconds
    except Exception as e:
        print("Error:", e)
        break
