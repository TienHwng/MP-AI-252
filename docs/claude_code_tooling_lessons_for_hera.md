# Core Tool-Orchestration Lessons For HERA

## Scope

This document does not record source files, modules, programming languages, frameworks, or implementation-specific details.

The goal is to extract core ideas and core logic that can be applied to HERA: how to design tool use, tool calling, orchestration, policy, verification, memory, and auditability for an agentic smart-home system.

The central idea:

> The LLM understands intent and proposes actions. The runtime decides, executes, verifies, and records what actually happens.

## Design Axioms

### 1. The Model Proposes, The Runtime Decides

The model should not directly "control the home." It should produce a structured proposal:

```text
capability: control_device
arguments: target, desired_state, scope
```

The runtime then:

- validates the target;
- checks policy;
- checks context;
- executes only if allowed;
- verifies the resulting state;
- writes an audit record;
- returns a structured result to the model.

Implication for HERA: model output, whether text or JSON, should not be treated as a real command. A real command only exists after the runtime accepts it.

### 2. Tool Calling Is A Protocol

Tool calling is not string parsing. It should be a protocol with a clear lifecycle:

```text
model proposes tool call
  -> runtime validates
  -> runtime authorizes
  -> runtime executes
  -> runtime verifies
  -> runtime returns matched result
  -> model summarizes from result
```

Every tool call must have a matching tool result. Even denial, schema failure, timeout, missing target, or offline gateway should become a valid tool result.

Without this pairing rule, the agent loop becomes fragile: the model can speak as if a tool succeeded even when the runtime never confirmed it.

### 3. Tool Contracts Must Be Explicit

A good tool needs more than a name and description. It needs a contract:

- input schema;
- output schema;
- effect type: read-only, mutating, physical, destructive;
- default policy;
- ambiguity rules;
- timeout;
- concurrency rules;
- result budget;
- audit fields.

For HERA, device-control tools are physical mutating tools, so they need stricter handling than sensor reads or anomaly queries.

### 4. The Runtime Owns The Lifecycle

A standard tool lifecycle should look like this:

```text
resolve capability
  -> validate schema
  -> normalize arguments
  -> domain validation
  -> policy decision
  -> execute
  -> verify observable state
  -> map to structured result
  -> audit
```

Schema validation only answers: "Does the data have the right shape?"

Domain validation answers the smart-home questions that actually matter:

- does the device or room exist;
- is the requested state valid;
- is the request ambiguous;
- does the action fit the device type;
- is the gateway or registry available;
- is the user referring to prior context.

### 5. Policy Is Not A Boolean

Policy should return one of several decisions:

- allow: execute the action;
- deny: refuse the action;
- ask: ask the user for clarification or confirmation;
- modify: rewrite the arguments into a safer form before execution.

HERA's policy layer should at least cover:

- deny missing targets;
- ask when the target is ambiguous;
- ask when the action is too broad, such as "turn everything on";
- no-op when the requested state is already true;
- deny when the gateway is offline;
- throttle repeated commands;
- require confirmation for high-risk device groups;
- log all physical commands.

### 6. Execution Should Be Idempotent

Physical control should be idempotent.

If the user says "turn on the light" and the light is already on, the runtime does not need to send another command. The result should say:

```text
ok: true
reason: already_in_requested_state
changed: []
unchanged: [light]
```

For group actions, the result should not be a single "success" value. It should separate:

- changed;
- unchanged;
- failed;
- skipped;
- denied.

### 7. Verification Is Separate From Execution

"Command sent" is not the same as "device state verified."

After an action, the runtime should verify through observable state:

- state snapshot;
- fresh telemetry;
- gateway acknowledgment;
- registry read-back.

The final answer should distinguish:

- verified success;
- command sent but unverified;
- already in requested state;
- partial success;
- denied;
- failed;
- needs clarification.

This is critical for smart-home control. The model should not say "done" if the system only published a command and did not verify the resulting state.

### 8. Results Must Be Structured

A tool result should contain:

```text
tool_call_id
ok
reason
facts
summary_for_model
before_state
after_state
verification
audit_metadata
error_kind
```

The model should produce the final answer from these facts and results. It should not infer success or failure on its own.

## Orchestrator As Control Plane

The orchestrator should not be just a router. It should be the control plane of the system.

The orchestrator is responsible for:

- understanding intent;
- selecting a specialist;
- granting a capability scope;
- attaching relevant context;
- deciding whether to clarify, execute, or deny;
- running the agent loop;
- receiving a structured specialist report;
- composing the final answer from verified facts;
- updating memory.

Specialists should not have global authority. Each specialist should only see the capabilities it needs:

- device control: actuators and device state;
- sensor analysis: sensor reads and history;
- anomaly expert: anomaly data and sensor context;
- digital twin: simulation and prediction;
- safety verifier: read-only verification.

