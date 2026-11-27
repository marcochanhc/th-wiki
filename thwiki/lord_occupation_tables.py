"""Compile the published 領主職業 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .highlight import highlight, highlight_lines
from .htmlutil import e, table
from .paths import DATA_CUTOFF, DATA_DIR, STRINGS_PATH, TOPHEROES_ROOT

# 本頁截止為 2026-11-22：以當日 LocalLow／live 為準。不改 paths.DATA_CUTOFF。
EXTRACT_DIR = TOPHEROES_ROOT / "extracts/2026-11-22-locallow"
EXTRACT_DATA = EXTRACT_DIR / "data"
EXTRACT_STRINGS = EXTRACT_DIR / "strings_zh.json"

PAGE_CUTOFF = "2026-11-22"
PACKAGE_NAME = "app-1.129.12_table-1.0.43173"
ZIP_TIME_RANGE = "2026-11-22 23:33:08–23:33:20"

OCCUPATION_COUNT = 3
LEVEL_COUNT = 80
TREE_COUNT = 108
TREE_PER_OCCUPATION = 36
DETAIL_COUNT = 413
PLUGIN_COUNT = 49
ATTR_PLUGIN_COUNT = 25
SKILL_PLUGIN_COUNT = 24
TASK_COUNT = 78
TASK_THEME_GROUPS = 3
TASK_UNIQUE_NAMES = 26
SEASON_COUNT = 1
TALENT_TRACK_COUNT = 2
HALL_BUILDING_ID = 179

TABLE_SHA256 = {
    "professional.json": "c98f2eaa8b367f0a319e4ebd6eeee380d48add0ba619f80b97c8cf173a107498",
    "professional_advanced_detail.json": "f573f6bfdac26b10bda8d8ae7414c45133f1f3309be5c600774d1d74c81a0e56",
    "professional_lv.json": "3304c06e08f60eb097eab1a65ba4f64e1d42a3ea2ef6c45e817c2c0559ae42a9",
    "professional_plugin.json": "5fb632d7e1d761b03ad627142f8bb6a89d1956924125e165f72a1aa5dbafe569",
    "professional_season.json": "073e4a03b102c288cda4a1fa16714d379e8c1794e50e64ca3569f76cc4767ddf",
    "professional_task.json": "4a8fd612dc03f6fe013d49ca44c9d61aac842fb023d605fb90cbf4a80f5ef12f",
    "player_talent_professional.json": "c7e57fcda1b127d0df8e4c1f532c3c6edd0c9dc322208cfce6170c29969cc889",
    "professional_advanced_tree.json": "4929f32979796df7c573da3cfff4b8ed499f16ed84381a3cb1605db50e69b988",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
    "map_building.json": "cf85c9b553d8ef99c07fc00cf363546371993c62b0e30c1526be8fa87b284b9a",
    "citybuilding.json": "25dc79829dcc0888168e76fe7f2bd5cb9d4dc97df6cecdc98b6e01cb24c24a0f",
}

TREE_SHA256_1105 = "4c719ae7e170738b868014add33270462ed1ec705f7751cd435c7bcc353d35e2"
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

IDENTICAL_TABLES = (
    "professional.json",
    "professional_advanced_detail.json",
    "professional_lv.json",
    "professional_plugin.json",
    "professional_season.json",
    "professional_task.json",
    "player_talent_professional.json",
)

Y_LABEL = {1: "上", 2: "中", 3: "下"}
GENERIC_NODE_NAMES = ("屬性提升", "屬性紋章基座", "職業紋章基座")
COLOR_RE = re.compile(r"</?color(?:=[^>]*)?>", re.I)

USED_KEYS: set[str] = set()
STRINGS: dict = {}


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


def visible_official(text: str) -> str:
    """Strip color tags for readable quoting; keep wording, punctuation and placeholders."""
    t = COLOR_RE.sub("", text or "")
    t = t.replace("\r\n", "\n")
    return t.strip()


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


def raw_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def code_json(value) -> str:
    return f"<code>{e(raw_json(value))}</code>"


def p_html(body: str) -> str:
    return f"<p>{body}</p>"


def quote_block(text: str, terms: list[str]) -> str:
    visible = visible_official(text)
    if not visible:
        return ""
    return f"<blockquote>{highlight_lines(visible, terms)}</blockquote>"


def fmt_levels(pairs: list[tuple[int, object]]) -> str:
    """Format (level, value) from high level to low, without arrays."""
    bits = [f"{lv} 級 {val}" for lv, val in pairs]
    return "、".join(bits)


def pos_label(position) -> str:
    x, y = int(position[0]), int(position[1])
    return f"第 {x} 列、{Y_LABEL.get(y, str(y))}"


def as_list(value):
    if value in (None, "", [], {}):
        return []
    if isinstance(value, list):
        return value
    return [value]


@dataclass
class AttrInfo:
    attr_id: int
    name: str
    name_key: str
    show_type: int | None
    name_missing: bool
    alt_name: str | None = None
    alt_key: str | None = None


@dataclass
class Occupation:
    oid: int
    name: str
    name_key: str
    intro: str
    intro_key: str
    icon: str
    tree_root: int
    bio_title: str
    bio_body: str


@dataclass
class TreeNode:
    nid: int
    occupation: int
    name: str
    name_key: str
    tree_desc_key: str
    tree_desc: str
    skill_type: int
    position: list
    lv_ids: list
    sub_type: object
    jump_id: object
    reject: object
    is_plugin: bool
    details: list = field(default_factory=list)


@dataclass
class Plugin:
    pid: int
    name: str
    name_key: str
    occupation: int
    is_attr: bool
    detail_ids: list
    weight: list
    levels: list = field(default_factory=list)  # (lv, num, attr)
    attr: AttrInfo | None = None


@dataclass
class TablesData:
    occupations: list[Occupation]
    levels: list[dict]
    tree: list[TreeNode]
    tree_by_id: dict[int, TreeNode]
    plugins: list[Plugin]
    tasks: list[dict]
    season: dict
    talent_tracks: list[dict]
    hall_name: str
    hall_des: str
    buildings: dict[int, tuple[str, str]]
    map_buildings: dict[int, tuple[str, str, str, str]]
    attributes: dict[int, dict]
    terms: list[str]
    unused_skill_names: list[str]
    unused_plugin_names: list[str]
    unused_task_names: list[str]
    alias_notes: list[str]
    pack_notes: dict
    hall_icon: str
    missing_keys: list[str]


def resolve_attr(attr_id: int, attributes: dict[int, dict], attr_name_key: str | None = None) -> AttrInfo:
    rec = attributes.get(int(attr_id))
    key = attr_name_key or ""
    if not key and rec:
        key = rec.get("NameKey") or rec.get("name") or ""
    if not key:
        key = f"attribute_name_{attr_id}"
    name = official_text(key)
    missing = not has_string(key)
    alt_name = None
    alt_key = None
    default_key = f"attribute_name_{attr_id}"
    if default_key != key and has_string(default_key):
        alt = official_text(default_key)
        if alt and alt != name:
            alt_name = alt
            alt_key = default_key
    show_type = rec.get("show_type") if rec else None
    return AttrInfo(
        attr_id=int(attr_id),
        name=name or "",
        name_key=key,
        show_type=show_type,
        name_missing=missing or not name,
        alt_name=alt_name,
        alt_key=alt_key,
    )


def _bio_for(oid: int) -> tuple[str, str, str, str]:
    # 界面簡介鍵：表沒有把它們寫在職業主表欄位上，只照錄字串表既有配對。
    mapping = {
        101: ("professional_bio_9", "professional_bio_10"),
        102: ("professional_bio_7", "professional_bio_8"),
        103: ("professional_bio_5", "professional_bio_6"),
    }
    t_key, b_key = mapping[oid]
    return official_text(t_key), official_text(b_key), t_key, b_key


def _compare_packs() -> dict:
    info: dict = {
        "identical": {},
        "tree": {},
        "strings": {},
        "attribute": {},
    }
    for name in IDENTICAL_TABLES:
        hashes = {}
        for label, folder in PACK_DATA_DIRS.items():
            path = folder / name
            if path.exists():
                hashes[label] = file_sha256(path)
        info["identical"][name] = hashes
    tree_hashes = {}
    for label, folder in PACK_DATA_DIRS.items():
        path = folder / "professional_advanced_tree.json"
        if path.exists():
            tree_hashes[label] = file_sha256(path)
    info["tree"]["hashes"] = tree_hashes

    locallow_tree = load_json(EXTRACT_DATA / "professional_advanced_tree.json")
    path_1105 = PACK_DATA_DIRS["2026-11-05"] / "professional_advanced_tree.json"
    tree_1105 = load_json(path_1105) if path_1105.exists() else []
    only_itempos = True
    same_ids = {r["id"] for r in locallow_tree} == {r["id"] for r in tree_1105}
    diffs = 0
    if tree_1105:
        by_old = {r["id"]: r for r in tree_1105}
        for row in locallow_tree:
            old = by_old.get(row["id"])
            if not old:
                only_itempos = False
                continue
            keys = set(row) | set(old)
            changed = [k for k in keys if row.get(k) != old.get(k)]
            if changed:
                diffs += 1
                if changed != ["itemPos"]:
                    only_itempos = False
    info["tree"]["same_ids"] = same_ids
    info["tree"]["changed_rows"] = diffs
    info["tree"]["only_itempos"] = only_itempos
    info["tree"]["sha_1105"] = TREE_SHA256_1105

    str_hashes = {label: file_sha256(path) for label, path in PACK_STRINGS.items() if path.exists()}
    info["strings"]["hashes"] = str_hashes
    live_s = load_json(EXTRACT_STRINGS)
    s_1105_path = PACK_STRINGS["2026-11-05"]
    extra_keys = []
    if s_1105_path.exists():
        s_1105 = load_json(s_1105_path)
        extra_keys = sorted(set(live_s) - set(s_1105))
        changed_shared = [k for k in set(live_s) & set(s_1105) if live_s[k] != s_1105[k]]
        info["strings"]["extra_keys"] = extra_keys
        info["strings"]["changed_shared"] = changed_shared
        info["strings"]["professional_32"] = live_s.get("professional_32")
    attr_hashes = {}
    for label, folder in PACK_DATA_DIRS.items():
        path = folder / "attribute.json"
        if path.exists():
            attr_hashes[label] = file_sha256(path)
    info["attribute"]["hashes"] = attr_hashes
    return info


def load_tables_data() -> TablesData:
    global STRINGS, USED_KEYS
    USED_KEYS = set()
    actual_strings = file_sha256(EXTRACT_STRINGS)
    if actual_strings != STRINGS_SHA256:
        raise RuntimeError(f"strings_zh.json sha256 mismatch: {actual_strings}")
    STRINGS = load_json(EXTRACT_STRINGS)

    occupations_raw = load_extract_table("professional.json")
    levels = load_extract_table("professional_lv.json")
    tree_raw = load_extract_table("professional_advanced_tree.json")
    details_raw = load_extract_table("professional_advanced_detail.json")
    plugins_raw = load_extract_table("professional_plugin.json")
    season_rows = load_extract_table("professional_season.json")
    tasks_raw = load_extract_table("professional_task.json")
    talent_raw = load_extract_table("player_talent_professional.json")
    attributes_raw = load_extract_table("attribute.json")
    city_raw = load_extract_table("citybuilding.json")
    map_raw = load_extract_table("map_building.json")

    if len(occupations_raw) != OCCUPATION_COUNT:
        raise RuntimeError(f"professional.json expected {OCCUPATION_COUNT} rows")
    if len(levels) != LEVEL_COUNT:
        raise RuntimeError(f"professional_lv.json expected {LEVEL_COUNT} rows")
    if len(tree_raw) != TREE_COUNT:
        raise RuntimeError(f"professional_advanced_tree.json expected {TREE_COUNT} rows")
    if len(details_raw) != DETAIL_COUNT:
        raise RuntimeError(f"professional_advanced_detail.json expected {DETAIL_COUNT} rows")
    if len(plugins_raw) != PLUGIN_COUNT:
        raise RuntimeError(f"professional_plugin.json expected {PLUGIN_COUNT} rows")
    if len(tasks_raw) != TASK_COUNT:
        raise RuntimeError(f"professional_task.json expected {TASK_COUNT} rows")
    if len(talent_raw) != TALENT_TRACK_COUNT:
        raise RuntimeError("player_talent_professional.json expected 2 rows")
    if len(season_rows) != SEASON_COUNT:
        raise RuntimeError("professional_season.json expected 1 row")

    attributes = {int(r["id"]): r for r in attributes_raw}
    buildings = {}
    hall_name = hall_des = hall_icon = ""
    for row in city_raw:
        bid = int(row["id"])
        name = official_text(row.get("name"))
        des = official_text(row.get("des"))
        buildings[bid] = (name, des)
        if bid == HALL_BUILDING_ID:
            hall_name = name
            hall_des = des
            hall_icon = str(row.get("func_icon") or row.get("default_icon") or "")

    map_buildings = {}
    for row in map_raw:
        mid = int(row["id"])
        map_buildings[mid] = (
            official_text(row.get("name")),
            row.get("name") or "",
            official_text(row.get("des")),
            row.get("des") or "",
        )

    details_by_tree: dict[int, list] = defaultdict(list)
    details_by_id = {int(r["id"]): r for r in details_raw}
    for row in details_raw:
        details_by_tree[int(row["tree_id"])].append(row)
    for rows in details_by_tree.values():
        rows.sort(key=lambda r: int(r.get("lv") or 0))

    occupations: list[Occupation] = []
    for row in sorted(occupations_raw, key=lambda r: int(r["order"])):
        oid = int(row["id"])
        bio_title, bio_body, _, _ = _bio_for(oid)
        occupations.append(
            Occupation(
                oid=oid,
                name=official_text(row["name"]),
                name_key=row["name"],
                intro=official_text(row["introduction"]),
                intro_key=row["introduction"],
                icon=str(row.get("professional_icon") or ""),
                tree_root=int(row["professional_advanced_tree_id"]),
                bio_title=bio_title,
                bio_body=bio_body,
            )
        )

    tree: list[TreeNode] = []
    tree_by_id: dict[int, TreeNode] = {}
    for row in tree_raw:
        node = TreeNode(
            nid=int(row["id"]),
            occupation=int(row["type"]),
            name=official_text(row["name"]),
            name_key=row["name"],
            tree_desc_key=row.get("desc") or "",
            tree_desc=official_text(row.get("desc")),
            skill_type=int(row["skill_type"]),
            position=list(row["position"]),
            lv_ids=list(row.get("lv_id") or []),
            sub_type=row.get("sub_type"),
            jump_id=row.get("jump_id"),
            reject=row.get("reject"),
            is_plugin=bool(row.get("IsPluginSlot")),
            details=sorted(
                [details_by_id[int(i)] for i in (row.get("lv_id") or []) if int(i) in details_by_id],
                key=lambda r: int(r.get("lv") or 0),
            ),
        )
        tree.append(node)
        tree_by_id[node.nid] = node

    plugins: list[Plugin] = []
    for row in plugins_raw:
        detail_ids = [int(x) for x in as_list(row.get("detail_id"))]
        level_rows = []
        attr_info = None
        for did in detail_ids:
            det = details_by_id.get(did)
            if not det:
                continue
            attr_id = int(det.get("attribute") or -1)
            if attr_id > 0 and attr_info is None:
                attr_info = resolve_attr(attr_id, attributes, det.get("attrName"))
            level_rows.append((int(det.get("lv") or 0), det.get("num"), attr_id, det))
        plugins.append(
            Plugin(
                pid=int(row["id"]),
                name=official_text(row["name"]),
                name_key=row["name"],
                occupation=int(row["professional"]),
                is_attr=bool(row.get("IsAttributePlugin")),
                detail_ids=detail_ids,
                weight=list(row.get("weight") or []),
                levels=level_rows,
                attr=attr_info,
            )
        )

    talent_tracks = []
    for row in sorted(talent_raw, key=lambda r: int(r.get("sort") or 0)):
        talent_tracks.append({
            "id": int(row["id"]),
            "name_key": row["name"],
            "name": official_text(row["name"]),
            "detail_key": row.get("detail"),
            "detail": official_text(row.get("detail")),
            "sort": row.get("sort"),
            "banner": row.get("career_banner"),
            "resetting_cost": row.get("resetting_cost"),
            "showIds": row.get("showIds"),
        })

    occ_by_id = {o.oid: o for o in occupations}
    used_skill_keys = {n.name_key for n in tree}
    used_plugin_keys = {p.name_key for p in plugins}
    used_task_keys = {str(t.get("name")) for t in tasks_raw}

    unused_skill_names = []
    for key, val in STRINGS.items():
        if not key.startswith("professional_name_"):
            continue
        if key in used_skill_keys:
            continue
        if key in {o.name_key for o in occupations}:
            continue
        if key.startswith("professional_name_sp_"):
            continue
        unused_skill_names.append(val)
    unused_skill_names = sorted(set(unused_skill_names), key=lambda n: (n.startswith("被動技能") is False, n))

    unused_plugin_names = []
    for key, val in STRINGS.items():
        if not (
            key.startswith("professional_plugin_str_name_")
            or key.startswith("professional_plugin_skill")
        ):
            continue
        if not key.endswith(tuple(f"name_{i}" for i in range(1, 20))) and "_name_" not in key:
            continue
        if "name_" not in key:
            continue
        if key in used_plugin_keys:
            continue
        # only actual display-name keys
        if "_name_" in key:
            unused_plugin_names.append(val)
    unused_plugin_names = sorted(set(unused_plugin_names))

    unused_task_names = []
    for i in range(1, 40):
        key = f"professional_task_name_{i}"
        if has_string(key) and key not in used_task_keys:
            unused_task_names.append(official_text(key))

    alias_notes = []
    for sp_key in ("professional_name_sp_02", "professional_name_sp_03", "professional_name_sp_04"):
        if has_string(sp_key):
            alias_notes.append(f"{sp_key}＝{official_text(sp_key)}")

    missing_keys = []
    for key in (
        "professional_season_name_1",
        "goods_desc_515",
        "goods_desc_516",
        "goods_desc_61",
        "goods_decc_61",
        "attribute_name_1400501",
    ):
        if not has_string(key):
            missing_keys.append(key)

    terms: list[str] = []
    def add_term(*vals: str) -> None:
        for v in vals:
            v = visible_official(v)
            if v and v not in terms and len(v) >= 2:
                terms.append(v)

    add_term("領主職業", "職業大廳", "新的職業")
    for o in occupations:
        add_term(o.name)
    add_term("戰爭領主", "豐饒領主")
    for n in tree:
        if n.name and n.name not in GENERIC_NODE_NAMES:
            add_term(n.name)
    for p in plugins:
        add_term(p.name)
        if p.attr and p.attr.name:
            add_term(p.attr.name)
    add_term(
        "翠綠秘藥", "職業重修指南", "職業領主培訓手冊", "職業領主培訓光碟",
        "職業經驗", "職業週任務積分", "血脈精粹", "魔法塵埃", "先祖魂石",
        "先祖圖騰", "職業技能點", "屬性紋章", "職業紋章",
        "屬性紋章基座", "職業紋章基座", "屬性提升",
        "基礎技能", "主動技能", "被動技能", "屬性技能", "終極技能",
        "職業基礎技能",
    )
    for _name, _des in buildings.values():
        if _name in (
            "伐木場", "石礦場", "牧場", "強化石礦", "水晶礦", "修道院",
            "粗礦場", "口糧工廠", "魔紋石礦", "功勳碑", "職業大廳",
            "精煉金屬礦", "先祖圖騰",
        ):
            add_term(_name)
    for mb_name, _, _, _ in map_buildings.values():
        if mb_name:
            add_term(mb_name)
    add_term("投石機", "魔法結界", "拒馬", "哨塔", "詛咒祭壇")
    add_term("部族")

    pack_notes = _compare_packs()
    pack_notes["details_by_id_count"] = len(details_by_id)
    pack_notes["orphan_plugin_details"] = [
        d["id"] for d in details_raw
        if int(d.get("tree_id") or 0) == -1
        and int(d["id"]) not in {i for p in plugins for i in p.detail_ids}
    ]

    # silence unused
    _ = occ_by_id
    _ = hall_icon

    return TablesData(
        occupations=occupations,
        levels=levels,
        tree=tree,
        tree_by_id=tree_by_id,
        plugins=plugins,
        tasks=tasks_raw,
        season=season_rows[0],
        talent_tracks=talent_tracks,
        hall_name=hall_name,
        hall_des=hall_des,
        buildings=buildings,
        map_buildings=map_buildings,
        attributes=attributes,
        terms=terms,
        unused_skill_names=unused_skill_names,
        unused_plugin_names=unused_plugin_names,
        unused_task_names=unused_task_names,
        alias_notes=alias_notes,
        pack_notes=pack_notes,
        hall_icon=hall_icon,
        missing_keys=missing_keys,
    )


def exp_bands(levels: list[dict]) -> list[tuple[str, int]]:
    bands = []
    start = int(levels[0]["level"])
    prev_exp = int(levels[0]["exp"])
    prev = start
    for row in levels[1:]:
        lv = int(row["level"])
        exp = int(row["exp"])
        if exp != prev_exp:
            label = str(start) if start == prev else f"{start}–{prev}"
            bands.append((label, prev_exp))
            start = lv
            prev_exp = exp
        prev = lv
    label = str(start) if start == prev else f"{start}–{prev}"
    bands.append((label, prev_exp))
    return bands


def describe_prereq(node: TreeNode, data: TablesData) -> str:
    if not node.details:
        return "沒有前置"
    # Use the first (usually only, or lowest) level's prerequisites.
    det = node.details[0]
    pres = as_list(det.get("lvup_pre_id"))
    if not pres:
        return "沒有前置"
    parts = []
    for item in pres:
        text = str(item)
        if "|" not in text:
            parts.append(text)
            continue
        nid_s, lv_s = text.split("|", 1)
        src = data.tree_by_id.get(int(nid_s))
        if not src:
            parts.append(f"節點 {nid_s} {lv_s} 級")
            continue
        if src.name == "屬性提升":
            need = f"滿 {lv_s} 級" if int(lv_s) > 1 else f"{lv_s} 級"
            parts.append(f"{pos_label(src.position)} {need}")
        elif src.name in ("屬性紋章基座", "職業紋章基座"):
            parts.append(f"{pos_label(src.position)}的{src.name} {lv_s} 級")
        else:
            parts.append(f"{src.name} {lv_s} 級")
    # de-duplicate while preserving order
    seen = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return "、".join(seen)


def node_levels_text(node: TreeNode, data: TablesData) -> str:
    if not node.details:
        return ""
    bits = []
    for det in node.details:
        attr_id = int(det.get("attribute") or -1)
        if attr_id <= 0:
            continue
        info = resolve_attr(attr_id, data.attributes, det.get("attrName"))
        bits.append((int(det.get("lv") or 0), det.get("num"), info))
    if not bits:
        return ""
    name = bits[0][2].name
    return f"{name}：" + "、".join(f"{lv} 級 {num}" for lv, num, _ in bits)


def hall_link(name: str, terms: list[str]) -> str:
    return f'<a href="city-buildings.html">{H(name, terms)}</a>'


def talent_link(terms: list[str]) -> str:
    return f'<a href="talents.html">{H("天賦總表", terms)}</a>'


def lord_eq_link(terms: list[str]) -> str:
    return f'<a href="lord-equipment.html">{H("領主裝備總表", terms)}</a>'


def occupation_of(data: TablesData, oid: int) -> Occupation:
    for o in data.occupations:
        if o.oid == oid:
            return o
    raise KeyError(oid)


def named_nodes(data: TablesData, oid: int) -> list[TreeNode]:
    nodes = [
        n for n in data.tree
        if n.occupation == oid and n.name not in GENERIC_NODE_NAMES
    ]
    nodes.sort(key=lambda n: (n.position[0], n.position[1], n.nid))
    return nodes


def attr_nodes_for(data: TablesData, oid: int) -> list[TreeNode]:
    nodes = [n for n in data.tree if n.occupation == oid and n.skill_type == 3]
    nodes.sort(key=lambda n: (n.position[0], n.position[1]))
    return nodes


def render_named_skill(node: TreeNode, data: TablesData, terms: list[str], parts: list[str]) -> None:
    add = parts.append
    add(f"      <h4>{H(node.name, terms)}</h4>")
    tree_text = visible_official(node.tree_desc)
    detail_keys = []
    detail_texts = []
    for det in node.details:
        key = det.get("des")
        if key:
            detail_keys.append(key)
            detail_texts.append(visible_official(official_text(key)))
    # If tree and detail texts are the same, show once.
    unique_detail = []
    for t in detail_texts:
        if t and t not in unique_detail:
            unique_detail.append(t)
    if tree_text and (not unique_detail or unique_detail == [tree_text]):
        add(p_html(highlight_lines(tree_text, terms)))
    else:
        if tree_text:
            add(p_html("樹上說明：" + highlight_lines(tree_text, terms)))
        for t in unique_detail:
            if t and t != tree_text:
                add(p_html("詳情：" + highlight_lines(t, terms)))

    # Extra official interface lines for a few skills, quoted as-is.
    extras = []
    if node.name == "命定之死":
        for key in ("professional_28", "professional_30", "professional_skill_lv_error"):
            if has_string(key):
                extras.append(visible_official(official_text(key)))
    elif node.name == "緊急動員":
        if has_string("professional_skills_ui_14"):
            extras.append(visible_official(official_text("professional_skills_ui_14")))
    elif node.name == "詛咒祭壇":
        if has_string("professional_skill_move_tips"):
            extras.append(visible_official(official_text("professional_skill_move_tips")))
    if extras:
        add(p_html("相關界面：「" + "」「".join(H(x, terms) for x in extras) + "」。"))

    # Scholar buildings / farm buildings mentioned by official parameters, named only.
    if node.details:
        det = node.details[0]
        para1 = as_list(det.get("para1"))
        # 善假於物 / 詛咒祭壇: map building ids in para1 segments
        b_ids: list[int] = []
        for item in para1:
            for part in str(item).split("|"):
                part = part.strip()
                if part.isdigit():
                    b_ids.append(int(part))
        map_hits = [i for i in b_ids if i in data.map_buildings]
        city_hits = [i for i in b_ids if i in data.buildings and i not in data.map_buildings]
        if map_hits:
            add("<ul>")
            for mid in map_hits:
                name, _nk, des, _dk = data.map_buildings[mid]
                add(f"<li>{H(name, terms)}：{highlight_lines(visible_official(des), terms)}</li>")
            add("</ul>")
        if city_hits:
            names = []
            for bid in city_hits:
                bname = data.buildings[bid][0]
                if bid == HALL_BUILDING_ID:
                    names.append(hall_link(bname or "職業大廳", terms))
                else:
                    names.append(H(bname, terms))
            add(p_html(
                "作用建築（名稱依城建表照錄，不展開升級）："
                + "、".join(names) + "。"
            ))


def notes_html(data: TablesData, terms: list[str]) -> list[str]:
    add_lines: list[str] = []
    a = add_lines.append
    pack = data.pack_notes
    a("      <h2>資料說明</h2>")
    a(p_html(
        f"資料截至 {PAGE_CUTOFF}（香港時間）。來源是 {PAGE_CUTOFF} LocalLow 解壓表與 "
        f"<code>strings_zh.json</code>（歸檔於 <code>/workspace/topheroes/extracts/2026-11-22-locallow/</code>，"
        f"包名 <code>{e(PACKAGE_NAME)}</code>，zip 內部時間 {e(ZIP_TIME_RANGE)}，香港時間）。"
        "各表已 pin sha256，不改用未記來源的現行 live 檔。不改 <code>paths.DATA_CUTOFF</code>（仍為 2026-11-05）。"
    ))
    a("<ul>")
    a(
        "<li>系統表列數："
        f"<code>professional.json</code> {OCCUPATION_COUNT}、"
        f"<code>professional_lv.json</code> {LEVEL_COUNT}、"
        f"<code>professional_advanced_tree.json</code> {TREE_COUNT}、"
        f"<code>professional_advanced_detail.json</code> {DETAIL_COUNT}、"
        f"<code>professional_plugin.json</code> {PLUGIN_COUNT}（屬性紋章 {ATTR_PLUGIN_COUNT}、職業紋章 {SKILL_PLUGIN_COUNT}）、"
        f"<code>professional_task.json</code> {TASK_COUNT}、"
        f"<code>professional_season.json</code> {SEASON_COUNT}、"
        f"<code>player_talent_professional.json</code> {TALENT_TRACK_COUNT}。</li>"
    )
    ident = pack["identical"]
    same = all(len(set(hs.values())) == 1 for hs in ident.values() if hs)
    a(f"<li>七張職業系統表（不含進階樹）在 11-05、StreamingAssets、LocalLow 與 live 的位元組{('相同' if same else '並非全部相同')}。SHA-256："
      + "；".join(
          f"<code>{e(name)}</code> <code>{e(TABLE_SHA256[name])}</code>"
          for name in IDENTICAL_TABLES
      )
      + "。</li>")
    tree_ok = pack["tree"].get("only_itempos") and pack["tree"].get("changed_rows") == TREE_COUNT
    a(
        "<li>進階樹 LocalLow／live SHA-256 <code>"
        f"{e(TABLE_SHA256['professional_advanced_tree.json'])}</code>；"
        f"11-05／StreamingAssets 為 <code>{e(TREE_SHA256_1105)}</code>。"
        f"108 個 <code>id</code> 相同，差異只在 <code>itemPos</code>："
        "11-05／StreamingAssets 為空物件 <code>{}</code>，LocalLow／live 為 "
        "<code>{Item1, Item2}</code>，數值與該列原本就有、且四批相同的 <code>position</code> 一一對應"
        f"（核對：{'是' if tree_ok else '否'}，變更列數 {pack['tree'].get('changed_rows')}）。"
        "名稱、說明鍵、<code>skill_type</code>、<code>lv_id</code>、<code>IsPluginSlot</code> 等其餘欄沒有差別。"
        "本頁以 LocalLow 為準，不把截稿寫成 11-05。</li>"
    )
    extra = pack.get("strings", {}).get("extra_keys") or []
    a(
        "<li>字串表 LocalLow／live SHA-256 <code>"
        f"{e(STRINGS_SHA256)}</code>。"
        f"與 11-05／StreamingAssets 相比，LocalLow／live 多出的鍵：{e('、'.join(extra) if extra else '（無）')}。"
        + (
            f"其中 <code>professional_32</code> 為「{e(pack.get('strings', {}).get('professional_32') or '')}」。"
            if "professional_32" in extra else ""
        )
        + "其餘共用鍵沒有改值。</li>"
    )
    a(
        "<li>三個職業主表：<code>professional_name_1</code>／<code>2</code>／<code>3</code> 對"
        f"{e(data.occupations[0].name)}／{e(data.occupations[1].name)}／{e(data.occupations[2].name)}；"
        "介紹鍵 <code>professional_dec_1</code>／<code>2</code>／<code>3</code>。"
        f"圖示鍵照錄，農場主人為 <code>{e(data.occupations[1].icon)}</code>（原文拼法 <code>famer</code>，不修正）。"
        "詳情頁路徑含 <code>ProfesProfessional_Info_Details_*</code>，照錄不修正。"
        f"三列 <code>unlock</code> 皆為 1；字串表另有「暫未開放」「目前賽季不開放」等界面句，只照錄，不據此標某個職業未開放。</li>"
    )
    # name key swap
    knight_ult = next(n for n in data.tree if n.occupation == 101 and n.skill_type == 5)
    farm_ult = next(n for n in data.tree if n.occupation == 102 and n.skill_type == 5)
    a(
        f"<li>騎士領主「{e(knight_ult.name)}」節點 <code>{knight_ult.nid}</code> 的名稱鍵是 <code>{e(knight_ult.name_key)}</code>；"
        f"農場主人「{e(farm_ult.name)}」節點 <code>{farm_ult.nid}</code> 的名稱鍵是 <code>{e(farm_ult.name_key)}</code>。"
        "按表上的鍵照錄，不改正鍵號。"
        + (" 字串表別名鍵：" + "；".join(e(x) for x in data.alias_notes) + "，未寫在這三列的 <code>name</code> 欄。" if data.alias_notes else "")
        + "</li>"
    )
    a(
        "<li>升級前置寫在 <code>professional_advanced_detail</code> 的 <code>lvup_pre_id</code>（格式 <code>節點id|等級</code>），"
        "並與 <code>andConditions</code>／<code>andOpenIds</code> 一致。本批 <code>lvup_pre_or_id</code> 皆空。"
        "進階樹 <code>reject</code> 欄全空；字串表另有互斥界面句，只照錄，不把空的 <code>reject</code> 欄補寫成互斥表。"
        "表沒有把 <code>professional_bio_12</code>–<code>21</code> 對到 <code>skill_type</code> 數字的欄位，本頁不自行對譯。"
        "官方說明寫各職業 1 個主動技能與 5 個被動技能；本批每棵樹實際為 "
        "<code>skill_type</code> 1 一列、2 兩列、3 二十二列、4 一列、5 一列、6 六列、7 三列，與這句不完全對得上，列入待補，不自行對應。</li>"
    )
    a(
        "<li>屬性名用該列 <code>attrName</code> 或屬性表 <code>NameKey</code>，否則 <code>attribute_name_{id}</code>。"
        "<code>show_type=2</code> 只錄原值，不自行換成百分比；官方技能或建築說明若已有百分比字串，只照錄該字串，與表上原值並列，不用字串覆寫欄位。"
        "同一屬性 id 在樹前段與後段會再出現，是不同節點，本頁分列，不把它們加總。</li>"
    )
    kpi = next((p for p in data.plugins if "KPI" in p.name), None)
    if kpi and kpi.attr:
        a(
            f"<li>農場主人紋章「{e(kpi.name)}」詳情列屬性 id 為 <code>{kpi.attr.attr_id}</code>，"
            f"<code>attrName</code>／屬性表 <code>NameKey</code> 為 <code>{e(kpi.attr.name_key)}</code>「{e(kpi.attr.name)}」。"
            + (
                f"字串表另有 <code>{e(kpi.attr.alt_key)}</code>「{e(kpi.attr.alt_name)}」。"
                if kpi.attr.alt_name else ""
            )
            + f"<code>show_type</code> 為 {kpi.attr.show_type}，只錄原值。</li>"
        )
    hit = next((p for p in data.plugins if "自然英雄命中" in p.name), None)
    if hit and hit.attr:
        a(
            f"<li>「{e(hit.name)}」的屬性官方名是「{e(hit.attr.name)}」，紋章顯示名與屬性名用字不同，照錄。</li>"
        )
    stone = next((p for p in data.plugins if p.name.endswith("·石礦")), None)
    if stone and stone.attr:
        a(
            f"<li>「{e(stone.name)}」紋章名為「石礦」，屬性名為「{e(stone.attr.name)}」，照錄。</li>"
        )
    a(
        "<li>紋章 <code>detail_id</code> 與 <code>weight</code> 等長，順序與詳情列一致（高等級在前）。"
        f"<code>weight</code> 只錄原陣列，不換算成機率。本批 49 列 <code>kvk_theme</code> 皆為 <code>[1, 2]</code>，不對成賽季號。"
        "紋章詳情的 <code>tree_id</code> 皆為 -1，不掛在進階樹節點上。</li>"
    )
    if pack.get("orphan_plugin_details"):
        a(
            "<li>詳情表另有未掛上本批插件名錄的孤兒列："
            + "、".join(f"<code>{i}</code>" for i in pack["orphan_plugin_details"])
            + "。不把對應名稱算進現行紋章名錄，也不標未開放。</li>"
        )
    a(
        "<li>職業任務 78 列，<code>kvk_theme_id</code> 為 1、2、3 各 26 列，名稱與條件三組對應相同。"
        "不把 1／2／3 對成賽季號。<code>refresh_type</code> 皆為 2，不把這個數字譯成刷新週期。"
        "獎勵 id 為 604129201–604129226，字串表只見 <code>activity_name_604129001</code>「先祖圖騰禮包」，對不上這 26 個獎勵的內容。"
        "回收獎勵 id 1466201–1466280 字串表沒有對應名稱。"
        "<code>recycle_reward_show</code> 寫成 <code>999|2|{n}</code>；類型 999 的第 2 段沒有官方資源名，只錄原值，不對成「鑽石」。"
        f"各列第三段數字，等於該級及之前各列 <code>exp</code> 除以 50 的累加（80 列 <code>exp</code> 合計 {sum(int(r['exp']) for r in data.levels)}，第 80 列顯示 "
        f"{str(data.levels[-1].get('recycle_reward_show') or data.levels[-1].get('displayReward'))}）。</li>"
    )
    a(
        "<li>賽季列 <code>reset_goods_id</code> 516、<code>reset_cost</code> "
        f"{code_json(data.season.get('reset_cost'))}、<code>reset_free_time</code> {e(str(data.season.get('reset_free_time')))}、"
        f"<code>reset_limit</code> {code_json(data.season.get('reset_limit'))}。"
        "與官方說明「免費重置職業後需過7天才可再次免費重置」並列，不把 168 自行標成單位，也不解釋 <code>reset_limit</code> 兩段的含義。"
        f"<code>professional_season_name_1</code>、{e('、'.join(data.missing_keys))}：字串表沒有內容。"
        "515／516 的說明取自 <code>goods_decc_515</code>／<code>goods_decc_516</code>（鍵名多一個 c）。"
        "live <code>goods.json</code> 無可用列。</li>"
    )
    a(
        "<li>具名技能的 <code>para1</code>／<code>para2</code>、<code>skill_cd</code>、<code>skill_stored</code> 原值只記在本節，不與官方百分比字串互相換算覆寫。"
        "<code>skill_cd</code> 為 -1 時表上沒有冷卻秒數。占位符 <code>{0}</code>／<code>{1}</code>／<code>{2}</code> 不代填。</li>"
    )
    a(
        "<li>領主天賦志向來自分開的 <code>player_talent_professional.json</code>，名稱鍵是 <code>professional_name01</code>／<code>professional_name02</code>，"
        "不是職業主表的 <code>professional_name_1</code>／<code>2</code>。"
        "橫幅路徑含 <code>s6</code>／<code>s5</code>，不把路徑裡的數字對成賽季號。"
        "<code>resetting_cost</code> 與 <code>showIds</code> 只錄原值。天賦節點內容屬天賦總表範圍，本頁不展開。"
        "表沒有寫這套天賦與三個職業如何疊加，本頁不推測。</li>"
    )
    a(
        "<li>本頁未列入城建升級專章、領主裝備、王稱，以及進階樹 108 列、詳情 413 列、等級 80 列、任務 78 列的逐列全表。"
        "字串表有、但本批進階樹或紋章表沒有對應列的名稱，不寫進現行名錄，也不標未開放。"
        "不從 <code>season</code>、<code>unlock</code>、<code>kvk_theme</code> 或文案自動標未開放；"
        "公開正文不把「雲海紀行」當作已核實的賽季名，郵件只照錄標題與原文。"
        "與英雄技能、天賦、裝備的疊加或戰鬥結算不在範圍內。不編造閉合公式，不評定強弱或養成順序。</li>"
    )
    a("</ul>")
    return add_lines


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    o1, o2, o3 = data.occupations
    title = "Top Heroes Wiki｜領主職業總表"
    lede = (
        f"本頁列出在「{data.hall_name}」裡可選擇的三個職業：{o1.name}、{o2.name}、{o3.name}。"
        "職業系統提供的屬性與技能僅在目前賽季生效，賽季結束後將回收。"
        "這不是領主裝備，也不是領主天賦裡的戰爭領主、豐饒領主。"
    )
    summary = (
        f"領主職業圖鑑：{o1.name}、{o2.name}、{o3.name} 的介紹、技能、屬性提升、紋章、任務與重置回收規則。"
        "這不是領主裝備，也不是領主天賦志向。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "catalog", "label": "三個職業"},
        {"id": "levels", "label": "職業等級"},
        {"id": "tree", "label": "進階樹規則"},
        {"id": "skills", "label": "具名技能"},
        {"id": "attrs", "label": "屬性提升"},
        {"id": "emblems", "label": "紋章與基座"},
        {"id": "tasks", "label": "職業任務"},
        {"id": "reset", "label": "重置、回收與道具"},
        {"id": "talents", "label": "領主天賦志向"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])

    parts: list[str] = []
    add = parts.append
    add('    <header class="entry-head">')
    add(f"      <h1>{e(title)}</h1>")
    add(f'      <p class="lede">{e(lede)}</p>')
    add("    </header>")
    add(f"    {toc}")

    # ---- lead ----
    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        f"選擇職業的建築是{hall_link(data.hall_name, terms)}，說明為「{H(visible_official(data.hall_des), terms)}」。"
        f"建築升級見已發佈的<a href=\"city-buildings.html\">{H('城建升級總表', terms)}</a>，本頁不展開升級排程。"
        f"這不是領主裝備；領主裝備見已發佈的{lord_eq_link(terms)}。"
        f"領主天賦裡另有「{H('戰爭領主', terms)}」「{H('豐饒領主', terms)}」兩個志向，來源不是這三個職業，見下文與已發佈的{talent_link(terms)}。"
    ))
    add(p_html(
        "界面短名是「"
        + H(official_text("professional_1") or "職業", terms)
        + "」。另有頁籤「"
        + H(official_text("kvk_tab_09") or "新的職業", terms)
        + "」，以及動員限制「"
        + H(visible_official(official_text("mobilize_invite_limit_19")), terms)
        + "」「"
        + H(visible_official(official_text("mobilize_invite_limit_20")), terms)
        + "」。本頁用「領主職業」稱呼這套系統，不另行統一成一個自創名稱。"
    ))
    add(p_html("官方說明如下，照錄："))
    add(quote_block(official_text("professional_info"), terms))
    add(p_html("界面另有分類名稱與說明，表沒有把它們對到進階樹的類型數字，本頁不自行對譯："))
    add("<ul>")
    for title_key, des_key in (
        ("professional_bio_12", "professional_bio_13"),
        ("professional_bio_14", "professional_bio_15"),
        ("professional_bio_16", "professional_bio_17"),
        ("professional_bio_18", "professional_bio_19"),
        ("professional_bio_20", "professional_bio_21"),
    ):
        add(
            f"<li>「{H(visible_official(official_text(title_key)), terms)}」："
            f"{H(visible_official(official_text(des_key)), terms)}</li>"
        )
    add("</ul>")
    if has_string("professional_11"):
        add(p_html(
            "界面另有「" + H(official_text("professional_11"), terms) + "」。"
        ))
    mutex = []
    for key in (
        "professional_skills_mutually_exclusive",
        "professional_skills_ui_5",
        "professional_skills_ui_7",
    ):
        if has_string(key):
            mutex.append(visible_official(official_text(key)))
    if mutex:
        add(p_html(
            "關於互斥，界面寫：「" + "」「".join(H(x, terms) for x in mutex) + "」。"
            "本批進階樹的互斥欄全空，本頁只照錄這些句子，不補寫互斥表。"
        ))
    closed = []
    for key in (
        "professional_closed", "professional_closed_1", "professional_closed_2",
        "professional_31", "professional_reset_closed",
    ):
        if has_string(key):
            closed.append(visible_official(official_text(key)))
    if closed:
        add(p_html(
            "界面另有「" + "」「".join(H(x, terms) for x in closed) + "」。"
            "只照錄，不據此把本頁三個職業標成未開放。"
        ))
    add(p_html(
        "名稱與說明依遊戲裡看得到的字照錄。屬性提升與紋章的數值一律錄表上原值，不自行換成百分比。"
        "官方技能或建築說明若已經寫了百分比，只照錄該句，不用它去改寫表上的數字。"
        "不評定職業強弱，不排優先或養成順序。"
    ))
    add("    </section>")

    # ---- catalog ----
    add('    <section id="catalog">')
    add("      <h2>三個職業</h2>")
    cat_rows = []
    for o in data.occupations:
        intro = highlight_lines(visible_official(o.intro), terms)
        bio = "／".join(x for x in (visible_official(o.bio_title), visible_official(o.bio_body)) if x)
        cat_rows.append([
            H(o.name, terms),
            intro,
            H(bio, terms) if bio else "",
        ])
    add(table(
        ["職業", "介紹", "界面簡介"],
        cat_rows,
        caption="三個可選職業",
        mobile="cards",
        card_title="職業",
    ))
    if has_string("professional_bio_11"):
        add(p_html(
            "界面另寫：「"
            + H(visible_official(official_text("professional_bio_11")), terms)
            + "」。只照錄，不據此排優先。"
        ))
    add("    </section>")

    # ---- levels ----
    add('    <section id="levels">')
    add("      <h2>職業等級</h2>")
    add(p_html(
        f"三個職業共用同一條等級曲線，共 {LEVEL_COUNT} 級。"
        "每升 1 級可得到的職業技能點，數量與該級等級相同。"
        "官方說明：每級職業等級可提供 1 個職業技能點，升級每個職業技能節點消耗 1 個職業技能點。"
    ))
    bands = exp_bands(data.levels)
    add(table(
        ["等級", "升級所需經驗（表上原值）"],
        [[e(label), e(str(exp))] for label, exp in bands],
        caption="共用職業等級的經驗分段",
        mobile="cards",
        card_title="等級",
    ))
    add(p_html(
        "賽季結束回收時，會依職業等級退還對應獎勵；表上另有回收展示數字，沒有官方資源名稱，原值見資料說明，本頁不把它對成某一種貨幣。"
    ))
    add("    </section>")

    # ---- tree rules ----
    add('    <section id="tree">')
    add("      <h2>進階樹規則</h2>")
    add(p_html(
        f"每個職業 {TREE_PER_OCCUPATION} 個節點，三棵樹的座標佈局相同，只是節點、前置、技能名與少數非屬性技能不同。"
        "屬性提升節點各 3 級；具名技能與紋章基座各 1 級（基座這 1 級用來解鎖鑲嵌，不是紋章本身的等級）。"
    ))
    add("<ul>")
    add("<li>最前排的基礎技能沒有前置。</li>")
    add("<li>基礎技能後方的中間屬性節點，需基礎技能 1 級；再後方並排的三個屬性節點，皆需該中間節點滿 3 級，三個可並行。</li>")
    add("<li>主動技能需這三個屬性節點皆滿 3 級（三條都要滿足，不是「或」）。</li>")
    add("<li>主動技能後方並排的三個屬性節點，需主動技能 1 級；其後中間屬性節點，需這排中間那一個滿 3 級。</li>")
    add("<li>屬性紋章基座需其同列外側屬性節點滿 3 級；職業紋章基座需中間那條屬性線滿 3 級。</li>")
    add("<li>其後屬性、基座依同樣「中線帶兩翼、滿 3 級再開下一座基座」推進。被動技能接在第一座職業紋章基座之後；樹後段的具名技能需第三座職業紋章基座 1 級，再接最後兩排屬性節點。</li>")
    add("</ul>")
    add(p_html("升級每個職業技能節點消耗 1 個職業技能點。"))
    add("    </section>")

    # ---- skills ----
    add('    <section id="skills">')
    add("      <h2>具名技能</h2>")
    add(p_html(
        "下列是進階樹上名稱不是「屬性提升」「屬性紋章基座」「職業紋章基座」的節點。"
        "技能說明若含百分比，是官方字串；表上參數與冷卻原值見資料說明，不互相換算覆寫。"
        "說明裡的占位符保持原樣，不代填數字。"
    ))
    for occ in data.occupations:
        add(f"      <h3>{H(occ.name, terms)}</h3>")
        for node in named_nodes(data, occ.oid):
            render_named_skill(node, data, terms, parts)
        # scholar extra UI, once
        if occ.oid == 103:
            ui_keys = (
                "professional_3_ui_6", "professional_3_ui_26", "professional_3_ui_37",
                "professional_3_ui_46", "professional_3_ui_33", "professional_3_ui_47",
            )
            bits = [visible_official(official_text(k)) for k in ui_keys if has_string(k)]
            if bits:
                add(p_html(
                    "學者建築相關界面（照錄，不展開城建專章）：「"
                    + "」「".join(H(x, terms) for x in bits)
                    + "」。"
                ))
    add("    </section>")

    # ---- attrs ----
    add('    <section id="attrs">')
    add("      <h2>屬性提升</h2>")
    add(p_html(
        f"三個職業各有 22 個名稱為「{H('屬性提升', terms)}」的節點，說明皆為「"
        + H(visible_official(official_text("professional_desc_100102")), terms)
        + "」。座標、屬性與各級原值在三棵樹上相同，只是節點與前置隨職業而變。下表以位置為準，各 3 級，只錄表上原值，不自行換成百分比。"
        "同一屬性在樹前段與後段會再出現一次，是不同節點，本頁分列，不把它們加總。"
    ))
    # verify three occupations share values
    base_nodes = attr_nodes_for(data, o1.oid)
    attr_rows = []
    for node in base_nodes:
        info = None
        vals = []
        for det in node.details:
            aid = int(det.get("attribute") or -1)
            if aid > 0 and info is None:
                info = resolve_attr(aid, data.attributes, det.get("attrName"))
            vals.append((int(det.get("lv") or 0), det.get("num")))
        vals.sort()
        attr_rows.append([
            e(pos_label(node.position)),
            H(info.name, terms) if info and info.name else "",
            e(str(vals[0][1]) if len(vals) > 0 else ""),
            e(str(vals[1][1]) if len(vals) > 1 else ""),
            e(str(vals[2][1]) if len(vals) > 2 else ""),
            H(describe_prereq(node, data), terms),
        ])
    add(table(
        ["位置", "屬性", "1 級", "2 級", "3 級", "前置"],
        attr_rows,
        caption="三個職業共用的屬性提升節點（表上原值）",
        mobile="cards",
        card_title="位置",
    ))
    add("    </section>")

    # ---- emblems ----
    add('    <section id="emblems">')
    add("      <h2>紋章與基座</h2>")
    add(p_html(
        f"每個職業樹上有 6 個「{H('屬性紋章基座', terms)}」，說明為「"
        + H(visible_official(official_text("professional_dec_plugin1")), terms)
        + f"」；以及 3 個「{H('職業紋章基座', terms)}」，說明為「"
        + H(visible_official(official_text("professional_dec_plugin2")), terms)
        + "」。"
    ))
    add(p_html("官方紋章規則如下，照錄："))
    # professional_plugin_25-29 may be one block or separate keys
    rule_text = []
    for i in range(25, 30):
        key = f"professional_plugin_{i:02d}" if False else f"professional_plugin_{i}"
        # keys are professional_plugin_25 etc.
        if has_string(f"professional_plugin_{i}"):
            rule_text.append(official_text(f"professional_plugin_{i}"))
        elif has_string(f"professional_plugin_{i:02d}"):
            rule_text.append(official_text(f"professional_plugin_{i:02d}"))
    if rule_text:
        add(quote_block("\n".join(rule_text), terms))
    switch = []
    for key in ("professional_plugin_06", "professional_plugin_08", "professional_plugin_23", "professional_plugin_105"):
        if has_string(key):
            switch.append(visible_official(official_text(key)))
    if switch:
        add(p_html(
            "切換與冷卻相關界面：「" + "」「".join(H(x, terms) for x in switch) + "」。"
            "兩句切換說明一併照錄，不自行調和。"
        ))
    add(p_html(
        f"本批對得上的紋章共 {PLUGIN_COUNT} 枚：屬性紋章 {ATTR_PLUGIN_COUNT} 枚，三個職業共用；"
        f"職業紋章 {SKILL_PLUGIN_COUNT} 枚，只屬於對應職業，職業之間不互通。"
        "各級原值由高到低排列。抽取權重原值見資料說明，不換成機率，也不評品質高低。"
    ))

    def emblem_rows(items: list[Plugin]) -> list[list[str]]:
        rows = []
        for p in items:
            attr_cell = ""
            if p.attr:
                attr_cell = H(p.attr.name, terms) if p.attr.name else ""
                extras = []
                if "自然英雄命中" in p.name and p.attr.name and p.attr.name != "自然英雄命中":
                    extras.append(f"紋章顯示名與屬性名用字不同，照錄")
                if p.name.endswith("·石礦") and p.attr.name and "石礦" not in p.attr.name:
                    extras.append(f"紋章名為「石礦」，屬性名照錄")
                if p.attr.alt_name:
                    extras.append(f"字串表另有「{p.attr.alt_name}」，對照見資料說明")
                if extras:
                    attr_cell += "（" + "；".join(extras) + "）"
            level_pairs = [(lv, num) for lv, num, _aid, _det in p.levels]
            rows.append([
                H(p.name, terms),
                attr_cell,
                e(fmt_levels(level_pairs)),
            ])
        return rows

    attr_plugins = [p for p in data.plugins if p.is_attr]
    attr_plugins.sort(key=lambda p: p.pid)
    add("      <h3>屬性紋章</h3>")
    add(p_html("下列 25 枚屬性紋章三個職業都可以用。出征上限這一枚的表上記法與其他戰鬥、採集屬性不同，仍然只錄原值。"))
    add(table(
        ["名稱", "屬性", "各級原值（高到低）"],
        emblem_rows(attr_plugins),
        caption="屬性紋章（三個職業共用）",
        mobile="cards",
        card_title="名稱",
    ))

    add("      <h3>職業紋章</h3>")
    for occ in data.occupations:
        items = [p for p in data.plugins if (not p.is_attr) and p.occupation == occ.oid]
        items.sort(key=lambda p: p.pid)
        add(p_html(f"{H(occ.name, terms)} {len(items)} 枚。"))
        add(table(
            ["名稱", "屬性", "各級原值（高到低）"],
            emblem_rows(items),
            caption=f"{occ.name}的職業紋章",
            mobile="cards",
            card_title="名稱",
        ))
    add("    </section>")

    # ---- tasks ----
    add('    <section id="tasks">')
    add("      <h2>職業任務</h2>")
    add(p_html(
        f"任務表共 {TASK_COUNT} 列，分成三組、每組 {TASK_UNIQUE_NAMES} 個任務。"
        "三組的名稱、條件與獎勵對應相同，只是編號重編。本頁不把這三組對成賽季號，也不把刷新欄的數字譯成週期。"
        "字串表另有「職業週任務積分」這個道具名，表沒有把它繫到刷新欄。"
        "同一組內的任務依序串成鏈，例如累計登入 1 天、3 天、6 天。"
        "任務獎勵的實際內容，本批對不上官方名稱，見資料說明。"
    ))
    # unique by name key, first theme group
    by_key: dict[str, dict] = {}
    for row in data.tasks:
        key = str(row.get("name"))
        if key not in by_key:
            by_key[key] = row
    # stable order: appearance in first theme
    first_theme = None
    themes = []
    for row in data.tasks:
        tid = row.get("kvk_theme_id")
        if tid not in themes:
            themes.append(tid)
        if first_theme is None:
            first_theme = tid
    first_rows = [row for row in data.tasks if row.get("kvk_theme_id") == first_theme]
    occ_names = {o.oid: o.name for o in data.occupations}
    task_rows = []
    for row in first_rows:
        name = official_text(row.get("name"))
        pid = int(row.get("professional_id") or 0)
        if pid in occ_names:
            who = occ_names[pid]
        else:
            who = "共用"
        task_rows.append([H(visible_official(name), terms), H(who, terms)])
    add(table(
        ["任務", "對象"],
        task_rows,
        caption="26 個職業任務名稱（三組共用）",
        mobile="cards",
        card_title="任務",
    ))
    if has_string("mail_title_600075"):
        add(p_html(
            "相關郵件標題：「" + H(official_text("mail_title_600075"), terms) + "」。"
        ))
    add("    </section>")

    # ---- reset / items ----
    add('    <section id="reset">')
    add("      <h2>重置、回收與道具</h2>")
    reset_ui = []
    for key in (
        "professional_3",
        "professional_skills_ui_11",
        "professional_skills_ui_9",
        "professional_reset_on_cooldown",
        "professional_reset_armed_busy",
        "farmer_potion_ui_9",
    ):
        if has_string(key):
            reset_ui.append(visible_official(official_text(key)))
    if reset_ui:
        add(p_html("重置相關界面：「" + "」「".join(H(x, terms) for x in reset_ui) + "」。"))
    if has_string("kvk_recycle_002") or has_string("kvk_recycle_011"):
        bits = []
        if has_string("kvk_recycle_002"):
            bits.append(visible_official(official_text("kvk_recycle_002")))
        if has_string("kvk_recycle_011"):
            bits.append("頁籤「" + visible_official(official_text("kvk_recycle_011")) + "」")
        add(p_html("回收界面：" + H("；".join(bits), terms) + "。"))
    if has_string("kvk_recycle_015"):
        add(p_html("回收內容與退還規則如下，照錄官方原文（已去掉顏色標籤，用字不變）："))
        add(quote_block(official_text("kvk_recycle_015"), terms))
    if has_string("kvk_recycle_018"):
        add(p_html(H(visible_official(official_text("kvk_recycle_018")), terms)))
    if has_string("kvk_recycle_014"):
        add(p_html(
            "另有建築回收說明：「"
            + H(visible_official(official_text("kvk_recycle_014")), terms)
            + "」。這句寫的是建築回收，不是職業等級本身。"
        ))

    add(p_html(
        "預告信與回收信是兩組不同的郵件。預告信標題為「"
        + H(official_text("mail_title_600060"), terms)
        + "」「"
        + H(official_text("mail_title_600126"), terms)
        + "」。後一個標題只照錄原文，不把其中的詞當作已核實的賽季名稱。兩封預告信正文相同："
    ))
    add(quote_block(official_text("mail_desc_600060"), terms))
    add(p_html(
        "回收信標題為「"
        + H(official_text("mail_title_600061"), terms)
        + "」「"
        + H(official_text("mail_title_600127"), terms)
        + "」。同樣只照錄標題，不把其中的詞當作已核實的賽季名稱。兩封回收信正文相同："
    ))
    add(quote_block(official_text("mail_desc_600061"), terms))
    add(p_html("「在賽季結束的15分鐘後」與結束時刻只出現在預告信，不在回收信。"))

    def goods_desc(gid: int) -> str:
        # prefer goods_desc, then goods_decc (extra c)
        if has_string(f"goods_desc_{gid}"):
            return official_text(f"goods_desc_{gid}")
        if has_string(f"goods_decc_{gid}"):
            return official_text(f"goods_decc_{gid}")
        return ""

    item_ids = (515, 516, 298, 299, 61)
    item_rows = []
    for gid in item_ids:
        name = official_text(f"goods_name_{gid}")
        desc = visible_official(goods_desc(gid))
        if not desc:
            desc = "字串表沒有說明"
        item_rows.append([H(name, terms), highlight_lines(desc, terms) if desc != "字串表沒有說明" else e(desc)])
    add(p_html("相關道具名稱與說明取自字串表："))
    add(table(
        ["名稱", "說明"],
        item_rows,
        caption="職業相關道具",
        mobile="cards",
        card_title="名稱",
    ))
    potion_ui = []
    for key in (
        "farmer_potion_ui_1",
        "farmer_potion_error_1",
        "professional_bio_44",
        "mobilize_invite_limit_9",
    ):
        if has_string(key):
            potion_ui.append(visible_official(official_text(key)))
    if potion_ui:
        add(p_html(
            "翠綠秘藥相關界面：「" + "」「".join(H(x, terms) for x in potion_ui) + "」。"
            "用到時照錄，不另編使用流程。"
        ))
    add("    </section>")

    # ---- talent tracks ----
    add('    <section id="talents">')
    add("      <h2>領主天賦志向</h2>")
    add(p_html(
        f"下列兩列來自領主天賦，不是{H(o1.name, terms)}、{H(o2.name, terms)}、{H(o3.name, terms)}。"
        f"志向的天賦節點見已發佈的{talent_link(terms)}，本頁不展開。"
        "表沒有寫這套天賦與三個職業如何疊加，本頁不推測。"
    ))
    talent_rows = []
    for tr in data.talent_tracks:
        talent_rows.append([
            H(tr["name"], terms),
            highlight_lines(visible_official(tr["detail"]), terms),
        ])
    add(table(
        ["志向", "介紹"],
        talent_rows,
        caption="領主天賦志向（與三個職業分開的來源）",
        mobile="cards",
        card_title="志向",
    ))
    add("    </section>")

    # ---- out of scope ----
    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add("<ul>")
    add(
        f"<li>城建升級專章。{hall_link(data.hall_name or '職業大廳', terms)}只作為職業系統的支援建築引用。"
        f"「{H('穀倉啟封', terms)}」提到的建築已對上名稱，不展開升級排程。</li>"
    )
    add(f"<li>領主裝備，以及王稱／國王稱號。領主裝備見{lord_eq_link(terms)}。</li>")
    add(f"<li>天賦節點詳情。本頁只記錄志向主表兩列；詳見{talent_link(terms)}。</li>")
    add(
        f"<li>進階樹 {TREE_COUNT} 列、詳情 {DETAIL_COUNT} 列、等級 {LEVEL_COUNT} 列、任務 {TASK_COUNT} 列的逐列全表。"
        "本頁改寫規則、關鍵節點與完整技能／紋章名錄。</li>"
    )
    unused_bits = []
    if data.unused_skill_names:
        unused_bits.append("、".join(H(n, terms) for n in data.unused_skill_names))
    if data.unused_plugin_names:
        unused_bits.append("、".join(H(n, terms) for n in data.unused_plugin_names))
    if unused_bits:
        add(
            "<li>字串表有、但本批進階樹與紋章表沒有對應列的名稱（不標未開放）："
            + "；".join(unused_bits)
            + "。</li>"
        )
    if data.unused_task_names:
        add(
            "<li>任務名稱見於字串表、但本批任務表未使用："
            + "、".join(H(n, terms) for n in data.unused_task_names)
            + "。其中若原文不是任務說明，也一併只照錄名稱，不當作本批任務。</li>"
        )
    add("<li>回收獎勵與任務獎勵的實際內容；沒有官方名稱的資源類型；重置欄位的單位與計數規則；主題欄與賽季日曆的對應。</li>")
    add("<li>與英雄技能、天賦、裝備的疊加或戰鬥結算。不編造閉合公式，不評定強弱或養成順序。</li>")
    add("</ul>")
    add("    </section>")

    add('    <section id="notes">')
    parts.extend(notes_html(data, terms))
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {PAGE_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_lord_occupation_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())
