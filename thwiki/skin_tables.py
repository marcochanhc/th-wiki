"""Compile the unpublished 造型 catalog tables (preview only; not wired into build.py)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from . import attrs as A
from .assemble import fashion_coins, hero_href, hero_name, star_team_rows, _pairs_to_map, _star_tier_maps
from .exclusive_tables import md_table
from .highlight import highlight
from .htmlutil import e, table
from .overrides import ROSTER, UNRELEASED_HERO_IDS, roster_display_name
from .paths import DATA_CUTOFF
from .strings import has_key, t
from .tables import catalog, load_table


LIVE_HERO = "https://marcochanhc.github.io/th-wiki/heroes/{id}.html"
# 造型預覽專用；不改 paths.DATA_CUTOFF，以免影響專武、英雄條目等已上線頁。
# 資料是 LocalLow 包 app-1.129.12_table-1.0.43173（759 張表），
# 打包時戳 2026-11-22 23:33（香港時間）。頁尾資料截至寫解壓包日期 2026-11-22，不寫整理次日。
SKIN_DATA_CUTOFF = "2026-11-22"
SKIN_DATA_PACK = "app-1.129.12_table-1.0.43173"
SKIN_DATA_PACKED = "2026-11-22 23:33"

COLLECT_POWER = 5500
TEAM_SCOPE = "全部"  # official skin_title_1; filled in load
SUIT_SCOPE_HERO = "套裝英雄"
SUIT_SCOPE_ALL = "全英雄"
FASHION_ITEM = 312

# Panel examples locked against handbook 15 (third edition).
ELEWEN_ID = 1003307
SHARK_ID = 1005002
PAIR_NEW_A = 1003108  # 審判官·富饒領主
PAIR_NEW_B = 1004208  # 豪士·武道宗師


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


def _hero_href_public(hero_id: int) -> str:
    if hero_href(hero_id):
        return f"heroes/{hero_id}.html"
    return ""


def _hero_link_html(hero_id: int, label: str, terms: list[str]) -> str:
    marked = H(label, terms)
    href = _hero_href_public(hero_id)
    if href:
        return f'<a href="{e(href)}">{marked}</a>'
    return marked


def _hero_link_md(hero_id: int, label: str) -> str:
    if hero_href(hero_id):
        return f"[{label}]({LIVE_HERO.format(id=hero_id)})"
    return label


def _int(value) -> int | None:
    if value in (None, "", -1):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_collectable(row: dict) -> bool:
    return row.get("add_power") == COLLECT_POWER


def _is_awaken(row: dict) -> bool:
    return row.get("is_awaken") == 1


def skin_display_name(row: dict) -> str:
    return t(row.get("skin_name")) or t(f"skin_name_{row.get('id')}") or str(row["id"])


def self_raw(row: dict):
    return row.get("attr1") or row.get("attr2")


def format_self(row: dict, hero_label: str) -> str:
    return A.format_skin_pairs(self_raw(row), scope=hero_label, joiner="；")


def format_unlocktime(raw) -> str:
    if raw in (None, "", -1, "無"):
        return "無" if raw == "無" else ""
    text = str(raw)
    if "|" in text and text.count("|") == 1:
        a, b = text.split("|", 1)
        left, right = a.strip(), b.strip()
        if left and right:
            return f"{left} 至 {right}"
    return text


def format_team(row: dict, *, max_star: bool = True) -> str:
    if row.get("CanUpStar") and _int(row.get("star_max")):
        rows = star_team_rows(row)
        if rows and max_star:
            return rows[-1][1]
        return A.format_skin_pairs(row.get("team_attr"), scope=TEAM_SCOPE, joiner="；")
    return A.format_skin_pairs(row.get("team_attr"), scope=TEAM_SCOPE, joiner="；")


def format_collect(row: dict, hero_label: str) -> str:
    parts = []
    self_txt = format_self(row, hero_label)
    team_txt = format_team(row, max_star=True)
    if self_txt != "無":
        parts.append(self_txt)
    if team_txt != "無":
        parts.append(team_txt)
    return "；".join(parts) if parts else "無"


def format_effect_pairs(raw) -> str:
    return A.format_skin_pairs(raw, joiner="、")


def attr_value_map(raw) -> dict[int, int]:
    """Parse attribute pairs to {id: raw int}. Used for summing display values."""
    return _pairs_to_map(raw)


def max_star_team_map(skin: dict) -> dict[int, int]:
    """Team attrs at max star: team_attr base + last star tier (same as table 1 / 2)."""
    base = _pairs_to_map(skin.get("team_attr"))
    if skin.get("CanUpStar") and _int(skin.get("star_max")):
        tiers = _star_tier_maps(skin)
        if tiers:
            combined = dict(base)
            for aid, val in tiers[-1].items():
                combined[aid] = combined.get(aid, 0) + val
            return combined
    return base


def format_sum_map(mapping: dict[int, int], order: list[int], *, scope: str | None = None, joiner: str = "；") -> str:
    """Format summed raw values with format_skin_attr (add first, then show_type)."""
    parts = []
    for aid in order:
        if aid not in mapping:
            continue
        item = A.format_skin_attr(aid, mapping[aid])
        if scope:
            item = f"{scope} {item}"
        parts.append(item)
    return joiner.join(parts) if parts else "無"


def add_into(dest: dict[int, int], order: list[int], src: dict[int, int]) -> None:
    for aid, val in src.items():
        dest[aid] = dest.get(aid, 0) + val
        if aid not in order:
            order.append(aid)


def unlock_text(row: dict) -> str:
    key = row.get("unlock_dec")
    if not key:
        return "無"
    return t(key) or str(key)


def season_text(row: dict) -> str:
    key = row.get("season_dec")
    if not key:
        return "無"
    return t(key) or str(key)


def season_effect_text(raw) -> str:
    if raw in (None, "", -1, 0):
        return "無"
    return format_effect_pairs(raw)


@dataclass
class SkinRow:
    row: dict
    skin_id: int
    hero_id: int
    hero_label: str  # official name, or the id for 15032/15033/15039
    hero_display: str  # may include （未開放）
    faction: str
    name: str
    quality: int | None
    coins: str
    unlock: str
    self_text: str
    team_text: str
    collect_text: str
    can_up: bool
    star_max: int | None
    star_consume: str
    star_goods: str
    star_team_max: str
    partner_id: int | None
    partner_name: str
    pair_attr: str
    suit_names: list[str]
    season: str
    season_no: str
    season_effect: str
    season_effect2: str
    has_voice: bool
    add_power: int


@dataclass
class SuitRow:
    suit_id: int
    name: str
    count: int
    quality: int | None
    need_raw: str
    conditions: list[str]
    members: list[tuple[int, str]]  # skin id, name
    tiers: list[tuple[str, str]]  # raw need segment, current-tier effect
    reward: str
    unlocktime: str


@dataclass
class PairRow:
    a_id: int
    a_name: str
    a_hero_id: int
    a_hero: str
    a_attr: str
    b_id: int
    b_name: str
    b_hero_id: int
    b_hero: str
    b_attr: str


@dataclass
class GroupRow:
    label: str
    count: int
    add_power: str
    note: str


@dataclass
class NoSkinRow:
    hero_id: int
    hero_label: str
    hero_display: str
    faction: str
    source: str
    has_default: bool
    default_note: str


@dataclass
class NamelessRow:
    hero_id: int
    count: int
    skin_ids: list[int]
    notes: list[str]


@dataclass
class HeroSumRow:
    hero_id: int
    faction: str
    hero_label: str
    hero_display: str
    count: int
    self_text: str
    team_text: str
    pair_text: str
    pair_partners: str
    season_text: str


@dataclass
class TablesData:
    collectable: list[SkinRow]
    hero_sums: list[HeroSumRow]
    star_skins: list[SkinRow]
    suits: list[SuitRow]
    pairs: list[PairRow]
    season_skins: list[SkinRow]
    awaken: list[SkinRow]
    no_skin: list[NoSkinRow]
    unnamed: list[SkinRow]  # 15032/15033/15039 collectable + awaken
    nameless: list[NamelessRow]  # 300xx
    groups: list[GroupRow]
    unlock_counts: list[tuple[str, str, int, int]]  # key, text, all, collectable
    coin_rows: list[list[str]]
    voice_collectable: tuple[int, int]
    voice_awaken: tuple[int, int]
    terms: list[str]
    verifications: dict
    button_dec: str
    fashion_name: str
    fashion_desc: str
    tab_book: str
    tab_suit: str


def _roster_index() -> dict[int, tuple[int, str, str, str]]:
    """hero_id -> (order, faction, official_or_none_label, display)."""
    out: dict[int, tuple[int, str, str, str]] = {}
    n = 0
    for faction, _anchor, heroes in ROSTER:
        for hid, official in heroes:
            label = official or str(hid)
            display = roster_display_name(hid, official)
            out[hid] = (n, faction, label, display)
            n += 1
    return out


def _faction_for(hero_id: int, roster: dict) -> str:
    if hero_id in roster:
        return roster[hero_id][1]
    fac, _src, _g, _a = A.hero_faction(hero_id)
    return fac or "無"


def _hero_label(hero_id: int, roster: dict) -> str:
    if hero_id in roster:
        return roster[hero_id][2]
    return hero_name(hero_id)


def _hero_display(hero_id: int, roster: dict) -> str:
    if hero_id in roster:
        return roster[hero_id][3]
    return hero_name(hero_id)


def _faction_source(hero_id: int, *, include_id: bool = True) -> str:
    fac, source, group, attr_id = A.hero_faction(hero_id)
    if source == "honor" and attr_id is not None:
        name = A.attr_name(attr_id)
        return f"榮譽加成鏈：{name}（{attr_id}）" if include_id else f"榮譽加成鏈：{name}"
    if source == "skill301":
        return "無陣營加成，依技能文案補入（既有圖鑑）"
    if source == "lock":
        # 藥劑師等鎖定陣營：公開文案不寫「由玩家確認」。
        return "依既有英雄圖鑑列為自然"
    return "無"


def _load_extra():
    voices = load_table("hero_skin_voice")
    models = load_table("skin")
    return {v["id"] for v in voices}, {m["id"]: m for m in models}


def _suit_members(suit: dict) -> list[int]:
    members = list(suit.get("heroSkinMetaIds") or [])
    if members:
        return [int(x) for x in members]
    hid = suit.get("hero_skin_id")
    if isinstance(hid, list):
        return [int(x) for x in hid]
    if hid in (None, "", -1, 0):
        return []
    out = []
    for seg in str(hid).split("|"):
        seg = seg.strip()
        if seg:
            out.append(int(seg))
    return out


def _build_suits(skin_map: dict[int, dict], name_of) -> list[SuitRow]:
    scope_hero = t("hero_skin_suit_12") or "套裝英雄"
    scope_all = t("hero_skin_suit_13") or "全英雄"
    tmpl = t("hero_skin_suit_3") or "收集{0}件套裝"
    out: list[SuitRow] = []
    # Handbook table follows suit id 1–10, not sort_id.
    for suit in sorted(catalog()["hero_skin_suit"], key=lambda s: s["id"]):
        members = _suit_members(suit)
        member_pairs = []
        for sid in members:
            row = skin_map.get(sid) or {}
            member_pairs.append((sid, name_of(row) if row else str(sid)))
        raw_need = suit.get("suit_star_need") or ""
        needs_raw = [seg.strip() for seg in str(raw_need).split(",") if seg.strip()] if raw_need else []
        conditions = []
        for seg in needs_raw:
            n = seg.split("|", 1)[0]
            conditions.append(tmpl.replace("{0}", str(n)))
        hero_cols: list[list[str]] = []
        all_cols: list[list[str]] = []
        for field in ("suit_hero_attibute_1", "suit_hero_attibute_2", "suit_hero_attibute_3"):
            raw = suit.get(field)
            if raw:
                hero_cols.append([p.strip() for p in str(raw).split(",") if p.strip()])
        for field in ("attibute_1", "attibute_2", "attibute_3"):
            raw = suit.get(field)
            if raw:
                all_cols.append([p.strip() for p in str(raw).split(",") if p.strip()])
        tiers = []
        for i, seg in enumerate(needs_raw):
            parts = []
            for col in hero_cols:
                if i < len(col):
                    parts.append(A.format_skin_pairs(col[i], scope=scope_hero, joiner="、"))
            for col in all_cols:
                if i < len(col):
                    parts.append(A.format_skin_pairs(col[i], scope=scope_all, joiner="、"))
            effect = "、".join(p for p in parts if p and p != "無") or "無"
            tiers.append((seg, effect))
        out.append(
            SuitRow(
                suit_id=suit["id"],
                name=t(suit.get("name")) or str(suit["id"]),
                count=int(suit.get("suit_num") or len(members)),
                quality=_int(suit.get("suit_quality")),
                need_raw=str(raw_need) if raw_need else "無",
                conditions=conditions,
                members=member_pairs,
                tiers=tiers,
                reward=str(suit.get("reward") or "無"),
                unlocktime=str(suit.get("unlocktime") or "無"),
            )
        )
    return out


def _build_pairs(collectable_rows: list[dict], name_of, roster) -> list[PairRow]:
    by_id = {s["id"]: s for s in collectable_rows}
    seen: set[tuple[int, int]] = set()
    pairs: list[PairRow] = []
    for row in collectable_rows:
        pid = row.get("suit")
        if pid in (None, "", -1, 0):
            continue
        pid = int(pid)
        partner = by_id.get(pid)
        if not partner:
            continue
        a, b = row["id"], pid
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        # Keep handbook orientation: lower id first, except keep data as stored
        # on each side's own suit_attr.
        left, right = row, partner
        if left["id"] > right["id"]:
            left, right = right, left
        pairs.append(
            PairRow(
                a_id=left["id"],
                a_name=name_of(left),
                a_hero_id=left["hero_id"],
                a_hero=_hero_label(left["hero_id"], roster),
                a_attr=A.format_skin_pairs(left.get("suit_attr"), joiner="、"),
                b_id=right["id"],
                b_name=name_of(right),
                b_hero_id=right["hero_id"],
                b_hero=_hero_label(right["hero_id"], roster),
                b_attr=A.format_skin_pairs(right.get("suit_attr"), joiner="、"),
            )
        )
    pairs.sort(key=lambda p: (p.a_id, p.b_id))
    return pairs


def _build_skin_row(row: dict, roster, voice_ids, suit_by_skin, name_of) -> SkinRow:
    hid = row["hero_id"]
    label = _hero_label(hid, roster)
    display = _hero_display(hid, roster)
    can_up = bool(row.get("CanUpStar"))
    star_max = _int(row.get("star_max")) if can_up else None
    partner_id = row.get("suit")
    if partner_id in (None, "", -1, 0):
        partner_id = None
        partner_name = "無"
        pair_attr = "無"
    else:
        partner_id = int(partner_id)
        partner = next((x for x in catalog()["hero_skin"] if x["id"] == partner_id), None)
        partner_name = name_of(partner) if partner else str(partner_id)
        pair_attr = A.format_skin_pairs(row.get("suit_attr"), joiner="、")
    goods = row.get("star_consume_goods")
    star_goods = "無" if goods in (None, "", -1, 0) else str(goods)
    consume = row.get("star_consume")
    star_consume = "無" if consume in (None, "", -1, 0) else str(consume)
    star_team_max = "無"
    if can_up and star_max:
        tiers = star_team_rows(row)
        if tiers:
            # star_team_rows already prefixes 全部; handbook star table omits the scope.
            star_team_max = tiers[-1][1].replace(f"{TEAM_SCOPE} ", "")
            star_team_max = star_team_max.replace("；", "、")
    season_no = row.get("season")
    return SkinRow(
        row=row,
        skin_id=row["id"],
        hero_id=hid,
        hero_label=label,
        hero_display=display,
        faction=_faction_for(hid, roster),
        name=name_of(row),
        quality=_int(row.get("quality")),
        coins=fashion_coins(row),
        unlock=unlock_text(row),
        self_text=format_self(row, label),
        team_text=format_team(row, max_star=True),
        collect_text=format_collect(row, label),
        can_up=can_up,
        star_max=star_max,
        star_consume=star_consume,
        star_goods=star_goods,
        star_team_max=star_team_max,
        partner_id=partner_id,
        partner_name=partner_name,
        pair_attr=pair_attr,
        suit_names=list(suit_by_skin.get(row["id"], [])),
        season=season_text(row),
        season_no="" if season_no in (None, "") else str(season_no),
        season_effect=season_effect_text(row.get("season_effect")),
        season_effect2=season_effect_text(row.get("season_effect2")),
        has_voice=row["id"] in voice_ids,
        add_power=int(row.get("add_power") or 0),
    )


def _sort_skins(rows: list[SkinRow], roster) -> list[SkinRow]:
    def key(s: SkinRow):
        order = roster[s.hero_id][0] if s.hero_id in roster else 10_000 + s.hero_id
        return (order, s.row.get("order") or 0, s.skin_id)

    return sorted(rows, key=key)


def _terms_for(data_collect, data_awaken, suits, pairs, no_skin) -> list[str]:
    terms = {
        t("goods_name_312") or "時裝幣",
        t("hero_skin_suit_1") or "圖鑑",
        t("hero_skin_suit_2") or "造型套裝",
        t("hero_skin_suit_12") or "套裝英雄",
        t("hero_skin_suit_13") or "全英雄",
        t("skin_title_1") or "全部",
        "聯盟",
        "自然",
        "部族",
    }
    def _add_attr_names(raw):
        for aid, _val in A.parse_pairs(raw):
            if aid is not None:
                terms.add(A.attr_name(aid))

    for row in data_collect + data_awaken:
        terms.add(row.name)
        terms.add(row.hero_label)
        if row.partner_name and row.partner_name != "無":
            terms.add(row.partner_name)
        for name in row.suit_names:
            terms.add(name)
        src = row.row
        for raw in (
            self_raw(src),
            src.get("team_attr"),
            src.get("suit_attr"),
            src.get("season_effect"),
            src.get("season_effect2"),
        ):
            _add_attr_names(raw)
        for i in range(1, 6):
            _add_attr_names(src.get(f"team_attr_{i}"))
        if row.season != "無":
            terms.add(row.season)
        if row.unlock != "無":
            terms.add(row.unlock)
    for suit in suits:
        terms.add(suit.name)
        for _sid, name in suit.members:
            terms.add(name)
        for raw, effect in suit.tiers:
            pass
    for su in catalog()["hero_skin_suit"]:
        for field in (
            "suit_hero_attibute_1", "suit_hero_attibute_2", "suit_hero_attibute_3",
            "attibute_1", "attibute_2", "attibute_3",
        ):
            raw = su.get(field)
            if not raw:
                continue
            for part in str(raw).split(","):
                _add_attr_names(part)
    for p in pairs:
        terms.update({p.a_name, p.b_name, p.a_hero, p.b_hero})
    for n in no_skin:
        terms.add(n.hero_label)
    # Drop very short fragments that would sit next to another .term inside
    # an official phrase (padding would insert a space).
    return sorted({x for x in terms if x and len(x) >= 2}, key=len, reverse=True)


def load_tables_data() -> TablesData:
    global TEAM_SCOPE, SUIT_SCOPE_HERO, SUIT_SCOPE_ALL
    TEAM_SCOPE = t("skin_title_1") or "全部"
    SUIT_SCOPE_HERO = t("hero_skin_suit_12") or "套裝英雄"
    SUIT_SCOPE_ALL = t("hero_skin_suit_13") or "全英雄"

    roster = _roster_index()
    voice_ids, models = _load_extra()
    all_skins = catalog()["hero_skin"]
    skin_map = {s["id"]: s for s in all_skins}
    hero_ids = set(catalog()["hero_by_id"])

    def name_of(row: dict) -> str:
        return skin_display_name(row)

    suits = _build_suits(skin_map, name_of)
    # Do not pull unreferenced string-only suit names into the live list.
    live_suit_names = {su.name for su in suits}
    suit_by_skin: dict[int, list[str]] = defaultdict(list)
    for su in suits:
        for sid, _name in su.members:
            if su.name not in suit_by_skin[sid]:
                suit_by_skin[sid].append(su.name)

    collectable_raw = [s for s in all_skins if _is_collectable(s)]
    awaken_raw = [s for s in all_skins if _is_awaken(s)]
    nameless_raw = [s for s in all_skins if s["hero_id"] not in hero_ids]
    unnamed_ids = {15032, 15033, 15039}

    collectable = _sort_skins(
        [_build_skin_row(s, roster, voice_ids, suit_by_skin, name_of) for s in collectable_raw],
        roster,
    )
    awaken = _sort_skins(
        [_build_skin_row(s, roster, voice_ids, suit_by_skin, name_of) for s in awaken_raw],
        roster,
    )
    pairs = _build_pairs(collectable_raw, name_of, roster)
    # 表二／表五列序跟第 15 章：依造型 id。表一總覽仍依本站名單總覽。
    season_skins = [s for s in collectable if s.season != "無" or s.season_effect != "無" or s.season_effect2 != "無"]
    season_skins.sort(key=lambda s: s.skin_id)
    star_skins = [s for s in collectable if s.can_up]
    star_skins.sort(key=lambda s: s.skin_id)
    unnamed = _sort_skins(
        [
            _build_skin_row(s, roster, voice_ids, suit_by_skin, name_of)
            for s in all_skins
            if s["hero_id"] in unnamed_ids
        ],
        roster,
    )

    no_skin = []
    for faction, _anchor, heroes in ROSTER:
        for hid, official in heroes:
            if any(s.hero_id == hid for s in collectable + awaken):
                continue
            # 尋路者／石匠 have only awaken rows, so they are not in this list.
            if hid in {s["hero_id"] for s in all_skins}:
                continue
            model = models.get(hid)
            if model:
                key = model.get("name")
                resolved = t(key) if key else ""
                bits = []
                if resolved:
                    bits.append(resolved)
                if model.get("head"):
                    bits.append(f"頭像 {model.get('head')}")
                note = "有預設模型（" + "，".join(bits) + "）" if bits else "有預設模型"
            else:
                note = "無與自身編號相同的預設模型列"
            no_skin.append(
                NoSkinRow(
                    hero_id=hid,
                    hero_label=official or str(hid),
                    hero_display=roster_display_name(hid, official),
                    faction=faction,
                    source=_faction_source(hid),
                    has_default=bool(model),
                    default_note=note,
                )
            )

    nameless_groups: dict[int, list[dict]] = defaultdict(list)
    for s in nameless_raw:
        nameless_groups[s["hero_id"]].append(s)
    nameless_rows = []
    for hid in sorted(nameless_groups):
        rows = sorted(nameless_groups[hid], key=lambda r: r["id"])
        notes = []
        for r in rows:
            mid = r.get("skin_id") or r["id"]
            model = models.get(mid)
            if model:
                key = model.get("name")
                resolved = t(key) if key else ""
                bit = f"{r['id']} 模型名稱：{mid}"
                if resolved:
                    bit += f"「{resolved}」（此為單位模型列名稱，不是造型圖鑑的造型名）"
                else:
                    bit += "（此為單位模型列名稱，不是造型圖鑑的造型名）"
            else:
                bit = f"{r['id']} 的外觀編號 {mid} 不在單位模型表"
            coins = fashion_coins(r)
            if coins != "無":
                ut = format_unlocktime(r.get('unlocktime')) or str(r.get('unlocktime') or "無")
                bit += f"；時裝幣價 {coins}，解鎖賽季欄 {r.get('unlock_season')}（只照錄），解鎖時間 {ut}"
            notes.append(bit)
        nameless_rows.append(
            NamelessRow(
                hero_id=hid,
                count=len(rows),
                skin_ids=[r["id"] for r in rows],
                notes=notes,
            )
        )

    groups = [
        GroupRow("可收集造型", len(collectable), "5500", "有隊伍屬性；多數可消耗時裝幣（312）在造型圖鑑解鎖"),
        GroupRow("覺醒造型", len(awaken), "0", "覺醒標記、品質 6、解鎖說明「英雄覺醒獲得」；沒有時裝幣價，也沒有自身／隊伍屬性"),
        GroupRow("300xx 列", len(nameless_raw), "0", "13 個編號（30001 起）不在英雄名錄，沒有造型名稱字串，也沒有造型戰力"),
    ]

    unlock_all = Counter((s.get("unlock_dec") or "（空）") for s in all_skins)
    unlock_col = Counter((s.get("unlock_dec") or "（空）") for s in collectable_raw)
    unlock_order = [
        "unlock_dec_jiesuo",
        "unlock_dec_awaken",
        "unlock_dec_jiesuo_1002706",
        "unlock_dec_shengdan",
        "（空）",
    ]
    unlock_counts = []
    for key in unlock_order:
        text = "—" if key == "（空）" else (t(key) or key)
        unlock_counts.append((key if key != "（空）" else "（空）", text, unlock_all[key], unlock_col[key]))

    coin_rows = []
    by_q = defaultdict(list)
    for s in collectable_raw:
        by_q[_int(s.get("quality"))].append(s)
    for q in sorted(k for k in by_q if k is not None):
        rows = by_q[q]
        priced = [s for s in rows if fashion_coins(s) != "無"]
        prices = sorted({fashion_coins(s) for s in priced})
        price_txt = "、".join(prices) if prices else "無"
        coin_rows.append(
            [str(q), str(len(rows)), str(len(priced)) + (f"（{price_txt}）" if priced else ""), str(len(rows) - len(priced))]
        )

    v_col = (sum(1 for s in collectable if s.has_voice), sum(1 for s in collectable if not s.has_voice))
    v_awk = (sum(1 for s in awaken if s.has_voice), sum(1 for s in awaken if not s.has_voice))

    terms = _terms_for(collectable, awaken, suits, pairs, no_skin)

    # --- per-hero sums of collectable skins (not awaken, not suits, not seasons in main) ---
    by_hero: dict[int, list[SkinRow]] = defaultdict(list)
    for s in collectable:
        by_hero[s.hero_id].append(s)
    hero_sums: list[HeroSumRow] = []
    for faction, _anchor, heroes in ROSTER:
        for hid, official in heroes:
            label = official or str(hid)
            display = roster_display_name(hid, official)
            rows = by_hero.get(hid, [])
            self_map: dict[int, int] = {}
            team_map: dict[int, int] = {}
            pair_map: dict[int, int] = {}
            self_order: list[int] = []
            team_order: list[int] = []
            pair_order: list[int] = []
            partners: list[str] = []
            season_bits: list[str] = []
            for s in rows:
                add_into(self_map, self_order, attr_value_map(self_raw(s.row)))
                add_into(team_map, team_order, max_star_team_map(s.row))
                if s.partner_id:
                    add_into(pair_map, pair_order, attr_value_map(s.row.get("suit_attr")))
                    partners.append(f"{s.partner_name}（{s.partner_id}）")
                season_parts = []
                if s.season_effect != "無":
                    season_parts.append(s.season_effect)
                if s.season_effect2 != "無":
                    season_parts.append(s.season_effect2)
                if season_parts:
                    bit = f"{s.name}：" + "、".join(season_parts)
                    if s.season != "無":
                        bit += f"（{s.season}）"
                    season_bits.append(bit)
            hero_sums.append(
                HeroSumRow(
                    hero_id=hid,
                    faction=faction,
                    hero_label=label,
                    hero_display=display,
                    count=len(rows),
                    self_text=format_sum_map(self_map, self_order, scope=label),
                    team_text=format_sum_map(team_map, team_order, scope=TEAM_SCOPE),
                    pair_text=format_sum_map(pair_map, pair_order),
                    pair_partners="、".join(partners) if partners else "無",
                    season_text="；".join(season_bits) if season_bits else "無",
                )
            )

    # --- verifications (must match handbook 15 third edition) ---
    elewen = next(s for s in collectable if s.skin_id == ELEWEN_ID)
    shark = next(s for s in collectable if s.skin_id == SHARK_ID)
    new_a = next(s for s in collectable if s.skin_id == PAIR_NEW_A)
    new_b = next(s for s in collectable if s.skin_id == PAIR_NEW_B)
    pair_new = next(p for p in pairs if {p.a_id, p.b_id} == {PAIR_NEW_A, PAIR_NEW_B})
    unused_suit_strings = []
    unused_suit_keys = []
    for key in ("hero_skin_suit_name_10", "hero_skin_suit_name_ym", "hero_skin_suit_name_11"):
        if has_key(key) and t(key) not in live_suit_names:
            unused_suit_strings.append(t(key))
            unused_suit_keys.append(key)

    verifications = {
        "collectable": len(collectable),
        "pairs": len(pairs),
        "suits": len(suits),
        "awaken": len(awaken),
        "nameless_300xx": len(nameless_raw),
        "no_skin": len(no_skin),
        "elewen_name": elewen.name,
        "elewen_collect": elewen.collect_text,
        "elewen_star_max": elewen.star_team_max,
        "shark_name": shark.name,
        "shark_collect": shark.collect_text,
        "shark_season": shark.season,
        "shark_season_effect2": shark.season_effect2,
        "new_a": f"{new_a.name}（{new_a.skin_id}）",
        "new_b": f"{new_b.name}（{new_b.skin_id}）",
        "new_pair_attr_a": new_a.pair_attr,
        "new_pair_attr_b": new_b.pair_attr,
        "pair_new": f"{pair_new.a_name}／{pair_new.b_name}",
        "unused_suit_strings": unused_suit_strings,
        "has_harvest_guard_string": any(
            "豐收護衛" in (t(k) or "") or k == "豐收護衛"
            for k in []  # checked separately below
        ),
    }

    # Confirm 豐收護衛 is not a live suit and is not pulled in.
    from .strings import load_strings

    harvest = [(k, v) for k, v in load_strings().items() if "豐收護衛" in str(v) or "豐收護衛" in str(k)]
    verifications["harvest_guard_hits"] = harvest
    verifications["live_suit_names"] = sorted(live_suit_names)
    # LocalLow 字串包可能有未引用的套裝名稱鍵；只要沒有進入活套裝名錄就不算失敗。

    expected_elewen = "聖徒 技能增傷+8.00%；全部 英雄攻擊+6.00%；全部 英雄生命+20.00%；全部 聯盟英雄減傷+2.00%"
    expected_shark_collect = "發明家 突破防禦+2000；全部 英雄攻擊+3.00%；全部 英雄生命+10.00%"
    expected_shark_eff2 = "黑潮來襲時扣除氧氣值減少+10.00%"
    errors = []
    if len(collectable) != 137:
        errors.append(f"collectable {len(collectable)} != 137")
    if len(pairs) != 9:
        errors.append(f"pairs {len(pairs)} != 9")
    if len(suits) != 10:
        errors.append(f"suits {len(suits)} != 10")
    if elewen.collect_text != expected_elewen:
        errors.append(f"elewen collect {elewen.collect_text!r} != {expected_elewen!r}")
    if elewen.star_team_max != "英雄攻擊+6.00%、英雄生命+20.00%、聯盟英雄減傷+2.00%":
        errors.append(f"elewen star {elewen.star_team_max!r}")
    if shark.collect_text != expected_shark_collect:
        errors.append(f"shark collect {shark.collect_text!r}")
    if shark.season != "僅在潮汐之怒賽季中生效":
        errors.append(f"shark season {shark.season!r}")
    if shark.season_effect2 != expected_shark_eff2:
        errors.append(f"shark effect2 {shark.season_effect2!r}")
    if "聖焰神衛" in live_suit_names:
        errors.append("聖焰神衛 must not appear as a live suit")
    if "幽冥使者" in live_suit_names:
        errors.append("幽冥使者 must not appear as a live suit")
    if "豐收護衛" in live_suit_names:
        errors.append("豐收護衛 must not be listed as a live suit")
    if new_a.name != "審判官·富饒領主" or new_b.name != "豪士·武道宗師":
        errors.append(f"new pair names {new_a.name} / {new_b.name}")
    if new_a.pair_attr != "紅水晶採集速度+20.00%" or new_b.pair_attr != "防禦+2000":
        errors.append(f"new pair attrs {new_a.pair_attr} / {new_b.pair_attr}")
    if new_a.can_up or new_b.can_up:
        errors.append("new pair skins must not be star-upgradable")

    expected_saint_self = "聖徒 暴擊+3.00%；聖徒 對召喚物傷害+10.00%；聖徒 必殺技係數+20.00%；聖徒 技能增傷+8.00%"
    expected_saint_team = "全部 英雄攻擊+21.00%；全部 英雄生命+70.00%；全部 聯盟英雄減傷+2.00%"
    expected_inventor_self = "發明家 突破防禦+2000；發明家 技能增傷+8.00%"
    expected_inventor_team = "全部 英雄攻擊+6.00%；全部 英雄生命+20.00%"
    saint_sum = next((r for r in hero_sums if r.hero_id == 10033), None)
    inventor_sum = next((r for r in hero_sums if r.hero_id == 10050), None)
    shepherd_sum = next((r for r in hero_sums if r.hero_id == 10029), None)
    boss_sum = next((r for r in hero_sums if r.hero_id == 10032), None)
    verifications["hero_sum_rows"] = len(hero_sums)
    verifications["hero_sum_total_skins"] = sum(r.count for r in hero_sums)
    verifications["saint_sum_count"] = saint_sum.count if saint_sum else None
    verifications["saint_sum_self"] = saint_sum.self_text if saint_sum else None
    verifications["saint_sum_team"] = saint_sum.team_text if saint_sum else None
    verifications["saint_sum_pair"] = saint_sum.pair_text if saint_sum else None
    verifications["saint_sum_season"] = saint_sum.season_text if saint_sum else None
    verifications["inventor_sum_self"] = inventor_sum.self_text if inventor_sum else None
    verifications["inventor_sum_team"] = inventor_sum.team_text if inventor_sum else None
    verifications["inventor_sum_season"] = inventor_sum.season_text if inventor_sum else None
    if len(hero_sums) != 57:
        errors.append(f"hero_sums {len(hero_sums)} != 57")
    if sum(r.count for r in hero_sums) != 137:
        errors.append(f"hero_sums skin count {sum(r.count for r in hero_sums)} != 137")
    roster_ids = [hid for _f, _a, heroes in ROSTER for hid, _n in heroes]
    if [r.hero_id for r in hero_sums] != roster_ids:
        errors.append("hero_sums order does not follow roster")
    if not saint_sum or saint_sum.count != 6:
        errors.append(f"saint sum count {saint_sum}")
    if not saint_sum or saint_sum.self_text != expected_saint_self:
        errors.append(f"saint self {getattr(saint_sum, 'self_text', None)!r}")
    if not saint_sum or saint_sum.team_text != expected_saint_team:
        errors.append(f"saint team {getattr(saint_sum, 'team_text', None)!r}")
    if saint_sum and saint_sum.pair_text != "無":
        errors.append(f"saint pair should be 無, got {saint_sum.pair_text!r}")
    if saint_sum and "對碎石巨像、暮光渡鴉的傷害提升+15.00%" not in (saint_sum.season_text or ""):
        errors.append(f"saint season missing 闇月 effect: {saint_sum.season_text!r}")
    if saint_sum and "對碎石巨像" in saint_sum.self_text + saint_sum.team_text:
        errors.append("saint season effect leaked into main sum")
    if not inventor_sum or inventor_sum.self_text != expected_inventor_self:
        errors.append(f"inventor self {getattr(inventor_sum, 'self_text', None)!r}")
    if not inventor_sum or inventor_sum.team_text != expected_inventor_team:
        errors.append(f"inventor team {getattr(inventor_sum, 'team_text', None)!r}")
    if inventor_sum and expected_shark_eff2 in (inventor_sum.self_text + inventor_sum.team_text):
        errors.append("shark season effect leaked into inventor main sum")
    if inventor_sum and expected_shark_eff2 not in (inventor_sum.season_text or ""):
        errors.append(f"inventor season missing shark effect: {inventor_sum.season_text!r}")
    if shepherd_sum is None or shepherd_sum.count != 0 or "未開放" not in shepherd_sum.hero_display:
        errors.append(f"shepherd sum {shepherd_sum}")
    if boss_sum is None or "未開放" in boss_sum.hero_display:
        errors.append(f"老闆娘 should not be marked 未開放: {boss_sum}")
    # 15032/15033/15039 must appear as their own rows
    for nid in (15032, 15033, 15039):
        row = next((r for r in hero_sums if r.hero_id == nid), None)
        if row is None or row.hero_display != str(nid) or row.hero_label != str(nid):
            errors.append(f"id-only hero {nid} missing or renamed: {row}")
    if errors:
        raise ValueError("skin table verification failed: " + "; ".join(errors))

    return TablesData(
        collectable=collectable,
        hero_sums=hero_sums,
        star_skins=star_skins,
        suits=suits,
        pairs=pairs,
        season_skins=season_skins,
        awaken=awaken,
        no_skin=no_skin,
        unnamed=unnamed,
        nameless=nameless_rows,
        groups=groups,
        unlock_counts=unlock_counts,
        coin_rows=coin_rows,
        voice_collectable=v_col,
        voice_awaken=v_awk,
        terms=terms,
        verifications=verifications,
        button_dec=t("hero_skin_button_2_dec") or "",
        fashion_name=t("goods_name_312") or "時裝幣",
        fashion_desc=t("goods_desc_312") or "",
        tab_book=t("hero_skin_suit_1") or "圖鑑",
        tab_suit=t("hero_skin_suit_2") or "造型套裝",
    )


def _voice_cell(flag: bool) -> str:
    return "有語音" if flag else "無語音"


def _star_cell(s: SkinRow) -> str:
    if s.can_up and s.star_max:
        return str(s.star_max)
    return "無"


def _join_suits(s: SkinRow) -> str:
    return "、".join(s.suit_names) if s.suit_names else "無"


def _pair_cell(s: SkinRow) -> str:
    if not s.partner_id:
        return "無"
    return f"{s.partner_name}（{s.partner_id}）"


def _quality(s: SkinRow) -> str:
    return str(s.quality) if s.quality is not None else "無"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    fashion = H(data.fashion_name, terms)

    t_group = table(
        ["組別", "筆數", "造型戰力", "說明"],
        [
            [H(g.label, terms), e(str(g.count)), e(g.add_power), e(g.note)]
            for g in data.groups
        ],
        mobile="cards",
    )
    t_unlock = table(
        ["說明原文", "全表筆數", "可收集造型"],
        [
            [H(text, terms) if text != "—" else e(text), e(str(n_all)), e(str(n_col))]
            for k, text, n_all, n_col in data.unlock_counts
        ],
        mobile="cards",
        card_title="字串",
    )
    t_coin = table(
        ["品質", "可收集筆數", "有時裝幣價（單價）", "無時裝幣價"],
        [[e(c) for c in row] for row in data.coin_rows],
    )

    collect_rows = []
    collect_ids = []
    for s in data.collectable:
        collect_ids.append(f"skin-{s.skin_id}")
        collect_rows.append([
            H(s.faction, terms),
            _hero_link_html(s.hero_id, s.hero_display, terms),
            H(s.name, terms),
            e(_quality(s)),
            e(s.coins),
            H(s.unlock, terms),
            H(s.collect_text, terms),
            e(_star_cell(s)),
            H(_pair_cell(s), terms),
            H(_join_suits(s), terms),
            H(s.season, terms) if s.season != "無" else "無",
            H(s.season_effect if s.season_effect != "無" else s.season_effect2, terms)
            if s.season_effect != "無" or s.season_effect2 != "無"
            else "無",
            e(_voice_cell(s.has_voice)),
        ])
    t_collect = table(
        [
            "陣營", "英雄", "造型", "品質", "時裝幣", "解鎖說明",
            "收集屬性（彈窗標籤；可升星寫滿星）", "升星上限", "成對造型", "收集套裝",
            "賽季說明", "賽季效果", "語音",
        ],
        collect_rows,
        row_ids=collect_ids,
        wrap_class="table-dense",
        mobile="cards",
    )

    star_rows = []
    for s in data.star_skins:
        star_rows.append([
            H(s.name, terms),
            _hero_link_html(s.hero_id, s.hero_label, terms),
            e(str(s.star_max or "無")),
            e(s.star_consume),
            e(s.star_goods),
            H(s.star_team_max, terms),
        ])
    t_star = table(
        ["造型", "英雄", "升星上限", "消耗個數", "道具編號", "滿星隊伍屬性（基礎＋最後一檔）"],
        star_rows,
        mobile="cards",
    )

    suit_rows = []
    for su in data.suits:
        members = "、".join(H(name, terms) if name else e(str(sid)) for sid, name in su.members)
        tiers = "<br>".join(
            f"{e(raw)}：{H(effect, terms)}" for raw, effect in su.tiers
        )
        extra = []
        if su.unlocktime != "無":
            extra.append(f"解鎖時間 {e(format_unlocktime(su.unlocktime) or su.unlocktime)}（只照錄，不用來標未開放）")
        suit_rows.append([
            H(su.name, terms),
            e(str(su.count)),
            e(str(su.quality) if su.quality is not None else "無"),
            e(su.need_raw),
            members,
            tiers,
            e(su.reward),
            "<br>".join(extra) if extra else "無",
        ])
    t_suit = table(
        ["套裝", "件數", "品質", "啟用條件", "成員", "各檔屬性（當前檔，不加總）", "獎勵原值", "備註"],
        suit_rows,
        wrap_class="table-dense",
        mobile="cards",
    )

    pair_rows = []
    for p in data.pairs:
        pair_rows.append([
            H(p.a_name, terms) if p.a_name else e(str(p.a_id)),
            _hero_link_html(p.a_hero_id, p.a_hero, terms),
            H(p.a_attr, terms),
            H(p.b_name, terms) if p.b_name else e(str(p.b_id)),
            _hero_link_html(p.b_hero_id, p.b_hero, terms),
            H(p.b_attr, terms),
        ])
    t_pair = table(
        ["造型 A", "英雄 A", "A 的成對屬性", "造型 B", "英雄 B", "B 的成對屬性"],
        pair_rows,
        mobile="cards",
    )

    season_rows = []
    for s in data.season_skins:
        season_rows.append([
            H(s.name, terms),
            _hero_link_html(s.hero_id, s.hero_label, terms),
            H(s.season, terms),
            e(s.season_no or "無"),
            H(s.season_effect, terms) if s.season_effect != "無" else "無",
            H(s.season_effect2, terms) if s.season_effect2 != "無" else "無",
        ])
    t_season = table(
        ["造型", "英雄", "賽季說明", "賽季欄（只照錄）", "賽季效果", "賽季效果二"],
        season_rows,
        mobile="cards",
    )

    awk_rows = []
    for s in data.awaken:
        awk_rows.append([
            H(s.faction, terms),
            _hero_link_html(s.hero_id, s.hero_display, terms),
            H(s.name, terms),
            e(str(s.skin_id)),
            e(str(s.row.get("skin_id") or "無")),
            e(_quality(s)),
            H(s.unlock, terms),
            e(_voice_cell(s.has_voice)),
        ])
    t_awaken = table(
        ["陣營", "英雄", "造型", "編號", "外觀編號", "品質", "解鎖說明", "語音"],
        awk_rows,
        mobile="cards",
    )

    noskin_rows = []
    for n in data.no_skin:
        noskin_rows.append([
            _hero_link_html(n.hero_id, n.hero_display, terms),
            e(str(n.hero_id)),
            H(n.faction, terms),
            e(_faction_source(n.hero_id, include_id=False)),
            e(n.default_note),
        ])
    t_noskin = table(
        ["英雄", "編號", "陣營", "陣營來源", "預設模型"],
        noskin_rows,
        mobile="cards",
    )

    unnamed_rows = []
    for s in data.unnamed:
        unnamed_rows.append([
            e(str(s.hero_id)),
            H(s.faction, terms),
            H(s.name, terms),
            e(str(s.skin_id)),
            e("覺醒" if _is_awaken(s.row) else "可收集"),
            e(_quality(s) if not _is_awaken(s.row) else "—"),
            e(s.coins if not _is_awaken(s.row) else "—"),
            H(s.unlock, terms),
            H(s.collect_text, terms) if not _is_awaken(s.row) else "無自身／隊伍屬性",
            e(_voice_cell(s.has_voice)),
        ])
    t_unnamed = table(
        ["編號", "陣營", "造型名稱（照官方名稱原樣）", "造型編號", "組別", "品質", "時裝幣", "解鎖說明", "收集屬性", "語音"],
        unnamed_rows,
        wrap_class="table-dense",
        mobile="cards",
    )

    nameless_rows = []
    for n in data.nameless:
        nameless_rows.append([
            e(str(n.hero_id)),
            e(str(n.count)),
            e("、".join(str(i) for i in n.skin_ids)),
            "<br>".join(e(x) for x in n.notes),
        ])
    t_nameless = table(
        ["編號", "筆數", "造型編號", "備註"],
        nameless_rows,
        wrap_class="table-dense",
        mobile="cards",
    )

    sum_rows = []
    sum_ids = []
    for r in data.hero_sums:
        sum_ids.append(f"sum-{r.hero_id}")
        pair_cell = H(r.pair_text, terms) if r.pair_text != "無" else "無"
        if r.pair_partners != "無":
            pair_cell += f"<br>{H('與' + r.pair_partners + '成對', terms)}"
        season_cell = H(r.season_text, terms).replace("；", "<br>") if r.season_text != "無" else "無"
        sum_rows.append([
            H(r.faction, terms),
            _hero_link_html(r.hero_id, r.hero_display, terms),
            e(str(r.count)),
            H(r.self_text, terms),
            H(r.team_text, terms),
            pair_cell,
            season_cell,
        ])
    t_hero_sum = table(
        ["陣營", "英雄", "可收集件數", "自身加總", "全部加總", "成對加總（不預設已啟動）", "賽季效果（未計入主要加總）"],
        sum_rows,
        row_ids=sum_ids,
        wrap_class="table-dense",
        mobile="cards",
    )

    n_col, n_pair, n_suit = len(data.collectable), len(data.pairs), len(data.suits)
    v_c_yes, v_c_no = data.voice_collectable
    v_a_yes, v_a_no = data.voice_awaken

    toc = toc_list([
        {"label": "簡介", "id": "lead"},
        {"label": "範圍、解鎖與時裝幣", "id": "scope"},
        {"label": "範圍與分組", "id": "scope-group", "depth": 1},
        {"label": "解鎖說明", "id": "scope-unlock", "depth": 1},
        {"label": "時裝幣與品質", "id": "scope-coin", "depth": 1},
        {"label": "表一、可收集造型總覽", "id": "t1"},
        {"label": "表一附、每位英雄所有可收集造型的屬性加總", "id": "t1-sum"},
        {"label": "表二、可升星造型", "id": "t2"},
        {"label": "表三、收集套裝", "id": "t3"},
        {"label": "表四、成對造型", "id": "t4"},
        {"label": "表五、賽季限定效果", "id": "t5"},
        {"label": "表六、覺醒造型", "id": "t6"},
        {"label": "表七、沒有造型圖鑑列的英雄", "id": "t7"},
        {"label": "表八、編號 15032／15033／15039 的造型", "id": "t8"},
        {"label": "附註：300xx 無名列", "id": "t9"},
        {"label": "資料說明", "id": "notes"},
    ])

    elewen = next(s for s in data.collectable if s.skin_id == ELEWEN_ID)
    shark = next(s for s in data.collectable if s.skin_id == SHARK_ID)
    new_a = next(s for s in data.collectable if s.skin_id == PAIR_NEW_A)
    new_b = next(s for s in data.collectable if s.skin_id == PAIR_NEW_B)
    saint_sum = next(r for r in data.hero_sums if r.hero_id == 10033)
    inventor_sum = next(r for r in data.hero_sums if r.hero_id == 10050)

    unlock_key_map = "、".join(
        f"{e(k)}＝{H(txt, terms) if txt != '—' else e(txt)}"
        for k, txt, _n_all, _n_col in data.unlock_counts
    )

    title = "Top Heroes Wiki｜造型總表"
    summary = (
        f"Top Heroes 造型總表：{n_col} 件可收集造型、{n_pair} 組成對、"
        f"{n_suit} 套收集套裝，以及可升星、賽季效果、覺醒列與每位英雄的屬性加總。"
    )

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">本頁列出英雄造型圖鑑的可收集造型、成對造型、收集套裝、可升星效果與賽季限定效果，以及每位英雄可收集造型的屬性加總。</p>
    </header>
    {toc}
    <section id="lead">
      <h2>簡介</h2>
      <p>介面字串寫：{H(data.button_dec, terms)}。圖鑑與造型套裝是分開的頁籤（{H(data.tab_book, terms)}、{H(data.tab_suit, terms)}）。本頁只收英雄造型圖鑑、造型套裝與語音，不收入部隊皮膚、城堡／世界皮膚、領主裝扮、聊天與社交皮膚。</p>
      <p>造型資料共 {e(str(sum(g.count for g in data.groups)))} 筆，分成可收集造型 {e(str(n_col))} 筆、覺醒造型 {e(str(len(data.awaken)))} 筆，以及尚無正式名稱的編號列 {e(str(sum(n.count for n in data.nameless)))} 筆。可收集造型另有 {e(str(n_pair))} 組成對、{e(str(n_suit))} 套收集套裝、{e(str(len(data.star_skins)))} 把可升星、{e(str(len(data.season_skins)))} 把寫了賽季說明。檔名與分欄見資料說明。</p>
      <p>造型的自身、隊伍、套裝、成對與賽季效果依類型顯示：百分比類寫成「屬性名+x.xx%」；點數類寫成加號，沒有百分號，也沒有千位分符（例如突破防禦+2000、出征上限+8、英雄等級上限+1）。可升星造型的隊伍顯示值＝基礎＋當前星檔（滿星用最後一檔）。套裝只取當前檔，不加總各檔。收集屬性彈窗上，自身欄用該英雄名稱、隊伍欄用「{H(TEAM_SCOPE, terms)}」；套裝範圍用語是「{H(SUIT_SCOPE_HERO, terms)}」與「{H(SUIT_SCOPE_ALL, terms)}」。這套規則只用於英雄造型，不套到專武、稱號、羈絆、英靈或天賦。換算方式見資料說明。</p>
      <p>排列依本站英雄目錄：聯盟 → 自然 → 部族（與首頁／手冊名單總覽相同）。{H("牧羊人", terms)}（10029）標為未開放；{H("老闆娘", terms)}不標未開放。不把時間或賽季欄位自行標成未開放。15032、15033、15039 只顯示編號，不編造中文名，也不與{H("老闆娘", terms)}、{H("聖徒", terms)}、{H("沙漠王子", terms)}合成同一人。官方連結只指向已公開的英雄條目，沒有另做造型詳情子頁。</p>
    </section>
    <section id="scope">
      <h2>範圍、解鎖與時裝幣</h2>
      <section id="scope-group">
        <h3>範圍與分組</h3>
        <p>兩層外觀不要混用。單位模型主表本身沒有時裝幣、隊伍屬性或造型戰力；造型圖鑑才是本頁要查的造型名錄。檔名對照見資料說明。</p>
        {t_group}
      </section>
      <section id="scope-unlock">
        <h3>解鎖說明</h3>
        <p>{fashion}說明：{H(data.fashion_desc, terms)}。</p>
        {t_unlock}
      </section>
      <section id="scope-coin">
        <h3>時裝幣與品質</h3>
        <p>可收集造型若有時裝幣價，依品質固定。品質欄只有 4、5、6 三個數值，收集套裝另有品質 7；表上沒有對應的品質名稱字串，只錄數字。可收集造型的造型戰力全是 5500，與品質無關。</p>
        {t_coin}
      </section>
    </section>
    <section id="t1">
      <h2>表一、可收集造型總覽</h2>
      <p>共 {e(str(n_col))} 件。收集屬性依彈窗標籤書寫：自身欄用英雄名，隊伍欄用「{H(TEAM_SCOPE, terms)}」。可升星造型的隊伍欄是滿星顯示值（基礎＋最後一檔）；0 星、較低星不在本表逐列展開，見表二。賽季說明與賽季效果分欄，前者不一定出現在收集屬性彈窗。以{H(elewen.name, terms)}為例，滿星收集屬性為「{H(elewen.collect_text, terms)}」。以{H(shark.name, terms)}為例，收集屬性為「{H(shark.collect_text, terms)}」，彈窗另列出「{H(shark.season_effect2, terms)}」；「{H(shark.season, terms)}」是表上的賽季說明，該句未出現在這張彈窗。2026-11-22 抽出新增的{H(new_a.name, terms)}與{H(new_b.name, terms)}已收入本表，見表四。編號對照見資料說明。</p>
      <p class="jump-nav">跳到：<a href="#skin-{data.collectable[0].skin_id}">表首</a>
      {' '.join(f'<a href="#skin-{next(s for s in data.collectable if s.faction==fac).skin_id}">{e(fac)}</a>' for fac in ("聯盟", "自然", "部族") if any(s.faction==fac for s in data.collectable))}
      <a href="#skin-{ELEWEN_ID}">{e(elewen.name)}</a>
      <a href="#skin-{SHARK_ID}">{e(shark.name)}</a>
      <a href="#skin-{PAIR_NEW_A}">{e(new_a.name)}</a>
      <a href="#skin-{PAIR_NEW_B}">{e(new_b.name)}</a></p>
      {t_collect}
    </section>
    <section id="t1-sum">
      <h2>表一附、每位英雄所有可收集造型的屬性加總</h2>
      <p>這張表把同一位英雄的所有可收集造型，依屬性把顯示值的原值相加，再依同一套類型規則書寫。百分比是數字相加（例如 3.00%＋6.00%＝9.00%），不是乘算。這不是遊戲面板上的單一數字，只是把表一的收集屬性加起來方便對照。可升星造型用滿星顯示值（隊伍屬性基礎＋最後一檔），與表一、表二相同。覺醒造型沒有自身／隊伍屬性，不算進件數，也不加進總數。</p>
      <p>「自身加總」與「全部加總」是主要加總，分欄書寫：自身欄用英雄名，隊伍欄用「{H(TEAM_SCOPE, terms)}」。成對屬性另欄列出；成對效果何時啟動，表上沒有另寫說明，對方也可能是別的英雄，本欄不預設已啟動，也不計入自身／全部加總。賽季效果另欄列出，賽季說明不當屬性加，也不計入主要加總。收集套裝要湊數件造型，不是單一英雄自己的造型加總，因此不算進本表。</p>
      <p>共 {e(str(len(data.hero_sums)))} 人，排列依本站英雄目錄：聯盟 → 自然 → 部族，不依加總排序。沒有可收集造型的件數為 0，加總欄寫「無」。以{H("聖徒", terms)}（10033）為例，6 件可收集造型（含{H(elewen.name, terms)}滿星）自身加總為「{H(saint_sum.self_text, terms)}」，全部加總為「{H(saint_sum.team_text, terms)}」。以{H("發明家", terms)}為例，{H(shark.name, terms)}的「{H(shark.season_effect2, terms)}」只出現在賽季效果欄，沒有加進自身／全部加總。</p>
      <p class="jump-nav">跳到：
      {' '.join(f'<a href="#sum-{next(r for r in data.hero_sums if r.faction==fac).hero_id}">{e(fac)}</a>' for fac in ("聯盟", "自然", "部族"))}
      <a href="#sum-10033">{e("聖徒")}</a>
      <a href="#sum-10050">{e("發明家")}</a></p>
      {t_hero_sum}
    </section>
    <section id="t2">
      <h2>表二、可升星造型</h2>
      <p>共 {e(str(len(data.star_skins)))} 把，全是品質 6 的可收集造型。隊伍顯示值＝隊伍屬性基礎＋當前星檔；沒有基礎的分營屬性只取星檔。滿星用最後一檔。升星消耗道具在字串表沒有名稱，本表只錄道具編號。名錄與本表的隊伍欄只寫滿星，不把 0 星、較低星再寫一遍。</p>
      {t_star}
    </section>
    <section id="t3">
      <h2>表三、收集套裝</h2>
      <p>共 {e(str(n_suit))} 套。啟用條件照錄（例如 {e("4|0,6|0")}）。介面字串有「{H(t("hero_skin_suit_3") or "收集{0}件套裝", terms)}」與「{H(t("hero_skin_suit_4") or "{0}件套裝達到{1}星", terms)}」。各檔屬性只寫<strong>該檔</strong>原值換算，不加總前面各檔；範圍用語是「{H(SUIT_SCOPE_HERO, terms)}」與「{H(SUIT_SCOPE_ALL, terms)}」。字串表另有「幽冥使者」「聖焰神衛」，沒有出現在這 {e(str(n_suit))} 套的名稱欄，不收入名錄。</p>
      {t_suit}
    </section>
    <section id="t4">
      <h2>表四、成對造型</h2>
      <p>另外，造型圖鑑有 {e(str(n_pair * 2))} 筆互相成對（{e(str(n_pair))} 對）。成對欄寫的是另一把造型的編號，不是上面那 {e(str(n_suit))} 套的套裝編號。成對雙方各帶一個成對屬性，同樣依類型書寫。這是成對機制，和收集套裝是分開的欄位。成對效果何時啟動，表上沒有另寫說明，本頁不自行推斷。</p>
      {t_pair}
    </section>
    <section id="t5">
      <h2>表五、賽季限定效果</h2>
      <p>共 {e(str(len(data.season_skins)))} 把可收集造型有賽季欄或賽季說明。賽季效果若在屬性表，依同一套類型規則改寫顯示。賽季欄的數字與賽季說明不一定同號，不自行對成第幾賽季日曆。官方另有「賽季屬性只在對應賽季生效」等說明，本頁不自行把這一欄對成臨時擁有或臨時使用。</p>
      {t_season}
    </section>
    <section id="t6">
      <h2>表六、覺醒造型</h2>
      <p>共 {e(str(len(data.awaken)))} 筆，解鎖說明都是「英雄覺醒獲得」，沒有時裝幣價，也沒有自身／隊伍屬性。{e(str(v_a_yes))} 筆有語音、{e(str(v_a_no))} 筆沒有。尋路者、石匠只有覺醒造型，沒有可收集列，因此只出現在本表。15032／15033／15039 的覺醒列見表八，名稱仍照官方造型名原樣登錄。</p>
      {t_awaken}
    </section>
    <section id="t7">
      <h2>表七、沒有造型圖鑑列的英雄</h2>
      <p>下列 {e(str(len(data.no_skin)))} 人在造型圖鑑沒有列，但單位模型表都有與英雄編號相同的預設模型。{H("大冒險家", terms)}有專武，造型表仍沒有他的列；這裡不標未開放。只把{H("牧羊人", terms)}標成未開放。</p>
      {t_noskin}
    </section>
    <section id="t8">
      <h2>表八、編號 15032／15033／15039 的造型</h2>
      <p>這三筆在英雄名錄，字串表沒有這三個編號的英雄名，本頁不編造中文名。造型名稱仍照官方造型名登錄。不把他們與{H("老闆娘", terms)}、{H("聖徒", terms)}、{H("沙漠王子", terms)}合成同一人，也不標未開放。客戶端是合併顯示還是兩套並行，表上沒寫死。</p>
      {t_unnamed}
      <p>說明：15032 的可收集列編號是 1003202，{H("老闆娘", terms)}（10032）的可收集列編號是 1503202，兩筆名稱都是「{H("老闆娘·指揮家", terms)}」，屬性與時裝幣價相同。15033 的「{H("聖徒·闇月", terms)}」（編號 1503302）沒有自身屬性，也沒有賽季說明；10033 的同名列有暴擊+3.00%，並寫「僅在暮光之戰賽季中生效」。15033 的「{H("聖徒·大廚", terms)}」（編號 1503303）隊伍屬性只有英雄攻擊+3.00%；10033 的同名列是英雄攻擊+3.00%、英雄生命+10.00%。15039 的「{H("沙漠王子·鬼武者", terms)}」（編號 1503902）隊伍屬性只有英雄生命+10.00%；10039 的同名列是英雄攻擊+3.00%、英雄生命+10.00%。這三筆重複列都沒有時裝幣價，外觀編號都不在單位模型表。</p>
    </section>
    <section id="t9">
      <h2>附註：300xx 無名列</h2>
      <p>共 {e(str(sum(n.count for n in data.nameless)))} 筆、{e(str(len(data.nameless)))} 個編號，皆不在英雄名錄，沒有英雄名或造型名字串，也沒有解鎖說明，沒有隊伍／自身屬性，造型戰力為 0，皆非覺醒。這些列是不是內部或關卡用角色，表上沒有名稱可證實，本頁不編造名稱。「模型名稱」是單位模型那一列的名稱，不是造型圖鑑的造型名。</p>
      {t_nameless}
    </section>
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>以下是整理用註記，查造型名稱與效果可略過。</li>
        <li>兩層外觀：單位模型主表是 <code>skin.json</code>，本身沒有時裝幣、隊伍屬性或造型戰力；造型圖鑑是 <code>hero_skin.json</code>。表七「有預設模型（名稱，頭像 Head_編號）」對應 <code>skin.json</code> 中與英雄編號相同的列，名稱鍵是 <code>hero_name_{{id}}</code>。無名列的模型名稱同樣取自 <code>skin.json</code>，不是造型圖鑑的造型名。</li>
        <li>解鎖說明可見表只列原文。鍵名對照：{unlock_key_map}。</li>
        <li>可見表標題對照：造型戰力原名 <code>add_power</code>；升星上限原名 <code>star_max</code>；成對屬性原名 <code>suit_attr</code>；賽季欄／賽季效果／賽季效果二原名 <code>season</code>、<code>season_effect</code>、<code>season_effect2</code>；賽季說明原名 <code>season_dec</code>；可見成對造型表不再在官方造型名後附加編號，改寫官方造型名；編號對照見此。可見套裝表成員欄不再在官方造型名後附加造型編號，改寫官方造型名；編號對照見此。可見可收集造型總覽表不再寫編號欄，改寫官方造型名；編號對照見此。可見表一說明不再在官方造型名後附加括號編號，改寫官方造型名；編號對照見此。外觀編號原名 <code>skin_id</code>；獎勵原值原名 <code>reward</code>；啟用條件原名 <code>suit_star_need</code>（例如 <code>4|0,6|0</code>）。成對欄原名 <code>hero_skin.suit</code>，寫的是另一把造型的 id，不是收集套裝 id。陣營來源「榮譽加成鏈」的組編號原名 <code>honor_group</code>；無陣營加成那筆是 <code>honor_group</code> 301。可見榮譽加成鏈只寫官方屬性名，編號見此：聯盟英雄攻擊 3103、聯盟英雄生命 3104、部族英雄攻擊 4103、部族英雄生命 4104、自然英雄攻擊 5103、自然英雄生命 5104。</li>
        <li>解鎖時間若是兩段日期，可見表寫成「A 至 B」；原值是 <code>A|B</code>，欄位原名 <code>unlocktime</code>。不把 <code>unlock_season</code>、<code>season</code> 或 <code>season_dec</code> 對成第幾賽季日曆，也不對成臨時擁有或臨時使用。</li>
        <li>本頁只收 {e("hero_skin")}／{e("hero_skin_suit")}／{e("hero_skin_voice")}。分組依戰力欄 {e("add_power")}。百分比類是 {e("show_type")}=2（原值÷100）；點數類是 {e("show_type")}=1。可升星造型的隊伍顯示值＝{e("team_attr")} 基礎＋當前星檔。不把 {e("unlock_season")}、{e("unlock_server")} 或 {e("unlocktime")} 自行標成未開放。</li>
        <li>資料出自遊戲資料表與官方字串（{e("hero_skin")}、{e("hero_skin_suit")}、{e("hero_skin_voice")}、{e("skin")}、{e("hero_detail")}、{e("attribute")}、{e("strings_zh.json")}），資料截至 {SKIN_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {e(SKIN_DATA_PACK)}（759 張表），打包時戳 {SKIN_DATA_PACKED}（香港時間）。顯示規則依攻略手冊「英雄造型圖鑑」第四版。第四版截稿已改對同一 live LocalLow 包。live 另有欄位序號殘件 <code>hero.json</code>（各列 <code>id</code> 皆為 0），不能當英雄名冊用。這不是官方 wiki。</li>
        <li>名稱、解鎖說明、賽季說明與介面標籤都照官方字串原樣引，包括「{H("占星學士·黑珍珠", terms)}」（英雄是{H("觀星學士", terms)}）、「{H("通靈者·威爾", terms)}」（英雄是{H("通靈師", terms)}）、「{H("喚潮使・海洋公主", terms)}」、「{H("主教‧八岐", terms)}」、「{H("樹人·聖誕", terms)}」等中點與用字。15033／15039 覺醒列名稱為「{H("沙漠王子·覺醒", terms)}」，照錄。</li>
        <li>屬性 3、4 的 {e("name")} 欄指向 {e("attribute_name_103")}／{e("attribute_name_104")}，但 {e("attribute_name_3")} 是「攻擊」、{e("attribute_name_4")} 是「生命值」，{e("show_type")} 為 1。本表實際用到的隊伍屬性是 103／104（英雄攻擊／英雄生命）。</li>
        <li>本頁出現的點數屬性是突破防禦（64）、成對欄位的防禦（22）、出征上限（1019）與英雄等級上限（1098）；其餘本頁出現的自身／隊伍／套裝英雄屬性，以及成對的「紅水晶採集速度」（1006），{e("show_type")} 皆為 2。賽季效果裡的點數屬性同樣寫成點數。</li>
        <li>以{H(elewen.name, terms)}、{H(shark.name, terms)}、馴龍高手聯名、怪奇物語、不朽王座核對累加與不加總。這套顯示規則只用於本頁英雄造型。</li>
        <li>本頁數值仍讀 {e("team_attr")}、{e("attr1")}／{e("attr2")}、{e("suit_attr")}、{e("suit_star_need")}、{e("attibute_*")}、{e("suit_hero_attibute_*")} 等既有欄，不改讀 {e("AttrListDic")}。LocalLow 包裡，13 把可升星造型的 {e("AttrListDic")} 與 {e("team_attr_1")} 起各星檔是同一套數值的另一種序列化（按星列出增量，不含 {e("team_attr")} 基礎，也不含自身屬性）；10 套收集套裝的 {e("AttrListDic")}、{e("AttrActiveNeeds")} 則對應各檔當前屬性與啟用條件，並帶範圍鍵 {e("hero_skin_suit_12")}／{e("hero_skin_suit_13")}（套裝英雄／全英雄）。與既有欄核對後數值一致，沒有多出其他屬性。本頁不把 {e("AttrListDic")} 單獨當成滿星或套裝加總值來用。</li>
        <li>不把 {e("unlock_season")}、{e("unlocktime")} 或 {e("season")} 自行標成未開放，也不自行對成 S1／S2。字串包有「聖焰神衛」「幽冥使者」但未被這 {e(str(n_suit))} 套引用，不收入名錄。</li>
        <li>表一附的屬性加總，是把同一英雄各件可收集造型的顯示值依屬性 id 把原值相加，再依 {e("show_type")} 書寫；百分比是數字相加，不是乘算。這不是遊戲面板上的單一數字。成對屬性與賽季效果另欄，不計入自身／全部加總；收集套裝要湊數件造型，也不算進每位英雄這一行。本頁不依加總排序，也不評定誰比較強。</li>
        <li>{e("repeat_reward_1")} 類型 999 在表上沒有名稱，本頁不自行斷定。沒有時裝幣價的可收集造型，取得途徑只寫在解鎖說明，沒有完整來源表。本頁沒有社群備註，也沒有把猜測寫進正文，也不評定造型強弱。</li>
      </ul>
    </section>
    """

    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    html = html.replace(
        f"<p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
        f"<p>資料截至 {SKIN_DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>",
    )
    return html


