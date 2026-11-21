from __future__ import annotations

import html
from typing import Iterable


def highlight(text: str, terms: Iterable[str]) -> str:
    """Escape text and wrap 專有名詞, longest first, no overlapping ranges."""
    if text is None:
        return ""
    raw = str(text)
    term_list = sorted({t for t in terms if t}, key=len, reverse=True)
    ranges: list[tuple[int, int]] = []
    for term in term_list:
        start = 0
        while True:
            i = raw.find(term, start)
            if i < 0:
                break
            j = i + len(term)
            if not any(i < e and j > s for s, e in ranges):
                ranges.append((i, j))
            start = i + 1
    ranges.sort()
    parts: list[str] = []
    cursor = 0
    for s, e in ranges:
        if s > cursor:
            parts.append(html.escape(raw[cursor:s]))
        parts.append(f'<span class="term">{html.escape(raw[s:e])}</span>')
        cursor = e
    if cursor < len(raw):
        parts.append(html.escape(raw[cursor:]))
    return "".join(parts)


def highlight_lines(text: str, terms: Iterable[str]) -> str:
    lines = str(text).split("\n")
    return "<br>\n".join(highlight(line, terms) for line in lines)
