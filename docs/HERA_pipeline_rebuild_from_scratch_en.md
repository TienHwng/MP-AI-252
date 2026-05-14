# HERA Pipeline - Rebuild From Scratch and Capability Inventory

This document describes HERA as if the system had to be rebuilt from scratch. It starts from goals, capabilities, architectural layers, request pipelines, IoT execution, dashboard integration, telemetry, memory, safety, observability, and future extension paths.

It does not describe individual source files or code internals. The perspective here is system architecture: if the HERA folder had never existed, what pipeline should be designed to build a reliable AIoT assistant?

## 1. What HERA Is

HERA is an AIoT assistant for a smart-home environment. It combines:

- Conversational AI.
- Multi-agent orchestration.
- Device control through MQTT.
- Realtime telemetry from sensors and devices.
- A monitoring and control dashboard.
- Memory for conversations and actions.
- Anomaly analysis.
- Web research.
- Simulation mode and real-hardware mode.

The most important design rule is:

> The LLM may understand, explain, and propose. The runtime is the only layer allowed to decide, execute, verify, and audit physical actions.

For a smart-home system, this boundary matters. A command such as "turn on the fan" is not just text generation; it can change the state of a physical device. HERA should therefore be a controlled action runtime, not merely a chatbot.

## 2. HERA Capability Inventory

### 2.1 Communication Capabilities

HERA can receive requests from multiple channels:

- Telegram.
- Dashboard chat.
- Dashboard control UI.
- Dashboard floor plan.
- Future voice assistant integration.

Every request should be normalized into a shared request format containing:

- User text or action payload.
- Source channel.
- User ID.
- Session ID.
- Runtime metadata.
- Received timestamp.
- Relevant context.

### 2.2 Intent Understanding

HERA should classify requests into these main categories:

- Device control.
- Sensor status query.
- Anomaly query.
- Web research.
- General conversation.
- Confirmation or cancellation of a pending action.
- Contextual follow-up, such as "turn off the one I just turned on."

### 2.3 Device Control Capabilities

HERA can control:

- Main LED.
- NeoPixel LED.
- WS2812 LED.
- Relay.
- Mini fan.
- All supported lights.
- All supported devices.

Supported control operations:

- Turn a device on or off.
- Set NeoPixel brightness.
- Set WS2812 brightness.
- Set WS2812 color.
- Set mini fan speed.
- Run scenes made of multiple device actions.

### 2.4 Sensor Reading Capabilities

HERA can read and interpret:

- Temperature.
- Humidity.
- Light level.
- Gas level.
- Gas detected state.
- Anomaly score.
- WiFi/MQTT connection state.
- RSSI.
- Uptime.
- Current device states.

### 2.5 Environmental Analysis

HERA can:

- Answer current temperature and humidity questions.
- Report whether values are inside normal ranges.
- Warn when data is missing or stale.
- Explain anomaly severity.
- Combine threshold rules with anomaly scores.
- Read recent telemetry windows for additional context.

### 2.6 Anomaly Capabilities

HERA can classify anomalies as:

- Normal.
- High temperature.
- Low temperature.
- High humidity.
- Low humidity.
- ML-detected anomaly.
- Stale telemetry.
- Unknown or missing data.

Each anomaly result should include:

- Anomaly type.
- Severity.
- Relevant readings.
- Reference thresholds.
- Data freshness.
- Recommended action.

### 2.7 Web Research Capabilities

HERA can:

- Search the web.
- Fetch a URL.
- Look up weather.
- Look up news.
- Fall back to generic search if a specialized service fails.
- Summarize answers from retrieved evidence.

This is a read-only pipeline and should not enter the physical action runtime.

### 2.8 Dashboard Capabilities

The dashboard can support:

- Login.
- Device claiming.
- Realtime sensor display.
- Telemetry streaming.
- Historical analytics.
- Device on/off control.
- Floor-plan control.
- Intensity adjustment.
- Scene activation.
- Chat with HERA.
- Activity logs.
- Runtime status.
- AI provider/model settings.

### 2.9 Simulation Capabilities

Simulation mode supports:

- Simulated devices.
- Simulated telemetry.
- Simulated anomaly data.
- Simulated RPC responses.
- Sensor value overrides.
- Dashboard testing without hardware.
- AI pipeline testing without hardware dependency.

### 2.10 Hardware Capabilities

Hardware mode supports:

