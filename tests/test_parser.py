"""Unit tests for the TBD Smartshunt telemetry parser."""

import unittest
import sys
import os
import struct
import importlib.util

# Load parser directly without triggering __init__.py homeassistant dependencies
parser_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "custom_components", "tbd_smartshunt", "parser.py")
)
module_name = "custom_components.tbd_smartshunt.parser"
spec = importlib.util.spec_from_file_location(module_name, parser_path)
tbd_parser = importlib.util.module_from_spec(spec)
sys.modules[module_name] = tbd_parser
spec.loader.exec_module(tbd_parser)

parse_state_of_charge = tbd_parser.parse_state_of_charge


class TestTbdShuntParser(unittest.TestCase):
    """Test suite for parsing TBD Smartshunt telemetry payloads."""

    def test_parse_screenshot_payload(self):
        """Test parsing the exact 44-byte payload from Screenshot 163844."""
        hex_data = (
            "64-00-00-00-C8-75-51-41-55-2B-BA-40-CF-1D-96-42-"
            "00-00-00-00-FF-FF-FF-FF-9F-2A-00-00-AB-40-A4-3C-"
            "00-00-00-00-00-00-00-00-00-00-00-00"
        )
        raw_bytes = bytes.fromhex(hex_data.replace("-", ""))

        data = parse_state_of_charge(raw_bytes)
        self.assertIsNotNone(data)
        self.assertEqual(data.soc, 100)
        self.assertAlmostEqual(data.voltage, 13.09, places=2)
        self.assertAlmostEqual(data.current, 5.82, places=2)
        self.assertAlmostEqual(data.power, 75.06, places=2)
        self.assertAlmostEqual(data.consumed_ah, 0.02, places=2)
        self.assertIsNone(data.time_remaining_minutes)  # 0xFFFFFFFF = Infinite
        self.assertEqual(data.uptime_seconds, 10911)

    def test_short_payload_returns_none(self):
        """Test that truncated or malformed payloads safely return None."""
        self.assertIsNone(parse_state_of_charge(b""))
        self.assertIsNone(parse_state_of_charge(b"\x00" * 16))

    def test_discharging_payload(self):
        """Test parsing when battery is discharging with finite time remaining."""
        # Format: SoC(I), Voltage(f), Current(f), Power(f), Aux(f), TimeRem(I), Uptime(I), ConsumedAh(f)
        payload = struct.pack(
            "<IffffIIf",
            85,        # SoC
            12.8,      # Voltage
            -10.5,     # Current (discharging)
            -134.4,    # Power
            0.0,       # Aux
            360,       # Time remaining (min)
            5000,      # Uptime
            15.4,      # Consumed Ah
        ) + (b"\x00" * 12)

        data = parse_state_of_charge(payload)
        self.assertIsNotNone(data)
        self.assertEqual(data.soc, 85)
        self.assertAlmostEqual(data.voltage, 12.8, places=1)
        self.assertAlmostEqual(data.current, -10.5, places=1)
        self.assertAlmostEqual(data.power, -134.4, places=1)
        self.assertEqual(data.time_remaining_minutes, 360)
        self.assertAlmostEqual(data.consumed_ah, 15.4, places=1)


if __name__ == "__main__":
    unittest.main()
