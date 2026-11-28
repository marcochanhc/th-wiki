"""Public catalog of official PVE-related systems from the 2026-11-22 LocalLow extract."""

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
    "map_stage.json": "d81c0dc629b5276ddfc5a90733430f0d30d093f2a030cb207f76cd732b4bd538",
    "map_stage_wave.json": "41216ce89b287851b456be2ce28fb8db338015af2cfeb4514c7e311e71bebdb9",
    "map_adventure_area.json": "02454aeebd846bfcab188711467fe0173cc3b93ddbf0fc8c98bfd70319b050a4",
    "map_challenge.json": "3b69d9cb9a5fb58a1011ebe72c19e4d0de50e1cf87eae66d32c89f9d434c3937",
    "map_challenge_stage.json": "77995e88b524c542f0416be0adcd9a86cdb029d98046f9825b318cac8fa20ceb",
    "firepot_idle_reward.json": "856c0f1d94f9d4a2b09239262e6bbff46df53e89b459b169714956a8e1f2f027",
    "firepot_quick_raid.json": "2eb516f878853c12484b8059ebf6f56abfb4c4e8cd53fb57d787d43966b734c1",
    "monster.json": "a8d5239246075c33935d9b5c7b73998efdc9ef96d28f1a8b79e8b052dee55674",
    "monster_group.json": "21daf4b11e1a0d36620cf89d140356311a39b68538c86c4da5f6a8b95f7b3fba",
    "map_monster.json": "3f0d607235d729b0202214942bcd5df3d8121b9935c7e2f671d5696d1d5df819",
    "map_monster_group.json": "9ee2bdea0fec1f404dca7984b2820d95bc68212a81283860fcb96439c155bbcc",
    "map_monster_refresh.json": "96e8280b480006d5d852146ef98bb6c2da90c6be0a959301fc6e7614c8c33655",
    "map_boss.json": "6e52d5ed2630798ec1288ca3a7fbfffcb45712137fd8090affcdcc4f72ba0e23",
    "Infinite_monster.json": "361447c4b96c9de255008e25889db075d508302558d864faeeb4468ba7a7b8cc",
    "Infinite_monster_group.json": "9cef678acdee918b32a402462376df6491ffd011b636c6765ff92f2c995ee202",
    "Infinite_monster_attr.json": "de26661ccb6448d308b6bf8977c1c806f3ce4db3c0fd2b70d6997fdfd4ea69b1",
    "Infinite_monster_buff.json": "ea7213c50e7abf940dbd3ceebefc11b76e934327671a873bdf74849991335f1d",
    "Infinite_monster_buildingattr.json": "5c38260fddeb6a450b74dd44f89299f52fae264b8fdb4cb4e926ce6a9b654abf",
    "activity_infinite_floor.json": "5198c4d7ce0f80564b7995d27451b01e70f376d0769dd61e837937fea9047f81",
    "alliance_boss_difficulty.json": "406e46f51037838ea660866367faa4011b374e108f17fe15093ebad99789d97d",
    "raid_battlefield_group.json": "d2b96b2c93b16fc1f2494d98addb28172c57f7e355b2f63750cf62b8e7671aa4",
    "raid_treasure_group.json": "964a8ae3d593ba8e6d49288be37bdd151a8c704f736438cee465984a56ec0509",
    "activity_raid.json": "2c88507759e76a1124cbe2de637eba08b0cc5f92912975355a5868c1cbbc4073",
    "alliance_raid.json": "2e07642f00157e0cd93f0ff71b2319e541232c80204d07d1433c751338180ba0",
    "card_raid.json": "8f6d9ff48d1ffb897547597c7b0ef276fb346957dc62239ee2d45aec4ea9713c",
    "fort_raid.json": "2e7173221b287def7ef1f24940635bb28b5adfcdafc8012de84cb7d95e17bc90",
    "fort_raid_event.json": "a01b6a93650d96e612f10b9c04293e5f79f1661f16039ca02602819128fc1c69",
    "fort_raid_group.json": "cfe1412a64fdc7b70159bd83a39e809e234580afbaeb93b15d9c911e327b159f",
    "dark_legion_challenge.json": "84e85914fb02a1b3866ee87dc691346499e58afd0f793f07acd2b333febfe52d",
    "multiplayer_boss.json": "dd9848e5cc8b60c4a06c618275570e6eecf901fc29a8778e2168a9bf366b9219",
    "worm_boss.json": "1c2260eac6ed88443295c0ed4823f47eb25d43ec7251f486d5d5b98db1a65901",
    "activity_click_monster.json": "0db9f7d22931626ae564d12d1ebedc96089e1ff6554277d617705cae6df6239a",
    "challenge_arena_pve.json": "f7fb12924d7433e01f8cdf00714c49306429fda0b638e8a2d4076dfb6ae80b6b",
    "bounty_task.json": "db3d5d2dfb843699cc3bb9de8933ba3986d04c1d851ed48791361886eb5b4636",
    "bounty_prestige.json": "e7d8c7044d04733a4736bbe6a5ab86b3b4273bd443291aa9bbf5e576c63b6345",
    "bounty_world_ui_show.json": "6a5ef65e06f948af4aaad76b573ff0cb8ba577fc7da67d26ef46a91d6192501b",
    "trading_pve.json": "56987922ab9b1cef1615713e8e31cafec367405dff84fbc1cbdf53ab969cc978",
    "trading_pve_kvk.json": "675898a887ef5c2eb37c656b315f5b7785bc4afdba6e456345ffef560bb3eef3",
    "season_encounter.json": "17a9d271a56dd422e54282ff51a7509249b3bc18b2ca1876707e3b853c3bc0de",
    "season_activity_preview.json": "5cb4fa4c785a5ba29a6fc5e09bdc3544c18aa27735d87ef53011d16a7222a008",
    "activity_dispath_hero.json": "c6637ade7b6a0a28f20d33d9c44fdbc8205ae32dbc27951959e137420a352296",
    "citybuilding.json": "25dc79829dcc0888168e76fe7f2bd5cb9d4dc97df6cecdc98b6e01cb24c24a0f",
}


