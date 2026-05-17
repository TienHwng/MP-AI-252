# Orchestrator Diagram - Issues & Fixes

## Current Issues

### 1. Missing Critical Steps
- **Missing:** `Ground Tool Plan` node (chuẩn bị constraints + tool specifications)
- **Missing:** `Execute Tools` node (thực thi tool proposals)
- **Missing:** `Evaluate Tool Results` node (kiểm tra kết quả thực thi)

### 2. Incorrect Flow After Routing
**Current (Ảnh):**
```
Route → General Request? → Memory Scope → Confirmation → Specialist
```

**Actual (Code):**
```
Route → Check Pending Mode? 
├─ YES (pending): Handle Pending Confirmation → Check Response? → Execute Tools
└─ NO: Retrieve Memory → Check Intent? 
   ├─ "general": Finalize (skip full pipeline)
   └─ "specialist": Check Requires Execution?
      ├─ YES: Ground Tool Plan → Execute Tools → Evaluate Results
      └─ NO: Compose Response (no execution needed)
```

### 3. Merged Nodes That Should Be Separate
- **Issue:** "Memory Scope Decision" và "Confirmation State Handler" cần phân tách logic
  - Memory scope decision: chọn orchestrator.graph_retrieve_memory
  - Confirmation handling: chọn orchestrator.graph_handle_pending_confirmation (khác intent classifier)

### 4. Wrong Specialist → Response Composer Path
**Current (Ảnh):**
```
Specialist → Tool Execution? → Compose Response
```

**Actual (Code):**
```
Specialist → Check Requires Execution?
├─ YES: Ground Tool Plan → Execute Tools → Evaluate Tool Results → Compose Response
└─ NO: Compose Response (direct)
```

## Correct LangGraph Structure (from orchestration/graph.py)

### Nodes (11 total)
1. `intake` - Request State Intake
2. `route` - Intent Router (classify + check pending_mode)
3. `handle_pending_confirmation` - Confirmation State Handler
4. `retrieve_memory` - Memory Context Retrieval
5. `general` - General Response Handler (direct LLM reply)
6. `specialist` - Specialist Agent Dispatcher
7. `ground_tool_plan` - Tool Plan Grounding (NEW - add to diagram!)
8. `execute_tools` - Tool Execution Runner (NEW - add to diagram!)
9. `evaluate_tool_results` - Tool Result Evaluation (NEW - add to diagram!)
10. `compose_response` - Response Composition
11. `finalize` - State Finalization

### Edges (Conditional Routing)
```
intake → route
↓
route (conditional):
├─ pending_mode == "confirmation" → handle_pending_confirmation
└─ else → retrieve_memory

handle_pending_confirmation (conditional):
├─ response exists → finalize
└─ no response → execute_tools → evaluate_tool_results → compose_response → finalize

retrieve_memory (conditional):
├─ intent == "general" → general → finalize
└─ else → specialist

specialist (conditional):
├─ requires_execution == true → ground_tool_plan
└─ else → compose_response
↓
ground_tool_plan → execute_tools → evaluate_tool_results → compose_response → finalize
```

## What to Show in Updated Diagram

### Recommended Layout
```
Box 1: Request Entry
├─ 1. Request State Intake
└─ 2. Intent Router

Box 2: Early Routes (Pending Confirmation)
├─ 3. Confirmation State Handler
├─ 5. General Response Handler
└─ 8. Handle Pending Confirmation Path

Box 3: Memory Gate
├─ 4. Retrieve Memory

Box 4: Specialist Path (Core)
├─ 6. Specialist Dispatcher
├─ 7. Ground Tool Plan ← ADD THIS
├─ 8. Execute Tools ← ADD THIS
├─ 9. Evaluate Tool Results ← ADD THIS
└─ 10. Response Composer

Box 5: Output
├─ 11. State Finalizer
```

### Diamond Decisions (Need Clear Labels)
1. **"Pending Confirmation?"** (after Route) 
   - YES → handle_pending_confirmation
   - NO → retrieve_memory

2. **"Response Already Set?"** (after Confirmation)
   - YES → finalize
   - NO → execute_tools

3. **"Intent Type?"** (after Retrieve Memory)
   - "general" → general LLM
   - else → specialist

4. **"Requires Tool Execution?"** (after Specialist)
   - YES → ground_tool_plan
   - NO → compose_response

### Key Color/Style Notes
- **Read-only ops** (retrieve_memory, general): Blue
- **Write/execution ops** (execute_tools, ground_tool_plan): Red/Orange
- **Composition/synthesis** (compose_response, finalize): Green
- **Gating decisions**: Diamond with condition labels

## Summary of Changes
| Element | Current | Need |
|---------|---------|------|
| Nodes | 8 | 11 (+3) |
| Specialist path clarity | Ambiguous | Clear tool execution chain |
| Pending confirmation path | Missing | Show full branch |
| Memory gate logic | Oversimplified | Show intent-based routing |
| Tool execution | Collapsed | Expand to 3 nodes |
| Decision points | 4 | 4 (but different labels) |

