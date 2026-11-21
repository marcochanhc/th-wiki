from __future__ import annotations

from .strings import t
from .tables import catalog

# Locked title_attr percentages only. Do not extend to skins, 羈絆, or other show_type=2.
TITLE_ATTR_LOCK = {
    (33, 500): "治療效果+5%",
    (18, 300): "最終傷害+3%",
    (19, 500): "受到傷害-5%",
    (104, 500): "生命上限+5%",
}

# Informal earlier labels, used only as a parenthetical in 資料說明.
TITLE_ATTR_OLD = {
    (33, 500): "英雄治療率 500",
    (18, 300): "增傷 300",
    (19, 500): "減傷 500",
    (104, 500): "英雄生命 500",
}

TITLE1_BY_ATTR = {
    (19, 500): 1,  # 坦克
    (18, 300): 2,  # 傷害
    (33, 500): 3,  # 治療
    (104, 500): 4,  # 輔助
}

# honor_group -> first bonus attribute id
_GROUP_ATTR = None


def group_attr_map() -> dict:
    global _GROUP_ATTR
    if _GROUP_ATTR is None:
        mapping = {}
        for row in catalog()["hero_honor_bonus"]:
            mapping.setdefault(row["honor_group"], row["bonus_attribute"][0])
        _GROUP_ATTR = mapping
    return _GROUP_ATTR


# honor_group 301 is not a race attr; skill-text fallback only (not used for 審判官／修女).
SKILL301_FACTION = {
    10001: "聯盟",
    10002: "自然",
    10006: "聯盟",
    10009: "部族",
    10010: "部族",
}


def attr_name(attr_id: int) -> str:
    row = catalog()["attribute_by_id"].get(int(attr_id)) or {}
    name = t(row.get("name")) or t(f"attribute_name_{attr_id}")
    return name or str(attr_id)


def attr_show_type(attr_id: int):
    row = catalog()["attribute_by_id"].get(int(attr_id)) or {}
    return row.get("show_type")


def parse_pairs(raw) -> list[tuple[int, str]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, (list, tuple)):
        if raw and isinstance(raw[0], (list, tuple)) and len(raw[0]) >= 2:
            return [(int(a), str(b)) for a, b in raw]
        if len(raw) == 2 and not isinstance(raw[0], (list, tuple)):
            return [(int(raw[0]), str(raw[1]))]
        out = []
        for item in raw:
            out.extend(parse_pairs(item))
        return out
    text = str(raw)
    pairs = []
    for seg in text.split(","):
        seg = seg.strip()
        if not seg:
            continue
        if "|" in seg:
            a, b = seg.split("|", 1)
            pairs.append((int(a), b))
        else:
            pairs.append((None, seg))
    return pairs


def format_raw_pairs(raw, joiner: str = "、") -> str:
    """Format attribute pairs as official names plus raw points.

    Never apply the title_attr or talent percentage locks here.
    """
    pairs = parse_pairs(raw)
    if not pairs:
        return "無"
    parts = []
    for attr_id, value in pairs:
        if attr_id is None:
            parts.append(str(value))
        else:
            parts.append(f"{attr_name(attr_id)} {comma_int(value)}")
    return joiner.join(parts)


def comma_int(value) -> str:
    s = str(value).strip()
    try:
        f = float(s)
        if f.is_integer():
            n = int(f)
            # Skin / bond style on published pages usually has no thousands
            # separator under 10,000; talent raw values use 9,000. Callers
            # that need separators should use format_int().
            return str(n)
        return s
    except ValueError:
        return s


def format_int(value) -> str:
    s = str(value).strip().replace(",", "")
    try:
        f = float(s)
        if f.is_integer():
            return f"{int(f):,}"
        return s
    except ValueError:
        return str(value)


def format_title_attr(raw) -> str | None:
    pairs = parse_pairs(raw)
    if not pairs:
        return None
    locked = []
    for attr_id, value in pairs:
        try:
            key = (int(attr_id), int(float(str(value))))
        except (TypeError, ValueError):
            return None
        if key not in TITLE_ATTR_LOCK:
            return None
        locked.append(TITLE_ATTR_LOCK[key])
    return "、".join(locked)


def title_attr_old(raw) -> str | None:
    pairs = parse_pairs(raw)
    if len(pairs) != 1:
        return None
    attr_id, value = pairs[0]
    try:
        key = (int(attr_id), int(float(str(value))))
    except (TypeError, ValueError):
        return None
    return TITLE_ATTR_OLD.get(key)


def title1_index(raw) -> int | None:
    pairs = parse_pairs(raw)
    if len(pairs) != 1:
        return None
    attr_id, value = pairs[0]
    try:
        key = (int(attr_id), int(float(str(value))))
    except (TypeError, ValueError):
        return None
    return TITLE1_BY_ATTR.get(key)


def honor_faction(hero_id: int):
    heroes = catalog()["hero_by_id"]
    attrs = catalog()["attribute_by_id"]
    hero = heroes.get(hero_id) or {}
    group = hero.get("honor_group")
    attr_id = group_attr_map().get(group)
    if attr_id is None:
        return None, group, None, None
    if 3000 <= attr_id < 4000:
        fac = "聯盟"
    elif 4000 <= attr_id < 5000:
        fac = "部族"
    elif 5000 <= attr_id < 6000:
        fac = "自然"
    else:
        fac = None
    row = attrs.get(attr_id) or {}
    return fac, group, attr_id, row


def hero_faction(hero_id: int) -> tuple[str | None, str, int | None, int | None]:
    fac, group, attr_id, _row = honor_faction(hero_id)
    if fac:
        return fac, "honor", group, attr_id
    if hero_id in SKILL301_FACTION:
        return SKILL301_FACTION[hero_id], "skill301", group, attr_id
    return None, "unknown", group, attr_id
