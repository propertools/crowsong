#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
symbol_twist.py — Symbol Substitution Layer for FDS token streams

Applies a deterministic, reversible symbol substitution to a UCS-DEC token
stream. The primary purpose is to destroy script fingerprints in the token
value distribution before CCL prime-twist runs.

THREAT MODEL — why this layer exists:

    UCS-DEC encodes each character as its Unicode code point. Scripts
    cluster tightly in the token value space:

        ASCII/Latin:  00032–00126   CJK unified:  19968–40959
        Arabic:       01536–01791   Hangul:        44032–55203

    These clusters are recognisable signals intelligence fingerprints.
    A passive observer performing frequency analysis on token values can
    identify the script — and therefore the language, likely origin, and
    subject matter — of a payload, even before CCL is applied.

    CCL partially masks this for ASCII (small values, high twist rates)
    but is structurally limited for high-codepoint scripts. For a CJK
    token at value 40,000, only base 9 is feasible (9^5 = 59,049 > 40,000).
    The Arabic and CJK cluster signatures survive CCL at detectable levels.

    The symbol layer destroys the script fingerprint before CCL runs.

CONSTRUCTION — keyed bijection over 62,584 eligible Unicode code points:

    1. Enumerate eligible code points: assigned, non-control, non-combining,
       non-surrogate, WIDTH/5-safe (code point <= 99,999)
    2. Permute using Fisher-Yates shuffle seeded from SHA256(P1)
    3. Map each token value V -> permuted_candidates[V]
    4. Emit the mapped code point as a WIDTH/5 UCS-DEC token

    Properties:
        Bijection:      distinct input values -> distinct output values
        1:1:            no token count expansion
        Key-dependent:  different P1 -> different permutation
        Script-blind:   mapping is independent of input script
        Reversible:     given P1 and candidates list, fully recoverable

    After the symbol layer, tight script clusters are scattered across
    the full 0–62,583 eligible range. CCL then achieves high twist rates
    on the dispersed values.

PIPELINE:

    plaintext
      -> UCS-DEC encode            (ucs_dec_tool.py)
      -> Symbol substitution       (this tool)        <- symbol key P1
      -> CCL prime-twist           (prime_twist.py)   <- CCL key P2
      -> UCS-DEC output            (standard, transmit as-is)

KEY MODES:

    shared      P1 == P2. One verse drives both layers. Simpler operationally.
    independent P1 != P2. Independent keys. An adversary who recovers P2
                through coercion cannot reverse the symbol layer without P1.

WHEN TO APPLY:

    Always apply for Arabic, CJK, Hangul, Devanagari, Hebrew, or any
    script with code points above U+0800. The layer is 1:1 (no expansion)
    and costs only a table lookup per token.

    For ASCII/Latin text, the symbol layer adds visual camouflage
    (the output contains typographic symbols rather than decimal clusters)
    but the primary entropy gain comes from CCL, not this layer.

ALPHABETS:

    deepcut-v1   10 typographical symbols (one per digit value 0-9)
                 Used only for the base-N per-digit representation mode.
                 ¶ § † ‡ ⁂ ☉ ⁊ ‽ ✦ ☿

    bijection    62,584 eligible Unicode symbols, keyed permutation.
                 Each token value maps directly to one symbol.
                 Recommended for script fingerprint resistance.

Usage:
    python symbol_twist.py twist   [--key-prime P | --key-verse FILE]
                                   [--ccl-prime P | --ccl-verse FILE]
                                   [--alphabet deepcut-v1]
                                   [--schedule standard|mod3]
                                   [--width N] [--ref ID]
    python symbol_twist.py untwist <infile>
    python symbol_twist.py info    <infile>

Alphabets:
    deepcut-v1   10 typographical symbols, one per digit value 0-9
                 ¶ § † ‡ ⁂ ☉ ⁊ ‽ ✦ ☿
                 Pilcrow, Section, Dagger, Double Dagger, Asterism,
                 Sun, Tironian Et, Interrobang, Four-Pointed Star, Mercury

Key modes:
    shared      One prime drives both symbol and CCL layers.
                SYMBOL-KEY: shared
    independent Two separate primes. P1 for symbol, P2 for CCL.
                SYMBOL-KEY: independent

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

from mnemonic import derive, next_prime  # noqa: E402

# ── Named alphabets ───────────────────────────────────────────────────────────

ALPHABETS = {
    "deepcut-v1": [
        0x00B6,  # 0 → ¶  PILCROW SIGN
        0x00A7,  # 1 → §  SECTION SIGN
        0x2020,  # 2 → †  DAGGER
        0x2021,  # 3 → ‡  DOUBLE DAGGER
        0x2042,  # 4 → ⁂  ASTERISM
        0x2609,  # 5 → ☉  SUN
        0x204A,  # 6 → ⁊  TIRONIAN SIGN ET
        0x203D,  # 7 → ‽  INTERROBANG
        0x2726,  # 8 → ✦  BLACK FOUR POINTED STAR
        0x263F,  # 9 → ☿  MERCURY
    ],
}

