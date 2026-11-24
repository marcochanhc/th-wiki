"""Compile the published 士兵 catalog tables."""

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
from .strings import clean, has_key, t
from .tables import load_table


# 士兵總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫 2026-11-23。
# 士兵主表、光輝表與兵裝三表與第 19 章所用 2026-11-05 解壓檔、以及
# 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同，
# 但不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。
TROOP_DATA_CUTOFF = "2026-11-23"
TROOP_DATA_PACK = "app-1.129.12_table-1.0.43173"
TROOP_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "troop.json": "17205aabfc53f1e738f785650f318aa55963c557a925a41d866fea82b6742205",
    "shine_troop.json": "1b438f74a16289c9c0ed5e6a05c7c65df19e0493fdb1c82fc82f25d01d7ebbf1",
    "troop_skin_level.json": "99742316d855cd03859cb2e07d1f508b7f324b911d65584b9b0c67c7ed4af0f8",
    "troop_skin_break.json": "9993e6aadd467fb86900a04bc423700eefc7fa7aaf77796c66298f2f90f38902",
    "troop_skin_honor_break.json": "ee52ee5f82dc9ea9108402e2cde68b766a18ae72b22d2b72924aa3ce088e5bf6",
    "jump.json": "05169023beeba039e94014a8f45024004faee856a85c5bafd47420fbd72ec7d6",
}

SKIN_CATALOG = {
    5301: (2024501, 2024501),
    5302: (2024502, 2024502),
    5403: (2024506, 2024543),
    5404: (2024507, 2024544),
    5405: (2024512, 2024545),
    5406: (2024546, 2024546),
    5407: (2024547, 2024547),
    5501: (2024508, 2024551),
    5502: (2024510, 2024552),
    5503: (2024513, 2024553),
    5504: (2024515, 2024554),
    5505: (2024516, 2024555),
    5506: (2024556, 2024556),
    5507: (2024557, 2024557),
    5508: (2024558, 2024558),
    5509: (2024559, 2024559),
    5510: (2024560, 2024560),
    5511: (2024561, 2024561),
    5512: (2024562, 2024562),
    5513: (2024563, 2024563),
    5514: (2024564, 2024564),
}
NAMELESS_SKIN_GROUPS = (5401, 5402)
GUNNER_GOODS_ID = 2024503
HONOR_GOODS_ID = 1017
JUMP_SKIN_GROUPS = (5301, 5302, 5403, 5404, 5405, 5406, 5407, 5501, 5502, 5503, 5504, 5505, 5506, 5507)

PREFIXES = ("初級", "進階", "熟練", "優秀", "精英", "高級", "大師", "專家", "明星", "傳奇", "天御", "天穹")
QUALITY_BY_LEVEL = {1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 5, 10: 5, 11: 5, 12: 5}

CHAPTER_A_STATS = {
    1: (3, 33, 205, 15, 18), 2: (6, 69, 224, 30, 43), 3: (9, 108, 245, 45, 68),
    4: (12, 151, 268, 60, 93), 5: (15, 205, 295, 75, 118), 6: (18, 267, 325, 90, 143),
    7: (21, 334, 370, 105, 168), 8: (26, 443, 425, 135, 193), 9: (32, 580, 500, 175, 218),
    10: (40, 770, 600, 220, 243), 11: (45, 850, 700, 265, 268), 12: (50, 900, 800, 310, 293),
}
CHAPTER_B_STATS = {
    1: (3, 36, 0, 15, 18), 2: (6, 60, 0, 30, 43), 3: (10, 100, 0, 45, 68),
    4: (20, 200, 0, 60, 93), 5: (30, 300, 0, 75, 118), 6: (40, 500, 0, 90, 143),
    7: (60, 750, 0, 105, 168), 8: (75, 950, 0, 135, 193), 9: (95, 1200, 0, 175, 218),
    10: (113, 1500, 0, 220, 243),
}
CHAPTER_A_COSTS = {
    1: (75, 1, 1, 12, 1, 1, 5000, 12), 2: (150, 5, 5, 18, 2, 2, 5500, 16),
    3: (225, 40, 40, 24, 8, 8, 6000, 20), 4: (300, 100, 100, 30, 20, 20, 7000, 28),
    5: (400, 200, 200, 35, 40, 40, 8000, 36), 6: (500, 400, 400, 40, 80, 80, 9000, 40),
    7: (550, 500, 500, 45, 100, 100, 10000, 44), 8: (600, 600, 600, 50, 120, 120, 10000, 48),
    9: (700, 700, 700, 60, 140, 140, 10000, 56), 10: (800, 900, 900, 70, 180, 180, 10000, 64),
    11: (900, 1100, 1100, 80, 220, 220, 10000, 72), 12: (1000, 1300, 1300, 100, 260, 260, 10000, 80),
}
CHAPTER_B_COSTS = {
    1: (75, 1, 1, 15, 1, 1), 2: (150, 5, 5, 21, 2, 2), 3: (225, 40, 40, 27, 8, 8),
    4: (300, 100, 100, 36, 20, 20), 5: (400, 300, 300, 45, 40, 40), 6: (500, 500, 500, 50, 100, 100),
    7: (550, 800, 800, 55, 160, 160), 8: (600, 1000, 1000, 60, 200, 200),
    9: (700, 1400, 1400, 70, 280, 280), 10: (800, 1800, 1800, 80, 360, 360),
}
CHAPTER_SHINE = {
    1: (1490001, 1490004, 1490007, 8, 190, 100, 20, 12, 125045),
    2: (1490002, 1490005, 1490008, 15, 212, 200, 40, 32, 125050),
    3: (1490003, 1490006, 1490009, 23, 324, 300, 60, 52, 125055),
    4: (1490010, 1490012, 1490014, 27, 404, 350, 70, 62, 125060),
    5: (1490011, 1490013, 1490015, 30, 464, 400, 80, 72, 125065),
    6: (1490016, 1490017, 1490018, 34, 504, 450, 100, 82, 125070),
    7: (1490019, 1490021, 1490023, 39, 534, 500, 120, 92, 125075),
    8: (1490020, 1490022, 1490024, 44, 564, 550, 140, 102, 125080),
}
DIVINE_TRAIN_TIME = {1: 150, 2: 210, 3: 270, 4: 360, 5: 450}
FRONT_DESC_RE = re.compile(r"\s*（用於士兵兵裝解鎖或突破[，,].*）\s*$")
LEDE = (
    "本頁列出士兵的名稱、單兵數值、訓練與治療消耗、光輝建築，以及兵裝名錄與已鎖定的聯盟兵裝面板對照。"
    "同一種士兵有兩套編號，不要混用；差別見內文。"
    "行軍造型不是本頁主體。英雄裝備與領主裝備已有獨立總表，本頁只交叉引用。"
)


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def _int(value) -> int:
    return int(float(str(value).strip()))


def official_text(key: str, default: str = "") -> str:
    if key is None:
        return default
    return clean(t(key, default))


def goods_name(gid: int) -> str:
    name = official_text(f"goods_name_{gid}")
    if not name:
        raise ValueError(f"missing official goods_name_{gid}")
    return name


def goods_des(gid: int) -> str:
    for key in (f"goods_des_{gid}", f"goods_desc_{gid}"):
        if has_key(key):
            return official_text(key)
    return ""


def goods_front(gid: int) -> str:
    return FRONT_DESC_RE.sub("", goods_des(gid)).strip()


