"""Compile the published 帕魯 catalog tables from the 2026-11-22 LocalLow extract."""

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

# 本頁截止為 2026-11-22：升星／光環只出現在當日 LocalLow。不改 paths.DATA_CUTOFF。
EXTRACT_DIR = TOPHEROES_ROOT / "extracts/2026-11-22-locallow"
EXTRACT_DATA = EXTRACT_DIR / "data"
EXTRACT_STRINGS = EXTRACT_DIR / "strings_zh.json"

PAGE_CUTOFF = "2026-11-22"

PAL_COUNT = 55
STAR_COUNT = 330
STARS_PER_PAL = 6
SKILL_COUNT = 155
TAG_COUNT = 9
TEAM_COUNT = 3
TEAMPOS_COUNT = 18
FUSE_COUNT = 4
AURA_COUNT = 15
ROLL_COUNT = 30
CAMP_LEVELS = 41  # 0–40
BUILDING_INDEX = 183
CASTLE_INDEX = 117
FUNCTION_ID = 83
JUMP_ID = 2000067
INFLUENCE_PARENT = 32000
INFLUENCE_PAL = 32100
CATCH_ACTIVITY_IDS = (5002001, 5002002)
ARENA_ACTIVITY_IDS = (5001022, 5001025, 5001026, 5001027, 5001032)
ATTR_SHOW = {
    3: 1, 4: 1,
    62: 2, 63: 2, 1249: 2,
    103: 2, 104: 2,
    3003: 1, 3004: 1, 4003: 1, 4004: 1, 5003: 1, 5004: 1,
}
GOODS_CORE = (519, 522, 163001, 163002, 163003, 163004, 163005, 163006, 163007, 163008, 163101)
GOODS_TOKEN_MAIN = tuple(range(80001, 80056))
GOODS_TOKEN_EXTRA = tuple(range(80056, 80076))

TABLE_SHA256 = {
    "pal.json": "e974b347957ce4625ff07fdc763fd09d812bcbcc58cbcd9327be1aef326e1170",
    "pal_tag.json": "1c5add0020e0578bd07e303ef501e3ce05ca2d35c1c34372d7f31f4f4ce43f9f",
    "pal_team.json": "270542bd6fe08a1fa6d7a9aed1081d35c2b4cbf324d43c1819a1ea1b064d9342",
    "pal_teampos.json": "900d3ac13ddc788e5d47810bde7fa6aba0d5daa3dc0f70f82e8bf3430fa0705e",
    "pal_fuse.json": "9fbb0b63084edc7ebb1c7549ba4f4323f7ea5d23252fb0c981910a65946ccea9",
    "pal_catch_param.json": "a863fc3d3e448e6c01c3ec59db07cb2689f6ade8b837ba5ba1951ada9ab5f16b",
    "pal_roll_weight.json": "fc3cc2e05ed4c7b9ce7aa3fc4abaa3e160d378e74f786aac302491cdff2d3a87",
    "pal_star.json": "332b713e8c8bb85a8f08ec2626b21d984ac173c35ff446512ca3a67bc74965e4",
    "pal_aura.json": "dcbb1c4967fa2f134cf80a363144c0f897e5144098fdc9f25e68826955e19818",
    "hero_component.json": "c8530f16b07bbea7f9084c74826b9c8a35486186c8af87bc258373f3ef1118e8",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "function.json": "fb826efa087a122ad37682d1707bf877ce56970d92fbc44127ca390e72309afc",
    "citybuilding.json": "25dc79829dcc0888168e76fe7f2bd5cb9d4dc97df6cecdc98b6e01cb24c24a0f",
    "citybuilding_lvup.json": "2d85b94154e3a0f6f481805d49bace3e8ee8eccd84dfae79ac938743e75724d3",
    "citybuilding_lvup_new.json": "436ca7dcdba0f5aa962cfbbb728fd4b9d9ac3a3042154a2ec3e5c43a60158abf",
    "jump.json": "05169023beeba039e94014a8f45024004faee856a85c5bafd47420fbd72ec7d6",
    "influence_level.json": "1fb4eed1f01870b8147d400fcc07554934bdbbf8d97f972b9712a4b9df6924dc",
    "activity.json": "6e0fd9ff6bd81e71bfee29a3794d10b2ba8eff0601f288f56d8881547536602d",
    "goods.json": "3602b35aa5fcae2676cca2c85631d36b5a26299b01b8a245993bf10151c3cfc4",
}

STRINGS_SHA256 = "249e08f64922de78527d6669912e4202fd650d1bd2434e47c89351d123da0134"

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

USED_KEYS: set[str] = set()
STRINGS: dict = {}

MISSING_TEXT = "字串表沒有內容"
MISSING_NAME_DESC = "字串表沒有名稱與說明"


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


def _int(value) -> int:
    return int(float(str(value).strip()))


def fmt_int(value) -> str:
    return f"{int(value):,}"


def raw_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def cost_cell(raw) -> str:
    if raw in (None, "", [], -1):
        return "無"
    return f"<code>{e(raw_json(raw))}</code>"


def unwrap_pipe(raw):
    """Return the pipe-string stored in a one-element list, or a plain string."""
    if raw in (None, "", [], -1):
        return None
    if isinstance(raw, list):
        if len(raw) == 1 and isinstance(raw[0], str):
            return raw[0]
        return None
    return str(raw)



def fmt_unknown_cost(raw) -> str:
    if raw in (None, "", [], -1):
        return "無"
    if isinstance(raw, list) and len(raw) >= 3 and _int(raw[0]) == 999:
        return f"類型 999、第 {e(str(raw[1]))} 段、數量 {fmt_int(raw[2])}"
    return "沒有官方資源名，原值見資料說明"


def fmt_costs_visible(*raws) -> str:
    parts = [fmt_unknown_cost(r) for r in raws]
    parts = [p for p in parts if p != "無"]
    return "、".join(parts) if parts else "無"


def fmt_pre_visible(raw, castle_name: str, terms: list[str]) -> str:
    text = raw if isinstance(raw, str) else unwrap_pipe(raw)
    if not text:
        return "無"
    parts = str(text).split("|")
    if len(parts) == 2 and parts[0] == str(CASTLE_INDEX):
        return f"{H(castle_name, terms)} {e(parts[1])} 級"
    return "前置原值見資料說明"


def fmt_skill_levels_visible(raw) -> str:
    bits = [b for b in str(raw).split("|") if b != ""]
    return "、".join(bits) if bits else "無"


@dataclass
class Goods:
    gid: int
    name: str
    desc: str
    name_key: str
    desc_key: str
    name_missing: bool
    desc_missing: bool


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
    named: bool
    segments: list[SkillSegment]


@dataclass
class Tag:
    tid: int
    typ: int
    tag_id: int
    title_key: str
    desc_key: str
    title: str
    desc: str


@dataclass
class StarEnds:
    star0: dict
    star5: dict
    general_id: int
    general0: int
    general5: int
    atk0: int
    atk5: int
    hp0: int
    hp5: int
    power: dict[int, int]
    skill_levels: dict[int, str]
    skill_ids: list[int]


@dataclass
class PalInfo:
    pid: int
    name_key: str
    name: str
    item: int
    unlocknum: int
    typ: int
    quality: int
    tag: int
    season: int
    weight: int
    unit_id: int
    team_scale: int
    skills: list[SkillDef]
    star: StarEnds
    item_name: str
    item_desc: str


@dataclass
class ExtraName:
    name_key: str
    name: str
    gid: int
    item_name: str
    item_desc: str
    desc_missing: bool


@dataclass
class CampLevel:
    level: int
    para2: str | None
    attr_val: int | None
    fightforce: int
    pre: str
    cost1: object
    cost2: object
    cost3: object
    build_time: object


@dataclass
class Official:
    system_name: str
    attr_source: str
    partner_dir: str
    camp_name: str
    camp_des: str
    castle_name: str
    star_hint: str
    build_hint: str
    func_locked: str
    func_tips: str
    pages: list[str]
    filters: list[str]
    catch_title: str
    catch_desc: str
    arena_name: str
    preview_title: str
    preview_desc: str
    memo_text: str
    goods: dict[int, Goods]
    qualities: dict[int, str]
    quality_6: str


@dataclass
class TablesData:
    official: Official
    pals: list[PalInfo]
    tags: list[Tag]
    teams: list[dict]
    teampos: list[dict]
    fuses: list[dict]
    catch: dict
    rolls: list[dict]
    auras: list[dict]
    camp: list[CampLevel]
    extras: list[ExtraName]
    skills: dict[int, SkillDef]
    attrs: dict[int, dict]
    attr_names: dict[int, str]
    building: dict
    function: dict
    jump: dict
    influence_parent: dict
    influence_pal: dict
    activities: dict[int, dict]
    terms: list[str] = field(default_factory=list)
    table_meta: dict = field(default_factory=dict)


def _skill_def(comp: dict, sid: int) -> SkillDef:
    name_key = comp.get("name") or None
    name = official_text(name_key) if name_key else ""
    named = bool(name)
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
        named=named,
        segments=segments,
    )


def _compare_string_packs(keys: set[str]) -> dict:
    packs = {}
    for label, path in PACK_STRINGS.items():
        packs[label] = load_json(path) if path.exists() else {}
    diffs = []
    missing = []
    for key in sorted(keys):
        values = {}
        present = set()
        for label in packs:
            if key in packs[label]:
                present.add(label)
                values[label] = packs[label].get(key)
        if present != set(packs):
            missing.append(key)
        elif len({json.dumps(v, ensure_ascii=False, sort_keys=True) if not isinstance(v, (str, int, float, type(None))) else v for v in values.values()}) > 1:
            diffs.append(key)
    return {
        "used_keys": len(keys),
        "value_diffs": diffs,
        "missing": missing,
        "packs": {k: len(v) for k, v in packs.items()},
        "string_sha256": {label: file_sha256(path) for label, path in PACK_STRINGS.items() if path.exists()},
    }


def _compare_table_packs(names: list[str]) -> dict:
    out = {}
    source = "2026-11-22-locallow"
    for name in names:
        paths = {label: (directory / name) for label, directory in PACK_DATA_DIRS.items()}
        info = {"exists": {}, "sha256": {}, "identical": {}, "source": source}
        for label, path in paths.items():
            info["exists"][label] = path.exists()
            if path.exists():
                info["sha256"][label] = file_sha256(path)
        base = info["sha256"].get(source)
        for label, digest in info["sha256"].items():
            info["identical"][label] = digest == base
        out[name] = info
    return out


def _goods(gid: int) -> Goods:
    nk, dk = f"goods_name_{gid}", f"goods_desc_{gid}"
    name_missing = not has_string(nk)
    desc_missing = not has_string(dk)
    return Goods(
        gid=gid,
        name=official_text(nk),
        desc=official_text(dk),
        name_key=nk,
        desc_key=dk,
        name_missing=name_missing,
        desc_missing=desc_missing,
    )


