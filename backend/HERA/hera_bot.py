"""
HERA — Trợ lý AI IoT trên Telegram
====================================
Bot Telegram dùng LLM (Ollama / OpenRouter) với tool calling để:
  - Giám sát cảm biến ESP32 qua MQTT
  - Điều khiển LED qua lệnh RPC
  - Phản hồi bằng ngôn ngữ tự nhiên

Cách dùng:
    1. Khởi động Mosquitto broker
    2. Chạy device_simulator.py
    3. python hera_bot.py
    4. Chọn Ollama hoặc OpenRouter
"""

import os
import re
import json
import asyncio
from datetime import datetime

import paho.mqtt.client as mqtt
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from telegram.request import HTTPXRequest
import ollama
import openai
from dotenv import load_dotenv

load_dotenv()


# ==================== CẤU HÌNH ====================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
LLM_PROVIDER = None  # Được chọn khi khởi động

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-7b-instruct")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# MQTT topics — phải khớp với device_simulator.py / firmware thật
TOPIC_TELEMETRY = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/"
TOPIC_ATTRIBUTES = "v1/devices/me/attributes"

MAX_TOOL_ITERATIONS = 5
MAX_HISTORY = 8


# ==================== TRẠNG THÁI CẢM BIẾN ====================

sensor_state = {
    "temperature": None,
    "humidity": None,
    "inference_result": None,
    "led_state": None,
    "neo_led_state": None,
    "last_updated": None,
}


# ==================== MQTT ====================

mqtt_client = None
rpc_counter = 0


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(TOPIC_TELEMETRY)
        client.subscribe(TOPIC_ATTRIBUTES)
        print("[MQTT] Đã kết nối broker")
    else:
        print(f"[MQTT] Kết nối thất bại (rc={rc})")


def on_mqtt_message(client, userdata, msg):
    """Cập nhật trạng thái cảm biến từ telemetry / attributes."""
    try:
        data = json.loads(msg.payload.decode())
        if msg.topic == TOPIC_TELEMETRY:
            for key in ("temperature", "humidity", "inference_result",
                        "led_state", "neo_led_state"):
                if key in data:
                    sensor_state[key] = data[key]
            sensor_state["last_updated"] = datetime.now().strftime("%H:%M:%S")
        elif msg.topic == TOPIC_ATTRIBUTES:
            # RPC response dùng key PascalCase (LedState, NeoLedState)
            if "LedState" in data:
                sensor_state["led_state"] = data["LedState"]
            if "NeoLedState" in data:
                sensor_state["neo_led_state"] = data["NeoLedState"]
    except Exception as e:
        print(f"[MQTT] Lỗi parse: {e}")


def setup_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "HERA_Bot")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()


# ==================== ĐIỀU KHIỂN THIẾT BỊ ====================

def _publish_rpc(method: str, params) -> None:
    """Gửi lệnh RPC tới thiết bị qua MQTT."""
    global rpc_counter
    rpc_counter += 1
    payload = {"method": method, "params": params}
    mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rpc_counter}", json.dumps(payload))


# Bảng ánh xạ tool đơn lẻ: name -> (rpc_method, params, state_key, state_val, response)
_SINGLE_LED_TOOLS = {
    "turn_on_led":      ("setValueLedBlinky", True,  "led_state",     True,
                         "LED has been turned ON."),
    "turn_off_led":     ("setValueLedBlinky", False, "led_state",     False,
                         "LED has been turned OFF."),
    "turn_on_neo_led":  ("setValueNeoLed",    True,  "neo_led_state", True,
                         "NeoPixel LED has been turned ON."),
    "turn_off_neo_led": ("setValueNeoLed",    False, "neo_led_state", False,
                         "NeoPixel LED has been turned OFF."),
}


def execute_tool(name: str, args: dict) -> str:
    """Thực thi tool và trả về kết quả text cho LLM."""
    if name in _SINGLE_LED_TOOLS:
        method, params, state_key, state_val, msg = _SINGLE_LED_TOOLS[name]
        _publish_rpc(method, params)
        sensor_state[state_key] = state_val
        return msg

    if name == "turn_on_all_lights":
        _publish_rpc("setValueLedBlinky", True)
        _publish_rpc("setValueNeoLed", True)
        sensor_state["led_state"] = True
        sensor_state["neo_led_state"] = True
        return "Both LEDs have been turned ON."

    if name == "turn_off_all_lights":
        _publish_rpc("setValueLedBlinky", False)
        _publish_rpc("setValueNeoLed", False)
        sensor_state["led_state"] = False
        sensor_state["neo_led_state"] = False
        return "Both LEDs have been turned OFF."

    if name == "get_sensor_status":
        return json.dumps(sensor_state, indent=2)

    return f"Unknown tool: {name}"