ALPHABET_NAMES = sorted(ALPHABETS.keys())

BOX_INNER    = 41
MIDDLE_DOT   = "\u00b7"
DESTROY_FLAG = "IF COUNT FAILS: DESTROY IMMEDIATELY"


def _get_alphabet(name):
    if name not in ALPHABETS:
        raise ValueError("unknown alphabet: {0}. Available: {1}".format(
            name, ", ".join(ALPHABET_NAMES)))
    return ALPHABETS[name]


def _build_reverse(alphabet):
    """Build code_point -> digit_value reverse map."""
    return {cp: i for i, cp in enumerate(alphabet)}


# ── Key schedule (mirrors prime_twist.py exactly) ─────────────────────────────

def _scheduled_base(d, schedule="standard"):
    if schedule == "mod3":
        return 7 + (d % 3)
    return 10 if d <= 1 else d


def _effective_base(scheduled, token_value, width):
    if scheduled ** width > token_value:
        return scheduled
    return 10


# ── Core construction ─────────────────────────────────────────────────────────

def _to_base_digits(n, base, width):
    """Express n in given base, return list of digit values (MSB first, WIDTH long)."""
    if n == 0:
        return [0] * width
    digits = []
    tmp = n
    while tmp > 0:
        digits.append(tmp % base)
        tmp //= base
    while len(digits) < width:
        digits.append(0)
    return list(reversed(digits))


def _from_base_digits(digits, base):
    """Recover integer from digit value list in given base."""
    result = 0
    for d in digits:
        result = result * base + d
    return result


def symbolise(token_stream, prime_str, alphabet_name="deepcut-v1",
              width=5, schedule="standard"):
    """
    Apply symbol substitution to a UCS-DEC token stream.

    Each input token is expressed in a scheduled base using symbols from
    the named alphabet. Output is a WIDTH-times-longer UCS-DEC stream
    of symbol code points.

    Args:
        token_stream: whitespace-separated UCS-DEC token string
        prime_str:    decimal string of key prime P1
        alphabet_name: name of symbol alphabet (default: deepcut-v1)
        width:        FDS field width (default: 5)
        schedule:     base schedule — standard or mod3

    Returns:
        (output_tokens, symbol_map)
        output_tokens: list of WIDTH*n zero-padded strings
        symbol_map:    dict {input_position: base_used}
                       (only non-base-10 entries recorded)
    """
    alphabet = _get_alphabet(alphabet_name)
    tokens   = token_stream.split()
    p_digits = [int(d) for d in prime_str]
    p_len    = len(p_digits)

    output_tokens = []
    symbol_map    = {}

    for i, tok in enumerate(tokens):
        val   = int(tok)
        d     = p_digits[i % p_len]
        sched = _scheduled_base(d, schedule)
        base  = _effective_base(sched, val, width)

        digit_vals = _to_base_digits(val, base, width)
        sym_cps    = [alphabet[dv] for dv in digit_vals]

        for cp in sym_cps:
            output_tokens.append("{0:0{1}d}".format(cp, width))

        if base != 10:
            symbol_map[i] = base

    return output_tokens, symbol_map


def desymbolise(output_tokens, symbol_map, alphabet_name="deepcut-v1", width=5):
    """
    Reverse symbol substitution. Recovers original UCS-DEC token stream.

    Args:
        output_tokens: list of WIDTH*n symbol code point tokens
        symbol_map:    dict {input_position: base_used}
        alphabet_name: name of symbol alphabet
        width:         FDS field width

    Returns:
        List of original UCS-DEC token strings.
    """
    alphabet = _get_alphabet(alphabet_name)
    reverse  = _build_reverse(alphabet)
    n_input  = len(output_tokens) // width
    recovered = []

    for i in range(n_input):
        group  = output_tokens[i * width : (i + 1) * width]
        base   = symbol_map.get(i, 10)
        digits = [reverse[int(tok)] for tok in group]
        val    = _from_base_digits(digits, base)
        recovered.append("{0:0{1}d}".format(val, width))

    return recovered


def encode_symbol_map(symbol_map):
    """Compact sparse encoding: only non-base-10 entries as pos:base."""
    return ",".join("{0}:{1}".format(k, v)
                    for k, v in sorted(symbol_map.items()))


def decode_symbol_map(encoded, n_input):
    """Decode sparse symbol-map string to full dict."""
    result = {}
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
                if 0 <= pos < n_input:
                    result[pos] = base
            except ValueError:
                continue
    return result


# ── Artifact format ───────────────────────────────────────────────────────────

def _box_rule():
    return "+" + "-" * BOX_INNER + "+"