- Connecting ESP32/YoLo UNO-class boards to the same MQTT broker.
- Reading real sensors.
- Controlling real relay, LED, fan, LCD, and related modules.
- Replacing the simulator with real firmware while keeping the same backend contract.

### 2.11 Memory Capabilities

HERA memory includes:

- Session memory: recent conversation turns.
- Action memory: what the user did, which device was targeted, and what happened.
- User profile: user-level preferences or context.
- Recent action focus: useful for follow-ups such as "turn it off", "the one I just turned on", or "that device."

Memory should not be only prompt history. In AIoT, the most important memory is operational memory.

### 2.12 Model Configuration Capabilities

HERA can separate models by role:

- Orchestrator model.
- Device-control model.
- Sensor-analysis model.
- Anomaly-expert model.

Providers can include:

- Local model runtime.
- Cloud model provider.

The intended design is that each specialist can use a model suited to its latency, cost, and reasoning requirements.

## 3. Rebuild Principles

If HERA were rebuilt from scratch, these principles should guide the architecture:

1. The runtime owns physical actions, not the LLM.
2. Every write action must pass validation, policy, execution, verification, and audit.
3. Read-only requests should have a lightweight short path.
4. Device-control requests should pass through the full controlled runtime.
5. Telemetry is the source of truth for observed state.
6. Memory must be structured and should not rely entirely on chat history.
7. Dashboard actions and assistant actions must use the same action runtime.
8. Simulation mode and hardware mode must share the same contract.
9. Observability must answer: who asked, what the system understood, what command was sent, and whether the device actually changed state.
10. Personalization learns preferences; it does not replace safety rules.

## 4. Overall Architecture

High-level pipeline:

```text
User / Dashboard / Automation
-> Interface Adapter
-> Request Normalization
-> Orchestrator Control Plane
-> Memory + Live Context Retrieval
-> Specialist Agent
-> Runtime Policy Layer
-> MQTT Execution Layer
-> Device / Simulator
-> Telemetry + Attributes
-> Verification
-> Audit + Memory Update
-> Final Response
```

The system has eight conceptual layers:

1. Interface layer.
2. Orchestrator control plane.
3. Specialist agent layer.
4. Runtime action layer.
5. MQTT/IoT layer.
6. Telemetry and state layer.
7. Memory and personalization layer.
8. Dashboard and observability layer.

## 5. Pipeline 0 - System Startup

When HERA starts, the startup pipeline should be:

```text
Load environment
-> Load runtime settings
-> Connect database
-> Connect MQTT broker
-> Register capabilities
-> Start telemetry listener
-> Start assistant adapters
-> Start dashboard API
-> Start dashboard UI
```

Startup must determine:

- Whether the runtime is in simulation or hardware mode.
- Which MQTT broker is used.
- Which database is used.
- Which AI provider and models are active.
- Which capabilities are available.
- Which devices are supported.
- Whether recent telemetry is available.

Failure handling should be isolated:

- Telegram failure should not kill the dashboard.
- Dashboard failure should not kill the MQTT listener.
- Model-provider failure should be reported as assistant unavailability.
- MQTT failure should block device-control write actions.

## 6. Pipeline 1 - Request Intake and Normalization

Every request from Telegram, dashboard chat, dashboard buttons, or automation should be normalized.

Raw inputs:

- Text message.
- Button or floor-plan action.
- Scene activation.
- API request.

Normalized request output:

- Request ID.
- User ID.
- Session ID.
- Channel.
- Original text or action.
- Timestamp.
- Client metadata.
- Runtime mode.
- Correlation ID.

Why this stage is required:

- It makes the full request lifecycle traceable.
- It allows dashboard and Telegram to share one pipeline.
- It supports audit and latency tracking.
- It gives memory a stable user/session key.

## 7. Pipeline 2 - Routing and Risk Classification

After normalization, the orchestrator classifies the request:

```text
Incoming request
-> intent classification
-> risk classification
-> capability scope assignment
-> memory scope assignment
-> specialist selection
```

The routing result should include:

- Intent.
- Specialist.
- Whether execution is required.
- Risk level.
- Capability scope.
- Whether clarification is required.
- Maximum tool steps.

Risk levels:

- Low: sensor reads, general questions, web search.
- Medium: turn device on/off, set brightness, set fan speed.
- High: broad multi-device control, conditional automation, safety-sensitive actions.