def load_clause(desc: str) -> str:
    if "可同時被多隊裝載" in (desc or ""):
        return "可同時被多隊裝載"
    if "只可同時被一隊裝載" in (desc or ""):
        return "只可同時被一隊裝載"
    return ""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_pipe_cost(raw) -> list[tuple[int, int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    out: list[tuple[int, int, int]] = []
    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        for item in raw:
            parts = str(item).split("|")
            if len(parts) >= 3:
                out.append((_int(parts[0]), _int(parts[1]), _int(parts[2])))
        return out
    if isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
        if raw and isinstance(raw[0], list) and raw[0] and isinstance(raw[0][0], (list, tuple)):
            for group in raw:
                for typ, gid, qty in group:
                    out.append((_int(typ), _int(gid), _int(qty)))
            return out
        for item in raw:
            if len(item) >= 3:
                out.append((_int(item[0]), _int(item[1]), _int(item[2])))
        return out
    return out


def qty_of(pairs: list[tuple[int, int, int]], gid: int) -> int | None:
    for _typ, resid, qty in pairs:
        if resid == gid:
            return qty
    return None


def join_slash(values) -> str:
    return "／".join(str(v) for v in values)


def display_num_cell(raw) -> str:
    if raw in (None, "", [], -1):
        return "—"
    return "、".join(str(x) for x in raw)


def attr_label(attr_id: int, attr_by: dict) -> str:
    """Prefer attribute_name_{id}; fall back to the attribute table name key. Never invent."""
    name = official_text(f"attribute_name_{attr_id}")
    if name:
        return name
    row = attr_by.get(int(attr_id)) or {}
    return official_text(row.get("name") or "")


def table_name_label(attr_id: int, attr_by: dict) -> str:
    row = attr_by.get(int(attr_id)) or {}
    return official_text(row.get("name") or "")


def attr_meta(attr_id: int, attr_by: dict) -> dict:
    return attr_by.get(int(attr_id)) or {}


def line_of(troop_id: int) -> str:
    if troop_id in set(range(1001, 1013)) | set(range(2001, 2013)) | set(range(3001, 3013)):
        return "A"
    if troop_id in set(range(1901, 1911)) | set(range(2901, 2911)) | set(range(3901, 3911)) | set(range(4901, 4911)):
        return "B"
    return "?"


def troop_costs(row: dict) -> tuple[int, int, int, int, int, int, int, int]:
    train = row.get("trainCosts") or parse_pipe_cost(row.get("train_resource"))
    treat = row.get("treatCosts") or parse_pipe_cost(row.get("treat_cost"))
    return (
        _int(row["train_time"]),
        _int(qty_of(train, 4) or 0),
        _int(qty_of(train, 5) or 0),
        _int(row["treat_time"]),
        _int(qty_of(treat, 4) or 0),
        _int(qty_of(treat, 5) or 0),
        _int(row.get("lvup_time") or 0),
        _int(row.get("donate_medal") or 0),
    )


def pick_level_row(rows: list[dict], level: int) -> dict:
    cands = [r for r in rows if r["level"] == level]
    if not cands:
        raise KeyError(f"missing skin level {level}")
    if level <= 16:
        return cands[0]
    cands = [r for r in cands if r.get("level_small") == 0] or cands
    return cands[0] if level < 50 else cands[-1]


def break_cost_cell(row: dict, *, show_id: bool) -> str:
    costs = parse_pipe_cost(row.get("cost"))
    if not costs:
        return "（空）"
    _typ, gid, qty = costs[0]
    return f"{gid}×{qty}" if show_id else f"×{qty}"


def _slash_powers(rows: list[dict]) -> str:
    return join_slash(r["fightforce"] for r in rows)


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def _prefix_rows() -> list[list[str]]:
    rows = []
    for lv, prefix in enumerate(PREFIXES, 1):
        a = f"{1000 + lv}／{2000 + lv}／{3000 + lv}"
        if lv <= 10:
            b = f"{1900 + lv}／{2900 + lv}／{3900 + lv}"
            if lv == 1:
                b += "（神族 4901 無名稱字串）"
            elif lv == 10:
                b += "、神族 4910"
        else:
            a = f"僅 {1000 + lv}／{2000 + lv}／{3000 + lv}"
            b = "無"
        rows.append([str(lv), str(QUALITY_BY_LEVEL[lv]), prefix, a, b])
    return rows


@dataclass
class Official:
    races: dict[int, str]
    formulas: dict[str, str]
    buildings: dict[int, tuple[str, str]]
    resources: dict[int, str]
    categories: dict[int, tuple[str, str]]
    skin_system: str
    skin_training: list[str]
    shine_tip: str
    team_tips: str
    honor_forbid: str
    honor_unlock: str
    honor_item_name: str
    honor_item_desc: str
    gunner_name: str
    gunner_front: str
    gunner_clause: str
    leftover_name: str
    leftover_desc: str
    duel: str
    march_name: str
    march_desc: str
    shield_name: str
    shield_desc: str
    tribe_word: str


@dataclass
class SkinInfo:
    group: int
    name: str
    name_id: int | None
    cost_id: int | None
    quality: int
    has_break: bool
    clause: str
    front: str
    jump: bool
    break_desc: str
    display_num: bool


@dataclass
class TablesData:
    official: Official
    attr_by: dict
    troops: dict[int, dict]
    shine: list[dict]
    skins: dict[int, SkinInfo]
    skin_levels: dict[int, list[dict]]
    skin_breaks: dict[int, list[dict]]
    skin_honors: dict[int, list[dict]]
    terms: list[str] = field(default_factory=list)
    verifications: dict = field(default_factory=dict)


def load_tables_data() -> TablesData:
    for name, expected in TABLE_SHA256.items():
        path = DATA_DIR / name
        got = file_sha256(path)
        if got != expected:
            raise ValueError(f"{name} sha256 mismatch: {got} != {expected}")

    troops = load_table("troop.json")
    shine = load_table("shine_troop.json")
    skin_lv = load_table("troop_skin_level.json")
    skin_br = load_table("troop_skin_break.json")
    skin_hb = load_table("troop_skin_honor_break.json")
    jump = load_table("jump.json")
    attributes = load_table("attribute.json")
    categories = load_table("attr_category.json")
    fight = load_table("fight_type.json")
    top_res = load_table("top_resource.json")
    models = load_table("troop_skin.json")
    attr_by = {r["id"]: r for r in attributes}
    troop_by = {r["id"]: r for r in troops}

    if len(troops) != 76:
        raise ValueError(f"troop.json expected 76 rows, got {len(troops)}")
    if len(shine) != 24:
        raise ValueError(f"shine_troop.json expected 24 rows, got {len(shine)}")
    if len(skin_lv) != 4853:
        raise ValueError(f"troop_skin_level.json expected 4853 rows, got {len(skin_lv)}")
    if len(skin_br) != 147:
        raise ValueError(f"troop_skin_break.json expected 147 rows, got {len(skin_br)}")
    if len(skin_hb) != 3150:
        raise ValueError(f"troop_skin_honor_break.json expected 3150 rows, got {len(skin_hb)}")
    if len(models) != 155:
        raise ValueError(f"troop_skin.json expected 155 rows, got {len(models)}")
    if len(fight) != 72:
        raise ValueError(f"fight_type.json expected 72 rows, got {len(fight)}")

    races = {i: official_text(f"unit_race_{i}") for i in range(1, 5)}
    if races != {1: "聯盟", 2: "部族", 3: "自然", 4: "神族"}:
        raise ValueError(f"unexpected race names: {races}")
    if official_text("attribute_name_3") != "攻擊" or official_text("attribute_name_4") != "生命值":
        raise ValueError("attribute_name_3/4 mismatch")

    ids = sorted(troop_by)
    if line_of(1012) != "A" or line_of(1910) != "B" or any(line_of(i) == "?" for i in ids):
        raise ValueError(f"unexpected troop ids: {ids}")
    race_counts = {i: sum(1 for r in troops if r["race"] == i) for i in range(1, 5)}
    if race_counts != {1: 22, 2: 22, 3: 22, 4: 10}:
        raise ValueError(f"race counts {race_counts}")
    if any(r["speed"] != 100 or r["unit_ID"] != 22002 or list(r["army_type"]) != [1, 2, 3] for r in troops):
        raise ValueError("speed / unit_ID / army_type not uniform")
    if {r["quality"] for r in troops} != {2, 3, 4, 5} or {r["level"] for r in troops} != set(range(1, 13)):
        raise ValueError("quality/level set mismatch")

    r1012, r1910 = troop_by[1012], troop_by[1910]
    if (r1012["atk"], r1012["hp"]) != (50, 900) or official_text(r1012["name"]) != "天穹聯盟戰士":
        raise ValueError(f"locked 1012 mismatch: {r1012['atk']}/{r1012['hp']}")
    if (r1910["atk"], r1910["hp"]) != (113, 1500) or official_text(r1910["name"]) != "傳奇聯盟戰士":
        raise ValueError(f"locked 1910 mismatch: {r1910['atk']}/{r1910['hp']}")
    if r1910["name"] != "troop_name_1010" or r1910["desc"] != "troop_desc_1010":
        raise ValueError("1910 name/desc keys should share 1010")

    for race, a0, b0 in ((1, 1001, 1901), (2, 2001, 2901), (3, 3001, 3901)):
        for lv, exp in CHAPTER_A_STATS.items():
            row = troop_by[a0 + lv - 1]
            got = (row["atk"], row["hp"], row["morale"], row["power"], row["load"])
            if got != exp or row["quality"] != QUALITY_BY_LEVEL[lv]:
                raise ValueError(f"A curve mismatch {row['id']}: {got} q={row['quality']}")
            if lv <= 10:
                brow = troop_by[b0 + lv - 1]
                bgot = (brow["atk"], brow["hp"], brow["morale"], brow["power"], brow["load"])
                if bgot != CHAPTER_B_STATS[lv] or brow["name"] != row["name"] or brow["desc"] != row["desc"]:
                    raise ValueError(f"B curve/name mismatch {brow['id']}")
        for lv, exp in CHAPTER_A_COSTS.items():
            if troop_costs(troop_by[a0 + lv - 1]) != exp:
                raise ValueError(f"A cost mismatch {a0 + lv - 1}")
        for lv, exp in CHAPTER_B_COSTS.items():
            if troop_costs(troop_by[b0 + lv - 1])[:6] != exp:
                raise ValueError(f"B cost mismatch {b0 + lv - 1}")
            if troop_by[b0 + lv - 1]["donate_medal"] != -1 or troop_by[b0 + lv - 1]["kill_score_kingdom"] != -1:
                raise ValueError(f"B donate/kill not -1: {b0 + lv - 1}")

    for row in troops:
        lid = line_of(row["id"])
        if lid == "A":
            if not (205 <= row["morale"] <= 800):
                raise ValueError(f"A morale out of range {row['id']}")
            expect_b = {1: 125, 2: 126, 3: 127}[row["race"]]
            if row["correlate_building"] != expect_b:
                raise ValueError(f"A correlate_building {row['id']}")
            if row["season_get"] != f"2|999|20|{row['level']}":
                raise ValueError(f"A season_get {row['id']} {row['season_get']}")
            if row["attr_3"] != [10057, 0]:
                raise ValueError(f"A attr_3 {row['id']}")
            if row["level"] <= 9:
                if row["building_id"] != expect_b * 1000 + (row["level"] - 1) * 5:
                    raise ValueError(f"A building_id {row['id']} {row['building_id']}")
            elif row["building_id"] != -1:
                raise ValueError(f"A 10-12 building_id should be -1: {row['id']}")
        elif lid == "B":
            if row["morale"] != 0 or row["correlate_building"] != -1 or row["season_get"] not in (None, "", -1):
                raise ValueError(f"B structural {row['id']}")
            if row["attr_3"] not in (None,) or row["donate_medal"] != -1:
                raise ValueError(f"B attr_3/donate {row['id']}")

    for lv, prefix in enumerate(PREFIXES, 1):
        name = official_text(troop_by[1000 + lv]["name"])
        if not name.startswith(prefix) or not name.endswith("聯盟戰士"):
            raise ValueError(f"prefix {lv}: {name}")
        tname = official_text(troop_by[2000 + lv]["name"])
        if not tname.endswith("部族戰士") or "部落" in tname:
            raise ValueError(f"tribal name {2000 + lv}: {tname}")

    for lv, exp in CHAPTER_B_STATS.items():
        row = troop_by[4900 + lv]
        if official_text(row["name"]) or official_text(row["desc"]):
            raise ValueError(f"divine unexpectedly named {row['id']}")
        if row["name"] != f"troop_name_{4000 + lv}":
            raise ValueError(f"divine name key {row['id']} {row['name']}")
        got = (row["atk"], row["hp"], row["morale"], row["power"], row["load"])
        if got != exp or row["race"] != 4:
            raise ValueError(f"divine stats {row['id']}")
        scale = 18 if lv <= 6 else 15
        if row["map_soldier_scale"] != scale:
            raise ValueError(f"divine scale {row['id']}")
        ac = troop_costs(troop_by[1000 + lv])
        dc = troop_costs(row)
        if (dc[1], dc[2], dc[4], dc[5]) != (ac[1], ac[2], ac[4], ac[5]):
            raise ValueError(f"divine resource mismatch lv{lv}")
        if lv == 4:
            if dc[3] != 40:
                raise ValueError("divine lv4 treat_time")
        elif dc[3] != ac[3]:
            raise ValueError(f"divine treat_time lv{lv}")
        if lv <= 5:
            if dc[0] != DIVINE_TRAIN_TIME[lv]:
                raise ValueError(f"divine train_time lv{lv}")
        elif dc[0] != ac[0]:
            raise ValueError(f"divine train_time lv{lv} should match A")
    if any(r["map_soldier_scale"] != -1 and r["race"] != 4 for r in troops):
        raise ValueError("non-divine map_soldier_scale")

    for bases, maxlv in (([1001, 2001, 3001], 12), ([1901, 2901, 3901], 10)):
        for lv in range(1, maxlv + 1):
            rows = [troop_by[b + lv - 1] for b in bases]
            for key in ("atk", "hp", "morale", "power", "load", "quality", "train_time", "treat_time", "lvup_time", "donate_medal"):
                vals = [r[key] for r in rows]
                if len(set(vals)) != 1:
                    raise ValueError(f"cross-race {key} lv{lv}: {vals}")

    shine_by = {(r["race"], r["shine_lv"]): r for r in shine}
    if set(r["race"] for r in shine) != {1, 2, 3} or set(r["shine_lv"] for r in shine) != set(range(1, 9)):
        raise ValueError("shine race/level set")
    for lv, exp in CHAPTER_SHINE.items():
        atk, hp, mor, pow_, load, bid_a = exp[3], exp[4], exp[5], exp[6], exp[7], exp[8]
        for race, eid, prefix in ((1, exp[0], 125), (2, exp[1], 126), (3, exp[2], 127)):
            row = shine_by[(race, lv)]
            expect_bid = int(str(bid_a).replace("125", str(prefix), 1))
            if (
                row["id"] != eid
                or (row["atk"], row["hp"], row["morale"], row["power"], row["load"]) != (atk, hp, mor, pow_, load)
                or row["building_id"] != expect_bid
                or row["attr_3"] != [10057, 0]
                or row["correlate_building"] != prefix
            ):
                raise ValueError(f"shine mismatch race{race} lv{lv}")
    s7 = shine_by[(1, 7)]
    if (s7["id"], s7["atk"], s7["hp"], s7["morale"]) != (1490019, 39, 534, 500):
        raise ValueError("locked shine 7 mismatch")

    if has_key("top_resource_name_20"):
        raise ValueError("top_resource_name_20 unexpectedly present")
    if not any(r.get("id") == 20 for r in top_res):
        raise ValueError("resource 20 missing from top_resource.json")
    morale_on = sum(1 for r in fight if r.get("switch_troop_morale") == 1)
    if morale_on != 41:
        raise ValueError(f"switch_troop_morale=1 expected 41, got {morale_on}")

    groups = sorted({r["group"] for r in skin_lv})
    if groups != list(range(5301, 5303)) + list(range(5401, 5408)) + list(range(5501, 5515)):
        raise ValueError(f"unexpected skin groups {groups}")
    levels_by: dict[int, list[dict]] = defaultdict(list)
    for row in skin_lv:
        levels_by[row["group"]].append(row)
    breaks_by: dict[int, list[dict]] = defaultdict(list)
    for row in skin_br:
        breaks_by[row["group"]].append(row)
    honors_by: dict[int, list[dict]] = defaultdict(list)
    for row in skin_hb:
        honors_by[row["group"]].append(row)
    for g, rows in levels_by.items():
        if len(rows) != 211:
            raise ValueError(f"skin level count {g} {len(rows)}")
        rows.sort(key=lambda r: (r["level"], r.get("level_small") if r.get("level_small") not in (None, -1) else -1))
    if set(breaks_by) != set(SKIN_CATALOG) or set(honors_by) != set(SKIN_CATALOG):
        raise ValueError("break/honor groups should be the 21 named sets (not 5401/5402)")
    for g in NAMELESS_SKIN_GROUPS:
        if g in breaks_by or g in honors_by:
            raise ValueError(f"{g} unexpectedly has break/honor")

    jump_by_target = {}
    for row in jump:
        name_key = row.get("name") or ""
        if isinstance(name_key, str) and name_key.startswith("goods_name_20245"):
            jump_by_target[int(row.get("go_target"))] = row
    if set(jump_by_target) != set(JUMP_SKIN_GROUPS):
        raise ValueError(f"jump skin groups {sorted(jump_by_target)}")
    for g, row in jump_by_target.items():
        nid = SKIN_CATALOG[g][0]
        if row["name"] != f"goods_name_{nid}":
            raise ValueError(f"jump name key {g}")

    skins: dict[int, SkinInfo] = {}
    for g in groups:
        rows = levels_by[g]
        quality = rows[0]["quality"]
        if any(r["quality"] != quality for r in rows):
            raise ValueError(f"mixed quality in group {g}")
        if g in NAMELESS_SKIN_GROUPS:
            skins[g] = SkinInfo(g, "", None, None, quality, False, "", "", False, "", False)
            continue
        nid, cid = SKIN_CATALOG[g]
        name = goods_name(nid)
        desc = goods_des(nid)
        if cid != nid and official_text(f"goods_name_{cid}"):
            raise ValueError(f"cost id {cid} unexpectedly has goods_name")
        skins[g] = SkinInfo(
            group=g, name=name, name_id=nid, cost_id=cid, quality=quality, has_break=True,
            clause=load_clause(desc), front=goods_front(nid), jump=g in jump_by_target,
            break_desc=official_text(f"troop_skin_break_desc{g}"),
            display_num=any(r.get("display_num") not in (None, [], "", -1) for r in breaks_by[g]),
        )
        expect_clause = "可同時被多隊裝載" if quality in (3, 4) else "只可同時被一隊裝載"
        if skins[g].clause != expect_clause:
            raise ValueError(f"load clause {g}: {skins[g].clause}")
    if goods_name(GUNNER_GOODS_ID) != "槍兵" or load_clause(goods_des(GUNNER_GOODS_ID)) != "可同時被多隊裝載":
        raise ValueError("槍兵 name/clause")

    def lv_attrs(group: int, level: int):
        row = pick_level_row(levels_by[group], level)
        return [tuple(p) for p in row["attrList"]], row["fightforce"], row["exp"], row.get("unlock_lv"), row.get("prebuilding_level")

    def expect_curve(members, attrs_l1, attrs_l50, p1, p50, e1, e50):
        for g in members:
            a1, f1, x1, u1, pre1 = lv_attrs(g, 1)
            a50, f50, x50, u50, pre50 = lv_attrs(g, 50)
            if a1 != attrs_l1 or a50 != attrs_l50 or (f1, f50, x1, x50) != (p1, p50, e1, e50):
                raise ValueError(f"upgrade curve {g}: L1={a1,f1,x1} L50={a50,f50,x50}")
            if u1 != 0 or pre1 != [142, 1] or u50 != 6 or pre50 != [142, 50]:
                raise ValueError(f"unlock/pre {g}")
        base = members[0]
        payload = [(r["level"], r.get("level_small"), r["attrList"], r["fightforce"], r["exp"]) for r in levels_by[base]]
        for g in members[1:]:
            other = [(r["level"], r.get("level_small"), r["attrList"], r["fightforce"], r["exp"]) for r in levels_by[g]]
            if other != payload:
                raise ValueError(f"curve {g} differs from {base} on some level_small row")

    expect_curve((5301, 5302), [(10103, 15), (10104, 25)], [(10103, 645), (10104, 1149)], 190, 9284, 400, 27750)
    expect_curve(tuple(range(5401, 5408)), [(10103, 25), (10104, 40)], [(10103, 1149), (10104, 1924)], 9835, 28077, 800, 55500)
    expect_curve(tuple(range(5501, 5506)), [(10103, 30), (10104, 45)], [(10103, 1438), (10104, 2146)], 29419, 77486, 1600, 111000)
    expect_curve((5506,), [(15103, 30), (15104, 45)], [(15103, 1438), (15104, 2146)], 29419, 77486, 1600, 111000)
    expect_curve((5507,), [(13103, 30), (13104, 45)], [(13103, 1438), (13104, 2146)], 29419, 77486, 1600, 111000)
    expect_curve((5508,), [(14103, 30), (14104, 45)], [(14103, 1438), (14104, 2146)], 29419, 77486, 1600, 111000)
    expect_curve((5509,), [(13103, 30), (13104, 45), (3029, 50)], [(13103, 1438), (13104, 2146), (3029, 400)], 39350, 168600, 1600, 111000)
    expect_curve((5510,), [(14103, 30), (14104, 45), (4031, 50)], [(14103, 1438), (14104, 2146), (4031, 400)], 39350, 168600, 1600, 111000)
    expect_curve((5511,), [(15103, 30), (15104, 45), (5027, 50)], [(15103, 1438), (15104, 2146), (5027, 400)], 39350, 168600, 1600, 111000)
    expect_curve((5512,), [(13103, 30), (13104, 45), (3019, 50)], [(13103, 1438), (13104, 2146), (3019, 400)], 39350, 168600, 1600, 111000)
    expect_curve((5513,), [(14103, 30), (14104, 45), (4019, 50)], [(14103, 1438), (14104, 2146), (4019, 400)], 39350, 168600, 1600, 111000)
    expect_curve((5514,), [(15103, 30), (15104, 45), (5019, 50)], [(15103, 1438), (15104, 2146), (5019, 400)], 39350, 168600, 1600, 111000)
    r10 = pick_level_row(levels_by[5301], 10)
    if r10.get("unlock_lv") != 1 or r10.get("prebuilding_level") != [142, 10]:
        raise ValueError("lv10 unlock/pre")

    for g, rows in breaks_by.items():
        rows.sort(key=lambda r: r["level"])
        if [r["level"] for r in rows] != list(range(7)):
            raise ValueError(f"break levels {g}")
        expect_mm = [(10, 10), (20, 20), (30, 30), (40, 40), (45, 45), (50, 50), (50, 50)]
        expect_castle = [10, 10, 10, 10, 10, 10, -1]
        expect_qty = [1, 1, 2, 3, 3, 3, None]
        for i, row in enumerate(rows):
            if (row["skin_lv_min"], row["skin_lv_max"]) != expect_mm[i] or row["castle_lv_min"] != expect_castle[i]:
                raise ValueError(f"break skin/castle {g} {i}")
            costs = parse_pipe_cost(row.get("cost"))
            if expect_qty[i] is None:
                if costs:
                    raise ValueError(f"break lv6 cost not empty {g}")
            elif costs[0][1] != skins[g].cost_id or costs[0][2] != expect_qty[i]:
                raise ValueError(f"break cost {g} {i}")

    def blist(g, idx):
        return [tuple(p) for p in breaks_by[g][idx]["attrList"]]

    for i, vals in enumerate([(600, 200, 400), (1200, 400, 800), (1800, 600, 1200), (2400, 800, 1600), (3000, 1000, 2000), (3600, 1200, 2400), (4200, 1400, 2800)]):
        if blist(5301, i) != [(1052, vals[0]), (10103, vals[1]), (10104, vals[2])]:
            raise ValueError(f"5301 break attrs lv{i}")
    if [r["fightforce"] for r in breaks_by[5301]] != [950, 1900, 2850, 4750, 7600, 10450, 13300]:
        raise ValueError("5301 break power")
    if [r.get("display_num") for r in breaks_by[5301]] != [
        ["6", "2", "4"], ["12", "4", "8"], ["18", "6", "12"], ["24", "8", "16"],
        ["30", "10", "20"], ["30", "10", "20"], ["30", "10", "20"],
    ]:
        raise ValueError("5301 display_num")
    for i in range(7):
        atk, hp, mor, rally, extra = 400 * (i + 1), 800 * (i + 1), 50 * (i + 1), 50 * (i + 1), 200 * (i + 1)
        for g, aa, hh, ex in ((5506, 15103, 15104, 21028), (5507, 13103, 13104, 21024), (5508, 14103, 14104, 21026)):
            if blist(g, i) != [(aa, atk), (hh, hp), (10188, mor), (1300106, rally), (ex, extra)]:
                raise ValueError(f"{g} break attrs lv{i}")
        atk2, hp2, anti = 400 * (i + 1), 800 * (i + 1), 100 + 50 * i
        for g, aa, hh, anti_id in ((5509, 13103, 13104, 3029), (5510, 14103, 14104, 4031), (5511, 15103, 15104, 5027)):
            if blist(g, i) != [(aa, atk2), (hh, hp2), (anti_id, anti)]:
                raise ValueError(f"{g} break attrs lv{i}")
        red = 500 + 250 * i
        for g, aa, hh in ((5512, 13103, 13104), (5513, 14103, 14104), (5514, 15103, 15104)):
            if blist(g, i) != [(aa, atk2), (hh, hp2), (1000119, red)]:
                raise ValueError(f"{g} break attrs lv{i}")
    if [r["fightforce"] for r in breaks_by[5507]] != [5000, 10000, 15000, 25000, 40000, 55000, 70000]:
        raise ValueError("5507 break power")
    if [r["fightforce"] for r in breaks_by[5509]] != [24000, 38500, 53000, 67500, 82000, 96500, 111000]:
        raise ValueError("5509 break power")
    locked = blist(5507, 6)
    if locked != [(13103, 2800), (13104, 5600), (10188, 350), (1300106, 350), (21024, 1400)]:
        raise ValueError(f"locked 5507 lv6 {locked}")

    honor_attr1 = {}
    for g in (5301, 5302):
        honor_attr1[g] = (10104, 2, 198, 200, 300, 100, 9900, 10000, 15000)
    for g in range(5403, 5408):
        honor_attr1[g] = (10104, 5, 495, 500, 750, 200, 19800, 20000, 30000)
    for g in range(5501, 5506):
        honor_attr1[g] = (10104, 10, 990, 1000, 1500, 400, 39600, 40000, 60000)
    honor_attr1[5506] = (15104, 10, 990, 1000, 1500, 400, 39600, 40000, 60000)
    honor_attr1[5507] = (13104, 10, 990, 1000, 1500, 400, 39600, 40000, 60000)
    honor_attr1[5508] = (14104, 10, 990, 1000, 1500, 400, 39600, 40000, 60000)
    for g, aid in ((5509, 13104), (5510, 14104), (5511, 15104), (5512, 13104), (5513, 14104), (5514, 15104)):
        honor_attr1[g] = (aid, 10, 990, 1000, 1500, 400, 39600, 53750, 73750)
    honor_iattr = {
        5301: [(1052, 1000), (10103, 0), (10104, 0)],
        5302: [(1076, 1500), (10103, 0), (10104, 0)],
        5403: [(1100003, 1100), (10103, 0), (10104, 0)],
        5404: [(1000105, 1100), (10103, 0), (10104, 0)],
        5405: [(1000104, 2200), (10103, 0), (10104, 0)],
        5406: [(1300105, 150), (10103, 0), (10104, 0), (10104, 600)],
        5407: [(1300106, 80), (10103, 0), (10104, 0), (10188, 80)],
        5501: [(48, 280), (10103, 0), (10104, 0)],
        5502: [(45, 250), (1076, 1400), (10103, 0), (10104, 0)],
        5503: [(1000106, 250), (1129, 1400), (1114, 1000), (10103, 0), (10104, 0)],
        5504: [(1131, 420), (1037, 1), (10103, 0), (10104, 0)],
        5505: [(1300108, 280), (10103, 140), (10103, 0), (10104, 0)],
        5506: [(15103, 0), (15104, 0), (10188, 80), (1300106, 80), (21028, 280)],
        5507: [(13103, 0), (13104, 0), (10188, 80), (1300106, 80), (21024, 280)],
        5508: [(14103, 0), (14104, 0), (10188, 80), (1300106, 80), (21026, 280)],
        5509: [(13103, 0), (13104, 0), (3029, 100)],
        5510: [(14103, 0), (14104, 0), (4031, 100)],
        5511: [(15103, 0), (15104, 0), (5027, 100)],
        5512: [(13103, 0), (13104, 0), (1000119, 500)],
        5513: [(14103, 0), (14104, 0), (1000119, 500)],
        5514: [(15103, 0), (15104, 0), (1000119, 500)],
    }
    honor_attr2 = {
        5509: (3029, 100), 5510: (4031, 100), 5511: (5027, 100),
        5512: (3019, 100), 5513: (4019, 100), 5514: (5019, 100),
    }
    for g, rows in honors_by.items():
        rows.sort(key=lambda r: r["level"])
        if len(rows) != 150 or [r["level"] for r in rows] != list(range(1, 151)):
            raise ValueError(f"honor levels {g}")
        bylv = {r["level"]: r for r in rows}
        aid, v1, v99, v100, v150, p1, p99, p100, p150 = honor_attr1[g]
        for lv, ev, ep in ((1, v1, p1), (99, v99, p99), (100, v100, p100), (150, v150, p150)):
            row = bylv[lv]
            if list(row["attr_1"]) != [aid, ev] or row["fightforce"] != ep:
                raise ValueError(f"honor attr1 {g} lv{lv}: {row['attr_1']} {row['fightforce']}")
        uq = 3 if g in (5301, 5302) else 4 if 5403 <= g <= 5407 else 5
        if any(bylv[lv]["quality"] != uq for lv in range(1, 100)) or any(bylv[lv]["quality"] != uq + 1 for lv in range(100, 151)):
            raise ValueError(f"honor quality {g}")
        if any((bylv[lv].get("i_attrList") or []) for lv in range(1, 100)):
            raise ValueError(f"honor i_attr before 100: {g}")
        ia = [tuple(p) for p in (bylv[100].get("i_attrList") or [])]
        if ia != honor_iattr[g]:
            raise ValueError(f"honor i_attr {g}: {ia}")
        if any([tuple(p) for p in (bylv[lv].get("i_attrList") or [])] != ia for lv in range(100, 151)):
            raise ValueError(f"honor i_attr not constant {g}")
        if g in honor_attr2 and list(bylv[100].get("attr_2") or []) != list(honor_attr2[g]):
            raise ValueError(f"honor attr_2 {g}")
        if parse_pipe_cost(bylv[150].get("cost_1")) or parse_pipe_cost(bylv[150].get("cost_2")) or parse_pipe_cost(bylv[150].get("cost")):
            raise ValueError(f"honor lv150 cost not empty {g}")

    def honor_cost(row):
        c1 = parse_pipe_cost(row.get("cost_1"))
        c2 = parse_pipe_cost(row.get("cost_2"))
        return (c1[0][1], c1[0][2]) if c1 else None, (c2[0][1], c2[0][2]) if c2 else None

    def check_cost_run(g, start, end, medal, piece):
        cid = skins[g].cost_id
        for lv in range(start, end + 1):
            row = next(r for r in honors_by[g] if r["level"] == lv)
            c1, c2 = honor_cost(row)
            if c1 != (17, medal) or c2 != (cid, piece):
                raise ValueError(f"honor cost {g} lv{lv}: {c1} {c2}")

    check_cost_run(5301, 1, 149, 12500, 25)
    check_cost_run(5302, 1, 149, 12500, 25)
    check_cost_run(5403, 1, 149, 25000, 5)
    check_cost_run(5407, 1, 1, 25000, 5)
    check_cost_run(5407, 2, 49, 12500, 5)
    check_cost_run(5407, 50, 149, 25000, 5)
    check_cost_run(5501, 1, 99, 50000, 1)
    check_cost_run(5501, 100, 149, 50000, 2)
    check_cost_run(5507, 1, 99, 50000, 1)
    check_cost_run(5507, 100, 149, 50000, 2)

    if official_text("attribute_name_10188"):
        raise ValueError("attribute_name_10188 unexpectedly present")
    if attr_label(10188, attr_by) != "士兵士氣":
        raise ValueError("10188 table name")
    meta_10188 = attr_meta(10188, attr_by)
    if meta_10188.get("type") != 2 or meta_10188.get("show_type") != 2:
        raise ValueError("10188 type/show")
    if official_text("attribute_name_1129") or table_name_label(1129, attr_by):
        raise ValueError("1129 unexpectedly named")
    if attr_meta(1300106, attr_by).get("max") != 5000 or attr_meta(1300106, attr_by).get("is_max_show") != 1:
        raise ValueError("1300106 max")
    if attr_meta(1300105, attr_by).get("max") != 20000:
        raise ValueError("1300105 max")
    if attr_meta(1300108, attr_by).get("attribute_Id") != 1137:
        raise ValueError("1300108 attribute_Id")

    cat = {r["id"]: r for r in categories}
    official = Official(
        races=races,
        formulas={
            "atk": official_text("hero_detailed_stats_ui_formula_4"),
            "hp": official_text("hero_detailed_stats_ui_formula_8"),
        },
        buildings={
            bid: (official_text(f"citybuilding_name_{bid}"), official_text(f"citybuilding_des_{bid}"))
            for bid in (125, 126, 127, 142, 169, 121)
        },
        resources={n: official_text(f"top_resource_name_{n}") for n in (4, 5, 17)},
        categories={
            cid: (official_text(cat[cid]["name_key"]), official_text(cat[cid]["tips_key"]))
            for cid in (32, 33, 34, 50)
        },
        skin_system=official_text("troop_skin"),
        skin_training=[ln for ln in official_text("info_title_army_troop_skin_content1").split("\n") if ln],
        shine_tip=official_text("UI_army_shine_attr_tip"),
        team_tips=official_text("UI_hero_team_tips"),
        honor_forbid=official_text("troop_skin_break_honor_level_forbid"),
        honor_unlock=official_text("troop_skin_break_unlock_skill"),
        honor_item_name=goods_name(HONOR_GOODS_ID),
        honor_item_desc=official_text("goods_desc_1017"),
        gunner_name=goods_name(GUNNER_GOODS_ID),
        gunner_front=goods_front(GUNNER_GOODS_ID),
        gunner_clause=load_clause(goods_des(GUNNER_GOODS_ID)),
        leftover_name=official_text("troop_skin_name501"),
        leftover_desc=official_text("troop_skin_break_desc501"),
        duel=official_text("champion_duel_info_desc_1_3"),
        march_name=official_text(cat[50]["name_key"]),
        march_desc=official_text(cat[50]["tips_key"]),
        shield_name=official_text("citybuilding_name_121"),
        shield_desc=official_text("citybuilding_des_121"),
        tribe_word=official_text("UI_hero_team_troop_2"),
    )
    if official.resources != {4: "木材", 5: "石頭", 17: "勳章"}:
        raise ValueError(f"resource names {official.resources}")
    if official.categories[32][0] != "光輝建築" or official.categories[33][0] != "兵裝突破" or official.categories[34][0] != "兵裝升級":
        raise ValueError(f"category names {official.categories}")
    if official.march_name != "行軍造型" or official.skin_system != "兵裝":
        raise ValueError("march/skin system name")
    if official.buildings[125][0] != "聯盟兵營" or official.buildings[126][0] != "部族兵營":
        raise ValueError(official.buildings)
    if official.tribe_word != "部落士兵" or official.leftover_name != "羅馬時代":
        raise ValueError("tribe/leftover strings")
    if not official.formulas["atk"].startswith("士兵攻擊="):
        raise ValueError(official.formulas["atk"])

    data = TablesData(
        official=official, attr_by=attr_by, troops=troop_by, shine=shine, skins=skins,
        skin_levels=dict(levels_by), skin_breaks=dict(breaks_by), skin_honors=dict(honors_by),
        verifications={
            "troop_rows": 76, "shine_rows": 24, "skin_level_rows": 4853,
            "skin_break_rows": 147, "skin_honor_rows": 3150,
            "locked_1012": (50, 900), "locked_1910": (113, 1500),
            "locked_shine_7": (39, 534, 500), "locked_5507_lv6": locked,
            "morale_switch_on": morale_on, "data_cutoff": TROOP_DATA_CUTOFF,
        },
    )
    data.terms = _terms(data)
    return data


def _terms(data: TablesData) -> list[str]:
    o = data.official
    terms: set[str] = {
        o.skin_system, o.shine_tip, o.team_tips, o.honor_forbid, o.honor_unlock,
        o.honor_item_name, o.gunner_name, o.leftover_name, o.march_name, o.march_desc,
        o.shield_name, o.tribe_word, o.formulas["atk"], o.formulas["hp"],
        "裝備總表", "領主裝備總表", "專武總表", "造型總表",
        "英雄裝備", "領主裝備", "專武", "英雄造型",
        "光輝建築", "兵裝突破", "兵裝升級", "兵裝研究所", "光輝研究所",
        "行軍造型", "士兵圖鑑", "士兵總表",
        "藍色、紫色兵裝", "可同時被多隊裝載", "只可同時被一隊裝載",
        "單個士兵攻擊基礎值", "單個士兵生命基礎值",
        "士兵攻擊百分比", "士兵生命百分比",
        "士兵攻擊額外值", "士兵生命額外值", "士兵數量",
        "所有士兵攻擊", "所有士兵生命",
        "聯盟士兵攻擊", "聯盟士兵生命", "部族士兵攻擊", "部族士兵生命",
        "自然士兵攻擊", "自然士兵生命",
        "聯盟士兵", "部族士兵", "自然士兵", "部落士兵",
        "天穹聯盟戰士", "天御聯盟戰士", "傳奇聯盟戰士",
        "初級聯盟戰士", "聯盟兵營", "部族兵營", "自然兵營",
        "士兵士氣", "集結士氣", "守城時減傷", "逆克制增傷",
        "隊伍英雄為同一陣營時，聯盟士兵生命額外提升",
        "隊伍英雄為同一陣營時，部族士兵生命額外提升",
        "隊伍英雄為同一陣營時，自然士兵生命額外提升",
        "所有士兵的城防傷害", "兵裝榮譽勛章",
    }
    for name in o.races.values():
        terms.add(name)
    for name, desc in o.buildings.values():
        terms.add(name)
        terms.add(desc)
    for name in o.resources.values():
        terms.add(name)
    for name, tip in o.categories.values():
        terms.add(name)
        terms.add(tip)
    for line in o.skin_training:
        terms.add(line)
        terms.add(re.sub(r"^\d+\.", "", line).strip())
    for row in data.troops.values():
        terms.add(official_text(row["name"]))
        terms.add(official_text(row["desc"]))
    for skin in data.skins.values():
        terms.add(skin.name)
        terms.add(skin.front)
        terms.add(skin.break_desc)
        terms.add(skin.clause)
    terms.add(o.gunner_front)
    terms.add(o.gunner_clause)
    terms.add(o.honor_item_desc)
    terms.add(o.leftover_desc)
    terms.add(o.duel)
    terms.add(o.shield_desc)
    terms.update(PREFIXES)
    terms.add("最高等級")
    for key in ("morale_002", "morale_003", "morale_004", "morale_005", "morale_006"):
        terms.add(official_text(key))
    for aid in (
        3, 4, 45, 48, 88, 1037, 1052, 1076, 1114, 1130, 1131, 1136, 1137,
        1018, 1019, 10003, 10004, 10057, 10088, 10103, 10104, 10105, 10106, 10188,
        13103, 13104, 14103, 14104, 15103, 15104,
        21024, 21026, 21028, 3029, 4031, 5027, 3019, 4019, 5019,
        1000104, 1000105, 1000106, 1000119, 1100003, 1300105, 1300106, 1300108, 16000, 16001,
    ):
        terms.add(attr_label(aid, data.attr_by))
        terms.add(table_name_label(aid, data.attr_by))
    return sorted({x for x in terms if x}, key=len, reverse=True)


def _alabel(data: TablesData, attr_id: int, terms: list[str] | None = None) -> str:
    name = attr_label(attr_id, data.attr_by)
    text = f"{name}（{attr_id}）" if name else str(attr_id)
    return H(text, terms) if terms is not None else text


def _build_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    prefix_tbl = table(
        ["level", "quality", "名稱前綴（後接「〔陣營〕戰士」）", "線 A id", "線 B id"],
        [[H(c, terms) if j == 2 else c for j, c in enumerate(row)] for row in _prefix_rows()],
        mobile="cards",
        card_title="名稱前綴（後接「〔陣營〕戰士」）",
    )
    diff_tbl = table(
        ["項目", "線 A（1001–1012 等）", "線 B（1901–1910 等，含神族）"],
        [
            [H("最高等級", terms), "12（天穹）", "10（傳奇）"],
            ["士氣 morale", "205–800", "全為 0"],
            ["correlate_building", "125／126／127（" + H("聯盟兵營", terms) + "／" + H("部族兵營", terms) + "／" + H("自然兵營", terms) + "）", "−1"],
            ["season_get", e("2|999|20|{level}"), "無（None）"],
            ["attr_3", e("[10057, 0]") + "（" + _alabel(data, 10057, terms) + "，值為 0）", "無"],
            ["捐贈勳章、王國擊殺積分", "有正值", "donate_medal、擊殺積分皆為 −1"],
            ["同階戰力 power、負重 load、移動 speed", "與線 B 相同", "與線 A 相同"],
            ["中高階攻擊／生命", "較低（傳奇 40／770，天穹 50／900）", "較高（傳奇 113／1500）"],
        ],
        mobile="cards",
        card_title="項目",
    )
    stat_cols = ["等級", "名稱", "id", "品質", "攻擊", "生命", "士氣", "戰力", "負重"]

    def stat_rows(base: int, last: int) -> list[list[str]]:
        out = []
        for lv in range(1, last + 1):
            row = data.troops[base + lv - 1]
            out.append([
                str(lv), H(official_text(row["name"]), terms), str(row["id"]), str(row["quality"]),
                str(row["atk"]), str(row["hp"]), str(row["morale"]), str(row["power"]), str(row["load"]),
            ])
        return out

    a_stat_tbl = table(stat_cols, stat_rows(1001, 12), mobile="sticky", card_title="名稱")
    b_stat_tbl = table(stat_cols, stat_rows(1901, 10), mobile="sticky", card_title="名稱")
    a_cost_tbl = table(
        ["等級", "訓練時間", "木材", "石頭", "治療時間", "治療木材", "治療石頭", "lvup_time", "捐贈勳章"],
        [[str(lv)] + [str(x) for x in troop_costs(data.troops[1000 + lv])] for lv in range(1, 13)],
        mobile="sticky", card_title="等級",
    )
    b_cost_tbl = table(
        ["等級", "訓練時間", "木材", "石頭", "治療時間", "治療木材", "治療石頭"],
        [[str(lv)] + [str(x) for x in troop_costs(data.troops[1900 + lv])[:6]] for lv in range(1, 11)],
        mobile="sticky", card_title="等級",
    )
    shine_by = {(r["race"], r["shine_lv"]): r for r in data.shine}
    shine_rows = []
    for lv in range(1, 9):
        a, b, c = shine_by[(1, lv)], shine_by[(2, lv)], shine_by[(3, lv)]
        shine_rows.append([
            str(lv), str(a["id"]), str(b["id"]), str(c["id"]),
            str(a["atk"]), str(a["hp"]), str(a["morale"]), str(a["power"]), str(a["load"]), str(a["building_id"]),
        ])
    shine_tbl = table(
        ["shine_lv", "聯盟 id", "部族 id", "自然 id", "攻擊", "生命", "士氣", "戰力", "負重", "聯盟 building_id"],
        shine_rows, mobile="sticky", card_title="shine_lv",
    )
    catalog_rows = []
    for g in list(range(5301, 5303)) + list(range(5401, 5408)) + list(range(5501, 5515)):
        s = data.skins[g]
        if g in NAMELESS_SKIN_GROUPS:
            catalog_rows.append([str(g), "（無名稱字串）", "—", "—", str(s.quality), "無", "—"])
        else:
            cost = "同左" if s.cost_id == s.name_id else str(s.cost_id)
            catalog_rows.append([str(g), H(s.name, terms), str(s.name_id), cost, str(s.quality), "有", H(s.clause, terms)])
    catalog_tbl = table(
        ["group", "名稱", "名稱道具 id", "消耗道具 id（若不同）", "升級表品質", "有突破／榮譽", "道具說明（裝載句）"],
        catalog_rows, mobile="cards", card_title="名稱",
    )

    def up_row(label: str, group: int) -> list[str]:
        r1 = pick_level_row(data.skin_levels[group], 1)
        r50 = pick_level_row(data.skin_levels[group], 50)
        attrs = "、".join(
            f"{attr_label(a, data.attr_by)} {a}" if attr_label(a, data.attr_by) else str(a)
            for a, _v in r1["attrList"]
        )
        return [
            H(label, terms), H(attrs, terms),
            join_slash(v for _a, v in r1["attrList"]), join_slash(v for _a, v in r50["attrList"]),
            str(r1["fightforce"]), str(r50["fightforce"]), str(r1["exp"]), str(r50["exp"]),
        ]

    upgrade_tbl = table(
        ["組別", "升級屬性（id）", "1 級原值", "50 級原值", "1 級戰力", "50 級戰力", "1 級 exp", "50 級 exp"],
        [
            up_row("5301、5302", 5301), up_row("5401–5407", 5403), up_row("5501–5505", 5501),
            up_row("5506 " + data.skins[5506].name, 5506),
            up_row("5507 " + data.skins[5507].name, 5507),
            up_row("5508 " + data.skins[5508].name, 5508),
            up_row("5509 " + data.skins[5509].name, 5509),
            up_row("5510 " + data.skins[5510].name, 5510),
            up_row("5511 " + data.skins[5511].name, 5511),
            up_row("5512 " + data.skins[5512].name, 5512),
            up_row("5513 " + data.skins[5513].name, 5513),
            up_row("5514 " + data.skins[5514].name, 5514),
        ],
        mobile="cards", card_title="組別",
    )
    br5301_rows = []
    for i, row in enumerate(data.skin_breaks[5301]):
        amap = {a: v for a, v in row["attrList"]}
        br5301_rows.append([
            str(i), str(amap[1052]), str(amap[10103]), str(amap[10104]),
            display_num_cell(row.get("display_num")), break_cost_cell(row, show_id=(i == 0)),
        ])
    br5301_tbl = table(["階", "1052", "10103", "10104", "display_num", "消耗"], br5301_rows, mobile="sticky", card_title="階")

    def faction_rows(group: int, extra: str) -> list[list[str]]:
        out = []
        for i, row in enumerate(data.skin_breaks[group]):
            pairs = row["attrList"]
            costs = parse_pipe_cost(row.get("cost"))
            cells = [str(i), str(pairs[0][1]), str(pairs[1][1])]
            if extra == "morale":
                cells.extend([str(pairs[2][1]), str(pairs[3][1]), str(pairs[4][1])])
            else:
                cells.append(str(pairs[2][1]))
            cells.append(str(costs[0][2]) if costs else "（空）")
            out.append(cells)
        return out

    br5507_tbl = table(
        ["階", "分營攻擊", "分營生命", "10188", "1300106", "同營生命額外", "消耗個數"],
        faction_rows(5507, "morale"), mobile="sticky", card_title="階",
    )
    br5509_tbl = table(
        ["階", "分營攻擊", "分營生命", "逆克制增傷", "消耗個數"],
        faction_rows(5509, "anti"), mobile="sticky", card_title="階",
    )
    br5512_tbl = table(
        ["階", "分營攻擊", "分營生命", "1000119", "消耗個數"],
        faction_rows(5512, "red"), mobile="sticky", card_title="階",
    )
    honor_attr_tbl = table(
        ["組", "品質段", "等級", "attr_1", "戰力"],
        [
            [H("5301、5302", terms), "3→4", "1–99／100–150", H("10104：2→198／200→300", terms), "100→9900／10000→15000"],
            [H("5403–5407", terms), "4→5", "1–99／100–150", H("10104：5→495／500→750", terms), "200→19800／20000→30000"],
            [H("5501–5505", terms), "5→6", "1–99／100–150", H("10104：10→990／1000→1500", terms), "400→39600／40000→60000"],
            [H("5506", terms), "5→6", "同上", H("15104：10→990／1000→1500", terms), "同上"],
            [H("5507", terms), "5→6", "同上", H("13104：10→990／1000→1500", terms), "同上"],
            [H("5508", terms), "5→6", "同上", H("14104：10→990／1000→1500", terms), "同上"],
            [H("5509", terms), "5→6", "同上", H("13104：10→990／1000→1500", terms), "400→39600／53750→73750"],
            [H("5510", terms), "5→6", "同上", H("14104：10→990／1000→1500", terms), "同 5509"],
            [H("5511", terms), "5→6", "同上", H("15104：10→990／1000→1500", terms), "同 5509"],
            [H("5512", terms), "5→6", "同上", H("13104：10→990／1000→1500", terms), "同 5509"],
            [H("5513", terms), "5→6", "同上", H("14104：10→990／1000→1500", terms), "同 5509"],
            [H("5514", terms), "5→6", "同上", H("15104：10→990／1000→1500", terms), "同 5509"],
        ],
        mobile="cards", card_title="組",
    )

    def iattr_text(g: int) -> str:
        row = next(r for r in data.skin_honors[g] if r["level"] == 100)
        parts = [f"{a}＝{v}" for a, v in (row.get("i_attrList") or [])]
        a2 = row.get("attr_2")
        extra = f"（另 attr_2 {a2[0]}＝{a2[1]}）" if a2 else ""
        return "，".join(parts) + extra

    honor_i_tbl = table(
        ["組", "升檔後 i_attr（原值）"],
        [[H(f"{g} {data.skins[g].name}", terms), H(iattr_text(g), terms)] for g in SKIN_CATALOG],
        mobile="cards", card_title="組",
    )
    return {
        "prefix": prefix_tbl, "diff": diff_tbl, "a_stat": a_stat_tbl, "b_stat": b_stat_tbl,
        "a_cost": a_cost_tbl, "b_cost": b_cost_tbl, "shine": shine_tbl, "catalog": catalog_tbl,
        "upgrade": upgrade_tbl, "br5301": br5301_tbl, "br5507": br5507_tbl,
        "br5509": br5509_tbl, "br5512": br5512_tbl, "honor_attr": honor_attr_tbl, "honor_i": honor_i_tbl,
    }


def _fronts_html(data: TablesData, terms: list[str]) -> str:
    o = data.official
    bits = []
    for item in (5301, 5302, GUNNER_GOODS_ID, 5403, 5404, 5501, 5502, 5405, 5503, 5504, 5505, 5406, 5407, 5506, 5507, 5508, 5509, 5510, 5511, 5512, 5513, 5514):
        if item == GUNNER_GOODS_ID:
            name, front = o.gunner_name, o.gunner_front
        else:
            name, front = data.skins[item].name, data.skins[item].front
        bits.append(H(name, terms) + "「" + H(front, terms) + "」")
    return "；".join(bits)


def _break_prose_html(data: TablesData, terms: list[str]) -> str:
    def desc(g: int) -> str:
        return H(data.skins[g].break_desc, terms)

    def lab(aid: int) -> str:
        name = attr_label(aid, data.attr_by)
        return H(name, terms) if name else str(aid)

    def powers(g: int) -> str:
        return _slash_powers(data.skin_breaks[g])

    parts = [
        p_html(
            f"<strong>{H('騎兵', terms)} 5302。</strong>說明：{desc(5302)}。"
            f"屬性 1076 {lab(1076)}、10103、10104。戰力與消耗個數與盾兵相同（消耗 id 2024502）。"
            f"<code>display_num</code>：10／2／4、20／4／8、30／6／12、40／8／16、50／10／20，第 5、6 階仍為 50／10／20；"
            f"對應原值 1000／200／400 起，每階加 1000／200／400，第 6 階為 7000／1400／2800。"
        ),
        p_html(
            f"<strong>{H('熊皮勇士', terms)} 5403。</strong>說明：{desc(5403)}。"
            f"屬性 1100003 {lab(1100003)}、10103、10104。戰力 {powers(5403)}。"
            f"原值第 0 階 700／300／600，每階加 700／300／600，第 6 階 4900／2100／4200。"
            f"<code>display_num</code> 第 0–5 階為 7／3／6 起依此遞增至 42／18／36，第 6 階仍為 42／18／36。"
            f"消耗 id 2024543，個數 1／1／2／3／3／3／空。"
        ),
        p_html(
            f"<strong>{H('武士', terms)} 5404。</strong>說明：{desc(5404)}。"
            f"屬性 1000105 {lab(1000105)}、10103、10104。原值、<code>display_num</code>、戰力、消耗個數與熊皮勇士相同（消耗 id 2024544）。"
        ),
        p_html(
            f"<strong>{H('優雅侍者', terms)} 5405。</strong>說明：{desc(5405)}。"
            f"屬性 1000104（<code>attribute_name_1000104</code> 為「{lab(1000104)}」）、10103、10104。"
            f"第 0 階原值 800／300／600，每階加 800／300／600，第 6 階 5600／2100／4200。"
            f"<code>display_num</code> 第 0–5 階為 8／3／6 至 48／18／36，第 6 階為 42／18／36。"
            f"戰力、消耗個數同上（消耗 id 2024545）。"
        ),
        p_html(
            f"<strong>{H('後勤隨從', terms)} 5406。</strong>說明：{desc(5406)}。"
            f"屬性 1300105 {lab(1300105)}（<code>max=20000</code>、<code>is_max_show=1</code>）、10103、10104，以及再一筆 10104。"
            f"第 0 階原值 100／300／600／400，每階加 100／300／600／400，第 6 階 700／2100／4200／2800。"
            f"<code>display_num</code> 第 0–5 階為 1／3／6／4 至 6／18／36／24，第 6 階仍為 6／18／36／24。"
            f"戰力、消耗個數同上（消耗 id 2024546）。1300105 的上限如何顯示，除 <code>max</code>／<code>is_max_show</code> 兩欄外，本頁不自行換算。"
        ),
        p_html(
            f"<strong>{H('鼓號隊', terms)} 5407。</strong>說明：{desc(5407)}。"
            f"屬性 1300106 {lab(1300106)}、10103、10104、10188 {lab(10188)}。"
            f"第 0 階原值 50／300／600／50，每階加 50／300／600／50，第 6 階 350／2100／4200／350。"
            f"<code>display_num</code> 第 0–5 階為 0.5／3／6／0.5 至 3／18／36／3，第 6 階仍為 3／18／36／3。"
            f"戰力、消耗個數同上（消耗 id 2024547）。集結士氣 1300106 的 <code>max=5000</code> 且 <code>is_max_show=1</code>，與畫面括號「最大 50%」的對照見後文已鎖定項。"
        ),
        p_html(
            f"<strong>{H('榮耀近衛', terms)} 5501。</strong>說明：{desc(5501)}。"
            f"屬性 48 {lab(48)}、10103、10104。戰力 {powers(5501)}。"
            f"第 0 階原值 200／400／800，每階加 200／400／800，第 6 階 1400／2800／5600。"
            f"<code>display_num</code> 第 0–5 階為 2／4／8 至 12／24／48，第 6 階仍為 12／24／48。"
            f"消耗 id 2024551，個數 1／1／2／3／3／3／空。這裡的「守城時減傷」對到屬性 48；5512–5514 說明裡同樣寫「守城時減傷」，對到的是 1000119，不是同一條。"
        ),
        p_html(
            f"<strong>{H('重騎兵', terms)} 5502。</strong>說明：{desc(5502)}。"
            f"屬性 45 {lab(45)}、1076、10103、10104。第 0 階原值 160／1000／400／800，第 6 階 1120／7000／2800／5600。"
            f"<code>display_num</code> 第 0–5 階為 1.6／10／4／8 至 9.6／60／24／48，第 6 階仍為 9.6／60／24／48。"
            f"戰力、消耗個數與榮耀近衛相同（消耗 id 2024552）。"
        ),
        p_html(
            f"<strong>{H('攻城車', terms)} 5503。</strong>說明：{desc(5503)}。"
            f"屬性 1000106 {lab(1000106)}、1129、1114 {lab(1114)}、10103、10104。"
            f"1129 的名稱鍵 <code>attribute_name_1129</code> 在字串表中不存在，本頁不編造名稱；它是 <code>type=1</code>、<code>show_type=1</code>。"
            f"第 0 階原值 160／1000／1000／400／800，第 6 階 1120／7000／7000／2800／5600。"
            f"<code>display_num</code> 第 0 階為 1.6／1000／10／4／8；第 5 階為 9.6／6000／60／24／48，第 6 階仍為 9.6／6000／60／24／48"
            f"（1129 的顯示字是「1000」「2000」這種原值，不是改寫成 10、20）。戰力、消耗個數同上（消耗 id 2024553）。"
        ),
        p_html(
            f"<strong>{H('無畏戰士', terms)} 5504。</strong>說明：{desc(5504)}。"
            f"屬性 1131 {lab(1131)}、1037 {lab(1037)}（<code>type=1</code>、<code>show_type=1</code>）、10103、10104。"
            f"第 0 階原值 300／1／400／800，第 6 階 2100／7／2800／5600。"
            f"<code>display_num</code> 第 0–5 階為 3／1／4／8 至 18／6／24／48，第 6 階仍為 18／6／24／48。"
            f"戰力、消耗個數同上（消耗 id 2024554）。"
        ),
        p_html(
            f"<strong>{H('骸靈士兵', terms)} 5505。</strong>說明：{desc(5505)}。"
            f"屬性 1300108 {lab(1300108)}（<code>max=10000</code>、<code>is_max_show=1</code>，<code>attribute_Id=1137</code>）、兩筆 10103、以及 10104。"
            f"第 0 階原值 200／100／400／800，第 6 階 1400／700／2800／5600。"
            f"<code>display_num</code> 第 0–5 階為 2／1／4／8 至 12／6／24／48，第 6 階仍為 12／6／24／48。"
            f"戰力、消耗個數同上（消耗 id 2024555）。"
        ),
    ]
    return "\n      ".join(parts)


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_tables(data, terms)
    title = "Top Heroes Wiki｜士兵總表"
    summary = "士兵兩條 id 線、單兵數值、訓練與治療消耗、光輝建築，以及兵裝名錄與已鎖定的聯盟兵裝面板對照。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "lines", "label": "士兵兩條線"},
        {"id": "diff", "label": "兩條線的差別", "depth": 1},
        {"id": "stats", "label": "單兵數值", "depth": 1},
        {"id": "costs", "label": "訓練與治療消耗", "depth": 1},
        {"id": "fight", "label": "戰鬥類型開關", "depth": 1},
        {"id": "divine", "label": "神族（只在 B 線）", "depth": 1},
        {"id": "formulas", "label": "官方公式與面板、戰報核對"},
        {"id": "shine", "label": "光輝建築"},
        {"id": "skins", "label": "兵裝"},
        {"id": "catalog", "label": "名錄", "depth": 1},
        {"id": "upgrade", "label": "升級", "depth": 1},
        {"id": "break", "label": "突破", "depth": 1},
        {"id": "honor", "label": "榮譽突破", "depth": 1},
        {"id": "locked", "label": "已鎖定的聯盟兵裝面板對照", "depth": 1},
        {"id": "march", "label": "行軍造型", "depth": 1},
        {"id": "morale", "label": "士氣"},
        {"id": "models", "label": "部隊外觀編號"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{LEDE}</p>')
    add(f"    {toc}")
    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(
        "<p>正文只根據遊戲資料表與官方字串，不評定兵種或兵裝強弱，也不另外發明名稱。"
        "社群說法若出現會標成社群備註；本頁沒有這類條目。英雄裝備見"
        f'<a href="equipment.html">{H("裝備總表", terms)}</a>，領主裝備見'
        f'<a href="lord-equipment.html">{H("領主裝備總表", terms)}</a>。已發佈的'
        f'<a href="exclusive.html">{H("專武總表", terms)}</a>與'
        f'<a href="skins.html">{H("造型總表", terms)}</a>是英雄專武與英雄造型，不是本頁的士兵或兵裝。</p>'
    )
    add("<ul>")
    add(
        "<li><strong>士兵有兩套資料，不要混用。</strong>"
        f"一套是兵營那套，有 11、12 級（{H('天御', terms)}、{H('天穹', terms)}）。"
        f"另一套只到 10 級{H('傳奇', terms)}，{H('神族', terms)}只在這套。"
        f"同一中文名會出現在兩套（例如「{H('傳奇聯盟戰士', terms)}」），戰力相同，攻擊／生命曲線不同。編號對照見資料說明。</li>"
    )
    add(
        "<li><strong>面板士兵階 XII／XI，以及戰報裡的單兵攻擊／生命基礎值，用的是兵營那套，不是另一套。</strong>已鎖定："
        f'{H("天穹聯盟戰士", terms)} 攻擊 50、生命 900；另一套的{H("傳奇聯盟戰士", terms)} 攻擊 113、生命 1500。'
        "不要把攜帶相關欄位強行對成另一套或「虛擬兵」。</li>"
    )
    add(
        "<li><strong>官方屬性公式</strong>照錄為："
        f"{H(o.formulas['atk'], terms)}；生命同構：{H(o.formulas['hp'], terms)}。"
        f"戰鬥公式裡的「{H('士兵數量', terms)}」因戰報 15.4M／600M 等顯示進位，推不出唯一整數，維持未驗證。</li>"
    )
    add("<li>屬性只錄表上的原值，不自行換成百分比。若官方文案或已鎖定面板有對應，該條照記，仍不推廣到其他屬性。</li>")
    add("<li>不要從時間或賽季欄位自動標未開放。相關欄位只照錄。</li>")
    add("<li>不要編造士氣「x 倍士氣造成 y 倍傷害」的數列。也不要把關卡技能當成通用 PvP 士氣表。</li>")
    add(
        f"<li>{H('行軍造型', terms)}不在本篇展開。屬性來源分類的官方名稱是「{H(o.march_name, terms)}」。"
        f"不要把聯盟士兵生命面板曾另標的 20% 強行對成{H(o.shield_name, terms)}或裝飾物的一筆效果。</li>"
    )
    add(
                f"<li>品質欄只錄表上的數字（2–5）。養成說明若有「{H('藍色、紫色兵裝', terms)}」與「其他兵裝」的裝載規則，那是官方文案，不是替品質 3／4／5 改名。</li>"
    )
    add(
        f"<li>官方用語是「{H('部族', terms)}」不是「部落」。種族名稱取 <code>unit_race_1</code>–<code>4</code>：1＝{H('聯盟', terms)}、2＝{H('部族', terms)}、3＝{H('自然', terms)}、4＝{H('神族', terms)}。"
        f"影響力目錄把三營士兵寫成「{H('聯盟士兵', terms)}／{H(o.tribe_word, terms)}／{H('自然士兵', terms)}」（此處原文是「部落」不是「部族」），照錄並標明。</li>"
    )
    add("</ul>")
    add("    </section>")
    add('    <section id="lines">')
    add("      <h2>士兵兩條線</h2>")
    add(
        "<p>主表 <code>troop.json</code> 76 筆。<code>race</code>：1＝"
        f"{H('聯盟', terms)}（22 筆）、2＝{H('部族', terms)}（22）、3＝{H('自然', terms)}（22）、4＝{H('神族', terms)}"
        "（10，只在 B 線）。<code>quality</code> 為 2–5，<code>level</code> 為 1–12。<code>army_type</code> 皆為 <code>[1, 2, 3]</code>，本頁未對到這三個數字的含義。"
        "<code>speed</code> 全表都是 100。<code>unit_ID</code> 全表都是 22002。<code>atk</code>／<code>hp</code> 就是屬性 3／4（"
        f"{_alabel(data, 3, terms)}／{_alabel(data, 4, terms)}）。</p>"
    )
    add(
        "<p>有中文名的士兵全部是「戰士」一系。線 B 的名稱、說明鍵與線 A 相同（例如 1910 的 <code>name</code> 也是 <code>troop_name_1010</code>）。"
        f"三營名稱結構相同，只改「{H('聯盟', terms)}／{H('部族', terms)}／{H('自然', terms)}」：</p>"
    )
    add(tbl["prefix"])
    add(
        f"<p>官方說明句式相同，例如「{H(official_text('troop_desc_1012'), terms)}」（<code>troop_desc_1012</code>）。"
        f"{H(o.team_tips, terms)}（<code>UI_hero_team_tips</code>）。</p>"
    )
    add('      <h3 id="diff">兩條線的差別</h3>')
    add(tbl["diff"])
    add(
        "<p>兵營建築名稱：<code>citybuilding_name_125</code>／<code>126</code>／<code>127</code> 為"
        f"{H(o.buildings[125][0], terms)}、{H(o.buildings[126][0], terms)}、{H(o.buildings[127][0], terms)}。"
        f"說明分別是「{H(o.buildings[125][1], terms)}」「{H(o.buildings[126][1], terms)}」「{H(o.buildings[127][1], terms)}」。"
        "兵營升級表到 80 級。線 A 的 1–9 級對到兵營 <code>building_id</code> 125000／125005／…／125040（即建築 0、5、10、…、40 級；部族、自然同規律，建築編號改 126、127）。"
        "10–12 級（傳奇、天御、天穹）的 <code>building_id</code> 為 −1，仍寫 <code>correlate_building</code> 為對應兵營。"
        "表沒有另寫這三級的解鎖條件；本頁不把科技「士兵等級＋1」或其他欄位寫成解鎖式。</p>"
    )
    add("<p><code>season_get</code> 的寫法是 <code>2|999|20|{level}</code>。資源 20 在 <code>top_resource.json</code> 有列，但 <code>strings_zh</code> 沒有 <code>top_resource_name_20</code>，本頁不編造資源名，也不把這一欄解釋成開放條件。</p>")
    add('      <h3 id="stats">單兵數值</h3>')
    add("<p>同階、同線的攻擊、生命、士氣、戰力、負重，三個有中文名的陣營完全相同；B 線神族的攻擊、生命、戰力、負重也與同階 B 線一致。因此下面只各列一張表。</p>")
    add("<p>線 A（以聯盟為例；部族 20xx、自然 30xx 同值）：</p>")
    add(tbl["a_stat"])
    add("<p>線 B（以聯盟為例；部族 29xx、自然 39xx、神族 49xx 的攻擊／生命／戰力／負重同值。神族名稱見下節）：</p>")
    add(tbl["b_stat"])
    add("<p>1 級時兩條線攻擊同為 3，線 B 生命較高（36 對 33）；2 級起線 A 生命一度較高，自 4 級起線 B 的攻擊與生命都明顯較高。戰力列全程相同。</p>")
    add('      <h3 id="costs">訓練與治療消耗</h3>')
    add(
        "<p>消耗寫成 <code>999|4|數量</code>、<code>999|5|數量</code>，對應資源 4「"
        f'{H(o.resources[4], terms)}」、資源 5「{H(o.resources[5], terms)}」（<code>top_resource_name_4</code>／<code>5</code>）。'
        "<code>train_time</code>、<code>treat_time</code>、<code>lvup_time</code> 表上是整數，沒有寫單位，本頁不自行換算成秒。</p>"
    )
    add(
        "<p>三個有中文名的陣營，在同一條線、同一等級的訓練／治療欄完全相同。神族（B 線 race 4）的木材、石頭數量與線 A 同階相同；"
        "治療時間在 1–3、5–10 級也與線 A 相同，唯獨 4 級的 <code>treat_time</code> 是 40，線 A 同階是 30。"
        "表上 1–5 級的 <code>train_time</code> 也與線 A／B 其他三營不同（150／210／270／360／450，對上同階的 75／150／225／300／400）；"
        "6–10 級訓練時間與線 A 相同。B 線聯盟／部族／自然（1901–1910 等）從 5 級起，部分訓練與治療數量、以及各級治療時間，與線 A 不同。"
        "線 B 仍沒有兵營與 <code>season_get</code>；這些欄位只是表上有值，不能據此把 B 線寫成兵營可訓練士兵。</p>"
    )
    add("<p>線 A（三營相同）：</p>")
    add(tbl["a_cost"])
    add("<p>線 B、聯盟／部族／自然（以 1901–1910 為例；捐贈勳章與王國擊殺積分為 −1）：</p>")
    add(tbl["b_cost"])
    add('      <h3 id="fight">戰鬥類型開關</h3>')
    add("<p><code>fight_type.json</code> 72 種戰鬥類型。與士兵直接有關的開關是 <code>switch_troop_morale</code>、<code>switch_troop_carry</code>（表上為 1 或 −1）。本頁核對 41 筆 <code>switch_troop_morale=1</code>（含打田、競技場、掠奪、天梯、冠軍對決等常見 PvP，以及部分 PvE），其餘為 −1。開關打開後士氣壓制是否一定生效，表只給開關。</p>")
    add(f"<p><code>switch_troop_carry</code> 在競技場、3v3 天梯賽、玩家間切磋、冠軍對決等為 −1，在打田、掠奪、遺蹟等為 1。冠軍對決說明寫「{H(o.duel, terms)}」（<code>champion_duel_info_desc_1_3</code>）。兵營建築與「可訓練」說明只對上線 A；這只說明「可訓練」的字面指向兵營那套，不能把 <code>switch_troop_carry=-1</code> 寫成改走 19xx。再掃過戰鬥類型與相關編成表，沒有欄位把某場戰鬥對到 19xx／29xx 那套 id。</p>")
    add('      <h3 id="divine">神族（只在 B 線）</h3>')
    add(
        f"<p>4901–4910 的 <code>race=4</code>，字串 <code>unit_race_4</code> 為「{H('神族', terms)}」。"
        "名稱鍵是 <code>troop_name_4001</code>–<code>troop_name_4010</code>（不是 4901），說明鍵 <code>troop_desc_4001</code>–<code>4010</code>，"
        "<code>strings_zh</code> 都沒有對應文案，本頁不編造名稱。攻擊、生命、戰力、負重與同階 B 線其他三營相同，士氣為 0，沒有兵營。"
        "這 10 筆是全表僅有 <code>map_soldier_scale</code> 不為 −1 的列：4901–4906 為 18，4907–4910 為 15。該欄含義未驗證。</p>"
    )
    add("    </section>")
    add('    <section id="formulas">')
    add("      <h2>官方公式與面板、戰報核對</h2>")
    add("<p>官方屬性介面把士兵攻擊、生命寫成：</p>")
    add(f"<ul><li>{H(o.formulas['atk'], terms)}</li><li>{H(o.formulas['hp'], terms)}</li></ul>")
    add(
        "<p>面板兵種階級 XII／XI 是兵營那套（有 11、12 級）。戰報裡單個士兵攻擊／生命基礎值也用這套，不是 19xx。"
        f"已核對的一例：審判官戰報攻擊基礎值 110＝建築 50（{H('天穹聯盟戰士', terms)} 1012）＋符文 21＋光輝建築 39（<code>shine_troop</code> 聯盟第 7 級攻擊）；"
        "生命基礎值 1508＝建築 900＋科技 10＋符文 64＋光輝建築 534（第 7 級生命）。建築與光輝兩項與表一致。光輝建築點數是加進單兵基礎值，與兵營基礎值相加，而不是改走 19xx。</p>"
    )
    add("<p>百分比來源加總與表頭一致；數量因顯示進位仍推不出唯一整數，維持未驗證。</p>")
    add("<p>英雄攜帶士兵上限＝畫面上列出的來源點數相加；其中「等級」＝<code>hero_level.army_count</code>（品質 3–5 為 2×等級，品質 6 為 3×等級）。出征上限（1019 等）與容納士兵上限（1018 等）沒有出現在這份攜帶上限清單。戰鬥公式裡的「士兵數量」與這份攜帶上限是否同一整數，維持未驗證。</p>")
    add(
        "<p>和「士兵攻擊百分比」名稱相近的屬性：科技、兵裝、裝飾、領主裝備、英雄天賦、公會科技等大量寫入的 <code>type=2</code> 屬性是 10103／10104「"
        f"{H(attr_label(10103, data.attr_by), terms)}／{H(attr_label(10104, data.attr_by), terms)}」，以及分營的 13103／14103／15103（生命同理：13104／14104／15104）。"
        "公式用語仍不能從表寫死只對 10103 一條。10105／10106 的屬性表 <code>name</code> 指向「"
        f"{H(table_name_label(10105, data.attr_by), terms)}／{H(table_name_label(10106, data.attr_by), terms)}」，"
        "本抽取沒有來源把數值寫進 10105／10106，不能當成這條百分比欄的候選。10003／10004「"
        f"{H(attr_label(10003, data.attr_by), terms)}／{H(attr_label(10004, data.attr_by), terms)}」是 <code>type=1</code> 點數，本抽取幾乎沒有來源寫入。10103 與分營條如何疊加，表沒有說明。</p>"
    )
    add("    </section>")
    add('    <section id="shine">')
    add("      <h2>光輝建築</h2>")
    add(
        f"<p>官方屬性來源分類 32 的名稱是「{H(o.categories[32][0], terms)}」，說明是「{H(o.categories[32][1], terms)}」"
        "（<code>hero_detailed_stats_ui_shine</code>／<code>_dec</code>）。介面另有「"
        f"{H(o.shine_tip, terms)}」（<code>UI_army_shine_attr_tip</code>）。本頁說的光輝士兵數值在 <code>shine_troop.json</code>，對到的是兵營建築的 <code>shine_lv</code>，不是改走 B 線。</p>"
    )
    add("<p><code>shine_troop.json</code> 24 筆：三個種族（1／2／3，對應三座兵營）各 8 級（<code>shine_lv</code> 1–8）。同階的攻擊、生命、士氣、戰力、負重三營完全相同。<code>attr_3</code> 同樣是 <code>[10057, 0]</code>。沒有種族 4（神族）列，也沒有獨立中文名稱鍵。</p>")
    add("<p>兵營升級表（以聯盟兵營 125 為例；126／127 結構相同，建築 id 改前綴）：建築 40 級起出現 <code>shine_para1</code>；41–44 級 <code>shine_lv=0</code>；45 級起 <code>shine_lv=1</code>，之後每 5 級加一階，80 級 <code>shine_lv=8</code>。<code>shine_troop.building_id</code> 正好對上 45、50、55、60、65、70、75、80 級（聯盟為 125045–125080）。此段兵營 <code>shine_lv</code> 進度已對 <code>citybuilding_lvup.json</code> 與 <code>citybuilding_lvup_new.json</code> 的 125／126／127 列核過，兩表在這些列上一致；本頁不把整份建築升級表展開。</p>")
    add(tbl["shine"])
    add("<p>已鎖定：光輝聯盟 <code>shine_lv</code> 7、id 1490019 為攻擊 39、生命 534、士氣 500，戰報把這組點數加進單兵基礎值。</p>")
    add(f"<p>另有建築「{H(o.buildings[169][0], terms)}」（<code>citybuilding_name_169</code>），說明是「{H(o.buildings[169][1], terms)}」。那是另一個建築與科技線，本頁不展開。</p>")
    add("    </section>")

    add('    <section id="skins">')
    add("      <h2>兵裝</h2>")
    add(
        f"<p>官方系統名是「{H(o.skin_system, terms)}」（<code>troop_skin</code>）。屬性來源分類 33「{H(o.categories[33][0], terms)}」、34「{H(o.categories[34][0], terms)}」。"
        f"對應建築是{H(o.buildings[142][0], terms)}（<code>citybuilding_name_142</code>），說明為「{H(o.buildings[142][1], terms)}」。"
        "升級前置寫在 <code>troop_skin_level.prebuilding_level</code>，都是建築 142 的指定等級。</p>"
    )
    add("<p>養成說明原文（<code>info_title_army_troop_skin_content1</code>）：</p>")
    add("<ol>" + "".join(f"<li>{H(re.sub(r'^\\d+\\.', '', ln).strip(), terms)}</li>" for ln in o.skin_training) + "</ol>")
    add(
        f"<p>資源 17 的名稱是「{H(o.resources[17], terms)}」（<code>top_resource_name_17</code>）。另有道具 1017「{H(o.honor_item_name, terms)}」，說明為「{H(o.honor_item_desc, terms)}」。"
        "榮譽突破表的 <code>cost_1</code> 寫的是 <code>999|17|數量</code>，沒有寫入 1017；兩種寫法如何對上，表沒有說明，維持未驗證。</p>"
    )
    add(
        f"<p>影響力目錄（<code>influence_level.json</code>）在「士兵」下有「士兵強化 → {H(o.skin_system, terms)}」；同目錄把三營士兵寫成「"
        f"{H('聯盟士兵', terms)}／{H(o.tribe_word, terms)}／{H('自然士兵', terms)}」（此處原文是「部落」不是「部族」）。</p>"
    )
    add('      <h3 id="catalog">名錄</h3>')
    add("<p><code>troop_skin_level.json</code> 4,853 筆，有 23 個 <code>group</code>（5301、5302、5401–5407、5501–5514），每組 211 筆、等級 1–50。其中 21 組在突破表與榮譽突破表出現，並可對到道具名稱。<code>jump.json</code> 用 <code>goods_name_*</code> 對到其中 14 組（5301–5302、5403–5407、5501–5507）；5508–5514 沒有這類跳轉列，但仍有道具名稱、升級、突破與榮譽表。</p>")
    add(f"<p>部分組的突破／榮譽消耗道具 id，與名稱所用的 <code>goods_name</code> id 不同（例如{H('熊皮勇士', terms)}名稱是 2024506，消耗寫 2024543，而後者沒有 <code>goods_name</code> 字串）。本頁同時記錄兩種 id，不臆測為何分開。</p>")
    add(
        f"<p>另有道具 2024503「{H(o.gunner_name, terms)}」，說明為「用於士兵兵裝解鎖或突破，{H(o.gunner_clause, terms)}」，但沒有對上任何 <code>group</code>，也不在 <code>jump</code> 的兵裝列。"
        "5401、5402 兩組只有升級表（品質 4，曲線與 5403–5407 完全相同），沒有名稱字串、沒有跳轉、也沒有突破或榮譽列，本頁不編造名稱。</p>"
    )
    add(f"<p><code>troop_skin_name501</code> 為「{H(o.leftover_name, terms)}」、<code>troop_skin_break_desc501</code> 為「{H(o.leftover_desc, terms)}」，沒有出現在上述 23 個 group 裡，本頁只記有這兩條字串，不把它寫進名錄。</p>")
    add(f"<p>道具說明裡，「{H('可同時被多隊裝載', terms)}」或「{H('只可同時被一隊裝載', terms)}」與養成說明第 5 點一致：下列品質 3、4 的具名兵裝寫可多隊；品質 5 的具名兵裝寫只可一隊。</p>")
    add(tbl["catalog"])
    add("<p>各具名兵裝的道具說明前段（解鎖／突破句之前）照錄於下，不作評價：" + _fronts_html(data, terms) + "</p>")
    add('      <h3 id="upgrade">升級（<code>troop_skin_level</code>）</h3>')
    add("<p>每組 211 筆：等級 1–16 各 1 列（<code>level_small=-1</code>）；17 級起出現 <code>level_small</code> 分列，筆數隨等級增加，至 44–49 級各 10 列（<code>level_small</code> 0–9）；50 級只有 <code>level_small=0</code> 一列。<code>level_small</code> 在介面上叫什麼，表沒有名稱，只記欄位。</p>")
    add("<p><code>unlock_lv</code> 為 0–6，與兵裝研究所等級前置成對出現（例：1–9 級 <code>unlock_lv=0</code>、前置 <code>[142, 1]</code>；10–19 級開始要 142 的 10 級；50 級 <code>unlock_lv=6</code>、前置 <code>[142, 50]</code>）。升級消耗欄是 <code>exp</code>（整數），表沒有另寫資源 id；養成說明寫「消耗勳章可以升級兵裝」。</p>")
    add("<p>升級屬性按品質帶分成幾組曲線（同品質、同屬性組合的組，1–50 級含 <code>level_small</code> 的攻擊／生命／戰力／<code>exp</code> 完全相同）：</p>")
    add(tbl["upgrade"])
    add(f"<p>5509–5514 的第三項從 1 級就有，收到 50 級為 400。這第三項與突破表裡 5512–5514 的「{H('守城時減傷', terms)}」（屬性 1000119）不是同一條，不要混讀。</p>")
    add('      <h3 id="break">突破（<code>troop_skin_break</code>）</h3>')
    add("<p>21 組、每組 7 階（<code>level</code> 0–6），共 147 筆。第 0–5 階的 <code>skin_lv_min</code>／<code>skin_lv_max</code> 依序為 10、20、30、40、45、50，<code>castle_lv_min</code> 為 10，消耗為同種兵裝 1／1／2／3／3／3 個。第 6 階 <code>skin_lv</code> 仍為 50，<code>castle_lv_min</code> 為 −1，<code>cost</code> 為空。本頁只記欄位，不把第 6 階寫成「自動升」或其他未見於表的規則。</p>")
    add("<p>突破說明取 <code>troop_skin_break_desc{group}</code>。部分組另有 <code>display_num</code> 字串陣列，對應說明裡的 <code>{0}</code>、<code>{1}</code>…占位符，本頁照錄該欄，不自行用原值換算去改寫它。要注意：多組在第 5、6 階的 <code>display_num</code> 不再隨 <code>attrList</code> 增加，或與「原值÷100」不一致（例如盾兵第 4 階起 <code>display_num</code> 停在 30／10／20，但 <code>attrList</code> 續增；優雅侍者第 6 階 <code>display_num</code> 為 42／18／36，與第 5 階的 48／18／36 以及 <code>attrList</code> 都不相同）。沒有 <code>display_num</code> 的組只記原值。下文「官方說明」是該組文案模板，數字以表為準。</p>")
    add(
        "<p>下列各表「屬性」欄記 <code>attrList</code> 原值，屬性名取 <code>attribute_name_{id}</code>。10188 沒有 <code>attribute_name_10188</code>，屬性表 <code>name</code> 指向「"
        f'{H("士兵士氣", terms)}」，照這一名稱記，並標 id 10188（<code>type=2</code>、<code>show_type=2</code>）。</p>'
    )
    add(
        f"<p><strong>{H('盾兵', terms)} 5301。</strong>官方說明：{H(data.skins[5301].break_desc, terms)}。"
        f"屬性為 1052 {H(attr_label(1052, data.attr_by), terms)}、10103、10104。戰力 {_slash_powers(data.skin_breaks[5301])}。</p>"
    )
    add(tbl["br5301"])
    add(_break_prose_html(data, terms))
    add(
        f"<p><strong>{H(data.skins[5506].name, terms)} 5506、{H(data.skins[5507].name, terms)} 5507、{H(data.skins[5508].name, terms)} 5508。</strong>"
        f"三組說明結構相同，只改陣營。5507 原文：{H(data.skins[5507].break_desc, terms)}。5506、5508 把「聯盟」換成「自然」「部族」。沒有 <code>display_num</code>。"
        f"戰力 {_slash_powers(data.skin_breaks[5507])}。消耗個數 1／1／2／3／3／3／空。</p>"
    )
    add(
        f"<p>分營攻擊／生命與「同營生命額外」對應：5506 為 15103／15104／21028（{H(attr_label(21028, data.attr_by), terms)}）；"
        "5507 為 13103／13104／21024（聯盟）；5508 為 14103／14104／21026（部族）。消耗 id 分別為 2024556／2024557／2024558。</p>"
    )
    add(tbl["br5507"])
    add(
        f"<p><strong>{H(data.skins[5509].name, terms)} 5509、{H(data.skins[5510].name, terms)} 5510、{H(data.skins[5511].name, terms)} 5511。</strong>"
        "說明為：本隊〔陣營〕士兵攻擊提升{0}%，〔陣營〕士兵生命提升{1}%，〔陣營〕逆克制增傷提升{2}%。沒有 <code>display_num</code>。"
        f"戰力 {_slash_powers(data.skin_breaks[5509])}。消耗個數 1／1／2／3／3／3／空。</p>"
    )
    add("<p>5509：13103／13104／3029，消耗 2024559。5510：14103／14104／4031，消耗 2024560。5511：15103／15104／5027，消耗 2024561。</p>")
    add(tbl["br5509"])
    add(
        f"<p><strong>{H(data.skins[5512].name, terms)} 5512、{H(data.skins[5513].name, terms)} 5513、{H(data.skins[5514].name, terms)} 5514。</strong>"
        f"說明：本隊〔陣營〕士兵攻擊提升{{0}}%，〔陣營〕士兵生命提升{{1}}%，守城時減傷提升{{2}}%。屬性第三項是 1000119 {H(attr_label(1000119, data.attr_by), terms)}"
        "（不是升級表上的 3019／4019／5019）。沒有 <code>display_num</code>。戰力與消耗個數與山羊騎士組相同。</p>"
    )
    add("<p>5512：13103／13104，消耗 2024562。5513：14103／14104，消耗 2024563。5514：15103／15104，消耗 2024564。</p>")
    add(tbl["br5512"])
    add('      <h3 id="honor">榮譽突破（<code>troop_skin_honor_break</code>）</h3>')
    add(
        f"<p>21 組、每組 150 級（<code>level</code> 1–150），共 3,150 筆。介面文案有「{H(o.honor_forbid, terms)}」「{H(o.honor_unlock, terms)}」。"
        "表上的 <code>quality</code> 在前 99 級等於該兵裝升級表的品質（3／4／5），100–150 級升一檔（4／5／6）。"
        "<code>i_attr</code>（表欄 <code>i_attrList</code>）只出現在升檔後的 100–150 級，同一組這 51 級的 <code>i_attr</code> 固定不變。"
        "<code>attr_1</code> 每級遞增，多數組是士兵生命（10104）或對應分營士兵生命（13104／14104／15104）。</p>"
    )
    add(
        f"<p>消耗：<code>cost_1</code> 為 <code>999|17|數量</code>（資源 17「{H(o.resources[17], terms)}」），<code>cost_2</code> 為同種兵裝。"
        f"品質 3 組（{H('盾兵', terms)}、{H('騎兵', terms)}）勳章 12,500、兵裝 25；品質 4 組多數是勳章 25,000、兵裝 5（{H('鼓號隊', terms)}"
        "在品質 4 的 2–49 級勳章為 12,500，第 1 級與 50–99 級及品質 5 仍為 25,000）；品質 5 組在 1–99 級是勳章 50,000、兵裝 1，100–150 級兵裝改為 2。第 150 級 <code>cost</code> 為空。</p>"
    )
    add("<p><code>attr_1</code> 與戰力（該品質段首尾）：</p>")
    add(tbl["honor_attr"])
    add("<p>升檔後固定 <code>i_attr</code>（100–150 級；寫成 0 的分項也照錄）。5509–5511 另有 <code>attr_2</code>（逆克制增傷 100）；5512–5514 的 <code>attr_2</code> 是 3019／4019／5019 各 100，與 <code>i_attr</code> 裡的 1000119 不是同一條：</p>")
    add(tbl["honor_i"])
    add('      <h3 id="locked">已鎖定的聯盟兵裝面板對照</h3>')
    add("<p>以下只鎖定這一組面板數字，不推廣到其他兵裝或其他 <code>show_type=2</code> 屬性。</p>")
    add(
        f"<p>聯盟兵裝突破第 6 階（group 5507，{H('甜點騎士', terms)}）的原值：13103＝2800、13104＝5600、10188＝350、1300106＝350、21024＝1400。"
        "榮譽突破品質 6 的固定 <code>i_attr</code>：21024＝280、10188＝80、1300106＝80（13103／13104 在此列為 0）。兩者相加後，對上面板：</p>"
    )
    add("<ul>")
    add(f"<li>{H('士兵士氣', terms)}／{H('集結士氣', terms)} 4.30%（350＋80）</li>")
    add(f"<li>{H(attr_label(21024, data.attr_by), terms)} 16.80%（1400＋280）</li>")
    add(f"<li>{H('聯盟士兵攻擊', terms)} 28%（2800）</li>")
    add(f"<li>{H('聯盟士兵生命', terms)}裡，標成「{H('兵裝突破', terms)}」的那一部分 56%（5600）</li>")
    add("</ul>")
    add("<p>集結士氣官方兵裝文案有「不可疊加」。屬性 1300106 的 <code>max=5000</code> 且 <code>is_max_show=1</code>，對上畫面括號「最大 50%」。</p>")
    add("<p>榮譽表 <code>attr_1</code> 在聯盟士兵生命還有約 10%–15%（品質 6 時 13104 為 1000–1500），但面板「兵裝突破」生命正好是 56%，這筆沒有出現在該行，維持未驗證。</p>")
    add('      <h3 id="march">行軍造型（面板有提到，不是本篇主體）</h3>')
    add(
        f"<p>同一張聯盟士兵生命面板，另 20% 標示來自行軍造型。屬性來源分類 50 的名稱就是「{H(o.march_name, terms)}」，說明為「{H(o.march_desc, terms)}」。"
        "要對上這 20%，需要唯一的 <code>13104|2000</code> 表列；本抽取在行軍／世界造型相關表裡沒有 13104。不要把這 20% 強行對成：</p>"
    )
    add("<ul>")
    add(f"<li>{H(o.shield_name, terms)}（那是建築 121「{H(o.shield_desc, terms)}」，不是一筆 <code>13104|2000</code> 或 <code>10104|2000</code> 的行軍造型列）</li>")
    add("<li>裝飾物 DIY 裡恰好寫了 <code>13104|2000</code> 的列（<code>citybuilding_DIY_property</code> 有多筆 13104，其中 11150107、15550304 的值是 2000，來源分類是裝飾物，不是行軍造型）</li>")
    add("</ul>")
    add(
        "<p>因此：面板有這 20%，表上沒有唯一對得上的行軍造型列，維持未驗證。行軍造型目錄本身見城堡／世界造型相關篇，不在本篇展開；也不把已發佈的"
        f'<a href="skins.html">{H("造型總表", terms)}</a>當成行軍造型名錄（那是英雄造型）。</p>'
    )
    add("    </section>")
    add('    <section id="morale">')
    add("      <h2>士氣</h2>")
    add("<p>官方介面字串已經說明規則，但沒有把數字寫進對照表：</p>")
    add("<ul>")
    add(f"<li><code>morale_002</code>：{H(official_text('morale_002'), terms)}</li>")
    add(f"<li><code>morale_003</code>：{H(official_text('morale_003'), terms)}</li>")
    add(f"<li><code>morale_004</code>：{H(official_text('morale_004'), terms)}</li>")
    add(f"<li><code>morale_005</code>／<code>006</code>：{H(official_text('morale_005'), terms)}／{H(official_text('morale_006'), terms)}</li>")
    add("</ul>")
    add("<p>因此還不能寫出「x 倍士氣對應 y 倍傷害」的數列。戰報「士氣影響」的工作假設在戰鬥公式的結算草稿，本頁不把那套假設抄進來當已驗證公式。官方另有傷害上限「最多 300%」的說法，與戰力係數上限 2.0 不是同一條。</p>")
    add(
        f"<p>與士氣有關的屬性：88 {H(attr_label(88, data.attr_by), terms)}、10088 {H(attr_label(10088, data.attr_by), terms)}、16000 {H(attr_label(16000, data.attr_by), terms)}"
        f"（皆 <code>type=1</code>）；16001 {H(attr_label(16001, data.attr_by), terms)}（<code>type=2</code>）；另有 1136 {H(attr_label(1136, data.attr_by), terms)}、1137 {H(attr_label(1137, data.attr_by), terms)}、"
        f"1130 {H(attr_label(1130, data.attr_by), terms)}、1131 {H(attr_label(1131, data.attr_by), terms)}；以及兵裝用的 10188（名稱同「{H('士兵士氣', terms)}」，<code>type=2</code>）、"
        f"1300106 {H(attr_label(1300106, data.attr_by), terms)}、1300108 {H(attr_label(1300108, data.attr_by), terms)}。16001 如何疊進上述 {{1}} 倍傷害，表沒有說明。</p>"
    )
    add("<p>士兵表上，線 A 的 <code>troop.morale</code> 為 205–800；光輝士兵為 100、200、300、350、400、450、500、550。線 B 的 <code>morale</code> 為 0。<code>switch_troop_morale</code> 見上文戰鬥類型一節。關卡技能 <code>troop_morale_skill_01</code> 不可拿來當通用 PvP 士氣表。</p>")
    add("    </section>")
    add('    <section id="models">')
    add("      <h2>部隊外觀編號（不是兵裝）</h2>")
    add("<p><code>troop_skin.json</code> 155 筆，欄位只有 <code>id</code>、<code>skin_id</code>、<code>skill_ID</code>、<code>spine_skin</code>，這是士兵模型／外觀編號，不是上文的兵裝圖鑑。<code>troop.json</code> 的 <code>skin_ID</code> 指向這裡（例如 1001 與 1901 都是 10011–10014）。<code>skill_ID</code> 只有 1001、1002、1003、1004 四種。本頁不把這張表當成兵裝名錄，也不展開模型資源。</p>")
    add("    </section>")
    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add("<li>士兵捐贈上限表（<code>troop_donate.json</code> 243 筆，按種族與兵營等級給 <code>limit</code>／賽季與伺服器標記上限）。</li>")
    add("<li>光輝研究所與光輝科技的研究線。</li>")
    add("<li>行軍造型、城堡／世界造型、裝飾物 DIY 的完整名錄（只在士兵生命面板提到行軍造型 20% 時，說明沒有唯一表列）。</li>")
    add("<li>訓練時間、治療時間、<code>lvup_time</code> 的單位換算，以及實際訓練／治療介面是否讀線 B 的消耗欄。</li>")
    add("<li>10–12 級士兵（傳奇、天御、天穹）在 <code>building_id=-1</code> 之後的確切解鎖條件。</li>")
    add("<li><code>season_get</code>（<code>2|999|20|{level}</code>）與資源 20 的含義。</li>")
    add("<li><code>army_type</code> <code>[1, 2, 3]</code>、<code>map_soldier_scale</code>、屬性 10057（值為 0）的實際作用。</li>")
    add("<li>英雄攻擊／生命轉化率是否作用於士兵傷害。</li>")
    add("<li>士氣壓制的 x→y 數列、16001 的疊加方式，以及戰報「士氣影響」是否等於實際傷害倍率。</li>")
    add("<li>兵裝 <code>exp</code> 與勳章、榮譽道具 1017 與資源 17 的兌換關係；<code>level_small</code>、突破第 6 階空消耗在客戶端的具體顯示。</li>")
    add(f"<li>{H(o.gunner_name, terms)}（2024503）以及只有升級表的 5401、5402 在客戶端是否出現。</li>")
    add("<li>士兵與英雄技能、站位、陣容的搭配模擬，以及強弱評定。</li>")
    add("</ul>")
    add("    </section>")
    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<ul>")
    add(
        "<li>以下是整理用註記，查名稱與數值可略過。</li>"
    )
    add(
        "<li>士兵有兩條 id 線，不要混用。線 A：1001–1012、2001–2012、3001–3012（有 11、12 級）。"
        "線 B：1901–1910、2901–2910、3901–3910、4901–4910（只到 10 級；神族只在 B 線）。"
        "例如「傳奇聯盟戰士」既是 1010 也是 1910。面板與戰報基礎值用的是線 A，不是 19xx。"
        "已鎖定：天穹聯盟戰士 1012 的攻擊 50、生命 900；傳奇聯盟戰士 1910 的攻擊 113、生命 1500。"
        "不要把 <code>fight_type.switch_troop_carry</code> 強行對成 B 線或「虛擬兵」。"
        "官方公式鍵是 <code>hero_detailed_stats_ui_formula_4</code>／<code>8</code>。"
        "屬性名優先用 <code>attribute_name_{id}</code>。<code>show_type=2</code> 預設只記表內原值。"
        "不要從 <code>unlocktime</code>、<code>season</code> 或 <code>season_get</code> 自動標未開放。"
        "也不要把關卡技能 <code>troop_morale_skill_01</code> 當成通用 PvP 士氣表。"
        "行軍造型屬性來源分類 50。不要把聯盟士兵生命面板曾另標的 20% 強行對成裝飾物 DIY 的 <code>13104|2000</code>。</li>"
    )
    add(
        "<li>資料出自遊戲資料表與官方字串（troop、shine_troop、troop_skin_level、troop_skin_break、troop_skin_honor_break、jump、troop_skin、fight_type、attribute、attr_category、top_resource、strings_zh.json），"
        f"資料截至 {TROOP_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {e(TROOP_DATA_PACK)}（759 張表），打包時戳 {TROOP_DATA_PACKED}（香港時間）。"
        "士兵主表、光輝表與兵裝三表與第 19 章所用 2026-11-05 解壓檔、以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "<code>jump.json</code> 現行包與 2026-11-22 兩份歸檔相同（969 筆），2026-11-05 解壓檔少 3 筆（966），但本頁用到的 14 組兵裝跳轉列與 2026-11-05 位元組相同。"
        "<code>strings_zh.json</code> 現行檔與 2026-11-22 LocalLow 歸檔相同（40,581 鍵）；2026-11-05 與 2026-11-22 StreamingAssets 整體不同，本頁用到的鍵值與這三份歸檔一致。"
        "<code>attribute.json</code> 列數同為 764，2026-11-05 與現行包位元組不同，差在後來多了 <code>NameKey</code> 等欄；本頁用到的 <code>type</code>／<code>show_type</code>／<code>name</code>／<code>max</code>／<code>is_max_show</code>／<code>attribute_Id</code> 與 2026-11-05 相同。"
        "顯示規則依攻略手冊「士兵圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。這不是官方 wiki。</li>"
    )
    add("</ul>")
    add("    </section>")
    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {TROOP_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_troop_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    prefix = md_table(
        ["level", "quality", "名稱前綴（後接「〔陣營〕戰士」）", "線 A id", "線 B id"],
        _prefix_rows(),
    )
    diff = md_table(
        ["項目", "線 A（1001–1012 等）", "線 B（1901–1910 等，含神族）"],
        [
            ["最高等級", "12（天穹）", "10（傳奇）"],
            ["士氣 morale", "205–800", "全為 0"],
            ["correlate_building", "125／126／127（聯盟兵營／部族兵營／自然兵營）", "−1"],
            ["season_get", "2|999|20|{level}", "無（None）"],
            ["attr_3", "[10057, 0]（" + attr_label(10057, data.attr_by) + "，值為 0）", "無"],
            ["捐贈勳章、王國擊殺積分", "有正值", "donate_medal、擊殺積分皆為 −1"],
            ["同階戰力 power、負重 load、移動 speed", "與線 B 相同", "與線 A 相同"],
            ["中高階攻擊／生命", "較低（傳奇 40／770，天穹 50／900）", "較高（傳奇 113／1500）"],
        ],
    )

    def stat_rows(base: int, last: int) -> list[list[str]]:
        out = []
        for lv in range(1, last + 1):
            row = data.troops[base + lv - 1]
            out.append([
                str(lv), official_text(row["name"]), str(row["id"]), str(row["quality"]),
                str(row["atk"]), str(row["hp"]), str(row["morale"]), str(row["power"]), str(row["load"]),
            ])
        return out

    cols = ["等級", "名稱", "id", "品質", "攻擊", "生命", "士氣", "戰力", "負重"]
    a_stat = md_table(cols, stat_rows(1001, 12))
    b_stat = md_table(cols, stat_rows(1901, 10))
    a_cost = md_table(
        ["等級", "訓練時間", "木材", "石頭", "治療時間", "治療木材", "治療石頭", "lvup_time", "捐贈勳章"],
        [[str(lv)] + [str(x) for x in troop_costs(data.troops[1000 + lv])] for lv in range(1, 13)],
    )
    b_cost = md_table(
        ["等級", "訓練時間", "木材", "石頭", "治療時間", "治療木材", "治療石頭"],
        [[str(lv)] + [str(x) for x in troop_costs(data.troops[1900 + lv])[:6]] for lv in range(1, 11)],
    )
    shine_by = {(r["race"], r["shine_lv"]): r for r in data.shine}
    shine_rows = []
    for lv in range(1, 9):
        a, b, c = shine_by[(1, lv)], shine_by[(2, lv)], shine_by[(3, lv)]
        shine_rows.append([
            str(lv), str(a["id"]), str(b["id"]), str(c["id"]),
            str(a["atk"]), str(a["hp"]), str(a["morale"]), str(a["power"]), str(a["load"]), str(a["building_id"]),
        ])
    shine = md_table(
        ["shine_lv", "聯盟 id", "部族 id", "自然 id", "攻擊", "生命", "士氣", "戰力", "負重", "聯盟 building_id"],
        shine_rows,
    )
    catalog_rows = []
    for g in list(range(5301, 5303)) + list(range(5401, 5408)) + list(range(5501, 5515)):
        s = data.skins[g]
        if g in NAMELESS_SKIN_GROUPS:
            catalog_rows.append([str(g), "（無名稱字串）", "—", "—", str(s.quality), "無", "—"])
        else:
            cost = "同左" if s.cost_id == s.name_id else str(s.cost_id)
            catalog_rows.append([str(g), s.name, str(s.name_id), cost, str(s.quality), "有", s.clause])
    catalog = md_table(
        ["group", "名稱", "名稱道具 id", "消耗道具 id（若不同）", "升級表品質", "有突破／榮譽", "道具說明（裝載句）"],
        catalog_rows,
    )

    def up_row(label: str, group: int) -> list[str]:
        r1 = pick_level_row(data.skin_levels[group], 1)
        r50 = pick_level_row(data.skin_levels[group], 50)
        attrs = "、".join(
            f"{attr_label(a, data.attr_by)} {a}" if attr_label(a, data.attr_by) else str(a)
            for a, _v in r1["attrList"]
        )
        return [
            label, attrs,
            join_slash(v for _a, v in r1["attrList"]), join_slash(v for _a, v in r50["attrList"]),
            str(r1["fightforce"]), str(r50["fightforce"]), str(r1["exp"]), str(r50["exp"]),
        ]

    upgrade = md_table(
        ["組別", "升級屬性（id）", "1 級原值", "50 級原值", "1 級戰力", "50 級戰力", "1 級 exp", "50 級 exp"],
        [
            up_row("5301、5302", 5301), up_row("5401–5407", 5403), up_row("5501–5505", 5501),
            up_row("5506 " + data.skins[5506].name, 5506),
            up_row("5507 " + data.skins[5507].name, 5507),
            up_row("5508 " + data.skins[5508].name, 5508),
            up_row("5509 " + data.skins[5509].name, 5509),
            up_row("5510 " + data.skins[5510].name, 5510),
            up_row("5511 " + data.skins[5511].name, 5511),
            up_row("5512 " + data.skins[5512].name, 5512),
            up_row("5513 " + data.skins[5513].name, 5513),
            up_row("5514 " + data.skins[5514].name, 5514),
        ],
    )
    br5301_rows = []
    for i, row in enumerate(data.skin_breaks[5301]):
        amap = {a: v for a, v in row["attrList"]}
        br5301_rows.append([
            str(i), str(amap[1052]), str(amap[10103]), str(amap[10104]),
            display_num_cell(row.get("display_num")), break_cost_cell(row, show_id=(i == 0)),
        ])
    br5301 = md_table(["階", "1052", "10103", "10104", "display_num", "消耗"], br5301_rows)

    def faction_rows(group: int, extra: str) -> list[list[str]]:
        out = []
        for i, row in enumerate(data.skin_breaks[group]):
            pairs = row["attrList"]
            costs = parse_pipe_cost(row.get("cost"))
            cells = [str(i), str(pairs[0][1]), str(pairs[1][1])]
            if extra == "morale":
                cells.extend([str(pairs[2][1]), str(pairs[3][1]), str(pairs[4][1])])
            else:
                cells.append(str(pairs[2][1]))
            cells.append(str(costs[0][2]) if costs else "（空）")
            out.append(cells)
        return out

    br5507 = md_table(
        ["階", "分營攻擊", "分營生命", "10188", "1300106", "同營生命額外", "消耗個數"],
        faction_rows(5507, "morale"),
    )
    br5509 = md_table(
        ["階", "分營攻擊", "分營生命", "逆克制增傷", "消耗個數"],
        faction_rows(5509, "anti"),
    )
    br5512 = md_table(
        ["階", "分營攻擊", "分營生命", "1000119", "消耗個數"],
        faction_rows(5512, "red"),
    )
    honor_attr = md_table(
        ["組", "品質段", "等級", "attr_1", "戰力"],
        [
            ["5301、5302", "3→4", "1–99／100–150", "10104：2→198／200→300", "100→9900／10000→15000"],
            ["5403–5407", "4→5", "1–99／100–150", "10104：5→495／500→750", "200→19800／20000→30000"],
            ["5501–5505", "5→6", "1–99／100–150", "10104：10→990／1000→1500", "400→39600／40000→60000"],
            ["5506", "5→6", "同上", "15104：10→990／1000→1500", "同上"],
            ["5507", "5→6", "同上", "13104：10→990／1000→1500", "同上"],
            ["5508", "5→6", "同上", "14104：10→990／1000→1500", "同上"],
            ["5509", "5→6", "同上", "13104：10→990／1000→1500", "400→39600／53750→73750"],
            ["5510", "5→6", "同上", "14104：10→990／1000→1500", "同 5509"],
            ["5511", "5→6", "同上", "15104：10→990／1000→1500", "同 5509"],
            ["5512", "5→6", "同上", "13104：10→990／1000→1500", "同 5509"],
            ["5513", "5→6", "同上", "14104：10→990／1000→1500", "同 5509"],
            ["5514", "5→6", "同上", "15104：10→990／1000→1500", "同 5509"],
        ],
    )

    def iattr_text(g: int) -> str:
        row = next(r for r in data.skin_honors[g] if r["level"] == 100)
        parts = [f"{a}＝{v}" for a, v in (row.get("i_attrList") or [])]
        a2 = row.get("attr_2")
        extra = f"（另 attr_2 {a2[0]}＝{a2[1]}）" if a2 else ""
        return "，".join(parts) + extra

    honor_i = md_table(
        ["組", "升檔後 i_attr（原值）"],
        [[f"{g} {data.skins[g].name}", iattr_text(g)] for g in SKIN_CATALOG],
    )
    return {
        "prefix": prefix, "diff": diff, "a_stat": a_stat, "b_stat": b_stat,
        "a_cost": a_cost, "b_cost": b_cost, "shine": shine, "catalog": catalog,
        "upgrade": upgrade, "br5301": br5301, "br5507": br5507,
        "br5509": br5509, "br5512": br5512, "honor_attr": honor_attr, "honor_i": honor_i,
    }


def _fronts_md(data: TablesData) -> str:
    o = data.official
    bits = []
    for item in (5301, 5302, GUNNER_GOODS_ID, 5403, 5404, 5501, 5502, 5405, 5503, 5504, 5505, 5406, 5407, 5506, 5507, 5508, 5509, 5510, 5511, 5512, 5513, 5514):
        if item == GUNNER_GOODS_ID:
            name, front = o.gunner_name, o.gunner_front
        else:
            name, front = data.skins[item].name, data.skins[item].front
        bits.append(f"{name}「{front}」")
    return "；".join(bits)


def _break_prose_md(data: TablesData) -> list[str]:
    def desc(g: int) -> str:
        return data.skins[g].break_desc

    def lab(aid: int) -> str:
        return attr_label(aid, data.attr_by) or str(aid)

    def powers(g: int) -> str:
        return _slash_powers(data.skin_breaks[g])

    return [
        f"**騎兵 5302。**說明：{desc(5302)}。屬性 1076 {lab(1076)}、10103、10104。戰力與消耗個數與盾兵相同（消耗 id 2024502）。`display_num`：10／2／4、20／4／8、30／6／12、40／8／16、50／10／20，第 5、6 階仍為 50／10／20；對應原值 1000／200／400 起，每階加 1000／200／400，第 6 階為 7000／1400／2800。",
        f"**熊皮勇士 5403。**說明：{desc(5403)}。屬性 1100003 {lab(1100003)}、10103、10104。戰力 {powers(5403)}。原值第 0 階 700／300／600，每階加 700／300／600，第 6 階 4900／2100／4200。`display_num` 第 0–5 階為 7／3／6 起依此遞增至 42／18／36，第 6 階仍為 42／18／36。消耗 id 2024543，個數 1／1／2／3／3／3／空。",
        f"**武士 5404。**說明：{desc(5404)}。屬性 1000105 {lab(1000105)}、10103、10104。原值、`display_num`、戰力、消耗個數與熊皮勇士相同（消耗 id 2024544）。",
        f"**優雅侍者 5405。**說明：{desc(5405)}。屬性 1000104（`attribute_name_1000104` 為「{lab(1000104)}」）、10103、10104。第 0 階原值 800／300／600，每階加 800／300／600，第 6 階 5600／2100／4200。`display_num` 第 0–5 階為 8／3／6 至 48／18／36，第 6 階為 42／18／36。戰力、消耗個數同上（消耗 id 2024545）。",
        f"**後勤隨從 5406。**說明：{desc(5406)}。屬性 1300105 {lab(1300105)}（`max=20000`、`is_max_show=1`）、10103、10104，以及再一筆 10104。第 0 階原值 100／300／600／400，每階加 100／300／600／400，第 6 階 700／2100／4200／2800。`display_num` 第 0–5 階為 1／3／6／4 至 6／18／36／24，第 6 階仍為 6／18／36／24。戰力、消耗個數同上（消耗 id 2024546）。1300105 的上限如何顯示，除 `max`／`is_max_show` 兩欄外，本頁不自行換算。",
        f"**鼓號隊 5407。**說明：{desc(5407)}。屬性 1300106 {lab(1300106)}、10103、10104、10188 {lab(10188)}。第 0 階原值 50／300／600／50，每階加 50／300／600／50，第 6 階 350／2100／4200／350。`display_num` 第 0–5 階為 0.5／3／6／0.5 至 3／18／36／3，第 6 階仍為 3／18／36／3。戰力、消耗個數同上（消耗 id 2024547）。集結士氣 1300106 的 `max=5000` 且 `is_max_show=1`，與畫面括號「最大 50%」的對照見後文已鎖定項。",
        f"**榮耀近衛 5501。**說明：{desc(5501)}。屬性 48 {lab(48)}、10103、10104。戰力 {powers(5501)}。第 0 階原值 200／400／800，每階加 200／400／800，第 6 階 1400／2800／5600。`display_num` 第 0–5 階為 2／4／8 至 12／24／48，第 6 階仍為 12／24／48。消耗 id 2024551，個數 1／1／2／3／3／3／空。這裡的「守城時減傷」對到屬性 48；5512–5514 說明裡同樣寫「守城時減傷」，對到的是 1000119，不是同一條。",
        f"**重騎兵 5502。**說明：{desc(5502)}。屬性 45 {lab(45)}、1076、10103、10104。第 0 階原值 160／1000／400／800，第 6 階 1120／7000／2800／5600。`display_num` 第 0–5 階為 1.6／10／4／8 至 9.6／60／24／48，第 6 階仍為 9.6／60／24／48。戰力、消耗個數與榮耀近衛相同（消耗 id 2024552）。",
        f"**攻城車 5503。**說明：{desc(5503)}。屬性 1000106 {lab(1000106)}、1129、1114 {lab(1114)}、10103、10104。1129 的名稱鍵 `attribute_name_1129` 在字串表中不存在，本頁不編造名稱；它是 `type=1`、`show_type=1`。第 0 階原值 160／1000／1000／400／800，第 6 階 1120／7000／7000／2800／5600。`display_num` 第 0 階為 1.6／1000／10／4／8；第 5 階為 9.6／6000／60／24／48，第 6 階仍為 9.6／6000／60／24／48（1129 的顯示字是「1000」「2000」這種原值，不是改寫成 10、20）。戰力、消耗個數同上（消耗 id 2024553）。",
        f"**無畏戰士 5504。**說明：{desc(5504)}。屬性 1131 {lab(1131)}、1037 {lab(1037)}（`type=1`、`show_type=1`）、10103、10104。第 0 階原值 300／1／400／800，第 6 階 2100／7／2800／5600。`display_num` 第 0–5 階為 3／1／4／8 至 18／6／24／48，第 6 階仍為 18／6／24／48。戰力、消耗個數同上（消耗 id 2024554）。",
        f"**骸靈士兵 5505。**說明：{desc(5505)}。屬性 1300108 {lab(1300108)}（`max=10000`、`is_max_show=1`，`attribute_Id=1137`）、兩筆 10103、以及 10104。第 0 階原值 200／100／400／800，第 6 階 1400／700／2800／5600。`display_num` 第 0–5 階為 2／1／4／8 至 12／6／24／48，第 6 階仍為 12／24／48。戰力、消耗個數同上（消耗 id 2024555）。",
    ]


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    lines: list[str] = []
    add = lines.append
    add("# Top Heroes Wiki｜士兵總表")
    add("")
    add(LEDE)
    add("")
    add(
        f"資料截至 {TROOP_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {TROOP_DATA_PACK}（759 張表），打包時戳 {TROOP_DATA_PACKED}（香港時間）。"
        "士兵主表、光輝表與兵裝三表與第 19 章所用 2026-11-05 解壓檔、以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；"
        "這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "`jump.json` 現行包與 2026-11-22 兩份歸檔相同（969 筆），2026-11-05 解壓檔少 3 筆（966），但本頁用到的 14 組兵裝跳轉列與 2026-11-05 位元組相同。"
        "`strings_zh.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（40,581 鍵）；2026-11-05 與 2026-11-22 StreamingAssets 整體不同，本頁用到的鍵值與這三份歸檔一致。"
        "`attribute.json` 列數同為 764，2026-11-05 與現行包位元組不同，差在後來多了 `NameKey` 等欄；本頁用到的 `type`／`show_type`／`name`／`max`／`is_max_show`／`attribute_Id` 與 2026-11-05 相同。"
        "顯示規則依攻略手冊「士兵圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。"
    )
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "正文只根據遊戲資料表與官方字串，不評定兵種或兵裝強弱，也不另外發明名稱。"
        "社群說法若出現會標成社群備註；本頁沒有這類條目。"
        "英雄裝備見[裝備總表](equipment.html)，領主裝備見[領主裝備總表](lord-equipment.html)。"
        "已發佈的 [專武總表](exclusive.html) 與 [造型總表](skins.html) 是英雄專武與英雄造型，不是本頁的士兵或兵裝。"
    )
    add("")
    add("- **士兵有兩條 id 線，不要混用。**線 A：1001–1012、2001–2012、3001–3012（有 11、12 級：天御、天穹）。線 B：1901–1910、2901–2910、3901–3910、4901–4910（只到 10 級傳奇；神族只在 B 線）。同一中文名會出現在兩條線（例如「傳奇聯盟戰士」既是 1010 也是 1910），戰力相同，攻擊／生命曲線不同。")
    add("- **面板士兵階 XII／XI，以及戰報裡的單兵攻擊／生命基礎值，用的是線 A（兵營那套），不是 19xx。**已鎖定：天穹聯盟戰士 1012 的攻擊 50、生命 900；傳奇聯盟戰士 1910 的攻擊 113、生命 1500。不要把 `fight_type.switch_troop_carry` 強行對成 B 線或「虛擬兵」。")
    add(
        f"- **官方屬性公式**（`hero_detailed_stats_ui_formula_4`／`8`）照錄為：{o.formulas['atk']}；生命同構：{o.formulas['hp']}。"
        "戰鬥公式裡的「士兵數量」因戰報 15.4M／600M 等顯示進位，推不出唯一整數，維持未驗證。"
    )
    add("- 屬性名優先用 `attribute_name_{id}`。`show_type=2` 預設只記表內原值，不自行換算成百分比。若官方文案或已鎖定面板有對應，該條照記，仍不推廣到其他屬性。")
    add("- 不要從 `unlocktime`、`season` 或 `season_get` 自動標未開放。`season_get` 只照錄欄位。")
    add("- 不要編造士氣「x 倍士氣造成 y 倍傷害」的數列。也不要把關卡技能 `troop_morale_skill_01` 當成通用 PvP 士氣表。")
    add(
        f"- 行軍造型不在本篇展開。屬性來源分類 50 的官方名稱是「{o.march_name}」。"
        f"不要把聯盟士兵生命面板曾另標的 20% 強行對成{o.shield_name}或裝飾物 DIY 的 `13104|2000`。"
    )
    add("- 品質欄只錄表上的數字（2–5）。養成說明若有「藍色、紫色兵裝」與「其他兵裝」的裝載規則，那是官方文案，不是替品質 3／4／5 改名。")
    add(
        f"- 官方用語是「部族」不是「部落」。種族名稱取 `unit_race_1`–`4`：1＝聯盟、2＝部族、3＝自然、4＝神族。"
        f"影響力目錄把三營士兵寫成「聯盟士兵／{o.tribe_word}／自然士兵」（此處原文是「部落」不是「部族」），照錄並標明。"
    )
    add("")
    add("## 士兵兩條線")
    add("")
    add(
        "主表 `troop.json` 76 筆。`race`：1＝聯盟（22 筆）、2＝部族（22）、3＝自然（22）、4＝神族（10，只在 B 線）。"
        "`quality` 為 2–5，`level` 為 1–12。`army_type` 皆為 `[1, 2, 3]`，本頁未對到這三個數字的含義。"
        f"`speed` 全表都是 100。`unit_ID` 全表都是 22002。`atk`／`hp` 就是屬性 3／4（{attr_label(3, data.attr_by)}／{attr_label(4, data.attr_by)}）。"
    )
    add("")
    add("有中文名的士兵全部是「戰士」一系。線 B 的名稱、說明鍵與線 A 相同（例如 1910 的 `name` 也是 `troop_name_1010`）。三營名稱結構相同，只改「聯盟／部族／自然」：")
    add("")
    add(tbl["prefix"])
    add("")
    add(f"官方說明句式相同，例如「{official_text('troop_desc_1012')}」（`troop_desc_1012`）。{o.team_tips}（`UI_hero_team_tips`）。")
    add("")
    add("### 兩條線的差別")
    add("")
    add(tbl["diff"])
    add("")
    add(
        f"兵營建築名稱：`citybuilding_name_125`／`126`／`127` 為{o.buildings[125][0]}、{o.buildings[126][0]}、{o.buildings[127][0]}。"
        f"說明分別是「{o.buildings[125][1]}」「{o.buildings[126][1]}」「{o.buildings[127][1]}」。"
        "兵營升級表到 80 級。線 A 的 1–9 級對到兵營 `building_id` 125000／125005／…／125040（即建築 0、5、10、…、40 級；部族、自然同規律，建築編號改 126、127）。"
        "10–12 級（傳奇、天御、天穹）的 `building_id` 為 −1，仍寫 `correlate_building` 為對應兵營。"
        "表沒有另寫這三級的解鎖條件；本頁不把科技「士兵等級＋1」或其他欄位寫成解鎖式。"
    )
    add("")
    add("`season_get` 的寫法是 `2|999|20|{level}`。資源 20 在 `top_resource.json` 有列，但 `strings_zh` 沒有 `top_resource_name_20`，本頁不編造資源名，也不把這一欄解釋成開放條件。")
    add("")
    add("### 單兵數值")
    add("")
    add("同階、同線的攻擊、生命、士氣、戰力、負重，三個有中文名的陣營完全相同；B 線神族的攻擊、生命、戰力、負重也與同階 B 線一致。因此下面只各列一張表。")
    add("")
    add("線 A（以聯盟為例；部族 20xx、自然 30xx 同值）：")
    add("")
    add(tbl["a_stat"])
    add("")
    add("線 B（以聯盟為例；部族 29xx、自然 39xx、神族 49xx 的攻擊／生命／戰力／負重同值。神族名稱見下節）：")
    add("")
    add(tbl["b_stat"])
    add("")
    add("1 級時兩條線攻擊同為 3，線 B 生命較高（36 對 33）；2 級起線 A 生命一度較高，自 4 級起線 B 的攻擊與生命都明顯較高。戰力列全程相同。")
    add("")
    add("### 訓練與治療消耗")
    add("")
    add(
        f"消耗寫成 `999|4|數量`、`999|5|數量`，對應資源 4「{o.resources[4]}」、資源 5「{o.resources[5]}」（`top_resource_name_4`／`5`）。"
        "`train_time`、`treat_time`、`lvup_time` 表上是整數，沒有寫單位，本頁不自行換算成秒。"
    )
    add("")
    add(
        "三個有中文名的陣營，在同一條線、同一等級的訓練／治療欄完全相同。神族（B 線 race 4）的木材、石頭數量與線 A 同階相同；"
        "治療時間在 1–3、5–10 級也與線 A 相同，唯獨 4 級的 `treat_time` 是 40，線 A 同階是 30。"
        "表上 1–5 級的 `train_time` 也與線 A／B 其他三營不同（150／210／270／360／450，對上同階的 75／150／225／300／400）；"
        "6–10 級訓練時間與線 A 相同。B 線聯盟／部族／自然（1901–1910 等）從 5 級起，部分訓練與治療數量、以及各級治療時間，與線 A 不同。"
        "線 B 仍沒有兵營與 `season_get`；這些欄位只是表上有值，不能據此把 B 線寫成兵營可訓練士兵。"
    )
    add("")
    add("線 A（三營相同）：")
    add("")
    add(tbl["a_cost"])
    add("")
    add("線 B、聯盟／部族／自然（以 1901–1910 為例；捐贈勳章與王國擊殺積分為 −1）：")
    add("")
    add(tbl["b_cost"])
    add("")
    add("### 戰鬥類型開關")
    add("")
    add("`fight_type.json` 72 種戰鬥類型。與士兵直接有關的開關是 `switch_troop_morale`、`switch_troop_carry`（表上為 1 或 −1）。本頁核對 41 筆 `switch_troop_morale=1`（含打田、競技場、掠奪、天梯、冠軍對決等常見 PvP，以及部分 PvE），其餘為 −1。開關打開後士氣壓制是否一定生效，表只給開關。")
    add("")
    add(f"`switch_troop_carry` 在競技場、3v3 天梯賽、玩家間切磋、冠軍對決等為 −1，在打田、掠奪、遺蹟等為 1。冠軍對決說明寫「{o.duel}」（`champion_duel_info_desc_1_3`）。兵營建築與「可訓練」說明只對上線 A；這只說明「可訓練」的字面指向兵營那套，不能把 `switch_troop_carry=-1` 寫成改走 19xx。再掃過戰鬥類型與相關編成表，沒有欄位把某場戰鬥對到 19xx／29xx 那套 id。")
    add("")
    add("### 神族（只在 B 線）")
    add("")
    add(
        "4901–4910 的 `race=4`，字串 `unit_race_4` 為「神族」。名稱鍵是 `troop_name_4001`–`troop_name_4010`（不是 4901），說明鍵 `troop_desc_4001`–`4010`，"
        "`strings_zh` 都沒有對應文案，本頁不編造名稱。攻擊、生命、戰力、負重與同階 B 線其他三營相同，士氣為 0，沒有兵營。"
        "這 10 筆是全表僅有 `map_soldier_scale` 不為 −1 的列：4901–4906 為 18，4907–4910 為 15。該欄含義未驗證。"
    )
    add("")
    add("## 官方公式與面板、戰報核對")
    add("")
    add("官方屬性介面把士兵攻擊、生命寫成：")
    add("")
    add(f"- {o.formulas['atk']}")
    add(f"- {o.formulas['hp']}")
    add("")
    add(
        "面板兵種階級 XII／XI 是兵營那套（有 11、12 級）。戰報裡單個士兵攻擊／生命基礎值也用這套，不是 19xx。"
        "已核對的一例：審判官戰報攻擊基礎值 110＝建築 50（天穹聯盟戰士 1012）＋符文 21＋光輝建築 39（`shine_troop` 聯盟第 7 級攻擊）；"
        "生命基礎值 1508＝建築 900＋科技 10＋符文 64＋光輝建築 534（第 7 級生命）。建築與光輝兩項與表一致。光輝建築點數是加進單兵基礎值，與兵營基礎值相加，而不是改走 19xx。"
    )
    add("")
    add("百分比來源加總與表頭一致；數量因顯示進位仍推不出唯一整數，維持未驗證。")
    add("")
    add("英雄攜帶士兵上限＝畫面上列出的來源點數相加；其中「等級」＝`hero_level.army_count`（品質 3–5 為 2×等級，品質 6 為 3×等級）。出征上限（1019 等）與容納士兵上限（1018 等）沒有出現在這份攜帶上限清單。戰鬥公式裡的「士兵數量」與這份攜帶上限是否同一整數，維持未驗證。")
    add("")
    add(
        f"和「士兵攻擊百分比」名稱相近的屬性：科技、兵裝、裝飾、領主裝備、英雄天賦、公會科技等大量寫入的 `type=2` 屬性是 10103／10104「"
        f"{attr_label(10103, data.attr_by)}／{attr_label(10104, data.attr_by)}」，以及分營的 13103／14103／15103（生命同理：13104／14104／15104）。"
        f"公式用語仍不能從表寫死只對 10103 一條。10105／10106 的屬性表 `name` 指向「{table_name_label(10105, data.attr_by)}／{table_name_label(10106, data.attr_by)}」，"
        "本抽取沒有來源把數值寫進 10105／10106，不能當成這條百分比欄的候選。"
        f"10003／10004「{attr_label(10003, data.attr_by)}／{attr_label(10004, data.attr_by)}」是 `type=1` 點數，本抽取幾乎沒有來源寫入。10103 與分營條如何疊加，表沒有說明。"
    )
    add("")
    add("## 光輝建築")
    add("")
    add(
        f"官方屬性來源分類 32 的名稱是「{o.categories[32][0]}」，說明是「{o.categories[32][1]}」"
        f"（`hero_detailed_stats_ui_shine`／`_dec`）。介面另有「{o.shine_tip}」（`UI_army_shine_attr_tip`）。"
        "本頁說的光輝士兵數值在 `shine_troop.json`，對到的是兵營建築的 `shine_lv`，不是改走 B 線。"
    )
    add("")
    add("`shine_troop.json` 24 筆：三個種族（1／2／3，對應三座兵營）各 8 級（`shine_lv` 1–8）。同階的攻擊、生命、士氣、戰力、負重三營完全相同。`attr_3` 同樣是 `[10057, 0]`。沒有種族 4（神族）列，也沒有獨立中文名稱鍵。")
    add("")
    add("兵營升級表（以聯盟兵營 125 為例；126／127 結構相同，建築 id 改前綴）：建築 40 級起出現 `shine_para1`；41–44 級 `shine_lv=0`；45 級起 `shine_lv=1`，之後每 5 級加一階，80 級 `shine_lv=8`。`shine_troop.building_id` 正好對上 45、50、55、60、65、70、75、80 級（聯盟為 125045–125080）。此段兵營 `shine_lv` 進度已對 `citybuilding_lvup.json` 與 `citybuilding_lvup_new.json` 的 125／126／127 列核過，兩表在這些列上一致；本頁不把整份建築升級表展開。")
    add("")
    add(tbl["shine"])
    add("")
    add("已鎖定：光輝聯盟 `shine_lv` 7、id 1490019 為攻擊 39、生命 534、士氣 500，戰報把這組點數加進單兵基礎值。")
    add("")
    add(f"另有建築「{o.buildings[169][0]}」（`citybuilding_name_169`），說明是「{o.buildings[169][1]}」。那是另一個建築與科技線，本頁不展開。")
    add("")

    add("## 兵裝")
    add("")
    add(
        f"官方系統名是「{o.skin_system}」（`troop_skin`）。屬性來源分類 33「{o.categories[33][0]}」、34「{o.categories[34][0]}」。"
        f"對應建築是{o.buildings[142][0]}（`citybuilding_name_142`），說明為「{o.buildings[142][1]}」。"
        "升級前置寫在 `troop_skin_level.prebuilding_level`，都是建築 142 的指定等級。"
    )
    add("")
    add("養成說明原文（`info_title_army_troop_skin_content1`）：")
    add("")
    for i, ln in enumerate(o.skin_training, 1):
        add(f"{i}. {re.sub(r'^\\d+\\.', '', ln).strip()}")
    add("")
    add(
        f"資源 17 的名稱是「{o.resources[17]}」（`top_resource_name_17`）。另有道具 1017「{o.honor_item_name}」，說明為「{o.honor_item_desc}」。"
        "榮譽突破表的 `cost_1` 寫的是 `999|17|數量`，沒有寫入 1017；兩種寫法如何對上，表沒有說明，維持未驗證。"
    )
    add("")
    add(
        f"影響力目錄（`influence_level.json`）在「士兵」下有「士兵強化 → {o.skin_system}」；同目錄把三營士兵寫成「"
        f"聯盟士兵／{o.tribe_word}／自然士兵」（此處原文是「部落」不是「部族」）。"
    )
    add("")
    add("### 名錄")
    add("")
    add("`troop_skin_level.json` 4,853 筆，有 23 個 `group`（5301、5302、5401–5407、5501–5514），每組 211 筆、等級 1–50。其中 21 組在突破表與榮譽突破表出現，並可對到道具名稱。`jump.json` 用 `goods_name_*` 對到其中 14 組（5301–5302、5403–5407、5501–5507）；5508–5514 沒有這類跳轉列，但仍有道具名稱、升級、突破與榮譽表。")
    add("")
    add("部分組的突破／榮譽消耗道具 id，與名稱所用的 `goods_name` id 不同（例如熊皮勇士名稱是 2024506，消耗寫 2024543，而後者沒有 `goods_name` 字串）。本頁同時記錄兩種 id，不臆測為何分開。")
    add("")
    add(
        f"另有道具 2024503「{o.gunner_name}」，說明為「用於士兵兵裝解鎖或突破，{o.gunner_clause}」，但沒有對上任何 `group`，也不在 `jump` 的兵裝列。"
        "5401、5402 兩組只有升級表（品質 4，曲線與 5403–5407 完全相同），沒有名稱字串、沒有跳轉、也沒有突破或榮譽列，本頁不編造名稱。"
    )
    add("")
    add(f"`troop_skin_name501` 為「{o.leftover_name}」、`troop_skin_break_desc501` 為「{o.leftover_desc}」，沒有出現在上述 23 個 group 裡，本頁只記有這兩條字串，不把它寫進名錄。")
    add("")
    add("道具說明裡，「可同時被多隊裝載」或「只可同時被一隊裝載」與養成說明第 5 點一致：下列品質 3、4 的具名兵裝寫可多隊；品質 5 的具名兵裝寫只可一隊。")
    add("")
    add(tbl["catalog"])
    add("")
    add("各具名兵裝的道具說明前段（解鎖／突破句之前）照錄於下，不作評價：" + _fronts_md(data))
    add("")
    add("### 升級（`troop_skin_level`）")
    add("")
    add("每組 211 筆：等級 1–16 各 1 列（`level_small=-1`）；17 級起出現 `level_small` 分列，筆數隨等級增加，至 44–49 級各 10 列（`level_small` 0–9）；50 級只有 `level_small=0` 一列。`level_small` 在介面上叫什麼，表沒有名稱，只記欄位。")
    add("")
    add("`unlock_lv` 為 0–6，與兵裝研究所等級前置成對出現（例：1–9 級 `unlock_lv=0`、前置 `[142, 1]`；10–19 級開始要 142 的 10 級；50 級 `unlock_lv=6`、前置 `[142, 50]`）。升級消耗欄是 `exp`（整數），表沒有另寫資源 id；養成說明寫「消耗勳章可以升級兵裝」。")
    add("")
    add("升級屬性按品質帶分成幾組曲線（同品質、同屬性組合的組，1–50 級含 `level_small` 的攻擊／生命／戰力／`exp` 完全相同）：")
    add("")
    add(tbl["upgrade"])
    add("")
    add("5509–5514 的第三項從 1 級就有，收到 50 級為 400。這第三項與突破表裡 5512–5514 的「守城時減傷」（屬性 1000119）不是同一條，不要混讀。")
    add("")
    add("### 突破（`troop_skin_break`）")
    add("")
    add("21 組、每組 7 階（`level` 0–6），共 147 筆。第 0–5 階的 `skin_lv_min`／`skin_lv_max` 依序為 10、20、30、40、45、50，`castle_lv_min` 為 10，消耗為同種兵裝 1／1／2／3／3／3 個。第 6 階 `skin_lv` 仍為 50，`castle_lv_min` 為 −1，`cost` 為空。本頁只記欄位，不把第 6 階寫成「自動升」或其他未見於表的規則。")
    add("")
    add("突破說明取 `troop_skin_break_desc{group}`。部分組另有 `display_num` 字串陣列，對應說明裡的 `{0}`、`{1}`…占位符，本頁照錄該欄，不自行用原值換算去改寫它。要注意：多組在第 5、6 階的 `display_num` 不再隨 `attrList` 增加，或與「原值÷100」不一致（例如盾兵第 4 階起 `display_num` 停在 30／10／20，但 `attrList` 續增；優雅侍者第 6 階 `display_num` 為 42／18／36，與第 5 階的 48／18／36 以及 `attrList` 都不相同）。沒有 `display_num` 的組只記原值。下文「官方說明」是該組文案模板，數字以表為準。")
    add("")
    add(
        f"下列各表「屬性」欄記 `attrList` 原值，屬性名取 `attribute_name_{{id}}`。10188 沒有 `attribute_name_10188`，屬性表 `name` 指向「士兵士氣」，照這一名稱記，並標 id 10188（`type=2`、`show_type=2`）。"
    )
    add("")
    add(
        f"**盾兵 5301。**官方說明：{data.skins[5301].break_desc}。"
        f"屬性為 1052 {attr_label(1052, data.attr_by)}、10103、10104。戰力 {_slash_powers(data.skin_breaks[5301])}。"
    )
    add("")
    add(tbl["br5301"])
    add("")
    for para in _break_prose_md(data):
        add(para)
        add("")
    add(
        f"**{data.skins[5506].name} 5506、{data.skins[5507].name} 5507、{data.skins[5508].name} 5508。**"
        f"三組說明結構相同，只改陣營。5507 原文：{data.skins[5507].break_desc}。5506、5508 把「聯盟」換成「自然」「部族」。沒有 `display_num`。"
        f"戰力 {_slash_powers(data.skin_breaks[5507])}。消耗個數 1／1／2／3／3／3／空。"
    )
    add("")
    add(
        f"分營攻擊／生命與「同營生命額外」對應：5506 為 15103／15104／21028（{attr_label(21028, data.attr_by)}）；"
        "5507 為 13103／13104／21024（聯盟）；5508 為 14103／14104／21026（部族）。消耗 id 分別為 2024556／2024557／2024558。"
    )
    add("")
    add(tbl["br5507"])
    add("")
    add(
        f"**{data.skins[5509].name} 5509、{data.skins[5510].name} 5510、{data.skins[5511].name} 5511。**"
        "說明為：本隊〔陣營〕士兵攻擊提升{0}%，〔陣營〕士兵生命提升{1}%，〔陣營〕逆克制增傷提升{2}%。沒有 `display_num`。"
        f"戰力 {_slash_powers(data.skin_breaks[5509])}。消耗個數 1／1／2／3／3／3／空。"
    )
    add("")
    add("5509：13103／13104／3029，消耗 2024559。5510：14103／14104／4031，消耗 2024560。5511：15103／15104／5027，消耗 2024561。")
    add("")
    add(tbl["br5509"])
    add("")
    add(
        f"**{data.skins[5512].name} 5512、{data.skins[5513].name} 5513、{data.skins[5514].name} 5514。**"
        "說明：本隊〔陣營〕士兵攻擊提升{0}%，〔陣營〕士兵生命提升{1}%，守城時減傷提升{2}%。屬性第三項是 1000119 "
        f"{attr_label(1000119, data.attr_by)}"
        "（不是升級表上的 3019／4019／5019）。沒有 `display_num`。戰力與消耗個數與山羊騎士組相同。"
    )
    add("")
    add("5512：13103／13104，消耗 2024562。5513：14103／14104，消耗 2024563。5514：15103／15104，消耗 2024564。")
    add("")
    add(tbl["br5512"])
    add("")
    add("### 榮譽突破（`troop_skin_honor_break`）")
    add("")
    add(
        f"21 組、每組 150 級（`level` 1–150），共 3,150 筆。介面文案有「{o.honor_forbid}」「{o.honor_unlock}」。"
        "表上的 `quality` 在前 99 級等於該兵裝升級表的品質（3／4／5），100–150 級升一檔（4／5／6）。"
        "`i_attr`（表欄 `i_attrList`）只出現在升檔後的 100–150 級，同一組這 51 級的 `i_attr` 固定不變。"
        "`attr_1` 每級遞增，多數組是士兵生命（10104）或對應分營士兵生命（13104／14104／15104）。"
    )
    add("")
    add(
        f"消耗：`cost_1` 為 `999|17|數量`（資源 17「{o.resources[17]}」），`cost_2` 為同種兵裝。"
        "品質 3 組（盾兵、騎兵）勳章 12,500、兵裝 25；品質 4 組多數是勳章 25,000、兵裝 5（鼓號隊"
        "在品質 4 的 2–49 級勳章為 12,500，第 1 級與 50–99 級及品質 5 仍為 25,000）；品質 5 組在 1–99 級是勳章 50,000、兵裝 1，100–150 級兵裝改為 2。第 150 級 `cost` 為空。"
    )
    add("")
    add("`attr_1` 與戰力（該品質段首尾）：")
    add("")
    add(tbl["honor_attr"])
    add("")
    add("升檔後固定 `i_attr`（100–150 級；寫成 0 的分項也照錄）。5509–5511 另有 `attr_2`（逆克制增傷 100）；5512–5514 的 `attr_2` 是 3019／4019／5019 各 100，與 `i_attr` 裡的 1000119 不是同一條：")
    add("")
    add(tbl["honor_i"])
    add("")
    add("### 已鎖定的聯盟兵裝面板對照")
    add("")
    add("以下只鎖定這一組面板數字，不推廣到其他兵裝或其他 `show_type=2` 屬性。")
    add("")
    add(
        f"聯盟兵裝突破第 6 階（group 5507，{data.skins[5507].name}）的原值：13103＝2800、13104＝5600、10188＝350、1300106＝350、21024＝1400。"
        "榮譽突破品質 6 的固定 `i_attr`：21024＝280、10188＝80、1300106＝80（13103／13104 在此列為 0）。兩者相加後，對上面板："
    )
    add("")
    add("- 士兵士氣／集結士氣 4.30%（350＋80）")
    add(f"- {attr_label(21024, data.attr_by)} 16.80%（1400＋280）")
    add("- 聯盟士兵攻擊 28%（2800）")
    add("- 聯盟士兵生命裡，標成「兵裝突破」的那一部分 56%（5600）")
    add("")
    add("集結士氣官方兵裝文案有「不可疊加」。屬性 1300106 的 `max=5000` 且 `is_max_show=1`，對上畫面括號「最大 50%」。")
    add("")
    add("榮譽表 `attr_1` 在聯盟士兵生命還有約 10%–15%（品質 6 時 13104 為 1000–1500），但面板「兵裝突破」生命正好是 56%，這筆沒有出現在該行，維持未驗證。")
    add("")
    add("### 行軍造型（面板有提到，不是本篇主體）")
    add("")
    add(
        f"同一張聯盟士兵生命面板，另 20% 標示來自行軍造型。屬性來源分類 50 的名稱就是「{o.march_name}」，說明為「{o.march_desc}」。"
        "要對上這 20%，需要唯一的 `13104|2000` 表列；本抽取在行軍／世界造型相關表裡沒有 13104。不要把這 20% 強行對成："
    )
    add("")
    add(f"- {o.shield_name}（那是建築 121「{o.shield_desc}」，不是一筆 `13104|2000` 或 `10104|2000` 的行軍造型列）")
    add("- 裝飾物 DIY 裡恰好寫了 `13104|2000` 的列（`citybuilding_DIY_property` 有多筆 13104，其中 11150107、15550304 的值是 2000，來源分類是裝飾物，不是行軍造型）")
    add("")
    add("因此：面板有這 20%，表上沒有唯一對得上的行軍造型列，維持未驗證。行軍造型目錄本身見城堡／世界造型相關篇，不在本篇展開；也不把已發佈的 [造型總表](skins.html) 當成行軍造型名錄（那是英雄造型）。")
    add("")
    add("## 士氣")
    add("")
    add("官方介面字串已經說明規則，但沒有把數字寫進對照表：")
    add("")
    add(f"- `morale_002`：{official_text('morale_002')}")
    add(f"- `morale_003`：{official_text('morale_003')}")
    add(f"- `morale_004`：{official_text('morale_004')}")
    add(f"- `morale_005`／`006`：{official_text('morale_005')}／{official_text('morale_006')}")
    add("")
    add("因此還不能寫出「x 倍士氣對應 y 倍傷害」的數列。戰報「士氣影響」的工作假設在戰鬥公式的結算草稿，本頁不把那套假設抄進來當已驗證公式。官方另有傷害上限「最多 300%」的說法，與戰力係數上限 2.0 不是同一條。")
    add("")
    add(
        f"與士氣有關的屬性：88 {attr_label(88, data.attr_by)}、10088 {attr_label(10088, data.attr_by)}、16000 {attr_label(16000, data.attr_by)}"
        f"（皆 `type=1`）；16001 {attr_label(16001, data.attr_by)}（`type=2`）；另有 1136 {attr_label(1136, data.attr_by)}、1137 {attr_label(1137, data.attr_by)}、"
        f"1130 {attr_label(1130, data.attr_by)}、1131 {attr_label(1131, data.attr_by)}；以及兵裝用的 10188（名稱同「士兵士氣」，`type=2`）、"
        f"1300106 {attr_label(1300106, data.attr_by)}、1300108 {attr_label(1300108, data.attr_by)}。16001 如何疊進上述 {{1}} 倍傷害，表沒有說明。"
    )
    add("")
    add("士兵表上，線 A 的 `troop.morale` 為 205–800；光輝士兵為 100、200、300、350、400、450、500、550。線 B 的 `morale` 為 0。`switch_troop_morale` 見上文戰鬥類型一節。關卡技能 `troop_morale_skill_01` 不可拿來當通用 PvP 士氣表。")
    add("")
    add("## 部隊外觀編號（不是兵裝）")
    add("")
    add("`troop_skin.json` 155 筆，欄位只有 `id`、`skin_id`、`skill_ID`、`spine_skin`，這是士兵模型／外觀編號，不是上文的兵裝圖鑑。`troop.json` 的 `skin_ID` 指向這裡（例如 1001 與 1901 都是 10011–10014）。`skill_ID` 只有 1001、1002、1003、1004 四種。本頁不把這張表當成兵裝名錄，也不展開模型資源。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 士兵捐贈上限表（`troop_donate.json` 243 筆，按種族與兵營等級給 `limit`／賽季與伺服器標記上限）。")
    add("- 光輝研究所與光輝科技的研究線。")
    add("- 行軍造型、城堡／世界造型、裝飾物 DIY 的完整名錄（只在士兵生命面板提到行軍造型 20% 時，說明沒有唯一表列）。")
    add("- 訓練時間、治療時間、`lvup_time` 的單位換算，以及實際訓練／治療介面是否讀線 B 的消耗欄。")
    add("- 10–12 級士兵（傳奇、天御、天穹）在 `building_id=-1` 之後的確切解鎖條件。")
    add("- `season_get`（`2|999|20|{level}`）與資源 20 的含義。")
    add("- `army_type` `[1, 2, 3]`、`map_soldier_scale`、屬性 10057（值為 0）的實際作用。")
    add("- 英雄攻擊／生命轉化率是否作用於士兵傷害。")
    add("- 士氣壓制的 x→y 數列、16001 的疊加方式，以及戰報「士氣影響」是否等於實際傷害倍率。")
    add("- 兵裝 `exp` 與勳章、榮譽道具 1017 與資源 17 的兌換關係；`level_small`、突破第 6 階空消耗在客戶端的具體顯示。")
    add(f"- {o.gunner_name}（2024503）以及只有升級表的 5401、5402 在客戶端是否出現。")
    add("- 士兵與英雄技能、站位、陣容的搭配模擬，以及強弱評定。")
    add("")
    add("## 資料說明")
    add("")
    add(
        "資料出自遊戲資料表與官方字串（troop、shine_troop、troop_skin_level、troop_skin_break、troop_skin_honor_break、jump、troop_skin、fight_type、attribute、attr_category、top_resource、strings_zh.json），"
        f"資料截至 {TROOP_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {TROOP_DATA_PACK}（759 張表），打包時戳 {TROOP_DATA_PACKED}（香港時間）。"
        "顯示規則依攻略手冊「士兵圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。這不是官方 wiki。"
    )
    add("")
    return "\n".join(lines)
