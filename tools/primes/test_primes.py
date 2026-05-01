#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for primes.py"""

from __future__ import print_function, unicode_literals

import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tools.primes.primes import (
    WITNESSES,
    is_prime,
    next_prime,
    generate_first_primes,
    generate_primes_in_range,
    _sha256_hex,
    _make_body,
    _parse_prime_header,
    _extract_body,
    cmd_generate,
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


class TempFile(object):
    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        return self.path

    def __exit__(self, *_):
        try:
            os.unlink(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# is_prime
# ---------------------------------------------------------------------------

class TestIsPrime(unittest.TestCase):

    def test_small_primes(self):
        for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]:
            self.assertTrue(is_prime(p), "{0} should be prime".format(p))

    def test_small_composites(self):
        for n in [0, 1, 4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 25, 35]:
            self.assertFalse(is_prime(n), "{0} should not be prime".format(n))

    def test_large_prime(self):
        self.assertTrue(is_prime(104729))

    def test_large_composite(self):
        self.assertFalse(is_prime(104728))

    def test_large_semiprime(self):
        self.assertFalse(is_prime(104729 * 104723))

    def test_all_witnesses_are_prime(self):
        for w in WITNESSES:
            self.assertTrue(is_prime(w))

    def test_two_is_prime(self):
        self.assertTrue(is_prime(2))

    def test_one_not_prime(self):
        self.assertFalse(is_prime(1))

    def test_zero_not_prime(self):
        self.assertFalse(is_prime(0))


# ---------------------------------------------------------------------------
# next_prime
# ---------------------------------------------------------------------------

class TestNextPrime(unittest.TestCase):

    def test_next_prime_of_0(self):
        self.assertEqual(next_prime(0), 2)

    def test_next_prime_of_1(self):
        self.assertEqual(next_prime(1), 2)

    def test_next_prime_of_2(self):
        self.assertEqual(next_prime(2), 2)

    def test_next_prime_of_3(self):
        self.assertEqual(next_prime(3), 3)

    def test_next_prime_of_4(self):
        self.assertEqual(next_prime(4), 5)

    def test_next_prime_of_1000(self):
        self.assertEqual(next_prime(1000), 1009)

    def test_next_prime_of_2038(self):
        self.assertEqual(next_prime(2038), 2039)

    def test_prime_input_returns_itself(self):
        self.assertEqual(next_prime(17), 17)

    def test_result_is_always_prime(self):
        for n in range(0, 200):
            self.assertTrue(is_prime(next_prime(n)))

    def test_result_is_always_ge_input(self):
        for n in range(0, 200):
            self.assertGreaterEqual(next_prime(n), n)


# ---------------------------------------------------------------------------
# generate_first_primes
# ---------------------------------------------------------------------------

class TestGenerateFirstPrimes(unittest.TestCase):

    def test_first_ten_known_vector(self):
        self.assertEqual(
            list(generate_first_primes(10)),
            [2, 3, 5, 7, 11, 13, 17, 19, 23, 29],
        )

    def test_first_one(self):
        self.assertEqual(list(generate_first_primes(1)), [2])

    def test_zero_yields_nothing(self):
        self.assertEqual(list(generate_first_primes(0)), [])

    def test_negative_yields_nothing(self):
        self.assertEqual(list(generate_first_primes(-1)), [])

    def test_count_is_exact(self):
        self.assertEqual(len(list(generate_first_primes(100))), 100)

    def test_all_results_are_prime(self):
        for p in generate_first_primes(50):
            self.assertTrue(is_prime(p))

    def test_results_are_strictly_increasing(self):
        primes = list(generate_first_primes(20))
        for i in range(len(primes) - 1):
            self.assertLess(primes[i], primes[i + 1])


# ---------------------------------------------------------------------------
# generate_primes_in_range
# ---------------------------------------------------------------------------

class TestGeneratePrimesInRange(unittest.TestCase):

    def test_range_100_to_150(self):
        primes = list(generate_primes_in_range(100, 150))
        self.assertEqual(primes, [101, 103, 107, 109, 113, 127, 131, 137, 139, 149])

    def test_range_inclusive_endpoints(self):
        self.assertIn(101, generate_primes_in_range(101, 101))

    def test_composite_endpoint_excluded(self):
        self.assertNotIn(100, list(generate_primes_in_range(100, 105)))

    def test_reversed_range_empty(self):
        self.assertEqual(list(generate_primes_in_range(100, 50)), [])

    def test_range_below_2_empty(self):
        self.assertEqual(list(generate_primes_in_range(0, 1)), [])

    def test_single_prime(self):
        self.assertEqual(list(generate_primes_in_range(17, 17)), [17])

    def test_single_composite(self):
        self.assertEqual(list(generate_primes_in_range(4, 4)), [])

    def test_all_results_are_prime(self):
        for p in generate_primes_in_range(200, 300):
            self.assertTrue(is_prime(p))


# ---------------------------------------------------------------------------
# PRIME-001: witness set sync with mnemonic.py
# ---------------------------------------------------------------------------

class TestWitnessSync(unittest.TestCase):

    def test_witnesses_match_mnemonic_witnesses_small(self):
        from tools.mnemonic.mnemonic import WITNESSES_SMALL
        self.assertEqual(
            WITNESSES, WITNESSES_SMALL,
            "WITNESSES in primes.py must be identical to WITNESSES_SMALL in "
            "mnemonic.py - update both together if the witness set changes."
        )


# ---------------------------------------------------------------------------
# _sha256_hex / _make_body / _parse_prime_header / _extract_body
# ---------------------------------------------------------------------------

class TestHelpers(unittest.TestCase):

    def test_sha256_hex_known(self):
        import hashlib
        text = "hello"
        self.assertEqual(
            _sha256_hex(text),
            hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    def test_make_body_format(self):
        body = _make_body([2, 3, 5])
        self.assertEqual(body, "2\n3\n5\n")

    def test_make_body_trailing_newline(self):
        body = _make_body([2])
        self.assertTrue(body.endswith("\n"))

    def test_parse_header_count(self):
        text = "# primes\n# Count:     10\n# SHA256:    abc123\n#\n2\n3\n"
        h = _parse_prime_header(text)
        self.assertEqual(h["count"], 10)

    def test_parse_header_sha256(self):
        text = "# primes\n# Count:     10\n# SHA256:    abc123\n#\n2\n3\n"
        h = _parse_prime_header(text)
        self.assertEqual(h["sha256"], "abc123")

    def test_parse_header_missing_fields_return_none(self):
        h = _parse_prime_header("2\n3\n5\n")
        self.assertIsNone(h["count"])
        self.assertIsNone(h["sha256"])

    def test_parse_header_survives_blank_line_between_fields(self):
        text = "# primes\n\n# Count:     10\n# SHA256:    abc123\n#\n2\n3\n"
        h = _parse_prime_header(text)
        self.assertEqual(h["count"], 10)
        self.assertEqual(h["sha256"], "abc123")

    def test_extract_body_strips_header(self):
        text = "# header line\n#\n2\n3\n5\n"
        body = _extract_body(text)
        self.assertEqual(body, "2\n3\n5\n")

    def test_extract_body_no_header(self):
        text = "2\n3\n5\n"
        body = _extract_body(text)
        self.assertEqual(body, "2\n3\n5\n")


# ---------------------------------------------------------------------------
# generate subcommand
# ---------------------------------------------------------------------------

class TestCmdGenerate(unittest.TestCase):

    def test_creates_nonempty_file(self):
        with TempFile() as path:
            rc = cmd_generate(_args(count=10, outfile=path))
            self.assertEqual(rc, 0)
            self.assertGreater(os.path.getsize(path), 0)

    def test_file_contains_correct_count(self):
        with TempFile() as path:
            cmd_generate(_args(count=10, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            body = _extract_body(content)
            primes = [int(l) for l in body.splitlines() if l]
            self.assertEqual(len(primes), 10)

    def test_file_contains_sha256_header(self):
        with TempFile() as path:
            cmd_generate(_args(count=5, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            h = _parse_prime_header(content)
            self.assertIsNotNone(h["sha256"])

    def test_file_contains_count_header(self):
        with TempFile() as path:
            cmd_generate(_args(count=5, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            h = _parse_prime_header(content)
            self.assertEqual(h["count"], 5)

    def test_sha256_in_header_matches_body(self):
        with TempFile() as path:
            cmd_generate(_args(count=20, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            h    = _parse_prime_header(content)
            body = _extract_body(content)
            self.assertEqual(h["sha256"], _sha256_hex(body))

    def test_generated_primes_are_correct(self):
        with TempFile() as path:
            cmd_generate(_args(count=10, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            body   = _extract_body(content)
            primes = [int(l) for l in body.splitlines() if l]
            self.assertEqual(primes, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])


# ---------------------------------------------------------------------------
# verify subcommand
# ---------------------------------------------------------------------------

class TestCmdVerify(unittest.TestCase):

    def test_passes_on_generated_file(self):
        with TempFile() as path:
            cmd_generate(_args(count=20, outfile=path))
            rc = cmd_verify(_args(infile=path))
            self.assertEqual(rc, 0)

    def test_fails_on_tampered_prime(self):
        with TempFile() as path:
            cmd_generate(_args(count=10, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # Corrupt the first body line (first non-# non-empty line)
            for i, line in enumerate(lines):
                if not line.startswith("#") and line.strip():
                    lines[i] = "4\n"  # replace with a composite
                    break
            with io.open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            rc = cmd_verify(_args(infile=path))
            self.assertEqual(rc, 1)

    def test_fails_on_truncated_file(self):
        with TempFile() as path:
            cmd_generate(_args(count=10, outfile=path))
            with io.open(path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            truncated = "\n".join(lines[:-3]) + "\n"
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(truncated)
            rc = cmd_verify(_args(infile=path))
            self.assertEqual(rc, 1)

    def test_fails_on_missing_file(self):
        rc = cmd_verify(_args(infile="/tmp/crowsong_nonexistent_primes.txt"))
        self.assertEqual(rc, 1)

    def test_no_header_reports_without_error(self):
        with TempFile() as path:
            with io.open(path, "w", encoding="utf-8") as f:
                f.write("2\n3\n5\n7\n11\n")
            rc = cmd_verify(_args(infile=path))
            self.assertEqual(rc, 0)

    def test_roundtrip_100_primes(self):
        with TempFile() as path:
            cmd_generate(_args(count=100, outfile=path))
            rc = cmd_verify(_args(infile=path))
            self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

class TestBuildParser(unittest.TestCase):

    def setUp(self):
        self.p = build_parser()

    def test_generate_subcommand(self):
        args = self.p.parse_args(["generate", "100", "/tmp/out.txt"])
        self.assertEqual(args.command, "generate")
        self.assertEqual(args.count, 100)
        self.assertEqual(args.outfile, "/tmp/out.txt")

    def test_verify_subcommand(self):
        args = self.p.parse_args(["verify", "/tmp/primes.txt"])
        self.assertEqual(args.command, "verify")
        self.assertEqual(args.infile, "/tmp/primes.txt")

    def test_is_prime_subcommand(self):
        args = self.p.parse_args(["is-prime", "17"])
        self.assertEqual(args.command, "is-prime")
        self.assertEqual(args.n, 17)

    def test_next_prime_subcommand(self):
        args = self.p.parse_args(["next-prime", "1000"])
        self.assertEqual(args.command, "next-prime")
        self.assertEqual(args.n, 1000)

    def test_first_subcommand(self):
        args = self.p.parse_args(["first", "10"])
        self.assertEqual(args.command, "first")
        self.assertEqual(args.count, 10)

    def test_range_subcommand(self):
        args = self.p.parse_args(["range", "100", "200"])
        self.assertEqual(args.command, "range")
        self.assertEqual(args.start, 100)
        self.assertEqual(args.end, 200)

    def test_no_command_exits(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args([])

    def test_generate_count_must_be_positive(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args(["generate", "0", "/tmp/out.txt"])


if __name__ == "__main__":
    unittest.main()
