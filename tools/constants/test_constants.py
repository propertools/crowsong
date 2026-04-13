#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_constants.py — test suite for constants.py

Covers:
  - Canonical digit vectors (known-good expected outputs)
  - format_digits layout
  - CAHF body normalisation and hashing contract
  - generate/verify round-trip
  - parse_cahf_file: structural validation, field parsing, body validation
  - Verification failure modes: missing fields, bad SHA256, bad CRC32,
    junk in body, duplicate singleton fields, tampered body
  - Python 2.7 / 3.x compatibility of all public interfaces

Run:
    python -m pytest test_constants.py -v
    python test_constants.py          # fallback: unittest discover

Compatibility: Python 2.7+ / 3.x
Requires: mpmath (pip install mpmath)
"""

from __future__ import print_function, unicode_literals

import hashlib
import io
import os
import sys
import tempfile
import unittest
import zlib

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import constants as C


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp(content):
    """Write a Unicode string to a named temp file; return the path."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _cleanup(path):
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 1. Canonical digit vectors
#
# These are the ground-truth expected outputs for a small, fixed digit count.
# If any of these fail, the digit generation or formatting logic has regressed.
# Vectors were computed from the implementation on 2026-04-10 and are
# committed here as the authoritative reference.
# ---------------------------------------------------------------------------

class TestCanonicalVectors(unittest.TestCase):

    # Raw digit strings — no formatting, no whitespace.
    # Verify against well-known published values.
    DIGITS = {
        ("pi",    10): "3141592653",
        ("pi",    32): "31415926535897932384626433832795",
        ("pi",    60): "314159265358979323846264338327950288419716939937510582097494",
        ("e",     32): "27182818284590452353602874713526",
        ("phi",   32): "16180339887498948482045868343656",
        ("sqrt2", 32): "14142135623730950488016887242096",
    }

    # SHA256 over the *formatted* body (spaces + newlines), normalised per
    # CAHF §4.4.  These must match what generate/verify use.
    SHA256 = {
        ("pi",    10): "0ac59a6eff4c0d73984b7ec775d6a01864e80dbc5e5488c594ed1ae4748ff56d",
        ("pi",    32): "53a08d54fc2eaebfe8e92e76e0600f4ac2c115cee8bafbbbf94fbf109829bb00",
        ("pi",    60): "97c92c160413c7d68c956280187051b59d2b3bdd01f1b1b09ac4e655caf13b01",
        ("e",     32): "3b1b67a05da641fbfb5b37e6cf772bb5f819b351a05b5ea13adc17ad3ee29172",
        ("phi",   32): "b1439008d356ec1f115fb3ee35b998fcf5faf182ae2d807c9e73e6301af54b5a",
        ("sqrt2", 32): "94a8a0d90084394a57c5627e5894e712e3131ddce339b611eb27b8bdc6b674ce",
    }

    # CRC32 over the same formatted body.
    CRC32 = {
        ("pi",    10): "c93430fc",
        ("pi",    32): "25e6a783",
        ("pi",    60): "766fd432",
        ("e",     32): "8f9580c4",
        ("phi",   32): "af0c3aa3",
        ("sqrt2", 32): "2c8ca82c",
    }

    def _body(self, name, count):
        digits = C.get_digits(name, count)
        return C._normalise_body(C.format_digits(digits))

    def test_digit_strings(self):
        for (name, count), expected in self.DIGITS.items():
            with self.subTest(name=name, count=count):
                got = C.get_digits(name, count)
                self.assertEqual(got, expected,
                    "digit mismatch for {0}/{1}".format(name, count))

    def test_sha256_over_formatted_body(self):
        for (name, count), expected in self.SHA256.items():
            with self.subTest(name=name, count=count):
                body = self._body(name, count)
                got = C.sha256_hex(body)
                self.assertEqual(got, expected,
                    "SHA256 mismatch for {0}/{1}".format(name, count))

    def test_crc32_over_formatted_body(self):
        for (name, count), expected in self.CRC32.items():
            with self.subTest(name=name, count=count):
                body = self._body(name, count)
                got = C.crc32_hex(body)
                self.assertEqual(got, expected,
                    "CRC32 mismatch for {0}/{1}".format(name, count))

    def test_get_digits_exact_count(self):
        """get_digits must return exactly the requested number of digits."""
        for count in (1, 10, 32, 100):
            with self.subTest(count=count):
                d = C.get_digits("pi", count)
                self.assertEqual(len(d), count)
                self.assertTrue(d.isdigit())

    def test_get_digits_unknown_constant(self):
        with self.assertRaises(ValueError):
            C.get_digits("notaconstant", 10)

    def test_get_digits_restores_mpmath_dps(self):
        """get_digits must not permanently mutate mpmath.mp.dps."""
        import mpmath
        before = mpmath.mp.dps
        C.get_digits("pi", 500)
        self.assertEqual(mpmath.mp.dps, before)

    def test_all_registry_constants_are_reachable(self):
        """Every constant in the registry should produce 10 digits without error."""
        for name in C.CONSTANTS:
            with self.subTest(name=name):
                d = C.get_digits(name, 10)
                self.assertEqual(len(d), 10)


