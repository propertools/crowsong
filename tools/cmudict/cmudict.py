#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cmudict.py — CMU Pronouncing Dictionary mirror and syllable tool

Fetches, caches, and serves the CMU Pronouncing Dictionary for offline
use, syllable counting, and haiku corpus bin generation.

The CMU Pronouncing Dictionary contains ~134,000 English words with
their phonemic transcriptions. Syllable count is exact for any word
in the dictionary: count the vowel phonemes (those ending in a digit).

Usage:
    python cmudict.py fetch              # download and cache
    python cmudict.py verify             # verify SHA256 of cached file
    python cmudict.py syllables <word>   # syllable count for a word
    python cmudict.py phones <word>      # full phoneme list for a word
    python cmudict.py bin <n>            # all words with n syllables
    python cmudict.py bins               # summary: count per bin
    python cmudict.py export             # write bins.json for haiku tool

Examples:
    python cmudict.py fetch
    python cmudict.py verify
    python cmudict.py syllables entropy      # 3
    python cmudict.py syllables signal       # 2
    python cmudict.py phones entropy         # EH1 N T R AH0 P IY0
    python cmudict.py bin 1 | head -20
    python cmudict.py bin 5 | wc -l
    python cmudict.py bins
    python cmudict.py export
    python cmudict.py export --output docs/cmudict/bins.json

The cached file uses the archivist header format (SHA256 + metadata),
consistent with the rest of the Crowsong corpus tools.

Syllable counting:
    Each vowel phoneme ends in a digit (0=unstressed, 1=primary,
    2=secondary stress). Syllable count = number of phonemes ending
    in a digit. This is exact for any in-dictionary word.

Out-of-dictionary words:
    The tool returns None for words not in the dictionary. The haiku
    tool skips out-of-dictionary words when building syllable bins.
    No heuristic fallback is used — only confirmed syllable counts.

Compatibility: Python 2.7+ / 3.x
No external dependencies.
Author: Proper Tools SRL
License: MIT (this tool); CMU Pronouncing Dictionary is public domain.
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import json
import os
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    from urllib2 import urlopen, Request, URLError, HTTPError  # noqa
    text_type = unicode  # noqa: F821
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError               # noqa
    text_type = str

# ── Source URLs ───────────────────────────────────────────────────────────────
#
# We pin the GitHub raw URL to the master branch of the canonical
# cmusphinx/cmudict repository. The SHA256 declared in the cached file
# pins the specific content fetched; re-fetching and getting a different
# SHA256 indicates the upstream file has changed.

CMUDICT_PRIMARY = (
    "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
)
CMUDICT_SECONDARY = (
    "http://svn.code.sf.net/p/cmusphinx/code/trunk/cmudict/cmudict-0.7b"
)

USER_AGENT    = ("Crowsong/1.0 (trey@propertools.be; "
                 "CMU dict mirror for haiku corpus)")
