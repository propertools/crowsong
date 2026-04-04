#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prime_twist.py — Channel Camouflage Layer: prime-derived base-switching

A test implementation of the prime-twisting construction for the
Channel Camouflage Layer (CCL). Not a production cryptographic tool.

Construction:

    For a UCS-DEC token stream and a prime P:
      - Use the decimal digits of P as a key schedule (ouroboros)
      - For each token tᵢ at position i:
          digit  = P_digits[i mod len(P_digits)]
          base   = digit   (if digit >= 2 and base^width > token_value)
                 = 10      (otherwise — fallback, no change)
          output = token value represented in base, zero-padded to width
      - Record the actual base used per position in the RSRC twist-map

    The twist-map is stored in the RSRC block of the output artifact.
    Decoding reads the twist-map and applies the inverse base conversion.

    The twisted token stream is still valid UCS-DEC: decimal digits,
    whitespace-separated, fixed width. It is not encrypted. It is
    statistically less recognisable than uniform base-10 encoding.

    CCL provides no cryptographic confidentiality or integrity protection.
    See draft-darley-shard-bundle-01 for normative security properties.

Usage:
    python prime_twist.py twist   --prime <P> [--width N] [--ref ID]
    python prime_twist.py untwist <infile>

Input is read from stdin (bare UCS-DEC token stream).
Output is a self-describing FDS Print Profile artifact.

Examples:
    # Twist using a prime derived from a verse
    cat archive/flash-paper-SI-2084-FP-001-payload.txt | \\
      python prime_twist.py twist --prime 74851412...701 > twisted.txt

    # Untwist
    python prime_twist.py untwist twisted.txt

    # Full pipeline: verse -> prime -> twist
    echo "Factoring primes" | python verse_to_prime.py derive --ref K1 > k1.txt
    PRIME=$(grep '  P:' k1.txt | awk '{print $2}')
    cat archive/flash-paper-SI-2084-FP-001-payload.txt | \\
      python prime_twist.py twist --prime $PRIME --ref CCL-TEST > twisted.txt
    python prime_twist.py untwist twisted.txt | \\
      python ucs_dec_tool.py -d

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT

NOTE: This is a test implementation. The CCL construction and
twist-map format are not yet normatively specified. The interface
and file format may change in future revisions.
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import sys
import time
import unicodedata

PY2 = (sys.version_info[0] == 2)

if PY2:
    text_type = unicode  # noqa: F821
    to_chr    = unichr   # noqa: F821
else:
    text_type = str
    to_chr    = chr

_DIGIT_CHARS = "0123456789"

BOX_INNER    = 41
MIDDLE_DOT   = "\u00b7"
DESTROY_FLAG = "IF COUNT FAILS: DESTROY IMMEDIATELY"


# ── Base conversion ───────────────────────────────────────────────────────────

def _to_base(n, base, width):
    """Convert non-negative int n to base, zero-padded to width."""
    if base == 10 or n == 0:
        return "{0:0{1}d}".format(n, width)
    out = []
    tmp = n
    while tmp > 0:
        out.append(_DIGIT_CHARS[tmp % base])
        tmp //= base
    return "".join(reversed(out)).zfill(width)


def _from_base(s, base):
    """Parse string s in given base to int."""
    if base == 10:
        return int(s)
    return int(s, base)


# ── Key schedule ──────────────────────────────────────────────────────────────

def _prime_digits(prime_str):
    """Return the digit sequence of the prime as a tuple of ints."""
    return tuple(int(d) for d in prime_str)


def _scheduled_base(digit):
    """
    Return the scheduled base for a prime digit.

    Digit 0 or 1 → base 10 (no twist).
    Digit 2–9    → base equal to digit.
    """
    return 10 if digit <= 1 else digit


def _effective_base(scheduled, token_value, width):
    """
    Return the base actually used for encoding.

    Falls back to base 10 if scheduled base cannot represent
    token_value within width digits (scheduled^width <= token_value).
    """
    if scheduled == 10:
        return 10
    if scheduled ** width > token_value:
        return scheduled
    return 10


# ── Twist / untwist ───────────────────────────────────────────────────────────

def twist(token_stream, prime_str, width=5):
    """
    Apply prime-derived base-switching to a UCS-DEC token stream.

    Args:
        token_stream: string of whitespace-separated UCS-DEC tokens
        prime_str:    decimal string representation of the prime P
        width:        token field width (default: 5)

    Returns:
        tuple of (twisted_tokens, twist_map)
        twisted_tokens: list of zero-padded strings in scheduled bases
        twist_map:      list of ints — actual base used per token
    """
    tokens   = token_stream.split()
    p_digits = _prime_digits(prime_str)
    p_len    = len(p_digits)

    twisted   = []
    twist_map = []

    for i, tok in enumerate(tokens):
        n       = int(tok)
        sched   = _scheduled_base(p_digits[i % p_len])
        base    = _effective_base(sched, n, width)
        twisted.append(_to_base(n, base, width))
        twist_map.append(base)

    return twisted, twist_map


