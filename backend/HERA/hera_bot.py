"""
HERA — AI-Powered IoT Telegram Bot
====================================
A Telegram bot that uses either local LLM (Ollama) or cloud LLM (OpenRouter) with tool calling to:
    - Monitor sensor data from the ESP32 simulator via MQTT
  - Control LEDs by publishing MQTT RPC commands
  - Respond in natural language

Usage:
    1. Start Mosquitto broker
    2. Start device_simulator.py
    3. python hera_bot.py
    4. Choose between Ollama or OpenRouter when prompted

Requires: 
  - For Ollama: Ollama running with qwen2.5:7b pulled
  - For OpenRouter: Valid API key in environment variable OPENROUTER_API_KEY
"""

import os
import json
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any

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
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# CONFIGURATION — Loaded from .env file

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- LLM Provider Configuration ---
LLM_PROVIDER = None  # Will be set based on user selection

# --- Ollama ---
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

# --- OpenRouter ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-7b-instruct")  # Budget-friendly
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# --- MQTT ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost") 
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

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


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
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
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "HERA_Bot")
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
                "Turn ON the white indicator LED (main LED) on the ESP32 device. "
                "This is the basic white LED, NOT the colorful NeoPixel. "
                "Use when user specifically mentions 'main LED', 'white LED', or 'indicator LED'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_led",
            "description": (
                "Turn OFF the white indicator LED (main LED) on the ESP32 device. "
                "This is the basic white LED, NOT the colorful NeoPixel. "
                "Use when user specifically mentions 'main LED', 'white LED', or 'indicator LED'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_on_neo_led",
            "description": (
                "Turn ON the NeoPixel RGB LED (colorful LED) on the ESP32 device. "
                "This is the colorful programmable LED, NOT the basic white LED. "
                "Use when user mentions 'NeoPixel', 'RGB LED', 'colorful LED', or 'color LED'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_neo_led",
            "description": (
                "Turn OFF the NeoPixel RGB LED (colorful LED) on the ESP32 device. "
                "This is the colorful programmable LED, NOT the basic white LED. "
                "Use when user mentions 'NeoPixel', 'RGB LED', 'colorful LED', or 'color LED'."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_on_all_lights",
            "description": (
                "Turn ON both LEDs: the white indicator LED AND the NeoPixel RGB LED. "
                "Use when user says 'all lights', 'both lights', 'everything', 'all LEDs', or wants both lights on."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_all_lights",
            "description": (
                "Turn OFF both LEDs: the white indicator LED AND the NeoPixel RGB LED. "
                "Use when user says 'all lights off', 'both lights off', 'turn off everything', 'all LEDs off', or wants both lights off."
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

    elif name == "turn_on_all_lights":
        # Turn on both LEDs
        rid1 = rpc_counter + 1
        rpc_counter += 1
        payload1 = {"method": "setValueLedBlinky", "params": True}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid1}", json.dumps(payload1))
        sensor_state["led_state"] = True
        
        rid2 = rpc_counter + 1  
        rpc_counter += 1
        payload2 = {"method": "setValueNeoLed", "params": True}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid2}", json.dumps(payload2))
        sensor_state["neo_led_state"] = True
        
        return "Both LEDs have been turned ON: white indicator LED and NeoPixel RGB LED."

    elif name == "turn_off_all_lights":
        # Turn off both LEDs
        rid1 = rpc_counter + 1
        rpc_counter += 1  
        payload1 = {"method": "setValueLedBlinky", "params": False}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid1}", json.dumps(payload1))
        sensor_state["led_state"] = False
        
        rid2 = rpc_counter + 1
        rpc_counter += 1
        payload2 = {"method": "setValueNeoLed", "params": False}
        mqtt_client.publish(f"{TOPIC_RPC_REQUEST}{rid2}", json.dumps(payload2))
        sensor_state["neo_led_state"] = False
        
        return "Both LEDs have been turned OFF: white indicator LED and NeoPixel RGB LED."

    elif name == "get_sensor_status":
        return json.dumps(sensor_state, indent=2)

    return f"Unknown tool: {name}"


# LLM SYSTEM PROMPT

SYSTEM_PROMPT = """\
You are HERA, a friendly AI assistant for an IoT environmental monitoring system.
You help the user monitor temperature/humidity sensors on an ESP32 device
and control its actuators (TWO separate LEDs + sensors).

### Device has TWO different LEDs:
1. **White Indicator LED** - Basic white LED (main LED)  
2. **NeoPixel RGB LED** - Colorful programmable LED

### Live sensor data (auto-refreshed)
{sensor_context}

### Important reference values
- Normal temperature range : 25 – 35 °C
- Normal humidity range    : 60 – 80 %
- Anomaly score > 0.5 means the on-device ML model detected something abnormal.

### Your capabilities (use the provided tools)
- Turn the WHITE indicator LED on/off (main LED)
- Turn the NEOPIXEL RGB LED on/off (colorful LED)  
- Turn BOTH LEDs on/off at same time
- Fetch the latest sensor readings

### System info
- AI Provider: {llm_provider}
- Model: {model_name}

### STRICT RULES
- ALWAYS respond in the SAME LANGUAGE as the user's input
- If user writes in English, respond in English
- If user writes in Vietnamese, respond in Vietnamese  
- If user writes in other languages, respond in that same language
- ANSWER ONLY what the user asks - do NOT volunteer extra information
- If they ask for time, give ONLY time
- If they ask for temperature, give ONLY temperature  
- If they ask for device status, THEN give sensor/LED info
- Be concise and direct - no unnecessary details
- NEVER generate, suggest, or reference any image URLs
- NEVER use markdown image syntax ![](url)
- NEVER mention image files, cameras, or visual content
- ONLY respond with plain text about sensor data and device control
- Do NOT make up external services or IP addresses
- When tools execute successfully, simply confirm the action was completed
- When user says "lights" (plural), "both lights", or "all lights" - use the ALL lights tools
- When user specifies one LED type, use the specific LED tool

### Personality
- Be concise and direct.
- Answer exactly what was asked, nothing more.
- Only mention sensor/LED status if specifically asked about device status.
- If the user asks to turn on/off lights, LEDs, etc., use the appropriate tool.
- If the user asks about device status/readings, use the get_sensor_status tool first.
- Keep responses focused ONLY on what was asked.
"""


# CONVERSATION MEMORY

conversations: dict[str, list[dict]] = {}
MAX_HISTORY = 8  # Reduced for better context management


# TELEGRAM HANDLERS

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    conversations[chat_id] = []
    
    provider_info = f"🏠 Ollama ({OLLAMA_MODEL})" if LLM_PROVIDER == "ollama" else f"☁️ OpenRouter ({OPENROUTER_MODEL})"

    await update.message.reply_text(
        "👋 *Hi! I'm HERA* — your AI IoT assistant.\n\n"
        f"🤖 *AI Provider:* {provider_info}\n\n"
        "💡 *I control TWO LEDs:*\n"
        "• White indicator LED (main LED)\n"  
        "• NeoPixel RGB LED (colorful LED)\n\n"
        "Feel free to talk to me, for example:\n"
        '• _"What\'s the temperature right now?"_\n'
        '• _"Turn on the white LED"_\n'
        '• _"Turn on the colorful LED"_\n'  
        '• _"Turn off all lights"_\n'
        '• _"Is everything normal?"_\n\n'
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
        f"💡 White LED: `{'ON' if s['led_state'] else 'OFF'}`\n"
        f"🌈 NeoPixel LED: `{'ON' if s['neo_led_state'] else 'OFF'}`\n"
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
    model_name = OLLAMA_MODEL if LLM_PROVIDER == "ollama" else OPENROUTER_MODEL
    sys_prompt = SYSTEM_PROMPT.format(
        sensor_context=json.dumps(sensor_state, indent=2),
        llm_provider=LLM_PROVIDER,
        model_name=model_name
    )
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(conversations[chat_id][-MAX_HISTORY:])
    messages.append({"role": "user", "content": user_text})

    # ---- LLM loop - handles chained tool calls ----
    # Removed typing action to prevent timeouts
    
    tool_calls_made = False  # Track if any tools were called

    try:
        for iteration in range(MAX_TOOL_ITERATIONS):
            if LLM_PROVIDER == "ollama":
                response = await asyncio.to_thread(
                    ollama.chat,
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                )
                assistant_msg = response.message

                # -- Ollama: No tool calls → we have the final answer --
                if not assistant_msg.tool_calls:
                    reply = assistant_msg.content or "(no response)"
                    break

                # -- Ollama: Has tool calls → execute them --
                tool_calls_made = True
                
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

            elif LLM_PROVIDER == "openrouter":
                response = await asyncio.to_thread(
                    call_openrouter_chat,
                    messages=messages,
                    tools=TOOLS,
                )
                
                # OpenRouter returns processed messages list
                messages = response["messages"]
                reply = response["reply"]
                tool_calls_made = response.get("had_tools", False)
                
                if reply:
                    break
                    
            else:
                raise ValueError(f"Unknown LLM provider: {LLM_PROVIDER}")

            # Removed typing action to prevent timeouts between iterations
        else:
            reply = "(Reached tool-call limit. Please try again.)"

    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg and LLM_PROVIDER == "openrouter":
            reply = f"⚠️ Tool calling not supported by this model. Try saying 'turn on LED' in simple text."
        elif "401" in error_msg and LLM_PROVIDER == "openrouter": 
            reply = f"⚠️ API key invalid. Check OPENROUTER_API_KEY in .env file"
        else:
            reply = f"⚠️ Error: {e}"
        print(f"[HERA] Error: {e}")

    # ---- Save history ----
    # For tool calling reliability, completely reset conversation after any tool use
    if tool_calls_made:
        conversations[chat_id] = []  # Complete reset for clean slate
    else:
        # Normal conversation - maintain some context
        conversations[chat_id].append({"role": "user", "content": user_text})
        conversations[chat_id].append({"role": "assistant", "content": reply})
        
        if len(conversations[chat_id]) > MAX_HISTORY:
            conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

    # Filter out any hallucinated content before sending
    reply = filter_response(reply)
    await update.message.reply_text(reply)


def filter_response(text: str) -> str:
    """Remove hallucinated content like fake image URLs."""
    if not text:
        return text
    
    # Remove markdown image syntax
    import re
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # Remove any URLs that look like fake image services
    text = re.sub(r'http[s]?://[^\s]+\.(jpg|jpeg|png|gif)', '', text)
    
    # Remove common hallucinated phrases
    hallucination_phrases = [
        "![",
        "Image:",
        "Picture:",
        "Photo:",
        "http://192.168.",
        "LED_ON.jpeg",
        "specific color you'd like for"
    ]
    
    for phrase in hallucination_phrases:
        if phrase in text:
            text = "✅ Action completed successfully."
            break
    
    return text.strip()


# OPENROUTER CLIENT

def call_openrouter_chat(messages: list, tools: list) -> dict:
    """Call OpenRouter API with proper tool calling protocol."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter")
    
    client = openai.OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )
    
    try:
        # Make initial request with tools
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            tools=tools,
        )
        
        choice = response.choices[0]
        assistant_message = choice.message
        
        # If no tool calls, return the final response
        if not assistant_message.tool_calls:
            return {
                "messages": messages + [{"role": "assistant", "content": assistant_message.content}],
                "reply": assistant_message.content,
                "had_tools": False
            }
        
        # Process tool calls following OpenRouter format
        messages.append({
            "role": "assistant", 
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })
        
        # Execute tools and add results
        for tc in assistant_message.tool_calls:
            func_name = tc.function.name
            func_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            
            print(f"[HERA] 🔧 Tool call: {func_name}({func_args})")
            result = execute_tool(func_name, func_args)
            print(f"[HERA] 📋 Result: {result}")
            
            # Add tool result in OpenRouter format
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })
        
        # Make second request with tool results
        final_response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            tools=tools  # Always include tools as per documentation
        )
        
        final_content = final_response.choices[0].message.content
        
        return {
            "messages": messages + [{"role": "assistant", "content": final_content}],
            "reply": final_content,
            "had_tools": True  # We had tool calls if we reach here
        }
        
    except Exception as e:
        error_msg = str(e)
        if "400" in error_msg:
            error_reply = "⚠️ Model doesn't support tool calling. Try a different model or use Ollama."
        elif "401" in error_msg:
            error_reply = "⚠️ Invalid API key. Check your .env file."
        else:
            error_reply = f"⚠️ OpenRouter error: {error_msg}"
            
        return {
            "messages": messages + [{"role": "assistant", "content": error_reply}],
            "reply": error_reply,
            "had_tools": False
        }


# PROVIDER SELECTION

def select_llm_provider() -> str:
    """Interactive provider selection at startup."""
    print("\n" + "="*60)
    print("   🤖 HERA - LLM Provider Selection")
    print("="*60)
    
    while True:
        print("\nChoose your LLM provider:")
        print("1. 🏠 Ollama (Local) - Free")
        print("2. ☁️  OpenRouter (Cloud) - Budget models (~$0.20/1M tokens)")
        print("3. ❓ Help me decide")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            # Validate Ollama availability
            try:
                ollama.list()
                available_models = [model['name'] for model in ollama.list()['models']]
                if OLLAMA_MODEL in available_models:
                    print(f"✅ Ollama is ready with model: {OLLAMA_MODEL}")
                    return "ollama"
                else:
                    print(f"❌ Model {OLLAMA_MODEL} not found in Ollama")
                    print(f"Available models: {', '.join(available_models)}")
                    print(f"Run: ollama pull {OLLAMA_MODEL}")
                    continue
            except Exception as e:
                print(f"❌ Ollama not available: {e}")
                print("Make sure Ollama is installed and running")
                continue
        
        elif choice == "2":
            if OPENROUTER_API_KEY:
                # Test API key before confirming
                print("\u23f3 Testing OpenRouter API key...")
                try:
                    client = openai.OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=OPENROUTER_API_KEY,
                    )
                    # Quick test call to validate API key and model
                    response = client.chat.completions.create(
                        model=OPENROUTER_MODEL,
                        messages=[{"role": "user", "content": "Hello"}],
                        max_tokens=5
                    )
                    print(f"✅ OpenRouter API key valid")
                    print(f"✅ Model {OPENROUTER_MODEL} available")
                    return "openrouter"
                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ OpenRouter API error: {e}")
                    if "400" in error_msg or "bad request" in error_msg.lower():
                        print(f"💡 Model '{OPENROUTER_MODEL}' might be unavailable")
                        print("   Try editing .env with: OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct")
                    elif "401" in error_msg or "unauthorized" in error_msg.lower():
                        print("   Check your API key in .env file")
                    else:
                        print("   Please check your API key and model availability")
                    continue
            else:
                print("❌ OPENROUTER_API_KEY not set in .env file")
                print("Add your API key to .env: OPENROUTER_API_KEY=sk-or-v1-...")
                continue
        
        elif choice == "3":
            print("\n📊 Comparison:")
            print("┌─────────────┬─────────────┬──────────────┬───────────────┐")
            print("│ Provider    │ Speed       │ Cost         │ Model         │")
            print("├─────────────┼─────────────┼──────────────┼───────────────┤")
            print("│ Ollama      │ ⚡ Fast    │ 💰 Free     │ Qwen 2.5 7B  │")
            print("│ OpenRouter  │ 🚀 Fast    │ 💰 ~$0.02/day│ Qwen 2.5 7B  │")
            print("└─────────────┴─────────────┴──────────────┴───────────────┘")
            print("\n💡 Budget-friendly setup:")
            print("   • Ollama: Completely free, runs on your hardware")
            print("   • OpenRouter: Very cheap Qwen models (~$0.20/1M tokens)")
            continue
        
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")


# MAIN

def main():
    global LLM_PROVIDER
    
    print("=" * 55)
    print("   HERA — AI-Powered IoT Telegram Bot")
    print("=" * 55)

    # Validate config
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env file!")
        print("   1. Copy .env file and add your token")
        print("   2. Get one from @BotFather on Telegram")
        return

    # Select LLM provider FIRST
    LLM_PROVIDER = select_llm_provider()
    print(f"\n[HERA] Selected provider: {LLM_PROVIDER}")

    # MQTT
    print("\n[HERA] Connecting to MQTT broker...")
    try:
        setup_mqtt()
        print(f"[HERA] MQTT connected ({MQTT_BROKER}:{MQTT_PORT})")
    except ConnectionRefusedError:
        print("❌ Cannot connect to MQTT broker!")
        print("   Make sure Mosquitto is running.")
        return

    # Display configuration
    if LLM_PROVIDER == "ollama":
        print(f"[HERA] 🏠 LLM Provider: Ollama (Local)")
        print(f"[HERA] 🤖 Model: {OLLAMA_MODEL}")
    elif LLM_PROVIDER == "openrouter":
        print(f"[HERA] ☁️  LLM Provider: OpenRouter (Cloud)")
        print(f"[HERA] 🤖 Model: {OPENROUTER_MODEL}")
    
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
