#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_harvester.py -- Canonical test vectors for harvester.py

Covers:
  - Round-trip integrity (harvest -> sidecar -> feed)
  - Fragment extraction with strip rules
  - Plain text rendering from HTML fragment
  - Standalone HTML wrapping
  - Metadata sidecar serialise/parse
  - CRLF normalisation
  - Non-ASCII content (UTF-8 throughout)
  - lxml / stdlib parity for well-formed HTML
  - Strip rule semantics (tag, tag.class, nested elements)
  - Empty-container, missing-h1, missing-meta edge cases
  - Slug derivation (index.html convention vs flat files)
  - Config-file parsing (RawConfigParser idioms)
  - Feed channel metadata round-trip
  - Cron-friendly atomic writes (no partial files on interruption)

Run with:
    python test_harvester.py
    python -m pytest test_harvester.py -v

Compatibility: Python 2.7+ / 3.x
"""

from __future__ import print_function, unicode_literals

import io
import os
import shutil
import sys
import tempfile
import unittest


# ---------------------------------------------------------------------------
# Load harvester without triggering __main__
# ---------------------------------------------------------------------------

def _load_harvester():
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "harvester.py")
    if not os.path.exists(target):
        raise RuntimeError("harvester.py not found next to test file: " + target)

    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("harvester", target)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except (ImportError, AttributeError):
        import imp
        return imp.load_source("harvester", target)

_mod = _load_harvester()


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

# A representative Field Note structure with multiple strip targets,
# manicule asides (which must NOT be stripped), and a canonical-archive
# footer (which MUST be stripped).
SAMPLE_FN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Field Note #99 \u2237 Test Document</title>
<meta name="description" content="A test document for the harvester.">
<meta property="article:published_time" content="2026-04-27">
<meta property="og:url" content="https://example.com/fieldwork/field-note-99/">
<link rel="stylesheet" href="/assets/css/main.css">
</head>
<body>
<header>This is the site header, should NOT appear in fragment.</header>
<main>
<article class="essay">
<h1>Field Note #99 \u2237 Test Document</h1>
<div class="meta">
<span>Published: 2026-04-27</span>
</div>
<p>This is the first paragraph of the body.</p>
<p>This is the second paragraph, with an <em>emphasis</em>.</p>
<p class="note">\u261e <em>This is a manicule editorial aside. It MUST survive harvesting.</em></p>
<p>Body continues here.</p>
<hr>
<p class="archive-note">If you received this via email, the canonical archive lives at example.com.</p>
</article>
</main>
<footer>Site footer, should NOT appear in fragment.</footer>
</body>
</html>
"""

# Strip rules for the sample: meta div and archive-note footer.
# Manicule p.note is preserved.
SAMPLE_STRIP_RULES = [
    ("h1", None),
    ("div", "meta"),
    ("p", "archive-note"),
]


# ---------------------------------------------------------------------------
# Fragment extraction tests
# ---------------------------------------------------------------------------

