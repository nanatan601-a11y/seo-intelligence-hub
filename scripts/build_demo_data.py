#!/usr/bin/env python3
"""Export a read-only data snapshot for the GitHub Pages portfolio."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seo_hub.core import (  # noqa: E402
    dashboard_data,
    experts_data,
    generate_weekly_report,
    init_db,
    list_articles,
    reclassify_articles,
    source_list,
)


def main() -> None:
    init_db()
    reclassify_articles(3650)
    generate_weekly_report(use_ai=False)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dashboard": dashboard_data(),
        "sources": source_list(),
        "experts": experts_data(),
        "articles": list_articles({"limit": ["200"]}),
    }
    output = ROOT / "static" / "demo-data.js"
    output.write_text(
        "window.SIGNAL_DESK_DEMO = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {output} with {len(payload['articles'])} articles.")


if __name__ == "__main__":
    main()
