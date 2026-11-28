from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from . import attrs as A
from .overrides import (
    COMMON_TERMS,
    HERO_OVERRIDES,
    PAGE_IDS,
    UNRELEASED_HERO_IDS,
    rec_cutoff_note,
    SEASON_LABEL,
)
from .paths import DATA_CUTOFF
from .strings import fill_text, fmt_num, has_key, t
from .tables import catalog, component, components_for, hero_row


def param_list(comp: dict, n: int = 1) -> list:
    key = f"desc_parameter{n}"
    if comp.get(key):
        return list(comp[key])
    dps = comp.get("descParams") or []
    if n - 1 < len(dps) and dps[n - 1]:
        return list(dps[n - 1])
    return []


def merge_params(base, overlay) -> list:
    out = list(base or [])
    for i, v in enumerate(overlay or []):
        if i >= len(out):
            out.append(v)
        elif v not in (None, ""):
            out[i] = v
    return out


def resolve_key(x) -> str:
    if not x:
        return ""
    if isinstance(x, str) and has_key(x):
        return t(x)
    if isinstance(x, str) and not str(x).startswith("hero_"):
        return x
    return t(x)


def primary_text(comp, inherit_params=None, inherit_special=None) -> str:
    raw = t(comp.get("desc1")) or t(comp.get("desc"))
    if not raw and comp.get("descs"):
        raw = resolve_key(comp["descs"][0])
    params = merge_params(inherit_params, param_list(comp, 1))
    special = comp.get("special_desc") or inherit_special
    return fill_text(raw, params, special)


def upgrade_texts(comp) -> list[str]:
    ups = []
    for i in range(2, 6):
        key = comp.get(f"desc{i}")
        raw = t(key) if key else ""
        if not raw:
            continue
        if "下級" in raw and len(raw) < 40:
            continue
        filled = fill_text(raw, param_list(comp, i), None)
        if filled and filled not in ups:
            ups.append(filled)
    return ups


def as_int(value):
    if value in (None, "", -1):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def skill_kind(comp: dict, desc: str, name: str) -> str:
    suffix = comp["id"] % 100
    typ = comp.get("type")
    show = as_int(comp.get("show_type"))
    # Prefer official type / show_type so heroes whose 專武／英靈
    # occupy suffix 13／14 (not 14／15) still classify correctly.
    if typ == 3 or as_int(typ) == 3:
        return "上陣效果"
    if show == 2:
        return "進階技能"
    if show == 3:
        return "後段進階技能"
    if suffix in (1, 2, 3):
        if "必殺" in (desc or "") or "必殺" in (name or ""):
            return "必殺技"
        return "基礎技能"
    if suffix == 4:
        return "技能升級／變體"
    if suffix in (11, 12, 13):
        return "被動"
    if suffix == 14:
        return "進階技能"
    if suffix in (15, 16):
        return "後段進階技能"
    return "其他"


def unwrap_spirit_name(name: str) -> str:
    if not name:
        return name
    m = re.fullmatch(r"英靈「(.+)」", name)
    return m.group(1) if m else name


def hero_name(hero_id: int) -> str:
    return t(f"hero_name_{hero_id}") or str(hero_id)


def hero_href(hero_id: int) -> str | None:
    if hero_id in PAGE_IDS:
        return f"{hero_id}.html"
    return None


def official_stars() -> dict:
    """Gold 1–5 / red 6–10 / white 11–15 interface mapping."""
    return {
        "gold": (1, 5, "金色星（英雄星 1–5）"),
        "red": (6, 10, "紅色星（英雄星 6–10）"),
        "white": (11, 15, "白色星（英雄星 11–15）"),
    }


def as_list(value) -> list:
    if value in (None, "", -1):
        return []
    if isinstance(value, list):
        return value
    return [value]


# --- skins / suits ---------------------------------------------------------

def split_keys(raw) -> list[str]:
    if not raw:
        return []
    return [p for p in str(raw).split("|") if p]


def fashion_coins(skin: dict) -> str:
    goods = skin.get("need_goods") or skin.get("itemUnlockArr")
    if not goods:
        return "無"
    if isinstance(goods, (list, tuple)) and len(goods) >= 2:
        item, qty = goods[0], goods[1]
        return str(qty) if int(item) == 312 else "無"
    text = str(goods)
    for seg in text.split(","):
        if "|" in seg:
            item, qty = seg.split("|", 1)
            if item == "312":
                return qty
    return "無"


def _pairs_to_map(raw) -> dict[int, int]:
    out: dict[int, int] = {}
    for attr_id, value in A.parse_pairs(raw):
        if attr_id is None:
            continue
        out[int(attr_id)] = int(float(str(value).strip().replace(",", "")))
    return out


def _star_tier_maps(skin: dict) -> list[dict[int, int]]:
    """Parse team_attr_1..n, where each field is successive-star values of one attr."""
    by_star: list[dict[int, int]] = []
    for i in range(1, 5):
        raw = skin.get(f"team_attr_{i}")
        if not raw:
            continue
        parts = [p.strip() for p in str(raw).split(",") if p.strip()]
        for star_idx, part in enumerate(parts):
            while len(by_star) <= star_idx:
                by_star.append({})
            by_star[star_idx].update(_pairs_to_map(part))
    return by_star


def _ordered_attr_ids(base: dict[int, int], tiers: list[dict[int, int]]) -> list[int]:
    order: list[int] = []
    for mapping in [base, *tiers]:
        for aid in mapping:
            if aid not in order:
                order.append(aid)
    return order


def _format_team_collect(mapping: dict[int, int], order: list[int]) -> str:
    scope = t("skin_title_1") or "全部"
    parts = [f"{scope} {A.format_skin_attr(aid, mapping[aid])}" for aid in order if aid in mapping]
    return "；".join(parts) if parts else "無"


def star_team_rows(skin: dict) -> list[tuple[str, str]]:
    """Build 星級 / 收集屬性 rows: team_attr base + the current star tier.

    Max star uses the last tier. Faction-only attrs with no base use the tier alone.
    """
    base = _pairs_to_map(skin.get("team_attr"))
    tiers = _star_tier_maps(skin)
    if not tiers:
        return []
    order = _ordered_attr_ids(base, tiers)
    rows = []
    for i, tier in enumerate(tiers):
        combined = dict(base)
        for aid, val in tier.items():
            combined[aid] = combined.get(aid, 0) + val
        rows.append((f"{i + 1} 星", _format_team_collect(combined, order)))
    return rows


def skin_star_names(skin: dict) -> list[str]:
    names = []
    for key in split_keys(skin.get("star_name")):
        names.append(t(key) or key)
    return names


