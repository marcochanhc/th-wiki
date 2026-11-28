"""Public 商隊貿易 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter

from .catalog_common import (
    H,
    footer_swap,
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
    "carriage_quality.json": "97295fda20babaeb73e7939958e1394bd8918c8b8196cabd5bacdb62a1f38eb2",
    "carriage_car.json": "004ac32cf15b71aac9043767a1293bf32d80c060344a66332ebb59ddca5ac0aa",
    "carriage_captain_reward.json": "24dd3f1979fa3217f8d7781f975a5dabed0ee3a31863500e4b6ec360b70c6ee7",
    "trading.json": "711cb6d59b92777fb6fa60e070854e167280892985b43c58d7a81d97d39a7533",
    "trading_kvk.json": "846d485813229279799f744f62d0dbf7442d0e336f88d0ff3c9a488433fc1c4c",
    "trade_post.json": "f94ccde7004d53e6e66bb4151156a486cfd80d217c449d3e87cbfbf64145699e",
    "trade_post_shop.json": "b5f659bbc05702358b02bc6bb99607caf3d350514c7a46251df98740f9e2d670",
    "rob_setting.json": "4542bfa720baca978bb51f8116451f20f77a27ba38b28ad8dcaea4c909fd260b",
}

INFO_SHA256 = "48e3a023094f1f80e9725b8a13a8c82efcdd288b9527fc5a6df41003f50631fe"

# Official quality labels 1–6; there is no official name for quality 99.
QUALITY_KEYS = {
    1: "hatred_carriagr1",
    2: "hatred_carriagr2",
    3: "hatred_carriagr3",
    4: "hatred_carriagr4",
    5: "hatred_carriagr5",
    6: "hatred_carriagr6",
}

INFO_IDS = (14001, 14002, 14004, 35008, 50054, 60104, 60105)


def terms_for(extra: list[str] | None = None) -> list[str]:
    names = [
        official_text("quick_bar_caravan_trade_new"),
        official_text("business_delegation_desc_14"),
        official_text("season_memo_s4_point3_title"),
        official_text("business_group_info_title"),
        official_text("UI_Title_60104"),
        official_text("kvk_trade_post_11"),
        official_text("UI_Title_60105"),
        official_text("carriage_info_022"),
        official_text("UI_Title_038"),
        official_text("UI_Title_039"),
        official_text("UI_Title_090"),
        official_text("map_filter_example_personal_carriage"),
        official_text("map_filter_example_guild_carriage"),
        official_text("map_filter_example_group_carriage"),
        official_text("citybuilding_name_151"),
        "深海貿易商團",
        "天空貿易商團",
        "海底貿易商團",
    ]
    for key in QUALITY_KEYS.values():
        names.append(official_text(key))
    for key in (
        "business_delegation_desc_58", "business_delegation_desc_59",
        "business_delegation_desc_60", "business_delegation_desc_61",
        "business_group_station_1", "business_group_station_2",
        "business_group_station_3", "business_group_station_4",
    ):
        names.append(official_text(key))
    if extra:
        names.extend(extra)
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def _info_row(rows: list[dict], info_id: int):
    return next((r for r in rows if r.get("id") == info_id), None)


def _station_name(row: dict) -> str:
    key = row.get("name")
    text = visible_official(official_text(key)) if key else ""
    return text or "遊戲中文名稱表沒有對應名稱"


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    info_rows = load_table("info.json", INFO_SHA256)
    terms = terms_for()

    trade = visible_official(official_text("quick_bar_caravan_trade_new") or "商隊貿易")
    group = visible_official(official_text("business_delegation_desc_14") or "貿易商團")
    sea = visible_official(official_text("season_memo_s4_point3_title") or "海底貿易商團")
    sky = visible_official(official_text("business_group_info_title") or "天空貿易商團規則")
    sky_name = sky.replace("規則", "") if sky.endswith("規則") else sky
    # Keep official titles intact; 天空貿易商團規則 is the official rule-page title.
    post = visible_official(official_text("UI_Title_60104") or official_text("kvk_trade_post_11") or "貿易站")
    shop = visible_official(official_text("UI_Title_60105") or "貿易商店")
    personal = visible_official(official_text("map_filter_example_personal_carriage") or "個人商隊")
    guild = visible_official(official_text("map_filter_example_guild_carriage") or "公會商隊")
    team = visible_official(official_text("map_filter_example_group_carriage") or "組隊商隊")
    hall = visible_official(official_text("citybuilding_name_151") or "商隊")

    title = f"Top Heroes Wiki｜{trade}"
    lede = (
        f"本頁寫「{trade}」，並並列「{group}」的「{sea}」與「{sky}」，以及「{post}」。"
        "這幾套系統名稱並列保留，不自行合併。"
        "只見於說明文、表上沒有對上常數的次數上限，會標成未驗證。"
    )
    summary = f"{trade}圖鑑：品質與官方規則，並並列貿易商團與貿易站。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "quality", "label": "品質與車隊表"},
        {"id": "groups", "label": "貿易商團與貿易站"},
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
        "名稱與說明以遊戲裡看得到的為準。"
        f"快捷列官方名是「{H(trade, terms)}」。"
        f"另有「{H(group, terms)}」，其變體是「{H(sea, terms)}」與「{H(sky, terms)}」，二者不是同一名稱，本頁不合併書寫。"
        f"「{H(sea, terms)}」的說明文另寫「{H('深海貿易商團', terms)}」，這是另一句官方原文，與標題並列保留，不改字。"
        f"「{H(post, terms)}」與「{H(shop, terms)}」是再並列的一套界面，不是把商團併進商隊貿易。"
        f"過濾示例還有「{H(personal, terms)}」、「{H(guild, terms)}」、「{H(team, terms)}」。"
        f"城建顯示名「{H(hall, terms)}」是建築名，本頁不展開升級。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    for iid in INFO_IDS:
        row = _info_row(info_rows, iid)
        if not row:
            continue
        heading = visible_official(official_text(row.get("title")) or "")
        if heading:
            add(f"<h3>{H(heading, terms)}</h3>")
        for block in render_info_pages(row, terms):
            add(block)
    plunder = visible_official(official_text("carriage_info_013"))
    if plunder:
        add("<h3>劫掠說明裡的次數</h3>")
        add(quote_block(plunder, terms))
        add(p_html(
            "說明文寫每日最多掠奪 4 次、被掠奪過 2 次的商隊無法被繼續掠奪。"
            "這些數字只出現在官方說明，對應常數表沒有對上同一數字的欄位，列為未驗證。"
        ))
    add("    </section>")

    add('    <section id="quality">')
    add("      <h2>品質與車隊表</h2>")
    quality_rows = data["carriage_quality.json"]
    car_rows = data["carriage_car.json"]
    qcounts = Counter(r.get("quality") for r in quality_rows)
    qtable = []
    for q in sorted(qcounts):
        key = QUALITY_KEYS.get(q)
        name = visible_official(official_text(key)) if key else ""
        label = H(name, terms) if name else "遊戲中文名稱表沒有對應名稱"
        qtable.append([str(q), label, str(qcounts[q])])
    add(p_html(
        f"品質表 {len(quality_rows)} 列、車隊報酬表 {len(car_rows)} 列，不逐列傾印。"
        "品質 1 至 6 有官方品質名；另有一列品質編號沒有官方名稱，不編造稱呼。"
        "時間欄是表上的數字，表沒有單位欄，本頁不自行標成秒或小時。"
    ))
    add(table(
        ["品質編號", "官方名稱", "列數"],
        qtable,
        caption="商隊品質",
        mobile="cards",
        card_title="品質編號",
    ))
    cap = data["carriage_captain_reward.json"]
    add(p_html(
        f"隊長報酬表有 {len(cap)} 列。表上另有一欄數字，本頁不把它寫成官方第 N 季，也不傾印全部報酬內容。"
    ))
    add("    </section>")

    add('    <section id="groups">')
    add("      <h2>貿易商團與貿易站</h2>")
    sea_rows = data["trading.json"]
    sky_rows = data["trading_kvk.json"]
    sea_names = unique_keep_order(_station_name(r) for r in sea_rows)
    sky_names = unique_keep_order(_station_name(r) for r in sky_rows)
    add(p_html(
        f"「{H(sea, terms)}」站點官方名是"
        + "、".join(f"「{H(n, terms)}」" for n in sea_names)
        + f"。共 {len(sea_rows)} 列。"
    ))
    add(p_html(
        f"「{H(sky, terms)}」站點官方名是"
        + "、".join(f"「{H(n, terms)}」" for n in sky_names)
        + f"。共 {len(sky_rows)} 列。"
    ))
    posts = data["trade_post.json"]
    post_names = unique_keep_order(
        visible_official(official_text(r.get("name"))) or "遊戲中文名稱表沒有對應名稱" for r in posts
    )
    add(p_html(
        f"「{H(post, terms)}」定義表有 {len(posts)} 列，官方顯示名是"
        + "、".join(f"「{H(n, terms)}」" for n in post_names)
        + f"。商店表另有 {len(data['trade_post_shop.json'])} 列，本頁不傾印商品清單。"
        "站點表另有陣營與等級欄，不把欄位數字寫成官方第 N 季。"
    ))
    time_pairs = []
    for row in posts:
        raw = row.get("open_time")
        shown = str(raw).replace("|", "｜") if raw not in (None, "", -1, "-1") else ""
        dur = row.get("fight_duration")
        time_pairs.append((shown, dur))
    time_counts = Counter(time_pairs)
    add(p_html(
        f"「{H(post, terms)}」的官方說明已寫「開啟時間：週五」「每次爭奪時間：1 小時」，見上方官方說明。"
        "本頁使用的現行表裡，開放時段的數字有兩組，以下是表上的數字，沒有額外的官方中文欄名："
        + "；".join(
            f"{cnt} 列是 {shown}，對應時長數字 {dur:,}"
            for (shown, dur), cnt in sorted(time_counts.items(), key=lambda x: (x[1], x[0][0]))
        )
        + "。"
        "這三段數字各自的含義、以及它們如何對上說明文的「週五」與「1 小時」，尚未核對，"
        "本頁不把它寫成鐘點或星期幾的時間表，也不自行換算時長單位。"
        "較早的 2026-11-05 抽取裡，同樣 60 列的時段數字是 0｜4｜2（24 列）與 1｜4｜2（36 列），"
        "與現行值不同，不混成同一份時段。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"車隊報酬 {len(car_rows)} 列與貿易商店 {len(data['trade_post_shop.json'])} 列不逐筆展開。"
        f"掠奪係數表有 {len(data['rob_setting.json'])} 列，沒有對上說明文每日次數的欄位，不把係數表讀成已被核對的次數上限。"
        "本頁也不把說明文裡的次數寫成已核對的常量表。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{e(sha)}</code>，{len(data[name])} 列。</li>")
    add(f"<li><code>info.json</code> SHA-256 <code>{e(INFO_SHA256)}</code>；本頁引用的說明頁依標題照錄。</li>")
    add(
        "<li>品質 1–6 的官方名來自 <code>hatred_carriagr1</code> 至 <code>hatred_carriagr6</code>。"
        "品質 99 沒有對應官方名。</li>"
    )
    add(
        "<li>「海底貿易商團」來自 <code>season_memo_s4_point3_title</code>，可見正文只寫這個官方名，"
        "不把它對成官方第 4 季。</li>"
    )
    add(
        "<li>「天空貿易商團規則」是說明頁官方標題，與「海底貿易商團」並列，不另造合併名稱。</li>"
    )
    add(
        "<li>貿易站開放時段欄是 <code>open_time</code>。"
        "現行 LocalLow／live 為 <code>0|4|12</code> 24 列（<code>group</code> 1001，<code>fight_duration</code> 79200）"
        "與 <code>1|4|12</code> 36 列（<code>group</code> 1002，<code>fight_duration</code> 3600）。"
        "2026-11-05 抽取 SHA-256 <code>56d72980b96d14b51543e190da75e1d031b9fab7d8ebc2aa70fda41accc17a2a</code>，"
        "同樣分組的時段數字是 <code>0|4|2</code> 與 <code>1|4|2</code>，只改了第三段。"
        "三段含義及與官方「開啟時間：週五」「每次爭奪時間：1 小時」的對應尚未核對。"
        "<code>next_open</code>、<code>close_time</code>、<code>shop_close_time</code> 的單位與鐘點對應亦未核對，可見正文不展開。</li>"
    )
    add("    </ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_caravan_trade_page() -> str:
    return render_html()
