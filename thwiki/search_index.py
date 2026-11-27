"""Build a static site-search index from published HTML pages.

Generated at build time. Do not hand-write the output file.
"""

from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from .paths import DOCS_DIR

TITLE_PREFIX = "Top Heroes Wiki｜"

# Never use these typo or unofficial forms as result titles.
FORBIDDEN_TITLES = frozenset({
    "乙太牧場",
    "以太牧場",
    "地心獵獵",
    "地心獵獸",
    "鐵喉",
    "鐵噎",
    "魚缺",
    "魚缽",
    "堡堡外觀",
})

# Generic faction words are official, but make poor standalone result titles.
GENERIC_TITLES = frozenset({"聯盟", "自然", "部族"})

SKIP_TAGS = frozenset({"script", "style", "svg", "noscript"})
SKIP_IDS = frozenset({"notes"})
SKIP_CLASSES = frozenset({
    "toc",
    "page-filter",
    "site-search",
    "site-nav",
    "site-header",
    "site-footer",
    "skip",
})
VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


def _classes(attrs: dict[str, str]) -> set[str]:
    return set((attrs.get("class") or "").split())


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def display_title(raw: str) -> str:
    text = _norm_space(raw)
    if text.startswith(TITLE_PREFIX):
        text = text[len(TITLE_PREFIX):].strip()
    return text


def ok_name(text: str, *, allow_digits: bool = False) -> bool:
    s = _norm_space(text)
    if not s or s in FORBIDDEN_TITLES or s in GENERIC_TITLES:
        return False
    if len(s) < 2 or len(s) > 40:
        return False
    if re.fullmatch(r"[\d.\-–—→~\s]+", s) and not allow_digits:
        return False
    if re.fullmatch(r"[0-9a-fA-F]{16,}", s):
        return False
    if "." in s and s.rsplit(".", 1)[-1].lower() in {"json", "html", "js", "css", "md", "png"}:
        return False
    return True