## 8. Pipeline 3 - Memory Retrieval

Memory retrieval should be scoped by intent.

General request:

- Retrieve lightweight session memory, or skip memory for trivial greetings.

Sensor/anomaly request:

- Retrieve user profile if preferences matter.
- Retrieve telemetry context.

Device-control request:

- Retrieve recent actions.
- Retrieve device focus.
- Retrieve user profile.
- Retrieve recent session context.

Web search:

- Retrieve session context if the question is a follow-up.

Memory output:

- Recent turns.
- Recent actions.
- User profile.
- Device focus.
- Reason if memory is unavailable.

## 9. Pipeline 4 - Device-Control Runtime

This is HERA's most important pipeline.

```text
Device request
-> route as device_control
-> retrieve recent action memory
-> specialist interprets command
-> generate tool/action proposal
-> validate schema and target
-> policy decision
-> execute MQTT RPC
-> wait for response/attributes
-> verify read-back
-> record action memory
-> compose final response
```

### 9.1 Device Specialist

The device specialist must answer:

- Does the user want to turn on, turn off, set a value, query status, or create a condition?
- Which device is targeted?
- Is the target clear?
- What value should be set?
- Does the value have a unit or range?
- Is this a contextual follow-up?
- Is clarification required?

The output should not be free-form prose. It should be a structured action proposal.

### 9.2 Capability Validation

The runtime checks whether the action proposal is inside the allowed capability scope.

Example capabilities:

- Get device status.
- Turn on device.
- Turn off device.
- Set device value.
- Set simulator sensor value.

If a specialist proposes an unknown capability, the runtime rejects it.

### 9.3 Policy Decision

Policy may return:

- Allow: execute the action.
- Ask: ask the user for clarification.
- Deny: block the action.
- Noop: no action needed because the requested state is already true.

Policy should block or redirect:

- Unclear target.
- Invalid target.
- Offline device.
- Offline MQTT broker.
- Unconfirmed all-devices command.
- Out-of-range value.
- Simulation-only command in hardware mode.
- Duplicate action where the device is already in the requested state.

### 9.4 Execution

If policy allows execution:

- The runtime creates an RPC request.
- It publishes the request to the MQTT broker.
- The device or simulator receives the request.
- The device or simulator applies the change.
- The device or simulator publishes a response.
- The device or simulator publishes updated attributes/state.

Execution only means the command was sent or applied according to the response. It is not enough to claim that the physical device changed state unless verification succeeds.

### 9.5 Verification

Verification reads state after execution.

Possible verification results:

- Verified: observed state matches expected state.
- Noop: no command was needed because state already matched.
- Failed: response or state did not match.
- Timeout: no state change observed within the wait period.
- Unverified: command was sent, but no reliable read-back is available.
- Rejected: policy blocked the action.

### 9.6 Final Response

The final response must reflect runtime truth:

- Verified: "The light is now on."
- Noop: "The light was already on."
- Ask: "Which device do you want to control?"
- Denied: "The device appears offline."
- Timeout: "I sent the command, but could not verify the device state."
- Failed: "The command did not complete successfully."

## 10. Pipeline 5 - Sensor Query

Sensor queries are read-only.

```text
Sensor question
-> route as sensor_query
-> get latest telemetry snapshot
-> check availability
-> compare with reference thresholds
-> compose answer
```

Output should include:

- Current value.
- Unit.
- Last update time.
- Whether data is stale.
- Whether the reading is inside the normal range.
- Whether the sensor is available.

Examples:

- Current temperature.
- Current humidity.
- Current light level.
- Whether gas exceeds the threshold.
- Which devices are on.

## 11. Pipeline 6 - Anomaly Query

```text
Anomaly question
-> route as anomaly_query
-> get latest telemetry
-> compute freshness
-> read telemetry window
-> classify anomaly
-> estimate severity
-> compose explanation and recommendation
```

Required checks:

- Last-seen timestamp.
- Age in seconds.
- Stale threshold.
- Temperature range.
- Humidity range.
- Gas threshold.
- Anomaly score threshold.
- Telemetry window point count.

Severity levels:

- None.
- Low.
- Medium.
- High.
- Unknown when telemetry is stale or missing.

Important rule: if telemetry is stale, HERA should not confidently say the home is safe. It should say that current data is not fresh enough to support a confident conclusion.

