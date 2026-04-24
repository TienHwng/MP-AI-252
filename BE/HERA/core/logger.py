"""
HERA Structured Logger
======================
Thread-safe, per-request structured logging with colored output.
Each request gets a short trace ID so you can grep/follow one
conversation turn across every layer of the system.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

# ── ANSI colour codes (auto-disabled on non-TTY) ──────────────

_COLORS = {
	"cyan": "\033[96m",
	"green": "\033[92m",
	"yellow": "\033[93m",
	"magenta": "\033[95m",
	"blue": "\033[94m",
	"red": "\033[91m",
	"dim": "\033[2m",
	"bold": "\033[1m",
	"reset": "\033[0m",
}

LAYER_COLORS: dict[str, str] = {
	"GRAPH": "cyan",
	"ORCH": "green",
	"ROUTE": "yellow",
	"MEMORY": "blue",
	"AGENT": "magenta",
	"LLM": "cyan",
	"RUNTIME": "yellow",
	"POLICY": "blue",
	"EXEC": "green",
	"VERIFY": "green",
	"COMPOSE": "magenta",
	"MQTT": "cyan",
	"TELEGRAM": "blue",
	"TELEMETRY": "dim",
	"ALERT": "red",
	"HERA": "bold",
}


def _c(color_key: str, text: str) -> str:
	"""Wrap *text* in ANSI colour."""
	return f"{_COLORS.get(color_key, '')}{text}{_COLORS['reset']}"


# ── Trace context (per-request) ───────────────────────────────


@dataclass
class TraceContext:
	"""Lightweight bag of per-request metadata."""

	trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
	start_time: float = field(default_factory=time.perf_counter)
	extras: dict[str, Any] = field(default_factory=dict)

	@property
	def elapsed_ms(self) -> float:
		return (time.perf_counter() - self.start_time) * 1000


_current_trace: ContextVar[TraceContext | None] = ContextVar(
	"_current_trace",
	default=None,
)


def get_trace() -> TraceContext | None:
	return _current_trace.get()


@contextmanager
def trace_scope(**extras):
	"""
	Usage::

	    with trace_scope(user="Tran", chat_id="12345"):
	        await orchestrator.handle(msg)
	"""
	ctx = TraceContext(extras=extras)
	token = _current_trace.set(ctx)
	try:
		yield ctx
	finally:
		_current_trace.reset(token)


# ── Core log function ─────────────────────────────────────────


def hera_log(
	layer: str,
	message: str,
	*,
	detail: str | None = None,
	data: dict[str, Any] | None = None,
	trace: TraceContext | None = None,
) -> None:
	"""
	Print a structured, coloured log line.

	Parameters
	----------
	layer   : one of LAYER_COLORS keys (e.g. "ORCH", "LLM", "POLICY")
	message : short human-readable summary
	detail  : optional second line with extra context
	data    : optional key=value pairs appended inline
	trace   : override auto-detected trace context
	"""
	trace = trace or get_trace()

	color = LAYER_COLORS.get(layer, "dim")
	tag = _c(color, f"[{layer}]")
	trace_tag = ""
	if trace is not None:
		elapsed = f"{trace.elapsed_ms:,.0f}ms"
		trace_tag = _c("dim", f" [{trace.trace_id} +{elapsed}]")

	# Build inline data string
	data_str = ""
	if data:
		pairs = " ".join(f"{k}={v}" for k, v in data.items())
		data_str = _c("dim", f"  ({pairs})")

	print(f"{tag}{trace_tag} {message}{data_str}")

	if detail:
		indent = "  "
		print(f"{_c('dim', indent + '|')} {detail}")


# ── Convenience helpers per-layer ─────────────────────────────


def log_graph(msg: str, **kw):
	hera_log("GRAPH", msg, **kw)


def log_orch(msg: str, **kw):
	hera_log("ORCH", msg, **kw)


def log_route(msg: str, **kw):
	hera_log("ROUTE", msg, **kw)


def log_memory(msg: str, **kw):
	hera_log("MEMORY", msg, **kw)


def log_agent(msg: str, **kw):
	hera_log("AGENT", msg, **kw)


def log_llm(msg: str, **kw):
	hera_log("LLM", msg, **kw)


def log_runtime(msg: str, **kw):
	hera_log("RUNTIME", msg, **kw)


def log_policy(msg: str, **kw):
	hera_log("POLICY", msg, **kw)


def log_exec(msg: str, **kw):
	hera_log("EXEC", msg, **kw)


def log_verify(msg: str, **kw):
	hera_log("VERIFY", msg, **kw)


def log_compose(msg: str, **kw):
	hera_log("COMPOSE", msg, **kw)


def log_mqtt(msg: str, **kw):
	hera_log("MQTT", msg, **kw)


def log_telegram(msg: str, **kw):
	hera_log("TELEGRAM", msg, **kw)


def log_telemetry(msg: str, **kw):
	hera_log("TELEMETRY", msg, **kw)


def log_alert(msg: str, **kw):
	hera_log("ALERT", msg, **kw)


def log_hera(msg: str, **kw):
	hera_log("HERA", msg, **kw)
