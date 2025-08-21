from pysolarmanv5 import PySolarmanV5
import time

LOGGER_IP = "192.168.18.40"
LOGGER_SN = 2331491601

client = PySolarmanV5(LOGGER_IP, LOGGER_SN)

while True:
    try:
        raw = client.read_holding_registers(150, 1)[0]
        voltage = raw / 10.0
        print(f"Grid Voltage: {voltage:.1f} V")
        time.sleep(2)
    except Exception as e:
        print("Error:", e)
        break