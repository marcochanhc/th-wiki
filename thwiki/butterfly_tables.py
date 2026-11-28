"""Public 抓蝴蝶 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter, defaultdict

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
    "butterfly_info.json": "90e12895022e479a4d75a3aa71227fe482dd7088a90c7fd9cb89a7fd0403dca6",
    "butterfly_catch.json": "54031c1e0f7aecd4c416541151d0606a438224c033eb3973c22a8b4491340694",
    "butterfly_child.json": "a59fb378b832bd26b134417f7c1fbfd253fa660393bbbb6a4ec5f4e07e626666",
    "butterfly_item.json": "115c506203973fe87993cf759a773a801bf1334b21e5422131096ed81ae2e672",
}


def terms_for() -> list[str]:
    names = [
        official_text("butterfly_catch_42"),
        official_text("butterfly_catch_10"),
        official_text("butterfly_catch_16"),
        official_text("butterfly_catch_51"),
        official_text("butterfly_catch_50"),
        official_text("butterfly_catch_30"),
        official_text("butterfly_catch_17"),
        official_text("butterfly_catch_139"),
        official_text("butterfly_catch_152"),
        official_text("butterfly_catch_147"),
        official_text("butterfly_catch_36"),
        official_text("butterfly_catch_37"),
        official_text("butterfly_catch_38"),
        official_text("butterfly_catch_39"),
        official_text("butterfly_catch_191"),
        official_text("butterfly_catch_192"),
        official_text("butterfly_catch_232"),
        official_text("goods_name_504225001"),
        official_text("butterfly_catch_231"),
        official_text("butterfly_catch_112"),
        official_text("butterfly_catch_113"),
        official_text("butterfly_catch_6"),
        official_text("butterfly_catch_35"),
    ]
    # species and type names only (not generic verbs in the same key range)
    for i in range(68, 110):
        names.append(official_text(f"butterfly_catch_{i}"))
    names.extend([
        "彩蝶林域",
        "彩蝶領域",
        "使用花蜜",
        "使用檸檬",
        "提交隱藏蝶",
        "使用道具",
        "花蜜分數",
        "公會花蜜總分數",
        "你成功提交了一隻隱藏蝶",
    ])
    skip = {"使用", "提交", "確認", "取消", "查看", "參與", "配對", "出生", "主人", "同意", "全部", "詳情", "請求"}
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2 and n not in skip]


def render_html() -> str:
    from .render import page_shell, toc_list

    info_rows = load_table("butterfly_info.json", TABLE_SHA256["butterfly_info.json"])
    catch = load_table("butterfly_catch.json", TABLE_SHA256["butterfly_catch.json"])
    child = load_table("butterfly_child.json", TABLE_SHA256["butterfly_child.json"])
    items = load_table("butterfly_item.json", TABLE_SHA256["butterfly_item.json"])
    info = load_table("info.json")
    terms = terms_for()
    title_name = visible_official(official_text("butterfly_catch_42") or "抓蝴蝶")
    activity = visible_official(official_text("butterfly_catch_10") or "抓蝴蝶活動")
    help_title = visible_official(official_text("butterfly_catch_16") or "抓蝴蝶活動說明")
    area = visible_official(official_text("butterfly_catch_30") or "彩蝶領域")
    book = visible_official(official_text("butterfly_catch_51") or "蝴蝶圖冊")
    page_title = f"Top Heroes Wiki｜{title_name}"
    lede = (
        f"本頁寫「{title_name}」活動的名錄與規則。"
        f"界面也稱「{activity}」，規則標題是「{help_title}」。"
    )
    summary = f"{title_name}圖鑑：三十六種蝴蝶的名稱、類型與活動說明。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "catalog", "label": "蝴蝶名錄"},
        {"id": "catch", "label": "捕捉與配對"},
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
        f"官方活動名是「{H(title_name, terms)}」、「{H(activity, terms)}」。"
        f"另有「{H(book, terms)}」、「{H(area, terms)}」。"
        "說明文案裡另有用字「彩蝶林域」，與「彩蝶領域」並列保留，不合併、不判哪個是錯字。"
        "遊戲中文名稱表沒有剛好等於「蝴蝶」的系統標題，本頁標題用「抓蝴蝶」。"
    ))
    if has_string("butterfly_catch_148") or has_string("butterfly_catch_149"):
        ea = []
        for key in ("butterfly_catch_148", "butterfly_catch_149"):
            if has_string(key):
                ea.append(visible_official(official_text(key)))
        add(p_html(
            "另有「" + "」「".join(H(x, terms) for x in ea) + "」。"
            "沒有官方說明這段括號是什麼，不自行解釋。"
        ))
    add(p_html(
        "名稱與說明以遊戲裡看得到的為準。道具對不上官方短名的，不靠編號或順序去對。"
        "星級與品質是兩個欄，即使這批列上數值相同，也不合併成同一個官方概念。"
        "以下是表上的數字，沒有額外的官方中文欄名。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    row = next((r for r in info if r.get("id") == 30003), None)
    if row:
        add(f"<h3>{H(help_title, terms)}</h3>")
        parts.extend(render_info_pages(row, terms))
    add("    </section>")

    add('    <section id="catalog">')
    add("      <h2>蝴蝶名錄</h2>")
    add(p_html(f"名錄共 {len(info_rows)} 筆，名稱與類型皆有官方中文。"))
    rows = []
    for r in info_rows:
        name = visible_official(official_text(r.get("name")))
        typ = visible_official(official_text(r.get("typename")))
        rows.append([
            H(name, terms) if name else "沒有官方名稱",
            H(typ, terms) if typ else "沒有官方類型名",
            e(str(r.get("star"))),
            e(str(r.get("quality"))),
        ])
    add(table(
        ["名稱", "類型", "星級", "品質"],
        rows,
        caption="蝴蝶名錄",
        mobile="cards",
        card_title="名稱",
    ))
    type_counts = Counter(visible_official(official_text(r.get("typename"))) for r in info_rows)
    add(p_html("類型筆數：" + "、".join(f"「{H(n, terms)}」{c} 筆" for n, c in type_counts.items()) + "。"))
    add("    </section>")

    add('    <section id="catch">')
    add("      <h2>捕捉與配對</h2>")
    add(p_html(
        f"捕捉配置有 {len(catch)} 列，名稱皆是「{H(area, terms)}」。"
        "沒有六個不同的官方活動名。差異在預覽天數等數值欄，以下只列數字，不自行解釋含義。"
    ))
    catch_rows = []
    for r in catch:
        catch_rows.append([
            H(area, terms),
            e(fmt_pipe(r.get("size"))),
            e(str(r.get("preview_day"))),
            e(str(r.get("wait_settle_day"))),
        ])
    add(table(
        ["名稱", "場地大小", "預覽天數", "結算等待天數"],
        catch_rows,
        caption="捕捉配置",
        mobile="cards",
        card_title="名稱",
    ))
    add(p_html("各列的獎勵與郵件欄，許多對不上官方道具短名，本頁不逐筆猜獎、不展開。"))
    ch = child[0]
    add(p_html(
        "配對與幼體表有 1 列。下列數字沒有官方欄位標題，不標成機率單位或時間單位。"
        f"自身相關數字 {e(str(ch.get('self_prop')))}，對方相關數字 {e(str(ch.get('the_other_prop')))}，"
        f"另有數字 {e(str(ch.get('butterfly_six_prop')))}。"
        f"交叉相關數字：{e(fmt_pipe(ch.get('stars_cross_prop')))}；"
        f"{e(fmt_pipe(ch.get('stars_cross_time')))}。"
        f"一至五星幼體相關數字："
        + "；".join(
            e(fmt_pipe(ch.get(k)))
            for k in (
                "one_star_child_prop", "two_star_child_prop", "three_star_child_prop",
                "four_star_child_prop", "five_star_child_prop",
            )
        )
        + "。"
    ))
    # items: do not map to 花蜜/檸檬
    named = []
    for key in (
        "butterfly_catch_36", "butterfly_catch_37", "butterfly_catch_38",
        "butterfly_catch_39", "butterfly_catch_191", "butterfly_catch_192",
        "butterfly_catch_232",
    ):
        if has_string(key):
            named.append(visible_official(official_text(key)))
    if has_string("goods_name_504225001"):
        named.append(visible_official(official_text("goods_name_504225001")))
    add(p_html(
        f"道具配置表有 {len(items)} 列。這些列沒有對得上的官方短名或說明，"
        "不靠後綴或順序去對界面用字。"
        "界面另有這些官方用字，只並列、不對號入座：「"
        + "」「".join(H(x, terms) for x in unique_keep_order(named))
        + "」。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"摸魚時光與魚缸、精靈小屋、牧場物語見"
        f"<a href=\"fish-tank.html\">{H(visible_official(official_text('activity_name_5001003') or '摸魚時光'), terms)}</a>、"
        f"<a href=\"elf-cottage.html\">{H(visible_official(official_text('elf_d1') or '精靈小屋'), terms)}</a>、"
        f"<a href=\"ranch-tale.html\">{H(visible_official(official_text('ether_ranch_030') or '牧場物語'), terms)}</a>。"
        "排行獎勵內容對不上官方短名的，不列入名錄。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add("<li>四張表在三批 extracts 全文相同。</li>")
    add("<li>道具列的 <code>item_id</code> 沒有 <code>goods_name_*</code>，可見正文不把它們對成花蜜或檸檬。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(page_title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_butterfly_catch_page() -> str:
    return render_html()