def _combat_pair(row: dict) -> tuple[int, int]:
    pairs = {aid: val for aid, val in (row.get("combatAttrArray") or parse_pipe_pairs(row.get("combatattr")))}
    if 3 not in pairs or 4 not in pairs:
        # fallback from string
        parsed = parse_pipe_pairs(row.get("combatattr"))
        pairs = {aid: val for aid, val in parsed}
    return pairs[3], pairs[4]


def _general_pair(row: dict) -> tuple[int, int]:
    arr = row.get("generalAttrArray")
    if isinstance(arr, list) and len(arr) >= 2 and not isinstance(arr[0], (list, tuple)):
        return _int(arr[0]), _int(arr[1])
    pairs = parse_pipe_pairs(row.get("generalattr"))
    if not pairs:
        raise RuntimeError(f"missing generalattr on star row {row.get('id')}")
    return pairs[0]


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    global STRINGS
    actual_strings = file_sha256(EXTRACT_STRINGS)
    if actual_strings != STRINGS_SHA256:
        raise RuntimeError(f"strings_zh.json sha256 mismatch: {actual_strings} != {STRINGS_SHA256}")
    STRINGS = load_json(EXTRACT_STRINGS)

    raw_pals = load_extract_table("pal.json")
    raw_tags = load_extract_table("pal_tag.json")
    raw_teams = load_extract_table("pal_team.json")
    raw_pos = load_extract_table("pal_teampos.json")
    raw_fuse = load_extract_table("pal_fuse.json")
    raw_catch = load_extract_table("pal_catch_param.json")
    raw_roll = load_extract_table("pal_roll_weight.json")
    raw_star = load_extract_table("pal_star.json")
    raw_aura = load_extract_table("pal_aura.json")
    raw_comp = {c["id"]: c for c in load_extract_table("hero_component.json")}
    raw_attr = {a["id"]: a for a in load_extract_table("attribute.json")}
    raw_func = load_extract_table("function.json")
    raw_build = load_extract_table("citybuilding.json")
    raw_lvup = load_extract_table("citybuilding_lvup.json")
    raw_lvup_new = load_extract_table("citybuilding_lvup_new.json")
    raw_jump = load_extract_table("jump.json")
    raw_inf = load_extract_table("influence_level.json")
    raw_act = load_extract_table("activity.json")
    raw_goods_file = load_extract_table("goods.json")

    if len(raw_pals) != PAL_COUNT:
        raise RuntimeError(f"pal.json expected {PAL_COUNT} rows, got {len(raw_pals)}")
    if len(raw_star) != STAR_COUNT:
        raise RuntimeError(f"pal_star.json expected {STAR_COUNT} rows, got {len(raw_star)}")
    if len(raw_tags) != TAG_COUNT:
        raise RuntimeError(f"pal_tag.json expected {TAG_COUNT} rows, got {len(raw_tags)}")
    if len(raw_teams) != TEAM_COUNT or len(raw_pos) != TEAMPOS_COUNT:
        raise RuntimeError("unexpected pal_team / pal_teampos counts")
    if len(raw_fuse) != FUSE_COUNT or len(raw_aura) != AURA_COUNT or len(raw_roll) != ROLL_COUNT:
        raise RuntimeError("unexpected pal_fuse / pal_aura / pal_roll_weight counts")
    if len(raw_catch) != 1:
        raise RuntimeError("pal_catch_param.json should have exactly 1 row")

    tags = []
    for row in raw_tags:
        title_key = row.get("titile")  # table spelling
        desc_key = row.get("desc")
        tags.append(Tag(
            tid=_int(row["id"]),
            typ=_int(row["type"]),
            tag_id=_int(row["tag_id"]),
            title_key=str(title_key) if title_key else "",
            desc_key=str(desc_key) if desc_key else "",
            title=official_text(title_key),
            desc=official_text(desc_key),
        ))
    tags_by_id = {t.tag_id: t for t in tags if t.typ == 1}

    qualities = {}
    for q in range(1, 6):
        name = official_text(f"pal_quality_{q}")
        if not name:
            raise RuntimeError(f"missing pal_quality_{q}")
        qualities[q] = name
    quality_6 = official_text("pal_quality_6")

    goods: dict[int, Goods] = {}
    for gid in GOODS_CORE + GOODS_TOKEN_MAIN + GOODS_TOKEN_EXTRA:
        goods[gid] = _goods(gid)

    attr_names = {}
    for aid in ATTR_SHOW:
        attr_names[aid] = official_text(f"attribute_name_{aid}")
        if not attr_names[aid]:
            raise RuntimeError(f"missing attribute_name_{aid}")
        show = raw_attr[aid].get("show_type")
        if show != ATTR_SHOW[aid]:
            raise RuntimeError(f"attribute {aid} show_type {show} != {ATTR_SHOW[aid]}")

    stars_by_pal: dict[int, dict[int, dict]] = defaultdict(dict)
    skill_ids: set[int] = set()
    for row in raw_star:
        pid = _int(row["monsterid"])
        star = _int(row["starlevel"])
        stars_by_pal[pid][star] = row
        arr = row.get("skillArray") or []
        for sid in arr:
            skill_ids.add(_int(sid))
        if row.get("skill"):
            for bit in str(row["skill"]).split("|"):
                if bit.strip():
                    skill_ids.add(_int(bit))
    if len(skill_ids) != SKILL_COUNT:
        raise RuntimeError(f"expected {SKILL_COUNT} skill ids, got {len(skill_ids)}")
    missing_comp = [sid for sid in sorted(skill_ids) if sid not in raw_comp]
    if missing_comp:
        raise RuntimeError(f"skill ids missing from hero_component: {missing_comp}")

    skills = {sid: _skill_def(raw_comp[sid], sid) for sid in skill_ids}
    leftovers = []
    for skill in skills.values():
        if skill.maxlv != 2:
            raise RuntimeError(f"skill {skill.sid} maxlv is {skill.maxlv}, not 2")
        if any(seg.level >= 3 for seg in skill.segments):
            raise RuntimeError(f"skill {skill.sid} has desc3–desc5")
        if not skill.named:
            raise RuntimeError(f"skill {skill.sid} has no official name")
        for seg in skill.segments:
            leftovers.extend((skill.sid, seg.level, seg.leftover) for _ in [0] if seg.leftover)
    if leftovers:
        raise RuntimeError(f"skill placeholders left unused: {leftovers[:8]}")

    pals: list[PalInfo] = []
    for row in raw_pals:
        pid = _int(row["id"])
        name_key = row["name"]
        name = official_text(name_key)
        if not name:
            raise RuntimeError(f"missing name for pal {pid} key {name_key}")
        by_star = stars_by_pal.get(pid, {})
        if set(by_star) != {0, 1, 2, 3, 4, 5}:
            raise RuntimeError(f"pal {pid} star rows are {sorted(by_star)}")
        s0, s5 = by_star[0], by_star[5]
        gid, g0 = _general_pair(s0)
        gid5, g5 = _general_pair(s5)
        if gid != gid5:
            raise RuntimeError(f"pal {pid} generalattr id changes across stars")
        # 0-star × (star+1) for all six rows
        for star, srow in by_star.items():
            g_id, g_val = _general_pair(srow)
            if g_id != gid or g_val != g0 * (star + 1):
                raise RuntimeError(f"pal {pid} star {star} generalattr {g_val} != {g0}×{star+1}")
            if _int(srow.get("cost") or 0) != 1:
                raise RuntimeError(f"pal {pid} star {star} cost is not 1")
            if _int(srow.get("season") or 0) != 0:
                raise RuntimeError(f"pal {pid} star {star} season is not 0")
        atk0, hp0 = _combat_pair(s0)
        atk5, hp5 = _combat_pair(s5)
        skill_ids_pal = [ _int(s) for s in (s0.get("skillArray") or str(s0.get("skill") or "").split("|") ) if s not in (None, "")]
        for sid in skill_ids_pal:
            if sid not in skills:
                raise RuntimeError(f"pal {pid} skill {sid} not loaded")
        power = {st: _int(by_star[st]["power"]) for st in range(6)}
        skill_levels = {st: str(by_star[st].get("skill_level") or "") for st in range(6)}
        item = _int(row["item"])
        pals.append(PalInfo(
            pid=pid,
            name_key=str(name_key),
            name=name,
            item=item,
            unlocknum=_int(row["unlocknum"]),
            typ=_int(row["type"]),
            quality=_int(row["quality"]),
            tag=_int(row["tag"] if row.get("tagInt") is None else row["tagInt"]),
            season=_int(row["season"]),
            weight=_int(row["weight"]),
            unit_id=_int(row["unit_id"]),
            team_scale=_int(row["team_scale"]),
            skills=[skills[sid] for sid in skill_ids_pal],
            star=StarEnds(
                star0=s0, star5=s5, general_id=gid, general0=g0, general5=g5,
                atk0=atk0, atk5=atk5, hp0=hp0, hp5=hp5,
                power=power, skill_levels=skill_levels, skill_ids=skill_ids_pal,
            ),
            item_name=goods[item].name if item in goods else official_text(f"goods_name_{item}"),
            item_desc=goods[item].desc if item in goods else official_text(f"goods_desc_{item}"),
        ))

    # constant columns
    if any(p.season != 0 or p.unlocknum != 1 or p.weight != 100 for p in pals):
        raise RuntimeError("pal.json season/unlocknum/weight are not uniformly 0/1/100")
    if any(p.quality not in qualities for p in pals):
        raise RuntimeError("pal quality outside 1–5")
    type_counts = defaultdict(int)
    for p in pals:
        type_counts[p.typ] += 1
    if dict(type_counts) != {1: 11, 2: 11, 3: 11, 4: 11, 5: 11}:
        raise RuntimeError(f"unexpected type distribution {dict(type_counts)}")

    # extras: palname_* not in pal.json
    in_table = {p.name_key for p in pals}
    extras: list[ExtraName] = []
    for key in sorted(STRINGS):
        if not key.startswith("palname_") or key in in_table:
            continue
        name = official_text(key)
        matched = [gid for gid in GOODS_TOKEN_EXTRA if goods[gid].name == name]
        if len(matched) != 1:
            # still record; try any goods_name with same value
            matched = [gid for gid, g in goods.items() if g.name == name and gid in GOODS_TOKEN_EXTRA]
        gid = matched[0] if matched else 0
        extras.append(ExtraName(
            name_key=key,
            name=name,
            gid=gid,
            item_name=goods[gid].name if gid else "",
            item_desc=goods[gid].desc if gid else "",
            desc_missing=goods[gid].desc_missing if gid else True,
        ))
    if len(extras) != 20:
        raise RuntimeError(f"expected 20 extra palname keys, got {len(extras)}")

    camp_rows = [r for r in raw_lvup if r.get("index") == BUILDING_INDEX]
    camp_new = [r for r in raw_lvup_new if r.get("index") == BUILDING_INDEX]
    if len(camp_rows) != CAMP_LEVELS or len(camp_new) != CAMP_LEVELS:
        raise RuntimeError("citybuilding_lvup 183 should have 41 rows")
    camp_by = { _int(r["lv"]): r for r in camp_rows }
    new_by = { _int(r["lv"]): r for r in camp_new }
    if set(camp_by) != set(range(0, 41)) or set(new_by) != set(range(0, 41)):
        raise RuntimeError("camp levels are not 0–40")
    # shared fields identical between lvup and lvup_new
    for lv, row in camp_by.items():
        shared = set(row) & set(new_by[lv])
        for k in shared:
            if row[k] != new_by[lv][k]:
                raise RuntimeError(f"citybuilding_lvup vs _new differ at 183 lv {lv} field {k}")

    camp: list[CampLevel] = []
    for lv in range(0, 41):
        row = camp_by[lv]
        para2 = unwrap_pipe(row.get("string_para2"))
        attr_val = None
        if para2:
            parts = [p for p in para2.split("|") if p != ""]
            if len(parts) >= 2 and _int(parts[0]) == 1249:
                attr_val = _int(parts[1])
        pre = unwrap_pipe(row.get("pre_building_level")) or ""
        camp.append(CampLevel(
            level=lv,
            para2=para2,
            attr_val=attr_val,
            fightforce=_int(row.get("fightforce") or 0),
            pre=pre,
            cost1=row.get("cost1"),
            cost2=row.get("cost2"),
            cost3=row.get("cost3"),
            build_time=row.get("buildTime"),
        ))
    if camp[0].attr_val is not None or camp[40].attr_val != 4000 or camp[1].attr_val != 100:
        raise RuntimeError("camp 1249 values are not 100,200,…,4000 from level 1–40")

    building = next(r for r in raw_build if r.get("id") == BUILDING_INDEX)
    function = next(r for r in raw_func if r.get("id") == FUNCTION_ID)
    jump = next(r for r in raw_jump if r.get("id") == JUMP_ID)
    influence_parent = next(r for r in raw_inf if r.get("id") == INFLUENCE_PARENT)
    influence_pal = next(r for r in raw_inf if r.get("id") == INFLUENCE_PAL)

    act_by = {r["id"]: r for r in raw_act if "id" in r}
    activities = {}
    for aid in CATCH_ACTIVITY_IDS + ARENA_ACTIVITY_IDS:
        if aid not in act_by:
            raise RuntimeError(f"missing activity {aid}")
        activities[aid] = act_by[aid]

    # goods.json is a remnant (column-index rows); none of the pal item ids appear.
    goods_ids_present = {r.get("id") for r in raw_goods_file if isinstance(r, dict)}
    if any(gid in goods_ids_present for gid in goods):
        # still only use strings; note in meta
        goods_usable = True
    else:
        goods_usable = False

    catch = raw_catch[0]
    official = Official(
        system_name=official_text("pal_list_1"),
        attr_source=official_text("pal_attr_1"),
        partner_dir=official_text(influence_parent.get("name")),
        camp_name=official_text(building.get("name") or "citybuilding_name_183"),
        camp_des=official_text(building.get("des") or "citybuilding_des_183"),
        castle_name=official_text("citybuilding_name_117"),
        star_hint=official_text("pal_attr_2"),
        build_hint=official_text("pal_edit_10"),
        func_locked=official_text("pal_function_1"),
        func_tips=official_text(function.get("tips") or "function_tips_30"),
        pages=[official_text(f"pal_page_{i}") for i in range(1, 4)],
        filters=[official_text(f"pal_filter_{i}") for i in range(1, 4)],
        catch_title=official_text("pal_catch_title"),
        catch_desc=official_text("activity_desc_5002001"),
        arena_name=official_text("activity_name_5001022"),
        preview_title=official_text("season_preview_title_406"),
        preview_desc=official_text("season_preview_desc_413"),
        memo_text=official_text("season_memo_s2_photo1_text3"),
        goods=goods,
        qualities=qualities,
        quality_6=quality_6,
    )
    if official.system_name != "帕魯" or official.camp_name != "帕魯營地":
        raise RuntimeError("official system / building names did not resolve")

    table_cmp = _compare_table_packs(list(TABLE_SHA256))
    string_cmp = _compare_string_packs(set(USED_KEYS))
    terms = _terms(official, pals, tags, goods, skills, extras, attr_names)
    # Use the whole string pack so compounds in later-rendered official sentences are kept whole.
    source_texts = [v for v in STRINGS.values() if isinstance(v, str) and v]
    source_texts.extend([f"{pal.name}帕魯" for pal in pals])
    source_texts.extend([f"{ex.name}帕魯" for ex in extras])
    source_texts.extend([f"{tag.title}帕魯" for tag in tags if tag.title])
    terms = _extend_adjacent_terms(terms, source_texts)
    data = TablesData(
        official=official,
        pals=pals,
        tags=tags,
        teams=list(raw_teams),
        teampos=list(raw_pos),
        fuses=list(raw_fuse),
        catch=catch,
        rolls=list(raw_roll),
        auras=list(raw_aura),
        camp=camp,
        extras=extras,
        skills=skills,
        attrs=raw_attr,
        attr_names=attr_names,
        building=building,
        function=function,
        jump=jump,
        influence_parent=influence_parent,
        influence_pal=influence_pal,
        activities=activities,
        terms=terms,
        table_meta={
            "table_cmp": table_cmp,
            "string_cmp": string_cmp,
            "goods_usable": goods_usable,
            "goods_rows": len(raw_goods_file),
            "skill_count": len(skills),
            "used_keys": len(USED_KEYS),
        },
    )
    return data


