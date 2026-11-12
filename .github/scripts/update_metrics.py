#!/usr/bin/env python3
"""Refresh profile/metrics.json for the README research badges.

All values come from one request to the Google Scholar profile page:
- citations, h_index, i10_index: the "Cited by" table
- publications: the number of articles listed on the profile

robots.txt allows /citations?user= for all crawlers but disallows paging
(cstart=), so the page is fetched once with pagesize=100 (Scholar's maximum)
and an honest User-Agent. Past 100 articles the count is reported as "100+".

If the page can't be read, the previous values are kept and a warning is
printed, so a temporary block never blanks a badge. Standard library only.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHOLAR_URL = "https://scholar.google.com/citations?user=LupDxKUAAAAJ&hl=en&pagesize=100"
OUT = Path(__file__).resolve().parents[2] / "profile" / "metrics.json"
USER_AGENT = "profile-metrics-bot/1.0 (+https://github.com/alexsigaras/alexsigaras)"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("latin-1", errors="replace")


def scholar_metrics() -> dict:
    html = fetch(SCHOLAR_URL)
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

    articles = html.count('<tr class="gsc_a_tr">')
    if articles <= 0:
        raise ValueError("article list not found")
    more = re.search(r'<button[^>]*id="gsc_bpf_more"[^>]*>', html)
    complete = more is None or "disabled" in more.group(0)

    return {
        "citations": rows["Citations"],
        "h_index": rows["h-index"],
        "i10_index": rows["i10-index"],
        "publications": articles if complete else f"{articles}+",
    }


def main() -> int:
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    try:
        values = scholar_metrics()
    except Exception as exc:  # keep last good values
        print(f"::warning::scholar: {exc}; keeping previous values")
        return 0 if previous else 1
    print(f"scholar: {values}")

    if all(previous.get(k) == v for k, v in values.items()):
        print("no change")
        return 0

    metrics = dict(values, updated=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
