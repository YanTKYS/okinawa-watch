"""Compare baseline publishers with all adopted metadata from the same collection."""
import argparse
from collections import Counter
from pathlib import Path
import json

from watch import ROOT, load, save


def publisher(article, sources):
    source = sources.get(article["source_id"], {})
    return source.get("publisher") or article.get("publisher") or article["source_name"]


def distribution(articles, sources):
    total = len(articles)
    publishers = Counter(publisher(a, sources) for a in articles)
    topics = Counter(a["topic"] for a in articles)
    def shares(counts):
        return {key: {"count": value, "percent": round(value * 100 / total, 1)}
                for key, value in sorted(counts.items())}
    return {"total": total, "publisher_count": len(publishers), "publishers": shares(publishers),
            "topics": shares(topics), "event_percent": round(topics["催し・体験"] * 100 / total, 1) if total else 0,
            "food_percent": round(topics["グルメ"] * 100 / total, 1) if total else 0,
            "largest_publisher_percent": round(max(publishers.values(), default=0) * 100 / total, 1) if total else 0}


def compare(data, source_config, baseline_publishers, collection=None):
    sources = {s["id"]: s for s in source_config["sources"]}
    articles = data["articles"]
    baseline = [a for a in articles if publisher(a, sources) in baseline_publishers]
    return {"collected_at": data.get("updated_at"), "baseline_publishers": baseline_publishers,
            "before": distribution(baseline, sources), "after": distribution(articles, sources),
            "source_results": (collection or {}).get("sources", []),
            "samples": [{"publisher": publisher(a, sources), "source_id": a["source_id"],
                         "title": a["title"], "url": a["url"], "topic": a["topic"],
                         "published_at": a.get("published_at")} for a in articles
                        if publisher(a, sources) not in baseline_publishers]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "work/live-articles.json")
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--collection", type=Path, default=ROOT / "work/live-report.json")
    parser.add_argument("--baseline-publisher", action="append", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "work/source-comparison.json")
    args = parser.parse_args()
    result = compare(load(args.data), load(args.sources), args.baseline_publisher,
                     load(args.collection) if args.collection.exists() else None)
    save(args.output, result)
    print("SOURCE_COMPARISON_JSON=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
