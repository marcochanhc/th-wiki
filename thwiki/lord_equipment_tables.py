"""Compile the published 領主裝備 catalog tables."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR
from .strings import clean, t
from .tables import catalog, load_table
from . import attrs as A


# 領主裝備總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫資料日的次日。
# 這三張領主裝備表與第 25 章所用 2026-11-05 解壓檔、以及
# 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同，
# 但不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。
LORD_DATA_CUTOFF = "2026-11-23"
LORD_DATA_PACK = "app-1.129.12_table-1.0.43173"
LORD_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "lord_equipment.json": "f93001995a06aaf71ced682022de62b1a5839265fd7bbcb85337fb273c873702",
    "lord_equip_master.json": "a8f5c7494c89bd7fa6560db69b06aca2f74eabc0d4cd79ed39440ce399061119",
    "lord_equipment_enchantment.json": "e2a1096310c4d17bb55669d9963fea754a652981c7d2f90b50dc147bc5893e4c",
}

# 物品名只取官方字串，不用 LocalLow 的 goods.json 骨架表。
GOODS_IDS = (154, 155, 156, 157)
NAME_KEYS = {
    1: "lord_equip_name01",
    2: "lord_equip_name02",
    3: "lord_equip_name03",
    4: "lord_equip_name04",
    5: "lord_equip_name05",
    6: "lord_equip_name06",
    7: "lord_equip_name07",
}
ICON_BY_TYPE = {
    1: "icon_lord_3",
    2: "icon_lord_6",
    3: "icon_lord_1",
    4: "icon_lord_4",
    5: "icon_lord_2",
    6: "icon_lord_5",
    7: "icon_lord_7",
}
ATTR_IDS_BY_TYPE = {
    1: (5104, 15104, 10103),
    2: (5103, 15103, 10104),
    3: (3104, 13104, 10103),
    4: (3103, 13103, 10104),
    5: (4104, 14104, 10103),
    6: (4103, 14103, 10104),
    7: (64, 6501, 6502, 103, 104),
}

# 第 25 章總覽：1 級／滿級原值與戰力。產生器若偏離會 raise。
CHAPTER_OVERVIEW = {
    1: {
        "lv1": ((5104, 75), (15104, 205), (10103, 25)),
        "max": ((5104, 7800), (15104, 21450), (10103, 2710)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    2: {
        "lv1": ((5103, 35), (15103, 75), (10104, 70)),
        "max": ((5103, 3900), (15103, 8125), (10104, 7150)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    3: {
        "lv1": ((3104, 75), (13104, 205), (10103, 25)),
        "max": ((3104, 7800), (13104, 21450), (10103, 2710)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    4: {
        "lv1": ((3103, 35), (13103, 75), (10104, 70)),
        "max": ((3103, 3900), (13103, 8125), (10104, 7150)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    5: {
        "lv1": ((4104, 75), (14104, 205), (10103, 25)),
        "max": ((4104, 7800), (14104, 21450), (10103, 2710)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    6: {
        "lv1": ((4103, 35), (14103, 75), (10104, 70)),
        "max": ((4103, 3900), (14103, 8125), (10104, 7150)),
        "power": (1818, 993035),
        "max_level": 166,
    },
    7: {
        "lv1": ((64, 130), (6501, 20), (6502, 10), (103, 150), (104, 250)),
        "max": ((64, 9600), (6501, 1200), (6502, 600), (103, 14000), (104, 31000)),
        "power": (18816, 1015949),
        "max_level": 64,
    },
}

# 前六件階段起始列（等級下限、上限、名稱鍵、quality、equip_tier）。
FIRST_SIX_STAGES = (
    (1, 2, "lord_equip_desc001", 2, None),
    (3, 9, "lord_equip_desc002", 3, None),
    (10, 19, "lord_equip_desc003", 4, None),
    (20, 32, "lord_equip_desc006", 5, "icon_txt_T1"),
    (33, 45, "lord_equip_desc007", 5, "icon_txt_T2"),
    (46, 58, "lord_equip_desc0061", 5, "icon_txt_T3"),
    (59, 71, "lord_equip_desc0071", 5, "icon_txt_T4"),
    (72, 87, "lord_equip_desc008", 6, None),
    (88, 103, "lord_equip_desc009", 6, "icon_txt_T1"),
    (104, 119, "lord_equip_desc010", 6, "icon_txt_T2"),
    (120, 135, "lord_equip_desc011", 6, "icon_txt_T3"),
    (136, 166, "lord_equip_desc011", 6, "icon_txt_T4"),
)

CODEX_STAGES = (
    (1, 16, "lord_equip_desc008", 6, None, 72, 87),
    (17, 32, "lord_equip_desc009", 6, "icon_txt_T1", 88, 103),
    (33, 48, "lord_equip_desc010", 6, "icon_txt_T2", 104, 119),
    (49, 64, "lord_equip_desc011", 6, "icon_txt_T3", 120, 135),
)

# 前六件階段起始列消耗＋166 級（類型皆 2|物品|數量）。
CHAPTER_COSTS = {
    1: ((154, 1500), (155, 20)),
    3: ((154, 4000), (155, 50)),
    10: ((154, 1800), (155, 5), (156, 12)),
    20: ((154, 3300), (155, 30), (156, 15)),
    33: ((154, 5500), (155, 50), (156, 20)),
    46: ((154, 8500), (155, 85), (156, 20)),
    59: ((154, 10000), (155, 90), (156, 20)),
    72: ((154, 15000), (155, 140), (156, 20), (157, 2)),
    88: ((154, 15000), (155, 180), (156, 25), (157, 4)),
    104: ((154, 18000), (155, 190), (156, 30), (157, 4)),
    120: ((154, 20000), (155, 245), (156, 40), (157, 5)),
    136: ((154, 24000), (155, 290), (156, 50), (157, 8)),
    166: ((154, 36000), (155, 360), (156, 70), (157, 18)),
}
CODEX_COST_LV1 = ((155, 200), (156, 50))
CODEX_COST_LV64 = ((156, 1200), (157, 240))
CODEX_MASTER_ADDITIONAL = {1: 6000, 64: 26000}

MASTER_LEVELS = (3, 4, 6, 8, 10, 11, 14, 17, 20, 33, 46, 59, 72, 88, 104, 120, 136)

# 三件加成：104、10103；六件加成：103、10103、10104。戰力與原值依第 25 章。
CHAPTER_MASTER_3 = {
    3: ((104, 400), (10103, 120), 2696, "lord_equip_desc002"),
    4: ((104, 800), (10103, 240), 7076, "lord_equip_desc002"),
    6: ((104, 1200), (10103, 360), 13544, "lord_equip_desc002"),
    8: ((104, 1600), (10103, 480), 22500, "lord_equip_desc002"),
    10: ((104, 3200), (10103, 960), 54952, "lord_equip_desc003"),
    11: ((104, 5040), (10103, 1440), 101052, "lord_equip_desc003"),
    14: ((104, 7040), (10103, 1920), 163366, "lord_equip_desc003"),
    17: ((104, 8800), (10103, 2400), 239438, "lord_equip_desc003"),
    20: ((104, 11040), (10103, 2880), 341534, "lord_equip_desc006"),
    33: ((104, 13920), (10103, 3600), 493270, "lord_equip_desc007"),
    46: ((104, 16320), (10103, 4320), 664998, "lord_equip_desc0061"),
    59: ((104, 19500), (10103, 5040), 890368, "lord_equip_desc0071"),
    72: ((104, 23920), (10103, 6000), 1214276, "lord_equip_desc008"),
    88: ((104, 29160), (10103, 6960), 1627684, "lord_equip_desc009"),
    104: ((104, 35960), (10103, 8160), 2198636, "lord_equip_desc010"),
    120: ((104, 42000), (10103, 9600), 2846208, "lord_equip_desc011"),
    136: ((104, 48000), (10103, 11400), 3571402, "lord_equip_desc013"),
}
CHAPTER_MASTER_6 = {
    3: ((103, 200), (10103, 80), (10104, 400), 13364, "lord_equip_desc002"),
    4: ((103, 400), (10103, 160), (10104, 800), 31934, "lord_equip_desc002"),
    6: ((103, 600), (10103, 240), (10104, 1200), 55910, "lord_equip_desc002"),
    8: ((103, 800), (10103, 320), (10104, 1600), 85492, "lord_equip_desc002"),
    10: ((103, 1600), (10103, 640), (10104, 3200), 193412, "lord_equip_desc003"),
    11: ((103, 2400), (10103, 960), (10104, 5040), 337592, "lord_equip_desc003"),
    14: ((103, 3200), (10103, 1280), (10104, 7040), 517800, "lord_equip_desc003"),
    17: ((103, 4000), (10103, 1600), (10104, 8800), 711464, "lord_equip_desc003"),
    20: ((103, 4800), (10103, 1920), (10104, 11040), 965928, "lord_equip_desc006"),
    33: ((103, 5800), (10103, 2400), (10104, 14400), 1351232, "lord_equip_desc007"),
    46: ((103, 6800), (10103, 2880), (10104, 17280), 1746404, "lord_equip_desc0061"),
    59: ((103, 7800), (10103, 3360), (10104, 21000), 2257644, "lord_equip_desc0071"),
    72: ((103, 9200), (10103, 4000), (10104, 26000), 2964420, "lord_equip_desc008"),
    88: ((103, 10800), (10103, 4640), (10104, 31320), 3783752, "lord_equip_desc009"),
    104: ((103, 12400), (10103, 5440), (10104, 39440), 4978378, "lord_equip_desc010"),
    120: ((103, 14000), (10103, 6400), (10104, 48000), 6345022, "lord_equip_desc011"),
    136: ((103, 16000), (10103, 7600), (10104, 57000), 7599404, "lord_equip_desc013"),
}

# 等級階段 11 筆特殊列（id, level_show, stage_name, special_level, bonus, extra, combat, mats）。
CHAPTER_SPECIAL = (
    (1, 1, "fmjd_1", 0, ((10103, 21), (10104, 63), (103, 21), (104, 63)), (), 4062, (25000, 250, 160, 40)),
    (11, 5, "fmjd_2", 1, ((10103, 231), (10104, 693), (103, 231), (104, 693)), ((20, 200),), 44688, (30200, 263, 168, 42)),
    (36, 10, "fmjd_2", 1, ((10103, 820), (10104, 2460), (103, 820), (104, 2460)), ((20, 200), (21, 200)), 158635, (38900, 338, 216, 54)),
    (61, 15, "fmjd_3", 2, ((10103, 1533), (10104, 4599), (103, 1533), (104, 4599)), ((20, 400), (21, 200)), 296570, (51700, 431, 276, 69)),
    (86, 20, "fmjd_3", 2, ((10103, 2382), (10104, 7146), (103, 2382), (104, 7146)), ((20, 400), (21, 400)), 460815, (65600, 525, 336, 84)),
    (111, 25, "fmjd_4", 3, ((10103, 3351), (10104, 10053), (103, 3351), (104, 10053)), ((20, 600), (21, 400)), 648275, (80500, 619, 396, 99)),
    (136, 30, "fmjd_4", 3, ((10103, 4440), (10104, 13320), (103, 4440), (104, 13320)), ((20, 600), (21, 600)), 858950, (97100, 719, 460, 115)),
    (161, 35, "fmjd_5", 4, ((10103, 5653), (10104, 16959), (103, 5653), (104, 16959)), ((20, 800), (21, 600)), 1093614, (118200, 844, 540, 135)),
    (186, 40, "fmjd_5", 4, ((10103, 7002), (10104, 21006), (103, 7002), (104, 21006)), ((20, 800), (21, 800)), 1354588, (140500, 969, 620, 155)),
    (211, 45, "fmjd_6", 5, ((10103, 8427), (10104, 25281), (103, 8427), (104, 25281)), ((20, 1000), (21, 800)), 1630265, (164100, 1094, 700, 175)),
    (236, 50, "fmjd_6", 5, ((10103, 9852), (10104, 29556), (103, 9852), (104, 29556)), ((20, 1000), (21, 1000)), 1905941, (188900, 1219, 780, 195)),
)

UNUSED_DESC_KEYS = (
    "lord_equip_desc004",
    "lord_equip_desc005",
    "lord_equip_desc012",
    "lord_equip_desc013",
)

# 突破防禦：type=1、show_type=1；其餘本頁屬性為 type=2、show_type=2。
SHOW_TYPE_EXCEPTIONS = {64}


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def _int(value) -> int:
    return int(float(str(value).strip()))


def official_text(key: str, default: str = "") -> str:
    return clean(t(key, default))


def quality_label(key: str) -> str:
    """Strip colour tags and the unused {0} slot."""
    text = official_text(key)
    return re.sub(r"\{0\}", "", text).strip()


def goods_name(gid: int) -> str:
    name = official_text(f"goods_name_{gid}")
    if not name:
        raise ValueError(f"missing official goods_name_{gid}")
    return name


def fmt_int(value) -> str:
    return f"{_int(value):,}"


def attr_label(attr_id: int, *, with_id: bool = False) -> str:
    name = A.attr_name(attr_id)
    return f"{name}（{attr_id}）" if with_id else name


def format_attrs(pairs, *, named: bool = True) -> str:
    if not pairs:
        return "—"
    bits = []
    for item in pairs:
        aid, val = _int(item[0]), _int(item[1])
        if named:
            bits.append(f"{attr_label(aid)} {fmt_int(val)}")
        else:
            bits.append(f"{aid} {fmt_int(val)}")
    return "、".join(bits)


def parse_pipe_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                out.append((_int(item[0]), _int(item[1])))
            elif isinstance(item, str) and "|" in item:
                a, v = item.split("|", 1)
                out.append((_int(a), _int(v)))
        return out
    if isinstance(raw, str):
        out = []
        for part in raw.split(","):
            part = part.strip()
            if "|" in part:
                a, v = part.split("|", 1)
                out.append((_int(a), _int(v)))
        return out
    return []


def parse_costs(raw) -> list[tuple[int, int, int]]:
    """Return (type, goods_id, qty). Leading type is recorded as 2, not reinterpreted."""
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                out.append((_int(item[0]), _int(item[1]), _int(item[2])))
            elif isinstance(item, str):
                parts = item.split("|")
                if len(parts) >= 3:
                    out.append((_int(parts[0]), _int(parts[1]), _int(parts[2])))
        return out
    if isinstance(raw, str):
        out = []
        for part in raw.split(","):
            parts = part.split("|")
            if len(parts) >= 3:
                out.append((_int(parts[0]), _int(parts[1]), _int(parts[2])))
        return out
    return []


def cost_map(costs: list[tuple[int, int, int]]) -> dict[int, int]:
    out: dict[int, int] = {}
    for typ, gid, qty in costs:
        if typ != 2:
            raise ValueError(f"unexpected cost type {typ} for goods {gid}")
        out[gid] = qty
    return out


def cost_qty_cell(mapping: dict[int, int], gid: int) -> str:
    if gid not in mapping:
        return "—"
    return fmt_int(mapping[gid])


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row_attrs(row: dict) -> list[tuple[int, int]]:
    if row.get("attrs"):
        return parse_pipe_pairs(row["attrs"])
    return parse_pipe_pairs(row.get("attr_para1") or row.get("bonus_attribute"))


def _row_costs(row: dict) -> list[tuple[int, int, int]]:
    if row.get("costs"):
        return parse_costs(row["costs"])
    return parse_costs(row.get("cost") or row.get("material"))


def _tier_cell(tier, *, short: bool = False) -> str:
    if tier in (None, "", -1):
        return "（空）"
    s = str(tier)
    if short and s.startswith("icon_txt_"):
        return s[len("icon_txt_"):]
    return s


@dataclass
class PieceInfo:
    typ: int
    name_key: str
    name: str
    icon: str
    attr_ids: tuple[int, ...]
    lv1_attrs: list[tuple[int, int]]
    max_attrs: list[tuple[int, int]]
    lv1_power: int
    max_power: int
    max_level: int
    lv1_id: int
    max_id: int
    name_key_bug_rows: int
    lv1_costs: list[tuple[int, int, int]]
    max_costs: list[tuple[int, int, int]]
    master_additional_lv1: int | None
    master_additional_max: int | None


@dataclass
class StageRow:
    lo: int
    hi: int
    desc_key: str
    label: str
    quality: int
    equip_tier: str | None
    note: str = ""


@dataclass
class CostRow:
    level: int
    stage_label: str
    quantities: dict[int, int]
    note: str = ""


@dataclass
class MasterRow:
    equip_num: int
    level: int
    desc_key: str
    label: str
    attrs: list[tuple[int, int]]
    power: int


@dataclass
class SpecialStageRow:
    sid: int
    level_show: int
    stage_key: str
    stage_name: str
    special_level: int
    bonus: list[tuple[int, int]]
    extra: list[tuple[int, int]]
    power: int
    materials: dict[int, int]


@dataclass
class TablesData:
    pieces: list[PieceInfo]
    first_six_stages: list[StageRow]
    codex_stages: list[StageRow]
    cost_rows: list[CostRow]
    cost_lv166: CostRow
    master_3: list[MasterRow]
    master_6: list[MasterRow]
    special_stages: list[SpecialStageRow]
    official: dict
    goods: dict[int, dict]
    counts: dict
    verifications: dict
    terms: list[str] = field(default_factory=list)


def _expected_id(typ: int, level: int) -> int:
    return int(f"13{typ}0{level:03d}")


def _norm_tier(val):
    return None if val in (None, "", -1) else val


def _attr_meta_ok(attr_id: int) -> None:
    row = catalog()["attribute_by_id"].get(int(attr_id)) or {}
    typ = row.get("type")
    show = row.get("show_type")
    if attr_id in SHOW_TYPE_EXCEPTIONS:
        if typ != 1 or show != 1:
            raise ValueError(f"attr {attr_id} expected type=1 show_type=1, got {typ}/{show}")
    else:
        if typ != 2 or show != 2:
            raise ValueError(f"attr {attr_id} expected type=2 show_type=2, got {typ}/{show}")


def load_tables_data() -> TablesData:
    for name, expected in TABLE_SHA256.items():
        actual = file_sha256(DATA_DIR / name)
        if actual != expected:
            raise ValueError(f"{name} sha256 {actual} != {expected}")

    equipment = load_table("lord_equipment")
    master = load_table("lord_equip_master")
    enchant = load_table("lord_equipment_enchantment")
    categories = load_table("attr_category")

    if len(equipment) != 1060:
        raise ValueError(f"lord_equipment should have 1060 rows, got {len(equipment)}")
    if len(master) != 34:
        raise ValueError(f"lord_equip_master should have 34 rows, got {len(master)}")
    if len(enchant) != 240:
        raise ValueError(f"lord_equipment_enchantment should have 240 rows, got {len(enchant)}")

    cat49 = next((r for r in categories if int(r["id"]) == 49), None)
    if not cat49 or cat49.get("name_key") != "property_lordequip_name":
        raise ValueError(f"attr_category 49 unexpected: {cat49}")
    if cat49.get("tips_key") != "property_lordequip_dec":
        raise ValueError(f"attr_category 49 tips_key unexpected: {cat49}")

    official = {
        "system": official_text("ui_lordequip_002"),
        "property_name": official_text("property_lordequip_name"),
        "property_dec": official_text("property_lordequip_dec"),
        "lord_fm4": official_text("lord_fm4"),
        "three": official_text("ui_lordequip_012"),
        "six": official_text("ui_lordequip_013"),
        "own_n": official_text("ui_lordequip_005"),
        "not_active": official_text("ui_lordequip_009"),
        "current_bonus": official_text("ui_lordequip_007"),
        "next_bonus": official_text("ui_lordequip_008"),
        "add_1": official_text("lord_equip_7_add_1"),
        "add_2": official_text("lord_equip_7_add_2"),
        "add_3": official_text("lord_equip_7_add_3"),
        "unlock_1": official_text("lordequipment_level_not_enough"),
        "unlock_2": official_text("lzzbfm_js1"),
        "unlock_3": official_text("lordequipment7_open_day"),
        "unlock_1_key": "lordequipment_level_not_enough",
        "unlock_2_key": "lzzbfm_js1",
        "unlock_3_key": "lordequipment7_open_day",
    }
    expected_official = {
        "system": "領主裝備",
        "property_name": "領主裝備",
        "property_dec": "領主裝備提供的屬性，可以在領主介面查看",
        "lord_fm4": "不斷提升你的領主裝備等級，即可突破至更高的階段，到達更高階段還會提高額外屬性！",
        "three": "三件加成",
        "six": "六件加成",
        "own_n": "擁有{0}件",
        "not_active": "尚未啟動領主裝備最高等級的加成",
        "current_bonus": "目前加成",
        "next_bonus": "下一級加成",
        "add_1": "提升領主裝備大師屬性，品質越高提升越多",
        "add_2": "大師屬性",
        "add_3": "神聖法典提供",
        "unlock_1": "需要其他領主裝備都達到傳說T2開啟。",
        "unlock_2": "前6件領主裝備中，任一件達到{0}後解鎖",
        "unlock_3": "{0}賽季{1}天後開啟。",
    }
    for key, expected in expected_official.items():
        if official[key] != expected:
            raise ValueError(f"official string {key} drifted: {official[key]!r} != {expected!r}")
    if official["system"] != official["property_name"]:
        raise ValueError("ui_lordequip_002 and property_lordequip_name differ")

    # 字串表沒有「裝魂」「領主裝佩」。
    from .strings import load_strings
    strings_all = load_strings()
    for banned in ("裝魂", "領主裝佩"):
        hits = [k for k, v in strings_all.items() if isinstance(v, str) and banned in v]
        if hits:
            raise ValueError(f"unexpected string hits for {banned}: {hits[:5]}")

    goods = {}
    for gid in GOODS_IDS:
        name = goods_name(gid)
        desc = official_text(f"goods_desc_{gid}")
        if "用於打造領主裝備" not in desc:
            raise ValueError(f"goods_desc_{gid} missing 用於打造領主裝備: {desc!r}")
        goods[gid] = {"id": gid, "name": name, "desc": desc}
    expected_goods_names = {154: "精煉金屬", 155: "魔法絲線", 156: "奧利哈鋼", 157: "龍之血"}
    for gid, name in expected_goods_names.items():
        if goods[gid]["name"] != name:
            raise ValueError(f"goods_name_{gid} drifted: {goods[gid]['name']!r}")
    if "可將傳說T4等級的領主裝備晉升為神話品質" not in goods[157]["desc"]:
        raise ValueError(f"goods_desc_157 missing promotion sentence: {goods[157]['desc']!r}")

    by_type: dict[int, list[dict]] = defaultdict(list)
    for row in equipment:
        by_type[_int(row["type"])].append(row)
    for typ in range(1, 8):
        rows = sorted(by_type.get(typ, []), key=lambda r: _int(r["level"]))
        expected_n = 64 if typ == 7 else 166
        if len(rows) != expected_n:
            raise ValueError(f"type {typ} should have {expected_n} rows, got {len(rows)}")
        levels = [_int(r["level"]) for r in rows]
        if levels != list(range(1, expected_n + 1)):
            raise ValueError(f"type {typ} levels are not 1–{expected_n}")
        by_type[typ] = rows

    if sum(len(v) for v in by_type.values()) != 1060:
        raise ValueError("type counts do not sum to 1060")

    pieces: list[PieceInfo] = []
    name_bug_total = 0
    for typ in range(1, 8):
        rows = by_type[typ]
        lv1, mx = rows[0], rows[-1]
        name_key = NAME_KEYS[typ]
        live_lv1_key = lv1["lord_equip_name"]
        if live_lv1_key != name_key:
            raise ValueError(f"type {typ} lv1 name key {live_lv1_key} != {name_key}")
        name = official_text(name_key)
        if not name:
            raise ValueError(f"missing official name for {name_key}")
        icon = lv1["icon"]
        if icon != ICON_BY_TYPE[typ]:
            raise ValueError(f"type {typ} icon {icon} != {ICON_BY_TYPE[typ]}")
        if any(r["icon"] != icon for r in rows):
            raise ValueError(f"type {typ} icon changes across levels")

        lv1_attrs = _row_attrs(lv1)
        max_attrs = _row_attrs(mx)
        attr_ids = tuple(a for a, _ in lv1_attrs)
        if attr_ids != ATTR_IDS_BY_TYPE[typ]:
            raise ValueError(f"type {typ} attr ids {attr_ids} != {ATTR_IDS_BY_TYPE[typ]}")
        if any(tuple(a for a, _ in _row_attrs(r)) != attr_ids for r in rows):
            raise ValueError(f"type {typ} attr ids change across levels")
        for aid in attr_ids:
            _attr_meta_ok(aid)

        chap = CHAPTER_OVERVIEW[typ]
        if tuple(lv1_attrs) != chap["lv1"]:
            raise ValueError(f"type {typ} lv1 attrs {lv1_attrs} != {chap['lv1']}")
        if tuple(max_attrs) != chap["max"]:
            raise ValueError(f"type {typ} max attrs {max_attrs} != {chap['max']}")
        if (_int(lv1["fightforce"]), _int(mx["fightforce"])) != chap["power"]:
            raise ValueError(
                f"type {typ} power {lv1['fightforce']}/{mx['fightforce']} != {chap['power']}"
            )
        if _int(mx["level"]) != chap["max_level"]:
            raise ValueError(f"type {typ} max level {mx['level']} != {chap['max_level']}")
        if _int(lv1["id"]) != _expected_id(typ, 1) or _int(mx["id"]) != _expected_id(typ, _int(mx["level"])):
            raise ValueError(f"type {typ} id pattern drifted: {lv1['id']}/{mx['id']}")
        for r in rows:
            if _int(r["id"]) != _expected_id(typ, _int(r["level"])):
                raise ValueError(f"id pattern failed for type {typ} level {r['level']}: {r['id']}")

        bug_rows = [r for r in rows if r["lord_equip_name"] != name_key]
        if typ in (4, 5, 6):
            if len(bug_rows) != 31:
                raise ValueError(f"type {typ} expected 31 name-key rows at 136+, got {len(bug_rows)}")
            if any(_int(r["level"]) < 136 for r in bug_rows):
                raise ValueError(f"type {typ} name-key change appears before 136")
            if any(r["lord_equip_name"] != "lord_equip_name03" for r in bug_rows):
                raise ValueError(f"type {typ} 136+ name key is not lord_equip_name03")
            if attr_ids == ATTR_IDS_BY_TYPE[3]:
                raise ValueError(f"type {typ} attrs unexpectedly match 統禦王冠")
            name_bug_total += len(bug_rows)
        elif bug_rows:
            raise ValueError(f"type {typ} unexpected name-key changes: {len(bug_rows)}")

        master_add_lv1 = _int(lv1["master_additional"])
        master_add_max = _int(mx["master_additional"])
        if typ <= 6:
            if any(_int(r["master_additional"]) != -1 for r in rows):
                raise ValueError(f"type {typ} master_additional is not all -1")
            master_add_lv1 = master_add_max = None
        else:
            if any(_int(r["master_additional"]) == -1 for r in rows):
                raise ValueError("神聖法典 missing master_additional on some rows")
            if master_add_lv1 != CODEX_MASTER_ADDITIONAL[1] or master_add_max != CODEX_MASTER_ADDITIONAL[64]:
                raise ValueError(
                    f"神聖法典 master_additional {master_add_lv1}/{master_add_max} "
                    f"!= {CODEX_MASTER_ADDITIONAL}"
                )
            mls = [_int(r["master_level"]) for r in rows]
            if mls != list(range(72, 136)):
                raise ValueError(f"神聖法典 master_level not 72–135: {mls[0]}–{mls[-1]}")

        pieces.append(
            PieceInfo(
                typ=typ,
                name_key=name_key,
                name=name,
                icon=icon,
                attr_ids=attr_ids,
                lv1_attrs=lv1_attrs,
                max_attrs=max_attrs,
                lv1_power=_int(lv1["fightforce"]),
                max_power=_int(mx["fightforce"]),
                max_level=_int(mx["level"]),
                lv1_id=_int(lv1["id"]),
                max_id=_int(mx["id"]),
                name_key_bug_rows=len(bug_rows),
                lv1_costs=_row_costs(lv1),
                max_costs=_row_costs(mx),
                master_additional_lv1=master_add_lv1,
                master_additional_max=master_add_max,
            )
        )

    if official_text("lord_equip_name03") != "統禦王冠":
        raise ValueError("lord_equip_name03 is not 統禦王冠")
    if name_bug_total != 93:
        raise ValueError(f"name-key bug rows should be 31×3=93, got {name_bug_total}")

    for level in range(1, 167):
        rows = [next(r for r in by_type[t] if _int(r["level"]) == level) for t in range(1, 7)]
        ffs = {_int(r["fightforce"]) for r in rows}
        costs = {tuple(_row_costs(r)) for r in rows}
        if len(ffs) != 1 or len(costs) != 1:
            raise ValueError(f"first six power/cost diverged at level {level}")
        nums_hp = [
            tuple(v for _, v in _row_attrs(next(r for r in by_type[t] if _int(r["level"]) == level)))
            for t in (1, 3, 5)
        ]
        nums_atk = [
            tuple(v for _, v in _row_attrs(next(r for r in by_type[t] if _int(r["level"]) == level)))
            for t in (2, 4, 6)
        ]
        if len(set(nums_hp)) != 1 or len(set(nums_atk)) != 1:
            raise ValueError(f"shared curves diverged at level {level}")

    first_six_stages: list[StageRow] = []
    sample = by_type[1]
    for lo, hi, key, quality, tier in FIRST_SIX_STAGES:
        chunk = [r for r in sample if lo <= _int(r["level"]) <= hi]
        if not chunk:
            raise ValueError(f"no rows for first-six stage {lo}–{hi}")
        if any(r["lord_equip_desc"] != key for r in chunk):
            raise ValueError(f"desc key drifted in {lo}–{hi}")
        if any(_int(r["quality"]) != quality for r in chunk):
            raise ValueError(f"quality drifted in {lo}–{hi}")
        if any(_norm_tier(r.get("equip_tier")) != tier for r in chunk):
            raise ValueError(f"equip_tier drifted in {lo}–{hi}")
        start = next(r for r in chunk if _int(r["level"]) == lo)
        if _int(start["star"]) != 0:
            raise ValueError(f"stage-start star at {lo} is not 0")
        for typ in range(1, 7):
            other = [r for r in by_type[typ] if lo <= _int(r["level"]) <= hi]
            if any(
                r["lord_equip_desc"] != key
                or _int(r["quality"]) != quality
                or _norm_tier(r.get("equip_tier")) != tier
                for r in other
            ):
                raise ValueError(f"type {typ} stage {lo}–{hi} drifted")
        note = ""
        label = quality_label(key)
        if lo == 136:
            if key != "lord_equip_desc011" or label != "神話T3" or tier != "icon_txt_T4":
                raise ValueError("136–166 must remain 神話T3 with tier T4")
            note = "名稱仍是神話T3，階級欄為 T4。不改稱為神話T4。"
        first_six_stages.append(
            StageRow(lo=lo, hi=hi, desc_key=key, label=label, quality=quality, equip_tier=tier, note=note)
        )

    used_desc = {r["lord_equip_desc"] for r in sample}
    for key in UNUSED_DESC_KEYS:
        if key in used_desc:
            raise ValueError(f"{key} unexpectedly used on first-six equipment rows")

    codex_stages: list[StageRow] = []
    codex_rows = by_type[7]
    unexpected_codex = (
        "lord_equip_desc001", "lord_equip_desc002", "lord_equip_desc003",
        "lord_equip_desc004", "lord_equip_desc005",
        "lord_equip_desc006", "lord_equip_desc0061", "lord_equip_desc007", "lord_equip_desc0071",
        "lord_equip_desc013",
    )
    if any(r["lord_equip_desc"] in unexpected_codex for r in codex_rows):
        raise ValueError("神聖法典 has unexpected quality keys (良好–傳說 or 神話T4)")
    for lo, hi, key, quality, tier, ml_lo, ml_hi in CODEX_STAGES:
        chunk = [r for r in codex_rows if lo <= _int(r["level"]) <= hi]
        if not chunk or any(r["lord_equip_desc"] != key or _int(r["quality"]) != quality for r in chunk):
            raise ValueError(f"神聖法典 stage {lo}–{hi} drifted")
        if any(_norm_tier(r.get("equip_tier")) != tier for r in chunk):
            raise ValueError(f"神聖法典 equip_tier drifted in {lo}–{hi}")
        mls = [_int(r["master_level"]) for r in chunk]
        if mls[0] != ml_lo or mls[-1] != ml_hi or mls != list(range(ml_lo, ml_hi + 1)):
            raise ValueError(f"神聖法典 master_level {lo}–{hi}: {mls[0]}–{mls[-1]} != {ml_lo}–{ml_hi}")
        codex_stages.append(
            StageRow(
                lo=lo, hi=hi, desc_key=key, label=quality_label(key),
                quality=quality, equip_tier=tier, note=f"master_level {ml_lo}–{ml_hi}",
            )
        )

    cost_rows: list[CostRow] = []
    for lo, hi, key, quality, tier in FIRST_SIX_STAGES:
        row = next(r for r in sample if _int(r["level"]) == lo)
        mapping = cost_map(_row_costs(row))
        expected = dict(CHAPTER_COSTS[lo])
        if mapping != expected:
            raise ValueError(f"first-six cost at {lo}: {mapping} != {expected}")
        label = quality_label(key)
        if lo == 136:
            label = "（裝備列名稱仍為神話T3，階級欄為 T4）"
        cost_rows.append(CostRow(level=lo, stage_label=label, quantities=mapping))
    row166 = next(r for r in sample if _int(r["level"]) == 166)
    map166 = cost_map(_row_costs(row166))
    if map166 != dict(CHAPTER_COSTS[166]):
        raise ValueError(f"lv166 cost {map166} != {CHAPTER_COSTS[166]}")
    cost_lv166 = CostRow(level=166, stage_label="166 級（滿級；非階段起始）", quantities=map166)

    c1 = cost_map(pieces[6].lv1_costs)
    c64 = cost_map(pieces[6].max_costs)
    if c1 != dict(CODEX_COST_LV1):
        raise ValueError(f"神聖法典 lv1 cost {c1} != {CODEX_COST_LV1}")
    if c64 != dict(CODEX_COST_LV64):
        raise ValueError(f"神聖法典 lv64 cost {c64} != {CODEX_COST_LV64}")
    first_157 = min(_int(r["level"]) for r in codex_rows if any(c[1] == 157 for c in _row_costs(r)))
    if first_157 != 17:
        raise ValueError(f"神聖法典 first 龍之血 at {first_157}, expected 17")
    first6_157 = min(_int(r["level"]) for r in sample if any(c[1] == 157 for c in _row_costs(r)))
    if first6_157 != 72:
        raise ValueError(f"first six first 龍之血 at {first6_157}, expected 72")

    def _master_rows(num: int, chapter: dict, expected_ids: tuple[int, ...]) -> list[MasterRow]:
        rows = sorted((r for r in master if _int(r["equip_num"]) == num), key=lambda r: _int(r["level"]))
        if [_int(r["level"]) for r in rows] != list(MASTER_LEVELS):
            raise ValueError(f"equip_num {num} levels drifted")
        out = []
        for r in rows:
            level = _int(r["level"])
            attrs = _row_attrs(r)
            if tuple(a for a, _ in attrs) != expected_ids:
                raise ValueError(f"equip_num {num} level {level} attr ids {attrs}")
            exp = chapter[level]
            expected_attrs = exp[:-2]
            expected_power = exp[-2]
            expected_key = exp[-1]
            if tuple(attrs) != expected_attrs:
                raise ValueError(f"equip_num {num} level {level} attrs {attrs} != {expected_attrs}")
            if _int(r["fightforce"]) != expected_power:
                raise ValueError(f"equip_num {num} level {level} power {r['fightforce']} != {expected_power}")
            if r["attr_key"] != expected_key:
                raise ValueError(f"equip_num {num} level {level} attr_key {r['attr_key']} != {expected_key}")
            label = quality_label(r["attr_key"])
            if level == 136 and label != "神話T4":
                raise ValueError(f"master level 136 must be 神話T4, got {label}")
            out.append(
                MasterRow(
                    equip_num=num,
                    level=level,
                    desc_key=r["attr_key"],
                    label=label,
                    attrs=attrs,
                    power=_int(r["fightforce"]),
                )
            )
        return out

    master_3 = _master_rows(3, CHAPTER_MASTER_3, (104, 10103))
    master_6 = _master_rows(6, CHAPTER_MASTER_6, (103, 10103, 10104))
    if len(master_3) + len(master_6) != 34:
        raise ValueError("master 3+6 did not total 34")

    ids = [_int(r["id"]) for r in enchant]
    bonus_lvs = [_int(r["bonus_lv"]) for r in enchant]
    if sorted(ids) != list(range(1, 241)) or ids != bonus_lvs:
        raise ValueError("enchantment id / bonus_lv are not 1–240 and equal")
    shows = sorted({_int(r["level_show"]) for r in enchant})
    extras = sorted({_int(r["level_extra"]) for r in enchant})
    if shows != list(range(1, 51)) or extras != [0, 1, 2, 3, 4]:
        raise ValueError(f"level_show/extra unexpected: {shows[:3]}… {extras}")
    if any(_int(r["exp"]) != -1 for r in enchant):
        raise ValueError("enchantment exp is not all -1")
    for r in enchant:
        bonus = parse_pipe_pairs(r.get("bonus_attribute"))
        if tuple(a for a, _ in bonus) != (10103, 10104, 103, 104):
            raise ValueError(f"enchantment {r['id']} bonus attrs {bonus}")
        for aid, _ in bonus:
            _attr_meta_ok(aid)

    special_raw = [r for r in enchant if r.get("IsSpecialLevelData") is True]
    if len(special_raw) != 11:
        raise ValueError(f"special stage rows {len(special_raw)} != 11")
    if sum(1 for r in enchant if r.get("IsSpecialLevelData") is False) != 229:
        raise ValueError("non-special stage rows are not 229")
    stage_names = {r.get("stage_name") for r in enchant if r.get("stage_name")}
    if any(f"fmjd_{i}" in stage_names for i in range(7, 11)):
        raise ValueError("fmjd_7–10 unexpectedly appear in enchantment table")
    for key in (f"fmjd_{i}" for i in range(7, 11)):
        if not official_text(key).startswith("等級階段"):
            raise ValueError(f"missing official {key}")

    special_stages: list[SpecialStageRow] = []
    for rec, raw in zip(CHAPTER_SPECIAL, sorted(special_raw, key=lambda r: _int(r["id"]))):
        sid, show, skey, slevel, bonus, extra, power, mats = rec
        if _int(raw["id"]) != sid or _int(raw["level_show"]) != show:
            raise ValueError(f"special row id/show {raw['id']}/{raw['level_show']} != {sid}/{show}")
        if raw.get("stage_name") != skey:
            raise ValueError(f"special {sid} stage_name {raw.get('stage_name')} != {skey}")
        if _int(raw.get("special_level") or 0) != slevel:
            raise ValueError(f"special {sid} special_level {raw.get('special_level')} != {slevel}")
        live_bonus = parse_pipe_pairs(raw.get("bonus_attribute"))
        if tuple(live_bonus) != bonus:
            raise ValueError(f"special {sid} bonus {live_bonus} != {bonus}")
        live_extra = parse_pipe_pairs(raw.get("extra_aattribute"))
        if tuple(live_extra) != extra:
            raise ValueError(f"special {sid} extra {live_extra} != {extra}")
        for aid, _ in live_extra:
            _attr_meta_ok(aid)
        if _int(raw["combat"]) != power:
            raise ValueError(f"special {sid} combat {raw['combat']} != {power}")
        live_mats = cost_map([(2, gid, qty) for gid, qty in parse_pipe_pairs(raw.get("material"))])
        expected_mats = {154: mats[0], 155: mats[1], 156: mats[2], 157: mats[3]}
        if live_mats != expected_mats:
            raise ValueError(f"special {sid} materials {live_mats} != {expected_mats}")
        special_stages.append(
            SpecialStageRow(
                sid=sid,
                level_show=show,
                stage_key=skey,
                stage_name=official_text(skey),
                special_level=slevel,
                bonus=live_bonus,
                extra=live_extra,
                power=power,
                materials=live_mats,
            )
        )
    by_stage: dict[str, set[int]] = defaultdict(set)
    for rec in special_stages:
        by_stage[rec.stage_key].add(rec.special_level)
    for key, levels in by_stage.items():
        if key != "fmjd_1" and (len([r for r in special_stages if r.stage_key == key]) != 2 or len(levels) != 1):
            raise ValueError(f"stage {key} pair / special_level unexpected: {levels}")

    json_tables = list(DATA_DIR.glob("*.json"))
    if len(json_tables) != 759:
        raise ValueError(f"expected 759 json tables in live pack, got {len(json_tables)}")

    terms = _terms(pieces, goods, official)
    counts = {
        "lord_equipment": len(equipment),
        "first_six_each": 166,
        "codex": 64,
        "master": len(master),
        "master_3": len(master_3),
        "master_6": len(master_6),
        "enchantment": len(enchant),
        "special_stages": len(special_stages),
        "name_key_bug_rows": name_bug_total,
        "pack_tables": len(json_tables),
    }
    verifications = {
        "row_counts": (
            counts["lord_equipment"],
            166 * 6 + 64,
            counts["master"],
            counts["enchantment"],
            counts["special_stages"],
        ),
        "table_sha256": dict(TABLE_SHA256),
        "overview_match": True,
        "no_unreleased_marks": True,
        "quality_136_166_is_myth_t3_tier_t4": first_six_stages[-1].label == "神話T3"
        and first_six_stages[-1].equip_tier == "icon_txt_T4",
        "master_136_is_myth_t4": master_3[-1].label == "神話T4" and master_6[-1].label == "神話T4",
        "types_456_keep_lv1_names": [p.name for p in pieces if p.typ in (4, 5, 6)]
        == [
            official_text("lord_equip_name04"),
            official_text("lord_equip_name05"),
            official_text("lord_equip_name06"),
        ],
        "values_are_raw": True,
        "data_cutoff": LORD_DATA_CUTOFF,
        "data_pack": LORD_DATA_PACK,
    }

    return TablesData(
        pieces=pieces,
        first_six_stages=first_six_stages,
        codex_stages=codex_stages,
        cost_rows=cost_rows,
        cost_lv166=cost_lv166,
        master_3=master_3,
        master_6=master_6,
        special_stages=special_stages,
        official=official,
        goods=goods,
        counts=counts,
        verifications=verifications,
        terms=terms,
    )


def _terms(pieces: list[PieceInfo], goods: dict, official: dict) -> list[str]:
    terms = {
        official["system"],
        official["three"],
        official["six"],
        official["not_active"],
        official["current_bonus"],
        official["next_bonus"],
        official["add_2"],
        official["add_3"],
        official["add_1"],
        "領主裝備大師屬性",
        "英雄裝備",
        "裝備總表",
        "專武總表",
        "專武",
        "等級階段",
        "階段突破",
        "突破防禦",
        "部族",
        "聯盟",
        "自然",
    }
    for p in pieces:
        terms.add(p.name)
    for item in goods.values():
        terms.add(item["name"])
    for key in (
        "lord_equip_desc001", "lord_equip_desc002", "lord_equip_desc003",
        "lord_equip_desc004", "lord_equip_desc005", "lord_equip_desc006",
        "lord_equip_desc007", "lord_equip_desc0061", "lord_equip_desc0071",
        "lord_equip_desc008", "lord_equip_desc009", "lord_equip_desc010",
        "lord_equip_desc011", "lord_equip_desc013",
    ):
        terms.add(quality_label(key))
    for i in range(1, 11):
        terms.add(official_text(f"fmjd_{i}"))
    for ids in ATTR_IDS_BY_TYPE.values():
        for aid in ids:
            terms.add(A.attr_name(aid))
    for aid in (20, 21, 103, 104, 10103, 10104):
        terms.add(A.attr_name(aid))
    return sorted({t for t in terms if t}, key=len, reverse=True)


def _cost_headers() -> list[str]:
    return [
        "等級",
        "階段",
        goods_name(154),
        goods_name(155),
        goods_name(156),
        goods_name(157),
    ]


def _cost_cells(row: CostRow) -> list[str]:
    return [
        str(row.level),
        row.stage_label,
        cost_qty_cell(row.quantities, 154),
        cost_qty_cell(row.quantities, 155),
        cost_qty_cell(row.quantities, 156),
        cost_qty_cell(row.quantities, 157),
    ]


def _attr_map(pairs: list[tuple[int, int]]) -> dict[int, int]:
    return {a: v for a, v in pairs}


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    o = data.official
    title = "Top Heroes Wiki｜領主裝備總表"
    summary = "七件領主裝備的寫入屬性、品質階段、消耗、三件／六件加成，以及等級階段的特殊列。"

    overview_rows = []
    overview_ids = []
    for p in data.pieces:
        overview_ids.append(f"piece-{p.typ}")
        overview_rows.append([
            e(str(p.typ)),
            H(p.name, terms),
            H(format_attrs(p.lv1_attrs), terms),
            H(format_attrs(p.max_attrs), terms),
            f"{fmt_int(p.lv1_power)}／{fmt_int(p.max_power)}",
        ])
    overview_tbl = table(
        ["類型", "名稱", "1 級寫入（原值）", "滿級寫入（原值）", "1 級／滿級戰力"],
        overview_rows,
        row_ids=overview_ids,
        mobile="cards",
        card_title="名稱",
    )

    quality_rows = []
    for st in data.first_six_stages:
        name_cell = st.label
        if st.note:
            name_cell = f"{st.label}（{st.note}）"
        quality_rows.append([
            f"{st.lo}–{st.hi} ",
            H(name_cell, terms) + " ",
            e(f" {st.quality} "),
            e(f" {_tier_cell(st.equip_tier, short=True)} "),
        ])
    quality_tbl = table(
        ["等級範圍", "官方階段名", "品質欄", "階級欄"],
        quality_rows,
        mobile="sticky",
        card_title="等級範圍",
    )

    codex_quality_rows = []
    for st in data.codex_stages:
        ml = st.note.replace("master_level ", "")
        codex_quality_rows.append([
            f"{st.lo}–{st.hi} ",
            H(st.label, terms) + " ",
            e(f" {st.quality} "),
            e(f" {_tier_cell(st.equip_tier, short=True)} "),
            e(f" {ml} "),
        ])
    codex_quality_tbl = table(
        ["等級範圍", "官方階段名", "品質欄", "階級欄", "大師等級"],
        codex_quality_rows,
        mobile="sticky",
        card_title="等級範圍",
    )

    cost_tbl = table(
        _cost_headers(),
        [[H(c, terms) if i == 1 else e(c) for i, c in enumerate(_cost_cells(r))] for r in data.cost_rows],
        mobile="sticky",
        card_title="等級",
    )
    cost_max_tbl = table(
        _cost_headers(),
        [[H(c, terms) if i == 1 else e(c) for i, c in enumerate(_cost_cells(data.cost_lv166))]],
        mobile="sticky",
        card_title="等級",
    )

    def master_cells(rows: list[MasterRow], attr_ids: tuple[int, ...]) -> tuple[list[str], list[list[str]]]:
        headers = ["等級", "名稱", *[attr_label(i) for i in attr_ids], "戰力"]
        body = []
        for r in rows:
            amap = _attr_map(r.attrs)
            body.append([
                e(str(r.level)),
                H(r.label, terms),
                *[e(fmt_int(amap[i])) for i in attr_ids],
                e(fmt_int(r.power)),
            ])
        return headers, body

    h3, b3 = master_cells(data.master_3, (104, 10103))
    master3_tbl = table(h3, b3, mobile="sticky", card_title="等級")
    h6, b6 = master_cells(data.master_6, (103, 10103, 10104))
    master6_tbl = table(h6, b6, mobile="sticky", card_title="等級")

    special_rows = []
    for r in data.special_stages:
        extra = format_attrs(r.extra) if r.extra else "（無）"
        mats = "／".join(fmt_int(r.materials[g]) for g in GOODS_IDS)
        special_rows.append([
            e(str(r.sid)),
            e(str(r.level_show)),
            H(r.stage_name, terms),
            H(format_attrs(r.bonus, named=False), terms),
            H(extra, terms),
            e(fmt_int(r.power)),
            e(mats),
        ])
    special_tbl = table(
        [
            "編號", "顯示等級", "階段名稱", "常駐加成（原值）", "額外屬性（原值）", "戰力",
            "材料（"
            f"{official_text('goods_name_154')}／"
            f"{official_text('goods_name_155')}／"
            f"{official_text('goods_name_156')}／"
            f"{official_text('goods_name_157')}）",
        ],
        special_rows,
        mobile="cards",
        card_title="階段名稱",
    )

    unused = "、".join(
        f"「{quality_label(k) if k != 'lord_equip_desc012' else official_text(k)}」"
        for k in UNUSED_DESC_KEYS
    )
    g154, g155, g156, g157 = (data.goods[i] for i in GOODS_IDS)
    p1, p2, p3, p4, p5, p6, p7 = (data.pieces[i] for i in range(7))
    c1 = cost_map(p7.lv1_costs)
    c64 = cost_map(p7.max_costs)

    toc = toc_list([
        {"label": "簡介與閱讀說明", "id": "lead"},
        {"label": "七件裝備", "id": "overview"},
        {"label": "品質與階段", "id": "quality"},
        {"label": "神聖法典", "id": "codex"},
        {"label": "消耗（前六件階段起始列）", "id": "costs"},
        {"label": "三件加成與六件加成", "id": "master"},
        {"label": "等級階段", "id": "stages"},
        {"label": "本頁未列入", "id": "out-of-scope"},
        {"label": "資料說明", "id": "notes"},
    ])

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">本頁列出七件領主裝備的寫入屬性、品質階段、消耗、三件／六件加成，以及等級階段Ⅰ–Ⅵ 的特殊列。英雄裝備已有獨立總表，本頁只交叉引用。</p>
    </header>
    {toc}
    <section id="lead">
      <h2>簡介與閱讀說明</h2>
      <p>正文只根據遊戲資料表與官方字串，不評定裝備強弱，也不另外發明連結或名稱。英雄裝備（武器、衣服、鞋子、頭盔）見<a href="equipment.html">{H("裝備總表", terms)}</a>，不把那套表改寫進來。已發佈的<a href="exclusive.html">{H("專武總表", terms)}</a>也不在本頁重複。</p>
      <p>本頁寫的是同一套「{H(o["system"], terms)}」系統（官方名稱「{H(o["property_name"], terms)}」，提示「{H(o["property_dec"], terms)}」）。介面標題同樣是「{H(o["system"], terms)}」。下面列出七件裝備的寫入屬性、品質階段、消耗，以及{H(o["three"], terms)}／{H(o["six"], terms)}和{H("等級階段", terms)}。檔名與分類編號見資料說明。</p>
      <p>字串表沒有「裝魂」「領主裝佩」這兩個名稱，也沒有把本系統叫做附魔。官方介面用的是「{H(official_text("fmjd_1"), terms)}」至「{H(official_text("fmjd_6"), terms)}」與「{H(o["lord_fm4"], terms)}」。本頁用官方中文名，不另譯檔名。檔名見資料說明。</p>
      <ul>
        <li><strong>正文只根據遊戲資料表。</strong>表上對不上唯一系統的，寫明範圍與待補，不推測。</li>
        <li><strong>表頭只用官方屬性名，不再掛編號。</strong>本頁數值先照表上的原值寫，不是面板上的百分比（例如{H("英雄攻擊", terms)}寫 {fmt_int(150)}，不是 1.50%）。編號對照見資料說明。</li>
        <li><strong>不要從解鎖時間或賽季欄自動標未開放。</strong>這三張表沒有這些欄，也沒有據此標{H(p7.name, terms)}或其他件是否已推出，本頁也不標。欄位名見資料說明。</li>
        <li>品質與階段名稱取自官方字串原文（去掉色碼與未填佔位符後綴後為良好、稀有、史詩、傳說T1–T4、神話、神話T1–T4）。表上的品質欄是 2–6，與這些稱呼不是一一對應（例如傳說T1 至傳說T4 的品質欄都是 5），兩欄都照錄，不另改稱。傳說T3、傳說T4 另有獨立名稱。對照見資料說明。</li>
        <li>消耗以類型、物品與數量三欄記錄。物品為 {H(g154["name"], terms)}、{H(g155["name"], terms)}、{H(g156["name"], terms)}、{H(g157["name"], terms)}，說明都寫「用於打造領主裝備」。開頭的類型在這份資料裡對得上貨品；本頁不自行把它解釋成別的系統。這四個名稱取自官方字串，不用骨架貨品表。編號與記法見資料說明。</li>
        <li>官方用語是「{H("部族", terms)}」，不是「部落」；若官方字串本身寫「部落」才照錄。本頁用到的領主裝備字串沒有「部落」。</li>
      </ul>
    </section>
    <section id="overview">
      <h2>七件裝備</h2>
      <p>領主裝備按 1–7 分件。前六件各 166 筆（1–166 級），{H(p7.name, terms)} 64 筆（1–64 級），合計 {fmt_int(1060)}。沒有像英雄裝備那樣的獨立部位名稱表；本頁用類型與官方裝備名。同一類型在全部等級寫入的屬性不變。目錄名稱一律取各件 1 級的官方名稱。</p>
      {overview_tbl}
      <p>前六件在同一等級的戰力相同。{H(p1.name, terms)}、{H(p3.name, terms)}、{H(p5.name, terms)} 的數值曲線相同（只換陣營生命屬性）；{H(p2.name, terms)}、{H(p4.name, terms)}、{H(p6.name, terms)} 是另一條曲線（只換陣營攻擊屬性）。表沒有再給這兩組套裝名稱，本頁不另起套名。</p>
      <p>各件各級列的編號記法見資料說明。</p>
    </section>

    <section id="quality">
      <h2>品質與階段</h2>
      <p>前六件的等級與階段名稱、品質欄、階級欄對照如下（六件斷檔相同）。階段起始列的星數欄為 0。名稱對照見資料說明。</p>
      {quality_tbl}
      <p>字串表另有{H(unused, terms)}。前六件的裝備列沒有用到這幾條。神話T4 這條名稱出現在大師表 136 級（見下節），與裝備列在 136–166 級仍寫「{H("神話T3", terms)}」、只把階級欄改成 T4 不一致。本頁兩處都照錄，不自行把裝備列改稱為神話T4。對照見資料說明。</p>
      <p>{H(g157["name"], terms)}說明：「{H(g157["desc"], terms)}」與上表在 72 級進入「{H("神話", terms)}」、並從此開始消耗{H(g157["name"], terms)}相符；表沒有另給「晉升」專表。編號對照見資料說明。</p>
      <p>每筆還有星數相關欄位。在同一名稱階段內，星數會從 0 走到 3，子星數在上限內遞增；換到下一階段時星數回到 0。表沒有說明這些欄等於介面第幾星，本頁不自行解釋。欄位名見資料說明。</p>
      <p><strong>136–166 級的名稱例外：</strong>{H(p4.name, terms)}、{H(p5.name, terms)}、{H(p6.name, terms)}從 136 級起，名稱改掛成{H(p3.name, terms)}，共各 31 筆。圖示仍是各件自己的，寫入屬性仍是該件的聯盟或部族攻擊列，與{H(p3.name, terms)}（聯盟生命列）不同。本頁在總表保留各件 1 級的名稱，並註明這 31 筆名稱與圖示、屬性不一致；不把這三件在 136 級之後改稱為{H(p3.name, terms)}。對照見資料說明。</p>
    </section>
    <section id="codex">
      <h2>{e(p7.name)}</h2>
      <p>{H(p7.name, terms)}只有{H("神話", terms)}及{H("神話T1", terms)}–{H("神話T3", terms)}，沒有良好至傳說列，也沒有神話T4 列：</p>
      {codex_quality_tbl}
      <p>大師等級欄與前六件進入神話以後的等級（72–135）對得上，表沒有再寫這個欄位的含義。64 筆都有大師附加欄（1 級 {fmt_int(p7.master_additional_lv1)}，64 級 {fmt_int(p7.master_additional_max)}）；前六件此欄全是 -1。介面字串寫：「{H(o["add_1"], terms)}」「{H(o["add_2"], terms)}」「{H(o["add_3"], terms)}」。大師附加欄沒有對應的寫入屬性，本頁只記原值，不推測它加在哪一條屬性上。欄名見資料說明。</p>
      <p>與解鎖有關的字串有三條，表沒有標哪一條對應{H(p7.name, terms)}、哪一條對應{H("等級階段", terms)}，本頁全部照錄，不自行取捨：</p>
      <ul>
        <li>「{H(o["unlock_1"], terms)}」</li>
        <li>「{H(o["unlock_2"], terms)}」</li>
        <li>「{H(o["unlock_3"], terms)}」</li>
      </ul>
      <p>1 級消耗是{H(g155["name"], terms)} {fmt_int(c1[155])}、{H(g156["name"], terms)} {fmt_int(c1[156])}；之後出現{H(g157["name"], terms)}（從 17 級起）。與前六件從{H(g154["name"], terms)}、{H(g155["name"], terms)}起算的消耗不同。滿級（64）消耗是{H(g156["name"], terms)} {fmt_int(c64[156])}、{H(g157["name"], terms)} {fmt_int(c64[157])}。</p>
    </section>
    <section id="costs">
      <h2>消耗（前六件階段起始列）</h2>
      <p>六件在同一等級的消耗相同。下表列各階段第一級；不是完整養成曲線。消耗以類型、物品與數量記錄。本頁不計算累計消耗。記法見資料說明。</p>
      {cost_tbl}
      <p>另錄 166 級（滿級）消耗，這一列不是階段起始列：</p>
      {cost_max_tbl}
    </section>
    <section id="master">
      <h2>{e(o["three"])}與{e(o["six"])}</h2>
      <p>大師加成表 {fmt_int(34)} 筆：件數欄 3 與 6 各 17 筆。介面寫「{H(o["three"], terms)}」「{H(o["six"], terms)}」「{H(o["own_n"], terms)}」。等級欄與前六件的階段起始等級對得上（{e("、".join(str(x) for x in MASTER_LEVELS))}）；屬性名稱欄在等級 136 使用「{H("神話T4", terms)}」。表沒有寫等級欄是「六件都達到」還是「其中若干件達到」，本頁只記表上的件數與等級。欄名見資料說明。</p>
      <p>{H(o["three"], terms)}一律寫{H(attr_label(104), terms)}與{H(attr_label(10103), terms)}：</p>
      {master3_tbl}
      <p>{H(o["six"], terms)}寫{H(attr_label(103), terms)}、{H(attr_label(10103), terms)}、{H(attr_label(10104), terms)}：</p>
      {master6_tbl}
      <p>介面另有「{H(o["not_active"], terms)}」、「{H(o["current_bonus"], terms)}／{H(o["next_bonus"], terms)}」。表沒有再寫啟動條件的計算式。</p>
    </section>

    <section id="stages">
      <h2>等級階段</h2>
      <p>等級階段表 {fmt_int(240)} 筆，編號與加成等級皆為 1–240，顯示等級為 1–50，額外等級為 0–4。全部列的經驗欄都是 -1，經驗怎麼累積不在這張表。這張表沒有外鍵指向某一件裝備，本頁不當成某一件的專屬表，也不把 240 級與前六件的 166 級或{H(p7.name, terms)}的 64 級自行對成同一條等級。欄名見資料說明。</p>
      <p>每一筆的常駐加成欄都是{H(attr_label(10103), terms)}、{H(attr_label(10104), terms)}、{H(attr_label(103), terms)}、{H(attr_label(104), terms)}。其中 {fmt_int(11)} 筆 標為特殊等級，並掛上階段名稱與額外屬性欄（{H(attr_label(20), terms)}、{H(attr_label(21), terms)}）。字串表還有「{H(official_text("fmjd_7"), terms)}」至「{H(official_text("fmjd_10"), terms)}」，本表沒有出現。對照見資料說明。</p>
      {special_tbl}
      <p>同一階段名稱會出現兩筆（Ⅱ 至 Ⅵ），特殊等級欄 在這兩筆上相同。表沒有說明為何一個階段寫兩次，以及其餘 229 筆（沒有階段名稱）與這 11 筆如何銜接。材料欄只在上表這 11 筆逐列對過；其他列也有 材料欄，本頁不逐列展開。</p>
    </section>
    <section id="out-of-scope">
      <h2>本頁未列入</h2>
      <ul>
        <li>英雄裝備、專武、裝備精通（那是英雄裝備系統）。英雄裝備見<a href="equipment.html">裝備總表</a>；專武見已發佈的<a href="exclusive.html">專武總表</a>。</li>
        <li>1–166 級（或神聖法典 1–64 級）的完整屬性與消耗曲線，以及累計材料。</li>
        <li>等級階段其餘 229 筆的逐級加成，以及經驗如何計算（表上經驗欄全是 -1）。</li>
        <li>大師附加欄加在哪一條屬性上；三件／六件加成的精確啟動條件；神聖法典三條解鎖字串各適用於哪一個介面。</li>
        <li>星數／子星數欄 與介面星數、階段突破的對應。</li>
        <li>{H(p4.name, terms)}、{H(p5.name, terms)}、{H(p6.name, terms)}在 136–166 級名稱改掛「{H(p3.name, terms)}」時，客戶端實際顯示哪一個名稱。</li>
        <li>活動（領主裝備試煉、骷髏王材料、養成積分）與儲值禮包內容。</li>
        <li>領主裝備與英雄、士兵的搭配模擬，以及強弱評定。士兵、秘寶等其餘圖鑑類也不在本頁。</li>
      </ul>
    </section>
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>以下是整理用註記，查屬性與消耗可略過。</li>
        <li>七件總表「類型」原欄名 <code>type</code>。等級階段特殊列表頭「編號」「顯示等級」原名 <code>id</code>、<code>level_show</code>。階級欄可見寫 T1–T4，原名 <code>icon_txt_T1</code>–<code>icon_txt_T4</code>（欄位 <code>equip_tier</code>）；字串表沒有這些鍵的顯示名，不另編造階級稱呼。</li>
        <li>可見正文「類型」「寫入屬性」「名稱對照」對應類型編號、屬性編號與名稱鍵；可見改寫「檔名見資料說明」「對照見資料說明」，鍵名對照見此。可見等級階段表材料欄改寫官方貨品名（<code>goods_name_154</code>／<code>155</code>／<code>156</code>／<code>157</code>）；編號對照見此。滿級（64）是等級不是屬性編號。不要從 <code>unlocktime</code>、<code>season</code> 自動標未開放。品質與階段名稱取自 <code>lord_equip_desc001</code>–<code>013</code> 的原文（去掉色碼與未填的 <code>{{0}}</code> 後綴）。表上的 <code>quality</code> 欄是 2–6，與這些稱呼不是一一對應（例如傳說T1 至傳說T4 的 <code>quality</code> 都是 5）。傳說T3、傳說T4 的名稱鍵是 <code>lord_equip_desc0061</code>、<code>lord_equip_desc0071</code>。消耗在表上寫成 <code>2|物品id|數量</code>；物品 154–157 名稱取自 <code>goods_name_154</code>–<code>157</code>，不用骨架貨品表。類型 2 在本抽取裡對得上貨品，本頁不自行把開頭的 2 解釋成別的系統。</li>
        <li>系統分類是 <code>attr_category</code> 49。介面標題鍵是 <code>ui_lordequip_002</code>。對應表為 <code>lord_equipment.json</code>（{fmt_int(data.counts["lord_equipment"])} 筆）、<code>lord_equip_master.json</code>（{fmt_int(data.counts["master"])} 筆，介面字串 <code>ui_lordequip_012</code>／<code>013</code>）、<code>lord_equipment_enchantment.json</code>（{fmt_int(data.counts["enchantment"])} 筆）。屬性名優先用 <code>attribute_name_{{id}}</code>。<code>show_type=2</code> 只記表內原值，不自行換算成百分比。除{H("突破防禦", terms)}（64）為 <code>type=1</code>、<code>show_type=1</code> 外，本頁其餘寫入屬性皆為 <code>type=2</code>、<code>show_type=2</code>。例如{H("英雄攻擊", terms)}（103）{fmt_int(150)}，不是 1.50%。消耗物品編號 154–157 只在資料說明保留，表頭改用官方物品名。資料表檔名含 <code>enchantment</code>；階段鍵是 <code>fmjd_1</code>–<code>fmjd_6</code>，說明鍵是 <code>lord_fm4</code>。</li>
        <li>資料出自遊戲資料表與官方字串（lord_equipment、lord_equip_master、lord_equipment_enchantment、attr_category、attribute、strings_zh.json），資料截至 {LORD_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {e(LORD_DATA_PACK)}（759 張表），打包時戳 {LORD_DATA_PACKED}（香港時間）。這三張領主裝備表與第 25 章所用 2026-11-05 解壓檔、以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。本頁用到的領主裝備相關官方字串與這三份歸檔一致。顯示規則依攻略手冊「領主裝備圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。這不是官方 wiki。</li>
        <li>屬性表 <code>attribute.json</code> 在後續包多了 <code>NameKey</code> 欄，與 2026-11-05 解壓檔不是整檔相同；本頁用到的屬性編號在 <code>type</code>、<code>show_type</code> 與名稱鍵上沒有差異，顯示名稱取自 <code>attribute_name_{{id}}</code>。</li>
      </ul>
    </section>
"""
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {LORD_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_lord_equipment_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def render_markdown(data: TablesData) -> str:
    o = data.official
    g = data.goods
    p7 = data.pieces[6]
    lines: list[str] = []
    add = lines.append

    add("# Top Heroes Wiki｜領主裝備總表")
    add("")
    add(
        f"資料截至 {LORD_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {LORD_DATA_PACK}（759 張表），打包時戳 {LORD_DATA_PACKED}（香港時間）。"
        "這三張領主裝備表（lord_equipment、lord_equip_master、lord_equipment_enchantment）"
        "與第 25 章所用 2026-11-05 解壓檔、以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；"
        "這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "顯示規則依攻略手冊「領主裝備圖鑑」第一版（2026-11-15，香港時間）。"
    )
    add("")
    add(
        "正文只根據遊戲資料表與官方字串，不評定裝備強弱。"
        "英雄裝備見[裝備總表](equipment.html)，專武見已發佈的[專武總表](exclusive.html)，本頁不重複那兩套名錄。"
        f"官方系統名是「{o['system']}」（`attr_category` 49；介面 `ui_lordequip_002`）。"
        "字串表沒有「裝魂」「領主裝佩」，也不把本系統叫做附魔。"
        f"官方階段名是「{official_text('fmjd_1')}」至「{official_text('fmjd_6')}」，說明為：「{o['lord_fm4']}」。"
    )
    add("")
    add("## 閱讀說明")
    add("")
    add("- 屬性名優先用 `attribute_name_{id}`。`show_type=2` 只記表內原值，不自行換成百分比。除突破防禦（64）為 `type=1`、`show_type=1` 外，本頁其餘寫入屬性皆為 `type=2`、`show_type=2`。例如英雄攻擊（103）150，不是 1.50%。")
    add("- 不要從 `unlocktime`、`season` 自動標未開放。這三張表沒有這些欄，本頁也不把神聖法典或其他件標成未開放。")
    add("- 品質名稱去掉色碼與 `{0}` 後綴後照錄；`quality` 2–6 與傳說T1–T4 等稱呼不是一一對應，兩欄都保留。136–166 級裝備列名稱鍵仍是神話T3，`equip_tier` 為 T4；大師表 level 136 才寫神話T4。")
    add(f"- 消耗格式為 `2|物品id|數量`。物品：154 {g[154]['name']}、155 {g[155]['name']}、156 {g[156]['name']}、157 {g[157]['name']}（說明都寫「用於打造領主裝備」）。名稱取自官方字串，不用骨架貨品表。")
    add("- 官方用語是「部族」。本頁用到的領主裝備字串沒有「部落」。")
    add("")
    add("## 七件裝備")
    add("")
    add("前六件各 166 級，神聖法典 64 級，合計 1,060。目錄名稱取各件 1 級官方名稱（type 4／5／6 在 136 級起名稱鍵改掛統禦王冠，見下節，不改稱）。")
    add("")
    overview_rows = []
    for p in data.pieces:
        overview_rows.append([
            str(p.typ),
            p.name,
            format_attrs(p.lv1_attrs),
            format_attrs(p.max_attrs),
            f"{fmt_int(p.lv1_power)}／{fmt_int(p.max_power)}",
        ])
    add(md_table(["類型", "名稱", "1 級寫入（原值）", "滿級寫入（原值）", "1 級／滿級戰力"], overview_rows))
    add("")
    add(
        f"前六件同一等級戰力相同（1 級 {fmt_int(data.pieces[0].lv1_power)}／滿級 {fmt_int(data.pieces[0].max_power)}）。"
        f"{data.pieces[0].name}、{data.pieces[2].name}、{data.pieces[4].name} 數值曲線相同（只換陣營生命屬性）；"
        f"{data.pieces[1].name}、{data.pieces[3].name}、{data.pieces[5].name} 是另一條曲線（只換陣營攻擊屬性）。表沒有給這兩組套名，不另起。"
        f"編號規律 `13{{type}}0{{等級三位}}`，例如 {data.pieces[0].name} 1 級為 {data.pieces[0].lv1_id}，{p7.name} 64 級為 {p7.max_id}。"
    )
    add("")
    add("## 品質與階段")
    add("")
    qrows = []
    for st in data.first_six_stages:
        name = st.label
        if st.note:
            name = f"{st.label}（名稱鍵仍是神話T3，{st.desc_key}）"
        qrows.append([f"{st.lo}–{st.hi}", name, st.desc_key, str(st.quality), _tier_cell(st.equip_tier)])
    add(md_table(["等級", "名稱字串", "名稱鍵", "quality", "equip_tier"], qrows))
    add("")
    unused = "、".join(
        f"「{quality_label(k) if k != 'lord_equip_desc012' else official_text(k)}」（`{k}`）"
        for k in UNUSED_DESC_KEYS
    )
    add(f"未掛在前六件裝備列的字串：{unused}。神話T4 出現在大師表 level 136 的 `attr_key`，與裝備列 136–166 仍寫神話T3、只改 tier 為 T4 不一致，兩處照錄。")
    add("")
    add(f"{g[157]['name']}（157）說明：「{g[157]['desc']}」與 72 級進入神話並開始消耗龍之血相符；沒有另給晉升專表。")
    add("")
    add(
        f"**名稱鍵例外：** type 4／5／6（{data.pieces[3].name}、{data.pieces[4].name}、{data.pieces[5].name}）"
        f"從 136 級起 `lord_equip_name` 改掛 `lord_equip_name03`（{data.pieces[2].name}），各 31 筆。"
        f"圖示仍是 `{data.pieces[3].icon}`／`{data.pieces[4].icon}`／`{data.pieces[5].icon}`，寫入屬性仍是各件自己的聯盟或部族攻擊列。"
        "總表保留 1 級官方名稱，不把這三件改稱為統禦王冠。"
    )
    add("")
    add("## 神聖法典")
    add("")
    crows = []
    for st in data.codex_stages:
        crows.append([
            f"{st.lo}–{st.hi}",
            st.label,
            st.desc_key,
            str(st.quality),
            _tier_cell(st.equip_tier),
            st.note.replace("master_level ", ""),
        ])
    add(md_table(["等級", "名稱字串", "名稱鍵", "quality", "equip_tier", "master_level"], crows))
    add("")
    add(
        f"`master_level` 對得上前六件神話之後的 72–135，表沒有再寫含義。"
        f"64 筆都有 `master_additional`（1 級 {fmt_int(p7.master_additional_lv1)}，64 級 {fmt_int(p7.master_additional_max)}）；前六件此欄為 -1。"
        f"介面字串：「{o['add_1']}」「{o['add_2']}」「{o['add_3']}」。只記原值，不推測加在哪一條屬性。"
    )
    add("")
    add("與解鎖有關的字串有三條，表沒有標各適用哪一個介面，全部照錄：")
    add("")
    add(f"- 「{o['unlock_1']}」（`{o['unlock_1_key']}`）")
    add(f"- 「{o['unlock_2']}」（`{o['unlock_2_key']}`）")
    add(f"- 「{o['unlock_3']}」（`{o['unlock_3_key']}`）")
    add("")
    c1 = cost_map(p7.lv1_costs)
    c64 = cost_map(p7.max_costs)
    add(
        f"1 級消耗：{g[155]['name']} {fmt_int(c1[155])}、{g[156]['name']} {fmt_int(c1[156])}；"
        f"之後出現{g[157]['name']}。滿級（64）消耗：{g[156]['name']} {fmt_int(c64[156])}、{g[157]['name']} {fmt_int(c64[157])}。"
    )
    add("")
    add("## 消耗（前六件階段起始列）")
    add("")
    add("六件同一等級消耗相同。下表只列階段第一級，另附 166 級滿級列。不計算累計消耗。")
    add("")
    add(md_table(_cost_headers(), [_cost_cells(r) for r in data.cost_rows] + [_cost_cells(data.cost_lv166)]))
    add("")
    add("## 三件加成與六件加成")
    add("")
    add(
        f"`lord_equip_master` 34 筆：`equip_num` 3 與 6 各 17 筆。介面寫「{o['three']}」「{o['six']}」「{o['own_n']}」。"
        f"`level` 為 {'、'.join(str(x) for x in MASTER_LEVELS)}；level 136 的 `attr_key` 是神話T4。"
        "表沒有寫啟動條件是六件都達到還是其中若干件達到，只記 `equip_num` 與 `level`。"
    )
    add("")
    add("三件加成一律為英雄生命（104）與所有士兵攻擊（10103）：")
    add("")

    def master_md(rows: list[MasterRow], attr_ids: tuple[int, ...]) -> str:
        headers = ["等級", "名稱", *[attr_label(i) for i in attr_ids], "戰力"]
        body = []
        for r in rows:
            amap = _attr_map(r.attrs)
            body.append([str(r.level), r.label, *[fmt_int(amap[i]) for i in attr_ids], fmt_int(r.power)])
        return md_table(headers, body)

    add(master_md(data.master_3, (104, 10103)))
    add("")
    add("六件加成為英雄攻擊（103）、所有士兵攻擊（10103）、所有士兵生命（10104）：")
    add("")
    add(master_md(data.master_6, (103, 10103, 10104)))
    add("")
    add(f"介面另有「{o['not_active']}」（`ui_lordequip_009`）、「{o['current_bonus']}／{o['next_bonus']}」。表沒有啟動條件計算式。")
    add("")
    add("## 等級階段")
    add("")
    add(
        "`lord_equipment_enchantment` 240 筆，`id` 與 `bonus_lv` 為 1–240，`level_show` 為 1–50，`level_extra` 為 0–4。"
        "全部 `exp` 為 -1。這張表沒有外鍵指向某一件裝備，不當成單件專屬表，也不把 240 與 166 或 64 對成同一條等級。"
        "每筆常駐加成都是所有士兵攻擊（10103）、所有士兵生命（10104）、英雄攻擊（103）、英雄生命（104）。"
        "11 筆 `IsSpecialLevelData=true` 另有階段名稱與額外屬性（技能增傷 20、技能減傷 21）。"
        f"字串另有「{official_text('fmjd_7')}」至「{official_text('fmjd_10')}」，本表沒有出現。"
        "其餘 229 筆不展開。"
    )
    add("")
    srows = []
    for r in data.special_stages:
        extra = format_attrs(r.extra) if r.extra else "（無）"
        mats = "／".join(fmt_int(r.materials[gid]) for gid in GOODS_IDS)
        srows.append([
            str(r.sid),
            str(r.level_show),
            r.stage_name,
            format_attrs(r.bonus, named=False),
            extra,
            fmt_int(r.power),
            mats,
        ])
    add(md_table(
        ["編號", "顯示等級", "階段名稱", "常駐加成（原值）", "額外屬性（原值）", "戰力", "材料（154／155／156／157）"],
        srows,
    ))
    add("")
    add("同一階段名稱會出現兩筆（Ⅱ 至 Ⅵ），`special_level` 在這兩筆上相同。表沒有說明為何寫兩次。材料只核對這 11 筆。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 英雄裝備、專武、裝備精通（`equipment_master.json`，屬英雄裝備系統）。")
    add("- 1–166 級（或神聖法典 1–64 級）的完整屬性與消耗曲線，以及累計材料。")
    add("- 等級階段其餘 229 筆的逐級加成，以及經驗如何計算。")
    add("- `master_additional` 加在哪一條屬性上；三件／六件加成的精確啟動條件；三條解鎖字串各適用於哪一個介面。")
    add("- `star`／`star_sub` 與介面星數、階段突破的對應。")
    add(f"- {data.pieces[3].name}、{data.pieces[4].name}、{data.pieces[5].name}在 136–166 級名稱鍵改掛「{data.pieces[2].name}」時，客戶端實際顯示哪一個名稱。")
    add("- 活動與儲值禮包內容。")
    add("- 搭配模擬、強弱評定；士兵、秘寶等其餘圖鑑類。")
    add("")
    add("## 資料說明")
    add("")
    add(
        f"- 資料截至 {LORD_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {LORD_DATA_PACK}（759 張表），"
        f"打包時戳 {LORD_DATA_PACKED}（香港時間）。三張領主裝備表與第 25 章 2026-11-05 解壓檔位元組相同，"
        "但不表示整個 LocalLow 包相同。顯示規則依攻略手冊「領主裝備圖鑑」第一版（2026-11-15，香港時間）。這不是官方 wiki。"
    )
    add("")
    return "\n".join(lines)
