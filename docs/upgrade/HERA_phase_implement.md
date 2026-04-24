# HERA Phase-Based Implementation Roadmap
## A Practical, Ordered Plan to Turn `BE/HERA` into a Production-Ready Multi-Agent Smart-Home Runtime

**Project scope:** `MP-AI-252`, with the main focus on `BE/HERA`, while keeping MongoDB, MQTT, the dashboard, and the existing monorepo structure in mind.

**Purpose of this document:**
This file is the execution roadmap that sits *after* the architecture/design documents. Instead of describing only the target state, it describes **how to get there step by step**, with:

- clear implementation phases,
- what to build in each phase,
- what success looks like,
- what tech stack is needed in that phase,
- how to install that stack,
- how to integrate it into the existing repo,
- and how to run the project together with the new pieces so you can actually inspect the result.

---

# 1. Guiding Strategy

The biggest mistake in a project like HERA is to add too many technologies too early.

For HERA, the correct strategy is:

1. **Stabilize the runtime contracts first**
2. **Harden device execution and verification next**
3. **Rebuild memory on MongoDB correctly**
4. **Add observability and audit as first-class citizens**
5. **Only then add agent evaluation and model monitoring**
6. **Only later add optional systems like Redis or MLflow if the pain is real**

The stack should therefore be introduced in layers, not all at once.

---

# 2. Current Starting Point

Based on the current codebase, HERA already has:

- Python runtime in `BE/HERA`
- MongoDB usage already present in the codebase
- MQTT-based device interaction
- Telegram-based user interface
- a dashboard in `FE/hera-dashboard`
- a lightweight orchestrator + specialist agent pattern
- an existing `requirements.txt` with core Python dependencies
- no serious observability stack yet
- no formal workflow orchestration framework yet
- no dedicated distributed lock/cache layer yet
- no serious model monitoring layer yet

This is actually a good starting point.

---

# 3. Recommended Final Stack by the Time All Phases Are Complete

By the end of the roadmap, the target stack should look like this:

## Core runtime
- Python 3.11+
- LangGraph
- Pydantic v2
- existing HERA code for runtime logic
- MQTT / paho-mqtt
- LiteLLM / OpenAI / Ollama integrations already used in the repo

## Data and memory
- MongoDB
- MongoDB time-series collection for telemetry
- normal MongoDB collections for memory, audit, profiles, sessions

## Observability and operations
- OpenTelemetry SDK + instrumentation
- OpenTelemetry Collector
- Prometheus
- Grafana
- Alertmanager
- Sentry

## Agent / LLM observability
- Phoenix

## ML monitoring
- Evidently

## Optional later additions
- Redis (for locks/cache only if needed)
- MLflow 3 (for serious experiment/model lineage and training lifecycle)

---

# 4. Repo Layout Recommendation for New Infrastructure Files

Before going phase-by-phase, add a small `infra/` area to the repo so that all non-business-runtime operational files have a home.

Recommended new structure:

```text
MP-AI-252/
├── BE/
│   └── HERA/
├── FE/
├── firmware/
├── infra/
│   ├── compose/
│   │   ├── local.core.yml
│   │   ├── local.observability.yml
│   │   ├── local.phoenix.yml
│   │   └── local.mlops.yml
│   ├── otel/
│   │   └── collector.yaml
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   └── alerts.yml
│   ├── grafana/
│   │   ├── provisioning/
│   │   └── dashboards/
│   ├── alertmanager/
│   │   └── alertmanager.yml
│   ├── sentry/
│   │   └── README.md
│   └── scripts/
│       ├── dev-up.sh
│       ├── dev-down.sh
│       ├── run-hera.sh
│       ├── run-dashboard.sh
│       └── run-db-api.sh
├── docs/
└── requirements.txt
```

This layout matters because once observability enters the repo, the project stops being “just code” and becomes a **system**.

---

# 5. Phase 0 — Environment Stabilization and Baseline Local Developer Workflow

## Goal
Create a clean, repeatable local development baseline before introducing new architecture pieces.

## Why this comes first
If the local environment is unstable, every later phase becomes misleading. You need one reproducible command path for:

- Python backend
- MongoDB
- optional MQTT broker
- dashboard
- database API

## Deliverables
- `.env.example` for the monorepo root
- reproducible Python virtual environment setup
- reproducible frontend install
- one local startup script for the current system
- one health checklist documenting what “baseline working” means

## Tech stack introduced in this phase
No new major framework yet.

Use only:
- Python venv / pip
- Node / npm
- Docker Compose for local infra containers if desired
- existing MongoDB and MQTT assumptions

## Installation

### Python backend environment
From the repo root:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell
pip install -U pip
pip install -r requirements.txt
```

### Frontend environment

```bash
cd FE/hera-dashboard
npm install
cd ../..
```

### Database API environment

```bash
cd BE/Database
npm install
cd ../..
```

## Integration work

### 1. Add `.env.example`
Include at least:

```env
TELEGRAM_BOT_TOKEN=
MQTT_BROKER=localhost
MQTT_PORT=1883
OLLAMA_API_BASE=http://localhost:11434
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=
NORMAL_TEMP_MIN=25
NORMAL_TEMP_MAX=35
NORMAL_HUMI_MIN=60
NORMAL_HUMI_MAX=80
ANOMALY_THRESHOLD=0.5
ANOMALY_CRITICAL_THRESHOLD=0.8
MAX_TOOL_ITERATIONS=5
MAX_HISTORY=8
MONGO_URI=mongodb://localhost:27017
```

### 2. Add local run scripts
Example `infra/scripts/run-hera.sh`:

```bash
#!/usr/bin/env bash
set -e
source .venv/bin/activate
cd BE/HERA
python main.py
```

Example `infra/scripts/run-db-api.sh`:

```bash
#!/usr/bin/env bash
set -e
cd BE/Database
node server.js
```

Example `infra/scripts/run-dashboard.sh`:

```bash
#!/usr/bin/env bash
set -e
cd FE/hera-dashboard
npm run dev
```

### 3. Add a simple baseline compose file if you want a local DB + broker
Suggested `infra/compose/local.core.yml`:

```yaml
services:
  mongo:
    image: mongo:7
    container_name: hera-mongo
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  mqtt:
    image: eclipse-mosquitto:2
    container_name: hera-mqtt
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro

volumes:
  mongo_data:
```

## How to run this phase

### Option A — current code only
Terminal 1:

```bash
source .venv/bin/activate
cd BE/HERA
python main.py
```

Terminal 2:

```bash
cd BE/Database
node server.js
```

Terminal 3:

```bash
cd FE/hera-dashboard
npm run dev
```

### Option B — with core infra via Docker

```bash
docker compose -f infra/compose/local.core.yml up -d
```

Then run the 3 app processes above.

## How to inspect whether Phase 0 is healthy
- `BE/HERA` starts without immediate import/config crashes
- MongoDB is reachable
- MQTT is reachable
- DB API starts
- dashboard starts
- Telegram adapter can connect if token exists
- one simple device/sensor request still works

## Exit criteria
Do not move to Phase 1 until the local dev baseline is clean and documented.

---

# 6. Phase 1 — Introduce Strong Contracts and Workflow State

## Goal
Add **LangGraph** and formal runtime schemas without changing the product behavior too aggressively yet.

## Why this phase matters
Right now, HERA behaves like a working orchestrator + specialist system, but the flow is still too implicit.

This phase makes it explicit by introducing:
- graph state,
- typed input/output contracts,
- deterministic orchestration stages,
- clearer extension points.

## Deliverables
- LangGraph added to the backend
- `schemas/` package added under `BE/HERA`
- graph-based orchestrator skeleton added
- current behavior wrapped into a graph state model
- no major product-side feature changes yet

## Tech stack introduced in this phase
- LangGraph
- Pydantic v2 (already present, but now treated as first-class)

## Installation

### LangGraph

```bash
pip install -U langgraph
```

### LangChain (optional, only if you want some convenience helpers)

```bash
pip install -U langchain
```

### Pydantic
Already present in the repo, but if needed:

```bash
pip install -U pydantic
```

## Integration work

### 1. Add new folders
Suggested additions under `BE/HERA`:

```text
BE/HERA/
├── graph/
│   ├── state.py
│   ├── nodes.py
│   ├── edges.py
│   └── build_graph.py
├── schemas/
│   ├── request.py
│   ├── route.py
│   ├── tooling.py
│   ├── memory.py
│   └── audit.py
```

### 2. Define graph state
Example state categories:
- incoming request
- thread/session metadata
- route decision
- live state context
- specialist report
- tool result
- verification result
- final response draft

### 3. Wrap the current orchestrator inside a graph node
Do **not** rewrite everything at once.

Use this transition strategy:
- keep the current `agents/orchestrator.py`
- create `graph/nodes.py`
- call current orchestrator logic from a graph node
- gradually replace internal logic later

### 4. Add typed Pydantic models
At minimum:
- `IncomingRequest`
- `RouteDecision`
- `ToolProposal`
- `PolicyDecision`
- `VerificationResult`
- `ToolExecutionResult`
- `ActionSummary`

## How to run this phase
Keep the same application boot flow, but add a feature flag in `.env` such as:

```env
HERA_USE_LANGGRAPH=true
```

Then in `main.py`:
- if `false`, run legacy orchestrator
- if `true`, run graph orchestrator

This lets you compare old/new behavior without breaking the whole project.

## What to inspect
- same requests should still resolve correctly
- graph state should be inspectable in logs
- route decisions should now be structured objects, not loose strings only
- failures should be easier to localize by stage

## Exit criteria
Move on only after the graph-based runtime can do the same core requests as the old runtime.

---

# 7. Phase 2 — Split Runtime Responsibilities and Harden Device Execution

## Goal
Turn HERA from “planner + executor blur” into a proper controlled action runtime.

## Why this phase matters
This is where HERA starts becoming *real* rather than merely clever.

The runtime must explicitly separate:
- proposal
- policy
- execution
- verification
- audit

## Deliverables
- `tool_registry.py` split into smaller services
- `policy_engine.py` introduced
- `verification_service.py` introduced
- device execution lifecycle normalized
- action result structure standardized

## Tech stack introduced in this phase
No major external platform yet.

Still mostly custom HERA code, using:
- LangGraph
- Pydantic
- existing MQTT + Mongo dependencies

## Installation
No new mandatory package beyond what Phase 1 already introduced.

## Integration work

### 1. Add new runtime packages

```text
BE/HERA/
├── runtime/
│   ├── tool_runner.py
│   ├── policy_engine.py
│   ├── verification_service.py
│   ├── capability_registry.py
│   └── execution_context.py
├── services/
│   ├── device_resolver.py
│   ├── device_executor.py
│   ├── device_verifier.py
│   └── device_state_service.py
```

### 2. Change the flow
Target execution flow:

```text
user request
-> route decision
-> specialist tool proposal
-> policy decision
-> execution
-> verification
-> audit write
-> memory write
-> final response
```

### 3. Keep the current MQTT service, but move “authority” away from specialists
The specialist should propose.
The runtime should decide and execute.

### 4. Add verification states
Suggested values:
- `verified`
- `unverified`
- `timeout`
- `rejected`
- `noop`
- `offline`

## How to run this phase
Same startup commands as before.

Add a dev test mode with a simulator and a mock verifier if the physical device is not always available.

Example `.env` flags:

```env
HERA_ENABLE_POLICY_ENGINE=true
HERA_ENABLE_VERIFICATION=true
HERA_ENABLE_ACTION_AUDIT=true
```

## What to inspect
- a tool action is no longer considered successful just because publish succeeded
- verification failures are visible
- policy decisions are explicit
- the same user request can now produce richer outcomes like `ask`, `deny`, `noop`, `offline`

## Exit criteria
Do not proceed until physical-control behavior is trustworthy and explainable.

---

# 8. Phase 3 — Rebuild Memory on MongoDB the Right Way

## Goal
Add serious AI memory using the **existing MongoDB setup**, instead of introducing a second database too early.

## Why this phase matters
Without memory, the agent remains stateless and brittle.
With badly designed memory, it becomes chaotic.

The right answer for HERA right now is **structured Mongo-backed memory**, not an additional database.

## Deliverables
- `session_threads` collection
- `action_summaries` collection
- `user_profiles` collection
- `tool_audit_logs` collection
- retrieval layer for operational context injection
- background consolidation job for profile updates

## Tech stack introduced in this phase
No new database required.

Use:
- MongoDB (existing)
- MongoDB time-series for telemetry (existing direction)
- custom memory service in HERA
- APScheduler already exists in dependencies and can be used for simple background jobs

## Installation
No new mandatory package if `pymongo` is already installed.

If you want a scheduler service in-process and APScheduler is not already installed, install it:

```bash
pip install APScheduler
```

(Your repo already has `APScheduler` in `requirements.txt`.)

## Integration work

### 1. Add memory services

```text
BE/HERA/
├── memory/
│   ├── session_store.py
│   ├── action_summary_store.py
│   ├── profile_store.py
│   ├── retrieval_service.py
│   └── consolidation_job.py
```

### 2. Add Mongo collections
Recommended collections:
- `session_threads`
- `action_summaries`
- `user_profiles`
- `tool_audit_logs`
- `telemetry_points` (keep for time-series)

### 3. Add retrieval orchestration
Each request should load:
- live context
- recent actions
- stable user profile

### 4. Add write policy
- write session updates frequently
- write action summaries after significant tool actions
- write user profile slowly, through consolidation or clear promotion rules

## How to run this phase
No new standalone service is required yet.

You just need Mongo running plus the app.

If using Docker:

```bash
docker compose -f infra/compose/local.core.yml up -d
```

Then run HERA and confirm the new collections are being populated.

## What to inspect
- follow-up requests like “turn off the one I just turned on” work
- aliases can survive across sessions
- recent action summaries can be retrieved quickly
- profile updates do not spam writes every second

## Exit criteria
Only move on once memory improves continuity *without* making the system unpredictable.

---

# 9. Phase 4 — Add OpenTelemetry, Prometheus, Grafana, and Alertmanager

## Goal
Create the first serious observability layer for HERA.

## Why this phase matters
At this point the runtime is becoming more complex, so you need to know:
- what happened,
- how long it took,
- where it failed,
- and whether the whole system is healthy.

## Deliverables
- OpenTelemetry instrumentation in `BE/HERA`
- OpenTelemetry Collector config
- Prometheus scraping config
- Grafana dashboards
- Alertmanager routing config

## Tech stack introduced in this phase
- OpenTelemetry SDK for Python
- OpenTelemetry Collector
- Prometheus
- Grafana
- Alertmanager

## Installation

### Python OpenTelemetry packages
Install the minimal instrumentation set:

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp \
  opentelemetry-instrumentation-logging opentelemetry-instrumentation-pymongo \
  opentelemetry-instrumentation-requests
```

