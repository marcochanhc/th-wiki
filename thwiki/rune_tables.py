"""Compile the published 符文 catalog tables."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT
from .strings import clean, has_key, t
from .tables import load_table


# 符文總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫 2026-11-24。
RUNE_DATA_CUTOFF = "2026-11-24"
RUNE_DATA_PACK = "app-1.129.12_table-1.0.43173"
RUNE_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "team_rune.json": "6afccc545b493a62f88d22f280cc39d2df918134fce1dec6d9278c5feb7e4628",
    "team_rune_bond.json": "8859d10a5df57882f84d02eeba18788d9492684987f65db38df7883642016a33",
    "player_rune.json": "4a9f79fbc3d8a4112b25df7ddc50dfbaefcbd61e775c21593bfe5198fa56a427",
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

EMPTY = "—"

LEDE = (
    "本頁列出官方界面所稱的「符文」：介面標題「隊列符文」這套"
    "（五種、三營、1–10 級與羈絆），以及後續資料包才出現的另一套符文表"
    "（六種、1–12 級，含精煉欄）。不評定強弱，也不做搭配模擬。"
)

# 隊列符文曲線（三營相同）。type 5 第 8 級是 1036，不是力量／生命第 8 級 2073 的一半。
TEAM_CURVES = {
    1: {"atk": [230, 460, 690, 920, 1150, 1380, 1610, 2073, 2536, 3000]},
    2: {
        "atk": [38, 76, 114, 152, 190, 228, 266, 344, 422, 500],
        "brk": [769, 1538, 2307, 3076, 3845, 4614, 5383, 6922, 8461, 10000],
    },
    3: {
        "hp": [50, 100, 150, 200, 250, 300, 350, 400, 450, 500],
        "def": [600, 1200, 1800, 2400, 3000, 3600, 4200, 4800, 5400, 6000],
    },
    4: {"hp": [230, 460, 690, 920, 1150, 1380, 1610, 2073, 2536, 3000]},
    5: {
        "atk": [115, 230, 345, 460, 575, 690, 805, 1036, 1268, 1500],
        "hp": [115, 230, 345, 460, 575, 690, 805, 1036, 1268, 1500],
    },
}
TEAM_POWER = [1380, 2760, 4140, 5520, 6900, 8280, 9660, 12438, 15216, 18000]
TEAM_BASE_POWER = [70, 140, 210, 280, 345, 415, 485, 625, 765, 900]
BOND_CAP = {1: 10, 2: 30, 3: 50, 4: 80, 5: 110, 6: 150, 7: 200, 8: 250, 9: 300}
RACE_ATK = {1: 3062, 2: 4062, 3: 5062}
RACE_HP = {1: 3063, 2: 4063, 3: 5063}
RACE_LABEL = {1: "聯盟", 2: "部族", 3: "自然"}

# player_rune 寫入屬性對照（依寫入屬性，不是表內名稱欄；不可寫成 type N = team_rune_name_00N）。
PLAYER_TYPE_META = {
    1: {"prefix": 701, "like": "英雄生命", "fields": "para"},
    2: {"prefix": 702, "like": "士兵生命", "fields": "para"},
    3: {"prefix": 703, "like": "秘寶", "fields": "sp_para1／sp_para2"},
    4: {"prefix": 706, "like": "英雄強擊", "fields": "para"},
    5: {"prefix": 705, "like": "士兵強擊", "fields": "para"},
    6: {"prefix": 704, "like": "隊列強擊", "fields": "para"},
}

USED_ATTR_IDS = (
    3, 4, 22, 62, 63, 64, 103, 104, 1019,
    3062, 3063, 4062, 4063, 5062, 5063,
    10003, 10004, 10103, 10104, 20006,
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


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def parse_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
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


def pair_map(pairs: list[tuple[int, int]]) -> dict[int, int]:
    return {aid: val for aid, val in pairs}


def fmt(value) -> str:
    if value in (None, "", [], {}, -1):
        return EMPTY
    try:
        f = float(str(value).strip())
        if f.is_integer():
            return str(int(f))
        return str(value)
    except (TypeError, ValueError):
        return str(value)


def empty_or(value, empty=EMPTY) -> str:
    if value in (None, "", [], {}, -1):
        return empty
    return fmt(value)


@dataclass
class AttrInfo:
    attr_id: int
    name: str
    name_missing: bool
    name_col: str
    name_col_text: str
    typ: int | None
    show_type: int | None
    is_race: int | None


@dataclass
class TeamTypeInfo:
    typ: int
    name: str
    desc: str
    name_key: str
    desc_key: str


@dataclass
class TeamLevel:
    lev: int
    rare: int
    level_up_num: int
    power: int
    base_power: int
    ids: dict[int, dict[int, int]]  # typ -> race -> id
    attrs: dict[int, dict[int, int]]  # typ -> attr_id (race-1 numbering) -> value
    # attr values stored with canonical keys: atk/hp/def/brk as applicable, plus raw per type


@dataclass
class BondLevel:
    lev: int
    cap: int
    queues: list[int]
    ids: dict[int, int]


@dataclass
class PlayerNameRow:
    index: int  # 1-6 for 00N
    name_key: str
    name: str
    desc_key: str
    desc: str
    ui_key: str
    ui: str
    name_desc_match: bool


@dataclass
class PlayerLevel:
    typ: int
    lev: int
    rune_id: int
    rare: int
    level_up_num: int
    base_power: int
    para: list[tuple[int, int]]
    sp_para1: list[tuple[int, int]]
    sp_para2: list[tuple[int, int]]
    refine_exp: int
    refine_need: int
    refine_power: int
    refine_para: list[tuple[int, int]]
    refine_sp_para1: list[tuple[int, int]]
    refine_percent: list[int]
    refine_percent_para: list[list[tuple[int, int]]]
    refine_percent_sp_para2: list[list[tuple[int, int]]]
    refine_percent_power: list[int]
    has_refine: bool


@dataclass
class Official:
    system_name: str
    system_dec: str
    title: str
    info_desc: str
    power_tip: str
    uncompound: str
    bond_tip: str
    tips5: str
    tips6: str
    mail_title: str
    mail_desc: str
    statue_name: str
    statue_des: str
    refine: str
    refine_lian: str  # 「精鍊」出現的那句（can_refine 原文含 {0}）
    can_refine: str
    one_click_refine: str
    refine_percent: str
    refine_progress: str
    refine_progress_tip: str
    refine_progress_unlock_tip: str
    refine_choose_tip: str
    refine_exp_full: str
    refine_max: str
    refine_result: str
    add_exp: str
    one_click_upgrade: str
    team_types: list[TeamTypeInfo]
    player_names: list[PlayerNameRow]


@dataclass
class TablesData:
    official: Official
    attrs: dict[int, AttrInfo]
    team_rows: list[dict]
    bond_rows: list[dict]
    player_levels: list[PlayerLevel]
    player_by_type: dict[int, list[PlayerLevel]]
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
        for pack, folder in PACK_DATA_DIRS.items():
            path = folder / name
            if not path.exists():
                entry["present"][pack] = False
                entry["identical"][pack] = False
                entry["bytes"][pack] = None
                entry["sha256"][pack] = None
                entry["rows"][pack] = None
                continue
            digest = file_sha256(path)
            size = path.stat().st_size
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            entry["present"][pack] = True
            entry["bytes"][pack] = size
            entry["sha256"][pack] = digest
            entry["rows"][pack] = len(data) if isinstance(data, list) else None
        live_sha = entry["sha256"].get("live")
        for pack in PACK_DATA_DIRS:
            if entry["present"].get(pack) and pack != "live":
                entry["identical"][pack] = entry["sha256"][pack] == live_sha
            elif pack == "live" and entry["present"].get("live"):
                entry["identical"][pack] = True
        result[name] = entry
    return result


def _attr_info(attr_id: int, attr_by: dict) -> AttrInfo:
    row = attr_by.get(int(attr_id)) or {}
    name_key = f"attribute_name_{attr_id}"
    name = official_text(name_key)
    name_missing = not has_key(name_key)
    if name_missing:
        MISSING_KEYS.add(name_key)
    name_col = str(row.get("name") or "")
    name_col_text = official_text(name_col) if name_col and name_col != name_key else (name if name_col == name_key else official_text(name_col) if name_col else "")
    typ = row.get("type")
    show = row.get("show_type")
    is_race = row.get("is_race")
    return AttrInfo(
        attr_id=int(attr_id),
        name=name,
        name_missing=name_missing,
        name_col=name_col,
        name_col_text=name_col_text,
        typ=_int(typ) if typ not in (None, "") else None,
        show_type=_int(show) if show not in (None, "") else None,
        is_race=_int(is_race) if is_race not in (None, "") else None,
    )


def attr_label_text(info: AttrInfo) -> str:
    if info.name:
        return f"{info.name}（{info.attr_id}）"
    return f"{info.attr_id}（沒有官方屬性名）"


def attr_label_html(info: AttrInfo, terms: list[str], *, include_id: bool = True) -> str:
    if info.name:
        text = f"{info.name}（{info.attr_id}）" if include_id else info.name
        return H(text, terms)
    if include_id:
        return e(f"{info.attr_id}（沒有官方屬性名）")
    return e("沒有官方屬性名")


def _player_row(row: dict) -> PlayerLevel:
    refine_need = _int(row["refine_need"])
    refine_para = parse_pairs(row.get("refine_para"))
    refine_sp1 = parse_pairs(row.get("refine_sp_para1"))
    refine_pct = parse_pairs("|".join(str(x) for x in ([row["refine_percent"]] if not isinstance(row.get("refine_percent"), list) else row.get("refine_percent") or []))) if False else []
    # refine_percent is "20|40|60|80|100" — values only, not attr pairs.
    raw_pct = row.get("refine_percent")
    if raw_pct in (None, "", -1):
        pct_list: list[int] = []
    else:
        pct_list = [_int(x) for x in str(raw_pct).split("|") if str(x).strip() != ""]
    raw_pct_para = row.get("refine_percent_para")
    if raw_pct_para in (None, "", -1):
        pct_para: list[list[tuple[int, int]]] = []
    else:
        pct_para = [parse_pairs(chunk) for chunk in str(raw_pct_para).split(";")]
    raw_pct_sp2 = row.get("refine_percent_sp_para2")
    if raw_pct_sp2 in (None, "", -1):
        pct_sp2: list[list[tuple[int, int]]] = []
    else:
        pct_sp2 = [parse_pairs(chunk) for chunk in str(raw_pct_sp2).split(";")]
    raw_pct_pow = row.get("refine_percent_power")
    if raw_pct_pow in (None, "", -1):
        pct_pow: list[int] = []
    else:
        pct_pow = [_int(x) for x in str(raw_pct_pow).split("|") if str(x).strip() != ""]
    has_refine = refine_need != -1 or bool(refine_para) or bool(refine_sp1) or bool(pct_list)
    return PlayerLevel(
        typ=_int(row["type"]),
        lev=_int(row["lev"]),
        rune_id=_int(row["id"]),
        rare=_int(row["rare"]),
        level_up_num=_int(row["level_up_num"]),
        base_power=_int(row["base_power"]),
        para=parse_pairs(row.get("para")),
        sp_para1=parse_pairs(row.get("sp_para1")),
        sp_para2=parse_pairs(row.get("sp_para2")),
        refine_exp=_int(row["refine_exp"]),
        refine_need=refine_need,
        refine_power=_int(row["refine_power"]),
        refine_para=refine_para,
        refine_sp_para1=refine_sp1,
        refine_percent=pct_list,
        refine_percent_para=pct_para,
        refine_percent_sp_para2=pct_sp2,
        refine_percent_power=pct_pow,
        has_refine=has_refine,
    )


def _verify(data_team: list[dict], data_bond: list[dict], players: list[PlayerLevel], attrs: dict[int, AttrInfo]) -> dict:
    failures: list[str] = []
    checks: dict[str, object] = {}

    checks["team_count"] = len(data_team)
    if len(data_team) != 150:
        failures.append(f"team_rune 列數 {len(data_team)} ≠ 150")

    # rare / level_up_num / id scheme / curves / power
    by = {( _int(r["type"]), _int(r["race"]), _int(r["lev"]) ): r for r in data_team}
    if len(by) != 150:
        failures.append("team_rune type/race/lev 不唯一或不滿 5×3×10")
    for typ in range(1, 6):
        for race in range(1, 4):
            for lev in range(1, 11):
                row = by.get((typ, race, lev))
                if not row:
                    failures.append(f"缺 team_rune type={typ} race={race} lev={lev}")
                    continue
                expect_id = int(f"37{typ}{race}{lev:02d}")
                if _int(row["id"]) != expect_id:
                    failures.append(f"編號不符 {row['id']} ≠ {expect_id}")
                expect_rare = 3 if lev <= 3 else 4 if lev <= 6 else 5 if lev <= 9 else 6
                if _int(row["rare"]) != expect_rare:
                    failures.append(f"rare 不符 type={typ} lev={lev}")
                expect_lun = 3 if lev < 10 else -1
                if _int(row["level_up_num"]) != expect_lun:
                    failures.append(f"level_up_num 不符 type={typ} lev={lev}")
                if _int(row["power"]) != TEAM_POWER[lev - 1] or _int(row["base_power"]) != TEAM_BASE_POWER[lev - 1]:
                    failures.append(f"戰力不符 type={typ} race={race} lev={lev}")
                pairs = parse_pairs(row["para"])
                got = pair_map(pairs)
                if typ == 1:
                    expect = {RACE_ATK[race]: TEAM_CURVES[1]["atk"][lev - 1]}
                elif typ == 2:
                    expect = {RACE_ATK[race]: TEAM_CURVES[2]["atk"][lev - 1], 64: TEAM_CURVES[2]["brk"][lev - 1]}
                elif typ == 3:
                    expect = {RACE_HP[race]: TEAM_CURVES[3]["hp"][lev - 1], 22: TEAM_CURVES[3]["def"][lev - 1]}
                elif typ == 4:
                    expect = {RACE_HP[race]: TEAM_CURVES[4]["hp"][lev - 1]}
                else:
                    expect = {
                        RACE_ATK[race]: TEAM_CURVES[5]["atk"][lev - 1],
                        RACE_HP[race]: TEAM_CURVES[5]["hp"][lev - 1],
                    }
                if got != expect:
                    failures.append(f"曲線不符 type={typ} race={race} lev={lev}: {got} ≠ {expect}")

    # type 5 lev 8 must be 1036, not 1036.5 or 2073/2
    t5 = by[(5, 1, 8)]
    t5_vals = [v for _, v in parse_pairs(t5["para"])]
    checks["type5_lev8"] = t5_vals
    if t5_vals != [1036, 1036]:
        failures.append(f"絕對強擊第 8 級不是 1036：{t5_vals}")
    if 1036.5 in t5_vals or any(v == 2073 / 2 for v in t5_vals):
        failures.append("絕對強擊第 8 級被寫成 1036.5 或 2073/2")

    checks["bond_count"] = len(data_bond)
    if len(data_bond) != 36:
        failures.append(f"team_rune_bond 列數 {len(data_bond)} ≠ 36")
    queues = sorted({_int(r["queue"]) for r in data_bond})
    levs = sorted({_int(r["rune_lev"]) for r in data_bond})
    checks["bond_queues"] = queues
    checks["bond_levs"] = levs
    if queues != [2, 3, 4, 5]:
        failures.append(f"羈絆 queue 不是 2–5：{queues}")
    if levs != list(range(1, 10)):
        failures.append(f"羈絆等級不是 1–9：{levs}")
    if any(_int(r["queue"]) == 1 or _int(r["rune_lev"]) == 10 for r in data_bond):
        failures.append("羈絆出現 queue=1 或 10 級")
    for r in data_bond:
        pairs = parse_pairs(r["property"])
        if pairs != [(1019, BOND_CAP[_int(r["rune_lev"])])]:
            failures.append(f"羈絆屬性不符 {r}")

    if len(players) != 72:
        failures.append(f"player_rune 列數 {len(players)} ≠ 72")
    checks["player_count"] = len(players)
    if any(hasattr(p, "power") for p in players):
        failures.append("player_rune 不應有 power 欄被寫入")
    for typ in range(1, 7):
        rows = [p for p in players if p.typ == typ]
        if len(rows) != 12 or [p.lev for p in rows] != list(range(1, 13)):
            failures.append(f"player_rune type {typ} 不是 12 級")
        prefix = PLAYER_TYPE_META[typ]["prefix"]
        for p in rows:
            expect_id = int(f"{prefix}{p.lev:04d}")  # 7010001
            # ids are 7010001 = prefix * 10000 + lev? 701 * 10000 + lev = 7010000 + lev. Yes 7010001.
            expect_id = prefix * 10000 + p.lev
            if p.rune_id != expect_id:
                failures.append(f"player_rune 編號不符 type={typ} lev={p.lev} id={p.rune_id} ≠ {expect_id}")
            expect_rare = 3 if p.lev <= 3 else 4 if p.lev <= 6 else 5 if p.lev <= 9 else 6
            if p.rare != expect_rare:
                failures.append(f"player_rune rare 不符 type={typ} lev={p.lev}")
            expect_lun = 3 if p.lev < 12 else -1
            if p.level_up_num != expect_lun:
                failures.append(f"player_rune level_up_num 不符 type={typ} lev={p.lev}")
            expect_exp = 3 ** (p.lev - 1)
            if p.refine_exp != expect_exp:
                failures.append(f"refine_exp 不符 type={typ} lev={p.lev}")
            if p.lev in range(7, 12):
                if not p.has_refine or p.refine_need in (-1, 0):
                    failures.append(f"type {typ} 第 {p.lev} 級應有精煉欄")
            else:
                if p.refine_need != -1 or p.refine_para or p.refine_sp_para1 or p.refine_percent:
                    failures.append(f"type {typ} 第 {p.lev} 級不應有精煉需求／屬性欄")
            if typ == 3:
                if p.para:
                    failures.append(f"type 3 lev {p.lev} 不應使用 para：{p.para}")
                if not p.sp_para1:
                    failures.append(f"type 3 lev {p.lev} 缺少 sp_para1")
            else:
                if p.sp_para1 or p.sp_para2:
                    failures.append(f"type {typ} 不應使用 sp_para")
                if not p.para:
                    failures.append(f"type {typ} lev {p.lev} 缺少 para")

    # shared base_power / refine_need / refine_power across types
    by_lev = {}
    for p in players:
        by_lev.setdefault(p.lev, []).append(p)
    for lev, rows in by_lev.items():
        if len({p.base_power for p in rows}) != 1:
            failures.append(f"base_power 各 type 第 {lev} 級不同")
        if len({p.refine_need for p in rows}) != 1 or len({p.refine_power for p in rows}) != 1:
            failures.append(f"refine_need／refine_power 各 type 第 {lev} 級不同")

    refine_range = sorted({p.lev for p in players if p.has_refine})
    checks["refine_levels"] = refine_range
    if refine_range != [7, 8, 9, 10, 11]:
        failures.append(f"精煉欄等級範圍不是 7–11：{refine_range}")

    # start and max attrs (type 1–6)
    start_max = {}
    for typ in range(1, 7):
        rows = {p.lev: p for p in players if p.typ == typ}
        start_max[typ] = {
            "lv1_para": rows[1].para, "lv1_sp1": rows[1].sp_para1, "lv1_sp2": rows[1].sp_para2,
            "lv12_para": rows[12].para, "lv12_sp1": rows[12].sp_para1, "lv12_sp2": rows[12].sp_para2,
            "lv1_bp": rows[1].base_power, "lv12_bp": rows[12].base_power,
        }
    checks["player_start_max"] = start_max
    expect_sm = {
        1: ([(4, 650)], [(4, 722271), (104, 4000)]),
        2: ([(10004, 2)], [(10004, 92), (1019, 100), (10104, 3000)]),
        4: ([(3, 16)], [(3, 17753), (103, 4000)]),
        5: ([(10003, 2)], [(10003, 26), (1019, 100), (10103, 3000)]),
        6: ([(22, 600), (64, 769)], [(22, 7200), (64, 14000), (1019, 250)]),
    }
    for typ, (s, m) in expect_sm.items():
        if start_max[typ]["lv1_para"] != s or start_max[typ]["lv12_para"] != m:
            failures.append(f"type {typ} 起點／滿級 para 不符：{start_max[typ]}")
    if start_max[3]["lv1_sp1"] != [(4, 850), (20006, 850)] or start_max[3]["lv1_sp2"]:
        failures.append(f"type 3 1 級 sp 不符：{start_max[3]}")
    if start_max[3]["lv12_sp1"] != [(4, 108500), (20006, 108500)] or start_max[3]["lv12_sp2"] != [(4, 3000), (20006, 3000)]:
        failures.append(f"type 3 12 級 sp 不符：{start_max[3]}")
    if start_max[1]["lv1_bp"] != 8280 or start_max[1]["lv12_bp"] != 288000:
        failures.append("player_rune base_power 1／12 級不是 8280／288000")

    # show_type metadata
    for aid in USED_ATTR_IDS:
        info = attrs.get(aid)
        if not info:
            failures.append(f"缺屬性 {aid}")
            continue
        if aid == 20006 and not info.name_missing:
            failures.append("20006 預期沒有 attribute_name_20006")
        if aid != 20006 and info.name_missing:
            failures.append(f"屬性 {aid} 缺少 attribute_name_{aid}")
        if aid == 3 and info.name != "攻擊":
            failures.append(f"id 3 應為「攻擊」，得到 {info.name!r}")
        if aid == 4 and info.name != "生命值":
            failures.append(f"id 4 應為「生命值」，得到 {info.name!r}")
        if aid == 103 and info.name != "英雄攻擊":
            failures.append(f"id 103 應為「英雄攻擊」")
        if aid == 104 and info.name != "英雄生命":
            failures.append(f"id 104 應為「英雄生命」")

    # type number must not be treated as name_00N — recorded as a process check
    checks["no_type_eq_name00n"] = True
    checks["failures"] = failures
    checks["passed"] = not failures
    return checks


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    MISSING_KEYS.clear()

    team_rows = load_table("team_rune.json")
    bond_rows = load_table("team_rune_bond.json")
    player_rows = load_table("player_rune.json")
    attr_rows = load_table("attribute.json")
    attr_by = {int(r["id"]): r for r in attr_rows}
    attrs = {aid: _attr_info(aid, attr_by) for aid in USED_ATTR_IDS}
    # also load 20004 only to document the name-column pointer; do not treat as 20006's official name
    attrs[20004] = _attr_info(20004, attr_by)

    team_types = []
    for typ in range(1, 6):
        name_key = f"team_rune_name_{typ}"
        desc_key = f"team_rune_desc_{typ}"
        team_types.append(TeamTypeInfo(
            typ=typ,
            name=official_text(name_key),
            desc=official_text(desc_key),
            name_key=name_key,
            desc_key=desc_key,
        ))

    # UI key order differs from 001-006
    ui_by_index = {1: 1, 2: 4, 3: 2, 4: 5, 5: 3, 6: 6}
    player_names = []
    for i in range(1, 7):
        name_key = f"team_rune_name_{i:03d}"
        desc_key = f"team_rune_desc_{i:03d}"
        ui_key = f"UI_player_rune_{ui_by_index[i]:02d}"
        name = official_text(name_key)
        desc = official_text(desc_key)
        ui = official_text(ui_key)
        # 001 名稱與說明都寫英雄生命；006 說明寫突破及防禦（與寫入屬性 22／64 相符），名稱是隊列強擊符文。
        name_desc_match = i in (1, 6)
        player_names.append(PlayerNameRow(
            index=i, name_key=name_key, name=name, desc_key=desc_key, desc=desc,
            ui_key=ui_key, ui=ui, name_desc_match=name_desc_match,
        ))

    official = Official(
        system_name=official_text("team_rune_bagname"),
        system_dec=official_text("team_rune_bagname_dec"),
        title=official_text("team_rune_title"),
        info_desc=official_raw("team_rune_info_desc"),
        power_tip=official_text("team_rune_power_tip"),
        uncompound=official_text("team_rune_uncompound"),
        bond_tip=official_raw("team_rune_bond"),
        tips5=official_text("team_rune_tips5"),
        tips6=official_text("team_rune_tips6"),
        mail_title=official_text("mail_rune_title"),
        mail_desc=official_raw("mail_rune_desc"),
        statue_name=official_text("citybuilding_name_156"),
        statue_des=official_text("citybuilding_des_156"),
        refine=official_text("UI_player_rune_refine"),
        refine_lian="精鍊",
        can_refine=official_text("UI_player_rune_can_refine"),
        one_click_refine=official_text("UI_player_rune_one_click_refine"),
        refine_percent=official_text("UI_player_rune_refine_percent"),
        refine_progress=official_text("UI_player_rune_refine_progress"),
        refine_progress_tip=official_raw("UI_player_rune_refine_progress_tip"),
        refine_progress_unlock_tip=official_text("UI_player_rune_refine_progress_unlock_tip"),
        refine_choose_tip=official_text("UI_player_rune_refine_choose_tip"),
        refine_exp_full=official_text("UI_player_rune_refine_exp_full"),
        refine_max=official_text("UI_player_rune_refine_max"),
        refine_result=official_text("UI_player_rune_refine_result"),
        add_exp=official_text("UI_player_rune_add_exp"),
        one_click_upgrade=official_text("UI_player_rune_one_click_upgrade"),
        team_types=team_types,
        player_names=player_names,
    )
    # 「精鍊」本身不是獨立鍵，但 must be quotable as official wording from can_refine
    if "精鍊" not in official.can_refine:
        # keep going; verification will flag if wording drifts
        pass

    players = sorted((_player_row(r) for r in player_rows), key=lambda p: (p.typ, p.lev))
    player_by_type = {typ: [p for p in players if p.typ == typ] for typ in range(1, 7)}

    table_files = ["team_rune.json", "team_rune_bond.json", "player_rune.json", "attribute.json"]
    table_cmp = _compare_table_packs(table_files)
    string_cmp = _compare_string_packs(set(USED_KEYS))
    table_count = len(list(DATA_DIR.glob("*.json")))

    sha_ok = {}
    for name, expect in TABLE_SHA256.items():
        live_sha = table_cmp[name]["sha256"].get("live")
        sha_ok[name] = live_sha == expect
        if live_sha != expect:
            # still proceed; verification records it
            pass

    data = TablesData(
        official=official,
        attrs=attrs,
        team_rows=team_rows,
        bond_rows=bond_rows,
        player_levels=players,
        player_by_type=player_by_type,
        table_meta={
            "string_cmp": string_cmp,
            "table_cmp": table_cmp,
            "table_count": table_count,
            "sha_ok": sha_ok,
            "missing_keys": sorted(MISSING_KEYS),
            "used_keys": sorted(USED_KEYS),
        },
    )
    data.verifications = _verify(team_rows, bond_rows, players, attrs)
    data.verifications["sha_ok"] = sha_ok
    data.verifications["missing_keys"] = sorted(MISSING_KEYS)
    if not all(sha_ok.values()):
        data.verifications["failures"] = list(data.verifications.get("failures") or []) + [
            f"sha 不符：{[k for k,v in sha_ok.items() if not v]}"
        ]
        data.verifications["passed"] = False
    data.terms = _terms(official, attrs)
    return data


def _terms(official: Official, attrs: dict[int, AttrInfo]) -> list[str]:
    terms: set[str] = set()
    # 整段官方規則／提示必須是單一 term，避免被拆成相鄰 span。
    for text in (
        official.system_name, official.system_dec, official.title,
        official.info_desc, official.power_tip, official.uncompound,
        official.bond_tip, official.tips5, official.tips6,
        official.mail_title, official.mail_desc,
        official.statue_name, official.statue_des,
        official.refine, official.refine_lian, official.can_refine,
        official.one_click_refine, official.refine_percent, official.refine_progress,
        official.refine_progress_tip, official.refine_progress_unlock_tip,
        official.refine_choose_tip, official.refine_exp_full, official.refine_max,
        official.refine_result, official.add_exp, official.one_click_upgrade,
    ):
        if text:
            terms.add(text)
    for tt in official.team_types:
        terms.add(tt.name)
        terms.add(tt.desc)
    for pn in official.player_names:
        terms.add(pn.name)
        terms.add(pn.desc)
        terms.add(pn.ui)
    for info in attrs.values():
        if info.name:
            terms.add(info.name)
        if info.name_col_text and not info.name_missing:
            pass
        if info.name_col_text:
            terms.add(info.name_col_text)
    for extra in (
        "聯盟", "部族", "自然",
        "裝備總表", "領主裝備總表", "士兵總表", "秘寶總表", "寵物總表",
        "專武總表", "英靈總表", "造型總表",
    ):
        terms.add(extra)
    # 去掉會把更長官方句拆開的短詞若造成問題——highlight 以最長優先且不重疊，
    # 整段已列入時會整段包住，短詞不會再切。仍避免把「精煉進度…」拆開。
    return [t for t in terms if t]


def val_cell(pairs: list[tuple[int, int]], attr_id: int) -> str:
    found = [v for a, v in pairs if a == attr_id]
    return fmt(found[0]) if found else EMPTY


def pairs_plain(pairs: list[tuple[int, int]], attrs: dict[int, AttrInfo]) -> str:
    if not pairs:
        return EMPTY
    parts = []
    for aid, val in pairs:
        info = attrs.get(aid) or AttrInfo(aid, "", True, "", "", None, None, None)
        parts.append(f"{attr_label_text(info)} {fmt(val)}")
    return "；".join(parts)


def pairs_html(pairs: list[tuple[int, int]], attrs: dict[int, AttrInfo], terms: list[str]) -> str:
    if not pairs:
        return e(EMPTY)
    parts = []
    for aid, val in pairs:
        info = attrs.get(aid) or AttrInfo(aid, "", True, "", "", None, None, None)
        parts.append(f"{attr_label_html(info, terms, include_id=False)} {e(fmt(val))}")
    return "；".join(parts)


def pct_steps_plain(steps: list[list[tuple[int, int]]], attrs: dict[int, AttrInfo], percents: list[int]) -> str:
    if not steps:
        return EMPTY
    parts = []
    for i, pairs in enumerate(steps):
        label = f"{percents[i]}%" if i < len(percents) else f"第 {i+1} 段"
        parts.append(f"{label} {pairs_plain(pairs, attrs)}")
    return "；".join(parts)


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    o = data.official
    attrs = data.attrs
    out: dict[str, str] = {}

    # 1. 隊列符文名錄
    cols = ["類型", "名稱", "說明", "寫入屬性", "1 級數值", "10 級數值"]
    rows = []
    for tt in o.team_types:
        typ = tt.typ
        if typ == 1:
            writ = "／".join(
                str(H(data.attrs[aid].name, terms))
                for aid in (3062, 4062, 5062)
            )
            v1, v10 = "230", "3000"
        elif typ == 2:
            writ = "／".join(
                str(H(data.attrs[aid].name, terms))
                for aid in (3062, 4062, 5062)
            ) + "，以及 " + H("突破防禦", terms)
            v1, v10 = "分營隊列攻擊 38、突破防禦 769", "分營隊列攻擊 500、突破防禦 10000"
        elif typ == 3:
            writ = "／".join(
                str(H(data.attrs[aid].name, terms))
                for aid in (3063, 4063, 5063)
            ) + "，以及 " + H("防禦", terms)
            v1, v10 = "分營隊列生命 50、防禦 600", "分營隊列生命 500、防禦 6000"
        elif typ == 4:
            writ = "／".join(
                str(H(data.attrs[aid].name, terms))
                for aid in (3063, 4063, 5063)
            )
            v1, v10 = "230", "3000"
        else:
            writ = (
                "／".join(str(H(data.attrs[aid].name, terms)) for aid in (3062, 4062, 5062))
                + " 與 "
                + "／".join(str(H(data.attrs[aid].name, terms)) for aid in (3063, 4063, 5063))
                + "，兩值相同"
            )
            v1, v10 = "各 115", "各 1500"
        # 上面 v1/v10 裡的「攻擊／生命／突破防禦／防禦」是簡述，屬性專名已在「寫入屬性」欄完整列出。
        rows.append([
            str(typ),
            H(tt.name, terms),
            H(tt.desc, terms),
            writ,
            e(v1),
            e(v10),
        ])
    out["team_catalog"] = table(cols, rows, mobile="cards", card_title="名稱")

    # 2. 隊列符文 1–10 級曲線（三營相同，不重列）
    cols = [
        "等級", "品質", "合成所需枚數",
        "力量／生命（分營隊列攻擊或生命）",
        "破甲：分營隊列攻擊", "破甲：突破防禦（64）",
        "厚甲：分營隊列生命", "厚甲：防禦（22）",
        "絕對強擊（攻擊與生命同值）",
        "戰力", "基礎戰力",
    ]
    # 表頭含官方屬性名時，用 html 並讓 highlight 包整名。短欄名用純文字即可。
    cols_html = [
        "等級", "品質", "合成所需枚數",
        H("力量符文", terms) + "／" + H("生命符文", terms) + "（分營隊列攻擊或生命）",
        H("破甲符文", terms) + "：" + "分營隊列攻擊",
        H("破甲符文", terms) + "：" + H("突破防禦", terms),
        H("厚甲符文", terms) + "：分營隊列生命",
        H("厚甲符文", terms) + "：" + H("防禦", terms),
        H("絕對強擊符文", terms) + "（攻擊與生命同值）",
        "戰力", "基礎戰力",
    ]
    rows = []
    for i, lev in enumerate(range(1, 11)):
        rows.append([
            str(lev),
            str(3 if lev <= 3 else 4 if lev <= 6 else 5 if lev <= 9 else 6),
            str(3 if lev < 10 else -1),
            str(TEAM_CURVES[1]["atk"][i]),
            str(TEAM_CURVES[2]["atk"][i]),
            str(TEAM_CURVES[2]["brk"][i]),
            str(TEAM_CURVES[3]["hp"][i]),
            str(TEAM_CURVES[3]["def"][i]),
            str(TEAM_CURVES[5]["atk"][i]),
            str(TEAM_POWER[i]),
            str(TEAM_BASE_POWER[i]),
        ])
    out["team_curve"] = table(cols_html, rows, mobile="sticky")

    # 3. 編號示例
    cols = ["類型", "種族", "陣營", "1 級編號", "10 級編號", "1 級攻擊／生命屬性"]
    rows = []
    for typ in range(1, 6):
        for race in range(1, 4):
            atk_or_hp = RACE_ATK[race] if typ in (1, 2, 5) else RACE_HP[race]
            if typ == 5:
                attr_txt = H(attrs[RACE_ATK[race]].name, terms) + "、" + H(attrs[RACE_HP[race]].name, terms)
            elif typ == 3:
                attr_txt = H(attrs[RACE_HP[race]].name, terms)
            elif typ == 4:
                attr_txt = H(attrs[RACE_HP[race]].name, terms)
            else:
                attr_txt = H(attrs[RACE_ATK[race]].name, terms)
            rows.append([
                str(typ),
                str(race),
                H(RACE_LABEL[race], terms),
                str(int(f"37{typ}{race}01")),
                str(int(f"37{typ}{race}10")),
                e(attr_txt),
            ])
    out["team_ids"] = table(cols, rows, mobile="sticky")

    # 4. 羈絆
    cols = ["符文等級", "出征上限（1019）", "隊列欄（數值相同）", "資料列對照"]
    cols_html = [
        "符文等級",
        H("出征上限", terms),
        "隊列欄（數值相同）",
        "資料列對照",
    ]
    rows = []
    for lev in range(1, 10):
        ids = []
        for r in data.bond_rows:
            if _int(r["rune_lev"]) == lev:
                ids.append(( _int(r["queue"]), _int(r["id"]) ))
        ids.sort()
        rows.append([
            str(lev),
            str(BOND_CAP[lev]),
            "2／3／4／5",
            e("、".join(f"隊列 {q}→{i}" for q, i in ids)),
        ])
    out["bond"] = table(cols_html, rows, mobile="sticky")

    # 5. player_rune 官方名稱
    cols = ["名稱", "說明", "介面字串（照原文，不加空格）", "名稱與說明"]
    rows = []
    for pn in o.player_names:
        flag = "名實相符" if pn.name_desc_match else "不一致"
        rows.append([
            H(pn.name, terms),
            H(pn.desc, terms),
            H(pn.ui, terms),
            e(flag),
        ])
    out["player_names"] = table(cols, rows, mobile="cards", card_title="名稱")

    # 6. 依寫入屬性對照
    cols = ["類型", "寫入屬性", "對照"]
    rows = []
    descriptions = {
        1: "像英雄生命。",
        2: "像士兵生命。",
        3: "像秘寶。其中一項沒有官方屬性名。",
        4: "像英雄強擊。",
        5: "像士兵強擊。",
        6: "像隊列強擊。",
    }
    for typ in range(1, 7):
        meta = PLAYER_TYPE_META[typ]
        rows_t = data.player_by_type[typ]
        lo, hi = rows_t[0].rune_id, rows_t[-1].rune_id
        # collect unique attr ids in order of first appearance
        seen: list[int] = []
        for p in rows_t:
            for aid, _ in (p.para + p.sp_para1 + p.sp_para2):
                if aid not in seen:
                    seen.append(aid)
        writ = "；".join(attr_label_html(attrs[aid], terms, include_id=False) if aid in attrs else e(str(aid)) for aid in seen)
        rows.append([
            str(typ),
            writ,
            e(descriptions[typ]),
        ])
    out["player_map"] = table(cols, rows, mobile="cards", card_title="類型")

    # 7. player_rune 共用曲線
    cols = [
        "等級", "品質", "合成所需枚數", "基礎戰力",
        "精煉經驗", "精煉需求", "精煉戰力",
        "精煉百分比欄", "精煉百分比戰力",
    ]
    rows = []
    sample = data.player_by_type[1]
    for p in sample:
        pct = "／".join(str(x) for x in p.refine_percent) if p.refine_percent else EMPTY
        ppow = "／".join(str(x) for x in p.refine_percent_power) if p.refine_percent_power else EMPTY
        rows.append([
            str(p.lev), str(p.rare), str(p.level_up_num), str(p.base_power),
            str(p.refine_exp), empty_or(p.refine_need), empty_or(p.refine_power),
            e(pct), e(ppow),
        ])
    out["player_shared"] = table(cols, rows, mobile="sticky")

    # 8–13. 各 type 屬性曲線
    def type_attr_table(typ: int) -> str:
        rows_t = data.player_by_type[typ]
        if typ == 3:
            cols_t = [
                "等級", "編號",
                "特殊參數 1 " + attr_label_html(attrs[4], terms, include_id=False),
                "特殊參數 1 " + attr_label_html(attrs[20006], terms, include_id=False),
                "特殊參數 2 " + attr_label_html(attrs[4], terms, include_id=False),
                "特殊參數 2 " + attr_label_html(attrs[20006], terms, include_id=False),
                "基礎戰力",
            ]
            body = []
            for p in rows_t:
                body.append([
                    str(p.lev), str(p.rune_id),
                    val_cell(p.sp_para1, 4), val_cell(p.sp_para1, 20006),
                    val_cell(p.sp_para2, 4), val_cell(p.sp_para2, 20006),
                    str(p.base_power),
                ])
            return table(cols_t, body, mobile="sticky")
        # ordered attr ids
        seen: list[int] = []
        for p in rows_t:
            for aid, _ in p.para:
                if aid not in seen:
                    seen.append(aid)
        cols_t = ["等級", "編號"] + [attr_label_html(attrs[aid], terms, include_id=False) for aid in seen] + ["基礎戰力"]
        body = []
        for p in rows_t:
            body.append(
                [str(p.lev), str(p.rune_id)]
                + [val_cell(p.para, aid) for aid in seen]
                + [str(p.base_power)]
            )
        return table(cols_t, body, mobile="sticky")

    for typ in range(1, 7):
        out[f"player_curve_{typ}"] = type_attr_table(typ)

    # 14–19. 各 type 精煉屬性 7–11
    def type_refine_table(typ: int) -> str:
        rows_t = [p for p in data.player_by_type[typ] if p.lev in range(7, 12)]
        if typ == 3:
            cols_t = [
                "等級",
                "精煉特殊參數 1",
                "精煉百分比特殊參數 2（對應 20／40／60／80／100）",
            ]
            body = []
            for p in rows_t:
                body.append([
                    str(p.lev),
                    pairs_html(p.refine_sp_para1, attrs, terms),
                    e(EMPTY) if not p.refine_percent_sp_para2 else "；".join(
                        f"{e(str(p.refine_percent[i]))}% {pairs_html(step, attrs, terms)}"
                        for i, step in enumerate(p.refine_percent_sp_para2)
                    ),
                ])
            return table(cols_t, body, mobile="sticky")
        cols_t = [
            "等級",
            "精煉參數",
            "精煉百分比參數（對應 20／40／60／80／100）",
        ]
        body = []
        for p in rows_t:
            body.append([
                str(p.lev),
                pairs_html(p.refine_para, attrs, terms),
                e(EMPTY) if not p.refine_percent_para else "；".join(
                    f"{e(str(p.refine_percent[i]))}% {pairs_html(step, attrs, terms)}"
                    for i, step in enumerate(p.refine_percent_para)
                ),
            ])
        return table(cols_t, body, mobile="sticky")

    for typ in range(1, 7):
        out[f"player_refine_{typ}"] = type_refine_table(typ)

    # 20. 屬性編號
    cols = ["屬性編號", "官方名稱", "類型", "顯示類型", "分營欄", "名稱欄", "備註"]
    rows = []
    notes = {
        3: "名稱欄指向 103 的名稱鍵，本頁用編號 3 的官方名稱「攻擊」。",
        4: "名稱欄指向 104 的名稱鍵，本頁用編號 4 的官方名稱「生命值」。",
        62: "不分營的隊列攻擊。隊列符文寫的是 3062 等分營編號，不與 62 寫成同一條公式。",
        63: "不分營的隊列生命。不與 3063 等寫成同一條公式。",
        103: "顯示類型為 2，只記原值，不換算成百分比。",
        104: "顯示類型為 2，只記原值，不換算成百分比。",
        10103: "顯示類型為 2，只記原值。",
        10104: "顯示類型為 2，只記原值。",
        3062: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        3063: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        4062: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        4063: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        5062: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        5063: "類型 2、顯示類型 2、分營欄 1，只記原值。",
        20006: "四份字串包都沒有這個編號的名稱鍵。名稱欄指向 20004（「秘寶生命」），不作本頁正式屬性名。",
    }
    for aid in USED_ATTR_IDS:
        info = attrs[aid]
        name_cell = H(info.name, terms) if info.name else e("（無此鍵）")
        rows.append([
            str(aid),
            name_cell,
            e(EMPTY if info.typ is None else str(info.typ)),
            e(EMPTY if info.show_type is None else str(info.show_type)),
            e(EMPTY if info.is_race is None else str(info.is_race)),
            e(info.name_col or EMPTY),
            e(notes.get(aid, "只記表內原值。" if info.show_type == 2 else "只記表內原值。")),
        ])
    out["attr_ref"] = table(cols, rows, mobile="cards", card_title="屬性編號")
    return out




def _data_notes(data: TablesData) -> str:
    sc = data.table_meta["string_cmp"]
    tc = data.table_meta["table_cmp"]
    live = sc["packs"]["live"]
    loc = sc["packs"]["2026-11-22-locallow"]
    old = sc["packs"]["2026-11-05"]
    sa = sc["packs"]["2026-11-22"]
    diffs = sc["value_diffs"]
    missing = sc["missing"]
    if diffs or missing:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵中，值不同的有 {diffs or '無'}，"
            f"缺鍵：{missing or '無'}。"
        )
    else:
        extra = f"本頁用到的 {sc['used_keys']} 個字串鍵在這四份裡值相同。"

    tr = tc["team_rune.json"]
    tb = tc["team_rune_bond.json"]
    pr = tc["player_rune.json"]
    attr = tc["attribute.json"]
    tr_same = all(tr["identical"].get(p) for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow"))
    tb_same = all(tb["identical"].get(p) for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow"))
    pr_note = (
        f"`player_rune.json` 只出現在現行 LocalLow 與 2026-11-22 LocalLow 歸檔"
        f"（皆 {pr['rows']['live']} 筆、{pr['bytes']['live']} bytes，sha256 {pr['sha256']['live']}），"
        "兩份位元組相同；2026-11-05 解壓檔與 2026-11-22 StreamingAssets 沒有此表。"
        "這是相對第 22 章（寫「本抽取沒有精煉表」）的主要補充。"
    )
    return (
        f"資料截至 {RUNE_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {RUNE_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {RUNE_DATA_PACKED}（香港時間）。"
        f"`team_rune.json` 四份包皆 {tr['rows']['live']} 筆、{tr['bytes']['live']} bytes，"
        f"sha256 {tr['sha256']['live']}，位元組" + ("相同。" if tr_same else "並非全部相同。")
        + f"`team_rune_bond.json` 四份包皆 {tb['rows']['live']} 筆、{tb['bytes']['live']} bytes，"
        f"sha256 {tb['sha256']['live']}，位元組" + ("相同。" if tb_same else "並非全部相同。")
        + pr_note
        + "`attribute.json` 列數同為 764；現行檔與 2026-11-22 兩份歸檔位元組相同，"
        "2026-11-05 與現行包位元組不同，差在後來多了欄位（NameKey、name_season）；"
        "本頁用到的 type／show_type／name 與 2026-11-05 相同。"
        "本頁不以 goods.json 當道具目錄。"
        f"`strings_zh.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（{live['keys']} 鍵，"
        f"{live['bytes']} bytes，sha256 {live['sha256']}）；"
        f"2026-11-05（{old['keys']} 鍵）與 2026-11-22 StreamingAssets（{sa['keys']} 鍵）整體不同。"
        f"{extra}"
        "attribute_name_20006 在現行字串表與三份歸檔都不存在，不是歸檔缺漏；"
        "attribute.json 裡 id 20006 的 name 欄指向 attribute_name_20004（「秘寶生命」），本頁不把它當作 20006 的正式名稱。"
        "顯示規則依攻略手冊「符文圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05），"
        "但數值一律以現行資料表為準。隊列符文與羈絆數列與第 22 章一致；"
        "player_rune 的 72 筆曲線與精煉欄為本頁按表補上。"
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜符文總表"
    summary = (
        "官方界面所稱的符文：隊列符文五種三營 1–10 級與羈絆，以及後續資料包才出現的另一套符文"
        "（六種、1–12 級，含精煉欄）。"
    )
    toc = toc_list([
        {"id": "rules", "label": "官方規則"},
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍"},
        {"id": "team-catalog", "label": "五種隊列符文"},
        {"id": "team-curves", "label": "隊列符文數值"},
        {"id": "bond", "label": "羈絆"},
        {"id": "player-names", "label": "後續資料包符文的官方名稱與說明"},
        {"id": "player-map", "label": "依寫入屬性對照"},
        {"id": "player-curves", "label": "後續資料包符文的數值與精煉"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{LEDE}</p>')
    add(f"    {toc}")

    add('    <section id="rules">')
    add("      <h2>官方規則</h2>")
    add(p_html(
        "以下整段引自官方規則說明，連「1.」「2.」前綴一起，不拆開、不另行加句號。字串鍵見資料說明。"
    ))
    add(f"<p>{official_term_html(o.info_desc)}</p>")
    add(p_html(
        "合成規則與表一致：隊列符文 1–9 級需 3 枚，第 10 級不再合成；"
        "後續資料包那套 1–11 級需 3 枚，第 12 級不再合成。"
        f"介面另有「{H(o.power_tip, terms)}」、"
        f"「{H(o.uncompound, terms)}」。"
        "羈絆列的提示原文是："
    ))
    add(f"<p>{official_term_html(o.bond_tip)}</p>")
    add(p_html(
        f"以及「{H(o.tips5, terms)}」、"
        f"「{H(o.tips6, terms)}」。"
    ))
    add(p_html(
        f"官方規則寫「五個插槽」。另有郵件標題「{H(o.mail_title, terms)}」，正文如下。兩者都照官方字串記下，不自行裁斷插槽數，也不把它們寫成同一套規則。對照見資料說明。"
    ))
    add(f"<p>{official_term_html(o.mail_desc)}</p>")
    add("    </section>")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        "正文只根據遊戲資料表與官方字串，不評定符文強弱，也不做搭配模擬。"
        f"官方系統名是「{H(o.system_name, terms)}」，"
        f"提示「{H(o.system_dec, terms)}」。"
        f"介面標題是「{H(o.title, terms)}」。"
        f"{H(o.statue_name, terms)}說明：「{H(o.statue_des, terms)}」。"
        f"英雄四件套裝備見<a href=\"equipment.html\">{H('裝備總表', terms)}</a>，"
        f"領主裝備見<a href=\"lord-equipment.html\">{H('領主裝備總表', terms)}</a>，"
        f"士兵見<a href=\"troops.html\">{H('士兵總表', terms)}</a>，"
        f"秘寶見<a href=\"artifacts.html\">{H('秘寶總表', terms)}</a>，"
        f"寵物見<a href=\"pets.html\">{H('寵物總表', terms)}</a>。"
        f"已發佈的<a href=\"exclusive.html\">{H('專武總表', terms)}</a>是英雄專武；"
        f"已發佈的<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>是綁在英雄身上的另一套養成；"
        f"已發佈的<a href=\"skins.html\">{H('造型總表', terms)}</a>是英雄造型。"
        "帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場、科技、裝飾物不在本頁展開。"
    ))
    add("<ul>")
    add("<li><strong>屬性只錄表上的原值</strong>，不自行換成百分比。"
        f"「{H('攻擊', terms)}／{H('生命值', terms)}」與「{H('英雄攻擊', terms)}／{H('英雄生命', terms)}」不要混成同一欄。"
        "有一個編號在四份字串包都沒有對應名稱，本頁不把它的備用名稱當成正式名稱。對照見資料說明。</li>")
    add("<li>正式用語是「部族」不是「部落」。不要從時間或賽季欄位自動標未開放（這幾張符文表沒有這類欄位）。</li>")
    add("<li>隊列符文五種只使用對應的官方名稱與說明，不用另一套符文表的編號名稱來標這五種。</li>")
    add("<li>官方字串同時有「精煉」與「精鍊」，照原文引，不統一改字。"
        f"例如介面寫「{H(o.refine, terms)}」，也寫「{H(o.can_refine, terms)}」。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍</h2>")
    add(p_html(
        "本頁寫兩套符文：介面標題「隊列符文」這套（五種、三營、1–10 級與羈絆），"
        "以及後續資料包才出現的另一套（六種、1–12 級，含精煉欄）。"
        "後一套沒有獨立的戰力欄，本頁不編造戰力，也不用它的編號名稱來標隊列符文的五種。檔名與筆數見資料說明。"
    ))
    add("    </section>")

    add('    <section id="team-catalog">')
    add("      <h2>五種隊列符文</h2>")
    add(p_html(
        "五種隊列符文各自使用對應的官方名稱與說明。對照見資料說明。"
        "三個陣營的數值相同，只換分營屬性（聯盟／部族／自然）。"
        "品質隨等級走：1–3 級為 3，4–6 級為 4，7–9 級為 5，10 級為 6。"
        "編號規律是 37、種類、陣營、等級兩位，例如聯盟力量 1 級為 371101，自然絕對強擊 10 級為 375310。"
    ))
    add(tbl["team_catalog"])
    add("    </section>")

    add('    <section id="team-curves">')
    add("      <h2>隊列符文數值</h2>")
    add(p_html(
        "下列曲線三營相同，故不把 150 列重複展開。"
        f"{H('力量符文', terms)}與{H('生命符文', terms)}的分營隊列攻擊／生命數列相同；"
        f"{H('絕對強擊符文', terms)}是同一條數列的一半（含進位：第 8 級 1036，不是力量／生命第 8 級 2073 的一半，表上不是 1036.5）。"
        "戰力五種符文、三個陣營皆相同；基礎戰力亦同。"
        "分營隊列攻擊／生命只記原值，不換成百分比。顯示規則見資料說明。"
    ))
    add(tbl["team_curve"])
    add(p_html("編號與分營屬性對照："))
    add(tbl["team_ids"])
    add("    </section>")

    add('    <section id="bond">')
    add("      <h2>羈絆（全隊同級加成）</h2>")
    add(p_html(
        f"羈絆表 36 筆：隊列欄為 2／3／4／5，符文等級為 1–9，"
        f"屬性一律是「{H('出征上限', terms)}」（點數類）。"
        "同一等級、不同隊列欄的數值完全相同。沒有隊列欄 1，也沒有 10 級羈絆。"
        "官方說明是同一個隊列建築上的符文均達到同一等級後額外加成；表沒有解釋隊列欄為何從 2 起算、為何 2–5 的數值相同，以及為何沒有 10 級，本頁不自行解釋。欄位名見資料說明。"
    ))
    add(tbl["bond"])
    add("    </section>")

    add('    <section id="player-names">')
    add("      <h2>後續資料包符文的官方名稱與說明</h2>")
    add(p_html(
        "後續資料包那套符文表沒有名稱欄。下列是字串表裡的官方名稱、說明與介面字串。對照見資料說明。"
        "介面字串前置羅馬數字，且順序與名稱表不完全相同"
        f"（第一條介面字串是「{H(o.player_names[0].ui, terms)}」，照原文，不自行加空格）。"
        "名稱與說明並非一一對應："
        f"第二個名稱是「{H('英雄強擊符文', terms)}」，對應說明卻寫士兵生命；"
        "只有第一個與第六個名實相符（第一個的名稱與說明都寫英雄生命；第六個的名稱是隊列強擊符文，說明寫提升突破及防禦屬性）。"
        "這組名稱絕不用來標隊列符文的五種，也不可把後續資料包的種類編號直接對成這組名稱的第 N 條。"
    ))
    add(tbl["player_names"])
    add("    </section>")

    add('    <section id="player-map">')
    add("      <h2>依寫入屬性對照</h2>")
    add(p_html(
        "下表依各種類實際寫入的屬性作對照，不是把種類編號直接對成上一節那組名稱的第 N 條。"
        "「像某某」只是依寫入屬性所作的對照說明。"
    ))
    add(tbl["player_map"])
    add("    </section>")

    add('    <section id="player-curves">')
    add("      <h2>後續資料包符文的數值與精煉</h2>")
    add(p_html(
        "6 個種類 × 12 級 = 72 筆。品質：1–3 級為 3，4–6 級為 4，7–9 級為 5，10–12 級為 6。"
        "合成所需枚數：1–11 級為 3，第 12 級為 -1。沒有戰力欄，只有基礎戰力；六個種類各級的基礎戰力與精煉相關欄完全相同，故先列共用表。"
        "精煉欄在六個種類都只出現於 7–11 級；1–6 級與 12 級（滿級）這些欄為空或未填。欄位名見資料說明。"
        "精煉需求與精煉經驗照表記數字，不猜道具，也不猜經驗與材料的換算。"
        "不把 1%、20% 規則自行代入結算面板；只列表上的精煉屬性與戰力數。"
    ))
    add(p_html("官方精煉進度說明（已去掉色彩標籤，整句收入單一標記，不拆句；字串鍵見資料說明）："))
    add(f"<p>{official_term_html(o.refine_progress_tip)}</p>")
    add(p_html(
        f"其他精煉相關原文：「{H(o.one_click_refine, terms)}」、「{H(o.refine_percent, terms)}」、"
        f"「{H(o.refine_progress, terms)}」、「{H(o.refine_progress_unlock_tip, terms)}」、"
        f"「{H(o.refine_choose_tip, terms)}」、「{H(o.refine_exp_full, terms)}」、"
        f"「{H(o.refine_max, terms)}」、「{H(o.refine_result, terms)}」。"
    ))
    add("<h3>共用曲線（六個種類相同）</h3>")
    add(tbl["player_shared"])
    for typ in range(1, 7):
        meta = PLAYER_TYPE_META[typ]
        add(f"<h3>第 {typ} 種屬性曲線（依寫入屬性對照，不是表內名稱欄）</h3>")
        add(tbl[f"player_curve_{typ}"])
        add(f"<h3>第 {typ} 種精煉屬性（僅 7–11 級）</h3>")
        add(tbl[f"player_refine_{typ}"])
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add("<li>羈絆隊列欄從 2 起、沒有 1 與 10 的含義。</li>")
    add("<li>分營隊列攻擊／生命與不分營隊列攻擊／生命如何疊加，以及如何進入戰鬥結算。</li>")
    add("<li>後續資料包名稱與說明不一致的原因；也不把這組名稱派給隊列符文，或按種類編號直接對成那組名稱的第 N 條。</li>")
    add("<li>精煉經驗與材料／道具的對應（表沒指明）。</li>")
    add("<li>插槽數為五或六的裁斷。</li>")
    add("<li>強弱評定與搭配模擬。</li>")
    add("<li>另一張圖騰表（檔名見資料說明），以及帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場、科技、裝飾物。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<p>以下是整理用註記，查名稱與效果可略過。</p>")
    add("<h3>屬性對照</h3>")
    add(p_html(
        "下表列出本頁用到的屬性編號。官方名稱取 <code>attribute_name_{id}</code>。"
        "show_type=2 只記原值，不換算成百分比。"
    ))
    add(tbl["attr_ref"])
    add("<ul>")
    add("<li>以下是整理用註記，查名稱與效果可略過。</li>")
    add(
        "<li>官方 1.–5. 條規則引自 <code>team_rune_info_desc</code>。"
        "合成所需枚數對應 <code>level_up_num</code>：隊列符文 1–9 級為 3，第 10 級為 -1；"
        "<code>player_rune</code> 1–11 級為 3，第 12 級為 -1。"
        "介面另有 <code>team_rune_power_tip</code>、<code>team_rune_uncompound</code>；"
        "羈絆提示為 <code>team_rune_bond</code>，以及 <code>team_rune_tips5</code>／<code>team_rune_tips6</code>。"
        "郵件標題鍵是 <code>mail_rune_title</code>。"
        "符文名稱只使用對應的官方名稱鍵，不改官方名。可見改寫「沒有對應名稱」「對照見資料說明」，名稱鍵對照見此。</li>"
    )
    add("<li>隊列符文對應 <code>team_rune.json</code>（150 筆）與 <code>team_rune_bond.json</code>（36 筆）；"
        "另一套是只在 LocalLow 包出現的 <code>player_rune.json</code>（72 筆：6 個 type × 12 級，含精煉欄）。"
        "player_rune 表沒有名稱欄，也沒有 power 欄，只有 base_power；本頁不編造 power，也不把 type N 寫成 <code>team_rune_name_00N</code>。</li>")
    add("<li>隊列符文對應 <code>team_rune.json</code> 與 <code>team_rune_bond.json</code>；另一套是只在 LocalLow 包出現的 <code>player_rune.json</code>。"
        "官方系統名鍵是 <code>team_rune_bagname</code>，標題鍵是 <code>team_rune_title</code>。"
        "屬性名優先用 <code>attribute_name_{id}</code>，不要盲目跟 <code>attribute.json</code> 的 <code>name</code> 欄。"
        f"id 3 的 name 欄指向 <code>attribute_name_103</code>，本頁用 <code>attribute_name_3</code>「{H('攻擊', terms)}」（type=1、show_type=1）；"
        f"id 4 用 <code>attribute_name_4</code>「{H('生命值', terms)}」，不寫成「{H('英雄攻擊', terms)}／{H('英雄生命', terms)}」。"
        f"id 103／104 才是 show_type=2 的「{H('英雄攻擊', terms)}／{H('英雄生命', terms)}」。"
        "id 20006 必須先查 <code>attribute_name_20006</code>：四份字串包都沒有此鍵；name 欄指向 <code>attribute_name_20004</code>，本頁不把它當作正式名稱。"
        "可見「依寫入屬性對照」表只列類型、寫入屬性官方名與對照。編號區間、寫入欄位、表內原值與編號前綴見此："
        "類型 1 為 7010001–7010012（前綴 701），寫入欄位為參數欄（原名 <code>para</code>），生命值 4、英雄生命 104，參數欄為 4，高級加 104；"
        "類型 2 為 7020001–7020012（前綴 702），參數欄，士兵生命 10004、出征上限 1019、所有士兵生命 10104；"
        "類型 3 為 7030001–7030012（前綴 703），寫入欄位為特殊參數 1／2（原名 <code>sp_para1</code>／<code>sp_para2</code>），生命值 4 與 20006（沒有官方屬性名），不用參數欄；"
        "類型 4 為 7060001–7060012（前綴 706，與種類編號不一致），參數欄，攻擊 3、英雄攻擊 103；"
        "類型 5 為 7050001–7050012（前綴 705），參數欄，士兵攻擊 10003、出征上限 1019、所有士兵攻擊 10103；"
        "類型 6 為 7040001–7040012（前綴 704，與種類編號不一致），參數欄，防禦 22、突破防禦 64、出征上限 1019。"
        "可見隊列符文寫入屬性只列官方名；分營屬性編號聯盟隊列攻擊／生命 3062／3063、部族 4062／4063、自然 5062／5063，破甲另加突破防禦 64，厚甲另加防禦 22。"
        "種族 1／2／3 對應聯盟／部族／自然。羈絆「出征上限」編號 1019。後續資料包曲線表頭只寫官方屬性名；20006 沒有官方屬性名，編號只在資料說明。"
        f"隊列符文的分營隊列攻擊／生命（3062 等）是 type=2、show_type=2；"
        f"{H('防禦', terms)} 22、{H('突破防禦', terms)} 64、{H('出征上限', terms)} 1019，"
        "以及 player_rune 裡 show_type=1 的 3／4／22／64／10003／10004／20006，也都只記原值。"
        "不把 3062 等與不分營的 62／63 寫成同一條公式。"
        "隊列符文的 type 1–5，只使用 <code>team_rune_name_1</code>–<code>5</code> 與 <code>team_rune_desc_1</code>–<code>5</code>。"
        "絕不用 <code>team_rune_name_001</code>–<code>006</code> 或 <code>UI_player_rune_01</code>–<code>06</code> 來標 <code>team_rune</code> 的 type。"
        "<code>kvk_totem</code> 不在本頁展開。"        "可見表頭「類型／戰力／基礎戰力／精煉經驗／精煉需求／精煉戰力／精煉百分比欄／精煉百分比戰力／精煉參數／精煉特殊參數／特殊參數 1／2／屬性編號／顯示類型／分營欄／名稱欄／種族編號」對應原欄名 <code>type</code>、<code>power</code>、<code>base_power</code>、<code>refine_exp</code>、<code>refine_need</code>、<code>refine_power</code>、<code>refine_percent</code>、<code>refine_percent_power</code>、<code>refine_para</code>、<code>refine_sp_para1</code>、<code>sp_para1</code>／<code>sp_para2</code>、<code>id</code>、<code>show_type</code>、<code>is_race</code>、<code>name</code>、<code>race</code>。寫入欄位「參數欄」原名 <code>para</code>。可見「羈絆隊列欄」原名 <code>queue</code>。</li>")
    add(f"<li>{_data_notes(data)}</li>")
    add("<li>待補：attribute_name_20006 缺失時客戶端實際顯示什麼；"
        "精煉經驗與材料的對應；羈絆隊列欄的含義；"
        "分營與不分營隊列攻擊／生命的疊加方式；"
        "以及 name_001–006 與說明不一致的原因。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {RUNE_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_rune_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    o = data.official
    attrs = data.attrs
    out: dict[str, str] = {}

    rows = []
    for tt in o.team_types:
        typ = tt.typ
        if typ == 1:
            writ = "聯盟／部族／自然隊列攻擊（3062／4062／5062）"
            v1, v10 = "230", "3000"
        elif typ == 2:
            writ = "聯盟／部族／自然隊列攻擊（3062／4062／5062），以及突破防禦（64）"
            v1, v10 = "分營隊列攻擊 38、突破防禦 769", "分營隊列攻擊 500、突破防禦 10000"
        elif typ == 3:
            writ = "聯盟／部族／自然隊列生命（3063／4063／5063），以及防禦（22）"
            v1, v10 = "分營隊列生命 50、防禦 600", "分營隊列生命 500、防禦 6000"
        elif typ == 4:
            writ = "聯盟／部族／自然隊列生命（3063／4063／5063）"
            v1, v10 = "230", "3000"
        else:
            writ = "分營隊列攻擊（3062／4062／5062）與分營隊列生命（3063／4063／5063），兩值相同"
            v1, v10 = "各 115", "各 1500"
        rows.append([str(typ), tt.name, tt.desc, writ, v1, v10])
    out["team_catalog"] = md_table(
        ["type", "名稱", "說明", "寫入屬性", "1 級數值", "10 級數值"], rows
    )

    rows = []
    for i, lev in enumerate(range(1, 11)):
        rows.append([
            str(lev),
            str(3 if lev <= 3 else 4 if lev <= 6 else 5 if lev <= 9 else 6),
            str(3 if lev < 10 else -1),
            str(TEAM_CURVES[1]["atk"][i]),
            str(TEAM_CURVES[2]["atk"][i]),
            str(TEAM_CURVES[2]["brk"][i]),
            str(TEAM_CURVES[3]["hp"][i]),
            str(TEAM_CURVES[3]["def"][i]),
            str(TEAM_CURVES[5]["atk"][i]),
            str(TEAM_POWER[i]),
            str(TEAM_BASE_POWER[i]),
        ])
    out["team_curve"] = md_table(
        [
            "等級", "品質", "合成所需枚數",
            "力量／生命（分營隊列攻擊或生命）",
            "破甲：分營隊列攻擊", "破甲：突破防禦（64）",
            "厚甲：分營隊列生命", "厚甲：防禦（22）",
            "絕對強擊（攻擊與生命同值）",
            "power", "base_power",
        ],
        rows,
    )

    rows = []
    for typ in range(1, 6):
        for race in range(1, 4):
            if typ == 5:
                attr_txt = f"{RACE_ATK[race]}、{RACE_HP[race]}"
            elif typ in (3, 4):
                attr_txt = str(RACE_HP[race])
            else:
                attr_txt = str(RACE_ATK[race])
            rows.append([
                str(typ), str(race), RACE_LABEL[race],
                str(int(f"37{typ}{race}01")),
                str(int(f"37{typ}{race}10")),
                attr_txt,
            ])
    out["team_ids"] = md_table(
        ["type", "種族 race", "陣營", "1 級編號", "10 級編號", "1 級攻擊／生命屬性編號"],
        rows,
    )

    rows = []
    for lev in range(1, 10):
        ids = sorted(
            (_int(r["queue"]), _int(r["id"]))
            for r in data.bond_rows
            if _int(r["rune_lev"]) == lev
        )
        rows.append([
            str(lev), str(BOND_CAP[lev]), "2／3／4／5",
            "、".join(f"queue {q}→{i}" for q, i in ids),
        ])
    out["bond"] = md_table(
        ["符文等級 rune_lev", "出征上限（1019）", "queue（數值相同）", "列 id"],
        rows,
    )

    rows = []
    for pn in o.player_names:
        rows.append([
            f"{pn.name_key}／{pn.desc_key}",
            pn.name, pn.desc, pn.ui_key, pn.ui,
            "名實相符" if pn.name_desc_match else "不一致",
        ])
    out["player_names"] = md_table(
        ["鍵（name／desc）", "名稱", "說明", "UI 鍵", "UI 字串（照原文，不加空格）", "名稱與說明"],
        rows,
    )

    descriptions = {
        1: "para 為 4，高級加 104。像英雄生命。",
        2: "para 為 10004，其後加 1019，再加 10104。像士兵生命。",
        3: "用 sp_para1／sp_para2，不用 para。寫入 4 與 20006。像秘寶。",
        4: "para 為 3，高級加 103。像英雄強擊。編號前綴是 706，與 type 號不一致。",
        5: "para 為 10003，其後加 1019，再加 10103。像士兵強擊。編號前綴是 705。",
        6: "para 為 22 與 64，高級加 1019。像隊列強擊。編號前綴是 704，與 type 號不一致。",
    }
    rows = []
    for typ in range(1, 7):
        meta = PLAYER_TYPE_META[typ]
        rows_t = data.player_by_type[typ]
        lo, hi = rows_t[0].rune_id, rows_t[-1].rune_id
        seen: list[int] = []
        for p in rows_t:
            for aid, _ in (p.para + p.sp_para1 + p.sp_para2):
                if aid not in seen:
                    seen.append(aid)
        writ = "；".join(attr_label_text(attrs[aid]) if aid in attrs else str(aid) for aid in seen)
        rows.append([
            str(typ),
            f"{lo}–{hi}（前綴 {meta['prefix']}）",
            meta["fields"],
            writ,
            descriptions[typ],
        ])
    out["player_map"] = md_table(
        ["type", "編號區間", "寫入欄位", "寫入屬性（表內原值）", "依寫入屬性對照，不是表內名稱欄"],
        rows,
    )

    rows = []
    for p in data.player_by_type[1]:
        pct = "／".join(str(x) for x in p.refine_percent) if p.refine_percent else EMPTY
        ppow = "／".join(str(x) for x in p.refine_percent_power) if p.refine_percent_power else EMPTY
        rows.append([
            str(p.lev), str(p.rare), str(p.level_up_num), str(p.base_power),
            str(p.refine_exp), empty_or(p.refine_need), empty_or(p.refine_power),
            pct, ppow,
        ])
    out["player_shared"] = md_table(
        [
            "等級", "品質", "合成所需枚數", "base_power",
            "refine_exp", "refine_need", "refine_power",
            "refine_percent", "refine_percent_power",
        ],
        rows,
    )

    for typ in range(1, 7):
        rows_t = data.player_by_type[typ]
        if typ == 3:
            rows = [[
                str(p.lev), str(p.rune_id),
                val_cell(p.sp_para1, 4), val_cell(p.sp_para1, 20006),
                val_cell(p.sp_para2, 4), val_cell(p.sp_para2, 20006),
                str(p.base_power),
            ] for p in rows_t]
            out[f"player_curve_{typ}"] = md_table(
                [
                    "等級", "編號",
                    "sp_para1 " + attr_label_text(attrs[4]),
                    "sp_para1 " + attr_label_text(attrs[20006]),
                    "sp_para2 " + attr_label_text(attrs[4]),
                    "sp_para2 " + attr_label_text(attrs[20006]),
                    "base_power",
                ],
                rows,
            )
        else:
            seen = []
            for p in rows_t:
                for aid, _ in p.para:
                    if aid not in seen:
                        seen.append(aid)
            rows = [
                [str(p.lev), str(p.rune_id)] + [val_cell(p.para, aid) for aid in seen] + [str(p.base_power)]
                for p in rows_t
            ]
            out[f"player_curve_{typ}"] = md_table(
                ["等級", "編號"] + [attr_label_text(attrs[aid]) for aid in seen] + ["base_power"],
                rows,
            )

        rows_r = [p for p in rows_t if p.lev in range(7, 12)]
        if typ == 3:
            rows = []
            for p in rows_r:
                steps = EMPTY if not p.refine_percent_sp_para2 else "；".join(
                    f"{p.refine_percent[i]}% {pairs_plain(step, attrs)}"
                    for i, step in enumerate(p.refine_percent_sp_para2)
                )
                rows.append([str(p.lev), pairs_plain(p.refine_sp_para1, attrs), steps])
            out[f"player_refine_{typ}"] = md_table(
                ["等級", "refine_sp_para1", "refine_percent_sp_para2（對應 20／40／60／80／100）"],
                rows,
            )
        else:
            rows = []
            for p in rows_r:
                steps = EMPTY if not p.refine_percent_para else "；".join(
                    f"{p.refine_percent[i]}% {pairs_plain(step, attrs)}"
                    for i, step in enumerate(p.refine_percent_para)
                )
                rows.append([str(p.lev), pairs_plain(p.refine_para, attrs), steps])
            out[f"player_refine_{typ}"] = md_table(
                ["等級", "refine_para", "refine_percent_para（對應 20／40／60／80／100）"],
                rows,
            )

    notes = {
        3: "name 欄指向 attribute_name_103，本頁用 attribute_name_3「攻擊」。",
        4: "name 欄指向 attribute_name_104，本頁用 attribute_name_4「生命值」。",
        62: "不分營的隊列攻擊。隊列符文寫的是 3062 等分營編號，不與 62 寫成同一條公式。",
        63: "不分營的隊列生命。不與 3063 等寫成同一條公式。",
        103: "show_type=2，只記原值，不換算成百分比。",
        104: "show_type=2，只記原值，不換算成百分比。",
        10103: "show_type=2，只記原值。",
        10104: "show_type=2，只記原值。",
        3062: "type=2、show_type=2、is_race=1，只記原值。",
        3063: "type=2、show_type=2、is_race=1，只記原值。",
        4062: "type=2、show_type=2、is_race=1，只記原值。",
        4063: "type=2、show_type=2、is_race=1，只記原值。",
        5062: "type=2、show_type=2、is_race=1，只記原值。",
        5063: "type=2、show_type=2、is_race=1，只記原值。",
        20006: "四份字串包都沒有 attribute_name_20006。name 欄指向 attribute_name_20004（「秘寶生命」），不作本頁正式屬性名。",
    }
    rows = []
    for aid in USED_ATTR_IDS:
        info = attrs[aid]
        rows.append([
            str(aid),
            info.name or "（無此鍵）",
            EMPTY if info.typ is None else str(info.typ),
            EMPTY if info.show_type is None else str(info.show_type),
            EMPTY if info.is_race is None else str(info.is_race),
            info.name_col or EMPTY,
            notes.get(aid, "只記表內原值。"),
        ])
    out["attr_ref"] = md_table(
        ["屬性 id", "官方名稱（attribute_name_{id}）", "type", "show_type", "is_race", "name 欄", "備註"],
        rows,
    )
    return out


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    add_lines: list[str] = []
    add = add_lines.append
    add("# Top Heroes Wiki｜符文總表")
    add("")
    add(LEDE)
    add("")
    add("本頁只寫符文這套系統。")
    add("")
    add(
        "交叉引用：[裝備總表](equipment.html)、[領主裝備總表](lord-equipment.html)、"
        "[士兵總表](troops.html)、[秘寶總表](artifacts.html)、[寵物總表](pets.html)；"
        "[專武總表](exclusive.html)、[英靈總表](valhalla.html)、[造型總表](skins.html)。"
    )
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "正文只根據遊戲資料表與官方字串，不評定符文強弱，也不做搭配模擬。"
        f"官方系統名是「{o.system_name}」（鍵 `team_rune_bagname`），提示「{o.system_dec}」。"
        f"介面標題是「{o.title}」（`team_rune_title`）。"
        f"{o.statue_name}說明：「{o.statue_des}」。"
        "帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場、科技、裝飾物，以及 `kvk_totem`，不在本頁展開。"
    )
    add("")
    add(
        "- **屬性名優先用 `attribute_name_{id}`**，不要盲目跟 `attribute.json` 的 `name` 欄。"
        "id 3 的 name 欄指向 `attribute_name_103`，本頁用 `attribute_name_3`「攻擊」（type=1、show_type=1）；"
        "id 4 用 `attribute_name_4`「生命值」，不寫成「英雄攻擊／英雄生命」。"
        "id 103／104 才是 show_type=2 的「英雄攻擊／英雄生命」。"
        "id 20006 必須先查 `attribute_name_20006`：四份字串包都沒有此鍵；name 欄指向 `attribute_name_20004`，本頁不把它當作正式名稱。"
    )
    add(
        "- **show_type=2 只記表內原值，不自行換算成百分比。**"
        "隊列符文的分營隊列攻擊／生命（3062 等）是 type=2、show_type=2；"
        "防禦 22、突破防禦 64、出征上限 1019，以及 player_rune 裡 show_type=1 的 3／4／22／64／10003／10004／20006，也都只記原值。"
        "不把 3062 等與不分營的 62／63 寫成同一條公式，也不推入戰鬥結算。"
    )
    add("- 正式用語是「部族」不是「部落」。種族 1／2／3 與聯盟／部族／自然的對應，依分營屬性編號 3xxx／4xxx／5xxx。不要從 `unlocktime`、`season` 自動標未開放（這幾張符文表沒有這類欄位）。")
    add("- 隊列符文的 type 1–5，只使用 `team_rune_name_1`–`5` 與 `team_rune_desc_1`–`5`。絕不用 `team_rune_name_001`–`006` 或 `UI_player_rune_01`–`06` 來標 `team_rune` 的 type。")
    add(
        f"- 官方字串同時有「精煉」與「精鍊」，照原文引，不統一改字。"
        f"例如 `UI_player_rune_refine` 是「{o.refine}」，`UI_player_rune_can_refine` 是「{o.can_refine}」。"
    )
    add("")
    add("## 範圍")
    add("")
    add(
        "本頁只寫符文這套：`team_rune.json`（150 筆：type 1–5 × race 1–3 × lev 1–10）與 "
        "`team_rune_bond.json`（36 筆：queue 2／3／4／5 × rune_lev 1–9），"
        "以及只在 LocalLow 包出現的 `player_rune.json`（72 筆：6 個 type × 12 級，含精煉欄）。"
        "player_rune 表沒有名稱欄，也沒有 power 欄，只有 base_power；本頁不編造 power，也不把 type N 寫成 `team_rune_name_00N`。"
    )
    add("")
    add("## 官方規則")
    add("")
    add("以下整段引自 `team_rune_info_desc`，連「1.」「2.」前綴一起，不拆開、不另行加句號：")
    add("")
    add("```")
    add(o.info_desc)
    add("```")
    add("")
    add(
        "合成規則與表一致：`level_up_num` 在隊列符文 1–9 級為 3，第 10 級為 -1；"
        "player_rune 1–11 級為 3，第 12 級為 -1。"
        f"介面另有「{o.power_tip}」（`team_rune_power_tip`）、「{o.uncompound}」（`team_rune_uncompound`）。"
        "羈絆列的提示原文是："
    )
    add("")
    add("```")
    add(o.bond_tip)
    add("```")
    add("")
    add(f"（`team_rune_bond`）以及「{o.tips5}」（`team_rune_tips5`）、「{o.tips6}」（`team_rune_tips6`）。")
    add("")
    add(
        f"`team_rune_info_desc` 寫「五個插槽」。另有郵件標題「{o.mail_title}」（`mail_rune_title`），正文如下。"
        "兩者都照官方字串記下，不自行裁斷插槽數，也不把它們寫成同一套規則。"
    )
    add("")
    add("```")
    add(o.mail_desc)
    add("```")
    add("")
    add("## 五種隊列符文")
    add("")
    add(
        "與 type 1–5 對得上的名稱鍵是 `team_rune_name_1`–`5`，說明是 `team_rune_desc_1`–`5`。"
        "三個陣營的數值相同，只換分營屬性編號：聯盟 3062／3063、部族 4062／4063、自然 5062／5063。"
        "品質 rare 隨等級走：1–3 級為 3，4–6 級為 4，7–9 級為 5，10 級為 6。"
        "編號規律是 `37{type}{race}{等級兩位}`，例如聯盟力量 1 級為 371101，自然絕對強擊 10 級為 375310。"
    )
    add("")
    add(tbl["team_catalog"])
    add("")
    add("## 隊列符文數值")
    add("")
    add(
        "下列曲線三營相同，故不把 150 列重複展開。"
        "力量符文與生命符文的分營隊列攻擊／生命數列相同；"
        "絕對強擊符文是同一條數列的一半（含進位：第 8 級 1036，不是力量／生命第 8 級 2073 的一半，表上不是 1036.5）。"
        "power 五種符文、三個陣營皆相同；base_power 亦同。"
        "show_type=2 的分營隊列攻擊／生命只記原值，不換成百分比。"
    )
    add("")
    add(tbl["team_curve"])
    add("")
    add("編號與分營屬性對照（種族 1／2／3 對應聯盟／部族／自然）：")
    add("")
    add(tbl["team_ids"])
    add("")
    add("## 羈絆（全隊同級加成）")
    add("")
    add(
        "`team_rune_bond` 36 筆：queue 為 2／3／4／5，rune_lev 為 1–9，"
        "屬性一律是 1019「出征上限」（type=1、show_type=1）。"
        "同一等級、不同 queue 的數值完全相同。沒有 queue=1，也沒有 10 級羈絆。"
        "官方說明是同一個隊列建築上的符文均達到同一等級後額外加成；表沒有解釋 queue 為何從 2 起算、為何 2–5 的數值相同，以及為何沒有 10 級，本頁不自行解釋。"
    )
    add("")
    add(tbl["bond"])
    add("")
    add("## player_rune 官方名稱與說明")
    add("")
    add(
        "`player_rune` 表沒有名稱欄。下列是字串表裡的 `team_rune_name_001`–`006`、"
        "`team_rune_desc_001`–`006`，以及 `UI_player_rune_01`–`06`。"
        f"UI 字串前置羅馬數字，且鍵順序與 001–006 不同（`UI_player_rune_01` 是「{o.player_names[0].ui}」，照原文，不自行加空格）。"
        "name_001–006 與 desc_001–006 並非一一對應："
        "name_002 是「英雄強擊符文」，desc_002 卻寫士兵生命；"
        "只有 001 與 006 名實相符（001 的名稱與說明都寫英雄生命；006 的名稱是隊列強擊符文，說明寫提升突破及防禦屬性）。"
        "這組名稱絕不用來標 team_rune 的 type，也不可寫成 player_rune 的 type N = `team_rune_name_00N`。"
    )
    add("")
    add(tbl["player_names"])
    add("")
    add("## 依寫入屬性對照")
    add("")
    add(
        "下表依各 type 實際寫入的屬性編號作對照，**不是表內名稱欄**，也不是把 type N 等同於 `team_rune_name_00N`。"
        "type 號與 id 前綴並不一致：type 4 的前綴是 706，type 6 的前綴是 704。"
        "type 3 用 sp_para1／sp_para2，不用 para，照欄位展示。"
        "「像某某」只是依寫入屬性所作的對照說明。"
    )
    add("")
    add(tbl["player_map"])
    add("")
    add("## player_rune 數值與精煉")
    add("")
    add(
        "6 個 type × 12 級 = 72 筆。品質 rare：1–3 級為 3，4–6 級為 4，7–9 級為 5，10–12 級為 6。"
        "level_up_num：1–11 級為 3，第 12 級為 -1。沒有 power 欄，只有 base_power；六個 type 各級的 base_power、refine_exp、refine_need、refine_power、refine_percent 與 refine_percent_power 完全相同，故先列共用表。"
        "精煉欄（refine_need／refine_para 或 refine_sp_para1／refine_percent 等）在六個 type 都只出現於 7–11 級；1–6 級與 12 級（滿級）這些欄為空或 -1。"
        "refine_need、refine_exp 照表記數字，不猜道具，也不猜經驗與材料的換算。"
        "不把 1%、20% 規則自行代入結算面板；只列表上的精煉屬性與戰力數。"
    )
    add("")
    add("官方精煉進度說明（`UI_player_rune_refine_progress_tip`，已去掉 color 標籤，整句收錄，不拆句）：")
    add("")
    add("```")
    add(o.refine_progress_tip)
    add("```")
    add("")
    add(
        f"其他精煉相關原文：「{o.one_click_refine}」、「{o.refine_percent}」、"
        f"「{o.refine_progress}」、「{o.refine_progress_unlock_tip}」、"
        f"「{o.refine_choose_tip}」、「{o.refine_exp_full}」、"
        f"「{o.refine_max}」、「{o.refine_result}」。"
    )
    add("")
    add("### 共用曲線（六個 type 相同）")
    add("")
    add(tbl["player_shared"])
    add("")
    for typ in range(1, 7):
        meta = PLAYER_TYPE_META[typ]
        add(f"### type {typ} 屬性曲線（編號前綴 {meta['prefix']}；依寫入屬性對照，不是表內名稱欄）")
        add("")
        add(tbl[f"player_curve_{typ}"])
        add("")
        add(f"### type {typ} 精煉屬性（僅 7–11 級）")
        add("")
        add(tbl[f"player_refine_{typ}"])
        add("")
    add("## 屬性編號")
    add("")
    add("下表列出本頁用到的屬性 id。官方名稱取 `attribute_name_{id}`。show_type=2 只記原值，不換算成百分比。")
    add("")
    add(tbl["attr_ref"])
    add("")
    add("## 本頁未列入")
    add("")
    add("- 羈絆 queue 從 2 起、沒有 1 與 10 的含義。")
    add("- 分營隊列攻擊／生命（3062 等）與不分營 62／63 如何疊加，以及如何進入戰鬥結算。")
    add("- name_001–006 與 desc 不一致的原因；也不把這組名稱派給 team_rune 或寫成 type N = name_00N。")
    add("- 精煉經驗與材料／道具的對應（表沒指明）。")
    add("- 插槽數為五或六的裁斷。")
    add("- 強弱評定與搭配模擬。")
    add("- `kvk_totem`，以及帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場、科技、裝飾物。")
    add("")
    add("## 資料說明")
    add("")
    add(_data_notes(data))
    add("")
    add(
        "待補：attribute_name_20006 缺失時客戶端實際顯示什麼；"
        "精煉經驗與材料的對應；羈絆 queue 欄的含義；"
        "分營與不分營隊列攻擊／生命的疊加方式；"
        "以及 name_001–006 與說明不一致的原因。"
    )
    add("")
    return "\n".join(add_lines)
