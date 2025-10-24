#!/usr/bin/env python3
"""
Meshtastic Log Analyzer
Analyzes and visualizes logged Meshtastic contact data
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
import statistics

class MeshtasticAnalyzer:
    def __init__(self, json_log="meshtastic_contacts.json"):
        self.json_log = json_log
        self.data = None
        self.load_data()
    
    def load_data(self):
        """Load JSON log data"""
        try:
            with open(self.json_log, 'r') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            print(f"Log file {self.json_log} not found")
            self.data = {"sessions": []}
        except json.JSONDecodeError:
            print(f"Error parsing {self.json_log}")
            self.data = {"sessions": []}
    
    def analyze_session(self, session_index=-1):
        """Analyze a specific session"""
        if not self.data["sessions"]:
            print("No sessions found in log file")
            return
        
        session = self.data["sessions"][session_index]
        contacts = session.get("contacts", [])
        
        if not contacts:
            print("No contacts in this session")
            return
        
        # Get unique nodes
        unique_nodes = {}
        for contact in contacts:
            node_id = contact["node_id"]
            if node_id not in unique_nodes:
                unique_nodes[node_id] = {
                    "first_seen": contact["timestamp"],
                    "last_seen": contact["timestamp"],
                    "name": contact["short_name"],
                    "long_name": contact["long_name"],
                    "hw_model": contact["hw_model"],
                    "rssi_values": [],
                    "snr_values": [],
                    "positions": []
                }
            
            unique_nodes[node_id]["last_seen"] = contact["timestamp"]
            
            if contact["rssi"] is not None:
                unique_nodes[node_id]["rssi_values"].append(contact["rssi"])
            if contact["snr"] is not None:
                unique_nodes[node_id]["snr_values"].append(contact["snr"])
            
            if contact["latitude"] and contact["longitude"]:
                unique_nodes[node_id]["positions"].append({
                    "lat": contact["latitude"],
                    "lon": contact["longitude"],
                    "alt": contact["altitude"]
                })
        
        # Print session summary
        print("\n" + "=" * 60)
        print("SESSION ANALYSIS")
        print("=" * 60)
        
        print(f"\nSession Start: {session.get('start_time', 'Unknown')}")
        print(f"Session End: {session.get('end_time', 'Ongoing')}")
        print(f"Status: {'Active' if session.get('active') else 'Completed'}")
        print(f"Total Contacts: {len(contacts)}")
        print(f"Unique Nodes: {len(unique_nodes)}")
        
        print("\n" + "-" * 60)
        print("NODE DETAILS")
        print("-" * 60)
        
        for node_id, node_data in unique_nodes.items():
            print(f"\n📡 Node ID: {node_id}")
            print(f"   Name: {node_data['name']} ({node_data['long_name']})")
            print(f"   Hardware: {node_data['hw_model']}")
            print(f"   First Seen: {node_data['first_seen']}")
            print(f"   Last Seen: {node_data['last_seen']}")
            
            if node_data["rssi_values"]:
                avg_rssi = statistics.mean(node_data["rssi_values"])
                max_rssi = max(node_data["rssi_values"])
                min_rssi = min(node_data["rssi_values"])
                print(f"   RSSI: Avg={avg_rssi:.1f} dBm, Best={max_rssi} dBm, Worst={min_rssi} dBm")
            
            if node_data["snr_values"]:
                avg_snr = statistics.mean(node_data["snr_values"])
                max_snr = max(node_data["snr_values"])
                min_snr = min(node_data["snr_values"])
                print(f"   SNR: Avg={avg_snr:.1f} dB, Best={max_snr} dB, Worst={min_snr} dB")
            
            if node_data["positions"]:
                print(f"   Position Updates: {len(node_data['positions'])}")
                last_pos = node_data["positions"][-1]
                print(f"   Last Position: {last_pos['lat']:.6f}, {last_pos['lon']:.6f}")
    
    def export_kml(self, output_file="meshtastic_contacts.kml", session_index=-1):
        """Export contacts to KML file for Google Earth"""
        if not self.data["sessions"]:
            print("No sessions found")
            return
        
        session = self.data["sessions"][session_index]
        contacts = session.get("contacts", [])
        
        # Collect unique positions
        positions = {}
        for contact in contacts:
            if contact["latitude"] and contact["longitude"]:
                node_id = contact["node_id"]
                if node_id not in positions:
                    positions[node_id] = {
                        "name": contact["short_name"],
                        "long_name": contact["long_name"],
                        "lat": contact["latitude"],
                        "lon": contact["longitude"],
                        "alt": contact["altitude"] or 0,
                        "timestamp": contact["timestamp"],
                        "rssi": contact["rssi"],
                        "snr": contact["snr"]
                    }
        
        # Create KML
        kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Meshtastic Contacts</name>
    <description>Logged Meshtastic node contacts</description>
    <Style id="nodeStyle">
        <IconStyle>
            <Icon>
                <href>http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png</href>
            </Icon>
        </IconStyle>
    </Style>
"""
        
        for node_id, pos_data in positions.items():
            kml_content += f"""    <Placemark>
        <name>{pos_data['name']} ({node_id})</name>
        <description>
            Long Name: {pos_data['long_name']}
            RSSI: {pos_data['rssi']} dBm
            SNR: {pos_data['snr']} dB
            Time: {pos_data['timestamp']}
        </description>
        <styleUrl>#nodeStyle</styleUrl>
        <Point>
            <coordinates>{pos_data['lon']},{pos_data['lat']},{pos_data['alt']}</coordinates>
        </Point>
    </Placemark>
"""
        
        kml_content += """</Document>
</kml>"""
        
        with open(output_file, 'w') as f:
            f.write(kml_content)
        
        print(f"\nKML file exported: {output_file}")
        print(f"Contains {len(positions)} nodes with position data")
    
    def export_csv(self, output_file="meshtastic_contacts.csv", session_index=-1):
        """Export contacts to CSV file"""
        import csv
        
        if not self.data["sessions"]:
            print("No sessions found")
            return
        
        session = self.data["sessions"][session_index]
        contacts = session.get("contacts", [])
        
        with open(output_file, 'w', newline='') as f:
            fieldnames = [
                "timestamp", "node_id", "short_name", "long_name", 
                "hw_model", "rssi", "snr", "latitude", "longitude", 
                "altitude", "is_new_contact"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for contact in contacts:
                row = {
                    "timestamp": contact["timestamp"],
                    "node_id": contact["node_id"],
                    "short_name": contact["short_name"],
                    "long_name": contact["long_name"],
                    "hw_model": contact["hw_model"],
                    "rssi": contact["rssi"],
                    "snr": contact["snr"],
                    "latitude": contact["latitude"],
                    "longitude": contact["longitude"],
                    "altitude": contact["altitude"],
                    "is_new_contact": contact["is_new_contact"]
                }
                writer.writerow(row)
        
        print(f"\nCSV file exported: {output_file}")
        print(f"Contains {len(contacts)} contact records")
    
    def summary(self):
        """Print overall summary of all sessions"""
        print("\n" + "=" * 60)
        print("OVERALL SUMMARY")
        print("=" * 60)
        
        total_sessions = len(self.data["sessions"])
        total_contacts = sum(len(s.get("contacts", [])) for s in self.data["sessions"])
        
        all_nodes = set()
        for session in self.data["sessions"]:
            for contact in session.get("contacts", []):
                all_nodes.add(contact["node_id"])
        
        print(f"\nTotal Sessions: {total_sessions}")
        print(f"Total Contact Records: {total_contacts}")
        print(f"Unique Nodes Seen: {len(all_nodes)}")
        
        if self.data["sessions"]:
            print("\nSessions:")
            for i, session in enumerate(self.data["sessions"]):
                status = "Active" if session.get("active") else "Completed"
                contacts = len(session.get("contacts", []))
                print(f"  Session {i+1}: {session.get('start_time', 'Unknown')} - {status} ({contacts} contacts)")

def main():
    parser = argparse.ArgumentParser(description="Analyze Meshtastic contact logs")
    parser.add_argument("-j", "--json", default="meshtastic_contacts.json", help="JSON log file path")
    parser.add_argument("-s", "--session", type=int, default=-1, help="Session index to analyze (default: last)")
    parser.add_argument("--summary", action="store_true", help="Show overall summary")
    parser.add_argument("--kml", help="Export to KML file")
    parser.add_argument("--csv", help="Export to CSV file")
    
    args = parser.parse_args()
    
    analyzer = MeshtasticAnalyzer(json_log=args.json)
    
    if args.summary:
        analyzer.summary()
    
    if args.kml:
        analyzer.export_kml(output_file=args.kml, session_index=args.session)
    
    if args.csv:
        analyzer.export_csv(output_file=args.csv, session_index=args.session)
    
    if not args.summary and not args.kml and not args.csv:
        analyzer.analyze_session(session_index=args.session)

if __name__ == "__main__":
    main()
