#!/usr/bin/env python3
"""Historical local-only 符文 catalog preview under preview/. Does not touch docs/. If rerun, still injects the unpublished banner and rewrites CSS / public paths."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thwiki.rune_tables import load_tables_data, render_html, render_markdown


PREVIEW = ROOT / "preview"
STYLE = """
  <style>
    .preview-banner {
      background: var(--callout, #efe6c9);
      border-left: 4px solid var(--accent, #8a6a14);
      padding: 0.55rem 0.85rem;
      border-radius: 0 6px 6px 0;
    }
    .jump-nav { font-size: 0.92rem; color: var(--muted); }
    .jump-nav a { margin-right: 0.45rem; }
    .table-wrap thead th {
      position: sticky;
      top: 0;
      background: var(--bg-card, #fffdf7);
      z-index: 2;
    }
  </style>
"""


def preview_page(html: str) -> str:
    html = html.replace('href="assets/css/site.css"', 'href="../docs/assets/css/site.css"')
    html = html.replace('href="index.html', 'href="../docs/index.html')
    html = html.replace('href="heroes/', 'href="../docs/heroes/')
    html = html.replace('href="exclusive.html"', 'href="../docs/exclusive.html"')
    for name in (
        "valhalla", "skins", "equipment", "lord-equipment",
        "troops", "artifacts", "pets", "runes",
    ):
        html = html.replace(f'href="{name}.html"', f'href="../docs/{name}.html"')
    html = html.replace('href="valhalla.html"', 'href="../docs/valhalla.html"')
    html = html.replace('href="skins.html"', 'href="../docs/skins.html"')
    html = html.replace("Top Heroes Wiki｜符文總表", "Top Heroes Wiki｜符文總表（本機預覽）")
    html = html.replace(
        '<p class="lede">本頁列出官方界面所稱的「符文」：介面標題「隊列符文」的 team_rune 與 team_rune_bond'
        '（五種、三營、1–10 級與羈絆），以及只在 LocalLow 包出現的 player_rune 表'
        '（六個 type、1–12 級，含精煉欄）。不評定強弱，也不做搭配模擬。</p>',
        '<p class="lede preview-banner">本機預覽，尚未發佈。這不是線上目錄，也不會寫進公開站。</p>\n'
        '      <p class="lede">本頁列出官方界面所稱的「符文」：介面標題「隊列符文」的 team_rune 與 team_rune_bond'
        '（五種、三營、1–10 級與羈絆），以及只在 LocalLow 包出現的 player_rune 表'
        '（六個 type、1–12 級，含精煉欄）。不評定強弱，也不做搭配模擬。</p>',
    )
    if "</head>" in html:
        html = html.replace("</head>", STYLE + "</head>", 1)
    return html


def main() -> int:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    data = load_tables_data()
    html_path = PREVIEW / "rune-tables.html"
    md_path = PREVIEW / "rune-tables.md"
    html_path.write_text(preview_page(render_html(data)), encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"wrote {html_path} ({html_path.stat().st_size} bytes)")
    print(f"wrote {md_path} ({md_path.stat().st_size} bytes)")
    print("verification", data.verifications)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