def collection_suits_for(skin_ids: set[int]) -> list[dict]:
    out = []
    for suit in catalog()["hero_skin_suit"]:
        members = set(suit.get("heroSkinMetaIds") or [])
        if not members:
            hid = suit.get("hero_skin_id")
            if isinstance(hid, list):
                members = set(hid)
            elif hid:
                members = {hid}
        if not members & skin_ids:
            continue
        name = t(suit.get("name")) or str(suit["id"])
        raw_need = suit.get("suit_star_need")
        # Official condition: 收集{0}件套裝. Do not invent a star requirement
        # when the second number is 0, and do not sum later tiers into earlier ones.
        tmpl = t("hero_skin_suit_3") or "收集{0}件套裝"
        needs = []
        if raw_need:
            for seg in str(raw_need).split(","):
                n = seg.split("|", 1)[0]
                needs.append(tmpl.replace("{0}", str(n)))
        scope_hero = t("hero_skin_suit_12") or "套裝英雄"
        scope_all = t("hero_skin_suit_13") or "全英雄"
        hero_cols = []
        all_cols = []
        for field in ("suit_hero_attibute_1", "suit_hero_attibute_2", "suit_hero_attibute_3"):
            raw = suit.get(field)
            if raw:
                hero_cols.append([p.strip() for p in str(raw).split(",") if p.strip()])
        for field in ("attibute_1", "attibute_2", "attibute_3"):
            raw = suit.get(field)
            if raw:
                all_cols.append([p.strip() for p in str(raw).split(",") if p.strip()])
        rows = []
        for i, cond in enumerate(needs):
            parts = []
            for col in hero_cols:
                if i < len(col):
                    parts.append(A.format_skin_pairs(col[i], scope=scope_hero, joiner="、"))
            for col in all_cols:
                if i < len(col):
                    parts.append(A.format_skin_pairs(col[i], scope=scope_all, joiner="、"))
            rows.append({"condition": cond, "effect": "、".join(p for p in parts if p and p != "無") or "無"})
        # which of this hero's skins belong
        belong = sorted(members & skin_ids)
        belong_names = []
        skin_map = {s["id"]: s for s in catalog()["hero_skin"]}
        for sid in belong:
            row = skin_map.get(sid) or {}
            belong_names.append(t(row.get("skin_name")) or t(f"skin_name_{sid}") or str(sid))
        out.append({"id": suit["id"], "name": name, "rows": rows, "skins": belong_names, "skin_ids": belong})
    return out



def talent_attr_pair(row: dict) -> tuple:
    """Prefer heroAttrs; some slots only have playerAttrs (lord / map attributes)."""
    for key in ("heroAttrs", "playerAttrs", "hero_attr", "player_attr"):
        pair = row.get(key)
        if pair and len(pair) >= 2:
            return pair[0], pair[1]
    raise ValueError(f"talent group {row.get('group_id')} level {row.get('level')} has no attribute pair")


# --- talents ----------------------------------------------------------------

# Talent display: all non-point attrs use raw/100 with two decimals.
# Point attrs are show_type=1 (including 1018, 1093): no %, no plus, no thousands.
# This rule is only for hero talents, not titles or 羈絆.
TALENT_POINT_ATTRS = frozenset({1018, 1093})
# These heroes have their own panel confirming the talent percentages / points.
TALENT_PANEL_HERO_IDS = frozenset({10031, 10007, 10005, 10028, 10021, 10039})


def format_talent_number(attr_id: int, value, *, max_lv: int | None = None, is_max_col: bool = False) -> tuple[str, str]:
    """Return (display, kind) where kind is percent or point.

    Mid-level values use the same rule as the cap (e.g. attr 21 at 21／22).
    """
    if int(attr_id) in TALENT_POINT_ATTRS or A.is_point_attr(attr_id):
        # Panel: no percent sign, no plus, no thousands separator.
        text = str(int(float(str(value).strip().replace(",", ""))))
        kind = "point"
    else:
        text = f"{int(float(str(value).strip().replace(',', ''))) / 100:.2f}%"
        kind = "percent"
    if is_max_col and max_lv and max_lv != 30:
        text = f"{text}（{max_lv} 級）"
    return text, kind


def talent_slot_note(hero_id: int, *, aname: str, vmax_s: str, kind: str, max_lv: int, first_slot: str | None = None) -> str:
    cap = ""
    if max_lv != 30:
        cap = f"此群組最高 {max_lv} 級，表上沒有 30 級。右欄是 {max_lv} 級的顯示值。"
    if first_slot:
        if kind == "percent":
            if hero_id in TALENT_PANEL_HERO_IDS:
                return f"與槽 {first_slot} 同名、同數值"
            return f"與槽 {first_slot} 同名、同數值"
        if kind == "point":
            return f"與槽 {first_slot} 同名、同點數"
        return f"與槽 {first_slot} 同名、同原值"
    if kind == "percent":
        shown = vmax_s.split("（")[0]
        if hero_id in TALENT_PANEL_HERO_IDS:
            return f"面板原文：自身{aname}提升{shown}。" + cap
        return f"自身{aname}提升{shown}。" + cap
    if kind == "point":
        shown = vmax_s.split("（")[0]
        return f"這是點數：{aname}提升{shown}。沒有百分號。" + cap
    return f"官方字串：自身{aname}提升{{1}}；這裡先寫表上的原值。" + cap


def talent_rows(hero_id: int) -> list[dict]:
    talents = [r for r in catalog()["hero_talent"] if r["hero_id"] == hero_id]
    groups = defaultdict(list)
    for row in catalog()["hero_talent_group"]:
        groups[row["group_id"]].append(row)
    rows = []
    for tal in sorted(talents, key=lambda r: r["slot"]):
        g = sorted(groups[tal["talent_group"]], key=lambda r: r["level"])
        lv1 = next(x for x in g if x["level"] == 1)
        max_lv = max(x["level"] for x in g)
        lvmax = next(x for x in g if x["level"] == max_lv)
        attr_id, v1 = talent_attr_pair(lv1)
        _, vmax = talent_attr_pair(lvmax)
        aname = A.attr_name(attr_id)
        v1_s, kind = format_talent_number(attr_id, v1)
        v30_s, _ = format_talent_number(attr_id, vmax, max_lv=max_lv, is_max_col=True)
        note = talent_slot_note(hero_id, aname=aname, vmax_s=v30_s, kind=kind, max_lv=max_lv)
        rows.append({
            "slot": str(tal["slot"]),
            "name": t(tal.get("talent_name")) or "",
            "attr": aname,
            "lv1": v1_s,
            "lv30": v30_s,
            "note": note,
            "kind": kind,
            "group": tal["talent_group"],
            "raw_lv1": v1,
            "raw_lv30": vmax,
            "max_level": max_lv,
            "attr_id": attr_id,
        })
    # Same-name later slots point back to the first; keep the first slot's own note.
    by_name = defaultdict(list)
    for r in rows:
        by_name[r["name"]].append(r["slot"])
    for r in rows:
        slots = by_name[r["name"]]
        if slots and r["slot"] != slots[0]:
            r["note"] = talent_slot_note(
                hero_id, aname=r["attr"], vmax_s=r["lv30"], kind=r["kind"],
                max_lv=r["max_level"], first_slot=slots[0],
            )
    extras = (HERO_OVERRIDES.get(hero_id) or {}).get("talent_note_extra") or {}
    for r in rows:
        extra = extras.get(int(r["slot"]))
        if extra:
            r["note"] = r["note"].rstrip("。") + "；" + extra
    return rows


UNNAMED_HERO_IDS = frozenset({15032, 15033, 15039})
LANDLADY_ID = 10032
UNNAMED_RESEMBLES = {15032: "老闆娘", 15033: "聖徒", 15039: "沙漠王子"}

# --- bonds / recs -----------------------------------------------------------

