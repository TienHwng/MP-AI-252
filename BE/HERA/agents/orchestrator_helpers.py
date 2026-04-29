"""Helpers for orchestrator fast-path routing and user-facing rendering."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from core.message import AgentResponse
from telemetry import device_status, sensor_value


def clean_user_visible_text(text: str) -> str:
	"""Keep LLM replies as plain Telegram text."""
	cleaned = (text or "").strip()
	if not cleaned:
		return cleaned
	cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
	cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
	cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
	cleaned = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", cleaned)
	cleaned = re.sub(r"(?m)^\s*[-*+]\s+", "", cleaned)
	cleaned = re.sub(r"(?m)^\s*\d+\.\s+", "", cleaned)
	cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
	return cleaned.strip()


def format_timestamp(value: str | None) -> str | None:
	if not value:
		return None
	try:
		dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=UTC)
		local_dt = dt.astimezone()
		return local_dt.strftime("%H:%M:%S %d/%m/%Y")
	except ValueError:
		return value


def looks_vietnamese(text: str) -> bool:
	normalized = text.lower()
	vietnamese_chars = (
		"àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ"
	)
	markers = (
		"đ",
		"ă",
		"â",
		"ê",
		"ô",
		"ơ",
		"ư",
		"bật",
		"tắt",
		"đèn",
		"thiết bị",
		"giùm",
		"giúp",
		"xác nhận",
		"xin chào",
		"tìm",
		"kiếm",
		"mới nhất",
		"về",
	)
	return any(char in normalized for char in vietnamese_chars) or any(
		marker in normalized for marker in markers
	)


def format_entity_list(items: list[str], prefer_vietnamese: bool) -> str:
	if not items:
		return ""
	if len(items) == 1:
		return items[0]
	if len(items) == 2:
		joiner = " và " if prefer_vietnamese else " and "
		return f"{items[0]}{joiner}{items[1]}"
	last_joiner = ", và " if prefer_vietnamese else ", and "
	return ", ".join(items[:-1]) + last_joiner + items[-1]


def action_label(capability_name: str, prefer_vietnamese: bool) -> str:
	labels = {
		"set_device_value": ("cai", "set"),
		"set_sensor_value": ("cai", "set"),
		"turn_on_device": ("bật", "turn on"),
		"turn_off_device": ("tắt", "turn off"),
		"get_device_status": ("kiểm tra trạng thái", "check the status of"),
	}
	vi, en = labels.get(capability_name, ("điều khiển", "control"))
	return vi if prefer_vietnamese else en


def requested_action_text(action: str, prefer_vietnamese: bool) -> str:
	labels = {
		"turn_on": ("bật", "turn something on"),
		"turn_off": ("tắt", "turn something off"),
		"status": ("kiểm tra trạng thái", "check the status"),
	}
	vi, en = labels.get(action, ("điều khiển", "control something"))
	return vi if prefer_vietnamese else en


def render_device_control_text(user_text: str, payload: dict) -> str:
	prefer_vietnamese = looks_vietnamese(user_text)
	status = str(payload.get("status") or "")
	reason = str(payload.get("reason") or "")
	capability_name = str(payload.get("capability_name") or "")
	user_visible_message = payload.get("user_visible_message")
	policy_reason = str(payload.get("policy_reason") or "")
	changed_entities = [
		str(item) for item in payload.get("changed_entities", []) if item is not None
	]
	unchanged_entities = [
		str(item) for item in payload.get("unchanged_entities", []) if item is not None
	]
	failed_entities = [
		str(item) for item in payload.get("failed_entities", []) if item is not None
	]
	target = payload.get("target")
	after_state = payload.get("after_state")
	verification_status = str(payload.get("verification_status") or "")

	if status == "pending_cancelled":
		return (
			"Đã hủy yêu cầu trước đó."
			if prefer_vietnamese
			else "The previous pending request has been cancelled."
		)
	if status == "pending_unclear":
		return (
			"Yêu cầu trước đó vẫn đang chờ xác nhận. Bạn có thể xác nhận hoặc hủy."
			if prefer_vietnamese
			else "The previous request is still waiting for confirmation. You can confirm or cancel it."
		)
	if status == "ask":
		if policy_reason == "broad_all_devices_scope_requires_confirmation":
			return (
				"Vui lòng xác nhận trước khi điều khiển tất cả các thiết bị được hỗ trợ cùng một lúc."
				if prefer_vietnamese
				else "Please confirm before controlling every supported device at once."
			)
		if user_visible_message:
			return str(user_visible_message)
		return (
			"Bạn muốn điều khiển thiết bị nào?"
			if prefer_vietnamese
			else "Which device should I control?"
		)
	if status == "deny":
		if user_visible_message:
			return str(user_visible_message)
		return (
			"Tôi không thể thực hiện yêu cầu này vào lúc này."
			if prefer_vietnamese
			else "I cannot complete that request right now."
		)
	if status == "noop" or reason in {"already_in_requested_state", "already_in_requested_value"}:
		if user_visible_message and not prefer_vietnamese:
			return str(user_visible_message)
		if reason == "already_in_requested_value":
			return (
				"Gia tri da o muc ban yeu cau."
				if prefer_vietnamese
				else "The value is already set as requested."
			)
		return (
			"Thiết bị đã ở trạng thái bạn yêu cầu."
			if prefer_vietnamese
			else "The device is already in the requested state."
		)
	if (
		capability_name == "get_device_status" or reason == "status_requested"
	) and isinstance(after_state, dict):
		if isinstance(target, str) and target in after_state:
			state = after_state.get(target)
			state_text = (
				(
					"đang bật"
					if state is True
					else "đang tắt"
					if state is False
					else "không rõ"
				)
				if prefer_vietnamese
				else (
					"is on"
					if state is True
					else "is off"
					if state is False
					else "is unknown"
				)
			)
			return (
				f"Thiết bị {target} hiện {state_text}."
				if prefer_vietnamese
				else f"The device {target} {state_text}."
			)
		on_devices = [name for name, state in after_state.items() if state is True]
		off_devices = [name for name, state in after_state.items() if state is False]
		return (
			f"Đang bật: {format_entity_list(on_devices, True) or 'không có'}. "
			f"Đang tắt: {format_entity_list(off_devices, True) or 'không có'}."
			if prefer_vietnamese
			else f"On: {format_entity_list(on_devices, False) or 'none'}. Off: {format_entity_list(off_devices, False) or 'none'}."
		)
	label = action_label(capability_name, prefer_vietnamese)
	target_list = format_entity_list(changed_entities, prefer_vietnamese)
	if capability_name in {"set_device_value", "set_sensor_value"}:
		if changed_entities and verification_status == "verified":
			return (
				f"Da cai {target_list}."
				if prefer_vietnamese
				else f"I set {target_list}."
			)
		if changed_entities:
			return (
				f"Toi da gui lenh cai {target_list}, nhung chua xac minh duoc gia tri cuoi cung."
				if prefer_vietnamese
				else f"I sent the command to set {target_list}, but I could not verify the final value yet."
			)
	if changed_entities and verification_status == "verified":
		return (
			f"Đã {label} {target_list}."
			if prefer_vietnamese
			else f"I have {label} {target_list}."
		)
	if changed_entities:
		return (
			f"Tôi đã gửi lệnh {label} {target_list}, nhưng chưa xác minh được trạng thái cuối cùng."
			if prefer_vietnamese
			else f"I sent the command to {label} {target_list}, but I could not verify the final state yet."
		)
	if unchanged_entities:
		target_list = format_entity_list(unchanged_entities, prefer_vietnamese)
		return (
			f"{target_list} đã ở trạng thái yêu cầu."
			if prefer_vietnamese
			else f"{target_list} were already in the requested state."
		)
	if failed_entities:
		target_list = format_entity_list(failed_entities, prefer_vietnamese)
		return (
			f"Tôi chưa thể xử lý yêu cầu cho {target_list}."
			if prefer_vietnamese
			else f"I could not complete the request for {target_list}."
		)
	return (
		"Yêu cầu đã được xử lý."
		if prefer_vietnamese
		else "The request has been processed."
	)


def render_device_specialist_fallback_text(
	user_text: str,
	specialist_response: AgentResponse,
) -> str:
	prefer_vietnamese = looks_vietnamese(user_text)
	raw_report = specialist_response.metadata.get("specialist_report")
	report = raw_report if isinstance(raw_report, dict) else {}
	summary = str(report.get("summary") or "")
	question = report.get("clarification_question")
	analysis_payload = report.get("analysis_payload", {})
	if not isinstance(analysis_payload, dict):
		analysis_payload = {}
	parsed_command = analysis_payload.get("parsed_command", {})
	if not isinstance(parsed_command, dict):
		parsed_command = {}
	condition = parsed_command.get("condition")
	if isinstance(condition, dict):
		status = condition.get("status")
		label = condition.get("sensor_label") or condition.get("sensor") or "điều kiện"
		current = condition.get("current_value")
		operator = condition.get("operator")
		threshold = condition.get("threshold")
		unit = condition.get("unit") or ""
		if condition.get("type") == "sensor_window_threshold":
			window_seconds = condition.get("window_seconds")
			observed = condition.get("observed_value")
			observed_key = condition.get("observed_key")
			window_text = (
				f"{window_seconds} giây gần đây"
				if isinstance(window_seconds, int | float)
				else "cửa sổ telemetry gần đây"
			)
			observed_label = "cao nhất" if observed_key == "max" else "thấp nhất"
			if status == "not_met":
				return (
					f"Mình đã kiểm tra {label} trong {window_text}: giá trị {observed_label} là {observed}{unit}, chưa {operator} {threshold}{unit}, nên mình chưa gửi lệnh điều khiển."
					if prefer_vietnamese
					else f"I checked {label} over the last {window_seconds} seconds: the {observed_key} value was {observed}{unit}, not {operator} {threshold}{unit}, so I did not send the device command."
				)
			if status == "unknown":
				return (
					f"Mình chưa đủ dữ liệu telemetry để kiểm tra {label} trong {window_text}, nên mình chưa gửi lệnh điều khiển."
					if prefer_vietnamese
					else f"I do not have enough telemetry to check {label} over that window, so I did not send the device command."
				)
		if status == "not_met":
			return (
				f"Mình đã kiểm tra {label}: hiện là {current}{unit}, chưa {operator} {threshold}{unit}, nên chưa gửi lệnh điều khiển."
				if prefer_vietnamese
				else f"I checked {label}: it is {current}{unit}, not {operator} {threshold}{unit}, so I did not send the device command."
			)
		if status == "unknown":
			return (
				f"Mình chưa đủ dữ liệu để kiểm tra điều kiện {label}, nên chưa gửi lệnh điều khiển."
				if prefer_vietnamese
				else f"I do not have enough data to check {label}, so I did not send the device command."
			)
	requested_action = parsed_command.get("requested_action") or parsed_command.get(
		"action"
	)
	if summary == "awaiting_target_clarification" and question:
		return str(question)
	if requested_action in {"turn_on", "turn_off", "status"}:
		action_text = requested_action_text(str(requested_action), prefer_vietnamese)
		return (
			f"Tôi hiểu bạn muốn {action_text}, nhưng chưa xác định được thiết bị cụ thể."
			if prefer_vietnamese
			else f"I understand you want to {action_text}, but I still do not know which specific device you mean."
		)
	return (
		"Tôi chưa hiểu rõ bạn muốn điều khiển thiết bị nào."
		if prefer_vietnamese
		else "I am not sure which device you want to control."
	)


def render_sensor_text(user_text: str, specialist_response: AgentResponse) -> str:
	prefer_vietnamese = looks_vietnamese(user_text)
	raw_report = specialist_response.metadata.get("specialist_report")
	report = raw_report if isinstance(raw_report, dict) else {}
	analysis_payload = report.get("analysis_payload", {})
	if not isinstance(analysis_payload, dict):
		analysis_payload = specialist_response.metadata
	snapshot = analysis_payload.get("snapshot", {})
	if not isinstance(snapshot, dict):
		snapshot = {}
	sensors = snapshot.get("sensors", {})
	if not isinstance(sensors, dict):
		sensors = {}
	devices = snapshot.get("devices", {})
	if not isinstance(devices, dict):
		devices = {}
	normalized = " ".join(user_text.strip().lower().split())
	temp = sensor_value(sensors, "temperature")
	humi = sensor_value(sensors, "humidity")
	light = sensor_value(sensors, "light")
	anomaly = sensor_value(sensors, "anomaly")

	if any(
		marker in normalized for marker in ("nhiệt độ", "nhiet do", "temperature")
	) and isinstance(temp, (int, float)):
		return (
			f"Nhiệt độ hiện tại là {temp:.1f}°C."
			if prefer_vietnamese
			else f"The current temperature is {temp:.1f}°C."
		)
	if any(
		marker in normalized for marker in ("độ ẩm", "do am", "humidity")
	) and isinstance(humi, (int, float)):
		return (
			f"Độ ẩm hiện tại là {humi:.1f}%."
			if prefer_vietnamese
			else f"The current humidity is {humi:.1f}%."
		)
	if any(
		marker in normalized for marker in ("ánh sáng", "anh sang", "light")
	) and isinstance(light, (int, float)):
		return (
			f"Mức ánh sáng hiện tại là {light:.1f}."
			if prefer_vietnamese
			else f"The current light level is {light:.1f}."
		)
	if any(
		marker in normalized for marker in ("anomaly", "bất thường", "bat thuong")
	) and isinstance(anomaly, (int, float)):
		return (
			f"Điểm bất thường hiện tại là {anomaly:.2f}."
			if prefer_vietnamese
			else f"The current anomaly score is {anomaly:.2f}."
		)
	if isinstance(temp, (int, float)) and isinstance(humi, (int, float)):
		parts = (
			[
				f"Nhiệt độ {temp:.1f}°C",
				f"độ ẩm {humi:.1f}%",
			]
			if prefer_vietnamese
			else [
				f"temperature {temp:.1f}°C",
				f"humidity {humi:.1f}%",
			]
		)
		if isinstance(light, (int, float)):
			parts.append(
				f"ánh sáng {light:.1f}" if prefer_vietnamese else f"light {light:.1f}"
			)
		if isinstance(anomaly, (int, float)):
			parts.append(
				f"điểm bất thường {anomaly:.2f}"
				if prefer_vietnamese
				else f"anomaly score {anomaly:.2f}"
			)
		prefix = "Hiện tại " if prefer_vietnamese else "Currently, "
		return prefix + ", ".join(parts) + "."
	if devices:
		device_names = ("main_led", "neo_led", "ws2812", "relay", "mini_fan")
		on_devices = [name for name in device_names if device_status(devices, name) is True]
		off_devices = [name for name in device_names if device_status(devices, name) is False]
		return (
			f"Đang bật: {format_entity_list(on_devices, True) or 'không có'}. Đang tắt: {format_entity_list(off_devices, True) or 'không có'}."
			if prefer_vietnamese
			else f"On: {format_entity_list(on_devices, False) or 'none'}. Off: {format_entity_list(off_devices, False) or 'none'}."
		)
	return (
		"Tôi chưa có đủ dữ liệu cảm biến mới nhất."
		if prefer_vietnamese
		else "I do not have enough current sensor data yet."
	)


def render_anomaly_text(user_text: str, specialist_response: AgentResponse) -> str:
	prefer_vietnamese = looks_vietnamese(user_text)
	raw_report = specialist_response.metadata.get("specialist_report")
	report = raw_report if isinstance(raw_report, dict) else {}
	analysis_payload = report.get("analysis_payload", {})
	if not isinstance(analysis_payload, dict):
		analysis_payload = specialist_response.metadata
	classification = analysis_payload.get("classification", {})
	if not isinstance(classification, dict):
		classification = {}
	freshness = analysis_payload.get("freshness", {})
	if not isinstance(freshness, dict):
		freshness = {}
	telemetry_window = analysis_payload.get("telemetry_window", {})
	if not isinstance(telemetry_window, dict):
		telemetry_window = {}

	if freshness.get("is_stale"):
		age = freshness.get("age_seconds")
		age_text = "không rõ" if age is None else f"{age:.1f}s"
		return (
			f"Dữ liệu hiện tại đã cũ ({age_text}), nên tôi chưa thể kết luận chắc về bất thường lúc này."
			if prefer_vietnamese
			else f"The latest telemetry is stale ({age_text}), so I cannot make a confident anomaly judgment right now."
		)

	anomaly_type = str(classification.get("type") or "unknown")
	severity = str(classification.get("severity") or "none")
	detail = str(classification.get("detail") or "").strip()
	score = classification.get("score")
	window_events = telemetry_window.get("anomaly_events", {})
	if not isinstance(window_events, dict):
		window_events = {}

	if severity == "none" or anomaly_type == "normal":
		base = (
			"Hiện chưa thấy dấu hiệu bất thường."
			if prefer_vietnamese
			else "There is no current sign of an anomaly."
		)
		if isinstance(score, (int, float)):
			base += (
				f" Điểm hiện tại là {score:.2f}."
				if prefer_vietnamese
				else f" The current score is {score:.2f}."
			)
		return base

	parts = []
	if prefer_vietnamese:
		parts.append(f"Phát hiện bất thường mức {severity}.")
		if isinstance(score, (int, float)):
			parts.append(f"Điểm hiện tại là {score:.2f}.")
	else:
		parts.append(f"An anomaly is detected with {severity} severity.")
		if isinstance(score, (int, float)):
			parts.append(f"The current score is {score:.2f}.")
	if detail:
		parts.append(detail)
	if window_events.get("available") and window_events.get("count"):
		count = int(window_events["count"])
		parts.append(
			f"Cửa sổ gần đây có {count} lần vượt ngưỡng."
			if prefer_vietnamese
			else f"The recent window contains {count} threshold crossings."
		)
	return " ".join(parts)


def fast_general_response(user_text: str) -> str | None:
	return None
