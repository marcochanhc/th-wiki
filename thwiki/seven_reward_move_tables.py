"""Public catalog of official 七日獎勵, 合服 and 王國遷移 systems from the 2026-11-22 LocalLow extract."""

from __future__ import annotations

from collections import Counter, defaultdict

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
from .overrides import PAGE_IDS

TABLE_SHA256 = {
    "hero_detail.json": "281686181df002ab27a568bead407fc1b9741fbf2ebc2aaa97dfa213e037354f",
    "hero_honor_bonus.json": "6ad5aebdee0b282d4de8b13f75fcc2c4bac50898f430bce07f0a8b499c0c4e82",
    "hero_recommend.json": "3c66d9172119b186713b6f4e8730af5f37f5710a822822379d062b7932a3d2e9",
    "reward_hero_new.json": "87faca0babb82bb17e131f5e58f1cf988765afa51c1537bed22058c984abab10",
    "function.json": "fb826efa087a122ad37682d1707bf877ce56970d92fbc44127ca390e72309afc",
    "activity.json": "6e0fd9ff6bd81e71bfee29a3794d10b2ba8eff0601f288f56d8881547536602d",
    "new_seven_login.json": "f421225fa68fee2ea8066a61daf4f3246eed55e1ffb4838b226a792538162d64",
    "gift_login.json": "85759c07db2ddb2b96bd53b2ba3a5f8595f6bd32a347afe842029a4ae3dac735",
    "reward_numerical_new.json": "bc6872975045c025c969ad6d52d542d5b9b72667437f42e3d777a6c5f1e834da",
    "guide2.json": "f846b08678f606ebc6f9e4381160726fa1f30045bfc13742ceed549f9e404a09",
    "task.json": "94ecf433786567ac1fd4b39c94d999194a787df469e4c5b324df5f19e6ca9322",
    "task_chapter_group.json": "b1fd54e9915b54c5e3c5410b24bb87b05bb77c88770ed3c5cd1613c255a95cd5",
    "map_stage.json": "d81c0dc629b5276ddfc5a90733430f0d30d093f2a030cb207f76cd732b4bd538",
    "map_birthpoint.json": "118e6a5ed884db973df343f66a35c0e002ca96827c85de8bb39cedf74cf09006",
    "season_memory.json": "860f6c2f742a88d073588dbae7fa04555103bb490baa720c0d2fab8f7d2976ae",
    "season_introduce.json": "d7ffb0f25ad9ae910a1ae72a8e71cacfe7a25d4158ded852b9c1b7217e145355",
    "season_activity_preview.json": "5cb4fa4c785a5ba29a6fc5e09bdc3544c18aa27735d87ef53011d16a7222a008",
    "season_prepare.json": "eb3a235b6851b5477c71bd0f007674ba137458ed08ab8d4c2e0c9acac5862dfd",
    "server_merge.json": "2adda42ce35c068a49b96f9b9785a4d2012758fffb11687be779123dafeb09c2",
    "server_move.json": "22e1ede5972b9d4e964595db7b128c8f8c6dcb6a19e5d875fdf31b783ecd004e",
    "server_move_cost.json": "2b17f7523a3291163f875bd3b40a23919bb2a869e0c3a946879d3f1af75bb87a",
    "server_task.json": "ce85fe05cd79419da2c5f0f3cb3c7268869bf3d646b0a945a07f83a1fcb1082c",
    "stronger.json": "a63e12676006ea7b42862f10090637787d3acff2d7c6e725691f13fc275a636b",
    "attribute.json": "72eca60115f5dba4d018c11ea7160b0772470091c064622c9a14667477e90ac9",
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
        T("function_name_206", "七日獎勵"),
        T("seven_reward_new_tips5", "開服慶典"),
        T("sevenday_celebrate_tips1", "七日慶典"),
        T("sevenday_celebrate_tips17", "傳唱的篇章"),
        T("rejoin_login_title", "七日豪禮"),
        T("new_seven_day_01", "天數"),
        T("new_seven_day_02", "免費"),
        T("new_seven_day_03", "貴族2"),
        T("activity_name_1054", "新人挑戰"),
        T("goods_name_283", "轉服卷軸"),
        T("s_move_info_tile_01", "王國遷移說明"),
        "王國遷移",
        "遷移流程",
        "遷移條件",
        "遷移卷軸",
        "遷服卷軸",
        "組隊遷移",
        "合服",
        "王國合併",
        T("mail_title_4044", "新手遷服成功"),
        T("mail_title_4045", "轉服成功"),
        T("hero_recommend_tips_1", "推薦陣容"),
        T("hero_recommend_1", "最佳聯盟"),
        T("hero_recommend_2", "最佳自然"),
        T("hero_recommend_3", "最佳部落"),
        T("hero_recommend_4", "老手推薦"),
        T("hero_recommend_5", "新手推薦"),
        T("hero_recommend_6", "最強陣容"),
        T("hero_recommend_8", "最佳部族"),
        T("hero_recommend_dec_3", "最好的部落陣容，有著快速又猛烈的攻擊"),
        T("attribute_name_1052", "所有部隊負重增加"),
        T("hero_name_10001", "戰士"),
        T("hero_name_10002", "弓箭手"),
        T("hero_name_10006", "老法師"),
        T("hero_name_10007", "藥劑師"),
        T("hero_name_10009", "鐵匠"),
        T("hero_name_10010", "護衛"),
        T("function_name_101", "冒險"),
        T("function_name_106", "世界"),
        T("function_name_116", "懸賞"),
        T("activity_name591", "公會Boss"),
        T("citybuilding_name_144", "懸賞大廳"),
        T("map_birthpoint_name", "信標"),
        T("season_name_1", "世界樹之影"),
        T("season_name_2", "冰封之焰"),
        T("season_name_3", "暮光之戰"),
        T("season_name_4", "潮汐之怒"),
        T("season_memo_s0_title", "王國之歌"),
        T("elf_season_theme_5", "雲海紀行"),
        T("elf_season_theme_6", "地心探險"),
        T("k3_activity_20003104_name", "地心狩獵"),
        T("serverTask_001", "冒險開始"),
        T("serverTask_002", "城市建設者"),
        T("serverTask_003", "探索世界"),
        T("serverTask_004", "狩獵魔物"),
        T("serverTask_005", "傳說之路"),
        T("serverTask_006", "寶藏獵人"),
        T("serverTask_007", "新的秩序"),
        T("function_name_202", "首儲"),
        T("UI_Combat_013", "英雄升級"),
        T("UI_Combat_012", "酒館招募"),
        T("battle_report_continuous_13", "我要變強"),
        "聯盟",
        "自然",
        "部族",
        "部落",
        "摸魚時光",
        "魚缸",
        "牧場物語",
        "抓蝴蝶",
        "鐵喙",
        "幸運火雞",
        "懸賞",
    ]
    skip = {"使用", "提交", "確認", "取消", "查看", "參與", "全部", "詳情"}
    return [n for n in unique_keep_order(names) if n and len(n) >= 2 and n not in skip]


