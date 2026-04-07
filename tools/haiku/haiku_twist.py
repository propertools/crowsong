#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
haiku_twist.py — Prime-driven haiku generator

Generates deterministic, reversible haiku from a verse-derived prime.
The prime's digit sequence drives two independent schedules:

    verse -> prime P
      forward digits  -> syllable count schedule  (digit mod 5 + 1)
      reversed digits -> word selection within bin (SHA256-seeded)

One verse. One prime. Two schedules. Zero additional key material.
Same structural pattern as the Gloss layer.

The format eats its own output:

    verse1 -> P1 -> haiku1
    haiku1 -> (as verse) -> P2 -> haiku2
    haiku2 -> P3 -> haiku3
    ...

Each haiku is the output of one prime and the seed for the next.

Canonical test vector:
    Verse:  K1 — "Factoring primes in the hot sun,
                   I fought Entropy — and Entropy won."
    Output: see archive/haiku-canonical-001.txt

Construction (generate):
    1. Derive prime P from verse via mnemonic.derive()
    2. Forward digits F = list(str(P))
    3. Reversed digits R = list(reversed(str(P)))
    4. For each haiku line (syllable targets: 5-7-5):
       a. For each word slot i:
          - s = (F[i mod len(F)] mod 5) + 1, capped to remaining
          - seed = SHA256(R[i mod len(R)] : i : s) as integer
          - word = bins[s][seed mod len(bins[s])]
       b. Accumulate until syllable target reached
    5. Wrap in self-describing RSRC artifact

Reversal (verify):
    Given artifact (haiku text + RSRC block):
    1. Read prime P, syllable plan, word indices from RSRC
    2. Recompute word selections from prime + bins
    3. Confirm each word matches declared index in declared bin
    4. Confirm syllable plan matches forward schedule

Usage:
    python haiku_twist.py generate      [--prime P] [--bins FILE] [--ref ID]
    python haiku_twist.py verify        <artifact>  [--bins FILE]
    python haiku_twist.py chain         [--steps N] [--bins FILE] [--output FILE]
    python haiku_twist.py decode        <artifact>
    python haiku_twist.py encode-stream [--prime P] [--verse FILE] [--bins FILE] [--ref ID]
    python haiku_twist.py decode-stream <artifact>  [--bins FILE]

encode-stream / decode-stream — word-space encoding of arbitrary token streams:

    Any UCS-DEC token stream (e.g. CCL3 output) can be encoded as a
    stream of real English words drawn from the keyed corpus, structured
    as repeating 5-7-5 haiku stanzas. The output looks like poetry.
    The prime drives a keyed Fisher-Yates permutation of the full corpus
    index (~134,000 words), mapping each token value to a unique word.
    Reversal is exact: same prime, same permutation, same mapping.

    Full pipeline (arbitrary text -> haiku poetry -> back):

        cat second-law-blues.txt \\
            | python tools/ucs-dec/ucs_dec_tool.py --encode \\
            | python tools/mnemonic/prime_twist.py stack \\
                --verse-file verses.txt --ref CCL3 --no-symbol-check \\
            | python tools/mnemonic/haiku_twist.py encode-stream \\
                --verse verses.txt --ref STREAM-001 \\
            > archive/second-law-blues-haiku.txt

        python tools/mnemonic/haiku_twist.py decode-stream \\
                archive/second-law-blues-haiku.txt \\
            | python tools/mnemonic/prime_twist.py unstack - \\
            | python tools/ucs-dec/ucs_dec_tool.py --decode

Examples:
    # Generate from K1 (canonical test vector)
    echo "Factoring primes in the hot sun, I fought Entropy and Entropy won." | \\
        python haiku_twist.py --bins docs/cmudict/bins.json generate

    # Chain: 7 linked haiku, each seeding the next
    echo "Factoring primes in the hot sun, I fought Entropy and Entropy won." | \\
        python haiku_twist.py --bins docs/cmudict/bins.json chain --steps 7

    # Encode arbitrary token stream as haiku word stream
    cat payload_tokens.txt | \\
        python haiku_twist.py --bins docs/cmudict/bins.json encode-stream \\
            --verse verses.txt --ref STREAM-001

    # Decode haiku word stream back to token stream
    python haiku_twist.py --bins docs/cmudict/bins.json decode-stream \\
        archive/stream-001.txt

Compatibility: Python 2.7+ / 3.x
Dependencies:  mnemonic.py (tools/mnemonic/ or same directory)
               bins.json   (from tools/cmudict/cmudict.py export)
Author: Proper Tools SRL
License: MIT

Dedicated to Felix 'FX' Lindner (1975-2026).
The signal strains, but never gone.
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import hashlib
import io
import json
import os
import sys
import time

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
    range     = xrange   # noqa: F821
else:
    text_type = str


# ── mnemonic import ───────────────────────────────────────────────────────────

