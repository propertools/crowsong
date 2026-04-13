#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
baseconv.py — convert integers between arbitrary base representations

Usage:
    python baseconv.py <number> <from_base> <to_base>

Examples:
    python baseconv.py 255 10 16        # decimal to hex:     FF
    python baseconv.py FF 16 10         # hex to decimal:      255
    python baseconv.py 11111111 2 10    # binary to decimal:   255
    python baseconv.py 255 10 2         # decimal to binary:   11111111
    python baseconv.py 255 10 8         # decimal to octal:    377
    python baseconv.py 26716 10 36      # decimal to base-36:  KM4

Supports bases 2-36.
Digits above 9 are represented as uppercase A-Z.
Input is case-insensitive. Output is always uppercase.
Negative numbers, signed forms, and floating-point values are not supported.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""
from __future__ import print_function, unicode_literals

import sys

# Explicitly Unicode. Under unicode_literals this is redundant,
# but the u"" prefix makes the intent unambiguous for Py2/Py3 audits.
DIGITS = u"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _validate_base(base, name):
    """Validate that a base is within the supported range (2-36 inclusive)."""
    if not (2 <= base <= 36):
        raise ValueError(u"{0} must be between 2 and 36".format(name))


def to_int(number_str, base):
    """
    Parse an unsigned string in the given base to a Python int.

    Args:
        number_str: String representation of a non-negative integer.
        base:       Integer base to interpret the string in (2-36).

    Returns:
        Python int value.

    Raises:
        ValueError: If base is out of range, the string is empty, contains
            surrounding whitespace, is signed, or contains digits invalid
            for the given base.
    """
    _validate_base(base, u"from_base")

    if not number_str:
        raise ValueError(u"number must not be empty")

    # Reject surrounding whitespace explicitly rather than inheriting
    # whatever int() happens to do — protocol tools should be strict.
    if number_str != number_str.strip():
        raise ValueError(u"number must not contain surrounding whitespace")

    # Reject both signs for symmetry; silently accepting '+' while
    # rejecting '-' would be an inconsistent and undocumented quirk.
    if number_str[0] in u"+-":
        raise ValueError(u"signed numbers are not supported")

    number_str = number_str.upper()
    allowed = set(DIGITS[:base])
    for idx, ch in enumerate(number_str):
        if ch not in allowed:
            raise ValueError(
                u"invalid digit at offset {0} for base {1}: {2}".format(
                    idx, base, ch
                )
            )

    return int(number_str, base)


def from_int(value, base):
    """
    Convert a non-negative Python int to a string in the given base.

    Args:
        value: Non-negative Python int.
        base:  Integer target base (2-36).

    Returns:
        Uppercase string representation of value in the given base.

    Raises:
        ValueError: If base is out of range or value is negative.
    """
    _validate_base(base, u"to_base")
    if value < 0:
        raise ValueError(u"negative numbers are not supported")
    if value == 0:
        return u"0"

    # No special-case for base 10: the generic loop is correct for all
    # bases and avoids a str() call whose return type differs across
    # Python 2 (bytes) and Python 3 (str/unicode).
    out = []
    while value > 0:
        out.append(DIGITS[value % base])
        value //= base
    out.reverse()
    return u"".join(out)


def convert(number_str, from_base, to_base):
    """
    Convert a number string from one base to another.

    Args:
        number_str: String representation of the number in from_base.
        from_base:  Integer source base (2-36).
        to_base:    Integer target base (2-36).

    Returns:
        Uppercase string representation of the number in to_base.

    Raises:
        ValueError: If either base is outside 2-36, the input is empty,
            signed, contains surrounding whitespace, or contains digits
            invalid for from_base.
    """
    return from_int(to_int(number_str, from_base), to_base)


def main(argv=None):
    """
    CLI entry point. Accepts an optional argv list for testability;
    defaults to sys.argv[1:].
    """
    if argv is None:
        argv = sys.argv[1:]

    if argv in ([u"-h"], [u"--help"]):
        print(u"Usage: python baseconv.py <number> <from_base> <to_base>")
        return 0

    if len(argv) != 3:
        print(
            u"Usage: python baseconv.py <number> <from_base> <to_base>",
            file=sys.stderr
        )
        return 1

    number_str = argv[0]
    try:
        from_base = int(argv[1])
        to_base = int(argv[2])
    except ValueError:
        print(u"Error: bases must be integers", file=sys.stderr)
        return 1

    try:
        print(convert(number_str, from_base, to_base))
        return 0
    except ValueError as err:
        print(u"Error: {0}".format(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
