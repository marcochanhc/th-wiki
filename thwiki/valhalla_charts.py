"""SVG line charts for 英靈 marginal effects. Preview only; not wired into build.py."""

from __future__ import annotations

from .exclusive_charts import (
    ACCENT,
    GOLD,
    Mark,
    Series,
    line_chart_svg,
    stacked_chart_svg,
)
from .htmlutil import e
from .valhalla_tables import TablesData


CAPTIONS = {
    "efficiency": (
        "數字來自表三。縱軸是本級Δ戰力÷本級專屬碎片，屬於依分欄推算，不是資料表原有欄位。"
        "金色虛線標出專屬技能升階點（1／25／50／75／100 級）。"
        "多數等級的效率隨消耗上升而下降；技能升階與部分 10 的倍數等級會出現高峰。"
        "縱軸從 0 起算。"
    ),
    "gain_cost": (
        "數字同樣來自表三。上圖是本級Δ戰力，下圖是本級專屬碎片消耗；兩項量尺差很大，"
        "所以分成兩張共用橫軸的圖，沒有畫在同一縱軸。金色虛線同樣標出技能升階點。"
        "上圖在技能升階處有明顯跳升。"
    ),
}


def _ratio(gain: int, cost: int) -> float:
    return gain / cost if cost else 0.0


def skill_marks() -> list[Mark]:
    return [
        Mark(1, "1階", GOLD),
        Mark(25, "25級／2階", GOLD),
        Mark(50, "50級／3階", GOLD),
        Mark(75, "75級／4階", GOLD),
        Mark(100, "100級／5階", GOLD),
    ]


def _x_ticks() -> list[tuple[float, str]]:
    ticks = [(1.0, "1")]
    for lv in range(10, 101, 10):
        ticks.append((float(lv), str(lv)))
    for lv in (25, 75):
        if all(t[0] != lv for t in ticks):
            ticks.append((float(lv), str(lv)))
    ticks.sort(key=lambda t: t[0])
    return ticks


def build_charts(data: TablesData) -> dict[str, str]:
    xs = [float(r.level) for r in data.levels]
    eff = [_ratio(r.delta_power, r.cost) for r in data.levels]
    dp = [float(r.delta_power) for r in data.levels]
    cost = [float(r.cost) for r in data.levels]
    marks = skill_marks()
    ticks = _x_ticks()
    c1 = line_chart_svg(
        [Series("每碎片Δ戰力（推算）", xs, eff, ACCENT)],
        x_min=1,
        x_max=100,
        x_ticks=ticks,
        y_label="每碎片Δ戰力（推算）",
        title="英靈升級：每碎片Δ戰力",
        marks=marks,
        aria="英靈升級邊際效率折線圖：橫軸英靈等級 1 至 100，縱軸每碎片Δ戰力（依分欄推算）。技能升階點在 1、25、50、75、100 級。",
    )
    c2 = stacked_chart_svg(
        [
            ("本級Δ戰力", Series("本級Δ戰力", xs, dp, ACCENT)),
            ("本級專屬碎片", Series("本級專屬碎片", xs, cost, GOLD)),
        ],
        x_min=1,
        x_max=100,
        x_ticks=ticks,
        x_label="英靈等級",
        title="英靈升級：本級Δ戰力與本級專屬碎片",
        marks=marks,
        aria="英靈升級增量與消耗：上圖本級Δ戰力，下圖本級專屬碎片，橫軸英靈等級。兩圖分軸，沒有畫在同一尺度上。",
    )
    return {"efficiency": c1, "gain_cost": c2}


def _figure(svg: str, caption: str, fig_id: str) -> str:
    return (
        f'<figure class="chart-block" id="{e(fig_id)}">'
        f"{svg}"
        f"<figcaption>{e(caption)}</figcaption>"
        f"</figure>"
    )


def charts_section_html(data: TablesData) -> str:
    svgs = build_charts(data)
    return (
        _figure(svgs["efficiency"], CAPTIONS["efficiency"], "chart-v-eff")
        + _figure(svgs["gain_cost"], CAPTIONS["gain_cost"], "chart-v-gain")
    )