def bonds_for(hero_id: int) -> list[dict]:
    seen = set()
    out = []
    for link in catalog()["hero_link"]:
        typ = link["type"]
        name = t(link["name"]) or {1: "強攻", 2: "統禦", 3: "強健"}.get(typ, "")
        group = tuple(link.get("hero_group") or [])
        key = (typ, group, str(link.get("attr")), str(link.get("hero_num")))
        if key in seen:
            continue
        seen.add(key)
        if hero_id not in group:
            continue
        members = []
        for hid in group:
            members.append({"id": hid, "name": hero_name(hid), "href": hero_href(hid)})
        num = link.get("hero_num")
        if str(num) == "2|3":
            num_note = "，兩人／三人時效果不同"
        elif num not in (None, "", -1):
            num_note = f"，人數條件 {num}"
        else:
            num_note = ""
        # 羈絆 stay raw points; use table names (增傷／減傷), not title-lock labels.
        attr_s = A.format_raw_pairs(link.get("attr"), joiner="／")
        out.append({
            "name": name,
            "members": members,
            "attr": attr_s,
            "hero_num": num,
            "text": f"{name}：{'、'.join(m['name'] for m in members)}（{attr_s}{num_note}）",
        })
    return out


def rec_labels(hero_id: int, title_has: str = "聯盟") -> list[str]:
    labels = []
    for rec in catalog()["hero_recommend"]:
        title = t(rec["key_id"])
        if title_has not in title:
            continue
        ids = rec.get("hero_id") or []
        if hero_id not in ids:
            continue
        raw = rec.get("season_on")
        lab = SEASON_LABEL.get(raw, raw)
        if lab not in labels:
            labels.append(lab)
    return labels


# --- tags / intro -----------------------------------------------------------

def first_tag(hero: dict) -> dict:
    idx = A.title1_index(hero.get("title_attr"))
    if not idx:
        return {"name": "", "dec": "", "index": None, "locked": A.format_title_attr(hero.get("title_attr"))}
    return {
        "name": t(f"hero_title1_{idx}"),
        "dec": t(f"hero_title1_dec_{idx}"),
        "index": idx,
        "locked": A.format_title_attr(hero.get("title_attr")),
    }


def second_tag_info(name: str) -> dict:
    for i in range(1, 9):
        if t(f"hero_title2_{i}") == name:
            return {"name": name, "dec": t(f"hero_title2_dec_{i}"), "index": i}
    return {"name": name, "dec": "", "index": None}


# --- assemble ---------------------------------------------------------------

@dataclass
class HeroPage:
    hero_id: int
    name: str
    faction: str
    tags: list[str]
    first_tag: dict
    second_tags: list[dict]
    status: str
    exclusive_name: str | None
    spirit_name: str | None
    star_max: int
    intro: str
    lead_image: str | None
    lead_alt: str
    lead_caption: str
    skill_sources: list[tuple[str, str]]
    star_tracks: list[dict]
    star_skills: list[dict]
    awaken_rows: list[dict]
    awaken_skills: list[dict]
    awaken_note: str
    exclusive: dict | None
    spirit: dict | None
    talents: list[dict]
    talent_percent: bool
    talent_intro: str
    skins: list[dict]
    skin_feature_sections: list[dict]
    suits: list[dict]
    gear: dict | None
    bonds: list[dict]
    rec_text: str
    notes: str
    community: str | None
    terms: list[str]
    override: dict = field(default_factory=dict)


def _exclusive_self_attr(comp: dict) -> str | None:
    mapping = comp.get("attributesSelf") or {}
    if not mapping:
        return None
    parts = []
    for attr_id, series in mapping.items():
        # first non-zero rank
        first = None
        for i, val in enumerate(series or []):
            if val not in (0, "0", None, ""):
                first = (i + 1, val)
                break
        if first is None:
            continue
        rank, val = first
        label = A.attr_name(int(attr_id))
        if rank == 1:
            parts.append(f"{label} {A.comma_int(val)}")
        else:
            parts.append(f"{label} {A.comma_int(val)}（第 {rank} 階起）")
    return "、".join(parts) if parts else None


def _break_auras(hero_id: int) -> list[tuple[int, str]]:
    found = {}
    for row in catalog()["exclusive_break"]:
        if row.get("index") != hero_id:
            continue
        star = row.get("star_big")
        desc = row.get("desc")
        if star in (2, 5) and desc and star not in found:
            found[star] = t(desc) or ""
    return [(s, found[s]) for s in sorted(found)]



def exclusive_name_key_hero(name_key) -> int | None:
    m = re.fullmatch(r"hero_exclusive_name_(\d+)", str(name_key or ""))
    return int(m.group(1)) if m else None


def components_owned_by_other(hero_id: int) -> set[int]:
    """Skills in this hero's component range that belong to another hero's exclusive / awaken package.

    Examples: 諾亞金鈴 is named hero_exclusive_name_10029 but use_hero is 森之少女;
    英雄絮語 is named hero_exclusive_name_10032 but use_hero is 15032.
    """
    owned: set[int] = set()
    lo, hi = hero_id * 100, hero_id * 100 + 100
    for row in catalog()["hero_exclusive"]:
        key_hid = exclusive_name_key_hero(row.get("name"))
        use = row.get("use_hero")
        if key_hid != hero_id or use in (None, hero_id):
            continue
        for c in components_for(hero_id):
            if as_int(c.get("show_type")) == 2:
                owned.add(c["id"])
        for aw in catalog()["hero_awaken"]:
            if aw.get("hero_id") != use:
                continue
            link = aw.get("link_skill")
            if isinstance(link, int) and lo <= link < hi:
                owned.add(link)
    return owned


def break_auras_for(hero_id: int, exclusive_row: dict | None = None) -> list[tuple[int, str]]:
    found = _break_auras(hero_id)
    if found:
        return found
    if exclusive_row:
        for cand in (exclusive_row.get("id"), exclusive_row.get("group")):
            if cand in (None, "", -1):
                continue
            try:
                found = _break_auras(int(cand))
            except (TypeError, ValueError):
                continue
            if found:
                return found
    return []



def awaken_upgrade_target_name(hero_id: int) -> str:
    """Official 覺醒強化 short text uses 強化[技能名]; do not assume suffix 03."""
    for r in catalog()["hero_awaken"]:
        if r.get("hero_id") != hero_id or r.get("star_sub") != 0:
            continue
        dec = t(r.get("star_dec")) or ""
        m = re.search(r"強化\[([^\]]+)\]", dec)
        if m:
            return m.group(1)
    return ""


