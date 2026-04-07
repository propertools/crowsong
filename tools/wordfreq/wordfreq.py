#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wordfreq.py — English word frequency corpus mirror

Fetches, caches, and serves word frequency data from three public
corpora, with a filter subcommand for pruning the CMU Pronouncing
Dictionary syllable bins to natural-language vocabulary.

Sources:
    coca      COCA 60k word frequency list (BYU / Mark Davies)
              ~60,000 words, frequency per million, POS-tagged
              Free download; academic use.

    subtlex   SUBTLEX-US (Ghent University / Brysbaert & New 2009)
              ~74,000 words from film/TV subtitles
              Best proxy for common spoken English recognition.
              Public domain for research use.

    ngrams    Google Books Ngram 1-grams, 2019 English corpus
              Aggregated total frequency per word across all years.
              26 gzipped TSV files, fetched and aggregated.
              WARNING: large download (~5GB compressed total).
              Use --source coca or --source subtlex for most purposes.

Usage:
    python wordfreq.py fetch      [--source SOURCE] [--dir DIR]
    python wordfreq.py verify     [--source SOURCE] [--dir DIR]
    python wordfreq.py lookup     <word> [--source SOURCE] [--dir DIR]
    python wordfreq.py rank       <word> [--source SOURCE] [--dir DIR]
    python wordfreq.py top        <n>    [--source SOURCE] [--dir DIR]
    python wordfreq.py export     [--source SOURCE] [--format tsv|json] [--dir DIR]
    python wordfreq.py export-pos [--source SOURCE] [--output FILE] [--dir DIR]
    python wordfreq.py filter     --bins FILE [--source SOURCE]
                                  [--min-freq N] [--min-rank N] [--dir DIR]

    SOURCE: coca | subtlex | ngrams | all  (default: coca,subtlex)

Examples:
    # Fetch COCA and SUBTLEX (recommended default)
    python wordfreq.py fetch

    # Fetch all sources (warning: ngrams is ~5GB)
    python wordfreq.py fetch --source all

    # Look up a word across all cached sources
    python wordfreq.py lookup entropy
    python wordfreq.py lookup signal

    # Top 100 words by SUBTLEX frequency
    python wordfreq.py top 100 --source subtlex

    # Filter cmudict bins to SUBTLEX top 30,000 words
    python wordfreq.py filter --bins docs/cmudict/bins.json \\
        --source subtlex --min-rank 30000 \\
        --output docs/cmudict/bins-common.json

    # Export POS index for haiku_grammar.py (requires COCA)
    python wordfreq.py export-pos
    python wordfreq.py export-pos --output docs/wordfreq/pos-index.json

    # Export COCA as TSV
    python wordfreq.py export --source coca --format tsv

The filter subcommand produces a filtered bins.json for use by
haiku_twist.py, containing only words that appear in the top N
of the frequency corpus. This makes haiku output read as natural
English rather than drawing from obscure technical vocabulary.

The export-pos subcommand produces pos-index.json: a mapping of
word -> [POS tags] derived from COCA's POS annotations. This is
consumed by haiku_grammar.py to build POS-indexed syllable bins
for grammatically coherent haiku generation.

Compatibility: Python 2.7+ / 3.x
No external dependencies (ngrams aggregation uses gzip + csv from stdlib).
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    from urllib2 import urlopen, Request, URLError  # noqa
    text_type = unicode  # noqa: F821
    range     = xrange   # noqa: F821
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
    text_type = str

# ── Source definitions ────────────────────────────────────────────────────────

