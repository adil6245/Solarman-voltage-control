import requests

# URL to your script (use the "Raw" link from GitHub)
URL = "https://raw.githubusercontent.com/adil6245/Solarman-voltage-control/refs/heads/master/control.py"

print("Fetching latest script from GitHub...")
response = requests.get(URL)
if response.status_code == 200:
    code = response.text
    # Option A: directly execute from memory
    exec(code, globals())
    
    # Option B (safer): save then run
    # with open("latest_script.py", "w") as f:
    #     f.write(code)
    # runpy.run_path("latest_script.py")
else:
    print("Failed to fetch script:", response.status_code)