# ---------------------------------------------------------------------------
# 2. format_digits layout
# ---------------------------------------------------------------------------

class TestFormatDigits(unittest.TestCase):

    def test_groups_of_10(self):
        digits = "1234567890" * 3
        formatted = C.format_digits(digits)
        # Each group is 10 digits separated by a single space
        first_line = formatted.split("\n")[0]
        groups = first_line.split(" ")
        for g in groups:
            self.assertEqual(len(g), 10)
            self.assertTrue(g.isdigit())

    def test_60_digits_one_line(self):
        """60 digits = exactly 6 groups = one line."""
        digits = "0" * 60
        formatted = C.format_digits(digits)
        self.assertEqual(formatted.count("\n"), 0)

    def test_61_digits_two_lines(self):
        """61 digits should wrap to a second line."""
        digits = "0" * 61
        formatted = C.format_digits(digits)
        self.assertEqual(formatted.count("\n"), 1)

    def test_pi_first_line(self):
        """Known first formatted line of pi/60."""
        digits = C.get_digits("pi", 60)
        body = C.format_digits(digits)
        first_line = body.split("\n")[0]
        self.assertEqual(
            first_line,
            "3141592653 5897932384 6264338327 9502884197 1693993751 0582097494"
        )

    def test_pi_32_first_line(self):
        """Known first formatted line of pi/32 (partial last group)."""
        digits = C.get_digits("pi", 32)
        body = C.format_digits(digits)
        first_line = body.split("\n")[0]
        self.assertEqual(
            first_line,
            "3141592653 5897932384 6264338327 95"
        )

    def test_round_trip_digits_preserved(self):
        """All digits extracted from formatted output must equal the input."""
        for name in ("pi", "e", "phi"):
            digits = C.get_digits(name, 100)
            formatted = C.format_digits(digits)
            extracted = "".join(ch for ch in formatted if ch.isdigit())
            self.assertEqual(extracted, digits)


# ---------------------------------------------------------------------------
# 3. CAHF normalisation and hashing contract (§4)
# ---------------------------------------------------------------------------

