"""Locked presentation and page-only prose that does not come from tables.

Second-group tags, talent percentage conversion, recommended gear, and
community notes are listed here only when the player has confirmed them.
Do not invent second-group tags or extend the 審判官 ÷100 talent lock.
"""

from __future__ import annotations

# First public build: TOC + these two hero entries.
PUBLISH_IDS = [10031, 10027]

# Heroes that already have a generated page (for internal links only).
PAGE_IDS = set(PUBLISH_IDS)

HERO_OVERRIDES = {
    10031: {
        "second_tags": ["持續", "增益"],
        # Portraits reserved on the template; do not publish lead art for now.
        "role_blurb": "前排坦克，用護盾和減傷幫隊伍撐傷害",
        "pronoun": "他",
        "talent_percent": True,
        "talent_note_extra": {3: "與蠻鬥士同一條；與套裝如何疊加尚未驗證"},
        "gear": {
            "rows": [
                ("目前可用", "凱旋之歌或雷霆庇護"),
                ("過渡", "品質 5 用大地的守護者"),
                ("後期", "血之怒（未開放）"),
                ("備選", "聖光祝福只作輔助向備選，不改主線"),
            ],
            "why": "為什麼選這套*：信仰之盾等依最大生命吸收傷害；專武審判帶來公正領域；英靈是誓約之獅；天賦槽 3 是格擋（與套裝如何疊加尚未驗證）。英雄屬性是坦克、持續、增益，其中坦克的效果是受到傷害-5%。聖光祝福只作輔助向備選，不改這條主線。",
            "extra": "凱旋之歌 4 件寫明「坦克英雄裝備時效果提升 600%」，與第一組「坦克」相符，但客戶端是否只認這一欄尚未驗證。完整傷害結算順序也尚未驗證。後期血之怒依玩家確認尚未開放。套裝效果詳見裝備圖鑑（本靜態站尚未搬入圖鑑分冊）。",
        },
        "community": "社群幾乎公認的聯盟核心前排，減傷、護盾、後期無敵等描述很常見，多數後期陣都會留他。",
    },
    10027: {
        "second_tags": ["增益", "個體"],
        # No 前服 portrait on the box; the template still reserves a slot.
        "role_blurb": "治療英雄，用治療和護盾幫隊伍抬血",
        "pronoun": "她",
        "talent_percent": False,
        "gear": {
            "rows": [
                ("目前可用", "生命之力"),
                ("後期", "騎士榮光（未開放）"),
                ("備選", "冠軍的英姿或聖光祝福只當必殺向備選，不改主線"),
            ],
            "why": "為什麼選這套*：治療術、治癒祈福、神之恩典對得上生命之力 4 件「釋放治療技能」加護盾（生命之力冷卻 18 秒，不是每次治療都觸發）。光輝讚美詩、光輝聖歌不是治療技能，故冠軍的英姿或聖光祝福只當必殺向備選。專武恩賜的護盾與生命之力護盾如何疊加尚未驗證。後期騎士榮光的攻擊有助於依攻擊計算的治療量；技能增傷會不會進治療尚未驗證。英雄屬性是治療、增益、個體，其中治療的效果是治療效果+5%；增益、個體的官方說明沒有再加百分比。",
            "extra": "套裝效果詳見裝備圖鑑（本靜態站尚未搬入圖鑑分冊）。",
        },
        "community": "後期聯盟陣仍常見的後排治療，負責抬血和減傷。第六人爭議裡，她是常被保留的人選之一。",
    },
}

# Shared glossary used for 專有名詞 highlighting, plus per-page names.
# Longer terms win. Do not typo 薔薇 as 蔷薇. Do not write 契約之獅 or 壁克.
COMMON_TERMS = [
    "Top Heroes X 馴龍高手聯名限定",
    "進行帕魯捕捉時，紅水晶採集速度提升",
    "礦脈爭奪戰魔晶產量增加",
    "審判·不敗戰神【I】",
    "審判·不敗戰神【II】",
    "修女·智慧女神【Ⅲ】",
    "修女·智慧女神【Ⅳ】",
    "修女·智慧女神【II】",
    "修女·智慧女神【I】",
    "薔薇公主·曇花月影",
    "修女·純潔之戀",
    "審判·狂熱之愛",
    "審判官·傑克船長",
    "審判官·王國隊長",
    "審判官·暴飛飛",
    "審判官·覺醒",
    "審判·不敗戰神",
    "審判·殘月騎士",
    "修女·南瓜女巫",
    "修女·智慧女神",
    "修女·巫女",
    "修女·光明",
    "修女·覺醒",
    "聯盟英雄增傷",
    "護盾值提升",
    "英雄等級上限",
    "暴擊傷害減免",
    "英雄治療率",
    "治療效果",
    "受到傷害",
    "最終傷害",
    "生命上限",
    "所有士兵攻擊",
    "所有士兵生命",
    "收集屬性",
    "裝備屬性",
    "永恆之戀",
    "海皇霸主",
    "不朽王座",
    "出征上限",
    "技能減傷",
    "技能增傷",
    "英雄攻擊",
    "英雄生命",
    "雲海紀行",
    "時裝幣",
    "抗暴",
    "暴擊",
    "信仰之盾",
    "守護戒律",
    "神聖秩序",
    "禁軍之盾",
    "公正領域",
    "雄獅血脈",
    "進攻戰略",
    "持久策略",
    "格擋研究",
    "大地的守護者",
    "凱旋之歌",
    "雷霆庇護",
    "聖光祝福",
    "血之怒",
    "世界樹之影",
    "冰封之焰",
    "暮光之戰",
    "觀星學士",
    "薔薇公主",
    "發明家",
    "聖徒",
    "光輝讚美詩",
    "光輝聖歌",
    "治癒祈福",
    "神聖聯盟",
    "神聖武裝",
    "神聖恩賜",
    "神之恩典",
    "治療術",
    "治療增效",
    "生命之力",
    "騎士榮光",
    "冠軍的英姿",
    "誓約之獅",
    "吟遊詩人",
    "守秘人",
    "火法師",
    "審判官",
    "主教",
    "統禦",
    "修女",
    "聯盟",
    "坦克",
    "持續",
    "增益",
    "治療",
    "個體",
    "不屈",
    "永恆",
    "審判",
    "恩賜",
    "格擋",
]

SEASON_LABEL = {
    "0-99": "未標具體賽季名稱",
    "0-0": "未標具體賽季名稱",
    "1-1": "S1 世界樹之影",
    "2-2": "S2 冰封之焰",
    "3-99": "S3 暮光之戰及之後",
}

# Rec list wording on published pages; keep the cutoff that matches the tables.
REC_CUTOFF_NOTE = "此資料截到 2026-11-05，表內沒有以 S4、S5、S6 為名的聯盟推薦更新。"
