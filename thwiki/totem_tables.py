"""Public 先祖圖騰 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from .catalog_common import (
    H,
    attr_pair_label,
    cost_spec_label,
    footer_swap,
    goods_label,
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
    "kvk_totem.json": "ddae8453783da272a26991f437902876c83f13c8c33679bdd3c1640432648677",
}

FACTIONS = (
    (1, "citybuilding_name_122", "聯盟"),
    (2, "citybuilding_name_123", "部族"),
    (3, "citybuilding_name_124", "自然"),
)

SAMPLE_LEVELS = (1, 2, 3, 5, 10, 40, 50, 100, 149, 150)


def terms_for() -> list[str]:
    names = [
        official_text("totem_ui_1"),
        official_text("citybuilding_name_195"),
        official_text("property_totem_name"),
        official_text("totem_ui_2"),
        official_text("goods_name_1043"),
        official_text("goods_name_1042"),
        official_text("goods_name_1045"),
        official_text("citybuilding_name_122"),
        official_text("citybuilding_name_123"),
        official_text("citybuilding_name_124"),
    ]
    for aid in (3103, 3104, 13104, 3019, 4103, 4104, 14104, 4016, 5103, 5104, 15104, 5011):
        names.append(official_text(f"attribute_name_{aid}"))
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]



def attr_name_only(spec, terms: list[str]) -> str:
    if spec in (None, "", 0, -1, "0", "-1"):
        return ""
    aid = str(spec[0] if isinstance(spec, (list, tuple)) else str(spec).split("|", 1)[0])
    name = visible_official(official_text(f"attribute_name_{aid}"))
    return H(name, terms) if name else "遊戲中文名稱表沒有對應名稱"


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    terms = terms_for()
    name = visible_official(
        official_text("totem_ui_1")
        or official_text("citybuilding_name_195")
        or official_text("property_totem_name")
        or "先祖圖騰"
    )
    rule = visible_official(official_text("totem_ui_2"))
    dust = visible_official(official_text("goods_name_1043") or "魔法塵埃")
    essence = visible_official(official_text("goods_name_1042") or "血脈精粹")
    token = visible_official(official_text("goods_name_1045") or "領主印記")
    rows = data["kvk_totem.json"]

    title = f"Top Heroes Wiki｜{name}"
    lede = (
        f"本頁寫「{name}」的等級範圍與屬性斷點。"
        f"表共 {len(rows)} 列，不逐列傾印。"
        "說明裡的「賽季結束後將被回收」照錄原文，不把它對成官方第 N 季。"
    )
    summary = f"{name}圖鑑：三陣營等級範圍與斷點。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "rules", "label": "官方說明"},
        {"id": "breakpoints", "label": "等級與斷點"},
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
        f"界面、城建與屬性名稱都寫「{H(name, terms)}」，是不同鍵的同一顯示名。"
        f"建築升級（上限與消耗）見"
        f"<a href=\"city-buildings.html\">{H('城建升級', terms)}</a>頁的「{H(name, terms)}」節；本頁只寫陣營效果等級表。"
    ))
    add("    </section>")

    add('    <section id="rules">')
    add("      <h2>官方說明</h2>")
    if rule:
        add(quote_block(rule, terms))
        add(p_html("本頁不另解釋回收規則。"))
    add("    </section>")

    add('    <section id="breakpoints">')
    add("      <h2>等級與斷點</h2>")
    by_f = {}
    for fid, key, _ in FACTIONS:
        sub = sorted((r for r in rows if r.get("faction_id") == fid), key=lambda r: r["level"])
        by_f[fid] = sub
        statue = visible_official(official_text(key))
        add(p_html(
            f"「{H(statue, terms)}」軌道共 {len(sub)} 列，等級 {sub[0]['level']} 至 {sub[-1]['level']}。"
        ))
    # Shared consume / token
    f1 = by_f[1]
    same = all(
        all(
            a.get("consume") == b.get("consume")
            and a.get("token_recovery") == b.get("token_recovery")
            and a.get("fightforce") == b.get("fightforce")
            for a, b in zip(by_f[fid], f1)
        )
        for fid, _, _ in FACTIONS
    )
    add(p_html(
        ("三條軌道的消耗、回收道具與戰力欄相同，屬性名稱與數值按陣營而異。" if same else "三條軌道並非所有欄位都相同。")
        + f"戰力欄在全部 {len(rows)} 列都是 0，本頁不另行解讀。"
        f"消耗以「{H(dust, terms)}」為主，部分等級另消耗「{H(essence, terms)}」。"
        f"回收欄是「{H(token, terms)}」。"
        "技能欄只有編號，遊戲中文名稱表沒有對應的官方技能名，本頁不編造名稱；149 級起該欄的第二段數字改為 2。"
    ))

    # When attrs appear, from faction 1
    unlocks = []
    for field, label in (("attr_1", "第一項屬性"), ("attr_2", "第二項屬性"), ("attr_3", "第三項屬性"), ("attr_4", "第四項屬性")):
        first = next((r for r in f1 if r.get(field) not in (None, "", 0, -1, "-1")), None)
        if first:
            unlocks.append(f"{first['level']} 級起有{label}")
    add(p_html("屬性出現節點：" + "；".join(unlocks) + "。第四項屬性的官方名在三個陣營並不相同。"))

    # Per-faction attribute names (from a mid level that has all four)
    name_rows = []
    for fid, key, _ in FACTIONS:
        mid = next(r for r in by_f[fid] if r["level"] == 5)
        name_rows.append([
            H(visible_official(official_text(key)), terms),
            attr_name_only(mid.get("attr_1"), terms),
            attr_name_only(mid.get("attr_2"), terms),
            attr_name_only(mid.get("attr_3"), terms),
            attr_name_only(mid.get("attr_4"), terms),
        ])
    add(table(
        ["雕像", "第一項", "第二項", "第三項", "第四項"],
        name_rows,
        caption="三陣營圖騰屬性名稱",
        mobile="cards",
        card_title="雕像",
    ))

    # Sample levels: shared consume + per-faction fourth attr and first attr values
    sample_rows = []
    for lv in SAMPLE_LEVELS:
        r = next((x for x in f1 if x["level"] == lv), None)
        if not r:
            continue
        fourths = []
        for fid, key, _ in FACTIONS:
            rr = next(x for x in by_f[fid] if x["level"] == lv)
            if rr.get("attr_4") not in (None, "", 0, -1, "-1"):
                statue = visible_official(official_text(key))
                fourths.append(f"{H(statue, terms)}：{attr_pair_label(rr.get('attr_4'), terms)}")
        sample_rows.append([
            str(lv),
            attr_pair_label(r.get("attr_1"), terms) or "—",
            attr_pair_label(r.get("attr_2"), terms) or "—",
            attr_pair_label(r.get("attr_3"), terms) or "—",
            "<br>".join(fourths) if fourths else "—",
            cost_spec_label(r.get("consume"), terms) or "無消耗",
            cost_spec_label(r.get("token_recovery"), terms) or "—",
        ])
    add(p_html("以下只舉關鍵等級，用來對消耗與屬性起點，不是完整 150 級表。"))
    add(table(
        ["等級", "第一項", "第二項", "第三項", "第四項", "消耗", "回收"],
        sample_rows,
        caption="先祖圖騰等級節錄",
        mobile="cards",
        card_title="等級",
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    add(p_html(
        f"全部 {len(rows)} 列不在此逐筆展開。"
        "建築 40 級升級與圖騰效果表的對應關係，表上沒有寫明，本頁不推測。"
        "沒有官方名稱的技能編號，不編造稱呼。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for tname, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(tname)}</code> SHA-256 <code>{e(sha)}</code>，{len(data[tname])} 列。</li>")
    add(
        "<li>界面鍵 <code>totem_ui_1</code>、城建鍵 <code>citybuilding_name_195</code>、屬性鍵 <code>property_totem_name</code> "
        "顯示名同為「先祖圖騰」。</li>"
    )
    add(
        "<li>技能欄原值如 <code>40011|1</code>、<code>40021|1</code>、<code>40031|1</code>，"
        "149 級起第二段改為 2。字串表沒有對應技能名。</li>"
    )
    add(
        "<li>本頁不把「賽季結束後將被回收」對成官方第 N 季，也不把消耗方向寫成已核對的建築 40 級條件。</li>"
    )
    add("    </ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_ancestral_totem_page() -> str:
    return render_html()
