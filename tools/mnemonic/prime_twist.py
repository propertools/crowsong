#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prime_twist.py — Channel Camouflage Layer: prime-derived base-switching

A test implementation of the prime-twisting construction for the
Channel Camouflage Layer (CCL). Not a production cryptographic tool.

Construction (single pass):

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

Stacking (multiple passes):

    Multiple passes may be applied using distinct primes. Each pass
    takes the token stream output of the previous pass as input. The
    output is a single stack file containing all pass artifacts as
    clearly delimited sections. Unwinding applies passes in reverse
    order. Maximum stack depth: 10.

    CCL provides no cryptographic confidentiality or integrity protection.
    Stacking increases statistical salience reduction but does not
    change the fundamental security properties of CCL.
    Security properties for mnemonic share wrapping are specified
    separately in draft-darley-shard-bundle-01.

Usage:
    python prime_twist.py twist   --prime <P> [--width N] [--ref ID]
                                  [--schedule standard|mod3]
    python prime_twist.py untwist <infile>
    python prime_twist.py stack   --primes P1,P2,... [--ref ID] [--med M]
                                  [--schedule standard|mod3]
    python prime_twist.py stack   --verse-file <file> [--ref ID] [--med M]
                                  [--schedule standard|mod3]
    python prime_twist.py unstack <infile>

Schedules:
    standard  Digit d -> base d (bases 2-9); falls back to base 10 when
              base^width <= token_value. Default. Appropriate for WIDTH/5
              UCS-DEC streams of natural language and Unicode text.

    mod3      Digit d -> base (7 + d mod 3), always base 7, 8, or 9.
              100% twist rate guaranteed -- no feasibility fallback.
              Proposed for WIDTH/3 BINARY mode where bases 2-6 cannot
              represent most byte values (base^3 <= 255).
              See draft-darley-fds-ccl-prime-twist-00 Section 11.4.

Input for twist/stack is read from stdin (bare UCS-DEC token stream).
Output is a self-describing FDS Print Profile artifact or stack file.

Examples:
    # Single pass
    cat payload.txt | python prime_twist.py twist --prime 748...701

    # Untwist
    python prime_twist.py untwist twisted.txt

    # Stack: three primes
    cat payload.txt | python prime_twist.py stack \\
        --primes 748...701,571...377,301...123 --ref CCL3

    # Stack: derive primes from a verse file (one verse per line)
    cat payload.txt | python prime_twist.py stack \\
        --verse-file verses.txt --ref CCL3

    # Unstack
    python prime_twist.py unstack stacked.txt | python ucs_dec_tool.py -d

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT

NOTE: This is a test implementation. The CCL construction and
stack file format are not yet normatively specified. The interface
and file format may change in future revisions.
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import io
import sys
import time

# Shared construction library — primality testing and verse-to-prime derivation.
# Single canonical implementation shared with verse_to_prime.py.
from mnemonic import derive as _mnemonic_derive  # noqa: E402
from mnemonic import is_prime as _is_prime        # noqa: E402

PY2 = (sys.version_info[0] == 2)

if PY2:
    to_chr = unichr   # noqa: F821
else:
    to_chr = chr

_DIGIT_CHARS = "0123456789"
BOX_INNER    = 41
MIDDLE_DOT   = "\u00b7"
DESTROY_FLAG = "IF COUNT FAILS: DESTROY IMMEDIATELY"
MAX_DEPTH    = 10

STACK_BEGIN  = "=== CCL STACK BEGIN {d} DEPTH/{depth} {d} REF/{ref} ==="
STACK_PASS   = "=== CCL STACK PASS {n}/{depth} ==="
STACK_END    = "=== CCL STACK END {d} REF/{ref} ==="


# ── Verse-to-prime (delegated to mnemonic library) ───────────────────────────

def _verse_to_prime(verse):
    """
    Derive a prime from a verse via NFC -> UCS-DEC -> SHA256 -> next_prime.
    Delegates to mnemonic.derive() — the single canonical implementation.
    Strip policy (leading/trailing whitespace) is applied in mnemonic.derive(),
    not here.
    """
    return _mnemonic_derive(verse)["P"]


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
    if not (2 <= base <= 9):
        raise ValueError("base must be 2-9 for non-decimal, got {0}".format(base))
    return int(s, base)


# ── Key schedule ──────────────────────────────────────────────────────────────

