"""Compile the published 寵物 catalog tables."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .exclusive_tables import md_table
from .highlight import highlight, highlight_lines
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT
from .strings import clean, fmt_num, has_key, t
from .tables import load_table


# 寵物總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫 2026-11-24。
PET_DATA_CUTOFF = "2026-11-24"
PET_DATA_PACK = "app-1.129.12_table-1.0.43173"
PET_DATA_PACKED = "2026-11-22 23:33"

PARK_INDEX = 160
PARK_KEY_LEVELS = (0, 1, 10, 11, 20, 31, 35, 40)
EXPECTED_PET_IDS = (
    830001, 830002, 830003,
    840001, 840002, 840003, 840004, 840005, 840006, 840007, 840008,
    840009, 840010, 840011, 840012, 840013, 840014, 840015, 840016,
    840017, 840018,
)
LEVEL_COST_TOTAL = 829700
GUIDEBOOK_EXP_TOTAL = 126760
PARK_FF = {0: 0, 1: 300, 20: 10950, 40: 140550}

# 升級消耗 2–90 級的規則段；91–120 級另列（91 級降為 5900，其後多為 +100，部分級 +200）。
COST_BANDS = (
    ((2, 5), 100, 50),
    ((6, 29), 300, 100),
    ((30, 39), 2750, 150),
    ((40, 49), 4300, 200),
    ((50, 70), 6350, 250),
    ((71, 90), 11600, 300),
)
COST_91_120 = (
    5900, 6000, 6100, 6200, 6400, 6500, 6600, 6800, 6900, 7000,
    7200, 7300, 7400, 7600, 7700, 7800, 8000, 8100, 8200, 8400,
    8500, 8600, 8800, 8900, 9000, 9200, 9300, 9400, 9600, 9700,
)
COST_91_200_LEVELS = (95, 98, 101, 104, 107, 110, 113, 116, 119)

TABLE_SHA256 = {
    "pet_detail.json": "2ed5f2cb88758195a59e7aa36e7cb4d5dc901325503489874fdea1ca3c12f090",
    "pet_level.json": "13a6cb17947dcd98a5eeb7b1d0ff36598dc58346666fed66456de07d4ea39c89",
    "pet_break.json": "0c75486e6b52b73712d522339b807346e405dfa0e6556335928b47d383bcdd61",
    "pet_guidebook.json": "1110101f3592615b15932fcac2981414c781c61c57577d0996dee87baf1e9088",
    "pet_honor.json": "553e7ec52c612b65f2197c9085843f73585785bdab6259e4e71f95b2fde14b8f",
    "pet_honor_bonus.json": "f6123d0681a9557357f3a268443d00f5f420e4f15ce7d2ad7d3e42f71cb93afd",
    "pet_incubate.json": "07b5ce9a1afa2bba0dcc4288618d0167273f9ac5743644fc077a6a9af6d7a286",
    "pet_egg_task.json": "1a890a67fe6a0c4b6d9aae4b6c74b76ea9c513f3b247133840ba7592dc95bf8c",
    "pet_food_convert.json": "5317a4e162f6f08dbbcac60e46dbf5844903f45713744fc04cf537a2d9b6429b",
    "pet_achievement.json": "a04838371acede78979ad01476e160e08aef901e5421d8bbe7fb6183d50dd82e",
    "citybuilding_lvup.json": "2d85b94154e3a0f6f481805d49bace3e8ee8eccd84dfae79ac938743e75724d3",
    "citybuilding_lvup_new.json": "436ca7dcdba0f5aa962cfbbb728fd4b9d9ac3a3042154a2ec3e5c43a60158abf",
    "hero_component.json": "c8530f16b07bbea7f9084c74826b9c8a35486186c8af87bc258373f3ef1118e8",
    "skin.json": "50db2a4731994ada67fdbf2b45e623585d7360dd3bdec076b468516ae975eae0",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "function.json": "fb826efa087a122ad37682d1707bf877ce56970d92fbc44127ca390e72309afc",
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
    "本頁列出官方界面所稱的「寵物」：21 隻的名稱與型態、寵物樂園關鍵級、升級與突破曲線、"
    "轉化率與全英雄加成、滿突破技能原文、圖鑑與榮譽牆，以及孵化與搜索規則。"
    "英靈不是寵物，本頁不把它們寫在一起。"
)

USED_KEYS: set[str] = set()


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def official_text(key, default: str = "") -> str:
    if key is None or key == "":
        return default
    USED_KEYS.add(str(key))
    return clean(t(key, default))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _int(value) -> int:
    return int(float(str(value).strip()))


def parse_attr_map(raw) -> dict[int, int]:
    """Parse id|value or id|value|flag (park string_para2 uses three parts)."""
    out: dict[int, int] = {}
    if raw in (None, "", [], {}, -1):
        return out
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[_int(k)] = _int(v)
        return out
    items: list = raw if isinstance(raw, list) else [raw]
    if items and isinstance(items[0], (list, tuple)) and len(items[0]) >= 2:
        for item in items:
            out[_int(item[0])] = _int(item[1])
        return out
    for item in items:
        parts = str(item).split("|")
        if len(parts) >= 2:
            out[_int(parts[0])] = _int(parts[1])
    return out


def format_attr_raw(raw) -> str:
    if raw in (None, "", [], {}, -1):
        return EMPTY
    if isinstance(raw, list):
        return "；".join(str(x) for x in raw)
    return str(raw)


def format_cost(raw) -> str:
    if raw in (None, "", [], -1):
        return EMPTY
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, (list, tuple)):
                parts.append("|".join(str(x) for x in item))
            else:
                parts.append(str(item))
        return "、".join(parts)
    return str(raw)


def format_unlocktime(raw) -> str:
    if raw in (None, "", -1):
        return EMPTY
    text = str(raw)
    if "|" in text and text.count("|") == 1:
        a, b = text.split("|", 1)
        return f"{a.strip()} 至 {b.strip()}"
    return text


def format_params(params) -> str:
    if params in (None, "", [], -1):
        return "無"
    return "[" + ", ".join(fmt_num(x) for x in params) + "]"


def fill_skill_segment(template: str, params: list) -> str:
    """Fill one desc segment. {n} always reads params[n]; leftover params are not shifted."""
    text = clean(template or "")
    if not text:
        return text

    def repl(match: re.Match) -> str:
        i = int(match.group(1))
        if i >= len(params) or params[i] in (None, ""):
            return match.group(0)
        return fmt_num(params[i])

    return re.sub(r"\{(\d+)\}", repl, text)


def leftover_params(template: str, params: list) -> list[tuple[int, object]]:
    text = clean(template or "")
    used = {int(m) for m in re.findall(r"\{(\d+)\}", text)}
    out = []
    for i, val in enumerate(params or []):
        if i not in used:
            out.append((i, val))
    return out


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def attr_label(attr_id: int, attr_by: dict) -> str:
    name = official_text(f"attribute_name_{attr_id}")
    if name:
        return name
    row = attr_by.get(int(attr_id)) or {}
    return official_text(row.get("name") or "")


def faction_from_group(group_id: int) -> str:
    hundred = group_id // 100
    if hundred == 1:
        return "聯盟"
    if hundred == 2:
        return "部族"
    if hundred == 3:
        return "自然"
    if group_id == 401:
        return "非三營（榮譽為英雄生命）"
    return f"未分組（{group_id}）"


def expected_level_cost(level: int) -> int:
    if level == 1:
        return -1
    if 2 <= level <= 90:
        for (lo, hi), start, step in COST_BANDS:
            if lo <= level <= hi:
                return start + (level - lo) * step
        raise KeyError(level)
    if 91 <= level <= 120:
        return COST_91_120[level - 91]
    raise KeyError(level)


@dataclass
class SkillSegment:
    step: int  # 1 = 基礎 (desc1), 2+ = 升至 N 級追加
    template_key: str
    template: str
    params: list
    filled: str
    leftover: list[tuple[int, object]]


@dataclass
class SkillDef:
    sid: int
    name_key: str
    name: str
    name_missing: bool
    maxlv: int
    segments: list[SkillSegment]


@dataclass
class Morph:
    break_level: int
    quality: int
    skin_id: int
    name_key: str
    name: str
    name_changed: bool
    skin_changed: bool


@dataclass
class BreakRow:
    break_level: int
    quality: int
    conversion_rate: int
    skill_ids: list[int]
    skill_levels: list[int]
    attr_role: dict[int, int]
    cost: object
    extra_cost: object
    pet_lv_min: int
    pet_lv_max: int
    season_limit: object
    season_limit_new: object
    skin_id: int
    name_key: str
    name: str
    fightforce: int


@dataclass
class LevelKey:
    level: int
    cost: int
    cost_extra: object
    attr_30004: int
    fightforce: int
    decomposed_get: object


@dataclass
class PetInfo:
    pid: int
    group_id: int
    break_max: int
    origin_break: int
    decomposed_get: int
    guidebook_openday: int
    hide: int
    is_lock: int
    component_unlock: list
    unlocktime: object
    guidebook_server_list: object
    base_name: str
    base_name_key: str
    base_skin: int
    quality_start: int
    quality_end: int
    faction: str
    morphs: list[Morph]
    name_constant: bool
    breaks: list[BreakRow]
    skills: list[SkillDef]
    cost_group: str  # "830" | "840a" | "840b"
    attr_ids: tuple[int, int]
    attr_origin: tuple[int, int]
    attr_max: tuple[int, int]
    level_keys: list[LevelKey]
    extra_from: int | None
    extra_to: int | None


@dataclass
class ParkLevel:
    lv: int
    para1: int
    para2: int
    string_para2: object
    attrs: dict[int, int]
    fightforce: int
    cost1: object
    cost2: object
    cost3_lvup: object
    cost3_new: object
    build_time: object
    build_time_new: object
    pre: object
    des_keys: list[str]
    note: str


@dataclass
class HonorRow:
    quality: int
    attr_id: int
    attr_name: str
    attr_value: int
    combat: int
    need_chip: str


@dataclass
class HonorBonus:
    group: int
    attr_id: int
    attr_name: str
    values: dict[int, int]
    combats: dict[int, int]
    pets: list[str]


@dataclass
class GuideLevel:
    level: int
    exp: int
    atk: int
    hp: int
    fightforce: int


@dataclass
class IncubateRow:
    iid: int
    cost: object
    time: int
    pet_reward: object
    is_guaranteed: object
    guaranteed_pet_id: object
    probability_time: object
    guaranteed_reward: object
    egg_name: str
    egg_desc: str
    in_detail: bool


@dataclass
class Official:
    system_name: str
    partner_dir: str
    catalog_name: str
    honour_name: str
    park_name: str
    park_des: str
    park_des_keys: dict[str, str]
    attr_cd: str
    tips: dict[str, str]
    titles: dict[str, str]
    formula_1: str
    formula_2: str
    attr_percent: str
    attr_break_all: str
    function_closed: str
    honour_info: str
    honour_title: str
    reborn_tips2: str
    need_break_tips: str
    title020: str
    title003_dec: str
    quality_common: str
    egg_names: dict[str, str]
    egg_descs: dict[str, str]
    box_good_name: str
    box_good_desc: str
    box_rare_name: str
    box_rare_desc: str
    cactus_egg_name: str
    cactus_egg_desc: str
    food_name: str
    food_desc: str
    essence_name: str
    essence_desc: str
    wood: str
    stone: str
    castle: str
    guaranteed: str
    attr_names: dict[int, str]
    attr_1133_key: str
    attr_1133_name: str
    attr_1133_has_name_key: bool
    show_types: dict[int, int]
    shelter: dict[str, str]


@dataclass
class TablesData:
    official: Official
    pets: list[PetInfo]
    park: list[ParkLevel]
    park_para1: list[tuple[int, int, int]]
    park_para2: list[tuple[int, int, int]]
    honor: list[HonorRow]
    honor_bonus: list[HonorBonus]
    guidebook: list[GuideLevel]
    guidebook_exp_total: int
    incubate: list[IncubateRow]
    egg_tasks: list[dict]
    food_convert: list[dict]
    function63: dict
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
        live_sha = file_sha256(live_path)
        live_bytes = live_path.stat().st_size
        entry = {
            "bytes": live_bytes,
            "sha256": live_sha,
            "identical": {},
            "present": {},
        }
        data = json.loads(live_path.read_text(encoding="utf-8-sig"))
        entry["rows"] = len(data) if isinstance(data, list) else None
        for pack, folder in PACK_DATA_DIRS.items():
            path = folder / name
            if not path.exists():
                entry["present"][pack] = False
                entry["identical"][pack] = False
                continue
            entry["present"][pack] = True
            entry["identical"][pack] = file_sha256(path) == live_sha and path.stat().st_size == live_bytes
        result[name] = entry
    return result


def _intervals(rows: list[dict], key: str) -> list[tuple[int, int, int]]:
    start = _int(rows[0]["lv"])
    prev = _int(rows[0][key])
    out: list[tuple[int, int, int]] = []
    for row in rows[1:]:
        val = _int(row[key])
        lv = _int(row["lv"])
        if val != prev:
            out.append((start, lv - 1, prev))
            start = lv
            prev = val
    out.append((start, _int(rows[-1]["lv"]), prev))
    return out


def _skill_def(comp: dict) -> SkillDef:
    name_key = str(comp.get("name") or "")
    name_missing = bool(name_key) and not has_key(name_key)
    # 缺鍵（如鐵喙前三個技能名）不列入 USED_KEYS，以免被當成歸檔缺漏。
    name = official_text(name_key) if name_key and not name_missing else ""
    segments: list[SkillSegment] = []
    maxlv = _int(comp.get("maxlv") or 0)
    for step in range(1, maxlv + 1):
        key = comp.get(f"desc{step}")
        params = list(comp.get(f"desc_parameter{step}") or [])
        tmpl = official_text(key) if key not in (None, "", -1) else ""
        filled = fill_skill_segment(tmpl, params)
        segments.append(SkillSegment(
            step=step,
            template_key=str(key or ""),
            template=tmpl,
            params=params,
            filled=filled,
            leftover=leftover_params(tmpl, params),
        ))
    return SkillDef(
        sid=_int(comp["id"]),
        name_key=name_key,
        name=name,
        name_missing=name_missing,
        maxlv=maxlv,
        segments=segments,
    )


def skill_lines(skill: SkillDef, level: int) -> list[str]:
    if level <= 0:
        return ["未解鎖"]
    lines: list[str] = []
    for seg in skill.segments:
        if seg.step > level:
            break
        if seg.step == 1:
            prefix = "基礎："
        else:
            prefix = f"升至 {seg.step} 級追加："
        line = prefix + seg.filled
        if seg.leftover:
            left = ", ".join(f"{{{i}}} 未使用（{fmt_num(v)}）" for i, v in seg.leftover)
            line += f"（原文：{seg.template}；參數：{format_params(seg.params)}；{left}，不自行挪位）"
        lines.append(line)
    return lines or ["（無文案）"]


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    for name, expected in TABLE_SHA256.items():
        path = DATA_DIR / name
        got = file_sha256(path)
        if got != expected:
            raise ValueError(f"{name} sha256 mismatch: {got} != {expected}")

    detail_raw = load_table("pet_detail.json")
    level_raw = load_table("pet_level.json")
    break_raw = load_table("pet_break.json")
    guidebook_raw = load_table("pet_guidebook.json")
    honor_raw = load_table("pet_honor.json")
    honor_bonus_raw = load_table("pet_honor_bonus.json")
    incubate_raw = load_table("pet_incubate.json")
    egg_task_raw = load_table("pet_egg_task.json")
    food_raw = load_table("pet_food_convert.json")
    achievement_raw = load_table("pet_achievement.json")
    lvup_raw = load_table("citybuilding_lvup.json")
    lvup_new_raw = load_table("citybuilding_lvup_new.json")
    components = load_table("hero_component.json")
    skins_raw = load_table("skin.json")
    attributes = load_table("attribute.json")
    functions = load_table("function.json")

    if len(detail_raw) != 21:
        raise ValueError(f"pet_detail.json expected 21 rows, got {len(detail_raw)}")
    if len(level_raw) != 2520:
        raise ValueError(f"pet_level.json expected 2520 rows, got {len(level_raw)}")
    if len(break_raw) != 396:
        raise ValueError(f"pet_break.json expected 396 rows, got {len(break_raw)}")
    if len(guidebook_raw) != 58:
        raise ValueError(f"pet_guidebook.json expected 58 rows, got {len(guidebook_raw)}")
    if len(honor_raw) != 2:
        raise ValueError(f"pet_honor.json expected 2 rows, got {len(honor_raw)}")
    if len(honor_bonus_raw) != 100:
        raise ValueError(f"pet_honor_bonus.json expected 100 rows, got {len(honor_bonus_raw)}")
    if len(incubate_raw) != 5:
        raise ValueError(f"pet_incubate.json expected 5 rows, got {len(incubate_raw)}")
    if len(egg_task_raw) != 3:
        raise ValueError(f"pet_egg_task.json expected 3 rows, got {len(egg_task_raw)}")
    if len(food_raw) != 9:
        raise ValueError(f"pet_food_convert.json expected 9 rows, got {len(food_raw)}")
    if len(achievement_raw) != 393:
        raise ValueError(f"pet_achievement.json expected 393 rows, got {len(achievement_raw)}")

    attr_by = {r["id"]: r for r in attributes}
    skin_by = {r["id"]: r for r in skins_raw}
    comp_by = {r["id"]: r for r in components}
    detail_by = {r["id"]: r for r in detail_raw}

    ids = tuple(r["id"] for r in detail_raw)
    if ids != EXPECTED_PET_IDS:
        raise ValueError(f"unexpected pet ids: {ids}")

    for row in detail_raw:
        if row["hide"] != 0 or row["is_lock"] != 0:
            raise ValueError(f"{row['id']} hide/is_lock drifted")
        if list(row["component_unlock"]) != [10, 20, 30, 40]:
            raise ValueError(f"{row['id']} component_unlock drifted")
        if row["id"] <= 830003:
            if (row["break_max"], row["origin_break"], row["decomposed_get"], row["guidebook_openday"]) != (17, 0, 100, 3):
                raise ValueError(f"{row['id']} early-pet fields drifted")
        else:
            if (row["break_max"], row["origin_break"], row["decomposed_get"], row["guidebook_openday"]) != (23, 5, 600, 5):
                raise ValueError(f"{row['id']} late-pet fields drifted")

    servers = [tuple(r["guidebook_server_list"]) for r in detail_raw]
    if len(set(servers)) != 1:
        raise ValueError("guidebook_server_list is not identical for all 21 pets")

    breaks_by: dict[int, list[dict]] = defaultdict(list)
    for row in break_raw:
        breaks_by[_int(row["pet_id"])].append(row)
    for pid, rows in breaks_by.items():
        rows.sort(key=lambda r: _int(r["break_level"]))
        origin = _int(detail_by[pid]["origin_break"])
        bmax = _int(detail_by[pid]["break_max"])
        levels = [_int(r["break_level"]) for r in rows]
        if levels != list(range(origin, bmax + 1)):
            raise ValueError(f"{pid} break levels {levels} != {origin}–{bmax}")

    levels_by: dict[int, list[dict]] = defaultdict(list)
    for row in level_raw:
        levels_by[_int(row["pet_id"])].append(row)
    for pid, rows in levels_by.items():
        rows.sort(key=lambda r: _int(r["level"]))
        if [ _int(r["level"]) for r in rows ] != list(range(1, 121)):
            raise ValueError(f"{pid} is not 1–120")
        if any(_int(r["build_level_limit"]) != 1 for r in rows):
            raise ValueError(f"{pid} build_level_limit drifted")
        for r in rows:
            if _int(r["cost"]) != expected_level_cost(_int(r["level"])):
                raise ValueError(f"{pid} level {r['level']} cost drifted: {r['cost']}")

    # 21 隻 cost 主欄相同
    base_costs = [_int(r["cost"]) for r in levels_by[830001]]
    total = sum(c for c in base_costs if c > 0)
    if total != LEVEL_COST_TOTAL:
        raise ValueError(f"upgrade cost total {total} != {LEVEL_COST_TOTAL}")
    for pid, rows in levels_by.items():
        if [_int(r["cost"]) for r in rows] != base_costs:
            raise ValueError(f"{pid} cost curve differs")

    skill_ids: set[int] = set()
    for row in break_raw:
        for sid in row.get("skill") or []:
            if sid not in (None, 0, -1):
                skill_ids.add(_int(sid))
    if len(skill_ids) != 81:
        raise ValueError(f"expected 81 skill ids, got {len(skill_ids)}")
    missing_comp = sorted(s for s in skill_ids if s not in comp_by)
    if missing_comp:
        raise ValueError(f"skill ids missing in hero_component: {missing_comp}")

    # official strings
    attr_ids_needed = (30004, 103, 104, 3103, 3104, 4103, 4104, 5103, 5104, 3, 4, 1191, 1192)
    attr_names = {aid: official_text(f"attribute_name_{aid}") for aid in attr_ids_needed}
    if not attr_names[30004]:
        raise ValueError("attribute_name_30004 missing")
    attr_1133 = attr_by[1133]
    attr_1133_key = str(attr_1133.get("name") or "")
    attr_1133_name = official_text(attr_1133_key) if attr_1133_key else ""
    official = Official(
        system_name=official_text("formation_d5") or official_text("home_func_name_6"),
        partner_dir=official_text("influence_level_12"),
        catalog_name=official_text("pet_title003"),
        honour_name=official_text("pet_honour_006"),
        park_name=official_text("citybuilding_name_160"),
        park_des=official_text("citybuilding_des_160"),
        park_des_keys={
            "pet_building_attr_place": official_text("pet_building_attr_place"),
            "pet_building_attr_egg_level": official_text("pet_building_attr_egg_level"),
            "pet_building_attr_cd": official_text("pet_building_attr_cd"),
            "attribute_name_1192": official_text("attribute_name_1192"),
            "attribute_name_1191": official_text("attribute_name_1191"),
        },
        attr_cd=official_text("pet_building_attr_cd"),
        tips={k: official_text(k) for k in (
            "pet_info_tips_1", "pet_info_tips_2", "pet_info_tips_3", "pet_info_tips_4",
            "pet_info_tips_5", "pet_info_tips_6", "pet_info_tips_7", "pet_info_tips_8",
            "pet_attr_info_tips",
        )},
        titles={k: official_text(k) for k in (
            "pet_info_title_01", "pet_info_title_02", "pet_info_title_03",
            "pet_title023", "pet_title026",
        )},
        formula_1=official_text("pet_function_attr_tips_1"),
        formula_2=official_text("pet_function_attr_tips_2"),
        attr_percent=official_text("pet_function_attr_percent"),
        attr_break_all=official_text("pet_function_attr_break_all"),
        function_closed=official_text("pet_egg_13"),
        honour_info=official_text("pet_honour_info_1"),
        honour_title=official_text("pet_honour_info_title"),
        reborn_tips2=official_text("pet_function_reborn_tips2"),
        need_break_tips=official_text("pet_function_need_break_tips"),
        title020=official_text("pet_title020"),
        title003_dec=official_text("pet_title003_dec"),
        quality_common=official_text("pet_function_quality_type_1"),
        egg_names={
            "pet_egg_05": official_text("pet_egg_05"),
            "pet_egg_08": official_text("pet_egg_08"),
            "pet_egg_09": official_text("pet_egg_09"),
        },
        egg_descs={
            "goods_desc_30001": official_text("goods_desc_30001"),
            "goods_desc_30002": official_text("goods_desc_30002"),
            "goods_desc_30003": official_text("goods_desc_30003"),
        },
        box_good_name=official_text("goods_name_160307"),
        box_good_desc=official_text("goods_desc_160307"),
        box_rare_name=official_text("goods_name_160308"),
        box_rare_desc=official_text("goods_desc_160308"),
        cactus_egg_name=official_text("goods_name_31001"),
        cactus_egg_desc=official_text("goods_desc_31001"),
        food_name=official_text("goods_name_284"),
        food_desc=official_text("goods_desc_284"),
        essence_name=official_text("goods_name_289"),
        essence_desc=official_text("goods_desc_289"),
        wood=official_text("top_resource_name_4"),
        stone=official_text("top_resource_name_5"),
        castle=official_text("citybuilding_name_117"),
        guaranteed=official_text("pet_probability"),
        attr_names=attr_names,
        attr_1133_key=attr_1133_key,
        attr_1133_name=attr_1133_name,
        attr_1133_has_name_key=has_key("attribute_name_1133"),
        show_types={aid: _int(attr_by[aid]["show_type"]) for aid in attr_ids_needed + (1133,)},
        shelter={
            "聯盟的庇護": official_text("hero_skill_name_8400104"),
            "部落的庇護": official_text("hero_skill_name_8400204"),
            "自然的庇護": official_text("hero_skill_name_8400304"),
            "魔狗的庇護": official_text("hero_skill_name_8401704"),
        },
    )
    if official.shelter["部落的庇護"] != "部落的庇護":
        raise ValueError("部落的庇護 official string drifted")
    if official.attr_1133_has_name_key:
        raise ValueError("attribute_name_1133 unexpectedly present")
    if official.show_types[30004] != 1:
        raise ValueError("30004 show_type drifted")
    for aid in (103, 104, 3103, 3104, 4103, 4104, 5103, 5104):
        if official.show_types[aid] != 2:
            raise ValueError(f"{aid} show_type drifted")
    for aid in (3, 4):
        if official.show_types[aid] != 1:
            raise ValueError(f"{aid} show_type drifted")

    func63_rows = [r for r in functions if r["id"] == 63]
    if len(func63_rows) != 1:
        raise ValueError("function id 63 missing")
    f63 = func63_rows[0]
    if f63.get("openPanel") != "show_pet_list_panel":
        raise ValueError("function 63 openPanel drifted")
    if f63.get("func_open_param") != "7|160|1":
        raise ValueError("function 63 func_open_param drifted")
    if official_text(f63.get("tips")) != official.function_closed:
        raise ValueError("function 63 tips drifted")
    if has_key(f63.get("name")):
        raise ValueError("function 63 name key unexpectedly present in strings")
    function63 = {
        "id": 63,
        "name_key": f63.get("name"),
        "name": official_text(f63.get("name")) if has_key(f63.get("name")) else "",
        "openPanel": f63.get("openPanel"),
        "func_open_param": f63.get("func_open_param"),
        "tips_key": f63.get("tips"),
        "tips": official.function_closed,
    }

    def skin_name(skin_id: int) -> tuple[str, str, str]:
        skin = skin_by.get(skin_id)
        if not skin:
            raise ValueError(f"skin {skin_id} missing")
        atlas = skin.get("head_Atlas") or skin.get("headAtlas")
        if atlas != "Atlas/UI_Pet_Head":
            raise ValueError(f"skin {skin_id} atlas {atlas}")
        key = str(skin.get("name") or "")
        return key, official_text(key), atlas

    pets: list[PetInfo] = []
    for drow in detail_raw:
        pid = _int(drow["id"])
        brows = breaks_by[pid]
        first = brows[0]
        last = brows[-1]
        base_key, base_name, _ = skin_name(_int(first["pet_skin_id"]))
        morphs: list[Morph] = []
        prev_skin = _int(first["pet_skin_id"])
        prev_key, prev_name, _ = skin_name(prev_skin)
        morphs.append(Morph(
            break_level=_int(first["break_level"]),
            quality=_int(first["quality"]),
            skin_id=prev_skin,
            name_key=prev_key,
            name=prev_name,
            name_changed=False,
            skin_changed=False,
        ))
        for row in brows[1:]:
            sid = _int(row["pet_skin_id"])
            key, name, _ = skin_name(sid)
            if sid != prev_skin or key != prev_key or name != prev_name:
                morphs.append(Morph(
                    break_level=_int(row["break_level"]),
                    quality=_int(row["quality"]),
                    skin_id=sid,
                    name_key=key,
                    name=name,
                    name_changed=name != prev_name or key != prev_key,
                    skin_changed=sid != prev_skin,
                ))
                prev_skin, prev_key, prev_name = sid, key, name
        name_constant = len({m.name for m in morphs}) == 1 and len({m.name_key for m in morphs}) == 1
        break_rows: list[BreakRow] = []
        for row in brows:
            sid = _int(row["pet_skin_id"])
            key, name, _ = skin_name(sid)
            skills = [_int(s) for s in (row.get("skill") or [])]
            slv = [_int(s) for s in (row.get("skill_level") or [])]
            break_rows.append(BreakRow(
                break_level=_int(row["break_level"]),
                quality=_int(row["quality"]),
                conversion_rate=_int(row["conversion_rate"]),
                skill_ids=skills,
                skill_levels=slv,
                attr_role=parse_attr_map(row.get("attr_role") or row.get("attr_roles")),
                cost=row.get("cost"),
                extra_cost=row.get("extra_cost"),
                pet_lv_min=_int(row["pet_lv_min"]),
                pet_lv_max=_int(row["pet_lv_max"]),
                season_limit=row.get("season_limit"),
                season_limit_new=row.get("season_limit_new"),
                skin_id=sid,
                name_key=key,
                name=name,
                fightforce=_int(row.get("fightforce") or 0),
            ))
        last_skills = last.get("skill") or []
        skill_defs = [_skill_def(comp_by[_int(sid)]) for sid in last_skills]
        # cost group
        if pid <= 830003:
            cost_group = "830"
        else:
            costs = tuple(
                tuple(r.get("cost") or []) if isinstance(r.get("cost"), list) else (r.get("cost"),)
                for r in brows
            )
            # 火花、達達：6 階起多為單一 2|5|n
            sample = format_cost(brows[1].get("cost")) if len(brows) > 1 else ""
            cost_group = "840b" if pid in (840015, 840017) else "840a"
            if cost_group == "840b" and not str(brows[1].get("cost")).startswith("['2|5|") and format_cost(brows[1].get("cost")) != "2|5|1":
                # still assign by pid; verify later
                pass
        attr0 = break_rows[0].attr_role
        attrm = break_rows[-1].attr_role
        attr_ids = tuple(sorted(attr0))
        if attr_ids != tuple(sorted(attrm)):
            raise ValueError(f"{pid} attr_role ids changed across breaks")
        if len(attr_ids) != 2:
            raise ValueError(f"{pid} attr_role not a pair: {attr_ids}")

        lrows = levels_by[pid]
        level_keys = []
        extra_from = extra_to = None
        for r in lrows:
            amap = parse_attr_map(r.get("attr_team") or r.get("attrs"))
            if 30004 not in amap:
                raise ValueError(f"{pid} lv {r['level']} missing 30004")
            extra = r.get("cost_extra")
            lv = _int(r["level"])
            if extra not in (None, "", -1):
                if extra_from is None:
                    extra_from = lv
                extra_to = lv
            if lv in (1, 2, 8, 10, 20, 30, 40, 50, 60, 70, 80, 83, 90, 100, 110, 119, 120) or extra not in (None, "", -1) and lv in (61, 91):
                level_keys.append(LevelKey(
                    level=lv,
                    cost=_int(r["cost"]),
                    cost_extra=extra,
                    attr_30004=_int(amap[30004]),
                    fightforce=_int(r["fightforce"]),
                    decomposed_get=r.get("decomposed_get"),
                ))
        # always keep standard key levels even if already added
        have = {x.level for x in level_keys}
        for lv in (1, 2, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120):
            if lv not in have:
                r = next(x for x in lrows if _int(x["level"]) == lv)
                amap = parse_attr_map(r.get("attr_team") or r.get("attrs"))
                level_keys.append(LevelKey(lv, _int(r["cost"]), r.get("cost_extra"), _int(amap[30004]), _int(r["fightforce"]), r.get("decomposed_get")))
        # also 8 and 83 for known exceptions
        for lv in (8, 83, 119, 61, 91):
            if lv not in have:
                r = next(x for x in lrows if _int(x["level"]) == lv)
                amap = parse_attr_map(r.get("attr_team") or r.get("attrs"))
                level_keys.append(LevelKey(lv, _int(r["cost"]), r.get("cost_extra"), _int(amap[30004]), _int(r["fightforce"]), r.get("decomposed_get")))
        level_keys = sorted({x.level: x for x in level_keys}.values(), key=lambda x: x.level)

        pets.append(PetInfo(
            pid=pid,
            group_id=_int(drow["group_id"]),
            break_max=_int(drow["break_max"]),
            origin_break=_int(drow["origin_break"]),
            decomposed_get=_int(drow["decomposed_get"]),
            guidebook_openday=_int(drow["guidebook_openday"]),
            hide=_int(drow["hide"]),
            is_lock=_int(drow["is_lock"]),
            component_unlock=list(drow["component_unlock"]),
            unlocktime=drow.get("unlocktime"),
            guidebook_server_list=drow.get("guidebook_server_list"),
            base_name=base_name,
            base_name_key=base_key,
            base_skin=_int(first["pet_skin_id"]),
            quality_start=_int(first["quality"]),
            quality_end=_int(last["quality"]),
            faction=faction_from_group(_int(drow["group_id"])),
            morphs=morphs,
            name_constant=name_constant,
            breaks=break_rows,
            skills=skill_defs,
            cost_group=cost_group,
            attr_ids=attr_ids,  # type: ignore[arg-type]
            attr_origin=(attr0[attr_ids[0]], attr0[attr_ids[1]]),
            attr_max=(attrm[attr_ids[0]], attrm[attr_ids[1]]),
            level_keys=level_keys,
            extra_from=extra_from,
            extra_to=extra_to,
        ))

    if [p.base_name for p in pets] != [
        "史萊姆", "毛茸茸", "噗噗豬", "閃啾啾", "蓬蓬崽", "絨嗚嗚", "蛋仔",
        "仙人掌寶寶", "雪球寶寶", "火苗喵喵", "翠牙苗", "虎寶", "燭寶", "雪團子",
        "時光龍·柯羅諾斯", "天馬", "潮汐蟹", "火花", "疾風", "達達", "鐵喙",
    ]:
        raise ValueError(f"base names drifted: {[p.base_name for p in pets]}")

    slime = next(p for p in pets if p.pid == 830001)
    slime17 = next(r for r in slime.breaks if r.break_level == 17)
    if (slime17.skin_id, slime17.name_key, slime17.name) != (56004, "hero_name_56003", "史萊姆帝皇"):
        raise ValueError(f"slime 17 name/skin drifted: {slime17}")

    # conversion
    for p in pets:
        if p.pid <= 830003:
            if p.breaks[0].conversion_rate != 2000 or p.breaks[-1].conversion_rate != 8800:
                raise ValueError(f"{p.pid} conversion drifted")
        else:
            if p.breaks[0].conversion_rate != 3600 or p.breaks[-1].conversion_rate != 10800:
                raise ValueError(f"{p.pid} conversion drifted")

    # 830 shared conv/quality/skill_levels/attr/cost
    def _830_core(p: PetInfo):
        return [
            (r.break_level, r.conversion_rate, r.quality, tuple(r.skill_levels),
             tuple(sorted(r.attr_role.items())), format_cost(r.cost), format_cost(r.extra_cost),
             r.pet_lv_min, r.pet_lv_max)
            for r in p.breaks
        ]
    if not (_830_core(pets[0]) == _830_core(pets[1]) == _830_core(pets[2])):
        raise ValueError("830xxx break cores differ")

    def _840_core(p: PetInfo):
        return [(r.break_level, r.conversion_rate, r.quality, tuple(r.skill_levels), r.pet_lv_min, r.pet_lv_max) for r in p.breaks]
    late = [p for p in pets if p.pid >= 840001]
    if any(_840_core(p) != _840_core(late[0]) for p in late):
        raise ValueError("840xxx conv/quality/skill/lv core differs")

    expected_attr = {
        (840001, 840002, 840003, 840006, 840008): ((103, 104), (170, 250), (3230, 4750)),
        (840004, 840010, 840011, 840016, 840018): ((3103, 3104), (510, 750), (9690, 14250)),
        (840007, 840009, 840012, 840015): ((4103, 4104), (510, 750), (9690, 14250)),
        (840005, 840013, 840014): ((5103, 5104), (510, 750), (9690, 14250)),
        (840017,): ((103, 104), (510, 750), (9690, 14250)),
    }
    seen = set()
    for pids, (ids_, origin, mx) in expected_attr.items():
        for pid in pids:
            p = next(x for x in pets if x.pid == pid)
            if p.attr_ids != ids_ or p.attr_origin != origin or p.attr_max != mx:
                raise ValueError(f"{pid} attr_role {p.attr_ids} {p.attr_origin} {p.attr_max} != {ids_} {origin} {mx}")
            seen.add(pid)
    if seen != {p.pid for p in late}:
        raise ValueError("attr group coverage drifted")

    for p in pets:
        if p.pid <= 830003:
            if p.attr_ids != (103, 104) or p.attr_origin != (50, 50) or p.attr_max != (900, 900):
                raise ValueError(f"{p.pid} 830 attr drifted")
        if p.pid <= 830003 and (p.extra_from, p.extra_to) != (61, 90):
            raise ValueError(f"{p.pid} cost_extra range {p.extra_from}-{p.extra_to}")
        if p.pid >= 840001 and (p.extra_from, p.extra_to) != (91, 120):
            raise ValueError(f"{p.pid} cost_extra range {p.extra_from}-{p.extra_to}")

    # cost groups
    if {p.pid for p in pets if p.cost_group == "840b"} != {840015, 840017}:
        raise ValueError("840b cost group drifted")
    # confirm first paid cost
    spark = next(p for p in pets if p.pid == 840015)
    if format_cost(spark.breaks[1].cost) != "2|5|1":
        raise ValueError(f"spark cost at 6: {spark.breaks[1].cost}")
    flash = next(p for p in pets if p.pid == 840001)
    if format_cost(flash.breaks[1].cost) != "1|5|1":
        raise ValueError(f"flash cost at 6: {flash.breaks[1].cost}")

    # crossed keys
    snow = next(p for p in pets if p.pid == 840011)
    if snow.skills[2].name_key != "hero_skill_name_8401203" or snow.skills[2].name != "優雅":
        raise ValueError("雪團子 skill 3 key drifted")
    dragon = next(p for p in pets if p.pid == 840012)
    if dragon.skills[2].name_key != "hero_skill_name_8401103" or dragon.skills[2].name != "龍威":
        raise ValueError("時光龍 skill 3 key drifted")
    beak = next(p for p in pets if p.pid == 840018)
    if not all(s.name_missing and not s.name for s in beak.skills[:3]):
        raise ValueError("鐵喙 first three skill names drifted")
    if beak.skills[3].name != "聯盟的庇護":
        raise ValueError("鐵喙 skill 4 drifted")
    dada = next(p for p in pets if p.pid == 840017)
    if dada.skills[2].name_key != "hero_skill_name_84017033" or dada.skills[2].name != "堅硬表皮":
        raise ValueError("達達 skill 3 name key drifted")
    if dada.skills[3].name != "魔狗的庇護":
        raise ValueError("達達 skill 4 drifted")
    pompon = next(p for p in pets if p.pid == 840002)
    if [s.sid for s in pompon.skills] != [8400301, 8400302, 8400303, 8400304]:
        raise ValueError("蓬蓬崽 skill ids drifted")
    fluff = next(p for p in pets if p.pid == 840003)
    if [s.sid for s in fluff.skills] != [8400201, 8400202, 8400203, 8400204]:
        raise ValueError("絨嗚嗚 skill ids drifted")

    # park
    park_live = sorted([r for r in lvup_raw if r["index"] == PARK_INDEX], key=lambda r: _int(r["lv"]))
    park_new = sorted([r for r in lvup_new_raw if r["index"] == PARK_INDEX], key=lambda r: _int(r["lv"]))
    if len(park_live) != 41 or [_int(r["lv"]) for r in park_live] != list(range(0, 41)):
        raise ValueError("park rows drifted")
    if [_int(r["lv"]) for r in park_new] != list(range(0, 41)):
        raise ValueError("park_new rows drifted")
    same_core = (
        "para1", "para2", "para3", "string_para1", "string_para2", "fightforce",
        "des", "cost1", "cost2", "pre_building_level",
    )
    for a, b in zip(park_live, park_new):
        for k in same_core:
            if a.get(k) != b.get(k):
                raise ValueError(f"park lv {a['lv']} {k} differs between lvup and lvup_new")
    para1 = _intervals(park_live, "para1")
    para2 = _intervals(park_live, "para2")
    if para1 != [(0, 10, 1), (11, 30, 2), (31, 40, 3)]:
        raise ValueError(f"para1 intervals drifted: {para1}")
    if para2 != [(0, 34, 1), (35, 40, 2)]:
        raise ValueError(f"para2 intervals drifted: {para2}")
    ff_map = { _int(r["lv"]): _int(r["fightforce"]) for r in park_live }
    for lv, exp in PARK_FF.items():
        if ff_map[lv] != exp:
            raise ValueError(f"park fightforce lv {lv} {ff_map[lv]} != {exp}")
    p1 = parse_attr_map(park_live[1].get("string_para2"))
    p40 = parse_attr_map(park_live[-1].get("string_para2"))
    if p1.get(1133) != 100 or p40.get(1133) != 4000:
        raise ValueError(f"park 1133 drifted: {p1} {p40}")
    first_1192 = next(_int(r["lv"]) for r in park_live if 1192 in parse_attr_map(r.get("string_para2")))
    first_1191 = next(_int(r["lv"]) for r in park_live if 1191 in parse_attr_map(r.get("string_para2")))
    if (first_1192, first_1191) != (10, 20):
        raise ValueError(f"1192/1191 start {first_1192}/{first_1191}")
    if p40.get(1191) != 2:
        raise ValueError("park 40 1191 drifted")

    park_notes = {
        0: "string_para2 為空；前置城堡 25 級",
        1: "1133＝100 自此級寫上",
        10: "1192 自此級寫上",
        11: "para1 改為 2",
        20: "1191 自此級寫上；戰力 10950",
        31: "para1 改為 3",
        35: "para2 改為 2",
        40: "1133＝4000、1191＝2；無再升級消耗（cost1／cost2 為空）",
    }
    park: list[ParkLevel] = []
    for a, b in zip(park_live, park_new):
        lv = _int(a["lv"])
        if lv not in PARK_KEY_LEVELS:
            continue
        des = a.get("des") or []
        if not isinstance(des, list):
            des = [des]
        park.append(ParkLevel(
            lv=lv,
            para1=_int(a["para1"]),
            para2=_int(a["para2"]),
            string_para2=a.get("string_para2"),
            attrs=parse_attr_map(a.get("string_para2")),
            fightforce=_int(a["fightforce"]),
            cost1=a.get("cost1"),
            cost2=a.get("cost2"),
            cost3_lvup=a.get("cost3"),
            cost3_new=b.get("cost3"),
            build_time=a.get("buildTime"),
            build_time_new=b.get("buildTime"),
            pre=a.get("pre_building_level"),
            des_keys=[str(x) for x in des],
            note=park_notes.get(lv, ""),
        ))

    # vs 11-05 park used fields identical (checked in table_meta later too)
    old_lvup = PACK_DATA_DIRS["2026-11-05"] / "citybuilding_lvup.json"
    old_park = sorted(
        [r for r in json.loads(old_lvup.read_text(encoding="utf-8-sig")) if r["index"] == PARK_INDEX],
        key=lambda r: _int(r["lv"]),
    )
    used_park_fields = same_core + ("cost3", "buildTime", "des_icon", "pre_building_level_new")
    for a, b in zip(park_live, old_park):
        for k in used_park_fields:
            if a.get(k) != b.get(k):
                raise ValueError(f"park 160 lv {a['lv']} {k} differs from 2026-11-05")

    guidebook: list[GuideLevel] = []
    exp_total = 0
    if any(r.get("attr_pet") not in (None, "", [], -1) for r in guidebook_raw):
        raise ValueError("guidebook attr_pet is not empty")
    for row in sorted(guidebook_raw, key=lambda r: _int(r["id"])):
        amap = parse_attr_map(row.get("attr_role") or row.get("attr_roles"))
        guidebook.append(GuideLevel(
            level=_int(row["id"]),
            exp=_int(row["level_exp"]),
            atk=_int(amap.get(3, 0)),
            hp=_int(amap.get(4, 0)),
            fightforce=_int(row["fightforce"]),
        ))
        exp_total += _int(row["level_exp"])
    if exp_total != GUIDEBOOK_EXP_TOTAL:
        raise ValueError(f"guidebook exp total {exp_total}")
    g1, g58 = guidebook[0], guidebook[-1]
    if (g1.exp, g1.atk, g1.hp, g1.fightforce) != (10, 60, 450, 2200):
        raise ValueError(f"guidebook 1 drifted {g1}")
    if (g58.exp, g58.atk, g58.hp, g58.fightforce) != (9000, 8090, 54050, 270100):
        raise ValueError(f"guidebook 58 drifted {g58}")

    honor: list[HonorRow] = []
    if [ _int(r["quality"]) for r in honor_raw ] != [5, 6]:
        raise ValueError("honor qualities drifted")
    for row in honor_raw:
        amap = parse_attr_map(row.get("attribute_up") or row.get("attribute_up_arr"))
        if list(amap) != [4]:
            raise ValueError("honor attr drifted")
        honor.append(HonorRow(
            quality=_int(row["quality"]),
            attr_id=4,
            attr_name=official.attr_names[4],
            attr_value=_int(amap[4]),
            combat=_int(row["combat_power"]),
            need_chip=str(row.get("need_chip") or ""),
        ))
    if (honor[0].attr_value, honor[0].combat, honor[1].attr_value, honor[1].combat) != (40, 160, 80, 880):
        raise ValueError("honor values drifted")

    by_group: dict[int, list[dict]] = defaultdict(list)
    for row in honor_bonus_raw:
        by_group[_int(row["honor_group"])].append(row)
    expected_bonus = {
        101: (3103, 50, 500, 9000, 90000),
        102: (3104, 50, 500, 9000, 90000),
        112: (3104, 25, 250, 4500, 45000),
        201: (4103, 50, 500, 9000, 90000),
        202: (4104, 50, 500, 9000, 90000),
        212: (4104, 25, 250, 4500, 45000),
        301: (5103, 50, 500, 9000, 90000),
        302: (5104, 50, 500, 9000, 90000),
        312: (5104, 25, 250, 4500, 45000),
        401: (104, 50, 500, 9000, 90000),
    }
    if set(by_group) != set(expected_bonus):
        raise ValueError(f"honor groups drifted: {sorted(by_group)}")
    pets_by_group: dict[int, list[str]] = defaultdict(list)
    for p in pets:
        pets_by_group[p.group_id].append(p.base_name)
    honor_bonus: list[HonorBonus] = []
    for group, rows in sorted(by_group.items()):
        rows = sorted(rows, key=lambda r: _int(r["bonus_lv"]))
        lvs = [_int(r["bonus_lv"]) for r in rows]
        if lvs != list(range(50, 501, 50)):
            raise ValueError(f"honor group {group} levels {lvs}")
        values = {}
        combats = {}
        attr_id = None
        for r in rows:
            amap = parse_attr_map(r.get("bonus_attribute") or r.get("bonus_attribute_arr"))
            if len(amap) != 1:
                raise ValueError(f"honor bonus {group} attr map {amap}")
            aid, val = next(iter(amap.items()))
            if attr_id is None:
                attr_id = aid
            elif aid != attr_id:
                raise ValueError(f"honor group {group} attr id changed")
            values[_int(r["bonus_lv"])] = _int(val)
            combats[_int(r["bonus_lv"])] = _int(r["combat"])
        exp = expected_bonus[group]
        if (attr_id, values[50], values[500], combats[50], combats[500]) != exp:
            raise ValueError(f"honor group {group} {attr_id, values[50], values[500], combats[50], combats[500]} != {exp}")
        honor_bonus.append(HonorBonus(
            group=group,
            attr_id=attr_id,
            attr_name=official.attr_names[attr_id],
            values=values,
            combats=combats,
            pets=pets_by_group.get(group, []),
        ))

    egg_name_by_cost = {
        30001: (official.egg_names["pet_egg_05"], official.egg_descs["goods_desc_30001"]),
        30002: (official.egg_names["pet_egg_08"], official.egg_descs["goods_desc_30002"]),
        30003: (official.egg_names["pet_egg_09"], official.egg_descs["goods_desc_30003"]),
    }
    detail_ids = {p.pid for p in pets}
    incubate: list[IncubateRow] = []
    for row in incubate_raw:
        iid = _int(row["id"])
        cost = row.get("cost")
        name, desc = egg_name_by_cost.get(_int(cost) if cost not in (None, "") else -1, ("", ""))
        incubate.append(IncubateRow(
            iid=iid,
            cost=cost,
            time=_int(row["time"]),
            pet_reward=row.get("pet_reward"),
            is_guaranteed=row.get("is_guaranteed"),
            guaranteed_pet_id=row.get("guaranteed_pet_id"),
            probability_time=row.get("probability_time"),
            guaranteed_reward=row.get("guaranteed_reward"),
            egg_name=name,
            egg_desc=desc,
            in_detail=iid in detail_ids,
        ))
    if [r.iid for r in incubate] != [830001, 830002, 830003, 830004, 830005]:
        raise ValueError("incubate ids drifted")
    if incubate[3].in_detail or incubate[4].in_detail:
        raise ValueError("830004/830005 unexpectedly in pet_detail")
    if (incubate[0].time, incubate[1].time, incubate[2].time) != (14400, 21600, 28800):
        raise ValueError("incubate times drifted")
    if incubate[1].is_guaranteed != 1 or str(incubate[1].guaranteed_pet_id) != "830001|830002|830003":
        raise ValueError("rare-egg guarantee drifted")

    food_ids = [_int(r["reward_id"]) for r in food_raw]
    if food_ids != list(range(110411, 110420)):
        raise ValueError(f"food convert reward ids drifted: {food_ids}")

    egg_tasks = []
    for row in egg_task_raw:
        egg_tasks.append({
            "id": row["id"],
            "name_key": row.get("name"),
            "name": official_text(row.get("name")),
            "time": row.get("time"),
            "disappear_time": row.get("disappear_time"),
            "quality": row.get("quality"),
        })

    # level key verification vs known values
    s1 = next(k for k in slime.level_keys if k.level == 1)
    s120 = next(k for k in slime.level_keys if k.level == 120)
    if (s1.attr_30004, s1.fightforce, s120.attr_30004, s120.fightforce) != (3318, 6636, 1626331, 3252662):
        raise ValueError("830 level 1/120 attrs drifted")
    f1 = next(k for k in flash.level_keys if k.level == 1)
    f120 = next(k for k in flash.level_keys if k.level == 120)
    if (f1.attr_30004, f1.fightforce, f120.attr_30004, f120.fightforce) != (5530, 11060, 2710552, 5421104):
        raise ValueError("840 level 1/120 attrs drifted")
    f70 = next(k for k in flash.level_keys if k.level == 70)
    late70 = next(k for k in beak.level_keys if k.level == 70)
    if late70.attr_30004 - f70.attr_30004 != 1000 or late70.fightforce - f70.fightforce != 2000:
        raise ValueError("840 70-level exception drifted")
    crab = next(p for p in pets if p.pid == 840014)
    c8 = next(k for k in crab.level_keys if k.level == 8)
    f8 = next(k for k in flash.level_keys if k.level == 8)
    if c8.attr_30004 - f8.attr_30004 != 10 or c8.fightforce - f8.fightforce != 20:
        raise ValueError("840014 lv8 exception drifted")

    string_cmp = _compare_string_packs(set(USED_KEYS))
    table_cmp = _compare_table_packs(list(TABLE_SHA256))
    terms = _terms(official, pets)
    table_count = 759
    try:
        table_count = sum(1 for p in DATA_DIR.glob("*.json"))
    except OSError:
        pass

    verifications = {
        "pet_rows": 21,
        "base_names": [p.base_name for p in pets],
        "slime_17": (slime17.skin_id, slime17.name_key, slime17.name),
        "park_ff": {lv: ff_map[lv] for lv in (0, 1, 20, 40)},
        "park_para1": para1,
        "park_para2": para2,
        "park_1133": (p1.get(1133), p40.get(1133)),
        "upgrade_cost_total": total,
        "conv_830": (2000, 8800),
        "conv_840": (3600, 10800),
        "attr_role_groups": expected_attr,
        "guidebook_exp_total": exp_total,
        "guidebook_1": (g1.exp, g1.atk, g1.hp, g1.fightforce),
        "guidebook_58": (g58.exp, g58.atk, g58.hp, g58.fightforce),
        "honor_bonus_groups": 10,
        "honor_bonus_50_500": {b.group: (b.values[50], b.values[500]) for b in honor_bonus},
        "beak_nameless": True,
        "tribe_shelter": official.shelter["部落的庇護"],
        "skill_ids": 81,
        "string_used_keys": string_cmp["used_keys"],
        "string_value_diffs": string_cmp["value_diffs"],
        "string_missing": string_cmp["missing"],
        "string_packs": {k: {"keys": v["keys"], "sha256": v["sha256"]} for k, v in string_cmp["packs"].items()},
        "tables_in_pack": table_count,
    }
    return TablesData(
        official=official,
        pets=pets,
        park=park,
        park_para1=para1,
        park_para2=para2,
        honor=honor,
        honor_bonus=honor_bonus,
        guidebook=guidebook,
        guidebook_exp_total=exp_total,
        incubate=incubate,
        egg_tasks=egg_tasks,
        food_convert=[{
            "id": r["id"],
            "upper_limit": r["upper_limit"],
            "consume": r["consume"],
            "reward_id": r["reward_id"],
        } for r in food_raw],
        function63=function63,
        terms=terms,
        verifications=verifications,
        table_meta={"string_cmp": string_cmp, "table_cmp": table_cmp, "table_count": table_count},
    )


def _terms(official: Official, pets: list[PetInfo]) -> list[str]:
    terms: set[str] = {
        official.system_name, official.partner_dir, official.catalog_name,
        official.honour_name, official.park_name, official.park_des,
        official.attr_cd, official.attr_percent, official.attr_break_all,
        official.function_closed, official.honour_info, official.honour_title,
        official.reborn_tips2, official.need_break_tips, official.title020,
        official.title003_dec, official.quality_common, official.formula_1,
        official.formula_2, official.food_name, official.food_desc,
        official.essence_name, official.essence_desc, official.wood,
        official.stone, official.castle, official.guaranteed,
        official.box_good_name, official.box_good_desc,
        official.box_rare_name, official.box_rare_desc,
        official.cactus_egg_name, official.cactus_egg_desc,
        "裝備總表", "領主裝備總表", "士兵總表", "秘寶總表", "專武總表", "英靈總表",
        "英雄裝備", "領主裝備", "專武", "士兵", "秘寶", "英靈", "寵物總表",
        "寵物樂園", "寵物榮譽牆", "寵物榮譽塵", "寵物屬性轉化率", "全英雄加成",
        "寵物功能未開啟", "寵物圖鑑", "寵物夥伴", "寵物口糧", "寵物精華",
        "英靈不是寵物", "官方界面稱「寵物」",
        "聯盟的庇護", "部落的庇護", "自然的庇護", "魔狗的庇護",
        "寵物攻擊 = 目前上陣英雄攻擊力總值 / 6 * 寵物屬性轉化率。",
        "寵物生命 = 目前上陣英雄生命總值 / 6  * 寵物屬性轉化率。",
        "寵物攻擊＝目前上陣英雄攻擊力總值／6×寵物屬性轉化率",
        "聯盟", "部族", "自然", "部落",
        "優良寵物蛋", "稀有寵物蛋", "史詩寵物蛋",
        "優良寵物寶箱", "稀有寵物寶箱", "仙人掌寵物蛋",
        "戰鬥中英雄生命增加", "英雄攻擊", "英雄生命",
        "聯盟英雄攻擊", "聯盟英雄生命", "部族英雄攻擊", "部族英雄生命",
        "自然英雄攻擊", "自然英雄生命", "攻擊", "生命值",
        "縮短孵化時間（秒）", "寵物孵化欄位", "寵物蛋搜尋等級",
        "寵物懸賞可購買次數", "寵物懸賞次數", "木材", "石頭", "城堡",
        "在賽季 2 以後才可以獲取和使用", "寵物精華在賽季2以後才可以獲取和使用。",
    }
    for name in official.park_des_keys.values():
        terms.add(name)
    for text in official.tips.values():
        terms.add(text)
        for line in text.split("\n"):
            terms.add(line.strip())
    for text in official.egg_names.values():
        terms.add(text)
    for text in official.egg_descs.values():
        terms.add(text)
    for text in official.titles.values():
        terms.add(text)
    for name in official.attr_names.values():
        terms.add(name)
    terms.add(official.attr_1133_name)
    for label, text in official.shelter.items():
        terms.add(label)
        terms.add(text)
    for line in official.formula_1.split("\n"):
        terms.add(line.strip())
    for line in official.formula_2.split("\n"):
        terms.add(line.strip())
    for pet in pets:
        terms.add(pet.base_name)
        terms.add(pet.faction)
        for m in pet.morphs:
            terms.add(m.name)
        for skill in pet.skills:
            terms.add(skill.name)
            for seg in skill.segments:
                terms.add(seg.template)
                terms.add(seg.filled)
                for line in skill_lines(skill, skill.maxlv):
                    terms.add(line)
    return sorted({x for x in terms if x}, key=len, reverse=True)


def _alabel(name: str, attr_id: int, terms: list[str] | None = None) -> str:
    text = f"{name}（{attr_id}）"
    return H(text, terms) if terms is not None else text


def _morph_plain(pet: PetInfo) -> str:
    later = [m for m in pet.morphs if m.break_level != pet.origin_break]
    if not later:
        return EMPTY
    if pet.name_constant and any(m.skin_changed for m in later):
        skins = "、".join(str(m.skin_id) for m in pet.morphs)
        return f"皮膚 id 會變（{skins}），顯示名與名稱鍵不變"
    parts = []
    for m in later:
        bit = f"{m.break_level} 階品質 {m.quality}：{m.name}（{m.name_key}，皮膚 {m.skin_id}）"
        parts.append(bit)
    return "；".join(parts)


def _skill_block_plain(pet: PetInfo, which: str) -> str:
    brow = pet.breaks[0] if which == "origin" else pet.breaks[-1]
    label = f"{brow.break_level} 階"
    chunks = [label]
    for skill, lv in zip(pet.skills, brow.skill_levels):
        name = skill.name if skill.name else "（名稱鍵在字串表沒有內容，不編造技能名）"
        head = f"{name}（{skill.sid}，名稱鍵 {skill.name_key}，等級 {lv}／{skill.maxlv}）"
        if skill.name_key == "hero_skill_name_84017033":
            head += "（鍵名照表為 84017033）"
        if skill.name_key in ("hero_skill_name_8401203", "hero_skill_name_8401103") and skill.sid in (8401103, 8401203):
            head += "（名稱鍵與寵物編號交叉，照表登錄）"
        lines = skill_lines(skill, lv)
        chunks.append(head + "\n" + "\n".join(lines))
    return "\n".join(chunks)


def _skill_block_html(pet: PetInfo, which: str, terms: list[str]) -> str:
    brow = pet.breaks[0] if which == "origin" else pet.breaks[-1]
    parts = [f"<strong>{e(str(brow.break_level))} 階</strong>"]
    for skill, lv in zip(pet.skills, brow.skill_levels):
        if skill.name:
            name = H(skill.name, terms)
        else:
            name = e("（名稱鍵在字串表沒有內容，不編造技能名）")
        note = ""
        if skill.name_key == "hero_skill_name_84017033":
            note = e("（鍵名照表為 84017033）")
        if skill.name_key in ("hero_skill_name_8401203", "hero_skill_name_8401103") and skill.sid in (8401103, 8401203):
            note = e("（名稱鍵與寵物編號交叉，照表登錄）")
        head = f"{name}（{e(str(skill.sid))}，名稱鍵 <code>{e(skill.name_key)}</code>，等級 {e(str(lv))}／{e(str(skill.maxlv))}）{note}"
        lines = "<br>".join(H(line, terms) for line in skill_lines(skill, lv))
        parts.append(f"{head}<br>{lines}")
    return "<br>".join(parts)


def _fmt_para2(raw, attrs: dict[int, int]) -> str:
    if raw in (None, "", [], -1):
        return EMPTY
    parts = []
    for aid, val in attrs.items():
        parts.append(f"{aid}｜{val}")
    return "、".join(parts)


def _build_html_tables(data: TablesData, terms: list[str]) -> dict:
    o = data.official
    park_rows = []
    for r in data.park:
        park_rows.append([
            str(r.lv),
            str(r.para1),
            str(r.para2),
            e(_fmt_para2(r.string_para2, r.attrs)),
            str(r.fightforce),
            H(r.note, terms) if r.note else EMPTY,
        ])
    park = table(
        ["樂園等級", "para1", "para2", "string_para2（id｜原值）", "戰力", "備註"],
        park_rows,
        mobile="sticky",
        card_title="樂園等級",
    )

    def_rows = []
    for p in data.pets:
        def_rows.append([
            H(p.base_name, terms),
            str(p.pid),
            str(p.group_id),
            H(p.faction, terms),
            f"{p.origin_break}–{p.break_max}",
            f"{p.quality_start}→{p.quality_end}",
            f"{p.decomposed_get}",
            str(p.guidebook_openday),
            e(format_unlocktime(p.unlocktime)),
        ])
    defs = table(
        ["基礎名", "寵物編號", "組別", "陣營（依榮譽組）", "突破", "品質起迄", "分解值", "圖鑑開放天數", "解鎖時間（只照錄）"],
        def_rows,
        mobile="sticky",
        card_title="基礎名",
    )

    cat_rows = []
    for p in data.pets:
        later = _morph_plain(p)
        cat_rows.append([
            H(p.base_name, terms),
            str(p.pid),
            e(p.base_name_key),
            str(p.base_skin),
            H(later, terms) if later != EMPTY else EMPTY,
        ])
    catalog = table(
        ["基礎名", "寵物 id", "基礎名稱鍵", "基礎皮膚", "後續型態（皮膚或顯示名有變化的階段）"],
        cat_rows,
        mobile="cards",
        card_title="基礎名",
    )

    band_rows = []
    for (lo, hi), start, step in COST_BANDS:
        total = sum(start + (lv - lo) * step for lv in range(lo, hi + 1))
        band_rows.append([
            f"{lo}–{hi}",
            str(start),
            f"+{step}",
            str(total),
        ])
    band_rows.append(["1", "-1", EMPTY, "0（不計入合計）"])
    band_rows.append([
        "91–120",
        "5900",
        "多為 +100；95、98、101、104、107、110、113、116、119 級為 +200",
        str(sum(COST_91_120)),
    ])
    band_rows.append(["合計（2–120 級）", EMPTY, EMPTY, str(LEVEL_COST_TOTAL)])
    # keep a consistent order: 1, bands, 91-120, total
    band_rows = [band_rows[-2]] + band_rows[:-2] + band_rows[-1:]
    costs = table(
        ["等級區間", "該段起始消耗", "每級增量", "段合計"],
        band_rows,
        mobile="sticky",
        card_title="等級區間",
    )

    c91_rows = [["91–100"] + [str(x) for x in COST_91_120[:10]]]
    c91_rows.append(["101–110"] + [str(x) for x in COST_91_120[10:20]])
    c91_rows.append(["111–120"] + [str(x) for x in COST_91_120[20:]])
    costs_91 = table(
        ["等級"] + [str(i) for i in range(0, 10)],
        c91_rows,
        mobile="sticky",
        card_title="等級",
    )

    # key attrs: 830 group + 840001 + exceptions
    slime = next(p for p in data.pets if p.pid == 830001)
    flash = next(p for p in data.pets if p.pid == 840001)
    crab = next(p for p in data.pets if p.pid == 840014)
    beak = next(p for p in data.pets if p.pid == 840018)
    key_lvs = (1, 10, 20, 40, 70, 90, 120)
    attr_rows = []
    for label, pet in (
        ("830001–830003", slime),
        ("840001–840009（70／8 級基準）", flash),
        ("840014（8 級例外）", crab),
        ("840010–840018（70 級例外；840014 亦屬此組）", beak),
    ):
        cells = [e(label)]
        for lv in key_lvs:
            k = next((x for x in pet.level_keys if x.level == lv), None)
            if k:
                cells.append(f"{k.attr_30004}／{k.fightforce}")
            else:
                cells.append(EMPTY)
        attr_rows.append(cells)
    level_attrs = table(
        ["曲線"] + [f"{lv} 級 30004／戰力" for lv in key_lvs],
        attr_rows,
        mobile="sticky",
        card_title="曲線",
    )

    extra_rows = [
        [e("830001–830003"), "61–90", "寵物精華 ×25 起，逐級增加至 ×1250", "16875"],
        [e("840001–840018"), "91–120", "寵物精華 ×50 起，逐級增加至 ×2500", "33750"],
    ]
    extras = table(
        ["寵物", "出現等級", "額外消耗", "段合計（精華數量）"],
        extra_rows,
        mobile="sticky",
        card_title="寵物",
    )

    def break_rows_for(pet: PetInfo, include_attr: bool) -> list[list[str]]:
        rows = []
        for r in pet.breaks:
            slv = "／".join(str(x) for x in r.skill_levels)
            cells = [
                str(r.break_level),
                str(r.conversion_rate),
                str(r.quality),
                slv,
                f"{r.pet_lv_min}–{r.pet_lv_max}",
                e(format_cost(r.cost)),
                e(format_cost(r.extra_cost)),
            ]
            if include_attr:
                cells.append("、".join(f"{k}｜{v}" for k, v in r.attr_role.items()))
            if r.season_limit not in (None, "", 0, -1) or r.season_limit_new not in (None, "", [], -1):
                cells.append(e(f"season_limit={r.season_limit}；season_limit_new={r.season_limit_new}"))
            else:
                cells.append(EMPTY)
            rows.append(cells)
        return rows

    headers_830 = ["突破階", "轉化率", "品質", "技能等級", "等級上下限", "消耗（照錄）", "extra_cost", "attr_role 原值", "season（只照錄）"]
    br830 = table(headers_830, break_rows_for(slime, True), mobile="sticky", card_title="突破階")
    headers_840c = ["突破階", "轉化率", "品質", "技能等級", "等級上下限", "消耗（840a，照錄）", "extra_cost", "season（只照錄）"]
    # 840a without attr (attrs differ by group)
    br840a = table(
        headers_840c,
        [row[:7] + [row[-1]] for row in break_rows_for(flash, False)],
        mobile="sticky",
        card_title="突破階",
    )
    dada = next(p for p in data.pets if p.pid == 840017)
    headers_840b = ["突破階", "轉化率", "品質", "技能等級", "等級上下限", "消耗（火花／達達，照錄）", "extra_cost", "season（只照錄）"]
    br840b = table(
        headers_840b,
        [row[:7] + [row[-1]] for row in break_rows_for(dada, False)],
        mobile="sticky",
        card_title="突破階",
    )

    group_rows = []
    labels = [
        ((103, 104), (170, 250), (3230, 4750), "閃啾啾、蓬蓬崽、絨嗚嗚、雪球寶寶、翠牙苗"),
        ((3103, 3104), (510, 750), (9690, 14250), "蛋仔、燭寶、雪團子、疾風、鐵喙"),
        ((4103, 4104), (510, 750), (9690, 14250), "火苗喵喵、虎寶、時光龍·柯羅諾斯、火花"),
        ((5103, 5104), (510, 750), (9690, 14250), "仙人掌寶寶、天馬、潮汐蟹"),
        ((103, 104), (510, 750), (9690, 14250), "達達"),
        ((103, 104), (50, 50), (900, 900), "史萊姆、毛茸茸、噗噗豬（0–17 階）"),
    ]
    for ids_, origin, mx, members in labels:
        group_rows.append([
            _alabel(o.attr_names[ids_[0]], ids_[0], terms) + "／" + _alabel(o.attr_names[ids_[1]], ids_[1], terms),
            f"{origin[0]}／{origin[1]}",
            f"{mx[0]}／{mx[1]}",
            H(members, terms),
        ])
    attr_groups = table(
        ["屬性（只錄原值）", "起點原值", "滿檔原值", "寵物"],
        group_rows,
        mobile="cards",
        card_title="屬性（只錄原值）",
    )

    skills = {}
    for p in data.pets:
        rows = [
            [e(f"{p.origin_break} 階（origin_break）"), _skill_block_html(p, "origin", terms)],
            [e(f"{p.break_max} 階（滿突破）"), _skill_block_html(p, "max", terms)],
        ]
        skills[p.pid] = table(
            ["階段", "技能文案"],
            rows,
            mobile="cards",
            card_title="階段",
        )

    gkey = (1, 10, 20, 30, 40, 50, 58)
    gb_rows = []
    for g in data.guidebook:
        if g.level in gkey:
            gb_rows.append([str(g.level), str(g.exp), str(g.atk), str(g.hp), str(g.fightforce)])
    gb_rows.append(["經驗合計（1–58 級）", str(data.guidebook_exp_total), EMPTY, EMPTY, EMPTY])
    guidebook = table(
        ["圖鑑等級", "該級經驗", "攻擊（3）", "生命值（4）", "戰力"],
        gb_rows,
        mobile="sticky",
        card_title="圖鑑等級",
    )

    honor = table(
        ["品質", "屬性", "戰力", "need_chip（各段含義未標，不解讀）"],
        [[
            str(r.quality),
            f"{_alabel(r.attr_name, r.attr_id, terms)} {r.attr_value}",
            str(r.combat),
            e(r.need_chip),
        ] for r in data.honor],
        mobile="sticky",
        card_title="品質",
    )

    bonus_rows = []
    for r in data.honor_bonus:
        bonus_rows.append([
            str(r.group),
            _alabel(r.attr_name, r.attr_id, terms),
            str(r.values[50]),
            str(r.values[500]),
            f"{r.combats[50]}／{r.combats[500]}",
            H("、".join(r.pets), terms),
        ])
    bonus = table(
        ["榮譽組", "屬性", "50 檔原值", "500 檔原值", "50／500 戰力", "寵物"],
        bonus_rows,
        mobile="sticky",
        card_title="榮譽組",
    )

    inc_rows = []
    for r in data.incubate:
        name = H(r.egg_name, terms) if r.egg_name else e("（不在 pet_detail，不編造蛋名）")
        desc = H(r.egg_desc, terms) if r.egg_desc else EMPTY
        inc_rows.append([
            str(r.iid),
            "是" if r.in_detail else "否",
            e(str(r.cost)),
            str(r.time),
            e(str(r.pet_reward)),
            e(str(r.is_guaranteed)),
            e(format_unlocktime(r.guaranteed_pet_id)),
            e(str(r.probability_time)),
            e(str(r.guaranteed_reward)),
            name,
            desc,
        ])
    incubate = table(
        ["id", "在 pet_detail", "消耗", "時間（秒）", "pet_reward", "is_guaranteed", "guaranteed_pet_id", "probability_time", "guaranteed_reward", "蛋短名", "蛋說明"],
        inc_rows,
        mobile="cards",
        card_title="id",
    )

    task_rows = []
    for r in data.egg_tasks:
        task_rows.append([
            str(r["id"]),
            H(r["name"], terms),
            e(str(r["name_key"])),
            e(str(r["time"])),
            e(str(r["disappear_time"])),
        ])
    egg_tasks = table(
        ["id", "名稱", "名稱鍵", "time", "disappear_time"],
        task_rows,
        mobile="sticky",
        card_title="名稱",
    )

    food_rows = []
    for r in data.food_convert:
        food_rows.append([
            str(r["id"]),
            str(r["consume"]),
            str(r["upper_limit"]),
            str(r["reward_id"]),
            e("字串表沒有名稱，關係未驗證"),
        ])
    food = table(
        ["id", "消耗", "上限", "獎勵 id", "名稱"],
        food_rows,
        mobile="sticky",
        card_title="id",
    )

    return {
        "park": park,
        "defs": defs,
        "catalog": catalog,
        "costs": costs,
        "costs_91": costs_91,
        "level_attrs": level_attrs,
        "extras": extras,
        "br830": br830,
        "br840a": br840a,
        "br840b": br840b,
        "attr_groups": attr_groups,
        "skills": skills,
        "guidebook": guidebook,
        "honor": honor,
        "bonus": bonus,
        "incubate": incubate,
        "egg_tasks": egg_tasks,
        "food": food,
    }


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

    pet_files = [
        "pet_detail.json", "pet_level.json", "pet_break.json", "pet_guidebook.json",
        "pet_honor.json", "pet_honor_bonus.json", "pet_incubate.json", "pet_egg_task.json",
        "pet_food_convert.json", "pet_achievement.json",
    ]
    pet_same = all(all(tc[n]["identical"].get(p) for p in ("2026-11-05", "2026-11-22", "2026-11-22-locallow")) for n in pet_files)
    pet_note = (
        "本頁用到的全部 pet_* 表（detail／level／break／guidebook／honor／honor_bonus／"
        "incubate／egg_task／food_convert／achievement）與 2026-11-05 解壓檔、以及 2026-11-22 "
        "StreamingAssets／LocalLow 歸檔位元組相同。"
        if pet_same else
        "本頁用到的 pet_* 表與歸檔的位元組對照見各檔說明，並非全部相同。"
    )
    return (
        f"資料截至 {PET_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {PET_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {PET_DATA_PACKED}（香港時間）。"
        f"{pet_note}"
        "這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "`citybuilding_lvup.json`／`citybuilding_lvup_new.json` 整檔與 2026-11-05 解壓檔位元組不同"
        "（現行檔與 2026-11-22 兩份歸檔相同），但建築 160 寵物樂園 0–40 級本頁用到的數值欄"
        "（para1／para2／para3、string_para1／string_para2、戰力、des、cost1／cost2、前置，以及 "
        "citybuilding_lvup 的 cost3／buildTime）在四份裡相同。"
        "兩張升級表彼此的樂園 para／戰力／string_para／cost1／cost2／des 相同，但 10 級起 buildTime 不同，"
        "18 級起 cost3（999｜6）只出現在 citybuilding_lvup_new；本頁不把這兩欄寫成單一數值。"
        "`hero_component.json` 現行檔與 LocalLow 歸檔相同，與 2026-11-05、2026-11-22 StreamingAssets "
        "整檔位元組不同；本頁用到的 81 個寵物技能 id 之 name／desc1–desc5／參數／maxlv 在這四份裡相同。"
        "`function.json` 同樣是現行檔與 LocalLow 歸檔相同、與另外兩份整檔不同；id 63 的 openPanel、"
        "func_open_param、tips、name 鍵在四份裡相同（_condition 為執行期欄，本頁不用）。"
        "`skin.json` 現行檔與 2026-11-22 兩份歸檔相同（1,115 筆），2026-11-05 為 1,113 筆（後來多的 "
        "1003108、1004208 不是寵物皮膚）；本頁用到的 84 個寵物皮膚 id 之 name 與頭像圖集 Atlas/UI_Pet_Head "
        "在四份裡相同。"
        "`attribute.json` 列數同為 764，2026-11-05 與現行包位元組不同，差在後來多了欄位；"
        "本頁用到的 type／show_type／name 與 2026-11-05 相同。"
        "2026-11-05 與 2026-11-22 StreamingAssets 解壓檔沒有 goods.json；現行 LocalLow 的 goods.json "
        "是 3,256 筆的完整表，不是空殼。本頁不以它當道具目錄，道具名稱只取字串鍵。"
        f"`strings_zh.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（{live['keys']} 鍵）；"
        f"2026-11-05（{old['keys']} 鍵）與 2026-11-22 StreamingAssets（{sa['keys']} 鍵）整體不同。"
        f"{extra}"
        "鐵喙前三個技能名稱鍵 hero_skill_name_8401801–8401803 在現行字串表與三份歸檔都不存在，不是歸檔缺漏。"
        "顯示規則依攻略手冊「寵物圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05），"
        "但數值一律以現行資料表為準。"
        "第 21 章升級節未列出 pet_level.cost_extra；本頁按表補上 830xxx 自 61 級、840xxx 自 91 級的 "
        "`2|289|數量`（道具 289 寵物精華），且不把主欄 cost 斷定成只扣口糧或口糧加精華。"
        "寵物樂園兩張升級表的 buildTime／cost3 差異也按表註明。"
        "口糧轉換獎勵 id 以表上的 110411–110419 為準。"
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜寵物總表"
    summary = (
        "官方界面所稱的寵物：21 隻名稱與型態、寵物樂園關鍵級、升級與突破、轉化率與全英雄加成、"
        "滿突破技能原文、圖鑑與榮譽牆，以及孵化與搜索規則。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍與解鎖"},
        {"id": "rules", "label": "系統規則（官方字串）"},
        {"id": "park", "label": "寵物樂園"},
        {"id": "catalog", "label": "名錄與型態名稱"},
        {"id": "upgrade", "label": "升級"},
        {"id": "break", "label": "突破與轉化率"},
        {"id": "skills", "label": "技能"},
        {"id": "guidebook", "label": "圖鑑與榮譽牆"},
        {"id": "incubate", "label": "孵化與搜索"},
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
        "正文只根據遊戲資料表與官方字串，不評定寵物強弱，也不排行。"
        f"官方界面稱「{H(o.system_name, terms)}」。"
        f"影響力目錄「{H(o.partner_dir, terms)}」底下再分「{H(o.system_name, terms)}」、"
        f"「{H(o.catalog_name, terms)}」、「{H(o.honour_name, terms)}」。"
        f"{H('英靈不是寵物', terms)}；帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場不在本頁展開。"
        f"英雄四件套裝備見<a href=\"equipment.html\">{H('裝備總表', terms)}</a>，"
        f"領主裝備見<a href=\"lord-equipment.html\">{H('領主裝備總表', terms)}</a>，"
        f"士兵見<a href=\"troops.html\">{H('士兵總表', terms)}</a>，"
        f"秘寶見<a href=\"artifacts.html\">{H('秘寶總表', terms)}</a>。"
        f"已發佈的<a href=\"exclusive.html\">{H('專武總表', terms)}</a>是英雄專武；"
        f"已發佈的<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>是綁在英雄身上的另一套養成，不是寵物。"
    ))
    add("<ul>")
    add("<li><strong>本頁只寫遊戲裡稱作「寵物」的這套養成，共 21 隻。</strong>"
        "下面會列出名稱與型態、寵物樂園關鍵級、升級與突破、轉化率與全英雄加成，以及圖鑑、榮譽牆、孵化與搜索規則。"
        "資料表檔名與筆數見資料說明。</li>")
    add("<li>名稱依遊戲裡看得到的顯示名書寫；對照路徑與例外見資料說明。</li>")
    add("<li><strong>不要從時間或賽季欄位自動標未開放。</strong>相關欄位只照錄。"
        "升級與突破屬性只錄表上的原值，不自行換成百分比。"
        f"{H(o.attr_percent, terms)}寫在突破表的轉化率欄，對照見資料說明。</li>")
    add("<li>技能文案以技能表的各段說明填入對應參數後照錄。"
        "第一段是基礎效果，其後各段是升階追加，不是另寫一條完整技能。"
        "若文案兩個位置都寫同一個佔位符，兩處都代入同一參數。欄位名見資料說明。"
        f"官方轉化公式不是戰鬥傷害公式，不代入面板去做戰鬥結算。正式用語是{H('部族', terms)}不是{H('部落', terms)}；"
        f"唯一例外是官方字串本身寫「{H('部落', terms)}」（如「{H('部落的庇護', terms)}」）時原文引用。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍與解鎖</h2>")
    add(p_html(
        "說明寫：寵物可升級、突破；在隊列中可裝配寵物；上陣後可在戰鬥中為該隊列的英雄增加屬性；"
        "寵物自身屬性由所在隊列的英雄平均屬性轉化而來。字串鍵見資料說明。"
    ))
    add(p_html(
        f"功能表裡寵物功能的開啟條件對應{H(o.park_name, terms)} 1 級，提示字串「{H(o.function_closed, terms)}」。"
        "名稱欄在字串表沒有對應內容，名稱欄為空。面板名、條件欄與鍵名見資料說明。"
    ))
    add(p_html(
        "21 筆定義：830001–830003 與 840001–840018。"
        "前 3 筆最高突破 17、起始突破 0、分解值 100、圖鑑開放天數 3；後 18 筆分別為 23、5、600、5。"
        "全部可見且未鎖定；技能解鎖門檻皆為 10／20／30／40（含義表上未標，不猜）。"
        "圖鑑伺服器名單 21 筆相同。達達、鐵喙有解鎖時間，只照錄，不標未開放。欄位名見資料說明。"
    ))
    add(tbl["defs"])
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>系統規則（官方字串）</h2>")
    add(p_html(
        f"轉化公式（<code>pet_function_attr_tips_1</code>／<code>_2</code>，不是戰鬥傷害公式）原文："
    ))
    add(f"<blockquote>{highlight_lines(o.formula_1, terms)}</blockquote>")
    add(p_html("上陣後的對照文案（<code>pet_function_attr_tips_2</code>）原文："))
    add(f"<blockquote>{highlight_lines(o.formula_2, terms)}</blockquote>")
    add(p_html(f"養成說明（<code>pet_info_tips_2</code>）："))
    add(f"<blockquote>{highlight_lines(o.tips['pet_info_tips_2'], terms)}</blockquote>")
    add(p_html(f"上陣說明（<code>pet_info_tips_3</code>）："))
    add(f"<blockquote>{highlight_lines(o.tips['pet_info_tips_3'], terms)}</blockquote>")
    add(p_html(f"戰鬥與轉化說明（<code>pet_attr_info_tips</code>）："))
    add(f"<blockquote>{highlight_lines(o.tips['pet_attr_info_tips'], terms)}</blockquote>")
    add("    </section>")

    add('    <section id="park">')
    add(f"      <h2>{H(o.park_name, terms)}</h2>")
    add(p_html(
        f"建築 160，官方名稱「{H(o.park_name, terms)}」，說明：「{H(o.park_des, terms)}」。"
        "升級表 0–40 級（41 列）。前置早期為城堡（117）達到指定等級，40 級這欄為空。"
        "升級說明五個鍵："
        f"「{H(o.park_des_keys['pet_building_attr_place'], terms)}」、"
        f"「{H(o.park_des_keys['pet_building_attr_egg_level'], terms)}」、"
        f"「{H(o.park_des_keys['pet_building_attr_cd'], terms)}」、"
        f"「{H(o.park_des_keys['attribute_name_1192'], terms)}」（1192）、"
        f"「{H(o.park_des_keys['attribute_name_1191'], terms)}」（1191）。"
    ))
    add(p_html(
        "<code>para1</code> 在 0–10 級為 1、11–30 級為 2、31–40 級為 3；"
        "<code>para2</code> 在 0–34 級為 1、35–40 級為 2。"
        "表沒有把這兩欄逐一標上「孵化欄位／搜尋等級／縮短時間」，本頁只錄數值，不自行指定為哪一欄。"
        f"另一欄從 1 級起有屬性 1133（字串表沒有對應官方屬性名；屬性表內部名稱對應「{H(o.attr_1133_name, terms)}」，與升級說明第三項相同，本頁不自行斷定界面一定用這個名稱顯示），"
        "數值隨等級增加（1 級 100、40 級 4000），並逐步寫上 1192／1191（1192 自 10 級、1191 自 20 級；40 級 1191 為 2）。"
    ))
    add(p_html(
        f"消耗方面，0–39 級的 <code>cost1</code>／<code>cost2</code> 為類型 999、資源 4／5"
        f"（頂欄名稱為{H(o.wood, terms)}／{H(o.stone, terms)}），兩張升級表這兩欄相同；40 級沒有再升級消耗。"
        "<code>cost3</code> 與 <code>buildTime</code> 在 <code>citybuilding_lvup</code> 與 "
        "<code>citybuilding_lvup_new</code> 並不完全相同（10 級起時間不同，18 級起後者才有 999｜6 的 cost3），"
        "本頁不把這兩欄寫成單一數值。戰力 0 級為 0、1 級為 300、20 級為 10,950、40 級為 140,550。"
    ))
    add(tbl["park"])
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>名錄與型態名稱</h2>")
    add(p_html(
        "顯示名取自該突破階段的皮膚 <code>name</code> 鍵。830xxx 從突破 0 開始，840xxx 從突破 5 開始（與 "
        "<code>origin_break=5</code> 一致）。下表「基礎名」是各隻第一筆突破列的顯示名；「後續型態」只列皮膚或顯示名有變化的階段。"
        f"<code>group_id</code> 的百位與榮譽加成一致：1＝{H('聯盟', terms)}、2＝{H('部族', terms)}、3＝{H('自然', terms)}；"
        "112／212／312 是前三隻，榮譽數值為同級的一半；401 只有達達，榮譽加的是英雄生命（104），不是陣營英雄屬性。"
    ))
    add(tbl["catalog"])
    add(p_html(
        "史萊姆 17 階品質 5：史萊姆帝皇（名稱鍵與皮膚編號不一致，對照見資料說明）。"
        "達達的解鎖時間為 2026-08-10 00:00:00 至 2026-10-01 00:00:00；"
        "鐵喙為 2030-08-10 00:00:00 至 2030-10-01 00:00:00。只照錄。"
    ))
    add(p_html(
        f"蛋與寶箱字串可對上部分基礎名：「{H(o.box_good_name, terms)}」寫「{H(o.box_good_desc, terms)}」；"
        f"「{H(o.box_rare_name, terms)}」寫「{H(o.box_rare_desc, terms)}」。這是道具說明，不是主表名稱欄。"
        f"「{H(o.cactus_egg_name, terms)}」寫「{H(o.cactus_egg_desc, terms)}」，與基礎顯示名「仙人掌寶寶」不完全相同，只並列。"
    ))
    add(p_html(
        "品質欄是突破表上的 2–6，會隨突破提高。"
        f"寵物蛋說明用「優良／稀有／史詩」：{H(o.egg_names['pet_egg_05'], terms)}寫「{H(o.egg_descs['goods_desc_30001'], terms)}」；"
        f"{H(o.egg_names['pet_egg_08'], terms)}寫「{H(o.egg_descs['goods_desc_30002'], terms)}」；"
        f"{H(o.egg_names['pet_egg_09'], terms)}寫「{H(o.egg_descs['goods_desc_30003'], terms)}」。"
        f"字串另有「{H(o.quality_common, terms)}」，"
        "沒有完整的品質 2–6 名稱表，本頁不以蛋文案自動給每隻標品質中文名。"
    ))
    add("    </section>")

    add('    <section id="upgrade">')
    add("      <h2>升級</h2>")
    add(p_html(
        "21 隻都是 1–120 級，升級消耗數量曲線完全相同，合計 829,700（1 級消耗為 -1，從 2 級起累加）。"
        "消耗欄只寫數字，沒有道具 id。"
        f"道具 284「{H(o.food_name, terms)}」說明為「{H(o.food_desc, terms)}」，"
        f"289「{H(o.essence_name, terms)}」說明為「{H(o.essence_desc, terms)}」；"
        "本頁不把升級表這個數字自行斷定成只扣口糧或口糧加精華。<code>build_level_limit</code> 全表為 1。"
        f"另外，升級表有獨立的額外消耗欄，消耗的是{H(o.essence_name, terms)}："
        "830xxx 自 61 級至 90 級、840xxx 自 91 級至 120 級出現。第 21 章升級節未列出此欄，本頁按表補上。"
    ))
    add(p_html(f"升級介面字串：「{H(o.need_break_tips, terms)}」。"))
    add(tbl["costs"])
    add(p_html("91–120 級因增量不固定，逐級照錄（列是十位區間，欄 0–9 是個位）："))
    add(tbl["costs_91"])
    add(p_html(
        f"升級屬性只有「{H(o.attr_names[30004], terms)}」（點數類屬性）。"
        "830001–830003 共用一條曲線：1 級 3318（戰力 6,636），120 級 1,626,331（戰力 3,252,662）。"
        "840001–840018 的 1 級與 120 級同為 5530（戰力 11,060）與 2,710,552（戰力 5,421,104）。"
        "後 18 隻不是逐級完全相同：840010–840018 在 70 級生命／戰力都比 840001 高 1,000／2,000；"
        "840014 另外在 8 級生命／戰力高 10／20。"
        "分解值在少數級也有差異（840010–840015 在 83 級為 241,000，840001 為 240,900；"
        "840016–840018 在 83 級為 241,600／241,700／241,800，在 119 級為 416,000／417,000／418,000，840001 為 410,000）。"
        "差異只出現在少數級，本頁不把它寫成另一條完整曲線，也不解釋原因。下面只列關鍵級屬性。"
    ))
    add(tbl["level_attrs"])
    add(tbl["extras"])
    add("    </section>")

    add('    <section id="break">')
    add("      <h2>突破與轉化率</h2>")
    add(p_html(
        f"突破會提高 <code>conversion_rate</code>（官方稱{H(o.attr_percent, terms)}）、"
        f"{H(o.attr_break_all, terms)}（界面字串同樣是「{H(o.attr_break_all, terms)}」）、"
        "等級上下限，並解鎖或提升技能。"
        f"材料說明：「{H(o.title020, terms)}」。"
        "消耗欄分段記錄，表上沒有標題說明各段含義，本頁只照錄原值，記法見資料說明。"
        f"額外消耗是道具「{H(o.essence_name, terms)}」："
        "830xxx 自 12 階、840xxx 自 18 階起出現。"
        "830xxx 從 12 階、840xxx 從 18 階起有賽季限制欄，只照錄，不標未開放。欄位名見資料說明。"
    ))
    add(p_html(
        "830001–830003 的突破中間值（消耗、轉化率、品質、技能等級、103／104）三隻相同，18 列（0–17 階）。"
        "轉化率 0 階 2000，17 階 8800。0 階全英雄加成是英雄攻擊 50、英雄生命 50，之後每階各 +50，17 階為 900／900。"
        "技能 1 在 0 階為 1 級，2 階升至 2，4 階升至 3（滿）；技能 2 在 5 階解鎖，7／9 階升至 2／3；技能 3 在 11 階解鎖（只有 1 級）。"
        "史萊姆 0 階 <code>pet_lv_max</code> 20、17 階 90。"
    ))
    add(tbl["br830"])
    add(p_html(
        "18 筆 840xxx 的轉化率、品質與技能解鎖節奏相同，19 列（5–23 階）。"
        "轉化率 5 階 3600，23 階 10800。"
        "技能四個：1、2 在 5 階即為 1 級，其後升至 4 級（技能 1 於 7／9／12 階、技能 2 於 8／10／14 階升至 2／3／4）；"
        "技能 3 在 11 階解鎖，13／16 階升至 2／3；技能 4 在 17 階解鎖（1 級）。"
        "品質 5 階為 3，11 階為 4，17 階為 5，23 階為 6。閃啾啾 5 階等級上限 35、23 階 120。"
        "消耗欄分成兩組：840001–840014、840016、840018 從 6 階起是一組記法；"
        "火花與達達從 6 階起多為另一組記法。原值記法見資料說明。"
    ))
    add(tbl["br840a"])
    add(tbl["br840b"])
    add(p_html(
        f"{H(o.attr_break_all, terms)}分成五組另加前三隻，原值照錄，不自行換成百分比。"
    ))
    add(tbl["attr_groups"])
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>技能</h2>")
    add(p_html(
        "突破表列出每隻的技能編號與目前等級（0 表示尚未解鎖）。81 個技能編號全部能在技能表對上。"
        "名稱取技能表上的名稱。"
        f"部分 4 號技能共用「{H(o.shelter['聯盟的庇護'], terms)}」「{H(o.shelter['部落的庇護'], terms)}」"
        f"「{H(o.shelter['自然的庇護'], terms)}」這組鍵；達達的 4 號技能是「{H(o.shelter['魔狗的庇護'], terms)}」。"
        "雪團子 3 號技能的名稱鍵是 <code>hero_skill_name_8401203</code>（「優雅」），"
        "時光龍 3 號技能的名稱鍵是 <code>hero_skill_name_8401103</code>（「龍威」），鍵與寵物編號交叉，照表登錄。"
        "蓬蓬崽的技能 id 是 8400301–8400304，絨嗚嗚是 8400201–8400204，也與寵物編號交叉，照表登錄。"
        "達達 3 號技能名稱鍵是 <code>hero_skill_name_84017033</code>（堅硬表皮）。"
        "鐵喙前三個技能的名稱鍵（<code>hero_skill_name_8401801</code>–<code>8401803</code>）在字串表沒有內容，不編造技能名；"
        f"第四個技能仍是「{H(o.shelter['聯盟的庇護'], terms)}」。"
        "每隻只列 origin_break 與滿突破的技能文案，不展每一中間等級。"
        "毛茸茸「揚塵」基礎文案兩處 <code>{1}</code> 都代入同一參數 6，參數表另有未使用的 1.5，照錄不猜、不自行挪位。"
    ))
    for p in data.pets:
        add(f'      <h3 id="skill-{p.pid}">{H(p.base_name, terms)}（{p.pid}）</h3>')
        add(p_html(
            "技能 id：" + "、".join(str(s.sid) for s in p.skills)
            + f"。滿突破技能等級：{'／'.join(str(x) for x in p.breaks[-1].skill_levels)}。"
        ))
        add(tbl["skills"][p.pid])
    add("    </section>")

    add('    <section id="guidebook">')
    add("      <h2>圖鑑與榮譽牆</h2>")
    add(p_html(
        f"圖鑑介面字串：「{H(o.title003_dec, terms)}」（<code>pet_title003_dec</code>）。"
        f"寵物圖鑑 58 級，每級有經驗與給英雄的"
        f"{H(o.attr_names[3], terms)}、{H(o.attr_names[4], terms)}（點數類屬性）。"
        f"<code>attr_pet</code> 全表為空。經驗合計 {data.guidebook_exp_total:,}。"
        "成就表 393 筆按寵物 id 與 <code>need_level</code>／<code>need_break</code> 給圖鑑經驗等，本頁不逐條展開。"
    ))
    add(tbl["guidebook"])
    add(p_html(f"{H(o.honour_name, terms)}說明（<code>pet_honour_info_1</code>）："))
    add(f"<blockquote>{highlight_lines(o.honour_info, terms)}</blockquote>")
    add(p_html(
        "榮譽牆表 2 筆，品質 5／6。生命值 40／80，戰力 160／880。"
        "<code>need_chip</code> 分別照錄，各段含義未標，不解讀。"
    ))
    add(tbl["honor"])
    add(p_html(
        "榮譽牆加成表 100 筆，10 個榮譽組（與寵物組別相同），"
        "門檻 50–500 每 50 一級。中間檔按門檻線性遞增（101 組每檔 +50，112 組每檔 +25），戰力同樣按檔遞增。原值照錄。"
    ))
    add(tbl["bonus"])
    add("    </section>")

    add('    <section id="incubate">')
    add("      <h2>孵化與搜索</h2>")
    add(p_html(
        "孵化表 5 筆。前 3 筆編號與 830001–830003 相同，消耗對應三種寵物蛋，"
        "孵化時間 14,400／21,600／28,800 秒（4／6／8 小時）。"
        "沒有對應的道具短名鍵；界面短名見上文優良／稀有／史詩寵物蛋。鍵名見資料說明。"
        "830002 列有保底：<code>is_guaranteed=1</code>，<code>guaranteed_pet_id</code> 為 830001｜830002｜830003，"
        f"<code>probability_time=4</code>，與字串「{H(o.guaranteed, terms)}」相符。"
        "後兩筆 id 830004／830005 不在 <code>pet_detail</code>，也沒有 30004／30005 的道具說明，"
        "不編造這兩種蛋的名稱與孵出結果（<code>pet_reward</code> 為 15004／15005，字串表沒有對應道具名）。"
    ))
    add(tbl["incubate"])
    add(p_html(
        "搜索任務表 3 筆，名稱為優良／稀有／史詩寵物蛋，是搜索任務而不是 21 隻寵物的定義。"
        "<code>pet_info_tips_1</code> 與 <code>_4</code> 文案不完全相同，兩則並列，不合併、不另推次數表。"
    ))
    add(p_html("搜索說明（<code>pet_info_tips_1</code>，完成任務時 33.33%、蛋最多存在 24 小時）："))
    add(f"<blockquote>{highlight_lines(o.tips['pet_info_tips_1'], terms)}</blockquote>")
    add(p_html("另一則（<code>pet_info_tips_4</code>，接取特殊任務 33.33%、蛋最多存在 72 小時）："))
    add(f"<blockquote>{highlight_lines(o.tips['pet_info_tips_4'], terms)}</blockquote>")
    add(p_html(f"<code>pet_info_tips_8</code>：「{H(o.tips['pet_info_tips_8'], terms)}」"))
    add(tbl["egg_tasks"])
    add(p_html(
        "口糧轉換表 9 筆，消耗 100–4000、上限 20–99999，獎勵編號 110411–110419，"
        "字串表沒有這些獎勵的名稱，關係未驗證，不猜。"
    ))
    add(tbl["food"])
    add(p_html(
        "重生說明（<code>pet_info_tips_5</code>、<code>pet_function_reborn_tips2</code>）："
    ))
    add(f"<blockquote>{highlight_lines(o.tips['pet_info_tips_5'], terms)}</blockquote>")
    add(p_html(f"另寫：「{H(o.reborn_tips2, terms)}」"))
    add(p_html(
        f"<code>pet_info_tips_6</code>：「{H(o.tips['pet_info_tips_6'], terms)}」"
        "這是官方說明，不是本頁對賽季開放的判斷。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(f"<li>{H('英靈', terms)}（見已發佈的<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>，英靈不是寵物）。"
        "帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場等伴侶與休閒系統。</li>")
    add("<li>寵物主表不存在的穩定 <code>pet_name_{id}</code>；不以寶箱俗稱覆寫皮膚名稱鍵。</li>")
    add("<li>升級消耗欄對應的確切道具（口糧／精華／兩者），以及突破消耗各段的含義。</li>")
    add("<li>技能解鎖門檻＝10／20／30／40 的含義；屬性 1133 沒有對應官方屬性名，"
        "與 <code>pet_building_attr_cd</code> 是否同一界面顯示待確認。</li>")
    add("<li>孵化表 830004／830005、獎勵 id 15001–15006／110411–110419 的名稱與實際孵出內容。</li>")
    add("<li>圖鑑成就 393 筆、搜索任務次數與協助獎勵的完整數值表、儲值與禮包。</li>")
    add("<li>寵物樂園全部 41 列的中間值，以及兩張升級表不同的 <code>buildTime</code>／<code>cost3</code> 逐級對照。"
        "也不把 <code>para1</code>／<code>para2</code> 自行指定為哪一欄。</li>")
    add("<li>升級 2,520 列逐級表、突破 396 列逐階全表，以及每一中間突破等級的技能文案。</li>")
    add("<li>解鎖時間、賽季限制與賽季日曆的對應（不標未開放）。</li>")
    add("<li>與英雄技能、站位的搭配模擬，以及轉化公式代入面板後的戰鬥結算。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<ul>")
    add("<li>以下是整理用註記，查寵物名稱與效果可略過。</li>")
    add(
        "<li>技能文案以 <code>hero_component</code> 的 <code>desc1</code>–<code>desc5</code> 填入對應參數後照錄。"
        "<code>desc1</code> 是基礎效果，其後各段是升階追加。"
        "若文案兩個位置都寫 <code>{1}</code>，兩處都代入同一參數。"
        "官方顯示名是鐵喙。寵物技能「部落的庇護」照錄官方字。"
        "不要發明「寵物榮譽塵」。"
        "功能表 <code>function.json</code> id 63 開啟面板是 <code>show_pet_list_panel</code>，"
        "<code>func_open_param</code> 為 <code>7|160|1</code>。"
        "定義列全部 <code>hide=0</code>、<code>is_lock=0</code>。"
        "突破消耗欄寫成 <code>1|0|n</code>、<code>2|0|n</code> 或 <code>2|5|n</code>；"
        "額外消耗 <code>extra_cost</code>／升級 <code>cost_extra</code> 為 <code>2|289|數量</code>（寵物精華）。"
        "830xxx 從 12 階、840xxx 從 18 階起 <code>season_limit=2</code>、<code>season_limit_new=[1, 35]</code>。"
        "達達 <code>unlocktime</code> 為 <code>2026-08-10 00:00:00|2026-10-01 00:00:00</code>；"
        "鐵喙為 <code>2030-08-10 00:00:00|2030-10-01 00:00:00</code>。</li>"
    )
    add("<li><strong>寵物主表沒有名稱欄，也沒有穩定的 <code>pet_name_{id}</code>。</strong>"
        "能對上的路徑是：突破表的 <code>pet_skin_id</code> → <code>skin.json</code>（頭像圖集為 "
        "<code>Atlas/UI_Pet_Head</code>）的 <code>name</code> 欄 → <code>strings_zh</code>。"
        "不能用皮膚 id 或寵物 id 直接推鍵名。這組 <code>hero_name_*</code> 不是 <code>hero_detail</code> 裡的英雄。"
        "史萊姆最終型態皮膚 id 是 56004，鍵卻是 <code>hero_name_56003</code>。"
        "寶箱俗稱若與皮膚顯示名不同，只並列，不以寶箱文案覆寫表上的鍵。</li>"
)
    add("<li>本頁只寫 <code>pet_*</code> 這套系統。定義在 <code>pet_detail.json</code>（21 筆），升級在 <code>pet_level.json</code>（2,520 筆，每隻 1–120 級），"
        "突破在 <code>pet_break.json</code>（396 筆），圖鑑在 <code>pet_guidebook.json</code>（58 級），"
        "榮譽在 <code>pet_honor.json</code>（2 筆）與 <code>pet_honor_bonus.json</code>（100 筆），"
        "孵化在 <code>pet_incubate.json</code>（5 筆），搜索蛋任務在 <code>pet_egg_task.json</code>（3 筆），"
        "口糧轉換在 <code>pet_food_convert.json</code>（9 筆），成就在 <code>pet_achievement.json</code>（393 筆，本頁不逐條展開）。"
        f"{H(o.park_name, terms)}升級在 <code>citybuilding_lvup.json</code>／<code>citybuilding_lvup_new.json</code>"
        "（建築 <code>index</code> 160，0–40 級共 41 列）。技能定義在 <code>hero_component.json</code>，81 個技能 id 全部能對上。"
        "不要從 <code>unlocktime</code>、<code>season_limit</code>、<code>season_limit_new</code> 或孵化說明裡的賽季字樣自動標未開放。"
        "屬性名用 <code>attribute_name_{id}</code>。升級主屬性 30004 為 <code>show_type=1</code>；"
        "突破 <code>attr_role</code> 的 103／104、3103／3104、4103／4104、5103／5104 都是 <code>show_type=2</code>，只錄原值。</li>")
    add(f"<li>{_data_notes(data)}</li>")
    add("<li>待補：名稱鍵為何不統一、客戶端中間型態實際顯示哪一個鍵；突破消耗欄各段含義；"
        "升級主欄數字對應哪種道具；830004／830005 與無名稱獎勵 id；鐵喙前三個技能在客戶端顯示什麼；"
        "屬性 1133 與 <code>pet_building_attr_cd</code> 是否同一顯示；"
        "突破 <code>attr_role</code> 為何分成 103／104 的 170／250 起點與三營／達達的 510／750 起點；"
        "以及兩張樂園升級表 cost3／buildTime 以哪一張為準。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {PET_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_pet_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    o = data.official
    park = md_table(
        ["樂園等級", "para1", "para2", "string_para2（id｜原值）", "戰力", "備註"],
        [[
            str(r.lv), str(r.para1), str(r.para2),
            _fmt_para2(r.string_para2, r.attrs), str(r.fightforce), r.note or EMPTY,
        ] for r in data.park],
    )
    defs = md_table(
        ["基礎名", "寵物編號", "組別", "陣營（依榮譽組）", "突破", "品質起迄", "分解值", "圖鑑開放天數", "解鎖時間（只照錄）"],
        [[
            p.base_name, str(p.pid), str(p.group_id), p.faction,
            f"{p.origin_break}–{p.break_max}", f"{p.quality_start}→{p.quality_end}",
            str(p.decomposed_get), str(p.guidebook_openday), format_unlocktime(p.unlocktime),
        ] for p in data.pets],
    )
    catalog = md_table(
        ["基礎名", "寵物 id", "基礎名稱鍵", "基礎皮膚", "後續型態（皮膚或顯示名有變化的階段）"],
        [[p.base_name, str(p.pid), p.base_name_key, str(p.base_skin), _morph_plain(p)] for p in data.pets],
    )
    band_rows = [["1", "-1", EMPTY, "0（不計入合計）"]]
    for (lo, hi), start, step in COST_BANDS:
        total = sum(start + (lv - lo) * step for lv in range(lo, hi + 1))
        band_rows.append([f"{lo}–{hi}", str(start), f"+{step}", str(total)])
    band_rows.append([
        "91–120", "5900",
        "多為 +100；95、98、101、104、107、110、113、116、119 級為 +200",
        str(sum(COST_91_120)),
    ])
    band_rows.append(["合計（2–120 級）", EMPTY, EMPTY, str(LEVEL_COST_TOTAL)])
    costs = md_table(["等級區間", "該段起始消耗", "每級增量", "段合計"], band_rows)
    costs_91 = md_table(
        ["等級"] + [str(i) for i in range(0, 10)],
        [
            ["91–100"] + [str(x) for x in COST_91_120[:10]],
            ["101–110"] + [str(x) for x in COST_91_120[10:20]],
            ["111–120"] + [str(x) for x in COST_91_120[20:]],
        ],
    )
    slime = next(p for p in data.pets if p.pid == 830001)
    flash = next(p for p in data.pets if p.pid == 840001)
    crab = next(p for p in data.pets if p.pid == 840014)
    beak = next(p for p in data.pets if p.pid == 840018)
    key_lvs = (1, 10, 20, 40, 70, 90, 120)
    attr_rows = []
    for label, pet in (
        ("830001–830003", slime),
        ("840001–840009（70／8 級基準）", flash),
        ("840014（8 級例外）", crab),
        ("840010–840018（70 級例外；840014 亦屬此組）", beak),
    ):
        cells = [label]
        for lv in key_lvs:
            k = next((x for x in pet.level_keys if x.level == lv), None)
            cells.append(f"{k.attr_30004}／{k.fightforce}" if k else EMPTY)
        attr_rows.append(cells)
    level_attrs = md_table(["曲線"] + [f"{lv} 級 30004／戰力" for lv in key_lvs], attr_rows)
    extras = md_table(
        ["寵物", "出現等級", "額外消耗", "段合計（精華數量）"],
        [
            ["830001–830003", "61–90", "2|289|25 起，逐級增加至 2|289|1250", "16875"],
            ["840001–840018", "91–120", "2|289|50 起，逐級增加至 2|289|2500", "33750"],
        ],
    )

    def break_md(pet: PetInfo, include_attr: bool, cost_header: str) -> str:
        headers = ["突破階", "轉化率", "品質", "技能等級", "等級上下限", cost_header, "extra_cost"]
        if include_attr:
            headers.append("attr_role 原值")
        headers.append("season（只照錄）")
        rows = []
        for r in pet.breaks:
            cells = [
                str(r.break_level), str(r.conversion_rate), str(r.quality),
                "／".join(str(x) for x in r.skill_levels),
                f"{r.pet_lv_min}–{r.pet_lv_max}",
                format_cost(r.cost), format_cost(r.extra_cost),
            ]
            if include_attr:
                cells.append("、".join(f"{k}｜{v}" for k, v in r.attr_role.items()))
            if r.season_limit not in (None, "", 0, -1) or r.season_limit_new not in (None, "", [], -1):
                cells.append(f"season_limit={r.season_limit}；season_limit_new={r.season_limit_new}")
            else:
                cells.append(EMPTY)
            rows.append(cells)
        return md_table(headers, rows)

    dada = next(p for p in data.pets if p.pid == 840017)
    labels = [
        ((103, 104), (170, 250), (3230, 4750), "閃啾啾、蓬蓬崽、絨嗚嗚、雪球寶寶、翠牙苗"),
        ((3103, 3104), (510, 750), (9690, 14250), "蛋仔、燭寶、雪團子、疾風、鐵喙"),
        ((4103, 4104), (510, 750), (9690, 14250), "火苗喵喵、虎寶、時光龍·柯羅諾斯、火花"),
        ((5103, 5104), (510, 750), (9690, 14250), "仙人掌寶寶、天馬、潮汐蟹"),
        ((103, 104), (510, 750), (9690, 14250), "達達"),
        ((103, 104), (50, 50), (900, 900), "史萊姆、毛茸茸、噗噗豬（0–17 階）"),
    ]
    attr_groups = md_table(
        ["屬性（只錄原值）", "起點原值", "滿檔原值", "寵物"],
        [[
            f"{o.attr_names[ids_[0]]}（{ids_[0]}）／{o.attr_names[ids_[1]]}（{ids_[1]}）",
            f"{origin[0]}／{origin[1]}", f"{mx[0]}／{mx[1]}", members,
        ] for ids_, origin, mx, members in labels],
    )
    skills = {}
    for p in data.pets:
        skills[p.pid] = md_table(
            ["階段", "技能文案"],
            [
                [f"{p.origin_break} 階（origin_break）", _skill_block_plain(p, "origin")],
                [f"{p.break_max} 階（滿突破）", _skill_block_plain(p, "max")],
            ],
        )
    gkey = (1, 10, 20, 30, 40, 50, 58)
    gb_rows = [[str(g.level), str(g.exp), str(g.atk), str(g.hp), str(g.fightforce)] for g in data.guidebook if g.level in gkey]
    gb_rows.append(["經驗合計（1–58 級）", str(data.guidebook_exp_total), EMPTY, EMPTY, EMPTY])
    guidebook = md_table(["圖鑑等級", "該級經驗", "攻擊（3）", "生命值（4）", "戰力"], gb_rows)
    honor = md_table(
        ["品質", "屬性", "戰力", "need_chip（各段含義未標，不解讀）"],
        [[str(r.quality), f"{r.attr_name}（{r.attr_id}） {r.attr_value}", str(r.combat), r.need_chip] for r in data.honor],
    )
    bonus = md_table(
        ["榮譽組", "屬性", "50 檔原值", "500 檔原值", "50／500 戰力", "寵物"],
        [[
            str(r.group), f"{r.attr_name}（{r.attr_id}）", str(r.values[50]), str(r.values[500]),
            f"{r.combats[50]}／{r.combats[500]}", "、".join(r.pets),
        ] for r in data.honor_bonus],
    )
    incubate = md_table(
        ["id", "在 pet_detail", "消耗", "時間（秒）", "pet_reward", "is_guaranteed", "guaranteed_pet_id", "probability_time", "guaranteed_reward", "蛋短名", "蛋說明"],
        [[
            str(r.iid), "是" if r.in_detail else "否", str(r.cost), str(r.time), str(r.pet_reward),
            str(r.is_guaranteed), format_unlocktime(r.guaranteed_pet_id), str(r.probability_time),
            str(r.guaranteed_reward),
            r.egg_name or "（不在 pet_detail，不編造蛋名）",
            r.egg_desc or EMPTY,
        ] for r in data.incubate],
    )
    egg_tasks = md_table(
        ["id", "名稱", "名稱鍵", "time", "disappear_time"],
        [[str(r["id"]), r["name"], str(r["name_key"]), str(r["time"]), str(r["disappear_time"])] for r in data.egg_tasks],
    )
    food = md_table(
        ["id", "消耗", "上限", "獎勵 id", "名稱"],
        [[str(r["id"]), str(r["consume"]), str(r["upper_limit"]), str(r["reward_id"]), "字串表沒有名稱，關係未驗證"] for r in data.food_convert],
    )
    return {
        "park": park, "defs": defs, "catalog": catalog, "costs": costs, "costs_91": costs_91,
        "level_attrs": level_attrs, "extras": extras,
        "br830": break_md(slime, True, "消耗（照錄）"),
        "br840a": break_md(flash, False, "消耗（840a，照錄）"),
        "br840b": break_md(dada, False, "消耗（火花／達達，照錄）"),
        "attr_groups": attr_groups, "skills": skills, "guidebook": guidebook,
        "honor": honor, "bonus": bonus, "incubate": incubate, "egg_tasks": egg_tasks, "food": food,
    }


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    add_lines: list[str] = []
    add = add_lines.append
    add("# Top Heroes Wiki｜寵物總表")
    add("")
    add(LEDE)
    add("")
    add("英靈不是寵物；本頁只寫 pet_* 這套系統。")
    add("")
    add("交叉引用：[裝備總表](equipment.html)、[領主裝備總表](lord-equipment.html)、[士兵總表](troops.html)、[秘寶總表](artifacts.html)；[專武總表](exclusive.html)、[英靈總表](valhalla.html)（英靈不是寵物）。")
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add("正文只根據遊戲資料表與官方字串，不評定寵物強弱，也不排行。"
        f"官方界面稱「{o.system_name}」。影響力目錄「{o.partner_dir}」底下再分「{o.system_name}」、「{o.catalog_name}」、「{o.honour_name}」。")
    add("")
    add("- **本頁只寫 `pet_*` 這套寵物系統。** 定義在 `pet_detail.json`（21 筆），升級在 `pet_level.json`（2,520 筆，每隻 1–120 級），突破在 `pet_break.json`（396 筆），圖鑑在 `pet_guidebook.json`（58 級），榮譽在 `pet_honor.json`（2 筆）與 `pet_honor_bonus.json`（100 筆），孵化在 `pet_incubate.json`（5 筆），搜索蛋任務在 `pet_egg_task.json`（3 筆），口糧轉換在 `pet_food_convert.json`（9 筆），成就在 `pet_achievement.json`（393 筆，本頁不逐條展開）。寵物樂園升級在 `citybuilding_lvup.json`／`citybuilding_lvup_new.json`（建築 `index` 160，0–40 級共 41 列）。技能定義在 `hero_component.json`，81 個技能 id 全部能對上。")
    add("- **寵物主表沒有名稱欄，也沒有穩定的 `pet_name_{id}`。** 能對上的路徑是：突破表的 `pet_skin_id` → `skin.json`（頭像圖集為 `Atlas/UI_Pet_Head`）的 `name` 欄 → `strings_zh`。不能用皮膚 id 或寵物 id 直接推鍵名。這組 `hero_name_*` 不是 `hero_detail` 裡的英雄。史萊姆最終型態皮膚 id 是 56004，鍵卻是 `hero_name_56003`。寶箱俗稱若與皮膚顯示名不同，只並列，不以寶箱文案覆寫表上的鍵。")
    add("- **不要從 `unlocktime`、`season_limit`、`season_limit_new` 或孵化說明裡的賽季字樣自動標未開放。** `unlocktime` 只照錄。屬性名用 `attribute_name_{id}`。升級主屬性 30004「戰鬥中英雄生命增加」（`show_type=1`）；突破 `attr_role` 的 103／104、3103／3104、4103／4104、5103／5104 都是 `show_type=2`，只錄原值，不自行換算成百分比。寵物屬性轉化率寫在突破表 `conversion_rate`，不是屬性 id。")
    add("- 技能文案以 `hero_component` 的 `desc1`–`desc5` 填入對應參數後照錄。`desc1` 是基礎效果，其後各段是升階追加，不是另寫一條完整技能。若文案兩個位置都寫 `{1}`，兩處都代入同一參數。官方轉化公式不是戰鬥傷害公式，不代入面板去做戰鬥結算。正式用語是部族不是部落；唯一例外是官方字串本身寫「部落」（如「部落的庇護」）時原文引用。")
    add("")
    add("## 範圍與解鎖")
    add("")
    add(f"`function.json` id 63 的開啟面板是 `{data.function63['openPanel']}`，`func_open_param` 為 `{data.function63['func_open_param']}`（對應{o.park_name} 1 級），提示字串「{o.function_closed}」（`pet_egg_13`）。名稱欄鍵是 `lord_equip_01`，字串表沒有這條，名稱欄為空。")
    add("")
    add("21 筆定義：830001–830003 與 840001–840018。前 3 筆 `break_max` 為 17、`origin_break` 為 0、`decomposed_get` 為 100、`guidebook_openday` 為 3；後 18 筆分別為 23、5、600、5。全部 `hide=0`、`is_lock=0`，`component_unlock` 皆為 10／20／30／40（含義表上未標，不猜）。`guidebook_server_list` 21 筆相同。840017、840018 有 `unlocktime`，只照錄，不標未開放。")
    add("")
    add(tbl["defs"])
    add("")
    add("## 系統規則（官方字串）")
    add("")
    add("轉化公式（`pet_function_attr_tips_1`／`_2`，不是戰鬥傷害公式）原文：")
    add("")
    add("```")
    add(o.formula_1)
    add("```")
    add("")
    add("上陣後的對照文案（`pet_function_attr_tips_2`）原文：")
    add("")
    add("```")
    add(o.formula_2)
    add("```")
    add("")
    add("養成說明（`pet_info_tips_2`）：")
    add("")
    add("```")
    add(o.tips["pet_info_tips_2"])
    add("```")
    add("")
    add("上陣說明（`pet_info_tips_3`）：")
    add("")
    add("```")
    add(o.tips["pet_info_tips_3"])
    add("```")
    add("")
    add("戰鬥與轉化說明（`pet_attr_info_tips`）：")
    add("")
    add("```")
    add(o.tips["pet_attr_info_tips"])
    add("```")
    add("")
    add(f"## {o.park_name}")
    add("")
    add(f"建築 160，官方名稱「{o.park_name}」，說明：「{o.park_des}」。升級表 0–40 級（41 列）。"
        f"`para1` 在 0–10 級為 1、11–30 級為 2、31–40 級為 3；`para2` 在 0–34 級為 1、35–40 級為 2。"
        "表沒有把這兩欄逐一標上「孵化欄位／搜尋等級／縮短時間」，本頁只錄數值，不自行指定為哪一欄。"
        f"`string_para2` 從 1 級起有屬性 1133（字串表沒有 `attribute_name_1133`；`attribute.json` 裡 id 1133 的 `name` 欄是 `{o.attr_1133_key}`，對應「{o.attr_1133_name}」，本頁不自行斷定界面一定用這個名稱顯示），1 級 100、40 級 4000；1192 自 10 級、1191 自 20 級，40 級 1191 為 2。"
        f"0–39 級 cost1／cost2 為類型 999、資源 4／5（{o.wood}／{o.stone}），兩張升級表這兩欄相同；40 級沒有再升級消耗。"
        "cost3 與 buildTime 在兩張升級表並不完全相同，本頁不把這兩欄寫成單一數值。戰力 0／1／20／40 級為 0／300／10,950／140,550。")
    add("")
    add(tbl["park"])
    add("")
    add("## 名錄與型態名稱")
    add("")
    add("顯示名取自該突破階段的皮膚 `name` 鍵。基礎名是各隻第一筆突破列的顯示名；後續型態只列皮膚或顯示名有變化的階段。"
        "`group_id` 百位：1＝聯盟、2＝部族、3＝自然；112／212／312 是前三隻，榮譽數值為同級一半；401 只有達達，榮譽加的是英雄生命（104）。")
    add("")
    add(tbl["catalog"])
    add("")
    add("史萊姆 17 階品質 5：史萊姆帝皇（`hero_name_56003`，皮膚 56004），鍵與皮膚 id 不一致。"
        "840017 達達的 `unlocktime` 為 `2026-08-10 00:00:00|2026-10-01 00:00:00`；"
        "840018 鐵喙為 `2030-08-10 00:00:00|2030-10-01 00:00:00`。只照錄。")
    add("")
    add(f"「{o.box_good_name}」寫「{o.box_good_desc}」；「{o.box_rare_name}」寫「{o.box_rare_desc}」。這是道具說明，不是主表名稱欄。"
        f"「{o.cactus_egg_name}」寫「{o.cactus_egg_desc}」，與基礎顯示名「仙人掌寶寶」不完全相同，只並列。")
    add("")
    add("品質欄是突破表上的 2–6，會隨突破提高。字串另有 `pet_function_quality_type_1`「普通」，沒有完整的品質 2–6 名稱表，本頁不以蛋文案自動給每隻標品質中文名。")
    add("")
    add("## 升級")
    add("")
    add("21 隻都是 1–120 級，升級消耗數量曲線完全相同，合計 829,700（1 級消耗為 -1，從 2 級起累加）。"
        f"消耗欄只寫數字，沒有道具 id。道具 284「{o.food_name}」說明為「{o.food_desc}」，289「{o.essence_name}」說明為「{o.essence_desc}」；"
        "本頁不把升級表這個數字自行斷定成只扣口糧或口糧加精華。`build_level_limit` 全表為 1。"
        "另外，升級表有獨立欄 `cost_extra`，寫成 `2|289|數量`：830xxx 自 61 級至 90 級、840xxx 自 91 級至 120 級出現。第 21 章升級節未列出此欄，本頁按表補上。")
    add("")
    add(f"升級介面字串：「{o.need_break_tips}」。")
    add("")
    add(tbl["costs"])
    add("")
    add("91–120 級因增量不固定，逐級照錄（列是十位區間，欄 0–9 是個位）：")
    add("")
    add(tbl["costs_91"])
    add("")
    add("升級屬性只有「戰鬥中英雄生命增加」（30004，`show_type=1`）。830001–830003 共用一條曲線：1 級 3318（戰力 6,636），120 級 1,626,331（戰力 3,252,662）。840001–840018 的 1 級與 120 級同為 5530（戰力 11,060）與 2,710,552（戰力 5,421,104）。後 18 隻不是逐級完全相同：840010–840018 在 70 級生命／戰力都比 840001 高 1,000／2,000；840014 另外在 8 級生命／戰力高 10／20。分解值在少數級也有差異，本頁不把它寫成另一條完整曲線。")
    add("")
    add(tbl["level_attrs"])
    add("")
    add(tbl["extras"])
    add("")
    add("## 突破與轉化率")
    add("")
    add(f"突破會提高 `conversion_rate`（官方稱{o.attr_percent}）、{o.attr_break_all}（`attr_role`），以及等級上下限，並解鎖或提升技能。"
        f"材料說明：「{o.title020}」。消耗欄寫成 `1|0|n`、`2|0|n` 或 `2|5|n` 這類列，表上沒有標題說明各段含義，本頁只照錄。"
        f"`extra_cost` 為 `2|289|數量`（道具 289 {o.essence_name}）：830xxx 自 12 階、840xxx 自 18 階起出現。"
        "830xxx 從 12 階、840xxx 從 18 階起 `season_limit=2`、`season_limit_new=[1, 35]`，只照錄，不標未開放。")
    add("")
    add("830001–830003 的突破中間值三隻相同，18 列（0–17 階）。轉化率 0 階 2000，17 階 8800。0 階全英雄加成是英雄攻擊 50、英雄生命 50，之後每階各 +50，17 階為 900／900。")
    add("")
    add(tbl["br830"])
    add("")
    add("18 筆 840xxx 的轉化率、品質與技能解鎖節奏相同，19 列（5–23 階）。轉化率 5 階 3600，23 階 10800。消耗欄兩組：840001–840014、840016、840018 從 6 階起為 `1|5|n` 或 `1|5|n`＋`2|5|n`；火花與達達從 6 階起多為單一的 `2|5|n`。")
    add("")
    add(tbl["br840a"])
    add("")
    add(tbl["br840b"])
    add("")
    add(f"{o.attr_break_all}（`attr_role`）原值照錄（`show_type` 為 2），不自行換成百分比。")
    add("")
    add(tbl["attr_groups"])
    add("")
    add("## 技能")
    add("")
    add("81 個技能 id 全部能在 `hero_component` 對上。雪團子 3 號名稱鍵是 `hero_skill_name_8401203`（優雅），時光龍 3 號是 `hero_skill_name_8401103`（龍威），鍵與寵物編號交叉，照表登錄。蓬蓬崽技能 id 為 8400301–8400304，絨嗚嗚為 8400201–8400204，也與寵物編號交叉。達達 3 號名稱鍵是 `hero_skill_name_84017033`。鐵喙前三個技能名稱鍵在字串表沒有內容，不編造技能名；第四個仍是「聯盟的庇護」。每隻只列 origin_break 與滿突破技能文案。毛茸茸「揚塵」基礎文案兩處 `{1}` 都代入同一參數 6，參數表另有未使用的 1.5，照錄不猜。正式用語是部族，但技能名「部落的庇護」是官方字串，原文照錄。")
    add("")
    for p in data.pets:
        add(f"### {p.base_name}（{p.pid}）")
        add("")
        add("技能 id：" + "、".join(str(s.sid) for s in p.skills) + f"。滿突破技能等級：{'／'.join(str(x) for x in p.breaks[-1].skill_levels)}。")
        add("")
        add(tbl["skills"][p.pid])
        add("")
    add("## 圖鑑與榮譽牆")
    add("")
    add(f"圖鑑介面字串：「{o.title003_dec}」。`pet_guidebook.json` 58 級，經驗合計 {data.guidebook_exp_total:,}。`attr_pet` 全表為空。成就表 393 筆本頁不逐條展開。")
    add("")
    add(tbl["guidebook"])
    add("")
    add(f"{o.honour_name}說明（`pet_honour_info_1`）：")
    add("")
    add("```")
    add(o.honour_info)
    add("```")
    add("")
    add(tbl["honor"])
    add("")
    add("`pet_honor_bonus.json` 100 筆，10 個榮譽組，門檻 50–500 每 50 一級。原值照錄。")
    add("")
    add(tbl["bonus"])
    add("")
    add("## 孵化與搜索")
    add("")
    add("`pet_incubate.json` 5 筆。前 3 筆照錄；830004／830005 不在 `pet_detail`，不編造蛋名與孵出結果。"
        f"830002 列有保底，與字串「{o.guaranteed}」相符。")
    add("")
    add(tbl["incubate"])
    add("")
    add("`pet_egg_task.json` 3 筆是搜索任務不是 21 隻定義。`pet_info_tips_1` 與 `_4` 不相同（完成任務 33.33%、24 小時 vs 接取特殊任務 33.33%、72 小時），兩則並列，不合併、不另推次數表。")
    add("")
    add("```")
    add(o.tips["pet_info_tips_1"])
    add("```")
    add("")
    add("```")
    add(o.tips["pet_info_tips_4"])
    add("```")
    add("")
    add(f"`pet_info_tips_8`：「{o.tips['pet_info_tips_8']}」")
    add("")
    add(tbl["egg_tasks"])
    add("")
    add("`pet_food_convert.json` 9 筆，獎勵 id 110411–110419，字串表沒有這些獎勵的名稱，關係未驗證，不猜。")
    add("")
    add(tbl["food"])
    add("")
    add("重生說明：")
    add("")
    add("```")
    add(o.tips["pet_info_tips_5"])
    add("```")
    add("")
    add(f"另寫：「{o.reborn_tips2}」")
    add("")
    add(f"`pet_info_tips_6`：「{o.tips['pet_info_tips_6']}」這是官方說明，不是本頁對賽季開放的判斷。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 英靈（見已上線英靈總表；英靈不是寵物）。帕魯、守護魔獸、精靈、魚缸、蝴蝶、乙太牧場。")
    add("- 寵物主表不存在的穩定 `pet_name_{id}`；不以寶箱俗稱覆寫皮膚名稱鍵。")
    add("- 升級消耗欄對應的確切道具，以及突破消耗 `1|0|n`、`2|5|n` 各段的含義。")
    add("- `component_unlock`＝10／20／30／40 的含義；屬性 1133 與 `pet_building_attr_cd` 是否同一界面顯示。")
    add("- 孵化表 830004／830005、獎勵 id 15001–15006／110411–110419 的名稱與實際孵出內容。")
    add("- 圖鑑成就 393 筆、搜索任務次數與協助獎勵的完整數值表、儲值與禮包。")
    add("- 寵物樂園全部 41 列的中間值，以及兩張升級表不同的 buildTime／cost3 逐級對照。也不把 para1／para2 自行指定為哪一欄。")
    add("- 升級 2,520 列逐級表、突破 396 列逐階全表，以及每一中間突破等級的技能文案。")
    add("- `unlocktime`、`season_limit` 與賽季日曆的對應（不標未開放）。")
    add("- 與英雄技能、站位的搭配模擬，以及轉化公式代入面板後的戰鬥結算。")
    add("")
    add("## 資料說明")
    add("")
    add(_data_notes(data))
    add("")
    add("待補：名稱鍵為何不統一、客戶端中間型態實際顯示哪一個鍵；突破消耗欄各段含義；升級主欄數字對應哪種道具；830004／830005 與無名稱獎勵 id；鐵喙前三個技能在客戶端顯示什麼；屬性 1133 與 `pet_building_attr_cd` 是否同一顯示；突破 `attr_role` 為何分成 103／104 的 170／250 起點與三營／達達的 510／750 起點；以及兩張樂園升級表 cost3／buildTime 以哪一張為準。")
    add("")
    return "\n".join(add_lines)
