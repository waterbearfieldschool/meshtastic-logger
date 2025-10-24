#!/usr/bin/env python3
"""
Meshtastic Node Logger
Logs unique contacts with timestamp, position, and signal strength
"""

import subprocess
import json
import time
import argparse
import sys
from datetime import datetime
from pathlib import Path
import signal
import re

class MeshtasticLogger:
    def __init__(self, port=None, log_file="meshtastic_contacts.log", json_log="meshtastic_contacts.json"):
        self.port = port
        self.log_file = log_file
        self.json_log = json_log
        self.seen_nodes = {}  # Track seen nodes with their last update
        self.running = True
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Initialize log files
        self.init_logs()
    
    def init_logs(self):
        """Initialize log files with headers"""
        if not Path(self.log_file).exists():
            with open(self.log_file, 'w') as f:
                f.write("=== Meshtastic Contact Logger ===\n")
                f.write(f"Started: {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
        
        if not Path(self.json_log).exists():
            with open(self.json_log, 'w') as f:
                json.dump({"sessions": []}, f)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print("\n\nShutting down logger...")
        self.running = False
        sys.exit(0)
    
    def get_node_info(self):
        """Get current node information from meshtastic CLI"""
        try:
            # Build command
            cmd = ["meshtastic", "--nodes", "--output", "json"]
            if self.port:
                cmd.extend(["--port", self.port])
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"Error running meshtastic command: {result.stderr}")
                return None
            
            # Parse JSON output
            try:
                data = json.loads(result.stdout)
                return data
            except json.JSONDecodeError:
                # Sometimes the output isn't pure JSON, try to extract it
                json_match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return None
                
        except subprocess.TimeoutExpired:
            print("Command timeout - node might be busy")
            return None
        except Exception as e:
            print(f"Error getting node info: {e}")
            return None
    
    def parse_node_data(self, node_data):
        """Extract relevant information from node data"""
        nodes = []
        
        if not node_data:
            return nodes
        
        # Handle different possible data structures
        if "nodes" in node_data:
            node_list = node_data["nodes"]
        elif isinstance(node_data, list):
            node_list = node_data
        else:
            node_list = [node_data]
        
        for node in node_list:
            node_info = {
                "id": node.get("num", "unknown"),
                "user": node.get("user", {}),
                "position": node.get("position", {}),
                "snr": node.get("snr"),
                "rssi": node.get("rssi"),
                "lastHeard": node.get("lastHeard"),
                "deviceMetrics": node.get("deviceMetrics", {})
            }
            
            # Extract user info
            user = node_info["user"]
            node_info["shortName"] = user.get("shortName", "Unknown")
            node_info["longName"] = user.get("longName", "Unknown")
            node_info["hwModel"] = user.get("hwModel", "Unknown")
            
            # Extract position if available
            pos = node_info["position"]
            if pos:
                node_info["latitude"] = pos.get("latitude")
                node_info["longitude"] = pos.get("longitude")
                node_info["altitude"] = pos.get("altitude")
            else:
                node_info["latitude"] = None
                node_info["longitude"] = None
                node_info["altitude"] = None
            
            nodes.append(node_info)
        
        return nodes
    
    def log_node(self, node_info):
        """Log node information to files"""
        timestamp = datetime.now().isoformat()
        node_id = node_info["id"]
        
        # Check if this is a new contact or update
        is_new = node_id not in self.seen_nodes
        
        # Update seen nodes
        self.seen_nodes[node_id] = {
            "last_seen": timestamp,
            "info": node_info
        }
        
        # Create log entry
        log_entry = {
            "timestamp": timestamp,
            "is_new_contact": is_new,
            "node_id": node_id,
            "short_name": node_info["shortName"],
            "long_name": node_info["longName"],
            "hw_model": node_info["hwModel"],
            "rssi": node_info["rssi"],
            "snr": node_info["snr"],
            "latitude": node_info["latitude"],
            "longitude": node_info["longitude"],
            "altitude": node_info["altitude"],
            "last_heard": node_info["lastHeard"]
        }
        
        # Write to text log
        with open(self.log_file, 'a') as f:
            if is_new:
                f.write(f"*** NEW CONTACT ***\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Node ID: {node_id}\n")
            f.write(f"Name: {node_info['shortName']} ({node_info['longName']})\n")
            f.write(f"Hardware: {node_info['hwModel']}\n")
            f.write(f"Signal: RSSI={node_info['rssi']} dBm, SNR={node_info['snr']} dB\n")
            
            if node_info["latitude"] and node_info["longitude"]:
                f.write(f"Position: {node_info['latitude']:.6f}, {node_info['longitude']:.6f}")
                if node_info["altitude"]:
                    f.write(f", Alt: {node_info['altitude']}m")
                f.write("\n")
            else:
                f.write("Position: Not available\n")
            
            f.write("-" * 40 + "\n\n")
        
        # Write to JSON log
        try:
            with open(self.json_log, 'r') as f:
                json_data = json.load(f)
        except:
            json_data = {"sessions": []}
        
        # Find or create current session
        if not json_data["sessions"] or not json_data["sessions"][-1].get("active"):
            json_data["sessions"].append({
                "start_time": timestamp,
                "active": True,
                "contacts": []
            })
        
        json_data["sessions"][-1]["contacts"].append(log_entry)
        
        with open(self.json_log, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        # Print to console
        if is_new:
            print(f"\n🆕 NEW CONTACT: {node_info['shortName']} ({node_info['longName']})")
        else:
            print(f"📡 Update: {node_info['shortName']}", end=" ")
        
        print(f"[RSSI: {node_info['rssi']} dBm, SNR: {node_info['snr']} dB]")
        
        if node_info["latitude"] and node_info["longitude"]:
            print(f"   📍 Position: {node_info['latitude']:.6f}, {node_info['longitude']:.6f}")
    
    def run(self, interval=5):
        """Main monitoring loop"""
        print(f"Starting Meshtastic Logger...")
        print(f"Port: {self.port if self.port else 'Auto-detect'}")
        print(f"Log file: {self.log_file}")
        print(f"JSON log: {self.json_log}")
        print(f"Polling interval: {interval} seconds")
        print("\nPress Ctrl+C to stop\n")
        print("=" * 50)
        
        while self.running:
            try:
                # Get current node information
                node_data = self.get_node_info()
                
                if node_data:
                    nodes = self.parse_node_data(node_data)
                    
                    # Log each node
                    for node in nodes:
                        # Skip nodes without ID or the local node
                        if node["id"] and node["id"] != "unknown":
                            # Only log if we have signal data (indicates actual contact)
                            if node["rssi"] is not None or node["snr"] is not None:
                                self.log_node(node)
                
                # Wait before next poll
                time.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(interval)
        
        # Mark session as inactive
        try:
            with open(self.json_log, 'r') as f:
                json_data = json.load(f)
            if json_data["sessions"] and json_data["sessions"][-1].get("active"):
                json_data["sessions"][-1]["active"] = False
                json_data["sessions"][-1]["end_time"] = datetime.now().isoformat()
                with open(self.json_log, 'w') as f:
                    json.dump(json_data, f, indent=2)
        except:
            pass
        
        print(f"\n\nLogging session ended")
        print(f"Total unique contacts: {len(self.seen_nodes)}")

def main():
    parser = argparse.ArgumentParser(description="Log Meshtastic node contacts with position and signal data")
    parser.add_argument("-p", "--port", help="Serial port (e.g., /dev/ttyUSB0 or COM3)")
    parser.add_argument("-i", "--interval", type=int, default=5, help="Polling interval in seconds (default: 5)")
    parser.add_argument("-l", "--log", default="meshtastic_contacts.log", help="Log file path")
    parser.add_argument("-j", "--json", default="meshtastic_contacts.json", help="JSON log file path")
    
    args = parser.parse_args()
    
    logger = MeshtasticLogger(
        port=args.port,
        log_file=args.log,
        json_log=args.json
    )
    
    logger.run(interval=args.interval)

if __name__ == "__main__":
    main()