SCHEDULE_STANDARD = "standard"
SCHEDULE_MOD3     = "mod3"
SCHEDULES         = (SCHEDULE_STANDARD, SCHEDULE_MOD3)


def _prime_digits(prime_str):
    """Return the digit sequence of the prime as a tuple of ints."""
    return tuple(int(d) for d in prime_str)


def _scheduled_base(digit, schedule=SCHEDULE_STANDARD):
    """
    Return the scheduled base for a prime digit under the given schedule.

    standard: digit 0 or 1 -> base 10 (no twist); digit 2-9 -> that base.
              Appropriate for WIDTH/5 UCS-DEC streams.

    mod3:     digit d -> base (7 + d mod 3), always 7, 8, or 9.
              Guarantees 100% twist rate at WIDTH/3 where bases 2-6
              fail the feasibility check for most byte values.
              See draft-darley-fds-ccl-prime-twist-00 Section 11.4.
    """
    if schedule == SCHEDULE_MOD3:
        return 7 + (digit % 3)
    return 10 if digit <= 1 else digit


def _effective_base(scheduled, token_value, width):
    """
    Return the base actually used for encoding.

    Falls back to base 10 if the scheduled base cannot represent
    token_value within width digits (base^width <= token_value).

    Note: the mod3 schedule always selects base 7, 8, or 9. At WIDTH/3,
    all three cover the full byte range (7^3=343, 8^3=512, 9^3=729, all
    > 255), so the feasibility fallback never triggers under mod3 for
    WIDTH/3 BINARY payloads.
    """
    if scheduled == 10:
        return 10
    if scheduled ** width > token_value:
        return scheduled
    return 10


# ── Single-pass twist / untwist ───────────────────────────────────────────────

def twist(token_stream, prime_str, width=5, schedule=SCHEDULE_STANDARD):
    """
    Apply prime-derived base-switching to a UCS-DEC token stream.

    Args:
        token_stream: whitespace-separated FDS token string
        prime_str:    decimal string of the key prime
        width:        FDS field width (default: 5)
        schedule:     base schedule — SCHEDULE_STANDARD or SCHEDULE_MOD3

    Returns:
        (twisted_tokens, twist_map)
        twisted_tokens: list of zero-padded strings in scheduled bases
        twist_map:      list of ints — actual base used per token
    """
    tokens    = token_stream.split()
    p_digits  = _prime_digits(prime_str)
    p_len     = len(p_digits)
    twisted   = []
    twist_map = []

    for i, tok in enumerate(tokens):
        n     = int(tok)
        sched = _scheduled_base(p_digits[i % p_len], schedule)
        base  = _effective_base(sched, n, width)
        twisted.append(_to_base(n, base, width))
        twist_map.append(base)

    return twisted, twist_map


