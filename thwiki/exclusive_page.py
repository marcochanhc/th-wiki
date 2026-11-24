"""Render a local-only exclusive-weapon wiki page.

This is not wired into build.py. Preview HTML belongs under preview/,
outside the GitHub Pages docs/ tree.
"""

from __future__ import annotations

from dataclasses import dataclass

from .assemble import assemble, hero_href
from .highlight import highlight
from .htmlutil import e, table
from .paths import DATA_CUTOFF
from .render import site_nav_items
from .strings import t
from .tables import catalog, load_table


# Official names via attribute_name_{id}. Do not follow attribute.json's
# name pointer for 3 / 4, which points at attribute_name_103 / 104.
ATTR_NAME_KEYS = {
    3: "attribute_name_3",
    4: "attribute_name_4",
    103: "attribute_name_103",
    104: "attribute_name_104",
    26: "attribute_name_26",
}

UPGRADE_KEY_LEVELS = (1, 5, 10, 15, 20)
# 1 / 2 / 3 / 4 / 5 星 (star_small == 0). 4 星 is included because
# attribute_big 英雄生命 6000 lands there, not only at the skill-style 1/2/3/5 set.
BREAK_KEY_STARS = (1, 2, 3, 4, 5)

SKILL_LEVEL_BY_RANK = {1: 1, 2: 5, 3: 10, 4: 15, 5: 20}

TERMS = [
    "公正領域",
    "審判官",
    "審判碎片",
    "隕星鐵芯",
    "裝備屬性",
    "突破屬性",
    "突破專屬",
    "專屬技能",
    "專屬裝備",
    "普攻減傷",
    "英雄攻擊",
    "英雄生命",
    "通用專屬裝備碎片",
    "聯盟",
    "審判",
]


def H(text: str) -> str:
    return highlight(text, TERMS)


def attr_label(attr_id: int) -> str:
    key = ATTR_NAME_KEYS.get(attr_id)
    if key:
        return t(key) or str(attr_id)
    return t(f"attribute_name_{attr_id}") or str(attr_id)


def raw_int(value) -> str:
    s = str(value).strip()
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return s
    except ValueError:
        return s


def comma_sum(value) -> str:
    n = int(value)
    return f"{n:,}"


def attr_map(pairs) -> dict[int, str]:
    out = {}
    for item in pairs or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out[int(item[0])] = raw_int(item[1])
    return out


def show_type(attr_id: int):
    row = catalog()["attribute_by_id"].get(int(attr_id)) or {}
    return row.get("show_type")


@dataclass
class ExclusivePreview:
    hero_id: int
    hero_name: str
    faction: str
    weapon: str
    skill: str
    skill_desc: str
    ranks: list[str]
    self_attr: str | None
    auras: list[tuple[int, str]]
    fragment_id: int
    fragment_name: str
    fragment_desc: str
    core_name: str
    core_desc: str
    maxlevel: int
    lvup_rows: list[dict]
    break_rows: list[dict]


def load_exclusive(hero_id: int) -> ExclusivePreview:
    page = assemble(hero_id)
    if not page.exclusive:
        raise ValueError(f"hero {hero_id} has no exclusive weapon in the data tables")
    ex = page.exclusive
    exclusive_row = next(
        (r for r in catalog()["hero_exclusive"] if r.get("use_hero") == hero_id),
        None,
    )
    if not exclusive_row:
        raise ValueError(f"hero_exclusive has no use_hero={hero_id}")
    index = exclusive_row.get("group") or exclusive_row.get("id")
    lvup = load_table("exclusive_lvup")
    brk = load_table("exclusive_break")
    lvup_rows = sorted(
        (r for r in lvup if r.get("index") == index),
        key=lambda r: r["lv"],
    )
    break_rows = sorted(
        (r for r in brk if r.get("index") == index),
        key=lambda r: r["lv"],
    )
    frag_id = ex["fragment"]
    return ExclusivePreview(
        hero_id=hero_id,
        hero_name=page.name,
        faction=page.faction,
        weapon=ex["weapon"],
        skill=ex["skill"],
        skill_desc=ex["desc"],
        ranks=list(ex["ranks"]),
        self_attr=ex["self_attr"],
        auras=list(ex["auras"]),
        fragment_id=frag_id,
        fragment_name=t(f"goods_name_{frag_id}") or str(frag_id),
        fragment_desc=t(f"goods_desc_{frag_id}") or "",
        core_name=t("goods_name_258"),
        core_desc=t("goods_desc_258"),
        maxlevel=int(exclusive_row.get("maxlevel") or 20),
        lvup_rows=lvup_rows,
        break_rows=break_rows,
    )


