"""Evaluate HERA AI agents through the local HTTP adapter.

Start backend/HERA/api_server.py first. Run once with local Ollama settings and once
with cloud/OpenRouter settings, using --provider-label to separate the results.

Example:
    python docs/evaluation/ai_agent_eval.py --provider-label ollama-local
    python docs/evaluation/ai_agent_eval.py --provider-label openrouter-cloud
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import requests

try:
	sys.stdout.reconfigure(encoding="utf-8")
except Exception:
	pass


def percentile(values: list[float], pct: float) -> float | None:
	if not values:
		return None
	ordered = sorted(values)
	index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
	return ordered[index]


def load_cases(path: Path) -> list[dict]:
	cases = []
	for line in path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if line:
			cases.append(json.loads(line))
	return cases


def tool_success(payload: dict, expected_tools: list[str]) -> tuple[bool, str]:
	if not expected_tools:
		return True, "not_applicable"
	metadata = payload.get("metadata") or {}
	results = metadata.get("tool_execution_results") or []
	seen_ok = set()
	for result in results:
		name = result.get("capability_name") or result.get("tool") or result.get("name")
		if result.get("ok") is not False:
			seen_ok.add(name)
	missing = [name for name in expected_tools if name not in seen_ok]
	return not missing, ",".join(missing) if missing else "ok"


def get_settings(base_url: str, timeout_sec: float) -> dict:
	response = requests.get(f"{base_url}/api/settings/models", timeout=timeout_sec)
	response.raise_for_status()
	payload = response.json()
	return payload if isinstance(payload, dict) else {}


def set_provider(base_url: str, provider: str, timeout_sec: float) -> dict:
	current = get_settings(base_url, timeout_sec)
	payload = {
		"provider": provider,
		"models": current.get("models", {}),
	}
	response = requests.put(
		f"{base_url}/api/settings/models",
		json=payload,
		timeout=timeout_sec,
	)
	response.raise_for_status()
	return response.json()


def main() -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--base-url", default="http://localhost:3002")
	parser.add_argument("--cases", default="docs/evaluation/ai_agent_cases.jsonl")
	parser.add_argument("--provider-label", default="current")
	parser.add_argument(
		"--set-provider",
		choices=["ollama", "openrouter"],
		help="Switch HERA runtime provider before running the benchmark.",
	)
	parser.add_argument("--repeat", type=int, default=1)
	parser.add_argument("--timeout-sec", type=float, default=60)
	parser.add_argument("--out-dir", default="docs/evaluation/results")
	args = parser.parse_args()

	out_dir = Path(args.out_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	rows_path = out_dir / f"ai_agent_eval_{args.provider_label}.csv"
	summary_path = out_dir / f"ai_agent_eval_{args.provider_label}_summary.json"
	cases = load_cases(Path(args.cases))
	if args.set_provider:
		set_provider(args.base_url, args.set_provider, args.timeout_sec)
		time.sleep(1.0)

	rows = []
	for repeat_index in range(args.repeat):
		for case in cases:
			start = time.perf_counter()
			try:
				response = requests.post(
					f"{args.base_url}/api/assistant/message",
					json={
						"text": case["text"],
						"user_id": "eval_user",
						"session_id": f"eval_{args.provider_label}_{repeat_index}",
					},
					timeout=args.timeout_sec,
				)
				latency_ms = (time.perf_counter() - start) * 1000
				try:
					payload = response.json()
				except ValueError:
					payload = {
						"ok": False,
						"error": "non_json_response",
						"message": response.text[:500],
						"metadata": {},
					}
				http_ok = response.ok and payload.get("ok") is not False
			except Exception as exc:
				latency_ms = (time.perf_counter() - start) * 1000
				payload = {"ok": False, "error": exc.__class__.__name__, "message": str(exc), "metadata": {}}
				http_ok = False

			metadata = payload.get("metadata") or {}
			predicted_intent = metadata.get("intent")
			intent_correct = predicted_intent == case["expected_intent"]
			expected_tools = case.get("expected_tools") or []
			tools_ok, tool_detail = tool_success(payload, expected_tools)

			rows.append(
				{
					"provider": args.provider_label,
					"repeat": repeat_index,
					"case_id": case["id"],
					"text": case["text"],
					"expected_intent": case["expected_intent"],
					"predicted_intent": predicted_intent or "",
					"intent_correct": intent_correct,
					"expected_tools": ",".join(expected_tools),
					"tools_ok": tools_ok,
					"tool_detail": tool_detail,
					"http_ok": http_ok,
					"latency_ms": round(latency_ms, 3),
					"agent_name": payload.get("agent_name", ""),
					"tools_used": ",".join(payload.get("tools_used") or []),
					"error": payload.get("error", ""),
					"message": str(payload.get("message", ""))[:240],
				}
			)
			print(json.dumps(rows[-1], ensure_ascii=False))

	with rows_path.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
		writer.writeheader()
		writer.writerows(rows)

	latencies = [row["latency_ms"] for row in rows if row["http_ok"]]
	intent_total = len(rows)
	intent_correct = sum(1 for row in rows if row["intent_correct"])
	tool_rows = [row for row in rows if row["expected_tools"]]
	tool_ok = sum(1 for row in tool_rows if row["tools_ok"])
	summary = {
		"provider": args.provider_label,
		"cases": len(cases),
		"runs": len(rows),
		"intent_accuracy_percent": round(intent_correct / intent_total * 100, 2) if intent_total else 0,
		"tool_call_success_percent": round(tool_ok / len(tool_rows) * 100, 2) if tool_rows else None,
		"http_success_percent": round(sum(1 for row in rows if row["http_ok"]) / len(rows) * 100, 2) if rows else 0,
		"latency_ms": {
			"mean": round(statistics.mean(latencies), 3) if latencies else None,
			"median": round(statistics.median(latencies), 3) if latencies else None,
			"p95": round(percentile(latencies, 95), 3) if latencies else None,
			"min": round(min(latencies), 3) if latencies else None,
			"max": round(max(latencies), 3) if latencies else None,
		},
	}
	summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
	print(json.dumps(summary, indent=2))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
