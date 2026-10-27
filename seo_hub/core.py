from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("SEO_HUB_DB", DATA_DIR / "seo_hub.db"))
SOURCES_PATH = ROOT / "config" / "sources.json"
EXPERTS_PATH = ROOT / "config" / "experts.json"

CATEGORY_LABELS = {
    "content": "Content SEO",
    "technical": "Technical SEO",
    "authority": "Authority SEO",
    "international": "International SEO",
    "geo": "GEO / AI Search",
    "sem": "SEM",
}

CORE_CATEGORIES = ("content", "technical", "authority")
SPECIALTY_CATEGORIES = ("international", "geo", "sem")

CATEGORY_GUIDANCE = {
    "content": {
        "impact": "May affect topic prioritization, content quality, search-intent alignment, and organic conversion efficiency.",
        "responses": [
            "Audit priority pages for verifiable information gain instead of simply increasing content volume.",
            "Map new signals to existing topic clusters and decide whether to update, consolidate, or create pages.",
            "Validate changes with rankings, CTR, conversions, and content-decay data.",
        ],
    },
    "technical": {
        "impact": "May affect crawling, rendering, index eligibility, and page experience, with the potential for sitewide impact.",
        "responses": [
            "Reproduce the issue in staging and confirm scope with Search Console, logs, and crawlers.",
            "Check that robots directives, canonicals, status codes, sitemaps, and rendered output agree.",
            "Turn confirmed findings into repeatable regression checks.",
        ],
    },
    "authority": {
        "impact": "May affect brand and author trust, the quality of third-party citations, and the ability to compete on difficult topics.",
        "responses": [
            "Prioritize original data, expert commentary, and useful assets that naturally earn citations.",
            "Audit brand mentions, author profiles, and high-value pages for consistent entity signals.",
            "Evaluate link opportunities by relevance and editorial value, not volume alone.",
        ],
    },
    "international": {
        "impact": "May affect index targeting, intent alignment, local trust, and conversion performance across languages and markets.",
        "responses": [
            "Validate hreflang, canonicals, regional URLs, and redirect logic market by market.",
            "Research local keywords, SERPs, and cultural context instead of relying on literal translation.",
            "Track indexing, rankings, clicks, and conversions separately for each market.",
        ],
    },
    "geo": {
        "impact": "May affect brand inclusion, citations, description accuracy, and zero-click visibility in AI answers.",
        "responses": [
            "Maintain a fixed prompt set and track whether and how the brand is mentioned across platforms and markets.",
            "Trace cited pages and strengthen clear entities, original evidence, and quotable information structures.",
            "Evaluate AI visibility alongside branded search and assisted conversions, not traffic alone.",
        ],
    },
    "sem": {
        "impact": "May affect paid-search reach, budget efficiency, automation controls, and landing-page conversion.",
        "responses": [
            "Check whether platform updates change active campaigns, APIs, bidding, or attribution settings.",
            "Validate automation in a small-budget experiment before scaling.",
            "Share paid-search query data with SEO to uncover content and landing-page opportunities.",
        ],
    },
}

KEYWORDS = {
    "technical": {
        "crawl": 3, "crawler": 3, "crawling": 3, "index": 2, "indexing": 3,
        "rendering": 3, "javascript": 3, "robots.txt": 3, "sitemap": 2,
        "canonical": 3, "structured data": 2, "schema": 2, "core web vitals": 3,
        "lcp": 2, "inp": 2, "cls": 2, "migration": 2, "log file": 3,
        "http": 1, "search console": 1, "googlebot": 3, "performance": 1,
    },
    "content": {
        "content": 2, "keyword": 2, "search intent": 3, "topic cluster": 3,
        "on-page": 2, "internal link": 2, "eeat": 3, "e-e-a-t": 3,
        "editorial": 2, "copywriting": 2, "content marketing": 2,
        "semantic": 2, "entity": 1, "content strategy": 3,
    },
    "authority": {
        "link building": 4, "backlink": 4, "backlinks": 4, "digital pr": 4,
        "brand mention": 4, "unlinked mention": 4, "earned media": 3,
        "media coverage": 3, "public relations": 3, "journalist": 2,
        "outreach": 3, "pitching": 2, "editorial link": 4,
        "referring domain": 4, "anchor text": 3, "link equity": 4,
        "link earning": 4, "link spam": 4, "toxic link": 4, "disavow": 4,
        "nofollow": 3, "sponsored link": 3, "domain authority": 3,
        "author authority": 4, "authorship": 3, "entity authority": 4,
        "brand authority": 4, "brand signal": 3, "online reputation": 4,
        "reputation management": 4, "co-citation": 3, "brand search": 2,
        "reputation": 2, "authority": 2,
    },
    "international": {
        "international seo": 4, "multilingual": 3, "multi-regional": 3,
        "hreflang": 4, "localization": 3, "localisation": 3, "transcreation": 3,
        "cctld": 3, "geo-targeting": 3, "global seo": 3, "regional search": 2,
        "cross-market": 3, "language targeting": 3,
    },
    "geo": {
        "ai search": 4, "generative search": 4, "geo": 2, "llm": 3,
        "ai overview": 4, "ai mode": 4, "chatgpt search": 4, "perplexity": 3,
        "answer engine": 3, "citation": 1, "brand visibility": 2,
        "generative engine optimization": 4,
    },
    "sem": {
        "google ads": 4, "microsoft advertising": 4, "paid search": 4,
        "ppc": 3, "campaign": 1, "bidding": 3, "performance max": 4,
        "pmax": 4, "ad creative": 3, "cpc": 2, "conversion": 1,
        "shopping ads": 3, "search ads": 3,
    },
}

