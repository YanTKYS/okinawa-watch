"""Read-only candidate feed audit. Uses the collector's robots and pacing rules."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from watch import ROOT, JST, Fetcher, SourceFailure, load, save


class AuditFetcher(Fetcher):
    def __init__(self):
        super().__init__()
        self.requests = []

    def get(self, url, delay=2, allowed=lambda url: True):
        event = {"url": url}
        self.requests.append(event)
        try:
            payload = super().get(url, delay, allowed)
        except (OSError, ValueError, SourceFailure) as error:
            event.update(status="failed", error=type(error).__name__, reason=str(error)[:200])
            raise
        event.update(status="retrieved", bytes=len(payload))
        return payload


def audit(candidates):
    results = []
    fetcher = AuditFetcher()
    for source in candidates:
        fetcher.requests = []
        result = {"source_id": source["id"], "url": source["url"]}
        if source.get("skip_reason"):
            result.update(status="skipped", reason=source["skip_reason"], requests=[])
            results.append(result)
            continue
        try:
            articles = fetcher.feed(source)
            result.update(status="ok", robots_check="allowed_by_collector", fetched=len(articles),
                          categories=dict(Counter(c for a in articles for c in a["source_categories"])),
                          articles=articles[:source.get("max_items", 10)])
        except (OSError, ValueError, ET.ParseError, SourceFailure) as error:
            result.update(status="failed", error=type(error).__name__, reason=str(error)[:200])
        result["requests"] = fetcher.requests
        results.append(result)
    return {"checked_at": datetime.now(JST).isoformat(timespec="seconds"), "candidates": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/source-candidates.json")
    parser.add_argument("--output", type=Path, default=ROOT / "work/source-audit.json")
    args = parser.parse_args()
    result = audit(load(args.config)["candidates"])
    save(args.output, result)
    print("SOURCE_AUDIT_JSON=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
