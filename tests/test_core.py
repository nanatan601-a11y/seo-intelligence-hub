import os
import tempfile
import unittest
from pathlib import Path


TEST_DIR = tempfile.TemporaryDirectory()
os.environ["SEO_HUB_DB"] = str(Path(TEST_DIR.name) / "test.db")

from seo_hub.core import (  # noqa: E402
    article_fingerprint,
    classify,
    clean_text,
    build_local_report,
    experts_data,
    init_db,
    normalized_url,
    paged_feed_url,
    parse_feed,
    source_list,
)


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    @classmethod
    def tearDownClass(cls):
        TEST_DIR.cleanup()

    def test_sources_are_seeded(self):
        sources = source_list()
        self.assertGreaterEqual(len(sources), 17)
        self.assertEqual(sum(source["category"] == "authority" for source in sources), 3)

    def test_expert_directory_has_full_roster(self):
        experts = experts_data()
        self.assertEqual(len(experts), 28)
        self.assertTrue(all(expert["x_url"].startswith("https://x.com/") for expert in experts))

    def test_parse_atom(self):
        feed = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>Rendering study</title><link href="https://example.com/post" />
        <summary>&lt;p&gt;A useful test&lt;/p&gt;</summary><updated>2026-10-18T09:00:00Z</updated></entry></feed>"""
        result = parse_feed(feed, "https://example.com/feed")
        self.assertEqual(result[0]["title"], "Rendering study")
        self.assertEqual(result[0]["summary"], "A useful test")

    def test_parse_rss(self):
        feed = b"""<rss><channel><item><title>Hreflang guide</title>
        <link>https://example.com/hreflang</link><description>Multilingual SEO</description>
        <pubDate>Sun, 18 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>"""
        result = parse_feed(feed, "https://example.com/feed")
        self.assertEqual(result[0]["url"], "https://example.com/hreflang")
        self.assertTrue(result[0]["published_at"].startswith("2026-10-18"))

    def test_classification(self):
        category, tags = classify("International SEO hreflang study", "multilingual localization", "content")
        self.assertEqual(category, "international")
        self.assertIn("hreflang", tags)
        category, tags = classify("How to recover from toxic backlinks", "link spam and disavow guidance", "content")
        self.assertEqual(category, "authority")
        self.assertIn("Link Risk", tags)

    def test_url_normalization_and_fingerprint(self):
        url = normalized_url("HTTPS://Example.com/post/?utm_source=x&a=1#top")
        self.assertEqual(url, "https://example.com/post?a=1")
        self.assertEqual(normalized_url("http://example.com/legacy"), "https://example.com/legacy")
        self.assertEqual(article_fingerprint("A", url), article_fingerprint("B", url))
        self.assertEqual(
            paged_feed_url("https://example.com/feed/?format=rss", 2),
            "https://example.com/feed/?format=rss&paged=2",
        )

    def test_clean_text(self):
        self.assertEqual(clean_text("<p>Hello&nbsp;SEO</p>"), "Hello SEO")

    def test_weekly_report_has_actionable_structure(self):
        report = build_local_report(save=False)
        self.assertEqual(report["version"], 2)
        self.assertEqual(len(report["groups"]["core_capabilities"]), 3)
        self.assertEqual(len(report["groups"]["professional_directions"]), 3)
        for group in report["groups"].values():
            for insight in group:
                self.assertIn("watch_points", insight)
                self.assertIn("impact", insight)
                self.assertIn("responses", insight)
                self.assertIn("evidence", insight)


if __name__ == "__main__":
    unittest.main()
