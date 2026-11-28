"""Public 摸魚時光／魚缸 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from .catalog_common import (
    H,
    fmt_pipe,
    footer_swap,
    has_string,
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
    "fish.json": "e65186de565385c78bc6811fddede12c2491a39b5e7ee918f5766089747c2cca",
    "fish_food.json": "f3d6417314e64fa6e88af434a506851f400cd9506e17339696b99ea256d2fa38",
    "fish_fry.json": "c1beb4f5ef8852604dae1f2986d9c839d34d478332c8e82eed0e7c2311ed61af",
    "fish_tank.json": "dc91312bdb345bafab291e11f464154bf5e7bd55ba7dab63e4f0c77b3ff99a8f",
}


def terms_for() -> list[str]:
    names = [
        official_text("activity_name_5001003"),
        official_text("UI_Title_097"),
        official_text("fish_activity_info_title1"),
        official_text("fish_activity_info_title2"),
        official_text("fish_activity_info_title3"),
        official_text("fish_tank_activity_key1"),
        official_text("fish_tank_activity_key15"),
        "魚缸",
        official_text("fish_fry_name_1"),
        official_text("fish_fry_name_2"),
        official_text("fish_fry_mark_1"),
        official_text("fish_fry_mark_2"),
    ]
    for i in range(1, 21):
        names.append(official_text(f"fish_name_{i}"))
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def render_html() -> str:
    from .render import page_shell, toc_list

    fish = load_table("fish.json", TABLE_SHA256["fish.json"])
    food = load_table("fish_food.json", TABLE_SHA256["fish_food.json"])
    fry = load_table("fish_fry.json", TABLE_SHA256["fish_fry.json"])
    tank = load_table("fish_tank.json", TABLE_SHA256["fish_tank.json"])
    info = load_table("info.json")
    terms = terms_for()
    act = visible_official(official_text("activity_name_5001003") or "摸魚時光")
    tank_word = "魚缸"
    my_tank = visible_official(official_text("fish_tank_activity_key1") or "我的魚缸")
    help_title = visible_official(official_text("UI_Title_097") or "摸魚時光活動說明")
    # Visible title lists two official names; not a coined blend.
    page_title = f"Top Heroes Wiki｜{act}、{tank_word}"
    lede = (
        f"本頁寫官方活動「{act}」與界面用詞「{tank_word}」。"
        f"例如「{my_tank}」「魚缸容量」。這兩個是各自的官方用字，不是另造的合併名稱。"
    )
    summary = f"{act}與{tank_word}圖鑑：二十種魚的名稱、說明與養魚、拜訪、圖鑑規則。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "catalog", "label": "魚種名錄"},
        {"id": "packs", "label": "魚苗包、飼料與魚缸"},
        {"id": "out-of-scope", "label": "本頁未列入"},
        {"id": "notes", "label": "資料說明"},
    ])
    parts: list[str] = []
    add = parts.append
    add('    <header class="entry-head">')
    add(f"      <h1>{e(page_title)}</h1>")
    add(f'      <p class="lede">{e(lede)}</p>')
    add("    </header>")
    add(f"    {toc}")

    add('    <section id="lead">')
    add("      <h2>簡介與閱讀說明</h2>")
    add(p_html(
        f"活動名是「{H(act, terms)}」，說明是「{H(visible_official(official_text('activity_desc_5001003')), terms)}」。"
        f"規則標題是「{H(help_title, terms)}」。"
        f"界面另有「{H(my_tank, terms)}」、「{H(visible_official(official_text('fish_tank_activity_key15')), terms)}」、"
        f"「{H(visible_official(official_text('season_memo_s4_photo1_title')), terms)}」。"
    ))
    add(p_html(
        "名稱與說明以遊戲裡看得到的為準。以下是表上的數字，沒有額外的官方中文欄名；品質欄不套用其他系統的品質稱呼。"
        "官方說明若寫每秒獲得經驗，與表上的數字並列，不自行改標單位。"
        "紀念標題或路徑裡若出現編號字樣，只引用官方用字，不寫成已核對的官方第 N 季。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    row = next((r for r in info if r.get("id") == 35011), None)
    if row:
        add(f"<h3>{H(help_title, terms)}</h3>")
        parts.extend(render_info_pages(row, terms))
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>魚種名錄</h2>")
    add(p_html(
        f"魚種表共 {len(fish)} 筆。名稱以該列對應的官方名稱為準，不假設表上順序與名稱一一對應。"
    ))
    rows = []
    for r in fish:
        name = visible_official(official_text(r.get("name")))
        desc = visible_official(official_text(r.get("desc")))
        rows.append([
            H(name, terms) if name else "沒有官方名稱",
            H(desc, terms) if desc else "",
            e(str(r.get("quality"))),
            e(str(r.get("grow_exp"))),
            e(fmt_pipe(r.get("sell_price"))),
            e(str(r.get("income"))),
            e(str(r.get("chart_exp"))),
        ])
    add(table(
        ["名稱", "說明", "品質", "成長經驗", "出售相關數字", "收益", "圖鑑經驗"],
        rows,
        caption="魚種名錄",
        mobile="cards",
        card_title="名稱",
    ))
    add("    </section>")

    add('    <section id="packs">')
    add("      <h2>魚苗包、飼料與魚缸</h2>")
    sea = visible_official(official_text("fish_fry_name_1"))
    deep = visible_official(official_text("fish_fry_name_2"))
    sea_mark = visible_official(official_text("fish_fry_mark_1"))
    deep_mark = visible_official(official_text("fish_fry_mark_2"))
    fry_rows = []
    for r in fry:
        name = visible_official(official_text(r.get("name")))
        mark = visible_official(official_text(r.get("mark")))
        fry_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            H(mark, terms) if mark else "",
            e(str(r.get("price"))),
            e(str(r.get("number"))),
            e(fmt_pipe(r.get("content"))),
        ])
    add(p_html(
        f"魚苗表只有 {len(fry)} 列，對應「{H(sea, terms)}」，標記「{H(sea_mark, terms)}」。"
        "內容欄沒有官方欄位標題，不自行解釋各段含義。"
        "沒有官方短名時不編造；若有官方說明，只引用說明原文。"
    ))
    add(table(
        ["名稱", "標記", "價格", "數量", "內容"],
        fry_rows,
        caption="魚苗表既有列",
        mobile="cards",
        card_title="名稱",
    ))
    add(p_html(
        f"遊戲中文名稱表另有「{H(deep, terms)}」，標記「{H(deep_mark, terms)}」。"
        f"道具說明寫：「{H(visible_official(official_text('goods_desc_319')), terms)}」。"
        "魚苗表沒有這一列，本頁不補造內容或機率。"
    ))
    if has_string("goods_desc_310"):
        add(p_html(
            f"「{H(sea, terms)}」的道具說明：「{H(visible_official(official_text('goods_desc_310')), terms)}」。"
            "兩者都沒有官方短名。"
        ))
    food_r = food[0]
    add(p_html(
        "飼料表有 1 列。"
        "對應道具沒有官方短名，也沒有官方說明，不另起名。"
        f"價格 {e(str(food_r.get('price')))}，經驗 {e(str(food_r.get('exp')))}。"
    ))
    tank_r = tank[0]
    add(p_html(
        f"魚缸設定表有 1 列。初始容量 {e(str(tank_r.get('size')))}，自動經驗 {e(str(tank_r.get('auto_exp')))}。"
        f"擴充相關數字：{e(fmt_pipe(tank_r.get('expand')))}。"
        f"投餵次數相關數字：{e(fmt_pipe(tank_r.get('food_extra_times')))}。"
        "這些欄沒有官方標題，不自行分段命名，也不改標單位。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"抓蝴蝶、精靈小屋、牧場物語見"
        f"<a href=\"butterfly-catch.html\">{H(visible_official(official_text('butterfly_catch_42') or '抓蝴蝶'), terms)}</a>、"
        f"<a href=\"elf-cottage.html\">{H(visible_official(official_text('elf_d1') or '精靈小屋'), terms)}</a>、"
        f"<a href=\"ranch-tale.html\">{H(visible_official(official_text('ether_ranch_030') or '牧場物語'), terms)}</a>。"
        "圖鑑獎勵包若沒有官方短名，不推測內容。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add("<li>三批 extracts 的這四張魚缸表全文相同。</li>")
    add(
        "<li>名稱鍵與列編號不是一一對應，例如有的列用了不同序號的名稱鍵。"
        "可見名錄以該列名稱鍵為準。</li>"
    )
    add(
        "<li>路徑或紀念鍵若含編號字樣，只在資料說明提及，可見正文不寫成官方第 N 季。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(page_title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_fish_tank_page() -> str:
    return render_html()
