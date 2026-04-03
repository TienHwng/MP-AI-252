import requests

# === FILL YOUR INFORMATION HERE ===
BOT_TOKEN = "8317438578:AAHKIEMK2IIlGtHIeNVTLiudOSJteWTVB2U"
CHAT_ID = "-1003308447409"  # can be a user id or a group id
# ==================================


def send_telegram_message(chat_id: str, text: str) -> None:
    """
    Send a text message to the given chat_id via Telegram Bot API.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2"  # enable this if you want **bold**, _italic_, ...
    }

    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ Message sent successfully!")
            print("Telegram response:", response.json())
        else:
            print("❌ Error while sending message")
            print("Status code:", response.status_code)
            print("Response body:", response.text)
    except requests.RequestException as e:
        print("🚨 Connection error:", e)


if __name__ == "__main__":
    # The message you want to test
    # message = "Hello! This is a test message from Python 🐍"
    message = "*Humid alert*: _percentage is too high\\!\\!\\!_"

    print("Sending message to Telegram...")
    send_telegram_message(CHAT_ID, message)