TAG_PATTERNS = {
    "Crawling": ("crawl", "googlebot"),
    "Indexing": ("indexing", "index coverage"),
    "JavaScript": ("javascript", "rendering"),
    "CWV": ("core web vitals", "lcp", "inp", "cls"),
    "Structured Data": ("structured data", "schema"),
    "Content Strategy": ("content strategy", "search intent", "topic cluster"),
    "Link Building": ("backlink", "link building", "digital pr"),
    "Digital PR": ("digital pr", "earned media", "media coverage", "journalist", "pitching"),
    "Brand Mentions": ("brand mention", "unlinked mention", "brand signal"),
    "Link Risk": ("link spam", "toxic link", "disavow", "nofollow", "sponsored link"),
    "Entity Authority": ("author authority", "authorship", "entity authority", "brand authority"),
    "International": ("international seo", "multilingual", "multi-regional"),
    "hreflang": ("hreflang",),
    "AI Search": ("ai search", "ai overview", "ai mode", "llm", "generative"),
    "Google Ads": ("google ads", "pmax", "performance max"),
    "Research": ("study", "research", "data", "report"),
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                owner TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'industry',
                feed_url TEXT NOT NULL DEFAULT '',
                site_url TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT 'content',
                tier TEXT NOT NULL DEFAULT 'T2',
                market TEXT NOT NULL DEFAULT 'global',
                language TEXT NOT NULL DEFAULT 'en',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_fetch_at TEXT,
                last_status TEXT NOT NULL DEFAULT 'pending',
                last_error TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL UNIQUE,
                source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                category TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                source_tier TEXT NOT NULL DEFAULT 'T2',
                market TEXT NOT NULL DEFAULT 'global',
                language TEXT NOT NULL DEFAULT 'en',
                is_bookmarked INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
            CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);
            CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);

            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL UNIQUE,
                generated_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                report_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                organization TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT '',
                primary_category TEXT NOT NULL DEFAULT 'technical',
                specialties TEXT NOT NULL DEFAULT '[]',
                market TEXT NOT NULL DEFAULT 'global',
                website_url TEXT NOT NULL DEFAULT '',
                x_url TEXT NOT NULL DEFAULT '',
                priority INTEGER NOT NULL DEFAULT 100,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            """
        )
    seed_sources()
    seed_experts()
    normalize_existing_article_urls()


def seed_sources() -> None:
    seeds = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    with connect() as conn:
        for source in seeds:
            conn.execute(
                """
                INSERT INTO sources
                    (slug, name, owner, kind, feed_url, site_url, category, tier,
                     market, language, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name=excluded.name, owner=excluded.owner, kind=excluded.kind,
                    feed_url=excluded.feed_url, site_url=excluded.site_url,
                    category=excluded.category, tier=excluded.tier,
                    market=excluded.market, language=excluded.language
                """,
                (
                    source["slug"], source["name"], source.get("owner", ""),
                    source.get("kind", "industry"), source.get("feed_url", ""),
                    source.get("site_url", ""), source.get("category", "content"),
                    source.get("tier", "T2"), source.get("market", "global"),
                    source.get("language", "en"), int(source.get("enabled", True)), utc_now(),
                ),
            )


def seed_experts() -> None:
    """Keep the expert directory separate from fetchable RSS sources.

    An expert can have an X profile and website without pretending that either
    is a stable machine-readable feed. Articles are linked to the directory by
    the source owner name when an RSS source is available.
    """
    seeds = json.loads(EXPERTS_PATH.read_text(encoding="utf-8"))
    with connect() as conn:
        for expert in seeds:
            conn.execute(
                """
                INSERT INTO experts
                    (slug, name, organization, role, primary_category, specialties,
                     market, website_url, x_url, priority, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name=excluded.name, organization=excluded.organization,
                    role=excluded.role, primary_category=excluded.primary_category,
                    specialties=excluded.specialties, market=excluded.market,
                    website_url=excluded.website_url, x_url=excluded.x_url,
                    priority=excluded.priority, enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    expert["slug"], expert["name"], expert.get("organization", ""),
                    expert.get("role", ""), expert.get("primary_category", "technical"),
                    json.dumps(expert.get("specialties", []), ensure_ascii=False),
                    expert.get("market", "global"), expert.get("website_url", ""),
                    expert.get("x_url", ""), int(expert.get("priority", 100)),
                    int(expert.get("enabled", True)), utc_now(),
                ),
            )


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    value = dict(row)
    for key in ("enabled", "feed_enabled", "is_bookmarked", "is_read"):
        if key in value:
            value[key] = bool(value[key])
    for json_key in ("tags", "specialties"):
        if json_key not in value:
            continue
        try:
            value[json_key] = json.loads(value[json_key])
        except (TypeError, json.JSONDecodeError):
            value[json_key] = []
    return value


