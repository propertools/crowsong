#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mnemonic.py — shared construction library for verse-to-prime derivation

This module is the single canonical implementation of the mnemonic prime
derivation construction used across the Crowsong mnemonic toolchain.
It is imported by verse_to_prime.py and prime_twist.py; neither tool
duplicates this logic.

Exports:
    WITNESSES_SMALL     Fixed Miller-Rabin witness set
    is_prime(n)         Miller-Rabin primality test
    next_prime(n)       Smallest prime >= n
    ucs_dec_encode(text, width)   UCS-DEC token stream encoder
    derive(verse, width)          Full verse-to-prime construction

Construction:

    verse (any Unicode text)
      -> NFC normalise
      -> UCS-DEC encode (WIDTH/5, no wrapping)
      -> SHA256 of token stream (UTF-8)
      -> interpret digest as 256-bit integer N
      -> next_prime(N)
      -> prime P

The resulting prime is deterministic for a given verse. It need not be
stored; it can be reconstructed from the verse at any time.

Primality note:
    Uses a fixed Miller-Rabin witness set (WITNESSES_SMALL). Deterministic
    (no false positives) for n < ~3.3e24. For larger n, including all
    SHA256-derived inputs (~77 decimal digits), this is a well-tested
    heuristic: no counterexample is known for this witness set, and inputs
    are not adversarially chosen. No probabilistic round count is used;
    behaviour does not vary with input size.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import unicode_literals

import hashlib
import unicodedata

# ── Miller-Rabin ──────────────────────────────────────────────────────────────

WITNESSES_SMALL = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _miller_rabin(n, witnesses):
    """Run Miller-Rabin with the given witness set. Return False if composite."""
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in witnesses:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        composite = True
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False
    return True


def is_prime(n):
    """
    Return True if n is (very probably) prime.

    Uses WITNESSES_SMALL with Miller-Rabin. Deterministic (no false
    positives) for n < ~3.3e24. For larger n, including all SHA256-derived
    inputs (~77 digits), this is a well-tested heuristic with no known
    counterexample for this witness set.
    """
    if n < 2:
        return False
    for p in WITNESSES_SMALL:
        if n == p:
            return True
        if n % p == 0:
            return False
    return _miller_rabin(n, WITNESSES_SMALL)


def next_prime(n):
    """Return the smallest prime >= n."""
    if n <= 2:
        return 2
    n = n | 1
    while not is_prime(n):
        n += 2
    return n


# ── UCS-DEC encoding (construction intermediate) ──────────────────────────────

def ucs_dec_encode(text, width=5):
    """
    Encode text as a UCS-DEC token stream (no line wrapping).

    Each Unicode code point is represented as a zero-padded decimal
    integer of the given field width. Space-separated.

    Args:
        text:  Unicode string (should be NFC-normalised before calling)
        width: field width in digits (default: 5)

    Returns:
        Space-separated token string.
    """
    return " ".join("{0:0{1}d}".format(ord(ch), width) for ch in text)


# ── Core construction ─────────────────────────────────────────────────────────

def derive(verse, width=5):
    """
    Derive a prime from a verse.

    Steps:
        1. NFC normalise
        2. UCS-DEC encode (width, no wrapping)
        3. SHA256 of token stream (UTF-8)
        4. Interpret digest as 256-bit integer N
        5. next_prime(N) -> P

    Args:
        verse: input text (any Unicode, any length)
        width: UCS-DEC field width (default: 5)

    Returns:
        dict with keys:
            normalised    (str)   NFC-normalised verse
            token_stream  (str)   UCS-DEC encoding of verse
            token_count   (int)
            digest_hex    (str)   SHA256 of token stream, hex
            N             (int)   integer interpretation of digest
            P             (int)   derived prime
            width         (int)   field width used
    """
    normalised   = unicodedata.normalize("NFC", verse)
    token_stream = ucs_dec_encode(normalised, width)
    digest_hex   = hashlib.sha256(
        token_stream.encode("utf-8")).hexdigest()
    N            = int(digest_hex, 16)
    P            = next_prime(N)

    return {
        "normalised":   normalised,
        "token_stream": token_stream,
        "token_count":  len(token_stream.split()),
        "digest_hex":   digest_hex,
        "N":            N,
        "P":            P,
        "width":        width,
    }