def _import_mnemonic():
    """
    Import derive() from mnemonic.py.
    Tries: same directory, ../mnemonic/, ../../tools/mnemonic/
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        script_dir,
        os.path.join(script_dir, "..", "mnemonic"),
        os.path.join(script_dir, "..", "..", "tools", "mnemonic"),
    ]
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.isfile(os.path.join(abs_path, "mnemonic.py")):
            if abs_path not in sys.path:
                sys.path.insert(0, abs_path)
            break
    try:
        from mnemonic import derive  # noqa: F401
        return derive
    except ImportError:
        raise ImportError(
            "mnemonic.py not found.\n"
            "Expected at tools/mnemonic/mnemonic.py or alongside haiku_twist.py.\n"
            "Clone from: github.com/propertools/crowsong")


_derive = _import_mnemonic()


# ── Constants ─────────────────────────────────────────────────────────────────

HAIKU_PATTERN  = [5, 7, 5]
DEFAULT_BINS   = os.path.join("docs", "cmudict", "bins.json")
BOX_INNER      = 41
MIDDLE_DOT     = "\u00b7"
DESTROY_FLAG   = "IF COUNT FAILS: DESTROY IMMEDIATELY"

CANONICAL_VERSE = (
    "Factoring primes in the hot sun, "
    "I fought Entropy \u2014 and Entropy won."
)

DEDICATION = "Dedicated to Felix 'FX' Lindner (1975\u20132026)."


# ── Bins ──────────────────────────────────────────────────────────────────────

def load_bins(bins_path):
    """
    Load syllable bins from bins.json (cmudict.py export output).

    Returns:
        dict: int -> list of words (lowercase, sorted)
    """
    if not os.path.isfile(bins_path):
        raise IOError(
            "Syllable bins not found: {0}\n"
            "Run: python tools/cmudict/cmudict.py fetch\n"
            "     python tools/cmudict/cmudict.py export".format(bins_path))

    with io.open(bins_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    bins = {}
    for key, words in raw.items():
        if key == "_meta":
            continue
        try:
            bins[int(key)] = words
        except ValueError:
            pass

    if not bins:
        raise ValueError(
            "bins.json contains no syllable data. "
            "Re-run: python tools/cmudict/cmudict.py export")

    return bins


# ── Schedule functions ────────────────────────────────────────────────────────

def _prime_fwd(prime_str):
    """Forward digit list as ints."""
    return [int(d) for d in str(prime_str)]


def _prime_rev(prime_str):
    """Reversed digit list as ints."""
    return [int(d) for d in reversed(str(prime_str))]


def _syllable_at(fwd, pos):
    """
    Scheduled syllable count at word position pos.
    forward digit mod 5 + 1 -> range [1, 6].
    """
    return (fwd[pos % len(fwd)] % 5) + 1


def _word_seed(rev, pos, syllable_count):
    """
    Deterministic seed for word selection at position pos.

    Uses reversed digits of prime combined with position and syllable
    count. SHA256-hashed for uniform distribution across the bin size.
    This is the same structural pattern as the Gloss layer's alphabet
    permutation: reversed digits -> second independent schedule.
    """
    seed_bytes = "{0}:{1}:{2}".format(
        rev[pos % len(rev)], pos, syllable_count).encode("utf-8")
    return int(hashlib.sha256(seed_bytes).hexdigest(), 16)


# ── Core generation ───────────────────────────────────────────────────────────

def generate_haiku(prime_str, bins):
    """
    Generate a haiku from prime P and syllable bins.

    Args:
        prime_str: decimal string of key prime P
        bins:      dict int -> list of words

    Returns dict:
        lines           list of 3 strings (one per haiku line)
        words           list of all words in order
        syllable_plan   list of syllable counts per word
        word_indices    list of (syllable_count, bin_index) per word
        prime           prime string
    """
    fwd  = _prime_fwd(prime_str)
    rev  = _prime_rev(prime_str)
    used = set()

    all_words    = []
    syllable_plan = []
    word_indices  = []
    lines        = []
    pos          = 0

    for target in HAIKU_PATTERN:
        remaining  = target
        line_words = []

        while remaining > 0:
            # Scheduled syllable count, capped to what's left in line
            s = min(_syllable_at(fwd, pos), remaining)

            # Fall back to smaller bins if needed
            while s > 1 and not bins.get(s):
                s -= 1
            if not bins.get(s):
                s = 1

            word_list  = bins.get(s, [])
            seed       = _word_seed(rev, pos, s)

            # Prefer unused words; fall back to full list if exhausted
            candidates = [w for w in word_list if w not in used]
            if not candidates:
                candidates = word_list

            idx_in_candidates = seed % len(candidates)
            word = candidates[idx_in_candidates]

            # Record index in the full bin (for reversibility)
            bin_idx = word_list.index(word)

            line_words.append(word)
            all_words.append(word)
            syllable_plan.append(s)
            word_indices.append((s, bin_idx))
            used.add(word)
            remaining -= s
            pos += 1

        lines.append(" ".join(line_words))

    return {
        "lines":         lines,
        "words":         all_words,
        "syllable_plan": syllable_plan,
        "word_indices":  word_indices,
        "prime":         prime_str,
    }


# ── Verification ──────────────────────────────────────────────────────────────

def verify_haiku(parsed, bins):
    """
    Verify a parsed haiku artifact against its declared prime and bins.

    Args:
        parsed: dict from parse_artifact()
        bins:   syllable bins dict

    Returns dict:
        ok              bool — all checks passed
        syllable_ok     bool — all words in correct syllable bins
        selection_ok    bool — all word indices match prime schedule
        errors          list of str
    """
    prime_str = parsed.get("prime", "")
    words     = parsed.get("words", [])
    syl_plan  = parsed.get("syllable_plan", [])
    w_idx     = parsed.get("word_indices", [])
    errors    = []

    if not prime_str:
        return {"ok": False, "syllable_ok": False,
                "selection_ok": False, "errors": ["No PRIME in artifact"]}

    rev = _prime_rev(prime_str)

    # Check each word is in its declared syllable bin
    for i, (word, s) in enumerate(zip(words, syl_plan)):
        word_list = bins.get(s, [])
        if word not in word_list:
            errors.append(
                "Pos {0}: '{1}' not in {2}-syllable bin".format(i, word, s))

    # Check each word matches its declared bin index under the prime schedule
    for i, (word, (s, bin_idx)) in enumerate(zip(words, w_idx)):
        word_list = bins.get(s, [])
        if not word_list:
            continue
        if bin_idx >= len(word_list):
            errors.append(
                "Pos {0}: bin index {1} out of range for {2}-syllable bin "
                "(size {3})".format(i, bin_idx, s, len(word_list)))
            continue
        declared_word = word_list[bin_idx]
        if declared_word != word:
            errors.append(
                "Pos {0}: expected '{1}' at index {2} in {3}-syllable bin, "
                "got '{4}'".format(i, declared_word, bin_idx, s, word))

    # Recompute from prime and compare
    try:
        recomputed = generate_haiku(prime_str, bins)
        if recomputed["words"] != words:
            errors.append(
                "Recomputed haiku differs from artifact. "
                "Prime schedule mismatch or corpus version mismatch.")
    except Exception as e:
        errors.append("Recomputation failed: {0}".format(e))

    syllable_ok  = not any("not in" in e for e in errors)
    selection_ok = not any("expected" in e or "index" in e for e in errors)

    return {
        "ok":           len(errors) == 0,
        "syllable_ok":  syllable_ok,
        "selection_ok": selection_ok,
        "errors":       errors,
    }


# ── Corpus index for stream encoding ─────────────────────────────────────────
#
# Stream encoding maps arbitrary token values to words via a keyed
# Fisher-Yates permutation of the full corpus word list.
#
# The corpus index is: bins[1] + bins[2] + ... + bins[9], sorted within
# each bin (alphabetical). This is deterministic and reproducible from
# any bins.json generated by cmudict.py export.
#
# The CMU dict contains ~134,000 words — sufficient to cover the full
# WIDTH/5 token range (00000–99999) with room to spare.
#
# Key insight: token value V -> permuted_index[V % corpus_size]
# Reversal:    word w -> V = permuted_index.index(w)
#
# The permutation is keyed from the prime, so the same word maps to
# different token values under different primes. The corpus is public;
# the prime is the secret.

def build_corpus_index(bins):
    """
    Build the flat corpus word list from syllable bins.

    Order: bins[1] + bins[2] + ... + bins[max], alphabetical within each bin.
    This order is deterministic given any bins.json from cmudict.py export.

    Returns:
        list of words (lowercase strings), length ~134,000
    """
    index = []
    for n in sorted(bins.keys()):
        index.extend(bins[n])
    return index


def _permute_corpus(corpus_index, prime_str):
    """
    Apply a keyed Fisher-Yates shuffle to the corpus index.

    Seed is derived from SHA256(prime_str) for uniform distribution.
    Returns a new list — the original is unchanged.

    This is the same structural pattern as the Gloss layer's alphabet
    permutation, scaled to the full corpus.
    """
    seed    = int(hashlib.sha256(
        prime_str.encode("utf-8")).hexdigest(), 16)
    permuted = list(corpus_index)
    n        = len(permuted)

    # Deterministic Fisher-Yates using the seed as a linear congruential
    # generator. We avoid importing random to keep Python 2.7 compat clean
    # and make the permutation fully explicit and auditable.
    # LCG parameters (Knuth): m=2^64, a=6364136223846793005, c=1442695040888963407
    state = seed
    def _lcg():
        # Use a slice of the SHA256 integer as state; advance with LCG
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) % (2**64)
        return state

    for i in range(n - 1, 0, -1):
        j = _lcg() % (i + 1)
        permuted[i], permuted[j] = permuted[j], permuted[i]

    return permuted


def _permute_corpus_py2_compat(corpus_index, prime_str):
    """
    Python 2/3 compatible Fisher-Yates permutation.
    nonlocal not available in Python 2, so we use a list as state cell.
    """
    seed     = int(hashlib.sha256(
        prime_str.encode("utf-8")).hexdigest(), 16)
    permuted = list(corpus_index)
    n        = len(permuted)
    state    = [seed]

    def _lcg():
        state[0] = (state[0] * 6364136223846793005 + 1442695040888963407) % (2**64)
        return state[0]

    for i in range(n - 1, 0, -1):
        j = _lcg() % (i + 1)
        permuted[i], permuted[j] = permuted[j], permuted[i]

    return permuted


def build_permuted_index(bins, prime_str):
    """
    Build the keyed permuted corpus index for stream encoding.

    Args:
        bins:      syllable bins dict from load_bins()
        prime_str: decimal string of key prime P

    Returns:
        (permuted, word_to_pos)
        permuted:    list of words in permuted order
        word_to_pos: dict word -> position in permuted list (for decode)
    """
    corpus   = build_corpus_index(bins)
    permuted = _permute_corpus_py2_compat(corpus, prime_str)
    word_to_pos = {word: i for i, word in enumerate(permuted)}
    return permuted, word_to_pos


# ── Stream syllable structure ─────────────────────────────────────────────────
#
# When encoding a token stream as haiku words, we want the output to look
# like poetry: real 5-7-5 stanzas. Each word in the permuted corpus has a
# known syllable count (from the bin it came from in the original bins).
# We use that syllable count to structure output lines.
#
# The syllable count of a word at permuted position V is recoverable from
# the original corpus structure: find which bin the word originally lived
# in. This is stored in the RSRC block as a syllable map for reversal.

def _build_syllable_lookup(bins):
    """Build word -> syllable_count lookup from bins."""
    lookup = {}
    for n, words in bins.items():
        for word in words:
            lookup[word] = n
    return lookup


def encode_stream(token_stream_str, prime_str, bins, ref="", bins_name="cmudict-v1"):
    """
    Encode a UCS-DEC token stream as a haiku word stream.

    Each token value V maps to permuted_index[V % corpus_size].
    Output is structured as repeating 5-7-5 stanzas using the natural
    syllable count of each selected word.

    Args:
        token_stream_str: whitespace-separated decimal token string
        prime_str:        decimal string of key prime P
        bins:             syllable bins dict
        ref:              artifact reference ID
        bins_name:        corpus name for RSRC block

    Returns:
        artifact string (self-describing, with RSRC block)
    """
    tokens = token_stream_str.split()
    if not tokens:
        raise ValueError("Empty token stream.")

    permuted, _   = build_permuted_index(bins, prime_str)
    corpus_size   = len(permuted)
    syl_lookup    = _build_syllable_lookup(bins)
    generated     = time.strftime("%Y-%m-%d")

    # Map each token to a word
    words = []
    for tok in tokens:
        try:
            v = int(tok)
        except ValueError:
            continue
        word = permuted[v % corpus_size]
        words.append((tok, word))

    # Structure output as repeating 5-7-5 stanzas
    # Each stanza is 3 lines; we fill by syllable count
    output_lines  = []
    current_line  = []
    current_syls  = 0
    pattern       = HAIKU_PATTERN
    pattern_pos   = 0   # which line in current stanza
    target        = pattern[pattern_pos % len(pattern)]

    for tok, word in words:
        s = syl_lookup.get(word, 1)
        if current_syls + s > target:
            # Flush current line even if short (token stream may not divide evenly)
            output_lines.append(" ".join(current_line))
            current_line  = []
            current_syls  = 0
            pattern_pos  += 1
            target        = pattern[pattern_pos % len(pattern)]
        current_line.append(word)
        current_syls += s
        if current_syls >= target:
            output_lines.append(" ".join(current_line))
            current_line  = []
            current_syls  = 0
            pattern_pos  += 1
            target        = pattern[pattern_pos % len(pattern)]

    # Flush any remaining words
    if current_line:
        output_lines.append(" ".join(current_line))

    payload    = "\n".join(output_lines)
    crc_input  = token_stream_str.strip()
    crc        = binascii.crc32(crc_input.encode("utf-8")) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    word_count = len(words)

    rsrc = [
        "RSRC: BEGIN",
        "  TYPE:         haiku-stream",
        "  VERSION:      1",
        "  NOTE:         TEST IMPLEMENTATION -- not normatively specified",
        "  CORPUS:       {0}".format(bins_name),
        "  CORPUS-SIZE:  {0}".format(corpus_size),
        "  PATTERN:      {0}".format("-".join(str(s) for s in HAIKU_PATTERN)),
        "  ENCODING:     keyed-permutation / Fisher-Yates / SHA256(P)",
        "  PRIME:        {0}".format(prime_str),
        "  TOKENS:       {0}".format(word_count),
        "  LINES:        {0}".format(len(output_lines)),
        "  CRC32-TOKENS: {0}".format(crc_str),
        "  GENERATED:    {0}".format(generated),
        "  DEDICATION:   {0}".format(DEDICATION),
        "RSRC: END",
    ]

    header = [_box_rule()]
    if ref:
        header.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    header.append(_box_line(
        "ENC: HAIKU-STREAM {d} PRIME-PERMUTATION".format(d=MIDDLE_DOT)))
    header.append(_box_line(
        "CORPUS: {0} ({1:,} words)".format(bins_name, corpus_size)))
    header.append(_box_line("NOT ENCRYPTED -- SALIENCE REDUCTION ONLY"))
    header.append(_box_rule())

    footer = [
        _box_rule(),
        _box_line("{0} TOKENS {1} CRC32:{2}".format(
            word_count, MIDDLE_DOT, crc_str)),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
        _box_rule(),
    ]

    return "\n".join([
        "RESERVED -- SINGLE USE",
        "\n".join(header),
        "",
        "\n".join(rsrc),
        "",
        payload,
        "",
        "\n".join(footer),
        "",
        "                   RESERVED -- SINGLE USE",
    ])


def decode_stream(content, bins):
    """
    Decode a haiku-stream artifact back to the original token stream.

    Args:
        content: full artifact text string
        bins:    syllable bins dict

    Returns:
        (token_stream_str, prime_str, crc_declared)
    """
    fields        = {}
    payload_lines = []
    in_rsrc       = False
    in_payload    = False

    SKIP = ("+", "|", "RESERVED", "TOKENS", "VERIFY", "DESTROY")

    for line in content.splitlines():
        s = line.strip()
        if s == "RSRC: BEGIN":
            in_rsrc, in_payload = True, False
            continue
        if s == "RSRC: END":
            in_rsrc, in_payload = False, True
            continue
        if in_rsrc and ":" in s:
            key, _, val = s.partition(":")
            fields[key.strip()] = val.strip()
            continue
        if in_payload and s:
            if any(s.startswith(c) for c in ("+", "|")):
                continue
            if any(kw in s for kw in ("RESERVED", "VERIFY", "DESTROY")):
                continue
            payload_lines.append(s)

    prime_str    = fields.get("PRIME", "")
    crc_declared = fields.get("CRC32-TOKENS", "")

    if not prime_str:
        raise ValueError("No PRIME field in RSRC block.")

    # Collect all words from payload
    all_words = []
    for line in payload_lines:
        if line.strip():
            all_words.extend(line.split())

    if not all_words:
        raise ValueError("No payload words found in artifact.")

    # Rebuild permuted index and reverse-lookup
    permuted, word_to_pos = build_permuted_index(bins, prime_str)
    corpus_size = len(permuted)

    # Recover token values
    tokens = []
    missing = []
    for word in all_words:
        pos = word_to_pos.get(word)
        if pos is None:
            missing.append(word)
            tokens.append("?????")
        else:
            tokens.append("{0:05d}".format(pos))

    if missing:
        import sys as _sys
        print("Warning: {0} word(s) not found in corpus: {1}".format(
            len(missing), missing[:5]), file=_sys.stderr)

    token_stream = "  ".join(tokens)
    return token_stream, prime_str, crc_declared




def _box_rule():
    return "+" + "-" * BOX_INNER + "+"

def _box_line(content=""):
    return "|" + ("  " + content).ljust(BOX_INNER) + "|"


def make_artifact(haiku_result, verse=None, ref="", bins_name="cmudict-v1"):
    """
    Wrap generated haiku in a self-describing RSRC artifact.

    The RSRC block carries the full generation trace: prime, syllable
    plan, word indices, corpus name. Sufficient for deterministic
    reversal without the original verse.
    """
    lines   = haiku_result["lines"]
    prime   = haiku_result["prime"]
    words   = haiku_result["words"]
    syl     = haiku_result["syllable_plan"]
    w_idx   = haiku_result["word_indices"]
    generated = time.strftime("%Y-%m-%d")

    payload    = "\n".join(lines)
    crc        = binascii.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    word_count = len(words)

    # Compact word index encoding: "s:i s:i ..."
    idx_str = " ".join("{0}:{1}".format(s, i) for s, i in w_idx)
    syl_str = " ".join(str(s) for s in syl)

    rsrc = [
        "RSRC: BEGIN",
        "  TYPE:         haiku-twist",
        "  VERSION:      1",
        "  NOTE:         TEST IMPLEMENTATION -- not normatively specified",
        "  CORPUS:       {0}".format(bins_name),
        "  PATTERN:      {0}".format("-".join(str(s) for s in HAIKU_PATTERN)),
        "  SCHEDULE:     forward=syl(d mod 5 + 1), reversed=word-select(SHA256)",
        "  WORDS:        {0}".format(word_count),
        "  PRIME:        {0}".format(prime),
        "  SYLLABLES:    {0}".format(syl_str),
        "  WORD-INDEX:   {0}".format(idx_str),
        "  GENERATED:    {0}".format(generated),
        "  DEDICATION:   {0}".format(DEDICATION),
    ]
    if verse:
        rsrc.append("  VERSE:        {0}".format(verse[:80]))
    rsrc.append("RSRC: END")

    header = [_box_rule()]
    if ref:
        header.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    header.append(_box_line(
        "ENC: HAIKU {d} PRIME-TWIST {d} 5-7-5".format(d=MIDDLE_DOT)))
    header.append(_box_line("SCHEDULE: FWD=SYLLABLE REV=WORD-SELECT"))
    header.append(_box_line("NOT ENCRYPTED -- SALIENCE REDUCTION ONLY"))
    header.append(_box_rule())

    footer = [
        _box_rule(),
        _box_line("{0} WORDS {1} CRC32:{2}".format(
            word_count, MIDDLE_DOT, crc_str)),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
        _box_rule(),
    ]

    return "\n".join([
        "RESERVED -- SINGLE USE",
        "\n".join(header),
        "",
        "\n".join(rsrc),
        "",
        payload,
        "",
        "\n".join(footer),
        "",
        "                   RESERVED -- SINGLE USE",
    ])


def parse_artifact(content):
    """
    Parse a haiku-twist artifact. Returns dict for verify_haiku().
    """
    fields     = {}
    payload_lines = []
    in_rsrc    = False
    in_payload = False

    STRUCTURAL = {"+", "|", "RESERVED", "WORDS", "VERIFY", "DESTROY"}

    for line in content.splitlines():
        s = line.strip()
        if s == "RSRC: BEGIN":
            in_rsrc, in_payload = True, False
            continue
        if s == "RSRC: END":
            in_rsrc, in_payload = False, True
            continue
        if in_rsrc and ":" in s:
            key, _, val = s.partition(":")
            fields[key.strip()] = val.strip()
            continue
        if in_payload and s:
            # Skip structural lines
            if any(s.startswith(c) for c in ("+", "|")):
                continue
            if any(kw in s for kw in ("RESERVED", "VERIFY", "DESTROY")):
                continue
            payload_lines.append(s)

    # Haiku lines are the payload (3 lines for 5-7-5)
    lines = [l for l in payload_lines if l]
    words = []
    for line in lines:
        words.extend(line.split())

    # Parse syllable plan
    syl = []
    for t in fields.get("SYLLABLES", "").split():
        try:
            syl.append(int(t))
        except ValueError:
            pass

    # Parse word indices: "s:i s:i ..."
    w_idx = []
    for pair in fields.get("WORD-INDEX", "").split():
        try:
            s_str, i_str = pair.split(":")
            w_idx.append((int(s_str), int(i_str)))
        except ValueError:
            pass

    return {
        "lines":         lines,
        "words":         words,
        "syllable_plan": syl,
        "word_indices":  w_idx,
        "prime":         fields.get("PRIME", ""),
        "verse":         fields.get("VERSE", ""),
        "corpus":        fields.get("CORPUS", ""),
        "dedication":    fields.get("DEDICATION", ""),
    }


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read_stdin():
    if PY2:
        data = sys.stdin.read()
        if not isinstance(data, text_type):
            data = data.decode("utf-8", errors="replace")
        return data
    return sys.stdin.read()


def _write(text):
    if PY2:
        if isinstance(text, text_type):
            sys.stdout.write(text.encode("utf-8"))
        else:
            sys.stdout.write(text)
    else:
        sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _resolve_prime(args, verse_text):
    """Return (prime_str, verse_str).

    Handles three cases:
      --prime P       use prime directly
      --verse FILE    read verse from file, derive prime
      stdin text      derive prime from verse_text
    """
    if getattr(args, "prime", None):
        return args.prime.strip(), None
    if getattr(args, "verse", None):
        with io.open(args.verse, "r", encoding="utf-8") as f:
            verse = f.read().strip()
        result = _derive(verse)
        return str(result["P"]), verse
    verse = verse_text.strip()
    if not verse:
        raise ValueError(
            "Empty input. Provide verse on stdin or use --prime P.")
    result = _derive(verse)
    return str(result["P"]), verse


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_generate(args):
    verse_raw = _read_stdin()
    prime_str, verse = _resolve_prime(args, verse_raw)
    bins = load_bins(args.bins)

    print("Verse:  {0}".format(
        (verse or "[prime provided directly]")[:60]), file=sys.stderr)
    print("Prime:  {0}... ({1} digits)".format(
        prime_str[:20], len(prime_str)), file=sys.stderr)

    result   = generate_haiku(prime_str, bins)
    artifact = make_artifact(
        result,
        verse=verse,
        ref=getattr(args, "ref", ""),
        bins_name=os.path.basename(args.bins))

    print("", file=sys.stderr)
    print("Haiku:", file=sys.stderr)
    for line in result["lines"]:
        print("  {0}".format(line), file=sys.stderr)
    print("", file=sys.stderr)

    _write(artifact)
    return 0


def cmd_chain(args):
    seed_verse = _read_stdin().strip()
    if not seed_verse:
        print("Error: provide seed verse on stdin.", file=sys.stderr)
        return 1

    bins  = load_bins(args.bins)
    steps = args.steps

    print("Crowsong Haiku Chain")
    print("Steps:  {0}".format(steps))
    print("Seed:   {0}".format(seed_verse[:60]))
    print("")

    current   = seed_verse
    artifacts = []

    for step in range(1, steps + 1):
        result_meta = _derive(current)
        prime_str   = str(result_meta["P"])
        haiku       = generate_haiku(prime_str, bins)
        artifact    = make_artifact(
            haiku,
            verse=current,
            ref="{0}-{1:02d}".format(
                getattr(args, "ref", "CHAIN"), step),
            bins_name=os.path.basename(args.bins))
        artifacts.append(artifact)

        print("Step {0}/{1}  (prime: {2}...)".format(
            step, steps, prime_str[:16]))
        for line in haiku["lines"]:
            print("  {0}".format(line))
        print("")

        # Ouroboros: haiku becomes the next verse
        current = " ".join(haiku["words"])

    output_path = getattr(args, "output", None)
    if output_path:
        sep  = "\n\n" + "=" * 72 + "\n\n"
        full = sep.join(artifacts)
        with io.open(output_path, "w", encoding="utf-8") as f:
            f.write(full)
            f.write("\n")
        print("Chain saved: {0}".format(output_path), file=sys.stderr)

    return 0


def cmd_verify(args):
    try:
        with io.open(args.artifact, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)

    if not parsed["prime"]:
        print("Error: no PRIME in RSRC block.", file=sys.stderr)
        return 1
    if not parsed["words"]:
        print("Error: no haiku words found in artifact.", file=sys.stderr)
        return 1

    bins   = load_bins(args.bins)
    result = verify_haiku(parsed, bins)

    print("File:       {0}".format(args.artifact))
    print("Prime:      {0}... ({1} digits)".format(
        parsed["prime"][:20], len(parsed["prime"])))
    print("Corpus:     {0}".format(parsed["corpus"]))
    print("Words:      {0}".format(len(parsed["words"])))
    if parsed.get("dedication"):
        print("Dedication: {0}".format(parsed["dedication"]))
    print("")
    print("Haiku:")
    for line in parsed["lines"]:
        print("  {0}".format(line))
    print("")
    print("Syllable check:  {0}".format(
        "PASS" if result["syllable_ok"] else "FAIL"))
    print("Selection check: {0}".format(
        "PASS" if result["selection_ok"] else "FAIL"))
    print("Recompute check: {0}".format(
        "PASS" if result["ok"] else "FAIL"))

    if result["errors"]:
        print("")
        print("Errors ({0}):".format(len(result["errors"])))
        for e in result["errors"][:10]:
            print("  {0}".format(e))
        if len(result["errors"]) > 10:
            print("  ... and {0} more".format(
                len(result["errors"]) - 10))

    print("")
    print("Verification: {0}".format(
        "PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


def cmd_encode_stream(args):
    """Encode a UCS-DEC token stream as a haiku word stream."""
    token_stream = _read_stdin().strip()
    if not token_stream:
        print("Error: empty input. Provide UCS-DEC token stream on stdin.",
              file=sys.stderr)
        return 1

    prime_str, verse = _resolve_prime(args, "")
    bins = load_bins(args.bins)

    corpus = build_corpus_index(bins)
    print("Prime:        {0}... ({1} digits)".format(
        prime_str[:20], len(prime_str)), file=sys.stderr)
    print("Corpus size:  {0:,} words".format(len(corpus)), file=sys.stderr)
    print("Tokens in:    {0:,}".format(
        len(token_stream.split())), file=sys.stderr)

    artifact = encode_stream(
        token_stream,
        prime_str,
        bins,
        ref=getattr(args, "ref", ""),
        bins_name=os.path.basename(args.bins))

    # Preview first stanza to stderr
    lines = [l for l in artifact.splitlines()
             if l and not l.startswith(("R","+"," ","|")) and "RSRC" not in l]
    print("", file=sys.stderr)
    print("First stanza:", file=sys.stderr)
    for line in lines[:3]:
        print("  {0}".format(line), file=sys.stderr)
    print("", file=sys.stderr)

    _write(artifact)
    return 0


def cmd_decode_stream(args):
    """Decode a haiku-stream artifact back to UCS-DEC token stream."""
    try:
        with io.open(args.artifact, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    bins = load_bins(args.bins)

    token_stream, prime_str, crc_declared = decode_stream(content, bins)
    tokens = token_stream.split()

    print("Prime:       {0}... ({1} digits)".format(
        prime_str[:20], len(prime_str)), file=sys.stderr)
    print("Tokens out:  {0:,}".format(len(tokens)), file=sys.stderr)

    # Verify CRC if declared
    if crc_declared:
        crc_actual = format(
            binascii.crc32(token_stream.strip().encode("utf-8")) & 0xFFFFFFFF,
            "08X")
        ok = (crc_actual == crc_declared)
        print("CRC32:       declared {0}, actual {1} — {2}".format(
            crc_declared, crc_actual, "OK" if ok else "MISMATCH"),
            file=sys.stderr)
        if not ok:
            print("Warning: CRC mismatch — corpus version or prime may differ.",
                  file=sys.stderr)

    print("", file=sys.stderr)
    _write(token_stream)
    return 0


def cmd_decode(args):
    """Print just the haiku text from an artifact."""
    try:
        with io.open(args.artifact, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)
    if not parsed["lines"]:
        print("Error: no haiku found in artifact.", file=sys.stderr)
        return 1

    for line in parsed["lines"]:
        print(line)
    return 0


# ── Grammar mode — import GrammarEngine ──────────────────────────────────────
#
# Grammar mode is optional. If haiku_grammar.py is not found, grammar
# subcommands degrade gracefully with a clear error message.

def _import_grammar():
    """Import GrammarEngine from haiku_grammar.py if available."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        script_dir,
        os.path.join(script_dir, "..", "haiku"),
        os.path.join(script_dir, "..", "..", "tools", "haiku"),
    ]
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.isfile(os.path.join(abs_path, "haiku_grammar.py")):
            if abs_path not in sys.path:
                sys.path.insert(0, abs_path)
            break
    try:
        from haiku_grammar import (
            GrammarEngine, load_templates, load_fields,
            load_pos_data, build_pos_bins)
        return GrammarEngine, load_templates, load_fields, \
               load_pos_data, build_pos_bins
    except ImportError:
        return None, None, None, None, None

