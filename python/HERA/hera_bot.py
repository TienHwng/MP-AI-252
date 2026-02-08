"""
HERA — AI-Powered IoT Telegram Bot
====================================
A Telegram bot that uses a local LLM (Ollama) with tool calling to:
    - Monitor sensor data from the ESP32 simulator via MQTT
  - Control LEDs by publishing MQTT RPC commands
  - Respond in natural language

Usage:
    1. Start Mosquitto broker
    2. Start device_simulator.py
    3. python hera_bot.py

Requires: Ollama running with qwen2.5:7b pulled.
"""

import os
import json
import asyncio
import threading
from datetime import datetime

import paho.mqtt.client as mqtt
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import ollama


# CONFIGURATION — EDIT HERE

# --- Telegram ---
# Get this from @BotFather on Telegram
TELEGRAM_BOT_TOKEN = "8452424681:AAEtG3OeO1KP48OwC_zG0b8QapaeX1htmzU"

# --- Ollama ---
OLLAMA_MODEL = "qwen2.5:7b"

# --- MQTT ---
MQTT_BROKER = "localhost"
MQTT_PORT   = 1883

# Topics - must match device_simulator.py / real firmware
TOPIC_TELEMETRY   = "v1/devices/me/telemetry"
TOPIC_RPC_REQUEST = "v1/devices/me/rpc/request/"
TOPIC_ATTRIBUTES  = "v1/devices/me/attributes"

# Max tool-call iterations per message - safety limit
MAX_TOOL_ITERATIONS = 5


# SENSOR STATE

sensor_state = {
    "temperature":      None,
    "humidity":         None,
    "inference_result": None,
    "led_state":        None,
    "neo_led_state":    None,
    "last_updated":     None,
}


# MQTT CLIENT SETUP

mqtt_client = None
rpc_counter = 0


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[HERA-MQTT] Connected to broker")
        client.subscribe(TOPIC_TELEMETRY)
        client.subscribe(TOPIC_ATTRIBUTES)
    else:
        print(f"[HERA-MQTT] Connection failed (rc={rc})")


def on_mqtt_message(client, userdata, msg):
    """Update local sensor state from incoming telemetry."""
    try:
        data = json.loads(msg.payload.decode())
        if msg.topic == TOPIC_TELEMETRY:
            sensor_state["temperature"]      = data.get("temperature",      sensor_state["temperature"])
            sensor_state["humidity"]         = data.get("humidity",         sensor_state["humidity"])
            sensor_state["inference_result"] = data.get("inference_result", sensor_state["inference_result"])
            sensor_state["led_state"]        = data.get("led_state",        sensor_state["led_state"])
            sensor_state["neo_led_state"]    = data.get("neo_led_state",    sensor_state["neo_led_state"])
            sensor_state["last_updated"]     = datetime.now().strftime("%H:%M:%S")
        elif msg.topic == TOPIC_ATTRIBUTES:
            if "LedState" in data:
                sensor_state["led_state"] = data["LedState"]
            if "NeoLedState" in data:
                sensor_state["neo_led_state"] = data["NeoLedState"]
    except Exception as e:
        print(f"[HERA-MQTT] Parse error: {e}")


def setup_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "HERA_Bot")
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()  # runs in a background thread


