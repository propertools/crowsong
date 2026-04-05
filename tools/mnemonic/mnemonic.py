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
import sys
import unicodedata

PY2       = (sys.version_info[0] == 2)
text_type = bytes if False else (str if not PY2 else type(u""))  # unicode in Py2, str in Py3

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
    if width < 1:
        raise ValueError("width must be >= 1")
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
        verse: input text (any Unicode, any length). Leading and trailing
               whitespace is stripped before NFC normalisation. This is
               the canonical policy; it applies here and nowhere else.
        width: UCS-DEC field width (default: 5, must be >= 1)

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
    if not isinstance(verse, text_type):
        raise TypeError("verse must be a Unicode string, got {0!r}".format(
            type(verse).__name__))
    if width < 1:
        raise ValueError("width must be >= 1")
    # Strip leading/trailing whitespace before normalisation.
    # This is the canonical strip policy for the construction:
    # "  verse  " and "verse" produce the same prime.
    verse        = verse.strip()
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

# ── Melody derivation ─────────────────────────────────────────────────────────

def normalise_intervals(intervals):
    """
    Canonicalise a semitone interval sequence.

    Each interval is clamped to [-24, +24] (two octaves) and represented
    as a signed zero-padded 3-character string, e.g. +02, -05, +00.
    Values are space-separated.

    Args:
        intervals: iterable of signed integers (semitone differences)

    Returns:
        Canonical byte string suitable for SHA256 input.
    """
    clamped = [max(-24, min(24, int(i))) for i in intervals]
    return " ".join("{0:+03d}".format(i) for i in clamped).encode("utf-8")


def midi_to_intervals(pitches):
    """
    Convert a MIDI pitch sequence to a semitone interval sequence.

    Args:
        pitches: iterable of MIDI note numbers (0-127)

    Returns:
        List of signed integer semitone differences.

    Raises:
        ValueError if fewer than 2 pitches are provided.
    """
    pitches = list(pitches)
    if len(pitches) < 2:
        raise ValueError("melody must have at least 2 notes")
    for p in pitches:
        if not (0 <= int(p) <= 127):
            raise ValueError(
                "MIDI pitch out of range: {0} (must be 0-127)".format(p))
    return [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]


def parsons_to_bytes(code):
    """
    Canonicalise a Parsons code string.

    Parsons code uses: * (start), U (up), D (down), R (repeat/same).
    Case-insensitive. Leading * is optional and normalised to present.

    Args:
        code: string of Parsons code characters

    Returns:
        Canonical byte string suitable for SHA256 input.

    Raises:
        ValueError if the code contains invalid characters.
    """
    code = code.strip().upper()
    if not code.startswith("*"):
        code = "*" + code
    valid = set("*UDR")
    invalid = set(code) - valid
    if invalid:
        raise ValueError(
            "invalid Parsons code characters: {0}".format(
                ", ".join(sorted(invalid))))
    return code.encode("ascii")


def derive_from_melody(intervals=None, midi=None, parsons=None,
                       abc=None):
    """
    Derive a prime from a musical melody.

    Accepts the melody in one of four representations. Exactly one
    must be provided.

    Args:
        intervals: list of signed integer semitone differences
                   Transposition-invariant. Recommended default.
                   e.g. [0, 2, -2, 5, -1] for Happy Birthday

        midi:      list of MIDI note numbers (0-127)
                   Transposition-sensitive: same tune in C and F
                   produces different primes.
                   e.g. [60, 60, 62, 60, 65, 64]

        parsons:   Parsons code string (* U D R)
                   Transposition-invariant and octave-invariant.
                   Very coarse — many tunes share the same contour.
                   e.g. "*RUDUUD"

        abc:       ABC notation string (standard text format)
                   Transposition-sensitive unless key is stripped.
                   e.g. "X:1\nT:...\nK:C\n..."

    Returns:
        dict with keys:
            representation  (str)   which input was used
            canonical       (bytes) the canonical byte string hashed
            digest_hex      (str)   SHA256 hex digest
            N               (int)   integer interpretation
            P               (int)   derived prime

    Raises:
        ValueError if not exactly one representation is provided,
        or if the input is invalid.

    Notes:
        Interval representation is RECOMMENDED. It is transposition-
        invariant: the same melody hummed in any key produces the same
        prime. The operator does not need to know which key they are
        humming in.

        MIDI representation is appropriate when the exact pitches are
        meaningful (e.g. a specific recording or MIDI file is the seed).

        Parsons code is appropriate when only the melodic contour
        (up/down/same) needs to be specified. It is the most forgiving
        representation but the least specific.

        ABC notation is appropriate when a canonical published score
        is the seed. The tune ID in a public database (e.g.
        thesession.org/tunes/1) provides an indestructible reference.
    """
    provided = sum(x is not None for x in [intervals, midi, parsons, abc])
    if provided != 1:
        raise ValueError(
            "exactly one of intervals, midi, parsons, abc must be provided")

    if intervals is not None:
        canonical = normalise_intervals(intervals)
        rep = "intervals"

    elif midi is not None:
        ivs = midi_to_intervals(midi)
        # Derive from intervals for transposition invariance
        canonical = normalise_intervals(ivs)
        rep = "midi-as-intervals"

    elif parsons is not None:
        canonical = parsons_to_bytes(parsons)
        rep = "parsons"

    else:
        # ABC notation: strip, normalise line endings, UTF-8
        lines = [l.strip() for l in abc.strip().splitlines() if l.strip()]
        canonical = "\n".join(lines).encode("utf-8")
        rep = "abc"

    digest_hex = hashlib.sha256(canonical).hexdigest()
    N = int(digest_hex, 16)
    P = next_prime(N)

    return {
        "representation": rep,
        "canonical":      canonical,
        "digest_hex":     digest_hex,
        "N":              N,
        "P":              P,
    }
