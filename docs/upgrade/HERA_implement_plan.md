# HERA `BE/HERA` Refactor and Implementation Plan

## From Lightweight Multi-Agent Orchestration to a Production-Ready Smart-Home Runtime

---

## 1. Purpose of This Document

This document is the implementation-oriented companion to the higher-level architecture memo for HERA.

Its purpose is to translate the current `BE/HERA` codebase into a concrete refactor plan that can be executed incrementally.

This document focuses on:

- the **actual role** of each current runtime module,
- the **gaps** between the current implementation and a production-ready system,
- a **target folder structure**,
- concrete **Python contracts and dataclasses**,
- how to redesign the current orchestrator/specialist/tooling flow,
- how to add policy, verification, memory, and observability,
- how to migrate safely without rewriting the entire project in one shot.

The goal is **not** to over-engineer the system or to add many unnecessary agents. The goal is to turn HERA into a **controlled smart-home action runtime** where:

- LLMs interpret and propose,
- deterministic runtime code decides and executes,
- every action is validated, verified, logged, and traceable.

---

## 2. Current `BE/HERA` Snapshot

Based on the current repository structure and code organization, `BE/HERA` already contains the core ingredients of a real multi-agent backend:

- `main.py` as the runtime entrypoint,
- adapters such as the Telegram adapter,
- specialist agents such as:
  - `device_agent.py`,
  - `sensor_agent.py`,
  - `anomaly_agent.py`,
- `orchestrator.py` as the top-level dispatcher,
- `llm_service.py` for model access,
- `mqtt_service.py` for device communication,
- `tool_registry.py` as the current action execution layer,
- runtime settings and event infrastructure.

This is already a strong foundation.

However, the current architecture still behaves more like:

1. **intent routing**,
2. **specialist parsing/reporting**,
3. **direct execution**,
4. **final response composition**.

That is good for a demoable smart-home assistant, but not yet sufficient for a production-grade smart-home control runtime.

The main problem is not that HERA lacks more agents.

The real problem is that HERA still lacks a strong **runtime protocol** for:

- capability control,
- structured planning,
- policy decisions,
- execution verification,
- memory continuity,
- durable auditability,
- failure taxonomy,
- concurrency and safety handling.

---

## 3. Design Principle: The Runtime Must Own Reality

The single most important design rule for HERA should be:

> The LLM never directly controls the home.
> The runtime controls the home.

In practice, this means:

- The LLM may classify, extract, interpret, plan, and explain.
- The runtime must validate, authorize, execute, verify, and log.
- Specialist agents may propose tool actions.
- Only the runtime may decide whether those actions become real physical actions.

This principle becomes especially important in smart-home contexts because tool use has **real-world side effects**:

- lights turn on,
- fans turn off,
- relays switch,
- automation preferences change,
- telemetry affects later decisions.

A production-ready system must therefore distinguish clearly between:

- **language reasoning**,
- **action policy**,
- **physical execution**,
- **post-action verification**.

---

## 4. What the Current System Is Missing

### 4.1 The Orchestrator Is a Router, Not Yet a Control Plane

Today, the orchestrator mostly:

- classifies intent,
- chooses a specialist,
- calls the specialist,
- builds a final answer.

A production orchestrator should additionally:

- attach live state context,
- attach recent action memory,
- issue capability grants,
- decide whether clarification is required,
- enforce per-request tool budgets,
- decide when to deny or modify action proposals,
- trigger verification,
- update durable memory,
- write a traceable audit event.

The orchestrator should evolve from **router** to **control plane**.

---

### 4.2 The Device Agent Is a Parser More Than a Planner

The current device agent is already useful, but it is still close to:

- text input,
- LLM parsing,
- normalized command,
- execution.

A production-grade device specialist should instead become a **domain planner** that can:

- interpret ambiguity,
- resolve targets using state and memory,
- propose one or more structured actions,
- request clarification when resolution is unsafe,
- explain expected outcomes before execution,
- accept tool results and adapt if necessary.

This is the difference between a command parser and a genuine specialist.

---

### 4.3 The Tool Registry Combines Too Many Responsibilities

The current `tool_registry.py` appears to do too much in one place:

- target normalization,
- action mapping,
- device execution,
- state update,
- result construction.

A production runtime should split these concerns into dedicated components:

- **capability metadata**,
- **policy evaluation**,
- **tool execution**,
- **verification**,
- **audit logging**,
- **domain-specific adapters**.

---

### 4.4 Verification Is Not Yet a First-Class Stage

In a physical control system, the statement:

> “The command was sent.”

is not equivalent to:

> “The device state actually changed.”

HERA needs an explicit verification phase that is separate from execution. That phase should determine whether:

- the action was verified by state read-back,
- the action is only assumed,
- the action failed,
- the action result is still unknown.

This is one of the biggest differences between a demo assistant and a reliable control system.

---

### 4.5 Memory Is Too Fragile

The current system appears to reset or minimize history after tool use in order to avoid context pollution.

That is understandable, but it creates a new problem:

- follow-up control becomes weak,
- pronoun references become unreliable,
- action continuity disappears,
- stateful conversation becomes brittle.

What HERA needs is not longer prompt history.

What HERA needs is **structured action memory**.

---

### 4.6 Sensor and Anomaly Specialists Are Still Too Shallow

Today those agents largely behave like:

- snapshot summarizers,
- threshold reporters,
- rule-based explainers.

To become genuinely valuable, they should evolve into:

- telemetry analysts,
- anomaly investigators,
- cause correlation specialists,
- stale-signal detectors,
- decision-support agents.

---

## 5. Target Architecture Overview

The target production-ready runtime should be organized into six conceptual layers.

### Layer 1 — Interface Layer