If you later expose HTTP APIs from Python, add the web-framework instrumentation you actually use.

### OpenTelemetry Collector
Example Docker image strategy:

```bash
docker pull otel/opentelemetry-collector
```

### Prometheus

```bash
docker pull prom/prometheus
```

### Alertmanager

```bash
docker pull prom/alertmanager
```

### Grafana

```bash
docker pull grafana/grafana
```

## Integration work

### 1. Add local observability compose file
Suggested `infra/compose/local.observability.yml`:

```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector
    container_name: hera-otel-collector
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ../otel/collector.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"
      - "4318:4318"

  prometheus:
    image: prom/prometheus
    container_name: hera-prometheus
    volumes:
      - ../prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ../prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
    ports:
      - "9090:9090"

  alertmanager:
    image: prom/alertmanager
    container_name: hera-alertmanager
    volumes:
      - ../alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "9093:9093"

  grafana:
    image: grafana/grafana
    container_name: hera-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ../grafana/provisioning:/etc/grafana/provisioning
      - ../grafana/dashboards:/var/lib/grafana/dashboards

volumes:
  grafana_data:
```

### 2. Instrument HERA startup
In `main.py`, initialize OpenTelemetry as early as possible.

Suggested new file:

```text
BE/HERA/observability/otel.py
```