Scoped capabilities keep prompts smaller, reduce the risk of wrong tool selection, and make auditing easier.

## Recommended Agent Loop

HERA should move toward this flow:

```text
User message
  -> Orchestrator
       classify intent
       choose specialist
       grant scoped capabilities
       attach relevant memory
  -> Specialist loop
       model proposes tool calls
       runtime executes through lifecycle
       structured tool results return to model
       repeat until done or limit reached
  -> Specialist report
       intent, facts, actions, verification, uncertainty
  -> Final composer
       answer from verified facts
       ask clarification if needed
  -> Memory update
       compact action summary
```

The fragile alternative is:

```text
model outputs JSON text
  -> app parses JSON
  -> app executes directly
```

That approach is weak at handling ambiguity, policy, partial success, timeout, multi-step tool use, and auditability.

## Context And Memory

HERA should not keep long raw tool traces in the prompt forever. Context should be split into three layers.

### Stable Rules

Rules that change rarely:

- device permissions;
- room and device naming;
- safety policy;
- anomaly thresholds;
- response style.

### Live State

State that changes quickly:

- latest sensor values;
- device states;
- gateway online/offline status;
- recent telemetry timestamp.

Live state should be read when needed, not treated as permanent truth inside the prompt.

### Action Summary

After each meaningful action, store a compact summary:

```text
user_request
interpreted_target
action
result
verified_state
timestamp
follow_up_reference
```

Action summaries help handle follow-ups such as "turn it off", "turn the previous one back on", or "why did it not work" without keeping the entire raw trace.

## Audit And Observability

Every physical action should leave an audit record that can answer:

- what the user asked for;
- which agent handled it;
- which tool was called;
- what the original and normalized arguments were;
- what policy decided;
- what the state was before execution;
- what command was sent;
- what the state was after execution;
- what verification concluded;
- what error occurred, if any;
- how long it took.

Auditability is not only for debugging. It is evidence that HERA does not hand direct smart-home control to the LLM.

## Extensibility Model

As the system grows, capabilities should not be hard-coded into the orchestrator. HERA should use a capability-provider model:

```text
domain provider
  -> exposes capability specs
  -> common tool runtime executes them
  -> orchestrator grants scoped access
```

Future domains can include:

- device control;
- sensor reading;
- anomaly detection;
- digital twin simulation;
- user preference;
- notification;
- scheduling.

All domains should pass through the same runtime lifecycle. If every domain invents its own execution path, policy, audit, and extension become harder.

## What Not To Copy Yet

Some mechanisms are useful later, but they are not the immediate priority for HERA:

- dynamic plugin marketplaces;
- heavy background multi-agent orchestration;
- large permission classifiers;
- multi-layer context compaction;
- parallel subagents for small tasks.

HERA should prioritize the core first:

- tool contracts;
- tool runner;
- policy;
- verification;
- structured results;
- audit;
- action-summary memory;
- orchestrator as control plane.

## Practical Roadmap For HERA

### Phase 1: Structured Tool Results

Standardize every tool result as an object with `ok`, `reason`, `facts`, `before`, `after`, `changed`, `failed`, and `verification`.

Goal: the final composer should not have to infer outcomes from free-form strings.

### Phase 2: Common Tool Runner

Introduce one shared pipeline:

```text
validate -> normalize -> policy -> execute -> verify -> audit -> result
```

Every future domain should pass through this pipeline.

### Phase 3: Real Tool Loop For Device Control

Replace model-generated JSON text with structured tool calls. The runtime executes the call and returns the result to the model, which then writes the user-facing answer.

### Phase 4: Physical Action Policy

Add rules for ambiguity, broad actions, offline gateways, repeated commands, no-op states, and confirmation.

### Phase 5: Verification Layer

After every command, read back state or acknowledgment. The final answer must distinguish verified execution from merely sent commands.

### Phase 6: Action Summary Memory

Instead of resetting context after tool use, store a compact summary of the action and the currently referenced entities.

### Phase 7: Capability Providers

As the number of tools grows, split domains into providers and let the orchestrator grant scoped capabilities to specialists.

## Thesis Framing

HERA's architecture can be described like this:

> HERA treats the LLM as an intent interpreter and planner, while all real-world actions are mediated by a deterministic runtime that validates, authorizes, executes, verifies, and audits every operation.

This sentence captures the important logic:

- the LLM does not hold final execution authority;
- every physical action passes through a policy gate;
- results must be verified;
- the system has an audit trail;
- final answers are based on facts, not model belief.

## Final Takeaway

The main lesson: tool use is not simply "letting the model call a function." Tool use is the design of a controlled action protocol.

Applied well, HERA should look like this:

```text
LLM plans
Runtime validates
Policy authorizes
Executor acts
Verifier checks
Auditor records
Composer answers
Memory summarizes
```

This is the foundation for making HERA an explainable, verifiable, and extensible agentic smart-home system rather than just a chatbot with a few API calls.
