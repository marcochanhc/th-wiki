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
from thwiki.exclusive_tables import render_exclusive_page
from thwiki.valhalla_tables import render_valhalla_page
from thwiki.skin_tables import render_skin_page
from thwiki.equipment_tables import render_equipment_page
from thwiki.lord_equipment_tables import render_lord_equipment_page
from thwiki.troop_tables import render_troop_page
from thwiki.artifact_tables import render_artifact_page
from thwiki.pet_tables import render_pet_page
from thwiki.rune_tables import render_rune_page
from thwiki.talent_tables import render_talent_page
from thwiki.tech_tables import render_tech_page
from thwiki.decoration_tables import render_decoration_page
from thwiki.castle_tables import render_castle_page
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

    exclusive = DOCS_DIR / "exclusive.html"
    exclusive.write_text(render_exclusive_page(), encoding="utf-8")
    print(f"wrote {exclusive.relative_to(PROJECT_ROOT)}")

    valhalla = DOCS_DIR / "valhalla.html"
    valhalla.write_text(render_valhalla_page(), encoding="utf-8")
    print(f"wrote {valhalla.relative_to(PROJECT_ROOT)}")

    skins = DOCS_DIR / "skins.html"
    skins.write_text(render_skin_page(), encoding="utf-8")
    print(f"wrote {skins.relative_to(PROJECT_ROOT)}")

    catalogs = (
        ("equipment.html", render_equipment_page),
        ("lord-equipment.html", render_lord_equipment_page),
        ("troops.html", render_troop_page),
        ("artifacts.html", render_artifact_page),
        ("pets.html", render_pet_page),
        ("runes.html", render_rune_page),
        ("talents.html", render_talent_page),
        ("tech.html", render_tech_page),
        ("decorations.html", render_decoration_page),
        ("castle.html", render_castle_page),
    )
    for name, renderer in catalogs:
        out = DOCS_DIR / name
        out.write_text(renderer(), encoding="utf-8")
        print(f"wrote {out.relative_to(PROJECT_ROOT)}")

    index = DOCS_DIR / "index.html"
    index.write_text(render_home(pages), encoding="utf-8")
    print(f"wrote {index.relative_to(PROJECT_ROOT)}")
    print(f"output: {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
