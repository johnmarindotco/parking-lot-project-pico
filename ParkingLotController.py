"""
ParkingLotController - Smart Parking Assistant controller for Pico

Features:
- 2 levels (L1, L2)
- Entry / Exit sensors per level
- Immediate occupancy (for debugging) logged to terminal
- Validated occupancy (15s parked rule) shown on LCD as "X Avail"
- Light strip: green when availability, flashing red when garage is full
- Uses StateModel with two states: NORMAL and FULL_ALERT
"""

import time
from time import ticks_ms, ticks_diff

from Log import *
from StateModel import StateModel
from Displays import LCDDisplay
from Sensors import DigitalSensor
from LightStrip import LightStrip
from Lights import RED, GREEN
from Button import Button
from Net import Net
from DAL import DAL
from secrets import WIFI_SSID, WIFI_PASSWORD

# State definitions
NORMAL = 0
FULL_ALERT = 1


class ParkingLotController:
    def __init__(self):
        # ----- Display -----
        self._display = LCDDisplay(sda=0, scl=1)

        # ----- Config -----
        self._garage_name = "Garage A"

        # ----- Light strip (overall garage indicator) -----
        self._lightstrip = LightStrip(pin=17, numleds=8)
        self._garage_full = False
        self._flash_on = False
        self._last_flash_ms = 0

        # ----- Raw sensor state tracking -----
        self._L1_entry_tripped = False
        self._L1_exit_tripped = False
        self._L2_entry_tripped = False
        self._L2_exit_tripped = False

        # ----- Immediate occupancy (for debug / logs only) -----
        self._L1_occupancy = 0
        self._L2_occupancy = 0

        # Capacity per level
        self._L1_capacity = 10
        self._L2_capacity = 10

        # ---- Map Pico Levels to Database Level IDs ----
        # These MUST match the level_id values from /parking/levels
        self._L1_level_id_db = 101  # Garage A, Level 1
        self._L2_level_id_db = 102  # Garage A, Level 2

        # ----- Cooldown configuration (in milliseconds) -----
        # Ignore repeated trips on the same sensor within this window
        self._sensor_cooldown_ms = 1000  # 1 second

        # Last time (in ms) that each sensor produced a *counted* event
        self._last_L1_entry_ms = None
        self._last_L1_exit_ms = None
        self._last_L2_entry_ms = None
        self._last_L2_exit_ms = None

        # ----- Validated occupancy (LCD uses this) -----
        # These only change after 15s "parked" confirmation or an exit
        self._L1_valid_occupancy = 0
        self._L2_valid_occupancy = 0

        # Pending entries (waiting 15 seconds to count as "parked")
        self._entry_confirm_delay_ms = 5000  # 5 seconds (was 15; adjust as desired)
        self._L1_pending_entry = False
        self._L2_pending_entry = False
        self._L1_pending_start_ms = None
        self._L2_pending_start_ms = None

        # ----- State Model -----
        # Two states: NORMAL and FULL_ALERT
        self._model = StateModel(2, self, debug=True)

        # Custom events to move between states
        self._model.addCustomEvent("garage_full")
        self._model.addCustomEvent("garage_not_full")

        # State transitions:
        # NORMAL -> FULL_ALERT when garage becomes full
        self._model.addTransition(NORMAL, ["garage_full"], FULL_ALERT)
        # FULL_ALERT -> NORMAL when garage is no longer full
        self._model.addTransition(FULL_ALERT, ["garage_not_full"], NORMAL)

        # ----- Sensors -----
        # Level 1 sensors
        self._entrySensor_L1 = DigitalSensor(
            pin=6, name="L1_entry", lowActive=False, handler=None
        )
        self._exitSensor_L1 = DigitalSensor(
            pin=5, name="L1_exit", lowActive=False, handler=None
        )

        # Level 2 sensors
        self._entrySensor_L2 = DigitalSensor(
            pin=21, name="L2_entry", lowActive=False, handler=None
        )
        self._exitSensor_L2 = DigitalSensor(
            pin=22, name="L2_exit", lowActive=False, handler=None
        )

        self._model.addSensor(self._entrySensor_L1)
        self._model.addSensor(self._exitSensor_L1)
        self._model.addSensor(self._entrySensor_L2)
        self._model.addSensor(self._exitSensor_L2)

        # ----- Reset button -----
        self._reset_button = Button(pin=11, name="reset", handler=None)
        self._model.addButton(self._reset_button)

        # ----- Networking / Database (Oracle APEX) -----
        self._net = Net()
        self._dal = DAL(self._net)

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    def _write_line(self, row: int, text):
        """
        Safely write a single line to the LCD.
        Assumes a 16-char wide display. Truncates or pads as needed.
        Works without relying on str.ljust (not available in some MicroPython builds).
        """
        max_width = 16  # adjust if your LCD is wider

        # Ensure it's a string
        text = str(text)

        # Truncate if too long
        if len(text) > max_width:
            text = text[:max_width]
        # Pad with spaces if too short
        elif len(text) < max_width:
            text = text + (" " * (max_width - len(text)))

        self._display.showText(text, row, 0)

    def _cooldown_ok(self, last_ts, now_ms):
        """
        Return True if enough time has passed since last_ts for this sensor
        to be considered 'ready' again.
        """
        if last_ts is None:
            return True
        return ticks_diff(now_ms, last_ts) > self._sensor_cooldown_ms

    def _update_garage_lights(self):
        """
        Update the light strip based on validated occupancy.
        Garage is considered FULL when BOTH levels are at capacity.
        Also drives state transitions via custom events.
        """
        full = (
            self._L1_valid_occupancy >= self._L1_capacity
            and self._L2_valid_occupancy >= self._L2_capacity
        )

        # If state didn't change, no need to touch LEDs or states
        if full == self._garage_full:
            return

        self._garage_full = full

        if full:
            Log.i("Garage is FULL -> triggering FULL_ALERT state")
            # Move NORMAL -> FULL_ALERT
            self._model.processEvent("garage_full")
            # Start flashing red
            self._flash_on = True
            self._lightstrip.setColor(RED)
        else:
            Log.i("Garage is NOT full -> triggering NORMAL state")
            # Move FULL_ALERT -> NORMAL
            self._model.processEvent("garage_not_full")
            # Solid green when not full
            self._flash_on = False
            self._lightstrip.setColor(GREEN)

        # Note: flashing behavior is handled in stateDo when in FULL_ALERT

    def _show_validated_occupancy(self):
        """
        Show the validated (15s-confirmed) available spots for both levels.
        """
        l1_avail = self._L1_capacity - self._L1_valid_occupancy
        l2_avail = self._L2_capacity - self._L2_valid_occupancy

        self._display.clear()
        self._display.showText(f"L1: {l1_avail} Avail", 0, 0)
        self._display.showText(f"L2: {l2_avail} Avail", 1, 0)

        # Sync lights and state with the new validated values
        self._update_garage_lights()

    def _record_sensor_event(self, level_id, sensor_type):
        """
        Send a single sensor event to the Oracle APEX backend.

        level_id: DB level_id (e.g., 101, 102)
        sensor_type: "entry" or "exit"
        """
        if not hasattr(self, "_dal") or self._dal is None:
            Log.e("DAL is not initialized; skipping sensor event")
            return

        Log.i(
            f"Recording sensor event -> level_id={level_id}, "
            f"sensor_type={sensor_type}"
        )

        try:
            resp = self._dal.send_sensor_event(level_id, sensor_type)
            Log.i(f"APEX event OK: {resp}")
        except Exception as e:
            # Never crash the controller because the network is down
            Log.e(f"Failed to send sensor event to APEX: {e}")

    def _show_startup_sequence(self):
        """
        Show a little intro on the LCD before starting the state model.
        Keeps messages within 16 characters per line.
        """
        # 1) Greeting
        self._display.clear()
        self._write_line(0, " Hello from")
        self._write_line(1, f" {self._garage_name}")
        time.sleep(2)

        # 2) Current time (HH:MM)
        now = time.localtime()
        hh = now[3]
        mm = now[4]

        self._display.clear()
        self._write_line(0, " Time:")
        self._write_line(1, f"   {hh:02d}:{mm:02d}")
        time.sleep(2)

        # 3) Garage open message
        self._display.clear()
        self._write_line(0, " Garage is now")
        self._write_line(1, "   OPEN!")
        time.sleep(2)

        # 4) Transition to normal availability view
        self._show_validated_occupancy()

    def _reset_garage(self):
        """
        Reset occupancy, pending entries, and lights back to initial state.
        """
        Log.i("Reset button pressed: resetting garage state")

        # Clear immediate and validated occupancy
        self._L1_occupancy = 0
        self._L2_occupancy = 0
        self._L1_valid_occupancy = 0
        self._L2_valid_occupancy = 0

        # Clear pending entries
        self._L1_pending_entry = False
        self._L1_pending_start_ms = None
        self._L2_pending_entry = False
        self._L2_pending_start_ms = None

        # Clear tripped flags
        self._L1_entry_tripped = False
        self._L1_exit_tripped = False
        self._L2_entry_tripped = False
        self._L2_exit_tripped = False

        # Force a "not full" transition via the usual logic
        # by pretending we WERE full and letting _update_garage_lights fix it.
        self._garage_full = True
        self._flash_on = False

        # This will:
        # - Show "L1: 10 Avail / L2: 10 Avail"
        # - Call _update_garage_lights()
        # - Trigger garage_not_full event and go to NORMAL state if needed
        self._show_validated_occupancy()

    # -------------------------------------------------------------------------
    # StateModel required callbacks
    # -------------------------------------------------------------------------
    def stateEntered(self, state, event):
        """
        Entry actions for a state (called once when entering the state).
        """
        Log.d(f"State {state} entered on event {event}")

        # For both states, we want the LCD (and lights) to reflect current status
        if state in (NORMAL, FULL_ALERT):
            self._show_validated_occupancy()

    def stateLeft(self, state, event):
        """
        Exit actions for a state.
        """
        Log.d(f"State {state} exited on event {event}")

    def stateEvent(self, state, event) -> bool:
        """
        Handle events without changing state.
        This is where we respond to sensor trip/untrip events.
        """
        now_ms = ticks_ms()

        # Global trace so we can see everything coming in
        Log.d(f"stateEvent: state={state}, event={event}")

        # ---------- Reset Button ----------
        if event == "reset_press":
            self._reset_garage()
            return True

        # ---------- Level 1 Sensors ----------
        if event == "L1_entry_trip":
            # Only start a NEW pending entry if:
            # - sensor wasn't already marked tripped
            # - there's no pending entry already in progress
            # - cooldown window has passed
            if (
                not self._L1_entry_tripped
                and not self._L1_pending_entry
                and self._cooldown_ok(self._last_L1_entry_ms, now_ms)
            ):
                self._L1_entry_tripped = True
                self._last_L1_entry_ms = now_ms

                # Start pending entry for validated count
                self._L1_pending_entry = True
                self._L1_pending_start_ms = now_ms

                # Log this raw event to the backend (DB level id)
                self._record_sensor_event(
                    level_id=self._L1_level_id_db,
                    sensor_type="entry",
                )

                # IMMEDIATE count (for terminal logging) – exactly once per pending entry
                if self._L1_occupancy < self._L1_capacity:
                    self._L1_occupancy += 1
                Log.i(
                    f"L1 immediate occupancy: "
                    f"{self._L1_occupancy}/{self._L1_capacity}"
                )
            return True

        if event == "L1_entry_untrip":
            if self._L1_entry_tripped:
                self._L1_entry_tripped = False
            return True

        if event == "L1_exit_trip":
            if (
                not self._L1_exit_tripped
                and self._cooldown_ok(self._last_L1_exit_ms, now_ms)
            ):
                self._L1_exit_tripped = True
                self._last_L1_exit_ms = now_ms

                # Log this raw event to the backend
                self._record_sensor_event(
                    level_id=self._L1_level_id_db,
                    sensor_type="exit",
                )

                # IMMEDIATE count (for terminal logging)
                if self._L1_occupancy > 0:
                    self._L1_occupancy -= 1
                Log.i(
                    f"L1 immediate occupancy: "
                    f"{self._L1_occupancy}/{self._L1_capacity}"
                )

                # If an entry was still pending, cancel it (pass-through)
                self._L1_pending_entry = False
                self._L1_pending_start_ms = None

                # For validated count, a car exiting frees a spot immediately
                if self._L1_valid_occupancy > 0:
                    self._L1_valid_occupancy -= 1
                    self._show_validated_occupancy()
            return True

        if event == "L1_exit_untrip":
            if self._L1_exit_tripped:
                self._L1_exit_tripped = False
            return True

        # ---------- Level 2 Sensors ----------
        if event == "L2_entry_trip":
            if (
                not self._L2_entry_tripped
                and not self._L2_pending_entry
                and self._cooldown_ok(self._last_L2_entry_ms, now_ms)
            ):
                self._L2_entry_tripped = True
                self._last_L2_entry_ms = now_ms

                # Start pending entry
                self._L2_pending_entry = True
                self._L2_pending_start_ms = now_ms

                # Log this raw event to the backend
                self._record_sensor_event(
                    level_id=self._L2_level_id_db,
                    sensor_type="entry",
                )

                # IMMEDIATE count – only once per pending entry
                if self._L2_occupancy < self._L2_capacity:
                    self._L2_occupancy += 1
                Log.i(
                    f"L2 immediate occupancy: "
                    f"{self._L2_occupancy}/{self._L2_capacity}"
                )
            return True

        if event == "L2_entry_untrip":
            if self._L2_entry_tripped:
                self._L2_entry_tripped = False
            return True

        if event == "L2_exit_trip":
            if (
                not self._L2_exit_tripped
                and self._cooldown_ok(self._last_L2_exit_ms, now_ms)
            ):
                self._L2_exit_tripped = True
                self._last_L2_exit_ms = now_ms

                # Log this raw event to the backend
                self._record_sensor_event(
                    level_id=self._L2_level_id_db,
                    sensor_type="exit",
                )

                # IMMEDIATE count (for terminal logging)
                if self._L2_occupancy > 0:
                    self._L2_occupancy -= 1
                Log.i(
                    f"L2 immediate occupancy: "
                    f"{self._L2_occupancy}/{self._L2_capacity}"
                )

                # Cancel pending entry if any (pass-through)
                self._L2_pending_entry = False
                self._L2_pending_start_ms = None

                # Validated count: car left
                if self._L2_valid_occupancy > 0:
                    self._L2_valid_occupancy -= 1
                    self._show_validated_occupancy()
            return True

        if event == "L2_exit_untrip":
            if self._L2_exit_tripped:
                self._L2_exit_tripped = False
            return True

        # All other events are not handled here
        return False

    def stateDo(self, state):
        """
        Called repeatedly while in a state.
        We use this to handle the 15s "parked" confirmation and flashing lights.
        """
        now_ms = ticks_ms()

        # ----- Check pending entries for Level 1 -----
        if self._L1_pending_entry and self._L1_pending_start_ms is not None:
            if ticks_diff(now_ms, self._L1_pending_start_ms) >= self._entry_confirm_delay_ms:
                # Time has passed without an exit -> parked car
                self._L1_pending_entry = False
                self._L1_pending_start_ms = None

                if self._L1_valid_occupancy < self._L1_capacity:
                    self._L1_valid_occupancy += 1
                    Log.i(
                        f"L1 VALIDATED occupancy: "
                        f"{self._L1_valid_occupancy}/{self._L1_capacity}"
                    )
                    self._show_validated_occupancy()

        # ----- Check pending entries for Level 2 -----
        if self._L2_pending_entry and self._L2_pending_start_ms is not None:
            if ticks_diff(now_ms, self._L2_pending_start_ms) >= self._entry_confirm_delay_ms:
                # Time has passed without an exit -> parked car
                self._L2_pending_entry = False
                self._L2_pending_start_ms = None

                if self._L2_valid_occupancy < self._L2_capacity:
                    self._L2_valid_occupancy += 1
                    Log.i(
                        f"L2 VALIDATED occupancy: "
                        f"{self._L2_valid_occupancy}/{self._L2_capacity}"
                    )
                    self._show_validated_occupancy()

        # ----- Flash lights if garage is full and we're in FULL_ALERT state -----
        if self._garage_full and state == FULL_ALERT:
            # Flash every 500 ms between bright and dim red
            if ticks_diff(now_ms, self._last_flash_ms) >= 500:
                self._last_flash_ms = now_ms
                self._flash_on = not self._flash_on

                if self._flash_on:
                    self._lightstrip.setColor(RED)
                else:
                    # Dimmer red (warning pulse)
                    self._lightstrip.setColor((80, 0, 0))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def run(self):
        """
        Start the state model.
        """
        # Bring up Wi-Fi so we can talk to Oracle APEX
        try:
            self._net.connect(WIFI_SSID, WIFI_PASSWORD)
        except Exception as e:
            Log.e(f"Wi-Fi connection failed: {e}")

        self._show_startup_sequence()
        self._model.run()

    def stop(self):
        """
        Stop the state model.
        """
        self._model.stop()


# Optional standalone test (used only if running this file directly)
if __name__ == "__main__":
    c = ParkingLotController()
    try:
        c.run()
    except KeyboardInterrupt:
        c.stop()