def untwist(twisted_tokens, twist_map, width=5):
    """
    Reverse prime-derived base-switching using a recorded twist-map.

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
    """Compact sparse encoding: only non-base-10 entries as 'pos:base'."""
    return ",".join(
        "{0}:{1}".format(i, b)
        for i, b in enumerate(twist_map)
        if b != 10)


def decode_twist_map(encoded, total_count):
    """Decode a compact sparse twist-map string to a full list."""
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
                pos, base = int(parts[0]), int(parts[1])
                if 0 <= pos < total_count and 2 <= base <= 10:
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
                  ref="", med="PAPER", width=5,
                  stack_pass=None, stack_depth=None,
                  schedule=SCHEDULE_STANDARD):
    """
    Wrap a twisted token stream in a self-describing FDS Print Profile
    artifact with an RSRC block carrying the twist-map and prime.
    """
    rows = []
    for i in range(0, len(twisted_tokens), 6):
        rows.append("  ".join(twisted_tokens[i:i + 6]))
    payload = "\n".join(rows)

    pad        = "0" * width
    real_count = len([t for t in twisted_tokens if t != pad])
    generated  = time.strftime("%Y-%m-%d")
    changed    = sum(1 for b in twist_map if b != 10)

    enc_line = "ENC: UCS {d} DEC {d} COL/6 {d} PAD/{p} {d} WIDTH/{w}".format(
        d=MIDDLE_DOT, p=pad, w=width)

    rsrc_lines = [
        "RSRC: BEGIN",
        "  TYPE:       prime-twist",
        "  VERSION:    1",
        "  NOTE:       TEST IMPLEMENTATION — not normatively specified",
        "  PRIME:      {0}".format(prime_str),
        "  SCHEDULE:   {0}".format(schedule),
        "  WIDTH:      {0}".format(width),
        "  TOKENS:     {0}".format(len(twisted_tokens)),
        "  TWISTED:    {0}".format(changed),
        "  GENERATED:  {0}".format(generated),
    ]
    if stack_pass is not None and stack_depth is not None:
        rsrc_lines.append(
            "  STACK-PASS: {0}/{1}".format(stack_pass, stack_depth))
    rsrc_lines.append(
        "  TWIST-MAP:  {0}".format(encode_twist_map(twist_map)))
    rsrc_lines.append("RSRC: END")

    rsrc_text  = "\n".join(rsrc_lines)
    crc_input  = (payload + "\n" + rsrc_text).encode("utf-8")
    crc        = binascii.crc32(crc_input) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    cnt_line   = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    if stack_pass is not None:
        header_lines.append(_box_line(
            "CCL PASS {0}/{1}".format(stack_pass, stack_depth)))
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
    """Parse a prime-twist artifact. Returns dict."""
    fields        = {}
    twisted_lines = []
    in_rsrc       = False
    in_payload    = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "RSRC: BEGIN":
            in_rsrc, in_payload = True, False
            continue
        if stripped == "RSRC: END":
            in_rsrc, in_payload = False, True
            continue
        if in_rsrc and ":" in stripped:
            key, _, val = stripped.partition(":")
            fields[key.strip()] = val.strip()
            continue
        if in_payload:
            toks = stripped.split()
            if toks and all(t.isdigit() for t in toks):
                twisted_lines.extend(toks)
            elif stripped and not stripped.startswith("+") \
                    and not stripped.startswith("|") \
                    and "RESERVED" not in stripped \
                    and "VALUES" not in stripped:
                pass  # structural line (box border, label etc.) — intentionally ignored

    return {
        "prime_str":     fields.get("PRIME", ""),
        "schedule":      fields.get("SCHEDULE", SCHEDULE_STANDARD),
        "width":         max(1, min(20, int(fields.get("WIDTH", "5")))),
        "twist_map_enc": fields.get("TWIST-MAP", ""),
        "twisted_tokens": twisted_lines,
        "token_count":   len(twisted_lines),
    }


# ── Stack file format ─────────────────────────────────────────────────────────

def make_stack_file(artifacts, ref, depth):
    """
    Assemble multiple pass artifacts into a single self-describing stack file.

    Format:
        === CCL STACK BEGIN · DEPTH/N · REF/ref ===
        [pass 1 artifact]
        === CCL STACK PASS 2/N ===
        [pass 2 artifact]
        ...
        === CCL STACK END · REF/ref ===
    """
    sections = [STACK_BEGIN.format(
        d=MIDDLE_DOT, depth=depth, ref=ref)]
    for i, artifact in enumerate(artifacts):
        if i > 0:
            sections.append(STACK_PASS.format(n=i + 1, depth=depth))
        sections.append(artifact)
    sections.append(STACK_END.format(d=MIDDLE_DOT, ref=ref))
    return "\n".join(sections)


def parse_stack_file(content):
    """
    Parse a stack file into a list of artifact strings in pass order (1..N).
    """
    artifacts = []
    current   = []
    in_stack  = False

    for line in content.splitlines():
        if line.startswith("=== CCL STACK BEGIN"):
            in_stack = True
            current  = []
            continue
        if line.startswith("=== CCL STACK PASS"):
            if current:
                artifacts.append("\n".join(current))
            current = []
            continue
        if line.startswith("=== CCL STACK END"):
            if current:
                artifacts.append("\n".join(current))
            break
        if in_stack:
            current.append(line)

    return artifacts


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
            "  # Single pass\n"
            "  cat payload.txt | python prime_twist.py twist --prime P\n"
            "  python prime_twist.py untwist twisted.txt\n"
            "\n"
            "  # Stack: N passes with N primes (max {0})\n"
            "  cat payload.txt | python prime_twist.py stack \\\n"
            "    --primes P1,P2,P3 --ref CCL3\n"
            "  python prime_twist.py unstack stacked.txt\n"
            "\n"
            "  # Stack: derive primes from verse file (one verse per line)\n"
            "  cat payload.txt | python prime_twist.py stack \\\n"
            "    --verse-file verses.txt --ref CCL3\n"
        ).format(MAX_DEPTH)
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # ── twist ──────────────────────────────────────────────────────────────
    p_twist = subparsers.add_parser(
        "twist",
        help="apply a single CCL pass to stdin token stream"
    )
    p_twist.add_argument(
        "--prime", required=True, metavar="P",
        help="prime as decimal string"
    )
    p_twist.add_argument(
        "--width", type=positive_int, default=5, metavar="N",
        help="UCS-DEC field width (default: 5)"
    )
    p_twist.add_argument("--ref", default="", metavar="ID")
    p_twist.add_argument("--med", default="PAPER", metavar="MEDIUM")
    p_twist.add_argument(
        "--schedule", default=SCHEDULE_STANDARD,
        choices=SCHEDULES, metavar="SCHEDULE",
        help="base schedule: standard (default) or mod3 (WIDTH/3 BINARY)"
    )

    # ── untwist ────────────────────────────────────────────────────────────
    p_untwist = subparsers.add_parser(
        "untwist",
        help="reverse a single CCL pass; emit bare token stream"
    )
    p_untwist.add_argument("infile", help="twisted artifact file")

    # ── stack ──────────────────────────────────────────────────────────────
    p_stack = subparsers.add_parser(
        "stack",
        help="apply N CCL passes (max {0}); output single stack file".format(
            MAX_DEPTH)
    )
    prime_group = p_stack.add_mutually_exclusive_group(required=True)
    prime_group.add_argument(
        "--primes", metavar="P1,P2,...",
        help="comma-separated prime list"
    )
    prime_group.add_argument(
        "--verse-file", metavar="FILE",
        help="file with one verse per line; primes derived automatically"
    )
    p_stack.add_argument(
        "--width", type=positive_int, default=5, metavar="N",
        help="UCS-DEC field width (default: 5)"
    )
    p_stack.add_argument("--ref", default="CCL-STACK", metavar="ID")
    p_stack.add_argument("--med", default="PAPER", metavar="MEDIUM")
    p_stack.add_argument(
        "--schedule", default=SCHEDULE_STANDARD,
        choices=SCHEDULES, metavar="SCHEDULE",
        help="base schedule: standard (default) or mod3 (WIDTH/3 BINARY)"
    )

    # ── unstack ────────────────────────────────────────────────────────────
    p_unstack = subparsers.add_parser(
        "unstack",
        help="unwind all passes in a stack file; emit bare token stream"
    )
    p_unstack.add_argument("infile", help="stack file")

    return parser


# ── Command implementations ───────────────────────────────────────────────────

def cmd_twist(args):
    data = _read_stdin().strip()
    if not data:
        print("Error: empty input", file=sys.stderr)
        return 1
    try:
        p_val = int(args.prime)
    except ValueError:
        print("Error: --prime must be a decimal integer", file=sys.stderr)
        return 1
    if not _is_prime(p_val):
        print("Warning: --prime is not prime; construction expects a prime",
              file=sys.stderr)

    twisted_tokens, twist_map = twist(
        data, args.prime, width=args.width, schedule=args.schedule)
    changed = sum(1 for b in twist_map if b != 10)
    print("Tokens: {0}, twisted: {1} ({2:.1f}%)  schedule: {3}".format(
        len(twist_map), changed,
        100.0 * changed / len(twist_map) if twist_map else 0,
        args.schedule),
        file=sys.stderr)

    artifact = make_artifact(
        twisted_tokens, twist_map, args.prime,
        ref=args.ref, med=args.med, width=args.width,
        schedule=args.schedule)
    _write_stdout(artifact)
    if not artifact.endswith("\n"):
        _write_stdout("\n")
    return 0


def cmd_untwist(args):
    try:
        with io.open(args.infile, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parsed = parse_artifact(content)
    if not parsed["twisted_tokens"]:
        print("Error: no payload found in artifact", file=sys.stderr)
        return 1
    if not parsed["prime_str"]:
        print("Error: no PRIME in RSRC block", file=sys.stderr)
        return 1

    twist_map = decode_twist_map(
        parsed["twist_map_enc"], parsed["token_count"])
    tokens = untwist(parsed["twisted_tokens"], twist_map, parsed["width"])

    print("Tokens: {0}, untwisted from {1} positions".format(
        len(tokens), sum(1 for b in twist_map if b != 10)),
        file=sys.stderr)
    _write_stdout("  ".join(tokens))
    _write_stdout("\n")
    return 0


def cmd_stack(args):
    data = _read_stdin().strip()
    if not data:
        print("Error: empty input", file=sys.stderr)
        return 1

    # Resolve primes
    if args.primes:
        prime_list = [p.strip() for p in args.primes.split(",") if p.strip()]
    else:
        try:
            with io.open(args.verse_file, "r", encoding="utf-8") as f:
                verses = [l.rstrip("\r\n") for l in f if l.strip()]
        except IOError as err:
            print("Error: {0}".format(err), file=sys.stderr)
            return 1
        prime_list = []
        for i, verse in enumerate(verses):
            p = _verse_to_prime(verse)
            prime_list.append(str(p))
            print("  Derived P{0}: {1}... ({2} digits)".format(
                i + 1, str(p)[:20], len(str(p))), file=sys.stderr)

    depth = len(prime_list)
    if depth < 1:
        print("Error: at least one prime required", file=sys.stderr)
        return 1
    if depth > MAX_DEPTH:
        print("Error: maximum stack depth is {0}".format(MAX_DEPTH),
              file=sys.stderr)
        return 1

    for i, p in enumerate(prime_list):
        try:
            p_val = int(p)
        except ValueError:
            print("Error: prime {0} is not a valid integer".format(i + 1),
                  file=sys.stderr)
            return 1
        if not _is_prime(p_val):
            print("Warning: prime {0} is not prime; construction expects a prime".format(
                i + 1), file=sys.stderr)

    print("Stack depth: {0}".format(depth), file=sys.stderr)

    artifacts      = []
    current_tokens = data

    for i, prime in enumerate(prime_list):
        twisted_tokens, twist_map = twist(
            current_tokens, prime, width=args.width, schedule=args.schedule)
        changed = sum(1 for b in twist_map if b != 10)
        print("  Pass {0}/{1}: {2} tokens, {3} twisted ({4:.1f}%)".format(
            i + 1, depth, len(twist_map), changed,
            100.0 * changed / len(twist_map) if twist_map else 0),
            file=sys.stderr)

        artifact = make_artifact(
            twisted_tokens, twist_map, prime,
            ref="{0}-P{1}".format(args.ref, i + 1),
            med=args.med,
            width=args.width,
            stack_pass=i + 1,
            stack_depth=depth,
            schedule=args.schedule)
        artifacts.append(artifact)
        current_tokens = "  ".join(twisted_tokens)

    stack_file = make_stack_file(artifacts, args.ref, depth)
    _write_stdout(stack_file)
    if not stack_file.endswith("\n"):
        _write_stdout("\n")
    return 0


def cmd_unstack(args):
    try:
        with io.open(args.infile, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    artifacts = parse_stack_file(content)
    if not artifacts:
        print("Error: no stack passes found in file", file=sys.stderr)
        return 1

    depth = len(artifacts)
    print("Stack depth: {0}".format(depth), file=sys.stderr)

    # Parse all passes first
    parsed_passes = []
    for i, artifact_text in enumerate(artifacts):
        parsed = parse_artifact(artifact_text)
        if not parsed["twisted_tokens"]:
            print("Error: no payload in pass {0}".format(i + 1),
                  file=sys.stderr)
            return 1
        if not parsed["prime_str"]:
            print("Error: no PRIME in pass {0} RSRC block".format(i + 1),
                  file=sys.stderr)
            return 1
        parsed_passes.append(parsed)

    # Unwind in reverse — outermost pass first
    current_tokens = parsed_passes[-1]["twisted_tokens"]

    for i, parsed in enumerate(reversed(parsed_passes)):
        twist_map = decode_twist_map(
            parsed["twist_map_enc"], len(current_tokens))
        current_tokens = untwist(
            current_tokens, twist_map, parsed["width"])
        changed = sum(1 for b in twist_map if b != 10)
        print("  Unstack pass {0}/{1}: {2} tokens, {3} untwisted".format(
            depth - i, depth, len(current_tokens), changed),
            file=sys.stderr)

    _write_stdout("  ".join(current_tokens))
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
        if args.command == "stack":
            return cmd_stack(args)
        if args.command == "unstack":
            return cmd_unstack(args)
    except (ValueError, IOError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
