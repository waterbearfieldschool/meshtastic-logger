#!/usr/bin/env python3
"""
Meshtastic Web Logger with Live Map Visualization
Combines logging with real-time web-based map display using Leaflet
"""

import subprocess
import csv
import time
import sys
import os
import json
import threading
from datetime import datetime
import signal
import serial
import re
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

class WebMeshtasticLogger:
    def __init__(self, port=None, csv_file="log.csv", gps_port=None, my_node_id=None):
        self.port = port
        self.csv_file = csv_file
        self.gps_port = gps_port
        self.my_node_id = my_node_id
        self.running = True
        self.seen_nodes = {}  # Track unique nodes
        self.current_position = {'lat': None, 'lon': None, 'alt': None}
        self.gps_serial = None
        self.data_lock = threading.Lock()
        
        # Flask app setup
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'meshtastic_logger_secret'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
        if gps_port:
            self.init_gps()
        
        self.init_csv()
        self.setup_routes()
    
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
            for _ in range(10):
                line = self.gps_serial.readline().decode('ascii', errors='ignore').strip()
                
                if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
                    parts = line.split(',')
                    if len(parts) > 10 and parts[6] in ['1', '2']:
                        if parts[2] and parts[3]:
                            lat_deg = float(parts[2][:2])
                            lat_min = float(parts[2][2:])
                            lat = lat_deg + lat_min/60
                            if parts[3] == 'S':
                                lat = -lat
                            self.current_position['lat'] = lat
                        
                        if parts[4] and parts[5]:
                            lon_deg = float(parts[4][:3])
                            lon_min = float(parts[4][3:])
                            lon = lon_deg + lon_min/60
                            if parts[5] == 'W':
                                lon = -lon
                            self.current_position['lon'] = lon
                        
                        if parts[9]:
                            self.current_position['alt'] = float(parts[9])
                        
                        break
        except Exception as e:
            pass
    
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
    
    def get_meshtastic_position(self):
        """Try to get our position from the Meshtastic device"""
        try:
            nodes = self.get_nodes()
            if nodes:
                for node in nodes:
                    is_our_node = False
                    
                    if self.my_node_id:
                        is_our_node = (self.my_node_id.lower() in node.get('aka', '').lower() or 
                                     self.my_node_id.lower() in node.get('id', '').lower())
                    else:
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
            pass
    
    def update_position(self):
        """Update our current position from available sources"""
        if self.gps_serial:
            self.get_gps_position()
        else:
            self.get_meshtastic_position()
    
    def log_node(self, node):
        """Log a single node to CSV"""
        timestamp = datetime.now().isoformat()
        
        lat = node.get('latitude', '')
        lon = node.get('longitude', '')
        alt = node.get('altitude', '')
        
        if lat and lat != 'N/A':
            lat = lat.replace('°', '')
        if lon and lon != 'N/A':
            lon = lon.replace('°', '')
        if alt and alt != 'N/A':
            alt = alt.replace('m', '')
        
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
            '',
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
        updated_nodes = []
        
        with self.data_lock:
            for node in nodes:
                node_id = node.get('id')
                if node_id and node.get('snr'):
                    is_new = node_id not in self.seen_nodes
                    
                    self.seen_nodes[node_id] = {
                        'user': node.get('user', 'Unknown'),
                        'aka': node.get('aka', ''),
                        'hardware': node.get('hardware', ''),
                        'snr': node.get('snr', ''),
                        'latitude': node.get('latitude', ''),
                        'longitude': node.get('longitude', ''),
                        'last_seen': current_time,
                        'last_heard': node.get('last_heard', ''),
                        'is_new': is_new
                    }
                    
                    self.log_node(node)
                    
                    # Prepare data for web update
                    lat = node.get('latitude', '')
                    lon = node.get('longitude', '')
                    if lat and lon and lat != 'N/A' and lon != 'N/A':
                        lat_val = float(lat.replace('°', ''))
                        lon_val = float(lon.replace('°', ''))
                        
                        updated_nodes.append({
                            'id': node_id,
                            'user': node.get('user', 'Unknown'),
                            'latitude': lat_val,
                            'longitude': lon_val,
                            'snr': node.get('snr', ''),
                            'hardware': node.get('hardware', ''),
                            'is_new': is_new
                        })
        
        # Emit updates to web clients
        if updated_nodes:
            self.socketio.emit('nodes_update', {
                'nodes': updated_nodes,
                'our_position': self.current_position
            })
    
    def setup_routes(self):
        """Setup Flask routes"""
        @self.app.route('/')
        def index():
            return render_template('map.html')
        
        @self.app.route('/api/data')
        def get_data():
            with self.data_lock:
                nodes_data = []
                for node_id, data in self.seen_nodes.items():
                    lat = data.get('latitude', '')
                    lon = data.get('longitude', '')
                    if lat and lon and lat != 'N/A' and lon != 'N/A':
                        lat_val = float(lat.replace('°', ''))
                        lon_val = float(lon.replace('°', ''))
                        
                        nodes_data.append({
                            'id': node_id,
                            'user': data['user'],
                            'latitude': lat_val,
                            'longitude': lon_val,
                            'snr': data['snr'],
                            'hardware': data['hardware'],
                            'last_seen': data['last_seen'].isoformat()
                        })
                
                return jsonify({
                    'nodes': nodes_data,
                    'our_position': self.current_position,
                    'total_nodes': len(self.seen_nodes)
                })
    
    def monitoring_loop(self):
        """Main monitoring loop"""
        print("Starting monitoring loop...")
        
        while self.running:
            try:
                self.update_position()
                
                nodes = self.get_nodes()
                if nodes:
                    self.update_seen_nodes(nodes)
                
                time.sleep(10)
                
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(10)
    
    def stop(self, signum=None, frame=None):
        """Stop logging"""
        self.running = False
        if self.gps_serial:
            self.gps_serial.close()
        print(f"\n\nStopping logger... Total unique nodes seen: {len(self.seen_nodes)}")
        sys.exit(0)
    
    def run(self, host='localhost', port=5000):
        """Run the web server and monitoring"""
        print(f"Starting Meshtastic Web Logger on http://{host}:{port}")
        
        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=self.monitoring_loop)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Start web server
        self.socketio.run(self.app, host=host, port=port, debug=False)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Meshtastic Web Logger with Live Map")
    parser.add_argument("-p", "--port", help="Meshtastic serial port (e.g., /dev/ttyACM0)")
    parser.add_argument("-g", "--gps-port", help="GPS serial port (e.g., /dev/ttyUSB0)")
    parser.add_argument("-n", "--my-node", help="Your node ID/AKA (e.g., 'baf0') for position tracking")
    parser.add_argument("-f", "--file", default="log.csv", help="CSV file name")
    parser.add_argument("--host", default="localhost", help="Web server host")
    parser.add_argument("--web-port", type=int, default=5000, help="Web server port")
    
    args = parser.parse_args()
    
    logger = WebMeshtasticLogger(
        port=args.port, 
        csv_file=args.file, 
        gps_port=args.gps_port, 
        my_node_id=args.my_node
    )
    logger.run(host=args.host, port=args.web_port)