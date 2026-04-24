# HERA Multi-Agent System: From Lightweight Orchestrator to Production-Ready Runtime

**Repository context:** `MP-AI-252`  
**Primary focus:** `BE/HERA`  
**Prepared for:** architectural evolution of HERA's multi-agent backend  
**Language:** English  

---

## Executive Summary

HERA already has the **right architectural instinct**: a central orchestrator receives user input, classifies intent, routes to domain specialists, and uses backend services to control smart-home devices or answer telemetry-related questions.

That is a meaningful foundation. It is **not** a toy one-agent chatbot anymore.

However, the current implementation is still **lightweight** in a very specific engineering sense:

- the orchestrator is mostly a router rather than a real control plane;
- the device specialist is mostly a **parser + direct executor**;
- the sensor and anomaly specialists are mostly **structured reporters**;
- tool execution is not yet separated into **planning, policy, execution, verification, and audit**;
- memory is mostly conversational history rather than operational memory;
- observability and traceability are not yet strong enough for a real production smart-home runtime.

This document argues that HERA should evolve toward the following target model:

> **The LLM should understand intent and propose actions. The runtime should be the only layer allowed to validate, authorize, execute, verify, log, and remember physical actions.**

That change is what will make the `BE/HERA` subsystem:

- architecturally serious,
- research-worthy,
- production-aligned,
- safer for physical device control,
- and extensible toward personalization and proactive assistance.

---

## 1. Current State of `BE/HERA`

This section is grounded in the current repository structure and code.

### 1.1 Core runtime entry point

`BE/HERA/main.py` wires together the major backend components:

- `LLMService`
- `MQTTService`
- `ToolRegistry`
- `DeviceControlAgent`
- `SensorAnalysisAgent`
- `AnomalyExpertAgent`
- `Orchestrator`
- `TelegramAdapter`

In other words, HERA already has a **coherent runtime topology** rather than a loose collection of scripts.

### 1.2 Current multi-agent pattern

The existing system follows an **orchestrator-specialist** pattern:

- `Orchestrator` classifies one of four intents:
  - `device_control`
  - `sensor_query`
  - `anomaly_query`
  - `general`
- requests are routed to one specialist agent per intent;
- the specialist returns a structured report;
- the orchestrator composes the final user-facing response.

This is a pragmatic and correct starting point. It already reflects a hierarchical multi-agent design.

### 1.3 Current role of each specialist

#### DeviceControlAgent
Current behavior:

1. receive user text;
2. use an LLM prompt to parse the command into a narrow JSON schema;
3. normalize the command;
4. execute it through `ToolRegistry`;
5. return a structured execution report.

This is useful, but still fundamentally a **parse → execute** pipeline.

#### SensorAnalysisAgent
Current behavior:

- fetch current MQTT sensor snapshot;
- package it into a structured report with reference thresholds;
- return it for the orchestrator to verbalize.

This is closer to a **report generator** than a reasoning-heavy specialist.

#### AnomalyExpertAgent
Current behavior:

- fetch current snapshot;
- run a deterministic rule-based anomaly classification;
- build a report including thresholds and severity;
- return it to the orchestrator.

This is currently a **rule interpreter + explainer**, not yet a true investigator agent.

### 1.4 Current shared runtime services

#### `LLMService`
Strengths:

- provider-agnostic access via LiteLLM;
- runtime model selection;
- per-provider model naming;
- normalized tool-call parsing.

This is already a strong abstraction and should be preserved.

#### `RuntimeSettingsStore`
Strengths:

- dynamic model/provider configuration through MongoDB;
- watch thread for live updates;
- provider-aware model selection.

This is especially useful for experimentation and future production tuning.

#### `ToolRegistry`
Current role:

- define tool schemas;
- normalize device targets;
- execute side effects by publishing MQTT commands;
- maintain a lightweight local device state view.

This is the most important place where HERA must evolve.

#### `EventBus`
Current role:

- lightweight async event pub/sub.

This is promising, but currently underused relative to its architectural potential.

---

## 2. What Is Good About the Current Design

Before discussing gaps, it is important to recognize what HERA already gets right.

### 2.1 It separates routing from domain handling

Many student systems push every task through one giant prompt. HERA does not. It already isolates:

- routing,
- device control,
- sensor analysis,
- anomaly explanation,
- general conversation.

That is a real strength.

### 2.2 It respects the distinction between specialist report and final response

The orchestrator owns final user-facing wording, while specialists own domain-specific interpretation. This is a solid design principle because it gives you:

- reusable specialists,
- better control over tone,
- cleaner user responses,
- and future compatibility with multiple frontends.

### 2.3 It already uses structured data as an intermediate representation

The specialists return JSON-like reports, not only prose. This is important because it means HERA is already partway toward a typed runtime.

### 2.4 It already has runtime-aware model selection

The combination of `LLMService` and `RuntimeSettingsStore` is stronger than what many student multi-agent projects have. It allows:

- model per provider,
- agent-specific model selection,
- runtime switching,
- experimentation with latency/cost tradeoffs.

### 2.5 It is grounded in a real physical execution layer

HERA is not merely text-in/text-out. It connects to:

- MQTT,
- firmware,
- real or simulated devices,
- telemetry,
- dashboard-facing state.

That makes production readiness a meaningful question, because this runtime can affect physical systems.

---

## 3. Why the Current System Is Still Lightweight

The issue is not that HERA lacks multiple agents. The issue is that it lacks a **hardened runtime protocol** around those agents.

### 3.1 The orchestrator is a router, not yet a control plane

The current orchestrator does these things well:

- classify intent,
- route to a specialist,
- compose the final response,
- keep limited conversation history.

But a production smart-home orchestrator should also decide:

- whether the request is safe to execute;
- whether the request is ambiguous enough to require clarification;
- which capabilities may be granted to the selected specialist;
- whether the current live state is fresh enough to trust;
- whether execution should be retried or denied;
- whether a tool result is sufficiently verified;
- what should be written into long-term memory and audit logs.

Right now, those responsibilities are either absent or distributed too informally.

### 3.2 The device agent is still a parser with side effects