def T(key: str, fallback: str = "") -> str:
    return visible_official(official_text(key) or fallback)


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def named(row: dict, fields: tuple[str, ...]) -> str:
    for field in fields:
        key = row.get(field)
        if key not in (None, "", -1, "-1") and has_string(key):
            return T(str(key))
    return ""


def load_pinned(name: str):
    return load_table(name, TABLE_SHA256[name])


def terms_for() -> list[str]:
    names = [
        T("function_name_101", "冒險"),
        T("function_name_106", "世界"),
        T("function_name_116", "懸賞"),
        T("UI_Bounty_001", "懸賞"),
        T("activity_name591", "公會Boss"),
        T("UI_Alliance_boss_02", "公會Boss活動規則"),
        T("citybuilding_name_144", "懸賞大廳"),
        T("Raid_BattaleField_01", "榮譽試煉"),
        T("Raid_BattaleField_20", "虛空寶庫"),
        T("treasure_1", "高塔寶庫"),
        T("alliance_brazier_name", "公會火盆"),
        T("infinitelevel_title", "關卡進度 {0}/{1}"),
        T("activity_infinite_floor_02", "本層大獎"),
        T("activity_infinite_floor_18", "前往寶藏層"),
        T("race_alliance_underway_tab_battle", "同盟突襲"),
        T("race_activity_title_advance", "公會突襲"),
        T("UI_Title_071", "要塞突襲說明"),
        T("activity_ui_alliance_raid_1", "馴龍訓練場"),
        T("new_card_raid_name_1", "捍衛者"),
        T("worm_boss_name", "沙漠暴君"),
        T("function_name_51", "商隊"),
        T("showname_318", "祕境派遣"),
        T("function_name_68", "滅火"),
        T("function_name_113", "挑戰賽"),
        T("function_name_114", "積分賽"),
        T("tvt_rank_function_name", "天梯賽"),
        T("s2_peak_name", "巔峰積分賽"),
        T("info_title_50024", "世界Boss"),
        T("bounty_fun_des_19"),
        T("bounty_fun_des_20"),
        T("bounty_fun_des_21"),
        T("pet_egg_04", "野外寵物"),
        T("Infinite_monster_buff_name_1"),
        T("Infinite_monster_buff_name_2"),
        T("Infinite_monster_buff_name_3"),
        T("Infinite_monster_buff_name_4"),
        T("ether_ranch_030", "牧場物語"),
        T("activity_name_5001003", "摸魚時光") if has_string("activity_name_5001003") else "摸魚時光",
        "魚缸",
        "抓蝴蝶",
        "精靈小屋",
        "守護魔獸",
        "帕魯",
        "合養",
        "蹦蹦向前衝",
        "世界樹之影",
        "冰封之焰",
        "暮光之戰",
        "潮汐之怒",
        "最強之路",
        "零售商船",
        "文化大廳",
        "破魔箭矢",
    ]
    skip = {"使用", "提交", "確認", "取消", "查看", "參與", "全部", "詳情"}
    return [n for n in unique_keep_order(names) if n and len(n) >= 2 and n not in skip]


def link(href: str, label: str, terms: list[str]) -> str:
    return f'<a href="{e(href)}">{H(label, terms)}</a>'


