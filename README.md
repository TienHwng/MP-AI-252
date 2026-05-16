# MP-AI-252: HERA AIoT Assistant

HERA is an AIoT project that combines a multi-agent assistant, MQTT-based device control, telemetry persistence, and a realtime monitoring dashboard.

This repository focuses on the practical local-development stack:
- Multi-agent runtime: Python (`backend/HERA`)
- MQTT infrastructure + simulator: Python (`backend/MQTT_Broker`)
- Data/API layer: Node.js + MongoDB (`backend/Database`)
- Dashboard: React + Vite (`frontend/hera-dashboard`)
- Device firmware: ESP32 + PlatformIO (`firmware`)

## Core Capabilities

- Telegram-driven AI assistant for smart-home style commands
- Intent routing to specialist agents (device control, sensor analysis, anomaly analysis, web research)
- MQTT-based command and telemetry pipeline
- Live telemetry ingestion and persistence in MongoDB
- Dashboard for login, device control, analytics, and model settings
- Voice command input and optional Google TTS spoken replies in the dashboard
  assistant; speech is transcribed to text and handled by the same HERA orchestration pipeline
- Switchable LLM provider strategy (OpenRouter or Ollama)

## System Overview

End-to-end flow:
1. User sends a message to the Telegram bot.
2. `Orchestrator` classifies intent and delegates to a specialist agent.
3. Tool execution publishes MQTT RPC commands when needed.
4. Device/simulator publishes telemetry and attributes.
5. MQTT manager can persist telemetry into MongoDB.
6. Database API serves telemetry/settings to the dashboard.

Main runtime entry points:
- HERA runtime: `backend/HERA/main.py`
- HERA dashboard API: `backend/HERA/api_server.py`
- MQTT manager: `backend/MQTT_Broker/mqtt_manager.py`
- MQTT simulator: `backend/MQTT_Broker/mqtt_simulator.py`
- API server: `backend/Database/server.js`

## MQTT Topics

- Telemetry: `v1/devices/me/telemetry`
- RPC request: `v1/devices/me/rpc/request/+`
- RPC response: `v1/devices/me/rpc/response/+`
- Attributes: `v1/devices/me/attributes`

## Repository Layout

```text
MP-AI-252/
|- backend/
|  |- HERA/               # Multi-agent runtime (Telegram adapter, agents, tools)
|  |- MQTT_Broker/        # Local broker manager and simulator scripts
|  |- Database/           # Express API + MongoDB integration
|  |- Telegram Bot/       # Utility scripts
|- frontend/
|  |- hera-dashboard/     # Main React dashboard
|- firmware/              # PlatformIO firmware for ESP32 board
|- docs/                  # Thesis and technical documents
|- setup.ps1              # Windows setup bootstrap script
|- requirements.txt
| README.md
```

## Prerequisites

- Python 3.12
- Node.js 18+ and npm
- MongoDB (default local URI)
- Telegram bot token
- LLM provider access:
  - OpenRouter API key, or
  - Local Ollama service

## Setup

### 1. Python dependencies

From repository root:

```powershell
.\setup.ps1
```

To keep `.venv` activated in the current shell:

```powershell
. .\setup.ps1
```

### 2. Frontend and API dependencies

```powershell
cd backend\Database
npm install

cd ..\..\frontend\hera-dashboard
npm install
```

### 3. Environment configuration

Use `.env.example` at repository root as the source of truth for runtime variables.

At minimum, ensure values for:
- Telegram token
- MQTT broker host/port
- MongoDB URI/database
- LLM provider credentials/endpoints

## Run The System

### Option A: VS Code task (recommended)

Run task: `Start All (VSCode Terminal)`

This starts all major services in parallel:
- MQTT simulator
- MQTT manager
- Database API
- HERA runtime
- Dashboard

### Option B: Manual terminals

Activate Python env first in Python terminals:

```powershell
.\.venv\Scripts\Activate.ps1
```

Terminal 1 - MQTT manager:

```powershell
cd backend\MQTT_Broker
python mqtt_manager.py
```

Terminal 2 - MQTT simulator (simulation mode):

```powershell
cd backend\MQTT_Broker
python mqtt_simulator.py
```

Terminal 3 - Database API:

```powershell
cd backend\Database
node server.js
```

Terminal 4 - HERA runtime:

```powershell
cd backend\HERA
python main.py
```

Terminal 5 - HERA dashboard API:

```powershell
cd backend\HERA
python api_server.py
```

Terminal 6 - Dashboard:

```powershell
cd frontend\hera-dashboard
npm run dev
```

## Local Endpoints

- Dashboard: http://localhost:5173
- Database API: http://localhost:3001
- HERA dashboard API: http://localhost:3002

Key API routes (Database service):
- `POST /api/auth/login`
- `POST /api/device/claim`
- `GET /api/telemetry`
- `GET /api/sensors/latest`
- `GET /api/sensors/stream`
- `GET /api/settings/models`
- `PUT /api/settings/models`

Key API routes (HERA dashboard service):
- `GET /api/runtime/status`
- `GET /api/devices/status`
- `POST /api/devices/:target/state`
- `POST /api/sensors/:sensor/value` (simulation mode only)
- `POST /api/assistant/message` (accepts `source: "voice"` for transcribed voice commands)
- `POST /api/assistant/tts` (Google TTS Vietnamese MP3 response audio)

## Runtime Modes

- Simulation mode:
  - `MODE=sim`
  - Run `mqtt_simulator.py`

- Hardware mode:
  - `MODE=real`
  - Skip simulator
  - Connect firmware device to the same broker

## Firmware Quick Note

Optional commands:

```powershell
cd firmware
platformio run --target upload
platformio device monitor --baud 115200
```

Before flashing, review board/network settings in:
- `firmware/src/global.cpp`
- `firmware/src/mqtt_handle.cpp`

## Troubleshooting

- HERA exits immediately:
  - Verify Telegram token
  - If using OpenRouter, verify API key and endpoint

- Dashboard has no data:
  - Check MongoDB is running
  - Check `mqtt_manager.py` is running
  - Check telemetry source (simulator or hardware)

- MQTT errors or no command execution:
  - Ensure all services share the same MQTT host/port
  - Verify broker bind host is reachable from all processes

- Model provider mismatch:
  - Provider/model settings can be updated from Dashboard Settings
  - Persisted settings are loaded from MongoDB model settings

## Project Notes

- `docs/` contains thesis and design documents.
- README is intentionally focused on current development and operations, not full research-level detail.
