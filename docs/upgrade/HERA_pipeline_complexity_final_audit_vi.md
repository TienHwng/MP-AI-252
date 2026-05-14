# HERA Pipeline Complexity Final Audit và Refactor Plan

## 1. Kết luận đã kiểm chứng

Sau khi đối chiếu trực tiếp với code hiện tại, kết luận chính là:

> HERA đang overcomplex, nhưng cần mô tả chính xác: vấn đề lớn nhất không phải mọi intent đều chạy đủ mọi node, mà là HERA đang dùng một orchestration graph chung cho cả request đơn giản lẫn device-control, đồng thời device routing/parsing có nhiều tầng rule-based fast path chồng lên LLM parser.

Nói ngắn gọn:

- Graph hiện tại có conditional edges, nên không phải request nào cũng chạy qua tất cả node.
- General request vẫn đi qua `intake -> route -> retrieve_memory(skip) -> general -> finalize`.
- Sensor/anomaly/web không đi qua `ground_tool_plan -> execute_tools -> evaluate_tool_results` nếu `requires_execution=False`.
- Device-control path mới đi qua full controlled runtime.
- Overcomplex thật sự nằm ở:
  - graph chung cho cả request đơn giản;
  - device fast route trước LLM router;
  - device fast parser trước LLM device parser;
  - prompt có phrase-specific examples;
  - test harness/FakeLLM vẫn phản ánh testcase-specific behavior.

## 2. Pipeline thực tế hiện tại

File chính:

- `BE/HERA/orchestration/graph.py`
- `BE/HERA/agents/orchestrator.py`

Graph khai báo các node:

```text
intake
route
handle_pending_confirmation
retrieve_memory
general
specialist
ground_tool_plan
execute_tools
evaluate_tool_results
compose_response
finalize
```

Luồng chính trong `graph.py`:

```text
intake -> route

route -> handle_pending_confirmation
      -> retrieve_memory

retrieve_memory -> general
                -> specialist

general -> finalize

specialist -> ground_tool_plan -> execute_tools -> evaluate_tool_results -> compose_response
           -> compose_response

compose_response -> finalize
finalize -> END
```

Điểm cần sửa từ các audit trước: `_route_after_specialist` quyết định:

```python
return "execute_tools" if route_decision.requires_execution else "compose_response"
```

Vì vậy read-only intents như `sensor_query`, `anomaly_query`, và thường cả `web_search` không chạy qua execution path.

## 3. Flow theo loại request

### 3.1 General request

Ví dụ:

```text
xin chào
bạn là ai
```

Flow:

```text
intake
-> route
-> retrieve_memory
-> general
-> finalize
```

`retrieve_memory` vẫn chạy nhưng nếu `memory_scope=none` thì chỉ tạo `MemoryContext(reason="memory_scope_none")`.

Đánh giá:

- 5 bước cho greeting/identity là hơi nặng.
- `can_use_route_direct_response()` không tránh router; nó chỉ được dùng trong `graph_general` sau khi router đã có `direct_response`.
- Request kiểu này nên có short path trước graph hoặc mini path riêng.

### 3.2 Sensor/anomaly read-only

Ví dụ:

```text
nhiệt độ hiện tại bao nhiêu
có gì bất thường không
```

Flow thực tế:

```text
intake
-> route
-> retrieve_memory
-> specialist
-> compose_response
-> finalize
```

Không chạy qua:

```text
ground_tool_plan
execute_tools
evaluate_tool_results
```

Đánh giá:

- Audit cũ nói sensor đi qua 9 node là không đúng với code hiện tại.
- Tuy vậy, sensor/anomaly vẫn bị đưa qua graph chung. Với read-only query đơn giản, có thể đi short path: classify/read/compose/finalize.

### 3.3 Device-control

Ví dụ:

```text
bật relay
bật đèn
nếu nhiệt độ trên 30 thì bật quạt
tắt thiết bị vừa bật
```

Flow:

```text
intake
-> route
-> retrieve_memory
-> specialist
-> ground_tool_plan
-> execute_tools
-> evaluate_tool_results
-> compose_response
-> finalize
```

Đánh giá:

- Full path này hợp lý hơn vì có side effect vật lý.
- Nên giữ policy, condition evaluation, MQTT execution, verification, action memory.
- Nhưng phần semantic route/parse trước đó đang quá rule-based.

