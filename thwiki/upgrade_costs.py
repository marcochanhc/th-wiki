"""Shared helpers for the static upgrade-cost calculators."""

from __future__ import annotations

import json
from pathlib import Path

from .htmlutil import e


def attach_upgrade_cost_scripts(html: str, *filenames: str) -> str:
    tags = "\n".join(f'  <script src="assets/js/{e(name)}" defer></script>' for name in filenames)
    needle = '  <script src="assets/js/page-filter.js" defer></script>'
    if needle not in html:
        raise RuntimeError("page-filter script hook missing; cannot attach upgrade-cost scripts")
    return html.replace(needle, needle + "\n" + tags, 1)


def write_data_js(path: Path, global_name: str, payload: dict) -> None:
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"var {global_name} = {blob};\n"
        f'if (typeof module === "object" && module.exports) module.exports = {global_name};\n',
        encoding="utf-8",
    )


def curve_max(curve: dict) -> int:
    return int(curve["min"]) + len(curve["t"]) - 1


def sum_city_range(curve: dict, from_lv: int, to_lv: int) -> dict:
    """Sum official rows from from_lv inclusive to to_lv exclusive."""
    if not curve:
        return {"ok": False, "reason": "missing curve"}
    if from_lv >= to_lv:
        return {"ok": False, "reason": "from >= to"}
    min_lv = int(curve["min"])
    max_lv = curve_max(curve)
    if from_lv < min_lv or to_lv > max_lv:
        return {"ok": False, "reason": "out of range", "min": min_lv, "max": max_lv}
    acc: dict[tuple[int, int], int] = {}
    time = 0
    rows = 0
    for lv in range(from_lv, to_lv):
        i = lv - min_lv
        time += int(curve["t"][i])
        rows += 1
        for typ, mid, qty in curve["c"][i]:
            key = (int(typ), int(mid))
            acc[key] = acc.get(key, 0) + int(qty)
    leftover = None
    if to_lv == max_lv:
        segs = curve["c"][to_lv - min_lv]
        if segs:
            leftover = {
                "time": int(curve["t"][to_lv - min_lv]),
                "costs": [(int(a), int(b), int(c)) for a, b, c in segs],
            }
    return {"ok": True, "time": time, "costs": acc, "rows": rows, "leftover": leftover, "min": min_lv, "max": max_lv}


def sum_beast_levels(levels: dict, from_lv: int, to_lv: int) -> dict:
    """Sum official level rows from from_lv+1 through to_lv inclusive."""
    if from_lv >= to_lv:
        return {"ok": False, "reason": "from >= to"}
    min_lv = int(levels["min"])
    max_lv = int(levels["max"])
    if from_lv < 0 or to_lv > max_lv or to_lv < min_lv:
        return {"ok": False, "reason": "out of range"}
    start = max(from_lv + 1, min_lv)
    crystal = 0
    core = 0
    core_levels = []
    for lv in range(start, to_lv + 1):
        crystal += int(levels["crystal"][lv - min_lv])
        if str(lv) in levels["core"]:
            core += int(levels["core"][str(lv)])
            core_levels.append(lv)
    return {"ok": True, "crystal": crystal, "core": core, "core_levels": core_levels}


def star_index(stars: list[dict], star: int, sub: int) -> int:
    for i, row in enumerate(stars):
        if int(row["star"]) == star and int(row["sub"]) == sub:
            return i
    return -1


def sum_beast_stars(stars: list[dict], from_star: int, from_sub: int, to_star: int, to_sub: int, include_start: bool) -> dict:
    to_i = star_index(stars, to_star, to_sub)
    from_i = -1 if include_start else star_index(stars, from_star, from_sub)
    if (not include_start and from_i < 0) or to_i < 0:
        return {"ok": False, "reason": "missing star row"}
    start_i = from_i + 1
    if start_i > to_i:
        return {"ok": False, "reason": "from after to"}
    contract = other = stone = 0
    other_differs = False
    for row in stars[start_i : to_i + 1]:
        if row.get("stone"):
            stone += int(row["stone"])
            other += int(row.get("other") or row["stone"])
            if int(row.get("other") or 0) not in (0, int(row["stone"])):
                if int(row.get("other") or row["stone"]) != int(row["stone"]):
                    other_differs = True
        else:
            contract += int(row["contract"])
            other += int(row["other"])
            if int(row["other"]) != int(row["contract"]):
                other_differs = True
    return {
        "ok": True,
        "contract": contract,
        "other": other,
        "stone": stone,
        "other_differs": other_differs,
        "used": to_i - start_i + 1,
    }