Today, `DeviceControlAgent` essentially does:

```text
user text -> LLM JSON parse -> normalize -> execute
```

That works for demos, but it is fragile in production because:

- the parse step is doing too much;
- the same step implicitly determines both interpretation and action;
- there is no explicit clarification phase;
- there is no formal policy result;
- there is no separate verification stage after the physical action.

### 3.3 Tool execution is not yet a full runtime lifecycle

`ToolRegistry` currently mixes several concerns together:

- capability declaration,
- target normalization,
- execution,
- local state update,
- basic user-facing result shaping.

A production runtime should instead decompose this into:

- capability specification,
- input validation,
- policy evaluation,
- execution,
- verification,
- audit logging,
- result packaging.

### 3.4 Sensor and anomaly agents are snapshot-oriented, not investigative

Both are useful, but both currently operate mainly on a single current snapshot. They do not yet investigate across:

- time windows,
- action history,
- stale-data detection,
- telemetry freshness,
- likely causes,
- environmental baselines,
- user-specific context.

### 3.5 Memory is conversational, not operational

The orchestrator stores per-chat history and resets after tool usage to avoid context pollution. That idea is understandable, but it means HERA currently lacks a stronger notion of:

- entity continuity,
- action summary memory,
- per-device operational context,
- per-user preferences,
- reference grounding for follow-up commands.

### 3.6 Observability is not yet sufficient for physical control

The current code does log activity, but production smart-home control requires more than console logs. You need to know:

- what the user asked for;
- what the system interpreted;
- what policy decision was made;
- what command was sent;
- whether it was verified;
- what state changed;
- what the latency was;
- and how failures should be classified.

---

## 4. The Correct Target: A Controlled Action Runtime

The most important conceptual shift is this:

> **Do not make HERA “more agentic” by adding more free-form LLM behavior. Make HERA more reliable by making the runtime around agents much stricter.**

A production-ready HERA should look like this:

```text
User Request
  -> Adapter
  -> Orchestrator Control Plane
  -> Specialist Planner
  -> Runtime Policy Check
  -> Deterministic Tool Execution
  -> Verification Service
  -> Audit + Memory Update
  -> Final Response Composer
```

In that design:

- the **LLM proposes**;
- the **runtime decides**;
- the **tool layer executes**;
- the **verification layer confirms**;
- the **orchestrator reports**;
- the **memory/audit layers persist**.

That is the correct architecture for a physical AI assistant.

---

## 5. Design Principles HERA Should Adopt

The `docs/claude_code_tooling_lessons_for_hera.md` document already points in the right direction. The following principles should become explicit architectural rules.

### 5.1 Model proposals are not authority

The model may suggest:

- which capability to use,
- which target is intended,
- whether clarification is needed,
- what explanation should be given.

But the model must **not** be treated as the final authority on:

- whether an action is allowed,
- whether the target is valid,
- whether execution succeeded,
- whether state truly changed.

### 5.2 Execution must be separate from verification

For a smart-home runtime, these two statements are fundamentally different:

- “the system published an MQTT command”; and
- “the physical state actually changed.”

A production system must track that difference explicitly.

### 5.3 Tool results must be structured, not prose-only

Every tool call should return a typed result that includes:

- success/failure,
- reason code,
- before-state,
- after-state,
- changed entities,
- unchanged entities,
- verification status,
- timestamps,
- optional audit ID.

### 5.4 Policy outcomes are richer than allow/deny

A robust policy engine should support at least:

- `allow`
- `deny`
- `ask_clarification`
- `noop`
- `modify`

This matters because many smart-home requests are not unsafe but are still not directly executable.

### 5.5 Memory should store summaries, not raw transcript only

Operational memory should persist compact summaries such as:

- what device was referenced;
- what action was attempted;
- what the result was;
- whether the result was verified;
- when it happened.

That memory is far more useful for follow-up control than a long chat transcript.

### 5.6 Specialists should be scoped and narrow

A specialist should not have broad unrestricted power. It should be given:

- a bounded capability set,
- domain-specific context,
- a maximum planning/execution budget,
- and a typed response contract.

---

## 6. Recommended Target Architecture for `BE/HERA`

The following target architecture stays close to the current codebase while making it significantly more production-aligned.

## 6.1 Layered architecture

### Layer A: Adapters

Examples:

- Telegram adapter
- future voice adapter
- future REST adapter

Responsibilities:

- convert external input into `UserMessage`-like canonical objects;
- pass messages to orchestrator;
- render final response;
- attach channel metadata.

### Layer B: Orchestrator Control Plane

Responsibilities:

- intent classification;
- route planning;
- capability grants;
- clarification decisions;
- context loading;
- specialist invocation;
- final response composition;
- memory write triggers;
- audit correlation.

This is the most important evolution of the current orchestrator.

### Layer C: Specialists (Scoped Planners)

Recommended specialists:

- `DeviceControlSpecialist`
- `SensorAnalysisSpecialist`
- `AnomalyInvestigatorSpecialist`
- `GeneralAssistantSpecialist`

Responsibilities:

- understand domain intent;
- plan within a bounded capability set;
- request clarification when needed;
- produce structured specialist reports;
- never directly own platform-level execution or policy.

### Layer D: Runtime Policy and Tool Execution

Recommended services:

- `CapabilityRegistry`
- `PolicyEngine`
- `ToolRunner`
- `DeviceExecutor`
- `TelemetryQueryService`
- `VerificationService`

Responsibilities:

- validate requests;
- normalize entities;
- authorize actions;
- execute deterministic operations;
- verify outcomes;
- classify failures.

### Layer E: Memory and Audit

Recommended services:

- `ActionMemoryService`
- `PreferenceContextService`
- `AuditLogger`
- `TraceContext`

Responsibilities:

- record operational summaries;
- store user preference context;
- store traces and execution outcomes;
- support debugging and personalization.

### Layer F: Shared Infrastructure

Examples:

- `LLMService`
- `RuntimeSettingsStore`
- `EventBus`
- `MQTTService`

These should remain shared services, but with stronger contracts.

---

## 7. How the Orchestrator Should Evolve