## Prompt for AI Image Editor

```
Title: Internal Structure of the H.E.R.A Orchestrator - Decision Flow

Description:
This diagram shows the ABSTRACT DECISION LOGIC flow inside the H.E.R.A Orchestrator (NOT LangGraph node names).

Update the existing diagram with these changes:

STEP 1: RESTRUCTURE THE FLOW
Current order: 1→2→3→4→5→6→7→8
New order should be:
  1. Request State Intake
  2. Intent Router (classify + check pending confirmation mode)
  3. [DECISION] Pending Confirmation? 
     ├─ YES → Handle Confirmation State
     └─ NO → Continue to step 4
  4. Memory Context Selector (select scope based on classification)
  5. [DECISION] Intent Type?
     ├─ GENERAL → Direct LLM Response (skip to Finalization)
     └─ SPECIALIST → Route to Agent
  6. Specialist Agent Dispatcher (select appropriate specialist)
  7. [DECISION] Requires Tool Execution?
     ├─ YES → Tool Planning & Execution (subprocess - see below)
     └─ NO → Skip to Response Composition
  8. Response Composer (synthesize final answer)
  9. State Finalizer (persist state)

STEP 2: ADD TOOL EXECUTION SUBPROCESS
Create a NESTED BOX or SUBPROCESS CONTAINER for steps 7-9 labeled "Tool Planning & Execution Pipeline":
  7a. Ground Tool Plan (prepare constraints + specifications)
  7b. Execute Tools (run tool proposals through MQTT)
  7c. Evaluate Tool Results (verify state changes + collect feedback)
  [Then exit to Response Composer]

This subprocess is OPTIONAL - only runs if "Requires Tool Execution?" = YES.

STEP 3: CLARIFY DECISION DIAMONDS
Each decision should have:
  - Clear condition label inside diamond
  - YES/NO or option labels on edges
  - Arrow directions clear

Decision Points:
  D1: "Pending Confirmation?" → YES [Handle Confirmation] / NO [Continue]
  D2: "Intent Type?" → "GENERAL" [Direct LLM] / "SPECIALIST" [Agent]
  D3: "Requires Tool Execution?" → YES [Tool Pipeline] / NO [Compose Response]

STEP 4: VISUAL HIERARCHY
- Main flow boxes: Light blue
- Decision diamonds: Orange
- Tool execution subprocess: Red/accent color (highlight complexity)
- Composition & finalization: Green

STEP 5: LABELS
Replace generic labels with:
  OLD "Request State Intake" → Keep (but add: "Normalize input + session context")
  OLD "Intent Router" → Keep (but add: "Classify intent + check pending_mode")
  OLD "Memory Scope Decision" → Change to "Memory Context Selector"
  OLD "Confirmation State Handler" → Make this separate (only if pending_mode='confirmation')
  OLD "Specialist Dispatcher" → Keep (add: "Route to device_control, sensor_analysis, etc.")
  OLD "Tool Requirement Decision" → Change to "Requires Tool Execution?"
  NEW "Ground Tool Plan" → Add (prepare tool constraints)
  NEW "Execute Tools" → Add (run MQTT commands)
  NEW "Evaluate Tool Results" → Add (verify state changes)
  OLD "Response Composer" → Keep (add: "Synthesize final user-facing answer")
  OLD "State Finalizer" → Keep (add: "Persist state + chat history")

STEP 6: LAYOUT RECOMMENDATION
┌─────────────────────────────────────────────┐
│ Request Intake                              │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│ Intent Router                               │
│ ├─ Classify intent                          │
│ └─ Check pending_mode                       │
└──────────────┬──────────────────────────────┘
               ↓
          ◇ Pending Confirmation?
         ╱   ╲
       YES   NO
      ╱       ╲
   [Handle]   [Memory Selector]
      │            │
      └─────┬──────┘
            ↓
      ◇ Intent Type?
     ╱   ╲
  GEN   SPEC
  ╱       ╲
[LLM]  [Specialist Dispatcher]
  │        │
  │        ↓
  │   ◇ Requires Execution?
  │  ╱   ╲
  │ YES  NO
  │ ╱     ╲
  │┌──────────────────────────┐
  ││ Tool Pipeline:           │
  ││ • Ground Plan            │
  ││ • Execute                │
  ││ • Evaluate Results       │
  │└────────┬─────────────────┘
  │         │
  └────┬────┘
       ↓
  [Response Composer]
       ↓
  [State Finalizer]

KEY NOTES:
- Tool execution is a subprocess (optional, only if needed)
- Two main entry branches: Pending Confirmation vs Normal Flow
- Memory scope decision affects which specialist gets called
- General requests bypass specialist entirely
- Response Composer receives input from ANY path (direct LLM or specialist + tools)

COLORS & STYLING:
- Main flow: Blue boxes with dark outline
- Decision points: Orange diamonds with rounded corners
- Tool subprocess: Red/salmon background box with nested flow
- Output steps: Green boxes
- Arrows: Black with direction labels (YES/NO/INTENT)
```

This prompt preserves the business logic level while being implementation-independent.
