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
from thwiki.holybeast_tables import render_holybeast_page, write_holybeast_upgrade_cost_data
from thwiki.pal_tables import render_pal_page
from thwiki.citybuilding_tables import render_citybuilding_page, write_city_upgrade_cost_data
from thwiki.lord_occupation_tables import render_lord_occupation_page
from thwiki.rune_tables import render_rune_page
from thwiki.talent_tables import render_talent_page
from thwiki.tech_tables import render_tech_page
from thwiki.decoration_tables import render_decoration_page
from thwiki.castle_tables import render_castle_page
from thwiki.kvk_tables import render_kingdom_clash_page
from thwiki.elf_tables import render_elf_cottage_page
from thwiki.fish_tank_tables import render_fish_tank_page
from thwiki.butterfly_tables import render_butterfly_catch_page
from thwiki.ranch_tables import render_ranch_tale_page
from thwiki.villager_tables import render_villagers_page
from thwiki.faction_level_tables import render_faction_levels_page
from thwiki.caravan_tables import render_caravan_trade_page
from thwiki.totem_tables import render_ancestral_totem_page
from thwiki.guild_mentor_tables import render_guild_mentors_page
from thwiki.pve_tables import render_pve_page
from thwiki.seven_reward_move_tables import render_seven_reward_move_page
from thwiki.arena_ladder_tables import render_arena_ladder_page
from thwiki.render import render_hero, render_home
from thwiki.search_index import write_search_index


def copy_assets():
    assets = DOCS_DIR / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    css_dst = assets / "css"
    css_dst.mkdir(parents=True)
    shutil.copy2(STATIC_DIR / "css" / "site.css", css_dst / "site.css")
    js_src = STATIC_DIR / "js" / "page-filter.js"
    js_dst = assets / "js"
    js_dst.mkdir(parents=True)
    shutil.copy2(js_src, js_dst / "page-filter.js")
    shutil.copy2(STATIC_DIR / "js" / "upgrade-cost.js", js_dst / "upgrade-cost.js")
    shutil.copy2(STATIC_DIR / "js" / "search.js", js_dst / "search.js")
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
        ("holybeasts.html", render_holybeast_page),
        ("pals.html", render_pal_page),
        ("city-buildings.html", render_citybuilding_page),
        ("lord-occupations.html", render_lord_occupation_page),
        ("runes.html", render_rune_page),
        ("talents.html", render_talent_page),
        ("tech.html", render_tech_page),
        ("decorations.html", render_decoration_page),
        ("castle.html", render_castle_page),
        ("kingdom-clash.html", render_kingdom_clash_page),
        ("elf-cottage.html", render_elf_cottage_page),
        ("fish-tank.html", render_fish_tank_page),
        ("butterfly-catch.html", render_butterfly_catch_page),
        ("ranch-tale.html", render_ranch_tale_page),
        ("villagers.html", render_villagers_page),
        ("faction-levels.html", render_faction_levels_page),
        ("caravan-trade.html", render_caravan_trade_page),
        ("ancestral-totem.html", render_ancestral_totem_page),
        ("guild-mentors.html", render_guild_mentors_page),
        ("pve.html", render_pve_page),
        ("seven-reward-move.html", render_seven_reward_move_page),
        ("arena-ladder.html", render_arena_ladder_page),
    )
    for name, renderer in catalogs:
        out = DOCS_DIR / name
        out.write_text(renderer(), encoding="utf-8")
        print(f"wrote {out.relative_to(PROJECT_ROOT)}")

    js_dir = DOCS_DIR / "assets" / "js"
    write_city_upgrade_cost_data(js_dir / "city-upgrade-costs-data.js")
    print(f"wrote { (js_dir / 'city-upgrade-costs-data.js').relative_to(PROJECT_ROOT) }")
    write_holybeast_upgrade_cost_data(js_dir / "holybeast-upgrade-costs-data.js")
    print(f"wrote { (js_dir / 'holybeast-upgrade-costs-data.js').relative_to(PROJECT_ROOT) }")

    index = DOCS_DIR / "index.html"
    index.write_text(render_home(pages), encoding="utf-8")
    print(f"wrote {index.relative_to(PROJECT_ROOT)}")

    published = [heroes_dir / f"{hid}.html" for hid in PUBLISH_IDS]
    published.append(exclusive)
    published.append(valhalla)
    published.append(skins)
    published.extend(DOCS_DIR / name for name, _renderer in catalogs)
    published.append(index)
    index_js = write_search_index(published)
    print(f"wrote {index_js.relative_to(PROJECT_ROOT)}")

    print(f"output: {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
