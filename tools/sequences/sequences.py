#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sequences.py — OEIS sequence mirror and quick reference tool

Fetches, caches, and serves terms from a curated subset of the
On-Line Encyclopedia of Integer Sequences (OEIS).

Usage:
    python sequences.py list
    python sequences.py show <id>
    python sequences.py terms <id> [--count N]
    python sequences.py sync [<id> ...] [--all]
    python sequences.py verify [<id> ...]

Examples:
    python sequences.py list
    python sequences.py show A000796
    python sequences.py terms A000040 --count 100
    python sequences.py sync A000796 A000040
    python sequences.py sync --all
    python sequences.py verify

Fetched data is stored in docs/sequences/ as plain-text files.
Each file is self-describing and human-readable without software.
Files are suitable for inclusion in the Vesper archive.

OEIS Terms of Use: https://oeis.org/wiki/The_OEIS_End-User_License_Agreement
Data is used with attribution per OEIS terms. Be polite — the tool
sleeps between requests and identifies itself in the User-Agent.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT (this tool); sequence data copyright OEIS Foundation
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import json
import os
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    from urllib2 import urlopen, Request, URLError, HTTPError  # noqa: F401
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError               # noqa: F401

# ── Curated sequence registry ─────────────────────────────────────────────────
#
# Criteria for inclusion:
#   - Mathematically significant for IV use, prime work, or general reference
#   - Well-established sequences with stable b-files on OEIS
#   - Broadly useful outside of Crowsong
#
# To add a sequence: add an entry here, then run: python sequences.py sync <id>

SEQUENCES = {
    # Primes and prime-adjacent
    "A000040": {
        "name":  "Prime numbers",
        "notes": "The prime numbers. Fundamental.",
        "tags":  ["primes", "reference"],
    },
    "A005384": {
        "name":  "Sophie Germain primes",
        "notes": "Primes p such that 2p+1 is also prime. Useful in cryptography.",
        "tags":  ["primes", "crypto"],
    },
    "A000225": {
        "name":  "Mersenne numbers",
        "notes": "2^n - 1. Includes the Mersenne primes as a subsequence.",
        "tags":  ["primes", "mersenne"],
    },
    "A000668": {
        "name":  "Mersenne primes",
        "notes": "Primes of the form 2^p - 1. Sparse; currently 51 known.",
        "tags":  ["primes", "mersenne"],
    },
    # Constants as digit sequences
    "A000796": {
        "name":  "Decimal expansion of Pi",
        "notes": "3, 1, 4, 1, 5, 9, ... Digits of pi. IV source.",
        "tags":  ["constant", "iv-source"],
    },
    "A001113": {
        "name":  "Decimal expansion of e",
        "notes": "2, 7, 1, 8, 2, 8, ... Digits of Euler's number. IV source.",
        "tags":  ["constant", "iv-source"],
    },
    "A001622": {
        "name":  "Decimal expansion of golden ratio phi",
        "notes": "1, 6, 1, 8, 0, 3, ... Digits of phi. IV source.",
        "tags":  ["constant", "iv-source"],
    },
    "A002193": {
        "name":  "Decimal expansion of sqrt(2)",
        "notes": "1, 4, 1, 4, 2, 1, ... First known irrational. IV source.",
        "tags":  ["constant", "iv-source"],
    },
    "A002117": {
        "name":  "Decimal expansion of Apery's constant zeta(3)",
        "notes": "1, 2, 0, 2, 0, 5, ... Sum of 1/n^3. IV source.",
        "tags":  ["constant", "iv-source"],
    },
    # Foundational sequences
    "A000045": {
        "name":  "Fibonacci numbers",
        "notes": "0, 1, 1, 2, 3, 5, 8, 13, ... Fundamental.",
        "tags":  ["reference"],
    },
    "A000142": {
        "name":  "Factorial numbers n!",
        "notes": "1, 1, 2, 6, 24, 120, ... Grows very fast.",
        "tags":  ["reference"],
    },
    "A000108": {
        "name":  "Catalan numbers",
        "notes": "1, 1, 2, 5, 14, 42, ... Appear everywhere in combinatorics.",
        "tags":  ["reference", "combinatorics"],
    },
    # Number theory
    "A000010": {
        "name":  "Euler's totient function phi(n)",
        "notes": "Count of integers <= n coprime to n. Fundamental in crypto.",
        "tags":  ["number-theory", "crypto"],
    },
    "A001065": {
        "name":  "Sum of proper divisors of n",
        "notes": "Basis for perfect, abundant, and deficient number classification.",
        "tags":  ["number-theory"],
    },
    # Combinatorics
    "A000110": {
        "name":  "Bell numbers",
        "notes": "Number of partitions of a set of n elements.",
        "tags":  ["combinatorics"],
    },
}