Handles external channels and incoming requests.

Examples:

- Telegram adapter,
- future voice adapter,
- dashboard chat endpoint.

Responsibilities:

- normalize incoming requests,
- assign correlation IDs,
- preserve user/session identity,
- forward into the orchestrator.

---

### Layer 2 — Orchestrator Control Plane

Responsible for end-to-end control of a request.

Responsibilities:

- classify intent,
- load live context,
- load recent action memory,
- compute risk level,
- issue capability grants,
- decide specialist routing,
- decide if clarification is required,
- call specialists,
- invoke tool runtime if necessary,
- invoke verification,
- compose final answer,
- update memory and audit.

---

### Layer 3 — Specialist Layer

Specialists are domain planners, not direct executors.

Examples:

- `device_control_specialist`,
- `sensor_analysis_specialist`,
- `anomaly_investigation_specialist`,
- `general_assistant_specialist`.

Responsibilities:

- interpret user requests within domain scope,
- reason over supplied state and memory,
- propose actions or analytical requests,
- request clarification when uncertainty remains,
- consume tool results if multiple planning steps are allowed.

---

### Layer 4 — Runtime Action Layer

This is the deterministic core that owns reality.

Responsibilities:

- input validation,
- schema validation,
- device existence checks,
- permission checks,
- policy decisions,
- execution,
- verification,
- retries/timeouts,
- structured result generation.

---

### Layer 5 — State/Memory Layer

Holds operational state and long-lived action continuity.

Responsibilities:

- device registry,
- alias registry,
- room mapping,
- live sensor snapshot,
- device last-known state,
- recent action summaries,
- preference context,
- future personalization artifacts.

---

### Layer 6 — Audit/Observability Layer

Ensures HERA is debuggable and trustworthy.

Responsibilities:

- request trace logging,
- action logging,
- policy decision logging,
- verification logging,
- latency metrics,
- error categorization,
- operator inspection support.

---

## 6. Proposed Folder Structure for `BE/HERA`

Below is a recommended refactor target. It is intentionally more explicit than the current layout.

```text
BE/HERA/
├── main.py
├── app/
│   ├── bootstrap.py
│   ├── wiring.py
│   └── dependencies.py
├── interfaces/
│   ├── adapters/
│   │   ├── telegram_adapter.py
│   │   ├── dashboard_adapter.py
│   │   └── voice_adapter.py
│   └── api/
│       └── internal_endpoints.py
├── orchestration/
│   ├── orchestrator.py
│   ├── intent_classifier.py
│   ├── route_planner.py
│   ├── final_composer.py
│   └── state_loader.py
├── specialists/
│   ├── base.py
│   ├── device_control_specialist.py
│   ├── sensor_analysis_specialist.py
│   ├── anomaly_investigation_specialist.py
│   └── general_assistant_specialist.py
├── runtime/
│   ├── tool_runner.py
│   ├── capability_registry.py
│   ├── policy_engine.py
│   ├── verification_service.py
│   ├── execution_budget.py
│   ├── idempotency.py
│   └── error_taxonomy.py
├── domain/
│   ├── devices/
│   │   ├── device_executor.py
│   │   ├── device_resolver.py
│   │   ├── device_verifier.py
│   │   ├── device_policy.py
│   │   └── device_state_service.py
│   ├── telemetry/
│   │   ├── telemetry_reader.py
│   │   ├── telemetry_history.py
│   │   ├── trend_analyzer.py
│   │   └── freshness_checker.py
│   └── anomalies/
│       ├── anomaly_rules.py
│       ├── anomaly_classifier.py
│       ├── anomaly_investigator.py
│       └── anomaly_explainer.py
├── memory/
│   ├── action_memory.py
│   ├── session_memory.py
│   ├── alias_store.py
│   ├── preference_context.py
│   └── summarizer.py
├── integrations/
│   ├── llm/
│   │   ├── llm_service.py
│   │   ├── prompt_templates.py
│   │   └── output_parsers.py
│   ├── mqtt/
│   │   ├── mqtt_service.py
│   │   ├── topic_map.py
│   │   └── ack_tracker.py
│   └── storage/
│       ├── audit_store.py
│       ├── state_store.py
│       └── settings_store.py
├── schemas/
│   ├── route.py
│   ├── capabilities.py
│   ├── execution.py
│   ├── messages.py
│   ├── telemetry.py
│   └── audit.py
├── observability/
│   ├── tracing.py
│   ├── metrics.py
│   ├── logger.py
│   └── audit_writer.py
└── tests/
    ├── unit/
    ├── integration/
    └── contract/
```

This structure makes several things clearer:

- **orchestration** is not the same as **runtime execution**,
- **specialists** are not the same as **domain executors**,
- **memory** is not the same as **live state**,
- **observability** is not optional.

---

## 7. Core Runtime Contracts

The current codebase should move toward explicit structured contracts. These contracts can be implemented with `dataclasses`, `pydantic`, or typed dictionaries. For a production-friendly Python codebase, `pydantic` or frozen `dataclasses` are recommended.

Below is a suggested contract layer.

### 7.1 Incoming Request

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

@dataclass(frozen=True)
class IncomingRequest:
    request_id: str
    channel: str
    user_id: str
    session_id: str
    text: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
```

This object should be created by adapters before the request enters orchestration.

---

### 7.2 Route Decision

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class RouteDecision:
    intent: str
    specialist: str
    requires_execution: bool
    risk_level: str
    clarification_needed: bool
    clarification_reason: Optional[str]
    capability_scope: List[str]
    max_tool_steps: int
```

This replaces loose string-based routing with an explicit control object.

---

