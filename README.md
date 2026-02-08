# AIoT Virtual Assistant: Voice-Controlled Smart Home Automation

**A next-generation AIoT system that bridges the gap between Natural Language Processing (NLP) and Physical Computing.**

This project implements a **Virtual Voice Assistant** capable of understanding human speech and controlling smart home devices via the **YOLO UNO ESP32-S3** (or YoLo:Bit) board. Unlike traditional IoT systems that rely on rigid app buttons, this assistant uses a "Brain" (High-Level AI) to interpret intent and a "Body" (Low-Level Firmware) to execute actions.

---

## 📖 Table of Contents

- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Development Roadmap](#-development-roadmap)
- [Hardware Setup](#-hardware-setup)
- [Installation & Usage](#-installation--usage)
- [Configuration Guide](#-configuration-guide)
- [Communication Protocol](#-communication-protocol)
- [Tech Stack](#-tech-stack)

---

## 🏗 System Architecture

The system is strictly divided into **two main layers**, communicating via **MQTT** (or Serial for debugging).

### 1. High-Level Layer (The Brain) - `backend/`
- **Role:** Perception & Decision Making.
- **Platform:** Python (PC / Raspberry Pi / Cloud Server).
- **Core Functions:**
  - **STT (Speech-to-Text):** Converts audio to text (Google Speech / OpenAI Whisper).
  - **NLP (Natural Language Processing):** Extracts **Intents** (e.g., `TURN_ON`) and **Entities** (e.g., `LIVING_ROOM_LIGHT`).
  - **TTS (Text-to-Speech):** Provides vocal feedback to the user.
  - **Central Logic:** Decides commands based on sensor data and user requests.

### 2. Low-Level Layer (The Body) - `firmware/`
- **Role:** Execution & Sensing.
- **Platform:** ESP32-S3 (Yolo UNO) / ESP32.
- **Core Functions:**
  - **Actuation:** Controls Relays, LEDs, Fans based on JSON commands.
  - **Sensing:** Monitors DHT20 (Temp/Humi), Light sensors.
  - **Connectivity:** Maintains WiFi/MQTT connection.

### 3. Frontend Layer (The Face) - `frontend/`
- **Role:** Visualization & Manual Control.
- **Platform:** Web Technologies (HTML/JS).
- **Core Functions:**
  - Real-time Dashboard for environmental monitoring.
  - System status and manual override controls.

---

## 📂 Project Structure

The repository follows a clean **Monorepo** structure:

```text
AIoT-Assistant/
├── backend/                   # [High-Level] AI Brain & Logic
│   ├── .venv/                 # Python Virtual Environment
│   ├── ai_modules/            # STT, TTS, and NLP Engines
│   ├── mqtt_server/           # MQTT Broker & Client Logic
│   ├── main.py                # Main Entry Point
│   └── requirements.txt       # Python Dependencies
│
├── firmware/                  # [Low-Level] ESP32 Firmware
│   ├── src/                   # Source Code (main.cpp, tasks)
│   ├── include/               # Headers (.configuration.h, secrets.h)
│   ├── lib/                   # External Libraries (DHT20, ArduinoJson)
│   └── platformio.ini         # Board Configuration
│
├── frontend/                  # [UI] Web Dashboard
│   ├── index.html             # Main Dashboard
│   ├── style.css
│   └── script.js              # WebSocket/API Logic
│
└── README.md                  # Project Documentation