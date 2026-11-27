"""Compile the unpublished 裝飾物 catalog tables. Public-style HTML; preview script adds the banner."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT
from .strings import clean, fill_text, has_key, load_strings, t
from .tables import load_table


# 裝飾物總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。本頁頁腳／截止日寫 2026-11-22，
# 因為現行包與第 16 章所據的 2026-11-05 解壓檔在城鎮裝飾屬性表上有差異。
DECORATION_DATA_CUTOFF = "2026-11-22"
DECORATION_DATA_PACK = "app-1.129.12_table-1.0.43173"
DECORATION_DATA_PACKED = "2026-11-22 23:33"
CHAPTER_FIRST_EDITION = "2026-11-15"

TABLE_SHA256 = {
    "citybuilding_DIY_property.json": "53451db8ca8100164b6ed356498b5f257cdde5d8b480db5e50c917b03d733698",
    "citybuilding_DIY_suit.json": "fb2ffc4162469357279af7c54bc18a2091860d50f0247b7ac6e0a1670d56e3b0",
    "citybuilding_DIY_suit_property.json": "212bc10c7d07723b8290a7f38fec79dcaaea9f5d25e36aee23553f9c626532dd",
    "citybuilding_DIY_skill.json": "53a0acd30c2fea443a3c0171697b442ed497fb8bc5e7aa1c35cd89cf955d7a05",
    "citybuilding_diy_filter.json": "fdd02e130c3a0660dcc046539249343c6f2a9ae73253c51c218f3cd304812f40",
    "alliance_decorations.json": "a58595133d6dc5e35af95b66db0184289a20f1cdb7687464faa59eebde24c301",
    "alliance_decorations_property.json": "867885fa1a2d18ca842128ec27a3e73e81eac3d3ce5a022c32154320c1a68e65",
    "collection_detail.json": "4f560603fbc093edf8da0766c3f6291369ab444934478efc037aff85bc386327",
    "collection_theme_milestone.json": "7df1f45bd12d10c1dcff9686af108d823db20c196668a6d99fab1e1a457a4967",
    "collection_refresh.json": "f0045b9275f5103f41356b83e4240fb260851049cb3b38564de96586a659c3c8",
    "citybuilding_guidebook.json": "8d7090c48551f60ad8249a7ca85a7f53182d6f2c9b00b5bb73977598438580d2",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "citybuilding_DIY.json": "876dc918c2dee872898eec927b97c401bd3eb3aa5718db8fb2059c148201d657",
    "citybuilding_DIY_switch.json": "49ac5d9981b58c18ff86df45f095c373363769e467f01d8f5a09e08aa76a4397",
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

COMPARE_TABLES = [
    "citybuilding_DIY_property.json",
    "citybuilding_DIY_suit.json",
    "citybuilding_DIY_suit_property.json",
    "citybuilding_DIY_skill.json",
    "citybuilding_diy_filter.json",
    "citybuilding_DIY.json",
    "citybuilding_DIY_switch.json",
    "alliance_decorations.json",
    "alliance_decorations_property.json",
    "collection_detail.json",
    "collection_theme_milestone.json",
    "collection_refresh.json",
    "citybuilding_guidebook.json",
    "attribute.json",
    "function.json",
]

# 第 16 章各套裝分節順序（不是檔案列序，也不是 sort_id）。
SUIT_ORDER = (
    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 3301, 35, 33, 502, 37, 3302, 503,
    38, 41, 44, 42, 43, 45, 46, 47, 9999, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,
)

# 第 16 章公會裝飾物表序。
GUILD_ORDER = (
    10001, 10002, 10003, 10004, 10005, 10006, 10007, 10008, 10016, 10009, 10010,
    10015, 10013, 10011, 10012, 10014, 10017, 10018, 10019, 10020, 10021, 10022,
)

# 第 16 章已列、本抽取亦有的只有名稱沒有屬性列編號。
NAME_ONLY_CHAPTER = (101401, 101402, 101403, 101404, 101501)
# 後續包新出現的名稱鍵，同樣沒有屬性列。
NAME_ONLY_LATER = (159501, 159502, 159503, 159504, 159505)
# 後續包定義表才有、不在屬性表的編號（名稱取自 collection_name_*）。
DEF_ONLY_LATER = (1009998, 1009999)

TOWER_IDS = (308501, 308502, 308503)
ELITE_IDS = (118501, 118502, 118503)
TOTEM_IDS = (108501, 108502)
NAMED_NOT_IN_MEMBERS = (501604, 501605, 501606, 501607)
NAMELESS_NOT_IN_SUIT = (10023, 10024)
WELCOME_ID = 210032
CRYSTAL_ID = 20004
TREE_ID = 502507
ANNIV_ID = 502404
RABBIT_CUP_ID = 150602
SNOWMAN_ID = 10019
ID_151601 = 151601

# 6–7 級要 40 級城堡，8 級 45，9 級 50，10–13 級 55，14 級 75，15 級 80。
STANDARD_GATE = (
    (1, None), (2, None), (3, None), (4, None), (5, None),
    (6, "117|40"), (7, "117|40"), (8, "117|45"), (9, "117|50"),
    (10, "117|55"), (11, "117|55"), (12, "117|55"), (13, "117|55"),
    (14, "117|75"), (15, "117|80"),
)
# 第 16 章沒有單列、但 2026-11-05 與現行包都已是這個寫法的 15 級件。
GATE_FROM_14 = (107404, 501501, 501502)
GATE_FROM_10 = (111501, 111502, 111503)

THEME_IDS = (1, 2, 3, 4)
THEME_NAME_KEYS = {1: "collection_dig_desc_1", 2: "collection_dig_desc_2", 3: "collection_dig_desc_3", 4: "collection_dig_desc_4"}

EMPTY = "—"
DASH = "—"

LEDE = (
    "本頁分開列出兩套系統，不要混為一套：擺在自己主城的城鎮裝飾，"
    "以及擺在公會領地的公會裝飾物。正文只根據遊戲資料表，不評定裝飾物強弱，也不編造取得途徑或名稱。"
)

PUBLISHED_LINKS = (
    ("exclusive.html", "專武總表"),
    ("valhalla.html", "英靈總表"),
    ("skins.html", "造型總表"),
    ("equipment.html", "裝備總表"),
    ("lord-equipment.html", "領主裝備總表"),
    ("troops.html", "士兵總表"),
    ("artifacts.html", "秘寶總表"),
    ("pets.html", "寵物總表"),
    ("runes.html", "符文總表"),
    ("talents.html", "天賦總表"),
    ("tech.html", "科技總表"),
    ("castle.html", "城堡外觀總表"),
)

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


def empty_or(value, empty: str = EMPTY) -> str:
    if value in (None, "", [], {}, -1, "-1"):
        return empty
    return str(value)


def is_empty(value) -> bool:
    return value in (None, "", [], {}, -1, "-1")


def parse_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, dict):
        out: list[tuple[int, int]] = []
        for key, val in raw.items():
            if str(key).strip() == "":
                continue
            out.append((_int(key), _int(val)))
        return out
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2 and not isinstance(item[0], (list, tuple)):
                try:
                    out.append((_int(item[0]), _int(item[1])))
                    continue
                except (TypeError, ValueError):
                    pass
            out.extend(parse_pairs(item))
        return out
    text = str(raw)
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk or "|" not in chunk:
            continue
        left, right = chunk.split("|", 1)
        if left.strip() == "":
            continue
        out.append((_int(left), _int(right)))
    return out


def fmt_int(value) -> str:
    try:
        return str(_int(value))
    except (TypeError, ValueError):
        return str(value)


def format_timerange(raw, empty: str = EMPTY) -> str:
    """Turn A|B datetimes into「A 至 B」. Other shapes stay as-is."""
    if is_empty(raw):
        return empty
    text = str(raw).strip()
    m = re.fullmatch(
        r"(\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2}:\d{2})\|(\d{4}-\d{1,2}-\d{1,2} \d{2}:\d{2}:\d{2})",
        text,
    )
    if m:
        return f"{m.group(1)} 至 {m.group(2)}"
    return text


def fmt_field(value, empty: str = EMPTY) -> str:
    if is_empty(value):
        return empty
    if isinstance(value, list):
        if not value:
            return empty
        return "、".join(fmt_field(v, empty=str(v)) for v in value)
    return str(value)


def fmt_activation(raw) -> str:
    if is_empty(raw):
        return EMPTY
    if isinstance(raw, (list, tuple)):
        return "[" + ", ".join(str(x) for x in raw) + "]"
    return str(raw)


def gate_token(raw) -> str | None:
    if is_empty(raw):
        return None
    return str(raw)


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
class NameOnly:
    group_id: int
    name: str
    name_key: str
    desc: str
    later: bool
    source: str  # diy_name / collection_name / definition


@dataclass
class Decoration:
    group_id: int
    name: str
    name_key: str | None
    name_src: str  # diy / collection / none
    desc: str
    max_level: int
    total_nums: tuple[int, ...]
    fight: int
    score: int
    self_attrs: list[tuple[int, int]]
    alliance_attrs: list[tuple[int, int]]
    attr_types_by_level: list[tuple[int, ...]]
    building_pre: tuple[tuple[int, str | None], ...]
    has_gate: bool
    time_type: int | None
    time_para1: str
    reward: str
    display: str
    suit_ids: list[int]
    collection_quality: int | None
    collection_theme: int | None
    is_treasure: bool
    no_self_attrs: bool


@dataclass
class SuitLevel:
    level: int
    activation: list
    self_attrs: list[tuple[int, int]]
    alliance_attrs: list[tuple[int, int]]
    power: int
    active_season: int | None
    property_num_add: str


@dataclass
class SuitInfo:
    suit_id: int
    name: str
    name_key: str
    typ: int | None
    members: list[int]
    member_count: int
    def_self: list[tuple[int, int]]
    def_alliance: list[tuple[int, int]]
    def_fight: int | None
    season_diy_ids: list[int]
    unlock_days: str
    unlock_season: str
    unlocktime: str
    alliance_max_num: str
    is_show: str
    levels: list[SuitLevel]
    def_differs_from_lv1: bool
    def_diff_note: str


@dataclass
class SkillRow:
    group_id: int
    season: int
    typ: int
    level: int
    desc_key: str
    params: list[str]
    params_text: str
    race: int
    text: str


@dataclass
class GuildDeco:
    deco_id: int
    name: str
    name_key: str | None
    name_from_obtain: bool
    obtain: str
    quality: int
    season: int | None
    unlocktime: str
    max_attrs: list[tuple[int, int]]
    suit_id: int


@dataclass
class Official:
    tip_upgrade: str
    tip_no_universal: str
    tip_alliance: str
    tip_alliance_key: str
    tip_member: str
    tip_territory: str
    tip_guild_cap: str
    shop_name: str
    shop_mall: str
    attr_src: str
    attr_suit_src: str
    castle_name: str
    dig_title: str
    dig_rule_1: str
    dig_rule_2: str
    junk_item_desc: str
    theme_names: dict[int, str]
    filter_names: list[str]
    town_univ: list[tuple[int, str, str]]
    guild_univ: list[tuple[int, str, str]]
    alliance_name_3: str
    alliance_name_4: str
    hero_atk: str
    hero_hp: str


@dataclass
class TablesData:
    official: Official
    attrs: dict[int, AttrInfo]
    decorations: dict[int, Decoration]
    deco_order: list[int]
    suits: dict[int, SuitInfo]
    skills: list[SkillRow]
    skills_by_tower: dict[int, list[SkillRow]]
    guild: list[GuildDeco]
    junk: list[NameOnly]
    name_only: list[NameOnly]
    def_only: list[NameOnly]
    leftover_suit_names: list[tuple[str, str, bool]]
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
    name_col = row.get("name")
    if name_missing and name_col:
        name = official_text(name_col, name)
    typ = row.get("type")
    show = row.get("show_type")
    typ_i = None
    show_i = None
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
        name_col=name_col,
    )


def attr_label(aid: int, attrs: dict[int, AttrInfo]) -> str:
    info = attrs.get(aid)
    if info and info.name:
        return info.name
    if aid == 999:
        return "（無名稱）"
    return "（無名稱）"


def fmt_attr_pairs(
    pairs: list[tuple[int, int]],
    attrs: dict[int, AttrInfo],
    prefix: str = "",
    *,
    include_id: bool = True,
) -> str:
    if not pairs:
        return EMPTY
    bits = []
    for aid, val in pairs:
        label = attr_label(aid, attrs)
        if include_id:
            bits.append(f"{label}（{aid}） {fmt_int(val)}")
        else:
            bits.append(f"{label} {fmt_int(val)}")
    body = "、".join(bits)
    return f"{prefix}{body}" if prefix else body


def deco_display_name(deco: Decoration) -> str:
    if deco.name_src == "none" or not deco.name:
        return "（無名稱）"
    return deco.name


def _member_ids(raw) -> list[int]:
    if is_empty(raw):
        return []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, str) and "|" in item:
                out.extend(_int(x) for x in item.split("|") if x.strip())
            else:
                try:
                    out.append(_int(item))
                except (TypeError, ValueError):
                    out.extend(_member_ids(item))
        return out
    text = str(raw)
    out = []
    for chunk in re.split(r"[|,]", text):
        chunk = chunk.strip()
        if chunk:
            out.append(_int(chunk))
    return out


def _season_diy_ids(raw) -> list[int]:
    # season_DIY_id may be like "1" plus "501604|501605|..." or a list.
    if is_empty(raw):
        return []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            out.extend(_season_diy_ids(item))
        return out
    text = str(raw)
    out = []
    for chunk in re.split(r"[|,]", text):
        chunk = chunk.strip()
        if chunk:
            try:
                out.append(_int(chunk))
            except (TypeError, ValueError):
                pass
    return out


def load_tables_data() -> TablesData:
    global USED_KEYS, MISSING_KEYS
    USED_KEYS = set()
    MISSING_KEYS = set()

    property_rows = load_table("citybuilding_DIY_property")
    suit_rows = load_table("citybuilding_DIY_suit")
    suit_prop_rows = load_table("citybuilding_DIY_suit_property")
    skill_rows = load_table("citybuilding_DIY_skill")
    filter_rows = load_table("citybuilding_diy_filter")
    alliance_rows = load_table("alliance_decorations")
    alliance_prop_rows = load_table("alliance_decorations_property")
    collection_rows = load_table("collection_detail")
    milestone_rows = load_table("collection_theme_milestone")
    refresh_rows = load_table("collection_refresh")
    guidebook_rows = load_table("citybuilding_guidebook")
    attribute_rows = load_table("attribute")
    function_rows = load_table("function")
    attr_by = { _int(a["id"]): a for a in attribute_rows }

    diy_def_rows = []
    switch_rows = []
    diy_def_path = DATA_DIR / "citybuilding_DIY.json"
    switch_path = DATA_DIR / "citybuilding_DIY_switch.json"
    if diy_def_path.exists():
        diy_def_rows = json.loads(diy_def_path.read_text(encoding="utf-8-sig"))
    if switch_path.exists():
        switch_rows = json.loads(switch_path.read_text(encoding="utf-8-sig"))

    groups: dict[int, list[dict]] = defaultdict(list)
    for row in property_rows:
        groups[_int(row["group_id"])].append(row)
    for gid in groups:
        groups[gid].sort(key=lambda r: _int(r["level"]))

    col_by_id = { _int(r["id"]): r for r in collection_rows }
    treasure_ids = { _int(r["id"]) for r in collection_rows if _int(r.get("type") or 0) == 1 }
    junk_rows = [r for r in collection_rows if _int(r.get("type") or 0) == 2]

    suit_members: dict[int, list[int]] = {}
    deco_to_suits: dict[int, list[int]] = defaultdict(list)
    for srow in suit_rows:
        sid = _int(srow["id"])
        members = _member_ids(srow.get("citybuilding_DIY_id"))
        suit_members[sid] = members
        for mid in members:
            deco_to_suits[mid].append(sid)

    decorations: dict[int, Decoration] = {}
    used_attr_ids: set[int] = set()
    for gid, rows in groups.items():
        max_row = rows[-1]
        diy_key = f"citybuilding_DIY_name_{gid}"
        col_key = f"collection_name_{gid}"
        if has_key(diy_key):
            name_src = "diy"
            name_key = diy_key
            name = official_text(diy_key)
        elif has_key(col_key):
            name_src = "collection"
            name_key = col_key
            name = official_text(col_key)
        else:
            name_src = "none"
            name_key = None
            name = ""
        des_key = f"citybuilding_DIY_des_{gid}"
        desc = official_text(des_key) if has_key(des_key) else ""
        if not desc:
            crow = col_by_id.get(gid)
            if crow and crow.get("desc") and has_key(str(crow.get("desc"))):
                desc = official_text(crow.get("desc"))
        self_attrs = parse_pairs(max_row.get("attrs") or max_row.get("property_num"))
        alliance_attrs = parse_pairs(max_row.get("alliance_attrs") or max_row.get("property_alliance"))
        used_attr_ids.update(a for a, _ in self_attrs + alliance_attrs)
        types_by_lv = []
        for r in rows:
            pairs = parse_pairs(r.get("attrs") or r.get("property_num"))
            types_by_lv.append(tuple(a for a, _ in pairs))
        pres = tuple((_int(r["level"]), gate_token(r.get("building_pre"))) for r in rows)
        has_gate = any(p is not None for _, p in pres)
        crow = col_by_id.get(gid)
        decorations[gid] = Decoration(
            group_id=gid,
            name=name,
            name_key=name_key,
            name_src=name_src,
            desc=desc,
            max_level=_int(max_row["level"]),
            total_nums=tuple(_int(r["total_num"]) for r in rows),
            fight=_int(max_row["fight"]),
            score=_int(max_row["score"]),
            self_attrs=self_attrs,
            alliance_attrs=alliance_attrs,
            attr_types_by_level=types_by_lv,
            building_pre=pres,
            has_gate=has_gate,
            time_type=None if is_empty(max_row.get("time_type")) else _int(max_row.get("time_type")),
            time_para1="" if is_empty(max_row.get("time_para1")) else str(max_row.get("time_para1")),
            reward="" if is_empty(max_row.get("reward")) else str(max_row.get("reward")),
            display="" if is_empty(max_row.get("display")) else str(max_row.get("display")),
            suit_ids=list(deco_to_suits.get(gid) or []),
            collection_quality=None if not crow or is_empty(crow.get("quality")) else _int(crow.get("quality")),
            collection_theme=None if not crow or is_empty(crow.get("theme")) else _int(crow.get("theme")),
            is_treasure=gid in treasure_ids,
            no_self_attrs=not self_attrs,
        )

    attrs: dict[int, AttrInfo] = {}

    def ensure_attr(aid: int) -> AttrInfo:
        if aid not in attrs:
            attrs[aid] = _attr_info(aid, attr_by)
        return attrs[aid]

    for aid in sorted(used_attr_ids):
        ensure_attr(aid)
    ensure_attr(999)

    # suits
    prop_by_suit: dict[int, list[dict]] = defaultdict(list)
    for row in suit_prop_rows:
        prop_by_suit[_int(row["group_id"])].append(row)
    for sid in prop_by_suit:
        prop_by_suit[sid].sort(key=lambda r: _int(r["level"]))

    suits: dict[int, SuitInfo] = {}
    for srow in suit_rows:
        sid = _int(srow["id"])
        name_key = str(srow.get("name") or "")
        name = official_text(name_key) if name_key else f"（無名稱）"
        members = suit_members.get(sid) or []
        def_self = parse_pairs(srow.get("attrs") or srow.get("attibute"))
        def_alliance = parse_pairs(srow.get("alliance_attrs") or srow.get("property_alliance"))
        used_attr_ids.update(a for a, _ in def_self + def_alliance)
        for aid, _ in def_self + def_alliance:
            ensure_attr(aid)
        def_fight = None if is_empty(srow.get("suit_fightforce")) else _int(srow.get("suit_fightforce"))
        levels: list[SuitLevel] = []
        for prow in prop_by_suit.get(sid) or []:
            sa = parse_pairs(prow.get("normalAttrs") or prow.get("property_num"))
            aa = parse_pairs(prow.get("alliance_attrs") or prow.get("property_alliance"))
            used_attr_ids.update(a for a, _ in sa + aa)
            for aid, _ in sa + aa:
                ensure_attr(aid)
            levels.append(SuitLevel(
                level=_int(prow["level"]),
                activation=list(prow.get("Activation") or prow.get("activations") or []),
                self_attrs=sa,
                alliance_attrs=aa,
                power=_int(prow["power"]) if not is_empty(prow.get("power")) else 0,
                active_season=None if is_empty(prow.get("active_season")) else _int(prow.get("active_season")),
                property_num_add="" if is_empty(prow.get("property_num_add")) else str(prow.get("property_num_add")),
            ))
        differs = False
        note = ""
        if levels:
            lv1 = levels[0]
            if def_self != lv1.self_attrs or def_alliance != lv1.alliance_attrs or (
                def_fight is not None and def_fight != lv1.power
            ):
                differs = True
                bits = []
                if def_self != lv1.self_attrs:
                    bits.append("自身屬性不同")
                if def_alliance != lv1.alliance_attrs:
                    bits.append("公會屬性不同")
                if def_fight is not None and def_fight != lv1.power:
                    bits.append(f"定義列戰力 {comma(def_fight)}、第 1 級戰力 {comma(lv1.power)}")
                note = "；".join(bits)
        typ = None if is_empty(srow.get("type")) else _int(srow.get("type"))
        alli_max = srow.get("property_alliance_max_num")
        suits[sid] = SuitInfo(
            suit_id=sid,
            name=name,
            name_key=name_key,
            typ=typ,
            members=members,
            member_count=len(members),
            def_self=def_self,
            def_alliance=def_alliance,
            def_fight=def_fight,
            season_diy_ids=_season_diy_ids(srow.get("season_DIY_id") or srow.get("season_DIY_ids")),
            unlock_days=fmt_field(srow.get("unlock_days")),
            unlock_season=fmt_field(srow.get("unlock_season")),
            unlocktime=fmt_field(srow.get("unlocktime")),
            alliance_max_num=EMPTY if is_empty(alli_max) else str(alli_max),
            is_show=fmt_field(srow.get("is_show")),
            levels=levels,
            def_differs_from_lv1=differs,
            def_diff_note=note,
        )

    skills: list[SkillRow] = []
    skills_by_tower: dict[int, list[SkillRow]] = defaultdict(list)
    for row in skill_rows:
        gid = _int(row["group_id"])
        key = str(row.get("desc") or "")
        params = row.get("DescParamArray") or []
        if not params and row.get("desc_parameter"):
            params = str(row.get("desc_parameter")).split("|")
        params = [str(x) for x in params]
        text = fill_text(t(key, "") if has_key(key) else "", params)
        if has_key(key):
            USED_KEYS.add(key)
        else:
            MISSING_KEYS.add(key)
        rec = SkillRow(
            group_id=gid,
            season=_int(row.get("season") or 0),
            typ=_int(row.get("type") or 0),
            level=_int(row["level"]),
            desc_key=key,
            params=params,
            params_text="|".join(params),
            race=_int(row.get("race") or 0),
            text=text,
        )
        skills.append(rec)
        skills_by_tower[gid].append(rec)
    for gid in skills_by_tower:
        skills_by_tower[gid].sort(key=lambda r: (r.season, r.level))

    # guild
    prop_by_guild: dict[int, list[dict]] = defaultdict(list)
    for row in alliance_prop_rows:
        prop_by_guild[_int(row["group_id"])].append(row)
        used_attr_ids.update(a for a, _ in parse_pairs(row.get("ownAttribute") or row.get("property_num")))
    for aid in sorted(used_attr_ids):
        ensure_attr(aid)

    guild_map: dict[int, GuildDeco] = {}
    for row in alliance_rows:
        did = _int(row["id"])
        idx = did - 10000
        name_key = f"alliance_decorations_name{idx}"
        obtain_key = f"alliance_decorations_item_desc{idx}"
        obtain = official_text(obtain_key)
        name_from_obtain = not has_key(name_key)
        if name_from_obtain:
            name = ""
            m = re.search(r"[：:]([^。（]+)[。（]", obtain)
            if m:
                name = m.group(1).strip()
        else:
            name = official_text(name_key)
        max_row = max(prop_by_guild.get(did) or [], key=lambda r: _int(r["level"]), default=None)
        max_attrs = parse_pairs(max_row.get("ownAttribute") or max_row.get("property_num")) if max_row else []
        for aid, _ in max_attrs:
            ensure_attr(aid)
        guild_map[did] = GuildDeco(
            deco_id=did,
            name=name,
            name_key=None if name_from_obtain else name_key,
            name_from_obtain=name_from_obtain,
            obtain=obtain,
            quality=_int(row.get("quality") or 0),
            season=None if is_empty(row.get("season")) else _int(row.get("season")),
            unlocktime=fmt_field(row.get("unlocktime")),
            max_attrs=max_attrs,
            suit_id=_int(row.get("suit_id") or 0),
        )
    guild = []
    seen_g = set()
    for did in GUILD_ORDER:
        if did in guild_map:
            guild.append(guild_map[did])
            seen_g.add(did)
    for did in sorted(guild_map):
        if did not in seen_g:
            guild.append(guild_map[did])

    name_only: list[NameOnly] = []
    for gid in NAME_ONLY_CHAPTER:
        key = f"citybuilding_DIY_name_{gid}"
        name_only.append(NameOnly(
            group_id=gid,
            name=official_text(key),
            name_key=key,
            desc=official_text(f"citybuilding_DIY_des_{gid}"),
            later=False,
            source="diy_name",
        ))
    for gid in NAME_ONLY_LATER:
        key = f"citybuilding_DIY_name_{gid}"
        name_only.append(NameOnly(
            group_id=gid,
            name=official_text(key),
            name_key=key,
            desc=official_text(f"citybuilding_DIY_des_{gid}"),
            later=True,
            source="diy_name",
        ))

    def_only: list[NameOnly] = []
    def_by_id = { _int(r["id"]): r for r in diy_def_rows }
    for gid in DEF_ONLY_LATER:
        row = def_by_id.get(gid) or {}
        nkey = str(row.get("name") or f"collection_name_{gid}")
        dkey = str(row.get("desc") or f"citybuilding_DIY_des_{gid}")
        def_only.append(NameOnly(
            group_id=gid,
            name=official_text(nkey),
            name_key=nkey,
            desc=official_text(dkey),
            later=True,
            source="definition",
        ))

    leftover_suit_names = []
    used_suit_keys = {s.name_key for s in suits.values()}
    strings = load_strings()
    for key in sorted(k for k in strings if k.startswith("citybuilding_DIY_suit_name_")):
        if key not in used_suit_keys:
            leftover_suit_names.append((key, official_text(key), key in json.loads(
                PACK_STRINGS["2026-11-05"].read_text(encoding="utf-8-sig")
            )))

    junk: list[NameOnly] = []
    for row in sorted(junk_rows, key=lambda r: _int(r["id"])):
        jid = _int(row["id"])
        nkey = f"goods_name_{jid}"
        dkey = f"goods_desc_{jid}"
        junk.append(NameOnly(
            group_id=jid,
            name=official_text(nkey),
            name_key=nkey,
            desc=official_text(dkey) if has_key(dkey) else "",
            later=False,
            source="junk",
        ))

    # official phrases
    theme_names = {tid: official_text(THEME_NAME_KEYS[tid]) for tid in THEME_IDS}
    filter_type1 = [official_text(r["attr_name"]) for r in filter_rows if _int(r.get("type") or 0) == 1]
    town_univ = []
    for iid, label in (
        (410295001, "藍色"), (410295002, "紫色"), (410295003, "橙色"), (410295004, "紅色"),
    ):
        town_univ.append((iid, official_text(f"goods_name_{iid}"), official_text(f"goods_desc_{iid}") or official_text(f"goods_des_{iid}")))
    guild_univ = []
    for iid in (505160008, 505160009, 505160010, 505160011):
        guild_univ.append((iid, official_text(f"goods_name_{iid}"), official_text(f"goods_desc_{iid}") or official_text(f"goods_des_{iid}")))

    # function 223/224 just to record keys
    official_text("ui_shop_name_1001")
    official_text("decoration_shop_1004")
    official_text("hero_attr_dec_citydiy")
    official_text("hero_attr_dec_citydiysuit")
    official_text("citybuilding_name_117")
    official_text("collection_dig_rule_title")
    official_text("collection_dig_rule_desc_1")
    official_text("collection_dig_rule_desc_2")
    official_text("UI_Common_Tips_027")
    official_text("citybuilding_diy_lvup")
    official_text("citybuilding_diy_allance_content")
    official_text("diy_alliance_effect_member_tip")
    official_text("alliance_bastion_04_014")
    official_text("guild_decoration_tips_1")
    official_text("attribute_name_3")
    official_text("attribute_name_4")
    official_text("attribute_name_103")
    official_text("attribute_name_104")

    official = Official(
        tip_upgrade=official_text("UI_Common_Tips_027"),
        tip_no_universal=official_text("citybuilding_diy_lvup"),
        tip_alliance=official_text("citybuilding_diy_allance_content"),
        tip_alliance_key="citybuilding_diy_allance_content",
        tip_member=official_text("diy_alliance_effect_member_tip"),
        tip_territory=official_text("alliance_bastion_04_014"),
        tip_guild_cap=official_text("guild_decoration_tips_1"),
        shop_name=official_text("ui_shop_name_1001"),
        shop_mall=official_text("decoration_shop_1004"),
        attr_src=official_text("hero_attr_dec_citydiy"),
        attr_suit_src=official_text("hero_attr_dec_citydiysuit"),
        castle_name=official_text("citybuilding_name_117"),
        dig_title=official_text("collection_dig_rule_title"),
        dig_rule_1=official_raw("collection_dig_rule_desc_1"),
        dig_rule_2=official_raw("collection_dig_rule_desc_2"),
        junk_item_desc=official_text("goods_desc_4001"),
        theme_names=theme_names,
        filter_names=filter_type1,
        town_univ=town_univ,
        guild_univ=guild_univ,
        alliance_name_3=official_text("attribute_name_3"),
        alliance_name_4=official_text("attribute_name_4"),
        hero_atk=official_text("attribute_name_103"),
        hero_hp=official_text("attribute_name_104"),
    )

    terms: list[str] = []
    def add_term(text: str) -> None:
        if text and text not in terms and text not in (EMPTY, DASH):
            terms.append(text)
    for phrase in (
        official.tip_upgrade, official.tip_no_universal, official.tip_alliance,
        official.tip_member, official.tip_territory, official.tip_guild_cap,
        official.shop_name, official.shop_mall, official.attr_src, official.attr_suit_src,
        official.castle_name, official.dig_title, official.junk_item_desc,
        official.alliance_name_3, official.alliance_name_4, official.hero_atk, official.hero_hp,
        "裝飾物套裝", "裝飾物", "裝飾物商城", "城鎮裝飾", "公會裝飾物", "世界大尋寶",
        "聯盟聖塔", "部族聖塔", "自然聖塔", "聯盟精英·聖輝", "部族精英·霸業", "自然精英·永恆",
        "雲海紀行", "馴龍高手第二期", "馴龍高手", "歡迎光臨", "金甲統禦不可撼動。",
        "部落榮耀", "部族", "聯盟", "自然", "專武總表", "英靈總表", "造型總表",
        "裝備總表", "領主裝備總表", "士兵總表", "秘寶總表", "寵物總表", "符文總表",
    ):
        add_term(phrase)
    for info in attrs.values():
        add_term(info.name)
    for deco in decorations.values():
        add_term(deco.name)
    for s in suits.values():
        add_term(s.name)
    for item in name_only + def_only + junk:
        add_term(item.name)
    for g in guild:
        add_term(g.name)
    for _, name, desc in official.town_univ + official.guild_univ:
        add_term(name)
        add_term(desc)
    for name in official.filter_names + list(official.theme_names.values()):
        add_term(name)
    for key, name, _ in leftover_suit_names:
        add_term(name)

    table_count = len(list(DATA_DIR.glob("*.json")))
    extract_count = len(list((TOPHEROES_ROOT / "extracts/2026-11-05/data").glob("*.json")))
    sha_ok = True
    sha_failures = []
    for name, expected in TABLE_SHA256.items():
        path = DATA_DIR / name
        if not path.exists():
            sha_ok = False
            sha_failures.append(f"missing {name}")
            continue
        got = file_sha256(path)
        if got != expected:
            sha_ok = False
            sha_failures.append(f"{name} sha mismatch")

    # function 223 / 224 snapshot
    fn223 = next((r for r in function_rows if _int(r.get("id") or 0) == 223), {})
    fn224 = next((r for r in function_rows if _int(r.get("id") or 0) == 224), {})

    table_meta = {
        "table_count": table_count,
        "extract_2026_11_05_table_count": extract_count,
        "property_rows": len(property_rows),
        "suit_rows": len(suit_rows),
        "suit_prop_rows": len(suit_prop_rows),
        "skill_rows": len(skill_rows),
        "filter_rows": len(filter_rows),
        "alliance_rows": len(alliance_rows),
        "alliance_prop_rows": len(alliance_prop_rows),
        "collection_rows": len(collection_rows),
        "treasure_count": len(treasure_ids),
        "junk_count": len(junk),
        "milestone_rows": len(milestone_rows),
        "refresh_rows": len(refresh_rows),
        "guidebook_rows": len(guidebook_rows),
        "diy_def_rows": len(diy_def_rows),
        "switch_rows": len(switch_rows),
        "diy_name_keys": sum(1 for k in strings if k.startswith("citybuilding_DIY_name_")),
        "fn223_name": fn223.get("name"),
        "fn223_panel": fn223.get("openPanel"),
        "fn223_param": fn223.get("func_open_param"),
        "fn224_name": fn224.get("name"),
        "fn224_panel": fn224.get("openPanel"),
        "fn224_param": fn224.get("func_open_param"),
        "table_cmp": _compare_table_packs(COMPARE_TABLES),
        "string_cmp": None,  # filled after used keys settle
    }

    deco_order = sorted(decorations)
    data = TablesData(
        official=official,
        attrs=attrs,
        decorations=decorations,
        deco_order=deco_order,
        suits=suits,
        skills=skills,
        skills_by_tower=dict(skills_by_tower),
        guild=guild,
        junk=junk,
        name_only=name_only,
        def_only=def_only,
        leftover_suit_names=leftover_suit_names,
        terms=terms,
        table_meta=table_meta,
    )
    table_meta["string_cmp"] = _compare_string_packs(set(USED_KEYS))
    data.verifications = _verify(data)
    data.verifications["sha_ok"] = sha_ok
    data.verifications["missing_keys"] = sorted(MISSING_KEYS)
    if sha_failures:
        data.verifications["failures"] = list(data.verifications.get("failures") or []) + sha_failures
        data.verifications["passed"] = False
    return data


def _curve_counts(data: TablesData) -> dict[int, int]:
    out: dict[int, int] = Counter()
    for deco in data.decorations.values():
        out[deco.max_level] += 1
    return dict(out)


def _verify(data: TablesData) -> dict:
    failures: list[str] = []
    decos = data.decorations
    n = len(decos)
    rows = data.table_meta["property_rows"]
    src = Counter(d.name_src for d in decos.values())
    treasure_named = sum(1 for d in decos.values() if d.name_src == "collection" and d.is_treasure)
    col_not_detail = [d.group_id for d in decos.values() if d.name_src == "collection" and not d.is_treasure]
    curves = _curve_counts(data)
    gate_n = sum(1 for d in decos.values() if d.has_gate)
    no_gate_15 = sorted(d.group_id for d in decos.values() if d.max_level == 15 and not d.has_gate)
    share = [d.group_id for d in decos.values() if d.alliance_attrs]
    q = Counter(g.quality for g in data.guild)
    diy_named = [d for d in decos.values() if d.name_src == "diy"]
    in_members = [d for d in diy_named if d.suit_ids]
    not_members = [d.group_id for d in diy_named if not d.suit_ids]
    std_gate = sum(1 for d in decos.values() if d.building_pre == STANDARD_GATE)
    later_named = [x for x in data.name_only if x.later]
    chapter_named = [x for x in data.name_only if not x.later]

    expected_live = {
        "property_rows": 5810,
        "decorations": 513,
        "diy_named": 321,
        "collection_named": 169,
        "nameless": 23,
        "diy_name_keys": 331,
        "name_only_chapter": 5,
        "name_only_later": 5,
        "suits": 57,
        "treasure": 160,
        "junk": 24,
        "skills": 54,
        "guild": 22,
        "guild_prop": 110,
        "quality_3": 13,
        "quality_4": 7,
        "quality_5": 2,
        "max15": 342,
        "max4": 160,
        "max9": 3,
        "max3": 1,
        "max2": 3,
        "max1": 4,
        "castle_gate": 340,
        "totem_no_gate": 2,
        "guild_share": 9,
        "diy_in_members": 317,
        "named_not_in_members": 4,
        "standard_gate": 334,
    }
    got = {
        "property_rows": rows,
        "decorations": n,
        "diy_named": src.get("diy", 0),
        "collection_named": src.get("collection", 0),
        "nameless": src.get("none", 0),
        "diy_name_keys": data.table_meta["diy_name_keys"],
        "name_only_chapter": len(chapter_named),
        "name_only_later": len(later_named),
        "suits": len(data.suits),
        "treasure": data.table_meta["treasure_count"],
        "junk": len(data.junk),
        "skills": len(data.skills),
        "guild": len(data.guild),
        "guild_prop": data.table_meta["alliance_prop_rows"],
        "quality_3": q.get(3, 0),
        "quality_4": q.get(4, 0),
        "quality_5": q.get(5, 0),
        "max15": curves.get(15, 0),
        "max4": curves.get(4, 0),
        "max9": curves.get(9, 0),
        "max3": curves.get(3, 0),
        "max2": curves.get(2, 0),
        "max1": curves.get(1, 0),
        "castle_gate": gate_n,
        "totem_no_gate": len(no_gate_15),
        "guild_share": len(share),
        "diy_in_members": len(in_members),
        "named_not_in_members": len(not_members),
        "standard_gate": std_gate,
    }
    for key, exp in expected_live.items():
        if got.get(key) != exp:
            failures.append(f"{key}: got {got.get(key)}, expected {exp}")
    if no_gate_15 != list(TOTEM_IDS):
        failures.append(f"totem ids {no_gate_15}")
    if sorted(not_members) != sorted(NAMED_NOT_IN_MEMBERS):
        failures.append(f"named not in members {not_members}")
    if sorted(col_not_detail) != sorted([151602, 151501, 151502, 151401, 151402, 1003041, 1003042, 1003043, 1003044]):
        failures.append(f"collection-named not in detail {col_not_detail}")
    if set(data.suits) != set(SUIT_ORDER):
        failures.append(f"suit ids mismatch {sorted(set(data.suits) ^ set(SUIT_ORDER))}")
    # cost_resource empty already known; welcome extra attr
    welcome = decos.get(WELCOME_ID)
    if not welcome or welcome.attr_types_by_level != [(1044,), (1044,), (1044, 1194)]:
        failures.append("welcome attr types")
    changes = [d.group_id for d in decos.values() if len(set(d.attr_types_by_level)) > 1]
    if changes != [WELCOME_ID]:
        failures.append(f"attr type changes {changes}")
    # skill quotes
    alli = [s for s in data.skills_by_tower.get(308501, []) if s.season == 0 and s.level == 1]
    if not alli or alli[0].text != "戰鬥開始時，隨機1位聯盟英雄生命提升40%":
        failures.append(f"skill s0 lv1 {alli[0].text if alli else None}")
    alli6 = [s for s in data.skills_by_tower.get(308501, []) if s.season == 0 and s.level == 6]
    expect6 = "戰鬥開始時，隨機1位聯盟英雄生命提升90%；若己方隊列中有6名聯盟英雄，則總共會隨機加持2位聯盟英雄且其中一位必定為站位為前排的英雄"
    if not alli6 or alli6[0].text != expect6:
        failures.append(f"skill s0 lv6 {alli6[0].text if alli6 else None}")
    # 151601 official 統禦
    d151 = decos.get(ID_151601)
    if not d151 or "統禦" not in d151.desc or "統御" in d151.desc:
        failures.append("151601 desc")
    # show_type 2 stays raw: just ensure we didn't convert in storage (ints)
    # 雲海紀行 name
    s57 = data.suits.get(57)
    if not s57 or s57.name != "雲海紀行":
        failures.append("suit 57 name")
    # guild 啟動 vs 啟用
    start_ids = [g.deco_id for g in data.guild if "啟動" in g.obtain]
    if start_ids != [10017, 10018, 10019]:
        failures.append(f"啟動 ids {start_ids}")

    chapter_diffs = [
        "屬性表 5,810 筆／513 件，第 16 章依 2026-11-05 解壓檔寫 5,780 筆／511 件。多出的兩件是幸運火雞（133524）、豐饒果籃（133525），已列入環球佳節（套裝 3301）成員（該套由 15 件增至 17 件）。",
        "citybuilding_DIY_name_* 現行 331 鍵，第 16 章寫 324 鍵。除上述兩件有屬性列的新名稱外，另有 5 個只有名稱、沒有屬性列的編號：鎮脈塔、地脈樞紐、深岩礦場、霜焰地泉、幽光岩蕈（159501–159505）。這 7 個鍵在 2026-11-05 字串表沒有，2026-11-22 與 LocalLow 字串表都有。",
        "15 級件 342（第 16 章 340）；有城堡條件的 340 件（第 16 章 338），全部仍是 15 級件。新增兩件採標準城堡條件。沒有城堡條件的 15 級件仍是鷹之圖騰（108501）、熊之圖騰（108502）。",
        "第 16 章寫「15 級裝飾物從第 6 級起有城堡等級條件」。現行包與 2026-11-05 解壓檔都已是：334 件從第 6 級起；幽蘭路燈（107404）、雪中舞（501501）、雙生玫瑰（501502）只在 14–15 級有 117|75／117|80；統治神像、平衡神像、征服神像（111501–111503）從第 10 級起有 117|55。本頁照表記錄，不改寫成一律從第 6 級起。",
        "第 16 章寫「套裝定義列上的屬性等於套裝等級表第 1 級（若有等級表）」。現行包與 2026-11-05 解壓檔已有例外：永世名將定義列公會礦採集速度（1263）為 4、戰力 30,000，等級表第 1 級為 400、戰力 26,000；雲海巡航定義列是出征上限／暴擊／抗暴，等級表第 1 級與滿級是所有士兵攻擊／生命與增傷。本頁兩種都照錄，不另寫合併公式。",
        "LocalLow／現行包另有 citybuilding_DIY.json（515 筆）與 citybuilding_DIY_switch.json（15 筆），2026-11-05 與 2026-11-22 解壓檔沒有這兩張表。本頁名錄仍以屬性表 group_id 為準，不用定義表去補一般城鎮裝飾與萬能裝飾物的顏色對照（該項維持待補）。定義表多出、屬性表沒有的編號是門廊（1009998）、獸骨帳篷（1009999），名稱取自 collection_name_*。",
        "字串表另有 citybuilding_DIY_suit_name_59「地心探險」，沒有對應套裝定義列（57 套套裝未變）。citybuilding_DIY_suit_name_12「氏族之力」在 2026-11-05 字串表已有，同樣沒有套裝定義列（沒有編號 12、34、36）。",
        "collection_detail.json 仍是 184 筆（藏品 160、廢品 24）。LocalLow／現行包只在 Offset 欄與 2026-11-05／2026-11-22 解壓檔不同，本頁不用這個欄位。",
    ]
    return {
        "passed": not failures,
        "failures": failures,
        "counts": got,
        "chapter_diffs": chapter_diffs,
        "col_not_detail": col_not_detail,
        "share_ids": share,
        "std_gate": std_gate,
        "treasure_named": treasure_named,
    }


def _suit_anchor(suit_id: int) -> str:
    return f"suit-{suit_id}"


def _deco_note(deco: Decoration, data: TablesData, *, html: bool = False) -> str:
    bits: list[str] = []
    if deco.time_type is not None:
        bits.append(f"時間類型 {deco.time_type}")
    if deco.time_para1:
        if deco.group_id == TREE_ID:
            bits.append("時間參數表上沒有說明含義，對照見資料說明")
        else:
            bits.append(f"時間 {format_timerange(deco.time_para1)}")
    if deco.reward:
        if deco.group_id == CRYSTAL_ID:
            bits.append("每日獎勵第 1 級 4,000、滿級 15 為 96,000；類型 999 與中段 6 沒有官方名稱")
        elif deco.group_id in ELITE_IDS:
            bits.append("每日獎勵沒有官方名稱（原值見資料說明）")
        elif deco.group_id == TREE_ID:
            bits.append("每日獎勵 驚喜寶箱 ×2")
        else:
            bits.append(f"每日獎勵 {deco.reward}")
    if deco.is_treasure and deco.collection_quality is not None:
        bits.append(f"收藏品質 {deco.collection_quality}")
    if deco.group_id == WELCOME_ID:
        bits.append("第 3 級多一條屬性，其餘等級屬性種類從第 1 級就固定")
    if deco.group_id in NAMELESS_NOT_IN_SUIT:
        snow = data.decorations.get(SNOWMAN_ID)
        snow_name = snow.name if snow else "雪人"
        if html:
            bits.append(f"模型路徑與{snow_name}（{SNOWMAN_ID}）相同；沒有說明")
        else:
            bits.append(f"模型路徑為 {deco.display}（與{snow_name} {SNOWMAN_ID} 相同）；沒有說明")
    if deco.group_id == ID_151601:
        rabbit = data.decorations.get(RABBIT_CUP_ID)
        rname = rabbit.name if rabbit else "榮耀金兔杯"
        bits.append(f"說明：「{deco.desc}」；模型路徑指向{rname}（{RABBIT_CUP_ID}）")
    if deco.name_src == "none" and deco.desc and deco.group_id not in NAMELESS_NOT_IN_SUIT and deco.group_id != ID_151601:
        bits.append(f"說明：「{deco.desc}」")
        if deco.suit_ids and 47 in deco.suit_ids:
            bits.append("不以說明裡的角色名當作裝飾物正式名稱")
    if deco.group_id in TOWER_IDS:
        bits.append("沒有自身屬性列，效果見戰鬥技能節")
    if deco.group_id in ELITE_IDS or deco.group_id in (TREE_ID, ANNIV_ID):
        if deco.no_self_attrs:
            bits.append("沒有自身屬性列")
    return "；".join(bits)


def _fmt_suit_attrs(self_attrs, alliance_attrs, attrs, power=None, include_power=False, *, include_id: bool = True) -> str:
    bits = []
    if self_attrs:
        bits.append(fmt_attr_pairs(self_attrs, attrs, include_id=include_id))
    if alliance_attrs:
        bits.append(fmt_attr_pairs(alliance_attrs, attrs, prefix="公會 ", include_id=include_id))
    body = "；".join(bits) if bits else EMPTY
    if include_power and power is not None:
        body = f"{body}；戰力 {comma(power)}" if body != EMPTY else f"戰力 {comma(power)}"
    return body


def _member_text(suit: SuitInfo, data: TablesData, *, html: bool = False) -> str:
    if not suit.members:
        return "此套沒有成員。"
    parts = []
    for mid in suit.members:
        deco = data.decorations.get(mid)
        if deco:
            name = deco_display_name(deco)
            # HTML: official names only; keep ids when there is no official name
            if html and deco.name_src != "none" and deco.name:
                parts.append(name)
            else:
                parts.append(f"{name}（{mid}）")
        else:
            parts.append(f"（無屬性列）（{mid}）")
    return "、".join(parts)


def _published_links_html(terms: list[str]) -> str:
    links = "、".join(f'<a href="{href}">{H(label, terms)}</a>' for href, label in PUBLISHED_LINKS)
    return (
        f"已發佈的{links}是其他系統，不在本頁展開。"
    )


def _published_links_md() -> str:
    links = "、".join(f"[{label}]({href})" for href, label in PUBLISHED_LINKS)
    return f"交叉引用：{links}。"


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    attrs = data.attrs
    o = data.official

    # scope split
    src = Counter(d.name_src for d in data.decorations.values())
    treasure_named = sum(1 for d in data.decorations.values() if d.name_src == "collection" and d.is_treasure)
    col_other = sum(1 for d in data.decorations.values() if d.name_src == "collection" and not d.is_treasure)
    out["scope"] = table(
        ["組別", "數量", "名稱來源", "常見滿級"],
        [
            [
                H("名稱取自城鎮裝飾", terms),
                comma(src.get("diy", 0)),
                "城鎮裝飾",
                "多數 15 級",
            ],
            [
                H("名稱取自收藏", terms),
                comma(src.get("collection", 0)),
                f"其中 {treasure_named} 筆同時在世界大尋寶藏品表（滿級 4、評分欄 -1）；另外 {col_other} 筆不在該表，而是「永世名將」「王國節日」的套裝成員",
                f"{treasure_named} 件為 4 級；其餘 {col_other} 件為 15 級",
            ],
            [
                "尚無名稱字串",
                comma(src.get("none", 0)),
                "部分有說明，或出現在套裝成員裡",
                "多數 15 級",
            ],
        ],
        mobile="cards",
        card_title="組別",
    )

    curves = _curve_counts(data)
    # identify named 1-lv / 2-lv / 3-lv
    def names_for(pred, limit=8):
        items = []
        for deco in data.decorations.values():
            if pred(deco):
                items.append(f"{deco_display_name(deco)}")
        return "、".join(items)

    curve_rows = [
        ["15", comma(curves.get(15, 0)), "60", "1、2、4、7、11、15，之後每級再加 5，直到 60"],
        ["4", comma(curves.get(4, 0)), "4", "1、2、3、4（皆為尋寶藏品）"],
        ["9", comma(curves.get(9, 0)), "30", "1、2、4、7、11、15、20、25、30，與 15 級曲線的前 9 級相同（聯盟／部族／自然聖塔）"],
        ["3", comma(curves.get(3, 0)), "4", f"1、2、4（{names_for(lambda d: d.max_level == 3)}）"],
        ["2", comma(curves.get(2, 0)), "2", f"1、2（{names_for(lambda d: d.max_level == 2)}）"],
        ["1", comma(curves.get(1, 0)), "1", f"只有 1 級（{names_for(lambda d: d.max_level == 1)}）"],
    ]
    out["upgrade"] = table(
        ["最高等級", "件數", "升滿所需個數", "曲線（各級累積個數）"],
        [[e(c) if i != 3 else H(c, terms) for i, c in enumerate(row)] for row in curve_rows],
        mobile="sticky",
    )

    # suits overview
    suit_rows = []
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        typ = EMPTY if suit.typ is None else str(suit.typ)
        def_text = _fmt_suit_attrs(suit.def_self, suit.def_alliance, attrs, include_id=False)
        if suit.alliance_max_num != EMPTY:
            def_text = ("" if def_text == EMPTY else def_text + "；") + f"公會屬性生效人數上限 {suit.alliance_max_num}"
        note = suit.def_diff_note if suit.def_differs_from_lv1 else ""
        if sid == 9999:
            note = ("；" if note else "") and note
            note = (note + "；" if note else "") + "此套沒有成員"
        if sid == 57:
            note = (note + "；" if note else "") + "只記官方套裝名稱，不把這個名稱當成已核對的官方賽季名，也不把解鎖賽季欄對成日曆賽季"
        suit_rows.append([
            official_term_html(suit.name) if suit.name else e("（無名稱）"),
            typ,
            str(suit.member_count),
            H(_member_text(suit, data, html=True), terms),
            H(def_text, terms) if def_text != EMPTY else EMPTY,
            e(suit.unlock_days),
            e(suit.unlock_season),
            e(format_timerange(suit.unlocktime)),
            H(note, terms) if note else "",
        ])
    out["suits"] = table(
        ["套裝", "類型", "件數", "成員", "套裝屬性（定義列／第 1 級，表上有才寫）", "解鎖天數（只照錄）", "解鎖賽季（只照錄）", "解鎖時間（只照錄）", "備註"],
        suit_rows,
        mobile="cards",
        card_title="套裝",
    )

    # suit levels
    level_rows = []
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        if not suit.levels:
            continue
        lv1, mx = suit.levels[0], suit.levels[-1]
        level_rows.append([
            official_term_html(suit.name),
            str(mx.level),
            e(fmt_activation(lv1.activation)),
            H(_fmt_suit_attrs(lv1.self_attrs, lv1.alliance_attrs, attrs, lv1.power, True, include_id=False), terms),
            e(fmt_activation(mx.activation)),
            H(_fmt_suit_attrs(mx.self_attrs, mx.alliance_attrs, attrs, mx.power, True, include_id=False), terms),
        ])
    out["suit_levels"] = table(
        ["套裝", "最高等級", "啟動欄（第 1 級）", "第 1 級", "啟動欄（滿級）", "滿級"],
        level_rows,
        mobile="cards",
        card_title="套裝",
    )

    def deco_table(ids: list[int], with_quality: bool = False) -> str:
        def _named(gid: int) -> bool:
            deco = data.decorations[gid]
            return deco.name_src != "none" and bool(deco_display_name(deco)) and deco_display_name(deco) != "（無名稱）"
        keep_id = any(not _named(gid) for gid in ids)
        rows = []
        for gid in ids:
            deco = data.decorations[gid]
            note = _deco_note(deco, data, html=True)
            row = [
                official_term_html(deco_display_name(deco)) if deco.name_src != "none" else e("（無名稱）"),
            ]
            if keep_id:
                row.append(str(gid))
            row.extend([
                str(deco.max_level),
                H(fmt_attr_pairs(deco.self_attrs, attrs, include_id=False), terms) if deco.self_attrs else EMPTY,
                H(fmt_attr_pairs(deco.alliance_attrs, attrs, include_id=False), terms) if deco.alliance_attrs else EMPTY,
                comma(deco.fight),
                str(deco.score) if deco.score == -1 else comma(deco.score),
            ])
            if with_quality:
                row.append(str(deco.collection_quality) if deco.collection_quality is not None else EMPTY)
            row.append(H(note, terms) if note else "")
            rows.append(row)
        cols = ["名稱"]
        if keep_id:
            cols.append("編號")
        cols.extend(["滿級", "自身屬性", "公會屬性", "戰力", "評分"])
        if with_quality:
            cols.append("收藏品質")
        cols.append("備註")
        return table(cols, rows, mobile="cards", card_title="名稱")

    out["effects"] = {}
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        out["effects"][sid] = deco_table(suit.members) if suit.members else ""
    out["named_only"] = deco_table([i for i in NAMED_NOT_IN_MEMBERS if i in data.decorations])
    out["treasure"] = {}
    for theme in THEME_IDS:
        ids = [d.group_id for d in sorted(
            (x for x in data.decorations.values() if x.is_treasure and x.collection_theme == theme),
            key=lambda x: x.group_id,
        )]
        out["treasure"][theme] = deco_table(ids, with_quality=True)
    out["nameless_rest"] = deco_table([i for i in NAMELESS_NOT_IN_SUIT if i in data.decorations])

    junk_keep_id = any(not item.name for item in data.junk)
    junk_rows = []
    for item in data.junk:
        row = [official_term_html(item.name) if item.name else e("（無名稱）")]
        if junk_keep_id:
            row.append(str(item.group_id))
        row.extend(["2", "不在城鎮裝飾屬性表"])
        junk_rows.append(row)
    out["junk"] = table(
        (["名稱", "編號", "品質", "備註"] if junk_keep_id else ["名稱", "品質", "備註"]),
        junk_rows,
        mobile="cards",
        card_title="名稱",
    )

    # skills
    def skill_table(tower_id: int, season: int) -> str:
        rows = []
        for rec in data.skills_by_tower.get(tower_id, []):
            if rec.season != season:
                continue
            rows.append([
                str(rec.level),
                e(rec.params_text),
                official_term_html(rec.text),
            ])
        return table(
            ["等級", "參數", "文案（代入參數、已去色碼）"],
            rows,
            mobile="cards",
            card_title="等級",
        )
    skill_meta_rows = []
    skill_keys = {
        308501: ("citybuilding_DIY_skill_1", "citybuilding_DIY_skill_2"),
        308502: ("citybuilding_DIY_skill_3", "citybuilding_DIY_skill_4"),
        308503: ("citybuilding_DIY_skill_5", "citybuilding_DIY_skill_6"),
    }
    for tid in TOWER_IDS:
        k1, k2 = skill_keys[tid]
        skill_meta_rows.append([
            official_term_html(data.decorations[tid].name),
            "見下表" if tid == 308501 else "參數與聯盟聖塔相同",
        ])
    out["skill_meta"] = table(
        ["裝飾物", "備註"],
        skill_meta_rows,
        mobile="cards",
        card_title="裝飾物",
    )
    out["skill0"] = skill_table(308501, 0)
    out["skill1"] = skill_table(308501, 1)

    guild_rows = []
    for g in data.guild:
        name = official_term_html(g.name) if g.name else e("（無名稱）")
        if g.name_from_obtain:
            name = name + e("（名稱取自獲得說明）")
        guild_rows.append([
            name,
            str(g.quality),
            H(fmt_attr_pairs(g.max_attrs, attrs, include_id=False), terms) if g.max_attrs else EMPTY,
            e(str(g.season) if g.season is not None else EMPTY),
            e(format_timerange(g.unlocktime)),
        ])
    out["guild"] = table(
        ["裝飾物", "品質", "滿級屬性", "賽季欄（只照錄）", "解鎖時間（只照錄）"],
        guild_rows,
        mobile="cards",
        card_title="裝飾物",
    )

    name_only_rows = []
    for item in data.name_only:
        name_only_rows.append([
            official_term_html(item.name) if item.name else e("（無名稱）"),
            e("後續包新增" if item.later else "第 16 章已列"),
            official_term_html(item.desc) if item.desc else EMPTY,
        ])
    out["name_only"] = table(
        ["名稱", "來源", "說明"],
        name_only_rows,
        mobile="cards",
        card_title="名稱",
    )
    return out


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
        extra = f"本頁用到的 {sc['used_keys']} 個字串鍵，在有該鍵的包裡值相同。"
    # 2026-11-05 is missing the 7 later name keys etc.

    def pack_note(name: str, label: str) -> str:
        rec = tc[name]
        if not rec["present"].get("live"):
            return f"`{name}`（{label}）現行包沒有此表。"
        rows = rec["rows"]["live"]
        raw_bytes = rec["bytes"]["live"]
        sha = rec["sha256"]["live"]
        present = [p for p, ok in rec["present"].items() if ok]
        identical = [p for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow") if rec["identical"].get(p)]
        missing_p = [p for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow") if not rec["present"].get(p)]
        if not missing_p and len(identical) == 3:
            same = "四份包位元組相同"
        elif missing_p and len(identical) == len([p for p in present if p != "live"]):
            same = f"只出現在 {'、'.join(present)}；" + "、".join(missing_p) + " 沒有此表，出現的包與現行檔位元組相同"
        elif missing_p:
            same = f"只出現在 {'、'.join(present)}；" + "、".join(missing_p) + " 沒有此表"
        else:
            same = "四份包並非全部位元組相同"
            details = []
            for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow"):
                if rec["identical"].get(p):
                    details.append(f"{p} 相同")
                else:
                    details.append(
                        f"{p} {rec['rows'][p]} 筆、{rec['bytes'][p]} bytes，sha256 {rec['sha256'][p]}"
                    )
            same += "（" + "；".join(details) + "）"
        return f"`{name}`（{label}）{rows} 筆、{raw_bytes} bytes，sha256 {sha}，{same}。"

    attr = tc["attribute.json"]
    attr_note = (
        f"`attribute.json` 列數同為 {attr['rows']['live']}；"
        "現行檔與 2026-11-22、2026-11-22 LocalLow 位元組相同，"
        f"sha256 {attr['sha256']['live']}。"
        f"2026-11-05 解壓檔列數相同（{attr['rows']['2026-11-05']} 筆）但檔案較小"
        f"（{attr['bytes']['2026-11-05']} bytes，sha256 {attr['sha256']['2026-11-05']}），"
        "差在後來多了 NameKey、name_season 欄；本頁用到的屬性 id、type、show_type 與 "
        "`attribute_name_{id}` 並未因此改變。"
    )
    return (
        f"資料截至 {DECORATION_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {DECORATION_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {DECORATION_DATA_PACKED}（香港時間）。"
        f"第 16 章第一版寫於 {CHAPTER_FIRST_EDITION}（香港時間），標題仍寫來源解壓日期 2026-11-05"
        f"（{data.table_meta['extract_2026_11_05_table_count']} 張表）。"
        "本頁正文改用現行 LocalLow 包，與章節不一致的數字會在下面單獨列出。"
        + pack_note("citybuilding_DIY_property.json", "城鎮裝飾屬性，名錄以 group_id 為準")
        + pack_note("citybuilding_DIY_suit.json", "城鎮裝飾套裝定義")
        + pack_note("citybuilding_DIY_suit_property.json", "套裝等級表")
        + pack_note("citybuilding_DIY_skill.json", "聖塔技能")
        + pack_note("citybuilding_diy_filter.json", "篩選分類")
        + pack_note("alliance_decorations.json", "公會裝飾物")
        + pack_note("alliance_decorations_property.json", "公會裝飾物屬性")
        + pack_note("collection_detail.json", "世界大尋寶藏品與廢品")
        + pack_note("collection_theme_milestone.json", "尋寶主題里程碑")
        + pack_note("collection_refresh.json", "尋寶刷新")
        + pack_note("citybuilding_guidebook.json", "城市建築圖鑑，本頁不展開")
        + pack_note("citybuilding_DIY.json", "後續包才出現的定義表，本頁不用它當名錄")
        + pack_note("citybuilding_DIY_switch.json", "後續包才出現，本頁不展開")
        + attr_note
        + extra
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜裝飾物總表"
    summary = (
        "分開登錄兩套系統：擺在自己主城的城鎮裝飾，以及擺在公會領地的公會裝飾物。"
        "含套裝、滿級自身與公會屬性、三座聖塔技能與尋寶藏品。"
    )
    toc_items = [
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍與資料表"},
        {"id": "upgrade", "label": "城鎮裝飾：升級"},
        {"id": "stats", "label": "戰力、評分、自身與公會屬性"},
        {"id": "skills", "label": "戰鬥技能（三座聖塔）"},
        {"id": "suits", "label": "城鎮裝飾套裝"},
        {"id": "suit-levels", "label": "套裝等級表", "depth": 1},
        {"id": "effects", "label": "各城鎮裝飾滿級效果"},
    ]
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        toc_items.append({"id": _suit_anchor(sid), "label": suit.name, "depth": 1})
    toc_items += [
        {"id": "named-only", "label": "有名稱但不在套裝成員列", "depth": 1},
        {"id": "treasure", "label": "尋寶藏品", "depth": 1},
        {"id": "junk", "label": "尋寶廢品", "depth": 1},
        {"id": "nameless-rest", "label": "其餘尚無名稱、也不在套裝", "depth": 1},
        {"id": "guild", "label": "公會裝飾物"},
        {"id": "unmatched", "label": "尚無名稱或對不上的城鎮裝飾"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ]
    toc = toc_list(toc_items)
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{LEDE}</p>')
    add(f"    {toc}")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        "本頁分開列出兩套系統，不要混為一套："
        "擺在自己主城的城鎮裝飾，"
        "以及擺在公會領地的公會裝飾物。"
        "英雄造型、領主裝扮、聊天與社交皮膚、行軍造型是另外的系統，這裡只一筆帶過，不展開。"
        f"城堡外觀見<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>，不在本頁展開。"
    ))
    add(p_html(_published_links_html(terms)))
    add("<ul>")
    add(
        "<li><strong>正文只根據遊戲資料表。</strong>"
        "表上沒有的標未驗證或待補，不編造公式或名稱。</li>"
    )
    add(
        f"<li><strong>名錄先列有屬性的城鎮裝飾</strong>（目前 {comma(len(data.decorations))} 個）。"
        "另有只有名稱、沒有屬性列的編號，見範圍一節。資料表檔名與筆數見資料說明。</li>"
    )
    add(
        "<li><strong>屬性只錄表上的原值</strong>，不自行換成百分比。"
        "技能說明若已寫成百分比，照錄官方文案。點數與百分比兩類同名屬性不要混成同一欄，對照見資料說明。</li>"
    )
    add(
        "<li><strong>不依解鎖時間、解鎖賽季、解鎖天數、賽季或伺服器欄位標未開放。</strong>表上有這些欄位的，只照錄。"
        "有一類套裝名稱對得上若干賽季稱呼，且帶有解鎖賽季欄，同樣只照錄，"
        f"不把官方套裝名稱「{official_term_html('雲海紀行')}」當成已核對的官方賽季名。"
        "欄位名見資料說明。</li>"
    )
    add(
        "<li>升級不消耗資源欄（全表為空），而是累積同一件裝飾物。介面寫"
        f"「{official_term_html(o.tip_upgrade)}」。欄位與字串鍵見資料說明。</li>"
    )
    add(
        "<li>一般城鎮裝飾的主表沒有品質欄。公會裝飾物與世界大尋寶藏品有品質欄，照錄。"
        "藍、紫、橙、紅萬能裝飾物與各件如何對色，表上沒有直接欄位，維持待補。</li>"
    )
    add(
        "<li>各件只列滿級自身屬性與公會屬性（若有）。除"
        f"「{H('歡迎光臨', terms)}」在第 3 級多一條屬性外，其餘有屬性列的裝飾物，屬性種類從第 1 級就固定，只是數值隨等級提高。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍與資料表</h2>")
    add(p_html(
        f"介面稱{H(o.attr_src, terms)}。功能表編號 223 的名稱是「{official_term_html(o.shop_name)}」，開啟的是商店面板；"
        f"商店另有字串「{official_term_html(o.shop_mall)}」。"
        f"編號 224 開啟個人裝飾面板，沒有獨立名稱，開啟條件對應{H(o.castle_name, terms)} 5 級，"
        "表上沒有把這串條件寫成說明文字。"
        f"英雄屬性來源把這套寫成「{official_term_html(o.attr_src)}」，"
        f"套裝來源寫「{official_term_html(o.attr_suit_src)}」。"
        "功能編號、面板名與字串鍵見資料說明。"
    ))
    add(p_html(
        f"{comma(len(data.decorations))} 個有屬性列的裝飾物可分成三組："
    ))
    add(tbl["scope"])
    chapter_only = "、".join(
        official_term_html(item.name) for item in data.name_only if not item.later
    )
    later_only = "、".join(
        official_term_html(item.name) for item in data.name_only if item.later
    )
    add(p_html(
        f"另有 {len([x for x in data.name_only if not x.later])} 個只有名稱、沒有屬性列的編號（第 16 章已列）："
        f"{chapter_only}。"
        f"後來又多了兩個有屬性列的名稱，以及另外 "
        f"{len([x for x in data.name_only if x.later])} 個只有名稱、沒有屬性列的編號："
        f"{later_only}。"
        "編號對照見資料說明。與第 16 章摘錄、解壓檔的鍵數差異見資料說明。"
    ))
    add(tbl["name_only"])
    filt_names = "、".join(official_term_html(n) for n in o.filter_names)
    add(p_html(
        f"篩選表 {comma(data.table_meta['filter_rows'])} 筆，"
        f"分類名稱包括{filt_names}。類型分成兩組（分類重複一份），"
        "表上沒有類型名稱，本頁不自行解釋。檔名見資料說明。"
    ))
    add("    </section>")

    add('    <section id="upgrade">')
    add("      <h2>城鎮裝飾：升級</h2>")
    add(p_html("各滿級與升滿所需個數（累計值）："))
    add(tbl["upgrade"])
    gate_n = sum(1 for d in data.decorations.values() if d.has_gate)
    totems = "、".join(
        f"{H(data.decorations[i].name, terms)}（{i}）" for i in TOTEM_IDS if i in data.decorations
    )
    add(p_html(
        f"多數 15 級裝飾物從第 6 級起有{H(o.castle_name, terms)}等級條件："
        "6–7 級要 40 級城堡，8 級 45，9 級 50，10–13 級 55，14 級 75，15 級 80。"
        f"{comma(len(data.decorations))} 件裡 {comma(gate_n)} 件有這條條件，全部都是 15 級件。"
        f"{comma(sum(1 for d in data.decorations.values() if d.max_level == 15))} 件 15 級裝飾物之中，"
        f"{totems} 沒有這條城堡條件。"
        f"另有 {comma(len(GATE_FROM_14))} 件只在 14–15 級出現這條條件（"
        + "、".join(f"{H(deco_display_name(data.decorations[i]), terms)}（{i}）" for i in GATE_FROM_14)
        + f"），以及 {comma(len(GATE_FROM_10))} 件從第 10 級起才有"
        "（"
        + "、".join(f"{H(deco_display_name(data.decorations[i]), terms)}（{i}）" for i in GATE_FROM_10)
        + "）。第 16 章把 15 級條件寫成一律從第 6 級起；上述例外在 2026-11-05 解壓檔已是如此，本頁照表記錄。"
    ))
    univ = "、".join(
        f"{official_term_html(name)}（說明「{official_term_html(desc)}」）"
        for iid, name, desc in o.town_univ
    )
    add(p_html(
        f"有藍、紫、橙、紅四種萬能裝飾物：{univ}。"
        "主表沒有品質欄，哪些件能用萬能、什麼顏色對哪一件，表上沒有直接對照。另有一句"
        f"「{official_term_html(o.tip_no_universal)}」，"
        "沒有列出適用或排除的編號。公會另有一套同名色的萬能材料（"
        + "、".join(official_term_html(name) for iid, name, desc in o.guild_univ)
        + "），說明是公會裝飾物專用。"
    ))
    add("    </section>")


    # stats
    add('    <section id="stats">')
    add("      <h2>戰力、評分、自身與公會屬性</h2>")
    fights = [d.fight for d in data.decorations.values()]
    scores = sorted(set(d.score for d in data.decorations.values()))
    f15 = [d.fight for d in data.decorations.values() if d.max_level == 15]
    min_deco = min(data.decorations.values(), key=lambda d: (d.fight, d.group_id))
    add(p_html(
        "每級有戰力和評分。"
        f"滿級戰力最低是 {comma(min(fights))}（{H(deco_display_name(min_deco), terms)}，只有 {min_deco.max_level} 級），"
        f"最高是 {comma(max(fights))}（15 級滿級的上限；15 級件的滿級戰力從 {comma(min(f15))} 到 {comma(max(f15))}）。"
        "滿級評分沒有 0：尋寶藏品 4 級件的評分欄是 -1；其餘滿級評分為 "
        + "、".join(("-1" if s == -1 else comma(s)) for s in scores if s != -1)
        + "。數值都照原值記錄。"
    ))
    share = [d for d in data.decorations.values() if d.alliance_attrs]
    share_txt = "、".join(f"{H(deco_display_name(d), terms)}（{d.group_id}）" for d in sorted(share, key=lambda x: x.group_id))
    max_nums = []
    for sid, label in ((23, "白之戰棋"), (37, "黑之戰棋"), (51, "永世名將"), (56, "失落王朝")):
        suit = data.suits.get(sid)
        if suit:
            max_nums.append(f"{H(suit.name, terms)}為 {e(suit.alliance_max_num)}")
    add(p_html(
        f"{comma(len(share))} 件有公會共享屬性："
        f"{share_txt}。通用介面字串是「{official_term_html(o.tip_alliance)}」。"
        "部分件或套裝另有不同寫法：例如"
        f"{H('黑之皇帝', terms)}／{H('黑之皇后', terms)} 的說明寫「可享受同公會 10 名領主的累加值」；"
        f"介面也有「{official_term_html(o.tip_member)}」。"
        "套裝表的公會屬性生效人數上限："
        + "、".join(max_nums)
        + "。這兩套規則如何同時套用，表上沒有合併說明，本頁只並記，不另寫公式。"
    ))
    add(p_html("少數件有時限或每日獎勵，只照錄，不用來標未開放："))
    add("<ul>")
    crystal = data.decorations[CRYSTAL_ID]
    # reward curve
    prop = None
    add(
        f"<li>{H(crystal.name, terms)}（{CRYSTAL_ID}）：時限類型 {crystal.time_type}，"
        f"時間 {e(format_timerange(crystal.time_para1))}。每日獎勵第 1 級 4,000、滿級 15 為 96,000。"
        "類型 999 與中段 6 在屬性表與官方屬性名裡都沒有名稱。</li>"
    )
    elites = "、".join(f"{H(data.decorations[i].name, terms)}（{i}）" for i in ELITE_IDS)
    e0 = data.decorations[ELITE_IDS[0]]
    add(
        f"<li>{elites}：時限類型 {e0.time_type}，同一段時間；每日獎勵沒有官方名稱（原值見資料說明）。"
        "這三件本身沒有自身屬性列。</li>"
    )
    tree = data.decorations[TREE_ID]
    add(
        f"<li>{H(tree.name, terms)}（{TREE_ID}）：時限類型 {tree.time_type}，"
        "時間參數表上沒有說明含義，對照見資料說明；"
        f"每日獎勵 {H('驚喜寶箱', terms)} ×2。本身沒有自身屬性列。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>戰鬥技能（三座聖塔）</h2>")
    add(p_html(
        f"只有三座聖塔有戰鬥技能（{comma(len(data.skills))} 筆＝3 × 18）。"
        f"{H('聯盟聖塔', terms)}、{H('部族聖塔', terms)}、{H('自然聖塔', terms)} 都沒有自身屬性列，效果只見技能表。"
        "各塔有兩套技能列：第一套與第二套，"
        "各 9 級（與裝飾物滿級 9 一致）。這是表上已寫成百分比的技能文案，與屬性欄的原值記錄不同。"
        "本頁不把這些分列對成日曆賽季，也不據此標未開放。分列欄位見資料說明。"
    ))
    add(p_html(
        "第一套的第 1–5 級用較短文案，第 6–9 級改用較長文案（多了"
        "「若己方隊列中有 6 名該陣營英雄，則總共會隨機加持 2 位，且其中一位必定為站位為前排的英雄」）。"
        "第二套全程用較短文案，但人數與百分比的起始值不同。"
    ))
    add(p_html(
        "三座聖塔的人數與百分比參數完全相同，只是文案裡的陣營"
        "（聯盟 1、部族 2、自然 3）不同。官方陣營用語是「部族」，不是「部落」，"
        f"除非官方字串本身就是「部落」（例如裝飾物名稱「{H('部落榮耀', terms)}」）。"
        "以聯盟聖塔為例（其餘兩座把「聯盟」換成「部族」或「自然」即可）："
    ))
    add(tbl["skill_meta"])
    add("      <h3>第一套技能文案</h3>")
    add(tbl["skill0"])
    add("      <h3>第二套技能文案</h3>")
    add(tbl["skill1"])
    add(p_html(
        f"{H('部族聖塔', terms)}、{H('自然聖塔', terms)}的說明文案與參數與上表相同（說明對照見資料說明）。"
    ))
    add("    </section>")

    add('    <section id="suits">')
    add("      <h2>城鎮裝飾套裝</h2>")
    add(p_html(
        f"城鎮裝飾套裝共 {comma(len(data.suits))} 套（沒有編號 12、34、36；另有 3301、3302、502、503、9999）。"
        "套裝類型欄為 1–5，表上沒有類型名稱。"
        "有一類套裝名稱對得上若干賽季稱呼，且帶有解鎖賽季欄，本頁只照錄，"
        f"不自行對成日曆賽季，也不標未開放，更不把「{official_term_html('雲海紀行')}」寫成已核對的官方賽季名。"
        "解鎖天數與解鎖時間同樣只照錄。欄位名見資料說明。"
    ))
    add(p_html(
        "套裝定義列上的屬性在有等級表時，多數等於第 1 級；"
        f"例外見備註欄與資料說明，例如{H('永世名將', terms)}、{H('雲海巡航', terms)}。"
        f"部分套裝另有套裝等級表（{comma(data.table_meta['suit_prop_rows'])} 筆）："
        "多數為 10 級，信仰為 9 級，搗蛋鬼、夢幻莊園只有 1 級。"
        "各級有啟動欄，表上沒有說明這兩個數字的含義。欄名見資料說明。"
        "下面總表先寫定義列屬性；有等級表的套裝，第 1 級與滿級另列於其後。中間第 2–9 級不展開。"
        f"編號 9999 的「{H('馴龍高手', terms)}」沒有成員；另有「{H('馴龍高手', terms)}」（47）與"
        f"「{H('馴龍高手第二期', terms)}」（55）兩套有成員。"
    ))
    diy_named = [d for d in data.decorations.values() if d.name_src == "diy"]
    not_in = [d for d in diy_named if not d.suit_ids]
    not_in_txt = "、".join(f"{H(d.name, terms)}（{d.group_id}）" for d in not_in)
    add(p_html(
        f"{comma(len(diy_named))} 件名稱來自城鎮裝飾的裝飾物裡，"
        f"{comma(sum(1 for d in diy_named if d.suit_ids))} 件出現在某套套裝成員列；"
        f"不在成員列的 {comma(len(not_in))} 件是{not_in_txt}。"
        "這 4 件編號出現在「世界之最」另外列出的裝飾編號欄，但不在該套的成員列。"
        f"尋寶藏品表的 {comma(data.table_meta['treasure_count'])} 件尋寶藏品都不進這些套裝；"
        "名稱也取自收藏、但不在尋寶藏品表的 9 件，"
        "則分別在「永世名將」與「王國節日」。"
    ))
    add(tbl["suits"])
    add('      <h3 id="suit-levels">套裝等級表（有才列）</h3>')
    add(p_html("下表只列第 1 級與最高級。戰力取戰力欄。另有一欄全為 -1、一欄全空，欄名見資料說明。"))
    add(tbl["suit_levels"])
    add("    </section>")

    add('    <section id="effects">')
    add("      <h2>各城鎮裝飾滿級效果</h2>")
    add(p_html(
        "上一節套裝表寫的是套裝加成；各件自己的滿級自身屬性與公會屬性在這裡。數值都是表上原值。"
        "聖塔沒有自身屬性，技能見上一節。"
        f"{H('榮耀雕像', terms)}三件、{H(data.decorations[ANNIV_ID].name, terms)}、{H(data.decorations[TREE_ID].name, terms)}也沒有自身屬性列。"
    ))
    jump = []
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        jump.append(f'<a href="#{_suit_anchor(sid)}">{e(suit.name)}</a>')
    jump.append('<a href="#named-only">有名稱但不在套裝成員列</a>')
    jump.append('<a href="#treasure">尋寶藏品</a>')
    jump.append('<a href="#junk">尋寶廢品</a>')
    jump.append('<a href="#nameless-rest">其餘尚無名稱</a>')
    add(f'      <p class="jump-nav">跳至：{" ".join(jump)}</p>')
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        add(f'      <h3 id="{_suit_anchor(sid)}">{e(suit.name)}（套裝 {suit.suit_id}）</h3>')
        if not suit.members:
            add(p_html("此套沒有成員。"))
            continue
        if sid == 3301 and any(i in suit.members for i in (133524, 133525)):
            add(p_html(
                f"此套在 2026-11-05 解壓檔有 15 件成員；現行包於成員列末新增"
                f"{H(data.decorations[133524].name, terms)}（133524）、{H(data.decorations[133525].name, terms)}（133525）。"
            ))
        add(tbl["effects"][sid])
    add('      <h3 id="named-only">有名稱但不在套裝成員列</h3>')
    add(p_html("這 4 件編號出現在「世界之最」另外列出的裝飾編號欄，但不在套裝成員列。"))
    add(tbl["named_only"])
    add('      <h3 id="treasure">尋寶藏品（未列入上述套裝）</h3>')
    add(p_html(
        f"規則字串稱「{official_term_html(o.dig_title)}」。"
        f"完整規則文案（已去色碼）為：「{official_term_html(o.dig_rule_1)}」。"
        "主題 1–4 各 40 件，對應"
        + "、".join(official_term_html(o.theme_names[i]) for i in THEME_IDS)
        + "；品質 3／4／5／6 的件數每主題相同（18／12／8／2）。"
        f"這 {comma(data.table_meta['treasure_count'])} 件同時是城鎮裝飾，升級為 4 級、評分欄為 -1。"
        "收藏裝飾可以擺進主城；規則並寫「獲得重複藏品可升級藏品屬性」。"
    ))
    add(p_html(
        f"尋寶主題里程碑表 {comma(data.table_meta['milestone_rows'])} 筆："
        "各主題在解鎖 1／10／20 件時各給一筆獎勵（46301–46312），這些獎勵編號在這份資料沒有道具名。"
        f"尋寶刷新表 {comma(data.table_meta['refresh_rows'])} 筆，對應各藏品的刷新／投放。檔名見資料說明。"
    ))
    for theme in THEME_IDS:
        add(f'      <h4 id="treasure-{theme}">{e(o.theme_names[theme])}</h4>')
        add(tbl["treasure"][theme])
    add('      <h3 id="junk">尋寶廢品（不在裝飾屬性表）</h3>')
    add(p_html(
        f"另外 {comma(len(data.junk))} 筆類型為 2、主題欄為 -1、品質 2、顯示欄為 -1，"
        "不在城鎮裝飾屬性表。它們沒有藏品名稱，但有道具名稱，"
        "名稱皆帶「（廢品）」。規則文案寫：廢品較為常見，發現後可獲得對應道具，使用後可轉化為資源"
        f"。道具說明亦寫「{official_term_html(o.junk_item_desc)}」。"
        "廢品不是有屬性列的城鎮裝飾。"
    ))
    add(tbl["junk"])
    add('      <h3 id="nameless-rest">其餘尚無名稱、也不在套裝</h3>')
    add(tbl["nameless_rest"])
    listed = (
        sum(len(data.suits[s].members) for s in SUIT_ORDER)
        + len([i for i in NAMED_NOT_IN_MEMBERS if i in data.decorations])
        + sum(1 for d in data.decorations.values() if d.is_treasure)
        + len([i for i in NAMELESS_NOT_IN_SUIT if i in data.decorations])
    )
    # members can overlap? shouldn't. treasure not in suits. Check listed unique
    uniq = set()
    for s in SUIT_ORDER:
        uniq.update(data.suits[s].members)
    uniq.update(NAMED_NOT_IN_MEMBERS)
    uniq.update(d.group_id for d in data.decorations.values() if d.is_treasure)
    uniq.update(NAMELESS_NOT_IN_SUIT)
    add(p_html(
        f"以上屬性表 {comma(len(data.decorations))} 件已全部列出（核對：已列 {comma(len(uniq))}，"
        f"未列 {comma(len(set(data.decorations) - uniq))}）。"
    ))
    add("    </section>")


    add('    <section id="guild">')
    add("      <h2>公會裝飾物</h2>")
    add(p_html(
        f"公會裝飾物 {comma(data.table_meta['alliance_rows'])} 件，"
        f"屬性表 {comma(data.table_meta['alliance_prop_rows'])} 筆（每件 5 級）。檔名見資料說明。"
        "升級同樣靠累積同一件：各級累積個數為 1、2、4、7、11，升到 5 級。"
        "獲得說明寫「重複獲得可用於提升裝飾物等級」（17–19 的用字是「啟動」，其餘多為「啟用」）。"
        f"領地說明寫：「{official_term_html(o.tip_territory)}」。"
        f"另有「{official_term_html(o.tip_guild_cap)}」。"
        "屬性表的領地效果欄全為 -1，本頁不把這個 -1 自行解釋成某種領地效果。"
    ))
    q = Counter(g.quality for g in data.guild)
    add(p_html(
        "17–19 沒有獨立名稱，正式名稱取自獲得說明："
        + "、".join(official_term_html(g.name) for g in data.guild if g.name_from_obtain)
        + f"。品質欄為 3／4／5（品質 3 共 {q.get(3, 0)} 件、品質 4 共 {q.get(4, 0)} 件、品質 5 共 {q.get(5, 0)} 件）。"
        "全部同屬一套公會套裝，表上沒有另一套定義。"
        "賽季欄有 0、3、5、999，部分有解鎖時間，只照錄，不標未開放。欄位名見資料說明。"
        "公會裝飾物各級（非滿級）的中間屬性不展開，下表只列滿級。"
    ))
    add(tbl["guild"])
    add(p_html(
        "公會萬能裝飾物是另外四種道具（"
        + "、".join(f"{official_term_html(name)}（說明「{official_term_html(desc)}」）" for iid, name, desc in o.guild_univ)
        + "）。一般城鎮裝飾的萬能材料（"
        + "、".join(official_term_html(name) for iid, name, _ in o.town_univ)
        + "）與這套不是同一組道具。"
    ))
    add("    </section>")

    add('    <section id="unmatched">')
    add("      <h2>尚無名稱或對不上的城鎮裝飾</h2>")
    nameless = [d for d in data.decorations.values() if d.name_src == "none"]
    add(p_html(
        f"{comma(len(nameless))} 件沒有城鎮裝飾名稱也沒有收藏名稱。其中："
    ))
    add("<ul>")
    add(
        "<li>10023、10024 共用"
        f"{H(data.decorations[SNOWMAN_ID].name, terms)}（{SNOWMAN_ID}）的模型路徑，沒有說明。</li>"
    )
    add(
        "<li>20007 在「稀奇古怪戰利品大集合！」套裝裡，只有建造速度屬性，沒有名稱。</li>"
    )
    add(
        "<li>104401–104404、104501 是「世界的起源」五件成員，沒有名稱也沒有說明。</li>"
    )
    d143 = data.decorations.get(143501)
    add(
        f"<li>143501／143502 是「暮光之戰」套裝成員；143501 說明寫「{e(d143.desc) if d143 else ''}」</li>"
    )
    add(
        "<li>147501–147503、147601–147603 有說明，內容對得上若干角色名，是「馴龍高手」套裝成員，但沒有正式名稱字串。"
        "本頁不以說明裡的角色名當作裝飾物正式名稱。</li>"
    )
    d151 = data.decorations[ID_151601]
    add(
        f"<li>151601 在「永世名將」套裝，說明是「{official_term_html(d151.desc)}」，"
        f"模型路徑卻指向{H(data.decorations[RABBIT_CUP_ID].name, terms)}（{RABBIT_CUP_ID}）。官方用字是「統禦」，不是「統御」。</li>"
    )
    add(
        "<li>155501–155503、155601–155603 是「馴龍高手第二期」六件成員，沒有名稱也沒有說明。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(
        f"<li>英雄造型、領主裝扮、聊天與社交皮膚、行軍造型、村莊風格與建造造型、城堡造型"
        f"（見<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>，不在本頁展開）。</li>"
    )
    add("<li>各裝飾物的取得途徑（禮包、活動、尋寶、商店）沒有完整來源表，本頁沒有逐件對商店，也不編造取得表。</li>")
    add(
        f"<li>城市建築圖鑑表 {comma(data.table_meta['guidebook_rows'])} 筆（編號 1–80），"
        "每筆有等級經驗與一組啟用屬性。"
        "屬性都是冒險相關：冒險攻擊百分比、冒險生命百分比、"
        "增傷（對冒險首領生效）、減傷（對冒險首領生效）、"
        "冒險模式復活時間縮短、冒險模式脫戰每秒回血速度、"
        "冒險模式救援速度增加、冒險模式免費復活次數。"
        "檔名是城市建築圖鑑，表上沒有寫死它就是裝飾物總評分，本頁不自行斷定，也不把這 80 級展開成裝飾物正文。</li>"
    )
    add("<li>套裝等級第 2–9 級的完整中間值（總表只列第 1 級與滿級）。</li>")
    add("<li>公會裝飾物各級（非滿級）的中間屬性。</li>")
    add("</ul>")
    add(p_html(
        "待補（均未決議，本頁不補寫答案）：一般城鎮裝飾與藍紫橙紅萬能裝飾物的顏色對照；"
        "套裝類型欄 1–5 與啟動欄兩數字的含義；"
        "解鎖天數、解鎖賽季與解鎖時間如何卡開（不自行標未開放）；"
        "世界的起源五件、10023／10024、馴龍高手兩期無名稱件、151601 在客戶端實際顯示什麼；"
        "尋寶主題里程碑獎勵 46301–46312、榮耀雕像每日獎勵道具的名稱；各件取得途徑。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<p>以下是整理用註記，查名稱與效果可略過。</p>")
    add(
        "<p>解鎖時間若是兩段日期，可見正文寫成「A 至 B」，原值是 <code>A|B</code>，欄位原名 <code>unlocktime</code> 或時間參數 <code>time_para1</code>。"
        f"{H('紅水晶礦', terms)}每日獎勵可見寫第 1 級 4,000、滿級 15 為 96,000；原值記法是 <code>999|6|{{數值}}</code>（滿級 <code>999|6|96000</code>）。類型 999 與中段 6 沒有官方資源名，不編造。"
        f"{H('繽紛聖誕樹', terms)}每日獎勵可見寫{H('驚喜寶箱', terms)} ×2，原值 <code>2|512110003|2</code>。"
        "其時間參數原值 <code>4519|4474|2144</code>，表上沒有說明這三個數字的含義，可見正文不推算。"
        f"{'、'.join(H(data.decorations[i].name, terms) for i in ELITE_IDS)}"
        " 每日獎勵原值 <code>2|601283006|1</code>、<code>2|601283005|1</code>、<code>2|601283004|1</code>，"
        "字串表沒有對應的官方物品名，可見正文不照錄編號。"
        "套裝「解鎖賽季（只照錄）」的 <code>1|0</code>、<code>2|0</code>、<code>3|0</code>、<code>4|0</code> 只照錄，不換算成賽季日曆。"
        "聖塔技能「參數」欄原值如 <code>1|40</code>、<code>1|90|6|2</code> 保留照錄，文案已代入參數，不另推算含義。可見聖塔一覽不再寫編號與陣營編號欄，改寫官方裝飾物名；編號與陣營編號對照見此。可見公會裝飾物表不再寫編號欄，改寫官方裝飾物名；編號對照見此。可見裝飾物分表與廢品表在該表全列都有官方名時不再寫編號欄，改寫官方名稱；若表內仍有（無名稱）列則保留編號欄。編號對照見此。可見正文改寫「沒有獨立名稱／沒有藏品名稱／沒有正式名稱字串」「說明對照見資料說明」，名稱鍵與說明鍵對照見此。可見表不再列出說明鍵；聯盟／部族／自然聖塔說明鍵原名 <code>citybuilding_DIY_skill_1</code>／<code>_2</code>、<code>citybuilding_DIY_skill_3</code>／<code>_4</code>、<code>citybuilding_DIY_skill_5</code>／<code>_6</code>。城鎮裝飾名稱鍵原名 <code>citybuilding_DIY_name_*</code>，收藏名稱鍵原名 <code>collection_name_*</code>。公會屬性生效人數上限原名 <code>property_alliance_max_num</code>。公會裝飾物「全部同屬一套公會套裝」原欄是 <code>suit_id=1</code>。"
        "戰力／評分欄原名 <code>fight</code>／<code>score</code>；公會共享屬性原名 <code>property_alliance</code>／<code>alliance_attrs</code>。"
        "通用公會共享介面字串原名 <code>citybuilding_diy_allance_content</code>（表上拼寫如此，照錄）；人數上限提示原名 <code>diy_alliance_effect_member_tip</code>。"
        "不能用萬能裝飾物升級的說明原名 <code>citybuilding_diy_lvup</code>。聖塔陣營欄原名 <code>race</code>。"
        "套裝類型欄原名 <code>type</code>，啟動欄原名 <code>Activation</code>。套裝成員列原名 <code>citybuilding_DIY_id</code>。"
        "尋寶藏品／廢品表原名 <code>collection_detail</code>（藏品 <code>type=1</code>、廢品 <code>type=2</code>）。"
        "尋寶規則標題／正文原名 <code>collection_dig_rule_title</code>、<code>collection_dig_rule_desc_1</code>／<code>_2</code>；"
        "主題名原名 <code>collection_dig_desc_1</code>–<code>4</code>。"
        "套裝等級戰力欄原名 <code>power</code>；另兩欄原名 <code>active_season</code>（全為 -1）、<code>property_num_add</code>（全空）。"
        "尋寶里程碑獎勵欄原名 <code>reward</code>；本抽取沒有對應的 <code>goods_name</code>。"
        "廢品主題欄原名 <code>theme</code>，顯示欄原名 <code>is_show</code>。"
        "公會裝飾累積個數原名 <code>total_num</code>；領地說明原名 <code>alliance_bastion_04_014</code>，公會上限提示原名 <code>guild_decoration_tips_1</code>，領地效果欄原名 <code>territory_effect</code>。"
        "公會裝飾名稱鍵原名 <code>alliance_decorations_name1</code>–<code>22</code>；17–19 正式名稱取自 <code>alliance_decorations_item_desc17</code>–<code>19</code>。"
        "城市建築圖鑑各級經驗與啟用屬性原名 <code>level_exp</code>、<code>active_attr</code>。"
        "模型路徑如 <code>Building/Building_DIY/Building_diy_10019</code> 是表上路徑事實。可見（無名稱）10023／10024 寫「模型路徑與雪人（10019）相同」，完整路徑只寫在資料說明，不另解釋檔名。可見屬性表、套裝表與公會裝飾表只寫官方屬性名與原值，不再括編號。城市建築圖鑑冒險相關屬性編號：冒險攻擊百分比 1100103、冒險生命百分比 1100104、增傷（對冒險首領生效）68、減傷（對冒險首領生效）69、冒險模式復活時間縮短 1125、冒險模式脫戰每秒回血速度 1108、冒險模式救援速度增加 1126、冒險模式免費復活次數 1111。</p>"
    )
    add(
        "<p>不依 <code>unlocktime</code>、<code>unlock_season</code>、<code>unlock_days</code>、"
        "<code>season</code> 或伺服器欄位標未開放；表上有這些欄位的，只照錄。"
        "套裝 <code>type=5</code> 的名稱對得上若干賽季稱呼，且帶有 <code>unlock_season</code>，同樣只照錄欄位，"
        "不把官方套裝名稱「雲海紀行」當成已核對的官方賽季名。"
        "升級不消耗資源欄 <code>cost_resource</code>（全表為空），而是累積同一件裝飾物；"
        "介面「多個相同裝飾物可進階獲得更多屬性。」對應 <code>UI_Common_Tips_027</code>。"
        "「雲海紀行」只作為套裝官方名稱，不得寫成已核對的官方賽季名。"
        "功能表 <code>function.json</code> 編號 223 名稱鍵是 <code>ui_shop_name_1001</code>，開啟面板見正文所述商店；"
        "可見升級節不再寫建築 117，條件所指建築編號 117 對照見此。編號 224 的 <code>func_open_param</code> 為 <code>7|117|5</code>（117 是城堡，<code>citybuilding_name_117</code>）。"
        "三座聖塔兩套技能列對應 <code>season</code> 0、<code>type</code> 1 與 <code>season</code> 1、<code>type</code> 2。"
        "<code>citybuilding_DIY_name_*</code> 在 2026-11-05 解壓檔（第 16 章摘錄所用）是 324 鍵；"
        "現行 LocalLow 包鍵數見下表摘錄，包括後來新增的名稱。此差異只記在資料說明，不用來標未開放。定義列欄位名在表上拼成 <code>attibute</code>，引用欄位時照這個拼寫；有等級表時多數等於第 1 級的 <code>attrs</code>。</p>"
    )
    add(p_html(_data_notes(data)))
    add("<ul>")
    add(
        "<li>名錄以 <code>citybuilding_DIY_property.json</code> 的 <code>group_id</code> 為準"
        f"（{comma(data.table_meta['property_rows'])} 筆等級列，{comma(len(data.decorations))} 個裝飾物）。"
        "沒有把後續包才出現的 <code>citybuilding_DIY.json</code> 當成名錄。"
        "名稱優先取 <code>citybuilding_DIY_name_*</code>；若無此鍵，再取 <code>collection_name_*</code>。"
        "屬性名稱優先用 <code>attribute_name_{id}</code>；少數 id 沒有對應鍵時改用 <code>attribute.json</code> 的 <code>name</code> 欄"
        "（例如 21007／21008 的名稱鍵是 <code>attribute_name_20007</code>／<code>20008</code>；"
        "1194 的名稱鍵是 <code>attribute_name_1046</code>）。"
        "<code>show_type=2</code> 的數值只記表內原值。"
        f"不要把 type=1 的「{H(o.alliance_name_3, terms)}／{H(o.alliance_name_4, terms)}」（3／4）"
        f"與 type=2 的「{H(o.hero_atk, terms)}／{H(o.hero_hp, terms)}」（103／104）混成同一欄。</li>"
    )
    for item in data.verifications.get("chapter_diffs") or []:
        add(f"<li>{H(item, terms)}</li>")
    if data.def_only:
        def_txt = "、".join(f"{official_term_html(x.name)}（{x.group_id}）" for x in data.def_only)
        add(
            f"<li>後續包定義表另有不在屬性表的 {def_txt}，本頁不把它們寫成有屬性列的城鎮裝飾。</li>"
        )
    leftover = "、".join(
        f"<code>{e(k)}</code>「{official_term_html(n)}」" + ("（2026-11-05 字串表已有）" if old else "（後續包才出現）")
        for k, n, old in data.leftover_suit_names
    )
    if leftover:
        add(f"<li>沒有對應套裝定義列的套裝名稱鍵：{leftover}。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {DECORATION_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_decoration_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    out: dict[str, str] = {}
    attrs = data.attrs
    src = Counter(d.name_src for d in data.decorations.values())
    treasure_named = sum(1 for d in data.decorations.values() if d.name_src == "collection" and d.is_treasure)
    col_other = sum(1 for d in data.decorations.values() if d.name_src == "collection" and not d.is_treasure)
    out["scope"] = md_table(
        ["組別", "數量", "名稱來源", "常見滿級"],
        [
            ["名稱取自 `citybuilding_DIY_name_*`", comma(src.get("diy", 0)), "城鎮裝飾名稱鍵", "多數 15 級"],
            [
                "名稱取自 `collection_name_*`",
                comma(src.get("collection", 0)),
                f"其中 {treasure_named} 筆同時在 `collection_detail`（世界大尋寶藏品，滿級 4、評分欄 -1）；另外 {col_other} 筆不在該表，而是「永世名將」「王國節日」的套裝成員",
                f"{treasure_named} 件為 4 級；其餘 {col_other} 件為 15 級",
            ],
            ["尚無名稱字串", comma(src.get("none", 0)), "部分有說明，或出現在套裝成員裡", "多數 15 級"],
        ],
    )
    curves = _curve_counts(data)

    def names_for(pred):
        return "、".join(deco_display_name(d) for d in data.decorations.values() if pred(d))

    out["upgrade"] = md_table(
        ["最高等級", "件數", "升滿所需個數", "曲線（各級 `total_num`）"],
        [
            ["15", comma(curves.get(15, 0)), "60", "1、2、4、7、11、15，之後每級再加 5，直到 60"],
            ["4", comma(curves.get(4, 0)), "4", "1、2、3、4（皆為 `collection_detail` 中的尋寶藏品）"],
            ["9", comma(curves.get(9, 0)), "30", "1、2、4、7、11、15、20、25、30，與 15 級曲線的前 9 級相同（聯盟／部族／自然聖塔）"],
            ["3", comma(curves.get(3, 0)), "4", f"1、2、4（{names_for(lambda d: d.max_level == 3)}）"],
            ["2", comma(curves.get(2, 0)), "2", f"1、2（{names_for(lambda d: d.max_level == 2)}）"],
            ["1", comma(curves.get(1, 0)), "1", f"只有 1 級（{names_for(lambda d: d.max_level == 1)}）"],
        ],
    )
    suit_rows = []
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        typ = EMPTY if suit.typ is None else str(suit.typ)
        def_text = _fmt_suit_attrs(suit.def_self, suit.def_alliance, attrs)
        if suit.alliance_max_num != EMPTY:
            def_text = ("" if def_text == EMPTY else def_text + "；") + f"property_alliance_max_num {suit.alliance_max_num}"
        note = suit.def_diff_note if suit.def_differs_from_lv1 else ""
        if sid == 9999:
            note = (note + "；" if note else "") + "此套沒有成員"
        if sid == 57:
            note = (note + "；" if note else "") + "只記官方套裝名稱，不把這個名稱當成已核對的官方賽季名，也不把解鎖賽季欄對成日曆賽季"
        suit_rows.append([
            suit.name or "（無名稱）",
            str(suit.suit_id),
            typ,
            str(suit.member_count),
            _member_text(suit, data),
            def_text,
            suit.unlock_days,
            suit.unlock_season,
            format_timerange(suit.unlocktime),
            note,
        ])
    out["suits"] = md_table(
        ["套裝", "編號", "類型", "件數", "成員", "套裝屬性（定義列／第 1 級，表上有才寫）", "解鎖天數（只照錄）", "解鎖賽季（只照錄）", "解鎖時間（只照錄）", "備註"],
        suit_rows,
    )
    level_rows = []
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        if not suit.levels:
            continue
        lv1, mx = suit.levels[0], suit.levels[-1]
        level_rows.append([
            suit.name,
            str(mx.level),
            fmt_activation(lv1.activation),
            _fmt_suit_attrs(lv1.self_attrs, lv1.alliance_attrs, attrs, lv1.power, True),
            fmt_activation(mx.activation),
            _fmt_suit_attrs(mx.self_attrs, mx.alliance_attrs, attrs, mx.power, True),
        ])
    out["suit_levels"] = md_table(
        ["套裝", "最高等級", "Activation（第 1 級）", "第 1 級", "Activation（滿級）", "滿級"],
        level_rows,
    )

    def deco_md(ids: list[int], with_quality: bool = False) -> str:
        rows = []
        for gid in ids:
            deco = data.decorations[gid]
            note = _deco_note(deco, data)
            row = [
                deco_display_name(deco),
                str(gid),
                str(deco.max_level),
                fmt_attr_pairs(deco.self_attrs, attrs) if deco.self_attrs else EMPTY,
                fmt_attr_pairs(deco.alliance_attrs, attrs) if deco.alliance_attrs else EMPTY,
                comma(deco.fight),
                str(deco.score) if deco.score == -1 else comma(deco.score),
            ]
            if with_quality:
                row.append(str(deco.collection_quality) if deco.collection_quality is not None else EMPTY)
            row.append(note)
            rows.append(row)
        cols = ["名稱", "編號", "滿級", "自身屬性", "公會屬性", "戰力", "評分"]
        if with_quality:
            cols.append("收藏品質")
        cols.append("備註")
        return md_table(cols, rows)

    out["effects"] = {sid: deco_md(data.suits[sid].members) if data.suits[sid].members else "" for sid in SUIT_ORDER}
    out["named_only"] = deco_md([i for i in NAMED_NOT_IN_MEMBERS if i in data.decorations])
    out["treasure"] = {}
    for theme in THEME_IDS:
        ids = [d.group_id for d in sorted(
            (x for x in data.decorations.values() if x.is_treasure and x.collection_theme == theme),
            key=lambda x: x.group_id,
        )]
        out["treasure"][theme] = deco_md(ids, with_quality=True)
    out["nameless_rest"] = deco_md([i for i in NAMELESS_NOT_IN_SUIT if i in data.decorations])
    out["junk"] = md_table(
        ["名稱", "編號", "品質", "備註"],
        [[item.name, str(item.group_id), "2", "不在城鎮裝飾屬性表"] for item in data.junk],
    )

    def skill_md(tower_id: int, season: int) -> str:
        rows = []
        for rec in data.skills_by_tower.get(tower_id, []):
            if rec.season != season:
                continue
            rows.append([str(rec.level), f"`{rec.desc_key}`", rec.params_text, rec.text])
        return md_table(["等級", "說明鍵", "參數", "文案（代入參數、已去色碼）"], rows)

    meta_rows = []
    key_map = {
        308501: ("citybuilding_DIY_skill_1", "citybuilding_DIY_skill_2"),
        308502: ("citybuilding_DIY_skill_3", "citybuilding_DIY_skill_4"),
        308503: ("citybuilding_DIY_skill_5", "citybuilding_DIY_skill_6"),
    }
    race_map = {308501: 1, 308502: 2, 308503: 3}
    for tid in TOWER_IDS:
        k1, k2 = key_map[tid]
        meta_rows.append([
            data.decorations[tid].name,
            str(tid),
            str(race_map[tid]),
            f"`{k1}`／`{k2}`",
            "見下表" if tid == 308501 else "參數與聯盟聖塔相同",
        ])
    out["skill_meta"] = md_table(
        ["裝飾物", "編號", "race", "season 0／type 1 說明鍵", "備註"],
        meta_rows,
    )
    out["skill0"] = skill_md(308501, 0)
    out["skill1"] = skill_md(308501, 1)
    out["guild"] = md_table(
        ["裝飾物", "編號", "品質", "滿級屬性", "賽季欄（只照錄）", "解鎖時間（只照錄）"],
        [
            [
                g.name + ("（名稱取自獲得說明）" if g.name_from_obtain else ""),
                str(g.deco_id),
                str(g.quality),
                fmt_attr_pairs(g.max_attrs, attrs) if g.max_attrs else EMPTY,
                str(g.season) if g.season is not None else EMPTY,
                format_timerange(g.unlocktime),
            ]
            for g in data.guild
        ],
    )
    out["name_only"] = md_table(
        ["名稱", "編號", "來源", "說明"],
        [
            [item.name, str(item.group_id), "後續包新增" if item.later else "第 16 章已列", item.desc or EMPTY]
            for item in data.name_only
        ],
    )
    return out


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    add_lines: list[str] = []
    add = add_lines.append
    add("# Top Heroes Wiki｜裝飾物總表")
    add("")
    add(LEDE)
    add("")
    add(_published_links_md())
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "本頁分開列出兩套系統，不要混為一套：擺在自己主城的城鎮裝飾，"
        "以及擺在公會領地的公會裝飾物。英雄造型、領主裝扮、聊天與社交皮膚、行軍造型是另外的系統，這裡只一筆帶過，不展開。"
        "城堡外觀見[城堡外觀總表](castle.html)，不在本頁展開。"
    )
    add("")
    add("- **正文只根據遊戲資料表。** 表上沒有的標未驗證或待補，不編造公式或名稱。")
    add(
        f"- **名錄以 `citybuilding_DIY_property.json` 的 `group_id` 為準**"
        f"（{comma(data.table_meta['property_rows'])} 筆等級列，{comma(len(data.decorations))} 個裝飾物）。"
        "沒有把後續包才出現的 `citybuilding_DIY.json` 當成名錄。"
    )
    add("- 名稱優先取 `citybuilding_DIY_name_*`；若無此鍵，再取 `collection_name_*`。另有只有名稱、沒有屬性列的編號，見範圍一節。")
    add(
        "- **屬性名稱優先用 `attribute_name_{id}`。** 少數屬性 id 沒有對應的 `attribute_name_{id}` 鍵，"
        "改用 `attribute.json` 的 `name` 欄（例如 21007／21008 的名稱鍵是 `attribute_name_20007`／`20008`；"
        "1194 的名稱鍵是 `attribute_name_1046`）。`show_type=2` 的數值只記表內原值，不自行換算成百分比。"
        "技能說明若已寫成百分比，照錄官方文案，不是由 `show_type` 換算而來。"
    )
    add(
        f"- **不要把 `type=1` 與 `type=2` 的同名屬性混成同一欄：**"
        f"「{o.alliance_name_3}／{o.alliance_name_4}」是 3／4，「{o.hero_atk}／{o.hero_hp}」是 103／104。"
    )
    add(
        "- **不依 `unlocktime`、`unlock_season`、`unlock_days`、`season` 或伺服器欄位標未開放。**"
        "表上有這些欄位的，只照錄。套裝 `type=5` 的名稱對得上若干賽季稱呼，且帶有 `unlock_season`，同樣只照錄欄位，"
        "不把官方套裝名稱「雲海紀行」當成已核對的官方賽季名。"
    )
    add(
        f"- 升級不消耗資源欄 `cost_resource`（全表為空），而是累積同一件裝飾物。介面寫「{o.tip_upgrade}」（`UI_Common_Tips_027`）。"
    )
    add("- 一般城鎮裝飾的主表沒有品質欄。公會裝飾物與世界大尋寶藏品有品質欄，照錄。藍、紫、橙、紅萬能裝飾物與各件如何對色，表上沒有直接欄位，維持待補。")
    add("- 各件只列滿級自身屬性與公會屬性（若有）。除「歡迎光臨」在第 3 級多一條屬性外，其餘有屬性列的裝飾物，屬性種類從第 1 級就固定，只是數值隨等級提高。")
    add("")
    add("## 範圍與資料表")
    add("")
    add(
        f"介面稱{o.attr_src}。功能表 `function.json` 編號 223 的名稱鍵是 `ui_shop_name_1001`，"
        f"字串為「{o.shop_name}」，開啟的是商店面板（`{data.table_meta['fn223_panel']}`）；"
        f"商店另有字串「{o.shop_mall}」（`decoration_shop_1004`）。"
        f"編號 224 開啟個人裝飾面板（`{data.table_meta['fn224_panel']}`），沒有名稱鍵，"
        f"開啟條件欄 `func_open_param` 為 `{data.table_meta['fn224_param']}`"
        f"（117 是{o.castle_name}，見 `citybuilding_name_117`），表上沒有把這串條件寫成說明文字。"
        f"英雄屬性來源把這套寫成「{o.attr_src}」（`hero_attr_dec_citydiy`），"
        f"套裝來源寫「{o.attr_suit_src}」（`hero_attr_dec_citydiysuit`）。"
    )
    add("")
    add(f"{comma(len(data.decorations))} 個有屬性列的裝飾物可分成三組：")
    add("")
    add(tbl["scope"])
    add("")
    chapter_only = "、".join(f"{item.name}（{item.group_id}）" for item in data.name_only if not item.later)
    later_only = "、".join(f"{item.name}（{item.group_id}）" for item in data.name_only if item.later)
    add(
        f"另有 {len([x for x in data.name_only if not x.later])} 個只有名稱、沒有屬性列的編號（第 16 章已列）：{chapter_only}。"
        f"`citybuilding_DIY_name_*` 在 2026-11-05 解壓檔是 324 鍵；現行包是 {comma(data.table_meta['diy_name_keys'])} 鍵，"
        f"包括後來新增的兩件有屬性列名稱，以及另外 {len([x for x in data.name_only if x.later])} 個只有名稱、沒有屬性列的編號：{later_only}。"
    )
    add("")
    add(tbl["name_only"])
    add("")
    add(
        f"篩選表 `citybuilding_diy_filter.json` {comma(data.table_meta['filter_rows'])} 筆，"
        f"分類名稱包括{'、'.join(o.filter_names)}。`type` 為 1 與 2 兩組（分類重複一份），表上沒有類型名稱，本頁不自行解釋。"
    )
    add("")
    add("## 城鎮裝飾：升級")
    add("")
    add("各滿級與升滿所需個數（`total_num` 累計值）：")
    add("")
    add(tbl["upgrade"])
    add("")
    gate_n = sum(1 for d in data.decorations.values() if d.has_gate)
    fights15 = sum(1 for d in data.decorations.values() if d.max_level == 15)
    totems = "、".join(f"{data.decorations[i].name}（{i}）" for i in TOTEM_IDS if i in data.decorations)
    add(
        f"多數 15 級裝飾物從第 6 級起有城堡等級條件（建築 117 是{o.castle_name}）："
        "6–7 級要 40 級城堡，8 級 45，9 級 50，10–13 級 55，14 級 75，15 級 80。"
        f"{comma(len(data.decorations))} 件裡 {comma(gate_n)} 件有這條條件，全部都是 15 級件。"
        f"{comma(fights15)} 件 15 級裝飾物之中，{totems} 沒有這條城堡條件。"
        f"另有 {comma(len(GATE_FROM_14))} 件只在 14–15 級出現這條條件（"
        + "、".join(f"{deco_display_name(data.decorations[i])}（{i}）" for i in GATE_FROM_14)
        + f"），以及 {comma(len(GATE_FROM_10))} 件從第 10 級起才有（"
        + "、".join(f"{deco_display_name(data.decorations[i])}（{i}）" for i in GATE_FROM_10)
        + "）。第 16 章把 15 級條件寫成一律從第 6 級起；上述例外在 2026-11-05 解壓檔已是如此，本頁照表記錄。"
    )
    add("")
    univ = "、".join(f"{name}（道具 {iid}，說明「{desc}」）" for iid, name, desc in o.town_univ)
    add(
        f"有藍、紫、橙、紅四種萬能裝飾物：{univ}。主表沒有品質欄，哪些件能用萬能、什麼顏色對哪一件，表上沒有直接對照。"
        f"另有一句「{o.tip_no_universal}」（`citybuilding_diy_lvup`），沒有列出適用或排除的編號。"
        "公會另有一套同名色的萬能材料（"
        + "、".join(f"{name}（{iid}）" for iid, name, desc in o.guild_univ)
        + "），說明是公會裝飾物專用。"
    )
    add("")

    add("## 戰力、評分、自身與公會屬性")
    add("")
    fights = [d.fight for d in data.decorations.values()]
    scores = sorted(set(d.score for d in data.decorations.values()))
    f15 = [d.fight for d in data.decorations.values() if d.max_level == 15]
    min_deco = min(data.decorations.values(), key=lambda d: (d.fight, d.group_id))
    add(
        f"每級有戰力（`fight`）和評分（`score`）。滿級戰力最低是 {comma(min(fights))}（{deco_display_name(min_deco)}，只有 {min_deco.max_level} 級），"
        f"最高是 {comma(max(fights))}（15 級滿級的上限；15 級件的滿級戰力從 {comma(min(f15))} 到 {comma(max(f15))}）。"
        "滿級評分沒有 0：尋寶藏品 4 級件的評分欄是 -1；其餘滿級評分為 "
        + "、".join(("-1" if s == -1 else comma(s)) for s in scores if s != -1)
        + "。數值都照原值記錄。"
    )
    add("")
    share = [d for d in data.decorations.values() if d.alliance_attrs]
    share_txt = "、".join(f"{deco_display_name(d)}（{d.group_id}）" for d in sorted(share, key=lambda x: x.group_id))
    max_nums = []
    for sid in (23, 37, 51, 56):
        suit = data.suits.get(sid)
        if suit:
            max_nums.append(f"{suit.name}為 {suit.alliance_max_num}")
    add(
        f"{comma(len(share))} 件有公會共享屬性（`property_alliance`／`alliance_attrs`）：{share_txt}。"
        f"通用介面字串是「{o.tip_alliance}」（官方鍵拼寫為 `{o.tip_alliance_key}`）。"
        "部分件或套裝另有不同寫法：例如黑之皇帝／黑之皇后的說明寫「可享受同公會 10 名領主的累加值」；"
        f"介面也有「{o.tip_member}」（`diy_alliance_effect_member_tip`）。"
        "套裝表的 `property_alliance_max_num`：" + "、".join(max_nums)
        + "。這兩套規則如何同時套用，表上沒有合併說明，本頁只並記，不另寫公式。"
    )
    add("")
    add("少數件有時限或每日獎勵，只照錄，不用來標未開放：")
    add("")
    crystal = data.decorations[CRYSTAL_ID]
    add(
        f"- {crystal.name}（{CRYSTAL_ID}）：`time_type` {crystal.time_type}，時間 `{crystal.time_para1}`。"
        "每日獎勵欄為 `999|6|{數值}`，數值隨等級提高：第 1 級 4,000，滿級 15 為 96,000。"
        "類型 999 在 `attribute.json` 與 `attribute_name_*` 都沒有名稱。"
    )
    elites = "、".join(f"{data.decorations[i].name}（{i}）" for i in ELITE_IDS)
    e0 = data.decorations[ELITE_IDS[0]]
    rewards = "、".join(f"`{data.decorations[i].reward}`" for i in ELITE_IDS)
    add(
        f"- {elites}：`time_type` {e0.time_type}，同一段時間；每日獎勵分別為 {rewards}。"
        "這三個道具編號在本抽取沒有 `goods_name`。這三件本身沒有自身屬性列。"
    )
    tree = data.decorations[TREE_ID]
    add(
        f"- {tree.name}（{TREE_ID}）：`time_type` {tree.time_type}，`time_para1` 為 `{tree.time_para1}`"
        f"（表上沒有說明這三個數字的含義）；每日獎勵 `{tree.reward}`（驚喜寶箱 ×2）。本身沒有自身屬性列。"
    )
    add("")
    add("## 戰鬥技能（三座聖塔）")
    add("")
    add(
        f"只有三座聖塔有 `citybuilding_DIY_skill.json` 技能（{comma(len(data.skills))} 筆＝3 × 18）。"
        "聯盟聖塔、部族聖塔、自然聖塔都沒有自身屬性列，效果只見技能表。"
        "各塔有兩套技能列：`season` 0、`type` 1 與 `season` 1、`type` 2，各 9 級（與裝飾物滿級 9 一致）。"
        "這是表上已寫成百分比的技能文案，與屬性欄的原值記錄不同。本頁不把 `season` 對成日曆賽季，也不據此標未開放。"
    )
    add("")
    add(
        "`season` 0 的第 1–5 級用較短文案，第 6–9 級改用較長文案（多了「若己方隊列中有 6 名該陣營英雄，則總共會隨機加持 2 位，且其中一位必定為站位為前排的英雄」）。"
        "`season` 1 全程用較短文案，但人數與百分比的起始值不同。"
    )
    add("")
    add(
        "三座聖塔的人數與百分比參數完全相同，只是文案裡的陣營與 `race`（聯盟 1、部族 2、自然 3）不同。"
        "官方陣營用語是「部族」，不是「部落」，除非官方字串本身就是「部落」（例如裝飾物名稱「部落榮耀」）。"
        "以聯盟聖塔為例（其餘兩座把「聯盟」換成「部族」或「自然」即可）："
    )
    add("")
    add(tbl["skill_meta"])
    add("")
    add("### `season` 0、`type` 1")
    add("")
    add(tbl["skill0"])
    add("")
    add("### `season` 1、`type` 2")
    add("")
    add(tbl["skill1"])
    add("")
    add("部族聖塔對應說明鍵為 `citybuilding_DIY_skill_3`／`_4`，自然聖塔為 `citybuilding_DIY_skill_5`／`_6`，參數與上表相同。")
    add("")
    add("## 城鎮裝飾套裝")
    add("")
    add(
        f"`citybuilding_DIY_suit.json` 共 {comma(len(data.suits))} 套（沒有編號 12、34、36；另有 3301、3302、502、503、9999）。"
        "套裝 `type` 為 1–5，表上沒有類型名稱。`type=5` 的套裝名稱對得上若干賽季稱呼，且帶有 `unlock_season`，本頁只照錄欄位，"
        "不自行對成日曆賽季，也不標未開放，更不把「雲海紀行」寫成已核對的官方賽季名。"
        "`unlock_days` 與 `unlocktime` 同樣只照錄。定義列欄位名在表上拼成 `attibute`，引用欄位時照這個拼寫。"
    )
    add("")
    add(
        "套裝定義列上的屬性（`attibute`／`attrs`）在有等級表時，多數等於第 1 級；例外見備註欄與資料說明，例如永世名將、雲海巡航。"
        f"部分套裝另有 `citybuilding_DIY_suit_property.json`（{comma(data.table_meta['suit_prop_rows'])} 筆）："
        "多數為 10 級，信仰為 9 級，搗蛋鬼、夢幻莊園只有 1 級。各級有 `Activation` 欄，表上沒有說明這兩個數字的含義。"
        "下面總表先寫定義列屬性；有等級表的套裝，第 1 級與滿級另列於其後。中間第 2–9 級不展開。"
        "編號 9999 的「馴龍高手」沒有成員；另有「馴龍高手」（47）與「馴龍高手第二期」（55）兩套有成員。"
    )
    add("")
    diy_named = [d for d in data.decorations.values() if d.name_src == "diy"]
    not_in = [d for d in diy_named if not d.suit_ids]
    not_in_txt = "、".join(f"{d.name}（{d.group_id}）" for d in not_in)
    add(
        f"{comma(len(diy_named))} 件有 `citybuilding_DIY_name_*` 的裝飾物裡，"
        f"{comma(sum(1 for d in diy_named if d.suit_ids))} 件出現在某套套裝成員列；"
        f"不在成員列的 {comma(len(not_in))} 件是{not_in_txt}。"
        "這 4 件編號出現在「世界之最」的 `season_DIY_id` 欄，但不在該套的 `citybuilding_DIY_id` 成員列。"
        f"`collection_detail` 的 {comma(data.table_meta['treasure_count'])} 件尋寶藏品都不進這些套裝；"
        "名稱也取自 `collection_name_*`、但不在 `collection_detail` 的 9 件，則分別在「永世名將」與「王國節日」。"
    )
    add("")
    add(tbl["suits"])
    add("")
    add("### 套裝等級表（有才列）")
    add("")
    add("下表只列第 1 級與最高級。戰力取 `power`。`active_season` 全為 -1，`property_num_add` 全空。")
    add("")
    add(tbl["suit_levels"])
    add("")
    add("## 各城鎮裝飾滿級效果")
    add("")
    add(
        "上一節套裝表寫的是套裝加成；各件自己的滿級自身屬性與公會屬性在這裡。數值都是表上原值。"
        f"聖塔沒有自身屬性，技能見上一節。榮耀雕像三件、{data.decorations[ANNIV_ID].name}、{data.decorations[TREE_ID].name}也沒有自身屬性列。"
    )
    add("")
    for sid in SUIT_ORDER:
        suit = data.suits[sid]
        add(f"### {suit.name}（套裝 {suit.suit_id}）")
        add("")
        if not suit.members:
            add("此套沒有成員。")
            add("")
            continue
        if sid == 3301 and any(i in suit.members for i in (133524, 133525)):
            add(
                f"此套在 2026-11-05 解壓檔有 15 件成員；現行包於成員列末新增"
                f"{data.decorations[133524].name}（133524）、{data.decorations[133525].name}（133525）。"
            )
            add("")
        add(tbl["effects"][sid])
        add("")
    add("### 有名稱但不在套裝成員列")
    add("")
    add("這 4 件編號出現在「世界之最」的 `season_DIY_id` 欄，但不在套裝成員列。")
    add("")
    add(tbl["named_only"])
    add("")
    add("### 尋寶藏品（`collection_detail` type=1，未列入上述套裝）")
    add("")
    add(
        f"規則字串稱「{o.dig_title}」（`collection_dig_rule_title`）。"
        f"完整規則文案（`collection_dig_rule_desc_1`，已去色碼）為：「{o.dig_rule_1}」。"
        "主題 1–4 各 40 件，對應"
        + "、".join(f"{o.theme_names[i]}（`collection_dig_desc_{i}`）" for i in THEME_IDS)
        + "；品質 3／4／5／6 的件數每主題相同（18／12／8／2）。"
        f"這 {comma(data.table_meta['treasure_count'])} 件同時是城鎮裝飾，升級為 4 級、評分欄為 -1。"
        "收藏裝飾可以擺進主城；規則並寫「獲得重複藏品可升級藏品屬性」。"
    )
    add("")
    add(
        f"`collection_theme_milestone.json` {comma(data.table_meta['milestone_rows'])} 筆："
        "各主題在解鎖 1／10／20 件時各給一筆 `reward`（46301–46312），這些獎勵編號在本抽取沒有 `goods_name`。"
        f"`collection_refresh.json` {comma(data.table_meta['refresh_rows'])} 筆，對應各藏品的刷新／投放。"
    )
    add("")
    for theme in THEME_IDS:
        add(f"#### {o.theme_names[theme]}")
        add("")
        add(tbl["treasure"][theme])
        add("")
    add("### 尋寶廢品（`collection_detail` type=2，不在裝飾屬性表）")
    add("")
    add(
        f"另外 {comma(len(data.junk))} 筆 `type=2`、`theme=-1`、品質 2、`is_show=-1`，不在 `citybuilding_DIY_property`。"
        "它們沒有 `collection_name_*`，但有 `goods_name_*`，名稱皆帶「（廢品）」。"
        "規則文案寫：廢品較為常見，發現後可獲得對應道具，使用後可轉化為資源（見 `collection_dig_rule_desc_2`）。"
        f"道具說明亦寫「{o.junk_item_desc}」。廢品不是有屬性列的城鎮裝飾。"
    )
    add("")
    add(tbl["junk"])
    add("")
    add("### 其餘尚無名稱、也不在套裝")
    add("")
    add(tbl["nameless_rest"])
    add("")
    uniq = set()
    for s in SUIT_ORDER:
        uniq.update(data.suits[s].members)
    uniq.update(NAMED_NOT_IN_MEMBERS)
    uniq.update(d.group_id for d in data.decorations.values() if d.is_treasure)
    uniq.update(NAMELESS_NOT_IN_SUIT)
    add(
        f"以上屬性表 {comma(len(data.decorations))} 件已全部列出（核對：已列 {comma(len(uniq))}，未列 {comma(len(set(data.decorations) - uniq))}）。"
    )
    add("")
    add("## 公會裝飾物")
    add("")
    q = Counter(g.quality for g in data.guild)
    add(
        f"`alliance_decorations.json` {comma(data.table_meta['alliance_rows'])} 件，"
        f"`alliance_decorations_property.json` {comma(data.table_meta['alliance_prop_rows'])} 筆（每件 5 級）。"
        "升級同樣靠累積同一件：各級 `total_num` 為 1、2、4、7、11，升到 5 級。"
        "獲得說明寫「重複獲得可用於提升裝飾物等級」（17–19 的用字是「啟動」，其餘多為「啟用」）。"
        f"領地說明寫：「{o.tip_territory}」（`alliance_bastion_04_014`）。"
        f"另有「{o.tip_guild_cap}」（`guild_decoration_tips_1`）。"
        "屬性表的 `territory_effect` 欄全為 -1，本頁不把這個 -1 自行解釋成某種領地效果。"
    )
    add("")
    add(
        "名稱鍵是 `alliance_decorations_name1`–`22`。17–19 沒有名稱鍵，正式名稱取自獲得說明 "
        "`alliance_decorations_item_desc17`–`19`："
        + "、".join(g.name for g in data.guild if g.name_from_obtain)
        + f"。品質欄為 3／4／5（品質 3 共 {q.get(3, 0)} 件、品質 4 共 {q.get(4, 0)} 件、品質 5 共 {q.get(5, 0)} 件）。"
        "全部 `suit_id=1`，表上沒有另一套公會套裝定義。`season` 有 0、3、5、999，部分有 `unlocktime`，只照錄，不標未開放。"
        "公會裝飾物各級（非滿級）的中間屬性不展開，下表只列滿級。"
    )
    add("")
    add(tbl["guild"])
    add("")
    add(
        "公會萬能裝飾物是另外四種道具（"
        + "、".join(f"{name}（{iid}），說明「{desc}」" for iid, name, desc in o.guild_univ)
        + "）。一般城鎮裝飾的萬能材料（"
        + "、".join(str(iid) for iid, _, _ in o.town_univ)
        + "）與這套不是同一組道具。"
    )
    add("")
    add("## 尚無名稱或對不上的城鎮裝飾")
    add("")
    nameless = [d for d in data.decorations.values() if d.name_src == "none"]
    add(f"{comma(len(nameless))} 件沒有 `citybuilding_DIY_name_*` 也沒有 `collection_name_*`。其中：")
    add("")
    add(f"- 10023、10024 共用{data.decorations[SNOWMAN_ID].name}（{SNOWMAN_ID}）的模型路徑，沒有說明。")
    add("- 20007 在「稀奇古怪戰利品大集合！」套裝裡，只有建造速度屬性，沒有名稱。")
    add("- 104401–104404、104501 是「世界的起源」五件成員，沒有名稱也沒有說明。")
    d143 = data.decorations.get(143501)
    add(f"- 143501／143502 是「暮光之戰」套裝成員；143501 說明寫「{d143.desc if d143 else ''}」")
    add("- 147501–147503、147601–147603 有說明，內容對得上若干角色名，是「馴龍高手」套裝成員，但名稱鍵缺失。本頁不以說明裡的角色名當作裝飾物正式名稱。")
    d151 = data.decorations[ID_151601]
    add(
        f"- 151601 在「永世名將」套裝，說明是「{d151.desc}」，模型路徑卻指向{data.decorations[RABBIT_CUP_ID].name}（{RABBIT_CUP_ID}）。官方用字是「統禦」，不是「統御」。"
    )
    add("- 155501–155503、155601–155603 是「馴龍高手第二期」六件成員，沒有名稱也沒有說明。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 英雄造型、領主裝扮、聊天與社交皮膚、行軍造型、村莊風格與建造造型、城堡造型（見[城堡外觀總表](castle.html)，不在本頁展開）。")
    add("- 各裝飾物的取得途徑（禮包、活動、尋寶、商店）沒有完整來源表，本頁沒有逐件對商店，也不編造取得表。")
    add(
        f"- `citybuilding_guidebook.json` {comma(data.table_meta['guidebook_rows'])} 筆（id 1–80），每筆有 `level_exp` 與一組 `active_attr`。"
        "屬性都是冒險相關：冒險攻擊百分比（1100103）、冒險生命百分比（1100104）、增傷（對冒險首領生效）（68）、減傷（對冒險首領生效）（69）、"
        "冒險模式復活時間縮短（1125）、冒險模式脫戰每秒回血速度（1108）、冒險模式救援速度增加（1126）、冒險模式免費復活次數（1111）。"
        "檔名是城市建築圖鑑，表上沒有寫死它就是裝飾物總評分，本頁不自行斷定，也不把這 80 級展開成裝飾物正文。"
    )
    add("- 套裝等級第 2–9 級的完整中間值（總表只列第 1 級與滿級）。")
    add("- 公會裝飾物各級（非滿級）的中間屬性。")
    add("")
    add(
        "待補（均未決議，本頁不補寫答案）：一般城鎮裝飾與藍紫橙紅萬能裝飾物的顏色對照；"
        "套裝 `type` 1–5 與 `Activation` 兩數字的含義；"
        "`unlock_days`／`unlock_season`／`unlocktime` 如何卡開（不自行標未開放）；"
        "世界的起源五件、10023／10024、馴龍高手兩期無名稱件、151601 在客戶端實際顯示什麼；"
        "尋寶主題里程碑獎勵 46301–46312、榮耀雕像每日獎勵道具的名稱；各件取得途徑。"
    )
    add("")
    add("## 資料說明")
    add("")
    add(_data_notes(data))
    add("")
    for item in data.verifications.get("chapter_diffs") or []:
        add(f"- {item}")
    if data.def_only:
        def_txt = "、".join(f"{x.name}（{x.group_id}）" for x in data.def_only)
        add(f"- 後續包定義表另有不在屬性表的 {def_txt}，本頁不把它們寫成有屬性列的城鎮裝飾。")
    leftover = "、".join(
        f"`{k}`「{n}」" + ("（2026-11-05 字串表已有）" if old else "（後續包才出現）")
        for k, n, old in data.leftover_suit_names
    )
    if leftover:
        add(f"- 沒有對應套裝定義列的套裝名稱鍵：{leftover}。")
    add("")
    return "\n".join(add_lines).rstrip() + "\n"
