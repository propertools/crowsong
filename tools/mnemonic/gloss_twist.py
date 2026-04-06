#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gloss_twist.py — Gloss Layer for FDS token streams

The Gloss Layer addresses the structural limitation of CCL prime-twist for
high-codepoint scripts (Arabic, CJK, Hangul, Devanagari, Hebrew, Thai, etc.).

PROBLEM:

    UCS-DEC encodes each character as its Unicode code point. High-codepoint
    scripts produce large token values. CCL's feasibility rule is:

        base^WIDTH > token_value

    For a CJK token at value 30,000 (WIDTH/5):
        base 2: 2^5 =     32 -- infeasible
        base 3: 3^5 =    243 -- infeasible
        ...
        base 8: 8^5 = 32,768 -- infeasible
        base 9: 9^5 = 59,049 -- feasible (only one!)

    Only base 9 is ever feasible for CJK. CCL twist rate is structurally
    capped at ~11% per pass for CJK text. The entropy gain is negligible.

CONSTRUCTION:

    The Gloss Layer re-encodes each token value in a base-52 alphabet of
    mixed-case Latin letters, producing WIDTH=3 symbol tokens. Because
    52^3 = 140,608 > 99,999, every WIDTH/5 FDS token fits in exactly 3
    gloss symbols. The gloss symbol code points (65-122, ASCII A-Z a-z)
    are small enough that CCL bases 3-9 are ALL feasible on every token.

    The alphabet is a key-derived permutation of the 52-letter base set,
    seeded from the REVERSED digits of the prime. This gives:

        Forward prime  P  -> CCL key schedule (base-switching)
        Reversed prime P' -> Gloss alphabet permutation

    One verse. One prime. Two independent, non-interfering schedules.

    Pipeline:

        plaintext
          -> UCS-DEC encode                (ucs_dec_tool.py)
          -> Gloss Layer   [P reversed]    (this tool)
          -> CCL prime-twist [P forward]   (prime_twist.py)
          -> UCS-DEC output

    Reversal:

        CCL output
          -> CCL untwist   [P forward]     (prime_twist.py unstack)
          -> Gloss untwist [P reversed]    (this tool, ungloss)
          -> original UCS-DEC token stream

ENTROPY IMPACT (canonical test, 3-pass CCL):

    Script          CCL3 alone   Gloss+CCL3   Delta
    English (poem)   8.16         7.56        -0.60  (CCL alone preferred)
    Russian          6.83         7.28        +0.45
    Arabic           6.40         7.05        +0.65
    Hebrew           6.40         7.02        +0.62
    Hindi            6.61         7.09        +0.48
    Chinese          5.93         7.29        +1.36  (largest gain)
    Japanese         6.11         7.24        +1.13
    Korean           6.17         7.47        +1.30

    The Gloss Layer is operationally necessary for any script with code
    points above U+0800. For ASCII/Latin text, CCL3 alone is preferred.

    prime_twist.py will warn and prompt when it detects >= 30% non-ASCII
    tokens. Use --no-symbol-check to suppress for known-ASCII pipelines.

KEY MODE:

    The same prime is always used for both layers. There is no "independent"
    key mode — the reversal construction derives the gloss key deterministically
    from the CCL key. One verse, one prime, two schedules.

ALPHABET:

    Base alphabet: ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
    Width: 3 (52^3 = 140,608 > 99,999)
    Permutation: keyed Fisher-Yates shuffle seeded from SHA256(reversed(P))

    The permutation is declared in the RSRC block (GLOSS-ALPHA field) so
    that the receiver can reconstruct it from the prime alone.

NAMING:

    A gloss (philology) is a brief rendering of one text in the characters
    of another — a marginal annotation translating a hard word into a
    familiar one. This layer glosses the input script into a key-derived
    Latin alphabet before CCL runs.

Usage:
    python gloss_twist.py gloss   [--prime P | --verse FILE]
                                  [--ref ID] [--med MEDIUM]
    python gloss_twist.py ungloss <infile>
    python gloss_twist.py info    <infile>

Examples:
    # Recommended pipeline for Arabic/CJK/Hangul/etc.:
    cat arabic_payload.txt | \\
        python gloss_twist.py gloss --verse key.txt --ref GLOSS1 | \\
        python prime_twist.py stack --verse-file verses.txt --ref CCL3

    # Reversal:
    python prime_twist.py unstack artifact.txt | \\
        python gloss_twist.py ungloss /dev/stdin

    # Inspect gloss artifact:
    python gloss_twist.py info artifact.txt

