# Final Database Design for HERA Dashboard

## 1) Objective

This document defines the final minimal schema to support:
- Real-time command lifecycle logging
- Real-time and historical telemetry dashboards
- Intent, agent routing, and latency tracking
- System error debugging

Final direction: use PostgreSQL as the primary database.

---

## 2) Final Schema

### 2.1 Table commands

One record for one user command.

```sql
CREATE TABLE commands (
  command_id      TEXT PRIMARY KEY,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

  chat_id         TEXT NOT NULL,
  device_id       TEXT NOT NULL,

  provider        TEXT NOT NULL,
  intent          TEXT NOT NULL,
  agent           TEXT NOT NULL,
  tool            TEXT,
  method          TEXT,
  params          JSONB NOT NULL DEFAULT '{}'::jsonb,

  user_text       TEXT NOT NULL,
  response_text   TEXT,

  status          TEXT NOT NULL DEFAULT 'pending',
  latency_ms      INTEGER,
  error_message   TEXT
);

CREATE INDEX idx_commands_chat_created
  ON commands(chat_id, created_at DESC);

CREATE INDEX idx_commands_device_created
  ON commands(device_id, created_at DESC);

CREATE INDEX idx_commands_status_created
  ON commands(status, created_at DESC);
```

### 2.2 Table command_steps

Detailed timeline steps for each command.

```sql
CREATE TABLE command_steps (
  id              BIGSERIAL PRIMARY KEY,
  command_id      TEXT NOT NULL REFERENCES commands(command_id) ON DELETE CASCADE,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),

  step            TEXT NOT NULL,
  source          TEXT NOT NULL,
  message         TEXT,

  state_before    JSONB,
  state_after     JSONB,
  meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_command_steps_cmd_ts
  ON command_steps(command_id, ts);

CREATE INDEX idx_command_steps_step_ts
  ON command_steps(step, ts DESC);
```

Expected step values:
- issued
- published
- received
- applied
- ack_sent
- observed
- failed
- timeout

### 2.3 Table telemetry_points

Time-series telemetry from simulator or firmware.

```sql
CREATE TABLE telemetry_points (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id       TEXT NOT NULL,

  temperature     NUMERIC(5,2),
  humidity        NUMERIC(5,2),
  anomaly_score   NUMERIC(6,4),
  led_state       BOOLEAN,
  neo_led_state   BOOLEAN,

  payload         JSONB NOT NULL,
  ingest_source   TEXT NOT NULL DEFAULT 'mqtt',
  quality         TEXT NOT NULL DEFAULT 'good'
);

CREATE INDEX idx_telemetry_device_ts
  ON telemetry_points(device_id, ts DESC);

CREATE INDEX idx_telemetry_ts
  ON telemetry_points(ts DESC);
```

### 2.4 Table app_logs_raw (optional)

Use this when full-text raw log search is needed.

```sql
CREATE TABLE app_logs_raw (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  source          TEXT NOT NULL,
  level           TEXT NOT NULL,
  line            TEXT NOT NULL,
  meta            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_app_logs_raw_ts
  ON app_logs_raw(ts DESC);

CREATE INDEX idx_app_logs_raw_source_ts
  ON app_logs_raw(source, ts DESC);
```

---

## 3) Sample Logs for Each Table

### 3.1 Sample for commands

```json
{
  "command_id": "rpc-1042",
  "created_at": "2026-03-20T08:15:10.321Z",
  "chat_id": "73482910",
  "device_id": "esp32-sim-01",
  "provider": "openrouter",
  "intent": "device_control",
  "agent": "device_control",
  "tool": "turn_on_all_lights",
  "method": "setValueLedBlinky+setValueNeoLed",
  "params": {"led": true, "neo_led": true},
  "user_text": "turn on all lights",
  "response_text": "Both LEDs have been turned ON.",
  "status": "ok",
  "latency_ms": 4940,
  "error_message": null
}
```

### 3.2 Sample for command_steps