The current orchestrator should become a **control plane**, not only a router.

### 7.1 New responsibilities

The orchestrator should explicitly decide:

1. **What intent is this?**
2. **Which specialist should handle it?**
3. **What capabilities may this specialist use?**
4. **Do we have enough context to execute safely?**
5. **Should we ask a clarification question first?**
6. **What live state must be attached?**
7. **Should the response be direct, investigative, or action-based?**
8. **What memory and audit data must be written afterward?**

### 7.2 Recommended new typed decision object

A production version of HERA should introduce a typed route decision structure such as:

```python
@dataclass(slots=True)
class RouteDecision:
    intent: str
    specialist: str
    requires_execution: bool
    clarification_needed: bool
    clarification_question: str | None
    granted_capabilities: list[str]
    risk_level: str
    reason: str
```

This turns routing from an implicit string mapping into an explicit runtime object.

### 7.3 Why this matters

Right now, route selection and execution readiness are coupled too loosely. A real control plane needs to represent:

- what was decided,
- why it was decided,
- what authority was granted,
- and whether execution was actually permitted.

That will also make the backend more testable.

---

## 8. How the Device Specialist Should Evolve

The device path is where HERA can improve the most.

### 8.1 Current device path

Current flow:

```text
user text
  -> parse JSON command with LLM
  -> normalize action and target
  -> execute through ToolRegistry
  -> return execution report
```

This is good for proof-of-concept work but not sufficiently hardened.

### 8.2 Recommended device specialist role

The device specialist should become a **domain planner**, not merely a parser.

It should answer questions like:

- what action does the user likely intend?
- what target does that refer to?
- is the target ambiguous?
- does the request imply a grouped action?
- does the current state already satisfy the request?
- should we request clarification instead of executing?

### 8.3 New output contract for device specialist

Instead of directly implying execution, it should return a proposal object such as:

```python
@dataclass(slots=True)
class ToolProposal:
    capability: str
    arguments: dict[str, Any]
    confidence: float
    ambiguity_detected: bool
    clarification_question: str | None
    rationale: str
```

This proposal then goes into the runtime policy and execution layer.

### 8.4 Why this is better

It separates:

- **interpretation** from **execution**,
- **planning** from **authorization**,
- **language understanding** from **physical side effects**.

That is the correct architecture for production smart-home systems.

---

## 9. How Tool Execution Should Be Refactored

`ToolRegistry` should be broken into clearer runtime components.

### 9.1 Problem with the current single-registry approach

Today, one class handles too many concerns:

- tool schema registration,
- normalization,
- state assumptions,
- MQTT action dispatch,
- result shaping.

This becomes hard to scale once you add:

- more devices,
- higher-risk actions,
- verification stages,
- idempotency,
- retries,
- audit requirements.

### 9.2 Recommended decomposition

#### A. `capability_registry.py`
Defines the canonical capabilities available to the runtime.

Each capability should include:

- capability name,
- domain,
- input schema,
- output schema,
- effect type,
- risk level,
- timeout policy,
- verifier binding,
- audit fields.

Example:

```python
@dataclass(slots=True)
class CapabilitySpec:
    name: str
    domain: str
    effect_type: str
    risk_level: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    verifier_name: str | None
    timeout_ms: int
    max_retries: int
```

#### B. `policy_engine.py`
Evaluates whether a proposed action should be:

- allowed,
- denied,
- clarified,
- turned into a no-op,
- or modified.

#### C. `tool_runner.py`
Runs the standard lifecycle:

```text
validate -> normalize -> policy -> execute -> verify -> audit -> return
```

#### D. `device_executor.py`
Owns deterministic physical side effects:

- publish MQTT command,
- attach request IDs,
- optionally wait for acknowledgements.

#### E. `device_verifier.py`
Owns post-action verification:

- read back device state,
- inspect fresh telemetry,
- inspect ack topics,
- classify verification confidence.

This decomposition is the single most important change for production readiness.

---

## 10. Device Control Should Be Treated as a Physical Action Protocol

To move beyond lightweight execution, the device path should follow a formal lifecycle.

### 10.1 Phase 1: Resolve target

Examples:

- “the light” -> does that mean `all_lights` or a room-level alias?
- “turn off the fan” -> should map to `mini_fan`;
- “turn that off” -> must resolve from recent operational memory.

### 10.2 Phase 2: Validate arguments

The runtime should validate:

- target exists;
- action is supported by target type;
- transport is available;
- gateway/device is online enough to attempt execution.

### 10.3 Phase 3: Policy decision

The policy engine should return something like:

```python
@dataclass(slots=True)
class PolicyDecision:
    action: str   # allow | deny | ask_clarification | noop | modify
    reason: str
    rewritten_args: dict[str, Any] | None = None
    clarification_question: str | None = None
```

Examples:

- request targets all devices -> `ask_clarification` if ambiguity is too high;
- device already in requested state -> `noop`;
- gateway offline -> `deny`;
- unsupported target alias -> `ask_clarification`.

### 10.4 Phase 4: Execute deterministically

Execution must include:

- correlation ID;
- timestamp;
- timeout budget;
- transport metadata;
- effect summary.

### 10.5 Phase 5: Verify independently

Verification should not reuse the model. It should be deterministic.

Possible verification methods:

- read-back from device snapshot;
- telemetry freshness window;
- acknowledgement topic;
- state delta compared with before-state.

### 10.6 Phase 6: Write audit log

The audit log should store at least:

- chat/user ID,
- request text,
- interpreted action,
- capability used,
- arguments,
- policy decision,
- before-state,
- after-state,
- verification result,
- latency,
- failure class.

### 10.7 Phase 7: Update memory

The runtime should store a compact action summary.

### 10.8 Phase 8: Compose final user response

The orchestrator should then communicate one of several distinct truths:

- command verified successfully;
- command was not needed because state already matched;
- command was attempted but not yet verified;
- command was denied;
- clarification is needed.

This distinction is essential for trust.

---

## 11. How Sensor Analysis Should Become More Valuable

The sensor specialist should evolve from **snapshot reporter** to **telemetry analyst**.

