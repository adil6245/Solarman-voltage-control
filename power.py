from pysolarmanv5 import PySolarmanV5
import time

LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601

GRID_VOLTAGE_REG = 150
CURRENT_POWER_REG = 136
CURRENT_EXPORT_REG = 134
CURRENT_UTL_REG = 176
EXPORT_LIMIT_REG = 53

# Candidate registers for inverter power  178, 185 ,167
candidate_regs = [134, 136, 176]

# Create client
client = PySolarmanV5(LOGGER_IP, LOGGER_SN)

def read_voltage(client):
    raw = client.read_holding_registers(150, 1)[0]
    return raw / 10.0

def read_signed_register(client, reg):
    """Read a single 16-bit signed register."""
    raw = client.read_holding_registers(reg, 1)[0]
    if raw > 32767:
        raw -= 65536
    return raw

while True:
    try:
        # print("Inverter Power Candidate Registers:")
        # for reg in candidate_regs:
        #     val = read_signed_register(client, reg)
        #     print(f"Register {reg}: {val} W")

        grid_voltage = read_voltage(client)
        current_limit = read_signed_register(client, 53)
        inverter_power = read_signed_register(client, 136)
        current_export = read_signed_register(client, 134)
        current_utl = read_signed_register(client, 176)

        print(f"Grid Voltage: {grid_voltage:.1f} V | Inverter Power: {inverter_power} W | Current Limit: {current_limit} W | Current Export: {current_export} W | Current Util: {current_utl} W")
        print("-" * 40)
        time.sleep(2)
    except Exception as e:
        print("Error:", e)
        break
