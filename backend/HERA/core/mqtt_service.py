"""
MQTT Service
=============
Thin wrapper around paho-mqtt providing:
  - Connection management with auto-reconnect
  - Sensor state aggregation from telemetry / attributes topics
  - RPC publishing helpers
"""

from __future__ import annotations

import json
from datetime import datetime
from threading import Lock

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT,
    TOPIC_TELEMETRY, TOPIC_ATTRIBUTES, TOPIC_RPC_REQUEST,
)


class MQTTService:
    """Singleton-style service — create once, inject everywhere."""

    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._rpc_counter = 0
        self._rpc_lock = Lock()

        # Shared sensor snapshot updated from MQTT callbacks
        self.sensor_state: dict = {
            "temperature": None,
            "humidity": None,
            "inference_result": None,
            "led_state": None,
            "neo_led_state": None,
            "last_updated": None,
        }

    # ── lifecycle ─────────────────────────────────────────────

    def connect(self) -> None:
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, "HERA_Bot",
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(MQTT_BROKER, MQTT_PORT)
        self._client.loop_start()

    def disconnect(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    # ── callbacks ─────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(TOPIC_TELEMETRY)
            client.subscribe(TOPIC_ATTRIBUTES)
            print("[MQTT] Connected to broker")
        else:
            print(f"[MQTT] Connection failed (rc={rc})")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
        except Exception as exc:
            print(f"[MQTT] Parse error: {exc}")
            return

        if msg.topic == TOPIC_TELEMETRY:
            for key in ("temperature", "humidity", "inference_result",
                        "led_state", "neo_led_state"):
                if key in data:
                    self.sensor_state[key] = data[key]
            self.sensor_state["last_updated"] = (
                datetime.now().strftime("%H:%M:%S")
            )
        elif msg.topic == TOPIC_ATTRIBUTES:
            if "LedState" in data:
                self.sensor_state["led_state"] = data["LedState"]
            if "NeoLedState" in data:
                self.sensor_state["neo_led_state"] = data["NeoLedState"]

    # ── public helpers ────────────────────────────────────────

    def publish_rpc(self, method: str, params) -> None:
        """Send an RPC command to the device over MQTT."""
        with self._rpc_lock:
            self._rpc_counter += 1
            rid = self._rpc_counter
        payload = json.dumps({"method": method, "params": params})
        self._client.publish(f"{TOPIC_RPC_REQUEST}{rid}", payload)

    def get_sensor_snapshot(self) -> dict:
        """Return a *copy* of the current sensor state."""
        return dict(self.sensor_state)