### 11.1 Current limitation

Current behavior is mostly current-state reporting.

### 11.2 Target behavior

The sensor specialist should be able to ask the runtime for:

- current snapshot,
- telemetry over a time window,
- min/max/mean over a recent interval,
- freshness age,
- recent device actions,
- comparison against configured baselines.

### 11.3 Recommended tool surface

Examples:

- `get_live_snapshot()`
- `get_telemetry_window(minutes=30)`
- `get_recent_action_summaries(limit=10)`
- `compute_environment_summary(window=30)`
- `get_sensor_freshness()`

### 11.4 Resulting capability

Then HERA can answer questions such as:

- “Has the room been getting hotter in the last half hour?”
- “Did humidity spike after the fan turned off?”
- “Are the readings recent enough to trust?”

That is far more valuable than single-point readings.

---

## 12. How the Anomaly Specialist Should Become a True Investigator

The anomaly path should become one of HERA’s highest-value capabilities.

### 12.1 Current limitation

At the moment, anomaly handling is largely threshold + rule-based classification.

That is fine as a first layer, but it does not yet investigate *why* an anomaly might have occurred.

### 12.2 Target behavior

The anomaly specialist should correlate:

- current anomaly score,
- temperature/humidity readings,
- historical telemetry,
- recent device actions,
- telemetry freshness,
- system connectivity,
- user context when relevant.

### 12.3 Recommended anomaly workflow

```text
query live snapshot
  -> check freshness
  -> compare with threshold baseline
  -> inspect recent action summaries
  -> inspect historical trend
  -> classify probable cause
  -> recommend next action
```

### 12.4 Possible anomaly categories

A more mature anomaly investigator should distinguish among:

- environmental anomaly,
- sensor fault,
- stale telemetry,
- actuation-induced transient,
- model-only anomaly without threshold breach,
- connectivity-induced uncertainty.

### 12.5 Why this matters

This gives HERA a genuinely interesting intelligence layer instead of only a polite rule explainer.

---

## 13. Memory Should Be Rebuilt Around Operational Continuity

One of the biggest opportunities in HERA is to redesign memory.

### 13.1 Current approach

Current per-chat history is useful for general conversation but weak for physical control.

The reset-after-tool-use behavior avoids contamination, but it also removes continuity.

### 13.2 Recommended memory model

HERA should use three separate memory layers.

#### A. Stable memory

Stores durable facts:

- device registry,
- aliases,
- room mappings,
- user/device ownership,
- policy constraints,
- preference profile references.

#### B. Live state memory

Stores ephemeral current state:

- sensor snapshot,
- device states,
- freshness timestamps,
- online/offline status,
- current anomaly score.

#### C. Action summary memory

Stores compact operational summaries such as:

```python
{
  "chat_id": "12345",
  "user_request": "turn on the fan",
  "interpreted_target": "mini_fan",
  "capability": "control_device",
  "result": "verified_success",
  "timestamp": "2026-04-22T20:10:00Z",
  "entity_refs": ["mini_fan"]
}
```

### 13.3 Why this is better

This lets HERA handle natural follow-ups such as:

- “turn that off”
- “switch it back on”
- “what did you just change?”
- “why didn’t it respond earlier?”

without bloating the prompt with a full transcript.

---

## 14. Personalization Should Be Added as Context, Not Chaos

The personalization redesign documents in `docs/` are strong. They suggest a transition from command execution toward adaptive assistance.

That is a good direction, but it should not be implemented by making the orchestrator itself more chaotic.

### 14.1 Recommended architecture for personalization

Create a dedicated `PreferenceContextService` or `PersonalizationService` responsible for:

- loading user-specific preferences,
- loading learned habits,
- exposing confidence-rated recommendations,
- injecting compact user context into orchestrator/specialists.

### 14.2 Example injected context

```python
@dataclass(slots=True)
class UserContext:
    preferences: dict[str, Any]
    recent_patterns: list[dict[str, Any]]
    confidence_scores: dict[str, float]
    preferred_language: str | None
```

### 14.3 Why this separation matters

Personalization should influence:

- how HERA interprets ambiguous targets,
- what default suggestions it prefers,
- how proactive prompts are ranked,
- and how multiple users’ habits are resolved.

But personalization should **not** bypass policy, verification, or explicit execution control.

---

## 15. What Should Be Deterministic, Not LLM-Driven

A common multi-agent design mistake is to over-assign responsibility to language models.

HERA should keep the following components deterministic:

### 15.1 Policy Engine

Reasons:

- safety,
- repeatability,
- explainability,
- auditability.

### 15.2 Verification Service

Reasons:

- success/failure is an operational fact, not a generated opinion;
- telemetry freshness and device state are measurable;
- physical trust should not be inferred by a model.

### 15.3 Memory Write Rules

Reasons:

- memory should be consistent;
- operational summaries should follow fixed schemas;
- analytics and debugging depend on stable records.

### 15.4 Audit Logger

Reasons:

- logs need stable keys and reliable structure;
- audit records may be used later for debugging, evaluation, or reporting.

The LLM should remain important, but mostly in these roles:

- interpretation,
- explanation,
- bounded planning,
- clarification question generation,
- final user-facing phrasing.

---

## 16. Recommended Specialist Set for the Next Version

HERA does not need many more agents. It needs **better-defined roles**.

### 16.1 Keep and upgrade

#### `device_control_specialist`
Role:

- interpret control intent,
- produce structured action proposal,
- request clarification when needed,
- explain grouped action implications.

#### `sensor_analysis_specialist`
Role:

- answer live and short-window telemetry questions,
- compare readings against baselines,
- summarize trends.

#### `anomaly_investigator_specialist`
Role:

- investigate current anomalies,
- classify likely cause,
- recommend next steps,
- differentiate stale/uncertain/system-caused events.

#### `general_assistant_specialist`
Role:

- answer help and open-ended questions,
- explain system capabilities,
- avoid polluting operational specialists.

### 16.2 Add as deterministic services, not LLM agents

#### `policy_engine`
#### `verification_service`
#### `memory_service`
#### `audit_logger`

