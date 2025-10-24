#!/usr/bin/env python3
"""
Simple Meshtastic CSV Logger
Logs node information to log.csv while driving
"""

import subprocess
import json
import csv
import time
import sys
from datetime import datetime
import signal

class SimpleMeshtasticLogger:
    def __init__(self, port=None, csv_file="log.csv"):
        self.port = port
        self.csv_file = csv_file
        self.running = True
        
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
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
                    'latitude',
                    'longitude', 
                    'altitude',
                    'rssi',
                    'snr',
                    'hw_model'
                ])
        except FileExistsError:
            pass
    
    def stop(self, signum=None, frame=None):
        """Stop logging"""
        self.running = False
        print("\nStopping logger...")
        sys.exit(0)
    
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
        
        # Find the data rows (skip header and separators)
        for line in lines:
            if line.startswith('│') and not line.startswith('╒') and not line.startswith('╞') and not line.startswith('╘'):
                # Split by │ and clean up
                parts = [p.strip() for p in line.split('│')[1:-1]]  # Remove first and last empty parts
                
                if len(parts) >= 12 and parts[0].isdigit():  # Make sure it's a data row
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
                        'last_heard': parts[16] if parts[16] != 'N/A' else None
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
            node.get('hardware', '')
        ]
        
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f"Logged: {node.get('user', 'Unknown')} (SNR: {snr})")
    
    def run(self, interval=10):
        """Main loop"""
        print(f"Starting CSV logger - saving to {self.csv_file}")
        print("Press Ctrl+C to stop\n")
        
        while self.running:
            try:
                nodes = self.get_nodes()
                if nodes:
                    for node in nodes:
                        if node.get("id") and node.get("snr"):
                            self.log_node(node)
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(interval)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Meshtastic CSV Logger")
    parser.add_argument("-p", "--port", help="Serial port")
    parser.add_argument("-i", "--interval", type=int, default=10, help="Polling interval (seconds)")
    parser.add_argument("-f", "--file", default="log.csv", help="CSV file name")
    
    args = parser.parse_args()
    
    logger = SimpleMeshtasticLogger(port=args.port, csv_file=args.file)
    logger.run(interval=args.interval)