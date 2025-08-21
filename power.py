from pysolarmanv5 import PySolarmanV5
import time

LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601

# Registers
GRID_VOLTAGE_REG = 150
CURRENT_POWER_REG = 136
EXPORT_LIMIT_REG = 53

# Create client
client = PySolarmanV5(LOGGER_IP, LOGGER_SN)

while True:
    try:
        # Read values
        raw_voltage = client.read_holding_registers(GRID_VOLTAGE_REG, 1)[0]
        voltage = raw_voltage / 10.0

        current_power = client.read_holding_registers(CURRENT_POWER_REG, 1)[0]
        export_limit = client.read_holding_registers(EXPORT_LIMIT_REG, 1)[0]

        # Print log
        print(f"Grid Voltage: {voltage:.1f} V | Inverter Power: {current_power} W | Export Limit: {export_limit} W")

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        break