Compatibility: Python 2.7+ / 3.x
Dependencies: mnemonic.py (in same directory)
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import hashlib
import io
import random
import sys
import time

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
    to_chr    = unichr   # noqa: F821
else:
    text_type = str
    to_chr    = chr

from mnemonic import derive  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_ALPHABET  = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
GLOSS_BASE     = len(BASE_ALPHABET)   # 52
GLOSS_WIDTH    = 3                    # 52^3 = 140,608 > 99,999
GLOSS_MAX_VAL  = GLOSS_BASE ** GLOSS_WIDTH  # 140,608

BOX_INNER      = 41
MIDDLE_DOT     = "\u00b7"
DESTROY_FLAG   = "IF COUNT FAILS: DESTROY IMMEDIATELY"


# ── Key derivation ────────────────────────────────────────────────────────────

def _prime_to_alphabet(prime_str):
    """
    Derive a permuted alphabet from a prime string.

    Uses the REVERSED digit sequence of the prime as the seed, giving a
    schedule that is completely independent from the forward CCL schedule
    while requiring no additional key material.

    Returns: list of 52 characters (permuted BASE_ALPHABET)
    """
    reversed_prime = prime_str[::-1]
    seed = int(hashlib.sha256(reversed_prime.encode("utf-8")).hexdigest(), 16)
    rng  = random.Random(seed)
    alpha = list(BASE_ALPHABET)
    rng.shuffle(alpha)
    return alpha


def _alphabet_index(alpha):
    """Build char -> index reverse map for an alphabet list."""
    return {ch: i for i, ch in enumerate(alpha)}


# ── Encoding / decoding ───────────────────────────────────────────────────────

def _encode_value(val, alpha):
    """
    Express val in base GLOSS_BASE using the given alphabet.
    Returns list of GLOSS_WIDTH characters (MSB first).
    """
    base = GLOSS_BASE
    if val == 0:
        return [alpha[0]] * GLOSS_WIDTH
    digits = []
    tmp = val
    while tmp > 0:
        digits.append(alpha[tmp % base])
        tmp //= base
    while len(digits) < GLOSS_WIDTH:
        digits.append(alpha[0])
    return list(reversed(digits))


def _decode_value(chars, alpha_idx):
    """
    Recover integer from GLOSS_WIDTH characters using the alphabet index.
    """
    base   = GLOSS_BASE
    result = 0
    for ch in chars:
        result = result * base + alpha_idx[ch]
    return result


# ── Core transform ────────────────────────────────────────────────────────────

def gloss(token_stream, prime_str, fds_width=5):
    """
    Apply the Gloss Layer to a UCS-DEC token stream.

    Each input token value is re-encoded in a key-derived base-52 alphabet,
    producing GLOSS_WIDTH output tokens per input token. Output tokens are
    the ASCII code points of the gloss symbols, UCS-DEC encoded.

    Args:
        token_stream: whitespace-separated UCS-DEC token string
        prime_str:    decimal string of key prime P
        fds_width:    FDS field width of input tokens (default: 5)

    Returns:
        (output_tokens, alpha)
        output_tokens: list of len(input)*GLOSS_WIDTH zero-padded strings
        alpha:         the permuted alphabet used (for RSRC block)
    """
    alpha  = _prime_to_alphabet(prime_str)
    tokens = token_stream.split()

    if not tokens:
        return [], alpha

    output_tokens = []
    for tok in tokens:
        val  = int(tok)
        if val >= GLOSS_MAX_VAL:
            raise ValueError(
                "Token value {0} exceeds maximum representable value "
                "{1} in base {2} width {3}. Use WIDTH/7 for tokens "
                "above code point U+{4:04X}.".format(
                    val, GLOSS_MAX_VAL - 1, GLOSS_BASE, GLOSS_WIDTH,
                    GLOSS_MAX_VAL - 1))
        chars = _encode_value(val, alpha)
        for ch in chars:
            output_tokens.append("{0:0{w}d}".format(ord(ch), w=fds_width))

    return output_tokens, alpha