def _box_line(content=""):
    return "|" + ("  " + content).ljust(BOX_INNER) + "|"


def make_artifact(output_tokens, symbol_map, prime_str,
                  alphabet_name, schedule, width,
                  ccl_prime_str=None, ref="", med="PAPER",
                  key_mode="shared"):
    """
    Wrap symbolised token stream in a self-describing FDS Print Profile
    artifact with RSRC block carrying the symbol-map and parameters.
    """
    rows = []
    for i in range(0, len(output_tokens), 6):
        rows.append("  ".join(output_tokens[i:i + 6]))
    payload = "\n".join(rows)

    pad        = "0" * width
    real_count = len([t for t in output_tokens if t != pad])
    crc        = binascii.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    crc_str    = format(crc, "08X")
    generated  = time.strftime("%Y-%m-%d")
    changed    = len(symbol_map)

    alphabet   = _get_alphabet(alphabet_name)
    alpha_str  = " ".join(to_chr(cp) for cp in alphabet)

    enc_line = "ENC: UCS {d} DEC {d} COL/6 {d} PAD/{p} {d} WIDTH/{w}".format(
        d=MIDDLE_DOT, p=pad, w=width)
    cnt_line = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    rsrc_lines = [
        "RSRC: BEGIN",
        "  TYPE:         symbol-twist",
        "  VERSION:      1",
        "  NOTE:         TEST IMPLEMENTATION -- not normatively specified",
        "  ALPHABET:     {0}".format(alphabet_name),
        "  ALPHABET-STR: {0}".format(alpha_str),
        "  SCHEDULE:     {0}".format(schedule),
        "  WIDTH:        {0}".format(width),
        "  SYMBOL-KEY:   {0}".format(key_mode),
        "  PRIME-P1:     {0}".format(prime_str),
    ]
    if key_mode == "independent" and ccl_prime_str:
        rsrc_lines.append(
            "  PRIME-P2:     {0}".format(ccl_prime_str))
    rsrc_lines += [
        "  INPUT-TOKENS: {0}".format(len(output_tokens) // width),
        "  OUTPUT-TOKENS:{0}".format(len(output_tokens)),
        "  TWISTED:      {0}".format(changed),
        "  GENERATED:    {0}".format(generated),
        "  SYMBOL-MAP:   {0}".format(encode_symbol_map(symbol_map)),
        "RSRC: END",
    ]

    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line("REF: {0}  PAGE 1/1".format(ref)))
    header_lines.append(_box_line(enc_line))
    header_lines.append(_box_line("MED: {0}".format(med)))
    header_lines.append(_box_line(
        "SYM: {0} {1} NOT ENCRYPTED".format(alphabet_name, MIDDLE_DOT)))
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
    """Parse a symbol-twist artifact. Returns dict."""
    fields         = {}
    output_tokens  = []
    in_rsrc        = False
    in_payload     = False

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
                output_tokens.extend(toks)
            elif stripped and not stripped.startswith("+") \
                    and not stripped.startswith("|") \
                    and "RESERVED" not in stripped \
                    and "VALUES" not in stripped:
                pass  # structural line — intentionally ignored

    width    = int(fields.get("WIDTH", "5"))
    n_input  = int(fields.get("INPUT-TOKENS", str(len(output_tokens) // width)))
    enc_smap = fields.get("SYMBOL-MAP", "")
    sym_map  = decode_symbol_map(enc_smap, n_input)

    return {
        "alphabet":     fields.get("ALPHABET", "deepcut-v1"),
        "schedule":     fields.get("SCHEDULE", "standard"),
        "width":        width,
        "key_mode":     fields.get("SYMBOL-KEY", "shared"),
        "prime_p1":     fields.get("PRIME-P1", ""),
        "prime_p2":     fields.get("PRIME-P2", ""),
        "symbol_map":   sym_map,
        "n_input":      n_input,
        "output_tokens": output_tokens,
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


def _load_prime(args):
    """Resolve P1 from --key-prime or --key-verse."""
    if getattr(args, "key_prime", None):
        return args.key_prime.strip()
    if getattr(args, "key_verse", None):
        with io.open(args.key_verse, "r", encoding="utf-8") as f:
            verse = f.read().rstrip("\r\n")
        return str(derive(verse)["P"])
    raise ValueError("--key-prime or --key-verse required")


def _load_ccl_prime(args, p1):
    """Resolve P2: shared with P1 or independently from --ccl-prime/--ccl-verse."""
    if getattr(args, "ccl_prime", None):
        return args.ccl_prime.strip(), "independent"
    if getattr(args, "ccl_verse", None):
        with io.open(args.ccl_verse, "r", encoding="utf-8") as f:
            verse = f.read().rstrip("\r\n")
        return str(derive(verse)["P"]), "independent"
    return p1, "shared"


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Symbol Substitution Layer for FDS token streams.\n"
            "Apply BEFORE CCL prime-twist for maximum entropy gain.\n"
            "TEST IMPLEMENTATION -- not yet normatively specified."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Pipeline:\n"
            "  cat payload.txt | python symbol_twist.py twist \\\n"
            "      --key-verse key.txt --ref SYM1 | \\\n"
            "      python prime_twist.py stack --verse-file verses.txt \\\n"
            "      --ref CCL3 > artifact.txt\n"
            "\n"
            "  python prime_twist.py unstack artifact.txt | \\\n"
            "      python symbol_twist.py untwist /dev/stdin\n"
        )
    )

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # twist
    pt = sub.add_parser("twist",
        help="apply symbol substitution to stdin UCS-DEC token stream")
    key_group = pt.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--key-prime", metavar="P",
        help="symbol layer key prime (decimal string)")
    key_group.add_argument("--key-verse", metavar="FILE",
        help="file containing symbol layer key verse (one verse)")
    ccl_group = pt.add_mutually_exclusive_group()
    ccl_group.add_argument("--ccl-prime", metavar="P",
        help="CCL layer key prime (if independent from symbol key)")
    ccl_group.add_argument("--ccl-verse", metavar="FILE",
        help="file containing CCL layer key verse (if independent)")
    pt.add_argument("--alphabet", default="deepcut-v1",
        choices=ALPHABET_NAMES,
        help="symbol alphabet (default: deepcut-v1)")
    pt.add_argument("--schedule", default="standard",
        choices=["standard", "mod3"],
        help="base schedule (default: standard)")
    pt.add_argument("--width", type=int, default=5, metavar="N",
        help="UCS-DEC field width (default: 5)")
    pt.add_argument("--ref", default="", metavar="ID")
    pt.add_argument("--med", default="PAPER", metavar="MEDIUM")

    # untwist
    pu = sub.add_parser("untwist",
        help="reverse symbol substitution; emit bare UCS-DEC token stream")
    pu.add_argument("infile", help="symbol-twist artifact file")

    # info
    pi = sub.add_parser("info",
        help="show artifact parameters without reversing")
    pi.add_argument("infile", help="symbol-twist artifact file")

    return p


def cmd_twist(args):
    data = _read_stdin().strip()
    if not data:
        print("Error: empty input", file=sys.stderr)
        return 1

    p1 = _load_prime(args)
    p2, key_mode = _load_ccl_prime(args, p1)

    output_tokens, symbol_map = symbolise(
        data, p1,
        alphabet_name=args.alphabet,
        width=args.width,
        schedule=args.schedule)

    changed = len(symbol_map)
    n_input = len(data.split())
    print("Symbol layer: {0} tokens → {1} tokens ({2}x expansion)".format(
        n_input, len(output_tokens), args.width), file=sys.stderr)
    print("  Twisted bases: {0}/{1} input positions ({2:.1f}%)".format(
        changed, n_input, 100.0 * changed / n_input if n_input else 0),
        file=sys.stderr)
    print("  Key mode: {0}".format(key_mode), file=sys.stderr)

    artifact = make_artifact(
        output_tokens, symbol_map, p1,
        alphabet_name=args.alphabet,
        schedule=args.schedule,
        width=args.width,
        ccl_prime_str=p2 if key_mode == "independent" else None,
        ref=args.ref,
        med=args.med,
        key_mode=key_mode)

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
    if not parsed["output_tokens"]:
        print("Error: no payload found in artifact", file=sys.stderr)
        return 1

    recovered = desymbolise(
        parsed["output_tokens"],
        parsed["symbol_map"],
        alphabet_name=parsed["alphabet"],
        width=parsed["width"])

    print("Symbol layer reversed: {0} tokens → {1} tokens".format(
        len(parsed["output_tokens"]), len(recovered)), file=sys.stderr)

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
    alphabet = _get_alphabet(parsed["alphabet"])
    alpha_str = " ".join(to_chr(cp) for cp in alphabet)

    print("File:          {0}".format(args.infile))
    print("Alphabet:      {0}  [{1}]".format(parsed["alphabet"], alpha_str))
    print("Schedule:      {0}".format(parsed["schedule"]))
    print("Width:         {0}".format(parsed["width"]))
    print("Key mode:      {0}".format(parsed["key_mode"]))
    print("Input tokens:  {0}".format(parsed["n_input"]))
    print("Output tokens: {0}".format(len(parsed["output_tokens"])))
    print("Twisted:       {0}/{1} input positions".format(
        len(parsed["symbol_map"]), parsed["n_input"]))
    return 0


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "twist":   return cmd_twist(args)
        if args.command == "untwist": return cmd_untwist(args)
        if args.command == "info":    return cmd_info(args)
    except (ValueError, IOError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