### 7.3 Capability Spec

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    effect_type: str
    risk_level: str
    timeout_ms: int
    supports_idempotency: bool
    requires_confirmation: bool
    verifier_name: Optional[str]
```

This makes tool permissions explicit and inspectable.

---

### 7.4 Tool Proposal

```python
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass(frozen=True)
class ToolProposal:
    capability_name: str
    arguments: Dict[str, Any]
    rationale: str
    expected_outcome: str
    confidence: float
```

A specialist should not directly execute actions. It should propose them.

---

### 7.5 Policy Decision

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PolicyDecision:
    decision: str  # allow | deny | ask | modify | noop
    reason: str
    user_visible_message: Optional[str]
    modified_arguments: Optional[dict] = None
```

This is a critical contract. Policy outcomes must be richer than a boolean.

---

### 7.6 Verification Result

```python
from dataclasses import dataclass
from typing import Any, Dict

@dataclass(frozen=True)
class VerificationResult:
    status: str  # verified | assumed | failed | unknown
    source: str  # mqtt_ack | telemetry_readback | cached_state | timeout
    details: Dict[str, Any]
```

---

### 7.7 Tool Execution Result

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class ToolExecutionResult:
    ok: bool
    capability_name: str
    status: str
    reason: str
    changed_entities: List[str] = field(default_factory=list)
    unchanged_entities: List[str] = field(default_factory=list)
    failed_entities: List[str] = field(default_factory=list)
    before_state: Dict[str, Any] = field(default_factory=dict)
    after_state: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[VerificationResult] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
```

This should become the standard runtime output from action execution.

---

### 7.8 Specialist Report

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class SpecialistReport:
    specialist_name: str
    summary: str
    tool_proposals: List[ToolProposal] = field(default_factory=list)
    clarification_question: Optional[str] = None
    analysis_payload: dict = field(default_factory=dict)
```

A specialist should always return a structured report, not just text.

---

### 7.9 Action Summary Memory Record

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass(frozen=True)
class ActionSummary:
    request_id: str
    user_id: str
    session_id: str
    original_text: str
    interpreted_action: str
    interpreted_targets: List[str]
    result_status: str
    timestamp: datetime
```

This record should be durable and queryable for short-horizon continuity.

---

## 8. Orchestrator Refactor Plan

The current `agents/orchestrator.py` should be redesigned into an orchestration package with clearer roles.

### 8.1 Split the Current Orchestrator into Four Components

#### A. `IntentClassifier`
Responsibility:
- classify intent into categories such as:
  - device control,
  - sensor analysis,
  - anomaly investigation,
  - general help,
  - unsupported,
  - clarification-needed.

This may use simple rules, an LLM classifier, or a hybrid approach.

#### B. `StateLoader`
Responsibility:
- load:
  - live sensor snapshot,
  - current device state,
  - device aliases,
  - recent action memory,
  - user preference context,
  - connectivity freshness.

This prevents specialists from working blind.

#### C. `RoutePlanner`
Responsibility:
- convert the classified intent and loaded state into a `RouteDecision`.

This is where risk can be assessed and clarification decisions can be made early.

#### D. `FinalComposer`
Responsibility:
- convert the final structured result into a user-facing natural language response.

This separation keeps orchestration logic clean and testable.

---

### 8.2 Recommended Orchestrator Flow

```text
IncomingRequest
-> load_state_context
-> classify_intent
-> plan_route
-> if clarification_needed: return clarification
-> invoke_specialist
-> if no execution needed: compose answer
-> else run tool runtime
-> verify result
-> update memory
-> write audit
-> compose final answer
```

---

### 8.3 Orchestrator Pseudocode

```python
class Orchestrator:
    def handle(self, request: IncomingRequest) -> str:
        state = self.state_loader.load(request)
        intent = self.intent_classifier.classify(request, state)
        route = self.route_planner.plan(request, state, intent)

        if route.clarification_needed:
            return self.final_composer.compose_clarification(route)

        specialist = self.specialist_registry.get(route.specialist)
        report = specialist.run(request=request, state=state, route=route)

        if report.clarification_question:
            return self.final_composer.compose_specialist_clarification(report)

        if not route.requires_execution:
            self.audit_writer.write_analysis_only(request, route, report)
            return self.final_composer.compose_analysis(report)

        execution_result = self.tool_runner.run_all(
            proposals=report.tool_proposals,
            route=route,
            state=state,
            request=request,
        )

        self.action_memory.append_from_execution(request, execution_result)
        self.audit_writer.write_action(request, route, report, execution_result)

        return self.final_composer.compose_action_result(
            request=request,
            report=report,
            execution_result=execution_result,
        )
```

This is much closer to a production orchestration lifecycle.

---

## 9. Specialist Redesign

### 9.1 Base Specialist Interface

All specialists should conform to one interface.

```python
from abc import ABC, abstractmethod

class BaseSpecialist(ABC):
    name: str

    @abstractmethod
    def run(self, request: IncomingRequest, state: dict, route: RouteDecision) -> SpecialistReport:
        raise NotImplementedError
