"""Compile the unpublished 城堡外觀 catalog tables. Public-style HTML; preview script adds the banner."""

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
from .strings import clean, has_key, t
from .tables import load_table


# 城堡外觀總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。本頁頁腳／截止日寫 2026-11-23，
# 因為第 17 章第十版與最後確認的前服面板寫於該日；現行包與 LocalLow 歸檔位元組相同。
CASTLE_DATA_CUTOFF = "2026-11-23"
CASTLE_DATA_PACK = "app-1.129.12_table-1.0.43173"
CASTLE_DATA_PACKED = "2026-11-22 23:33:08–23:33:20"
CHAPTER_EDITION = "第十版"
CHAPTER_DATE = "2026-11-23"

TABLE_SHA256 = {
    "world_skin.json": "ace18ca22ce55857e2b2b5b3f451ea6eb93d4aec8bb5d91bfe593f974f4fde9c",
    "world_skin_effect.json": "97a2fe0e870aa687154083181ab6c59e55a8fe1e10964e30f74f148db19f05f0",
    "world_skin_link.json": "e4c5e2bab7b18b02cd1b7d326cb324fc78bc5e0e45f564bf7c9f44ad57d925e9",
    "world_skin_march.json": "cbb58163623a9a6bd64abe806e8ff9da9183a2620148651dd5259dd6c05c4441",
    "world_skin_wing.json": "04f5e74b5512d81ef87960027a4b48f09127fdcaf7332aab56eb0c675115f96a",
    "world_skin_goods.json": "ce3701c3f8187a061ae3e784e4d45e704269b98359a6b2b37a6af915e8ec0010",
    "world_skin_skill.json": "5161057c4d7513f08d22f55aa6ded8728797f4364d82828623cbdaa72baa476e",
    "world_skin_skill_level_up.json": "4e0fae586e18844129017a71146ddfc6a2c32011c879e844edea835f44afd2d8",
    "world_skin_suit_collection.json": "06017979a0fd71b54c0980a9fc1d31e07e0fe64a49278fd1e45adf96544cc5ba",
    "world_skin_suit_collection_rewa.json": "be8e3916c8d60c5531c0e478d4dfc6d9d97e742d81caf042276033136a3970e1",
    "world_skin_suit_collect_fashion.json": "d47459a8ec91db4d3b8764ae5dfdb6807f5eb160267c0a78e2bd3f0a01004073",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "village_style.json": "1482cf5a2ba63c1980aa62f6c732c500149e7161a888c01f21814c77f918bc80",
    "citybuilding_skin_suit.json": "9d4e7151f94f76bf87996ab06f3f61f530b8d7a399d617267c9277470a4a8e9f",
    "alliance_fort_skin.json": "d72456eae6fd1273225b253c378357eaaee2f3dd7e9b755acf9603e1ef187dc7",
    "activity_skin_send.json": "c05fe3be6f1c4e099554e12f047f9176c46d02479a38199df5ba10667494dbe3",
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
    "world_skin.json",
    "world_skin_effect.json",
    "world_skin_link.json",
    "world_skin_march.json",
    "world_skin_wing.json",
    "world_skin_goods.json",
    "world_skin_skill.json",
    "world_skin_skill_level_up.json",
    "world_skin_suit_collection.json",
    "world_skin_suit_collection_rewa.json",
    "world_skin_suit_collect_fashion.json",
    "attribute.json",
    "village_style.json",
    "citybuilding_skin_suit.json",
    "alliance_fort_skin.json",
    "activity_skin_send.json",
]

LOCKED_STAR_GROUPS = (301, 302, 317, 318)
CURVE_16_ORDER = (
    100, 131, 151, 161, 191, 211, 212, 213, 221, 231, 241, 261, 271, 281, 291,
    304, 305, 307, 308, 309, 310, 312, 316,
)
LEVEL1_ORDER = (
    101, 110, 111, 121, 141, 181, 201, 202, 251, 252, 262, 303, 306, 313, 314,
    315, 319, 320, 321, 322, 323, 324, 325, 326, 328, 329, 330, 331, 332, 333,
    401, 402, 403, 404, 405, 406,
)
DIRECTORY_IDS = (
    1, 100, 101, 111, 121, 131, 141, 151, 161, 171, 181, 191, 201, 202, 211,
    212, 213, 221, 231, 241, 251, 252, 261, 262, 271, 281, 291, 301, 302, 303,
    304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318,
    319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333,
    401, 402, 403, 404, 405, 406,
)
LEFTOVER_SKIN_IDS = (334, 407)

EMPTY = "—"
DASH = "—"