class TestFragmentExtraction(unittest.TestCase):

    def test_basic_extraction(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertIn("first paragraph", fragment)
        self.assertIn("second paragraph", fragment)

    def test_h1_stripped(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertNotIn("<h1>", fragment)

    def test_meta_div_stripped(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertNotIn("Published: 2026-04-27", fragment)

    def test_archive_note_stripped(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertNotIn("canonical archive", fragment)

    def test_manicule_preserved(self):
        """Critical: manicule asides use class='note', not class='archive-note'."""
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertIn("manicule editorial aside", fragment)
        self.assertIn("MUST survive", fragment)

    def test_site_chrome_excluded(self):
        """Header/footer outside <article class='essay'> must not appear."""
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertNotIn("Site footer", fragment)
        self.assertNotIn("site header", fragment)

    def test_inline_emphasis_preserved(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        self.assertIn("<em>emphasis</em>", fragment)

    def test_empty_strip_rules(self):
        fragment = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", [], prefer_lxml=False)
        self.assertIn("<h1>Field Note", fragment)
        self.assertIn("Published:", fragment)

    def test_missing_container(self):
        html = "<html><body><p>no article here</p></body></html>"
        fragment = _mod.extract_fragment(
            html, "article", "essay", [], prefer_lxml=False)
        self.assertEqual(fragment, "")


class TestStripRuleSemantics(unittest.TestCase):

    def test_strip_by_tag_only(self):
        html = ("<article class='essay'>"
                "<p>keep</p><script>strip me</script><p>also keep</p>"
                "</article>")
        fragment = _mod.extract_fragment(
            html, "article", "essay", [("script", None)], prefer_lxml=False)
        self.assertNotIn("strip me", fragment)
        self.assertIn("keep", fragment)

    def test_strip_by_tag_and_class(self):
        html = ("<article class='essay'>"
                "<p class='keep'>keep</p>"
                "<p class='go'>strip</p>"
                "</article>")
        fragment = _mod.extract_fragment(
            html, "article", "essay", [("p", "go")], prefer_lxml=False)
        self.assertIn("keep", fragment)
        self.assertNotIn("strip", fragment)

    def test_nested_strip_target(self):
        html = ("<article class='essay'>"
                "<div class='strip'><p>nested content</p></div>"
                "<p>kept content</p>"
                "</article>")
        fragment = _mod.extract_fragment(
            html, "article", "essay", [("div", "strip")], prefer_lxml=False)
        self.assertNotIn("nested content", fragment)
        self.assertIn("kept content", fragment)


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

class TestMetadataExtraction(unittest.TestCase):

    def test_extract_h1(self):
        md = _mod.extract_metadata(SAMPLE_FN_HTML, "article", "essay")
        self.assertEqual(md["h1"], "Field Note #99 \u2237 Test Document")

    def test_extract_title(self):
        md = _mod.extract_metadata(SAMPLE_FN_HTML, "article", "essay")
        self.assertIn("Test Document", md["title"])

    def test_extract_description(self):
        md = _mod.extract_metadata(SAMPLE_FN_HTML, "article", "essay")
        self.assertEqual(md["meta"]["description"],
                         "A test document for the harvester.")

    def test_extract_published(self):
        md = _mod.extract_metadata(SAMPLE_FN_HTML, "article", "essay")
        self.assertEqual(md["meta"]["article:published_time"], "2026-04-27")

    def test_extract_canonical_url(self):
        md = _mod.extract_metadata(SAMPLE_FN_HTML, "article", "essay")
        self.assertEqual(
            md["meta"]["og:url"],
            "https://example.com/fieldwork/field-note-99/")


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------

class TestTextRendering(unittest.TestCase):

    def test_paragraphs_separated(self):
        text = _mod.render_text("<p>first</p><p>second</p>")
        self.assertIn("first", text)
        self.assertIn("second", text)
        self.assertIn("\n\n", text)

    def test_inline_em_preserved_as_text(self):
        text = _mod.render_text("<p>this is <em>important</em> text</p>")
        self.assertIn("important", text)
        self.assertNotIn("<em>", text)

    def test_whitespace_collapsed(self):
        text = _mod.render_text("<p>multiple   spaces</p>")
        self.assertNotIn("   ", text)

    def test_no_more_than_two_consecutive_newlines(self):
        text = _mod.render_text("<p>a</p><p>b</p><p>c</p>")
        self.assertNotIn("\n\n\n", text)

    def test_html_entity_decoded(self):
        text = _mod.render_text("<p>caf&eacute; au lait</p>")
        self.assertIn("caf\u00e9", text)

    def test_numeric_entity_decoded(self):
        text = _mod.render_text("<p>fan&#231;y</p>")
        self.assertIn("fan\u00e7y", text)

    def test_skip_script_tags(self):
        text = _mod.render_text(
            "<p>visible</p><script>alert('hi')</script><p>also visible</p>")
        self.assertNotIn("alert", text)
        self.assertIn("visible", text)


# ---------------------------------------------------------------------------
# Standalone HTML wrapper
# ---------------------------------------------------------------------------

class TestStandaloneWrapper(unittest.TestCase):

    def test_doctype_present(self):
        html = _mod.render_standalone(
            "Title", "<p>body</p>",
            "https://example.com/", "https://example.com/css")
        self.assertTrue(html.startswith("<!doctype html>"))

    def test_minimal_css_embedded(self):
        html = _mod.render_standalone(
            "Title", "<p>body</p>",
            "https://example.com/", "https://example.com/css")
        self.assertIn("<style>", html)
        self.assertIn("font-family", html)

    def test_canonical_link_present(self):
        html = _mod.render_standalone(
            "Title", "<p>body</p>",
            "https://example.com/path/", "https://example.com/css")
        self.assertIn(
            'rel="canonical" href="https://example.com/path/"', html)

    def test_canonical_css_link(self):
        html = _mod.render_standalone(
            "Title", "<p>body</p>",
            "https://example.com/", "https://example.com/main.css")
        self.assertIn(
            'rel="stylesheet" href="https://example.com/main.css"', html)

    def test_title_xml_escaped(self):
        html = _mod.render_standalone(
            "Title with <special> & \"chars\"", "<p>body</p>",
            "https://example.com/", "https://example.com/css")
        self.assertNotIn("<special>", html)
        self.assertIn("&lt;special&gt;", html)


# ---------------------------------------------------------------------------
# Metadata sidecar
# ---------------------------------------------------------------------------

class TestMetaSidecar(unittest.TestCase):

    def test_render_basic(self):
        meta = {"slug": "test", "title": "Hello", "published": "2026-04-27"}
        text = _mod.render_meta_sidecar(meta)
        self.assertIn("slug=test", text)
        self.assertIn("title=Hello", text)
        self.assertIn("published=2026-04-27", text)

    def test_round_trip(self):
        meta = {
            "slug": "fn-99",
            "title": "Field Note #99 \u2237 Test",
            "description": "A short description.",
            "published": "2026-04-27",
        }
        text = _mod.render_meta_sidecar(meta)
        parsed = _mod.parse_meta_sidecar(text)
        for key in meta:
            self.assertEqual(parsed[key], meta[key])

    def test_empty_values_omitted(self):
        meta = {"slug": "test", "title": "", "description": None}
        text = _mod.render_meta_sidecar(meta)
        self.assertIn("slug=test", text)
        self.assertNotIn("title=", text)
        self.assertNotIn("description=", text)

    def test_unicode_in_value(self):
        meta = {"title": "Field Note \u2237 \u00e9\u00e8"}
        text = _mod.render_meta_sidecar(meta)
        parsed = _mod.parse_meta_sidecar(text)
        self.assertEqual(parsed["title"], meta["title"])

    def test_multiline_value_folded(self):
        meta = {"description": "line one\nline two"}
        text = _mod.render_meta_sidecar(meta)
        parsed = _mod.parse_meta_sidecar(text)
        self.assertEqual(parsed["description"], "line one\nline two")


# ---------------------------------------------------------------------------
# CRLF and normalisation
# ---------------------------------------------------------------------------

class TestNormalisation(unittest.TestCase):

    def test_crlf_normalised(self):
        self.assertEqual(_mod._normalise("a\r\nb"), "a\nb")

    def test_bare_cr_normalised(self):
        self.assertEqual(_mod._normalise("a\rb"), "a\nb")

    def test_lf_unchanged(self):
        self.assertEqual(_mod._normalise("a\nb"), "a\nb")


# ---------------------------------------------------------------------------
# Slug derivation
# ---------------------------------------------------------------------------

class TestSlugDerivation(unittest.TestCase):

    def test_index_html_uses_parent_dir(self):
        slug = _mod.derive_slug(
            "/site/fieldwork/field-note-10/index.html",
            "/site/fieldwork")
        self.assertEqual(slug, "field-note-10")

    def test_flat_html_uses_basename(self):
        slug = _mod.derive_slug(
            "/site/posts/my-post.html",
            "/site/posts")
        self.assertEqual(slug, "my-post")

    def test_index_at_root(self):
        slug = _mod.derive_slug(
            "/site/index.html",
            "/site")
        self.assertEqual(slug, "index")


# ---------------------------------------------------------------------------
# End-to-end: walk, harvest, feed
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="harvester-test-")
        self.input_dir = os.path.join(self.tmpdir, "fieldwork")
        self.output_dir = os.path.join(self.tmpdir, "harvested")
        os.makedirs(os.path.join(self.input_dir, "field-note-99"))
        with io.open(
                os.path.join(self.input_dir, "field-note-99", "index.html"),
                "w", encoding="utf-8") as f:
            f.write(SAMPLE_FN_HTML)

        self.cfg_path = os.path.join(self.tmpdir, "harvester.cfg")
        with io.open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(
                "[walk]\n"
                "pattern = */index.html\n"
                "\n"
                "[extractor]\n"
                "container_tag = article\n"
                "container_class = essay\n"
                "strip = h1, div.meta, p.archive-note\n"
                "\n"
                "[output]\n"
                "canonical_base = https://example.com/fieldwork\n"
                "canonical_css = https://example.com/main.css\n"
                "\n"
                "[feed]\n"
                "title = Test Feed\n"
                "description = Test description.\n"
                "site_url = https://example.com\n"
                "link = https://example.com/fieldwork/\n"
                "feed_url = https://example.com/feed.xml\n"
                "language = en\n"
                "author = test@example.com\n"
            )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _harvest(self):
        config = _mod.Config(self.cfg_path)
        html_path = os.path.join(self.input_dir, "field-note-99", "index.html")
        return _mod.harvest_one(
            html_path, "field-note-99", config, self.output_dir)

    def test_artefacts_written(self):
        self._harvest()
        for ext in (".txt", ".fragment", ".standalone", ".meta"):
            path = os.path.join(self.output_dir, "field-note-99" + ext)
            self.assertTrue(os.path.exists(path),
                            "missing output: " + path)

    def test_fragment_preserves_manicule(self):
        self._harvest()
        with io.open(os.path.join(self.output_dir, "field-note-99.fragment"),
                     "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("manicule editorial aside", content)
        self.assertNotIn("canonical archive", content)

    def test_meta_sidecar_round_trip(self):
        self._harvest()
        with io.open(os.path.join(self.output_dir, "field-note-99.meta"),
                     "r", encoding="utf-8") as f:
            text = f.read()
        meta = _mod.parse_meta_sidecar(text)
        self.assertEqual(meta["slug"], "field-note-99")
        self.assertIn("Test Document", meta["title"])
        self.assertEqual(meta["published"], "2026-04-27")

    def test_text_is_archivist_compatible(self):
        """Plain text output should be ready for archivist stamping."""
        self._harvest()
        with io.open(os.path.join(self.output_dir, "field-note-99.txt"),
                     "r", encoding="utf-8") as f:
            text = f.read()
        # No HTML tags should remain.
        self.assertNotIn("<", text)
        self.assertNotIn(">", text)
        # Content should be present.
        self.assertIn("first paragraph", text)
        # Manicule should be in plain text too.
        self.assertIn("manicule editorial aside", text)

    def test_feed_aggregates_harvested(self):
        self._harvest()
        config = _mod.Config(self.cfg_path)
        rss = _mod.build_feed(self.output_dir, config)

        self.assertIn("<?xml version=\"1.0\"", rss)
        self.assertIn("<rss version=\"2.0\"", rss)
        self.assertIn("Test Document", rss)
        self.assertIn("manicule editorial aside", rss)
        self.assertIn("Mon, 27 Apr 2026", rss)

    def test_atomic_write_no_partial_files(self):
        """After a successful harvest no .tmp files should remain."""
        self._harvest()
        for fn in os.listdir(self.output_dir):
            self.assertFalse(fn.endswith(".tmp"),
                             "leftover .tmp file: " + fn)


# ---------------------------------------------------------------------------
# lxml / stdlib parity (only runs if lxml is installed)
# ---------------------------------------------------------------------------

class TestBackendParity(unittest.TestCase):

    def setUp(self):
        if not _mod.HAVE_LXML:
            self.skipTest("lxml not installed")

    def test_well_formed_html_yields_same_text(self):
        """For well-formed HTML, both backends should produce equivalent text."""
        stdlib = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=False)
        lxml = _mod.extract_fragment(
            SAMPLE_FN_HTML, "article", "essay", SAMPLE_STRIP_RULES,
            prefer_lxml=True)
        # Render both to plain text and compare. Direct fragment comparison
        # is unreliable because lxml and HTMLParser format attributes and
        # whitespace differently.
        stdlib_text = _mod.render_text(stdlib)
        lxml_text = _mod.render_text(lxml)
        self.assertEqual(stdlib_text, lxml_text)


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="harvester-cfg-")
        self.cfg_path = os.path.join(self.tmpdir, "test.cfg")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_config(self, text):
        with io.open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_loaded_flag(self):
        self._write_config("[extractor]\ncontainer_tag = article\n")
        config = _mod.Config(self.cfg_path)
        self.assertTrue(config.loaded)

    def test_missing_config(self):
        config = _mod.Config(os.path.join(self.tmpdir, "nope.cfg"))
        self.assertFalse(config.loaded)

    def test_get_with_default(self):
        self._write_config("[extractor]\ncontainer_tag = article\n")
        config = _mod.Config(self.cfg_path)
        self.assertEqual(config.get("extractor", "container_tag"), "article")
        self.assertEqual(config.get("extractor", "missing", "fallback"),
                         "fallback")

    def test_strip_rules_parsed(self):
        self._write_config(
            "[extractor]\n"
            "strip = h1, div.meta, p.archive-note, script\n"
        )
        config = _mod.Config(self.cfg_path)
        rules = config.get_strip_rules()
        self.assertIn(("h1", None), rules)
        self.assertIn(("div", "meta"), rules)
        self.assertIn(("p", "archive-note"), rules)
        self.assertIn(("script", None), rules)


# ---------------------------------------------------------------------------
# CDATA escape (regression: ]]> sequence in fragment terminates CDATA)
# ---------------------------------------------------------------------------

class TestCDATAEscape(unittest.TestCase):

    def test_plain_text_unchanged(self):
        self.assertEqual(_mod._cdata("hello world"), "hello world")

    def test_empty_string(self):
        self.assertEqual(_mod._cdata(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(_mod._cdata(None), "")

    def test_cdata_terminator_split(self):
        """The literal sequence ]]> must not appear in escaped output."""
        escaped = _mod._cdata("evil ]]> here")
        self.assertNotIn("]]>", escaped.replace("]]]]><![CDATA[>", ""))

    def test_multiple_terminators(self):
        escaped = _mod._cdata("a ]]> b ]]> c")
        # Two splits expected; "]]>" appears only as part of the split pattern
        self.assertEqual(escaped.count("]]]]><![CDATA[>"), 2)

    def test_feed_with_cdata_terminator_in_fragment(self):
        """End-to-end: a fragment containing ]]> must produce valid RSS."""
        # Build a minimal config and harvested directory in memory.
        tmpdir = tempfile.mkdtemp(prefix="harvester-cdata-test-")
        try:
            with io.open(os.path.join(tmpdir, "evil.fragment"),
                         "w", encoding="utf-8") as f:
                f.write("<p>Nested CDATA: ]]> would break things</p>")
            with io.open(os.path.join(tmpdir, "evil.meta"),
                         "w", encoding="utf-8") as f:
                f.write(
                    "slug=evil\n"
                    "title=Test ]]> Title\n"
                    "description=Description ]]> with terminator\n"
                    "published=2026-04-27\n"
                    "canonical_url=https://example.com/evil/\n"
                )

            cfg_path = os.path.join(tmpdir, "harvester.cfg")
            with io.open(cfg_path, "w", encoding="utf-8") as f:
                f.write(
                    "[feed]\n"
                    "title = Test\n"
                    "site_url = https://example.com\n"
                    "link = https://example.com/\n"
                    "feed_url = https://example.com/feed.xml\n"
                )
            config = _mod.Config(cfg_path)
            rss = _mod.build_feed(tmpdir, config)

            # Direct assertions on the contract:
            #   1. The escape pattern is present in the output.
            #   2. The visible content survives intact.
            self.assertIn("]]]]><![CDATA[>", rss)
            self.assertIn("Nested CDATA:", rss)
            self.assertIn("would break things", rss)
            self.assertIn("Description", rss)
            self.assertIn("with terminator", rss)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# RFC 822 date formatting
# ---------------------------------------------------------------------------

class TestRFC822(unittest.TestCase):

    def test_iso_date_only(self):
        result = _mod._rfc822("2026-04-27")
        self.assertIn("27 Apr 2026", result)
        self.assertIn("+0000", result)

    def test_iso_full(self):
        result = _mod._rfc822("2026-04-27T12:00:00Z")
        self.assertIn("27 Apr 2026", result)

    def test_empty_string(self):
        self.assertEqual(_mod._rfc822(""), "")

    def test_invalid_date(self):
        self.assertEqual(_mod._rfc822("not a date"), "")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
