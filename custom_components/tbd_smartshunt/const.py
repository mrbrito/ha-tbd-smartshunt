"""Constants for the TBD Smartshunt integration."""

DOMAIN = "tbd_smartshunt"

# BLE Services and Characteristics
SERVICE_UUID = "18424398-7cbc-11e9-8f9e-2a86e4085a59"

# 44-byte State of Charge characteristic (NOTIFY, READ, WRITE)
CHAR_STATE_OF_CHARGE = "2d86686a-53dc-25b3-0c4a-f0e10c8dee20"

# Additional characteristics identified from DaYan shunt hardware
CHAR_HISTORY = "5a87b4ef-3bfa-76a8-e642-92933c31434f"
CHAR_SETTING = "15005991-b131-3396-014c-664c9867b917"
CHAR_DATA = "16005991-b131-3396-014c-664c9867b917"
CHAR_PIN = "16005991-b131-3396-014c-664c9867b918"

# Configuration options
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 15  # seconds
MIN_POLL_INTERVAL = 5
MAX_POLL_INTERVAL = 300
