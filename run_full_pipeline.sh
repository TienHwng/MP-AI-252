#!/bin/bash
# run_full_pipeline.sh - Start HERA with TinyML Inference Pipeline
# Starts all required components in the correct order

echo "=========================================="
echo "   HERA Full Pipeline with TinyML"
echo "=========================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check dependencies
echo -e "\n${YELLOW}📋 Checking dependencies...${NC}"

# Check MQTT broker
if ! command -v mosquitto &> /dev/null; then
    echo -e "${RED}❌ Mosquitto not installed${NC}"
    echo "   Install: apt-get install mosquitto (Linux/WSL)"
    echo "   Install: brew install mosquitto (macOS)"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not installed${NC}"
    exit 1
fi

# Setup virtual environment
echo -e "${YELLOW}🔧 Setting up Python virtual environment...${NC}"
cd backend/HERA

# Create venv if not exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating new virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}📥 Installing dependencies...${NC}"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt --quiet

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies ready${NC}"

# Go back to root
cd ../..
PYTHON_BIN="backend/HERA/venv/bin/python3"

# Start components
echo -e "\n${GREEN}🚀 Starting components...${NC}"

# Kill any existing mosquitto on port 1883
echo -e "${YELLOW}Checking for existing Mosquitto process...${NC}"
pkill -f "mosquitto -v" 2>/dev/null || true
sleep 1

# Terminal 1: MQTT Broker
echo -e "\n${YELLOW}1️⃣ Starting MQTT Broker...${NC}"
mosquitto -v &
MQTT_PID=$!
sleep 2

# Terminal 2: Device Simulator (with TinyML)
echo -e "\n${YELLOW}2️⃣ Starting Device Simulator with TinyML...${NC}"
cd backend/HERA
source venv/bin/activate
$PYTHON_BIN device_simulator.py &
SIM_PID=$!
sleep 3

# Terminal 3: HERA Main Bot
echo -e "\n${YELLOW}3️⃣ Starting HERA Bot...${NC}"
$PYTHON_BIN main.py &
BOT_PID=$!
cd ../..

echo -e "\n${GREEN}✅ All components started!${NC}"
echo -e "${YELLOW}PIDs: MQTT=$MQTT_PID, Simulator=$SIM_PID, Bot=$BOT_PID${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all components...${NC}"

# Graceful shutdown
cleanup() {
    echo -e "\n${YELLOW}Stopping components...${NC}"
    kill $MQTT_PID $SIM_PID $BOT_PID 2>/dev/null
    wait 2>/dev/null
    echo -e "${GREEN}✅ Clean shutdown${NC}"
}

trap cleanup EXIT INT

# Wait for all processes
wait
