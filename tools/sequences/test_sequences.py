#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for sequences.py"""

from __future__ import print_function, unicode_literals

import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.sequences.sequences import (
    SEQUENCES,
    OEIS_BASE,
    REQUEST_DELAY,
    _fetch,
    fetch_bfile,
    fetch_metadata,
    make_sequence_file,
    parse_sequence_file,
    seq_path,
    is_cached,
    positive_int,
    cmd_list,
    cmd_show,
    cmd_terms,
    cmd_sync,
    cmd_verify,
    build_parser,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _args(**kw):
    class NS(object):
        pass
    a = NS()
    for k, v in kw.items():
        setattr(a, k, v)
    return a


class TempDir(object):
    def __enter__(self):
        self.path = tempfile.mkdtemp()
        return self.path

    def __exit__(self, *_):
        import shutil
        shutil.rmtree(self.path, ignore_errors=True)


def _write(path, content):
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


SAMPLE_METADATA = {
    "id":          "A000796",
    "name":        "Decimal expansion of Pi",
    "description": "",
    "offset":      "1,1",
    "keyword":     "nonn,cons,nice",
    "data":        "3,1,4,1,5,9",
}

SAMPLE_TERMS = [(i + 1, d) for i, d in enumerate([3, 1, 4, 1, 5, 9, 2, 6, 5, 3])]

SAMPLE_LOCAL = {
    "notes": "Digits of pi. IV source.",
    "tags":  ["constant", "iv-source"],
}


# ---------------------------------------------------------------------------
# SEQUENCES registry
# ---------------------------------------------------------------------------

class TestRegistry(unittest.TestCase):

    def test_registry_nonempty(self):
        self.assertGreater(len(SEQUENCES), 0)

    def test_all_ids_start_with_A(self):
        for seq_id in SEQUENCES:
            self.assertTrue(seq_id.startswith("A"),
                            "{0} does not start with A".format(seq_id))

    def test_all_ids_have_name(self):
        for seq_id, meta in SEQUENCES.items():
            self.assertIn("name", meta)
            self.assertTrue(meta["name"],
                            "{0} has empty name".format(seq_id))

    def test_all_ids_have_tags(self):
        for seq_id, meta in SEQUENCES.items():
            self.assertIn("tags", meta)
            self.assertIsInstance(meta["tags"], list)

    def test_registry_count_matches_readme(self):
        # README documents 15 sequences; keep in sync
        self.assertEqual(len(SEQUENCES), 15)


# ---------------------------------------------------------------------------
# fetch_bfile URL construction
# ---------------------------------------------------------------------------

class TestFetchBfileURL(unittest.TestCase):
    """Verify URL is assembled correctly without making network calls."""

    def _capture_url(self, seq_id):
        captured = []

        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch

        def fake_fetch(url, retries=3):
            captured.append(url)
            # Return minimal valid b-file content
            return "1 2\n2 3\n3 5\n"

        seq_mod._fetch = fake_fetch
        try:
            fetch_bfile(seq_id)
        finally:
            seq_mod._fetch = original

        return captured[0]

    def test_url_pi(self):
        url = self._capture_url("A000796")
        self.assertEqual(url, "{0}/A000796/b000796.txt".format(OEIS_BASE))

    def test_url_primes(self):
        url = self._capture_url("A000040")
        self.assertEqual(url, "{0}/A000040/b000040.txt".format(OEIS_BASE))

    def test_url_preserves_leading_zeros(self):
        # OEIS uses 6-digit zero-padded numbers; must NOT strip leading zeros
        url = self._capture_url("A000045")
        self.assertIn("b000045.txt", url)
        self.assertNotIn("b45.txt", url)

    def test_parses_two_column_lines(self):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: "1 2\n2 3\n3 5\n"
        try:
            terms = fetch_bfile("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(terms, [(1, 2), (2, 3), (3, 5)])

    def test_skips_comment_lines(self):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: "# comment\n1 2\n2 3\n"
        try:
            terms = fetch_bfile("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(len(terms), 2)

    def test_skips_blank_lines(self):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: "\n1 2\n\n2 3\n\n"
        try:
            terms = fetch_bfile("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(len(terms), 2)

    def test_skips_malformed_lines(self):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: "1 2\nnot_a_number\n3 5\n"
        try:
            terms = fetch_bfile("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(len(terms), 2)

    def test_returns_empty_on_no_data(self):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: "# only comments\n"
        try:
            terms = fetch_bfile("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(terms, [])


# ---------------------------------------------------------------------------
# _fetch retry behaviour
# ---------------------------------------------------------------------------

class TestFetch(unittest.TestCase):
    """Tests for the _fetch helper - exercises retry and HTTP error handling."""

    def setUp(self):
        import tools.sequences.sequences as seq_mod
        self._seq_mod      = seq_mod
        self._orig_urlopen = seq_mod.urlopen
        self._orig_sleep   = seq_mod.time.sleep
        self._sleep_calls  = []
        seq_mod.time.sleep = lambda t: self._sleep_calls.append(t)

    def tearDown(self):
        self._seq_mod.urlopen    = self._orig_urlopen
        self._seq_mod.time.sleep = self._orig_sleep

    def _set_urlopen(self, fake):
        self._seq_mod.urlopen = fake

    def test_404_raises_immediately_without_retry(self):
        # A 404 is a permanent client error; must not be retried.
        call_count = [0]
        HTTPError = self._seq_mod.HTTPError

        def fake_urlopen(req, timeout=30):
            call_count[0] += 1
            raise HTTPError(req.get_full_url(), 404, "Not Found", {}, None)

        self._set_urlopen(fake_urlopen)
        with self.assertRaises(IOError):
            self._seq_mod._fetch("https://oeis.org/test")

        self.assertEqual(call_count[0], 1, "404 must not be retried")
        self.assertEqual(self._sleep_calls, [], "no retry sleep on 404")

    def test_403_raises_immediately_without_retry(self):
        call_count = [0]
        HTTPError = self._seq_mod.HTTPError

        def fake_urlopen(req, timeout=30):
            call_count[0] += 1
            raise HTTPError(req.get_full_url(), 403, "Forbidden", {}, None)

        self._set_urlopen(fake_urlopen)
        with self.assertRaises(IOError):
            self._seq_mod._fetch("https://oeis.org/test")

        self.assertEqual(call_count[0], 1)
        self.assertEqual(self._sleep_calls, [])

    def test_500_is_retried(self):
        call_count = [0]
        HTTPError = self._seq_mod.HTTPError

        def fake_urlopen(req, timeout=30):
            call_count[0] += 1
            raise HTTPError(req.get_full_url(), 500, "Internal Server Error", {}, None)

        self._set_urlopen(fake_urlopen)
        with self.assertRaises(IOError):
            self._seq_mod._fetch("https://oeis.org/test", retries=3)

        self.assertEqual(call_count[0], 3, "500 should be retried up to retries times")

    def test_429_is_retried(self):
        call_count = [0]
        HTTPError = self._seq_mod.HTTPError

        def fake_urlopen(req, timeout=30):
            call_count[0] += 1
            raise HTTPError(req.get_full_url(), 429, "Too Many Requests", {}, None)

        self._set_urlopen(fake_urlopen)
        with self.assertRaises(IOError):
            self._seq_mod._fetch("https://oeis.org/test", retries=3)

        self.assertEqual(call_count[0], 3, "429 should be retried up to retries times")

    def test_404_error_message_includes_status_code(self):
        HTTPError = self._seq_mod.HTTPError

        def fake_urlopen(req, timeout=30):
            raise HTTPError(req.get_full_url(), 404, "Not Found", {}, None)

        self._set_urlopen(fake_urlopen)
        try:
            self._seq_mod._fetch("https://oeis.org/test")
            self.fail("expected IOError")
        except IOError as e:
            self.assertIn("404", str(e))


# ---------------------------------------------------------------------------
# fetch_metadata
# ---------------------------------------------------------------------------

class TestFetchMetadata(unittest.TestCase):

    def _fake_response(self, data):
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: data
        try:
            return fetch_metadata("A000796")
        finally:
            seq_mod._fetch = original

    def test_parses_dict_response(self):
        import json
        payload = json.dumps({"results": [{"number": 796, "name": "Pi digits",
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1,4"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["id"], "A000796")
        self.assertEqual(result["name"], "Pi digits")

    def test_parses_list_response(self):
        import json
        payload = json.dumps([{"number": 796, "name": "Pi digits",
                               "comment": [], "offset": "1,1",
                               "keyword": "nonn", "data": "3,1,4"}])
        result = self._fake_response(payload)
        self.assertEqual(result["id"], "A000796")

    def test_raises_on_empty_results_dict(self):
        import json
        payload = json.dumps({"results": []})
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: payload
        try:
            with self.assertRaises(ValueError):
                fetch_metadata("A000796")
        finally:
            seq_mod._fetch = original

    def test_raises_on_empty_results_list(self):
        import json
        payload = json.dumps([])
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: payload
        try:
            with self.assertRaises(ValueError):
                fetch_metadata("A000796")
        finally:
            seq_mod._fetch = original

    def test_non_dict_non_list_response_raises_value_error(self):
        import json
        # OEIS returning null JSON must raise ValueError, not AttributeError
        for payload in [json.dumps(None), json.dumps("Not found"), json.dumps(42)]:
            import tools.sequences.sequences as seq_mod
            original = seq_mod._fetch
            seq_mod._fetch = lambda url, retries=3, p=payload: p
            try:
                with self.assertRaises(ValueError):
                    fetch_metadata("A000796")
            finally:
                seq_mod._fetch = original

    def test_non_dict_result_element_raises_value_error(self):
        import json
        # OEIS returning {"results": [null]} must raise ValueError, not AttributeError.
        # results[0].get(...) would crash if results[0] is not a dict.
        for value in [None, "string", 42]:
            payload = json.dumps({"results": [value]})
            import tools.sequences.sequences as seq_mod
            original = seq_mod._fetch
            seq_mod._fetch = lambda url, retries=3, p=payload: p
            try:
                with self.assertRaises(ValueError):
                    fetch_metadata("A000796")
            finally:
                seq_mod._fetch = original

    def test_null_name_field_does_not_crash(self):
        import json
        # r.get("name", "") returns None when the key exists with null value;
        # _oneline(None) then raises AttributeError.  Use `or ""` instead.
        payload = json.dumps({"results": [{"number": 796, "name": None,
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1,4"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["name"], "")

    def test_null_offset_field_does_not_crash(self):
        import json
        payload = json.dumps({"results": [{"number": 796, "name": "Pi",
                                           "comment": [], "offset": None,
                                           "keyword": "nonn", "data": "3,1,4"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["offset"], "0")

    def test_null_keyword_field_does_not_crash(self):
        import json
        payload = json.dumps({"results": [{"number": 796, "name": "Pi",
                                           "comment": [], "offset": "1,1",
                                           "keyword": None, "data": "3,1,4"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["keyword"], "")

    def test_null_comment_field_does_not_raise(self):
        import json
        # OEIS could theoretically return "comment": null; must not raise TypeError
        payload = json.dumps({"results": [{"number": 796, "name": "Pi digits",
                                           "comment": None, "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1,4"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["description"], "")

    def test_comment_list_with_non_string_items_does_not_raise(self):
        import json
        # "comment": null is handled by `or []`, but "comment": [null] is not —
        # [None] is truthy so `or []` does not fire, and str.join([None]) raises
        # TypeError which is uncaught in cmd_sync and main.  str(c) coercion fixes it.
        for comment in [[None], [42], [None, "valid text"]]:
            payload = json.dumps({"results": [{"number": 796, "name": "Pi",
                                               "comment": comment, "offset": "1,1",
                                               "keyword": "nonn", "data": "3,1"}]})
            result = self._fake_response(payload)
            self.assertIsInstance(result["description"], str)

    def test_raises_on_missing_number_field(self):
        import json
        payload = json.dumps({"results": [{"name": "Pi digits",
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1,4"}]})
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: payload
        try:
            with self.assertRaises(ValueError):
                fetch_metadata("A000796")
        finally:
            seq_mod._fetch = original

    def test_id_zero_padded(self):
        import json
        payload = json.dumps({"results": [{"number": 40, "name": "Primes",
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "2,3"}]})
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: payload
        try:
            result = fetch_metadata("A000040")
        finally:
            seq_mod._fetch = original
        self.assertEqual(result["id"], "A000040")

    def test_number_as_string_is_coerced_to_int(self):
        import json
        # OEIS might return "number" as a JSON string rather than integer;
        # the code must coerce it rather than letting {:06d} raise ValueError.
        payload = json.dumps({"results": [{"number": "796", "name": "Pi",
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1"}]})
        result = self._fake_response(payload)
        self.assertEqual(result["id"], "A000796")

    def test_non_integer_number_raises_value_error(self):
        import json
        payload = json.dumps({"results": [{"number": "not_a_number", "name": "Pi",
                                           "comment": [], "offset": "1,1",
                                           "keyword": "nonn", "data": "3,1"}]})
        import tools.sequences.sequences as seq_mod
        original = seq_mod._fetch
        seq_mod._fetch = lambda url, retries=3: payload
        try:
            with self.assertRaises(ValueError):
                fetch_metadata("A000796")
        finally:
            seq_mod._fetch = original


# ---------------------------------------------------------------------------
# make_sequence_file
# ---------------------------------------------------------------------------

class TestMakeSequenceFile(unittest.TestCase):

    def setUp(self):
        self.content = make_sequence_file(
            "A000796", SAMPLE_METADATA, SAMPLE_TERMS, SAMPLE_LOCAL)

    def test_header_contains_seq_id(self):
        self.assertIn("A000796", self.content)

    def test_header_contains_name(self):
        self.assertIn("Decimal expansion of Pi", self.content)

    def test_header_contains_sha256(self):
        self.assertIn("SHA256:", self.content)

    def test_header_contains_term_count(self):
        self.assertIn("Terms:    {0}".format(len(SAMPLE_TERMS)), self.content)

    def test_header_contains_oeis_url(self):
        self.assertIn("https://oeis.org/A000796", self.content)

    def test_header_contains_tags(self):
        self.assertIn("constant", self.content)
        self.assertIn("iv-source", self.content)

    def test_header_contains_notes(self):
        self.assertIn("Digits of pi", self.content)

    def test_body_comma_separated(self):
        # Non-comment non-empty line is the body
        body_lines = [l for l in self.content.splitlines()
                      if l and not l.startswith("#")]
        self.assertEqual(len(body_lines), 1)
        values = [v.strip() for v in body_lines[0].split(",")]
        self.assertEqual(values, [str(t) for _, t in SAMPLE_TERMS])

    def test_no_em_dash_in_output(self):
        self.assertNotIn("—", self.content)

    def test_without_local_meta(self):
        content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
        self.assertIn("A000796", content)
        self.assertIn("SHA256:", content)

    def test_missing_name_key_uses_empty_string(self):
        meta_no_name = {k: v for k, v in SAMPLE_METADATA.items() if k != "name"}
        content = make_sequence_file("A000796", meta_no_name, SAMPLE_TERMS)
        self.assertIn("A000796", content)

    def test_empty_terms_produces_empty_body(self):
        content = make_sequence_file("A000796", SAMPLE_METADATA, [])
        body_lines = [l for l in content.splitlines()
                      if l and not l.startswith("#")]
        self.assertEqual(body_lines, [])

    def test_sha256_in_header_matches_body(self):
        import hashlib
        body_lines = [l for l in self.content.splitlines()
                      if l and not l.startswith("#")]
        body = ", ".join(v.strip() for v in body_lines[0].split(","))
        expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
        for line in self.content.splitlines():
            if "SHA256:" in line:
                declared = line.split("SHA256:")[-1].strip()
                self.assertEqual(declared, expected)
                return
        self.fail("SHA256 line not found in header")


# ---------------------------------------------------------------------------
# parse_sequence_file
# ---------------------------------------------------------------------------

class TestParseSequenceFile(unittest.TestCase):

    def _make_file(self, content):
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        _write(path, content)
        return path

    def tearDown(self):
        pass  # paths cleaned up per-test

    def _roundtrip(self, terms=None, local=None):
        if terms is None:
            terms = SAMPLE_TERMS
        content = make_sequence_file("A000796", SAMPLE_METADATA, terms, local)
        path = self._make_file(content)
        try:
            return parse_sequence_file(path)
        finally:
            os.unlink(path)

    def test_roundtrip_seq_id(self):
        result = self._roundtrip()
        self.assertEqual(result["seq_id"], "A000796")

    def test_roundtrip_term_count(self):
        result = self._roundtrip()
        self.assertEqual(result["term_count"], len(SAMPLE_TERMS))

    def test_roundtrip_terms(self):
        result = self._roundtrip()
        self.assertEqual(result["terms"], [t for _, t in SAMPLE_TERMS])

    def test_roundtrip_sha256_ok_true(self):
        result = self._roundtrip()
        self.assertIs(result["sha256_ok"], True)

    def test_sha256_ok_false_on_tampered_body(self):
        content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
        lines = content.splitlines()
        # Replace body line (last non-comment non-empty line) with garbage
        for i in range(len(lines) - 1, -1, -1):
            if lines[i] and not lines[i].startswith("#"):
                lines[i] = "0, 0, 0"
                break
        path = self._make_file("\n".join(lines) + "\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIs(result["sha256_ok"], False)

    def test_sha256_ok_none_when_no_header(self):
        path = self._make_file("3, 1, 4, 1, 5, 9\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIsNone(result["sha256_ok"])
        self.assertIsNone(result["sha256_declared"])

    def test_sha256_ok_none_when_header_value_empty(self):
        # "# SHA256:" with no value must produce sha256_ok=None (SKIP),
        # not sha256_ok=False (FAIL).  An empty field means "not computed".
        for line in ["# SHA256:", "# SHA256:   ", "# SHA256:\t"]:
            path = self._make_file("{0}\n3, 1, 4\n".format(line))
            try:
                result = parse_sequence_file(path)
            finally:
                os.unlink(path)
            self.assertIsNone(
                result["sha256_ok"],
                "sha256_ok should be None for empty declared hash, got {0!r} "
                "from {1!r}".format(result["sha256_ok"], line)
            )

    def test_seq_id_extracted_correctly(self):
        path = self._make_file("# A000040 - Prime numbers\n# SHA256: abc\n2, 3, 5\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["seq_id"], "A000040")

    def test_seq_id_none_when_no_title(self):
        path = self._make_file("# SHA256: abc\n2, 3, 5\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIsNone(result["seq_id"])

    def test_sha256_not_extracted_from_notes_field(self):
        # "SHA256:" appearing inside a Notes line must not overwrite the real hash
        content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
        content += ""  # inject a notes-style line after the real header
        # Build a file where Notes contains "SHA256: garbage"
        injected = content.rstrip("\n") + "\n# Notes:    Check SHA256: not_a_real_hash\n\n"
        path = self._make_file(injected)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIs(result["sha256_ok"], True,
                      "sha256_ok should be True; Notes field must not override SHA256 header")

    def test_term_count_not_extracted_from_notes_field(self):
        # "Terms:" appearing inside a Notes line must not overwrite the real count
        content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
        injected = content.rstrip("\n") + "\n# Notes:    There are Terms: 9999 here\n\n"
        path = self._make_file(injected)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["term_count"], len(SAMPLE_TERMS),
                         "term_count must come from # Terms: header, not Notes field")

    def test_seq_id_not_affected_by_separator_style(self):
        # seq_id extraction must not depend on em dash
        path = self._make_file("# A000796 - Name with hyphen\n2, 3\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["seq_id"], "A000796")

    def test_sha256_uppercase_declared_still_passes(self):
        # sha256_declared with uppercase hex must not cause spurious FAIL
        content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
        # Uppercase the SHA256 value in the header
        import re
        content = re.sub(
            r"(# SHA256:   )([0-9a-f]+)",
            lambda m: m.group(1) + m.group(2).upper(),
            content)
        fd, path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        _write(path, content)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIs(result["sha256_ok"], True,
                      "uppercase SHA256 in header must still verify as True")

    def test_terms_are_integers(self):
        result = self._roundtrip()
        for t in result["terms"]:
            self.assertIsInstance(t, int)

    def test_empty_file_returns_empty_terms(self):
        path = self._make_file("")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["terms"], [])

    def test_only_comments_returns_empty_terms(self):
        path = self._make_file("# comment only\n# another\n")
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["terms"], [])

    def test_newline_in_name_does_not_inject_header_line(self):
        # If the OEIS API returns a name containing "\n# SHA256: wrong_hash",
        # the generated file must have exactly one non-comment data line and
        # sha256_ok must still be True after round-trip.
        # Without sanitization, the first-match-wins SHA256 guard would capture
        # the injected hash instead of the real one, producing a spurious FAIL.
        wrong_hash = "a" * 64
        injected_name = "Decimal expansion of Pi\n# SHA256:   {0}".format(wrong_hash)
        meta = dict(SAMPLE_METADATA, name=injected_name)
        content = make_sequence_file("A000796", meta, SAMPLE_TERMS, SAMPLE_LOCAL)

        # File must have exactly one non-comment non-empty line (the body)
        body_lines = [l for l in content.splitlines()
                      if l and not l.startswith("#")]
        self.assertEqual(len(body_lines), 1,
                         "newline in name must not create extra body lines")

        path = self._make_file(content)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIs(result["sha256_ok"], True,
                      "newline-injected name must not cause spurious sha256 FAIL")

    def test_first_sha256_header_wins_not_last(self):
        # If a file has two # SHA256: lines, the FIRST must be used.
        # An appended "correct" SHA256 line must not bypass a mismatch in
        # the original declared hash (integrity bypass via header injection).
        import hashlib
        body_terms = [str(t) for _, t in SAMPLE_TERMS]
        correct_hash = hashlib.sha256(
            ", ".join(body_terms).encode("utf-8")).hexdigest()
        wrong_hash = "a" * 64
        # File: wrong hash declared first, correct hash appended second.
        # sha256_ok must be False (first hash wins, and it's wrong).
        content = (
            "# A000796 - Pi\n"
            "# SHA256:   {0}\n"
            "# SHA256:   {1}\n"
            "\n"
            "{2}\n"
        ).format(wrong_hash, correct_hash, ", ".join(body_terms))
        path = self._make_file(content)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertIs(result["sha256_ok"], False,
                      "first # SHA256: line must win; appended correct hash must not override")

    def test_first_term_count_header_wins_not_last(self):
        # If a file has two # Terms: lines, the FIRST must be used.
        content = (
            "# A000796 - Pi\n"
            "# Terms:    9999\n"
            "# Terms:    {0}\n"
            "\n"
            "{1}\n"
        ).format(len(SAMPLE_TERMS), ", ".join(str(t) for _, t in SAMPLE_TERMS))
        path = self._make_file(content)
        try:
            result = parse_sequence_file(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["term_count"], 9999,
                         "first # Terms: line must win; appended correct count must not override")


# ---------------------------------------------------------------------------
# seq_path / is_cached
# ---------------------------------------------------------------------------

class TestSeqPath(unittest.TestCase):

    def test_path_format(self):
        self.assertEqual(seq_path("A000796", "/tmp/seq"), "/tmp/seq/A000796.txt")

    def test_is_cached_false_when_missing(self):
        with TempDir() as d:
            self.assertFalse(is_cached("A000796", d))

    def test_is_cached_true_when_present(self):
        with TempDir() as d:
            path = seq_path("A000796", d)
            _write(path, "# content\n")
            self.assertTrue(is_cached("A000796", d))


# ---------------------------------------------------------------------------
# positive_int
# ---------------------------------------------------------------------------

class TestPositiveInt(unittest.TestCase):

    def test_valid(self):
        self.assertEqual(positive_int("1"), 1)
        self.assertEqual(positive_int("100"), 100)

    def test_zero_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("0")

    def test_negative_raises(self):
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            positive_int("-1")


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

class TestCmdList(unittest.TestCase):

    def test_runs_without_error(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd_list()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertTrue(len(output) > 0)

    def test_output_contains_all_ids(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd_list()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        for seq_id in SEQUENCES:
            self.assertIn(seq_id, output)

    def test_output_contains_count(self):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd_list()
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn(str(len(SEQUENCES)), output)


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------

class TestCmdShow(unittest.TestCase):

    def _show(self, seq_id, out_dir):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            cmd_show(seq_id, out_dir)
            return sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

    def test_always_prints_id_and_url(self):
        with TempDir() as d:
            output = self._show("A000796", d)
        self.assertIn("A000796", output)
        self.assertIn("https://oeis.org/A000796", output)

    def test_not_cached_shows_sync_message(self):
        with TempDir() as d:
            output = self._show("A000796", d)
        self.assertIn("cached: no", output.lower())

    def test_preview_no_ellipsis_when_ten_or_fewer_terms(self):
        few_terms = SAMPLE_TERMS[:5]  # only 5 terms
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, few_terms)
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        terms_line = next((l for l in output.splitlines() if l.startswith("Terms:")), "")
        self.assertNotIn("...", terms_line)

    def test_preview_shows_ellipsis_when_more_than_ten_terms(self):
        many_terms = [(i + 1, i * i) for i in range(20)]
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, many_terms)
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        terms_line = next((l for l in output.splitlines() if l.startswith("Terms:")), "")
        self.assertIn("...", terms_line)

    def test_cached_zero_terms_shows_0_not_question_mark(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, [])
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        self.assertIn("(0 terms)", output)
        self.assertNotIn("(? terms)", output)

    def test_cached_shows_term_count(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        self.assertIn(str(len(SAMPLE_TERMS)), output)

    def test_cached_valid_sha256(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        self.assertIn("yes", output)

    def test_cached_no_header_shows_no_sha256_message(self):
        with TempDir() as d:
            _write(seq_path("A000796", d), "3, 1, 4\n")
            output = self._show("A000796", d)
        self.assertIn("no SHA256 declared", output)

    def test_unknown_id_not_in_registry_still_prints(self):
        with TempDir() as d:
            output = self._show("A999999", d)
        self.assertIn("A999999", output)

    def test_no_em_dash_in_output(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        self.assertNotIn("—", output)

    def test_shows_actual_term_count_not_declared(self):
        # If the Terms: header disagrees with the actual body count, cmd_show
        # must report the actual parsed count, not the stale header value.
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            # Overwrite Terms: header with a wrong value; leave body intact.
            content = content.replace(
                "# Terms:    {0}".format(len(SAMPLE_TERMS)),
                "# Terms:    9999")
            _write(seq_path("A000796", d), content)
            output = self._show("A000796", d)
        self.assertIn("({0} terms)".format(len(SAMPLE_TERMS)), output)
        self.assertNotIn("(9999 terms)", output)


# ---------------------------------------------------------------------------
# cmd_terms
# ---------------------------------------------------------------------------

class TestCmdTerms(unittest.TestCase):

    def _terms(self, seq_id, count, out_dir):
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            rc = cmd_terms(seq_id, count, out_dir)
            return rc, sys.stdout.getvalue(), sys.stderr.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def test_not_cached_returns_1(self):
        with TempDir() as d:
            rc, _, _ = self._terms("A000796", 10, d)
        self.assertEqual(rc, 1)

    def test_not_cached_prints_error(self):
        with TempDir() as d:
            _, _, err = self._terms("A000796", 10, d)
        self.assertIn("not cached", err.lower())

    def test_returns_correct_count(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            rc, out, _ = self._terms("A000796", 5, d)
        self.assertEqual(rc, 0)
        # First 5 terms should appear
        for _, t in SAMPLE_TERMS[:5]:
            self.assertIn(str(t), out)

    def test_count_larger_than_available_returns_all(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            rc, out, _ = self._terms("A000796", 10000, d)
        self.assertEqual(rc, 0)
        for _, t in SAMPLE_TERMS:
            self.assertIn(str(t), out)

    def test_no_em_dash_in_output(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            _, out, _ = self._terms("A000796", 5, d)
        self.assertNotIn("—", out)


# ---------------------------------------------------------------------------
# cmd_sync
# ---------------------------------------------------------------------------

class TestCmdSync(unittest.TestCase):

    def _make_fake_sync(self, out_dir, side_effect=None):
        """Return a cmd_sync that monkeypatches fetch calls."""
        import tools.sequences.sequences as seq_mod

        fetch_calls = []
        sleep_calls = []

        def fake_fetch_metadata(seq_id):
            fetch_calls.append(("meta", seq_id))
            return {
                "id":          seq_id,
                "name":        "Test sequence",
                "description": "",
                "offset":      "1,1",
                "keyword":     "nonn",
                "data":        "1,2,3",
            }

        def fake_fetch_bfile(seq_id):
            fetch_calls.append(("bfile", seq_id))
            if side_effect:
                raise side_effect
            return [(1, 1), (2, 2), (3, 3)]

        def fake_sleep(t):
            sleep_calls.append(t)

        orig_meta  = seq_mod.fetch_metadata
        orig_bfile = seq_mod.fetch_bfile
        orig_sleep = seq_mod.time.sleep

        seq_mod.fetch_metadata = fake_fetch_metadata
        seq_mod.fetch_bfile    = fake_fetch_bfile
        seq_mod.time.sleep     = fake_sleep

        self._restore = (seq_mod, orig_meta, orig_bfile, orig_sleep)
        return fetch_calls, sleep_calls

    def tearDown(self):
        if hasattr(self, "_restore"):
            seq_mod, orig_meta, orig_bfile, orig_sleep = self._restore
            seq_mod.fetch_metadata = orig_meta
            seq_mod.fetch_bfile    = orig_bfile
            seq_mod.time.sleep     = orig_sleep

    def test_skips_cached_without_force(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            calls, _ = self._make_fake_sync(d)
            rc = cmd_sync(["A000796"], d, force=False)
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [])  # no fetch calls made

    def test_refetches_with_force(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            calls, _ = self._make_fake_sync(d)
            rc = cmd_sync(["A000796"], d, force=True)
        self.assertEqual(rc, 0)
        self.assertIn(("meta", "A000796"), calls)
        self.assertIn(("bfile", "A000796"), calls)

    def test_creates_output_dir(self):
        import shutil
        tmproot = tempfile.mkdtemp()
        out_dir = os.path.join(tmproot, "new_subdir")
        try:
            calls, _ = self._make_fake_sync(out_dir)
            cmd_sync(["A000796"], out_dir)
            self.assertTrue(os.path.isdir(out_dir))
        finally:
            shutil.rmtree(tmproot, ignore_errors=True)

    def test_atomic_write_no_tmp_files_left_on_success(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d)
            cmd_sync(["A000796"], d)
            files = os.listdir(d)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        self.assertEqual(tmp_files, [])

    def test_writes_file_on_success(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d)
            cmd_sync(["A000796"], d)
            self.assertTrue(os.path.isfile(seq_path("A000796", d)))

    def test_sleeps_between_requests(self):
        with TempDir() as d:
            _, sleep_calls = self._make_fake_sync(d)
            cmd_sync(["A000796"], d)
        self.assertGreater(len(sleep_calls), 0)

    def test_sleeps_three_times_per_sequence(self):
        # metadata fetch -> sleep -> bfile fetch -> sleep -> write -> sleep
        # ensures a 2s gap before the next sequence's metadata fetch
        with TempDir() as d:
            _, sleep_calls = self._make_fake_sync(d)
            cmd_sync(["A000796"], d)
        self.assertEqual(len(sleep_calls), 3)

    def test_sleeps_after_failure(self):
        # A failure must also sleep before the next sequence so requests
        # don't run back-to-back after a bfile fetch error.
        with TempDir() as d:
            _, sleep_calls = self._make_fake_sync(d, side_effect=IOError("network fail"))
            cmd_sync(["A000796"], d)
        # On failure: metadata sleep + failure sleep = 2 sleeps
        # (bfile raises before the second normal sleep)
        self.assertGreaterEqual(len(sleep_calls), 2)

    def test_handles_fetch_error_gracefully(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d, side_effect=IOError("network fail"))
            rc = cmd_sync(["A000796"], d)
        self.assertEqual(rc, 1)

    def test_handles_key_error_gracefully(self):
        # KeyError from fetch_metadata (e.g. missing 'number' field) must not
        # abort the whole sync run
        import tools.sequences.sequences as seq_mod

        orig_meta  = seq_mod.fetch_metadata
        orig_sleep = seq_mod.time.sleep
        seq_mod.time.sleep = lambda t: None

        def bad_fetch_metadata(seq_id):
            raise KeyError("number")

        seq_mod.fetch_metadata = bad_fetch_metadata
        try:
            with TempDir() as d:
                rc = cmd_sync(["A000796"], d)
        finally:
            seq_mod.fetch_metadata = orig_meta
            seq_mod.time.sleep     = orig_sleep
        self.assertEqual(rc, 1)

    def test_no_ids_syncs_all_registry_sequences(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d)
            cmd_sync([], d)
        synced_ids = {sid for _, sid in calls}
        for seq_id in SEQUENCES:
            self.assertIn(seq_id, synced_ids)

    def test_sync_all_flag_targets_all_registry(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d)
            cmd_sync([], d, sync_all=True)
        synced_ids = {sid for _, sid in calls}
        for seq_id in SEQUENCES:
            self.assertIn(seq_id, synced_ids)

    def test_sync_all_skips_cached_without_force(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            calls, _ = self._make_fake_sync(d)
            cmd_sync([], d, sync_all=True, force=False)
        fetched_ids = [sid for _, sid in calls]
        self.assertNotIn("A000796", fetched_ids)

    def test_sync_all_with_explicit_ids_warns(self):
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            with TempDir() as d:
                calls, _ = self._make_fake_sync(d)
                cmd_sync(["A000796"], d, sync_all=True)
            err = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr
        self.assertIn("ignored", err.lower())

    def test_makedirs_ok_when_dir_already_exists(self):
        with TempDir() as d:
            calls, _ = self._make_fake_sync(d)
            # Call twice -- second call should not raise even though dir exists
            cmd_sync(["A000796"], d, force=True)
            cmd_sync(["A000796"], d, force=True)

    def test_sync_all_force_refetches_cached(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            calls, _ = self._make_fake_sync(d)
            cmd_sync(["A000796"], d, sync_all=True, force=True)
        fetched_ids = [sid for _, sid in calls]
        self.assertIn("A000796", fetched_ids)


# ---------------------------------------------------------------------------
# cmd_verify
# ---------------------------------------------------------------------------

class TestCmdVerify(unittest.TestCase):

    def _verify(self, ids, out_dir):
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            rc = cmd_verify(ids, out_dir)
            return rc, sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

    def test_pass_on_valid_file(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            rc, out = self._verify(["A000796"], d)
        self.assertEqual(rc, 0)
        self.assertIn("PASS", out)

    def test_fail_on_tampered_file(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            lines = content.splitlines()
            for i in range(len(lines) - 1, -1, -1):
                if lines[i] and not lines[i].startswith("#"):
                    lines[i] = "0, 0, 0"
                    break
            _write(seq_path("A000796", d), "\n".join(lines) + "\n")
            rc, out = self._verify(["A000796"], d)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)

    def test_miss_on_missing_file(self):
        with TempDir() as d:
            rc, out = self._verify(["A000796"], d)
        self.assertEqual(rc, 1)
        self.assertIn("MISS", out)

    def test_skip_on_no_header(self):
        with TempDir() as d:
            _write(seq_path("A000796", d), "3, 1, 4, 1\n")
            rc, out = self._verify(["A000796"], d)
        # No SHA256 declared -- should not count as failure
        self.assertEqual(rc, 0)
        self.assertIn("SKIP", out)

    def test_unreadable_file_counts_as_fail_not_abort(self):
        # A file that raises UnicodeDecodeError (non-UTF-8 bytes) must be
        # counted as FAIL for that file; the rest of the verify run continues.
        with TempDir() as d:
            good = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), good)
            # Write a file with raw non-UTF-8 bytes
            bad_path = seq_path("A000040", d)
            with open(bad_path, "wb") as f:
                f.write(b"# A000040 - Primes\n\xff\xfe bad bytes\n")
            rc, out = self._verify(["A000796", "A000040"], d)
        # A000796 should pass; A000040 should fail; run must not abort
        self.assertIn("PASS", out)
        self.assertIn("FAIL", out)
        self.assertEqual(rc, 1)

    def test_no_targets_when_dir_missing(self):
        rc, out = self._verify([], "/tmp/crowsong_nonexistent_seq_dir")
        self.assertEqual(rc, 0)
        self.assertIn("No cached", out)

    def test_auto_discovers_cached_files(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            rc, out = self._verify([], d)
        self.assertEqual(rc, 0)
        self.assertIn("A000796", out)

    def test_returns_1_when_any_fail(self):
        with TempDir() as d:
            good = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), good)
            _write(seq_path("A000040", d), "# A000040 - Primes\n# SHA256: badhash\n2, 3, 5\n")
            rc, _ = self._verify([], d)
        self.assertEqual(rc, 1)

    def test_roundtrip_100_terms(self):
        terms = [(i + 1, i * i) for i in range(100)]
        with TempDir() as d:
            content = make_sequence_file("A000290", SAMPLE_METADATA, terms)
            _write(seq_path("A000290", d), content)
            rc, _ = self._verify(["A000290"], d)
        self.assertEqual(rc, 0)

    def test_no_em_dash_in_output(self):
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), content)
            _, out = self._verify(["A000796"], d)
        self.assertNotIn("—", out)

    def test_fail_on_term_count_mismatch(self):
        # SHA256 matches the body, but Terms: header disagrees with actual count
        with TempDir() as d:
            content = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            # Inject wrong count into header; leave body and SHA256 unchanged
            content = content.replace(
                "# Terms:    {0}".format(len(SAMPLE_TERMS)),
                "# Terms:    9999")
            _write(seq_path("A000796", d), content)
            rc, out = self._verify(["A000796"], d)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        self.assertIn("count", out.lower())

    def test_fail_on_term_count_mismatch_without_sha256(self):
        # A file with wrong Terms header but NO SHA256 line must FAIL, not SKIP.
        # The term_count check is independent of SHA256 presence.
        with TempDir() as d:
            # Build a file with no SHA256 header and a lying Terms count
            body = "2, 3, 5"
            content = (
                "# A000040 - Primes\n"
                "#\n"
                "# Terms:    9999\n"
                "#\n\n"
                "{0}\n".format(body)
            )
            _write(seq_path("A000040", d), content)
            rc, out = self._verify(["A000040"], d)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out)
        self.assertNotIn("SKIP", out)

    def test_results_summary_includes_skipped(self):
        with TempDir() as d:
            # One good file, one no-header file
            good = make_sequence_file("A000796", SAMPLE_METADATA, SAMPLE_TERMS)
            _write(seq_path("A000796", d), good)
            _write(seq_path("A000040", d), "2, 3, 5\n")
            _, out = self._verify([], d)
        self.assertIn("skipped", out.lower())

    def test_results_summary_skipped_not_counted_as_failed(self):
        with TempDir() as d:
            _write(seq_path("A000796", d), "3, 1, 4\n")
            rc, out = self._verify(["A000796"], d)
        self.assertEqual(rc, 0)
        self.assertIn("0 failed", out)


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------

class TestBuildParser(unittest.TestCase):

    def setUp(self):
        self.p = build_parser()

    def test_list_subcommand(self):
        args = self.p.parse_args(["list"])
        self.assertEqual(args.command, "list")

    def test_show_subcommand(self):
        args = self.p.parse_args(["show", "A000796"])
        self.assertEqual(args.command, "show")
        self.assertEqual(args.id, "A000796")

    def test_terms_subcommand_default_count(self):
        args = self.p.parse_args(["terms", "A000040"])
        self.assertEqual(args.command, "terms")
        self.assertEqual(args.count, 20)

    def test_terms_subcommand_custom_count(self):
        args = self.p.parse_args(["terms", "A000040", "--count", "50"])
        self.assertEqual(args.count, 50)

    def test_terms_count_must_be_positive(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args(["terms", "A000040", "--count", "0"])

    def test_sync_subcommand_no_ids(self):
        args = self.p.parse_args(["sync"])
        self.assertEqual(args.command, "sync")
        self.assertEqual(args.ids, [])
        self.assertFalse(args.sync_all)
        self.assertFalse(args.force)

    def test_sync_subcommand_with_ids(self):
        args = self.p.parse_args(["sync", "A000796", "A000040"])
        self.assertEqual(args.ids, ["A000796", "A000040"])

    def test_sync_all_flag(self):
        args = self.p.parse_args(["sync", "--all"])
        self.assertTrue(args.sync_all)

    def test_sync_force_flag(self):
        args = self.p.parse_args(["sync", "--force"])
        self.assertTrue(args.force)

    def test_verify_subcommand_no_ids(self):
        args = self.p.parse_args(["verify"])
        self.assertEqual(args.command, "verify")
        self.assertEqual(args.ids, [])

    def test_verify_subcommand_with_ids(self):
        args = self.p.parse_args(["verify", "A000796"])
        self.assertEqual(args.ids, ["A000796"])

    def test_dir_flag(self):
        args = self.p.parse_args(["--dir", "/tmp/seq", "list"])
        self.assertEqual(args.dir, "/tmp/seq")

    def test_no_command_exits(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args([])


if __name__ == "__main__":
    unittest.main()
