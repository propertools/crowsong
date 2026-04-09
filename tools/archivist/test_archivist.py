#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_archivist.py -- Canonical test vectors for archivist.py

Covers every case surfaced across the three-pass code review:
  - Round-trip integrity (stamp -> parse -> verify)
  - Line-count correctness (empty, single-line, multi-line)
  - CRLF normalisation
  - Non-ASCII metadata (the Python 2 UnicodeEncodeError regression)
  - Header-only stamped file (no body section)
  - Unstamped passthrough
  - Comment-prefixed non-stamped file (false-positive detection regression)
  - Tampered body detection
  - Truncated/damaged header (no SHA256 field)
  - Legacy colon-separator field parsing
  - Malformed colon line not over-interpreted
  - Empty body stamps and verifies cleanly
  - Multiple trailing newlines collapse correctly
  - No-final-newline input gains exactly one newline

Run with:
    python test_archivist.py
    python -m pytest test_archivist.py -v

Compatibility: Python 2.7+ / 3.x
"""

from __future__ import print_function, unicode_literals

import importlib
import os
import sys
import unittest

# ---------------------------------------------------------------------------
# Load archivist without triggering __main__
# ---------------------------------------------------------------------------

def _load_archivist():
    here   = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "archivist.py")
    if not os.path.exists(target):
        raise RuntimeError("archivist.py not found next to test file: " + target)

    # Works on both Python 2.7 (imp) and 3.x (importlib.util)
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("archivist", target)
        mod  = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except AttributeError:
        # Python 2 fallback
        import imp
        return imp.load_source("archivist", target)

_mod = _load_archivist()

stamp       = _mod.stamp
parse       = _mod.parse
_sha256     = _mod._sha256
_normalise  = _mod._normalise
_line_count = _mod._line_count
HEADER_MARKER = _mod.HEADER_MARKER
SHA256_FIELD  = _mod.SHA256_FIELD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stamp_parse(body, **meta_kwargs):
    """Convenience: stamp body with given meta, immediately parse result."""
    meta = dict({"no_date": True}, **meta_kwargs)
    return parse(stamp(body, meta))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestRoundTrip(unittest.TestCase):
    """stamp -> parse -> verify produces consistent results."""

    def test_basic_ascii(self):
        p = _stamp_parse("Hello world")
        self.assertTrue(p["is_stamped"])
        self.assertTrue(p["sha256_ok"])
        self.assertEqual(p["body"], "Hello world")

    def test_multiline_body(self):
        body = "line one\nline two\nline three"
        p = _stamp_parse(body)
        self.assertTrue(p["sha256_ok"])
        self.assertEqual(p["body"], body)
        self.assertEqual(p["line_count"], 3)

    def test_metadata_round_trip(self):
        p = _stamp_parse(
            "body text",
            title="My Document",
            author="T. Darley",
            lang="en",
            source="propertools.be",
        )
        self.assertEqual(p["fields"]["TITLE"],  "My Document")
        self.assertEqual(p["fields"]["AUTHOR"], "T. Darley")
        self.assertEqual(p["fields"]["LANG"],   "en")
        self.assertEqual(p["fields"]["SOURCE"], "propertools.be")

    def test_tags_and_tlp(self):
        p = _stamp_parse("body", tags="crowsong,fds", tlp="CLEAR")
        self.assertEqual(p["fields"]["TAGS"], "crowsong,fds")
        self.assertEqual(p["fields"]["TLP"],  "CLEAR")


class TestNonAsciiMetadata(unittest.TestCase):
    """
    Regression: Python 2 str(unicode_value) raises UnicodeEncodeError for
    non-ASCII metadata. Fixed by _to_text() helper.
    """

    def test_non_ascii_title(self):
        p = _stamp_parse("body", title="Ünïcödé títlé")
        self.assertTrue(p["sha256_ok"])
        self.assertEqual(p["fields"]["TITLE"], "Ünïcödé títlé")

    def test_arabic_title(self):
        p = _stamp_parse("body", title="\u0625\u0639\u0644\u0627\u0646")
        self.assertTrue(p["sha256_ok"])
        self.assertIn("TITLE", p["fields"])

    def test_cjk_author(self):
        p = _stamp_parse("body", author="\u4f5c\u8005")
        self.assertTrue(p["sha256_ok"])

    def test_non_ascii_note(self):
        p = _stamp_parse("body", note="Ré: café ☕")
        self.assertTrue(p["sha256_ok"])


class TestLineCounts(unittest.TestCase):
    """
    Regression: body.count("\\n") returned 0 for a one-line body.
    Fixed by _line_count() which returns count("\\n") + 1 for non-empty text.
    """

    def test_empty_body(self):
        self.assertEqual(_line_count(""), 0)

    def test_single_line_no_newline(self):
        self.assertEqual(_line_count("one line"), 1)

    def test_single_line_with_newline(self):
        self.assertEqual(_line_count("one line\n"), 2)

    def test_two_lines(self):
        self.assertEqual(_line_count("a\nb"), 2)

    def test_three_lines(self):
        self.assertEqual(_line_count("a\nb\nc"), 3)

    def test_stamped_single_line(self):
        p = _stamp_parse("one line")
        self.assertEqual(p["line_count"], 1)
        self.assertEqual(int(p["fields"]["LINES"]), 1)

    def test_stamped_empty_body(self):
        p = _stamp_parse("")
        self.assertEqual(p["line_count"], 0)
        self.assertEqual(int(p["fields"]["LINES"]), 0)

    def test_stamped_three_lines(self):
        p = _stamp_parse("a\nb\nc")
        self.assertEqual(p["line_count"], 3)


class TestCRLFNormalisation(unittest.TestCase):
    """CRLF input must produce the same hash as LF input."""

    def test_crlf_body_normalised(self):
        lf_body   = "line one\nline two"
        crlf_body = "line one\r\nline two\r\n"
        p_lf   = _stamp_parse(lf_body)
        p_crlf = _stamp_parse(crlf_body)
        # Both should hash to the same value
        self.assertEqual(p_lf["sha256_actual"], p_crlf["sha256_actual"])

    def test_crlf_not_in_parsed_body(self):
        p = _stamp_parse("line one\r\nline two\r\n")
        self.assertNotIn("\r", p["body"])

    def test_bare_cr_normalised(self):
        p = _stamp_parse("line one\rline two")
        self.assertNotIn("\r", p["body"])

    def test_verify_after_crlf(self):
        p = _stamp_parse("a\r\nb\r\nc\r\n")
        self.assertTrue(p["sha256_ok"])


class TestTrailingNewlines(unittest.TestCase):
    """
    Multiple trailing newlines collapse to one; no-final-newline gains one.
    """

    def test_multiple_trailing_newlines_collapse(self):
        p = _stamp_parse("body\n\n\n")
        self.assertEqual(p["body"], "body")
        self.assertTrue(p["sha256_ok"])

    def test_no_final_newline_gains_one(self):
        # stamp always ends with \n; strip output ends with \n
        stamped = stamp("body", {"no_date": True})
        self.assertTrue(stamped.endswith("\n"))

    def test_strip_output_ends_with_single_newline(self):
        stamped = stamp("body\n\n\n", {"no_date": True})
        p = parse(stamped)
        self.assertEqual(p["body"], "body")


class TestEmptyBody(unittest.TestCase):
    """Empty body is valid -- SHA256 of empty string is well-defined."""

    def test_empty_body_stamps(self):
        stamped = stamp("", {"no_date": True})
        self.assertIn(HEADER_MARKER, stamped)

    def test_empty_body_verifies(self):
        p = _stamp_parse("")
        self.assertTrue(p["is_stamped"])
        self.assertTrue(p["sha256_ok"])

    def test_empty_body_sha256_known(self):
        # SHA256 of empty string is a known constant
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(_sha256(""), expected)


class TestHeaderDetection(unittest.TestCase):
    """
    Regression: loose is_stamped check could misidentify arbitrary comment
    blocks as stamped files. Now requires first non-empty line == "# ARCHIVIST".
    """

    def test_comment_prefixed_file_not_stamped(self):
        text = "# This is just a comment\n# Not archivist format\nsome body"
        p = parse(text)
        self.assertFalse(p["is_stamped"])

    def test_archivist_word_in_body_not_stamped(self):
        # ARCHIVIST appears in body, not header
        text = "This document mentions ARCHIVIST in passing."
        p = parse(text)
        self.assertFalse(p["is_stamped"])

    def test_truncated_header_no_sha256_not_stamped(self):
        # Has ARCHIVIST first line but no SHA256 field
        text = "# ARCHIVIST   v1.0\n# TITLE       Something\n\nbody"
        p = parse(text)
        self.assertFalse(p["is_stamped"])

    def test_valid_minimal_header(self):
        # Minimum valid: ARCHIVIST line + SHA256 field
        digest = _sha256("body")
        text   = "# ARCHIVIST   v1.0\n# SHA256      {}\n\nbody".format(digest)
        p = parse(text)
        self.assertTrue(p["is_stamped"])
        self.assertTrue(p["sha256_ok"])

    def test_plain_text_not_stamped(self):
        p = parse("All human beings are born free.")
        self.assertFalse(p["is_stamped"])
        self.assertEqual(p["body"], "All human beings are born free.")


class TestHeaderOnlyFile(unittest.TestCase):
    """A stamped file with no body section should not crash."""

    def test_header_only_does_not_crash(self):
        # Build a stamped file then strip the body section
        stamped      = stamp("", {"no_date": True})
        header_only  = stamped.split("\n\n")[0]  # remove body section entirely
        p = parse(header_only)
        # Should not raise; is_stamped depends on SHA256 field presence
        self.assertIsNotNone(p)

    def test_header_only_body_is_empty(self):
        stamped     = stamp("", {"no_date": True})
        header_only = stamped.split("\n\n")[0]
        p = parse(header_only)
        self.assertEqual(p["body"], "")


class TestTamperedBody(unittest.TestCase):
    """Verification must fail when the body is modified after stamping."""

    def test_tampered_body_fails_verify(self):
        stamped  = stamp("original body", {"no_date": True})
        tampered = stamped.replace("original body", "modified body")
        p = parse(tampered)
        self.assertTrue(p["is_stamped"])
        self.assertFalse(p["sha256_ok"])

    def test_tampered_body_shows_both_hashes(self):
        stamped  = stamp("original", {"no_date": True})
        tampered = stamped.replace("original", "changed")
        p = parse(tampered)
        self.assertNotEqual(p["sha256_declared"], p["sha256_actual"])


class TestUnstampedPassthrough(unittest.TestCase):
    """Unstamped files parsed as plain body, no crash, no false positive."""

    def test_plain_body_preserved(self):
        text = "No header here\nJust plain text."
        p    = parse(text)
        self.assertFalse(p["is_stamped"])
        self.assertEqual(p["body"], text)

    def test_empty_file(self):
        p = parse("")
        self.assertFalse(p["is_stamped"])
        self.assertEqual(p["body"], "")

    def test_whitespace_only(self):
        p = parse("   \n  \n")
        self.assertFalse(p["is_stamped"])


class TestFieldParsing(unittest.TestCase):
    """Field parsing: canonical double-space format and legacy colon fallback."""

    def test_double_space_separator(self):
        digest = _sha256("body")
        text   = "# ARCHIVIST   v1.0\n# TITLE       My Title\n# SHA256      {}\n\nbody".format(digest)
        p = parse(text)
        self.assertEqual(p["fields"]["TITLE"], "My Title")

    def test_legacy_colon_separator_known_field(self):
        # Colon fallback should work for known fields
        digest = _sha256("body")
        text   = "# ARCHIVIST   v1.0\n# TITLE: Legacy Title\n# SHA256      {}\n\nbody".format(digest)
        p = parse(text)
        self.assertEqual(p["fields"].get("TITLE"), "Legacy Title")

    def test_colon_in_url_not_misinterpreted(self):
        """
        Regression: a SOURCE field value like https://example.com could
        previously be split at the colon in the URL when the legacy path
        fired. The double-space path now takes priority, so this is fine,
        but a malformed header line with only a colon should NOT produce
        a spurious field named after whatever came before the colon.
        """
        digest = _sha256("body")
        # Malformed line: no double-space, colon is in an unknown field name
        text = (
            "# ARCHIVIST   v1.0\n"
            "# WEIRDKEY: some value\n"  # not a known field
            "# SHA256      {}\n\nbody"
        ).format(digest)
        p = parse(text)
        # WEIRDKEY is not in the known-fields set, so it must not appear
        self.assertNotIn("WEIRDKEY", p["fields"])

    def test_unknown_field_via_double_space_preserved(self):
        # Unknown fields using the canonical double-space format ARE stored
        digest = _sha256("body")
        text   = "# ARCHIVIST   v1.0\n# CUSTOM      my value\n# SHA256      {}\n\nbody".format(digest)
        p = parse(text)
        self.assertEqual(p["fields"].get("CUSTOM"), "my value")


class TestNormalise(unittest.TestCase):
    """_normalise() handles all three line-ending styles."""

    def test_crlf(self):
        self.assertEqual(_normalise("a\r\nb"), "a\nb")

    def test_bare_cr(self):
        self.assertEqual(_normalise("a\rb"), "a\nb")

    def test_lf_unchanged(self):
        self.assertEqual(_normalise("a\nb"), "a\nb")

    def test_mixed(self):
        result = _normalise("a\r\nb\rc\nd")
        self.assertNotIn("\r", result)


class TestCharCount(unittest.TestCase):
    """CHARS header field must match len(body) after normalisation."""

    def test_ascii_char_count(self):
        body = "Hello"
        p    = _stamp_parse(body)
        self.assertEqual(int(p["fields"]["CHARS"].replace(",", "")), len(body))

    def test_unicode_char_count(self):
        body = "\u4e2d\u6587"  # two CJK characters
        p    = _stamp_parse(body)
        self.assertEqual(int(p["fields"]["CHARS"].replace(",", "")), len(body))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = loader.loadTestsFromModule(sys.modules[__name__])
    runner  = unittest.TextTestRunner(verbosity=2)
    result  = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
