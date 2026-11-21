#!/usr/bin/env python3
"""Sanity-check the built 審判官 / 修女 pages against locked presentation rules."""

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

    if "heroes/10031.html" not in index or "heroes/10027.html" not in index:
        fail("index: missing links to both hero pages", errors)

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
    if "蔷薇" in jt or "蔷薇" in nt:
        fail("typo 蔷薇 (should be 薔薇)", errors)
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

    # Portraits are reserved placeholders only; no character art in the build.
    for html, label in ((index, "index"), (judge, "審判官"), (nun, "修女")):
        if "lead-placeholder" not in html:
            fail(f"{label}: missing reserved lead-image placeholder", errors)
        if "10031-lead.jpg" in html or 'src="lead.jpg"' in html or "th-art/page/lead" in html:
            fail(f"{label}: should not embed a character portrait", errors)
        if "<img" in html.lower():
            fail(f"{label}: unexpected <img> (placeholder must not be a broken image tag)", errors)
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