Responsibilities:
- create resource metadata (`service.name=hera-runtime`)
- configure OTLP exporter endpoint
- instrument logging
- instrument Mongo requests if used from Python side
- create helper functions for spans around specialist/tool execution

### 3. Add metrics namespaces
Suggested metrics:
- `hera_requests_total`
- `hera_request_latency_ms`
- `hera_route_decisions_total`
- `hera_tool_calls_total`
- `hera_tool_timeouts_total`
- `hera_verification_failures_total`
- `hera_mqtt_publish_latency_ms`
- `hera_memory_load_latency_ms`
- `hera_policy_denials_total`

### 4. Add dashboards
At minimum add dashboards for:
- runtime health
- tool execution
- verification outcomes
- specialist latency
- MQTT/device outcomes

## How to run this phase

### Start infra

```bash
docker compose \
  -f infra/compose/local.core.yml \
  -f infra/compose/local.observability.yml \
  up -d
```

### Start app processes
Run HERA, DB API, dashboard as before.

### Inspect
- Grafana at port `3000`
- Prometheus at port `9090`
- Alertmanager at port `9093`

## What to inspect
- traces/spans exist for requests
- metrics are scraped
- dashboards move when you interact with HERA
- at least one synthetic alert can fire during testing

## Exit criteria
You should now be able to answer: “What is the system doing right now, and what is failing?”

---

# 10. Phase 5 — Add Sentry for Error Monitoring and Incident Visibility

## Goal
Catch crashes, exceptions, and bad runtime incidents quickly.

## Why this phase matters
Prometheus tells you numbers.
Sentry tells you what exception happened, where, and in which release.

## Deliverables
- Sentry SDK installed in Python runtime
- Sentry initialized in HERA
- release/environment tags added
- optional OpenAI integration enabled

## Tech stack introduced in this phase
- Sentry SDK

## Installation

```bash
pip install "sentry-sdk[openai]"
```

If token accounting for streaming outputs matters, keep `tiktoken` installed as well.

## Integration work