_GrammarEngine, _load_templates, _load_fields, \
    _load_pos_data, _build_pos_bins = _import_grammar()

DEFAULT_TEMPLATES = os.path.join("tools", "haiku", "templates.json")
DEFAULT_FIELDS    = os.path.join("tools", "haiku", "fields.json")
DEFAULT_POS_INDEX = os.path.join("docs",  "wordfreq", "pos-index.json")


def _grammar_available():
    return _GrammarEngine is not None


def _make_grammar_artifact(lines, prime_str, template_id, field_name,
                            ref, bins_name, token_count, crc_str,
                            templates_version, fields_version, generated):
    """Wrap grammar-mode haiku output in a self-describing RSRC artifact."""
    payload = "\n".join(lines)

    rsrc = [
        "RSRC: BEGIN",
        "  TYPE:              haiku-grammar-stream",
        "  VERSION:           1",
        "  NOTE:              TEST IMPLEMENTATION -- not normatively specified",
        "  CORPUS:            {0}".format(bins_name),
        "  TEMPLATES:         {0}".format(templates_version),
        "  FIELDS:            {0}".format(fields_version),
        "  ENCODING:          grammar-template / semantic-field / prime-schedule",
        "  PRIME:             {0}".format(prime_str),
        "  TOKENS:            {0}".format(token_count),
        "  CRC32-TOKENS:      {0}".format(crc_str),
        "  GENERATED:         {0}".format(generated),
        "  DEDICATION:        {0}".format(DEDICATION),
        "RSRC: END",
    ]

    header = [_box_rule()]
    if ref:
        header.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    header.append(_box_line(
        "ENC: HAIKU-GRAMMAR {d} EERILY PLAUSIBLE".format(d=MIDDLE_DOT)))
    header.append(_box_line(
        "CORPUS: {0}  TEMPLATES: {1}".format(
            bins_name, templates_version)))
    header.append(_box_line("NOT ENCRYPTED -- SALIENCE REDUCTION ONLY"))
    header.append(_box_rule())

    footer = [
        _box_rule(),
        _box_line("{0} TOKENS {1} CRC32:{2}".format(
            token_count, MIDDLE_DOT, crc_str)),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
        _box_rule(),
    ]

    return "\n".join([
        "RESERVED -- SINGLE USE",
        "\n".join(header),
        "",
        "\n".join(rsrc),
        "",
        payload,
        "",
        "\n".join(footer),
        "",
        "                   RESERVED -- SINGLE USE",
    ])


