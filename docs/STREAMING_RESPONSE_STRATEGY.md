# Streaming Response Strategy for Dashboard Chat

## Overview

This document describes the streaming strategy for delivering assistant responses to the HERA Dashboard. Instead of showing full responses as one large block, the system streams character-by-character, creating a natural conversational flow that improves user experience.

**Goal**: Transform "bulk response display" → "smooth character-by-character streaming"

---

## 1. Streaming Architecture

### 1.1 High-Level Data Flow

```
┌─────────────┐
│   User      │
│  Message    │
└────────┬────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    React Dashboard                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  AI.jsx Component                                    │  │
│  │  • Collects user input                               │  │
│  │  • Tracks streaming state (messageId, isStreaming)  │  │
│  │  • Provides pause/resume buttons                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐  │
│  │  api.js - sendAssistantMessageStreaming()          │  │
│  │  • Initiates fetch with ?stream=true                │  │
│  │  • Reads SSE stream from response body              │  │
│  │  • Parses JSON chunks from "data:" lines           │  │
│  │  • Forces immediate React render per chunk         │  │
│  │  • Handles network errors gracefully                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │
         │ HTTP POST with ?stream=true
         │
┌────────▼────────────────────────────────────────────────────┐
│              Python Backend (aiohttp)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  api_server.py - handle_assistant_message()         │  │
│  │  • Detects stream=true parameter                     │  │
│  │  • Routes to orchestrator                            │  │
│  │  • Gets full response (text + thinking)              │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐  │
│  │  _stream_assistant_response() - SSE Handler        │  │
│  │  • Prepares StreamResponse with CORS headers        │  │
│  │  • Chunks thinking block (3 chars, 3ms delay)      │  │
│  │  • Chunks content block (1 char, 20ms delay)       │  │
│  │  • Sends [DONE] marker on completion               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Three-Layer Optimization

| Layer | Issue | Solution |
|-------|-------|----------|
| **Network/Backend** | Chunks sent at wrong timing, missing CORS | 1-char/20ms, SSE format with CORS headers |
| **Frontend/React** | Batch renders hide streaming effect | ReactDOM.flushSync() forces render per chunk |
| **State Mgmt** | O(n) message updates per chunk | O(1) lookup + direct array index update |

---

## 2. Enabling Streaming

### 2.1 Frontend: Sending Streaming Request

**Location**: `FE/hera-dashboard/src/services/api.js`

The frontend must add `?stream=true` parameter:

```javascript
// Request with streaming parameter
fetch(`${HERA_API_BASE_URL}/api/assistant/message?stream=true`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: userMessage,
    user_id: userId,
    session_id: sessionId,
  }),
  signal: abortSignal, // For pause support
})
```

**Key requirements**:
- Include `?stream=true` query parameter
- Provide AbortSignal for pause functionality
- Handle both SSE and JSON response types (fallback)

### 2.2 Backend: Detecting Streaming Parameter

**Location**: `BE/HERA/api_server.py` - `handle_assistant_message()`

```python
# Check if streaming is requested
stream = request.query.get("stream", "false").lower() == "true"

# Get response from orchestrator
response = await request.app["orchestrator"].handle(message)

# Branch: streaming vs. standard response
if stream:
    return await _stream_assistant_response(request, response)
else:
    return web.json_response({...})
```

### 2.3 Required CORS Headers

The backend must send proper CORS headers for browser streaming:

```python
headers = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}
```

**Why critical**: Browser preflight OPTIONS requests will fail if headers missing, causing fallback to non-streaming.

---

## 3. Backend-Frontend Message Flow

### 3.1 Complete Request-Response Cycle

```
Timeline: User sends "Hello HERA"
═════════════════════════════════════════════════════════════

T=0s    Frontend: User types "Hello HERA", clicks Send
        → Generates messageId: "2025-05-16T10:30:00.000Z-0.123"
        → Creates AbortController for this request
        → Sends POST /api/assistant/message?stream=true

T=0.5s  Backend: Receives request
        → Calls orchestrator.handle(message)
        → Orchestrator generates response via LLM
        → Returns response object with .text and .metadata.thinking

