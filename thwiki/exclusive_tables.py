"""Compile the public exclusive-weapon tables page."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .assemble import assemble, component, hero_href
from .highlight import highlight
from .htmlutil import e, table
from .overrides import ROSTER, UNRELEASED_HERO_IDS, roster_display_name
from .paths import DATA_CUTOFF
from .strings import t
from .tables import catalog, load_table


LIVE_HERO = "https://marcochanhc.github.io/th-wiki/heroes/{id}.html"

ATTR_IDS = (3, 4, 103, 104)
ATTR_NAME_KEYS = {
    3: "attribute_name_3",
    4: "attribute_name_4",
    103: "attribute_name_103",
    104: "attribute_name_104",
}
STD_FIGHTFORCE = (100, 150, 200, 250, 300)
SKILL_LEVEL_BY_RANK = {1: 1, 2: 5, 3: 10, 4: 15, 5: 20}


def attr_label(attr_id: int) -> str:
    return t(ATTR_NAME_KEYS[attr_id]) or str(attr_id)


def raw_int(value) -> int:
    return int(float(str(value).strip()))


def raw(value) -> str:
    return str(raw_int(value))


def comma(value) -> str:
    return f"{raw_int(value):,}"


def attr_map(pairs) -> dict[int, int]:
    out = {}
    for item in pairs or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out[int(item[0])] = raw_int(item[1])
    return out


def ratio(gain, cost) -> str:
    """Derived 每單位素材的戰力增量; not an official column."""
    c = raw_int(cost)
    g = raw_int(gain)
    if c == 0:
        return "—"
    q = g / c
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    return f"{q:.1f}"


def md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n")


def md_cell(text: str) -> str:
    return md_escape(text).replace("\n", "<br>")


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(md_cell(c) for c in row) + " |" for row in rows)
    return "\n".join((head, sep, body))


def terms_for(weapons: list["WeaponRow"]) -> list[str]:
    terms = {
        "裝備屬性",
        "突破屬性",
        "突破專屬",
        "專屬技能",
        "專屬裝備",
        "通用專屬裝備碎片",
        "隕星鐵芯",
        "普攻減傷",
        "英雄攻擊",
        "英雄生命",
        "聯盟",
        "自然",
        "部族",
        "愛情蛊惑",
    }
    for w in weapons:
        terms.update({w.weapon, w.skill, w.hero_label.replace("（未開放）", "")})
        if w.hero_name:
            terms.add(w.hero_name)
    return sorted({t for t in terms if t}, key=len, reverse=True)


def H(text: str, terms: list[str]) -> str:
    return highlight(text, terms)


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


@dataclass
class BreakRow:
    step: int
    star_big: int
    star_small: int
    cost: int
    cumulative: int
    attrs: dict[int, int]
    big: list[tuple[int, int]]
    power: int
    aura_rank: int | None
    delta_attrs: dict[int, int]
    delta_big: list[tuple[int, int]]
    delta_power: int


@dataclass
class WeaponRow:
    hero_id: int
    hero_name: str | None
    hero_label: str
    faction: str
    weapon: str
    skill: str
    skill_desc: str
    ranks: list[str]
    self_attr: str | None
    fightforce: tuple
    fragment_intro: str
    fragment_intro_note: str
    shared_intro: str
    live_url: str


@dataclass
class TablesData:
    upgrade: list[LevelRow]
    breakthrough: list[BreakRow]
    weapons: list[WeaponRow]
    auras: dict[str, list[tuple[int, str]]]  # faction -> [(star, text)]
    upgrade_total: int
    break_total: int
    verifications: dict
    terms: list[str] = field(default_factory=list)


def _curve_or_raise(groups: dict, label: str):
    bad = {k: v for k, v in groups.items() if len(v) > 1}
    if bad:
        raise ValueError(f"{label} is not identical across all weapons: {bad}")


def load_tables_data() -> TablesData:
    lvup = load_table("exclusive_lvup")
    brk = load_table("exclusive_break")
    hexc = catalog()["hero_exclusive"]
    if len(hexc) != 35 or len(lvup) != 700 or len(brk) != 875:
        raise ValueError(
            f"unexpected table sizes: exclusive={len(hexc)} lvup={len(lvup)} break={len(brk)}"
        )

    # --- upgrade curve (ignore hero-specific shard id) ---
    cost_by_lv = defaultdict(set)
    attr_by_lv = defaultdict(set)
    power_by_lv = defaultdict(set)
    rank_by_lv = defaultdict(set)
    lv_cost_items = Counter()
    extra_lv_costs = []
    for r in lvup:
        arr = r.get("costArr") or []
        if len(arr) != 1:
            extra_lv_costs.append(r)
        typ, iid, qty = arr[0]
        lv_cost_items[(typ, iid)] += 1
        cost_by_lv[r["lv"]].add((typ, int(qty)))
        attr_by_lv[r["lv"]].add(tuple(sorted((int(a[0]), raw_int(a[1])) for a in r.get("attrs") or [])))
        power_by_lv[r["lv"]].add(raw_int(r["power"]))
        rank_by_lv[r["lv"]].add(tuple(int(p[1]) for p in (r.get("skillArr") or [])))
    _curve_or_raise(cost_by_lv, "upgrade costs (qty)")
    _curve_or_raise(attr_by_lv, "upgrade attrs")
    _curve_or_raise(power_by_lv, "upgrade power")
    _curve_or_raise(rank_by_lv, "upgrade skill ranks")
    if extra_lv_costs:
        raise ValueError("upgrade rows have extra cost items")

    upgrade: list[LevelRow] = []
    cum = 0
    prev_attrs = {i: 0 for i in ATTR_IDS}
    prev_power = 0
    for lv in range(1, 21):
        typ, qty = next(iter(cost_by_lv[lv]))
        if typ != 2:
            raise ValueError(f"unexpected upgrade cost type {typ}")
        cum += qty
        attrs = {aid: val for aid, val in next(iter(attr_by_lv[lv]))}
        power = next(iter(power_by_lv[lv]))
        rank = next(iter(rank_by_lv[lv]))[0]
        delta = {i: attrs[i] - prev_attrs[i] for i in ATTR_IDS}
        dpower = power - prev_power
        upgrade.append(
            LevelRow(lv, qty, cum, attrs, power, rank, delta, dpower)
        )
        prev_attrs, prev_power = attrs, power

    # --- breakthrough curve ---
    br_cost = defaultdict(set)
    br_small = defaultdict(set)
    br_big = defaultdict(set)
    br_power = defaultdict(set)
    br_rank = defaultdict(set)
    br_items = Counter()
    cost1_used = 0
    for r in brk:
        key = (r["lv"], r["star_big"], r["star_small"])
        arr2 = r.get("costArr2") or []
        if r.get("cost1") not in (None, "") or r.get("costArr1"):
            cost1_used += 1
        typ, iid, qty = arr2[0]
        br_items[(typ, iid)] += 1
        br_cost[key].add((typ, int(qty)))
        br_small[key].add(tuple(sorted((int(a[0]), raw_int(a[1])) for a in r.get("attrsSmall") or [])))
        br_big[key].add(tuple(sorted((int(a[0]), raw_int(a[1])) for a in r.get("attrsBig") or [])))
        br_power[key].add(raw_int(r["power"]))
        rawc = r.get("exclusive_component")
        if not rawc:
            br_rank[key].add(None)
        else:
            if isinstance(rawc, list):
                rawc = rawc[0] if rawc else None
            br_rank[key].add(int(str(rawc).split("|")[1]) if rawc and "|" in str(rawc) else rawc)
    for label, groups in (
        ("break costs", br_cost),
        ("break small attrs", br_small),
        ("break big attrs", br_big),
        ("break power", br_power),
        ("break component rank", br_rank),
    ):
        _curve_or_raise(groups, label)
    if cost1_used:
        raise ValueError("breakthrough cost1 is not empty")
    if set(br_items) != {(2, 258)}:
        raise ValueError(f"unexpected break cost items: {br_items}")

    breakthrough: list[BreakRow] = []
    cum = 0
    prev_attrs = {i: 0 for i in ATTR_IDS}
    prev_power = 0
    for key in sorted(br_cost):
        typ, qty = next(iter(br_cost[key]))
        cum += qty
        attrs = {aid: val for aid, val in next(iter(br_small[key]))}
        big = [(aid, val) for aid, val in next(iter(br_big[key]))]
        power = next(iter(br_power[key]))
        aura_rank = next(iter(br_rank[key]))
        step, star_big, star_small = key
        delta = {i: attrs[i] - prev_attrs[i] for i in ATTR_IDS}
        dpower = power - prev_power
        breakthrough.append(
            BreakRow(
                step, star_big, star_small, qty, cum, attrs, big, power,
                aura_rank, delta, big, dpower,
            )
        )
        prev_attrs, prev_power = attrs, power

    # --- weapons in roster order ---
    hexc_by = {r["use_hero"]: r for r in hexc}
    lv_item_by_index = {}
    for r in lvup:
        if r["lv"] == 1:
            lv_item_by_index[r["index"]] = r["costArr"][0][1]

    weapons: list[WeaponRow] = []
    auras: dict[str, list[tuple[int, str]]] = {}
    shared_intro = t("hero_exclusive_02_dec")
    for faction, _anchor, entries in ROSTER:
        for hid, name in entries:
            row = hexc_by.get(hid)
            if not row:
                continue
            page = assemble(hid)
            ex = page.exclusive
            if not ex:
                raise ValueError(f"assemble({hid}) has no exclusive block")
            if page.faction != faction:
                raise ValueError(f"faction mismatch {hid}: {page.faction} vs roster {faction}")
            index = row.get("group") or row.get("id")
            cost_item = lv_item_by_index[index]
            intro = t(f"goods_desc_{cost_item}") or ""
            note = ""
            if hid == 10036:
                # 升級消耗寫 11036，名稱與說明字串在 11029。
                intro = intro or t("goods_desc_11029")
                note = (
                    "升級消耗欄的道具是 11036，字串表沒有這件的名稱與說明；"
                    "官方名稱與說明寫在 11029「諾亞金鈴碎片」及其說明。"
                    "本列介紹錄 11029 原文。專武依所屬英雄屬於森之少女（10036），不是牧羊人。"
                )
            elif hid == 15032:
                note = (
                    "碎片說明原文寫「解鎖老闆娘全新專屬裝備」。定義表所屬英雄是 15032，"
                    "本列按所屬英雄歸在 15032，不與老闆娘合成同一人。"
                )
            ff = tuple(component(ex["comp_id"]).get("fightforces") or component(ex["comp_id"]).get("fightforce") or [])
            label = roster_display_name(hid, name)
            # 牧羊人沒有專武列，不會走到這裡；若日後有列，也只標未開放。
            if hid in UNRELEASED_HERO_IDS and "未開放" not in label:
                label = f"{label}（未開放）"
            hero_name = name or label
            weapons.append(
                WeaponRow(
                    hero_id=hid,
                    hero_name=name,
                    hero_label=label,
                    faction=faction,
                    weapon=ex["weapon"],
                    skill=ex["skill"],
                    skill_desc=ex["desc"],
                    ranks=list(ex["ranks"]),
                    self_attr=ex["self_attr"],
                    fightforce=ff,
                    fragment_intro=intro,
                    fragment_intro_note=note,
                    shared_intro=shared_intro,
                    live_url=LIVE_HERO.format(id=hid),
                )
            )
            if faction not in auras and ex.get("auras"):
                auras[faction] = list(ex["auras"])

    if len(weapons) != 35:
        raise ValueError(f"expected 35 weapons, got {len(weapons)}")
    split = Counter(w.faction for w in weapons)
    if split != {"聯盟": 12, "部族": 12, "自然": 11}:
        raise ValueError(f"unexpected faction split {split}")
    noah = next(w for w in weapons if w.weapon == "諾亞金鈴")
    yarn = next(w for w in weapons if w.weapon == "英雄絮語")
    if noah.hero_id != 10036 or yarn.hero_id != 15032:
        raise ValueError("owner checks failed")
    bard = next(w for w in weapons if w.hero_id == 10030)
    inv = next(w for w in weapons if w.hero_id == 10050)
    if "愛情蛊惑" not in bard.skill or "蠱" in bard.skill:
        raise ValueError(f"bard skill wording unexpected: {bard.skill}")
    if inv.weapon != "思維火花" or inv.skill != "共鳴":
        raise ValueError(f"inventor unexpected: {inv.weapon} {inv.skill}")

    verifications = {
        "exclusive_rows": len(hexc),
        "lvup_rows": len(lvup),
        "break_rows": len(brk),
        "upgrade_cost_identical": True,
        "upgrade_attr_identical": True,
        "break_cost_identical": True,
        "break_attr_identical": True,
        "upgrade_cost_items": "各把專屬碎片（道具類型 2，id 隨專武而異）；數量曲線 35 把相同。消耗欄沒有其他道具，也沒有通用專屬裝備碎片 230001。",
        "break_cost_items": "只消耗隕星鐵芯（道具 258，類型 2）；cost1 全表空白。",
        "upgrade_total": upgrade[-1].cumulative,
        "break_total": breakthrough[-1].cumulative,
        "faction_split": dict(split),
        "noah_owner": f"{noah.hero_label}（{noah.hero_id}）",
        "yarn_owner": f"{yarn.hero_label}（{yarn.hero_id}）",
        "unreleased_in_table": [w.hero_id for w in weapons if w.hero_id in UNRELEASED_HERO_IDS],
        "shepherd_has_row": 10029 in hexc_by,
    }
    data = TablesData(
        upgrade=upgrade,
        breakthrough=breakthrough,
        weapons=weapons,
        auras=auras,
        upgrade_total=upgrade[-1].cumulative,
        break_total=breakthrough[-1].cumulative,
        verifications=verifications,
        terms=terms_for(weapons),
    )
    return data


def _hero_display(w: WeaponRow) -> str:
    """Roster label plus id; unnamed heroes (15032) are the id only."""
    if w.hero_name is None:
        return str(w.hero_id)
    return f"{w.hero_label}（{w.hero_id}）"


def _hero_href_public(w: WeaponRow) -> str:
    """Relative link from docs/exclusive.html to a published hero page."""
    if hero_href(w.hero_id):
        return f"heroes/{w.hero_id}.html"
    return ""


def _hero_link_html(w: WeaponRow, terms: list[str]) -> str:
    label = H(_hero_display(w), terms)
    href = _hero_href_public(w)
    if href:
        return f'<a href="{e(href)}">{label}</a>'
    return label


def _hero_link_md(w: WeaponRow) -> str:
    label = _hero_display(w)
    if hero_href(w.hero_id):
        return f"[{label}]({w.live_url})"
    return label


def _unlock_note(row: BreakRow) -> str:
    bits = []
    if row.star_big == 2 and row.star_small == 0:
        bits.append("2 星：解鎖突破效果 1 階（陣營共用光環）")
    if row.star_big == 5 and row.star_small == 0:
        bits.append("5 星：解鎖突破效果 2 階（陣營共用光環）")
    if row.delta_big:
        parts = "、".join(f"{attr_label(a)} {raw(v)}" for a, v in row.delta_big)
        bits.append(f"額外大屬性：{parts}")
    return "；".join(bits)


def _skill_rank_note(row: LevelRow, prev_rank: int | None) -> str:
    if prev_rank is None or row.skill_rank != prev_rank:
        return f"專屬技能 {row.skill_rank} 階"
    return ""


def render_html(data: TablesData) -> str:
    from .render import page_shell, toc_list

    terms = data.terms
    a3, a4, a103, a104 = (attr_label(i) for i in ATTR_IDS)
    title = "Top Heroes Wiki｜專武總表"
    summary = "Top Heroes 專武總表：升級與突破素材、35 把專武的專屬技能，以及素材消耗對能力提升的邊際效果。"

    t1_rows = [
        [e(f"{r.level} 級"), e(raw(r.cost)), e(raw(r.cumulative))]
        for r in data.upgrade
    ]
    t1 = table(["等級（到達該級）", "本級專武碎片", "累計專武碎片"], t1_rows)

    t2_rows = []
    for r in data.breakthrough:
        t2_rows.append([
            e(str(r.step)),
            e(str(r.star_big)),
            e(str(r.star_small)),
            e(f"{r.star_big}-{r.star_small}"),
            e(raw(r.cost)),
            e(raw(r.cumulative)),
            H(_unlock_note(r), terms) if _unlock_note(r) else "—",
        ])
    t2 = table(
        ["步驟", "大星", "小星", "大星-小星", "本步隕星鐵芯", "累計隕星鐵芯", "解鎖／備註"],
        t2_rows,
        mobile="sticky",
    )
    aura_rows = []
    for faction in ("聯盟", "部族", "自然"):
        for star, text in data.auras.get(faction, []):
            aura_rows.append([H(faction, terms), e(f"{star} 星"), H(text, terms)])
    aura_table = table(["陣營", "解鎖星", "光環原文"], aura_rows, mobile="cards")

    t3_rows = []
    for w in data.weapons:
        ranks = "<br>".join(H(r, terms) for r in w.ranks)
        intro = H(w.fragment_intro, terms) if w.fragment_intro else "（沒有對應的碎片說明字串。）"
        if w.fragment_intro_note:
            intro += f"<br>{H(w.fragment_intro_note, terms)}"
        ff = "／".join(str(x) for x in w.fightforce) if w.fightforce else "—"
        t3_rows.append([
            H(w.faction, terms),
            _hero_link_html(w, terms),
            H(w.weapon, terms),
            intro,
            H(w.skill, terms),
            f'<p>{H(w.skill + "：" + w.skill_desc, terms)}</p>{ranks}',
            H(w.self_attr, terms) if w.self_attr else "組件表沒有另列自身屬性",
            e(ff),
        ])
    t3 = table(
        ["陣營", "英雄", "專武", "官方說明", "專屬技能", "技能全文與五階（對應 1／5／10／15／20 級）", "附加自身屬性（原值）", "技能戰力"],
        t3_rows,
        mobile="cards",
        card_title="英雄",
    )

    t4u_rows = []
    prev_rank = None
    for r in data.upgrade:
        note = _skill_rank_note(r, prev_rank)
        t4u_rows.append([
            e(f"{r.level} 級"),
            e(raw(r.cost)),
            e(raw(r.delta_attrs[3])),
            e(raw(r.delta_attrs[4])),
            e(raw(r.delta_attrs[103])),
            e(raw(r.delta_attrs[104])),
            e(raw(r.delta_power)),
            e(ratio(r.delta_power, r.cost)),
            e(note) if note else "—",
        ])
        prev_rank = r.skill_rank
    t4u = table(
        [
            "等級",
            "本級專武碎片",
            f"Δ{a3}",
            f"Δ{a4}",
            f"Δ{a103}",
            f"Δ{a104}",
            "Δ戰力",
            "每碎片Δ戰力（推算）",
            "技能解鎖",
        ],
        t4u_rows,
        mobile="sticky",
    )

    t4b_rows = []
    for r in data.breakthrough:
        big = "、".join(f"{attr_label(a)} {raw(v)}" for a, v in r.delta_big) if r.delta_big else "無"
        t4b_rows.append([
            e(str(r.step)),
            e(f"{r.star_big}-{r.star_small}"),
            e(raw(r.cost)),
            e(raw(r.delta_attrs[3])),
            e(raw(r.delta_attrs[4])),
            e(raw(r.delta_attrs[103])),
            e(raw(r.delta_attrs[104])),
            e(big),
            e(raw(r.delta_power)),
            e(ratio(r.delta_power, r.cost)),
            H(_unlock_note(r), terms) if _unlock_note(r) else "—",
        ])
    t4b = table(
        [
            "步驟",
            "大星-小星",
            "本步隕星鐵芯",
            f"Δ{a3}（小屬性）",
            f"Δ{a4}（小屬性）",
            f"Δ{a103}（小屬性）",
            f"Δ{a104}（小屬性）",
            "額外大屬性增量",
            "Δ戰力",
            "每鐵芯Δ戰力（推算）",
            "解鎖／備註",
        ],
        t4b_rows,
        mobile="sticky",
    )

    toc = toc_list([
        {"label": "簡介", "id": "lead"},
        {"label": "表一、通用升級素材", "id": "t1"},
        {"label": "表二、通用突破素材", "id": "t2"},
        {"label": "突破效果（陣營共用光環）", "id": "t2-aura", "depth": 1},
        {"label": "表三、所有英雄專武", "id": "t3"},
        {"label": "表四、素材消耗對能力提升的邊際效果", "id": "t4"},
        {"label": "升級邊際", "id": "t4-up", "depth": 1},
        {"label": "突破邊際", "id": "t4-br", "depth": 1},
        {"label": "資料說明", "id": "notes"},
    ])

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">本頁列出 35 把專武的升級素材、突破素材、各把專屬技能，以及素材消耗對能力提升的邊際效果。</p>
    </header>
    {toc}
    <section id="lead">
      <h2>簡介</h2>
      <p>升級和突破是兩條獨立軌道，介面分別叫「{H('裝備屬性', terms)}」和「{H('突破屬性', terms)}」。兩套表、兩種消耗、兩組屬性；表上沒有合計列，本頁也不把兩條軌道加總成官方合計。屬性只錄原值，不是面板上的百分比。</p>
      <p>35 把專武的升級與突破素材數量、屬性曲線都相同，突破效果則依陣營套用聯盟／自然／部族的共用光環。升級 1 至 20 級相加共 {comma(data.upgrade_total)} 個專武碎片；突破 25 步相加共 {comma(data.break_total)} 個{H('隕星鐵芯', terms)}。排列依本站英雄目錄：聯盟 → 自然 → 部族（聯盟 12、自然 11、部族 12）。{H('牧羊人', terms)}標為未開放，但沒有專武列，因此不出現在表三。{H('諾亞金鈴', terms)}屬於{H('森之少女', terms)}。{H('英雄絮語', terms)}屬於 15032。</p>
    </section>
    <section id="t1">
      <h2>表一、通用升級素材</h2>
      <p>等級指升級後的專武等級。本級專武碎片是到達該級時的消耗（第 1 級為 5）。累計是第 1 級到該級相加。本表只記數量，不區分各把專屬碎片名稱。{H('通用專屬裝備碎片', terms)}的官方說明寫「{H(t('goods_desc_230001'), terms)}」它不在升級消耗欄，本表不把它寫成必消耗列。表上沒有單獨的解鎖數量欄；第 1 級就要 5 個，是否包含解鎖，此處不下結論。</p>
      {t1}
    </section>
    <section id="t2">
      <h2>表二、通用突破素材</h2>
      <p>突破每把 25 步，大星 0–5、小星 0–4（從 0 星 1 小星走到 5 星 0 小星），只消耗{H('隕星鐵芯', terms)}。本步是該步消耗，累計是第 1 步到該步相加。2 星（第 10 步）與 5 星（第 25 步）解鎖突破效果，已在解鎖欄標出。到達 1／2／3／4／5 星該步的隕星鐵芯分別是 20／60／120／160／200，這是單步消耗，不是累計。</p>
      {t2}
      <section id="t2-aura">
        <h3>突破效果（陣營共用光環）</h3>
        <p>突破效果是依專武所屬陣營套用的共用光環，不是某一把獨有的說明。介面標籤是「{H('突破專屬', terms)}」。原文如下。</p>
        {aura_table}
      </section>
    </section>
    <section id="t3">
      <h2>表三、所有英雄專武</h2>
      <p>共 35 列。「官方說明」錄各把碎片說明原文；全體另有共用字串「{H(data.weapons[0].shared_intro, terms)}」。技能全文與五階照原文列出，不改寫成一句滿級描述。附加自身屬性只錄原值。英雄名連到本站對應條目；15032 只顯示編號。</p>
      {t3}
    </section>
    <section id="t4">
      <h2>表四、素材消耗對能力提升的邊際效果</h2>
      <p>此表列的是<strong>本級／本步增量</strong>，不是累計值。第 1 級、第 1 步的增量等於該檔相對 0 的數值。{H(a103, terms)}、{H(a104, terms)}的增量同樣只錄原值，不換算成百分比。額外大屬性沒有加進小屬性欄，所以突破表另列「額外大屬性增量」。每碎片Δ戰力、每鐵芯Δ戰力是本級（本步）Δ戰力除以該檔素材量，屬於依分欄推算，不是資料表原有欄位。升級與突破兩表不合併加總。</p>
      <section id="t4-up">
        <h3>升級邊際</h3>
        {t4u}
      </section>
      <section id="t4-br">
        <h3>突破邊際</h3>
        {t4b}
      </section>
    </section>
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>資料出自遊戲資料表與官方字串，資料截至 {DATA_CUTOFF}（香港時間）。</li>
        <li>名稱、技能、光環與介面標籤都照官方字串。吟遊詩人專屬技能官方寫法是「{H('愛情蛊惑', terms)}」（蛊，不是蠱）；後續升級原文若寫「蠱」，仍照錄。發明家專武是「{H('思維火花', terms)}」，專屬技能是「{H('共鳴', terms)}」。</li>
        <li>屬性名稱依字串鍵寫成{H(a3, terms)}、{H(a4, terms)}、{H(a103, terms)}、{H(a104, terms)}。只錄原值，不把{H(a103, terms)}、{H(a104, terms)}自行 ÷100 寫成百分比；這條只用於專武屬性，不改變已鎖定的英雄天賦、造型顯示規則。{H('牧羊人', terms)}（10029）沒有專武列；{H('諾亞金鈴', terms)}依對應英雄屬於{H('森之少女', terms)}（10036）；{H('英雄絮語', terms)}屬於 15032。</li>
        <li>不把突破季節、伺服器名單或介面字串「{e(t('exclusive_break_01'))}」自行標成未開放。本頁沒有社群備註，也沒有把猜測寫進正文。可見正文「所屬英雄」原欄名 <code>use_hero</code>。諾亞金鈴碎片官方名稱與說明鍵是 <code>goods_name_11029</code>／<code>goods_desc_11029</code>；升級消耗道具 11036 在字串表沒有 <code>goods_name_11036</code>／<code>goods_desc_11036</code>。</li>
      </ul>
    </section>
    """
    return page_shell(title, summary, body, depth=0, nav_current="codex")


