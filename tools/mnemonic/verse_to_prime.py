#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
verse_to_prime.py — mnemonic prime derivation

Derives a deterministic prime from a verse or other memorable text,
using UCS-DEC as the canonical intermediate representation.

Construction:

    verse (any Unicode text)
      -> NFC normalise
      -> UCS-DEC encode (WIDTH/5, no wrapping)
      -> SHA256 of the token stream
      -> interpret SHA256 digest as 256-bit integer N
      -> next_prime(N)
      -> prime P

Output is a self-describing FDS Print Profile artifact whose payload
is the UCS-DEC encoding of the derived prime.

This tool generates reproducibility artifacts. The derived prime P
and the intermediate value N are both stored in the artifact RSRC
block. This enables verification of the construction trace but means
the artifact does not conceal P. Confidentiality and threshold
security are provided by separate layers; see draft-darley-shard-bundle-01.

Usage:
    python verse_to_prime.py derive
    python verse_to_prime.py derive --show-steps
    python verse_to_prime.py derive --ref SHARE-1 --med PAPER
    python verse_to_prime.py verify <infile>

verify checks artifact integrity and internal consistency:
    - RSRC block present and TYPE/VERSION correct
    - declared P is prime
    - payload encodes declared P
    - declared N is consistent with declared P (N <= P)
    - declared DIGITS matches len(P)
    - CRC32 matches payload

verify does NOT check derivation correctness. Without the original
verse, it cannot verify that P was derived from that verse. To verify
the full derivation, re-run derive on the original verse and compare
the declared DIGEST fields.

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
import io
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    to_chr = unichr   # noqa: F821
else:
    to_chr = chr

# Shared construction library — primality testing and verse-to-prime derivation.
# This is the single canonical implementation; prime_twist.py also imports from here.
from mnemonic import is_prime, next_prime, ucs_dec_encode, derive  # noqa: E402


# ── UCS-DEC (decode only — encode is imported from mnemonic) ────────────────

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


# derive() is imported from mnemonic — see mnemonic.py for the canonical
# implementation of the verse-to-prime construction.


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
    header_lines.append(_box_line("DESTROY AFTER READING"))
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
    verse = _read_stdin().rstrip("\r\n")
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
        with io.open(args.infile, "r", encoding="utf-8") as f:
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

    P_declared      = fields.get("P", "").strip()
    N_declared      = fields.get("N", "").strip()
    digits_declared = fields.get("DIGITS", "").strip()
    type_declared   = fields.get("TYPE", "").strip()
    ver_declared    = fields.get("VERSION", "").strip()
    digest_hex      = fields.get("DIGEST", "").replace("SHA256:", "").strip()

    print("File:      {0}".format(args.infile))
    print("Type:      {0}".format(type_declared or "?"))
    print("Method:    {0}".format(fields.get("METHOD", "?")))
    if digest_hex:
        print("Digest:    present (not verifiable without source verse)")
    print()

    ok = True

    # Check TYPE and VERSION
    if type_declared != "mnemonic-prime":
        print("Type:      FAIL (expected mnemonic-prime, got {0!r})".format(
            type_declared))
        ok = False
    if ver_declared != "1":
        print("Version:   FAIL (expected 1, got {0!r})".format(ver_declared))
        ok = False

    # Verify P is prime
    P = None
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

    # Verify declared DIGITS matches len(P)
    if P is not None and digits_declared:
        digits_ok = (digits_declared == str(len(str(P))))
        print("Digits:    {0} — {1}".format(
            digits_declared,
            "OK" if digits_ok else "FAIL (actual: {0})".format(len(str(P)))))
        if not digits_ok:
            ok = False

    # Verify construction consistency: next_prime(N) must equal P.
    # This is a strong check — it verifies the construction without
    # needing the original verse.
    if P is not None and N_declared:
        try:
            N = int(N_declared)
            derived_p = next_prime(N)
            n_ok = (derived_p == P)
            print("next_prime(N): {0}... — {1}".format(
                str(derived_p)[:20],
                "OK — P = next_prime(N)" if n_ok
                else "FAIL — declared P does not match next_prime(N)"))
            if not n_ok:
                ok = False
        except ValueError:
            print("N:         FAIL (unparseable)")
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
    print("NOTE: verify checks artifact integrity only.")
    print("      To verify derivation, re-run derive on the original")
    print("      verse and compare the DIGEST fields.")
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