## 4. Root cause đã kiểm chứng

### 4.1 Graph chung cho mọi request

Một graph chung làm code dễ thống nhất state, nhưng nó khiến request đơn giản bị gánh cùng abstraction với request điều khiển thiết bị.

Với HERA, nên phân biệt:

```text
simple/general/read-only -> short path
device write/conditional/pending -> controlled runtime path
```

### 4.2 Device routing có fast path trước LLM router

Trong `BE/HERA/agents/orchestrator.py`, `classify_route()` kiểm tra các hàm từ `device_agent.py` trước khi gọi LLM router:

- `looks_like_standalone_device_request`
- `looks_like_conditional_device_request`
- `looks_like_contextual_device_request`

Các hàm này dựa vào fast parser/token logic trong `device_agent.py`.

Vấn đề:

- Router không còn là single source of truth.
- Một phần semantic understanding bị đẩy vào Python regex/token logic.
- Khi fast path match sai, LLM router không có cơ hội sửa.
- Khi fast path không match, behavior lại phụ thuộc LLM router.

Đây là dual-router pattern cho device-related requests.

### 4.3 Device parsing có fast parser trước LLM parser

Trong `DeviceControlAgent.parse_command()`:

```text
fast_parse_value_command
fast_parse_local_command
fast_parse_contextual_command
if all fail:
    call LLM with DEVICE_COMMAND_INTERPRETER_PROMPT
```

Các fast parser sử dụng nhiều marker/token set:

- `ACTION_STOPWORDS`
- `FILLER_TOKENS`
- `GENERIC_LIGHT_TOKEN_SETS`
- `ALL_LIGHTS_TOKEN_SETS`
- `ALL_DEVICES_TOKEN_SETS`
- `STATUS_MARKERS`
- `STATUS_FOLLOWUP_MARKERS`
- `CONDITIONAL_MARKERS`
- `SPECIFIC_TARGET_TOKEN_SETS`
- `SENSOR_CONDITION_ALIASES`
- `VALUE_SET_MARKERS`
- `SENSOR_WRITE_ALIASES`

Đánh giá:

- Đây gần như là một hand-written NLU parser.
- Một số logic là hardware validation hợp lý, nhưng phần lớn token/phrase matching đang duplicate nhiệm vụ semantic parser của LLM.
- Dấu hiệu overfit rõ: typo-specific handling như `ắt`/`at`, phrase follow-up như `chắc chưa`, recent-reference markers, Vietnamese filler matching.

### 4.4 Prompt chứa phrase-specific examples

Trong `BE/HERA/prompts/orchestrator.py`:

- `"the device I just mentioned"`
- `"vậy còn..."`
- `"vậy có gì cần lưu ý không"`

Trong `BE/HERA/prompts/device.py`:

- `"bật đi"`
- `"tắt đi"`
- `"chắc chưa"`

Đánh giá:

- Đây là smell của testcase-driven prompt patching.
- Prompt nên mô tả semantic rule, không nhúng từng phrase user từng gặp.
- Device ontology/action schema nên giữ, vì đó là grounding; phrase-specific examples nên giảm.

### 4.5 Test harness hiện tại đã bớt khóa call count, nhưng vẫn còn testcase smell

Trạng thái code hiện tại:

- Không còn thấy assert `route_call_count == 0`, `device_call_count == 0`, `memory.retrieve_count == 0` trong `tests_device_behavior.py`.
- Tuy nhiên tên test như `test_temporal_conditional_device_request_bypasses_bad_router` vẫn còn.
- `FakeLLM._route()` và `FakeLLM._parse_command()` vẫn là substring lookup table cho các phrase cụ thể như:
  - `"5 phút"`, `"20"`, `"quạt"`
  - `"10 giây"`, `"35"`, `"quạt"`
  - `"trên 40"`, `"quạt"`
  - `"các thiết bị khác"`
  - `"tất cả đèn"`
  - `"vừa được bật"`
- Có comment trong test hiện tại:

```text
pre-existing issue — fast-parser path doesn't trigger noop detection...
Tracked for Phase 3 (remove fast parser).
```

Đây là bằng chứng rất tốt cho root cause: fast parser không chỉ làm code phức tạp, mà còn gây behavior lệch với runtime/noop expectation.

