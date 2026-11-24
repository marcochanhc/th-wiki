"""Compile the unpublished 英靈 catalog tables (preview only; not wired into build.py)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import lru_cache
from dataclasses import dataclass, field

from .assemble import (
    assemble,
    component,
    hero_href,
    param_list,
    unwrap_spirit_name,
)
from .exclusive_tables import comma, md_table, raw, raw_int, ratio
from .highlight import highlight, highlight_lines
from .htmlutil import e, table
from .overrides import ROSTER, roster_display_name
from .paths import DATA_CUTOFF
from .strings import fill_text, t
from .tables import load_table


LIVE_HERO = "https://marcochanhc.github.io/th-wiki/heroes/{id}.html"
# 英靈預覽專用；不改 paths.DATA_CUTOFF，以免影響專武等頁。
VALHALLA_DATA_CUTOFF = "2026-11-22"
CURRENT_UNLOCK_SERVER = "1-501,10001-19999"
PREVIOUS_NARROW_SERVER = "1-501,10001-10728"
PREVIOUS_NARROW_HEROES = (10046, 10047, 10037)
# 批次列依手冊第二版：3|9 仍分兩列（現用 unlock_server 已相同）。
BATCH_IDS = [
    ("2|5", (10031, 10042, 10048)),
    ("3|0", (10033, 10041, 10044)),
    ("3|5", (10050, 10045, 10051)),
    ("3|9", (10043, 10039, 10049)),
    ("3|9", (10046, 10047, 10037)),
]
# 升級效果預覽把 3／103、4／104 都標成英雄攻擊／英雄生命；表頭帶 id 以免混淆。
PANEL_HEADER = {
    3: "英雄攻擊（點數）",
    4: "英雄生命（點數）",
    103: "英雄攻擊（百分比）",
    104: "英雄生命（百分比）",
    1098: "英雄等級上限",
}

COMMON_ATTR_IDS = (3, 4, 103, 104, 1098)
SKILL_LEVEL_BY_RANK = {1: 1, 2: 25, 3: 50, 4: 75, 5: 100}
SIXTH_BREAKS = (1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
APPEARANCE_LEVELS = (75, 100)


def attr_label(attr_id: int) -> str:
    return t(f"attribute_name_{attr_id}") or str(attr_id)


def attr_map(pairs) -> dict[int, int]:
    out = {}
    for item in pairs or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out[int(item[0])] = raw_int(item[1])
    return out


@lru_cache(maxsize=None)
def attr_show_type(attr_id: int) -> int:
    rows = load_table("attribute")
    for row in rows:
        if int(row["id"]) == int(attr_id):
            return int(row["show_type"])
    raise ValueError(f"unknown attribute id {attr_id}")


def format_attr(attr_id: int, value) -> str:
    """英靈專用顯示。show_type 1＝點數（無％、無千分位、不加＋）；2＝原值÷100，兩位小數加％，不加＋。

    不可用於專武、稱號或羈絆。
    """
    raw_v = raw_int(value)
    kind = attr_show_type(attr_id)
    if kind == 1:
        return str(raw_v)
    if kind == 2:
        return f"{raw_v / 100:.2f}%"
    raise ValueError(f"unexpected show_type {kind} for attribute {attr_id}")


def format_power(value) -> str:
    """戰力照表上整數書寫（例如 627500），不用 628K，也不加千分位。"""
    return str(raw_int(value))


def attr_header(attr_id: int, *, delta: bool = False) -> str:
    if attr_id in PANEL_HEADER:
        name = PANEL_HEADER[attr_id]
    else:
        name = attr_label(attr_id)
    return f"Δ{name}" if delta else name


def _self_attrs(comp: dict) -> list[tuple[int, str, list[str]]]:
    raw_map = comp.get("attributesSelf") or {}
    out: list[tuple[int, str, list[str]]] = []
    for key, vals in raw_map.items():
        aid = int(key)
        out.append((aid, attr_label(aid), [format_attr(aid, v) for v in list(vals or [])]))
    out.sort(key=lambda item: item[0])
    return out


def _self_attr_text(items: list[tuple[int, str, list[str]]]) -> str:
    if not items:
        return ""
    parts = []
    for aid, name, vals in items:
        ranks = "／".join(vals)
        parts.append(f"{name}各階 {ranks}")
    return "技能列自身屬性：" + "；".join(parts)


def _curve_or_raise(groups: dict, label: str) -> None:
    bad = {k: v for k, v in groups.items() if len(v) != 1}
    if bad:
        raise ValueError(f"{label} not identical across spirits: {list(bad)[:8]}")


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def Hl(text: str, terms: list[str]) -> str:
    return highlight_lines(text, terms)


@dataclass
class LevelRow:
    level: int
    cost: int
    cumulative: int
    attrs: dict[int, int]
    power: int
    skill_rank: int
    delta_attrs: dict[int, int]
    delta_power: int
    appearance: str


@dataclass
class SpiritRow:
    hero_id: int
    hero_name: str
    hero_label: str
    faction: str
    spirit: str
    spirit_short: str
    shard_item: int
    shard_name: str
    shard_desc: str
    sixth_id: int
    sixth_name: str
    sixth_max: int
    sixth_by_lv: dict[int, int]
    skill_id: int
    skill: str
    skill_desc: str
    ranks: list[str]
    fightforce: tuple[int, ...]
    unlock_season: str
    unlock_server: str
    live_url: str
    self_attrs: list[tuple[int, str, list[str]]] = field(default_factory=list)


@dataclass
class TablesData:
    levels: list[LevelRow]
    spirits: list[SpiritRow]
    upgrade_total: int
    generic_shard_name: str
    generic_shard_desc: str
    verifications: dict
    terms: list[str] = field(default_factory=list)


def terms_for(spirits: list[SpiritRow]) -> list[str]:
    terms = {
        "英靈",
        "英靈強化",
        "專屬技能",
        "通用英靈碎片",
        "英雄等級上限",
        "英雄攻擊",
        "英雄生命",
        "技能減傷",
        "技能增傷",
        "聯盟",
        "自然",
        "部族",
        "攻擊",
        "生命值",
        "吸血",
        "格擋",
        "抗暴",
        "增傷",
    }
    for s in spirits:
        terms.update({s.spirit, s.spirit_short, s.skill, s.hero_label, s.shard_name})
        if s.hero_name:
            terms.add(s.hero_name)
        terms.add(s.sixth_name)
        terms.add("技能暴擊傷害")
        # 官方碎片說明「即可解鎖…英靈」整段當一個詞，避免「妖精英靈」被拆成兩個 .term（有左右內距，看起來像加了空格）。
        if s.shard_desc:
            m = re.search(r"即可解鎖.+?英靈", s.shard_desc)
            if m:
                terms.add(m.group(0))
        terms.add("妖精英靈")
    return sorted({t for t in terms if t}, key=len, reverse=True)


def _fill_rank(comp: dict, n: int) -> str:
    key = comp.get(f"desc{n}")
    raw_text = t(key) if key else ""
    if not raw_text:
        return ""
    special = comp.get("special_desc") if n == 1 else None
    return fill_text(raw_text, param_list(comp, n), special)


def load_tables_data() -> TablesData:
    defs = load_table("hero_valhalla")
    lvup = load_table("hero_valhalla_lvup")
    details = {int(r["id"]): r for r in load_table("hero_detail")}
    if len(defs) != 15 or len(lvup) != 1500:
        raise ValueError(f"unexpected table sizes: valhalla={len(defs)} lvup={len(lvup)}")

    defn_by = {int(r["id"]): r for r in defs}
    if any(int(r["id"]) != int(r["use_hero"]) or int(r["id"]) != int(r["group"]) for r in defs):
        raise ValueError("id / use_hero / group mismatch")
    if any(int(r["maxlevel"]) != 100 for r in defs):
        raise ValueError("maxlevel is not 100 for every spirit")
    if any(int(r["unlock_herostar"]) != 11 or int(r["unlock_day"]) != 60 for r in defs):
        raise ValueError("unlock star/day not uniform")

    for hid in defn_by:
        detail = details.get(hid)
        if not detail:
            raise ValueError(f"missing hero_detail for {hid}")
        if int(detail["star_max"]) != 15:
            raise ValueError(f"star_max of {hid} is {detail['star_max']}, not 15")
        if int(detail["honor_group"]) == 301:
            raise ValueError(f"{hid} is in honor_group 301")

    by_index: dict[int, list] = defaultdict(list)
    for r in lvup:
        by_index[int(r["index"])].append(r)
    if set(by_index) != set(defn_by):
        raise ValueError("lvup indexes do not match valhalla ids")

    cost_by_lv = defaultdict(set)
    common_by_lv = defaultdict(set)
    power_by_lv = defaultdict(set)
    rank_by_lv = defaultdict(set)
    appear_by_lv = defaultdict(set)
    extra_costs = []
    generic_in_cost = False
    for r in lvup:
        arr = r.get("costArr") or []
        if len(arr) != 1:
            extra_costs.append(r)
        typ, iid, qty = arr[0]
        if int(iid) == 230003:
            generic_in_cost = True
        cost_by_lv[int(r["lv"])].add((int(typ), int(qty)))
        attrs = attr_map(r.get("attrs"))
        common = tuple((i, attrs[i]) for i in COMMON_ATTR_IDS)
        common_by_lv[int(r["lv"])].add(common)
        power_by_lv[int(r["lv"])].add(raw_int(r["power"]))
        rank_by_lv[int(r["lv"])].add(tuple(int(p[1]) for p in (r.get("skillArr") or [])))
        appear_by_lv[int(r["lv"])].add((r.get("art_illusion", "").split("_lv")[-1], raw_int(r.get("preview") or -1)))
    _curve_or_raise(cost_by_lv, "upgrade costs (qty)")
    _curve_or_raise(common_by_lv, "common attrs")
    _curve_or_raise(power_by_lv, "power")
    _curve_or_raise(rank_by_lv, "skill ranks")
    if extra_costs:
        raise ValueError("upgrade rows have extra cost items")
    if generic_in_cost:
        raise ValueError("generic shard 230003 appeared in the cost column")

    levels: list[LevelRow] = []
    cum = 0
    prev_attrs = {i: 0 for i in COMMON_ATTR_IDS}
    prev_power = 0
    for lv in range(1, 101):
        typ, qty = next(iter(cost_by_lv[lv]))
        if typ != 2:
            raise ValueError(f"unexpected upgrade cost type {typ}")
        cum += qty
        attrs = {aid: val for aid, val in next(iter(common_by_lv[lv]))}
        power = next(iter(power_by_lv[lv]))
        rank = next(iter(rank_by_lv[lv]))[0]
        delta = {i: attrs[i] - prev_attrs[i] for i in COMMON_ATTR_IDS}
        dpower = power - prev_power
        stage, preview = next(iter(appear_by_lv[lv]))
        appearance = ""
        if lv in APPEARANCE_LEVELS:
            appearance = f"外觀欄改為 lv{stage}（preview={preview}）"
        levels.append(
            LevelRow(lv, qty, cum, attrs, power, rank, delta, dpower, appearance)
        )
        prev_attrs, prev_power = attrs, power
    if levels[-1].cumulative != 3163:
        raise ValueError(f"upgrade total is {levels[-1].cumulative}, expected 3163")

    expected_rank_lv = {SKILL_LEVEL_BY_RANK[r]: r for r in SKILL_LEVEL_BY_RANK}
    prev_rank = 0
    for row in levels:
        if row.skill_rank != prev_rank:
            if expected_rank_lv.get(row.level) != row.skill_rank:
                raise ValueError(f"unexpected skill rank {row.skill_rank} at lv {row.level}")
            prev_rank = row.skill_rank

    lv_item_by_index = {}
    sixth_track: dict[int, dict[int, tuple[int, int]]] = defaultdict(dict)
    skill_by_index: dict[int, int] = {}
    for r in lvup:
        idx, lv = int(r["index"]), int(r["lv"])
        if lv == 1:
            lv_item_by_index[idx] = int(r["costArr"][0][1])
            skill_by_index[idx] = int(r["skillArr"][0][0])
        attrs = attr_map(r.get("attrs"))
        extra = [(aid, val) for aid, val in attrs.items() if aid not in COMMON_ATTR_IDS]
        if len(extra) != 1:
            raise ValueError(f"{idx} lv{lv} does not have exactly one exclusive attr")
        sixth_track[idx][lv] = extra[0]
        if int(r["costArr"][0][1]) != lv_item_by_index[idx]:
            raise ValueError(f"{idx} cost item changes at lv {lv}")

    spirits: list[SpiritRow] = []
    for faction, _anchor, entries in ROSTER:
        for hid, name in entries:
            row = defn_by.get(hid)
            if not row:
                continue
            page = assemble(hid)
            if page.faction != faction:
                raise ValueError(f"faction mismatch {hid}: {page.faction} vs roster {faction}")
            cost_item = lv_item_by_index[hid]
            spirit = t(row["name"]) or t(f"hero_valhalla_name_{hid}")
            if "契約之獅" in spirit:
                raise ValueError("official name unexpectedly contains 契約之獅")
            short = unwrap_spirit_name(spirit)
            skill_id = skill_by_index[hid]
            comp = component(skill_id)
            if not comp:
                raise ValueError(f"missing hero_component {skill_id}")
            skill_name = t(comp.get("name")) or str(skill_id)
            ranks = []
            for n in range(1, 6):
                filled = _fill_rank(comp, n)
                if not filled:
                    raise ValueError(f"empty skill desc{n} for {skill_id}")
                ranks.append(f"{n} 階：{filled}")
            sixth_id = sixth_track[hid][100][0]
            if any(sixth_track[hid][lv][0] != sixth_id for lv in sixth_track[hid]):
                raise ValueError(f"{hid} exclusive attr type changes across levels")
            sixth_by_lv = {lv: sixth_track[hid][lv][1] for lv in SIXTH_BREAKS}
            ff = tuple(int(x) for x in (comp.get("fightforce") or []))
            label = roster_display_name(hid, name)
            spirits.append(
                SpiritRow(
                    hero_id=hid,
                    hero_name=name,
                    hero_label=label,
                    faction=faction,
                    spirit=spirit,
                    spirit_short=short,
                    shard_item=cost_item,
                    shard_name=t(f"goods_name_{cost_item}"),
                    shard_desc=t(f"goods_desc_{cost_item}"),
                    sixth_id=sixth_id,
                    sixth_name=attr_label(sixth_id),
                    sixth_max=sixth_track[hid][100][1],
                    sixth_by_lv=sixth_by_lv,
                    skill_id=skill_id,
                    skill=skill_name,
                    skill_desc=_fill_rank(comp, 1),
                    ranks=ranks,
                    fightforce=ff,
                    unlock_season=str(row["unlock_season"]),
                    unlock_server=str(row["unlock_server"]),
                    live_url=LIVE_HERO.format(id=hid),
                    self_attrs=_self_attrs(comp),
                )
            )

    if len(spirits) != 15:
        raise ValueError(f"expected 15 spirits, got {len(spirits)}")
    split = Counter(s.faction for s in spirits)
    if split != {"聯盟": 5, "自然": 5, "部族": 5}:
        raise ValueError(f"unexpected faction split {split}")
    if any(s.fightforce != (100, 150, 200, 250, 300) for s in spirits):
        raise ValueError("skill fightforce is not uniform")

    verifications = {
        "spirit_rows": len(defs),
        "lvup_rows": len(lvup),
        "upgrade_total": levels[-1].cumulative,
        "cost_identical": True,
        "common_attr_identical": True,
        "power_identical": True,
        "faction_split": dict(split),
        "unlock_star": 11,
        "unlock_day": 60,
        "star_max": 15,
        "unlock_season_values": sorted({s.unlock_season for s in spirits}),
        "unlock_server_values": sorted({s.unlock_server for s in spirits}),
        "generic_in_cost": False,
        "lv1_hero_atk_raw": levels[0].attrs[103],
        "lv1_hero_atk_display": format_attr(103, levels[0].attrs[103]),
        "lv100_power": levels[-1].power,
        "data_cutoff": VALHALLA_DATA_CUTOFF,
    }
    # 與前服預覽／手冊第二版抽樣核對（共用前五項；第 6 項以 10031 技能減傷為代表）。
    samples = {
        1: (80, 2400, "3.60%", "10.80%", "0", 44600),
        25: (2000, 60000, "55.20%", "165.60%", "2", 176650),
        50: (4000, 120000, "139.20%", "417.60%", "5", 354200),
        75: (6000, 180000, "229.20%", "687.60%", "7", 498850),
        100: (8000, 240000, "320.00%", "960.00%", "10", 627500),
    }
    for lv, exp in samples.items():
        row = levels[lv - 1]
        got = (
            int(format_attr(3, row.attrs[3])),
            int(format_attr(4, row.attrs[4])),
            format_attr(103, row.attrs[103]),
            format_attr(104, row.attrs[104]),
            format_attr(1098, row.attrs[1098]),
            row.power,
        )
        if got != exp:
            raise ValueError(f"display sample mismatch at lv{lv}: {got} != {exp}")
    lion = next(s for s in spirits if s.hero_id == 10031)
    if format_attr(lion.sixth_id, lion.sixth_by_lv[1]) != "0.00%":
        raise ValueError("lv1 sixth display")
    if format_attr(lion.sixth_id, lion.sixth_by_lv[100]) != "50.00%":
        raise ValueError("lv100 sixth display")
    if any(s.unlock_server != CURRENT_UNLOCK_SERVER for s in spirits):
        raise ValueError(f"unexpected unlock_server: {set(s.unlock_server for s in spirits)}")
    data = TablesData(
        levels=levels,
        spirits=spirits,
        upgrade_total=levels[-1].cumulative,
        generic_shard_name=t("goods_name_230003"),
        generic_shard_desc=t("goods_desc_230003"),
        verifications=verifications,
        terms=terms_for(spirits),
    )
    return data


def _hero_display(s: SpiritRow) -> str:
    if s.hero_name is None:
        return str(s.hero_id)
    return f"{s.hero_label}（{s.hero_id}）"


def _hero_href_public(s: SpiritRow) -> str:
    if hero_href(s.hero_id):
        return f"heroes/{s.hero_id}.html"
    return ""


def _hero_link_html(s: SpiritRow, terms: list[str]) -> str:
    label = H(_hero_display(s), terms)
    href = _hero_href_public(s)
    if href:
        return f'<a href="{e(href)}">{label}</a>'
    return label


def _hero_link_md(s: SpiritRow) -> str:
    label = _hero_display(s)
    if hero_href(s.hero_id):
        return f"[{label}]({s.live_url})"
    return label


def _cost_segments(levels: list[LevelRow]) -> list[tuple[str, int]]:
    segs: list[tuple[str, int]] = []
    start = levels[0].level
    prev = levels[0].cost
    for row in levels[1:]:
        if row.cost != prev:
            end = row.level - 1
            label = f"{start} 級" if start == end else f"{start}–{end} 級"
            segs.append((label, prev))
            start = row.level
            prev = row.cost
    end = levels[-1].level
    label = f"{start} 級" if start == end else f"{start}–{end} 級"
    segs.append((label, prev))
    return segs


def _level_note(row: LevelRow, prev_rank: int | None, *, html: bool = False) -> str:
    bits = []
    if prev_rank is None or row.skill_rank != prev_rank:
        bits.append(f"專屬技能 {row.skill_rank} 階")
    if row.appearance:
        if html:
            text = row.appearance.replace("外觀欄改為 lv", "外觀欄改為第 ").replace("（preview=", " 檔（預覽標記為 ")
            bits.append(text)
        else:
            bits.append(row.appearance)
    if row.delta_attrs[1098]:
        bits.append(f"英雄等級上限 {row.attrs[1098]}")
    return "；".join(bits)


def _jump_nav(prefix: str, levels: list[int], label: str) -> str:
    links = " ".join(
        f'<a href="#{prefix}{lv}">{lv}</a>' for lv in levels
    )
    return f'<p class="jump-nav">{e(label)}：{links}</p>'


def _batch_groups(spirits: list[SpiritRow]) -> list[tuple[str, str, list[SpiritRow], str]]:
    """Return handbook batches. 3|9 stays two rows; current server value is recorded on both."""
    by_id = {s.hero_id: s for s in spirits}
    rows = []
    for season, ids in BATCH_IDS:
        group = []
        for hid in ids:
            s = by_id[hid]
            if s.unlock_season != season or s.unlock_server != CURRENT_UNLOCK_SERVER:
                raise ValueError(
                    f"batch mismatch {hid}: season={s.unlock_season} server={s.unlock_server}"
                )
            group.append(s)
        note = ""
        if set(ids) == set(PREVIOUS_NARROW_HEROES):
            note = (
                f"先前的伺服器欄為 {PREVIOUS_NARROW_SERVER}；"
                f"現用資料已改為 {CURRENT_UNLOCK_SERVER}。只記現用值，不標已開放或未開放。"
            )
        rows.append((season, CURRENT_UNLOCK_SERVER, group, note))
    return rows


def render_html(data: TablesData, *, include_charts: bool = True) -> str:
    from .render import page_shell, toc_list
    from .valhalla_charts import charts_section_html

    terms = data.terms
    title = "Top Heroes Wiki｜英靈總表"
    summary = "Top Heroes 英靈總表：15 隻英靈的升級素材、共通屬性、專屬屬性與專屬技能，以及素材消耗對能力提升的邊際效果。"

    jumps = [1, 10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100]
    segs = _cost_segments(data.levels)
    t_seg = table(["等級範圍", "本級專屬碎片"], [[e(a), e(raw(b))] for a, b in segs])

    t1_rows = []
    t1_ids = []
    prev_rank = None
    for r in data.levels:
        note = _level_note(r, prev_rank, html=True)
        t1_rows.append([
            e(f"{r.level} 級"),
            e(raw(r.cost)),
            e(raw(r.cumulative)),
            e(format_attr(3, r.attrs[3])),
            e(format_attr(4, r.attrs[4])),
            e(format_attr(103, r.attrs[103])),
            e(format_attr(104, r.attrs[104])),
            e(format_attr(1098, r.attrs[1098])),
            e(format_power(r.power)),
            e(str(r.skill_rank)),
            e(note) if note else "—",
        ])
        t1_ids.append(f"u-lv-{r.level}")
        prev_rank = r.skill_rank
    t1 = table(
        [
            "等級（到達該級）",
            "本級專屬碎片",
            "累計專屬碎片",
            e(attr_header(3)),
            e(attr_header(4)),
            e(attr_header(103)),
            e(attr_header(104)),
            e(attr_header(1098)),
            "戰力",
            "技能階",
            "解鎖／備註",
        ],
        t1_rows,
        row_ids=t1_ids,
        wrap_class="table-dense",
        mobile="sticky",
    )

    sixth_headers = ["陣營", "英靈", "專屬屬性"] + [f"{lv} 級" for lv in SIXTH_BREAKS]
    sixth_rows = []
    for s in data.spirits:
        sixth_rows.append(
            [H(s.faction, terms), H(s.spirit, terms), H(attr_header(s.sixth_id), terms)]
            + [e(format_attr(s.sixth_id, s.sixth_by_lv[lv])) for lv in SIXTH_BREAKS]
        )
    t_sixth = table(sixth_headers, sixth_rows, wrap_class="table-dense", mobile="sticky2")

    t2_rows = []
    for s in data.spirits:
        ranks = "<br>".join(Hl(r, terms) for r in s.ranks)
        self_txt = _self_attr_text(s.self_attrs)
        skill_cell = f'<p>{H(s.skill + "：" + s.skill_desc, terms)}</p>{ranks}'
        if self_txt:
            skill_cell += f"<p>{H(self_txt, terms)}</p>"
        t2_rows.append([
            H(s.faction, terms),
            _hero_link_html(s, terms),
            H(s.spirit, terms),
            Hl(s.shard_desc, terms) if s.shard_desc else "（沒有對應的碎片說明字串。）",
            f"{H(attr_header(s.sixth_id), terms)} {e(format_attr(s.sixth_id, s.sixth_max))}",
            skill_cell,
        ])
    t2 = table(
        ["陣營", "英雄", "英靈", "官方說明", "滿級專屬屬性", "專屬技能全文與五階（對應 1／25／50／75／100 級）"],
        t2_rows,
        mobile="cards",
        card_title="英靈",
    )

    batch_rows = []
    for season, server, group, note in _batch_groups(data.spirits):
        names = "、".join(f"{s.spirit_short}（{s.hero_label}，{s.hero_id}）" for s in group)
        batch_rows.append([e(season), e(server), e(str(len(group))), H(names, terms), H(note, terms) if note else "—"])
    t_batch = table(["解鎖賽季欄（照錄）", "解鎖伺服器欄（照錄）", "隻數", "英靈", "備註"], batch_rows, mobile="cards", card_title="英靈")

    t3_rows = []
    t3_ids = []
    prev_rank = None
    for r in data.levels:
        note = _level_note(r, prev_rank, html=True)
        t3_rows.append([
            e(f"{r.level} 級"),
            e(raw(r.cost)),
            e(format_attr(3, r.delta_attrs[3])),
            e(format_attr(4, r.delta_attrs[4])),
            e(format_attr(103, r.delta_attrs[103])),
            e(format_attr(104, r.delta_attrs[104])),
            e(format_attr(1098, r.delta_attrs[1098])),
            e(format_power(r.delta_power)),
            e(ratio(r.delta_power, r.cost)),
            e(note) if note else "—",
        ])
        t3_ids.append(f"m-lv-{r.level}")
        prev_rank = r.skill_rank
    t3 = table(
        [
            "等級",
            "本級專屬碎片",
            e(attr_header(3, delta=True)),
            e(attr_header(4, delta=True)),
            e(attr_header(103, delta=True)),
            e(attr_header(104, delta=True)),
            e(attr_header(1098, delta=True)),
            "Δ戰力",
            "每碎片Δ戰力（推算）",
            "解鎖／備註",
        ],
        t3_rows,
        row_ids=t3_ids,
        wrap_class="table-dense",
        mobile="sticky",
    )

    charts = charts_section_html(data) if include_charts else ""

    toc = toc_list([
        {"label": "簡介", "id": "lead"},
        {"label": "表一、通用升級素材與共通屬性", "id": "t1"},
        {"label": "消耗分段", "id": "t1-seg", "depth": 1},
        {"label": "解鎖欄位（照錄，不換算）", "id": "t1-batch", "depth": 1},
        {"label": "表二、15 隻英靈", "id": "t2"},
        {"label": "專屬屬性成長", "id": "t2-sixth", "depth": 1},
        {"label": "表三、素材消耗對能力提升的邊際效果", "id": "t3"},
        {"label": "資料說明", "id": "notes"},
    ])

    h3, h4, h103, h104, h1098 = (H(attr_header(i), terms) for i in COMMON_ATTR_IDS)
    official_3, official_4 = H(attr_label(3), terms), H(attr_label(4), terms)
    gen_name = H(data.generic_shard_name, terms)
    gen_desc = H(data.generic_shard_desc, terms)
    ui_name = H(t("system_valhalla_des1") or "英靈", terms)
    ui_how = H(t("system_valhalla_des12"), terms)
    ui_show = e(t("system_valhalla_des16"))

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">本頁列出 15 隻英靈的升級素材、共通屬性、各隻專屬屬性與專屬技能，以及素材消耗對能力提升的邊際效果。</p>
    </header>
    {toc}
    <section id="lead">
      <h2>簡介</h2>
      <p>介面名稱是「{ui_name}」。官方說明寫「{ui_how}」{ui_show}。57 名可收集英雄裡，15 人各有一隻英靈。其餘英雄目前沒有英靈，本頁也不另外補。</p>
      <p>啟用條件 15 人相同：英雄要到 11 星（這 15 人的星級上限都是 15）、開服第 60 天，再用該英靈專屬碎片 10 個。本頁不據此標成已開放或未開放，也沒有「已推出」欄。</p>
      <p>15 隻的每級碎片數量、戰力、前五項共通屬性都相同，只有第 6 項專屬屬性的種類與數值、以及專屬技能不同。滿級 100。第 1 至 100 級專屬碎片相加共 {comma(data.upgrade_total)}（含第 1 級的 10 個）。排列依本站英雄目錄：聯盟 → 自然 → 部族（各 5 隻）。表頭用「點數」和「百分比」區分兩種英雄攻擊與英雄生命，寫成{h3}、{h4}、{h103}、{h104}、{h1098}。點數沒有百分號，百分比寫成兩位小數。戰力照表上整數書寫（滿級 627500）；升級效果預覽畫面寫 628K，是四捨五入，本表不改成 628K。這套顯示規則只用於本頁英靈屬性，不套到專武、稱號或羈絆。</p>
      <p>{gen_name}的官方說明寫「{gen_desc}」它不在升級消耗欄，本表不把它寫成必消耗列。消耗欄只記各英靈自己的專屬碎片數量。</p>
    </section>
    <section id="t1">
      <h2>表一、通用升級素材與共通屬性</h2>
      <p>等級指升級後的英靈等級。本級專屬碎片是到達該級時的消耗（第 1 級為 10）。累計是第 1 級到該級相加。本表只記數量，不區分各隻專屬碎片名稱。前五項屬性與戰力 15 隻共用，錄的是該級累計顯示值，不是本級增量。第 6 項專屬屬性因種類不同，列在表二。</p>
      <p>專屬技能在 1／25／50／75／100 級升階。升級表的外觀欄在 75 級改為第 2 檔、100 級改為第 3 檔（這兩級的預覽標記為 1）；此處只記欄位變更，不描述外觀。</p>
      {_jump_nav("u-lv-", jumps, "跳到等級")}
      {t1}
      <section id="t1-seg">
        <h3>消耗分段</h3>
        <p>下表是表一「本級專屬碎片」欄的分段整理，方便對照；不是另一張獨立資料表。1–100 級相加仍是 {comma(data.upgrade_total)}。</p>
        {t_seg}
      </section>
      <section id="t1-batch">
        <h3>解鎖欄位（照錄，不換算）</h3>
        <p>以下照錄定義表的解鎖欄位原值，不自行對成 S2／S3，也不標已開放或未開放。現用資料 15 筆的伺服器欄都是 {e(CURRENT_UNLOCK_SERVER)}。賽季欄有 {e("2|5")}、{e("3|0")}、{e("3|5")}、{e("3|9")} 四種寫法；前三種各 3 隻，{e("3|9")} 仍分兩列（各 3 隻）。主教、行者、妖精先前的伺服器欄為 {e(PREVIOUS_NARROW_SERVER)}，現用資料已改為與其他列相同，只記現用值。欄位名見資料說明。</p>
        {t_batch}
      </section>
    </section>
    <section id="t2">
      <h2>表二、15 隻英靈</h2>
      <p>官方名稱照字串錄成英靈「短名」這種形式。官方說明錄各隻碎片說明原文。滿級專屬屬性寫成百分比。技能全文與五階照原文列出，不改寫成一句滿級描述。技能戰力 15 隻都是 100／150／200／250／300，不另分欄。風暴領主、娜迦女王的技能另有自身屬性，同樣寫成百分比。英雄名連到本站對應條目。</p>
      {t2}
      <section id="t2-sixth">
        <h3>專屬屬性成長</h3>
        <p>第 6 項專屬屬性 1 級為 0.00%，之後在 10、20、30……100 級加一檔，寫成百分比。下表列出這些檔位的顯示值，沒有把中間等級（數值與上一檔相同）再寫一遍。</p>
        {t_sixth}
      </section>
    </section>
    <section id="t3">
      <h2>表三、素材消耗對能力提升的邊際效果</h2>
      <p>此表列的是<strong>本級增量</strong>，不是累計值。第 1 級的增量等於該檔相對 0 的數值。共通屬性的增量用與表一相同的顯示規則（點數或百分比），不加加號。第 6 項專屬屬性因種類不同，沒有加進本表，請看表二。每碎片Δ戰力是本級Δ戰力除以該級專屬碎片，屬於依分欄推算，不是資料表原有欄位。多數等級的Δ戰力是 3150；技能升階（25／50／75／100）以及部分 10 的倍數等級會有較大跳升。</p>
      {charts}
      {_jump_nav("m-lv-", jumps, "跳到等級")}
      {t3}
    </section>
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>資料出自遊戲資料表與官方字串（{e("hero_valhalla")}、{e("hero_valhalla_lvup")}、{e("hero_component")}、{e("strings_zh.json")}），資料截至 {VALHALLA_DATA_CUTOFF}（香港時間）。本頁是英靈，不是神器；沒有使用神器表。</li>
        <li>以下是整理用註記，查效果與數值可略過。屬性顯示依 show_type，並以 {VALHALLA_DATA_CUTOFF} 前服審判官英靈「誓約之獅」100 級「升級效果預覽」核對。表頭用點數／百分比區分，不再掛屬性編號：點數對應 3、4、1098，百分比對應 103、104 以及第 6 項專屬屬性與技能自身屬性（attribute_self）。show_type 1 寫點數，無百分號、無千位分符、不加加號；show_type 2 為原值÷100，兩位小數加百分號。表頭寫成{h3}、{h4}、{h103}、{h104}、{h1098}；官方字串名稱 3 與 103 都是{official_3}，4 與 104 都是{official_4}。戰力滿級為 627500，畫面寫 628K 是四捨五入，本表維持 627500。這套規則只用於本頁英靈屬性。unlock_season、unlock_server 只照錄欄位原值，不自行改寫成第幾賽季，也不據此標成已開放或未開放。</li>
        <li>妖精碎片說明官方寫「{H("集齊一定數量的碎片即可解鎖妖精英靈。碎片還可以用於英靈強化", terms)}」（「妖精英靈」中間沒有「的」），照錄。</li>
        <li>織夢花靈專屬技能「{H("惡作劇", terms)}」第 4、5 階原文兩個位置都寫 {e("{0}")}。第 4 階兩個參數都是 8，填入後是「暴擊率+8%，暴擊抗性+8%」。第 5 階參數是 60 與 100，但兩個位置都只代入第一個參數，照錄為「分身從本體繼承的屬性提升60%。【花香】造成的傷害提升60%」。</li>
        <li>行者專屬技能「{H("齊天鎮岳", terms)}」第 4 階官方原文是「全體部落增傷率+10%，免傷率+20%」。本頁正文用語是部族，這句技能仍照錄「部落」。</li>
        <li>官方用字並不完全統一，一律照錄：例如「釋放／施放」、「暴擊／爆擊」、「閃避／迴避」。</li>
        <li>另有首發／啟用禮包字串。薔薇公主那筆首發禮包字串只寫「英靈首發禮包」，沒有冠上英靈短名。本頁不展開活動與儲值。</li>
        <li>不把 unlock_season、unlock_server 自行標成未開放。本頁沒有社群備註，也沒有把猜測寫進正文，也不寫戰鬥結算公式。可見外觀欄寫第 2 檔／第 3 檔，預覽標記為 1；原欄為 lv2／lv3，preview=1。</li>
      </ul>
    </section>
    """
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    # 只改本頁頁腳，不改 render.page_shell 的全域資料截止日期。
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {VALHALLA_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    # Preview-tested: keep the second frozen column aligned to the real first-column width.
    html = html.replace(
        "</body>",
        "<script>"
        "function syncStickyOffsets(){"
        "document.querySelectorAll('.table-wrap.table-sticky-col-2').forEach(function(wrap){"
        "var th=wrap.querySelector('thead th:first-child');"
        "if(th){wrap.style.setProperty('--sticky-col1',th.getBoundingClientRect().width+'px');}"
        "});}"
        "syncStickyOffsets();"
        "addEventListener('resize',syncStickyOffsets);"
        "</script>\n</body>",
        1,
    )
    return html


def render_markdown(data: TablesData) -> str:
    lines: list[str] = []
    lines.append("# Top Heroes Wiki｜英靈總表（未發佈預覽）")
    lines.append("")
    lines.append("這是未發佈的本機預覽，不是線上目錄，也不會寫進公開站。")
    lines.append("")
    lines.append(f"資料截至 {VALHALLA_DATA_CUTOFF}（香港時間）。這不是官方 wiki。本頁是英靈，不是神器。")
    lines.append("")
    lines.append("## 簡介")
    lines.append("")
    lines.append(
        f"介面名稱是「{t('system_valhalla_des1') or '英靈'}」。"
        f"官方說明寫「{t('system_valhalla_des12')}」{t('system_valhalla_des16')}。"
        "57 名可收集英雄裡，15 人各有一隻英靈。"
        "其餘英雄目前沒有英靈，本頁也不另外補。"
    )
    lines.append("")
    lines.append(
        "啟用條件 15 人相同：英雄星級 11（這 15 人的星級上限都是 15）、開服第 60 天，"
        "再用該英靈專屬碎片 10 個。"
        "本頁不據此標成已開放或未開放，也沒有「已推出」欄。"
    )
    lines.append("")
    lines.append(
        "15 隻的每級碎片數量、戰力、前五項共通屬性都相同，只有第 6 項專屬屬性的種類與數值、以及專屬技能不同。"
        f"滿級 100。第 1 至 100 級專屬碎片相加共 {comma(data.upgrade_total)}（含第 1 級的 10 個）。"
        "排列依本站英雄目錄：聯盟 → 自然 → 部族（各 5 隻）。"
        f"表頭用「點數」和「百分比」區分兩種英雄攻擊與英雄生命，寫成{attr_header(3)}、{attr_header(4)}、{attr_header(103)}、{attr_header(104)}、{attr_header(1098)}。"
        "點數沒有百分號，百分比寫成兩位小數。"
        "戰力照表上整數書寫（滿級 627500）；升級效果預覽畫面寫 628K，是四捨五入，本表不改成 628K。"
        "這套顯示規則只用於本頁英靈屬性，不套到專武、稱號或羈絆。"
    )
    lines.append("")
    lines.append(
        f"{data.generic_shard_name}的官方說明寫「{data.generic_shard_desc}」"
        "它不在升級消耗欄，本表不把它寫成必消耗列。消耗欄只記各英靈自己的專屬碎片數量。"
    )
    lines.append("")
    lines.append("## 表一、通用升級素材與共通屬性")
    lines.append("")
    lines.append(
        "等級指升級後的英靈等級。本級專屬碎片是到達該級時的消耗（第 1 級為 10）。"
        "累計是第 1 級到該級相加。前五項屬性與戰力 15 隻共用，錄的是該級累計顯示值。"
        "專屬技能在 1／25／50／75／100 級升階。升級表的外觀欄在 75 級改為 lv2、100 級改為 lv3（這兩級的 preview 為 1）。"
    )
    lines.append("")
    t1_rows = []
    prev_rank = None
    for r in data.levels:
        note = _level_note(r, prev_rank) or "—"
        t1_rows.append([
            f"{r.level} 級",
            raw(r.cost),
            raw(r.cumulative),
            format_attr(3, r.attrs[3]),
            format_attr(4, r.attrs[4]),
            format_attr(103, r.attrs[103]),
            format_attr(104, r.attrs[104]),
            format_attr(1098, r.attrs[1098]),
            format_power(r.power),
            str(r.skill_rank),
            note,
        ])
        prev_rank = r.skill_rank
    lines.append(md_table(
        [
            "等級（到達該級）",
            "本級專屬碎片",
            "累計專屬碎片",
            attr_header(3),
            attr_header(4),
            attr_header(103),
            attr_header(104),
            attr_header(1098),
            "戰力",
            "技能階",
            "解鎖／備註",
        ],
        t1_rows,
    ))
    lines.append("")
    lines.append("### 消耗分段")
    lines.append("")
    lines.append(f"下表是表一「本級專屬碎片」欄的分段整理。1–100 級相加仍是 {comma(data.upgrade_total)}。")
    lines.append("")
    lines.append(md_table(["等級範圍", "本級專屬碎片"], [[a, raw(b)] for a, b in _cost_segments(data.levels)]))
    lines.append("")
    lines.append("### 解鎖欄位（照錄，不換算）")
    lines.append("")
    lines.append(
        "以下照錄定義表的解鎖欄位原值，不自行對成 S2／S3，也不標已開放或未開放。"
        f"現用資料 15 筆的伺服器欄都是 `{CURRENT_UNLOCK_SERVER}`。"
        "賽季欄有 `2|5`、`3|0`、`3|5`、`3|9` 四種寫法；前三種各 3 隻，`3|9` 仍分兩列（各 3 隻）。"
        f"主教、行者、妖精先前的伺服器欄為 `{PREVIOUS_NARROW_SERVER}`，現用資料已改為與其他列相同，只記現用值。欄位名見資料說明。"
    )
    lines.append("")
    batch_rows = []
    for season, server, group, note in _batch_groups(data.spirits):
        names = "、".join(f"{s.spirit_short}（{s.hero_label}，{s.hero_id}）" for s in group)
        batch_rows.append([season, server, str(len(group)), names, note or "—"])
    lines.append(md_table(["解鎖賽季欄（照錄）", "解鎖伺服器欄（照錄）", "隻數", "英靈", "備註"], batch_rows))
    lines.append("")
    lines.append("## 表二、15 隻英靈")
    lines.append("")
    lines.append(
        "官方名稱照字串錄成英靈「短名」這種形式。技能全文與五階照原文列出。"
        "滿級專屬屬性依 show_type 2 寫成百分比。"
        "技能戰力 15 隻都是 100／150／200／250／300。"
        "風暴領主、娜迦女王的技能列另有 attribute_self，同樣依 show_type 2 寫成百分比。"
        "英雄名連到本站對應條目。"
    )
    lines.append("")
    t2_rows = []
    for s in data.spirits:
        ranks = "<br>".join(s.ranks)
        skill_cell = f"{s.skill}：{s.skill_desc}<br>{ranks}"
        self_txt = _self_attr_text(s.self_attrs)
        if self_txt:
            skill_cell += f"<br>{self_txt}"
        t2_rows.append([
            s.faction,
            _hero_link_md(s),
            s.spirit,
            s.shard_desc or "（沒有對應的碎片說明字串。）",
            f"{attr_header(s.sixth_id)} {format_attr(s.sixth_id, s.sixth_max)}",
            skill_cell,
        ])
    lines.append(md_table(
        ["陣營", "英雄", "英靈", "官方說明", "滿級專屬屬性", "專屬技能全文與五階（對應 1／25／50／75／100 級）"],
        t2_rows,
    ))
    lines.append("")
    lines.append("### 專屬屬性成長")
    lines.append("")
    lines.append("第 6 項專屬屬性 1 級為 0.00%，之後在 10、20、30……100 級加一檔，依 show_type 2 寫成百分比。下表列出這些檔位的顯示值。")
    lines.append("")
    sixth_rows = []
    for s in data.spirits:
        sixth_rows.append(
            [s.faction, s.spirit, attr_header(s.sixth_id)]
            + [format_attr(s.sixth_id, s.sixth_by_lv[lv]) for lv in SIXTH_BREAKS]
        )
    lines.append(md_table(
        ["陣營", "英靈", "專屬屬性"] + [f"{lv} 級" for lv in SIXTH_BREAKS],
        sixth_rows,
    ))
    lines.append("")
    lines.append("## 表三、素材消耗對能力提升的邊際效果")
    lines.append("")
    lines.append(
        "此表列的是本級增量，不是累計值。第 1 級的增量等於該檔相對 0 的數值。"
        "共通屬性的增量用與表一相同的顯示規則（點數或百分比），不加加號。"
        "每碎片Δ戰力是本級Δ戰力除以該級專屬碎片，屬於依分欄推算，不是資料表原有欄位。"
        "第 6 項專屬屬性因種類不同，沒有加進本表。"
        "折線圖見同目錄的 HTML 預覽與 PNG。"
    )
    lines.append("")
    t3_rows = []
    prev_rank = None
    for r in data.levels:
        note = _level_note(r, prev_rank) or "—"
        t3_rows.append([
            f"{r.level} 級",
            raw(r.cost),
            format_attr(3, r.delta_attrs[3]),
            format_attr(4, r.delta_attrs[4]),
            format_attr(103, r.delta_attrs[103]),
            format_attr(104, r.delta_attrs[104]),
            format_attr(1098, r.delta_attrs[1098]),
            format_power(r.delta_power),
            ratio(r.delta_power, r.cost),
            note,
        ])
        prev_rank = r.skill_rank
    lines.append(md_table(
        [
            "等級",
            "本級專屬碎片",
            attr_header(3, delta=True),
            attr_header(4, delta=True),
            attr_header(103, delta=True),
            attr_header(104, delta=True),
            attr_header(1098, delta=True),
            "Δ戰力",
            "每碎片Δ戰力（推算）",
            "解鎖／備註",
        ],
        t3_rows,
    ))
    lines.append("")
    lines.append("## 資料說明")
    lines.append("")
    lines.append(f"- 資料出自遊戲資料表與官方字串，資料截至 {VALHALLA_DATA_CUTOFF}（香港時間）。本頁是英靈，不是神器。")
    lines.append(
        f"- 屬性顯示依 show_type，並以 {VALHALLA_DATA_CUTOFF} 前服審判官英靈「誓約之獅」100 級「升級效果預覽」核對。"
        f"表頭寫成{attr_header(3)}、{attr_header(4)}、{attr_header(103)}、{attr_header(104)}、{attr_header(1098)}；"
        f"官方字串名稱 3 是{attr_label(3)}、4 是{attr_label(4)}。"
        "戰力滿級為 627500，畫面寫 628K 是四捨五入，本表維持 627500。這套規則只用於本頁英靈屬性，不套到專武、稱號或羈絆。"
    )
    lines.append("- 妖精碎片說明官方寫「集齊一定數量的碎片即可解鎖妖精英靈。碎片還可以用於英靈強化」（「妖精英靈」中間沒有「的」），照錄。")
    lines.append("- 織夢花靈「惡作劇」第 5 階原文兩個位置都寫 `{0}`，參數是 60 與 100，但只代入第一個參數，照錄為「分身從本體繼承的屬性提升60%。【花香】造成的傷害提升60%」。")
    lines.append("- 行者「齊天鎮岳」第 4 階官方原文是「全體部落增傷率+10%，免傷率+20%」。本頁正文用語是部族，這句技能仍照錄「部落」。")
    lines.append("- 官方用字並不完全統一，一律照錄：例如「釋放／施放」、「暴擊／爆擊」、「閃避／迴避」。")
    lines.append("- 薔薇公主那筆首發禮包字串只寫「英靈首發禮包」，沒有冠上英靈短名。本頁不展開活動與儲值。")
    lines.append("- 不把 unlock_season、unlock_server 自行標成已開放或未開放。本頁沒有社群備註，也不寫戰鬥結算公式。")
    lines.append("")
    return "\n".join(lines)

def render_valhalla_page(data: TablesData | None = None) -> str:
    """Public 英靈總表 HTML for docs/valhalla.html. No unpublished banner."""
    return render_html(data or load_tables_data())
