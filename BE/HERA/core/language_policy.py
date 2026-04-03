"""
Language policy helpers for hard-locking EN/VI responses.
"""

from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

_VI_CHARS = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")

_VI_KEYWORDS = {
    "xin", "chao", "toi", "ban", "minh", "giup", "duoc", "khong", "cam", "on",
    "nhiet", "do", "doam", "bat", "tat", "den", "trang", "thai", "bao", "nhieu",
    "nhu", "the", "nao", "sao", "loi", "du", "lieu", "canh", "bao", "batthuong",
}

_EN_KEYWORDS = {
    "the", "and", "is", "are", "to", "of", "in", "for", "with", "you", "your",
    "please", "turn", "on", "off", "temperature", "humidity", "status", "anomaly",
    "help", "what", "how", "why", "can", "do", "hello", "hi",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", (text or "").lower())


def contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def _looks_vietnamese(text: str) -> bool:
    lower = (text or "").lower()
    if any(ch in _VI_CHARS for ch in lower):
        return True
    tokens = _tokenize(lower)
    vi_hits = sum(1 for t in tokens if t in _VI_KEYWORDS)
    return vi_hits >= 2


def _looks_english(text: str) -> bool:
    tokens = _tokenize(text)
    en_hits = sum(1 for t in tokens if t in _EN_KEYWORDS)
    return en_hits >= 3


def detect_user_language(text: str) -> str:
    """Detect user language as either 'vi' or 'en'."""
    return "vi" if _looks_vietnamese(text) else "en"


def build_language_policy(target_language: str) -> str:
    if target_language == "vi":
        return (
            "LANGUAGE LOCK: Vietnamese only.\n"
            "- You MUST respond only in Vietnamese.\n"
            "- You MUST NOT use English as the response language.\n"
            "- You MUST NOT output Chinese (Simplified/Traditional), Taiwanese Mandarin, "
            "Japanese, or Korean under any circumstance.\n"
            "- If your draft violates this rule, regenerate until fully Vietnamese."
        )
    return (
        "LANGUAGE LOCK: English only.\n"
        "- You MUST respond only in English.\n"
        "- You MUST NOT use Vietnamese as the response language.\n"
        "- You MUST NOT output Chinese (Simplified/Traditional), Taiwanese Mandarin, "
        "Japanese, or Korean under any circumstance.\n"
        "- If your draft violates this rule, regenerate until fully English."
    )


def is_response_language_valid(text: str, target_language: str) -> bool:
    if not text:
        return True
    if contains_cjk(text):
        return False
    if target_language == "vi":
        # For VI mode, reject clearly-English responses.
        return _looks_vietnamese(text) or not _looks_english(text)
    # For EN mode, reject clearly-Vietnamese responses.
    return not _looks_vietnamese(text)


def enforce_language_output(text: str, target_language: str) -> str:
    cleaned = (text or "").strip()
    if is_response_language_valid(cleaned, target_language):
        return cleaned
    if target_language == "vi":
        return "Xin loi, toi chi duoc phep tra loi bang tieng Viet. Vui long gui lai yeu cau bang tieng Viet."
    return "Sorry, I am only allowed to respond in English for this request. Please ask again in English."