## 5. Những claim từ 2 report cũ cần chỉnh

### 5.1 Claim đúng

- HERA overcomplex: đúng.
- Device path có dual parser/router: đúng.
- `device_agent.py` có nhiều rule/token hardcode: đúng.
- Prompt có phrase-specific examples: đúng.
- Cần giữ safety/runtime components: đúng.
- Cần chuyển tests sang behavior contract: đúng; code hiện tại đã bắt đầu làm.

### 5.2 Claim sai hoặc nói quá

1. "Mọi intent đều chạy qua rule-based fast path trước LLM router"  
   Không chính xác. Fast path trước router chủ yếu là device-related. General/sensor/anomaly/web vẫn phụ thuộc router LLM hoặc router prompt output.

2. "Sensor query đi qua 9 node, trong đó execute/evaluate skip"  
   Không đúng với `graph.py`. `requires_execution=False` đưa sensor/anomaly/web từ `specialist` thẳng sang `compose_response`.

3. "Mọi request đi qua đủ 11 node"  
   Không đúng. Graph có 11 node khai báo, nhưng conditional edges chỉ chạy một subset.

4. "`can_use_route_direct_response` giúp greeting tránh router LLM"  
   Không đúng. Nó chạy trong `graph_general`, sau `route`.

5. "22/25 tests assert implementation detail"  
   Không còn đúng với code hiện tại. Các call-count assert đã được gỡ hoặc không còn xuất hiện. Test harness vẫn còn phrase-specific FakeLLM và tên test cũ.

## 6. Nên giữ

Các phần sau là complexity có giá trị:

- `ToolRunner`
- `PolicyEngine`
- `VerificationService`
- capability registry/tool contracts
- typed schemas
- action memory/focus cho device follow-up
- pending confirmation cho command scope rộng
- pending clarification cho target ambiguous
- condition evaluator cho sensor threshold/window
- hardware specs/canonical targets:
  - `DEVICE_TARGETS`
  - `DEVICE_VALUE_SPECS`
  - `SENSOR_VALUE_SPECS`

Lý do: đây là runtime correctness và safety, không phải overengineering.

## 7. Nên giảm

### 7.1 Full graph cho trivial/general request

Không nên để greeting/identity/chitchat phải đi qua graph chung.

Đề xuất:

```text
handle()
  -> try_short_path()
  -> if not handled: graph.run()
```

Short path ban đầu:

- trivial greeting;
- identity;
- simple general direct response;
- simple sensor snapshot;
- simple anomaly status.

### 7.2 Device fast parser quá sâu

Nên giảm `fast_parse_local_command`, `fast_parse_contextual_command`, và các token sets lớn.

Chỉ giữ fast path cho case cực rõ:

```text
explicit action + explicit target/value
```

Ví dụ:

- `bật relay`
- `turn off relay`
- `set ws2812 brightness to 128`

Những case nên để LLM structured parser:

- ambiguous target: `bật đèn`
- follow-up: `bật đi`, `chắc chưa`
- recent reference: `tắt thiết bị vừa bật`
- conditional: `nếu nhiệt độ trên 30 thì bật quạt`
- multi-action: `bật quạt và bật đèn`
- typo/noisy Vietnamese sentence

### 7.3 Phrase-specific prompt examples

Thay:

```text
Use it to understand follow-up references like "the device I just mentioned" or "vậy còn..."
```

Bằng:

```text
Resolve elliptical follow-up references using recent conversation, active device focus, and recent action memory. If the reference is ambiguous, ask for clarification instead of guessing.
```

### 7.4 FakeLLM phrase lookup

Nên chuyển FakeLLM từ exact substring table sang test double theo contract:

- nhận payload;
- trả structured intent/command dựa trên scenario setup;
- không cần copy từng phrase user thật.

Hoặc tách test:

- unit test deterministic validator/tool runner;
- integration test với fake parser result;
- small E2E golden tests cho vài utterance thật.

## 8. Refactor plan đã hiệu chỉnh

### Phase 1: Chốt baseline và sửa test names

Tasks:

1. Đổi tên `test_temporal_conditional_device_request_bypasses_bad_router` thành `test_temporal_conditional_device_request_routes_to_device_runtime`.
2. Giữ hướng hiện tại: không assert call count.
3. Giảm phrase lookup trong `FakeLLM`.
4. Thêm tests theo output contract:
   - final intent;
   - parsed command;
   - MQTT publish/no publish;
   - verification/noop behavior;
   - pending clarification state;
   - response text tối thiểu.

### Phase 2: Thêm short path trước graph

Trong `Orchestrator.handle()`:

```python
async def handle(self, message: UserMessage) -> AgentResponse:
    short_response = await self.try_short_path(message)
    if short_response is not None:
        return short_response
    state = await self.graph.run(message)
    return state["response"]
```

Short path không cần hoàn hảo ngay. Bắt đầu với:

- greetings;
- identity;
- simple sensor read;
- simple anomaly read.

Không đưa device write vào short path ở phase này.

### Phase 3: Clean prompt

Files:

- `BE/HERA/prompts/orchestrator.py`
- `BE/HERA/prompts/device.py`

Tasks:

1. Xóa examples phrase-specific.
2. Giữ schema và ontology.
3. Thay examples bằng semantic rules cho:
   - follow-up reference;
   - ambiguity;
   - current focus;
   - recent action memory.

### Phase 4: Giảm device semantic fast parser

Files:

- `BE/HERA/agents/device_agent.py`
- `BE/HERA/agents/orchestrator.py`

Tasks:

1. Bỏ fast-route dependency trong `classify_route()` hoặc chỉ giữ explicit command fast path.
2. Giảm `fast_parse_local_command` và `fast_parse_contextual_command`.
3. Đưa ambiguous/follow-up/conditional/multi-action sang LLM parser.
4. Giữ `normalise_command()` để validate output.
5. Giữ condition evaluator và tool-call builder.

### Phase 5: Sửa noop/verification behavior bị fast parser che

Test hiện tại đã ghi nhận issue: fast parser path không trigger noop detection khi fan đã bật.

Tasks:

1. Đảm bảo mọi command path, dù parse từ fast path hay LLM, đều đi qua cùng `ToolRunner`/state comparison.
2. Không cho parser quyết định command đã complete hay chưa.
3. Completion/noop phải là runtime result, không phải parser result.

### Phase 6: Tách graph vai trò device runtime

Sau khi short path ổn:

Option A ít rủi ro:

- giữ `OrchestrationGraph`;
- chỉ gọi graph cho request không short path, nhất là device/pending/conditional.

Option B sâu hơn:

- đổi thành `DeviceRuntimeGraph`;
- orchestrator thường xử lý general/sensor/anomaly/web;
- graph chỉ xử lý device action lifecycle.

Khuyến nghị làm Option A trước.

### Phase 7: Đơn giản hóa response compose

Tasks:

1. Fallback renderer chỉ dùng khi LLM composer fail/timeout hoặc khi muốn deterministic sensor/anomaly answer.
2. Không để Python renderer và LLM composer cùng encode quá nhiều user-facing policy.
3. Chuẩn hóa payload facts cho composer:

```json
{
  "intent": "...",
  "user_message": "...",
  "facts": {
    "analysis": {},
    "tool_results": [],
    "verification": {}
  }
}
```

## 9. Definition of Done

Refactor đạt khi:

- `xin chào` không cần full graph.
- `bạn là ai` không cần full graph.
- simple sensor/anomaly query không đi qua device runtime.
- device write vẫn đi qua policy + execute + verify.
- conditional command vẫn evaluate sensor/window trước khi execute.
- prompt không còn phrase-specific testcase.
- device parser không còn là hand-written Vietnamese NLP engine lớn.
- tests không assert call count và không yêu cầu bypass router.
- FakeLLM không còn là exact phrase lookup table lớn.
- fast parser không còn gây lệch noop/verification behavior.

## 10. Nguyên tắc sau cùng

Thiết kế nên theo nguyên tắc:

> Deterministic code bảo vệ schema, safety, policy, execution, verification. LLM xử lý semantic interpretation. Tests đo behavior cuối cùng, không đo đường đi nội bộ.

Nếu theo nguyên tắc này, HERA vẫn giữ được phần an toàn cần thiết cho smart-home control, nhưng bớt giống một workflow engine cồng kềnh cho mọi câu chat đơn giản.