def link(href: str, label: str, terms: list[str]) -> str:
    return f'<a href="{e(href)}">{H(label, terms)}</a>'


def hero_link(hid, terms: list[str]) -> str:
    name = T(f"hero_name_{hid}") or str(hid)
    if hid in PAGE_IDS:
        return link(f"heroes/{hid}.html", name, terms)
    return H(name, terms)


def interval_text(value) -> str:
    if value in (None, "", -1, "-1"):
        return ""
    return str(value).replace("|", "｜")


def gift_slot_text(reward_row: dict, slot: int, terms: list[str]) -> str:
    typ = reward_row.get(f"type_{slot}")
    ids = reward_row.get(f"reward_{slot}")
    nums = reward_row.get(f"num_{slot}")
    if typ in (None, "", -1, "-1") or not ids:
        return ""
    rid = ids[0] if isinstance(ids, list) else ids
    num = nums[0] if isinstance(nums, list) else nums
    goods = visible_official(official_text(f"goods_name_{rid}"))
    hero = visible_official(official_text(f"hero_name_{rid}"))
    qty = fmt_int(num) if num not in (None, "", -1) else ""
    if typ == 2 and goods:
        bit = H(goods, terms)
        return f"{bit} {qty}".strip()
    if goods and hero and goods != hero:
        return (
            f"編號 {rid}：官方短名「{H(goods, terms)}」，英雄名是「{H(hero, terms)}」"
            f"{('，數量 ' + qty) if qty else ''}；這一列的類型數字含義未核對，本頁不把它寫成整隻英雄或碎片"
        )
    if goods:
        return (
            f"官方短名「{H(goods, terms)}」{('，數量 ' + qty) if qty else ''}"
            "；類型數字含義未核對"
        )
    if hero:
        return (
            f"英雄名「{H(hero, terms)}」{('，數量 ' + qty) if qty else ''}"
            "；類型數字含義未核對，遊戲中文名稱表沒有對應的道具短名"
        )
    return "遊戲中文名稱表沒有對應名稱" + (f"，數量 {qty}" if qty else "")