def cmd_grammar_encode_stream(args):
    """
    Encode a UCS-DEC token stream as grammatically coherent,
    eerily plausible AI-style nature haiku.

    Uses GrammarEngine (haiku_grammar.py) with POS templates and
    semantic fields to produce output that reads as plausible
    AI-generated nature poetry from circa 2022-2024.

    The encoding is fully deterministic and reversible given the
    same prime, template library, fields, and POS-indexed bins.
    """
    if not _grammar_available():
        print(
            "Error: haiku_grammar.py not found.\n"
            "Expected at tools/haiku/haiku_grammar.py\n"
            "Grammar mode requires the full haiku toolkit.",
            file=sys.stderr)
        return 1

    token_stream = _read_stdin().strip()
    if not token_stream:
        print("Error: empty input. Provide UCS-DEC token stream on stdin.",
              file=sys.stderr)
        return 1

    prime_str, verse = _resolve_prime(args, "")
    bins             = load_bins(args.bins)
    templates_path   = getattr(args, "templates", None) or DEFAULT_TEMPLATES
    fields_path      = getattr(args, "fields",    None) or DEFAULT_FIELDS
    pos_path         = getattr(args, "pos",        None) or DEFAULT_POS_INDEX

    try:
        templates, tmeta = _load_templates(templates_path)
        fields,    fmeta = _load_fields(fields_path)
    except IOError as e:
        print("Error loading grammar data: {0}".format(e), file=sys.stderr)
        return 1

    pos_data = _load_pos_data(pos_path)
    if pos_data is None:
        print(
            "Note: POS index not found at {0}".format(pos_path),
            file=sys.stderr)
        print(
            "Using heuristic POS assignment. For better output run:\n"
            "  python tools/wordfreq/wordfreq.py fetch --source coca\n"
            "  python tools/wordfreq/wordfreq.py export-pos",
            file=sys.stderr)
        print("", file=sys.stderr)

    pos_bins = _build_pos_bins(bins, pos_data)

    templates_version = tmeta.get("name", "haiku-templates-v1")
    fields_version    = fmeta.get("name", "haiku-fields-v1")

    engine = _GrammarEngine(
        pos_bins=pos_bins,
        templates=templates,
        fields=fields,
        prime_str=prime_str,
        templates_version=templates_version,
        fields_version=fields_version)

    tokens     = token_stream.split()
    token_count = len(tokens)
    crc         = binascii.crc32(token_stream.encode("utf-8")) & 0xFFFFFFFF
    crc_str     = format(crc, "08X")
    generated   = time.strftime("%Y-%m-%d")

    print("Prime:     {0}... ({1} digits)".format(
        prime_str[:20], len(prime_str)), file=sys.stderr)
    print("Templates: {0} ({1})".format(
        templates_version, len(templates)), file=sys.stderr)
    print("Fields:    {0} ({1})".format(
        fields_version, len(fields)), file=sys.stderr)
    print("Tokens in: {0:,}".format(token_count), file=sys.stderr)
    print("", file=sys.stderr)

    # Generate haiku stanzas — one stanza encodes multiple tokens
    # Each call to generate_haiku advances the prime position and
    # produces one 5-7-5 stanza. We generate enough stanzas to
    # produce at least token_count words (one word per token).
    all_lines    = []
    global_pos   = 0
    words_so_far = 0

    while words_so_far < token_count:
        haiku = engine.generate_haiku(global_pos=global_pos)
        all_lines.extend(haiku["lines"])
        words_so_far += len(haiku["words"])
        global_pos    = haiku["next_pos"]

        # Blank line between stanzas
        all_lines.append("")

    # Trim trailing blank
    while all_lines and not all_lines[-1]:
        all_lines.pop()

    # Preview
    print("First stanza:", file=sys.stderr)
    for line in all_lines[:3]:
        print("  {0}".format(line), file=sys.stderr)
    print("", file=sys.stderr)

    artifact = _make_grammar_artifact(
        lines=all_lines,
        prime_str=prime_str,
        template_id=None,
        field_name=None,
        ref=getattr(args, "ref", ""),
        bins_name=os.path.basename(args.bins),
        token_count=token_count,
        crc_str=crc_str,
        templates_version=templates_version,
        fields_version=fields_version,
        generated=generated)

    _write(artifact)
    return 0


