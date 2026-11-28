"""Compile the published 守護魔獸 catalog tables from the 2026-11-05 extract."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .highlight import highlight, highlight_lines
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT
from .strings import clean, fmt_num

# 本頁只用 2026-11-05 解壓表與字串；不改 paths.DATA_CUTOFF。
EXTRACT_DIR = TOPHEROES_ROOT / "extracts/2026-11-05"
EXTRACT_DATA = EXTRACT_DIR / "data"
EXTRACT_STRINGS = EXTRACT_DIR / "strings_zh.json"

PAGE_CUTOFF = DATA_CUTOFF  # "2026-11-05"

EXPECTED_BEAST_IDS = (1001, 2001, 3001, 4001, 5001, 6001)
LEVEL_COUNT = 1020
STAR_COUNT = 606
RETURN_COUNT = 50
LEVELS_PER_BEAST = 170
STARS_PER_BEAST = 101
CORE_LEVELS = (20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170)
CORE_CORE_COUNTS = (1500, 3100, 3700, 4300, 4900, 5500, 6200, 6800, 7400, 8000, 8600, 9000, 9000, 9000, 9000, 9000)
KEY_LEVELS = (1, 10, 20, 30, 60, 80, 100, 110, 120, 121, 130, 160, 170)
SKILL_IDS = (
    2000001, 2000002,
    2000101, 2000102, 2000103, 2000111,
    2000201, 2000202, 2000203, 2000211,
    2000301, 2000302, 2000303, 2000311,
    2000401, 2000402, 2000403, 2000411,
    2000501, 2000502, 2000503, 2000511,
    2000601, 2000602, 2000603, 2000611,
)
UNNAMED_SKILL_IDS = (2000001, 2000111, 2000211, 2000311, 2000411, 2000511, 2000611)
RESONANCE_ALIASES = {
    2000403: 2000103,
    2000503: 2000203,
    2000603: 2000303,
}
TYPE_CRYSTAL = {1: 292, 2: 293, 3: 294}
TYPE_FACTION_ATTR = {
    1: {"atk1": 3003, "hp1": 3004, "cap": 1099, "atk2": 3103, "hp2": 3104, "red": 3019, "dmg": 3018},
    2: {"atk1": 4003, "hp1": 4004, "cap": 1100, "atk2": 4103, "hp2": 4104, "red": 4019, "dmg": 4018},
    3: {"atk1": 5003, "hp1": 5004, "cap": 1101, "atk2": 5103, "hp2": 5104, "red": 5019, "dmg": 5018},
}
FACTION_BY_TYPE = {1: "聯盟", 2: "部族", 3: "自然"}
GOODS_IDS = (160, 292, 293, 294, 295, 297, 32001, 32002, 32003, 32004, 32005, 32006, 230002)
BUILDING_INDEX = 178
CASTLE_INDEX = 117

TABLE_SHA256 = {
    "holybeast.json": "492cd3efa0c47c75d1af413f9d195cd554adf3d214a5ebd9ff2281c29857352b",
    "holybeast_level.json": "6f48b3f67b8cfc164e4f997a3584a026dc533af9072a93fa58a13e4a1960c97b",
    "holybeast_star.json": "4cb7912b1226432ffb3a712565f0ad5e00ddffc3c541c71d9586eb8c615a547a",
    "holybeast_return.json": "7c9f7061dccae4c62a45ac6531382862479d39ab37fe96ebc6c26138dfbc1345",
    "hero_component.json": "650805c241799d65c5adebeaf320feae75b9752333bf5f49c04a7e34c757acae",
    "attribute.json": "11409fb0a49e864db6a4d9575a69b5a6f29fbbd7e60307786cc10b96be0907aa",
    "function.json": "bb8acce49ecfe42bdc13c23acb8a0f0d7ae3144277b5451f34392165848cac40",
    "citybuilding_lvup.json": "0ac7918a26efd5680eb91f8f4265716faa20230a1ab00243443101637c569144",
    "jump.json": "58e9fd501074015aa7a65f94488bb20d78172e6107d57d8b50c2f894bc38de1d",
    "influence_level.json": "1fb4eed1f01870b8147d400fcc07554934bdbbf8d97f972b9712a4b9df6924dc",
}

PACK_DATA_DIRS = {
    "live": DATA_DIR,
    "2026-11-05": EXTRACT_DATA,
}
PACK_STRINGS = {
    "live": STRINGS_PATH,
    "2026-11-05": EXTRACT_STRINGS,
}

USED_KEYS: set[str] = set()
STRINGS: dict = {}

MISSING_TEXT = "字串表沒有內容"


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def official_text(key, default: str = "") -> str:
    if key is None or key == "":
        return default
    USED_KEYS.add(str(key))
    value = STRINGS.get(str(key))
    if value is None:
        return default
    return clean(value)


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


def parse_pipe_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, dict):
        return [(_int(k), _int(v)) for k, v in raw.items()]
    text = raw if isinstance(raw, str) else ",".join(str(x) for x in raw)
    out = []
    for bit in text.split(","):
        parts = [p for p in bit.split("|") if p != ""]
        if len(parts) >= 2:
            out.append((_int(parts[0]), _int(parts[1])))
    return out


def parse_cost(raw) -> list[tuple[int, int, int]]:
    if raw in (None, "", [], -1):
        return []
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                out.append((_int(item[0]), _int(item[1]), _int(item[2])))
            else:
                out.extend(parse_cost(item))
        return out
    out = []
    for bit in str(raw).split(","):
        parts = [p for p in bit.split("|") if p != ""]
        if len(parts) >= 3:
            out.append((_int(parts[0]), _int(parts[1]), _int(parts[2])))
    return out


def _int(value) -> int:
    return int(float(str(value).strip()))


def fmt_int(value) -> str:
    return f"{int(value):,}"


def cost_label(items: list[tuple[int, int, int]], goods: dict[int, "Goods"]) -> str:
    if not items:
        return "無"
    parts = []
    for typ, gid, qty in items:
        name = goods[gid].name if gid in goods and goods[gid].name else f"道具{gid}"
        parts.append(f"{name} ×{fmt_int(qty)}")
    return "、".join(parts)


def raw_cost(items: list[tuple[int, int, int]]) -> str:
    if not items:
        return "無"
    return "、".join(f"{a}|{b}|{c}" for a, b, c in items)


def attr_pair(raw) -> tuple[int, int] | None:
    pairs = parse_pipe_pairs(raw)
    if not pairs:
        return None
    return pairs[0]


def attr_cell(raw) -> str:
    pair = attr_pair(raw)
    if pair is None:
        return "無"
    return fmt_int(pair[1])


def attr_pair_cell(raw_a, raw_b) -> str:
    a = attr_pair(raw_a)
    b = attr_pair(raw_b)
    if a is None and b is None:
        return "無"
    left = fmt_int(a[1]) if a else "無"
    right = fmt_int(b[1]) if b else "無"
    return f"{left}／{right}"


@dataclass
class Goods:
    gid: int
    name: str
    desc: str
    name_key: str
    desc_key: str


@dataclass
class SkillSegment:
    level: int
    key: str
    template: str
    params: list
    filled: str
    leftover: list[tuple[int, object]]


@dataclass
class SkillDef:
    sid: int
    name_key: str | None
    name: str
    maxlv: int
    icon: str | None
    skill_field: object
    named: bool
    name_from: int | None
    segments: list[SkillSegment] = field(default_factory=list)


@dataclass
class Beast:
    bid: int
    name_key: str
    name: str
    typ: int
    faction: str
    season: str
    skin: int
    splinter: int
    quality: int
    show_skill: list[int]
    skill_up: list[str]
    idle: str | None
    star_des: object


@dataclass
class LevelRow:
    bid: int
    level: int
    limit_star: int
    season_1: str
    fightforce: int
    cost: list[tuple[int, int, int]]
    attr_01: object
    attr_02: object
    attr_03: object
    attr_11: object
    attr_12: object
    attr_13: object


@dataclass
class StarRow:
    bid: int
    star: int
    star_sub: int
    conversion_rate: int
    fightforce: int
    leve_add: int
    need_level: int
    city_level: int
    season: object
    season_1: object
    cost: list[tuple[int, int, int]]
    season_cost: list[tuple[int, int, int]]
    skill: str
    skill_level: str
    attr_01: object
    attr_02: object
    attr_03: object
    skill_list_empty: bool


@dataclass
class ReturnRow:
    rid: int
    group: int
    star: int
    star_sub: int
    cost_origin: int
    cost_change: int
    return_num: object
    return_items: list[tuple[int, int, int]]
    return_num_new: object


@dataclass
class Official:
    system_name: str
    short_name: str
    partner_dir: str
    altar_name: str
    altar_des: str
    castle_name: str
    attr_percent: str
    contract_bonus: str
    team_bonus: str
    all_hero_attr: str
    team_hero_attr: str
    level_attr_text: str
    star_text: str
    hero_attr_text: str
    city_show: str
    formula_unslot: str
    formula_slotted: str
    training: str
    formation_limit: str
    preview_title: str
    preview_desc: str
    memo_title: str
    memo_text: str
    gift_name: str
    gift_tips: str
    need_star: str
    level_full: str
    star_full: str
    breakthrough: str
    need_level: str
    leve_add: str
    return_title: str
    return_desc: str
    return_origin: str
    return_now: str
    return_star: str
    return_stat: str
    return_reward: str
    return_rule_title: str
    return_rule_body: str
    return_rule_4: str
    return_mail_title: str
    build_task: str
    factions: dict[int, str]
    goods: dict[int, Goods]
    attr_names: dict[int, str]
    attr_show_type: dict[int, int]


@dataclass
class BuildingInfo:
    levels: list[dict]


@dataclass
class JumpInfo:
    jid: int
    name: object
    desc: object
    go_target: object
    task_guide: object
    city_lv: object
    season: object


@dataclass
class InfluenceInfo:
    other_id: int
    other_name: str
    beast_id: int
    beast_name: str
    type_name: str
    jump: int


@dataclass
class TablesData:
    official: Official
    beasts: list[Beast]
    levels: dict[int, list[LevelRow]]
    stars: dict[int, list[StarRow]]
    returns: list[ReturnRow]
    skills: dict[int, SkillDef]
    building: BuildingInfo
    jump: JumpInfo
    influence: InfluenceInfo
    terms: list[str]
    table_meta: dict
    unnamed_skills: list[int]


def _skill_def(comp: dict, sid: int) -> SkillDef:
    name_key = comp.get("name") or None
    name = official_text(name_key) if name_key else ""
    named = bool(name)
    name_from = None
    if sid in RESONANCE_ALIASES and name_key:
        name_from = RESONANCE_ALIASES[sid]
    segments: list[SkillSegment] = []
    maxlv = _int(comp.get("maxlv") or 0)
    for i in range(1, 6):
        key = comp.get(f"desc{i}")
        params = comp.get(f"desc_parameter{i}") or []
        if not key and not params:
            continue
        template = official_text(key) if key else ""
        filled = fill_skill_segment(template, params)
        segments.append(SkillSegment(
            level=i,
            key=str(key) if key else "",
            template=template,
            params=list(params),
            filled=filled,
            leftover=leftover_params(template, params),
        ))
    return SkillDef(
        sid=sid,
        name_key=str(name_key) if name_key else None,
        name=name,
        maxlv=maxlv,
        icon=comp.get("icon"),
        skill_field=comp.get("skill"),
        named=named,
        name_from=name_from,
        segments=segments,
    )


def _compare_string_packs(keys: set[str]) -> dict:
    packs = {}
    for label, path in PACK_STRINGS.items():
        packs[label] = load_json(path) if path.exists() else {}
    diffs = []
    missing = []
    for key in sorted(keys):
        values = {label: packs[label].get(key) for label in packs}
        present = {label for label, val in values.items() if key in packs[label]}
        if present != set(packs):
            missing.append(key)
        elif len({json.dumps(v, ensure_ascii=False, sort_keys=True) if not isinstance(v, (str, int, float, type(None))) else v for v in values.values()}) > 1:
            diffs.append(key)
    return {"used_keys": len(keys), "value_diffs": diffs, "missing": missing, "packs": {k: len(v) for k, v in packs.items()}}


def _compare_table_packs(names: list[str]) -> dict:
    out = {}
    for name in names:
        paths = {label: (directory / name) for label, directory in PACK_DATA_DIRS.items()}
        info = {"exists": {}, "sha256": {}, "identical": {}, "rows": {}}
        base = None
        for label, path in paths.items():
            info["exists"][label] = path.exists()
            if path.exists():
                info["sha256"][label] = file_sha256(path)
                if base is None and label == "2026-11-05":
                    base = info["sha256"][label]
        for label, digest in info["sha256"].items():
            info["identical"][label] = digest == info["sha256"].get("2026-11-05")
        out[name] = info
    return out


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    global STRINGS
    STRINGS = load_json(EXTRACT_STRINGS)

    raw_beasts = load_extract_table("holybeast.json")
    raw_levels = load_extract_table("holybeast_level.json")
    raw_stars = load_extract_table("holybeast_star.json")
    raw_returns = load_extract_table("holybeast_return.json")
    raw_comp = {c["id"]: c for c in load_extract_table("hero_component.json")}
    raw_attr = {a["id"]: a for a in load_extract_table("attribute.json")}
    raw_func = load_extract_table("function.json")
    raw_lvup = load_extract_table("citybuilding_lvup.json")
    raw_jump = load_extract_table("jump.json")
    raw_inf = load_extract_table("influence_level.json")

    goods: dict[int, Goods] = {}
    for gid in GOODS_IDS:
        nk, dk = f"goods_name_{gid}", f"goods_desc_{gid}"
        goods[gid] = Goods(gid=gid, name=official_text(nk), desc=official_text(dk), name_key=nk, desc_key=dk)
        if not goods[gid].name:
            raise RuntimeError(f"missing official goods name for {gid}")

    attr_ids = set()
    for mapping in TYPE_FACTION_ATTR.values():
        attr_ids.update(mapping.values())
    attr_ids.update((103, 104))
    attr_names = {}
    attr_show = {}
    for aid in sorted(attr_ids):
        row = raw_attr[aid]
        name = official_text(f"attribute_name_{aid}")
        if not name:
            name = official_text(row.get("name") or "")
        attr_names[aid] = name
        attr_show[aid] = _int(row.get("show_type") or 0)

    official = Official(
        system_name=official_text("holybeast_01"),
        short_name=official_text("formation_d6"),
        partner_dir=official_text("influence_level_13"),
        altar_name=official_text("citybuilding_name_178"),
        altar_des=official_text("citybuilding_des_178"),
        castle_name=official_text("citybuilding_name_117"),
        attr_percent=official_text("holybeast_function_attr_percent"),
        contract_bonus=official_text("holybeast_attr_title_01"),
        team_bonus=official_text("holybeast_attr_title_02"),
        all_hero_attr=official_text("holybeast_02"),
        team_hero_attr=official_text("holybeast_06"),
        level_attr_text=official_text("holybeast_leve_attr_text"),
        star_text=official_text("holybeast_star_text"),
        hero_attr_text=official_text("holybeast_hero_attr_text"),
        city_show=official_text("holybeast_city_show"),
        formula_unslot=official_text("holybeast_17"),
        formula_slotted=official_text("holybeast_18"),
        training=official_text("holybeast_19"),
        formation_limit=official_text("holybeast_16"),
        preview_title=official_text("season_preview_title_205"),
        preview_desc=official_text("season_preview_desc_212"),
        memo_title=official_text("season_memo_s2_point1_title"),
        memo_text=official_text("season_memo_s2_point1_text"),
        gift_name=official_text("gift_sale_beast"),
        gift_tips=official_text("gift_sale_beast_max_tips"),
        need_star=official_text("holybeast_leve_limit_star"),
        level_full=official_text("holybeast_07"),
        star_full=official_text("holybeast_08"),
        breakthrough=official_text("holybeast_text_101"),
        need_level=official_text("holybeast_text_102"),
        leve_add=official_text("holybeast_leve_add"),
        return_title=official_text("holybeast_return_des1"),
        return_desc=official_text("holybeast_return_des2"),
        return_origin=official_text("holybeast_return_des9"),
        return_now=official_text("holybeast_return_des10"),
        return_star=official_text("holybeast_return_des3"),
        return_stat=official_text("holybeast_return_des4"),
        return_reward=official_text("holybeast_return_des5"),
        return_rule_title=official_text("holybeast_return_rule1"),
        return_rule_body=official_text("holybeast_return_rule2"),
        return_rule_4=official_text("holybeast_return_rule3"),
        return_mail_title=official_text("holybeast_return_mail_title"),
        build_task=official_text("task_msdc1"),
        factions={1: official_text("goods_desc_292") and "聯盟" or "聯盟", 2: "部族", 3: "自然"},
        goods=goods,
        attr_names=attr_names,
        attr_show_type=attr_show,
    )
    # 聯盟／部族／自然 are official words from beast names and goods strings; copy from those strings.
    official.factions = {
        1: official_text("holybeast_09")[:2],
        2: official_text("holybeast_10")[:2],
        3: official_text("holybeast_11")[:2],
    }
    if official.factions != FACTION_BY_TYPE:
        raise RuntimeError(f"faction prefix mismatch: {official.factions}")

    beasts: list[Beast] = []
    for row in raw_beasts:
        typ = _int(row["holybeast_type"])
        beasts.append(Beast(
            bid=_int(row["id"]),
            name_key=row["holybeast_name"],
            name=official_text(row["holybeast_name"]),
            typ=typ,
            faction=official.factions[typ],
            season=str(row.get("season") or ""),
            skin=_int(row["skin"]),
            splinter=_int(row["splinter"]),
            quality=_int(row["quality"]),
            show_skill=[_int(x) for x in str(row["show_skill"]).split("|") if x],
            skill_up=[str(row[f"skill_up_{i}"]) for i in range(1, 5)],
            idle=row.get("idle"),
            star_des=row.get("holybeast_star_des"),
        ))
    if tuple(b.bid for b in beasts) != EXPECTED_BEAST_IDS:
        raise RuntimeError(f"unexpected beast ids: {[b.bid for b in beasts]}")
    if any(not b.name for b in beasts):
        raise RuntimeError("a holybeast is missing its official name")
    if any(b.quality != 5 for b in beasts):
        raise RuntimeError("quality column is not 5 for every row")
    if has_string("holybeast_quality_5"):
        raise RuntimeError("unexpected holybeast_quality_5 key present")

    skills = {}
    for sid in SKILL_IDS:
        if sid not in raw_comp:
            raise RuntimeError(f"skill {sid} missing from hero_component")
        skills[sid] = _skill_def(raw_comp[sid], sid)
    for sid in UNNAMED_SKILL_IDS:
        if skills[sid].named or skills[sid].name_key or skills[sid].segments:
            raise RuntimeError(f"expected unnamed skill {sid} to have no name or desc")
    for sid, src in RESONANCE_ALIASES.items():
        if skills[sid].name_key != skills[src].name_key:
            raise RuntimeError(f"{sid} name key is not reused from {src}")
        if not skills[sid].named:
            raise RuntimeError(f"{sid} should reuse the official name of {src}")

    levels: dict[int, list[LevelRow]] = defaultdict(list)
    for row in raw_levels:
        levels[_int(row["holy_id"])].append(LevelRow(
            bid=_int(row["holy_id"]),
            level=_int(row["level"]),
            limit_star=_int(row["limit_star"]),
            season_1=str(row.get("season_1") or ""),
            fightforce=_int(row["fightforce"]),
            cost=parse_cost(row.get("cost")),
            attr_01=row.get("attr_01"),
            attr_02=row.get("attr_02"),
            attr_03=row.get("attr_03"),
            attr_11=row.get("attr_11"),
            attr_12=row.get("attr_12"),
            attr_13=row.get("attr_13"),
        ))
    for bid, rows in levels.items():
        rows.sort(key=lambda r: r.level)
    if sum(len(v) for v in levels.values()) != LEVEL_COUNT:
        raise RuntimeError(f"expected {LEVEL_COUNT} level rows")
    if any(len(levels[b.bid]) != LEVELS_PER_BEAST for b in beasts):
        raise RuntimeError("each beast should have 170 level rows")

    # 魔核 appears on 16 levels, not "appears at level 16".
    for b in beasts:
        cores = [r for r in levels[b.bid] if any(item[1] == 295 for item in r.cost)]
        if tuple(r.level for r in cores) != CORE_LEVELS:
            raise RuntimeError(f"core levels mismatch for {b.bid}: {[r.level for r in cores]}")
        got = []
        for r in cores:
            got.append(next(item[2] for item in r.cost if item[1] == 295))
        if tuple(got) != CORE_CORE_COUNTS:
            raise RuntimeError(f"core counts mismatch for {b.bid}: {got}")

    stars: dict[int, list[StarRow]] = defaultdict(list)
    for row in raw_stars:
        skill_list = row.get("SkillList")
        empty_list = isinstance(skill_list, list) and all(item in ({}, None) or item == {} for item in skill_list)
        stars[_int(row["holybeast_id"])].append(StarRow(
            bid=_int(row["holybeast_id"]),
            star=_int(row["star"]),
            star_sub=_int(row["star_sub"]),
            conversion_rate=_int(row["conversion_rate"]),
            fightforce=_int(row["fightforce"]),
            leve_add=_int(row["leve_add"]),
            need_level=_int(row["need_level"]),
            city_level=_int(row["city_level"]),
            season=row.get("season"),
            season_1=row.get("season_1"),
            cost=parse_cost(row.get("cost")),
            season_cost=parse_cost(row.get("season_cost_1")),
            skill=str(row.get("skill") or ""),
            skill_level=str(row.get("skill_level") or ""),
            attr_01=row.get("attr_01"),
            attr_02=row.get("attr_02"),
            attr_03=row.get("attr_03"),
            skill_list_empty=empty_list,
        ))
    for bid, rows in stars.items():
        rows.sort(key=lambda r: (r.star, r.star_sub))
    if sum(len(v) for v in stars.values()) != STAR_COUNT:
        raise RuntimeError(f"expected {STAR_COUNT} star rows")
    for b in beasts:
        rows = stars[b.bid]
        if len(rows) != STARS_PER_BEAST:
            raise RuntimeError(f"{b.bid} star row count {len(rows)}")
        counts = {s: sum(1 for r in rows if r.star == s) for s in range(0, 21)}
        if any(counts[s] != 5 for s in range(0, 20)):
            raise RuntimeError(f"{b.bid} 0-19 star sub counts {counts}")
        if counts[20] != 1:
            raise RuntimeError(f"{b.bid} 20-star should have 1 row")
        special = next(r for r in rows if r.star == 10 and r.star_sub == 1)
        if special.cost != [(2, 160, 10)] or special.need_level != 120:
            raise RuntimeError(f"{b.bid} 10-star 1-sub is not 魔源之石 ×10 at need_level 120")
        if any(r.city_level != -1 for r in rows):
            raise RuntimeError(f"{b.bid} city_level is not all -1")
        if not all(r.skill_list_empty for r in rows):
            raise RuntimeError(f"{b.bid} SkillList is not empty in the 11-05 extract")

    returns = []
    for row in raw_returns:
        returns.append(ReturnRow(
            rid=_int(row["id"]),
            group=_int(row["group"]),
            star=_int(row["star"]),
            star_sub=_int(row["star_sub"]),
            cost_origin=_int(row["cost_origin"]),
            cost_change=_int(row["cost_change"]),
            return_num=row.get("return_num"),
            return_items=parse_cost(row.get("return_num")),
            return_num_new=row.get("return_num_new"),
        ))
    returns.sort(key=lambda r: r.rid)
    if len(returns) != RETURN_COUNT:
        raise RuntimeError(f"expected {RETURN_COUNT} return rows")
    if any(r.group != 1 for r in returns):
        raise RuntimeError("return group is not all 1")
    if (returns[0].star, returns[0].star_sub) != (0, 1) or (returns[-1].star, returns[-1].star_sub) != (10, 0):
        raise RuntimeError("return coverage is not 0-star 1-sub through 10-star 0-sub")

    b_rows = [r for r in raw_lvup if r.get("index") == BUILDING_INDEX]
    b_rows.sort(key=lambda r: _int(r.get("lv")))
    if [r.get("lv") for r in b_rows] != [0, 1]:
        raise RuntimeError(f"building 178 should have levels 0 and 1, got {[r.get('lv') for r in b_rows]}")
    building = BuildingInfo(levels=b_rows)

    jump_row = next(r for r in raw_jump if r.get("id") == 2000039)
    jump = JumpInfo(
        jid=2000039,
        name=jump_row.get("name"),
        desc=jump_row.get("desc"),
        go_target=jump_row.get("go_target"),
        task_guide=jump_row.get("task_guide"),
        city_lv=jump_row.get("city_lv"),
        season=jump_row.get("season"),
    )

    other = next(r for r in raw_inf if r.get("id") == 32000)
    beast_inf = next(r for r in raw_inf if r.get("id") == 32200)
    influence = InfluenceInfo(
        other_id=32000,
        other_name=official_text(other.get("name")),
        beast_id=32200,
        beast_name=official_text(beast_inf.get("name")),
        type_name=str(beast_inf.get("type_name") or ""),
        jump=_int(beast_inf.get("jump")),
    )
    if influence.type_name != "HOLY_BEAST" or influence.jump != 2000039:
        raise RuntimeError("influence 32200 does not point at HOLY_BEAST / 2000039")

    func_hits = []
    for row in raw_func:
        blob = json.dumps(row, ensure_ascii=False).lower()
        if "holybeast" in blob or "holy_beast" in blob or "sacredbeast" in blob:
            func_hits.append(row.get("id"))
    if func_hits:
        raise RuntimeError(f"unexpected function.json holybeast rows: {func_hits}")

    table_names = [
        "holybeast.json", "holybeast_level.json", "holybeast_star.json", "holybeast_return.json",
        "hero_component.json", "attribute.json", "function.json", "citybuilding_lvup.json",
        "jump.json", "influence_level.json",
    ]
    table_meta = {
        "table_cmp": _compare_table_packs(table_names),
        "string_cmp": None,  # filled after terms/keys are known
        "extract": "2026-11-05",
        "goods_json_1105": (EXTRACT_DATA / "goods.json").exists(),
        "function_hits": func_hits,
        "quality_key": has_string("holybeast_quality_5"),
        "jump_empty": jump.name in (None, "") and jump.desc in (None, ""),
        "star_skill_list_empty": True,
        "used_components": 26,
        "live_star_skill_list": None,
    }
    # Compare live star SkillList without using live values on the page.
    live_star_path = DATA_DIR / "holybeast_star.json"
    if live_star_path.exists():
        live_star = load_json(live_star_path)
        empty = 0
        filled = 0
        if isinstance(live_star, list):
            for row in live_star:
                sl = row.get("SkillList")
                if isinstance(sl, list) and all(item in ({}, None) or item == {} for item in sl):
                    empty += 1
                else:
                    filled += 1
        table_meta["live_star_rows"] = len(live_star) if isinstance(live_star, list) else None
        table_meta["live_star_skill_list"] = {"empty": empty, "filled": filled}

    data = TablesData(
        official=official,
        beasts=beasts,
        levels=dict(levels),
        stars=dict(stars),
        returns=returns,
        skills=skills,
        building=building,
        jump=jump,
        influence=influence,
        terms=[],
        table_meta=table_meta,
        unnamed_skills=list(UNNAMED_SKILL_IDS),
    )
    data.terms = _terms(data)
    data.table_meta["string_cmp"] = _compare_string_packs(set(USED_KEYS))
    return data


def star_show_key(typ: int, star: int) -> str:
    return f"holybeast_star_show_{typ}_{star}"


def star_show_text(typ: int, star: int) -> str:
    if star <= 0:
        return ""
    return official_text(star_show_key(typ, star))


def _terms(data: TablesData) -> list[str]:
    o = data.official
    terms: set[str] = {
        o.system_name, o.short_name, o.partner_dir, o.altar_name, o.altar_des,
        o.castle_name, o.attr_percent, o.contract_bonus, o.team_bonus,
        o.all_hero_attr, o.team_hero_attr, o.level_attr_text, o.star_text,
        o.hero_attr_text, o.formation_limit, o.preview_title, o.preview_desc,
        o.memo_title, o.memo_text, o.gift_name, o.gift_tips, o.level_full,
        o.star_full, o.breakthrough, o.leve_add, o.return_title, o.return_desc,
        o.return_origin, o.return_now, o.return_star, o.return_stat, o.return_reward,
        o.return_rule_title, o.return_rule_body, o.return_rule_4, o.return_mail_title,
        o.build_task, o.training, o.formula_unslot, o.formula_slotted,
        "守護魔獸屬性轉化率", "守護魔獸總表", "寵物總表", "英靈總表", "專武總表",
        "裝備總表", "領主裝備總表", "士兵總表", "秘寶總表", "符文總表",
        "聯盟", "部族", "自然", "契約加成", "上陣加成",
        "全英雄屬性提升", "上陣英雄屬性提升", "魔獸祭壇", "魔獸屬性轉化率",
        "魔獸等級上限", "魔獸升星退還", "契約印記", "魔源之石", "魔核",
        "聯盟魔晶", "部族魔晶", "自然魔晶", "魔晶寶箱", "契約魔獸",
        "位階壓制", "聯盟共鳴", "部族共鳴", "自然共鳴",
        "群狼統率", "群狼統帥", "銀月統率",
        "英雄攻擊", "英雄生命", "聯盟英雄攻擊", "聯盟英雄生命",
        "部族英雄攻擊", "部族英雄生命", "自然英雄攻擊", "自然英雄生命",
        "聯盟英雄增傷", "部族英雄增傷", "自然英雄增傷",
        "聯盟英雄減傷", "部族英雄減傷", "自然英雄減傷",
        "聯盟英雄等級上限", "部族英雄等級上限", "自然英雄等級上限",
        "寵物", "英靈", "內城魔獸祭壇",
    }
    for text in (o.formula_unslot, o.formula_slotted, o.training, o.star_text, o.return_rule_body, o.return_desc, o.preview_desc, o.level_attr_text, o.hero_attr_text, o.memo_text, o.city_show, o.need_star, o.need_level):
        terms.add(text)
        for line in (text or "").split("\n"):
            terms.add(line.strip())
            # numbered official lines without the leading "1、"
            stripped = re.sub(r"^\d+[、.]\s*", "", line.strip())
            if stripped:
                terms.add(stripped)
    for g in o.goods.values():
        terms.add(g.name)
        terms.add(g.desc)
    for name in o.attr_names.values():
        terms.add(name)
    for b in data.beasts:
        terms.add(b.name)
        terms.add(b.faction)
        terms.add(o.goods[b.splinter].name)
        terms.add(o.goods[b.splinter].desc)
        for typ in (b.typ,):
            for star in range(1, 21):
                text = star_show_text(typ, star)
                terms.add(text)
                for line in (text or "").split("\n"):
                    terms.add(line.strip())
    for skill in data.skills.values():
        terms.add(skill.name)
        for seg in skill.segments:
            terms.add(seg.template)
            terms.add(seg.filled)
            for line in (seg.filled or "").split("\n"):
                terms.add(line.strip())
    # drop empty and the short 部落 (not used unless an official string has it)
    return sorted({x for x in terms if x}, key=len, reverse=True)


def _limit_star_bands(rows: list[LevelRow]) -> str:
    bands = []
    start = rows[0].level
    prev = rows[0].limit_star
    for row in rows[1:]:
        if row.limit_star != prev:
            bands.append((start, row.level - 1, prev))
            start = row.level
            prev = row.limit_star
    bands.append((start, rows[-1].level, prev))
    parts = []
    for a, b, val in bands:
        if a == b:
            parts.append(f"{a} 級為 {val}")
        else:
            parts.append(f"{a}–{b} 級為 {val}")
    return "，".join(parts)


def _leve_add_bands(rows: list[StarRow]) -> str:
    zero_subs = [r for r in rows if r.star_sub == 0 or r.star == 20]
    bands = []
    start = zero_subs[0].star
    prev = zero_subs[0].leve_add
    for row in zero_subs[1:]:
        if row.leve_add != prev:
            bands.append((start, row.star - 1, prev))
            start = row.star
            prev = row.leve_add
    bands.append((start, zero_subs[-1].star, prev))
    parts = []
    for a, b, val in bands:
        if a == b:
            parts.append(f"{a} 星 {val}")
        else:
            parts.append(f"{a}–{b} 星 {val}")
    return "，".join(parts)


def _skill_name_cell(sid: int, skills: dict[int, SkillDef], terms: list[str]) -> str:
    skill = skills[sid]
    if skill.named:
        return H(skill.name, terms)
    return e("字串表沒有名稱與說明")


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    o = data.official
    beasts = data.beasts
    skills = data.skills

    catalog_rows = []
    for b in beasts:
        skill_names = "、".join(
            skills[sid].name if skills[sid].named else "字串表沒有名稱與說明"
            for sid in b.show_skill
        )
        catalog_rows.append([
            H(b.name, terms),
            H(b.faction, terms),
            H(o.goods[b.splinter].name, terms),
            H(skill_names, terms) if all(skills[sid].named for sid in b.show_skill) else "、".join(
                H(skills[sid].name, terms) if skills[sid].named else e("字串表沒有名稱與說明")
                for sid in b.show_skill
            ),
        ])
    catalog = table(
        ["顯示名", "陣營", "契約道具", "展示技能"],
        catalog_rows,
        mobile="cards",
        card_title="顯示名",
    )

    mat_rows = []
    for gid in (292, 293, 294, 295, 160, 230002, 297):
        g = o.goods[gid]
        use = {
            292: "類型 1 升級主項",
            293: "類型 2 升級主項",
            294: "類型 3 升級主項",
            295: "部分等級的額外消耗（等級突破）",
            160: "10 星 1 子階升星消耗",
            230002: "升星退還發出的材料；升星消耗欄沒有出現這項",
            297: "這四張主表的消耗欄沒有用到",
        }[gid]
        mat_rows.append([H(g.name, terms), H(g.desc, terms), e(use)])
    for b in beasts:
        g = o.goods[b.splinter]
        mat_rows.append([
            H(g.name, terms),
            H(g.desc, terms),
            H(b.name, terms) + "的契約與升星主項",
        ])
    materials = table(
        ["道具", "官方說明", "在本頁的用法"],
        mat_rows,
        mobile="cards",
        card_title="道具",
    )

    sample = data.levels[1001]
    by_lv = {r.level: r for r in sample}
    crystal = o.goods[292].name
    attrs = TYPE_FACTION_ATTR[1]
    level_rows = []
    for lv in KEY_LEVELS:
        r = by_lv[lv]
        level_rows.append([
            str(lv),
            str(r.limit_star),
            H(cost_label(r.cost, o.goods), terms),
            fmt_int(r.fightforce),
            attr_pair_cell(r.attr_01, r.attr_02),
            attr_cell(r.attr_03),
            attr_pair_cell(r.attr_11, r.attr_12),
            attr_cell(r.attr_13),
        ])
    atk1 = H(o.attr_names[attrs["atk1"]], terms)
    hp1 = H(o.attr_names[attrs["hp1"]], terms)
    cap = H(o.attr_names[attrs["cap"]], terms)
    atk2 = H(o.attr_names[attrs["atk2"]], terms)
    hp2 = H(o.attr_names[attrs["hp2"]], terms)
    red = H(o.attr_names[attrs["red"]], terms)
    level_key = table(
        [
            "等級",
            "升星門檻",
            "消耗",
            "戰力",
            f"{atk1}／{hp1}",
            cap,
            f"{atk2}／{hp2}",
            red,
        ],
        level_rows,
        caption=f"以{H(data.beasts[0].name, terms)}為例；其餘五隻只換魔晶與對應陣營屬性，數值相同。{H(crystal, terms)}對應類型 1。屬性只錄原值。",
        mobile="sticky",
    )

    star_sample = data.stars[1001]
    zero = {r.star: r for r in star_sample if r.star_sub == 0}
    dmg_name = H(o.attr_names[3018], terms)
    star_rows = []
    for star in range(0, 21):
        r = zero[star]
        show = star_show_text(1, star)
        show_cell = highlight_lines(show, terms) if show else "無"
        star_rows.append([
            str(star),
            str(r.leve_add),
            str(r.conversion_rate),
            attr_cell(r.attr_01),
            attr_cell(r.attr_02),
            attr_cell(r.attr_03) if star >= 1 else "無",
            "、".join(b for b in str(r.skill_level).split("|") if b != "") or "無",
            fmt_int(r.fightforce),
            H(cost_label(r.cost, o.goods), terms),
            H(cost_label(r.season_cost, o.goods), terms),
            show_cell,
        ])
    star_key = table(
        [
            "星",
            H(o.leve_add, terms),
            H(o.attr_percent, terms),
            H(o.attr_names[103], terms),
            H(o.attr_names[104], terms),
            dmg_name,
            "升星技能等級",
            "戰力",
            "消耗",
            "另一欄消耗",
            "官方星級說明",
        ],
        star_rows,
        caption=(
            f"以{H(data.beasts[0].name, terms)}各星 0 子階為例。"
            "其餘五隻只換契約道具、技能與對應陣營增傷，數字與說明句式相同，只把「"
            + H("聯盟", terms)
            + "」換成「"
            + H("部族", terms)
            + "」或「"
            + H("自然", terms)
            + "」。"
            + H(o.attr_percent, terms)
            + "與增傷屬性都只錄原值；官方說明字串若已有百分比，只照錄字串，不與原值換算對齊。"
        ),
        mobile="sticky",
    )

    skill_level_rows = [
        ["0", "1", "0", "0", "1", "第一段為 1 級；第四段為 1 級；其餘為 0"],
        ["1–6", "1", "0", "0", "2 至 7", "僅第四段每星 +1，6 星到 7"],
        ["7–8", "1", "0", "1 至 2", "7", "第三段在 7 星為 1、8 星為 2"],
        ["9", "1", "1", "2", "7", "第二段在 9 星為 1"],
        ["10–19", "1", "1", "3", "7", "第三段在 10 星為 3"],
        ["20", "1", "2", "3", "7", "第二段在 20 星為 2"],
    ]
    skill_levels = table(
        ["星", "第一段", "第二段", "第三段", "第四段", "變化"],
        skill_level_rows,
        mobile="sticky",
        caption="等級只在整星 0 子階改變。四段對應升星表列出的技能，與主表展示技能不是同一組。各段編號見資料說明。",
    )

    ret_rows = []
    for r in data.returns:
        if r.return_items:
            ret_cell = H(cost_label(r.return_items, o.goods), terms)
        else:
            ret_cell = "無"
        ret_rows.append([
            str(r.star),
            str(r.star_sub),
            fmt_int(r.cost_origin),
            fmt_int(r.cost_change),
            ret_cell,
        ])
    returns = table(
        ["星", "子階", H(o.return_origin, terms), H(o.return_now, terms), H(o.return_reward, terms)],
        ret_rows,
        mobile="sticky",
        caption="50 列全列。兩邊數量相同的列沒有退還道具。",
    )

    return {
        "catalog": catalog,
        "materials": materials,
        "level_key": level_key,
        "star_key": star_key,
        "skill_levels": skill_levels,
        "returns": returns,
    }


def _skill_block(skill: SkillDef, terms: list[str]) -> str:
    if not skill.named:
        body = "字串表沒有名稱與說明，本頁不編造技能名。"
        if skill.skill_field not in (None, "", [], -1):
            body += "組件在，且另有指向欄，但不把它寫成已命名的展示技能。"
        return (
            f"<li><strong>{e('（沒有官方技能名）')}</strong>（最高 {skill.maxlv} 級）"
            f"<p>{e(body)}</p></li>"
        )
    title = H(skill.name, terms)
    parts = [f"<li><p><strong>{title}</strong>（最高 {skill.maxlv} 級）</p>"]
    items = []
    for seg in skill.segments:
        if not seg.filled:
            continue
        if seg.level == 1:
            label = "基礎"
        else:
            label = f"升至 {seg.level} 級追加"
        note = ""
        if seg.level > 2 and skill.segments[1].filled and seg.filled == skill.segments[1].filled and seg.params == skill.segments[1].params:
            note = "（文案與參數與升至 2 級相同）"
        elif seg.level > 1 and skill.segments[seg.level - 2].filled and seg.level - 2 >= 0:
            prev = skill.segments[seg.level - 2]
            if prev.filled == seg.filled and prev.params == seg.params and seg.level > 2:
                note = f"（文案與參數與升至 {prev.level} 級相同）"
        leftover = ""
        if seg.leftover:
            leftover = "（原文有未出現的佔位，參數已按對應位置代入，不自行挪位）"
        text = highlight_lines(seg.filled, terms)
        items.append(f"<li>{e(label)}：{text}{e(note)}{e(leftover)}</li>")
    parts.append("<ul>" + "".join(items) + "</ul></li>")
    return "".join(parts)


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
        extra = f"本頁用到的 {sc['used_keys']} 個字串鍵在 2026-11-05 解壓檔與現行字串檔值相同。"

    same_core = all(tc[n]["identical"].get("live") for n in ("holybeast.json", "holybeast_level.json", "holybeast_return.json"))
    star_same = tc["holybeast_star.json"]["identical"].get("live")
    if same_core and not star_same:
        star_note = (
            "`holybeast.json`、`holybeast_level.json`、`holybeast_return.json` 與現行檔位元組相同。"
            "`holybeast_star.json` 整檔與現行檔不同：兩邊都是 606 筆、欄名相同，"
            "但 2026-11-05 的 `SkillList` 是四個空物件，現行檔同一欄有填入組件內容。"
            "本頁以 2026-11-05 的 `skill`／`skill_level` 字串為準，不用現行檔的 `SkillList`。"
        )
    elif same_core and star_same:
        star_note = "四張 holybeast 主表與現行檔位元組相同。"
    else:
        star_note = "四張 holybeast 主表與現行檔的位元組對照見各檔說明，並非全部相同。"

    comp_same = tc["hero_component.json"]["identical"].get("live")
    if comp_same:
        comp_note = "`hero_component.json` 與現行檔位元組相同。"
    else:
        comp_note = (
            "`hero_component.json` 整檔與現行檔位元組不同；"
            "本頁用到的 26 個技能 id 之 name／desc1–desc5／參數／maxlv 在這兩份裡相同。"
        )

    goods_note = (
        "2026-11-05 解壓檔沒有 `goods.json`；道具名稱與說明取自同一批 `strings_zh.json` 的 `goods_name_*`／`goods_desc_*`。"
        if not data.table_meta["goods_json_1105"] else
        "道具名稱另見 `goods.json`。"
    )

    return (
        f"資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。"
        "來源是 2026-11-05 解壓表與 `strings_zh.json`（歸檔於解壓目錄），不採用其後的 LocalLow 包。"
        f"{star_note}{comp_note}{goods_note}{extra}"
        "屬性名用 `attribute_name_{id}`。"
        "升級、升星用到的 103／104、3018／4018／5018、3019／4019／5019、3103／3104、4103／4104、5103／5104 的 `show_type` 皆為 2，只錄原值，不自行換成百分比。"
        "3003／3004、4003／4004、5003／5004 與 1099／1100／1101 的 `show_type` 為 1，同樣只錄原值。"
        "升星說明若官方已有百分比字串，只照錄字串，不用表上原值去換算或對齊成同一個數字。"
        "`conversion_rate`、`season`／`season_1` 只照錄，不對成 S2／S3，也不把預告或紀念文案當成已推出或標未開放。"
        "主表沒有 `unlocktime`。"
        f"`function.json` 這批沒有守護魔獸專用開啟列。"
        "影響力跳轉 2000039 的 `name`／`desc` 為空，`go_target` 為 29，`task_guide` 為 25，`city_lv` 為 -1，`season` 為空。"
        "建築 178 升級表只有 0、1 兩級，兩級 `cost1` 皆為 `[999, 4, 100]`，`pre_building_level` 皆為 `117|30`，`buildTime` 皆為 3，`fightforce` 為 100／200，`des` 為空。"
        "品質欄皆為 5；這批沒有 `holybeast_quality_5` 這類官方品質顯示名。"
        "升星表 `SkillList` 在這批是四個空物件；技能 id 與等級以 `skill`／`skill_level` 字串為準。"
        "4001 的 `idle` 為 `idle_skill0`，其餘為空。主表 `holybeast_star_des` 皆為空。"
        "2000001 與 2000111／2000211／2000311／2000411／2000511／2000611 在字串表沒有名稱與說明；"
        "2000x11 的組件指向欄指向該魔獸第一個展示技能，`maxlv` 為 7，本頁不把它們寫成已命名技能。"
        "4001／5001／6001 的第三個展示技能（2000403／2000503／2000603）名稱與說明鍵沿用 2000103／2000203／2000303，不是缺名。"
        "本頁範圍只限守護魔獸這套表，不含 `map_monster`／`monster.json` 等野外或 PVE 怪物。"
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜守護魔獸總表"
    lede = (
        f"本頁列出官方界面所稱的「{o.system_name}」：6 隻的名稱、契約與材料、升級與升星規則與關鍵節點、"
        "展示技能原文，以及升星退還規則。"
        "這不是寵物，寵物見已發佈的寵物總表。"
        "野外或 PVE 怪物不在本頁。"
    )
    summary = (
        f"官方界面所稱的{o.system_name}：6 隻名稱、契約與材料、升級與升星規則與關鍵節點、"
        "展示技能原文，以及升星退還規則。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍與解鎖"},
        {"id": "catalog", "label": "名錄"},
        {"id": "materials", "label": "契約與材料"},
        {"id": "upgrade", "label": "升級"},
        {"id": "star", "label": "升星"},
        {"id": "skills", "label": "技能"},
        {"id": "return", "label": "升星退還"},
        {"id": "cost-calc", "label": "養成花費試算"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])
    parts: list[str] = []
    add = parts.append
    add(f'      <p class="lede">{e(lede)}</p>')
    add(f"    {toc}")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        "正文只根據遊戲資料表與官方字串，不評定守護魔獸強弱，也不排行。"
        f"官方界面稱「{H(o.system_name, terms)}」。"
        f"這不是寵物；寵物見已發佈的<a href=\"pets.html\">{H('寵物總表', terms)}</a>。"
        "<a href=\"pals.html\">帕魯</a>、<a href=\"elf-cottage.html\">精靈小屋</a>、<a href=\"fish-tank.html\">摸魚時光</a>（魚缸）、<a href=\"butterfly-catch.html\">抓蝴蝶</a>、<a href=\"ranch-tale.html\">牧場物語</a>不在本頁展開。"
        f"已發佈的<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>是綁在英雄身上的另一套養成，不是守護魔獸。"
        "野外或 PVE 怪物不在本頁。"
    ))
    add("<ul>")
    add("<li><strong>本頁只寫官方所稱的「"
        + H(o.system_name, terms)
        + "」這套養成，共 6 隻。</strong>"
        "下面會列出名稱、契約與材料、升級與升星規則與關鍵節點、展示技能原文，以及升星退還。"
        "升級與升星不整表傾印。對照路徑與筆數見資料說明。</li>")
    add("<li>名稱依遊戲裡看得到的顯示名書寫。沒有官方名稱或技能說明的欄位會註明「字串表沒有內容」或「字串表沒有名稱與說明」，不編造。"
        f"官方用語是「{H(o.system_name, terms)}」「{H('部族', terms)}」；界面亦有簡稱「{H(o.short_name, terms)}」。"
        "官方用字不一致時照錄，不自行改寫。</li>")
    add("<li><strong>不要從時間或賽季欄位、預告或紀念文案自動標未開放，也不把預告當成已推出證明。</strong>"
        "相關欄位與文案只照錄。"
        "升級與升星屬性只錄表上的原值，不自行換成百分比。"
        f"{H(o.attr_percent, terms)}只照錄原值，不自行當百分比改寫。"
        "官方星級說明字串若已有百分比，只照錄字串，不與表上原值換算成同一個數字。</li>")
    add("<li>技能文案以技能表各段說明填入對應參數後照錄。"
        "第一段是基礎效果，其後各段是升階追加，不是另寫一條完整技能。"
        "若文案某個佔位未出現，不自行挪位。"
        "官方技能名與說明用字不一致時，照錄不改。"
        "例如技能名「"
        + H("群狼統率", terms)
        + "」，說明寫「"
        + H("群狼統帥", terms)
        + "」與「"
        + H("銀月統率", terms)
        + "」。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍與解鎖</h2>")
    add(p_html(
        f"官方界面稱「{H(o.system_name, terms)}」。"
        f"影響力目錄在「{H(o.partner_dir, terms)}」底下有「{H(o.short_name, terms)}」一項。"
        "本批沒有守護魔獸專用的功能開啟列；跳轉列的名稱與說明為空，細節見資料說明。"
        "本頁不把這些前置自行寫成唯一開啟條件。"
    ))
    add(p_html(
        f"建築的官方名稱是「{H(o.altar_name, terms)}」，說明：「{H(o.altar_des, terms)}」。"
        f"界面亦寫：「{H(o.hero_attr_text, terms)}」；"
        f"展示確認句「{H(o.city_show, terms)}」。"
        f"升級表只有 0、1 兩級，兩級消耗欄相同，前置欄都指向「{H(o.castle_name, terms)}」30 級。"
        f"任務名稱有「{H(o.build_task, terms)}」。"
        "消耗欄各段含義見資料說明，本頁不自行解釋。"
    ))
    add(p_html(
        f"界面屬性標題有「{H(o.contract_bonus, terms)}」「{H(o.team_bonus, terms)}」，"
        f"另有「{H(o.all_hero_attr, terms)}」「{H(o.team_hero_attr, terms)}」。"
        f"升級相關說明：「{H(o.level_attr_text, terms)}」。"
        "升星說明："
    ))
    add(f"<blockquote>{highlight_lines(o.star_text, terms)}</blockquote>")
    add(p_html(
        "升級表分成兩組屬性欄，本頁不把這些欄位名自行對成某一條界面標題。對照見資料說明。"
    ))
    add(p_html("轉化公式（這是官方說明字串，不是戰鬥傷害公式）："))
    add(f"<blockquote>{highlight_lines(o.formula_unslot, terms)}</blockquote>")
    add(p_html("已上陣時的說明另列出目前上陣英雄攻擊力總值、生命總值，以及轉化率："))
    add(f"<blockquote>{highlight_lines(o.formula_slotted, terms)}</blockquote>")
    add(p_html("養成說明："))
    add(f"<blockquote>{highlight_lines(o.training, terms)}</blockquote>")
    add(p_html(
        f"編隊限制：「{H(o.formation_limit, terms)}」"
        "另有改名與領地展示相關提示，本頁不展開操作流程。"
    ))
    add(p_html(
        f"預告標題「{H(o.preview_title, terms)}」，說明「{H(o.preview_desc, terms)}」。"
        f"紀念標題有「{H(o.memo_title, terms)}」，對應說明「{H(o.memo_text, terms)}」。"
        "預告與紀念文案照錄，不是評級，也不是已推出證明。"
    ))
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>名錄</h2>")
    add(p_html(
        "主表 6 筆全部入冊，品質欄皆為 5；這批字串沒有對應的官方品質顯示名。"
        "名稱都能對上字串。"
        f"類型為 1／2／3 的三隻，官方名稱前綴分別是{H('聯盟', terms)}／{H('部族', terms)}／{H('自然', terms)}。"
        "前三隻與後三隻的系統欄原值不同，只照錄，不對成賽季編號。原值見資料說明。"
        "六隻的展示技能升階節點相同。"
    ))
    add(tbl["catalog"])
    add(p_html(
        "後三隻的第三個展示技能並非缺名：名稱與說明沿用前三隻對應陣營的「"
        + H("聯盟共鳴", terms) + "」、「"
        + H("部族共鳴", terms) + "」、「"
        + H("自然共鳴", terms) + "」。"
        + H("位階壓制", terms)
        + "六隻共用。"
    ))
    add(p_html(
        "升星表另列一組技能，與主表展示技能不完全相同。"
        "其中兩類在字串表沒有名稱與說明；組件在，但不把它們改寫成展示技能名。"
        "編號與細節見資料說明與技能節。"
    ))
    add("    </section>")

    add('    <section id="materials">')
    add("      <h2>契約與材料</h2>")
    add(p_html(
        "消耗欄在資料表寫成三段數字，與其他圖鑑相同，本頁改以官方道具名與數量顯示；原始欄位見資料說明，不另解釋第一段的枚舉定義。"
        "升級主項依類型："
        f"類型 1 用「{H(o.goods[292].name, terms)}」，"
        f"類型 2 用「{H(o.goods[293].name, terms)}」，"
        f"類型 3 用「{H(o.goods[294].name, terms)}」。"
        f"說明皆照錄。部分等級另加「{H(o.goods[295].name, terms)}」，"
        f"說明：「{H(o.goods[295].desc, terms)}」。"
    ))
    add(p_html(
        "升星主項為該魔獸的契約道具，官方名稱與說明如下表。"
        f"10 星 1 子階六隻都改消耗「{H(o.goods[160].name, terms)}」10 個，"
        f"說明：「{H(o.goods[160].desc, terms)}」。"
        f"退還表發出「{H(o.goods[230002].name, terms)}」，"
        f"說明：「{H(o.goods[230002].desc, terms)}」。"
        "升星消耗欄沒有出現這項。"
    ))
    add(p_html(
        f"另有道具「{H(o.goods[297].name, terms)}」，"
        f"說明：「{H(o.goods[297].desc, terms)}」。"
        "這四張主表的消耗欄沒有用到它，本頁不把它寫成升級材料表的一列。"
    ))
    add(tbl["materials"])
    add(p_html(
        f"禮包相關名稱有「{H(o.gift_name, terms)}」與「{H(o.gift_tips, terms)}」，只照錄名稱，不做儲值或購買建議。"
    ))
    add("    </section>")

    add('    <section id="upgrade">')
    add("      <h2>升級</h2>")
    add(p_html(
        "六隻都是 1–170 級，每隻 170 列，共 1,020 筆。把陣營對應的屬性與魔晶對齊後，"
        "六隻的等級、升星門檻、戰力、消耗數量與屬性原值全部相同。"
        "另有一欄只照錄原值，不對成賽季編號，見資料說明。"
        "本頁不整表傾印，只寫規則與關鍵節點。"
    ))
    add(p_html(
        "升星門檻隨等級提高："
        + e(_limit_star_bands(data.levels[1001]))
        + "。"
        "表上沒有門檻 4，也沒有 6–10。"
        f"界面字串有「{H(o.need_star, terms)}」、「{H(o.level_full, terms)}」。"
        "這組門檻與升星表的魔獸等級上限、官方星級說明裡的「魔獸等級提升至○○」並列照錄，不自行合併成一條升級公式。"
    ))
    add(p_html(
        f"「{H(o.goods[292].name, terms)}」數量 1 級 240、2 級 480，其後遞增；170 級為 194,880。"
        f"「{H(o.goods[295].name, terms)}」出現在 20、30 直到 170 級，共 16 級（20、30、40、50、60、70、80、90、100、110、120、130、140、150、160、170），不是只在其中某一級。"
        "數量依序為 1,500、3,100、3,700、4,300、4,900、5,500、6,200、6,800、7,400、8,000、8,600，自 130 級起為 9,000。"
        "其餘等級只有魔晶。"
        f"界面另有「{H(o.breakthrough, terms)}」；"
        f"「{H(o.goods[295].name, terms)}」說明寫的是「等級突破」，"
        f"與升星 10 星 1 子階改消耗「{H(o.goods[160].name, terms)}」不是同一列。"
    ))
    add(p_html(
        "升級屬性六隻結構相同，只換陣營屬性："
        f"第一組是該營「{H(o.attr_names[3003], terms)}」「{H(o.attr_names[3004], terms)}」（只錄原值），"
        "1 級 75／225，其後每級攻擊 +75、生命 +225，至 120 級 9,000／27,000；"
        "121 級起改為每級 +80／+240，170 級 13,000／39,000。"
        f"第三項自 20 級出現，為該營「{H(o.attr_names[1099], terms)}」。"
        "20–39 級為 1，40–59 級為 2，60–79 級為 3，80–99 級為 4，100–120 級為 5，"
        "121–129 級為 6，130–139 級為 7，140–149 級為 8，150–159 級為 9，160–170 級為 10。"
        f"另一組同樣是該營「{H(o.attr_names[3103], terms)}」「{H(o.attr_names[3104], terms)}」，但只錄原值、不換成百分比："
        "1 級 150／450，至 120 級 18,000／54,000（每級 +150／+450）；"
        "121 級起每級 +100／+300，170 級 23,000／69,000。"
        f"減傷項自 10 級出現，為該營「{H(o.attr_names[3019], terms)}」，只錄原值："
        "10–29 級 300，30–49 級 400，50–69 級 550，70–89 級 700，90–109 級 900，110–129 級 1,100，130–149 級 1,300，150–170 級 1,500。"
    ))
    add(p_html(
        "表上戰力：1 級 5,570，10 級 61,260，20 級 183,700，60 級 1,285,920，120 級 4,793,130，170 級 7,189,630。"
        "這是表欄原值，不是戰鬥結算。"
    ))
    add(tbl["level_key"])
    add("    </section>")

    add('    <section id="star">')
    add("      <h2>升星</h2>")
    add(p_html(
        "每隻 101 列，星級 0–20，共 606 筆。0–19 星各有 5 個子階，20 星只有 1 列。"
        "遊戲中文名稱表另有 21 至 30 星的說明，升星表仍只到 20 星，不把那些說明寫成已開放星階。"
        "把契約道具、技能與增傷屬性按陣營對齊後，六隻的星、子階、轉化率、戰力、魔獸等級上限、技能等級、"
        "需求等級、消耗數量與屬性原值全部相同。"
        "其餘欄位原值見資料說明，只照錄，不對成賽季編號。"
    ))
    add(p_html(
        f"{H(o.leve_add, terms)}："
        + e(_leve_add_bands(data.stars[1001]))
        + "。"
        "同一星的子階這項相同。"
        "官方星級說明字串在 1、2、3、5、11–15 星另寫「魔獸等級提升至○○」，數字與該星這項相同；"
        "4、6–10、16–20 星的說明字串沒有這句。"
    ))
    add(p_html(
        f"{H(o.attr_percent, terms)}在 0 星 0 子階為 10000，其後每個子階 +150，"
        "至 10 星 0 子階為 17500，10 星 1 子階起至 20 星維持 17500。原值照錄，不自行當百分比。"
    ))
    add(p_html(
        "有一組時間欄在 10 星 0 子階與 10 星 1 子階之間改值，只照錄原值，不對成賽季編號，見資料說明。"
        "需求等級全表只有 10 星 1 子階為 120，其餘為 -1。"
        f"這一列六隻的消耗都是「{H(o.goods[160].name, terms)}」10 個，兩邊消耗欄相同，戰力仍為 4,219,740（與 10 星 0 子階相同）。"
        f"界面有「{H(o.breakthrough, terms)}」與「{H(o.need_level, terms)}」。"
        "10 星 2 子階起消耗回到各自的契約道具，且兩邊消耗數量相同。"
    ))
    add(p_html(
        f"升星屬性為「{H(o.attr_names[103], terms)}」「{H(o.attr_names[104], terms)}」與對應陣營增傷，只錄原值："
        "攻擊／生命 0 星 0 子階為 180／540，0 星 1 子階至 9 星 4 子階每個子階 +180／+540，"
        "9 星 4 子階與 10 星 0 子階同為 9,000／27,000；"
        "10 星 1 子階至 15 星 0 子階每個子階 +90／+270（15 星 0 子階 11,250／33,750）；"
        "15 星 1 子階至 20 星每個子階 +45／+135，20 星為 12,375／37,125。生命全表都是攻擊的三倍。"
        "對應陣營的英雄增傷自 1 星 0 子階出現：1 星 300，其後每增加 1 星 +80，至 10 星 1020；"
        "11 星起每星 +40，20 星 1420。同一星的子階之間這項不變。"
        "官方說明字串寫的百分比是字串原文，與表上原值並列，不互相換算。"
    ))
    add(tbl["star_key"])
    add(p_html(
        "0–9 星各子階的契約數量：同一星內，0 子階用較小值，1–4 子階用同一個較大值"
        "（0 星例外，五個子階分別為 1、6、8、12、16）。"
        "1 星 1–4 子階消耗皆為 48；2 星 0 子階仍為 48，1–4 子階為 72；其後依此遞增，"
        "至 9 星 0 子階 240、1–4 子階 336，10 星 0 子階 336。"
        f"10 星 1 子階改為「{H(o.goods[160].name, terms)}」10 個。"
        "10 星 2 子階起至 20 星，兩邊消耗數量相同，為 72、74、76（10 星 2–4 子階），"
        "11 星 78、80、82、84、86，其後逐子階遞增，20 星為 346。"
    ))
    add(p_html(
        "升星表的技能等級只在整星 0 子階改變，同一星的 1–4 子階維持不變。"
        "以第一隻為例，四段對應升星表列出的技能（含沒有官方名的技能），編號見資料說明："
    ))
    add(tbl["skill_levels"])
    add(p_html(
        "主表寫的是展示技能的星級節點，與上表不是同一組技能，本頁分開照錄，不自行對成同一條升級軌。"
        "各節點原值見資料說明。"
        "升星表另有一項沒有官方名稱的技能，全表都是 1 級。"
        f"界面另有「{H(o.star_full, terms)}」。"
    ))
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>技能</h2>")
    add(p_html(
        "展示技能的解鎖與升階節點見主表。"
        "下列每隻先列展示技能名與上限，再寫基礎與後續升階追加。參數已代入。"
        f"共用的「{H('位階壓制', terms)}」只在本節開頭寫一次。"
        "沒有官方名稱的升星技能在此註明，不編造名稱，也不把它寫成該魔獸第一個展示技能。"
    ))
    shared = data.skills[2000002]
    add(f"      <h3 id=\"skill-shared\">{H(shared.name, terms)}（六隻共用）</h3>")
    add("<ul>" + _skill_block(shared, terms) + "</ul>")

    for b in data.beasts:
        add(f'      <h3 id="skill-{b.bid}">{H(b.name, terms)}</h3>')
        add(p_html("展示技能：" + "、".join(
            (H(data.skills[sid].name, terms) if data.skills[sid].named else e("字串表沒有名稱與說明"))
            for sid in b.show_skill
        ) + "。"))
        items = []
        for sid in b.show_skill:
            if sid == 2000002:
                items.append(f"<li>{H(shared.name, terms)}：見上節。</li>")
            else:
                items.append(_skill_block(data.skills[sid], terms))
        add("<ul>" + "".join(items) + "</ul>")
        # mark unnamed companion id
        unnamed = 2000000 + (b.bid // 1000) * 100 + 11
        if unnamed in data.skills:
            add(p_html(
                "升星表另有一項：字串表沒有名稱與說明；組件在，且指向該魔獸第一個展示技能，"
                f"最高 {data.skills[unnamed].maxlv} 級。本頁不把它寫成「"
                + (H(data.skills[b.show_skill[0]].name, terms) if data.skills[b.show_skill[0]].named else "")
                + "」。編號見資料說明。"
            ))
    add(p_html("另外，升星表六隻皆另有一項：字串表沒有名稱與說明，全表都是 1 級。本頁不編造技能名。編號見資料說明。"))
    add("    </section>")

    add('    <section id="return">')
    add("      <h2>升星退還</h2>")
    add(p_html(
        "退還表 50 筆，分組皆為 1，覆蓋 0 星 1 子階至 10 星 0 子階；沒有 0 星 0 子階，也沒有 10 星 1 子階以後的列。這批沒有第二組。"
    ))
    add(p_html(
        f"官方活動文案標題為「{H(o.return_title, terms)}」，"
        f"說明「{H(o.return_desc, terms)}」。"
        f"界面還有「{H(o.return_origin, terms)}」「{H(o.return_now, terms)}」、"
        f"「{H(o.return_star, terms)}」「{H(o.return_stat, terms)}」「{H(o.return_reward, terms)}」。"
        f"{H(o.return_rule_title, terms)}："
    ))
    add(f"<blockquote>{highlight_lines(o.return_rule_body + chr(10) + o.return_rule_4, terms)}</blockquote>")
    add(p_html(
        "這是活動規則，不是日常升星消耗表。"
        f"郵件標題「{H(o.return_mail_title, terms)}」。"
        "文案本身沒有寫時區或具體開啟時刻，本頁不加。"
    ))
    add(p_html(
        "50 列與升星表 0 星 1 子階至 10 星 0 子階逐列對得上：原消耗等於該列升星消耗數量，現消耗等於該列另一個消耗欄數量。"
        "兩邊數量相同時（0 星 1–2 子階），沒有退還道具；自 0 星 3 子階起，退還「"
        + H(o.goods[230002].name, terms)
        + "」。"
        "5 星 0 子階兩邊數量同為 120，退還數量仍維持前一列的 346，不是清零。"
        "10 星 0 子階退還 1,446。"
        "10 星 1 子階起升星表兩邊消耗已相同，退還表不再列表。"
    ))
    add(tbl["returns"])
    add("    </section>")

    add(render_holybeast_cost_calculator(data))

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add("<li>寵物（見已發佈的<a href=\"pets.html\">"
        + H("寵物總表", terms)
        + "</a>）、英靈（見已發佈的<a href=\"valhalla.html\">"
        + H("英靈總表", terms)
        + "</a>），以及<a href=\"pals.html\">帕魯</a>、<a href=\"elf-cottage.html\">精靈小屋</a>、<a href=\"fish-tank.html\">摸魚時光</a>（魚缸）、<a href=\"butterfly-catch.html\">抓蝴蝶</a>、<a href=\"ranch-tale.html\">牧場物語</a>等其他伴侶與休閒系統；野外或 PVE 怪物。</li>")
    add("<li>升級 1,020 筆、升星 606 筆的逐列全表（規則與關鍵節點已寫；退還 50 筆已全列）。</li>")
    add("<li>功能開啟表沒有守護魔獸專用開啟列；影響力跳轉的名稱與說明為空。建築消耗欄各段的枚舉定義。</li>")
    add("<li>升星表裡沒有官方名稱的技能在客戶端如何與展示技能合併顯示。</li>")
    add("<li>時間欄與賽季日曆的對應（不標未開放）；預告、紀念與禮包的推出時程。</li>")
    add(f"<li>「{H(o.goods[297].name, terms)}」的實際開出內容，以及契約、魔晶、魔核、魔源之石、契約印記在活動或商店中的取得表。</li>")
    add("<li>與英雄技能、站位的搭配模擬，以及轉化公式代入面板後的戰鬥結算。</li>")
    add("<li>品質 5 的專用顯示名（本批沒有這類顯示名）。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(_data_notes(data)))
    add(p_html(
        "以下補錄正文改寫後移入的欄位名與原值，只照錄，不對成賽季號，"
        "也不把 holybeast 與 holybeast_2、或 season／season_1 的 2／2|0 與 5／5|7，對成臨時擁有／臨時使用，"
        "也不把 season_effect 與 season_effect2 那樣對應。"
        "主表前三隻（1001、2001、3001）的 season 欄為 <code>holybeast</code>，"
        "後三隻（4001、5001、6001）為 <code>holybeast_2</code>。"
        "升級表 season_1 在 1–120 級為 <code>2|0</code>，121–170 級為 <code>5|7</code>。"
        "升星表 season／season_1 在 0 星 0 子階至 10 星 0 子階為 2／<code>2|0</code>（306 筆）；"
        "自 10 星 1 子階起改為 5／<code>5|7</code>（300 筆）。"
        "升星表城堡等級欄全表為 -1。"
        "season_cost_1 是升星表另一欄消耗，正文已用官方道具名列出。"
    ))
    add(p_html(
        "升星表 skill_level 原值（只在整星 0 子階改變）："
        "0 星 <code>1|0|0|1</code>；1–6 星 <code>1|0|0|2</code> 至 <code>1|0|0|7</code>；"
        "7 星 <code>1|0|1|7</code>、8 星 <code>1|0|2|7</code>；9 星 <code>1|1|2|7</code>；"
        "10–19 星 <code>1|1|3|7</code>；20 星 <code>1|2|3|7</code>。"
        "以第一隻為例，四段對應 2000001、位階壓制（2000002）、該營共鳴，以及沒有官方名的 2000x11。"
        "主表展示技能的星級節點為 <code>0|1|3|5</code>、<code>2|4|6</code>、<code>7|8|10</code>、<code>9|20</code>，"
        "與升星表 skill ／ skill_level 不是同一組 id。"
        "2000001 全表都是 1 級，字串表沒有技能名。"
        "各魔獸升星表另有 2000111／2000211／2000311／2000411／2000511／2000611，"
        "字串表沒有名稱與說明；組件指向欄指向該魔獸第一個展示技能，maxlv 為 7。"
        "4001／5001／6001 的第三個展示技能（2000403／2000503／2000603）名稱與說明鍵沿用 2000103／2000203／2000303，不是缺名。"
        "共用技能 2000002 為「位階壓制」。"
        "退還表有 id 欄；return_num_new 的數字與退還獎勵數量相同，正文只列官方退還獎勵。"
    ))
    add("<ul>")
    add("<li>定義在 <code>holybeast.json</code>（6 筆），升級在 <code>holybeast_level.json</code>（1,020 筆，每隻 1–170 級），"
        "升星在 <code>holybeast_star.json</code>（606 筆，每隻 101 列），退還在 <code>holybeast_return.json</code>（50 筆）。"
        "字串表另有 <code>holybeast_star_show_1_21</code> 至 <code>holybeast_star_show_3_30</code> 共 30 鍵，升星表仍只到 20 星，不把那些鍵寫成已開放星階。"
        "展示技能與升星表列出的技能 id 全部能在 <code>hero_component.json</code> 對上（26 個 id）。"
        "名稱來自主表名稱鍵。消耗欄原始寫法是 <code>2|道具id|數量</code>。</li>")
    add("<li>升級屬性 <code>attr_01</code>–<code>attr_03</code> 匯總為 <code>AttrAllList</code>，"
        "<code>attr_11</code>–<code>attr_13</code> 匯總為 <code>AttrTeamList</code>；"
        "升星屬性在 <code>attr_01</code>–<code>attr_03</code>（匯總為 <code>AttrTeamList</code>）。"
        "本頁不把這些欄位名自行對成「契約加成」或「上陣加成」。</li>")
    add("<li>待補：2000001 與 2000x11 在客戶端的顯示；展示技能升階節點與升星表技能等級在界面上如何對應；"
        "建築消耗欄各段含義；上述兩組屬性欄與界面標題的對應；season／season_1 與賽季日曆。</li>")
    add("<li>養成花費試算的升級加總，是目前等級之後到目標等級（含）的官方列；升星同樣從目前之後加到目標（含）。"
        "六隻只換魔晶與契約道具，數量共用。表上另一欄消耗只照錄，不對成賽季編號或臨時擁有／臨時使用。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    from .upgrade_costs import attach_upgrade_cost_scripts
    return attach_upgrade_cost_scripts(html, "holybeast-upgrade-costs-data.js", "upgrade-cost.js")


def render_holybeast_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def build_holybeast_upgrade_cost_payload(data: TablesData) -> dict:
    o = data.official
    beasts = []
    for b in data.beasts:
        crystal_id = TYPE_CRYSTAL[b.typ]
        beasts.append({
            "name": b.name,
            "crystal": o.goods[crystal_id].name,
            "contract": o.goods[b.splinter].name,
        })
    base = data.beasts[0]
    level_rows = data.levels[base.bid]
    crystal = []
    core = {}
    for r in level_rows:
        c_qty = 0
        for typ, gid, qty in r.cost:
            if gid == 295:
                core[str(r.level)] = int(qty)
            else:
                c_qty += int(qty)
        crystal.append(c_qty)
    stars = []
    for r in data.stars[base.bid]:
        stone = 0
        contract = 0
        other = 0
        for typ, gid, qty in r.cost:
            if gid == 160:
                stone += int(qty)
            else:
                contract += int(qty)
        for typ, gid, qty in r.season_cost:
            other += int(qty)
        row = {"star": r.star, "sub": r.star_sub, "contract": contract, "other": other}
        if stone:
            row["stone"] = stone
        stars.append(row)
    return {
        "kind": "holybeast",
        "beasts": beasts,
        "coreName": o.goods[295].name,
        "stoneName": o.goods[160].name,
        "levels": {"min": 1, "max": 170, "crystal": crystal, "core": core},
        "stars": stars,
    }


def write_holybeast_upgrade_cost_data(path: Path, data: TablesData | None = None) -> None:
    from .upgrade_costs import write_data_js

    payload = build_holybeast_upgrade_cost_payload(data or load_tables_data())
    write_data_js(path, "TH_HOLYBEAST_UPGRADE_COST", payload)


def render_holybeast_cost_calculator(data: TablesData) -> str:
    o = data.official
    core = o.goods[295].name
    stone = o.goods[160].name
    return "\n".join([
        '    <section id="cost-calc">',
        "      <h2>養成花費試算</h2>",
        "<p>六隻守護魔獸的升級數量相同，只是魔晶與契約道具依陣營、魔獸而異。"
        "選一隻，再選升級或升星，可以加總官方表上已有的消耗。只加總表上原值，不計算折扣，也不補沒有官方列的消耗。</p>",
        "<p>升級表列的是到達該級的消耗。從目前等級升到目標等級，加總目前之後到目標（含）的各列；尚未升級請把目前等級填 0。"
        f"「{e(core)}」出現在 20、30 直到 170 級，共 16 級，不是只在其中某一級。</p>",
        "<p>升星表列的是到達該星、該子階的消耗。從目前之後加總到目標（含）。"
        f"10 星 1 子階改消耗「{e(stone)}」。"
        "表上另有一欄消耗時，只照錄原值，作為第二欄官方消耗，不對成賽季編號。</p>",
        "<p>沒有使用指令時，上面的總表與規則仍可閱讀；試算需要瀏覽器執行本頁指令。</p>",
        '<form class="upgrade-cost" data-upgrade-cost data-upgrade-source="TH_HOLYBEAST_UPGRADE_COST" action="#" method="get">',
        "<noscript><p>目前沒有執行指令，無法在這一欄加總。請改看上方的升級與升星規則，或開啟指令後再試。</p></noscript>",
        "<fieldset>",
        "<legend>守護魔獸升級與升星</legend>",
        '<div class="upgrade-cost-grid">',
        '<div><label for="uc-beast-item">守護魔獸</label>',
        '<select id="uc-beast-item" data-uc-beast></select></div>',
        '<div><label for="uc-beast-mode">要加總的項目</label>',
        '<select id="uc-beast-mode" data-uc-mode>',
        '<option value="level">升級</option>',
        '<option value="star">升星</option>',
        "</select></div>",
        '<div data-uc-level-fields>',
        '<label for="uc-beast-from-lv">目前等級</label>',
        '<input id="uc-beast-from-lv" data-uc-from-lv type="number" inputmode="numeric">',
        "</div>",
        '<div data-uc-level-fields>',
        '<label for="uc-beast-to-lv">目標等級</label>',
        '<input id="uc-beast-to-lv" data-uc-to-lv type="number" inputmode="numeric">',
        "</div>",
        '<div data-uc-star-fields hidden>',
        '<label for="uc-beast-from-star">目前星級</label>',
        '<select id="uc-beast-from-star" data-uc-from-star></select>',
        "</div>",
        '<div data-uc-star-fields hidden>',
        '<label for="uc-beast-to-star">目標星級</label>',
        '<select id="uc-beast-to-star" data-uc-to-star></select>',
        "</div>",
        "</div>",
        '<div class="upgrade-cost-actions"><button type="submit" data-uc-run>加總</button></div>',
        '<div class="upgrade-cost-result" data-uc-result hidden aria-live="polite"></div>',
        "</fieldset>",
        "</form>",
        "    </section>",
    ])
