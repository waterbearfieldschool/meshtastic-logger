Meshtastic CSV Map Viewer (resilient version)

To run locally:

1. Unzip this folder.
2. In the terminal, run:

   python -m http.server 8000

3. Open your browser to:

   http://localhost:8000

This version validates coordinates before plotting.
If any line has missing/invalid latitude/longitude, it is skipped to avoid crashing.
