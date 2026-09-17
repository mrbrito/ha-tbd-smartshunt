import sys
from unittest.mock import MagicMock
sys.modules['homeassistant'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.bluetooth'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()

import asyncio
import logging
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed
logging.basicConfig(level=logging.INFO)

class DummyCoordinator:
    def __init__(self, *args, **kwargs):
        self.hass = args[0]
    def __class_getitem__(cls, item):
        return cls
sys.modules['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator = DummyCoordinator
from custom_components.tbd_smartshunt.coordinator import TbdSmartshuntCoordinator

class MockBLEDevice:
    def __init__(self, address, source, is_local=False):
        self.address = address
        self.details = {"source": source}
        if is_local:
            self.details["path"] = "/org/bluez/hci0/dev_FB_FB_FB_FF_0D_74"

class MockHA:
    def __init__(self):
        self.data = {}

async def test_bonding_lifecycle():
    hass = MockHA()
    
    class DummyCoordinator:
        def __init__(self, *args, **kwargs):
            pass
    import custom_components.tbd_smartshunt.coordinator as coord_module
    coord_module.DataUpdateCoordinator = DummyCoordinator
    
    coord = TbdSmartshuntCoordinator(hass, "FB:FB:FB:FF:0D:74", "Test Shunt")
    
    # Create mock devices: one proxy and one local BlueZ adapter
    proxy_device = MockBLEDevice("FB:FB:FB:FF:0D:74", "AC:27:6E:83:2E:42")
    local_device = MockBLEDevice("FB:FB:FB:FF:0D:74", "hci0", is_local=True)
    
    # We mock async_scanner_devices_by_address to return both
    with patch("custom_components.tbd_smartshunt.coordinator.bluetooth.async_scanner_devices_by_address", 
               return_value=[proxy_device, local_device]):
        
        # We also need to mock establish_connection and PairingReader.read
        with patch("custom_components.tbd_smartshunt.coordinator.establish_connection", new_callable=AsyncMock) as mock_connect:
            mock_client = MagicMock()
            mock_client.disconnect = AsyncMock()
            mock_client.services.get_service.return_value = MagicMock(characteristics=[MagicMock(uuid="2d86686a-53dc-25b3-0c4a-f0e10c8dee20")])
            mock_client._backend = MagicMock()
            mock_client._backend.__class__.__name__ = "BleakClientBlueZDBus"
            mock_connect.return_value = mock_client
            
            with patch("custom_components.tbd_smartshunt.coordinator.PairingReader.read", new_callable=AsyncMock) as mock_read:
                import struct
                mock_read.return_value = struct.pack("<Ifff", 100, 12.5, 1.5, 18.75) + (b'\x00' * 28)
                
                try:
                    data = await coord.async_read_data()
                    print(f"SUCCESS: Read data SOC={data.soc} V={data.voltage}")
                    
                    called_device = mock_connect.call_args[0][1]
                    assert called_device.details.get("source") == "hci0", "Failed to prioritize local BlueZ adapter!"
                    print("SUCCESS: Validated server-side bonding priority (local BlueZ adapter selected over ESPHome proxy)")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"FAILED: {e}")
                    raise

if __name__ == "__main__":
    asyncio.run(test_bonding_lifecycle())