These should not be framed as “agents” in the model sense.

### 16.3 Add later if needed

#### `personalization_specialist`
Only after behavior data becomes mature.

#### `scheduler_or_notification_service`
For proactive suggestions or reminders.

### 16.4 Avoid for now

Do **not** rush into:

- debate agents,
- peer-to-peer agent networks,
- planner-reviewer loops for every request,
- autonomous unrestricted tool loops,
- excessive “agent marketplace” abstraction.

That would increase complexity faster than value.

---

## 17. Framework Recommendation for HERA

The best fit is not “whichever framework has the most agent branding.” It is whichever one matches HERA’s actual runtime shape.

### 17.1 Why HERA is a workflow graph problem

HERA has:

- clear state transitions,
- physical action checkpoints,
- deterministic validation,
- verification gates,
- memory update stages,
- multiple domain-specific branches.

That means HERA is fundamentally a **graph/workflow orchestration problem**, not a free-form autonomous-agent problem.

### 17.2 Best conceptual fit: LangGraph-style architecture

A LangGraph-style design is the strongest conceptual fit because it naturally models nodes such as:

```text
receive_message
  -> classify_intent
  -> build_route_decision
  -> load_live_context
  -> specialist_plan
  -> policy_check
  -> execute_tool
  -> verify_outcome
  -> compose_response
  -> write_memory
  -> write_audit
```

This does **not** mean HERA must be rewritten around a framework immediately. It means HERA should adopt that style of stateful workflow explicitly.

### 17.3 Why not lean too heavily on framework-native tool loops

HERA’s smart-home control path is too safety-sensitive to delegate fully to framework defaults. Regardless of framework choice, HERA should keep its own custom:

- policy engine,
- execution runtime,
- verification service,
- action memory,
- audit schema.

### 17.4 Practical framework position

A sensible recommendation is:

- use a **LangGraph-like state machine design** for orchestration;
- keep tool execution and verification as **custom runtime code**;
- treat framework use as a workflow aid, not as the authority on smart-home safety.

---

## 18. Proposed Refactor by File and Package

This section maps the redesign directly onto `BE/HERA`.

### 18.1 `agents/orchestrator.py`

#### Current role
- intent classifier,
- specialist router,
- general chat handler,
- final response composer,
- limited conversation memory.

#### Recommended split
- `intent_classifier.py`
- `route_planner.py`
- `response_composer.py`
- `orchestrator.py` as the top-level coordinator

#### New responsibilities to add
- capability grant generation,
- clarification gating,
- live context attachment,
- trace ID propagation,
- post-action memory write calls,
- post-action audit write calls.

### 18.2 `agents/device_agent.py`

#### Current role
- parse a command,
- normalize it,
- call execution,
- report result.

#### Recommended redesign
Rename or reconceptualize as `device_control_specialist.py`.

Responsibilities:
- resolve user intent into action proposal,
- recognize ambiguity,
- request clarification when necessary,
- consume runtime tool results and produce final specialist report.

### 18.3 `agents/sensor_agent.py`

#### Recommended redesign
Turn it into a real telemetry analyst that can query:

- current snapshot,
- telemetry windows,
- recent actions,
- freshness metadata,
- trend summaries.

### 18.4 `agents/anomaly_agent.py`

#### Recommended redesign
Turn it into an anomaly investigator with support for:

- historical lookback,
- cause inference,
- stale-data detection,
- cross-checking recent actions,
- uncertainty-aware recommendations.

### 18.5 `core/tool_registry.py`

#### Recommended split
- `core/capability_registry.py`
- `core/tool_runner.py`
- `core/policy_engine.py`
- `core/verification_service.py`
- `core/device_executor.py`
- `core/device_verifier.py`

This is the highest-priority refactor in the entire package.

### 18.6 `core/message.py`

This file should become the central contract layer.

Recommended additions:

- `RouteDecision`
- `CapabilitySpec`
- `ToolProposal`
- `PolicyDecision`
- `ToolExecutionResult`
- `VerificationResult`
- `SpecialistReport`
- `ActionSummary`
- `TraceContext`

### 18.7 `core/runtime_settings.py`

Current dynamic provider/model settings are good.

Recommended extensions:

- per-specialist max step budget,
- timeout budgets,
- risk thresholds,
- policy flags,
- verification strictness,
- feature flags for personalization/proactive suggestions.

### 18.8 `core/event_bus.py`

Current implementation is intentionally lightweight.

Recommended future uses:

- anomaly event publication,
- async audit writes,
- behavior logging,
- proactive suggestion scheduling,
- dashboard event streaming.

Important caution:

- do not let event handlers become hidden business logic;
- orchestrator should remain the explicit main control path.

---

## 19. Recommended New Core Data Contracts

The fastest way to mature HERA is to strengthen its typed contracts.

## 19.1 `ToolProposal`

```python
@dataclass(slots=True)
class ToolProposal:
    capability: str
    arguments: dict[str, Any]
    confidence: float
    ambiguity_detected: bool = False
    clarification_question: str | None = None
    rationale: str | None = None
```

## 19.2 `PolicyDecision`

```python
@dataclass(slots=True)
class PolicyDecision:
    decision: str  # allow | deny | ask_clarification | noop | modify
    reason: str
    rewritten_arguments: dict[str, Any] | None = None
    clarification_question: str | None = None
```

## 19.3 `VerificationResult`

```python
@dataclass(slots=True)
class VerificationResult:
    status: str  # verified | unverified | failed | stale | unknown
    source: str  # mqtt_ack | state_readback | telemetry_window | none
    confidence: float
    details: dict[str, Any]
```

## 19.4 `ToolExecutionResult`

```python
@dataclass(slots=True)
class ToolExecutionResult:
    ok: bool
    capability: str
    reason: str
    before_state: dict[str, Any]
    after_state: dict[str, Any]
    changed_entities: list[str]
    unchanged_entities: list[str]
    verification: VerificationResult
    audit_id: str | None = None
```

## 19.5 `ActionSummary`

```python
@dataclass(slots=True)
class ActionSummary:
    chat_id: str
    user_request: str
    interpreted_target: str | None
    capability: str
    result: str
    verification_status: str
    timestamp: datetime
    entity_refs: list[str]
```

