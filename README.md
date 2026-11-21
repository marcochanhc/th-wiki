# Top Heroes Wiki（靜態站骨架）

本專案把英雄條目做成可重複生成的靜態網站，可放到 GitHub Pages 發布。目前公開總目錄（英雄按聯盟、自然、部族列出完整名單），以及薔薇公主、審判官、修女三條已公開條目。

這不是 Cursor Page 的搬遷：頁面以普通 HTML／CSS 重寫，資料來自遊戲表，版面走共用樣板。改樣板後重新建置，所有英雄頁會一起更新。

## 本機建置

需要 Python 3.10 以上，只用標準庫。資料表預設讀：

- `/workspace/topheroes/data/*.json`
- `/workspace/topheroes/strings_zh.json`（utf-8-sig）
英雄頁左側預留頭像位置，目前不套角色圖。審判官的前服截圖仍在 `/workspace/th-art/page/lead.jpg`，建置時不會複製進 `docs/`。

可用環境變數改路徑：`TOPHEROES_ROOT`、`THWIKI_DOCS`。

```bash
cd /workspace/th-wiki
python3 build.py
```

輸出在 `docs/`：

- `docs/index.html` — 總目錄
- `docs/heroes/10043.html` — 薔薇公主
- `docs/heroes/10031.html` — 審判官
- `docs/heroes/10027.html` — 修女
- `docs/assets/` — 樣式（頭像位置為預留空位，暫不放圖）

建置後可再跑核對：

```bash
python3 scripts/check_build.py
```

用瀏覽器打開 `docs/index.html` 即可預覽。不需資料庫，也不必在每次有人打開頁面時重算。

## GitHub Pages

公開站以 `docs/` 為 Pages 來源。GitHub Pages 不能靠付費加大流量或容量；以這套 wiki 的規模，免費上限通常夠用。

遊戲資料表目前仍放在本機 `/workspace/topheroes/`，沒有一併打進這個專案。以後若要把產生器放進公開倉庫，需要另定資料表怎麼帶上建置環境（本專案不會改原始資料表或手冊原文）。

## 樣板與鎖定規則

條目章節順序與呈現規則跟 `top-heroes-wiki` 技能一致。稱號百分比、審判官已確認天賦的 ÷100、第二組英雄屬性等，只套用已鎖定項目，不會自行推到外觀、羈絆或其他英雄。
