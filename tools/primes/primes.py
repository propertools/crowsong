#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
primes.py - prime utilities with deterministic Miller-Rabin

Usage:
    python primes.py is-prime <n>
    python primes.py next-prime <n>
    python primes.py first <count>
    python primes.py range <start> <end>
    python primes.py generate <count> <outfile>
    python primes.py verify <infile>

Examples:
    python primes.py is-prime 17
    python primes.py next-prime 1000
    python primes.py first 10
    python primes.py first 10000
    python primes.py range 100 200
    python primes.py generate 10000 docs/sequences/primes-10000.txt
    python primes.py verify docs/sequences/primes-10000.txt

Compatibility: Python 2.7+ / 3.x
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import sys
import time

# Sufficient for deterministic Miller-Rabin below:
# 3,317,044,064,679,887,385,961,981
#
# PRIME-001: this set must remain identical to WITNESSES_SMALL in
# tools/mnemonic/mnemonic.py. Both implement the same construction;
# primes.py stays dependency-free so they are not shared via import.
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


# ---------------------------------------------------------------------------
# SHA256 helpers for generate / verify
# ---------------------------------------------------------------------------

def _sha256_hex(text):
    """Return SHA256 of a Unicode string encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_body(primes_iter):
    """Format an iterable of primes as a body string: one per line, trailing LF."""
    return "\n".join(str(p) for p in primes_iter) + "\n"


def _parse_prime_header(text):
    """
    Extract declared Count and SHA256 from a prime file header.

    Processes all '#'-prefixed lines in the file (symmetric with _extract_body,
    which processes all non-'#' lines). Blank lines between header fields do not
    interrupt parsing.
    Returns a dict with keys 'count' (int or None) and 'sha256' (str or None).
    """
    fields = {}
    for line in text.splitlines():
        if not line.startswith("#"):
            continue
        content = line[1:].strip()
        if ":" in content:
            key, _, val = content.partition(":")
            fields[key.strip().lower()] = val.strip()

    count = None
    if "count" in fields:
        try:
            count = int(fields["count"])
        except ValueError:
            pass

    return {"count": count, "sha256": fields.get("sha256")}


def _extract_body(text):
    """
    Return the body of a prime file as a normalised string.

    Body lines are all non-'#' non-empty lines, joined with newlines
    and terminated with a single trailing newline.
    """
    body_lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    return "\n".join(body_lines) + "\n" if body_lines else ""


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

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


def cmd_is_prime(args):
    print("true" if is_prime(args.n) else "false")
    return 0


def cmd_next_prime(args):
    print(next_prime(args.n))
    return 0


def cmd_first(args):
    for p in generate_first_primes(args.count):
        print(p)
    return 0


def cmd_range(args):
    if args.end < args.start:
        print("Error: end must be >= start", file=sys.stderr)
        return 1
    for p in generate_primes_in_range(args.start, args.end):
        print(p)
    return 0


def cmd_generate(args):
    """Write the first <count> primes to <outfile> with a SHA256 header."""
    primes = list(generate_first_primes(args.count))
    body   = _make_body(primes)
    digest = _sha256_hex(body)
    date   = time.strftime("%Y-%m-%d")

    header = "\n".join([
        "# primes - first {0} primes".format(args.count),
        "#",
        "# Count:     {0}".format(args.count),
        "# SHA256:    {0}".format(digest),
        "# Generated: {0}".format(date),
        "# Tool:      tools/primes/primes.py",
        "#",
    ])

    with io.open(args.outfile, "w", encoding="utf-8") as f:
        f.write(header + "\n" + body)

    print("Written:  {0} ({1} primes)".format(args.outfile, args.count),
          file=sys.stderr)
    print("SHA256:   {0}".format(digest), file=sys.stderr)
    return 0


def cmd_verify(args):
    """
    Verify a prime file generated by this tool.

    Checks:
      1. Count declared in header matches count of primes in body
      2. SHA256 declared in header matches SHA256 of body
      3. Primes recomputed from first principles match the file body

    Assumes the file contains the first N primes in ascending order,
    as produced by 'generate'. Files produced by 'range' will fail
    the primality recomputation check because 'range' does not start at 2.
    """
    try:
        with io.open(args.infile, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError) as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    header = _parse_prime_header(content)
    body   = _extract_body(content)

    body_lines = [l for l in body.splitlines() if l]
    primes_in_file = []
    for line in body_lines:
        try:
            primes_in_file.append(int(line.strip()))
        except ValueError:
            print("Error: non-integer in body: {0!r}".format(line),
                  file=sys.stderr)
            return 1

    count         = len(primes_in_file)
    digest_actual = _sha256_hex(body)
    ok            = True

    def status(flag, declared=None):
        if flag:
            return "OK"
        return "FAIL" + (" (declared: {0})".format(declared) if declared is not None else "")

    print("File:     {0}".format(args.infile))

    if header["count"] is not None:
        count_ok = (count == header["count"])
        print("Count:    {0}  {1}".format(
            count, status(count_ok, header["count"])))
        if not count_ok:
            ok = False
    else:
        print("Count:    {0} (no count declared in header)".format(count))

    if header["sha256"] is not None:
        sha_ok = (digest_actual == header["sha256"].lower())
        print("SHA256:   {0}  {1}".format(
            digest_actual, status(sha_ok, header["sha256"])))
        if not sha_ok:
            ok = False
    else:
        print("SHA256:   {0} (no SHA256 declared in header)".format(
            digest_actual))

    expected   = list(generate_first_primes(count))
    primes_ok  = (primes_in_file == expected)
    print("Primes:   recomputed {0}  {1}".format(count, status(primes_ok)))
    if not primes_ok:
        ok = False

    print("Verification: {0}".format("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
    p_range.add_argument("end",   type=nonnegative_int, help="range end")

    p_gen = subparsers.add_parser(
        "generate",
        help="write the first COUNT primes to OUTFILE with a SHA256 header"
    )
    p_gen.add_argument("count",  type=positive_int, help="number of primes")
    p_gen.add_argument("outfile", help="output file path")

    p_ver = subparsers.add_parser(
        "verify",
        help="verify a 'generate'-produced prime file (first-N format) against its declared SHA256"
    )
    p_ver.add_argument("infile", help="prime file to verify")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "is-prime":   return cmd_is_prime(args)
        if args.command == "next-prime": return cmd_next_prime(args)
        if args.command == "first":      return cmd_first(args)
        if args.command == "range":      return cmd_range(args)
        if args.command == "generate":   return cmd_generate(args)
        if args.command == "verify":     return cmd_verify(args)
    except (IOError, OSError, ValueError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
