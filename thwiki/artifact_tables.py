"""Compile the published 秘寶 catalog tables."""

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


# 秘寶總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫 2026-11-23。
ARTIFACT_DATA_CUTOFF = "2026-11-23"
ARTIFACT_DATA_PACK = "app-1.129.12_table-1.0.43173"
ARTIFACT_DATA_PACKED = "2026-11-22 23:33"

TABLE_SHA256 = {
    "artifact.json": "87fca3b16ad59381a8336b98fc9c3fdd32fc1c833d4f6fd5177bcf021213f433",
    "artifact_star_up.json": "e8205f7e91ffd5f0f0c3e6036a11ff2ef6fdc7a7b7f1195f53100d5510e04bb6",
    "artifact_suit.json": "b2141a0cd4e00645a80e774f431b09ad6e94e982f710d3f6507a824452bc360e",
    "artifact_honor.json": "4ceb8be445b784dbf2ac6413e672efeddf6c7c90e5bdb5398e69b14fe5b6730b",
    "artifact_honor_bonus.json": "60134b4ba7b33418b185e461d789c1633bcb48abe32101f591894022d57efc8c",
    "artifact_skill_attr.json": "6fd8b56f2bb9cefc0aa749fd504e44b4282120bc962af390eea76962701d7d60",
    "citybuilding_lvup.json": "2d85b94154e3a0f6f481805d49bace3e8ee8eccd84dfae79ac938743e75724d3",
    "citybuilding_lvup_new.json": "436ca7dcdba0f5aa962cfbbb728fd4b9d9ac3a3042154a2ec3e5c43a60158abf",
}

HALL_INDEX = 140
HALL_KEY_LEVELS = (0, 1, 20, 21, 35, 40, 50, 150, 200, 2076)
# lv -> (para1, para2, slot, fightforce)
HALL_EXPECTED = {
    0: (0, 0, 0, 0),
    1: (1000, 1, 0, 100),
    20: (1150, 20, 0, 10850),
    21: (1200, 21, 1, 13100),
    35: (1350, 35, 2, 82300),
    40: (1400, 40, 2, 140750),
    50: (1400, 42, 2, 141750),
    150: (1600, 63, 2, 151750),
    200: (1700, 71, 2, 156750),
    2076: (3440, 199, 2, 396950),
}
HALL_NOTES = {
    0: "前置城堡 12 級",
    20: "官方寫此級解鎖額外位置；表上插槽仍為 0",
    21: "表上插槽改為 1",
    35: "表上插槽改為 2",
    40: "此級起消耗改為魔紋石／奧術水晶，前置城堡欄為空",
    50: "官方寫此級解鎖額外位置；表上插槽在 35 級已是 2",
    150: "榮譽牆解鎖字串寫此級",
    2076: "滿級，無再升級消耗",
}

# 品質 2 version=1 per-star qty by inclusive star band; version=-1 differs from 41 星.
Q2_V1_BANDS = (
    ((1, 5), 2), ((6, 10), 4), ((11, 15), 6), ((16, 20), 8), ((21, 25), 10),
    ((26, 30), 12), ((31, 35), 14), ((36, 40), 16), ((41, 45), 20), ((46, 50), 30),
    ((51, 55), 40), ((56, 60), 50), ((61, 65), 60), ((66, 70), 100), ((71, 75), 120),
    ((76, 80), 70), ((81, 85), 80), ((86, 90), 90), ((91, 95), 110), ((96, 100), 130),
)
Q2_VM1_DIFF = {41: 18, 46: 20, 66: 70, 71: 80}  # start of 5-star band -> qty
Q3_BANDS = (
    ((1, 5), 2), ((6, 10), 4), ((11, 15), 6), ((16, 20), 8), ((21, 25), 10),
    ((26, 30), 12), ((31, 35), 14), ((36, 40), 16), ((41, 45), 18), ((46, 50), 20),
    ((51, 55), 30), ((56, 60), 40), ((61, 65), 50), ((66, 70), 60), ((71, 75), 80),
    ((76, 80), 30), ((81, 85), 40), ((86, 90), 50), ((91, 95), 60), ((96, 100), 80),
)
Q4_BANDS = (
    ((1, 5), 2), ((6, 15), 4), ((16, 25), 8), ((26, 35), 12),
    ((36, 50), 16), ((51, 60), 20), ((61, 65), 26), ((66, 100), 28),
)
Q2_V1_TOTAL = 4860
Q2_VM1_TOTAL = 4450
Q3_TOTAL = 3150
Q4_TOTAL = 1800

# 0/100 star self atk/hp and hero 103/104, plus fightforce v1 / v-1.
# 品質 4 0-star atk/hp is 2780／19100 in the table (source prose 3530／23600 is not in the star-up rows).
ATTR_SUMMARY = {
    2: {"atk0": 340, "hp0": 2300, "atk100": 8650, "hp100": 57700,
        "h0": (5, 10), "h100": (600, 1200), "ff0": (11400, 4000), "ff100": (288400, 150400)},
    3: {"atk0": 1060, "hp0": 7100, "atk100": 25990, "hp100": 173300,
        "h0": (20, 40), "h100": (1200, 2400), "ff0": (35400, 5000), "ff100": (866400, 179500)},
    4: {"atk0": 2780, "hp0": 19100, "atk100": 65180, "hp100": 435400,
        "h0": (15, 30), "h100": (2000, 4000), "ff0": (93800, 7500), "ff100": (2174400, 293500)},
}

TYPE_ORDER = {1: "進攻", 2: "生存", 3: "通用"}
EMPTY = "—"