def render_exclusive_page(data: TablesData | None = None) -> str:
    return render_html(data or load_tables_data())


def render_markdown(data: TablesData) -> str:
    a3, a4, a103, a104 = (attr_label(i) for i in ATTR_IDS)
    lines: list[str] = []
    add = lines.append
    add("# Top Heroes Wiki｜專武四表（未發佈樣板）")
    add("")
    add("這是未發佈的本機草稿，只供預覽，**不是**線上目錄，也尚未列入公開圖鑑。資料截至 " + DATA_CUTOFF + "（香港時間）。")
    add("")
    add("## 核對說明")
    add("")
    add("- 升級消耗數量、升級屬性、升級戰力、突破消耗、突破小屬性、額外大屬性與突破戰力，35 把完全相同。突破效果依陣營分為聯盟／部族／自然三組共用光環，不是每把一段獨特說明。")
    add("- 升級消耗欄只有專屬碎片（道具類型 2），沒有第二種道具。表一、表四升級側只記數量，不區分各把碎片名稱。通用專屬裝備碎片（230001）官方說明寫「" + t("goods_desc_230001") + "」它不在升級消耗欄，本表不把它寫成必消耗列。")
    add("- 突破只消耗隕星鐵芯（258），cost1 全表空白。升級 1 至 20 級相加共 " + comma(data.upgrade_total) + " 個專武碎片；突破 25 步相加共 " + comma(data.break_total) + " 個隕星鐵芯。")
    add("- 升級和突破是兩條獨立軌道，介面分別叫「裝備屬性」和「突破屬性」。表上沒有合計列。本頁不把兩條軌道加總成官方合計。")
    add("- 屬性只錄原值，不是面板上的百分比。名稱為" + a3 + "、" + a4 + "、" + a103 + "、" + a104 + "。編號與 ÷100 換算見資料說明。")
    add("- 表三排列依本站英雄目錄（手冊 01–03 名單總覽）：聯盟 → 自然 → 部族，只列定義表有專武的 35 人（聯盟 12、自然 11、部族 12）。牧羊人是唯一標未開放的可收集英雄，但定義表沒有專武列，因此不出現在表三。諾亞金鈴屬於森之少女。英雄絮語屬於 15032。")
    add("")
    add("## 表一、通用升級素材")
    add("")
    add("等級指升級後的專武等級。本級專武碎片是 `exclusive_lvup` 寫在該級的消耗，也就是到達該級時付出的數量（第 1 級為 5）。累計是第 1 級到該級相加。表上沒有單獨的解鎖數量欄；第 1 級就要 5 個，是否包含解鎖，此處不下結論。")
    add("")
    add(md_table(
        ["等級（到達該級）", "本級專武碎片", "累計專武碎片"],
        [[f"{r.level} 級", raw(r.cost), raw(r.cumulative)] for r in data.upgrade],
    ))
    add("")
    add("## 表二、通用突破素材")
    add("")
    add("突破每把 25 步，大星 0–5、小星 0–4（從 0 星 1 小星走到 5 星 0 小星）。本步是該步消耗，累計是第 1 步到該步相加。2 星（第 10 步）與 5 星（第 25 步）解鎖突破效果，已在解鎖欄標出。到達 1／2／3／4／5 星該步的隕星鐵芯分別是 20／60／120／160／200，這是單步消耗，不是累計。")
    add("")
    add(md_table(
        ["步驟", "大星", "小星", "大星-小星", "本步隕星鐵芯", "累計隕星鐵芯", "解鎖／備註"],
        [[
            str(r.step),
            str(r.star_big),
            str(r.star_small),
            f"{r.star_big}-{r.star_small}",
            raw(r.cost),
            raw(r.cumulative),
            _unlock_note(r) or "—",
        ] for r in data.breakthrough],
    ))
    add("")
    add("### 突破效果（陣營共用光環）")
    add("")
    add("突破效果是依專武所屬陣營套用的共用光環，不是某一把獨有的說明。介面標籤是「突破專屬」。")
    add("")
    aura_md = []
    for faction in ("聯盟", "部族", "自然"):
        for star, text in data.auras.get(faction, []):
            aura_md.append([faction, f"{star} 星", text])
    add(md_table(["陣營", "解鎖星", "光環原文"], aura_md))
    add("")
    add("## 表三、所有英雄專武")
    add("")
    add("共 35 條。定義表沒有獨立的專武介紹欄；各條「官方說明」錄碎片說明原文，全體另有共用字串「" + data.weapons[0].shared_intro + "」。技能全文與五階照資料表原文。為方便手機閱讀，本表在 Markdown 裡改成逐把分列，內容與 HTML 表三相同，沒有省略。英雄名連到已上線條目。")
    add("")
    current_faction = None
    for w in data.weapons:
        if w.faction != current_faction:
            current_faction = w.faction
            add(f"### {current_faction}")
            add("")
        add(f"#### {w.weapon}（{_hero_link_md(w)}）")
        add("")
        add(f"- 陣營：{w.faction}")
        add(f"- 英雄：{_hero_link_md(w)}")
        add(f"- 專武：{w.weapon}")
        add(f"- 官方說明：{w.fragment_intro or '（此把沒有對應的碎片說明字串。）'}")
        if w.fragment_intro_note:
            add(f"- 說明備註：{w.fragment_intro_note}")
        add(f"- 專屬技能：{w.skill}")
        add(f"- 附加自身屬性：{w.self_attr or '組件表沒有另列自身屬性'}（原值，不換算成百分比）")
        ff = "／".join(str(x) for x in w.fightforce) if w.fightforce else "—"
        add(f"- 技能戰力：{ff}")
        add("- 技能全文與五階（對應專武 1／5／10／15／20 級）：")
        add(f"  - 技能原文：{w.skill}：{w.skill_desc}")
        for r in w.ranks:
            for i, line in enumerate(r.split("\n")):
                prefix = "  - " if i == 0 else "    "
                add(prefix + line)
        add("")
    add("## 表四、素材消耗對能力提升的邊際效果")
    add("")
    add("此表列的是本級／本步增量，不是累計值。第 1 級、第 1 步的增量等於該檔相對 0 的數值。103／104 的增量同樣只錄原值。額外大屬性沒有加進小屬性欄。每碎片Δ戰力／每鐵芯Δ戰力是本級（本步）Δ戰力除以該檔素材量，屬於依分欄推算，不是資料表原有欄位。升級與突破兩表不合併加總。")
    add("")
    add("### 升級邊際")
    add("")
    prev_rank = None
    urows = []
    for r in data.upgrade:
        note = _skill_rank_note(r, prev_rank) or "—"
        urows.append([
            f"{r.level} 級",
            raw(r.cost),
            raw(r.delta_attrs[3]),
            raw(r.delta_attrs[4]),
            raw(r.delta_attrs[103]),
            raw(r.delta_attrs[104]),
            raw(r.delta_power),
            ratio(r.delta_power, r.cost),
            note,
        ])
        prev_rank = r.skill_rank
    add(md_table(
        ["等級", "本級專武碎片", f"Δ{a3}", f"Δ{a4}", f"Δ{a103}", f"Δ{a104}", "Δ戰力", "每碎片Δ戰力（推算）", "技能解鎖"],
        urows,
    ))
    add("")
    add("### 突破邊際")
    add("")
    brows = []
    for r in data.breakthrough:
        big = "、".join(f"{attr_label(a)} {raw(v)}" for a, v in r.delta_big) if r.delta_big else "無"
        brows.append([
            str(r.step),
            f"{r.star_big}-{r.star_small}",
            raw(r.cost),
            raw(r.delta_attrs[3]),
            raw(r.delta_attrs[4]),
            raw(r.delta_attrs[103]),
            raw(r.delta_attrs[104]),
            big,
            raw(r.delta_power),
            ratio(r.delta_power, r.cost),
            _unlock_note(r) or "—",
        ])
    add(md_table(
        ["步驟", "大星-小星", "本步隕星鐵芯", f"Δ{a3}（小屬性）", f"Δ{a4}（小屬性）", f"Δ{a103}（小屬性）", f"Δ{a104}（小屬性）", "額外大屬性增量", "Δ戰力", "每鐵芯Δ戰力（推算）", "解鎖／備註"],
        brows,
    ))
    add("")
    add("## 資料說明")
    add("")
    add("- 名稱、技能、光環與介面標籤都照官方字串。吟遊詩人專屬技能官方寫法是「愛情蛊惑」（蛊，不是蠱）。發明家專武是「思維火花」，專屬技能是「共鳴」。")
    add("- 不把 break_season、break_server 或介面字串「" + t("exclusive_break_01") + "」自行標成未開放。本頁沒有社群備註，也沒有把猜測寫進正文。")
    add("- 本頁未列入公開目錄，也沒有接入網站組建腳本。")
    add("")
    return "\n".join(lines)
