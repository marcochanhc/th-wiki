from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = Path(os.environ.get("THWIKI_DOCS", PROJECT_ROOT / "docs"))
STATIC_DIR = PROJECT_ROOT / "static"

TOPHEROES_ROOT = Path(os.environ.get("TOPHEROES_ROOT", "/workspace/topheroes"))
DATA_DIR = TOPHEROES_ROOT / "data"
STRINGS_PATH = TOPHEROES_ROOT / "strings_zh.json"

# 前服 panel art exists at /workspace/th-art/page/lead.jpg (審判官 only),
# but pages currently reserve an empty portrait slot and do not publish it.
# Do not use star/talent art, Fandom, or unofficial 2D art.
LEAD_ART = {
    10031: Path(os.environ.get("TH_ART_LEAD_10031", "/workspace/th-art/page/lead.jpg")),
}

DATA_CUTOFF = "2026-11-05"
