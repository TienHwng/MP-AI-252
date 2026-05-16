"""Deterministic fallback response composition for HERA.

Primary natural-language composition should come from the configured LLM.
This module only formats truthful fallback text when a runtime/service result
must be returned without another model call.
"""

from __future__ import annotations

from core.message import AgentResponse

from .text_utils import clean_user_visible_text, looks_vietnamese


class ResponseComposer:
	"""Owns compact non-LLM fallback rendering."""

	def render_device_control_text(self, user_text: str, payload: dict) -> str:
		visible = payload.get("user_visible_message")
		if isinstance(visible, str) and visible.strip():
			return clean_user_visible_text(visible)

		prefer_vi = looks_vietnamese(user_text)
		status = str(payload.get("status") or "").lower()
		capability = str(payload.get("capability_name") or "")

		if status == "ask":
			return (
				"Mình cần bạn xác nhận trước khi điều khiển nhóm thiết bị này."
				if prefer_vi
				else "Please confirm before I control this device group."
			)
		if status in {"denied", "blocked"}:
			return (
				"Mình chưa thực hiện lệnh vì yêu cầu không được policy cho phép."
				if prefer_vi
				else "I did not execute the request because policy blocked it."
			)
		if capability == "get_device_status":
			return self._render_device_status(payload, prefer_vi)

		ok = payload.get("ok")
		target = payload.get("target") or payload.get("device") or "device"
		if ok is False or status in {"failed", "error"}:
			return (
				f"Mình chưa điều khiển được {target}."
				if prefer_vi
				else f"I could not control {target}."
			)
		return (
			f"Đã xử lý yêu cầu cho {target}."
			if prefer_vi
			else f"Processed the request for {target}."
		)

	def render_device_specialist_fallback_text(
		self,
		user_text: str,
		specialist_response: AgentResponse,
	) -> str:
		report = self._report(specialist_response)
		question = report.get("clarification_question")
		if isinstance(question, str) and question.strip():
			return clean_user_visible_text(question)

		payload = self._payload(report)
		if report.get("summary") == "awaiting_target_clarification":
			return self._render_target_choice(payload, looks_vietnamese(user_text))
		condition = payload.get("condition") or payload.get("condition_result")
		prefer_vi = looks_vietnamese(user_text)
		if isinstance(condition, dict):
			status = condition.get("status")
			if status == "not_met":
				return (
					"Điều kiện chưa đạt nên mình chưa gửi lệnh điều khiển."
					if prefer_vi
					else "The condition was not met, so no device command was sent."
				)
			if status in {"unknown", "unavailable"}:
				return (
					"Mình chưa đủ dữ liệu để kiểm tra điều kiện, nên chưa gửi lệnh điều khiển."
					if prefer_vi
					else "I do not have enough data to check the condition, so no device command was sent."
				)

		text = clean_user_visible_text(specialist_response.text)
		if text:
			return text
		return (
			"Mình cần bạn chọn một mục cụ thể trong nhà."
			if prefer_vi
			else "Please choose a specific home device."
		)

	def render_sensor_text(
		self,
		user_text: str,
		specialist_response: AgentResponse,
	) -> str:
		report = self._report(specialist_response)
		payload = self._payload(report)
		snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
		if not isinstance(snapshot, dict):
			snapshot = payload if isinstance(payload, dict) else {}
		if isinstance(snapshot.get("sensors"), dict):
			snapshot = snapshot["sensors"]

		readings = []
		for key in ("temperature", "humidity", "light", "soil_moisture"):
			value = snapshot.get(key)
			if value is None:
				continue
			readings.append(f"{key}: {value}")
		if readings:
			prefix = "Telemetry hiện tại" if looks_vietnamese(user_text) else "Current telemetry"
			return f"{prefix}: " + "; ".join(readings) + "."

		text = clean_user_visible_text(specialist_response.text)
		if text:
			return text
		return (
			"Chưa có dữ liệu telemetry hiện tại."
			if looks_vietnamese(user_text)
			else "Current telemetry is unavailable."
		)

	def render_anomaly_text(
		self,
		user_text: str,
		specialist_response: AgentResponse,
	) -> str:
		report = self._report(specialist_response)
		payload = self._payload(report)
		classification = payload.get("classification")
		if isinstance(classification, dict):
			kind = classification.get("type") or "unknown"
			severity = classification.get("severity") or "unknown"
			score = classification.get("score")
			detail = classification.get("detail")
			parts = [f"type={kind}", f"severity={severity}"]
			if score is not None:
				parts.append(f"score={score}")
			if detail:
				parts.append(str(detail))
			prefix = "Trạng thái bất thường" if looks_vietnamese(user_text) else "Anomaly status"
			return f"{prefix}: " + "; ".join(parts) + "."

		text = clean_user_visible_text(specialist_response.text)
		if text:
			return text
		return (
			"Chưa có đủ dữ liệu để kết luận bất thường."
			if looks_vietnamese(user_text)
			else "There is not enough data to classify anomalies."
		)

	@staticmethod
	def _report(response: AgentResponse) -> dict:
		report = response.metadata.get("specialist_report")
		return report if isinstance(report, dict) else {}

	@staticmethod
	def _payload(report: dict) -> dict:
		payload = report.get("analysis_payload")
		return payload if isinstance(payload, dict) else {}

	@staticmethod
	def _render_device_status(payload: dict, prefer_vi: bool) -> str:
		state = payload.get("after_state") or payload.get("raw_result")
		if not isinstance(state, dict):
			target = payload.get("target") or "device"
			return (
				f"Chưa đọc được trạng thái của {target}."
				if prefer_vi
				else f"Could not read the status of {target}."
			)
		items = []
		for name, value in sorted(state.items()):
			if isinstance(value, dict):
				value = value.get("state") or value.get("status") or value.get("value")
			items.append(f"{name}: {value}")
		prefix = "Trạng thái thiết bị" if prefer_vi else "Device status"
		return f"{prefix}: " + "; ".join(items) + "."

	@staticmethod
	def _render_target_choice(payload: dict, prefer_vi: bool) -> str:
		options = payload.get("available_targets")
		if not isinstance(options, list):
			options = []
		labels = []
		for option in options:
			if not isinstance(option, dict):
				continue
			label = option.get("label")
			if isinstance(label, str) and label.strip():
				labels.append(label.strip())
		if labels:
			joined = ", ".join(labels[:5])
			return (
				f"Bạn muốn chọn mục nào: {joined}?"
				if prefer_vi
				else f"Which one should I use: {joined}?"
			)
		return (
			"Mình cần bạn chọn một mục cụ thể trong nhà."
			if prefer_vi
			else "Please choose a specific home device."
		)
