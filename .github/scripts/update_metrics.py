#!/usr/bin/env python3
"""Refresh profile/metrics.json for the README research badges.

- citations, h_index, i10_index: Google Scholar profile page
  (robots.txt allows /citations?user= for all crawlers; fetched once per run
  with an honest User-Agent).
- publications: entries in the Publications section of alex.sigaras.com
  (journal articles, conference proceedings, abstracts, posters), read from
  the site's data file.

If a source can't be read, its previous values are kept and a warning is
printed, so a temporary block or site change never blanks a badge.
Standard library only.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHOLAR_URL = "https://scholar.google.com/citations?user=LupDxKUAAAAJ&hl=en"
SITE_DATA_URL = "https://alex.sigaras.com/assets/js/site.js"
PUBLICATION_TYPES = ("journal", "conference", "abstract", "poster")
OUT = Path(__file__).resolve().parents[2] / "profile" / "metrics.json"
USER_AGENT = "profile-metrics-bot/1.0 (+https://github.com/alexsigaras/alexsigaras)"


def fetch(url: str, encoding: str = "utf-8") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode(encoding, errors="replace")


def scholar_metrics() -> dict:
    html = fetch(SCHOLAR_URL, encoding="latin-1")
    rows = dict(
        (label, int(all_time))
        for label, all_time in re.findall(
            r'<td class="gsc_rsb_sc1"><a[^>]*>([^<]+)</a></td>'
            r'<td class="gsc_rsb_std">(\d+)</td>',
            html,
        )
    )
    if not {"Citations", "h-index", "i10-index"} <= rows.keys():
        raise ValueError("citation table not found (page layout changed or request blocked)")
    if rows["Citations"] <= 0 or rows["h-index"] <= 0:
        raise ValueError(f"implausible values: {rows}")
    return {
        "citations": rows["Citations"],
        "h_index": rows["h-index"],
        "i10_index": rows["i10-index"],
    }


def site_publications() -> dict:
    js = fetch(SITE_DATA_URL)
    types = re.findall(r'\{t:"([a-z_-]+)",y:\d{4}', js)
    count = sum(1 for t in types if t in PUBLICATION_TYPES)
    if count <= 0:
        raise ValueError("no publication entries found (site data format changed?)")
    return {"publications": count}


def main() -> int:
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    metrics = dict(previous)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for name, source in (("scholar", scholar_metrics), ("site", site_publications)):
        try:
            values = source()
        except Exception as exc:  # keep last good values
            print(f"::warning::{name}: {exc}; keeping previous values")
            continue
        if any(metrics.get(k) != v for k, v in values.items()):
            metrics.update(values)
            metrics[f"{name}_updated"] = today
        print(f"{name}: {values}")

    if not metrics:
        print("::error::no metrics available from any source")
        return 1

    if metrics != previous:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
        print(f"wrote {OUT}")
    else:
        print("no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