LEDE = (
    "本頁主體是城堡造型（介面欄位「城堡造型」）。"
    "同一套「城堡外觀」介面還有城堡效果、行軍造型、城堡護盾、城堡翅膀、遷城特效與光環造型；"
    "那些相鄰欄位另節登錄，不是城堡造型主體。"
    "正文只根據遊戲資料表與官方字串。不評定造型強弱。"
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
    ("decorations.html", "裝飾物總表"),
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


def is_empty(value) -> bool:
    return value in (None, "", [], {}, -1, "-1")


def fmt(value) -> str:
    if is_empty(value):
        return EMPTY
    try:
        f = float(str(value).strip())
        if f.is_integer():
            return str(int(f))
        return str(value)
    except (TypeError, ValueError):
        return str(value)


def parse_pairs(raw) -> list[tuple[int, int]]:
    if is_empty(raw):
        return []
    if isinstance(raw, list):
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
    out = []
    for chunk in re.split(r"[;,]", text):
        chunk = chunk.strip()
        if not chunk or "|" not in chunk:
            continue
        left, right = chunk.split("|", 1)
        out.append((_int(left), _int(right)))
    return out


def parse_cost(raw) -> list[tuple[int, int, int]]:
    """Return (type, goods_id, qty) triples. Type 2 is an item."""
    if is_empty(raw):
        return []
    if isinstance(raw, list):
        out: list[tuple[int, int, int]] = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 3 and not isinstance(item[0], (list, tuple, str)):
                out.append((_int(item[0]), _int(item[1]), _int(item[2])))
            elif isinstance(item, str) and item.count("|") >= 2:
                a, b, c = item.split("|", 2)
                out.append((_int(a), _int(b), _int(c)))
            else:
                out.extend(parse_cost(item))
        return out
    text = str(raw)
    out = []
    for chunk in re.split(r"[;,]", text):
        chunk = chunk.strip()
        if chunk.count("|") < 2:
            continue
        a, b, c = chunk.split("|", 2)
        out.append((_int(a), _int(b), _int(c)))
    return out


def fmt_cost(raw, style: str = "short") -> str:
    items = parse_cost(raw)
    if not items:
        return "（空）"
    bits = []
    for typ, gid, qty in items:
        if typ == 2:
            if style == "short":
                bits.append(f"道具 {gid} ×{qty}")
            else:
                name = official_text(f"goods_name_{gid}")
                if name:
                    bits.append(f"道具 {gid}（{name}）×{qty}")
                else:
                    bits.append(f"道具 {gid} ×{qty}")
        else:
            bits.append(f"類型 {typ}、編號 {gid} ×{qty}")
    return "加".join(bits)


def format_unlock_range(raw) -> str:
    if is_empty(raw):
        return ""
    text = str(raw)
    if "|" in text and all(part.strip()[:4].isdigit() for part in text.split("|", 1)):
        # date ranges like 2026-08-07 00:00:00|2026-10-01 00:00:00
        a, b = text.split("|", 1)
        if ":" in a and ":" in b:
            return f"{a.strip()} 至 {b.strip()}"
    return text


def fmt_pct_from_raw(val: int) -> str:
    """Present a show_type=2 raw value the same way chapter 17 already locked (4000→40%, 550→5.5%). Not a new conversion rule."""
    pct = val / 100
    if pct == int(pct):
        return f"{int(pct)}%"
    return f"{pct:g}%"


@dataclass
class AttrInfo:
    attr_id: int
    name: str
    typ: int | None
    show_type: int | None
    name_key: str
    name_missing: bool
    name_col: object = None


def _attr_info(aid: int, attr_by: dict[int, dict]) -> AttrInfo:
    row = attr_by.get(aid) or {}
    name_key = f"attribute_name_{aid}"
    name_missing = not has_key(name_key)
    name = official_text(name_key) if not name_missing else ""
    name_col = row.get("name") or row.get("NameKey")
    if name_missing and name_col:
        name = official_text(name_col, name)
        if name_col:
            name_key = str(name_col)
            name_missing = not has_key(name_key)
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
    return "（無名稱）"


def fmt_curve_pair(aid: int, val: int, attrs: dict[int, AttrInfo], compact: bool = False) -> str:
    """Format one own/use pair for the main-table curves, matching chapter 17 presentation."""
    name = attr_label(aid, attrs)
    info = attrs.get(aid)
    show = info.show_type if info else None
    if show == 2:
        body = f"+{fmt_pct_from_raw(val)}（{val}）" if compact else f"{name} +{fmt_pct_from_raw(val)}（原值 {val}）"
        return body
    if compact:
        return f"+{val}"
    return f"{name} +{val}"


def fmt_curve_pairs(pairs: list[tuple[int, int]], attrs: dict[int, AttrInfo], empty: str = "（空）") -> str:
    if not pairs:
        return empty
    return "；".join(fmt_curve_pair(aid, val, attrs) for aid, val in pairs)


def fmt_raw_pairs(pairs: list[tuple[int, int]], empty: str = EMPTY) -> str:
    """Adjacent tables in chapter 17 record raw values only."""
    if not pairs:
        return empty
    return "、".join(f"{aid} {val}" for aid, val in pairs)


@dataclass
class SkinRow:
    sid: int
    group: int
    level: int
    name_key: str
    desc_key: str
    quality: int | None
    quality2: int | None
    hide: int | None
    sex: int | None
    own: list[tuple[int, int]]
    equip: list[tuple[int, int]]
    own_f: list[tuple[int, int]]
    equip_f: list[tuple[int, int]]
    cost: object
    fightforce: object
    territory_range: object
    raw: dict


@dataclass
class SkinGroup:
    group: int
    name: str
    name_key: str
    name_note: str
    rows: list[SkinRow]
    display_id: int


@dataclass
class SkillRow:
    sid: int
    reset_group: int
    skill_group: int
    skill_level: int
    reset_times: int
    name_key: str
    name: str
    desc_key: str
    desc: str


@dataclass
class EffectRow:
    sid: int
    group: int
    typ: int
    level: int
    name_key: str
    name: str
    desc_key: str
    desc: str
    quality: object
    fightforce: object
    own: list[tuple[int, int]]
    equip: list[tuple[int, int]]
    conversion: object
    extra_key: str
    extra: str
    unlocktime: object
    raw: dict


@dataclass
class Official:
    city_skin: dict[int, str]
    city_skin_1_dec: str
    own_label: str
    use_label: str
    cover_tip: str
    prop_sum: str
    halo_tab: str
    halo_own: str
    halo_use: str
    influence: dict[int, str]
    illusion: str
    illusioning: str
    illusion_title: str
    illusion_text: str
    effect_illusion_title: str
    effect_illusion_text: str
    goods: dict[int, tuple[str, str]]
    leftover_334: str
    leftover_407: str
    cangqiong: str
    cangqiong_desc: str
    damage_name: str
    alliance_damage: str
    wing_suit: str
    fashion_point: str


@dataclass
class TablesData:
    official: Official
    attrs: dict[int, AttrInfo]
    groups: dict[int, SkinGroup]
    group_order: list[int]
    rows_by_id: dict[int, SkinRow]
    skills: list[SkillRow]
    skills_by_reset: dict[int, list[SkillRow]]
    effects: list[EffectRow]
    effects_by_type: dict[int, list[EffectRow]]
    links: list[dict]
    marches: list[dict]
    wings: list[dict]
    goods: list[dict]
    suits: list[dict]
    suit_rewards: list[dict]
    fashion: list[dict]
    skill_level_up: list[dict]
    village: list[dict]
    village_suits: list[dict]
    fort: list[dict]
    sendable: list[dict]
    leftover: list[tuple[int, str, str]]
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


def _maybe_int(value):
    if is_empty(value):
        return None
    try:
        return _int(value)
    except (TypeError, ValueError):
        return value


def display_name_for_group(group: int, name_key: str) -> tuple[str, str, str]:
    """Return (display_name, resolved_key, note). Panel-locked names beat a missing skin_name."""
    if group == 320:
        name = official_text("crossover_rss_name1") or "博克島"
        return name, "crossover_rss_name1", "仍缺 skin_name 鍵；面板名稱已確認為博克島"
    if group == 330:
        name = official_text("strangerthings_skin_name_01") or "霍金斯實驗室"
        return name, "strangerthings_skin_name_01", "仍缺 skin_name 鍵；面板名稱已確認為霍金斯實驗室"
    if group == 131:
        name = official_text("skin_name_131") or "黃金獅鷲-戰鬥"
        return name, "skin_name_131", "列上 name 為 skin_name_101；獨立名稱鍵 skin_name_131"
    if group in (110, 111):
        name = official_text("skin_name_111") or "不敗榮耀"
        return name, "skin_name_111", "兩組共用 skin_name_111，沒有 skin_name_112"
    if group in (0, 1):
        name = official_text("skin_name_001") or "城堡"
        return name, "skin_name_001", "預設造型"
    if group == 406:
        name = official_text("skin_name_406") or "蒼穹雲都"
        return name, "skin_name_406", "面板與永久名稱鍵為蒼穹雲都；說明與限時名稱／說明仍作滄穹雲都"
    name = official_text(name_key) if name_key else ""
    return name or f"（{name_key}）", str(name_key or ""), ""


def parse_repeat_diamonds(desc: str) -> str:
    if not desc:
        return EMPTY
    m = re.search(r"轉換為\s*([0-9,]+)\s*鑽石", desc)
    if not m:
        m = re.search(r"轉化為\s*([0-9,]+)\s*鑽石", desc)
    if not m:
        return "說明未寫" if "鑽石" not in desc else EMPTY
    return f"{int(m.group(1).replace(',', ''))} 鑽"


def load_tables_data() -> TablesData:
    global USED_KEYS, MISSING_KEYS
    USED_KEYS = set()
    MISSING_KEYS = set()

    skin_rows = load_table("world_skin.json")
    effect_rows = load_table("world_skin_effect.json")
    link_rows = load_table("world_skin_link.json")
    march_rows = load_table("world_skin_march.json")
    wing_rows = load_table("world_skin_wing.json")
    goods_rows = load_table("world_skin_goods.json")
    skill_rows = load_table("world_skin_skill.json")
    skill_up = load_table("world_skin_skill_level_up.json")
    suit_rows = load_table("world_skin_suit_collection.json")
    rewa_rows = load_table("world_skin_suit_collection_rewa.json")
    fashion_rows = load_table("world_skin_suit_collect_fashion.json")
    attr_rows = load_table("attribute.json")
    village_rows = load_table("village_style.json")
    village_suit_rows = load_table("citybuilding_skin_suit.json")
    fort_rows = load_table("alliance_fort_skin.json")
    send_rows = load_table("activity_skin_send.json")
    attr_by = { _int(r["id"]): r for r in attr_rows }

    parsed_skins: list[SkinRow] = []
    used_aids: set[int] = set()
    for r in skin_rows:
        own = parse_pairs(r.get("attr_own"))
        equip = parse_pairs(r.get("attr_equip"))
        own_f = parse_pairs(r.get("attr_own_f"))
        equip_f = parse_pairs(r.get("attr_equip_f"))
        for pairs in (own, equip, own_f, equip_f):
            used_aids.update(aid for aid, _ in pairs)
        parsed_skins.append(
            SkinRow(
                sid=_int(r["id"]),
                group=_int(r["group"]),
                level=_int(r["level"]),
                name_key=str(r.get("name") or ""),
                desc_key=str(r.get("desc") or ""),
                quality=_maybe_int(r.get("quality")),
                quality2=_maybe_int(r.get("quality2")),
                hide=_maybe_int(r.get("hide")),
                sex=_maybe_int(r.get("sex")),
                own=own,
                equip=equip,
                own_f=own_f,
                equip_f=equip_f,
                cost=r.get("cost"),
                fightforce=r.get("fightforce"),
                territory_range=r.get("territory_range"),
                raw=r,
            )
        )

    grouped: dict[int, list[SkinRow]] = defaultdict(list)
    rows_by_id: dict[int, SkinRow] = {}
    for row in parsed_skins:
        grouped[row.group].append(row)
        rows_by_id[row.sid] = row
    for rows in grouped.values():
        rows.sort(key=lambda x: (x.level, x.sid))

    groups: dict[int, SkinGroup] = {}
    for gid, rows in grouped.items():
        name, key, note = display_name_for_group(gid, rows[0].name_key)
        # directory id: first visible / chapter directory id
        display_id = rows[0].sid
        if gid == 1:
            display_id = 1
        if gid == 110:
            display_id = 111
        if gid == 111:
            display_id = 112
        groups[gid] = SkinGroup(
            group=gid,
            name=name,
            name_key=key,
            name_note=note,
            rows=rows,
            display_id=display_id,
        )

    skills: list[SkillRow] = []
    skills_by_reset: dict[int, list[SkillRow]] = defaultdict(list)
    for r in skill_rows:
        sk = SkillRow(
            sid=_int(r["id"]),
            reset_group=_int(r.get("resetGroup")),
            skill_group=_int(r.get("skill_group")),
            skill_level=_int(r.get("skill_level") or 0),
            reset_times=_int(r.get("resetTimes") or 0),
            name_key=str(r.get("name") or ""),
            name=official_text(r.get("name")),
            desc_key=str(r.get("desc") or ""),
            desc=official_raw(r.get("desc")),
        )
        skills.append(sk)
        skills_by_reset[sk.reset_group].append(sk)
    for rows in skills_by_reset.values():
        rows.sort(key=lambda x: (x.skill_level, x.sid))

    effects: list[EffectRow] = []
    for r in effect_rows:
        typ = _int(r.get("type"))
        own = parse_pairs(r.get("attr_own"))
        equip = parse_pairs(r.get("attr_equip"))
        used_aids.update(aid for aid, _ in own + equip)
        # alliance / extra attrs on auras
        for key in ("property_alliance", "attr_equip_extra"):
            used_aids.update(aid for aid, _ in parse_pairs(r.get(key)))
        extra_key = str(r.get("attr_equip_extra") or "")
        # attr_equip_extra may be a string key or attr pairs; shields use world_shields_buff_desc_*
        extra_text = ""
        if extra_key and "|" not in extra_key and not extra_key[:1].isdigit():
            extra_text = official_raw(extra_key)
        name_key = str(r.get("name") or "")
        desc_key = str(r.get("desc") or "")
        effects.append(
            EffectRow(
                sid=_int(r["id"]),
                group=_int(r.get("skin_effect_group") or r.get("group") or r["id"]),
                typ=typ,
                level=_int(r.get("level") or 1),
                name_key=name_key,
                name=official_text(name_key),
                desc_key=desc_key,
                desc=official_raw(desc_key),
                quality=r.get("quality"),
                fightforce=r.get("fightforce"),
                own=own,
                equip=equip,
                conversion=r.get("conversion_goods"),
                extra_key=extra_key,
                extra=extra_text,
                unlocktime=r.get("unlocktime"),
                raw=r,
            )
        )
    effects_by_type: dict[int, list[EffectRow]] = defaultdict(list)
    for ev in effects:
        effects_by_type[ev.typ].append(ev)
        used_aids.update(aid for aid, _ in ev.own + ev.equip)
    for rows in effects_by_type.values():
        rows.sort(key=lambda x: (x.group, x.level, x.sid))

    for r in list(link_rows) + list(march_rows) + list(wing_rows) + list(rewa_rows):
        for key in ("attr_own", "attr_equip", "property_alliance", "collect_skin_attr"):
            used_aids.update(aid for aid, _ in parse_pairs(r.get(key)))

    attrs = {aid: _attr_info(aid, attr_by) for aid in sorted(used_aids)}
    # ensure frequently cited ids exist even if unused in a pair parse
    for aid in (19, 26, 1019, 1098, 3029, 4031, 5027, 1000104, 1010104, 1142, 10188, 21007, 21008):
        if aid not in attrs and aid in attr_by:
            attrs[aid] = _attr_info(aid, attr_by)

    official = Official(
        city_skin={i: official_text(f"City_Skin_{i}") for i in range(1, 7)},
        city_skin_1_dec=official_text("City_Skin_1_dec"),
        own_label=official_text("UI_CitySkin_001"),
        use_label=official_text("UI_CitySkin_002"),
        cover_tip=official_text("UI_CitySkin_007"),
        prop_sum=official_text("world_skin_prop_sum_title"),
        halo_tab=official_text("world_skin_halo_tab"),
        halo_own=official_text("world_skin_halo_own_prop"),
        halo_use=official_text("world_skin_halo_use_prop"),
        influence={i: official_text(f"influence_level_{i}") for i in (19, 20, 21)},
        illusion=official_text("world_skin_01_01"),
        illusioning=official_text("world_skin_01_03"),
        illusion_title=official_text("info_title_13020"),
        illusion_text=official_raw("info_text_13020"),
        effect_illusion_title=official_text("UI_Title_030"),
        effect_illusion_text=official_raw("info_text_13021"),
        goods={
            gid: (official_text(f"goods_name_{gid}"), official_raw(f"goods_desc_{gid}"))
            for gid in (290, 314, 305, 313)
        },
        leftover_334=official_text("skin_name_334"),
        leftover_407=official_text("skin_name_407"),
        cangqiong=official_text("skin_name_406"),
        cangqiong_desc=official_raw("skin_desc_406"),
        damage_name=official_text("attribute_name_damage"),
        alliance_damage=official_text("attribute_name_3029"),
        wing_suit=official_text("world_skin_wing_suit"),
        fashion_point=official_text("skin_collection_fashion_point"),
    )
    leftover = []
    for sid in LEFTOVER_SKIN_IDS:
        leftover.append((sid, official_text(f"skin_name_{sid}"), official_raw(f"skin_desc_{sid}")))

    # terms: official phrases as wholes, longest first handled by highlight()
    terms: set[str] = {
        official.own_label, official.use_label, official.prop_sum, official.halo_tab,
        official.illusion, official.illusioning, official.illusion_title,
        official.effect_illusion_title, official.damage_name, official.alliance_damage,
        official.cangqiong, "滄穹雲都", official.leftover_334, official.leftover_407,
        official.fashion_point, official.wing_suit,
        "城堡造型", "城堡效果", "行軍造型", "城堡護盾", "城堡翅膀", "遷城特效", "光環造型",
        "建造造型", "城堡造型套裝", "領域效果", "裝備屬性", "共鳴",
        "博克島", "霍金斯實驗室", "黃金獅鷲-戰鬥", "黃金獅鷲", "加倍美味史萊姆",
        "美味史萊姆", "怪奇物語", "創世紀", "永恆紀", "水晶聖城", "蛋糕城", "飛翔號", "飛翔號擁有屬性",
        "夢幻摩天輪", "熾火要塞", "山岳之傲", "天空之城", "洋流環繞", "果香帷幕",
        "逆克制增傷", "聯盟逆克制增傷", "部族逆克制增傷", "自然逆克制增傷",
        "專屬於VIP18的城堡造型", "專屬於VIP20的城堡及光環造型", "專屬於VIP19的行軍造型",
        "防守時我方損兵比例降低", "攻擊時敵方損兵比例增加", "防守時敵方損兵比例增加",
        "守城時士兵生命", "隊伍英雄為同一陣營時，聯盟士兵攻擊額外提升",
        "隊伍英雄為同一陣營時，聯盟士兵生命額外提升",
        "隊伍英雄為同一陣營時，士兵攻擊額外提升",
        "隊伍英雄為同一陣營時，士兵生命額外提升",
        "隊伍英雄為同一陣營時，部族士兵攻擊額外提升",
        "隊伍英雄為同一陣營時，自然士兵攻擊額外提升",
        "普攻減傷", "所有士兵攻擊", "所有士兵生命", "出征上限", "英雄等級上限",
        "時尚值", "感恩大餐", "感恩大餐（高級）", "冰桶", "地心專車",
        "電流閃爍", "頻閃迴響", "兩心同騎", "雪球舞會", "逆界閃遷",
        "鳳焰裂地", "馴龍高手", "春光綻放", "水晶冠冕", "聖輝神翼", "創世聖翼",
        "蘑菇之家", "城堡設計圖", "城堡設計手冊", "城堡進階徽章", "水晶徽章",
        "玩家確認", "社群備註", "部族", "聯盟", "自然", "統禦",
    }
    for g in groups.values():
        if g.name:
            terms.add(g.name)
    for ev in effects:
        if ev.name:
            terms.add(ev.name)
    for info in attrs.values():
        if info.name:
            terms.add(info.name)
    for r in march_rows:
        nm = official_text(r.get("name"))
        if nm:
            terms.add(nm)
    for r in wing_rows:
        nm = official_text(r.get("name"))
        if nm:
            terms.add(nm)
    for r in suit_rows:
        nm = official_text(r.get("name"))
        if nm:
            terms.add(nm)
    for name, _desc in official.goods.values():
        if name:
            terms.add(name)
    term_list = [t for t in terms if t]

    sha_ok = True
    sha_failures = []
    for name, expected in TABLE_SHA256.items():
        path = DATA_DIR / name
        actual = file_sha256(path)
        if actual != expected:
            sha_ok = False
            sha_failures.append(f"{name}: expected {expected}, got {actual}")

    table_meta = {
        "table_count": len(list(DATA_DIR.glob("*.json"))),
        "extract_2026_11_05_table_count": len(list(PACK_DATA_DIRS["2026-11-05"].glob("*.json"))),
        "extract_2026_11_22_table_count": len(list(PACK_DATA_DIRS["2026-11-22"].glob("*.json"))),
        "extract_locallow_table_count": len(list(PACK_DATA_DIRS["2026-11-22-locallow"].glob("*.json"))),
        "skin_rows": len(parsed_skins),
        "skin_groups": len(groups),
        "effect_rows": len(effects),
        "effect_groups": len({ev.group for ev in effects}),
        "effect_type_counts": {typ: len(rows) for typ, rows in effects_by_type.items()},
        "effect_type_groups": {typ: len({ev.group for ev in rows}) for typ, rows in effects_by_type.items()},
        "link_rows": len(link_rows),
        "march_rows": len(march_rows),
        "wing_rows": len(wing_rows),
        "goods_rows": len(goods_rows),
        "skill_rows": len(skills),
        "skill_level_up_rows": len(skill_up),
        "suit_rows": len(suit_rows),
        "reward_rows": len(rewa_rows),
        "fashion_rows": len(fashion_rows),
        "pack_cmp": _compare_table_packs(COMPARE_TABLES),
    }

    group_order = (
        list(LOCKED_STAR_GROUPS)
        + [0, 1, 171, 311, 327]
        + list(CURVE_16_ORDER)
        + list(LEVEL1_ORDER)
    )

    data = TablesData(
        official=official,
        attrs=attrs,
        groups=groups,
        group_order=group_order,
        rows_by_id=rows_by_id,
        skills=skills,
        skills_by_reset=dict(skills_by_reset),
        effects=effects,
        effects_by_type=dict(effects_by_type),
        links=list(link_rows),
        marches=list(march_rows),
        wings=list(wing_rows),
        goods=list(goods_rows),
        suits=list(suit_rows),
        suit_rewards=list(rewa_rows),
        fashion=list(fashion_rows),
        skill_level_up=list(skill_up),
        village=list(village_rows),
        village_suits=list(village_suit_rows),
        fort=list(fort_rows),
        sendable=list(send_rows),
        leftover=leftover,
        terms=term_list,
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


def _verify(data: TablesData) -> dict:
    failures: list[str] = []
    tm = data.table_meta
    if tm["skin_rows"] != 233:
        failures.append(f"world_skin rows {tm['skin_rows']} != 233")
    if tm["skin_groups"] != 68:
        failures.append(f"world_skin groups {tm['skin_groups']} != 68")
    expected_groups = set(LOCKED_STAR_GROUPS) | {0, 1, 171, 311, 327} | set(CURVE_16_ORDER) | set(LEVEL1_ORDER)
    missing_g = expected_groups - set(data.groups)
    extra_g = set(data.groups) - expected_groups
    if missing_g:
        failures.append(f"missing groups {sorted(missing_g)}")
    if extra_g:
        failures.append(f"unexpected groups {sorted(extra_g)}")
    if tm["effect_rows"] != 55:
        failures.append(f"effect rows {tm['effect_rows']} != 55")
    if tm["effect_groups"] != 51:
        failures.append(f"effect groups {tm['effect_groups']} != 51")
    if tm["link_rows"] != 3:
        failures.append(f"link rows {tm['link_rows']} != 3")
    if tm["march_rows"] != 23:
        failures.append(f"march rows {tm['march_rows']} != 23")
    if tm["wing_rows"] != 2:
        failures.append(f"wing rows {tm['wing_rows']} != 2")
    if tm["goods_rows"] != 3:
        failures.append(f"goods rows {tm['goods_rows']} != 3")
    if tm["skill_rows"] != 67:
        failures.append(f"skill rows {tm['skill_rows']} != 67")
    if tm["skill_level_up_rows"] != 10:
        failures.append(f"skill_level_up rows {tm['skill_level_up_rows']} != 10")
    if tm["suit_rows"] != 8:
        failures.append(f"suit rows {tm['suit_rows']} != 8")
    if tm["reward_rows"] != 21:
        failures.append(f"reward rows {tm['reward_rows']} != 21")
    if tm["fashion_rows"] != 15:
        failures.append(f"fashion rows {tm['fashion_rows']} != 15")
    typ = tm["effect_type_counts"]
    if typ.get(1) != 20 or typ.get(2) != 15 or typ.get(3) != 11 or typ.get(4) != 9:
        failures.append(f"effect type counts {typ}")
    # leftover strings must not be table rows
    if any(sid in data.rows_by_id for sid, _, _ in data.leftover):
        failures.append("leftover skin ids unexpectedly present in world_skin")
    if 334 in data.groups or 407 in data.groups:
        failures.append("leftover groups present in world_skin")
    # goods_desc_314 pack vs chapter
    live_314 = data.official.goods[314][1]
    chapter_314_old = "目前可升級城堡：蘑菇之家、黃金獅鬚、藍晶堡、木馬之夢、奇幻舞台"
    # use the actual five-name list from chapter (黃金獅鷲)
    chapter_five = "蘑菇之家、黃金獅鷲、藍晶堡、木馬之夢、奇幻舞台"
    chapter_diffs = []
    if "火砲要塞" in live_314 and chapter_five in live_314:
        chapter_diffs.append(
            "現行 LocalLow 包的 goods_desc_314 名單在五座之外還有火砲要塞；"
            "第 17 章升級材料節與目錄「升級材料（說明名單）」欄仍按較早 StreamingAssets 的五座名單書寫，"
            "且目錄 221 火砲要塞的升級材料寫成 —。主表 group 221 的 cost 在章節與現行包都是道具 314 ×5。"
            "本頁改引現行官方字串，並在目錄標 314。"
        )
    elif "火砲要塞" in live_314:
        chapter_diffs.append(
            "現行 LocalLow 包的 goods_desc_314 含火砲要塞，與第 17 章所引五座名單不同。"
        )
    # lock checks: 301/302/317/318 level 1 and 6 ids
    expect_ids = {
        301: {1: 301, 6: 3012},
        302: {1: 302, 6: 3022},
        317: {1: 317, 6: 3172},
        318: {1: 318, 6: 3182},
    }
    for gid, lvmap in expect_ids.items():
        g = data.groups[gid]
        by_lv = {r.level: r.sid for r in g.rows}
        for lv, sid in lvmap.items():
            if by_lv.get(lv) != sid:
                failures.append(f"group {gid} level {lv} id {by_lv.get(lv)} != {sid}")
    # 蛋糕城 L6 own
    r3016 = next(r for r in data.groups[301].rows if r.level == 6)
    if r3016.own != [(10104, 4000), (1019, 30), (1039, 500)] or r3016.equip != [(10104, 1000), (26, 500)]:
        failures.append("cake level 6 attrs drifted")
    r3026 = next(r for r in data.groups[302].rows if r.level == 6)
    if r3026.own != [(10104, 3000), (1019, 30), (1039, 1000), (21023, 1500), (21024, 3000)]:
        failures.append("flyer level 6 own drifted")
    if official_text("attribute_name_damage") != "逆克制增傷":
        failures.append("attribute_name_damage drifted")
    if official_text("attribute_name_3029") != "聯盟逆克制增傷":
        failures.append("attribute_name_3029 drifted")

    counts = {
        "world_skin_rows": tm["skin_rows"],
        "world_skin_groups": tm["skin_groups"],
        "world_skin_effect_rows": tm["effect_rows"],
        "world_skin_effect_groups": tm["effect_groups"],
        "type1": typ.get(1),
        "type2": typ.get(2),
        "type3": typ.get(3),
        "type4": typ.get(4),
        "link": tm["link_rows"],
        "march": tm["march_rows"],
        "wing": tm["wing_rows"],
        "goods": tm["goods_rows"],
        "skill": tm["skill_rows"],
        "skill_level_up": tm["skill_level_up_rows"],
        "suit": tm["suit_rows"],
        "reward": tm["reward_rows"],
        "fashion": tm["fashion_rows"],
    }
    return {
        "passed": not failures,
        "failures": failures,
        "counts": counts,
        "chapter_diffs": chapter_diffs,
    }

def _published_links_html(terms: list[str]) -> str:
    links = "、".join(f'<a href="{href}">{H(label, terms)}</a>' for href, label in PUBLISHED_LINKS)
    return (
        f"已發佈的{links}是其他系統。"
    )


def _published_links_md() -> str:
    links = "、".join(f"[{label}]({href})" for href, label in PUBLISHED_LINKS)
    return (
        f"交叉引用：{links}。"
    )


def _ids_list(rows: list[SkinRow], html: bool = False) -> str:
    bits = []
    last = rows[-1].sid if rows else None
    multi = len(rows) > 1
    for r in rows:
        if multi and r.sid == last:
            bits.append(f"<strong>{r.sid}</strong>" if html else f"**{r.sid}**")
        else:
            bits.append(str(r.sid))
    return "、".join(bits)


def _quality_sentence(rows: list[SkinRow]) -> str:
    if not rows:
        return ""
    qset = {(r.quality, r.quality2) for r in rows}
    if len(qset) == 1:
        q, q2 = next(iter(qset))
        if q == q2:
            return f"品質皆為 {q}。"
        return f"品質為 {q}、第二品質為 {q2}。"
    # split by last level vs earlier
    earlier = rows[:-1]
    last = rows[-1]
    eq = {(r.quality, r.quality2) for r in earlier}
    if len(eq) == 1:
        q, q2 = next(iter(eq))
        if last.quality == last.quality2:
            if q == q2:
                return (
                    f"品質在表上等級 1–{earlier[-1].level} 為 {q}，"
                    f"等級 {last.level} 為 {last.quality}。"
                )
        if q == q2 and last.quality != last.quality2:
            return (
                f"品質在表上等級 1–{earlier[-1].level} 為 {q}，"
                f"等級 {last.level} 為品質 {last.quality}、第二品質 {last.quality2}。"
            )
        if q == q2:
            return (
                f"品質在表上等級 1–{earlier[-1].level} 為 {q}，"
                f"等級 {last.level} 為 {last.quality}。"
            )
    return "各列品質照表。"


def _cost_sentence(rows: list[SkinRow]) -> str:
    if all(is_empty(r.cost) for r in rows):
        return "各列都沒有升級消耗。"
    first, rest = rows[0], rows[1:]
    if is_empty(first.cost) and rest and all(str(r.cost) == str(rest[0].cost) for r in rest):
        return f"表上等級 {first.level} 沒有升級消耗，等級 {rest[0].level}–{rest[-1].level} 為{fmt_cost(rest[0].cost)}。"
    # maybe two cost bands (創世紀)
    bands: list[tuple[str, list[int]]] = []
    for r in rows:
        key = "（空）" if is_empty(r.cost) else fmt_cost(r.cost)
        if bands and bands[-1][0] == key:
            bands[-1][1].append(r.level)
        else:
            bands.append((key, [r.level]))
    bits = []
    for key, lvs in bands:
        if len(lvs) == 1:
            bits.append(f"表上等級 {lvs[0]} 為{key if key != '（空）' else '空'}")
        else:
            bits.append(f"表上等級 {lvs[0]}–{lvs[-1]} 為{key if key != '（空）' else '空'}")
    return "，".join(bits) + "。"


def _use_constant(rows: list[SkinRow]) -> bool:
    if not rows:
        return True
    first = rows[0].equip
    return all(r.equip == first for r in rows)


def _own_constant(rows: list[SkinRow]) -> bool:
    if not rows:
        return True
    first = rows[0].own
    return all(r.own == first for r in rows)


GROUP_EXTRA = {
    131: (
        "名稱列與「黃金獅鷲」共用，說明則獨立；"
        "官方顯示名為「黃金獅鷲-戰鬥」。目錄已鎖定：這是獨立造型，不是「黃金獅鷲」的升級形態。"
        "314 說明可升級的是「黃金獅鷲」，升級後是 Lv.2，不是變成這一座。"
    ),
    211: "滿星為 1 顆金星。面板擁有／使用見介面實例；本節只抄表，不把表上等級寫成面板星數。",
    212: "滿星為 1 顆金星；本抽取無技能列，畫面亦無技能按鈕。面板擁有／使用見介面實例；本節只抄表，不把表上等級寫成面板星數。",
    231: (
        "滿星為 1 顆金星。面板擁有／使用與技能 Lv 10 見介面實例；"
        "本節只抄表，不把表上等級寫成面板星數。使用欄「守城時士兵生命」的編號對照見資料說明。"
    ),
    312: (
        "滿星就是 1 星；"
        "沒有可停的 1/5–4/5 中間檔，一次升級就滿一顆星；VIP18 先拿到此座、再用 313 升成 VIP20 形態；"
        "目前只見這座有「幻化」按鈕。"
        "擁有屬性在六階都是空的。面板的 0 星／滿 1 星使用屬性、取消幻化後主頁空欄、隱藏使用屬性，見介面實例。"
        "本節只抄表，不把表上等級 1／6 寫成 0 星／滿 1 星，也不把中間檔寫成可停的星級檔。內部欄見資料說明。"
    ),
}

DIRECTORY_NOTES = {
    1: "預設造型",
    100: "說明亦稱蘑菇之家",
    101: "另有 7 天、14 天名稱鍵；升級後為 Lv.2，不是 131",
    111: "",
    131: "獨立造型，不是 101 的升級形態",
    201: "與 202 為獨立造型",
    202: "與 201 為獨立造型；禮包文案提士兵生命與帶兵上限（無數值）",
    211: "滿星為 1 顆金星；擁有／使用屬性見介面實例（截圖抄錄，滿星）。滿星顆數不是通用規則",
    212: "滿星為 1 顆金星；本抽取無技能列，畫面亦無技能按鈕；英雄等級來源表以這座為英雄等級上限來源。禮包文案提士兵攻擊和生命，並提升英雄等級上限；擁有／使用屬性見介面實例",
    221: "可作為贈送造型（品質 5）。現行道具說明已把火砲要塞列入可升級名單，主表 2–6 級消耗為對應升級道具×5；第 17 章目錄此欄仍寫 —，見資料說明",
    231: "滿星為 1 顆金星；擁有／使用屬性與技能 Lv 10 見介面實例",
    251: "與 252 為獨立造型",
    252: "與 251 為獨立造型；禮包文案提士兵生命與帶兵上限（無數值）",
    262: "套裝「不可思議之日」成員",
    301: "可作為贈送造型（品質 5）；任務字串有 -Lv.2；升級用道具 290，主表等級 2–6 消耗亦為 290×20，但道具說明名單尚未列這座。面板上：滿星 1 星、永久，畫面無技能按鈕，與表相符。擁有／使用曲線見主表；滿 1 星對表等級 6",
    302: "任務字串有 -Lv.2；升級用道具 290，主表等級 2–6 消耗亦為 290×20，但道具說明名單尚未列這座。面板上：滿星 1 星、永久，畫面無技能按鈕，與表相符。擁有／使用曲線見主表；滿 1 星對表等級 6",
    304: "說明可升級，本抽取無技能",
    305: "與 306 為獨立造型",
    306: "與 305 為獨立造型",
    308: "另有 7／14／30 天限時 id 412–414；可贈送（品質 5）",
    309: "另有 1／3／7 天名稱鍵；可生成「感恩大餐」",
    311: "滿星為 2 顆金星；技能／領域的 1 顆星與 2 顆星檔，見技能章與介面實例",
    312: "說明未寫重複轉換；升級材料說明寫來自 VIP20 專屬禮包。VIP18 先拿到此座，再用 313 升成 VIP20 形態；表上屬性仍寫「專屬於VIP18的城堡造型」。滿星為 1 星。目前只見這座有「幻化」按鈕。屬性見介面實例",
    315: "可作為贈送造型（品質 4）",
    316: "套裝「春意盎然」成員",
    317: "強化名稱為「加倍美味史萊姆」；任務字串有 -Lv.2；升級用道具 290，主表等級 2–6 消耗亦為 290×20，但道具說明名單尚未列這座；另有 3／7／15／30 天名稱鍵。面板上：滿星 1 星、永久，畫面有技能按鈕；滿 1 星對表等級 6，見主表與技能章",
    318: "技能表有強化列；升級用道具 290，主表等級 2–6 消耗亦為 290×20，但道具說明名單尚未列這座。面板上：滿星 1 星、永久，畫面有技能按鈕；滿 1 星對表等級 6，見主表與技能章",
    320: "表上沒有獨立名稱鍵，名稱取自說明；活動資源名與畫面亦作「博克島」；套裝「馴龍高手I」成員",
    323: "套裝「揚帆啟航」成員",
    327: "名稱下無星；目前滿星就是 0 星；主表有這座 1–11 級列，不能把表上等級當成目前可升的星數；共鳴等級 2／3 目前因此開不到，見機制與介面實例",
    330: "表上沒有獨立名稱鍵，名稱取自說明；畫面亦作「霍金斯實驗室」；套裝「怪奇物語」成員",
    331: "套裝「神火鳳凰」成員",
    332: "套裝「馴龍高手II」成員",
    406: "畫面用字為「蒼穹雲都」，與永久名稱一致；說明與全部限時名稱／說明作「滄穹雲都」；另有 3／7／14／30 天名稱鍵",
}

LIMITED_NOTE_IDS = {101, 309, 317, 401, 402, 403, 404, 405, 406, 322}


def _goods_upgrade_map(official: Official) -> dict[int, str]:
    """Map directory id -> official goods list label (290/314/305/313)."""
    mapping: dict[int, str] = {}
    # parse names mentioned in official desc; then map to directory ids via known names
    name_to_code = {
        "山岳之傲": "290", "奪魄聖殿": "290", "巨蟹沙城": "290", "協奏": "290",
        "熾火要塞": "290", "盾貝城": "290", "鋼鐵元帥": "290", "混亂之塔": "290",
        "南瓜小鎮": "290", "幸運火雞": "290",
        "蘑菇之家": "314", "黃金獅鷲": "314", "藍晶堡": "314", "木馬之夢": "314",
        "奇幻舞台": "314", "火砲要塞": "314",
        "創世紀": "305 升星", "天空之城": "305 升星",
        "水晶聖城": "313",
    }
    # only assign if the official text actually names them
    texts = {290: official.goods[290][1], 314: official.goods[314][1], 305: official.goods[305][1], 313: official.goods[313][1]}
    name_to_id = {
        "山岳之傲": 231, "奪魄聖殿": 213, "巨蟹沙城": 304, "協奏": 307, "熾火要塞": 211,
        "盾貝城": 241, "鋼鐵元帥": 310, "混亂之塔": 271, "南瓜小鎮": 308, "幸運火雞": 309,
        "蘑菇之家": 100, "黃金獅鷲": 101, "藍晶堡": 151, "木馬之夢": 161, "奇幻舞台": 305,
        "火砲要塞": 221, "創世紀": 311, "天空之城": 212, "水晶聖城": 312,
    }
    for gid, text in texts.items():
        for name, sid in name_to_id.items():
            if name in text:
                mapping[sid] = name_to_code[name]
    return mapping


def _skill_dir_label(sid: int, data: TablesData) -> str:
    if sid in (304, 308, 212):
        return EMPTY
    if sid == 311:
        return "三筆技能"
    if sid == 317:
        return "贈禮＋自領"
    if sid == 309:
        return "基礎＋強化（生成物）"
    if sid == 322:
        return "生成冰桶"
    rows = data.skills_by_reset.get(sid) or []
    if not rows:
        return EMPTY
    levels = [r.skill_level for r in rows]
    has_lv2 = any("lv2" in (r.desc_key or "") or "_lv2" in (r.desc_key or "") for r in rows)
    if max(levels) >= 10:
        return "1–10"
    if has_lv2 or len(rows) > 1:
        return "基礎＋強化"
    return "基礎"


def _footer_text(data: TablesData) -> str:
    tm = data.table_meta
    cmp_ = tm["pack_cmp"]

    def pack_note(name: str, label: str) -> str:
        rec = cmp_[name]
        live_present = rec["present"].get("live")
        if not live_present:
            return f"`{name}`（{label}）現行包沒有此表。"
        rows = rec["rows"]["live"]
        sha = rec["sha256"]["live"]
        raw_bytes = rec["bytes"]["live"]
        same_bits = []
        for p, label_p in (
            ("2026-11-22-locallow", "2026-11-22 LocalLow"),
            ("2026-11-22", "2026-11-22 StreamingAssets"),
            ("2026-11-05", "2026-11-05 解壓檔"),
        ):
            if not rec["present"].get(p):
                same_bits.append(f"{label_p}沒有此表")
            elif rec["identical"].get(p):
                same_bits.append(f"與{label_p}位元組相同")
            else:
                same_bits.append(
                    f"{label_p}為 {rec['rows'][p]} 筆、{rec['bytes'][p]} bytes，sha256 {rec['sha256'][p]}"
                )
        return (
            f"`{name}`（{label}）{rows} 筆、{raw_bytes} bytes，sha256 {sha}；"
            + "；".join(same_bits)
            + "。"
        )

    extra = ""
    diffs = data.verifications.get("chapter_diffs") or []
    if diffs:
        extra = "與第 17 章不一致的項目：" + " ".join(diffs)
    return (
        f"資料截至 {CASTLE_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {CASTLE_DATA_PACK}（{tm['table_count']} 張表），"
        f"打包時戳 {CASTLE_DATA_PACKED}（香港時間）。"
        f"第 17 章{CHAPTER_EDITION}寫於 {CHAPTER_DATE}（香港時間），同樣以這份 LocalLow 包為準；"
        f"稍早同一日的 StreamingAssets 抽取是 {tm['extract_2026_11_22_table_count']} 張表，沒有城堡造型主表與四張附屬主表。"
        + pack_note("world_skin.json", "城堡造型主表，233 列、68 組")
        + pack_note("world_skin_effect.json", "效果／護盾／遷城／光環")
        + pack_note("world_skin_link.json", "共鳴")
        + pack_note("world_skin_march.json", "行軍造型")
        + pack_note("world_skin_wing.json", "城堡翅膀")
        + pack_note("world_skin_goods.json", "技能生成採集物，不是升級材料表")
        + pack_note("world_skin_skill.json", "城堡技能")
        + pack_note("world_skin_skill_level_up.json", "技能 1–10 級消耗")
        + pack_note("world_skin_suit_collection.json", "城堡造型套裝")
        + pack_note("world_skin_suit_collection_rewa.json", "套裝件數獎勵")
        + pack_note("world_skin_suit_collect_fashion.json", "時尚值獎勵")
        + extra
    )


def li_html(body: str) -> str:
    return f"<li>{body}</li>"


def _curve_table(rows: list[SkinRow], attrs: dict[int, AttrInfo], mode: str = "auto"):
    """Build (columns, rows, mobile) for a main-table group."""
    if not rows:
        return None
    use_same = _use_constant(rows)
    own_same = _own_constant(rows)
    # collect own attr ids in first-seen order (union)
    own_ids: list[int] = []
    for r in rows:
        for aid, _ in r.own:
            if aid not in own_ids:
                own_ids.append(aid)
    use_ids: list[int] = []
    for r in rows:
        for aid, _ in r.equip:
            if aid not in use_ids:
                use_ids.append(aid)
    def cell(pairs, aid):
        found = [v for a, v in pairs if a == aid]
        if not found:
            return EMPTY
        return fmt_curve_pair(aid, found[0], attrs, compact=True)

    if own_same and use_same:
        cols = ["表上等級", "擁有屬性", "使用屬性"]
        body = [[
            str(r.level),
            fmt_curve_pairs(r.own, attrs) if r.own else "（空）",
            fmt_curve_pairs(r.equip, attrs) if r.equip else "（空）",
        ] for r in rows]
        return cols, body, "sticky"
    if use_same and own_ids:
        cols = ["表上等級"] + [f"擁有：{attr_label(aid, attrs)}" for aid in own_ids]
        body = []
        for r in rows:
            body.append([str(r.level)] + [cell(r.own, aid) for aid in own_ids])
        return cols, body, "sticky"
    # both vary, or use not constant
    if own_ids or use_ids:
        cols = ["表上等級", "擁有屬性", "使用屬性"]
        body = []
        for r in rows:
            body.append([
                str(r.level),
                fmt_curve_pairs(r.own, attrs),
                fmt_curve_pairs(r.equip, attrs),
            ])
        return cols, body, "cards"
    cols = ["表上等級", "擁有屬性", "使用屬性"]
    body = [[str(r.level), "（空）", "（空）"] for r in rows]
    return cols, body, "sticky"


def _group_heading(g: SkinGroup) -> str:
    return g.name


def _standard_group_prose(g: SkinGroup, html: bool, attrs: dict[int, AttrInfo], terms: list[str]) -> str:
    rows = g.rows
    n = len(rows)
    levels = [r.level for r in rows]
    lv_txt = f"{levels[0]}–{levels[-1]}" if len(set(levels)) > 1 else str(levels[0])
    head = (
        f"{'十二' if n==11 else '十一' if n==11 else '六' if n==6 else '五' if n==5 else '三' if n==3 else n}列，"
        if n != 11 else "十一列，"
    )
    if n == 11:
        head = "十一列，"
    elif n == 6:
        head = "六列，"
    elif n == 5:
        head = "五列，"
    elif n == 3:
        head = "三列，"
    elif n == 1:
        head = "一列，"
    else:
        head = f"{n}列，"
    text = (
        f"{head}表上等級 {lv_txt}；編號依序為 {_ids_list(rows, html=html)}。"
        f"{_quality_sentence(rows)}"
        f"{_cost_sentence(rows)}"
    )
    extra = GROUP_EXTRA.get(g.group, "")
    if g.group not in (301, 302, 317, 318, 311, 327, 0, 1, 171, 312) and g.group in CURVE_16_ORDER and not extra:
        text += "本節只抄表上 level 與擁有／使用屬性，不是已用面板核過 0 星或滿星。"
    elif extra and g.group in CURVE_16_ORDER and g.group not in (211, 212, 231, 312, 131):
        text += extra + "本節只抄表上 level 與擁有／使用屬性，不是已用面板核過 0 星或滿星。"
    elif extra:
        text += extra
    elif g.group in CURVE_16_ORDER:
        text += "本節只抄表上 level 與擁有／使用屬性，不是已用面板核過 0 星或滿星。"
    return text


def _use_prose(rows: list[SkinRow], attrs: dict[int, AttrInfo]) -> str:
    if not _use_constant(rows):
        return ""
    body = fmt_curve_pairs(rows[0].equip, attrs)
    return f"使用屬性（各階皆同）：{body}。"


def _own_prose(rows: list[SkinRow], attrs: dict[int, AttrInfo]) -> str:
    if not _own_constant(rows):
        return ""
    body = fmt_curve_pairs(rows[0].own, attrs)
    return f"擁有屬性（各階皆同）：{body}。"


def _tbl(cols, rows, mobile, caption=None, card_title=None):
    kwargs = {"mobile": mobile}
    if caption:
        kwargs["caption"] = caption
    if mobile == "cards":
        kwargs["card_title"] = card_title or cols[0]
        # prefer 名稱 / 套裝 if present
        for cand in ("名稱", "套裝", "造型", "城堡造型"):
            if cand in cols:
                kwargs["card_title"] = cand
                break
    return table(cols, rows, **kwargs)


def _md(cols, rows):
    return md_table(cols, [[str(c) for c in row] for row in rows])


# 已確認面板原文（第 17 章，去標籤後須一致）
PANEL_CAKE_FULL = (
    "當時為滿星 1 星、永久；畫面沒有技能按鈕，與技能表相符。"
    "擁有屬性為所有士兵生命 +40%、出征上限 +30、防守時我方損兵比例降低 +5%；"
    "使用屬性為所有士兵生命 +10%、普攻減傷 +5%。"
    "這組數字與表上等級 6 一致。不是等級 1。原值對照見資料說明。"
)
PANEL_CAKE_ZERO = (
    "擁有屬性為所有士兵生命 +20%、出征上限 +20、防守時我方損兵比例降低 +5%；"
    "使用屬性與滿 1 星相同，為所有士兵生命 +10%、普攻減傷 +5%"
    "（使用屬性在表上等級 1 與 6 相同）。"
    "對應表上等級 1。原值對照見資料說明。"
)
PANEL_FLY_FULL = (
    "當時為滿星 1 星、永久；畫面沒有技能按鈕，與技能表相符。"
    "飛翔號擁有屬性因畫面溢出分在連續幾張裡，合在一起是：所有士兵生命 +30%、出征上限 +30、"
    "防守時我方損兵比例降低 +10%、隊伍英雄為同一陣營時聯盟士兵攻擊額外提升 +15%、"
    "隊伍英雄為同一陣營時聯盟士兵生命額外提升 +30%；"
    "使用屬性為所有士兵生命 +10%、普攻減傷 +5%。"
    "這組數字與表上等級 6 一致。不是等級 1。原值對照見資料說明。"
)
PANEL_FLY_ZERO = (
    "擁有屬性為所有士兵生命 +20%、出征上限 +20、防守時我方損兵比例降低 +5%、"
    "隊伍英雄為同一陣營時聯盟士兵攻擊額外提升 +10%、隊伍英雄為同一陣營時聯盟士兵生命額外提升 +20%；"
    "使用屬性與滿 1 星相同，為所有士兵生命 +10%、普攻減傷 +5%"
    "（使用屬性在表上等級 1 與 6 相同）。"
    "對應表上等級 1。原值對照見資料說明。"
)
PANEL_SLIME_FULL = (
    "當時為滿星 1 星、永久；畫面有技能按鈕，與技能表相符。"
    "擁有屬性為所有士兵攻擊 +10%、所有士兵生命 +25%、出征上限 +10；"
    "使用屬性為所有士兵攻擊 +2%、所有士兵生命 +3%。"
    "這組數字與表上等級 6 一致。技能見「城堡技能」。原值對照見資料說明。"
)
PANEL_SLIME_ZERO = (
    "擁有屬性為所有士兵攻擊 +5%、所有士兵生命 +15%；"
    "使用屬性與滿 1 星相同，為所有士兵攻擊 +2%、所有士兵生命 +3%"
    "（使用屬性在表上等級 1 與 6 相同）。"
    "對應表上等級 1（品質 5）。原值對照見資料說明。"
)
PANEL_WHEEL_FULL = (
    "當時為滿星 1 星、永久；畫面有技能按鈕，與技能表相符。"
    "擁有屬性為所有士兵生命 +40%、出征上限 +30；"
    "使用屬性是「減傷 +5%」和所有士兵攻擊 +5%。"
    "這裡的減傷與蛋糕城、飛翔號使用欄的普攻減傷不是同一條，分開記。"
    "這組數字與表上等級 6 一致。技能見「城堡技能」。原值對照見資料說明。"
)
PANEL_WHEEL_ZERO = (
    "擁有屬性為所有士兵生命 +20%、出征上限 +20；"
    "使用屬性與滿 1 星相同，為減傷 +5%、所有士兵攻擊 +5%"
    "（使用屬性在表上等級 1 與 6 相同；減傷仍不是普攻減傷）。"
    "對應表上等級 1（品質 5）。原值對照見資料說明。"
)


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    attrs = data.attrs
    title = "Top Heroes Wiki｜城堡外觀總表"
    summary = (
        "本頁主體是城堡造型（介面欄位「城堡造型」）。同一套城堡外觀介面的效果、行軍、護盾、翅膀、遷城與光環另節登錄。"
    )
    toc_items = [
        {"id": "lead", "label": "閱讀說明"},
        {"id": "scope", "label": "範圍與資料缺口"},
        {"id": "mechanics", "label": "系統機制"},
        {"id": "directory", "label": "城堡造型目錄"},
        {"id": "main", "label": "城堡造型主表"},
        {"id": "g-301", "label": "蛋糕城", "depth": 1},
        {"id": "g-302", "label": "飛翔號", "depth": 1},
        {"id": "g-317", "label": "美味史萊姆", "depth": 1},
        {"id": "g-318", "label": "夢幻摩天輪", "depth": 1},
        {"id": "g-default", "label": "預設城堡", "depth": 1},
        {"id": "g-171", "label": "賢者之城", "depth": 1},
        {"id": "g-311", "label": "創世紀", "depth": 1},
        {"id": "g-327", "label": "永恆紀", "depth": 1},
        {"id": "g-16", "label": "表上有多檔的其他城堡", "depth": 1},
        {"id": "g-1only", "label": "表上只有一檔的城堡", "depth": 1},
        {"id": "upgrade", "label": "升級與升星材料"},
        {"id": "skills", "label": "城堡技能"},
        {"id": "suits", "label": "城堡造型套裝"},
        {"id": "territory", "label": "領域效果"},
        {"id": "resonance", "label": "共鳴"},
        {"id": "effects", "label": "城堡效果／特效"},
        {"id": "shields", "label": "城堡護盾"},
        {"id": "teleport", "label": "遷城特效"},
        {"id": "auras", "label": "光環造型"},
        {"id": "march", "label": "行軍造型"},
        {"id": "wings", "label": "城堡翅膀"},
        {"id": "adjacent", "label": "其他相鄰系統"},
        {"id": "panels", "label": "介面實例"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ]
    toc = toc_list(toc_items)
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{LEDE}</p>')
    add(f"    {toc}")

    # ----- 閱讀說明 -----
    add('    <section id="lead">')
    add("      <h2>閱讀說明</h2>")
    add(p_html(
        f"<strong>本頁主體是{H('城堡造型', terms)}</strong>"
        f"（介面欄位「{official_term_html(o.city_skin[1])}」）。"
        f"同一套「城堡外觀」介面還有{H('城堡效果', terms)}、{H('行軍造型', terms)}、"
        f"{H('城堡護盾', terms)}、{H('城堡翅膀', terms)}、{H('遷城特效', terms)}與{H('光環造型', terms)}；"
        "那些相鄰欄位另節登錄，不是城堡造型主體。"
        f"城鎮裝飾與地脈建築造型、DIY 裝飾套裝見<a href=\"decorations.html\">{H('裝飾物總表', terms)}</a>，不列入本頁主體。"
    ))
    add(p_html(
        "<strong>查城堡造型時，請先看面板上的星數、擁有屬性與使用屬性。</strong>"
        "蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪這四座：面板 0 星對應表上等級 1，滿 1 星對應表上等級 6。"
        "<strong>不能把表上等級當成面板星數。</strong>"
        "也不能把創世紀或永恆紀的表上等級 1／6／11 對成面板星數。"
        "表上也沒有標成「0 星／1 星」的欄。"
        "永恆紀目前滿星就是 0 星。"
        "各座滿星不一定相同，不能把某一座的滿星推成通例。"
        "左側心形數字是讚數，不是戰力，不寫進屬性。"
        "不依時間、賽季或伺服器欄位標未開放。"
    ))
    add("    </section>")

    # ----- 範圍 -----
    add('    <section id="scope">')
    add("      <h2>範圍與資料缺口</h2>")
    add(p_html("遊戲介面把「城堡外觀」分成六個欄位："))
    scope_rows = []
    notes = {
        1: f"獲得後有「{o.own_label}」；使用後另有「{o.use_label}」。說明文仍寫「裝備屬性」，與介面標籤不一致",
        2: "名稱與屬性見「城堡效果／特效」",
        3: "名稱與屬性見「行軍造型」",
        4: "名稱與屬性見「城堡護盾」",
        5: "稀有翅膀可給全公會加屬性；名稱與屬性見「城堡翅膀」",
        6: "名稱與屬性見「遷城特效」",
    }
    for i in range(1, 7):
        scope_rows.append([str(i), official_term_html(o.city_skin[i]), notes[i]])
    add(_tbl(["欄位", "名稱", "說明（介面字串）"], scope_rows, "cards", card_title="名稱"))
    add(p_html(
        f"另外還有「{official_term_html(o.halo_tab)}」頁，介面同樣有"
        f"「{official_term_html(o.halo_own)}」「{official_term_html(o.halo_use)}」。"
        f"影響力分類把「{official_term_html(o.influence[19])}」、"
        f"「{official_term_html(o.influence[20])}」、"
        f"「{official_term_html(o.influence[21])}」分成三項。"
    ))
    add(p_html(
        "護盾、效果、遷城、光環、行軍、翅膀與共鳴在本頁另節登錄。"
        "不要把面板「行軍造型 20%」強行對成其他表的屬性列。"
    ))
    add("    </section>")

    # ----- 系統機制 -----
    add('    <section id="mechanics">')
    add("      <h2>系統機制</h2>")
    add("<ul>")
    add(li_html(
        f"<strong>獲得與使用分兩套屬性。</strong>介面標籤為「{official_term_html(o.own_label)}」「{official_term_html(o.use_label)}」。"
        f"說明文寫「{official_term_html(o.city_skin_1_dec)}」，其中「裝備屬性」與介面的「使用屬性」應指同一套。"
        f"屬性加總標題為「{official_term_html(o.prop_sum)}」。"
    ))
    add(li_html(
        f"<strong>高級造型會覆蓋初級造型的擁有屬性。</strong>"
        f"系統提示：「{official_term_html(o.cover_tip)}」。原文只提擁有屬性，沒有寫使用屬性。"
        "任務字串可見升級後名稱加「-Lv.2」後綴，因此「高級／初級」可能指同一座城堡升級前後的形態，但這句系統提示沒有寫死範圍。"
        "高級造型也會覆蓋初級造型的「使用屬性」。官方只提擁有屬性。"
    ))
    illusion_lines = o.illusion_text.split("\n")
    effect_ill = o.effect_illusion_text.split("\n")
    add(li_html(
        f"<strong>{official_term_html(o.illusion)}</strong>。官方說明原文："
        f"<br>{official_term_html(o.illusion_title)}："
        + "".join(f"<br>{official_term_html(x)}" for x in illusion_lines if x)
        + f"<br>{official_term_html(o.effect_illusion_title)}："
        + "".join(f"<br>{official_term_html(x)}" for x in effect_ill if x)
        + "因此幻化不是只換外觀：使用屬性與領域效果會改套用目標，自身使用屬性失效。原文沒有寫擁有屬性會被替換或保留。"
        "幻化後自身「擁有屬性」仍保留。"
        "說明文案是通用的，沒有寫只有哪一座能幻化。目前只在水晶聖城見到「幻化」與"
        f"「{official_term_html(o.illusioning)}」按鈕。"
        "不要和城堡造型幻化、特效幻化混為一談。"
    ))
    add(li_html(
        "<strong>限時造型</strong>有獨立名稱（如 7 天／14 天），並有「【城堡造型】限時屬性」提示。"
        "南瓜小鎮另有獨立的限時道具，不是獨立永久造型。"
    ))
    add(li_html(
        "<strong>升級城堡與升級技能是兩件事。</strong>"
        "名稱下方的金星是城堡本身星級；技能等級是另一套。"
        f"技能升級介面字串：「{official_term_html(official_text('world_skin_skill_level_up_4'))}」。"
        "三座城堡（熾火要塞、山岳之傲、盾貝城）技能可升到 1–10 級；其他「可升級」城堡多半只有基礎技能與一筆強化技能。"
        "蛋糕城、飛翔號：表上等級 2–6 皆為道具 290 ×20。"
        "道具說明名單仍未列這兩座。"
    ))
    add(li_html(
        "<strong>賽季增益。</strong>字串有「（目前賽季生效，賽季結束後失效）」「（未生效，{0}賽季生效）」"
        f"另有說明：{official_term_html(official_raw('info_text_13004').replace(chr(10), '／'))}。"
        "蛋糕城、飛翔號沒有另列賽季加成分。本頁不展開其他造型的賽季加成分。"
    ))
    add(li_html(
        f"<strong>領域效果。</strong>介面標籤為「{official_term_html(official_text('world_skin_01_02'))}」，"
        f"另有「{official_term_html(official_text('castle_skill_ui_7'))}」"
        f"「{official_term_html(official_text('castle_skill_ui_8'))}」。"
        "目前語系只見三筆領域說明：創世紀、永恆紀、效果「星紀元」。"
        "文案皆寫「使用中生效」。詳見「領域效果」。"
    ))
    add(li_html(
        "<strong>共鳴。</strong>"
        f"官方說明為「{official_term_html(official_text('eternity_gm11'))}」，沒有寫死是哪兩座。"
        "須同時擁有創世紀與永恆紀才會啟動。"
        "不能把共鳴表上的等級讀成面板星數；0 星＝level 1、滿 1 星＝level 6 只鎖定在蛋糕城、飛翔號，"
        "不能套到創世紀或永恆紀，也不要把永恆紀目前的 0 星當成已核對的表上等級 1。"
        "已見到共鳴等級 1、2、3 的條件與額外擁有／額外使用（等級 3 另有領域範圍），詳見「共鳴」。"
        "不要把這三檔逕指為創世紀或永恆紀的基礎擁有／使用屬性或滿星屬性。"
        "目前只開到共鳴等級 1（已擁有創世紀與永恆紀）。"
        "永恆紀目前滿星就是 0 星，與名稱下無星相符。"
        "因此共鳴等級 2（兩城都要 1 星）與等級 3（都要 2 星）目前開不到。不要推斷永恆紀以後會不會開放升星。"
    ))
    add(li_html(
        "<strong>星級換算。</strong>"
        "畫面 1 顆星內部算 5 格，2 顆星算 10 格。"
        "這是可見星的對應，不是說每座城堡都可以停在 1/5、2/5 等中間檔；水晶聖城一次升級就滿一顆星，見介面實例。"
    ))
    add(li_html(
        "<strong>滿星不是全部 1 星。</strong>"
        "熾火要塞、山岳之傲、天空之城、水晶聖城的滿星都是 1 顆金星；"
        "蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪當時亦為滿星 1 星、永久（見主表與目錄）。"
        "創世紀滿星 2 顆金星；永恆紀目前滿星就是 0 星（名稱下沒有星，"
        "本抽取也沒有它的升星材料說明，與畫面相符）。"
        "另有一些當時能升星的城堡，滿星也是 1 星；這不是全部 68 組的通例，也不要把「可升級都是 1 星」寫成通例。"
        "創世紀目前最高仍是 2 星、永恆紀目前最高仍是 0 星。也不要推斷永恆紀以後會不會開放升星。"
        "不要把 2 顆星檔讀成滿星至少 10 星（創世紀面板為 2 金星）。內部檔名見資料說明。"
    ))
    add("</ul>")
    add("    </section>")

    # ----- 目錄 -----
    add('    <section id="directory">')
    add("      <h2>城堡造型目錄</h2>")
    add(p_html(
        "下列為說明寫成「城堡造型」的條目，外加預設造型「城堡」。"
        "博克島、霍金斯實驗室在表上沒有獨立名稱鍵，名稱取自說明文。"
        "畫面上也是「博克島」和「霍金斯實驗室」，就依這兩個名稱記。"
        "南瓜小鎮的限時道具不是獨立永久造型。"
    ))
    add(p_html(
        "重複獲得時，多數永久造型轉 5,000 鑽石；蘑菇為 1,000，奇幻舞台為 3,000，創世紀與永恆紀為 20,000。"
        "水晶聖城的說明沒有寫轉換鑽石。已永久啟用時再拿南瓜小鎮限時道具：7／14／30 天分別轉 1,000／2,000／4,000 鑽石。"
        "其餘限時名稱見各條備註。"
    ))
    add(p_html(
        "「技能」欄：基礎＝只有一筆；基礎＋強化＝另有強化列、無 1–10 級；"
        "1–10＝有強化技能且可再升到 10 級。創世紀有三筆技能，對應關係見技能章。"
        "巨蟹沙城、南瓜小鎮在 290 的可升級名單中，但本抽取沒有技能列。"
        "巨蟹沙城、南瓜小鎮、天空之城在本抽取沒有主動技能列，這已由技能表確認，不是漏對；天空之城畫面亦無技能按鈕。"
    ))
    up_map = _goods_upgrade_map(o)
    dir_rows = []
    for sid in DIRECTORY_IDS:
        # find group: usually group == sid, except 1 (group 1), 111 (group 110)
        g = None
        if sid == 1:
            g = data.groups[1]
        elif sid == 111:
            g = data.groups[110]
        else:
            g = data.groups.get(sid)
        name = g.name if g else official_text(f"skin_name_{sid}")
        desc = official_raw(g.rows[0].desc_key) if g and g.rows[0].desc_key else official_raw(f"skin_desc_{sid}")
        if sid == 1:
            diamonds = EMPTY
        elif sid == 312:
            diamonds = "說明未寫"
        else:
            diamonds = parse_repeat_diamonds(desc)
        mat = up_map.get(sid, EMPTY)
        note = DIRECTORY_NOTES.get(sid, "")
        dir_rows.append([
            str(sid),
            official_term_html(name),
            _skill_dir_label(sid, data),
            mat,
            diamonds,
            H(note, terms) if note else "",
        ])
    add(_tbl(["id", "名稱", "技能", "升級材料（說明名單）", "重複獲得", "備註"], dir_rows, "cards", card_title="名稱"))
    add(p_html(
        f"以上永久造型（含預設、不含南瓜小鎮限時道具）共 {len(DIRECTORY_IDS)} 座。"
        "有幾座名稱與若干賽季稱呼相近，這裡只記名稱，不推斷開放賽季。"
    ))
    add(p_html(
        "不能把未具名的 VIP18 造型逕指為某一座。"
        "VIP18 先拿到水晶聖城，再用 VIP20 水晶徽章（313）升成 VIP20 的水晶聖城。"
        "徽章說明只寫來自 VIP20 專屬禮包；官方屬性名仍是"
        f"「{official_term_html(official_text('attribute_name_1142'))}」，沒有寫造型名稱。"
        "對照：已實裝行軍造型「水晶戰車」（說明寫「VIP19級獲得」）；"
        "另有「專屬於VIP20的城堡及光環造型」；水晶聖城以 313 升級，光環「水晶冠冕」的說明寫「VIP20級獲得」。"
    ))
    add(p_html(
        "可贈送：春日小屋（品質 4）、火砲要塞、蛋糕城、南瓜小鎮（後三座品質 5）。"
        f"另有道具「{official_term_html(official_text('goods_name_503110010'))}」。"
        f"規則字串：{official_term_html(official_raw('castle_gift7').replace(chr(10), '／'))}。"
    ))
    add("    </section>")

    # ----- 主表 -----
    add('    <section id="main">')
    add("      <h2>城堡造型主表</h2>")
    add(p_html(
        f"本節抄錄全部 {data.table_meta['skin_groups']} 組城堡造型的擁有／使用曲線。"
        "表上沒有 0 這一行。預設「城堡」有五檔，賢者之城有三檔，創世紀與永恆紀有十一檔，"
        "另有一批只有一檔、一批有六檔；檔數是表上列數，不是面板星數，不要把「只有一檔」當成 0 星。"
        "<strong>不能把表的 level 當成面板星數。</strong>"
        "也不能把創世紀或永恆紀的表上等級 1／6／11 寫成面板幾星。"
        "表上也沒有標成「0 星／1 星」的欄。"
        "蛋糕城、飛翔號仍為已鎖定的表上等級 1–6 與 0 星／滿 1 星對應；"
        "美味史萊姆、夢幻摩天輪保留已確認的 0 星／滿 1 星，並補上中間檔的主表數字（中間檔未用面板核過）。"
        "其餘各組只抄表上等級與擁有／使用屬性，不是已用面板核過 0 星或滿星。"
        "創世紀目前最高 2 星、永恆紀目前最高 0 星仍見介面實例。"
        "主表曲線同時寫出百分比與表內原值（例如 4000 寫成 40%），不是改寫全書換算規則。"
        f"字串有但本表沒列的 {official_term_html(o.leftover_334)}、{official_term_html(o.leftover_407)}，不當成本表列。"
    ))

    def add_locked(gid, hid, title, full_txt, zero_txt, zero_kind, mid_note=False):
        g = data.groups[gid]
        add(f'    <section id="{hid}">')
        add(f"      <h3>{H(g.name, terms)}</h3>")
        add(p_html(
            f"六列，level 1–6；id 依序為 {_ids_list(g.rows, html=True)}。"
            f"{'使用屬性六階完全相同' + ('，與蛋糕城的使用屬性相同' if gid==302 else '') + '；擁有屬性隨表上等級遞增。' if True else ''}"
            f"{_cost_sentence(g.rows)}"
            f"{_quality_sentence(g.rows)}"
            + (
                "本節列出 0 星與滿 1 星，並補上表上等級 2–5 的數字；中間檔尚未用面板核對。"
                "這座與蛋糕城、飛翔號一樣都是主表六檔，使用屬性整條曲線不變，"
                f"滿 1 星對上表上等級 6（id {g.rows[-1].sid}），因此表上等級 1 就是 0 星檔。"
                if mid_note else ""
            )
        ))
        add(p_html(
            f"<strong>滿 1 星：</strong>{H(full_txt, terms)}"
        ))
        if zero_kind == "panel":
            add(p_html(
                f"<strong>0 星：</strong>{H(zero_txt, terms)}"
            ))
        else:
            add(p_html(
                f"<strong>0 星：</strong>{H(zero_txt, terms)}"
            ))
        use_p = _use_prose(g.rows, attrs)
        if use_p and gid != 318:
            # 318 另用下方已鎖定的「六階皆同」句，避免與自動句重複。
            add(p_html(H(use_p.replace("使用屬性（各階皆同）", "使用屬性（六階皆同）"), terms)))
        elif use_p:
            pass
        if gid == 302:
            add(p_html(
                "官方屬性名：21023 為「"
                + official_term_html(attr_label(21023, attrs))
                + "」；21024 為「"
                + official_term_html(attr_label(21024, attrs))
                + "」。顯示規則見資料說明。"
            ))
        if gid == 318:
            add(p_html(
                "使用屬性（六階皆同）：減傷 +5%（不是普攻減傷）、所有士兵攻擊 +5%。屬性編號對照見資料說明。"
            ))
        built = _curve_table(g.rows, attrs)
        if built:
            cols, body, mobile = built
            # add 備註 column
            notes = []
            for r in g.rows:
                if r.level == 1:
                    if mid_note:
                        notes.append("對應 0 星（表上等級 1）")
                    else:
                        notes.append("對應面板 0 星")
                elif r.level == 6:
                    notes.append("對應滿 1 星")
                elif mid_note:
                    notes.append("中間檔，尚未用面板核對")
                else:
                    notes.append("")
            cols = cols + ["備註"]
            body = [row + [notes[i]] for i, row in enumerate(body)]
            add(_tbl(cols, body, mobile if mobile != "cards" else "sticky2"))
        add("    </section>")

    add_locked(301, "g-301", "蛋糕城", PANEL_CAKE_FULL, PANEL_CAKE_ZERO, "panel")
    add_locked(302, "g-302", "飛翔號", PANEL_FLY_FULL, PANEL_FLY_ZERO, "panel")
    add_locked(317, "g-317", "美味史萊姆", PANEL_SLIME_FULL, PANEL_SLIME_ZERO, "infer", mid_note=True)
    add_locked(318, "g-318", "夢幻摩天輪", PANEL_WHEEL_FULL, PANEL_WHEEL_ZERO, "infer", mid_note=True)

    add(p_html(
        "以下為其餘 64 組的主表擁有／使用曲線。一律只抄表上等級與擁有／使用屬性，"
        "<strong>不能把表的 level 當成面板星數</strong>。"
        "0 星＝level 1 只鎖定蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪，不是 68 組通例。"
        "已有介面實例的組（熾火要塞、山岳之傲、創世紀、永恆紀、天空之城、水晶聖城）面板數字仍以「介面實例」為準，"
        "此處不把某一列寫成已用面板核過的 0 星或滿星。"
        "創世紀目前最高 2 星、永恆紀目前最高 0 星仍保留，不把他們的表上等級 1／6／11 寫成面板幾星。"
        f"字串有但本表沒列的 {official_term_html(o.leftover_334)}、{official_term_html(o.leftover_407)}，不當成本表列。"
    ))

    # default
    add('    <section id="g-default">')
    add("      <h3>預設城堡</h3>")
    add(p_html(
        "兩組都叫「城堡」，各有五列、表上等級 1–5，"
        "擁有屬性與使用屬性在全部等級都是空的，各列也沒有升級消耗。"
        "目錄所列預設造型對應其中一組；另一組是主表多出來的一組，名稱相同。"
        "本節只抄表，也不把表上等級當成面板星數。列上其他內部欄見資料說明。"
    ))
    def_rows = []
    for gid in (0, 1):
        for r in data.groups[gid].rows:
            def_rows.append([
                str(gid), str(r.level), "（空）", "（空）",
            ])
    add(_tbl(["組", "表上等級", "擁有", "使用"], def_rows, "sticky"))
    add("    </section>")

    def add_simple_group(gid, hid, heading=None, lead=None):
        g = data.groups[gid]
        add(f'    <section id="{hid}">')
        tag = "h3" if heading is None or heading == "h3" else "h4"
        add(f"      <{tag}>{H(g.name, terms)}</{tag}>")
        if lead:
            add(p_html(lead))
        else:
            add(p_html(H(_standard_group_prose(g, True, attrs, terms), terms)))
        up = _use_prose(g.rows, attrs)
        if up:
            add(p_html(H(up, terms)))
        op = _own_prose(g.rows, attrs)
        if op and (gid in (171, 327) or _own_constant(g.rows)):
            add(p_html(H(op, terms)))
        built = _curve_table(g.rows, attrs)
        if built:
            cols, body, mobile = built
            add(_tbl(cols, body, mobile, card_title="表上等級"))
        if gid == 331:
            # handled in level-1 table note
            pass
        add("    </section>")

    add_simple_group(
        171, "g-171", "h3",
        "三列，level 1–3；id 依序為 171、172、173。"
        + _quality_sentence(data.groups[171].rows)
        + _cost_sentence(data.groups[171].rows)
        + "<code>hide</code> 在 level 1–3 為 1。三列擁有屬性完全相同，使用屬性皆空。"
        "本節只抄表上 level 與擁有／使用屬性，不是已用面板核過 0 星或滿星。",
    )
    add_simple_group(
        311, "g-311", "h3",
        "十一列，表上等級 1–11；編號依序為 "
        + _ids_list(data.groups[311].rows, html=True) + "。"
        + _quality_sentence(data.groups[311].rows)
        + _cost_sentence(data.groups[311].rows)
        + "滿星為 2 顆金星；技能／領域的 1 顆星與 2 顆星檔，見技能章與介面實例。"
        "面板抄錄的擁有／使用與共鳴等級 1 額外屬性見「介面實例」與「共鳴」。"
        "<strong>不要把表上等級 1／6／11 寫成面板幾星</strong>，也不要把共鳴條件的 1／6／11 讀成此座星數。"
        "本節只抄表上等級與擁有／使用屬性。",
    )
    add_simple_group(
        327, "g-327", "h3",
        "十一列，表上等級 1–11；編號依序為 "
        + _ids_list(data.groups[327].rows, html=True) + "。"
        + _quality_sentence(data.groups[327].rows)
        + _cost_sentence(data.groups[327].rows)
        + "名稱下無星；目前滿星就是 0 星，不要推斷以後會不會開放升星。"
        "因此共鳴等級 2／3 目前開不到，見機制與介面實例。"
        "主表雖有 1–11 級列，且十一階擁有／使用完全相同，"
        "<strong>不能把表上等級當成目前可升的星數</strong>，也不要把表上等級 1／6／11 寫成面板幾星。"
        "面板 0 星＝表的等級 1 是蛋糕城、飛翔號的對應，不是這座已用面板對過主表。"
        "面板抄錄見「介面實例」。本節只抄表上等級與擁有／使用屬性。",
    )

    add('    <section id="g-16">')
    add("      <h3>表上有多檔的其他城堡</h3>")
    add(p_html(
        "下列各組在表上有多檔（六列）。檔數是表上列數，不是面板星數。只抄表，不是已用面板核過 0 星或滿星。"
        "熾火要塞、山岳之傲、天空之城、水晶聖城的面板抄錄見「介面實例」；"
        "水晶聖城另已鎖定沒有可停的 1/5–4/5 中間檔、一次升級就滿一顆星，故表上等級 2–5 只是表列，"
        "不要寫成可停的星級檔，也不把表上等級 1／6 寫成已用本表新核的 0 星／滿 1 星。"
    ))
    for gid in CURVE_16_ORDER:
        add_simple_group(gid, f"g-{gid}", "h4")
    add("    </section>")

    add('    <section id="g-1only">')
    add("      <h3>表上只有一檔的城堡</h3>")
    add(p_html(
        "下列 36 座在表上只有一檔（一列）。這是表上列數，不是面板星數，不要把「只有一檔」當成 0 星。"
        "只抄這一列的擁有／使用屬性，不是已用面板核過 0 星或滿星。"
        "不敗榮耀在表上有兩組，擁有／使用數字相同；目錄只列其中一座。"
        "黃金獅鷲與黃金獅鷲-戰鬥是目錄已鎖定的兩個獨立造型。"
        "博克島、霍金斯實驗室沒有獨立名稱鍵，名稱用已鎖定的面板名稱。"
        "品質欄與內部欄對照見資料說明。"
    ))
    l1_rows = []
    for gid in LEVEL1_ORDER:
        g = data.groups[gid]
        r = g.rows[0]
        note = g.name_note
        if gid == 101:
            note = "與黃金獅鷲-戰鬥為獨立造型"
        elif gid == 110:
            note = "目錄所列的那一組"
        elif gid == 111:
            note = "與上一組同名，目錄未單列"
        elif gid == 320:
            note = "名稱取自說明與畫面：博克島"
        elif gid == 330:
            note = "名稱取自說明與畫面：霍金斯實驗室"
        elif gid == 331:
            own_f = fmt_curve_pairs(r.own_f, attrs)
            note = (
                f"另有一組擁有屬性為{own_f}"
                "（僅此座擁有欄兩組不同；不另發明名稱）"
            )
        elif gid == 406:
            note = "面板與永久名稱為蒼穹雲都；說明與限時名稱／說明仍作滄穹雲都"
        else:
            note = note or ""
        l1_rows.append([
            str(gid),
            official_term_html(g.name) if g.name else e(g.name),
            str(r.quality if r.quality is not None else EMPTY),
            H(fmt_curve_pairs(r.own, attrs), terms),
            H(fmt_curve_pairs(r.equip, attrs), terms),
            note,
        ])
    add(_tbl(["組", "名稱", "品質", "擁有屬性", "使用屬性", "備註"], l1_rows, "cards", card_title="名稱"))
    add("    </section>")
    add("    </section>")  # main

    # ----- 升級材料 -----
    add('    <section id="upgrade">')
    add("      <h2>升級與升星材料</h2>")
    up_rows = []
    for gid in (290, 314, 305, 313):
        name, desc = o.goods[gid]
        up_rows.append([str(gid), official_term_html(name), official_term_html(desc).replace("<br>", "／")])
    add(_tbl(["道具", "名稱", "用途（道具說明原文）"], up_rows, "cards", card_title="名稱"))
    add(p_html(
        "技能 1–10 級消耗（道具 290）："
    ))
    su_rows = []
    total = 0
    for r in data.skill_level_up:
        cost = parse_cost(r.get("cost"))
        qty = cost[0][2] if cost else 0
        total += qty
        su_rows.append([str(r.get("level")), str(qty), str(r.get("skill_quality"))])
    add(_tbl(["技能等級", "消耗 290", "技能品質"], su_rows, "sticky"))
    add(p_html(
        f"合計 {total} 張城堡設計圖（只計這張技能升級表，不含把城堡升到可解鎖更高技能上限所需的數量）。"
    ))
    add(p_html(
        "道具說明稱 314 的對象為「蘑菇之家」，官方名稱另有「蘑菇」，可能是同一座城堡的不同稱呼。"
        f"現行道具說明名單為：{official_term_html(o.goods[314][1]).replace('<br>', '／')}。"
        "第 17 章此處仍按較早五座名單書寫（沒有火砲要塞）；本頁改引現行官方字串。主表火砲要塞升級消耗在章節與現行包都是道具 314 ×5。"
    ))
    add(p_html(
        "任務字串可見升級後名稱加「-Lv.2」，例如「擁有城堡巨蟹沙城-Lv.2」；290 名單中多座都有對應條目。"
        "同一批任務字串還有蛋糕城（301）、飛翔號（302）、美味史萊姆（317）的 -Lv.2，這三座卻不在 290／314 的說明名單；"
        "美味史萊姆的強化形態名稱為「加倍美味史萊姆」。"
        "夢幻摩天輪（318）技能表有強化列，也不在這兩份說明名單。"
        "蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪都用城堡設計圖（290）升級。"
        "道具說明名單仍未列這四座。"
        "蛋糕城／飛翔號主表等級 2–6 的消耗亦為 290×20。"
    ))
    add(p_html(
        f"採集物表仍只有 {data.table_meta['goods_rows']} 筆，分別是幸運火雞的"
        f"「{official_term_html(official_text('skin_goods_name_309'))}」"
        f"「{official_term_html(official_text('skin_goods_name_309_lv2'))}」與泡泡霜熊的"
        f"「{official_term_html(official_text('skin_name_3221'))}」，"
        "是技能在身邊生成的採集物，不是城堡升級材料表。"
        "所有道具說明裡寫「升級城堡外觀／升星」的道具，仍只有 290、314、305、313 四種；"
        "沒有任何道具說明把蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪列入可升級名單。"
        "夢幻摩天輪也沒有 <code>-Lv.2</code> 任務字串，只有技能表的強化列。"
        "升級材料以道具 290 與官方名單一併列出：說明名單尚未列這四座，但這四座都用 290 升級。"
    ))
    add("    </section>")

    # ----- 技能 -----
    add('    <section id="skills">')
    add("      <h2>城堡技能</h2>")
    add(p_html(
        "技能說明直接引用官方技能文案（遊戲已寫成百分比處，照錄，不是自行換算）。"
        "同一座城堡若有基礎與強化兩筆，後者效果較強，應是城堡升級後的技能；"
        "三座有 1–10 級的城堡，是在強化這筆之上再升級。"
        "每日次數取自技能列（與說明文案一致）。以下文案已去除色碼。"
    ))
    add("      <h3>有 1–10 級的技能</h3>")
    for sid, label in ((211, "熾火要塞"), (231, "山岳之傲"), (241, "盾貝城")):
        rows = data.skills_by_reset.get(sid) or []
        base = next((r for r in rows if r.skill_level == 0 and "lv2" not in r.desc_key), None)
        up = next((r for r in rows if r.skill_level == 0 and "lv2" in r.desc_key), None)
        leveled = [r for r in rows if r.skill_level >= 1]
        add(f"      <h4>{H(label, terms)}</h4>")
        if base:
            add(p_html(f"基礎（每日 {base.reset_times} 次）：{official_term_html(base.desc)}"))
        if up:
            add(p_html(f"升級後（每日 {up.reset_times} 次）：{official_term_html(up.desc)}"))
        if leveled:
            add(p_html("1–10 級（皆在升級後這筆之上；每日次數與升級後相同）："))
            lv_rows = []
            if up:
                lv_rows.append(["0（升級後）", official_term_html(up.desc)])
            for r in leveled:
                lv_rows.append([str(r.skill_level), official_term_html(r.desc)])
            add(_tbl(["技能等級", "效果（官方說明）"], lv_rows, "cards", card_title="技能等級"))
    add("      <h3>只有基礎或基礎＋強化的技能</h3>")
    basic_order = (
        (213, "奪魄聖殿"), (271, "混亂之塔"), (306, "奇幻舞會"), (307, "協奏"),
        (310, "鋼鐵元帥"), (311, "創世紀"), (313, "冰雪王國"), (318, "夢幻摩天輪"),
        (321, "晶角獸城"), (323, "深海王庭"), (324, "魔龍寶庫"), (326, "閃耀球場"),
        (327, "永恆紀"), (329, "DJ·喵喵"), (330, "霍金斯實驗室"), (333, "幻夜之曲"),
    )
    b_rows = []
    for sid, label in basic_order:
        rows = data.skills_by_reset.get(sid) or []
        for r in rows:
            if r.skill_level:
                continue
            stage = "基礎"
            if "star5" in r.desc_key:
                stage = "鍵名 star5"
            elif "star10" in r.desc_key:
                stage = "鍵名 star10"
            elif "lv2" in r.desc_key:
                stage = "強化"
            b_rows.append([H(label, terms), stage, official_term_html(r.desc), str(r.reset_times)])
    add(_tbl(["造型", "階段", "效果（官方說明，已去色碼）", "每日"], b_rows, "cards", card_title="造型"))
    add(p_html(
        "夢幻摩天輪當時開到的技能畫面與升級檔 <code>world_skin_skill_318_lv2</code> 完全一致："
        "減傷 +15%、士兵生命 +120%，持續 20 分鐘，每日 3 次。這是面板與強化檔對上，不是另推的換算。"
    ))
    add(p_html(
        "創世紀三筆技能的 <code>skill_level</code> 皆為 0，表內沒有星級數字欄；說明鍵分別為 "
        "<code>world_skin_skill_311</code>、<code>world_skin_skill_311_star5</code>、<code>world_skin_skill_311_star10</code>，"
        "與道具 305「可用於城堡造型創世紀、天空之城的升星」相符。"
        "<strong>不要把鍵名 star5／star10 讀成滿星至少 5 星或 10 星。</strong>"
        "內部 star5＝畫面 1 顆星、star10＝2 顆星；創世紀滿星為 2 顆金星，與這檔對得上。"
        "這三筆依鍵名對應基礎、1 顆可見星、2 顆可見星（滿星），不是從升星上限欄讀出的。"
        "天空之城可升星，本抽取卻沒有技能列；畫面亦無技能按鈕，與表相符。"
    ))
    add("      <h3>生成物與贈禮技能</h3>")
    for sid, label in ((309, "幸運火雞"), (322, "泡泡霜熊")):
        rows = data.skills_by_reset.get(sid) or []
        add(f"      <h4>{H(label, terms)}</h4>")
        for r in rows:
            stage = "強化" if "lv2" in r.desc_key else "基礎"
            add(p_html(f"{stage}（每日 {r.reset_times} 次）：{official_term_html(r.desc)}"))
    add(p_html(
        f"採集物表：感恩大餐／高級皆需造型 309、造型等級 1 至 6；"
        "這只說明這張採集物表承認造型等級 1 至 6，不是滿星上限欄。"
        "泡泡霜熊對應 id 3，需造型 322、等級 1。"
    ))
    add(f"      <h4>{H('美味史萊姆', terms)}（317）</h4>")
    add(p_html("有兩組技能（<code>resetGroup</code> 3171 與 3172）："))
    add("<ul>")
    for rg, kind in ((3171, "贈送，skill_group=-1"), (3172, "自領，skill_group=1000")):
        rows = data.skills_by_reset.get(rg) or []
        add(li_html(f"{rg}（{kind}）："))
        for r in rows:
            add(li_html(
                f"<code>{e(r.desc_key)}</code>（名稱 {official_term_html(r.name)}，每日 {r.reset_times} 次）："
                f"{official_term_html(r.desc)}"
            ))
    add("</ul>")
    add(p_html(
        "技能表的強化列名稱已指向「加倍美味史萊姆」（<code>skin_name_317_lv2</code> 存在；上列名稱欄以技能表 <code>name</code> 鍵為準）。"
        "升級用城堡設計圖（290），主表等級 2–6 消耗亦為 290×20，但 290／314 說明名單尚未列這座。"
    ))
    add(p_html(
        "面板上：畫面技能名稱是「加倍美味史萊姆」；開到的是贈送介面，每日選三位玩家送糖果，"
        "畫面寫「今日剩餘贈送次數 0/3」，與官方技能文案（每日 3 次、贈送精緻史萊姆糖果）對得上。"
        "表上另有自領列（給自己開糖果）。"
        "「使用」就是給自己拿糖果，沒有另外一套特別說明。"
        "自領那筆當時未在畫面上獨立看到。"
    ))
    add("    </section>")

    # ----- 套裝 -----
    add('    <section id="suits">')
    add("      <h2>城堡造型套裝</h2>")
    add(p_html(
        f"套裝表共 {data.table_meta['suit_rows']} 套。"
        "一套通常要集齊指定的城堡造型，以及護盾、效果、行軍、遷城、翅膀或光環。"
        f"套裝獎勵另有 {data.table_meta['reward_rows']} 筆。"
        f"官方介面名稱為「{official_term_html(o.fashion_point)}」。"
        "這些獎勵道具在本抽取沒有物品名，故只記編號。屬性用官方名稱，數值為表內原值。欄位對照見資料說明。"
    ))
    add(p_html(
        f"套裝「{official_term_html(official_text('citybuilding_DIY_suit_name_52'))}」沿用此官方名稱。"
        "揚帆啟航護盾對應洋流環繞，不是果香帷幕。編號對照見資料說明。"
    ))

    def effect_name(eid):
        for ev in data.effects:
            if ev.sid == eid or ev.group == eid:
                return ev.name or str(eid)
        return str(eid)

    def march_name(mid):
        for r in data.marches:
            if _int(r["id"]) == mid:
                return official_text(r.get("name")) or str(mid)
        return str(mid)

    def wing_name(wid):
        for r in data.wings:
            if _int(r["id"]) == wid:
                return official_text(r.get("name")) or str(wid)
        return str(wid)

    def castle_member(cid):
        g = data.groups.get(cid) or data.groups.get(cid) 
        # id 316 etc is group
        if cid in data.groups:
            return f"{data.groups[cid].name}（{cid}）"
        # maybe directory id
        for g in data.groups.values():
            if g.display_id == cid or any(r.sid == cid for r in g.rows):
                return f"{g.name}（{cid}）"
        return str(cid)

    suit_rows_html = []
    # keep chapter order by `order` field? chapter order is 1001.. as in file
    suits_sorted = sorted(data.suits, key=lambda r: _int(r.get("id")))
    rewa_by = defaultdict(list)
    for r in data.suit_rewards:
        rewa_by[_int(r.get("skin_collection_main_id"))].append(r)
    for s in suits_sorted:
        sid = _int(s["id"])
        sname = official_text(s.get("name"))
        castle = s.get("req_world_skin")
        castle_txt = castle_member(_int(castle)) if not is_empty(castle) else "—"
        others = []
        pairs = [
            ("護盾", s.get("req_world_skin_shield"), effect_name),
            ("效果", s.get("req_world_skin_effect"), effect_name),
            ("行軍", s.get("req_world_skin_march"), march_name),
            ("遷城", s.get("req_world_skin_move"), effect_name),
            ("光環", s.get("req_world_skin_aura"), effect_name),
        ]
        for label, val, fn in pairs:
            if is_empty(val) or str(val) in ("-1", "0"):
                continue
            others.append(f"{label} {fn(_int(val))}（{_int(val)}）")
        wings_req = s.get("req_world_skin_wing") or s.get("req_world_skin_wing_Arr")
        if not is_empty(wings_req) and str(wings_req) not in ("-1", "0"):
            if isinstance(wings_req, list):
                ids = [_int(x) for x in wings_req]
            else:
                ids = [_int(x) for x in str(wings_req).split("|") if x not in ("", "-1")]
            if ids:
                others.append("翅膀 " + "、".join(f"{wing_name(i)}（{i}）" for i in ids))
        rewas = sorted(rewa_by.get(sid, []), key=lambda r: _int(r.get("req_collect_num")))
        attr_bits = []
        pts = []
        for rw in rewas:
            n = rw.get("req_collect_num")
            pairs_a = parse_pairs(rw.get("collect_skin_attr"))
            attr_s = "、".join(f"{attr_label(a, attrs)}（{a}） {v}" for a, v in pairs_a) if pairs_a else EMPTY
            attr_bits.append(f"{n} 件：{attr_s}")
            pts.append(str(rw.get("collect_skin_point")))
        note = ""
        ut = s.get("unlocktime")
        if not is_empty(ut):
            note = f"；解鎖時間 {format_unlock_range(ut)}（檔內無時區，只照錄）"
        if sid == 1003:
            note = "；揚帆啟航護盾為洋流環繞，不是果香帷幕" + note
        if sid == 1005:
            note = (
                "。面板上：護盾是雪球舞會，效果與光環畫面都寫「怪奇物語」，"
                "行軍是兩心同騎，遷城是逆界閃遷。語系另有名稱「電流閃爍」、「頻閃迴響」，與表列名稱／說明一併記錄，"
                "不要把這兩個名稱當成效果／光環的表列正式名"
                + note
            )
        if sid == 1007:
            note = "；光環 5005 官方名為鳳焰裂地，此為 type 4 列的官方名，不是面板另鎖定" + note
        if sid == 1008:
            note = "；光環 5007 官方名為馴龍高手。名稱是「馴龍高手、鳳焰裂地」" + note
        suit_rows_html.append([
            official_term_html(sname),
            str(s.get("quality")),
            H(castle_txt, terms),
            H("、".join(others) if others else EMPTY, terms) + note,
            "；".join(attr_bits),
            "／".join(pts) + (note if sid in (1006, 1008) and "解鎖時間" in note else ""),
        ])
    add(_tbl(["套裝", "品質", "城堡造型", "其他成員", "件數與屬性", "時尚值"], suit_rows_html, "cards", card_title="套裝"))
    add(p_html(
        f"翅膀 1、2 的官方名為「{official_term_html(official_text('world_skin_wing_name_1'))}」、「{official_term_html(official_text('world_skin_wing_name_2'))}」。"
        f"套裝介面寫「{official_term_html(o.wing_suit)}」，與羽翼典藏屬性方向一致。"
    ))
    add(p_html(
        f"官方套裝說明：{official_term_html(official_raw('skin_collection_rules_desc').replace(chr(10), '／'))}"
    ))
    fash_rows = []
    for r in sorted(data.fashion, key=lambda x: _int(x.get("order") or x.get("id"))):
        fash_rows.append([str(r.get("order") or r.get("id")), str(r.get("point_require")), str(r.get("mission_reward"))])
    add(p_html(f"時尚值獎勵 {data.table_meta['fashion_rows']} 檔。本抽取沒有這些獎勵的物品名，故只記編號。"))
    add(_tbl(["檔", "時尚值門檻", "獎勵編號"], fash_rows, "sticky"))
    add("    </section>")

    # ----- 領域 -----
    add('    <section id="territory">')
    add("      <h2>領域效果</h2>")
    add(p_html("以下領域說明皆為官方字串，不是從城堡造型主表讀出的基礎擁有／使用屬性。共鳴三檔另有面板核對，見「共鳴」。"))
    add(f"      <h3>{H('創世紀', terms)}</h3>")
    add(p_html(f"基礎領域：{official_term_html(official_raw('skin_territory_311'))}"))
    add(p_html(f"2 顆星檔：{official_term_html(official_raw('skin_territory_311_star10'))}"))
    add(p_html(
        "這份 2 顆星檔與對應技能、道具 305 相符。"
        "這就是創世紀的滿星檔，不是「至少 10 星」。不要把某一座的滿星顆數推到其他造型。"
    ))
    add(f"      <h3>{H('永恆紀', terms)}</h3>")
    add(p_html(official_term_html(official_raw('skin_territory_327'))))
    add(f"      <h3>{H('星紀元', terms)}</h3>")
    add(p_html(official_term_html(official_raw('skin_territory_2011'))))
    add(p_html(official_term_html(official_raw('skin_territory_2011_extra'))))
    ev2011 = next((ev for ev in data.effects if ev.sid == 2011), None)
    if ev2011:
        add(p_html(
            "星紀元在效果表為城堡效果、編號 2011。"
            f"表上領域範圍為 {ev2011.raw.get('territory_range')}，"
            "參數欄原值見資料說明，"
            "升級範圍欄點名創世紀、永恆紀。原值見資料說明。"
            f"擁有屬性為 {fmt_raw_pairs(ev2011.own)}（出征上限，照點數記），"
            "使用屬性為空。主表 68 組沒有欄位指向這一列；連動方向是這張特效列指向創世紀、永恆紀。欄位對照見資料說明。"
        ))
    add(p_html(
        "創世紀、永恆紀在表上等級 1–10 的領域範圍欄為 4，等級 11 為 5。只記欄位原值。"
        "<strong>不要把範圍欄 4／5 寫成已證明等於文案的 9×9／11×11</strong>；文案尺寸見下，欄位與畫面的對拍仍需面板。"
    ))
    add(p_html("領域範圍（只錄字串與表上已見欄位，不推未寫明的星級，也不把表欄折成格數公式）："))
    add("<ul>")
    add(li_html(official_term_html(official_raw('castle_upgrade_des3').replace(chr(10), '／'))))
    add(li_html(official_term_html(official_raw('skin_link1'))))
    add(li_html(official_term_html(official_raw('skin_link2'))))
    add(li_html(official_term_html(official_raw('castle_upgrade_des14'))))
    add("</ul>")
    add("    </section>")

    # ----- 共鳴 -----
    add('    <section id="resonance">')
    add("      <h2>共鳴</h2>")
    add(p_html(
        f"本抽取這張表有 {data.table_meta['link_rows']} 列。三列都綁創世紀與永恆紀。"
        "三檔編號為 1、2、3；條件是兩座城堡的主表等級須同時達到 1、6、11（這是表上等級，不是面板星數）。"
        "對應字串鍵見資料說明。"
    ))
    add(p_html(
        "<strong>不能把這裡的表上等級讀成面板星數。</strong>"
        "面板 0 星＝表上等級 1、滿 1 星＝表上等級 6，只鎖定在蛋糕城、飛翔號，不能套到創世紀或永恆紀。"
        "不要把永恆紀目前的 0 星當成已核對的表上等級 1。"
    ))
    add(p_html(
        "<strong>官方共鳴說明更正。</strong>"
        "先前研究備註曾把這條記成官方未命名。"
        f"現行字串為「{official_term_html(official_text('eternity_gm11'))}」，與先前正文已抄錄的用字相同。"
        "官方文案仍沒有寫死是哪兩座。須同時擁有創世紀與永恆紀才會啟動。"
    ))
    gm_keys = ("eternity_gm1","eternity_gm3","eternity_gm4","eternity_gm5","eternity_gm6","eternity_gm7","eternity_gm8","eternity_gm9","eternity_gm10","eternity_gm12","eternity_gm13")
    add(p_html("其他相關官方用字（照錄）：" + "；".join(
        official_term_html(official_text(k)) for k in gm_keys
    ) + "。"))
    add(p_html(
        "表上三列的屬性原值如下。聯盟／部族／自然逆克制增傷的官方名照錄；"
        f"官方字串與面板把這三條收成一句「{official_term_html(o.damage_name)}」，"
        "不要把面板那句逕指成聯盟那條。表內仍記原值。鍵名與顯示規則見資料說明。"
    ))
    link_rows = []
    for r in data.links:
        link_rows.append([
            str(r.get("id")),
            str(r.get("linklevel")),
            str(r.get("level")),
            fmt_raw_pairs(parse_pairs(r.get("attr_own"))),
            fmt_raw_pairs(parse_pairs(r.get("attr_equip"))),
            official_text(r.get("buff_key")) or e(r.get("buff_key") or ""),
            "空" if is_empty(r.get("buff_range")) else str(r.get("buff_range")),
            official_term_html(official_raw(r.get("buff_range_desc"))) if r.get("buff_range_desc") else "",
        ])
    add(_tbl(["檔", "共鳴等級", "條件（表上等級）", "擁有原值", "使用原值", "對照字串", "領域範圍", "領域說明"], link_rows, "cards", card_title="檔"))
    add(p_html(
        "<strong>共鳴額外屬性（三檔皆已核到）。</strong>"
        "三檔的條件與數值仍依面板抄錄，並與上述字串對照，不以表列改寫已核對的面板數值。"
        "不要把這三檔逕指為創世紀或永恆紀的基礎擁有／使用屬性或滿星屬性。"
        "面板條件寫的是「兩個城堡等級達到：」與金星顆數，那是第四版已核到的畫面，不是把表的 <code>level</code> 1／6／11 自行換算成星數。"
    ))
    add(p_html(
        "目前只開到共鳴等級 1（已擁有創世紀與永恆紀）。"
        "永恆紀目前滿星就是 0 星，與名稱下沒有星相符。"
        "因此等級 2（兩個城堡都要達到 1 星）與等級 3（都要達到 2 星）目前開不到。不要推斷永恆紀以後會不會開放升星。"
    ))
    res_panel = [
        ["1", "「啟動兩個城堡造型」", "逆克制增傷 +1%、出征上限 +10", "所有士兵攻擊 +5%", EMPTY, "與 jbms_csj1 完全一致"],
        ["2", "「兩個城堡等級達到：」1 顆金星（畫面為 1 金星＋1 灰星空位，讀成要 1 星，不要讀成 2 星）", "逆克制增傷 +1.5%、出征上限 +15", "所有士兵攻擊 +8%", EMPTY, "與 jbms_csj2 完全一致"],
        ["3", "「兩個城堡等級達到：」2 顆金星", "逆克制增傷 +2.5%、出征上限 +25", "所有士兵攻擊 +10%", "面板正文：「永恆紀、創世紀領域範圍從11*11擴大至13*13（星紀元領域同時提升）」。jbms_csj3 同段未寫「永恆紀、創世紀」，以面板為準。「星紀元」照官方／面板原文，不自行解釋或推斷它是哪個造型。", "數值與領域幅度與 jbms_csj3 一致"],
    ]
    add(_tbl(["共鳴等級", "面板條件", "額外擁有", "額外使用", "領域範圍", "對照字串"], [[H(c, terms) for c in row] for row in res_panel], "cards", card_title="共鳴等級"))
    add(p_html(
                f"以下四節（城堡效果／特效、護盾、遷城、光環）的列都來自同一張效果表（{data.table_meta['effect_rows']} 列、{data.table_meta['effect_groups']} 組），依效果、護盾、遷城、光環分開寫。"
        "這張表不是純特效資源：幾乎每列都同時有路徑與擁有／使用屬性（或其中之一）。"
        "本表沒有用 VIP 或賽季欄標未開放。"
        "表上另有戰力欄，只記原值，不把此欄對成左側心形讚數。"
        "來源道具只記編號；本抽取的道具主表是骨架表，不為這些編號取物品名。"
    ))
    add("    </section>")

    def conversion_note(raw):
        if is_empty(raw):
            return EMPTY
        text = str(raw)
        if "5000" in text:
            return "轉 5,000 鑽"
        if "3000" in text:
            return "轉 3,000 鑽"
        return text

    # ----- 效果 -----
    add('    <section id="effects">')
    add("      <h2>城堡效果／特效</h2>")
    t1 = data.effects_by_type.get(1) or []
    groups1 = {ev.group for ev in t1}
    add(p_html(
        f"{len(t1)} 列、{len(groups1)} 組（2001–2020，無缺號），皆只有一檔。"
        "官方說明多數寫「使用後可獲得城堡效果」；怪奇物語的說明寫「城堡特效造型」。"
        "屬性以所有士兵攻擊、所有士兵生命、出征上限為主；表內只記原值。"
        "寒冬之雪、水晶魔力沒有擁有屬性，只有使用屬性。"
        "星紀元沒有使用屬性，領域欄見「領域效果」。"
    ))
    add(p_html(
        "此列與光環裡那一列官方都叫「怪奇物語」，但是不同類型、不同編號，不能合併成同一件物品。"
        "聯名活動另有名稱「電流閃爍」「頻閃迴響」，都不是本列的表列名稱。"
        "面板上：效果與光環畫面都寫「怪奇物語」，依畫面記。鍵名對照見資料說明。"
    ))
    e1_rows = []
    for ev in t1:
        e1_rows.append([
            str(ev.sid),
            official_term_html(ev.name),
            fmt_raw_pairs(ev.own),
            fmt_raw_pairs(ev.equip),
            conversion_note(ev.conversion) if ev.sid == 2011 else "",
        ])
    add(_tbl(["id", "名稱", "擁有屬性（原值）", "使用屬性（原值）", "備註"], e1_rows, "cards", card_title="名稱"))
    add(p_html("沒有 021 以後的效果組。怦然心動的技能是表演技能，每日次數見技能表。"))
    add("    </section>")

    # ----- 護盾 -----
    add('    <section id="shields">')
    add("      <h2>城堡護盾</h2>")
    t2 = data.effects_by_type.get(2) or []
    ids2 = sorted({ev.sid for ev in t2})
    add(p_html(
        f"{len(t2)} 列、{len({ev.group for ev in t2})} 組（{ids2[0]}–{ids2[-1]} 之間缺表組 3009），皆 <code>level=1</code>。"
        "官方 desc 寫「使用後可獲得城堡護盾造型」。文案已寫成百分比處，照錄，不把它反推成表內原值。"
    ))
    add(p_html(
        "<strong>護盾編號與名稱在果香帷幕之後錯開一號。</strong>"
        "其中一列官方名是果香帷幕；下一列官方名是洋流環繞。"
        "沒有再下一號的表列，也沒有缺官方名的那一鍵。這是名稱編號的錯位，不是洋流環繞缺官方名。"
        "套裝「揚帆啟航」對上的護盾是洋流環繞。"
    ))
    sh_rows = []
    for ev in t2:
        extra = ev.extra or ""
        sh_rows.append([
            str(ev.sid),
            official_term_html(ev.name),
            str(ev.quality or EMPTY),
            fmt_raw_pairs(ev.own),
            fmt_raw_pairs(ev.equip),
            (conversion_note(ev.conversion) + ("；" + official_term_html(extra) if extra else "")),
        ])
    add(_tbl(["編號", "名稱", "品質", "擁有屬性（原值）", "使用屬性（原值）", "重複獲得／效果說明"], sh_rows, "cards", card_title="名稱"))
    ev3013 = next((ev for ev in t2 if ev.sid == 3013), None)
    if ev3013:
        add(p_html(
            "3013 淨月蓮是本表唯一填了聯盟護盾數值欄的列："
            f"範圍欄 {ev3013.raw.get('allianceShieldRange')}，"
            f"時間欄 {ev3013.raw.get('allianceShieldTime')}，"
            f"每日次數欄 {ev3013.raw.get('allianceShieldDailyMaxTimes')}。"
            "官方 extra 寫「為 3 格範圍內盟友開啟護盾 1 小時，每日次數 {0}/{1} 次」。"
            "官方「3 格」與表上 range=4 並列，不在這裡折成同一單位，仍需面板。"
        ))
    add(p_html(
        "同系列另有名稱「抵禦斗篷」。"
        "本表 type 2 沒有 id 7402 這一列，只是同系列字串，效果文案與一般護盾造型不同。"
        "3015 官方 extra 用字為「部落士兵」（照錄官方字串，不改成部族）。"
    ))
    add("    </section>")

    # ----- 遷城 -----
    add('    <section id="teleport">')
    add("      <h2>遷城特效</h2>")
    t3 = data.effects_by_type.get(3) or []
    add(p_html(
        f"{len(t3)} 列、{len({ev.group for ev in t3})} 組，缺表組 4010，皆 <code>level=1</code>。"
        "官方 desc 寫「使用後可獲得城堡遷城特效」。這 11 列都有屬性，不是純遷城動畫。"
        "4002 霸主遷城沒有 <code>attr_own</code>，只有 <code>attr_equip</code>。"
        "楓葉隨風的解鎖時間只照錄，檔內無時區。"
    ))
    tp_rows = []
    for ev in t3:
        tp_rows.append([
            str(ev.sid), official_term_html(ev.name),
            fmt_raw_pairs(ev.own), fmt_raw_pairs(ev.equip),
            e(format_unlock_range(ev.unlocktime)) if not is_empty(ev.unlocktime) else "",
        ])
    add(_tbl(["id", "名稱", "擁有屬性（原值）", "使用屬性（原值）", "備註"], tp_rows, "cards", card_title="名稱"))
    add("    </section>")

    # ----- 光環 -----
    add('    <section id="auras">')
    add("      <h2>光環造型</h2>")
    t4 = data.effects_by_type.get(4) or []
    add(p_html(
        f"{len(t4)} 列、{len({ev.group for ev in t4})} 組：5001 春光綻放、5002 水晶冠冕、5004 怪奇物語、5005 鳳焰裂地、5007 馴龍高手。"
        "缺表組 5003、5006。官方 desc 寫「使用後可獲得城堡光環造型」。"
        f"介面另有「{official_term_html(o.halo_own)}」「{official_term_html(o.halo_use)}」標籤。"
    ))
    add(p_html(
        "光環名稱是「馴龍高手、鳳焰裂地」。"
        "字串 36007 是馴龍高手、36005 是鳳焰裂地；依套裝歸屬，5007 對馴龍高手、5005 對鳳焰裂地，與本表 type 4 的 <code>name</code>／<code>desc</code> 欄一致。"
    ))
    add(p_html(
        "春光綻放（組 5001）與怪奇物語光環（組 5004）各有三列，表 <code>level</code> 為 1、6、11，"
        "官方名為 Lv.1／Lv.2／Lv.3（春光綻放第一列官方名沒有「Lv.1」前綴），<code>level_up_step=5</code>。"
        "<strong>這是光環自己的升級列，不是城堡星級</strong>，也還沒用面板核對 Lv 與升級材料在畫面上怎麼顯示。"
        "不要發明光環等級的顯示規則。"
        "水晶冠冕（5002）官方 desc 寫「VIP20級獲得」，但本列 <code>unlockvip=-1</code>。不要把它和主表 312 水晶聖城混為一談。"
        "5005 鳳焰裂地本列掛的 desc 是 <code>world_effect_desc_36005_1</code>（沒有公會疊加句）；"
        "另有一條未掛在本列的 <code>world_effect_desc_36005</code> 帶公會疊加句。以哪一條為準，表不能決定，二者一併記錄。"
        "馴龍高手只有表上等級 1 一列，卻有升級步進 5；是否預留未列入的升級列，表沒有寫，不推測。"
        "字串另有閃電衝擊，以及一個缺號；本表光環沒有對應列，只記錄字串，不為缺號補表列。"
    ))
    au_rows = []
    for ev in t4:
        alliance = parse_pairs(ev.raw.get("property_alliance"))
        maxn = ev.raw.get("property_alliance_max_num")
        au_rows.append([
            str(ev.sid), str(ev.group), str(ev.level),
            official_term_html(ev.name),
            fmt_raw_pairs(ev.own),
            fmt_raw_pairs(ev.equip),
            (fmt_raw_pairs(alliance) + (f"（{maxn}）" if not is_empty(maxn) and str(maxn) not in ("-1",) else "")) if alliance else "無",
        ])
    add(_tbl(["編號", "組", "表上等級", "官方名", "擁有屬性（原值）", "使用屬性（原值）", "公會屬性（上限）"], au_rows, "cards", card_title="官方名"))
    add("    </section>")

    # ----- 行軍 -----
    add('    <section id="march">')
    add("      <h2>行軍造型</h2>")
    add(p_html(
        f"{data.table_meta['march_rows']} 列。官方說明一律寫「使用後可獲得行軍造型」，"
        "這就是城堡／大世界的行軍外觀表，不是部隊皮膚，也不是地圖行軍表。"
        "編號為 1001–1017、1019、1023–1027。表內沒有 1018、1020–1022、1028。"
        f"官方字串有「{official_term_html(official_text('skin_name_1028'))}」，"
        "但本表與造型總表的對應區都沒有這一列；"
        "造型總表另有一筆，其名稱／說明鍵在本檔缺失。"
        "都不為缺號補名稱。本頁不另開地心探險目錄。"
    ))
    add(p_html(
        "水晶戰車的官方說明寫「VIP19級獲得」，這是字串，不是解鎖欄；"
        "不要和水晶聖城、光環「水晶冠冕」混為一談。"
        "不要把面板「行軍造型 20%」強行對成下表任何一列。"
    ))
    m_rows = []
    for r in data.marches:
        mid = _int(r["id"])
        m_rows.append([
            str(mid),
            official_term_html(official_text(r.get("name"))),
            str(r.get("quality") or EMPTY),
            fmt_raw_pairs(parse_pairs(r.get("attr_own"))),
            fmt_raw_pairs(parse_pairs(r.get("attr_equip"))),
            (("解鎖時間 " + e(format_unlock_range(r.get("unlocktime"))) + "（只照錄）") if not is_empty(r.get("unlocktime")) else ""),
        ])
    add(_tbl(["編號", "名稱", "品質", "擁有屬性（原值）", "使用屬性（原值）", "備註"], m_rows, "cards", card_title="名稱"))
    add("    </section>")

    # ----- 翅膀 -----
    add('    <section id="wings">')
    add("      <h2>城堡翅膀</h2>")
    add(p_html(
        f"{data.table_meta['wing_rows']} 列，皆 <code>level=1</code>。"
        "官方說明都沒有寫重複獲得轉鑽石。字串寫稀有翅膀可給全公會加屬性。"
        "<strong>表內沒有指向某一 <code>world_skin</code> 組的外鍵。</strong>"
        "兩列的 3D 材質路徑都寫 <code>M_yunzhicheng3D_*</code>；這只是資源路徑，不能拿來掛到某一座城堡。"
        f"套裝介面字串 <code>world_skin_wing_suit</code>＝「{official_term_html(o.wing_suit)}」，"
        "與這兩列翅膀的 <code>attr_own</code>／<code>attr_equip</code>／<code>property_alliance</code> 對不上（兩列都沒有 3029／4031／5027）。"
        "羽翼典藏套裝獎勵仍是這三條逆克制屬性，不要和翅膀列本身的屬性混為一談。"
        "消耗欄寫成 1、沒有對應道具的含義，表沒有再說明；實際操作仍需面板。"
    ))
    w_rows = []
    for r in data.wings:
        w_rows.append([
            str(r.get("id")),
            official_term_html(official_text(r.get("name"))),
            str(r.get("source_goods") or EMPTY),
            fmt_raw_pairs(parse_pairs(r.get("attr_own"))),
            fmt_raw_pairs(parse_pairs(r.get("attr_equip"))),
            fmt_raw_pairs(parse_pairs(r.get("property_alliance"))) + f"（上限 {r.get('property_alliance_max_num')}）",
        ])
    add(_tbl(["編號", "官方名", "來源道具（編號）", "擁有屬性（原值）", "使用屬性（原值）", "公會屬性"], w_rows, "cards", card_title="官方名"))
    add(p_html("套裝「羽翼典藏」要求翅膀 1｜2。id 2 的說明鍵是 <code>world_skin_wing_desc2</code>（鍵名少一條底線）。"))
    add("    </section>")

    # ----- 相鄰 -----
    add('    <section id="adjacent">')
    add("      <h2>其他相鄰系統</h2>")
    add(p_html("以下兩項仍與城堡造型分開，不是上面四張附屬表。本頁不展開村莊風格逐棟屬性，也不把地脈建築造型或 DIY 裝飾套裝寫進主體。"))
    add("      <h3>建造造型／村莊風格</h3>")
    v_rows = []
    for r in data.village:
        v_rows.append([
            str(r.get("id")),
            official_term_html(official_text(r.get("name"))),
            str(r.get("season")),
            f"<code>{e(r.get('name'))}</code>",
        ])
    add(_tbl(["編號", "名稱", "賽季欄（只照錄）"], [[a,b,c] for a,b,c,d in v_rows], "sticky"))
    add(p_html(
        f"村莊風格表 {len(data.village)} 筆；村莊建築外觀套裝 {len(data.village_suits)} 套"
        "（沙漠、寒冬、荊棘、海洋、天空）各 38 棟建築外觀，對應村莊風格 201–601；"
        "套裝名稱寫「海洋」，村莊風格寫「海底」，是同一套。"
        "賽季解鎖欄為 1／2／3／5／6–999，沒有對應 4 的套裝。"
        "這張表沒有套裝屬性。逐棟屬性本頁不展開。"
    ))
    add("      <h3>公會堡壘造型</h3>")
    if data.fort:
        fr = data.fort[0]
        add(p_html(
            f"公會堡壘外觀僅 {len(data.fort)} 筆："
            f"{official_term_html(official_text(fr.get('name')))}（品質 {fr.get('quality')}）。"
            f"解鎖說明「{official_term_html(official_raw(fr.get('unlock_dec')))}」。"
            f"解鎖時間為 {e(format_unlock_range(fr.get('unlocktime')))}（只記錄）。"
            f"擁有屬性：{fmt_raw_pairs(parse_pairs(fr.get('attr_own')))}。"
            "醫院容量上限照點數記；傷兵治療速度只記原值。"
            f"使用屬性欄為 {e(str(fr.get('attr_equip')))}，對不上屬性名稱表的編號，本抽取無法對成屬性名稱。"
        ))
    add("    </section>")

    # ----- 介面實例 -----
    add('    <section id="panels">')
    add("      <h2>介面實例</h2>")
    add(p_html(
        "本節數值從遊戲「城堡造型」頁抄錄，是面板紀錄，"
        "不在此把六座畫面全部改寫成表列，也不把表的 level 當成面板星數。"
        "蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪的表列與 0 星／滿 1 星對應，見「城堡造型主表」。"
        "其他城堡不要自行把表上等級當成面板星數。"
        "面板已顯示的百分比或點數，照畫面記錄，不把畫面數字反推成表內原值。"
        "左側心形數字是讚數，不是戰力，不寫進屬性；下文讚數只作對圖註記。"
        "名稱下方的金星是城堡本身星級；技能等級是另一套。"
        "已見多座滿星，不同造型滿星不一定相同，不能把某一座的滿星推成通例。"
    ))
    add(p_html("本篇依面板用字記錄，屬性鍵與 id 對照見資料說明。"))

    add("      <h3>熾火要塞</h3>")
    add(p_html(
        "來源為較早的熾火要塞詳情截圖。此造型滿星就是 1 星，與畫面名稱下方那一顆金色星相符，因此這裡的擁有／使用屬性按滿星記錄。"
        "底部標示「永久」。不同造型滿星不一定相同，仍不能把某一座的滿星推成通例。"
        "本筆截圖未另記讚數。技能等級是另一件事：同一帳號的技能升級畫面為 Lv 0/10，屬性截圖對應的是滿星、技能尚未升級的狀態。"
        "本節仍按當時面板抄錄，不在此對主表改寫。屬性編號與顯示規則見資料說明。"
    ))
    add(_tbl(
        ["欄位", "屬性（介面原文）"],
        [
            [official_term_html(o.own_label), "所有士兵攻擊 +10%"],
            [official_term_html(o.own_label), "所有士兵生命 +10%"],
            [official_term_html(o.own_label), "部族士兵生命 +25%"],
            [official_term_html(o.use_label), "部族士兵攻擊 +15%"],
            [official_term_html(o.use_label), "部族英雄暴擊率 +15%"],
        ],
        "cards", card_title="屬性（介面原文）",
    ))
    add(p_html("同一畫面可見「技能」「外觀套裝」入口，以及底部「永久」「技能」「使用」。底部頁籤與字串一致：城堡造型、城堡護盾、遷城特效等。"))

    add("      <h3>山岳之傲</h3>")
    add(p_html("面板上：滿星 1 顆金星；讚數 11703。技能 Lv 10/10。本節仍按當時面板抄錄，不在此對主表改寫，也不把表上等級當成面板星數。"))
    add(_tbl(
        ["欄位", "屬性（介面原文）"],
        [
            [official_term_html(o.own_label), "所有士兵攻擊 +10%"],
            [official_term_html(o.own_label), "所有士兵生命 +10%"],
            [official_term_html(o.own_label), "聯盟士兵生命 +25%"],
            [official_term_html(o.use_label), "防守時我方損兵比例降低 +5%"],
            [official_term_html(o.use_label), "守城時士兵生命 +30%"],
        ],
        "cards", card_title="屬性（介面原文）",
    ))
    add(p_html(
        "技能 Lv 10/10 與官方技能文案完全一致："
        f"{official_term_html(official_raw('world_skin_skill_231_lv2_10'))}。"
        "使用屬性用「損兵」、技能用「傷兵」，照字分開記，不要合併。"
    ))

    add("      <h3>創世紀</h3>")
    add(p_html(
        "面板上：滿星 2 顆金星；讚數 18990。兩張圖是同一畫面因版面太窄分拍，合在一起才是完整屬性。"
        "共鳴等級 1 已啟動。本節仍按當時面板抄錄，不在此對主表改寫，也不把表上等級當成面板星數。"
    ))
    add(_tbl(
        ["欄位", "屬性（介面原文）", "備註"],
        [
            [official_term_html(o.own_label), "逆克制增傷 +1%", "標共鳴等級1；不要寫成聯盟逆克制增傷那條"],
            [official_term_html(o.own_label), "出征上限 +10", "標共鳴等級1；照畫面記點數"],
            [official_term_html(o.own_label), "所有士兵攻擊 +30%", ""],
            [official_term_html(o.own_label), "所有士兵生命 +90%", ""],
            [official_term_html(o.own_label), "攻擊時敵方損兵比例增加 +25%", ""],
            [official_term_html(o.use_label), "所有士兵攻擊 +15%", ""],
            [official_term_html(o.use_label), "攻擊時敵方損兵比例增加 +10%", ""],
        ],
        "cards", card_title="屬性（介面原文）",
    ))
    add(p_html("共鳴等級 1 的額外使用（所有士兵攻擊 +5%）已在共鳴介面核到，見「共鳴」。"))

    add("      <h3>永恆紀</h3>")
    add(p_html(
        "面板上：名稱下沒有星，並標「永久」；讚數 2294。"
        "目前滿星就是 0 星。"
        "主表雖有這座 1–11 級列，不能把表上等級當成目前可升的星數。"
        "不要推斷以後會不會開放升星。因此共鳴等級 2（兩城都要 1 星）與等級 3（都要 2 星）目前開不到。"
        "同樣因版面太窄分拍兩張，合在一起才是完整屬性。共鳴等級 1 與創世紀相同（目前只開到這一檔）。"
        "本節仍按當時面板抄錄，不在此對主表改寫。"
        "面板 0 星＝表的 level 1 是蛋糕城、飛翔號的對應，不是這座已用面板對過主表。"
    ))
    add(_tbl(
        ["欄位", "屬性（介面原文）", "備註"],
        [
            [official_term_html(o.own_label), "逆克制增傷 +1%", "共鳴等級1，與創世紀相同；不要寫成聯盟逆克制增傷那條"],
            [official_term_html(o.own_label), "出征上限 +10", "共鳴等級1；照畫面記點數"],
            [official_term_html(o.own_label), "所有士兵攻擊 +10%", ""],
            [official_term_html(o.own_label), "所有士兵生命 +30%", ""],
            [official_term_html(o.own_label), "防守時敵方損兵比例增加 +15%", ""],
            [official_term_html(o.use_label), "防守時敵方損兵比例增加 +10%", ""],
            [official_term_html(o.use_label), "所有士兵攻擊 +15%", ""],
        ],
        "cards", card_title="屬性（介面原文）",
    ))

    add("      <h3>天空之城</h3>")
    add(p_html(
        "面板上：滿星 1 顆金星，並標「永久」；讚數 42532。"
        "畫面無技能按鈕，與本抽取沒有技能列相符。"
        "本節仍按當時面板抄錄，不在此對主表改寫，也不把表上等級當成面板星數。"
    ))
    add(_tbl(
        ["欄位", "屬性（介面原文）", "備註"],
        [
            [official_term_html(o.own_label), "所有士兵生命 +50%", ""],
            [official_term_html(o.own_label), "英雄等級上限 +20", "照畫面記點數，不是百分比"],
            [official_term_html(o.use_label), "所有士兵攻擊 +5%", ""],
            [official_term_html(o.use_label), "所有士兵生命 +15%", ""],
        ],
        "cards", card_title="屬性（介面原文）",
    ))

    add("      <h3>水晶聖城</h3>")
    add(p_html(
        "面板上：這是 VIP18 形態；名稱下為灰星，有「升級」按鈕；讚數 146。"
        "滿星就是 1 星，不能再升。材料畫面曾見 0/1。"
    ))
    add(p_html("<strong>取消幻化後</strong>，主頁面的擁有屬性與使用屬性都是空的。"))
    add(p_html(
        f"<strong>幻化中</strong>（畫面使用欄與領域皆標「{official_term_html(o.illusioning)}」）："
        "使用屬性為防守時敵方損兵比例增加 +10%、所有士兵攻擊 +15%，與永恆紀的使用屬性完全相同；擁有欄仍空。"
        "這張自身的擁有欄本來就是空的，所以看不出幻化後留下了什麼擁有屬性；"
        "自身擁有屬性仍保留，見上文「系統機制」。"
    ))
    add(p_html("<strong>隱藏使用屬性</strong>只在升星介面看到，主頁面不列；升到 1 星後，主頁面仍不顯示。"))
    add(p_html(
        "<strong>升星檔。</strong>沒有可停的 1/5、2/5、3/5、4/5 中間檔；一次升級就滿一顆星。"
        "先前那張「升星效果預覽」出現 9%＋1%、23%＋2%，是面板設計不佳，不是 4/5 可停檔，本篇不再按 4/5 中間檔來寫。"
        "也不要把 0 星預覽的 5%＋1%、15%＋2% 讀成下一步只到 6%／17%，或把 5%＋1% 讀成滿星 +6%。"
    ))
    add(_tbl(
        ["檔", "使用屬性", "說明"],
        [
            ["0 星（0/5）", "所有士兵攻擊 +5%、所有士兵生命 +15%", "升星預覽曾見 5%＋1%、15%＋2%；此檔就是 0 星 5%／15%"],
            ["滿 1 星（5/5）", "所有士兵攻擊 +10%、所有士兵生命 +25%", "一次升級即到此檔；滿星就是 1 星，不能再升"],
        ],
        "cards", card_title="檔",
    ))
    add(p_html("這組使用屬性仍按當時面板抄錄，不在此對主表改寫，也不把表上等級當成面板星數。"))
    add("    </section>")

    # ----- 未列入 -----
    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(li_html(
        "本頁已把 68 組的擁有／使用曲線寫入「城堡造型主表」（只有一列的也寫那一列）。"
        "不能把表的 level 當成面板星數。0 星＝level 1 只鎖定四座，不是 68 組通例。"
        "已見面板的六座仍寫在「介面實例」。共鳴三檔已在面板驗證，見「共鳴」；仍不是創世紀或永恆紀的基礎擁有／使用屬性或滿星屬性。"
    ))
    add(li_html(
        "護盾、效果、遷城、光環、翅膀、行軍、共鳴已在本頁另節登錄。"
        "不把尚未用面板核對的項目寫成結論。"
    ))
    add(li_html("村莊風格 190 棟建築外觀的逐棟屬性（這張套裝表沒有屬性）。地脈建築造型與 DIY 裝飾套裝不列入本頁主體。"))
    add(li_html(
        "禮包文案裡沒有數值的屬性方向，不能當成滿星屬性。"
        "已核到的方向只有：黃金獅鷲禮包說明寫「提供大量聯盟士兵攻擊屬性」（另有字串寫「提供大量聯盟進攻屬性」）；"
        "鍵名含藍晶堡拼音的字串寫「更改城市外觀，並可提供大量冒險減傷屬性！」；"
        "聖誕城堡與夢幻之城寫士兵生命與帶兵上限；天空之城寫士兵攻擊和生命，並提升英雄等級上限"
        "（天空之城的面板數值見介面實例，不能把禮包文案本身當成滿星表）。"
    ))
    add("</ul>")
    add("    </section>")

    # ----- 資料說明 -----
    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<p>以下是整理用註記，查星數與屬性可略過。</p>")
    add(p_html(
        "本輪可見正文移入：預設城堡的 sex／hide 欄（兩組五列、表上等級 1–5；其中一組為目錄預設，另一組名稱相同；"
        "level 1 的 hide 為 -1，level 2–5 為 1；兩組 sex 分別為 1 與 2）只抄表，不把這些欄寫成面板性別或顯示名稱。"
        "表上只有一檔的城堡：不敗榮耀兩組為 quality 5／hide=1 與 quality 4／hide=-1，名稱鍵皆為 skin_name_111，目錄只列 id 111；"
        "黃金獅鷲為 hide=1，與黃金獅鷲-戰鬥為獨立造型。主表屬性原格式為「屬性id|數值」，例如 1043|2000、19|500、10103|500；"
        "可見表改寫成官方屬性名與數值（或百分比加原值），對照仍以抽取為準。"
        "介面實例的屬性 id 與 show_type：熾火要塞、山岳之傲、創世紀、永恆紀、天空之城各列見本頁先前對照；"
        "「逆克制增傷」官方鍵是 <code>attribute_name_damage</code>，不要逕指成 3029（那是聯盟逆克制增傷）。"
        "共鳴 buff_key 為 jbms_csj1／2／3；領域與技能 2 顆星檔鍵為 star10 系列。"
        "中段提到的資料表檔名包括 world_skin_goods.json、world_skin_suit_collection.json、"
        "world_skin_suit_collection_rewa.json、world_skin_suit_collect_fashion.json、world_skin_effect.json、"
        "world_skin_goods 採集物、troop_skin.json、map_march.json、skin.json、village_style.json、"
        "citybuilding_skin_suit.json、alliance_fort_skin.json、attribute.json、goods.json。"
        "星紀元效果列的參數欄與升級範圍欄原值（含 311|327 這類寫法）只抄表，對照見抽取；升級範圍欄點名創世紀、永恆紀。中段面板抄錄日期為 2026-11-22（香港時間）；頁尾資料截至 2026-11-23（香港時間）。"
        "揚帆啟航護盾表 id 3008 官方名鍵為 world_shields_name_3009（洋流環繞）；果香帷幕為表 id 3007、鍵 world_shields_name_3008。"
        "水晶聖城 hide 在 level 1 為 1、level 2–6 為 -1。山岳之傲「守城時士兵生命」列 id 1000104，鍵 attribute_name_1010104。"
    ))
    add(p_html(
        "鎖定來源（可略過）：2026-11-22／23 前服面板與玩家核對。"
        "蛋糕城、飛翔號：面板 0 星＝表的 level 1，滿 1 星＝表的 level 6。"
        "美味史萊姆、夢幻摩天輪亦作 0 星＝level 1：依據是主表六檔、使用屬性整條曲線不變，且滿 1 星已對上 level 6，"
        "不是另一張 0 星面板截圖；不是 68 組通例。"
        "不能把創世紀或永恆紀的表上等級 1／6／11 對成面板星數。永恆紀目前滿星就是 0 星。"
        "高級造型也會覆蓋使用屬性、幻化後擁有屬性仍保留、須同時擁有創世紀與永恆紀才會啟動共鳴、"
        "目前只開到共鳴等級 1、這四座升級用道具 290 等，已寫入正文。"
    ))
    add(p_html(_published_links_html(terms) + "不在本頁展開。"))
    add(p_html(
        "介面六個欄位鍵是 <code>City_Skin_1</code>–<code>City_Skin_6</code>。"
        "對應說明鍵為 <code>City_Skin_1_dec</code>（本抽取未見 2–6 的 <code>_dec</code>）。"
        "擁有／使用介面鍵是 <code>UI_CitySkin_001</code>／<code>002</code>。"
        f"光環頁鍵是 <code>world_skin_halo_tab</code>，擁有／使用為 <code>world_skin_halo_own_prop</code>／<code>world_skin_halo_use_prop</code>。"
        "影響力分類鍵是 <code>influence_level_19</code>／<code>20</code>／<code>21</code>。"
        "覆蓋提示鍵是 <code>UI_CitySkin_007</code>；屬性加總標題鍵是 <code>world_skin_prop_sum_title</code>。"
        "幻化相關鍵：<code>world_skin_01_01</code>、<code>info_title_13020</code>／<code>info_text_13020</code>、"
        "<code>UI_Title_030</code>／<code>info_text_13021</code>（沒有 <code>info_title_13021</code>）、"
        f"<code>world_skin_01_03</code>。"
        "限時屬性提示鍵是 <code>info_title_13004</code>／<code>info_text_13004</code>；賽季字串鍵是 <code>world_skin_01_07</code>–<code>10</code>。"
        "領域介面鍵是 <code>world_skin_01_02</code>、<code>castle_skill_ui_7</code>／<code>8</code>；"
        "領域說明鍵是 <code>skin_territory_311</code>／<code>skin_territory_311_star10</code>、"
        "<code>skin_territory_327</code>、<code>skin_territory_2011</code>／<code>skin_territory_2011_extra</code>。"
        "共鳴官方說明鍵是 <code>eternity_gm11</code>。"
    ))
    typ = data.table_meta["effect_type_counts"]
    add(p_html(
        f"護盾、效果、遷城、光環的列都在 <code>world_skin_effect.json</code>"
        f"（{data.table_meta['effect_rows']} 列，依 <code>type</code> 1–4 分成四個獨立節），"
        f"行軍見 <code>world_skin_march.json</code>（{data.table_meta['march_rows']} 列），"
        f"翅膀見 <code>world_skin_wing.json</code>（{data.table_meta['wing_rows']} 列），"
        f"共鳴見 <code>world_skin_link.json</code>（{data.table_meta['link_rows']} 列）。"
        "主表 68 組幾乎都沒有欄位指向這四張表的 id。"
        "<code>goods.json</code> 在本抽取是骨架表（各欄值等於欄位序號），不用來為 <code>source_goods</code> 取物品名。"
        f"主動技能寫在 <code>world_skin_skill.json</code>（{data.table_meta['skill_rows']} 筆），"
        "以 <code>resetGroup</code> 對應造型 id（美味史萊姆為 3171／3172，城堡效果「怦然心動」為 2016）。"
        "<code>resetType</code> 全部為 1。<code>skill_group</code>：1 為戰鬥增益；1000 為在身邊生成可採集物"
        "（幸運火雞、泡泡霜熊，以及美味史萊姆的自領列）；-1 為美味史萊姆的贈送列，以及奇幻舞會（其技能文案是士兵士氣，不是贈禮）；"
        "0 為表演（怦然心動，屬城堡效果）。"
        "技能升級表是 <code>world_skin_skill_level_up.json</code>，只有一組 <code>skill_level_group=1</code>、10 級消耗，材料為道具 290；"
        "技能升級介面字串鍵是 <code>world_skin_skill_level_up_4</code>。強化技能說明鍵帶 <code>_lv2</code>。"
        "城堡本身的升級消耗見主表 <code>cost</code>（level 1 為空；其後各 level 有消耗）。"
        "可贈送列見 <code>activity_skin_send.json</code>：春日小屋 315、火砲要塞 221、蛋糕城 301、南瓜小鎮 308；規則鍵 <code>castle_gift7</code>。"
    ))
    add(p_html(
        "主表欄位包括 <code>id</code>、<code>group</code>、<code>level</code>、<code>quality</code>、"
        "<code>attr_own</code>（擁有屬性）、<code>attr_equip</code>（使用屬性）；"
        "另有 <code>attr_own_f</code>／<code>attr_equip_f</code>（蛋糕城、飛翔號與對應欄相同）、"
        "<code>cost</code>、<code>fightforce</code> 等。"
        "屬性格式為 <code>\"屬性id|數值\"</code> 陣列，例如 <code>\"10104|4000\"</code>。"
        "另有 <code>attr_own_season</code>／<code>attr_equip_season</code>／<code>attr_own_kvk</code>／<code>attr_equip_kvk</code> 等欄；"
        "蛋糕城、飛翔號這些欄為空。本頁不展開其他造型的賽季加成分。"
        "表裡沒有 level=0。<code>level</code> 取值 1–11：36 組只有 level 1；27 組為 1–6；"
        "group 0、1（預設「城堡」）為 1–5；group 171（賢者之城）為 1–3；"
        "group 311（創世紀）、327（永恆紀）為 1–11。"
        "主表各組列 id 見各座說明句；本頁主表不再單列「列 id」欄。"
        "不依 <code>unlocktime</code>／<code>unlock_season</code>／伺服器欄位標未開放；表上沒有「已推出」欄。"
        "401–406 的名稱與若干賽季稱呼相近，但本抽取沒有把它們綁到 <code>unlock_season</code> 的表，只記名稱，不推斷開放賽季。"
    ))
    add(p_html(
        "屬性名稱優先用 <code>attribute_name_{id}</code>。"
        f"「{official_term_html(o.damage_name)}」的字串鍵是 <code>attribute_name_damage</code>，不要逕指成數字 id"
        f"（<code>attribute_name_3029</code> 是「{official_term_html(o.alliance_damage)}」）。"
        "<code>show_type=2</code> 的<strong>表內數值</strong>只記原值，不自行把全書改成百分比換算規則；"
        "技能說明若已寫成百分比，照錄官方文案。面板已顯示的百分比或點數，照畫面記錄，不把畫面數字反推成表內原值。"
        "主表曲線的百分比寫法跟已鎖定的面板相同（<code>show_type=2</code>：4000→40%、1000→10%、500→5%、"
        "1500→15%、2000→20%、2500→25%、300→3%、200→2%、550→5.5%、650→6.5%），並並陳表內原值；"
        "出征上限（1019，<code>show_type=1</code>）、英雄等級上限（1098，<code>show_type=1</code>）等照點數記。"
        "這不是改寫全書換算規則。"
        "左側心形數字不是本表的 <code>fightforce</code>。"
        "下列 id 的 <code>name</code> 鍵不是 <code>attribute_name_{id}</code>，仍用該鍵的官方名："
        "<code>1000104</code>「守城時士兵生命」（鍵 <code>attribute_name_1010104</code>）；"
        "<code>10188</code>「士兵士氣」（鍵 <code>attribute_name_10088</code>）；"
        "<code>21007</code>／<code>21008</code> 為「隊伍英雄為同一陣營時，士兵攻擊額外提升／士兵生命額外提升」"
        "（鍵 <code>attribute_name_20007</code>／<code>attribute_name_20008</code>）。"
        "「守城時士兵生命」對得上字串鍵 <code>attribute_name_1010104</code>（<code>show_type=2</code>）。"
        "<code>attribute.json</code> 出現 id 與 <code>name</code> 交叉：id 1000104（以及 1000108）的 <code>name</code> 為 <code>attribute_name_1010104</code>；"
        "id 1010104 的 <code>name</code> 為 <code>attribute_name_1000104</code>（「守城時生命」）。"
        "本篇依面板用字與字串鍵記錄，不把交叉的列逕指為唯一來源。"
        "飛翔號官方屬性 21023／21024 為 <code>show_type=2</code>。"
        "VIP 相關鍵：<code>attribute_name_1142</code>、<code>exchange_name_vip18</code>；水晶戰車為 <code>skin_name_1016</code>／<code>skin_desc_1016</code>；"
        "可贈送與材料說明見 <code>goods_desc_290</code>／<code>313</code>／<code>314</code>／<code>305</code>。"
        "博克島、霍金斯實驗室仍缺 <code>skin_name</code> 鍵，名稱取自說明文"
        "（<code>crossover_rss_name1</code>、<code>strangerthings_skin_name_01</code>）。"
        "預設城堡名稱鍵是 <code>skin_name_001</code>。"
    ))
    add(p_html(
        "共鳴表 <code>world_skin_link.json</code> 的 <code>skin</code> 為 <code>311|327</code>，<code>linklevel</code> 1–3，"
        "<code>buff_key</code> 分別為 <code>jbms_csj1</code>／<code>csj2</code>／<code>csj3</code>；"
        "這張表的 <code>level</code> 在三檔分別為 1、6、11。不能把這裡的 <code>level</code> 讀成面板星數。"
        "第十版已把其餘各組的主表曲線寫入，那些組仍尚未用面板核 0 星／滿星。"
        "來源包名、列數與 id 對照如下。"
    ))
    add(p_html(_footer_text(data)))
    add("<ul>")
    add(li_html(
        f"<strong>城堡造型主表</strong>來源是 LocalLow 包 <code>{CASTLE_DATA_PACK}</code> 的 <code>world_skin.json</code>"
        f"（{data.table_meta['skin_rows']} 列、{data.table_meta['skin_groups']} 組），"
        "不是稍早同一日那份沒有此主表的 StreamingAssets 抽取。"
        "蛋糕城、飛翔號滿 1 星仍對表的 level 6（id 3012、3022），0 星對 level 1（id 301、302）；"
        "美味史萊姆、夢幻摩天輪滿 1 星對 level 6（id 3172、3182），0 星對 level 1（id 317、318）。"
        f"<code>world_skin_goods.json</code> 仍是 {data.table_meta['goods_rows']} 筆，是技能生成的採集物，不是升級材料表。"
    ))
    leftover_txt = "、".join(
        f"{sid} {official_term_html(name)}（<code>skin_name_{sid}</code>；{official_term_html(desc)}）"
        for sid, name, desc in data.leftover
    )
    add(li_html(f"字串有但主表沒列的造型名稱鍵：{leftover_txt}。不當成本表列，不編造列。"))
    add(li_html(
        "仍待補、本頁不寫成結論的項目："
        "其餘各組尚未用面板核對 0 星／滿星；蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪的升級材料在 <code>goods_desc_290</code> 名單仍未列；"
        "博克島、霍金斯實驗室仍缺 <code>skin_name</code> 鍵；406「蒼穹／滄穹」字串差異仍在；"
        "時尚值與套裝 <code>reward</code> 的道具名稱；表上仍無 VIP18 造型名稱鍵；"
        "其餘尚未逐座點名、也未見面板的造型滿星上限；其他造型是否也能幻化。"
        "共鳴 1／6／11 在創世紀／永恆紀對應幾星（面板條件已見「共鳴」，不是把表 <code>level</code> 換成星數）；"
        "光環 Lv 與升級怎麼顯示；<code>territory_range</code> 4／5 是否就是文案的 9×9／11×11；"
        "淨月蓮官方「3 格」對表上 <code>allianceShieldRange=4</code>；翅膀 <code>cost=\"1\"</code> 與位置方案的實際操作；"
        "<code>source_goods</code> 對應哪件物品。"
        "行軍表內仍缺 1018、1020–1022、1028（1028 只有官方字串「地心專車」）；護盾表缺 3009；遷城表缺 4010；光環表缺 5003、5006；"
        "字串有 36003 閃電衝擊、36006 缺號，本表 type 4 沒有對應列。"
    ))
    for item in data.verifications.get("chapter_diffs") or []:
        add(li_html("與第 17 章的差異：" + H(item, terms)))
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {CASTLE_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_castle_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _p_md(text: str) -> str:
    return text


def render_markdown(data: TablesData) -> str:
    o = data.official
    attrs = data.attrs
    lines: list[str] = []
    add = lines.append
    add("# 城堡外觀總表")
    add("")
    add(LEDE)
    add("")
    add(_published_links_md())
    add("")
    add("## 閱讀說明")
    add("")
    add("- **本頁主體是城堡造型**（介面欄位「城堡造型」）。同一套「城堡外觀」介面還有城堡效果、行軍造型、城堡護盾、城堡翅膀、遷城特效與光環造型；那些相鄰欄位另節登錄，不是城堡造型主體。城鎮裝飾與地脈建築造型、DIY 裝飾套裝見[裝飾物總表](decorations.html)，不列入本頁主體。介面欄位鍵 `City_Skin_1` 見資料說明。")
    add(f"- 城堡造型主表是 LocalLow 包 `{CASTLE_DATA_PACK}` 的 `world_skin.json`（{data.table_meta['skin_rows']} 列、{data.table_meta['skin_groups']} 組）。**不能把表的 `level` 當成面板星數。** **玩家確認**（2026-11-23）：面板 0 星＝表的 level 1；當初確認對象是蛋糕城、飛翔號。美味史萊姆、夢幻摩天輪亦鎖定 0 星＝level 1（依主表 level 1 加已對上的滿 1 星＝level 6，不是另一張 0 星面板截圖），不是 68 組通例。")
    add("- 介面實例已有熾火要塞、山岳之傲、創世紀、永恆紀、天空之城、水晶聖城。各座滿星不一定相同，不能把某一座的滿星推成通例。")
    add(f"- 不依 `unlocktime`／`unlock_season`／伺服器欄位標未開放。屬性名稱優先用 `attribute_name_{{id}}`。「{o.damage_name}」的字串鍵是 `attribute_name_damage`，不要逕指成數字 id（`attribute_name_3029` 是「{o.alliance_damage}」）。`show_type=2` 的表內數值只記原值；面板百分比照畫面記錄。主表曲線的百分比寫法跟已鎖定面板相同並並陳原值，不是改寫全書換算規則。左側心形數字是讚數，不是戰力。")
    add("")
    add("## 範圍與資料缺口")
    add("")
    add("遊戲介面把「城堡外觀」分成六個欄位（`City_Skin_1`–`6`）：")
    add("")
    scope = []
    labels = {1: "獲得後有「擁有屬性」；使用後另有「使用屬性」。說明文 City_Skin_1_dec 仍寫「裝備屬性」，與介面標籤不一致",
              2: "本抽取未見 City_Skin_2_dec。名稱與屬性見「城堡效果／特效」",
              3: "本抽取未見 City_Skin_3_dec。名稱與屬性見「行軍造型」",
              4: "本抽取未見 City_Skin_4_dec。名稱與屬性見「城堡護盾」",
              5: "本欄沒有 City_Skin_5_dec。名稱與屬性見「城堡翅膀」",
              6: "本抽取未見 City_Skin_6_dec。名稱與屬性見「遷城特效」"}
    for i in range(1, 7):
        scope.append([str(i), o.city_skin[i], labels[i]])
    add(_md(["欄位", "名稱", "說明（介面字串）"], scope))
    add("")
    add(f"另外還有「{o.halo_tab}」頁。影響力分類把「{o.influence[19]}」「{o.influence[20]}」「{o.influence[21]}」分成三項。護盾、效果、遷城、光環都在 `world_skin_effect.json`（{data.table_meta['effect_rows']} 列），行軍 {data.table_meta['march_rows']} 列，翅膀 {data.table_meta['wing_rows']} 列，共鳴 {data.table_meta['link_rows']} 列。不要把面板「行軍造型 20%」強行對成其他表的屬性列。")
    add("")
    add("## 系統機制（資料表、官方字串與已確認的面板／玩家說法）")
    add("")
    add(f"- **獲得與使用分兩套屬性。** 介面標籤為「{o.own_label}」「{o.use_label}」。說明文寫「{o.city_skin_1_dec}」。屬性加總標題為「{o.prop_sum}」。")
    add(f"- **高級造型會覆蓋初級造型的擁有屬性。** `{o.cover_tip}`。原文只提擁有屬性。**玩家確認**：高級造型也會覆蓋初級造型的「使用屬性」。兩者並陳。")
    add(f"- **{o.illusion}**。官方說明：{o.illusion_text.replace(chr(10), '／')}。特效幻化標題為「{o.effect_illusion_title}」：{o.effect_illusion_text.replace(chr(10), '／')}。**玩家確認**：幻化後自身「擁有屬性」仍保留。2026-11-22 前服面板目前只在水晶聖城見到「幻化」與「領域（幻化中）」按鈕，先依畫面記，不要寫成表證的唯一描述。")
    add("- **主動技能**寫在 `world_skin_skill.json`。升級城堡與升級技能是兩件事。`world_skin_skill_level_up.json` 材料為道具 290。蛋糕城、飛翔號 level 2–6 皆為道具 290 ×20；`goods_desc_290` 名單仍未列，與玩家確認並陳。")
    add(f"- **共鳴。** 官方 `eternity_gm11` 為「{official_text('eternity_gm11')}」，沒有寫死是哪兩座。**玩家確認**：須同時擁有創世紀與永恆紀才會啟動。表 `skin` 為 `311|327`，`level` 為 1、6、11，不能讀成面板星數。0 星＝level 1、滿 1 星＝level 6 只鎖定蛋糕城、飛翔號。**玩家確認**目前只開到共鳴等級 1；永恆紀目前滿星就是 0 星（「the max is 0 star now」）。")
    add("- **滿星不是全部 1 星。** 熾火要塞、山岳之傲、天空之城、水晶聖城滿星都是 1 顆金星；蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪當時亦為滿星 1 星。創世紀滿星 2 顆金星；永恆紀目前滿星就是 0 星。**玩家確認**（2026-11-22）他手上其他能確認的可升星城堡滿星也都是 1 星，不推成 68 組通例。")
    add("")
    add("## 城堡造型主表（`world_skin.json`）")
    add("")
    add(f"本節依 LocalLow 包 `{CASTLE_DATA_PACK}` 的 `world_skin.json` 抄錄。主表 {data.table_meta['skin_rows']} 列、{data.table_meta['skin_groups']} 組。**不能把表的 `level` 當成面板星數。** 左側心形數字是讚數，不是 `fightforce`。字串有但本表沒列的 334 {o.leftover_334}、407 {o.leftover_407}，不當成本表列。")
    add("")

    def add_locked_md(gid, full_txt, zero_txt, zero_kind, mid_note=False):
        g = data.groups[gid]
        add(f"### {g.name}（group {gid}，`{g.name_key}`）")
        add("")
        extra_equip = "，與蛋糕城的使用屬性相同" if gid == 302 else ""
        add(
            f"六列，level 1–6；id 依序為 {_ids_list(g.rows)}。"
            f"`attr_equip` 六階完全相同{extra_equip}；`attr_own` 隨 level 遞增。"
            + _cost_sentence(g.rows)
            + _quality_sentence(g.rows)
            + (
                "本節保留已確認的 0 星與滿 1 星，並補上 level 2–5 的主表數字；中間檔未用面板核過。"
                "0 星＝level 1 的依據是：這座與蛋糕城、飛翔號一樣都是主表 level 1–6，使用屬性整條曲線不變，"
                f"滿 1 星已用面板對上 level 6（id {g.rows[-1].sid}），因此表上 level 1 就是 0 星檔；"
                "不是另一張 0 星面板截圖，也不是 68 組通例。"
                if mid_note else ""
            )
        )
        add("")
        add(f"**已確認的滿 1 星（2026-11-22 玩家面板，不得改掉已確認的數字）：** {full_txt}")
        add("")
        if zero_kind == "panel":
            add(f"**已確認的 0 星（2026-11-23 玩家確認，面板 0 星＝表的 level 1；不是表上的欄名）：** {zero_txt}")
        else:
            add(f"**已確認的 0 星（2026-11-23；依據是主表 level 1，加上已用面板對上的滿 1 星＝level 6，不是另一張 0 星面板截圖）：** {zero_txt}")
        add("")
        if gid == 318:
            add("使用屬性（六階皆同）：減傷 +5%（屬性 19，`19|500`，不是普攻減傷 26）、所有士兵攻擊 +5%（`10103|500`）。")
            add("")
        else:
            up = _use_prose(g.rows, attrs)
            if up:
                add(up.replace("使用屬性（各階皆同）", "使用屬性（六階皆同）"))
                add("")
        if gid == 302:
            add("官方屬性名：21023 為「" + attr_label(21023, attrs) + "」；21024 為「" + attr_label(21024, attrs) + "」（`show_type=2`）。")
            add("")
        built = _curve_table(g.rows, attrs)
        if built:
            cols, body, _m = built
            notes = []
            for r in g.rows:
                if r.level == 1:
                    if mid_note:
                        notes.append("與已確認的 0 星一致（依據是主表 level 1 加已對上的滿 1 星＝level 6，不是另一張 0 星面板截圖）")
                    else:
                        notes.append("與已確認的 0 星面板一致（玩家確認：面板 0 星＝表的 level 1）")
                elif r.level == 6:
                    notes.append("與已確認的滿 1 星面板一致")
                elif mid_note:
                    notes.append("中間檔，未用面板核過")
                else:
                    notes.append("")
            add(_md(cols + ["備註"], [row + [notes[i]] for i, row in enumerate(body)]))
            add("")

    add_locked_md(301, PANEL_CAKE_FULL, PANEL_CAKE_ZERO, "panel")
    add_locked_md(302, PANEL_FLY_FULL, PANEL_FLY_ZERO, "panel")
    add_locked_md(317, PANEL_SLIME_FULL, PANEL_SLIME_ZERO, "infer", mid_note=True)
    add_locked_md(318, PANEL_WHEEL_FULL, PANEL_WHEEL_ZERO, "infer", mid_note=True)

    add(
        "以下為其餘 64 組的主表擁有／使用曲線。一律只抄表上 `level` 與 `attr_own`／`attr_equip`，"
        "**不能把表的 `level` 當成面板星數**。"
        "0 星＝level 1 只鎖定蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪，不是 68 組通例。"
        "已有介面實例的組（熾火要塞、山岳之傲、創世紀、永恆紀、天空之城、水晶聖城）面板數字仍以「介面實例」為準，"
        "此處不把某一列寫成已用面板核過的 0 星或滿星。"
        "創世紀目前最高 2 星、永恆紀目前最高 0 星仍保留，不把他們的 level 1／6／11 寫成面板幾星。"
        f"字串有但本表沒列的 334 {official_text('skin_name_334')}、407 {official_text('skin_name_407')}，不當成本表列。"
    )
    add("")
    add(
        "屬性名稱用官方字串。下列 id 的 `name` 鍵不是 `attribute_name_{id}`，仍用該鍵的官方名，並標 id："
        "`1000104`「守城時士兵生命」（鍵 `attribute_name_1010104`，id 與 `name` 交叉見介面實例）；"
        "`10188`「士兵士氣」（鍵 `attribute_name_10088`）；"
        "`21007`／`21008` 為「隊伍英雄為同一陣營時，士兵攻擊額外提升／士兵生命額外提升」"
        "（鍵 `attribute_name_20007`／`attribute_name_20008`）。"
        "「逆克制增傷」不要逕指成單一數字 id；本節這批曲線未出現此鍵。"
        "`show_type=1` 的出征上限（1019）、英雄等級上限（1098）等照點數記。"
        "左側心形數字不是本表的 `fightforce`，不寫進屬性。"
        "若干組另有 `attr_own_season`／`attr_own_kvk` 等欄，本版仍不展開賽季／KVK 加成分。"
    )
    add("")

    add("### 預設城堡（group 0、1，`skin_name_001`）")
    add("")
    add("兩組都叫「城堡」，各有五列、level 1–5，擁有／使用皆空。目錄所列預設造型 id 1 對應 group 1；group 0 是主表多出來的一組。本節只抄表，不把 `sex` 或 `hide` 寫成面板上的性別或顯示名稱。")
    add("")
    def_rows = []
    for gid in (0, 1):
        for r in data.groups[gid].rows:
            def_rows.append([str(gid), str(r.level), str(r.sid), str(r.sex), str(r.hide), "（空）", "（空）"])
    add(_md(["組", "表 level", "列 id", "sex", "hide", "擁有", "使用"], def_rows))
    add("")

    def add_group_md(gid, level="###"):
        g = data.groups[gid]
        add(f"{level} {g.name}（group {gid}，`{g.name_key}`）")
        add("")
        if gid == 171:
            add("三列，level 1–3；id 依序為 171、172、173。" + _quality_sentence(g.rows) + _cost_sentence(g.rows) + "`hide` 在 level 1–3 為 1。本節只抄表，不是已用面板核過 0 星或滿星。")
        elif gid == 311:
            add("十一列，level 1–11；id 依序為 " + _ids_list(g.rows) + "。" + _quality_sentence(g.rows) + _cost_sentence(g.rows) + "已鎖定：滿星為 2 顆金星（前服面板＋玩家確認）。**不要把表的 level 1／6／11 寫成面板幾星**。本節只抄表。")
        elif gid == 327:
            add("十一列，level 1–11；id 依序為 " + _ids_list(g.rows) + "。" + _quality_sentence(g.rows) + _cost_sentence(g.rows) + "已鎖定：名稱下無星；玩家確認目前滿星就是 0 星（「the max is 0 star now」）。**不能把表的 `level` 當成目前可升的星數**。本節只抄表。")
        else:
            add(_standard_group_prose(g, False, attrs, []))
        add("")
        up = _use_prose(g.rows, attrs)
        if up:
            add(up)
            add("")
        op = _own_prose(g.rows, attrs)
        if op and (gid in (171, 327) or _own_constant(g.rows)):
            add(op)
            add("")
        built = _curve_table(g.rows, attrs)
        if built:
            cols, body, _m = built
            add(_md(cols, body))
            add("")

    add_group_md(171)
    add_group_md(311)
    add_group_md(327)
    add("### 其餘 level 1–6 組")
    add("")
    add("下列各組都是主表 level 1–6。只抄表，不是已用面板核過 0 星或滿星。水晶聖城沒有可停的 1/5–4/5 中間檔，一次升級就滿一顆星；level 2–5 只是表列。")
    add("")
    for gid in CURVE_16_ORDER:
        add_group_md(gid, "####")

    add("### 只有 level 1 的組")
    add("")
    add("下列 36 組在主表都只有一列。不敗榮耀有兩組（group 110 為 id 111、`hide=1`；group 111 為 id 112、`hide=-1`），目錄只列 id 111。黃金獅鷲與黃金獅鷲-戰鬥是兩個獨立造型。博克島、霍金斯實驗室仍缺 `skin_name` 鍵，名稱用已鎖定的面板名稱。")
    add("")
    l1 = []
    for gid in LEVEL1_ORDER:
        g = data.groups[gid]
        r = g.rows[0]
        note = g.name_note or ""
        if gid == 331:
            note = f"attr_own_f 為 {fmt_curve_pairs(r.own_f, attrs)}（僅此座擁有欄兩組不同）"
        elif gid == 406:
            note = "面板與永久名稱鍵為蒼穹雲都；說明與限時名稱／說明仍作滄穹雲都，並陳"
        l1.append([
            str(gid), g.name, str(r.sid), str(r.quality if r.quality is not None else EMPTY),
            fmt_curve_pairs(r.own, attrs), fmt_curve_pairs(r.equip, attrs), note,
        ])
    add(_md(["group", "名稱", "列 id", "quality", "擁有屬性", "使用屬性", "備註"], l1))
    add("")

    add("## 升級與升星材料")
    add("")
    up_rows = []
    for gid in (290, 314, 305, 313):
        name, desc = o.goods[gid]
        up_rows.append([str(gid), name, desc.replace("\n", "／")])
    add(_md(["道具", "名稱", "用途（道具說明原文）"], up_rows))
    add("")
    su_rows = []
    total = 0
    for r in data.skill_level_up:
        cost = parse_cost(r.get("cost"))
        qty = cost[0][2] if cost else 0
        total += qty
        su_rows.append([str(r.get("level")), str(qty), str(r.get("skill_quality"))])
    add("技能 1–10 級消耗（`world_skin_skill_level_up`，道具 290）：")
    add("")
    add(_md(["技能等級", "消耗 290", "skill_quality"], su_rows))
    add("")
    add(f"合計 {total} 張城堡設計圖（只計這張技能升級表）。")
    add("")
    add(f"現行 `goods_desc_314` 為：{o.goods[314][1].replace(chr(10), '／')}。第 17 章此處仍按較早五座名單書寫（沒有火砲要塞）；本頁改引現行官方字串。")
    add("")
    add("**玩家確認**（2026-11-22）：蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪都用城堡設計圖（290）升級。`goods_desc_290` 的名單仍未列這四座。蛋糕城／飛翔號主表 `cost` 亦為 290×20，並陳。`world_skin_goods.json` 仍只有 3 筆，是技能生成的採集物，不是升級材料表。")
    add("")

    add("## 城堡造型目錄")
    add("")
    add("博克島、霍金斯實驗室沒有 `skin_name` 鍵；**玩家確認**前服面板亦用這兩個名稱。id 412–414 是南瓜小鎮的限時道具，不是獨立永久造型。巨蟹沙城、南瓜小鎮、天空之城在本抽取沒有主動技能列，已由技能表確認；天空之城前服面板亦無技能按鈕。")
    add("")
    up_map = _goods_upgrade_map(o)
    dir_rows = []
    for sid in DIRECTORY_IDS:
        if sid == 1:
            g = data.groups[1]
        elif sid == 111:
            g = data.groups[110]
        else:
            g = data.groups.get(sid)
        name = g.name if g else official_text(f"skin_name_{sid}")
        desc = official_raw(g.rows[0].desc_key) if g and g.rows[0].desc_key else official_raw(f"skin_desc_{sid}")
        if sid == 1:
            diamonds = EMPTY
        elif sid == 312:
            diamonds = "說明未寫"
        else:
            diamonds = parse_repeat_diamonds(desc)
        dir_rows.append([
            str(sid), name, _skill_dir_label(sid, data), up_map.get(sid, EMPTY), diamonds,
            DIRECTORY_NOTES.get(sid, ""),
        ])
    add(_md(["id", "名稱", "技能", "升級材料（說明名單）", "重複獲得", "備註"], dir_rows))
    add("")
    add(f"以上永久造型（含預設、不含 412–414）共 {len(DIRECTORY_IDS)} 座。**玩家確認**：VIP18 先拿到水晶聖城，再用 313 升成 VIP20 形態；表上沒有 VIP18 造型名稱鍵，並陳，不把「VIP18=水晶聖城」寫成表證。")
    add("")

    add("## 城堡技能（詳細效果）")
    add("")
    add("技能說明直接引用官方字串（遊戲已寫成百分比處，照錄）。")
    add("")
    add("### 有 1–10 級的技能")
    add("")
    for sid, label in ((211, "熾火要塞"), (231, "山岳之傲"), (241, "盾貝城")):
        rows = data.skills_by_reset.get(sid) or []
        base = next((r for r in rows if r.skill_level == 0 and "lv2" not in r.desc_key), None)
        up = next((r for r in rows if r.skill_level == 0 and "lv2" in r.desc_key), None)
        leveled = [r for r in rows if r.skill_level >= 1]
        add(f"**{label}（{sid}）**")
        add("")
        if base:
            add(f"- 基礎（每日 {base.reset_times} 次）：{base.desc}")
        if up:
            add(f"- 升級後（每日 {up.reset_times} 次）：{up.desc}")
        add("")
        if leveled:
            lv_rows = ([["0（升級後）", up.desc]] if up else []) + [[str(r.skill_level), r.desc] for r in leveled]
            add(_md(["技能等級", "效果（官方說明）"], lv_rows))
            add("")
    add("### 只有基礎或基礎＋強化的技能")
    add("")
    basic_order = (
        (213, "奪魄聖殿"), (271, "混亂之塔"), (306, "奇幻舞會"), (307, "協奏"),
        (310, "鋼鐵元帥"), (311, "創世紀"), (313, "冰雪王國"), (318, "夢幻摩天輪"),
        (321, "晶角獸城"), (323, "深海王庭"), (324, "魔龍寶庫"), (326, "閃耀球場"),
        (327, "永恆紀"), (329, "DJ·喵喵"), (330, "霍金斯實驗室"), (333, "幻夜之曲"),
    )
    b_rows = []
    for sid, label in basic_order:
        for r in data.skills_by_reset.get(sid) or []:
            if r.skill_level:
                continue
            stage = "基礎"
            if "star5" in r.desc_key:
                stage = "鍵名 star5"
            elif "star10" in r.desc_key:
                stage = "鍵名 star10"
            elif "lv2" in r.desc_key:
                stage = "強化"
            b_rows.append([label, stage, r.desc, str(r.reset_times)])
    add(_md(["造型", "階段", "效果（官方說明，已去色碼）", "每日"], b_rows))
    add("")
    add("**玩家確認／前服面板**（2026-11-22）：夢幻摩天輪當時開到的技能畫面與升級檔 `world_skin_skill_318_lv2` 完全一致：減傷 +15%、士兵生命 +120%，持續 20 分鐘，每日 3 次。不要把創世紀鍵名 star5／star10 讀成滿星至少 5 星或 10 星。")
    add("")
    add("### 生成物與贈禮技能")
    add("")
    for sid, label in ((309, "幸運火雞"), (322, "泡泡霜熊")):
        add(f"**{label}（{sid}）**")
        add("")
        for r in data.skills_by_reset.get(sid) or []:
            stage = "強化" if "lv2" in r.desc_key else "基礎"
            add(f"- {stage}（每日 {r.reset_times} 次）：{r.desc}")
        add("")
    add("**美味史萊姆（317）** 有兩組技能（`resetGroup` 3171 與 3172）：")
    add("")
    for rg, kind in ((3171, "贈送"), (3172, "自領")):
        add(f"- {rg}（{kind}）：")
        for r in data.skills_by_reset.get(rg) or []:
            add(f"  - `{r.desc_key}`（名稱 {r.name}，每日 {r.reset_times} 次）：{r.desc}")
    add("")
    add("**前服面板**（2026-11-22）：畫面技能名稱是「加倍美味史萊姆」；開到的是贈送介面，畫面寫「今日剩餘贈送次數 0/3」，與 `world_skin_skill_317_new_other` 對得上。**玩家確認**：「使用」就是給自己拿糖果。自領那筆當時未在畫面上獨立核對，先不當成已驗證。")
    add("")

    add("## 城堡造型套裝")
    add("")
    add(f"`world_skin_suit_collection.json` {data.table_meta['suit_rows']} 套。套裝 1005 官方名稱鍵是 `citybuilding_DIY_suit_name_52`＝「{official_text('citybuilding_DIY_suit_name_52')}」。揚帆啟航護盾 3008 為洋流環繞。**前服面板確認**怪奇物語成員名稱，並與「電流閃爍」「頻閃迴響」鍵名並陳。")
    add("")
    add("時尚值獎勵見 `world_skin_suit_collect_fashion.json`；獎勵道具 id 沒有 `goods_name`，只記 id。")
    add("")
    fash = [[str(r.get("order") or r.get("id")), str(r.get("point_require")), str(r.get("mission_reward"))] for r in sorted(data.fashion, key=lambda x: _int(x.get("order") or x.get("id")))]
    add(_md(["檔", "時尚值門檻", "mission_reward"], fash))
    add("")

    add("## 領域效果")
    add("")
    add(f"- 創世紀基礎（`skin_territory_311`）：{official_raw('skin_territory_311')}")
    add(f"- 創世紀 star10（`skin_territory_311_star10`）：{official_raw('skin_territory_311_star10')}")
    add(f"- 永恆紀（`skin_territory_327`）：{official_raw('skin_territory_327')}")
    add(f"- 星紀元（`skin_territory_2011`）：{official_raw('skin_territory_2011')}")
    add("")
    add("不要把 `territory_range` 4／5 寫成已證明等於文案的 9×9／11×11。")
    add("")

    add("## 共鳴（`world_skin_link.json`）")
    add("")
    add(f"3 列，`skin` 皆為 `311|327`。`level` 為 1、6、11，**不能讀成面板星數**。官方 `eternity_gm11` 為「{official_text('eternity_gm11')}」。**玩家確認**須同時擁有創世紀與永恆紀才會啟動。不要把面板「逆克制增傷」逕指成 3029。")
    add("")
    link_rows = []
    for r in data.links:
        link_rows.append([
            str(r.get("id")), str(r.get("linklevel")), str(r.get("level")),
            fmt_raw_pairs(parse_pairs(r.get("attr_own"))),
            fmt_raw_pairs(parse_pairs(r.get("attr_equip"))),
            str(r.get("buff_key")),
            "空" if is_empty(r.get("buff_range")) else str(r.get("buff_range")),
            str(r.get("buff_range_desc") or ""),
        ])
    add(_md(["id", "linklevel", "表 level", "attr_own 原值", "attr_equip 原值", "buff_key", "buff_range", "buff_range_desc"], link_rows))
    add("")
    add("**共鳴額外屬性（2026-11-22 前服面板，三檔皆已核到）**，不以表列改寫已核對的面板數值。**玩家確認**目前只開到共鳴等級 1；永恆紀「the max is 0 star now」。")
    add("")
    add(_md(
        ["共鳴等級", "面板條件", "額外擁有", "額外使用", "領域範圍", "對照字串"],
        [
            ["1", "「啟動兩個城堡造型」", "逆克制增傷 +1%、出征上限 +10", "所有士兵攻擊 +5%", EMPTY, "與 jbms_csj1 完全一致"],
            ["2", "「兩個城堡等級達到：」1 顆金星（1 金星＋1 灰星空位，讀成要 1 星，不要讀成 2 星）", "逆克制增傷 +1.5%、出征上限 +15", "所有士兵攻擊 +8%", EMPTY, "與 jbms_csj2 完全一致"],
            ["3", "「兩個城堡等級達到：」2 顆金星", "逆克制增傷 +2.5%、出征上限 +25", "所有士兵攻擊 +10%", "面板正文：「永恆紀、創世紀領域範圍從11*11擴大至13*13（星紀元領域同時提升）」。以面板為準。", "數值與領域幅度與 jbms_csj3 一致"],
        ],
    ))
    add("")

    add("## 城堡效果／特效（`world_skin_effect.json` type 1）")
    add("")
    t1 = data.effects_by_type.get(1) or []
    add(f"{len(t1)} 列、20 組，缺號無。表內只記原值。**前服面板確認**效果 2018 與光環 5004 畫面都寫「怪奇物語」。")
    add("")
    add(_md(["id", "名稱", "擁有屬性（原值）", "使用屬性（原值）"], [[str(ev.sid), ev.name, fmt_raw_pairs(ev.own), fmt_raw_pairs(ev.equip)] for ev in t1]))
    add("")

    add("## 城堡護盾（`world_skin_effect.json` type 2）")
    add("")
    t2 = data.effects_by_type.get(2) or []
    add(f"{len(t2)} 列，缺表組 3009。表 id 與名稱鍵後綴在 3007 起錯開一號：3007 果香帷幕、3008 洋流環繞。")
    add("")
    add(_md(["id", "名稱", "名稱鍵", "擁有屬性（原值）", "使用屬性（原值）"], [[str(ev.sid), ev.name, ev.name_key, fmt_raw_pairs(ev.own), fmt_raw_pairs(ev.equip)] for ev in t2]))
    add("")

    add("## 遷城特效（`world_skin_effect.json` type 3）")
    add("")
    t3 = data.effects_by_type.get(3) or []
    add(f"{len(t3)} 列，缺表組 4010。")
    add("")
    add(_md(["id", "名稱", "擁有屬性（原值）", "使用屬性（原值）"], [[str(ev.sid), ev.name, fmt_raw_pairs(ev.own), fmt_raw_pairs(ev.equip)] for ev in t3]))
    add("")

    add("## 光環造型（`world_skin_effect.json` type 4）")
    add("")
    t4 = data.effects_by_type.get(4) or []
    add(f"{len(t4)} 列、5 組，缺表組 5003、5006。這是光環自己的升級列，不是城堡星級。**玩家確認**名稱是「馴龍高手、鳳焰裂地」；若按所問的 5005、5007 順序回答會跟套裝歸屬相反，此保留條件與表列官方名並陳。")
    add("")
    au = []
    for ev in t4:
        alliance = parse_pairs(ev.raw.get("property_alliance"))
        au.append([str(ev.sid), str(ev.group), str(ev.level), ev.name, fmt_raw_pairs(ev.own), fmt_raw_pairs(ev.equip), fmt_raw_pairs(alliance) if alliance else "無"])
    add(_md(["id", "group", "表 level", "官方名", "擁有屬性（原值）", "使用屬性（原值）", "公會屬性"], au))
    add("")

    add("## 行軍造型（`world_skin_march.json`）")
    add("")
    add(f"{data.table_meta['march_rows']} 列。表內沒有 1018、1020–1022、1028。官方字串有 `skin_name_1028`＝{official_text('skin_name_1028')}，但不為缺號補表列，也不另開地心探險目錄。不要把面板「行軍造型 20%」強行對成下表任何一列。")
    add("")
    add(_md(
        ["id", "名稱", "名稱鍵", "擁有屬性（原值）", "使用屬性（原值）"],
        [[str(_int(r["id"])), official_text(r.get("name")), str(r.get("name") or ""), fmt_raw_pairs(parse_pairs(r.get("attr_own"))), fmt_raw_pairs(parse_pairs(r.get("attr_equip")))] for r in data.marches],
    ))
    add("")

    add("## 城堡翅膀（`world_skin_wing.json`）")
    add("")
    add(f"{data.table_meta['wing_rows']} 列。表內沒有指向某一城堡組的外鍵。`world_skin_wing_suit`＝「{o.wing_suit}」，與翅膀列本身的屬性對不上。")
    add("")
    add(_md(
        ["id", "官方名", "擁有屬性（原值）", "使用屬性（原值）", "公會屬性"],
        [[str(r.get("id")), official_text(r.get("name")), fmt_raw_pairs(parse_pairs(r.get("attr_own"))), fmt_raw_pairs(parse_pairs(r.get("attr_equip"))), fmt_raw_pairs(parse_pairs(r.get("property_alliance")))] for r in data.wings],
    ))
    add("")

    add("## 其他相鄰系統（不是本篇主體）")
    add("")
    add("### 建造造型／村莊風格")
    add("")
    add(_md(["id", "名稱", "season"], [[str(r.get("id")), official_text(r.get("name")), str(r.get("season"))] for r in data.village]))
    add("")
    add("逐棟屬性、地脈建築造型與 DIY 裝飾套裝不列入本頁主體。")
    add("")
    add("### 公會堡壘造型")
    add("")
    if data.fort:
        fr = data.fort[0]
        add(f"`alliance_fort_skin.json` 僅 {len(data.fort)} 筆：{official_text(fr.get('name'))}。擁有屬性：{fmt_raw_pairs(parse_pairs(fr.get('attr_own')))}。`attr_equip` 為 {fr.get('attr_equip')}，無法對成屬性名稱。")
        add("")

    add("## 介面實例（2026-11-22 前服面板＋玩家說明）")
    add("")
    add(
        "本節數值從遊戲「城堡造型」頁抄錄。主表 `world_skin.json` 現已收入本抽取；"
        "本節仍是 2026-11-22 前服面板紀錄，不在此把六座畫面全部改寫成表列，也不把表的 `level` 當成面板星數。"
        "蛋糕城、飛翔號、美味史萊姆、夢幻摩天輪的表列與 0 星／滿 1 星對應，見「城堡造型主表」。"
        "後兩座的 0 星＝level 1 是依主表 level 1，加上已用面板對上的滿 1 星＝level 6 鎖定，不是另一張 0 星面板截圖；"
        "不是 68 組都已用面板核過 0 星。"
        "面板已顯示的百分比或點數，照畫面記錄，不把畫面數字反推成表內原值。"
        "「逆克制增傷」用字串鍵 `attribute_name_damage`，不要寫成 3029。"
        "左側心形數字是讚數，不是戰力，不寫進屬性；下文讚數只作對圖註記。"
        "名稱下方的金星是城堡本身星級；技能等級是另一套。"
        "已有多座滿星補證，不同造型滿星不一定相同，不能把某一座的滿星推成通例。"
    )
    add("")
    add(
        "「守城時士兵生命」對得上字串鍵 `attribute_name_1010104`（`show_type=2`）。"
        "`attribute.json` 出現 id 與 `name` 交叉：id 1000104（以及 1000108）的 `name` 為 `attribute_name_1010104`；"
        "id 1010104 的 `name` 為 `attribute_name_1000104`（「守城時生命」）。"
        "本篇依面板用字與字串鍵記錄，不把交叉的列逕指為唯一來源。"
    )
    add("")
    add("### 熾火要塞（211）")
    add("")
    add(
        "來源為較早的熾火要塞詳情截圖。**玩家確認此造型滿星就是 1 星**，與畫面名稱下方那一顆金色星相符，因此這裡的擁有／使用屬性按滿星記錄。"
        "底部標示「永久」。當時只核到這一座滿星；第三版已有多座滿星補證，不同造型滿星不一定相同，仍不能把某一座的滿星推成通例。"
        "本筆截圖未另記讚數。技能等級是另一件事：同一帳號的技能升級畫面為 Lv 0/10，屬性截圖對應的是滿星、技能尚未升級的狀態。"
        "下列五條皆為 `show_type=2`。本節仍按當時面板抄錄，不在此對主表改寫。"
    )
    add("")
    add(_md(["欄位", "屬性（介面原文）", "屬性 id", "show_type"], [
        ["擁有屬性", "所有士兵攻擊 +10%", "10103", "2"],
        ["擁有屬性", "所有士兵生命 +10%", "10104", "2"],
        ["擁有屬性", "部族士兵生命 +25%", "14104", "2"],
        ["使用屬性", "部族士兵攻擊 +15%", "14103", "2"],
        ["使用屬性", "部族英雄暴擊率 +15%", "4008", "2"],
    ]))
    add("")
    add("同一畫面可見「技能」「外觀套裝」入口，以及底部「永久」「技能」「使用」。底部頁籤與字串一致：城堡造型、城堡護盾、遷城特效等。")
    add("")
    add("### 山岳之傲（231）")
    add("")
    add("2026-11-22 前服面板。滿星 1 顆金星；讚數 11703。技能 Lv 10/10。本節仍按當時面板抄錄，不在此對主表改寫，也不把表的 `level` 當成面板星數。")
    add("")
    add(_md(["欄位", "屬性（介面原文）", "屬性 id", "show_type"], [
        ["擁有屬性", "所有士兵攻擊 +10%", "10103", "2"],
        ["擁有屬性", "所有士兵生命 +10%", "10104", "2"],
        ["擁有屬性", "聯盟士兵生命 +25%", "13104", "2"],
        ["使用屬性", "防守時我方損兵比例降低 +5%", "1039", "2"],
        ["使用屬性", "守城時士兵生命 +30%", "1010104（字串鍵 `attribute_name_1010104`）", "2"],
    ]))
    add("")
    add("技能 Lv 10/10 與表 `world_skin_skill_231_lv2_10` 完全一致：自身提供增益：防守時我方傷兵比例降低+20%、防守時士兵生命+80%／持續時間12小時／每日次數2次。使用屬性用「損兵」、技能用「傷兵」，照字分開記，不要合併。")
    add("")
    add("### 創世紀（311）")
    add("")
    add("2026-11-22 前服面板。滿星 2 顆金星；讚數 18990。兩張圖是同一畫面因版面太窄分拍，合在一起才是完整屬性。共鳴等級 1 已啟動。本節仍按當時面板抄錄，不在此對主表改寫，也不把表的 `level` 當成面板星數。")
    add("")
    add(_md(["欄位", "屬性（介面原文）", "屬性 id／鍵", "show_type", "備註"], [
        ["擁有屬性", "逆克制增傷 +1%", "`attribute_name_damage`", "—", "標共鳴等級1，與 `jbms_csj1` 額外擁有一致；不要寫成 3029"],
        ["擁有屬性", "出征上限 +10", "1019", "1", "標共鳴等級1，與 `jbms_csj1` 額外擁有一致；照畫面記點數"],
        ["擁有屬性", "所有士兵攻擊 +30%", "10103", "2", ""],
        ["擁有屬性", "所有士兵生命 +90%", "10104", "2", ""],
        ["擁有屬性", "攻擊時敵方損兵比例增加 +25%", "1038", "2", ""],
        ["使用屬性", "所有士兵攻擊 +15%", "10103", "2", ""],
        ["使用屬性", "攻擊時敵方損兵比例增加 +10%", "1038", "2", ""],
    ]))
    add("")
    add("共鳴等級 1 的額外使用（所有士兵攻擊 +5%）已在共鳴介面核到，與 `jbms_csj1` 完全一致，見「共鳴」。")
    add("")
    add("### 永恆紀（327）")
    add("")
    add(
        "2026-11-22 前服面板。名稱下沒有星，並標「永久」；讚數 2294。"
        "玩家確認目前滿星就是 0 星（原話：「the max is 0 star now」）。"
        "主表雖有 group 327 的 level 1–11 列，不能把表的 `level` 當成目前可升的星數，與名稱下無星並陳。"
        "不要推斷以後會不會開放升星。因此共鳴等級 2（兩城都要 1 星）與等級 3（都要 2 星）目前開不到。"
        "同樣因版面太窄分拍兩張，合在一起才是完整屬性。共鳴等級 1 與創世紀相同（目前只開到這一檔）。"
        "本節仍按當時面板抄錄，不在此對主表改寫。面板 0 星＝表的 level 1，是玩家就蛋糕城、飛翔號確認的對應，不是這座已用面板對過主表。"
    )
    add("")
    add(_md(["欄位", "屬性（介面原文）", "屬性 id／鍵", "show_type", "備註"], [
        ["擁有屬性", "逆克制增傷 +1%", "`attribute_name_damage`", "—", "共鳴等級1，與創世紀、`jbms_csj1` 額外擁有相同；不要寫成 3029"],
        ["擁有屬性", "出征上限 +10", "1019", "1", "共鳴等級1；照畫面記點數"],
        ["擁有屬性", "所有士兵攻擊 +10%", "10103", "2", ""],
        ["擁有屬性", "所有士兵生命 +30%", "10104", "2", ""],
        ["擁有屬性", "防守時敵方損兵比例增加 +15%", "1059", "2", ""],
        ["使用屬性", "防守時敵方損兵比例增加 +10%", "1059", "2", ""],
        ["使用屬性", "所有士兵攻擊 +15%", "10103", "2", ""],
    ]))
    add("")
    add("### 天空之城（212）")
    add("")
    add("2026-11-22 前服面板。滿星 1 顆金星，並標「永久」；讚數 42532。畫面無技能按鈕，與本抽取沒有技能列相符。本節仍按當時面板抄錄，不在此對主表改寫，也不把表的 `level` 當成面板星數。")
    add("")
    add(_md(["欄位", "屬性（介面原文）", "屬性 id", "show_type", "備註"], [
        ["擁有屬性", "所有士兵生命 +50%", "10104", "2", ""],
        ["擁有屬性", "英雄等級上限 +20", "1098", "1", "照畫面記點數，不是百分比"],
        ["使用屬性", "所有士兵攻擊 +5%", "10103", "2", ""],
        ["使用屬性", "所有士兵生命 +15%", "10104", "2", ""],
    ]))
    add("")
    add("### 水晶聖城（312）")
    add("")
    add("2026-11-22 前服面板。玩家說明這是 VIP18 形態；名稱下為灰星，有「升級」按鈕；讚數 146。滿星就是 1 星，不能再升（玩家確認）。材料畫面曾見 0/1。")
    add("")
    add("**取消幻化後**，主頁面的擁有屬性與使用屬性都是空的（玩家確認）。")
    add("")
    add(
        "**幻化中**（畫面使用欄與領域皆標「幻化中」，`world_skin_01_03`）："
        "使用屬性為防守時敵方損兵比例增加 +10%、所有士兵攻擊 +15%，與永恆紀的使用屬性完全相同；擁有欄仍空。"
        "這張自身的擁有欄本來就是空的，所以看不出幻化後留下了什麼擁有屬性；"
        "自身擁有仍保留是玩家對幻化機制的確認，見上文「系統機制」，不是從這張空欄讀出的。"
    )
    add("")
    add("**隱藏使用屬性**只在升星介面看到，主頁面不列；玩家確認升到 1 星後，主頁面仍不顯示。")
    add("")
    add(
        "**升星檔（玩家更正）。** 沒有可停的 1/5、2/5、3/5、4/5 中間檔；一次升級就滿一顆星。"
        "先前那張「升星效果預覽」出現 9%＋1%、23%＋2%，是面板設計不佳，不是 4/5 可停檔，本篇不再按 4/5 中間檔來寫。"
        "也不要把 0 星預覽的 5%＋1%、15%＋2% 讀成下一步只到 6%／17%，或把 5%＋1% 讀成滿星 +6%。"
    )
    add("")
    add(_md(["檔", "使用屬性", "說明"], [
        ["0 星（0/5）", "所有士兵攻擊 +5%、所有士兵生命 +15%", "升星預覽曾見 5%＋1%、15%＋2%；玩家確認此檔就是 0 星 5%／15%"],
        ["滿 1 星（5/5）", "所有士兵攻擊 +10%、所有士兵生命 +25%", "一次升級即到此檔；滿星就是 1 星，不能再升（玩家確認）"],
    ]))
    add("")
    add("這組使用屬性仍按當時面板與玩家更正抄錄，不在此對主表改寫，也不把表的 `level` 當成面板星數。")
    add("")

    add("## 本頁未列入")
    add("")
    add(
        "- 主表 `world_skin.json` 已在本抽取。本頁已把 68 組的擁有／使用曲線寫入「城堡造型主表」（只有一列的也寫那一列）。"
        "不能把表的 `level` 當成面板星數。0 星＝level 1 只鎖定四座，不是 68 組通例。"
        "已見面板的六座仍寫在「介面實例」。共鳴三檔已在前服面板驗證，見「共鳴」；仍不是創世紀或永恆紀的基礎擁有／使用屬性或滿星屬性。"
    )
    add("- 護盾、效果、遷城、光環見 `world_skin_effect.json`（已依 type 分成四個獨立節），翅膀見 `world_skin_wing.json`，行軍見 `world_skin_march.json`，共鳴見 `world_skin_link.json`。不把尚未用面板核對的項目寫成結論。")
    add("- 村莊風格 190 棟建築外觀的逐棟屬性（這張套裝表沒有屬性）。地脈建築造型與 DIY 裝飾套裝不列入本頁主體。")
    add(
        "- 禮包文案裡沒有數值的屬性方向，不能當成滿星屬性。"
        "已核到的方向只有：黃金獅鷲禮包說明寫「提供大量聯盟士兵攻擊屬性」（另有字串寫「提供大量聯盟進攻屬性」）；"
        "鍵名含藍晶堡拼音的字串寫「更改城市外觀，並可提供大量冒險減傷屬性！」；"
        "聖誕城堡與夢幻之城寫士兵生命與帶兵上限；天空之城寫士兵攻擊和生命，並提升英雄等級上限"
        "（天空之城的面板數值見介面實例，不能把禮包文案本身當成滿星表）。"
    )
    add("")
    add("## 資料說明")
    add("")
    add(_footer_text(data))
    add("")
    leftover_txt = "、".join(f"{sid} {name}" for sid, name, _d in data.leftover)
    add(f"- 字串有但主表沒列：{leftover_txt}。不當成本表列。")
    add("- 仍待補、本頁不寫成結論：其餘各組 0 星／滿星、四座 290 升級未列入官方名單、博克島／霍金斯缺 `skin_name` 鍵、406 蒼穹／滄穹差異、時尚值道具名稱、表上無 VIP18 造型名稱鍵、共鳴 1／6／11 對應幾星、光環 Lv 顯示、`territory_range` 與文案格數、淨月蓮 3 格對 range=4、翅膀 cost 實際操作、source_goods 對物、行軍缺 1018／1020–1022／1028（1028 只有「地心專車」字串）、護盾缺 3009、遷城缺 4010、光環缺 5003／5006。")
    for item in data.verifications.get("chapter_diffs") or []:
        add(f"- 與第 17 章的差異：{item}")
    add("")
    return "\n".join(lines) + "\n"