def render_html() -> str:
    from .render import page_shell, toc_list

    functions = load_pinned("function.json")
    stages = load_pinned("map_stage.json")
    waves = load_pinned("map_stage_wave.json")
    areas = load_pinned("map_adventure_area.json")
    challenges = load_pinned("map_challenge.json")
    challenge_stages = load_pinned("map_challenge_stage.json")
    firepot_idle = load_pinned("firepot_idle_reward.json")
    firepot_quick = load_pinned("firepot_quick_raid.json")
    monsters = load_pinned("monster.json")
    monster_groups = load_pinned("monster_group.json")
    map_monsters = load_pinned("map_monster.json")
    map_monster_groups = load_pinned("map_monster_group.json")
    map_monster_refresh = load_pinned("map_monster_refresh.json")
    map_bosses = load_pinned("map_boss.json")
    inf_monsters = load_pinned("Infinite_monster.json")
    inf_groups = load_pinned("Infinite_monster_group.json")
    inf_attr = load_pinned("Infinite_monster_attr.json")
    inf_buff = load_pinned("Infinite_monster_buff.json")
    inf_building = load_pinned("Infinite_monster_buildingattr.json")
    floors = load_pinned("activity_infinite_floor.json")
    boss_diff = load_pinned("alliance_boss_difficulty.json")
    honor_groups = load_pinned("raid_battlefield_group.json")
    treasure_groups = load_pinned("raid_treasure_group.json")
    activity_raid = load_pinned("activity_raid.json")
    alliance_raid = load_pinned("alliance_raid.json")
    card_raid = load_pinned("card_raid.json")
    fort_raid = load_pinned("fort_raid.json")
    fort_event = load_pinned("fort_raid_event.json")
    fort_group = load_pinned("fort_raid_group.json")
    dark_legion = load_pinned("dark_legion_challenge.json")
    multi_boss = load_pinned("multiplayer_boss.json")
    worm_boss = load_pinned("worm_boss.json")
    click_monsters = load_pinned("activity_click_monster.json")
    arena_pve = load_pinned("challenge_arena_pve.json")
    bounty_tasks = load_pinned("bounty_task.json")
    bounty_prestige = load_pinned("bounty_prestige.json")
    bounty_ui = load_pinned("bounty_world_ui_show.json")
    trading_pve = load_pinned("trading_pve.json")
    trading_pve_kvk = load_pinned("trading_pve_kvk.json")
    encounters = load_pinned("season_encounter.json")
    previews = load_pinned("season_activity_preview.json")
    dispatch = load_pinned("activity_dispath_hero.json")
    terms = terms_for()

    adventure = T("function_name_101", "冒險")
    world = T("function_name_106", "世界")
    bounty = T("function_name_116", "懸賞")
    alliance_boss = T("activity_name591", "公會Boss")
    hall = T("citybuilding_name_144", "懸賞大廳")
    honor = T("Raid_BattaleField_01", "榮譽試煉")
    void = T("Raid_BattaleField_20", "虛空寶庫")
    tower = T("treasure_1", "高塔寶庫")
    progress = T("infinitelevel_title", "關卡進度 {0}/{1}")
    layer_prize = T("activity_infinite_floor_02", "本層大獎")
    title_names = f"{adventure}、{bounty}、{alliance_boss}"
    page_title = f"Top Heroes Wiki｜{title_names}"
    lede = (
        f"本頁寫功能「{adventure}」、「{world}」、「{bounty}」與活動「{alliance_boss}」，"
        f"以及「{honor}」、「{void}」等已核對的官方名稱系統。"
        "遊戲中文名稱表沒有一個單獨功能名，用來把這兩套層數關卡叫成同一個系統；"
        f"一套界面標題是「{progress}」，另一套界面用語包括「{layer_prize}」。"
        "兩套分開寫，不把它們寫成同一玩法。"
        "本頁不是對戰頁，也不把這些系統寫進王國對決。"
    )
    summary = f"{title_names}等已核對系統：關卡規模、官方名稱與規則原文。不是打法攻略。"
    toc = toc_list([
        {"id": "lead", "label": "簡介與閱讀說明"},
        {"id": "adventure", "label": adventure},
        {"id": "world", "label": world},
        {"id": "stage-progress", "label": "關卡進度"},
        {"id": "layer-prize", "label": layer_prize},
        {"id": "alliance-boss", "label": alliance_boss},
        {"id": "honor-trial", "label": honor},
        {"id": "void-vault", "label": void},
        {"id": "named-battles", "label": "其他已命名系統"},
        {"id": "bounty", "label": bounty},
        {"id": "season-preview", "label": "賽季預告原文"},
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
        "名稱與說明以遊戲裡看得到的為準。本頁不是遊戲裡的單一功能名，"
        f"而是把已核對的相關官方系統寫在一起。標題用「{H(adventure, terms)}」、「{H(bounty, terms)}」、"
        f"「{H(alliance_boss, terms)}」，因為這三個都是功能表或活動裡的官方名稱。"
        "沒有官方名稱的，寫「遊戲中文名稱表沒有對應名稱」，不編造總稱，也不把不同系統合併成一種。"
    ))
    add(p_html(
        "以下是表上的數字，沒有額外的官方中文欄名。官方字串按遊戲裡的原文寫出，不改標點。"
        "表上沒有說明文字的數字，不當成已核對的解鎖條件或戰鬥公式。"
        "獎勵還沒對到道具名稱的，只標待補，不編造內容。"
        "本頁不模擬戰鬥，不排關卡優先，也不做通關陣容。"
    ))
    add(p_html(
        f"「{H(adventure, terms)}」按鈕不能單獨對成關卡主表的某一類。"
        f"「{H(progress, terms)}」與「{H(layer_prize, terms)}」沒有對照說明，分開寫。"
        f"「{H(void, terms)}」與「{H(tower, terms)}」用字不同，不逕行等同為同一入口。"
        f"「冒險火盆」與「{H(T('alliance_brazier_name', '公會火盆'), terms)}」不是同一套。"
        "預告裡的賽季名只按遊戲裡的原文寫出；表上沒有以潮汐之怒之後的標題為名的第 5、第 6 組，不補造季號。"
    ))
    add("    </section>")

    # 冒險
    add('    <section id="adventure">')
    add(f"      <h2>{H(adventure, terms)}</h2>")
    add(p_html(
        f"功能表有 {len(functions)} 筆。其中「{H(adventure, terms)}」開啟小地圖面板。"
        f"官方說明：「{H(T('adventure_fund_1'), terms)}」"
        "另有每日殺怪抽卡碎片規則，原文較長，見下方引文。"
        "任務名稱包括："
        + "、".join(f"「{H(T(f'task_map_adventure_{i}'), terms)}」" for i in range(1, 11))
        + "。這些字串證明界面有章節進度，仍不能證明關卡主表的某一類就是這個按鈕。"
    ))
    add(quote_block(official_text("adventure_draw_card_drop_5"), terms))
    add(p_html(
        f"冒險區域表有 {fmt_int(len(areas))} 筆，沒有關卡中文名。"
        f"挑戰主表有 {fmt_int(len(challenges))} 筆，對應的關卡表有 {fmt_int(len(challenge_stages))} 筆，"
        f"{len({r.get('group_id') for r in challenge_stages})} 個分組與挑戰主表一一對上。"
        f"挑戰名稱是官方地名或路線名；其中 {sum(1 for r in challenges if named(r, ('challenge_name',)) == '最強之路')} 筆共用名稱"
        f"「{H('最強之路', terms)}」，這是遊戲原文，不是本頁評級。"
        "本頁不把這些挑戰列自行等同於「冒險」按鈕。"
    ))
    name_counts = Counter(named(r, ("challenge_name",)) or "遊戲中文名稱表沒有對應名稱" for r in challenges)
    add(table(
        ["名稱", "筆數"],
        [[H(name, terms), fmt_int(count)] for name, count in sorted(name_counts.items(), key=lambda x: (-x[1], x[0]))],
        caption="挑戰名稱",
    ))

    type_counts = Counter(r.get("type") for r in stages)
    t1 = type_counts.get(1, 0)
    t2 = type_counts.get(2, 0)
    t1_ids = [int(r["id"]) for r in stages if r.get("type") == 1]
    t1_cont = sum(1 for i in t1_ids if 1 <= i <= 1000)
    t2_ids = [int(r["id"]) for r in stages if r.get("type") == 2]
    maps = {r.get("map") for r in stages}
    fight_one = [r for r in stages if r.get("fight_type") == 1]
    season_vals = Counter(r.get("season") for r in stages if r.get("season") not in (None, -1, "-1"))
    wave_stages = {r.get("stage") for r in waves}
    stage_ids = {r.get("id") for r in stages}
    only_waves = len(wave_stages - stage_ids)
    row1 = next(r for r in stages if r.get("id") == 1)
    add(p_html(
        f"關卡主表有 {fmt_int(len(stages))} 筆，沒有關卡中文名。"
        f"較大的一組有 {fmt_int(t1)} 筆，其中編號 1 至 1000 是連續的 {fmt_int(t1_cont)} 筆，其餘 {fmt_int(t1 - t1_cont)} 筆編號不連續。"
        f"另一組有 {fmt_int(t2)} 筆，編號從 {fmt_int(min(t2_ids))} 起到 {fmt_int(max(t2_ids))}。"
        f"另外還有 {fmt_int(type_counts.get(3, 0))} 筆、{fmt_int(type_counts.get(4, 0))} 筆、{fmt_int(type_counts.get(6, 0))} 筆較少的分組。"
        f"編號 1 的列寫有隊伍等級 {fmt_int(row1.get('team_level'))}、隊伍戰力 {fmt_int(row1.get('team_power'))}、"
        f"另一項戰力數字 {fmt_int(row1.get('new_power'))}、城堡等級 {fmt_int(row1.get('team_castle_level'))}。"
        "這些數字是推薦值、門檻還是別的條件，表上沒有說明，不當成已核對的解鎖條件。本頁不抄每關戰力曲線。"
        f"地圖編號共 {fmt_int(len(maps))} 個不同值；場景中文名尚未全部對上，待補。"
        f"有一種戰鬥標記的列共 {fmt_int(len(fight_one))} 筆，編號落在同一區段，賽季欄都是 −1；不把它寫成已核對的戰鬥公式。"
        f"賽季欄有值的列共 {fmt_int(sum(season_vals.values()))} 筆（1：{season_vals.get(1, 0)}、2：{season_vals.get(2, 0)}、3：{season_vals.get(3, 0)}），只記數字，不補造官方季號。"
        f"波次表有 {fmt_int(len(waves))} 筆，去重後的關卡編號也是 {fmt_int(len(wave_stages))} 個；"
        f"其中 {fmt_int(len(wave_stages & stage_ids))} 個對得上關卡主表，其餘 {fmt_int(only_waves)} 個不在主表，不自行補關卡名。"
    ))

    add("      <h3>冒險火盆</h3>")
    add(p_html(
        f"放置獎勵表有 {fmt_int(len(firepot_idle))} 筆，是掛機獎勵，不是 {fmt_int(len(firepot_idle))} 個關卡名。"
        f"立即領取表有 {fmt_int(len(firepot_quick))} 筆：城堡等級 "
        + "／".join(str(r.get("city_level")) for r in firepot_quick)
        + f"，體力消耗皆為 {firepot_quick[0].get('stamina_cost')}。"
        "官方說明如下。"
    ))
    add(quote_block(official_text("UI_firepotidle_desc_5"), terms))
    add(quote_block(official_text("UI_firepotidle_desc_6"), terms))
    add(p_html(f"活動文案另有：「{H(T('activity_desc_100007'), terms)}」。"))
    add(p_html(
        f"另有「{H(T('alliance_brazier_name', '公會火盆'), terms)}」，文案用於驅散迷霧，"
        "與上面的冒險火盆不是同一張表，不要混成一套。"
    ))
    add("    </section>")

    # 世界
    add('    <section id="world">')
    add(f"      <h2>{H(world, terms)}</h2>")
    add(p_html(
        f"功能「{H(world, terms)}」的提示是：「{H(T('function_tips_106'), terms)}」。"
        f"建築官方名稱是「{link('city-buildings.html', hall, terms)}」。"
        f"這是世界地圖入口，含打野與其他地圖互動，不把它寫成只打怪。"
        f"「{H(bounty, terms)}」的開啟條件與「{H(world, terms)}」相同，見下方懸賞節。"
    ))
    gathering = sorted({
        T(str(r.get("name"))) for r in monsters
        if r.get("name") not in (None, "", -1, "-1") and has_string(r.get("name"))
    })
    group_names = sorted({
        T(str(r.get("group_name"))) for r in monster_groups
        if r.get("group_name") not in (None, "", -1, "-1") and has_string(r.get("group_name"))
    })
    add(p_html(
        f"怪物主表有 {fmt_int(len(monsters))} 筆。名稱對到遊戲中文名稱表的只有 "
        f"{sum(1 for r in monsters if r.get('name') not in (None, '', -1, '-1') and has_string(r.get('name')))} 筆，"
        f"去重後 {fmt_int(len(gathering))} 個官方名稱，全部是採集物："
        + "、".join(H(n, terms) for n in gathering)
        + "。其餘大量列沒有對應的界面名稱，本頁不編造戰鬥怪物名錄。"
        f"怪物分組表有 {fmt_int(len(monster_groups))} 筆，其中有官方名稱的包括："
        + "、".join(H(n, terms) for n in group_names)
        + "；大多數分組沒有名稱。"
    ))
    add(p_html(
        f"世界地圖刷新表有 {fmt_int(len(map_monsters))} 筆、分組 {fmt_int(len(map_monster_groups))} 種、"
        f"刷新配置 {fmt_int(len(map_monster_refresh))} 筆。本頁不評哪些野怪比較值得打。"
    ))
    world_boss = T("info_title_50024", "世界Boss")
    boss_names = []
    for r in map_bosses:
        key = r.get("boss_name") or r.get("activity_name")
        label = T(str(key), str(key) if key else "")
        if not label and key:
            label = str(key)
        if label:
            boss_names.append(label)
    add(p_html(
        f"世界地圖首領表有 {fmt_int(len(map_bosses))} 筆。官方名稱（同時也是活動名）是："
        + "、".join(f"「{H(n, terms)}」" for n in unique_keep_order(boss_names))
        + f"。這與「{H(alliance_boss, terms)}」不是同一系統。界面另有說明標題「{H(world_boss, terms)}」。"
    ))
    add("    </section>")

    # 關卡進度
    add('    <section id="stage-progress">')
    add("      <h2>關卡進度</h2>")
    group_counts = Counter(r.get("group_id") for r in inf_groups)
    buff_names = [T(f"Infinite_monster_buff_name_{i}") for i in range(1, 5) if T(f"Infinite_monster_buff_name_{i}")]
    add(p_html(
        f"遊戲中文名稱表沒有單獨的功能名對應這套關卡。界面標題是「{H(progress, terms)}」。"
        f"勝利說明：「{H(T('Infinite_monster_ui_5'), terms)}」。"
        f"波次怪物定義有 {fmt_int(len(inf_monsters))} 筆；分組表有 {fmt_int(len(inf_groups))} 筆"
        f"（其中一組 {fmt_int(group_counts.get(1, 0))} 筆、另一組 {fmt_int(group_counts.get(2, 0))} 筆），"
        "含前置等級、所需天數、地圖、強化與首通獎勵。"
        f"強化、屬性與建築加成表分別有 {fmt_int(len(inf_buff))}、{fmt_int(len(inf_attr))}、{fmt_int(len(inf_building))} 筆。"
        "強化官方名稱有："
        + "、".join(f"「{H(n, terms)}」" for n in buff_names)
        + "。界面另有全體攻擊、移速、生命、冒險減傷，以及士兵或弓兵加入隊伍等說明。"
        "功能表沒有與這套關卡對得上的單獨功能列；它是否掛在「冒險」或其他入口，尚未核對。"
        f"這一套與下面「{H(layer_prize, terms)}」沒有對照說明，不合併。"
    ))
    add("    </section>")

    # 本層大獎
    add('    <section id="layer-prize">')
    add(f"      <h2>{H(layer_prize, terms)}</h2>")
    floor_groups = Counter(r.get("group") for r in floors)
    levels = {g: [r.get("level") for r in floors if r.get("group") == g] for g in sorted(floor_groups)}
    loop_vals = Counter(r.get("loop") for r in floors)
    first_rewards = {}
    for g in sorted(floor_groups):
        rows = sorted((r for r in floors if r.get("group") == g), key=lambda x: x.get("level") or 0)
        first_rewards[g] = rows[0].get("reward") if rows else None
    add(p_html(
        f"這套界面用語包括「{H(T('activity_infinite_floor_01', '第{0}層'), terms)}」、"
        f"「{H(layer_prize, terms)}」、「{H(T('activity_infinite_floor_18', '前往寶藏層'), terms)}」。"
        f"表上共 {fmt_int(len(floors))} 筆，分成 {fmt_int(len(floor_groups))} 組，"
        + "、".join(
            f"第 {g} 組 {fmt_int(len(levels[g]))} 層（{fmt_int(min(levels[g]))} 至 {fmt_int(max(levels[g]))}）"
            for g in sorted(levels)
        )
        + "。"
        "各層寫有獎勵編號，具體道具尚未對到名稱，待補。"
        f"循環相關數字多數是 −1，另有 {fmt_int(loop_vals.get(51, 0))} 筆是 51，含義尚未核對。"
        f"與上一節「關卡進度」是否為同一入口，表上沒有對照說明，不把它們寫成同一玩法。"
    ))
    add("    </section>")

    # 公會Boss
    add('    <section id="alliance-boss">')
    add(f"      <h2>{H(alliance_boss, terms)}</h2>")
    add(p_html(
        f"難度表有 {fmt_int(len(boss_diff))} 筆，同一組。官方難度名是"
        + "、".join(
            f"「{H(named(r, ('difficulty_name',)) or '遊戲中文名稱表沒有對應名稱', terms)}」"
            for r in boss_diff
        )
        + "。擊殺血量只按表上數字寫出，不換算、不模擬。"
    ))
    add(table(
        ["難度", "擊殺血量"],
        [
            [
                H(named(r, ("difficulty_name",)) or "遊戲中文名稱表沒有對應名稱", terms),
                fmt_int(r.get("kill_hp")),
            ]
            for r in boss_diff
        ],
        caption="公會Boss難度與擊殺血量",
    ))
    add(p_html(
        "解鎖與可見的賽季數字：難度1至難度9為 −1；難度10為 1／1；難度11為 2／1；"
        "難度12為 3／2；難度13為 5／5；難度14為 6／6。"
        "這裡的 5、6 是表上欄位，不是已核對的官方賽季標題。"
    ))
    add(quote_block(official_text("alliance_boss_mainui_desc1"), terms))
    add(p_html(f"參與條件原文：「{H(T('alliance_boss_participate_level'), terms)}」。"))
    add(quote_block(official_text("alliance_boss_choose_difficulty_tips2"), terms))
    add(quote_block(official_text("alliance_boss_choose_difficulty_tips3"), terms))
    add(quote_block(official_text("alliance_boss_choose_difficulty_tips4"), terms))
    add(p_html("傷害獎勵分個人、公會與最高傷害等欄，具體道具尚未對到名稱，待補。"))
    add(p_html("更完整的官方規則如下。"))
    add(quote_block(official_text("alliance_boss_rule"), terms))
    add("    </section>")

    # 榮譽試煉
    add('    <section id="honor-trial">')
    add(f"      <h2>{H(honor, terms)}</h2>")
    corps = [named(r, ("corps_name",)) or "遊戲中文名稱表沒有對應名稱" for r in honor_groups]
    type_h = Counter(r.get("type") for r in honor_groups)
    add(p_html(
        f"功能官方名稱是「{H(honor, terms)}」。官方文案包括"
        f"「{H(T('Raid_BattaleField_09'), terms)}」、「{H(T('Raid_BattaleField_13'), terms)}」、"
        f"「{H(T('Raid_BattaleField_10'), terms)}」、「{H(T('Raid_BattaleField_warning'), terms)}」。"
        f"分組表有 {fmt_int(len(honor_groups))} 筆，軍團名為："
        + "、".join(H(n, terms) for n in corps)
        + f"。其中一類 {fmt_int(type_h.get(1, 0))} 筆、另一類 {fmt_int(type_h.get(2, 0))} 筆。"
        "完整關卡層數與獎勵不在這張分組表，待補。"
    ))
    add("    </section>")

    # 虛空寶庫
    add('    <section id="void-vault">')
    add(f"      <h2>{H(void, terms)}</h2>")
    treasure_names = Counter(named(r, ("name",)) or "遊戲中文名稱表沒有對應名稱" for r in treasure_groups)
    add(p_html(f"功能官方名稱是「{H(void, terms)}」。官方規則如下。這與"
              f"<a href=\"artifacts.html\">{H('秘寶', terms)}</a>有關，但不把本節寫成秘寶總表。"))
    add(quote_block(official_text("raid_battlefield_rules2"), terms))
    add(p_html(
        f"另有分組表 {fmt_int(len(treasure_groups))} 筆，名稱都是「{H(tower, terms)}」，"
        f"與功能名「{H(void, terms)}」用字不同，本頁不逕行等同為同一入口。"
    ))
    add("    </section>")

    # 其他已命名系統
    add('    <section id="named-battles">')
    add("      <h2>其他已命名系統</h2>")
    add(p_html(
        "下列都是表上或官方字串已具名的系統，用官方名稱分開寫。本頁不排哪個比較值得打。"
    ))
    alliance_raid_names = Counter(
        named(r, ("name", "difficulty_name", "name_key")) or "遊戲中文名稱表沒有對應名稱"
        for r in alliance_raid
    )
    add(p_html(
        f"「{H(T('race_alliance_underway_tab_battle', '同盟突襲'), terms)}」是官方頁籤名。"
        f"對應表有 {fmt_int(len(alliance_raid))} 筆，名稱是："
        + "、".join(f"「{H(n, terms)}」{fmt_int(c)} 筆" for n, c in alliance_raid_names.most_common())
        + "。"
    ))
    add(p_html(
        f"「{H(T('race_activity_title_advance', '公會突襲'), terms)}」是另一個官方名稱。"
        "官方說明寫它將發生在賽季地圖中，與「同盟突襲」、「馴龍訓練場」不是同一個名稱。"
        f"細節不在本頁展開，賽季地圖見{link('kingdom-clash.html', '王國對決', terms)}。"
    ))
    add(p_html(
        f"「{H('要塞突襲', terms)}」見說明標題「{H(T('UI_Title_071'), terms)}」。"
        f"據點表有 {fmt_int(len(fort_raid))} 筆，官方名稱為「要塞3A」一類編號"
        f"（{fmt_int(len({r.get('fort_name') for r in fort_raid}))} 個名稱鍵，部分重複使用）。"
        f"事件表 {fmt_int(len(fort_event))} 筆，分組表 {fmt_int(len(fort_group))} 筆。本頁不展開座標。"
    ))
    card_names = Counter(named(r, ("name", "name_key")) or "遊戲中文名稱表沒有對應名稱" for r in card_raid)
    add(p_html(
        f"卡牌關卡表有 {fmt_int(len(card_raid))} 筆，名稱都是「"
        + "」「".join(H(n, terms) for n, _c in card_names.most_common())
        + "」。遊戲中文名稱表沒有「卡牌突襲」這個總名，本頁只用表上的官方名稱。"
    ))
    add(p_html(
        f"另有一張 {fmt_int(len(activity_raid))} 筆的挑戰表，難度數字 1 與 2 各 "
        f"{sum(1 for r in activity_raid if r.get('difficulty') == 1)} 筆，表上沒有關卡中文名。"
        "遊戲中文名稱表沒有給這張表單獨的系統總名，本頁不編造。"
    ))
    dark_names = Counter(named(r, ("difficulty_name",)) or "遊戲中文名稱表沒有對應名稱" for r in dark_legion)
    add(p_html(
        f"挑戰表有 {fmt_int(len(dark_legion))} 筆，分成 {fmt_int(len({r.get('group') for r in dark_legion}))} 組。"
        "難度名稱是："
        + "、".join(f"「{H(n, terms)}」{fmt_int(c)} 筆" for n, c in dark_names.most_common())
        + "。遊戲中文名稱表沒有這張表的系統總名，本頁不編造。"
    ))
    add(p_html(
        f"「{H(T('worm_boss_name', '沙漠暴君'), terms)}」表有 {fmt_int(len(worm_boss))} 筆，名稱皆為這個官方名。"
    ))
    click_names = unique_keep_order([
        named(r, ("monster_name",)) for r in click_monsters if named(r, ("monster_name",))
    ])
    add(p_html(
        f"點擊類怪物表有 {fmt_int(len(click_monsters))} 筆，已具名者包括："
        + "、".join(H(n, terms) for n in click_names)
        + "。"
    ))
    add(p_html(
        f"另有 {fmt_int(len(multi_boss))} 筆沒有官方中文名稱的合作關卡表，本頁不編造名稱。"
    ))
    tower_types = Counter(r.get("tower_type") for r in arena_pve)
    show_floors = [r.get("show_floor") for r in arena_pve if r.get("show_floor") not in (None, -1, "-1")]
    add(p_html(
        f"另有一張 {fmt_int(len(arena_pve))} 筆的爬塔表，分成 4 組（"
        + "／".join(fmt_int(tower_types.get(i, 0)) for i in range(1, 5))
        + f" 筆），可見層數寫到 {fmt_int(max(show_floors) if show_floors else 0)}。"
        "設定規則是編碼數字，本頁不自行翻譯，也不把它寫成功能「挑戰賽」的已核對主表。"
    ))
    add("    </section>")

    # 懸賞
    add('    <section id="bounty">')
    add(f"      <h2>{H(bounty, terms)}</h2>")
    add(p_html(
        f"功能「{H(bounty, terms)}」與「{H(world, terms)}」同樣在建造"
        f"{link('city-buildings.html', hall, terms)}後開啟。"
        f"任務表有 {fmt_int(len(bounty_tasks))} 筆。名稱去重後如下。其中 "
        f"{sum(1 for r in bounty_tasks if r.get('name_desc') == 'bounty_task_name_09')} 筆的名稱鍵在遊戲中文名稱表沒有對應名稱，"
        "不把它們與「邪惡煉金術師」合併。"
        f"「{H(T('pet_egg_04', '野外寵物'), terms)}」與寵物蛋有關，見{link('pets.html', '寵物總表', terms)}。"
        "世界地圖快捷說明三種："
        + "、".join(f"「{H(T(k), terms)}」" for k in ("bounty_fun_des_19", "bounty_fun_des_20", "bounty_fun_des_21"))
        + "。"
    ))
    bounty_name_counts = Counter()
    missing_bounty = 0
    for r in bounty_tasks:
        key = r.get("name_desc")
        if key and has_string(key):
            bounty_name_counts[T(str(key))] += 1
        else:
            missing_bounty += 1
            bounty_name_counts["遊戲中文名稱表沒有對應名稱"] += 1
    add(table(
        ["名稱", "筆數"],
        [[H(name, terms), fmt_int(count)] for name, count in bounty_name_counts.most_common()],
        caption="懸賞任務名稱",
    ))
    add(p_html("官方說明原文："))
    add(quote_block(official_text("UI_Bounty_011"), terms))
    add(p_html(
        f"聲望表有 {fmt_int(len(bounty_prestige))} 筆（第 1 至第 {fmt_int(len(bounty_prestige))} 檔）。"
        "回復時間全表為 28800，表上未標單位，不換算。"
        "第 1 檔與第 21 至 30 檔沒有寫入獎勵編號；第 2 至 20 檔寫有獎勵編號，尚未對到道具名稱，待補。"
        f"世界地圖快捷界面表有 {fmt_int(len(bounty_ui))} 筆。"
        "本頁不把懸賞任務排優先，也不計算體力與聲望划不算。"
    ))
    add(table(
        ["檔次", "任務數", "可累積上限", "回復數量", "回復時間", "獎勵"],
        [
            [
                fmt_int(r.get("id")),
                fmt_int(r.get("task_num")),
                fmt_int(r.get("task_max_num")),
                fmt_int(r.get("task_recover_num")),
                fmt_int(r.get("task_recover_time")),
                "沒有寫入獎勵編號" if r.get("reward") in (-1, "-1", None) else "獎勵編號待補",
            ]
            for r in bounty_prestige
        ],
        caption="懸賞聲望檔",
    ))
    add("    </section>")

    # 賽季預告
    add('    <section id="season-preview">')
    add("      <h2>賽季預告原文</h2>")
    preview_groups = Counter(r.get("group") for r in previews)
    add(p_html(
        f"官方預告表有 {fmt_int(len(previews))} 筆，分成 {fmt_int(len(preview_groups))} 組、每組 7 天。"
        "這是官方預告，不是本頁的攻略結論，也不據此標哪些內容已上線。"
        "此表沒有以潮汐之怒之後的官方賽季標題為名的第 5、第 6 組，不補造季號。"
    ))
    group_title = {}
    for r in previews:
        if r.get("day") == 7:
            group_title[r.get("group")] = T(str(r.get("title")), str(r.get("title") or ""))
    for g in sorted(preview_groups):
        heading = group_title.get(g) or f"第 {g} 組"
        add(f"      <h3>{H(heading, terms)}</h3>")
        rows = sorted((r for r in previews if r.get("group") == g), key=lambda x: x.get("day") or 0)
        lines = []
        for r in rows:
            title = T(str(r.get("title")), str(r.get("title") or ""))
            body = T(str(r.get("text"))) if r.get("text") and has_string(r.get("text")) else ""
            lines.append([fmt_int(r.get("day")), H(title, terms), body])
        add(table(["日", "標題", "預告原文"], lines, caption=heading))
    enc_names = Counter()
    nameless_enc = 0
    for r in encounters:
        label = named(r, ("name",))
        if label:
            enc_names[label] += 1
        else:
            nameless_enc += 1
    add(p_html(
        f"賽季遭遇表另有 {fmt_int(len(encounters))} 筆，已讀到的官方名稱包括："
        + "、".join(f"「{H(n, terms)}」{fmt_int(c)} 筆" for n, c in enc_names.most_common())
        + (f"；另有 {fmt_int(nameless_enc)} 筆遊戲中文名稱表沒有對應名稱。" if nameless_enc else "。")
        + "本頁不展開遭遇細節。"
    ))
    add("    </section>")

    # 本頁未列入
    add('    <section id="out-of-scope">')
    add("      <h2>本頁未列入</h2>")
    trade_names = unique_keep_order([
        named(r, ("name", "name_key")) or "" for r in trading_pve
    ])
    trade_names = [n for n in trade_names if n]
    add(p_html(
        f"功能「{H(T('function_name_51', '商隊'), terms)}」見"
        f"{link('caravan-trade.html', '商隊貿易', terms)}。"
        + (
            f"貿易相關表 {fmt_int(len(trading_pve))} 筆，名稱皆為「{H(trade_names[0], terms)}」。"
            if trade_names else ""
        )
        + f"功能「{H(T('showname_318', '祕境派遣'), terms)}」的派遣活動表有 {fmt_int(len(dispatch))} 筆，細節不在本頁展開。"
        f"功能「{H(T('function_name_68', '滅火'), terms)}」尚未對到唯一玩法表，本頁不編造規則。"
        f"功能「{H(T('function_name_113', '挑戰賽'), terms)}」、「{H(T('function_name_114', '積分賽'), terms)}」、"
        f"「{H(T('tvt_rank_function_name', '天梯賽'), terms)}」、「{H(T('s2_peak_name', '巔峰積分賽'), terms)}」"
        "的對戰規則見"
        + link(
            "arena-ladder.html",
            f"{T('function_name_114', '積分賽')}、{T('function_name_113', '挑戰賽')}、{T('tvt_rank_function_name', '天梯賽')}、{T('s2_peak_name', '巔峰積分賽')}",
            terms,
        )
        + "。"
        f"功能「{H(T('function_name_206', '七日獎勵'), terms)}」、「{H('王國遷移', terms)}」與合服見"
        + link("seven-reward-move.html", f"{T('function_name_206', '七日獎勵')}、王國遷移", terms)
        + "。"
        f"「{H(T('activity_name_5001003') or '摸魚時光', terms)}」、魚缸、抓蝴蝶、牧場物語、精靈小屋、守護魔獸、帕魯見既有圖鑑頁。"
    ))
    add("    </section>")

    add('    <section id="notes">')
    add("      <h2>資料說明</h2>")
    add(p_html(notes_source_intro()))
    add("<ul>")
    add(
        "<li>手冊第 7 章是章節提綱。數值、名稱與條件以 2026-11-22 LocalLow 表與字串表為準；"
        "現行 <code>/workspace/topheroes/data/</code> 與該批解壓檔在本頁用到的表上全文相同。"
        "字串表沒有「無限關」或「無限層」這一功能名；手冊以此作節名，可見正文改用界面標題「關卡進度 {0}/{1}」與「本層大獎」。"
        "聲望表第 2 至 20 檔的 <code>reward</code> 並非全為 −1，可見正文已依現行表改正。</li>"
    )
    add(
        "<li>可見正文不寫原始欄位名。<code>map_stage</code> 的 <code>type</code> 計數為 "
        f"1：{t1}、2：{t2}、3：{type_counts.get(3, 0)}、4：{type_counts.get(4, 0)}、6：{type_counts.get(6, 0)}。"
        f"<code>activity_infinite_floor</code> 各組開頭獎勵編號為 "
        + "、".join(f"group {g}：{first_rewards.get(g)}" for g in sorted(first_rewards))
        + "。<code>bounty_task_name_09</code> 20 筆沒有字串；相近的 <code>bounty_task_name_9</code> 是「邪惡煉金術師」，不合併。"
        "現行包沒有 <code>bounty_refresh_quality.json</code>。"
        "參與條件原文寫「文化大廳」，城建名稱表沒有完全相同的「文化大廳」條目，本頁不把它對成其他大廳名。</li>"
    )
    for name, sha in TABLE_SHA256.items():
        add(f"<li><code>{e(name)}</code> SHA-256 <code>{sha}</code>。</li>")
    add("</ul>")
    add("    </section>")

    body = "\n".join(parts)
    html = page_shell(page_title, summary, body, depth=0, nav_current="codex")
    return footer_swap(html)


def render_pve_page() -> str:
    return render_html()