OEIS_BASE     = "https://oeis.org"
USER_AGENT    = "Crowsong/1.0 (trey@propertools.be; OEIS mirror for offline use)"
REQUEST_DELAY = 2.0   # seconds between requests — be polite

DEFAULT_DIR = os.path.join("docs", "sequences")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _fetch(url, retries=3):
    """Fetch a URL, returning the response body as a unicode string."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                response = urlopen(req, timeout=30)
                body = response.read()
                return body.decode("utf-8", errors="replace")
            else:
                with urlopen(req, timeout=30) as response:
                    return response.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed to fetch {0}: {1}".format(url, last_err))


# ── OEIS fetch ────────────────────────────────────────────────────────────────

def fetch_metadata(seq_id):
    """
    Fetch sequence metadata from the OEIS JSON API.

    Returns a dict with keys: id, name, description, offset, keyword.
    """
    url = "{0}/search?q=id:{1}&fmt=json".format(OEIS_BASE, seq_id)
    body = _fetch(url)
    data = json.loads(body)

    # OEIS API returns either a dict with a "results" key, or the results
    # list directly. Handle both.
    if isinstance(data, list):
        results = data
    else:
        results = data.get("results") or []

    if not results:
        raise ValueError("sequence not found: {0}".format(seq_id))

    r = results[0]
    return {
        "id":          "A{0:06d}".format(r["number"]),
        "name":        r.get("name", ""),
        "description": " ".join(r.get("comment", [])),
        "offset":      r.get("offset", "0"),
        "keyword":     r.get("keyword", ""),
        "data":        r.get("data", ""),  # first ~20 terms, comma-separated
    }


def fetch_bfile(seq_id):
    """
    Fetch the b-file for a sequence (up to 10000+ terms).

    Returns a list of (index, term) integer tuples.
    """
    url = "{0}/{1}/b{2}.txt".format(
        OEIS_BASE,
        seq_id,
        seq_id[1:].lstrip("0") or "0"   # b000796.txt → b796.txt pattern
    )
    # OEIS b-file naming: A000796 → b000796.txt
    url = "{0}/{1}/b{2}.txt".format(OEIS_BASE, seq_id, seq_id[1:])

    body = _fetch(url)
    terms = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                terms.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
    return terms


# ── File format ───────────────────────────────────────────────────────────────

def make_sequence_file(seq_id, metadata, terms, local_meta=None):
    """
    Render a self-describing plain-text sequence file.

    Args:
        seq_id:     OEIS ID string, e.g. 'A000796'
        metadata:   dict from fetch_metadata()
        terms:      list of (index, term) tuples from fetch_bfile()
        local_meta: optional dict from SEQUENCES registry for extra notes

    Returns:
        File content as a unicode string.
    """
    fetched    = time.strftime("%Y-%m-%d")
    term_count = len(terms)
    values     = [str(t) for _, t in terms]
    body       = ", ".join(values)
    sha256     = hashlib.sha256(body.encode("utf-8")).hexdigest()

    notes = ""
    tags  = ""
    if local_meta:
        notes = local_meta.get("notes", "")
        tags  = ", ".join(local_meta.get("tags", []))

    lines = [
        "# {0} — {1}".format(seq_id, metadata["name"]),
        "#",
        "# OEIS:     https://oeis.org/{0}".format(seq_id),
        "# Fetched:  {0}".format(fetched),
        "# Terms:    {0}".format(term_count),
        "# Offset:   {0}".format(metadata.get("offset", "")),
        "# Keywords: {0}".format(metadata.get("keyword", "")),
        "# SHA256:   {0}".format(sha256),
    ]
    if tags:
        lines.append("# Tags:     {0}".format(tags))
    if notes:
        lines.append("# Notes:    {0}".format(notes))
    lines += [
        "#",
        "# Data copyright OEIS Foundation Inc. — https://oeis.org",
        "# Used with attribution per OEIS End-User License Agreement.",
        "#",
        "",
        body,
        "",
    ]
    return "\n".join(lines)


def parse_sequence_file(path):
    """
    Parse a cached sequence file. Returns dict with digits, sha256, metadata.
    """
    sha256_declared = None
    seq_id          = None
    term_count      = None
    data_line       = None

    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    for line in lines:
        if line.startswith("# ") and " — " in line and seq_id is None:
            seq_id = line.split("# ")[1].split(" — ")[0].strip()
        if "SHA256:" in line:
            sha256_declared = line.split("SHA256:")[-1].strip()
        if "Terms:" in line and ":" in line:
            try:
                term_count = int(line.split("Terms:")[-1].strip())
            except ValueError:
                pass
        if line and not line.startswith("#"):
            data_line = line.strip()

    terms = []
    if data_line:
        for t in data_line.split(","):
            t = t.strip()
            if t:
                try:
                    terms.append(int(t))
                except ValueError:
                    pass

    body = ", ".join(str(t) for t in terms)
    sha256_actual = hashlib.sha256(body.encode("utf-8")).hexdigest()

    return {
        "seq_id":          seq_id,
        "term_count":      term_count,
        "terms":           terms,
        "sha256_declared": sha256_declared,
        "sha256_actual":   sha256_actual,
        "sha256_ok":       (sha256_actual == sha256_declared),
    }


# ── Output directory helpers ──────────────────────────────────────────────────

def seq_path(seq_id, out_dir):
    """Return the expected file path for a sequence ID."""
    return os.path.join(out_dir, "{0}.txt".format(seq_id))


def is_cached(seq_id, out_dir):
    """Return True if a sequence file already exists."""
    return os.path.isfile(seq_path(seq_id, out_dir))


# ── CLI helpers ───────────────────────────────────────────────────────────────

def positive_int(value):
    """argparse type: integer >= 1"""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "OEIS sequence mirror and quick reference tool.\n"
            "Fetches and caches a curated subset of integer sequences\n"
            "for offline use, Vesper archival, and IV generation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python sequences.py list\n"
            "  python sequences.py show A000796\n"
            "  python sequences.py terms A000040 --count 50\n"
            "  python sequences.py sync A000796 A000040\n"
            "  python sequences.py sync --all\n"
            "  python sequences.py verify\n"
        )
    )

    parser.add_argument(
        "--dir",
        default=DEFAULT_DIR,
        metavar="PATH",
        help="directory for cached sequence files (default: docs/sequences/)"
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # list
    subparsers.add_parser(
        "list",
        help="list all sequences in the curated registry"
    )

    # show
    p_show = subparsers.add_parser(
        "show",
        help="show metadata for a sequence (from cache if available)"
    )
    p_show.add_argument("id", help="OEIS sequence ID, e.g. A000796")

    # terms
    p_terms = subparsers.add_parser(
        "terms",
        help="print terms of a cached sequence"
    )
    p_terms.add_argument("id", help="OEIS sequence ID")
    p_terms.add_argument(
        "--count", type=positive_int, default=20,
        help="number of terms to print (default: 20)"
    )

    # sync
    p_sync = subparsers.add_parser(
        "sync",
        help="fetch sequences from OEIS and write to cache"
    )
    p_sync.add_argument(
        "ids", nargs="*",
        help="sequence IDs to sync (default: sync missing only)"
    )
    p_sync.add_argument(
        "--all", dest="sync_all", action="store_true",
        help="sync all sequences in registry, even if cached"
    )
    p_sync.add_argument(
        "--force", action="store_true",
        help="re-fetch even if already cached"
    )

    # verify
    p_verify = subparsers.add_parser(
        "verify",
        help="verify SHA256 of cached sequence files"
    )
    p_verify.add_argument(
        "ids", nargs="*",
        help="sequence IDs to verify (default: all cached)"
    )

    return parser


# ── Command implementations ───────────────────────────────────────────────────

def cmd_list():
    fmt = "{:<10}  {:<50}  {}"
    print(fmt.format("ID", "Name", "Tags"))
    print("-" * 80)
    for seq_id, meta in sorted(SEQUENCES.items()):
        tags = ", ".join(meta.get("tags", []))
        print(fmt.format(seq_id, meta["name"][:50], tags))
    print()
    print("{0} sequences in registry.".format(len(SEQUENCES)))


def cmd_show(seq_id, out_dir):
    seq_id = seq_id.upper()
    path   = seq_path(seq_id, out_dir)

    local = SEQUENCES.get(seq_id, {})
    print("ID:     {0}".format(seq_id))
    print("URL:    https://oeis.org/{0}".format(seq_id))

    if local:
        print("Name:   {0}".format(local.get("name", "")))
        print("Notes:  {0}".format(local.get("notes", "")))
        print("Tags:   {0}".format(", ".join(local.get("tags", []))))

    if is_cached(seq_id, out_dir):
        parsed = parse_sequence_file(path)
        print("Cached: yes ({0} terms)".format(parsed["term_count"] or "?"))
        print("SHA256: {0}".format(parsed["sha256_actual"]))
        print("Valid:  {0}".format("yes" if parsed["sha256_ok"] else "NO — mismatch"))
        if parsed["terms"]:
            preview = ", ".join(str(t) for t in parsed["terms"][:10])
            print("Terms:  {0} ...".format(preview))
    else:
        print("Cached: no (run: python sequences.py sync {0})".format(seq_id))


def cmd_terms(seq_id, count, out_dir):
    seq_id = seq_id.upper()
    path   = seq_path(seq_id, out_dir)

    if not is_cached(seq_id, out_dir):
        print(
            "Error: {0} not cached. Run: python sequences.py sync {0}".format(seq_id),
            file=sys.stderr)
        return 1

    parsed = parse_sequence_file(path)
    terms  = parsed["terms"][:count]
    print("{0} — first {1} terms:".format(seq_id, len(terms)))
    print()
    print(", ".join(str(t) for t in terms))
    return 0


def cmd_sync(ids, out_dir, force=False, sync_all=False):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if sync_all or not ids:
        targets = list(SEQUENCES.keys())
    else:
        targets = [i.upper() for i in ids]

    errors = 0
    for i, seq_id in enumerate(sorted(targets)):
        path = seq_path(seq_id, out_dir)

        if is_cached(seq_id, out_dir) and not force and not sync_all:
            print("  SKIP  {0} (cached; use --force to re-fetch)".format(seq_id))
            continue

        if sync_all and is_cached(seq_id, out_dir) and not force:
            print("  SKIP  {0} (cached)".format(seq_id))
            continue

        print("  SYNC  {0} ...".format(seq_id), end="")
        sys.stdout.flush()

        try:
            metadata = fetch_metadata(seq_id)
            time.sleep(REQUEST_DELAY)
            terms    = fetch_bfile(seq_id)
            time.sleep(REQUEST_DELAY)

            local_meta = SEQUENCES.get(seq_id)
            content    = make_sequence_file(seq_id, metadata, terms, local_meta)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            print(" {0} terms".format(len(terms)))

        except (IOError, ValueError) as err:
            print(" FAIL: {0}".format(err))
            errors += 1

    return 0 if errors == 0 else 1


def cmd_verify(ids, out_dir):
    if ids:
        targets = [i.upper() for i in ids]
    else:
        # all cached
        targets = sorted(
            f[:-4] for f in os.listdir(out_dir)
            if f.endswith(".txt") and f.startswith("A")
        ) if os.path.isdir(out_dir) else []

    if not targets:
        print("No cached sequences to verify.")
        return 0

    passed = 0
    failed = 0
    for seq_id in targets:
        path = seq_path(seq_id, out_dir)
        if not os.path.isfile(path):
            print("  MISS  {0} (not cached)".format(seq_id))
            failed += 1
            continue

        parsed = parse_sequence_file(path)
        if parsed["sha256_ok"]:
            print("  PASS  {0} ({1} terms)".format(
                seq_id, parsed["term_count"] or len(parsed["terms"])))
            passed += 1
        else:
            print("  FAIL  {0} — SHA256 mismatch".format(seq_id))
            print("        declared: {0}".format(parsed["sha256_declared"]))
            print("        actual:   {0}".format(parsed["sha256_actual"]))
            failed += 1

    print()
    print("Results: {0} passed, {1} failed".format(passed, failed))
    return 0 if failed == 0 else 1


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args   = parser.parse_args()
    out_dir = args.dir

    if args.command == "list":
        cmd_list()
        return 0

    if args.command == "show":
        cmd_show(args.id, out_dir)
        return 0

    if args.command == "terms":
        return cmd_terms(args.id, args.count, out_dir)

    if args.command == "sync":
        return cmd_sync(
            args.ids, out_dir,
            force=args.force,
            sync_all=args.sync_all)

    if args.command == "verify":
        return cmd_verify(args.ids, out_dir)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