## 12. Pipeline 7 - Web Research

```text
Web/search question
-> route as web_search
-> classify search subtype
-> use specialized service if available
-> fallback to generic search
-> optionally fetch top result
-> extract evidence
-> compose answer with source awareness
```

Subtypes:

- Weather.
- News.
- URL fetch.
- Generic search.

Rules:

- Weather and news questions require fresh data.
- URL questions should fetch the URL.
- If a specialized service fails, fall back to generic search.
- Do not overstate confidence when evidence is weak.

## 13. Pipeline 8 - Dashboard Control

Dashboard actions should not bypass the runtime.

```text
User clicks dashboard control
-> dashboard sends structured action
-> HERA runtime receives action
-> policy check
-> MQTT execution
-> verification
-> telemetry update
-> dashboard refreshes state
-> activity log records event
```

Reasons:

- Telegram and dashboard share one source of truth.
- Logs are consistent.
- Policy is consistent.
- Device state is not faked on the frontend.
- If a command fails or times out, the dashboard can show the real status.

## 14. Pipeline 9 - Telemetry Ingestion

Telemetry pipeline:

```text
Device/simulator publishes telemetry
-> MQTT manager/listener receives payload
-> normalize nested sensor/device schema
-> attach metadata
-> store latest snapshot
-> persist time-series record
-> update dashboard stream
-> make data available for sensor/anomaly agents
```

Telemetry should include:

- recorded_at.
- device_id.
- environment_id.
- user_id if the device is claimed.
- sensors.
- devices.
- network.
- runtime metadata.
- source topic.
- quality.

### 14.1 Time-Series Storage

Telemetry is time-series data: many points over time, attached to device/source metadata, rarely updated after insertion. Storage should be optimized for time-range and device-based queries.

MongoDB recommends time-series collections for sensor and IoT data because they optimize storage, indexing, and time-based queries. If MongoDB is used long term, telemetry points should be designed with a time field and metadata field from the beginning.

## 15. Pipeline 10 - Activity Log and Audit

Every action should have a lifecycle:

```text
issued
-> interpreted
-> policy_checked
-> published
-> received
-> applied
-> acknowledged
-> observed
-> verified / failed / timeout
```

Audit records should answer:

- Who requested the action?
- When was it requested?
- Through which channel?
- What was the original text?
- What action did the system infer?
- What policy decision was made?
- Which MQTT command was sent?
- Did the device acknowledge it?
- What was the before/after state?
- What was the verification status?
- What was the latency?
- What error occurred, if any?

Without audit, HERA will be hard to debug during hardware demos.

## 16. Pipeline 11 - Memory Update

After every request:

```text
final response
-> record session turn
-> if tools used: record action summary
-> update recent focus
-> optionally update user profile
```

Action summaries should store:

- Original request.
- Interpreted action.
- Targets.
- Result status.
- Verification status.
- Changed entities.
- Unchanged entities.
- Failed entities.
- Timestamp.
- Runtime context.

This memory enables:

- "Turn off the one I just turned on."
- "What about the bedroom light?"
- "Make it brighter."
- "Is that device on or off?"

## 17. Pipeline 12 - Simulation Mode

Simulation mode should fully emulate the hardware contract:

```text
Simulator starts
-> connects MQTT
-> publishes telemetry periodically
-> subscribes to RPC request topic
-> receives command
-> updates internal device state
-> publishes RPC response
-> publishes attributes
-> continues telemetry with updated state
```

Simulation should support:

- Sensor randomization.
- Sensor override.
- Gas anomaly samples.
- Temperature/humidity anomaly samples.
- Device state transitions.
- Brightness/color/speed state.
- Network metadata.

Value of simulation:

- Test AI without a board.
- Test dashboard quickly.
- Test anomaly logic.
- Test policy and verification.
- Demo when hardware is unavailable.

## 18. Pipeline 13 - Hardware Mode

Hardware mode replaces the simulator with a real board:

```text
Firmware boots
-> connects WiFi
-> connects MQTT broker
-> publishes telemetry
-> subscribes to RPC request
-> applies command to pins/modules
-> publishes response and attributes
```

Hardware must preserve:

- Same topic contract as simulation.
- Same payload schema as simulation.
- RPC response whenever possible.
- Attributes or telemetry after state changes.
- Heartbeat or last_seen tracking to detect offline devices.

