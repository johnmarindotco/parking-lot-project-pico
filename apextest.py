# test_apex.py – Minimal test to verify DAL + APEX connectivity from the Pico

from Net import Net
from DAL import DAL
from secrets import WIFI_SSID, WIFI_PASSWORD
from Log import *
import time

def main():
    Log.i("Starting APEX connectivity test...")

    net = Net()
    dal = DAL(net)

    # Connect to Wi-Fi
    Log.i(f"Connecting to WiFi SSID: {WIFI_SSID}")
    net.connect(WIFI_SSID, WIFI_PASSWORD)
    Log.i("WiFi connected!")

    # Optional: test GET endpoints
    try:
        Log.i("Testing GET /garages ...")
        garages = dal.get_garages()
        Log.i(f"Garages JSON: {garages}")
    except Exception as e:
        Log.e(f"Error retrieving garages: {e}")

    try:
        Log.i("Testing GET /levels ...")
        levels = dal.get_levels()
        Log.i(f"Levels JSON: {levels}")
    except Exception as e:
        Log.e(f"Error retrieving levels: {e}")

    # Determine database level_id for Garage A Level 1
    level1_id = None
    try:
        if levels and "items" in levels:
            for item in levels["items"]:
                if item.get("garage_id") == 1 and item.get("level_number") == 1:
                    level1_id = item.get("level_id")
                    break
        if level1_id is None:
            level1_id = 101  # fallback
        Log.i(f"Using DB level_id={level1_id} for Garage A Level 1")
    except Exception as e:
        Log.e(f"Error determining level_id: {e}")
        level1_id = 101

    time.sleep(1)

    # Test POST /events
    try:
        Log.i("Sending test entry event...")
        resp = dal.send_sensor_event(level1_id, "entry")
        Log.i(f"POST response: {resp}")
    except Exception as e:
        Log.e(f"Error sending POST event: {e}")

    Log.i("APEX test complete.")

if __name__ == "__main__":
    main()
