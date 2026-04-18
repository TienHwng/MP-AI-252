import requests
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

# === FILL YOUR INFORMATION HERE ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # can be a user id or a group id
# ==================================


def send_telegram_message(chat_id: str, text: str) -> None:
	"""
	Send a text message to the given chat_id via Telegram Bot API.
	"""
	url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
	data = {
		"chat_id": chat_id,
		"text": text,
		"parse_mode": "MarkdownV2",  # enable this if you want **bold**, _italic_, ...
	}

	try:
		response = requests.post(url, data=data, timeout=10)
		if response.status_code == 200:
			print("[ OK ] Message sent successfully!")
			print("Telegram response:", response.json())
		else:
			print("[ ERROR ] Error while sending message")
			print("Status code:", response.status_code)
			print("Response body:", response.text)
	except requests.RequestException as e:
		print("[ WARNING ] Connection error:", e)


if __name__ == "__main__":
	if not BOT_TOKEN or not CHAT_ID:
		raise RuntimeError(
			"TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env"
		)
	# The message you want to test
	# message = "Hello! This is a test message from Python [ INFO ]"
	message = "*Humid alert*: _percentage is too high\\!\\!\\!_"

	print("Sending message to Telegram...")
	send_telegram_message(CHAT_ID, message)