def assemble(hero_id: int) -> HeroPage:
    hero = hero_row(hero_id)
    ov = HERO_OVERRIDES.get(hero_id, {})
    name = hero_name(hero_id)
    fac, _src, honor_group, honor_attr = A.hero_faction(hero_id)
    faction = fac or ""
    first = first_tag(hero)
    second_names = list(ov.get("second_tags") or [])
    seconds = [second_tag_info(n) for n in second_names]
    tags = [first["name"]] + second_names if first["name"] else list(second_names)
    owned_by_other = components_owned_by_other(hero_id)
    has_awaken_rows = any(
        r.get("hero_id") == hero_id and r.get("star_sub") == 0 and (r.get("star") or 0) >= 1
        for r in catalog()["hero_awaken"]
    )

    # 狀態欄不以 hide 旗標決定。公開站鎖定只有牧羊人為未開放。
    # 老闆娘不標已開放／未開放；15032／15033／15039 只寫沒有官方中文名稱。
    if hero_id in UNRELEASED_HERO_IDS:
        status = "未開放"
    elif hero_id in UNNAMED_HERO_IDS:
        status = "沒有官方中文名稱"
    elif hero_id == LANDLADY_ID:
        status = ""
    else:
        status = "已開放"

    # exclusive
    exclusive_row = next((r for r in catalog()["hero_exclusive"] if r.get("use_hero") == hero_id), None)
    exclusive_name = t(exclusive_row["name"]) if exclusive_row else None

    # spirit
    spirit_row = next((r for r in catalog()["hero_valhalla"] if r.get("use_hero") == hero_id), None)
    spirit_name = unwrap_spirit_name(t(spirit_row["name"])) if spirit_row else None

    comps = components_for(hero_id)
    comp_by_id = {c["id"]: c for c in comps}

    # classify components
    star_skill_ids = []  # suffix 01,02,03,11,12
    awaken_variant_id = None
    awaken_passive_id = None
    exclusive_skill_id = None
    spirit_skill_id = None
    variant_ids: list[int] = []
    prev_name = None
    prev_params = None
    prev_special = None
    skill_pack = {}
    for c in comps:
        if c["id"] in owned_by_other:
            continue
        cname = t(c.get("name"))
        inherit_p = prev_params if cname and cname == prev_name else None
        inherit_s = prev_special if cname and cname == prev_name else None
        desc = primary_text(c, inherit_p, inherit_s)
        ups = upgrade_texts(c)
        suffix = c["id"] % 100
        if not cname and not desc:
            prev_name, prev_params, prev_special = cname, merge_params(inherit_p, param_list(c, 1)), c.get("special_desc") or inherit_s
            continue
        kind = skill_kind(c, desc, cname or "")
        if cname and cname == prev_name:
            kind = "技能升級／變體"
        skill_pack[c["id"]] = {
            "id": c["id"],
            "name": cname or "",
            "kind": kind,
            "desc": desc,
            "ups": ups,
            "show_type": c.get("show_type"),
            "suffix": suffix,
        }
        typ = c.get("type")
        if suffix in (1, 2, 3, 11, 12):
            star_skill_ids.append(c["id"])
        elif typ == 3 or as_int(typ) == 3:
            # 上陣效果 is not 覺醒被動, even when the component suffix is 13.
            pass
        elif as_int(c.get("show_type")) == 2:
            exclusive_skill_id = c["id"]
        elif as_int(c.get("show_type")) == 3 or suffix == 15:
            spirit_skill_id = c["id"]
        elif suffix == 14:
            exclusive_skill_id = c["id"]
        elif suffix == 13:
            if has_awaken_rows:
                awaken_passive_id = c["id"]
        elif suffix == 4:
            if has_awaken_rows:
                awaken_variant_id = c["id"]
            else:
                variant_ids.append(c["id"])
        prev_name = cname
        prev_params = merge_params(inherit_p, param_list(c, 1))
        prev_special = c.get("special_desc") or inherit_s

    def pack_from_component(comp: dict, inherit_p=None, inherit_s=None) -> dict:
        cname = t(comp.get("name")) or ""
        desc = primary_text(comp, inherit_p, inherit_s)
        ups = upgrade_texts(comp)
        kind = skill_kind(comp, desc, cname)
        return {
            "id": comp["id"],
            "name": cname,
            "kind": kind,
            "desc": desc,
            "ups": ups,
            "show_type": comp.get("show_type"),
            "suffix": comp["id"] % 100,
        }

    # Exclusive skill may live in another hero's component range
    # (e.g. 乾杯 1003214 for 15032「英雄絮語」).
    if exclusive_row and not exclusive_skill_id:
        key_hid = exclusive_name_key_hero(exclusive_row.get("name"))
        if key_hid:
            for c in components_for(key_hid):
                if as_int(c.get("show_type")) != 2:
                    continue
                if c["id"] not in skill_pack:
                    skill_pack[c["id"]] = pack_from_component(c)
                exclusive_skill_id = c["id"]
                comp_by_id[c["id"]] = c
                break

    # Unlock skills listed in hero_star with 解鎖技能 (hero_star_desc_2).
    # Shared skills such as 守護使者／戰爭使者 live outside the hero id range;
    # some heroes instead unlock an in-range 上陣效果 (e.g. 閃爍懷錶) at 11 stars.
    unlock_skill_ids: list[int] = []
    unlock_at_star: dict[int, int] = {}
    reserved = (awaken_passive_id, awaken_variant_id, exclusive_skill_id, spirit_skill_id)
    for r in catalog()["hero_star"]:
        if r["hero_id"] != hero_id or r.get("star_sub") != 0 or (r.get("star") or 0) < 1:
            continue
        skills = as_list(r.get("skills") or r.get("skill"))
        desc_keys = as_list(r.get("desc"))
        for i, sid in enumerate(skills):
            if sid in (-1, None, 0):
                continue
            dkey = desc_keys[i] if i < len(desc_keys) else ""
            is_unlock = dkey == "hero_star_desc_2"
            extra = component(sid) or comp_by_id.get(sid)
            if not extra:
                continue
            if sid not in skill_pack:
                skill_pack[sid] = pack_from_component(extra)
            if is_unlock:
                if sid in reserved or sid in unlock_skill_ids:
                    continue
                if sid in star_skill_ids:
                    star_skill_ids.remove(sid)
                unlock_skill_ids.append(sid)
                unlock_at_star[sid] = r["star"]
            elif sid not in star_skill_ids and sid not in reserved and sid not in unlock_skill_ids:
                # Star-table skills that live outside this hero's component
                # prefix (e.g. 15033 using 10033 numbers) still count as 英雄升星.
                star_skill_ids.append(sid)

    def skill_source_label(sk: dict) -> str:
        if sk["id"] in unlock_skill_ids:
            star = unlock_at_star.get(sk["id"])
            if star:
                return f"英雄升星（{star} 星解鎖技能）"
            return "英雄升星（解鎖技能）"
        if sk["suffix"] in (1, 2, 3, 11, 12):
            return "英雄升星"
        if sk["id"] == exclusive_skill_id and exclusive_name:
            return f"專武「{exclusive_name}」專屬技能"
        if sk["id"] == spirit_skill_id and spirit_name:
            return f"英靈「{spirit_name}」專屬技能"
        if sk["id"] == awaken_passive_id:
            return "覺醒被動技能"
        if sk["id"] == awaken_variant_id:
            base_name = awaken_upgrade_target_name(hero_id)
            return f"覺醒強化技能（強化{base_name}）" if base_name else "覺醒強化技能"
        if sk["id"] in variant_ids:
            return "技能升級／變體"
        return sk["kind"]

    source_order = list(star_skill_ids)
    source_order.extend(unlock_skill_ids)
    source_order.extend(variant_ids)
    if awaken_passive_id:
        source_order.append(awaken_passive_id)
    if awaken_variant_id:
        source_order.append(awaken_variant_id)
    if exclusive_skill_id:
        source_order.append(exclusive_skill_id)
    if spirit_skill_id:
        source_order.append(spirit_skill_id)
    skill_sources = []
    for sid in source_order:
        sk = skill_pack[sid]
        skill_sources.append((sk["name"], skill_source_label(sk)))

    # star tracks from hero_star (star_sub=0)
    star_rows = [
        r for r in catalog()["hero_star"]
        if r["hero_id"] == hero_id and r.get("star_sub") == 0 and r.get("star", 0) >= 1
    ]
    star_rows.sort(key=lambda r: r["star"])
    tracks = []
    for tint, (lo, hi, heading) in official_stars().items():
        items = []
        for r in star_rows:
            if lo <= r["star"] <= hi:
                skills = as_list(r.get("skills") or r.get("skill"))
                levels = as_list(r.get("skill_levels") or r.get("skill_level"))
                desc_keys = as_list(r.get("desc"))
                desc_names = as_list(r.get("desc_2"))
                bits = []
                for i, sid in enumerate(skills):
                    if sid in (-1, None, 0):
                        continue
                    if i < len(desc_names) and desc_names[i]:
                        sname = t(desc_names[i]) or ""
                    else:
                        crow = comp_by_id.get(sid) or component(sid) or {}
                        sname = t(crow.get("name")) if crow else ""
                    slv = levels[i] if i < len(levels) else None
                    dkey = desc_keys[i] if i < len(desc_keys) else "hero_star_desc_1"
                    raw = t(dkey) if dkey else t("hero_star_desc_1")
                    # hero_star_desc_2 is「解鎖技能{0}」; others take name + skill star.
                    if "{1}" not in (raw or ""):
                        text = fill_text(raw, [sname])
                    else:
                        text = fill_text(raw, [sname, slv])
                    if text:
                        bits.append(text)
                text = "；".join(bits)
                items.append({"count": r["star"] - lo + 1, "tint": tint, "text": text, "hero_star": r["star"]})
        tracks.append({"tint": tint, "heading": heading, "items": items})

    def pack_skill_block(sid: int, heading_extra: str = "") -> dict:
        sk = skill_pack[sid]
        heading = sk["name"] + (f"（{heading_extra}）" if heading_extra else "")
        body = f"【{sk['kind']}】{sk['name']}：{sk['desc']}"
        return {"heading": heading, "text": body, "upgrades": [f"升級：{u}" for u in sk["ups"]]}

    star_skills = [pack_skill_block(sid) for sid in star_skill_ids]
    for sid in unlock_skill_ids:
        star = unlock_at_star.get(sid)
        extra = f"{star} 星解鎖技能" if star else "解鎖技能"
        star_skills.append(pack_skill_block(sid, extra))
    for sid in variant_ids:
        star_skills.append(pack_skill_block(sid, "技能升級／變體"))

    # awaken stages (star 1-4, star_sub=0)
    awaken = [
        r for r in catalog()["hero_awaken"]
        if r["hero_id"] == hero_id and r.get("star_sub") == 0 and r.get("star", 0) >= 1
    ]
    awaken.sort(key=lambda r: r["star"])
    awaken_rows = []
    for r in awaken:
        stage = r["star"]
        sname = t(r.get("star_name")) or "無"
        sdec = t(r.get("star_dec")) or "無"
        link = r.get("link_skill")
        if link and link not in (-1, None, 0):
            lname = t((comp_by_id.get(link) or component(link) or {}).get("name")) or str(link)
            if link == awaken_variant_id:
                base_name = awaken_upgrade_target_name(hero_id)
                related = f"{lname}（強化{base_name}）" if base_name else lname
            else:
                related = lname
        else:
            skin_id = r.get("skin")
            quality = r.get("quality")
            # Official short desc already says when an appearance unlocks.
            # Keep skin id / quality in 資料說明, not in the main 關聯技能 column.
            related = "無連結技能"
        awaken_rows.append({"stage": str(stage), "name": sname, "dec": sdec, "related": related, "row": r})

    awaken_skills = []
    if awaken_passive_id:
        awaken_skills.append(pack_skill_block(awaken_passive_id, "覺醒被動技能"))
    if awaken_variant_id:
        base_name = awaken_upgrade_target_name(hero_id)
        extra = f"覺醒強化{base_name}" if base_name else "覺醒強化技能"
        awaken_skills.append(pack_skill_block(awaken_variant_id, extra))
    # Heroes with no component prefix of their own (e.g. 15033) still have
    # hero_awaken link_skill values; show those as 覺醒表關聯, do not relabel
    # an 上陣效果 as 覺醒被動.
    if awaken and not awaken_skills:
        seen_links = set()
        for r in awaken:
            link = r.get("link_skill")
            if link in (-1, None, 0) or link in seen_links:
                continue
            seen_links.add(link)
            extra_comp = component(link) or comp_by_id.get(link)
            if not extra_comp:
                continue
            if link not in skill_pack:
                skill_pack[link] = pack_from_component(extra_comp)
            sk = skill_pack[link]
            awaken_skills.append(pack_skill_block(link, f"覺醒表關聯技能；{sk['kind']}"))
            skill_sources.append((sk["name"], f"覺醒表關聯技能（{sk['kind']}）"))

    # exclusive block
    exclusive = None
    if exclusive_skill_id and exclusive_name:
        sk = skill_pack[exclusive_skill_id]
        ranks = [f"1 階：{sk['desc']}"]
        for i, u in enumerate(sk["ups"], start=2):
            ranks.append(f"{i} 階：{u}")
        self_attr = _exclusive_self_attr(comp_by_id.get(exclusive_skill_id) or component(exclusive_skill_id) or {})
        auras = break_auras_for(hero_id, exclusive_row)
        exclusive = {
            "weapon": exclusive_name,
            "skill": sk["name"],
            "desc": sk["desc"],
            "ranks": ranks,
            "self_attr": self_attr,
            "auras": auras,
            "comp_id": exclusive_skill_id,
            "break_comp": hero_id * 100 + 16,
            "fragment": 10000 + (hero_id % 10000) + 1000 if False else 11000 + (hero_id % 10000),
        }
        # 專武碎片：published uses 11031 / 11027 = 11 + last 3 digits? 11000+31? 
        # 10031 → 11031; 10027 → 11027. That's 10000 + (hero_id % 1000)? 10000+1031=11031. Yes 10000 + hero_id % 10000? 10000+31=10031 wrong.
        # 1 + hero_id: 1+10031=10032 no. Pattern: replace leading 10 with 11: 10031→11031.
        exclusive["fragment"] = int("11" + str(hero_id)[2:])

    # spirit block
    spirit = None
    if spirit_row and spirit_skill_id:
        # Reuse 英靈總表 formatters; import lazily to avoid a module cycle.
        from .valhalla_tables import (
            COMMON_ATTR_IDS,
            _self_attr_text,
            _self_attrs,
            attr_header,
            attr_map,
            format_attr,
        )

        sk = skill_pack[spirit_skill_id]
        levels = [1, 25, 50, 75, 100]
        lvup = [r for r in catalog()["hero_valhalla_lvup"] if r["index"] == hero_id]
        by_lv = {r["lv"]: r for r in lvup}
        sixth_id = None
        for lv in (100, 1):
            row = by_lv.get(lv)
            if not row:
                continue
            extra = [aid for aid in attr_map(row.get("attrs")) if aid not in COMMON_ATTR_IDS]
            if len(extra) != 1:
                raise ValueError(f"{hero_id} lv{lv} does not have exactly one exclusive attr")
            sixth_id = extra[0]
            break
        if sixth_id is None:
            raise ValueError(f"{hero_id} missing hero_valhalla_lvup rows")
        for lv, row in by_lv.items():
            extra = [aid for aid in attr_map(row.get("attrs")) if aid not in COMMON_ATTR_IDS]
            if extra != [sixth_id]:
                raise ValueError(f"{hero_id} exclusive attr type changes at lv {lv}")
        sixth_rows = []
        ranks = []
        for i, lv in enumerate(levels, start=1):
            row = by_lv.get(lv)
            raw_sixth = 0
            if row:
                raw_sixth = attr_map(row.get("attrs")).get(sixth_id, 0)
            if i == 1:
                text = sk["desc"]
            else:
                text = sk["ups"][i - 2] if i - 2 < len(sk["ups"]) else ""
            ranks.append(f"{lv} 級（技能 {i} 階）：{text}")
            sixth_rows.append((f"{lv} 級", format_attr(sixth_id, raw_sixth)))
        comp = comp_by_id.get(spirit_skill_id) or component(spirit_skill_id) or {}
        forces = comp.get("fightforces") or comp.get("fightforce")
        spirit = {
            "name": spirit_name,
            "skill": sk["name"],
            "desc": sk["desc"],
            "ranks": ranks,
            "sixth_id": sixth_id,
            "sixth_header": attr_header(sixth_id),
            "sixth_rows": sixth_rows,
            "self_attr_text": _self_attr_text(_self_attrs(comp)),
            "fightforce": forces,
            "comp_id": spirit_skill_id,
            "fragment": int("12" + str(hero_id)[2:]),
        }
    elif not spirit_row:
        spirit = None

    talents = talent_rows(hero_id)
    talent_percent = any(r.get("kind") == "percent" for r in talents)
    slot_words = {1: "一", 2: "兩", 3: "三", 4: "四"}
    slot_bit = slot_words.get(len(talents), str(len(talents)))
    talent_intro = f"{name}有{slot_bit}個天賦槽。下表列出槽位、名稱，以及 1 級與滿級效果。"
    has_percent = any(r.get("kind") == "percent" for r in talents)
    has_point = any(r.get("kind") == "point" for r in talents)
    if has_percent:
        if hero_id in TALENT_PANEL_HERO_IDS:
            talent_intro += "百分比按本站統一規則換算，說明見資料說明。"
            if hero_id == 10031:
                talent_intro += "格擋與套裝同層如何疊加尚未確認。"
        else:
            talent_intro += "百分比按本站統一規則換算，說明見資料說明。"
    if has_point:
        talent_intro += "點數依面板原文寫，沒有百分號。"
    odd_caps = sorted({r.get("max_level") for r in talents if r.get("max_level") and r["max_level"] != 30})
    if odd_caps:
        talent_intro += "部分槽位的天賦群組最高只有" + "／".join(str(x) + " 級" for x in odd_caps) + "，沒有 30 級，右欄改寫該群組最高級的顯示值。"

    # skins
    skin_rows = [s for s in catalog()["hero_skin"] if s["hero_id"] == hero_id]
    skin_rows.sort(key=lambda s: s.get("order") or 0)
    skins = []
    feature_sections = []
    skin_ids = set()
    for s in skin_rows:
        sid = s["id"]
        skin_ids.add(sid)
        sname = t(s.get("skin_name")) or t(f"skin_name_{s.get('skin_id')}") or str(sid)
        unlock = t(s.get("unlock_dec")) or "無"
        coins = fashion_coins(s)
        can_up = bool(s.get("CanUpStar"))
        star_max = s.get("star_max")
        self_raw = s.get("attr1") or s.get("attr2")
        team_scope = t("skin_title_1") or "全部"
        self_txt = A.format_skin_pairs(self_raw, scope=name)
        team_txt = A.format_skin_pairs(s.get("team_attr"), scope=team_scope)
        if can_up and star_max and int(star_max) > 0:
            bits = []
            if self_txt != "無":
                bits.append(self_txt)
            bits.append(f"可升至 {int(star_max)} 星，隊伍屬性見下方星級表")
            collect = "；".join(bits)
        else:
            bits = []
            if self_txt != "無":
                bits.append(self_txt)
            if team_txt != "無":
                bits.append(team_txt)
            collect = "；".join(bits) if bits else "無"
        equip = A.format_skin_pairs(self_raw) if self_raw not in (None, "", -1, 0) else "無"
        skins.append({
            "id": sid,
            "name": sname,
            "collect": collect,
            "equip": equip,
            "unlock": unlock,
            "coins": coins,
            "row": s,
        })
        # feature sections: pairing, season, star-up
        parts = []
        section_id = None
        # pairing via suit pointing at another skin id (not collection suit)
        partner_id = s.get("suit")
        if partner_id not in (None, "", -1, 0):
            partner = next((x for x in catalog()["hero_skin"] if x["id"] == partner_id), None)
            if partner:
                pname = t(partner.get("skin_name")) or t(f"skin_name_{partner_id}") or str(partner_id)
                pattr = A.format_skin_pairs(s.get("suit_attr"), joiner="、")
                partner_hero = partner.get("hero_id")
                href = hero_href(partner_hero)
                partner_hero_name = hero_name(partner_hero)
                link_note = ""
                if href:
                    link_note = f"{pname}可到{partner_hero_name}條目查閱。"
                # Do not invent a link when the partner hero has no page.
                parts.append(
                    f"成對造型與收集套裝不是同一欄。{sname}與{pname}互為成對，雙方成對屬性皆為{pattr}。"
                    f"成對效果何時啟動，表上沒有另寫說明，本頁不自行推斷。"
                    + (link_note and f"{link_note}" or "")
                )
        season_dec = t(s.get("season_dec")) if s.get("season_dec") else ""
        extra_eff = s.get("season_effect2") or s.get("season_effect")
        if season_dec or extra_eff:
            text = ""
            if season_dec:
                text = f"此套另有賽季說明「{season_dec}」"
            if extra_eff:
                extras = []
                for aid, val in A.parse_pairs(extra_eff):
                    if aid is None:
                        extras.append(str(val))
                    else:
                        extras.append(A.format_skin_attr(aid, val))
                if extras:
                    text += ("，以及賽季屬性" if text else "此套另有賽季屬性") + "、".join(extras)
            text += "。官方另有「賽季屬性只在對應賽季生效」「臨時擁有屬性，對應賽季持續期間，擁有造型即可生效」「臨時使用屬性，對應賽季持續期間，使用造型即可生效」，但本頁不自行把這一欄對成擁有或使用。賽季欄的數字不自行對成第幾賽季日曆。"
            parts.append(text)
        if can_up and star_max and int(star_max) > 0:
            names = "、".join(skin_star_names(s))
            star_tbl = star_team_rows(s)
            if names:
                star_intro = (
                    f"此套可升星至 {int(star_max)}，星級名為{names}。"
                    "隊伍屬性是基礎加上該星檔，滿星用最後一檔，寫在下表。"
                )
            else:
                star_intro = (
                    f"此套可升星至 {int(star_max)}。表上沒有另列星級名。"
                    "隊伍屬性是基礎加上該星檔，滿星用最後一檔，寫在下表。"
                )
            parts.insert(0, star_intro)
            feature_sections.append({
                "id": f"skin-{sid}",
                "heading": sname,
                "paragraphs": parts[:1],
                "star_table": star_tbl,
                "after": parts[1:],
            })
        elif parts:
            feature_sections.append({
                "id": f"skin-{sid}",
                "heading": sname,
                "paragraphs": parts,
                "star_table": [],
                "after": [],
            })

    suits = collection_suits_for(skin_ids)
    skin_order = {s["id"]: s.get("order") or 0 for s in skin_rows}
    suits.sort(key=lambda su: min(skin_order.get(sid, 999) for sid in su.get("skin_ids") or [999]))

    # intro
    pronoun = ov.get("pronoun")
    role = ov.get("role_blurb") or "英雄"
    recs = rec_labels(hero_id, title_has=faction or "聯盟")
    rec_join = "、".join(recs) if recs else "未出現"
    tag_line = "、".join(tags) if tags else first["name"]
    first_dec = first.get("dec") or ""
    second_bits = []
    for sg in seconds:
        if sg["dec"]:
            second_bits.append(f"{sg['name']}是「{sg['dec']}」")
    if len(seconds) == 2:
        second_prose = (
            f"{seconds[0]['name']}是「{seconds[0]['dec']}」，{seconds[1]['name']}是「{seconds[1]['dec']}」；"
            "後兩項的官方說明沒有百分比。"
        )
    elif seconds:
        second_prose = "；".join(second_bits) + "。後項的官方說明沒有百分比。"
    else:
        second_prose = "第二組標籤本頁不推算。"

    official_rec_title = {
        "聯盟": t("hero_recommend_1") or "最佳聯盟",
        "自然": t("hero_recommend_2") or "最佳自然",
        "部族": t("hero_recommend_8") or "最佳部族",
    }
    rec_title = official_rec_title.get(faction) or official_rec_title["聯盟"]
    if recs:
        rec_intro = f"並出現在官方「{rec_title}」名單（{rec_join}）"
    else:
        rec_intro = f"官方「{rec_title}」名單未列"
    # Only say 已開放 when hide=-1, as on the published 審判官／修女 pages.
    # hide=1 is not a 未開放 flag; do not invent either wording from that field.
    # 牧羊人 is the exception: the index already confirms 未開放.
    if hero_id in UNRELEASED_HERO_IDS:
        open_bit = "目前未開放，一般招募還拿不到。"
    elif hero.get("hide") == -1:
        open_bit = f"{pronoun}已開放，" if pronoun else "已開放，"
    else:
        open_bit = ""
    intro = (
        f"{name}是{faction}的{role}。{open_bit}{rec_intro}。"
        f"英雄屬性是{tag_line}。"
        f"{first['name']}的官方說明是「{first_dec}」。{second_prose}"
    )
    if hero_id in UNNAMED_HERO_IDS:
        other = UNNAMED_RESEMBLES.get(hero_id)
        resemble = f"技能或造型的官方字串可能與{other}相近，但本頁不當成同一人。" if other else ""
        intro += f"遊戲中文名稱表沒有這個編號，所以本頁只用 {hero_id}，不另起中文名。{resemble}"
    if ov.get("intro"):
        intro = ov["intro"]

    rec_text = ""
    if recs:
        rec_text = f"官方「{rec_title}」出場：{rec_join}。{rec_cutoff_note(faction)}"
        if faction == "部族":
            tribe_title = t("hero_recommend_8") or "最佳部族"
            tribe_short = t("hero_recommend_dec_3") or "最好的部落陣容，有著快速又猛烈的攻擊"
            rec_text = (
                f"官方「{rec_title}」出場：{rec_join}。"
                f"早期未標具體賽季名稱的標題是「{tribe_title}」，"
                f"短述是「{tribe_short}」，兩者並列，不把短述裡的「部落」改成「部族」。"
                f"{rec_cutoff_note(faction)}"
            )

    # notes
    notes = _build_notes(
        hero=hero,
        hero_id=hero_id,
        name=name,
        first=first,
        seconds=seconds,
        honor_group=honor_group,
        honor_attr=honor_attr,
        exclusive=exclusive,
        spirit=spirit,
        talents=talents,
        talent_percent=talent_percent,
        awaken=awaken,
        unlock_skill_ids=unlock_skill_ids,
        unlock_at_star=unlock_at_star,
        has_lead=False,
        notes_extra=ov.get("notes_extra"),
    )

    terms = list(COMMON_TERMS)
    for extra in [name, exclusive_name, spirit_name] + [s["name"] for s in skins] + [su["name"] for su in suits]:
        if extra and extra not in terms:
            terms.append(extra)
    for sk in skill_pack.values():
        if sk["name"] and sk["name"] not in terms:
            terms.append(sk["name"])

    return HeroPage(
        hero_id=hero_id,
        name=name,
        faction=faction,
        tags=tags,
        first_tag=first,
        second_tags=seconds,
        status=status,
        exclusive_name=exclusive_name,
        spirit_name=spirit_name,
        star_max=hero.get("star_max") or 15,
        intro=intro,
        lead_image=ov.get("lead_image"),
        lead_alt=ov.get("lead_alt") or "",
        lead_caption=ov.get("lead_caption") or "",
        skill_sources=skill_sources,
        star_tracks=tracks,
        star_skills=star_skills,
        awaken_rows=awaken_rows,
        awaken_skills=awaken_skills,
        awaken_note="",
        exclusive=exclusive,
        spirit=spirit,
        talents=talents,
        talent_percent=talent_percent,
        talent_intro=talent_intro,
        skins=skins,
        skin_feature_sections=feature_sections,
        suits=suits,
        gear=ov.get("gear"),
        bonds=bonds_for(hero_id),
        rec_text=rec_text,
        notes=notes,
        community=ov.get("community"),
        terms=terms,
        override=ov,
    )


