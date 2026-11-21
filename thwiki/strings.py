from __future__ import annotations

import json
import re
from functools import lru_cache

from .paths import STRINGS_PATH


@lru_cache(maxsize=1)
def load_strings() -> dict:
    with open(STRINGS_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def t(key, default: str = "") -> str:
    if key is None:
        return default
    strings = load_strings()
    value = strings.get(str(key))
    return value if value is not None else default


def has_key(key) -> bool:
    if key is None:
        return False
    return str(key) in load_strings()


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("\\n", "\n").strip()


def fmt_num(value) -> str:
    s = str(value).strip()
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return format(f, "g")
    except ValueError:
        return s


def fill_text(text, params=None, special=None) -> str:
    """Fill {0} placeholders. special_desc == 2 usually means a percent.

    If the template already has % or 秒 after the slot, do not add another unit.
    A few official strings omit 秒 after「持續／每」, but still mark type 2;
    those are treated as seconds, matching the league-guide formatter.
    """
    text = clean(text or "")
    if not text:
        return text
    params = list(params or [])
    special = list(special or [])

    def repl(match: re.Match) -> str:
        i = int(match.group(1))
        if i >= len(params) or params[i] in (None, ""):
            return match.group(0)
        val = fmt_num(params[i])
        typ = special[i] if i < len(special) else None
        after = text[match.end() : match.end() + 1]
        before = text[max(0, match.start() - 8) : match.start()]
        if after in ("%", "秒"):
            return val
        if before.endswith("持續"):
            return val + "秒"
        if before.endswith("每") and text[match.end() :].startswith("可"):
            return val + "秒"
        if typ == 2:
            return val + "%"
        return val

    return re.sub(r"\{(\d+)\}", repl, text)