### 1. Add `.env` entries

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=local
SENTRY_RELEASE=hera-dev
```

### 2. Add `BE/HERA/observability/sentry_setup.py`
Initialize Sentry near startup, before major runtime actions begin.

### 3. Add tags/contexts
Useful tags:
- provider
- model_name
- specialist
- environment
- git_sha

### 4. Capture runtime exceptions carefully
You do *not* want every tool verification failure to be an exception.
Distinguish between:
- expected operational outcome (`offline`, `timeout`, `ask`, `noop`)
- real software defect (raise/capture)

## How to run this phase
No extra local container is required if you use hosted Sentry.

If you do not want hosted Sentry in local-only development, guard it with:

```env
HERA_ENABLE_SENTRY=false
```

## What to inspect
- a forced exception in a test path reaches Sentry
- OpenAI / LLM spans appear if configured
- errors are grouped meaningfully

## Exit criteria
You can now answer: “What code path crashed, with what context, in which release?”

---

# 11. Phase 6 — Add Phoenix for Agent and LLM Observability

## Goal
See inside the agent/runtime workflow at the LLM and tool-call level.

## Why this phase matters
Generic tracing is not enough once you care about:
- prompt inputs,
- route quality,
- tool-call reasoning,
- evaluation and regression of the agent flow.

## Deliverables
- local Phoenix instance
- traces from HERA sent into Phoenix
- project separation for HERA runs
- basic eval workflow using captured traces

## Tech stack introduced in this phase
- Phoenix (self-hosted locally first)
- OpenTelemetry/OpenInference-compatible trace emission

## Installation

### Simplest local Phoenix install

```bash
pip install arize-phoenix
```

Start locally:

```bash
phoenix serve
```

Phoenix will typically be available at port `6006`.

## Integration work

### 1. Add local Phoenix compose or terminal workflow
For the simplest developer flow, it is okay to run Phoenix in its own terminal.

If you want Dockerized local infra later, add a dedicated `local.phoenix.yml` file.

### 2. Add trace export routing
Either:
- export via OTLP and point to Phoenix-compatible ingestion path, or
- use the Phoenix-specific recommended setup for tracing in code

### 3. Tag traces consistently
Recommended trace attributes:
- `hera.user_id`
- `hera.thread_id`
- `hera.specialist`
- `hera.provider`
- `hera.model`
- `hera.tool_name`
- `hera.verification_status`
- `hera.policy_outcome`

### 4. Use Phoenix only for the agent/LLM layer
Do not try to make Phoenix your full observability stack.
It complements Prometheus/Grafana/Sentry; it does not replace them.

## How to run this phase
Terminal A:

```bash
phoenix serve
```

Terminal B/C/D:
- HERA
- DB API
- dashboard

Or combine Phoenix into a later compose stack if you prefer.

## What to inspect
- agent traces appear per request
- tool-call steps are visible
- prompt/policy/verification regressions are easier to debug
- you can inspect exact bad runs instead of guessing from logs

## Exit criteria
You can now answer: “Why did the agent make this decision?”

---

# 12. Phase 7 — Add Evidently for Drift and Model Monitoring

## Goal
Track whether anomaly detection and personalization models are degrading over time.

## Why this phase matters
A model can keep “running” while getting worse.
You need to catch that.

## Deliverables
- Evidently installed
- drift/quality jobs created
- baseline dataset snapshots defined
- reports generated on a schedule

## Tech stack introduced in this phase
- Evidently

## Installation

```bash
pip install evidently
```

If you later evaluate LLM-heavy use cases with Evidently’s optional extras:

```bash
pip install "evidently[llm]"
```

## Integration work

### 1. Add monitoring jobs folder

```text
BE/HERA/mlops/
├── evidently_jobs/
│   ├── anomaly_drift_job.py
│   ├── personalization_drift_job.py
│   └── report_writer.py
```

### 2. Define reference datasets
For example:
- anomaly model baseline on known-good telemetry windows
- personalization model baseline from a stable historical period

### 3. Schedule batch monitoring
Use APScheduler first.
If it becomes too large later, move to a dedicated scheduler/orchestrator.

### 4. Write report outputs to Mongo or filesystem
Recommendation:
- keep the report artifact on disk or object storage,
- store summary metadata in Mongo.

## How to run this phase
The simplest first version is *not* a permanent service.
It can be a scheduled Python job.

Example:

```bash
source .venv/bin/activate
python BE/HERA/mlops/evidently_jobs/anomaly_drift_job.py
```

Later, connect it to APScheduler inside a small worker process.

## What to inspect
- drift reports generate consistently
- you can detect baseline shifts
- false positives in anomaly scores become visible over time

## Exit criteria
You can now answer: “Is the model still behaving like it used to?”

---

# 13. Phase 8 — Add Optional Redis for Locking and Fast Ephemeral State

## Goal
Only add Redis if concurrency, duplicate actions, or ephemeral coordination become painful.

## Why this is optional
Redis is useful, but many teams add it too early.
For HERA, it should be justified by real problems such as:
- multiple workers issuing device actions,
- device-level locks,
- cooldown windows,
- short-lived cross-process state.

## Deliverables
Only if needed:
- Redis container/service
- per-device action lock
- idempotency or cooldown cache

## Tech stack introduced in this phase
- Redis
- Python Redis client

## Installation

### Python client

```bash
pip install redis
```

### Redis container

```bash
docker pull redis:7
```

## Integration work

### 1. Add compose service when needed
Add to a new compose layer or to `local.core.yml` only once it is truly necessary.

### 2. Limit Redis usage to a narrow purpose
Use it for:
- locks
- cooldown TTLs
- temporary request coordination

Do **not** move all memory into Redis.
Mongo should remain the source of truth for memory/audit.

## How to run this phase
If added via compose:

```bash
docker compose \
  -f infra/compose/local.core.yml \
  -f infra/compose/local.observability.yml \
  up -d