```json
[
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.330Z",
    "step": "issued",
    "source": "agent.device_control",
    "message": "Agent selected tool turn_on_all_lights",
    "state_before": {"led_state": false, "neo_led_state": false},
    "state_after": null,
    "meta": {"intent": "device_control", "agent": "device_control"}
  },
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.410Z",
    "step": "published",
    "source": "mqtt_service",
    "message": "Published RPC request",
    "state_before": null,
    "state_after": null,
    "meta": {
      "topic": "v1/devices/me/rpc/request/1042",
      "method": "setValueLedBlinky",
      "params": true
    }
  },
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.501Z",
    "step": "received",
    "source": "simulator",
    "message": "RPC received from broker",
    "state_before": {"led": false},
    "state_after": null,
    "meta": {"method": "setValueLedBlinky", "request_id": "1042"}
  },
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.515Z",
    "step": "applied",
    "source": "simulator",
    "message": "LedState -> ON",
    "state_before": {"led": false},
    "state_after": {"led": true},
    "meta": {"attribute_key": "LedState"}
  },
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.523Z",
    "step": "ack_sent",
    "source": "simulator",
    "message": "Published RPC response and attributes",
    "state_before": null,
    "state_after": null,
    "meta": {
      "rpc_response_topic": "v1/devices/me/rpc/response/1042",
      "attributes_topic": "v1/devices/me/attributes"
    }
  },
  {
    "command_id": "rpc-1042",
    "ts": "2026-03-20T08:15:10.620Z",
    "step": "observed",
    "source": "backend.observer",
    "message": "Backend observed state change from attributes or telemetry",
    "state_before": {"led_state": false, "neo_led_state": false},
    "state_after": {"led_state": true, "neo_led_state": true},
    "meta": {"last_updated": "08:15:10"}
  }
]
```

### 3.3 Sample for telemetry_points

```json
{
  "ts": "2026-03-20T08:15:11.002Z",
  "device_id": "esp32-sim-01",
  "temperature": 29.44,
  "humidity": 65.63,
  "anomaly_score": 0.2402,
  "led_state": true,
  "neo_led_state": true,
  "payload": {
    "temperature": 29.44,
    "humidity": 65.63,
    "inference_result": 0.2402,
    "led_state": true,
    "neo_led_state": true
  },
  "ingest_source": "simulator",
  "quality": "good"
}
```

### 3.4 Sample for app_logs_raw (optional)

```json
[
  {
    "ts": "2026-03-20T08:15:10.320Z",
    "source": "hera.orchestrator",
    "level": "INFO",
    "line": "[Orchestrator] intent='device_control' -> agent='device_control'",
    "meta": {"chat_id": "73482910", "command_id": "rpc-1042"}
  },
  {
    "ts": "2026-03-20T08:15:10.620Z",
    "source": "hera.orchestrator",
    "level": "INFO",
    "line": "[Orchestrator] done in 4.94s",
    "meta": {"chat_id": "73482910", "command_id": "rpc-1042", "latency_s": 4.94}
  },
  {
    "ts": "2026-03-20T08:15:11.002Z",
    "source": "simulator",
    "level": "INFO",
    "line": "[SIM] T=29.44C H=65.63% Anomaly=0.2402 LED=ON Neo=ON",
    "meta": {"device_id": "esp32-sim-01"}
  }
]
```

---

## 4) Why PostgreSQL Over MongoDB for This Problem

### 4.1 Strong Data Relationships

This system needs strict command lifecycle linkage by command_id:
- commands (one command)
- command_steps (multiple lifecycle steps)
- telemetry_points (observed state over time)

PostgreSQL is a better fit for joins, foreign keys, and timeline analytics in SQL.

### 4.2 Consistency and Auditability

You need to verify whether each command passed all required steps: issued -> published -> received -> applied -> observed.

PostgreSQL provides:
- Transactions
- Constraints
- Accurate final status updates

MongoDB can do this too, but it usually requires stronger app-layer discipline and is easier to drift.

### 4.3 Easier Dashboard and Reporting Queries

Typical queries include:
- Timeout rate by agent
- Average latency by intent
- Mismatch between applied and observed state

These are usually simpler, clearer, and easier to maintain in PostgreSQL SQL.

### 4.4 Time-Series Support Without Splitting Early

If telemetry volume grows, you can enable TimescaleDB on top of PostgreSQL.
This keeps one database platform instead of introducing multiple systems too early.

### 4.5 Conclusion

For this thesis and prototype scope:
- PostgreSQL is the best balance of complexity, correctness, and query power.
- MongoDB is not wrong, but it is not the optimal default for this lifecycle-heavy, highly-related data model.
