from __future__ import annotations

from .assemble import HeroPage, hero_href, official_stars
from .highlight import highlight, highlight_lines
from .htmlutil import e, table, tag
from .overrides import (
    CODEX_ITEMS,
    PAGE_IDS,
    PUBLISH_IDS,
    ROSTER,
    UNRELEASED_HERO_IDS,
    roster_display_name,
)
from .paths import DATA_CUTOFF
from .strings import t


STAR_PATH = "M12 2.2l2.72 6.36 6.93.74-5.2 4.86 1.48 6.82L12 17.7l-5.93 3.28 1.48-6.82-5.2-4.86 6.93-.74L12 2.2z"
STAR_LABEL = {"gold": "金色", "red": "紅色", "white": "白色"}


def star_icon(tint: str, size: int = 16) -> str:
    return (
        f'<svg class="star star-{tint}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'aria-hidden="true" focusable="false"><path d="{STAR_PATH}"/></svg>'
    )


def star_row(tint: str, count: int, size: int = 16) -> str:
    icons = "".join(star_icon(tint, size) for _ in range(count))
    return f'<span class="star-row" aria-label="{STAR_LABEL[tint]}{count}星">{icons}</span>'


def star_max_block() -> str:
    return (
        '<span class="star-max">'
        + star_row("gold", 5)
        + star_row("red", 5)
        + star_row("white", 5)
        + "<span>金 5＋紅 5＋白 5（上限 15 星）</span></span>"
    )


def H(text: str, terms) -> str:
    return highlight(text, terms)


def asset_prefix(depth: int) -> str:
    return "" if depth == 0 else "../" * depth


def site_nav_items(prefix: str) -> list[tuple[str, str, str]]:
    """Shared top nav: home plus in-page index anchors. No per-hero links."""
    home = f"{prefix}index.html"
    items = [
        ("index", home, "首頁"),
        ("heroes", f"{home}#heroes", "英雄"),
    ]
    for faction, anchor, _heroes in ROSTER:
        items.append((anchor, f"{home}#{anchor}", faction))
    items += [
        ("codex", f"{home}#codex", "圖鑑"),
        ("about", f"{home}#about", "關於本站"),
    ]
    return items


def page_shell(title: str, summary: str, body: str, depth: int, nav_current: str = "") -> str:
    prefix = asset_prefix(depth)
    nav_html = []
    for key, href, label in site_nav_items(prefix):
        cls = ' class="current"' if key == nav_current else ""
        nav_html.append(f'<a href="{href}"{cls}>{e(label)}</a>')
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)}</title>
  <meta name="description" content="{e(summary)}">
  <link rel="stylesheet" href="{prefix}assets/css/site.css">
</head>
<body id="top">
  <a class="skip" href="#main">跳到本文</a>
  <header class="site-header">
    <div class="inner">
      <a class="site-title" href="{prefix}index.html">Top Heroes Wiki</a>
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


def skill_blocks(skills: list[dict], terms) -> str:
    out = []
    for sk in skills:
        ups = ""
        if sk.get("upgrades"):
            ups = "<ul>" + "".join(f"<li>{H(u, terms)}</li>" for u in sk["upgrades"]) + "</ul>"
        out.append(
            f'<details class="skill"><summary>{H(sk["heading"], terms)}</summary>'
            f'<p>{H(sk["text"], terms)}</p>{ups}</details>'
        )
    return "\n".join(out)


def lead_placeholder(*, card: bool = False) -> str:
    """Reserved portrait slot. No image file, no broken <img>, no invented art."""
    cls = "lead-art lead-placeholder"
    if card:
        cls += " lead-placeholder-card"
        return (
            f'<span class="{cls}">'
            '<span class="lead-frame" role="img" aria-label="頭像位置，待補">'
            "<span>頭像<br>待補</span></span></span>"
        )
    return (
        f'<figure class="{cls}">'
        '<div class="lead-frame" role="img" aria-label="頭像位置，待補">'
        "<span>頭像（待補）</span></div>"
        "<figcaption>頭像位置，以後再補</figcaption></figure>"
    )