```

This makes specialists swappable, testable, and predictable.

---

### 9.2 Device Control Specialist

The current `device_agent.py` should become `device_control_specialist.py`.

#### Responsibilities
- resolve ambiguous device mentions,
- interpret user intent in the context of current state,
- decide if clarification is needed,
- propose one or more device actions,
- explain expected outcomes.

#### It should **not**:
- publish MQTT directly,
- update device state directly,
- decide policy outcomes,
- claim execution success.

#### Input Context Should Include
- live device state,
- recent actions,
- alias map,
- online/offline gateway status,
- user-specific restrictions or preferences.

#### Output Should Be
- a `SpecialistReport` with `ToolProposal` objects,
- or a clarification question.

---

### 9.3 Sensor Analysis Specialist

The current `sensor_agent.py` should become more than a snapshot explainer.

#### Responsibilities
- choose what telemetry data is needed,
- request trend analysis,
- compare current values with thresholds,
- correlate with recent actions,
- determine whether data is stale.

#### Example
If the user asks:

> “Is the room unusually hot?”

The specialist should not only inspect a single temperature reading. It should reason over:

- current temperature,
- last 30-minute trend,
- whether the fan was recently turned off,
- sensor freshness,
- user-specific comfort range if personalization exists.

---

### 9.4 Anomaly Investigation Specialist

The current `anomaly_agent.py` should be upgraded from rule reporting to investigation.

#### Responsibilities
- check anomaly score,
- compare with raw telemetry,
- determine if an anomaly is model-only or threshold-backed,
- detect stale sensor conditions,
- correlate with recent actions,
- produce actionable explanations.

#### Target Output Style
Instead of:

> “Temperature is high.”

It should be able to say:

> “The anomaly score rose sharply after the relay turned on three minutes ago. Temperature is now above baseline and telemetry is fresh, so this appears to be a genuine environmental change rather than stale sensor data.”

That is the level of explanation that makes the agent truly valuable.

---

## 10. Tool Runtime Redesign

The current `tool_registry.py` should be decomposed into a proper action runtime.

### 10.1 Proposed Components

#### `capability_registry.py`
Defines what tools exist and what they are allowed to do.

#### `tool_runner.py`
Coordinates execution lifecycle:
- validate,
- normalize,
- evaluate policy,
- execute,
- verify,
- audit,
- return structured result.

#### `policy_engine.py`
Determines whether a proposal may be executed.

#### `verification_service.py`
Determines whether an execution result is actually confirmed.

#### domain executors
For example:
- `device_executor.py`,
- `telemetry_reader.py`.

---

### 10.2 Standard Tool Execution Lifecycle

Every tool execution should follow this general pattern:

```text
proposal received
-> capability lookup
-> schema validation
-> argument normalization
-> policy decision
-> if denied/ask/noop: stop with structured result
-> execute action
-> verify outcome
-> write audit event
-> return ToolExecutionResult
```

This lifecycle should be consistent across all side-effecting tools.

---

### 10.3 Policy Engine Design

The policy engine should be deterministic and domain-aware.

#### Why it should not be an LLM
Because policy must be:

- consistent,
- testable,
- explainable,
- safe under ambiguity,
- independent of prompt drift.

#### Example Policy Outcomes
- `allow`: safe and valid
- `deny`: invalid or unsafe
- `ask`: ambiguity too high
- `modify`: narrow the action or alter its arguments
- `noop`: already in desired state

#### Example Rules
- if target is unresolved -> `ask`
- if command affects all devices and wording is broad -> `ask`
- if gateway is offline -> `deny`
- if device already in requested state -> `noop`
- if requested target is known alias -> `modify` to canonical device ID

---

### 10.4 Verification Service Design

Verification should be treated as first-class.

#### Verification Sources
- device acknowledgment topic,
- telemetry state read-back,
- last-known state refresh,
- eventual consistency timeout,
- simulator acknowledgment.

#### Status Values
- `verified`
- `assumed`
- `failed`
- `unknown`

#### Example
Turning on a fan should not return “success” merely because MQTT publish succeeded.

Instead:
- publish command,
- wait for ack or telemetry refresh,
- compare before/after,
- mark as `verified` or `unknown`.

---

## 11. Device Control Hardening Plan

The device domain is the most critical because it causes physical change.

### 11.1 Device Resolver

Add a dedicated `device_resolver.py`.

Responsibilities:
- map natural language references to device IDs,
- support aliases,
- support room-scoped resolution,
- support recent-action references such as:
  - “turn that off”,
  - “switch it back”,
  - “the light I just turned on”.

Resolution should return:

```python
@dataclass(frozen=True)
class TargetResolution:
    resolved: bool
    canonical_targets: list[str]
    ambiguity_score: float
    unresolved_terms: list[str]
