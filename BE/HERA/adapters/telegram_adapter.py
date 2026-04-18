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

from agents.orchestrator import Orchestrator
from config import (
	TELEGRAM_BOT_TOKEN,
	TELEGRAM_CONNECT_TIMEOUT,
	TELEGRAM_READ_TIMEOUT,
	TELEGRAM_WRITE_TIMEOUT,
)
from core.message import AgentResponse, MessageSource, UserMessage
from core.mqtt_service import MQTTService
from core.runtime_settings import runtime_settings
from telegram import Update
from telegram.ext import (
	Application,
	CommandHandler,
	ContextTypes,
	MessageHandler,
	filters,
)
from telegram.request import HTTPXRequest


class TelegramAdapter:
	"""Wire Telegram → Orchestrator → Telegram reply."""

	def __init__(
		self,
		orchestrator: Orchestrator,
		mqtt: MQTTService,
		provider: str,
	) -> None:
		self.orch = orchestrator
		self.mqtt = mqtt
		self.provider = provider
		self.app = None
		self.registered_chats = set()  # Track users who started the bot

	# ── command handlers ──────────────────────────────────────

	async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
		chat_id = update.effective_chat.id
		self.registered_chats.add(chat_id)  # Register this user for alerts

		settings = runtime_settings.get()
		active_provider = settings["provider"]
		model = settings["models"][active_provider]["orchestratorModel"]
		provider_label = (
			f"Ollama ({model})"
			if active_provider == "ollama"
			else f"OpenRouter ({model})"
		)
		await update.message.reply_text(
			"*Hi! I'm HERA* — your AI IoT assistant.\n\n"
			f"*Provider:* {provider_label}\n"
			"*Architecture:* Multi-Agent System\n\n"
			"*Two LEDs:*\n"
			"• White indicator LED\n"
			"• NeoPixel RGB LED\n\n"
			'Try: _"What\'s the temperature?"_, _"Turn on all lights"_\n\n'
			"Commands: /start, /reset, /status",
			parse_mode="Markdown",
		)

	async def cmd_reset(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
		self.orch.reset_history(str(update.effective_chat.id))
		await update.message.reply_text("Conversation history cleared.")

	async def cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
		sensors = self.mqtt.get_sensor_readings_snapshot()
		devices = self.mqtt.get_device_snapshot()
		network = self.mqtt.get_network_snapshot()
		anomaly_score = sensors.get("anomaly")
		await update.message.reply_text(
			f"*Sensor state*\n"
			f"Temperature: `{sensors.get('temperature')}` °C\n"
			f"Humidity: `{sensors.get('humidity')}` %\n"
			f"Light: `{sensors.get('light')}`\n"
			f"Anomaly: `{anomaly_score}`\n"
			f"White LED: `{'ON' if devices.get('led_status') else 'OFF'}`\n"
			f"NeoPixel: `{'ON' if devices.get('neo_led_status') else 'OFF'}`\n"
			f"WS2812: `{'ON' if devices.get('ws2812_status') else 'OFF'}`\n"
			f"Relay: `{'ON' if devices.get('relay_status') else 'OFF'}`\n"
			f"Mini fan: `{'ON' if devices.get('mini_fan_status') else 'OFF'}`\n"
			f"WiFi RSSI: `{network.get('wifi_rssi')}` dBm\n"
			f"Uptime: `{network.get('uptime_ms')}` ms",
			parse_mode="Markdown",
		)

	# ── anomaly monitoring ────────────────────────────────────

	async def monitor_anomalies(self, context):
		"""Background task: Check sensor state and alert on anomalies."""
		try:
			sensor_state = self.mqtt.get_sensor_snapshot()
			sensors = sensor_state.get("sensors", {})
			current_score = sensors.get("anomaly") or 0

			# Alert on every anomaly detection (score > 0.5) in real-time
			if current_score > 0.5:
				severity = "CRITICAL" if current_score > 0.8 else "ABNORMAL"
				alert_msg = (
					f"\n{'=' * 60}\n"
					f"{severity} Environmental Anomaly Detected!\n"
					f"{'=' * 60}\n"
					f"Temperature: {sensors.get('temperature')}°C\n"
					f"Humidity: {sensors.get('humidity')}%\n"
					f"ML Score: {current_score:.4f}\n"
					f"{'=' * 60}\n"
				)

				print(alert_msg)

				# Send alert to all registered Telegram users
				if self.registered_chats and self.app:
					for chat_id in self.registered_chats:
						try:
							await self.app.bot.send_message(
								chat_id=chat_id, text=alert_msg, parse_mode="HTML"
							)
							print(f"[TELEGRAM] Sent alert to chat {chat_id}")
						except Exception as send_err:
							print(f"[TELEGRAM] Failed to send to {chat_id}: {send_err}")
				else:
					print("[ALERT] No registered users (need /start)")

		except Exception as e:
			print(f"[MONITOR] Error: {e}")

	# ── message handler ───────────────────────────────────────

	async def handle_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
		user_msg = UserMessage(
			text=update.message.text,
			chat_id=str(update.effective_chat.id),
			source=MessageSource.TELEGRAM,
			timestamp=datetime.now(),
		)

		try:
			response: AgentResponse = await self.orch.handle(user_msg)
			reply = response.text
		except Exception as exc:
			err = str(exc)
			if "400" in err:
				reply = "[ WARNING ] Model hien tai khong ho tro tool calling."
			elif "401" in err:
				reply = "[ WARNING ] API key khong hop le. Vui long kiem tra file .env."
			else:
				reply = f"[ WARNING ] Loi: {exc}"
			print(f"[Telegram] Error: {exc}")

		try:
			await update.message.reply_text(reply)
		except Exception as send_err:
			if "timeout" in str(send_err).lower():
				try:
					await asyncio.sleep(1)
					await update.message.reply_text(reply)
				except Exception:
					print("[Telegram] Failed to send reply after retry")
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
		app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
		app.add_handler(CommandHandler("start", self.cmd_start))
		app.add_handler(CommandHandler("reset", self.cmd_reset))
		app.add_handler(CommandHandler("status", self.cmd_status))
		app.add_handler(
			MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message),
		)
		self.app = app

		# Start background anomaly monitoring (5-second interval)
		app.job_queue.run_repeating(self.monitor_anomalies, interval=5.0, first=1.0)

		app.run_polling()