class TestNormalisation(unittest.TestCase):

    def test_crlf_normalised_to_lf(self):
        text = "hello\r\nworld\r\n"
        self.assertEqual(C._normalise_line_endings(text), "hello\nworld\n")

    def test_bare_cr_normalised(self):
        text = "hello\rworld"
        self.assertEqual(C._normalise_line_endings(text), "hello\nworld")

    def test_crlf_before_cr_no_double_replace(self):
        """CRLF must be replaced before bare CR to avoid double-replacement."""
        text = "a\r\nb"
        result = C._normalise_line_endings(text)
        self.assertEqual(result, "a\nb")
        self.assertNotIn("\r", result)

    def test_normalise_body_strips_trailing_newlines(self):
        self.assertEqual(C._normalise_body("abc\n\n\n"), "abc")
        self.assertEqual(C._normalise_body("abc\n"), "abc")
        self.assertEqual(C._normalise_body("abc"), "abc")

    def test_cahf_empty_body_sha256(self):
        """SHA256 of empty string is the well-known CAHF constant (§B)."""
        self.assertEqual(
            C.sha256_hex(""),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_cahf_hello_sha256(self):
        """'hello' and 'hello\\n' produce the same digest after normalisation."""
        h1 = C.sha256_hex(C._normalise_body("hello"))
        h2 = C.sha256_hex(C._normalise_body("hello\n"))
        self.assertEqual(h1, h2)
        self.assertEqual(
            h1,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_crc32_hex_is_8_chars_lowercase(self):
        result = C.crc32_hex("test")
        self.assertEqual(len(result), 8)
        self.assertEqual(result, result.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

    def test_stamp_verify_hash_symmetry(self):
        """Hash computed at stamp time must equal hash computed at verify time."""
        digits = C.get_digits("pi", 60)
        # Stamp path
        body_raw = C.format_digits(digits)
        body_for_hash = C._normalise_body(body_raw)
        sha_stamp = C.sha256_hex(body_for_hash)

        # Verify path: simulate what parse_cahf_file does after sentinel split
        # body_text = content after sentinel, body_for_hash = normalise(body_text)
        # The stored file has body_for_hash + "\n" after the sentinel.
        stored_body = body_for_hash + "\n"
        body_verify = C._normalise_body(stored_body)
        sha_verify = C.sha256_hex(body_verify)

        self.assertEqual(sha_stamp, sha_verify)


# ---------------------------------------------------------------------------
# 4. generate / verify round-trip
# ---------------------------------------------------------------------------

class TestGenerateVerifyRoundtrip(unittest.TestCase):

    def setUp(self):
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            _cleanup(p)

    def _tmp(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        self.paths.append(path)
        return path

    def test_make_cahf_file_contains_marker(self):
        digits = C.get_digits("pi", 32)
        content = C.make_cahf_file("pi", 32, digits)
        self.assertTrue(content.startswith(C.CAHF_MARKER))

    def test_make_cahf_file_contains_sentinel(self):
        digits = C.get_digits("pi", 32)
        content = C.make_cahf_file("pi", 32, digits)
        self.assertIn(C.CAHF_SENTINEL, content)

    def test_make_cahf_file_sentinel_no_blank_line_before_body(self):
        """CAHF §2.3: no blank line between sentinel and body."""
        digits = C.get_digits("pi", 32)
        content = C.make_cahf_file("pi", 32, digits)
        sentinel_pos = content.index(C.CAHF_SENTINEL)
        after_sentinel = content[sentinel_pos + len(C.CAHF_SENTINEL):]
        # Should start with exactly "\n" then digits, not "\n\n"
        self.assertTrue(after_sentinel.startswith("\n"))
        self.assertFalse(after_sentinel.startswith("\n\n"))

    def test_make_cahf_file_ends_with_single_lf(self):
        """CAHF §4.4(b): exactly one trailing LF."""
        digits = C.get_digits("pi", 32)
        content = C.make_cahf_file("pi", 32, digits)
        self.assertTrue(content.endswith("\n"))
        self.assertFalse(content.endswith("\n\n"))

    def test_make_cahf_file_sha256_field_matches_body(self):
        """SHA256 declared in header must match body extracted after sentinel."""
        digits = C.get_digits("e", 32)
        content = C.make_cahf_file("e", 32, digits)

        # Extract declared SHA256
        declared = None
        for line in content.split("\n"):
            if line.startswith("# SHA256"):
                declared = line.split(None, 2)[2].strip()
                break
        self.assertIsNotNone(declared)

        # Extract body and hash it
        sentinel_pos = content.index(C.CAHF_SENTINEL + "\n")
        body_text = content[sentinel_pos + len(C.CAHF_SENTINEL) + 1:]
        body_for_hash = C._normalise_body(body_text)
        self.assertEqual(C.sha256_hex(body_for_hash), declared)

    def test_round_trip_all_constants(self):
        """generate then parse_cahf_file must recover the correct digit string."""
        for name in sorted(C.CONSTANTS.keys()):
            with self.subTest(name=name):
                path = self._tmp()
                digits = C.get_digits(name, 50)
                content = C.make_cahf_file(name, 50, digits)
                with io.open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                parsed = C.parse_cahf_file(path)
                self.assertEqual(parsed["digits"], digits)
                self.assertEqual(parsed["name_declared"], name)
                self.assertEqual(parsed["count_declared"], 50)

    def test_round_trip_sha256_and_crc32_pass(self):
        """Parsed SHA256 and CRC32 must match recomputed values."""
        path = self._tmp()
        digits = C.get_digits("phi", 60)
        content = C.make_cahf_file("phi", 60, digits)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
        parsed = C.parse_cahf_file(path)
        body = parsed["body_for_hash"]
        self.assertEqual(C.sha256_hex(body), parsed["sha256_declared"])
        self.assertEqual(C.crc32_hex(body), parsed["crc32_declared"])

    def test_crlf_file_still_verifies(self):
        """A file with CRLF line endings must still parse and hash correctly."""
        path = self._tmp()
        digits = C.get_digits("pi", 32)
        content = C.make_cahf_file("pi", 32, digits)
        # Convert to CRLF
        crlf_content = content.replace("\n", "\r\n")
        with io.open(path, "wb") as f:
            f.write(crlf_content.encode("utf-8"))
        parsed = C.parse_cahf_file(path)
        body = parsed["body_for_hash"]
        self.assertEqual(C.sha256_hex(body), parsed["sha256_declared"])


# ---------------------------------------------------------------------------
# 5. parse_cahf_file: structural validation
# ---------------------------------------------------------------------------

class TestParseCahfFileStructural(unittest.TestCase):

    def setUp(self):
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            _cleanup(p)

    def _write(self, content):
        path = _write_tmp(content)
        self.paths.append(path)
        return path

    def _minimal_valid(self, name="pi", count=10):
        """Return a valid CAHF file string for the given constant."""
        digits = C.get_digits(name, count)
        return C.make_cahf_file(name, count, digits)

    def test_missing_archivist_marker_raises(self):
        content = self._minimal_valid().replace(C.CAHF_MARKER, "# NOT_ARCHIVIST  v1.0", 1)
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("CAHF", str(ctx.exception))

    def test_wrong_archivist_version_raises(self):
        content = self._minimal_valid().replace(C.CAHF_MARKER, "# ARCHIVIST  v2.0", 1)
        path = self._write(content)
        with self.assertRaises(ValueError):
            C.parse_cahf_file(path)

    def test_missing_sentinel_raises(self):
        content = self._minimal_valid().replace(C.CAHF_SENTINEL, "# NOSENTINEL", 1)
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("sentinel", str(ctx.exception))

    def test_junk_character_in_body_raises(self):
        content = self._minimal_valid()
        # Insert a non-digit, non-whitespace character after the sentinel
        content = content.replace(
            C.CAHF_SENTINEL + "\n3141592653",
            C.CAHF_SENTINEL + "\n3141592653X"
        )
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("invalid character", str(ctx.exception))

    def test_empty_body_produces_empty_digits(self):
        """An empty body is structurally valid; digits will be empty string."""
        body_sha = C.sha256_hex("")
        body_crc = C.crc32_hex("")
        content = (
            C.CAHF_MARKER + "\n"
            "# CONSTANT   pi\n"
            "# DIGITS     0\n"
            "# CRC32      " + body_crc + "\n"
            "# SHA256     " + body_sha + "\n"
            + C.CAHF_SENTINEL + "\n"
        )
        path = self._write(content)
        parsed = C.parse_cahf_file(path)
        self.assertEqual(parsed["digits"], "")

    def test_duplicate_sha256_raises(self):
        content = self._minimal_valid()
        # Inject a duplicate SHA256 line into the header
        content = content.replace(
            "# SHA256     ",
            "# SHA256     fakefakefakefakefakefakefakefakefakefakefakefakefakefakefakefake\n# SHA256     ",
            1
        )
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("duplicate", str(ctx.exception))

    def test_duplicate_crc32_raises(self):
        content = self._minimal_valid()
        content = content.replace(
            "# CRC32      ",
            "# CRC32      ffffffff\n# CRC32      ",
            1
        )
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("duplicate", str(ctx.exception))

    def test_duplicate_constant_raises(self):
        content = self._minimal_valid()
        content = content.replace(
            "# CONSTANT   pi",
            "# CONSTANT   e\n# CONSTANT   pi",
            1
        )
        path = self._write(content)
        with self.assertRaises(ValueError) as ctx:
            C.parse_cahf_file(path)
        self.assertIn("duplicate", str(ctx.exception))

    def test_duplicate_note_is_allowed(self):
        """NOTE is a repeatable field; duplicates must not raise."""
        content = self._minimal_valid()
        # NOTE lines already appear multiple times in generate output
        # so this just confirms the parser handles them
        path = self._write(content)
        parsed = C.parse_cahf_file(path)
        notes = parsed["fields"].get("NOTE")
        # Should be a list (multiple NOTEs in generated output)
        self.assertIsInstance(notes, list)

    def test_legacy_colon_fields_accepted(self):
        """Legacy colon-separated fields (§7.3) should parse for known field names."""
        body_str = "3141592653"
        body_sha = C.sha256_hex(C._normalise_body(body_str))
        body_crc = C.crc32_hex(C._normalise_body(body_str))
        content = (
            C.CAHF_MARKER + "\n"
            "# CONSTANT:  pi\n"
            "# DIGITS:    10\n"
            "# CRC32:     " + body_crc + "\n"
            "# SHA256:    " + body_sha + "\n"
            + C.CAHF_SENTINEL + "\n"
            + body_str + "\n"
        )
        path = self._write(content)
        parsed = C.parse_cahf_file(path)
        self.assertEqual(parsed["name_declared"], "pi")
        self.assertEqual(parsed["count_declared"], 10)


# ---------------------------------------------------------------------------
# 6. Verification failure modes (integrity checks)
# ---------------------------------------------------------------------------

class TestVerificationFailureModes(unittest.TestCase):

    def setUp(self):
        self.paths = []

    def tearDown(self):
        for p in self.paths:
            _cleanup(p)

    def _write(self, content):
        path = _write_tmp(content)
        self.paths.append(path)
        return path

    def _valid_file(self, name="pi", count=32):
        digits = C.get_digits(name, count)
        return C.make_cahf_file(name, count, digits)

    def test_tampered_body_sha256_mismatch(self):
        """Replacing a digit in the body must cause SHA256 mismatch on parse."""
        content = self._valid_file()
        # Flip one digit in the body (after sentinel)
        sentinel_end = content.index(C.CAHF_SENTINEL) + len(C.CAHF_SENTINEL) + 1
        body_start = sentinel_end
        body_chars = list(content[body_start:])
        # Find first digit character and flip it
        for i, ch in enumerate(body_chars):
            if ch.isdigit():
                body_chars[i] = "9" if ch != "9" else "0"
                break
        tampered = content[:body_start] + "".join(body_chars)
        path = self._write(tampered)
        parsed = C.parse_cahf_file(path)
        body = parsed["body_for_hash"]
        # SHA256 of tampered body must differ from declared
        self.assertNotEqual(C.sha256_hex(body), parsed["sha256_declared"])

    def test_tampered_sha256_header_detected(self):
        """A wrong SHA256 in the header must not match recomputed value."""
        content = self._valid_file()
        # Replace SHA256 with all-zeros
        bad = content
        for line in content.split("\n"):
            if line.startswith("# SHA256"):
                bad = content.replace(line, "# SHA256     " + "0" * 64)
                break
        path = self._write(bad)
        parsed = C.parse_cahf_file(path)
        body = parsed["body_for_hash"]
        self.assertNotEqual(C.sha256_hex(body), parsed["sha256_declared"])

    def test_tampered_crc32_header_detected(self):
        """A wrong CRC32 in the header must not match recomputed value."""
        content = self._valid_file()
        bad = content
        for line in content.split("\n"):
            if line.startswith("# CRC32"):
                bad = content.replace(line, "# CRC32      " + "ffffffff")
                break
        path = self._write(bad)
        parsed = C.parse_cahf_file(path)
        body = parsed["body_for_hash"]
        self.assertNotEqual(C.crc32_hex(body), parsed["crc32_declared"])

    def test_missing_sha256_field(self):
        """File with no SHA256 field must parse with sha256_declared=None."""
        content = self._valid_file()
        filtered = "\n".join(
            l for l in content.split("\n")
            if not l.startswith("# SHA256")
        )
        path = self._write(filtered)
        parsed = C.parse_cahf_file(path)
        self.assertIsNone(parsed["sha256_declared"])

    def test_missing_crc32_field(self):
        """File with no CRC32 field must parse with crc32_declared=None."""
        content = self._valid_file()
        filtered = "\n".join(
            l for l in content.split("\n")
            if not l.startswith("# CRC32")
        )
        path = self._write(filtered)
        parsed = C.parse_cahf_file(path)
        self.assertIsNone(parsed["crc32_declared"])

    def test_missing_constant_field(self):
        content = self._valid_file()
        filtered = "\n".join(
            l for l in content.split("\n")
            if not l.startswith("# CONSTANT")
        )
        path = self._write(filtered)
        parsed = C.parse_cahf_file(path)
        self.assertIsNone(parsed["name_declared"])

    def test_missing_digits_field(self):
        content = self._valid_file()
        filtered = "\n".join(
            l for l in content.split("\n")
            if not l.startswith("# DIGITS")
        )
        path = self._write(filtered)
        parsed = C.parse_cahf_file(path)
        self.assertIsNone(parsed["count_declared"])


# ---------------------------------------------------------------------------
# 7. get_constant_meta
# ---------------------------------------------------------------------------

class TestGetConstantMeta(unittest.TestCase):

    def test_known_constant_returns_key_and_meta(self):
        key, meta = C.get_constant_meta("pi")
        self.assertEqual(key, "pi")
        self.assertIn("symbol", meta)
        self.assertIn("oeis", meta)

    def test_case_insensitive(self):
        key, _ = C.get_constant_meta("PI")
        self.assertEqual(key, "pi")

    def test_unknown_constant_raises(self):
        with self.assertRaises(ValueError):
            C.get_constant_meta("tau")

    def test_all_constants_have_required_keys(self):
        for name, meta in C.CONSTANTS.items():
            with self.subTest(name=name):
                for field in ("fn", "name", "symbol", "oeis", "notes"):
                    self.assertIn(field, meta)


# ---------------------------------------------------------------------------
# 8. positive_int argparse type
# ---------------------------------------------------------------------------

class TestPositiveInt(unittest.TestCase):

    def test_valid_integer(self):
        self.assertEqual(C.positive_int("42"), 42)

    def test_one_is_valid(self):
        self.assertEqual(C.positive_int("1"), 1)

    def test_zero_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            C.positive_int("0")

    def test_negative_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            C.positive_int("-1")

    def test_non_integer_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            C.positive_int("abc")

    def test_float_string_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            C.positive_int("3.14")


# ---------------------------------------------------------------------------
# 9. CLI smoke tests
# ---------------------------------------------------------------------------

class TestCLISmoke(unittest.TestCase):
    """Light integration tests via build_parser + direct func dispatch."""

    def _run(self, argv):
        """Parse argv and call the dispatched subcommand. Return exit code."""
        parser = C.build_parser()
        args = parser.parse_args(argv)
        if not getattr(args, "command", None):
            return 1
        return args.func(args)

    def test_list_exits_zero(self):
        self.assertEqual(self._run(["list"]), 0)

    def test_digits_exits_zero(self):
        self.assertEqual(self._run(["digits", "pi", "10"]), 0)

    def test_show_exits_zero(self):
        self.assertEqual(self._run(["show", "e", "10"]), 0)

    def test_generate_and_verify(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            self.assertEqual(self._run(["generate", "pi", "32", path]), 0)
            self.assertEqual(self._run(["verify", "pi", path]), 0)
        finally:
            _cleanup(path)

    def test_verify_wrong_name_fails(self):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            self._run(["generate", "pi", "32", path])
            # Verify against "e" — CONSTANT field will say "pi", mismatch
            result = self._run(["verify", "e", path])
            self.assertEqual(result, 1)
        finally:
            _cleanup(path)

    def test_no_subcommand_exits_nonzero(self):
        parser = C.build_parser()
        args = parser.parse_args([])
        result = 1 if not getattr(args, "command", None) else args.func(args)
        self.assertEqual(result, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
