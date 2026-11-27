"""Public 公會導師 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from .catalog_common import (
    H,
    footer_swap,
    goods_label,
    load_table,
    notes_source_intro,
    official_text,
    p_html,
    quote_block,
    render_info_pages,
    unique_keep_order,
    visible_official,
)
from .htmlutil import e, table

TABLE_SHA256 = {
    "royal_academy.json": "d3c176c3edf1d8022f408d956d47648c86817cb7ebaa2e24dddc36a4487359ad",
    "royal_academy_level.json": "1f8f003ea2c03a8031de8ebd6900264abce07da250a7db2fbbbd6caf1caa182b",
    "royal_academy_room.json": "fbcfd680a2de0e157eb650a02aba3fe1e76456d4dc7c4d1793532029742e72ee",
    "royal_academy_skill.json": "917793c9ebaa1fa3fb7f1bf5a43d36f4953f053188ea398f4f2d0684c604b7e0",
    "royal_academy_skill_negative.json": "cd6b30e47da78680cb983f461cef49ebfa2dbc7ba2730ca4e05b08648ada8ba0",
    "royal_academy_skill_show.json": "90ef56cda175a2becd5f38eb0e4593e94725e5893238054ca683dfc7bd43de96",
    "royal_academy_star.json": "220c2cbcd5659513cd285d3253c9f6f0919da4623c877c2c517918af32cf03fc",
    "royal_academy_star_max.json": "f8ed9ff9bd15b3ee7853fea46f408fb43e8fd4b847259b69f1932f49c1b52796",
    "royal_academy_star_max_bonus.json": "f255aa302fe9668215829aa27bf8fb1c64527095ac8ae4a4604cd3f281a7937a",
    "royal_academy_story.json": "488775fe0ab1244bee5f3b6d6e45dd95aa4ea899619205dd69f87d914e6a7e69",
}

INFO_SHA256 = "48e3a023094f1f80e9725b8a13a8c82efcdd288b9527fc5a6df41003f50631fe"

# Mentor id in tables: 1 科迪莉亞, 2 安布羅斯
MENTOR_NAME_KEYS = {1: "royal_academy_mentor_name_1", 2: "royal_academy_mentor_name_2"}
MENTOR_TITLE_KEYS = {1: "royal_academy_desc_9", 2: "royal_academy_desc_10"}
MENTOR_TECH_KEYS = {1: "alliance_tech_name_40104", 2: "alliance_tech_name_40304"}
INFO_IDS = (35018, 30033, 30032)


def terms_for(extra: list[str] | None = None) -> list[str]:
    names = [
        official_text("royal_academy_info_title_3"),
        official_text("royal_academy_tab_15"),
        official_text("ra_name_d1"),
        official_text("royal_academy_mentor_info_title"),
        official_text("royal_academy_desc_27"),
        official_text("royal_academy_info_title"),
        official_text("alliance_tech_page4"),
        official_text("royal_academy_mentor_name_1"),
        official_text("royal_academy_mentor_name_2"),
        official_text("royal_academy_desc_9"),
        official_text("royal_academy_desc_10"),
        official_text("alliance_tech_name_40104"),
        official_text("alliance_tech_name_40304"),
        official_text("royal_academy_info_title_4"),
        official_text("royal_academy_info_title_5"),
        official_text("royal_academy_info_title_6"),
        official_text("goods_name_1055"),
        official_text("goods_name_1056"),
        official_text("goods_name_1071"),
        official_text("goods_name_1072"),
        official_text("goods_name_1057"),
        official_text("goods_name_505160112"),
    ]
    for i in range(1, 11):
        names.append(official_text(f"royal_academy_relationship_{i}"))
    if extra:
        names.extend(extra)
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def _unique_skill_names(rows: list[dict], mentor: int) -> list[str]:
    out = []
    for r in rows:
        if r.get("mentor") != mentor:
            continue
        name = visible_official(official_text(r.get("name"))) or "字串表沒有名稱"
        if name not in out:
            out.append(name)
    return out


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    info_rows = load_table("info.json", INFO_SHA256)
    extra = []
    for r in data["royal_academy_skill.json"] + data["royal_academy_skill_negative.json"]:
        extra.append(visible_official(official_text(r.get("name"))))
    terms = terms_for(extra)

    mentor_sys = visible_official(
        official_text("royal_academy_info_title_3")
        or official_text("royal_academy_tab_15")
        or official_text("ra_name_d1")
        or "公會導師"
    )
    mentor_help = visible_official(official_text("royal_academy_mentor_info_title") or "公會導師說明")
    hall = visible_official(official_text("royal_academy_desc_27") or official_text("alliance_tech_page4") or "爐火大廳")
    hall_help = visible_official(official_text("royal_academy_info_title") or "爐火大廳說明")

    mentors = []
    for row in data["royal_academy.json"]:
        mid = row["id"]
        mentors.append({
            "id": mid,
            "name": visible_official(official_text(MENTOR_NAME_KEYS[mid])),
            "title": visible_official(official_text(MENTOR_TITLE_KEYS[mid])),
            "tech": visible_official(official_text(MENTOR_TECH_KEYS[mid])),
            "desc": visible_official(official_text(row.get("desc"))),
            "row": row,
        })

    title = f"Top Heroes Wiki｜{mentor_sys}"
    lede = (
        f"本頁寫「{mentor_sys}」的兩位導師、好感與榮譽斷點，以及官方說明。"
        f"「{mentor_sys}」與「{hall}」是不同的官方名稱，並列保留，不合併成一個系統名。"
        "名稱與說明依遊戲裡看得到的字照錄。"
        "贈禮、印記與每日上限只引用已有官方說明；表上沒有寫明的折算，不猜測。"
    )
    summary = f"{mentor_sys}圖鑑：兩位導師、官方說明與等級斷點。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "mentors", "label": "兩位導師"},
        {"id": "progress", "label": "等級與斷點"},
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

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        f"界面標題是「{H(mentor_sys, terms)}」，說明頁標題是「{H(mentor_help, terms)}」。"
        f"「{H(hall, terms)}」另有說明頁「{H(hall_help, terms)}」，是共聚空間的官方名，不是導師功能的另一個標題。"
        "本頁不把內部檔名寫成界面標題。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    for iid in INFO_IDS:
        row = next((r for r in info_rows if r.get("id") == iid), None)
        if not row:
            continue
        heading = visible_official(official_text(row.get("title")) or "")
        if heading:
            add(f"<h3>{H(heading, terms)}</h3>")
        for block in render_info_pages(row, terms):
            add(block)
    add(p_html(
        "官方說明提到贈禮可提高好感度、普通印記有每日可捐獻上限、高級印記沒有上限，以及學識手冊可提高技能學習經驗。"
        "這些規則以說明文為準。表上沒有寫明贈禮對好感、印記折算或每日上限的具體數字時，本頁不猜測實作欄位。"
    ))
    add("    </section>")

    add('    <section id="mentors">')
    add("      <h2>兩位導師</h2>")
    mrows = []
    for m in mentors:
        stamps = []
        for gid in (m["row"].get("item") or []):
            label = goods_label(gid, terms)
            if label:
                stamps.append(label)
        skills = _unique_skill_names(data["royal_academy_skill.json"], m["id"])
        negs = _unique_skill_names(data["royal_academy_skill_negative.json"], m["id"])
        mrows.append([
            H(m["name"], terms),
            H(m["title"], terms),
            H(m["tech"], terms),
            "、".join(H(s, terms) for s in skills) if skills else "字串表沒有名稱",
            "、".join(H(s, terms) for s in negs) if negs else "字串表沒有名稱",
            "、".join(stamps) if stamps else "沒有官方短名",
        ])
        if m["desc"]:
            add(p_html(f"「{H(m['name'], terms)}」說明：「{H(m['desc'], terms)}」。"))
    add(table(
        ["導師", "頭銜", "解鎖科技", "技能", "其他官方技能", "專屬印記"],
        mrows,
        caption="公會導師",
        mobile="cards",
        card_title="導師",
    ))
    book = goods_label(1057, terms)
    common = goods_label(505160112, terms)
    add(p_html(
        f"說明文也提到學識手冊與通用導師印記。道具官方短名是「{book}」與「{common}」。"
    ))
    add("    </section>")

    add('    <section id="progress">')
    add("      <h2>等級與斷點</h2>")
    levels = data["royal_academy_level.json"]
    by_m = {1: [r for r in levels if r.get("mentor") == 1], 2: [r for r in levels if r.get("mentor") == 2]}
    add(p_html(
        f"好感等級表共 {len(levels)} 列，是兩位導師各 {len(by_m[1])} 級，不是一條軌道打通到 {len(levels)} 級。"
        f"兩條軌道的等級範圍都是 {by_m[1][0]['level']} 至 {by_m[1][-1]['level']}。"
    ))
    stars = data["royal_academy_star.json"]
    rel_rows = []
    # Use mentor 1 for relationship labels; names are shared keys
    for r in [x for x in stars if x.get("mentor") == 1]:
        rel = visible_official(official_text(r.get("desc"))) or "字串表沒有名稱"
        rel_rows.append([str(r.get("star")), H(rel, terms)])
    add(p_html(f"羈絆（好感星級）官方名稱如下，兩位導師共用這套稱呼，共 {len(rel_rows)} 級。"))
    add(table(
        ["星級", "官方名稱"],
        rel_rows,
        caption="導師羈絆名稱",
        mobile="cards",
        card_title="星級",
    ))
    bonus = data["royal_academy_star_max_bonus.json"]
    bonus_lvs = unique_keep_order(r.get("bonus_lv") for r in bonus if r.get("mentor") == 1)
    add(p_html(
        "羈絆達到上限後，說明文寫將解鎖榮譽等級。"
        f"榮譽加成分檔出現在 { '、'.join(str(x) for x in bonus_lvs) }，"
        "這與好感等級的 100 級不是同一條軸，本頁不把兩者併成一種等級。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"導師等級 {len(levels)} 列、技能 {len(data['royal_academy_skill.json'])} 列與故事 {len(data['royal_academy_story.json'])} 列不逐筆傾印數值。"
        "城建表沒有名為爐火大廳的建築；內部路徑名稱不是界面標題。"
        "本頁不把未出現在字串表的詞寫成界面標題。"
        "也不把公會牧場連到本頁。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for tname, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(tname)}</code> SHA-256 <code>{e(sha)}</code>，{len(data[tname])} 列。</li>")
    add(f"<li><code>info.json</code> SHA-256 <code>{e(INFO_SHA256)}</code>。</li>")
    add(
        "<li>定義表有一欄寫成 <code>unlock_teh</code>（原文拼法如此），這是資料欄名，不是界面名稱，可見正文不使用這個詞。</li>"
    )
    add(
        "<li>表檔名含 royal_academy，但字串表沒有「皇家學院」作為界面標題，可見正文不使用這個詞。</li>"
    )
    add(
        "<li>解鎖科技鍵是 <code>alliance_tech_name_40104</code>「邀請科迪莉亞」、"
        "<code>alliance_tech_name_40304</code>「邀請安布羅斯」。</li>"
    )
    add(
        "<li>榮譽分檔來自 <code>royal_academy_star_max_bonus</code> 的 50、100、150、200；"
        "好感等級上限是每位導師 100 級。贈禮折算與每日上限沒有可對上的完整常量表，只引用官方說明。</li>"
    )
    add("    </ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_guild_mentors_page() -> str:
    return render_html()
