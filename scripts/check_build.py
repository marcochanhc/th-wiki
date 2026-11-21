#!/usr/bin/env python3
"""Sanity-check the built index and 審判官 / 修女 pages against locked rules."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
JUDGE = DOCS / "heroes" / "10031.html"
NUN = DOCS / "heroes" / "10027.html"
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
    allowed = {"heroes/10031.html", "heroes/10027.html"}
    got_hrefs = set()
    for href in hero_hrefs:
        tail = href.rsplit("/", 2)
        norm = "/".join(tail[-2:]) if len(tail) >= 2 else href
        got_hrefs.add(norm)
    if got_hrefs != allowed:
        fail(f"index: hero links should be only 10031/10027, got {sorted(got_hrefs)}", errors)
    # Unpublished / unreleased names must not be wrapped in an anchor.
    for hid in ("10029", "10032", "10007", "15032", "15033", "15039", "10043"):
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
        if item.startswith("老闆娘") and "尚未公開" not in item:
            fail("index: 老闆娘 should be marked 尚未公開", errors)

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


def main() -> int:
    errors = []
    for p in (INDEX, JUDGE, NUN):
        if not p.exists():
            fail(f"missing {p}", errors)
    if errors:
        print("\n".join(errors))
        return 1

    index = INDEX.read_text(encoding="utf-8")
    judge = JUDGE.read_text(encoding="utf-8")
    nun = NUN.read_text(encoding="utf-8")
    jt, nt, it = text_of(judge), text_of(nun), text_of(index)

    for html, label in ((index, "index"), (judge, "審判官"), (nun, "修女")):
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
    if "稱號屬性" in jt or "稱號屬性" in nt:
        fail("used 稱號屬性 instead of 英雄屬性", errors)
    if "英雄屬性" not in jt or "英雄屬性" not in nt:
        fail("missing 英雄屬性 label", errors)
    if "坦克、持續、增益" not in jt:
        fail("審判官 tags should be 坦克、持續、增益", errors)
    if "治療、增益、個體" not in nt:
        fail("修女 tags should be 治療、增益、個體", errors)
    if "受到傷害-5%" not in jt:
        fail("審判官 missing locked 受到傷害-5%", errors)
    if "治療效果+5%" not in nt:
        fail("修女 missing locked 治療效果+5%", errors)

    # talents
    for s in ("90.00%", "270.00%", "30.00%", "3.00%", "9.00%", "1.00%"):
        if s not in jt:
            fail(f"審判官 talent missing {s}", errors)
    if "進攻戰略" not in jt or "持久策略" not in jt or "格擋研究" not in jt:
        fail("審判官 talent names missing", errors)
    # 修女 must stay raw, not inherit ÷100
    if "90.00%" in nt or "270.00%" in nt:
        fail("修女 talents must stay 原值, not inherit 審判官 percentages", errors)
    if "9,000" not in nt or "27,000" not in nt or "3,000" not in nt:
        fail("修女 talents missing raw values 9,000 / 27,000 / 3,000", errors)
    if "治療增效" not in nt:
        fail("修女 missing 治療增效", errors)

    # appearance split tables
    for label, html in (("審判官", judge), ("修女", nun)):
        if "收集屬性" not in html or "裝備屬性" not in html or "解鎖來源" not in html or "時裝幣" not in html:
            fail(f"{label}: 外觀 tables not split as required", errors)
        if re.search(r">—<|>–<|>－<", html):
            fail(f"{label}: empty cell used dash instead of 無", errors)

    if "審判官·傑克船長" not in jt or "審判·狂熱之愛" not in jt or "審判·不敗戰神" not in jt:
        fail("審判官 skins missing", errors)
    if "可升至 2 星，見下方星級表" not in jt:
        fail("審判官 不敗戰神 should point to star table", errors)
    if "修女·純潔之戀" not in nt or "修女·智慧女神" not in nt:
        fail("修女 skins missing", errors)
    if "可升至 4 星，見下方星級表" not in nt:
        fail("修女 智慧女神 should point to star table", errors)
    if "雙方成對屬性" not in jt or "雙方成對屬性" not in nt:
        fail("pairing prose should use 雙方成對屬性", errors)
    if "僅在雲海紀行賽季中生效" not in jt or "僅在雲海紀行賽季中生效" not in nt:
        fail("missing official skin_season_6 quote", errors)
    if "蔷薇" in jt or "蔷薇" in nt or "蔷薇" in it or "蕊薇" in it:
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

    # no invented 薔薇公主 page link
    if re.search(r'href="[^"]*薔薇', jt) or "10043.html" in jt:
        fail("should not invent a link to unbuilt 薔薇公主 entry", errors)

    if "建議裝備" not in jt or "建議裝備" not in nt:
        fail("missing 建議裝備 section", errors)
    if "（推算，不是官方最佳裝備）" in jt or "（推算，不是官方最佳裝備）" in nt:
        fail("disclaimer should not sit inline with gear names", errors)
    if "社群備註" not in jt or "社群備註" not in nt:
        fail("missing 社群備註 heading", errors)

    if "star-white" not in judge or "star-white" not in nun:
        fail("15-star display should include white star icons", errors)

    # Homepage is a compact roster, not portrait cards.
    # Hero pages still reserve a portrait slot; no character art in the build.
    if "lead-placeholder" in index or "hero-card" in index:
        fail("index: homepage should list names, not hero cards or portrait placeholders", errors)
    for html, label in ((index, "index"), (judge, "審判官"), (nun, "修女")):
        if "10031-lead.jpg" in html or 'src="lead.jpg"' in html or "th-art/page/lead" in html:
            fail(f"{label}: should not embed a character portrait", errors)
        if "<img" in html.lower():
            fail(f"{label}: unexpected <img> (placeholder must not be a broken image tag)", errors)
    for html, label in ((judge, "審判官"), (nun, "修女")):
        if "lead-placeholder" not in html:
            fail(f"{label}: missing reserved lead-image placeholder", errors)
    lead_out = DOCS / "assets" / "img" / "10031-lead.jpg"
    if lead_out.exists():
        fail("docs still contains published lead art 10031-lead.jpg", errors)

    if "公正領域" not in jt or "雄獅血脈" not in jt:
        fail("審判官 exclusive / spirit skills missing", errors)
    if "神聖恩賜" not in nt:
        fail("修女 exclusive skill missing", errors)

    if "海皇霸主" not in jt or "永恆之戀" not in jt or "不朽王座" not in jt:
        fail("審判官 collection suits missing", errors)
    if "永恆之戀" not in nt or "不朽王座" not in nt:
        fail("修女 collection suits missing", errors)

    # display server 50 vs id 10050 should not be claimed
    if re.search(r"顯示.?50.{0,12}10050|10050.{0,12}顯示.?50", jt + nt):
        fail("must not claim display 50 equals internal id 10050", errors)

    if errors:
        print(f"{len(errors)} check(s) failed:")
        for msg in errors:
            print(" -", msg)
        return 1
    print("ok: TOC + 審判官 + 修女 passed locked-rule checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