class PageExtractor(HTMLParser):
    """Pull title, lede, headings and official names from visible body, skipping 資料說明."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.doc_title = ""
        self.h1 = ""
        self.lede = ""
        self.headings: list[tuple[str, str, bool]] = []  # id, text, has_term
        self.terms: list[str] = []
        self.first_cells: list[str] = []
        self._title_buf: list[str] = []
        self._h1_buf: list[str] = []
        self._lede_buf: list[str] = []
        self._heading_buf: list[str] = []
        self._heading_id = ""
        self._heading_has_term = False
        self._term_buf: list[str] = []
        self._cell_buf: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._in_lede = False
        self._in_heading = False
        self._in_term = False
        self._in_tbody = False
        self._row_cell = 0
        self._in_first_cell = False
        self._section_ids: list[str] = []

    def _skipping(self) -> bool:
        return bool(self.stack and self.stack[-1]["skip"])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        parent_skip = self._skipping()
        cls = _classes(d)
        skip = parent_skip or tag in SKIP_TAGS or d.get("id") in SKIP_IDS or bool(cls & SKIP_CLASSES)
        if tag not in VOID:
            self.stack.append({"tag": tag, "skip": skip})
        if tag == "section":
            self._section_ids.append(d.get("id") or "")
        if skip or tag in VOID:
            return
        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag == "p" and "lede" in cls:
            self._in_lede = True
        if tag in {"h2", "h3", "h4"}:
            self._in_heading = True
            self._heading_buf = []
            self._heading_has_term = False
            self._heading_id = d.get("id") or (self._section_ids[-1] if self._section_ids else "")
        if "term" in cls:
            self._in_term = True
            self._term_buf = []
            if self._in_heading:
                self._heading_has_term = True
        if tag == "tbody":
            self._in_tbody = True
        if tag == "tr" and self._in_tbody:
            self._row_cell = 0
        if tag == "td" and self._in_tbody:
            self._row_cell += 1
            if self._row_cell == 1:
                self._in_first_cell = True
                self._cell_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        # pop through to matching tag if needed
        while self.stack:
            last = self.stack.pop()
            if last["tag"] == tag:
                break
        if tag == "section" and self._section_ids:
            self._section_ids.pop()
        if tag == "title":
            if self._in_title:
                self.doc_title = _norm_space("".join(self._title_buf))
            self._in_title = False
        if tag == "h1":
            if self._in_h1:
                self.h1 = _norm_space("".join(self._h1_buf))
            self._in_h1 = False
        if tag == "p" and self._in_lede:
            self.lede = _norm_space("".join(self._lede_buf))
            self._in_lede = False
        if tag in {"h2", "h3", "h4"} and self._in_heading:
            text = _norm_space("".join(self._heading_buf))
            if text:
                self.headings.append((self._heading_id, text, self._heading_has_term))
            self._in_heading = False
        if tag == "span" and self._in_term:
            text = _norm_space("".join(self._term_buf))
            if text:
                self.terms.append(text)
            self._in_term = False
        if tag == "tbody":
            self._in_tbody = False
        if tag == "td" and self._in_first_cell:
            text = _norm_space("".join(self._cell_buf))
            if text:
                self.first_cells.append(text)
            self._in_first_cell = False

    def handle_data(self, data: str) -> None:
        if self._skipping():
            return
        if self._in_title:
            self._title_buf.append(data)
        if self._in_h1:
            self._h1_buf.append(data)
        if self._in_lede:
            self._lede_buf.append(data)
        if self._in_heading:
            self._heading_buf.append(data)
        if self._in_term:
            self._term_buf.append(data)
        if self._in_first_cell:
            self._cell_buf.append(data)


def extract_page(html: str, rel_url: str) -> list[dict[str, str]]:
    parser = PageExtractor()
    parser.feed(html)
    title = display_title(parser.h1 or parser.doc_title) or display_title(parser.doc_title)
    if not title or title in FORBIDDEN_TITLES:
        return []

    parts: list[str] = [title]
    if parser.lede:
        parts.append(parser.lede)
    for _hid, text, _term in parser.headings:
        parts.append(text)
    parts.extend(parser.terms)
    parts.extend(parser.first_cells)
    # unique, stable, compact
    seen: set[str] = set()
    blob_parts: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            blob_parts.append(p)
    haystack = " ".join(blob_parts)

    entries = [{"title": title, "url": rel_url, "text": haystack}]

    names: list[tuple[str, str]] = []
    for hid, text, has_term in parser.headings:
        if has_term and ok_name(text):
            url = f"{rel_url}#{hid}" if hid else rel_url
            names.append((text, url))
    for cell in parser.first_cells:
        if ok_name(cell):
            names.append((cell, rel_url))

    # Deduplicate by (title, page without new fragment if one already has a fragment).
    kept: dict[str, tuple[str, str]] = {}
    for name, url in names:
        if name == title:
            continue
        page = url.split("#", 1)[0]
        key = f"{name}\0{page}"
        prev = kept.get(key)
        if prev is None or ("#" not in prev[1] and "#" in url):
            kept[key] = (name, url)
    for name, url in kept.values():
        entries.append({"title": name, "url": url, "text": name})
    return entries


def write_search_index(pages: list[Path]) -> Path:
    entries: list[dict[str, str]] = []
    for path in pages:
        rel = path.relative_to(DOCS_DIR).as_posix()
        html = path.read_text(encoding="utf-8")
        entries.extend(extract_page(html, rel))
    entries.sort(key=lambda e: (e["url"], e["title"]))
    out = DOCS_DIR / "assets" / "js" / "search-index.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    out.write_text(
        "/* Generated by build.py. Do not edit. */\n"
        "window.TH_WIKI_SEARCH_INDEX = "
        + payload
        + ";\n",
        encoding="utf-8",
    )
    return out
