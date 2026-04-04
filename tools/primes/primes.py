#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
primes.py — prime utilities with deterministic Miller-Rabin

Usage:
    python primes.py is-prime <n>
    python primes.py next-prime <n>
    python primes.py first <count>
    python primes.py range <start> <end>

Examples:
    python primes.py is-prime 17
    python primes.py next-prime 1000
    python primes.py first 10
    python primes.py first 10000
    python primes.py range 100 200

Compatibility: Python 2.7+ / 3.x
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import sys

# Sufficient for deterministic Miller-Rabin below:
# 3,317,044,064,679,887,385,961,981
WITNESSES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
SMALL_PRIMES = WITNESSES


def is_prime(n):
    """
    Return True if n is prime.

    Deterministic Miller-Rabin for n < 3.3e24 using the witness
    set above. For this utility's intended use, that is more than enough.
    """
    if n < 2:
        return False

    for p in SMALL_PRIMES:
        if n == p:
            return True
        if n % p == 0:
            return False

    d = n - 1
    r = 0
    while (d % 2) == 0:
        d //= 2
        r += 1

    for a in WITNESSES:
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


def next_prime(n):
    """Return the smallest prime >= n."""
    if n <= 2:
        return 2

    if n % 2 == 0:
        n += 1

    while not is_prime(n):
        n += 2

    return n


def generate_first_primes(count):
    """Yield the first `count` primes."""
    if count < 1:
        return

    yielded = 0
    candidate = 2

    while yielded < count:
        if is_prime(candidate):
            yield candidate
            yielded += 1
        candidate = 3 if candidate == 2 else candidate + 2


def generate_primes_in_range(start, end):
    """Yield all primes p such that start <= p <= end."""
    if end < 2 or end < start:
        return

    candidate = next_prime(start)
    while candidate <= end:
        yield candidate
        candidate = next_prime(candidate + 1)


def positive_int(value):
    """argparse type: integer >= 1"""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def nonnegative_int(value):
    """argparse type: integer >= 0"""
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return ivalue


def build_parser():
    parser = argparse.ArgumentParser(
        description="Prime utilities with deterministic Miller-Rabin."
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    p_is = subparsers.add_parser(
        "is-prime",
        help="test whether an integer is prime"
    )
    p_is.add_argument("n", type=nonnegative_int, help="integer to test")

    p_next = subparsers.add_parser(
        "next-prime",
        help="return the smallest prime >= n"
    )
    p_next.add_argument("n", type=nonnegative_int, help="lower bound")

    p_first = subparsers.add_parser(
        "first",
        help="print the first COUNT primes, one per line"
    )
    p_first.add_argument("count", type=positive_int, help="number of primes")

    p_range = subparsers.add_parser(
        "range",
        help="print all primes in [start, end], one per line"
    )
    p_range.add_argument("start", type=nonnegative_int, help="range start")
    p_range.add_argument("end", type=nonnegative_int, help="range end")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "is-prime":
        print("true" if is_prime(args.n) else "false")
        return 0

    if args.command == "next-prime":
        print(next_prime(args.n))
        return 0

    if args.command == "first":
        for p in generate_first_primes(args.count):
            print(p)
        return 0

    if args.command == "range":
        if args.end < args.start:
            print("Error: end must be >= start", file=sys.stderr)
            return 1
        for p in generate_primes_in_range(args.start, args.end):
            print(p)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
