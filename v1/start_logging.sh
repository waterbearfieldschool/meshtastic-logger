#!/bin/bash

# Meshtastic Logger Startup Script
# Easy way to start logging with common options

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}    Meshtastic Contact Logger    ${NC}"
echo -e "${GREEN}==================================${NC}"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if meshtastic CLI is installed
if ! command -v meshtastic &> /dev/null; then
    echo -e "${YELLOW}Warning: Meshtastic CLI not found${NC}"
    echo "Install with: pip install meshtastic"
    echo
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Default values
PORT=""
INTERVAL=5
LOG_DIR="./logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -d|--dir)
            LOG_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -p, --port PORT       Serial port (e.g., /dev/ttyUSB0)"
            echo "  -i, --interval SEC    Polling interval in seconds (default: 5)"
            echo "  -d, --dir DIR         Log directory (default: ./logs)"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Auto-detect serial port if not specified
if [ -z "$PORT" ]; then
    echo "Auto-detecting serial port..."
    
    # Look for common Meshtastic devices
    for port in /dev/ttyUSB* /dev/ttyACM* /dev/tty.usbserial* /dev/tty.usbmodem*; do
        if [ -e "$port" ]; then
            echo -e "${GREEN}Found potential port: $port${NC}"
            PORT="$port"
            break
        fi
    done
    
    if [ -z "$PORT" ]; then
        echo -e "${YELLOW}No serial port auto-detected${NC}"
        echo "Will try default Meshtastic behavior"
    fi
fi

# Set up log files
LOG_FILE="$LOG_DIR/meshtastic_${TIMESTAMP}.log"
JSON_FILE="$LOG_DIR/meshtastic_${TIMESTAMP}.json"

# Display configuration
echo -e "${YELLOW}Configuration:${NC}"
echo "  Port: ${PORT:-Auto}"
echo "  Interval: ${INTERVAL}s"
echo "  Text log: $LOG_FILE"
echo "  JSON log: $JSON_FILE"
echo

# Start logging
echo -e "${GREEN}Starting logger...${NC}"
echo "Press Ctrl+C to stop"
echo

# Build command
CMD="python3 meshtastic_logger.py --interval $INTERVAL --log \"$LOG_FILE\" --json \"$JSON_FILE\""

if [ ! -z "$PORT" ]; then
    CMD="$CMD --port $PORT"
fi

# Execute
eval $CMD

# After logging stops
echo
echo -e "${GREEN}Logging session complete!${NC}"
echo "Logs saved to:"
echo "  Text: $LOG_FILE"
echo "  JSON: $JSON_FILE"
echo
echo "To analyze the data, run:"
echo "  python3 meshtastic_analyzer.py --json \"$JSON_FILE\""
