from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .paths import DATA_DIR


def load_table(name: str):
    path = DATA_DIR / name
    if not path.suffix:
        path = DATA_DIR / f"{name}.json"
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def catalog():
    heroes = load_table("hero_detail")
    attributes = load_table("attribute")
    return {
        "hero_detail": heroes,
        "hero_by_id": {h["id"]: h for h in heroes},
        "hero_component": load_table("hero_component"),
        "hero_star": load_table("hero_star"),
        "hero_awaken": load_table("hero_awaken"),
        "hero_exclusive": load_table("hero_exclusive"),
        "exclusive_break": load_table("exclusive_break"),
        "hero_valhalla": load_table("hero_valhalla"),
        "hero_valhalla_lvup": load_table("hero_valhalla_lvup"),
        "hero_talent": load_table("hero_talent"),
        "hero_talent_group": load_table("hero_talent_group"),
        "hero_talent_new": load_table("hero_talent_new"),
        "hero_skin": load_table("hero_skin"),
        "hero_skin_suit": load_table("hero_skin_suit"),
        "hero_link": load_table("hero_link"),
        "hero_recommend": load_table("hero_recommend"),
        "hero_honor_bonus": load_table("hero_honor_bonus"),
        "attribute": attributes,
        "attribute_by_id": {a["id"]: a for a in attributes},
    }


def hero_row(hero_id: int) -> dict:
    row = catalog()["hero_by_id"].get(hero_id)
    if not row:
        raise KeyError(f"hero_id {hero_id} not in hero_detail")
    return row


def components_for(hero_id: int) -> list[dict]:
    lo, hi = hero_id * 100, hero_id * 100 + 100
    rows = [c for c in catalog()["hero_component"] if lo <= c["id"] < hi]
    return sorted(rows, key=lambda c: c["id"])


def component(comp_id: int):
    for row in catalog()["hero_component"]:
        if row["id"] == comp_id:
            return row
    return None
