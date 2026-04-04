#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
constants.py — named mathematical constant digit generator

Generates digit strings for named constants suitable for use as
initialisation vectors in the Channel Camouflage Layer and Mnemonic
Share Wrapping constructions.

Usage:
    python constants.py list
    python constants.py digits <name> <count>
    python constants.py show <name> <count>
    python constants.py generate <name> <count> <outfile>
    python constants.py verify <name> <infile>

Examples:
    python constants.py list
    python constants.py digits pi 100
    python constants.py show phi 200
    python constants.py generate sqrt2 10000 docs/constants/sqrt2-10000.txt
    python constants.py verify pi docs/constants/pi-10000.txt

Requires:
    mpmath  (pip install mpmath)

Generated files are plain UTF-8 text and require no dependencies to read.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import os
import sys
import time

try:
    import mpmath
    MPMATH_AVAILABLE = True
except ImportError:
    MPMATH_AVAILABLE = False


GROUP_SIZE = 10
GROUPS_PER_LINE = 6
EXTRA_PRECISION = 40


def _pi(mp):
    return mp.pi


def _e(mp):
    return mp.e


def _phi(mp):
    return mp.phi


def _sqrt2(mp):
    return mp.sqrt(2)


def _sqrt3(mp):
    return mp.sqrt(3)


def _sqrt5(mp):
    return mp.sqrt(5)


def _ln2(mp):
    return mp.log(2)


def _apery(mp):
    return mp.apery


CONSTANTS = {
    "pi": {
        "fn": _pi,
        "name": "Pi",
        "symbol": "π",
        "oeis": "A000796",
        "notes": "Ratio of circumference to diameter. Infinite, non-repeating.",
    },
    "e": {
        "fn": _e,
        "name": "Euler's number",
        "symbol": "e",
        "oeis": "A001113",
        "notes": "Base of the natural logarithm. Infinite, non-repeating.",
    },
    "phi": {
        "fn": _phi,
        "name": "Golden ratio",
        "symbol": "φ",
        "oeis": "A001622",
        "notes": "Limit of consecutive Fibonacci ratios. Infinite, non-repeating.",
    },
    "sqrt2": {
        "fn": _sqrt2,
        "name": "Square root of 2",
        "symbol": "√2",
        "oeis": "A002193",
        "notes": "First known irrational number. Infinite, non-repeating.",
    },
    "sqrt3": {
        "fn": _sqrt3,
        "name": "Square root of 3",
        "symbol": "√3",
        "oeis": "A002194",
        "notes": "Infinite, non-repeating.",
    },
    "sqrt5": {
        "fn": _sqrt5,
        "name": "Square root of 5",
        "symbol": "√5",
        "oeis": "A002163",
        "notes": "Infinite, non-repeating.",
    },
    "ln2": {
        "fn": _ln2,
        "name": "Natural logarithm of 2",
        "symbol": "ln(2)",
        "oeis": "A002162",
        "notes": "Infinite, non-repeating.",
    },
    "apery": {
        "fn": _apery,
        "name": "Apery's constant",
        "symbol": "ζ(3)",
        "oeis": "A002117",
        "notes": "Sum of reciprocals of cubes. Infinite, likely non-repeating.",
    },
}


def positive_int(value):
    """argparse type: integer >= 1"""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def require_mpmath():
    """Fail clearly if mpmath is unavailable."""
    if not MPMATH_AVAILABLE:
        raise RuntimeError(
            "mpmath is required for digit generation.\n"
            "Install with: pip install mpmath"
        )


def get_constant_meta(name):
    """Return registry metadata for a constant name, or raise ValueError."""
    key = name.lower()
    if key not in CONSTANTS:
        raise ValueError("unknown constant: {0}".format(name))
    return key, CONSTANTS[key]


