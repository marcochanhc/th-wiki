from __future__ import annotations

from .assemble import HeroPage, hero_href, official_stars


def link_cross_heroes(notes_html: str, current_id: int) -> str:
    """Turn the 牧羊人／森之少女 cross mention into a formal in-page link."""
    pairs = {10029: (10036, "森之少女"), 10036: (10029, "牧羊人")}
    if current_id not in pairs:
        return notes_html
    other, name = pairs[current_id]
    href = hero_href(other)
    if not href:
        return notes_html
    span = f'<span class="term">{e(name)}</span>'
    linked = f'<a href="{href}">{span}</a>'
    if span in notes_html:
        return notes_html.replace(span, linked, 1)
    if e(name) in notes_html:
        return notes_html.replace(e(name), f'<a href="{href}">{e(name)}</a>', 1)
    return notes_html


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
        props.append((sg["name"], H(f"{sg['dec']}（官方說明沒有百分比，由玩家在面板確認）", terms)))
    if page.status:
        props.append(("狀態", e(page.status)))
    props += [
        ("專武", H(page.exclusive_name, terms) if page.exclusive_name else "無"),
        ("英靈", H(page.spirit_name, terms) if page.spirit_name else "沒有英靈"),
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
    aw_linked = any("覺醒表關聯" in (s.get("heading") or "") for s in page.awaken_skills)
    if aw_names:
        if aw_linked:
            skill_intro += "覺醒表列出的關聯技能寫在對應區塊。"
        elif len(aw_names) == 2:
            skill_intro += f"{aw_names[0]}與{aw_names[1]}則屬於覺醒，分別寫在對應區塊。"
        else:
            skill_intro += "覺醒技能寫在對應區塊。"
    elif skill_intro.endswith("，"):
        skill_intro = skill_intro[:-1] + "。"
    if not page.spirit:
        skill_intro += page.name + "目前沒有英靈，因此沒有英靈專屬技能。"

    track_html = []
    for tr in page.star_tracks:
        texts = [it.get("text") or "" for it in tr["items"]]
        if texts and all(not str(x).strip() for x in texts):
            empty_msg = "白色星沒有再提升技能。" if tr.get("tint") == "white" else "這一檔沒有再提升技能。"
            track_html.append(f'<h4>{e(tr["heading"])}</h4><p>{H(empty_msg, terms)}</p>')
            continue
        rows = []
        for it in tr["items"]:
            cell = H(it["text"], terms) if str(it.get("text") or "").strip() else "沒有再提升技能"
            rows.append([star_row(tr["tint"], it["count"]), cell])
        track_html.append(f'<h4>{e(tr["heading"])}</h4>' + table(["英雄星（介面）", "技能升級"], rows))

    aw_rows = []
    for r in page.awaken_rows:
        aw_rows.append([
            e(r["stage"]),
            H(r["name"], terms),
            highlight_lines(r["dec"], terms),
            H(r["related"], terms),
        ])

    n_star = len(page.star_skills)
    has_unlock = any("解鎖" in (sk.get("heading") or "") for sk in page.star_skills)
    has_variant = any("技能升級／變體" in (sk.get("heading") or "") for sk in page.star_skills)
    if has_unlock and has_variant:
        star_skill_count_line = (
            f"下面是這{n_star}個技能全文，包括會隨英雄星提升或在指定英雄星解鎖的技能，以及資料表另列的技能升級／變體。"
        )
    elif has_unlock:
        star_skill_count_line = (
            f"下面是這{n_star}個會隨英雄星提升或在指定英雄星解鎖的技能全文，可與上表對到是哪一檔英雄星解鎖哪一階技能星。"
        )
    elif has_variant:
        star_skill_count_line = (
            f"下面是這{n_star}個技能全文，包括會隨英雄星提升的技能，以及資料表另列的技能升級／變體。"
        )
    else:
        star_skill_count_line = (
            f"下面是這{n_star}個會隨英雄星提升的技能全文，可與上表對到是哪一檔英雄星解鎖哪一階技能星。"
        )

    if page.awaken_rows or page.awaken_skills:
        awaken_inner = (
            f'<p>{H("下表是覺醒階段的官方短述；其後再附圖鑑裡的技能全文與升級加成。兩者用字可能略有出入，都照原文保留，不互相改寫。", terms)}</p>'
            + table(["階段", "名稱", "官方短述", "關聯技能"], aw_rows)
            + skill_blocks(page.awaken_skills, terms)
        )
    else:
        awaken_inner = f'<p>{H(page.name + "目前沒有覺醒階段，也沒有覺醒被動或覺醒強化技能。此處不虛擬覺醒內容。", terms)}</p>'

    skills = f"""
    <section id="skills">
      <h2>技能與覺醒</h2>
      <p>{H(skill_intro, terms)}</p>
      {table(["技能", "從哪裡來"], src_rows)}
      <section id="star-skills">
        <h3>英雄升星與技能星</h3>
        <p>{H("遊戲介面以金、紅、白三色各 1 至 5 顆星來顯示，對應英雄星 1–5、6–10、11–15。文案格式是「技能名提升至N星」，這裡的 N 是介面上的技能星（1／2／3）。對應如下。", terms)}</p>
        {''.join(track_html)}
        <p>{H(star_skill_count_line, terms)}</p>
        {skill_blocks(page.star_skills, terms)}
      </section>
      <section id="awaken">
        <h3>覺醒階段</h3>
        {awaken_inner}
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
                f"附加自身屬性為{ex['self_attr']}。這裡先照表上的點數寫，可能與面板上的百分比不同。"
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
        sixth_header = sp.get("sixth_header") or "專屬屬性"
        sixth_rows = sp.get("sixth_rows") or sp.get("reduce_rows") or []
        sixth_max = sixth_rows[-1][1] if sixth_rows else ""
        self_line = ""
        if sp.get("self_attr_text"):
            self_line = sp["self_attr_text"] + "。"
        intro = (
            f"{sp['name']}是{page.name}的英靈。專屬技能是{sp['skill']}，寫在下面的英靈專屬技能，不當作一般升星或覺醒技能。"
            f"技能戰力為 {ff_s}。100 級時，第 6 項專屬屬性{sixth_header}是 {sixth_max}。"
            "1 級時這項是 0.00%。"
            "點數屬性用點數寫，百分比屬性用百分比寫；升級戰力照表上整數書寫，滿級是 627500，遊戲畫面會顯示成 628K。"
            "這套規則只用於英靈屬性，不套到專武、稱號或羈絆。"
            f"{self_line}關鍵等級（1／25／50／75／100）見下表。"
        )
        spirit_html = f"""
        <section>
          <h3>英靈{H(sp['name'], terms)}</h3>
          <p>{H(intro, terms)}</p>
          {table(["等級", H(sixth_header, terms)], [[e(a), e(b)] for a, b in sixth_rows])}
          <section>
            <h4>英靈專屬技能：{H(sp['skill'], terms)}</h4>
            <p>{H(sp['skill'] + '：' + sp['desc'], terms)}</p>
            <ul>{''.join(f'<li>{H(r, terms)}</li>' for r in sp['ranks'])}</ul>
          </section>
        </section>
        """
    else:
        spirit_html = f"<p>{H(page.name + '目前沒有英靈，本頁不虛擬英靈或英靈專屬技能。', terms)}</p>"

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
                sname = su["name"]
                sep = " " if sname and sname[0].isascii() else ""
                belong_bits.append(f"{sn}屬{sep}{sname}")
        rows = []
        for su in page.suits:
            for r in su["rows"]:
                rows.append([H(su["name"], terms), e(r["condition"]), H(r["effect"], terms)])
        suit_html = f"""
        <section id="skin-suits">
          <h3>收集套裝</h3>
          <p>{H("收集套裝的效果只寫當前檔，不加總前面各檔。範圍用「套裝英雄」與「全英雄」。" + "，".join(belong_bits) + "。", terms)}</p>
          {table(["套裝", "條件", "效果"], rows)}
        </section>
        """
    appear_noart = (
        "以下只列出官方表的外觀名稱、解鎖來源與效果，不配 2D 立繪，也不使用 Fandom／社群立繪。"
        "頭像位置已預留，稍後再補。本頁不推測目前面板顯示的是哪一套外觀。"
        "解鎖文案依官方字串。"
    )
    if page.skins:
        appear_body = (
            f'<p>{H("可收集造型有收集屬性與裝備屬性。收集屬性裡，自身欄用該英雄名稱，隊伍欄用「全部」。百分比寫成加號與兩位小數，點數寫成加號、沒有百分號也沒有千分位。覺醒造型沒有這兩欄。升星、成對、賽季與收集套裝寫在下方分節。", terms)}</p>'
            f'<p>{H(appear_noart, terms)}</p>'
            + table(["名稱", "收集屬性", "裝備屬性"], attr_rows)
            + table(["名稱", "編號", "解鎖來源", "時裝幣"], unlock_rows)
            + ''.join(feat_html)
            + suit_html
        )
    else:
        appear_body = (
            f'<p>{H("目前沒有可收集造型。", terms)}</p>'
            f'<p>{H("頭像位置已預留，稍後再補。不配 2D 立繪，也不使用 Fandom／社群立繪。", terms)}</p>'
        )
    appear_sec = f"""
    <section id="appearance">
      <h2>外觀</h2>
      {appear_body}
    </section>
    """

    # gear
    if page.gear:
        rows = "".join(
            f'<div class="gear-row"><h3>{e(k)}</h3><p>{H(v, terms)}</p></div>'
            for k, v in page.gear["rows"]
        )
        stale = "套裝效果詳見裝備圖鑑（本靜態站尚未搬入圖鑑分冊）。"
        extra_text = (page.gear.get("extra") or "").replace(stale, "").strip()
        extra = f"<p>{H(extra_text, terms)}</p>" if extra_text else ""
        guide = page.faction if page.faction in {"聯盟", "自然", "部族"} else "聯盟"
        gear_sec = f"""
        <section id="gear">
          <h2>建議裝備*</h2>
          <aside class="callout" aria-label="推算／非官方">
            <strong>推算／非官方</strong>
            <p>建議裝備是依技能、專武、覺醒、英靈、天賦和英雄屬性做的整體推算，只是參考，不是官方指定。下列主線與原因照錄已發布的{guide}圖鑑，不另行改主線。</p>
          </aside>
          <div class="gear-list">{rows}</div>
          <p>{H(page.gear['why'], terms)}</p>
          {extra}
          <p>套裝效果見<a href="../equipment.html">{H("裝備總表", terms)}</a>。</p>
          <p>{H("*建議裝備是推算，不是官方最佳裝備。主線與備選照錄已發布的" + guide + "圖鑑，不另行改寫。", terms)}</p>
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
        miss_p = f"<p>{H('、'.join(missing) + '尚無獨立條目，本靜態站目前只公開已生成的英雄頁。羈絆效果這裡先寫表上的點數，可能與面板上的百分比不同。', terms)}</p>"
    else:
        miss_p = f"<p>{H('羈絆效果這裡先寫表上的點數，可能與面板上的百分比不同。', terms)}</p>"
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

    notes_html = link_cross_heroes(H(page.notes, terms), page.hero_id)
    notes_sec = f"""
    <section id="notes">
      <h2>資料說明</h2>
      <p>{notes_html}</p>
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
    def render_codex_item(item: str) -> str:
        hrefs = {
            "專武": "exclusive.html",
            "英靈": "valhalla.html",
            "造型": "skins.html",
            "裝備": "equipment.html",
            "領主裝備": "lord-equipment.html",
            "士兵": "troops.html",
            "秘寶": "artifacts.html",
            "寵物": "pets.html",
            "符文": "runes.html",
            "天賦": "talents.html",
            "科技": "tech.html",
            "裝飾物": "decorations.html",
            "城堡外觀": "castle.html",
        }
        href = hrefs.get(item)
        if href:
            return f'<li><a href="{href}">{e(item)}</a></li>'
        return f"<li>{e(item)}</li>"

    codex = "".join(render_codex_item(item) for item in CODEX_ITEMS)
    body = f"""
    <header class="entry-head">
      <h1>Top Heroes Wiki</h1>
      <p class="lede">Top Heroes 英雄 wiki。目前聯盟、自然和部族的英雄條目都已公開。專武總表、英靈總表、造型總表、裝備總表、領主裝備總表、士兵總表、秘寶總表、寵物總表、符文總表、天賦總表、科技總表、裝飾物總表和城堡外觀總表也已公開。</p>
    </header>
    <section id="heroes">
      <h2>英雄</h2>
      {''.join(factions)}
    </section>
    <section id="codex">
      <h2>圖鑑</h2>
      <p>專武總表、英靈總表、造型總表、裝備總表、領主裝備總表、士兵總表、秘寶總表、寵物總表、符文總表、天賦總表、科技總表、裝飾物總表和城堡外觀總表已公開。</p>
      <ul class="codex-index">{codex}</ul>
    </section>
    <section id="about">
      <h2>關於本站</h2>
      <ul>
        <li>這是繁體中文的英雄 wiki，不是官方網站。</li>
        <li>英雄條目會介紹技能與覺醒、專武、英靈與天賦、外觀、建議裝備和羈絆。</li>
        <li>數值以遊戲裡看到的為準。建議裝備只是參考，不是官方指定。</li>
        <li>名單裡的 15032、15033、15039 在遊戲中文名稱表沒有對應名稱，條目只能用編號，本站不另起中文名。</li>
      </ul>
    </section>
    """
    return page_shell("Top Heroes Wiki", "Top Heroes 英雄 wiki 總目錄。目前聯盟、自然和部族的英雄條目都已公開。專武總表、英靈總表、造型總表、裝備總表、領主裝備總表、士兵總表、秘寶總表、寵物總表、符文總表、天賦總表、科技總表、裝飾物總表和城堡外觀總表也已公開。", body, depth=0, nav_current="index")