These contracts alone would dramatically improve maintainability.

---

## 20. Observability and Audit Requirements

A production-ready HERA must be debuggable.

### 20.1 Minimum trace structure

Every inbound request should get a trace ID.

A single trace should connect:

- adapter receipt,
- intent classification,
- route decision,
- specialist proposal,
- policy decision,
- tool execution,
- verification,
- memory write,
- audit write,
- final response.

### 20.2 Suggested metrics

At minimum, capture:

- intent classification latency,
- specialist planning latency,
- tool execution latency,
- verification latency,
- total request latency,
- success/deny/clarification/noop counts,
- verification success rate,
- stale telemetry rate,
- ambiguity rate,
- per-capability failure rate.

### 20.3 Suggested audit record schema

Suggested fields:

- `audit_id`
- `trace_id`
- `chat_id`
- `user_message`
- `intent`
- `specialist`
- `tool_proposal`
- `policy_decision`
- `execution_result`
- `verification_result`
- `before_state`
- `after_state`
- `latency_ms`
- `timestamp`

This will be useful for:

- debugging,
- demo explanation,
- evaluation,
- personalization training logs,
- and future admin dashboards.

---

## 21. Safety and Reliability Requirements

Because HERA controls physical devices, production readiness must include basic safety engineering.

### 21.1 Ambiguity handling

HERA must prefer clarification over risky execution when:

- the target is unclear,
- a pronoun has no valid referent,
- the command scope is broad,
- user intent conflicts with current context.

### 21.2 Offline-awareness

HERA should be explicit about connectivity states such as:

- broker unreachable,
- device offline,
- stale telemetry,
- no recent state confirmation.

### 21.3 Idempotency

Repeat requests should not produce confusing duplicate actuation. The runtime should be able to detect:

- already-on requests,
- already-off requests,
- duplicate commands within a short window.

### 21.4 Concurrency control

If multiple requests target the same device, HERA should guard against race conditions. Even a simple per-device lock or queue is better than none.

### 21.5 Fallback language

When verification fails, HERA should say something operationally correct such as:

- “I sent the command, but I could not verify the device state yet.”

That is much better than falsely implying success.

---

## 22. Evaluation Plan for the Multi-Agent Runtime

If HERA is meant to be academically convincing or production-oriented, it needs evaluation criteria beyond “it mostly works in demos.”

### 22.1 Suggested evaluation dimensions

#### A. Intent routing accuracy
Measure correctness of routing across:

- device control,
- sensor query,
- anomaly query,
- general.

#### B. Proposal correctness
Measure whether the specialist correctly identifies:

- target,
- action,
- ambiguity,
- grouped scope.

#### C. Policy correctness
Measure whether the runtime appropriately:

- allows,
- denies,
- clarifies,
- no-ops,
- rewrites.

#### D. Verification reliability
Measure how often HERA:

- correctly detects success,
- correctly detects failure,
- correctly flags uncertainty.

#### E. Follow-up continuity
Measure whether HERA correctly resolves references such as:

- “that”
- “the one you just turned on”
- “switch everything back”

#### F. User trustworthiness
Measure whether user-facing responses remain truthful under:

- stale data,
- lost acknowledgement,
- duplicate commands,
- ambiguous device names.

### 22.2 Suggested benchmark dataset

Build a small internal benchmark of realistic smart-home utterances across:

- explicit control,
- ambiguous control,
- grouped commands,
- sensor/trend questions,
- anomaly explanations,
- corrections and follow-ups,
- multi-lingual or Vietnamese/English mixed expressions if relevant.

---

## 23. Suggested Implementation Roadmap

The correct roadmap is not “add more agents first.” It is “strengthen the runtime first.”

## Phase 1 — Establish strong contracts and runtime lifecycle

Highest priority.

Build:

- `RouteDecision`
- `ToolProposal`
- `PolicyDecision`
- `VerificationResult`
- `ToolExecutionResult`
- `ActionSummary`

Refactor execution into:

- validation,
- policy,
- execution,
- verification,
- audit.

**Outcome:** HERA becomes operationally truthful.

## Phase 2 — Harden device control

Implement:

- clarification paths,
- per-device policy checks,
- before/after state recording,
- verification-aware responses,
- idempotency detection,
- simple device concurrency control.

**Outcome:** the most safety-critical path becomes much stronger.

## Phase 3 — Redesign memory

Introduce:

- stable memory,
- live state memory,
- action summary memory.

Reduce reliance on raw chat history for operational continuity.

**Outcome:** better follow-up control, less prompt pollution.

## Phase 4 — Upgrade sensor and anomaly specialists

Add:

- telemetry windows,
- freshness checks,
- trend summaries,
- recent-action correlation,
- better cause classification.

**Outcome:** HERA becomes more analytically valuable.

## Phase 5 — Add observability and audit rigor

Implement:

- trace IDs,
- structured audit records,
- latency metrics,
- failure taxonomy,
- admin/debug views.

**Outcome:** HERA becomes supportable and debuggable.

## Phase 6 — Add personalization safely

Only after the core runtime is trustworthy.

Introduce:

- `PreferenceContextService`,
- user behavior summaries,
- confidence-rated suggestions,
- proactive recommendation thresholds.

**Outcome:** HERA evolves from command executor into adaptive assistant.

---

## 24. What “Production-Ready” Should Mean for HERA

For HERA, production-ready does **not** need to mean hyperscale cloud infrastructure. It means the runtime can be trusted to behave correctly and transparently under realistic conditions.

A production-ready HERA should satisfy these criteria:

### 24.1 Architectural criteria

- clear contracts between orchestration, planning, execution, verification, memory, and audit;
- deterministic runtime around physical actions;
- bounded specialist responsibilities.

### 24.2 Operational criteria

- no false success claims for unverifiable actions;
- safe ambiguity handling;
- offline/stale-data awareness;
- stable action summaries for follow-up commands.

### 24.3 Engineering criteria

- traceability across request lifecycle;
- structured logs and metrics;
- clear error taxonomy;
- isolated components that are testable.

