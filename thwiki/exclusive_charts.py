"""SVG line charts for exclusive-weapon marginal effects.

Used by the local preview script. Not wired into build.py, so a normal
wiki build will not change docs/exclusive.html.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .exclusive_tables import TablesData, attr_label, ratio
from .htmlutil import e


# Wiki light-theme colors (charts stay on a light card even in dark mode).
INK = "#1c1a16"
MUTED = "#5c564c"
LINE = "#d9d0bf"
ACCENT = "#8a6a14"
GOLD = "#b07a10"
RED = "#9a1e1e"
CARD = "#fffdf7"
PLOT = "#fbf8f0"
FONT = '"Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK TC", sans-serif'


def _nice_ticks(lo: float, hi: float, max_ticks: int = 6) -> list[float]:
    if hi < lo:
        lo, hi = hi, lo
    if hi == lo:
        hi = lo + 1
    # Always include 0 when the series is non-negative, so declines stay honest.
    if lo >= 0:
        lo = 0
    span = hi - lo
    raw = span / max(1, max_ticks - 1)
    exp = math.floor(math.log10(raw)) if raw > 0 else 0
    frac = raw / (10 ** exp)
    if frac <= 1:
        step = 1
    elif frac <= 2:
        step = 2
    elif frac <= 2.5:
        step = 2.5
    elif frac <= 5:
        step = 5
    else:
        step = 10
    step *= 10 ** exp
    start = math.floor(lo / step) * step
    ticks = []
    x = start
    # Guard against float drift.
    while x <= hi + step * 0.5 + 1e-9 and len(ticks) < 16:
        if x >= lo - step * 0.01:
            ticks.append(round(x, 10))
        x += step
    if ticks[-1] < hi:
        ticks.append(round(ticks[-1] + step, 10))
    return ticks


def _fmt_tick(v: float) -> str:
    if abs(v - round(v)) < 1e-9:
        n = int(round(v))
        return f"{n:,}"
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{v:.1f}"


def _ratio(gain: int, cost: int) -> float:
    return gain / cost if cost else 0.0


@dataclass
class Series:
    name: str
    xs: list[float]
    ys: list[float]
    color: str = ACCENT


@dataclass
class Mark:
    x: float
    label: str
    color: str = GOLD


def line_chart_svg(
    series: list[Series],
    *,
    x_min: float,
    x_max: float,
    x_ticks: list[tuple[float, str]],
    y_label: str,
    title: str,
    marks: list[Mark] | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
    width: int = 760,
    height: int = 400,
    aria: str = "",
) -> str:
    marks = marks or []
    ys = [y for s in series for y in s.ys]
    if y_min is None:
        y_min = 0 if min(ys) >= 0 else min(ys)
    if y_max is None:
        y_max = max(ys)
    pad = (y_max - y_min) * 0.08 if y_max > y_min else 1
    y_max = y_max + pad
    yticks = _nice_ticks(y_min, y_max)
    if yticks:
        y_min = min(y_min, yticks[0])
        y_max = max(y_max, yticks[-1])

    left, right, top, bottom = 62, 18, 52, 56
    pw, ph = width - left - right, height - top - bottom

    def xpix(x: float) -> float:
        return left + (x - x_min) / (x_max - x_min) * pw

    def ypix(y: float) -> float:
        return top + (y_max - y) / (y_max - y_min) * ph

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{e(aria or title)}" '
        f'style="font-family:{FONT};background:{CARD};">')
    parts.append(f'<rect width="{width}" height="{height}" fill="{CARD}"/>')
    parts.append(
        f'<text x="{left}" y="18" fill="{INK}" font-size="15" font-weight="700">{e(title)}</text>'
    )
    # plot background
    parts.append(
        f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="{PLOT}" stroke="{LINE}"/>'
    )
    for tv in yticks:
        y = ypix(tv)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" '
            f'stroke="{LINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{_fmt_tick(tv)}</text>'
        )
    # y-axis title
    cx, cy = 16, top + ph / 2
    parts.append(
        f'<text x="{cx}" y="{cy:.1f}" fill="{MUTED}" font-size="12" text-anchor="middle" '
        f'transform="rotate(-90 {cx} {cy:.1f})">{e(y_label)}</text>'
    )
    # marks behind the line
    for m in marks:
        x = xpix(m.x)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top+ph}" '
            f'stroke="{m.color}" stroke-width="1" stroke-dasharray="4 3" opacity="0.85"/>'
        )
        anchor = "start" if m.x <= x_min + 0.1 else ("end" if m.x >= x_max - 0.1 else "middle")
        parts.append(
            f'<text x="{x:.1f}" y="{top-6}" text-anchor="{anchor}" fill="{m.color}" font-size="10">{e(m.label)}</text>'
        )
    for s in series:
        pts = " ".join(f"{xpix(x):.1f},{ypix(y):.1f}" for x, y in zip(s.xs, s.ys))
        parts.append(
            f'<polyline fill="none" stroke="{s.color}" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{pts}"/>'
        )
        mark_xs = {m.x for m in marks}
        for x, y in zip(s.xs, s.ys):
            r = 4.2 if x in mark_xs else 3.1
            parts.append(
                f'<circle cx="{xpix(x):.1f}" cy="{ypix(y):.1f}" r="{r}" '
                f'fill="{CARD}" stroke="{s.color}" stroke-width="1.8"/>'
            )
    for xv, lab in x_ticks:
        x = xpix(xv)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top+ph}" x2="{x:.1f}" y2="{top+ph+5}" stroke="{MUTED}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top+ph+18}" text-anchor="middle" fill="{MUTED}" font-size="11">{e(lab)}</text>'
        )
    if len(series) > 1:
        lx = left
        ly = height - 14
        for s in series:
            parts.append(f'<circle cx="{lx+6}" cy="{ly-3}" r="4" fill="{s.color}"/>')
            parts.append(
                f'<text x="{lx+16}" y="{ly}" fill="{INK}" font-size="12">{e(s.name)}</text>'
            )
            lx += 12 + 8 * (len(s.name) + 4)
    parts.append("</svg>")
    return "\n".join(parts)


def stacked_chart_svg(
    panels: list[tuple[str, Series]],
    *,
    x_min: float,
    x_max: float,
    x_ticks: list[tuple[float, str]],
    x_label: str,
    title: str,
    marks: list[Mark] | None = None,
    width: int = 760,
    panel_height: int = 170,
    aria: str = "",
) -> str:
    """Two (or more) line panels sharing one x-axis. Avoids dual-axis clutter."""
    marks = marks or []
    n = len(panels)
    left, right, top, gap, bottom = 62, 18, 52, 18, 52
    height = top + n * panel_height + (n - 1) * gap + bottom
    pw = width - left - right

    def xpix(x: float) -> float:
        return left + (x - x_min) / (x_max - x_min) * pw

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{e(aria or title)}" '
        f'style="font-family:{FONT};background:{CARD};">',
        f'<rect width="{width}" height="{height}" fill="{CARD}"/>',
        f'<text x="{left}" y="18" fill="{INK}" font-size="15" font-weight="700">{e(title)}</text>',
    ]
    for i, (y_label, series) in enumerate(panels):
        ys = list(series.ys)
        y_min = 0 if min(ys) >= 0 else min(ys)
        y_max = max(ys)
        pad = (y_max - y_min) * 0.10 if y_max > y_min else 1
        y_max = y_max + pad
        yticks = _nice_ticks(y_min, y_max)
        if yticks:
            y_min = min(y_min, yticks[0])
            y_max = max(y_max, yticks[-1])
        ptop = top + i * (panel_height + gap)
        ph = panel_height

        def ypix(y: float, _top=ptop, _ymax=y_max, _ymin=y_min, _ph=ph) -> float:
            return _top + (_ymax - y) / (_ymax - _ymin) * _ph

        parts.append(
            f'<rect x="{left}" y="{ptop}" width="{pw}" height="{ph}" fill="{PLOT}" stroke="{LINE}"/>'
        )
        for tv in yticks:
            y = ypix(tv)
            parts.append(
                f'<line x1="{left}" y1="{y:.1f}" x2="{left+pw}" y2="{y:.1f}" stroke="{LINE}" stroke-width="1"/>'
            )
            parts.append(
                f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{_fmt_tick(tv)}</text>'
            )
        cx, cy = 16, ptop + ph / 2
        parts.append(
            f'<text x="{cx}" y="{cy:.1f}" fill="{MUTED}" font-size="12" text-anchor="middle" '
            f'transform="rotate(-90 {cx} {cy:.1f})">{e(y_label)}</text>'
        )
        for m in marks:
            x = xpix(m.x)
            parts.append(
                f'<line x1="{x:.1f}" y1="{ptop}" x2="{x:.1f}" y2="{ptop+ph}" '
                f'stroke="{m.color}" stroke-width="1" stroke-dasharray="4 3" opacity="0.85"/>'
            )
            if i == 0:
                anchor = "start" if m.x <= x_min + 0.1 else ("end" if m.x >= x_max - 0.1 else "middle")
                parts.append(
                    f'<text x="{x:.1f}" y="{ptop-6}" text-anchor="{anchor}" fill="{m.color}" font-size="10">{e(m.label)}</text>'
                )
        pts = " ".join(f"{xpix(x):.1f},{ypix(y):.1f}" for x, y in zip(series.xs, series.ys))
        parts.append(
            f'<polyline fill="none" stroke="{series.color}" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round" points="{pts}"/>'
        )
        mark_xs = {m.x for m in marks}
        for x, y in zip(series.xs, series.ys):
            r = 4.2 if x in mark_xs else 3.1
            parts.append(
                f'<circle cx="{xpix(x):.1f}" cy="{ypix(y):.1f}" r="{r}" '
                f'fill="{CARD}" stroke="{series.color}" stroke-width="1.8"/>'
            )
        if i == n - 1:
            for xv, lab in x_ticks:
                x = xpix(xv)
                parts.append(
                    f'<line x1="{x:.1f}" y1="{ptop+ph}" x2="{x:.1f}" y2="{ptop+ph+5}" stroke="{MUTED}"/>'
                )
                parts.append(
                    f'<text x="{x:.1f}" y="{ptop+ph+18}" text-anchor="middle" fill="{MUTED}" font-size="11">{e(lab)}</text>'
                )
            parts.append(
                f'<text x="{left+pw/2}" y="{height-8}" text-anchor="middle" fill="{MUTED}" font-size="12">{e(x_label)}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def _figure(svg: str, caption: str, fig_id: str) -> str:
    return (
        f'<figure class="chart-block" id="{e(fig_id)}">'
        f"{svg}"
        f"<figcaption>{caption}</figcaption>"
        f"</figure>"
    )


def upgrade_marks() -> list[Mark]:
    return [
        Mark(1, "1階", GOLD),
        Mark(5, "5級／2階", GOLD),
        Mark(10, "10級／3階", GOLD),
        Mark(15, "15級／4階", GOLD),
        Mark(20, "20級／5階", GOLD),
    ]


def break_marks() -> list[Mark]:
    return [
        Mark(5, "1星 大屬性", ACCENT),
        Mark(10, "2星光環", RED),
        Mark(15, "3星 大屬性", ACCENT),
        Mark(20, "4星 大屬性", ACCENT),
        Mark(25, "5星光環", RED),
    ]


def build_charts(data: TablesData) -> dict[str, str]:
    """Return SVG markup for the four preview charts."""
    u_xs = [float(r.level) for r in data.upgrade]
    u_eff = [_ratio(r.delta_power, r.cost) for r in data.upgrade]
    u_dp = [float(r.delta_power) for r in data.upgrade]
    u_cost = [float(r.cost) for r in data.upgrade]
    u_ticks = [(float(i), str(i)) for i in range(1, 21)]
    # Tick density: show all levels; font is small enough at 760px.
    b_xs = [float(r.step) for r in data.breakthrough]
    b_eff = [_ratio(r.delta_power, r.cost) for r in data.breakthrough]
    b_dp = [float(r.delta_power) for r in data.breakthrough]
    b_cost = [float(r.cost) for r in data.breakthrough]
    b_ticks = []
    for r in data.breakthrough:
        if r.star_small == 0:
            b_ticks.append((float(r.step), f"{r.step}（{r.star_big}星）"))
        elif r.step in (1, 25) or r.step % 5 == 0:
            b_ticks.append((float(r.step), str(r.step)))

    # First point of break is 0-1, not a big-star gate; include 1.
    if not any(t[0] == 1 for t in b_ticks):
        b_ticks.insert(0, (1.0, "1"))
    b_ticks = sorted(set(b_ticks), key=lambda t: t[0])

    c1 = line_chart_svg(
        [Series("每碎片Δ戰力（推算）", u_xs, u_eff, ACCENT)],
        x_min=1,
        x_max=20,
        x_ticks=u_ticks,
        y_label="每碎片Δ戰力（推算）",
        title="升級：每碎片Δ戰力",
        marks=upgrade_marks(),
        aria="升級邊際效率折線圖：橫軸專武等級 1 至 20，縱軸每碎片Δ戰力（依分欄推算）。技能升階點在 1、5、10、15、20 級。",
    )
    c2 = stacked_chart_svg(
        [
            ("本級Δ戰力", Series("本級Δ戰力", u_xs, u_dp, ACCENT)),
            ("本級專武碎片", Series("本級專武碎片", u_xs, u_cost, GOLD)),
        ],
        x_min=1,
        x_max=20,
        x_ticks=u_ticks,
        x_label="專武等級",
        title="升級：本級Δ戰力與本級專武碎片",
        marks=upgrade_marks(),
        aria="升級增量與消耗：上圖本級Δ戰力，下圖本級專武碎片，橫軸專武等級。兩圖分軸，沒有畫在同一尺度上。",
    )
    c3 = line_chart_svg(
        [Series("每鐵芯Δ戰力（推算）", b_xs, b_eff, ACCENT)],
        x_min=1,
        x_max=25,
        x_ticks=b_ticks,
        y_label="每鐵芯Δ戰力（推算）",
        title="突破：每鐵芯Δ戰力",
        marks=break_marks(),
        aria="突破邊際效率折線圖：橫軸步驟 1 至 25，縱軸每鐵芯Δ戰力（依分欄推算）。標出 2 星、5 星光環與 1、3、4 星額外大屬性。",
    )
    c4 = stacked_chart_svg(
        [
            ("本步Δ戰力", Series("本步Δ戰力", b_xs, b_dp, ACCENT)),
            ("本步隕星鐵芯", Series("本步隕星鐵芯", b_xs, b_cost, GOLD)),
        ],
        x_min=1,
        x_max=25,
        x_ticks=b_ticks,
        x_label="突破步驟",
        title="突破：本步Δ戰力與本步隕星鐵芯",
        marks=break_marks(),
        aria="突破增量與消耗：上圖本步Δ戰力，下圖本步隕星鐵芯，橫軸步驟。兩圖分軸，沒有畫在同一尺度上。",
    )
    return {
        "upgrade_efficiency": c1,
        "upgrade_gain_cost": c2,
        "break_efficiency": c3,
        "break_gain_cost": c4,
    }


CAPTIONS = {
    "upgrade_efficiency": (
        "數字來自表四「升級邊際」。縱軸是本級Δ戰力÷本級專武碎片，屬於依分欄推算，不是資料表原有欄位。"
        "金色虛線標出專屬技能升階點（對應專武 1／5／10／15／20 級）。縱軸從 0 起算。"
    ),
    "upgrade_gain_cost": (
        "數字同樣來自表四「升級邊際」。上圖是本級Δ戰力，下圖是本級專武碎片消耗；兩項量尺差很大，所以分成兩張共用橫軸的圖，沒有畫在同一縱軸。"
        "金色虛線同樣標出技能升階點。"
    ),
    "break_efficiency": (
        "數字來自表四「突破邊際」。縱軸是本步Δ戰力÷本步隕星鐵芯，屬於依分欄推算，不是資料表原有欄位。"
        "紅色虛線是 2 星、5 星陣營共用光環解鎖點；棕色虛線是額外大屬性出現的 1 星（英雄生命 4000）、3 星（英雄攻擊 5000）、4 星（英雄生命 6000）。縱軸從 0 起算。"
    ),
    "break_gain_cost": (
        "數字同樣來自表四「突破邊際」。上圖是本步Δ戰力，下圖是本步隕星鐵芯；兩項量尺差很大，所以分成兩張共用橫軸的圖。"
        "解鎖與額外大屬性的標記與上一張相同。額外大屬性沒有加進小屬性欄；本圖的Δ戰力用表上該步戰力差。"
    ),
}


def charts_section_html(data: TablesData) -> tuple[str, str]:
    """HTML for the upgrade-chart block and the breakthrough-chart block."""
    svgs = build_charts(data)
    up = (
        _figure(svgs["upgrade_efficiency"], CAPTIONS["upgrade_efficiency"], "chart-u-eff")
        + _figure(svgs["upgrade_gain_cost"], CAPTIONS["upgrade_gain_cost"], "chart-u-gain")
    )
    br = (
        _figure(svgs["break_efficiency"], CAPTIONS["break_efficiency"], "chart-b-eff")
        + _figure(svgs["break_gain_cost"], CAPTIONS["break_gain_cost"], "chart-b-gain")
    )
    return up, br
