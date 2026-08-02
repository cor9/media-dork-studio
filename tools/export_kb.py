#!/usr/bin/env python3
"""Export knowledge_base.json -> docs/knowledge_base.js for the static web app.

Single source of truth stays in the root JSON (used by the desktop app);
run this script after editing it:   python3 tools/export_kb.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = ROOT / "knowledge_base.json"
dst = ROOT / "docs" / "knowledge_base.js"

data = json.loads(src.read_text(encoding="utf-8"))
dst.write_text(
    "// GENERATED from knowledge_base.json by tools/export_kb.py - do not edit by hand.\n"
    "window.KNOWLEDGE_BASE = " + json.dumps(data, indent=2) + ";\n",
    encoding="utf-8",
)
print(f"wrote {dst.relative_to(ROOT)} ({len(json.dumps(data))} bytes of KB data)")
