#!/usr/bin/env python3
"""Sanity-check the built index, catalog tables, and published hero pages against locked rules."""

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
EXCLUSIVE = DOCS / "exclusive.html"
VALHALLA = DOCS / "valhalla.html"
SKINS = DOCS / "skins.html"
EQUIPMENT = DOCS / "equipment.html"
LORD_EQUIPMENT = DOCS / "lord-equipment.html"
TROOPS = DOCS / "troops.html"
ARTIFACTS = DOCS / "artifacts.html"
PETS = DOCS / "pets.html"
HOLYBEASTS = DOCS / "holybeasts.html"
PALS = DOCS / "pals.html"
RUNES = DOCS / "runes.html"
TALENTS = DOCS / "talents.html"
TECH = DOCS / "tech.html"
DECORATIONS = DOCS / "decorations.html"
CASTLE = DOCS / "castle.html"


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = re.sub(r"[ \t\r\n]+", " ", t)
    return t



def visible_before_notes(html: str) -> str:
    """Plain text of a public page before the last 資料說明 heading."""
    matches = list(re.finditer(r"<h2\b[^>]*>\s*資料說明\s*</h2>", html))
    if not matches:
        return text_of(html)
    return text_of(html[: matches[-1].start()])


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
    "天賦", "科技", "裝飾物", "城堡外觀", "守護魔獸", "帕魯",
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
    published = PUBLISHED_IDS
    allowed = {f"heroes/{hid}.html" for hid in published}
    got_hrefs = set()
    for href in hero_hrefs:
        tail = href.rsplit("/", 2)
        norm = "/".join(tail[-2:]) if len(tail) >= 2 else href
        got_hrefs.add(norm)
    if got_hrefs != allowed:
        fail(f"index: hero links should be all published pages, got {sorted(got_hrefs)}", errors)
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

    # All nature and tribe entries are now published links, not 尚未公開.
    for sid, names, id_list, label in (
        ("faction-nature", NATURE_NAMES, NATURE_IDS, "nature"),
        ("faction-tribe", TRIBE_NAMES, TRIBE_IDS, "tribe"),
    ):
        block = section_html(index, sid) or ""
        for item in li_texts(block):
            if "尚未公開" in item:
                fail(f"index: published {label} entry should not be marked 尚未公開: {item}", errors)
            if "未開放" in item:
                fail(f"index: {label} entry must not be marked 未開放: {item}", errors)
        for hid, display in zip(id_list, names):
            if f'href="heroes/{hid}.html"' not in index:
                fail(f"index: {display} should be a real link to heroes/{hid}.html", errors)
    if "15039" not in it:
        fail("index: 15039 should appear as the id only", errors)
    tribe = section_html(index, "faction-tribe") or ""
    for item in li_texts(tribe):
        if "15039" in item and core_name(item) != "15039":
            fail(f"index: 15039 must not invent a Chinese name: {item}", errors)

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
        published_codex = (
            ("exclusive.html", "專武"),
            ("valhalla.html", "英靈"),
            ("skins.html", "造型"),
            ("equipment.html", "裝備"),
            ("lord-equipment.html", "領主裝備"),
            ("troops.html", "士兵"),
            ("artifacts.html", "秘寶"),
            ("pets.html", "寵物"),
            ("runes.html", "符文"),
            ("talents.html", "天賦"),
            ("tech.html", "科技"),
            ("decorations.html", "裝飾物"),
            ("castle.html", "城堡外觀"),
            ("holybeasts.html", "守護魔獸"),
            ("pals.html", "帕魯"),
        )
        other = codex
        for href, label in published_codex:
            if not re.search(rf'<a href="{re.escape(href)}">{label}</a>', codex):
                fail(f"index 圖鑑 {label} should link to {href}", errors)
            other = re.sub(rf'<a href="{re.escape(href)}">{label}</a>', label, other)
        if re.search(r"<a\b", other):
            fail("index 圖鑑 should only link the published catalogue items", errors)

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
    if "目前聯盟、自然和部族的英雄條目都已公開。" not in it:
        fail("index lede should say alliance, nature and tribe pages are all published", errors)
    if "專武總表、英靈總表、造型總表、裝備總表、領主裝備總表、士兵總表、秘寶總表、寵物總表、符文總表、天賦總表、科技總表、裝飾物總表和城堡外觀總表也已公開" not in it:
        fail("index lede should name all published catalogs, including talent, tech, decoration and castle", errors)
    if "專武總表、英靈總表和造型總表也已公開" in it:
        fail("index lede still only lists exclusive, valhalla and skin catalogs", errors)
    if "專武總表、英靈總表、造型總表、裝備總表、領主裝備總表、士兵總表、秘寶總表、寵物總表、符文總表、天賦總表、科技總表、裝飾物總表和城堡外觀總表已公開" not in it:
        fail("index 圖鑑 should name all published catalogs, including talent, tech, decoration and castle", errors)
    if "其餘分類稍後再補" in it:
        fail("index 圖鑑 should not still say remaining categories will follow", errors)
    if "專武總表、英靈總表和造型總表已公開，其餘分類稍後再補" in it:
        fail("index 圖鑑 still omits later catalogs", errors)
    for href in (
        "exclusive.html", "valhalla.html", "skins.html",
        "equipment.html", "lord-equipment.html", "troops.html",
        "artifacts.html", "pets.html", "runes.html",
        "talents.html", "tech.html", "decorations.html", "castle.html",
        "holybeasts.html", "pals.html",
    ):
        if f'href="{href}"' not in index:
            fail(f"index should link to {href}", errors)
    if "目前先公開薔薇公主、審判官、發明家和修女" in it:
        fail("index lede still only lists the first four published heroes", errors)
    if "條目會陸續補上" in it:
        fail("index lede should not still say remaining pages are upcoming", errors)



LEAGUE_IDS = [
    10043, 10031, 10050, 10033, 10046, 10027, 10018, 10025, 10030, 10024,
    10003, 10004, 10014, 10029, 10032, 10053, 10001, 10006, 15032, 15033,
]
NATURE_IDS = [
    10042, 10049, 10051, 10036, 10037, 10044, 10019, 10035, 10040, 10008,
    10005, 10012, 10013, 10021, 10026, 10054, 10002, 10007,
]
TRIBE_IDS = [
    10039, 10048, 10047, 10038, 10045, 10041, 10017, 10020, 10023, 10028,
    10034, 10011, 10015, 10016, 10022, 10052, 10009, 10010, 15039,
]
PUBLISHED_IDS = LEAGUE_IDS + NATURE_IDS + TRIBE_IDS

