"""Check the static site in site/: files, wording rules, links, structure."""
from __future__ import annotations

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES = ["index.html", "start.html", "reports.html", "privacy.html",
         "kev.html", "sbom.html", "data-updates.html", "404.html"]
SITE_PREFIX = "/software-lifecycle/"
BASE_URL = "https://evemcgivern.github.io/software-lifecycle/"
INDEXABLE = [p for p in PAGES if p != "404.html"]

CLAIMS_LINE = "Runs locally with no network by default; not independently assessed."
KEV_LINE = ("The vendor and product appear in CISA KEV. "
            "This does not mean your version is affected.")
# Pages that mention CISA KEV only as a data source, not as a matching result.
KEV_LINE_EXEMPT = {"data-updates.html"}
BANNED_ELEMENTS = {"form", "input", "textarea"}


class Page(HTMLParser):
    """Collect what the checks need from one page."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.tags = []          # (tag, attrs dict)
        self.ids = set()
        self.text_parts = []
        self.visible_parts = []  # body text, no head, no script
        self.ld_blocks = []
        self._ld = None
        self.footer_parts = []
        self.title = ""
        self._stack = []
        self._in_title = False
        self.details = []       # one entry per <details>: has a summary
        self._details_stack = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "title":
            self._in_title = True
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._ld = []
        if tag == "details":
            self._details_stack.append(False)
        if tag == "summary" and self._details_stack:
            self._details_stack[-1] = True
        if tag not in ("meta", "link", "br", "hr", "img", "input"):
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "script" and self._ld is not None:
            self.ld_blocks.append("".join(self._ld))
            self._ld = None
        if tag == "title":
            self._in_title = False
        if tag == "details" and self._details_stack:
            self.details.append(self._details_stack.pop())
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        self.text_parts.append(data)
        if self._ld is not None:
            self._ld.append(data)
        elif "head" not in self._stack:
            self.visible_parts.append(data)
        if "footer" in self._stack:
            self.footer_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())

    @property
    def visible_text(self) -> str:
        joined = " ".join(" ".join(self.visible_parts).split())
        # Inline tags leave a space before punctuation; the reader sees none.
        return re.sub(r" ([.,;:?!])", r"\1", joined)

    def prop(self, name: str):
        for tag, a in self.tags:
            if tag == "meta" and a.get("property") == name:
                return a.get("content", "")
        return None

    def canonical(self):
        for tag, a in self.tags:
            if tag == "link" and a.get("rel") == "canonical":
                return a.get("href")
        return None

    def count(self, tag: str) -> int:
        return sum(1 for t, _ in self.tags if t == tag)

    def meta(self, name: str):
        for tag, a in self.tags:
            if tag == "meta" and a.get("name") == name:
                return a.get("content", "")
        return None


def load(name: str) -> Page:
    return Page((SITE / name).read_text(encoding="utf-8"))


def sentences(text: str):
    return re.split(r"(?<=[.!?])\s+", text)


def is_external(url: str) -> bool:
    return urlparse(url).scheme in ("http", "https") or url.startswith("//")


class SiteFiles(unittest.TestCase):
    def test_expected_files_exist(self):
        for name in PAGES + ["style.css", ".nojekyll"]:
            self.assertTrue((SITE / name).is_file(), name)

    def test_nojekyll_is_empty(self):
        self.assertEqual((SITE / ".nojekyll").read_bytes(), b"")


class SiteStructure(unittest.TestCase):
    def test_each_page_has_the_basics(self):
        titles = set()
        for name in PAGES:
            with self.subTest(page=name):
                page = load(name)
                self.assertEqual(page.count("h1"), 1)
                self.assertTrue(page.title.strip())
                self.assertNotIn(page.title.strip(), titles)
                titles.add(page.title.strip())
                self.assertTrue((page.meta("description") or "").strip())
                self.assertTrue((page.meta("viewport") or "").strip())
                self.assertIn(("html", {"lang": "en-GB"}),
                              [(t, {k: v for k, v in a.items() if k == "lang"})
                               for t, a in page.tags if t == "html"])
                self.assertTrue(any(
                    t == "link" and a.get("rel") == "canonical"
                    for t, a in page.tags))
                for landmark in ("header", "nav", "main", "footer"):
                    self.assertGreaterEqual(page.count(landmark), 1, landmark)
                self.assertTrue(any(
                    t == "a" and a.get("class") == "skip"
                    and a.get("href") == "#main" for t, a in page.tags))
                self.assertIn("main", page.ids)

    def test_claims_line_in_footer(self):
        for name in PAGES:
            with self.subTest(page=name):
                page = load(name)
                footer = " ".join(" ".join(page.footer_parts).split())
                self.assertIn(CLAIMS_LINE, footer)

    def test_kev_line_where_cisa_kev_is_named(self):
        for name in PAGES:
            if name in KEV_LINE_EXEMPT:
                continue
            with self.subTest(page=name):
                text = load(name).text
                if "CISA KEV" in text:
                    self.assertIn(KEV_LINE, text)

    def test_every_details_has_a_summary(self):
        seen = 0
        for name in PAGES:
            page = load(name)
            for has_summary in page.details:
                seen += 1
                self.assertTrue(has_summary, name)
        self.assertGreater(seen, 0)

    def test_no_form_elements(self):
        for name in PAGES:
            page = load(name)
            for tag, _ in page.tags:
                self.assertNotIn(tag, BANNED_ELEMENTS, name)


class SiteExternalRequests(unittest.TestCase):
    def test_no_scripts_except_ld_json(self):
        for name in PAGES:
            for tag, a in load(name).tags:
                if tag == "script":
                    self.assertEqual(a.get("type"), "application/ld+json", name)

    def test_only_anchors_point_off_site(self):
        for name in PAGES:
            for tag, a in load(name).tags:
                for attr in ("src", "href", "srcset", "poster", "action", "data"):
                    value = a.get(attr)
                    if not value or not is_external(value):
                        continue
                    allowed = tag == "a" and attr == "href"
                    allowed = allowed or (
                        tag == "link" and attr == "href"
                        and a.get("rel") == "canonical")
                    self.assertTrue(allowed, f"{name}: <{tag} {attr}={value}>")

    def test_stylesheets_are_local(self):
        for name in PAGES:
            sheets = [a for t, a in load(name).tags
                      if t == "link" and "stylesheet" in a.get("rel", "")]
            self.assertTrue(sheets, name)
            for a in sheets:
                self.assertFalse(is_external(a["href"]), name)

    def test_css_makes_no_requests(self):
        css = (SITE / "style.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"@import|url\(|https?://")


class SiteLinks(unittest.TestCase):
    def resolve(self, name: str, url: str) -> Path:
        path = urlparse(url).path
        if path.startswith(SITE_PREFIX):
            target = SITE / path[len(SITE_PREFIX):]
        elif path == "":
            target = SITE / name
        else:
            target = (SITE / name).parent / unquote(path)
        if target.is_dir():
            target = target / "index.html"
        return target

    def test_relative_links_and_fragments_resolve(self):
        pages = {name: load(name) for name in PAGES}
        for name, page in pages.items():
            for tag, a in page.tags:
                url = a.get("href") if tag in ("a", "link") else a.get("src")
                if not url or is_external(url) or url.startswith("mailto:"):
                    continue
                with self.subTest(page=name, url=url):
                    target = self.resolve(name, url)
                    self.assertTrue(target.is_file(), f"missing {target}")
                    fragment = urlparse(url).fragment
                    if fragment and target.suffix == ".html":
                        ids = pages[target.name].ids
                        self.assertIn(fragment, ids)


class SiteWording(unittest.TestCase):
    def test_banned_wording(self):
        for name in PAGES:
            text = load(name).text
            with self.subTest(page=name):
                for sentence in sentences(text):
                    if re.search(r"\bvulnerable\b", sentence, re.I):
                        self.assertIn("never", sentence.lower(), sentence)
                    if "BOD 22-01" in sentence:
                        self.assertIn("superseded", sentence, sentence)
                self.assertNotRegex(text, r"\bsigned\b")
                for phrase in ("certified", "enterprise-grade", "fully compliant"):
                    self.assertNotIn(phrase, text.lower())

    def test_no_invitation_to_upload_inventory(self):
        for name in PAGES:
            text = load(name).text.lower()
            for phrase in ("upload your", "paste your", "upload an inventory"):
                self.assertNotIn(phrase, text, name)

    def test_owner_wording_on_home_page(self):
        text = load("index.html").text
        self.assertIn("Who built this and why", text)
        self.assertIn("I'm Eve McGivern. I run IT application governance", text)
        self.assertIn("honest about what it can't match.", text)
        self.assertIn(CLAIMS_LINE, text)


def page_url(name: str) -> str:
    return BASE_URL if name == "index.html" else BASE_URL + name


class SiteSeo(unittest.TestCase):
    def test_titles_and_descriptions_fit_search_results(self):
        for name in PAGES:
            with self.subTest(page=name):
                page = load(name)
                self.assertLessEqual(len(page.title.strip()), 60)
                self.assertLessEqual(len(page.meta("description").strip()), 155)

    def test_canonical_matches_sitemap_url(self):
        for name in INDEXABLE:
            with self.subTest(page=name):
                self.assertEqual(load(name).canonical(), page_url(name))

    def test_robots_meta(self):
        for name in PAGES:
            with self.subTest(page=name):
                expected = "noindex" if name == "404.html" else "index,follow"
                self.assertEqual(load(name).meta("robots"), expected)

    def test_social_tags_on_indexable_pages(self):
        for name in INDEXABLE:
            with self.subTest(page=name):
                page = load(name)
                self.assertEqual(page.prop("og:title"), page.title.strip())
                self.assertEqual(page.prop("og:description"), page.meta("description"))
                self.assertEqual(page.prop("og:url"), page_url(name))
                self.assertEqual(page.prop("og:site_name"), "software-lifecycle")
                self.assertEqual(page.prop("og:locale"), "en_GB")
                self.assertEqual(page.meta("twitter:card"), "summary")
                self.assertEqual(page.meta("twitter:title"), page.title.strip())
                self.assertEqual(page.meta("twitter:description"),
                                 page.meta("description"))

    def test_no_image_references(self):
        for name in PAGES:
            page = load(name)
            self.assertIsNone(page.prop("og:image"), name)
            self.assertIsNone(page.meta("twitter:image"), name)
            self.assertNotIn("<img", (SITE / name).read_text(encoding="utf-8"))

    def test_json_ld_parses_and_has_context_and_type(self):
        for name in PAGES:
            for raw in load(name).ld_blocks:
                with self.subTest(page=name):
                    data = json.loads(raw)
                    self.assertEqual(data["@context"], "https://schema.org")
                    self.assertTrue(data["@type"])

    def ld_types(self, name: str) -> dict:
        return {json.loads(raw)["@type"]: json.loads(raw)
                for raw in load(name).ld_blocks}

    def test_json_ld_types_per_page(self):
        self.assertIn("SoftwareApplication", self.ld_types("index.html"))
        for name in ("kev.html", "sbom.html", "data-updates.html"):
            self.assertIn("FAQPage", self.ld_types(name), name)
        for name in INDEXABLE:
            if name != "index.html":
                self.assertIn("BreadcrumbList", self.ld_types(name), name)
        self.assertEqual(self.ld_types("404.html"), {})

    def test_software_application_facts(self):
        app = self.ld_types("index.html")["SoftwareApplication"]
        self.assertEqual(app["license"], "https://opensource.org/license/mit")
        self.assertIs(app["isAccessibleForFree"], True)
        self.assertEqual(app["offers"]["price"], "0")
        self.assertEqual(app["author"], {"@type": "Person", "name": "Eve McGivern"})
        for banned in ("aggregateRating", "review", "award"):
            self.assertNotIn(banned, app)

    def test_faq_text_appears_verbatim_on_the_page(self):
        for name in ("kev.html", "sbom.html", "data-updates.html"):
            page = load(name)
            visible = page.visible_text
            faq = self.ld_types(name)["FAQPage"]
            self.assertTrue(faq["mainEntity"], name)
            for item in faq["mainEntity"]:
                with self.subTest(page=name, question=item["name"]):
                    self.assertIn(item["name"], visible)
                    self.assertIn(item["acceptedAnswer"]["text"], visible)

    def test_breadcrumb_urls_resolve_to_real_pages(self):
        for name in INDEXABLE:
            for raw in load(name).ld_blocks:
                data = json.loads(raw)
                if data["@type"] != "BreadcrumbList":
                    continue
                for entry in data["itemListElement"]:
                    self.assertIn(entry["item"], self.sitemap_urls(), name)

    def sitemap_urls(self):
        text = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        return re.findall(r"<loc>([^<]+)</loc>", text)

    def test_sitemap_lists_exactly_the_indexable_pages(self):
        urls = self.sitemap_urls()
        self.assertEqual(sorted(urls), sorted(page_url(n) for n in INDEXABLE))
        self.assertEqual(len(urls), len(set(urls)))
        for url in urls:
            self.assertTrue(url.startswith(BASE_URL), url)
            rel = url[len(BASE_URL):] or "index.html"
            self.assertTrue((SITE / rel).is_file(), url)
        text = (SITE / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("priority", text)
        self.assertNotIn("changefreq", text)

    def test_robots_and_llms_files_live_at_the_host_root(self):
        # Crawlers read robots.txt and llms.txt only at the top of the host
        # (https://evemcgivern.github.io/), which is the user-site
        # repository, not this project page. Copies here would be ignored.
        for name in ("robots.txt", "llms.txt"):
            self.assertFalse((SITE / name).exists(), name)

    def test_seo_files_follow_wording_rules(self):
        for name in ("sitemap.xml",):
            text = (SITE / name).read_text(encoding="utf-8")
            for sentence in sentences(text):
                if re.search(r"\bvulnerable\b", sentence, re.I):
                    self.assertIn("never", sentence.lower(), sentence)
            self.assertNotRegex(text, r"\bsigned\b")
            self.assertNotRegex(text.lower(), r"certified|enterprise-grade|fully compliant|\bbest\b|\bleading\b")
            if "BOD 22-01" in text:
                self.fail(name)

    def test_explainers_link_to_each_other_and_start(self):
        explainers = ["kev.html", "sbom.html", "data-updates.html"]
        for name in explainers:
            hrefs = {a.get("href") for t, a in load(name).tags if t == "a"}
            with self.subTest(page=name):
                self.assertIn("start.html", hrefs)
                for other in explainers:
                    if other != name:
                        self.assertIn(other, hrefs)

    def test_no_vague_anchor_text(self):
        for name in PAGES:
            self.assertNotRegex(load(name).text.lower(), r"click here")


class SiteAccessibility(unittest.TestCase):
    """Source-level checks. They do not replace browser or screen-reader testing."""

    def test_no_style_attributes(self):
        for name in PAGES:
            with self.subTest(page=name):
                for tag, a in load(name).tags:
                    self.assertNotIn("style", a, f"{name}: <{tag}> has a style attribute")

    def test_heading_levels_do_not_skip(self):
        for name in PAGES:
            with self.subTest(page=name):
                levels = [int(t[1]) for t, _ in load(name).tags
                          if re.fullmatch(r"h[1-6]", t)]
                self.assertEqual(levels[0], 1)
                for prev, cur in zip(levels, levels[1:]):
                    self.assertLessEqual(cur, prev + 1, levels)

    def test_skip_link_is_first_link_in_body(self):
        for name in PAGES:
            with self.subTest(page=name):
                body = False
                for tag, a in load(name).tags:
                    if tag == "body":
                        body = True
                    if body and tag == "a":
                        self.assertEqual(a.get("class"), "skip")
                        break

    def test_main_is_focus_target_for_skip_link(self):
        for name in PAGES:
            with self.subTest(page=name):
                mains = [a for t, a in load(name).tags if t == "main"]
                self.assertEqual(len(mains), 1)
                self.assertEqual(mains[0].get("id"), "main")
                self.assertEqual(mains[0].get("tabindex"), "-1")

    def test_nav_marks_current_page_once_and_correctly(self):
        for name in PAGES:
            with self.subTest(page=name):
                current = [a for t, a in load(name).tags
                           if t == "a" and a.get("aria-current")]
                for a in current:
                    self.assertEqual(a["aria-current"], "page")
                    self.assertEqual(a["href"], name)
                self.assertLessEqual(len(current), 1)
                if name in ("index.html", "start.html", "reports.html",
                            "privacy.html", "data-updates.html"):
                    self.assertEqual(len(current), 1)

    def test_nav_landmarks_have_distinct_names(self):
        for name in PAGES:
            with self.subTest(page=name):
                labels = [a.get("aria-label") for t, a in load(name).tags if t == "nav"]
                self.assertTrue(all(labels), labels)
                self.assertEqual(len(labels), len(set(labels)))

    def test_links_do_not_open_new_windows(self):
        for name in PAGES:
            for tag, a in load(name).tags:
                self.assertNotIn("target", a, name)

    def test_tables_have_caption_and_scoped_headers(self):
        for name in PAGES:
            source = (SITE / name).read_text(encoding="utf-8")
            self.assertEqual(source.count("<table"), source.count("<caption"), name)
            for m in re.finditer(r"<th(?=[\s>])([^>]*)>", source):
                self.assertIn("scope=", m.group(1), f"{name}: {m.group(0)}")

    def test_scrollable_regions_are_focusable_and_named(self):
        for name in PAGES:
            source = (SITE / name).read_text(encoding="utf-8")
            for m in re.finditer(r'<(pre|div class="table-scroll")([^>]*)>', source):
                attrs = m.group(2)
                with self.subTest(page=name, el=m.group(1)):
                    self.assertIn('tabindex="0"', attrs)
                    self.assertIn('role="region"', attrs)
                    self.assertIn("aria-label=", attrs)

    def test_css_has_focus_summary_motion_and_forced_colors(self):
        css = (SITE / "style.css").read_text(encoding="utf-8")
        self.assertIn(":focus-visible", css)
        self.assertNotRegex(css, r"(?m)^:focus\s*\{")
        self.assertIn("summary::before", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("forced-colors", css)
        self.assertIn("@media print", css)
        for rule in re.findall(r"([^{}]+)\{[^{}]*outline\s*:\s*(?:none|0)\b", css):
            self.assertEqual(rule.strip(), "main:focus", rule)

    def test_json_ld_is_inert_script_in_head(self):
        for name in PAGES:
            source = (SITE / name).read_text(encoding="utf-8")
            head = source.split("</head>")[0]
            body = source.split("</head>")[1]
            self.assertNotIn("ld+json", body, name)
            self.assertEqual(head.count("ld+json"), source.count("ld+json"), name)

    def test_404_uses_root_relative_site_paths(self):
        for tag, a in load("404.html").tags:
            url = a.get("href") if tag in ("a", "link") else None
            if url and not is_external(url) and not url.startswith("#") \
                    and a.get("rel") != "canonical":
                self.assertTrue(url.startswith(SITE_PREFIX), url)


if __name__ == "__main__":
    unittest.main()
