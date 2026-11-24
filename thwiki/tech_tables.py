"""Compile the unpublished 科技 catalog tables. Public-style HTML; preview script adds the banner."""

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
from .strings import clean, has_key, load_strings, t
from .tables import load_table


# 科技總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。本頁頁腳／截止日寫 2026-11-15
# （第 24 章第一版，香港時間）。與本頁正文有關的科技表在四份包位元組相同，
# 無需改用更晚的截止日。
TECH_DATA_CUTOFF = "2026-11-15"
TECH_DATA_PACK = "app-1.129.12_table-1.0.43173"
TECH_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "technology_advanced_type.json": "cba16ef820066b2bfc09e32ff7dc683e954d629a4db015de1cfc9585c4c2ae9c",
    "technology_advanced_detail.json": "befd42bd743aa80d8192998206d6bcfab8abc27a96897d7f8a6b0a8dcca03641",
    "technology_classfication.json": "6ae5a551292a7a2324a4b9cefdd2467ab763668a87e1329a41436d8102f0b2ba",
    "alliance_tech.json": "06776bcf2d79c8e8b33fd95758d4369dd65d6a0b6bac922ab265d64d77312669",
    "alliance_tech_page.json": "4a27d9f6c423be800e086b96eac52845c9a78cc8ee4823a8ba4403be229a8dbc",
    "alliance_tech_restype.json": "88920edbc74e5723455a430c1cb817002078fd998735c53b1f2c6c443297c920",
    "attr_category.json": "c24a1de29c2ca5d7960b24e7d61b629dcaf6adaad9048b8e38727629535829f2",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
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

EMPTY = "（空）"
DASH = "—"

LEDE = (
    "本頁主體是玩家科技（attr_category 25，官方名稱「科技」，提示「可在研究所內研究科技」）。"
    "公會科技是另一個來源分類（attr_category 14，官方名稱「公會科技」），下文另節登錄，不要與玩家科技混成同一欄。"
    "正文只根據遊戲資料表，不評定科技強弱，也不做搭配模擬。"
)

# 第 24 章頁面表序。不以檔案列序為準。
SET1_IDS = (1, 2, 10, 7, 8, 9, 101, 302, 303, 304, 301, 21)
SET2_IDS = (202, 213, 216, 214, 215, 217, 402, 403, 404, 401, 20)
EMPTY_IDS = (11, 12, 501, 502, 503, 504)
SHINE_IDS = (1001, 1002, 1003, 1004, 1005, 1006)
ALLIANCE_PAGE_ORDER = (1, 201, 3, 4, 101)

# 第 24 章在「名稱（名稱鍵）」欄註明的非常規名稱鍵。
UNUSUAL_NAME_KEYS = {
    101: "exchange_first_textA2",
    213: "alliance_tech_tips1",
    214: "exchange_first_textA2",
    215: "hero_name_64012",
    501: "activity_name_348",
    502: "activity_name_359",
}

# 明細表對不上類型表的 28 條樹（第 24 章鎖定；不以 tree_id 前綴臆測所屬頁）。
UNMATCHED_TREE_IDS = (
    130201, 130203, 130302, 130402, 130501, 130503, 130602, 130702,
    130801, 130803, 130902, 131002, 131101, 131103, 131202, 131302,
    131401, 131403, 131502, 131602, 131701, 131703, 131802, 131902,
    132001, 132003, 132102, 140102,
)

SOUL_TREES_20 = (200101, 200102, 200103, 200104, 200105, 200106)
SOUL_TREES_21 = (210101, 210102, 210103, 210104, 210105, 210106)
SOUL_ATTR = {
    200101: 21029, 210101: 21029,
    200102: 21031, 210102: 21031,
    200103: 21033, 210103: 21033,
    200104: 21030, 210104: 21030,
    200105: 21032, 210105: 21032,
    200106: 21034, 210106: 21034,
}

# 戰鬥統計表（第 24 章列序與合併方式）。counts 由全表明細計算，並與章節核對。
COMBAT_GROUPS = (
    ((10103, 10104), "所有士兵攻擊／生命", "各 18", "100–500", "滿級有 5 級、10 級與 1 級三種，不是一律 1–10 級"),
    ((13103, 13104, 14103, 14104, 15103, 15104), "聯盟／部族／自然士兵攻擊、生命", "各 12", "100–200", ""),
    ((3103, 3104, 4103, 4104, 5103, 5104), "聯盟／部族／自然英雄攻擊、生命", "各 5", "100–300", ""),
    ((3018, 3019, 4018, 4019, 5018, 5019), "聯盟／部族／自然英雄增傷、減傷", "各 4", "100–300", ""),
    ((103, 104), "英雄攻擊／生命", "各 5", "100–500", ""),
    ((18, 19), "增傷／減傷", "各 2", "100–300", "皆 5 級"),
    ((1019,), "出征上限", "12", "每級都是 10", "滿級有 5 級與 10 級"),
    ((165,), "裝備攻擊", "8 條樹、80 筆", "200–300", "皆 10 級"),
    ((166,), "裝備生命", "8 條樹、80 筆", "200–900", "皆 10 級"),
)

