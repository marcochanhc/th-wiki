"""Public 陣營等級 catalog from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter

from .catalog_common import (
    H,
    attr_pair_label,
    cost_spec_label,
    footer_swap,
    load_table,
    notes_source_intro,
    official_text,
    p_html,
    unique_keep_order,
    visible_official,
)
from .htmlutil import e, table

TABLE_SHA256 = {
    "faction_level.json": "1ae8b43dbe024ad1964bbbbcff20d0f833e4d1fb4b71d6a28751b6ec925b2002",
    "influence_level.json": "1fb4eed1f01870b8147d400fcc07554934bdbbf8d97f972b9712a4b9df6924dc",
    "season_faction.json": "90b43e04a5b2e2b1cada5a0b8d4300031e4f54a5de9dad8b79eb2e006e282400",
    "season_faction_level.json": "91304ee09baae0fb4b156578a6028954f37df069aab85d6fc8e7d2e4f35a38d2",
}

PREFIXES = (
    (122, "citybuilding_name_122"),
    (123, "citybuilding_name_123"),
    (124, "citybuilding_name_124"),
)


def terms_for() -> list[str]:
    names = [
        official_text("property_camplv_name"),
        official_text("faction_lv_1"),
        official_text("property_camplv_dec"),
        official_text("influence_level_6"),
        official_text("influence_level_11"),
        official_text("influence_level_1"),
        official_text("citybuilding_name_122"),
        official_text("citybuilding_name_123"),
        official_text("citybuilding_name_124"),
        official_text("top_resource_name_3"),
        official_text("goods_name_220005"),
    ]
    for aid in (3003, 3004, 4003, 4004, 5003, 5004, 21041, 21043, 21039):
        names.append(official_text(f"attribute_name_{aid}"))
    for row_key in ("狼人", "吸血鬼"):
        names.append(row_key)
    return [n for n in unique_keep_order(visible_official(x) for x in names if x) if n and len(n) >= 2]


def _rows_for_prefix(rows: list[dict], prefix: int) -> list[dict]:
    return sorted((r for r in rows if str(r.get("id", "")).startswith(str(prefix))), key=lambda r: (r["level"], r.get("level_subordinate") or 0))


def _step_ranges(rows: list[dict]) -> list[tuple[int, int, int]]:
    steps = Counter(r["level"] for r in rows)
    compact = []
    start = prev_n = None
    last = None
    for lv in sorted(steps):
        n = steps[lv]
        if n != prev_n:
            if start is not None:
                compact.append((start, last, prev_n))
            start = lv
            prev_n = n
        last = lv
    if start is not None:
        compact.append((start, last, prev_n))
    return compact


def _first_with(rows: list[dict], field: str):
    for r in rows:
        if r.get(field) not in (None, "", 0, -1, "-1"):
            return r
    return None


def render_html() -> str:
    from .render import page_shell, toc_list

    data = {name: load_table(name, sha) for name, sha in TABLE_SHA256.items()}
    terms = terms_for()
    sys_name = visible_official(official_text("property_camplv_name") or official_text("faction_lv_1") or "陣營等級")
    desc = visible_official(official_text("property_camplv_dec"))
    hero_inf = visible_official(official_text("influence_level_6") or "陣營等級（英雄）")
    team_inf = visible_official(official_text("influence_level_11") or "陣營等級（編隊）")
    troop_inf = visible_official(official_text("influence_level_1") or "陣營士兵")
    statues = [visible_official(official_text(key)) for _, key in PREFIXES]

    rows = data["faction_level.json"]
    tracks = []
    for prefix, key in PREFIXES:
        sub = _rows_for_prefix(rows, prefix)
        tracks.append((prefix, visible_official(official_text(key)), sub))

    title = f"Top Heroes Wiki｜{sys_name}"
    lede = (
        f"本頁寫「{sys_name}」三條雕像軌道的等級範圍、小段結構與屬性對照。"
        f"共 {len(rows)} 列，不逐列傾印。"
    )
    summary = f"{sys_name}圖鑑：三陣營雕像對照與等級斷點。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "tracks", "label": "三陣營對照"},
        {"id": "breakpoints", "label": "等級斷點"},
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
        "名稱與說明以遊戲裡看得到的為準。表上的編號前綴對應雕像，不是官方第 N 季。"
        + f"官方系統名是「{H(sys_name, terms)}」。"
        + (f"說明是「{H(desc, terms)}」。" if desc else "")
        + f"三條升級軌道分別對應「{H(statues[0], terms)}」、「{H(statues[1], terms)}」、「{H(statues[2], terms)}」。"
        + f"界面影響條目另有「{H(hero_inf, terms)}」、「{H(team_inf, terms)}」、「{H(troop_inf, terms)}」，那些不是本頁這張升級表。"
    ))
    add("    </section>")

    add('    <section id="tracks">')
    add("      <h2>三陣營對照</h2>")
    # Same structure check
    base = tracks[0][2]
    same = all(
        len(sub) == len(base)
        and all(
            a["level"] == b["level"]
            and a.get("level_subordinate") == b.get("level_subordinate")
            and a.get("fightforce") == b.get("fightforce")
            and a.get("consume") == b.get("consume")
            for a, b in zip(sub, base)
        )
        for _, _, sub in tracks
    )
    add(p_html(
        f"三條軌道各 {len(base)} 列，主等級從 {base[0]['level']} 到 {base[-1]['level']}。"
        + ("消耗、戰力與小段結構三條相同，只有屬性不同。" if same else "三條軌道的結構不完全相同，下表分列。")
    ))
    cmp_rows = []
    for _, name, sub in tracks:
        first = sub[0]
        mid = _first_with(sub, "attr_3")
        cmp_rows.append([
            H(name, terms),
            attr_pair_label(first.get("attr_1"), terms),
            attr_pair_label(first.get("attr_2"), terms),
            (
                f"{mid['level']} 級起出現「{attr_pair_label(mid.get('attr_3'), terms)}」"
                if mid else "沒有第三項屬性"
            ),
        ])
    add(table(
        ["雕像", "起始第一項屬性", "起始第二項屬性", "第三項屬性"],
        cmp_rows,
        caption="三陣營雕像屬性對照",
        mobile="cards",
        card_title="雕像",
    ))
    add("    </section>")

    add('    <section id="breakpoints">')
    add("      <h2>等級斷點</h2>")
    ranges = _step_ranges(base)
    range_rows = []
    for start, end, n in ranges:
        label = str(start) if start == end else f"{start}–{end}"
        range_rows.append([label, str(n)])
    add(p_html("每一個主等級可能有多個小段。下表是小段數的連續區間，不是逐級清單。"))
    add(table(
        ["主等級", "每一級小段數"],
        range_rows,
        caption="陣營等級小段結構",
        mobile="cards",
        card_title="主等級",
    ))
    sample_levels = unique_keep_order([1, 10, 40, 80])
    sample_rows = []
    for lv in sample_levels:
        hits = [r for r in base if r["level"] == lv]
        if not hits:
            continue
        first, last = hits[0], hits[-1]
        sample_rows.append([
            str(lv),
            str(len(hits)),
            str(first.get("fightforce")),
            str(last.get("fightforce")),
            cost_spec_label(first.get("consume"), terms) or "無消耗",
        ])
    add(p_html("以下只舉幾個主等級的首段與末段，用來對消耗與戰力，不是完整升級表。"))
    add(table(
        ["主等級", "小段數", "首段戰力", "末段戰力", "該級首段消耗"],
        sample_rows,
        caption="陣營等級節錄",
        mobile="cards",
        card_title="主等級",
    ))
    add("    </section>")

    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    sf = data["season_faction.json"]
    sfl = data["season_faction_level.json"]
    sf_names = []
    for r in sf:
        raw = r.get("name")
        nm = visible_official(official_text(raw) if official_text(raw) else str(raw or ""))
        if nm:
            sf_names.append(nm)
    named = "、".join(f"「{H(n, terms)}」" for n in unique_keep_order(sf_names))
    add(p_html(
        f"另有賽季陣營表 {len(sf)} 列、賽季陣營等級表 {len(sfl)} 列，官方顯示名是{named}。"
        "那是另一套系統，不是本頁的聯盟、部族、自然陣營等級，也不把它寫成官方第 N 季。"
        f"升級表全部 {len(rows)} 列不在此逐筆展開。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{e(sha)}</code>，{len(data[name])} 列。</li>")
    add(
        "<li>三條軌道的列識別前綴與雕像 <code>citybuilding_name_122</code>、<code>123</code>、<code>124</code> 同一組數字，"
        "可見正文只寫雕像官方名，不把前綴寫成官方季數。</li>"
    )
    add(
        "<li>消耗寫成 <code>999|3|數量</code> 時，對應頂欄資源「肉」；"
        "<code>2|220005|數量</code> 對應「橙色英雄萬能碎片」。</li>"
    )
    add("    </ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_faction_levels_page() -> str:
    return render_html()