def source_list() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sources ORDER BY enabled DESC, tier, name COLLATE NOCASE"
        ).fetchall()
    return [row_dict(row) for row in rows]  # type: ignore[misc]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def save_source(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    feed_url = str(payload.get("feed_url", "")).strip()
    site_url = str(payload.get("site_url", "")).strip()
    if not name:
        raise ValueError("Source name is required")
    if feed_url:
        validate_public_url(feed_url, resolve=False)
    if site_url:
        validate_public_url(site_url, resolve=False)
    category = str(payload.get("category", "content"))
    if category not in CATEGORY_LABELS:
        raise ValueError("Invalid intelligence channel")
    tier = str(payload.get("tier", "T2"))
    if tier not in {"T0", "T1", "T2", "T3", "T4"}:
        raise ValueError("Invalid source tier")
    slug = slugify(str(payload.get("slug") or name))
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sources
                (slug, name, owner, kind, feed_url, site_url, category, tier,
                 market, language, enabled, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug, name, str(payload.get("owner", "")).strip(),
                str(payload.get("kind", "industry")), feed_url, site_url, category, tier,
                str(payload.get("market", "global")), str(payload.get("language", "en")),
                int(bool(payload.get("enabled", True))), utc_now(),
            ),
        )
        row = conn.execute("SELECT * FROM sources WHERE id=?", (cursor.lastrowid,)).fetchone()
    return row_dict(row)  # type: ignore[return-value]


def update_source(source_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"name", "owner", "kind", "feed_url", "site_url", "category", "tier", "market", "language", "enabled"}
    updates: list[str] = []
    values: list[Any] = []
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key in {"feed_url", "site_url"} and value:
            validate_public_url(str(value), resolve=False)
        if key == "category" and value not in CATEGORY_LABELS:
            raise ValueError("Invalid intelligence channel")
        if key == "tier" and value not in {"T0", "T1", "T2", "T3", "T4"}:
            raise ValueError("Invalid source tier")
        if key == "enabled":
            value = int(bool(value))
        updates.append(f"{key}=?")
        values.append(value)
    if not updates:
        raise ValueError("No supported fields to update")
    values.append(source_id)
    with connect() as conn:
        conn.execute(f"UPDATE sources SET {', '.join(updates)} WHERE id=?", values)
        row = conn.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if row is None:
        raise ValueError("Source not found")
    return row_dict(row)  # type: ignore[return-value]


def validate_public_url(url: str, resolve: bool = True) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public HTTP/HTTPS URLs are supported")
    host = parsed.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Local addresses cannot be fetched")
    if not resolve:
        return
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve source hostname: {exc}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        # Some managed desktop runtimes route approved public egress through the
        # RFC 2544 benchmarking range. It is not a private/LAN destination and
        # is safe to allow here while loopback, RFC1918 and link-local remain blocked.
        if ip in ipaddress.ip_network("198.18.0.0/15"):
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Private or reserved network addresses cannot be fetched")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, timeout: int = 12) -> bytes:
    validate_public_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SEO-Intelligence-Hub/1.0 (+local RSS reader)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
            "Accept-Encoding": "identity",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    with opener.open(request, timeout=timeout) as response:
        if response.geturl() != url:
            validate_public_url(response.geturl())
        return response.read(5_000_001)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(node):
        if local_name(child.tag) in wanted:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return ""


def entry_link(node: ET.Element, base_url: str) -> str:
    for child in list(node):
        if local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href", "").strip()
        rel = child.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return urllib.parse.urljoin(base_url, href)
        if child.text and child.text.strip():
            return urllib.parse.urljoin(base_url, child.text.strip())
    return ""


def clean_text(value: str, limit: int = 700) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value


def parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError):
        pass
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return None


