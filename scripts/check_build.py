#!/usr/bin/env python3
"""Sanity-check the built index and published alliance hero pages against locked rules."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
JUDGE = DOCS / "heroes" / "10031.html"
NUN = DOCS / "heroes" / "10027.html"
ROSE = DOCS / "heroes" / "10043.html"
INVENTOR = DOCS / "heroes" / "10050.html"
INDEX = DOCS / "index.html"


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = re.sub(r"[ \t\r\n]+", " ", t)
    return t


def fail(msg, errors):
    errors.append(msg)



# Locked homepage roster (handbook 01–03 名單總覽 order and wording).
LEAGUE_NAMES = [
    "薔薇公主", "審判官", "發明家", "聖徒", "主教", "修女", "守秘人", "火法師",
    "吟遊詩人", "觀星學士", "牧師", "騎士", "遊俠", "牧羊人", "老闆娘", "鈴蘭女僕",
    "戰士", "老法師", "15032", "15033",
]
NATURE_NAMES = [
    "豪士", "中壇元帥", "花藝師", "森之少女", "妖精", "喚潮使", "樹人守衛", "賢者",
    "風行者", "德魯伊", "舞孃", "尋路者", "祭司", "守望者", "石匠", "大冒險家",
    "弓箭手", "藥劑師",
]
TRIBE_NAMES = [
    "沙漠王子", "馴獸師", "行者", "通靈師", "女巫", "風暴聖女", "蠻鬥士", "劍術教官",
    "荒野獵手", "術士", "薩滿", "盜賊", "罪犯", "鬥者", "獵人", "暗影牧師",
    "鐵匠", "護衛", "15039",
]
CODEX_ITEMS = [
    "專武", "英靈", "造型", "裝備", "領主裝備", "士兵", "秘寶", "寵物", "符文",
    "天賦", "科技", "裝飾物", "城堡外觀",
]
GAMEPLAY_TERMS = ("開局", "陣容與羈絆", "PVE", "PVP", "KVK")
STALE_DEPLOY = ("GitHub Pages 公開部署尚未進行", "公開部署還沒做")


def section_html(html: str, section_id: str) -> str | None:
    m = re.search(
        rf'<section\b[^>]*\bid="{re.escape(section_id)}"[^>]*>(.*?)</section>',
        html,
        flags=re.S,
    )
    return m.group(1) if m else None


def li_texts(block: str) -> list[str]:
    out = []
    for li in re.findall(r"<li\b[^>]*>(.*?)</li>", block, flags=re.S):
        t = re.sub(r"<[^>]+>", "", li)
        t = t.replace("&nbsp;", " ").replace("&amp;", "&")
        t = re.sub(r"[ \t\r\n]+", " ", t).strip()
        if t:
            out.append(t)
    return out


def core_name(item: str) -> str:
    t = item.replace("尚未公開", "").strip()
    t = re.sub(r"（未開放）\s*$", "", t).strip()
    return t


def check_index(index: str, it: str, errors: list[str]) -> None:
    nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', index, flags=re.S)
    if not nav_m:
        fail("index: missing site-nav", errors)
        nav = ""
    else:
        nav = nav_m.group(0)
        for label, href in (
            ("首頁", "index.html"),
            ("英雄", "index.html#heroes"),
            ("聯盟", "index.html#faction-league"),
            ("自然", "index.html#faction-nature"),
            ("部族", "index.html#faction-tribe"),
            ("圖鑑", "index.html#codex"),
            ("關於本站", "index.html#about"),
        ):
            if href not in nav or label not in nav:
                fail(f"index nav missing {label} -> {href}", errors)
        if re.search(r"heroes/\d+\.html", nav):
            fail("index site-nav should not link individual hero pages", errors)

    if 'id="heroes"' not in index or ">英雄<" not in index:
        fail("index: missing 英雄 section", errors)

    expected = {
        "faction-league": LEAGUE_NAMES,
        "faction-nature": NATURE_NAMES,
        "faction-tribe": TRIBE_NAMES,
    }
    counts = {"faction-league": 20, "faction-nature": 18, "faction-tribe": 19}
    for sid, names in expected.items():
        block = section_html(index, sid)
        if block is None:
            fail(f"index: missing section {sid}", errors)
            continue
        got = [core_name(x) for x in li_texts(block)]
        if got != names:
            fail(f"index {sid}: roster mismatch {got!r}", errors)
        if len(got) != counts[sid]:
            fail(f"index {sid}: expected {counts[sid]} names, got {len(got)}", errors)

    # Only published hero pages may be linked from the index body.
    hero_hrefs = re.findall(r'href="([^"]*heroes/\d+\.html)"', index)
    published = [
        10043, 10031, 10050, 10033, 10046, 10027, 10018, 10025, 10030, 10024,
        10003, 10004, 10014, 10029, 10032, 10053, 10001, 10006, 15032, 15033,
    ]
    allowed = {f"heroes/{hid}.html" for hid in published}
    got_hrefs = set()
    for href in hero_hrefs:
        tail = href.rsplit("/", 2)
        norm = "/".join(tail[-2:]) if len(tail) >= 2 else href
        got_hrefs.add(norm)
    if got_hrefs != allowed:
        fail(f"index: hero links should be all published alliance pages, got {sorted(got_hrefs)}", errors)
    if 'href="heroes/10043.html"' not in index or "薔薇公主" not in it:
        fail("index: 薔薇公主 should be a real link to heroes/10043.html", errors)
    if 'href="heroes/10050.html"' not in index or "發明家" not in it:
        fail("index: 發明家 should be a real link to heroes/10050.html", errors)
    if 'href="heroes/10029.html"' not in index or "牧羊人（未開放）" not in it:
        fail("index: 牧羊人（未開放） should be a real link to heroes/10029.html", errors)
    if 'href="heroes/10032.html"' not in index or "老闆娘" not in it:
        fail("index: 老闆娘 should be a real link to heroes/10032.html", errors)
    if 'href="heroes/15032.html"' not in index or 'href="heroes/15033.html"' not in index:
        fail("index: 15032 and 15033 should be real links", errors)
    # Published heroes must not still be marked 尚未公開 now that the pages exist.
    league = section_html(index, "faction-league") or ""
    for item in li_texts(league):
        if "尚未公開" in item:
            fail(f"index: published league entry should not be marked 尚未公開: {item}", errors)
    # Nature / tribe / unbuilt ids must not be wrapped in an anchor.
    for hid in ("10007", "15039", "10036", "10042", "10039", "10037"):
        if re.search(rf'href="[^"]*{hid}\.html"', index):
            fail(f"index: should not link unbuilt hero {hid}", errors)

    if "牧羊人（未開放）" not in it:
        fail("index: 牧羊人 should be labelled 未開放", errors)
    # The 牧羊人 list item must not also say 尚未公開.
    league = section_html(index, "faction-league") or ""
    for item in li_texts(league):
        if "牧羊人" in item and "尚未公開" in item:
            fail("index: 牧羊人 should not also be marked 尚未公開", errors)
        if "老闆娘" in item and "未開放" in item:
            fail("index: 老闆娘 must not be marked 未開放", errors)

    nature = section_html(index, "faction-nature") or ""
    nature_cores = [core_name(x) for x in li_texts(nature)]
    if "藥劑師" not in nature_cores:
        fail("index: 藥劑師 should be listed under 自然", errors)
    if "玩家確認" in it or "由玩家確認" in it:
        fail("index: must not mention 玩家確認", errors)

    for bad in ("蕊薇", "蔷薇", "遊俺", "舞嬢", "蠾鬥士", "契約之獅", "壁克"):
        if bad in index:
            fail(f"index: typo or wrong term {bad}", errors)
    if "薔薇公主" not in it or "遊俠" not in it or "舞孃" not in it or "蠻鬥士" not in it:
        fail("index: missing correct names 薔薇公主 / 遊俠 / 舞孃 / 蠻鬥士", errors)

    codex = section_html(index, "codex")
    if codex is None:
        fail("index: missing 圖鑑 section", errors)
    else:
        items = li_texts(codex)
        if items != CODEX_ITEMS:
            fail(f"index 圖鑑 items mismatch {items!r}", errors)
        if re.search(r"<a\b", codex):
            fail("index 圖鑑 placeholders must not have links", errors)

    for term in GAMEPLAY_TERMS:
        if term in it:
            fail(f"index: should not include gameplay category {term}", errors)
    for phrase in STALE_DEPLOY:
        if phrase in index:
            fail(f"index: stale wording still present: {phrase}", errors)

    if "官方 wiki" in it and "不是官方" not in it:
        fail("index: must not call this an official wiki", errors)

    # Private handbook / Canvas links must not appear on the public index.
    if re.search(r"cursor\.com|canvas/|Cursor Page|私人手冊", index, flags=re.I):
        fail("index: must not link private handbook or Canvas pages", errors)

    about = section_html(index, "about") or ""
    about_t = text_of(about)
    for jargon in ("資料表", "樣板", "換算規則", "鎖定呈現", "靜態站", "稱號百分比"):
        if jargon in about_t:
            fail(f"index 關於本站 still too technical: {jargon}", errors)
    if "不是官方" not in about_t:
        fail("index 關於本站 should say this is not official", errors)
    if "目前聯盟英雄的條目都已公開" not in it and "目前聯盟英雄條目都已公開" not in it:
        fail("index lede should say all alliance hero pages are published", errors)
    if "目前先公開薔薇公主、審判官、發明家和修女" in it:
        fail("index lede still only lists the first four published heroes", errors)
    if "自然" not in it or "部族" not in it:
        fail("index lede should still mention 自然 and 部族 as upcoming", errors)



PUBLISHED_IDS = [
    10043, 10031, 10050, 10033, 10046, 10027, 10018, 10025, 10030, 10024,
    10003, 10004, 10014, 10029, 10032, 10053, 10001, 10006, 15032, 15033,
]

EXPECTED_TAGS = {
    10033: ("傷害、爆發、群體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成群體傷害"], "後兩項沒有百分比"),
    10046: ("傷害、爆發、控制", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "能夠對敵人造成控制"], "後兩項沒有百分比"),
    10018: ("坦克、控制、增益", "受到傷害-5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項沒有百分比"),
    10025: ("傷害、爆發、群體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成群體傷害"], "後兩項沒有百分比"),
    10030: ("輔助、增益、群體", "生命上限+5%", ["能夠為隊友提供加強效果", "專注於造成群體傷害"], "後兩項沒有百分比"),
    10024: ("傷害、爆發、個體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成個體傷害"], "後兩項沒有百分比"),
    10003: ("治療、增益", "治療效果+5%", ["能夠為隊友提供加強效果"], "後項沒有百分比"),
    10004: ("坦克、控制", "受到傷害-5%", ["能夠對敵人造成控制"], "後項沒有百分比"),
    10014: ("傷害、增益", "最終傷害+3%", ["能夠為隊友提供加強效果"], "後項沒有百分比"),
    10032: ("坦克、控制、群體", "受到傷害-5%", ["能夠對敵人造成控制", "專注於造成群體傷害"], "後兩項沒有百分比"),
    10053: ("輔助、控制、增益", "生命上限+5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項沒有百分比"),
    10001: ("傷害、持續", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰"], "後項沒有百分比"),
    10006: ("傷害、群體", "最終傷害+3%", ["專注於造成群體傷害"], "後項沒有百分比"),
}

NO_SECOND_IDS = {10029, 15032, 15033}

OPEN_IDS = {10018, 10025, 10030, 10024, 10003, 10004, 10014, 10001, 10006}

GEAR_MAIN = {
    10033: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10046: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10018: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10025: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10030: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10024: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10003: ("生命之力", "騎士榮光"),
    10004: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10014: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10029: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10032: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10053: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10001: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10006: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    15032: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    15033: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
}

NAMES = {
    10033: "聖徒", 10046: "主教", 10018: "守秘人", 10025: "火法師", 10030: "吟遊詩人",
    10024: "觀星學士", 10003: "牧師", 10004: "騎士", 10014: "遊俠", 10029: "牧羊人",
    10032: "老闆娘", 10053: "鈴蘭女僕", 10001: "戰士", 10006: "老法師",
    15032: "15032", 15033: "15033",
}

TYPOS = ("蔷薇", "蕊薇", "遊俺", "舞嬢", "蠾鬥士", "契約之獅", "壁克", "鈴蘭女仆", "老板娘", "突破防御", "驯龙高手", "不朽王坐")


def check_new_league_pages(errors: list[str]) -> None:
    pages = {}
    texts = {}
    for hid in PUBLISHED_IDS:
        path = DOCS / "heroes" / f"{hid}.html"
        if not path.exists():
            fail(f"missing {path}", errors)
            continue
        html = path.read_text(encoding="utf-8")
        pages[hid] = html
        texts[hid] = text_of(html)

    new_ids = [hid for hid in PUBLISHED_IDS if hid not in {10043, 10031, 10050, 10027}]
    for hid in new_ids:
        html = pages.get(hid)
        if not html:
            continue
        vt = texts[hid]
        label = NAMES[hid]
        if 'lang="zh-Hant"' not in html:
            fail(f"{label}: missing lang=zh-Hant", errors)
        if "稱號屬性" in vt:
            fail(f"{label}: used 稱號屬性 instead of 英雄屬性", errors)
        if "英雄屬性" not in vt:
            fail(f"{label}: missing 英雄屬性 label", errors)
        if "頭像（待補）" not in html:
            fail(f"{label}: missing portrait placeholder 頭像（待補）", errors)
        if hid in OPEN_IDS:
            if "已開放" not in vt:
                fail(f"{label}: hide=-1 should say 已開放", errors)
        else:
            if "見資料說明" not in vt:
                fail(f"{label}: hide=1 status should be 見資料說明", errors)
            # 牧羊人 page status is not announced as 未開放 from hide; index label is separate.
            if hid != 10029 and re.search(r"已開放", section_html(html, "lead") or ""):
                fail(f"{label}: hide=1 must not be announced as 已開放", errors)
        if hid in EXPECTED_TAGS:
            tags, locked, decs, pct_note = EXPECTED_TAGS[hid]
            if tags not in vt:
                fail(f"{label} tags should be {tags}", errors)
            if locked not in vt:
                fail(f"{label} missing locked {locked}", errors)
            for dec in decs:
                if dec not in vt:
                    fail(f"{label} missing official description {dec}", errors)
            if pct_note not in vt or "玩家確認面板" not in vt:
                fail(f"{label} should note second-group has no percentage and is panel-confirmed", errors)
        if hid in NO_SECOND_IDS:
            if "第二組標籤尚未經玩家面板確認，本頁不推算" not in vt:
                fail(f"{label} should say second-group tags are unconfirmed and not inferred", errors)
            # Must not invent a second-group pair.
            if re.search(r"英雄屬性是(?:輔助|坦克|傷害)[、，].{0,8}(?:爆發|持續|控制|增益|減益|召喚|個體|群體)", vt):
                fail(f"{label} must not invent second-group tags", errors)
        for piece in GEAR_MAIN.get(hid, ()):
            if piece not in vt:
                fail(f"{label} recommended gear missing {piece}", errors)
        if "（推算，不是官方最佳裝備）" in html:
            fail(f"{label} should not put 推算 note inline beside gear names", errors)
        for bad in TYPOS:
            if bad in html:
                fail(f"{label} typo or wrong term {bad}", errors)
        # Nature / tribe pages are not built; do not invent links.
        for other in ("10007", "10036", "10037", "10039", "10042", "15039"):
            if re.search(rf'href="[^"]*{other}\\.html"', html):
                fail(f"{label} should not invent a link to unbuilt hero {other}", errors)
        if hid in (15032, 15033):
            if f"<title>Top Heroes Wiki｜{hid}</title>" not in html:
                fail(f"{hid} title should use the id only, not an invented Chinese name", errors)
            if re.search(rf"<h1>[^<]*Top Heroes Wiki｜(?!{hid}<)", html):
                fail(f"{hid} heading should use the id only", errors)

    # Talent display: all non-point attrs use raw/100 with two decimals.
    # Quality-3 10103／10104 should show 90.00%／270.00%; slot 3 is also percent.
    q3_percent = [
        hid for hid in new_ids
        if hid not in {10003, 10004, 10014, 10001, 10006}
    ]
    for hid in q3_percent:
        vt = texts.get(hid, "")
        label = NAMES[hid]
        if "90.00%" not in vt or "270.00%" not in vt:
            fail(f"{label} slots with 所有士兵攻擊／生命 should show 90.00%／270.00%", errors)
        if "依已確認的前服天賦面板規則" not in vt or "不是本英雄自己的面板確認" not in vt:
            fail(f"{label} percent talents should cite the confirmed 前服 rule, not own-panel confirmation", errors)
        if "不曾用審判官面板的÷100 推算" in vt:
            fail(f"{label} must not say the locked ÷100 rule was not applied", errors)
    # Slot-3 (and similar) percent conversions that used to be left raw.
    for hid, needles in (
        (10032, ("1.33%", "40.00%")),
        (15032, ("1.33%", "40.00%")),
        (10053, ("1.00%", "30.00%")),
        (10024, ("1.67%", "50.00%")),
        (10029, ("1.00%", "30.00%")),
        (10004, ("1.00%", "30.00%")),
        (10014, ("1.00%", "30.00%")),
        (10018, ("1.67%", "50.00%")),
        (10030, ("1.33%", "40.00%")),
        (10033, ("0.67%", "20.00%")),
        (10046, ("0.67%", "20.00%")),
        (10025, ("0.67%", "20.00%")),
    ):
        vt = texts.get(hid, "")
        label = NAMES[hid]
        for needle in needles:
            if needle not in vt:
                fail(f"{label} talent should show converted {needle}", errors)
    # 牧師 1022 is a locked percent attr; slots 1／2 are 10103／10104 at cap 20.
    priest = texts.get(10003, "")
    if "1.00%" not in priest or "30.00%" not in priest:
        fail("牧師 傷兵治療速度 (1022) should show converted 1.00%／30.00%", errors)
    if "2.50%" not in priest or "50.00%" not in priest or "7.50%" not in priest or "150.00%" not in priest:
        fail("牧師 slots 1／2 should show converted 2.50%／50.00% and 7.50%／150.00%", errors)
    if "依已確認的前服天賦面板規則" not in priest:
        fail("牧師 percent talents should cite the confirmed 前服 rule", errors)
    # 騎士 slots 1／2 plus slot 3 士兵訓練速度 are all percent.
    knight = texts.get(10004, "")
    if "2.50%" not in knight or "50.00%" not in knight or "7.50%" not in knight or "150.00%" not in knight:
        fail("騎士 slots 1／2 should show converted 2.50%／50.00% and 7.50%／150.00%", errors)
    if "士兵訓練速度" not in knight:
        fail("騎士 missing 士兵訓練速度", errors)
    if "1.00%" not in knight or "30.00%" not in knight:
        fail("騎士 士兵訓練速度 should show converted 1.00%／30.00%", errors)
    ranger = texts.get(10014, "")
    if "2.50%" not in ranger or "50.00%" not in ranger or "7.50%" not in ranger or "150.00%" not in ranger:
        fail("遊俠 slots 1／2 should show converted 2.50%／50.00% and 7.50%／150.00%", errors)
    # 戰士／老法師 caps at 10.
    for hid in (10001, 10006):
        vt = texts.get(hid, "")
        label = NAMES[hid]
        if "2.00%" not in vt or "20.00%" not in vt or "6.00%" not in vt or "60.00%" not in vt:
            fail(f"{label} slots 1／2 should show converted 2.00%／20.00% and 6.00%／60.00%", errors)

    # Special cases
    saint = texts.get(10033, "")
    saint_html = pages.get(10033, "")
    if "不敗正義" not in saint or "聖靈天使" not in saint:
        fail("聖徒 missing 專武／英靈", errors)
    if "征服者（6 星解鎖技能）" not in saint_html and "6 星解鎖技能" not in saint:
        fail("聖徒 should unlock 征服者 at 6 stars", errors)
    if "神聖號令" in saint and "覺醒強化" in saint and "神聖號令（覺醒" in saint_html:
        fail("聖徒 神聖號令 must not be labelled as 覺醒", errors)
    if "資料表沒有" not in saint or "覺醒" not in saint:
        fail("聖徒 should state there is no 覺醒 in the tables", errors)
    if "聖徒·伊萊雯" not in saint:
        fail("聖徒 missing skin 聖徒·伊萊雯", errors)
    for needle in ("技能增傷+8.00%", "英雄攻擊+6.00%", "英雄生命+20.00%", "聯盟英雄減傷+2.00%"):
        if needle not in saint:
            fail(f"聖徒·伊萊雯 max-star collection should include {needle}", errors)
    eleven = section_html(pages.get(10033, ""), "skin-1003307") or ""
    eleven_t = text_of(eleven) if eleven else ""
    if eleven_t:
        if "英雄攻擊+3.00%" in eleven_t and "英雄攻擊+6.00%" not in eleven_t:
            fail("聖徒·伊萊雯 must not show only the star-tier 英雄攻擊+3.00%", errors)
        if "英雄生命+10.00%" in eleven_t and "英雄生命+20.00%" not in eleven_t:
            fail("聖徒·伊萊雯 must not show only the star-tier 英雄生命+10.00%", errors)
        if "表上另有一欄隊伍屬性" in eleven_t:
            fail("聖徒·伊萊雯 must not describe team_attr as a separate uncombined column", errors)

    bishop = texts.get(10046, "")
    if "光明聖契" not in bishop or "聖諭祭司" not in bishop:
        fail("主教 missing 專武／英靈", errors)
    if "戰爭使者" not in bishop or "11 星" not in bishop:
        fail("主教 missing 11-star 戰爭使者", errors)
    if "共用解鎖技能" not in bishop:
        fail("主教 戰爭使者 should be marked as a shared unlock skill", errors)

    maid = texts.get(10053, "")
    if "鈴蘭誓言" not in maid or "撫傷" not in maid:
        fail("鈴蘭女僕 missing 專武 鈴蘭誓言／撫傷", errors)
    if "鼓勵" not in maid or "11 星" not in maid:
        fail("鈴蘭女僕 missing 11-star 鼓勵", errors)

    shepherd_html = pages.get(10029, "")
    shepherd = texts.get(10029, "")
    exclusive = section_html(shepherd_html, "exclusive") or ""
    stars = section_html(shepherd_html, "star-skills") or ""
    if "資料表沒有專武列" not in text_of(exclusive) and "沒有專武" not in text_of(exclusive):
        fail("牧羊人 exclusive section should say there is no 專武", errors)
    if "諾亞金鈴" in text_of(exclusive):
        fail("牧羊人 must not list 諾亞金鈴 as their exclusive", errors)
    for skill in ("森林之歌", "春之祝福", "諾亞之聲"):
        if skill in text_of(stars):
            fail(f"牧羊人 star skills should not include {skill}", errors)
    if "第二組標籤尚未經玩家面板確認" not in shepherd:
        fail("牧羊人 should not invent second-group tags", errors)

    landlady_html = pages.get(10032, "")
    landlady = texts.get(10032, "")
    lex = section_html(landlady_html, "exclusive") or ""
    if "英雄絮語" in text_of(lex) or "專武專屬技能：乾杯" in landlady_html:
        fail("老闆娘 must not list 英雄絮語／乾杯 as her exclusive", errors)
    if "未開放" in (section_html(landlady_html, "lead") or "") :
        fail("老闆娘 must not be marked 未開放", errors)

    x32 = texts.get(15032, "")
    if "英雄絮語" not in x32 or "乾杯" not in x32:
        fail("15032 should have exclusive 英雄絮語／乾杯", errors)
    if "開懷暢飲" not in x32 or "旅店之魂" not in x32:
        fail("15032 missing awaken skills 開懷暢飲／旅店之魂", errors)
    if "覺醒：老闆娘" not in x32:
        fail("15032 should keep official awaken name 覺醒：老闆娘", errors)

    x33 = texts.get(15033, "")
    x33_html = pages.get(15033, "")
    if "號令萬軍" not in x33 or "天國之劍" not in x33:
        fail("15033 should include shared star skills with 聖徒", errors)
    if "6 星解鎖" in x33 and "征服者" in x33 and "6 星解鎖技能" in x33_html:
        fail("15033 must not copy 聖徒's 6-star unlock of 征服者", errors)
    if "覺醒表關聯技能" not in x33 or "神聖號令" not in x33 or "征服者" not in x33:
        fail("15033 should show 神聖號令 and 征服者 as 覺醒表關聯技能", errors)
    if "沙漠王子·覺醒" not in x33:
        fail("15033 should keep official skin name 沙漠王子·覺醒", errors)

    bard = texts.get(10030, "")
    if "愛神" not in bard or "愛情蛊惑" not in bard:
        fail("吟遊詩人 missing exclusive 愛神／愛情蛊惑", errors)
    if "專武「愛神」專屬技能" not in bard:
        fail("吟遊詩人 source table should label 愛情蛊惑 as 專武專屬技能", errors)
    if "愛情虫惑" in bard or "愛情蠱惑" in bard:
        fail("吟遊詩人 must keep official spelling 愛情蛊惑, not rewrite 蛊", errors)
    if "共鳴" in bard:
        fail("吟遊詩人 must not inherit 發明家 exclusive 共鳴", errors)

    # Rec cutoff preserved on official-rec heroes
    for hid in (10033, 10046, 10018, 10025, 10030, 10024):
        vt = texts.get(hid, "")
        if "此資料截到 2026-11-05，表內沒有以 S4、S5、S6 為名的聯盟推薦更新。" not in vt:
            fail(f"{NAMES[hid]} missing official rec cutoff note", errors)

    # display server number must not be claimed equal to internal id
    blob = "".join(texts.get(hid, "") for hid in new_ids)
    for hid in new_ids:
        tail = str(hid)[-2:] if hid < 15000 else str(hid)[-3:]
        if hid >= 15000:
            continue
        if re.search(rf"顯示.?{int(str(hid)[2:])}.{{0,12}}{hid}|{hid}.{{0,12}}顯示.?{int(str(hid)[2:])}", blob):
            fail(f"must not claim display number equals internal id {hid}", errors)


def main() -> int:
    errors = []
    for p in (INDEX, JUDGE, NUN, ROSE, INVENTOR):
        if not p.exists():
            fail(f"missing {p}", errors)
    if errors:
        print("\n".join(errors))
        return 1

    index = INDEX.read_text(encoding="utf-8")
    judge = JUDGE.read_text(encoding="utf-8")
    nun = NUN.read_text(encoding="utf-8")
    rose = ROSE.read_text(encoding="utf-8")
    inventor = INVENTOR.read_text(encoding="utf-8")
    jt, nt, rt, vt, it = text_of(judge), text_of(nun), text_of(rose), text_of(inventor), text_of(index)

    for html, label in ((index, "index"), (judge, "審判官"), (nun, "修女"), (rose, "薔薇公主"), (inventor, "發明家")):
        if 'lang="zh-Hant"' not in html:
            fail(f"{label}: missing lang=zh-Hant", errors)
        nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', html, flags=re.S)
        if not nav_m:
            fail(f"{label}: missing site-nav", errors)
        else:
            nav = nav_m.group(0)
            if re.search(r"heroes/\d+\.html", nav):
                fail(f"{label}: site-nav should not link individual hero pages", errors)
            for needle in ("#heroes", "#codex", "#about", "#faction-league", "#faction-nature", "#faction-tribe"):
                if needle not in nav:
                    fail(f"{label}: site-nav missing {needle}", errors)

    check_index(index, it, errors)

    # tags
    if "稱號屬性" in jt or "稱號屬性" in nt or "稱號屬性" in rt or "稱號屬性" in vt:
        fail("used 稱號屬性 instead of 英雄屬性", errors)
    if "英雄屬性" not in jt or "英雄屬性" not in nt or "英雄屬性" not in rt or "英雄屬性" not in vt:
        fail("missing 英雄屬性 label", errors)
    if "坦克、持續、增益" not in jt:
        fail("審判官 tags should be 坦克、持續、增益", errors)
    if "治療、增益、個體" not in nt:
        fail("修女 tags should be 治療、增益、個體", errors)
    if "受到傷害-5%" not in jt:
        fail("審判官 missing locked 受到傷害-5%", errors)
    if "治療效果+5%" not in nt:
        fail("修女 missing locked 治療效果+5%", errors)
    if "坦克" not in rt or "受到傷害-5%" not in rt:
        fail("薔薇公主 should show first-group 坦克 and 受到傷害-5%", errors)
    if "坦克、爆發、控制" not in rt:
        fail("薔薇公主 tags should be 坦克、爆發、控制", errors)
    if "坦克、持續" in rt or "坦克、增益" in rt:
        fail("薔薇公主 must not inherit 審判官 second-group tags", errors)
    if "尚未經玩家面板確認" in rt or "本頁不推算" in rt or "本頁不為她推算第二組英雄屬性" in rt:
        fail("薔薇公主 should no longer say second-group tags are unconfirmed", errors)
    if "偏向於使用技能在短時間內造成高額傷害" not in rt or "能夠對敵人造成控制" not in rt:
        fail("薔薇公主 missing official 爆發／控制 descriptions", errors)
    if "後兩項沒有百分比" not in rt or "玩家確認面板" not in rt:
        fail("薔薇公主 should note 爆發／控制 have no percentage and are panel-confirmed", errors)
    if "輔助、控制、增益" not in vt:
        fail("發明家 tags should be 輔助、控制、增益", errors)
    if "生命上限+5%" not in vt:
        fail("發明家 missing locked 生命上限+5%", errors)
    if "善於用技巧提供幫助，生命上限+5%" not in vt:
        fail("發明家 missing official 輔助 description", errors)
    if "能夠對敵人造成控制" not in vt or "能夠為隊友提供加強效果" not in vt:
        fail("發明家 missing official 控制／增益 descriptions", errors)
    if "後兩項沒有百分比" not in vt or "玩家確認面板" not in vt:
        fail("發明家 should note 控制／增益 have no percentage and are panel-confirmed", errors)
    if "坦克、持續" in vt or "治療、增益" in vt:
        fail("發明家 must not inherit 審判官 or 修女 tag sets", errors)

    # talents
    for s in ("90.00%", "270.00%", "30.00%", "3.00%", "9.00%", "1.00%"):
        if s not in jt:
            fail(f"審判官 talent missing {s}", errors)
    if "進攻戰略" not in jt or "持久策略" not in jt or "格擋研究" not in jt:
        fail("審判官 talent names missing", errors)
    if "已用面板確認" not in jt and "已用他自己的面板確認" not in jt:
        fail("審判官 talent notes should still say the values were panel-confirmed", errors)
    if "不是本英雄自己的面板確認" in jt:
        fail("審判官 must not be worded as if his percentages were only borrowed", errors)
    # 修女／薔薇公主／發明家: slots 1／2／4 still 90.00%／270.00%；
    # slot 3 (抗暴／治療增效) is now also 1.00%／30.00%.
    for label, body in (("修女", nt), ("薔薇公主", rt), ("發明家", vt)):
        if "90.00%" not in body or "270.00%" not in body:
            fail(f"{label} slots with 所有士兵攻擊／生命 should show 90.00%／270.00%", errors)
        if "1.00%" not in body or "30.00%" not in body:
            fail(f"{label} slot 3 should show converted 1.00%／30.00%", errors)
        if "依已確認的前服天賦面板規則" not in body or "不是本英雄自己的面板確認" not in body:
            fail(f"{label} percent talents should cite the confirmed 前服 rule, not own-panel confirmation", errors)
        if "不曾用審判官面板的÷100 推算" in body:
            fail(f"{label} must not say the locked ÷100 rule was not applied", errors)
    if "治療增效" not in nt:
        fail("修女 missing 治療增效", errors)
    if "進攻戰略" not in rt or "持久策略" not in rt or "抵抗研究" not in rt:
        fail("薔薇公主 talent names missing", errors)
    if "格擋研究" in rt:
        fail("薔薇公主 slot 3 is 抵抗研究, not 格擋研究", errors)
    if "進攻戰略" not in vt or "持久策略" not in vt or "抵抗研究" not in vt:
        fail("發明家 talent names missing", errors)
    if "格擋研究" in vt:
        fail("發明家 slot 3 is 抵抗研究, not 格擋研究", errors)

    # appearance split tables
    for label, html in (("審判官", judge), ("修女", nun), ("薔薇公主", rose), ("發明家", inventor)):
        if "收集屬性" not in html or "裝備屬性" not in html or "解鎖來源" not in html or "時裝幣" not in html:
            fail(f"{label}: 外觀 tables not split as required", errors)
        if re.search(r">—<|>–<|>－<", html):
            fail(f"{label}: empty cell used dash instead of 無", errors)

    if "審判官·傑克船長" not in jt or "審判·狂熱之愛" not in jt or "審判·不敗戰神" not in jt:
        fail("審判官 skins missing", errors)
    if "可升至 2 星，隊伍屬性見下方星級表" not in jt:
        fail("審判官 不敗戰神 should point to star table", errors)
    if "修女·純潔之戀" not in nt or "修女·智慧女神" not in nt:
        fail("修女 skins missing", errors)
    if "可升至 4 星，隊伍屬性見下方星級表" not in nt:
        fail("修女 智慧女神 should point to star table", errors)
    if "雙方成對屬性" not in jt or "雙方成對屬性" not in nt:
        fail("pairing prose should use 雙方成對屬性", errors)
    if "僅在雲海紀行賽季中生效" not in jt or "僅在雲海紀行賽季中生效" not in nt:
        fail("missing official skin_season_6 quote", errors)
    if "蔷薇" in jt or "蔷薇" in nt or "蔷薇" in rt or "蔷薇" in vt or "蔷薇" in it or "蕊薇" in it or "蕊薇" in rt or "蕊薇" in vt:
        fail("typo 蔷薇 or 蕊薇 (should be 薔薇)", errors)
    if "契約之獅" in jt or "壁克" in jt:
        fail("wrong terms 契約之獅 or 壁克", errors)
    if "誓約之獅" not in jt:
        fail("審判官 missing 誓約之獅", errors)
    if "英靈專屬技能" not in jt or "專武專屬技能" not in jt:
        fail("審判官 missing exclusive skill source labels", errors)
    if "資料表沒有" not in nt or "英靈列" not in nt:
        fail("修女 should state there is no 英靈 in the tables", errors)
    if "英靈「" in nt and "誓約" in nt:
        fail("修女 should not invent an 英靈", errors)

    if "王國之夢" not in rt:
        fail("薔薇公主 missing exclusive 王國之夢", errors)
    if "聖殿誓騎" not in rt:
        fail("薔薇公主 missing 英靈 聖殿誓騎", errors)
    if "堅定庇護" not in rt or "專武專屬技能" not in rt:
        fail("薔薇公主 missing 專武專屬技能 堅定庇護", errors)
    if "專武「王國之夢」專屬技能" not in rt:
        fail("薔薇公主 source table should label 堅定庇護 as 專武專屬技能", errors)
    if "堅定庇護覺醒被動" in rt.replace(" ", "").replace("\n", ""):
        fail("薔薇公主 堅定庇護 must not be labelled 覺醒被動技能", errors)
    if "誓約騎士" not in rt or "英靈專屬技能" not in rt:
        fail("薔薇公主 missing 英靈專屬技能 誓約騎士", errors)
    if "守護使者" not in rt:
        fail("薔薇公主 missing 11-star unlock skill 守護使者", errors)
    if "資料表沒有" not in rt or "覺醒" not in rt:
        fail("薔薇公主 should state there is no 覺醒 in the tables", errors)
    for skin in ("薔薇公主·女王", "薔薇公主·海軍上將", "薔薇公主·木蘭", "薔薇公主·亞絲翠",
                 "薔薇公主·寶石騎士", "薔薇公主·武神之靈", "薔薇公主·曇花月影"):
        if skin not in rt:
            fail(f"薔薇公主 missing skin {skin}", errors)
    if "可升至 2 星，隊伍屬性見下方星級表" not in rt:
        fail("薔薇公主 star-up skins should point to star table", errors)
    if "雙方成對屬性" not in rt or "審判·殘月騎士" not in rt:
        fail("薔薇公主 曇花月影 should describe pairing with 審判·殘月騎士", errors)
    if "海皇霸主" not in rt or "Top Heroes X 馴龍高手聯名限定" not in rt:
        fail("薔薇公主 collection suits missing", errors)
    if "凱旋之歌" not in rt or "雷霆庇護" not in rt or "大地的守護者" not in rt or "血之怒" not in rt:
        fail("薔薇公主 recommended gear mainline missing", errors)
    # Official links may point to published heroes only (all alliance pages in this build).
    allowed_hero_pages = {
        "10043.html", "10031.html", "10050.html", "10033.html", "10046.html",
        "10027.html", "10018.html", "10025.html", "10030.html", "10024.html",
        "10003.html", "10004.html", "10014.html", "10029.html", "10032.html",
        "10053.html", "10001.html", "10006.html", "15032.html", "15033.html",
    }
    for html, label in ((rose, "薔薇公主"), (judge, "審判官"), (nun, "修女"), (inventor, "發明家")):
        hrefs = set(re.findall(r'href="([^"]*\d+\.html)"', html))
        for href in hrefs:
            tail = href.rsplit("/", 1)[-1]
            if tail not in allowed_hero_pages:
                fail(f"{label} has link to unpublished hero page {href}", errors)
    for hid in ("10007", "10036", "10037", "10039", "10042", "15039"):
        if re.search(rf'href="[^"]*{hid}\.html"', rose + judge + nun + inventor):
            fail(f"published pages should not invent a link to unbuilt hero {hid}", errors)

    # Published sibling cards may link each other; 審判官 also has the 殘月騎士 pairing.
    if "10043.html" not in judge:
        fail("審判官 should now link the published 薔薇公主 entry", errors)
    if "10043.html" not in nun:
        fail("修女 should link the published 薔薇公主 entry in 相關條目", errors)
    if "10050.html" not in rose or "10050.html" not in judge or "10050.html" not in nun:
        fail("published pages should link the 發明家 entry in 相關條目", errors)
    if "10043.html" not in inventor or "10031.html" not in inventor or "10027.html" not in inventor:
        fail("發明家 should link the published 薔薇公主 / 審判官 / 修女 entries", errors)
    if "審判·殘月騎士" not in jt or "薔薇公主·曇花月影" not in jt:
        fail("審判官 殘月騎士 should describe pairing with 薔薇公主·曇花月影", errors)
    if "曇花月影" in nt or "殘月騎士" in nt:
        fail("修女 should not invent a 薔薇公主 pairing", errors)

    if "建議裝備" not in jt or "建議裝備" not in nt or "建議裝備" not in rt or "建議裝備" not in vt:
        fail("missing 建議裝備 section", errors)
    if "（推算，不是官方最佳裝備）" in jt or "（推算，不是官方最佳裝備）" in nt or "（推算，不是官方最佳裝備）" in rt or "（推算，不是官方最佳裝備）" in vt:
        fail("disclaimer should not sit inline with gear names", errors)
    if "社群備註" not in jt or "社群備註" not in nt or "社群備註" not in rt or "社群備註" not in vt:
        fail("missing 社群備註 heading", errors)

    if "star-white" not in judge or "star-white" not in nun or "star-white" not in rose or "star-white" not in inventor:
        fail("15-star display should include white star icons", errors)

    # Homepage is a compact roster, not portrait cards.
    # Hero pages still reserve a portrait slot; no character art in the build.
    if "lead-placeholder" in index or "hero-card" in index:
        fail("index: homepage should list names, not hero cards or portrait placeholders", errors)
    for html, label in ((index, "index"), (judge, "審判官"), (nun, "修女"), (rose, "薔薇公主"), (inventor, "發明家")):
        if "10031-lead.jpg" in html or 'src="lead.jpg"' in html or "th-art/page/lead" in html:
            fail(f"{label}: should not embed a character portrait", errors)
        if "<img" in html.lower():
            fail(f"{label}: unexpected <img> (placeholder must not be a broken image tag)", errors)
    for html, label in ((judge, "審判官"), (nun, "修女"), (rose, "薔薇公主"), (inventor, "發明家")):
        if "lead-placeholder" not in html:
            fail(f"{label}: missing reserved lead-image placeholder", errors)
    lead_out = DOCS / "assets" / "img" / "10031-lead.jpg"
    if lead_out.exists():
        fail("docs still contains published lead art 10031-lead.jpg", errors)

    if "公正領域" not in jt or "雄獅血脈" not in jt:
        fail("審判官 exclusive / spirit skills missing", errors)
    if "Top Heroes X 馴龍高手聯名限定" not in jt:
        fail("審判官 missing official suit name Top Heroes X 馴龍高手聯名限定", errors)
    if "套裝英雄 技能減傷+10.00%" not in jt or "套裝英雄 英雄攻擊+8.00%" not in jt or "全英雄 出征上限+8" not in jt:
        fail("審判官 馴龍高手聯名 8-piece tier should show current-tier 技能減傷+10.00%、英雄攻擊+8.00%、出征上限+8", errors)
    if "不朽王座" not in jt:
        fail("審判官 missing official suit name 不朽王座", errors)
    if "全英雄 英雄等級上限+1" not in jt or "全英雄 英雄等級上限+2" not in jt or "全英雄 英雄等級上限+3" not in jt:
        fail("審判官 不朽王座 should show current-tier 英雄等級上限+1／+2／+3", errors)
    if "英雄等級上限+0.01%" in jt or "出征上限+0.08%" in jt or "出征上限+20.00%" in jt:
        fail("審判官 must not write suit point attrs as percent", errors)
    if "神聖恩賜" not in nt:
        fail("修女 exclusive skill missing", errors)
    if "思維火花" not in vt:
        fail("發明家 missing exclusive 思維火花", errors)
    if "發條守衛" not in vt:
        fail("發明家 missing 英靈 發條守衛", errors)
    if "共鳴" not in vt or "專武專屬技能" not in vt:
        fail("發明家 missing 專武專屬技能 共鳴", errors)
    if "專武「思維火花」專屬技能" not in vt:
        fail("發明家 source table should label 共鳴 as 專武專屬技能", errors)
    if "愛情蛊惑" in vt or "愛情虫惑" in vt or "愛情蠱惑" in vt:
        fail("發明家 must not include 吟遊詩人 exclusive 愛情蛊惑", errors)
    if "機械過載" not in vt or "英靈專屬技能" not in vt:
        fail("發明家 missing 英靈專屬技能 機械過載", errors)
    if "閃爍懷錶" not in vt:
        fail("發明家 missing 11-star unlock skill 閃爍懷錶", errors)
    if "11 星解鎖技能" not in vt or "閃爍懷錶" not in vt:
        fail("發明家 閃爍懷錶 should be labelled as an 11-star unlock skill", errors)
    if "閃爍懷錶覺醒被動" in vt.replace(" ", "").replace("\n", ""):
        fail("發明家 閃爍懷錶 must not be labelled 覺醒被動技能", errors)
    # More precise: the source-table cell for 閃爍懷錶 must not say 覺醒
    src = section_html(inventor, "skills") or inventor
    if re.search(r"閃爍懷錶</span></td><td>覺醒", src) or "閃爍懷錶</span></td><td>覺醒被動技能" in src:
        fail("發明家 閃爍懷錶 must not be sourced as 覺醒被動技能", errors)
    if "資料表沒有" not in vt or "覺醒" not in vt:
        fail("發明家 should state there is no 覺醒 in the tables", errors)
    if "不是本英雄獨立組件號段" in vt:
        fail("發明家 閃爍懷錶 is in-range (1005013), must not be called a shared out-of-range skill", errors)
    if "守護使者" in rt and "不是本英雄獨立組件號段" not in rt:
        fail("薔薇公主 守護使者 should still be described as a shared unlock skill", errors)
    if "發明家·大白鯊" not in vt or "發明家·愛麗絲" not in vt:
        fail("發明家 skins missing", errors)
    if "夢境童話" not in vt:
        fail("發明家 collection suit 夢境童話 missing", errors)
    if "出征上限+20.00%" in vt or "出征上限+0.08%" in vt:
        fail("發明家 suit points must not be written as percent", errors)
    if "雙方成對屬性" in vt:
        fail("發明家 should not invent a pairing", errors)
    if "聖光祝福" not in vt or "冠軍的英姿" not in vt or "騎士榮光" not in vt:
        fail("發明家 recommended gear mainline missing", errors)
    if "見資料說明" not in vt:
        fail("發明家 status should follow hide=1 wording 見資料說明", errors)
    # hide=1 is not a 已開放 / 未開放 flag; 騎士榮光（未開放） is gear-only wording.
    if "已開放" in vt:
        fail("發明家 hide=1 must not be announced as 已開放", errors)
    head_t = text_of(inventor.split("建議裝備")[0])
    if "發明家（未開放）" in vt or "他未開放" in vt or re.search(r"(?<!騎士榮光（)未開放", head_t):
        fail("發明家 hide=1 must not be announced as 未開放", errors)
    if "僅在潮汐之怒賽季中生效" not in vt:
        fail("發明家 大白鯊 should quote official 潮汐之怒 season text", errors)
    if "突破防禦+2000" not in vt:
        fail("發明家·大白鯊 should show 突破防禦+2000", errors)
    if "突破防禦+20.00%" in vt:
        fail("發明家 must not write 突破防禦 as +20.00%", errors)
    if "英雄攻擊+3.00%" not in vt or "英雄生命+10.00%" not in vt:
        fail("發明家·大白鯊 should show 英雄攻擊+3.00% and 英雄生命+10.00%", errors)
    if "黑潮來襲時扣除氧氣值減少+10.00%" not in vt:
        fail("發明家·大白鯊 season attr 1244 should display as 黑潮來襲時扣除氧氣值減少+10.00%", errors)
    if "表上另有一欄隊伍屬性" in vt:
        fail("發明家 must not still describe team_attr as a separate uncombined column", errors)
    if "臨時擁有屬性，對應賽季持續期間，擁有造型即可生效" in vt and "不自行把這一欄對成擁有或使用" not in vt:
        fail("發明家 must not map season_effect2 to 臨時擁有／臨時使用", errors)
    if "S3 暮光之戰及之後" not in vt:
        fail("發明家 missing official 最佳聯盟 S3 label", errors)
    if "此資料截到 2026-11-05，表內沒有以 S4、S5、S6 為名的聯盟推薦更新。" not in vt:
        fail("發明家 missing official rec cutoff note", errors)
    for bad in ("契約之獅", "壁克", "发条守卫", "思維火華", "爱丽丝", "大白鲨", "梦境童话"):
        if bad in vt or bad in it:
            fail(f"發明家/index typo or wrong term {bad}", errors)

    if "海皇霸主" not in jt or "永恆之戀" not in jt or "不朽王座" not in jt:
        fail("審判官 collection suits missing", errors)
    if "永恆之戀" not in nt or "不朽王座" not in nt:
        fail("修女 collection suits missing", errors)

    # display server 50 vs id 10050 should not be claimed
    if re.search(r"顯示.?50.{0,12}10050|10050.{0,12}顯示.?50", jt + nt + rt + vt + it):
        fail("must not claim display 50 equals internal id 10050", errors)

    check_new_league_pages(errors)

    if errors:
        print(f"{len(errors)} check(s) failed:")
        for msg in errors:
            print(" -", msg)
        return 1
    print("ok: TOC + all published alliance hero pages passed locked-rule checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