EXPECTED_TAGS = {
    10033: ("傷害、爆發、群體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10046: ("傷害、爆發、控制", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "能夠對敵人造成控制"], "後兩項的官方說明沒有百分比"),
    10018: ("坦克、控制、增益", "受到傷害-5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10025: ("傷害、爆發、群體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10030: ("輔助、增益、群體", "生命上限+5%", ["能夠為隊友提供加強效果", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10024: ("傷害、爆發、個體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成個體傷害"], "後兩項的官方說明沒有百分比"),
    10003: ("治療、增益", "治療效果+5%", ["能夠為隊友提供加強效果"], "後項的官方說明沒有百分比"),
    10004: ("坦克、控制", "受到傷害-5%", ["能夠對敵人造成控制"], "後項的官方說明沒有百分比"),
    10014: ("傷害、增益", "最終傷害+3%", ["能夠為隊友提供加強效果"], "後項的官方說明沒有百分比"),
    10032: ("坦克、控制、群體", "受到傷害-5%", ["能夠對敵人造成控制", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10053: ("輔助、控制、增益", "生命上限+5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10001: ("傷害、持續", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰"], "後項的官方說明沒有百分比"),
    10006: ("傷害、群體", "最終傷害+3%", ["專注於造成群體傷害"], "後項的官方說明沒有百分比"),
}

NO_SECOND_IDS = {10029, 15032, 15033}

OPEN_IDS = {
    10018, 10025, 10030, 10024, 10003, 10004, 10014, 10001, 10006,
    10033, 10046, 10053,
}

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
    for hid in LEAGUE_IDS:
        path = DOCS / "heroes" / f"{hid}.html"
        if not path.exists():
            fail(f"missing {path}", errors)
            continue
        html = path.read_text(encoding="utf-8")
        pages[hid] = html
        texts[hid] = text_of(html)

    new_ids = [hid for hid in LEAGUE_IDS if hid not in {10043, 10031, 10050, 10027}]
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
        elif hid == 10029:
            # Index already confirms 未開放; the entry uses the same wording.
            lead = section_html(html, "lead") or ""
            if "未開放" not in text_of(lead):
                fail("牧羊人: lead/status should say 未開放, matching the index", errors)
            if re.search(r"已開放", lead):
                fail("牧羊人: must not be announced as 已開放", errors)
        elif hid in {15032, 15033}:
            lead = section_html(html, "lead") or ""
            leadt = text_of(lead)
            if "沒有官方中文名稱" not in vt:
                fail(f"{label}: 狀態欄 should say 沒有官方中文名稱", errors)
            if re.search(r"已開放", lead) or "未開放" in leadt:
                fail(f"{label}: must not invent 已開放／未開放", errors)
        elif hid == 10032:
            lead = section_html(html, "lead") or ""
            leadt = text_of(lead)
            if "本頁不另標上線狀態" in vt:
                fail("老闆娘 狀態欄 must not say 本頁不另標上線狀態", errors)
            if "見資料說明" in leadt:
                fail("老闆娘 狀態欄 must not say 見資料說明", errors)
            if re.search(r"已開放", lead):
                fail("老闆娘 must not be marked 已開放", errors)
            if re.search(r"<dt>狀態</dt>\s*<dd>\s*(?:已開放|未開放|本頁不另標上線狀態|見資料說明|[^<\s])", lead):
                fail("老闆娘 狀態欄 should be omitted or empty", errors)
        else:
            if "已開放" not in vt:
                fail(f"{label}: 狀態欄 should say 已開放", errors)
            if "本頁不另標上線狀態" in vt:
                fail(f"{label}: 狀態欄 must not say 本頁不另標上線狀態", errors)
        if hid in EXPECTED_TAGS:
            tags, locked, decs, pct_note = EXPECTED_TAGS[hid]
            if tags not in vt:
                fail(f"{label} tags should be {tags}", errors)
            if locked not in vt:
                fail(f"{label} missing locked {locked}", errors)
            for dec in decs:
                if dec not in vt:
                    fail(f"{label} missing official description {dec}", errors)
            if pct_note not in vt or "由玩家在面板確認" not in vt:
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
    landlady_lead = section_html(landlady_html, "lead") or ""
    landlady_leadt = text_of(landlady_lead)
    if "未開放" in landlady_lead:
        fail("老闆娘 must not be marked 未開放", errors)
    if re.search(r"已開放", landlady_lead):
        fail("老闆娘 must not be marked 已開放", errors)
    if "本頁不另標上線狀態" in landlady or "見資料說明" in landlady_leadt:
        fail("老闆娘 狀態欄 must not say 本頁不另標上線狀態 or 見資料說明", errors)
    if re.search(r"<dt>狀態</dt>\s*<dd>\s*(?:已開放|未開放|本頁不另標上線狀態|見資料說明|[^<\s])", landlady_lead):
        fail("老闆娘 狀態欄 should be omitted or empty", errors)

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



NATURE_TRIBE_TAGS = {
    10042: ("坦克、持續、增益", "受到傷害-5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10049: ("坦克、爆發、控制", "受到傷害-5%", ["偏向於使用技能在短時間內造成高額傷害", "能夠對敵人造成控制"], "後兩項的官方說明沒有百分比"),
    10051: ("輔助、控制、增益", "生命上限+5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10036: ("輔助、控制、召喚", "生命上限+5%", ["能夠對敵人造成控制", "能夠召喚額外單位參與戰鬥"], "後兩項的官方說明沒有百分比"),
    10037: ("傷害、爆發、控制", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "能夠對敵人造成控制"], "後兩項的官方說明沒有百分比"),
    10044: ("傷害、控制、召喚", "最終傷害+3%", ["能夠對敵人造成控制", "能夠召喚額外單位參與戰鬥"], "後兩項的官方說明沒有百分比"),
    10019: ("坦克、持續、增益", "受到傷害-5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10035: ("坦克、持續、減益", "受到傷害-5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10040: ("傷害、爆發、個體", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "專注於造成個體傷害"], "後兩項的官方說明沒有百分比"),
    10008: ("治療、增益、召喚", "治療效果+5%", ["能夠為隊友提供加強效果", "能夠召喚額外單位參與戰鬥"], "後兩項的官方說明沒有百分比"),
    10005: ("輔助、增益", "生命上限+5%", ["能夠為隊友提供加強效果"], "後項的官方說明沒有百分比"),
    10012: ("傷害、持續、群體", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10013: ("傷害、召喚", "最終傷害+3%", ["能夠召喚額外單位參與戰鬥"], "後項的官方說明沒有百分比"),
    10021: ("傷害、爆發、減益", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10026: ("傷害、控制、群體", "最終傷害+3%", ["能夠對敵人造成控制", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10054: ("輔助、增益、減益", "生命上限+5%", ["能夠為隊友提供加強效果", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10002: ("傷害、群體", "最終傷害+3%", ["專注於造成群體傷害"], "後項的官方說明沒有百分比"),
    10007: ("治療、群體", "治療效果+5%", ["專注於造成群體傷害"], "後項的官方說明沒有百分比"),
    10039: ("坦克、持續、群體", "受到傷害-5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10048: ("坦克、控制、增益", "受到傷害-5%", ["能夠對敵人造成控制", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10047: ("傷害、控制、召喚", "最終傷害+3%", ["能夠對敵人造成控制", "能夠召喚額外單位參與戰鬥"], "後兩項的官方說明沒有百分比"),
    10038: ("輔助、增益、群體", "生命上限+5%", ["能夠為隊友提供加強效果", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10045: ("治療、持續、控制", "治療效果+5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠對敵人造成控制"], "後兩項的官方說明沒有百分比"),
    10041: ("傷害、持續、群體", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10017: ("坦克、控制、減益", "受到傷害-5%", ["能夠對敵人造成控制", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10020: ("坦克、持續、群體", "受到傷害-5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10023: ("傷害、持續、增益", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠為隊友提供加強效果"], "後兩項的官方說明沒有百分比"),
    10028: ("輔助、增益、減益", "生命上限+5%", ["能夠為隊友提供加強效果", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10034: ("治療、持續、群體", "治療效果+5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "專注於造成群體傷害"], "後兩項的官方說明沒有百分比"),
    10011: ("傷害、減益", "最終傷害+3%", ["能夠使敵人受到弱化效果"], "後項的官方說明沒有百分比"),
    10015: ("輔助、減益", "生命上限+5%", ["能夠使敵人受到弱化效果"], "後項的官方說明沒有百分比"),
    10016: ("傷害、持續", "最終傷害+3%", ["偏向於為攻擊附加特殊效果並進行持續作戰"], "後項的官方說明沒有百分比"),
    10022: ("傷害、爆發、控制", "最終傷害+3%", ["偏向於使用技能在短時間內造成高額傷害", "能夠對敵人造成控制"], "後兩項的官方說明沒有百分比"),
    10052: ("治療、持續、減益", "治療效果+5%", ["偏向於為攻擊附加特殊效果並進行持續作戰", "能夠使敵人受到弱化效果"], "後兩項的官方說明沒有百分比"),
    10009: ("輔助、增益", "生命上限+5%", ["能夠為隊友提供加強效果"], "後項的官方說明沒有百分比"),
    10010: ("坦克、控制", "受到傷害-5%", ["能夠對敵人造成控制"], "後項的官方說明沒有百分比"),
}

NATURE_TRIBE_GEAR = {
    10042: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10049: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10051: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10036: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10037: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10044: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10019: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10035: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10040: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10008: ("生命之力", "騎士榮光"),
    10005: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10012: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10013: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10021: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10026: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10054: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10002: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10007: ("生命之力", "騎士榮光"),
    10039: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10048: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10047: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10038: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10045: ("生命之力", "騎士榮光"),
    10041: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10017: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10020: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    10023: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10028: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10034: ("生命之力", "騎士榮光"),
    10011: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10015: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10016: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10022: ("太陽之怒", "扭曲印記", "賢者的敏銳", "泰坦之威"),
    10052: ("生命之力", "騎士榮光"),
    10009: ("聖光祝福", "冠軍的英姿", "騎士榮光"),
    10010: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
    15039: ("凱旋之歌", "雷霆庇護", "大地的守護者", "血之怒"),
}

NATURE_TRIBE_NAMES = {
    10042: "豪士", 10049: "中壇元帥", 10051: "花藝師", 10036: "森之少女", 10037: "妖精",
    10044: "喚潮使", 10019: "樹人守衛", 10035: "賢者", 10040: "風行者", 10008: "德魯伊",
    10005: "舞孃", 10012: "尋路者", 10013: "祭司", 10021: "守望者", 10026: "石匠",
    10054: "大冒險家", 10002: "弓箭手", 10007: "藥劑師",
    10039: "沙漠王子", 10048: "馴獸師", 10047: "行者", 10038: "通靈師", 10045: "女巫",
    10041: "風暴聖女", 10017: "蠻鬥士", 10020: "劍術教官", 10023: "荒野獵手", 10028: "術士",
    10034: "薩滿", 10011: "盜賊", 10015: "罪犯", 10016: "鬥者", 10022: "獵人",
    10052: "暗影牧師", 10009: "鐵匠", 10010: "護衛", 15039: "15039",
}

NATURE_TRIBE_OPEN = {
    10036, 10019, 10035, 10040, 10008, 10005, 10013, 10002, 10007,
    10038, 10020, 10023, 10028, 10034, 10011, 10015, 10016, 10009, 10010,
    10012, 10021, 10026, 10037, 10042, 10044, 10049, 10051, 10054,
    10017, 10022, 10039, 10041, 10045, 10047, 10048, 10052,
}
TALENT_PANEL_CHECK_IDS = {10007, 10005, 10028, 10021, 10039}
NOT_UNRELEASED = {10012, 10042, 10039, 10041, 15039}
CAP10_IDS = {10002, 10007, 10009, 10010}
CAP20_IDS = {10005, 10013, 10011, 10015, 10016}
NATURE_REC_IDS = {10042, 10049, 10051, 10036, 10037, 10044, 10019, 10035, 10040, 10008}
TRIBE_REC_IDS = {10039, 10048, 10047, 10038, 10045, 10041, 10017, 10020, 10023, 10028, 10034}


def check_nature_tribe_pages(errors: list[str]) -> None:
    pages = {}
    texts = {}
    for hid in NATURE_IDS + TRIBE_IDS:
        path = DOCS / "heroes" / f"{hid}.html"
        if not path.exists():
            fail(f"missing {path}", errors)
            continue
        html = path.read_text(encoding="utf-8")
        pages[hid] = html
        texts[hid] = text_of(html)

    for hid in NATURE_IDS + TRIBE_IDS:
        html = pages.get(hid)
        if not html:
            continue
        vt = texts[hid]
        label = NATURE_TRIBE_NAMES[hid]
        if 'lang="zh-Hant"' not in html:
            fail(f"{label}: missing lang=zh-Hant", errors)
        if "稱號屬性" in vt:
            fail(f"{label}: used 稱號屬性 instead of 英雄屬性", errors)
        if "英雄屬性" not in vt:
            fail(f"{label}: missing 英雄屬性 label", errors)
        if "頭像（待補）" not in html:
            fail(f"{label}: missing portrait placeholder 頭像（待補）", errors)
        if hid in NATURE_TRIBE_OPEN:
            if "已開放" not in vt:
                fail(f"{label}: hide=-1 should say 已開放", errors)
        elif hid == 15039:
            lead = section_html(html, "lead") or ""
            leadt = text_of(lead)
            if "沒有官方中文名稱" not in vt:
                fail("15039: 狀態欄 should say 沒有官方中文名稱", errors)
            if re.search(r"已開放", lead) or "未開放" in leadt:
                fail("15039: must not invent 已開放／未開放", errors)
        else:
            if "已開放" not in vt:
                fail(f"{label}: 狀態欄 should say 已開放", errors)
            if "本頁不另標上線狀態" in vt:
                fail(f"{label}: 狀態欄 must not say 本頁不另標上線狀態", errors)
        if hid in NOT_UNRELEASED:
            if "未開放" in (section_html(html, "lead") or "") or re.search(r"（未開放）", section_html(html, "lead") or ""):
                fail(f"{label} must not be marked 未開放", errors)
        if hid in NATURE_TRIBE_TAGS:
            tags, locked, decs, pct_note = NATURE_TRIBE_TAGS[hid]
            if tags not in vt:
                fail(f"{label} tags should be {tags}", errors)
            if locked not in vt:
                fail(f"{label} missing locked {locked}", errors)
            for dec in decs:
                if dec not in vt:
                    fail(f"{label} missing official description {dec}", errors)
            if pct_note not in vt or "由玩家在面板確認" not in vt:
                fail(f"{label} should note second-group has no percentage and is panel-confirmed", errors)
        if hid == 15039:
            if "第二組標籤尚未經玩家面板確認，本頁不推算" not in vt:
                fail("15039 should say second-group tags are unconfirmed and not inferred", errors)
            if "暫缺" in vt:
                fail("15039 must not write 暫缺 as a public tag", errors)
            if f"<title>Top Heroes Wiki｜{hid}</title>" not in html:
                fail("15039 title should use the id only, not an invented Chinese name", errors)
        for piece in NATURE_TRIBE_GEAR.get(hid, ()):
            if piece not in vt:
                fail(f"{label} recommended gear missing {piece}", errors)
        if "（推算，不是官方最佳裝備）" in html:
            fail(f"{label} should not put 推算 note inline beside gear names", errors)
        for bad in TYPOS:
            if bad in html:
                fail(f"{label} typo or wrong term {bad}", errors)
        if "由玩家確認" in vt:
            fail(f"{label} public page must not say 由玩家確認", errors)
        if "這不是寫死所有伺服器、所有英雄都讀舊表" not in vt and ("所有伺服器都讀舊表" in vt or "所有伺服器、所有英雄都讀同一張表" in vt):
            fail(f"{label} must not say every server reads the old talent table", errors)
        if "契約之獅" in vt or "壁克" in vt:
            fail(f"{label} wrong term 契約之獅 or 壁克", errors)

    # Talent display
    q3 = [hid for hid in NATURE_IDS + TRIBE_IDS if hid not in CAP10_IDS | CAP20_IDS]
    for hid in q3:
        vt = texts.get(hid, "")
        label = NATURE_TRIBE_NAMES[hid]
        if "90.00%" not in vt or "270.00%" not in vt:
            fail(f"{label} slots with 所有士兵攻擊／生命 should show 90.00%／270.00%", errors)
        if hid in TALENT_PANEL_CHECK_IDS:
            if "已用面板確認" not in vt:
                fail(f"{label} should say talent values were panel-confirmed", errors)
            if "不是本英雄自己的面板確認" in vt:
                fail(f"{label} must not be worded as if percentages were only borrowed", errors)
        else:
            if "依已確認的前服天賦面板規則" not in vt or "不是本英雄自己的面板確認" not in vt:
                fail(f"{label} percent talents should cite the confirmed 前服 rule, not own-panel confirmation", errors)
        if "不曾用審判官面板的÷100 推算" in vt:
            fail(f"{label} must not say the locked ÷100 rule was not applied", errors)

    for hid in CAP10_IDS:
        vt = texts.get(hid, "")
        label = NATURE_TRIBE_NAMES[hid]
        if "2.00%" not in vt or "20.00%" not in vt or "6.00%" not in vt or "60.00%" not in vt:
            fail(f"{label} slots 1／2 should show converted 2.00%／20.00% and 6.00%／60.00%", errors)
        if hid in TALENT_PANEL_CHECK_IDS:
            if "已用面板確認" not in vt:
                fail(f"{label} should say talent values were panel-confirmed", errors)
            if "不是本英雄自己的面板確認" in vt:
                fail(f"{label} must not be worded as if percentages were only borrowed", errors)
        else:
            if "依已確認的前服天賦面板規則" not in vt or "不是本英雄自己的面板確認" not in vt:
                fail(f"{label} percent talents should cite the confirmed 前服 rule, not own-panel confirmation", errors)

    for hid in CAP20_IDS:
        vt = texts.get(hid, "")
        label = NATURE_TRIBE_NAMES[hid]
        if "2.50%" not in vt or "50.00%" not in vt or "7.50%" not in vt or "150.00%" not in vt:
            fail(f"{label} slots 1／2 should show converted 2.50%／50.00% and 7.50%／150.00%", errors)
        if hid in TALENT_PANEL_CHECK_IDS:
            if "已用面板確認" not in vt:
                fail(f"{label} should say talent values were panel-confirmed", errors)
            if "不是本英雄自己的面板確認" in vt:
                fail(f"{label} must not be worded as if percentages were only borrowed", errors)
        else:
            if "依已確認的前服天賦面板規則" not in vt or "不是本英雄自己的面板確認" not in vt:
                fail(f"{label} percent talents should cite the confirmed 前服 rule, not own-panel confirmation", errors)

    # Spot-check converted slot-3 percents and point talents.
    for hid, needles in (
        (10042, ("1.00%", "30.00%")),
        (10049, ("0.67%", "20.00%")),
        (10036, ("1.67%", "50.00%")),
        (10039, ("1.67%", "50.00%")),
        (10019, ("1.33%", "40.00%")),
        (10023, ("2.00%", "60.00%")),
        (15039, ("1.67%", "50.00%")),
    ):
        vt = texts.get(hid, "")
        label = NATURE_TRIBE_NAMES[hid]
        for needle in needles:
            if needle not in vt:
                fail(f"{label} talent should show converted {needle}", errors)

    watcher_html = pages.get(10021, "")
    watcher_tal = text_of(section_html(watcher_html, "spirit-talents") or "")
    watcher = texts.get(10021, "")
    if "67" not in watcher or "2000" not in watcher:
        fail("守望者 士兵擴編 should show point values 67 and 2000", errors)
    if "67%" in watcher_tal or "2000%" in watcher_tal or "+67" in watcher_tal or "2,000" in watcher_tal:
        fail("守望者 士兵擴編 must not use percent, plus, or thousands separators", errors)
    if "已用面板確認" not in watcher:
        fail("守望者 should say talent values were panel-confirmed", errors)

    warlock_html = pages.get(10028, "")
    warlock_tal = text_of(section_html(warlock_html, "spirit-talents") or "")
    warlock = texts.get(10028, "")
    if "12000" not in warlock or "360000" not in warlock:
        fail("術士 資源掠奪 should show point values 12000 and 360000", errors)
    if "12,000" in warlock_tal or "360,000" in warlock_tal or "12000%" in warlock_tal or "360000%" in warlock_tal:
        fail("術士 資源掠奪 must not use thousands separators or percent", errors)
    if "已用面板確認" not in warlock:
        fail("術士 should say talent values were panel-confirmed", errors)

    # Appearance percent / point display: at least one nature and one tribe skin line.
    shark_like = texts.get(10042, "")  # 豪士 skins, percent form if present
    x39 = texts.get(15039, "")
    if "英雄生命+10.00%" not in x39 or "普攻距離+5.00%" not in x39:
        fail("15039 沙漠王子·鬼武者 should show 普攻距離+5.00% and 英雄生命+10.00%", errors)

    # Official rec cutoff by faction
    for hid in NATURE_REC_IDS:
        vt = texts.get(hid, "")
        if "此資料截到 2026-11-05，表內沒有以 S4、S5、S6 為名的自然推薦更新。" not in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} missing official nature rec cutoff note", errors)
        if "聯盟推薦更新" in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} must not use the 聯盟 rec cutoff sentence", errors)
        if "最佳聯盟" in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} must not use 最佳聯盟 wording", errors)
    for hid in TRIBE_REC_IDS:
        vt = texts.get(hid, "")
        if "此資料截到 2026-11-05，表內沒有以 S4、S5、S6 為名的部族推薦更新。" not in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} missing official tribe rec cutoff note", errors)
        if "聯盟推薦更新" in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} must not use the 聯盟 rec cutoff sentence", errors)
        if "最佳聯盟" in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} must not use 最佳聯盟 wording", errors)

    # 藥劑師 is nature
    alchemist = texts.get(10007, "")
    if "自然" not in alchemist:
        fail("藥劑師 should be listed as 自然", errors)
    if "部族" in (section_html(pages.get(10007, ""), "lead") or ""):
        fail("藥劑師 lead must not call her 部族", errors)

    # 森之少女 / 牧羊人 cross
    girl_html = pages.get(10036, "")
    girl = texts.get(10036, "")
    stars = section_html(girl_html, "star-skills") or ""
    exclusive = section_html(girl_html, "exclusive") or ""
    awaken = section_html(girl_html, "awaken") or section_html(girl_html, "skills") or ""
    for skill in ("綿羊衝鋒", "牧羊人之鈴", "咩咩守護", "生命之歌", "復仇"):
        if skill not in girl:
            fail(f"森之少女 missing star skill {skill}", errors)
    if "諾亞金鈴" not in text_of(exclusive) and "諾亞金鈴" not in girl:
        fail("森之少女 should list exclusive 諾亞金鈴", errors)
    if "諾亞之聲" not in girl:
        fail("森之少女 missing exclusive skill 諾亞之聲", errors)
    if "森林之歌" not in girl or "春之祝福" not in girl:
        fail("森之少女 missing awaken skills 森林之歌／春之祝福", errors)
    if 'href="10029.html"' not in girl_html:
        fail("森之少女 should formally link to 牧羊人 page 10029.html", errors)

    # 牧羊人 must still exclude her exclusive/awaken package, and may now link to her page.
    shepherd_path = DOCS / "heroes" / "10029.html"
    if shepherd_path.exists():
        shepherd_html = shepherd_path.read_text(encoding="utf-8")
        if "森之少女條目尚未公開" in shepherd_html or "這裡不自製連結" in text_of(shepherd_html):
            fail("牧羊人 should no longer say 森之少女 is unpublished or refuse a link", errors)
        if 'href="10036.html"' not in shepherd_html:
            fail("牧羊人 should formally link to 森之少女 page 10036.html", errors)

    # Official odd spelling on 神賜之沙
    for hid in (10039, 15039):
        vt = texts.get(hid, "")
        if "冷却時間" not in vt:
            fail(f"{NATURE_TRIBE_NAMES[hid]} should keep official spelling 冷却時間 on 神賜之沙", errors)

    # display server number must not be claimed equal to internal id
    blob = "".join(texts.get(hid, "") for hid in NATURE_IDS + TRIBE_IDS)
    for hid in NATURE_IDS + TRIBE_IDS:
        if hid >= 15000:
            continue
        if re.search(rf"顯示.?{int(str(hid)[2:])}.{{0,12}}{hid}|{hid}.{{0,12}}顯示.?{int(str(hid)[2:])}", blob):
            fail(f"must not claim display number equals internal id {hid}", errors)



def check_exclusive_page(html: str, errors: list[str]) -> None:
    if not html:
        fail("exclusive: missing page", errors)
        return
    if 'lang="zh-Hant"' not in html:
        fail("exclusive: missing lang=zh-Hant", errors)
    if "<title>Top Heroes Wiki｜專武總表</title>" not in html:
        fail("exclusive: unexpected title", errors)
    for banner in ("未發佈", "本機預覽", "尚未發佈", "不是線上目錄", "preview-banner", "只供預覽", "只供本機預覽", "尚未列入公開"):
        if banner in html:
            fail(f"exclusive: unpublished banner still present: {banner}", errors)
    if "本頁列出 35 把專武" not in html:
        fail("exclusive: missing public lede", errors)
    if 'href="assets/css/site.css"' not in html:
        fail("exclusive: should use site CSS at assets/css/site.css", errors)

    nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', html, flags=re.S)
    if not nav_m:
        fail("exclusive: missing site-nav", errors)
    else:
        nav = nav_m.group(0)
        if re.search(r"heroes/\d+\.html", nav):
            fail("exclusive: site-nav should not link individual hero pages", errors)
        for needle in ("index.html", "index.html#heroes", "index.html#codex", "index.html#about"):
            if needle not in nav:
                fail(f"exclusive: site-nav missing {needle}", errors)

    t = text_of(html)
    for bad in ("部落", "壁克", "契約之獅", "愛情蠶惑", "未發佈樣板"):
        if bad in html or bad in t:
            fail(f"exclusive: forbidden term {bad}", errors)
    if "愛情蛊惑" not in t:
        fail("exclusive: missing official 愛情蛊惑 spelling", errors)
    if "思維火花" not in t or "共鳴" not in t:
        fail("exclusive: missing 發明家 exclusive 思維火花／共鳴", errors)
    if "2.80%" in html or "+2.80" in html:
        fail("exclusive: must not convert 英雄攻擊 280 into +2.80%", errors)
    if "依分欄推算" not in t:
        fail("exclusive: marginal ratios must be labelled 依分欄推算", errors)
    if "裝備屬性" not in t or "突破屬性" not in t:
        fail("exclusive: missing the two-track interface labels", errors)

    def rows_in(section_id: str) -> list[list[str]]:
        m = re.search(rf'id="{section_id}".*?(?=<section id="t|<section id="notes"|</main>)', html, flags=re.S)
        if not m:
            return []
        out = []
        for tr in re.findall(r"<tr>(.*?)</tr>", m.group(0), flags=re.S):
            cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            cells = [re.sub(r"[ \t\r\n]+", " ", c).strip() for c in cells]
            if cells:
                out.append(cells)
        return out

    t1 = [r for r in rows_in("t1") if r and r[0].endswith("級") and r[0] != "等級"]
    if len(t1) != 20:
        fail(f"exclusive table 1 should have 20 levels, got {len(t1)}", errors)
    elif t1[0] != ["1 級", "5", "5"] or t1[-1] != ["20 級", "150", "1185"]:
        fail(f"exclusive table 1 first/last row mismatch: {t1[0]} / {t1[-1]}", errors)

    t2 = [r for r in rows_in("t2") if r and r[0].isdigit()]
    if len(t2) != 25:
        fail(f"exclusive table 2 should have 25 steps, got {len(t2)}", errors)
    else:
        if t2[-1][0] != "25" or t2[-1][5] != "2385":
            fail(f"exclusive table 2 total should be 2385, got {t2[-1]}", errors)
        if "2 星" not in t2[9][-1]:
            fail(f"exclusive table 2 should mark the 2-star gate on step 10: {t2[9]}", errors)
        if "5 星" not in t2[24][-1]:
            fail(f"exclusive table 2 should mark the 5-star gate on step 25: {t2[24]}", errors)

    t3 = [r for r in rows_in("t3") if r and r[0] in ("聯盟", "自然", "部族")]
    if len(t3) != 35:
        fail(f"exclusive table 3 should have 35 rows, got {len(t3)}", errors)
    else:
        from collections import Counter
        split = Counter(r[0] for r in t3)
        if dict(split) != {"聯盟": 12, "自然": 11, "部族": 12}:
            fail(f"exclusive table 3 faction split mismatch {dict(split)}", errors)
        if t3[0][0] != "聯盟" or t3[12][0] != "自然" or t3[23][0] != "部族":
            fail("exclusive table 3 should be ordered 聯盟 → 自然 → 部族", errors)
        noah = [r for r in t3 if "諾亞金鈴" in "".join(r)]
        yarn = [r for r in t3 if "英雄絮語" in "".join(r)]
        if not noah or "森之少女" not in "".join(noah[0]) or "10036" not in "".join(noah[0]):
            fail(f"exclusive: 諾亞金鈴 should belong to 森之少女 10036, got {noah}", errors)
        if any("牧羊人" in "".join(r) and "諾亞金鈴" in "".join(r) and "不是牧羊人" not in "".join(r) for r in t3):
            fail("exclusive: 諾亞金鈴 must not be owned by 牧羊人", errors)
        if not yarn or "15032" not in "".join(yarn[0]):
            fail(f"exclusive: 英雄絮語 should belong to 15032, got {yarn}", errors)
        if any("老闆娘" in "".join(r) and "英雄絮語" in "".join(r) and "不與老闆娘合成同一人" not in "".join(r) for r in yarn):
            fail("exclusive: 英雄絮語 must not be merged with 老闆娘", errors)
        if any(r[0] != "—" and "牧羊人" in r[1] for r in t3):
            fail("exclusive table 3 must not include a 牧羊人 row", errors)
        if 'href="heroes/10031.html"' not in html:
            fail("exclusive: 審判官 should link to heroes/10031.html", errors)
        if 'href="heroes/10036.html"' not in html or 'href="heroes/15032.html"' not in html:
            fail("exclusive: 森之少女 and 15032 should have relative hero links", errors)

    if "公正領域冷卻時間減少1秒且範圍提升" not in t:
        fail("exclusive: missing 公正領域 rank 5 official text", errors)
    if "提高我方全體聯盟英雄4%減傷與10%生命值" not in t:
        fail("exclusive: missing 公正領域 rank 4 official text", errors)
    if "解鎖老闆娘全新專屬裝備" not in t:
        fail("exclusive: 英雄絮語 should quote the official 老闆娘 shard blurb", errors)
    if "1185" not in t and "1,185" not in t:
        fail("exclusive: missing upgrade total 1185", errors)
    if "2385" not in t and "2,385" not in t:
        fail("exclusive: missing breakthrough total 2385", errors)

    t4u = [r for r in rows_in("t4-up") if r and r[0].endswith("級") and r[0] != "等級"]
    if len(t4u) != 20:
        fail(f"exclusive upgrade-marginal should have 20 rows, got {len(t4u)}", errors)
    elif t4u[0][1:7] != ["5", "170", "4225", "280", "560", "3176"]:
        fail(f"exclusive lv1 marginal row should keep raw 英雄攻擊 280, got {t4u[0]}", errors)

    t4b = [r for r in rows_in("t4-br") if r and r[0].isdigit()]
    if len(t4b) != 25:
        fail(f"exclusive breakthrough-marginal should have 25 rows, got {len(t4b)}", errors)
    elif "英雄生命 4000" not in "".join(t4b[4]):
        fail(f"exclusive 1-star extra big attr missing: {t4b[4]}", errors)



def check_valhalla_page(html: str, errors: list[str]) -> None:
    if not html:
        fail("valhalla: missing page", errors)
        return
    if 'lang="zh-Hant"' not in html:
        fail("valhalla: missing lang=zh-Hant", errors)
    if "<title>Top Heroes Wiki｜英靈總表</title>" not in html:
        fail("valhalla: unexpected title", errors)
    for banner in ("未發佈", "本機預覽", "尚未發佈", "不是線上目錄", "preview-banner"):
        if banner in html:
            fail(f"valhalla: unpublished banner still present: {banner}", errors)
    if "本頁列出 15 隻英靈的升級素材、共通屬性、各隻專屬屬性與專屬技能，以及素材消耗對能力提升的邊際效果。" not in html:
        fail("valhalla: missing public lede", errors)
    if 'href="assets/css/site.css"' not in html:
        fail("valhalla: should use site CSS at assets/css/site.css", errors)
    nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', html, flags=re.S)
    if not nav_m:
        fail("valhalla: missing site-nav", errors)
    else:
        nav = nav_m.group(0)
        if re.search(r"heroes/\d+\.html", nav):
            fail("valhalla: site-nav should not link individual hero pages", errors)
        for needle in ("index.html", "index.html#heroes", "index.html#codex", "index.html#about"):
            if needle not in nav:
                fail(f"valhalla: site-nav missing {needle}", errors)
    for bad in ("契約之獅", "部落英雄", "壁克"):
        if bad in html:
            fail(f"valhalla: forbidden term {bad}", errors)
    it = text_of(html)
    if "3.60%" not in html:
        fail("valhalla: missing lv1 英雄攻擊 3.60%", errors)
    if re.search(r"\+3\.60%", html):
        fail("valhalla: must not write +3.60%", errors)
    if "320.00%" not in html or "960.00%" not in html:
        fail("valhalla: missing lv100 英雄攻擊／英雄生命 percentages", errors)
    if "627500" not in html:
        fail("valhalla: missing lv100 power 627500", errors)
    if "8,000" in html or "240,000" in html:
        fail("valhalla: show_type 1 values must not use thousands separators", errors)
    if "英雄攻擊（點數）" not in html or "英雄攻擊（百分比）" not in html:
        fail("valhalla: missing 點數／百分比 英雄攻擊 headers", errors)
    if "英雄生命（點數）" not in html or "英雄生命（百分比）" not in html:
        fail("valhalla: missing 點數／百分比 英雄生命 headers", errors)
    if "英雄等級上限" not in html:
        fail("valhalla: missing 英雄等級上限 header", errors)
    if "技能減傷" not in it or "50.00%" not in html:
        fail("valhalla: missing 技能減傷 50.00%", errors)
    if "英雄攻擊（3" in html or "英雄攻擊（103）" in html or "技能減傷（21）" in it:
        fail("valhalla: table headers should not keep attribute ids in parentheses", errors)
    if "3,163" not in it and "3163" not in html:
        fail("valhalla: missing shard total 3,163", errors)
    if "即可解鎖妖精英靈" not in it:
        fail("valhalla: missing official 妖精 shard phrase 即可解鎖妖精英靈", errors)
    if re.search(r'<span class="term">妖精</span>\s*<span class="term">英靈</span>', html):
        fail("valhalla: 即可解鎖妖精英靈 must not be split into two .term spans", errors)
    if "傷害提升60%" not in html:
        fail("valhalla: 惡作劇 rank 5 should fill both {0} with 60", errors)
    if "全體部落" not in html:
        fail("valhalla: 齊天鎮岳 rank 4 should quote 全體部落", errors)
    if "1-501,10001-19999" not in html:
        fail("valhalla: missing current unlock_server value", errors)
    if "1-501,10001-10728" not in html:
        fail("valhalla: missing historical unlock_server note", errors)
    if "已開放" in html and "不標已開放" not in it:
        fail("valhalla: must not mark spirits 已開放", errors)
    if "資料截至 2026-11-22" not in it:
        fail("valhalla: data cutoff should be 2026-11-22", errors)
    if "資料截至 2026-11-05" in it:
        fail("valhalla: must not use the global 2026-11-05 cutoff on this page", errors)
    if "依分欄推算" not in html:
        fail("valhalla: marginal ratios must be labelled 依分欄推算", errors)
    if 'href="heroes/10031.html"' not in html or 'href="heroes/10037.html"' not in html:
        fail("valhalla: missing relative hero links", errors)
    names = [
        "英靈「誓約之獅」", "英靈「聖靈天使」", "英靈「發條守衛」", "英靈「聖殿誓騎」", "英靈「聖諭祭司」",
        "英靈「翠竹青龍」", "英靈「蓮身護法」", "英靈「幽影梵蓮」", "英靈「織夢花靈」", "英靈「娜迦女王」",
        "英靈「沙漠死神」", "英靈「金焰犬神」", "英靈「上古魔猿」", "英靈「巫毒祭司」", "英靈「風暴領主」",
    ]
    missing = [n for n in names if n not in it]
    if missing:
        fail(f"valhalla: missing spirit names {missing}", errors)
    t1 = re.findall(r'id="u-lv-(\d+)"', html)
    if t1 != [str(i) for i in range(1, 101)]:
        fail(f"valhalla table 1 should have levels 1–100, got {t1[:5]}... n={len(t1)}", errors)
    t3 = re.findall(r'id="m-lv-(\d+)"', html)
    if t3 != [str(i) for i in range(1, 101)]:
        fail(f"valhalla marginal table should have levels 1–100, got n={len(t3)}", errors)



# 15 spirits on hero pages; sixth-attr display must follow the public 英靈總表 rules.
SPIRIT_HERO_SIXTH = {
    10043: ("薔薇公主", "技能減傷", "50.00%"),
    10031: ("審判官", "技能減傷", "50.00%"),
    10050: ("發明家", "技能減傷", "50.00%"),
    10033: ("聖徒", "技能增傷", "50.00%"),
    10046: ("主教", "增傷", "50.00%"),
    10042: ("豪士", "技能減傷", "50.00%"),
    10049: ("中壇元帥", "抗暴", "30.00%"),
    10051: ("花藝師", "技能減傷", "50.00%"),
    10037: ("妖精", "吸血", "30.00%"),
    10044: ("喚潮使", "吸血", "20.00%"),
    10039: ("沙漠王子", "抗暴", "30.00%"),
    10048: ("馴獸師", "格擋", "30.00%"),
    10047: ("行者", "增傷", "50.00%"),
    10045: ("女巫", "技能減傷", "50.00%"),
    10041: ("風暴聖女", "技能增傷", "50.00%"),
}
# Key-level sixth values at 1／25／50／75／100, keyed by the max display.
SIXTH_KEY_LEVELS = {
    "50.00%": ["0.00%", "10.00%", "25.00%", "35.00%", "50.00%"],
    "30.00%": ["0.00%", "6.00%", "15.00%", "21.00%", "30.00%"],
    "20.00%": ["0.00%", "4.00%", "10.00%", "14.00%", "20.00%"],
}
SPIRIT_SELF_ATTR = {
    10044: "技能增傷各階 0.00%／10.00%／10.00%／10.00%／10.00%",
    10041: "技能暴擊傷害各階 0.00%／15.00%／15.00%／15.00%／15.00%",
}
JUDGE_SIXTH_LEVELS = [
    ("1 級", "0.00%"),
    ("25 級", "10.00%"),
    ("50 級", "25.00%"),
    ("75 級", "35.00%"),
    ("100 級", "50.00%"),
]


def spirit_section(html: str) -> str:
    m = re.search(r"<h3>英靈.*?<h3>天賦", html, flags=re.S)
    return m.group(0) if m else ""


def check_hero_valhalla_attrs(errors: list[str]) -> None:
    """Hero-page 英靈 attrs must use the public table show_type rules."""
    for hid, (label, header, max_v) in SPIRIT_HERO_SIXTH.items():
        path = DOCS / "heroes" / f"{hid}.html"
        if not path.exists():
            fail(f"{label}: missing hero page {path}", errors)
            continue
        html = path.read_text(encoding="utf-8")
        block = spirit_section(html)
        if not block:
            fail(f"{label}: missing 英靈 subsection", errors)
            continue
        body = text_of(block)
        if "不換算成百分比" in body or "表上原值，不是英雄屬性" in body:
            fail(f"{label}: 英靈 subsection still says attributes are raw / not converted", errors)
        if "關鍵等級原值" in body or "技能減傷（原值）" in body:
            fail(f"{label}: 英靈 subsection still labels sixth attr as 原值", errors)
        if f"100 級時，第 6 項專屬屬性{header}是 {max_v}" not in body:
            fail(f"{label}: missing 100 級 {header} {max_v}", errors)
        if header not in body:
            fail(f"{label}: missing sixth-attr header {header}", errors)
        if "這套規則只用於英靈屬性，不套到專武、稱號或羈絆" not in body:
            fail(f"{label}: missing 英靈-only display-rule disclaimer", errors)
        if "1 級時這項是 0.00%" not in body:
            fail(f"{label}: should say lv1 sixth attr is 0.00%", errors)
        if f"{header}（" in body and "各階" not in header:
            # headers in the spirit section should not keep attribute ids
            import re as _re
            if _re.search(rf"{_re.escape(header)}（\d+", body):
                fail(f"{label}: sixth-attr header still has attribute id", errors)
        # Table values at 1／25／50／75／100.
        expected = SIXTH_KEY_LEVELS[max_v]
        cells = re.findall(r"<tr><td>([^<]+)</td><td>([^<]+)</td></tr>", block)
        got = [val for _, val in cells]
        if got != expected:
            fail(f"{label}: sixth-attr key levels {got} != {expected}", errors)
        if hid in SPIRIT_SELF_ATTR and SPIRIT_SELF_ATTR[hid] not in body:
            fail(f"{label}: missing skill attribute_self {SPIRIT_SELF_ATTR[hid]}", errors)
        if hid not in SPIRIT_SELF_ATTR and "技能列自身屬性" in body:
            fail(f"{label}: unexpected skill attribute_self line", errors)

    # 審判官: explicit lv1／25／50／75／100 readout; 專武 still stays raw.
    judge = (DOCS / "heroes" / "10031.html").read_text(encoding="utf-8")
    jblock = spirit_section(judge)
    jbody = text_of(jblock)
    for lv, val in JUDGE_SIXTH_LEVELS:
        if not re.search(rf"{re.escape(lv)}\s*{re.escape(val)}", jbody):
            fail(f"審判官: missing {lv} {val} in 英靈 table", errors)
    exclusive = section_html(judge, "exclusive") or ""
    if "這裡先照表上的點數寫，可能與面板上的百分比不同" not in text_of(exclusive):
        fail("審判官: 專武自身屬性 must still say unconverted table points in plain language", errors)
    # 織夢花靈 rank 5 both placeholders stay 60; 行者 rank 4 keeps 全體部落.
    fairy = text_of((DOCS / "heroes" / "10037.html").read_text(encoding="utf-8"))
    if "60" not in fairy:
        fail("妖精: 惡作劇 rank 5 should still fill placeholders with 60", errors)
    walker = text_of((DOCS / "heroes" / "10047.html").read_text(encoding="utf-8"))
    if "全體部落" not in walker:
        fail("行者: 齊天鎮岳 rank 4 should still quote 全體部落", errors)



def _cell_display(html_cell: str) -> str:
    """Strip tags and the space .term padding inserts before + signs."""
    t = re.sub(r"<[^>]+>", "", html_cell)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&")
    t = re.sub(r"[ \t\r\n]+", " ", t).strip()
    t = t.replace(" +", "+")
    return t


def _section_rows(html: str, section_id: str) -> list[list[str]]:
    m = re.search(
        rf'id="{re.escape(section_id)}".*?(?=<section id="t|<section id="notes"|</main>)',
        html,
        flags=re.S,
    )
    if not m:
        return []
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), flags=re.S):
        raw = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)
        cells = [_cell_display(c) for c in raw]
        if cells:
            out.append(cells)
    return out



def _section_chunk(html: str, section_id: str) -> str:
    m = re.search(
        rf'<section[^>]*id="{re.escape(section_id)}"[^>]*>.*?(?=<section |</main>)',
        html,
        flags=re.S,
    )
    return m.group(0) if m else ""


def check_mobile_catalog_markup(errors: list[str]) -> None:
    """Narrow-screen card / sticky-col markup on catalog pages only."""
    skins = SKINS.read_text(encoding="utf-8")
    exclusive = EXCLUSIVE.read_text(encoding="utf-8")
    valhalla = VALHALLA.read_text(encoding="utf-8")
    static_css = (ROOT / "static" / "css" / "site.css").read_text(encoding="utf-8")
    docs_css = (DOCS / "assets" / "css" / "site.css").read_text(encoding="utf-8")

    if static_css != docs_css:
        fail("static/css/site.css and docs/assets/css/site.css should be identical", errors)
    for needle, label in (
        ("@media (max-width: 44rem)", "44rem card breakpoint"),
        (".table-wrap.table-cards", "table-cards rules"),
        (".table-wrap.table-sticky-col", "sticky first-column rules"),
        (".table-wrap.table-sticky-col-2", "two-column sticky rules"),
    ):
        if needle not in docs_css:
            fail(f"site.css missing {label}", errors)
    if "preview-banner" in docs_css or "尚未發佈" in docs_css:
        fail("site.css should not include the unpublished preview banner", errors)

    def expect(chunk: str, label: str, *needles: str) -> None:
        if not chunk:
            fail(f"{label}: missing section", errors)
            return
        for n in needles:
            if n not in chunk:
                fail(f"{label}: missing {n}", errors)

    def forbid(chunk: str, label: str, *needles: str) -> None:
        if not chunk:
            fail(f"{label}: missing section", errors)
            return
        for n in needles:
            if n in chunk:
                fail(f"{label}: should not contain {n}", errors)

    expect(_section_chunk(skins, "t1"), "skins 表一", "table-cards", 'data-label="造型"', "card-title")
    expect(_section_chunk(skins, "t1-sum"), "skins 表一附", "table-cards", 'data-label="英雄"', "card-title")
    forbid(_section_chunk(skins, "scope-coin"), "skins 時裝幣與品質", "table-cards", "data-label")
    expect(_section_chunk(exclusive, "t3"), "exclusive 表三", "table-cards", 'data-label="英雄"', 'data-label="專武"', "card-title")
    expect(_section_chunk(exclusive, "t2-aura"), "exclusive 突破光環", "table-cards")
    expect(_section_chunk(exclusive, "t2"), "exclusive 表二", "table-sticky-col")
    expect(_section_chunk(exclusive, "t4-up"), "exclusive 表四升級", "table-sticky-col")
    expect(_section_chunk(exclusive, "t4-br"), "exclusive 表四突破", "table-sticky-col")
    forbid(_section_chunk(exclusive, "t1"), "exclusive 表一", "table-cards", "table-sticky-col", "data-label")
    expect(_section_chunk(valhalla, "t1"), "valhalla 表一", "table-sticky-col")
    expect(_section_chunk(valhalla, "t3"), "valhalla 表三", "table-sticky-col")
    expect(_section_chunk(valhalla, "t2-sixth"), "valhalla 專屬屬性成長", "table-sticky-col-2")
    expect(_section_chunk(valhalla, "t2"), "valhalla 表二", "table-cards", 'data-label="英靈"', "card-title")
    expect(_section_chunk(valhalla, "t1-batch"), "valhalla unlock 批次", "table-cards", 'data-label="英靈"')
    forbid(_section_chunk(valhalla, "t1-seg"), "valhalla 消耗分段", "table-cards", "table-sticky-col", "data-label")

    for path in sorted((DOCS / "heroes").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        for needle in ("table-cards", "table-sticky-col", "data-label", "card-title", "尚未發佈", "preview-banner"):
            if needle in html:
                fail(f"{path.name}: hero page should not contain {needle}", errors)


def check_skins_page(html: str, errors: list[str]) -> None:
    if not html:
        fail("skins: missing page", errors)
        return
    if 'lang="zh-Hant"' not in html:
        fail("skins: missing lang=zh-Hant", errors)
    if "<title>Top Heroes Wiki｜造型總表</title>" not in html:
        fail("skins: unexpected title", errors)
    if "本機預覽" in html or "尚未發佈" in html:
        fail("skins: unpublished banner still present", errors)
    for banner in ("未發佈", "不是線上目錄", "preview-banner", "只供預覽", "尚未列入公開"):
        if banner in html:
            fail(f"skins: unpublished banner still present: {banner}", errors)
    if "本頁列出英雄造型圖鑑的可收集造型、成對造型、收集套裝、可升星效果與賽季限定效果，以及每位英雄可收集造型的屬性加總。" not in html:
        fail("skins: missing public lede", errors)
    if 'href="assets/css/site.css"' not in html:
        fail("skins: should use site CSS at assets/css/site.css", errors)
    if "../docs/" in html or "preview/" in html:
        fail("skins: public page should not use preview-relative paths", errors)

    nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', html, flags=re.S)
    if not nav_m:
        fail("skins: missing site-nav", errors)
    else:
        nav = nav_m.group(0)
        if re.search(r"heroes/\d+\.html", nav):
            fail("skins: site-nav should not link individual hero pages", errors)
        for needle in ("index.html", "index.html#heroes", "index.html#codex", "index.html#about"):
            if needle not in nav:
                fail(f"skins: site-nav missing {needle}", errors)

    it = text_of(html)
    if "資料截至 2026-11-23" not in it:
        fail("skins: data cutoff should be 2026-11-23", errors)
    if "資料截至 2026-11-05" in it:
        fail("skins: must not use the global 2026-11-05 cutoff on this page", errors)
    if "app-1.129.12_table-1.0.43173" not in html:
        fail("skins: missing LocalLow pack name", errors)
    if html.count("<table>") != 13:
        fail(f"skins: expected 13 tables (12 plus 表一附), got {html.count('<table>')}", errors)

    for bad in ("契約之獅", "壁克", "由玩家確認", "豐收護衛"):
        if bad in html or bad in it:
            fail(f"skins: forbidden term {bad}", errors)
    if re.search(r"(?<![全])部落", it) and "全體部落" not in it:
        # 部落 only allowed if an official string uses it; skins catalog should not say 部落
        if "部落" in it:
            fail("skins: must not write 部落 (official term is 部族)", errors)
    if "部落" in it:
        fail("skins: must not write 部落 (official term is 部族)", errors)

    # Table 1: 137 collectable skins
    t1 = [r for r in _section_rows(html, "t1") if r and r[0] in ("聯盟", "自然", "部族")]
    if len(t1) != 137:
        fail(f"skins table 1 should have 137 collectable rows, got {len(t1)}", errors)
    if "聖徒 技能增傷+8.00%" not in it or "全部 英雄攻擊+6.00%" not in it:
        fail("skins: missing 聖徒·伊萊雯 max-star collect attributes", errors)
    if "發明家 突破防禦+2000" not in it:
        fail("skins: missing 發明家·大白鯊 突破防禦+2000", errors)
    if "黑潮來襲時扣除氧氣值減少+10.00%" not in it:
        fail("skins: missing 大白鯊 season effect", errors)
    if "審判官·富饒領主" not in it or "豪士·武道宗師" not in it:
        fail("skins: missing the 2026-11-22 pair skins", errors)
    if "紅水晶採集速度+20.00%" not in it or "防禦+2000" not in it:
        fail("skins: missing new pair attributes", errors)
    if "審判·殘月騎士" not in it or "審判·狂熱之愛" not in it:
        fail("skins: official 審判 skin names should be quoted as-is", errors)

    # 表一附: 57 heroes, roster order, locked sums
    sum_rows = [r for r in _section_rows(html, "t1-sum") if r and r[0] in ("聯盟", "自然", "部族")]
    if len(sum_rows) != 57:
        fail(f"skins 表一附 should have 57 hero rows, got {len(sum_rows)}", errors)
    elif sum(int(r[2]) for r in sum_rows) != 137:
        fail(f"skins 表一附 counts should sum to 137, got {sum(int(r[2]) for r in sum_rows)}", errors)
    else:
        names = [r[1] for r in sum_rows]
        expected = LEAGUE_NAMES + NATURE_NAMES + TRIBE_NAMES
        # display may include （未開放）
        core = [re.sub(r"（未開放）\s*$", "", n).strip() for n in names]
        if core != expected:
            fail(f"skins 表一附 order mismatch: {core[:5]}... vs roster", errors)
        if names[LEAGUE_NAMES.index("牧羊人")] != "牧羊人（未開放）" and "牧羊人（未開放）" not in names:
            # after _cell_display, 牧羊人 （未開放） may have a space from .term
            if not any(n.replace(" ", "") == "牧羊人（未開放）" for n in names):
                fail(f"skins 表一附: 牧羊人 should be labelled 未開放, got {names}", errors)
        boss = [n for n in names if "老闆娘" in n]
        if any("未開放" in n for n in boss):
            fail("skins 表一附: 老闆娘 must not be marked 未開放", errors)
        saint = next((r for r in sum_rows if r[1].replace(" ", "") == "聖徒"), None)
        inventor = next((r for r in sum_rows if r[1].replace(" ", "") == "發明家"), None)
        if not saint or saint[2] != "6":
            fail(f"skins 表一附: 聖徒 should have 6 collectable skins, got {saint}", errors)
        expected_self = "聖徒 暴擊+3.00%；聖徒 對召喚物傷害+10.00%；聖徒 必殺技係數+20.00%；聖徒 技能增傷+8.00%"
        expected_team = "全部 英雄攻擊+21.00%；全部 英雄生命+70.00%；全部 聯盟英雄減傷+2.00%"
        if not saint or saint[3].replace("； ", "；") != expected_self and saint[3] != expected_self:
            # normalize spaces around ； too
            got = re.sub(r"\s*；\s*", "；", saint[3] if saint else "")
            if got != expected_self:
                fail(f"skins 表一附 聖徒自身 mismatch: {saint[3] if saint else None!r}", errors)
        if saint:
            got_team = re.sub(r"\s*；\s*", "；", saint[4])
            if got_team != expected_team:
                fail(f"skins 表一附 聖徒全部 mismatch: {saint[4]!r}", errors)
            if saint[5] != "無":
                fail(f"skins 表一附 聖徒成對 should be 無, got {saint[5]!r}", errors)
            if "對碎石巨像、暮光渡鴉的傷害提升+15.00%" not in saint[6].replace(" ", ""):
                if "對碎石巨像、暮光渡鴉的傷害提升+15.00%" not in saint[6] and "對碎石巨像、暮光渡鴉的傷害提升 +15.00%" not in saint[6]:
                    fail(f"skins 表一附 聖徒賽季 missing 闇月 effect: {saint[6]!r}", errors)
            if "對碎石巨像" in saint[3] + saint[4]:
                fail("skins 表一附: 聖徒 season effect leaked into main sum", errors)
        if inventor:
            got_self = re.sub(r"\s*；\s*", "；", inventor[3])
            got_team = re.sub(r"\s*；\s*", "；", inventor[4])
            if got_self != "發明家 突破防禦+2000；發明家 技能增傷+8.00%":
                fail(f"skins 表一附 發明家自身 mismatch: {inventor[3]!r}", errors)
            if got_team != "全部 英雄攻擊+6.00%；全部 英雄生命+20.00%":
                fail(f"skins 表一附 發明家全部 mismatch: {inventor[4]!r}", errors)
            if "黑潮來襲時扣除氧氣值減少+10.00%" in inventor[3] + inventor[4]:
                fail("skins 表一附: 大白鯊 season effect leaked into main sum", errors)
            if "黑潮來襲時扣除氧氣值減少+10.00%" not in inventor[6] and "黑潮來襲時扣除氧氣值減少 +10.00%" not in inventor[6]:
                fail(f"skins 表一附 發明家賽季 missing 大白鯊 effect: {inventor[6]!r}", errors)
        for nid in ("15032", "15033", "15039"):
            row = next((r for r in sum_rows if r[1].replace(" ", "") == nid), None)
            if row is None:
                fail(f"skins 表一附: missing id-only row {nid}", errors)

    if "這不是遊戲面板上的單一數字" not in it:
        fail("skins: 表一附 must say the sums are not a single in-game panel figure", errors)
    if "百分比是數字相加" not in it:
        fail("skins: 表一附 must say percentages are added, not multiplied", errors)
    if "收集套裝要湊數件造型" not in it:
        fail("skins: must note collection suits are not included in the per-hero sums", errors)
    if "AttrListDic" not in html:
        fail("skins: data notes should mention AttrListDic is not the display source", errors)
    if "不改讀" not in it and "不改讀 AttrListDic" not in it:
        if "不改讀" not in html:
            fail("skins: must say display values are not read from AttrListDic", errors)

    if "聖焰神衛" in it and "不收入名錄" not in it:
        fail("skins: 聖焰神衛 must not be listed as a live suit without the unused-string note", errors)
    # live suit table should not have 聖焰神衛 / 幽冥使者 as a suit name cell
    suit_rows = _section_rows(html, "t3")
    suit_names = [r[0] for r in suit_rows if r and r[0] not in ("套裝",)]
    for forbidden in ("聖焰神衛", "幽冥使者", "豐收護衛"):
        if any(forbidden == n or n.startswith(forbidden) for n in suit_names):
            fail(f"skins: {forbidden} must not appear as a live suit", errors)
    if len([n for n in suit_names if n != "套裝"]) not in (10, 11):
        # header plus 10, or 10 if header filtered
        live = [n for n in suit_names if n and n != "套裝"]
        if len(live) != 10:
            fail(f"skins table 3 should have 10 suits, got {len(live)}: {live}", errors)

    if 'href="heroes/10031.html"' not in html or 'href="heroes/10033.html"' not in html:
        fail("skins: missing relative hero links", errors)
    if re.search(r'href="[^"]*skins/[^"]+"', html):
        fail("skins: must not invent skin detail subpage links", errors)
    if "雲海紀行是 S6" in it or "官方名稱是 S6" in it or "skin_season_6 是 S6" in it:
        fail("skins: must not claim skin_season_6 is the official S6 name", errors)

    footer = re.search(r'<footer class="site-footer">.*?</footer>', html, flags=re.S)
    if not footer or "資料截至 2026-11-23" not in text_of(footer.group(0)):
        fail("skins: footer cutoff should be 2026-11-23", errors)



PUBLISHED_CATALOG_HREFS = (
    "exclusive.html", "valhalla.html", "skins.html",
    "equipment.html", "lord-equipment.html", "troops.html",
    "artifacts.html", "pets.html", "runes.html",
    "talents.html", "tech.html", "decorations.html", "castle.html",
)
UNPUBLISHED_BANNER = (
    "本機預覽", "尚未發佈", "不是線上目錄", "preview-banner",
    "只供預覽", "只供本機預覽", "尚未列入公開", "不會寫進公開站",
    "沒有接入網站組建腳本", "（本機預覽）",
)
PREVIEW_PATHS = (
    "equipment-tables.html", "lord-equipment-tables.html", "troop-tables.html",
    "artifact-tables.html", "pet-tables.html", "rune-tables.html",
    "preview/", "../docs/",
)


def check_adjacent_term_spans(html: str, label: str, errors: list[str]) -> None:
    if re.search(r'</span>\s*<span class="term">', html):
        fail(f"{label}: long official phrases must not be split into adjacent .term spans", errors)


def check_public_catalog_shell(html: str, label: str, title: str, cutoff: str, errors: list[str]) -> None:
    if not html:
        fail(f"{label}: missing page", errors)
        return
    if 'lang="zh-Hant"' not in html:
        fail(f"{label}: missing lang=zh-Hant", errors)
    if f"<title>{title}</title>" not in html:
        fail(f"{label}: unexpected title", errors)
    if "（本機預覽）" in html:
        fail(f"{label}: title or body still has （本機預覽）", errors)
    for banner in UNPUBLISHED_BANNER:
        if banner in html:
            fail(f"{label}: unpublished banner still present: {banner}", errors)
    if 'href="assets/css/site.css"' not in html:
        fail(f"{label}: should use site CSS at assets/css/site.css", errors)
    for needle in PREVIEW_PATHS:
        if needle in html:
            fail(f"{label}: leftover preview path {needle}", errors)
    nav_m = re.search(r'<nav class="site-nav"[^>]*>.*?</nav>', html, flags=re.S)
    if not nav_m:
        fail(f"{label}: missing site-nav", errors)
    else:
        nav = nav_m.group(0)
        if re.search(r"heroes/\d+\.html", nav):
            fail(f"{label}: site-nav should not link individual hero pages", errors)
        for needle in ("index.html", "index.html#heroes", "index.html#codex", "index.html#about"):
            if needle not in nav:
                fail(f"{label}: site-nav missing {needle}", errors)
    footer = re.search(r'<footer class="site-footer">.*?</footer>', html, flags=re.S)
    if not footer or f"資料截至 {cutoff}" not in text_of(footer.group(0)):
        fail(f"{label}: footer cutoff should be {cutoff}", errors)
    check_adjacent_term_spans(html, label, errors)
    t = text_of(html)
    if "尚未發佈" in t or "本機預覽" in t:
        fail(f"{label}: stripped text still mentions unpublished preview status", errors)
    for bad in ("繁絆", "精録", "魚缺", "魚缽", "鐵喉", "部落的伝護", "部族的庇護"):
        if bad in html or bad in t:
            fail(f"{label}: forbidden typo or rewritten official term {bad}", errors)


def check_equipment_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "equipment", "Top Heroes Wiki｜裝備總表", "2026-11-23", errors)
    if not html:
        return
    if "本頁列出四件套裝備的 12 個實際使用套裝" not in html:
        fail("equipment: missing public lede", errors)
    if 'href="exclusive.html"' not in html:
        fail("equipment: should link to exclusive.html", errors)
    t = text_of(html)
    if "部落護甲" not in t or "部落戰靴" not in t:
        fail("equipment: official 部落護甲／部落戰靴 must be kept", errors)


def check_lord_equipment_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "lord-equipment", "Top Heroes Wiki｜領主裝備總表", "2026-11-23", errors)
    if not html:
        return
    if "本頁列出七件領主裝備的寫入屬性" not in html:
        fail("lord-equipment: missing public lede", errors)
    if 'href="equipment.html"' not in html:
        fail("lord-equipment: should link to equipment.html", errors)
    if 'href="exclusive.html"' not in html:
        fail("lord-equipment: should link to exclusive.html", errors)


def check_troops_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "troops", "Top Heroes Wiki｜士兵總表", "2026-11-23", errors)
    if not html:
        return
    if "本頁列出士兵的名稱、單兵數值" not in html:
        fail("troops: missing public lede", errors)
    for href in ("equipment.html", "lord-equipment.html", "exclusive.html", "skins.html"):
        if f'href="{href}"' not in html:
            fail(f"troops: should link to {href}", errors)
    t = text_of(html)
    if "天穹聯盟戰士" not in t or "攻擊 50" not in t or "生命 900" not in t:
        fail("troops: missing locked 天穹聯盟戰士 1012 攻擊 50、生命 900", errors)


def check_artifacts_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "artifacts", "Top Heroes Wiki｜秘寶總表", "2026-11-23", errors)
    if not html:
        return
    if "本頁列出可佩戴到隊列上的秘寶" not in html:
        fail("artifacts: missing public lede", errors)
    for href in ("equipment.html", "lord-equipment.html", "troops.html", "exclusive.html"):
        if f'href="{href}"' not in html:
            fail(f"artifacts: should link to {href}", errors)
    t = text_of(html)
    if "2780／19100" not in t:
        fail("artifacts: quality 4 0-star attack/HP 2780／19100 missing", errors)
    if re.search(r"<td>4</td><td>3530／23600</td>", html):
        fail("artifacts: quality 4 0-star row must not use 3530／23600", errors)
    if "3530／23600" in t and "該數字未出現在升星表" not in t:
        fail("artifacts: 3530／23600 may only appear as the rejected chapter-20 figure", errors)


def check_pets_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "pets", "Top Heroes Wiki｜寵物總表", "2026-11-24", errors)
    if not html:
        return
    if "本頁列出官方界面所稱的「寵物」" not in html:
        fail("pets: missing public lede", errors)
    for href in ("equipment.html", "lord-equipment.html", "troops.html", "artifacts.html", "exclusive.html", "valhalla.html", "holybeasts.html", "pals.html"):
        if f'href="{href}"' not in html:
            fail(f"pets: should link to {href}", errors)
    t = text_of(html)
    if "鐵喙" not in t:
        fail("pets: missing official name 鐵喙", errors)
    if "部落的庇護" not in t:
        fail("pets: official skill name 部落的庇護 must be kept", errors)
    if "魚缸" not in t:
        fail("pets: 魚缸 must be kept", errors)


def check_runes_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "runes", "Top Heroes Wiki｜符文總表", "2026-11-24", errors)
    if not html:
        return
    if "本頁列出官方界面所稱的「符文」" not in html:
        fail("runes: missing public lede", errors)
    for href in (
        "equipment.html", "lord-equipment.html", "troops.html", "artifacts.html",
        "pets.html", "holybeasts.html", "pals.html", "exclusive.html", "valhalla.html", "skins.html",
    ):
        if f'href="{href}"' not in html:
            fail(f"runes: should link to {href}", errors)
    t = text_of(html)
    if "1036" not in t:
        fail("runes: missing locked 絕對強擊 level-8 value 1036", errors)
    if "精煉" not in t:
        fail("runes: missing 精煉", errors)
    if "20006" in t and "秘寶生命" in t:
        # official note may mention that name_20004 is 秘寶生命 and must not be used as the official name for 20006
        if "不把它當作正式名稱" not in t and "不把它當作正式名" not in t:
            fail("runes: 20006 must not be presented as official 秘寶生命", errors)
    if "team_rune_name_00" in html and "player_rune" in t:
        # type numbers must not be written as team_rune_name_00N
        if re.search(r"player_rune[^.]{0,80}type\s*[1-9][^.]{0,80}team_rune_name_00", t):
            fail("runes: must not name a player_rune type as team_rune_name_00N", errors)


def check_talents_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "talents", "Top Heroes Wiki｜天賦總表", "2026-11-21", errors)
    if not html:
        return
    if "本頁分開列出兩套系統，不要混為一套：英雄天賦" not in html:
        fail("talents: missing public lede", errors)
    if "領主大廳" not in html:
        fail("talents: missing official 領主大廳", errors)
    for href in (
        "exclusive.html", "valhalla.html", "skins.html",
        "equipment.html", "lord-equipment.html", "troops.html",
        "artifacts.html", "pets.html", "runes.html",
        "tech.html", "decorations.html", "castle.html",
    ):
        if f'href="{href}"' not in html:
            fail(f"talents: should link to {href}", errors)
    t = text_of(html)
    if "英雄天賦" not in t or "領主天賦" not in t:
        fail("talents: must keep the two official talent systems", errors)
    if "藥劑師" not in t or "舞孃" not in t or "審判官" not in t:
        fail("talents: missing locked confirmed-panel heroes", errors)
    if "90.00%" not in t:
        fail("talents: missing locked 審判官 panel percentage 90.00%", errors)
    if "不在本頁展開" not in t:
        fail("talents: other catalogs should remain out of scope for this page", errors)


def check_tech_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "tech", "Top Heroes Wiki｜科技總表", "2026-11-15", errors)
    if not html:
        return
    if "本頁主體是玩家科技（官方名稱「科技」" not in html:
        fail("tech: missing public lede", errors)
    if "attr_category</code> 25" not in html and "attr_category 25" not in html:
        fail("tech: attr_category 25 should remain in 資料說明", errors)
    for href in (
        "exclusive.html", "valhalla.html", "skins.html",
        "equipment.html", "lord-equipment.html", "troops.html",
        "artifacts.html", "pets.html", "runes.html",
        "talents.html", "decorations.html", "castle.html",
    ):
        if f'href="{href}"' not in html:
            fail(f"tech: should link to {href}", errors)
    t = text_of(html)
    if "公會科技" not in t:
        fail("tech: missing official 公會科技", errors)
    if "不在本頁展開" not in t:
        fail("tech: other catalogs should remain out of scope for this page", errors)


def check_decorations_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "decorations", "Top Heroes Wiki｜裝飾物總表", "2026-11-22", errors)
    if not html:
        return
    if "本頁分開列出兩套系統，不要混為一套：擺在自己主城的城鎮裝飾" not in html:
        fail("decorations: missing public lede", errors)
    for href in (
        "exclusive.html", "valhalla.html", "skins.html",
        "equipment.html", "lord-equipment.html", "troops.html",
        "artifacts.html", "pets.html", "runes.html",
        "talents.html", "tech.html", "castle.html",
    ):
        if f'href="{href}"' not in html:
            fail(f"decorations: should link to {href}", errors)
    t = text_of(html)
    if "城鎮裝飾" not in t or "公會裝飾物" not in t:
        fail("decorations: must keep the two official decoration systems", errors)
    if "雲海紀行" not in t:
        fail("decorations: missing official suit name 雲海紀行", errors)
    if "當成已核對的官方賽季名" not in t:
        fail("decorations: 雲海紀行 must not be treated as a confirmed official season name", errors)
    if "統禦" not in t:
        fail("decorations: official 統禦 must be kept", errors)
    if "不在本頁展開" not in t:
        fail("decorations: castle appearance should remain out of scope for this page", errors)


def check_castle_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "castle", "Top Heroes Wiki｜城堡外觀總表", "2026-11-23", errors)
    if not html:
        return
    if "本頁主體是城堡造型（介面欄位「城堡造型」）" not in html:
        fail("castle: missing public lede", errors)
    if "City_Skin_1" not in html:
        fail("castle: City_Skin_1 key should remain in 資料說明", errors)
    for href in (
        "exclusive.html", "valhalla.html", "skins.html",
        "equipment.html", "lord-equipment.html", "troops.html",
        "artifacts.html", "pets.html", "runes.html",
        "talents.html", "tech.html", "decorations.html",
    ):
        if f'href="{href}"' not in html:
            fail(f"castle: should link to {href}", errors)
    t = text_of(html)
    for name in ("蛋糕城", "飛翔號", "美味史萊姆", "夢幻摩天輪"):
        if name not in t:
            fail(f"castle: missing locked skin {name}", errors)
    if "0 星＝level 1" not in t and "0 星＝表的 level 1" not in t:
        fail("castle: missing locked 0-star = level 1 wording", errors)
    if "不是 68 組通例" not in t and "不是 68 組都已用面板核過 0 星" not in t:
        fail("castle: 0-star/1-star lock must not be generalized to all 68 groups", errors)
    if "火砲要塞" not in t:
        fail("castle: goods_desc_314 list should include 火砲要塞", errors)
    if "不列入本頁主體" not in t:
        fail("castle: decorations should remain out of scope for the main catalog body", errors)