def parse_feed(data: bytes, base_url: str) -> list[dict[str, Any]]:
    if len(data) > 5_000_000:
        raise ValueError("Feed exceeds the 5 MB limit")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Unable to parse feed XML: {exc}") from exc
    entries = [node for node in root.iter() if local_name(node.tag) in {"item", "entry"}]
    results: list[dict[str, Any]] = []
    for node in entries[:50]:
        title = clean_text(child_text(node, ("title",)), 300)
        url = entry_link(node, base_url)
        if not title or not url:
            continue
        summary = child_text(node, ("description", "summary", "content", "encoded"))
        author = child_text(node, ("author", "creator"))
        published = child_text(node, ("pubdate", "published", "updated", "date"))
        results.append(
            {
                "title": title,
                "url": url,
                "summary": clean_text(summary),
                "author": clean_text(author, 120),
                "published_at": parse_date(published),
            }
        )
    if not results:
        raise ValueError("No article entries were found in the feed")
    return results


def normalized_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    scheme = parsed.scheme.lower()
    # Feed publishers often leave legacy HTTP links in otherwise HTTPS sites.
    # Canonicalizing them avoids an extra redirect and browser security prompt.
    if scheme == "http":
        scheme = "https"
    return urllib.parse.urlunsplit((scheme, parsed.netloc.lower(), path, urllib.parse.urlencode(query), ""))


