#!/usr/bin/env python3
"""Test Ollama LLM with thinking chain support."""

import requests
import json
import sys

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.5:0.8B"

test_prompts = [
	"Giải thích cách để hạ nhiệt độ phòng trong mùa hè?",
	"What are the benefits of using smart home devices?",
	"Viết 1 bài hát ngắn về IoT",
]


def call_ollama(prompt: str, model: str = MODEL, show_thinking: bool = False):
	"""Call Ollama LLM with streaming response."""

	print(f"\n[Model: {model}]")
	print(f"[Prompt: {prompt}]")
	print(f"[Thinking: {'ON' if show_thinking else 'OFF'}]\n")

	payload = {
		"model": model,
		"messages": [{"role": "user", "content": prompt}],
		"stream": True,
		"think": show_thinking,  # True to enable thinking, False to disable
		"temperature": 0.7,
	}

	try:
		response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120)

		if response.status_code != 200:
			print(f"Error: {response.status_code}")
			print(response.text)
			return None

		thinking_text = ""
		response_text = ""
		first_thinking = True

		for line in response.iter_lines():
			if line:
				data = json.loads(line)

				if "message" in data:
					msg = data["message"]

					# Handle thinking chunks
					if "thinking" in msg and msg["thinking"]:
						if first_thinking and show_thinking:
							print("[THINKING]")
							first_thinking = False
						thinking_text += msg["thinking"]
						sys.stdout.write(msg["thinking"])
						sys.stdout.flush()

					# Handle content chunks
					if "content" in msg and msg["content"]:
						if thinking_text and show_thinking:
							print("\n\n[RESPONSE]")
							thinking_text = ""  # Reset to avoid duplicate print
						response_text += msg["content"]
						sys.stdout.write(msg["content"])
						sys.stdout.flush()

		print("\n")
		return response_text

	except requests.exceptions.ConnectionError:
		print("Error: Cannot connect to Ollama")
		print("Start Ollama: ollama serve")
		return None
	except Exception as e:
		print(f"Error: {e}")
		return None


def main():
	print("\nOLLAMA TEST - Thinking Chain Support\n")
	print(f"Model: {MODEL}")
	print(f"URL: {OLLAMA_URL}\n")

	# Test 1: Without thinking

	print("TEST 1: Without thinking (faster)")

	call_ollama(test_prompts[0], show_thinking=False)

	# Test 2: With thinking (if you want to see reasoning)

	print("TEST 2: With thinking enabled (slower, shows reasoning)")

	# Uncomment to test with thinking:
	call_ollama(test_prompts[0], show_thinking=True)


if __name__ == "__main__":
	main()
