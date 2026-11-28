"""Public 牧場物語 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter, defaultdict

from .catalog_common import (
    EXTRACT_DATA,
    H,
    file_sha256,
    footer_swap,
    goods_label,
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
    "ether.json": "ce881120b2204afbfb82b6b566de54eed85634f77ca8bd0305b1da886f335624",
    "ether_pool.json": "d00bc99bf514bfd90a0846437578962813b7df1019ee09832eb6a57763ab2bbc",
    "ether_exchange.json": "b13ec85c3744c0c70deddb060b274bd87b49655ef98407a7e2399043738437f6",
    "ether_exchange_goods.json": "5491b7a7dbce33805997600837f96373ef1ec1e0dd60618a20e6ebc8569eb5bb",
    "ether_ranch_repu.json": "32760546532887a24a02f22d5f1e533f0b1bfc4a9d89b3c9428c7b93e76fabc3",
    "ether_ranch_tech_detail.json": "3844cb09eaf87c10f1c204480c4f755254819f26b348d59a410f2bef628dea41",
    "ether_shop.json": "c09f5cb85697e02c941e6437c2eb5376c16278d16cb507e37fcd3e1b73813af4",
    "ether_task.json": "31dd1b9317e69374142f943cf1306b33e342b0d994f8ab52c62a786490baeb7d",
    "ether_settings.json": "d536e2d7dae8e99041852894ea4dbbec16665dd6785ef81ae7718c18b1cfcf89",
}


def terms_for() -> list[str]:
    names = [
        official_text("ether_ranch_030"), official_text("ether_ranch_067"),
        official_text("info_title_50044"), official_text("ether_ranch_029"),
        official_text("ether_ranch_025"), official_text("ether_ranch_001"),
        official_text("ether_ranch_002"), official_text("ether_ranch_003"),
        official_text("ether_ranch_004"), official_text("ether_ranch_022"),
        official_text("ether_ranch_054"), official_text("ether_ranch_145"),
        official_text("jump_name_2000079"), official_text("goods_name_606163003"),
        official_text("goods_name_606163004"), official_text("ether_ranch_info_title1"),
        official_text("ether_ranch_info_title2"), official_text("ether_ranch_042"),
        official_text("ether_ranch_098"), official_text("ether_task_04"),
        official_text("ether_task_05"), official_text("ether_task_06"),
        official_text("ether_task_07"), official_text("k2_boss_info_01"),
        official_text("citybuilding_name_10"), official_text("alliance_resource_3"), official_text("alliance_tech_name_303"),
    ]
    for i in range(1, 7):
        names.append(official_text(f"ether_pool_name_00{i}"))
    for key in ("ranch_tech_name_100101", "ranch_tech_name_100102", "ranch_tech_name_100103"):
        names.append(official_text(key))
    names.extend([
        "帕菲祝福",
        "帕菲打招呼",
        "與帕菲打招呼",
        "給好友的帕菲祝福",
        "為幼崽期帕菲祝福",
        "為成年期帕菲祝福",
        "跟您的帕菲打招呼",
    ])
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def pafi_terms(rows) -> list[str]:
    extra = []
    for r in rows:
        extra.append(visible_official(official_text(r.get("name"))))
    return [n for n in unique_keep_order(extra) if n and len(n) >= 2]


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    info = load_table("info.json")
    terms = terms_for() + pafi_terms(data["ether.json"])
    sys_name = visible_official(official_text("ether_ranch_030") or "牧場物語")
    unit = visible_official(official_text("ether_ranch_025") or "帕菲")
    dex = visible_official(official_text("ether_ranch_029") or "帕菲圖鑑")
    help_title = visible_official(official_text("info_title_50044") or "牧場物語活動說明")
    coin = visible_official(official_text("goods_name_606163003") or "牧歌金幣")
    cheese = visible_official(official_text("goods_name_606163004") or "帕菲起司")
    title = f"Top Heroes Wiki｜{sys_name}"
    lede = (
        f"本頁寫「{sys_name}」的尋覓、{unit}培養與產出、設施、聲望任務、商店與交易所。"
        f"單位官方名是「{unit}」。這不是城建裡的牧場，也不是界面圖鑑分頁「{dex}」所能涵蓋的全部內容。"
    )
    summary = f"{sys_name}圖鑑：{unit}名冊、棲息地、設施與官方活動說明。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "catalog", "label": f"{unit}名冊"},
        {"id": "habitats", "label": "尋覓與棲息地"},
        {"id": "facilities", "label": "設施"},
        {"id": "tasks", "label": "聲望、任務與商店"},
        {"id": "exchange", "label": "交易所"},
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
    tabs = []
    for key in (
        "ether_ranch_001", "ether_ranch_002", "ether_ranch_003", "ether_ranch_004",
        "ether_ranch_022", "ether_ranch_054", "ether_ranch_145", "jump_name_2000079",
    ):
        if has_string(key):
            tabs.append(visible_official(official_text(key)))
    add(p_html(
        f"官方總名是「{H(sys_name, terms)}」。規則標題是「{H(help_title, terms)}」。"
        f"界面圖鑑分頁是「{H(dex, terms)}」，與本頁所寫的整套玩法範圍不同，兩詞不合併。"
        f"分頁與功能名還有「" + "」「".join(H(x, terms) for x in unique_keep_order(tabs)) + "」。"
    ))
    add(p_html(
        f"貨幣官方短名是「{H(coin, terms)}」，說明：「{H(visible_official(official_text('goods_desc_606163003')), terms)}」。"
        f"食物官方短名是「{H(cheese, terms)}」，說明：「{H(visible_official(official_text('goods_desc_606163004')), terms)}」。"
        "界面另有「牧場代幣」「牧場金幣」「金幣」等用字，與「牧歌金幣」並列，不合併。"
        "說明中的「收藏憑證」與「收藏券」也並列，不合併。"
    ))
    add(p_html(
        "城建與同盟裡若也有「牧場」這個詞，與本系統分頁不是同一處，不合併，也不把城建升級排程搬進來。"
        "名稱與說明以遊戲裡看得到的為準。沒有官方顏色名，就不把品質寫成顏色。"
        "以下是表上的數字，沒有額外的官方中文欄名。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    row = next((r for r in info if r.get("id") == 50044), None)
    if row:
        add(f"<h3>{H(help_title, terms)}</h3>")
        parts.extend(render_info_pages(row, terms))
    # 打招呼 40% vs get_percent 20
    settings = data["ether_settings.json"][0]
    add(p_html(
        "上列打招呼說明寫了 40%。"
        f"設定表另有一個原值 {e(str(settings.get('get_percent')))}。"
        "兩者並列，不自行取捨哪一個才算顯示規則。"
    ))
    share = settings.get("share_rate")
    if share is not None:
        add(p_html(
            f"交易所說明寫分潤「10%」，設定表對應原值是 {e(str(share))}，兩者可對看。"
        ))
    add("    </section>")

    add('    <section id="catalog">')
    add(f"      <h2>{e(unit)}名冊</h2>")
    eth = data["ether.json"]
    add(p_html(
        f"名冊共 {len(eth)} 筆、{len({r.get('name') for r in eth})} 個不同名稱。"
        "同一名稱可對多筆、多個品質數字，不合併成一隻。"
        "部分名稱與其他系統共用同一句官方用字，本頁仍用該官方名稱，不改當成英雄或其他道具。"
    ))
    # collapse by official name: list qualities present, count
    by_name = defaultdict(list)
    for r in eth:
        name = visible_official(official_text(r.get("name")))
        by_name[name].append(r)
    cat_rows = []
    for name, rows in by_name.items():
        quals = "、".join(str(q) for q in unique_keep_order(r.get("ether_quality") for r in rows))
        cat_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            e(str(len(rows))),
            e(quals),
        ])
    add(table(
        ["名稱", "列數", "品質"],
        cat_rows,
        caption=f"{unit}名冊",
        mobile="cards",
        card_title="名稱",
    ))
    add("    </section>")

    add('    <section id="habitats">')
    add("      <h2>尋覓與棲息地</h2>")
    pool_rows = []
    for r in data["ether_pool.json"]:
        name = visible_official(official_text(r.get("name")))
        pool_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            e(str(r.get("unlock_level"))),
            e(str(r.get("open_time"))),
        ])
    add(p_html(
        "棲息地名稱如下。開放時間沒有單位欄，不自行標成小時。"
        "名冊裡的分類欄與棲息地如何對應，未驗證，本頁不自行對譯。"
    ))
    add(table(
        ["棲息地", "解鎖等級", "開放時間"],
        pool_rows,
        caption="棲息地",
        mobile="cards",
        card_title="棲息地",
    ))
    add("    </section>")

    add('    <section id="facilities">')
    add("      <h2>設施</h2>")
    tech = data["ether_ranch_tech_detail.json"]
    tech_names = unique_keep_order(visible_official(official_text(r.get("name"))) for r in tech)
    add(p_html(
        f"設施共 {len(tech_names)} 種、{len(tech)} 列，等級由 0 到 10。"
        "名稱是「" + "」「".join(H(n, terms) for n in tech_names if n) + "」。"
        "升級消耗與條件對不上官方短名的，不寫成道具名；本頁先列名稱與等級範圍。"
    ))
    fac_rows = []
    by_fac = defaultdict(list)
    for r in tech:
        by_fac[visible_official(official_text(r.get("name")))].append(int(r.get("lv")))
    for name, lvs in by_fac.items():
        fac_rows.append([H(name, terms) if name else "沒有官方名稱", e(f"{min(lvs)}–{max(lvs)}")])
    add(table(
        ["設施", "等級範圍"],
        fac_rows,
        caption="牧場設施",
        mobile="cards",
        card_title="設施",
    ))
    add("    </section>")

    add('    <section id="tasks">')
    add("      <h2>聲望、任務與商店</h2>")
    repu = data["ether_ranch_repu.json"]
    add(p_html(f"聲望表共 {len(repu)} 級。本頁只記級數，不把對不上官方短名的解鎖內容寫成道具名。"))
    # reputation item
    add(p_html(
        "聲望相關道具有說明「"
        + H(visible_official(official_text("goods_desc_606163005")), terms)
        + "」，但沒有官方短名，不另起名。"
    ))
    task_map = defaultdict(list)
    for r in data["ether_task.json"]:
        name = visible_official(official_text(r.get("name")))
        desc = visible_official(official_text(r.get("desc")))
        task_map[(name, desc)].append(r)
    task_rows = []
    for (name, desc), rows in task_map.items():
        task_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            H(desc, terms) if desc else "",
            e(str(len(rows))),
        ])
    add(p_html("委託任務名稱與說明如下。相同名稱與說明只列一次。"))
    add(table(
        ["任務", "說明", "表上列數"],
        task_rows,
        caption="委託任務",
        mobile="cards",
        card_title="任務",
    ))
    shop = data["ether_shop.json"]
    add(p_html(f"商店表共 {len(shop)} 列。對不上官方短名的商品不列入名錄。"))
    add("    </section>")

    add('    <section id="exchange">')
    add("      <h2>交易所</h2>")
    ex_row = next((r for r in info if r.get("id") == 50055), None)
    if ex_row:
        heading = visible_official(official_text(ex_row.get("title")))
        if heading:
            add(f"<h3>{H(heading, terms)}</h3>")
        parts.extend(render_info_pages(ex_row, terms))
    goods = data["ether_exchange_goods.json"]
    known = []
    unknown = 0
    for r in goods:
        gid = r.get("goods")
        # only use clearly matching exchange ticket strings already verified
        # 10001 -> ether_exchange_goods_009, 10002 -> 010; others unknown
        ticket = ""
        if r.get("id") == 10001 and has_string("ether_exchange_goods_009"):
            ticket = visible_official(official_text("ether_exchange_goods_009"))
        elif r.get("id") == 10002 and has_string("ether_exchange_goods_010"):
            ticket = visible_official(official_text("ether_exchange_goods_010"))
        if ticket:
            known.append([H(ticket, terms), e(str(r.get("price")))])
        else:
            unknown += 1
    add(p_html(
        f"交易所商品表有 {len(goods)} 列。其中 {len(known)} 列可對上官方收藏券名稱；"
        f"其餘 {unknown} 列沒有可靠的官方短名，不靠後綴或順序去對。"
        "遊戲中文名稱表另有更多「收藏券-…」名稱，未對上表列的不補進名錄。"
    ))
    if known:
        add(table(
            ["名稱", "價格"],
            known,
            caption="對得上官方名稱的收藏券",
            mobile="cards",
            card_title="名稱",
        ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"精靈小屋、摸魚時光與魚缸、抓蝴蝶見"
        f"<a href=\"elf-cottage.html\">{H(visible_official(official_text('elf_d1') or '精靈小屋'), terms)}</a>、"
        f"<a href=\"fish-tank.html\">{H(visible_official(official_text('activity_name_5001003') or '摸魚時光'), terms)}</a>、"
        f"<a href=\"butterfly-catch.html\">{H(visible_official(official_text('butterfly_catch_42') or '抓蝴蝶'), terms)}</a>。"
        "圖鑑進度獎勵、部分祝福與拜訪的顯示規則，以及對不上短名的商店內容，不列入。"
    ))
    ranch_tab = visible_official(official_text("ether_ranch_001"))
    city_ranch = visible_official(official_text("citybuilding_name_10"))
    guild_ranch = visible_official(official_text("alliance_resource_3"))
    if city_ranch and guild_ranch and ranch_tab:
        add(p_html(
            f"城建名稱「{H(city_ranch, terms)}」與同盟「{H(guild_ranch, terms)}」，"
            f"和本系統分頁「{H(ranch_tab, terms)}」不是同一鍵，不合併。"
            f"城建「{H(city_ranch, terms)}」的升級見已發佈的"
            f"<a href=\"city-buildings.html\">城建升級總表</a>；"
            f"「{H(guild_ranch, terms)}」不在本頁展開，也不另開未建立的圖鑑頁。"
        ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add(
        "<li>除設定表外，其餘八張主表在 11-05、11-22 StreamingAssets 與 LocalLow 全文相同。"
        "設定表差異只在解析欄是否已填入，原始設定欄相同；正文以 LocalLow 為準。</li>"
    )
    add(
        "<li>字串表沒有「乙太牧場」「以太牧場」或「以太」。這是手冊分類曾用的工作檔名，不是已核到的官方界面標題。"
        "本頁可見標題只用「牧場物語」。</li>"
    )
    add(
        "<li>打招呼說明中的 40% 與設定欄 <code>get_percent</code> 原值並列，不自行取捨。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_ranch_tale_page() -> str:
    return render_html()