### 24.4 Product criteria

- natural user responses;
- continuity across turns;
- useful sensor/anomaly reasoning;
- future support for personalization and proactive assistance.

---

## 25. Final Recommendation

The most important recommendation is this:

> **Do not try to make HERA impressive by multiplying agents. Make HERA impressive by turning the existing orchestrator-specialist pipeline into a controlled action runtime with explicit contracts, policy, verification, memory, and audit.**

That is the path that will make `BE/HERA`:

- more robust,
- more explainable,
- more testable,
- more truthful,
- safer for physical control,
- and much more compelling as both a technical project and a thesis-grade system.

In practical terms, HERA should evolve from:

```text
router + parser + executor
```

into:

```text
control plane + scoped planners + deterministic runtime + verification + operational memory + audit trail
```

That transformation is what will move it from a lightweight multi-agent demo into a genuinely valuable and production-aligned AIoT backend.

---

## 26. Condensed Action Checklist

If implementation must start immediately, the first concrete tasks should be:

1. Add typed runtime contracts in `core/message.py`.
2. Split `ToolRegistry` into capability, policy, execution, and verification layers.
3. Refactor `DeviceControlAgent` from parser into bounded planner.
4. Upgrade `Orchestrator` into a real route-and-control decision layer.
5. Add action summary memory instead of relying on raw chat history.
6. Introduce structured audit logging with trace IDs.
7. Add telemetry freshness and verification-aware user responses.
8. Only then expand toward personalization and proactive behavior.

---

## Closing Note

HERA already has the most important asset: **a real system boundary connecting LLM reasoning to physical control**. That makes the design problem both harder and more meaningful.

The next step is not to make it more magical. The next step is to make it more disciplined.

That discipline is what will make the system truly worth building.


---

## 27. Framework and Technology Stack Additions Required to Realize This Architecture

After reviewing the current codebase and the later design discussion around memory, database strategy, and production operations, the architectural recommendation can now be made more concrete.

HERA does **not** need many unrelated frameworks.
It needs a **small number of carefully chosen layers** that each solve a specific class of problem.

### 27.1 Recommended stack by responsibility

#### A. Multi-agent orchestration and stateful workflow
Recommended addition:

- **LangGraph**

Recommended role:

- model request handling as a typed state graph;
- preserve execution checkpoints;
- support orchestrator-to-specialist routing;
- provide controlled transitions between planning, policy, execution, verification, memory update, and final response stages.

Why this fits HERA:

- HERA is not just a chatbot;
- it is a stateful smart-home runtime with physical side effects;
- the system already has a natural graph shape;
- the current orchestrator should become a control plane rather than a free-form dispatcher.

LangGraph should therefore be used for:

- state management,
- workflow orchestration,
- checkpointing,
- and execution topology.

It should **not** replace HERA's custom runtime logic for:

- policy enforcement,
- device execution,
- verification,
- or audit persistence.

#### B. Typed contracts and structured runtime schemas
Recommended addition:

- **Pydantic v2**

Recommended role:

- define all runtime input/output contracts;
- validate specialist proposals;
- validate tool requests and tool results;
- generate stable schemas for testing and future API exposure;
- reduce fragile ad-hoc JSON parsing.

Pydantic should be used for objects such as:

- `RouteDecision`
- `CapabilityGrant`
- `ToolProposal`
- `PolicyDecision`
- `VerificationResult`
- `ToolExecutionResult`
- `ActionSummary`
- `UserProfileContext`

#### C. Distributed tracing, metrics, and structured observability instrumentation
Recommended addition:

- **OpenTelemetry**

Recommended role:

- assign trace IDs to every request;
- correlate orchestrator, specialist, tool runtime, MongoDB, MQTT, and adapter activity;
- export traces, metrics, and structured logs to downstream backends;
- unify observability across Python services and future dashboard/admin tools.

OpenTelemetry is the correct place to instrument:

- request lifecycle spans,
- per-agent latency,
- tool execution spans,
- verification spans,
- database call spans,
- MQTT publish/ack spans.

#### D. Metrics, dashboards, and alerts
Recommended additions:

- **Prometheus**
- **Grafana**
- **Alertmanager**

Recommended role:

- collect service-level and domain-level metrics;
- build operator dashboards;
- define alerts for failing verification, stale telemetry, offline gateways, and rising error rates.

These tools should carry the numerical health-monitoring burden rather than overloading MongoDB for operational dashboards.

#### E. Error monitoring and incident tracking
Recommended addition:

- **Sentry**

Recommended role:

- capture exceptions,
- group runtime failures,
- monitor job failures,
- provide release-aware error visibility,
- support performance/error investigation across runtime changes.

#### F. LLM and agent observability
Recommended addition for the near term:

- **Phoenix**

Recommended role:

- inspect LLM traces,
- compare prompt and agent behaviors,
- evaluate routing and tool-use quality,
- debug regressions in orchestrator or specialist behavior.

Recommended addition for a later, more mature model lifecycle:

- **MLflow**

Recommended role:

- experiment tracking,
- model and prompt lineage,
- evaluation history,
- training and deployment record-keeping,
- personalization model lifecycle management.

#### G. Drift and quality monitoring for ML components
Recommended addition:

- **Evidently**

Recommended role:

- monitor drift for anomaly detection and personalization models;
- run periodic batch checks;
- compare current feature and prediction distributions against a baseline.

### 27.2 What should remain custom HERA code

The following parts should remain HERA-native rather than outsourced to a framework:

- `PolicyEngine`
- `VerificationService`
- `ToolRunner`
- `DeviceExecutor`
- `MemoryService`
- `AuditWriter`
- device-specific concurrency control
- MQTT read-back logic
- alias resolution logic
- personalization context injection rules

This distinction matters.
HERA will become valuable not because it uses many frameworks, but because it uses a few frameworks **around** a well-designed custom runtime core.

### 27.3 What should not be added yet

HERA does **not** need the following in the near term:

- a separate vector database,
- Kafka or a heavy event bus platform,
- a second orchestration framework,
- peer-to-peer autonomous agent swarms,
- a planner-reviewer chain for all requests,
- a large distributed microservice decomposition.

