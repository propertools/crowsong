#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for mnemonic.derive_from_bytes (binary-seed derivation)."""

import hashlib
import sys
import os
import unittest

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.mnemonic.mnemonic import derive_from_bytes, is_prime, next_prime


class TestDeriveFromBytes(unittest.TestCase):
    """Binary-seed derivation: bytes -> SHA256 -> next_prime -> P."""

    # ── known vector ─────────────────────────────────────────────────────

    def test_known_vector(self):
        """Pin a concrete input to its expected prime."""
        r = derive_from_bytes(b"crowsong")
        self.assertEqual(
            r["digest_hex"],
            "378c7a695480455074c43b55fba9f2c435689740b29fbd158075e6c66bc49e4d",
        )
        self.assertEqual(
            r["P"],
            25125410113896333696023117912461443006818191086584771010919297437932116549409,
        )

    # ── construction properties ──────────────────────────────────────────

    def test_result_keys(self):
        """Return dict contains exactly the documented keys."""
        r = derive_from_bytes(b"\x00\x01\x02")
        self.assertEqual(set(r.keys()), {"canonical", "digest_hex", "N", "P"})

    def test_canonical_is_identity(self):
        """canonical must be the exact input bytes — no transformation."""
        blob = os.urandom(256)
        r = derive_from_bytes(blob)
        self.assertIs(r["canonical"], blob)

    def test_digest_matches_sha256(self):
        """digest_hex must equal SHA256 of the raw input."""
        blob = b"binary-seed test payload"
        r = derive_from_bytes(blob)
        self.assertEqual(r["digest_hex"], hashlib.sha256(blob).hexdigest())

    def test_N_is_digest_as_int(self):
        """N must be int(digest_hex, 16)."""
        r = derive_from_bytes(b"check-N")
        self.assertEqual(r["N"], int(r["digest_hex"], 16))

    def test_P_is_prime(self):
        """P must actually be prime."""
        r = derive_from_bytes(b"primality check")
        self.assertTrue(is_prime(r["P"]))

    def test_P_ge_N(self):
        """P must be >= N (next_prime never goes backwards)."""
        r = derive_from_bytes(b"ordering check")
        self.assertGreaterEqual(r["P"], r["N"])

    def test_P_is_next_prime_of_N(self):
        """P must be exactly next_prime(N), not some other prime."""
        r = derive_from_bytes(b"exact next_prime")
        self.assertEqual(r["P"], next_prime(r["N"]))

    # ── determinism ──────────────────────────────────────────────────────

    def test_deterministic(self):
        """Same bytes in -> same prime out, every time."""
        blob = b"determinism"
        self.assertEqual(
            derive_from_bytes(blob)["P"],
            derive_from_bytes(blob)["P"],
        )

    def test_different_bytes_different_prime(self):
        """Distinct inputs must (almost certainly) produce distinct primes."""
        a = derive_from_bytes(b"alpha")["P"]
        b = derive_from_bytes(b"bravo")["P"]
        self.assertNotEqual(a, b)

    # ── bytes are bytes (no normalisation) ───────────────────────────────

    def test_single_byte_difference(self):
        """A one-bit change in input must change the output."""
        a = derive_from_bytes(b"\x00")["P"]
        b = derive_from_bytes(b"\x01")["P"]
        self.assertNotEqual(a, b)

    def test_binary_blob_roundtrip(self):
        """Arbitrary binary (including nulls) passes through unchanged."""
        blob = bytes(range(256))
        r = derive_from_bytes(blob)
        self.assertEqual(r["canonical"], blob)
        self.assertTrue(is_prime(r["P"]))

    def test_no_unicode_normalisation(self):
        """NFC and NFD forms of the same text must produce different primes
        when encoded to bytes, because raw bytes are not normalised."""
        import unicodedata
        text = "\u00e9"  # é (NFC: single codepoint)
        nfc = unicodedata.normalize("NFC", text).encode("utf-8")
        nfd = unicodedata.normalize("NFD", text).encode("utf-8")
        self.assertNotEqual(nfc, nfd)  # precondition: different byte sequences
        self.assertNotEqual(
            derive_from_bytes(nfc)["P"],
            derive_from_bytes(nfd)["P"],
        )

    # ── input validation ─────────────────────────────────────────────────

    def test_rejects_str(self):
        """Must raise TypeError for str input."""
        with self.assertRaises(TypeError):
            derive_from_bytes("not bytes")

    def test_rejects_int(self):
        """Must raise TypeError for non-bytes input."""
        with self.assertRaises(TypeError):
            derive_from_bytes(42)

    def test_rejects_none(self):
        """Must raise TypeError for None."""
        with self.assertRaises(TypeError):
            derive_from_bytes(None)

    def test_rejects_empty(self):
        """Must raise ValueError for zero-length bytes."""
        with self.assertRaises(ValueError):
            derive_from_bytes(b"")


if __name__ == "__main__":
    unittest.main()