def untwist(twisted_tokens, twist_map, width=5):
    """
    Reverse prime-derived base-switching using a recorded twist-map.

    Args:
        twisted_tokens: list of twisted token strings
        twist_map:      list of ints — base used per token (from RSRC block)
        width:          token field width (default: 5)

    Returns:
        List of base-10 UCS-DEC token strings, zero-padded to width.
    """
    tokens = []
    for tok, base in zip(twisted_tokens, twist_map):
        n = _from_base(tok, base)
        tokens.append("{0:0{1}d}".format(n, width))
    return tokens


# ── Twist-map encoding ────────────────────────────────────────────────────────

def encode_twist_map(twist_map):
    """
    Encode a twist-map as a compact sparse string.

    Only non-base-10 entries are stored, as 'position:base' pairs.
    Base-10 entries are implicit (fall back to base 10).

    Returns: string like '3:5,5:4,8:5,...'
    """
    pairs = [
        "{0}:{1}".format(i, b)
        for i, b in enumerate(twist_map)
        if b != 10
    ]
    return ",".join(pairs)


def decode_twist_map(encoded, total_count):
    """
    Decode a compact sparse twist-map string back to a full list.

    Args:
        encoded:     compact twist-map string (from RSRC block)
        total_count: total number of tokens (to fill implicit base-10 entries)

    Returns:
        List of ints of length total_count.
    """
    result = [10] * total_count
    if not encoded.strip():
        return result
    for pair in encoded.split(","):
        pair = pair.strip()
        if not pair:
            continue
        parts = pair.split(":")
        if len(parts) == 2:
            try:
                pos  = int(parts[0])
                base = int(parts[1])
                if 0 <= pos < total_count:
                    result[pos] = base
            except ValueError:
                continue
    return result


# ── Print Profile artifact ────────────────────────────────────────────────────

def _box_rule():
    return "+" + "-" * BOX_INNER + "+"


def _box_line(content):
    return "|" + ("  " + content).ljust(BOX_INNER) + "|"


def make_artifact(twisted_tokens, twist_map, prime_str,
                  ref="", med="PAPER", width=5):
    """
    Wrap a twisted token stream in a self-describing FDS Print Profile
    artifact with an RSRC block carrying the twist-map and prime.

    Args:
        twisted_tokens: list of twisted token strings
        twist_map:      list of ints — base used per token
        prime_str:      decimal string of the prime P
        ref:            artifact reference ID (optional)
        med:            medium designation (default: PAPER)
        width:          token field width

    Returns:
        Complete artifact as a unicode string.
    """
    payload    = "  ".join(
        "  ".join(twisted_tokens[i:i + 6])
        for i in range(0, len(twisted_tokens), 6)
    )
    # Reformat as proper rows of 6
    rows = []
    for i in range(0, len(twisted_tokens), 6):
        rows.append("  ".join(twisted_tokens[i:i + 6]))
    payload = "\n".join(rows)

    pad        = "0" * width
    real_count = len([t for t in twisted_tokens if t != pad])
    crc        = binascii.crc32(
        payload.encode("utf-8")) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    generated  = time.strftime("%Y-%m-%d")

    twist_map_enc = encode_twist_map(twist_map)
    changed       = sum(1 for b in twist_map if b != 10)

    enc_line = "ENC: UCS {d} DEC {d} COL/6 {d} PAD/{p} {d} WIDTH/{w}".format(
        d=MIDDLE_DOT, p=pad, w=width)
    cnt_line = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    rsrc_lines = [
        "RSRC: BEGIN",
        "  TYPE:       prime-twist",
        "  VERSION:    1",
        "  NOTE:       TEST IMPLEMENTATION — not normatively specified",
        "  PRIME:      {0}".format(prime_str),
        "  WIDTH:      {0}".format(width),
        "  TOKENS:     {0}".format(len(twisted_tokens)),
        "  TWISTED:    {0}".format(changed),
        "  GENERATED:  {0}".format(generated),
        "  TWIST-MAP:  {0}".format(twist_map_enc),
        "RSRC: END",
    ]

    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line(
            "REF: {0}  PAGE 1/1".format(ref)))
    header_lines.append(_box_line(enc_line))
    header_lines.append(_box_line("MED: {0}".format(med)))
    header_lines.append(_box_line(
        "CCL: PRIME-TWIST {d} NOT ENCRYPTED".format(d=MIDDLE_DOT)))
    header_lines.append(_box_rule())

    footer_lines = [
        _box_rule(),
        _box_line(cnt_line),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
        _box_rule(),
    ]

    parts = [
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
    ]

    return "\n".join(parts)