def render_html() -> str:
    from .render import page_shell, toc_list

    heroes = load_pinned("hero_detail.json")
    honor_rows = load_pinned("hero_honor_bonus.json")
    recommends = load_pinned("hero_recommend.json")
    reward_hero_new = load_pinned("reward_hero_new.json")
    functions = load_pinned("function.json")
    activities = load_pinned("activity.json")
    seven_login = load_pinned("new_seven_login.json")
    gift_login = load_pinned("gift_login.json")
    numerical = load_pinned("reward_numerical_new.json")
    guide2 = load_pinned("guide2.json")
    tasks = load_pinned("task.json")
    chapters = load_pinned("task_chapter_group.json")
    stages = load_pinned("map_stage.json")
    birthpoints = load_pinned("map_birthpoint.json")
    memories = load_pinned("season_memory.json")
    introduces = load_pinned("season_introduce.json")
    previews = load_pinned("season_activity_preview.json")
    prepares = load_pinned("season_prepare.json")
    merges = load_pinned("server_merge.json")
    moves = load_pinned("server_move.json")
    move_costs = load_pinned("server_move_cost.json")
    server_tasks = load_pinned("server_task.json")
    stronger = load_pinned("stronger.json")
    attributes = load_pinned("attribute.json")
    terms = terms_for()

    seven = T("function_name_206", "七日獎勵")
    open_fest = T("seven_reward_new_tips5", "開服慶典")
    seven_fest = T("sevenday_celebrate_tips1", "七日慶典")
    chaptersong = T("sevenday_celebrate_tips17", "傳唱的篇章")
    return_gift = T("rejoin_login_title", "七日豪禮")
    newbie_challenge = T("activity_name_1054", "新人挑戰")
    move_name = "王國遷移"
    move_title = T("s_move_info_tile_01", "王國遷移說明")
    scroll = T("goods_name_283", "轉服卷軸")
    scroll_desc = T("goods_desc_283")
    rec_title = T("hero_recommend_tips_1", "推薦陣容")
    best_tribe = T("hero_recommend_8", "最佳部族")
    tribe_short = T("hero_recommend_dec_3")
    attr_name = T("attribute_name_1052", "所有部隊負重增加")
    warrior = T("hero_name_10001", "戰士")
    archer = T("hero_name_10002", "弓箭手")
    old_mage = T("hero_name_10006", "老法師")
    alchemist = T("hero_name_10007", "藥劑師")
    smith = T("hero_name_10009", "鐵匠")
    guard = T("hero_name_10010", "護衛")
    adventure = T("function_name_101", "冒險")
    world = T("function_name_106", "世界")
    bounty = T("function_name_116", "懸賞")
    alliance_boss = T("activity_name591", "公會Boss")
    hall = T("citybuilding_name_144", "懸賞大廳")
    beacon = T("map_birthpoint_name", "信標")
    s1 = T("season_name_1", "世界樹之影")
    s2 = T("season_name_2", "冰封之焰")
    s3 = T("season_name_3", "暮光之戰")
    s4 = T("season_name_4", "潮汐之怒")
    song = T("season_memo_s0_title", "王國之歌")
    cloud = T("elf_season_theme_5", "雲海紀行")
    under = T("elf_season_theme_6", "地心探險")
    hunt = T("k3_activity_20003104_name", "地心狩獵")
    first_store = T("function_name_202", "首儲")
    hero_up = T("UI_Combat_013", "英雄升級")
    tavern = T("UI_Combat_012", "酒館招募")
    grow = T("battle_report_continuous_13", "我要變強")
    mail_ok = T("mail_title_4045", "轉服成功")
    mail_new = T("mail_title_4044", "新手遷服成功")

    starter_ids = (10001, 10002, 10006, 10007, 10009, 10010)
    hero_by_id = {int(r["id"]): r for r in heroes}
    honor_301 = [r for r in honor_rows if r.get("honor_group") == 301]
    honor_301 = sorted(honor_301, key=lambda r: r.get("id") or 0)
    rhn_by_hero = {int(r["hero"]): r for r in reward_hero_new if r.get("hero") in starter_ids}
    numerical_by_id = {r.get("id"): r for r in numerical}
    activity_by_id = {r.get("id"): r for r in activities}

    act_seven = activity_by_id.get(301) or {}
    act_fest = activity_by_id.get(217) or {}
    act_open = activity_by_id.get(303) or {}
    act_new = activity_by_id.get(1054) or {}
    act_return = next(
        (r for r in activities if r.get("name") == "rejoin_login_title"),
        {},
    )

    groups = defaultdict(list)
    for row in seven_login:
        groups[row.get("group")].append(row)
    group_sizes = {g: len(rows) for g, rows in groups.items()}

    attr_1052 = next((r for r in attributes if r.get("id") == 1052), {}) or {}
    show_type = attr_1052.get("show_type")

    fn_world = next((r for r in functions if r.get("id") == 106), {}) or {}
    world_tip = T(fn_world.get("tips") or "function_tips_106")

    chapter_titles = []
    for row in chapters:
        title = T(row.get("charter_name") or "")
        if title:
            chapter_titles.append(title)

    task_ids = [r.get("id") for r in tasks]
    unique_start = sum(1 for i in task_ids if i == 1)

    task2 = next((r for r in tasks if r.get("id") == 2), {}) or {}
    task4 = next((r for r in tasks if r.get("id") == 4), {}) or {}
    help_archer = T(task2.get("dec") or "task_dec_gongjianshou")
    rescue_alchemist = T(task4.get("dec") or "task_dec_shangren")

    preview_groups = Counter(r.get("group") for r in previews)
    intro_by_season = Counter(r.get("season") for r in introduces)
    season5_intro = [r for r in introduces if r.get("season") == 5]
    season5_titles = unique_keep_order(
        T(r.get("title") or "") for r in season5_intro if T(r.get("title") or "")
    )

    merge_times = Counter(r.get("time") for r in merges)
    reversed_times = []
    for row in merges:
        raw = row.get("time") or ""
        if "|" in raw:
            start, end = raw.split("|", 1)
            if start > end:
                reversed_times.append(raw)
    reversed_counter = Counter(reversed_times)
    merge_ids = {r.get("server_id") for r in merges}
    move_ids = {r.get("server_id") for r in moves}
    move_times = Counter(r.get("time") for r in moves)
    move_groups = Counter(r.get("cost_group") for r in moves)
    team_open = {r.get("team_is_open") for r in moves}

    cost_by_group = defaultdict(list)
    for row in move_costs:
        cost_by_group[row.get("cost_group")].append(row)
    for g in cost_by_group:
        cost_by_group[g] = sorted(
            cost_by_group[g],
            key=lambda r: (r.get("item_cost") is None, r.get("item_cost"), r.get("power_max") or 0),
        )

    title_names = f"{seven}、{move_name}"
    page_title = f"Top Heroes Wiki｜{title_names}"
    lede = (
        f"本頁寫功能「{seven}」、活動「{open_fest}」與「{seven_fest}」、"
        f"官方說明「{move_title}」，以及合服／「王國合併」、郵件標題「{mail_new}」等已核對的官方名稱。"
        "遊戲中文名稱表沒有一個單獨功能名，用來把這些系統叫成同一個入口；本頁用官方名稱分開寫。"
        "本頁不排列培養優先順序，也不把界面上看到的伺服器編號，對成表內編號。"
    )
    summary = f"{title_names}等已核對系統：官方名稱、表上規則與原文。不是培養或轉服攻略。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "starters", "label": f"{warrior}、{old_mage}、{archer}、{smith}、{guard}、{alchemist}"},
        {"id": "recommend", "label": rec_title},
        {"id": "seven-reward", "label": seven},
        {"id": "festivals", "label": f"{open_fest}、{seven_fest}"},
        {"id": "tasks", "label": "主要任務與功能開放"},
        {"id": "seasons", "label": f"{s1}、{s2}、{s3}、{s4}"},
        {"id": "merge", "label": "合服、王國合併"},
        {"id": "move", "label": move_name},
        {"id": "newbie-move", "label": mail_new},
        {"id": "server-tasks", "label": f"{T('serverTask_001')}、{T('serverTask_002')}、{T('serverTask_003')}"},
        {"id": "stronger", "label": grow},
        {"id": "notes", "label": "資料說明"},
    ])

    parts: list[str] = []
    add = parts.append
    add('    <section id="lead">')
    add("      <h1>" + H(title_names, terms) + "</h1>")
    add(toc)
    add(p_html(H(lede, terms)))
    add(
        p_html(
            H(
                "下列都是表上或官方字串已具名的系統，用官方名稱分開寫。"
                "官方字串按遊戲裡的原文寫出，不改標點。"
                "表上數字只按原值寫出，不換算、不模擬。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="starters">')
    add(
        f"      <h2>{H(warrior, terms)}、{H(old_mage, terms)}、{H(archer, terms)}、"
        f"{H(smith, terms)}、{H(guard, terms)}、{H(alchemist, terms)}</h2>"
    )
    starter_links = "、".join(hero_link(i, terms) for i in starter_ids)
    add(
        p_html(
            f"同一榮譽加成組有六名英雄：{starter_links}。"
            + H(
                f"加成屬性的官方名稱是「{attr_name}」。"
                f"{warrior}、{old_mage}的技能文案有「聯盟」用詞，{archer}有「自然」用詞，"
                f"{smith}、{guard}有「部族」用詞。"
                f"{alchemist}的技能文案沒有陣營用詞，榮譽加成也不能用來判定陣營；"
                f"本站自然英雄名單已收入{alchemist}。"
                "本頁不排列培養優先順序。",
                terms,
            )
        )
    )
    missing_unlock = sum(
        1
        for i in starter_ids
        if hero_by_id.get(i, {}).get("unlock_condition") in (None, "", [], -1)
    )
    has_unlock = sum(
        1
        for i in starter_ids
        if hero_by_id.get(i, {}).get("unlock_condition") not in (None, "", [], -1)
    )
    star_set = sorted({hero_by_id.get(i, {}).get("star_max") for i in starter_ids})
    frag_set = sorted({hero_by_id.get(i, {}).get("fragment_num") for i in starter_ids})
    add(
        p_html(
            H(
                f"這六名在英雄表上的星數上限都是 {star_set[0] if len(star_set)==1 else '、'.join(str(x) for x in star_set)}，"
                f"碎片數都是 {frag_set[0] if len(frag_set)==1 else '、'.join(str(x) for x in frag_set)}。"
                f"{warrior}這一列沒有解鎖條件數字；其餘 {has_unlock} 名寫有一組數字，"
                "這組數字在表上的含義尚未核對，本頁不把它寫成某個城堡等級。",
                terms,
            )
        )
    )
    rhn_star = {rhn_by_hero[i].get("hero_star") for i in starter_ids if i in rhn_by_hero}
    rhn_lv = {rhn_by_hero[i].get("hero_level") for i in starter_ids if i in rhn_by_hero}
    rhn_br = {rhn_by_hero[i].get("hero_break") for i in starter_ids if i in rhn_by_hero}
    rhn_fr = {rhn_by_hero[i].get("fragment_num") for i in starter_ids if i in rhn_by_hero}
    if len(rhn_by_hero) == 6 and len(rhn_star) == len(rhn_lv) == len(rhn_br) == len(rhn_fr) == 1:
        add(
            p_html(
                H(
                    "另有一張給英雄初始數值的表，這六名的星數、等級、突破與碎片數都是 "
                    f"{list(rhn_star)[0]}、{list(rhn_lv)[0]}、{list(rhn_br)[0]}、{list(rhn_fr)[0]}。"
                    "本頁只按表上數字寫出，不另作說明。",
                    terms,
                )
            )
        )
    honor_rows_html = []
    for row in honor_301:
        pair = row.get("bonus_attribute") or []
        val = pair[1] if isinstance(pair, list) and len(pair) > 1 else ""
        honor_rows_html.append(
            [fmt_int(row.get("bonus_lv")), fmt_int(val), fmt_int(row.get("combat"))]
        )
    add(
        p_html(
            H(
                f"同一榮譽加成共 {len(honor_301)} 檔。屬性在表上的顯示類型數字是 {show_type}，"
                "本頁按原值寫出，不把數值換成百分比。",
                terms,
            )
        )
    )
    if honor_rows_html:
        add(
            table(
                ["檔次數字", f"{attr_name}（原值）", "戰力（原值）"],
                honor_rows_html,
            )
        )
    add("    </section>")

    add('    <section id="recommend">')
    add(f"      <h2>{H(rec_title, terms)}</h2>")
    add(
        p_html(
            H(
                f"官方推薦表共 {len(recommends)} 筆。標題與簡述按遊戲裡的原文寫出。"
                f"例如標題「{best_tribe}」的簡述是「{tribe_short}」，其中「部落」按原文保留，不改成「部族」。"
                "表上的站位編號按原值列出，不改寫成前排或後排。"
                "表上的區間原文照抄，不把它們寫成界面上的伺服器編號。"
                "本頁不排列哪一套比較值得培養。",
                terms,
            )
        )
    )
    used_title_keys = [r.get("key_id") for r in recommends]
    unused_titles = []
    for key, fallback in (
        ("hero_recommend_3", "最佳部落"),
        ("hero_recommend_4", "老手推薦"),
        ("hero_recommend_6", "最強陣容"),
    ):
        if key not in used_title_keys:
            unused_titles.append(T(key, fallback))
    if unused_titles:
        bits = "、".join(f"「{H(t, terms)}」" for t in unused_titles)
        add(
            p_html(
                "字串表另有"
                + bits
                + H(f"等標題，這 {len(recommends)} 筆沒有引用這些鍵，本頁不把它們當成目前這張表的標題。", terms)
            )
        )
    rec_table = []
    for row in recommends:
        title = T(row.get("key_id") or "")
        desc = T(row.get("dec_1") or "")
        sits = list(row.get("sit_id") or [])
        heroes_in = list(row.get("hero_id") or row.get("heroIds") or [])
        ordered = []
        if sits and len(sits) == len(heroes_in):
            pairs = sorted(zip(sits, heroes_in), key=lambda x: x[0])
            ordered = [f"{hid_sit[0]} {hero_link(hid_sit[1], terms)}" for hid_sit in pairs]
        else:
            ordered = [hero_link(h, terms) for h in heroes_in]
        rec_table.append(
            [
                H(title, terms) if title else "遊戲中文名稱表沒有對應名稱",
                H(desc, terms) if desc else "遊戲中文名稱表沒有對應名稱",
                "<br>".join(ordered),
                e(interval_text(row.get("season_on"))),
                e(interval_text(row.get("server_list"))),
            ]
        )
    add(
        table(
            ["官方標題", "官方簡述", "英雄與站位編號", "表上區間一", "表上區間二"],
            rec_table,
        )
    )
    add("    </section>")

    add('    <section id="seven-reward">')
    add(f"      <h2>{H(seven, terms)}</h2>")
    add(
        p_html(
            H(
                f"功能名稱是「{seven}」。活動表有一列使用同一名稱，時效欄位的數字是 "
                f"{act_seven.get('take_effect_time')}，本頁不換算單位。",
                terms,
            )
        )
    )
    g1 = groups.get(1) or []
    free_ids = [r.get("free_reward") for r in sorted(g1, key=lambda x: x.get("day") or 0)]
    vip_ids = [r.get("vip_reward") for r in sorted(g1, key=lambda x: x.get("day") or 0)]
    unresolved = [
        i
        for i in free_ids + vip_ids
        if i not in numerical_by_id
    ]
    add(
        p_html(
            H(
                f"另有一張登入獎勵表，共 {len(groups)} 組 {len(seven_login)} 筆。"
                f"各組筆數是 "
                + "、".join(f"第 {g} 組 {group_sizes[g]} 筆" for g in sorted(group_sizes))
                + "。"
                f"第 1 組有 {len(g1)} 日，免費獎勵編號是 "
                + "、".join(str(i) for i in free_ids)
                + "，貴族獎勵編號是 "
                + "、".join(str(i) for i in vip_ids)
                + "。"
                + (
                    "這些編號在本頁使用的數值獎勵表裡對不上內容，因此功能「"
                    + seven
                    + "」實際發什麼，本頁不寫。"
                    if unresolved
                    else ""
                )
                + "這張表本身沒有寫各組對應哪一個活動名稱，本頁不自行配對。"
                f"表上另有「{T('new_seven_day_01')}」「{T('new_seven_day_02')}」「{T('new_seven_day_03')}」等界面用字。",
                terms,
            )
        )
    )
    add(
        p_html(
            H(
                f"活動「{return_gift}」是回歸活動的官方名稱，與功能「{seven}」不是同一項。"
                "本頁不把它寫成新手七日獎勵。",
                terms,
            )
        )
    )
    gift_bits = []
    for row in sorted(gift_login, key=lambda r: r.get("day") or 0):
        rid = row.get("rewards") or row.get("rewards_show")
        reward_row = numerical_by_id.get(rid)
        if not reward_row:
            gift_bits.append(f"第 {row.get('day')} 日的獎勵編號在數值獎勵表對不上內容")
            continue
        slots = []
        for slot in range(1, 6):
            text = gift_slot_text(reward_row, slot, terms)
            if text:
                slots.append(text)
        gift_bits.append(f"第 {row.get('day')} 日：" + "；".join(slots))
    add(
        p_html(
            H(
                f"另外還有一張 {len(gift_login)} 日的登入贈禮表，獎勵編號可以在數值獎勵表對上部分內容。"
                "這張表不是功能「",
                terms,
            )
            + H(seven, terms)
            + H("」的獎勵內容，本頁分開寫。", terms)
        )
    )
    add("<ul>")
    for bit in gift_bits:
        add(f"<li>{bit}。</li>")
    add("</ul>")
    add(
        p_html(
            H(
                f"活動「{newbie_challenge}」在本頁使用的活動表裡標記為未開放；本頁只記名稱，不寫任務內容。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="festivals">')
    add(f"      <h2>{H(open_fest, terms)}、{H(seven_fest, terms)}</h2>")
    add(
        p_html(
            H(
                f"活動「{open_fest}」與「{seven_fest}」在活動表上互相列為互斥。"
                f"「{seven_fest}」的另一則官方用字是「{chaptersong}」。"
                f"兩個活動時效欄位的數字分別是 {act_open.get('take_effect_time')} 與 {act_fest.get('take_effect_time')}，"
                "本頁不換算單位。本頁沒有對上這兩個活動的任務或獎勵數值表，因此實際發什麼，本頁不寫。",
                terms,
            )
        )
    )
    open_tips = T("seven_reward_new_tips6")
    if open_tips:
        add(p_html(H(f"「{open_fest}」的說明原文如下。", terms)))
        add(quote_block(open_tips, terms))
    add("    </section>")

    add('    <section id="tasks">')
    add("      <h2>主要任務與功能開放</h2>")
    add(
        p_html(
            H(
                f"主要任務表共 {len(tasks)} 筆，唯一的起始編號是 1，這樣的列有 {unique_start} 筆。"
                f"其中有任務原文「{help_archer}」「{rescue_alchemist}」，這是任務文案，不是發放英雄的欄位。"
                f"引導表只有 {len(guide2)} 筆，本頁不把它寫成逐步攻略。",
                terms,
            )
        )
    )
    add(
        p_html(
            H(
                f"章節標題表有 {len(chapter_titles)} 則官方標題，表上沒有把這些標題對到具體任務編號，本頁只列出標題，不自行配對。",
                terms,
            )
        )
    )
    if chapter_titles:
        add("<ul>")
        for title in chapter_titles:
            add(f"<li>{H(title, terms)}</li>")
        add("</ul>")
    hall_link = link("city-buildings.html", hall, terms)
    pve_link = link("pve.html", f"{adventure}、{bounty}、{alliance_boss}", terms)
    add(
        p_html(
            H(f"功能「{world}」的開啟說明原文是「{world_tip}」。", terms)
            + hall_link
            + H("的城建資料見該頁。", terms)
        )
    )
    add(
        p_html(
            H(
                f"關卡表共 {fmt_int(len(stages))} 筆。功能「{adventure}」、「{bounty}」與活動「{alliance_boss}」的關卡規模與規則見",
                terms,
            )
            + pve_link
            + H("，本頁不重複抄錄。", terms)
        )
    )
    add(
        p_html(
            H(
                f"地圖物件「{beacon}」有 {len(birthpoints)} 筆，官方說明寫的是領主回到王國時選取座標，"
                "不是創角出生點。本頁使用的表裡沒有見到創角初始資源或初始道具專表。說明原文如下。",
                terms,
            )
        )
    )
    add(quote_block(official_text("map_birthpoint_info"), terms))
    add("    </section>")

    add('    <section id="seasons">')
    add(f"      <h2>{H(s1, terms)}、{H(s2, terms)}、{H(s3, terms)}、{H(s4, terms)}</h2>")
    clash = link("kingdom-clash.html", T("function_name_48", "王國對決") if has_string("function_name_48") else "王國對決", terms)
    # official 王國對決 page title is locked; use the same visible name as that page
    clash = link("kingdom-clash.html", "王國對決", terms)
    add(
        p_html(
            H(
                f"遊戲中文名稱表的賽季名稱有四則：「{s1}」「{s2}」「{s3}」「{s4}」。"
                "沒有第五、第六則賽季名稱。"
                f"回憶錄標題另有「{song}」，以及與上述四則相同的標題；另有一列沒有標題、標記為未開放。"
                f"預告表共 {len(previews)} 筆、{len(preview_groups)} 組，沒有第 5、第 6 組。"
                "預告裡的賽季名只按遊戲裡的原文寫出，不補造季號。",
                terms,
            )
        )
    )
    prepare_titles = []
    for row in prepares:
        title = T(row.get("season_prepare_title") or "")
        if title:
            prepare_titles.append(title)
    if prepare_titles:
        last_prep = T((prepares[-1] or {}).get("season_prepare_title") or "") if prepares else ""
        add(
            p_html(
                H(
                    f"賽季準備表共 {len(prepares)} 筆，官方標題是 "
                    + "、".join(f"「{t}」" for t in prepare_titles)
                    + "。"
                    + (
                        f"最後一筆的官方標題仍是「{last_prep}」，不能據內部季號把它寫成官方第五季名稱。"
                        if last_prep
                        else ""
                    ),
                    terms,
                )
            )
        )
    add(
        p_html(
            H(
                f"介紹表共 {len(introduces)} 筆。其中有 {len(season5_intro)} 筆的內部季號寫 5、主題號寫 4，"
                "條目標題包括"
                + "、".join(f"「{t}」" for t in season5_titles[:8])
                + (" 等" if len(season5_titles) > 8 else "")
                + f"，不是「{cloud}」或「{under}」。本頁不把內部季號寫成官方第 N 季。",
                terms,
            )
        )
    )
    add(
        p_html(
            H(
                f"「{cloud}」「{under}」出現在其他官方字串；「{hunt}」是另一則已核對的官方活動名，與「{under}」不是同一名稱。"
                "本頁不把這些名稱寫成已核對的官方第五季或第六季標題。相關說明見",
                terms,
            )
            + clash
            + "。"
        )
    )
    add("    </section>")

    add('    <section id="merge">')
    add("      <h2>" + H("合服、王國合併", terms) + "</h2>")
    add(
        p_html(
            H(
                "官方通知與狀態原文使用「合服」，合併郵件原文使用「王國合併」。兩種用字都按原文保留，不合併成一個自創總稱。",
                terms,
            )
        )
    )
    add(quote_block(official_text("notice_common_004"), terms))
    add(quote_block(official_text("server_status_001"), terms))
    add(p_html(H("合併郵件原文如下。時間寫法按模板保留，含其中的時區標記，不改寫成個別列的時區。", terms)))
    add(quote_block(official_text("server_merge_mail_3116"), terms))
    window_2033 = "2033-01-01 00:00:00|2033-01-01 23:59:59"
    add(
        p_html(
            H(
                f"合併表共 {fmt_int(len(merges))} 筆，時間窗有 {len(merge_times)} 種。"
                f"其中時間原文是「{window_2033.replace('|', '｜')}」的有 {merge_times.get(window_2033, 0)} 筆；"
                "本頁只記原文，不把它寫成已排程或未排程。"
                f"另有 {len(reversed_times)} 筆的起始時間字面值晚於結束時間，原文是「"
                + "、".join(sorted({t.replace('|', '｜') for t in reversed_times}))
                + "」，本頁按原文寫出，不對調。"
                f"合併表有內部編號 10050 的列，沒有編號 50 的列。"
                "本頁不把界面上看到的伺服器編號，對成表內編號。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="move">')
    add(f"      <h2>{H(move_name, terms)}</h2>")
    add(
        p_html(
            H(
                f"官方說明標題是「{move_title}」。道具官方短名是「{scroll}」，說明原文是「{scroll_desc}」。"
                "系統提示與說明另有「遷服卷軸」「遷移卷軸」的寫法；本頁使用的道具表只有這一筆，不把它們當成兩件不同道具。",
                terms,
            )
        )
    )
    add(p_html(H("官方說明原文如下，按遊戲裡的原文寫出。", terms)))
    for key in (
        "s_move_info_tile_21",
        "s_move_info_tips_111",
        "s_move_info_tile_22",
        "s_move_info_tips_121",
        "s_move_info_tile_23",
        "s_move_info_tips_131",
        "s_move_info_tips_132",
        "s_move_info_tips_133",
        "s_move_info_tile_24",
        "s_move_info_tips_141",
        "s_move_info_tips_142",
        "s_move_info_tips_143",
        "s_move_info_tips_144",
        "s_move_info_tips_145",
        "s_move_info_tile_25",
        "s_move_info_tips_151",
        "s_move_info_tips_152",
        "s_move_info_tips_153",
        "s_move_info_tile_31",
        "s_move_info_tips_211",
        "s_move_info_tips_212",
        "s_move_info_tips_213",
        "s_move_info_tile_32",
        "s_move_info_tips_221",
        "s_move_info_tips_222",
        "s_move_info_tips_223",
        "s_move_info_tile_33",
        "s_move_info_tips_231",
        "s_move_info_tips_232",
        "s_move_info_tips_233",
        "s_move_info_tips_234",
        "s_move_info_tips_235",
        "s_move_info_tips_236",
        "s_move_info_tips_237",
        "s_move_info_tips_238",
        "s_move_info_tips_239",
        "s_move_info_tips_240",
        "s_move_info_tips_241",
        "s_move_info_tile_41",
        "s_move_info_tips_311",
        "s_move_info_tips_312",
        "s_move_info_tile_42",
        "s_move_info_tips_321",
        "s_move_info_tips_322",
        "s_move_info_tips_323",
        "s_move_info_tips_324",
        "s_move_info_tips_325",
        "s_move_info_tile_43",
        "s_move_info_tips_331",
        "s_move_info_tips_400",
        "s_move_info_tips_401",
        "s_move_info_tips_402",
        "s_move_info_tips_403",
        "s_move_info_tips_404",
        "s_move_info_tips_405",
        "s_move_info_tips_406",
    ):
        text = official_text(key)
        title_like = key.startswith("s_move_info_tile_") or key == "s_move_info_tips_400"
        visible = visible_official(text)
        if not visible:
            continue
        if title_like and not visible[0].isdigit():
            add(f"<h3>{H(visible, terms)}</h3>")
        else:
            add(quote_block(text, terms))
    add(
        p_html(
            H(
                f"遷移表共 {fmt_int(len(moves))} 筆，時間窗有 {len(move_times)} 種，花費組有 "
                + "、".join(f"第 {g} 組 {move_groups[g]} 筆" for g in sorted(move_groups))
                + f"。組隊開放標記在 {fmt_int(len(moves))} 筆都是 "
                + "、".join(str(x) for x in sorted(team_open, key=lambda x: str(x)))
                + "。"
                f"遷移表同樣有內部編號 10050 的列，沒有編號 50 的列。"
                "本頁不把界面上看到的伺服器編號，對成表內編號。"
                "補償郵件另提到按城堡等級計算的遷服券政策，與下面這張以歷史最大影響力分檔的花費表不是同一欄，不合併成一條公式。",
                terms,
            )
        )
    )
    # cost table: item_cost is shared; power_max differs
    cost_header = ["檔序", "卷軸數量"] + [f"第 {g} 組上限數字" for g in sorted(cost_by_group)]
    n_tiers = max(len(v) for v in cost_by_group.values()) if cost_by_group else 0
    cost_body = []
    for i in range(n_tiers):
        row = [str(i + 1)]
        costs = [cost_by_group[g][i].get("item_cost") for g in sorted(cost_by_group) if i < len(cost_by_group[g])]
        row.append(fmt_int(costs[0]) if costs and len(set(costs)) == 1 else "、".join(fmt_int(c) for c in costs))
        for g in sorted(cost_by_group):
            rec = cost_by_group[g][i] if i < len(cost_by_group[g]) else {}
            row.append(fmt_int(rec.get("power_max")))
        cost_body.append(row)
    add(
        p_html(
            H(
                f"花費表共 {len(move_costs)} 筆，{len(cost_by_group)} 個花費組各 {n_tiers} 檔。"
                "各檔的卷軸數量完全相同，差別只在上限數字。"
                "官方說明寫：「領主的歷史最大影響力越高，需要消耗的遷移卷軸越多。」"
                "比較方向（大於、小於或等於上一檔）表上沒有寫，只列出原值，不自行改寫成滿多少就收多少張。",
                terms,
            )
        )
    )
    if cost_body:
        add(table(cost_header, cost_body))
    add("    </section>")

    add('    <section id="newbie-move">')
    add(f"      <h2>{H(mail_new, terms)}</h2>")
    add(
        p_html(
            H(
                f"與上述 30 級／60 天規則並列，另有免費新手遷服文案。成功郵件標題是「{mail_new}」；"
                f"一般「{move_name}」成功的郵件標題是「{mail_ok}」。"
                "這條特權的條件沒有另寫在遷移表的欄位裡，只見於官方字串。原文如下。",
                terms,
            )
        )
    )
    add(quote_block(official_text("invitee_transfer_1"), terms))
    add("    </section>")

    add('    <section id="server-tasks">')
    st_names = unique_keep_order(T(r.get("name") or "") for r in server_tasks)
    add(
        "      <h2>"
        + H("、".join(st_names[:3]), terms)
        + "</h2>"
    )
    add(
        p_html(
            H(
                f"開服後依天數排列的任務表共 {len(server_tasks)} 筆，官方名稱只有 {len(st_names)} 種，重複使用："
                + "、".join(f"「{n}」" for n in st_names)
                + "。"
                "說明原文與條件數字有對不上的地方，一律並列，不自行改寫說明。"
                "獎勵編號對不上本頁使用的數值獎勵表，不寫具體道具。",
                terms,
            )
        )
    )
    st_table = []
    for row in server_tasks:
        name = T(row.get("name") or "") or "遊戲中文名稱表沒有對應名稱"
        desc = T(row.get("describe") or "") or "遊戲中文名稱表沒有對應名稱"
        limit = row.get("time_limit")
        auto = row.get("auto_accomplished")
        limit_text = fmt_int(limit)
        if auto == 1:
            limit_text = f"{limit_text}（自動完成）"
        st_table.append(
            [
                H(name, terms),
                fmt_int(row.get("server_open_days")),
                H(desc, terms),
                limit_text,
            ]
        )
    add(table(["官方名稱", "開服天數", "官方說明（原文）", "時限"], st_table))
    add(
        p_html(
            H(
                "說明原文寫城堡達到 7 級的「城市建設者」有三筆，後兩筆的條件數字是 15 與 25，本頁只並列，不改寫說明。"
                "「狩獵魔物」有一筆的說明原文是「領主的城堡達到5級」；「冒險開始」也有一筆說明同樣是這句，條件數字是 30。"
                "一律按原文並列。",
                terms,
            )
        )
    )
    add("    </section>")

    add('    <section id="stronger">')
    add(f"      <h2>{H(grow, terms)}</h2>")
    add(
        p_html(
            H(
                f"「變強」入口表共 {len(stronger)} 筆，不是商店價目。"
                f"有兩筆名稱與說明相同的「{first_store}」，差別只在表上另一組數字，本頁不解釋這組數字。"
                f"其餘官方名稱是「{hero_up}」「{tavern}」「{grow}」，這三筆沒有說明原文。",
                terms,
            )
        )
    )
    stronger_table = []
    for row in stronger:
        name = T(row.get("name") or "") or "遊戲中文名稱表沒有對應名稱"
        desc = T(row.get("desc") or "")
        stronger_table.append([H(name, terms), H(desc, terms) if desc else "（無說明原文）"])
    add(table(["官方名稱", "官方說明"], stronger_table))
    add(
        p_html(
            H(
                "登入彈窗表有 33 筆，欄位只有編號、優先順序、類型與中斷標記，沒有名稱或活動綁定，無法分辨哪些是開場提示、哪些是一般宣傳。本頁不展開。",
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
        "<li>手冊第 4 章是章節提綱。數值、名稱與條件以 2026-11-22 LocalLow 表與字串表為準；"
        "現行 <code>/workspace/topheroes/data/</code> 與該批解壓檔在本頁用到的表上全文相同。"
        "可見正文不寫「開局」為官方功能總稱，也不把顯示伺服器編號寫成內部編號加一萬。</li>"
    )
    add(
        "<li>可見正文不寫原始欄位名。六名英雄的榮譽組編號是 <code>301</code>。"
        f"{e(warrior)} 的解鎖條件為空，其餘五名是 <code>[1, 10]</code>，含義未核對。"
        "登入獎勵表各組與活動名稱沒有在本頁用到的表上直接對上；第 1 組獎勵編號不在 <code>reward_numerical_new</code>。"
        "活動「七日獎勵」「開服慶典」「七日慶典」的時效數字是 240、336、168，單位未核對。"
        "推薦表的 <code>exchage</code>／<code>hero_change</code> 界面含義未核對。"
        "合併表 8 筆逆序時間窗的內部編號是 10857–10864。"
        "全服任務獎勵編號是 905701–905720。"
        "賽季道具回收表不是王國遷移，本頁不展開。</li>"
    )
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(page_title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_seven_reward_move_page() -> str:
    return render_html()