def render_hero(page: HeroPage, depth: int = 1) -> str:
    terms = page.terms
    name = page.name
    toc = [
        {"label": "簡介", "id": "lead"},
        {"label": "技能與覺醒", "id": "skills"},
        {"label": "英雄升星與技能星", "id": "star-skills", "depth": 1},
        {"label": "覺醒階段", "id": "awaken", "depth": 1},
        {"label": f"專武{page.exclusive_name}" if page.exclusive_name else "專武", "id": "exclusive"},
        {"label": "英靈與天賦", "id": "spirit-talents"},
        {"label": "外觀", "id": "appearance"},
    ]
    for sec in page.skin_feature_sections:
        toc.append({"label": sec["heading"], "id": sec["id"], "depth": 1})
    if page.suits:
        toc.append({"label": "收集套裝", "id": "skin-suits", "depth": 1})
    toc += [
        {"label": "建議裝備*", "id": "gear"},
        {"label": "羈絆與相關條目", "id": "bonds"},
        {"label": "資料說明", "id": "notes"},
        {"label": "社群備註", "id": "community"},
    ]

    # lead
    tag_s = "、".join(page.tags)
    first = page.first_tag
    props = [
        ("陣營", H(page.faction, terms)),
        ("英雄屬性", H(tag_s, terms)),
        (first["name"], H(first["dec"], terms)),
    ]
    for sg in page.second_tags:
        props.append((sg["name"], H(f"{sg['dec']}（無百分比；玩家確認面板，非表上每人欄位）", terms)))
    props += [
        ("狀態", e(page.status)),
        ("專武（資料表）", H(page.exclusive_name, terms) if page.exclusive_name else "無"),
        ("英靈", H(page.spirit_name, terms) if page.spirit_name else "資料表沒有英靈列"),
        ("星級上限", star_max_block()),
    ]
    lead = f"""
    <section id="lead">
      <h2>簡介</h2>
      <p>{H(page.intro, terms)}</p>
      <div class="lead-grid">
        {lead_placeholder()}
        {properties(props)}
      </div>
    </section>
    """

    # skills
    src_rows = [[H(a, terms), H(b, terms)] for a, b in page.skill_sources]
    skill_intro = (
        f"以下先用遊戲裡「技能升級」的方式，對上英雄星與技能星；各技能全文與升級加成仍照資料表原文列出，不另行改寫成一句滿級描述。"
    )
    if page.exclusive:
        skill_intro += f"{page.exclusive['skill']}是專武「{page.exclusive['weapon']}」的專屬技能，"
    if page.spirit:
        skill_intro += f"{page.spirit['skill']}是英靈「{page.spirit['name']}」的專屬技能，"
    # awaken names
    aw_names = [s["heading"].split("（")[0] for s in page.awaken_skills]
    if aw_names:
        if len(aw_names) == 2:
            skill_intro += f"{aw_names[0]}與{aw_names[1]}則屬於覺醒，分別寫在對應區塊。"
        else:
            skill_intro += "覺醒技能寫在對應區塊。"
    if not page.spirit:
        skill_intro += "資料表沒有" + page.name + "的英靈列，因此沒有英靈專屬技能。"

    track_html = []
    for tr in page.star_tracks:
        rows = [[star_row(tr["tint"], it["count"]), H(it["text"], terms)] for it in tr["items"]]
        track_html.append(f'<h4>{e(tr["heading"])}</h4>' + table(["英雄星（介面）", "技能升級"], rows))

    aw_rows = []
    for r in page.awaken_rows:
        aw_rows.append([
            e(r["stage"]),
            H(r["name"], terms),
            highlight_lines(r["dec"], terms),
            H(r["related"], terms),
        ])

    skills = f"""
    <section id="skills">
      <h2>技能與覺醒</h2>
      <p>{H(skill_intro, terms)}</p>
      {table(["技能", "從哪裡來"], src_rows)}
      <section id="star-skills">
        <h3>英雄升星與技能星</h3>
        <p>{H("遊戲介面以金、紅、白三色各 1 至 5 顆星來顯示，對應英雄星 1–5、6–10、11–15。文案格式是「技能名提升至N星」，這裡的 N 是介面上的技能星（1／2／3），不是資料表裡的 skill_level 原值。對照畫面與 hero_star 表（star_sub=0）後，對應如下。", terms)}</p>
        {''.join(track_html)}
        <p>{H("下面是這五個會隨英雄星提升的技能全文，可與上表對到是哪一檔英雄星解鎖哪一階技能星。", terms)}</p>
        {skill_blocks(page.star_skills, terms)}
      </section>
      <section id="awaken">
        <h3>覺醒階段</h3>
        <p>{H("下表是覺醒階段的官方短述；其後再附圖鑑裡的技能全文與升級加成。兩者用字可能略有出入，都照原文保留，不互相改寫。", terms)}</p>
        {table(["階段", "名稱", "官方短述", "關聯技能"], aw_rows)}
        {skill_blocks(page.awaken_skills, terms)}
      </section>
    </section>
    """

    # exclusive
    ex_html = "<p>資料表沒有專武列。</p>"
    if page.exclusive:
        ex = page.exclusive
        if ex["self_attr"]:
            self_line = (
                f"升級專屬技能是{ex['skill']}，寫在下面的專武專屬技能，不當作一般升星或覺醒技能。"
                f"附加自身屬性為{ex['self_attr']}；這是表上原值，不是英雄屬性，不換算成百分比。"
            )
        else:
            self_line = (
                f"升級專屬技能是{ex['skill']}，寫在下面的專武專屬技能，不當作一般升星或覺醒技能。"
                "這項專屬技能在組件表沒有另列自身屬性。"
            )
        aura_p = ""
        if ex["auras"]:
            bits = "；".join(f"{star} 星時，{text}" for star, text in ex["auras"])
            aura_p = (
                f"<p>{H('專武突破在 2 星、5 星解鎖效果，是依專武所屬陣營套用的共用光環，不是' + ex['weapon'] + '這把獨有的說明。' + page.faction + '光環原文：' + bits + '。', terms)}</p>"
            )
        ranks = "<ul>" + "".join(f"<li>{H(r, terms)}</li>" for r in ex["ranks"]) + "</ul>"
        ex_html = f"""
        <p>{H('專武名稱是' + ex['weapon'] + '。' + self_line, terms)}</p>
        <section>
          <h3>專武專屬技能：{H(ex['skill'], terms)}</h3>
          <p>{H(ex['skill'] + '：' + ex['desc'], terms)}</p>
          {ranks}
        </section>
        {aura_p}
        """
    exclusive_sec = f"""
    <section id="exclusive">
      <h2>專武{e(page.exclusive_name or "")}</h2>
      {ex_html}
    </section>
    """

    # spirit + talents
    if page.spirit:
        sp = page.spirit
        ff = sp.get("fightforce") or []
        if isinstance(ff, list):
            ff_s = "／".join(str(x) for x in ff)
        else:
            ff_s = str(ff)
        spirit_html = f"""
        <section>
          <h3>英靈{H(sp['name'], terms)}</h3>
          <p>{H(f"{sp['name']}是{page.name}的英靈。專屬技能是{sp['skill']}，寫在下面的英靈專屬技能，不當作一般升星或覺醒技能。技能戰力為 {ff_s}。滿級第 6 項專屬屬性是技能減傷 {sp['reduce_rows'][-1][1]}（表上原值，不是英雄屬性，不換算成百分比）。關鍵等級原值（1／25／50／75／100）見下表。", terms)}</p>
          {table(["等級", "技能減傷（原值）"], [[e(a), e(b)] for a, b in sp["reduce_rows"]])}
          <section>
            <h4>英靈專屬技能：{H(sp['skill'], terms)}</h4>
            <p>{H(sp['skill'] + '：' + sp['desc'], terms)}</p>
            <ul>{''.join(f'<li>{H(r, terms)}</li>' for r in sp['ranks'])}</ul>
          </section>
        </section>
        """
    else:
        spirit_html = f"<p>{H('hero_valhalla.json 沒有' + page.name + '的英靈列，本頁不虛擬英靈或英靈專屬技能。', terms)}</p>"

    tal_rows = []
    for r in page.talents:
        tal_rows.append([
            e(r["slot"]),
            H(r["name"], terms),
            H(r["attr"], terms),
            e(r["lv1"]),
            e(r["lv30"]),
            H(r["note"], terms),
        ])
    spirit_sec = f"""
    <section id="spirit-talents">
      <h2>英靈與天賦</h2>
      {spirit_html}
      <section>
        <h3>天賦</h3>
        <p>{H(page.talent_intro, terms)}</p>
        {table(["槽位", "名稱", "屬性", "1 級", "30 級", "說明"], tal_rows)}
      </section>
    </section>
    """

    # appearance
    attr_rows = [[H(s["name"], terms), H(s["collect"], terms) if s["collect"] != "無" else "無", H(s["equip"], terms) if s["equip"] != "無" else "無"] for s in page.skins]
    unlock_rows = [[H(s["name"], terms), e(s["id"]), H(s["unlock"], terms) if s["unlock"] != "無" else "無", e(s["coins"])] for s in page.skins]
    feat_html = []
    for sec in page.skin_feature_sections:
        body = "".join(f"<p>{H(p, terms)}</p>" for p in sec["paragraphs"])
        star_t = ""
        if sec.get("star_table"):
            star_t = table(["星級", "收集屬性"], [[e(a), H(b, terms)] for a, b in sec["star_table"]])
        after = "".join(f"<p>{H(p, terms)}</p>" for p in sec.get("after") or [] if p)
        feat_html.append(f'<section id="{e(sec["id"])}"><h3>{H(sec["heading"], terms)}</h3>{body}{star_t}{after}</section>')
    suit_html = ""
    if page.suits:
        belong = "，".join(f"{su['skins'][0] if len(su['skins'])==1 else '、'.join(su['skins'])}屬{su['name']}" for su in page.suits)
        # actually each suit lists this hero's member skins
        belong_bits = []
        for su in page.suits:
            for sn in su["skins"]:
                belong_bits.append(f"{sn}屬{su['name']}")
        rows = []
        for su in page.suits:
            for r in su["rows"]:
                rows.append([H(su["name"], terms), e(r["condition"]), H(r["effect"], terms)])
        suit_html = f"""
        <section id="skin-suits">
          <h3>收集套裝</h3>
          <p>{H("收集套裝在另一張表，啟用條件照錄，不把後檔當成前檔的增量。" + "，".join(belong_bits) + "。", terms)}</p>
          {table(["套裝", "條件", "效果"], rows)}
        </section>
        """
    appear_noart = (
        "以下只列出官方表的外觀名稱、解鎖來源與效果，不配 2D 立繪，也不使用 Fandom／社群立繪。"
        "頭像位置已預留，稍後再補。本頁不推測目前面板顯示的是哪一套外觀。"
        "解鎖文案依官方字串。"
    )
    appear_sec = f"""
    <section id="appearance">
      <h2>外觀</h2>
      <p>{H("可收集造型有收集屬性（介面標籤；對應表上隊伍屬性，擁有即可生效），部分還有裝備屬性（介面標籤；對應自身屬性）。數值都是原值，不自行換算成百分比。覺醒造型沒有這兩欄。升星、成對、賽季與收集套裝寫在下方分節，不是單套外觀自己的欄位。", terms)}</p>
      <p>{H(appear_noart, terms)}</p>
      {table(["名稱", "收集屬性", "裝備屬性"], attr_rows)}
      {table(["名稱", "編號", "解鎖來源", "時裝幣"], unlock_rows)}
      {''.join(feat_html)}
      {suit_html}
    </section>
    """

    # gear
    if page.gear:
        rows = "".join(
            f'<div class="gear-row"><h3>{e(k)}</h3><p>{H(v, terms)}</p></div>'
            for k, v in page.gear["rows"]
        )
        extra = f"<p>{H(page.gear['extra'], terms)}</p>" if page.gear.get("extra") else ""
        gear_sec = f"""
        <section id="gear">
          <h2>建議裝備*</h2>
          <aside class="callout" aria-label="推算／非官方">
            <strong>推算／非官方</strong>
            <p>建議裝備是依技能、專武、覺醒、英靈、天賦，再搭配英雄屬性做的整體推算，不是只看英雄屬性，也不是已鎖定的客戶端傷害模擬。下列主線與原因照錄已發布的聯盟圖鑑，不另行改主線。</p>
          </aside>
          <div class="gear-list">{rows}</div>
          <p>{H(page.gear['why'], terms)}</p>
          {extra}
          <p>{H("*建議裝備是推算，不是官方最佳裝備。主線與備選照錄已發布的聯盟圖鑑，不另行改寫。", terms)}</p>
        </section>
        """
    else:
        gear_sec = """
        <section id="gear">
          <h2>建議裝備*</h2>
          <aside class="callout"><strong>推算／非官方</strong><p>本英雄尚未寫入建議裝備。建議裝備須依英靈、專武、技能、覺醒、天賦整體推算，不會只看英雄屬性。</p></aside>
        </section>
        """

    # bonds
    missing = []
    bond_items = []
    for b in page.bonds:
        names = []
        for m in b["members"]:
            if m["id"] not in PAGE_IDS and m["id"] != page.hero_id:
                missing.append(m["name"])
        bond_items.append(f"<li>{H(b['text'], terms)}</li>")
    missing = list(dict.fromkeys(missing))
    miss_p = ""
    if missing:
        miss_p = f"<p>{H('、'.join(missing) + '尚無獨立條目，本靜態站目前只公開已生成的英雄頁。羈絆數值仍是表上的原始點數，不換算成百分比。', terms)}</p>"
    else:
        miss_p = f"<p>{H('羈絆數值仍是表上的原始點數，不換算成百分比。', terms)}</p>"
    rec_p = f"<p>{H(page.rec_text, terms)}</p>" if page.rec_text else ""
    # internal links only
    cards = ['<a class="card" href="../index.html"><strong>Top Heroes Wiki</strong><span>總目錄</span></a>']
    for hid in PUBLISH_IDS:
        if hid != page.hero_id:
            from .assemble import hero_name as _hn
            cards.append(
                f'<a class="card" href="{hid}.html"><strong>Top Heroes Wiki｜{_hn(hid)}</strong><span>英雄條目</span></a>'
            )
    bonds_sec = f"""
    <section id="bonds">
      <h2>羈絆與相關條目</h2>
      {miss_p}
      <ul>{''.join(bond_items)}</ul>
      {rec_p}
      <div class="cards">{''.join(cards)}</div>
    </section>
    """

    notes_sec = f"""
    <section id="notes">
      <h2>資料說明</h2>
      <p>{H(page.notes, terms)}</p>
    </section>
    """
    comm = page.community or "本頁暫無社群備註。"
    comm_sec = f"""
    <section id="community">
      <h2>社群備註（非資料表）</h2>
      <p>{H(comm, terms)}</p>
    </section>
    """

    title = f"Top Heroes Wiki｜{name}"
    summary = (
        f"{name}的英雄條目：{page.faction}{first['name']}，英雄屬性為{tag_s}。"
        + (f"{first['name']}效果為{first['locked']}。" if first.get("locked") else "")
        + "建議裝備為推算，不是官方列。"
    )
    body = (
        f"    <header class=\"entry-head\"><h1>{e(title)}</h1></header>\n"
        + toc_list(toc)
        + lead + skills + exclusive_sec + spirit_sec + appear_sec + gear_sec + bonds_sec + notes_sec + comm_sec
    )
    return page_shell(title, summary, body, depth=depth, nav_current="")


