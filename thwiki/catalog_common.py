"""Shared helpers for the 2026-11-22 LocalLow public catalog pages."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .highlight import highlight, highlight_lines
from .htmlutil import e, table
from .paths import DATA_CUTOFF, TOPHEROES_ROOT

EXTRACT_DIR = TOPHEROES_ROOT / "extracts/2026-11-22-locallow"
EXTRACT_DATA = EXTRACT_DIR / "data"
EXTRACT_STRINGS = EXTRACT_DIR / "strings_zh.json"

PAGE_CUTOFF = "2026-11-22"
STRINGS_SHA256 = "249e08f64922de78527d6669912e4202fd650d1bd2434e47c89351d123da0134"
STRINGS_KEY_COUNT = 40581

COLOR_RE = re.compile(r"</?color(?:=[^>]*)?>", re.I)

_STRINGS: dict | None = None
_STRINGS_SHA: str | None = None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def load_strings() -> dict:
    global _STRINGS, _STRINGS_SHA
    if _STRINGS is None:
        actual = file_sha256(EXTRACT_STRINGS)
        if actual != STRINGS_SHA256:
            raise RuntimeError(f"strings_zh.json sha256 mismatch: {actual} != {STRINGS_SHA256}")
        _STRINGS = load_json(EXTRACT_STRINGS)
        _STRINGS_SHA = actual
        if len(_STRINGS) != STRINGS_KEY_COUNT:
            raise RuntimeError(f"strings_zh.json key count {len(_STRINGS)} != {STRINGS_KEY_COUNT}")
    return _STRINGS


def strings_sha() -> str:
    load_strings()
    return _STRINGS_SHA or STRINGS_SHA256


def official_text(key, default: str = "") -> str:
    if key is None or key == "" or key == -1 or str(key) == "-1":
        return default
    value = load_strings().get(str(key))
    if value is None:
        return default
    return value


def has_string(key) -> bool:
    if key is None or key == "" or key == -1 or str(key) == "-1":
        return False
    return str(key) in load_strings()


def visible_official(text: str) -> str:
    t = COLOR_RE.sub("", text or "")
    t = t.replace("\r\n", "\n")
    return t.strip()


def load_table(name: str, expected_sha: str | None = None):
    path = EXTRACT_DATA / name
    if expected_sha:
        actual = file_sha256(path)
        if actual != expected_sha:
            raise RuntimeError(f"{name} sha256 mismatch: {actual} != {expected_sha}")
    return load_json(path)


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def quote_block(text: str, terms: list[str]) -> str:
    visible = visible_official(text)
    if not visible:
        return ""
    return f"<blockquote>{highlight_lines(visible, terms)}</blockquote>"


def fmt_pipe(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            if isinstance(item, (list, tuple)):
                parts.append("｜".join(str(x) for x in item))
            else:
                parts.append(str(item))
        return "，".join(parts)
    return str(value).replace("|", "｜")


def fmt_qty(value) -> str:
    if value is None or value == "":
        return ""
    return str(value)


def goods_label(gid, terms: list[str]) -> str:
    """Official short name only; if missing, say so without inventing one."""
    if gid in (None, "", -1, 0, "0", "-1"):
        return ""
    name = official_text(f"goods_name_{gid}")
    if name:
        return H(visible_official(name), terms)
    return "沒有官方短名"


def resource_label(rid, terms: list[str]) -> str:
    """Official top-bar resource name; do not invent a label if the key is missing."""
    if rid in (None, "", -1, 0, "0", "-1"):
        return ""
    name = official_text(f"top_resource_name_{rid}")
    if name:
        return H(visible_official(name), terms)
    return "字串表沒有名稱"


def attr_pair_label(spec, terms: list[str]) -> str:
    """Official attribute name plus value, without a raw id in the visible phrase."""
    if spec in (None, "", -1, 0, "0", "-1"):
        return ""
    if isinstance(spec, (list, tuple)):
        if not spec:
            return ""
        aid = spec[0]
        val = spec[1] if len(spec) > 1 else ""
    else:
        text = str(spec)
        if "|" in text:
            aid, val = text.split("|", 1)
        else:
            aid, val = text, ""
    name = official_text(f"attribute_name_{aid}")
    label = H(visible_official(name), terms) if name else "字串表沒有名稱"
    if val in ("", None):
        return label
    shown = str(val).split("|", 1)[0]
    return f"{label} {fmt_qty(shown)}"


def cost_spec_label(spec, terms: list[str]) -> str:
    """Format consume strings such as 999|3|n or 2|goodsId|n into official names."""
    if spec in (None, "", -1, 0, "0", "-1"):
        return ""
    tokens = []
    if isinstance(spec, (list, tuple)):
        if spec and isinstance(spec[0], (list, tuple)):
            tokens = list(spec)
        elif spec and not isinstance(spec[0], (list, tuple)) and len(spec) >= 2:
            tokens = [spec]
        else:
            tokens = list(spec)
    else:
        for part in str(spec).split(","):
            part = part.strip()
            if part:
                tokens.append(part.split("|"))
    bits = []
    for tok in tokens:
        if not tok:
            continue
        if isinstance(tok, str):
            parts = tok.split("|")
        else:
            parts = [str(x) for x in tok]
        if len(parts) < 2:
            continue
        if len(parts) == 2:
            # Ambiguous two-part forms are not guessed in visible body.
            continue
        typ, mid, qty = parts[0], parts[1], parts[2]
        if typ == "999":
            name = resource_label(mid, terms)
        else:
            name = goods_label(mid, terms) or "沒有官方短名"
        bits.append(f"{name} {fmt_qty(qty)}")
    return "、".join(bits)


def render_info_pages(row: dict, terms: list[str], skip_title_keys: set[str] | None = None) -> list[str]:
    """Render official info.json pages: section titles and quoted bodies."""
    parts: list[str] = []
    skip = skip_title_keys or set()
    page_titles = []
    raw_titles = row.get("titlePage") or row.get("title_page") or []
    for key in raw_titles:
        if not key or str(key) in ("-1", "") or str(key) in skip:
            continue
        title = visible_official(official_text(key))
        if title:
            page_titles.append(title)
    if page_titles:
        bits = "、".join(f"「{H(t, terms)}」" for t in page_titles)
        parts.append(p_html("說明頁的分節標題是" + bits + "。"))
    for attr, fallback in (("page1", "info_num_1"), ("page2", "info_num_2"), ("page3", "info_num_3")):
        pages = row.get(attr) or []
        if not pages:
            continue
        for item in pages:
            if isinstance(item, str) and "|" in item:
                bits = item.split("|")
                heading_key, body_key = bits[1] if len(bits) > 1 else "", bits[2] if len(bits) > 2 else ""
            elif isinstance(item, (list, tuple)) and len(item) >= 3:
                heading_key, body_key = item[1], item[2]
            else:
                continue
            heading = visible_official(official_text(heading_key)) if has_string(heading_key) else ""
            body = visible_official(official_text(body_key)) if has_string(body_key) else ""
            if heading:
                parts.append(f"<h3>{H(heading, terms)}</h3>")
            if body:
                parts.append(quote_block(body, terms))
    return parts


def footer_swap(html: str) -> str:
    from .paths import DATA_CUTOFF as GLOBAL_CUTOFF

    return html.replace(
        f"<p>資料截至 {GLOBAL_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        1,
    )


def notes_source_intro() -> str:
    return (
        f"資料截至 {PAGE_CUTOFF}（香港時間）。來源是 {PAGE_CUTOFF} LocalLow 解壓表與 "
        f"字串表（UTF-8 BOM），字串表 {STRINGS_KEY_COUNT} 鍵，SHA-256 <code>{STRINGS_SHA256}</code>。"
        f"不改 <code>paths.DATA_CUTOFF</code>（仍為 {DATA_CUTOFF}）。"
    )


def unique_keep_order(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
