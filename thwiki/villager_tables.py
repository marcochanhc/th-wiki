"""Public 村民 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter

from .catalog_common import (
    H,
    file_sha256,
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
    "villagers.json": "ce58c357361a5aab2bf7789c7f4642ec56ac282ba156b869090eee9b0522870f",
    "villagers_name.json": "1461671ceb75c5b3d92807852aa59fc8b14e95407c716bcad510f5569356710d",
    "villagers_image.json": "d5be5c03cf1289cb85e9540f9f581e213f18f84c57b9c1329a11f780e3af8b15",
    "villagers_skills.json": "306c77131371249e742f88f88b983f9df051edf4e7f1115e3cb4f3d6b87abf53",
    "slot.json": "a09481013848b3f2f1232960307b5e4b98ceca5d731a64243290d22938ed22d4",
    "village_style.json": "1482cf5a2ba63c1980aa62f6c732c500149e7161a888c01f21814c77f918bc80",
    "gacha_villagers.json": "e639e0998d85c37f05db6c9d6b984afcd1fd37b5f150a3fb20e38217eed07348",
    "village.json": "972341f77c88e385cd546d8b2f29fd23ea44ef7d3ac71edb509c1d7e1c00fa31",
    "parkour_villagers.json": "3d78999e4d83920fb8ca8d66e5f82ee67d12edf5e5804ac5c122034ccc088ab9",
    "citybuilding.json": "25dc79829dcc0888168e76fe7f2bd5cb9d4dc97df6cecdc98b6e01cb24c24a0f",
}

INFO_SHA256 = "48e3a023094f1f80e9725b8a13a8c82efcdd288b9527fc5a6df41003f50631fe"


def terms_for(extra: list[str] | None = None) -> list[str]:
    names = [
        official_text("building_info_tab_2"),
        official_text("info_title_36004"),
        official_text("UI_VillagerList_001"),
        official_text("UI_Villager_4"),
        official_text("gacha_d_name_herotab"),
        official_text("goods_name_1019"),
        official_text("villagers_sp_10024"),
        official_text("village_style_0"),
        official_text("village_style_1"),
        official_text("village_style_2"),
        official_text("village_style_3"),
        official_text("village_style_4"),
        official_text("village_style_5"),
        official_text("village_style_6"),
        official_text("citybuilding_name_10"),
        "部落陣營",
    ]
    for key in (
        "villager_name_20001",
        "villager_name_20002",
        "villager_name_20004",
        "hero_detailed_stats_ui_gratitude_38",
    ):
        names.append(official_text(key))
    if extra:
        names.extend(extra)
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def _name_map(rows: list[dict]) -> dict:
    return {r["id"]: r for r in rows}


def villager_display_name(row: dict, name_by_id: dict) -> str:
    rec = name_by_id.get(row.get("name"))
    if not rec:
        return "名稱編號未對上"
    text = visible_official(official_text(rec.get("name")))
    return text or "遊戲中文名稱表沒有對應名稱"


def building_display_name(row: dict) -> str:
    key = row.get("name")
    text = visible_official(official_text(key)) if key else ""
    return text or "遊戲中文名稱表沒有對應名稱"


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    info_rows = load_table("info.json", INFO_SHA256)
    name_by_id = _name_map(data["villagers_name.json"])
    villagers = data["villagers.json"]
    stars = [r for r in villagers if r.get("is_star") == 1]
    non_stars = [r for r in villagers if r.get("is_star") != 1]
    other_typed = [r for r in non_stars if r.get("type") in (3, 4)]

    star_names = [villager_display_name(r, name_by_id) for r in stars]
    skill_rows = data["villagers_skills.json"]
    skill_series = []
    seen_series = set()
    extra_terms = list(star_names)
    for row in skill_rows:
        keys = row.get("name") or []
        names = [visible_official(official_text(k)) or "遊戲中文名稱表沒有對應名稱" for k in keys]
        bkey = row.get("buildingName")
        bname = visible_official(official_text(bkey)) if bkey and official_text(bkey) else (
            "遊戲中文名稱表沒有對應名稱" if bkey else "遊戲中文名稱表沒有對應名稱"
        )
        first = names[0] if names else "遊戲中文名稱表沒有對應名稱"
        last = names[-1] if names else "遊戲中文名稱表沒有對應名稱"
        sig = (tuple(names), bname)
        extra_terms.extend(names)
        extra_terms.append(bname)
        if sig in seen_series:
            for item in skill_series:
                if (tuple(item["names"]), item["building"]) == sig:
                    item["count"] += 1
                    break
            continue
        seen_series.add(sig)
        skill_series.append({"names": names, "first": first, "last": last, "building": bname, "count": 1})

    buildings = {r["id"]: r for r in data["citybuilding.json"]}
    work_rows = []
    for row in data["citybuilding.json"]:
        if row.get("isCanVillager") is True or row.get("is_villager") == 1:
            num = row.get("villager_build_num")
            work_rows.append({
                "name": building_display_name(row),
                "num": "未填人數" if num in (None, "", -1) else str(num),
            })
            extra_terms.append(building_display_name(row))

    slot_rows = data["slot.json"]
    slot_named = Counter()
    unmatched = 0
    for row in slot_rows:
        bid = row.get("citybuilding")
        bld = buildings.get(bid)
        if not bld:
            unmatched += 1
            continue
        slot_named[building_display_name(bld)] += 1

    styles = []
    for row in data["village_style.json"]:
        sname = visible_official(official_text(row.get("name"))) or "遊戲中文名稱表沒有對應名稱"
        styles.append(sname)
        extra_terms.append(sname)
    style_ground = visible_official(official_text("village_style_6"))

    terms = terms_for(extra_terms)
    func_name = visible_official(official_text("building_info_tab_2") or "村民")
    unit_name = visible_official(official_text("villager_name_20001") or "村民")
    rules_title = visible_official(official_text("info_title_36004") or "村民規則")
    list_title = visible_official(official_text("UI_VillagerList_001") or official_text("UI_Villager_4") or "村民列表")
    recruit = visible_official(official_text("gacha_d_name_herotab") or "村民招募")
    ticket = visible_official(official_text("goods_name_1019") or "村民招募券")
    ranch = visible_official(official_text("citybuilding_name_10") or "牧場")

    title = f"Top Heroes Wiki｜{func_name}"
    lede = (
        f"本頁寫功能名「{func_name}」的規則摘要、明星名冊與工作格對照。"
        f"功能名「{func_name}」與單位名「{unit_name}」是不同的官方字串，並列保留，不合併成一種用法。"
        f"界面列表標題是「{list_title}」，招募分頁是「{recruit}」。"
        "技能只列系列名稱與生效建築，不傾印全部數值。"
    )
    summary = f"{func_name}圖鑑：官方規則、明星名冊與工作格對照。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "roster", "label": "明星名冊"},
        {"id": "skills", "label": "技能系列"},
        {"id": "slots", "label": "工作格對照"},
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
        f"定義表共 {len(villagers)} 列，其中明星標記 {len(stars)} 列、其餘 {len(non_stars)} 列。"
        f"功能名來自界面分頁「{H(func_name, terms)}」；單位名「{H(unit_name, terms)}」出現在另一組名稱鍵，兩者同字不同鍵。"
        f"本頁不把跑酷地圖上的放置、地圖救援來源，或村莊區域表，當成可招募名冊。"
        f"城建裡的「{H(ranch, terms)}」是建築名，與本頁功能不是同一鍵。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add(f"      <h2>{H(rules_title, terms)}</h2>")
    info = next((r for r in info_rows if r.get("id") == 36004), None)
    if info:
        add(p_html(f"說明頁標題是「{H(rules_title, terms)}」。"))
        for block in render_info_pages(info, terms):
            add(block)
    up = visible_official(official_text("UI_Villager_up_info"))
    if up:
        add("<h3>升級說明</h3>")
        add(quote_block(up, terms))
    body_info = visible_official(official_text("UI_Villager_info"))
    if body_info:
        add("<h3>派遣與戰力</h3>")
        add(quote_block(body_info, terms))
    visit = visible_official(official_text("UI_Villager_24"))
    if visit:
        add("<h3>取得途徑</h3>")
        add(quote_block(visit, terms))
        add(p_html(
            "說明文提到冒險救援、村民拜訪與村民招募等來源；"
            "說明裡的未填空位保持原樣，本頁不代填數字。"
        ))
    gacha = data["gacha_villagers.json"][0]
    add(p_html(
        f"招募分頁官方名是「{H(recruit, terms)}」，對應道具官方短名是「{goods_label(gacha.get('item_id'), terms) or H(ticket, terms)}」。"
        f"招募表只有 {len(data['gacha_villagers.json'])} 列。"
    ))
    add("    </section>")

    add('    <section id="roster">')
    add("      <h2>明星名冊</h2>")
    add(p_html(
        f"明星標記列共 {len(stars)} 人，以下只列官方顯示名。"
        + (
            f"其中「{H('主廚', terms)}」出現兩次，表上是兩列同一顯示名，本頁不另行合併或改名。"
            if star_names.count("主廚") >= 2
            else ""
        )
    ))
    roster_rows = [[H(n, terms)] for n in star_names]
    add(table(["官方顯示名"], roster_rows, caption="明星標記村民", mobile="cards", card_title="官方顯示名"))
    other_names = unique_keep_order(villager_display_name(r, name_by_id) for r in other_typed)
    add(p_html(
        f"其餘 {len(non_stars)} 列也有官方顯示名，共 {len(set(villager_display_name(r, name_by_id) for r in non_stars))} 種，不在此逐列傾印。"
        f"其中另有一組具名列，官方顯示名是"
        + "、".join(f"「{H(n, terms)}」" for n in other_names)
        + "，這些列不是明星標記。"
    ))
    ted_desc = visible_official(official_text("villagers_sp_10024"))
    if ted_desc:
        add(p_html("其中一位非明星列「泰德」的官方特殊說明如下，用字以遊戲裡看得到的為準。"))
        add(quote_block(ted_desc, terms))
    add("    </section>")

    add('    <section id="skills">')
    add("      <h2>技能系列</h2>")
    add(p_html(
        f"技能表共 {len(skill_rows)} 列，整理成 {len(skill_series)} 個官方名稱系列。"
        "下表只寫系列的起迄稱謂與生效建築，不傾印各級數值。"
        "同一學徒稱謂若生效建築或最高稱謂不同，就分成不同系列。"
    ))
    skill_tbl = []
    for item in skill_series:
        if item["first"] == item["last"]:
            series = H(item["first"], terms)
        else:
            series = f"{H(item['first'], terms)}至{H(item['last'], terms)}"
        bld = item["building"]
        bld_h = H(bld, terms) if bld != "遊戲中文名稱表沒有對應名稱" else "遊戲中文名稱表沒有對應名稱"
        skill_tbl.append([series, bld_h, str(item["count"])])
    add(table(
        ["技能系列", "生效建築", "列數"],
        skill_tbl,
        caption="村民技能系列（名稱與建築）",
        mobile="cards",
        card_title="技能系列",
    ))
    add("    </section>")

    add('    <section id="slots">')
    add("      <h2>工作格對照</h2>")
    add(p_html(
        f"城建定義裡標記可派遣村民的建築共 {len(work_rows)} 座。"
        "人數欄只在表有填時列出；未填者不猜測格數。"
    ))
    add(table(
        ["建築", "表上人數"],
        [[H(r["name"], terms) if r["name"] != "遊戲中文名稱表沒有對應名稱" else "遊戲中文名稱表沒有對應名稱", r["num"]] for r in work_rows],
        caption="可派遣村民的建築",
        mobile="cards",
        card_title="建築",
    ))
    named_bits = "、".join(
        f"「{H(name, terms)}」{count} 格" for name, count in slot_named.most_common()
    )
    add(p_html(
        f"工作格表共 {len(slot_rows)} 列。對得上城建官方名的有{named_bits}。"
        f"另有 {unmatched} 列的建築編號在城建表對不上，不編造建築名。"
    ))
    if styles:
        style_txt = "、".join(f"「{H(s, terms)}」" for s in styles)
        extra = f"遊戲中文名稱表另有「{H(style_ground, terms)}」，但樣式表沒有對應列。" if style_ground and style_ground not in styles else ""
        add(p_html(
            f"村莊樣式官方名是{style_txt}。{extra}"
            "樣式表另有一欄數字，本頁不把它寫成官方第 N 季。"
        ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"跑酷村民表有 {len(data['parkour_villagers.json'])} 列，只見地圖放置，沒有可招募官方名冊，不當作明星或招募名單。"
        f"村莊區域表有 {len(data['village.json'])} 列，不是招募名冊。"
        f"形象表有 {len(data['villagers_image.json'])} 列，本頁不展開外觀資源。"
        "技能數值、招募權重與未填的說明空位，本頁都不代填或推算。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{e(sha)}</code>，{len(data[name])} 列。</li>")
    add(f"<li><code>info.json</code> SHA-256 <code>{e(INFO_SHA256)}</code>；本頁只用標題為「{e(rules_title)}」的說明頁。</li>")
    add(
        "<li>單位名「村民」來自 <code>villager_name_20001</code> 等鍵；名冊顯示名來自 <code>villagers_name</code>。"
        "功能名來自 <code>building_info_tab_2</code>。這三組不是同一鍵。</li>"
    )
    add(
        "<li>明星標記原欄是 <code>is_star=1</code>。"
        "鍛造系列生效建築鍵是 <code>UI_Villager_28</code>，字串表沒有這個鍵，可見正文寫「遊戲中文名稱表沒有對應名稱」。</li>"
    )
    add(
        "<li>「泰德」特殊說明鍵 <code>villagers_sp_10024</code> 原文是「部落陣營」，照錄，不改成「部族」。</li>"
    )
    add(
        "<li>功勳碑產量說明用「勛章」，與「勳章」不同字，照錄官方寫法。</li>"
    )
    add("    </ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_villagers_page() -> str:
    return render_html()