def get_digits(name, count):
    """
    Return the first `count` decimal digits of the named constant as a plain
    digit string (no decimal point, no whitespace).

    Digits begin with the leading integer digit, e.g. pi -> '31415...'.
    """
    require_mpmath()
    key, meta = get_constant_meta(name)

    mpmath.mp.dps = count + EXTRA_PRECISION
    value = meta["fn"](mpmath.mp)

    # Ask for more than needed, then strip to digits only.
    rendered = mpmath.nstr(value, count + 20, strip_zeros=False)
    digits = "".join(ch for ch in rendered if ch.isdigit())

    if len(digits) < count:
        raise RuntimeError(
            "insufficient digits generated for {0}: wanted {1}, got {2}".format(
                key, count, len(digits)
            )
        )

    return digits[:count]


def format_digits(digits, group=GROUP_SIZE, per_line=GROUPS_PER_LINE):
    """
    Format a digit string into grouped, line-wrapped output.

    Default: 10 digits per group, 6 groups per line (60 digits per line).
    """
    groups = [digits[i:i + group] for i in range(0, len(digits), group)]
    lines = [
        " ".join(groups[i:i + per_line])
        for i in range(0, len(groups), per_line)
    ]
    return "\n".join(lines)


def sha256_hex(text):
    """Return SHA-256 of a Unicode string encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_file_header(name, count, digits):
    """Return a self-describing plain-text header for a generated constant file."""
    _, meta = get_constant_meta(name)
    generated = time.strftime("%Y-%m-%d")
    digest = sha256_hex(digits)

    lines = [
        "# {symbol} — {full_name}".format(
            symbol=meta["symbol"], full_name=meta["name"]
        ),
        "#",
        "# Constant:  {0}".format(name),
        "# OEIS:      {0}".format(meta["oeis"]),
        "# Notes:     {0}".format(meta["notes"]),
        "#",
        "# Digits:    {0}".format(count),
        "# Format:    decimal, {0} digits per group, {1} groups per line".format(
            GROUP_SIZE, GROUPS_PER_LINE
        ),
        "# SHA256:    {0}".format(digest),
        "# Generated: {0}".format(generated),
        "# Tool:      tools/constants.py (Proper Tools SRL)",
        "#",
        "# This file contains only decimal digits of {0}.".format(meta["symbol"]),
        "# No decimal point. Digits begin with the leading integer digit.",
        "# Suitable for use as an IV source per draft-darley-shard-bundle-01.",
        "#",
    ]
    return "\n".join(lines)


def parse_constant_file(path):
    """
    Parse a generated constant file.

    Returns:
        dict with keys:
            digits
            sha256_declared
            name_declared
            count_declared
    """
    digits = []
    sha256_declared = None
    name_declared = None
    count_declared = None

    with io.open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n\r")
            if line.startswith("#"):
                if "Constant:" in line:
                    name_declared = line.split("Constant:", 1)[1].strip()
                elif "Digits:" in line:
                    value = line.split("Digits:", 1)[1].strip()
                    try:
                        count_declared = int(value)
                    except ValueError:
                        pass
                elif "SHA256:" in line:
                    sha256_declared = line.split("SHA256:", 1)[1].strip()
            else:
                digits.extend(ch for ch in line if ch.isdigit())

    return {
        "digits": "".join(digits),
        "sha256_declared": sha256_declared,
        "name_declared": name_declared,
        "count_declared": count_declared,
    }


def cmd_list(_args):
    """List all known constants."""
    fmt = "{:<8}  {:<6}  {:<10}  {}"
    print(fmt.format("name", "symbol", "OEIS", "notes"))
    print("-" * 72)
    for key in sorted(CONSTANTS):
        meta = CONSTANTS[key]
        print(fmt.format(
            key,
            meta["symbol"],
            meta["oeis"],
            meta["notes"][:50]
        ))
    return 0


def cmd_digits(args):
    """Print plain digits only."""
    print(get_digits(args.name, args.count))
    return 0


def cmd_show(args):
    """Print formatted digits with heading."""
    key, meta = get_constant_meta(args.name)
    digits = get_digits(key, args.count)
    print("{symbol} — {name} ({count} digits)".format(
        symbol=meta["symbol"],
        name=meta["name"],
        count=args.count
    ))
    print()
    print(format_digits(digits))
    return 0


def cmd_generate(args):
    """Generate a self-describing constant file."""
    key, _meta = get_constant_meta(args.name)
    digits = get_digits(key, args.count)
    header = make_file_header(key, args.count, digits)
    body = format_digits(digits)

    outdir = os.path.dirname(args.outfile)
    if outdir and not os.path.exists(outdir):
        os.makedirs(outdir)

    with io.open(args.outfile, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n\n")
        f.write(body)
        f.write("\n")

    print("Written:  {0}".format(args.outfile))
    print("Digits:   {0}".format(args.count))
    print("SHA256:   {0}".format(sha256_hex(digits)))
    return 0


def cmd_verify(args):
    """Verify a generated constant file."""
    key, _meta = get_constant_meta(args.name)
    parsed = parse_constant_file(args.infile)
    digits = parsed["digits"]

    if not digits:
        raise ValueError("no digits found in file")

    count = len(digits)
    sha256_actual = sha256_hex(digits)
    sha256_ok = (sha256_actual == parsed["sha256_declared"])

    recomputed = get_digits(key, count)
    digits_ok = (digits == recomputed)

    name_ok = (
        parsed["name_declared"] is None or
        parsed["name_declared"].lower() == key
    )

    count_ok = (
        parsed["count_declared"] is None or
        parsed["count_declared"] == count
    )

    print("File:         {0}".format(args.infile))
    print("Constant:     {0} — {1}".format(
        key,
        "OK" if name_ok else "FAIL (declared: {0})".format(parsed["name_declared"])
    ))
    print("Digits:       {0} — {1}".format(
        count,
        "OK" if count_ok else "FAIL (declared: {0})".format(parsed["count_declared"])
    ))
    print("SHA256:       {0} — {1}".format(
        sha256_actual,
        "OK" if sha256_ok else "FAIL (declared: {0})".format(parsed["sha256_declared"])
    ))
    print("Recomputed:   {0}".format(
        "OK — digits match" if digits_ok else "FAIL — digits differ"
    ))

    if name_ok and count_ok and sha256_ok and digits_ok:
        print("Verification: PASS")
        return 0

    print("Verification: FAIL")
    return 1


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Named mathematical constant digit generator.\n"
            "Produces digit strings for IV sources and related constructions."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python constants.py list\n"
            "  python constants.py digits pi 100\n"
            "  python constants.py show phi 200\n"
            "  python constants.py generate e 10000 docs/constants/e-10000.txt\n"
            "  python constants.py verify pi docs/constants/pi-10000.txt\n"
        )
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    p_list = subparsers.add_parser("list", help="list all known constants")
    p_list.set_defaults(func=cmd_list)

    p_digits = subparsers.add_parser(
        "digits",
        help="print the first N digits of a constant (plain, no formatting)"
    )
    p_digits.add_argument("name", help="constant name (see list)")
    p_digits.add_argument("count", type=positive_int, help="number of digits")
    p_digits.set_defaults(func=cmd_digits)

    p_show = subparsers.add_parser(
        "show",
        help="print the first N digits, formatted for readability"
    )
    p_show.add_argument("name", help="constant name (see list)")
    p_show.add_argument("count", type=positive_int, help="number of digits")
    p_show.set_defaults(func=cmd_show)

    p_generate = subparsers.add_parser(
        "generate",
        help="generate a self-describing digit file"
    )
    p_generate.add_argument("name", help="constant name (see list)")
    p_generate.add_argument("count", type=positive_int, help="number of digits")
    p_generate.add_argument("outfile", help="output file path")
    p_generate.set_defaults(func=cmd_generate)

    p_verify = subparsers.add_parser(
        "verify",
        help="verify a generated digit file against its declared metadata"
    )
    p_verify.add_argument("name", help="constant name (for recomputation)")
    p_verify.add_argument("infile", help="file to verify")
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.func(args)
    except (ValueError, RuntimeError, IOError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
