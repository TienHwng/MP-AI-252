"""
Lightweight async event bus for inter-agent / proactive alert communication.

Usage
-----
    bus = EventBus()
    bus.subscribe("anomaly_detected", my_handler)
    await bus.publish("anomaly_detected", {"score": 0.85})
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine


EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    def __init__(self) -> None:
        self.handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event: str, handler: EventHandler) -> None:
        self.handlers[event].append(handler)

    async def publish(self, event: str, data: Any = None) -> None:
        for handler in self.handlers.get(event, []):
            try:
                await handler(data)
            except Exception as exc:
                print(f"[EventBus] handler error on '{event}': {exc}")
