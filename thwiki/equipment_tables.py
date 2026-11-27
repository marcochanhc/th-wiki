"""Compile the published 裝備 catalog tables."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .assemble import hero_href
from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .overrides import UNRELEASED_HERO_IDS, roster_display_name
from .paths import DATA_CUTOFF
from .strings import clean, t
from .tables import catalog, load_table
from . import attrs as A


# 裝備總表專用；不改 paths.DATA_CUTOFF，以免影響首頁與英雄條目的全局截止日。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁腳／截止日寫資料日的次日。
# 17 張 equipment*.json 與 hero_detail.json 與 2026-11-05 解壓檔位元組相同，
# 但不表示整個 LocalLow 包與該日解壓檔相同。
EQUIP_DATA_CUTOFF = "2026-11-23"
EQUIP_DATA_PACK = "app-1.129.12_table-1.0.43173"
EQUIP_DATA_PACKED = "2026-11-22 23:33"

LIVE_HERO = "https://marcochanhc.github.io/th-wiki/heroes/{id}.html"
LIVE_EXCLUSIVE = "https://marcochanhc.github.io/th-wiki/exclusive.html"

# 實際掛在 equipment_new 上的 12 套，順序依第 13 章總覽表。
LIVE_SUIT_ORDER = (1101, 1102, 1103, 311, 312, 313, 314, 315, 319, 301, 302, 303)
NEW_SUIT_IDS = (1101, 1102, 1103)
OLD_SUIT_IDS = (311, 312, 313, 314, 315, 319, 301, 302, 303)
# 本站標未開放；表上沒有裝備「已推出」欄。來源見資料說明。
UNRELEASED_SUIT_IDS = frozenset(NEW_SUIT_IDS)
UNFILLED_SUIT_IDS = (101, 102)

# 第 13 章總覽表的官方效果文案（用來核對 live 字串，不是另一套文案）。
CHAPTER_OVERVIEW = {
    1101: "集齊4件：裝備攻擊+20%，增傷+3%／4件升至40級：裝備攻擊+80%，增傷+6%／4件突破至紅色：裝備攻擊+160%，增傷+12%",
    1102: "集齊4件：裝備生命+40%，減傷+3%／4件升至40級：裝備生命+160%，減傷+6%／4件突破至紅色：裝備生命+480%，減傷+12%",
    1103: "集齊4件：裝備攻擊+10%，裝備生命+20%，技能增傷+4%／4件升至40級：裝備攻擊+40%，裝備生命+80%，技能增傷+8%／4件突破至紅色：裝備攻擊+80%，裝備生命+240%，技能增傷+16%",
    311: "2件：裝備攻擊+10%／4件：釋放任意技能後，爆擊率提高25%，持續6秒，冷卻18秒",
    312: "2件：裝備生命+10%／4件：受到傷害時，自身減傷提高35%，持續6秒，冷卻24秒",
    313: "2件：裝備生命+10%／4件：釋出必殺技後，全體隊友攻擊力提升20%，持續6秒，冷卻18秒",
    314: "2件：裝備生命+10%／4件：釋放治療技能將為受治療目標增加一個15%自身最大生命值護盾，持續6秒，冷卻18秒",
    315: "2件：裝備攻擊+10%／4件：釋放技能，將提高自身15%攻擊，持續6秒，同時重傷受到被擊中的目標，使其受到的治療降低44%，持續8秒，冷卻18秒",
    319: "2件：裝備生命+10%／4件：獲得造成傷害10%的護盾，坦克英雄裝備時效果提升600%，護盾可吸收受到傷害的50%，持續8秒",
    301: "2件：裝備生命+5%／4件：受到傷害時，自身減傷提高25%，持續6秒，冷卻24秒",
    302: "2件：裝備生命+5%／4件：釋出必殺技後，隊友攻擊力提高10%，持續6秒",
    303: "2件：裝備攻擊+5%／4件：釋放任意技能後，自身爆擊提升15%，持續6秒，冷卻18秒",
}

# 鍛造介面簡稱（官方 UI_Forge_404：血怒、泰坦、騎士）。
FORGE_SHORT = {1101: "泰坦", 1102: "血怒", 1103: "騎士"}

# 第 13 章推算分組順序（成員與 title_attr 核對；治療組順序依手冊，牧師列最後）。
DERIVED_GROUPS = (
    {
        "anchor": "derived-heal",
        "title": "英雄治療率 500 → 生命之力（生命套裝）",
        "title_attr": (33, 500),
        "ids": (10007, 10008, 10027, 10034, 10045, 10052, 10003),
        "body": (
            "4 件效果綁「釋放治療技能」加護盾，和這類稱號最直接。"
            "後期若走打造套，較近的是騎士榮光（技能增傷，尚未開放），而不是血之怒／泰坦之威。"
            "目前可用生命之力。"
        ),
        "after": "藥劑師歸自然，榮譽鏈無法分營。",
    },
    {
        "anchor": "derived-mitigation",
        "title": "減傷 500 → 凱旋之歌或雷霆庇護",
        "title_attr": (19, 500),
        "ids": (10004, 10010, 10017, 10018, 10019, 10020, 10031, 10032, 10035, 10039, 10042, 10043, 10048, 10049, 15032, 15039),
        "body": (
            "凱旋之歌 4 件寫明「坦克英雄裝備時效果提升 600%」；雷霆庇護是大地系的受傷減傷（25%→35%）。"
            "品質 5 過渡用大地的守護者。後期打造套對得上血之怒（裝備生命＋減傷，尚未開放）。"
            "目前可用凱旋之歌或雷霆庇護。"
        ),
        "after": "老闆娘要不要標未開放，仍等玩家決定，此處只按稱號歸類，不標未開放。",
    },
    {
        "anchor": "derived-damage",
        "title": "增傷 300 → 太陽之怒或扭曲印記",
        "title_attr": (18, 300),
        "ids": (10001, 10002, 10006, 10011, 10012, 10013, 10014, 10016, 10021, 10022, 10023, 10024, 10025, 10026, 10033, 10037, 10040, 10041, 10044, 10046, 10047, 15033),
        "body": (
            "太陽之怒是賢者系的技能後爆擊加強；扭曲印記是攻擊＋降低目標受治療。"
            "品質 5 過渡用賢者的敏銳。後期打造套對得上泰坦之威（裝備攻擊＋增傷，尚未開放）。"
            "目前可用太陽之怒或扭曲印記。"
        ),
        "after": "",
    },
    {
        "anchor": "derived-hp",
        "title": "英雄生命 500 → 聖光祝福／冠軍的英姿，後期可看騎士榮光",
        "title_attr": (104, 500),
        "ids": (10005, 10009, 10015, 10028, 10029, 10030, 10036, 10038, 10050, 10051, 10053, 10054),
        "body": (
            "這 12 人不是治療稱號也不是減傷稱號。較接近輔助的是冠軍系：必殺後給隊友加攻擊（聖光祝福為加強版）。"
            "後期騎士榮光（尚未開放）同時加攻擊、生命、技能增傷，適合這組混合定位。"
            "目前可用聖光祝福或冠軍的英姿。若個別技能有治療，生命之力也可以用，但表上沒有現成欄位可自動切開。"
        ),
        "after": "",
    },
)

SHOP_ROWS_SPEC = (
    ("生命套裝", 314, "生命套裝禮包與生命套裝武器／衣服／鞋子／頭盔自選箱"),
    ("扭曲套裝", 315, "扭曲套裝武器／衣服／鞋子／頭盔自選箱"),
    ("凱旋套裝", 319, "凱旋套裝武器／衣服／鞋子／頭盔自選箱"),
    ("賢者套裝", 303, "賢者套裝自選箱（無陣營／自然／聯盟／部族）；亦有品質 4 的騎士長劍一線"),
    ("大地套裝", 301, "大地套裝自選箱（無陣營／自然／聯盟／部族）；亦有品質 4 的守護戰錘一線"),
    ("冠軍套裝", 302, "冠軍套裝自選箱（無陣營／自然／聯盟／部族）"),
    ("血怒／血之怒", 1102, "官方鍛造介面稱「血怒」。標為未開放，無商店自選箱。"),
    ("泰坦", 1101, "官方鍛造介面稱「泰坦」。標為未開放，無商店自選箱。"),
    ("騎士（新套裝）", 1103, "官方鍛造介面稱「騎士」，勿與舊套「騎士長劍」（屬賢者的敏銳）或「騎士級」散件混淆。標為未開放，無商店自選箱。"),
)


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def _hero_href_public(hero_id: int) -> str:
    if hero_href(hero_id):
        return f"heroes/{hero_id}.html"
    return ""


def _int(value) -> int:
    return int(float(str(value).strip()))


def attr_label(attr_id: int, *, include_id: bool = True) -> str:
    name = A.attr_name(attr_id)
    return f"{name}（{attr_id}）" if include_id else name


def format_attrs(pairs, *, include_id: bool = True) -> str:
    if not pairs:
        return "—"
    bits = []
    for item in pairs:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            bits.append(f"{attr_label(_int(item[0]), include_id=include_id)} {_int(item[1])}")
        elif isinstance(item, str) and "|" in item:
            a, v = item.split("|", 1)
            bits.append(f"{attr_label(_int(a), include_id=include_id)} {_int(v)}")
    return "、".join(bits) if bits else "—"


def format_attr_map(mapping: dict, *, include_id: bool = True) -> str:
    if not mapping:
        return "—"
    bits = [f"{attr_label(_int(a), include_id=include_id)} {_int(v)}" for a, v in mapping.items()]
    return "、".join(bits)


def format_thresholds(triples, *, include_id: bool = True) -> str:
    if not triples:
        return "—"
    bits = []
    for item in triples:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            bits.append(f"門檻 {_int(item[0])}：{attr_label(_int(item[1]), include_id=include_id)} {_int(item[2])}")
    return "；".join(bits) if bits else "—"


def format_fightforce(values) -> str:
    if values in (None, "", [], -1):
        return "—"
    if not isinstance(values, (list, tuple)):
        return str(_int(values))
    return ", ".join(str(_int(v)) for v in values)


def parse_pipe_pairs(raw) -> list[tuple[int, int]]:
    if raw in (None, "", [], {}, -1):
        return []
    if isinstance(raw, dict):
        return [(_int(k), _int(v)) for k, v in raw.items()]
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




def official_text(key: str, default: str = "") -> str:
    return clean(t(key, default))


def goods_name(gid: int) -> str:
    return official_text(f"goods_name_{gid}") or str(gid)


def piece_name(row: dict) -> str:
    return official_text(row.get("name") or f"equipment_name_{row['id']}") or str(row["id"])


@dataclass
class SlotInfo:
    slot_id: int
    name_key: str
    name: str
    unlock_level: int
    show_level: int


@dataclass
class EffectRow:
    num: int | str
    desc: str
    attrs: list[tuple[int, int]]
    power: int | None
    component: int | None
    raw_note: str


@dataclass
class BondRow:
    quality: int
    attrs: list[tuple[int, int]]
    power_suit_refine: int | None
    text: str


@dataclass
class RefineOption:
    slot_id: int
    slot_name: str
    entries: list[tuple[int, int, str]]  # col_id, attr_id, label


@dataclass
class PieceRow:
    piece_id: int
    name: str
    slot_id: int
    slot_name: str
    quality: int
    version: int
    suit_id: int
    attrs: list[tuple[int, int]]
    attrs_text: str
    star_text: str
    break_text: str
    star_pairs: list
    break_pairs: list
    fightforce: str
    upgrade_text: str
    get_ids: list[int]
    max_level: int | None
    break_on: int | None
    produce_text: str
    race_produce_text: str


@dataclass
class SuitRow:
    suit_id: int
    name: str
    version: int
    version_label: str
    unreleased: bool
    unreleased_note: str
    qualities: list[int]
    quality_label: str
    overview: str
    forge_short: str
    leftover_ids: list[int]
    effects: list[EffectRow]
    pieces: list[PieceRow]
    bonds: list[BondRow]
    refine: list[RefineOption]
    produce_same: bool
    produce_text: str
    race_produce_text: str


@dataclass
class UnfilledSuit:
    suit_id: int
    name: str
    effects: list[EffectRow]


@dataclass
class DerivedGroup:
    anchor: str
    title: str
    title_attr: tuple[int, int]
    heroes: list[tuple[int, str, bool, bool]]  # id, label, unreleased, unnamed
    body: str
    after: str


@dataclass
class TablesData:
    slots: list[SlotInfo]
    suits: list[SuitRow]
    unfilled: list[UnfilledSuit]
    loose: list[PieceRow]
    shop_rows: list[list[str]]
    get_id_note_parts: list[str]
    upgrades: list[tuple[int, str, int, str, int, str]]  # from_id, from_name, to_id, to_name, goods_id, goods_name
    synthesize: list[dict]
    derived: list[DerivedGroup]
    counts: dict
    official: dict
    verifications: dict
    terms: list[str] = field(default_factory=list)


def _slot_map() -> dict[int, SlotInfo]:
    rows = load_table("equipment_slot")
    out = {}
    for r in rows:
        name_key = r["name"]
        out[int(r["id"])] = SlotInfo(
            slot_id=int(r["id"]),
            name_key=name_key,
            name=official_text(name_key) or name_key,
            unlock_level=int(r["unlock_level"]),
            show_level=int(r["show_level"]),
        )
    return out


def _suit_name(suit_id: int, suit_rows: list[dict]) -> str:
    if suit_id in NEW_SUIT_IDS:
        return official_text(f"equipment_suit_{suit_id}")
    rows = [r for r in suit_rows if r["suit_id"] == suit_id]
    if rows:
        return official_text(rows[0]["name"])
    return official_text(f"equipment_suit_{suit_id}")


def _effect_from_suit_row(r: dict, num_label: int | str | None = None, *, include_component: bool = True) -> EffectRow:
    desc = official_text(r["desc"])
    attrs = parse_pipe_pairs(r.get("attrs") or r.get("attr_new"))
    power = r.get("fihtforce")
    power_i = None if power in (None, -1, "") else _int(power)
    comp = r.get("component")
    comp_i = None if comp in (None, -1, "") else _int(comp)
    bits = []
    if attrs:
        bits.append(f"原始點數：{format_attrs(attrs)}")
    if power_i is not None:
        bits.append(f"戰力欄 {power_i}")
    if include_component:
        if comp_i is not None:
            bits.append(f"零件編號 {comp_i}")
        elif comp == -1:
            bits.append("零件編號 -1")
    return EffectRow(
        num=num_label if num_label is not None else r.get("num"),
        desc=desc,
        attrs=attrs,
        power=power_i,
        component=comp_i if comp_i is not None else (comp if comp == -1 else None),
        raw_note="；".join(bits),
    )


def _upgrade_index(up_rows: list[dict], pieces_by_id: dict[int, dict], slots: dict[int, SlotInfo]):
    by_from = {}
    by_to = {}
    for r in up_rows:
        src, dst = int(r["id"]), int(r["after_id"])
        cost = r.get("breakCost") or r.get("break_cost")
        gid = int(cost[1]) if isinstance(cost, (list, tuple)) and len(cost) >= 3 else None
        qty = int(cost[2]) if gid is not None else None
        gname = goods_name(gid) if gid is not None else ""
        src_name = piece_name(pieces_by_id[src]) if src in pieces_by_id else str(src)
        dst_name = piece_name(pieces_by_id[dst]) if dst in pieces_by_id else str(dst)
        by_from[src] = (dst, dst_name, gid, gname, qty)
        by_to[dst] = (src, src_name, gid, gname, qty)
    return by_from, by_to


def _piece_row(
    r: dict,
    slots: dict[int, SlotInfo],
    by_from: dict,
    by_to: dict,
) -> PieceRow:
    pid = int(r["id"])
    slot_id = int(r["type"])
    slot = slots[slot_id]
    attrs = r.get("attrs") or []
    attr_pairs = [(_int(a), _int(v)) for a, v in attrs]
    star = r.get("starAttrs") or []
    brk = r.get("breakBonusAttr") or []
    get_id = r.get("get_id") or []
    if get_id in (None, -1, ""):
        get_ids = []
    elif isinstance(get_id, (list, tuple)):
        get_ids = [int(x) for x in get_id]
    else:
        get_ids = [int(get_id)]

    upgrade_text = "—"
    if pid in by_to:
        src, src_name, gid, gname, qty = by_to[pid]
        upgrade_text = f"由 {src_name}（{src}）進階而來"
    elif pid in by_from:
        dst, dst_name, gid, gname, qty = by_from[pid]
        extra = f"，{gname} ×{qty}" if gname else ""
        upgrade_text = f"→ {dst_name}（{dst}）{extra}"

    produce = r.get("produceGoods") or []
    produce_text = "—"
    if produce:
        bits = []
        for item in produce:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                bits.append(f"{goods_name(int(item[1]))} ×{int(item[2])}")
        time_s = r.get("produce_time")
        if bits:
            produce_text = "、".join(bits)
            if time_s not in (None, "", -1):
                sec = _int(time_s)
                hours = sec // 3600
                produce_text += f"；時間 {sec} 秒（{hours} 小時）"

    race = r.get("race_produce_goods") or r.get("RaceCostDic")
    race_text = "—"
    if r.get("RaceCostDic"):
        # 三營皆為同一貨品時照章節寫法。
        dic = r["RaceCostDic"]
        items = []
        for camp, arr in dic.items():
            if isinstance(arr, (list, tuple)) and len(arr) >= 3:
                items.append((str(camp), int(arr[1]), int(arr[2])))
        if items and len({(g, q) for _, g, q in items}) == 1:
            gid, qty = items[0][1], items[0][2]
            race_text = f"陣營打造另耗{goods_name(gid)}（三營皆為貨品 {gid} ×{qty}）"
        elif items:
            race_text = "、".join(f"營{c}：{goods_name(g)} ×{q}" for c, g, q in items)

    return PieceRow(
        piece_id=pid,
        name=piece_name(r),
        slot_id=slot_id,
        slot_name=slot.name,
        quality=int(r["quality"]),
        version=int(r["version"]),
        suit_id=int(r.get("suit_id") or -1),
        attrs=attr_pairs,
        attrs_text=format_attrs(attr_pairs),
        star_text=format_thresholds(star),
        break_text=format_thresholds(brk),
        star_pairs=star,
        break_pairs=brk,
        fightforce=format_fightforce(r.get("fightforce") or r.get("basePowers")),
        upgrade_text=upgrade_text,
        get_ids=get_ids,
        max_level=None if r.get("max_level") in (None, -1) else int(r["max_level"]),
        break_on=None if r.get("break_on") in (None, "") else int(r["break_on"]),
        produce_text=produce_text,
        race_produce_text=race_text,
    )


def _piece_sort_key(p: PieceRow):
    return (p.quality, p.slot_id, p.piece_id)


def _loose_sort_key(p: PieceRow):
    # 新版侍從級至元帥級在前，舊式散件在後；各按 id。
    group = 0 if p.version == 1 else 1
    return (group, p.piece_id)


def _leftover_ids(suit_id: int, official_name: str, suit_rows: list[dict]) -> list[int]:
    found = []
    for r in suit_rows:
        sid = int(r["suit_id"])
        if sid == suit_id:
            continue
        if official_text(r["name"]) == official_name and sid not in found:
            found.append(sid)
    return sorted(found)


def _new_effect_rows(suit_id: int, suit_rows: list[dict], groups: list[dict]) -> list[EffectRow]:
    g_rows = sorted(
        [g for g in groups if int(g["group_id"]) == suit_id],
        key=lambda g: int(g.get("Priority") or 0),
    )
    out = []
    for g in g_rows:
        matches = [r for r in suit_rows if int(r["suit_id"]) == int(g["id"])]
        for r in matches:
            out.append(_effect_from_suit_row(r, num_label=r.get("num"), include_component=False))
    return out


def _old_effect_rows(suit_id: int, suit_rows: list[dict]) -> list[EffectRow]:
    rows = sorted(
        [r for r in suit_rows if int(r["suit_id"]) == suit_id],
        key=lambda r: int(r["num"]),
    )
    return [_effect_from_suit_row(r) for r in rows]


def _overview_text(effects: list[EffectRow]) -> str:
    return "／".join(e.desc for e in effects)


def _bond_rows(suit_id: int, bond_rows: list[dict]) -> list[BondRow]:
    out = []
    for r in sorted((b for b in bond_rows if int(b["suit"]) == suit_id), key=lambda x: int(x["quality"])):
        attrs = parse_pipe_pairs(r.get("suit_attribute"))
        raw_p = r.get("power_suit_refine")
        power = None if raw_p in (None, "", -1) else _int(raw_p)
        text = format_attrs(attrs)
        if power is not None:
            text = f"{text}（power_suit_refine={power}）"
        out.append(BondRow(quality=int(r["quality"]), attrs=attrs, power_suit_refine=power, text=text))
    return out


def _refine_rows(suit_id: int, refine_rows: list[dict], attr_rows: dict[int, dict], slots: dict[int, SlotInfo]) -> list[RefineOption]:
    out = []
    for r in sorted((x for x in refine_rows if int(x["suit"]) == suit_id), key=lambda x: int(x["type"])):
        slot_id = int(r["type"])
        entries = []
        ids = r.get("attrIndexIdArr") or []
        if not ids and r.get("attribute"):
            ids = [int(x) for x in str(r["attribute"]).split("|") if x]
        for col in ids:
            col_i = int(col)
            ar = attr_rows.get(col_i) or {}
            aid = int(ar["attribute"]) if ar else col_i
            entries.append((col_i, aid, f"{col_i}＝{attr_label(aid)}"))
        out.append(RefineOption(slot_id=slot_id, slot_name=slots[slot_id].name, entries=entries))
    return out




def _hero_label(hero_id: int) -> tuple[str, bool, bool]:
    """Return (display label, is_unreleased, is_unnamed). 老闆娘不標未開放。"""
    row = catalog()["hero_by_id"].get(hero_id)
    official = official_text(f"hero_name_{hero_id}")
    unnamed = not official
    unreleased = hero_id in UNRELEASED_HERO_IDS
    if unnamed:
        label = str(hero_id)
    else:
        # roster_display_name 只給公開名冊的未開放標記；牧羊人會加上（未開放）。
        label = roster_display_name(hero_id, official)
        if unreleased and "未開放" not in label:
            label = f"{official}（未開放）"
    return label, unreleased, unnamed


def _shop_rows(suits_by_id: dict[int, SuitRow]) -> list[list[str]]:
    rows = []
    member_notes = {
        314: "生命法杖、生命斗篷、生命木靴、生命頭環（681–684）。同套另有森林法杖一線（641–644）。商店箱文案：可在任意陣營的生命法杖等中選擇一項。",
        315: "扭曲鐮刀、扭曲刃甲、扭曲刃靴、扭曲面罩（671–674）。同套另有黑暗鐮刀一線（651–654）。",
        319: "凱旋斬斧、凱旋板甲、凱旋護靴、凱旋頭甲（691–694）。",
        303: "賢者長杖、賢者上衣、賢者靴子、賢者兜帽；亦有品質 4 的騎士長劍一線（411–414）。商店另有無陣營／聯盟／部族／自然自選箱。",
        301: "大地之斧、大地重甲、大地重靴、大地重盔；亦有品質 4 的守護戰錘一線（431–434）。",
        302: "冠軍之劍、冠軍盔甲、冠軍靴子、冠軍頭盔（521–524）。",
        1102: "官方鍛造介面稱「血怒」。成員：血獄狂斧、怒血戰甲、血影疾靴、怒血魔盔。標為未開放，無商店自選箱。",
        1101: "官方鍛造介面稱「泰坦」。成員：泰坦巨錘、泰坦神甲、泰坦重靴、泰坦聖盔。標為未開放，無商店自選箱。",
        1103: "官方鍛造介面稱「騎士」，勿與舊套「騎士長劍」（屬賢者的敏銳）或「騎士級」散件混淆。成員：騎士聖劍、騎士耀甲、騎士靈靴、騎士輝盔。標為未開放，無商店自選箱。",
    }
    formal_extra = {
        1101: "（未開放）",
        1102: "（未開放）",
        1103: "（未開放）",
    }
    for shop, sid, _hint in SHOP_ROWS_SPEC:
        suit = suits_by_id[sid]
        formal = f"{suit.name}（{sid}{('，未開放' if sid in UNRELEASED_SUIT_IDS else '')}）"
        # 名稱欄的「未開放」只加在正式名上；來源見資料說明。
        rows.append([shop, formal, member_notes[sid]])
    return rows


def _terms_for(data_pieces: list[PieceRow], suits: list[SuitRow], slots: list[SlotInfo]) -> list[str]:
    terms = {
        "裝備攻擊",
        "裝備生命",
        "技能增傷",
        "技能減傷",
        "普攻減傷",
        "暴擊傷害",
        "對怪物傷害",
        "受怪物減傷",
        "太陽金",
        "泰坦印記",
        "武器進階石",
        "衣服進階石",
        "鞋子進階石",
        "頭盔進階石",
        "裝備精華",
        "傳說打造",
        "傳奇打造",
        "鐵匠鋪",
        "鐵匠舖",
        "無陣營",
        "聯盟",
        "自然",
        "部族",
        "生命套裝",
        "扭曲套裝",
        "凱旋套裝",
        "賢者套裝",
        "大地套裝",
        "冠軍套裝",
        "騎士長劍",
        "騎士級",
        "侍從級",
        "士兵級",
        "元帥級",
        "專武",
        "未開放",
        "玩家確認",
        "泰坦之威",
        "血之怒",
        "騎士榮光",
        "太陽之怒",
        "雷霆庇護",
        "聖光祝福",
        "生命之力",
        "扭曲印記",
        "凱旋之歌",
        "大地的守護者",
        "冠軍的英姿",
        "賢者的敏銳",
        "血怒",
        "橘色",
        "橙色",
        "老闆娘",
        "牧羊人",
        "藥劑師",
        "英雄治療率",
        "英雄生命",
        # 完整官方箱名／箱內用詞，避免被較短詞切開而在 .term 之間露出空白。
        "生命套裝武器自選箱",
        "生命套裝衣服自選箱",
        "生命套裝鞋子自選箱",
        "生命套裝頭盔自選箱",
        "生命套裝禮包",
        "扭曲套裝武器自選箱",
        "扭曲套裝衣服自選箱",
        "扭曲套裝鞋子自選箱",
        "扭曲套裝頭盔自選箱",
        "凱旋套裝武器自選箱",
        "凱旋套裝衣服自選箱",
        "凱旋套裝鞋子自選箱",
        "凱旋套裝頭盔自選箱",
        "賢者套裝自選箱（無陣營）",
        "賢者套裝自選箱（自然）",
        "賢者套裝自選箱（聯盟）",
        "賢者套裝自選箱（部族）",
        "大地套裝自選箱（無陣營）",
        "大地套裝自選箱（自然）",
        "大地套裝自選箱（聯盟）",
        "大地套裝自選箱（部族）",
        "冠軍套裝自選箱（無陣營）",
        "冠軍套裝自選箱（自然）",
        "冠軍套裝自選箱（聯盟）",
        "冠軍套裝自選箱（部族）",
        "橘色賢者套裝",
        "橙色大地套裝",
        "橙色冠軍套裝",
        "武器自選箱（無陣營）",
        "衣服自選箱（無陣營）",
        "鞋子自選箱（無陣營）",
        "頭盔自選箱（無陣營）",
    }
    for s in slots:
        terms.add(s.name)
    for suit in suits:
        terms.add(suit.name)
        if suit.forge_short:
            terms.add(suit.forge_short)
        for p in suit.pieces:
            terms.add(p.name)
    for p in data_pieces:
        terms.add(p.name)
    # 英雄正式名（不含空名與純編號）。
    for h in catalog()["hero_detail"]:
        name = official_text(f"hero_name_{h['id']}")
        if name:
            terms.add(name)
    # 不含孤立的「部落」（官方散件名是「部落護甲」「部落戰靴」，較長詞優先）。
    return sorted({t for t in terms if t}, key=len, reverse=True)


def load_tables_data() -> TablesData:
    equipment = load_table("equipment_new")
    old_equipment = load_table("equipment")
    suit_rows = load_table("equipment_suit")
    groups = load_table("equipment_suit_group")
    bonds = load_table("equipment_suit_bond")
    refine = load_table("equipment_suit_refine")
    attr_list = load_table("equipment_suit_attribute")
    upgrades = load_table("equipment_upgrade")
    synthesize = load_table("equipment_synthesize")
    slots = _slot_map()
    attr_by_id = {int(r["id"]): r for r in attr_list}
    pieces_by_id = {int(r["id"]): r for r in equipment}
    by_from, by_to = _upgrade_index(upgrades, pieces_by_id, slots)

    if len(equipment) != 111:
        raise ValueError(f"equipment_new should have 111 rows, got {len(equipment)}")
    if len(old_equipment) != 2561:
        raise ValueError(f"equipment.json should have 2561 rows, got {len(old_equipment)}")
    if list(slots) != [1, 2, 3, 4]:
        raise ValueError(f"unexpected slots: {list(slots)}")

    # 部位名稱鍵對調：id 3 → equipment_slot_name_4（鞋子）；id 4 → equipment_slot_name_3（頭盔）。
    if slots[3].name_key != "equipment_slot_name_4" or slots[3].name != "鞋子":
        raise ValueError(f"slot 3 name-key swap failed: {slots[3]}")
    if slots[4].name_key != "equipment_slot_name_3" or slots[4].name != "頭盔":
        raise ValueError(f"slot 4 name-key swap failed: {slots[4]}")
    if slots[1].name != "武器" or slots[2].name != "衣服":
        raise ValueError(f"slot 1/2 names unexpected: {slots[1].name}, {slots[2].name}")
    for s in slots.values():
        if s.unlock_level != 5 or s.show_level != 5:
            raise ValueError(f"slot {s.slot_id} unlock/show not 5")

    used_suits = sorted({int(r["suit_id"]) for r in equipment if int(r["suit_id"]) != -1})
    expected_used = sorted(LIVE_SUIT_ORDER)
    if used_suits != expected_used:
        raise ValueError(f"live suit ids {used_suits} != {expected_used}")

    suit_objs: list[SuitRow] = []
    for sid in LIVE_SUIT_ORDER:
        name = _suit_name(sid, suit_rows)
        version = 1 if sid in NEW_SUIT_IDS else -1
        pieces = [
            _piece_row(r, slots, by_from, by_to)
            for r in equipment
            if int(r["suit_id"]) == sid
        ]
        pieces.sort(key=_piece_sort_key)
        if sid in NEW_SUIT_IDS:
            effects = _new_effect_rows(sid, suit_rows, groups)
            # 新套裝 effect 列不附 component（表上為 -1），戰力與原始點數仍附上。
        else:
            effects = _old_effect_rows(sid, suit_rows)
        overview = _overview_text(effects)
        expected = CHAPTER_OVERVIEW[sid]
        if overview != expected:
            raise ValueError(f"suit {sid} overview mismatch:\n  live: {overview}\n  chap: {expected}")
        qualities = sorted({p.quality for p in pieces})
        unreleased = sid in UNRELEASED_SUIT_IDS
        leftover = _leftover_ids(sid, name, suit_rows)
        # 新套效果列的 suit_id 是 11011 等，不算「同名剩餘 id」臆測對象。
        leftover = [i for i in leftover if not (sid in NEW_SUIT_IDS and i // 10 == sid)]
        produce_texts = {p.produce_text for p in pieces}
        race_texts = {p.race_produce_text for p in pieces}
        produce_same = len(produce_texts) == 1
        suit_objs.append(
            SuitRow(
                suit_id=sid,
                name=name,
                version=version,
                version_label="新套裝" if version == 1 else "舊套裝",
                unreleased=unreleased,
                unreleased_note="未開放" if unreleased else "",
                qualities=qualities,
                quality_label="、".join(str(q) for q in qualities),
                overview=overview,
                forge_short=FORGE_SHORT.get(sid, ""),
                leftover_ids=leftover,
                effects=effects,
                pieces=pieces,
                bonds=_bond_rows(sid, bonds),
                refine=_refine_rows(sid, refine, attr_by_id, slots),
                produce_same=produce_same,
                produce_text=next(iter(produce_texts)) if produce_same else "—",
                race_produce_text=next(iter(race_texts)) if len(race_texts) == 1 else "—",
            )
        )

    unfilled = []
    for sid in UNFILLED_SUIT_IDS:
        name = _suit_name(sid, suit_rows)
        if name != "0.0":
            raise ValueError(f"unfilled suit {sid} name is {name!r}, expected '0.0'")
        effects = _old_effect_rows(sid, suit_rows)
        # 4 件說明應只有「4件：」。
        four = [e for e in effects if e.num == 4]
        if not four or four[0].desc != "4件：":
            raise ValueError(f"suit {sid} 4-piece desc unexpected: {[e.desc for e in four]}")
        hung = [r for r in equipment if int(r["suit_id"]) == sid]
        if hung:
            raise ValueError(f"equipment_new has pieces on unfilled suit {sid}")
        unfilled.append(UnfilledSuit(suit_id=sid, name=name, effects=effects))

    loose = [
        _piece_row(r, slots, by_from, by_to)
        for r in equipment
        if int(r["suit_id"]) == -1
    ]
    loose.sort(key=_loose_sort_key)
    if len(loose) != 47:
        raise ValueError(f"loose pieces should be 47, got {len(loose)}")

    suits_by_id = {s.suit_id: s for s in suit_objs}
    shop_rows = _shop_rows(suits_by_id)

    # 品質 6 的 get_id 仍掛橙色／橘色自選箱。
    get_id_groups = defaultdict(list)
    for s in suit_objs:
        if 6 in s.qualities:
            for p in s.pieces:
                get_id_groups[(s.suit_id, p.name, tuple(p.get_ids))].append(p.piece_id)

    upgrade_list = []
    for src, (dst, dst_name, gid, gname, qty) in sorted(by_from.items()):
        src_name = piece_name(pieces_by_id[src])
        upgrade_list.append((src, src_name, dst, dst_name, gid or 0, gname))

    syn_out = []
    for r in synthesize:
        syn_out.append(
            {
                "num": int(r["num"]),
                "weapons": list(r["weapons"]),
                "armors": list(r["armors"]),
                "shoes": list(r["shoes"]),
                "helmets": list(r["helmets"]),
                "label": {
                    4: "士兵級（1301–1304）",
                    15: "騎士級（1401–1404）",
                    20: "泰坦之威／血之怒／騎士榮光對應部位（三選一）",
                }.get(int(r["num"]), ""),
            }
        )

    derived = []
    by_title = defaultdict(list)
    for h in catalog()["hero_detail"]:
        ta = h.get("titleAttr") or []
        if len(ta) == 1:
            key = (_int(ta[0][0]), _int(ta[0][1]))
            by_title[key].append(int(h["id"]))
    for spec in DERIVED_GROUPS:
        live_ids = set(by_title.get(spec["title_attr"], []))
        if live_ids != set(spec["ids"]):
            raise ValueError(f"derived group {spec['title']} mismatch: live={sorted(live_ids)} chap={list(spec['ids'])}")
        heroes = []
        for hid in spec["ids"]:
            label, unrel, unnamed = _hero_label(hid)
            if hid == 10032 and unrel:
                raise ValueError("老闆娘 must not be marked 未開放")
            if hid == 10029 and not unrel:
                raise ValueError("牧羊人 must be marked 未開放")
            heroes.append((hid, label, unrel, unnamed))
        derived.append(
            DerivedGroup(
                anchor=spec["anchor"],
                title=spec["title"],
                title_attr=spec["title_attr"],
                heroes=heroes,
                body=spec["body"],
                after=spec["after"],
            )
        )

    official = {
        "forge_404": official_text("UI_Forge_404"),
        "forge_409": official_text("UI_Forge_409"),
        "forge_014": official_text("UI_Forge_014"),
        "forge_open": official_text("equip_4.0_open_forge"),
        "titan_desc": official_text("goods_desc_404100006"),
        "sun_gold_desc": official_text("goods_desc_404100005"),
        "forge_210": official_text("UI_Forge_210"),
        "forge_sys_08": official_text("UI_Forge_sys_08"),
        "life_box_weapon": official_text("goods_name_401110001"),
        "life_box_weapon_desc": official_text("goods_desc_401110001"),
        "life_pack": official_text("exchange_desc_shengming"),
        "box_xianzhe": official_text("goods_name_11145001"),
        "box_xianzhe_desc": official_text("goods_desc_11145001"),
        "box_dadi": official_text("goods_name_11145005"),
        "box_dadi_desc": official_text("goods_desc_11145005"),
        "box_guanjun": official_text("goods_name_11145009"),
        "box_guanjun_desc": official_text("goods_desc_11145009"),
        "slot_box_weapon": official_text("goods_name_12120101"),
        "equip_orange": official_text("equip_orange"),
        "equip_color_5": official_text("equip_color_5"),
        "blacksmith": official_text("citybuilding_name_114"),
        "castle": official_text("citybuilding_name_117"),
    }

    # 鐵匠鋪 15 級前置城堡 16 級（citybuilding_lvup_new；舊表鐵匠鋪只到 1 級）。
    bnew = load_table("citybuilding_lvup_new")
    bold = load_table("citybuilding_lvup")
    row_15 = next(r for r in bnew if int(r["id"]) == 114015)
    pre_15 = row_15.get("pre_building_level")
    if pre_15 != ["117|16"] and pre_15 != "117|16":
        raise ValueError(f"blacksmith 15 pre-building unexpected: {pre_15}")
    old_114_lvs = [int(r["lv"]) for r in bold if int(r["id"]) // 1000 == 114 or str(r["id"]).startswith("114")]
    # ids are 114000, 114001
    old_114_lvs = [int(r["lv"]) for r in bold if int(r.get("index") or 0) == 114 or (isinstance(r.get("id"), int) and 114000 <= int(r["id"]) < 115000)]
    if old_114_lvs and max(old_114_lvs) != 1:
        # 若舊表其實不只 1 級，記下但不默默改寫章節。
        old_max = max(old_114_lvs)
    else:
        old_max = 1

    counts = {
        "equipment_new": len(equipment),
        "equipment_old": len(old_equipment),
        "live_suits": len(suit_objs),
        "loose": len(loose),
        "make_level": len(load_table("equipment_make_level")),
        "build": len(load_table("equipment_build")),
        "upgrade": len(upgrades),
        "synthesize": len(synthesize),
        "material": len(load_table("equipment_material")),
        "entry": len(load_table("equipment_entry")),
        "master": len(load_table("equipment_master")),
        "refine": len(refine),
        "bond": len(bonds),
        "star_up": len(load_table("equipment_star_up")),
        "break": len(load_table("equipment_break")),
        "hero_detail": len(catalog()["hero_detail"]),
        "old_blacksmith_max_lv": old_max,
    }

    verifications = {
        "equipment_new_rows": counts["equipment_new"],
        "live_suits": counts["live_suits"],
        "used_suit_ids": used_suits,
        "unfilled_ids": list(UNFILLED_SUIT_IDS),
        "unfilled_names": [u.name for u in unfilled],
        "slot_swap": {
            3: (slots[3].name_key, slots[3].name),
            4: (slots[4].name_key, slots[4].name),
        },
        "overview_match": True,
        "unreleased_suits": [s.name for s in suit_objs if s.unreleased],
        "unreleased_is_player_confirm": True,
        "quality6_not_unreleased": all(not s.unreleased and 6 in s.qualities for s in suit_objs if s.suit_id in (311, 312, 313, 314, 315, 319)),
        "loose_new_not_unreleased": True,
        "laobanliang_not_unreleased": all(not unrel for hid, _, unrel, _ in derived[1].heroes if hid == 10032),
        "shepherd_unreleased": any(unrel for hid, _, unrel, _ in derived[3].heroes if hid == 10029),
        "data_cutoff": EQUIP_DATA_CUTOFF,
        "data_pack": EQUIP_DATA_PACK,
        "old_blacksmith_max_lv": old_max,
    }

    # 侍從級至元帥級 16 件不得標未開放（本頁只在新三套名稱上標）。
    new_loose = [p for p in loose if p.version == 1]
    if len(new_loose) != 16:
        raise ValueError(f"expected 16 version=1 loose pieces, got {len(new_loose)}")

    terms = _terms_for(loose, suit_objs, list(slots.values()))
    return TablesData(
        slots=list(slots.values()),
        suits=suit_objs,
        unfilled=unfilled,
        loose=loose,
        shop_rows=shop_rows,
        get_id_note_parts=[],
        upgrades=upgrade_list,
        synthesize=syn_out,
        derived=derived,
        counts=counts,
        official=official,
        verifications=verifications,
        terms=terms,
    )




def _suit_heading(suit: SuitRow, *, html: bool = False) -> str:
    if html:
        return f"{suit.name}（未開放）" if suit.unreleased else suit.name
    if suit.unreleased:
        return f"{suit.name}（{suit.suit_id}，未開放）"
    return f"{suit.name}（{suit.suit_id}）"


def _effect_note_html(ev: EffectRow) -> str:
    bits = []
    if ev.attrs:
        bits.append(f"原始點數：{format_attrs(ev.attrs, include_id=False)}")
    if ev.power is not None:
        bits.append(f"戰力欄 {ev.power}")
    if ev.component is not None:
        bits.append(f"零件編號 {ev.component}")
    return "；".join(bits)


def _effect_lines_html(effects: list[EffectRow], terms: list[str]) -> str:
    items = []
    for ev in effects:
        note_body = _effect_note_html(ev)
        note = f"（{e(note_body)}）" if note_body else ""
        items.append(f"<li>{H(ev.desc, terms)}{note}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _bond_table(suit: SuitRow, terms: list[str], *, show_power: bool) -> str:
    if not suit.bonds:
        return "<p>本套在套裝羈絆表沒有列。</p>"
    cols = ["品質", "羈絆屬性（原始點數）"]
    if show_power:
        cols.append("精煉戰力")
    rows = []
    for b in suit.bonds:
        row = [e(str(b.quality)), H(format_attrs(b.attrs, include_id=False), terms)]
        if show_power:
            row.append(e(str(b.power_suit_refine) if b.power_suit_refine is not None else "—"))
        rows.append(row)
    return table(cols, rows, mobile="sticky", card_title="品質")


def _refine_table(suit: SuitRow, terms: list[str]) -> str:
    if not suit.refine:
        return "<p>本套在套裝精煉表沒有列。</p>"
    rows = []
    for opt in suit.refine:
        rows.append([H(opt.slot_name, terms), H("、".join(f"{col}＝{attr_label(aid, include_id=False)}" for col, aid, _ in opt.entries), terms)])
    return table(
        ["部位", "可選屬性（列編號＝屬性名；數字是精煉屬性表的列編號，不是屬性編號）"],
        rows,
        mobile="cards",
        card_title="部位",
    )


def _new_piece_table(suit: SuitRow, terms: list[str]) -> str:
    rows = []
    ids = []
    for p in suit.pieces:
        ids.append(f"piece-{p.piece_id}")
        rows.append([
            H(p.name, terms),
            H(p.slot_name, terms),
            H(format_attrs(p.attrs, include_id=False), terms),
            H(format_thresholds(p.star_pairs, include_id=False), terms),
            H(format_thresholds(p.break_pairs, include_id=False), terms),
            e(p.fightforce),
        ])
    return table(
        ["名稱", "部位", "基礎屬性", "升星加成", "突破加成", "戰力欄"],
        rows,
        row_ids=ids,
        mobile="cards",
        card_title="名稱",
    )


def _upgrade_text_visible(text: str) -> str:
    """HTML-only: drop parenthetical part ids; keep official part names."""
    import re as _re_up
    return _re_up.sub(r"（\d+）", "", text)


def _old_piece_table(suit: SuitRow, terms: list[str]) -> str:
    rows = []
    ids = []
    for p in suit.pieces:
        ids.append(f"piece-{p.piece_id}")
        rows.append([
            H(p.name, terms),
            H(p.slot_name, terms),
            e(str(p.quality)),
            H(format_attrs(p.attrs, include_id=False), terms),
            e(p.fightforce),
            H(_upgrade_text_visible(p.upgrade_text), terms),
        ])
    return table(
        ["名稱", "部位", "品質", "基礎屬性", "戰力欄", "進階"],
        rows,
        row_ids=ids,
        mobile="cards",
        card_title="名稱",
    )


def _hero_link_html(hero_id: int, label: str, terms: list[str], unnamed: bool) -> str:
    href = _hero_href_public(hero_id)
    if unnamed:
        marked = e(str(hero_id))
    else:
        marked = H(label, terms)
    if href:
        return f'<a href="{e(href)}">{marked}</a>'
    return marked


def _hero_link_md(hero_id: int, label: str, unnamed: bool) -> str:
    text = str(hero_id) if unnamed else label
    return f"[{text}]({LIVE_HERO.format(id=hero_id)})"


def _derived_hero_html(group: DerivedGroup, terms: list[str]) -> str:
    bits = []
    unnamed = []
    for hid, label, unrel, is_unnamed in group.heroes:
        if is_unnamed:
            unnamed.append(_hero_link_html(hid, label, terms, True))
            continue
        # 牧羊人：在名冊標記上補陣營說明，但不改官方未開放標記。
        if hid == 10029:
            bits.append(f"{_hero_link_html(hid, '牧羊人', terms, False)}（10029，聯盟未開放）")
        else:
            bits.append(f"{_hero_link_html(hid, official_text(f'hero_name_{hid}'), terms, False)}（{hid}）")
    text = "、".join(bits)
    if unnamed:
        text += "，以及無名的 " + "、".join(unnamed)
    return text + "。"


def _derived_hero_md(group: DerivedGroup) -> str:
    bits = []
    unnamed = []
    for hid, label, unrel, is_unnamed in group.heroes:
        if is_unnamed:
            unnamed.append(_hero_link_md(hid, label, True))
            continue
        if hid == 10029:
            bits.append(f"{_hero_link_md(hid, '牧羊人', False)}（10029，聯盟未開放）")
        else:
            name = official_text(f"hero_name_{hid}")
            bits.append(f"{_hero_link_md(hid, name, False)}（{hid}）")
    text = "、".join(bits)
    if unnamed:
        text += "，以及無名的 " + "、".join(unnamed)
    return text + "。"


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    o = data.official
    title = "Top Heroes Wiki｜裝備總表"
    summary = "四件套裝備的套裝、散件、商店名稱對照，以及打造與進階規則。"

    def _shop_formal_html(formal: str) -> str:
        import re as _re_shop
        formal = _re_shop.sub(r"（\d+，未開放）", "（未開放）", formal)
        formal = _re_shop.sub(r"（\d+）", "", formal)
        return formal

    def _shop_note_html(note: str) -> str:
        import re as _re_note
        return _re_note.sub(r"（\d+–\d+）", "", note)

    shop_tbl = table(
        ["商店／介面用詞", "套裝正式名", "對應零件與備註"],
        [[H(a, terms), H(_shop_formal_html(b), terms), H(_shop_note_html(c), terms)] for a, b, c in data.shop_rows],
        mobile="cards",
        card_title="商店／介面用詞",
    )

    overview_rows = []
    overview_ids = []
    for s in data.suits:
        name = s.name + ("（未開放）" if s.unreleased else "")
        overview_ids.append(f"overview-{s.suit_id}")
        overview_rows.append([
            H(name, terms),
            e(s.version_label),
            e(s.quality_label),
            H(s.overview, terms),
        ])
    overview_tbl = table(
        ["套裝", "版本", "品質（零件）", "件數效果摘要"],
        overview_rows,
        row_ids=overview_ids,
        mobile="cards",
        card_title="套裝",
    )

    loose_rows = []
    loose_ids = []
    for p in data.loose:
        loose_ids.append(f"piece-{p.piece_id}")
        loose_rows.append([
            H(p.name, terms),
            H(p.slot_name, terms),
            e(str(p.quality)),
            e(str(p.version)),
            H(format_attrs(p.attrs, include_id=False), terms),
            e(p.fightforce),
        ])
    loose_tbl = table(
        ["名稱", "部位", "品質", "版本", "基礎屬性", "戰力欄"],
        loose_rows,
        row_ids=loose_ids,
        mobile="cards",
        card_title="名稱",
    )

    up_rows = []
    for src, src_name, dst, dst_name, gid, gname in data.upgrades:
        up_rows.append([
            H(src_name, terms),
            H(dst_name, terms),
            H(f"{gname} ×1" if gname else "—", terms),
        ])
    upgrade_tbl = table(
        ["進階前", "進階後", "消耗"],
        up_rows,
        mobile="cards",
        card_title="進階前",
    )

    syn_rows = []
    slot_names = {s.slot_id: s.name for s in data.slots}
    piece_names = {}
    for suit in data.suits:
        for p in suit.pieces:
            if p.name:
                piece_names[p.piece_id] = p.name
    for p in data.loose:
        if p.name:
            piece_names[p.piece_id] = p.name

    def _pool_html(ids):
        parts = []
        for i in ids:
            n = piece_names.get(i)
            parts.append(H(n, terms) if n else str(i))
        return "、".join(parts)

    for rec in data.synthesize:
        dest = "／".join(
            "、".join(str(i) for i in rec[k])
            for k in ("weapons", "armors", "shoes", "helmets")
        )
        label = rec["label"] or dest
        # HTML-only: drop research id ranges already listed as official names in 各部位池
        if "（" in label and any(ch.isdigit() for ch in label):
            import re as _re
            label = _re.sub(r"（\d+–\d+）", "", label)
        syn_rows.append([
            e(str(rec["num"])),
            H(label, terms),
            (
                f"武器 {_pool_html(rec['weapons'])}；"
                f"衣服 {_pool_html(rec['armors'])}；"
                f"鞋子 {_pool_html(rec['shoes'])}；"
                f"頭盔 {_pool_html(rec['helmets'])}"
            ),
        ])
    syn_tbl = table(
        ["消耗件數", "合成結果", "各部位池"],
        syn_rows,
        mobile="cards",
        card_title="合成結果",
    )

    unfilled_rows = []
    for u in data.unfilled:
        two = next(ev for ev in u.effects if ev.num == 2)
        four = next(ev for ev in u.effects if ev.num == 4)
        unfilled_rows.append([
            e(str(u.suit_id)),
            e(u.name),
            H(f"{two.desc}（原始點數 {format_attrs(two.attrs, include_id=False)}）", terms),
            H(four.desc, terms),
        ])
    unfilled_tbl = table(
        ["編號", "名稱文案", "2 件說明", "4 件說明"],
        unfilled_rows,
        mobile="cards",
        card_title="編號",
    )

    # 各套裝正文
    new_sections = []
    old_sections = []
    for s in data.suits:
        leftover = ""
        if s.leftover_ids:
            ids = "、".join(str(i) for i in s.leftover_ids)
            leftover = (
                "<p>同名套裝效果列還出現在其他資料組，文案相同，"
                "較新的裝備定義裡，零件掛的是本套。"
                "本頁不臆測其餘組各自對應哪個陣營或伺服器分段。"
                "編號對照見資料說明。</p>"
            )
        extra = ""
        if s.unreleased:
            extra = (
                f"<p>鍛造介面簡稱：{H(s.forge_short, terms)}。"
                "本套標為未開放；表上沒有裝備「已推出」欄。</p>"
            )
            import re as _re_race
            _race = _re_race.sub(
                r"（三營皆為貨品 \d+ ×(\d+)）",
                r"×\1（三營皆同）",
                s.race_produce_text or "",
            )
            extra += (
                f"<p>打造消耗（四件相同）：{H(s.produce_text, terms)}。"
                f"{H(_race, terms)}。</p>"
            )
        piece_tbl = _new_piece_table(s, terms) if s.version == 1 else _old_piece_table(s, terms)
        quality_note = ""
        if s.version == 1:
            quality_note = "<p>零件品質皆為 5。零件最高等級皆為 40，並可突破。升星與突破加成格式為「門檻、屬性、數值」；表上沒有說明門檻等於第幾星或第幾級，本頁不自行解釋。</p>"
        bond_note = "<p>套裝羈絆（品質 2–6）列原始點數，不換算成百分比。羈絆是 4 件都精煉到指定品質才啟動，屬養成加深，不是另一套裝備。</p>" if s.bonds else ""
        refine_intro = (
            "<p>套裝精煉可選屬性（精煉表依部位列出；"
            "數字是精煉屬性表的列編號，不是屬性編號）。"
            "六檔數值見原表，本頁不全部抄列。</p>"
            if s.refine else ""
        )
        sec = f"""
      <section id="suit-{s.suit_id}">
        <h4>{H(_suit_heading(s, html=True), terms)}</h4>
        <p>{"新套裝" if s.version == 1 else "舊套裝"}</p>
        {extra}
        {leftover}
        <p>套裝效果：</p>
        {_effect_lines_html(s.effects, terms)}
        {quality_note}
        <p>零件：</p>
        {piece_tbl}
        {bond_note}
        {_bond_table(s, terms, show_power=s.version == 1) if s.bonds else ""}
        {refine_intro}
        {_refine_table(s, terms) if s.refine else ""}
      </section>
