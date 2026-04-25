"""Semantic content extraction - split, score, filter."""

from __future__ import annotations

import re
from typing import Any


def extract_keywords(query: str) -> set[str]:
	"""Extract keywords from query."""
	# Remove common words
	stopwords = {
		"là",
		"ở",
		"và",
		"hay",
		"hay",
		"với",
		"từ",
		"cái",
		"những",
		"những",
		"có",
		"được",
		"thì",
		"không",
		"nào",
		"gì",
		"cách",
		"mình",
		"bạn",
		"tôi",
		"for",
		"the",
		"and",
		"or",
		"is",
		"at",
		"to",
		"a",
		"an",
		"in",
		"on",
		"of",
	}

	# Split and normalize
	words = re.findall(r"\w+", query.lower())
	return {w for w in words if w not in stopwords and len(w) > 2}


def split_paragraphs(content: str) -> list[str]:
	"""Split content into paragraphs."""
	# Split by multiple newlines or sentence endings
	paragraphs = re.split(r"\n\n+|\n(?=[A-Z])", content)
	# Clean and filter
	return [p.strip() for p in paragraphs if p.strip() and len(p.strip()) > 20]


def score_paragraph(paragraph: str, keywords: set[str]) -> float:
	"""Score paragraph based on keyword overlap."""
	para_words = set(re.findall(r"\w+", paragraph.lower()))
	if not para_words:
		return 0.0

	# Jaccard similarity
	overlap = len(keywords & para_words)
	union = len(keywords | para_words)

	return overlap / union if union > 0 else 0.0


def extract_relevant_content(
	content: str,
	query: str,
	max_chars: int = 2000,
	min_score: float = 0.1,
) -> str:
	"""Extract relevant paragraphs from content based on query."""

	# Extract keywords from query
	keywords = extract_keywords(query)

	if not keywords:
		# Fallback: return first N chars
		return content[:max_chars]

	# Split into paragraphs
	paragraphs = split_paragraphs(content)

	# Score and filter
	scored = [(p, score_paragraph(p, keywords)) for p in paragraphs]

	# Sort by score, keep high-scoring
	relevant = [
		p
		for p, score in sorted(scored, key=lambda x: x[1], reverse=True)
		if score >= min_score
	]

	# Combine until max_chars
	result = []
	total_chars = 0
	for para in relevant:
		if total_chars + len(para) > max_chars:
			break
		result.append(para)
		total_chars += len(para)

	return "\n\n".join(result) if result else content[:max_chars]


# Test
if __name__ == "__main__":
	test_content = """
	Lẩu Bò Nguyễn Cư Trinh, với địa chỉ tại số 119 Nguyễn Cư Trinh, Quận 1, TP. Hồ Chí Minh, 
	là một điểm đến lý tưởng cho những ai yêu thích ẩm thực đậm đà và trải nghiệm dịch vụ chất lượng.
	
	Quán nổi tiếng với món lẩu bò hấp dẫn, khiến bạn không thể cưỡng lại được hương vị thơm ngon và đậm đà.
	Những miếng thịt bò tươi ngon và các loại rau củ tươi mát được chế biến tinh tế.
	
	Không chỉ về đồ ăn ngon, Lẩu Bò Nguyễn Cư Trinh còn ghi điểm bởi dịch vụ tận tâm và tốt.
	Đội ngũ nhân viên luôn sẵn sàng phục vụ bạn với tinh thần niềm nở.
	
	Menu rất đa dạng với lẩu bò, lẩu hải sản, lẩu nấm và nhiều loại khác.
	"""

	query = "quán lẩu quận 1"
	extracted = extract_relevant_content(test_content, query, max_chars=1000)

	print("Original length:", len(test_content))
	print("Extracted length:", len(extracted))
	print("\nExtracted content:")
	print(extracted)

	print("\n\nKeywords:", extract_keywords(query))
