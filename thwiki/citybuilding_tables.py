"""Compile the published 城建升級 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .highlight import highlight
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT

# 本頁截止為 2026-11-22：主表只在當日 LocalLow／live。不改 paths.DATA_CUTOFF。
EXTRACT_DIR = TOPHEROES_ROOT / "extracts/2026-11-22-locallow"
EXTRACT_DATA = EXTRACT_DIR / "data"
EXTRACT_STRINGS = EXTRACT_DIR / "strings_zh.json"

PAGE_CUTOFF = "2026-11-22"
PACKAGE_NAME = "app-1.129.12_table-1.0.43173"
ZIP_TIME_RANGE = "2026-11-22 23:33:08–23:33:20"

MAIN_COUNT = 126
LVUP_COUNT = 7973
LVUP_NEW_COUNT = 8032
LVUP_NEW_ONLY = 59
SHARED_FIELD_DIFFS = 2818
FUNCTION_COUNT = 5
GUIDEBOOK_COUNT = 80
REWARD_COUNT = 238
REWARD_ID_COUNT = 16
PRODUCTION_COUNT = 20
CIV_COUNT = 81
SWORD_COUNT = 82
WAR_COUNT = 66
CUTOFF_VS_1105_DIFFS = 42

TABLE_SHA256 = {
    "citybuilding.json": "25dc79829dcc0888168e76fe7f2bd5cb9d4dc97df6cecdc98b6e01cb24c24a0f",
    "citybuilding_lvup.json": "2d85b94154e3a0f6f481805d49bace3e8ee8eccd84dfae79ac938743e75724d3",
    "citybuilding_lvup_new.json": "436ca7dcdba0f5aa962cfbbb728fd4b9d9ac3a3042154a2ec3e5c43a60158abf",
    "citybuilding_function.json": "96adcfc21a4bc6de901598b03226ca1fdc1deb638c1a5d8f7f6775eb825f5239",
    "citybuilding_guidebook.json": "8d7090c48551f60ad8249a7ca85a7f53182d6f2c9b00b5bb73977598438580d2",
    "guidebook_reward.json": "08f8045ab9d353b3431f44d05b0592d8d4d6eba02c0c968b9c45e73d43a3cb76",
    "citybuild_production.json": "5541aab3840d870ed1501ac4c8e280c7113adc30c354eda21ba1cabcf5fae246",
    "citybuild_civilization_hall.json": "86b02a0b8a12ba72c083779d7fae4457c9218271d52cac437d9efac994de107d",
    "citybuild_kingdom_sword.json": "0595d4a929a49e09a5fa3e685e84205631695dcb4afbfb735ff77ff29b4fa626",
    "citybuild_war_center.json": "2807705e068515c941041485c96d9e32412aa5c3b662fda79ec62338fec88890",
}

STRINGS_SHA256 = "249e08f64922de78527d6669912e4202fd650d1bd2434e47c89351d123da0134"
STRINGS_KEY_COUNT = 40581

PACK_DATA_DIRS = {
    "live": DATA_DIR,
    "2026-11-05": TOPHEROES_ROOT / "extracts/2026-11-05/data",
    "2026-11-22": TOPHEROES_ROOT / "extracts/2026-11-22/data",
    "2026-11-22-locallow": EXTRACT_DATA,
}
PACK_STRINGS = {
    "live": STRINGS_PATH,
    "2026-11-05": TOPHEROES_ROOT / "extracts/2026-11-05/strings_zh.json",
    "2026-11-22": TOPHEROES_ROOT / "extracts/2026-11-22/strings_zh.json",
    "2026-11-22-locallow": EXTRACT_STRINGS,
}

# 已公開圖鑑頁；職業大廳連到領主職業頁。
BUILDING_LINKS = {
    140: "artifacts.html",
    155: "artifacts.html",
    160: "pets.html",
    178: "holybeasts.html",
    179: "lord-occupations.html",
    183: "pals.html",
}

LVUP_EXTRA_EMPTY_FIELDS = (
    "costList", "preBuild", "paramDatas", "descs", "icons", "showTypes",
    "attrArray", "offlineList", "string_params_1", "string_params_2",
    "group2_string_params_1", "group2_string_params_2",
)

USED_KEYS: set[str] = set()
STRINGS: dict = {}

MISSING_TEXT = "字串表沒有內容"
EMPTY_DES_FIELD = "該列 des 欄為空"


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def official_text(key, default: str = "") -> str:
    """Return the official string exactly as stored. Do not strip tags or rewrite glyphs."""
    if key is None or key == "":
        return default
    USED_KEYS.add(str(key))
    value = STRINGS.get(str(key))
    if value is None:
        return default
    return value


def has_string(key) -> bool:
    if key is None or key == "":
        return False
    return str(key) in STRINGS


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def load_extract_table(name: str):
    path = EXTRACT_DATA / name
    expected = TABLE_SHA256.get(name)
    if expected:
        actual = file_sha256(path)
        if actual != expected:
            raise RuntimeError(f"{name} sha256 mismatch: {actual} != {expected}")
    return load_json(path)


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def raw_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def code_json(value) -> str:
    return f"<code>{e(raw_json(value))}</code>"


SRC_OLD = "原升級表"
SRC_NEW = "新升級表"
SRC_LABEL = {"lvup": SRC_OLD, "lvup_new": SRC_NEW}
VISIBLE_EMPTY_DES = "該列沒有說明"


def _as_segments(value):
    if not is_filled(value):
        return []
    if isinstance(value, list):
        if value and isinstance(value[0], (list, tuple)):
            return [list(x) for x in value]
        if value and isinstance(value[0], str) and "|" in value[0]:
            segs = []
            for item in value:
                parts = str(item).split("|")
                segs.append(parts)
            return segs
        if len(value) >= 3 and all(not isinstance(x, (list, tuple)) for x in value):
            return [list(value)]
        return [value]
    if isinstance(value, str) and "|" in value:
        return [value.split("|")]
    return [value]


def fmt_cost_segment(seg, terms: list[str]) -> str:
    if isinstance(seg, str):
        parts = seg.split("|")
    elif isinstance(seg, (list, tuple)):
        parts = list(seg)
    else:
        return e(raw_json(seg))
    if len(parts) < 3:
        return e(raw_json(seg) if not isinstance(seg, str) else seg)
    typ, mid, qty = parts[0], parts[1], parts[2]
    try:
        typ_n = int(typ)
    except (TypeError, ValueError):
        typ_n = typ
    if typ_n == 2:
        try:
            item_id = int(mid)
        except (TypeError, ValueError):
            item_id = mid
        name = official_text(f"goods_name_{item_id}") if isinstance(item_id, int) else ""
        if name:
            return f"{H(name, terms)} ×{e(str(qty))}"
        return f"類型 2、道具 {e(str(mid))}、數量 {e(str(qty))}"
    if typ_n == 999:
        return f"類型 999、第 {e(str(mid))} 段、數量 {e(str(qty))}"
    return f"類型 {e(str(typ))}、第 {e(str(mid))} 段、數量 {e(str(qty))}"


def fmt_cost_value(value, terms: list[str]) -> str:
    segs = _as_segments(value)
    if not segs:
        return "（空）"
    return "、".join(fmt_cost_segment(seg, terms) for seg in segs)


def fmt_costs_row(row: dict, terms: list[str]) -> str:
    parts = [fmt_cost_value(row.get(key), terms) for key in ("cost1", "cost2", "cost3", "cost4") if is_filled(row.get(key))]
    return "、".join(parts) if parts else "（空）"


def fmt_prereq(value, buildings: dict[int, "Building"], terms: list[str]) -> str:
    if not is_filled(value):
        return "（空）"
    items = value if isinstance(value, list) else [value]
    bits = []
    for item in items:
        s = str(item)
        if "|" in s:
            bid_s, lv_s = s.split("|", 1)
            try:
                bid = int(bid_s)
            except ValueError:
                bits.append(e(s))
                continue
            b = buildings.get(bid)
            if b:
                bits.append(f"{linked_name(bid, b.name, terms)} {e(lv_s)} 級")
            else:
                bits.append(f"{bid} {e(lv_s)} 級")
        else:
            bits.append(e(s))
    return "、".join(bits)


def fmt_para_list(value, terms: list[str]) -> str:
    if not is_filled(value):
        return ""
    items = value if isinstance(value, list) else [value]
    bits = []
    for item in items:
        s = str(item)
        parts = s.split("|")
        if len(parts) >= 2:
            try:
                aid = int(parts[0])
            except ValueError:
                bits.append(e(s))
                continue
            name = official_text(f"attribute_name_{aid}")
            raw = parts[1]
            if name:
                bits.append(f"{H(name, terms)} {e(str(raw))}")
            else:
                bits.append(f"屬性 {aid}、原值 {e(str(raw))}")
        else:
            bits.append(e(s))
    return "、".join(bits)


def fmt_effect_params(row: dict, terms: list[str], *, include_para1: bool, include_group2: bool) -> str:
    bits = []
    if include_para1 and row.get("para1") not in (None, ""):
        bits.append(f"參數 {e(str(row.get('para1')))}")
    sp = fmt_para_list(row.get("string_para2"), terms)
    if sp:
        bits.append(sp)
    if include_group2:
        g2 = fmt_para_list(row.get("group2_string_para2"), terms)
        if g2 and g2 != sp:
            bits.append(f"另一組：{g2}")
    return "；".join(bits) if bits else "（空）"



def is_filled(value) -> bool:
    return value not in (None, "", [], {}, -1)


def expected_row_id(index: int, lv: int) -> int:
    if index == 140:
        if lv <= 40:
            return index * 1000 + lv
        return index * 10000 + lv
    if index == 155:
        return index * 10000 + lv
    if index in (160, 198):
        return index * 1000 + lv + 1
    return index * 1000 + lv


def verify_row_ids(rows, label: str) -> None:
    bad = [r for r in rows if r["id"] != expected_row_id(int(r["index"]), int(r["lv"]))]
    if bad:
        sample = ", ".join(f"{r['id']} (index {r['index']} lv {r['lv']})" for r in bad[:5])
        raise RuntimeError(f"{label} row-id rule mismatch ({len(bad)}): {sample}")


def cost_pattern(row: dict) -> tuple[bool, bool, bool, bool]:
    return tuple(is_filled(row.get(c)) for c in ("cost1", "cost2", "cost3", "cost4"))


def linked_name(bid: int, name: str, terms: list[str]) -> str:
    inner = H(name, terms)
    href = BUILDING_LINKS.get(bid)
    if href:
        return f'<a href="{e(href)}">{inner}</a>'
    return inner


def name_of(buildings: dict[int, "Building"], bid: int, terms: list[str]) -> str:
    b = buildings.get(bid)
    if b:
        return f"{bid} {linked_name(bid, b.name, terms)}"
    return str(bid)

@dataclass
class Building:
    bid: int
    name_key: str
    des_key: str
    name: str
    des: str
    des_status: str  # "ok" | "missing" | "empty-field"
    typ: int
    new_type: int
    maxlevel: int
    new_maxlevel: int
    lvupid: int
    is_discard: int
    is_building_list: int
    initlevel: int
    count: int
    function: object
    server_list: object
    season: object
    is_guidebook_active: object
    guidebook_arrange: object


@dataclass
class TablesData:
    buildings: list[Building]
    by_id: dict[int, Building]
    functions: list[tuple[int, str, str]]
    lvup: list[dict]
    lvup_new: list[dict]
    production: list[dict]
    guidebook: list[dict]
    rewards: list[dict]
    civ: list[dict]
    sword: list[dict]
    war: list[dict]
    terms: list[str]
    table_meta: dict = field(default_factory=dict)


def _lv_range(rows: list[dict], index: int) -> tuple[int, int, int]:
    lvs = [int(r["lv"]) for r in rows if int(r["index"]) == index]
    if not lvs:
        raise RuntimeError(f"no upgrade rows for index {index}")
    return min(lvs), max(lvs), len(lvs)


def _rows_for(rows: list[dict], index: int) -> list[dict]:
    return sorted((r for r in rows if int(r["index"]) == index), key=lambda r: int(r["lv"]))


def _common_field_diff_count(lvup: list[dict], lvup_new: list[dict]) -> int:
    common = set(lvup[0].keys()) & set(lvup_new[0].keys())
    old = {r["id"]: r for r in lvup}
    n = 0
    for row in lvup_new:
        other = old.get(row["id"])
        if other is None:
            continue
        if any(other.get(k) != row.get(k) for k in common):
            n += 1
    return n


def _shine_summary(rows: list[dict]) -> dict:
    by: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by[int(r["index"])].append(r)
    from41_0: list[int] = []
    from45_1: list[int] = []
    for idx, group in by.items():
        values = {int(r["lv"]): r.get("shine_lv") for r in group}
        if values.get(41) == 0:
            from41_0.append(idx)
        if values.get(45) == 1:
            from45_1.append(idx)
    return {"from41_0": sorted(from41_0), "from45_1": sorted(from45_1)}


def _pack_table_info(name: str) -> dict:
    info = {"exists": {}, "sha256": {}, "identical": {}}
    for label, folder in PACK_DATA_DIRS.items():
        path = folder / name
        exists = path.is_file()
        info["exists"][label] = exists
        if exists:
            info["sha256"][label] = file_sha256(path)
    base = info["sha256"].get("2026-11-22-locallow")
    for label, digest in info["sha256"].items():
        info["identical"][label] = digest == base
    return info


def compare_cutoff_diffs(old_rows: list[dict], new_rows: list[dict]) -> dict:
    old = {r["id"]: r for r in old_rows}
    new = {r["id"]: r for r in new_rows}
    changed = []
    fields: set[str] = set()
    for rid in sorted(set(old) & set(new)):
        if old[rid] != new[rid]:
            ch = sorted(k for k in set(old[rid]) | set(new[rid]) if old[rid].get(k) != new[rid].get(k))
            fields.update(ch)
            changed.append((rid, int(new[rid]["index"]), int(new[rid]["lv"]), ch, old[rid], new[rid]))
    return {
        "only_old": sorted(set(old) - set(new)),
        "only_new": sorted(set(new) - set(old)),
        "changed": changed,
        "fields": sorted(fields),
        "indexes": dict(Counter(item[1] for item in changed)),
    }


NARRATIVE_KEYS = (
    "attribute_name_1237", "attribute_name_1500106", "attribute_name_1012",
    "attribute_name_1014", "attribute_name_1123", "artifact_atk_up", "artifact_hp_up",
    "uilding_lvup_des_115003", "building_lvup_des_115003",
    "building_lvup_des_141001", "building_lvup_des_xianzututeng",
    "goods_name_101", "goods_name_102", "goods_name_153", "goods_desc_153",
    "goods_name_237", "goods_desc_237", "goods_name_1044", "goods_desc_1044",
    "building_villager_tips_106", "building_villager_tips_107",
    "building_villager_tips_110", "building_villager_tips_168",
    "pre_building_level_2_desc_117", "pre_building_level_3_desc_117",
    "pre_building_level_4_desc_117", "pre_building_level_5_desc_117",
    "pre_building_level_2_desc_117_tips", "pre_building_level_3_desc_117_tips",
    "pre_building_level_4_desc_117_tips", "pre_building_level_5_desc_117_tips",
    "citybuilding_lvup_condition003", "citybuilding_lvup_pre_condition",
    "citybuilding_requirement_2", "citybuilding_production_list_full",
    "citybuilding_production_not_enough", "citybuilding_name_168", "citybuilding_des_168",
    "citybuilding_name_6_2", "citybuilding_name_8", "citybuilding_name_134",
    "citybuilding_name_202", "citybuilding_name_203", "citybuilding_name_204",
)

MISSING_TRACK_KEYS = (
    "attribute_name_1500107",
    "citybuilding_des_11", "citybuilding_des_144", "citybuilding_des_151",
    "citybuilding_des_157", "citybuilding_des_204",
)

def load_tables_data() -> TablesData:
    global STRINGS, USED_KEYS
    USED_KEYS = set()
    if not EXTRACT_STRINGS.is_file():
        raise RuntimeError(f"missing LocalLow strings: {EXTRACT_STRINGS}")
    actual_strings = file_sha256(EXTRACT_STRINGS)
    if actual_strings != STRINGS_SHA256:
        raise RuntimeError(f"strings_zh.json sha256 mismatch: {actual_strings} != {STRINGS_SHA256}")
    STRINGS = load_json(EXTRACT_STRINGS)
    if len(STRINGS) != STRINGS_KEY_COUNT:
        raise RuntimeError(f"strings_zh.json key count {len(STRINGS)} != {STRINGS_KEY_COUNT}")

    main = load_extract_table("citybuilding.json")
    lvup = load_extract_table("citybuilding_lvup.json")
    lvup_new = load_extract_table("citybuilding_lvup_new.json")
    functions_raw = load_extract_table("citybuilding_function.json")
    guidebook = load_extract_table("citybuilding_guidebook.json")
    rewards = load_extract_table("guidebook_reward.json")
    production = load_extract_table("citybuild_production.json")
    civ = load_extract_table("citybuild_civilization_hall.json")
    sword = load_extract_table("citybuild_kingdom_sword.json")
    war = load_extract_table("citybuild_war_center.json")

    counts = {
        "citybuilding.json": (main, MAIN_COUNT),
        "citybuilding_lvup.json": (lvup, LVUP_COUNT),
        "citybuilding_lvup_new.json": (lvup_new, LVUP_NEW_COUNT),
        "citybuilding_function.json": (functions_raw, FUNCTION_COUNT),
        "citybuilding_guidebook.json": (guidebook, GUIDEBOOK_COUNT),
        "guidebook_reward.json": (rewards, REWARD_COUNT),
        "citybuild_production.json": (production, PRODUCTION_COUNT),
        "citybuild_civilization_hall.json": (civ, CIV_COUNT),
        "citybuild_kingdom_sword.json": (sword, SWORD_COUNT),
        "citybuild_war_center.json": (war, WAR_COUNT),
    }
    for name, (rows, expected) in counts.items():
        if len(rows) != expected:
            raise RuntimeError(f"{name} rows {len(rows)} != {expected}")

    verify_row_ids(lvup, "citybuilding_lvup.json")
    verify_row_ids(lvup_new, "citybuilding_lvup_new.json")

    buildings: list[Building] = []
    for row in main:
        name_key = row.get("name") or ""
        des_key = row.get("des") or ""
        name = official_text(name_key)
        if not name_key or not has_string(name_key):
            raise RuntimeError(f"building {row.get('id')} missing official name for key {name_key!r}")
        if not des_key:
            des = ""
            des_status = "empty-field"
        elif not has_string(des_key):
            des = ""
            des_status = "missing"
            USED_KEYS.add(str(des_key))
        else:
            des = official_text(des_key)
            des_status = "ok"
        buildings.append(Building(
            bid=int(row["id"]),
            name_key=str(name_key),
            des_key=str(des_key) if des_key else "",
            name=name,
            des=des,
            des_status=des_status,
            typ=int(row["type"]),
            new_type=int(row["new_type"]),
            maxlevel=int(row["maxlevel"]),
            new_maxlevel=int(row["new_maxlevel"]),
            lvupid=int(row["lvupid"]),
            is_discard=int(row["is_discard"]),
            is_building_list=int(row["is_building_list"]),
            initlevel=int(row["initlevel"]),
            count=int(row["count"]),
            function=row.get("function"),
            server_list=row.get("server_list"),
            season=row.get("season"),
            is_guidebook_active=row.get("is_guidebook_active"),
            guidebook_arrange=row.get("guidebook_arrange"),
        ))
    by_id = {b.bid: b for b in buildings}
    if len(by_id) != len(buildings):
        raise RuntimeError("duplicate citybuilding id")

    functions = []
    for row in functions_raw:
        key = row["name"]
        functions.append((int(row["id"]), str(key), official_text(key)))

    for key in NARRATIVE_KEYS:
        official_text(key)
    for key in MISSING_TRACK_KEYS:
        if has_string(key):
            official_text(key)
        else:
            USED_KEYS.add(key)

    reward_ids = sorted({int(r["reward_id"]) for r in rewards})
    if len(reward_ids) != REWARD_ID_COUNT:
        raise RuntimeError(f"unique reward_id count {len(reward_ids)} != {REWARD_ID_COUNT}")
    for rid in reward_ids:
        des_key = f"goods_des_{rid}"
        icon_key = f"chat_icon_{rid}"
        if not has_string(des_key) or not has_string(icon_key):
            raise RuntimeError(f"reward {rid} missing {des_key} or {icon_key}")
        official_text(des_key)
        official_text(icon_key)
        for absent in (f"goods_name_{rid}", f"goods_desc_{rid}"):
            if has_string(absent):
                official_text(absent)

    ids_lvup = {r["id"] for r in lvup}
    ids_new = {r["id"] for r in lvup_new}
    only_new = [r for r in lvup_new if r["id"] not in ids_lvup]
    only_old = [r for r in lvup if r["id"] not in ids_new]
    if only_old:
        raise RuntimeError(f"lvup has unexpected extra ids: {len(only_old)}")
    if len(only_new) != LVUP_NEW_ONLY:
        raise RuntimeError(f"lvup_new-only rows {len(only_new)} != {LVUP_NEW_ONLY}")
    only_by_index = Counter(int(r["index"]) for r in only_new)
    expected_only = {106: 10, 107: 10, 114: 39}
    if dict(only_by_index) != expected_only:
        raise RuntimeError(f"lvup_new-only indexes {dict(only_by_index)} != {expected_only}")

    shared_diffs = _common_field_diff_count(lvup, lvup_new)
    if shared_diffs != SHARED_FIELD_DIFFS:
        raise RuntimeError(f"shared-field diffs {shared_diffs} != {SHARED_FIELD_DIFFS}")

    idx_lvup = {int(r["index"]) for r in lvup}
    idx_new = {int(r["index"]) for r in lvup_new}
    main_ids = {b.bid for b in buildings}
    if idx_lvup != idx_new:
        raise RuntimeError("upgrade table index sets differ")
    if main_ids - idx_lvup != {103}:
        raise RuntimeError(f"unexpected main ids missing from upgrade tables: {sorted(main_ids - idx_lvup)}")
    if idx_lvup - main_ids:
        raise RuntimeError(f"upgrade indexes not in main table: {sorted(idx_lvup - main_ids)}")

    table_cmp = {name: _pack_table_info(name) for name in TABLE_SHA256}
    pack_strings = {label: load_json(path) for label, path in PACK_STRINGS.items() if path.is_file()}
    string_cmp = {
        "sha256": {label: file_sha256(path) for label, path in PACK_STRINGS.items() if path.is_file()},
        "keys": {label: len(data) for label, data in pack_strings.items()},
        "used_keys": len(USED_KEYS),
        "value_diffs": {},
        "missing": {},
    }
    value_diffs = {}
    missing = {}
    for key in sorted(USED_KEYS):
        present = {label: key in data for label, data in pack_strings.items()}
        if not all(present.values()):
            missing[key] = [label for label, ok in present.items() if not ok]
        values = {label: data.get(key) for label, data in pack_strings.items() if key in data}
        unique = {json.dumps(v, ensure_ascii=False) for v in values.values()}
        if len(unique) > 1:
            value_diffs[key] = values
    string_cmp["value_diffs"] = value_diffs
    string_cmp["missing"] = missing

    cutoff_lvup = None
    cutoff_new = None
    old_lvup_path = PACK_DATA_DIRS["2026-11-05"] / "citybuilding_lvup.json"
    old_new_path = PACK_DATA_DIRS["2026-11-05"] / "citybuilding_lvup_new.json"
    if old_lvup_path.is_file():
        cutoff_lvup = compare_cutoff_diffs(load_json(old_lvup_path), lvup)
        if len(cutoff_lvup["changed"]) != CUTOFF_VS_1105_DIFFS:
            raise RuntimeError(f"lvup 11-05 diffs {len(cutoff_lvup['changed'])} != {CUTOFF_VS_1105_DIFFS}")
    if old_new_path.is_file():
        cutoff_new = compare_cutoff_diffs(load_json(old_new_path), lvup_new)
        if len(cutoff_new["changed"]) != CUTOFF_VS_1105_DIFFS:
            raise RuntimeError(f"lvup_new 11-05 diffs {len(cutoff_new['changed'])} != {CUTOFF_VS_1105_DIFFS}")

    goods_ids = set()
    goods_rows = None
    goods_path = EXTRACT_DATA / "goods.json"
    if goods_path.is_file():
        goods = load_json(goods_path)
        goods_rows = len(goods) if isinstance(goods, list) else len(goods)
        if isinstance(goods, list):
            for item in goods:
                if isinstance(item, dict) and "id" in item:
                    goods_ids.add(int(item["id"]))
        elif isinstance(goods, dict):
            for key in goods:
                try:
                    goods_ids.add(int(key))
                except (TypeError, ValueError):
                    continue
    reward_in_goods = [rid for rid in reward_ids if rid in goods_ids]

    used_name_keys = {b.name_key for b in buildings}
    extra_name_keys = sorted(
        ((key, value) for key, value in STRINGS.items() if key.startswith("citybuilding_name_") and key not in used_name_keys),
        key=lambda x: x[0],
    )

    terms_set = {
        "部族", "功勳碑", "勛章", "秘寶大廳", "職業大廳", "先祖圖騰",
        "秘寶屬性轉化率", "全體英雄防禦", "木板", "原石", "巨龍精華", "魔紋石", "先祖魂石",
        "木板工坊", "石頭工坊", "每日免費城邦遷城次數", "伐木場產量加成", "石礦場產量加成",
        "水晶礦產量提升", "秘寶攻擊放大率", "秘寶生命放大率", "工人數", "魔法塵埃產量",
        "冰封之焰賽季", "寵物樂園", "帕魯營地", "魔獸祭壇", "城堡外觀", "裝飾物", "圖鑑點",
    }
    for b in buildings:
        if b.bid != 111:
            terms_set.add(b.name)
    for _fid, _key, fname in functions:
        # Do not highlight short generic function names such as 升級／資訊,
        # which would split official phrases into adjacent term spans.
        if fname in ("木板工坊", "石頭工坊"):
            terms_set.add(fname)
    for rid in reward_ids:
        terms_set.add(official_text(f"chat_icon_{rid}"))
    terms = sorted((t for t in terms_set if t), key=len, reverse=True)

    meta = {
        "table_cmp": table_cmp,
        "string_cmp": string_cmp,
        "only_new": only_new,
        "shared_diffs": shared_diffs,
        "shine_lvup": _shine_summary(lvup),
        "shine_new": _shine_summary(lvup_new),
        "cutoff_lvup": cutoff_lvup,
        "cutoff_new": cutoff_new,
        "reward_ids": reward_ids,
        "reward_in_goods": reward_in_goods,
        "goods_rows": goods_rows,
        "extra_name_keys": extra_name_keys,
        "idx_count": len(idx_lvup),
        "cost_patterns_new": dict(Counter(cost_pattern(r) for r in lvup_new)),
        "pre_filled_new": sum(1 for r in lvup_new if is_filled(r.get("pre_building_level"))),
        "pre_new_filled": [int(r["index"]) for r in lvup_new if is_filled(r.get("pre_building_level_new"))],
        "pre2_new_filled": sum(1 for r in lvup_new if is_filled(r.get("pre_building_level_2_new"))),
        "lvup_extra_empty": all(not any(is_filled(r.get(name)) for r in lvup) for name in LVUP_EXTRA_EMPTY_FIELDS),
        "package": PACKAGE_NAME,
        "zip_time": ZIP_TIME_RANGE,
    }
    return TablesData(
        buildings=buildings, by_id=by_id, functions=functions,
        lvup=lvup, lvup_new=lvup_new, production=production, guidebook=guidebook,
        rewards=rewards, civ=civ, sword=sword, war=war, terms=terms, table_meta=meta,
    )

def _des_cell(b: Building, terms: list[str]) -> str:
    if b.des_status == "empty-field":
        return e(VISIBLE_EMPTY_DES)
    if b.des_status == "missing":
        return e(MISSING_TEXT)
    # Official descriptions: do not split a sentence by highlighting inner terms.
    return e(b.des)


def _shared_upgrade_cell(b: Building, data: "TablesData") -> str:
    if b.lvupid == b.bid:
        return "—"
    other = data.by_id.get(b.lvupid)
    if other:
        return f"與{linked_name(other.bid, other.name, data.terms)}共用"
    return f"與 {b.lvupid} 共用"


def _data_notes(data: TablesData) -> str:
    sc = data.table_meta["string_cmp"]
    tc = data.table_meta["table_cmp"]
    diffs = sc["value_diffs"]
    missing = sc["missing"]
    if diffs or missing:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵中，值不同的有 {len(diffs) or '無'}，"
            f"在某一批缺鍵：{len(missing) or '無'}。"
        )
        if diffs:
            extra += "值不同的鍵：" + "、".join(f"`{k}`" for k in list(diffs)[:8]) + "。"
        if missing:
            extra += "缺鍵：" + "、".join(f"`{k}`" for k in list(missing)[:8]) + "。"
    else:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵，在 2026-11-05、2026-11-22 StreamingAssets、"
            "2026-11-22 LocalLow 與現行字串檔裡，凡是該批有此鍵者，值都相同。"
        )

    def same_as_ll(*labels: str, name: str) -> bool:
        info = tc[name]
        return all(info["exists"].get(label) and info["identical"].get(label) for label in labels)

    main_note = (
        "`citybuilding.json` 只出現在 2026-11-22 LocalLow 與現行 `data/`，兩批位元組相同；"
        "2026-11-05 與 2026-11-22 StreamingAssets 的 `data/` 沒有這張主表。"
        "本頁從 LocalLow 歸檔讀取，不改用未記來源的現行 live 檔。"
    )
    if not (tc["citybuilding.json"]["exists"].get("2026-11-22-locallow") and tc["citybuilding.json"]["identical"].get("live")):
        main_note = "`citybuilding.json` 在 LocalLow 與 live 的對照見各檔說明，並非兩批相同。"
    if tc["citybuilding.json"]["exists"].get("2026-11-05") or tc["citybuilding.json"]["exists"].get("2026-11-22"):
        main_note += "對照時發現 11-05 或 StreamingAssets 也有這張主表，與原先記錄不同。"

    lvup_same_later = same_as_ll("live", "2026-11-22", "2026-11-22-locallow", name="citybuilding_lvup.json")
    lvup_new_same_later = same_as_ll("live", "2026-11-22", "2026-11-22-locallow", name="citybuilding_lvup_new.json")
    if lvup_same_later and lvup_new_same_later:
        lvup_note = (
            "`citybuilding_lvup.json` 與 `citybuilding_lvup_new.json` 在 StreamingAssets、LocalLow 與現行 `data/` 三位元組相同，"
            "與 2026-11-05 相比列數相同、列 id 集合相同，但各有 42 列內容不同："
            "索引 200（風帆節點）0–40 級的 `string_para2`，以及索引 179（職業大廳）1 級的 `string_para2` 與 `group2_string_para2`。"
            "11-05 的 179 級 1，這兩欄都是 `['1237|1|0', '1500106|1|0']`，本批都是 `['1237|1|0']`（少了 `1500106`）。"
            "11-05 的 200 級 0 為 `['1500107|0|1']`，本批為 `['1500106|0|1', '1500107|0|1']`（多了 `1500106`）。"
            f"`attribute_name_1500106` 為「{official_text('attribute_name_1500106')}」；`attribute_name_1500107` 字串表沒有內容。"
        )
    else:
        lvup_note = "兩張升級表在四批裡的位元組對照見各檔說明，並非後三批全部相同。"

    others = (
        "citybuilding_function.json", "citybuilding_guidebook.json", "guidebook_reward.json",
        "citybuild_production.json", "citybuild_civilization_hall.json",
        "citybuild_kingdom_sword.json", "citybuild_war_center.json",
    )
    if all(same_as_ll("live", "2026-11-05", "2026-11-22", "2026-11-22-locallow", name=n) for n in others):
        other_note = (
            "`citybuilding_function.json`、`citybuilding_guidebook.json`、`guidebook_reward.json`、"
            "`citybuild_production.json`、`citybuild_civilization_hall.json`、`citybuild_kingdom_sword.json`、"
            "`citybuild_war_center.json` 四批位元組相同。"
        )
    else:
        other_note = "功能、圖鑑點、生產、文明大廳與兩張附註表在四批裡的對照見各檔說明，並非全部相同。"

    strings_note = (
        "字串檔本身三批解壓並不相同：2026-11-05、2026-11-22 StreamingAssets 與 2026-11-22 LocalLow 的 `strings_zh.json` 整檔 sha256 各異；"
        "現行 `strings_zh.json` 與 LocalLow 那份位元組相同"
        f"（SHA-256 `{STRINGS_SHA256}`，{STRINGS_KEY_COUNT} 鍵）。本頁採用 LocalLow 字串檔。"
    )
    return (
        f"資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 2026-11-22 LocalLow 解壓表與 `strings_zh.json`（歸檔於 `/workspace/topheroes/extracts/2026-11-22-locallow/`，"
        f"包名 `{PACKAGE_NAME}`，zip 內部時間 {ZIP_TIME_RANGE}，香港時間），"
        "各表已 pin sha256，不改用未記來源的現行 live 檔。"
        f"{main_note}{lvup_note}{other_note}{strings_note}{extra}"
        "名稱、說明、屬性名與道具文案一律按該列鍵從字串表照錄原字節，不自行改寫。"
        "不要把 `show_type=2` 轉成百分比；官方說明若已有百分比字串，只照錄該字串，與表上原值並列。"
        "`season`、`kvk_theme_dic`、`server_list`、`theme` 只照錄，不對成 S2／S3，不自行加上開放狀態。"
        "類型 999 的各段沒有官方資源名，只錄原值。類型 996／997 同樣沒有官方資源名，只錄原值。"
        "`buildTime` 沒有單位欄，不自行標成秒或分鐘。"
        "兩張升級表並列，不以其中一張覆寫另一張。"
        "養成花費試算只加總目前等級到目標前一級的官方列；目標為該表頂格且頂格列仍有消耗時，該列只照錄、不加進合計。"
        "共用升級進度的建築依 `lvupid` 查列，不用該建築自身卻未被指向的 `index` 列。"
        "名錄中的訓練所在兩張升級表都沒有列，試算名單不收。"
    )


def _render_catalog(data: TablesData) -> str:
    terms = data.terms
    rows = []
    row_ids = []
    for b in data.buildings:
        rows.append([
            str(b.bid),
            linked_name(b.bid, b.name, terms),
            _des_cell(b, terms),
            str(b.maxlevel),
            str(b.new_maxlevel),
            _shared_upgrade_cell(b, data),
        ])
        row_ids.append(f"b{b.bid}")
    return table(
        ["編號", "顯示名", "說明", "定義表上限", "定義表另一上限", "共用升級"],
        rows,
        caption="名錄 126 座，顯示名與說明依遊戲裡看得到的字照錄",
        row_ids=row_ids,
        mobile="cards",
        card_title="顯示名",
        wrap_class="table-sticky-col",
    )


def _render_production(data: TablesData) -> str:
    terms = data.terms
    rows = []
    for r in data.production:
        item = int(r["item"])
        item_name = official_text(f"goods_name_{item}") or MISSING_TEXT
        rows.append([
            str(r["id"]),
            H(item_name, terms),
            str(r["out_put_num"]),
            fmt_cost_value(r.get("cost"), terms),
        ])
    return table(
        ["編號", "產出物", "產出數量", "消耗（原值）"],
        rows,
        caption="木板與原石的生產列（20 列）",
        mobile="cards",
        card_title="產出物",
    )


def _render_rewards(data: TablesData) -> str:
    terms = data.terms
    rows = []
    for rid in data.table_meta["reward_ids"]:
        rows.append([
            str(rid),
            e(official_text(f"goods_des_{rid}")),
            H(official_text(f"chat_icon_{rid}"), terms),
        ])
    return table(
        ["獎勵編號", "道具說明", "聊天圖示名稱"],
        rows,
        caption="16 個獨特獎勵的官方說明與聊天圖示名，用字差異不統一",
        mobile="cards",
        card_title="獎勵編號",
    )


def _render_function_table(data: TablesData) -> str:
    terms = data.terms
    rows = [[H(name, terms)] for _fid, _key, name in data.functions]
    return table(["官方名"], rows, caption="功能的官方名", mobile="cards", card_title="官方名")


def _render_civ_examples(data: TablesData) -> str:
    terms = data.terms
    wanted = {15, 20, 25, 70}
    rows = []

    def fmt_unlock(raw) -> str:
        if not is_filled(raw):
            return "（空）"
        parts = []
        for bit in str(raw).split("|"):
            bit = bit.strip()
            if not bit:
                continue
            try:
                bid = int(bit)
            except ValueError:
                parts.append(e(bit))
                continue
            parts.append(name_of(data.by_id, bid, terms))
        return "、".join(parts) if parts else e(str(raw))

    for r in data.civ:
        if int(r["hero_lv"]) not in wanted:
            continue
        rows.append([
            str(r["id"]), str(r["hero_lv"]),
            fmt_unlock(r.get("unlock_building")),
            fmt_unlock(r.get("new_unlock_building")),
        ])
    return table(
        ["列編號", "表上等級（不對成玩家等級或賽季號）", "解鎖建築", "另一欄解鎖建築"],
        rows,
        caption="文明大廳解鎖表示例（只錄建築與官方顯示名，不是升級建議）",
        mobile="cards",
        card_title="表上等級（不對成玩家等級或賽季號）",
    )


def _class_totem_tables(data: TablesData) -> tuple[str, str]:
    terms = data.terms
    cols = ["來源", "等級", "時間（表上原值，無單位）", "消耗", "戰力", "前置", "效果／參數（只錄原值）"]
    class_rows = []
    for key, rows in (("lvup_new", data.lvup_new), ("lvup", data.lvup)):
        by_lv = {int(r["lv"]): r for r in rows if int(r["index"]) == 179}
        for lv in (0, 1):
            r = by_lv[lv]
            class_rows.append([
                e(SRC_LABEL[key]), str(lv), str(r["buildTime"]),
                fmt_costs_row(r, terms),
                str(r["fightforce"]),
                fmt_prereq(r.get("pre_building_level"), data.by_id, terms),
                fmt_effect_params(r, terms, include_para1=True, include_group2=True),
            ])
    class_tbl = table(cols, class_rows, caption="職業大廳兩張升級表的 0–1 級", mobile="cards", card_title="等級")
    totem_rows = []
    for key, rows in (("lvup_new", data.lvup_new), ("lvup", data.lvup)):
        by_lv = {int(r["lv"]): r for r in rows if int(r["index"]) == 195}
        for lv in (0, 1, 39, 40):
            r = by_lv[lv]
            totem_rows.append([
                e(SRC_LABEL[key]), str(lv), str(r["buildTime"]),
                fmt_costs_row(r, terms),
                str(r["fightforce"]),
                fmt_prereq(r.get("pre_building_level"), data.by_id, terms),
                fmt_effect_params(r, terms, include_para1=False, include_group2=False),
            ])
    totem_tbl = table(cols, totem_rows, caption="先祖圖騰舉例：0、1、39、40 級，兩表並列", mobile="cards", card_title="等級")
    return class_tbl, totem_tbl


def _treasure_examples(data: TablesData) -> str:
    terms = data.terms
    rows = []
    for index, levels in ((140, (0, 39, 40, 2076)), (155, (0, 39, 184, 2193))):
        for key, src_rows in (("lvup_new", data.lvup_new), ("lvup", data.lvup)):
            by_lv = {int(r["lv"]): r for r in src_rows if int(r["index"]) == index}
            for lv in levels:
                r = by_lv[lv]
                rows.append([
                    str(index), e(SRC_LABEL[key]), str(lv),
                    str(r["buildTime"]),
                    fmt_costs_row(r, terms),
                    str(r.get("fightforce")),
                    fmt_prereq(r.get("pre_building_level"), data.by_id, terms),
                    fmt_effect_params(r, terms, include_para1=True, include_group2=False),
                ])
    return table(
        ["編號", "來源", "等級", "時間（表上原值，無單位）", "消耗", "戰力", "前置", "效果／參數（只錄原值）"],
        rows,
        caption="兩座秘寶大廳的節點舉例（兩表並列；其中一座 184 級的效果原值兩表不同）",
        mobile="cards",
        card_title="等級",
    )


def _mismatch_range_table(data: TablesData) -> str:
    terms = data.terms
    rows = []
    for bid in (101, 105, 106, 107, 109, 110, 113, 114, 130, 131, 132, 133):
        b = data.by_id[bid]
        lo, hi, n = _lv_range(data.lvup, bid)
        nlo, nhi, nn = _lv_range(data.lvup_new, bid)
        rows.append([
            str(bid), linked_name(bid, b.name, terms), str(b.maxlevel), str(b.new_maxlevel),
            f"{lo}–{hi}（{n} 列）", f"{nlo}–{nhi}（{nn} 列）",
        ])
    return table(
        ["編號", "顯示名", "定義表上限", "定義表另一上限", "原升級表等級範圍", "新升級表等級範圍"],
        rows,
        caption="定義表上限與升級表實際等級範圍不一致的例子（不自行判定哪一個是真正上限）",
        mobile="cards",
        card_title="顯示名",
    )

def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    title = "Top Heroes Wiki｜城建升級總表"
    lede = (
        "本頁列出主城 126 座建築的名稱與說明，以及兩張升級表的並列規則與關鍵斷點。"
        "這不是城堡外觀，也不是裝飾物。升級表列數很大，本頁寫規則、例子與斷點，不整表傾印。"
    )
    summary = "主城 126 座建築名稱與說明、兩張升級表的並列規則與關鍵斷點，以及生產、圖鑑點與文明大廳解鎖表。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "catalog", "label": "名錄"},
        {"id": "lvup", "label": "兩張升級表"},
        {"id": "costs", "label": "升級消耗、時間與前置", "depth": 1},
        {"id": "cost-calc", "label": "養成花費試算"},
        {"id": "class-totem", "label": "職業大廳與先祖圖騰"},
        {"id": "treasure", "label": "秘寶大廳"},
        {"id": "production", "label": "生產、功能與圖鑑點"},
        {"id": "civilization", "label": "文明大廳解鎖表"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])

    b103, b106, b107, b114 = data.by_id[103], data.by_id[106], data.by_id[107], data.by_id[114]
    b140, b155, b160, b168 = data.by_id[140], data.by_id[155], data.by_id[160], data.by_id[168]
    b178, b179, b183, b195 = data.by_id[178], data.by_id[179], data.by_id[183], data.by_id[195]
    b198, b200, b111, b117 = data.by_id[198], data.by_id[200], data.by_id[111], data.by_id[117]
    b123, b126, b108, b151 = data.by_id[123], data.by_id[126], data.by_id[108], data.by_id[151]
    b120, b119 = data.by_id[120], data.by_id[119]

    attr1237 = official_text("attribute_name_1237")
    goods153, desc153 = official_text("goods_name_153"), official_text("goods_desc_153")
    goods237, desc237 = official_text("goods_name_237"), official_text("goods_desc_237")
    goods1044, desc1044 = official_text("goods_name_1044"), official_text("goods_desc_1044")
    atk_up, hp_up = official_text("artifact_atk_up"), official_text("artifact_hp_up")
    uilding = official_text("uilding_lvup_des_115003")
    building115003 = official_text("building_lvup_des_115003")
    des_worker = official_text("building_lvup_des_141001")
    des_dust = official_text("building_lvup_des_xianzututeng")
    attr1012 = official_text("attribute_name_1012")
    attr1014 = official_text("attribute_name_1014")
    attr1123 = official_text("attribute_name_1123")

    shine_old = data.table_meta["shine_lvup"]
    shine_new = data.table_meta["shine_new"]
    cost_pat = data.table_meta["cost_patterns_new"]
    pre_filled = data.table_meta["pre_filled_new"]
    pre_new_indexes = sorted(set(data.table_meta["pre_new_filled"]))
    pre_new_count = len(data.table_meta["pre_new_filled"])

    ex_old = next(r for r in data.lvup if int(r["index"]) == 12902 and int(r["lv"]) == 63)
    ex_new = next(r for r in data.lvup_new if int(r["index"]) == 12902 and int(r["lv"]) == 63)
    ex155_old = next(r for r in data.lvup if int(r["index"]) == 155 and int(r["lv"]) == 184)
    ex155_new = next(r for r in data.lvup_new if int(r["index"]) == 155 and int(r["lv"]) == 184)
    r140_new = {int(r["lv"]): r for r in data.lvup_new if int(r["index"]) == 140}
    r155_new = {int(r["lv"]): r for r in data.lvup_new if int(r["index"]) == 155}
    para1_140 = len({r["para1"] for r in data.lvup_new if int(r["index"]) == 140})
    para1_155 = len({r["para1"] for r in data.lvup_new if int(r["index"]) == 155})
    r195 = {int(r["lv"]): r for r in data.lvup_new if int(r["index"]) == 195}
    r179 = {int(r["lv"]): r for r in data.lvup_new if int(r["index"]) == 179}

    shared_lvupid = [b for b in data.buildings if b.lvupid != b.bid]
    discard_n = sum(1 for b in data.buildings if b.is_discard == 1)
    list_counts = Counter(b.is_building_list for b in data.buildings)
    init_counts = Counter(b.initlevel for b in data.buildings)
    only_new_type = [b for b in data.buildings if b.new_type != -1]
    dorms_front = [b for b in data.buildings if b.bid in (147, 148, 149, 150)]
    dorms_back = [b for b in data.buildings if 1001 <= b.bid <= 1024]
    rewards_min = min(int(r["guidebook_points"]) for r in data.rewards)
    rewards_max = max(int(r["guidebook_points"]) for r in data.rewards)
    gb_first, gb_last = data.guidebook[0], data.guidebook[-1]
    class_tbl, totem_tbl = _class_totem_tables(data)

    def pat_count(*flags: bool) -> int:
        return int(cost_pat.get(flags, 0))

    parts: list[str] = []
    add = parts.append
    add('    <header class="entry-head">')
    add(f"      <h1>{e(title)}</h1>")
    add(f'      <p class="lede">{e(lede)}</p>')
    add("    </header>")
    add(f"    {toc}")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        "正文只根據遊戲資料表與官方字串，不評定建築強弱，也不排升級優先。"
        "本頁寫主城城建與升級排程。"
        f"這不是城堡外觀；城堡外觀見已發佈的<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>。"
        f"這不是裝飾物；裝飾物見已發佈的<a href=\"decorations.html\">{H('裝飾物總表', terms)}</a>。"
        f"{linked_name(178, b178.name, terms)}見已發佈的<a href=\"holybeasts.html\">{H('守護魔獸總表', terms)}</a>。"
        f"{linked_name(183, b183.name, terms)}見已發佈的<a href=\"pals.html\">{H('帕魯總表', terms)}</a>。"
        f"{linked_name(160, b160.name, terms)}見已發佈的<a href=\"pets.html\">{H('寵物總表', terms)}</a>。"
        f"{H('秘寶大廳', terms)}見已發佈的<a href=\"artifacts.html\">{H('秘寶總表', terms)}</a>。"
        f"顯示名為「{H(b151.name, terms)}」的建築只在名錄與升級索引中照錄，不展開商隊系統。"
    ))
    add("<ul>")
    add(
        "<li>名稱與說明依遊戲裡看得到的字照錄。"
        f"沒有官方說明的標明「{e(MISSING_TEXT)}」，不編造沒有官方名的資源或道具。"
        "少數建築名稱不是按編號一一對應、兩座秘寶大廳共用同一個顯示名，以及部分列沒有說明，對照見資料說明。</li>"
    )
    add(
        f"<li>官方用語是「{H('部族', terms)}」。"
        f"例如「{H(b123.name, terms)}」「{H(b126.name, terms)}」皆照錄。"
        f"建築名「{H(b168.name, terms)}」與說明「{e(b168.des)}」、"
        f"村民提示「{e(official_text('building_villager_tips_168'))}」用字不同，兩種並存，不統一。</li>"
    )
    add(
        "<li>兩張升級表並列，不以其中一張覆寫另一張。"
        f"以下稱「{e(SRC_OLD)}」與「{e(SRC_NEW)}」（檔名見資料說明）。"
        "名錄先寫定義表上的兩個等級上限；"
        "升級列的等級範圍、消耗、時間與前置若兩表不同，分開標明來源。只在兩表相同時才合寫。</li>"
    )
    add(
        "<li>屬性只錄表上原值，不自行換成百分比。"
        "官方說明若已有百分比字串，只照錄該字串，與表上原值並列。"
        "賽季與伺服器相關欄位只照錄，不對成 S2／S3，不自行加上開放狀態。"
        "有些消耗段沒有官方資源名，只錄原值。"
        "升級時間在表上沒有單位，本頁不自行標成秒或分鐘。欄位名與對照見資料說明。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>名錄</h2>")
    add(p_html(
        f"名錄共 {MAIN_COUNT} 座，編號彼此不重複。"
        f"{H(b114.name, terms)}是唯一定義表兩個上限不一致的列（{b114.maxlevel} 與 {b114.new_maxlevel}）。"
        "兩張升級表的實際等級範圍見下一節，本頁不自行判定哪一個是真正上限。"
    ))
    shared_txt = "、".join(
        f"{linked_name(b.bid, b.name, terms)}{_shared_upgrade_cell(b, data)}"
        for b in shared_lvupid
    )
    add(p_html(
        f"多數建築用自己的編號查升級列。下列 {len(shared_lvupid)} 座與另一座建築共用升級進度："
        + shared_txt
        + "。"
    ))
    add(_render_catalog(data))
    add(p_html(
        f"「{H(dorms_front[0].name, terms)}」有多座顯示名相同，其中編號 147–150 與 1001–1024 的說明均為「{e(MISSING_TEXT)}」。"
    ))
    add("    </section>")

    add('    <section id="lvup">')
    add("      <h2>兩張升級表</h2>")
    add(p_html(
        f"{e(SRC_OLD)} {LVUP_COUNT} 列，{e(SRC_NEW)} {LVUP_NEW_COUNT} 列。"
        f"兩張表的建築索引集合相同，皆為 {data.table_meta['idx_count']} 個，都比名錄少「{H(b103.name, terms)}」"
        f"（兩張表都沒有它的升級列）。"
    ))
    add(p_html(
        f"{e(SRC_NEW)}比{e(SRC_OLD)}多 {LVUP_NEW_ONLY} 列，且只多在三處："
        f"{H(b106.name, terms)} 41–50 級（10 列）、{H(b107.name, terms)} 41–50 級（10 列）、"
        f"{H(b114.name, terms)} 2–40 級（39 列）。"
        f"這與定義表上限的對照是：{H(b106.name, terms)}／{H(b107.name, terms)}的兩個上限都是 {b106.maxlevel}，"
        f"{e(SRC_OLD)}最高到 40，{e(SRC_NEW)}最高到 50；"
        f"{H(b114.name, terms)}的兩個上限為 {b114.maxlevel} 與 {b114.new_maxlevel}，"
        f"{e(SRC_OLD)}最高到 1，{e(SRC_NEW)}最高到 40。"
        "本頁同時記錄定義表上限與兩張表的實際等級範圍，不自行判定哪一個是真正上限。"
    ))
    add(_mismatch_range_table(data))
    add(p_html(
        f"兩表共有的 {LVUP_COUNT} 列裡，在共同欄位上有 {SHARED_FIELD_DIFFS} 列內容不同，"
        "涉及消耗、時間、前置、戰力與效果原值等，"
        f"不是只有多出來的 {LVUP_NEW_ONLY} 列才有差別。"
        f"例如{H(data.by_id[12902].name, terms)} 63 級的消耗，以及一座{H('秘寶大廳', terms)} 184 級的效果原值，兩表不同。"
        "因此不能只用其中一張表代表升級。具體原值見資料說明。"
    ))
    add(p_html(
        "同一座建築的等級在表內連續。"
        "最高級常見消耗為空、時間為 -1，像是該級已達表內頂格、不再寫下一級消耗；"
        "本頁只錄原值，不把 -1 自行解釋成「不可升級」以外的含義。"
    ))

    add('      <h3 id="costs">升級消耗、時間與前置</h3>')
    add(p_html(
        "消耗可以有多段。類型 999 的各段沒有官方資源名，只錄「類型 999、第 4 段、數量 …」、「類型 999、第 5 段、數量 …」、「類型 999、第 6 段、數量 …」。"
        "已有官方道具名的消耗寫道具名與數量，例如 "
        f"「{H(goods153, terms)}」（「{e(desc153)}」）、"
        f"「{H(goods237, terms)}」（「{e(desc237)}」）、"
        f"「{H(goods1044, terms)}」（「{e(desc1044)}」）。"
    ))
    wood = {int(r["lv"]): r for r in data.lvup_new if int(r["index"]) == 106}
    add(p_html(
        f"前置寫官方建築名與等級。{e(SRC_NEW)}常見前置是{H(data.by_id[117].name, terms)}。"
        f"例如{H(b106.name, terms)}在{e(SRC_NEW)}裡 0–2 級前置為 {fmt_prereq(wood[0].get('pre_building_level'), data.by_id, terms)}，"
        f"3 級起為 {fmt_prereq(wood[3].get('pre_building_level'), data.by_id, terms)}，之後隨等級把城堡要求往上加，"
        f"至 49 級仍為 {fmt_prereq(wood[49].get('pre_building_level'), data.by_id, terms)}；"
        f"50 級（該表頂格）的前置為{fmt_prereq(wood[50].get('pre_building_level'), data.by_id, terms)}，該級亦無消耗。"
        f"同一張表裡，{H(b107.name, terms)} 50 級與{H(b114.name, terms)} 40 級（各自頂格）的前置同樣為空。"
        "同一座建築在兩張表上的數量可以不同，引用時必須標明來源。"
    ))
    castle_pre2 = [r for r in _rows_for(data.lvup_new, 117) if is_filled(r.get("pre_building_level_2"))]
    bands = []
    for r in castle_pre2:
        key = (tuple(r.get("pre_building_level_2") or []), r.get("pre_building_level_2_desc"))
        if not bands or bands[-1]["key"] != key:
            bands.append({"lo": int(r["lv"]), "hi": int(r["lv"]), "key": key, "row": r})
        else:
            bands[-1]["hi"] = int(r["lv"])
    band_bits = []
    for band in bands:
        desc_key = band["row"].get("pre_building_level_2_desc")
        desc = official_text(desc_key) if desc_key else ""
        band_bits.append(f"{band['lo']}–{band['hi']} 級對應說明「{e(desc)}」")
    table_nums = []
    for band in bands:
        for item in list(band["key"][0]):
            if "|" in str(item):
                try:
                    table_nums.append(int(str(item).split("|", 1)[1]))
                except ValueError:
                    pass
    table_num_txt = "／".join(str(n) for n in sorted(set(table_nums)))
    add(p_html(
        f"{H(b117.name, terms)}另有第二前置（{len(castle_pre2)} 列）："
        + "；".join(band_bits) + "。"
        + "對應提示寫「"
        + e(official_text("pre_building_level_2_desc_117_tips"))
        + "」到「"
        + e(official_text("pre_building_level_5_desc_117_tips"))
        + "」。說明原文是「光輝4級」至「光輝7級」，"
        + f"表上的數字是 {e(table_num_txt)}，本頁並列照錄，不把這些數字自行換算成「光輝」等級。"
        + f"界面另有「{e(official_text('citybuilding_lvup_condition003'))}」、"
        + f"「{e(official_text('citybuilding_lvup_pre_condition'))}」、"
        + f"「{e(official_text('citybuilding_requirement_2'))}」。"
    ))
    add(p_html("升級時間為整數，表沒有單位欄，本頁不自行標成秒或分鐘。"))
    add("    </section>")

    add(render_city_cost_calculator())

    add('    <section id="class-totem">')
    add("      <h2>職業大廳與先祖圖騰</h2>")
    add(p_html(
        f"{H(b179.name, terms)}說明為「{e(b179.des)}」。"
        f"定義表兩個上限皆為 {b179.maxlevel}。"
        "兩張升級表都是 0–1 級共 2 列，在共同欄位上相同（本批）："
        f"兩級時間皆為 {r179[0]['buildTime']}、消耗皆為 {fmt_cost_value(r179[0].get('cost1'), terms)}、"
        f"前置皆為 {fmt_prereq(r179[0].get('pre_building_level'), data.by_id, terms)}；"
        f"0 級戰力 {r179[0]['fightforce']}，1 級戰力 {r179[1]['fightforce']}。"
        f"1 級效果原文為「{e(attr1237)}」。"
        f"表上另有參數 {e(str(r179[1]['para1']))}，只錄原值，表沒有寫對應關係，本頁不推測。"
        "與先前截稿的欄位差別見資料說明。"
        "本頁不另開領主職業圖鑑。"
    ))
    add(class_tbl)
    add(p_html(
        f"{H(b195.name, terms)}說明為「{e(b195.des)}」。"
        f"定義表上限 {b195.maxlevel}，兩張升級表皆為 0–40 級共 41 列，共同欄位相同。"
        f"前置一律為 {fmt_prereq(r195[0].get('pre_building_level'), data.by_id, terms)}，戰力一律 {r195[0]['fightforce']}。"
        f"效果官方名為「{H(des_worker, terms)}」、「{H(des_dust, terms)}」、"
        f"「{H(attr1012, terms)}」、「{H(attr1014, terms)}」、「{H(attr1123, terms)}」。"
        f"0 級無消耗、時間 {r195[0]['buildTime']}；"
        f"1 級起消耗為{H(goods1044, terms)}，數量從 1 級 {r195[1]['cost1'][2]} 增至 39 級 {r195[39]['cost1'][2]}；"
        f"40 級無消耗、時間 {r195[40]['buildTime']}。"
        f"加成原值從 0 級 {e(str(r195[0].get('string_para2')[0].split('|')[1]))} 起，"
        f"1 級為 {e(str(r195[1].get('string_para2')[0].split('|')[1]))}，之後每級加 500，"
        f"至 40 級為 {e(str(r195[40].get('string_para2')[0].split('|')[1]))}。"
        "本頁只錄原值，不換算成百分比。"
    ))
    add(totem_tbl)
    add("    </section>")

    add('    <section id="treasure">')
    add("      <h2>秘寶大廳</h2>")
    add(p_html(
        f"兩座顯示名都是「{H(b140.name, terms)}」，說明都是「{e(b140.des)}」。"
        f"編號 140 上限 {b140.maxlevel}，升級表 0–2076 共 {1 + 2076} 列；"
        f"編號 155 上限 {b155.maxlevel}，升級表 0–2193 共 {1 + 2193} 列。"
        "兩座在兩張升級表裡都有完整這些列，但部分欄位（例如編號 155 的效果原值）兩表不同。"
        f"升級說明官方字為「{H(atk_up, terms)}」、「{H(hp_up, terms)}」，以及「{H(uilding, terms)}」。"
        f"本批用的是「{H(uilding, terms)}」這條，不是「{H(building115003, terms)}」；兩個都是官方字串，不自行改正。"
    ))
    add(p_html(f"以下斷點取自{e(SRC_NEW)}（{e(SRC_OLD)}同範圍，消耗與參數請以各表為準，不要混用）："))
    add(p_html(
        f"140：0–39 級消耗為類型 999、第 4 段（數量隨等級變化），"
        f"時間為正值（0 級 {r140_new[0]['buildTime']}，39 級 {r140_new[39]['buildTime']}），"
        f"參數從 {r140_new[0]['para1']} 到 {r140_new[39]['para1']}，"
        f"戰力從 {r140_new[0]['fightforce']} 到 {r140_new[39]['fightforce']}；"
        f"40–2075 級消耗改為{H(goods237, terms)}，"
        "其間時間在 -1 與 0 之間分段切換"
        "（40–439 為 -1，440–478 為 0，479–1439 為 -1，1440–1478 為 0，1479–2076 為 -1）；"
        f"其中 2076 級無消耗，參數 {r140_new[2076]['para1']}，"
        f"戰力 {r140_new[2076]['fightforce']}。"
        f"參數共有 {para1_140} 個不同取值。"
    ))
    add(p_html(
        f"155：全程消耗皆為{H(goods237, terms)}。"
        f"0 級消耗 {r155_new[0]['cost1'][2]}、時間 {r155_new[0]['buildTime']}、"
        f"參數 {r155_new[0]['para1']}、戰力 {r155_new[0]['fightforce']}；"
        "1–39 級時間為 0；40–556 級為 -1；557–595 級為 0；"
        "596–1556 級為 -1；1557–1595 級為 0；1596–2193 級為 -1。"
        f"2193 級消耗 {fmt_cost_value(r155_new[2193].get('cost1'), terms)}、"
        f"時間 {r155_new[2193]['buildTime']}、"
        f"參數 {r155_new[2193]['para1']}、"
        f"戰力 {r155_new[2193]['fightforce']}。"
        f"參數同樣有 {para1_155} 個不同取值。"
        "這兩座列數很大，本頁不逐列傾印。"
    ))
    add(_treasure_examples(data))
    add("    </section>")

    add('    <section id="production">')
    add("      <h2>生產、功能與圖鑑點</h2>")
    add(p_html(
        f"生產表 {PRODUCTION_COUNT} 列，{H(official_text('goods_name_101'), terms)}與{H(official_text('goods_name_102'), terms)}各 10 列。"
        f"{H(official_text('goods_name_101'), terms)}的消耗為類型 999、第 4 段，數量 1000 至 6000，對應產出 1 至 6；"
        f"{H(official_text('goods_name_102'), terms)}的消耗為類型 999、第 5 段，數量同樣 1000 至 6000，對應產出 1 至 6。"
        "產出 2 至 5 各有兩列（例如有兩列都是"
        f"{H(official_text('goods_name_101'), terms)} ×2、消耗 2000），產出 1 與 6 各只一列。"
        f"界面有「{e(official_text('citybuilding_production_list_full'))}」、"
        f"「{e(official_text('citybuilding_production_not_enough'))}」。"
        f"功能裡的官方名包括「{H(data.functions[3][2], terms)}」「{H(data.functions[4][2], terms)}」。"
        f"主表「{H(b108.name, terms)}」說明為「{e(b108.des)}」。"
    ))
    add(_render_function_table(data))
    add(_render_production(data))
    add(p_html(
        f"圖鑑 1–{GUIDEBOOK_COUNT} 級，該級經驗從 1 級 {gb_first['level_exp']} 增至 80 級 {gb_last['level_exp']}，不是等差。"
        "屬性只錄原值，不換成百分比，本頁不整表傾印。"
        "升級表另有圖鑑相關欄，本頁不把它們與這 80 級逐列對齊（對應規則見資料說明）。"
    ))
    add(p_html(
        f"圖鑑獎勵 {REWARD_COUNT} 列，點數從 {rewards_min} 到 {rewards_max}，"
        f"有 {REWARD_ID_COUNT} 個獨特獎勵編號："
        + "、".join(str(i) for i in data.table_meta["reward_ids"])
        + "。"
        "如下照錄官方說明與聊天圖示名，用字差異不統一。"
        f"例如同一獎勵說明寫「{e(official_text('goods_des_61022'))}」，"
        f"圖示名寫「{e(official_text('chat_icon_61022'))}」。"
        "61023、61024 的說明寫「聊天視窗」，圖示名寫「聊天框」；"
        "61031 則相反，"
        f"說明寫「{e(official_text('goods_des_61031'))}」，"
        f"圖示名寫「{e(official_text('chat_icon_61031'))}」。"
    ))
    add(_render_rewards(data))
    add(p_html(
        "生產建築的村民提示有官方產量用字，例如 "
        f"「{e(official_text('building_villager_tips_106'))}」、"
        f"「{e(official_text('building_villager_tips_107'))}」、"
        f"「{e(official_text('building_villager_tips_110'))}」、"
        f"「{e(official_text('building_villager_tips_168'))}」。"
        "這些是提示字串，不是類型 999 消耗段的官方名。"
    ))
    add("    </section>")

    add('    <section id="civilization">')
    add("      <h2>文明大廳解鎖表</h2>")
    add(p_html(
        f"文明大廳解鎖表 {CIV_COUNT} 列。表上等級從 {data.civ[0]['hero_lv']} 到 {data.civ[-1]['hero_lv']}，不自行對成玩家等級或賽季號。"
        "解鎖建築與另一欄解鎖建築寫的是名錄裡的建築（有時一欄寫兩座）。"
        f"例如表上等級 15 有兩列：一列沒有解鎖建築，一列解鎖{H(data.by_id[110].name, terms)}；"
        f"20 解鎖{H(data.by_id[130].name, terms)}；"
        f"25 解鎖{H(b106.name, terms)}。"
        f"兩欄有時不同，例如表上等級 70 一欄是{H(data.by_id[137].name, terms)}與一座{H('秘寶大廳', terms)}，"
        f"另一欄是{H(data.by_id[137].name, terms)}與另一座{H('秘寶大廳', terms)}。"
        "本頁只錄這些建築，不把它寫成升級優先建議。"
    ))
    add(_render_civ_examples(data))
    add(p_html(
        f"另有兩張表，本批沒有可對上的建築升級內容，不把它們當成「{H(b120.name, terms)}」或「{H(b119.name, terms)}」的升級表。"
        "檔名與列數見資料說明。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(
        f"<li>裝飾物、DIY 套裝與道路擺放，見已發佈的<a href=\"decorations.html\">{H('裝飾物總表', terms)}</a>。"
        "那些不是主城升級排程。</li>"
    )
    add(
        f"<li>城堡外觀與皮膚，見已發佈的<a href=\"castle.html\">{H('城堡外觀總表', terms)}</a>。"
        "本頁不引用皮膚名稱。</li>"
    )
    add(
        f"<li>科技見已發佈的<a href=\"tech.html\">{H('科技總表', terms)}</a>。"
        "同盟領地建築、地圖／PVE／KVK 地圖建築、商隊玩法細節不在本頁展開。</li>"
    )
    add(
        f"<li>兩張升級表 {LVUP_COUNT}／{LVUP_NEW_COUNT} 列的逐列全表，以及 140／155 合計四千餘列的逐級消耗；"
        f"兩表共有 {SHARED_FIELD_DIFFS} 列的逐欄差異總表（本頁只舉規則與例子）。</li>"
    )
    seen_extra = []
    for _key, value in data.table_meta["extra_name_keys"]:
        if value not in seen_extra:
            seen_extra.append(value)
    extra_bits = "、".join(f"「{H(v, terms)}」" for v in seen_extra)
    add(
        "<li>字串表有、但不在這 126 座名錄裡的建築名，只在此列出官方顯示名，不收入名錄，不自行加上開放狀態："
        + extra_bits
        + "。鍵名見資料說明。</li>"
    )
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(_data_notes(data)))
    add("<ul>")
    add(
        "<li>定義在 <code>citybuilding.json</code>（126 筆，只在 LocalLow／live），"
        "升級在 <code>citybuilding_lvup.json</code>（7973 筆）與 <code>citybuilding_lvup_new.json</code>（8032 筆），"
        "功能在 <code>citybuilding_function.json</code>（5 筆），"
        "圖鑑等級在 <code>citybuilding_guidebook.json</code>（80 筆），"
        "圖鑑獎勵在 <code>guidebook_reward.json</code>（238 筆），"
        "生產在 <code>citybuild_production.json</code>（20 筆），"
        "文明大廳在 <code>citybuild_civilization_hall.json</code>（81 筆）。"
        "<code>citybuild_kingdom_sword.json</code>（82 筆）與 <code>citybuild_war_center.json</code>（66 筆）只作附註。"
        "名稱來自主表該列的 <code>name</code>／<code>des</code> 鍵。</li>"
    )
    add(
        f"<li>可見正文稱「{e(SRC_OLD)}」與「{e(SRC_NEW)}」，分別對應 <code>citybuilding_lvup.json</code>（{LVUP_COUNT} 列）與 "
        f"<code>citybuilding_lvup_new.json</code>（{LVUP_NEW_COUNT} 列）。"
        "名錄「定義表上限」與「定義表另一上限」分別對應主表 <code>maxlevel</code>／<code>new_maxlevel</code>。"
        "不要把 <code>show_type=2</code> 轉成百分比；"
        "<code>season</code>、<code>kvk_theme_dic</code>、<code>server_list</code>、<code>theme</code> 只照錄，不對成 S2／S3，不自行加上開放狀態。"
        "<code>buildTime</code> 沒有單位欄，不自行標成秒或分鐘。</li>"
    )
    add(
        "<li>顯示名、說明按該列 <code>name</code>／<code>des</code> 鍵從字串表照錄。"
        "名稱鍵不一定是 <code>citybuilding_name_{id}</code>。"
        "例如 id 106 的名稱鍵是 <code>citybuilding_name_6</code>，id 155 與 140 都用 <code>citybuilding_name_140</code>。"
        f"id 111 的顯示名原文是 <code>{e(b111.name)}</code>，照錄；該列 <code>des</code> 欄為空（不是缺 <code>citybuilding_des_111</code> 這條鍵），可見名錄寫「{e(VISIBLE_EMPTY_DES)}」。"
        f"id 309 的名稱鍵是 <code>{e(data.by_id[309].name_key)}</code>。"
        f"建築名「{e(b168.name)}」出自 <code>{e(b168.name_key)}</code>（「勳」為 U+52F3）；"
        f"說明 <code>{e(b168.des_key)}</code> 寫「{e(b168.des)}」（「勛」為 U+52DB）。"
        f"村民提示 <code>building_villager_tips_168</code> 寫「{e(official_text('building_villager_tips_168'))}」。</li>"
    )
    add(
        f"<li>主表共 {MAIN_COUNT} 列，編號彼此不重複，範圍不是單純的 101–201（另有 1001–1024、301–309、12902 等）。"
        f"<code>count</code> 皆為 1。<code>is_discard</code> 為 1 的有 {discard_n} 列，其餘 {MAIN_COUNT - discard_n} 列為 -1。"
        f"<code>is_building_list</code> 為 1 的有 {list_counts[1]} 列，為 -1 的有 {list_counts[-1]} 列，為 0 的只有 id 181（{e(data.by_id[181].name)}）。"
        f"<code>initlevel</code> 為 0 的有 {init_counts[0]} 列，為 1 的有 {init_counts[1]} 列。"
        f"<code>type</code> 沒有官方中文類型名。<code>new_type</code> 僅 id 114（{e(b114.name)}）為 {only_new_type[0].new_type}，其餘為 -1。"
        f"<code>is_discard</code> 為 1 的 {discard_n} 列，<code>server_list</code> 皆為 {code_json(['999'])}。"
        f"未標記 <code>is_discard</code> 的 id 164（{e(data.by_id[164].name)}）同樣是 {code_json(['999'])}。"
        "這些欄位只照錄，不自行加上開放狀態。"
        f"<code>lvupid</code> 等於自身 <code>id</code> 的有 {MAIN_COUNT - len(shared_lvupid)} 列；其餘與另一座共用升級進度。"
        "升級表裡仍有這些建築自身 <code>index</code>＝其 <code>id</code> 的列，但對應建築的 <code>lvupid</code> 並不指向那些列。"
        f"宿舍 id 147–150 與 1001–1024 的名稱鍵都是 <code>citybuilding_name_11</code>，說明鍵都是 <code>citybuilding_des_11</code>（{e(MISSING_TEXT)}）。"
        f"前四座 <code>is_discard</code> 為 {dorms_front[0].is_discard}、<code>is_building_list</code> 為 {dorms_front[0].is_building_list}；"
        f"1001–1024 的 <code>is_discard</code> 為 {dorms_back[0].is_discard}、<code>is_building_list</code> 為 {dorms_back[0].is_building_list}。</li>"
    )
    extra_fields = "、".join(f"<code>{e(name)}</code>" for name in LVUP_EXTRA_EMPTY_FIELDS)
    empty_note = "在本批匯出裡這些欄全部為空。" if data.table_meta["lvup_extra_empty"] else "這些欄在本批並非全部為空。"
    add(
        "<li>列 <code>id</code> 寫成索引加等級，兩張升級表規則相同。"
        "多數為 <code>index * 1000 + lv</code>（例如 101 的 0 級是 101000）。"
        "不是全程使用這個式子的索引有四個，沒有第五個："
        "140（秘寶大廳）0–40 級仍是 <code>index * 1000 + lv</code>（140000–140040），"
        "41 級起改為 <code>index * 10000 + lv</code>（41 級 1400041，2076 級 1402076）；"
        "155（秘寶大廳）全程為 <code>index * 10000 + lv</code>（0 級 1550000，2193 級 1552193），沒有從 <code>* 1000</code> 切換；"
        f"160（{e(b160.name)}）與 198（升級表有此索引；主表 id 198 {e(b198.name)} 的 <code>lvupid</code> 為 {b198.lvupid}）"
        "全程為 <code>index * 1000 + lv + 1</code>（160 的 0 級 160001、40 級 160041；198 的 0 級 198001、40 級 198041）。"
        "其餘 121 個索引皆為 <code>index * 1000 + lv</code>。</li>"
    )
    add(
        f"<li><code>citybuilding_lvup.json</code> 比新表多 12 個欄位（{extra_fields}），{empty_note}"
        "新表沒有多出來的獨有欄位，但與原表同樣有 <code>pre_building_level_new</code>、"
        f"<code>pre_building_level_2_new</code> 等欄；其中 <code>pre_building_level_2_new</code> 與對應說明欄在本批為空，"
        f"<code>pre_building_level_new</code> 有 {pre_new_count} 列有值（索引 {'、'.join(str(i) for i in pre_new_indexes)}）。"
        f"本批 <code>shine_lv</code>：原升級表有 {len(shine_old['from41_0'])} 個索引自 41 級起為 0，"
        f"新升級表則為 {len(shine_new['from41_0'])} 個"
        f"（差異在索引 124 {e(data.by_id[124].name)}：原表的 41–44 級為 0，新表同段為 -1）。"
        f"兩張表都是 {len(shine_old['from45_1'])} 個索引自 45 級起為 1。</li>"
    )
    add(
        f"<li>兩表差異舉例：原升級表裡 12902（{e(data.by_id[12902].name)}）63 級 "
        f"<code>cost1</code> 為 {code_json(ex_old.get('cost1'))}、"
        f"<code>cost2</code>／<code>cost3</code> 為 {code_json(ex_old.get('cost2'))}／{code_json(ex_old.get('cost3'))}、"
        f"<code>cost4</code> 為 {code_json(ex_old.get('cost4'))}；"
        f"同 id 在新升級表為 {code_json(ex_new.get('cost1'))}、"
        f"{code_json(ex_new.get('cost2'))}、{code_json(ex_new.get('cost3'))}、{code_json(ex_new.get('cost4'))}。"
        f"155 的 184 級，原升級表的 <code>string_para2</code> 為 {code_json(ex155_old.get('string_para2'))}，"
        f"新升級表為 {code_json(ex155_new.get('string_para2'))}。"
        f"新升級表 {LVUP_NEW_COUNT} 列裡，消耗形態計次："
        f"只有 <code>cost1</code> {pat_count(True, False, False, False)} 列；"
        f"<code>cost1</code>＋<code>cost2</code> {pat_count(True, True, False, False)} 列；"
        f"再加 <code>cost3</code> {pat_count(True, True, True, False)} 列；"
        f"四段都有 {pat_count(True, True, True, True)} 列；"
        f"沒有消耗 {pat_count(False, False, False, False)} 列；"
        f"只有 <code>cost2</code>＋<code>cost3</code> {pat_count(False, True, True, False)} 列。"
        f"前置 <code>pre_building_level</code> 寫成 <code>建築id|等級</code>；新升級表有 {pre_filled} 列填了此欄。</li>"
    )
    add(
        f"<li>秘寶大廳升級說明：<code>artifact_atk_up</code>「{e(atk_up)}」、"
        f"<code>artifact_hp_up</code>「{e(hp_up)}」，以及 "
        f"<code>uilding_lvup_des_115003</code>（鍵名開頭少一個 b）「{e(uilding)}」。"
        f"字串表另有 <code>building_lvup_des_115003</code>「{e(building115003)}」，"
        "本批這兩座的 <code>des</code> 用的是少字母的那個鍵。兩者都是官方鍵，不自行改正。"
        f"職業大廳 1 級 <code>string_para2</code> 與 <code>group2_string_para2</code> 對應 <code>attribute_name_1237</code>「{e(attr1237)}」；"
        "與 2026-11-05 的差別見上段來源說明。</li>"
    )
    add(
        "<li>圖鑑獎勵 16 個獨特 <code>reward_id</code> 對得上 <code>goods_des_{id}</code>（鍵名是 <code>des</code> 不是 <code>desc</code>）與 <code>chat_icon_{id}</code>；"
        "字串表沒有 <code>goods_name_{id}</code> 或 <code>goods_desc_{id}</code>，這些 id 也都不在 live <code>goods.json</code> 表列。"
        f"61022 的 <code>goods_des_61022</code> 寫「{e(official_text('goods_des_61022'))}」（「蘇」為 U+8607），"
        f"<code>chat_icon_61022</code> 寫「{e(official_text('chat_icon_61022'))}」（「甦」為 U+7526）。"
        f"<code>citybuild_kingdom_sword.json</code> {SWORD_COUNT} 列，id 從 {data.sword[0]['id']} 到 {data.sword[-1]['id']}；"
        f"<code>citybuild_war_center.json</code> {WAR_COUNT} 列，id {data.war[0]['id']}–{data.war[-1]['id']}。"
        "兩張附註表都沒有可逕行當成對應建築升級表的欄位。</li>"
    )
    extra_key_bits = "、".join(
        f"<code>{e(k)}</code>「{e(v)}」" for k, v in data.table_meta["extra_name_keys"]
    )
    add(
        "<li>字串表有、但不在主表 126 列的建築名稱鍵："
        + extra_key_bits
        + "。</li>"
    )
    add(
        "<li>待補：兩張升級表共有 2818 列的逐欄差異總表（本頁只舉規則與例子）；"
        "<code>is_guidebook_active</code>／<code>guidebook_lv_points</code> 與 80 級圖鑑表的對應；"
        "16 個 <code>reward_id</code> 的 <code>goods_des_*</code>／<code>chat_icon_*</code> 已對上字串表，這些 id 不在 live <code>goods.json</code> 表列，實際開出的物品列仍待補；"
        "類型 999 各段的資源名稱與 <code>buildTime</code> 單位；"
        f"{H(b103.name, terms)}沒有升級列的原因；"
        "主表上限與升級表範圍不一致時，客戶端實際採用哪一張、哪一個上限；"
        "字串表多出的 202–204 等名稱若進入主表後的補錄；"
        "<code>attribute_name_1500107</code> 字串表沒有內容；"
        "<code>citybuilding_des_11</code>、<code>citybuilding_des_144</code>、<code>citybuilding_des_151</code>、<code>citybuilding_des_157</code>、<code>citybuilding_des_204</code> 字串表沒有內容；"
        "id 111 的 <code>des</code> 欄為空（不是缺 <code>citybuilding_des_111</code> 這條鍵）；"
        "<code>citybuild_kingdom_sword</code>／<code>citybuild_war_center</code> 若日後填入 <code>attr</code> 後的補錄；"
        "<code>season</code>、<code>kvk_theme_dic</code>、<code>server_list</code> 與賽季日曆或顯示伺服器的對應（不自行加上開放狀態）；"
        "與戰鬥公式、科技、天賦的疊加計算。不編造閉合公式，不評定強弱或升級順序。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    from .upgrade_costs import attach_upgrade_cost_scripts
    html = attach_upgrade_cost_scripts(html, "city-upgrade-costs-data.js", "upgrade-cost.js")
    return html


def render_citybuilding_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _plain_cost_segment(seg) -> str:
    segs = _as_segments(seg)
    if not segs:
        return ""
    parts = []
    for item in segs:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            parts.append(str(item))
            continue
        typ, mid, qty = item[0], item[1], item[2]
        try:
            typ_n = int(typ)
        except (TypeError, ValueError):
            typ_n = typ
        if typ_n == 2:
            try:
                item_id = int(mid)
            except (TypeError, ValueError):
                item_id = mid
            name = official_text(f"goods_name_{item_id}") if isinstance(item_id, int) else ""
            if name:
                parts.append(f"{name} ×{qty}")
                continue
        parts.append(f"類型 {typ}、第 {mid} 段、數量 {qty}")
    return "、".join(parts)


def _plain_row_costs(row: dict) -> str:
    bits = [_plain_cost_segment(row.get(key)) for key in ("cost1", "cost2", "cost3", "cost4") if is_filled(row.get(key))]
    return "、".join(bits)


def _pack_city_curve(rows: list[dict]) -> dict:
    rows = sorted(rows, key=lambda r: int(r["lv"]))
    times = []
    costs = []
    for r in rows:
        times.append(int(r.get("buildTime") if r.get("buildTime") not in (None, "") else 0))
        segs = []
        for key in ("cost1", "cost2", "cost3", "cost4"):
            for item in _as_segments(r.get(key)):
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    segs.append([int(item[0]), int(item[1]), int(item[2])])
        costs.append(segs)
    return {"min": int(rows[0]["lv"]), "t": times, "c": costs}


def _curve_key(curve: dict) -> str:
    return json.dumps(curve, ensure_ascii=False, separators=(",", ":"))


def _collect_city_resources(curves: dict[str, dict]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for curve in curves.values():
        for segs in curve["c"]:
            for typ, mid, _qty in segs:
                key = f"{typ}:{mid}"
                if key in out:
                    continue
                if typ == 2:
                    name = official_text(f"goods_name_{mid}")
                    out[key] = name or None
                else:
                    out[key] = None
    return out


def _lookup_rows(table: list[dict], index: int) -> list[dict]:
    return [r for r in table if int(r["index"]) == int(index)]


def build_city_upgrade_cost_payload(data: TablesData) -> dict:
    curves: dict[str, dict] = {}
    curve_ids: dict[str, str] = {}

    def intern(rows: list[dict]) -> str | None:
        if not rows:
            return None
        packed = _pack_city_curve(rows)
        blob = _curve_key(packed)
        hid = curve_ids.get(blob)
        if not hid:
            hid = f"c{len(curves)}"
            curve_ids[blob] = hid
            curves[hid] = packed
        return hid

    prelim = []
    for b in data.buildings:
        src = b.lvupid
        old_rows = _lookup_rows(data.lvup, src)
        new_rows = _lookup_rows(data.lvup_new, src)
        if not old_rows and not new_rows:
            continue
        old_id = intern(old_rows)
        new_id = intern(new_rows)
        shared_name = ""
        if b.lvupid != b.bid:
            other = data.by_id.get(b.lvupid)
            if other and other.name:
                shared_name = other.name
        lv0 = None
        if new_rows:
            lv0 = next((r for r in new_rows if int(r["lv"]) == 0), None)
        elif old_rows:
            lv0 = next((r for r in old_rows if int(r["lv"]) == 0), None)
        lv0_text = _plain_row_costs(lv0) if lv0 else ""
        old_rng = None
        new_rng = None
        if old_id:
            c = curves[old_id]
            old_rng = (c["min"], c["min"] + len(c["t"]) - 1)
        if new_id:
            c = curves[new_id]
            new_rng = (c["min"], c["min"] + len(c["t"]) - 1)
        prelim.append({
            "name": b.name,
            "old": old_id,
            "new": new_id,
            "shared": shared_name,
            "lv0": lv0_text,
            "old_rng": old_rng,
            "new_rng": new_rng,
        })

    # Collapse buildings that share display name, curves and shared-upgrade note.
    groups: list[dict] = []
    index = {}
    for row in prelim:
        key = (row["name"], row["old"], row["new"], row["shared"])
        if key in index:
            continue
        index[key] = len(groups)
        groups.append(row)

    name_counts: dict[str, int] = {}
    for g in groups:
        name_counts[g["name"]] = name_counts.get(g["name"], 0) + 1

    def range_text(g: dict) -> str:
        old_rng, new_rng = g["old_rng"], g["new_rng"]
        if old_rng and new_rng and old_rng == new_rng:
            return f"升級表 {old_rng[0]}–{old_rng[1]} 級"
        bits = []
        if old_rng:
            bits.append(f"{SRC_OLD} {old_rng[0]}–{old_rng[1]} 級")
        if new_rng:
            bits.append(f"{SRC_NEW} {new_rng[0]}–{new_rng[1]} 級")
        return "、".join(bits)

    items = []
    for g in groups:
        label = g["name"]
        if name_counts[g["name"]] > 1:
            rng = range_text(g)
            # If every colliding group has a unique range, use that; else add 0-level costs.
            collide = [x for x in groups if x["name"] == g["name"]]
            ranges = [range_text(x) for x in collide]
            if len(set(ranges)) == len(collide) and rng:
                label = f"{g['name']}（{rng}）"
            elif g["lv0"]:
                label = f"{g['name']}（0 級消耗為{g['lv0']}）"
            else:
                label = f"{g['name']}（0 級沒有消耗）"
        hint = ""
        if g["shared"]:
            hint = f"與{g['shared']}共用升級進度，以下加總該共用列。"
        tables = {}
        if g["old"]:
            tables[SRC_OLD] = g["old"]
        if g["new"]:
            tables[SRC_NEW] = g["new"]
        items.append({"label": label, "hint": hint, "tables": tables})

    return {
        "kind": "city",
        "tables": [SRC_OLD, SRC_NEW],
        "resources": _collect_city_resources(curves),
        "curves": curves,
        "items": items,
    }


def write_city_upgrade_cost_data(path: Path, data: TablesData | None = None) -> None:
    from .upgrade_costs import write_data_js

    payload = build_city_upgrade_cost_payload(data or load_tables_data())
    write_data_js(path, "TH_CITY_UPGRADE_COST", payload)


def render_city_cost_calculator() -> str:
    parts = [
        '    <section id="cost-calc">',
        "      <h2>養成花費試算</h2>",
        "<p>選一座建築，再填目前等級與目標等級，可以加總這段升級在兩張升級表裡已經寫出的消耗與時間。"
        "只加總表上原值，不計算折扣，也不補沒有官方列的消耗。"
        f"「{e(official_text('citybuilding_name_103') or '訓練所')}」在兩張升級表都沒有列，所以不會出現在下面的名單裡。</p>",
        f"<p>從目前等級升到目標等級，加總的是目前等級到目標前一級的各列（也就是在這些等級再升上一級時，表上寫的消耗與時間）。"
        "目標等級那一列不計入。時間在表上沒有單位，合計時也不自行標成秒或分鐘。"
        "類型 999、類型 997、類型 996 的各段沒有官方資源名，只錄原值。"
        f"「{e(SRC_OLD)}」與「{e(SRC_NEW)}」分開顯示，不以其中一張覆寫另一張。</p>",
        "<p>沒有使用指令時，上面的總表與規則仍可閱讀；試算需要瀏覽器執行本頁指令。</p>",
        '<form class="upgrade-cost" data-upgrade-cost data-upgrade-source="TH_CITY_UPGRADE_COST" action="#" method="get">',
        "<noscript><p>目前沒有執行指令，無法在這一欄加總。請改看上方的升級規則與例子，或開啟指令後再試。</p></noscript>",
        "<fieldset>",
        "<legend>城建升級</legend>",
        '<div class="upgrade-cost-grid">',
        '<div class="upgrade-cost-span"><label for="uc-city-item">建築</label>',
        '<select id="uc-city-item" data-uc-item></select></div>',
        '<div><label for="uc-city-from">目前等級</label>',
        '<input id="uc-city-from" data-uc-from type="number" inputmode="numeric"></div>',
        '<div><label for="uc-city-to">目標等級</label>',
        '<input id="uc-city-to" data-uc-to type="number" inputmode="numeric"></div>',
        "</div>",
        '<div class="upgrade-cost-actions"><button type="submit" data-uc-run>加總</button></div>',
        '<div class="upgrade-cost-result" data-uc-result hidden aria-live="polite"></div>',
        "</fieldset>",
        "</form>",
        "    </section>",
    ]
    return "\n".join(parts)