# TOOL DEFINITIONS for LLM

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "turn_on_led",
            "description": (
                "Turn ON the indicator LED on the ESP32 device. "
                "Use when the user asks to turn on / enable the main LED."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_led",
            "description": (
                "Turn OFF the indicator LED on the ESP32 device. "
                "Use when the user asks to turn off / disable the main LED."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_on_neo_led",
            "description": (
                "Turn ON the NeoPixel RGB LED on the ESP32 device. "
                "Use when the user asks to turn on the NeoPixel / RGB / colorful LED."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_neo_led",
            "description": (
                "Turn OFF the NeoPixel RGB LED on the ESP32 device. "
                "Use when the user asks to turn off the NeoPixel / RGB / colorful LED."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sensor_status",
            "description": (
                "Get the current sensor readings: temperature (°C), humidity (%), "
                "anomaly detection score (0-1), and LED / NeoPixel on/off states."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# TOOL EXECUTION

def execute_tool(name: str, args: dict) -> str:
    """Run a tool and return the result string."""
    global rpc_counter

    rpc_counter += 1
    rid = rpc_counter

    if name == "turn_on_led":
        payload = {"method": "setValueLedBlinky", "params": True}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid}", json.dumps(payload))
        sensor_state["led_state"] = True
        return "LED has been turned ON."

    elif name == "turn_off_led":
        payload = {"method": "setValueLedBlinky", "params": False}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid}", json.dumps(payload))
        sensor_state["led_state"] = False
        return "LED has been turned OFF."

    elif name == "turn_on_neo_led":
        payload = {"method": "setValueNeoLed", "params": True}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid}", json.dumps(payload))
        sensor_state["neo_led_state"] = True
        return "NeoPixel LED has been turned ON."

    elif name == "turn_off_neo_led":
        payload = {"method": "setValueNeoLed", "params": False}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid}", json.dumps(payload))
        sensor_state["neo_led_state"] = False
        return "NeoPixel LED has been turned OFF."

    elif name == "get_sensor_status":
        return json.dumps(sensor_state, indent=2)

    return f"Unknown tool: {name}"


# LLM SYSTEM PROMPT

SYSTEM_PROMPT = """\
You are HERA, a friendly AI assistant for an IoT environmental monitoring system.
You help the user monitor temperature/humidity sensors on an ESP32 device
and control its actuators (LED, NeoPixel LED).

### Live sensor data (auto-refreshed)
{sensor_context}

### Important reference values
- Normal temperature range : 25 – 35 °C
- Normal humidity range    : 60 – 80 %
- Anomaly score > 0.5 means the on-device ML model detected something abnormal.

### Your capabilities (use the provided tools)
- Turn the indicator LED on/off
- Turn the NeoPixel RGB LED on/off
- Fetch the latest sensor readings

### Personality
- Be concise but expressive.
- Proactively warn the user if readings are abnormal.
- If the user asks to turn on/off lights, LEDs, etc., use the appropriate tool.
- If the user asks about status/readings, use the get_sensor_status tool first,
  then explain the result in plain language.
"""


# CONVERSATION MEMORY

conversations: dict[str, list[dict]] = {}
MAX_HISTORY = 20  # keep last N messages per chat


# TELEGRAM HANDLERS

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    conversations[chat_id] = []

    await update.message.reply_text(
        "👋 *Hi! I'm HERA* — your AI IoT assistant.\n\n"
        "Feel free to talk to me, for example:\n"
        '• _"What\'s the temperature right now?"_\n'
        '• _"Turn on the LED"_\n'
        '• _"Is everything normal?"_\n'
        '• _"Turn off all lights"_\n\n'
        "Commands: /start, /reset, /status",
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    conversations[chat_id] = []
    await update.message.reply_text("🔄 Conversation history cleared.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick raw status (no LLM)."""
    s = sensor_state
    text = (
        f"📊 *Raw sensor state*\n"
        f"🌡 Temperature: `{s['temperature']}` °C\n"
        f"💧 Humidity: `{s['humidity']}` %\n"
        f"🤖 Anomaly score: `{s['inference_result']}`\n"
        f"💡 LED: `{'ON' if s['led_state'] else 'OFF'}`\n"
        f"🌈 NeoPixel: `{'ON' if s['neo_led_state'] else 'OFF'}`\n"
        f"🕐 Last update: `{s['last_updated'] or 'waiting…'}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main handler — sends user text to the LLM with tools."""
    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    if chat_id not in conversations:
        conversations[chat_id] = []

    # ---- Build messages list ----
    sys_prompt = SYSTEM_PROMPT.format(sensor_context=json.dumps(sensor_state, indent=2))
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(conversations[chat_id][-MAX_HISTORY:])
    messages.append({"role": "user", "content": user_text})

    # ---- LLM loop - handles chained tool calls ----
    await update.message.chat.send_action("typing")

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            response = await asyncio.to_thread(
                ollama.chat,
                model=OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
            )

            assistant_msg = response.message

            # -- No tool calls → we have the final answer --
            if not assistant_msg.tool_calls:
                reply = assistant_msg.content or "(no response)"
                break

            # -- Has tool calls → execute them --
            # Append assistant message with tool_calls to history
            assistant_dict = {"role": "assistant", "content": assistant_msg.content or ""}
            assistant_dict["tool_calls"] = [
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in assistant_msg.tool_calls
            ]
            messages.append(assistant_dict)

            for tc in assistant_msg.tool_calls:
                func_name = tc.function.name
                func_args = tc.function.arguments if tc.function.arguments else {}
                print(f"[HERA] 🔧 Tool call: {func_name}({func_args})")

                result = execute_tool(func_name, func_args)
                print(f"[HERA] 📋 Result: {result}")

                messages.append({"role": "tool", "content": result})

            await update.message.chat.send_action("typing")
        else:
            reply = "(Reached tool-call limit. Please try again.)"

    except Exception as e:
        reply = f"⚠️ Error: {e}"
        print(f"[HERA] Error: {e}")

    # ---- Save history ----
    conversations[chat_id].append({"role": "user", "content": user_text})
    conversations[chat_id].append({"role": "assistant", "content": reply})
    if len(conversations[chat_id]) > MAX_HISTORY:
        conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

    await update.message.reply_text(reply)


# MAIN

def main():
    print("=" * 55)
    print("   HERA — AI-Powered IoT Telegram Bot")
    print("=" * 55)

    # Validate config
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set your TELEGRAM_BOT_TOKEN in hera_bot.py first!")
        print("   Get one from @BotFather on Telegram.")
        return

    # MQTT
    print("[HERA] Connecting to MQTT broker...")
    try:
        setup_mqtt()
        print(f"[HERA] MQTT connected ({MQTT_BROKER}:{MQTT_PORT})")
    except ConnectionRefusedError:
        print("❌ Cannot connect to MQTT broker!")
        print("   Make sure Mosquitto is running.")
        return

    # Telegram
    print(f"[HERA] LLM model: {OLLAMA_MODEL}")
    print("[HERA] Starting Telegram bot... (press Ctrl+C to stop)")
    print("[HERA] Send /start to your bot in Telegram!\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
