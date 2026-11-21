#!/usr/bin/env python3
"""Build the Top Heroes static wiki into docs/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from thwiki.assemble import assemble
from thwiki.overrides import PUBLISH_IDS
from thwiki.paths import DOCS_DIR, PROJECT_ROOT, STATIC_DIR
from thwiki.render import render_hero, render_home


def copy_assets():
    assets = DOCS_DIR / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    css_dst = assets / "css"
    css_dst.mkdir(parents=True)
    shutil.copy2(STATIC_DIR / "css" / "site.css", css_dst / "site.css")
    # Portraits are reserved placeholders for now; do not copy lead art into docs/.


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    copy_assets()
    heroes_dir = DOCS_DIR / "heroes"
    heroes_dir.mkdir(exist_ok=True)

    pages = []
    for hid in PUBLISH_IDS:
        page = assemble(hid)
        pages.append(page)
        out = heroes_dir / f"{hid}.html"
        out.write_text(render_hero(page), encoding="utf-8")
        print(f"wrote {out.relative_to(PROJECT_ROOT)}")

    index = DOCS_DIR / "index.html"
    index.write_text(render_home(pages), encoding="utf-8")
    print(f"wrote {index.relative_to(PROJECT_ROOT)}")
    print(f"output: {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