```

(or add a Redis-specific compose file if you prefer cleaner layering.)

## What to inspect
- conflicting device actions are throttled or serialized
- duplicate requests are suppressed when appropriate
- Redis is not used as a dumping ground

## Exit criteria
Redis should solve a specific runtime pain, not just exist.

---

# 14. Phase 9 — Add MLflow 3 Only When Training and Model Lineage Become Real Needs

## Goal
Track experiments, models, metrics, and training lineage for personalization/anomaly components once those parts are mature enough.

## Why this is not earlier
MLflow is extremely valuable when model development becomes a real lifecycle.
It is unnecessary overhead if you are still stabilizing the runtime and not yet running disciplined experiments.

## Deliverables
Only when justified:
- MLflow tracking server
- experiment logging from training jobs
- model/version lineage
- training/evaluation registry practices

## Tech stack introduced in this phase
- MLflow 3

## Installation

```bash
pip install "mlflow>=3.1"
```

For a quick local UI:

```bash
mlflow server --port 5000
```

## Integration work

### 1. Add training job packages

```text
BE/HERA/ml/
├── training/
├── evaluation/
└── tracking/
```

### 2. Log experiments from training code
Use MLflow only in training/evaluation pipelines, not in the hot runtime path.

### 3. Keep runtime and training concerns separate
The online HERA runtime should consume selected model artifacts, not perform experiment tracking itself on every request.

## How to run this phase
Terminal A:

```bash
mlflow server --port 5000
```

Then run training/evaluation scripts that log to MLflow.

## What to inspect
- experiments appear in the UI
- metrics and artifacts are versioned
- best model selection becomes reproducible

## Exit criteria
You can now answer: “Which model version produced this behavior, and why was it deployed?”

---

# 15. Recommended Phase-by-Phase Stack Summary

## Phase 0 — Baseline local environment
**Stack:** Python, pip, Node, npm, Docker Compose, MongoDB, MQTT

## Phase 1 — Contracts and workflow state
**Add:** LangGraph, Pydantic-first contract discipline

## Phase 2 — Runtime hardening
**Add:** custom HERA runtime modules only (policy, verification, tool runner)

## Phase 3 — Memory redesign
**Add:** structured Mongo memory collections, APScheduler-based consolidation jobs

## Phase 4 — Observability foundation
**Add:** OpenTelemetry, Collector, Prometheus, Grafana, Alertmanager

## Phase 5 — Error monitoring
**Add:** Sentry

## Phase 6 — Agent/LLM observability
**Add:** Phoenix

## Phase 7 — ML monitoring
**Add:** Evidently

## Phase 8 — Optional runtime coordination
**Add only if needed:** Redis

## Phase 9 — Optional training lifecycle
**Add only if needed:** MLflow 3

---

# 16. How to Start Everything Together During Development

The easiest development strategy is layered startup.

## Layer A — Core app/data layer
Start:
- MongoDB
- MQTT broker
- HERA runtime
- DB API
- dashboard

## Layer B — Observability layer
Start:
- OpenTelemetry Collector
- Prometheus
- Grafana
- Alertmanager
- optionally Sentry (hosted, no local process needed)

## Layer C — Agent/ML tooling layer
Start only when needed:
- Phoenix
- Evidently jobs
- MLflow
- Redis

---

# 17. Recommended Developer Startup Commands by Stage

## Minimal core run

```bash
docker compose -f infra/compose/local.core.yml up -d
```

Then manually:

```bash
# terminal 1
source .venv/bin/activate
cd BE/HERA
python main.py

# terminal 2
cd BE/Database
node server.js

# terminal 3
cd FE/hera-dashboard
npm run dev
```

## Core + observability

```bash
docker compose \
  -f infra/compose/local.core.yml \
  -f infra/compose/local.observability.yml \
  up -d
```

Then run HERA + DB API + dashboard manually.

## Core + observability + Phoenix

```bash
docker compose \
  -f infra/compose/local.core.yml \
  -f infra/compose/local.observability.yml \
  up -d
