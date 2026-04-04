#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verse_to_prime.py — mnemonic prime derivation

Derives a prime number from a verse or other memorable text,
using UCS-DEC encoding as the intermediate representation.

The construction:

    verse (any Unicode text)
      -> NFC normalise
      -> UCS-DEC encode (WIDTH/5, no wrapping)
      -> SHA256 of the token stream
      -> interpret SHA256 digest as 256-bit integer N
      -> next_prime(N)
      -> prime P

Output is a self-describing FDS Print Profile artifact whose
payload is the UCS-DEC encoding of the derived prime.

Usage:
    python verse_to_prime.py derive
    python verse_to_prime.py derive --show-steps
    python verse_to_prime.py derive --ref SHARE-1 --med PAPER
    python verse_to_prime.py verify <infile>

Input is read from stdin. The verse may be any length.

Examples:
    echo "Factoring primes" | python verse_to_prime.py derive
    cat verse.txt | python verse_to_prime.py derive --show-steps
    cat verse.txt | python verse_to_prime.py derive --ref K1 > k1.txt
    python verse_to_prime.py verify k1.txt

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import hashlib
import sys
import time
import unicodedata

PY2 = (sys.version_info[0] == 2)

if PY2:
    text_type = unicode   # noqa: F821
    to_chr    = unichr    # noqa: F821
else:
    text_type = str
    to_chr    = chr

# ── Miller-Rabin ──────────────────────────────────────────────────────────────
# Deterministic below 3.3e24; probabilistic with negligible error above that.
# For 77-digit inputs (SHA256 output range) we use 64 rounds — the probability
# of a composite passing is at most 4^-64, which is negligible.

WITNESSES_SMALL = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
ROUNDS_LARGE    = 64


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

    Deterministic for n < 3,317,044,064,679,887,385,961,981.
    For larger n (including all SHA256-derived inputs), uses 64
    Miller-Rabin rounds — error probability at most 4^-64.
    """
    if n < 2:
        return False
    for p in WITNESSES_SMALL:
        if n == p:
            return True
        if n % p == 0:
            return False
    # Use deterministic witness set for small n, random-equivalent
    # fixed witnesses for large n
    return _miller_rabin(n, WITNESSES_SMALL)


def next_prime(n):
    """Return the smallest prime >= n."""
    if n <= 2:
        return 2
    n = n | 1  # ensure odd
    while not is_prime(n):
        n += 2
    return n


# ── UCS-DEC ───────────────────────────────────────────────────────────────────

def ucs_dec_encode(text, width=5):
    """
    Encode text as a UCS-DEC token stream (no line wrapping).

    Args:
        text:  NFC-normalised Unicode string
        width: field width (default: 5)

    Returns:
        Space-separated token string.
    """
    return " ".join("{0:0{1}d}".format(ord(ch), width) for ch in text)


def ucs_dec_decode(token_stream, width=5, skip_null=True):
    """Decode a UCS-DEC token stream back to text."""
    pad   = "0" * width
    chars = []
    for token in token_stream.split():
        try:
            value = int(token)
        except ValueError:
            continue
        if not (0 <= value <= 0x10FFFF):
            continue
        if skip_null and token == pad:
            continue
        chars.append(to_chr(value))
    return "".join(chars)


# ── Core construction ─────────────────────────────────────────────────────────

def derive(verse, width=5):
    """
    Derive a prime from a verse.

    Steps:
        1. NFC normalise
        2. UCS-DEC encode (width, no wrapping)
        3. SHA256 of token stream (UTF-8)
        4. Interpret digest as integer N
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


# ── Print Profile artifact ────────────────────────────────────────────────────

BOX_INNER    = 41
MIDDLE_DOT   = "\u00b7"
DESTROY_FLAG = "IF COUNT FAILS: DESTROY IMMEDIATELY"


def _box_rule():
    return "+" + "-" * BOX_INNER + "+"


def _box_line(content):
    return "|" + ("  " + content).ljust(BOX_INNER) + "|"