def render_skin_page(data: TablesData | None = None) -> str:
    """Public 造型總表 HTML for docs/skins.html. No unpublished banner."""
    return render_html(data or load_tables_data())


# ---------------------------------------------------------------------------
# Markdown（方便手機上看）
# ---------------------------------------------------------------------------

def render_markdown(data: TablesData) -> str:
    lines: list[str] = []
    add = lines.append
    n_col, n_pair, n_suit = len(data.collectable), len(data.pairs), len(data.suits)
    elewen = next(s for s in data.collectable if s.skin_id == ELEWEN_ID)
    shark = next(s for s in data.collectable if s.skin_id == SHARK_ID)
    new_a = next(s for s in data.collectable if s.skin_id == PAIR_NEW_A)
    new_b = next(s for s in data.collectable if s.skin_id == PAIR_NEW_B)
    saint_sum = next(r for r in data.hero_sums if r.hero_id == 10033)
    inventor_sum = next(r for r in data.hero_sums if r.hero_id == 10050)
    v_c_yes, v_c_no = data.voice_collectable
    v_a_yes, v_a_no = data.voice_awaken

    add("# Top Heroes Wiki｜造型總表（本機預覽）")
    add("")
    add("**本機預覽，尚未發佈。** 這不是線上目錄，也不會寫進公開站。")
    add("")
    add(f"資料截至 {SKIN_DATA_CUTOFF}（香港時間）。這不是官方 wiki。來源是 LocalLow 包 {SKIN_DATA_PACK}（759 張表），打包時戳 {SKIN_DATA_PACKED}（香港時間）。顯示規則依攻略手冊「英雄造型圖鑑」第四版。第四版截稿已改對同一 live LocalLow 包。live 另有欄位序號殘件 `hero.json`（各列 `id` 皆為 0），不能當英雄名冊用。")
    add("")
    add("## 簡介")
    add("")
    add(f"介面字串寫：{data.button_dec}。圖鑑與造型套裝是分開的頁籤（{data.tab_book}、{data.tab_suit}）。本頁只收 hero_skin／hero_skin_suit／hero_skin_voice，不收入部隊皮膚、城堡／世界皮膚、領主裝扮、聊天與社交皮膚。")
    add("")
    add(
        f"造型資料共 {sum(g.count for g in data.groups)} 筆，分成可收集造型 {n_col} 筆、"
        f"覺醒造型 {len(data.awaken)} 筆、300xx 列 {sum(n.count for n in data.nameless)} 筆。"
        f"可收集造型另有 {n_pair} 組成對、{n_suit} 套收集套裝、{len(data.star_skins)} 把可升星、{len(data.season_skins)} 把寫了賽季說明。"
    )
    add("")
    add(
        "造型的自身、隊伍、套裝、成對與賽季效果依屬性類型顯示：show_type=2 把原值÷100，寫成「屬性名+x.xx%」；"
        "show_type=1 寫成點數加號，沒有百分號，也沒有千位分符（例如突破防禦+2000、出征上限+8、英雄等級上限+1）。"
        "可升星造型的隊伍顯示值＝隊伍屬性基礎＋當前星檔（滿星用最後一檔）。套裝只取當前檔，不加總各檔。"
        f"收集屬性彈窗上，自身欄用該英雄名稱、隊伍欄用「{TEAM_SCOPE}」；套裝範圍用語是「{SUIT_SCOPE_HERO}」與「{SUIT_SCOPE_ALL}」。"
        "這套規則只用於英雄造型，不套到專武、稱號、羈絆、英靈或天賦。"
    )
    add("")
    add(
        "排列依本站英雄目錄：聯盟 → 自然 → 部族（與首頁／手冊名單總覽相同）。"
        "牧羊人（10029）標為未開放；老闆娘不標未開放。不把 unlock_season、unlock_server 或 unlocktime 自行標成未開放。"
        "15032、15033、15039 只顯示編號，不編造中文名，也不與老闆娘、聖徒、沙漠王子合成同一人。"
        "官方連結只指向已公開的英雄條目，沒有另做造型詳情子頁。"
    )
    add("")
    add("## 範圍、解鎖與時裝幣")
    add("")
    add("### 範圍與分組")
    add("")
    add("兩層外觀不要混用。單位模型主表本身沒有時裝幣、隊伍屬性或造型戰力；造型圖鑑才是本頁要查的造型名錄。檔名對照見資料說明。")
    add("")
    add(md_table(
        ["組別", "筆數", "造型戰力", "說明"],
        [[g.label, str(g.count), g.add_power, g.note] for g in data.groups],
    ))
    add("")
    add("### 解鎖說明")
    add("")
    add(f"{data.fashion_name}（物品 {FASHION_ITEM}）說明：{data.fashion_desc}。")
    add("")
    add(md_table(
        ["說明原文", "全表筆數", "可收集造型"],
        [[text, str(n_all), str(n_col)] for k, text, n_all, n_col in data.unlock_counts],
    ))
    add("")
    add("### 時裝幣與品質")
    add("")
    add("可收集造型若有時裝幣價，依品質固定。品質欄只有 4、5、6 三個數值，收集套裝另有品質 7；表上沒有對應的品質名稱字串，只錄數字。可收集造型的造型戰力全是 5500，與品質無關。")
    add("")
    add(md_table(
        ["品質", "可收集筆數", "有時裝幣價（單價）", "無時裝幣價"],
        data.coin_rows,
    ))
    add("")
    add("## 表一、可收集造型總覽")
    add("")
    add(
        f"共 {n_col} 件。下列依英雄分列，方便手機閱讀；欄位與 HTML 總表相同。"
        f"收集屬性依彈窗標籤書寫：自身欄用英雄名，隊伍欄用「{TEAM_SCOPE}」。"
        "可升星造型的隊伍欄是滿星顯示值。賽季說明與賽季效果分寫，前者不一定出現在收集屬性彈窗。"
    )
    add("")
    add(
        f"以{elewen.name}（{ELEWEN_ID}）為例，滿星收集屬性為「{elewen.collect_text}」。"
        f"以{shark.name}（{SHARK_ID}）為例，收集屬性為「{shark.collect_text}」，彈窗另列出「{shark.season_effect2}」；"
        f"「{shark.season}」是表上的賽季說明，該句未出現在這張彈窗。"
        f"2026-11-22 抽出新增的{new_a.name}（{PAIR_NEW_A}）與{new_b.name}（{PAIR_NEW_B}）已收入本表，見表四。"
    )
    add("")
    current_fac = None
    current_hero = None
    for s in data.collectable:
        if s.faction != current_fac:
            current_fac = s.faction
            current_hero = None
            add(f"### {current_fac}")
            add("")
        if s.hero_id != current_hero:
            current_hero = s.hero_id
            add(f"#### {_hero_link_md(s.hero_id, s.hero_display)}（{s.hero_id}，{s.faction}）")
            add("")
        bits = [
            f"品質 {s.quality}" if s.quality is not None else "品質 無",
            f"時裝幣 {s.coins}",
            s.unlock,
        ]
        if s.can_up and s.star_max:
            bits.append(f"可升星至 {s.star_max}")
        bits.append(s.collect_text)
        if s.partner_id:
            bits.append(f"成對 {_pair_cell(s)}，成對屬性 {s.pair_attr}")
        if s.suit_names:
            bits.append("收集套裝 " + "、".join(s.suit_names))
        if s.season != "無":
            bits.append(s.season)
        if s.season_effect != "無":
            bits.append(s.season_effect)
        if s.season_effect2 != "無":
            bits.append(s.season_effect2)
        bits.append(_voice_cell(s.has_voice))
        add(f"- {s.name}（id {s.skin_id}）：" + "；".join(bits))
    add("")
    add("## 表一附、每位英雄所有可收集造型的屬性加總")
    add("")
    add(
        "這張表把同一位英雄的所有可收集造型，依屬性 id 把顯示值的原值相加，再依同一套類型規則書寫。"
        "百分比是數字相加（例如 3.00%＋6.00%＝9.00%），不是乘算。這不是遊戲面板上的單一數字，只是把表一的收集屬性加起來方便對照。"
        "可升星造型用滿星顯示值（隊伍屬性基礎＋最後一檔），與表一、表二相同。覺醒造型沒有自身／隊伍屬性，不算進件數，也不加進總數。"
    )
    add("")
    add(
        f"「自身加總」與「全部加總」是主要加總，分欄書寫：自身欄用英雄名，隊伍欄用「{TEAM_SCOPE}」。"
        "成對屬性另欄列出；成對效果何時啟動，表上沒有另寫說明，對方也可能是別的英雄，本欄不預設已啟動，也不計入自身／全部加總。"
        "賽季效果另欄列出，賽季說明不當屬性加，也不計入主要加總。"
        "收集套裝要湊數件造型，不是單一英雄自己的造型加總，因此不算進本表。"
    )
    add("")
    add(
        f"共 {len(data.hero_sums)} 人，排列依本站英雄目錄：聯盟 → 自然 → 部族，不依加總排序。沒有可收集造型的件數為 0，加總欄寫「無」。"
        f"以聖徒（10033）為例，6 件可收集造型（含{elewen.name}滿星）自身加總為「{saint_sum.self_text}」，全部加總為「{saint_sum.team_text}」。"
        f"以發明家為例，{shark.name}的「{shark.season_effect2}」只出現在賽季效果欄，沒有加進自身／全部加總。"
    )
    add("")
    current_fac = None
    for r in data.hero_sums:
        if r.faction != current_fac:
            current_fac = r.faction
            add(f"### {current_fac}")
            add("")
        pair_cell = r.pair_text if r.pair_text != "無" else "無"
        if r.pair_partners != "無":
            pair_cell = pair_cell + f"；與{r.pair_partners}成對"
        add(f"#### {_hero_link_md(r.hero_id, r.hero_display)}（{r.hero_id}，{r.faction}）")
        add("")
        add(f"- 可收集件數：{r.count}")
        add(f"- 自身加總：{r.self_text}")
        add(f"- 全部加總：{r.team_text}")
        add(f"- 成對加總（不預設已啟動）：{pair_cell}")
        add(f"- 賽季效果（未計入主要加總）：{r.season_text}")
        add("")
    add("## 表二、可升星造型")
    add("")
    add(f"共 {len(data.star_skins)} 把，全是品質 6 的可收集造型。隊伍顯示值＝隊伍屬性基礎＋當前星檔；沒有基礎的分營屬性只取星檔。滿星用最後一檔。升星消耗道具在字串表沒有名稱，本表只錄道具 id。")
    add("")
    add(md_table(
        ["造型", "英雄", "升星上限", "消耗個數", "道具編號", "滿星隊伍屬性（基礎＋最後一檔）"],
        [
            [s.name, _hero_link_md(s.hero_id, s.hero_label), str(s.star_max or "無"), s.star_consume, s.star_goods, s.star_team_max]
            for s in data.star_skins
        ],
    ))
    add("")
    add("## 表三、收集套裝")
    add("")
    add(
        f"共 {n_suit} 套。啟用條件照錄（例如 4|0,6|0）。各檔屬性只寫該檔原值換算，不加總前面各檔；"
        f"範圍用語是「{SUIT_SCOPE_HERO}」與「{SUIT_SCOPE_ALL}」。"
        f"字串表另有「幽冥使者」「聖焰神衛」，沒有出現在這 {n_suit} 套的 name 欄，不收入名錄。"
    )
    add("")
    suit_md = []
    for su in data.suits:
        members = "、".join(f"{name}（{sid}）" for sid, name in su.members)
        tiers = "；".join(f"{raw}：{effect}" for raw, effect in su.tiers)
        note = f"解鎖時間 {format_unlocktime(su.unlocktime) or su.unlocktime}（只照錄，不用來標未開放）" if su.unlocktime != "無" else "無"
        suit_md.append([
            su.name,
            str(su.count),
            str(su.quality) if su.quality is not None else "無",
            su.need_raw,
            members,
            tiers,
            su.reward,
            note,
        ])
    add(md_table(
        ["套裝", "件數", "品質", "啟用條件", "成員（造型編號）", "各檔屬性（當前檔，不加總）", "獎勵原值", "備註"],
        suit_md,
    ))
    add("")
    add("## 表四、成對造型")
    add("")
    add(
        f"另外，造型圖鑑有 {n_pair * 2} 筆互相成對（{n_pair} 對）。成對欄寫的是另一把造型的編號，不是上面那 {n_suit} 套的套裝編號。"
        "成對雙方各帶一個成對屬性，同樣依類型書寫。這是成對機制，和收集套裝是分開的欄位。成對效果何時啟動，表上沒有另寫說明，本頁不自行推斷。"
    )
    add("")
    add(md_table(
        ["造型 A", "英雄 A", "A 的成對屬性", "造型 B", "英雄 B", "B 的成對屬性"],
        [
            [
                f"{p.a_name}（{p.a_id}）",
                _hero_link_md(p.a_hero_id, p.a_hero),
                p.a_attr,
                f"{p.b_name}（{p.b_id}）",
                _hero_link_md(p.b_hero_id, p.b_hero),
                p.b_attr,
            ]
            for p in data.pairs
        ],
    ))
    add("")
    add("## 表五、賽季限定效果")
    add("")
    add(
        f"共 {len(data.season_skins)} 把可收集造型有賽季欄或賽季說明。賽季效果若在屬性表，依同一套類型規則改寫顯示。"
        "賽季欄的數字與賽季說明不一定同號，不自行對成第幾賽季日曆。本頁不自行把這一欄對成臨時擁有或臨時使用。"
    )
    add("")
    add(md_table(
        ["造型", "英雄", "賽季說明", "賽季欄（只照錄）", "賽季效果", "賽季效果二"],
        [
            [s.name, _hero_link_md(s.hero_id, s.hero_label), s.season, s.season_no or "無", s.season_effect, s.season_effect2]
            for s in data.season_skins
        ],
    ))
    add("")
    add("## 表六、覺醒造型")
    add("")
    add(
        f"共 {len(data.awaken)} 筆，解鎖說明都是「英雄覺醒獲得」，沒有時裝幣價，也沒有自身／隊伍屬性。"
        f"{v_a_yes} 筆有語音、{v_a_no} 筆沒有。尋路者、石匠只有覺醒造型，沒有可收集列，因此只出現在本表。"
        "15032／15033／15039 的覺醒列見表八，名稱仍照官方造型名原樣登錄。"
    )
    add("")
    add(md_table(
        ["陣營", "英雄", "造型", "編號", "外觀編號", "品質", "解鎖說明", "語音"],
        [
            [
                s.faction,
                _hero_link_md(s.hero_id, s.hero_display),
                s.name,
                str(s.skin_id),
                str(s.row.get("skin_id") or "無"),
                _quality(s),
                s.unlock,
                _voice_cell(s.has_voice),
            ]
            for s in data.awaken
        ],
    ))
    add("")
    add("## 表七、沒有造型圖鑑列的英雄")
    add("")
    add(
        f"下列 {len(data.no_skin)} 人在造型圖鑑沒有列，但單位模型表都有與英雄編號相同的預設模型。"
        "大冒險家有專武，造型表仍沒有他的列；這裡不標未開放。只把牧羊人標成未開放。"
    )
    add("")
    add(md_table(
        ["英雄", "編號", "陣營", "陣營來源", "預設模型"],
        [
            [_hero_link_md(n.hero_id, n.hero_display), str(n.hero_id), n.faction, n.source, n.default_note]
            for n in data.no_skin
        ],
    ))
    add("")
    add("## 表八、編號 15032／15033／15039 的造型")
    add("")
    add(
        "這三筆在英雄名錄，字串表沒有這三個編號的英雄名，本頁不編造中文名。"
        "造型名稱仍照官方造型名登錄。不把他們與老闆娘、聖徒、沙漠王子合成同一人，也不標未開放。"
        "客戶端是合併顯示還是兩套並行，表上沒寫死。"
    )
    add("")
    add(md_table(
        ["編號", "陣營", "造型名稱（照官方名稱原樣）", "造型編號", "組別", "品質", "時裝幣", "解鎖說明", "收集屬性", "語音"],
        [
            [
                str(s.hero_id),
                s.faction,
                s.name,
                str(s.skin_id),
                "覺醒" if _is_awaken(s.row) else "可收集",
                _quality(s) if not _is_awaken(s.row) else "—",
                s.coins if not _is_awaken(s.row) else "—",
                s.unlock,
                s.collect_text if not _is_awaken(s.row) else "無自身／隊伍屬性",
                _voice_cell(s.has_voice),
            ]
            for s in data.unnamed
        ],
    ))
    add("")
    add(
        "說明：15032 的可收集列編號是 1003202，老闆娘（10032）的可收集列編號是 1503202，兩筆名稱都是「老闆娘·指揮家」，屬性與時裝幣價相同。"
        "15033 的「聖徒·闇月」（id 1503302）沒有自身屬性，也沒有賽季說明；10033 的同名列有暴擊+3.00%，並寫「僅在暮光之戰賽季中生效」。"
        "15033 的「聖徒·大廚」（id 1503303）隊伍屬性只有英雄攻擊+3.00%；10033 的同名列是英雄攻擊+3.00%、英雄生命+10.00%。"
        "15039 的「沙漠王子·鬼武者」（id 1503902）隊伍屬性只有英雄生命+10.00%；10039 的同名列是英雄攻擊+3.00%、英雄生命+10.00%。"
        "這三筆重複列都沒有時裝幣價，外觀編號都不在單位模型表。"
    )
    add("")
    add("## 附註：300xx 無名列")
    add("")
    add(
        f"共 {sum(n.count for n in data.nameless)} 筆、{len(data.nameless)} 個編號，皆不在英雄名錄，"
        "沒有英雄名或造型名字串，也沒有解鎖說明，沒有隊伍／自身屬性，造型戰力為 0，皆非覺醒。"
        "這些列是不是內部或關卡用角色，表上沒有名稱可證實，本頁不編造名稱。「模型名稱」是單位模型那一列的名稱，不是造型圖鑑的造型名。"
    )
    add("")
    add(md_table(
        ["編號", "筆數", "造型編號", "備註"],
        [
            [str(n.hero_id), str(n.count), "、".join(str(i) for i in n.skin_ids), "；".join(n.notes)]
            for n in data.nameless
        ],
    ))
    add("")
    add("## 資料說明")
    add("")
    add(f"- 資料出自遊戲資料表與官方字串（hero_skin、hero_skin_suit、hero_skin_voice、skin、hero_detail、attribute、strings_zh.json），資料截至 {SKIN_DATA_CUTOFF}（香港時間）。來源是 LocalLow 包 {SKIN_DATA_PACK}（759 張表），打包時戳 {SKIN_DATA_PACKED}（香港時間）。顯示規則依攻略手冊「英雄造型圖鑑」第四版。第四版截稿已改對同一 live LocalLow 包。live 另有欄位序號殘件 `hero.json`（各列 `id` 皆為 0），不能當英雄名冊用。")
    add("- 名稱、解鎖說明、賽季說明與介面標籤都照官方字串原樣引，包括「占星學士·黑珍珠」（英雄是觀星學士）、「通靈者·威爾」（英雄是通靈師）、「喚潮使・海洋公主」、「主教‧八岐」、「樹人·聖誕」等中點與用字。15033／15039 覺醒列名稱為「沙漠王子·覺醒」，照錄。")
    add("- 屬性 3、4 的 name 欄指向 attribute_name_103／attribute_name_104，但 attribute_name_3 是「攻擊」、attribute_name_4 是「生命值」，show_type 為 1。本表實際用到的隊伍屬性是 103／104（英雄攻擊／英雄生命）。")
    add("- 本頁出現的點數屬性是突破防禦（64）、成對欄位的防禦（22）、出征上限（1019）與英雄等級上限（1098）；其餘本頁出現的自身／隊伍／套裝英雄屬性，以及成對的「紅水晶採集速度」（1006），show_type 皆為 2。賽季效果裡的點數屬性同樣寫成點數。")
    add(f"- 以{elewen.name}、{shark.name}、馴龍高手聯名、怪奇物語、不朽王座核對累加與不加總。這套顯示規則只用於本頁英雄造型。")
    add("- 本頁數值仍讀 team_attr、attr1／attr2、suit_attr、suit_star_need、attibute_*、suit_hero_attibute_* 等既有欄，不改讀 AttrListDic。LocalLow 包裡，13 把可升星造型的 AttrListDic 與 team_attr_1 起各星檔是同一套數值的另一種序列化（按星列出增量，不含 team_attr 基礎，也不含自身屬性）；10 套收集套裝的 AttrListDic、AttrActiveNeeds 則對應各檔當前屬性與啟用條件，並帶範圍鍵套裝英雄／全英雄。與既有欄核對後數值一致，沒有多出其他屬性。本頁不把 AttrListDic 單獨當成滿星或套裝加總值來用。")
    add(f"- 不把 unlock_season、unlocktime 或 season 自行標成未開放，也不自行對成 S1／S2。字串包有「聖焰神衛」「幽冥使者」但未被這 {n_suit} 套引用，不收入名錄。")
    add("- 表一附的屬性加總，是把同一英雄各件可收集造型的顯示值依屬性 id 把原值相加，再依 show_type 書寫；百分比是數字相加，不是乘算。這不是遊戲面板上的單一數字。成對屬性與賽季效果另欄，不計入自身／全部加總；收集套裝要湊數件造型，也不算進每位英雄這一行。本頁不依加總排序，也不評定誰比較強。")
    add("- repeat_reward_1 類型 999 在表上沒有名稱，本頁不自行斷定。沒有時裝幣價的可收集造型，取得途徑只寫在解鎖說明，沒有完整來源表。本頁沒有社群備註，也沒有把猜測寫進正文，也不評定造型強弱。")
    add(f"- 可收集造型有語音 {v_c_yes} 筆、無語音 {v_c_no} 筆；覺醒造型有語音 {v_a_yes} 筆、無語音 {v_a_no} 筆。")
    add("")
    return "\n".join(lines) + "\n"
