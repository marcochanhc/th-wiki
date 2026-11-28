"""Public 精靈小屋 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import defaultdict

from .catalog_common import (
    H,
    footer_swap,
    fmt_pipe,
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
    "elf_act.json": "8ecaf05757a5fa0fde543613e2f31fdfd818d5c8ab6d0cc164553916348b38fb",
    "elf_food.json": "0ccc17acbf03aafb22351b8af3f26aaf1e4200c4fdf828b06c2fbc4d1b0daa5b",
    "elf_lvup.json": "7b63bc053249e3aa16bc54df8b4af57f08fba02de543274c2be1a5fed51d2b46",
    "elf_reward.json": "9c60693a7a4ba83f788566b48a83c6aec5bb51bc68f4333f41d96371ee4050fe",
    "elf_season_desc.json": "66055402aa46d59715933af382b3f31d43af733edeea44a1a87e1513ce4689ed",
    "elf_skin.json": "c4f8451901cfaf2b56b9e57405e4d2ebd090390c359ac540b41837e0935f3cb5",
    "elf_task.json": "3c37757a479d798e4f967208ad10826e21f2c4c4cc2e1573f30b8ac1c2d32e60",
    "elf_task_person.json": "216ebdaa4b683592596d6f1181bb5fd6d749acd09df4e64e22c6e4471d50f8cb",
    "elf_unlockfunc.json": "e1a56105c7bde33b5372250398f9640fc22448a28d70f808feee4a3755482f4f",
}


def terms_for() -> list[str]:
    names = [
        official_text("elf_d1"), official_text("elf_name23"), official_text("elf_rule_title1"),
        official_text("elf_d113"), official_text("info_title_50023"), official_text("info_title_50030"),
        official_text("info_title_50049"), official_text("season_preview_title_404"),
        official_text("info_title_50026"), official_text("info_title_50028"),
        official_text("elf_rule_title2"), official_text("elf_rule_title3"),
        official_text("elf_name1"), official_text("elf_d3"), official_text("elf_d5"),
        official_text("elf_title1_1"), official_text("elf_title1_2"), official_text("elf_title1_3"),
        official_text("elf_title2_1"), official_text("elf_title2_2"), official_text("elf_title2_3"),
        official_text("elf_title2_4"), official_text("elf_title3_1"), official_text("elf_title3_2"),
        official_text("elf_title3_3"),
    ]
    for i in range(1, 7):
        names.append(official_text(f"elf_season_theme_{i}"))
    for i in range(1, 16):
        names.append(official_text(f"elf_name{i}"))
        names.append(official_text(f"elf_food_d{i}"))
        names.append(official_text(f"elf_skin_d{i}"))
    names.extend([
        official_text("elf_d101"),  # 精靈打工
        official_text("elf_d102"),  # 共同餵養
        official_text("elf_d25"),   # 餵養精靈
        "精靈互動",
        "與精靈互動",
        "與他人精靈互動",
        "雙方各自與精靈互動",
        "精靈餵養",
        "精靈合養",
        "精靈開始打工",
        "精靈正在打工",
        "對每隻精靈互動",
    ])
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def load_data() -> dict:
    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    data["info.json"] = load_table("info.json")
    return data


def info_row(info, iid):
    return next((r for r in info if r.get("id") == iid), None)


def render_html() -> str:
    from .render import page_shell, toc_list

    data = load_data()
    terms = terms_for()
    hut = visible_official(official_text("elf_d1") or "精靈小屋")
    short = visible_official(official_text("elf_rule_title1") or "精靈")
    title = f"Top Heroes Wiki｜{hut}"
    lede = (
        f"本頁寫「{hut}」的合養、餵養、打工、互動、裝扮、任務與週里程碑規則。"
        f"界面短名是「{short}」。"
    )
    summary = f"{hut}圖鑑：短名「{short}」。合養規則、行動、食物、升級、裝扮與任務。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "themes", "label": "主題字串"},
        {"id": "actions", "label": "互動、打工與功能"},
        {"id": "food", "label": "食物與好感"},
        {"id": "levels", "label": "升級"},
        {"id": "skins", "label": "裝扮"},
        {"id": "tasks", "label": "任務與週里程碑"},
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
        f"功能主名是「{H(hut, terms)}」，短名是「{H(short, terms)}」。"
        f"另有「{H(visible_official(official_text('season_preview_title_404')), terms)}」。"
        f"預告文案寫「{H(visible_official(official_text('season_preview_desc_411')), terms)}」。"
        "「合養」與「共養」不是同一個詞，本頁並列保留，不合併。"
    ))
    add(p_html(
        f"還有「{H(visible_official(official_text('elf_d113')), terms)}」、"
        f"「{H(visible_official(official_text('info_title_50030')), terms)}」、"
        f"「{H(visible_official(official_text('info_title_50049')), terms)}」。"
        "遊戲中文名稱表沒有「精靈圖鑑」這個名稱，本頁標題用官方功能名。"
    ))
    add(p_html(
        "名稱與說明以遊戲裡看得到的為準。表上若分成多組，只說明列數與內容，不把分組或主題字串寫成官方第 N 季，也不評定養成優先。"
        "名稱若與其他系統共用同一句官方用字，仍用該官方名稱，不改當成別種道具。"
        "以下是表上的數字，沒有額外的官方中文欄名，不自行命名各段含義。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    for iid in (50023, 50025, 50026, 50028, 50030, 50049):
        row = info_row(data["info.json"], iid)
        if not row:
            continue
        heading = visible_official(official_text(row.get("title")))
        if heading:
            add(f"<h3>{H(heading, terms)}</h3>")
        parts.extend(render_info_pages(row, terms))
    add("    </section>")

    add('    <section id="themes">')
    add("      <h2>主題字串</h2>")
    add(p_html(
        "下列是遊戲裡看得到的主題名稱。不把它們與王國對決的輪次等號。"
    ))
    theme_rows = []
    for i in range(1, 7):
        key = f"elf_season_theme_{i}"
        if has_string(key):
            theme_rows.append([H(visible_official(official_text(key)), terms)])
    add(table(
        ["主題字串"],
        theme_rows,
        caption="精靈主題字串",
        mobile="cards",
        card_title="主題字串",
    ))
    add(p_html(
        "另有一張主題說明表，把上述名稱與表上其他欄位寫在同一列。本頁不把那些欄位寫進可見正文，也不據此標第 N 季。"
        "其中「地心探險」這個主題名稱出現在遊戲中文名稱表，但沒有出現在那張說明表的列裡。"
    ))
    add("    </section>")

    add('    <section id="actions">')
    add("      <h2>互動、打工與功能</h2>")
    unlock_rows = []
    for r in data["elf_unlockfunc.json"]:
        name = visible_official(official_text(r.get("name")))
        unlock_rows.append([H(name, terms) if name else "沒有官方名稱"])
    add(p_html("功能入口名稱："))
    add(table(
        ["功能"],
        unlock_rows,
        caption="精靈小屋功能入口",
        mobile="cards",
        card_title="功能",
    ))
    # collapse identical name+para actions
    act_map = defaultdict(list)
    for r in data["elf_act.json"]:
        name = visible_official(official_text(r.get("name")))
        para = r.get("para")
        act_map[(name, tuple(para) if isinstance(para, list) else para)].append(r)
    act_rows = []
    for (name, para), rows in act_map.items():
        para_txt = "｜".join(str(x) for x in para) if isinstance(para, tuple) else fmt_safe(para)
        act_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            e(para_txt),
            e(str(len(rows))),
        ])
    add(p_html(
        "行動名稱與參數如下。相同名稱與參數若有多列，只列一次並註明列數。"
    ))
    add(table(
        ["行動", "參數", "列數"],
        act_rows,
        caption="互動與打工行動",
        mobile="cards",
        card_title="行動",
    ))
    add("    </section>")

    add('    <section id="food">')
    add("      <h2>食物與好感</h2>")
    # foods identical across groups; 撫摸 rows separate
    food_unique = {}
    pet_rows = []
    for r in data["elf_food.json"]:
        name = visible_official(official_text(r.get("name")))
        key = (name, r.get("level"), r.get("sun_value"), r.get("if_free"), r.get("order"), r.get("sun_level"))
        food_unique.setdefault(key, 0)
        food_unique[key] += 1
        if official_text(r.get("name")) == official_text("elf_name2") or name == visible_official(official_text("elf_name2")):
            pet_rows.append(r)
    food_rows = []
    pet_table = []
    pet_name = visible_official(official_text("elf_name2"))
    for (name, level, sun, free, order, sun_level), n in food_unique.items():
        row = [
            H(name, terms) if name else "沒有官方名稱",
            e(str(level)),
            e(str(sun)),
            e(fmt_pipe(None if sun_level == "None" else sun_level).replace(";", "；")),
            e(str(n)),
        ]
        if name == pet_name:
            pet_table.append(row)
        else:
            food_rows.append(row)
    add(p_html("食物名稱與好感相關數字如下。六組內容相同，下表只列一份，並註明列數。"))
    add(table(
        ["名稱", "等級", "好感相關數字", "分段數字", "列數"],
        food_rows,
        caption="食物",
        mobile="cards",
        card_title="名稱",
    ))
    add(p_html(
        f"同一張表裡另有名稱為「{H(pet_name, terms)}」的列。這是官方名稱「{H(pet_name, terms)}」，"
        "與互動行動同名，本頁保留這個官方名稱，不改標成一種食物。"
        "分段數字與官方互動說明中的等級心情值可以對看，不另行換算。"
    ))
    add(table(
        ["名稱", "等級", "好感相關數字", "分段數字", "列數"],
        pet_table,
        caption="名稱為撫摸的列",
        mobile="cards",
        card_title="名稱",
    ))
    add("    </section>")

    add('    <section id="levels">')
    add("      <h2>升級</h2>")
    lv = data["elf_lvup.json"]
    groups = defaultdict(list)
    for r in lv:
        groups[r["group_id"]].append(r)
    exp_same = True
    base = groups[sorted(groups)[0]]
    base = sorted(base, key=lambda r: int(r["level"]))
    for g, rows in groups.items():
        rows = sorted(rows, key=lambda r: int(r["level"]))
        if [(r["level"], r["exp"]) for r in rows] != [(r["level"], r["exp"]) for r in base]:
            exp_same = False
            break
    add(p_html(
        f"升級表共 {len(lv)} 列，分成 {len(groups)} 組，各涵蓋 1 至 30 級。"
        + ("六組升級所需經驗相同，下表只列一份。" if exp_same else "各組經驗若不同，本頁分列數字。")
        + "各組等級獎勵的道具編號並非全部相同；沒有官方短名的不寫名稱，也不推測獎勵內容。"
    ))
    if exp_same:
        add(table(
            ["等級", "升級所需經驗"],
            [[e(str(r["level"])), e(str(r["exp"]))] for r in base],
            caption="共用升級經驗",
            mobile="cards",
            card_title="等級",
        ))
    add("    </section>")

    add('    <section id="skins">')
    add("      <h2>裝扮</h2>")
    skin_map = defaultdict(int)
    skin_meta = {}
    for r in data["elf_skin.json"]:
        name = visible_official(official_text(r.get("name")))
        key = (name, r.get("unlock_level"), r.get("rare"), r.get("if_free"))
        skin_map[key] += 1
        skin_meta[key] = r
    skin_rows = []
    for (name, unlock, rare, free), n in skin_map.items():
        free_txt = "免費" if free == 1 else (str(free) if free not in (-1, None) else "不是標成免費")
        # Don't invent quality names for rare
        skin_rows.append([
            H(name, terms) if name else "沒有官方名稱",
            e(str(unlock)),
            e(str(rare)),
            e(free_txt),
            e(str(n)),
        ])
    add(p_html(
        "裝扮依官方名稱列出。相同名稱、解鎖等級與稀有欄數字若有多列，只列一次並註明列數。"
        "稀有欄沒有官方中文名。"
    ))
    add(table(
        ["裝扮", "解鎖等級", "稀有", "是否免費", "列數"],
        skin_rows,
        caption="精靈裝扮",
        mobile="cards",
        card_title="裝扮",
    ))
    add("    </section>")

    add('    <section id="tasks">')
    add("      <h2>任務與週里程碑</h2>")
    def task_text(r):
        for field in ("task_discription", "desc", "task_describe"):
            key = r.get(field)
            if has_string(key):
                return visible_official(official_text(key))
        vo = r.get("taskConditionVo") or {}
        if isinstance(vo, dict) and has_string(vo.get("taskDesLanguageKey") or vo.get("taskDescribe")):
            return visible_official(official_text(vo.get("taskDesLanguageKey") or vo.get("taskDescribe")))
        return ""

    def collapse_tasks(rows, label):
        acc = defaultdict(int)
        for r in rows:
            text = task_text(r)
            acc[text] += 1
        out = []
        for text, n in acc.items():
            out.append([H(text, terms) if text else "沒有官方說明", e(str(n))])
        add(p_html(f"{label}共 {len(rows)} 列。相同說明只列一次，並註明列數。"))
        add(table(
            ["說明", "表上列數"],
            out,
            caption=label,
            mobile="cards",
            card_title="說明",
        ))

    collapse_tasks(data["elf_task.json"], "任務表")
    collapse_tasks(data["elf_task_person.json"], "個人任務表")
    rew = data["elf_reward.json"]
    add(p_html(
        f"週里程碑獎勵表共 {len(rew)} 列。本頁只記列數，不把對不上官方短名的獎勵編號寫成道具名。"
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        "魚缸、抓蝴蝶、牧場物語、帕魯、守護魔獸不作為本頁正文。"
        f"見已發佈或同批公開的"
        f"<a href=\"fish-tank.html\">{H(visible_official(official_text('activity_name_5001003') or '摸魚時光'), terms)}</a>、"
        f"<a href=\"butterfly-catch.html\">{H(visible_official(official_text('butterfly_catch_42') or '抓蝴蝶'), terms)}</a>、"
        f"<a href=\"ranch-tale.html\">{H(visible_official(official_text('ether_ranch_030') or '牧場物語'), terms)}</a>、"
        f"<a href=\"pals.html\">{H('帕魯', terms)}</a>、"
        f"<a href=\"holybeasts.html\">{H('守護魔獸', terms)}</a>。"
    ))
    add(p_html(
        "世界樹捐獻與採集不搬入本頁。聊天火花的完整規則不是精靈表，只在合養條件需「點亮火花」時交叉引用官方句。"
        "沒有名稱等於「精靈小屋」的城建列，不把「建築小屋」混稱，也不展開城建升級排程。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add(
        "<li>任務兩張的列數與編號與 2026-11-05 相同，差異只在解析欄。"
        "正文以 LocalLow 原欄與說明鍵為準。</li>"
    )
    add(
        "<li>主題說明表的 <code>season</code>／<code>theme</code>／分組欄不寫進可見正文，"
        "也不對成官方第 N 季。</li>"
    )
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def fmt_safe(value) -> str:
    if value is None:
        return ""
    return str(value)


def render_elf_cottage_page() -> str:
    return render_html()
