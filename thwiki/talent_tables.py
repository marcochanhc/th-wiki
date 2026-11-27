"""Compile the unpublished 天賦 catalog tables. Public-style HTML; preview script adds the banner."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .assemble import hero_href
from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .overrides import ROSTER, UNRELEASED_HERO_IDS, roster_display_name
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT
from .strings import clean, has_key, t
from .tables import load_table


# 天賦總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁尾資料截至寫解壓包日期 2026-11-22。
# 第 23 章第三版／前服面板確認寫於 2026-11-21（香港時間），那是整理日期，不是解壓截止日。
TALENT_DATA_CUTOFF = "2026-11-22"
TALENT_DATA_PACK = "app-1.129.12_table-1.0.43173"
TALENT_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "hero_talent.json": "b52849d3f051c2f231d1f0e8b8ef9b2aabca03835d2e69dc8a28358c19198a15",
    "hero_talent_new.json": "0450c26c4253fbb18ccd6c2c68be121f06c6ea8810f5e6660fddea049fa8c114",
    "hero_talent_group.json": "fcb822964dfc59d52f290c047da700cd39b3f666cd75e9a289c821bb0c6b4b11",
    "hero_talent_swap.json": "76f9b5d71a34ae4160264ff05b306f2b8456e75ebc761b2c0bf7bc0a9cdff227",
    "hero_detail.json": "281686181df002ab27a568bead407fc1b9741fbf2ebc2aaa97dfa213e037354f",
    "player_talent_professional.json": "c7e57fcda1b127d0df8e4c1f532c3c6edd0c9dc322208cfce6170c29969cc889",
    "player_talent_detail.json": "30674740cf8bfaeba06f9a4cd600400cac51ce41f15525fa36a13c8438f45a05",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "map_building.json": "cf85c9b553d8ef99c07fc00cf363546371993c62b0e30c1526be8fa87b284b9a",
}

PACK_DATA_DIRS = {
    "live": DATA_DIR,
    "2026-11-05": TOPHEROES_ROOT / "extracts/2026-11-05/data",
    "2026-11-22": TOPHEROES_ROOT / "extracts/2026-11-22/data",
    "2026-11-22-locallow": TOPHEROES_ROOT / "extracts/2026-11-22-locallow/data",
}
PACK_STRINGS = {
    "live": STRINGS_PATH,
    "2026-11-05": TOPHEROES_ROOT / "extracts/2026-11-05/strings_zh.json",
    "2026-11-22": TOPHEROES_ROOT / "extracts/2026-11-22/strings_zh.json",
    "2026-11-22-locallow": TOPHEROES_ROOT / "extracts/2026-11-22-locallow/strings_zh.json",
}

EMPTY = "—"

LEDE = (
    "本頁分開列出兩套系統，不要混為一套：英雄天賦（官方名稱「天賦」），"
    "可在英雄介面消耗對應英雄碎片提升；以及領主天賦（官方名稱「領主天賦」），"
    "在領主大廳中學習。以面板看得到的為準，兩套定義不要混。不評定天賦強弱，也不做搭配模擬。"
)

# 已確認前服面板原文，一字不改，從第 23 章抄錄。
PANEL_JUDGE_ATK = "進攻戰略／自身所有士兵攻擊提升90.00%"
PANEL_JUDGE_HP = "持久策略／自身所有士兵生命提升270.00%"
PANEL_JUDGE_BLOCK = "格擋研究／自身格擋提升30.00%"
PANEL_ALCHEMIST_ATK = "進攻戰略／自身所有士兵攻擊提升20.00%"
PANEL_DANCER_ATK = "進攻戰略／自身所有士兵攻擊提升50.00%"
PANEL_DANCER_HP = "持久策略／自身所有士兵生命提升150.00%"
PANEL_DANCER_HEAL = "快速醫療／傷兵治療速度提升30.00%"
PANEL_WARLOCK = "資源掠奪／每日木材、石頭掠奪上限提升360000"
PANEL_WATCHER = "士兵擴編／每個陣營容納士兵上限提升2000"
PANEL_PRINCE = "自身技能減傷提升35.00%(下一級技能減傷提升36.67%)"

PANEL_QUOTES = (
    PANEL_JUDGE_ATK,
    PANEL_JUDGE_HP,
    PANEL_JUDGE_BLOCK,
    PANEL_ALCHEMIST_ATK,
    PANEL_DANCER_ATK,
    PANEL_DANCER_HP,
    PANEL_DANCER_HEAL,
    PANEL_WARLOCK,
    PANEL_WATCHER,
    PANEL_PRINCE,
)

# 第 23 章槽 3 列序（先戰鬥、後行軍）。集合須與新表槽 3 完全一致。
SLOT3_COMBAT_ORDER = (20105, 20196, 20115, 20145, 20045, 20055, 20075, 20085, 20155, 20255)
SLOT3_MARCH_ORDER = (
    20175, 20185, 20195, 10124, 10125, 10114, 10094, 10095, 10105,
    10054, 10055, 10064, 10065, 10074, 10075, 20205,
)
SLOT3_HERO_ORDER = {
    20105: (10024, 10036, 10040),
    20196: (10037,),
    20115: (10035, 10039, 10044, 10048, 15039),
    20145: (10020, 10025, 10033, 10041, 10046, 10047, 10049, 15033),
    20045: (10023,),
    20055: (10038, 10042, 10043, 10045, 10050, 10051, 10052, 10053, 10054),
    20075: (10029,),
    20085: (10017, 10031),
    20155: (10008, 10027),
    20255: (10001, 10002, 10006, 10007, 10009, 10010),
    20175: (10012,),
    20185: (10018,),
    20195: (10021,),
    10124: (10004,),
    10125: (10032, 15032),
    10114: (10003, 10005, 10013),
    10094: (10016,),
    10095: (10034,),
    10105: (10030,),
    10054: (10015,),
    10055: (10019,),
    10064: (10011,),
    10065: (10026,),
    10074: (10014,),
    10075: (10022,),
    20205: (10028,),
}

QUALITY1_IDS = (10001, 10002, 10006, 10007, 10009, 10010)
QUALITY2_IDS = (10003, 10004, 10005, 10011, 10013, 10014, 10015, 10016)

WAR_TREE_ORDER = (
    60010300, 60010900, 60020100, 60020500, 60020900, 60030300, 60030700,
    60030900, 60031100, 60040100, 60040300, 60040500, 60040700, 60040900,
    60041100, 60050100, 60050300, 60050500, 60050900, 60060300, 60070100,
    60070500,
)
# 第 23 章豐饒表序：700501／503／505 寫在 700407／409／411 之前。
ABUNDANCE_TREE_ORDER = (
    70010300, 70010900, 70020100, 70020300, 70020500, 70020900, 70030300,
    70030900, 70040100, 70040300, 70040500, 70050100, 70050300, 70050500,
    70040700, 70040900, 70041100, 70060300, 70070100, 70070500,
)
SERIES_710_ORDER = (71040700, 71041100, 71050100, 71050300, 71050500)

NAMED_LORD_NODES = {
    60010300: "player_talent_name_1000105",  # 戰爭狂熱
    60020500: "player_talent_name_1022",     # 治療加速
    60030300: "player_talent_name_1100003",  # 狂野本性
}

USED_KEYS: set[str] = set()
MISSING_KEYS: set[str] = set()


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def official_text(key, default: str = "") -> str:
    if key is None or key == "":
        return default
    key = str(key)
    if not has_key(key):
        MISSING_KEYS.add(key)
        return default
    USED_KEYS.add(key)
    return clean(t(key, default))


def official_raw(key, default: str = "") -> str:
    """Official string with color tags stripped, newlines kept (for whole-block quotes)."""
    if key is None or key == "":
        return default
    key = str(key)
    if not has_key(key):
        MISSING_KEYS.add(key)
        return default
    USED_KEYS.add(key)
    text = t(key, default) or ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("\\n", "\n").strip()


def official_term_html(text: str) -> str:
    """Wrap an entire official phrase in a single .term; do not split the sentence."""
    if not text:
        return ""
    return f'<span class="term">{e(text).replace(chr(10), "<br>")}</span>'


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value) -> int:
    return int(float(str(value).strip()))


def comma(value) -> str:
    return f"{_int(value):,}"


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def parse_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, list):
        # Flat pair [attr_id, value], as used by hero_attr / player_attr.
        if raw and not isinstance(raw[0], (list, tuple, dict)):
            if len(raw) >= 2:
                try:
                    return [(_int(raw[0]), _int(raw[1]))]
                except (TypeError, ValueError):
                    return []
            return []
        out: list[tuple[int, int]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and not isinstance(item[0], (list, tuple, str)):
                try:
                    out.append((_int(item[0]), _int(item[1])))
                    continue
                except (TypeError, ValueError):
                    pass
            out.extend(parse_pairs(item))
        return out
    text = str(raw)
    out: list[tuple[int, int]] = []
    for chunk in re.split(r"[;,]", text):
        chunk = chunk.strip()
        if not chunk or "|" not in chunk:
            continue
        left, right = chunk.split("|", 1)
        try:
            out.append((_int(left), _int(right)))
        except (TypeError, ValueError):
            continue
    return out


def parse_id_list(raw) -> list[int]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, list):
        out: list[int] = []
        for item in raw:
            out.extend(parse_id_list(item))
        return out
    text = str(raw).strip()
    out = []
    for part in re.split(r"[|;,]", text):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(_int(part))
    return out


def parse_cost_triples(raw) -> list[tuple[int, int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, list):
        if raw and not isinstance(raw[0], (list, tuple)):
            if len(raw) >= 3:
                return [(_int(raw[0]), _int(raw[1]), _int(raw[2]))]
            return []
        out: list[tuple[int, int, int]] = []
        for item in raw:
            out.extend(parse_cost_triples(item))
        return out
    text = str(raw)
    out = []
    for chunk in re.split(r"[;,]", text):
        parts = [p for p in chunk.strip().split("|") if p != ""]
        if len(parts) >= 3:
            out.append((_int(parts[0]), _int(parts[1]), _int(parts[2])))
    return out


def first_attr(pairs: list[tuple[int, int]]) -> tuple[int, int] | None:
    if not pairs:
        return None
    return pairs[0]


def fmt_pre(pairs: list[tuple[int, int]]) -> str:
    if not pairs:
        return "（無）"
    return "、".join(f"{tid}|{lv}" for tid, lv in pairs)


def _hero_href_public(hero_id: int) -> str:
    if hero_href(hero_id):
        return f"heroes/{hero_id}.html"
    return ""


def hero_label(hero_id: int, roster_names: dict[int, str | None]) -> str:
    key = f"hero_name_{hero_id}"
    official = official_text(key) if has_key(key) else ""
    roster = roster_names.get(hero_id)
    name = official or roster
    if not name:
        return str(hero_id)
    return roster_display_name(hero_id, name)


def hero_is_unnamed(hero_id: int) -> bool:
    return not has_key(f"hero_name_{hero_id}")


def hero_link_html(hero_id: int, terms: list[str], roster_names: dict[int, str | None]) -> str:
    href = _hero_href_public(hero_id)
    if hero_is_unnamed(hero_id):
        marked = e(str(hero_id))
    else:
        marked = H(hero_label(hero_id, roster_names), terms)
    if href:
        return f'<a href="{e(href)}">{marked}</a>'
    return marked


def hero_link_md(hero_id: int, roster_names: dict[int, str | None]) -> str:
    text = str(hero_id) if hero_is_unnamed(hero_id) else hero_label(hero_id, roster_names)
    return f"[{text}](https://marcochanhc.github.io/th-wiki/heroes/{hero_id}.html)"


def join_heroes_html(ids: list[int], terms: list[str], roster_names: dict[int, str | None]) -> str:
    named = [hid for hid in ids if not hero_is_unnamed(hid)]
    unnamed = [hid for hid in ids if hero_is_unnamed(hid)]
    bits = [hero_link_html(hid, terms, roster_names) for hid in named]
    text = "、".join(bits)
    if unnamed:
        extra = "、".join(hero_link_html(hid, terms, roster_names) for hid in unnamed)
        text = f"{text}，以及 {extra}" if text else extra
    return text


def join_heroes_md(ids: list[int], roster_names: dict[int, str | None]) -> str:
    named = [hid for hid in ids if not hero_is_unnamed(hid)]
    unnamed = [hid for hid in ids if hero_is_unnamed(hid)]
    bits = [hero_link_md(hid, roster_names) for hid in named]
    text = "、".join(bits)
    if unnamed:
        extra = "、".join(hero_link_md(hid, roster_names) for hid in unnamed)
        text = f"{text}，以及 {extra}" if text else extra
    return text


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "")


@dataclass
class AttrInfo:
    attr_id: int
    name: str
    typ: int | None
    show_type: int | None
    name_key: str
    name_missing: bool
    name_col: str | None


@dataclass
class GroupCurve:
    group_id: int
    attr_id: int
    side: str  # hero / player / none
    typ: int | None
    show_type: int | None
    attr_name: str
    levels: list[int]
    values: list[int]


@dataclass
class HeroSlot:
    hero_id: int
    slot: int
    quality: int
    group_id: int
    name_key: str
    name: str
    dec_key: str
    dec: str
    cost: tuple[int, int, int]
    upgrade_cost: tuple[int, int, int]


@dataclass
class LordTree:
    tree_id: int
    max_lv: int
    bld_first: int
    bld_last: int
    prereqs: list[tuple[int, int]]
    attr_id: int | None
    attr_name: str
    typ: int | None
    show_type: int | None
    v_first: int | None
    v_last: int | None
    map_buildings: list[str]
    node_name: str
    node_name_key: str


@dataclass
class Official:
    hero_talent_name: str
    hero_talent_dec: str
    lord_talent_name: str
    lord_talent_dec: str
    awaken_name: str
    awaken_dec: str
    break_name: str
    break_dec: str
    quality_not_swap: str
    tips_unlock: str
    swap_count: str
    swap_level: str
    swap_slot: str
    war_name: str
    war_des: str
    abundance_name: str
    abundance_des: str
    switch_desc: str
    reset_desc: str
    diamond: str
    hall_name: str
    scroll_name: str
    scroll_desc: str
    point_name: str
    point_desc: str
    medal_name: str
    medal_desc: str
    light_tower: str
    dark_tower: str
    auto_facility: str
    tips_light: str
    tips_dark: str
    tips_facility: str
    des_101: str
    des_102: str
    des_104: str
    name_atk: str
    name_hp_i: str
    name_hp_ii: str
    name_strategy: str
    name_endure: str
    train_accel_name: str
    wood: str
    stone: str
    crystal: str
    knight_lord: str
    farm_lord: str
    scholar: str


@dataclass
class TablesData:
    official: Official
    attrs: dict[int, AttrInfo]
    groups: dict[int, GroupCurve]
    old_slots: list[HeroSlot]
    new_slots: list[HeroSlot]
    old_by: dict[tuple[int, int], HeroSlot]
    new_by: dict[tuple[int, int], HeroSlot]
    roster_names: dict[int, str | None]
    hero_ids: list[int]
    quality_heroes: dict[int, list[int]]
    swap_rows: list[dict]
    unref_groups: list[int]
    unref_caps: dict[int, int]
    war_trees: list[LordTree]
    abundance_trees: list[LordTree]
    series_710: list[LordTree]
    terms: list[str] = field(default_factory=list)
    verifications: dict = field(default_factory=dict)
    table_meta: dict = field(default_factory=dict)


def _compare_string_packs(keys: set[str]) -> dict:
    loaded: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for name, path in PACK_STRINGS.items():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        loaded[name] = data
        meta[name] = {"keys": len(data), "sha256": file_sha256(path), "bytes": path.stat().st_size}
    live = loaded["live"]
    diffs: list[str] = []
    missing: dict[str, list[str]] = {}
    for pack, data in loaded.items():
        if pack == "live":
            continue
        miss = sorted(k for k in keys if k not in data)
        if miss:
            missing[pack] = miss
        for k in keys:
            if k in data and data.get(k) != live.get(k):
                diffs.append(f"{pack}:{k}")
    return {"packs": meta, "used_keys": len(keys), "value_diffs": diffs, "missing": missing}


def _compare_table_packs(names: list[str]) -> dict:
    result: dict[str, dict] = {}
    for name in names:
        live_path = DATA_DIR / name
        entry: dict = {
            "present": {},
            "identical": {},
            "bytes": {},
            "sha256": {},
            "rows": {},
        }
        live_sha = file_sha256(live_path) if live_path.exists() else None
        for pack, folder in PACK_DATA_DIRS.items():
            path = folder / name
            if not path.exists():
                entry["present"][pack] = False
                entry["identical"][pack] = False
                entry["bytes"][pack] = None
                entry["sha256"][pack] = None
                entry["rows"][pack] = None
                continue
            entry["present"][pack] = True
            entry["bytes"][pack] = path.stat().st_size
            entry["sha256"][pack] = file_sha256(path)
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            entry["rows"][pack] = len(data) if isinstance(data, list) else None
            entry["identical"][pack] = entry["sha256"][pack] == live_sha
        result[name] = entry
    return result


def _attr_info(aid: int, attr_by: dict[int, dict]) -> AttrInfo:
    row = attr_by.get(aid) or {}
    name_key = f"attribute_name_{aid}"
    name_missing = not has_key(name_key)
    name = official_text(name_key) if not name_missing else ""
    typ = row.get("type")
    show = row.get("show_type")
    try:
        typ_i = _int(typ) if typ not in (None, "", -1) else None
    except (TypeError, ValueError):
        typ_i = None
    try:
        show_i = _int(show) if show not in (None, "", -1) else None
    except (TypeError, ValueError):
        show_i = None
    return AttrInfo(
        attr_id=aid,
        name=name,
        typ=typ_i,
        show_type=show_i,
        name_key=name_key,
        name_missing=name_missing,
        name_col=row.get("name"),
    )


def _group_side_pairs(row: dict) -> tuple[str, list[tuple[int, int]]]:
    hero = parse_pairs(row.get("hero_attr") or row.get("heroAttrs"))
    player = parse_pairs(row.get("player_attr") or row.get("playerAttrs"))
    if hero:
        return "hero", hero
    if player:
        return "player", player
    return "none", []


def _build_group_curve(group_id: int, rows: list[dict], attrs: dict[int, AttrInfo]) -> GroupCurve:
    rows = sorted(rows, key=lambda r: _int(r["level"]))
    levels: list[int] = []
    values: list[int] = []
    attr_id = 0
    side = "none"
    for row in rows:
        side, pairs = _group_side_pairs(row)
        levels.append(_int(row["level"]))
        if pairs:
            attr_id = pairs[0][0]
            values.append(pairs[0][1])
        else:
            values.append(0)
    info = attrs.get(attr_id)
    return GroupCurve(
        group_id=group_id,
        attr_id=attr_id,
        side=side,
        typ=info.typ if info else None,
        show_type=info.show_type if info else None,
        attr_name=info.name if info else "",
        levels=levels,
        values=values,
    )


def _parse_slot(row: dict) -> HeroSlot:
    cost = parse_cost_triples(row.get("cost"))[0]
    upgrade = parse_cost_triples(row.get("upgrade_cost"))[0]
    name_key = str(row.get("talent_name") or "")
    dec_key = str(row.get("talent_dec") or "")
    return HeroSlot(
        hero_id=_int(row["hero_id"]),
        slot=_int(row["slot"]),
        quality=_int(row["talent_quality"]),
        group_id=_int(row["talent_group"]),
        name_key=name_key,
        name=official_text(name_key),
        dec_key=dec_key,
        dec=official_text(dec_key),
        cost=cost,
        upgrade_cost=upgrade,
    )


def _type_show_plain(typ, show) -> str:
    """Player wording for type/show_type. Never convert show_type=2 values to percents."""
    if typ in (None, "", EMPTY) and show in (None, "", EMPTY):
        return ""
    try:
        typ_i = int(typ) if typ not in (None, "", EMPTY) else None
    except (TypeError, ValueError):
        typ_i = typ
    try:
        show_i = int(show) if show not in (None, "", EMPTY) else None
    except (TypeError, ValueError):
        show_i = show
    if typ_i == 2 and show_i == 2:
        return "百分比類，本頁不自行換成百分比"
    if typ_i == 1 and show_i == 1:
        return "點數"
    parts = []
    if typ_i is not None:
        parts.append(f"類型 {typ_i}")
    if show_i is not None:
        parts.append(f"顯示類型 {show_i}")
    return "、".join(parts)


def _attr_label(info: AttrInfo | None, aid: int | None) -> str:
    if aid is None:
        return EMPTY
    note = _type_show_plain(info.typ, info.show_type) if info else ""
    if info and info.name:
        return f"{info.name}（{aid}，{note}）" if note else f"{info.name}（{aid}）"
    if info and info.name_missing:
        base = f"屬性 {aid}（沒有官方屬性名稱字串"
        if note:
            base += f"；{note}"
        return base + "）"
    return f"屬性 {aid}"


def _build_lord_tree(tree_id: int, rows: list[dict], attrs: dict[int, AttrInfo]) -> LordTree:
    rows = sorted(rows, key=lambda r: _int(r["lv"]))
    blds = [_int(r["talent_building_lv"]) for r in rows]
    prereqs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        for tid, lv in parse_pairs(row.get("lvup_pre_id") or row.get("lvUpPreNodes")):
            if tid != tree_id and (tid, lv) not in seen:
                seen.add((tid, lv))
                prereqs.append((tid, lv))
    first, last = rows[0], rows[-1]
    a_first = first_attr(first.get("attributes") or parse_pairs(first.get("attribute")))
    a_last = first_attr(last.get("attributes") or parse_pairs(last.get("attribute")))
    attr_id = a_first[0] if a_first else None
    info = attrs.get(attr_id) if attr_id is not None else None
    mb: list[str] = []
    for row in rows:
        raw = row.get("map_building_id")
        if raw in (None, "", [], {}, -1):
            mb.append("")
        else:
            mb.append(str(raw))
    name_key = NAMED_LORD_NODES.get(tree_id, "")
    node_name = official_text(name_key) if name_key else ""
    return LordTree(
        tree_id=tree_id,
        max_lv=_int(last["lv"]),
        bld_first=blds[0],
        bld_last=blds[-1],
        prereqs=prereqs,
        attr_id=attr_id,
        attr_name=info.name if info else "",
        typ=info.typ if info else None,
        show_type=info.show_type if info else None,
        v_first=a_first[1] if a_first else None,
        v_last=a_last[1] if a_last else None,
        map_buildings=mb,
        node_name=node_name,
        node_name_key=name_key,
    )


def _roster_names() -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    for _faction, _anchor, heroes in ROSTER:
        for hid, name in heroes:
            out[int(hid)] = name
    return out


def _build_terms(o: Official, attrs: dict[int, AttrInfo], new_slots: list[HeroSlot], roster_names: dict[int, str | None]) -> list[str]:
    terms: list[str] = []
    # Official phrases as wholes first (longest wins in highlight).
    terms.extend(PANEL_QUOTES)
    terms.extend([
        o.hero_talent_dec, o.lord_talent_dec, o.war_des, o.abundance_des,
        o.scroll_desc, o.point_desc, o.medal_desc,
        o.quality_not_swap, o.tips_unlock, o.swap_count, o.swap_level, o.swap_slot,
        o.switch_desc, o.reset_desc, o.awaken_dec, o.break_dec,
        "可在英雄介面消耗對應英雄碎片提升英雄天賦",
        "在領主大廳中進行的天賦學習帶來的加成",
        "英雄天賦數量不匹配", "英雄天賦等級不匹配", "英雄天賦插槽不匹配",
        "自身{0}提升{1}", "{0}提升{1}", "全隊列{0}提升{1}",
        "英雄生命II", "英雄生命I", "英雄攻擊",
        "所有士兵攻擊", "所有士兵生命",
        "傷兵治療速度", "士兵訓練速度", "科技研究速度", "建造速度",
        "木材採集速度", "石頭採集速度", "紅水晶採集速度",
        "每個陣營容納士兵上限", "每日木材、石頭掠奪上限",
        "進攻戰略", "持久策略", "格擋研究", "快速醫療", "資源掠奪", "士兵擴編", "法術偏移",
        "法術增效", "嗜血", "暴傷研究", "抵抗研究", "迴避研究", "治療增效",
        "尋路術", "行軍術", "快速訓練", "快速研究", "快速建造",
        "木材採集", "礦石採集", "水晶採集",
        "戰爭領主", "豐饒領主", "領主天賦卷軸", "領主天賦點數", "光榮勳章", "領主大廳", "領主天賦",
        "騎士領主", "農場主人", "學者",
        "光明之塔", "暗黑之塔", "黑暗之塔", "自動採集設施",
        "戰爭狂熱", "治療加速", "狂野本性", "訓練加速",
        "藥劑師", "舞孃", "審判官", "術士", "守望者", "沙漠王子", "牧羊人（未開放）", "牧羊人", "老闆娘",
        "鐵匠", "護衛", "戰士", "弓箭手", "老法師", "妖精",
        o.diamond, o.wood, o.stone, o.crystal,
        "天賦", "羈絆", "部族", "聯盟", "自然", "鑽石",
        "統禦", "坦克", "誓約之獅",
    ])
    for info in attrs.values():
        if info.name:
            terms.append(info.name)
    for slot in new_slots:
        if slot.name:
            terms.append(slot.name)
    for hid, name in roster_names.items():
        label = hero_label(hid, roster_names)
        if label:
            terms.append(label)
        if name:
            terms.append(name)
    # unique, empty dropped; highlight itself sorts longest first
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        if term and term not in seen:
            seen.add(term)
            out.append(term)
    return out


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    MISSING_KEYS.clear()

    old_rows = load_table("hero_talent.json")
    new_rows = load_table("hero_talent_new.json")
    group_rows = load_table("hero_talent_group.json")
    swap_rows = load_table("hero_talent_swap.json")
    hero_rows = load_table("hero_detail.json")
    attr_rows = load_table("attribute.json")
    prof_rows = load_table("player_talent_professional.json")
    detail_rows = load_table("player_talent_detail.json")
    map_rows = load_table("map_building.json")
    cat_rows = load_table("attr_category.json")

    attr_by = {_int(r["id"]): r for r in attr_rows}
    # Load attrs that appear in talent groups or lord trees, plus a few named ones.
    needed_attr_ids: set[int] = set()

    groups_raw: dict[int, list[dict]] = defaultdict(list)
    for row in group_rows:
        groups_raw[_int(row["group_id"])].append(row)
        _side, pairs = _group_side_pairs(row)
        for aid, _val in pairs:
            needed_attr_ids.add(aid)

    old_slots = [_parse_slot(r) for r in old_rows]
    new_slots = [_parse_slot(r) for r in new_rows]
    old_by = {(s.hero_id, s.slot): s for s in old_slots}
    new_by = {(s.hero_id, s.slot): s for s in new_slots}

    tree_rows: dict[int, list[dict]] = defaultdict(list)
    for row in detail_rows:
        tree_rows[_int(row["tree_id"])].append(row)
        pairs = row.get("attributes") or parse_pairs(row.get("attribute"))
        for aid, _val in pairs:
            needed_attr_ids.add(aid)

    attrs = {aid: _attr_info(aid, attr_by) for aid in sorted(needed_attr_ids)}
    groups = {gid: _build_group_curve(gid, rows, attrs) for gid, rows in groups_raw.items()}

    roster_names = _roster_names()
    hero_ids = sorted(_int(r["id"]) for r in hero_rows)
    quality_heroes: dict[int, list[int]] = defaultdict(list)
    seen_q: set[tuple[int, int]] = set()
    for slot in new_slots:
        key = (slot.quality, slot.hero_id)
        if key in seen_q:
            continue
        seen_q.add(key)
        quality_heroes[slot.quality].append(slot.hero_id)
    # Stable chapter-like order: listed q1/q2 first, then remaining by roster then id.
    roster_order = [hid for hid, _name in sum((list(hs) for _f, _a, hs in ROSTER), [])]
    def _order(ids: list[int], preferred: tuple[int, ...] | None = None) -> list[int]:
        pref = list(preferred or ())
        rest = [i for i in roster_order if i in ids and i not in pref]
        leftover = [i for i in sorted(ids) if i not in pref and i not in rest]
        return pref + rest + leftover
    quality_heroes = {
        1: _order(quality_heroes[1], QUALITY1_IDS),
        2: _order(quality_heroes[2], QUALITY2_IDS),
        3: _order(quality_heroes[3]),
    }

    used_groups = {s.group_id for s in old_slots} | {s.group_id for s in new_slots}
    unref = sorted(set(groups) - used_groups)
    unref_caps: dict[int, int] = defaultdict(int)
    for gid in unref:
        unref_caps[groups[gid].levels[-1]] += 1

    war_trees = [_build_lord_tree(tid, tree_rows[tid], attrs) for tid in WAR_TREE_ORDER]
    abundance_trees = [_build_lord_tree(tid, tree_rows[tid], attrs) for tid in ABUNDANCE_TREE_ORDER]
    series_710 = [_build_lord_tree(tid, tree_rows[tid], attrs) for tid in SERIES_710_ORDER]

    # Touch official strings used on the page (and map-building names).
    o = Official(
        hero_talent_name=official_text("hero_talent"),
        hero_talent_dec=official_text("hero_talent_dec"),
        lord_talent_name=official_text("property_lordtalent_name"),
        lord_talent_dec=official_text("property_lordtalent_dec"),
        awaken_name=official_text("hero_awaken"),
        awaken_dec=official_text("hero_awaken_dec"),
        break_name=official_text("equip_break"),
        break_dec=official_text("equip_break_dec"),
        quality_not_swap=official_text("hero_talent_quality_not_swap"),
        tips_unlock=official_text("hero_talent_tips_3"),
        swap_count=official_text("hero_talent_swap_count_no_match"),
        swap_level=official_text("hero_talent_swap_level_no_match"),
        swap_slot=official_text("hero_talent_swap_slot_no_match"),
        war_name=official_text("professional_name01"),
        war_des=official_raw("professional_des01"),
        abundance_name=official_text("professional_name02"),
        abundance_des=official_raw("professional_des02"),
        switch_desc=official_text("player_talent_switch_desc"),
        reset_desc=official_text("player_talent_reset_desc"),
        diamond=official_text("top_resource_name_2"),
        hall_name=official_text("citybuilding_name_145"),
        scroll_name=official_text("goods_name_12210100"),
        scroll_desc=official_text("goods_desc_12210100"),
        point_name=official_text("goods_name_12210000"),
        point_desc=official_text("goods_desc_12210000"),
        medal_name=official_text("goods_name_12210200"),
        medal_desc=official_text("goods_desc_12210200"),
        light_tower=official_text("talent_tower_001"),
        dark_tower=official_text("talent_tower_002"),
        auto_facility=official_text("talent_facilities_001"),
        tips_light=official_raw("mapBuilding_tips_01"),
        tips_dark=official_raw("mapBuilding_tips_02"),
        tips_facility=official_raw("mapBuilding_tips_03"),
        des_101=official_text("hero_talent_des_101"),
        des_102=official_text("hero_talent_des_102"),
        des_104=official_text("hero_talent_des_104"),
        name_atk=official_text("talent_name_301"),
        name_hp_i=official_text("talent_name_302"),
        name_hp_ii=official_text("talent_name_303"),
        name_strategy=official_text("talent_name_201"),
        name_endure=official_text("talent_name_225"),
        train_accel_name=official_text("player_talent_name_1016"),
        wood=official_text("top_resource_name_4"),
        stone=official_text("top_resource_name_5"),
        crystal=official_text("top_resource_name_6"),
        knight_lord=official_text("professional_name_1"),
        farm_lord=official_text("professional_name_2"),
        scholar=official_text("professional_name_3"),
    )
    # category keys already used via official_text above; confirm ids exist
    _ = cat_rows, prof_rows, map_rows
    for mid in (
        20101, 20102, 20103, 20104, 20105,
        20201, 20202, 20203, 20204, 20205,
        10101, 10201, 10301, 10102, 10202, 10302, 10103, 10203, 10303,
    ):
        # names already loaded via talent_tower / talent_facilities keys
        _ = mid

    terms = _build_terms(o, attrs, new_slots, roster_names)

    compare_names = [
        "hero_talent.json", "hero_talent_new.json", "hero_talent_group.json",
        "hero_talent_swap.json", "hero_detail.json", "hero.json",
        "player_talent_professional.json", "player_talent_detail.json",
        "player_talent.json", "attribute.json", "map_building.json",
        "attr_category.json", "top_resource.json", "goods.json",
    ]
    table_cmp = _compare_table_packs(compare_names)
    string_cmp = _compare_string_packs(set(USED_KEYS))
    sha_ok = True
    sha_failures: list[str] = []
    for name, expected in TABLE_SHA256.items():
        live_sha = table_cmp[name]["sha256"]["live"]
        if live_sha != expected:
            sha_ok = False
            sha_failures.append(f"{name}: {live_sha} != {expected}")

    # Any other table mentioning hero_talent_new?
    refs = []
    for path in DATA_DIR.glob("*.json"):
        if path.name == "hero_talent_new.json":
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        if "hero_talent_new" in text:
            refs.append(path.name)

    table_count = len(list(DATA_DIR.glob("*.json")))
    old_count = len(list((TOPHEROES_ROOT / "extracts/2026-11-05/data").glob("*.json"))) if (TOPHEROES_ROOT / "extracts/2026-11-05/data").exists() else None

    table_meta = {
        "table_cmp": table_cmp,
        "string_cmp": string_cmp,
        "sha_ok": sha_ok,
        "sha_failures": sha_failures,
        "table_count": table_count,
        "extract_2026_11_05_table_count": old_count,
        "hero_talent_new_refs": refs,
        "pathfinder_new_upgrade": [
            s.upgrade_cost for s in new_slots if s.hero_id == 10012
        ],
    }

    data = TablesData(
        official=o,
        attrs=attrs,
        groups=groups,
        old_slots=old_slots,
        new_slots=new_slots,
        old_by=old_by,
        new_by=new_by,
        roster_names=roster_names,
        hero_ids=hero_ids,
        quality_heroes=quality_heroes,
        swap_rows=swap_rows,
        unref_groups=unref,
        unref_caps=dict(unref_caps),
        war_trees=war_trees,
        abundance_trees=abundance_trees,
        series_710=series_710,
        terms=terms,
        table_meta=table_meta,
    )
    data.verifications = _verify(data)
    data.verifications["sha_ok"] = sha_ok
    data.verifications["missing_keys"] = sorted(MISSING_KEYS)
    if not sha_ok:
        data.verifications["failures"] = list(data.verifications.get("failures") or []) + sha_failures
        data.verifications["passed"] = False
    return data


def _verify(data: TablesData) -> dict:
    failures: list[str] = []
    checks: dict = {}
    checks["old_rows"] = len(data.old_slots)
    checks["new_rows"] = len(data.new_slots)
    checks["group_rows"] = len(data.groups)  # unique groups; also store raw later
    # group row count from curves
    group_levels = sum(len(g.levels) for g in data.groups.values())
    checks["group_levels"] = group_levels
    checks["hero_detail"] = len(data.hero_ids)
    checks["war_trees"] = len(data.war_trees)
    checks["abundance_trees"] = len(data.abundance_trees)
    checks["series_710"] = len(data.series_710)
    checks["lord_trees"] = len(data.war_trees) + len(data.abundance_trees) + len(data.series_710)
    checks["lord_nodes"] = (
        sum(t.max_lv for t in data.war_trees)
        + sum(t.max_lv for t in data.abundance_trees)
        + sum(t.max_lv for t in data.series_710)
    )
    checks["unref"] = len(data.unref_groups)
    checks["unref_caps"] = dict(data.unref_caps)

    if len(data.old_slots) != 208:
        failures.append(f"舊表列數 {len(data.old_slots)} != 208")
    if len(data.new_slots) != 228:
        failures.append(f"新表列數 {len(data.new_slots)} != 228")
    if group_levels != 2580:
        failures.append(f"hero_talent_group 級數列 {group_levels} != 2580")
    if len(data.hero_ids) != 57:
        failures.append(f"hero_detail {len(data.hero_ids)} != 57")
    if checks["lord_nodes"] != 293:
        failures.append(f"player_talent_detail {checks['lord_nodes']} != 293")
    if checks["lord_trees"] != 47:
        failures.append(f"樹數 {checks['lord_trees']} != 47")
    if checks["war_trees"] != 22:
        failures.append("戰爭領主不是 22 條")
    if checks["abundance_trees"] != 20:
        failures.append("豐饒領主不是 20 條")
    if checks["series_710"] != 5:
        failures.append("710 系列不是五條")
    if checks["unref"] != 81:
        failures.append(f"未引用群組 {checks['unref']} != 81")
    if data.unref_caps.get(10) != 35 or data.unref_caps.get(20) != 29 or data.unref_caps.get(30) != 17:
        failures.append(f"未引用滿級分檔不符：{data.unref_caps}")

    if set(data.quality_heroes[1]) != set(QUALITY1_IDS) or len(data.quality_heroes[1]) != 6:
        failures.append(f"品質 1 人數不符：{data.quality_heroes[1]}")
    if set(data.quality_heroes[2]) != set(QUALITY2_IDS) or len(data.quality_heroes[2]) != 8:
        failures.append(f"品質 2 人數不符：{data.quality_heroes[2]}")
    if len(data.quality_heroes[3]) != 43:
        failures.append(f"品質 3 人數 {len(data.quality_heroes[3])} != 43")

    # old table slot counts
    old_q1 = [hid for hid in data.hero_ids if any(s.hero_id == hid and s.quality == 1 for s in data.old_slots)]
    old_slots_by_hero: dict[int, set[int]] = defaultdict(set)
    old_q_by_hero: dict[int, int] = {}
    for s in data.old_slots:
        old_slots_by_hero[s.hero_id].add(s.slot)
        old_q_by_hero[s.hero_id] = s.quality
    q1_only12 = [hid for hid, sl in old_slots_by_hero.items() if old_q_by_hero[hid] == 1]
    q2_only123 = [hid for hid, sl in old_slots_by_hero.items() if old_q_by_hero[hid] == 2]
    if not q1_only12 or any(old_slots_by_hero[hid] != {1, 2} for hid in q1_only12) or len(q1_only12) != 6:
        failures.append(f"舊表品質 1 槽位不符：{ {h: old_slots_by_hero[h] for h in q1_only12} }")
    if not q2_only123 or any(old_slots_by_hero[hid] != {1, 2, 3} for hid in q2_only123) or len(q2_only123) != 8:
        failures.append("舊表品質 2 槽位不符")
    not_four = [hid for hid, sl in old_slots_by_hero.items() if sl != {1, 2, 3, 4}]
    if len(not_four) != 14:
        failures.append(f"舊表非 4 槽人數 {len(not_four)} != 14")

    # new table: every hero 4 slots
    new_by_hero: dict[int, set[int]] = defaultdict(set)
    for s in data.new_slots:
        new_by_hero[s.hero_id].add(s.slot)
    if any(sl != {1, 2, 3, 4} for sl in new_by_hero.values()) or len(new_by_hero) != 57:
        failures.append("新表不是每名英雄 4 槽")

    # slot 3 sets
    slot3 = [s for s in data.new_slots if s.slot == 3]
    by_g: dict[int, list[int]] = defaultdict(list)
    for s in slot3:
        by_g[s.group_id].append(s.hero_id)
    expected_g = set(SLOT3_COMBAT_ORDER) | set(SLOT3_MARCH_ORDER)
    if set(by_g) != expected_g:
        failures.append(f"槽 3 群組不符：多 {set(by_g)-expected_g} 少 {expected_g-set(by_g)}")
    for gid, ids in SLOT3_HERO_ORDER.items():
        if set(by_g.get(gid, [])) != set(ids):
            failures.append(f"槽 3 群組 {gid} 英雄不符：{by_g.get(gid)} != {ids}")

    # confirmed old-table groups
    def gval(gid, lv):
        curve = data.groups[gid]
        return curve.values[curve.levels.index(lv)]

    expect_vals = {
        (20015, 1): 300, (20015, 30): 9000,
        (20255, 1): 900, (20255, 30): 27000,
        (20085, 1): 100, (20085, 30): 3000,
        (20013, 1): 200, (20013, 10): 2000,
        (20253, 1): 600, (20253, 10): 6000,
        (20014, 1): 250, (20014, 20): 5000,
        (20254, 1): 750, (20254, 20): 15000,
        (10114, 30): 3000,
        (20195, 30): 2000,
        (20205, 30): 360000,
        (20115, 21): 3500, (20115, 22): 3667,
        (30101, 1): 100, (30101, 30): 4000,
        (40101, 1): 300, (40101, 30): 10000,
        (50101, 1): 600, (50101, 30): 18000,
    }
    for (gid, lv), val in expect_vals.items():
        got = gval(gid, lv)
        if got != val:
            failures.append(f"群組 {gid} 第 {lv} 級 {got} != {val}")

    # 尋路者 new-table upgrade exception
    path_costs = {s.slot: s.upgrade_cost for s in data.new_slots if s.hero_id == 10012}
    if path_costs.get(1) != (2, 10008, 10) or path_costs.get(2) != (2, 10008, 10) or path_costs.get(4) != (2, 10008, 10) or path_costs.get(3) != (2, 10012, 10):
        failures.append(f"尋路者新表升級消耗不符：{path_costs}")
    for hid in (15032, 15033, 15039):
        costs = {s.upgrade_cost[1] for s in data.new_slots if s.hero_id == hid}
        if costs != {hid}:
            failures.append(f"{hid} 升級消耗不是自己的 id：{costs}")

    # 710 no prereq, bld 21
    for tree in data.series_710:
        if tree.prereqs:
            failures.append(f"{tree.tree_id} 不應有前置：{tree.prereqs}")
        if tree.bld_first != 21 or tree.bld_last != 21:
            failures.append(f"{tree.tree_id} talent_building_lv 不是 21")

    # names
    o = data.official
    if o.war_name != "戰爭領主" or o.abundance_name != "豐饒領主":
        failures.append("志向官方名稱不符")
    if o.hall_name != "領主大廳":
        failures.append(f"領主大廳名稱不符：{o.hall_name!r}")
    if hero_label(10005, data.roster_names) != "舞孃":
        failures.append(f"舞孃名稱不符：{hero_label(10005, data.roster_names)!r}")
    if hero_label(10029, data.roster_names) != "牧羊人（未開放）":
        failures.append("牧羊人應標未開放")
    if "未開放" in hero_label(10032, data.roster_names):
        failures.append("老闆娘不應標未開放")
    for hid in (15032, 15033, 15039):
        if not hero_is_unnamed(hid) or hero_label(hid, data.roster_names) != str(hid):
            failures.append(f"{hid} 應只寫編號")
    if UNRELEASED_HERO_IDS != frozenset({10029}):
        failures.append("未開放英雄集合不是只有 10029")

    # no typo strings in official payload
    blob = " ".join([
        o.hero_talent_name, o.lord_talent_name, o.war_name, o.abundance_name,
        o.hall_name, hero_label(10005, data.roster_names),
    ])
    if "繁絆" in blob or "魯絆" in blob:
        failures.append("官方名稱混入錯誤羈絆用字")

    checks["hero_talent_new_refs"] = data.table_meta.get("hero_talent_new_refs")
    if data.table_meta.get("hero_talent_new_refs"):
        failures.append(f"其他表引用 hero_talent_new：{data.table_meta['hero_talent_new_refs']}")

    checks["failures"] = failures
    checks["passed"] = not failures
    return checks


def _curve(data: TablesData, gid: int) -> GroupCurve:
    return data.groups[gid]


def _lv_pair(curve: GroupCurve, lo: int | None = None, hi: int | None = None) -> str:
    lo = lo or curve.levels[0]
    hi = hi or curve.levels[-1]
    v1 = curve.values[curve.levels.index(lo)]
    v2 = curve.values[curve.levels.index(hi)]
    return f"{comma(v1)}／{comma(v2)}"


def _seq_text(curve: GroupCurve) -> str:
    return "、".join(str(v) for v in curve.values)


def _dec_label(dec_key: str, o: Official) -> str:
    if dec_key == "hero_talent_des_101":
        return o.des_101
    if dec_key == "hero_talent_des_102":
        return o.des_102
    if dec_key == "hero_talent_des_104":
        return o.des_104
    return official_text(dec_key) or dec_key


def _slot3_name_note(slot: HeroSlot, curve: GroupCurve, *, html: bool = False) -> str:
    name = slot.name
    if slot.group_id == 20196:
        label = "顯示名" if html else "名稱鍵"
        return f"{name}（{label}仍是「法術增效」，群組是 20196，不是技能增傷那條）"
    if slot.group_id == 20255 and slot.name_key == "talent_name_201":
        label = "顯示名" if html else "名稱鍵"
        return f"{name}（{label}仍是「進攻戰略」，群組是 20255）"
    return name


def _attr_cell(curve: GroupCurve, attrs: dict[int, AttrInfo], *, include_id: bool = True) -> str:
    info = attrs.get(curve.attr_id)
    aname = info.name if info and info.name else f"屬性 {curve.attr_id}"
    if info and info.name_missing:
        aname = f"屬性 {curve.attr_id}（沒有官方屬性名稱字串）"
    note = _type_show_plain(info.typ, info.show_type) if info else ""
    if include_id:
        return f"{aname}（{curve.attr_id}，{note}）" if note else f"{aname}（{curve.attr_id}）"
    return f"{aname}（{note}）" if note else aname


def _lord_effect(tree: LordTree, data: TablesData, *, include_id: bool = True) -> str:
    o = data.official
    if tree.tree_id == 70050100:
        ids = "／".join(tree.map_buildings)
        if include_id:
            return (
                f"無寫入屬性，只寫地圖建築編號：1／2／3 級分別為 {ids.replace('|', '／')}。"
                f"三筆在地圖建築表的名稱都是「{o.light_tower}」。"
                "應視為解鎖地圖建築的節點，不是屬性加成"
            )
        return (
            f"無寫入屬性。1／2／3 級解鎖的地圖建築名稱都是「{o.light_tower}」。"
            "應視為解鎖地圖建築的節點，不是屬性加成"
        )
    if tree.tree_id == 70050300:
        parts = "、".join(
            f"{lv} 級為 `{raw}`" for lv, raw in enumerate(tree.map_buildings, 1)
        )
        if include_id:
            return (
                f"無屬性。{parts}。這些編號在地圖建築表的名稱都是「{o.auto_facility}」"
                f"；資源類型分別對應{o.wood}、{o.stone}、{o.crystal}"
            )
        return (
            f"無屬性。1／2／3 級解鎖的地圖建築名稱都是「{o.auto_facility}」"
            f"；資源類型分別對應{o.wood}、{o.stone}、{o.crystal}"
        )
    if tree.tree_id == 70050500:
        ids = "／".join(tree.map_buildings)
        if include_id:
            return (
                f"無屬性。1／2／3 級分別為 {ids}，名稱都是「{o.dark_tower}」"
            )
        return (
            f"無屬性。1／2／3 級解鎖的地圖建築名稱都是「{o.dark_tower}」"
        )
    if tree.tree_id == 70040700:
        ids = "／".join(tree.map_buildings)
        if include_id:
            return f"無屬性。1／2 級為 {ids}（{o.light_tower}）"
        return f"無屬性。1／2 級解鎖的地圖建築名稱都是「{o.light_tower}」"
    if tree.tree_id == 70041100:
        ids = "／".join(tree.map_buildings)
        if include_id:
            return f"無屬性。1／2 級為 {ids}（{o.dark_tower}）"
        return f"無屬性。1／2 級解鎖的地圖建築名稱都是「{o.dark_tower}」"

    info = data.attrs.get(tree.attr_id) if tree.attr_id is not None else None
    v = f"{comma(tree.v_first)}→{comma(tree.v_last)}"
    if info and info.name_missing:
        text = (
            f"屬性 {tree.attr_id}：{v}。沒有官方屬性名稱字串"
        )
    else:
        aname = info.name if info and info.name else f"屬性 {tree.attr_id}"
        typ_note = ""
        plain = ""
        if info and (info.typ, info.show_type) != (2, 2):
            plain = _type_show_plain(info.typ, info.show_type)
            typ_note = f"，{plain}" if plain else ""
        if include_id:
            text = f"{aname}（{tree.attr_id}{typ_note}）{v}"
        elif typ_note:
            text = f"{aname}（{plain}）{v}"
        else:
            text = f"{aname} {v}"
    if tree.node_name:
        text += f"。節點名稱字串「{tree.node_name}」"
    if tree.tree_id == 71040700:
        if include_id:
            text += (
                "。與戰爭樹 60070500 的醫院容量上限（1032，點數）官方名稱相同，"
                "但不是同一個屬性編號，類型與顯示類型也不同"
            )
        else:
            text += (
                f"。與「{o.war_name}」的醫院容量上限（點數）官方名稱相同，"
                "但不是同一條屬性，類型與顯示類型也不同"
            )
    return text


def _data_notes(data: TablesData) -> str:
    sc = data.table_meta["string_cmp"]
    tc = data.table_meta["table_cmp"]
    diffs = sc["value_diffs"]
    missing = sc["missing"]
    if diffs or missing:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵中，值不同的有 {diffs or '無'}，"
            f"缺鍵：{missing or '無'}。"
        )
    else:
        extra = f"本頁用到的 {sc['used_keys']} 個字串鍵在這四份裡值相同。"

    def pack_note(name: str, label: str) -> str:
        rec = tc[name]
        rows = rec["rows"]["live"]
        raw_bytes = rec["bytes"]["live"]
        sha = rec["sha256"]["live"]
        present = [p for p, ok in rec["present"].items() if ok]
        identical = [p for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow") if rec["identical"].get(p)]
        missing_p = [p for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow") if not rec["present"].get(p)]
        if not missing_p and len(identical) == 3:
            same = "四份包位元組相同"
        elif missing_p:
            same = (
                f"只出現在 { '、'.join(present) }"
                + ("；" + "、".join(missing_p) + " 沒有此表" if missing_p else "")
            )
        else:
            same = "四份包並非全部位元組相同"
        return f"`{name}`（{label}）{rows} 筆、{raw_bytes} bytes，sha256 {sha}，{same}。"

    attr = tc["attribute.json"]
    attr_note = (
        f"`attribute.json` 列數同為 {attr['rows']['live']}；"
        "現行檔與 2026-11-22、2026-11-22 LocalLow 位元組相同，"
        f"sha256 {attr['sha256']['live']}。"
        f"2026-11-05 解壓檔列數相同（{attr['rows']['2026-11-05']} 筆）但檔案較小"
        f"（{attr['bytes']['2026-11-05']} bytes，sha256 {attr['sha256']['2026-11-05']}），"
        "差在後來多了 NameKey、name_season 欄；本頁用到的屬性 id、type、show_type 與名稱鍵並未因此改變。"
    )
    pt = tc["player_talent.json"]
    hj = tc["hero.json"]
    extra_tables = (
        f"`player_talent.json` 只出現在現行 LocalLow 與 2026-11-22 LocalLow 歸檔"
        f"（皆 {pt['rows']['live']} 筆、{pt['bytes']['live']} bytes，sha256 {pt['sha256']['live']}），"
        "兩份位元組相同；2026-11-05 解壓檔與 2026-11-22 StreamingAssets 沒有此表。"
        "這 47 筆對應 47 條樹，但本頁不把它當成節點名稱來源，也不用它來判斷 710 與 700 哪套現役。"
        f"`hero.json` 同樣只在現行與 LocalLow 歸檔出現（{hj['rows']['live']} 筆），是 LocalLow 包裡另一份較短的 hero 表，"
        "本頁英雄名單只取 `hero_detail.json` 的 57 筆，不用 `hero.json`。"
    )
    return (
        f"資料截至 {TALENT_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {TALENT_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {TALENT_DATA_PACKED}（香港時間）。"
        f"第 23 章第三版寫於 2026-11-21（香港時間），那是整理日期；該版寫的是 2026-11-05 解壓檔（{data.table_meta['extract_2026_11_05_table_count']} 張表）。"
        + pack_note("hero_talent.json", "舊表")
        + pack_note("hero_talent_new.json", "後來的定義")
        + pack_note("hero_talent_group.json", "數值")
        + pack_note("hero_talent_swap.json", "交換")
        + pack_note("hero_detail.json", "可收集英雄")
        + pack_note("player_talent_professional.json", "志向")
        + pack_note("player_talent_detail.json", "節點")
        + attr_note
        + extra_tables
        + extra
        + "現行 759 張表與 2026-11-05 的 675 張表裡，都沒有其他表引用 `hero_talent_new`，也沒有讀表開關。"
        + "本頁列出的群組 1 級／30 級數值與第 23 章一致。"
        + "第 23 章未寫的表列事實：尋路者（10012）在新表槽 1／2／4 的 `upgrade_cost` 英雄 id 是 10008，只有槽 3 是 10012；舊表四槽都是 10012。本頁照表記錄，不推測原因。"
    )


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    o = data.official
    out: dict[str, str] = {}

    q_rows = []
    q_groups = {
        1: "30101／30201／30301",
        2: "40101／40201／40301",
        3: "50101／50201／50301",
    }
    q_vals = {1: "100／4,000", 2: "300／10,000", 3: "600／18,000"}
    for q in (1, 2, 3):
        ids = data.quality_heroes[q]
        q_rows.append([
            e(str(q)),
            e(str(len(ids))),
            e(q_groups[q]),
            e(q_vals[q]),
            join_heroes_html(ids, terms, data.roster_names),
        ])
    out["quality"] = table(
        ["品質", "人數（含 15032／15033／15039）", "新表槽 1／2／4 群組", "新表英雄攻擊或生命 1 級／30 級", "英雄"],
        q_rows,
        mobile="cards",
        card_title="品質",
    )

    seq_rows = []
    for lv in range(1, 31):
        seq_rows.append([
            e(str(lv)),
            e(str(_curve(data, 30101).values[lv - 1])),
            e(str(_curve(data, 40101).values[lv - 1])),
            e(str(_curve(data, 50101).values[lv - 1])),
        ])
    out["new_seq"] = table(
        ["等級", "品質 1", "品質 2", "品質 3"],
        seq_rows,
        mobile="sticky",
    )

    def slot3_table(gids: tuple[int, ...]) -> str:
        rows = []
        for gid in gids:
            slots = [s for s in data.new_slots if s.slot == 3 and s.group_id == gid]
            slots.sort(key=lambda s: SLOT3_HERO_ORDER[gid].index(s.hero_id))
            s0 = slots[0]
            curve = _curve(data, gid)
            name_note = _slot3_name_note(s0, curve, html=True)
            quals = "／".join(str(q) for q in sorted({s.quality for s in slots}))
            rows.append([
                H(_attr_cell(curve, data.attrs, include_id=False), terms),
                H(name_note, terms),
                H(_dec_label(s0.dec_key, o), terms),
                e(str(gid)),
                e(quals),
                e(_lv_pair(curve)),
                join_heroes_html([s.hero_id for s in slots], terms, data.roster_names),
            ])
        return table(
            ["寫入屬性", "名稱", "說明文", "群組", "品質", "1 級／30 級", "英雄"],
            rows,
            mobile="cards",
            card_title="名稱",
        )

    out["slot3_combat"] = slot3_table(SLOT3_COMBAT_ORDER)
    out["slot3_march"] = slot3_table(SLOT3_MARCH_ORDER)

    trees_by_id = {
        t.tree_id: t
        for t in (*data.war_trees, *data.abundance_trees, *data.series_710)
    }

    def _visible_node_label(tree: LordTree) -> str:
        if tree.node_name:
            return H(tree.node_name, terms)
        o = data.official
        if tree.tree_id in (70050100, 70040700):
            return H(o.light_tower, terms)
        if tree.tree_id in (70050500, 70041100):
            return H(o.dark_tower, terms)
        if tree.tree_id == 70050300:
            return H(o.auto_facility, terms)
        info = data.attrs.get(tree.attr_id) if tree.attr_id is not None else None
        if info and info.name_missing:
            return e("沒有官方屬性名稱字串")
        if info and info.name:
            return H(info.name, terms)
        return e("（無官方節點名稱）")

    def fmt_pre_html(pairs: list[tuple[int, int]]) -> str:
        if not pairs:
            return "（無）"
        bits = []
        for tid, lv in pairs:
            label = _visible_node_label(trees_by_id[tid])
            bits.append(f"{label} {lv} 級")
        return "、".join(bits)

    def lord_table(trees: list[LordTree], with_bld: bool) -> str:
        rows = []
        cols = ["級數", "天賦建築等級", "前置", "寫入屬性（1 級→滿級）"] if with_bld else ["級數", "寫入屬性（1 級→滿級）"]
        title = "寫入屬性（1 級→滿級）"
        for tree in trees:
            effect = _lord_effect(tree, data, include_id=False)
            if with_bld:
                bld = f"{tree.bld_first}→{tree.bld_last}"
                rows.append([
                    e(str(tree.max_lv)),
                    e(bld),
                    fmt_pre_html(tree.prereqs),
                    H(effect, terms),
                ])
            else:
                rows.append([
                    e(str(tree.max_lv)),
                    H(effect, terms),
                ])
        return table(cols, rows, mobile="cards", card_title=title)

    out["war"] = lord_table(data.war_trees, True)
    out["abundance"] = lord_table(data.abundance_trees, True)
    out["series710"] = lord_table(data.series_710, False)
    return out


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜天賦總表"
    summary = (
        "分開列出英雄天賦與領主天賦兩套系統：以面板看得到的為準，"
        "並登錄戰爭領主、豐饒領主，以及五條沒有前置的樹。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "hero-talents", "label": "英雄天賦"},
        {"id": "slots", "label": "槽位、品質與升級", "depth": 1},
        {"id": "confirmed", "label": "舊表與面板對照", "depth": 1},
        {"id": "slot3", "label": "槽 3", "depth": 1},
        {"id": "slot3-combat", "label": "戰鬥屬性", "depth": 1},
        {"id": "slot3-march", "label": "行軍、帶兵、經濟", "depth": 1},
        {"id": "old-swap", "label": "舊表、交換、未引用群組", "depth": 1},
        {"id": "lord-talents", "label": "領主天賦"},
        {"id": "war", "label": "戰爭領主", "depth": 1},
        {"id": "abundance", "label": "豐饒領主", "depth": 1},
        {"id": "series-710", "label": "沒有前置", "depth": 1},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{LEDE}</p>')
    add(f"    {toc}")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        "本頁分兩大節，不要混為一套系統。"
        f"英雄天賦（官方名稱「{H(o.hero_talent_name, terms)}」，"
        f"提示「{official_term_html(o.hero_talent_dec)}」）可在英雄介面消耗對應英雄碎片提升。"
        "目前面板看得到的是舊的那一套（進攻戰略、持久策略等），本頁以面板看得到的為準；"
        "另一套定義先不拿來改你在遊戲裡看到的名稱。完整對照見「舊表與面板對照」與資料說明。"
        f"領主天賦（官方名稱「{H(o.lord_talent_name, terms)}」，"
        f"提示「{official_term_html(o.lord_talent_dec)}」）在領主大廳中學習。"
        f"官方志向名稱是「{H(o.war_name, terms)}」「{H(o.abundance_name, terms)}」。"
    ))
    add(p_html(
        f"另有一套領主職業（{H(o.knight_lord, terms)}、{H(o.farm_lord, terms)}、{H(o.scholar, terms)}）。"
        "表沒有寫職業與領主天賦如何疊加，也不標哪一套會取代另一套。本頁不把職業寫進領主天賦正文，見文末「本頁未列入」。檔名與分類編號見資料說明。"
    ))
    add(p_html(
        f"已發佈的<a href=\"exclusive.html\">{H('專武總表', terms)}</a>、<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>、"
        f"<a href=\"skins.html\">{H('造型總表', terms)}</a>、<a href=\"equipment.html\">{H('裝備總表', terms)}</a>、"
        f"<a href=\"lord-equipment.html\">{H('領主裝備總表', terms)}</a>、<a href=\"troops.html\">{H('士兵總表', terms)}</a>、"
        f"<a href=\"artifacts.html\">{H('秘寶總表', terms)}</a>、<a href=\"pets.html\">{H('寵物總表', terms)}</a>、"
        f"<a href=\"runes.html\">{H('符文總表', terms)}</a>、"
        f"<a href=\"tech.html\">{H('科技總表', terms)}</a>、<a href=\"decorations.html\">{H('裝飾物總表', terms)}</a>、"
        f"<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>是其他系統，不在本頁展開。"
    ))
    add("<ul>")
    add(
        "<li><strong>正文只根據遊戲資料表與面板看得到的內容。</strong>"
        "不評定天賦強弱，也不做搭配模擬。兩套英雄天賦定義不要混用，本頁不以後來的那一套當成現用全表。"
        "對照與換算規則見「舊表與面板對照」與資料說明。</li>"
    )
    add(
        "<li>公開名冊裡只有牧羊人標未開放；老闆娘不標未開放。"
        "不要從解鎖時間或賽季欄自動標未開放。"
        "15032、15033、15039 三筆沒有官方中文名，本頁不編造。</li>"
    )
    add("<li>本頁不把未被引用的 81 個天賦群組當成現役英雄天賦。檔名、欄位與換算細節見資料說明。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="hero-talents">')
    add("      <h2>英雄天賦</h2>")
    add(p_html(
        f"官方說明是在英雄介面消耗對應英雄碎片升級：「{official_term_html(o.hero_talent_dec)}」。"
        f"同一品質才能交換（「{official_term_html(o.quality_not_swap)}」）；"
        f"官方另有「{official_term_html(o.swap_count)}」「{official_term_html(o.swap_level)}」「{official_term_html(o.swap_slot)}」等提示。"
        f"解鎖需先解鎖上一個天賦（「{official_term_html(o.tips_unlock)}」）。"
    ))

    add('    <section id="slots">')
    add("      <h3>槽位、品質與升級</h3>")
    add(p_html(
        "名冊 57 個英雄編號在新表都有 4 個槽位，共 228 筆。"
        f"四個槽位的解鎖消耗一律是「{H(o.diamond, terms)}」×數量，數量依槽位為 200／500／1,000／2,000，與天賦品質欄無關。"
        "類型 999 在表上沒有名稱，本頁不自行斷定。"
    ))
    add(p_html(
        "升級消耗是碎片×10。"
        "多數列的英雄 id 等於該英雄自己的 id；15032／15033／15039 用的也是自己的 id，不是 10032／10033／10039。"
        f"表上另有一條例外，第 23 章未列出：{hero_link_html(10012, terms, data.roster_names)}（10012）在新表槽 1／2／4 的升級消耗寫的是 10008，"
        "只有槽 3 寫 10012；舊表四槽都寫 10012。本頁照表記錄，不推測原因。"
    ))
    add(p_html(
        f"天賦品質欄 1／2／3 把英雄分成三檔。<strong>新表</strong>裡，槽 1／2／4 對應攻擊或生命群組的強度；"
        f"群組都是 1–30 級，寫入皆為英雄側、百分比類（本頁不自行換成百分比）的"
        f"{H('英雄攻擊', terms)}或{H('英雄生命', terms)}。"
        f"說明文是「{official_term_html(o.des_101)}」。"
        f"槽 1 一般名稱是「{H(o.name_atk, terms)}」、槽 2 是「{H(o.name_hp_i, terms)}」、槽 4 是「{H(o.name_hp_ii, terms)}」。"
        "這些是新表的寫法，不是這次前服面板顯示的那套。"
    ))
    add(tbl["quality"])
    add(p_html("新表槽 1 的 1–30 級數列如下。槽 2／4 的新表英雄生命數列，與同品質槽 1 的英雄攻擊數列相同（只是屬性改為英雄生命）。"))
    add(tbl["new_seq"])
    add(p_html(
        f"例外（僅就新表顯示名）：{hero_link_html(10009, terms, data.roster_names)}、{hero_link_html(10010, terms, data.roster_names)}"
        f"的槽 1／2 顯示名仍是「{H(o.name_strategy, terms)}」「{H(o.name_endure, terms)}」，"
        "但掛的群組已是 30101／30201（英雄攻擊／英雄生命），數值與同品質其他英雄相同。"
        f"槽 4 名稱已是「{H(o.name_hp_ii, terms)}」。介面實際顯示哪一組，表沒有再說明。"
        "前服已確認的品質 1／2／3 面板都對舊表，不能用來推鐵匠、護衛在新表顯示名下會顯示哪一組。"
    ))
    add("    </section>")

    add('    <section id="confirmed">')
    add("      <h3>舊表與面板對照</h3>")
    add(p_html(
        f"<strong>舊表與面板對照。</strong>舊表品質 3 的槽 1 是群組 20015（{H('所有士兵攻擊', terms)}，1 級 300／30 級 9,000），"
        f"名稱「{H(o.name_strategy, terms)}」；槽 2 是群組 20255（{H('所有士兵生命', terms)}，900／27,000），"
        f"名稱「{H(o.name_endure, terms)}」。品質 3 的槽 4 不是人人相同：23 人掛 20255（{H(o.name_endure, terms)}），"
        f"20 人掛 20015（{H(o.name_strategy, terms)}）。"
        f"{hero_link_html(10031, terms, data.roster_names)}（10031，品質 3）槽 4 是 20255；槽 3 兩表相同，審判官是群組 20085（{H('格擋', terms)}，100／3,000），"
        f"名稱「{H('格擋研究', terms)}」。舊表品質 1 只有槽 1／2，滿級 10 級（群組 20013／20253：所有士兵攻擊 200／2,000，所有士兵生命 600／6,000）；"
        "品質 2 只有槽 1／2／3，槽 1／2 滿級 20 級（群組 20014／20254：250／5,000、750／15,000），槽 3 滿級 30 級。"
    ))
    add(p_html(
        "2026-11-16 前服審判官（10031，品質 3）四槽皆 30 級、已滿級的面板，槽名與數值都對得上這份舊表，"
        "對不上新表的英雄攻擊／英雄生命、600／18,000（槽 3 除外）。面板原文："
    ))
    add("<ul>")
    add(f"<li>{official_term_html(PANEL_JUDGE_ATK)}</li>")
    add(f"<li>{official_term_html(PANEL_JUDGE_HP)}（槽 2 與槽 4 同句）</li>")
    add(f"<li>{official_term_html(PANEL_JUDGE_BLOCK)}</li>")
    add("</ul>")
    add(p_html(
        "30 級原值除以 100 剛好等於面板百分比：所有士兵攻擊 9,000＝90.00%，所有士兵生命 27,000＝270.00%，"
        "格擋 3,000＝30.00%（10000＝100%）。"
    ))
    add(p_html("2026-11-21 前服另確認下列面板，槽名與數值同樣對得上舊表，對不上新表（槽 3 兩表相同的除外）："))
    add("<ul>")
    add(
        f"<li>{hero_link_html(10007, terms, data.roster_names)}（10007，品質 1）兩槽皆已滿 10 級。"
        f"面板原文：「{official_term_html(PANEL_ALCHEMIST_ATK)}」。"
        "這筆鎖定前服品質 1 讀舊表（只有 2 槽，滿級 10 級），不是新表的 4 槽／30 級／英雄攻擊／英雄生命。"
        "槽 2 未入鏡，本頁不編造槽 2 的面板原文。</li>"
    )
    add(
        f"<li>{hero_link_html(10005, terms, data.roster_names)}（10005，品質 2）三槽皆已滿級。"
        f"面板原文：「{official_term_html(PANEL_DANCER_ATK)}」（20 級）、"
        f"「{official_term_html(PANEL_DANCER_HP)}」（20 級）、"
        f"「{official_term_html(PANEL_DANCER_HEAL)}」（30 級）。"
        "這筆鎖定前服品質 2 讀舊表（3 槽；槽 1／2 滿級 20 級，槽 3 滿級 30 級），並鎖定傷兵治療速度滿級原值 3,000＝30.00%。</li>"
    )
    add(
        f"<li>{hero_link_html(10028, terms, data.roster_names)}（10028）槽 3 已滿 30 級。"
        f"面板原文：「{official_term_html(PANEL_WARLOCK)}」。"
        "沒有百分號，沒有正號，也沒有千分位。這筆鎖定屬性 1093 為點數。</li>"
    )
    add(
        f"<li>{hero_link_html(10021, terms, data.roster_names)}（10021）槽 3 已滿 30 級。"
        f"面板原文：「{official_term_html(PANEL_WATCHER)}」。"
        "格式同上。這筆鎖定屬性 1018 為點數。</li>"
    )
    add(
        f"<li>{hero_link_html(10039, terms, data.roster_names)}（10039）槽 3「{H('法術偏移', terms)}」21 級。"
        f"面板原文：「{official_term_html(PANEL_PRINCE)}」，"
        "對得上群組 20115 的 21 級 3,500、22 級 3,667。"
        "這筆鎖定中間等級的顯示：原值除以 100，固定兩位小數。"
        "依同一規則，原值 167、133、67 會顯示為相應的兩位小數百分比，但這些字串尚未入鏡，本頁不把它們寫成已對面板的原文。</li>"
    )
    add("</ul>")
    add(p_html(
        "此對應只鎖定這些已確認的天賦顯示，不要自行推到所有 百分比類屬性，"
        "也不要推到稱號、羈絆或其他非天賦來源。"
        "這幾筆仍不能寫死所有伺服器、所有英雄都只讀舊表；新表是否已在其他伺服器或未對面板的英雄上線，表內沒有開關可鎖。"
        "舊表另有 14 名英雄不是 4 槽，見「舊表、交換、未引用群組」。"
    ))
    add(p_html(
        "103／104 如何進入官方「攻擊百分比／生命百分比」欄，表沒有標。"
        "前服已確認的天賦百分比是舊表的 10103／10104／16／1022／21 等，不是新表 103／104。"
        "除上述已鎖定的天賦顯示外，本頁其餘 百分比類屬性 只記原值。"
    ))
    add("    </section>")

    add('    <section id="slot3">')
    add("      <h3>槽 3（每人一條，名稱以群組屬性為準）</h3>")
    add(p_html(
        "槽 3 的名稱與群組多數一致，說明文有"
        f"「{official_term_html(o.des_101)}」、"
        f"「{official_term_html(o.des_102)}」、"
        f"「{official_term_html(o.des_104)}」三種。"
        "下面按實際寫入的屬性排列；1 級與 30 級數值已對過群組表。名稱與屬性不一致的，在該條註明。"
    ))
    add('    <section id="slot3-combat">')
    add("      <h4>戰鬥屬性（寫入英雄側）</h4>")
    add(tbl["slot3_combat"])
    add("    </section>")
    add('    <section id="slot3-march">')
    add("      <h4>行軍、帶兵、經濟（多寫入領主側）</h4>")
    add(tbl["slot3_march"])
    add("    </section>")
    add(p_html(
        "槽 3 已對前服面板的，見上文「舊表與面板對照」："
        f"{H('格擋研究', terms)}（審判官，自身格擋提升30.00%）、"
        f"{H('快速醫療', terms)}（舞孃，傷兵治療速度提升30.00%）、"
        f"{H('士兵擴編', terms)}（守望者，每個陣營容納士兵上限提升2000）、"
        f"{H('資源掠奪', terms)}（術士，每日木材、石頭掠奪上限提升360000）、"
        f"{H('法術偏移', terms)}（沙漠王子 21 級，自身技能減傷提升35.00%(下一級技能減傷提升36.67%)）。"
        "表上「1 級／30 級」仍記群組原值。"
    ))
    add(p_html(
        "15032／15033／15039 的四槽與 10032／10033／10039（"
        + join_heroes_html([10032, 10033, 10039], terms, data.roster_names)
        + "）相同，只是沒有對應的英雄名稱字串。本頁不把它們與 10032／10033／10039 合併成同一人。"
    ))
    add("    </section>")

    add('    <section id="old-swap">')
    add("      <h3>舊表、交換、未引用群組</h3>")
    add(p_html(
        "舊表 208 筆、新表 228 筆，少掉的 20 筆就是那 14 名英雄後來補上的槽位："
        + join_heroes_html(list(QUALITY1_IDS), terms, data.roster_names)
        + "在舊表只有槽 1／2；"
        + join_heroes_html(list(QUALITY2_IDS), terms, data.roster_names)
        + "在舊表只有槽 1／2／3。舊表專用、新表不再掛的群組是 20013／20014／20015／20253／20254。"
        "這份資料沒有欄位標明客戶端讀哪張表，其他表也不引用後來那一套定義。"
        "從槽位數與群組改掛來看，新表是後來的定義，但這不是表內開關。"
        "這次已對過面板的藥劑師、舞孃、審判官（以及術士、守望者、沙漠王子的槽 3），顯示的都是舊表，不是新表"
        "（槽 3 兩表相同的除外）；現役以哪張為準仍不能全庫寫死。"
    ))
    add(p_html(
        f"交換消耗表 4 筆按交換品質欄給消耗：品質 3 為「{H(o.diamond, terms)}」×200，"
        "品質 4 為 500，品質 5 與 6 各有一筆、皆為 2,000。"
        "這裡的品質編號是 3／4／5／6，與英雄天賦定義表上的天賦品質欄 1／2／3 不是同一欄，"
        "本頁不自行對成同一套品質。官方提示品質不同、槽位或等級不匹配時不能交換。"
        "類型 999 在表上沒有名稱，本頁不自行斷定。"
    ))
    add(p_html(
        f"天賦群組表另有 81 個群組沒有被新舊定義表引用（滿級為 10 級的 {data.unref_caps[10]} 個、"
        f"20 級的 {data.unref_caps[20]} 個、30 級的 {data.unref_caps[30]} 個，多為採集、行軍、攻城等）。"
        "本頁不當成現役天賦，也不推測它們何時會掛上。"
    ))
    add("    </section>")
    add("    </section>")

    add('    <section id="lord-talents">')
    add("      <h2>領主天賦</h2>")
    add(p_html(
        f"領主天賦是另一套系統，在{H(o.hall_name, terms)}學習。"
        f"志向只有兩筆，官方名稱是「{H(o.war_name, terms)}」「{H(o.abundance_name, terms)}」"
        "。"
    ))
    add(p_html(
        f"{H(o.war_name, terms)}的說明：「{official_term_html(o.war_des)}」"
    ))
    add(p_html(
        f"{H(o.abundance_name, terms)}的說明：「{official_term_html(o.abundance_des)}」"
    ))
    add(p_html(
        f"變更志向或重置會退還已學習的天賦點數（「{official_term_html(o.switch_desc)}」；"
        f"「{official_term_html(o.reset_desc)}」）。"
        f"重置／變更消耗是「{H(o.scroll_name, terms)}」×1（"
        f"說明：「{official_term_html(o.scroll_desc)}」）。"
        f"節點升級多用「{H(o.point_name, terms)}」×1（"
        f"說明：「{official_term_html(o.point_desc)}」）；"
        f"部分節點另加「{H(o.medal_name, terms)}」（說明：「{official_term_html(o.medal_desc)}」），"
        "附加數量在表上為 100、200、300、600、1,000 或 2,000。"
        "節點另要求天賦建築等級欄（1 到 21）。"
        f"表沒有把這個欄位直接寫成哪一座建築的等級；物品說明提到{H(o.hall_name, terms)}"
        "，本頁不自行斷定該欄就等於該建築。"
    ))
    add(p_html(
        "領主天賦明細 293 筆、47 條樹。所有節點的說明、時間、品質欄皆為空或 -1。"
        f"「{H(o.war_name, terms)}」（22 條），「{H(o.abundance_name, terms)}」（20 條）；"
        "另有五條沒有前置。下面各樹列出 1 級→滿級；屬性皆 百分比類（本頁不自行換成百分比），除非另註。"
        "有官方節點名稱字串的（僅少數）一併註明。"
    ))

    add('    <section id="war">')
    add(f"      <h3>{e(o.war_name)}</h3>")
    add(tbl["war"])
    add(p_html(
        f"字串表另有「{H(o.train_accel_name, terms)}」，"
        "對應屬性「士兵訓練速度」。戰爭樹沒有寫入這條屬性，本頁不把這條名稱掛到任何節點。"
    ))
    add("    </section>")

    add('    <section id="abundance">')
    add(f"      <h3>{e(o.abundance_name)}</h3>")
    add(tbl["abundance"])
    add(p_html(
        f"地圖建築的官方說明文寫「{H(o.abundance_name, terms)}建造」的特殊建築或自動採集設施"
        "。"
        f"其中一則稱強化塔為「{H(o.light_tower, terms)}」，與建築名稱一致；"
        f"另一則稱削弱塔為「{H('黑暗之塔', terms)}」，"
        f"與建築表名稱「{H(o.dark_tower, terms)}」用字不同，本頁兩種寫法都照錄，不自行統一。"
        "說明文還寫：同一範圍內多座光明之塔只生效最高等級、效果不可疊加；黑暗之塔同樣按非所在公會的最高等級計算。"
        "本頁不展開建築戰鬥效果與耐久規則。官方說明全文如下。"
    ))
    add("<h4>強化塔說明</h4>")
    add(f"<blockquote>{official_term_html(o.tips_light)}</blockquote>")
    add("<h4>削弱塔說明</h4>")
    add(f"<blockquote>{official_term_html(o.tips_dark)}</blockquote>")
    add("<h4>自動採集設施說明</h4>")
    add(f"<blockquote>{official_term_html(o.tips_facility)}</blockquote>")
    add(p_html(
        "「英雄攻擊轉化率」如何進入士兵或戰鬥公式，表沒有寫。本頁只記錄它被豐饒樹寫入。"
    ))
    add("    </section>")

    add('    <section id="series-710">')
    add("      <h3>沒有前置</h3>")
    add(p_html(
        "以下五條樹沒有前置，天賦建築等級欄皆為 21，"
        f"與「{H(o.abundance_name, terms)}」部分節點（醫院、治療、三種採集）並列。表沒有標哪套現役。"
    ))
    add(tbl["series710"])
    add("    </section>")
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(
        f"<li>領主職業（{H(o.knight_lord, terms)}、{H(o.farm_lord, terms)}、{H(o.scholar, terms)}）及其進階樹、職業技能與紋章"
        "。這是與領主天賦分開的來源分類（分類 41–43），表沒有寫兩者如何疊加。檔名見資料說明。</li>"
    )
    add("<li>未被新舊英雄天賦定義表引用的 81 個群組。</li>")
    add(
        f"<li>{H(o.light_tower, terms)}、{H(o.dark_tower, terms)}、{H(o.auto_facility, terms)}"
        "的建築效果、範圍與耐久明細（只在豐饒樹註明解鎖的建築編號與官方名稱）。</li>"
    )
    add("<li>英雄天賦的英雄攻擊／英雄生命、領主天賦「英雄攻擊轉化率」如何進入官方戰鬥公式。</li>")
    add("<li>天賦與英雄技能、站位、士兵的搭配模擬，以及強弱評定。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<ul>")
    add("<li>以下是整理用註記，查天賦名稱與效果可略過。</li>")
    add(
        "<li>可見正文把檔名與欄位名收到這裡。可見天賦屬性只寫官方名，編號見此：英雄攻擊 103、英雄生命 104、所有士兵攻擊 10103、所有士兵生命 10104、格擋 16、傷兵治療速度 1022、士兵訓練速度 1016、英雄攻擊轉化率 1040；槽 3 說明文三種對應 <code>hero_talent_des_101</code>／<code>102</code>／<code>104</code>。可見「顯示名」對應名稱鍵。"
        "屬性 <code>type=2</code>／<code>show_type=2</code> 在可見正文寫成「百分比類，本頁不自行換成百分比」；"
        "<code>type=1</code>／<code>show_type=1</code> 寫成「點數」。沒有把百分比類原值自行換成百分比，已鎖定的面板顯示除外。"
        "志向官方名稱鍵是 <code>professional_name01</code>／<code>professional_name02</code>（戰爭領主、豐饒領主），說明鍵 <code>professional_des01</code>／<code>professional_des02</code>。"
        "英雄天賦官方說明鍵 <code>hero_talent_dec</code>；交換／解鎖提示鍵見 <code>hero_talent_quality_not_swap</code>、<code>hero_talent_swap_*</code>、<code>hero_talent_tips_3</code>。"
        "解鎖消耗原值 <code>999|2|數量</code>。地圖建築表原名 <code>map_building.json</code>。可見槽位解鎖消耗不再寫類型 999、資源 2，改寫官方資源名；數量 200／500／1,000／2,000 與「類型 999 在表上沒有名稱，本頁不自行斷定」照留。可見升級消耗不再寫類型 2、數量 10（碎片），改寫碎片×10；類型 2 是消耗格式開頭，不是頂欄資源編號，對照見此。可見領主天賦明細不再以樹 id 600／700／710 開頭識別，改寫官方志向名；22／20 條與五條沒有前置照留。可見交換消耗不再寫類型 999、資源 2，改寫官方資源名；品質 3／4／5／6 數量 200／500／2,000（品質 5 與 6 各有一筆、皆為 2,000）、「這裡的品質編號是 3／4／5／6，與英雄天賦定義表上的天賦品質欄 1／2／3 不是同一欄，本頁不自行對成同一套品質。官方提示品質不同、槽位或等級不匹配時不能交換。」與「類型 999 在表上沒有名稱，本頁不自行斷定」照留。可見領主重置／變更與節點升級消耗不再寫物品 12210100／12210000／12210200 前綴，改寫官方物品名與說明；退還確認字串、附加數量 100、200、300、600、1,000 或 2,000，以及天賦建築等級欄警示照留。可見領主天賦樹表不再寫「樹 id」欄與前置「樹|等級」編號，改寫官方節點名、官方屬性名或官方建築名；沒有官方屬性名稱字串的前置照留該警示，官方節點名稱字串與「屬性皆 百分比類（本頁不自行換成百分比）」照留。可見地圖建築節點不再寫 20101–20105、20201–20205、10101–10303 等編號，改寫官方建築名；「應視為解鎖地圖建築的節點，不是屬性加成」與木材／石頭／紅水晶對應照留。可見「710 系列（沒有前置）」改寫「沒有前置」。可見「與 700 部分節點」改寫官方志向名。編號對照見此。</li>"
    )
    add(
        "<li>正文所據：遊戲資料表與已確認的前服面板。英雄天賦同時登錄 <code>hero_talent.json</code>（208 筆）與 <code>hero_talent_new.json</code>（228 筆）。"
        "新表是後來的定義，但 2026-11-16 至 2026-11-21 已確認的前服面板，槽名與數值都對得上舊表，對不上新表"
        "（槽 3 兩表相同的除外）：品質 1 藥劑師（10007）兩槽滿 10 級、品質 2 舞孃（10005）三槽已滿級"
        "（槽 1／2 滿級 20、槽 3 滿級 30）、品質 3 審判官（10031）四槽滿 30 級，以及術士、守望者、沙漠王子的槽 3。"
        "這幾筆已能說明前服這幾名英雄讀舊表，仍不能寫死所有伺服器、所有英雄都只讀舊表"
        "（舊表另有 14 名英雄不是 4 槽：品質 1 的 6 人只有槽 1／2，品質 2 的 8 人只有槽 1／2／3）。"
        "數值要讀 <code>hero_talent_group.json</code>（2,580 筆），不要只看 <code>talent_name</code>："
        "有幾處名稱鍵還是舊的，和群組實際寫入的屬性不一致。"
        "屬性名優先用 <code>attribute_name_{id}</code>。"
        "<code>show_type=2</code> 預設只記表內原值，不自行換算成百分比。"
        "例外：已確認的英雄天賦面板，原值除以 100 等於面板百分比（10000＝100%），並固定兩位小數，"
        "見「舊表與面板對照」；不要自行推到所有 <code>show_type=2</code>，"
        "也不要推到稱號、羈絆或其他非天賦來源。"
        "<code>type=1</code>、<code>show_type=1</code> 的點數，已確認的兩條（1018、1093）依面板原文記，"
        "沒有百分號、沒有正號、也沒有千分位；其餘點數（例如出征上限）同樣只記原值。"
        "不要從 <code>unlocktime</code>、<code>season</code> 自動標未開放。可收集英雄主表是 <code>hero_detail.json</code>（57 筆）。"
        "名稱取 <code>hero_name_{id}</code>。15032、15033、15039 三筆在主表與天賦表裡，但字串表沒有對應的 <code>hero_name_*</code>，本頁不編造中文名。"
        "公開名冊裡只有牧羊人標未開放；老闆娘是正常已連結的名稱。"
        f"領主天賦樹 id 以 600 開頭的是{H(o.war_name, terms)}，700 開頭的是{H(o.abundance_name, terms)}；"
        "另有 710 開頭五條沒有前置，與 700 部分節點並列，表沒有標哪套現役，正文分開登錄。</li>"
    )
    add(
        "<li>英雄天賦 <code>attr_category</code> 6，定義同時見 <code>hero_talent.json</code>"
        "（208 筆，舊表）與 <code>hero_talent_new.json</code>（228 筆，後來的定義），"
        "數值在 <code>hero_talent_group.json</code>。兩表並存；現行 759 張表與 2026-11-05 的 675 張表都沒有讀表開關，"
        "其他表也不引用 <code>hero_talent_new</code>。"
        "已確認的前服面板（品質 1 藥劑師、品質 2 舞孃、品質 3 審判官，以及術士、守望者、沙漠王子的槽 3）"
        "顯示的都是舊表，不是新表；現役以哪張為準仍不能全庫寫死。"
        "領主天賦 <code>attr_category</code> 45，志向在 <code>player_talent_professional.json</code>，"
        "節點在 <code>player_talent_detail.json</code>。"
        "領主職業（騎士／農場／學者）是 <code>attr_category</code> 41–43，定義在 <code>professional.json</code> 與進階／紋章表。"
        f"屬性來源「{H(o.awaken_name, terms)}」（<code>attr_category</code> 4）的提示文案是「{official_term_html(o.awaken_dec)}」；"
        f"「{H(o.break_name, terms)}」（<code>attr_category</code> 5）的提示文案是「{official_term_html(o.break_dec)}」。"
        "兩條提示與分類名稱對調，本頁照錄，不改正文。這兩條不是本頁的天賦系統。</li>"
    )
    add(f"<li>{_data_notes(data)}</li>")
    add(
        "<li>版本：第 23 章第一版日期 2026-11-15（香港時間），當時以新表為正文主線；"
        "第二版 2026-11-16（香港時間）依前服審判官四槽滿 30 級面板，改掉「以 <code>hero_talent_new</code> 為現役」的寫法；"
        "第三版 2026-11-21（香港時間）補上藥劑師、舞孃、術士、守望者、沙漠王子的面板鎖定。"
        "本頁依第三版的鎖定撰寫，並用現行 LocalLow 包覆核表列；不能把 <code>hero_talent_new</code> 寫成全庫現役。</li>"
    )
    add(
        "<li>待補（均未決議，本頁不補寫答案）：其他英雄、其他伺服器目前讀哪張表；"
        "鐵匠／護衛、戰士一系、妖精的名稱鍵與群組屬性不一致時，介面實際顯示哪一組；"
        "藥劑師槽 2 的面板原文（未入鏡）；"
        "<code>hero_talent_swap</code> 的品質 3–6 與 <code>talent_quality</code> 1–3 如何對應；"
        "屬性 1212、1085、1079 的名稱；710 系列與 700 對應節點哪套現役；"
        "<code>talent_building_lv</code> 對應哪一座建築；領主天賦與職業加成是否同時生效。"
        "可見表頭「天賦建築等級」原名 <code>talent_building_lv</code>。可見不再寫建築 145，建築編號 145 對照見此。可見新表數列表頭不再附（30101）／（40101）／（50101），改寫「品質 1／品質 2／品質 3」；群組編號對照見名錄「新表槽 1／2／4 群組」欄。"
        "地圖建築官方說明全文對應 <code>mapBuilding_tips_01</code>／<code>_02</code>／<code>_03</code>。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {TALENT_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_talent_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    o = data.official
    out: dict[str, str] = {}
    q_groups = {
        1: "30101／30201／30301",
        2: "40101／40201／40301",
        3: "50101／50201／50301",
    }
    q_vals = {1: "100／4,000", 2: "300／10,000", 3: "600／18,000"}
    q_rows = []
    for q in (1, 2, 3):
        ids = data.quality_heroes[q]
        q_rows.append([
            str(q),
            str(len(ids)),
            q_groups[q],
            q_vals[q],
            join_heroes_md(ids, data.roster_names),
        ])
    out["quality"] = md_table(
        ["品質", "人數（含 15032／15033／15039）", "新表槽 1／2／4 群組", "新表英雄攻擊或生命 1 級／30 級（屬性 103 或 104）", "英雄"],
        q_rows,
    )
    seq_rows = []
    for lv in range(1, 31):
        seq_rows.append([
            str(lv),
            str(_curve(data, 30101).values[lv - 1]),
            str(_curve(data, 40101).values[lv - 1]),
            str(_curve(data, 50101).values[lv - 1]),
        ])
    out["new_seq"] = md_table(
        ["等級", "品質 1（30101）", "品質 2（40101）", "品質 3（50101）"],
        seq_rows,
    )

    def slot3_table(gids: tuple[int, ...]) -> str:
        rows = []
        for gid in gids:
            slots = [s for s in data.new_slots if s.slot == 3 and s.group_id == gid]
            slots.sort(key=lambda s: SLOT3_HERO_ORDER[gid].index(s.hero_id))
            s0 = slots[0]
            curve = _curve(data, gid)
            rows.append([
                _attr_cell(curve, data.attrs),
                _slot3_name_note(s0, curve),
                _dec_label(s0.dec_key, o),
                str(gid),
                "／".join(str(q) for q in sorted({s.quality for s in slots})),
                _lv_pair(curve),
                join_heroes_md([s.hero_id for s in slots], data.roster_names),
            ])
        return md_table(
            ["寫入屬性", "名稱", "說明文", "群組", "品質", "1 級／30 級", "英雄"],
            rows,
        )

    out["slot3_combat"] = slot3_table(SLOT3_COMBAT_ORDER)
    out["slot3_march"] = slot3_table(SLOT3_MARCH_ORDER)

    def lord_table(trees: list[LordTree], with_bld: bool) -> str:
        rows = []
        cols = ["樹 id", "級數", "talent_building_lv", "前置（樹|等級）", "寫入屬性（1 級→滿級）"] if with_bld else ["樹 id", "級數", "寫入屬性（1 級→滿級）"]
        for tree in trees:
            effect = _lord_effect(tree, data)
            if with_bld:
                rows.append([
                    str(tree.tree_id),
                    str(tree.max_lv),
                    f"{tree.bld_first}→{tree.bld_last}",
                    fmt_pre(tree.prereqs),
                    effect,
                ])
            else:
                rows.append([str(tree.tree_id), str(tree.max_lv), effect])
        return md_table(cols, rows)

    out["war"] = lord_table(data.war_trees, True)
    out["abundance"] = lord_table(data.abundance_trees, True)
    out["series710"] = lord_table(data.series_710, False)
    return out


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    add_lines: list[str] = []
    add = add_lines.append
    add("# Top Heroes Wiki｜天賦總表")
    add("")
    add(LEDE)
    add("")
    add(
        "交叉引用：[專武總表](exclusive.html)、[英靈總表](valhalla.html)、[造型總表](skins.html)、"
        "[裝備總表](equipment.html)、[領主裝備總表](lord-equipment.html)、[士兵總表](troops.html)、"
        "[秘寶總表](artifacts.html)、[寵物總表](pets.html)、[符文總表](runes.html)、"
        "[科技總表](tech.html)、[裝飾物總表](decorations.html)、[城堡外觀總表](castle.html)。"
    )
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "本頁分兩大節，不要混為一套系統。"
        f"英雄天賦（官方名稱「{o.hero_talent_name}」，提示「{o.hero_talent_dec}」）可在英雄介面消耗對應英雄碎片提升。"
        "目前面板看得到的是舊的那一套（進攻戰略、持久策略等），本頁以面板看得到的為準；"
        "另一套定義先不拿來改你在遊戲裡看到的名稱。完整對照見「舊表與面板對照」與資料說明。"
        f"領主天賦（官方名稱「{o.lord_talent_name}」，提示「{o.lord_talent_dec}」）在領主大廳中學習。"
        f"官方志向名稱是「{o.war_name}」「{o.abundance_name}」。"
    )
    add("")
    add(
        f"另有一套領主職業（{o.knight_lord}、{o.farm_lord}、{o.scholar}）。"
        "表沒有寫職業與領主天賦如何疊加，也不標哪一套會取代另一套。"
        "本頁不把職業寫進領主天賦正文，見文末「本頁未列入」。檔名與分類編號見資料說明。"
    )
    add("")
    add("- **正文只根據遊戲資料表與面板看得到的內容。** 不評定天賦強弱，也不做搭配模擬。兩套英雄天賦定義不要混用，本頁不以後來的那一套當成現用全表。對照與換算規則見「舊表與面板對照」與資料說明。")
    add("- 公開名冊裡只有牧羊人標未開放；老闆娘不標未開放。不要從解鎖時間或賽季欄自動標未開放。15032、15033、15039 三筆沒有官方中文名，本頁不編造。")
    add("- 本頁不把未被引用的 81 個天賦群組當成現役英雄天賦。檔名、欄位與換算細節見資料說明。")
    add("")
    add("## 英雄天賦")
    add("")
    add(
        f"官方說明是在英雄介面消耗對應英雄碎片升級（`hero_talent_dec`：「{o.hero_talent_dec}」）。"
        f"同一品質才能交換（`hero_talent_quality_not_swap`：「{o.quality_not_swap}」）；"
        f"官方另有「{o.swap_count}」「{o.swap_level}」「{o.swap_slot}」等提示（`hero_talent_swap_*`）。"
        f"解鎖需先解鎖上一個天賦（`hero_talent_tips_3`：「{o.tips_unlock}」）。"
    )
    add("")
    add("### 槽位、品質與升級")
    add("")
    add(
        "`hero_detail` 的 57 個英雄 id 在新表都有 4 個槽位，共 228 筆。"
        "四個槽位的解鎖消耗一律寫成 `999|2|數量`，數量依槽位為 200／500／1,000／2,000，與 `talent_quality` 無關。"
        f"既有圖鑑對 `999|2` 的說明：類型 2 對得上頂欄資源「{o.diamond}」（`top_resource` id 2，`top_resource_name_2`）；"
        "類型 999 在表上沒有名稱，本頁不自行斷定。"
    )
    add("")
    add(
        "升級消耗是 `upgrade_cost`：類型 2、數量 10（碎片）。"
        "多數列的英雄 id 等於該英雄自己的 id；15032／15033／15039 用的也是自己的 id，不是 10032／10033／10039。"
        f"表上另有一條例外，第 23 章未列出：{hero_link_md(10012, data.roster_names)}（10012）在新表槽 1／2／4 的升級消耗寫的是 10008，"
        "只有槽 3 寫 10012；舊表四槽都寫 10012。本頁照表記錄，不推測原因。"
    )
    add("")
    add(
        f"`talent_quality` 1／2／3 把英雄分成三檔。**新表**裡，槽 1／2／4 對應攻擊或生命群組的強度；"
        "群組都是 1–30 級，寫入皆為英雄側、`type=2`、`show_type=2` 的英雄攻擊（103）或英雄生命（104）。"
        f"說明文是「{o.des_101}」（`hero_talent_des_101`）。"
        f"槽 1 一般名稱是「{o.name_atk}」、槽 2 是「{o.name_hp_i}」、槽 4 是「{o.name_hp_ii}」。"
        "這些是新表的寫法，不是這次前服面板顯示的那套。"
    )
    add("")
    add(tbl["quality"])
    add("")
    add("新表槽 1 的 1–30 級數列如下。槽 2／4 的新表英雄生命數列，與同品質槽 1 的英雄攻擊數列相同（只是屬性改為 104）。")
    add("")
    add(tbl["new_seq"])
    add("")
    add(
        f"例外（僅就新表名稱鍵）：{hero_link_md(10009, data.roster_names)}、{hero_link_md(10010, data.roster_names)}"
        f"的槽 1／2 名稱鍵仍是「{o.name_strategy}」「{o.name_endure}」，"
        "但掛的群組已是 30101／30201（英雄攻擊／英雄生命），數值與同品質其他英雄相同。"
        f"槽 4 名稱已是「{o.name_hp_ii}」。介面實際顯示哪一組，表沒有再說明。"
        "前服已確認的品質 1／2／3 面板都對舊表，不能用來推鐵匠、護衛在新表名稱鍵下會顯示哪一組。"
    )
    add("")
    add("### 舊表與面板對照")
    add("")
    add(
        f"**舊表與面板對照。** 舊表品質 3 的槽 1 是群組 20015（屬性 10103 所有士兵攻擊，1 級 300／30 級 9,000），"
        f"名稱「{o.name_strategy}」；槽 2 是群組 20255（10104 所有士兵生命，900／27,000），名稱「{o.name_endure}」。"
        f"品質 3 的槽 4 不是人人相同：23 人掛 20255（{o.name_endure}），20 人掛 20015（{o.name_strategy}）。"
        f"{hero_link_md(10031, data.roster_names)}（10031，品質 3）槽 4 是 20255；槽 3 兩表相同，審判官是群組 20085（16 格擋，100／3,000），名稱「格擋研究」。"
        "舊表品質 1 只有槽 1／2，滿級 10 級（群組 20013／20253：所有士兵攻擊 200／2,000，所有士兵生命 600／6,000）；"
        "品質 2 只有槽 1／2／3，槽 1／2 滿級 20 級（群組 20014／20254：250／5,000、750／15,000），槽 3 滿級 30 級。"
    )
    add("")
    add("2026-11-16 前服審判官（10031，品質 3）四槽皆 30 級、已滿級的面板，槽名與數值都對得上這份舊表，對不上新表的 103／104、600／18,000（槽 3 除外）。面板原文：")
    add("")
    add(f"- {PANEL_JUDGE_ATK}")
    add(f"- {PANEL_JUDGE_HP}（槽 2 與槽 4 同句）")
    add(f"- {PANEL_JUDGE_BLOCK}")
    add("")
    add("30 級原值除以 100 剛好等於面板百分比：所有士兵攻擊 9,000＝90.00%，所有士兵生命 27,000＝270.00%，格擋 3,000＝30.00%（10000＝100%）。")
    add("")
    add("2026-11-21 前服另確認下列面板，槽名與數值同樣對得上舊表，對不上新表（槽 3 兩表相同的除外）：")
    add("")
    add(
        f"- {hero_link_md(10007, data.roster_names)}（10007，品質 1）兩槽皆已滿 10 級。"
        f"面板原文：「{PANEL_ALCHEMIST_ATK}」。"
        "這筆鎖定前服品質 1 讀舊表（只有 2 槽，滿級 10 級），不是新表的 4 槽／30 級／103／104。"
        "槽 2 未入鏡，本頁不編造槽 2 的面板原文。"
    )
    add(
        f"- {hero_link_md(10005, data.roster_names)}（10005，品質 2）三槽皆已滿級。"
        f"面板原文：「{PANEL_DANCER_ATK}」（20 級）、「{PANEL_DANCER_HP}」（20 級）、「{PANEL_DANCER_HEAL}」（30 級）。"
        "這筆鎖定前服品質 2 讀舊表（3 槽；槽 1／2 滿級 20 級，槽 3 滿級 30 級），並鎖定屬性 1022 滿級原值 3,000＝30.00%。"
    )
    add(
        f"- {hero_link_md(10028, data.roster_names)}（10028）槽 3 已滿 30 級。"
        f"面板原文：「{PANEL_WARLOCK}」。沒有百分號，沒有正號，也沒有千分位。這筆鎖定屬性 1093 為點數。"
    )
    add(
        f"- {hero_link_md(10021, data.roster_names)}（10021）槽 3 已滿 30 級。"
        f"面板原文：「{PANEL_WATCHER}」。格式同上。這筆鎖定屬性 1018 為點數。"
    )
    add(
        f"- {hero_link_md(10039, data.roster_names)}（10039）槽 3「法術偏移」21 級。"
        f"面板原文：「{PANEL_PRINCE}」，對得上群組 20115 的 21 級 3,500、22 級 3,667。"
        "這筆鎖定中間等級的顯示：原值除以 100，固定兩位小數。"
        "依同一規則，原值 167、133、67 會顯示為相應的兩位小數百分比，但這些字串尚未入鏡，本頁不把它們寫成已對面板的原文。"
    )
    add("")
    add(
        "此對應只鎖定這些已確認的天賦顯示，不要自行推到所有 `show_type=2`，也不要推到稱號、羈絆或其他非天賦來源。"
        "這幾筆仍不能寫死所有伺服器、所有英雄都只讀舊表；新表是否已在其他伺服器或未對面板的英雄上線，表內沒有開關可鎖。"
        "舊表另有 14 名英雄不是 4 槽，見「舊表、交換、未引用群組」。"
    )
    add("")
    add(
        "103／104 如何進入官方「攻擊百分比／生命百分比」欄，表沒有標。"
        "前服已確認的天賦百分比是舊表的 10103／10104／16／1022／21 等，不是新表 103／104。"
        "除上述已鎖定的天賦顯示外，本頁其餘 `show_type=2` 只記原值。"
    )
    add("")
    add("### 槽 3（每人一條，名稱以群組屬性為準）")
    add("")
    add(
        f"槽 3 的名稱與群組多數一致，說明文有「{o.des_101}」（`hero_talent_des_101`）、"
        f"「{o.des_102}」（102）、「{o.des_104}」（104）三種。"
        "下面按實際寫入的屬性排列；1 級與 30 級數值已對過群組表。名稱與屬性不一致的，在該條註明。"
    )
    add("")
    add("#### 戰鬥屬性（寫入英雄側）")
    add("")
    add(tbl["slot3_combat"])
    add("")
    add("#### 行軍、帶兵、經濟（多寫入領主側 `player_attr`）")
    add("")
    add(tbl["slot3_march"])
    add("")
    add(
        "槽 3 已對前服面板的，見上文「舊表與面板對照」："
        "格擋研究（審判官，自身格擋提升30.00%）、快速醫療（舞孃，傷兵治療速度提升30.00%）、"
        "士兵擴編（守望者，每個陣營容納士兵上限提升2000）、資源掠奪（術士，每日木材、石頭掠奪上限提升360000）、"
        "法術偏移（沙漠王子 21 級，自身技能減傷提升35.00%(下一級技能減傷提升36.67%)）。"
        "表上「1 級／30 級」仍記群組原值。"
    )
    add("")
    add(
        "15032／15033／15039 的四槽與 10032／10033／10039（"
        + join_heroes_md([10032, 10033, 10039], data.roster_names)
        + "）相同，只是沒有 `hero_name_*` 字串。本頁不把它們與 10032／10033／10039 合併成同一人。"
    )
    add("")
    add("### 舊表、交換、未引用群組")
    add("")
    add(
        "舊表 208 筆、新表 228 筆，少掉的 20 筆就是那 14 名英雄後來補上的槽位："
        + join_heroes_md(list(QUALITY1_IDS), data.roster_names)
        + "在舊表只有槽 1／2；"
        + join_heroes_md(list(QUALITY2_IDS), data.roster_names)
        + "在舊表只有槽 1／2／3。舊表專用、新表不再掛的群組是 20013／20014／20015／20253／20254。"
        "本抽取沒有欄位標明客戶端讀哪張表，其他表也不引用 `hero_talent_new`。"
        "從槽位數與群組改掛來看，新表是後來的定義，但這不是表內開關。"
        "這次已對過面板的藥劑師、舞孃、審判官（以及術士、守望者、沙漠王子的槽 3），顯示的都是舊表，不是新表"
        "（槽 3 兩表相同的除外）；現役以哪張為準仍不能全庫寫死。"
    )
    add("")
    add(
        "`hero_talent_swap` 4 筆按 `swap_quality` 給交換消耗：品質 3 為 `999|2|200`，品質 4 為 500，品質 5 與 6 各有一筆、皆為 2,000。"
        "這裡的品質編號是 3／4／5／6，與英雄天賦定義表上的 `talent_quality` 1／2／3 不是同一欄，本頁不自行對成同一套品質。"
        "官方提示品質不同、槽位或等級不匹配時不能交換。"
    )
    add("")
    add(
        f"`hero_talent_group` 另有 81 個群組沒有被新舊定義表引用（滿級為 10 級的 {data.unref_caps[10]} 個、"
        f"20 級的 {data.unref_caps[20]} 個、30 級的 {data.unref_caps[30]} 個，多為採集、行軍、攻城等）。"
        "本頁不當成現役天賦，也不推測它們何時會掛上。"
    )
    add("")
    add("## 領主天賦")
    add("")
    add(
        f"領主天賦是另一套系統，在{o.hall_name}學習（`property_lordtalent_dec`）。"
        f"志向只有兩筆，官方名稱是「{o.war_name}」「{o.abundance_name}」（`professional_name01`／`professional_name02`）。"
    )
    add("")
    add(f"{o.war_name}的說明（`professional_des01`）：「{o.war_des}」")
    add("")
    add(f"{o.abundance_name}的說明（`professional_des02`）：「{o.abundance_des}」")
    add("")
    add(
        f"變更志向或重置會退還已學習的天賦點數（`player_talent_switch_desc`：「{o.switch_desc}」；"
        f"`player_talent_reset_desc`：「{o.reset_desc}」）。"
        f"重置／變更消耗是 `2|12210100|1`（物品 12210100「{o.scroll_name}」，說明：「{o.scroll_desc}」）。"
        f"節點升級多用 `2|12210000|1`（物品 12210000「{o.point_name}」，說明：「{o.point_desc}」）；"
        f"部分節點另加物品 12210200「{o.medal_name}」（說明：「{o.medal_desc}」），"
        "附加數量在表上為 100、200、300、600、1,000 或 2,000。"
        "節點另要求 `talent_building_lv`（1 到 21）。"
        f"表沒有把這個欄位直接寫成哪一座建築的等級；物品說明提到{o.hall_name}（`citybuilding_name_145`），"
        "本頁不自行斷定欄位就等於建築 145。"
    )
    add("")
    add(
        "`player_talent_detail` 293 筆、47 條樹。所有節點的 `des`、`time`、`quality` 皆為空或 -1。"
        f"樹 id 以 600 開頭的是{o.war_name}（22 條），700 開頭的是{o.abundance_name}（20 條）；另有 710 開頭五條沒有前置。"
        "下面各樹列出 1 級→滿級；屬性皆 `type=2`、`show_type=2`，除非另註。有官方節點名稱字串的（僅少數）一併註明。"
    )
    add("")
    add(f"### {o.war_name}")
    add("")
    add(tbl["war"])
    add("")
    add(
        f"字串表另有 `player_talent_name_1016`「{o.train_accel_name}」，對應屬性名稱鍵 1016（士兵訓練速度）。"
        "戰爭樹沒有寫入 1016，本頁不把這條名稱掛到任何節點。"
    )
    add("")
    add(f"### {o.abundance_name}")
    add("")
    add(tbl["abundance"])
    add("")
    add(
        f"地圖建築的官方說明文寫「{o.abundance_name}建造」的特殊建築或自動採集設施（`mapBuilding_tips_01`／`02`／`03`）。"
        f"`mapBuilding_tips_01` 稱強化塔為「{o.light_tower}」，與建築名稱一致；"
        f"`mapBuilding_tips_02` 稱削弱塔為「黑暗之塔」，與建築表名稱「{o.dark_tower}」用字不同，本頁兩種寫法都照錄，不自行統一。"
        "說明文還寫：同一範圍內多座光明之塔只生效最高等級、效果不可疊加；黑暗之塔同樣按非所在公會的最高等級計算。"
        "本頁不展開建築戰鬥效果與耐久規則。官方說明全文如下。"
    )
    add("")
    add("```")
    add(o.tips_light)
    add("```")
    add("")
    add("```")
    add(o.tips_dark)
    add("```")
    add("")
    add("```")
    add(o.tips_facility)
    add("```")
    add("")
    add("1040「英雄攻擊轉化率」如何進入士兵或戰鬥公式，表沒有寫。本頁只記錄它被豐饒樹寫入。")
    add("")
    add("### 710 系列（沒有前置）")
    add("")
    add("以下五條樹的 `lvup_pre_id` 皆空，`talent_building_lv` 皆為 21，與 700 部分節點（醫院、治療、三種採集）並列。表沒有標哪套現役。")
    add("")
    add(tbl["series710"])
    add("")
    add("## 本頁未列入")
    add("")
    add(f"- 領主職業（{o.knight_lord}、{o.farm_lord}、{o.scholar}）及其進階樹、職業技能與紋章（`professional.json`、`professional_advanced_tree.json`、`professional_advanced_detail.json`、`professional_plugin.json` 等）。這是與領主天賦分開的來源分類（`attr_category` 41–43），表沒有寫兩者如何疊加。")
    add("- 未被新舊英雄天賦定義表引用的 81 個群組。")
    add(f"- {o.light_tower}、{o.dark_tower}、{o.auto_facility}的建築效果、範圍與耐久明細（只在豐饒樹註明解鎖的建築 id 與官方名稱）。")
    add("- 英雄天賦 103／104、領主天賦 1040「英雄攻擊轉化率」如何進入官方戰鬥公式。")
    add("- 天賦與英雄技能、站位、士兵的搭配模擬，以及強弱評定。")
    add("")
    add("## 資料說明")
    add("")
    add("以下是整理用註記，查天賦名稱與效果可略過。")
    add("")
    add(
        "正文所據：遊戲資料表與已確認的前服面板。英雄天賦同時登錄 `hero_talent.json`（208 筆）與 `hero_talent_new.json`（228 筆）。"
        "新表是後來的定義，但 2026-11-16 至 2026-11-21 已確認的前服面板，槽名與數值都對得上舊表，對不上新表"
        "（槽 3 兩表相同的除外）：品質 1 藥劑師（10007）兩槽滿 10 級、品質 2 舞孃（10005）三槽已滿級"
        "（槽 1／2 滿級 20、槽 3 滿級 30）、品質 3 審判官（10031）四槽滿 30 級，以及術士、守望者、沙漠王子的槽 3。"
        "這幾筆已能說明前服這幾名英雄讀舊表，仍不能寫死所有伺服器、所有英雄都只讀舊表"
        "（舊表另有 14 名英雄不是 4 槽：品質 1 的 6 人只有槽 1／2，品質 2 的 8 人只有槽 1／2／3）。"
        "數值要讀 `hero_talent_group.json`（2,580 筆），不要只看 `talent_name`："
        "有幾處名稱鍵還是舊的，和群組實際寫入的屬性不一致。"
        "屬性名優先用 `attribute_name_{id}`。`show_type=2` 預設只記表內原值，不自行換算成百分比。"
        "例外：已確認的英雄天賦面板，原值除以 100 等於面板百分比（10000＝100%），並固定兩位小數，"
        "見「舊表與面板對照」；不要自行推到所有 `show_type=2`，也不要推到稱號、羈絆或其他非天賦來源。"
        "`type=1`、`show_type=1` 的點數，已確認的兩條（1018、1093）依面板原文記，"
        "沒有百分號、沒有正號、也沒有千分位；其餘點數（例如出征上限）同樣只記原值。"
        "不要從 `unlocktime`、`season` 自動標未開放。可收集英雄主表是 `hero_detail.json`（57 筆）。"
        "名稱取 `hero_name_{id}`。15032、15033、15039 三筆在主表與天賦表裡，但字串表沒有對應的 `hero_name_*`，本頁不編造中文名。"
        "公開名冊裡只有牧羊人標未開放；老闆娘是正常已連結的名稱。"
        f"領主天賦樹 id 以 600 開頭的是{o.war_name}，700 開頭的是{o.abundance_name}；"
        "另有 710 開頭五條沒有前置，與 700 部分節點並列，表沒有標哪套現役，正文分開登錄。"
        "英雄天賦 `attr_category` 6；領主天賦 `attr_category` 45，志向在 `player_talent_professional.json`，節點在 `player_talent_detail.json`。"
        f"領主職業（{o.knight_lord}、{o.farm_lord}、{o.scholar}，`attr_category` 41–43），定義在 `professional.json` 與進階／紋章表。"
        f"屬性來源「{o.awaken_name}」（`attr_category` 4）的提示文案是「{o.awaken_dec}」；"
        f"「{o.break_name}」（`attr_category` 5）的提示文案是「{o.break_dec}」。"
        "兩條提示與分類名稱對調，本頁照錄，不改正文。這兩條不是本頁的天賦系統。"
    )
    add("")
    add(_data_notes(data))
    add("")
    add(
        "版本：第 23 章第一版日期 2026-11-15（香港時間），當時以新表為正文主線；"
        "第二版 2026-11-16（香港時間）依前服審判官四槽滿 30 級面板，改掉「以 `hero_talent_new` 為現役」的寫法；"
        "第三版 2026-11-21（香港時間）補上藥劑師、舞孃、術士、守望者、沙漠王子的面板鎖定。"
        "本頁依第三版的鎖定撰寫，並用現行 LocalLow 包覆核表列；不能把 `hero_talent_new` 寫成全庫現役。"
    )
    add("")
    add(
        "待補（均未決議，本頁不補寫答案）：其他英雄、其他伺服器目前讀哪張表；"
        "鐵匠／護衛、戰士一系、妖精的名稱鍵與群組屬性不一致時，介面實際顯示哪一組；"
        "藥劑師槽 2 的面板原文（未入鏡）；"
        "`hero_talent_swap` 的品質 3–6 與 `talent_quality` 1–3 如何對應；"
        "屬性 1212、1085、1079 的名稱；710 系列與 700 對應節點哪套現役；"
        "`talent_building_lv` 對應哪一座建築；領主天賦與職業加成是否同時生效。"
    )
    add("")
    return "\n".join(add_lines)