FORBIDDEN_VISIBLE_ATTRIBUTION = (
    "玩家確認",
    "由玩家在面板確認",
    "尚未經玩家面板確認",
    "依玩家確認",
    "已確認的前服",
    "已用面板確認",
    "玩家說法",
)


def check_attribution_cleanup(errors: list[str]) -> None:
    """Visible body (before 資料說明) must state facts without confirmation-source wording."""
    hero_dir = DOCS / "heroes"
    paths = sorted(hero_dir.glob("*.html"))
    if len(paths) != 57:
        fail(f"expected 57 hero pages, found {len(paths)}", errors)
    for path in paths:
        html = path.read_text(encoding="utf-8")
        vis = visible_before_notes(html)
        all_text = text_of(html)
        label = path.stem
        for phrase in FORBIDDEN_VISIBLE_ATTRIBUTION:
            if phrase in vis:
                fail(f"{label}: visible body still has {phrase}", errors)
        if "（本機預覽）" in html or "本機預覽" in vis:
            fail(f"{label}: must not introduce a preview banner", errors)
        hid = int(path.stem)
        if hid in {10029, 15032, 15033, 15039}:
            if "第二組標籤本頁不推算" not in vis:
                fail(f"{label}: visible body should still say 第二組標籤本頁不推算", errors)
            if "第二組標籤尚未經玩家面板確認，本頁不推算" not in all_text:
                fail(f"{label}: data notes should keep the unconfirmed-second-group source", errors)
        if "後項的官方說明沒有百分比" in all_text or "後兩項的官方說明沒有百分比" in all_text:
            if "後項的官方說明沒有百分比" not in vis and "後兩項的官方說明沒有百分比" not in vis:
                fail(f"{label}: official no-percentage fact should remain in the visible body", errors)
        if "百分比按本站統一規則換算，說明見資料說明。" not in vis and "有兩個天賦槽" in vis:
            # quality-1 heroes still have talent intro; all published heroes have talents
            pass
        if "有" in vis and "個天賦槽" in vis:
            if "百分比按本站統一規則換算，說明見資料說明。" not in vis:
                # some heroes might only have point talents; only require when percents exist
                if "%" in (section_html(html, "spirit-talents") or "") and "90.00%" in all_text:
                    fail(f"{label}: talent intro should cite the site conversion rule", errors)

    for path, label in (
        (DOCS / "equipment.html", "裝備總表"),
        (DOCS / "talents.html", "天賦總表"),
    ):
        html = path.read_text(encoding="utf-8")
        vis = visible_before_notes(html)
        all_text = text_of(html)
        for phrase in FORBIDDEN_VISIBLE_ATTRIBUTION:
            if phrase in vis:
                fail(f"{label}: visible body still has {phrase}", errors)
        if "（本機預覽）" in html or "本機預覽" in vis:
            fail(f"{label}: must not introduce a preview banner", errors)
        if label == "裝備總表":
            if "這三套尚未開放" not in vis:
                fail("裝備總表: visible body should say the three later suits are 尚未開放", errors)
            if "藥劑師歸自然" not in vis:
                fail("裝備總表: visible body should still say 藥劑師歸自然", errors)
            if "依玩家確認" not in all_text or "藥劑師歸自然亦依玩家確認" not in all_text:
                fail("裝備總表: data notes should keep the confirmation source", errors)
            if "不評定套裝強弱" not in vis:
                fail("裝備總表: must keep the no-ranking rule", errors)
        if label == "天賦總表":
            if "以面板看得到的為準" not in vis:
                fail("天賦總表: lede should say 以面板看得到的為準", errors)
            if "不評定天賦強弱" not in vis:
                fail("天賦總表: must keep the no-ranking rule", errors)
            if "舊表與面板對照" not in vis:
                fail("天賦總表: section title should be 舊表與面板對照", errors)
            if "舊表對應與已確認面板" in vis:
                fail("天賦總表: must not keep the old confirmed-panel title in the visible body", errors)
            if "藥劑師" not in vis or "舞孃" not in vis or "審判官" not in vis or "90.00%" not in vis:
                fail("天賦總表: visible body should keep the locked panel examples", errors)
            if "已確認的前服面板" not in all_text:
                fail("天賦總表: data notes should keep the confirmed 前服 panel source", errors)



