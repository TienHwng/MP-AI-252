### MQTT
{
  "total": 100,
  "successful": 100,
  "success_rate_percent": 100.0,
  "timeout_count": 0,
  "latency_ms": {
    "mean": 1.391,
    "median": 1.163,
    "p95": 2.601,
    "min": 0.76,
    "max": 5.998
  }
}

python docs/evaluation/firmware_mqtt_rpc_latency.py --broker 10.0.2.131 --count 100

python docs/evaluation/firmware_heap_serial_logger.py --port COM5 --duration-sec 1800

python docs/evaluation/ai_agent_eval.py --provider-label ollama-local
python docs/evaluation/ai_agent_eval.py --provider-label openrouter-cloud

node docs/evaluation/db_benchmark.mjs --count 17280 --api http://localhost:3001

node docs/evaluation/web_floorplan_perf.mjs --url http://localhost:5173 --lighthouse