def parse_artifact(content):
    """
    Parse a prime-twist artifact.

    Returns dict with:
        prime_str, width, twist_map_enc, twisted_tokens, token_count
    """
    fields        = {}
    twisted_lines = []
    in_rsrc       = False
    in_payload    = False

    for line in content.splitlines():
        stripped = line.strip()

        if stripped == "RSRC: BEGIN":
            in_rsrc   = True
            in_payload = False
            continue
        if stripped == "RSRC: END":
            in_rsrc   = False
            in_payload = True
            continue

        if in_rsrc and ":" in stripped:
            key, _, val = stripped.partition(":")
            fields[key.strip()] = val.strip()
            continue

        if in_payload:
            # Payload lines: all tokens are digit strings
            toks = stripped.split()
            if toks and all(t.isdigit() for t in toks):
                twisted_lines.extend(toks)
            elif stripped and not stripped.startswith("+") \
                    and not stripped.startswith("|") \
                    and "RESERVED" not in stripped \
                    and "VALUES" not in stripped:
                # Could be end of payload
                pass

    return {
        "prime_str":    fields.get("PRIME", ""),
        "width":        int(fields.get("WIDTH", "5")),
        "twist_map_enc": fields.get("TWIST-MAP", ""),
        "twisted_tokens": twisted_lines,
        "token_count":  len(twisted_lines),
    }


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read_stdin():
    if PY2:
        data = sys.stdin.read()
        if not isinstance(data, unicode):  # noqa: F821
            data = data.decode("utf-8")
        return data
    return sys.stdin.read()


def _write_stdout(text):
    if PY2:
        if isinstance(text, unicode):  # noqa: F821
            sys.stdout.write(text.encode("utf-8"))
        else:
            sys.stdout.write(text)
    else:
        sys.stdout.write(text)


# ── CLI ───────────────────────────────────────────────────────────────────────

def positive_int(value):
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "CCL prime-twist: base-switching driven by a prime key schedule.\n"
            "TEST IMPLEMENTATION — not yet normatively specified.\n"
            "CCL provides no cryptographic confidentiality or integrity."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  cat payload.txt | python prime_twist.py twist"
            " --prime 748...701 > twisted.txt\n"
            "  python prime_twist.py untwist twisted.txt\n"
            "\n"
            "  # Full pipeline\n"
            "  PRIME=$(echo 'my verse' | python verse_to_prime.py derive"
            " | grep '  P:' | awk '{print $2}')\n"
            "  cat payload.txt | python prime_twist.py twist"
            " --prime $PRIME > twisted.txt\n"
            "  python prime_twist.py untwist twisted.txt"
            " | python ucs_dec_tool.py -d\n"
        )
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    p_twist = subparsers.add_parser(
        "twist",
        help="apply prime-twist to a UCS-DEC token stream from stdin"
    )
    p_twist.add_argument(
        "--prime", required=True, metavar="P",
        help="prime number as decimal string (use verse_to_prime.py to derive)"
    )
    p_twist.add_argument(
        "--width", type=positive_int, default=5, metavar="N",
        help="UCS-DEC token field width (default: 5)"
    )
    p_twist.add_argument(
        "--ref", default="", metavar="ID",
        help="artifact reference ID"
    )
    p_twist.add_argument(
        "--med", default="PAPER", metavar="MEDIUM",
        help="medium designation (default: PAPER)"
    )

    p_untwist = subparsers.add_parser(
        "untwist",
        help="reverse prime-twist and emit bare UCS-DEC token stream"
    )
    p_untwist.add_argument("infile", help="twisted artifact file")

    return parser


def cmd_twist(args):
    data = _read_stdin().strip()
    if not data:
        print("Error: empty input", file=sys.stderr)
        return 1

    # Validate prime (basic check)
    try:
        int(args.prime)
    except ValueError:
        print("Error: --prime must be a decimal integer", file=sys.stderr)
        return 1

    twisted_tokens, twist_map = twist(data, args.prime, width=args.width)
    changed = sum(1 for b in twist_map if b != 10)

    print("Tokens: {0}, twisted: {1} ({2:.1f}%)".format(
        len(twist_map), changed,
        100.0 * changed / len(twist_map) if twist_map else 0),
        file=sys.stderr)

    artifact = make_artifact(
        twisted_tokens, twist_map, args.prime,
        ref=args.ref, med=args.med, width=args.width)

    _write_stdout(artifact)
    if not artifact.endswith("\n"):
        _write_stdout("\n")
    return 0


def cmd_untwist(args):
    try:
        with open(args.infile, encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)

    if not parsed["twisted_tokens"]:
        print("Error: no payload found in artifact", file=sys.stderr)
        return 1

    if not parsed["prime_str"]:
        print("Error: no PRIME found in RSRC block", file=sys.stderr)
        return 1

    twist_map = decode_twist_map(
        parsed["twist_map_enc"],
        parsed["token_count"])

    tokens = untwist(parsed["twisted_tokens"], twist_map, parsed["width"])

    print("Tokens: {0}, untwisted from {1} non-base-10 positions".format(
        len(tokens),
        sum(1 for b in twist_map if b != 10)),
        file=sys.stderr)

    _write_stdout("  ".join(tokens))
    _write_stdout("\n")
    return 0


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "twist":
            return cmd_twist(args)
        if args.command == "untwist":
            return cmd_untwist(args)
    except (ValueError, IOError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
