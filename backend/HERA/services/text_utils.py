"""Shared text utilities for user-visible responses."""

from __future__ import annotations

from datetime import datetime


def clean_user_visible_text(text: str) -> str:
	"""Strip common markdown wrappers from LLM/user-visible text."""
	cleaned = (text or "").strip()
	if cleaned.startswith("```"):
		lines = cleaned.splitlines()
		if lines and lines[0].startswith("```"):
			lines = lines[1:]
		if lines and lines[-1].strip() == "```":
			lines = lines[:-1]
		cleaned = "\n".join(lines).strip()
	if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
		cleaned = cleaned[1:-1].strip()
	return cleaned


def format_timestamp(value: str | None) -> str | None:
	if not value:
		return None
	text = str(value)
	if text.endswith("Z"):
		text = text[:-1] + "+00:00"
	try:
		parsed = datetime.fromisoformat(text)
	except ValueError:
		return value
	return parsed.strftime("%Y-%m-%d %H:%M:%S")


def looks_vietnamese(text: str) -> bool:
	"""Small presentation hint only; routing must not depend on this."""
	lowered = (text or "").lower()
	return any(
		ch in lowered
		for ch in "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
	)