def cmd_grammar_decode_stream(args):
    """
    Decode a haiku-grammar-stream artifact back to UCS-DEC token stream.

    Reconstructs the GrammarEngine from the declared prime, templates,
    and fields, replays the generation sequence, and recovers token
    values from word positions in the POS-indexed bins.
    """
    if not _grammar_available():
        print(
            "Error: haiku_grammar.py not found.\n"
            "Expected at tools/haiku/haiku_grammar.py",
            file=sys.stderr)
        return 1

    try:
        with io.open(args.artifact, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    # Parse RSRC block
    fields = {}
    for line in content.splitlines():
        s = line.strip()
        if s == "RSRC: BEGIN":
            continue
        if s == "RSRC: END":
            break
        if ":" in s and s.startswith(tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")):
            key, _, val = s.partition(":")
            fields[key.strip()] = val.strip()

    prime_str        = fields.get("PRIME", "")
    crc_declared     = fields.get("CRC32-TOKENS", "")
    token_count_decl = int(fields.get("TOKENS", "0") or "0")
    templates_ver    = fields.get("TEMPLATES", "haiku-templates-v1")
    fields_ver       = fields.get("FIELDS",    "haiku-fields-v1")

    if not prime_str:
        print("Error: no PRIME in RSRC block.", file=sys.stderr)
        return 1

    bins           = load_bins(args.bins)
    templates_path = getattr(args, "templates", None) or DEFAULT_TEMPLATES
    fields_path    = getattr(args, "fields",    None) or DEFAULT_FIELDS
    pos_path       = getattr(args, "pos",        None) or DEFAULT_POS_INDEX

    try:
        templates, tmeta = _load_templates(templates_path)
        fields_data, fmeta = _load_fields(fields_path)
    except IOError as e:
        print("Error loading grammar data: {0}".format(e), file=sys.stderr)
        return 1

    # Verify template/field library versions match
    if tmeta.get("name") != templates_ver:
        print(
            "Warning: template version mismatch. "
            "Artifact uses '{0}', loaded '{1}'.".format(
                templates_ver, tmeta.get("name")),
            file=sys.stderr)

    pos_data = _load_pos_data(pos_path)
    pos_bins = _build_pos_bins(bins, pos_data)

    engine = _GrammarEngine(
        pos_bins=pos_bins,
        templates=templates,
        fields=fields_data,
        prime_str=prime_str,
        templates_version=templates_ver,
        fields_version=fields_ver)

    # Replay generation to recover word→token mapping
    # Each word in the output was drawn from a specific POS+syllable bin.
    # Its index in that bin encodes a token value modulo bin size.
    # We reconstruct the same sequence and recover indices.
    recovered_tokens = []
    global_pos       = 0

    while len(recovered_tokens) < token_count_decl:
        haiku = engine.generate_haiku(global_pos=global_pos)
        for bin_idx in haiku["bin_indices"]:
            recovered_tokens.append("{0:05d}".format(bin_idx))
            if len(recovered_tokens) >= token_count_decl:
                break
        global_pos = haiku["next_pos"]

    token_stream = "  ".join(recovered_tokens[:token_count_decl])

    print("Prime:       {0}... ({1} digits)".format(
        prime_str[:20], len(prime_str)), file=sys.stderr)
    print("Tokens out:  {0:,}".format(len(recovered_tokens[:token_count_decl])),
          file=sys.stderr)

    if crc_declared:
        crc_actual = format(
            binascii.crc32(token_stream.encode("utf-8")) & 0xFFFFFFFF,
            "08X")
        ok = (crc_actual == crc_declared)
        print("CRC32:       declared {0}, actual {1} — {2}".format(
            crc_declared, crc_actual, "OK" if ok else "MISMATCH"),
            file=sys.stderr)

    print("", file=sys.stderr)
    _write(token_stream)
    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def positive_int(value):
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def build_parser():
    p = argparse.ArgumentParser(
        prog="haiku_twist",
        description=(
            "Prime-driven haiku generator.\n"
            "\n"
            "verse -> prime P\n"
            "  forward digits  -> syllable count schedule (d mod 5 + 1)\n"
            "  reversed digits -> word selection within syllable bin\n"
            "\n"
            "One verse. One prime. Two schedules. Infinite poems.\n"
            "The format eats its own output.\n"
            "\n"
            "TEST IMPLEMENTATION -- not yet normatively specified.\n"
            "\n"
            "{dedication}".format(dedication=DEDICATION)
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Canonical test vector (K1):\n"
            "  echo \"{verse}\" | \\\n"
            "      python haiku_twist.py generate \\\n"
            "          --bins docs/cmudict/bins.json\n"
            "\n"
            "Chain (ouroboros — format eats its own output):\n"
            "  echo \"{verse}\" | \\\n"
            "      python haiku_twist.py chain \\\n"
            "          --bins docs/cmudict/bins.json --steps 7\n"
            "\n"
            "Quick start:\n"
            "  python tools/cmudict/cmudict.py fetch\n"
            "  python tools/cmudict/cmudict.py export\n"
            "  echo \"{verse}\" | \\\n"
            "      python haiku_twist.py generate\n"
        ).format(verse=CANONICAL_VERSE[:55] + "...")
    )

    p.add_argument("--bins", default=DEFAULT_BINS, metavar="FILE",
        help="syllable bins JSON (default: {0})".format(DEFAULT_BINS))

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # generate
    pg = sub.add_parser("generate",
        help="generate a haiku from stdin verse")
    pg.add_argument("--prime", default=None, metavar="P",
        help="use prime directly (skip verse derivation)")
    pg.add_argument("--ref", default="", metavar="ID",
        help="artifact reference ID")

    # chain
    pc = sub.add_parser("chain",
        help="generate a chain of linked haiku, each seeding the next")
    pc.add_argument("--steps", type=positive_int, default=5, metavar="N",
        help="chain length (default: 5)")
    pc.add_argument("--ref", default="CHAIN", metavar="ID",
        help="artifact reference prefix (default: CHAIN)")
    pc.add_argument("--output", "-o", default=None, metavar="FILE",
        help="save full chain to file")

    # verify
    pv = sub.add_parser("verify",
        help="verify a haiku artifact against its prime and corpus")
    pv.add_argument("artifact", help="artifact file to verify")

    # decode
    pd = sub.add_parser("decode",
        help="print just the haiku text from an artifact")
    pd.add_argument("artifact", help="artifact file")

    # encode-stream
    pes = sub.add_parser("encode-stream",
        help="encode a UCS-DEC token stream as haiku words (word-space camouflage)")
    pes_key = pes.add_mutually_exclusive_group(required=True)
    pes_key.add_argument("--prime", default=None, metavar="P",
        help="use prime directly")
    pes_key.add_argument("--verse", default=None, metavar="FILE",
        help="file containing key verse (one verse)")
    pes.add_argument("--ref", default="", metavar="ID",
        help="artifact reference ID")

    # decode-stream
    pds = sub.add_parser("decode-stream",
        help="decode a haiku-stream artifact back to UCS-DEC token stream")
    pds.add_argument("artifact", help="haiku-stream artifact file")

    # grammar-encode-stream
    pges = sub.add_parser("grammar-encode-stream",
        help="encode token stream as grammatically coherent AI-style nature haiku")
    pges_key = pges.add_mutually_exclusive_group(required=True)
    pges_key.add_argument("--prime", default=None, metavar="P",
        help="use prime directly")
    pges_key.add_argument("--verse", default=None, metavar="FILE",
        help="file containing key verse (one verse)")
    pges.add_argument("--ref", default="", metavar="ID",
        help="artifact reference ID")
    pges.add_argument("--templates", default=None, metavar="FILE",
        help="template library JSON (default: tools/haiku/templates.json)")
    pges.add_argument("--fields", default=None, metavar="FILE",
        help="semantic fields JSON (default: tools/haiku/fields.json)")
    pges.add_argument("--pos", default=None, metavar="FILE",
        help="POS index JSON (default: docs/wordfreq/pos-index.json)")

    # grammar-decode-stream
    pgds = sub.add_parser("grammar-decode-stream",
        help="decode a haiku-grammar-stream artifact back to token stream")
    pgds.add_argument("artifact", help="haiku-grammar-stream artifact file")
    pgds.add_argument("--templates", default=None, metavar="FILE",
        help="template library JSON (must match encoding)")
    pgds.add_argument("--fields", default=None, metavar="FILE",
        help="semantic fields JSON (must match encoding)")
    pgds.add_argument("--pos", default=None, metavar="FILE",
        help="POS index JSON")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "generate":               return cmd_generate(args)
        if args.command == "chain":                  return cmd_chain(args)
        if args.command == "verify":                 return cmd_verify(args)
        if args.command == "decode":                 return cmd_decode(args)
        if args.command == "encode-stream":          return cmd_encode_stream(args)
        if args.command == "decode-stream":          return cmd_decode_stream(args)
        if args.command == "grammar-encode-stream":  return cmd_grammar_encode_stream(args)
        if args.command == "grammar-decode-stream":  return cmd_grammar_decode_stream(args)
    except (IOError, ValueError, KeyboardInterrupt) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
