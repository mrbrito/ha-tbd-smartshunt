# TBD Smartshunt Home Assistant Integration

Custom Home Assistant integration for the **TBD Smartshunt** (also known as DaYan DA1 / FE-Shunt 500A Battery Monitor).

This integration interfaces with the shunt over Bluetooth Low Energy (BLE). It works with both **local Bluetooth adapters** and **ESPHome Bluetooth Proxies**, allowing you to monitor your battery bank anywhere in your home or RV.

---

## Features

- **Multi-device support**: Connect to multiple shunts simultaneously (e.g. House Battery and Auxiliary/Starter Battery).
- **Auto-Discovery**: Automatically discovers nearby `TBDsmartshunt-*` devices via Bluetooth advertisements or ESPHome proxies.
- **Rich Telemetry Entities**:
  - **State of Charge (SoC)** (`%`)
  - **Battery Voltage** (`V`)
  - **Battery Current** (`A`, positive for charging, negative for discharging)
  - **Instantaneous Power** (`W`)
  - **Consumed Capacity** (`Ah`)
  - **Time Remaining** (`min`, indicates "Infinite" when charging)
  - **Uptime** (`s`, diagnostic)
- **ESPHome Bluetooth Proxy Friendly**: Connects cleanly, reads GATT telemetry, and disconnects so connection handles remain free for the mobile app or other devices.
- **Configurable Polling**: Adjust poll frequency (default 15s, range 5s–300s) directly in the setup flow.

---

## Installation

### Method 1: HACS (Recommended)

1. Open **HACS** in your Home Assistant UI.
2. Click the top-right three dots (**⋮**) and select **Custom repositories**.
3. Enter your repository URL (e.g., `https://github.com/your-username/ha-tbd-smartshunt`).
4. Select **Integration** as the category and click **Add**.
5. Find **TBD Smartshunt** in the HACS store and click **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Copy the `custom_components/tbd_smartshunt` directory to your Home Assistant configuration directory:
   ```
   <config_dir>/custom_components/tbd_smartshunt/
   ```
2. Restart Home Assistant.

---

## Configuration

1. Once Home Assistant restarts, if a TBD Smartshunt is powered on and within range of your Bluetooth adapter or ESPHome Bluetooth Proxy, Home Assistant will display a notification:
   > **Discovered: TBDsmartshunt-XXXXXX**
2. Click **Configure** and follow the prompts.
3. If not discovered automatically:
   - Go to **Settings** → **Devices & Services** → **Add Integration**.
   - Search for **TBD Smartshunt**.
   - Select your device from the discovered dropdown or enter its MAC address manually.

---

## Technical Protocol Specifications

### BLE GATT Architecture

- **Primary Service UUID**: `18424398-7cbc-11e9-8f9e-2a86e4085a59`
- **State of Charge Characteristic UUID**: `2d86686a-53dc-25b3-0c4a-f0e10c8dee20` (Properties: `NOTIFY`, `READ`, `WRITE`)

### 44-Byte Binary Payload Mapping

| Offset | Format | Unit | Description |
| :--- | :--- | :--- | :--- |
| `0 - 3` | `uint32` | `%` | State of Charge |
| `4 - 7` | `float32` (LE) | `V` | Battery Voltage |
| `8 - 11` | `float32` (LE) | `A` | Battery Current |
| `12 - 15` | `float32` (LE) | `W` | Power |
| `16 - 19` | `float32` (LE) | `V` | Auxiliary Voltage / Starter Battery |
| `20 - 23` | `uint32` | `min` | Time remaining (`0xFFFFFFFF` = Infinite / Charging) |
| `24 - 27` | `uint32` | `s` | Uptime counter |
| `28 - 31` | `float32` (LE) | `Ah` | Consumed capacity |
| `32 - 43` | `bytes[12]` | — | Padding / Reserved |

---

## License

MIT License. Feel free to use, modify, and distribute.