If simulation and hardware contracts diverge, AI and dashboard behavior will become unstable.

## 19. Pipeline 14 - Future Personalization

Personalization should not replace safety rules. It is a preference-learning layer.

```text
User action
-> async behavior logging
-> feature extraction
-> per-user model training
-> model evaluation
-> model registry/update
-> runtime user context injection
-> proactive suggestion
-> feedback logging
```

Useful features:

- Time of day.
- Day of week.
- Temperature.
- Humidity.
- Light level.
- Device state.
- Recent actions.
- User ID.
- Room/environment ID.

Prediction tasks:

- Next likely action.
- Preferred device state.
- Suggested scene.

Cold start:

- Use a global default.
- Train a per-user model only after enough interactions are collected.

Multi-user conflict handling:

- Role-based priority.
- Temporal priority.
- Compromise strategy.
- Ask the user when conflict is high.

## 20. Short Path and Controlled Path

If rebuilt from scratch, HERA should have two processing paths.

### 20.1 Short Path

Used for:

- Greetings.
- Identity questions.
- Simple sensor snapshots.
- Simple anomaly status.
- General non-tool responses.

Pipeline:

```text
intake
-> lightweight classify
-> read state if needed
-> compose response
-> record turn
```

### 20.2 Controlled Runtime Path

Used for:

- Device control.
- Set value.
- Scene activation.
- Conditional command.
- Broad-scope command.
- Simulation sensor override.

Pipeline:

```text
intake
-> full route
-> memory retrieval
-> specialist planning
-> policy
-> execution
-> verification
-> audit
-> memory
-> response
```

This keeps simple requests fast while keeping side-effecting requests strict.

## 21. Safety Model

HERA needs layered safety.

### 21.1 Input Safety

- Reject empty requests.
- Normalize channel/user/session.
- Rate-limit if needed.

### 21.2 Semantic Safety

- Ask when target is ambiguous.
- Ask when action is ambiguous.
- Ask when a follow-up cannot be safely resolved.

### 21.3 Capability Safety

- Specialists may only propose capabilities inside their granted scope.
- The runtime rejects unknown capabilities.

### 21.4 Device Safety

- Check target validity.
- Check value ranges.
- Check simulation/hardware mode.
- Check MQTT online state.
- Check stale telemetry.

### 21.5 Confirmation Safety

Require confirmation for:

- All-devices actions.
- Broad-scope commands.
- High-risk conditional automation.
- Commands that cannot be verified.

### 21.6 Verification Safety

- Do not say "done" if the action is not verified.
- Distinguish sent, applied, and verified.
- Report timeout clearly.

## 22. Observability

HERA should be observable along three dimensions:

- Traces: which stages a request passed through.
- Metrics: latency, error rate, verification success rate, MQTT reconnect count.
- Logs: detailed events and errors.

OpenTelemetry is a good fit because it is a vendor-neutral framework for traces, metrics, and logs. For HERA, every request should have a correlation ID linking Telegram/dashboard -> orchestrator -> MQTT -> verification -> final response.

Useful metrics:

- Intent count.
- Tool execution count.
- Policy deny count.
- Verification success/fail/timeout.
- Average latency.
- MQTT connected/disconnected.
- Telemetry age.
- LLM provider error.
- Dashboard API error.

## 23. Conceptual Data Model

Independent of a specific database, HERA should have these data groups.

### 23.1 Users

- User identity.
- Telegram/chat mapping.
- Dashboard account.
- Role.

### 23.2 Devices

- Device ID.
- Owner/current user.
- Environment/room.
- Device capabilities.
- Last seen.

### 23.3 Telemetry Points

- Timestamp.
- Device metadata.
- Sensor values.
- Device states.
- Network state.
- Runtime source.
- Quality.

### 23.4 Commands

- Command ID.
- User/session.
- Intent.
- Agent/specialist.
- Tool/capability.
- Params.
- Status.
- Latency.
- Error.

### 23.5 Command Steps

- Issued.
- Policy checked.
- Published.
- Acknowledged.
- Observed.
- Verified.
- Failed/timeout.

### 23.6 Activity Logs

- UI-friendly event log.
- Actor.
- Target.
- Old/new value.
- Severity.
- Message.

### 23.7 Sessions

- Chat messages.
- Assistant responses.
- Intent history.
- Tool usage.

### 23.8 Action Summaries