SOURCES = {
    "coca": {
        "name":    "COCA 60k Word Frequency List",
        "credit":  "Mark Davies, Brigham Young University",
        "license": "Free for academic/research use",
        "url":     "https://www.wordfrequency.info/files/entries/wordFrequency.xlsx",
        # The free TSV mirror (same data, no Excel required)
        "url_tsv": (
            "https://www.wordfrequency.info/files/entries/wordFrequency.txt"
        ),
        "filename": "coca-60k.tsv",
        "columns":  ["rank", "word", "pos", "frequency", "per_million"],
        "word_col": "word",
        "freq_col": "per_million",
        "rank_col": "rank",
        "note": (
            "60,000 most frequent English words. Balanced corpus: "
            "spoken, fiction, magazines, newspapers, academic. "
            "Frequency given as occurrences per million words."
        ),
    },
    "subtlex": {
        "name":    "SUBTLEX-US",
        "credit":  "Brysbaert & New (2009), Ghent University",
        "license": "Free for research use",
        "url": (
            "https://www.ugent.be/pp/experimentele-psychologie/en/research/"
            "documents/subtlexus/subtlexus2.zip"
        ),
        # Direct TSV mirror at multiple locations; use the most stable
        "url_tsv": (
            "https://raw.githubusercontent.com/psychbruce/ChineseWordFreq/"
            "main/data/SUBTLEX-US.txt"
        ),
        "filename": "subtlex-us.tsv",
        "columns":  ["word", "freq_count", "cd_count", "freq_per_million",
                     "cd_per_movie", "log_freq", "log_cd",
                     "freq_subtitle", "freq_internet"],
        "word_col": "word",
        "freq_col": "freq_per_million",
        "rank_col": None,   # rank computed from frequency
        "note": (
            "~74,000 words from 8,388 US film and TV subtitles "
            "(51 million words). Best proxy for words that fluent "
            "speakers recognise instantly. Ideal for natural-language "
            "haiku corpus filtering."
        ),
    },
    "ngrams": {
        "name":    "Google Books Ngram 1-grams (2019 English corpus)",
        "credit":  "Google Books / Michel et al. (2011)",
        "license": "CC BY 3.0",
        "url_pattern": (
            "http://storage.googleapis.com/books/ngrams/books/"
            "20200217/eng/1-gram-{letter}.gz"
        ),
        "letters":  list("abcdefghijklmnopqrstuvwxyz") + ["other"],
        "filename": "ngrams-1gram-aggregated.tsv.gz",
        "columns":  ["word", "total_count", "book_count"],
        "word_col": "word",
        "freq_col": "total_count",
        "rank_col": None,
        "note": (
            "Aggregated total frequency per word across all years "
            "in the 2019 Google Books English corpus. "
            "WARNING: ~5GB compressed download. "
            "Use coca or subtlex for most purposes."
        ),
    },
}