def normalize_existing_article_urls() -> None:
    """Upgrade previously stored HTTP article links and preserve deduplication."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, url FROM articles WHERE url LIKE 'http://%'"
        ).fetchall()
        for row in rows:
            new_url = normalized_url(row["url"])
            new_fingerprint = article_fingerprint(row["title"], new_url)
            duplicate = conn.execute(
                "SELECT id FROM articles WHERE fingerprint=? AND id<>?",
                (new_fingerprint, row["id"]),
            ).fetchone()
            if duplicate:
                conn.execute("DELETE FROM articles WHERE id=?", (row["id"],))
            else:
                conn.execute(
                    "UPDATE articles SET url=?, fingerprint=? WHERE id=?",
                    (new_url, new_fingerprint, row["id"]),
                )


def classify(title: str, summary: str, default: str) -> tuple[str, list[str]]:
    haystack = f"{title} {summary}".lower()
    # The source category is a tie-breaker, not a hard assignment. A clear
    # article-level signal such as GEO or technical SEO should still win even
    # when it appears in an Authority-focused publication.
    scores = {category: (1 if category == default else 0) for category in CATEGORY_LABELS}
    for category, words in KEYWORDS.items():
        for word, weight in words.items():
            if word in haystack:
                scores[category] += weight
    highest = max(scores.values())
    category = default if scores.get(default) == highest else max(scores, key=scores.get)  # type: ignore[arg-type]
    tags = [label for label, patterns in TAG_PATTERNS.items() if any(pattern in haystack for pattern in patterns)]
    return category, tags[:6]


def article_fingerprint(title: str, url: str) -> str:
    base = normalized_url(url) or re.sub(r"\W+", "", title.lower())
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def paged_feed_url(feed_url: str, page: int) -> str:
    if page <= 1:
        return feed_url
    parsed = urllib.parse.urlsplit(feed_url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    query["paged"] = str(page)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def fetch_feed_entries(feed_url: str, backfill_days: int | None = None) -> tuple[list[dict[str, Any]], int]:
    """Fetch one feed, optionally walking WordPress-style pages for a time window."""
    cutoff = None
    if backfill_days is not None:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=backfill_days)
    collected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    max_pages = 8 if cutoff else 1
    for page in range(1, max_pages + 1):
        page_url = paged_feed_url(feed_url, page)
        try:
            page_entries = parse_feed(fetch_url(page_url), page_url)
        except Exception:
            if page == 1:
                raise
            break
        new_entries = 0
        dated_entries: list[dt.datetime] = []
        for entry in page_entries:
            canonical = normalized_url(entry["url"])
            if canonical in seen_urls:
                continue
            seen_urls.add(canonical)
            collected.append(entry)
            new_entries += 1
            if entry["published_at"]:
                dated_entries.append(dt.datetime.fromisoformat(entry["published_at"]))
        if page > 1 and new_entries == 0:
            break
        # Syndicated feeds are reverse chronological. Once a page reaches the
        # cutoff, later pages cannot contribute to the requested window.
        if cutoff and dated_entries and min(dated_entries) < cutoff:
            break
    if not cutoff:
        return collected, 0
    kept: list[dict[str, Any]] = []
    skipped = 0
    for entry in collected:
        if not entry["published_at"]:
            kept.append(entry)
            continue
        if dt.datetime.fromisoformat(entry["published_at"]) >= cutoff:
            kept.append(entry)
        else:
            skipped += 1
    return kept, skipped


def ingest_source(source: dict[str, Any], backfill_days: int | None = None) -> dict[str, Any]:
    source_id = int(source["id"])
    feed_url = str(source.get("feed_url", ""))
    if not feed_url:
        return {"source_id": source_id, "name": source["name"], "status": "skipped", "added": 0, "reason": "No feed configured"}
    now = utc_now()
    try:
        entries, skipped_old = fetch_feed_entries(feed_url, backfill_days)
        added = 0
        with connect() as conn:
            for entry in entries:
                category, tags = classify(entry["title"], entry["summary"], source["category"])
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO articles
                        (fingerprint, source_id, title, url, summary, author, published_at,
                         fetched_at, category, tags, source_tier, market, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article_fingerprint(entry["title"], entry["url"]), source_id,
                        entry["title"], normalized_url(entry["url"]), entry["summary"],
                        entry["author"], entry["published_at"], now, category,
                        json.dumps(tags, ensure_ascii=False), source["tier"],
                        source["market"], source["language"],
                    ),
                )
                added += max(cursor.rowcount, 0)
            conn.execute(
                "UPDATE sources SET last_fetch_at=?, last_status='ok', last_error='' WHERE id=?",
                (now, source_id),
            )
        return {
            "source_id": source_id,
            "name": source["name"],
            "status": "ok",
            "added": added,
            "found": len(entries),
            "skipped_old": skipped_old,
        }
    except Exception as exc:  # Keep one broken source from stopping the complete refresh.
        message = clean_text(str(exc), 350)
        if not message:
            reason = getattr(exc, "reason", None)
            message = type(exc).__name__
            if reason is not None:
                message += f": {type(reason).__name__}"
        with connect() as conn:
            conn.execute(
                "UPDATE sources SET last_fetch_at=?, last_status='error', last_error=? WHERE id=?",
                (now, message, source_id),
            )
        return {"source_id": source_id, "name": source["name"], "status": "error", "added": 0, "reason": message}


def refresh_sources(source_id: int | None = None) -> dict[str, Any]:
    started_at = utc_now()
    sources = source_list()
    selected = [s for s in sources if s["enabled"] and s.get("feed_url")]
    if source_id is not None:
        selected = [s for s in selected if int(s["id"]) == source_id]
    results: list[dict[str, Any]] = []
    # Network-bound feeds are independent. A small worker pool keeps a slow or
    # blocked site from making a complete refresh take several minutes.
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(selected)))) as pool:
        futures = {pool.submit(ingest_source, source): source for source in selected}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item.get("name", "")).lower())
    return {
        "started_at": started_at,
        "finished_at": utc_now(),
        "sources": len(results),
        "added": sum(result.get("added", 0) for result in results),
        "ok": sum(result["status"] == "ok" for result in results),
        "errors": sum(result["status"] == "error" for result in results),
        "results": results,
    }


def reclassify_articles(days: int = 90) -> dict[str, int]:
    """Apply the current taxonomy to recent articles after keyword changes."""
    days = min(max(int(days), 1), 3650)
    changed = 0
    reviewed = 0
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.title, a.summary, a.category, a.tags, s.category AS source_category
            FROM articles a JOIN sources s ON s.id=a.source_id
            WHERE COALESCE(a.published_at, a.fetched_at) >= datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchall()
        for row in rows:
            reviewed += 1
            category, tags = classify(row["title"], row["summary"], row["source_category"])
            encoded_tags = json.dumps(tags, ensure_ascii=False)
            if category != row["category"] or encoded_tags != row["tags"]:
                conn.execute(
                    "UPDATE articles SET category=?, tags=? WHERE id=?",
                    (category, encoded_tags, row["id"]),
                )
                changed += 1
    return {"reviewed": reviewed, "changed": changed}


def backfill_sources(days: int = 90, source_ids: Iterable[int] | None = None) -> dict[str, Any]:
    """Backfill the available paged feed history and refresh recent taxonomy."""
    days = min(max(int(days), 1), 3650)
    wanted = {int(value) for value in source_ids} if source_ids is not None else None
    selected = [
        source for source in source_list()
        if source["enabled"] and source.get("feed_url")
        and (wanted is None or int(source["id"]) in wanted)
    ]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(selected)))) as pool:
        futures = {pool.submit(ingest_source, source, days): source for source in selected}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item.get("name", "")).lower())
    classification = reclassify_articles(days)
    return {
        "days": days,
        "sources": len(results),
        "added": sum(result.get("added", 0) for result in results),
        "ok": sum(result["status"] == "ok" for result in results),
        "errors": sum(result["status"] == "error" for result in results),
        "classification": classification,
        "results": results,
    }


def list_articles(params: dict[str, list[str]]) -> list[dict[str, Any]]:
    where = ["1=1"]
    values: list[Any] = []
    category = first_param(params, "category")
    if category in CATEGORY_LABELS:
        where.append("a.category=?")
        values.append(category)
    if first_param(params, "official") == "1":
        where.append("a.source_tier='T0'")
    if first_param(params, "experts") == "1":
        where.append("s.kind='expert'")
    source = first_param(params, "source")
    if source and source.isdigit():
        where.append("a.source_id=?")
        values.append(int(source))
    market = first_param(params, "market")
    if market:
        where.append("a.market=?")
        values.append(market)
    if first_param(params, "bookmarked") == "1":
        where.append("a.is_bookmarked=1")
    query = first_param(params, "q").strip()
    if query:
        where.append("(a.title LIKE ? OR a.summary LIKE ? OR a.tags LIKE ? OR s.name LIKE ?)")
        token = f"%{query}%"
        values.extend([token, token, token, token])
    days = first_param(params, "days")
    if days.isdigit() and int(days) > 0:
        where.append("COALESCE(a.published_at, a.fetched_at) >= datetime('now', ?)")
        values.append(f"-{min(int(days), 3650)} days")
    try:
        limit = min(max(int(first_param(params, "limit") or 60), 1), 200)
    except ValueError:
        limit = 60
    values.append(limit)
    sql = f"""
        SELECT a.*, s.name AS source_name, s.owner AS source_owner,
               s.kind AS source_kind, s.site_url AS source_site_url
        FROM articles a JOIN sources s ON s.id=a.source_id
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(a.published_at, a.fetched_at) DESC, a.id DESC
        LIMIT ?
    """
    with connect() as conn:
        rows = conn.execute(sql, values).fetchall()
    return [row_dict(row) for row in rows]  # type: ignore[misc]


def first_param(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name, [])
    return values[0] if values else ""


def update_article(article_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"is_bookmarked", "is_read"}
    updates = []
    values: list[Any] = []
    for key in allowed:
        if key in payload:
            updates.append(f"{key}=?")
            values.append(int(bool(payload[key])))
    if not updates:
        raise ValueError("No supported fields to update")
    values.append(article_id)
    with connect() as conn:
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id=?", values)
        row = conn.execute(
            """SELECT a.*, s.name AS source_name, s.owner AS source_owner,
                      s.kind AS source_kind, s.site_url AS source_site_url
               FROM articles a JOIN sources s ON s.id=a.source_id WHERE a.id=?""",
            (article_id,),
        ).fetchone()
    if row is None:
        raise ValueError("Article not found")
    return row_dict(row)  # type: ignore[return-value]


def dashboard_data() -> dict[str, Any]:
    with connect() as conn:
        stats = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN fetched_at >= datetime('now','-7 days') THEN 1 ELSE 0 END) AS week,
                   SUM(CASE WHEN source_tier='T0' AND fetched_at >= datetime('now','-7 days') THEN 1 ELSE 0 END) AS official_week,
                   SUM(is_bookmarked) AS bookmarked,
                   SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) AS unread
            FROM articles
            """
        ).fetchone()
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM articles GROUP BY category"
        ).fetchall()
        source_stats = conn.execute(
            """SELECT COUNT(*) AS total, SUM(enabled) AS enabled,
                      SUM(CASE WHEN last_status='ok' THEN 1 ELSE 0 END) AS healthy,
                      SUM(CASE WHEN last_status='error' THEN 1 ELSE 0 END) AS errors
               FROM sources"""
        ).fetchone()
        latest_report = conn.execute(
            "SELECT * FROM weekly_reports ORDER BY week_start DESC LIMIT 1"
        ).fetchone()
    report = None
    if latest_report:
        candidate = json.loads(latest_report["report_json"])
        if candidate.get("version") == 2:
            report = candidate
            report["mode"] = latest_report["mode"]
            report["generated_at"] = latest_report["generated_at"]
    return {
        "stats": {key: int(stats[key] or 0) for key in stats.keys()},
        "categories": {row["category"]: row["count"] for row in category_rows},
        "source_stats": {key: int(source_stats[key] or 0) for key in source_stats.keys()},
        "latest": list_articles({"limit": ["12"]}),
        "weekly": report or build_local_report(save=False),
        "category_labels": CATEGORY_LABELS,
    }