- Structured action memory.
- Recent target focus.
- Changed/unchanged/failed entities.

### 23.9 Model Settings

- Provider.
- Model per agent.
- Last updated.

### 23.10 Personalization Artifacts

- Behavior logs.
- Learned patterns.
- Suggestion feedback.
- Model metadata.

## 24. Failure Modes to Handle

### 24.1 MQTT Offline

HERA should not send write commands when MQTT is offline. The response should clearly state that the device or broker is not ready.

### 24.2 Stale Telemetry

Sensor and anomaly responses must report stale data. Device verification may time out.

### 24.3 LLM Provider Error

If the model fails:

- General or device parsing may fail.
- Runtime must not execute a command without a valid proposal.
- Dashboard should display provider errors clearly.

### 24.4 Missing Device Acknowledgement

If a command is sent but no response is received:

- Mark timeout.
- Do not update state based on assumption.
- Let the dashboard wait for future telemetry.

### 24.5 Ambiguous Target

If the user says "turn on the light" but multiple lights exist:

- Use a reasonable default or recent focus only if it is safe.
- Otherwise ask for clarification.

### 24.6 Broad Scope

If the user says "turn off every device":

- Require confirmation.
- Execute only after confirmation.

## 25. Roadmap for a Clean Rebuild

### Phase 1 - Baseline Runtime

- Request normalization.
- Routing.
- Device catalog.
- MQTT connection.
- Sensor snapshot.
- Basic dashboard status.

### Phase 2 - Controlled Device Execution

- Capability registry.
- Policy decision.
- MQTT RPC execution.
- Read-back verification.
- Command lifecycle audit.

### Phase 3 - Specialist Agents

- Device planner.
- Sensor reporter.
- Anomaly investigator.
- General assistant.
- Web research agent.

### Phase 4 - Memory

- Session memory.
- Action memory.
- Recent focus.
- User profile.
- Follow-up resolution.

### Phase 5 - Deep Dashboard Integration

- Floor plan uses the same runtime.
- Activity log.
- Telemetry stream.
- Model settings.
- Runtime health.

### Phase 6 - Observability

- Tracing.
- Metrics.
- Structured logs.
- Error taxonomy.
- Verification dashboard.

### Phase 7 - Personalization

- Behavior logging.
- Feature extraction.
- Per-user model.
- Proactive suggestions.
- Conflict resolution.

## 26. Architecture Conclusion

HERA should be treated as a controlled AIoT runtime, not as a chatbot that directly controls devices.

The core pipeline is:

```text
Understand
-> Plan
-> Validate
-> Authorize
-> Execute
-> Verify
-> Remember
-> Explain
```

Where:

- Understand and Explain may use LLMs.
- Plan may use specialist agents.
- Validate, Authorize, Execute, and Verify must be deterministic runtime responsibilities.
- Remember should use structured memory.
- Dashboard must share the same runtime as the assistant.
- Telemetry must be the source of truth.

With this design, HERA can grow from an AIoT demo into a smart-home platform that is explainable, memory-aware, safer, and capable of learning user behavior over time.

## 27. External Research References

The design above was cross-checked against these external references:

- ThingsBoard MQTT Device API: telemetry topic, attributes topic, and server-side RPC pattern. https://thingsboard.io/docs/pe/reference/mqtt-api/
- ThingsBoard MQTT Gateway/API docs: RPC, attributes, gateway/device communication. https://thingsboard.io/docs/reference/gateway-mqtt-api/
- LangGraph overview: durable execution, human-in-the-loop, memory, and workflow orchestration for agents. https://docs.langchain.com/oss/python/langgraph
- LangGraph durable execution: checkpointing, resume, and deterministic/idempotent workflow considerations for side effects. https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph persistence: checkpointed state, conversational memory, and fault tolerance. https://docs.langchain.com/oss/python/langgraph/persistence
- LangChain/LangGraph human-in-the-loop: pause, approve, reject, or edit risky tool actions. https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- MongoDB time-series collections: time, metadata, metrics, measurements, and IoT use cases. https://www.mongodb.com/docs/manual/core/timeseries-collections/
- MongoDB IoT data modeling: bucketing/time-series approaches for sensor data and historical trends. https://www.mongodb.com/docs/v8.0/tutorial/model-iot-data/
- OpenTelemetry documentation: vendor-neutral traces, metrics, and logs for observability. https://opentelemetry.io/docs/