```

If resolution confidence is low, the system should ask a clarification question instead of acting.

---

### 11.2 Device Executor

`device_executor.py` should handle only the actual side effect.

Responsibilities:
- map normalized action into topic/payload,
- publish to MQTT,
- attach correlation ID,
- return immediate execution metadata.

It should not:
- make policy decisions,
- claim verified success,
- infer language meaning.

---

### 11.3 Device Verifier

`device_verifier.py` should confirm the real-world effect.

Responsibilities:
- await acknowledgment or state update,
- compare before and after,
- determine verification status,
- capture verification evidence.

---

### 11.4 Device State Service

Add `device_state_service.py` to manage device state access.

Responsibilities:
- return last known states,
- refresh from MQTT or cache,
- track staleness,
- expose device online/offline metadata.

This keeps specialists and executors from pulling state through ad hoc logic.

---

## 12. Sensor and Anomaly Deepening Plan

### 12.1 Telemetry Services

Add a telemetry domain package that includes:

- `telemetry_reader.py` for live snapshot retrieval,
- `telemetry_history.py` for historical windows,
- `trend_analyzer.py` for simple analysis,
- `freshness_checker.py` for staleness detection.

This turns sensor reasoning into tool-based analysis rather than one-shot explanation.

---

### 12.2 Anomaly Investigation Flow

A mature anomaly investigation should follow a standard sequence:

```text
read live telemetry
-> inspect anomaly score
-> inspect recent history window
-> check freshness
-> inspect recent actions
-> compare to baseline
-> classify likely cause
-> explain outcome
```

This can be implemented with a combination of deterministic domain tools and one explanatory specialist.

---

## 13. Memory Redesign

HERA should not depend on long raw chat history for continuity.

It should have three explicit memory layers.

### 13.1 Stable Memory

Stores information that changes slowly:

- canonical device inventory,
- aliases,
- room-to-device mapping,
- user permissions,
- future preference context.

---

### 13.2 Live State Memory

Stores rapidly changing operational state:

- sensor snapshot,
- device status,
- gateway status,
- freshness timestamps,
- current anomaly indicators.

This is operational state, not chat memory.

---

### 13.3 Action Summary Memory

Stores short, structured summaries of recent actions.

Examples:
- what the user asked,
- what device was actually targeted,
- what happened,
- whether verification succeeded.

This is what enables robust follow-up commands.

#### Example Records
- “turn on the fan” -> `mini_fan` -> `verified_success`
- “turn it off” can now resolve `it` using recent action memory.

This approach is much safer and cheaper than stuffing the full transcript back into the LLM prompt.

---

## 14. Observability and Audit Design

A production-ready system must explain what it did.

### 14.1 Minimum Trace Fields per Request

Every request should produce a trace record containing at least:

- `request_id`
- `user_id`
- `channel`
- `incoming_text`
- `intent`
- `selected_specialist`
- `route_decision`
- `tool_proposals`
- `policy_decisions`
- `execution_results`
- `verification_results`
- `latencies`
- `errors`
- `final_response`

---

### 14.2 Action Audit Record

For every side-effecting command, store:

- original request text,
- interpreted action,
- canonical targets,
- before state,
- after state,
- verification result,
- runtime metadata,
- timestamps,
- failure reason if any.

This is essential for debugging and operator trust.

---

### 14.3 Error Taxonomy

Define explicit runtime error classes.

Suggested categories:

- `AmbiguousTargetError`
- `UnsupportedActionError`
- `OfflineGatewayError`
- `PolicyDeniedError`
- `VerificationTimeoutError`
- `StaleTelemetryError`
- `ExecutionTransportError`
- `PlannerOutputSchemaError`

This will make logs and operator dashboards much more meaningful.

---

## 15. Framework Mapping Recommendation

If HERA uses a framework later, the safest architectural fit is a **LangGraph-style orchestration layer**.

### Why LangGraph-style Fits Best

HERA is not just an agent chat system. It is a stateful runtime with:

- clear stages,
- physical side effects,
- verification checkpoints,
- memory updates,
- policy gates,
- different exit paths.

That is closer to a graph/workflow engine than to a free-form agent swarm.

### Recommended Rule
Use a framework only for:

- state graph orchestration,
- checkpointing,
- trace visibility,
- retry scaffolding,
- node composition.

Do **not** outsource these parts to the framework:

- physical action policy,
- verification logic,
- device execution rules,
- memory semantics,
- audit schema.

Those should remain HERA-owned application logic.

---

## 16. Incremental Migration Strategy

The refactor should be staged. Avoid rewriting the whole system in one large commit.

### Phase 1 — Introduce Structured Schemas Without Changing Behavior

Goal:
- add explicit request/route/report/result models,
- preserve current runtime flow.

Steps:
1. create `schemas/` package,
2. add `IncomingRequest`, `RouteDecision`, `ToolProposal`, `ToolExecutionResult`, `SpecialistReport`, `ActionSummary`,
3. update adapters and orchestrator to pass objects instead of loose dicts/strings,
4. keep old execution logic under the hood for now.

#### Success Criteria
- behavior remains functionally equivalent,
- types are explicit,
- logs become clearer.

---

### Phase 2 — Split the Current Tool Registry

Goal:
- separate planning from execution.

Steps:
1. keep existing `tool_registry.py`,
2. create `runtime/tool_runner.py`,
3. move capability metadata to `capability_registry.py`,
4. move direct MQTT calls into `domain/devices/device_executor.py`,
5. adapt device agent to return `ToolProposal` instead of calling execution directly.

#### Success Criteria
- specialists no longer directly cause side effects,
- execution runs through a central runtime path.

---

### Phase 3 — Add Policy Engine

Goal:
- prevent unsafe or ambiguous execution.

Steps:
1. add `policy_engine.py`,
2. define decision values: `allow`, `deny`, `ask`, `modify`, `noop`,
3. insert policy stage into `tool_runner`,
4. implement first rules for:
   - unresolved targets,
   - offline gateway,
   - already-satisfied state,
   - broad all-device actions.

#### Success Criteria
- runtime can refuse or reshape unsafe proposals deterministically.

---

### Phase 4 — Add Verification Service

Goal:
- separate command dispatch from actual success claims.

Steps:
1. add `verification_service.py`,
2. add `domain/devices/device_verifier.py`,
3. integrate ack or read-back checks,
4. expose verification status in final response and audit logs.

#### Success Criteria
- the user can distinguish between:
  - command sent,
  - success verified,
  - unknown result,
  - failed action.

---

### Phase 5 — Add Action Memory

Goal:
- preserve continuity without raw-history bloat.

Steps:
1. add `memory/action_memory.py`,
2. store short action summaries after every executed command,
3. use action summaries inside the device resolver,
4. support references like:
   - “it”,
   - “that light”,
   - “the one from earlier”.

#### Success Criteria
- follow-up control becomes much more reliable.

---

### Phase 6 — Upgrade Sensor and Anomaly Specialists

Goal:
- make them real analytical specialists.

Steps:
1. add telemetry and anomaly domain tools,
2. let specialists request trend/history/freshness data,
3. correlate with recent actions,
4. standardize explanation formats.

#### Success Criteria
- responses go beyond snapshot explanation and become contextual investigations.

---

### Phase 7 — Add Observability and Audit Persistence

Goal:
- make the runtime inspectable and operator-friendly.

Steps:
1. add audit writer and trace logger,
2. emit a trace per request,
3. persist action audit records,
4. categorize errors,
5. capture per-stage latency.

#### Success Criteria
- a failed action can be reconstructed after the fact.

---

### Phase 8 — Add Personalization Hook Points

Goal:
- prepare for future per-user modeling without entangling the core runtime.

Steps:
1. add a lightweight `preference_context.py`,
2. inject preference context into state loading,
3. keep personalization read-only at first,
4. later connect it to recommendation or routine suggestion flows.

#### Success Criteria
- personalization is additive, not invasive.

---

## 17. File-by-File Refactor Suggestions

### `main.py`

#### Current Role
Bootstraps runtime dependencies and starts the bot.

#### Recommended Changes
- keep `main.py` minimal,
- move object creation into `app/bootstrap.py` or `app/wiring.py`,
- avoid turning `main.py` into a large dependency assembly file.

#### Target State
`main.py` should mainly:
- load config,
- bootstrap services,
- start adapters.

---

### `agents/orchestrator.py`

#### Current Role
Central request dispatcher.

#### Recommended Changes
- move to `orchestration/orchestrator.py`,
- split classifier, route planner, final composer, and state loading into submodules,
- stop using free-form routing outputs.

#### Target State
The orchestrator becomes a request lifecycle manager.

---

### `agents/device_agent.py`

#### Current Role
LLM-assisted command parsing and execution logic.

#### Recommended Changes
- rename conceptually to `device_control_specialist.py`,
- remove direct execution responsibility,
- produce structured tool proposals,
- support clarification when target ambiguity is high.

#### Target State
A domain planner, not a command executor.

---

### `agents/sensor_agent.py`

#### Current Role
Sensor snapshot explanation.

#### Recommended Changes
- evolve into a telemetry analysis specialist,
- consume live snapshot, history window, and freshness checks.

#### Target State
A small analytical specialist rather than a static reporter.

---

### `agents/anomaly_agent.py`

#### Current Role
Rule-based anomaly explanation.

#### Recommended Changes
- add cause-correlation and stale-signal logic,
- support structured investigation flows.

#### Target State
A true anomaly investigator.

---

### `core/tool_registry.py`

#### Current Role
Mixed execution/normalization/result layer.

#### Recommended Changes
- split into capability registry, tool runner, policy, verifier, and domain executors.

#### Target State
No single file should own the full action lifecycle.

---

### `core/llm_service.py`

#### Current Role
Model/provider access.

#### Recommended Changes
- keep it provider-focused,
- do not bury orchestration or policy inside it,
- add structured output parsing helpers nearby.

#### Target State
A reusable LLM client layer.

---

### `core/mqtt_service.py`

#### Current Role
Transport layer for device communication.

#### Recommended Changes
- keep it low-level,
- ensure request correlation support,
- expose ack tracking support if feasible.

#### Target State
A transport integration, not a policy layer.

---

## 18. Testing Strategy

A production-ready HERA runtime must be heavily testable.

### 18.1 Unit Tests

Test pure logic:
- target resolution,
- policy decisions,
- route planning,
- explanation formatting,
- anomaly classification,
- telemetry freshness checks.

---

### 18.2 Contract Tests

Test schema boundaries:
- specialist outputs conform to `SpecialistReport`,
- tool proposals conform to schema,
- runtime results always include verification and status fields.

---

### 18.3 Integration Tests

Test full request flows:
- incoming user text,
- route selection,
- specialist proposal,
- runtime execution,
- verification,
- final response.

---

### 18.4 Simulation Tests

Use simulator-backed MQTT flows to verify:
- light on/off actions,
- verification timeouts,
- stale telemetry handling,
- all-device action safeguards.

---

## 19. What Not to Do

There are several tempting but counterproductive directions.

### Do Not Add Too Many Agents Too Early

HERA does not need:
- debate agents,
- meta-review agents,
- self-critique agents,
- free-form peer-to-peer agent swarms.

The current problem is not lack of agents. It is lack of runtime discipline.

---

### Do Not Let the LLM Own Policy

The LLM may recommend or interpret, but policy decisions for device control should remain deterministic.

---

### Do Not Claim Success Without Verification

Smart-home control systems must distinguish between dispatch and confirmed state change.

---

### Do Not Depend on Long Prompt History for Continuity

Use action summaries, state injection, and structured memory instead.

---

### Do Not Entangle Personalization with Core Action Safety

Personalization should enrich context, not weaken action controls.

---

## 20. Final Recommended End State

A mature `BE/HERA` runtime should behave like this:

1. **An adapter** receives a user request and creates an `IncomingRequest`.
2. **The orchestrator** loads live state and recent action memory.
3. **Intent classification** and **route planning** produce a `RouteDecision`.
4. **A specialist** produces a `SpecialistReport` with structured action proposals or analysis.
5. **The tool runtime** validates those proposals.
6. **The policy engine** decides whether they are allowed, denied, modified, or require clarification.
7. **The executor** performs the physical or logical action.
8. **The verification service** checks whether the action result is real.
9. **Action memory** stores a concise summary for future reference.
10. **Audit and observability layers** persist what happened.
11. **The final composer** returns an honest response to the user.

That is the system shape that would make HERA feel:

- technically serious,
- robust under real-world control conditions,
- explainable,
- extensible,
- and much closer to production-ready.

---

## 21. Recommended Immediate Next Steps

If development begins right away, the highest-leverage first tasks are:

1. introduce core schemas,
2. split the current tool registry,
3. add a deterministic policy engine,
4. add verification status to every device action,
5. introduce action summary memory,
6. refactor the device agent into a proposal-based specialist.

If these six steps are completed well, HERA will already move from a lightweight agentic demo toward a truly valuable smart-home runtime.

---

## 22. Closing Assessment

The strongest conclusion is this:

HERA does **not** need to become “more agentic” in the sense of adding many more autonomous agents.

HERA needs to become **more controlled**.

Its next stage of maturity should come from:

- better contracts,
- better runtime separation,
- stronger execution discipline,
- real verification,
- real memory,
- and real observability.

Once those are in place, the system will not only look more production-ready on paper. It will actually behave more like a production smart-home assistant in practice.



---

## 23. Framework, Data, and MLOps Stack Recommendation

This section updates the earlier implementation plan with a more explicit technology recommendation based on the later discussion around memory, MongoDB, and operational readiness.

### 23.1 Recommended stack for the next major version of `BE/HERA`

#### Orchestration and request state
Add:

- **LangGraph**

Use it for:

- request state graphs,
- checkpoint persistence,
- orchestrator-to-specialist routing,
- bounded multi-step execution,
- resumable workflows.

Do **not** use it to replace:

- policy logic,
- execution logic,
- verification logic,
- or audit persistence.

Those must remain custom HERA code.

#### Runtime contracts and validation
Add:

- **Pydantic v2**

Use it for:

- request normalization,
- specialist input contracts,
- specialist output contracts,
- tool schemas,
- policy schemas,
- memory write schemas,
- audit schemas.

#### Distributed tracing and telemetry instrumentation
Add:

- **OpenTelemetry SDK + OpenTelemetry Collector**

Use it for:

- end-to-end request tracing,
- per-span correlation,
- export to observability backends,
- latency measurement,
- propagation of trace IDs through adapters, runtime, and tool execution.

#### Service metrics, dashboards, and alerts
Add:

- **Prometheus**
- **Grafana**
- **Alertmanager**

Use them for:

- service health metrics,
- device/control metrics,
- verification metrics,
- dashboarding,
- numerical alerts.

#### Error and incident monitoring
Add:

- **Sentry**

Use it for:

- exceptions,
- failed jobs,
- release regressions,
- performance-linked errors,
- grouped incident triage.

#### Agent and LLM observability
Add in the near term:

- **Phoenix**

Use it for:

- orchestrator trace inspection,
- prompt and routing analysis,
- tool-use inspection,
- evaluation of specialist quality.

Add later if the ML lifecycle grows:

- **MLflow**

Use it for:

- experiment tracking,
- model/prompt lineage,
- evaluation history,
- personalization model lifecycle management.

#### ML drift monitoring
Add when anomaly and personalization models mature:

- **Evidently**

Use it for:

- batch drift checks,
- feature distribution monitoring,
- score distribution monitoring,
- report generation for data/model shifts.

### 23.2 Technologies that should remain optional

Do not add them until a concrete need appears:

- Redis,
- vector database,
- relational reporting database,
- Kafka/NATS,
- Temporal,
- Airflow,
- more than one orchestration framework.

### 23.3 The simplest serious stack for HERA

If implementation bandwidth is limited, the smallest still-serious stack is:

- Python + LangGraph + Pydantic
- MongoDB
- OpenTelemetry
- Prometheus + Grafana + Alertmanager
- Sentry
- Phoenix

That is enough to move HERA from a demoable runtime to a significantly more production-like system.

---

## 24. Memory, Database, and MLOps Implementation Design

This section translates the earlier memory redesign into a concrete MongoDB-centered implementation strategy and connects it to the observability and MLOps stack.

### 24.1 Database decision

**Recommendation:** keep MongoDB as the only required database for the next major version.

This is the correct near-term choice because MongoDB already aligns with the current codebase and can store:

- live operational state,
- structured action memory,
- user profiles,
- audit records,
- telemetry time series.

A second database is optional, not mandatory.

### 24.2 Proposed MongoDB collection layout

#### A. `session_threads`
Purpose:

- working memory for a live conversation or user thread.

Suggested fields:

- `_id`
- `thread_id`
- `user_id`
- `channel`
- `active_entities`
- `conversation_window`
- `last_tool_result`
- `pending_clarification`
- `updated_at`
- `expires_at`

Suggested indexes:

- unique index on `thread_id`
- TTL index on `expires_at`
- index on `user_id`

Notes:

- this collection should remain small and short-lived;
- do not store full unbounded transcripts.

#### B. `action_summaries`
Purpose:

- episodic operational memory for follow-up control and review.

Suggested fields:

- `_id`
- `trace_id`
- `thread_id`
- `user_id`
- `env_id`
- `request_text`
- `intent`
- `specialist`
- `target_devices`
- `capability`
- `policy_decision`
- `execution_status`
- `verification_status`
- `before_state`
- `after_state`
- `timestamp`
- `entity_refs`

Suggested indexes:

- compound index on `(thread_id, timestamp desc)`
- compound index on `(user_id, timestamp desc)`
- compound index on `(target_devices, timestamp desc)`
- index on `verification_status`

Notes:

- this is the main continuity layer for device-related follow-up.

#### C. `user_profiles`
Purpose:

- stable semantic memory and personalization context.

Suggested fields:

- `_id`
- `user_id`
- `preferred_language`
- `device_aliases`
- `room_preferences`
- `comfort_preferences`
- `habit_patterns`
- `policy_overrides` (if allowed)
- `updated_at`
- `profile_version`

Suggested indexes:

- unique index on `user_id`

Notes:

- writes should be controlled and not happen on every request;
- prefer background consolidation jobs.

#### D. `tool_audit_logs`
Purpose:

- durable action traceability.

Suggested fields:

- `_id`
- `audit_id`
- `trace_id`
- `thread_id`
- `request_id`
- `user_id`
- `incoming_text`
- `intent`
- `selected_specialist`
- `tool_proposals`
- `policy_decisions`
- `execution_results`
- `verification_results`
- `latencies`
- `error_codes`
- `timestamp`

Suggested indexes:

- unique index on `audit_id`
- index on `trace_id`
- index on `(timestamp desc)`
- compound index on `(user_id, timestamp desc)`

Notes:

- this is not the same thing as application logs;
- this is an operational audit trail.

#### E. `telemetry_points` (time-series)
Purpose:

- telemetry, sensor history, anomaly score history, and device-adjacent measurements.

Suggested structure:

- keep as time-series collection;
- use the measurement timestamp as `timeField`;
- use stable tags such as `device_id`, `room_id`, `sensor_type`, `env_id` as `metaField`.

Suggested usages:

- live snapshot loading,
- trend inspection,
- freshness checks,
- anomaly baseline comparison,
- pre/post actuation verification context.

### 24.3 Memory read path per request

Each request should load three distinct context blocks.

#### A. Live operational context
Loaded from:

- latest telemetry,
- latest device snapshot,
- gateway status,
- freshness indicators.

#### B. Recent episodic action context
Loaded from:

- the most recent action summaries for the current thread,
- recent actions on the same target device,
- recent verification failures,
- recent denied or modified policies.

#### C. Stable profile context
Loaded from:

- aliases,
- preferences,
- known habits,
- language or room defaults.

The orchestrator should then pass a compact structured state object to the specialist instead of a long transcript.

### 24.4 Memory write policy

#### Write to `session_threads` on:

- every user request,
- every clarification turn,
- final response emission.

#### Write to `action_summaries` on:

- any action proposal that reaches execution,
- any denied or modified physical action,
- any verification completion event.

#### Write to `user_profiles` on:

- controlled background consolidation,
- explicit user preference updates,
- validated habit extraction jobs.

#### Write to `tool_audit_logs` on:

- every side-effecting request,
- every failed or denied action,
- any execution with verification uncertainty.

### 24.5 When to add Redis

Do **not** add Redis by default.

Add it only if one or more of the following becomes a real issue:

- two or more worker processes may control the same device concurrently;
- lock contention becomes hard to manage inside Mongo-backed logic;
- short-lived cache traffic becomes hot-path critical;
- cooldown/rate-limiting requires a very fast TTL store.

If Redis is added, use it for:

- per-device locks,
- short-lived request deduplication,
- cooldown keys,
- ephemeral cache.

Do not move primary memory ownership out of MongoDB.

### 24.6 MLOps and observability architecture by layer

#### Layer A — Application/service observability
Use:

- OpenTelemetry
- Prometheus
- Grafana
- Alertmanager
- Sentry

Track:

- request rate,
- p50/p95/p99 latency,
- Mongo call latency,
- MQTT latency,
- timeout rates,
- retry rates,
- error rates,
- stale telemetry rates,
- gateway offline events.

#### Layer B — Agent and LLM observability
Use:

- Phoenix
- optional later MLflow

Track:

- route distribution,
- clarification rate,
- specialist failure rate,
- tool proposal validity rate,
- token usage,
- cost per request,
- per-prompt regression patterns,
- unverified action ratio,
- fallback-to-general rate.

#### Layer C — ML model monitoring
Use:

- Evidently
- optional later MLflow

Track:

- feature drift,
- prediction drift,
- anomaly score drift,
- personalization acceptance rate,
- retraining job health,
- evaluation trend over time.

### 24.7 Suggested metric namespaces

Recommended Prometheus-style naming patterns:

- `hera_requests_total`
- `hera_request_latency_seconds`
- `hera_orchestrator_routing_latency_seconds`
- `hera_specialist_calls_total`
- `hera_specialist_failures_total`
- `hera_tool_executions_total`
- `hera_tool_timeouts_total`
- `hera_verification_latency_seconds`
- `hera_verification_success_total`
- `hera_verification_unknown_total`
- `hera_policy_denied_total`
- `hera_policy_modified_total`
- `hera_stale_telemetry_total`
- `hera_gateway_offline_total`
- `hera_mongo_query_latency_seconds`
- `hera_mqtt_publish_latency_seconds`

### 24.8 Suggested structured log fields

Every structured log or audit-like event should include as many of the following as appropriate:

- `trace_id`
- `request_id`
- `audit_id`
- `thread_id`
- `user_id`
- `channel`
- `intent`
- `selected_specialist`
- `tool_name`
- `device_id`
- `policy_decision`
- `verification_status`
- `error_code`
- `latency_ms`
- `timestamp`

### 24.9 Suggested alert categories

#### Critical alerts

- verification success rate collapses,
- gateway offline,
- telemetry freshness drops below threshold,
- tool timeout spike,
- database connectivity failure,
- scheduled consolidation job failure,
- anomaly model output becomes invalid.

#### Warning alerts

- clarification rate rises sharply,
- unverified action ratio rises,
- per-request token cost rises,
- route distribution changes abnormally,
- drift metrics exceed warning thresholds,
- a specific device's success rate degrades.

### 24.10 Practical rollout order

The most practical rollout order is:

1. keep MongoDB as the only required database;
2. add the new memory collections and indexes;
3. instrument OpenTelemetry in adapters, orchestrator, tool runtime, and Mongo/MQTT paths;
4. add Prometheus metrics and Grafana dashboards;
5. add Sentry for errors and release regressions;
6. add Phoenix for LLM/agent tracing and evaluation;
7. add Evidently when the anomaly/personalization models need drift monitoring;
8. add Redis only if concurrency or lock pressure becomes real.

This sequence keeps the system aligned with the current codebase and avoids infrastructure sprawl.
