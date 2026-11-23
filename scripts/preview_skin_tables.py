#!/usr/bin/env python3
"""Write a local-only 造型 catalog preview under preview/. Does not touch docs/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thwiki.skin_tables import load_tables_data, render_html, render_markdown


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
    .table-dense table { font-size: 0.88rem; }
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
    html = html.replace("Top Heroes Wiki｜造型總表", "Top Heroes Wiki｜造型總表（本機預覽）")
    html = html.replace(
        '<p class="lede">本頁列出英雄造型圖鑑的可收集造型、成對造型、收集套裝、可升星效果與賽季限定效果，以及每位英雄可收集造型的屬性加總。</p>',
        '<p class="lede preview-banner">本機預覽，尚未發佈。這不是線上目錄，也不會寫進公開站。</p>\n'
        '      <p class="lede">本頁列出英雄造型圖鑑的可收集造型、成對造型、收集套裝、可升星效果與賽季限定效果，以及每位英雄可收集造型的屬性加總。</p>',
    )
    if "</head>" in html:
        html = html.replace("</head>", STYLE + "</head>", 1)
    return html


def main() -> int:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    data = load_tables_data()
    html_path = PREVIEW / "skin-tables.html"
    md_path = PREVIEW / "skin-tables.md"
    html_path.write_text(preview_page(render_html(data)), encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"wrote {html_path} ({html_path.stat().st_size} bytes)")
    print(f"wrote {md_path} ({md_path.stat().st_size} bytes)")
    print("verification", data.verifications)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