# 聯盟科技 effect_type=2 第 24 章提到的寫入（以 effectParamPairs 計筆）。
ALLIANCE_ET2_MENTIONS = (
    ((3103, 3104, 4103, 4104, 5103, 5104), "陣營英雄攻擊／生命", "各 40 筆"),
    ((103, 104), "英雄攻擊／生命", "各 23 筆"),
    ((10104,), "所有士兵生命", "20 筆"),
    ((10103,), "所有士兵攻擊", "5 筆"),
    ((165, 166), "裝備攻擊／生命", "各 5 筆"),
    ((22,), "防禦", "10 筆"),
    ((1000201, 1000202, 1000203), "攻城掠地（沙漠／冰雪／永夜）所有士兵攻擊", "各 5 筆"),
    ((1004, 1005, 1006), "採集速度", "各 30 筆"),
    ((1200115, 1200116), "對怪物傷害／受怪物減傷", "各 25 筆"),
    ((3, 4), "攻擊／生命值（type=1）", "各 30 筆"),
    ((3003,), "聯盟英雄攻擊（type=1）", "5 筆"),
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


def empty_or(value, empty: str = EMPTY) -> str:
    if value in (None, "", [], {}, -1):
        return empty
    return str(value)


def fmt_build_lv(raw) -> str:
    if raw in (None, "", [], {}, -1):
        return EMPTY
    if isinstance(raw, list):
        return "／".join(str(x) for x in raw)
    return str(raw)


def fmt_attr_id(raw) -> str:
    if raw in (None, "", [], {}, -1):
        return EMPTY
    if isinstance(raw, list):
        return "／".join(str(x) for x in raw)
    return str(raw)


def fmt_server_list(raw) -> str:
    if raw in (None, "", [], {}, -1):
        return EMPTY
    if isinstance(raw, list):
        return "、".join(str(x) for x in raw)
    return str(raw)


def fmt_range(lo, hi) -> str:
    if lo == hi:
        return comma(lo)
    return f"{comma(lo)}–{comma(hi)}"


@dataclass
class AttrInfo:
    attr_id: int
    name: str
    typ: int | None
    show_type: int | None
    name_key: str
    name_missing: bool
    name_col: str | None
    desc: str


@dataclass
class TypePage:
    type_id: int
    name: str
    name_key: str | None
    unusual_key: bool
    build_lv: str
    attr_id: str
    season_open: int
    server_list: list[str]
    server_list_raw: str
    pre_old: str
    pre_new: str
    is_shine: bool
    brilliance_switch: int
    note: str


@dataclass
class ClassRow:
    class_id: int
    name: str
    name_key: str
    condition: str
    close_des: str
    close_des_key: str


@dataclass
class CombatRow:
    label: str
    ids_text: str
    tree_text: str
    range_text: str
    note: str
    attr_ids: tuple[int, ...]
    computed_trees: list[int]
    computed_rows: list[int]
    computed_lo: list[int]
    computed_hi: list[int]
    computed_maxlv: list[dict]


@dataclass
class SameCampRow:
    attr_id: int
    name: str
    trees: int
    lo: int
    hi: int
    rows: int
    typ: int | None
    show_type: int | None
    has_official_name: bool
    desc: str


@dataclass
class SoulPair:
    tree_20: int
    tree_21: int
    attr_id: int
    desc: str


@dataclass
class UnmatchedTree:
    tree_id: int
    levels: int
    attr_id: int
    attr_name: str
    v_first: int
    v_last: int
    des_key: str
    des: str
    building_lv: str


@dataclass
class AlliancePage:
    page_id: int
    name: str
    name_key: str
    is_open: int
    season: int
    open_tech: str
    show: str
    note: str


@dataclass
class Official:
    tech_name: str
    tech_dec: str
    guild_name: str
    guild_dec: str
    shine_building_name: str
    shine_building_dec: str
    building_136: str
    building_136_des: str
    building_169: str
    building_169_des: str
    class_normal: str
    class_advanced: str
    close_des_1: str
    close_des_2: str
    leftover_502: str
    shine_name_1: str
    shine_name_2: str
    speed_1152: str
    speed_1153: str
    speed_1154: str
    speed_1155: str
    speed_1264: str
    name_atk_1: str
    name_hp_1: str
    name_hero_atk: str
    name_hero_hp: str
    name_3003: str
    name_3103: str
    great_guild: str
    great_guild_des: str
    s1_alliance: str


@dataclass
class TablesData:
    official: Official
    attrs: dict[int, AttrInfo]
    class_rows: list[ClassRow]
    set1: list[TypePage]
    set2: list[TypePage]
    empty_pages: list[TypePage]
    shine_pages: list[TypePage]
    combat_rows: list[CombatRow]
    same_camp: list[SameCampRow]
    unnamed_21007: list[SameCampRow]
    unnamed_21029: list[SameCampRow]
    unnamed_21035: list[SameCampRow]
    soul_pairs: list[SoulPair]
    unmatched: list[UnmatchedTree]
    alliance_pages: list[AlliancePage]
    alliance_et2_counts: dict[int, int]
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


def _attr_info(aid: int, attr_by: dict[int, dict], desc: str = "") -> AttrInfo:
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
        typ_i = typ_i
        show_i = None
    return AttrInfo(
        attr_id=aid,
        name=name,
        typ=typ_i,
        show_type=show_i,
        name_key=name_key,
        name_missing=name_missing,
        name_col=row.get("name"),
        desc=desc,
    )


def _note_for_page(row: dict, typ_id: int, name_key: str | None) -> str:
    bits: list[str] = []
    pre_old = row.get("pre_old")
    pre_new = row.get("pre_new")
    if typ_id in (7, 8, 9) and pre_old not in (None, "", -1):
        bits.append(f"`pre_old` 為 {pre_old}")
    elif typ_id in (302, 303, 304, 301) and pre_old not in (None, "", -1):
        bits.append(f"`pre_old` 為 {pre_old}")
    elif typ_id in (214, 402, 403, 404, 401) and pre_new not in (None, "", -1):
        bits.append(f"`pre_new` 為 {pre_new}")
    elif typ_id in (11, 12):
        parts = []
        if pre_new not in (None, "", -1):
            parts.append(f"`pre_new` {pre_new}")
        if pre_old not in (None, "", -1):
            parts.append(f"`pre_old` {pre_old}")
        bits.append("、".join(parts))
    if typ_id == 21:
        bits.append("本套鑄魂頁；`server_list` 為 1、6、10001–10107，比同套其他頁更窄")
    if typ_id == 20:
        bits.append(
            "名稱鍵同樣是 `tech_type_name_21`；`server_list` 為 2、3、4、7–999、10108–99999，與本套其他頁不完全相同"
        )
    if typ_id in (501, 502, 503, 504):
        bits.append("季節頁")
    if typ_id == 502:
        leftover = official_text("tech_type_name_502")
        bits.append(f"字串表另有 `tech_type_name_502`「{leftover}」，本頁名稱鍵不是這一條")
    if typ_id == 504:
        bits.append("`season_open` 為 5，不是 4，只照錄")
    return "；".join(b for b in bits if b)


def _parse_type(row: dict) -> TypePage:
    typ_id = _int(row["id"])
    raw_key = row.get("tech_type_name")
    name_key = str(raw_key) if raw_key not in (None, "", -1) else None
    name = official_text(name_key) if name_key else ""
    unusual = typ_id in UNUSUAL_NAME_KEYS
    sl = row.get("server_list")
    if sl in (None, "", -1):
        sl_list: list[str] = []
    elif isinstance(sl, list):
        sl_list = [str(x) for x in sl]
    else:
        sl_list = [str(sl)]
    return TypePage(
        type_id=typ_id,
        name=name,
        name_key=name_key,
        unusual_key=unusual,
        build_lv=fmt_build_lv(row.get("build_lv")),
        attr_id=fmt_attr_id(row.get("attribute_id") if row.get("attribute_id") not in (None, "") else row.get("AttrNameList")),
        season_open=_int(row["season_open"]) if row.get("season_open") not in (None, "") else -1,
        server_list=sl_list,
        server_list_raw=fmt_server_list(sl),
        pre_old=empty_or(row.get("pre_old")),
        pre_new=empty_or(row.get("pre_new")),
        is_shine=bool(row.get("IsShineTechnology")),
        brilliance_switch=_int(row["brilliance_switch"]) if row.get("brilliance_switch") not in (None, "") else -1,
        note=_note_for_page(row, typ_id, name_key),
    )


def _detail_writes(details: list[dict]) -> dict[int, dict]:
    tree_max: dict[int, int] = {}
    by: dict[int, dict] = {}
    for r in details:
        tid = _int(r["tree_id"])
        lv = _int(r["lv"])
        tree_max[tid] = max(tree_max.get(tid, 0), lv)
        for field_a, field_n in (("attribute", "num"), ("attribute_2", "num_2")):
            raw = r.get(field_a)
            num = r.get(field_n)
            if raw in (None, "", -1, 0):
                continue
            aid = _int(raw)
            rec = by.setdefault(aid, {"trees": set(), "vals": [], "rows": 0, "by_tree": defaultdict(list)})
            rec["trees"].add(tid)
            rec["vals"].append(_int(num))
            rec["rows"] += 1
            rec["by_tree"][tid].append(_int(num))
    for rec in by.values():
        rec["maxlv"] = Counter(tree_max[tid] for tid in rec["trees"])
    return by


def _alliance_et2_counts(rows: list[dict]) -> dict[int, int]:
    counts: Counter[int] = Counter()
    for r in rows:
        if _int(r.get("effect_type")) != 2:
            continue
        pairs = r.get("effectParamPairs") or []
        for pair in pairs:
            if isinstance(pair, (list, tuple)) and pair:
                counts[_int(pair[0])] += 1
    return dict(counts)


def _build_terms(o: Official, attrs: dict[int, AttrInfo], pages: list[TypePage],
                 class_rows: list[ClassRow], same_camp: list[SameCampRow],
                 unmatched: list[UnmatchedTree], soul: list[SoulPair],
                 alliance_pages: list[AlliancePage]) -> list[str]:
    terms: set[str] = {
        o.tech_name, o.tech_dec, o.guild_name, o.guild_dec,
        o.shine_building_name, o.shine_building_dec,
        o.building_136, o.building_136_des, o.building_169, o.building_169_des,
        o.class_normal, o.class_advanced, o.close_des_1, o.close_des_2,
        o.leftover_502, o.shine_name_1, o.shine_name_2,
        o.speed_1152, o.speed_1153, o.speed_1154, o.speed_1155, o.speed_1264,
        o.name_atk_1, o.name_hp_1, o.name_hero_atk, o.name_hero_hp,
        o.name_3003, o.name_3103, o.great_guild, o.great_guild_des, o.s1_alliance,
        "玩家科技", "公會科技", "聯盟科技", "英雄鑄魂", "光輝科技",
        "光輝研究所", "研究院", "研究所",
        "陣營強化聯盟", "陣營強化部族", "陣營強化自然",
        "部族的榮耀", "聯盟的光輝", "自然的生機", "巨龍的甦醒",
        "所有士兵攻擊", "所有士兵生命",
        "聯盟士兵攻擊", "聯盟士兵生命", "部族士兵攻擊", "部族士兵生命",
        "自然士兵攻擊", "自然士兵生命",
        "聯盟英雄攻擊", "聯盟英雄生命", "部族英雄攻擊", "部族英雄生命",
        "自然英雄攻擊", "自然英雄生命",
        "聯盟英雄增傷", "聯盟英雄減傷", "部族英雄增傷", "部族英雄減傷",
        "自然英雄增傷", "自然英雄減傷",
        "英雄攻擊", "英雄生命", "增傷", "減傷", "出征上限",
        "裝備攻擊", "裝備生命", "防禦",
        "木材採集速度", "石頭採集速度", "紅水晶採集速度",
        "對怪物傷害", "受怪物減傷",
        "攻城掠地（沙漠）所有士兵攻擊",
        "攻城掠地（冰雪）所有士兵攻擊",
        "攻城掠地（永夜）所有士兵攻擊",
        "基本科技", "公會發展", "進階發展", "爐火大廳",
        "普通訓練", "進階訓練",
        "世界樹之影", "冰封之焰", "暮光之戰", "潮汐之怒",
        "生產發展", "軍事理論", "隊列增強", "戰鬥專研", "發展", "經濟", "士兵", "英雄",
        "軍備表彰", "軍備準備",
        "初級科技研究加速", "進階科技研究加速", "高級科技研究加速", "大師科技研究加速",
        "光輝科技I研究加速", "光輝科技I", "光輝科技II",
        "S1科技", "偉大公會Ⅰ",
        "科技總表", "專武總表", "英靈總表", "造型總表", "裝備總表",
        "領主裝備總表", "士兵總表", "秘寶總表", "寵物總表", "符文總表",
    }
    for p in pages:
        if p.name:
            terms.add(p.name)
    for c in class_rows:
        terms.add(c.name)
        terms.add(c.close_des)
    for a in attrs.values():
        if a.name:
            terms.add(a.name)
        if a.desc:
            terms.add(a.desc)
    for row in same_camp:
        if row.name:
            terms.add(row.name)
        if row.desc:
            terms.add(row.desc)
    for u in unmatched:
        if u.attr_name:
            terms.add(u.attr_name)
        if u.des:
            terms.add(u.des)
    for s in soul:
        if s.desc:
            terms.add(s.desc)
    for p in alliance_pages:
        if p.name:
            terms.add(p.name)
    return [x for x in terms if x]


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    MISSING_KEYS.clear()

    type_rows = load_table("technology_advanced_type")
    detail_rows = load_table("technology_advanced_detail")
    class_raw = load_table("technology_classfication")
    attr_rows = load_table("attribute")
    cat_rows = load_table("attr_category")
    alliance_rows = load_table("alliance_tech")
    page_rows = load_table("alliance_tech_page")
    restype_rows = load_table("alliance_tech_restype")
    attr_by = {_int(a["id"]): a for a in attr_rows}
    type_by = {_int(r["id"]): r for r in type_rows}
    cat_by = {_int(r["id"]): r for r in cat_rows}

    pages = {tid: _parse_type(type_by[tid]) for tid in type_by}
    set1 = [pages[i] for i in SET1_IDS]
    set2 = [pages[i] for i in SET2_IDS]
    empty_pages = [pages[i] for i in EMPTY_IDS]
    shine_pages = [pages[i] for i in SHINE_IDS]

    class_rows = []
    for r in class_raw:
        class_rows.append(ClassRow(
            class_id=_int(r["id"]),
            name=official_text(r["name"]),
            name_key=str(r["name"]),
            condition=empty_or(r.get("condition")),
            close_des=official_text(r["close_des"]),
            close_des_key=str(r["close_des"]),
        ))

    writes = _detail_writes(detail_rows)
    tree_ids = {_int(r["tree_id"]) for r in detail_rows}
    trees_by: dict[int, list[dict]] = defaultdict(list)
    for r in detail_rows:
        trees_by[_int(r["tree_id"])].append(r)

    # Only attach a description when the official key is technology_adv_desc_{id}.
    # Do not follow borrowed keys (for example 21007 rows may point at
    # technology_adv_desc_20007); the chapter records 21007–21010 as having
    # no description, and 21029–21037 as using their own desc keys.
    desc_by_attr: dict[int, str] = {}
    for aid in list(range(21023, 21038)):
        key = f"technology_adv_desc_{aid}"
        if has_key(key):
            desc_by_attr[aid] = official_text(key)

    needed = set()
    for group in COMBAT_GROUPS:
        needed.update(group[0])
    needed.update(range(21007, 21011))
    needed.update(range(21023, 21038))
    needed.update(writes)
    needed.update({3, 4, 22, 103, 104, 165, 166, 1019, 3003, 3103, 3104,
                   1004, 1005, 1006, 1200115, 1200116, 1000201, 1000202, 1000203,
                   1152, 1153, 1154, 1155, 1264})
    attrs = {aid: _attr_info(aid, attr_by, desc_by_attr.get(aid, "")) for aid in sorted(needed)}

    combat_rows: list[CombatRow] = []
    for ids, label, _tree_text, _range_text, note in COMBAT_GROUPS:
        trees, rows_n, los, his, maxlvs = [], [], [], [], []
        id_bits = []
        for aid in ids:
            rec = writes[aid]
            trees.append(len(rec["trees"]))
            rows_n.append(rec["rows"])
            los.append(min(rec["vals"]))
            his.append(max(rec["vals"]))
            maxlvs.append(dict(rec["maxlv"]))
            an = attrs[aid]
            id_bits.append(str(aid))
        typ = attrs[ids[0]].typ
        show = attrs[ids[0]].show_type
        ids_text = "／".join(id_bits)
        if typ is not None and show is not None and len(ids) <= 2:
            ids_text = f"{ids_text}，type={typ}，show_type={show}"
        elif typ is not None and show is not None and ids[0] in (10103, 10104, 1019):
            ids_text = f"{ids_text}，type={typ}，show_type={show}"
        # Keep the chapter's display shape for the first row and 1019 / 165 / 166.
        if ids == (10103, 10104):
            ids_text = "10103／10104，type=2，show_type=2"
        elif ids == (1019,):
            ids_text = "1019，type=1，show_type=1"
        combat_rows.append(CombatRow(
            label=label,
            ids_text=ids_text,
            tree_text=_tree_text,
            range_text=_range_text,
            note=note,
            attr_ids=ids,
            computed_trees=trees,
            computed_rows=rows_n,
            computed_lo=los,
            computed_hi=his,
            computed_maxlv=maxlvs,
        ))

    def camp_row(aid: int) -> SameCampRow:
        rec = writes.get(aid, {"trees": set(), "vals": [], "rows": 0})
        info = attrs.get(aid) or _attr_info(aid, attr_by, desc_by_attr.get(aid, ""))
        vals = rec["vals"]
        return SameCampRow(
            attr_id=aid,
            name=info.name,
            trees=len(rec["trees"]),
            lo=min(vals) if vals else 0,
            hi=max(vals) if vals else 0,
            rows=rec["rows"],
            typ=info.typ,
            show_type=info.show_type,
            has_official_name=not info.name_missing and bool(info.name),
            desc=info.desc,
        )

    same_camp = [camp_row(aid) for aid in range(21023, 21029)]
    unnamed_21007 = [camp_row(aid) for aid in range(21007, 21011)]
    unnamed_21029 = [camp_row(aid) for aid in range(21029, 21035)]
    unnamed_21035 = [camp_row(aid) for aid in range(21035, 21038)]
    # Touch official descriptions even when attribute_name_* is missing.
    for aid in list(range(21029, 21038)):
        official_text(f"technology_adv_desc_{aid}")

    soul_pairs = []
    for t20, t21 in zip(SOUL_TREES_20, SOUL_TREES_21):
        aid = SOUL_ATTR[t20]
        soul_pairs.append(SoulPair(
            tree_20=t20,
            tree_21=t21,
            attr_id=aid,
            desc=official_text(f"technology_adv_desc_{aid}"),
        ))

    unmatched: list[UnmatchedTree] = []
    for tid in UNMATCHED_TREE_IDS:
        rows = sorted(trees_by[tid], key=lambda r: _int(r["lv"]))
        first, last = rows[0], rows[-1]
        aid = _int(first["attribute"])
        builds = []
        for r in rows:
            builds.append(fmt_build_lv(r.get("building_lv")))
        build_set = sorted(set(builds))
        unmatched.append(UnmatchedTree(
            tree_id=tid,
            levels=len(rows),
            attr_id=aid,
            attr_name=attrs[aid].name if aid in attrs else official_text(f"attribute_name_{aid}"),
            v_first=_int(first["num"]),
            v_last=_int(last["num"]),
            des_key=str(first.get("des") or ""),
            des=official_text(first.get("des")),
            building_lv="／".join(build_set),
        ))

    page_by = {_int(r["id"]): r for r in page_rows}
    alliance_pages = []
    for pid in ALLIANCE_PAGE_ORDER:
        r = page_by[pid]
        name_key = str(r["pagename"])
        name = official_text(name_key)
        show = r.get("show")
        show_s = EMPTY if show in (None, "", -1) else str(show)
        open_tech = empty_or(r.get("open_tech"))
        note = ""
        if pid == 101:
            note = "不把 `season=1` 標成未開放"
        elif pid == 201:
            note = f"`open_tech` 為 `{r.get('open_tech')}`"
        elif pid == 3:
            note = f"`open_tech` 為 `{r.get('open_tech')}`"
        elif pid == 4:
            note = f"`show` 為 {r.get('show')}"
        alliance_pages.append(AlliancePage(
            page_id=pid,
            name=name,
            name_key=name_key,
            is_open=_int(r["is_open"]),
            season=_int(r["season"]),
            open_tech=open_tech,
            show=show_s,
            note=note,
        ))
    et2_counts = _alliance_et2_counts(alliance_rows)

    cat25 = cat_by[25]
    cat14 = cat_by[14]
    cat32 = cat_by[32]
    o = Official(
        tech_name=official_text(cat25["name_key"]),
        tech_dec=official_text(cat25["tips_key"]),
        guild_name=official_text(cat14["name_key"]),
        guild_dec=official_text(cat14["tips_key"]),
        shine_building_name=official_text(cat32["name_key"]),
        shine_building_dec=official_text(cat32["tips_key"]),
        building_136=official_text("citybuilding_name_136"),
        building_136_des=official_text("citybuilding_des_136"),
        building_169=official_text("citybuilding_name_169"),
        building_169_des=official_text("citybuilding_des_169"),
        class_normal=class_rows[0].name,
        class_advanced=class_rows[1].name,
        close_des_1=class_rows[0].close_des,
        close_des_2=class_rows[1].close_des,
        leftover_502=official_text("tech_type_name_502"),
        shine_name_1=official_text("tech_type_name_shine_1"),
        shine_name_2=official_text("tech_type_name_shine_2"),
        speed_1152=official_text("attribute_name_1152"),
        speed_1153=official_text("attribute_name_1153"),
        speed_1154=official_text("attribute_name_1154"),
        speed_1155=official_text("attribute_name_1155"),
        speed_1264=official_text("attribute_name_1264"),
        name_atk_1=official_text("attribute_name_3"),
        name_hp_1=official_text("attribute_name_4"),
        name_hero_atk=official_text("attribute_name_103"),
        name_hero_hp=official_text("attribute_name_104"),
        name_3003=official_text("attribute_name_3003"),
        name_3103=official_text("attribute_name_3103"),
        great_guild=official_text("alliance_tech_name_101"),
        great_guild_des=official_text("alliance_tech_desc_101"),
        s1_alliance=official_text("alliance_tech_tips101"),
    )
    # Leftover shine / 502 keys already loaded. Touch alliance missing-name rule only via count.
    strings = load_strings()
    adv_name_count = sum(1 for k in strings if k.startswith("technology_adv_name_"))
    missing_alliance_names = [
        gid for gid in sorted({_int(r["group_id"]) for r in alliance_rows})
        if not has_key(f"alliance_tech_name_{gid}")
    ]

    all_pages = set1 + set2 + empty_pages + shine_pages
    terms = _build_terms(o, attrs, all_pages, class_rows, same_camp + unnamed_21007 + unnamed_21029 + unnamed_21035,
                         unmatched, soul_pairs, alliance_pages)

    compare_names = [
        "technology_advanced_type.json",
        "technology_advanced_detail.json",
        "technology_advanced_tree.json",
        "technology_classfication.json",
        "technology.json",
        "alliance_tech.json",
        "alliance_tech_page.json",
        "alliance_tech_restype.json",
        "alliance_tech_group.json",
        "attr_category.json",
        "attribute.json",
        "citybuilding.json",
        "ether_ranch_tech_detail.json",
        "kvk_alliance_fortress_tech.json",
        "shine_troop.json",
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

    table_count = len(list(DATA_DIR.glob("*.json")))
    old_dir = TOPHEROES_ROOT / "extracts/2026-11-05/data"
    old_count = len(list(old_dir.glob("*.json"))) if old_dir.exists() else None

    groups = defaultdict(list)
    for r in alliance_rows:
        groups[_int(r["group_id"])].append(r)
    maxlv_dist = Counter(_int(rows[0]["max_level"]) for rows in groups.values())
    effect_types = Counter(_int(r["effect_type"]) for r in alliance_rows)
    level_dist = Counter(len(v) for v in trees_by.values())

    table_meta = {
        "table_cmp": table_cmp,
        "string_cmp": string_cmp,
        "sha_ok": sha_ok,
        "sha_failures": sha_failures,
        "table_count": table_count,
        "extract_2026_11_05_table_count": old_count,
        "type_rows": len(type_rows),
        "detail_rows": len(detail_rows),
        "tree_count": len(trees_by),
        "class_rows": len(class_rows),
        "adv_name_count": adv_name_count,
        "alliance_rows": len(alliance_rows),
        "alliance_groups": len(groups),
        "alliance_maxlv": dict(maxlv_dist),
        "alliance_pages": len(page_rows),
        "alliance_restype": len(restype_rows),
        "effect_types": dict(effect_types),
        "level_dist": dict(level_dist),
        "missing_alliance_names": len(missing_alliance_names),
        "soul_levels": {tid: len(trees_by[tid]) for tid in list(SOUL_TREES_20) + list(SOUL_TREES_21)},
        "writes": writes,
    }

    data = TablesData(
        official=o,
        attrs=attrs,
        class_rows=class_rows,
        set1=set1,
        set2=set2,
        empty_pages=empty_pages,
        shine_pages=shine_pages,
        combat_rows=combat_rows,
        same_camp=same_camp,
        unnamed_21007=unnamed_21007,
        unnamed_21029=unnamed_21029,
        unnamed_21035=unnamed_21035,
        soul_pairs=soul_pairs,
        unmatched=unmatched,
        alliance_pages=alliance_pages,
        alliance_et2_counts=et2_counts,
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
    meta = data.table_meta
    checks["type_rows"] = meta["type_rows"]
    checks["detail_rows"] = meta["detail_rows"]
    checks["tree_count"] = meta["tree_count"]
    checks["class_rows"] = meta["class_rows"]
    checks["unmatched"] = len(data.unmatched)
    checks["soul_trees"] = len(data.soul_pairs) * 2
    checks["soul_levels"] = list(meta["soul_levels"].values())
    checks["alliance_rows"] = meta["alliance_rows"]
    checks["alliance_groups"] = meta["alliance_groups"]
    checks["alliance_maxlv"] = meta["alliance_maxlv"]
    checks["alliance_pages"] = meta["alliance_pages"]
    checks["effect_type_2"] = meta["effect_types"].get(2)
    checks["adv_name_count"] = meta["adv_name_count"]
    checks["shine_named"] = [p.name for p in data.shine_pages]
    checks["season_open_504"] = next(p.season_open for p in data.empty_pages if p.type_id == 504)
    checks["s1_season"] = next(p.season for p in data.alliance_pages if p.page_id == 101)

    def expect(key: str, actual, wanted) -> None:
        if actual != wanted:
            failures.append(f"{key}: {actual} != {wanted}")

    expect("type_rows", checks["type_rows"], 35)
    expect("detail_rows", checks["detail_rows"], 24104)
    expect("tree_count", checks["tree_count"], 841)
    expect("class_rows", checks["class_rows"], 2)
    expect("unmatched", checks["unmatched"], 28)
    expect("soul_trees", checks["soul_trees"], 12)
    if any(lv != 1500 for lv in checks["soul_levels"]):
        failures.append(f"soul_levels: {checks['soul_levels']}")
    expect("alliance_rows", checks["alliance_rows"], 756)
    expect("alliance_groups", checks["alliance_groups"], 194)
    expect("alliance_maxlv", checks["alliance_maxlv"], {5: 140, 1: 52, 2: 2})
    expect("alliance_pages", checks["alliance_pages"], 5)
    expect("effect_type_2", checks["effect_type_2"], 697)
    expect("adv_name_count", checks["adv_name_count"], 406)
    if any(data.shine_pages[i].name for i in range(len(data.shine_pages))):
        failures.append(f"shine pages have names: {checks['shine_named']}")
    expect("season_open_504", checks["season_open_504"], 5)
    expect("s1_season", checks["s1_season"], 1)

    # Combat statistics vs chapter 24.
    expected_combat = {
        (10103, 10104): {"trees": 18, "lo": 100, "hi": 500},
        (13103, 13104, 14103, 14104, 15103, 15104): {"trees": 12, "lo": 100, "hi": 200},
        (3103, 3104, 4103, 4104, 5103, 5104): {"trees": 5, "lo": 100, "hi": 300},
        (3018, 3019, 4018, 4019, 5018, 5019): {"trees": 4, "lo": 100, "hi": 300},
        (103, 104): {"trees": 5, "lo": 100, "hi": 500},
        (18, 19): {"trees": 2, "lo": 100, "hi": 300},
        (1019,): {"trees": 12, "lo": 10, "hi": 10},
        (165,): {"trees": 8, "rows": 80, "lo": 200, "hi": 300},
        (166,): {"trees": 8, "rows": 80, "lo": 200, "hi": 900},
    }
    combat_diffs: list[str] = []
    for row in data.combat_rows:
        exp = expected_combat[row.attr_ids]
        if any(t != exp["trees"] for t in row.computed_trees):
            combat_diffs.append(f"{row.attr_ids} trees {row.computed_trees} != {exp['trees']}")
        if any(lo != exp["lo"] or hi != exp["hi"] for lo, hi in zip(row.computed_lo, row.computed_hi)):
            combat_diffs.append(
                f"{row.attr_ids} range {list(zip(row.computed_lo, row.computed_hi))} != {exp['lo']}-{exp['hi']}"
            )
        if "rows" in exp and any(n != exp["rows"] for n in row.computed_rows):
            combat_diffs.append(f"{row.attr_ids} rows {row.computed_rows} != {exp['rows']}")
    checks["combat_diffs"] = combat_diffs
    if combat_diffs:
        failures.extend(combat_diffs)

    # Same-camp examples from the chapter.
    by_camp = {r.attr_id: r for r in data.same_camp}
    if by_camp[21024].trees != 10 or (by_camp[21024].lo, by_camp[21024].hi) != (100, 600):
        failures.append(f"21024 {by_camp[21024].trees} {by_camp[21024].lo}-{by_camp[21024].hi}")
    if by_camp[21025].trees != 7 or (by_camp[21025].lo, by_camp[21025].hi) != (50, 600):
        failures.append(f"21025 {by_camp[21025].trees} {by_camp[21025].lo}-{by_camp[21025].hi}")
    for row in data.unnamed_21007:
        if row.trees != 10 or row.lo != 100 or row.hi != 100 or row.has_official_name or row.desc:
            failures.append(
                f"21007-group {row.attr_id}: trees={row.trees} {row.lo}-{row.hi} "
                f"name={row.has_official_name!r} desc={row.desc!r}"
            )
    for row in data.unnamed_21029:
        if row.has_official_name:
            failures.append(f"21029-group has official name {row.attr_id}")
        if not row.desc:
            failures.append(f"21029-group missing desc {row.attr_id}")
    soul_ids = set(SOUL_TREES_20) | set(SOUL_TREES_21)
    writes = meta["writes"]
    for aid in range(21029, 21035):
        rec = writes[aid]
        soul_vals = [v for tid, vs in rec["by_tree"].items() if tid in soul_ids for v in vs]
        if set(soul_vals) != {10}:
            failures.append(f"soul attr {aid} vals {set(soul_vals)}")
        if min(rec["vals"]) != 10 or max(rec["vals"]) != 1000:
            failures.append(f"{aid} whole-table range {min(rec['vals'])}-{max(rec['vals'])}")

    expected_et2 = {
        3103: 40, 3104: 40, 4103: 40, 4104: 40, 5103: 40, 5104: 40,
        103: 23, 104: 23, 10104: 20, 10103: 5, 165: 5, 166: 5, 22: 10,
        1000201: 5, 1000202: 5, 1000203: 5,
        1004: 30, 1005: 30, 1006: 30, 1200115: 25, 1200116: 25,
        3: 30, 4: 30, 3003: 5,
    }
    et2_diffs = [
        f"{aid}: {data.alliance_et2_counts.get(aid)} != {n}"
        for aid, n in expected_et2.items()
        if data.alliance_et2_counts.get(aid) != n
    ]
    checks["et2_diffs"] = et2_diffs
    if et2_diffs:
        failures.extend(et2_diffs)

    # 偉大公會Ⅰ effect_para [3] is recorded as a count, not attribute 3.
    checks["great_guild_name"] = data.official.great_guild
    checks["type20_server"] = data.set2[-1].server_list_raw
    checks["type21_server"] = data.set1[-1].server_list_raw
    if data.set2[-1].name_key != "tech_type_name_21":
        failures.append(f"type 20 name key {data.set2[-1].name_key}")
    if data.empty_pages[3].name_key != "activity_name_359":
        failures.append(f"type 502 name key {data.empty_pages[3].name_key}")

    return {
        "checks": checks,
        "failures": failures,
        "passed": not failures,
        "chapter_diffs": combat_diffs + et2_diffs,
    }


def _page_name_cell(page: TypePage, html: bool, terms: list[str] | None = None) -> str:
    if not page.name:
        label = EMPTY
        body = official_term_html(EMPTY) if html else EMPTY
    else:
        body = official_term_html(page.name) if html else page.name
    if page.unusual_key and page.name_key:
        key = f"<code>{e(page.name_key)}</code>" if html else f"`{page.name_key}`"
        return f"{body}（名稱鍵 {key}）"
    return body


def _note_cell(text: str, html: bool, terms: list[str]) -> str:
    if not text:
        return EMPTY if not html else official_term_html("") or EMPTY
    if not html:
        return text
    # Keep code spans; highlight the rest in chunks.
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`"):
            out.append(f"<code>{e(part[1:-1])}</code>")
        else:
            out.append(H(part, terms))
    return "".join(out) if out else EMPTY


def _attr_label_html(row: CombatRow, terms: list[str]) -> str:
    name = official_term_html(row.label) if "／" not in row.label else H(row.label, terms)
    return f"{name}（{e(row.ids_text)}）"


def _attr_label_md(row: CombatRow) -> str:
    return f"{row.label}（{row.ids_text}）"


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    class_rows = []
    for r in data.class_rows:
        class_rows.append([
            str(r.class_id),
            official_term_html(r.name),
            e(r.condition) if r.condition != EMPTY else EMPTY,
            official_term_html(r.close_des),
        ])
    out["class"] = table(
        ["id", "名稱", "條件 <code>condition</code>", "關閉說明 <code>close_des</code>"],
        class_rows,
        mobile="cards",
        card_title="名稱",
    )

    def page_rows(pages: list[TypePage], with_speed: bool, with_season: bool) -> list[list[str]]:
        rows = []
        for p in pages:
            name = _page_name_cell(p, True, terms)
            note = _note_cell(p.note, True, terms) if p.note else ""
            if with_speed:
                rows.append([str(p.type_id), name, e(p.build_lv), e(p.attr_id), note])
            elif with_season:
                rows.append([str(p.type_id), name, e(p.build_lv), str(p.season_open), note])
            else:
                rows.append([str(p.type_id), name, e(p.build_lv), note])
        return rows

    out["set1"] = table(
        ["類型 id", "名稱（名稱鍵）", "<code>build_lv</code>", "加速屬性", "備註"],
        page_rows(data.set1, True, False),
        mobile="cards",
        card_title="名稱（名稱鍵）",
    )
    out["set2"] = table(
        ["類型 id", "名稱（名稱鍵）", "<code>build_lv</code>", "加速屬性", "備註"],
        page_rows(data.set2, True, False),
        mobile="cards",
        card_title="名稱（名稱鍵）",
    )
    shine_note = (
        f"<code>tech_type_name</code> 為空，無名稱字串。<code>IsShineTechnology=true</code>，"
        f"<code>brilliance_switch=1</code>。1001–1003 的加速屬性是 1264「{official_term_html(data.official.speed_1264)}」，"
        "1004–1006 沒有掛加速屬性。字串表另有 "
        f"<code>tech_type_name_shine_1</code>「{official_term_html(data.official.shine_name_1)}」、"
        f"<code>tech_type_name_shine_2</code>「{official_term_html(data.official.shine_name_2)}」，"
        "類型表沒有把這兩個鍵掛上 1001–1006，本頁不自行對號"
    )
    empty_rows = page_rows(data.empty_pages, False, True)
    empty_rows.append([
        "1001–1006",
        EMPTY,
        "169|1",
        "-1",
        shine_note,
    ])
    out["empty"] = table(
        ["類型 id", "名稱", "<code>build_lv</code>", "<code>season_open</code>", "備註"],
        empty_rows,
        mobile="cards",
        card_title="類型 id",
    )

    unmatched_rows = []
    for u in data.unmatched:
        attr = f"{u.attr_id}"
        if u.attr_name:
            attr = f"{official_term_html(u.attr_name)}（{u.attr_id}）"
        unmatched_rows.append([
            str(u.tree_id),
            str(u.levels),
            attr,
            f"{comma(u.v_first)}／{comma(u.v_last)}",
            official_term_html(u.des) if u.des else EMPTY,
            e(u.building_lv),
        ])
    out["unmatched"] = table(
        ["樹 id", "級數", "寫入屬性", "1 級／滿級", "說明文", "建築條件"],
        unmatched_rows,
        mobile="cards",
        card_title="樹 id",
    )

    combat_rows = []
    for row in data.combat_rows:
        combat_rows.append([
            _attr_label_html(row, terms),
            e(row.tree_text),
            e(row.range_text),
            H(row.note, terms) if row.note else "",
        ])
    out["combat"] = table(
        ["屬性", "樹數", "數值範圍", "備註"],
        combat_rows,
        mobile="sticky",
    )

    camp_rows = []
    for row in data.same_camp:
        camp_rows.append([
            str(row.attr_id),
            official_term_html(row.name),
            str(row.trees),
            fmt_range(row.lo, row.hi),
        ])
    out["same_camp"] = table(
        ["屬性 id", "官方屬性名", "樹數", "數值範圍"],
        camp_rows,
        mobile="cards",
        card_title="官方屬性名",
    )

    soul_rows = []
    for s in data.soul_pairs:
        soul_rows.append([
            f"{s.tree_20}／{s.tree_21}",
            str(s.attr_id),
            official_term_html(s.desc),
        ])
    out["soul"] = table(
        ["樹 id（20／21 各一）", "屬性（名稱未定）", "說明文"],
        soul_rows,
        mobile="cards",
        card_title="樹 id（20／21 各一）",
    )

    ap_rows = []
    for p in data.alliance_pages:
        other = ""
        if p.page_id == 201:
            other = f"<code>open_tech</code> 為 <code>{e(p.open_tech)}</code>"
        elif p.page_id == 3:
            other = f"<code>open_tech</code> 為 <code>{e(p.open_tech)}</code>"
        elif p.page_id == 4:
            other = f"<code>show</code> 為 {e(p.show)}"
        elif p.page_id == 101:
            other = "不把 <code>season=1</code> 標成未開放"
        name = official_term_html(p.name)
        if p.page_id == 101:
            name = f"{name}（名稱鍵 <code>{e(p.name_key)}</code>）"
        ap_rows.append([
            str(p.page_id),
            name,
            str(p.is_open),
            str(p.season),
            other,
        ])
    out["alliance_pages"] = table(
        ["頁 id", "名稱", "<code>is_open</code>", "<code>season</code>", "其他欄"],
        ap_rows,
        mobile="cards",
        card_title="名稱",
    )

    et2_rows = []
    for ids, label, count_text in ALLIANCE_ET2_MENTIONS:
        id_text = "／".join(str(i) for i in ids)
        et2_rows.append([
            H(label, terms),
            e(id_text),
            e(count_text),
        ])
    out["alliance_et2"] = table(
        ["寫入", "屬性 id", "筆數（effect_type=2）"],
        et2_rows,
        mobile="sticky",
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
        extra = f"本頁用到的 {sc['used_keys']} 個字串鍵在這四份裡值相同。"
    live = sc["packs"]["live"]
    old = sc["packs"]["2026-11-05"]
    sa = sc["packs"]["2026-11-22"]

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
            same = f"只出現在 {'、'.join(present)}；" + "、".join(missing_p) + " 沒有此表"
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
        "差在後來多了 NameKey、name_season 欄；本頁用到的屬性 id、type、show_type 與 "
        "`attribute_name_{id}` 並未因此改變。"
    )
    locallow_only = (
        pack_note("technology_advanced_tree.json", "樹定義，本頁不用它把樹劃進頁面")
        + pack_note("technology.json", "舊科技表，本頁不展開")
        + pack_note("alliance_tech_group.json", "聯盟科技組，本頁不另作目錄")
        + pack_note("citybuilding.json", "建築表")
        + "建築正式名取自字串鍵 `citybuilding_name_136`、`citybuilding_name_169`，四份字串表都有。"
    )
    return (
        f"資料截至 {TECH_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {TECH_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {TECH_DATA_PACKED}（香港時間）。"
        f"第 24 章第一版寫於 2026-11-15（香港時間），標題仍寫來源解壓日期 2026-11-05"
        f"（{data.table_meta['extract_2026_11_05_table_count']} 張表）。"
        + pack_note("technology_advanced_type.json", "玩家科技頁")
        + pack_note("technology_advanced_detail.json", "玩家科技節點")
        + pack_note("technology_classfication.json", "訓練分類；檔名少一個 i")
        + pack_note("alliance_tech.json", "聯盟科技")
        + pack_note("alliance_tech_page.json", "聯盟科技頁")
        + pack_note("alliance_tech_restype.json", "捐獻資源類型")
        + pack_note("attr_category.json", "屬性來源分類")
        + attr_note
        + locallow_only
        + f"`strings_zh.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（{live['keys']} 鍵，"
        f"{live['bytes']} bytes，sha256 {live['sha256']}）；"
        f"2026-11-05（{old['keys']} 鍵）與 2026-11-22 StreamingAssets（{sa['keys']} 鍵）整體不同。"
        f"{extra}"
        "顯示規則依攻略手冊「科技圖鑑」第一版（2026-11-15，香港時間），數值以現行資料表為準；"
        "與本頁正文有關的類型、明細、分類與聯盟科技表在四份包位元組相同，頁上數字與第 24 章一致。"
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜科技總表"
    summary = (
        "玩家科技與公會科技分開登錄：35 個玩家科技頁、全表明細的戰鬥屬性統計、"
        "英雄鑄魂 12 條 1,500 級樹，以及聯盟科技頁面與主要戰鬥寫入。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "classification", "label": "訓練分類"},
        {"id": "pages", "label": "頁面與伺服器名單"},
        {"id": "set1", "label": "第一套 server_list", "depth": 1},
        {"id": "set2", "label": "第二套 server_list", "depth": 1},
        {"id": "empty-pages", "label": "server_list 為空的頁", "depth": 1},
        {"id": "unmatched", "label": "對不上類型表的樹", "depth": 1},
        {"id": "combat", "label": "與戰鬥相關的寫入（玩家科技）"},
        {"id": "soul", "label": "英雄鑄魂"},
        {"id": "alliance", "label": "聯盟科技（公會科技）"},
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
        "本頁主體是玩家科技"
        f"（<code>attr_category</code> 25，官方名稱「{H(o.tech_name, terms)}」，"
        f"提示「{official_term_html(o.tech_dec)}」）。"
        f"定義頁在 <code>technology_advanced_type.json</code>（{comma(35)} 筆），"
        f"節點在 <code>technology_advanced_detail.json</code>"
        f"（{comma(24104)} 筆、{comma(841)} 條樹）。"
        "分類表 <code>technology_classfication.json</code> 只有兩類（檔名少一個 i）。"
    ))
    add(p_html(
        "公會科技是另一個來源分類"
        f"（<code>attr_category</code> 14，官方名稱「{H(o.guild_name, terms)}」，"
        f"提示「{official_term_html(o.guild_dec)}」），"
        "表在 <code>alliance_tech.json</code> 等，下文另節登錄，不要與玩家科技混成同一欄。"
    ))
    add(p_html(
        f"{H(o.shine_building_name, terms)}（<code>attr_category</code> 32，"
        f"提示「{official_term_html(o.shine_building_dec)}」）不是科技樹，也不在本頁正文展開。"
        "本抽取另有光輝科技頁（類型 1001–1006，<code>IsShineTechnology=true</code>，"
        f"前置建築 169「{H(o.building_169, terms)}」），與光輝建築不是同一分類，見下文。"
    ))
    add(p_html(
        f"已發佈的<a href=\"exclusive.html\">{H('專武總表', terms)}</a>、<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>、"
        f"<a href=\"skins.html\">{H('造型總表', terms)}</a>、<a href=\"equipment.html\">{H('裝備總表', terms)}</a>、"
        f"<a href=\"lord-equipment.html\">{H('領主裝備總表', terms)}</a>、<a href=\"troops.html\">{H('士兵總表', terms)}</a>、"
        f"<a href=\"artifacts.html\">{H('秘寶總表', terms)}</a>、<a href=\"pets.html\">{H('寵物總表', terms)}</a>、"
        f"<a href=\"runes.html\">{H('符文總表', terms)}</a>、"
        f"<a href=\"talents.html\">{H('天賦總表', terms)}</a>、<a href=\"decorations.html\">{H('裝飾物總表', terms)}</a>、"
        f"<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>是其他系統，不在本頁展開。"
    ))
    add("<ul>")
    add(
        "<li><strong>正文只根據遊戲資料表。</strong>不把玩家討論寫進正文。"
        "明細表沒有「類型」外鍵，不能由 <code>tree_id</code> 前綴唯一對回 35 個頁面"
        "（前綴會重疊，例如 20xxxx 既可能讀成類型 20，也可能讀成類型 202）。"
        "本頁以類型表列出頁面，戰鬥相關寫入改按全表明細做屬性統計，不把每條樹強行劃進某一頁。</li>"
    )
    add(
        "<li><strong>屬性名</strong>優先用 <code>attribute_name_{id}</code>。"
        "<code>show_type=2</code> 只記表內原值，不自行換算成百分比。"
        "不要把 <code>type=1</code> 與 <code>type=2</code> 的同名屬性混成同一欄："
        f"例如「{H(o.name_atk_1, terms)}／{H(o.name_hp_1, terms)}」是 3／4"
        f"（<code>type=1</code>、<code>show_type=1</code>），"
        f"「{H(o.name_hero_atk, terms)}／{H(o.name_hero_hp, terms)}」是 103／104"
        f"（<code>type=2</code>、<code>show_type=2</code>）；"
        f"「{H(o.name_3003, terms)}」既有 3003（<code>type=1</code>）也有 3103（<code>type=2</code>）。"
        "玩家科技寫的陣營英雄攻擊／生命是 3103／3104 這組 <code>type=2</code>。</li>"
    )
    add(
        "<li><strong>不要從 <code>unlocktime</code>、<code>season</code> 或 <code>season_open</code> 自動標未開放。</strong>"
        "季節頁的 <code>season_open</code> 只照錄。</li>"
    )
    add(
        "<li>類型表的 <code>attribute_id</code>／<code>AttrNameList</code> 掛的是頁面加速屬性："
        f"1152 {official_term_html(o.speed_1152)}、1153 {official_term_html(o.speed_1153)}、"
        f"1154 {official_term_html(o.speed_1154)}、1155 {official_term_html(o.speed_1155)}，"
        f"以及 1264 {official_term_html(o.speed_1264)}。"
        "這些是研究加速，不是戰鬥攻擊。</li>"
    )
    add(
        "<li>節點消耗與時間、研究所建築等級寫在明細表。前置建築實際出現的是 "
        f"136「{official_term_html(o.building_136)}」（<code>citybuilding_name_136</code>，"
        f"說明「{official_term_html(o.building_136_des)}」）與 "
        f"169「{official_term_html(o.building_169)}」"
        f"（說明「{official_term_html(o.building_169_des)}」）。"
        "屬性分類提示寫的是「研究所」，與建築正式名「研究院」用字不同，兩種寫法都照錄。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="classification">')
    add("      <h2>訓練分類</h2>")
    add(p_html("<code>technology_classfication.json</code> 兩筆："))
    add(tbl["class"])
    add(p_html(
        "關閉說明是字串表原文，本頁不拆成兩句，也不把「全英雄攻擊增加」寫成已驗證的開啟效果。"
        "條件 <code>1|2402|1</code> 在分類表沒有再說明，本頁不自行解釋。"
        "這張表與 35 個進階科技頁之間沒有外鍵，本頁不把頁面劃進「普通／進階訓練」。"
    ))
    add("    </section>")

    add('    <section id="pages">')
    add("      <h2>頁面與伺服器名單</h2>")
    add(p_html(
        "類型表用 <code>server_list</code> 把同一名稱的頁面分成兩套。"
        "本頁只按表列出名單，不另外推哪一個客戶端開關會覆蓋這份名單。"
        f"<code>build_lv</code> 是該頁要求的{H(o.building_136, terms)}（136）或{H(o.building_169, terms)}（169）等級。"
    ))
    add('    <h3 id="set1">第一套 <code>server_list</code></h3>')
    add(p_html("第一套 <code>server_list</code> 含 1、6、11、13、15–999、1001–1004、10001–10107："))
    add(tbl["set1"])
    add('    <h3 id="set2">第二套 <code>server_list</code></h3>')
    add(p_html(
        "第二套 <code>server_list</code> 含 2–5、7–9、12、14、1005–9999、10108–99999"
        "（類型 20 的名單略有不同，見該列）："
    ))
    add(tbl["set2"])
    add('    <h3 id="empty-pages"><code>server_list</code> 為空的頁</h3>')
    add(tbl["empty"])
    add(p_html(
        "多數樹是 5 級或 10 級；也有 1、2、3、20 級，以及英雄鑄魂底下 1,500 級的樹。"
        "節點消耗、時間與 <code>tech_building_lv</code> 都在明細表，本頁不逐條展開。"
    ))
    add('    <h3 id="unmatched">對不上類型表的樹</h3>')
    add(p_html(
        "明細表另有 28 條樹，<code>tree_id</code> 為 130201–132102 與 140102，對不上類型表任何 id。"
        "這 28 條的說明文鍵是 <code>technology_hero_desc_1</code>–<code>16</code>，"
        "研究所建築條件從 <code>136|30</code> 起（與「英雄」頁類型 101 的 <code>build_lv</code> 相同），"
        "寫入聯盟／部族／自然英雄攻擊、生命、增傷、減傷，以及英雄攻擊／生命、增傷／減傷；"
        "多數列的 1 級與滿級數值都是 100。"
        "表沒有把它們掛到類型欄，本頁只記錄這批樹的存在與寫入，不臆測它們屬於哪一頁。"
    ))
    add(tbl["unmatched"])
    add("    </section>")

    add('    <section id="combat">')
    add("      <h2>與戰鬥相關的寫入（玩家科技）</h2>")
    add(p_html(
        "下面統計本抽取 <code>technology_advanced_detail</code> 實際出現的屬性與數值範圍。"
        "同一屬性可能出現在兩套頁面的不同樹上，戰鬥輸入要對具體 <code>tree_id</code> 與等級，不能只記屬性 id。"
        "數值都是原值，不把 <code>show_type=2</code> 自行換算成百分比。"
    ))
    add(tbl["combat"])
    add(p_html(
        "另有「隊伍英雄為同一陣營時」額外提升的屬性。其中 21023–21028 有官方屬性名，例如 "
        f"21024「{official_term_html(next(r.name for r in data.same_camp if r.attr_id==21024))}」"
        "（本抽取 10 條樹，數值 100–600）、"
        f"21025「{official_term_html(next(r.name for r in data.same_camp if r.attr_id==21025))}」"
        "（7 條樹，50–600）；21026–21028、21023 是同一組的其餘陣營士兵攻擊／生命。"
        "21029–21034 沒有 <code>attribute_name_*</code> 字串，說明文是"
        "「當隊伍中上陣英雄均為同一陣營時，隊伍中所有〔陣營〕英雄攻擊／生命提升」；"
        "除下文英雄鑄魂每級固定寫 10 以外，全表這組屬性的數值範圍是 10–1,000。"
        "21007–21010 在屬性表裡（<code>type=2</code>、<code>show_type=2</code>），"
        "沒有名稱字串，也沒有說明文，本抽取各 10 條樹、數值固定 100，功能不能從本抽取定名。"
        "21035–21037 同樣沒有屬性名，說明文是"
        "「當隊伍中上陣英雄全為〔陣營〕時，英雄出征上限增加」"
        "（<code>type=1</code>、<code>show_type=1</code>）。"
    ))
    add(tbl["same_camp"])
    add(p_html("10103、陣營 13103 等、同一陣營額外屬性 210xx 如何疊加，表沒有公式。"))
    add("    </section>")

    add('    <section id="soul">')
    add("      <h2>英雄鑄魂</h2>")
    add(p_html(
        "類型 20 與 21 都叫「"
        f"{H('英雄鑄魂', terms)}"
        "」，對應兩套伺服器名單。底下可明確對上的是 12 條樹、每條 1,500 級："
        "<code>tree_id</code> 200101–200106（類型 20 那套）與 210101–210106（類型 21 那套）。"
        "每一級都寫同一組屬性、數值固定是 10，說明文是「當隊伍中上陣英雄均為同一陣營時…」："
    ))
    add(tbl["soul"])
    add(p_html(
        "這 12 條樹沒有 <code>technology_adv_name_*</code> 名稱字串。"
        "表沒有再寫這 1,500 級如何取得或有沒有實際上限。"
        "同一組屬性 21029–21034 也出現在其他樹上（數值可到 1,000），"
        "不要把全表這組屬性都當成鑄魂的每級 +10。"
        "本頁不把 1,500 級逐列展開。"
    ))
    add("    </section>")

    add('    <section id="alliance">')
    add("      <h2>聯盟科技（公會科技）</h2>")
    add(p_html(
        "聯盟科技不屬 <code>attr_category</code> 25，屬 14「"
        f"{H(o.guild_name, terms)}"
        "」。<code>alliance_tech.json</code> 756 筆、194 組：140 組為 5 級、52 組為 1 級、2 組為 2 級，"
        "組內等級與 <code>max_level</code> 一致。頁面在 <code>alliance_tech_page.json</code>（5 筆）："
    ))
    add(tbl["alliance_pages"])
    add(p_html(
        "捐獻資源類型在 <code>alliance_tech_restype.json</code>（308 筆），本頁不逐列展開。"
    ))
    add(p_html(
        "<code>effect_type=2</code>（697 筆）時，<code>effect_para</code> 是「屬性 id、數值」。"
        "出現較多的戰鬥寫入如下。計筆以表內 <code>effectParamPairs</code> 為準"
        "（部分列的 <code>effect_para</code> 把兩組寫入擠在同一欄，不能只讀該欄第一個數字）。"
    ))
    add(tbl["alliance_et2"])
    add(p_html(
        "同一 <code>effect_type=2</code> 也寫入 <code>type=1</code> 的 3／4"
        f"（官方名稱是「{official_term_html(o.name_atk_1)}」「{official_term_html(o.name_hp_1)}」，各 30 筆），"
        f"以及 <code>type=1</code> 的 3003「{official_term_html(o.name_3003)}」（5 筆）。"
        "不要和 103／104、3103 混成同一欄。聯盟科技同時寫入這兩組時，公式用哪一組，表沒有標。"
    ))
    add(p_html(
        "<code>effect_type</code> 還有其他值，不要一律當成屬性加成。例如 <code>effect_type=1</code> 的"
        f"「{official_term_html(o.great_guild)}」效果參數是 <code>[3]</code>，說明文是"
        f"「{official_term_html(o.great_guild_des)}」，這裡的 3 不是屬性 3「{H(o.name_atk_1, terms)}」。"
        "<code>effect_type=-1</code> 的 25 筆沒有 <code>effect_para</code>"
        "（例如部分活動獎勵、解鎖公會箭塔）。"
        "<code>effect_type=3／4／5</code> 筆數很少（鑽石福袋、公會商隊、邀請科迪莉亞等），本頁不展開。"
    ))
    add(p_html(
        "部分組沒有 <code>alliance_tech_name_{group_id}</code> 名稱字串，本頁不編造名稱。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add("<li>以太牧場科技（<code>ether_ranch_tech_detail.json</code>）與 KVK 同盟堡壘科技（<code>kvk_alliance_fortress_tech.json</code>）。</li>")
    add(
        f"<li>{H(o.shine_building_name, terms)}（<code>attr_category</code> 32、<code>shine_troop.json</code>）"
        "的士兵基礎值。那不是科技樹。</li>"
    )
    add(
        "<li>841 條樹的完整名稱、消耗、時間與前置鏈（名稱字串也不完整："
        f"<code>technology_adv_name_*</code> 只有 {comma(data.table_meta['adv_name_count'])} 條，對不上全部 <code>tree_id</code>）。</li>"
    )
    add(
        "<li>兩套 <code>server_list</code> 在同一服是否只開一套，以及 11／12、季節頁、光輝科技頁在沒有 "
        "<code>server_list</code> 時如何對伺服器開放。</li>"
    )
    add("<li>英雄鑄魂 1,500 級的實際取得方式與上限。</li>")
    add(
        "<li>10103、陣營士兵／英雄屬性、同一陣營額外屬性 210xx 的疊加公式；"
        "聯盟科技 type=1 的 3／4 與 type=2 的 103／104 並寫時公式用哪一組。</li>"
    )
    add("<li>屬性 21007–21010 的功能，以及光輝科技 1001–1006 的官方頁名。</li>")
    add("<li>科技與英雄、士兵、站位的搭配模擬，以及強弱評定。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<ul>")
    add(f"<li>{_data_notes(data)}</li>")
    add(
        "<li>版本：第 24 章第一版日期 2026-11-15（香港時間）。"
        "依資料表寫出 35 個玩家科技頁的名稱、伺服器名單與建築條件，全表明細的戰鬥屬性統計，"
        "英雄鑄魂 12 條 1,500 級樹，以及聯盟科技的頁面與主要戰鬥寫入。"
        f"{H(o.shine_building_name, terms)}不列入正文主體。</li>"
    )
    add(
        "<li>待補（均未決議，本頁不補寫答案）：樹與頁面的一一對應、兩套伺服器名單的實際開關、"
        "鑄魂 1,500 級的取得方式、光輝科技頁名、21007–21010 的名稱，以及疊加公式。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {TECH_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_tech_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    out: dict[str, str] = {}
    out["class"] = md_table(
        ["id", "名稱", "條件 `condition`", "關閉說明 `close_des`"],
        [
            [str(r.class_id), r.name, r.condition, r.close_des]
            for r in data.class_rows
        ],
    )

    def page_rows(pages: list[TypePage], with_speed: bool, with_season: bool) -> list[list[str]]:
        rows = []
        for p in pages:
            name = _page_name_cell(p, False)
            note = p.note or ""
            if with_speed:
                rows.append([str(p.type_id), name, p.build_lv, p.attr_id, note])
            elif with_season:
                rows.append([str(p.type_id), name, p.build_lv, str(p.season_open), note])
            else:
                rows.append([str(p.type_id), name, p.build_lv, note])
        return rows

    out["set1"] = md_table(
        ["類型 id", "名稱（名稱鍵）", "`build_lv`", "加速屬性", "備註"],
        page_rows(data.set1, True, False),
    )
    out["set2"] = md_table(
        ["類型 id", "名稱（名稱鍵）", "`build_lv`", "加速屬性", "備註"],
        page_rows(data.set2, True, False),
    )
    o = data.official
    shine_note = (
        "`tech_type_name` 為空，無名稱字串。`IsShineTechnology=true`，`brilliance_switch=1`。"
        f"1001–1003 的加速屬性是 1264「{o.speed_1264}」，1004–1006 沒有掛加速屬性。"
        f"字串表另有 `tech_type_name_shine_1`「{o.shine_name_1}」、`tech_type_name_shine_2`「{o.shine_name_2}」，"
        "類型表沒有把這兩個鍵掛上 1001–1006，本頁不自行對號"
    )
    empty_rows = page_rows(data.empty_pages, False, True)
    empty_rows.append(["1001–1006", EMPTY, "169|1", "-1", shine_note])
    out["empty"] = md_table(
        ["類型 id", "名稱", "`build_lv`", "`season_open`", "備註"],
        empty_rows,
    )
    unmatched_rows = []
    for u in data.unmatched:
        attr = f"{u.attr_name}（{u.attr_id}）" if u.attr_name else str(u.attr_id)
        unmatched_rows.append([
            str(u.tree_id),
            str(u.levels),
            attr,
            f"{comma(u.v_first)}／{comma(u.v_last)}",
            u.des or EMPTY,
            u.building_lv,
        ])
    out["unmatched"] = md_table(
        ["樹 id", "級數", "寫入屬性", "1 級／滿級", "說明文", "建築條件"],
        unmatched_rows,
    )
    out["combat"] = md_table(
        ["屬性", "樹數", "數值範圍", "備註"],
        [[_attr_label_md(row), row.tree_text, row.range_text, row.note] for row in data.combat_rows],
    )
    out["same_camp"] = md_table(
        ["屬性 id", "官方屬性名", "樹數", "數值範圍"],
        [[str(r.attr_id), r.name, str(r.trees), fmt_range(r.lo, r.hi)] for r in data.same_camp],
    )
    out["soul"] = md_table(
        ["樹 id（20／21 各一）", "屬性（名稱未定）", "說明文"],
        [[f"{s.tree_20}／{s.tree_21}", str(s.attr_id), s.desc] for s in data.soul_pairs],
    )
    ap_rows = []
    for p in data.alliance_pages:
        other = ""
        if p.page_id == 201:
            other = f"`open_tech` 為 `{p.open_tech}`"
        elif p.page_id == 3:
            other = f"`open_tech` 為 `{p.open_tech}`"
        elif p.page_id == 4:
            other = f"`show` 為 {p.show}"
        elif p.page_id == 101:
            other = "不把 `season=1` 標成未開放"
        name = p.name
        if p.page_id == 101:
            name = f"{name}（名稱鍵 `{p.name_key}`）"
        ap_rows.append([str(p.page_id), name, str(p.is_open), str(p.season), other])
    out["alliance_pages"] = md_table(
        ["頁 id", "名稱", "`is_open`", "`season`", "其他欄"],
        ap_rows,
    )
    out["alliance_et2"] = md_table(
        ["寫入", "屬性 id", "筆數（effect_type=2）"],
        [
            [label, "／".join(str(i) for i in ids), count_text]
            for ids, label, count_text in ALLIANCE_ET2_MENTIONS
        ],
    )
    return out


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    add_lines: list[str] = []
    add = add_lines.append
    add("# Top Heroes Wiki｜科技總表")
    add("")
    add(LEDE)
    add("")
    add(
        "交叉引用：[專武總表](exclusive.html)、[英靈總表](valhalla.html)、[造型總表](skins.html)、"
        "[裝備總表](equipment.html)、[領主裝備總表](lord-equipment.html)、[士兵總表](troops.html)、"
        "[秘寶總表](artifacts.html)、[寵物總表](pets.html)、[符文總表](runes.html)、"
        "[天賦總表](talents.html)、[裝飾物總表](decorations.html)、[城堡外觀總表](castle.html)。"
    )
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "本頁主體是玩家科技"
        f"（`attr_category` 25，官方名稱「{o.tech_name}」，提示「{o.tech_dec}」）。"
        "定義頁在 `technology_advanced_type.json`（35 筆），"
        "節點在 `technology_advanced_detail.json`（24,104 筆、841 條樹）。"
        "分類表 `technology_classfication.json` 只有兩類（檔名少一個 i）。"
    )
    add("")
    add(
        "公會科技是另一個來源分類"
        f"（`attr_category` 14，官方名稱「{o.guild_name}」，提示「{o.guild_dec}」），"
        "表在 `alliance_tech.json` 等，下文另節登錄，不要與玩家科技混成同一欄。"
    )
    add("")
    add(
        f"{o.shine_building_name}（`attr_category` 32，提示「{o.shine_building_dec}」）不是科技樹，也不在本頁正文展開。"
        f"本抽取另有光輝科技頁（類型 1001–1006，`IsShineTechnology=true`，前置建築 169「{o.building_169}」），"
        "與光輝建築不是同一分類，見下文。"
    )
    add("")
    add("- **正文只根據遊戲資料表。** 不把玩家討論寫進正文。明細表沒有「類型」外鍵，不能由 `tree_id` 前綴唯一對回 35 個頁面（前綴會重疊，例如 20xxxx 既可能讀成類型 20，也可能讀成類型 202）。本頁以類型表列出頁面，戰鬥相關寫入改按全表明細做屬性統計，不把每條樹強行劃進某一頁。")
    add(f"- **屬性名**優先用 `attribute_name_{{id}}`。`show_type=2` 只記表內原值，不自行換算成百分比。不要把 `type=1` 與 `type=2` 的同名屬性混成同一欄：例如「{o.name_atk_1}／{o.name_hp_1}」是 3／4（`type=1`、`show_type=1`），「{o.name_hero_atk}／{o.name_hero_hp}」是 103／104（`type=2`、`show_type=2`）；「{o.name_3003}」既有 3003（`type=1`）也有 3103（`type=2`）。玩家科技寫的陣營英雄攻擊／生命是 3103／3104 這組 `type=2`。")
    add("- **不要從 `unlocktime`、`season` 或 `season_open` 自動標未開放。** 季節頁的 `season_open` 只照錄。")
    add(f"- 類型表的 `attribute_id`／`AttrNameList` 掛的是頁面加速屬性：1152 {o.speed_1152}、1153 {o.speed_1153}、1154 {o.speed_1154}、1155 {o.speed_1155}，以及 1264 {o.speed_1264}。這些是研究加速，不是戰鬥攻擊。")
    add(f"- 節點消耗與時間、研究所建築等級寫在明細表。前置建築實際出現的是 136「{o.building_136}」（`citybuilding_name_136`，說明「{o.building_136_des}」）與 169「{o.building_169}」（說明「{o.building_169_des}」）。屬性分類提示寫的是「研究所」，與建築正式名「研究院」用字不同，兩種寫法都照錄。")
    add("")
    add("## 訓練分類")
    add("")
    add("`technology_classfication.json` 兩筆：")
    add("")
    add(tbl["class"])
    add("")
    add("關閉說明是字串表原文，本頁不拆成兩句，也不把「全英雄攻擊增加」寫成已驗證的開啟效果。條件 `1|2402|1` 在分類表沒有再說明，本頁不自行解釋。這張表與 35 個進階科技頁之間沒有外鍵，本頁不把頁面劃進「普通／進階訓練」。")
    add("")
    add("## 頁面與伺服器名單")
    add("")
    add(f"類型表用 `server_list` 把同一名稱的頁面分成兩套。本頁只按表列出名單，不另外推哪一個客戶端開關會覆蓋這份名單。`build_lv` 是該頁要求的{o.building_136}（136）或{o.building_169}（169）等級。")
    add("")
    add("### 第一套 `server_list`")
    add("")
    add("第一套 `server_list` 含 1、6、11、13、15–999、1001–1004、10001–10107：")
    add("")
    add(tbl["set1"])
    add("")
    add("### 第二套 `server_list`")
    add("")
    add("第二套 `server_list` 含 2–5、7–9、12、14、1005–9999、10108–99999（類型 20 的名單略有不同，見該列）：")
    add("")
    add(tbl["set2"])
    add("")
    add("### `server_list` 為空的頁")
    add("")
    add(tbl["empty"])
    add("")
    add("多數樹是 5 級或 10 級；也有 1、2、3、20 級，以及英雄鑄魂底下 1,500 級的樹。節點消耗、時間與 `tech_building_lv` 都在明細表，本頁不逐條展開。")
    add("")
    add("### 對不上類型表的樹")
    add("")
    add("明細表另有 28 條樹，`tree_id` 為 130201–132102 與 140102，對不上類型表任何 id。這 28 條的說明文鍵是 `technology_hero_desc_1`–`16`，研究所建築條件從 `136|30` 起（與「英雄」頁類型 101 的 `build_lv` 相同），寫入聯盟／部族／自然英雄攻擊、生命、增傷、減傷，以及英雄攻擊／生命、增傷／減傷；多數列的 1 級與滿級數值都是 100。表沒有把它們掛到類型欄，本頁只記錄這批樹的存在與寫入，不臆測它們屬於哪一頁。")
    add("")
    add(tbl["unmatched"])
    add("")
    add("## 與戰鬥相關的寫入（玩家科技）")
    add("")
    add("下面統計本抽取 `technology_advanced_detail` 實際出現的屬性與數值範圍。同一屬性可能出現在兩套頁面的不同樹上，戰鬥輸入要對具體 `tree_id` 與等級，不能只記屬性 id。數值都是原值，不把 `show_type=2` 自行換算成百分比。")
    add("")
    add(tbl["combat"])
    add("")
    n24 = next(r for r in data.same_camp if r.attr_id == 21024)
    n25 = next(r for r in data.same_camp if r.attr_id == 21025)
    add(
        f"另有「隊伍英雄為同一陣營時」額外提升的屬性。其中 21023–21028 有官方屬性名，例如 21024「{n24.name}」（本抽取 10 條樹，數值 100–600）、21025「{n25.name}」（7 條樹，50–600）；21026–21028、21023 是同一組的其餘陣營士兵攻擊／生命。21029–21034 沒有 `attribute_name_*` 字串，說明文是「當隊伍中上陣英雄均為同一陣營時，隊伍中所有〔陣營〕英雄攻擊／生命提升」；除下文英雄鑄魂每級固定寫 10 以外，全表這組屬性的數值範圍是 10–1,000。21007–21010 在屬性表裡（`type=2`、`show_type=2`），沒有名稱字串，也沒有說明文，本抽取各 10 條樹、數值固定 100，功能不能從本抽取定名。21035–21037 同樣沒有屬性名，說明文是「當隊伍中上陣英雄全為〔陣營〕時，英雄出征上限增加」（`type=1`、`show_type=1`）。"
    )
    add("")
    add(tbl["same_camp"])
    add("")
    add("10103、陣營 13103 等、同一陣營額外屬性 210xx 如何疊加，表沒有公式。")
    add("")
    add("## 英雄鑄魂")
    add("")
    add("類型 20 與 21 都叫「英雄鑄魂」，對應兩套伺服器名單。底下可明確對上的是 12 條樹、每條 1,500 級：`tree_id` 200101–200106（類型 20 那套）與 210101–210106（類型 21 那套）。每一級都寫同一組屬性、數值固定是 10，說明文是「當隊伍中上陣英雄均為同一陣營時…」：")
    add("")
    add(tbl["soul"])
    add("")
    add("這 12 條樹沒有 `technology_adv_name_*` 名稱字串。表沒有再寫這 1,500 級如何取得或有沒有實際上限。同一組屬性 21029–21034 也出現在其他樹上（數值可到 1,000），不要把全表這組屬性都當成鑄魂的每級 +10。本頁不把 1,500 級逐列展開。")
    add("")
    add("## 聯盟科技（公會科技）")
    add("")
    add(f"聯盟科技不屬 `attr_category` 25，屬 14「{o.guild_name}」。`alliance_tech.json` 756 筆、194 組：140 組為 5 級、52 組為 1 級、2 組為 2 級，組內等級與 `max_level` 一致。頁面在 `alliance_tech_page.json`（5 筆）：")
    add("")
    add(tbl["alliance_pages"])
    add("")
    add("捐獻資源類型在 `alliance_tech_restype.json`（308 筆），本頁不逐列展開。")
    add("")
    add("`effect_type=2`（697 筆）時，`effect_para` 是「屬性 id、數值」。出現較多的戰鬥寫入如下。計筆以表內 `effectParamPairs` 為準（部分列的 `effect_para` 把兩組寫入擠在同一欄，不能只讀該欄第一個數字）。")
    add("")
    add(tbl["alliance_et2"])
    add("")
    add(f"同一 `effect_type=2` 也寫入 `type=1` 的 3／4（官方名稱是「{o.name_atk_1}」「{o.name_hp_1}」，各 30 筆），以及 `type=1` 的 3003「{o.name_3003}」（5 筆）。不要和 103／104、3103 混成同一欄。聯盟科技同時寫入這兩組時，公式用哪一組，表沒有標。")
    add("")
    add(f"`effect_type` 還有其他值，不要一律當成屬性加成。例如 `effect_type=1` 的「{o.great_guild}」效果參數是 `[3]`，說明文是「{o.great_guild_des}」，這裡的 3 不是屬性 3「{o.name_atk_1}」。`effect_type=-1` 的 25 筆沒有 `effect_para`（例如部分活動獎勵、解鎖公會箭塔）。`effect_type=3／4／5` 筆數很少（鑽石福袋、公會商隊、邀請科迪莉亞等），本頁不展開。")
    add("")
    add("部分組沒有 `alliance_tech_name_{group_id}` 名稱字串，本頁不編造名稱。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 以太牧場科技（`ether_ranch_tech_detail.json`）與 KVK 同盟堡壘科技（`kvk_alliance_fortress_tech.json`）。")
    add(f"- {o.shine_building_name}（`attr_category` 32、`shine_troop.json`）的士兵基礎值。那不是科技樹。")
    add(f"- 841 條樹的完整名稱、消耗、時間與前置鏈（名稱字串也不完整：`technology_adv_name_*` 只有 {comma(data.table_meta['adv_name_count'])} 條，對不上全部 `tree_id`）。")
    add("- 兩套 `server_list` 在同一服是否只開一套，以及 11／12、季節頁、光輝科技頁在沒有 `server_list` 時如何對伺服器開放。")
    add("- 英雄鑄魂 1,500 級的實際取得方式與上限。")
    add("- 10103、陣營士兵／英雄屬性、同一陣營額外屬性 210xx 的疊加公式；聯盟科技 type=1 的 3／4 與 type=2 的 103／104 並寫時公式用哪一組。")
    add("- 屬性 21007–21010 的功能，以及光輝科技 1001–1006 的官方頁名。")
    add("- 科技與英雄、士兵、站位的搭配模擬，以及強弱評定。")
    add("")
    add("## 資料說明")
    add("")
    add(_data_notes(data).replace("`", "`"))
    add("")
    add(f"版本：第 24 章第一版日期 2026-11-15（香港時間）。依資料表寫出 35 個玩家科技頁的名稱、伺服器名單與建築條件，全表明細的戰鬥屬性統計，英雄鑄魂 12 條 1,500 級樹，以及聯盟科技的頁面與主要戰鬥寫入。{o.shine_building_name}不列入正文主體。")
    add("")
    add("待補（均未決議，本頁不補寫答案）：樹與頁面的一一對應、兩套伺服器名單的實際開關、鑄魂 1,500 級的取得方式、光輝科技頁名、21007–21010 的名稱，以及疊加公式。")
    add("")
    return "\n".join(add_lines)
