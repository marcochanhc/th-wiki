from __future__ import annotations

import html
import re
from typing import Iterable

# Visible name column for card titles, in preference order. Exact header text only.
CARD_TITLE_HEADERS = (
    "造型名稱（照 skin_name 原樣）",
    "造型",
    "造型 A",
    "英靈",
    "套裝",
    "英雄",
    "專武",
)


def e(text) -> str:
    return html.escape("" if text is None else str(text))


def tag(name: str, body: str = "", attrs: dict | None = None, void: bool = False) -> str:
    attr = ""
    if attrs:
        bits = []
        for k, v in attrs.items():
            if v is None or v is False:
                continue
            if v is True:
                bits.append(k)
            else:
                bits.append(f'{k}="{html.escape(str(v), quote=True)}"')
        if bits:
            attr = " " + " ".join(bits)
    if void:
        return f"<{name}{attr}>"
    return f"<{name}{attr}>{body}</{name}>"


def _plain_label(text: str) -> str:
    t = re.sub(r"<[^>]+>", "", text or "")
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _card_title_index(columns: list[str], card_title: str | None) -> int:
    if card_title:
        labels = [_plain_label(c) for c in columns]
        if card_title in labels:
            return labels.index(card_title)
        if card_title in columns:
            return columns.index(card_title)
    labels = [_plain_label(c) for c in columns]
    for name in CARD_TITLE_HEADERS:
        if name in labels:
            return labels.index(name)
    return 0


def table(
    columns: list[str],
    rows: list[list[str]],
    caption: str | None = None,
    row_ids: list[str] | None = None,
    wrap_class: str | None = None,
    mobile: str | None = None,
    card_title: str | None = None,
) -> str:
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr></thead>"
    body = []
    labels = [_plain_label(c) for c in columns] if mobile == "cards" else []
    title_i = _card_title_index(columns, card_title) if mobile == "cards" else -1
    for i, row in enumerate(rows):
        rid = ""
        if row_ids and i < len(row_ids) and row_ids[i]:
            rid = f' id="{html.escape(str(row_ids[i]), quote=True)}"'
        if mobile == "cards":
            cells = []
            for j, c in enumerate(row):
                label = labels[j] if j < len(labels) else ""
                attr = f' data-label="{html.escape(label, quote=True)}"'
                if j == title_i:
                    attr += ' class="card-title"'
                cells.append(f"<td{attr}>{c}</td>")
            body.append(f"<tr{rid}>" + "".join(cells) + "</tr>")
        else:
            body.append(f"<tr{rid}>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    cap = f"<caption>{caption}</caption>" if caption else ""
    cls = "table-wrap"
    if wrap_class:
        cls += " " + wrap_class
    if mobile == "cards":
        cls += " table-cards"
    elif mobile == "sticky":
        cls += " table-sticky-col"
    elif mobile == "sticky2":
        cls += " table-sticky-col table-sticky-col-2"
    return f'<div class="{cls}"><table>{cap}{thead}<tbody>{"".join(body)}</tbody></table></div>'