def _terms(
    official: Official,
    pals: list[PalInfo],
    tags: list[Tag],
    goods: dict[int, Goods],
    skills: dict[int, SkillDef],
    extras: list[ExtraName],
    attr_names: dict[int, str],
) -> list[str]:
    terms: set[str] = set()
    add = terms.add
    for value in (
        official.system_name, official.attr_source, official.partner_dir,
        official.camp_name, official.castle_name, official.catch_title,
        official.arena_name, official.preview_title, official.quality_6,
        "寵物", "寵物總表", "守護魔獸", "守護魔獸總表", "英靈", "英靈總表",
        "部族", "聯盟", "自然", "種族光環", "帕魯信物", "帕魯捕捉隊",
        "英雄屬性加成", "戰鬥技能",
    ):
        if value:
            add(value)
    for name in official.qualities.values():
        add(name)
    for name in official.pages + official.filters:
        if name:
            add(name)
    for pal in pals:
        add(pal.name)
    for ex in extras:
        add(ex.name)
    for tag in tags:
        if tag.title:
            add(tag.title)
    for g in goods.values():
        if g.name:
            add(g.name)
    for skill in skills.values():
        if skill.name:
            add(skill.name)
    for name in attr_names.values():
        if name:
            add(name)
    return sorted({t for t in terms if t}, key=len, reverse=True)


def _extend_adjacent_terms(terms: list[str], texts: list[str]) -> list[str]:
    """If two highlight terms sit next to each other in official text, add the compound as a term."""
    found = {t for t in terms if t}
    corpus = [str(text) for text in texts if text]

    def adjacent(text: str) -> list[str]:
        term_list = sorted(found, key=len, reverse=True)
        ranges: list[tuple[int, int]] = []
        for term in term_list:
            start = 0
            while True:
                i = text.find(term, start)
                if i < 0:
                    break
                j = i + len(term)
                if not any(i < e and j > s for s, e in ranges):
                    ranges.append((i, j))
                start = i + 1
        ranges.sort()
        out = []
        for (s1, e1), (s2, e2) in zip(ranges, ranges[1:]):
            if e1 == s2:
                combo = text[s1:e2]
                if combo and combo not in found:
                    out.append(combo)
        return out

    changed = True
    while changed:
        changed = False
        for text in corpus:
            for combo in adjacent(text):
                found.add(combo)
                changed = True
    return sorted(found, key=len, reverse=True)


def _quality_label(q: int, official: Official) -> str:
    return official.qualities.get(q, str(q))


def _tag_label(tag_id: int, tags: list[Tag]) -> str:
    for t in tags:
        if t.typ == 1 and t.tag_id == tag_id:
            return t.title or str(tag_id)
    return str(tag_id)


def _attr_plain(attr_id: int, value: int, names: dict[int, str]) -> str:
    name = names.get(attr_id)
    if not name:
        return str(value)
    return f"{name} {value}"


