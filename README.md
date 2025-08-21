# Solarman-voltage-control
Dynamic Solar Inverter Export Control

This Python script dynamically adjusts the export power limit of a Solarman PV inverter to optimize solar generation while keeping grid voltage within safe limits.

Features

Dynamic Adjustment: Automatically increases or decreases inverter export limit based on actual inverter power and grid voltage.

Voltage Safety: Keeps grid voltage below 267 V and reduces power if voltage exceeds 269 V.

Sunlight Check: Avoids increasing export limit if there isn’t enough sunlight (difference between set limit and actual inverter power is too large).

Increment/Decrement Control:

Increases in steps of 100 W.

Decreases in steps of 200 W.

Reduces by 300 W if sunlight is insufficient.

Duplicate Request Prevention: Only sends update requests if the new ideal limit differs from the current one.

Maximum Limit: Ensures the export limit does not exceed 5000 W.

Requirements

Python 3.x

pysolarmanv5 package (pip install pysolarmanv5)

requests package (pip install requests)

Root or appropriate network access to communicate with your inverter.

Setup

Clone the repository or copy the script to your machine.

Update the following constants with your inverter and Solarman account details:

LOGGER_IP = "10.10.100.254"
LOGGER_SN = 2331491601
SOLARMAN_ACCESS_TOKEN = "YOUR_BEARER_TOKEN_HERE"
DEVICE_SN = "2203274322"
DEVICE_ID = "217113889"
GATEWAY_ID = 212907181
GATEWAY_SN = "2331491601"


Adjust the voltage and increment/decrement constants if needed:

VOLTAGE_LOWER = 267
VOLTAGE_UPPER = 269
INCREMENT = 100
DECREMENT = 200
MAX_LIMIT = 5000
MIN_LIMIT = 1000
SUN_THRESHOLD = 500
SUN_DIFF_MAX = 600
SUN_DIFF_DECREASE = 300

Usage

Run the script using:

python control.py


The script will:

Read the current grid voltage (Reg 150).

Read the current inverter export limit (Reg 53) and actual inverter power (Reg 136).

Calculate the ideal export limit based on voltage and power conditions.

Send a Solarman request to update the limit only if necessary.

Repeat every 5 seconds.

Notes

Ensure you keep your Solarman access token up to date; tokens may expire.

The script is safe to run continuously, but monitor logs during initial operation.

Adjust constants carefully to match your system’s specifications and local regulations.

License

This project is provided for personal use and experimentation. Use at your own risk.