def _build_notes(*, hero, hero_id, name, first, seconds, honor_group, honor_attr,
                 exclusive, spirit, talents, talent_percent, awaken,
                 unlock_skill_ids=None, unlock_at_star=None, has_lead=False,
                 notes_extra=None) -> str:
    attrs = catalog()["attribute_by_id"]
    honor_name = A.attr_name(honor_attr) if honor_attr else ""
    is_race = (attrs.get(honor_attr) or {}).get("is_race") if honor_attr else None
    ta = hero.get("title_attr")
    locked = first.get("locked") or ""
    # describe title_attr as 19｜500 style
    ta_disp = str(ta).replace("|", "｜") if ta else ""
    hide = hero.get("hide")
    openday = hero.get("openday_hide")
    frag = hero.get("fragment_id")
    frag_n = hero.get("fragment_num")
    bits = [
        "以下是整理用註記，查技能與效果可略過。",
        f"資料說明：編號 {hero_id}。表上記號 hide={hide}（狀態欄不以 hide 旗標決定，此欄只在本節照錄）。openday_hide={openday}（第二欄數字可能與開服天數有關，尚未對到說明文字）。",
        f"碎片 fragment_id={frag}，合成所需 {frag_n}。",
        f"榮譽加成 honor_group {honor_group} → {honor_name}（{honor_attr}，is_race={is_race}）。",
        f"英雄屬性的表鍵是 title_attr／{ta_disp}，依已鎖定百分比顯示為{first['name']}的{locked}"
        + (f"（舊稱 {A.title_attr_old(ta)}）" if A.title_attr_old(ta) else "")
        + "。",
    ]
    if seconds:
        sec_names = "、".join(s["name"] for s in seconds)
        bits.append(f"{sec_names}由玩家在面板確認；官方說明沒有百分比。表上尚無每人第二組欄位，不推及其他英雄。")
    else:
        bits.append("第二組標籤尚未經玩家面板確認，本頁不推算。")
    if exclusive:
        show = 2
        bits.append(
            f"專武升級技能{exclusive['skill']}組件 {exclusive['comp_id']}（show_type={show}），"
            f"突破元件 {exclusive['break_comp']}"
            + ("" if has_key(f"hero_skill_name_{exclusive['break_comp']}") else f"（字串表沒有 hero_skill_name_{exclusive['break_comp']}）")
            + f"，碎片 {exclusive['fragment']}。"
        )
    if spirit:
        bits.append(
            f"英靈專屬技能{spirit['skill']} {spirit['comp_id']}（show_type=3），專屬碎片物品 id {spirit['fragment']}。"
        )
        bits.append(
            "英靈屬性依 show_type 書寫：1（3、4、1098）寫點數，無百分號、無千位分符、不加加號；"
            "2（103、104、第 6 項專屬屬性，以及專屬技能列 attribute_self）為原值÷100，兩位小數加百分號。"
            "升級戰力照表上整數書寫（滿級 627500），不改成 628K。"
            "這套規則只用於英靈屬性，不套到專武、稱號或羈絆。"
        )
    else:
        bits.append("資料表沒有英靈列。")
    if not awaken:
        bits.append("資料表 hero_awaken 沒有本英雄的覺醒列，組件表也沒有獨立的覺醒被動或覺醒強化技能。")
    unlock_skill_ids = unlock_skill_ids or []
    unlock_at_star = unlock_at_star or {}
    if unlock_skill_ids:
        own_parts = []
        shared_parts = []
        lo, hi = hero_id * 100, hero_id * 100 + 100
        for sid in unlock_skill_ids:
            crow = component(sid) or {}
            sname = t(crow.get("name")) or str(sid)
            star = unlock_at_star.get(sid)
            star_bit = f"英雄星 {star} " if star else ""
            piece = f"{star_bit}另解鎖{sname}（組件 {sid}）"
            if lo <= sid < hi:
                own_parts.append(piece)
            else:
                shared_parts.append(piece)
        if own_parts:
            bits.append("、".join(own_parts) + "；此為本英雄組件號段內、以「解鎖技能」寫在英雄星上的技能。")
        if shared_parts:
            bits.append("、".join(shared_parts) + "；這是共用解鎖技能，不是本英雄獨立組件號段。")
    # talent groups
    tal_bits = []
    for row in talents:
        cap = f"{row['max_level']} 級 " if row.get("max_level") and row["max_level"] != 30 else ""
        tal_bits.append(
            f"槽 {row['slot']} 群組 {row['group']}（{row['name']}，{row['attr']} {A.format_int(row['raw_lv1'])}／{cap}{A.format_int(row['raw_lv30'])}）"
        )
    bits.append(
        "天賦依舊表 hero_talent.json 寫（不讀 hero_talent_new.json）："
        + "、".join(tal_bits)
        + "。這不是寫死所有伺服器、所有英雄都讀舊表。"
    )
    pct_ids = sorted({int(row["attr_id"]) for row in talents if row.get("kind") == "percent"})
    raw_ids = sorted({int(row["attr_id"]) for row in talents if row.get("kind") == "raw"})
    point_ids = sorted({int(row["attr_id"]) for row in talents if row.get("kind") == "point"})
    if pct_ids:
        id_bit = "、".join(str(i) for i in pct_ids)
        if hero_id in TALENT_PANEL_HERO_IDS:
            bits.append(
                f"屬性 {id_bit} 的百分比已用面板確認，等於原值除100；"
                "此換算只用於英雄天賦，不推到羈絆或稱號。"
            )
        else:
            bits.append(
                f"屬性 {id_bit} 依已確認的前服天賦面板規則，把原值除100寫成兩位小數；"
                "這不是本英雄自己的面板確認。此換算只用於英雄天賦，不推到羈絆或稱號。"
            )
    if raw_ids:
        bits.append(
            "屬性 "
            + "、".join(str(i) for i in raw_ids)
            + " 寫原值，未依那條百分比規則換算。"
        )
    if point_ids:
        bits.append(
            "屬性 "
            + "、".join(str(i) for i in point_ids)
            + " 依已確認面板為點數，沒有百分號、正號或千分位。"
        )
    bits.append("較新一張天賦表把槽 1／2／4 改掛為英雄攻擊／英雄生命，本頁不採。")
    bits.append(
        "建議裝備裡，後期泰坦之威、血之怒、騎士榮光若標尚未開放或未開放，"
        "是本站依面板加上的標註，不是表上的欄位。"
    )
    bits.append(
        "造型的自身、隊伍、套裝、成對與賽季效果依屬性類型顯示："
        "show_type=2 把原值除以 100，寫成加號、兩位小數、百分號；"
        "show_type=1 寫成點數加號，沒有百分號，也沒有千分位。"
        "可升星造型的隊伍顯示值是 team_attr 基礎加當前星檔，滿星用最後一檔；套裝只取當前檔、不加總。"
        "這條只用於英雄造型，不套到稱號或羈絆。"
    )

    # 修女 awaken key quirk
    odd_keys = []
    for r in awaken:
        key = r.get("star_dec")
        if key and f"hero_awaken_{hero_id}_" not in str(key) and str(key).startswith("hero_awaken_"):
            odd_keys.append(str(key))
    if odd_keys:
        bits.append(
            "覺醒階段 "
            + "、".join(
                str(r["star"]) for r in awaken if r.get("star_dec") and f"hero_awaken_{hero_id}_" not in str(r.get("star_dec"))
            )
            + " 的 star_dec 鍵是 "
            + "／".join(odd_keys)
            + f"，本頁照表鍵解出短述，不改寫成未掛上的 hero_awaken_{hero_id}_dec 字串。"
        )
    # show_star / link_star
    if awaken:
        ss = {r.get("show_star") for r in awaken}
        ls = {r.get("link_star") for r in awaken}
        bits.append(
            f"覺醒列另有 show_star={next(iter(ss)) if len(ss)==1 else ss}、link_star={next(iter(ls)) if len(ls)==1 else ls}"
            "（本英雄各列原值相同）；含義尚未在已發布圖鑑說明，此處不自行解釋。"
        )
    missing_aw_keys = []
    for r in awaken:
        for key in (r.get("star_name"), r.get("star_dec")):
            if key and str(key).startswith("hero_awaken_") and not t(key):
                missing_aw_keys.append(str(key))
    if missing_aw_keys:
        # Keep unique order.
        seen = []
        for k in missing_aw_keys:
            if k not in seen:
                seen.append(k)
        bits.append(
            "覺醒階段名稱／短述的表鍵是"
            + "／".join(seen)
            + "，字串表沒有這些鍵，本頁不虛擬短述。"
        )
    if notes_extra:
        bits.append(str(notes_extra).rstrip("。") + "。")
    bits.append("頭像位置已預留，以後再補；目前不放角色圖，也不使用解包立繪或 Fandom／社群立繪。")
    out = []
    for b in bits:
        b = b.strip()
        if b and not b.endswith(("。", "）")):
            b += "。"
        out.append(b)
    return "".join(out)
