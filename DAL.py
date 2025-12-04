# DAL.py – Data Access Layer for Smart Parking (Oracle APEX)

from Net import Net
from Log import *

# Base URL for your parking REST module in Oracle APEX
BASEURL = "https://oracleapex.com/ords/jarias32/parking/"

# Individual endpoints
GARAGES_URL = f"{BASEURL}garages"
LEVELS_URL  = f"{BASEURL}levels"
EVENTS_URL  = f"{BASEURL}events"   # POST here with level_id + sensor_type


class DAL:
    """
    Minimal DAL for the Smart Parking project.
    - send_sensor_event: POST raw sensor events to /parking/events
    - get_garages / get_levels: optional helpers for debugging/inspection
    """

    def __init__(self, net: Net | None = None):
        # Reuse an existing Net instance if provided, otherwise create our own
        self._net = net if net is not None else Net()

    # ------------------------------------------------------------------
    # POST /parking/events
    # ------------------------------------------------------------------
    def send_sensor_event(self, level_id: int, sensor_type: str):
        """
        Send a single sensor event to the Oracle APEX backend.

        level_id: numeric level id (1, 2, ...)
        sensor_type: "entry" or "exit"
        """

        if sensor_type not in ("entry", "exit"):
            raise ValueError("sensor_type must be 'entry' or 'exit'")

        payload = {
            "level_id": level_id,
            "sensor_type": sensor_type,
        }

        Log.i(f"DAL: POST {EVENTS_URL} payload={payload}")
        data = self._net.postJson(EVENTS_URL, payload)
        Log.i(f"DAL: send_sensor_event response = {data}")
        return data

    # ------------------------------------------------------------------
    # Optional helpers (GET) – useful for quick tests from the Pico
    # ------------------------------------------------------------------
    def get_garages(self):
        """
        GET /parking/garages
        Returns the list of garages from APEX.
        """
        Log.i(f"DAL: GET {GARAGES_URL}")
        data = self._net.getJson(GARAGES_URL)
        Log.i(f"DAL: get_garages response = {data}")
        return data

    def get_levels(self):
        """
        GET /parking/levels
        Returns the list of levels from APEX.
        """
        Log.i(f"DAL: GET {LEVELS_URL}")
        data = self._net.getJson(LEVELS_URL)
        Log.i(f"DAL: get_levels response = {data}")
        return data