def check_holybeasts_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "holybeasts", "Top Heroes Wiki｜守護魔獸總表", "2026-11-05", errors)
    if not html:
        return
    if "本頁列出官方界面所稱的「守護魔獸」" not in html:
        fail("holybeasts: missing public lede", errors)
    for href in ("pets.html", "valhalla.html", "pals.html"):
        if f'href="{href}"' not in html:
            fail(f"holybeasts: should link to {href}", errors)
    t = text_of(html)
    vis = visible_before_notes(html)
    for name in (
        "聯盟·血月女王", "部族·銀月統帥", "自然·熔岩霸龍",
        "聯盟·狂刃阿蒙", "部族·黃金巨蠍", "自然·冰霜鳳凰",
    ):
        if name not in t:
            fail(f"holybeasts: missing official name {name}", errors)
    for phrase in FORBIDDEN_VISIBLE_ATTRIBUTION:
        if phrase in vis:
            fail(f"holybeasts: visible body still has {phrase}", errors)
    if "字串表沒有名稱與說明" not in vis:
        fail("holybeasts: unnamed skills should be marked in the visible body", errors)
    if "群狼統率" not in vis or "群狼統帥" not in vis or "銀月統率" not in vis:
        fail("holybeasts: official skill wording 群狼統率／群狼統帥／銀月統率 must be kept", errors)
    if "聯盟共鳴" not in vis or "部族共鳴" not in vis or "自然共鳴" not in vis:
        fail("holybeasts: resonance skill official names should be kept", errors)
    if "魔核" not in vis or "魔源之石" not in vis:
        fail("holybeasts: missing official 魔核／魔源之石", errors)
    if "16 級出現" in vis:
        fail("holybeasts: must not say 魔核 appears at level 16", errors)
    if "20、30" not in vis and "20、30、40" not in vis:
        fail("holybeasts: 魔核 should be listed on levels 20, 30, …, 170", errors)
    if "部落" in vis:
        fail("holybeasts: must not write 部落 (official term is 部族)", errors)
    if "雲海紀行" in vis:
        fail("holybeasts: must not present 雲海紀行 as a verified official season name", errors)
    if "玩家確認" in vis:
        fail("holybeasts: visible body must not mention 玩家確認", errors)



