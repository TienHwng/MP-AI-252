# H.E.R.A. Evaluation Harness

This folder contains local scripts for collecting empirical numbers for the final report.
They do not generate fake results. Run them against your own board, MQTT broker, MongoDB,
backend APIs, and local Vite dashboard, then copy the CSV/JSON summaries into the report.

## Evaluation Matrix

| Component | Metric | Script | Output |
|---|---:|---|---|
| Firmware / MQTT | RPC round-trip latency, success rate, timeout rate | `python firmware_mqtt_rpc_latency.py` | `results/firmware_rpc_latency.csv`, summary JSON |
| Firmware / FreeRTOS | Heap stability over time from serial logs | `python firmware_heap_serial_logger.py` | `results/firmware_heap_serial.csv`, summary JSON |
| AI agents | Intent accuracy, tool-call success rate, inference latency | `python ai_agent_eval.py` | `results/ai_agent_eval.csv`, summary JSON |
| Database | Insert throughput, 24h query latency | `node db_benchmark.mjs` | `results/db_benchmark.json` |
| Web local | FloorPlan render timing, SSE-to-UI sync latency, Lighthouse | `node web_floorplan_perf.mjs` | `results/web_floorplan_perf.json`, optional Lighthouse JSON |

## Prerequisites

Install only what you need:

```powershell
pip install paho-mqtt pyserial requests
cd FE/hera-dashboard
npm install
npm install -D playwright lighthouse
cd ../../BE/Database
npm install
```

Start the usual local services in separate terminals:

```powershell
# MongoDB must be running locally.
cd BE/Database
node server.js

cd BE/HERA
python api_server.py

cd FE/hera-dashboard
npm run dev
```

For real firmware tests, keep the ESP32 powered and connected to the same MQTT broker
configured in `.env` / `BE/HERA/config.py`.

## Report Formulas

Use these definitions consistently:

| Metric | Formula |
|---|---|
| Success rate | `successful_trials / total_trials * 100` |
| Intent accuracy | `correct_intent_predictions / total_cases * 100` |
| Tool-calling success | `cases_with_all_expected_tools_ok / tool_cases * 100` |
| P50/P95 latency | percentile of per-request latency in milliseconds |
| Insert throughput | `inserted_documents / elapsed_seconds` |
| Heap drift | `last_free_heap_bytes - first_free_heap_bytes` |

