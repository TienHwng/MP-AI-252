# Model Selection for HERA

This document summarizes the recommended model allocation for the HERA conversational intelligence pipeline, based on the current HERA codebase, planned web/SSE refactor, and OpenRouter model options.

## Selection Principle

HERA should not use a single model for all components. Different stages of the pipeline have different requirements:

- **Fast path:** should avoid LLM calls whenever possible.
- **Orchestrator / Router:** should prioritize low latency, stable JSON output, and cost efficiency.
- **DeviceControlAgent:** should prioritize structured output, tool/function calling reliability, and command parsing accuracy.
- **Diagnostic / Environment reasoning:** should prioritize reasoning quality over raw speed.
- **ResponseComposer / Streaming:** should prioritize fast, natural, user-facing response generation.
- **Memory summarization:** should prioritize extraction, summarization, and classification quality.
- **External context / Web research:** should use lightweight models for normal queries and stronger research models only when needed.

The most important optimization is that simple smart-home commands should not call an LLM at all.

Examples:

```text
bật đèn
tắt quạt
nhiệt độ bao nhiêu
trạng thái quạt
```

These should go through deterministic fast path first, then fallback to the LLM pipeline only when the request is ambiguous or complex.

---

## Recommended Models by Component

## 1. Orchestrator / Router

**Recommended model:**

```text
Google: Gemini 2.5 Flash Lite
```

### Why

The orchestrator/router needs to be fast, cheap, and reliable for short classification-style tasks. It does not need heavy reasoning for most requests.

Use it for:

```text
intent routing
memory scope decision
pending mode classification
fallback general response
```

### Suggested config

```json
{
  "orchestratorModel": "google/gemini-2.5-flash-lite"
}
```

---

## 2. DeviceControlAgent

**Recommended model:**

```text
Mistral: Mistral Small 3.2 24B
```

### Why

This is the most important agent in HERA because it converts natural language into structured device actions. It needs strong instruction following, reliable structured output, and good tool/function calling behavior.

Use it for:

```text
parse device command
resolve device target
handle multi-action command
handle conditional command
build scene/action plan
generate tool proposal
```

### Suggested config

```json
{
  "deviceModel": "mistralai/mistral-small-3.2-24b-instruct"
}
```

### Cheaper fallback

```text
Qwen: Qwen2.5 7B Instruct
```

Use this fallback when cost or latency is more important than maximum device-command reliability.

---

## 3. DiagnosticAgent / Environment Reasoning

**Recommended model:**

```text
Qwen: Qwen3 32B
```

### Why

Diagnostic reasoning is more complex than routing. It may need to combine current telemetry, telemetry history, device status, and recent actions to explain root causes or recommend actions.

Use it for:

```text
anomaly explanation
root-cause reasoning
environment insight
recommend action
multi-signal interpretation
```

### Suggested config

```json
{
  "diagnosticModel": "qwen/qwen3-32b"
}
```

### Lighter fallback

```text
Google: Gemini 2.5 Flash Lite
```

Use this if latency is more important than deep reasoning quality.

---

## 4. ResponseComposer / Web Streaming

**Recommended model:**

```text
Google: Gemini 2.5 Flash Lite
```

### Why

The response composer should generate short, natural, user-facing responses quickly. For SSE web streaming, fast first-token latency and low cost matter more than heavy reasoning.

Use it for:

```text
final user-facing response
Vietnamese natural response
SSE streaming
short explanation
fallback response
```

### Suggested config

```json
{
  "composerModel": "google/gemini-2.5-flash-lite"
}
```

### Note

For deterministic fast-path results, do not call the composer LLM. Stream only:

```text
status → final
```

Example:

```text
Đã bật đèn.
```

---

## 5. Memory Summarizer / Profile Extraction

**Recommended model:**

```text
IBM: Granite 4.1 8B
```

### Why

Memory tasks are mostly summarization, classification, and extraction. They do not require the strongest model, but they do need stable structured extraction.

Use it for:

```text
summarize conversation
extract user preference
classify memory-worthy information
compress history
```

### Suggested config

```json
{
  "memoryModel": "ibm-granite/granite-4.1-8b"
}
```

---

## 6. ExternalContext / Web Research

There should be two levels.

### Normal web/weather/news queries

**Recommended model:**

```text
Google: Gemini 2.5 Flash Lite
```

Use it to summarize normal external information quickly.

### Deep research mode

**Recommended model:**

```text
Tongyi DeepResearch 30B A3B
```

Use this only for complex multi-step external research. Do not use it for every web query because it is overkill for normal smart-home interaction.

### Suggested config

```json
{
  "externalContextModel": "google/gemini-2.5-flash-lite",
  "deepResearchModel": "alibaba/tongyi-deepresearch-30b-a3b"
}
```

---

# Best Balanced Configuration

```json
{
  "orchestratorModel": "google/gemini-2.5-flash-lite",
  "deviceModel": "mistralai/mistral-small-3.2-24b-instruct",
  "diagnosticModel": "qwen/qwen3-32b",
  "composerModel": "google/gemini-2.5-flash-lite",
  "memoryModel": "ibm-granite/granite-4.1-8b",
  "externalContextModel": "google/gemini-2.5-flash-lite",
  "deepResearchModel": "alibaba/tongyi-deepresearch-30b-a3b"
}
```

---

# Cheaper Configuration

```json
{
  "orchestratorModel": "google/gemini-2.5-flash-lite",
  "deviceModel": "qwen/qwen2.5-7b-instruct",
  "diagnosticModel": "google/gemini-2.5-flash-lite",
  "composerModel": "google/gemini-2.5-flash-lite",
  "memoryModel": "ibm-granite/granite-4.1-8b"
}
```

---

# Tool-Calling-Oriented Configuration

```json
{
  "orchestratorModel": "google/gemini-2.5-flash-lite",
  "deviceModel": "mistralai/mistral-small-3.2-24b-instruct",
  "diagnosticModel": "mistralai/mistral-small-3.2-24b-instruct",
  "composerModel": "google/gemini-2.5-flash-lite"
}
```

This configuration prioritizes structured output and tool/function calling consistency, especially for device control and automation-related tasks.

---

# Free OpenRouter-Oriented Configuration

Based on the latest available model list, these free models are worth testing:

```text
Google Gemma 4 26B A4B free
Google Gemma 4 31B free
DeepSeek V4 Flash free
NVIDIA Nemotron 3 Nano A3B free
```

Suggested free setup:

```json
{
  "orchestratorModel": "google/gemma-4-26b-a4b:free",
  "deviceModel": "google/gemma-4-26b-a4b:free",
  "diagnosticModel": "deepseek/deepseek-v4-flash:free",
  "composerModel": "google/gemma-4-26b-a4b:free"
}
```

## Warning

Free models are useful for development and testing, but they may be less stable in availability, throughput, or latency. For thesis demo or important evaluation, keep a paid fallback.

---

# Final Recommendation

For the main HERA setup, use:

```text
Orchestrator:
Google Gemini 2.5 Flash Lite

DeviceControlAgent:
Mistral Small 3.2 24B

DiagnosticAgent:
Qwen3 32B

ResponseComposer / SSE streaming:
Google Gemini 2.5 Flash Lite

Memory:
IBM Granite 4.1 8B

Deep web research:
Tongyi DeepResearch 30B A3B
```

Most importantly:

```text
FastPathRouter should use no LLM.
```

Simple requests such as device on/off, current temperature, current humidity, and device status should be handled deterministically before falling back to any LLM.