DEFAULT_SOURCES = ["coca", "subtlex"]
DEFAULT_DIR     = os.path.join("docs", "wordfreq")
USER_AGENT      = "Crowsong-wordfreq/1.0 (trey@propertools.be)"
REQUEST_DELAY   = 2.0


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_url(url, retries=3, timeout=120):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                r = urlopen(req, timeout=timeout)
                return r.read()
            else:
                with urlopen(req, timeout=timeout) as r:
                    return r.read()
        except (URLError, IOError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed to fetch {0}: {1}".format(url, last_err))


# ── Archivist header ──────────────────────────────────────────────────────────

def _make_header(source_key, url, row_count, sha256):
    src = SOURCES[source_key]
    lines = [
        "# {0}".format(src["name"]),
        "#",
        "# Source:   {0}".format(url),
        "# Credit:   {0}".format(src["credit"]),
        "# License:  {0}".format(src["license"]),
        "# Fetched:  {0}".format(time.strftime("%Y-%m-%d")),
        "# Rows:     {0:,}".format(row_count),
        "# SHA256:   {0}".format(sha256),
        "#",
        "# {0}".format(src["note"]),
        "#",
        "# Tool: tools/wordfreq/wordfreq.py (Proper Tools SRL)",
        "#",
    ]
    return "\n".join(lines)


# ── Cache paths ───────────────────────────────────────────────────────────────

def _cache_path(source_key, out_dir):
    return os.path.join(out_dir, SOURCES[source_key]["filename"])


def _is_cached(source_key, out_dir):
    return os.path.isfile(_cache_path(source_key, out_dir))


# ── Loading ───────────────────────────────────────────────────────────────────

def _load_tsv(path, word_col, freq_col, rank_col=None):
    """
    Load a cached TSV (with archivist header) into a list of dicts.
    Returns list of {word, frequency, rank} dicts, sorted by frequency desc.
    """
    rows = []
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        header_done = False
        col_names   = None
        for line in f:
            line = line.rstrip("\n\r")
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            if not header_done:
                col_names   = line.split("\t")
                header_done = True
                continue
            if col_names is None:
                continue
            parts = line.split("\t")
            if len(parts) < len(col_names):
                continue
            row = dict(zip(col_names, parts))
            word = row.get(word_col, "").strip().lower()
            if not word:
                continue
            try:
                freq = float(row.get(freq_col, 0) or 0)
            except ValueError:
                freq = 0.0
            rank = None
            if rank_col and rank_col in row:
                try:
                    rank = int(row[rank_col])
                except ValueError:
                    rank = None
            rows.append({"word": word, "frequency": freq, "rank": rank})

    # Sort by frequency descending; assign ranks if not present
    rows.sort(key=lambda r: r["frequency"], reverse=True)
    for i, r in enumerate(rows):
        if r["rank"] is None:
            r["rank"] = i + 1

    return rows


def load_source(source_key, out_dir):
    """
    Load a cached frequency corpus. Returns list of {word, frequency, rank}.
    Raises IOError if not cached.
    """
    path = _cache_path(source_key, out_dir)
    if not os.path.isfile(path):
        raise IOError(
            "{0} not cached. Run: python wordfreq.py fetch --source {1}".format(
                source_key, source_key))
    src      = SOURCES[source_key]
    word_col = src["word_col"]
    freq_col = src["freq_col"]
    rank_col = src["rank_col"]

    if path.endswith(".gz"):
        # ngrams: read gzipped TSV
        rows = []
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.rstrip().split("\t")
                if len(parts) < 2:
                    continue
                word = parts[0].strip().lower()
                try:
                    freq = float(parts[1])
                except (ValueError, IndexError):
                    freq = 0.0
                rows.append({"word": word, "frequency": freq, "rank": None})
        rows.sort(key=lambda r: r["frequency"], reverse=True)
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    return _load_tsv(path, word_col, freq_col, rank_col)


def word_index(rows):
    """Build word → row dict for fast lookup."""
    return {r["word"]: r for r in rows}


# ── COCA fetch ────────────────────────────────────────────────────────────────

def fetch_coca(out_dir, force=False):
    src  = SOURCES["coca"]
    path = _cache_path("coca", out_dir)

    if _is_cached("coca", out_dir) and not force:
        print("Already cached: {0}".format(path))
        return 0

    url = src["url_tsv"]
    print("Fetching COCA from {0} ...".format(url))
    try:
        data = _fetch_url(url)
    except IOError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        print("COCA requires free registration at wordfrequency.info", file=sys.stderr)
        print("Download manually and place at: {0}".format(path), file=sys.stderr)
        return 1

    # Decode and count rows
    text = data.decode("utf-8", errors="replace")
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    row_count = max(0, len(lines) - 1)  # subtract header
    sha256 = hashlib.sha256(data).hexdigest()
    header = _make_header("coca", url, row_count, sha256)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with io.open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")

    print("Cached: {0} ({1:,} rows)".format(path, row_count))
    print("SHA256: {0}".format(sha256))
    return 0


# ── SUBTLEX fetch ─────────────────────────────────────────────────────────────

def fetch_subtlex(out_dir, force=False):
    src  = SOURCES["subtlex"]
    path = _cache_path("subtlex", out_dir)

    if _is_cached("subtlex", out_dir) and not force:
        print("Already cached: {0}".format(path))
        return 0

    url = src["url_tsv"]
    print("Fetching SUBTLEX-US from {0} ...".format(url))
    try:
        data = _fetch_url(url)
    except IOError as e:
        print("Error fetching SUBTLEX-US: {0}".format(e), file=sys.stderr)
        print(
            "Try fetching manually from:\n"
            "  https://www.ugent.be/pp/experimentele-psychologie/en/research/"
            "documents/subtlexus\n"
            "and place the TSV at: {0}".format(path),
            file=sys.stderr)
        return 1

    text = data.decode("utf-8", errors="replace")
    lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
    row_count = max(0, len(lines) - 1)
    sha256 = hashlib.sha256(data).hexdigest()
    header = _make_header("subtlex", url, row_count, sha256)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with io.open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")

    print("Cached: {0} ({1:,} rows)".format(path, row_count))
    print("SHA256: {0}".format(sha256))
    return 0


# ── Ngrams fetch ──────────────────────────────────────────────────────────────

def fetch_ngrams(out_dir, force=False):
    src     = SOURCES["ngrams"]
    path    = _cache_path("ngrams", out_dir)
    letters = src["letters"]

    if _is_cached("ngrams", out_dir) and not force:
        print("Already cached: {0}".format(path))
        return 0

    print("WARNING: Google Books Ngrams is a large download (~5GB compressed).")
    print("This will take a long time. Use --source coca or --source subtlex")
    print("for most purposes. Proceeding in 5 seconds — Ctrl-C to abort.")
    time.sleep(5)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # Aggregate word frequencies across all letter files
    aggregated = {}
    for letter in letters:
        url = src["url_pattern"].format(letter=letter)
        print("Fetching {0} ...".format(url))
        try:
            data = _fetch_url(url, timeout=300)
        except IOError as e:
            print("  WARN: {0}".format(e), file=sys.stderr)
            time.sleep(REQUEST_DELAY)
            continue

        # Each file is gzipped TSV: ngram TAB year TAB match_count TAB volume_count
        try:
            with gzip.open(io.BytesIO(data), "rt",
                           encoding="utf-8", errors="replace") as gz:
                for line in gz:
                    parts = line.rstrip().split("\t")
                    if len(parts) < 3:
                        continue
                    word = parts[0].strip().lower()
                    # Skip ngrams containing spaces (phrases, not words)
                    if " " in word:
                        continue
                    # Skip POS-tagged variants (word_NOUN etc.)
                    if "_" in word:
                        continue
                    try:
                        count = int(parts[2])
                    except ValueError:
                        continue
                    aggregated[word] = aggregated.get(word, 0) + count
        except Exception as e:
            print("  WARN: decompression error for {0}: {1}".format(
                letter, e), file=sys.stderr)

        time.sleep(REQUEST_DELAY)
        print("  Done ({0:,} unique words so far)".format(len(aggregated)))

    # Write aggregated TSV (gzipped)
    print("Writing aggregated output ({0:,} words) ...".format(len(aggregated)))
    sorted_words = sorted(aggregated.items(), key=lambda x: x[1], reverse=True)

    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("# Google Books Ngram 1-grams (2019 English corpus)\n")
        f.write("# Aggregated total frequency per word across all years\n")
        f.write("# Generated: {0}\n".format(time.strftime("%Y-%m-%d")))
        f.write("# Words: {0:,}\n".format(len(sorted_words)))
        f.write("# License: CC BY 3.0 (Google Books)\n#\n")
        f.write("word\ttotal_count\n")
        for word, count in sorted_words:
            f.write("{0}\t{1}\n".format(word, count))

    print("Cached: {0} ({1:,} words)".format(path, len(sorted_words)))
    return 0


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_fetch(args):
    sources = _resolve_sources(args.source)
    out_dir = args.dir
    rc = 0
    for src in sources:
        print("")
        print("── {0} ──".format(SOURCES[src]["name"]))
        if src == "coca":
            rc |= fetch_coca(out_dir, force=getattr(args, "force", False))
        elif src == "subtlex":
            rc |= fetch_subtlex(out_dir, force=getattr(args, "force", False))
        elif src == "ngrams":
            rc |= fetch_ngrams(out_dir, force=getattr(args, "force", False))
    return rc


def cmd_verify(args):
    sources = _resolve_sources(args.source)
    out_dir = args.dir
    all_ok  = True

    for src_key in sources:
        path = _cache_path(src_key, out_dir)
        src  = SOURCES[src_key]
        print("")
        print("── {0} ──".format(src["name"]))
        print("File: {0}".format(path))

        if not os.path.isfile(path):
            print("NOT CACHED — run: python wordfreq.py fetch --source {0}".format(
                src_key))
            all_ok = False
            continue

        # Read declared SHA256 from header
        sha256_declared = None
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "SHA256:" in line:
                    sha256_declared = line.split("SHA256:")[-1].strip()
                    break
                if not line.startswith("#"):
                    break

        # Recompute SHA256 of raw file content
        with open(path, "rb") as f:
            sha256_actual = hashlib.sha256(f.read()).hexdigest()

        if sha256_declared:
            ok = sha256_actual == sha256_declared
            print("SHA256 declared: {0}".format(sha256_declared))
            print("SHA256 actual:   {0}".format(sha256_actual))
            print("Match:           {0}".format("YES" if ok else "NO — MISMATCH"))
            if not ok:
                all_ok = False
        else:
            print("SHA256: {0} (no declared value to verify against)".format(
                sha256_actual))

        # Row count
        try:
            rows = load_source(src_key, out_dir)
            print("Words: {0:,}".format(len(rows)))
            print("Status: PASS")
        except Exception as e:
            print("Load error: {0}".format(e))
            all_ok = False

    return 0 if all_ok else 1


def cmd_lookup(args):
    word    = args.word.lower().strip()
    sources = _resolve_sources(args.source)
    out_dir = args.dir
    found   = False

    print("Word: {0}".format(word))
    print("")

    for src_key in sources:
        src = SOURCES[src_key]
        try:
            rows = load_source(src_key, out_dir)
        except IOError as e:
            print("  {0}: not cached ({1})".format(src_key, e))
            continue

        idx = word_index(rows)
        if word in idx:
            r = idx[word]
            print("  {0}:".format(src["name"]))
            print("    Rank:      {0:,}".format(r["rank"]))
            print("    Frequency: {0:.2f} per million".format(r["frequency"]))
            found = True
        else:
            print("  {0}: not found".format(src["name"]))

    return 0 if found else 1


def cmd_rank(args):
    return cmd_lookup(args)


def cmd_top(args):
    n       = args.n
    sources = _resolve_sources(args.source)
    out_dir = args.dir

    for src_key in sources:
        src = SOURCES[src_key]
        try:
            rows = load_source(src_key, out_dir)
        except IOError as e:
            print("{0}: not cached — {1}".format(src_key, e), file=sys.stderr)
            continue

        print("Top {0} words — {1}:".format(n, src["name"]))
        print("")
        fmt = "  {rank:>6}  {word:<24}  {freq:.2f}/M"
        for r in rows[:n]:
            print(fmt.format(
                rank=r["rank"], word=r["word"], freq=r["frequency"]))
        print("")

    return 0


def cmd_export(args):
    sources = _resolve_sources(args.source)
    out_dir = args.dir
    fmt     = getattr(args, "format", "tsv")

    for src_key in sources:
        src = SOURCES[src_key]
        try:
            rows = load_source(src_key, out_dir)
        except IOError as e:
            print("{0}: not cached — {1}".format(src_key, e), file=sys.stderr)
            continue

        if fmt == "json":
            out = json.dumps(
                [{"word": r["word"], "rank": r["rank"],
                  "frequency": r["frequency"]} for r in rows],
                ensure_ascii=False, indent=2)
            print(out)
        else:
            print("rank\tword\tfrequency_per_million")
            for r in rows:
                print("{0}\t{1}\t{2:.4f}".format(
                    r["rank"], r["word"], r["frequency"]))

    return 0


def cmd_filter(args):
    """
    Filter cmudict bins.json to words present in the frequency corpus.

    Produces a filtered bins.json containing only words that appear
    in the top --min-rank entries of the frequency corpus, or above
    --min-freq occurrences per million.

    This makes haiku_twist.py output read as natural English rather
    than drawing from obscure technical vocabulary in the full CMU dict.
    """
    bins_path  = args.bins
    out_path   = getattr(args, "output", None)
    sources    = _resolve_sources(args.source)
    out_dir    = args.dir
    min_rank   = getattr(args, "min_rank", None)
    min_freq   = getattr(args, "min_freq", None)

    if not os.path.isfile(bins_path):
        print("Error: bins file not found: {0}".format(bins_path),
              file=sys.stderr)
        return 1

    # Build allowed word set from frequency corpora
    allowed = set()
    for src_key in sources:
        try:
            rows = load_source(src_key, out_dir)
        except IOError as e:
            print("Warning: {0} not cached, skipping: {1}".format(
                src_key, e), file=sys.stderr)
            continue

        for r in rows:
            include = True
            if min_rank is not None and r["rank"] > min_rank:
                include = False
            if min_freq is not None and r["frequency"] < min_freq:
                include = False
            if include:
                allowed.add(r["word"])

    if not allowed:
        print("Error: no words loaded from frequency corpora.", file=sys.stderr)
        return 1

    print("Frequency vocabulary: {0:,} words".format(len(allowed)),
          file=sys.stderr)

    # Load bins
    with io.open(bins_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    meta = raw.get("_meta", {})
    filtered_bins = {}
    total_before  = 0
    total_after   = 0

    for key, words in raw.items():
        if key == "_meta":
            continue
        total_before += len(words)
        kept = [w for w in words if w in allowed]
        total_after  += len(kept)
        filtered_bins[key] = kept

    # Update meta
    filter_desc = []
    if min_rank:
        filter_desc.append("top-{0}-by-rank".format(min_rank))
    if min_freq:
        filter_desc.append("min-freq-{0}".format(min_freq))
    filter_desc = "+".join(filter_desc) or "unfiltered"

    filtered_bins["_meta"] = {
        "source":          meta.get("source", os.path.basename(bins_path)),
        "generated":       time.strftime("%Y-%m-%d"),
        "filtered_by":     [SOURCES[s]["name"] for s in sources if _is_cached(s, out_dir)],
        "filter":          filter_desc,
        "total_words":     total_after,
        "words_before":    total_before,
        "words_removed":   total_before - total_after,
        "retention_pct":   round(100.0 * total_after / total_before, 1)
                           if total_before else 0,
        "note": (
            "Syllable bins filtered to common English vocabulary. "
            "Use with haiku_twist.py for natural-language output."
        ),
    }

    # Determine output path
    if out_path is None:
        base     = os.path.splitext(bins_path)[0]
        out_path = "{0}-common.json".format(base)

    out_dir_parent = os.path.dirname(out_path)
    if out_dir_parent and not os.path.exists(out_dir_parent):
        os.makedirs(out_dir_parent)

    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(filtered_bins, f, ensure_ascii=False,
                  indent=2, sort_keys=True)
        f.write("\n")

    print("Input bins:   {0:,} words".format(total_before), file=sys.stderr)
    print("Output bins:  {0:,} words ({1}% retained)".format(
        total_after,
        filtered_bins["_meta"]["retention_pct"]), file=sys.stderr)
    print("Written:      {0}".format(out_path), file=sys.stderr)

    # Print per-syllable summary
    print("", file=sys.stderr)
    print("Syllable bin summary:", file=sys.stderr)
    for n in sorted(int(k) for k in filtered_bins if k != "_meta"):
        before = len(raw.get(str(n), []))
        after  = len(filtered_bins.get(str(n), []))
        print("  {0} syllable{1}: {2:,} → {3:,}".format(
            n, "" if n == 1 else "s", before, after), file=sys.stderr)

    return 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_sources(source_arg):
    if source_arg == "all":
        return list(SOURCES.keys())
    parts = [s.strip() for s in source_arg.split(",")]
    valid = []
    for p in parts:
        if p in SOURCES:
            valid.append(p)
        else:
            print("Warning: unknown source '{0}' — skipping".format(p),
                  file=sys.stderr)
    return valid or DEFAULT_SOURCES


def positive_int(value):
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


# ── POS tag mapping ───────────────────────────────────────────────────────────
#
# COCA uses a simplified POS tag set. We map these to Penn Treebank tags
# so they are compatible with haiku_grammar.py's POS-indexed bins.
#
# COCA tag -> list of Penn Treebank equivalent tags
#
# COCA tags reference:
#   n     noun
#   v     verb
#   j     adjective
#   r     adverb
#   i     preposition
#   c     conjunction
#   d     determiner
#   p     pronoun
#   m     modal
#   e     existential there
#   x     negation
#   at    article (the/a/an) -> DT
#   in    preposition or subordinating conjunction -> IN
#   (and many others)

COCA_TO_PTB = {
    # Nouns
    "nn":    ["NN"],
    "nn1":   ["NN"],
    "nn2":   ["NNS"],
    "nnl1":  ["NN"],
    "nnl2":  ["NNS"],
    "nno":   ["NN"],
    "nno2":  ["NNS"],
    "nnot":  ["NN"],
    "nnu":   ["NN"],
    "nnu1":  ["NN"],
    "nnu2":  ["NNS"],
    "np":    ["NNP"],
    "np1":   ["NNP"],
    "np2":   ["NNPS"],
    "npd1":  ["NNP"],
    "npd2":  ["NNPS"],
    "npm1":  ["NNP"],
    "npm2":  ["NNPS"],
    # Simple COCA codes
    "n":     ["NN", "NNS"],
    "n1":    ["NN"],
    "n2":    ["NNS"],
    # Verbs
    "vb":    ["VB"],
    "vbz":   ["VBZ"],
    "vbg":   ["VBG"],
    "vbn":   ["VBN"],
    "vbd":   ["VBD"],
    "vbp":   ["VBP"],
    "vhb":   ["VB"],
    "vhd":   ["VBD"],
    "vhg":   ["VBG"],
    "vhn":   ["VBN"],
    "vhz":   ["VBZ"],
    "vhp":   ["VBP"],
    "vmb":   ["MD"],
    "vmd":   ["MD"],
    "vmg":   ["VBG"],
    "vmn":   ["VBN"],
    "vmz":   ["MD"],
    "vmp":   ["MD"],
    "vvb":   ["VB"],
    "vvd":   ["VBD"],
    "vvg":   ["VBG"],
    "vvgk":  ["VBG"],
    "vvn":   ["VBN"],
    "vvnk":  ["VBN"],
    "vvz":   ["VBZ"],
    "vvp":   ["VBP"],
    "v":     ["VB", "VBZ", "VBG", "VBN", "VBD"],
    # Adjectives
    "jj":    ["JJ"],
    "jjr":   ["JJR"],
    "jjs":   ["JJS"],
    "j":     ["JJ"],
    # Adverbs
    "rb":    ["RB"],
    "rbr":   ["RBR"],
    "rbs":   ["RBS"],
    "r":     ["RB"],
    "rr":    ["RB"],
    "rrq":   ["RB"],
    "rrqv":  ["RB"],
    # Prepositions / conjunctions
    "in":    ["IN"],
    "i":     ["IN"],
    "cs":    ["IN"],
    "csn":   ["IN"],
    "cst":   ["IN"],
    "cc":    ["CC"],
    "ccb":   ["CC"],
    "c":     ["CC", "IN"],
    # Determiners / articles
    "dt":    ["DT"],
    "at":    ["DT"],
    "at1":   ["DT"],
    "d":     ["DT"],
    "dd":    ["DT"],
    "dd1":   ["DT"],
    "dd2":   ["DT"],
    "ddq":   ["DT"],
    "ddqv":  ["DT"],
    # Pronouns
    "pp":    ["PRP"],
    "pp$":   ["PRP$"],
    "pn":    ["PRP"],
    "pn1":   ["PRP"],
    "ppx1":  ["PRP"],
    "ppx2":  ["PRP"],
    "ppge":  ["PRP$"],
    "pph1":  ["PRP"],
    "ppy":   ["PRP"],
    "p":     ["PRP"],
    # Modals
    "vm":    ["MD"],
    "md":    ["MD"],
    "m":     ["MD"],
    # Existential
    "ex":    ["EX"],
    "ex$":   ["EX"],
    "e":     ["EX"],
    # Wh- words
    "wh":    ["WP", "WDT", "WRB"],
    "whq":   ["WP"],
    "wdq":   ["WDT"],
    "wrq":   ["WRB"],
    # To
    "to":    ["TO"],
    # Numerals
    "mc":    ["CD"],
    "mc1":   ["CD"],
    "mc2":   ["CD"],
    "cd":    ["CD"],
}

# SUBTLEX-US does not include POS tags per-entry in the basic file.
# We extract POS from COCA only. SUBTLEX is used for frequency filtering.


def _coca_pos_to_ptb(coca_tag):
    """
    Convert a COCA POS tag to a list of Penn Treebank tags.
    Returns empty list if tag is unknown or not mappable.
    """
    if not coca_tag:
        return []
    tag = coca_tag.lower().strip()
    # Direct lookup
    if tag in COCA_TO_PTB:
        return COCA_TO_PTB[tag]
    # Try prefix match (e.g. "nn1" -> "nn")
    for length in (3, 2, 1):
        prefix = tag[:length]
        if prefix in COCA_TO_PTB:
            return COCA_TO_PTB[prefix]
    return []


def cmd_export_pos(args):
    """
    Export POS index from COCA corpus data.

    Produces pos-index.json: a mapping of word (lowercase) ->
    list of Penn Treebank POS tags, derived from COCA's POS column.

    This is the primary input to haiku_grammar.py's build_pos_bins()
    for corpus-quality POS-indexed syllable bin construction.

    Output format:
    {
      "_meta": { ... provenance ... },
      "falling": ["VBG"],
      "stone": ["NN"],
      "golden": ["JJ"],
      "breathe": ["VB"],
      ...
    }

    Words may have multiple tags if they appear with different POS
    in the COCA corpus (e.g. "light": ["NN", "JJ", "VB"]).
    """
    out_dir    = args.dir
    out_path   = getattr(args, "output", None) or os.path.join(
        out_dir, "pos-index.json")
    sources    = _resolve_sources(args.source)

    # COCA is the only source with reliable POS data
    if "coca" not in sources:
        print("Warning: COCA is the primary POS source. Adding coca.",
              file=sys.stderr)
        sources = ["coca"] + [s for s in sources if s != "coca"]

    coca_path = _cache_path("coca", out_dir)
    if not os.path.isfile(coca_path):
        print(
            "Error: COCA not cached. Run:\n"
            "  python wordfreq.py fetch --source coca",
            file=sys.stderr)
        return 1

    print("Building POS index from COCA ...")

    pos_index = {}   # word -> set of PTB tags
    row_count = 0
    mapped    = 0
    skipped   = 0

    with io.open(coca_path, "r", encoding="utf-8", errors="replace") as f:
        header_done = False
        col_names   = None

        for line in f:
            line = line.rstrip("\n\r")
            if line.startswith("#"):
                continue
            if not line.strip():
                continue
            if not header_done:
                col_names   = [c.strip().lower() for c in line.split("\t")]
                header_done = True
                continue
            if col_names is None:
                continue

            parts = line.split("\t")
            if len(parts) < len(col_names):
                continue

            row = dict(zip(col_names, parts))
            word = row.get("word", "").strip().lower()
            if not word or not word.replace("'", "").replace("-", "").isalpha():
                skipped += 1
                continue

            # Extract COCA POS tag
            coca_tag = row.get("pos", "").strip()
            ptb_tags = _coca_pos_to_ptb(coca_tag)

            if not ptb_tags:
                # Try to infer from word form as fallback
                skipped += 1
                continue

            if word not in pos_index:
                pos_index[word] = set()
            for tag in ptb_tags:
                pos_index[word].add(tag)

            row_count += 1
            mapped    += 1

    # Convert sets to sorted lists for JSON serialisation
    pos_index_serialisable = {
        word: sorted(tags)
        for word, tags in pos_index.items()
    }

    # Count tag distribution
    tag_counts = {}
    for tags in pos_index_serialisable.values():
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    pos_index_serialisable["_meta"] = {
        "source":      "COCA 60k word frequency list",
        "generated":   time.strftime("%Y-%m-%d"),
        "words":       len(pos_index_serialisable) - 1,  # -1 for _meta
        "mapped":      mapped,
        "skipped":     skipped,
        "tag_counts":  tag_counts,
        "note": (
            "Penn Treebank POS tags derived from COCA POS column. "
            "Words may have multiple tags (polysemy). "
            "Consumed by haiku_grammar.py build_pos_bins()."
        ),
    }

    out_dir_parent = os.path.dirname(out_path)
    if out_dir_parent and not os.path.exists(out_dir_parent):
        os.makedirs(out_dir_parent)

    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump(pos_index_serialisable, f,
                  ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    word_count = len(pos_index_serialisable) - 1

    print("Words indexed:  {0:,}".format(word_count))
    print("Rows processed: {0:,}".format(row_count))
    print("Skipped:        {0:,} (unknown POS or non-alpha)".format(skipped))
    print("")
    print("Top POS tags:")
    for tag, count in sorted(tag_counts.items(),
                              key=lambda x: x[1], reverse=True)[:15]:
        print("  {0:<6} {1:>6,} words".format(tag, count))
    print("")
    print("Written: {0}".format(out_path))
    print("")
    print("Next step:")
    print("  python tools/haiku/haiku_grammar.py info --pos {0}".format(
        out_path))

    return 0


# ── Build parser ──────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="wordfreq",
        description=(
            "English word frequency corpus mirror.\n"
            "\n"
            "Sources: coca (BYU/Davies), subtlex (Ghent/Brysbaert),\n"
            "         ngrams (Google Books 2019)\n"
            "\n"
            "Default: coca + subtlex (recommended).\n"
            "Use --source all to include ngrams (~5GB download).\n"
            "\n"
            "The filter subcommand produces a filtered bins.json for\n"
            "haiku_twist.py — natural-language vocabulary only.\n"
            "\n"
            "The export-pos subcommand produces pos-index.json for\n"
            "haiku_grammar.py — POS-tagged word index from COCA."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start (frequency filtering):\n"
            "  python wordfreq.py fetch\n"
            "  python wordfreq.py filter --bins docs/cmudict/bins.json\n"
            "  # produces docs/cmudict/bins-common.json\n"
            "\n"
            "Quick start (POS index for grammar-aware haiku):\n"
            "  python wordfreq.py fetch --source coca\n"
            "  python wordfreq.py export-pos\n"
            "  # produces docs/wordfreq/pos-index.json\n"
            "  python tools/haiku/haiku_grammar.py info\n"
        )
    )

    p.add_argument(
        "--source", default=",".join(DEFAULT_SOURCES), metavar="SOURCE",
        help="corpus source(s): coca,subtlex,ngrams or all "
             "(default: {0})".format(",".join(DEFAULT_SOURCES)))
    p.add_argument(
        "--dir", default=DEFAULT_DIR, metavar="DIR",
        help="cache directory (default: {0})".format(DEFAULT_DIR))

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # fetch
    pf = sub.add_parser("fetch", help="download and cache frequency corpora")
    pf.add_argument("--force", action="store_true",
        help="re-fetch even if already cached")

    # verify
    sub.add_parser("verify", help="verify cached corpora (SHA256)")

    # lookup
    pl = sub.add_parser("lookup",
        help="look up a word's frequency and rank")
    pl.add_argument("word", help="word to look up")

    # rank (alias for lookup)
    pr = sub.add_parser("rank",
        help="look up a word's rank (alias for lookup)")
    pr.add_argument("word", help="word to look up")

    # top
    pt = sub.add_parser("top",
        help="print the top N most frequent words")
    pt.add_argument("n", type=positive_int, help="number of words to show")

    # export
    pe = sub.add_parser("export",
        help="export corpus as TSV or JSON to stdout")
    pe.add_argument("--format", choices=["tsv", "json"], default="tsv",
        help="output format (default: tsv)")

    # export-pos
    pep = sub.add_parser("export-pos",
        help="export POS index (word -> PTB tags) for haiku_grammar.py")
    pep.add_argument(
        "--output", "-o", default=None, metavar="FILE",
        help="output path (default: docs/wordfreq/pos-index.json)")

    # filter
    pfi = sub.add_parser("filter",
        help="filter cmudict bins.json to common vocabulary")
    pfi.add_argument("--bins", required=True, metavar="FILE",
        help="input bins.json from cmudict.py export")
    pfi.add_argument("--output", "-o", default=None, metavar="FILE",
        help="output path (default: bins-common.json alongside input)")
    pfi.add_argument("--min-rank", type=positive_int, default=30000,
        metavar="N",
        help="include only words ranked <= N (default: 30000)")
    pfi.add_argument("--min-freq", type=float, default=None, metavar="F",
        help="include only words with frequency >= F per million")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "fetch":      return cmd_fetch(args)
        if args.command == "verify":     return cmd_verify(args)
        if args.command == "lookup":     return cmd_lookup(args)
        if args.command == "rank":       return cmd_rank(args)
        if args.command == "top":        return cmd_top(args)
        if args.command == "export":     return cmd_export(args)
        if args.command == "export-pos": return cmd_export_pos(args)
        if args.command == "filter":     return cmd_filter(args)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
