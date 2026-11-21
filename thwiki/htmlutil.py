from __future__ import annotations

import html
from typing import Iterable


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


def table(columns: list[str], rows: list[list[str]], caption: str | None = None) -> str:
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr></thead>"
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    cap = f"<caption>{caption}</caption>" if caption else ""
    return f'<div class="table-wrap"><table>{cap}{thead}<tbody>{"".join(body)}</tbody></table></div>'