LEDE = (
    "本頁列出可佩戴到隊列上的秘寶：兩套編號、29 個中文名錄、秘寶大廳關鍵級、升星消耗與 0 星／100 星屬性、"
    "表列套裝、榮譽牆，以及各件 0 星與 100 星技能原文。英雄裝備、專武與領主裝備都不是秘寶，本頁只交叉引用。"
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
    out: dict[int, int] = {}
    if raw in (None, "", [], {}, -1):
        return out
    if isinstance(raw, dict):
        for k, v in raw.items():
            out[_int(k)] = _int(v)
        return out
    if isinstance(raw, list):
        if raw and isinstance(raw[0], (list, tuple)) and len(raw[0]) >= 2:
            for item in raw:
                out[_int(item[0])] = _int(item[1])
            return out
        for item in raw:
            s = str(item)
            if "|" in s:
                a, b = s.split("|", 1)
                out[_int(a)] = _int(b)
        return out
    for part in str(raw).split(","):
        if "|" in part:
            a, b = part.split("|", 1)
            out[_int(a)] = _int(b)
    return out


def parse_slot(raw) -> int:
    text = ""
    if isinstance(raw, list) and raw:
        text = str(raw[0])
    elif raw not in (None, "", -1):
        text = str(raw)
    parts = text.split("|")
    if len(parts) >= 2 and _int(parts[0]) == 1097:
        return _int(parts[1])
    raise ValueError(f"unexpected string_para2: {raw!r}")


def parse_cost_pair(raw) -> tuple[int, int, int] | None:
    if raw in (None, "", [], -1):
        return None
    if isinstance(raw, list) and len(raw) >= 3:
        return _int(raw[0]), _int(raw[1]), _int(raw[2])
    return None


def star_cost(row: dict) -> tuple[int, int] | None:
    raw = row.get("star_up_cost")
    if raw in (None, "", [], -1):
        return None
    if isinstance(raw, list) and len(raw) >= 2 and not isinstance(raw[0], (list, tuple)):
        return _int(raw[0]), _int(raw[1])
    if isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
        item = raw[0]
        return _int(item[0]), _int(item[1])
    raise ValueError(f"unexpected star_up_cost: {raw!r}")


def band_total(bands) -> int:
    return sum((hi - lo + 1) * qty for (lo, hi), qty in bands)


def qty_at(bands, star: int) -> int:
    for (lo, hi), qty in bands:
        if lo <= star <= hi:
            return qty
    raise KeyError(star)


def format_params(params) -> str:
    if params in (None, "", [], -1):
        return "無"
    return "[" + ", ".join(fmt_num(x) for x in params) + "]"


def format_unlock_stars(raw) -> str:
    """Turn 0|4|7|11 into 0、4、7、11 星; two sets joined by comma become 另一套."""
    if raw in (None, "", [], -1):
        return EMPTY
    text = str(raw).strip()
    if not text:
        return EMPTY

    def one(seg: str) -> str:
        nums = [x for x in seg.split("|") if x != ""]
        if not nums:
            return seg
        return "、".join(nums) + " 星"

    parts = [x.strip() for x in text.split(",") if x.strip()]
    if len(parts) == 1:
        return one(parts[0])
    if len(parts) == 2:
        return f"{one(parts[0])}；另一套 {one(parts[1])}"
    return "；".join(one(x) for x in parts)


def format_season(raw) -> str:
    if raw in (None, "", [], -1):
        return EMPTY
    if isinstance(raw, list):
        return ", ".join(fmt_num(x) for x in raw)
    return str(raw)


def attr_label(attr_id: int, attr_by: dict) -> str:
    name = official_text(f"attribute_name_{attr_id}")
    if name:
        return name
    row = attr_by.get(int(attr_id)) or {}
    return official_text(row.get("name") or "")


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


def skill_fill(desc_keys, params) -> tuple[list[str], list[str], bool]:
    """Return (filled_lines, original_templates, show_originals)."""
    if desc_keys in (None, "", [], -1):
        return ["（無技能說明）"], [], False
    keys = desc_keys if isinstance(desc_keys, list) else [desc_keys]
    plist = list(params or [])
    filled: list[str] = []
    originals: list[str] = []
    unfilled = False
    for key in keys:
        tmpl = official_text(key) if key else ""
        originals.append(tmpl)
        filled.append(fill_skill_segment(tmpl, plist))
        for m in re.finditer(r"\{(\d+)\}", tmpl):
            i = int(m.group(1))
            if i >= len(plist) or plist[i] in (None, ""):
                unfilled = True
    show = len(keys) > 1 or unfilled
    return filled, originals, show


def p_html(body: str) -> str:
    return f"<p>{body}</p>"




@dataclass
class SkillSnapshot:
    star: int
    level: int
    show_level: int
    name: str
    name_key: str
    params: list | None
    filled: list[str]
    originals: list[str]
    show_originals: bool
    name_is_artifact: bool


@dataclass
class ArtifactInfo:
    name: str
    id_v1: int
    id_vm1: int
    quality: int
    typ: int
    type_name: str
    group_id: int
    season: str
    unlock: str
    desc: str
    desc_missing: bool
    fragment_id: int
    exchange_goods: int
    skill_attr_type: int
    skill0: SkillSnapshot
    skill100: SkillSnapshot
    extra0: dict[int, int]
    extra100: dict[int, int]
    hero0: tuple[int, int]
    hero100: tuple[int, int]
    atk0: int
    hp0: int
    atk100: int
    hp100: int
    ff0_v1: int
    ff0_vm1: int
    ff100_v1: int
    ff100_vm1: int
    suit_origin: int


@dataclass
class SuitInfo:
    name: str
    race: int
    race_name: str
    id_v1: int
    id_vm1: int
    members: list[str]
    member_ids_v1: list[int]
    desc: str
    skill_star: int


@dataclass
class HallLevel:
    lv: int
    para1: int
    para2: int
    slot: int
    fightforce: int
    note: str
    string_para1: str
    pre: str
    cost: str


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


@dataclass
class Official:
    system_name: str
    rules: str
    rules_new: str
    info: dict[str, str]
    buff_desc: str
    name_dec: str
    hall_name: str
    hall_des: str
    honour_unlock: str
    honour_lines: dict[str, str]
    atk_up: str
    hp_up: str
    attr_up: str
    typo_des: str
    wrong_des: str
    type_names: dict[int, str]
    type_descs: dict[int, str]
    same_type_tips: str
    wood: str
    stone: str
    hammer: str
    hammer_desc: str
    magic_stone: str
    arcane: str
    castle: str
    races: dict[int, str]
    slot_name: str
    art_atk: str
    art_hp: str
    hero_atk: str
    hero_hp: str
    dmg_up: str
    dmg_cut: str
    atk: str
    hp: str
    swap_tips: str
    frog_totem_descs: tuple[str, str]
    power_suit_name: str
    power_suit_desc: str
    suit_unlock: tuple[str, str]
    generic_chips: dict[int, tuple[str, str]]
    chip_descs_example: tuple[str, str]


@dataclass
class TablesData:
    official: Official
    artifacts: list[ArtifactInfo]
    suits: list[SuitInfo]
    hall: list[HallLevel]
    honor: list[HonorRow]
    honor_bonus: list[HonorBonus]
    terms: list[str] = field(default_factory=list)
    verifications: dict = field(default_factory=dict)
    table_meta: dict = field(default_factory=dict)


def _q2_vm1_qty(star: int) -> int:
    for start, qty in Q2_VM1_DIFF.items():
        if start <= star <= start + 4:
            return qty
    return qty_at(Q2_V1_BANDS, star)


def _self_and_hero(row: dict) -> tuple[dict[int, int], dict[int, int]]:
    self_map = parse_attr_map(row.get("attribute")) or parse_attr_map(row.get("AttributeArr"))
    hero_map = parse_attr_map(row.get("attribute_all")) or parse_attr_map(row.get("AttributeHeroArr"))
    return self_map, hero_map


def _snapshot(row: dict, artifact_name: str) -> SkillSnapshot:
    filled, originals, show = skill_fill(row.get("skill_desc"), row.get("skill_desc_parameter"))
    name_key = row.get("skill_name") or ""
    name = official_text(name_key) if name_key else ""
    return SkillSnapshot(
        star=_int(row["star"]),
        level=_int(row["level"]),
        show_level=_int(row["skillShowLevel"]),
        name=name,
        name_key=str(name_key),
        params=None if row.get("skill_desc_parameter") in (None, -1) else list(row.get("skill_desc_parameter") or []),
        filled=filled,
        originals=originals,
        show_originals=show,
        name_is_artifact=bool(name) and name == artifact_name,
    )


def _compare_string_packs(keys: set[str]) -> dict:
    packs = {
        "live": STRINGS_PATH,
        "2026-11-05": TOPHEROES_ROOT / "extracts/2026-11-05/strings_zh.json",
        "2026-11-22": TOPHEROES_ROOT / "extracts/2026-11-22/strings_zh.json",
        "2026-11-22-locallow": TOPHEROES_ROOT / "extracts/2026-11-22-locallow/strings_zh.json",
    }
    loaded: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for name, path in packs.items():
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


def _hall_cost_label(row: dict, official: Official) -> str:
    c1 = parse_cost_pair(row.get("cost1"))
    c2 = parse_cost_pair(row.get("cost2"))
    if c1 is None and c2 is None:
        return "無再升級消耗"
    parts = []
    for c in (c1, c2):
        if not c:
            continue
        typ, gid, qty = c
        if typ == 999 and gid == 4:
            parts.append(f"{official.wood} {qty}")
        elif typ == 999 and gid == 5:
            parts.append(f"{official.stone} {qty}")
        elif typ == 2 and gid == 237:
            parts.append(f"{official.magic_stone} {qty}")
        elif typ == 2 and gid == 238:
            parts.append(f"{official.arcane} {qty}")
        else:
            parts.append(f"{typ}|{gid}|{qty}")
    return "／".join(parts)


def load_tables_data() -> TablesData:
    USED_KEYS.clear()
    for name, expected in TABLE_SHA256.items():
        path = DATA_DIR / name
        got = file_sha256(path)
        if got != expected:
            raise ValueError(f"{name} sha256 mismatch: {got} != {expected}")

    artifacts_raw = load_table("artifact.json")
    stars_raw = load_table("artifact_star_up.json")
    suits_raw = load_table("artifact_suit.json")
    honor_raw = load_table("artifact_honor.json")
    honor_bonus_raw = load_table("artifact_honor_bonus.json")
    skill_attr_raw = load_table("artifact_skill_attr.json")
    lvup_raw = load_table("citybuilding_lvup.json")
    lvup_new_raw = load_table("citybuilding_lvup_new.json")
    attributes = load_table("attribute.json")
    attr_by = {r["id"]: r for r in attributes}

    if len(artifacts_raw) != 58:
        raise ValueError(f"artifact.json expected 58 rows, got {len(artifacts_raw)}")
    if len(stars_raw) != 5858:
        raise ValueError(f"artifact_star_up.json expected 5858 rows, got {len(stars_raw)}")
    if len(suits_raw) != 6:
        raise ValueError(f"artifact_suit.json expected 6 rows, got {len(suits_raw)}")
    if len(honor_raw) != 3:
        raise ValueError(f"artifact_honor.json expected 3 rows, got {len(honor_raw)}")
    if len(honor_bonus_raw) != 30:
        raise ValueError(f"artifact_honor_bonus.json expected 30 rows, got {len(honor_bonus_raw)}")
    if len(skill_attr_raw) != 120:
        raise ValueError(f"artifact_skill_attr.json expected 120 rows, got {len(skill_attr_raw)}")

    star_by: dict[int, dict[int, dict]] = defaultdict(dict)
    for row in stars_raw:
        star_by[_int(row["artifact_id"])][_int(row["star"])] = row
    art_by = {r["id"]: r for r in artifacts_raw}

    if {r["version"] for r in artifacts_raw} != {-1, 1}:
        raise ValueError("unexpected version set")
    if any(r["fragment_num"] != 10 for r in artifacts_raw):
        raise ValueError("fragment_num is not 10 for every row")
    if len(star_by) != 58 or any(set(star_by[i]) != set(range(101)) for i in star_by):
        raise ValueError("star table is not 58 × 0–100")

    official = Official(
        system_name=official_text("artifact_system_name"),
        rules=official_text("artifact_system_rules"),
        rules_new=official_text("artifact_system_rules_new"),
        info={f"artifact_info_{i:03d}": official_text(f"artifact_info_{i:03d}") for i in range(1, 8)},
        buff_desc=official_text("artifact_system_buff_desc"),
        name_dec=official_text("artifact_system_name_dec"),
        hall_name=official_text("citybuilding_name_140"),
        hall_des=official_text("citybuilding_des_140"),
        honour_unlock=official_text("artifact_honour_005"),
        honour_lines={k: official_text(k) for k in (
            "artifact_honour_002", "artifact_honour_003", "artifact_honour_004",
            "artifact_honour_005", "artifact_honour_006",
        )},
        atk_up=official_text("artifact_atk_up"),
        hp_up=official_text("artifact_hp_up"),
        attr_up=official_text("uilding_lvup_des_115003"),
        typo_des=official_text("uilding_lvup_des_115003"),
        wrong_des=official_text("building_lvup_des_115003"),
        type_names={i: official_text(f"artifact_type_name{i}") for i in (1, 2, 3)},
        type_descs={i: official_text(f"artifact_type_desc{i}") for i in (1, 2, 3)},
        same_type_tips=official_text("artifact_type_same_tips"),
        wood=official_text("top_resource_name_4"),
        stone=official_text("top_resource_name_5"),
        hammer=official_text("goods_name_514"),
        hammer_desc=official_text("goods_desc_514"),
        magic_stone=official_text("goods_name_237"),
        arcane=official_text("goods_name_238"),
        castle=official_text("citybuilding_name_117"),
        races={i: official_text(f"unit_race_{i}") for i in (1, 2, 3)},
        slot_name=official_text("attribute_name_1097"),
        art_atk=official_text("attribute_name_20003"),
        art_hp=official_text("attribute_name_20004"),
        hero_atk=official_text("attribute_name_103"),
        hero_hp=official_text("attribute_name_104"),
        dmg_up=official_text("attribute_name_18"),
        dmg_cut=official_text("attribute_name_19"),
        atk=official_text("attribute_name_3"),
        hp=official_text("attribute_name_4"),
        swap_tips=official_text("artifact_swap_tips1"),
        frog_totem_descs=(official_text("goods_desc_340061"), official_text("goods_desc_364006")),
        power_suit_name=official_text("ui_artifact_suit_name_04"),
        power_suit_desc=official_text("ui_artifact_suit_04"),
        suit_unlock=(official_text("ui_artifact_05"), official_text("ui_artifact_06")),
        generic_chips={
            gid: (official_text(f"goods_name_{gid}"), official_text(f"goods_desc_{gid}"))
            for gid in (220201, 220202, 220203)
        },
        chip_descs_example=(official_text("goods_desc_330011"), official_text("goods_desc_363001")),
    )
    if official.system_name != "秘寶":
        raise ValueError(f"system name drifted: {official.system_name!r}")
    if official.hall_name != "秘寶大廳" or official.hall_des != "用於管理秘寶，升級後可提高秘寶的威力":
        raise ValueError("hall name/des drifted")
    if official.atk_up != "秘寶攻擊放大率" or official.hp_up != "秘寶生命放大率":
        raise ValueError("hall des name drifted")
    if official.typo_des != "秘寶屬性轉化率":
        raise ValueError("uilding_lvup_des_115003 drifted")
    if official.wrong_des != "全體英雄防禦":
        raise ValueError("building_lvup_des_115003 drifted")
    if official.type_names != {1: "進攻", 2: "生存", 3: "通用"}:
        raise ValueError(f"type names drifted: {official.type_names}")
    if official.races != {1: "聯盟", 2: "部族", 3: "自然"}:
        raise ValueError(f"race names drifted: {official.races}")
    if official.wood != "木材" or official.stone != "石頭":
        raise ValueError("resource names drifted")
    if official.hammer != "奇蹟之錘" or official.magic_stone != "魔紋石" or official.arcane != "奧術水晶":
        raise ValueError("item names drifted")
    if official.art_atk != "秘寶攻擊" or official.art_hp != "秘寶生命":
        raise ValueError("artifact attr names drifted")
    if official.hero_atk != "英雄攻擊" or official.hero_hp != "英雄生命":
        raise ValueError("hero attr names drifted")
    if official.dmg_up != "增傷" or official.dmg_cut != "減傷":
        raise ValueError("18/19 names drifted")
    if official.atk != "攻擊" or official.hp != "生命值":
        raise ValueError("3/4 names drifted")
    if official.slot_name != "額外秘寶插槽":
        raise ValueError("slot name drifted")
    if official.honour_unlock != "需要秘寶大廳達到150級解鎖秘寶榮譽牆":
        raise ValueError("honour unlock string drifted")
    if has_key("attribute_name_20005") or has_key("attribute_name_20006"):
        raise ValueError("unexpected attribute_name_20005/20006")
    for aid, show, typ in (
        (3, 1, 1), (4, 1, 1), (18, 2, 2), (19, 2, 2), (103, 2, 2), (104, 2, 2),
        (1097, 1, 1), (20003, 1, 1), (20004, 1, 1), (20005, 1, 1), (20006, 1, 1),
    ):
        row = attr_by[aid]
        if row.get("show_type") != show or row.get("type") != typ:
            raise ValueError(f"attr {aid} show_type/type drifted: {row.get('show_type')}/{row.get('type')}")
    if attr_by[20005]["name"] != "attribute_name_20003" or attr_by[20006]["name"] != "attribute_name_20004":
        raise ValueError("20005/20006 name keys drifted")
    # attr 3/4 name columns point at 103/104; display must prefer attribute_name_{id}.
    if attr_by[3]["name"] != "attribute_name_103" or attr_by[4]["name"] != "attribute_name_104":
        raise ValueError("attr 3/4 name column unexpected")

    # pair 29 names
    by_name: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in artifacts_raw:
        name = official_text(row["name"])
        if not name:
            raise ValueError(f"missing name for {row['id']}")
        by_name[name][row["version"]] = row
    if len(by_name) != 29 or any(set(v) != {-1, 1} for v in by_name.values()):
        raise ValueError("expected 29 names each with version -1 and 1")

    artifacts: list[ArtifactInfo] = []
    q2_v1_ids = []
    for name, vers in by_name.items():
        v1, vm1 = vers[1], vers[-1]
        for field in ("quality", "type", "group_id", "SeasonParam", "show_unlock_condition", "FragmentId", "fragment_num", "exchange_goods"):
            if v1.get(field) != vm1.get(field):
                raise ValueError(f"{name} field {field} differs across versions")
        if v1["name"] != vm1["name"] or v1["desc"] != vm1["desc"]:
            raise ValueError(f"{name} name/desc keys differ")
        # self attrs identical; fightforce always different
        for star in range(101):
            a, b = star_by[v1["id"]][star], star_by[vm1["id"]][star]
            sa, _ = _self_and_hero(a)
            sb, _ = _self_and_hero(b)
            if sa != sb:
                raise ValueError(f"{name} self attrs differ at star {star}")
            if a["level"] != b["level"] or a["skillShowLevel"] != b["skillShowLevel"]:
                raise ValueError(f"{name} level fields differ at star {star}")
            if a["fightforce"] == b["fightforce"]:
                raise ValueError(f"{name} fightforce unexpectedly same at star {star}")
        s0, s100 = star_by[v1["id"]][0], star_by[v1["id"]][100]
        self0, hero0 = _self_and_hero(s0)
        self100, hero100 = _self_and_hero(s100)
        exp = ATTR_SUMMARY[v1["quality"]]
        if (self0[3], self0[4], self100[3], self100[4]) != (exp["atk0"], exp["hp0"], exp["atk100"], exp["hp100"]):
            raise ValueError(f"{name} atk/hp mismatch: {self0} {self100}")
        # hero exceptions only for version=-1 元帥號角 5–9 and 石化魔杖 100
        if name != "石化魔杖":
            if (hero0.get(103), hero0.get(104)) != exp["h0"] or (hero100.get(103), hero100.get(104)) != exp["h100"]:
                raise ValueError(f"{name} v1 hero attrs mismatch")
        else:
            if (hero0.get(103), hero0.get(104)) != exp["h0"] or (hero100.get(103), hero100.get(104)) != exp["h100"]:
                raise ValueError("石化魔杖 v1 100-star hero should match 品質 4")
        h0_vm1 = _self_and_hero(star_by[vm1["id"]][0])[1]
        h100_vm1 = _self_and_hero(star_by[vm1["id"]][100])[1]
        # 第 20 章只寫石化魔杖；升星表同樣例外還有煌雷裁決、青藤古弓。
        if name in ("石化魔杖", "煌雷裁決", "青藤古弓"):
            if (h100_vm1.get(103), h100_vm1.get(104)) != (1800, 3600):
                raise ValueError(f"{name} v-1 100-star hero exception drifted")
        elif (h100_vm1.get(103), h100_vm1.get(104)) != exp["h100"]:
            raise ValueError(f"{name} v-1 100-star hero mismatch")
        if name == "元帥號角":
            for star in range(5, 10):
                hv = _self_and_hero(star_by[vm1["id"]][star])[1]
                if (hv.get(103), hv.get(104)) != (30, 30):
                    raise ValueError("元帥號角 v-1 5–9 star exception drifted")
                hv1 = _self_and_hero(star_by[v1["id"]][star])[1]
                if (hv1.get(103), hv1.get(104)) != (30, 60):
                    raise ValueError("元帥號角 v1 5–9 star drifted")
        ff0 = (_int(s0["fightforce"]), _int(star_by[vm1["id"]][0]["fightforce"]))
        ff100 = (_int(s100["fightforce"]), _int(star_by[vm1["id"]][100]["fightforce"]))
        if ff0 != exp["ff0"] or ff100 != exp["ff100"]:
            raise ValueError(f"{name} fightforce mismatch {ff0} {ff100}")
        if v1["quality"] == 4 and v1["exchange_goods"] != 514:
            raise ValueError("品質 4 exchange_goods is not 514")
        if v1["quality"] in (2, 3) and v1["exchange_goods"] != -1:
            raise ValueError("品質 2/3 exchange_goods is not -1")
        desc_key = v1["desc"]
        desc_missing = not has_key(desc_key)
        if desc_missing:
            # 神聖盟約 to 不敗華冠 (50012–50019) have no desc string.
            if not (50012 <= _int(str(desc_key).rsplit("_", 1)[-1]) <= 50019):
                raise ValueError(f"unexpected missing desc {desc_key}")
            desc = ""
        else:
            desc = official_text(desc_key)
        info = ArtifactInfo(
            name=name,
            id_v1=_int(v1["id"]),
            id_vm1=_int(vm1["id"]),
            quality=_int(v1["quality"]),
            typ=_int(v1["type"]),
            type_name=official.type_names[v1["type"]],
            group_id=_int(v1["group_id"]),
            season=format_season(v1.get("SeasonParam")),
            unlock=str(v1["show_unlock_condition"]),
            desc=desc,
            desc_missing=desc_missing,
            fragment_id=_int(v1["FragmentId"]),
            exchange_goods=_int(v1["exchange_goods"]),
            skill_attr_type=_int(v1["artifact_skill_attr_type"]),
            skill0=_snapshot(s0, name),
            skill100=_snapshot(s100, name),
            extra0={k: v for k, v in self0.items() if k in (18, 19)},
            extra100={k: v for k, v in self100.items() if k in (18, 19)},
            hero0=(hero0.get(103, 0), hero0.get(104, 0)),
            hero100=(hero100.get(103, 0), hero100.get(104, 0)),
            atk0=self0[3],
            hp0=self0[4],
            atk100=self100[3],
            hp100=self100[4],
            ff0_v1=ff0[0],
            ff0_vm1=ff0[1],
            ff100_v1=ff100[0],
            ff100_vm1=ff100[1],
            suit_origin=_int(s0.get("suit_originID") or -1),
        )
        artifacts.append(info)
        if info.quality == 2 and True:
            q2_v1_ids.append(info.id_v1)

    artifacts.sort(key=lambda a: a.id_v1)
    type_counts = {1: 0, 2: 0, 3: 0}
    quality_counts = {2: 0, 3: 0, 4: 0}
    for a in artifacts:
        type_counts[a.typ] += 1
        quality_counts[a.quality] += 1
    if type_counts != {1: 10, 2: 11, 3: 8} or quality_counts != {2: 3, 3: 7, 4: 19}:
        raise ValueError(f"type/quality counts {type_counts} {quality_counts}")
    # 青藤古弓 is 進攻 but group 1502
    ivy = next(a for a in artifacts if a.name == "青藤古弓")
    if ivy.typ != 1 or ivy.group_id != 1502:
        raise ValueError("青藤古弓 type/group drifted")
    # empty skill_desc locked
    for empty_name in ("煌雷裁決", "龍骸護符", "青藤古弓"):
        art = next(a for a in artifacts if a.name == empty_name)
        if art.skill0.filled != ["（無技能說明）"] or art.skill100.filled != ["（無技能說明）"]:
            raise ValueError(f"{empty_name} unexpectedly has skill_desc")
    # locked skill fills
    bottle = next(a for a in artifacts if a.name == "秘藥之瓶")
    if bottle.skill0.filled != ["為己方血量最少的2名角色提供5%的減傷持續4秒，冷卻時間20秒"]:
        raise ValueError(f"秘藥之瓶 0-star fill drifted: {bottle.skill0.filled}")
    if bottle.skill100.filled[0] != "為己方血量最少的3名角色提供10%的減傷持續4秒，冷卻時間20秒":
        raise ValueError("秘藥之瓶 100-star first segment drifted")
    if bottle.skill100.filled[1] != "，使被治療角色獲得3秒持續治療效果，每秒回復10%秘寶攻擊的生命":
        raise ValueError("秘藥之瓶 100-star second segment must start from {0}=3, not leftover 2")
    pin = next(a for a in artifacts if a.name == "平衡胸針")
    if pin.skill100.filled[1] != "，箭塔攻擊附加100秒的灼燒傷害，每秒造成450%傷害":
        raise ValueError("平衡胸針 100-star second segment must start from {0}=100")
    # cost curves
    def curve_qty(aid: int) -> list[int]:
        out = []
        for star in range(1, 101):
            cost = star_cost(star_by[aid][star])
            if cost is None:
                raise ValueError(f"missing cost {aid} star {star}")
            out.append(cost[1])
        return out

    if band_total(Q2_V1_BANDS) != Q2_V1_TOTAL or band_total(Q3_BANDS) != Q3_TOTAL or band_total(Q4_BANDS) != Q4_TOTAL:
        raise ValueError("band totals drifted")
    if sum(_q2_vm1_qty(s) for s in range(1, 101)) != Q2_VM1_TOTAL:
        raise ValueError("q2 v-1 total drifted")
    for art in artifacts:
        qtys = curve_qty(art.id_v1)
        qtys_m = curve_qty(art.id_vm1)
        if art.quality == 2:
            expect = [qty_at(Q2_V1_BANDS, s) for s in range(1, 101)]
            expect_m = [_q2_vm1_qty(s) for s in range(1, 101)]
            if qtys != expect or qtys_m != expect_m:
                raise ValueError(f"{art.name} q2 cost curve drifted")
        elif art.quality == 3:
            expect = [qty_at(Q3_BANDS, s) for s in range(1, 101)]
            if qtys != expect or qtys_m != expect:
                raise ValueError(f"{art.name} q3 cost curve drifted")
        else:
            expect = [qty_at(Q4_BANDS, s) for s in range(1, 101)]
            if qtys != expect or qtys_m != expect:
                raise ValueError(f"{art.name} q4 cost curve drifted")
        if star_cost(star_by[art.id_v1][0]) is not None:
            raise ValueError("0-star has cost")
        # 100-star level/show
        s100 = star_by[art.id_v1][100]
        expect_lv = {2: (11, 10), 3: (13, 12), 4: (21, 20)}[art.quality]
        if (s100["level"], s100["skillShowLevel"]) != expect_lv:
            raise ValueError(f"{art.name} 100-star level {s100['level']}/{s100['skillShowLevel']} != {expect_lv}")

    # hall
    hall_rows = [r for r in lvup_raw if r["index"] == HALL_INDEX]
    hall_new_rows = [r for r in lvup_new_raw if r["index"] == HALL_INDEX]
    if len(hall_rows) != 2077 or len(hall_new_rows) != 2077:
        raise ValueError("hall row count drifted")
    by_lv = {r["lv"]: r for r in hall_rows}
    by_lv_new = {r["lv"]: r for r in hall_new_rows}
    if set(by_lv) != set(range(0, 2077)) or set(by_lv_new) != set(by_lv):
        raise ValueError("hall levels not 0–2076")
    compare_fields = (
        "para1", "para2", "para3", "string_para1", "string_para2", "fightforce",
        "des", "cost1", "cost2", "buildTime", "pre_building_level",
    )
    for lv, row in by_lv.items():
        other = by_lv_new[lv]
        for f in compare_fields:
            if row.get(f) != other.get(f):
                raise ValueError(f"lvup vs lvup_new hall lv {lv} field {f} differs")
        if row["para3"] != 0:
            raise ValueError("para3 is not 0")
        if row["des"] != ["artifact_atk_up", "artifact_hp_up", "uilding_lvup_des_115003"]:
            raise ValueError(f"hall des keys drifted at {lv}")
        slot = parse_slot(row["string_para2"])
        if lv <= 20 and slot != 0:
            raise ValueError(f"slot at {lv} not 0")
        if 21 <= lv <= 34 and slot != 1:
            raise ValueError(f"slot at {lv} not 1")
        if lv >= 35 and slot != 2:
            raise ValueError(f"slot at {lv} not 2")
        c1 = parse_cost_pair(row.get("cost1"))
        if lv <= 39:
            if not c1 or c1[0] != 999 or c1[1] != 4 or parse_cost_pair(row.get("cost2"))[1] != 5:
                raise ValueError(f"lv {lv} should cost wood/stone")
        elif lv <= 2075:
            c2 = parse_cost_pair(row.get("cost2"))
            if not c1 or c1[0] != 2 or c1[1] != 237 or not c2 or c2[0] != 2 or c2[1] != 238:
                raise ValueError(f"lv {lv} should cost 237/238")
            if row["buildTime"] not in (-1, 0):
                raise ValueError(f"lv {lv} unexpected buildTime {row['buildTime']}")
            if row.get("pre_building_level") not in (None, "", [], -1):
                raise ValueError(f"lv {lv} should have empty pre_building_level")
        else:
            if parse_cost_pair(row.get("cost1")) is not None:
                raise ValueError("2076 still has cost")
    zero_bt = [lv for lv, row in by_lv.items() if 40 <= lv <= 2075 and row["buildTime"] == 0]
    if zero_bt != list(range(440, 479)) + list(range(1440, 1479)):
        raise ValueError(f"unexpected hall buildTime 0 levels: {zero_bt[:8]}... n={len(zero_bt)}")
    if parse_attr_map(by_lv[1]["string_para1"]).get(20005) != 13535:

        raise ValueError("hall lv 1 string_para1 20005 drifted")
    if parse_attr_map(by_lv[2076]["string_para1"]).get(20005) != 37771:
        raise ValueError("hall lv 2076 string_para1 20005 drifted")
    if len({r["para1"] for r in hall_rows}) != 129 or max(r["para1"] for r in hall_rows) != 3440:
        raise ValueError("para1 unique/max drifted")
    if len({r["para2"] for r in hall_rows}) != 200 or max(r["para2"] for r in hall_rows) != 199:
        raise ValueError("para2 unique/max drifted")
    hall: list[HallLevel] = []
    for lv in HALL_KEY_LEVELS:
        row = by_lv[lv]
        slot = parse_slot(row["string_para2"])
        expect = HALL_EXPECTED[lv]
        got = (_int(row["para1"]), _int(row["para2"]), slot, _int(row["fightforce"]))
        if got != expect:
            raise ValueError(f"hall lv {lv} {got} != {expect}")
        pre = row.get("pre_building_level")
        pre_s = "／".join(str(x) for x in pre) if isinstance(pre, list) and pre else (EMPTY if pre in (None, "", [], -1) else str(pre))
        sp1 = row.get("string_para1")
        sp1_s = EMPTY if sp1 in (None, "", [], -1) else "、".join(str(x) for x in (sp1 if isinstance(sp1, list) else [sp1]))
        hall.append(HallLevel(
            lv=lv, para1=got[0], para2=got[1], slot=got[2], fightforce=got[3],
            note=HALL_NOTES.get(lv, ""), string_para1=sp1_s, pre=pre_s,
            cost=_hall_cost_label(row, official),
        ))

    # suits
    if {r["id"] for r in suits_raw} != {101, 102, 103, 201, 202, 203}:
        raise ValueError("suit ids drifted")
    suits: list[SuitInfo] = []
    name_by_id = {a.id_v1: a.name for a in artifacts}
    name_by_id.update({a.id_vm1: a.name for a in artifacts})
    for vid, mid in ((201, 101), (202, 102), (203, 103)):
        rv = next(r for r in suits_raw if r["id"] == vid)
        rm = next(r for r in suits_raw if r["id"] == mid)
        if rv["name"] != rm["name"] or rv["desc"] != rm["desc"] or rv["race"] != rm["race"] or rv["suit_skill_star"] != 15:
            raise ValueError(f"suit {vid}/{mid} mismatch")
        ids_v1 = [_int(x) for x in str(rv["artifact_group"]).split("|")]
        members = [name_by_id[i] for i in ids_v1]
        suits.append(SuitInfo(
            name=official_text(rv["name"]),
            race=_int(rv["race"]),
            race_name=official.races[rv["race"]],
            id_v1=vid,
            id_vm1=mid,
            members=members,
            member_ids_v1=ids_v1,
            desc=official_text(rv["desc"]),
            skill_star=_int(rv["suit_skill_star"]),
        ))
    if [s.name for s in suits] != ["秘法寶庫", "巨龍之力", "聖林誓約"]:
        raise ValueError(f"suit names drifted: {[s.name for s in suits]}")
    if official.power_suit_name != "秘寶之力":
        raise ValueError("秘寶之力 name drifted")

    # honor
    honor: list[HonorRow] = []
    expect_honor = {
        2: (4, 40, 160),
        3: (4, 80, 880),
        4: (4, 160, 1760),
    }
    chip = "200|10,300|20,400|30,600|30"
    for row in sorted(honor_raw, key=lambda r: r["quality"]):
        if row["need_chip"] != chip:
            raise ValueError("honor need_chip drifted")
        aid, aval = expect_honor[row["quality"]][0], expect_honor[row["quality"]][1]
        attr = parse_attr_map(row["attribute_up"])
        if attr != {aid: aval} or row["combat_power"] != expect_honor[row["quality"]][2]:
            raise ValueError(f"honor quality {row['quality']} drifted")
        honor.append(HonorRow(
            quality=_int(row["quality"]),
            attr_id=aid,
            attr_name=attr_label(aid, attr_by),
            attr_value=aval,
            combat=_int(row["combat_power"]),
            need_chip=str(row["need_chip"]),
        ))
    thresholds = (50, 100, 150, 200, 300)
    grouped: dict[int, list] = defaultdict(list)
    for row in honor_bonus_raw:
        grouped[row["honor_group"]].append(row)
    if set(grouped) != {1301, 1302, 1401, 1402, 1501, 1502}:
        raise ValueError("honor bonus groups drifted")
    honor_bonus: list[HonorBonus] = []
    expect_bonus = {
        1301: (103, {50: 10, 100: 20, 150: 30, 200: 40, 300: 50}, {50: 9000, 100: 18000, 150: 27000, 200: 36000, 300: 45000}),
        1302: (104, {50: 10, 100: 20, 150: 30, 200: 40, 300: 50}, {50: 9000, 100: 18000, 150: 27000, 200: 36000, 300: 45000}),
        1401: (103, {50: 20, 100: 40, 150: 60, 200: 80, 300: 100}, {50: 18000, 100: 36000, 150: 54000, 200: 72000, 300: 90000}),
        1402: (104, {50: 20, 100: 40, 150: 60, 200: 80, 300: 100}, {50: 18000, 100: 36000, 150: 54000, 200: 72000, 300: 90000}),
        1501: (103, {50: 30, 100: 60, 150: 90, 200: 120, 300: 150}, {50: 27000, 100: 54000, 150: 81000, 200: 108000, 300: 135000}),
        1502: (104, {50: 30, 100: 60, 150: 90, 200: 120, 300: 150}, {50: 27000, 100: 54000, 150: 81000, 200: 108000, 300: 135000}),
    }
    for gid in (1301, 1302, 1401, 1402, 1501, 1502):
        rows = sorted(grouped[gid], key=lambda r: r["bonus_lv"])
        if [r["bonus_lv"] for r in rows] != list(thresholds):
            raise ValueError(f"honor bonus thresholds for {gid} drifted")
        attr_id, vals, combats = expect_bonus[gid]
        got_v = {r["bonus_lv"]: parse_attr_map(r["bonus_attribute"])[attr_id] for r in rows}
        got_c = {r["bonus_lv"]: _int(r["combat"]) for r in rows}
        if got_v != vals or got_c != combats:
            raise ValueError(f"honor bonus {gid} drifted {got_v} {got_c}")
        honor_bonus.append(HonorBonus(
            group=gid, attr_id=attr_id, attr_name=attr_label(attr_id, attr_by),
            values=vals, combats=combats,
        ))

    # skill_attr: three types, 40 levels each, identical curves; do not dump or override star-up.
    by_type = defaultdict(list)
    for row in skill_attr_raw:
        by_type[row["type"]].append(row)
    if set(by_type) != {3, 4, 5} or any(len(v) != 40 for v in by_type.values()):
        raise ValueError("skill_attr type/level counts drifted")
    def sa_curve(typ: int):
        return [(r["level"], r["attr_1"], r["attr_2"], r["attr_3"], r["attr_4"]) for r in sorted(by_type[typ], key=lambda x: x["level"])]
    if not (sa_curve(3) == sa_curve(4) == sa_curve(5)):
        raise ValueError("skill_attr type curves are not identical")
    lv1 = next(r for r in skill_attr_raw if r["type"] == 3 and r["level"] == 1)
    if (lv1["attr_1"], lv1["attr_2"], lv1["attr_3"]) != ("3|90", "4|900", "10|10000"):
        raise ValueError("skill_attr level 1 drifted")
    if max(r["level"] for r in skill_attr_raw) != 40:
        raise ValueError("skill_attr max level drifted")

    # 電青蛙 formal name vs 蛙神圖騰
    if "蛙神圖騰" not in official.frog_totem_descs[0] or "電青蛙" not in [a.name for a in artifacts]:
        raise ValueError("frog totem / 電青蛙 check failed")

    string_cmp = _compare_string_packs(set(USED_KEYS))
    terms = _terms(official, artifacts, suits)
    table_count = 759
    try:
        table_count = sum(1 for p in DATA_DIR.glob("*.json"))
    except OSError:
        pass

    verifications = {
        "artifact_rows": 58,
        "names": 29,
        "star_rows": 5858,
        "suit_rows": 6,
        "honor_rows": 3,
        "honor_bonus_rows": 30,
        "skill_attr_rows": 120,
        "hall_rows": 2077,
        "q4_0_star_atk_hp": (2780, 19100),
        "q3_100_star_level": (13, 12),
        "string_used_keys": string_cmp["used_keys"],
        "string_value_diffs": string_cmp["value_diffs"],
        "string_missing": string_cmp["missing"],
        "string_packs": {k: {"keys": v["keys"], "sha256": v["sha256"]} for k, v in string_cmp["packs"].items()},
        "tables_in_pack": table_count,
    }
    data = TablesData(
        official=official,
        artifacts=artifacts,
        suits=suits,
        hall=hall,
        honor=honor,
        honor_bonus=honor_bonus,
        terms=terms,
        verifications=verifications,
        table_meta={"string_cmp": string_cmp, "table_count": table_count},
    )
    return data


def _terms(official: Official, artifacts: list[ArtifactInfo], suits: list[SuitInfo]) -> list[str]:
    terms: set[str] = {
        official.system_name, official.hall_name, official.hall_des,
        official.honour_unlock, official.atk_up, official.hp_up, official.attr_up,
        official.wrong_des, official.same_type_tips, official.wood, official.stone,
        official.hammer, official.hammer_desc, official.magic_stone, official.arcane,
        official.castle, official.slot_name, official.art_atk, official.art_hp,
        official.hero_atk, official.hero_hp, official.dmg_up, official.dmg_cut,
        official.atk, official.hp, official.swap_tips, official.power_suit_name,
        official.power_suit_desc, official.buff_desc, official.name_dec,
        "裝備總表", "領主裝備總表", "士兵總表", "專武總表",
        "英雄裝備", "領主裝備", "專武", "士兵", "秘寶總表",
        "秘寶大廳", "秘寶榮譽牆", "秘寶攻擊放大率", "秘寶生命放大率", "秘寶屬性轉化率",
        "額外秘寶插槽", "秘寶攻擊", "秘寶生命", "英雄攻擊", "英雄生命",
        "上陣英雄攻擊", "上陣英雄生命", "全體英雄防禦",
        "遠征大廳", "無法上陣相同定位的秘寶",
        "藍色品質秘寶", "紫色品質秘寶", "橙色品質秘寶", "橙色秘寶",
        "藍秘寶萬能碎片", "紫秘寶萬能碎片", "橙秘寶萬能碎片",
        "藍色秘寶碎片", "紫色秘寶碎片", "橙色秘寶碎片",
        "蛙神圖騰", "電青蛙", "奇蹟之錘", "魔紋石", "奧術水晶",
        "進攻型秘寶", "生存型秘寶", "通用型秘寶",
        "傳奇(含)以上品質的秘寶星級", "傳奇(含)以上品質",
    }
    for name in official.races.values():
        terms.add(name)
    for name in official.type_names.values():
        terms.add(name)
    for desc in official.type_descs.values():
        terms.add(desc)
    for line in official.rules.split("\n"):
        terms.add(line.strip())
    for line in official.rules_new.split("\n"):
        terms.add(line.strip())
    for text in official.info.values():
        terms.add(text)
        for line in text.split("\n"):
            terms.add(line.strip())
    for text in official.honour_lines.values():
        terms.add(text)
    terms.add(official.suit_unlock[0])
    terms.add(official.suit_unlock[1])
    for art in artifacts:
        terms.add(art.name)
        terms.add(art.desc)
        terms.add(art.skill0.name)
        terms.add(art.skill100.name)
        for line in art.skill0.filled + art.skill100.filled + art.skill0.originals + art.skill100.originals:
            terms.add(line)
    for suit in suits:
        terms.add(suit.name)
        terms.add(suit.desc)
        for line in suit.desc.split("\n"):
            terms.add(line.strip())
        terms.update(suit.members)
    for text in official.frog_totem_descs:
        terms.add(text)
    for name, desc in official.generic_chips.values():
        terms.add(name)
        terms.add(desc)
    for text in official.chip_descs_example:
        terms.add(text)
    # composed official formula phrases (info_003 uses 上陣英雄攻擊=…)
    terms.add("上陣英雄攻擊=秘寶攻擊*倍率*轉化率")
    terms.add("上陣英雄生命=秘寶生命*倍率*轉化率")
    terms.add("英雄攻擊=秘寶攻擊*倍率*轉化率")
    terms.add("英雄生命=秘寶生命*倍率*轉化率")
    return sorted({x for x in terms if x}, key=len, reverse=True)



def _alabel(name: str, attr_id: int, terms: list[str] | None = None) -> str:
    # Visible cells keep the official name; attribute ids are listed in 資料說明.
    text = name
    return H(text, terms) if terms is not None else text


def _skill_cell_plain(snap: SkillSnapshot) -> str:
    parts = list(snap.filled)
    if snap.show_originals:
        orig = "；".join(snap.originals)
        parts.append(f"（各段原文：{orig}）")
    return "\n".join(parts)


def _skill_cell_html(snap: SkillSnapshot, terms: list[str]) -> str:
    parts = [H(line, terms) for line in snap.filled]
    if snap.show_originals:
        orig = "；".join(snap.originals)
        parts.append(H(f"（各段原文：{orig}）", terms))
    return "<br>".join(parts)


def _cost_headers(bands) -> list[str]:
    cols = [f"{lo}–{hi}" for (lo, hi), _ in bands]
    cols.append("合計")
    return cols


def _cost_qty_row(bands, qty_fn) -> list[str]:
    qtys = [str(qty_fn(lo)) for (lo, hi), _ in bands]
    total = sum((hi - lo + 1) * qty_fn(lo) for (lo, hi), _ in bands)
    qtys.append(str(total))
    return qtys


def _extra_plain(extra: dict[int, int], official: Official) -> str:
    if not extra:
        return "無"
    parts = []
    if 18 in extra:
        parts.append(f"{official.dmg_up} {extra[18]}")
    if 19 in extra:
        parts.append(f"{official.dmg_cut} {extra[19]}")
    return "／".join(parts)


def _build_html_tables(data: TablesData, terms: list[str]) -> dict[str, str]:
    o = data.official
    hall = table(
        ["大廳等級", "數值 1", "數值 2", f"{H(o.slot_name, terms)}", "戰力", "備註"],
        [
            [str(r.lv), str(r.para1), str(r.para2), str(r.slot), str(r.fightforce), H(r.note, terms) if r.note else ""]
            for r in data.hall
        ],
        mobile="sticky",
        card_title="大廳等級",
    )
    catalog_rows = []
    row_ids = []
    for a in data.artifacts:
        typ = f"{a.typ} {a.type_name}"
        desc = "（無說明字串）" if a.desc_missing else a.desc
        catalog_rows.append([
            H(a.name, terms),
            str(a.id_v1),
            str(a.id_vm1),
            str(a.quality),
            H(typ, terms),
            str(a.group_id),
            a.season,
            e(format_unlock_stars(a.unlock)),
            H(desc, terms),
        ])
        row_ids.append(f"art-{a.id_v1}")
    catalog = table(
        ["名稱", "目前這套", "資料裡另一套", "品質", "類型", "榮譽組", "賽季參數", "技能解鎖星", "說明"],
        catalog_rows,
        mobile="cards",
        card_title="名稱",
        row_ids=row_ids,
    )
    suit_rows = []
    for s in data.suits:
        members = "、".join(H(n, terms) for n in s.members)
        suit_rows.append([
            H(s.name, terms),
            f"{s.race} {H(s.race_name, terms)}",
            str(s.id_v1),
            str(s.id_vm1),
            members,
            highlight_lines(s.desc, terms),
        ])
    suits = table(
        ["套裝", "陣營", "目前這套", "資料裡另一套", "成員", "官方說明（原文）"],
        suit_rows,
        mobile="cards",
        card_title="套裝",
    )
    cost_q2 = table(
        ["版本"] + _cost_headers(Q2_V1_BANDS),
        [
            [H("目前這套", terms)] + _cost_qty_row(Q2_V1_BANDS, lambda lo: qty_at(Q2_V1_BANDS, lo)),
            [H("資料裡另一套", terms)] + _cost_qty_row(Q2_V1_BANDS, _q2_vm1_qty),
        ],
        mobile="sticky",
    )
    cost_q3 = table(
        _cost_headers(Q3_BANDS),
        [_cost_qty_row(Q3_BANDS, lambda lo: qty_at(Q3_BANDS, lo))],
        mobile="sticky",
    )
    cost_q4 = table(
        _cost_headers(Q4_BANDS),
        [_cost_qty_row(Q4_BANDS, lambda lo: qty_at(Q4_BANDS, lo))],
        mobile="sticky",
    )
    attr_rows = []
    for q in (2, 3, 4):
        exp = ATTR_SUMMARY[q]
        attr_rows.append([
            str(q),
            f"{exp['atk0']}／{exp['hp0']}",
            f"{exp['atk100']}／{exp['hp100']}",
            f"{exp['h0'][0]}／{exp['h0'][1]}",
            f"{exp['h100'][0]}／{exp['h100'][1]}",
            f"{exp['ff0'][0]}（{exp['ff0'][1]}）",
            f"{exp['ff100'][0]}（{exp['ff100'][1]}）",
        ])
    attrs = table(
        [
            "品質",
            "0 星攻擊／生命",
            "100 星攻擊／生命",
            f"0 星{o.hero_atk}／{o.hero_hp}",
            f"100 星{o.hero_atk}／{o.hero_hp}",
            "0 星戰力",
            "100 星戰力",
        ],
        attr_rows,
        mobile="sticky",
    )
    honor = table(
        ["品質", "附加屬性", "戰力", "碎片欄（表上無標題）"],
        [
            [str(r.quality), _alabel(r.attr_name, r.attr_id, terms) + f" {r.attr_value}", str(r.combat), e(r.need_chip)]
            for r in data.honor
        ],
        mobile="sticky",
    )
    bonus_rows = []
    for r in data.honor_bonus:
        bonus_rows.append(
            [str(r.group), _alabel(r.attr_name, r.attr_id, terms)]
            + [str(r.values[lv]) for lv in (50, 100, 150, 200, 300)]
            + [f"{r.combats[50]}–{r.combats[300]}"]
        )
    bonus = table(
        ["榮譽組", "屬性", "50", "100", "150", "200", "300", "對應戰力"],
        bonus_rows,
        mobile="sticky",
    )
    skills: dict[int, str] = {}
    for a in data.artifacts:
        rows = []
        for snap in (a.skill0, a.skill100):
            name = H(snap.name, terms) if snap.name else EMPTY
            if snap.name_is_artifact:
                name += "<br>" + e("（技能顯示與秘寶同名）")
            rows.append([
                f"{snap.star} 星",
                str(snap.level),
                str(snap.show_level),
                name,
                e(format_params(snap.params)),
                _skill_cell_html(snap, terms),
            ])
        skills[a.id_v1] = table(
            ["星級", "等級", "技能顯示等級", "技能名", "參數", "技能文案"],
            rows,
            mobile="cards",
            card_title="星級",
        )
    return {
        "hall": hall,
        "catalog": catalog,
        "suits": suits,
        "cost_q2": cost_q2,
        "cost_q3": cost_q3,
        "cost_q4": cost_q4,
        "attrs": attrs,
        "honor": honor,
        "bonus": bonus,
        "skills": skills,
    }


def _data_notes(data: TablesData) -> str:
    sc = data.table_meta["string_cmp"]
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
    return (
        f"資料截至 {ARTIFACT_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {ARTIFACT_DATA_PACK}（{data.table_meta['table_count']} 張表），"
        f"打包時戳 {ARTIFACT_DATA_PACKED}（香港時間）。"
        "升星、套裝、榮譽與技能屬性輔表（artifact_star_up、artifact_suit、artifact_honor、"
        "artifact_honor_bonus、artifact_skill_attr）與第 20 章所用 2026-11-05 解壓檔、"
        "以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同。"
        "這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "`artifact.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（58 筆）；"
        "2026-11-05 與 2026-11-22 StreamingAssets 彼此相同，但與現行檔位元組不同："
        "只差在 `GetSkillVOList`／`_skillVOList` 後來多了 `artifactMetaId` 與 `skillId`；"
        "其餘共有欄（含 id、名稱鍵、品質、類型、碎片、SeasonParam、技能解鎖星）相同。"
        "`citybuilding_lvup.json`／`citybuilding_lvup_new.json` 整檔與 2026-11-05 解壓檔位元組不同"
        "（現行檔與 2026-11-22 兩份歸檔相同），但建築 140 秘寶大廳 0–2076 級本頁用到的數值欄"
        "（para1／para2／para3、string_para1／string_para2、戰力、des、消耗、buildTime、前置）"
        "在四份裡相同。"
        f"`strings_zh.json` 現行檔與 2026-11-22 LocalLow 歸檔相同（{live['keys']} 鍵）；"
        f"2026-11-05（{old['keys']} 鍵）與 2026-11-22 StreamingAssets（{sa['keys']} 鍵）整體不同。"
        f"{extra}"
        "`attribute.json` 列數同為 764，2026-11-05 與現行包位元組不同，差在後來多了欄位；"
        "本頁用到的 type／show_type／name 與 2026-11-05 相同。"
        "顯示規則依攻略手冊「秘寶圖鑑」第一版（2026-11-15，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。"
        "第 20 章升星節摘要把 品質 4 的 0 星攻擊／生命寫成 3530／23600、把 品質 3 的 100 星"
        "寫成 level 16／skillShowLevel 15、把 artifact_skill_attr 的級數寫成 11／16／40；"
        "本頁改以升星表與輔表實有列為準：品質 4 的 0 星為 2780／19100，品質 3 的 100 星為"
        "level 13／skillShowLevel 12（該章各件技能小節原本已寫 13／12），輔表三型皆為 1–40 級且曲線相同。"
    )


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    o = data.official
    terms = data.terms
    tbl = _build_html_tables(data, terms)
    title = "Top Heroes Wiki｜秘寶總表"
    summary = "可佩戴到隊列上的秘寶：兩套編號、29 個中文名錄、秘寶大廳關鍵級、升星消耗與滿星屬性、表列套裝、榮譽牆，以及各件 0 星／100 星技能原文。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "scope", "label": "範圍"},
        {"id": "rules", "label": "系統規則（官方字串）"},
        {"id": "hall", "label": "秘寶大廳"},
        {"id": "versions", "label": "兩套編號"},
        {"id": "catalog", "label": "名錄"},
        {"id": "suits", "label": "套裝"},
        {"id": "upgrade", "label": "升星、消耗與屬性"},
        {"id": "skills", "label": "技能"},
        {"id": "honor", "label": "榮譽牆"},
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
        "正文只根據遊戲資料表與官方字串，不評定秘寶強弱，也不排行。"
        f"官方界面名稱是「{H(o.system_name, terms)}」。"
        "分類目錄把這批內容寫成「神器（Artifact）」，與界面用字不同；"
        f"本頁跟界面，稱「{H(o.system_name, terms)}」。"
        f"英雄四件套裝備見<a href=\"equipment.html\">{H('裝備總表', terms)}</a>，"
        f"領主裝備見<a href=\"lord-equipment.html\">{H('領主裝備總表', terms)}</a>，"
        f"士兵見<a href=\"troops.html\">{H('士兵總表', terms)}</a>。"
        f"已發佈的<a href=\"exclusive.html\">{H('專武總表', terms)}</a>是英雄專武。"
        f"{H('英雄裝備', terms)}、{H('專武', terms)}、{H('領主裝備', terms)}都不是{H('秘寶', terms)}。"
    ))
    add("<ul>")
    add("<li><strong>本頁只寫可佩戴到隊列上的秘寶系統。</strong>"
        f"下面會列出 29 個中文名、{H('秘寶大廳', terms)}關鍵級、升星與套裝、榮譽牆，以及 0 星／100 星技能原文。"
        "資料表檔名與筆數見資料說明。</li>")
    add("<li><strong>同一件秘寶有兩套編號。</strong>"
        "同一中文名的品質、類型、技能解鎖星，以及升星表裡的"
        f"{H(o.atk, terms)}／{H(o.hp, terms)}與附加的{H(o.dmg_up, terms)}、{H(o.dmg_cut, terms)}，兩套相同。"
        "戰力、部分升星消耗、以及少數技能文案／全英雄屬性並不完全相同，見「兩套編號」。"
        "名錄與技能以目前這套為準列出，並註明另一套的差別。"
        "本頁不自行斷定遊戲現在讀哪一套。</li>")
    add("<li><strong>不要從季節或活動欄位自動標未開放。</strong>表上沒有「已推出」旗標，只照錄。</li>")
    add("<li><strong>屬性只錄表上的原值</strong>，不自行換成百分比。點數與百分比兩類屬性的對照見資料說明。</li>")
    add("<li><strong>品質欄是表上的 2／3／4。</strong>"
        f"任務與道具字串有「{H('藍色品質秘寶', terms)}／{H('紫色品質秘寶', terms)}／{H('橙色品質秘寶', terms)}」；"
        f"{H(o.hammer, terms)}說明寫「{H('橙色秘寶', terms)}」，且只有品質 4 的秘寶以{H(o.hammer, terms)}作為交換道具。"
        "品質欄仍錄數字，不把任務鍵編號自行解釋成另一套枚舉，也不把「傳奇(含)以上品質」強行對成 2／3／4。"
        "欄位對照見資料說明。</li>")
    add("<li>技能文案以升星表的說明填入參數後照錄。"
        "同一列若有多段說明，每段都從第一個佔位符起算，多餘參數不自行挪給下一段；"
        "對不上的地方改並列原文與參數。欄位名見資料說明。</li>")
    add("<li>官方用語是「部族」不是「部落」。本頁用到的秘寶字串沒有「部落」。"
        f"套裝的陣營編號與士兵表{H('聯盟', terms)}／{H('部族', terms)}／{H('自然', terms)}相同。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="scope">')
    add("      <h2>範圍</h2>")
    add(p_html(
        f"介面寫：{H(o.buff_desc.replace(chr(10)*2, '；'), terms)}。"
        f"另有「{H(o.name_dec, terms)}」。"
        f"影響力目錄把「{H('秘寶', terms)}」「{H('秘寶榮譽牆', terms)}」放在「隊伍提升」底下。"
        "字串鍵見資料說明。"
    ))
    add(p_html(
        f"官方用「{H('秘寶', terms)}」這兩個字的，不只這一系統。活動與道具、尋寶／寶藏表、城堡裝飾等不在本頁展開，見「本頁未列入」。"
        f"功能表沒有以「{H('秘寶', terms)}」為名的功能列。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>系統規則（官方字串）</h2>")
    add(p_html("資料裡有兩套規則文案，用字不完全相同，一併照錄，不自行判斷哪一套是目前介面。"))
    add(p_html("<strong>規則原文</strong>"))
    add(f"      <p>{highlight_lines(o.rules, terms)}</p>")
    add(p_html("<strong>較新的規則原文</strong>"))
    add(f"      <p>{highlight_lines(o.rules_new, terms)}</p>")
    add(p_html(
        "與較新規則並列的補充說明用字也不完全相同，同樣照錄。"
        f"其中一則寫「{H(o.info['artifact_info_002'], terms)}」，沒有「途徑」二字。"
        f"公式一則把效果寫成「{H('上陣英雄攻擊', terms)}／{H('上陣英雄生命', terms)}」："
        f"{H(o.info['artifact_info_003'], terms)}"
    ))
    add(p_html(
        f"另兩則寫：「{H(o.info['artifact_info_006'], terms)}」；"
        f"「{H(o.info['artifact_info_007'], terms)}」"
        "與升級表欄位的對照見下節，兩處不完全相同，只並列記錄，不作顯示結論。"
    ))
    add(p_html("所有 58 筆的碎片數量都是 10。合成與升星消耗的物品 id 見升星節。"))
    add("    </section>")

    add('    <section id="hall">')
    add(f"      <h2>{H('秘寶大廳', terms)}</h2>")
    add(p_html(
        f"官方名稱「{H(o.hall_name, terms)}」，說明：「{H(o.hall_des, terms)}」。"
        f"前面等級的解鎖／升級前置是{H(o.castle, terms)}達到指定等級，"
        f"例如 0 級列為{H(o.castle, terms)} 12 級；40 級起這欄為空。"
    ))
    add(p_html(
        "升級表 0–2076 級，共 2,077 列。兩張建築升級表此建築數值相同。"
        f"每級說明三個鍵依序是「{H(o.atk_up, terms)}」「{H(o.hp_up, terms)}」「{H(o.attr_up, terms)}」"
        "（第三個鍵在表上少了首字，字串內容確是"
        f"「{H(o.typo_des, terms)}」；相近的另一鍵是「{H(o.wrong_des, terms)}」，不是同一鍵。對照見資料說明）。"
        "數值有兩欄（第三欄全表為 0）。"
        "表沒有把這兩欄逐一標上上述三個名稱，本頁只列出各級數值，"
        "不自行指定哪一欄是倍率、哪一欄是轉化率。"
    ))
    add(p_html(
        f"「{H(o.slot_name, terms)}」：表上這欄是 0／1／2（對應 0–20、21–34、35–2076 級）。"
        "官方說明寫 20 級、50 級解鎖，與表上這欄對不上，只並列記錄，不作顯示結論。"
    ))
    add(p_html(
        f"從 1 級起寫{H(o.atk, terms)}、{H(o.hp, terms)}（名稱欄指向{H(o.art_atk, terms)}／{H(o.art_hp, terms)}），數值隨大廳等級增加，"
        "例如 1 級為 13535、2076 級為 37771。這組與數值 1／數值 2 的換算關係表上沒寫。"
    ))
    add(p_html(
        f"消耗：0–39 級為類型 999、資源 4／5（頂欄名稱為{H(o.wood, terms)}／{H(o.stone, terms)}），並有建造時間；"
        f"40–2075 級改為道具 237「{H(o.magic_stone, terms)}」與 238「{H(o.arcane, terms)}」；多數列的建造時間為 -1，但 440–478 與 1440–1478 共 78 級為 0；"
        "2076 級沒有再升級消耗。這與「額外需要使用奧術水晶升級時無法暴擊」的字串相符，"
        "但表沒有標哪一級開始算「額外使用奧術水晶」。"
    ))
    add(p_html(
        f"榮譽牆解鎖字串：「{H(o.honour_unlock, terms)}」。"
    ))
    add(p_html(
        "數值 1 從 1 級的 1000 起跳，共 129 個不同值，滿級 3440；"
        "數值 2 從 1 級的 1 增至 199，共 200 個不同值。完整 2,077 級不在本頁逐列。"
    ))
    add(tbl["hall"])
    add(p_html(
        "戰鬥公式分析裡，編隊面板有「秘寶 52.50%」作為增傷／減傷的來源分項；"
        f"本抽取沒有單一列{H(o.dmg_up, terms)} 5250 或{H(o.dmg_cut, terms)} 5250，可能是加總，只能載為面板來源，不編造表 id。"
        "單件 品質 4、目前這套 滿星時，進攻型自身增傷原值 3500，生存型自身減傷原值 3500，通用型兩項各 1750；"
        "3500＋1750＝5250，與面板那個分項數字相同，但表與官方說明都沒有把這兩件寫成固定搭配，不作唯一來源結論。"
        "完整加總式不在本頁展開。"
    ))
    add("    </section>")

    add('    <section id="versions">')
    add("      <h2>兩套編號</h2>")
    add(p_html(
        "29 個中文名各自有一筆 資料裡另一套 與一筆 目前這套，碎片、品質、類型、"
        "組別、賽季參數、技能解鎖星相同。"
        f"升星表中，自身{H(o.atk, terms)}／{H(o.hp, terms)}與附加的{H(o.dmg_up, terms)}／{H(o.dmg_cut, terms)}兩套一致；"
        "等級與技能顯示等級也一致。差別如下："
    ))
    add("<ul>")
    add("<li><strong>戰力全列不同。</strong>目前這套 滿星戰力：品質 2 為 288,400，品質 3 為 866,400，品質 4 為 2,174,400。"
        "資料裡另一套 滿星戰力分別為 150,400、179,500、293,500。"
        "0 星戰力同樣是 目前這套 較高（11,400／35,400／93,800 對 4,000／5,000／7,500）。</li>")
    add("<li><strong>升星消耗：品質 3／4 兩套數量相同；品質 2 從 41 星起不同。</strong>"
        "目前這套 的 品質 2 合計 4,860，資料裡另一套 合計 4,450。見升星節。</li>")
    add("<li><strong>技能文案不完全相同。</strong>資料裡另一套 的平衡胸針在 55 星起把技能名稱欄寫成秘藥之瓶那筆技能鍵；"
        "恐懼之眼 0–100 星的技能說明寫成神聖盟約的鍵，參數也不同；"
        "禁魔手銬有 21 列只差在單一參數（例如 80 星一處為 21 對 20）。名錄技能以 目前這套 為準。</li>")
    add("<li><strong>全英雄屬性基本相同，只有兩處例外：</strong>"
        "資料裡另一套 的元帥號角在 5–9 星為英雄攻擊 30、英雄生命 30（目前這套 同期為 30／60）；"
        "資料裡另一套 的石化魔杖、煌雷裁決、青藤古弓 100 星為 1800／3600（目前這套 為 2000／4000，與同品質其餘秘寶滿星一致；第 20 章只寫了石化魔杖，另兩件以升星表為準）。</li>")
    add("</ul>")
    add(p_html(
        "套裝表也是兩套 id：101–103 掛 資料裡另一套 的 5xxxx，201–203 掛 目前這套 的 15xxxx，套裝名與說明相同。"
    ))
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>名錄</h2>")
    add(p_html(
        "下列以 目前這套 的 id 為準，並附 資料裡另一套 的對應 id。"
        "說明文案兩套共用；神聖盟約至不敗華冠沒有對應的說明，不編造說明。"
        "賽季參數只照錄。"
    ))
    add(p_html(
        f"類型 1／2／3 的官方短名是「{H(o.type_names[1], terms)}」「{H(o.type_names[2], terms)}」「{H(o.type_names[3], terms)}」。"
        f"說明分別為：{H(o.type_descs[1], terms)}；{H(o.type_descs[2], terms)}；{H(o.type_descs[3], terms)}。"
        f"介面另有「{H(o.same_type_tips, terms)}」。"
    ))
    off = [a.name for a in data.artifacts if a.typ == 1]
    surv = [a.name for a in data.artifacts if a.typ == 2]
    gen = [a.name for a in data.artifacts if a.typ == 3]
    add("<ul>")
    add(f"<li>{H('進攻', terms)}（{len(off)}）：{'、'.join(H(n, terms) for n in off)}</li>")
    add(f"<li>{H('生存', terms)}（{len(surv)}）：{'、'.join(H(n, terms) for n in surv)}</li>")
    add(f"<li>{H('通用', terms)}（{len(gen)}）：{'、'.join(H(n, terms) for n in gen)}</li>")
    add("</ul>")
    add(tbl["catalog"])
    add(p_html(
        "品質 2 三件、品質 3 七件、品質 4 十九件（以一套編號計）。"
        f"品質 4 的交換道具皆為{H(o.hammer, terms)}（說明：{H(o.hammer_desc, terms)}）；"
        f"品質 2／3 為 -1。星級相同時無法交換（介面提示：{H(o.swap_tips, terms)}）。"
    ))
    add(p_html(
        f"道具說明另把「{H('電青蛙', terms)}」的合成／升星材料寫成秘寶「{H('蛙神圖騰', terms)}」"
        f"（{H(o.frog_totem_descs[0], terms)}；"
        f"{H(o.frog_totem_descs[1], terms)}），"
        "與秘寶正式名不一致，只並列記錄。"
    ))
    add("    </section>")

    add('    <section id="suits">')
    add("      <h2>套裝</h2>")
    add(p_html(
        "套裝表 6 筆，去重後 3 套，各有一組對應資料裡另一套（id 101–103，成員為 5xxxx）"
        "與目前這套（id 201–203，成員為 15xxxx）。三套都是 15 星解鎖套裝技能。"
        f"解鎖說明兩句：{H(o.suit_unlock[0], terms)}；{H(o.suit_unlock[1], terms)}。"
        "<code>{0}</code> 應對 15 星，表沒有另寫填入規則。"
        f"陣營編號 1／2／3 與士兵表{H('聯盟', terms)}／{H('部族', terms)}／{H('自然', terms)}編號相同。"
    ))
    add(tbl["suits"])
    add(p_html(
        f"字串另有套裝名「{H(o.power_suit_name, terms)}」，說明：「{H(o.power_suit_desc, terms)}」。"
        "套裝表沒有這一套，本頁不把它算進 3 套之內。"
        "「傳奇」與表上品質 2／3／4 如何對應，未驗證。"
    ))
    has_origin = [a.name for a in data.artifacts if a.suit_origin not in (-1, 0)]
    no_origin = [a.name for a in data.artifacts if a.name in ("契約之羽", "龍骸護符", "神聖盟約")]
    add(p_html(
        "升星表部分秘寶另有套裝來源編號（"
        + "、".join(H(n, terms) for n in has_origin)
        + "），與上列套裝成員大致相符，但"
        + "、".join(H(n, terms) for n in no_origin)
        + "這欄為 -1。套裝技能在本抽取沒有對到獨立技能文案表，效果以套裝說明為準。"
    ))
    add("    </section>")

    add('    <section id="upgrade">')
    add("      <h2>升星、消耗與屬性</h2>")
    add(p_html(
        "每件 0–100 星。0 星列沒有升星消耗（該欄為空）；"
        "首次合成解鎖與 0 星的關係，規則字串有寫「首次合成會解鎖」，表沒有另列解鎖消耗，只有定義表寫碎片數量 10。"
    ))
    add(p_html(
        "消耗欄是 <code>[物品id, 數量]</code>，物品 id 為 303001–303003、304001–304007、305001–305019，"
        "與定義表的碎片編號／合成式／重複獲得欄同一組。"
        "字串表沒有這組升星材料的官方短名。"
        f"另有道具說明寫「{H(o.chip_descs_example[0], terms)}」，"
        f"以及「{H(o.chip_descs_example[1], terms)}」。"
        "本頁不把 303001、330011、363001 這三組 id 自行當成同一件道具。"
        f"通用碎片 220201／220202／220203 名稱為{H(o.generic_chips[220201][0], terms)}／"
        f"{H(o.generic_chips[220202][0], terms)}／{H(o.generic_chips[220203][0], terms)}，"
        f"說明為「{H(o.generic_chips[220201][1], terms)}／{H(o.generic_chips[220202][1], terms)}／{H(o.generic_chips[220203][1], terms)}」；"
        "升星消耗欄沒有列出通用碎片的替代規則。"
    ))
    add(p_html("數量曲線按品質（同一品質各件數量相同，只是物品 id 不同）。品質 3／4 兩套編號數量相同；品質 2 從 41 星起分岔。"))
    add(p_html("品質 2（目前這套 合計 4,860；資料裡另一套 在 41–45 星為 18、46–50 星為 20、66–70 星為 70、71–75 星為 80，合計 4,450）："))
    add(tbl["cost_q2"])
    add(p_html("品質 3（兩套皆合計 3,150）："))
    add(tbl["cost_q3"])
    add(p_html("品質 4（兩套皆合計 1,800）："))
    add(tbl["cost_q4"])
    add(p_html(
        "等級與技能顯示等級同品質全件相同（兩套編號也相同）。"
        "品質 2：0–4 星為等級 1，之後每 5 星升 1 級，50–100 星維持等級 11、技能顯示等級 10。"
        "品質 3：0–4 星為等級 1，之後每 5 星升 1 級，60–100 星維持等級 13、技能顯示等級 12。"
        "品質 4：0–4 星為等級 1／技能顯示等級 0，其後每 5 星升一檔，100 星為等級 21、技能顯示等級 20。"
        "技能解鎖星見名錄，與技能顯示等級的對應不是簡單的「解鎖星＝顯示等級」，本頁不自行對齊。"
        "第 20 章升星節摘要曾把品質 3 的 100 星寫成等級 16／15，與同章各件技能小節及升星表不符，本頁以表為準。"
    ))
    add(p_html(
        f"自身{H(o.atk, terms)}／{H(o.hp, terms)}同品質全件相同。"
        f"品質 3／4 另有{H(o.dmg_up, terms)}或{H(o.dmg_cut, terms)}，或兩者都有，按件列出。"
        f"全英雄加成是{H(o.hero_atk, terms)}、{H(o.hero_hp, terms)}，同品質曲線相同（目前這套；"
        "資料裡另一套的兩處例外見上）。"
    ))
    add(tbl["attrs"])
    add(p_html(
        "品質 4 的 0 星攻擊／生命與 100 星攻擊／生命，三件類型都是 2780／19100 與 65180／435400"
        "（與附加屬性無關，全件相同；升星表三欄數值一致，欄名見資料說明）。"
        "附加屬性（目前這套與資料裡另一套相同）："
    ))
    add("<ul>")
    add(f"<li>品質 2：沒有{H(o.dmg_up, terms)}或{H(o.dmg_cut, terms)}。</li>")
    q3_up = [a.name for a in data.artifacts if a.quality == 3 and 18 in a.extra0]
    q3_cut = [a.name for a in data.artifacts if a.quality == 3 and 19 in a.extra0]
    add("<li>品質 3："
        + "、".join(H(n, terms) for n in q3_up)
        + f"為{H(o.dmg_up, terms)}，0 星 50、100 星 1750；"
        + "、".join(H(n, terms) for n in q3_cut)
        + f"為{H(o.dmg_cut, terms)}，0 星 50、100 星 1750。"
        f"{H('恐懼之眼', terms)}是通用型，附加的是{H(o.dmg_up, terms)}不是{H(o.dmg_cut, terms)}。</li>")
    add("<li>品質 4 進攻型（含青藤古弓）："
        f"{H(o.dmg_up, terms)} 0 星 200、100 星 3500。</li>")
    add(f"<li>品質 4 生存型：{H(o.dmg_cut, terms)} 0 星 200、100 星 3500。</li>")
    add(f"<li>品質 4 通用型：{H(o.dmg_up, terms)}與{H(o.dmg_cut, terms)}各 0 星 100、100 星 1750。</li>")
    add("</ul>")
    add(p_html(
        "中間星級的附加屬性幾乎每星上調，不在本頁逐星列出。"
        "技能屬性輔表按類型 3／4／5"
        "（與定義表的技能屬性類型、品質 2／3／4 對應）給攻擊、生命值、暴擊傷害（值固定 10000）曲線；"
        "三型都是 1–40 級共 40 列，且攻擊／生命／暴擊傷害曲線彼此相同。"
        "第 20 章曾寫級數分別到 11／16／40，與輔表不符，本頁以表為準。"
        "與升星表同級的攻擊／生命並不一致（例如 品質 2、等級 1 升星表為 340／2300，輔表為 90／900）。"
        "兩者關係未驗證，本頁不以輔表覆蓋升星表，也不把 120 列整表倒進頁面。"
    ))
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>技能</h2>")
    add(p_html(
        "技能名稱與描述取自目前這套升星表的技能名稱、說明與參數。"
        "多數技能名稱取自對應名稱；神聖盟約起改把技能名稱欄寫成秘寶名，顯示會與秘寶同名，不是另有技能短名。對照見資料說明。"
        "下列每件先寫 0 星，再寫 100 星。中間解鎖星只改參數，不逐段展開。"
        "煌雷裁決、龍骸護符、青藤古弓在 0–100 星的技能說明與參數皆為空，只錄「無技能說明」，不從其他表補文案。"
    ))
    for a in data.artifacts:
        add(f'    <h3 id="skill-{a.id_v1}">{H(a.name, terms)}（{a.id_v1}／{a.id_vm1}，{H(a.type_name, terms)}，品質 {a.quality}）</h3>')
        note = ""
        if a.skill0.name_is_artifact:
            note = "技能顯示與秘寶同名，不是另有技能短名。"
        add(p_html(
            f"解鎖星：{e(format_unlock_stars(a.unlock))}。0 星技能名「{H(a.skill0.name, terms)}」，"
            f"100 星技能名「{H(a.skill100.name, terms)}」。{H(note, terms) if note else ''}"
        ))
        add(tbl["skills"][a.id_v1])
    add("    </section>")

    add('    <section id="honor">')
    add(f"      <h2>{H('榮譽牆', terms)}</h2>")
    add(p_html(
        f"官方說明：{H(o.honour_lines['artifact_honour_004'], terms)}；"
        f"{H(o.honour_lines['artifact_honour_002'], terms)}；"
        f"{H(o.honour_unlock, terms)}。"
        "（榮譽說明各句出處見資料說明）。"
    ))
    add(p_html(
        "榮譽牆表 3 筆，按品質 2／3／4："
        f"附加屬性為{H(o.hp, terms)} 40／80／160，戰力 160／880／1760。"
        "碎片欄三筆都是 200|10,300|20,400|30,600|30。"
        "這四個數字在表上沒有標題，本頁不自行解釋成哪一種碎片或等級。"
    ))
    add(tbl["honor"])
    add(p_html(
        "榮譽牆加成表 30 筆，按秘寶組分成 6 組，"
        "門檻為榮譽等級 50／100／150／200／300（沒有 250）。"
        f"1301／1401／1501 加{H(o.hero_atk, terms)}，1302／1402／1502 加{H(o.hero_hp, terms)}。"
        "各組成員見名錄「榮譽組」欄。數值是原值。"
    ))
    add(tbl["bonus"])
    add(p_html(
        "同一組在兩套編號裡都會出現（例如 1301 同時掛平衡胸針的 30002 與 130002）。"
        "榮譽牆如何計算「等級」、兩套 id 是否分開累計，表上沒有說明，不要猜。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(f"<li>{H('英雄裝備', terms)}、{H('專武', terms)}、{H('領主裝備', terms)}；城堡裝飾「秘寶之劍」。</li>")
    add("<li>紫金秘寶等活動、秘寶禮包與儲值檔位、秘寶隨機箱／自選箱的完整開箱表、秘寶占卜與秘寶卷軸。</li>")
    add("<li>尋寶／寶藏相關表。</li>")
    add(f"<li>字串中的「{H(o.power_suit_name, terms)}」套裝（表上無列）、套裝技能的獨立文案、以及「傳奇(含)以上品質」與品質 2／3／4 的對應。</li>")
    add("<li>秘寶大廳全部 2,077 級的中間值，以及兩欄數值與「倍率／轉化率」三個名稱的逐欄對應。</li>")
    add("<li>升星 1–99 星的逐星屬性與中間技能參數；技能屬性輔表與升星表的關係。</li>")
    add("<li>通用碎片如何折算進合成或升星；303001 與 330011／363001 是否為同一道具。</li>")
    add("<li>賽季參數與賽季日曆的對應（不標未開放）。</li>")
    add(f"<li>編隊面板「秘寶 52.50%」的完整加總式（只記沒有單一列{H(o.dmg_up, terms)} 5250 或{H(o.dmg_cut, terms)} 5250，以及 3500＋1750 這個數字對得上）。</li>")
    add("<li>與英雄技能、站位、士兵的搭配模擬。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add("<ul>")
    add("<li>以下是整理用註記，查名錄與效果可略過。</li>")
    add(
        "<li>技能解鎖星可見寫成「0、4、7、11 星」或「0、7、13、21 星；另一套 4、10、16 星」；"
        "原值記法是 <code>0|4|7|11</code>、<code>0|7|13|21,4|10|16</code> 這種用 | 與逗號分套的寫法。"
        "本頁不把解鎖星自行對齊 <code>skillShowLevel</code>。"
        f"秘寶大廳 0 級前置可見寫成{H('城堡', terms)} 12 級，原值 <code>117|12</code>（建築 117 官方名稱是城堡）。"
        "可見大廳不再寫建築 140，建築編號 140 對照見此；可見表頭不再附（1097），屬性 1097 原值見此。額外秘寶插槽可見寫 0／1／2（對應 0–20、21–34、35–2076 級），原值 <code>1097|0|1</code>、<code>1097|1|1</code>、<code>1097|2|1</code>。"
        "技能表「等級」「技能顯示等級」原名 <code>level</code>、<code>skillShowLevel</code>，數字不改。可見名錄「目前這套／資料裡另一套」對應 <code>version=1</code>／<code>version=-1</code>；可見「組別」對應組編號；青藤古弓組編號 1502。可見「前面等級的解鎖／升級前置」對應前置早期欄。可見「賽季參數」原名 <code>SeasonParam</code>，只照錄，不對成賽季日曆。可見技能改寫「取自對應名稱」「寫成秘寶名」「技能顯示與秘寶同名」，名稱鍵對照見此：多數是 <code>hero_skill_name_*</code>；神聖盟約起 <code>skill_name</code> 寫成 <code>artifact_name_*</code>。可見「套裝技能的獨立文案」對應 <code>suit_skill</code>。神聖盟約至不敗華冠沒有說明鍵 <code>artifact_desc_50012</code>–<code>50019</code>。兩張建築升級表原名 <code>citybuilding_lvup</code>／<code>citybuilding_lvup_new</code>。大廳說明第三鍵在表上少了首字，原名 <code>uilding_lvup_des_115003</code>；相近另一鍵是 <code>building_lvup_des_115003</code>。可見表頭「0 星戰力」「100 星戰力」寫目前這套，括號內為資料裡另一套，來源是 <code>version=1</code>／<code>version=-1</code>。可見「0 星／100 星英雄攻擊／英雄生命」對應屬性 103／104；自身攻擊／生命對應 3／4；增傷／減傷對應 18／19。榮譽牆附加屬性「生命值」對應 4。技能文案同一列多段 <code>desc</code> 都從 <code>{0}</code> 起算，此規則只寫在資料說明。數值兩欄原名 <code>para1</code>／<code>para2</code>（<code>para3</code> 全 0）；可見表頭寫「數值 1／數值 2」。可見不再寫「字串參數」與 id 20005／20006，大廳字串參數原名 <code>string_para1</code>，編號對照見後列屬性顯示；建造時間原名 <code>buildTime</code>。榮譽牆解鎖字串原名 <code>artifact_honour_005</code>。碎片數量原名 <code>fragment_num</code>；榮譽牆附加屬性原名 <code>attribute_up</code>，碎片欄原名 <code>need_chip</code>。</li>"
    )
    add(
        "<li>只有品質 4（<code>quality=4</code>）的秘寶 <code>exchange_goods=514</code>（奇蹟之錘）。"
        "技能文案以 <code>artifact_star_up</code> 的 <code>skill_desc</code> 填入 <code>skill_desc_parameter</code> 後照錄；"
        "同一列多段 <code>desc</code> 都從 <code>{0}</code> 起算。"
        "套裝 <code>race</code> 1／2／3 與士兵表聯盟／部族／自然編號相同。"
        "不要從 SeasonParam 或其他季節、活動欄自動標未開放。"
        "品質 4 的 0 星攻擊／生命用 2780／19100。第 20 章升星節摘要曾把品質 4 的 0 星攻擊／生命寫成 3530／23600，該數字未出現在升星表，本頁以表為準（2780／19100）。"
        "編號 20006 不得冒用 20004 的官方名「秘寶生命」。"
        "<code>show_type=2</code> 只記原值（天賦面板已鎖定例外除外，本頁不套用那套例外）。</li>"
    )
    add("<li><strong>定義表：</strong>"
        "定義在 <code>artifact.json</code>（58 筆），升星在 <code>artifact_star_up.json</code>（5,858 筆，每件 0–100 星共 101 列），"
        "套裝在 <code>artifact_suit.json</code>（6 筆），榮譽在 <code>artifact_honor.json</code>（3 筆）與 "
        "<code>artifact_honor_bonus.json</code>（30 筆），技能屬性輔表在 <code>artifact_skill_attr.json</code>（120 筆）。"
        f"{H('秘寶大廳', terms)}升級在 <code>citybuilding_lvup.json</code>／<code>citybuilding_lvup_new.json</code>"
        "（建築 <code>index</code> 140，兩表此建築 0–2076 級數值相同）。"
        "官方界面名稱鍵是 <code>artifact_system_name</code>。"
        "</li>")
    add("<li><strong>兩套編號：</strong>"
        "58 筆是 29 個中文名的兩套編號。<code>version=-1</code> 用 3xxxx／4xxxx／5xxxx，"
        "<code>version=1</code> 用 13xxxx／14xxxx／15xxxx。"
        "名錄與技能以 <code>version=1</code> 為準列出，並註明與 <code>version=-1</code> 的差別。"
        "不要從 <code>SeasonParam</code> 自動標未開放。</li>")
    add("<li><strong>屬性顯示：</strong>屬性名優先用 <code>attribute_name_{id}</code>。"
        f"{H(o.atk, terms)}、{H(o.hp, terms)}（3／4，點數）的 <code>show_type</code> 為 1；"
        f"{H(o.hero_atk, terms)}、{H(o.hero_hp, terms)}（103／104，百分比類）與{H(o.dmg_up, terms)}、{H(o.dmg_cut, terms)}（18／19）"
        "的 <code>show_type</code> 為 2。本頁只錄原值，不自行換算成百分比。"
        "升星表 <code>newFightAttrs</code>／大廳 <code>string_para1</code> 另用 id 20005／20006，"
        f"其 <code>name</code> 欄指向 <code>attribute_name_20003</code>／<code>20004</code>（{H(o.art_atk, terms)}／{H(o.art_hp, terms)}），"
        "字串表沒有 <code>attribute_name_20005</code>／<code>20006</code>。</li>")
    add(f"<li>{_data_notes(data)}</li>")
    add("<li>待補：客戶端實際讀 <code>version=-1</code> 還是 <code>version=1</code>；"
        "大廳 para 欄與倍率／轉化率的對應，以及插槽解鎖字串與表不一致的原因；"
        "碎片三組 id 的關係；「秘寶之力」與「傳奇」品質用字；面板 52.50% 的完整來源；活動與取得途徑。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {ARTIFACT_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_artifact_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def _build_md_tables(data: TablesData) -> dict[str, str]:
    o = data.official
    hall = md_table(
        ["大廳等級", "para1", "para2", f"{o.slot_name}（1097）", "戰力", "備註"],
        [[str(r.lv), str(r.para1), str(r.para2), str(r.slot), str(r.fightforce), r.note] for r in data.hall],
    )
    catalog_rows = []
    for a in data.artifacts:
        desc = "（無說明字串）" if a.desc_missing else a.desc
        catalog_rows.append([
            a.name, str(a.id_v1), str(a.id_vm1), str(a.quality),
            f"{a.typ} {a.type_name}", str(a.group_id), a.season,
            format_unlock_stars(a.unlock), desc,
        ])
    catalog = md_table(
        ["名稱", "現行編號", "另一套編號", "品質", "類型", "榮譽組", "賽季參數（只照錄）", "技能解鎖星", "說明"],
        catalog_rows,
    )
    suit_rows = []
    for s in data.suits:
        suit_rows.append([
            s.name, f"{s.race} {s.race_name}", str(s.id_v1), str(s.id_vm1),
            "、".join(s.members), s.desc.replace("\n", "；"),
        ])
    suits = md_table(
        ["套裝", "陣營", "現行編號", "另一套編號", "成員", "官方說明（原文）"],
        suit_rows,
    )
    cost_q2 = md_table(
        ["版本"] + _cost_headers(Q2_V1_BANDS),
        [
            ["version=1"] + _cost_qty_row(Q2_V1_BANDS, lambda lo: qty_at(Q2_V1_BANDS, lo)),
            ["version=-1"] + _cost_qty_row(Q2_V1_BANDS, _q2_vm1_qty),
        ],
    )
    cost_q3 = md_table(
        _cost_headers(Q3_BANDS),
        [_cost_qty_row(Q3_BANDS, lambda lo: qty_at(Q3_BANDS, lo))],
    )
    cost_q4 = md_table(
        _cost_headers(Q4_BANDS),
        [_cost_qty_row(Q4_BANDS, lambda lo: qty_at(Q4_BANDS, lo))],
    )
    attr_rows = []
    for q in (2, 3, 4):
        exp = ATTR_SUMMARY[q]
        attr_rows.append([
            str(q),
            f"{exp['atk0']}／{exp['hp0']}",
            f"{exp['atk100']}／{exp['hp100']}",
            f"{exp['h0'][0]}／{exp['h0'][1]}",
            f"{exp['h100'][0]}／{exp['h100'][1]}",
            f"{exp['ff0'][0]}（{exp['ff0'][1]}）",
            f"{exp['ff100'][0]}（{exp['ff100'][1]}）",
        ])
    attrs = md_table(
        ["品質", "0 星攻擊／生命", "100 星攻擊／生命", "0 星全英雄（103／104）", "100 星全英雄", "0 星戰力 v1（v-1）", "100 星戰力 v1（v-1）"],
        attr_rows,
    )
    honor = md_table(
        ["品質", "attribute_up", "戰力", "need_chip（表上無標題）"],
        [[str(r.quality), f"{r.attr_name}（{r.attr_id}） {r.attr_value}", str(r.combat), r.need_chip] for r in data.honor],
    )
    bonus_rows = []
    for r in data.honor_bonus:
        bonus_rows.append(
            [str(r.group), f"{r.attr_name}（{r.attr_id}）"]
            + [str(r.values[lv]) for lv in (50, 100, 150, 200, 300)]
            + [f"{r.combats[50]}–{r.combats[300]}"]
        )
    bonus = md_table(
        ["榮譽組", "屬性", "50", "100", "150", "200", "300", "對應戰力"],
        bonus_rows,
    )
    skills: dict[int, str] = {}
    for a in data.artifacts:
        rows = []
        for snap in (a.skill0, a.skill100):
            name = snap.name or EMPTY
            if snap.name_is_artifact:
                name += "（技能名鍵是秘寶名鍵，顯示與秘寶同名）"
            rows.append([
                f"{snap.star} 星",
                str(snap.level),
                str(snap.show_level),
                name,
                format_params(snap.params),
                _skill_cell_plain(snap),
            ])
        skills[a.id_v1] = md_table(
            ["星級", "等級", "技能顯示等級", "技能名", "參數", "技能文案"],
            rows,
        )
    return {
        "hall": hall, "catalog": catalog, "suits": suits,
        "cost_q2": cost_q2, "cost_q3": cost_q3, "cost_q4": cost_q4,
        "attrs": attrs, "honor": honor, "bonus": bonus, "skills": skills,
    }


def render_markdown(data: TablesData) -> str:
    o = data.official
    tbl = _build_md_tables(data)
    lines: list[str] = []
    add = lines.append
    add("# Top Heroes Wiki｜秘寶總表")
    add("")
    add(LEDE)
    add("")
    add(_data_notes(data))
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add(
        "正文只根據遊戲資料表與官方字串，不評定秘寶強弱，也不排行。"
        f"官方界面名稱是「{o.system_name}」（`artifact_system_name`）；資料表檔名是 `artifact*`。"
        "分類目錄把這批表寫成「神器（Artifact）」，與界面用字不同；本頁跟界面，稱「秘寶」。"
        "英雄四件套裝備見[裝備總表](equipment.html)，"
        "領主裝備見[領主裝備總表](lord-equipment.html)，士兵見[士兵總表](troops.html)。"
        "已發佈的 [專武總表](exclusive.html) 是英雄專武。"
        "英雄裝備、專武、領主裝備都不是秘寶。"
    )
    add("")
    add(
        "- **本頁只寫可佩戴到隊列上的秘寶系統。**定義在 `artifact.json`（58 筆），升星在 `artifact_star_up.json`"
        "（5,858 筆，每件 0–100 星共 101 列），套裝在 `artifact_suit.json`（6 筆），榮譽在 `artifact_honor.json`（3 筆）"
        "與 `artifact_honor_bonus.json`（30 筆），技能屬性輔表在 `artifact_skill_attr.json`（120 筆）。"
        "秘寶大廳升級在 `citybuilding_lvup.json`／`citybuilding_lvup_new.json`（建築 `index` 140，兩表此建築 0–2076 級數值相同）。"
    )
    add(
        "- **58 筆是 29 個中文名的兩套編號。**`version=-1` 用 3xxxx／4xxxx／5xxxx，`version=1` 用 13xxxx／14xxxx／15xxxx。"
        "同一中文名的品質、類型、碎片 id、`SeasonParam`、技能解鎖星兩套相同；升星表裡攻擊／生命與附加的增傷、減傷兩套也相同。"
        "戰力、部分升星消耗、以及少數技能文案／全英雄屬性並不完全相同，見「兩套編號」。"
        "名錄與技能以 `version=1` 為準列出，並註明與 `version=-1` 的差別。本頁不自行斷定客戶端目前讀哪一套。"
    )
    add("- **不要從 `SeasonParam` 自動標未開放。**欄位本身沒有「已推出」旗標，只照錄。")
    add(
        "- **屬性名**優先用 `attribute_name_{id}`。攻擊、生命值（3／4）的 `show_type` 為 1；"
        "英雄攻擊、英雄生命（103／104）與增傷、減傷（18／19）的 `show_type` 為 2。本頁只錄原值，不自行換算成百分比。"
        "升星表 `newFightAttrs`／大廳 `string_para1` 另用 id 20005／20006，其 `name` 欄指向 `attribute_name_20003`／`20004`"
        "（秘寶攻擊／秘寶生命），字串表沒有 `attribute_name_20005`／`20006`。"
    )
    add(
        f"- **品質欄是表上的 2／3／4。**任務與道具字串有「藍色品質秘寶／紫色品質秘寶／橙色品質秘寶」；"
        f"{o.hammer}說明寫「橙色秘寶」，且只有 quality=4 的秘寶 `exchange_goods=514`。"
        "品質欄仍錄數字，不把任務鍵編號自行解釋成另一套枚舉，也不把「傳奇(含)以上品質」強行對成 2／3／4。"
    )
    add(
        "- 技能文案以 `artifact_star_up` 的 `skill_desc` 填入 `skill_desc_parameter` 後照錄。"
        "同一列若有多段 desc，每段都從 `{0}` 起算，多餘參數不自行挪給下一段；對不上的地方改並列原文與參數。"
    )
    add("- 官方用語是「部族」不是「部落」。本頁用到的秘寶字串沒有「部落」。套裝 `race` 1／2／3 與士兵表聯盟／部族／自然編號相同。")
    add("")
    add("## 範圍")
    add("")
    add(
        f"介面寫：{o.buff_desc.replace(chr(10)*2, '；')}（`artifact_system_buff_desc`）。"
        f"另有「{o.name_dec}」（`artifact_system_name_dec`）。"
        "影響力目錄把「秘寶」「秘寶榮譽牆」放在「隊伍提升」底下（`influence_level` 類型 `ARTIFACT`／`ARTIFACT_HONOR`）。"
    )
    add("")
    add("官方用「秘寶」這兩個字的，不只這一系統。活動與道具、尋寶／寶藏表、城堡裝飾等不在本頁展開，見「本頁未列入」。`function.json` 沒有以「秘寶」為名的功能列。")
    add("")
    add("## 系統規則（官方字串）")
    add("")
    add("資料裡有兩套規則文案，用字不完全相同，一併照錄，不自行判斷哪一套是目前介面。")
    add("")
    add("`artifact_system_rules`：")
    add("")
    add(o.rules)
    add("")
    add("`artifact_system_rules_new`：")
    add("")
    add(o.rules_new)
    add("")
    add(
        "與 `artifact_system_rules_new` 並列的 `artifact_info_*` 用字也不完全相同，同樣照錄。"
        f"`artifact_info_002` 寫「{o.info['artifact_info_002']}」，沒有「途徑」二字。"
        f"`artifact_info_003` 把公式寫成「上陣英雄攻擊／上陣英雄生命」：{o.info['artifact_info_003']}"
    )
    add("")
    add(
        f"`artifact_info_006`：{o.info['artifact_info_006']}"
        f"`artifact_info_007`：{o.info['artifact_info_007']}"
        "與升級表欄位的對照見下節，兩處不完全相同，只並列記錄，不作顯示結論。"
    )
    add("")
    add("所有 58 筆的 `fragment_num` 都是 10。合成與升星消耗的物品 id 見升星節。")
    add("")
    add("## 秘寶大廳")
    add("")
    add(
        f"建築 140，官方名稱「{o.hall_name}」，說明：「{o.hall_des}」。"
        f"解鎖／升級前置寫在 `pre_building_level`，早期級是{o.castle}（建築 117）達到指定等級，"
        "例如 0 級列為城堡 12 級；40 級起這欄為空。"
    )
    add("")
    add(
        "升級表 0–2076 級，共 2,077 列。`citybuilding_lvup` 與 `citybuilding_lvup_new` 此建築數值相同。"
        f"每級 `des` 三個鍵依序是「{o.atk_up}」「{o.hp_up}」「{o.attr_up}」"
        "（第三個鍵在表上少了首字，寫成 `uilding_lvup_des_115003`，字串內容確是"
        f"「{o.typo_des}」；相近的 `building_lvup_des_115003` 是「{o.wrong_des}」，不是同一鍵）。"
        "數值欄是 `para1`／`para2`（`para3` 全表為 0）。"
        "表沒有把這兩欄逐一標上上述三個名稱，本頁只列出各級 `para1`／`para2`，不自行指定哪一欄是倍率、哪一欄是轉化率。"
    )
    add("")
    add(
        f"`string_para2` 是屬性 1097「{o.slot_name}」。官方說明寫 20 級、50 級解鎖額外位置（`artifact_info_007`）；"
        "表上這欄是額外秘寶插槽 0／1／2（對應 0–20、21–34、35–2076 級）。官方說明寫 20 級、50 級解鎖，與表上這欄對不上，只並列記錄。"
        "兩處對不上，只並列記錄，不作顯示結論。"
    )
    add("")
    add(
        f"`string_para1` 從 1 級起寫{o.atk}、{o.hp}、以及 id 20005／20006（名稱欄指向{o.art_atk}／{o.art_hp}），"
        "數值隨大廳等級增加，例如 1 級為 13535、2076 級為 37771。這組與 `para1`／`para2` 的換算關係表上沒寫。"
    )
    add("")
    add(
        f"消耗：0–39 級為類型 999、資源 4／5（頂欄名稱為{o.wood}／{o.stone}），並有建造時間；"
        f"40–2075 級改為道具 237「{o.magic_stone}」與 238「{o.arcane}」；多數列的 `buildTime` 為 -1，但 440–478 與 1440–1478 共 78 級為 0；2076 級沒有再升級消耗。"
        "這與「額外需要使用奧術水晶升級時無法暴擊」的字串相符，但表沒有標哪一級開始算「額外使用奧術水晶」。"
    )
    add("")
    add(f"榮譽牆解鎖字串：「{o.honour_unlock}」（`artifact_honour_005`）。")
    add("")
    add("`para1` 從 1 級的 1000 起跳，共 129 個不同值，滿級 3440；`para2` 從 1 級的 1 增至 199，共 200 個不同值。完整 2,077 級不在本頁逐列。")
    add("")
    add(tbl["hall"])
    add("")
    add(
        "戰鬥公式分析裡，編隊面板有「秘寶 52.50%」作為增傷／減傷的來源分項；"
        "本抽取沒有單一列 18｜5250 或 19｜5250，可能是加總，只能載為面板來源，不編造表 id。"
        "單件 quality 4、`version=1` 滿星時，進攻型自身增傷原值 3500，生存型自身減傷原值 3500，通用型兩項各 1750；"
        "3500＋1750＝5250，與面板那個分項數字相同，但表與官方說明都沒有把這兩件寫成固定搭配，不作唯一來源結論。"
        "完整加總式不在本頁展開。"
    )
    add("")
    add("## 兩套編號")
    add("")
    add(
        "29 個中文名各自有一筆 `version=-1` 與一筆 `version=1`，碎片、品質、類型、`group_id`、`SeasonParam`、技能解鎖星相同。"
        "升星表中，自身攻擊／生命（3／4）與附加的增傷／減傷（18／19）兩套一致；`level` 與 `skillShowLevel` 也一致。差別如下："
    )
    add("")
    add(
        "- **戰力全列不同。** `version=1` 滿星戰力：quality 2 為 288,400，quality 3 為 866,400，quality 4 為 2,174,400。"
        "`version=-1` 滿星戰力分別為 150,400、179,500、293,500。0 星戰力同樣是 `version=1` 較高（11,400／35,400／93,800 對 4,000／5,000／7,500）。"
    )
    add("- **升星消耗：quality 3／4 兩套數量相同；quality 2 從 41 星起不同。** `version=1` 的 quality 2 合計 4,860，`version=-1` 合計 4,450。見升星節。")
    add(
        "- **技能文案不完全相同。** `version=-1` 的平衡胸針在 55 星起把 `skill_name` 寫成秘藥之瓶那筆技能鍵；"
        "恐懼之眼 0–100 星的 `skill_desc` 寫成神聖盟約的鍵，參數也不同；禁魔手銬有 21 列只差在單一參數（例如 80 星一處為 21 對 20）。"
        "名錄技能以 `version=1` 為準。"
    )
    add(
        "- **全英雄屬性（103／104）基本相同，只有兩處例外：** `version=-1` 的元帥號角在 5–9 星為英雄攻擊 30、英雄生命 30"
        "（`version=1` 同期為 30／60）；`version=-1` 的石化魔杖、煌雷裁決、青藤古弓 100 星為 1800／3600（`version=1` 為 2000／4000，與同品質其餘秘寶滿星一致；第 20 章只寫了石化魔杖，另兩件以升星表為準）。"
    )
    add("")
    add("套裝表也是兩套 id：101–103 掛 `version=-1` 的 5xxxx，201–203 掛 `version=1` 的 15xxxx，套裝名與說明相同。")
    add("")
    add("## 名錄")
    add("")
    add(
        "下列以 `version=1` 的 id 為準，並附 `version=-1` 的對應 id。"
        "說明文案取自 `artifact_desc_3xxxx`／`4xxxx`／`5xxxx`（兩套編號共用這組鍵）；"
        "神聖盟約至不敗華冠沒有對應的 `artifact_desc_50012`–`50019`，不編造說明。`SeasonParam` 只照錄。"
    )
    add("")
    add(
        f"類型 1／2／3 的官方短名是「{o.type_names[1]}」「{o.type_names[2]}」「{o.type_names[3]}」。"
        f"說明分別為：{o.type_descs[1]}；{o.type_descs[2]}；{o.type_descs[3]}。"
        f"介面另有「{o.same_type_tips}」。"
    )
    add("")
    off = [a.name for a in data.artifacts if a.typ == 1]
    surv = [a.name for a in data.artifacts if a.typ == 2]
    gen = [a.name for a in data.artifacts if a.typ == 3]
    add(f"- 進攻（{len(off)}）：{'、'.join(off)}")
    add(f"- 生存（{len(surv)}）：{'、'.join(surv)}")
    add(f"- 通用（{len(gen)}）：{'、'.join(gen)}")
    add("")
    add(tbl["catalog"])
    add("")
    add(
        "quality 2 三件、quality 3 七件、quality 4 十九件（以一套編號計）。"
        f"quality 4 的 `exchange_goods` 皆為 514（{o.hammer}，說明：{o.hammer_desc}）；quality 2／3 為 -1。"
        f"星級相同時無法交換（`artifact_swap_tips1`：{o.swap_tips}）。"
    )
    add("")
    add(
        f"道具說明另把「電青蛙」的合成／升星材料寫成秘寶「蛙神圖騰」"
        f"（`goods_desc_340061`、{o.frog_totem_descs[0]}；`goods_desc_364006`、{o.frog_totem_descs[1]}），"
        "與秘寶正式名不一致，只並列記錄。"
    )
    add("")
    add("## 套裝")
    add("")
    add(
        "`artifact_suit.json` 6 筆，去重後 3 套，各有一組對應 `version=-1`（id 101–103，成員為 5xxxx）"
        "與 `version=1`（id 201–203，成員為 15xxxx）。三套 `suit_skill_star` 皆為 15。"
        f"解鎖說明兩句：{o.suit_unlock[0]}；{o.suit_unlock[1]}。`{{0}}` 應對 15 星，表沒有另寫填入規則。"
        " `race` 1／2／3 與士兵表聯盟／部族／自然編號相同。"
    )
    add("")
    add(tbl["suits"])
    add("")
    add(
        f"字串另有套裝名「{o.power_suit_name}」（`ui_artifact_suit_name_04`），說明：「{o.power_suit_desc}」。"
        "`artifact_suit.json` 沒有這一套，本頁不把它算進 3 套之內。「傳奇」與表上品質 2／3／4 如何對應，未驗證。"
    )
    add("")
    has_origin = [a.name for a in data.artifacts if a.suit_origin not in (-1, 0)]
    no_origin = [a.name for a in data.artifacts if a.name in ("契約之羽", "龍骸護符", "神聖盟約")]
    add(
        "升星表部分秘寶另有 `suit_originID`（" + "、".join(has_origin) + "），與上列套裝成員大致相符，但"
        + "、".join(no_origin) + "這欄為 -1。套裝技能 id（`suit_skill`）在本抽取沒有對到獨立技能文案表，效果以套裝說明為準。"
    )
    add("")
    add("## 升星、消耗與屬性")
    add("")
    add("每件 0–100 星。0 星列沒有升星消耗（`star_up_cost` 為空）；首次合成解鎖與 0 星的關係，規則字串有寫「首次合成會解鎖」，表沒有另列解鎖消耗，只有定義表 `fragment_num=10`。")
    add("")
    add(
        "消耗欄是 `[物品id, 數量]`，物品 id 為 303001–303003、304001–304007、305001–305019，"
        "與定義表 `FragmentId`／`fragment_formula`／`repeat_get` 同一組。字串表沒有 `goods_name_303001` 這組名稱。"
        f"另有 `goods_desc_330011` 等寫「{o.chip_descs_example[0]}」，以及 `goods_desc_363001` 等寫「{o.chip_descs_example[1]}」。"
        "本頁不把 303001、330011、363001 這三組 id 自行當成同一件道具。"
        f"通用碎片 220201／220202／220203 名稱為{o.generic_chips[220201][0]}／{o.generic_chips[220202][0]}／{o.generic_chips[220203][0]}，"
        f"說明為「{o.generic_chips[220201][1]}／{o.generic_chips[220202][1]}／{o.generic_chips[220203][1]}」；"
        "升星消耗欄沒有列出通用碎片的替代規則。"
    )
    add("")
    add("數量曲線按品質（同一品質各件數量相同，只是物品 id 不同）。quality 3／4 兩套編號數量相同；quality 2 從 41 星起分岔。")
    add("")
    add("quality 2（`version=1` 合計 4,860；`version=-1` 在 41–45 星為 18、46–50 星為 20、66–70 星為 70、71–75 星為 80，合計 4,450）：")
    add("")
    add(tbl["cost_q2"])
    add("")
    add("quality 3（兩套皆合計 3,150）：")
    add("")
    add(tbl["cost_q3"])
    add("")
    add("quality 4（兩套皆合計 1,800）：")
    add("")
    add(tbl["cost_q4"])
    add("")
    add(
        "`level` 與 `skillShowLevel` 同品質全件相同（兩套編號也相同）。"
        "quality 2：0–4 星為 level 1，之後每 5 星升 1 級，50–100 星維持 level 11、`skillShowLevel` 10。"
        "quality 3：0–4 星 level 1，之後每 5 星升 1 級，60–100 星維持 level 13、`skillShowLevel` 12。"
        "quality 4：0–4 星 level 1／`skillShowLevel` 0，其後每 5 星升一檔，100 星為 level 21、`skillShowLevel` 20。"
        "技能解鎖星見名錄，與 `skillShowLevel` 的對應不是簡單的「解鎖星＝顯示等級」，本頁不自行對齊。"
        "第 20 章升星節摘要曾把 quality 3 的 100 星寫成 level 16／15，與同章各件技能小節及升星表不符，本頁以表為準。"
    )
    add("")
    add("自身攻擊／生命（3／4）同品質全件相同。quality 3／4 另有增傷（18）或減傷（19），或兩者都有，按件列出。全英雄加成是英雄攻擊、英雄生命（103／104），同品質曲線相同（`version=1`；`version=-1` 的兩處例外見上）。")
    add("")
    add(tbl["attrs"])
    add("")
    add(
        "quality 4 的 0 星攻擊／生命與 100 星攻擊／生命，三件類型都是 2780／19100 與 65180／435400"
        "（與附加屬性無關，全件相同；升星表 `attribute`、`AttributeArr`、`newFightAttrs` 一致）。"
        "第 20 章升星節曾把 0 星寫成 3530／23600，該數字未出現在升星表，本頁以表為準。附加屬性（`version=1` 與 `version=-1` 相同）："
    )
    add("")
    q3_up = [a.name for a in data.artifacts if a.quality == 3 and 18 in a.extra0]
    q3_cut = [a.name for a in data.artifacts if a.quality == 3 and 19 in a.extra0]
    add("- quality 2：沒有 18／19。")
    add(f"- quality 3：{'、'.join(q3_up)}為增傷，0 星 50、100 星 1750；{'、'.join(q3_cut)}為減傷，0 星 50、100 星 1750。恐懼之眼是通用型，附加的是增傷不是減傷。")
    add("- quality 4 進攻型（含青藤古弓，其 `group_id` 為 1502）：增傷 0 星 200、100 星 3500。")
    add("- quality 4 生存型：減傷 0 星 200、100 星 3500。")
    add("- quality 4 通用型：增傷與減傷各 0 星 100、100 星 1750。")
    add("")
    add(
        "中間星級的附加屬性幾乎每星上調，不在本頁逐星列出。"
        "`artifact_skill_attr.json` 按 `type` 3／4／5（與定義表 `artifact_skill_attr_type`、品質 2／3／4 對應）"
        "給攻擊、生命值、暴擊傷害（10，值固定 10000）曲線；三型都是 1–40 級共 40 列，且攻擊／生命／暴擊傷害曲線彼此相同。"
        "第 20 章曾寫級數分別到 11／16／40，與輔表不符，本頁以表為準。"
        "與升星表同級的攻擊／生命並不一致（例如 quality 2、level 1 升星表為 340／2300，輔表為 90／900）。"
        "兩者關係未驗證，本頁不以輔表覆蓋升星表，也不把 120 列整表倒進頁面。"
    )
    add("")
    add("## 技能")
    add("")
    add(
        "技能名稱與描述取自升星表的 `skill_name`、`skill_desc`、`skill_desc_parameter`（`version=1`）。"
        "多數名稱鍵是 `hero_skill_name_23xxxxx`／`24xxxxx`／`25xxxxx`；神聖盟約起改把 `skill_name` 寫成 `artifact_name_50012` 這類秘寶名鍵，顯示會與秘寶同名，不是另有技能短名。"
        "下列每件先寫 0 星，再寫 100 星。中間解鎖星只改參數，不逐段展開。多段 desc 各自從 `{0}` 起算。"
        "煌雷裁決、龍骸護符、青藤古弓在 0–100 星的 `skill_desc`／`skill_desc_parameter` 皆為空，只錄「無 skill_desc」，不從其他表補文案。"
    )
    add("")
    for a in data.artifacts:
        add(f"### {a.name}（{a.id_v1}／{a.id_vm1}，{a.type_name}，品質 {a.quality}）")
        add("")
        note = "技能名鍵是秘寶名鍵，顯示與秘寶同名。" if a.skill0.name_is_artifact else ""
        add(f"解鎖星：{format_unlock_stars(a.unlock)}。0 星技能名「{a.skill0.name}」，100 星技能名「{a.skill100.name}」。{note}")
        add("")
        add(tbl["skills"][a.id_v1])
        add("")
    add("## 榮譽牆")
    add("")
    add(
        f"官方說明：{o.honour_lines['artifact_honour_004']}；{o.honour_lines['artifact_honour_002']}；{o.honour_unlock}。"
        "（`artifact_honour_003`–`006`、`artifact_honour_005`）。"
    )
    add("")
    add(
        "`artifact_honor.json` 3 筆，按品質 2／3／4：`attribute_up` 為生命值（4）40／80／160，戰力 160／880／1760。"
        "`need_chip` 三筆都是 `200|10,300|20,400|30,600|30`。這四個數字在表上沒有標題，本頁不自行解釋成哪一種碎片或等級。"
    )
    add("")
    add(tbl["honor"])
    add("")
    add(
        "`artifact_honor_bonus.json` 30 筆，按秘寶 `group_id` 分成 6 組，門檻為榮譽等級 50／100／150／200／300（沒有 250）。"
        "1301／1401／1501 加英雄攻擊（103），1302／1402／1502 加英雄生命（104）。各組成員見名錄「榮譽組」欄。數值是原值。"
    )
    add("")
    add(tbl["bonus"])
    add("")
    add("同一 `group_id` 在兩套編號裡都會出現（例如 1301 同時掛平衡胸針的 30002 與 130002）。榮譽牆如何計算「等級」、兩套 id 是否分開累計，表上沒有說明，不要猜。")
    add("")
    add("## 本頁未列入")
    add("")
    add("- 英雄裝備、專武、領主裝備；城堡裝飾「秘寶之劍」。")
    add("- 紫金秘寶等活動、秘寶禮包與儲值檔位、秘寶隨機箱／自選箱的完整開箱表、秘寶占卜與秘寶卷軸。")
    add("- `dig_treasure`、`mine_treasure*`、`season_treasure`、`raid_treasure_group`、`kvk_map_treasure` 等尋寶／寶藏表。")
    add(f"- 字串中的「{o.power_suit_name}」套裝（表上無列）、套裝技能 id 的獨立文案、以及「傳奇(含)以上品質」與品質 2／3／4 的對應。")
    add("- 秘寶大廳全部 2,077 級的中間值，以及 `para1`／`para2` 與「倍率／轉化率」三個名稱的逐欄對應。")
    add("- 升星 1–99 星的逐星屬性與中間技能參數；`artifact_skill_attr` 與升星表的關係。")
    add("- 通用碎片如何折算進合成或升星；303001 與 330011／363001 是否為同一道具。")
    add("- `SeasonParam` 與賽季日曆的對應（不標未開放）。")
    add("- 編隊面板「秘寶 52.50%」的完整加總式（只記沒有單一列 18｜5250／19｜5250，以及 3500＋1750 這個數字對得上）。")
    add("- 與英雄技能、站位、士兵的搭配模擬。")
    add("")
    add("## 資料說明")
    add("")
    add(f"- {_data_notes(data)}")
    add("- 待補：客戶端實際讀 `version=-1` 還是 `version=1`；大廳 para 欄與倍率／轉化率的對應，以及插槽解鎖字串與表不一致的原因；碎片三組 id 的關係；「秘寶之力」與「傳奇」品質用字；面板 52.50% 的完整來源；活動與取得途徑。")
    add("")
    return "\n".join(lines)
