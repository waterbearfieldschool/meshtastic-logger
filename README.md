# Meshtastic Contact Logger

A tool for logging Meshtastic node contacts with timestamps, position data, and signal strength information. Perfect for mobile/wardriving scenarios.

## Features

- **Real-time monitoring** of Meshtastic nodes via serial connection
- **Automatic logging** of new contacts and updates
- **Position tracking** with GPS coordinates (when available)
- **Signal strength recording** (RSSI and SNR values)
- **Dual logging format** (human-readable text and structured JSON)
- **Data analysis tools** for post-processing
- **Export capabilities** (KML for Google Earth, CSV for spreadsheets)

## Prerequisites

1. Python 3.6 or higher
2. Meshtastic Python CLI installed:
   ```bash
   pip install meshtastic
   ```

## Installation

1. Download the scripts:
   - `meshtastic_logger.py` - Main logging tool
   - `meshtastic_analyzer.py` - Data analysis tool

2. Make them executable:
   ```bash
   chmod +x meshtastic_logger.py
   chmod +x meshtastic_analyzer.py
   ```

## Usage

### Basic Logging

Start logging with auto-detected serial port:
```bash
python3 meshtastic_logger.py
```

Specify a serial port:
```bash
python3 meshtastic_logger.py --port /dev/ttyUSB0
```

On Windows:
```bash
python meshtastic_logger.py --port COM3
```

### Advanced Options

```bash
python3 meshtastic_logger.py \
    --port /dev/ttyUSB0 \
    --interval 10 \
    --log my_drive.log \
    --json my_drive.json
```

Options:
- `-p, --port`: Serial port (e.g., /dev/ttyUSB0, COM3)
- `-i, --interval`: Polling interval in seconds (default: 5)
- `-l, --log`: Text log file path (default: meshtastic_contacts.log)
- `-j, --json`: JSON log file path (default: meshtastic_contacts.json)

### Analyzing Logged Data

View analysis of the last session:
```bash
python3 meshtastic_analyzer.py
```

View overall summary:
```bash
python3 meshtastic_analyzer.py --summary
```

Export to KML (for Google Earth):
```bash
python3 meshtastic_analyzer.py --kml contacts.kml
```

Export to CSV:
```bash
python3 meshtastic_analyzer.py --csv contacts.csv
```

Analyze a specific session:
```bash
python3 meshtastic_analyzer.py --session 0  # First session
```

## Output Files

### Text Log (meshtastic_contacts.log)
Human-readable format with timestamps and formatted data:
```
*** NEW CONTACT ***
Timestamp: 2025-01-XX...
Node ID: !abcd1234
Name: Node1 (Mobile Node 1)
Hardware: TLORA_V2
Signal: RSSI=-85 dBm, SNR=7.5 dB
Position: 42.123456, -71.234567, Alt: 50m
```

### JSON Log (meshtastic_contacts.json)
Structured data for programmatic analysis:
```json
{
  "sessions": [
    {
      "start_time": "2025-01-XX...",
      "active": false,
      "contacts": [
        {
          "timestamp": "...",
          "node_id": "!abcd1234",
          "short_name": "Node1",
          "rssi": -85,
          "snr": 7.5,
          "latitude": 42.123456,
          "longitude": -71.234567
        }
      ]
    }
  ]
}
```

## Tips for Mobile/Wardriving Use

1. **Power**: Use a USB battery pack for extended logging sessions
2. **Antenna**: Consider an external antenna for better range
3. **Mounting**: Secure the node and laptop/Pi properly in your vehicle
4. **GPS**: Ensure your Meshtastic node has GPS enabled for position logging
5. **Screen/tmux**: Run in a screen or tmux session to prevent disconnection:
   ```bash
   screen -S mesh
   python3 meshtastic_logger.py
   # Press Ctrl+A, then D to detach
   # Reattach with: screen -r mesh
   ```

## Troubleshooting

### Permission Denied on Serial Port
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### No Nodes Detected
- Check serial connection: `ls /dev/tty*`
- Verify Meshtastic CLI works: `meshtastic --info`
- Ensure node is powered and connected

### JSON Decode Errors
- The Meshtastic CLI sometimes outputs non-JSON text
- The script handles this automatically
- Check if running the latest Meshtastic CLI version

## Signal Strength Reference

- **RSSI (Received Signal Strength Indicator)**:
  - Excellent: > -50 dBm
  - Good: -50 to -70 dBm
  - Fair: -70 to -85 dBm
  - Poor: -85 to -100 dBm
  - Very Poor: < -100 dBm

- **SNR (Signal-to-Noise Ratio)**:
  - Excellent: > 10 dB
  - Good: 5 to 10 dB
  - Fair: 0 to 5 dB
  - Poor: < 0 dB

## Safety Note

When using while driving:
- Have a passenger operate the equipment
- Set up everything before driving
- Use voice alerts or review logs after stopping
- Follow all local laws regarding mobile device use

## License

These scripts are provided as-is for educational and amateur radio purposes.