"""
        (new_sections if s.version == 1 else old_sections).append(sec)

    derived_secs = []
    for g in data.derived:
        after = f"<p>{H(g.after, terms)}</p>" if g.after else ""
        derived_secs.append(f"""
      <section id="{e(g.anchor)}">
        <h3>{H(g.title, terms)}</h3>
        <p>{H(g.body, terms)}</p>
        <p>{_derived_hero_html(g, terms)}</p>
        {after}
      </section>
""")

    toc = toc_list([
        {"label": "簡介與閱讀說明", "id": "lead"},
        {"label": "商店名稱對照", "id": "shop"},
        {"label": "套裝總覽", "id": "overview"},
        {"label": "各套裝資料", "id": "suits"},
        {"label": "新套裝（血怒、泰坦、騎士，未開放）", "id": "suits-new", "depth": 1},
        *[{"label": _suit_heading(s, html=True), "id": f"suit-{s.suit_id}", "depth": 2} for s in data.suits if s.version == 1],
        {"label": "舊套裝（2 件／4 件）", "id": "suits-old", "depth": 1},
        *[{"label": _suit_heading(s, html=True), "id": f"suit-{s.suit_id}", "depth": 2} for s in data.suits if s.version == -1],
        {"label": "文案未填的套裝列", "id": "unfilled", "depth": 1},
        {"label": "無套裝散件", "id": "loose"},
        {"label": "打造、進階、精通與精煉", "id": "systems"},
        {"label": "專武", "id": "exclusive"},
        {"label": "由表推算的角色套裝（非官方欄位）", "id": "derived"},
        *[{"label": g.title, "id": g.anchor, "depth": 1} for g in data.derived],
        {"label": "本頁未列入", "id": "out-of-scope"},
        {"label": "資料說明", "id": "notes"},
    ])

    slot_bits = "、".join(f"{s.slot_id}＝{s.name}（名稱鍵 {s.name_key}）" for s in data.slots)
    q6_names = "、".join(s.name for s in data.suits if 6 in s.qualities)

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">本頁列出四件套裝備的 12 個實際使用套裝、無套裝散件、商店名稱對照，以及打造、進階與合成規則。專武已有獨立總表，本頁只交叉引用。</p>
    </header>
    {toc}
    <section id="lead">
      <h2>簡介與閱讀說明</h2>
      <p>正文只根據遊戲資料表與官方字串，不評定套裝強弱。表上沒有「每個英雄推薦哪套裝備」的欄位；角色搭配一節是依英雄屬性推算，不是官方列，已另外標明。</p>
      <p>名錄以較新的裝備定義為準，較舊的展開表不拿來當完整名錄。檔名與筆數見資料說明。</p>
      <p>部位共四格：{H("武器", terms)}、{H("衣服", terms)}、{H("鞋子", terms)}、{H("頭盔", terms)}。四格都是等級 5 顯示與解鎖。鞋子與頭盔的編號順序與名稱不完全相同，對照見資料說明。</p>
      <p>兩套套裝體例並存。舊套裝用 2 件／4 件效果；新套裝（{H("泰坦之威", terms)}、{H("血之怒", terms)}、{H("騎士榮光", terms)}）用「集齊 4 件／4 件升至 40 級／4 件突破至紅色」三檔。官方鍛造介面寫「{H(o["forge_404"], terms)}」。這三套尚未開放：表上沒有裝備「已推出」欄。功能條件是{H("鐵匠鋪", terms)} 15 級開啟「{H(o["forge_014"], terms)}／{H("傳奇打造", terms)}」（官方提示「{H(o["forge_open"], terms)}」；前置{H("城堡", terms)} 16 級），也沒有商店自選箱。品質 6 的{H(q6_names, terms)}是另一條舊線，已有進階路徑和商店箱，不標未開放。同版本的侍從級至元帥級散件是合成進這三套的線，本身不標未開放。</p>
      <p>套裝效果以官方說明文案為準。表上另有原始點數（例如裝備攻擊／裝備生命的 500 對應文案「裝備生命＋5%」），本頁在需要核對時附上原始點數，不另行換算未見於文案的百分比。這與天賦、造型、英靈的 ÷100 規則不同，也不沿用專武部分英雄屬性保留原值的寫法。</p>
      <p>升星與突破加成照表列出，格式為「門檻、屬性、數值」。表上沒有說明門檻等於第幾星或第幾級，本頁不自行解釋。品質欄是表上的 2–6，正文不另改稱傳說或神話。名稱已自帶「侍從級／士兵級／騎士級／元帥級」的，照錄。</p>
      <p>打造可帶陣營標記。{H("泰坦印記", terms)}官方說明：「{H(o["titan_desc"], terms)}」。介面另寫：「{H(o["forge_210"], terms)}」「{H(o["forge_sys_08"], terms)}」。商店箱也寫「可在任意陣營的〔某件〕中選擇」。資料表沒有為每個陣營各存一筆獨立編號，本頁不自造分營零件列。</p>
        </section>
    <section id="shop">
      <h2>商店名稱對照</h2>
      <p>玩家常說的「{H("生命套裝", terms)}」來自禮包與自選箱文案（例如「{H(o["life_pack"], terms)}」、「{H(o["life_box_weapon"], terms)}」，說明「{H(o["life_box_weapon_desc"], terms)}」），不是套裝表裡的正式套裝名。</p>
      {shop_tbl}
      <p>品質 6 零件在取得來源欄仍掛在橙色／橘色自選箱上（箱名文案稱「{H(o["equip_color_5"], terms)}／{H(o["equip_orange"], terms)}」，對應表上品質 5 的大地／冠軍／賢者箱）：{H("太陽之怒", terms)}、{H("扭曲印記", terms)}掛{H("賢者套裝自選箱（無陣營）", terms)}（文案「{H(o["box_xianzhe_desc"], terms)}」）；{H("雷霆庇護", terms)}、{H("凱旋之歌", terms)}掛{H("大地套裝自選箱（無陣營）", terms)}（文案「{H(o["box_dadi_desc"], terms)}」）；{H("聖光祝福", terms)}掛{H("冠軍套裝自選箱（無陣營）", terms)}（文案「{H(o["box_guanjun_desc"], terms)}」）。{H("生命之力", terms)}兩組零件同屬一套，但箱子不同：森林法杖一線掛大地箱，生命法杖一線掛冠軍箱。上述取得來源同時還掛無陣營部位自選箱（例如「{H(o["slot_box_weapon"], terms)}」；編號見資料說明）。本頁不把箱名「橙色／橘色」自行改成品質 6。</p>
      <p>較舊的展開表裡，大地／冠軍／賢者有陣營欄：{H("聯盟", terms)}、{H("部族", terms)}、{H("自然", terms)}，或商店稱「{H("無陣營", terms)}」。商店自選箱也按這四類分開。品質 6 與泰坦／血怒／騎士在較新的裝備定義裡沒有再為各營各存一筆分件。舊表另有一批同套裝、但未出現在較新定義的零件名稱，本名錄仍以新表 111 筆為準，不把舊表 2561 筆逐件展開。編號對照見資料說明。</p>
    </section>
    <section id="overview">
      <h2>套裝總覽</h2>
      <p>去重後，較新的裝備定義實際用到的套裝有 12 套（舊套裝 9、新套裝 3）。另有兩組名稱文案是「0.0」、4 件說明只有「4件：」，本頁視為文案未填，不當作正式套裝。編號對照見資料說明。同一中文套裝名在套裝表會重複多組（例如「{H("大地的守護者", terms)}」），2 件／4 件效果文案相同。本頁不臆測其餘組各自對應哪個陣營或伺服器分段。</p>
      <p>總覽表中，泰坦之威、血之怒、騎士榮光的「未開放」是本站加上的標註，不是表上的欄位。說明見資料說明。</p>
      {overview_tbl}
    </section>
    <section id="suits">
      <h2>各套裝資料</h2>
      <section id="suits-new">
        <h3>新套裝（血怒、泰坦、騎士，未開放）</h3>
        <p>這三套尚未開放：表上沒有裝備「已推出」欄。功能條件是{H("鐵匠鋪", terms)} 15 級開啟「{H(o["forge_014"], terms)}」（提示文案作「{H("傳奇打造", terms)}」：「{H(o["forge_open"], terms)}」），前置{H("城堡", terms)} 16 級。三套都不在普通隨機打造池，也沒有商店自選箱；指定打造為{H("太陽金", terms)} ×750、172800 秒，或由 20 件騎士級合成，對應部位在三套中三選一。品質 6 舊線不在此列。以下效果與消耗仍照表列出，供日後開放時對照。</p>
        <p>這三套在官方鍛造介面被稱為{H("血怒", terms)}、{H("泰坦", terms)}、{H("騎士", terms)}。官方另有轉換提示：「{H(o["forge_409"], terms)}」。本頁不把這句話寫成合成公式以外的路徑。四件集齊即可啟動套裝屬性，另有「升至 40 級」「突破至紅色」兩檔強化。套裝羈絆為品質 2–6 共五檔，下列原始點數，不換算成百分比。</p>
        {''.join(new_sections)}
      </section>
      <section id="suits-old">
        <h3>舊套裝（2 件／4 件）</h3>
        <p>以下為舊套裝。品質 5 的賢者／大地／冠軍，可分別用對應部位的進階石（{H("武器進階石", terms)}／{H("衣服進階石", terms)}／{H("鞋子進階石", terms)}／{H("頭盔進階石", terms)}各 ×1）進階為{H("太陽之怒", terms)}／{H("雷霆庇護", terms)}／{H("聖光祝福", terms)}。{H("生命之力", terms)}、{H("扭曲印記", terms)}、{H("凱旋之歌", terms)}在進階表沒有進階列。</p>
        {''.join(old_sections)}
      </section>
      <section id="unfilled">
        <h3>文案未填的套裝列</h3>
        <p>套裝表還有兩組文案未填的列。名稱對照見資料說明，文案是「0.0」。較新的裝備定義沒有零件掛這兩組。本頁不為它們編造套裝名。</p>
        {unfilled_tbl}
      </section>
    </section>
    <section id="loose">
      <h2>無套裝散件</h2>
      <p>較新的裝備定義裡，未掛套裝的有 {e(str(len(data.loose)))} 件，分兩類：舊式無套裝零件，以及新版冠以侍從級／士兵級／騎士級／元帥級的零件。新版合成表寫明：4 件可合成士兵級、15 件合成騎士級、20 件合成泰坦／血之怒／騎士榮光三套之一（三套各自有武器與對應部位的合成池，編號見資料說明；這三套尚未開放）。侍從級至元帥級這 16 件本身不標未開放。</p>
      <p>部分舊式零件中文名重複、屬性也相同，但編號不同（例如兩件都叫冷酷戰斧），照列分列，不合併、不刪。狂戰士之斧、狂戰士的盔甲、輕便靴子數值與後續同名或同部位件差距很大，本頁照錄，不判斷是否為測試或教學件。名稱「部落護甲」「部落戰靴」是官方字串，照錄，不改寫成「部族」。</p>
      {loose_tbl}
    </section>
    <section id="systems">
      <h2>打造、進階、精通與精煉</h2>
      <p>本頁只列系統與表上規則，<strong>不計算打造、升星、突破的完整養成曲線，也不排養成優先。</strong>精煉六檔數值與全部消耗未在第 13 章展開，此處也不自行補成完整消耗表。</p>
      <ul>
        <li><strong>打造等級</strong>表（{e(str(data.counts["make_level"]))} 筆），含經驗、前置建築等級、消耗、成功率，以及裝備、陣營、星數、品質的隨機權重。陣營隨機欄的權重對照介面「無陣營／聯盟／部族／自然」與泰坦印記說明，但表上沒有把 0–3 寫成這四個中文名，本頁不把權重改寫成機率百分比。欄位原值見資料說明。檔名見資料說明。</li>
        <li><strong>建造／打造預覽</strong>表（{e(str(data.counts["build"]))} 筆），依建築等級與類型列出品質權重與預覽裝備編號，本頁不逐列展開。</li>
        <li><strong>進階（舊套品質 5→6）：</strong>進階表 {e(str(data.counts["upgrade"]))} 筆。賢者長杖一線→太陽之怒；大地之斧一線→雷霆庇護；冠軍之劍一線→聖光祝福。消耗為對應部位進階石 ×1。生命之力、扭曲印記、凱旋之歌無此列。</li>
      </ul>
      {upgrade_tbl}
      <ul>
        <li><strong>合成（新版）：</strong> 4 件→士兵級，15 件→騎士級，20 件→泰坦之威／血之怒／騎士榮光三套的對應部位（三選一池）。編號對照見資料說明。這三套標為未開放；侍從級至元帥級散件不標。</li>
      </ul>
      {syn_tbl}
      <ul>
        <li><strong>材料：</strong>{H("太陽金", terms)}（官方說明「{H(o["sun_gold_desc"], terms)}」）；{H("泰坦印記", terms)}（官方說明「{H(o["titan_desc"], terms)}」）。材料表有兩筆名稱同為「{H("裝備精華", terms)}」，照列分列，不合併；編號見資料說明。材料表另有 {e(str(data.counts["material"]))} 筆合成／分解數量關係，本頁未展開。</li>
        <li><strong>詞條：</strong>詞條表 {e(str(data.counts["entry"]))} 筆，是隨機屬性條目（含屬性、分數、品質、戰力）。較舊的展開表以詞條組引用這些組，本頁不逐條展開。</li>
        <li><strong>裝備精通：</strong>裝備精通表 {e(str(data.counts["master"]))} 筆，按類型、等級（以及部分列的品質）給裝備攻擊、裝備生命，部分列還有出征上限。本頁不把類型臆測成部位或套裝。</li>
        <li><strong>套裝精煉與套裝羈絆：</strong>套裝精煉表 {e(str(data.counts["refine"]))} 筆，只覆蓋新三套與舊的太陽／雷霆／聖光／生命／扭曲／凱旋。每部位可從若干精煉屬性表的列中取值，列上依品質 1–6 有一組遞增數值。上節各套裝已列出可選屬性種類，六檔數值見原表，本頁不全部抄列。套裝羈絆表的羈絆是 4 件都精煉到指定品質才啟動，屬養成加深，不是另一套裝備。</li>
        <li><strong>升星／突破表：</strong>升星表（{e(str(data.counts["star_up"]))} 筆）、突破表（{e(str(data.counts["break"]))} 筆）體積較大，本頁不展開消耗。新三套零件上已列出升星與突破加成的門檻與屬性。</li>
      </ul>
    </section>
    <section id="exclusive">
      <h2>專武</h2>
      <p>專武（英雄專屬裝備）與本頁的四件套裝備分開，不列名錄，也不複製已上線的四張專武表或未發佈的專武圖。定義、升級、突破、消耗、屬性和各把效果見已發佈的<a href="exclusive.html">{H("專武總表", terms)}</a>。角色圖鑑各條只記專武名稱。</p>
    </section>
    <section id="derived">
      <h2>由表推算的角色套裝（非官方欄位）</h2>
      <p><strong>本節是推算，不是官方推薦列。</strong>表上沒有「每個英雄推薦哪一套裝備」的欄位。以下依英雄屬性四類對套裝 2／4 件效果推算，同一類走同一條主線，並另列後期打造套。英雄屬性只寫表上的原始點數（例如英雄治療率 500），不把已鎖定的四項百分比套用或延伸到本節。未把技能逐條模擬，英雄生命那組尤其不能一刀切。後期對應的泰坦之威、血之怒、騎士榮光尚未開放，目前可用路徑停在品質 6 或橙色過渡套；打造套仍照推算列出，供開放後對照。本節不寫進英雄條目頁。</p>
      {''.join(derived_secs)}
    </section>
    <section id="out-of-scope">
      <h2>本頁未列入</h2>
      <ul>
        <li>領主裝備與神器／秘寶。</li>
        <li>皮膚套裝、城市 DIY 套裝、世界皮膚套裝（屬外觀，不是英雄裝備）。</li>
        <li>打造、升星、突破、精煉的完整消耗與屬性加總，以及精煉六檔數值、精通表逐列。</li>
        <li>依技能逐條模擬後的裝備搭配；上述角色套裝只依英雄屬性推算。</li>
        <li>專武升級與突破（見<a href="exclusive.html">專武總表</a>）。</li>
      </ul>
    </section>
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>以下是整理用註記，查套裝與效果可略過。</li>
        <li>可見正文把檔名與欄位名收到這裡。較新的裝備定義原名 <code>equipment_new.json</code>；較舊的展開表原名 <code>equipment.json</code>；套裝表 <code>equipment_suit.json</code>（未填文案列的名稱鍵是 <code>equipment_suit_101</code>／<code>equipment_suit_102</code>）。可見各套裝標題不再寫套裝編號，改寫官方套裝名（未開放三套標題仍加「未開放」）。可見總覽表不再寫編號欄，套裝編號對照見此。可見商店表「套裝正式名」不再附加括號編號，改寫官方套裝名（未開放三套仍加「未開放」）。可見舊套零件「進階」欄不再附加括號編號，改寫「由 …進階而來」／「→ …」加官方零件名；編號對照見此。可見商店表「對應零件與備註」不再附加括號編號區間，改寫官方零件名；編號對照見此。可見舊套零件表與無套裝散件表不再寫編號欄，改寫官方零件名；編號對照見此。可見新三套零件表也不再寫編號欄，改寫官方零件名；編號對照見此。可見各套裝正文不再寫「版本：-1（舊套裝）／版本：1（新套裝）」，改寫總覽已用的「新套裝／舊套裝」；原值對照見此。可見合成說明不再寫士兵級（1301–1304）、騎士級（1401–1404），改寫官方階名；編號對照見此。可見舊套正文不再寫「同名套裝效果列還出現在套裝編號 …零件掛的是」編號，改寫「其他資料組／本套」，編號對照見此。可見總覽與文案未填節不再寫套裝編號 101、102，仍照錄官方名稱文案「0.0」與 4 件說明「4件：」，視為文案未填，不當作正式套裝，不編造套裝名；編號對照見此（101、102）。可見「同一中文套裝名會重複多組」對應套裝編號，例如「大地的守護者」有 103、301、419、519 等；較舊展開表引用的詞條組編號原名 <code>entry_group</code>；套裝編號原名 <code>suit_id</code>，未掛套裝為 <code>suit_id=-1</code>；陣營欄 <code>race_list</code>；取得來源欄 <code>get_id</code>；零件最高等級／可否突破原欄名 <code>max_level</code>、<code>break_on</code>（新三套為 40 與 1）。進階表 <code>equipment_upgrade.json</code>；打造等級表 <code>equipment_make_level.json</code>；陣營隨機欄原文為 <code>0|300,1|100,2|100,3|100</code>（0 與 1／2／3 對照介面「無陣營／聯盟／部族／自然」與泰坦印記說明，表上沒有把 0–3 寫成這四個中文名，可見正文不照錄原字串，也不把權重改寫成機率百分比）；打造預覽表 <code>equipment_build.json</code>；材料表 <code>equipment_material.json</code>；詞條表 <code>equipment_entry.json</code>，詞條組編號 <code>entry_group</code>；裝備精通表 <code>equipment_master.json</code>（按 <code>type</code>、<code>level</code>）；套裝精煉表 <code>equipment_suit_refine.json</code>；精煉屬性表 <code>equipment_suit_attribute</code>；套裝羈絆表 <code>equipment_suit_bond.json</code>；升星表 <code>equipment_star_up.json</code>、突破表 <code>equipment_break.json</code>；升星／突破加成本名 <code>starAttrs</code>／<code>breakBonusAttr</code>；合成表 <code>equipment_synthesize</code>；角色詳情表 <code>hero_detail.json</code>；領主裝備表 <code>lord_equipment.json</code>。可見正文「英雄屬性」對應角色詳情表的稱號屬性欄。可見裝備屬性只寫官方名與原值，編號見此：裝備攻擊 65／165、裝備生命 66／166、增傷 18／20、減傷 19／21／26／1200116；文案「裝備生命＋5%」對應的原始點數例是裝備攻擊／裝備生命 165／166 的 500。舊套裝 <code>version=-1</code>，新套裝 <code>version=1</code>。精煉戰力欄原名 <code>power_suit_refine</code>。版本欄可見寫成「新套裝／舊套裝」，原值 <code>version=1</code>／<code>version=-1</code>。套裝效果備註「零件編號」原名 <code>component</code>（含 <code>-1</code>）。陣營打造另耗原名 <code>race_produce_goods</code>／<code>RaceCostDic</code>。</li>
        <li>名錄以 <code>equipment_new.json</code>（111 筆定義）為準。<code>equipment.json</code>（2561 筆）是較舊的展開表，含等級欄（1、20、40…200），品質只到 5，套裝 id 也只出現 301／302／303，不拿它當完整名錄。部位出自 <code>equipment_slot.json</code>；四格的 <code>unlock_level</code> 與 <code>show_level</code> 皆為 5。id 3 的名稱鍵是 <code>equipment_slot_name_4</code>（鞋子），id 4 是 <code>equipment_slot_name_3</code>（頭盔）。對照見頁內部位表。<code>equipment_new.type</code> 1–4 分別對應這四個部位。舊套裝 <code>version=-1</code>，新套裝 <code>version=1</code>。鐵匠鋪前置見新建築表 <code>citybuilding_lvup_new</code>（舊表鐵匠鋪只到對應最高級）。升星與突破加成照 <code>starAttrs</code>、<code>breakBonusAttr</code> 列出。<code>equipment_new</code> 沒有為每個陣營各存一筆獨立 id。</li>
        <li>資料出自遊戲資料表與官方字串（equipment_new、equipment_slot、equipment_suit、equipment_suit_group、equipment_suit_bond、equipment_suit_refine、equipment_suit_attribute、equipment_upgrade、equipment_synthesize、equipment_make_level、equipment_build、equipment_material、equipment_entry、equipment_master、equipment_star_up、equipment_break、hero_detail、attribute、strings_zh.json），資料截至 {EQUIP_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {e(EQUIP_DATA_PACK)}（759 張表），打包時戳 {EQUIP_DATA_PACKED}（香港時間）。這 17 張 <code>equipment*.json</code> 與 <code>hero_detail.json</code> 與第 13 章所用 2026-11-05 解壓檔、以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。顯示規則依攻略手冊「裝備圖鑑」第四版（2026-11-13，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。這不是官方 wiki。</li>
        <li>泰坦之威、血之怒、騎士榮光的「未開放」依玩家確認標註，不是表上的欄位。藥劑師歸自然亦依玩家確認。品質 6 舊線與侍從級至元帥級散件不標未開放。公開名冊裡只有牧羊人（10029）標未開放；老闆娘不標未開放。</li>
      </ul>
    </section>
"""
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {EQUIP_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_equipment_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def render_markdown(data: TablesData) -> str:
    o = data.official
    q6_names = "、".join(s.name for s in data.suits if 6 in s.qualities)
    lines: list[str] = []
    add = lines.append

    add("# Top Heroes Wiki｜裝備總表")
    add("")
    add(
        f"資料截至 {EQUIP_DATA_CUTOFF}（香港時間）。這不是官方 wiki。"
        f"來源是 LocalLow 包 {EQUIP_DATA_PACK}（759 張表），打包時戳 {EQUIP_DATA_PACKED}（香港時間）。"
        "這 17 張 equipment*.json 與 hero_detail.json 與第 13 章所用 2026-11-05 解壓檔、"
        "以及 2026-11-22 StreamingAssets／LocalLow 歸檔位元組相同；"
        "這不表示整個 LocalLow 包與 2026-11-05 解壓檔相同。"
        "顯示規則依攻略手冊「裝備圖鑑」第四版（2026-11-13，香港時間；該章標題仍寫來源解壓日期 2026-11-05）。"
    )
    add("")
    add("## 簡介與閱讀說明")
    add("")
    add("正文只根據遊戲資料表與官方字串，不評定套裝強弱。表上沒有「每個英雄推薦哪套裝備」的欄位；角色搭配一節是依稱號屬性推算，不是官方列。")
    add("")
    add("名錄以較新的裝備定義為準，較舊的展開表不拿來當完整名錄。檔名與筆數見資料說明。")
    add("")
    add("部位共四格：武器、衣服、鞋子、頭盔。四格都是等級 5 顯示與解鎖。鞋子與頭盔的編號順序與名稱鍵不完全相同，對照見資料說明。")
    add("")
    add(
        f"兩套套裝體例並存。舊套裝用 2 件／4 件效果；新套裝（泰坦之威、血之怒、騎士榮光）用「集齊 4 件／4 件升至 40 級／4 件突破至紅色」三檔。"
        f"官方鍛造介面寫「{o['forge_404']}」。這三套尚未開放：表上沒有裝備「已推出」欄。"
        f"功能條件是鐵匠鋪 15 級開啟「{o['forge_014']}／傳奇打造」（官方提示「{o['forge_open']}」；前置城堡 16 級），也沒有商店自選箱。"
        f"品質 6 的{q6_names}是另一條舊線，已有進階路徑和商店箱，不標未開放。同版本的侍從級至元帥級散件是合成進這三套的線，本身不標未開放。"
    )
    add("")
    add("套裝效果以官方說明文案為準。表上另有原始點數，本頁在需要核對時附上，不另行換算未見於文案的百分比。升星與突破加成照表列出，格式為「門檻、屬性、數值」；表上沒有說明門檻等於第幾星或第幾級，本頁不自行解釋。品質欄是表上的 2–6，不另改稱傳說或神話。")
    add("")
    add(f"打造可帶陣營標記。泰坦印記官方說明：「{o['titan_desc']}」。介面另寫：「{o['forge_210']}」「{o['forge_sys_08']}」。資料表沒有為每個陣營各存一筆獨立編號。")
    add("")
    add("## 商店名稱對照")
    add("")
    add(f"玩家常說的「生命套裝」來自禮包與自選箱文案（例如「{o['life_pack']}」、「{o['life_box_weapon']}」，說明「{o['life_box_weapon_desc']}」），不是 `equipment_suit` 裡的正式套裝名。")
    add("")
    add(md_table(["商店／介面用詞", "套裝正式名（編號）", "對應零件與備註"], data.shop_rows))
    add("")
    add(
        f"品質 6 零件在 `equipment_new.get_id` 仍掛在橙色／橘色自選箱上（箱名文案稱「{o['equip_color_5']}／{o['equip_orange']}」，對應表上品質 5 的大地／冠軍／賢者箱）。"
        f"太陽之怒、扭曲印記掛賢者套裝自選箱（無陣營）（11145001，文案「{o['box_xianzhe_desc']}」）；"
        f"雷霆庇護、凱旋之歌掛大地套裝自選箱（無陣營）（11145005，文案「{o['box_dadi_desc']}」）；"
        f"聖光祝福掛冠軍套裝自選箱（無陣營）（11145009，文案「{o['box_guanjun_desc']}」）。"
        "生命之力兩組零件同屬套裝 314，但箱子不同：森林法杖一線掛大地箱，生命法杖一線掛冠軍箱。"
        f"上述 `get_id` 同時還掛無陣營部位自選箱（12120101–12120104，例如「{o['slot_box_weapon']}」）。本頁不把箱名「橙色／橘色」自行改成品質 6。"
    )
    add("")
    add("舊表 `equipment.json` 裡，大地／冠軍／賢者（suit_id 301／302／303）有陣營欄 `race_list`：1 聯盟、2 部族、3 自然，或 `1|2|3`（商店稱「無陣營」）。品質 6 與泰坦／血怒／騎士在 `equipment_new` 沒有再為各營各存一筆分件。本名錄仍以新表 111 筆為準。")
    add("")
    add("## 套裝總覽")
    add("")
    add("去重後，`equipment_new` 實際用到的套裝有 12 套（舊套裝 9、新套裝 3）。另有套裝 id 101、102，名稱文案是「0.0」、4 件說明只有「4件：」，視為文案未填，不當作正式套裝。總覽表中，泰坦之威、血之怒、騎士榮光的「未開放」是本站加上的標註，不是表上的欄位。說明見資料說明。")
    add("")
    ov_rows = []
    for s in data.suits:
        name = s.name + ("（未開放）" if s.unreleased else "")
        ov_rows.append([name, str(s.suit_id), s.version_label, s.quality_label, s.overview])
    add(md_table(["套裝", "編號", "版本", "品質（零件）", "件數效果摘要"], ov_rows))
    add("")
    add("## 各套裝資料")
    add("")
    add("### 新套裝（血怒、泰坦、騎士，未開放）")
    add("")
    add(
        f"這三套尚未開放：表上沒有裝備「已推出」欄。功能條件是鐵匠鋪 15 級開啟「{o['forge_014']}」（提示文案作「傳奇打造」：「{o['forge_open']}」），前置城堡 16 級。"
        "三套都不在普通隨機打造池，也沒有商店自選箱；指定打造為太陽金 ×750、172800 秒，或由 20 件騎士級合成，對應部位在三套中三選一。"
        f"官方鍛造介面稱之為血怒、泰坦、騎士，並寫「{o['forge_404']}」。另有轉換提示：「{o['forge_409']}」。本頁不把這句話寫成合成公式以外的路徑。"
    )
    add("")
    for s in data.suits:
        if s.version != 1:
            continue
        add(f"#### {_suit_heading(s)}")
        add("")
        add(f"- 版本：{s.version}（新套裝）")
        add(f"- 鍛造介面簡稱：{s.forge_short}")
        add("- 套裝效果：")
        for ev in s.effects:
            note = f"（{ev.raw_note}）" if ev.raw_note else ""
            add(f"  - {ev.desc}{note}")
        add("- 零件（品質皆為 5）：")
        add("")
        add(md_table(
            ["編號", "名稱", "部位", "基礎屬性", "升星加成", "突破加成", "戰力欄"],
            [[str(p.piece_id), p.name, p.slot_name, p.attrs_text, p.star_text, p.break_text, p.fightforce] for p in s.pieces],
        ))
        add("")
        add(f"- 打造消耗（四件相同）：{s.produce_text}。{s.race_produce_text}。")
        if s.bonds:
            add("- 套裝羈絆（quality 2–6）：")
            for b in s.bonds:
                add(f"  - quality {b.quality}：{b.text}")
        if s.refine:
            add("- 套裝精煉可選屬性（列 id → 屬性名；數字是 `equipment_suit_attribute` 的列 id，不是屬性 id）：")
            for opt in s.refine:
                add(f"  - {opt.slot_name}：" + "、".join(lab for _, _, lab in opt.entries))
        add("")
    add("### 舊套裝（2 件／4 件）")
    add("")
    add("以下套裝 `version=-1`。品質 5 的賢者／大地／冠軍，可分別用對應部位的進階石（貨品 144–147 各 ×1）進階為太陽之怒／雷霆庇護／聖光祝福。生命之力、扭曲印記、凱旋之歌在 `equipment_upgrade.json` 沒有進階列。")
    add("")
    for s in data.suits:
        if s.version != -1:
            continue
        add(f"#### {_suit_heading(s)}")
        add("")
        add(f"- 版本：{s.version}（舊套裝）")
        if s.leftover_ids:
            ids = "、".join(str(i) for i in s.leftover_ids)
            add(f"- 同名套裝效果列還出現在 suit_id {ids}，文案相同，`equipment_new` 零件掛的是 {s.suit_id}。本頁不臆測其餘 id 各自對應哪個陣營或伺服器分段。")
        add("- 套裝效果：")
        for ev in s.effects:
            note = f"（{ev.raw_note}）" if ev.raw_note else ""
            add(f"  - {ev.desc}{note}")
        add("- 零件：")
        add("")
        add(md_table(
            ["編號", "名稱", "部位", "品質", "基礎屬性", "戰力欄", "進階"],
            [[str(p.piece_id), p.name, p.slot_name, str(p.quality), p.attrs_text, p.fightforce, p.upgrade_text] for p in s.pieces],
        ))
        add("")
        if s.bonds:
            add("- 套裝羈絆（quality 2–6）：")
            for b in s.bonds:
                add(f"  - quality {b.quality}：{b.text}")
        if s.refine:
            add("- 套裝精煉可選屬性（列 id → 屬性名）：")
            for opt in s.refine:
                add(f"  - {opt.slot_name}：" + "、".join(lab for _, _, lab in opt.entries))
        add("")
    add("### 文案未填的套裝列")
    add("")
    add("`equipment_suit` 還有 101、102 兩組。名稱文案是「0.0」；`equipment_new` 沒有零件掛這兩個 id。本頁不為它們編造套裝名。")
    add("")
    uf_rows = []
    for u in data.unfilled:
        two = next(ev for ev in u.effects if ev.num == 2)
        four = next(ev for ev in u.effects if ev.num == 4)
        uf_rows.append([str(u.suit_id), u.name, f"{two.desc}（原始點數 {format_attrs(two.attrs)}）", four.desc])
    add(md_table(["suit_id", "名稱文案", "2 件說明", "4 件說明"], uf_rows))
    add("")
    add("## 無套裝散件")
    add("")
    add(f"`equipment_new` 裡 `suit_id=-1` 的有 {len(data.loose)} 件，分兩類：舊式無套裝零件（`version=-1`），以及新版冠以侍從級／士兵級／騎士級／元帥級的零件（`version=1`）。新版合成：4 件可合成士兵級、15 件合成騎士級、20 件合成泰坦／血之怒／騎士榮光三套之一（這三套尚未開放）。侍從級至元帥級這 16 件本身不標未開放。中文名重複但 id 不同的零件照 id 分列。名稱「部落護甲」「部落戰靴」是官方字串，照錄。")
    add("")
    add(md_table(
        ["編號", "名稱", "部位", "品質", "版本", "基礎屬性", "戰力欄"],
        [[str(p.piece_id), p.name, p.slot_name, str(p.quality), str(p.version), p.attrs_text, p.fightforce] for p in data.loose],
    ))
    add("")
    add("## 打造、進階、精通與精煉")
    add("")
    add("本頁只列系統與表上規則，**不計算打造、升星、突破的完整養成曲線，也不排養成優先。**精煉六檔數值與全部消耗未在第 13 章展開，此處也不自行補成完整消耗表。")
    add("")
    add(f"- **打造等級**在 `equipment_make_level.json`（{data.counts['make_level']} 筆）。陣營隨機欄原文為 `0|300,1|100,2|100,3|100`，本頁不把權重改寫成機率百分比，也不把 0–3 自行改寫成中文名。")
    add(f"- **建造／打造預覽**在 `equipment_build.json`（{data.counts['build']} 筆），本頁不逐列展開。")
    add(f"- **進階（舊套品質 5→6）：** `equipment_upgrade.json` {data.counts['upgrade']} 筆。生命之力、扭曲印記、凱旋之歌無此列。")
    add("")
    add(md_table(
        ["進階前編號", "進階前", "進階後編號", "進階後", "消耗"],
        [[str(a), b, str(c), d, f"{f} ×1" if f else "—"] for a, b, c, d, e_, f in data.upgrades],
    ))
    add("")
    add("- **合成（新版）：** 4 件→士兵級，15 件→騎士級，20 件→泰坦之威／血之怒／騎士榮光對應部位（三選一）。這三套標為未開放；侍從級至元帥級散件不標。")
    add("")
    add(md_table(
        ["消耗件數", "合成結果", "各部位池"],
        [[
            str(rec["num"]),
            rec["label"],
            f"武器 {'、'.join(map(str, rec['weapons']))}；衣服 {'、'.join(map(str, rec['armors']))}；鞋子 {'、'.join(map(str, rec['shoes']))}；頭盔 {'、'.join(map(str, rec['helmets']))}",
        ] for rec in data.synthesize],
    ))
    add("")
    add(f"- **材料：**太陽金（404100005，官方說明「{o['sun_gold_desc']}」）；泰坦印記（404100006，「{o['titan_desc']}」）。裝備精華有 301、302 兩個貨品 id，名稱同為「裝備精華」。`equipment_material.json` 另有 {data.counts['material']} 筆，本頁未展開。")
    add(f"- **詞條：** `equipment_entry.json` {data.counts['entry']} 筆，本頁不逐條展開。")
    add(f"- **裝備精通：** `equipment_master.json` {data.counts['master']} 筆。本頁不把 type 臆測成部位或套裝。")
    add(f"- **套裝精煉與套裝羈絆：** `equipment_suit_refine.json` {data.counts['refine']} 筆，只覆蓋新三套與舊的太陽／雷霆／聖光／生命／扭曲／凱旋。六檔數值見原表，本頁不全部抄列。")
    add(f"- **升星／突破表：** `equipment_star_up.json`（{data.counts['star_up']} 筆）、`equipment_break.json`（{data.counts['break']} 筆），本頁不展開消耗。")
    add("")
    add("## 專武")
    add("")
    add(f"專武與本頁的四件套裝備分開，不列名錄，也不複製已上線的四張專武表。細節見已發佈的[專武總表]({LIVE_EXCLUSIVE})。")
    add("")
    add("## 由表推算的角色套裝（非官方欄位）")
    add("")
    add("**本節是推算，不是官方推薦列。**表上沒有「每個英雄推薦哪一套裝備」的欄位。以下依稱號屬性四類對套裝 2／4 件效果推算。稱號屬性只寫表上的原始點數（例如英雄治療率 500），不把已鎖定的四項百分比套用或延伸到本節。未把技能逐條模擬。後期對應的泰坦之威、血之怒、騎士榮光尚未開放。本節不寫進英雄條目頁。")
    add("")
    for g in data.derived:
        add(f"### {g.title}")
        add("")
        add(g.body)
        add("")
        add(_derived_hero_md(g))
        add("")
        if g.after:
            add(g.after)
            add("")
    add("## 本頁未列入")
    add("")
    add("- 領主裝備與神器／秘寶。")
    add("- 皮膚套裝、城市 DIY 套裝、世界皮膚套裝。")
    add("- 打造、升星、突破、精煉的完整消耗與屬性加總，以及精煉六檔數值、精通表逐列。")
    add("- 依技能逐條模擬後的裝備搭配。")
    add(f"- 專武升級與突破（見[專武總表]({LIVE_EXCLUSIVE})）。")
    add("")
    add("## 資料說明")
    add("")
    add("- 以下是整理用註記，查套裝與效果可略過。")
    add("- 名錄以 `equipment_new.json`（111 筆定義）為準。`equipment.json`（2561 筆）是較舊的展開表。部位出自 `equipment_slot.json`；四格的 `unlock_level` 與 `show_level` 皆為 5。id 3 名稱鍵是 `equipment_slot_name_4`（鞋子），id 4 是 `equipment_slot_name_3`（頭盔）。舊套裝 `version=-1`，新套裝 `version=1`。鐵匠鋪前置見 `citybuilding_lvup_new`。升星與突破加成照 `starAttrs`、`breakBonusAttr` 列出。")
    add(f"- 資料截至 {EQUIP_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {EQUIP_DATA_PACK}（759 張表），打包時戳 {EQUIP_DATA_PACKED}（香港時間）。17 張 equipment*.json 與 hero_detail.json 與第 13 章 2026-11-05 解壓檔位元組相同，但不表示整個 LocalLow 包相同。顯示規則依攻略手冊「裝備圖鑑」第四版（2026-11-13，香港時間）。這不是官方 wiki。")
    add("- 泰坦之威、血之怒、騎士榮光的「未開放」依玩家確認標註，不是表上的欄位。藥劑師歸自然亦依玩家確認。品質 6 舊線與侍從級至元帥級散件不標未開放。公開名冊裡只有牧羊人（10029）標未開放；老闆娘不標未開放。")
    add("")
    return "\n".join(lines)