def _skill_level_curves(pals: list[PalInfo]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for pal in pals:
        q = pal.quality
        curve = pal.star.skill_levels
        n = len(pal.star.skill_ids)
        if q not in out:
            out[q] = {"n": n, "levels": dict(curve)}
        else:
            if out[q]["n"] != n or out[q]["levels"] != curve:
                raise RuntimeError(f"quality {q} skill-level curves are not uniform")
    return out


def _power_curves(pals: list[PalInfo]) -> dict[int, dict[int, int]]:
    out: dict[int, dict[int, int]] = {}
    for pal in pals:
        q = pal.quality
        if q not in out:
            out[q] = dict(pal.star.power)
        elif out[q] != pal.star.power:
            raise RuntimeError(f"quality {q} power curves are not uniform")
    return out


def _upgrade_nodes(levels: dict[int, str]) -> list[str]:
    """Read at which star each skill slot first reaches level 2."""
    slots = [bit for bit in str(levels[0]).split("|") if bit != ""]
    n = len(slots)
    first = [None] * n
    for star in range(0, 6):
        bits = [bit for bit in str(levels[star]).split("|") if bit != ""]
        if len(bits) != n:
            continue
        for i, bit in enumerate(bits):
            if first[i] is None and bit.strip() == "2":
                first[i] = star
    parts = []
    for i, star in enumerate(first, start=1):
        label = f"第 {i} 段" if n > 1 else "技能"
        parts.append(f"{label} {star} 星" if star is not None else f"{label} 未升至 2 級")
    return parts


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    o = data.official
    names = data.attr_names
    castle = o.castle_name

    camp_rows = []
    for row in data.camp:
        if row.para2 and row.attr_val is not None:
            para = fmt_int(row.attr_val)
        else:
            para = "無"
        time_cell = "無" if row.build_time in (None, "", -1) else fmt_int(row.build_time)
        camp_rows.append([
            str(row.level),
            para,
            fmt_int(row.fightforce),
            fmt_pre_visible(row.pre, castle, terms),
            fmt_costs_visible(row.cost1, row.cost2, row.cost3),
            time_cell,
        ])
    camp = table(
        [
            "級",
            H(names[1249], terms) + "（原值）",
            "戰力",
            "前置",
            "消耗",
            "時間（表上原值，無單位）",
        ],
        camp_rows,
        mobile="cards",
        card_title="級",
    )

    catalog_rows = []
    for pal in data.pals:
        catalog_rows.append([
            str(pal.pid),
            H(pal.name, terms),
            H(_quality_label(pal.quality, o), terms),
            H(_tag_label(pal.tag, data.tags), terms),
            str(pal.item),
            H(_attr_plain(pal.star.general_id, pal.star.general0, names), terms),
        ])
    catalog = table(
        ["編號", "名稱", "品質", "標籤", "道具", H(official_text("pal_detail_1"), terms) + "（0 星原值）"],
        catalog_rows,
        mobile="cards",
        card_title="名稱",
    )

    extra_rows = []
    for ex in data.extras:
        desc = MISSING_TEXT if ex.desc_missing else ex.item_desc
        extra_rows.append([
            H(ex.name, terms),
            str(ex.gid) if ex.gid else "無",
            H(desc, terms) if not ex.desc_missing else e(MISSING_TEXT),
        ])
    extras = table(
        ["名稱", "道具", "道具說明"],
        extra_rows,
        mobile="cards",
        card_title="名稱",
    )

    tag_rows = []
    for t in data.tags:
        tag_rows.append([
            H(t.title, terms) if t.title else e(MISSING_TEXT),
            H(t.desc, terms) if t.desc else e(MISSING_TEXT),
        ])
    tags = table(
        ["名稱", "說明"],
        tag_rows,
        mobile="cards",
        card_title="名稱",
    )

    catch_fields = [
        "id", "pal_catch_open_season", "pal_per_catch_amount", "pal_team_usage_time",
        "pal_abandon_percent", "pal_abandon_pal_percent", "pal_hall_team_max",
        "pal_loot_percent", "pal_loot_pal_percent", "pal_loot_pal_max", "pal_loot_time_max",
        "crystal_pal_reward_weight_id", "guild_pal_reward_weight_id",
        "loot_war_mail_id", "been_loot_war_mail_id", "loot_reward_mail_id", "catch_end_mail",
        "alliance_resource_id", "ocean_server_march_gate_id",
        "crystal_pal_reward_icon", "palace_pal_reward_icon",
        "pal_catch_chance", "other_kingdom_reward_id", "retreat_time",
        "target_catch_time_min", "target_change_max", "activity_desc", "activity_info",
        "palace_pal_per_catch_amount", "patch_per_spot_max",
        "plunder_block_count", "plunder_block_cd_seconds", "palace_build_range",
    ]
    catch_rows = []
    for field in catch_fields:
        val = data.catch.get(field)
        if field == "activity_desc":
            text = official_text(val) if val else ""
            shown = f"<code>{e(val)}</code>"
            if text:
                shown += f"（{H(text, terms)}）"
            elif val:
                shown += f"（{e(MISSING_TEXT)}）"
        else:
            shown = f"<code>{e(raw_json(val) if not isinstance(val, str) else val)}</code>"
        catch_rows.append([f"<code>{e(field)}</code>", shown])
    notes_catch = table(["欄位", "原值"], catch_rows, mobile="cards", card_title="欄位")

    mail_specs = [
        ("loot_war_mail_id", 600052, "mail_title_600052", "mail_desc_600052"),
        ("been_loot_war_mail_id", 600053, "mail_title_600053", "mail_desc_600053"),
        ("loot_reward_mail_id", 600054, "mail_title_600054", "mail_desc_600054"),
        ("catch_end_mail", 600055, "mail_title_600055", "pal_catch_reward_mail_text"),
    ]
    mail_rows = []
    mail_note_rows = []
    for field, mid, title_key, body_key in mail_specs:
        title = official_text(title_key) if has_string(title_key) else ""
        body = official_text(body_key) if has_string(body_key) else ""
        mail_rows.append([
            H(title, terms) if title else e(MISSING_TEXT),
            H(body, terms) if body else e(MISSING_TEXT),
        ])
        bits = []
        if title:
            bits.append(f"標題「{H(title, terms)}」（<code>{e(title_key)}</code>）")
        else:
            bits.append(f"標題鍵 <code>{e(title_key)}</code>：{e(MISSING_TEXT)}")
        if body:
            bits.append(f"正文「{H(body, terms)}」（<code>{e(body_key)}</code>）")
        else:
            bits.append(f"正文鍵 <code>{e(body_key)}</code>：{e(MISSING_TEXT)}")
        mail_note_rows.append([f"<code>{e(field)}</code>", str(mid), "；".join(bits)])
    mails = table(["標題", "正文"], mail_rows, mobile="cards", card_title="標題")
    notes_mails = table(["欄位", "id", "標題／正文"], mail_note_rows, mobile="cards", card_title="欄位")

    roll_rows = []
    for row in data.rolls:
        roll_rows.append([
            str(row.get("group_id")),
            str(row.get("reward_id")),
            str(row.get("weight")),
        ])
    rolls = table(
        ["組", "獎勵編號", "權重（原值）"],
        roll_rows,
        mobile="cards",
        card_title="獎勵編號",
    )

    fuse_rows = []
    for row in data.fuses:
        q = _int(row["quality"])
        fuse_rows.append([
            H(_quality_label(q, o), terms),
            str(row.get("higherweight")),
            str(row.get("luck")),
        ])
    fuses = table(
        ["品質", "權重原值", "幸運值"],
        fuse_rows,
        mobile="cards",
        card_title="品質",
    )

    team_rows = []
    for row in data.teams:
        desc_key = row.get("desc")
        if desc_key:
            desc = official_text(desc_key)
            desc_cell = H(desc, terms) if desc else e(MISSING_TEXT)
        else:
            desc_cell = e(MISSING_TEXT)
        team_rows.append([
            str(row.get("id")),
            str(row.get("pal_num")),
            desc_cell,
        ])
    teams = table(
        ["隊伍", "人數", "說明"],
        team_rows,
        mobile="cards",
        card_title="隊伍",
    )

    pos_rows = []
    for row in data.teampos:
        desc_key = row.get("desc")
        if desc_key:
            desc = official_text(desc_key)
            desc_cell = H(desc, terms) if desc else e(MISSING_TEXT)
        else:
            desc_cell = e(MISSING_TEXT)
        pos_rows.append([
            str(row.get("teamid")),
            str(row.get("type")),
            desc_cell,
        ])
    teampos = table(
        ["隊伍", "站位", "說明"],
        pos_rows,
        mobile="cards",
        card_title="隊伍",
    )

    power = _power_curves(data.pals)
    power_rows = []
    for q in sorted(power):
        power_rows.append([H(_quality_label(q, o), terms)] + [fmt_int(power[q][st]) for st in range(6)])
    powers = table(
        ["品質", "0 星", "1 星", "2 星", "3 星", "4 星", "5 星"],
        power_rows,
        mobile="cards",
        card_title="品質",
    )

    star_rows = []
    for pal in data.pals:
        star_rows.append([
            str(pal.pid),
            H(pal.name, terms),
            H(_quality_label(pal.quality, o), terms),
            f"{fmt_int(pal.star.atk0)}／{fmt_int(pal.star.atk5)}",
            f"{fmt_int(pal.star.hp0)}／{fmt_int(pal.star.hp5)}",
            H(
                f"{names[pal.star.general_id]} {pal.star.general0}／{pal.star.general5}",
                terms,
            ),
        ])
    stars = table(
        ["編號", "名稱", "品質", "攻擊 0／5 星", "生命值 0／5 星", H(official_text("pal_detail_1"), terms) + " 0／5 星"],
        star_rows,
        mobile="cards",
        card_title="名稱",
    )

    curves = _skill_level_curves(data.pals)
    sl_rows = []
    for q in sorted(curves):
        lv = curves[q]["levels"]
        sl_rows.append(
            [H(_quality_label(q, o), terms), str(curves[q]["n"])]
            + [fmt_skill_levels_visible(lv[st]) for st in range(6)]
        )
    skill_levels = table(
        ["品質", "技能數", "0 星", "1 星", "2 星", "3 星", "4 星", "5 星"],
        sl_rows,
        mobile="cards",
        card_title="品質",
    )

    # Visible aura: collapse five unnamed groups with identical values into 3 rows.
    by_count: dict[int, dict] = {}
    for row in data.auras:
        desc_key = row.get("desc")
        desc = official_text(desc_key) if desc_key else ""
        req = str(row.get("require") or "")
        parts = req.split("|")
        count = _int(parts[1]) if len(parts) >= 2 else 0
        attr_pairs = parse_pipe_pairs(row.get("attr"))
        vals = {aid: val for aid, val in attr_pairs}
        entry = {"desc": desc, "atk": vals.get(62), "hp": vals.get(63), "raw": row}
        if count not in by_count:
            by_count[count] = entry
        else:
            if (by_count[count]["atk"] != entry["atk"] or by_count[count]["hp"] != entry["hp"]
                    or by_count[count]["desc"] != entry["desc"]):
                raise RuntimeError(f"aura values for count {count} are not uniform")
    aura_rows = []
    for count in sorted(by_count):
        item = by_count[count]
        aura_rows.append([
            str(count),
            H(item["desc"], terms) if item["desc"] else e(MISSING_TEXT),
            fmt_int(item["atk"]) if item["atk"] is not None else "無",
            fmt_int(item["hp"]) if item["hp"] is not None else "無",
        ])
    auras = table(
        ["同種族隻數", "官方說明", H(names[62], terms) + "（原值）", H(names[63], terms) + "（原值）"],
        aura_rows,
        mobile="cards",
        card_title="同種族隻數",
    )

    aura_note_rows = []
    for row in data.auras:
        aura_note_rows.append([
            str(row.get("id")),
            f"<code>{e(row.get('require'))}</code>",
            f"<code>{e(row.get('desc'))}</code>",
            f"<code>{e(row.get('attr'))}</code>",
        ])
    notes_auras = table(
        ["id", "require", "說明鍵", "屬性原值（62、63）"],
        aura_note_rows,
        mobile="cards",
        card_title="id",
    )

    mat_ids = list(GOODS_CORE)
    mat_rows = []
    for gid in mat_ids:
        g = o.goods[gid]
        desc = e(MISSING_TEXT) if g.desc_missing else H(g.desc, terms)
        name = e(MISSING_TEXT) if g.name_missing else H(g.name, terms)
        mat_rows.append([name, desc])
    materials = table(
        ["名稱", "說明"],
        mat_rows,
        mobile="cards",
        card_title="名稱",
    )

    arena_note_rows = []
    for aid in ARENA_ACTIVITY_IDS:
        row = data.activities[aid]
        arena_note_rows.append([
            str(aid),
            f"<code>{e(row.get('is_open'))}</code>",
            f"<code>{e(row.get('take_effect_time'))}</code>",
            f"<code>{e(row.get('server_list'))}</code>",
        ])
    notes_arena = table(
        ["id", "is_open", "take_effect_time", "server_list"],
        arena_note_rows,
        mobile="cards",
        card_title="id",
    )

    return {
        "camp": camp,
        "catalog": catalog,
        "extras": extras,
        "tags": tags,
        "mails": mails,
        "rolls": rolls,
        "fuses": fuses,
        "teams": teams,
        "teampos": teampos,
        "powers": powers,
        "stars": stars,
        "skill_levels": skill_levels,
        "auras": auras,
        "materials": materials,
        "notes_catch": notes_catch,
        "notes_mails": notes_mails,
        "notes_auras": notes_auras,
        "notes_arena": notes_arena,
        "skill_curves": curves,
    }


def _skill_block(skill: SkillDef, terms: list[str]) -> str:
    if not skill.named:
        return (
            f"<li><strong>{e('（沒有官方技能名）')}</strong>"
            f"<p>{e(MISSING_NAME_DESC)}</p></li>"
        )
    parts = [f"<li><strong>{H(skill.name, terms)}</strong>"]
    items = []
    for seg in skill.segments:
        if seg.level == 1:
            label = "基礎"
        else:
            label = f"升至 {seg.level} 級追加"
        if not seg.template:
            body = e(MISSING_TEXT)
        else:
            body = highlight_lines(seg.filled, terms)
        leftover = ""
        if seg.leftover:
            leftover = "（原文有未出現的佔位，參數已按對應位置代入，不自行挪位）"
        items.append(f"<li>{e(label)}：{body}{e(leftover)}</li>")
    parts.append("<ul>" + "".join(items) + "</ul></li>")
    return "".join(parts)




def _pack_same(tc: dict, name: str, labels: tuple[str, ...]) -> bool:
    info = tc.get(name) or {}
    return all(info.get("exists", {}).get(label) and info.get("identical", {}).get(label) for label in labels)


def _data_notes(data: TablesData) -> str:
    sc = data.table_meta["string_cmp"]
    tc = data.table_meta["table_cmp"]
    diffs = sc["value_diffs"]
    missing = sc["missing"]
    if diffs or missing:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵中，值不同的有 {diffs or '無'}，"
            f"在某一批缺鍵：{missing or '無'}。"
        )
    else:
        extra = (
            f"本頁用到的 {sc['used_keys']} 個字串鍵，在 2026-11-05、2026-11-22、"
            "2026-11-22 LocalLow 與現行字串檔裡值相同。"
        )

    seven = (
        "pal.json", "pal_tag.json", "pal_team.json", "pal_teampos.json",
        "pal_fuse.json", "pal_catch_param.json", "pal_roll_weight.json",
    )
    seven_all = all(_pack_same(tc, name, ("live", "2026-11-05", "2026-11-22", "2026-11-22-locallow")) for name in seven)
    if seven_all:
        seven_note = (
            "`pal.json`、`pal_tag.json`、`pal_team.json`、`pal_teampos.json`、`pal_fuse.json`、"
            "`pal_catch_param.json`、`pal_roll_weight.json` 這七張表在 2026-11-05、2026-11-22 StreamingAssets、"
            "2026-11-22 LocalLow 與現行 `data/` 四批都存在，且四批位元組相同。"
            "初查曾以為 11-05 可能沒有 `pal_catch_param.json` 與 `pal_roll_weight.json`；對過檔案後，這兩張在 11-05 解壓目錄裡就有，並且與後續三批相同。"
        )
    else:
        seven_note = "七張共有帕魯主表在四批裡的存在與位元組對照見各檔說明，並非全部相同。"

    star_note = (
        "`pal_star.json` 與 `pal_aura.json` 只出現在 2026-11-22 LocalLow 與現行 `data/`，兩批位元組相同；"
        "2026-11-05 解壓快照與 2026-11-22 StreamingAssets 都沒有這兩張表。"
        "本頁從 LocalLow 歸檔讀取這兩張，不把它們寫成 11-05 也有。"
    )

    strings_note = (
        "字串檔本身三批解壓並不相同：2026-11-05、2026-11-22 與 2026-11-22 LocalLow 的 `strings_zh.json` 整檔 sha256 各異；"
        "現行 `strings_zh.json` 與 LocalLow 那份位元組相同。本頁採用 LocalLow 字串檔。"
        "含 pal 的界面鍵在三批解壓裡都已有，與 live 值相同；缺的是升星、光環表本身，不是這些字串。"
    )

    # hero_component
    comp_ident = tc["hero_component.json"]["identical"]
    if comp_ident.get("2026-11-05") and comp_ident.get("2026-11-22"):
        comp_note = "`hero_component.json` 四批位元組相同。"
    else:
        comp_note = (
            "`hero_component.json` 整檔在 2026-11-05／2026-11-22 StreamingAssets 與 LocalLow／現行檔不同；"
            "列數同為 1,911。兩邊只在無關本頁的 1503213 列 `specialAttribute4Self` 不同。"
            "本頁用到的 155 個技能 id，11-05 已有，其 name／desc1–desc2／參數／maxlv 與 LocalLow 相同。"
        )

    attr_note = (
        "`attribute.json` 整檔 11-05 與 11-22／LocalLow／現行檔不同；本頁用到的屬性列只差 `NameKey` 欄，"
        "`show_type` 與 `attribute_name_{id}` 顯示名按本頁所錄。"
    )
    func_note = (
        "`function.json` 整檔 11-05／11-22 StreamingAssets 與 LocalLow／現行檔不同；"
        "本頁用到的 id 83 列，除 LocalLow 多了 `_condition.metaId` 外，名稱、開啟面板、`func_open_param`、`condition_type`、`value`、提示鍵皆相同。"
    )
    build_note = (
        "`citybuilding.json` 只出現在 2026-11-22 LocalLow 與現行 `data/`，11-05 與 11-22 StreamingAssets 沒有這份檔。"
        "建築 183 的 `season_range_1`、`open_season_day`、`costs`、`maxlevel` 取自 LocalLow 這份。"
        "建築名稱與說明字串 `citybuilding_name_183`／`citybuilding_des_183` 在 11-05 字串檔已有，與 live 相同。"
    )
    lvup_note = (
        "`citybuilding_lvup.json` 與 `citybuilding_lvup_new.json` 整檔 11-05 與後續批次不同；"
        "建築 183 的 41 筆（0–40 級）在 11-05 與 LocalLow 相同，兩張升級表的共有欄位也相同。"        "`string_para2` 與 `pre_building_level` 在表上是單元素陣列，本頁列出其中的字串。"
    )
    jump_note = (
        "`jump.json` 整檔 11-05 與後續批次不同；本頁用到的 2000067 列與 11-05 相同。"
        "`influence_level.json` 四批位元組相同。"
    )
    act_note = (
        "`activity.json` 整檔 11-05 與後續批次不同；本頁列出的 7 列活動在 11-05 已有。"
        "對照所列欄位（名稱、說明、type、is_open、season、condition、take_effect_time、server_list、form_list、info、faq）與 11-05 相同；"
        "LocalLow 的捕捉活動列多了 `main_entrance_change`（值為空），本頁不另解釋這一欄。"
    )
    goods_note = (
        f"`goods.json` 只出現在 LocalLow 與現行 `data/`（{data.table_meta['goods_rows']} 列），"
        "列內容是欄位序號殘件，對不上本頁用到的道具 id。道具名稱與說明一律取自同一批 `strings_zh.json` 的 `goods_name_*`／`goods_desc_*`。"
    )

    mail_note = (
        "郵件 600052、600053 的標題鍵是 `mail_title_600052`／`mail_title_600053`，"
        "標題分別是「劫掠戰報」「被劫掠戰報」，與正文鍵 `mail_desc_*` 不是同一鍵；正文已去掉顏色標籤後照錄。"
        "600055 的正文鍵是 `pal_catch_reward_mail_text`，沒有 `mail_desc_600055`。"
    )

    return (
        f"資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。"
        "來源是 2026-11-22 LocalLow 解壓表與 `strings_zh.json`（歸檔於 `/workspace/topheroes/extracts/2026-11-22-locallow/`），"
        "各表已 pin sha256，不改用未記來源的現行 live 檔。"
        f"{seven_note}{star_note}{strings_note}{comp_note}{attr_note}{func_note}{build_note}{lvup_note}{jump_note}{act_note}{goods_note}{mail_note}{extra}"
        "屬性名用 `attribute_name_{id}`。"
        "升星 `combatattr` 的 3／4（攻擊／生命值）與 `generalattr` 的 3003／4003／5003、3004／4004／5004、以及部分列的 3／4，`show_type` 皆為 1，只錄原值。"
        "不要把 3／4 跟 103／104（英雄攻擊／英雄生命，`show_type` 為 2）混在一起。"
        "光環的 62／63（隊列攻擊／隊列生命）與營地升級的 1249（提高捕獲帕魯的機率）`show_type` 為 2，只錄原值，不自行換成百分比。"
        "升星說明若官方已有百分比字串，只照錄字串，不用表上原值去換算或對齊成同一個數字。"
        "`conversion_rate`、`season`、`unlocktime`、`season_range_1`、`open_season_day`、`take_effect_time`、`server_list`、`is_open` 只照錄，不對成 S2／S3，也不把預告或紀念文案當成已推出或標未開放。"
        "主表與升星表的 `season` 皆為 0。主表沒有 `unlocktime`。"
        "標籤表欄位名是 `titile`（表上的拼法）；隊伍表欄位名是 `conditon`（表上的拼法）。"
        "本頁不收 `map_slg_underpalace.json`（檔名含 pal，內容是地圖實例，沒有繫在帕魯系統上）。"
    )