```

Then separately:

```bash
phoenix serve
```

## Optional MLflow

```bash
mlflow server --port 5000
```

---

# 18. What You Should Absolutely Avoid

## Do not install every platform in Phase 1
That will create noise and slow down real engineering progress.

## Do not add Redis before you have a real concurrency pain
It will complicate the stack without making the system safer by itself.

## Do not add MLflow before you have a real model lifecycle
It is not a substitute for runtime observability.

## Do not let Phoenix replace Prometheus/Grafana/Sentry
Phoenix is excellent for agent/LLM tracing, but it is not your full operations stack.

## Do not use Mongo time-series as a replacement for every kind of memory
Telemetry belongs there. Session/action/profile memory does not.

---

# 19. Best Practical Rollout Order

If you want the most practical sequence with the least wasted effort, use this exact order:

1. **Phase 0** — local baseline
2. **Phase 1** — LangGraph + contracts
3. **Phase 2** — runtime hardening (policy/verification/tool runner)
4. **Phase 3** — Mongo memory redesign
5. **Phase 4** — OpenTelemetry + Prometheus + Grafana + Alertmanager
6. **Phase 5** — Sentry
7. **Phase 6** — Phoenix
8. **Phase 7** — Evidently
9. **Phase 8** — Redis only if needed
10. **Phase 9** — MLflow only when training/personalization lifecycle is mature

This order gives you the highest engineering return per unit of complexity.

---

# 20. Final Recommendation

If you are actually going to implement this and not just document it, the right mindset is:

- keep the stack small at the beginning,
- make each phase deliver visible value,
- do not chase “enterprise-looking architecture” too early,
- and only introduce a new tool when a concrete operational pain appears.

For HERA specifically:

- **MongoDB remains good enough for memory through the early serious phases**
- **LangGraph should be the first major framework addition**
- **OpenTelemetry + Prometheus/Grafana should be the first major MLOps/ops addition**
- **Phoenix should be added once you want to debug agent behavior deeply**
- **Redis and MLflow should remain conditional, not assumed**

That is the most disciplined way to turn HERA into a system that is not only smart, but also understandable, monitorable, and maintainable.

---

# 21. Quick Checklist

## Before Phase 1
- [ ] `.env.example` exists
- [ ] local scripts exist
- [ ] Mongo runs
- [ ] MQTT runs
- [ ] HERA starts cleanly
- [ ] dashboard starts cleanly

## Before Phase 4
- [ ] contracts are typed
- [ ] route decisions are structured
- [ ] policy exists
- [ ] verification exists
- [ ] memory collections exist

## Before Phase 6
- [ ] OpenTelemetry spans exist
- [ ] Prometheus metrics exist
- [ ] Grafana dashboard exists
- [ ] alerts can fire in test
- [ ] Sentry can catch real exceptions

## Before Phase 9
- [ ] personalization training is real
- [ ] model versions matter
- [ ] evaluation datasets exist
- [ ] lineage and reproducibility are now required

---

# 22. Suggested Companion Files to Create After This Document

After this roadmap, the next most useful artifacts would be:

1. `HERA_memory_schema_and_indexes.md`
2. `HERA_observability_metric_log_alert_catalog.md`
3. `infra/compose/local.core.yml`
4. `infra/compose/local.observability.yml`
5. `infra/otel/collector.yaml`
6. `infra/prometheus/prometheus.yml`
7. `infra/prometheus/alerts.yml`
8. `infra/grafana/provisioning/*`
9. `infra/scripts/dev-up.sh`
10. `infra/scripts/dev-down.sh`

Those files will turn this roadmap from planning into implementation.


---

# Appendix A — Notes on Install Commands

The installation examples in this roadmap were chosen to stay close to the official documentation for the relevant tools at the time this file was written. In practice, you should still pin exact versions in your own `requirements.txt`, lockfiles, or Compose files before using them in a team setting.

Suggested policy:

- use `pip install -U ...` only during initial experimentation,
- pin exact versions once the team agrees on a working combination,
- prefer Docker/Compose for infrastructure services,
- keep Python app dependencies pinned in `requirements.txt`,
- and document every environment variable needed to start the stack.