def ungloss(output_tokens, prime_str, fds_width=5):
    """
    Reverse the Gloss Layer. Recovers original UCS-DEC token stream.

    Args:
        output_tokens: list of GLOSS_WIDTH*N UCS-DEC token strings
        prime_str:     decimal string of key prime P
        fds_width:     FDS field width (default: 5)

    Returns:
        List of original UCS-DEC token strings.
    """
    alpha     = _prime_to_alphabet(prime_str)
    alpha_idx = _alphabet_index(alpha)
    n_input   = len(output_tokens) // GLOSS_WIDTH
    recovered = []

    for i in range(n_input):
        group = output_tokens[i * GLOSS_WIDTH : (i + 1) * GLOSS_WIDTH]
        chars = [to_chr(int(tok)) for tok in group]
        val   = _decode_value(chars, alpha_idx)
        recovered.append("{0:0{w}d}".format(val, w=fds_width))

    return recovered


# ── Artifact format ───────────────────────────────────────────────────────────

def _box_rule():
    return "+" + "-" * BOX_INNER + "+"


def _box_line(content=""):
    return "|" + ("  " + content).ljust(BOX_INNER) + "|"


def make_artifact(output_tokens, alpha, prime_str,
                  fds_width=5, ref="", med="PAPER"):
    """
    Wrap glossed token stream in a self-describing FDS Print Profile artifact.
    """
    rows    = []
    col     = 6
    for i in range(0, len(output_tokens), col):
        rows.append("  ".join(output_tokens[i:i + col]))
    payload = "\n".join(rows)

    pad        = "0" * fds_width
    real_count = len([t for t in output_tokens if t != pad])
    crc        = binascii.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    generated  = time.strftime("%Y-%m-%d")
    alpha_str  = "".join(alpha)

    enc_line = (
        "ENC: UCS {d} DEC {d} COL/{c} {d} PAD/{p} {d} WIDTH/{w}".format(
            d=MIDDLE_DOT, c=col, p=pad, w=fds_width))
    cnt_line = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    rsrc_lines = [
        "RSRC: BEGIN",
        "  TYPE:         gloss-twist",
        "  VERSION:      1",
        "  NOTE:         TEST IMPLEMENTATION -- not normatively specified",
        "  GLOSS-BASE:   {0}".format(GLOSS_BASE),
        "  GLOSS-WIDTH:  {0}".format(GLOSS_WIDTH),
        "  GLOSS-ALPHA:  {0}".format(alpha_str),
        "  PRIME:        {0}".format(prime_str),
        "  INPUT-TOKENS: {0}".format(len(output_tokens) // GLOSS_WIDTH),
        "  OUTPUT-TOKENS:{0}".format(len(output_tokens)),
        "  FDS-WIDTH:    {0}".format(fds_width),
        "  GENERATED:    {0}".format(generated),
        "RSRC: END",
    ]

    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    header_lines += [
        _box_line(enc_line),
        _box_line("MED: {0}".format(med)),
        _box_line("GLOSS: base{0}/w{1} {2} KEY-DERIVED".format(
            GLOSS_BASE, GLOSS_WIDTH, MIDDLE_DOT)),
        _box_rule(),
    ]

    footer_lines = [
        _box_rule(),
        _box_line(cnt_line),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
        _box_rule(),
    ]

    return "\n".join([
        "RESERVED -- SINGLE USE",
        "\n".join(header_lines),
        "",
        "\n".join(rsrc_lines),
        "",
        payload,
        "",
        "\n".join(footer_lines),
        "",
        "                   RESERVED -- SINGLE USE",
    ])


def parse_artifact(content):
    """Parse a gloss-twist artifact. Returns dict."""
    fields        = {}
    output_tokens = []
    in_rsrc       = False
    in_payload    = False

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
        if in_payload:
            toks = s.split()
            if toks and all(t.isdigit() for t in toks):
                output_tokens.extend(toks)

    fds_width = int(fields.get("FDS-WIDTH", "5"))
    n_input   = int(fields.get(
        "INPUT-TOKENS", str(len(output_tokens) // GLOSS_WIDTH)))

    return {
        "prime":         fields.get("PRIME", ""),
        "gloss_alpha":   fields.get("GLOSS-ALPHA", ""),
        "gloss_base":    int(fields.get("GLOSS-BASE", str(GLOSS_BASE))),
        "gloss_width":   int(fields.get("GLOSS-WIDTH", str(GLOSS_WIDTH))),
        "fds_width":     fds_width,
        "n_input":       n_input,
        "output_tokens": output_tokens,
    }


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _read_stdin():
    if PY2:
        data = sys.stdin.read()
        if not isinstance(data, text_type):
            data = data.decode("utf-8")
        return data
    return sys.stdin.read()


def _write_stdout(text):
    if PY2:
        if isinstance(text, text_type):
            sys.stdout.write(text.encode("utf-8"))
        else:
            sys.stdout.write(text)
    else:
        sys.stdout.write(text)


def _load_prime(args):
    """Resolve prime from --prime or --verse."""
    if getattr(args, "prime", None):
        return args.prime.strip()
    if getattr(args, "verse", None):
        with io.open(args.verse, "r", encoding="utf-8") as f:
            verse = f.read().rstrip("\r\n")
        result = derive(verse)
        return str(result["P"])
    raise ValueError("--prime or --verse required")


# ── Script fingerprint analysis (mirrors prime_twist.py) ─────────────────────

SCRIPT_BLOCKS = [
    (592,   687,   "Latin Extended / IPA"),
    (880,   1023,  "Greek and Coptic"),
    (1024,  1279,  "Cyrillic"),
    (1424,  1535,  "Hebrew"),
    (1536,  1791,  "Arabic"),
    (2304,  2431,  "Devanagari"),
    (2432,  2559,  "Bengali"),
    (3584,  3711,  "Thai"),
    (4352,  4607,  "Hangul Jamo"),
    (4608,  4991,  "Ethiopic"),
    (19968, 40959, "CJK Unified Ideographs"),
    (40960, 42127, "Yi"),
    (44032, 55203, "Hangul Syllables"),
]


def _script_risk(token_stream):
    """Return (risk_str, high_fraction, dominant_block)."""
    import collections as _c
    tokens = token_stream.split()
    if not tokens:
        return "low", 0.0, "None"
    values   = [int(t) for t in tokens if t.isdigit()]
    total    = len(values)
    high_bmp = sum(1 for v in values if v > 591)
    clusters = _c.Counter()
    for v in values:
        if v <= 591:
            continue
        label = "Other non-ASCII"
        for lo, hi, name in SCRIPT_BLOCKS:
            if lo <= v <= hi:
                label = name
                break
        clusters[label] += 1
    high_frac = high_bmp / total if total else 0.0
    dominant  = clusters.most_common(1)[0][0] if clusters else "None"
    risk = ("high"   if high_frac >= 0.30 else
            "medium" if high_frac >= 0.10 else "low")
    return risk, high_frac, dominant


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_gloss(args):
    data = _read_stdin().strip()
    if not data:
        print("Error: empty input", file=sys.stderr)
        return 1

    # Informational script risk note (not a block — gloss handles it)
    risk, frac, dominant = _script_risk(data)
    if risk in ("high", "medium"):
        print(
            "Note: {:.0f}% non-ASCII tokens ({}) — "
            "Gloss layer will maximise CCL effectiveness.".format(
                100 * frac, dominant),
            file=sys.stderr)

    prime_str = _load_prime(args)
    fds_width = getattr(args, "fds_width", 5)

    try:
        output_tokens, alpha = gloss(data, prime_str, fds_width=fds_width)
    except ValueError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    n_in  = len(data.split())
    n_out = len(output_tokens)
    print(
        "Gloss: {0} tokens -> {1} tokens ({2}x expansion, "
        "base {3}, width {4})".format(
            n_in, n_out, GLOSS_WIDTH, GLOSS_BASE, GLOSS_WIDTH),
        file=sys.stderr)
    print(
        "  Alphabet (key-derived): {0}".format("".join(alpha)),
        file=sys.stderr)
    print(
        "  All output code points in ASCII range (65-122) -- "
        "CCL bases 3-9 fully feasible.",
        file=sys.stderr)

    artifact = make_artifact(
        output_tokens, alpha, prime_str,
        fds_width=fds_width,
        ref=getattr(args, "ref", ""),
        med=getattr(args, "med", "PAPER"))

    _write_stdout(artifact)
    if not artifact.endswith("\n"):
        _write_stdout("\n")
    return 0


def cmd_ungloss(args):
    try:
        with io.open(args.infile, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)
    if not parsed["output_tokens"]:
        print("Error: no payload tokens found in artifact", file=sys.stderr)
        return 1
    if not parsed["prime"]:
        print("Error: PRIME field missing from RSRC block", file=sys.stderr)
        return 1

    recovered = ungloss(
        parsed["output_tokens"],
        parsed["prime"],
        fds_width=parsed["fds_width"])

    print(
        "Ungloss: {0} tokens -> {1} tokens".format(
            len(parsed["output_tokens"]), len(recovered)),
        file=sys.stderr)

    _write_stdout("  ".join(recovered))
    _write_stdout("\n")
    return 0


def cmd_info(args):
    try:
        with io.open(args.infile, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)
    print("File:          {0}".format(args.infile))
    print("Type:          gloss-twist")
    print("Gloss base:    {0}".format(parsed["gloss_base"]))
    print("Gloss width:   {0}".format(parsed["gloss_width"]))
    print("FDS width:     {0}".format(parsed["fds_width"]))
    print("Input tokens:  {0}".format(parsed["n_input"]))
    print("Output tokens: {0}".format(len(parsed["output_tokens"])))
    print("Expansion:     {0}x".format(parsed["gloss_width"]))
    if parsed["gloss_alpha"]:
        print("Alphabet:      {0}".format(parsed["gloss_alpha"]))
    print("Prime (P):     {0}...".format(parsed["prime"][:20]))
    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Gloss Layer for FDS token streams.\n"
            "Re-encodes high-codepoint tokens in a key-derived base-52\n"
            "alphabet, enabling maximum CCL twist rates for Arabic, CJK,\n"
            "Hangul, Devanagari, Hebrew, Thai, and other non-Latin scripts.\n"
            "\n"
            "TEST IMPLEMENTATION -- not yet normatively specified.\n"
            "\n"
            "Key derivation: one prime, two schedules.\n"
            "  Reversed prime -> gloss alphabet permutation\n"
            "  Forward prime  -> CCL base-switching (prime_twist.py)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Pipeline (Arabic/CJK/Hangul/etc.):\n"
            "  cat payload.txt | \\\n"
            "      python gloss_twist.py gloss --verse key.txt | \\\n"
            "      python prime_twist.py stack \\\n"
            "          --verse-file verses.txt --no-symbol-check\n"
            "\n"
            "Reversal:\n"
            "  python prime_twist.py unstack artifact.txt | \\\n"
            "      python gloss_twist.py ungloss /dev/stdin\n"
            "\n"
            "Entropy impact (3-pass CCL, canonical test):\n"
            "  Chinese:  CCL3=5.93 -> Gloss+CCL3=7.29 (+1.36 bits/token)\n"
            "  Korean:   CCL3=6.17 -> Gloss+CCL3=7.47 (+1.30 bits/token)\n"
            "  Japanese: CCL3=6.11 -> Gloss+CCL3=7.24 (+1.13 bits/token)\n"
            "  Arabic:   CCL3=6.40 -> Gloss+CCL3=7.05 (+0.65 bits/token)\n"
        )
    )

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # gloss
    pg = sub.add_parser("gloss",
        help="apply Gloss Layer to stdin UCS-DEC token stream")
    key_group = pg.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--prime", metavar="P",
        help="prime key (decimal string)")
    key_group.add_argument("--verse", metavar="FILE",
        help="file containing key verse (one verse per file)")
    pg.add_argument("--fds-width", dest="fds_width", type=int, default=5,
        metavar="N",
        help="FDS field width of input tokens (default: 5)")
    pg.add_argument("--ref", default="", metavar="ID",
        help="artifact reference ID")
    pg.add_argument("--med", default="PAPER", metavar="MEDIUM",
        help="transport medium label (default: PAPER)")

    # ungloss
    pu = sub.add_parser("ungloss",
        help="reverse Gloss Layer; emit bare UCS-DEC token stream")
    pu.add_argument("infile",
        help="gloss-twist artifact file (use /dev/stdin for pipe)")

    # info
    pi = sub.add_parser("info",
        help="display artifact parameters without reversing")
    pi.add_argument("infile",
        help="gloss-twist artifact file")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "gloss":   return cmd_gloss(args)
        if args.command == "ungloss": return cmd_ungloss(args)
        if args.command == "info":    return cmd_info(args)
    except (ValueError, IOError, KeyboardInterrupt) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