def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    func = data.function
    b = data.building
    catch1 = data.activities[5002001]
    catch2 = data.activities[5002002]
    title = "Top Heroes Wiki｜帕魯總表"
    lede = (
        f"本頁列出官方界面所稱的「{o.system_name}」：55 隻的名稱、標籤、捕捉與權重、融合、隊伍與位置、"
        "升星規則與關鍵節點、技能原文，以及光環。"
        "這不是寵物，也不是守護魔獸或英靈。"
    )
    summary = (
        f"官方界面所稱的{o.system_name}：55 隻名稱、標籤、捕捉與權重、融合、隊伍與位置、"
        "升星規則與關鍵節點、技能原文，以及光環。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍與解鎖"},
        {"id": "camp", "label": "帕魯營地升級"},
        {"id": "catalog", "label": "名錄"},
        {"id": "tags", "label": "標籤"},
        {"id": "catch", "label": "捕捉與權重"},
        {"id": "fuse", "label": "融合"},
        {"id": "teams", "label": "隊伍與位置"},
        {"id": "star", "label": "升星"},
        {"id": "skills", "label": "技能"},
        {"id": "aura", "label": "光環"},
        {"id": "materials", "label": "材料與道具"},
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
        "正文只根據遊戲資料表與官方字串，不評定帕魯強弱，也不排行。"
        f"官方界面稱「{H(o.system_name, terms)}」。"
        f"這不是寵物；寵物見已發佈的<a href=\"pets.html\">{H('寵物總表', terms)}</a>。"
        f"這不是守護魔獸；守護魔獸見已發佈的<a href=\"holybeasts.html\">{H('守護魔獸總表', terms)}</a>。"
        f"已發佈的<a href=\"valhalla.html\">{H('英靈總表', terms)}</a>是綁在英雄身上的另一套養成，不是帕魯。"
        "精靈、魚缸、蝴蝶、乙太牧場不在本頁展開。"
        "對照路徑、筆數與欄位原值見資料說明。"
    ))
    add("<ul>")
    add("<li><strong>本頁只寫官方所稱的「"
        + H(o.system_name, terms)
        + "」這套，共 55 隻。</strong>"
        "下面會列出名稱、標籤、捕捉與權重、融合、隊伍與位置、升星規則與關鍵節點、技能原文，以及光環。"
        "升星 330 筆不整表傾印。</li>")
    add("<li>名稱依遊戲裡看得到的顯示名書寫。沒有官方名稱或說明的欄位會註明「字串表沒有內容」或「字串表沒有名稱與說明」，不編造。"
        f"官方用語是「{H(o.system_name, terms)}」「{H('部族', terms)}」。"
        "官方用字不一致時照錄，不自行改寫。"
        "主表有一欄類型編號為 1–5，字串表沒有這欄的中文名；"
        + "、".join(H(t.title, terms) for t in data.tags if t.typ == 1 and t.tag_id <= 5)
        + " 是標籤名稱，不是那一欄的名稱，不編造陣營或地圖名。</li>")
    add("<li><strong>不要從時間或賽季欄位、預告或紀念文案自動標未開放，也不把預告當成已推出證明。</strong>"
        "相關欄位與文案只照錄，不把欄位裡的數字自行對成賽季號。"
        "屬性只錄表上的原值，不自行換成百分比。"
        "官方文案若已有百分比，只照錄字串，不與表上原值換算成同一個數字。</li>")
    add("<li>技能文案以官方基礎效果與升至 2 級的追加說明填入對應參數後照錄。"
        "追加說明不是另寫一條完整技能。這批帕魯技能沒有第三段到第五段說明。"
        "若文案某個佔位未出現，不自行挪位。"
        "多名技能共用同一名稱時，仍各錄各的參數與文案，不以同名視為同一條。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍與解鎖</h2>")
    add(p_html(
        f"官方界面稱「{H(o.system_name, terms)}」。"
        f"影響力目錄在「{H(o.partner_dir, terms)}」底下有「{H(o.system_name, terms)}」一項。"
        f"開啟提示寫「{H(o.func_tips, terms)}」。"
        "開啟條件的欄位原值見資料說明；117 的官方名稱是「"
        + H(o.castle_name, terms)
        + "」。"
    ))
    add(p_html(
        f"建築 {BUILDING_INDEX} 的官方名稱是「{H(o.camp_name, terms)}」，升級說明「{H(o.camp_des, terms)}」。"
        "最高等級與建造費用原值見資料說明，只照錄，不對成賽季號。"
        "升級表見下節。"
        f"界面另寫：「{H(o.star_hint, terms)}」；「{H(o.build_hint, terms)}」；「{H(o.func_locked, terms)}」。"
        "分頁標題為「"
        + "」「".join(H(p, terms) for p in o.pages)
        + "」。篩選有「"
        + "」「".join(H(f, terms) for f in o.filters)
        + "」。"
        "本頁不把這些前置自行寫成唯一開啟條件，也不把「"
        + H(o.filters[2], terms)
        + "」篩選自行寫成類型 1–5 的中文名。"
    ))
    add(p_html(
        f"活動「{H(o.catch_title, terms)}」說明：「{H(o.catch_desc, terms)}」。"
        "活動表有兩列共用此名稱與說明。時間、伺服器與開關欄只照錄，不自行對成賽季號或顯示伺服器，也不據此標已推出或未開放。原值見資料說明。"
    ))
    add(p_html(
        f"活動「{H(o.arena_name, terms)}」在活動表有五列共用此名稱，說明字串表沒有內容。"
        "五列的類型、條件與其他欄位原值見資料說明，只照錄，不自行對成賽季號。"
    ))
    add(p_html(
        f"亂鬥玩法說明標題是「{H(official_text('palu_arena_info_title'), terms)}」。官方說明："
    ))
    add(f"<blockquote>{highlight_lines(official_text('palu_activity_info_desc1'), terms)}</blockquote>")
    arena_keys = "、".join(
        f"「{H(official_text(f'palu_arena_activity_key{i}'), terms)}」" for i in range(1, 7)
    )
    arena_tips = "、".join(
        [
            f"「{H(official_text(f'palu_arena_activity_tips{i}'), terms)}」" for i in range(1, 4)
        ]
        + [f"「{H(official_text(f'pal_arena_tips_{i}'), terms)}」" for i in range(1, 4)]
    )
    g522 = o.goods[522]
    add(p_html(
        f"亂鬥界面另有{arena_keys}，以及{arena_tips}。"
        f"道具 522 名稱「{H(g522.name, terms)}」，說明「{H(g522.desc, terms)}」。"
        f"機器人名稱是「{H(official_text('palu_arena_robot_name'), terms)}」。"
        "升星表另有戰力欄，本頁不把該欄與「"
        + H(official_text("palu_arena_activity_key1"), terms)
        + "」自行寫成同一顯示，也不把心形圖標當戰力。"
        "亂鬥用的獨立對戰數值表本頁未另列，見資料說明。"
    ))
    add(p_html(
        f"預告標題是「{H(o.preview_title, terms)}」，"
        f"說明是「{H(o.preview_desc, terms)}」。"
        f"紀念文案是「{H(o.memo_text, terms)}」。"
        "標題與說明是遊戲原文，只照錄，不是已推出或未開放的判斷，也不把文案裡的數字自行對成賽季號。"
    ))
    add("    </section>")

    add('    <section id="camp">')
    add(f"      <h2>{e(o.camp_name)}升級</h2>")
    add(p_html(
        f"升級表列建築「{H(o.camp_name, terms)}」0–40 級，共 41 筆（檔名見資料說明）。"
        "說明欄全為空。"
        "1–40 級的捕捉機率原值從 100 起每級加 100，至 40 級為 4000。"
        f"官方名稱是「{H(data.attr_names[1249], terms)}」，只錄原值，不自行換成百分比。"
        "這與捕捉參數表裡另一個機率欄不是同一欄，本頁不自行合併。"
    ))
    add(p_html(
        f"0–25 級的前置是「{H(o.castle_name, terms)}」25 級；"
        f"26–40 級的前置是「{H(o.castle_name, terms)}」同級。"
        "消耗沒有官方資源名，表上寫成類型 999、第 4／5／6 段與數量，只錄原值，待補。"
        "0 級消耗為類型 999、第 4 段、數量 50，時間 3，戰力 0。"
        "1 級消耗為類型 999、第 4 段與第 5 段、數量各 100，時間 100，戰力 300。"
        "2 級起有第 4、5、6 段。"
        "40 級沒有消耗，也沒有時間。"
        f"第 2、3 支帕魯隊伍的解鎖說明寫在隊伍表（「{H(official_text('pal_edit_2'), terms)}」「{H(official_text('pal_edit_3'), terms)}」），不在這張升級表裡。"
    ))
    add(tbl["camp"])
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>名錄</h2>")
    add(p_html(
        f"主表 {PAL_COUNT} 筆。"
        "主表有一欄類型編號為 1–5，各 11 筆，字串表沒有這欄的中文名，不編造陣營或地圖名。"
        "品質名稱為「"
        + "、".join(H(name, terms) for name in o.qualities.values())
        + f"」（字串另有「{H(o.quality_6, terms)}」，主表 55 筆沒有這個品質）。"
        "品質分佈：普通 10、優秀 10、稀有 20、史詩 10、傳說 5。"
        "標籤分佈：冰霜 15、魔人 32、野獸 3、亡靈 5。"
        "主表沒有標籤「"
        + H(next(t.title for t in data.tags if t.tid == 5), terms)
        + "」，也沒有把標籤表裡職能類的"
        + "／".join(H(t.title, terms) for t in data.tags if t.typ == 2)
        + "寫進標籤欄。"
        "其餘欄位原值見資料說明；不把時間或賽季欄自行解釋成賽季編號或未開放。"
    ))
    add(p_html(
        "道具 80001–80055 的名稱與對應帕魯名相同。"
        "說明多數為「可用來啟用○○帕魯，同時也是帕魯升星和融合的材料。」"
        "其中 80043（"
        + H(next(p.name for p in data.pals if p.item == 80043), terms)
        + "）、80052（"
        + H(next(p.name for p in data.pals if p.item == 80052), terms)
        + "）兩條寫「素材」而不是「材料」，照錄不改。"
        "這 55 個道具編號以及 519、522、163001–163008、163101 在道具表裡對不上可用的列，名稱與說明一律取自字串表。"
        "下表「"
        + H(official_text("pal_detail_1"), terms)
        + "」是升星表英雄加成屬性的名稱與 0 星原值（各星為 0 星原值乘以 星+1，見升星節）。"
    ))
    add(tbl["catalog"])
    add(p_html(
        "字串表另有 20 個名稱與對應道具名（道具 80056–80075），"
        "這些名稱不在這 55 筆主表裡，也不在升星表，不把它們算進本名錄，也不因此標未開放或已實裝。"
        "對應關係依道具名稱與帕魯名稱字串相同來並列："
    ))
    add(tbl["extras"])
    add("    </section>")

    add('    <section id="tags">')
    add("      <h2>標籤</h2>")
    add(p_html(
        "標籤表 9 筆。"
        "一類說明寫「與其他○○帕魯同時上陣可獲得屬性加成」；另一類是職能說明。"
        "主表標籤只用到前四種元素標籤。光環表按主表類型編號 1–5 計同種族隻數，不是按這組元素標籤計，見光環節。"
    ))
    add(tbl["tags"])
    add("    </section>")

    add('    <section id="catch">')
    add("      <h2>捕捉與權重</h2>")
    add(p_html(
        "捕捉參數表僅 1 筆全域設定。"
        f"官方說明標題是「{H(official_text('pal_catch_intro_title'), terms)}」。"
        "以下先照錄說明；表上沒有標成百分比的欄，不自行換算。"
        "說明字串若已寫出百分比，仍只照錄字串，不用原值去對齊成同一個數字。"
        "參數欄位名與原值見資料說明。"
    ))
    add(p_html(
        f"<strong>{H(official_text('pal_catch_intro_subtitle1'), terms)}／"
        f"{H(official_text('pal_catch_intro_subtitle1_1'), terms)}</strong>："
    ))
    add(f"<blockquote>{highlight_lines(official_text('pal_catch_intro_text1_1'), terms)}</blockquote>")
    add(p_html(f"<strong>{H(official_text('pal_catch_intro_subtitle1_2'), terms)}</strong>："))
    add(f"<blockquote>{highlight_lines(official_text('pal_catch_intro_text1_2'), terms)}</blockquote>")
    add(p_html(f"<strong>{H(official_text('pal_catch_intro_subtitle1_3'), terms)}</strong>："))
    add(f"<blockquote>{highlight_lines(official_text('pal_catch_intro_text1_3'), terms)}</blockquote>")
    add(p_html(f"<strong>{H(official_text('pal_catch_intro_subtitle2'), terms)}</strong>："))
    add(f"<blockquote>{highlight_lines(official_text('pal_catch_intro_text2'), terms)}</blockquote>")
    add(p_html(
        f"另有自動捕捉說明（「{H(official_text('pal_catch_auto_title'), terms)}」）："
    ))
    add(f"<blockquote>{highlight_lines(official_text('pal_catch_auto_text'), terms)}</blockquote>")
    add(p_html(
        f"界面另有「{H(official_text('pal_catch_auto_warrior_text'), terms)}」、"
        f"「{H(official_text('pal_catch_auto_enable_btn'), terms)}」、"
        f"「{H(official_text('pal_catch_auto_palace_btn'), terms)}」。"
        "無法發起劫掠、無法發起捕捉的提示，本頁不逐條展開。"
    ))
    add(p_html(
        "說明字串「每日可以成功劫掠3次」與表上成功劫掠次數上限 3 數字相同；"
        "「以及30%的紅水晶」是說明字串裡已寫出的百分比，表上對應欄仍只記 3000。"
        "開放相關欄的原值只照錄，不對成賽季號。"
        "每次捕捉數量、機率等與「每採滿一定數量的紅水晶就有機率捕捉」的確切對應，表沒有標註，見資料說明。"
        "若干獎勵圖示與資源編號在字串表沒有對應名稱。"
    ))
    add(p_html("相關郵件標題與正文："))
    add(tbl["mails"])
    add(p_html(
        "權重表 30 筆。第一組 20 筆：獎勵編號 604011101–604011110 的權重各為 900，604011111–604011120 的權重各為 100。"
        "第二組 10 筆：獎勵編號同樣是 604011111–604011120，權重皆為 100。"
        "這些獎勵編號在字串表沒有名稱或說明，本頁不把它們自行對成普通或優秀品質。"
        "兩組與捕捉參數欄的對應見資料說明。"
    ))
    add(tbl["rolls"])
    add("    </section>")

    add('    <section id="fuse">')
    add("      <h2>融合</h2>")
    add(p_html(
        f"官方融合說明標題「{H(official_text('pal_info_title'), terms)}」，分頁為「"
        + "」「".join(H(official_text(f"pal_info_tab_{i}"), terms) for i in range(1, 4))
        + "」。"
    ))
    add(p_html(f"{H(official_text('pal_info_tab_1'), terms)}："))
    add(f"<blockquote>{highlight_lines(official_text('pal_info_1'), terms)}</blockquote>")
    add(p_html(f"{H(official_text('pal_info_tab_2'), terms)}："))
    add(f"<blockquote>{highlight_lines(official_text('pal_info_2'), terms)}</blockquote>")
    add(p_html(f"{H(official_text('pal_info_tab_3'), terms)}："))
    add(f"<blockquote>{highlight_lines(official_text('pal_info_3'), terms)}</blockquote>")
    add(p_html(
        "融合表 4 筆，對應品質普通到史詩。權重原值為 4500／3500／2500／1500，只錄原值，不用來對齊說明字串裡的百分比。"
        "幸運值為 1／3／10／50，與幸運值說明裡的數字相同。"
        f"主表沒有品質「{H(o.qualities[5], terms)}」或「{H(o.quality_6, terms)}」的融合列。"
        "其餘欄位原值見資料說明。"
    ))
    add(tbl["fuses"])
    g519 = o.goods[519]
    add(p_html(
        f"道具 519 名稱「{H(g519.name, terms)}」，說明：「{H(g519.desc, terms)}」。"
        "界面另有「"
        + "」「".join(
            H(official_text(k), terms)
            for k in (
                "pal_fuse_02", "pal_fuse_03", "pal_fuse_04", "pal_fuse_05",
                "pal_fuse_06", "pal_fuse_01", "pal_fusion_4", "pal_fusion_5",
            )
        )
        + "」。"
    ))
    add("    </section>")

    add('    <section id="teams">')
    add("      <h2>隊伍與位置</h2>")
    add(p_html(
        "隊伍表 3 筆，每隊 6 人。"
        f"第 1 隊說明{MISSING_TEXT}。"
        f"第 2 隊說明「{H(official_text('pal_edit_2'), terms)}」，"
        f"第 3 隊說明「{H(official_text('pal_edit_3'), terms)}」。"
        "前置欄原值見資料說明。"
    ))
    add(tbl["teams"])
    add(p_html(
        "站位表 18 筆，三隊各 6 個站位，站位含義字串表沒有內容。"
        "編輯界面字串："
        f"「{H(official_text('pal_edit_6'), terms)}」；"
        f"「{H(official_text('pal_edit_9'), terms)}」；"
        f"「{H(official_text('pal_edit_12'), terms)}」；"
        f"「{H(official_text('pal_edit_4'), terms)}」；"
        f"「{H(official_text('pal_edit_5'), terms)}」；"
        f"「{H(official_text('pal_edit_1'), terms)}」／"
        f"「{H(official_text('pal_edit_8'), terms)}」／"
        f"「{H(official_text('pal_edit_13'), terms)}」。"
        "列表狀態有「"
        + "」「".join(H(official_text(f"pal_list_{i}"), terms) for i in range(2, 5))
        + "」。詳情頁標題有「"
        + "」「".join(H(official_text(f"pal_detail_{i}"), terms) for i in range(1, 7))
        + "」；後兩項文案同為「"
        + H(official_text("pal_detail_5"), terms)
        + "」。"
    ))
    add(tbl["teampos"])
    add("    </section>")

    add('    <section id="star">')
    add("      <h2>升星</h2>")
    add(p_html(
        "升星表 330 筆，每隻 6 列，星級 0–5，55 隻都有、沒有缺列。"
        "消耗欄全表為 1，沒有寫道具編號。對應帕魯的道具說明寫「同時也是帕魯升星和融合的材料」（80043、80052 為「素材」）；0 星列的消耗同樣為 1。"
        f"界面有「{H(official_text('pal_detail_4'), terms)}」「{H(official_text('pal_detail_3'), terms)}」「{H(official_text('pal_detail_5'), terms)}」，"
        f"以及「{H(official_text('pal_not_enough'), terms)}」。"
        f"另有道具 163101 名稱「{H(o.goods[163101].name, terms)}」，說明「{H(o.goods[163101].desc, terms)}」。"
        f"主表與升星表都沒有品質「{H(o.quality_6, terms)}」的列。"
        "其餘欄位原值見資料說明。"
    ))
    add(p_html("戰力只依品質分組，同一品質 55 筆裡同星的值全部相同："))
    add(tbl["powers"])
    add(p_html(
        "英雄加成屬性每隻只掛一種，六個星級的原值為 0 星原值的 1–6 倍。0 星原值見名錄。"
        f"這一欄用到的官方名是「{H(data.attr_names[3], terms)}」「{H(data.attr_names[4], terms)}」，以及"
        f"{H(data.attr_names[3003], terms)}／{H(data.attr_names[4003], terms)}／{H(data.attr_names[5003], terms)}、"
        f"{H(data.attr_names[3004], terms)}／{H(data.attr_names[4004], terms)}／{H(data.attr_names[5004], terms)}。"
        "只錄原值。"
    ))
    add(p_html(
        f"戰鬥屬性全表都是「{H(data.attr_names[3], terms)}」與「{H(data.attr_names[4], terms)}」。"
        "同一隻在 1–5 星的攻擊、生命值，分別是 0 星原值再加 0 星原值的 10%、20%、30%、40%、50%。"
        "生命值都是整數。攻擊若出現非整數，表上記的是四捨五入後的整數（例如 0 星攻擊 375，1 星為 413，2 星為 450）。"
        "本頁以表上原值為準，不另用公式改寫。各隻 0 星與 5 星如下。"
    ))
    add(tbl["stars"])
    add(p_html(
        "技能數量與各星等級只依品質，55 隻同一品質的曲線全部相同。"
        "技能本身每隻不同，見技能節。這批技能最高 2 級，各星只出現 1 或 2 級："
    ))
    add(tbl["skill_levels"])
    node_bits = []
    curves = tbl["skill_curves"]
    quality_order = sorted(curves)
    for q in quality_order:
        nodes = _upgrade_nodes(curves[q]["levels"])
        node_bits.append(H(o.qualities[q], terms) + "：" + "、".join(nodes))
    add(p_html("由此讀出各段技能升至 2 級的星級：" + "；".join(node_bits) + "。"))
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>技能</h2>")
    add(p_html(
        "下列每隻先寫技能名稱，再寫基礎效果與升至 2 級的追加說明。"
        "這批技能最高 2 級。參數已代入。百分比是官方文案用字，不是本頁用表上原值換算的。"
        "技能編號見資料說明。"
    ))
    for pal in data.pals:
        add(f'      <h3 id="pal-{pal.pid}">{H(pal.name, terms)}</h3>')
        add("<ul>")
        for skill in pal.skills:
            add(_skill_block(skill, terms))
        add("</ul>")
    add("    </section>")

    add('    <section id="aura">')
    add("      <h2>光環</h2>")
    add(p_html(
        "光環表 15 筆。"
        f"官方標題是「{H(official_text('pal_aura_8'), terms)}」，"
        f"另寫「{H(official_text('pal_aura_7'), terms)}」。"
        f"說明寫「{H(official_text('pal_aura_4'), terms)}」"
        "（5、6 隻同此句式，隻數改為 5 或 6）。"
        "光環按主表類型編號 1–5 計同種族隻數，不是按元素標籤計。本頁不把 1–5 自行寫成種族中文名。"
    ))
    add(p_html(
        f"15 筆的屬性都是「{H(data.attr_names[62], terms)}」與「{H(data.attr_names[63], terms)}」，只錄原值。"
        "同一隻數的五個類型原值完全相同：4 隻各 1500，5 隻各 2500，6 隻各 3500。"
    ))
    add(tbl["auras"])
    add("    </section>")

    add('    <section id="materials">')
    add("      <h2>材料與道具</h2>")
    add(p_html(
        "名稱、說明一律取自官方字串表。道具表對不上這些編號的可用列，見名錄節。"
        "80001–80055 見名錄；80056–80075 見名錄後未入冊的 20 個名稱。"
        f"163002 與 163004 名稱同為「{H(o.goods[163002].name, terms)}」，"
        f"163003 與 163005 名稱同為「{H(o.goods[163003].name, terms)}」；"
        "163002／163003／163006 的說明是「獲得一個○○品質的隨機帕魯。」，"
        "163001／163007／163008 的說明是「獲得隨機○○帕魯信物」，"
        "163004、163005 的說明字串表沒有內容。"
        f"163006 與 163007 名稱同為「{H(o.goods[163006].name, terms)}」，說明用字不同"
        f"（前者「{H(o.goods[163006].desc, terms)}」，後者「{H(o.goods[163007].desc, terms)}」）。"
    ))
    add(tbl["materials"])
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(
        "<li>寵物（見已發佈的<a href=\"pets.html\">"
        + H("寵物總表", terms)
        + "</a>）、守護魔獸（見已發佈的<a href=\"holybeasts.html\">"
        + H("守護魔獸總表", terms)
        + "</a>）、英靈（見已發佈的<a href=\"valhalla.html\">"
        + H("英靈總表", terms)
        + "</a>）。</li>"
    )
    add("<li>一張內容為地圖實例、未繫在帕魯表上的地圖表（檔名見資料說明）。</li>")
    add("<li>字串表有、但不在主表或升星表的 20 個名稱與道具 80056–80075；不把它們算進名錄，也不標未開放。</li>")
    add("<li>升星 330 筆的逐列全表；本頁改寫規則、0 星／5 星原值與技能文案。</li>")
    add("<li>權重表的獎勵編號 604011101–604011120，以及捕捉參數裡若干獎勵圖示與資源編號：字串表沒有名稱。</li>")
    add("<li>主表類型編號 1–5 的中文名；站位 1–6 的含義；升級消耗類型 999、第 4／5／6 段的資源名稱。</li>")
    add("<li>每次捕捉數量、捕捉機率、營地「提高捕獲帕魯的機率」與說明文案「每採滿一定數量的紅水晶就有機率捕捉」之間的確切對應。</li>")
    add("<li>亂鬥活動說明（字串表沒有內容）；亂鬥的獨立對戰、積分與排名獎勵數值表。</li>")
    add("<li>道具表的可用道具列（本批該檔為欄位序號殘件）。</li>")
    add("<li>時間、賽季與伺服器欄與賽季日曆或顯示伺服器的對應（不標未開放，不斷言顯示伺服器編號等於表上區間）。</li>")
    add("<li>與英雄技能、站位的搭配模擬，以及把屬性原值或官方百分比文案代入之後的戰鬥結算。不編造閉合戰鬥公式，不評定強弱或養成順序。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(_data_notes(data)))
    add(p_html(
        "以下補錄正文改寫後移入的欄位名與原值，只照錄，不另行對成賽季號或系統名。"
        "主表與升星表的 season 皆為 0。主表沒有 unlocktime。主表 unlocknum 皆為 1，weight 皆為 100，"
        "damage_volume／volume／model_scale 皆為 -1。tag 與 tagInt 數值一致（1–4）。"
        "unit_id 與技能 id 前綴一致。team_scale 只錄原值，字串表沒有這一欄的名稱。"
        "名稱來自主表 palname_* 鍵。字串表另有 20 條 palname_* 與 goods_name_80056–goods_name_80075，不在 pal.json 的 55 筆裡。"
        "主表 type 為 1–5，字串表沒有這欄的中文名；"
        "<code>pal_type_1</code> 至 <code>pal_type_5</code> 是標籤「"
        + "、".join(H(t.title, terms) for t in data.tags if t.typ == 1 and t.tag_id <= 5)
        + "」，不是 type 欄的名稱，不編造陣營或地圖名。"
        "品質用 pal_quality_{n}；字串另有 pal_quality_6。"
    ))
    add(p_html(
        f"影響力目錄項 id 32100，名稱鍵 <code>pal_list_1</code>，type_name 為 <code>PAL</code>，jump 為 {JUMP_ID}。"
        f"jump.json {JUMP_ID} 的 name／desc 為空，go_target 為空，task_guide 為 {e(str(data.jump.get('task_guide')))}，"
        f"city_lv 為 {e(str(data.jump.get('city_lv')))}，season 為空。"
        f"function.json id {FUNCTION_ID} 的開啟面板是 <code>{e(func.get('openPanel'))}</code>，"
        f"func_open_param 為 <code>{e(func.get('func_open_param'))}</code>"
        f"（117 的官方名稱是「{H(o.castle_name, terms)}」），"
        f"condition_type 為 {e(str(func.get('condition_type')))}、value 為 {e(str(func.get('value')))}（{H(o.camp_name, terms)}）。"
        "名稱欄為空，字串表沒有對應內容。"
    ))
    add(p_html(
        f"建築 {BUILDING_INDEX} 的 maxlevel／new_maxlevel 皆為 {e(str(b.get('maxlevel')))}。"
        f"主表 season_range_1 為 <code>{e(b.get('season_range_1'))}</code>，"
        f"open_season_day 為 <code>{e(raw_json(b.get('open_season_day')))}</code>，只照錄。"
        f"建造費用欄 costs 為 <code>{e(raw_json(b.get('costs')))}</code>。"
        "citybuilding_lvup.json 與 citybuilding_lvup_new.json 同一建築的這 41 筆，在兩表共有欄位上相同。"
        "des 全為空。string_para1 全為空。"
        "0 級沒有 string_para2；1–40 級的 string_para2 為 1249|{n}|1，n 從 100 起每級加 100，至 40 級為 4000。"
        "1249 的 show_type 為 2。"
        "捕捉參數表的 pal_catch_chance=6000 與營地 1249 不是同一欄。"
    ))
    add(p_html(
        "0–25 級的 pre_building_level 皆為 <code>117|25</code>；"
        "26–40 級分別為 <code>117|26</code> 至 <code>117|40</code>（表上是各級的具體值，不是寫成 117|{該級} 的省略）。"
        "0 級 cost1 為 <code>[999, 4, 50]</code>，沒有 cost2／cost3，buildTime 為 3，fightforce 為 0。"
        "1 級 cost1／cost2 為 <code>[999, 4, 100]</code>／<code>[999, 5, 100]</code>，沒有 cost3，buildTime 為 100，fightforce 為 300。"
        "2 級起有 cost1／cost2／cost3（第三段為 <code>[999, 6, …]</code>）。"
        "40 級沒有 cost1–cost4，也沒有 buildTime（表上 buildTime 為 -1）。"
        "999 與 4／5／6 在字串表沒有對應的道具或資源名稱。"
    ))
    add(p_html(
        f"活動名稱鍵 pal_catch_title。兩列："
        f"id 5002001（type {e(str(catch1.get('type')))}，is_open {e(str(catch1.get('is_open')))}，"
        f"season {e(str(catch1.get('season')))}，condition 為 <code>{e(catch1.get('condition'))}</code>，"
        f"take_effect_time 為 <code>{e(catch1.get('take_effect_time'))}</code>，"
        f"server_list 為 <code>{e(catch1.get('server_list'))}</code>，"
        f"form_list 為 <code>{e(catch1.get('form_list'))}</code>，"
        f"info／faq 為 {e(str(catch1.get('info')))}，與捕捉參數表 activity_info／activity_desc 對得上）；"
        f"id 5002002（type {e(str(catch2.get('type')))}，is_open {e(str(catch2.get('is_open')))}，"
        f"season {e(str(catch2.get('season')))}，condition 同樣為 <code>{e(catch2.get('condition'))}</code>，"
        f"take_effect_time 為 <code>{e(catch2.get('take_effect_time'))}</code>，"
        f"server_list 為 <code>{e(catch2.get('server_list'))}</code>，"
        f"form_list 為 <code>{e(catch2.get('form_list'))}</code>）。"
        f"活動「{H(o.arena_name, terms)}」五列：名稱鍵 activity_name_5001022，describe 皆為 activity_desc_5001022（字串表沒有內容），"
        "type 皆為 10089，season 皆為 5，condition 皆為 <code>2|117|12</code>，"
        "info／faq 皆為 35013，form_list 皆為 208。各列 is_open、take_effect_time、server_list 如下："
    ))
    add(tbl["notes_arena"])
    add(p_html(
        "預告標題鍵 season_preview_title_406，說明鍵 season_preview_desc_413，紀念文案鍵 season_memo_s2_photo1_text3。"
        "只照錄鍵名與正文，不把鍵名裡的數字或 s2 自行對成賽季號。"
    ))
    add(p_html("pal_catch_param 表上原值（欄位名照錄）："))
    add(tbl["notes_catch"])
    add(p_html(
        "crystal_pal_reward_weight_id=1、guild_pal_reward_weight_id=2 對應權重表的 group_id。"
        "crystal_pal_reward_icon／palace_pal_reward_icon、alliance_resource_id、other_kingdom_reward_id、ocean_server_march_gate_id 在字串表沒有對應名稱。"
        "無法發起劫掠、無法發起捕捉的提示字串鍵為 pal_catch_cant_loot_*、pal_catch_cant_*，本頁不逐條展開。"
    ))
    add(p_html("郵件欄位、id 與字串鍵："))
    add(tbl["notes_mails"])
    add(p_html(
        "融合表 sameweight 全為 -1，luckcost 為空，luckCostArray 為 <code>[]</code>。"
        "隊伍表 type 為 1，conditon（表上的拼法）為 1，para 皆為 <code>183|0</code>。"
        "站位表 conditon 皆為 1，para、desc 皆為空。標籤表欄位名是 titile（表上的拼法）。"
        "升星表 season 全表為 0；attrdesc 全為空，字串表沒有內容。"
        "combatattr 的 3／4 與 generalattr 的 3003／4003／5003、3004／4004／5004、以及部分列的 3／4，show_type 皆為 1。"
        "光環的 62／63 與營地升級的 1249，show_type 為 2。"
        "技能表 desc1 是基礎效果，desc2 是升至 2 級的追加說明；這批帕魯技能沒有 desc3–desc5。名稱鍵與技能 id 不必相同。"
        "詳情頁 pal_detail_5 與 pal_detail_6 文案相同。"
        "各隻技能 id 如下。"
    ))
    skill_bits = []
    for pal in data.pals:
        ids = "、".join(str(s.sid) for s in pal.skills)
        skill_bits.append(f"{H(pal.name, terms)}（{pal.pid}）：{ids}")
    add(p_html("；".join(skill_bits) + "。"))
    add(p_html("光環表 require、說明鍵與屬性原值："))
    add(tbl["notes_auras"])
    add(p_html(
        "光環 require 寫成 a|b：左欄為 1–5，與主表 type 相同；右欄為 4、5 或 6。"
        "說明鍵 pal_aura_4／pal_aura_5／pal_aura_6。"
        "本頁不收 map_slg_underpalace.json（檔名含 pal，內容是地圖實例，沒有繫在帕魯系統上）。"
    ))
    add("<ul>")
    add(
        "<li>定義在 <code>pal.json</code>（55 筆），捕捉全域在 <code>pal_catch_param.json</code>（1 筆），"
        "融合在 <code>pal_fuse.json</code>（4 筆），捕捉權重在 <code>pal_roll_weight.json</code>（30 筆），"
        "標籤在 <code>pal_tag.json</code>（9 筆），隊伍在 <code>pal_team.json</code>（3 筆）與 <code>pal_teampos.json</code>（18 筆），"
        "升星在 <code>pal_star.json</code>（330 筆，每隻 0–5 星共 6 列，只在 LocalLow），"
        "光環在 <code>pal_aura.json</code>（15 筆，只在 LocalLow）。"
        "升星表列出的技能 id 全部能在 <code>hero_component.json</code> 對上（155 個 id，maxlv 皆為 2）。"
        "名稱來自主表 <code>palname_*</code> 鍵。</li>"
    )
    add(
        "<li>待補：reward_id 604011101–604011120 的實際開出內容；type 1–5 若日後有官方名稱；"
        "升星 cost 與道具 id 的對應（表上只有數字 1）；"
        "pal_per_catch_amount／pal_catch_chance／屬性 1249 與捕捉說明的對應；"
        "亂鬥對戰與獎勵表；goods.json 可用列若之後有完整匯出；"
        "163004／163005 的說明；以及 20 個未入冊名稱若進入 pal.json 後的補錄；"
        "升級消耗欄 999 與 4／5／6 的官方資源名；站位 type 1–6 的含義。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_pal_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())