def week_start_date() -> dt.date:
    today = dt.datetime.now().astimezone().date()
    return today - dt.timedelta(days=today.weekday())


def report_period_dates() -> tuple[dt.date, dt.date]:
    end = dt.datetime.now().astimezone().date()
    return end - dt.timedelta(days=6), end


def evidence_from_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": article["id"],
        "title": article["title"],
        "url": article["url"],
        "source": article["source_name"],
        "tier": article["source_tier"],
        "published_at": article["published_at"],
        "excerpt": clean_text(article.get("summary", ""), 260),
    }


def concise_signal(article: dict[str, Any]) -> str:
    excerpt = clean_text(article.get("summary", ""), 180)
    if excerpt:
        return f"{article['title']}: {excerpt}"
    return article["title"]


def build_category_insight(category: str, articles: list[dict[str, Any]]) -> dict[str, Any]:
    guidance = CATEGORY_GUIDANCE[category]
    category_articles = [item for item in articles if item["category"] == category]
    evidence = [evidence_from_article(item) for item in category_articles[:4]]
    if not category_articles:
        return {
            "category": category,
            "label": CATEGORY_LABELS[category],
            "status": "No new signal",
            "signal": "No sufficiently reliable new signal was detected this week",
            "summary": "The current source set produced no new high-relevance evidence in this area. This does not prove that the market was inactive; maintain baseline monitoring and review source coverage.",
            "watch_points": ["Confirm that official sources and priority expert feeds for this area are updating normally."],
            "impact": guidance["impact"],
            "responses": guidance["responses"][:2],
            "evidence": [],
        }

    official = [item for item in category_articles if item["source_tier"] == "T0"]
    research = [item for item in category_articles if item["source_tier"] == "T1"]
    sources = list(dict.fromkeys(item["source_name"] for item in category_articles))
    evidence_mix = []
    if official:
        evidence_mix.append(f"{len(official)} official update{'s' if len(official) != 1 else ''}")
    if research:
        evidence_mix.append(f"{len(research)} primary research item{'s' if len(research) != 1 else ''}")
    other_count = len(category_articles) - len(official) - len(research)
    if other_count:
        evidence_mix.append(f"{other_count} industry or expert analysis item{'s' if other_count != 1 else ''}")
    evidence_text = ", ".join(evidence_mix) or f"{len(category_articles)} intelligence items"
    top_titles = "; ".join(item["title"] for item in category_articles[:2])
    status = "Priority" if official else "Watch closely" if len(category_articles) >= 3 else "Monitor"
    responses = list(guidance["responses"])
    if official:
        responses.insert(0, "Confirm scope, publication date, and implementation conditions in the primary source.")
    if research:
        responses.append("Review the sample, methodology, and applicability before extending the finding to your own program.")
    return {
        "category": category,
        "label": CATEGORY_LABELS[category],
        "status": status,
        "signal": f"This week's signal centers on {top_titles}",
        "summary": (
            f"The past seven days produced {evidence_text}, led by {', '.join(sources[:3])}. "
            "Treat these as decision signals: verify applicability, then validate with first-party data or a contained test."
        ),
        "watch_points": [concise_signal(item) for item in category_articles[:3]],
        "impact": guidance["impact"],
        "responses": responses[:4],
        "evidence": evidence,
    }


