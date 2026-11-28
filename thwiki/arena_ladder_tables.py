"""Public catalog of official 積分賽、挑戰賽、天梯賽 and 巔峰積分賽 systems from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter

from .catalog_common import (
    H,
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
    "function.json": "fb826efa087a122ad37682d1707bf877ce56970d92fbc44127ca390e72309afc",
    "challenge_arena_pve.json": "f7fb12924d7433e01f8cdf00714c49306429fda0b638e8a2d4076dfb6ae80b6b",
    "challenge_arena_pve_setting.json": "60e00955774f5088c02ec78c26bca9fdd6ce1abc9b1f0fc90dddf8b60bae8953",
    "arena_cross_reward.json": "14a36d78d088bc9ff62af8a24e48830fe3703acb791a7e2fcee5c273bab58c5f",
    "champion_duel.json": "d3ed965a7945eea1bff18250547de4b88c57399bb32db95e863c00ef848eda01",
    "legend_battle_common.json": "1d10ac36d21433f3c538e1da8c87cf033f69c43229665738419cf843d944a461",
    "legend_battlefield_reward.json": "f09c1fc41ea0c631401f6b62342322109685dcbb5a6cf459f3b68102ab9ab56b",
    "gvg_rank.json": "53072515ad974dc06c46a7db5f70ad409e8a4814324698e5b2019181e176f3d8",
    "gvg5_rank.json": "dde2811328d7741e5057cd06ea10a92f4d92e9607d4805803c2d22bd11379879",
    "gvg_cross_group.json": "66d42db47f51b3c9aeeb1e4b6269d51a0bcaf5d26eb79d26b1919376b58ff385",
    "fight_type.json": "9adbe344cfaa027227aa01f09d3a6b37b7a0695538b29e0e1372a35d4310e109",
    "reward_numerical_new.json": "bc6872975045c025c969ad6d52d542d5b9b72667437f42e3d777a6c5f1e834da",
}


def T(key: str, fallback: str = "") -> str:
    return visible_official(official_text(key) or fallback)


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def load_pinned(name: str):
    return load_table(name, TABLE_SHA256[name])


def terms_for() -> list[str]:
    names = [
        T("function_name_114", "積分賽"),
        T("function_name_113", "挑戰賽"),
        T("tvt_rank_function_name", "天梯賽"),
        T("s2_peak_name", "巔峰積分賽"),
        T("UI_Arena_014", "競技場"),
        T("champion_duel_title_3", "榮耀對決（Beta）"),
        "榮耀對決",
        T("champion_duel_info_title", "榮耀對決說明"),
        T("champion_duel_info_title_2_4", "巔峰賽"),
        T("champion_duel_desc_15", "海選賽"),
        T("champion_duel_info_title_2_3", "淘汰賽"),
        T("legend_battle_name_2001", "傳奇戰場"),
        T("gvg_desc050", "亂鬥競技場"),
        T("cross_arena_group1", "巔峰組"),
        T("cross_arena_group2", "黃金組"),
        T("cross_arena_group3", "白銀組"),
        T("cross_arena_group4", "青銅組"),
        T("cross_arena_group5", "進階組"),
        T("cross_arena_group6", "大眾組"),
        T("s2_peak_dan_qigntong", "青銅段位"),
        T("s2_peak_dan_baiyin", "白銀段位"),
        T("s2_peak_dan_huangjin", "黃金段位"),
        T("s2_peak_dan_zuasnhi", "鑽石段位"),
        T("s2_peak_dan_wangzhe", "王者段位"),
        T("s2_peak_Internal_rank", "服內排行榜"),
        T("s2_peak_server_rank", "跨服排行榜"),
        T("s2_peak_fast", "快速挑戰"),
        T("function_name_101", "冒險"),
        T("function_name_116", "懸賞"),
        T("activity_name591", "公會Boss"),
        T("function_name_206", "七日獎勵"),
        "王國遷移",
        "合服",
        T("Raid_BattaleField_01", "榮譽試煉"),
        T("Raid_BattaleField_20", "虛空寶庫"),
        "王國對決",
        T("elf_season_theme_5", "雲海紀行"),
        T("elf_season_theme_6", "地心探險"),
        T("k3_activity_20003104_name", "地心狩獵"),
        T("season_name_1", "世界樹之影"),
        T("season_name_2", "冰封之焰"),
        T("season_name_3", "暮光之戰"),
        T("season_name_4", "潮汐之怒"),
        "摸魚時光",
        "魚缸",
        "牧場物語",
        "抓蝴蝶",
        "鐵喙",
        "幸運火雞",
        T("g_5v5_rank1", "初級"),
        T("g_5v5_rank2", "中級"),
        T("g_5v5_rank3", "高級"),
        T("g_5v5_rank4", "精英"),
        T("g_5v5_rank5", "榮耀"),
        T("g_5v5_rank6", "大師"),
        T("g_5v5_rank7", "傳奇"),
        "王者",
        T("citybuilding_name_118", "競技場"),
    ]
    skip = {"使用", "提交", "確認", "取消", "查看", "參與", "全部", "詳情", "規則", "獎勵"}
    return [n for n in unique_keep_order(names) if n and len(n) >= 2 and n not in skip]


def link(href: str, label: str, terms: list[str]) -> str:
    return f'<a href="{e(href)}">{H(label, terms)}</a>'


def render_html() -> str:
    from .render import page_shell, toc_list

    functions = load_pinned("function.json")
    climbing = load_pinned("challenge_arena_pve.json")
    climbing_set = load_pinned("challenge_arena_pve_setting.json")
    cross_rewards = load_pinned("arena_cross_reward.json")
    duels = load_pinned("champion_duel.json")
    legend_common = load_pinned("legend_battle_common.json")
    legend_rewards = load_pinned("legend_battlefield_reward.json")
    gvg_ranks = load_pinned("gvg_rank.json")
    gvg5_ranks = load_pinned("gvg5_rank.json")
    gvg_groups = load_pinned("gvg_cross_group.json")
    fight_types = load_pinned("fight_type.json")
    numerical = load_pinned("reward_numerical_new.json")
    terms = terms_for()

    score = T("function_name_114", "積分賽")
    challenge = T("function_name_113", "挑戰賽")
    ladder = T("tvt_rank_function_name", "天梯賽")
    peak = T("s2_peak_name", "巔峰積分賽")
    arena = T("UI_Arena_014", "競技場")
    honor_duel = T("champion_duel_title_3", "榮耀對決（Beta）")
    honor_duel_short = "榮耀對決"
    honor_title = T("champion_duel_info_title", "榮耀對決說明")
    peak_stage = T("champion_duel_info_title_2_4", "巔峰賽")
    legend = T("legend_battle_name_2001", "傳奇戰場")
    brawl = T("gvg_desc050", "亂鬥競技場")
    adventure = T("function_name_101", "冒險")
    bounty = T("function_name_116", "懸賞")
    alliance_boss = T("activity_name591", "公會Boss")
    seven = T("function_name_206", "七日獎勵")
    move_name = "王國遷移"
    honor = T("Raid_BattaleField_01", "榮譽試煉")
    void = T("Raid_BattaleField_20", "虛空寶庫")
    cloud = T("elf_season_theme_5", "雲海紀行")
    under = T("elf_season_theme_6", "地心探險")
    hunt = T("k3_activity_20003104_name", "地心狩獵")

    groups = [
        T("cross_arena_group1", "巔峰組"),
        T("cross_arena_group2", "黃金組"),
        T("cross_arena_group3", "白銀組"),
        T("cross_arena_group4", "青銅組"),
        T("cross_arena_group5", "進階組"),
        T("cross_arena_group6", "大眾組"),
    ]
    dans = [
        T("s2_peak_dan_qigntong", "青銅段位"),
        T("s2_peak_dan_baiyin", "白銀段位"),
        T("s2_peak_dan_huangjin", "黃金段位"),
        T("s2_peak_dan_zuasnhi", "鑽石段位"),
        T("s2_peak_dan_wangzhe", "王者段位"),
    ]

    tower_types = Counter(r.get("tower_type") for r in climbing)
    show_floors = [r.get("show_floor") for r in climbing if r.get("show_floor") not in (None, -1, "-1")]
    reward_types = Counter(r.get("type") for r in cross_rewards)
    reward_ids = [r.get("reward_id") for r in cross_rewards if r.get("reward_id") not in (None, "", -1)]
    numerical_ids = {r.get("id") for r in numerical}
    resolved = sum(1 for i in set(reward_ids) if i in numerical_ids)
    unresolved = len(set(reward_ids)) - resolved

    castle_lv = sorted({r.get("castle_lv") for r in duels})
    sign_num = sorted({r.get("sign_least_num") for r in duels})
    q_seed = sorted({r.get("qualifier_seed_num") for r in duels})
    k_seed = sorted({r.get("knockout_seed_num") for r in duels})
    rank_groups = sorted({tuple(r.get("rank_group") or []) for r in duels})

    g5_names = unique_keep_order(T(r.get("rank_name") or "") for r in gvg5_ranks)
    last_g5 = gvg5_ranks[-1] if gvg5_ranks else {}
    last_official = T(last_g5.get("rank_name") or "")
    last_note = last_g5.get("note") or ""

    title_names = f"{score}、{challenge}、{ladder}、{peak}"
    page_title = f"Top Heroes Wiki｜{title_names}"
    lede = (
        f"本頁寫功能「{score}」、「{challenge}」、「{ladder}」、「{peak}」，"
        f"以及界面用字「{arena}」、說明標題「{honor_title}」、活動「{legend}」與「{brawl}」等已核對的官方名稱。"
        "遊戲中文名稱表沒有一個單獨功能名，用來把這些對戰入口叫成同一個系統；本頁用官方名稱分開寫。"
        f"「{honor}」、「{void}」見"
    )
    summary = f"{title_names}等已核對系統：官方名稱與規則原文。不是對戰攻略，也不排陣容。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "arena", "label": arena},
        {"id": "score", "label": score},
        {"id": "challenge", "label": challenge},
        {"id": "ladder", "label": ladder},
        {"id": "peak", "label": peak},
        {"id": "honor-duel", "label": honor_duel},
        {"id": "legend", "label": legend},
        {"id": "brawl", "label": brawl},
        {"id": "combat", "label": "對戰結算"},
        {"id": "kingdom-clash", "label": "王國對決"},
        {"id": "notes", "label": "資料說明"},
    ])

    pve_link = link("pve.html", f"{adventure}、{bounty}、{alliance_boss}", terms)
    move_link = link("seven-reward-move.html", f"{seven}、{move_name}", terms)
    clash_link = link("kingdom-clash.html", "王國對決", terms)

    parts: list[str] = []
    add = parts.append
    add('    <section id="lead">')
    add("      <h1>" + H(title_names, terms) + "</h1>")
    add(toc)
    add(p_html(H(lede, terms) + pve_link + H("。合服與「", terms) + H(move_name, terms) + H("」見", terms) + move_link + "。"))
    add(
        p_html(
            H(
                "下列都是表上或官方字串已具名的系統，用官方名稱分開寫。"
                "官方字串按遊戲裡的原文寫出，不改標點。"
                "表上數字只按原值寫出，不換算、不模擬。"
                "本頁不排列對戰陣容，也不寫尚未核對、不能保證等於遊戲客戶端的傷害公式。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="arena">')
    add(f"      <h2>{H(arena, terms)}</h2>")
    add(
        p_html(
            H(
                f"界面字串把「{arena}」用作總稱，同一組鍵裡有「{challenge}」與「{score}」。"
                "賽季紀念文案也有「競技場的對手」。"
                f"這仍不能把「{arena}」三個字單獨對成下面某一張表，本頁不把它釘死成單一入口。"
                f"另有一則官方字串「{T('UI_Arena_037')}」，字串本身沒有寫是哪一個分頁，本頁不擅自掛到「{score}」或「{ladder}」。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="score">')
    add(f"      <h2>{H(score, terms)}</h2>")
    add(p_html(H(f"功能名稱是「{score}」。官方說明原文如下，按遊戲裡的原文寫出，不改標點。", terms)))
    for i in range(1, 9):
        add(quote_block(official_text(f"arena_info_{i:03d}"), terms))
    add(
        p_html(
            H(
                "郵件標題有「"
                + T("mail_arena_1")
                + "」「"
                + T("mail_arena_2")
                + "」，以及「"
                + T("mail_season_arena_1")
                + "」「"
                + T("mail_season_arena_2")
                + "」。其中「周」與「週」按各則原文保留，不互相改寫。"
                f"本頁使用的表裡沒有單獨的「{score}」段位表。"
                f"「{ladder}」的說明寫「每個段位初始化排名將按上週積分賽的積分做初始化排名」，只說明兩者有銜接，"
                f"不把「{score}」本身寫成已具名的段位系統。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="challenge">')
    add(f"      <h2>{H(challenge, terms)}</h2>")
    add(
        p_html(
            H(
                f"同一「{arena}」界面有「{T('UI_Arena_009')}」「{T('UI_Arena_010')}」，以及「{T('UI_Arena_035')}」。",
                terms,
            )
        )
    )
    add(
        p_html(
            H(
                f"另有一張 {fmt_int(len(climbing))} 筆的爬塔表，分成 4 組（"
                + "／".join(fmt_int(tower_types.get(i, 0)) for i in range(1, 5))
                + f" 筆），可見層數寫到 {fmt_int(max(show_floors) if show_floors else 0)}。"
                f"另有 {fmt_int(len(climbing_set))} 筆設定，規則是編碼數字，本頁不自行翻譯。"
                f"這張爬塔表與功能「{challenge}」是否同一入口尚未核對，本頁不把它們寫成已核對的同一系統，也不擅自寫成只打人或只打怪。"
                "關卡規模亦見",
                terms,
            )
            + pve_link
            + "。"
        )
    )
    add("    </section>")

    add('    <section id="ladder">')
    add(f"      <h2>{H(ladder, terms)}</h2>")
    add(
        p_html(
            H(
                f"功能名稱是「{ladder}」。跨服競技場字串把本期結算稱為「{ladder}」。"
                "分組名稱是"
                + "、".join(f"「{g}」" for g in groups)
                + "。"
                "官方玩法說明在「段位由高至低」只列前五組，沒有寫「"
                + groups[-1]
                + "」；本頁並列兩處原文，不自行改說明。",
                terms,
            )
        )
    )
    add(quote_block(official_text("cross_arena_end_tip"), terms))
    add(quote_block(official_text("cross_arena_tip_info"), terms))
    add(quote_block(official_text("cross_arena_challenge_list_desc"), terms))
    add(
        p_html(
            H(
                f"獎勵表共 {fmt_int(len(cross_rewards))} 筆，類型數字 1 至 5 的筆數是 "
                + "／".join(fmt_int(reward_types.get(i, 0)) for i in range(1, 6))
                + "。"
                f"獎勵編號共 {fmt_int(len(set(reward_ids)))} 個不同值；"
                f"其中 {fmt_int(resolved)} 個可在本頁使用的數值獎勵表對上列，"
                f"{fmt_int(unresolved)} 個對不上。"
                "本頁不把能對上的少數幾筆寫成完整獎勵單，也不排哪些獎勵比較值得拿。"
                f"郵件標題有「{T('mail_title_3v3_personal')}」「{T('mail_title_3v3_alliance')}」「{T('mail_title_3v3_compensation')}」。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="peak">')
    add(f"      <h2>{H(peak, terms)}</h2>")
    add(
        p_html(
            H(
                f"功能名稱是「{peak}」。字串有五個段位名："
                + "、".join(f"「{d}」" for d in dans)
                + "。"
                "本頁使用的表裡沒有對到記載積分門檻或升降條件的段位表，門檻不寫。"
                "界面另有「"
                + T("s2_peak_team1")
                + "」「"
                + T("s2_peak_team2")
                + "」「"
                + T("s2_peak_team3")
                + "」，以及「"
                + T("s2_peak_Internal_rank")
                + "」「"
                + T("s2_peak_server_rank")
                + "」「"
                + T("s2_peak_count").split("：")[0]
                + "」「"
                + T("s2_peak_fast")
                + "」。結算郵件原文如下。",
                terms,
            )
        )
    )
    add(quote_block(official_text("mail_rank_txt"), terms))
    add(
        p_html(
            H(
                f"「{peak_stage}」是「{honor_duel_short}」裡的一個階段名，與功能「{peak}」不是同一名稱，本頁分開寫。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="honor-duel">')
    add(f"      <h2>{H(honor_duel, terms)}</h2>")
    add(
        p_html(
            H(
                f"界面標題是「{honor_duel}」，說明標題是「{honor_title}」。"
                "遊戲中文名稱表沒有「冠軍決鬥」這一功能名，本頁只用上述官方標題。"
                f"說明正文稱「{honor_duel_short}」。官方說明有兩套週次安排原文，本頁並列，不自行選一套當唯一賽程。"
                f"表上另有 {fmt_int(len(duels))} 筆列，城堡等級數字都是 "
                + "、".join(str(x) for x in castle_lv)
                + "，報名最少人數都是 "
                + "、".join(str(x) for x in sign_num)
                + "，預選種子數都是 "
                + "、".join(str(x) for x in q_seed)
                + "，淘汰種子數都是 "
                + "、".join(str(x) for x in k_seed)
                + f"。這 {fmt_int(len(duels))} 筆分成 {fmt_int(len(rank_groups))} 組排行編號，本頁不把未對到說明的時程數字寫成已核對的開賽時刻。",
                terms,
            )
        )
    )
    add(p_html(H("官方說明原文如下。", terms)))
    for key in (
        "champion_duel_info_title_1_1",
        "champion_duel_info_desc_1_1",
        "champion_duel_info_title_1_2",
        "champion_duel_info_desc_1_2",
        "champion_duel_info_desc_1_2_alter",
        "champion_duel_info_title_1_3",
        "champion_duel_info_desc_1_3",
        "champion_duel_info_title_2_1",
        "champion_duel_info_desc_2_1",
        "champion_duel_info_desc_2_1_alter",
        "champion_duel_info_title_2_2",
        "champion_duel_info_desc_2_2",
        "champion_duel_info_title_2_3",
        "champion_duel_info_desc_2_3",
        "champion_duel_info_title_2_4",
        "champion_duel_info_desc_2_4",
        "champion_duel_info_title_2_5",
        "champion_duel_info_desc_2_5",
        "champion_duel_info_title_3_1",
        "champion_duel_info_desc_3_1",
    ):
        text = official_text(key)
        visible = visible_official(text)
        if not visible:
            continue
        if key.startswith("champion_duel_info_title_") and "desc" not in key:
            add(f"<h3>{H(visible, terms)}</h3>")
        else:
            add(quote_block(text, terms))
    add("    </section>")

    add('    <section id="legend">')
    add(f"      <h2>{H(legend, terms)}</h2>")
    add(p_html(H(f"界面名稱是「{legend}」。官方說明原文如下。", terms)))
    add(quote_block(official_text("legend_battle_name_91"), terms))
    add(quote_block(official_text("legend_battle_name_2031"), terms))
    add(
        p_html(
            H(
                f"共用規則表有 {fmt_int(len(legend_common))} 筆，階段與名次獎勵表有 {fmt_int(len(legend_rewards))} 筆。"
                "時程欄是編碼數字，本頁不把它們寫成已核對的開賽時刻，也不展開獎勵編號當完整道具單。"
                "這兩張表不寫進王國對決頁。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="brawl">')
    add(f"      <h2>{H(brawl, terms)}</h2>")
    add(p_html(H(f"官方名稱是「{brawl}」。說明原文如下。", terms)))
    add(quote_block(official_text("gvg_desc053"), terms))
    add(quote_block(official_text("gvg_buid_desc007"), terms))
    add(quote_block(official_text("gvg_info_005"), terms))
    add(
        p_html(
            H(
                f"段位表有 {fmt_int(len(gvg_ranks))} 筆，名稱欄就是 "
                + "、".join(H(str(r.get("name") or ""), terms) for r in gvg_ranks)
                + "，對應下限數字是 "
                + "、".join(fmt_int(r.get("score_min")) for r in gvg_ranks)
                + f"。另有一張 {fmt_int(len(gvg5_ranks))} 筆的段位表，官方段位短名是 "
                + "、".join(f"「{n}」" for n in g5_names)
                + "，下限數字從 "
                + fmt_int(gvg5_ranks[0].get("score_min") if gvg5_ranks else 0)
                + " 起，至第 "
                + fmt_int(len(gvg5_ranks))
                + " 筆 "
                + fmt_int(gvg5_ranks[-1].get("score_min") if gvg5_ranks else 0)
                + f"。第 {fmt_int(len(gvg5_ranks))} 筆的備註寫「{e(str(last_note))}」，官方短名卻是「"
                + last_official
                + "」，兩欄並列，不合併成一個已核對的顯示名。"
                f"跨服分組表有 {fmt_int(len(gvg_groups))} 筆，本頁只記筆數。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="combat">')
    add("      <h2>對戰結算</h2>")
    add(
        p_html(
            H(
                f"戰鬥類型表有 {fmt_int(len(fight_types))} 筆，記錄戰鬥類型與戰損比例等，不是一份可保證等於遊戲客戶端的傷害公式。"
                "增傷、減傷、暴擊、防禦、突破防禦如何相乘或相加，真實傷害與護盾如何結算，出手順序與鎖定目標的完整規則，都不在本頁使用的表裡寫成閉式。"
                "本頁不編造組合公式，也不排對戰陣容。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="kingdom-clash">')
    add("      <h2>" + H("王國對決", terms) + "</h2>")
    add(
        p_html(
            H(
                "王國對決、王國紛爭與相關賽季地圖、匹配與獎勵結構見",
                terms,
            )
            + clash_link
            + H(
                f"，本頁不重複抄錄，也不把上述對戰表整批寫進那一頁。"
                f"「{cloud}」「{under}」出現在其他官方字串；「{hunt}」是另一則已核對的官方活動名，與「{under}」不是同一名稱。"
                "本頁不把這些名稱寫成已核對的官方第五季或第六季標題。"
                "遊戲中文名稱表的賽季名稱只有四則：「"
                + T("season_name_1")
                + "」「"
                + T("season_name_2")
                + "」「"
                + T("season_name_3")
                + "」「"
                + T("season_name_4")
                + "」，沒有第五、第六則賽季名稱。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    add(
        "<li>手冊第 8 章是章節提綱。數值、名稱與條件以 2026-11-22 LocalLow 表與字串表為準；"
        "現行 <code>/workspace/topheroes/data/</code> 與該批解壓檔在本頁用到的表上全文相同。"
        "可見正文不把「競技玩法」或「PVP」寫成官方功能總稱。"
        "字串表沒有「冠軍決鬥」這一功能名，可見正文改用界面標題「榮耀對決（Beta）」與說明標題「榮耀對決說明」。"
        "「巔峰賽」與功能「巔峰積分賽」不是同一名稱，可見正文已分開寫。</li>"
    )
    add(
        "<li>可見正文不寫原始欄位名。功能編號是積分賽 114、挑戰賽 113、天梯賽 46、巔峰積分賽 71。"
        "爬塔表 <code>challenge_arena_pve</code> 與功能「挑戰賽」是否同一入口尚未核對。"
        "天梯獎勵編號是 33001–33059，多數不在 <code>reward_numerical_new</code>。"
        "榮耀對決表 id 為 1–4 與 101–104 兩組，<code>rank_group</code> 不同。"
        "傳奇戰場共用規則 6 筆的 <code>legend_season</code> 皆為 1，不把它寫成官方第幾季。"
        "亂鬥 5v5 段位表第 26 筆 <code>note</code> 為「王者」、<code>rank_name</code> 為「傳奇」。"
        "<code>arenasettings.json</code> 108 筆皆為 <code>id=0</code>、<code>value=1</code>，本頁不採用。"
        "王國對決既有頁的「雲海紀行」說明未改。</li>"
    )
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(page_title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_arena_ladder_page() -> str:
    return render_html()
