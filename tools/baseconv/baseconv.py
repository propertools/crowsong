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
Supports bases 2–36.
Digits above 9 are represented as uppercase A–Z.
Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""
from __future__ import print_function, unicode_literals
import sys
DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def _validate_base(base, name):
    """Validate that a base is within the supported range."""
    if not (2 <= base <= 36):
        raise ValueError("{0} must be between 2 and 36".format(name))
def to_int(number_str, base):
    """Parse a string in the given base to a Python int."""
    _validate_base(base, "from_base")
    if not number_str:
        raise ValueError("number must not be empty")
    if number_str.startswith("-"):
        raise ValueError("negative numbers are not supported")
    try:
        return int(number_str.upper(), base)
    except ValueError:
        raise ValueError(
            "invalid digit for base {0}: {1}".format(base, number_str)
        )
def from_int(value, base):
    """Convert a non-negative Python int to a string in the given base."""
    _validate_base(base, "to_base")
    if value < 0:
        raise ValueError("negative numbers are not supported")
    if value == 0:
        return "0"
    if base == 10:
        return str(value)
    out = []
    while value > 0:
        out.append(DIGITS[value % base])
        value //= base
    out.reverse()
    return "".join(out)
def convert(number_str, from_base, to_base):
    """
    Convert a number string from one base to another.
    Args:
        number_str: String representation of the number in from_base
        from_base:  Integer source base (2-36)
        to_base:    Integer target base (2-36)
    Returns:
        String representation of the number in to_base.
    """
    value = to_int(number_str, from_base)
    return from_int(value, to_base)
def main():
    if len(sys.argv) != 4:
        print(
            "Usage: python baseconv.py <number> <from_base> <to_base>",
            file=sys.stderr
        )
        return 1
    number_str = sys.argv[1]
    try:
        from_base = int(sys.argv[2])
        to_base = int(sys.argv[3])
    except ValueError:
        print("Error: bases must be integers", file=sys.stderr)
        return 1
    try:
        print(convert(number_str, from_base, to_base))
        return 0
    except ValueError as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())