def check_pals_page(html: str, errors: list[str]) -> None:
    check_public_catalog_shell(html, "pals", "Top Heroes Wiki｜帕魯總表", "2026-11-22", errors)
    if not html:
        return
    if "本頁列出官方界面所稱的「帕魯」" not in html:
        fail("pals: missing public lede", errors)
    for href in ("pets.html", "holybeasts.html", "valhalla.html"):
        if f'href="{href}"' not in html:
            fail(f"pals: should link to {href}", errors)
    t = text_of(html)
    vis = visible_before_notes(html)
    for name in ("礦石史萊姆", "百夫長", "帕魯營地", "帕魯契約", "種族光環"):
        if name not in t:
            fail(f"pals: missing official name {name}", errors)
    for phrase in FORBIDDEN_VISIBLE_ATTRIBUTION:
        if phrase in vis:
            fail(f"pals: visible body still has {phrase}", errors)
    if "部落" in vis:
        fail("pals: must not write 部落 (official term is 部族)", errors)
    if "雲海紀行" in vis:
        fail("pals: must not present 雲海紀行 as a verified official season name", errors)
    if "玩家確認" in vis:
        fail("pals: visible body must not mention 玩家確認", errors)
    if "字串表沒有內容" not in vis:
        fail("pals: missing-name fields should be marked in the visible body", errors)


