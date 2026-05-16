#!/usr/bin/env python3
"""
Ollama LLM test script with STREAMING response.
Shows response in real-time as it's being generated.

Usage:
    python test_ollama_streaming.py
"""

import requests
import json
import sys

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"


def call_ollama_streaming(prompt: str, model: str = MODEL) -> str:
	"""
	Call Ollama with streaming enabled.
	Shows response in real-time.
	"""
	print(f"\n{'=' * 60}")
	print(f"📌 Model: {model}")
	print(f"❓ Prompt: {prompt}")
	print(f"{'=' * 60}\n")

	payload = {
		"model": model,
		"prompt": prompt,
		"stream": True,  # Enable streaming
		"temperature": 0.7,
	}

	try:
		print("🤖 Response:\n")
		full_response = ""

		response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=120)

		if response.status_code != 200:
			print(f"❌ Error: {response.status_code}")
			print(response.text)
			return None

		# Stream response line by line
		for line in response.iter_lines():
			if line:
				data = json.loads(line)
				chunk = data.get("response", "")
				full_response += chunk

				# Print chunk without newline for real-time effect
				print(chunk, end="", flush=True)

				# If this is the last chunk, print stats
				if data.get("done", False):
					print("\n")
					eval_count = data.get("eval_count", 0)
					eval_duration = data.get("eval_duration", 0) / 1e9
					print(f"\n✅ Done!")
					print(f"   Tokens: {eval_count} | Time: {eval_duration:.2f}s")

		return full_response

	except requests.exceptions.ConnectionError:
		print("\n❌ Cannot connect to Ollama!")
		print("   Start Ollama with: ollama serve")
		return None
	except Exception as e:
		print(f"\n❌ Error: {str(e)}")
		return None


def main():
	print("\n" + "=" * 60)
	print("🚀 OLLAMA STREAMING TEST".center(60))
	print("=" * 60)

	prompts = [
		"Hãy giải thích cách hoạt động của IoT smart home thiết bị.",
		# "Write a short poem about artificial intelligence in 5 lines",
		# "Tính 2+2 và giải thích từng bước",
	]

	for prompt in prompts:
		response = call_ollama_streaming(prompt)
		if response:
			print("-" * 60)

	print("\n✅ All tests completed!\n")


if __name__ == "__main__":
	main()