Those would likely increase operational burden faster than they create value.

---

## 28. Memory, Database Strategy, and MLOps for HERA

The earlier sections argued that HERA needs stronger memory and observability.
This section now makes the database and MLOps recommendation explicit.

### 28.1 Current database assessment

Based on the repository and follow-up discussion, the current data layer already relies on:

- **MongoDB** for operational collections,
- **MongoDB time-series collections** for telemetry-like data.

That is a strong starting point.

The correct conclusion is:

> HERA does **not** need a second database immediately.
> MongoDB is sufficient for the next major stage of memory and operational persistence, provided the schema is redesigned around structured runtime memory rather than raw conversation history.

### 28.2 MongoDB is sufficient for HERA's first serious memory architecture

MongoDB should continue as the primary operational database for the following categories.

#### A. Working/session memory
Example collection:

- `session_threads`

Stores:

- active conversation state,
- short rolling context window,
- current entity references,
- last tool result,
- unresolved clarification state.

This should be short-lived, bounded, and updated frequently.

#### B. Episodic action memory
Example collection:

- `action_summaries`

Stores:

- original user request,
- interpreted target,
- chosen capability,
- policy decision,
- execution result,
- verification status,
- before/after state,
- timestamp,
- trace or audit references.

This is the most important memory collection for follow-up control and operational continuity.

#### C. Stable user and environment profile memory
Example collections:

- `user_profiles`
- `device_aliases`
- `environment_profiles`

Stores:

- aliases,
- room mappings,
- preference summaries,
- user/device ownership,
- learned habits,
- safety-related default interpretations.

#### D. Audit and runtime history
Example collection:

- `tool_audit_logs`

Stores:

- request metadata,
- selected specialist,
- route decision,
- tool proposals,
- policy outputs,
- execution outcomes,
- verification outcomes,
- latencies,
- error classes.

#### E. Telemetry and sensor history
Example collection:

- `telemetry_points`

This should remain a time-series collection and continue to store:

- temperature,
- humidity,
- anomaly scores,
- device-side measurements,
- freshness timestamps,
- per-device metadata.

### 28.3 What “AI memory” should mean in HERA

HERA should not define memory as “whatever text the model saw recently.”

Instead, AI memory should be defined as structured state across four layers:

1. **working memory** for the current interaction;
2. **episodic memory** for recent actions and outcomes;
3. **stable semantic/profile memory** for preferences and aliases;
4. **operational telemetry memory** for device and sensor history.

That design is much more robust than transcript-centric memory and works naturally with MongoDB's strengths.

### 28.4 When a second database may become useful

A second database should only be added if a real operational need emerges.

#### Add Redis only if one of these becomes painful:

- multiple workers concurrently control the same device,
- short-lived caching becomes necessary,
- per-device distributed locks are required,
- cooldown/rate-limit enforcement becomes hot-path critical.

Redis is therefore an optimization or concurrency layer, not a mandatory foundation.

#### Add a relational database only if one of these becomes painful:

- compliance-style reporting,
- complex SQL analytics,
- many cross-collection joins become central,
- the team wants a relational reporting plane separate from the operational runtime.

#### Add vector retrieval only if one of these becomes painful:

- semantic retrieval over large long-form text history,
- user memory retrieval based on meaning rather than metadata,
- large-scale language retrieval beyond structured action memory.

Until then, HERA should stay with a **Mongo-first** design.

### 28.5 MLOps requirements by system layer

HERA should distinguish clearly among the following operational concerns.

#### A. Runtime and service observability
Questions answered:

- Is the service healthy?
- Is latency rising?
- Are MQTT publishes timing out?
- Is verification failing more often?
- Are devices appearing offline?

Recommended stack:

- OpenTelemetry
- Prometheus
- Grafana
- Alertmanager
- Sentry

#### B. Agent and LLM observability
Questions answered:

- Is routing quality degrading?
- Which specialist fails most often?
- Which prompt version increased token cost?
- Are tool proposals becoming more ambiguous?
- Which requests require repeated clarification?

Recommended stack:

- Phoenix for LLM/agent traces and evaluation;
- optional later MLflow for long-term lineage and experiment tracking.

#### C. ML model monitoring
Questions answered:

- Is the anomaly model drifting?
- Is personalization still aligned with user behavior?
- Are feature distributions changing over time?
- Are score distributions shifting?

Recommended stack:

- Evidently for drift and monitoring jobs;
- MLflow later for experiment and model lifecycle management.

### 28.6 Recommended monitoring categories for HERA

The following metrics and monitoring categories should be treated as first-class.

#### Runtime metrics

- request count,
- total request latency,
- per-stage latency,
- tool timeout count,
- retry count,
- database latency,
- MQTT publish latency,
- MQTT verification latency,
- stale telemetry rate,
- gateway offline rate.

#### Agent quality metrics

- route distribution,
- clarification rate,
- policy deny rate,
- policy modify rate,
- no-op rate,
- verified success rate,
- unverified execution rate,
- per-specialist failure rate,
- hallucinated target rate.

#### Model and personalization metrics

- anomaly score distribution drift,
- suggestion acceptance rate,
- feature drift,
- prediction drift,
- retraining job success rate,
- evaluation trend over time.

### 28.7 Final database and MLOps recommendation

The strongest practical recommendation is this:

- keep **MongoDB** as the primary operational and memory database;
- continue using **time-series collections** for telemetry;
- redesign memory around `session_threads`, `action_summaries`, `user_profiles`, and `tool_audit_logs`;
- add **OpenTelemetry + Prometheus/Grafana/Alertmanager + Sentry** for health and reliability;
- add **Phoenix** for agent and LLM tracing/evaluation;
- add **Evidently** for ML drift monitoring when anomaly/personalization models mature;
- add **MLflow** only when the project's training and experimentation lifecycle becomes large enough to justify it;
- add **Redis only if concurrency or lock-management becomes a real bottleneck**.

That stack is realistic, incremental, and aligned with HERA's current codebase rather than requiring a full platform reset.
