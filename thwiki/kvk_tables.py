"""Public 王國對決 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter

from .catalog_common import (
    EXTRACT_DATA,
    H,
    PAGE_CUTOFF,
    file_sha256,
    footer_swap,
    has_string,
    load_table,
    notes_source_intro,
    official_text,
    p_html,
    quote_block,
    unique_keep_order,
    visible_official,
)
from .htmlutil import e, table

TABLE_SHA256 = {
    "kvk_match_theme_para.json": "db0e61e21033ffa16a13d0f30fe3896af44aaf0559b9cc4c6c19b05ed815fe57",
    "kvk_introduce.json": "9e1f52482fcf1e94acf2f4f4f4558f532d30d8e8cbae1cc0c63ef3377080268d",
    "kvk_map.json": "6423388404eb3732923e31cd8861edd13322728133e3b51b57493afe34fd51f2",
    "kvk_match_prepare.json": "766e9c5147f95d65588dce572f205ea8a8b90ef692a7ba08e7a7e1c29f1763f7",
    "kvk_map_intro.json": "ac2a1031c8517840811b133344c97f13c21bd1cba1f5f4bd9b31626117e86990",
    "kvk_capital.json": "fa108e293ea9f1ccc7c8a805719bb96518469c4bfd386f4f25915e41896e9e31",
    "kvk_kingdom_elements.json": "daa47f0c2fcf1f9647412553af215253cb5864dce1b945a0c9789ca1df6a79b1",
}

THEME_NAME = {
    1: "kvk_activity_name_01",
    2: "kvk_activity_name_20002001",
}


def theme_official(theme: int) -> str:
    key = THEME_NAME.get(theme)
    return visible_official(official_text(key)) if key else ""


def terms_for() -> list[str]:
    names = [
        official_text("king_cross_1_1"),
        official_text("UI_Title_008"),
        official_text("kvk_activity_name_01"),
        official_text("kvk_activity_name_20002001"),
        official_text("kvk_activity_name_20003001"),
        official_text("k3_activity_20003104_name"),
        official_text("k3_activity_20003008_name"),
        official_text("king_cross_10_1"),
        official_text("king_cross_10_2"),
        official_text("unit_race_1"),
        official_text("unit_race_2"),
        official_text("unit_race_3"),
        official_text("professional_name_1"),
        official_text("professional_name_2"),
        official_text("professional_name_3"),
        official_text("citybuilding_name_195"),
        official_text("kvk_tab_07"),
        official_text("kvk_tab_08"),
        official_text("kvk_tab_04"),
        official_text("kvk_tab_05"),
        official_text("kvk_tab_06"),
        official_text("kvk_tab_09"),
        official_text("kvk_map_intro_01"),
        official_text("kvk_map_intro_03"),
        official_text("kvk_map_intro_05"),
        official_text("kvk_map_intro_07"),
        official_text("kvk_map_intro_11"),
        official_text("kvk_capital_name_01"),
        official_text("kvk_capital_name_02"),
        official_text("kvk_capital_name_03"),
        official_text("kvk_capital_name_04"),
        official_text("ui_kvk_kingdom_029"),
        official_text("ui_k2_kingdom_035"),
        official_text("ui_k3_kingdom_035"),
        official_text("kvk_introduce_title9"),
    ]
    for key in (
        "kvk_introduce_title1", "kvk_introduce_title2", "kvk_introduce_title3",
        "kvk_introduce_title4", "kvk_introduce_title5", "kvk_introduce_title6",
        "kvk_introduce_title7", "kvk_introduce_title8", "kvk_introduce_title9",
        "kvk_introduce_title10", "kvk_introduce_title12", "kvk_introduce_title13",
        "kvk_introduce_title14", "kvk_introduce_title16",
        "k3_info_tittle_50057", "k3_info_tittle_50058", "k3_info_title_50059",
        "k3_info_tittle_50060", "k3_info_tittle_50061",
        "king_cross_4_3", "king_cross_4_5",
    ):
        names.append(official_text(key))
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def load_data() -> dict:
    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    for extra in (
        "kvk_match_camp.json", "kvk_building_intro.json", "kvk_task_chapter.json",
        "kvk_map_area.json", "kvk_map_fortress.json", "kvk_server_group.json",
        "kvk_match_activity.json", "info.json",
    ):
        path = EXTRACT_DATA / extra
        if path.exists():
            data[extra] = load_table(extra)
    return data


def introduce_unique(rows: list[dict], theme: int) -> list[tuple[str, str]]:
    out = []
    seen = set()
    for r in rows:
        if r.get("theme") != theme:
            continue
        title = visible_official(official_text(r.get("title")))
        desc = visible_official(official_text(r.get("desc")))
        key = (title, desc)
        if key in seen:
            continue
        seen.add(key)
        if title or desc:
            out.append((title, desc))
    return out


def info_has_id(info_rows: list[dict], iid: int) -> bool:
    return any(r.get("id") == iid for r in info_rows)


MAP_INTRO_GROUP = {1: 1001, 2: 1002}


def map_intro_rows(rows: list[dict], theme: int) -> list[tuple[str, str]]:
    group = MAP_INTRO_GROUP.get(theme)
    out = []
    for r in rows:
        if r.get("group") != group:
            continue
        title = visible_official(official_text(r.get("tab_title")))
        desc = visible_official(official_text(r.get("tab_desc1")))
        if title or desc:
            out.append((title, desc))
    return out


def official_place_names(rows_capital: list[dict], rows_elements: list[dict], theme: int) -> list[str]:
    names: list[str] = []
    for r in rows_capital:
        if r.get("theme") != theme:
            continue
        name = visible_official(official_text(r.get("name"))) if r.get("name") else ""
        if name:
            names.append(name)
    for r in rows_elements:
        if r.get("theme") != theme:
            continue
        name = visible_official(official_text(r.get("name"))) if r.get("name") else ""
        if name:
            names.append(name)
    return unique_keep_order(names)


def render_html() -> str:
    from .render import page_shell, toc_list

    data = load_data()
    terms = terms_for()
    sys_name = visible_official(official_text("king_cross_1_1") or "王國對決")
    help_title = visible_official(official_text("UI_Title_008") or "王國對決說明")
    t1 = visible_official(official_text("kvk_activity_name_01") or "王國紛爭")
    t2 = visible_official(official_text("kvk_activity_name_20002001") or "雲海紀行")
    t3 = visible_official(official_text("kvk_activity_name_20003001") or "地心探險")
    hunt = visible_official(official_text("k3_activity_20003104_name") or "地心狩獵")
    cave = visible_official(official_text("k3_activity_20003008_name") or "塵封的寶藏洞窟")

    title = f"Top Heroes Wiki｜{sys_name}"
    lede = (
        f"本頁寫界面總稱「{sys_name}」的兩個已有完整主題參數與介紹表的主題：「{t1}」與「{t2}」。"
        f"「{t3}」與子活動「{hunt}」目前沒有對得上的主題參數、介紹或地圖列，本頁只列出已有的官方字串並標明表列未齊，不補造表。"
        "這不是全賽季圖鑑。"
    )
    summary = (
        f"{sys_name}圖鑑：{t1}、{t2} 的名錄與規則摘要；{t3}與{hunt}只列出已有的官方字串。"
    )
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "themes", "label": "主題總覽"},
        {"id": "rules", "label": "共用規則"},
        {"id": "theme-1", "label": t1},
        {"id": "theme-2", "label": t2},
        {"id": "theme-3", "label": t3},
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
        f"界面總稱是「{H(sys_name, terms)}」，說明標題是「{H(help_title, terms)}」。"
        f"另有短句「{H(visible_official(official_text('king_cross_1_2')), terms)}」。"
        "名稱與說明以遊戲裡看得到的為準。不評定主題強弱，不排佔領優先，不編造戰鬥公式。"
        "時間整數若沒有單位欄，不自行換成日或小時。官方文案若寫時區，只對該句有效，不套到其他沒寫時區的欄。"
        "界面若有「未開放」一類句子，不據此把整套系統標成未開放。"
    ))
    add(p_html(
        f"「{H(t2, terms)}」是這個系統裡一個主題的官方名。"
        "不把它寫成已核對的官方第六季，也不把其他主題字串或路徑後綴合併成官方第 N 季、第 N 輪。"
    ))
    add("    </section>")

    add('    <section id="themes">')
    add("      <h2>主題總覽</h2>")
    add(p_html(
        f"主題參數表有兩列，標題分別是「{H(t1, terms)}」與「{H(t2, terms)}」。"
        f"沒有「{H(t3, terms)}」的參數列。地圖表同樣只有這兩個主題各一列。"
    ))
    theme_rows = []
    for r in data["kvk_match_theme_para.json"]:
        name = visible_official(official_text(r.get("title")))
        theme_rows.append([H(name, terms) if name else "沒有官方標題"])
    add(table(
        ["主題"],
        theme_rows,
        caption="已有主題參數的兩個主題",
        mobile="cards",
        card_title="主題",
    ))
    intro = data["kvk_introduce.json"]
    counts = Counter(r.get("theme") for r in intro)
    add(p_html(
        f"介紹表共 {len(intro)} 列，其中「{H(t1, terms)}」{counts.get(1, 0)} 列、「{H(t2, terms)}」{counts.get(2, 0)} 列。"
        f"沒有「{H(t3, terms)}」的介紹列。後段有重複標題，下表只列一次，不推測重複原因。"
    ))
    prep = data["kvk_match_prepare.json"]
    prep_rows = []
    for r in prep:
        name = visible_official(official_text(r.get("kvk_match_prepare_title")))
        desc = visible_official(official_text(r.get("kvk_match_prepare_desc")))
        note = ""
        if r.get("id") == 3:
            note = f"標題與說明仍是「{t1}」，不是「{t3}」"
        prep_rows.append([
            H(name, terms) if name else "沒有官方標題",
            H(desc, terms) if desc else "",
            e(note),
        ])
    add(p_html("準備表有三列。第三列的標題與說明仍是「" + H(t1, terms) + "」，不可當成「" + H(t3, terms) + "」。"))
    add(table(
        ["標題", "說明", "備註"],
        prep_rows,
        caption="準備表三列",
        mobile="cards",
        card_title="標題",
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>共用規則</h2>")
    add(p_html(
        f"階段名稱有「{H(visible_official(official_text('king_cross_10_1')), terms)}」與「{H(visible_official(official_text('king_cross_10_2')), terms)}」。"
        "界面有兩則總說明，用字略有不同，以下並列，不以其中一則覆寫另一則。"
    ))
    add(quote_block(official_text("king_cross_function_tips_1"), terms))
    add(quote_block(official_text("king_cross_function_tips_1_new"), terms))
    add("    </section>")

    # theme 1 and 2
    for theme, sec, label in ((1, "theme-1", t1), (2, "theme-2", t2)):
        add(f'    <section id="{sec}">')
        add(f"      <h2>{e(label)}</h2>")
        desc_key = "kvk_activity_desc_01" if theme == 1 else "kvk_activity_desc_20002001"
        if has_string(desc_key):
            add(p_html("主題說明："))
            add(quote_block(official_text(desc_key), terms))
        items = introduce_unique(intro, theme)
        add(p_html("介紹頁標題與說明如下："))
        add(table(
            ["標題", "說明"],
            [[H(a, terms) if a else "", H(b, terms) if b else ""] for a, b in items],
            caption=f"{label}介紹節點",
            mobile="cards",
            card_title="標題",
        ))
        camps = []
        for r in data.get("kvk_match_camp.json") or []:
            if r.get("theme") != theme:
                continue
            name = visible_official(official_text(r.get("name"))) if r.get("name") else ""
            if name:
                camps.append([H(name, terms)])
            else:
                camps.append(["沒有官方名稱，不另起名"])
        if camps:
            add(p_html("陣營或城邦名稱如下："))
            add(table(
                ["名稱"],
                camps,
                caption=f"{label}陣營或城邦",
                mobile="cards",
                card_title="名稱",
            ))
        intros = map_intro_rows(data.get("kvk_map_intro.json") or [], theme)
        if intros:
            add(p_html("地圖介紹的標籤與說明如下；說明裡的佔位不自行填入。"))
            add(table(
                ["標籤", "說明"],
                [[H(a, terms) if a else "", H(b, terms) if b else ""] for a, b in intros],
                caption=f"{label}地圖介紹",
                mobile="cards",
                card_title="標籤",
            ))
        places = official_place_names(
            data.get("kvk_capital.json") or [],
            data.get("kvk_kingdom_elements.json") or [],
            theme,
        )
        if places:
            quoted = "、".join(f"「{H(n, terms)}」" for n in places)
            add(p_html(
                "王城名稱表與王國建築表出現的官方名有："
                + quoted
                + "。這些名稱與地圖介紹裡的用字可能不是同一鍵，並列保留，不以其中一個覆寫另一個。"
                "本批表沒有寫明客戶端實際顯示哪一個。"
            ))
        if theme == 1:
            sand_page = visible_official(official_text("kvk_introduce_title9"))
            dragon = visible_official(official_text("kvk_map_intro_11"))
            court = visible_official(official_text("ui_kvk_kingdom_029"))
            add(p_html(
                "地圖介紹與介紹頁的陣營用字也不全相同：地圖介紹寫「沙漠陣營」，介紹頁標題是「"
                + H(sand_page, terms)
                + "」。這是不同鍵，不合併。"
                + (f"地圖介紹另寫「{H(dragon, terms)}」，王國建築表寫「{H(court, terms)}」，同樣並列保留。" if dragon and court else "")
            ))
        add("    </section>")

    add('    <section id="theme-3">')
    add(f"      <h2>{e(t3)}</h2>")
    add(p_html(
        f"「{H(t3, terms)}」是官方主題名。主題參數表、介紹表與地圖表都沒有對應列，"
        "目前對得上的主要是遊戲裡的說明文字。以下只列出這些官方字串，不補造次數上限、座標、授獎或開放條件，也不寫成與前兩個主題同規格的表。"
    ))
    if has_string("kvk_activity_desc_20003001"):
        add(p_html("主題說明："))
        add(quote_block(official_text("kvk_activity_desc_20003001"), terms))
    for key in (
        "k3_info_tittle_50057",
        "k3_info_50057_1",
        "k3_info_tittle_50058",
        "k3_info_50058_1",
        "k3_info_tittle_50061",
        "k3_info_50061_1",
        "k3_introduce_desc1",
    ):
        if not has_string(key):
            continue
        text = visible_official(official_text(key))
        if not text:
            continue
        if "tittle" in key or key.endswith("_title") or key.startswith("k3_info_title") or key.startswith("k3_info_tittle"):
            add(f"<h3>{H(text, terms)}</h3>")
        else:
            add(quote_block(official_text(key), terms))
    # 地心狩獵 as subsection but not same spec
    add(f"<h3>{H(hunt, terms)}</h3>")
    add(p_html(
        f"子活動官方名是「{H(hunt, terms)}」。"
        "目前沒有找到以這個名稱為標題的活動配置表，只列出已有的官方字串，不補造表。"
    ))
    if has_string("k3_activity_20003104_desc"):
        add(quote_block(official_text("k3_activity_20003104_desc"), terms))
    if has_string("k3_info_title_50059"):
        add(p_html(
            f"另有說明標題「{H(visible_official(official_text('k3_info_title_50059')), terms)}」。"
        ))
    extra = []
    for key in ("mail_title_600151", "mail_title_600152"):
        if has_string(key):
            extra.append(visible_official(official_text(key)))
    if extra:
        add(p_html("郵件標題還有「" + "」「".join(H(x, terms) for x in extra) + "」。"))
    add(f"<h3>{H(cave, terms)}</h3>")
    add(p_html(
        f"另有官方名「{H(cave, terms)}」。"
        + (f"說明標題「{H(visible_official(official_text('k3_info_tittle_50060')), terms)}」。" if has_string("k3_info_tittle_50060") else "")
        + "同樣沒有在本頁展開未對上的配置表。官方說明原文如下。"
    ))
    if has_string("k3_info_50060_2"):
        add(quote_block(official_text("k3_info_50060_2"), terms))
        add(p_html(
            "這則官方說明寫有「UTC-2」。這個時區只對這一句，不套到其他沒寫時區的欄位。"
        ))
    add(p_html(
        "說明頁字串對應的資料列，在本批說明表裡找不到；只記錄這件事，不把那些說明標成未開放。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    area_n = len(data.get("kvk_map_area.json") or [])
    fort_n = len(data.get("kvk_map_fortress.json") or [])
    chap_n = len(data.get("kvk_task_chapter.json") or [])
    act_n = len(data.get("kvk_match_activity.json") or [])
    grp_n = len(data.get("kvk_server_group.json") or [])
    add(p_html(
        f"地圖區域、要塞與座標等大表只記列數，不逐列傾印：區域 {area_n} 列、要塞 {fort_n} 列。"
        f"任務章節 {chap_n} 列、對決活動 {act_n} 列、伺服器分組 {grp_n} 列亦不逐筆展開。"
        "伺服器分組表上的內部編號，不對成界面顯示的王國編號。"
    ))
    totem = visible_official(official_text("citybuilding_name_195"))
    add(p_html(
        f"介紹頁出現的「{H(totem, terms)}」、商隊貿易、村民、陣營等級、公會導師不在本頁展開，詳見"
        f"<a href=\"ancestral-totem.html\">「{H(totem, terms)}」</a>、"
        f"<a href=\"caravan-trade.html\">{H('商隊貿易', terms)}</a>、"
        f"<a href=\"villagers.html\">{H('村民', terms)}</a>、"
        f"<a href=\"faction-levels.html\">{H('陣營等級', terms)}</a>、"
        f"<a href=\"guild-mentors.html\">{H('公會導師', terms)}</a>。"
        f"三個職業名稱已見於「{H(t1, terms)}」介紹，規則見已發佈的"
        f"<a href=\"lord-occupations.html\">{H('領主職業', terms)}總表</a>。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add(
        "<li>主題參數表只在本批 LocalLow 出現，2026-11-05 與 11-22 StreamingAssets 沒有這張檔。"
        "正文以 LocalLow 為準。</li>"
    )
    add(
        "<li>準備頁第三列的 <code>theme</code> 欄是 3，但標題與說明鍵仍是 "
        f"「{e(t1)}」，與第一列相同。不可當成「{e(t3)}」。</li>"
    )
    add(
        f"<li>「{e(t2)}」亦見於精靈主題字串，本頁只把它當本系統主題官方名照錄，"
        "不寫成已核對的官方第六季。</li>"
    )
    add(
        "<li>伺服器分組欄是內部編號與分組，界面顯示格式是「#{0}」「#{0}王國」。"
        "不要聲稱顯示伺服器 N 等於內部編號 100N。</li>"
    )
    add(
        f"<li>「{e(t3)}」「{e(hunt)}」的說明標題鍵在字串表，"
        "本批 <code>info.json</code> 沒有對應列。部分表即使出現相近數字，沒有名稱鍵對上就不當作此活動配置。</li>"
    )
    add(
        "<li>地圖介紹、王城名稱表與王國建築表的官方名並存時（例如「星落龍廷」與「星落王庭」，"
        "「風之都」與「風息城」，地圖介紹「沙漠陣營」與介紹頁「沙丘陣營」），只並列照錄。"
        "客戶端實際顯示哪一個，本批沒有對得上的欄，不推測。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_kingdom_clash_page() -> str:
    return render_html()