def preview_shell(title: str, summary: str, body: str, *, css_href: str, home_href: str) -> str:
    nav_html = []
    for _key, href, label in site_nav_items(""):
        # Rewrite built-in docs-relative hrefs onto the preview's home prefix.
        if href.startswith("index.html"):
            href = home_href + href[len("index.html") :]
        nav_html.append(f'<a href="{e(href)}">{e(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(summary)}">
  <link rel="stylesheet" href="{e(css_href)}">
</head>
<body id="top">
  <a class="skip" href="#main">跳到本文</a>
  <header class="site-header">
    <div class="inner">
      <a class="site-title" href="{e(home_href)}">Top Heroes Wiki</a>
      <nav class="site-nav" aria-label="本站">{''.join(nav_html)}</nav>
    </div>
  </header>
  <main id="main" class="page">
{body}
  </main>
  <footer class="site-footer">
    <div class="inner">
      <p>資料截至 {DATA_CUTOFF}（香港時間）。這不是官方 wiki。</p>
      <p><a href="#top">回到頂部</a></p>
    </div>
  </footer>
</body>
</html>
"""


def toc_list(items: list[dict]) -> str:
    lis = []
    for it in items:
        depth = it.get("depth") or 0
        lis.append(f'<li class="d{depth}"><a href="#{e(it["id"])}">{e(it["label"])}</a></li>')
    return f'<nav class="toc" aria-label="本頁章節"><h2>本頁章節</h2><ol>{"".join(lis)}</ol></nav>'


def properties(rows: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<div class="prop"><dt>{e(k)}</dt><dd>{v}</dd></div>' for k, v in rows
    )
    return f'<dl class="props">{items}</dl>'


def art_placeholder(kind: str, caption: str, *, compact: bool = False) -> str:
    cls = "lead-art lead-placeholder"
    if compact:
        cls += " lead-placeholder-card"
        return (
            f'<figure class="{cls}">'
            f'<span class="lead-frame" role="img" aria-label="{e(caption)}">'
            f"<span>{e(kind)}<br>待補</span></span>"
            f"<figcaption>{e(caption)}</figcaption></figure>"
        )
    return (
        f'<figure class="{cls}">'
        f'<div class="lead-frame" role="img" aria-label="{e(caption)}">'
        f"<span>{e(kind)}（待補）</span></div>"
        f"<figcaption>{e(caption)}</figcaption></figure>"
    )


def hero_page_href(hero_id: int, hero_docs: str) -> str | None:
    if hero_href(hero_id):
        return f"{hero_docs.rstrip('/')}/{hero_id}.html"
    return None


def linked_hero(ex: ExclusivePreview, hero_docs: str) -> str:
    href = hero_page_href(ex.hero_id, hero_docs)
    name = H(ex.hero_name)
    if href:
        return f'<a href="{e(href)}">{name}</a>'
    return name


def render_preview(
    ex: ExclusivePreview,
    *,
    css_href: str = "../docs/assets/css/site.css",
    home_href: str = "../docs/index.html",
    hero_docs: str = "../docs/heroes",
) -> str:
    title = f"Top Heroes Wiki｜{ex.weapon}"
    summary = (
        f"{ex.weapon}的專武條目：{ex.faction}英雄{ex.hero_name}的專武，"
        f"專屬技能是{ex.skill}。這是未發佈樣板。"
    )
    hero_link = linked_hero(ex, hero_docs)
    toc = toc_list(
        [
            {"label": "簡介", "id": "lead"},
            {"label": "升級與突破", "id": "tracks"},
            {"label": f"專武專屬技能：{ex.skill}", "id": "skill"},
            {"label": "裝備屬性（升級）", "id": "level-up"},
            {"label": "升級碎片消耗", "id": "level-cost", "depth": 1},
            {"label": "突破屬性", "id": "break"},
            {"label": "突破效果（共用光環）", "id": "break-aura", "depth": 1},
            {"label": "突破小屬性", "id": "break-attrs", "depth": 1},
            {"label": "隕星鐵芯消耗", "id": "break-cost", "depth": 1},
            {"label": "資料說明", "id": "notes"},
        ]
    )

    props = properties(
        [
            ("專武", H(ex.weapon)),
            ("所屬英雄", hero_link),
            ("陣營", H(ex.faction)),
            ("專屬技能", H(ex.skill)),
            ("等級上限", e(str(ex.maxlevel))),
            ("升級消耗", H(ex.fragment_name)),
            ("突破消耗", H(ex.core_name)),
        ]
    )

    lead = f"""
    <section id="lead">
      <h2>簡介</h2>
      <p>{H(ex.weapon)}是{H(ex.faction)}英雄{hero_link}的專武。專屬技能是{H(ex.skill)}。官方字串寫「{H(t('hero_exclusive_02_dec'))}」。資料表把等級上限定為 {e(str(ex.maxlevel))}。</p>
      <div class="lead-grid">
        <div>
          {art_placeholder("武器圖", "武器圖位置，以後再補")}
          {art_placeholder("頭像", "所屬英雄頭像位置，以後再補", compact=True)}
        </div>
        {props}
      </div>
    </section>
    """

    tracks = f"""
    <section id="tracks">
      <h2>升級與突破</h2>
      <p>{H('升級和突破是兩條獨立軌道。兩套表、兩種消耗、兩組屬性，介面分別叫「裝備屬性」和「突破屬性」。表上沒有合計列。若戰鬥裡兩套同時生效，數值應疊加，這是依分欄推算，不是表內加總。')}</p>
    </section>
    """

    self_line = ""
    if ex.self_attr:
        self_line = (
            f"附加自身屬性為{ex.self_attr}；這是表上原值，不是英雄屬性，不換算成百分比。"
        )
    rank_rows = []
    for raw in ex.ranks:
        # ranks are "N 階：…" from the hero-page assembler, already filled.
        if "：" in raw:
            label, text = raw.split("：", 1)
            try:
                rank = int(label.replace("階", "").strip())
            except ValueError:
                rank = len(rank_rows) + 1
        else:
            label, text, rank = raw, raw, len(rank_rows) + 1
        lv = SKILL_LEVEL_BY_RANK.get(rank, "")
        rank_rows.append([e(f"{rank} 階"), e(f"{lv} 級") if lv != "" else "", H(text)])

    skill = f"""
    <section id="skill">
      <h2>專武專屬技能：{H(ex.skill)}</h2>
      <p>{H(ex.skill + '是專武「' + ex.weapon + '」的專屬技能，寫在下面，不當作一般升星或覺醒技能。升級五段對應專武 1／5／10／15／20 級。技能全文與升級加成照資料表原文列出，不另行改寫成一句滿級描述。' + self_line)}</p>
      <p>{H(ex.skill + '：' + ex.skill_desc)}</p>
      {table(["階", "專武等級", "說明"], rank_rows)}
    </section>
    """

    a3, a4, a103, a104 = attr_label(3), attr_label(4), attr_label(103), attr_label(104)
    lv_by = {r["lv"]: r for r in ex.lvup_rows}
    up_rows = []
    for lv in UPGRADE_KEY_LEVELS:
        row = lv_by[lv]
        attrs = attr_map(row.get("attrs") or [])
        skill_rank = ""
        for pair in row.get("skillArr") or []:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                skill_rank = f"{pair[1]} 階"
        up_rows.append([
            e(f"{lv} 級"),
            e(attrs.get(3, "")),
            e(attrs.get(4, "")),
            e(attrs.get(103, "")),
            e(attrs.get(104, "")),
            e(raw_int(row.get("power"))),
            e(skill_rank),
        ])
    frag_total = 0
    cost_cells = []
    for row in ex.lvup_rows:
        qty = 0
        for cost in row.get("costArr") or []:
            if isinstance(cost, (list, tuple)) and len(cost) >= 3:
                qty = int(cost[2])
        frag_total += qty
        cost_cells.append((row["lv"], qty))
    cost_header = ["等級"] + [e(str(lv)) for lv, _ in cost_cells] + ["合計"]
    cost_row = [H(ex.fragment_name)] + [e(str(q)) for _, q in cost_cells] + [e(str(frag_total))]

    level_up = f"""
    <section id="level-up">
      <h2>裝備屬性（升級）</h2>
      <p>{H('介面標籤是「裝備屬性」。四項為' + a3 + ' (3)、' + a4 + ' (4)、' + a103 + ' (103)、' + a104 + ' (104)。3、4 的 show_type 為 ' + str(show_type(3)) + '（點數）；103、104 的 show_type 為 ' + str(show_type(103)) + '。本頁只錄原值，不把 103／104 自行 ÷100 寫成百分比；這與英雄天賦、造型的顯示規則不同。數值是該級累計值，不是單級增量。下表只列技能升階點（1／5／10／15／20 級）。升級屬性曲線 35 把相同。')}</p>
      {table([
        "等級",
        f"{a3} (3)",
        f"{a4} (4)",
        f"{a103} (103)",
        f"{a104} (104)",
        "戰力",
        "技能階",
      ], up_rows)}
      <section id="level-cost">
        <h3>升級碎片消耗</h3>
        <p>{H('升級消耗該專武的專屬碎片「' + ex.fragment_name + '」。消耗曲線 35 把完全相同，只是碎片 id 不同。1 級到 20 級相加共 ' + comma_sum(frag_total) + ' 個。')}</p>
        {table(cost_header, [cost_row])}
      </section>
    </section>
    """

    aura_rows = []
    for star, text in ex.auras:
        aura_rows.append([e(f"{star} 星"), H(text)])
    aura_intro = (
        "專武突破在 2 星、5 星解鎖效果，是依專武所屬陣營套用的共用光環，不是"
        + ex.weapon
        + "這把獨有的說明。介面標籤是「突破專屬」。"
        + ex.faction
        + "光環原文見下表。"
    )

    br_by_star = {
        r["star_big"]: r
        for r in ex.break_rows
        if r.get("star_small") == 0 and r.get("star_big") in BREAK_KEY_STARS
    }
    br_rows_html = []
    for star in BREAK_KEY_STARS:
        row = br_by_star[star]
        small = attr_map(row.get("attrsSmall") or [])
        big_parts = []
        for aid, val in row.get("attrsBig") or []:
            big_parts.append(f"{attr_label(int(aid))} {raw_int(val)}")
        effect = ""
        desc_key = row.get("desc")
        if desc_key:
            effect = t(desc_key) or ""
        br_rows_html.append([
            e(f"{star} 星"),
            e(f"{row['star_big']}-{row['star_small']}"),
            e(small.get(3, "")),
            e(small.get(4, "")),
            e(small.get(103, "")),
            e(small.get(104, "")),
            e("、".join(big_parts) if big_parts else "無"),
            e(raw_int(row.get("power"))),
            H(effect) if effect else e("無"),
        ])

    core_total = 0
    for row in ex.break_rows:
        for cost in row.get("costArr2") or []:
            if isinstance(cost, (list, tuple)) and len(cost) >= 3:
                core_total += int(cost[2])

    # Key-star costs only, plus the documented total.
    key_cost_rows = []
    for star in BREAK_KEY_STARS:
        row = br_by_star[star]
        qty = 0
        for cost in row.get("costArr2") or []:
            if isinstance(cost, (list, tuple)) and len(cost) >= 3:
                qty = int(cost[2])
        key_cost_rows.append([
            e(f"{star} 星"),
            e(f"{row['star_big']}-{row['star_small']}"),
            e(str(qty)),
        ])

    break_sec = f"""
    <section id="break">
      <h2>突破屬性</h2>
      <p>{H('突破每把 25 步，大星 0–5、小星 0–4（從 0 星 1 小星走到 5 星 0 小星），只消耗' + ex.core_name + '。介面標籤是「突破屬性」。')}</p>
      <section id="break-aura">
        <h3>突破效果（共用光環）</h3>
        <p>{H(aura_intro)}</p>
        {table(["解鎖", f"{ex.faction}光環原文"], aura_rows)}
      </section>
      <section id="break-attrs">
        <h3>突破小屬性</h3>
        <p>{H('突破小屬性同樣只錄原值，不把 103／104 自行 ÷100 寫成百分比。數值是該步累計值，不是單步增量。額外大屬性沒有加進小屬性欄，下表另欄列出，不自行加總成官方合計，也不把升級與突破兩表加在一起。下表列出 1 星、2 星、3 星、4 星、5 星；列入 4 星是因為該檔有額外大屬性。曲線 35 把相同。')}</p>
        {table([
          "大星",
          "大星-小星",
          f"{a3} (3)",
          f"{a4} (4)",
          f"{a103} (103)",
          f"{a104} (104)",
          "額外大屬性",
          "戰力",
          "突破效果",
        ], br_rows_html)}
      </section>
      <section id="break-cost">
        <h3>隕星鐵芯消耗</h3>
        <p>{H('官方說明寫：「' + ex.core_desc + '」消耗曲線 35 把完全相同，25 步相加共 ' + comma_sum(core_total) + ' 個。下表只列關鍵星檔到達該檔時的單步消耗，不是累計。')}</p>
        {table(["大星", "大星-小星", ex.core_name], key_cost_rows)}
      </section>
    </section>
    """

    notes = f"""
    <section id="notes">
      <h2>資料說明</h2>
      <ul>
        <li>資料出自 {e('hero_exclusive.json')}、{e('exclusive_lvup.json')}、{e('exclusive_break.json')}、{e('hero_component.json')} 與 {e('strings_zh.json')}。資料截至 {DATA_CUTOFF}（香港時間）。攻略手冊「專武圖鑑」第一版寫於 2026-11-13（香港時間），依同一批資料表整理。</li>
        <li>名稱、技能全文、光環原文與介面標籤都照官方字串填入參數後列出，不改寫成自己的一句話。</li>
        <li>升級和突破是兩條獨立軌道，兩套表、兩種消耗、兩組屬性。表上沒有合計列。上文若寫戰鬥裡可能同時生效、數值應疊加，只是依分欄推算，不是表內加總。</li>
        <li>裝備屬性與突破小屬性都只錄原值。屬性 3、4 的 show_type 為 1（點數），103、104 的 show_type 為 2，但本頁不把 103／104 自行 ÷100 寫成百分比。這條只用於專武屬性，不改變已鎖定的英雄天賦、造型顯示規則。{e('attribute_big')} 沒有加進 {e('attribute_small')}，所以額外大屬性另欄列出。</li>
        <li>屬性名稱依字串鍵 {e('attribute_name_3')}／{e('attribute_name_4')}／{e('attribute_name_103')}／{e('attribute_name_104')}，寫成{H(a3)}、{H(a4)}、{H(a103)}、{H(a104)}。{e('attribute')} 表裡 3、4 的 name 欄指向 {e('attribute_name_103')}／{e('attribute_name_104')}，本頁不跟那一欄改名。</li>
        <li>突破效果是依專武所屬陣營套用的共用光環，不是{H(ex.weapon)}這把獨有的說明。本頁所錄是{H(ex.faction)}光環原文。</li>
        <li>三項定義全表相同的欄位包括等級上限 {e(str(ex.maxlevel))}、{e('unlock_day')} 50、{e('break_server')} 與 {e('break_season')}。表上沒有已推出旗標，不把突破季節或伺服器名單自行標成未開放。介面另有字串「{e(t('exclusive_break_01'))}」（{e('exclusive_break_01')}），此處只記官方字串，不作開放或未開放的結論。</li>
        <li>{H('「' + ex.fragment_name + '」的說明寫：「' + ex.fragment_desc + '」')}表上沒有單獨的解鎖數量欄；升級第 1 級就要 5 個，是否包含解鎖，資料表沒寫清楚，此處不下結論。{H(t('goods_name_230001') + '的說明寫：「' + t('goods_desc_230001') + '」')}升級消耗欄只列專屬碎片，沒有通用碎片可替代的列。</li>
        <li>頭像與武器圖位置已預留，以後再補；目前不放圖，也不使用解包圖示或社群圖。</li>
      </ul>
    </section>
    """

    body = f"""
    <header class="entry-head">
      <h1>{e(title)}</h1>
      <p class="lede">這是未發佈的專武條目樣板，只供本機預覽，尚未列入公開目錄。</p>
    </header>
    {toc}
    {lead}
    {tracks}
    {skill}
    {level_up}
    {break_sec}
    {notes}
    """
    return preview_shell(title, summary, body, css_href=css_href, home_href=home_href)