REQUEST_DELAY = 2.0
DEFAULT_DIR   = os.path.join("docs", "cmudict")
DEFAULT_FILE  = "cmudict.dict"
DEFAULT_BINS  = "bins.json"


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_url(url, retries=3):
    """Fetch a URL, returning body as unicode string."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                r = urlopen(req, timeout=60)
                body = r.read()
                return body.decode("utf-8", errors="replace")
            else:
                with urlopen(req, timeout=60) as r:
                    return r.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed to fetch {0}: {1}".format(url, last_err))


# ── File format ───────────────────────────────────────────────────────────────

def _make_header(body, source_url):
    """Build an archivist-style self-describing header."""
    fetched    = time.strftime("%Y-%m-%d")
    entry_count = sum(
        1 for line in body.splitlines()
        if line and not line.startswith(";") and not line.startswith("#")
    )
    sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()

    lines = [
        "# CMU Pronouncing Dictionary",
        "#",
        "# Source:   {0}".format(source_url),
        "# Fetched:  {0}".format(fetched),
        "# Entries:  {0:,}".format(entry_count),
        "# SHA256:   {0}".format(sha256),
        "# License:  Public domain (Carnegie Mellon University)",
        "#",
        "# Format: WORD  PH1 PH2 ... PHn",
        "# Vowel phonemes end in a digit (0=unstressed, 1=primary, 2=secondary).",
        "# Syllable count = number of phonemes ending in a digit.",
        "#",
        "# Suitable for Vesper archival and offline haiku corpus generation.",
        "# Tool: tools/cmudict/cmudict.py (Proper Tools SRL)",
        "#",
    ]
    return "\n".join(lines)


def _sha256_of_body(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# ── Core parser ───────────────────────────────────────────────────────────────

def _parse_dict(content):
    """
    Parse CMU dict content into a dict: word -> list of phonemes.

    Handles both the raw upstream format and the archivist-wrapped format.
    Comment lines (starting with ; or #) are skipped.
    Alternate pronunciations (WORD(2), WORD(3)) are stored under the
    base word key as additional phoneme lists.

    Returns:
        dict mapping lowercase word -> list of phoneme lists
        e.g. {"entropy": [["EH1","N","T","R","AH0","P","IY0"]]}
    """
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        word_raw  = parts[0]
        phones    = parts[1:]

        # Strip alternate pronunciation markers: WORD(2) -> WORD
        if "(" in word_raw:
            word_raw = word_raw[:word_raw.index("(")]

        word = word_raw.lower()
        if word not in result:
            result[word] = []
        result[word].append(phones)

    return result


def _syllable_count(phones):
    """
    Count syllables in a phoneme list.
    Syllable count = number of phonemes ending in a digit (vowel nuclei).
    """
    return sum(1 for p in phones if p[-1].isdigit())


# ── Dictionary access ─────────────────────────────────────────────────────────

def load_dict(dict_path):
    """
    Load the cached CMU dictionary from disk.

    Returns:
        dict: word (lowercase) -> list of phoneme lists
    """
    if not os.path.isfile(dict_path):
        raise IOError(
            "CMU dict not cached. Run: python cmudict.py fetch")
    with io.open(dict_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _parse_dict(content)


def get_syllables(cmudict, word):
    """
    Return syllable count for word (primary pronunciation), or None.

    Args:
        cmudict: dict from load_dict()
        word:    word string (case-insensitive)

    Returns:
        int syllable count, or None if word not in dictionary.
    """
    entries = cmudict.get(word.lower())
    if not entries:
        return None
    return _syllable_count(entries[0])


def get_phones(cmudict, word):
    """
    Return phoneme list for word (primary pronunciation), or None.

    Args:
        cmudict: dict from load_dict()
        word:    word string (case-insensitive)

    Returns:
        list of phoneme strings, or None if word not in dictionary.
    """
    entries = cmudict.get(word.lower())
    if not entries:
        return None
    return entries[0]


def get_all_pronunciations(cmudict, word):
    """
    Return all known pronunciations for word.

    Args:
        cmudict: dict from load_dict()
        word:    word string (case-insensitive)

    Returns:
        list of phoneme lists (may be empty if word not in dictionary).
    """
    return cmudict.get(word.lower(), [])


def build_bins(cmudict):
    """
    Group all words by syllable count.

    Uses primary pronunciation only. Words with zero syllables
    (e.g. abbreviations without vowels) are excluded.

    Returns:
        dict: syllable_count (int) -> sorted list of words (lowercase)
    """
    bins = {}
    for word, pronunciations in cmudict.items():
        if not pronunciations:
            continue
        n = _syllable_count(pronunciations[0])
        if n < 1:
            continue
        if n not in bins:
            bins[n] = []
        bins[n].append(word)
    for n in bins:
        bins[n].sort()
    return bins


# ── Path helpers ──────────────────────────────────────────────────────────────

def _dict_path(out_dir):
    return os.path.join(out_dir, DEFAULT_FILE)

def _bins_path(out_dir):
    return os.path.join(out_dir, DEFAULT_BINS)

def _is_cached(out_dir):
    return os.path.isfile(_dict_path(out_dir))


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_fetch(out_dir, force=False):
    """Download and cache the CMU Pronouncing Dictionary."""
    path = _dict_path(out_dir)

    if _is_cached(out_dir) and not force:
        print("Already cached: {0}".format(path))
        print("Use --force to re-fetch.")
        return 0

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    source_url = None
    body       = None
    errors     = []

    for url in (CMUDICT_PRIMARY, CMUDICT_SECONDARY):
        print("Fetching {0} ...".format(url))
        try:
            body = _fetch_url(url)
            # Sanity check: should have thousands of lines
            lines = [l for l in body.splitlines()
                     if l and not l.startswith(";")]
            if len(lines) < 1000:
                raise ValueError(
                    "suspiciously short ({0} non-comment lines)".format(
                        len(lines)))
            source_url = url
            break
        except (IOError, ValueError) as e:
            errors.append("{0}: {1}".format(url, e))
            print("  FAIL: {0}".format(e))
            time.sleep(REQUEST_DELAY)

    if body is None:
        print("Error: could not fetch CMU dict from any source.",
              file=sys.stderr)
        for e in errors:
            print("  {0}".format(e), file=sys.stderr)
        return 1

    header  = _make_header(body, source_url)
    content = header + "\n\n" + body + "\n"

    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content)

    sha256 = _sha256_of_body(body)
    print("Cached: {0}".format(path))
    print("SHA256: {0}".format(sha256))
    print("Size:   {0:,} bytes".format(len(content)))

    # Count entries
    cmudict = _parse_dict(body)
    print("Words:  {0:,} unique entries".format(len(cmudict)))
    return 0


def cmd_verify(out_dir):
    """Verify SHA256 of cached CMU dict file."""
    path = _dict_path(out_dir)
    if not os.path.isfile(path):
        print("Error: not cached. Run: python cmudict.py fetch",
              file=sys.stderr)
        return 1

    with io.open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract declared SHA256 from header
    sha256_declared = None
    body_lines      = []
    in_header       = True

    for line in content.splitlines():
        if in_header:
            if line.startswith("# SHA256:"):
                sha256_declared = line.split("SHA256:")[-1].strip()
            if not line.startswith("#"):
                in_header = False
        if not in_header and line.strip():
            body_lines.append(line)

    body = "\n".join(body_lines)
    sha256_actual = _sha256_of_body(body)

    print("File:     {0}".format(path))
    print("SHA256:   {0}".format(sha256_actual))

    if sha256_declared:
        ok = (sha256_actual == sha256_declared)
        print("Declared: {0}".format(sha256_declared))
        print("Match:    {0}".format("YES" if ok else "NO — MISMATCH"))
        if not ok:
            return 1
    else:
        print("Declared: (none — old format, no verification possible)")

    # Parse and count
    cmudict = _parse_dict(body)
    print("Words:    {0:,} unique entries".format(len(cmudict)))
    print("Verification: PASS")
    return 0


def cmd_syllables(word, out_dir):
    """Print syllable count for a word."""
    cmudict = load_dict(_dict_path(out_dir))
    n = get_syllables(cmudict, word)
    if n is None:
        print("Not in dictionary: {0}".format(word), file=sys.stderr)
        return 1
    print("{0}  →  {1} syllable{2}".format(
        word.lower(), n, "" if n == 1 else "s"))
    return 0


def cmd_phones(word, out_dir):
    """Print phoneme list for a word."""
    cmudict = load_dict(_dict_path(out_dir))
    all_pron = get_all_pronunciations(cmudict, word)
    if not all_pron:
        print("Not in dictionary: {0}".format(word), file=sys.stderr)
        return 1
    for i, phones in enumerate(all_pron):
        n   = _syllable_count(phones)
        tag = "" if i == 0 else "  (alternate {0})".format(i + 1)
        print("{0}{1}  →  {2}  ({3} syllable{4})".format(
            word.lower(), tag,
            " ".join(phones),
            n, "" if n == 1 else "s"))
    return 0


def cmd_bin(n, out_dir):
    """Print all words with exactly n syllables, one per line."""
    cmudict = load_dict(_dict_path(out_dir))
    bins    = build_bins(cmudict)
    words   = bins.get(n, [])
    if not words:
        print("No words with {0} syllable{1}.".format(
            n, "" if n == 1 else "s"), file=sys.stderr)
        return 1
    for word in words:
        sys.stdout.write(word + "\n")
    print("", file=sys.stderr)
    print("{0:,} words with {1} syllable{2}.".format(
        len(words), n, "" if n == 1 else "s"), file=sys.stderr)
    return 0


def cmd_bins(out_dir):
    """Print summary of word counts per syllable bin."""
    cmudict = load_dict(_dict_path(out_dir))
    bins    = build_bins(cmudict)

    total = sum(len(v) for v in bins.values())
    print("{0:,} unique words across {1} syllable bins:\n".format(
        total, len(bins)))

    fmt = "  {syl:>3} syllable{pl}  {count:>7,} words  {bar}"
    for n in sorted(bins.keys()):
        count  = len(bins[n])
        bar_w  = 30
        filled = int(min(1.0, count / 10000) * bar_w)
        bar    = "█" * filled + "░" * (bar_w - filled)
        print(fmt.format(
            syl=n,
            pl="" if n == 1 else "s",
            count=count,
            bar=bar))

    print()
    print("  Note: only primary pronunciations counted.")
    print("  Words with 0 syllables (abbreviations, etc.) excluded.")
    return 0


def cmd_export(out_dir, output_path=None, min_syllables=1, max_syllables=9):
    """
    Export syllable bins as JSON for use by the haiku tool.

    Output format:
    {
      "1": ["a", "by", "cry", ...],
      "2": ["signal", "prime", ...],
      ...
      "_meta": {
        "source": "cmudict.dict",
        "fetched": "YYYY-MM-DD",
        "total_words": N,
        "min_syllables": 1,
        "max_syllables": 9
      }
    }

    Keys are string representations of syllable counts.
    Words are lowercase, alphabetically sorted within each bin.
    """
    if output_path is None:
        output_path = _bins_path(out_dir)

    cmudict = load_dict(_dict_path(out_dir))
    bins    = build_bins(cmudict)

    # Filter to requested range
    filtered = {
        str(n): words
        for n, words in bins.items()
        if min_syllables <= n <= max_syllables
    }

    total = sum(len(v) for v in filtered.values())
    filtered["_meta"] = {
        "source":        DEFAULT_FILE,
        "generated":     time.strftime("%Y-%m-%d"),
        "total_words":   total,
        "min_syllables": min_syllables,
        "max_syllables": max_syllables,
        "note": (
            "Syllable counts from CMU Pronouncing Dictionary "
            "(primary pronunciation only). "
            "Public domain. Generated by tools/cmudict/cmudict.py."
        ),
    }

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with io.open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False,
                  indent=2, sort_keys=True)
        f.write("\n")

    print("Exported: {0}".format(output_path))
    print("Words:    {0:,} across {1} bins".format(
        total, len(filtered) - 1))  # -1 for _meta
    for n in sorted(bins.keys()):
        if min_syllables <= n <= max_syllables:
            print("  {0} syllable{1}: {2:,} words".format(
                n, "" if n == 1 else "s", len(bins[n])))
    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def positive_int(value):
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def build_parser():
    p = argparse.ArgumentParser(
        prog="cmudict",
        description=(
            "CMU Pronouncing Dictionary mirror and syllable tool.\n"
            "Fetches, caches, and serves syllable counts for English words.\n"
            "Used by the Crowsong haiku generator for syllable bin lookup.\n"
            "\n"
            "The CMU Pronouncing Dictionary is public domain.\n"
            "~134,000 English words with exact syllable counts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cmudict.py fetch\n"
            "  python cmudict.py verify\n"
            "  python cmudict.py syllables entropy\n"
            "  python cmudict.py phones entropy\n"
            "  python cmudict.py bin 2 | head -20\n"
            "  python cmudict.py bins\n"
            "  python cmudict.py export\n"
            "\n"
            "Quick start:\n"
            "  python cmudict.py fetch && python cmudict.py export\n"
            "  # Then use docs/cmudict/bins.json in haiku.py\n"
        )
    )

    p.add_argument(
        "--dir", default=DEFAULT_DIR, metavar="PATH",
        help="directory for cached files (default: docs/cmudict/)")

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # fetch
    pf = sub.add_parser("fetch",
        help="download and cache the CMU Pronouncing Dictionary")
    pf.add_argument("--force", action="store_true",
        help="re-fetch even if already cached")

    # verify
    sub.add_parser("verify",
        help="verify SHA256 of cached file")

    # syllables
    ps = sub.add_parser("syllables",
        help="print syllable count for a word")
    ps.add_argument("word", help="word to look up (case-insensitive)")

    # phones
    ph = sub.add_parser("phones",
        help="print phoneme transcription for a word")
    ph.add_argument("word", help="word to look up (case-insensitive)")

    # bin
    pb = sub.add_parser("bin",
        help="list all words with exactly n syllables")
    pb.add_argument("n", type=positive_int,
        help="syllable count")

    # bins
    sub.add_parser("bins",
        help="print word counts per syllable bin")

    # export
    pe = sub.add_parser("export",
        help="export syllable bins as JSON for haiku tool")
    pe.add_argument(
        "--output", "-o", default=None, metavar="FILE",
        help="output path (default: docs/cmudict/bins.json)")
    pe.add_argument(
        "--min-syllables", type=positive_int, default=1, metavar="N",
        help="minimum syllable count to include (default: 1)")
    pe.add_argument(
        "--max-syllables", type=positive_int, default=9, metavar="N",
        help="maximum syllable count to include (default: 9)")

    return p


def main():
    parser  = build_parser()
    args    = parser.parse_args()
    out_dir = args.dir

    try:
        if args.command == "fetch":
            return cmd_fetch(out_dir, force=args.force)
        if args.command == "verify":
            return cmd_verify(out_dir)
        if args.command == "syllables":
            return cmd_syllables(args.word, out_dir)
        if args.command == "phones":
            return cmd_phones(args.word, out_dir)
        if args.command == "bin":
            return cmd_bin(args.n, out_dir)
        if args.command == "bins":
            return cmd_bins(out_dir)
        if args.command == "export":
            return cmd_export(
                out_dir,
                output_path=args.output,
                min_syllables=args.min_syllables,
                max_syllables=args.max_syllables)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
