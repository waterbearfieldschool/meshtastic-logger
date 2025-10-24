#!/usr/bin/env python3
"""
Live Meshtastic CSV Logger with Terminal Display
Logs node information to CSV and shows live unique contacts in terminal
"""

import subprocess
import csv
import time
import sys
import os
from datetime import datetime
import signal
import serial
import re

class LiveMeshtasticLogger:
    def __init__(self, port=None, csv_file="log.csv", gps_port=None, my_node_id=None):
        self.port = port
        self.csv_file = csv_file
        self.gps_port = gps_port
        self.my_node_id = my_node_id
        self.running = True
        self.seen_nodes = {}  # Track unique nodes
        self.current_position = {'lat': None, 'lon': None, 'alt': None}
        self.gps_serial = None
        
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
        if gps_port:
            self.init_gps()
        
        self.init_csv()
    
    def init_csv(self):
        """Initialize CSV file with headers"""
        try:
            with open(self.csv_file, 'x', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'node_id', 
                    'short_name',
                    'long_name',
                    'node_latitude',
                    'node_longitude', 
                    'node_altitude',
                    'rssi',
                    'snr',
                    'hw_model',
                    'our_latitude',
                    'our_longitude',
                    'our_altitude'
                ])
        except FileExistsError:
            pass
    
    def init_gps(self):
        """Initialize GPS connection"""
        try:
            self.gps_serial = serial.Serial(self.gps_port, 9600, timeout=1)
            print(f"GPS connected on {self.gps_port}")
        except Exception as e:
            print(f"GPS connection failed: {e}")
            self.gps_serial = None
    
    def get_gps_position(self):
        """Get current GPS position from NMEA data"""
        if not self.gps_serial:
            return
        
        try:
            # Read a few lines to find a good GPS fix
            for _ in range(10):
                line = self.gps_serial.readline().decode('ascii', errors='ignore').strip()
                
                # Look for GPGGA (Global Positioning System Fix Data)
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    parts = line.split(',')
                    if len(parts) > 10 and parts[6] in ['1', '2']:  # Valid fix
                        # Parse latitude
                        if parts[2] and parts[3]:
                            lat_deg = float(parts[2][:2])
                            lat_min = float(parts[2][2:])
                            lat = lat_deg + lat_min/60
                            if parts[3] == 'S':
                                lat = -lat
                            self.current_position['lat'] = lat
                        
                        # Parse longitude
                        if parts[4] and parts[5]:
                            lon_deg = float(parts[4][:3])
                            lon_min = float(parts[4][3:])
                            lon = lon_deg + lon_min/60
                            if parts[5] == 'W':
                                lon = -lon
                            self.current_position['lon'] = lon
                        
                        # Parse altitude
                        if parts[9]:
                            self.current_position['alt'] = float(parts[9])
                        
                        break
        except Exception as e:
            pass  # Silently handle GPS errors
    
    def get_meshtastic_position(self):
        """Try to get our position from the Meshtastic device"""
        try:
            # Get the nodes table and find our own node
            nodes = self.get_nodes()
            if nodes:
                for node in nodes:
                    # Look for our own node by ID/AKA or by "now" timestamp
                    is_our_node = False
                    
                    if self.my_node_id:
                        # Check if this matches our specified node ID
                        is_our_node = (self.my_node_id.lower() in node.get('aka', '').lower() or 
                                     self.my_node_id.lower() in node.get('id', '').lower())
                    else:
                        # Fall back to looking for "now" in since column or very recent
                        since = node.get('since', '')
                        is_our_node = (since and ('now' in since.lower() or 'sec ago' in since.lower()))
                    
                    if is_our_node and node.get('latitude') and node.get('longitude'):
                        lat = node.get('latitude', '')
                        lon = node.get('longitude', '')
                        alt = node.get('altitude', '')
                        
                        if lat and lat != 'N/A':
                            self.current_position['lat'] = float(lat.replace('°', ''))
                        if lon and lon != 'N/A':
                            self.current_position['lon'] = float(lon.replace('°', ''))
                        if alt and alt != 'N/A':
                            self.current_position['alt'] = float(alt.replace('m', ''))
                        break
        except Exception:
            pass  # Silently handle errors
    
    def update_position(self):
        """Update our current position from available sources"""
        # Try GPS first, then Meshtastic device
        if self.gps_serial:
            self.get_gps_position()
        else:
            self.get_meshtastic_position()
    
    def stop(self, signum=None, frame=None):
        """Stop logging"""
        self.running = False
        if self.gps_serial:
            self.gps_serial.close()
        print("\n\nStopping logger...")
        print(f"Total unique nodes seen: {len(self.seen_nodes)}")
        sys.exit(0)
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def get_nodes(self):
        """Get node data from meshtastic CLI"""
        try:
            cmd = ["/home/dwblair/gitwork/sx126x-circuitpython/myenv/bin/meshtastic", "--nodes"]
            if self.port:
                cmd.extend(["--port", self.port])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return self.parse_table_output(result.stdout)
        except Exception as e:
            print(f"Error: {e}")
        return None
    
    def parse_table_output(self, output):
        """Parse the table output from meshtastic --nodes"""
        nodes = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if line.startswith('│') and not line.startswith('╒') and not line.startswith('╞') and not line.startswith('╘'):
                parts = [p.strip() for p in line.split('│')[1:-1]]
                
                if len(parts) >= 17 and parts[0].isdigit():
                    node = {
                        'num': parts[0],
                        'user': parts[1],
                        'id': parts[2],
                        'aka': parts[3],
                        'hardware': parts[4],
                        'latitude': parts[7] if parts[7] != 'N/A' else None,
                        'longitude': parts[8] if parts[8] != 'N/A' else None,
                        'altitude': parts[9] if parts[9] != 'N/A' else None,
                        'snr': parts[13] if parts[13] != 'N/A' else None,
                        'last_heard': parts[16] if parts[16] != 'N/A' else None,
                        'since': parts[17] if len(parts) > 17 and parts[17] != 'N/A' else None
                    }
                    nodes.append(node)
        
        return nodes
    
    def log_node(self, node):
        """Log a single node to CSV"""
        timestamp = datetime.now().isoformat()
        
        # Clean up coordinate values
        lat = node.get('latitude', '')
        lon = node.get('longitude', '')
        alt = node.get('altitude', '')
        
        if lat and lat != 'N/A':
            lat = lat.replace('°', '')
        if lon and lon != 'N/A':
            lon = lon.replace('°', '')
        if alt and alt != 'N/A':
            alt = alt.replace('m', '')
        
        # Clean up SNR value
        snr = node.get('snr', '')
        if snr and snr != 'N/A':
            snr = snr.replace(' dB', '')
        
        row = [
            timestamp,
            node.get('id', ''),
            node.get('aka', ''),
            node.get('user', ''),
            lat,
            lon,
            alt,
            '',  # rssi not in table output
            snr,
            node.get('hardware', ''),
            self.current_position.get('lat', ''),
            self.current_position.get('lon', ''),
            self.current_position.get('alt', '')
        ]
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
    
    def update_seen_nodes(self, nodes):
        """Update the seen nodes tracker"""
        current_time = datetime.now()
        
        for node in nodes:
            node_id = node.get('id')
            if node_id and node.get('snr'):
                self.seen_nodes[node_id] = {
                    'user': node.get('user', 'Unknown'),
                    'aka': node.get('aka', ''),
                    'hardware': node.get('hardware', ''),
                    'snr': node.get('snr', ''),
                    'latitude': node.get('latitude', ''),
                    'longitude': node.get('longitude', ''),
                    'last_seen': current_time,
                    'last_heard': node.get('last_heard', '')
                }
                self.log_node(node)
    
    def display_nodes(self):
        """Display unique nodes in terminal"""
        self.clear_screen()
        
        print("🚗 Live Meshtastic Node Logger")
        print("=" * 110)
        print(f"CSV Log: {self.csv_file}")
        print(f"Unique Nodes Seen: {len(self.seen_nodes)}")
        print(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
        
        # Show our current position
        if self.current_position['lat'] and self.current_position['lon']:
            print(f"📍 Our Location: {self.current_position['lat']:.6f}, {self.current_position['lon']:.6f}", end="")
            if self.current_position['alt']:
                print(f", Alt: {self.current_position['alt']:.1f}m")
            else:
                print()
        else:
            print("📍 Our Location: GPS not available")
        
        print("\nPress Ctrl+C to stop")
        print("=" * 110)
        
        if not self.seen_nodes:
            print("\nNo nodes detected yet...")
            return
        
        # Sort by last seen time (most recent first)
        sorted_nodes = sorted(
            self.seen_nodes.items(), 
            key=lambda x: x[1]['last_seen'], 
            reverse=True
        )
        
        print(f"\n{'ID':<12} {'Name':<20} {'Hardware':<18} {'SNR':<8} {'Last Seen':<12} {'Node Location':<20} {'Our Location':<20}")
        print("-" * 110)
        
        for node_id, data in sorted_nodes:
            # Calculate time since last seen
            time_diff = datetime.now() - data['last_seen']
            if time_diff.seconds < 60:
                last_seen = f"{time_diff.seconds}s ago"
            elif time_diff.seconds < 3600:
                last_seen = f"{time_diff.seconds//60}m ago"
            else:
                last_seen = f"{time_diff.seconds//3600}h ago"
            
            # Format node location
            node_location = ""
            if data['latitude'] and data['longitude']:
                node_location = f"{data['latitude'][:8]},{data['longitude'][:8]}"
            
            # Format our location
            our_location = ""
            if self.current_position['lat'] and self.current_position['lon']:
                our_location = f"{self.current_position['lat']:.4f},{self.current_position['lon']:.4f}"
            
            # Clean SNR for display
            snr = data['snr'].replace(' dB', '') if data['snr'] else 'N/A'
            
            print(f"{node_id:<12} {data['user'][:19]:<20} {data['hardware'][:17]:<18} {snr:<8} {last_seen:<12} {node_location:<20} {our_location:<20}")
    
    def run(self, interval=10):
        """Main loop"""
        print("Starting Live Meshtastic Logger...")
        time.sleep(2)  # Brief pause before starting
        
        while self.running:
            try:
                # Update our position
                self.update_position()
                
                nodes = self.get_nodes()
                if nodes:
                    self.update_seen_nodes(nodes)
                
                self.display_nodes()
                time.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Meshtastic CSV Logger with Terminal Display and GPS")
    parser.add_argument("-p", "--port", help="Meshtastic serial port (e.g., /dev/ttyACM0)")
    parser.add_argument("-g", "--gps-port", help="GPS serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("-n", "--my-node", help="Your node ID/AKA (e.g., 'baf0') for position tracking")
    parser.add_argument("-i", "--interval", type=int, default=10, help="Polling interval (seconds)")
    parser.add_argument("-f", "--file", default="log.csv", help="CSV file name")
    
    args = parser.parse_args()
    
    logger = LiveMeshtasticLogger(port=args.port, csv_file=args.file, gps_port=args.gps_port, my_node_id=args.my_node)
    logger.run(interval=args.interval)