# ==================== TOOL DEFINITIONS ====================

def _tool_def(name: str, desc: str) -> dict:
    """Tạo định nghĩa tool không tham số cho LLM."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }


TOOLS = [
    _tool_def("turn_on_led",
              "Turn ON the white indicator LED (main LED). "
              "Use for 'main LED', 'white LED', 'indicator LED'."),
    _tool_def("turn_off_led",
              "Turn OFF the white indicator LED (main LED). "
              "Use for 'main LED', 'white LED', 'indicator LED'."),
    _tool_def("turn_on_neo_led",
              "Turn ON the NeoPixel RGB LED (colorful LED). "
              "Use for 'NeoPixel', 'RGB LED', 'colorful LED', 'color LED'."),
    _tool_def("turn_off_neo_led",
              "Turn OFF the NeoPixel RGB LED (colorful LED). "
              "Use for 'NeoPixel', 'RGB LED', 'colorful LED', 'color LED'."),
    _tool_def("turn_on_all_lights",
              "Turn ON both LEDs (white + NeoPixel). "
              "Use for 'all lights', 'both lights', 'all LEDs'."),
    _tool_def("turn_off_all_lights",
              "Turn OFF both LEDs (white + NeoPixel). "
              "Use for 'all lights off', 'both off', 'turn off everything'."),
    _tool_def("get_sensor_status",
              "Get current sensor readings: temperature, humidity, "
              "anomaly score, and LED states."),
]


# ==================== LLM ====================

SYSTEM_PROMPT = """\
You are HERA, an AI assistant for an IoT environmental monitoring system.
You monitor sensors on an ESP32 and control its TWO LEDs, to simulating a AIoT for smarthome.
DO NOT ANSWER THE PROMPT USING CHINESE/CHINESE SIMPLIFIED/MANDARIN IN ANY CASE, NO EXCEPTION.

### Two LEDs on device
1. White Indicator LED (main LED)
2. NeoPixel RGB LED (colorful LED)

### Live sensor data
{sensor_context}

### Reference values
- Normal temperature: 25–35 °C
- Normal humidity: 60–80 %
- Anomaly score > 0.5 = abnormal (on-device ML detection)

### System info
- Provider: {llm_provider} | Model: {model_name}