T=0.6s  Backend: Sends SSE response
        → Streaming response.metadata.thinking (if exists)
        → Sending: data: {"choices":[{"delta":{"thinking":"..."}}]}\n\n
        → Each thinking chunk: 3 chars, 3ms delay

T=1.5s  Backend: Switches to content streaming
        → Sending: data: {"choices":[{"delta":{"content":"H"}}]}\n\n
        → Each content chunk: 1 char, 20ms delay
        → Rate: ~50 chars/sec = readable speed

T=1.6s to T=N   Frontend: Receives chunks
        → Parses each SSE line
        → Extracts content from JSON
        → Calls: ReactDOM.flushSync(() => onChunk(content, fullText))
        → Message updates in state: O(1) operation
        → UI re-renders with 1 new character
        → User sees character appear on screen

T=N+1s  Backend: Sends completion
        → data: [DONE]\n\n

T=N+1.1s Frontend: Detects completion
        → Updates message: isStreaming = false
        → Saves response to database
        → Re-enables input, hides pause button
```

### 3.2 SSE Message Format

All streaming chunks follow this format:

```
data: {JSON_OBJECT}\n\n
```

**Thinking chunks**:
```json
{
  "choices": [
    {
      "delta": {"thinking": "Let"},
      "index": 0
    }
  ]
}
```

**Content chunks**:
```json
{
  "choices": [
    {
      "delta": {"content": "H"},
      "index": 0
    }
  ]
}
```

**Completion**:
```
data: [DONE]\n\n
```

---

## 4. Performance Tuning

### 4.1 Chunk Size & Delay Parameters

Current optimal settings:

| Parameter | Value | Reasoning |
|-----------|-------|-----------|
| Content chunk size | 1 character | Minimum visible granularity |
| Content delay | 20ms | ~50 chars/sec = comfortable reading speed |
| Thinking chunk size | 3 characters | Balance between smoothness and overhead |
| Thinking delay | 3ms | Consistent with ~333 chunks/sec thinking pace |

**Why 1-char chunks?**
- Perceivable by human eye (~300ms reaction time)
- Too small: flickers appear; too large: buffering visible
- 1-char is sweet spot for streaming illusion

**Why 20ms delay?**
- 50 chars/sec ≈ 300 words/minute = natural reading pace
- Slower (30ms) = feels sluggish
- Faster (10ms) = overwhelming, hard to follow

### 4.2 Adaptive Adjustments

**Future improvements** (not implemented):
- Detect client's network latency → adjust delay
- Monitor CPU → reduce chunk size if janky
- Respect user preference setting for speed

---

## 5. Fallback & Error Handling

### 5.1 Streaming Not Supported?

If browser doesn't support SSE or streaming fails:

```javascript
// Frontend detects failure
catch (error) {
  console.warn('Streaming failed, falling back to non-streaming');
  // Retry with stream=false
  const fallbackResponse = await fetch('...?stream=false');
  // Displays full response as single block
}
```

### 5.2 Network Errors During Streaming

**Scenario**: Connection drops mid-stream

```javascript
// Frontend handles errors
if (error.name === 'AbortError') {
  // User clicked pause - expected
  saveMessageState({ paused: true });
} else {
  // Network error - unexpected
  saveMessageState({ streamError: error.message });
  // Show retry button to user
}
```

**Backend ensures**: Partial responses are saved; user can retry.

---

## 6. Pause & Resume Feature

### 6.1 User Initiates Pause

```
User clicks "⏸ Pause" button
    ↓
abortControllerRef.current.abort()
    ↓
Browser closes fetch connection
    ↓
Backend detects closed connection
    ↓
Message saved with isStreaming=false, paused=true
```

### 6.2 Resume Streaming

```
User clicks "▶ Resume" button
    ↓
Frontend sends POST /api/assistant/message/resume/{messageId}
    ↓
Backend retrieves message ID
    ↓
Continues from last chunk position (if applicable)
    ↓