def check_index_published_catalogs(index: str, errors: list[str]) -> None:
    check_adjacent_term_spans(index, "index", errors)
    t = text_of(index)
    if "尚未發佈" in t or "本機預覽" in t:
        fail("index: stripped text still mentions unpublished preview status", errors)
    footer = re.search(r'<footer class="site-footer">.*?</footer>', index, flags=re.S)
    if not footer or "資料截至 2026-11-05" not in text_of(footer.group(0)):
        fail("index: footer cutoff should remain 2026-11-05", errors)


def main() -> int:
    errors = []
    for p in (
        INDEX, EXCLUSIVE, VALHALLA, SKINS,
        EQUIPMENT, LORD_EQUIPMENT, TROOPS, ARTIFACTS, PETS, HOLYBEASTS, PALS, RUNES,
        TALENTS, TECH, DECORATIONS, CASTLE,
        JUDGE, NUN, ROSE, INVENTOR,
    ):
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

    exclusive_html = EXCLUSIVE.read_text(encoding="utf-8")
    valhalla_html = VALHALLA.read_text(encoding="utf-8")
    skins_html = SKINS.read_text(encoding="utf-8")
    equipment_html = EQUIPMENT.read_text(encoding="utf-8")
    lord_html = LORD_EQUIPMENT.read_text(encoding="utf-8")
    troops_html = TROOPS.read_text(encoding="utf-8")
    artifacts_html = ARTIFACTS.read_text(encoding="utf-8")
    pets_html = PETS.read_text(encoding="utf-8")
    holybeasts_html = HOLYBEASTS.read_text(encoding="utf-8")
    pals_html = PALS.read_text(encoding="utf-8")
    runes_html = RUNES.read_text(encoding="utf-8")
    talents_html = TALENTS.read_text(encoding="utf-8")
    tech_html = TECH.read_text(encoding="utf-8")
    decorations_html = DECORATIONS.read_text(encoding="utf-8")
    castle_html = CASTLE.read_text(encoding="utf-8")
    check_index(index, it, errors)
    check_index_published_catalogs(index, errors)
    check_exclusive_page(exclusive_html, errors)
    check_valhalla_page(valhalla_html, errors)
    check_skins_page(skins_html, errors)
    check_equipment_page(equipment_html, errors)
    check_lord_equipment_page(lord_html, errors)
    check_troops_page(troops_html, errors)
    check_artifacts_page(artifacts_html, errors)
    check_pets_page(pets_html, errors)
    check_holybeasts_page(holybeasts_html, errors)
    check_pals_page(pals_html, errors)
    check_runes_page(runes_html, errors)
    check_talents_page(talents_html, errors)
    check_tech_page(tech_html, errors)
    check_decorations_page(decorations_html, errors)
    check_castle_page(castle_html, errors)
    for html, label in (
        (exclusive_html, "專武總表"),
        (valhalla_html, "英靈總表"),
        (skins_html, "造型總表"),
        (equipment_html, "裝備總表"),
        (lord_html, "領主裝備總表"),
        (troops_html, "士兵總表"),
        (artifacts_html, "秘寶總表"),
        (pets_html, "寵物總表"),
        (holybeasts_html, "守護魔獸總表"),
        (pals_html, "帕魯總表"),
        (runes_html, "符文總表"),
        (talents_html, "天賦總表"),
        (tech_html, "科技總表"),
        (decorations_html, "裝飾物總表"),
        (castle_html, "城堡外觀總表"),
    ):
        if 'lang="zh-Hant"' not in html:
            fail(f"{label}: missing lang=zh-Hant", errors)

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
    if "後兩項的官方說明沒有百分比" not in rt or "由玩家在面板確認" not in rt:
        fail("薔薇公主 should note 爆發／控制 have no percentage and are panel-confirmed", errors)
    if "輔助、控制、增益" not in vt:
        fail("發明家 tags should be 輔助、控制、增益", errors)
    if "生命上限+5%" not in vt:
        fail("發明家 missing locked 生命上限+5%", errors)
    if "善於用技巧提供幫助，生命上限+5%" not in vt:
        fail("發明家 missing official 輔助 description", errors)
    if "能夠對敵人造成控制" not in vt or "能夠為隊友提供加強效果" not in vt:
        fail("發明家 missing official 控制／增益 descriptions", errors)
    if "後兩項的官方說明沒有百分比" not in vt or "由玩家在面板確認" not in vt:
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
    if "已開放" not in rt:
        fail("薔薇公主 狀態欄 should say 已開放", errors)
    if "本頁不另標上線狀態" in rt:
        fail("薔薇公主 狀態欄 must not say 本頁不另標上線狀態", errors)
    # Official links may point to published heroes only.
    allowed_hero_pages = {f"{hid}.html" for hid in PUBLISHED_IDS}
    for html, label in ((rose, "薔薇公主"), (judge, "審判官"), (nun, "修女"), (inventor, "發明家")):
        hrefs = set(re.findall(r'href="([^"]*\d+\.html)"', html))
        for href in hrefs:
            tail = href.rsplit("/", 1)[-1]
            if tail not in allowed_hero_pages:
                fail(f"{label} has link to unpublished hero page {href}", errors)

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
    if "已開放" not in vt:
        fail("發明家 狀態欄 should say 已開放", errors)
    if "本頁不另標上線狀態" in vt:
        fail("發明家 狀態欄 must not say 本頁不另標上線狀態", errors)
    # 騎士榮光（未開放） is gear-only wording.
    head_t = text_of(inventor.split("建議裝備")[0])
    if "發明家（未開放）" in vt or "他未開放" in vt or re.search(r"(?<!騎士榮光（)未開放", head_t):
        fail("發明家 must not be announced as 未開放", errors)
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

    check_attribution_cleanup(errors)
    check_hero_valhalla_attrs(errors)
    check_new_league_pages(errors)
    check_nature_tribe_pages(errors)
    check_mobile_catalog_markup(errors)

    if errors:
        print(f"{len(errors)} check(s) failed:")
        for msg in errors:
            print(" -", msg)
        return 1
    print("ok: TOC + exclusive, valhalla, skin and six new catalog tables + all published alliance, nature and tribe hero pages passed locked-rule checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