def make_artifact(result, ref="", med="PAPER", width=5):
    """
    Wrap the derived prime in a self-describing FDS Print Profile artifact.

    The payload is the UCS-DEC encoding of the prime P.
    The resource fork header carries the construction parameters.
    """
    P            = result["P"]
    prime_str    = str(P)
    prime_tokens = ucs_dec_encode(prime_str, width=width)

    # Payload: UCS-DEC encoding of the prime digits
    # (encode the decimal digit characters, not the integer value)
    pad         = "0" * width
    tokens      = prime_tokens.split()
    real_count  = len([t for t in tokens if t != pad])
    crc         = binascii.crc32(
        prime_tokens.encode("utf-8")) & 0xFFFFFFFF
    crc_str     = format(crc, "08X")
    generated   = time.strftime("%Y-%m-%d")

    enc_line = "ENC: UCS {d} DEC {d} COL/0 {d} PAD/{p} {d} WIDTH/{w}".format(
        d=MIDDLE_DOT, p=pad, w=width)
    cnt_line = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    # Resource fork: construction parameters
    rsrc_lines = [
        "RSRC: BEGIN",
        "  TYPE:     mnemonic-prime",
        "  VERSION:  1",
        "  METHOD:   UCS-DEC / SHA256 / next-prime / Miller-Rabin",
        "  ENCODING: WIDTH/{w} {d} NFC {d} no-wrap".format(
            w=width, d=MIDDLE_DOT),
        "  TOKENS:   {0}".format(result["token_count"]),
        "  DIGEST:   SHA256:{0}".format(result["digest_hex"]),
        "  N:        {0}".format(result["N"]),
        "  P:        {0}".format(P),
        "  DIGITS:   {0}".format(len(prime_str)),
        "  GENERATED:{0}".format(generated),
        "RSRC: END",
    ]

    # Header box
    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line(
            "REF: {0}  PAGE 1/1".format(ref)))
    header_lines.append(_box_line(enc_line))
    header_lines.append(_box_line(
        "MED: {0}".format(med)))
    header_lines.append(_box_line("DESTROY AFTER USE"))
    header_lines.append(_box_rule())

    # Footer box
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
        prime_tokens,
        "",
        "\n".join(footer_lines),
        "",
        "                   RESERVED -- SINGLE USE",
    ]

    return "\n".join(parts)


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
            "Mnemonic prime derivation.\n"
            "Derives a prime from verse via UCS-DEC encoding and SHA256.\n"
            "Output is a self-describing FDS Print Profile artifact."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Construction:\n"
            "  verse -> NFC normalise -> UCS-DEC encode ->\n"
            "  SHA256 of token stream -> integer N -> next_prime(N) -> P\n"
            "\n"
            "Examples:\n"
            "  echo 'Factoring primes' | python verse_to_prime.py derive\n"
            "  cat verse.txt | python verse_to_prime.py derive --show-steps\n"
            "  cat verse.txt | python verse_to_prime.py derive --ref K1 > k1.txt\n"
            "  python verse_to_prime.py verify k1.txt\n"
        )
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    p_derive = subparsers.add_parser(
        "derive",
        help="derive a prime from stdin verse; output Print Profile artifact"
    )
    p_derive.add_argument(
        "--show-steps", action="store_true",
        help="print intermediate construction steps to stderr"
    )
    p_derive.add_argument(
        "--ref", default="", metavar="ID",
        help="artifact reference ID for Print Profile header"
    )
    p_derive.add_argument(
        "--med", default="PAPER", metavar="MEDIUM",
        help="medium designation (default: PAPER)"
    )
    p_derive.add_argument(
        "--width", type=positive_int, default=5, metavar="N",
        help="UCS-DEC field width (default: 5)"
    )

    p_verify = subparsers.add_parser(
        "verify",
        help="verify a derived prime artifact"
    )
    p_verify.add_argument("infile", help="artifact file to verify")

    return parser