Streams remaining content
```

**Note**: Requires stateful backend to track pause position (future enhancement).

---

## 7. Development Checklist

### 7.1 Setup Streaming

- [ ] Backend: `api_server.py` has `_stream_assistant_response()` function
- [ ] Backend: CORS headers set on StreamResponse
- [ ] Frontend: `api.js` has `sendAssistantMessageStreaming()` function
- [ ] Frontend: AI.jsx component tracks streaming state

### 7.2 Testing Streaming

- [ ] Send message, watch browser DevTools Network tab
  - Should see multiple `data:` events, not one response
- [ ] Open DevTools Console, send message
  - Should see: `✓ Streaming complete: NNN chunks (NNNN chars)`
- [ ] Visual test: Characters should appear one-by-one
  - Not: All text appears at once
- [ ] Pause mid-stream, verify connection closes
- [ ] Click pause, send new message, verify old message saved

### 7.3 Performance Validation

- [ ] No memory leaks during long streaming sessions
- [ ] CPU usage < 20% while streaming
- [ ] No "jank" or frame drops visible
- [ ] Works on slow connections (DevTools → throttle)

---

## 8. Streaming vs. Non-Streaming Comparison

### 8.1 UX Comparison

| Aspect | Non-Streaming | Streaming |
|--------|---------------|-----------|
| **Display** | Full response appears after 2-3s | Characters appear gradually |
| **Perceived speed** | Feels slow (waiting for completion) | Feels fast (seeing progress) |
| **Pause option** | N/A | Available during response |
| **Network bandwidth** | Single bulk response | Many small chunks |
| **Browser latency** | Entire response buffered | Immediate first-char feedback |

### 8.2 Cost-Benefit

**Benefits of streaming**:
- Better UX: Users see progress immediately
- Can pause long responses
- Feels more conversational

**Costs**:
- Slightly more network traffic (SSE overhead)
- Backend requires chunking logic
- Requires browser SSE support

**Decision**: Streaming recommended for chat, optional for other interfaces.

---

## 9. Diagram: Response Flow States

```
User sends message
        │
        ▼
    ┌──────────────────────┐
    │  Request submitted   │
    │  isStreaming = true  │
    │  Show pause button   │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────────────┐
    │  Streaming in progress       │
    │  chunks arriving via SSE     │
    │  UI updates per chunk        │
    │  User can pause anytime      │
    └──────────┬───────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
   [DONE]       [Error/Abort]
   received          │
        │            ▼
        ▼      ┌───────────────────┐
    ┌──────────┤  Error handling   │
    │  Stream  │  Save partial msg │
    │ complete │  Show retry btn   │
    │          └───────────────────┘
    ▼
┌────────────────────┐
│ Response complete  │
│ isStreaming=false  │
│ Hide pause button  │
│ Enable input       │
│ Save to DB         │
└────────────────────┘
```

---

## 10. Configuration

No hardcoded streaming configuration currently. To customize:

**Backend** (`BE/HERA/api_server.py`):
```python
# Adjust delays in _stream_assistant_response()
await asyncio.sleep(0.02)  # Content delay (20ms)
await asyncio.sleep(0.003)  # Thinking delay (3ms)
```

**Frontend** (`FE/hera-dashboard/src/services/api.js`):
```javascript
// Adjust in sendAssistantMessageStreaming()
// (No delay configuration; uses backend timing)
```

---

## 11. Summary

**Streaming Strategy**:
1. **Request**: Frontend adds `?stream=true` query parameter
2. **Backend**: Chunks response into 1-char segments with 20ms delays
3. **Transport**: Uses SSE (Server-Sent Events) format
4. **Frontend**: Parses chunks, forces React render with flushSync
5. **State**: O(1) message updates (direct index access)
6. **Completion**: [DONE] marker signals end
7. **Fallback**: Non-streaming mode if SSE fails
8. **Pause**: AbortController stops fetch on demand

**Result**: HERA Assistant chat displays responses naturally, character-by-character, with full pause/resume control. ✨

---

## References

- CORS headers: `api_server.py` lines 47-54
- Backend streaming: `api_server.py` lines 368-400
- Frontend SSE parsing: `api.js` lines 896-1000
- State management: `AI.jsx` lines 75-150
- Streaming report: `STREAMING_OPTIMIZATION_REPORT.md`
