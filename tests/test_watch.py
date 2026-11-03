from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SPEC = importlib.util.spec_from_file_location("watch", Path(__file__).resolve().parents[1] / "scripts/watch.py")
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)
RULES = w.load(w.ROOT / "config/rules.json")
NOW = datetime(2026, 11, 3, 12, tzinfo=w.JST)
SOURCE = {"id": "example", "name": "テスト媒体", "url": "https://example.com/feed", "method": "feed", "enabled": True}


def item(title="那覇市の図書館を発見", url="https://example.com/1", **more):
    return {"title": title, "url": url, "published_at": None, "source_categories": [], **more}


class StubFetcher:
    def __init__(self, values):
        self.values = values

    def feed(self, source):
        value = self.values[source["id"]]
        if isinstance(value, Exception):
            raise value
        return value


class WatchTests(unittest.TestCase):
    def test_rss_metadata_only(self):
        feed = b'''<rss><channel><item><title><![CDATA[<b>Library</b>]]></title><link>https://example.com/x?utm_source=rss</link><pubDate>Tue, 03 Nov 2026 01:00:00 +0000</pubDate><category>Culture</category><description>DO NOT STORE</description><content>DO NOT STORE</content></item></channel></rss>'''
        data = w.parse_feed(feed, SOURCE["url"])
        self.assertEqual(data[0]["title"], "Library")
        self.assertEqual(data[0]["published_at"], "2026-11-03T10:00:00+09:00")
        self.assertNotIn("DO NOT STORE", json.dumps(data))

    def test_atom_relative_links_without_inventing_publish_date(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Park</title><link rel="self" href="/self"/><link href="/park"/><updated>2026-11-03T00:00:00Z</updated><category term="Local"/></entry></feed>'''
        data = w.parse_feed(xml, SOURCE["url"])[0]
        self.assertEqual(data["url"], "https://example.com/park")
        self.assertIsNone(data["published_at"])
        self.assertEqual(data["source_categories"], ["Local"])

    def test_bad_feeds_and_entities(self):
        for xml in [b"<html/>", b'<rss><!DOCTYPE x></rss>', '<!DOCTYPE rss [<!ENTITY a "a">]><rss/>'.encode("utf-16")]:
            with self.assertRaises((ValueError, w.ET.ParseError)):
                w.parse_feed(xml, SOURCE["url"])

    def test_url_normalization_and_unsafe_links(self):
        self.assertEqual(w.canonical_url("https://EXAMPLE.com/a?z=2&utm_source=x&a=1#x"), "https://example.com/a?a=1&z=2")
        for url in ["javascript:alert(1)", "file:///etc/passwd", "https://user:pass@example.com/a"]:
            with self.assertRaises(ValueError):
                w.canonical_url(url)
        self.assertFalse(w.domain_match("https://notryukyushimpo.jp/", "ryukyushimpo.jp"))
        self.assertTrue(w.domain_match("https://www.ryukyushimpo.jp/", "ryukyushimpo.jp"))

    def test_rules_are_editable_and_categories_apply(self):
        self.assertEqual(w.exclusion(item("ＰＦＡＳの話題"), RULES), "keyword:PFAS")
        rules = {**RULES, "exclude_keywords": []}
        self.assertIsNone(w.exclusion(item("PFASの話題"), rules))
        self.assertEqual(w.exclusion(item(source_categories=["政治"]), RULES), "category:政治")
        self.assertEqual(w.exclusion(item(url="https://news.okinawatimes.co.jp/a"), RULES), "domain:okinawatimes.co.jp")

    def test_dates_do_not_use_publication_or_guess_years(self):
        for title in ["11月3日開催", "本日限定セール", "2026年11月3日公開の新商品", "2026年11月7日・8日開催", "2026年11月3日から販売", "2026年2月30日限定", "2026年11月3日と2026年11月8日開催"]:
            self.assertIsNone(w.timing(title), title)
        self.assertEqual(w.timing("2026年11月3日限定 無料体験")["end"], "2026-11-03")
        self.assertEqual(w.timing("2026/11/03〜2026/11/08 開催")["end"], "2026-11-08")
        self.assertIsNone(w.timing("2026年11月8日まで割引")["start"])
        self.assertEqual(w.classify(item("無料体験"), RULES)["labels"], ["お得"])
        self.assertEqual(w.classify(item("イベント開催", published_at="2026-11-03"), RULES)["labels"], ["発見"])

    def test_dedup_failure_isolation_and_audit(self):
        sources = [SOURCE, {**SOURCE, "id": "failed"}]
        fetcher = StubFetcher({"example": [item(), item(url="https://example.com/1?utm_source=x"), item("県知事の発表")], "failed": URLError("timeout")})
        data, report = w.collect(sources, RULES, {"articles": []}, NOW, fetcher)
        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(report["sources"][0]["new"], 1)
        self.assertEqual(report["sources"][0]["duplicate"], 1)
        self.assertEqual(report["sources"][1]["status"], "failed")
        self.assertEqual(report["exclusions"][0]["reason"], "keyword:県知事")
        self.assertIn("title", report["exclusions"][0])
        self.assertIn("url", report["exclusions"][0])
        # Retain data and first collection timestamp through a subsequent total outage.
        again, _ = w.collect(sources, RULES, data, NOW, StubFetcher({"example": URLError("down"), "failed": URLError("down")}))
        self.assertEqual(again["articles"], data["articles"])

    def test_feed_correction_updates_existing_metadata(self):
        data, _ = w.collect([SOURCE], RULES, {"articles": []}, NOW, StubFetcher({"example": [item()]}))
        stamp = data["articles"][0]["collected_at"]
        result, report = w.collect([SOURCE], RULES, data, NOW, StubFetcher({"example": [item("那覇市の図書館で無料体験")]}))
        self.assertEqual(result["articles"][0]["labels"], ["お得"])
        self.assertEqual(result["articles"][0]["collected_at"], stamp)
        self.assertEqual(report["sources"][0]["new"], 0)

    def test_edited_rules_remove_previously_collected_items(self):
        data, _ = w.collect([SOURCE], RULES, {"articles": []}, NOW, StubFetcher({"example": [item()]}))
        rules = {**RULES, "exclude_keywords": ["図書館"]}
        result, report = w.collect([], rules, data, NOW)
        self.assertEqual(result["articles"], [])
        self.assertEqual(report["exclusions"][0]["reason"], "existing:keyword:図書館")

    def test_robots_fail_closed_and_404_allowed(self):
        fetcher = w.Fetcher()
        cases = [(URLError("offline"), "robots_unavailable"),
                 (HTTPError("url", 403, "Forbidden", {}, None), "robots_http_403"),
                 (b"User-agent: *\nDisallow: /feed", "robots_disallow")]
        for response, reason in cases:
            with patch.object(fetcher, "get", side_effect=response if isinstance(response, Exception) else [response]):
                with self.assertRaisesRegex(w.SourceFailure, reason):
                    fetcher.feed(SOURCE)
        with patch.object(fetcher, "get", side_effect=[HTTPError("url", 404, "missing", {}, None), b"<rss><channel/></rss>"]):
            self.assertEqual(fetcher.feed(SOURCE), [])

    def test_redirects_and_rate_limit(self):
        redirect = w.SameOriginRedirect(w.origin(SOURCE["url"]), lambda url: "/private" not in url)
        request = w.Request(SOURCE["url"])
        for target in ["http://example.com/feed", "https://other.com/feed", "https://example.com/private"]:
            with self.assertRaises(w.SourceFailure):
                redirect.redirect_request(request, None, 302, "", {}, target)
        fetcher = w.Fetcher()
        with patch.object(fetcher, "get", return_value=b"User-agent: *\nCrawl-delay: 60"):
            with self.assertRaisesRegex(w.SourceFailure, "budget"):
                fetcher.feed(SOURCE)

    def test_build_does_not_publish_audit_or_mix_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            w.save(path / "data.json", {"articles": []})
            w.save(path / "report.json", {"sources": [], "exclusions": [{"title": "excluded"}]})
            w.build(path / "data.json", path / "report.json", path / "site")
            self.assertNotIn("exclusions", w.load(path / "site/status.json"))
            self.assertFalse(w.load(path / "site/articles.json")["sample_mode"])
            self.assertTrue((path / "site/index.html").exists())


if __name__ == "__main__":
    unittest.main()
