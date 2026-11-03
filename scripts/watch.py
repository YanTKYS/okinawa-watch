"""Small, metadata-only Okinawa feed collector. Python 3.12+, standard library."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
AGENT = "OkinawaWatchBot"
USER_AGENT = "OkinawaWatchBot/0.1 (+https://github.com/YanTKYS/okinawa-watch)"
MAX_BYTES = 2_000_000


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def text_only(value):
    parser = PlainText()
    parser.feed(unescape(value or ""))
    return " ".join(" ".join(parser.parts).split())[:300]


def normalized(value):
    return unicodedata.normalize("NFKC", value).casefold()


def canonical_url(value):
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("invalid_http_url")
    if parts.username or parts.password or parts.port not in (None, 80, 443):
        raise ValueError("invalid_url_authority")
    host = parts.hostname.encode("idna").decode("ascii").lower()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
    return urlunsplit((parts.scheme.lower(), host, parts.path or "/", urlencode(sorted(query)), ""))


def domain_match(url, domain):
    host = (urlsplit(url).hostname or "").lower()
    domain = domain.lower().strip(".")
    return bool(domain) and (host == domain or host.endswith("." + domain))


def exclusion(article, rules):
    for domain in rules["exclude_domains"]:
        if domain_match(article["url"], domain):
            return "domain:" + domain
    title = normalized(article["title"])
    for word in rules["exclude_keywords"]:
        if word and normalized(word) in title:
            return "keyword:" + word
    categories = {normalized(x) for x in article.get("source_categories", [])}
    for category in rules["exclude_categories"]:
        if normalized(category) in categories:
            return "category:" + category
    return None


def publication(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    # No guessed timezone for naive timestamps; keep only the stated date.
    if parsed.tzinfo is None:
        return parsed.date().isoformat()
    return parsed.astimezone(JST).isoformat(timespec="seconds")


def localname(tag):
    return tag.rsplit("}", 1)[-1]


def parse_feed(payload, base_url):
    # Reject DTD/entities before XML parsing (including UTF-16/32 documents).
    probe = payload.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
        raise ValueError("xml_dtd_forbidden")
    root = ET.fromstring(payload)
    if localname(root.tag) not in ("rss", "RDF", "feed"):
        raise ValueError("not_rss_or_atom")
    items = []
    for node in root.iter():
        if localname(node.tag) not in ("item", "entry"):
            continue
        fields = {}
        categories = []
        link = ""
        for child in node:
            tag = localname(child.tag)
            if tag == "link":
                if child.get("href") and child.get("rel", "alternate") == "alternate":
                    link = child.get("href")
                elif child.text and child.text.strip():
                    link = child.text.strip()
            elif tag == "category":
                categories.append(text_only(child.get("term") or child.text or ""))
            elif tag in ("title", "pubDate", "published", "date", "updated"):
                fields[tag] = "".join(child.itertext())
        # Description/content are deliberately never retained or used for classification.
        raw_date = fields.get("pubDate") or fields.get("published") or fields.get("date")
        items.append({"title": text_only(fields.get("title", "")),
                      "url": urljoin(base_url, link) if link else "",
                      "published_at": publication(raw_date),
                      "source_categories": categories[:10]})
    return items


FULL_DATE = re.compile(r"(?<!\d)(20\d{2})(?:年|[/-])(\d{1,2})(?:月|[/-])(\d{1,2})日?(?!\d)")


def timing(title):
    """Only explicit, unambiguous full dates in the title qualify. Never use pubDate."""
    title = unicodedata.normalize("NFKC", title)
    matches = list(FULL_DATE.finditer(title))
    if not 1 <= len(matches) <= 2 or not re.search(r"開催|限定|締切|まで", title):
        return None
    remainder = FULL_DATE.sub("", title)
    if re.search(r"\d{1,2}月\d{1,2}日|[〜～~・]\s*\d{1,2}日|から|以降|毎週|毎月", remainder):
        return None
    if len(matches) == 2 and not re.search(r"[〜～~]|から", title[matches[0].end():matches[1].start()]):
        return None
    try:
        dates = [date(*map(int, match.groups())) for match in matches]
    except ValueError:
        return None
    if dates[-1] < dates[0]:
        return None
    # "まで/締切" states an end, not a start; single event dates state both.
    start = None if len(dates) == 1 and re.search(r"まで|締切", title) else dates[0].isoformat()
    return {"start": start, "end": dates[-1].isoformat(), "evidence": title[:300]}


def classify(article, rules):
    title = article["title"]
    article["timing"] = timing(title)
    labels = []
    if article["timing"]:
        labels.append("今だけ")
    if any(normalized(k) in normalized(title) for k in rules["deal_keywords"] if k):
        labels.append("お得")
    article["labels"] = labels or ["発見"]
    article["topic"] = next((topic for topic, words in rules["topics"].items()
                              if any(normalized(w) in normalized(title) for w in words)), "その他")
    article["region"] = next((region for region in rules["regions"] if region in title), None)
    return article


class SourceFailure(Exception):
    pass


class SameOriginRedirect(HTTPRedirectHandler):
    def __init__(self, origin, allowed):
        self.origin = origin
        self.allowed = allowed

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        newurl = urljoin(req.full_url, newurl)
        if origin(newurl) != self.origin or not self.allowed(newurl):
            raise SourceFailure("redirect_not_allowed")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def origin(url):
    parts = urlsplit(url)
    return (parts.scheme, parts.hostname, parts.port)


class Fetcher:
    def __init__(self):
        self.last_request = {}

    def get(self, url, delay=2, allowed=lambda url: True):
        canonical_url(url)  # Reject non-HTTP URLs and credential-bearing addresses.
        key = origin(url)
        if key in self.last_request:
            time.sleep(max(0, delay - (time.monotonic() - self.last_request[key])))
        opener = build_opener(SameOriginRedirect(key, allowed))
        self.last_request[key] = time.monotonic()
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        with opener.open(request, timeout=15) as response:
            payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise SourceFailure("response_too_large")
            return payload

    def feed(self, source):
        if source["method"] != "feed":
            raise SourceFailure("unsupported_method")
        url = source["url"]
        parts = urlsplit(url)
        robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
        robot = RobotFileParser()
        try:
            robot.parse(self.get(robots_url).decode("utf-8-sig").splitlines())
        except HTTPError as error:
            if error.code in (404, 410):
                robot.parse([])
            else:
                raise SourceFailure("robots_http_" + str(error.code)) from error
        except (OSError, UnicodeError, ValueError) as error:
            raise SourceFailure("robots_unavailable") from error
        if not robot.can_fetch(AGENT, url):
            raise SourceFailure("robots_disallow")
        delay = max(2, robot.crawl_delay(AGENT) or 0)
        rate = robot.request_rate(AGENT)
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        if delay > 30:
            raise SourceFailure("robots_delay_exceeds_budget")
        return parse_feed(self.get(url, delay, lambda target: robot.can_fetch(AGENT, target)), url)


def collect(sources, rules, previous, now=None, fetcher=None):
    now = now or datetime.now(JST)
    stamp = now.isoformat(timespec="seconds")
    fetcher = fetcher or Fetcher()
    articles = {}
    events = []
    stats = []

    def log(source_id, reason, item):
        events.append({"source_id": source_id, "reason": reason,
                       "title": str(item.get("title", ""))[:300], "url": str(item.get("url", ""))[:1000]})

    for old in previous.get("articles", []):
        old = dict(old)
        old["url"] = canonical_url(old["url"])
        reason = exclusion(old, rules)
        if reason:
            log(old["source_id"], "existing:" + reason, old)
        elif date.fromisoformat(old["collected_at"][:10]) >= now.date() - timedelta(days=rules["retention_days"]):
            articles[old["url"]] = classify(old, rules)

    for source in sources:
        stat = {"source_id": source["id"], "name": source["name"], "fetched": 0,
                "accepted": 0, "new": 0, "duplicate": 0, "excluded": {}, "status": "disabled"}
        stats.append(stat)
        if not source.get("enabled"):
            stat["reason"] = source.get("disabled_reason", "disabled_in_config")
            continue
        if any(domain_match(source["url"], d) for d in rules["exclude_domains"]):
            stat.update(status="blocked", reason="source_domain_excluded")
            continue
        try:
            items = fetcher.feed(source)
        except (OSError, ValueError, ET.ParseError, SourceFailure) as error:
            stat.update(status="failed", error=type(error).__name__, reason=str(error)[:300])
            continue
        stat.update(status="ok", fetched=len(items))
        counts = Counter()
        for item in items[:source.get("max_items", 20)]:
            item = dict(item)
            try:
                item["url"] = canonical_url(item["url"])
                if not item["title"]:
                    raise ValueError("missing_title")
                reason = exclusion(item, rules)
            except ValueError as error:
                reason = str(error)
            if reason:
                counts[reason] += 1
                log(source["id"], reason, item)
                continue
            stat["accepted"] += 1
            url = item["url"]
            if url in articles:
                stat["duplicate"] += 1
                existing = articles[url]
                if existing["source_id"] == source["id"]:
                    # Reflect corrections in a feed without changing the first-seen date.
                    if not item.get("published_at"):
                        item["published_at"] = existing.get("published_at")
                    existing.update(item)
                    classify(existing, rules)
                existing["last_seen_at"] = stamp
                continue
            item.update(id=hashlib.sha256(url.encode()).hexdigest()[:20], source_id=source["id"],
                        source_name=source["name"], collected_at=stamp, last_seen_at=stamp,
                        provenance="feed")
            articles[url] = classify(item, rules)
            stat["new"] += 1
        stat["excluded"] = dict(counts)
        stat["unprocessed"] = max(0, len(items) - source.get("max_items", 20))
    ordered = sorted(articles.values(), key=lambda a: (a.get("published_at") or a["collected_at"], a["url"]), reverse=True)
    document = {"schema_version": 1, "updated_at": stamp, "articles": ordered[:rules["max_articles"]]}
    report = {"collected_at": stamp, "sources": stats, "total_articles": len(document["articles"]),
              "topics": dict(Counter(a["topic"] for a in document["articles"])), "exclusions": events}
    return document, report


def build(data_path, report_path, output, sample=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for asset in (ROOT / "web").iterdir():
        if asset.is_file():
            shutil.copyfile(asset, output / asset.name)
    data = load(data_path)
    data["sample_mode"] = sample
    save(output / "articles.json", data)
    report = load(report_path) if Path(report_path).exists() else None
    # Full exclusion audit stays in Actions artifacts/local logs, not on Pages.
    public = {k: v for k, v in (report or {}).items() if k != "exclusions"}
    save(output / "status.json", public)
    (output / ".nojekyll").touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "build"))
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--rules", type=Path, default=ROOT / "config/rules.json")
    parser.add_argument("--data", type=Path, default=ROOT / "data/articles.json")
    parser.add_argument("--report", type=Path, default=ROOT / "work/collection-report.json")
    parser.add_argument("--output", type=Path, default=ROOT / "work/site")
    parser.add_argument("--sample", action="store_true", help="Build the explicitly labelled manual research sample")
    args = parser.parse_args()
    if args.command == "collect":
        sources = load(args.sources)["sources"]
        rules = load(args.rules)
        if len({s["id"] for s in sources}) != len(sources):
            parser.error("duplicate source ids")
        previous = load(args.data) if args.data.exists() else {"articles": []}
        data, report = collect(sources, rules, previous)
        save(args.data, data)
        save(args.report, report)
        for stat in report["sources"]:
            print(json.dumps(stat, ensure_ascii=False))
        print(json.dumps({"total_articles": report["total_articles"], "topics": report["topics"]}, ensure_ascii=False))
        active = [s for s in report["sources"] if s["status"] != "disabled"]
        if not active or all(s["status"] != "ok" for s in active):
            print("WARNING: no source succeeded; previous data retained. See collection-report.json.")
    else:
        path = ROOT / "data/research-sample.json" if args.sample else args.data
        build(path, args.report, args.output, args.sample)


if __name__ == "__main__":
    main()