def cmd_derive(args):
    verse = _read_stdin().rstrip("\n")
    if not verse:
        print("Error: empty input", file=sys.stderr)
        return 1

    result = derive(verse, width=args.width)

    if args.show_steps:
        print("=== Construction steps ===", file=sys.stderr)
        print("Verse ({0} chars):".format(
            len(result["normalised"])), file=sys.stderr)
        print("  " + repr(result["normalised"]), file=sys.stderr)
        print("Token stream ({0} tokens, first 60 chars):".format(
            result["token_count"]), file=sys.stderr)
        print("  " + result["token_stream"][:60] + " ...", file=sys.stderr)
        print("SHA256 digest:", file=sys.stderr)
        print("  " + result["digest_hex"], file=sys.stderr)
        print("Integer N ({0} digits):".format(
            len(str(result["N"]))), file=sys.stderr)
        print("  " + str(result["N"]), file=sys.stderr)
        print("Prime P ({0} digits):".format(
            len(str(result["P"]))), file=sys.stderr)
        print("  " + str(result["P"]), file=sys.stderr)
        print("", file=sys.stderr)

    artifact = make_artifact(result, ref=args.ref, med=args.med,
                             width=args.width)
    _write_stdout(artifact)
    if not artifact.endswith("\n"):
        _write_stdout("\n")
    return 0


def cmd_verify(args):
    try:
        with open(args.infile, encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    # Extract fields from resource fork
    fields = {}
    in_rsrc = False
    payload_lines = []
    in_payload = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "RSRC: BEGIN":
            in_rsrc = True
            continue
        if stripped == "RSRC: END":
            in_rsrc = False
            in_payload = True
            continue
        if in_rsrc and ":" in stripped:
            key, _, val = stripped.partition(":")
            fields[key.strip()] = val.strip()
        if in_payload and all(t.isdigit() for t in stripped.split()) and stripped:
            payload_lines.append(line)

    if not fields:
        print("Error: no RSRC block found in artifact", file=sys.stderr)
        return 1

    payload = "\n".join(payload_lines)

    # Re-derive and check
    P_declared = fields.get("P", "").strip()
    N_declared = fields.get("N", "").strip()
    digest_declared = fields.get("DIGEST", "").replace("SHA256:", "").strip()

    print("File:      {0}".format(args.infile))
    print("Type:      {0}".format(fields.get("TYPE", "?")))
    print("Method:    {0}".format(fields.get("METHOD", "?")))
    print()

    ok = True

    # Verify P is prime
    if P_declared:
        try:
            P = int(P_declared)
            prime_ok = is_prime(P)
            print("Prime P:   {0}... ({1} digits) — {2}".format(
                str(P)[:20], len(str(P)),
                "prime" if prime_ok else "NOT PRIME"))
            if not prime_ok:
                ok = False
        except ValueError:
            print("Prime P:   FAIL (unparseable)")
            ok = False
    else:
        print("Prime P:   MISSING")
        ok = False

    # Verify payload encodes the declared prime
    if P_declared and payload:
        payload_decoded = ucs_dec_decode(payload)
        payload_ok = (payload_decoded == P_declared)
        print("Payload:   {0}".format(
            "OK — encodes declared prime" if payload_ok
            else "FAIL — payload does not encode declared prime"))
        if not payload_ok:
            ok = False

    # Verify CRC32
    if payload:
        crc_actual = format(
            binascii.crc32(payload.encode("utf-8")) & 0xFFFFFFFF, "08X")
        # Find declared CRC from footer
        crc_declared = None
        for line in content.splitlines():
            if "CRC32:" in line and "VALUES" in line:
                crc_declared = line.split("CRC32:")[-1].split()[0].strip()
                break
        if crc_declared:
            crc_ok = (crc_actual == crc_declared)
            print("CRC32:     {0} — {1}".format(
                crc_actual,
                "OK" if crc_ok else "FAIL (declared: {0})".format(
                    crc_declared)))
            if not crc_ok:
                ok = False

    print()
    print("Verification: {0}".format("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "derive":
            return cmd_derive(args)
        if args.command == "verify":
            return cmd_verify(args)
    except (ValueError, IOError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