def render_roster_item(hero_id: int, name: str | None) -> str:
    label = roster_display_name(hero_id, name)
    if hero_id in PAGE_IDS:
        return f'<li><a href="heroes/{hero_id}.html">{e(label)}</a></li>'
    # Unreleased-in-game (牧羊人) is labelled in the name; do not also mark 尚未公開.
    status = ""
    if hero_id not in UNRELEASED_HERO_IDS:
        status = ' <span class="wiki-status">尚未公開</span>'
    return f'<li><span>{e(label)}</span>{status}</li>'


def render_home(heroes: list[HeroPage] | None = None) -> str:
    del heroes  # roster comes from the locked index, not assembled pages
    factions = []
    for faction, anchor, entries in ROSTER:
        items = "".join(render_roster_item(hid, name) for hid, name in entries)
        factions.append(
            f'<section id="{anchor}">'
            f"<h3>{e(faction)}</h3>"
            f'<ul class="hero-roster">{items}</ul>'
            "</section>"
        )
    codex = "".join(f"<li>{e(item)}</li>" for item in CODEX_ITEMS)
    body = f"""
    <header class="entry-head">
      <h1>Top Heroes Wiki</h1>
      <p class="lede">Top Heroes 英雄 wiki。目前先公開審判官和修女，其他英雄已列在目錄裡，條目會陸續補上。</p>
    </header>
    <section id="heroes">
      <h2>英雄</h2>
      {''.join(factions)}
    </section>
    <section id="codex">
      <h2>圖鑑</h2>
      <p>以下分類稍後再補。</p>
      <ul class="codex-index">{codex}</ul>
    </section>
    <section id="about">
      <h2>關於本站</h2>
      <ul>
        <li>這是繁體中文的英雄 wiki，不是官方網站。</li>
        <li>英雄條目會介紹技能與覺醒、專武、英靈與天賦、外觀、建議裝備和羈絆。</li>
        <li>數值以遊戲裡看到的為準。建議裝備只是參考，不是官方指定。</li>
      </ul>
    </section>
    """
    return page_shell("Top Heroes Wiki", "Top Heroes 英雄 wiki 總目錄。目前已公開審判官與修女兩條。", body, depth=0, nav_current="index")
