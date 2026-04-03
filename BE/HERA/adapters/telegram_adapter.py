"""
Telegram Adapter
=================
Translates Telegram events into ``UserMessage`` objects, feeds them
to the Orchestrator, and sends ``AgentResponse.text`` back as a reply.

This is the *only* module that imports ``python-telegram-bot``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from telegram.request import HTTPXRequest

from agents.orchestrator import Orchestrator
from core.language_policy import detect_user_language
from core.message import AgentResponse, MessageSource, UserMessage
from core.mqtt_service import MQTTService
from config import (
    TELEGRAM_BOT_TOKEN,
    OLLAMA_MODEL,
    OPENROUTER_MODEL,
    TELEGRAM_READ_TIMEOUT,
    TELEGRAM_WRITE_TIMEOUT,
    TELEGRAM_CONNECT_TIMEOUT,
)


class TelegramAdapter:
    """Wire Telegram → Orchestrator → Telegram reply."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        mqtt: MQTTService,
        provider: str,
    ) -> None:
        self._orch = orchestrator
        self._mqtt = mqtt
        self._provider = provider
        self._app = None
        self._registered_chats = set()  # Track users who started the bot

    # ── command handlers ──────────────────────────────────────

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        self._registered_chats.add(chat_id)  # Register this user for alerts
        
        model = OLLAMA_MODEL if self._provider == "ollama" else OPENROUTER_MODEL
        provider_label = (
            f"🏠 Ollama ({model})" if self._provider == "ollama"
            else f"☁️ OpenRouter ({model})"
        )
        await update.message.reply_text(
            "👋 *Hi! I'm HERA* — your AI IoT assistant.\n\n"
            f"🤖 *Provider:* {provider_label}\n"
            "🧠 *Architecture:* Multi-Agent System\n\n"
            "💡 *Two LEDs:*\n"
            "• White indicator LED\n"
            "• NeoPixel RGB LED\n\n"
            "Try: _\"What's the temperature?\"_, _\"Turn on all lights\"_\n\n"
            "Commands: /start, /reset, /status",
            parse_mode="Markdown",
        )

    async def cmd_reset(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self._orch.reset_history(str(update.effective_chat.id))
        await update.message.reply_text("🔄 Conversation history cleared.")

    async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        s = self._mqtt.get_sensor_snapshot()
        await update.message.reply_text(
            f"📊 *Sensor state*\n"
            f"🌡 Temperature: `{s['temperature']}` °C\n"
            f"💧 Humidity: `{s['humidity']}` %\n"
            f"🤖 Anomaly: `{s['inference_result']}`\n"
            f"💡 White LED: `{'ON' if s['led_state'] else 'OFF'}`\n"
            f"🌈 NeoPixel: `{'ON' if s['neo_led_state'] else 'OFF'}`\n"
            f"🕐 Updated: `{s['last_updated'] or 'waiting…'}`",
            parse_mode="Markdown",
        )

    # ── anomaly monitoring ────────────────────────────────────

    async def monitor_anomalies(self, context):
        """Background task: Check sensor state and alert on anomalies."""
        try:
            sensor_state = self._mqtt.get_sensor_snapshot()
            current_score = sensor_state.get('inference_result') or 0  # Handle None values

            # Alert on every anomaly detection (score > 0.5) in real-time
            if current_score > 0.5:
                severity = "CRITICAL" if current_score > 0.8 else "ABNORMAL"
                alert_msg = (
                    f"\n{'='*60}\n"
                    f"🚨 {severity} Environmental Anomaly Detected!\n"
                    f"{'='*60}\n"
                    f"🌡 Temperature: {sensor_state['temperature']}°C\n"
                    f"💧 Humidity: {sensor_state['humidity']}%\n"
                    f"📊 ML Score: {current_score:.4f}\n"
                    f"{'='*60}\n"
                )
                
                print(alert_msg)
                
                # Send alert to all registered Telegram users
                if self._registered_chats and self._app:
                    for chat_id in self._registered_chats:
                        try:
                            await self._app.bot.send_message(
                                chat_id=chat_id,
                                text=alert_msg,
                                parse_mode="HTML"
                            )
                            print(f"[TELEGRAM] 📤 Sent alert to chat {chat_id}")
                        except Exception as send_err:
                            print(f"[TELEGRAM] Failed to send to {chat_id}: {send_err}")
                else:
                    print("[ALERT] ⏸️ No registered users (need /start)")

        except Exception as e:
            print(f"[MONITOR] Error: {e}")

    # ── message handler ───────────────────────────────────────

    async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        target_language = detect_user_language(update.message.text or "")

        user_msg = UserMessage(
            text=update.message.text,
            chat_id=str(update.effective_chat.id),
            source=MessageSource.TELEGRAM,
            timestamp=datetime.now(),
        )

        try:
            response: AgentResponse = await self._orch.handle(user_msg)
            reply = response.text
        except Exception as exc:
            err = str(exc)
            if "400" in err:
                reply = (
                    "⚠️ Tool calling is not supported by this model."
                    if target_language == "en"
                    else "⚠️ Model hien tai khong ho tro tool calling."
                )
            elif "401" in err:
                reply = (
                    "⚠️ API key is invalid. Please check your .env file."
                    if target_language == "en"
                    else "⚠️ API key khong hop le. Vui long kiem tra file .env."
                )
            else:
                reply = (
                    f"⚠️ Error: {exc}"
                    if target_language == "en"
                    else f"⚠️ Loi: {exc}"
                )
            print(f"[Telegram] Error: {exc}")

        try:
            await update.message.reply_text(reply)
        except Exception as send_err:
            if "timeout" in str(send_err).lower():
                try:
                    await asyncio.sleep(1)
                    await update.message.reply_text(reply)
                except Exception:
                    print(f"[Telegram] Failed to send reply after retry")
            else:
                print(f"[Telegram] Send error: {send_err}")

    # ── run ───────────────────────────────────────────────────

    def run(self) -> None:
        """Build the Telegram application and start polling."""
        request = HTTPXRequest(
            read_timeout=TELEGRAM_READ_TIMEOUT,
            write_timeout=TELEGRAM_WRITE_TIMEOUT,
            connect_timeout=TELEGRAM_CONNECT_TIMEOUT,
        )
        app = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .request(request)
            .build()
        )
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("reset", self.cmd_reset))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message),
        )
        self._app = app

        # Start background anomaly monitoring (5-second interval)
        app.job_queue.run_repeating(
            self.monitor_anomalies,
            interval=5.0,
            first=1.0
        )

        app.run_polling()
