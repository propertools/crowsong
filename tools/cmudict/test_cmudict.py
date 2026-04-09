#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_cmudict.py -- Canonical test suite for cmudict.py

Covers the CAHF format layer (normalisation, hashing contract, header
generation, sentinel splitting, field parsing, verification taxonomy),
the CMU dict parser, syllable counting, bin building, and export
provenance fields.

All tests run offline with no network access and no cached file required.

Run with:
    python test_cmudict.py
    python -m pytest test_cmudict.py -v   # if pytest is available

Compatibility: Python 2.7+ / 3.x
"""

from __future__ import print_function, unicode_literals

import importlib
import io
import os
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Load cmudict without triggering __main__
# ---------------------------------------------------------------------------

def _load_cmudict():
    here   = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "cmudict.py")
    if not os.path.exists(target):
        raise RuntimeError(
            "cmudict.py not found next to test file: " + target)
    try:
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("cmudict", target)
        mod  = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except AttributeError:
        import imp
        return imp.load_source("cmudict", target)

_mod = _load_cmudict()

# Pull out everything we test directly
_normalise_body      = _mod._normalise_body
_sha256_of_body      = _mod._sha256_of_body
_make_header         = _mod._make_header
_split_header_body   = _mod._split_header_body
_parse_cahf_header   = _mod._parse_cahf_header
_load_verified_body  = _mod._load_verified_body
_parse_dict          = _mod._parse_dict
_syllable_count      = _mod._syllable_count
build_bins           = _mod.build_bins
get_syllables        = _mod.get_syllables
get_phones           = _mod.get_phones
get_all_pronunciations = _mod.get_all_pronunciations
load_verified_dict   = _mod.load_verified_dict

CAHF_SENTINEL        = _mod.CAHF_SENTINEL
CAHF_VERSION         = _mod.CAHF_VERSION
_ACCEPTED_VERSIONS   = _mod._ACCEPTED_VERSIONS
_REQUIRED_FIELDS     = _mod._REQUIRED_FIELDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_file(body, extra_header_lines=None, source_url="https://example.com/test"):
    """
    Build a syntactically valid CAHF file string from a body.
    Returns (file_content, body_for_hash, sha256).
    """
    body_for_hash = _normalise_body(body)
    header        = _make_header(body_for_hash, source_url)
    content       = header + "\n" + body_for_hash + "\n"
    sha256        = _sha256_of_body(body_for_hash)
    return content, body_for_hash, sha256


def _write_tmp(content):
    """Write content to a temp file, return path. Caller deletes."""
    fd, path = tempfile.mkstemp(suffix=".dict", prefix="test_cmudict_")
    try:
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    finally:
        os.close(fd)
    return path


# ---------------------------------------------------------------------------
# 1. Normalisation
# ---------------------------------------------------------------------------

class TestNormaliseBody(unittest.TestCase):
    """CAHF §4.1-4.2: line-ending normalisation and trailing-newline strip."""

    def test_lf_unchanged(self):
        self.assertEqual(_normalise_body("a\nb"), "a\nb")

    def test_crlf_becomes_lf(self):
        self.assertEqual(_normalise_body("a\r\nb"), "a\nb")

    def test_bare_cr_becomes_lf(self):
        self.assertEqual(_normalise_body("a\rb"), "a\nb")

    def test_mixed_endings_normalised(self):
        result = _normalise_body("a\r\nb\rc\nd")
        self.assertNotIn("\r", result)
        self.assertEqual(result, "a\nb\nc\nd")

    def test_crlf_first_order_no_double_replacement(self):
        # "\r\n" must become "\n", not "\n\n"
        self.assertEqual(_normalise_body("a\r\nb"), "a\nb")

    def test_single_trailing_newline_stripped(self):
        self.assertEqual(_normalise_body("hello\n"), "hello")

    def test_multiple_trailing_newlines_stripped(self):
        self.assertEqual(_normalise_body("hello\n\n\n"), "hello")

    def test_no_trailing_newline_unchanged(self):
        self.assertEqual(_normalise_body("hello"), "hello")

    def test_empty_string(self):
        self.assertEqual(_normalise_body(""), "")

    def test_only_newlines_becomes_empty(self):
        self.assertEqual(_normalise_body("\n\n\n"), "")


# ---------------------------------------------------------------------------
# 2. SHA256 hashing contract
# ---------------------------------------------------------------------------

class TestSha256Contract(unittest.TestCase):
    """CAHF §4.3-4.4: SHA256 is computed over the normalised body."""

    def test_known_empty_body(self):
        # SHA256 of empty string is a universal constant.
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        self.assertEqual(_sha256_of_body(""), expected)

    def test_known_hello(self):
        # SHA256("hello") -- trailing newlines are already stripped by caller.
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        self.assertEqual(_sha256_of_body("hello"), expected)

    def test_trailing_newline_stripped_before_hash(self):
        # "hello\n" and "hello" normalise to the same body_for_hash.
        self.assertEqual(
            _sha256_of_body(_normalise_body("hello\n")),
            _sha256_of_body("hello"))

    def test_crlf_body_same_hash_as_lf(self):
        lf_body   = _normalise_body("line one\nline two")
        crlf_body = _normalise_body("line one\r\nline two\r\n")
        self.assertEqual(_sha256_of_body(lf_body), _sha256_of_body(crlf_body))

    def test_result_is_lowercase_hex(self):
        digest = _sha256_of_body("test")
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_stamp_verify_consistency(self):
        """Round-trip: hash at stamp time == hash at verify time."""
        body          = "ENTROPY  EH1 N T R AH0 P IY0\nSIGNAL  S IH1 G N AH0 L\n"
        body_for_hash = _normalise_body(body)
        sha_stamp     = _sha256_of_body(body_for_hash)

        content, _, _ = _make_valid_file(body)
        _, body_verify = _split_header_body(content)
        sha_verify = _sha256_of_body(body_verify)

        self.assertEqual(sha_stamp, sha_verify)


# ---------------------------------------------------------------------------
# 3. Header generation
# ---------------------------------------------------------------------------

class TestMakeHeader(unittest.TestCase):
    """_make_header() emits a CAHF-conformant header block."""

    def setUp(self):
        self.body = "A  EY1\nABLE  EY1 B AH0 L\n"
        self.body_for_hash = _normalise_body(self.body)
        self.header = _make_header(self.body_for_hash, "https://example.com/dict")

    def test_starts_with_archivist_marker(self):
        first_line = self.header.splitlines()[0]
        self.assertTrue(first_line.startswith("# ARCHIVIST"))
        self.assertIn(CAHF_VERSION, first_line)

    def test_contains_sha256_field(self):
        self.assertIn("# SHA256", self.header)

    def test_sha256_value_is_correct(self):
        expected = _sha256_of_body(self.body_for_hash)
        for line in self.header.splitlines():
            if "SHA256" in line and "  " in line:
                _, _, val = line.partition("  ")
                self.assertEqual(val.strip(), expected)
                return
        self.fail("SHA256 field not found in header")

    def test_ends_with_sentinel(self):
        self.assertTrue(
            self.header.endswith(CAHF_SENTINEL),
            "Header must end with sentinel line")

    def test_source_url_present(self):
        self.assertIn("https://example.com/dict", self.header)

    def test_entries_is_plain_digit(self):
        """Numeric fields must be plain digits, no commas."""
        for line in self.header.splitlines():
            if line.startswith("# ENTRIES"):
                _, _, val = line.partition("  ")
                val = val.strip()
                self.assertTrue(val.isdigit(),
                    "ENTRIES should be plain digits, got: " + val)
                return

    def test_chars_is_plain_digit(self):
        for line in self.header.splitlines():
            if line.startswith("# CHARS"):
                _, _, val = line.partition("  ")
                val = val.strip()
                self.assertTrue(val.isdigit(),
                    "CHARS should be plain digits, got: " + val)
                return

    def test_no_trailing_lf_on_header_string(self):
        # cmd_fetch() adds the separator LF; _make_header() must not.
        self.assertFalse(self.header.endswith("\n"))


# ---------------------------------------------------------------------------
# 4. Sentinel splitting
# ---------------------------------------------------------------------------

class TestSplitHeaderBody(unittest.TestCase):
    """_split_header_body() -- exact sentinel, no fallback."""

    def _build(self, body):
        content, body_for_hash, _ = _make_valid_file(body)
        return content, body_for_hash

    def test_clean_split(self):
        content, expected_body = self._build("WORD  W ER1 D\n")
        header, body = _split_header_body(content)
        self.assertEqual(body, expected_body)
        self.assertIn("# ARCHIVIST", header)

    def test_body_trailing_lf_stripped(self):
        # Stored file has one trailing LF after body; split must strip it.
        content, expected_body = self._build("hello")
        _, body = _split_header_body(content)
        self.assertEqual(body, expected_body)
        self.assertFalse(body.endswith("\n"))

    def test_missing_sentinel_raises_valueerror(self):
        with self.assertRaises(ValueError):
            _split_header_body("# ARCHIVIST  v1.0\n# SHA256  abc\nsome body\n")

    def test_empty_body_splits_cleanly(self):
        content, expected_body = self._build("")
        _, body = _split_header_body(content)
        self.assertEqual(body, "")
        self.assertEqual(expected_body, "")

    def test_body_with_leading_blank_lines(self):
        # Body that starts with blank lines must not be confused with header.
        content, expected_body = self._build("\n\nfirst real line\n")
        _, body = _split_header_body(content)
        self.assertEqual(body, expected_body)

    def test_verifier_tolerates_missing_final_lf(self):
        # CAHF §4.4(b): verifiers SHOULD accept zero trailing LF.
        content, expected_body = self._build("hello")
        # Strip the final LF that _make_valid_file wrote.
        content_no_lf = content.rstrip("\n")
        _, body = _split_header_body(content_no_lf)
        self.assertEqual(body, expected_body)


# ---------------------------------------------------------------------------
# 5. Header field parsing
# ---------------------------------------------------------------------------

class TestParseCahfHeader(unittest.TestCase):
    """_parse_cahf_header() -- canonical double-space, legacy colon, duplicates."""

    def _header(self, *lines):
        return "\n".join(lines)

    def test_canonical_double_space(self):
        h = self._header("# ARCHIVIST   v1.0", "# SHA256      " + "a" * 64)
        f = _parse_cahf_header(h)
        self.assertEqual(f["ARCHIVIST"], "v1.0")
        self.assertEqual(f["SHA256"], "a" * 64)

    def test_legacy_colon_known_field(self):
        h = self._header("# ARCHIVIST   v1.0", "# SHA256: " + "b" * 64)
        f = _parse_cahf_header(h)
        self.assertIn("SHA256", f)

    def test_comment_prose_not_parsed_as_field(self):
        # "# Format: WORD  PH1 PH2" -- contains two spaces but "Format:"
        # is not a known field and the double-space path requires uppercase-only.
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# Format: WORD  PH1 PH2 ... PHn",
            "# SHA256      " + "c" * 64,
        )
        f = _parse_cahf_header(h)
        self.assertNotIn("Format: WORD", f)
        self.assertNotIn("Format:", f)
        self.assertIn("SHA256", f)

    def test_url_colon_not_misread(self):
        # SOURCE value contains "://" -- must not produce a spurious field.
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# SOURCE      https://example.com/dict",
            "# SHA256      " + "d" * 64,
        )
        f = _parse_cahf_header(h)
        self.assertEqual(f.get("SOURCE"), "https://example.com/dict")

    def test_unknown_field_via_double_space_stored(self):
        # Canonical parsing is structural: unknown fields are accepted.
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# CUSTOM      my-value",
            "# SHA256      " + "e" * 64,
        )
        f = _parse_cahf_header(h)
        self.assertEqual(f.get("CUSTOM"), "my-value")

    def test_unknown_field_via_colon_not_stored(self):
        # Legacy colon parsing is restricted to known fields.
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# WEIRDKEY: some value",
            "# SHA256      " + "f" * 64,
        )
        f = _parse_cahf_header(h)
        self.assertNotIn("WEIRDKEY", f)

    def test_blank_comment_lines_ignored(self):
        h = self._header(
            "# ARCHIVIST   v1.0",
            "#",
            "# SHA256      " + "0" * 64,
            "#",
        )
        f = _parse_cahf_header(h)
        self.assertIn("ARCHIVIST", f)

    def test_duplicate_required_field_raises(self):
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# SHA256      " + "a" * 64,
            "# SHA256      " + "b" * 64,
        )
        with self.assertRaises(ValueError):
            _parse_cahf_header(h)

    def test_duplicate_archivist_raises(self):
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# ARCHIVIST   v1.0",
            "# SHA256      " + "a" * 64,
        )
        with self.assertRaises(ValueError):
            _parse_cahf_header(h)

    def test_duplicate_optional_field_first_wins(self):
        # CAHF §3.1: first occurrence of optional field wins; later ignored.
        h = self._header(
            "# ARCHIVIST   v1.0",
            "# SOURCE      first-value",
            "# SOURCE      second-value",
            "# SHA256      " + "a" * 64,
        )
        f = _parse_cahf_header(h)
        self.assertEqual(f.get("SOURCE"), "first-value")


# ---------------------------------------------------------------------------
# 6. _load_verified_body() -- full verification path
# ---------------------------------------------------------------------------

class TestLoadVerifiedBody(unittest.TestCase):
    """Integration: _load_verified_body() against real temp files."""

    def _write_valid(self, body="ENTROPY  EH1 N T R AH0 P IY0\n"):
        content, body_for_hash, sha256 = _make_valid_file(body)
        path = _write_tmp(content)
        return path, body_for_hash, sha256

    def tearDown(self):
        # Individual tests clean up their own paths.
        pass

    def test_clean_verification_passes(self):
        path, expected_body, expected_sha256 = self._write_valid()
        try:
            body, sha256 = _load_verified_body(path)
            self.assertEqual(body, expected_body)
            self.assertEqual(sha256, expected_sha256)
        finally:
            os.unlink(path)

    def test_tampered_body_fails(self):
        path, _, _ = self._write_valid()
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            tampered = content.replace(
                "ENTROPY  EH1 N T R AH0 P IY0",
                "ENTROPY  EH1 N T R AH0 P IY1")
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(tampered)
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    def test_missing_file_raises_ioerror(self):
        with self.assertRaises(IOError):
            _load_verified_body("/nonexistent/path/cmudict.dict")

    def test_unstamped_file_raises_ioerror(self):
        path = _write_tmp("just plain text\nno header\n")
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    def test_missing_sentinel_raises_ioerror(self):
        # Build a file that looks CAHF-ish but has no sentinel.
        content = "# ARCHIVIST   v1.0\n# SHA256      " + "a" * 64 + "\nsome body\n"
        path = _write_tmp(content)
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    def test_missing_sha256_field_raises_ioerror(self):
        content, body_for_hash, _ = _make_valid_file("test body")
        # Remove the SHA256 line.
        lines = [l for l in content.splitlines()
                 if not l.startswith("# SHA256")]
        path = _write_tmp("\n".join(lines) + "\n")
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    def test_invalid_sha256_syntax_raises_ioerror(self):
        content, _, _ = _make_valid_file("test body")
        # Replace SHA256 value with invalid syntax.
        broken = content.replace(
            _sha256_of_body(_normalise_body("test body")),
            "not-a-valid-sha256")
        path = _write_tmp(broken)
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    def test_uppercase_sha256_accepted(self):
        """Regression: uppercase SHA256 must not cause false mismatch."""
        content, body_for_hash, sha256_lower = _make_valid_file("hello world")
        # Replace lowercase SHA256 with uppercase equivalent.
        sha256_upper = sha256_lower.upper()
        content_upper = content.replace(sha256_lower, sha256_upper)
        path = _write_tmp(content_upper)
        try:
            body, sha256_out = _load_verified_body(path)
            self.assertEqual(body, body_for_hash)
            self.assertEqual(sha256_out, sha256_lower)  # always returns lowercase
        finally:
            os.unlink(path)

    def test_unsupported_version_raises_ioerror(self):
        content, _, _ = _make_valid_file("body")
        broken = content.replace("# ARCHIVIST   v1.0", "# ARCHIVIST   v99.0")
        path = _write_tmp(broken)
        try:
            with self.assertRaises(IOError) as ctx:
                _load_verified_body(path)
            self.assertIn("v99.0", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_duplicate_required_field_raises_ioerror(self):
        content, _, sha256 = _make_valid_file("body")
        # Inject a second SHA256 line.
        sha_line = "# SHA256      " + sha256
        broken = content.replace(sha_line, sha_line + "\n" + sha_line)
        path = _write_tmp(broken)
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 7. CMU dict parser
# ---------------------------------------------------------------------------

MINI_DICT = (
    "A  EY1\n"
    "A(2)  EH1\n"
    "ABLE  EY1 B AH0 L\n"
    "ENTROPY  EH1 N T R AH0 P IY0\n"
    "PRIME  P R AY1 M\n"
    "SIGNAL  S IH1 G N AH0 L\n"
    "READ  R IY1 D\n"
    "READ(2)  R EH1 D\n"
    "; This is a comment\n"
    "# Also a comment\n"
)


class TestParseDict(unittest.TestCase):
    """_parse_dict() -- basic parser behaviour."""

    def setUp(self):
        self.d = _parse_dict(MINI_DICT)

    def test_basic_entry(self):
        self.assertIn("entropy", self.d)
        self.assertEqual(self.d["entropy"][0],
                         ["EH1", "N", "T", "R", "AH0", "P", "IY0"])

    def test_lowercase_keys(self):
        self.assertIn("signal", self.d)
        self.assertNotIn("SIGNAL", self.d)

    def test_comment_lines_skipped(self):
        # Neither ";" nor "#" prefixed lines produce entries.
        for key in self.d:
            self.assertFalse(key.startswith(";"))
            self.assertFalse(key.startswith("#"))

    def test_alternate_pronunciations_stored(self):
        # READ has two pronunciations.
        self.assertEqual(len(self.d["read"]), 2)
        self.assertEqual(self.d["read"][0], ["R", "IY1", "D"])
        self.assertEqual(self.d["read"][1], ["R", "EH1", "D"])

    def test_alternate_suffix_stripped(self):
        # A(2) should collapse into the "a" key, not create "a(2)".
        self.assertNotIn("a(2)", self.d)
        self.assertEqual(len(self.d["a"]), 2)

    def test_case_insensitive_lookup(self):
        self.assertIn("entropy", self.d)
        # Parser stores lowercase; caller uses .lower() for lookup.
        self.assertEqual(self.d.get("ENTROPY"), None)

    def test_empty_content(self):
        self.assertEqual(_parse_dict(""), {})

    def test_cahf_header_lines_skipped(self):
        # A CAHF-wrapped file feeds its full content here; header is ignored.
        content = "# ARCHIVIST   v1.0\n# SHA256      " + "a" * 64 + "\n"
        content += "# ---END-HEADER---\n"
        content += "PRIME  P R AY1 M\n"
        d = _parse_dict(content)
        self.assertIn("prime", d)
        self.assertNotIn("archivist", d)


# ---------------------------------------------------------------------------
# 8. Syllable counting
# ---------------------------------------------------------------------------

class TestSyllableCount(unittest.TestCase):
    """_syllable_count() and get_syllables() -- vowel nucleus counting."""

    def setUp(self):
        self.d = _parse_dict(MINI_DICT)

    def test_entropy_3_syllables(self):
        self.assertEqual(get_syllables(self.d, "entropy"), 3)

    def test_signal_2_syllables(self):
        self.assertEqual(get_syllables(self.d, "signal"), 2)

    def test_prime_1_syllable(self):
        self.assertEqual(get_syllables(self.d, "prime"), 1)

    def test_able_2_syllables(self):
        self.assertEqual(get_syllables(self.d, "able"), 2)

    def test_case_insensitive(self):
        self.assertEqual(get_syllables(self.d, "ENTROPY"), 3)
        self.assertEqual(get_syllables(self.d, "Entropy"), 3)

    def test_unknown_word_returns_none(self):
        self.assertIsNone(get_syllables(self.d, "xyzzy"))

    def test_primary_pronunciation_used(self):
        # "a" has two pronunciations; syllable count uses first.
        n = get_syllables(self.d, "a")
        self.assertEqual(n, _syllable_count(self.d["a"][0]))

    def test_direct_syllable_count(self):
        self.assertEqual(_syllable_count(["EH1", "N", "T", "R", "AH0", "P", "IY0"]), 3)
        self.assertEqual(_syllable_count(["P", "R", "AY1", "M"]), 1)
        self.assertEqual(_syllable_count(["S", "IH1", "G", "N", "AH0", "L"]), 2)


# ---------------------------------------------------------------------------
# 9. Phoneme lookup
# ---------------------------------------------------------------------------

class TestGetPhones(unittest.TestCase):

    def setUp(self):
        self.d = _parse_dict(MINI_DICT)

    def test_primary_pronunciation(self):
        phones = get_phones(self.d, "entropy")
        self.assertEqual(phones, ["EH1", "N", "T", "R", "AH0", "P", "IY0"])

    def test_all_pronunciations(self):
        all_pron = get_all_pronunciations(self.d, "read")
        self.assertEqual(len(all_pron), 2)

    def test_unknown_word_returns_none(self):
        self.assertIsNone(get_phones(self.d, "xyzzy"))

    def test_unknown_word_all_pronunciations_empty(self):
        self.assertEqual(get_all_pronunciations(self.d, "xyzzy"), [])


# ---------------------------------------------------------------------------
# 10. Bin building
# ---------------------------------------------------------------------------

class TestBuildBins(unittest.TestCase):

    def setUp(self):
        self.d = _parse_dict(MINI_DICT)
        self.bins = build_bins(self.d)

    def test_bins_are_present(self):
        self.assertIn(1, self.bins)
        self.assertIn(2, self.bins)
        self.assertIn(3, self.bins)

    def test_correct_syllable_assignment(self):
        self.assertIn("prime", self.bins[1])
        self.assertIn("signal", self.bins[2])
        self.assertIn("entropy", self.bins[3])

    def test_words_alphabetically_sorted(self):
        for n, words in self.bins.items():
            self.assertEqual(words, sorted(words),
                "Bin {0} is not sorted".format(n))

    def test_zero_syllable_words_excluded(self):
        # No bin should contain a word with 0 syllables.
        for n in self.bins:
            self.assertGreater(n, 0)

    def test_primary_pronunciation_used_for_binning(self):
        # "a" has two pronunciations, both with 1 syllable; should be in bin 1.
        self.assertIn("a", self.bins[1])

    def test_empty_dict_gives_empty_bins(self):
        self.assertEqual(build_bins({}), {})


# ---------------------------------------------------------------------------
# 11. Export provenance
# ---------------------------------------------------------------------------

class TestExportProvenance(unittest.TestCase):
    """_make_header() provides source_sha256 for export _meta."""

    def test_sha256_round_trips_from_header(self):
        """SHA256 stored in header == SHA256 computable from body after split."""
        body          = "ENTROPY  EH1 N T R AH0 P IY0\n"
        body_for_hash = _normalise_body(body)
        header        = _make_header(body_for_hash, "https://example.com/dict")
        content       = header + "\n" + body_for_hash + "\n"

        _, body_out = _split_header_body(content)
        sha256_actual = _sha256_of_body(body_out)

        # Extract declared SHA256 from header
        sha256_declared = None
        for line in header.splitlines():
            if line.startswith("# SHA256"):
                sha256_declared = line.split("  ", 1)[-1].strip()
                break

        self.assertIsNotNone(sha256_declared)
        self.assertEqual(sha256_actual, sha256_declared)

    def test_source_url_in_header(self):
        body_for_hash = _normalise_body("WORD  W ER1 D\n")
        url = "https://example.com/cmudict.dict"
        header = _make_header(body_for_hash, url)
        self.assertIn(url, header)


# ---------------------------------------------------------------------------
# 12. Verification taxonomy (output labels)
# ---------------------------------------------------------------------------

class TestVerificationTaxonomy(unittest.TestCase):
    """
    Smoke-check that _load_verified_body raises descriptive IOErrors
    matching the CAHF taxonomy for each failure category.
    """

    def _fails_with(self, content, *substrings):
        path = _write_tmp(content)
        try:
            with self.assertRaises(IOError) as ctx:
                _load_verified_body(path)
            msg = str(ctx.exception)
            for s in substrings:
                self.assertIn(s, msg,
                    "Expected '{0}' in error: {1}".format(s, msg))
        finally:
            os.unlink(path)

    def test_unstamped_no_archivist(self):
        self._fails_with(
            "just plain text\n",
            "ARCHIVIST")

    def test_legacy_no_sentinel(self):
        sha = _sha256_of_body("body")
        self._fails_with(
            "# ARCHIVIST   v1.0\n# SHA256      {0}\nbody\n".format(sha),
            "sentinel")

    def test_damaged_no_sha256(self):
        content, _, _ = _make_valid_file("body")
        no_sha = "\n".join(
            l for l in content.splitlines()
            if not l.startswith("# SHA256")) + "\n"
        self._fails_with(no_sha, "SHA256")

    def test_damaged_invalid_sha256_syntax(self):
        content, _, sha256 = _make_valid_file("body")
        broken = content.replace(sha256, "not-hex-not-64-chars")
        self._fails_with(broken, "invalid SHA256")

    def test_damaged_sha256_mismatch(self):
        content, _, _ = _make_valid_file("body")
        # Replace first hex char to break the hash.
        import re as _re
        broken = _re.sub(
            r"(# SHA256\s+)([0-9a-f]{64})",
            lambda m: m.group(1) + ("f" if m.group(2)[0] != "f" else "e") + m.group(2)[1:],
            content)
        self._fails_with(broken, "verification")

    def test_unsupported_version(self):
        content, _, _ = _make_valid_file("body")
        broken = content.replace("# ARCHIVIST   v1.0", "# ARCHIVIST   v99.0")
        self._fails_with(broken, "v99.0")

    def test_malformed_duplicate_required_field(self):
        content, _, sha256 = _make_valid_file("body")
        sha_line = "# SHA256      " + sha256
        broken = content.replace(sha_line, sha_line + "\n" + sha_line)
        self._fails_with(broken, "Duplicate")


# ---------------------------------------------------------------------------
# 13. Regression: bugs fixed during crowsong-01 review
# ---------------------------------------------------------------------------

class TestRegressions(unittest.TestCase):
    """
    Targeted regression tests for every bug fixed in the crowsong-01
    pre-release code review.
    """

    # --- Bug: HTTP fallback allowed first-fetch MITM ---
    def test_no_http_sources(self):
        """All configured sources must be HTTPS."""
        for url in _mod.CMUDICT_SOURCES:
            self.assertTrue(url.startswith("https://"),
                "Non-HTTPS source: " + url)

    # --- Bug: verify hashed normalised reconstruction, not stored body ---
    def test_stamp_verify_hash_identical_bytes(self):
        """Fetch-time hash == verify-time hash for same logical body."""
        body = "PRIME  P R AY1 M\nSIGNAL  S IH1 G N AH0 L\n"
        body_for_hash = _normalise_body(body)
        sha_at_stamp = _sha256_of_body(body_for_hash)

        content, _, _ = _make_valid_file(body)
        _, body_at_verify = _split_header_body(content)
        sha_at_verify = _sha256_of_body(body_at_verify)

        self.assertEqual(sha_at_stamp, sha_at_verify)

    # --- Bug: verify returned PASS when SHA256 field absent ---
    def test_no_sha256_field_is_not_pass(self):
        content, _, _ = _make_valid_file("body")
        no_sha = "\n".join(
            l for l in content.splitlines()
            if not l.startswith("# SHA256")) + "\n"
        path = _write_tmp(no_sha)
        try:
            with self.assertRaises(IOError):
                _load_verified_body(path)
        finally:
            os.unlink(path)

    # --- Bug: HTTP fallback (removed) and errors="replace" (removed) ---
    def test_fetch_url_no_error_replace(self):
        """_fetch_url decodes strictly (no errors='replace' in source)."""
        import inspect
        src = inspect.getsource(_mod._fetch_url)
        self.assertNotIn('errors="replace"', src)
        self.assertNotIn("errors='replace'", src)

    # --- Bug: alternate pronunciation stripped too broadly ---
    def test_alternate_suffix_precise_pattern(self):
        """Only terminal (digits) suffix is stripped, not mid-token parens."""
        d = _parse_dict("WORD(2)  W ER1 D\n")
        self.assertIn("word", d)
        self.assertNotIn("word(2)", d)

    # --- Bug: Size printed as char count labelled "bytes" ---
    def test_make_header_chars_field_is_len(self):
        body_for_hash = _normalise_body("hello")
        header = _make_header(body_for_hash, "https://example.com/")
        for line in header.splitlines():
            if line.startswith("# CHARS"):
                _, _, val = line.partition("  ")
                self.assertEqual(int(val.strip()), len(body_for_hash))
                return

    # --- Bug: positive_int() raised raw ValueError on bad input ---
    def test_positive_int_bad_input(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            _mod.positive_int("xyz")
        with self.assertRaises(argparse.ArgumentTypeError):
            _mod.positive_int(None)

    # --- Bug: cmd_fetch() could write bad cache after failed sanity check ---
    def test_fetch_success_requires_source_url(self):
        """source_url being None after loop must prevent any write."""
        # We cannot run a real fetch, but we can verify the guard logic
        # is in the source.
        import inspect
        src = inspect.getsource(_mod.cmd_fetch)
        self.assertIn("if source_url is None:", src)
        # And that the old guard (body_raw is None) is gone.
        self.assertNotIn("if body_raw is None:", src)

    # --- Bug: uppercase SHA256 caused false mismatch ---
    def test_uppercase_sha256_not_rejected(self):
        content, body_for_hash, sha256_lower = _make_valid_file("hello world")
        sha256_upper = sha256_lower.upper()
        content_upper = content.replace(sha256_lower, sha256_upper)
        path = _write_tmp(content_upper)
        try:
            body, sha256_out = _load_verified_body(path)
            self.assertEqual(body, body_for_hash)
        finally:
            os.unlink(path)

    # --- Bug: comment prose misread as CAHF field ---
    def test_comment_prose_not_a_field(self):
        """'# Format: WORD  PH1 PH2' must not produce a spurious field."""
        h = (
            "# ARCHIVIST   v1.0\n"
            "# Format: WORD  PH1 PH2 ... PHn\n"
            "# SHA256      " + "a" * 64 + "\n"
        )
        f = _parse_cahf_header(h)
        for key in f:
            self.assertNotIn("Format", key)
            self.assertNotIn("WORD", key)

    # --- Bug: duplicate required fields silently last-one-wins ---
    def test_duplicate_sha256_raises(self):
        h = (
            "# ARCHIVIST   v1.0\n"
            "# SHA256      " + "a" * 64 + "\n"
            "# SHA256      " + "b" * 64 + "\n"
        )
        with self.assertRaises(ValueError):
            _parse_cahf_header(h)

    # --- Spec: optional duplicate first-wins (not raise) ---
    def test_duplicate_optional_first_wins_not_raise(self):
        h = (
            "# ARCHIVIST   v1.0\n"
            "# SOURCE      first\n"
            "# SOURCE      second\n"
            "# SHA256      " + "a" * 64 + "\n"
        )
        f = _parse_cahf_header(h)
        self.assertEqual(f["SOURCE"], "first")

    # --- Spec: min_syllables > max_syllables rejected ---
    def test_min_gt_max_syllables_rejected(self):
        """export --min-syllables 7 --max-syllables 3 must fail before running."""
        import inspect
        src = inspect.getsource(_mod.main)
        self.assertIn("min_syllables > args.max_syllables", src)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