### Rules
- ALWAYS respond in the SAME LANGUAGE as the user's input
- Answer ONLY what was asked — no extra info
- Be concise and direct
- NEVER generate image URLs or markdown images, or any unrelated content with the prompt
- Do NOT make up external services or IP addresses
- When tools succeed, confirm briefly
- "lights" / "both" / "all" → use ALL lights tools
- Specific LED name → use specific LED tool
- For device status → use get_sensor_status first
"""


def _llm_completion(messages: list) -> dict:
    """
    Gọi LLM (Ollama hoặc OpenRouter), trả về kết quả chuẩn hóa.
    Returns: {"content": str|None, "tool_calls": [{"id", "name", "args"}] | None}
    """
    if LLM_PROVIDER == "ollama":
        resp = ollama.chat(model=OLLAMA_MODEL, messages=messages, tools=TOOLS)
        msg = resp.message
        if not msg.tool_calls:
            return {"content": msg.content, "tool_calls": None}
        return {
            "content": msg.content or "",
            "tool_calls": [
                {"id": f"call_{i}", "name": tc.function.name,
                 "args": tc.function.arguments or {}}
                for i, tc in enumerate(msg.tool_calls)
            ],
        }

    # OpenRouter (qua OpenAI-compatible API)
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY chưa được set trong .env")
    client = openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)
    resp = client.chat.completions.create(
        model=OPENROUTER_MODEL, messages=messages, tools=TOOLS,
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return {"content": msg.content, "tool_calls": None}
    return {
        "content": msg.content or "",
        "tool_calls": [
            {"id": tc.id, "name": tc.function.name,
             "args": json.loads(tc.function.arguments) if tc.function.arguments else {}}
            for tc in msg.tool_calls
        ],
    }


def _build_assistant_tool_msg(content: str, tool_calls: list) -> dict:
    """Tạo assistant message chứa tool calls — format khác nhau theo provider."""
    msg = {"role": "assistant", "content": content}
    if LLM_PROVIDER == "openrouter":
        msg["tool_calls"] = [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
            for tc in tool_calls
        ]
    else:
        msg["tool_calls"] = [
            {"function": {"name": tc["name"], "arguments": tc["args"]}}
            for tc in tool_calls
        ]
    return msg


def _build_tool_result_msg(tool_call_id: str, result: str) -> dict:
    """Tạo tool result message — OpenRouter cần tool_call_id."""
    msg = {"role": "tool", "content": result}
    if LLM_PROVIDER == "openrouter":
        msg["tool_call_id"] = tool_call_id
    return msg


_HALLUCINATION_MARKERS = (
    "![", "Image:", "Picture:", "Photo:",
    "http://192.168.", "LED_ON.jpeg", "specific color you'd like for",
)


def filter_response(text: str) -> str:
    """Lọc nội dung hallucination (URL ảnh giả, markdown image)."""
    if not text:
        return text
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'https?://[^\s]+\.(jpg|jpeg|png|gif)', '', text)
    if any(m in text for m in _HALLUCINATION_MARKERS):
        return "✅ Action completed successfully."
    return text.strip()


# ==================== TELEGRAM HANDLERS ====================

conversations: dict[str, list[dict]] = {}


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    conversations[chat_id] = []
    provider = (f"🏠 Ollama ({OLLAMA_MODEL})" if LLM_PROVIDER == "ollama"
                else f"☁️ OpenRouter ({OPENROUTER_MODEL})")
    await update.message.reply_text(
        "👋 *Hi! I'm HERA* — your AI IoT assistant.\n\n"
        f"🤖 *Provider:* {provider}\n\n"
        "💡 *Two LEDs:*\n"
        "• White indicator LED\n"
        "• NeoPixel RGB LED\n\n"
        "Try: _\"What's the temperature?\"_, _\"Turn on all lights\"_\n\n"
        "Commands: /start, /reset, /status",
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conversations[str(update.effective_chat.id)] = []
    await update.message.reply_text("🔄 Conversation history cleared.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Trạng thái cảm biến nhanh (không qua LLM)."""
    s = sensor_state
    await update.message.reply_text(
        f"📊 *Raw sensor state*\n"
        f"🌡 Temperature: `{s['temperature']}` °C\n"
        f"💧 Humidity: `{s['humidity']}` %\n"
        f"🤖 Anomaly: `{s['inference_result']}`\n"
        f"💡 White LED: `{'ON' if s['led_state'] else 'OFF'}`\n"
        f"🌈 NeoPixel: `{'ON' if s['neo_led_state'] else 'OFF'}`\n"
        f"🕐 Updated: `{s['last_updated'] or 'waiting…'}`",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn: gửi đến LLM, thực thi tool nếu có, trả lời user."""
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    if chat_id not in conversations:
        conversations[chat_id] = []

    # Xây dựng danh sách messages cho LLM
    model_name = OLLAMA_MODEL if LLM_PROVIDER == "ollama" else OPENROUTER_MODEL
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            sensor_context=json.dumps(sensor_state, indent=2),
            llm_provider=LLM_PROVIDER,
            model_name=model_name,
        )},
        *conversations[chat_id][-MAX_HISTORY:],
        {"role": "user", "content": user_text},
    ]

    tool_calls_made = False
    reply = ""

    try:
        # Vòng lặp tool call — LLM có thể gọi tool nhiều lần liên tiếp
        for _ in range(MAX_TOOL_ITERATIONS):
            result = await asyncio.to_thread(_llm_completion, messages)

            # Không có tool call → đây là phản hồi cuối
            if not result["tool_calls"]:
                reply = result["content"] or "(no response)"
                break

            # Có tool calls → thực thi rồi gửi kết quả lại cho LLM
            tool_calls_made = True
            messages.append(
                _build_assistant_tool_msg(result["content"], result["tool_calls"])
            )
            for tc in result["tool_calls"]:
                print(f"[HERA] 🔧 {tc['name']}({tc['args']})")
                tool_result = execute_tool(tc["name"], tc["args"])
                print(f"[HERA] 📋 {tool_result}")
                messages.append(_build_tool_result_msg(tc["id"], tool_result))
        else:
            reply = "(Reached tool-call limit. Please try again.)"

    except Exception as e:
        err = str(e)
        if LLM_PROVIDER == "openrouter" and "400" in err:
            reply = "⚠️ Tool calling not supported by this model."
        elif LLM_PROVIDER == "openrouter" and "401" in err:
            reply = "⚠️ API key invalid. Check .env file."
        else:
            reply = f"⚠️ Error: {e}"
        print(f"[HERA] Error: {e}")

    # Reset lịch sử nếu có tool call để tránh context pollution
    if tool_calls_made:
        conversations[chat_id] = []
    else:
        conversations[chat_id].append({"role": "user", "content": user_text})
        conversations[chat_id].append({"role": "assistant", "content": reply})
        if len(conversations[chat_id]) > MAX_HISTORY:
            conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

    # Gửi reply với retry logic cho timeout
    final_reply = filter_response(reply)
    try:
        await update.message.reply_text(final_reply)
    except Exception as e:
        # Nếu timeout/network error, thử lại 1 lần
        if "TimedOut" in str(type(e).__name__) or "timeout" in str(e).lower():
            try:
                await asyncio.sleep(1)  # Chờ 1s rồi thử lại
                await update.message.reply_text(final_reply)
            except Exception as retry_err:
                print(f"[HERA] Không gửi được replies (đã retry): {retry_err}")
        else:
            print(f"[HERA] Lỗi gửi reply: {e}")


# ==================== CHỌN PROVIDER ====================

def select_llm_provider() -> str:
    """Menu chọn LLM provider khi khởi động."""
    print("\n" + "=" * 50)
    print("   🤖 HERA — Chọn LLM Provider")
    print("=" * 50)

    while True:
        print("\n1. 🏠 Ollama (Local, miễn phí)")
        print("2. ☁️  OpenRouter (Cloud, ~$0.20/1M tokens)")
        choice = input("\nChọn (1/2): ").strip()

        if choice == "1":
            try:
                models = [m["name"] for m in ollama.list()["models"]]
                if OLLAMA_MODEL in models:
                    print(f"✅ Ollama sẵn sàng: {OLLAMA_MODEL}")
                    return "ollama"
                print(f"❌ Model {OLLAMA_MODEL} chưa có. Run: ollama pull {OLLAMA_MODEL}")
                print(f"   Có sẵn: {', '.join(models)}")
            except Exception as e:
                print(f"❌ Ollama không khả dụng: {e}")
            continue

        if choice == "2":
            if not OPENROUTER_API_KEY:
                print("❌ OPENROUTER_API_KEY chưa được set trong .env")
                continue
            try:
                print("⏳ Kiểm tra API key...")
                client = openai.OpenAI(
                    base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY,
                )
                client.chat.completions.create(
                    model=OPENROUTER_MODEL,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=5,
                )
                print(f"✅ OpenRouter OK: {OPENROUTER_MODEL}")
                return "openrouter"
            except Exception as e:
                print(f"❌ OpenRouter lỗi: {e}")
            continue

        print("❌ Chọn 1 hoặc 2.")


# ==================== MAIN ====================

def main():
    global LLM_PROVIDER

    print("=" * 50)
    print("   HERA — AI-Powered IoT Telegram Bot")
    print("=" * 50)

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN chưa có trong .env!")
        return

    LLM_PROVIDER = select_llm_provider()

    try:
        setup_mqtt()
        print(f"[MQTT] Đã kết nối {MQTT_BROKER}:{MQTT_PORT}")
    except ConnectionRefusedError:
        print("❌ Không kết nối được MQTT broker!")
        return

    model = OLLAMA_MODEL if LLM_PROVIDER == "ollama" else OPENROUTER_MODEL
    print(f"[HERA] Provider: {LLM_PROVIDER} | Model: {model}")
    print("[HERA] Bot đang chạy... (Ctrl+C để dừng)\n")

    # Request với timeout cao hơn (30s) để tránh timeout khi network chậm
    request = HTTPXRequest(read_timeout=30, write_timeout=30, connect_timeout=30)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