def priority_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tier_score = {"T0": 4, "T1": 3, "T2": 2, "T3": 1, "T4": 0}
    ranked = sorted(
        articles,
        key=lambda item: (tier_score.get(item["source_tier"], 0), item.get("published_at") or ""),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for item in ranked:
        if item["category"] in seen_categories:
            continue
        selected.append(item)
        seen_categories.add(item["category"])
        if len(selected) == 3:
            break
    return selected


def build_local_report(save: bool = True) -> dict[str, Any]:
    articles = list_articles({"days": ["7"], "limit": ["120"]})
    insights = {category: build_category_insight(category, articles) for category in CATEGORY_LABELS}
    priorities = []
    for article in priority_articles(articles):
        guidance = CATEGORY_GUIDANCE[article["category"]]
        priorities.append(
            {
                "headline": article["title"],
                "category": article["category"],
                "why_it_matters": guidance["impact"],
                "response": guidance["responses"][0],
                "evidence": [evidence_from_article(article)],
            }
        )
    active = [insight for insight in insights.values() if insight["evidence"]]
    active_labels = ", ".join(item["label"] for item in active[:3])
    top_headlines = "; ".join(item["headline"] for item in priorities[:2])
    period_start, period_end = report_period_dates()
    if priorities:
        executive_summary = (
            f"Prioritize {active_labels or 'search ecosystem changes'} this week. Key signals include: {top_headlines}. "
            "Confirm the scope and evidence boundaries in primary sources, then validate with first-party data or contained experiments before treating industry commentary as a general rule."
        )
    else:
        executive_summary = "No sufficiently reliable new signal was captured this week. Review source health and maintain baseline monitoring across all six areas."
    report = {
        "version": 2,
        "title": f"SEO Intelligence Brief · {period_start.strftime('%b %d')}–{period_end.strftime('%b %d')}",
        "period": f"{period_start.isoformat()} — {period_end.isoformat()}",
        "mode": "local",
        "executive_summary": executive_summary,
        "priorities": priorities,
        "groups": {
            "core_capabilities": [insights[key] for key in CORE_CATEGORIES],
            "professional_directions": [insights[key] for key in SPECIALTY_CATEGORIES],
        },
        "actions": [item["response"] for item in priorities] or ["Review source health and add missing primary sources."],
        "evidence_count": sum(len(item["evidence"]) for item in insights.values()),
        "methodology": "Synthesized from the past seven days using source tier and topical relevance. T0 denotes official sources, T1 primary research, and T2/T3 expert or industry commentary.",
    }
    if save:
        save_report(report, "local")
    return report


def generate_weekly_report(use_ai: bool = False) -> dict[str, Any]:
    report = build_local_report(save=False)
    mode = "local"
    if use_ai:
        analysis = openai_weekly_analysis(report)
        report["executive_summary"] = analysis["executive_summary"]
        report["priorities"] = analysis["priorities"][:3]
        ai_insights = analysis["insights"]
        for group in report["groups"].values():
            for insight in group:
                generated = ai_insights[insight["category"]]
                insight.update(generated)
        mode = "ai"
        report["mode"] = mode
        report["actions"] = [item["response"] for item in report["priorities"]]
    save_report(report, mode)
    return report


def save_report(report: dict[str, Any], mode: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO weekly_reports (week_start, generated_at, mode, report_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(week_start) DO UPDATE SET
                generated_at=excluded.generated_at, mode=excluded.mode, report_json=excluded.report_json
            """,
            (week_start_date().isoformat(), utc_now(), mode, json.dumps(report, ensure_ascii=False)),
        )


def openai_weekly_analysis(report: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured; the local evidence-based brief remains available")
    model = os.environ.get("OPENAI_MODEL", "gpt-6-luna").strip()
    catalog: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for group in report["groups"].values():
        for insight in group:
            for evidence in insight["evidence"]:
                if evidence["url"] in seen_urls:
                    continue
                seen_urls.add(evidence["url"])
                catalog.append({"index": len(catalog), "category": insight["category"], **evidence})

    insight_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "signal": {"type": "string"},
            "summary": {"type": "string"},
            "watch_points": {"type": "array", "items": {"type": "string"}},
            "impact": {"type": "string"},
            "responses": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "signal", "summary", "watch_points", "impact", "responses"],
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "priorities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "category": {"type": "string", "enum": list(CATEGORY_LABELS)},
                        "why_it_matters": {"type": "string"},
                        "response": {"type": "string"},
                        "source_indices": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["headline", "category", "why_it_matters", "response", "source_indices"],
                    "additionalProperties": False,
                },
            },
            "insights": {
                "type": "object",
                "properties": {key: insight_schema for key in CATEGORY_LABELS},
                "required": list(CATEGORY_LABELS),
                "additionalProperties": False,
            },
        },
        "required": ["executive_summary", "priorities", "insights"],
        "additionalProperties": False,
    }
    prompt = (
        "Create a concise weekly intelligence brief for SEO professionals from the following evidence catalog. Focus on analysis and action, not article counts or item-by-item summaries. "
        "Cover core capabilities (content, technical, authority) and specialist areas (international, geo, sem). "
        "For every area, explain the core signal, watch points, likely impact, and recommended response. "
        "Use only facts from the catalog; distinguish T0 official sources, T1 primary research, and T2/T3 industry or expert commentary. Do not turn correlation into causation. "
        "Return at most three priorities. source_indices must refer to real catalog indices. If an area has no evidence, explicitly say 'No new signal' and do not invent one.\n\n"
        + json.dumps({"period": report["period"], "sources": catalog}, ensure_ascii=False)
    )
    body = json.dumps(
        {
            "model": model,
            "instructions": "You are a rigorous SEO intelligence analyst. Prioritize primary sources, state evidence boundaries, and provide specific, practical recommendations in clear professional English.",
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "seo_weekly_brief",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = clean_text(exc.read().decode("utf-8", errors="replace"), 500)
        raise ValueError(f"OpenAI API request failed ({exc.code}): {detail}") from exc
    chunks: list[str] = []
    for output in payload.get("output", []):
        if output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    output_text = "\n".join(chunks).strip()
    if not output_text:
        raise ValueError("The OpenAI API returned no usable text")
    try:
        analysis = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise ValueError("The structured weekly brief returned by the OpenAI API could not be parsed") from exc
    for priority in analysis.get("priorities", []):
        evidence = [catalog[index] for index in priority.pop("source_indices", []) if 0 <= index < len(catalog)]
        if not evidence:
            for group in report["groups"].values():
                match = next((item for item in group if item["category"] == priority["category"]), None)
                if match:
                    evidence = match["evidence"][:1]
                    break
        priority["evidence"] = [
            {key: value for key, value in item.items() if key not in {"index", "category"}}
            for item in evidence[:3]
        ]
    return analysis


def experts_data() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT e.*,
                   COUNT(a.id) AS article_count,
                   MAX(COALESCE(a.published_at, a.fetched_at)) AS latest_article_at,
                   MAX(CASE WHEN s.enabled=1 AND s.feed_url<>'' THEN 1 ELSE 0 END) AS feed_enabled,
                   COALESCE(MIN(s.tier), 'T3') AS tier
            FROM experts e
            LEFT JOIN sources s
              ON s.kind='expert' AND lower(trim(s.owner))=lower(trim(e.name))
            LEFT JOIN articles a ON a.source_id=s.id
            WHERE e.enabled=1
            GROUP BY e.id
            ORDER BY e.priority, e.name COLLATE NOCASE
            """
        ).fetchall()
    return [row_dict(row) for row in rows]  # type: ignore[misc]
