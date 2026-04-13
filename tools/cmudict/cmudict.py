#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
cmudict.py -- CMU Pronouncing Dictionary mirror and syllable tool

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

Cached file format:
    The cached file conforms to the Crowsong Archivist Header Format
    (CAHF), draft-darley-crowsong-archivist-03. The header is a block
    of comment lines beginning with "# ARCHIVIST  v1.0", terminated by
    the sentinel line "# ---END-HEADER---". The body follows immediately.

    SHA256 is computed over the normalised body (CRLF -> LF, trailing
    newlines stripped) encoded as UTF-8. Verification recomputes SHA256
    using the same normalisation rule applied at fetch time.

    Files produced by this tool are intended to be cross-verifiable by
    tools/archivist/archivist.py under the shared CAHF specification:
        python tools/archivist/archivist.py verify <file>

Syllable counting:
    Each vowel phoneme ends in a digit (0=unstressed, 1=primary,
    2=secondary stress). Syllable count = number of phonemes ending
    in a digit. This is exact with respect to the dictionary's phoneme
    transcription for any in-dictionary word.

Out-of-dictionary words:
    The tool returns None for words not in the dictionary. The haiku
    tool skips out-of-dictionary words when building syllable bins.
    No heuristic fallback is used -- only confirmed syllable counts.

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
import re
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    from urllib2 import urlopen, Request, URLError, HTTPError  # noqa
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError               # noqa

# ── Source URLs ───────────────────────────────────────────────────────────────
#
# HTTPS-only. Plain HTTP is not accepted: on first fetch the tool hashes
# the received body and writes that hash into the CAHF header. A MITM on
# an HTTP connection would let an attacker pin their own digest.
# If the primary is unreachable the fetch fails cleanly with no fallback.

CMUDICT_SOURCES = [
    "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict",
]

USER_AGENT    = ("Crowsong/1.0 (trey@propertools.be; "
                 "CMU dict mirror for haiku corpus)")
REQUEST_DELAY = 2.0
DEFAULT_DIR   = os.path.join("docs", "cmudict")
DEFAULT_FILE  = "cmudict.dict"
DEFAULT_BINS  = "bins.json"

# CAHF format constants. Conforms to draft-darley-crowsong-archivist-03.
CAHF_SENTINEL = "# ---END-HEADER---"
CAHF_VERSION  = "v1.0"

# Versions this tool accepts during verification. Forward-compatible: add
# future versions here when their semantics are understood.
_ACCEPTED_VERSIONS = frozenset(["v1.0"])

# Required CAHF fields -- duplicate required fields are malformed (FAIL).
# Duplicate optional fields: first occurrence wins, later ones are ignored.
# (CAHF spec §3.1 duplicate field rule, draft-darley-crowsong-archivist-03)
_REQUIRED_FIELDS = frozenset(["ARCHIVIST", "SHA256"])
_KNOWN_FIELDS = frozenset([
    "ARCHIVIST", "TITLE", "AUTHOR", "LANG", "SOURCE", "DATE", "FETCHED",
    "ENTRIES", "CHARS", "LINES", "TAGS", "TLP", "NOTE", "LICENSE",
    "TOOL", "SHA256",
])


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_url(url, retries=3):
    """
    Fetch a URL, returning the body as a unicode string.

    Decodes strictly as UTF-8. Raises IOError on encoding errors so
    corrupted or maliciously altered transfers are not silently accepted.
    All output goes to stderr to keep stdout clean for pipelines.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                r = urlopen(req, timeout=60)
                raw = r.read()
            else:
                with urlopen(req, timeout=60) as r:
                    raw = r.read()
            return raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise IOError(
                "Encoding error fetching {0}: {1}".format(url, e))
        except (URLError, HTTPError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed to fetch {0}: {1}".format(url, last_err))


# ── CAHF file format ──────────────────────────────────────────────────────────
#
# Conforms to draft-darley-crowsong-archivist-03.
#
# On-disk layout (LF line endings throughout):
#
#   # ARCHIVIST  v1.0
#   # <FIELD>    <value>       <- canonical: two spaces between name and value
#   ...
#   # SHA256     <hex>
#   # ---END-HEADER---
#   <body, LF-normalised, one trailing LF>
#
# Hashing contract (CAHF spec §4.4):
#
#   (a) Stamp:   body_for_hash = body_fetched.rstrip("\n")           (after CRLF->LF)
#                sha256        = sha256(body_for_hash.encode("utf-8")).hexdigest()
#
#   (b) Store:   content = header_block + "\n" + body_for_hash + "\n"
#                (header_block ends with the sentinel line, no trailing LF)
#
#   (c) Verify:  body_extracted = content_after_sentinel
#                body_for_hash  = body_extracted.rstrip("\n")
#                sha256_actual  = sha256(body_for_hash.encode("utf-8")).hexdigest()
#
# Field subset used by this tool (CAHF spec §8.3 documented exception):
#   ARCHIVIST, SOURCE, FETCHED, ENTRIES, CHARS, LINES, LICENSE, TOOL, SHA256.

def _normalise_body(body):
    """
    Apply CAHF line-ending normalisation and trailing-newline strip.
    Returns body_for_hash -- the string fed to SHA256. (CAHF spec §4.1-4.2)
    """
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    return body.rstrip("\n")


def _sha256_of_body(body_for_hash):
    """
    SHA256 of a normalised body string, encoded as UTF-8. (CAHF spec §4.3)
    Caller is responsible for passing a value already through _normalise_body().
    """
    return hashlib.sha256(body_for_hash.encode("utf-8")).hexdigest()


def _make_header(body_for_hash, source_url):
    """
    Build a CAHF-conformant header block for the cached dictionary file.

    body_for_hash must be the normalised body (already passed through
    _normalise_body()). Returns a string of all header lines joined with
    LF, ending with the sentinel line. No trailing LF is appended here;
    cmd_fetch() writes one separator LF between the returned string and
    the body. (CAHF spec §5, §8.1)
    """
    fetched     = time.strftime("%Y-%m-%d")
    entry_count = sum(
        1 for line in body_for_hash.splitlines()
        if line and not line.startswith(";") and not line.startswith("#")
    )
    char_count = len(body_for_hash)
    line_count = (0 if body_for_hash == ""
                  else body_for_hash.count("\n") + 1)
    sha256     = _sha256_of_body(body_for_hash)

    # Canonical CAHF field format: "# {FIELD:<10}  {value}"
    def field(key, value):
        return "# {0:<10}  {1}".format(key, value)

    lines = [
        field("ARCHIVIST", CAHF_VERSION),
        "#",
        field("SOURCE",    source_url),
        field("FETCHED",   fetched),
        field("ENTRIES",   str(entry_count)),
        field("CHARS",     str(char_count)),
        field("LINES",     str(line_count)),
        field("LICENSE",   "Public domain (Carnegie Mellon University)"),
        field("TOOL",      "tools/cmudict/cmudict.py (Proper Tools SRL)"),
        "#",
        "# Format: WORD  PH1 PH2 ... PHn",
        "# Vowel phonemes end in a digit (0=unstressed, 1=primary, 2=secondary).",
        "# Syllable count = number of phonemes ending in a digit.",
        "#",
        field("SHA256",    sha256),
        CAHF_SENTINEL,
    ]
    return "\n".join(lines)


def _split_header_body(content):
    """
    Split a CAHF file into (header_str, body_for_hash).

    Locates the exact sentinel line "# ---END-HEADER---\\n", splits there,
    and strips the one trailing LF appended at write time so the result
    equals the body_for_hash from stamp time. (CAHF spec §4.4 invariant (c))

    No fallback path. The sentinel is required. Files without it are
    rejected with ValueError. (CAHF spec §6.4, §8.2)
    """
    marker = CAHF_SENTINEL + "\n"
    idx = content.find(marker)
    if idx == -1:
        raise ValueError(
            "Cache file is missing the '{0}' sentinel line. "
            "Re-fetch with: python cmudict.py fetch --force".format(
                CAHF_SENTINEL))
    header        = content[:idx]
    body_stored   = content[idx + len(marker):]
    body_for_hash = body_stored.rstrip("\n")
    return header, body_for_hash


# Compiled regex for canonical CAHF field lines. Matches only lines whose
# field name is one or more uppercase letters, digits, or hyphens, followed
# by at least two spaces. This prevents freeform comment prose that happens
# to contain two spaces from being misread as a field. (CAHF spec §2.2)
_FIELD_RE = re.compile(r"^([A-Z0-9-]+)  (.*)$")


def _parse_cahf_header(header_str):
    """
    Parse CAHF header fields from a header block string.

    Canonical path: matches "# FIELDNAME  value" using _FIELD_RE, which
    requires the field name to consist only of A-Z, 0-9, and hyphen. This
    prevents comment prose lines like "# Format: WORD  PH1 PH2" from being
    misread as fields. (CAHF spec §2.2, §2.5)

    Legacy path: accepts "# FIELDNAME: value" but only for field names in
    _KNOWN_FIELDS, so arbitrary colons in URLs and comments are ignored.
    (CAHF spec §7.3)

    Duplicate handling (CAHF spec §3.1):
      - Duplicate required fields (ARCHIVIST, SHA256): raises ValueError.
      - Duplicate optional fields: first occurrence wins; later ignored.

    Returns dict of {field_name: value_string}.
    """
    fields = {}
    seen   = set()

    for line in header_str.splitlines():
        if not line.startswith("# "):
            continue
        rest = line[2:]

        key = val = None
        m = _FIELD_RE.match(rest)
        if m:
            key, val = m.group(1), m.group(2).strip()
        elif ":" in rest:
            # Legacy colon fallback -- restricted to known field names only.
            k, _, v = rest.partition(":")
            k = k.strip()
            if k in _KNOWN_FIELDS:
                key, val = k, v.strip()

        if key is not None:
            if key in seen:
                if key in _REQUIRED_FIELDS:
                    raise ValueError(
                        "Duplicate required CAHF field '{0}'.".format(key))
                # Optional duplicate: first wins, ignore subsequent.
                continue
            seen.add(key)
            fields[key] = val

    return fields


def _load_verified_body(dict_path):
    """
    Read the cached file, verify its CAHF SHA256, and return the verified
    body and declared SHA256.

    This is the single internal verification path. Both load_verified_dict()
    and cmd_export() call this so that verification logic is not duplicated.

    Returns:
        (body_for_hash, sha256_actual) -- both strings
    Raises:
        IOError with a descriptive message on any failure.
    """
    if not os.path.isfile(dict_path):
        raise IOError(
            "CMU dict not cached. Run: python cmudict.py fetch")

    with io.open(dict_path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # Gate on ARCHIVIST marker. (CAHF spec §6.1 step 3)
    first_content = next(
        (l for l in content.splitlines() if l.strip()), "")
    if not first_content.startswith("# ARCHIVIST"):
        raise IOError(
            "Cached file is not CAHF-stamped (missing # ARCHIVIST marker). "
            "Re-fetch with: python cmudict.py fetch --force")

    # Split at sentinel. (CAHF spec §6.1 steps 4-5)
    try:
        header, body_for_hash = _split_header_body(content)
    except ValueError as e:
        raise IOError(str(e))

    # Parse header fields; raises IOError on duplicate fields.
    # (CAHF spec §3.1 duplicate field rule)
    try:
        fields = _parse_cahf_header(header)
    except ValueError as e:
        raise IOError(str(e))

    # Version check: explicit forward-compatible gating. (CAHF spec §2.2)
    version = fields.get("ARCHIVIST", "")
    if version not in _ACCEPTED_VERSIONS:
        raise IOError(
            "Cached file declares CAHF version '{0}'; "
            "this tool accepts: {1}. "
            "Re-fetch with: python cmudict.py fetch --force".format(
                version, ", ".join(sorted(_ACCEPTED_VERSIONS))))

    # Extract and validate SHA256. (CAHF spec §6.1 steps 7-8, §6.4)
    sha256_declared = fields.get("SHA256")
    if not sha256_declared:
        raise IOError(
            "Cached file has no declared SHA256. "
            "Re-fetch with: python cmudict.py fetch --force")

    if not re.match(r"^[0-9a-fA-F]{64}$", sha256_declared):
        raise IOError(
            "Cached file has invalid SHA256 field syntax: '{0}'. "
            "Re-fetch with: python cmudict.py fetch --force".format(
                sha256_declared))
    # Normalise to lowercase before comparison so uppercase hex (which the
    # CAHF spec says SHOULD be accepted on verify) does not cause a false
    # mismatch. _sha256_of_body() always returns lowercase. (CAHF spec §4.3)
    sha256_declared = sha256_declared.lower()

    sha256_actual = _sha256_of_body(body_for_hash)
    if sha256_actual != sha256_declared:
        raise IOError(
            "Cached file failed SHA256 verification.\n"
            "  Declared: {0}\n"
            "  Actual:   {1}\n"
            "Re-fetch with: python cmudict.py fetch --force".format(
                sha256_declared, sha256_actual))

    return body_for_hash, sha256_actual


# ── Core parser ───────────────────────────────────────────────────────────────

def _parse_dict(content):
    """
    Parse CMU dict content into a dict: word -> list of phoneme lists.

    Handles both raw upstream format and CAHF-wrapped cached format
    (lines starting with '#' or ';' are skipped as comments).
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
        word_raw = parts[0]
        phones   = parts[1:]

        # Strip CMUdict alternate-pronunciation suffix: WORD(2) -> WORD.
        # Precise terminal pattern avoids mangling tokens with literal parens.
        word_raw = re.sub(r"\(\d+\)$", "", word_raw)

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

def load_unverified_dict(dict_path):
    """
    Load and parse the cached CMU dictionary WITHOUT verifying SHA256.

    WARNING: This bypasses CAHF integrity verification and MUST NOT be
    used for normal corpus consumption. Use load_verified_dict() instead.
    This path exists only for callers that have already verified externally
    (e.g. cmd_verify, which performs its own explicit verification before
    calling _parse_dict directly).

    Returns:
        dict: word (lowercase) -> list of phoneme lists
    Raises:
        IOError if the file does not exist.
    """
    if not os.path.isfile(dict_path):
        raise IOError(
            "CMU dict not cached. Run: python cmudict.py fetch")
    with io.open(dict_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _parse_dict(content)


def load_verified_dict(dict_path):
    """
    Load the cached CMU dictionary, verifying SHA256 before returning.

    Delegates to _load_verified_body() for the single internal verification
    path. Refuses to return content if the file is missing, not CAHF-stamped,
    has an unrecognised version, lacks a SHA256 field, or fails digest
    comparison.

    Used by all CLI commands that produce downstream artifacts
    (syllables, phones, bin, bins).

    Returns:
        dict: word (lowercase) -> list of phoneme lists
    Raises:
        IOError with a descriptive message on any failure.
    """
    body_for_hash, _ = _load_verified_body(dict_path)
    return _parse_dict(body_for_hash)


def get_syllables(cmudict, word):
    """
    Return syllable count for word (primary pronunciation), or None.

    Args:
        cmudict: dict from load_unverified_dict() or load_verified_dict()
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
        cmudict: dict from load_unverified_dict() or load_verified_dict()
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
        cmudict: dict from load_unverified_dict() or load_verified_dict()
        word:    word string (case-insensitive)

    Returns:
        list of phoneme lists (may be empty if word not in dictionary).
    """
    return cmudict.get(word.lower(), [])


def build_bins(cmudict):
    """
    Group all words by syllable count (primary pronunciation only).

    Words with zero syllables (e.g. abbreviations without vowels) are
    excluded. Words within each bin are alphabetically sorted, giving
    downstream tools a stable, reproducible index.

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
    """
    Download and cache the CMU Pronouncing Dictionary.

    All progress and status output goes to stderr so that this command
    is safe to use in shell pipelines. stdout is reserved for data.
    """
    path = _dict_path(out_dir)

    if _is_cached(out_dir) and not force:
        print("Already cached: {0}".format(path), file=sys.stderr)
        print("Use --force to re-fetch.", file=sys.stderr)
        return 0

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    source_url   = None
    body_for_hash = None
    parsed_check  = None
    errors        = []

    for url in CMUDICT_SOURCES:
        print("Fetching {0} ...".format(url), file=sys.stderr)
        try:
            body_raw = _fetch_url(url)
            # Normalise before sanity check so we operate on the same body
            # that will be stored and hashed. (CAHF spec §4.4 invariant (a))
            candidate_body = _normalise_body(body_raw)
            # Sanity check on parsed entry count, not raw line count,
            # so a body full of garbage lines cannot slip through.
            candidate_dict = _parse_dict(candidate_body)
            if len(candidate_dict) < 1000:
                raise ValueError(
                    "suspiciously few entries ({0} parsed)".format(
                        len(candidate_dict)))
            # All checks passed -- commit the result.
            body_for_hash = candidate_body
            parsed_check  = candidate_dict
            source_url    = url
            break
        except (IOError, ValueError) as e:
            errors.append("{0}: {1}".format(url, e))
            print("  FAIL: {0}".format(e), file=sys.stderr)
            time.sleep(REQUEST_DELAY)

    if source_url is None:
        print("Error: could not fetch CMU dict from any source.",
              file=sys.stderr)
        for e in errors:
            print("  {0}".format(e), file=sys.stderr)
        return 1

    # body_for_hash and parsed_check are guaranteed non-None here.
    header  = _make_header(body_for_hash, source_url)

    # Stored layout: header (ends with sentinel) + "\n" + body + "\n"
    # (CAHF spec §4.4 invariant (b), §5 step 5)
    content = header + "\n" + body_for_hash + "\n"

    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    sha256 = _sha256_of_body(body_for_hash)
    print("Cached: {0}".format(path), file=sys.stderr)
    print("SHA256: {0}".format(sha256), file=sys.stderr)
    print("Size:   {0:,} bytes".format(len(content.encode("utf-8"))),
          file=sys.stderr)
    print("Words:  {0:,} unique entries".format(len(parsed_check)),
          file=sys.stderr)
    return 0


def cmd_verify(out_dir):
    """
    Verify SHA256 of the cached CMU dict file. (CAHF spec §6)

    The full verification report (file path, declared/actual digests,
    match status, word count, result) goes to stdout so that automation
    can capture a complete, consistent record. Only operational errors
    that prevent reading the file at all (file missing, unreadable) go
    to stderr.
    """
    path = _dict_path(out_dir)
    if not os.path.isfile(path):
        print("Error: not cached. Run: python cmudict.py fetch",
              file=sys.stderr)
        return 1

    with io.open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # Family gate: "# ARCHIVIST" identifies CAHF-family files.
    # Actual version acceptance is checked after header parsing below.
    # (CAHF spec §2.2, §6.1 step 3)
    first_content = next(
        (l for l in content.splitlines() if l.strip()), "")
    if not first_content.startswith("# ARCHIVIST"):
        print("File:     {0}".format(path))
        print("Error:    not a CAHF-stamped file (missing # ARCHIVIST marker).")
        print("Verification: UNSTAMPED")
        return 1

    # Locate and split at sentinel. (CAHF spec §6.1 steps 4-5)
    # A missing sentinel on a CAHF-family file is classified as legacy
    # (pre-sentinel format), not malformed. (CAHF spec §7.1 taxonomy)
    try:
        header, body_for_hash = _split_header_body(content)
    except ValueError as e:
        print("File:     {0}".format(path))
        print("Error:    {0}".format(e))
        print("Verification: FAIL (legacy)")
        return 1

    # Parse fields; catch duplicate required-field violations. (CAHF spec §3.1)
    try:
        fields = _parse_cahf_header(header)
    except ValueError as e:
        print("File:     {0}".format(path))
        print("Error:    {0}".format(e))
        print("Verification: FAIL (malformed)")
        return 1

    # Version check. (CAHF spec §2.2)
    version = fields.get("ARCHIVIST", "")
    if version not in _ACCEPTED_VERSIONS:
        print("File:     {0}".format(path))
        print("Error:    unsupported CAHF version '{0}' "
              "(accepted: {1}).".format(
                  version, ", ".join(sorted(_ACCEPTED_VERSIONS))))
        print("Verification: UNSUPPORTED -- this is a CAHF-family file, "
              "not an unstamped file.")
        return 1

    # Extract and validate declared SHA256. (CAHF spec §6.4)
    sha256_declared = fields.get("SHA256")
    if not sha256_declared:
        print("File:     {0}".format(path))
        print("Error:    no SHA256 field in header.")
        print("Verification: FAIL (damaged) -- re-fetch with: "
              "python cmudict.py fetch --force")
        return 1

    if not re.match(r"^[0-9a-fA-F]{64}$", sha256_declared):
        print("File:     {0}".format(path))
        print("Error:    invalid SHA256 field syntax: '{0}'".format(
            sha256_declared))
        print("Verification: FAIL (damaged)")
        return 1

    # Normalise to lowercase before comparison so uppercase hex (SHOULD be
    # accepted per CAHF spec §4.3) does not cause a false mismatch.
    sha256_declared = sha256_declared.lower()

    sha256_actual = _sha256_of_body(body_for_hash)

    print("File:     {0}".format(path))
    print("Version:  {0}".format(version))
    print("Declared: {0}".format(sha256_declared))
    print("Actual:   {0}".format(sha256_actual))

    if sha256_actual != sha256_declared:
        print("Match:    NO -- MISMATCH")
        print("Verification: FAIL (damaged)")
        return 1

    print("Match:    YES")
    cmudict = _parse_dict(body_for_hash)
    print("Words:    {0:,} unique entries".format(len(cmudict)))
    print("Verification: PASS")
    return 0


def cmd_syllables(word, out_dir):
    """Print syllable count for a word (verifies cache before use)."""
    cmudict = load_verified_dict(_dict_path(out_dir))
    n = get_syllables(cmudict, word)
    if n is None:
        print("Not in dictionary: {0}".format(word), file=sys.stderr)
        return 1
    print("{0}  ->  {1} syllable{2}".format(
        word.lower(), n, "" if n == 1 else "s"))
    return 0


def cmd_phones(word, out_dir):
    """Print phoneme list for a word (verifies cache before use)."""
    cmudict = load_verified_dict(_dict_path(out_dir))
    all_pron = get_all_pronunciations(cmudict, word)
    if not all_pron:
        print("Not in dictionary: {0}".format(word), file=sys.stderr)
        return 1
    for i, phones in enumerate(all_pron):
        n   = _syllable_count(phones)
        tag = "" if i == 0 else "  (alternate {0})".format(i + 1)
        print("{0}{1}  ->  {2}  ({3} syllable{4})".format(
            word.lower(), tag,
            " ".join(phones),
            n, "" if n == 1 else "s"))
    return 0


def cmd_bin(n, out_dir):
    """Print all words with exactly n syllables, one per line."""
    cmudict = load_verified_dict(_dict_path(out_dir))
    bins    = build_bins(cmudict)
    words   = bins.get(n, [])
    if not words:
        print("No words with {0} syllable{1}.".format(
            n, "" if n == 1 else "s"), file=sys.stderr)
        return 1
    for word in words:
        sys.stdout.write(word + "\n")
    print("{0:,} words with {1} syllable{2}.".format(
        len(words), n, "" if n == 1 else "s"), file=sys.stderr)
    return 0


def cmd_bins(out_dir):
    """Print summary of word counts per syllable bin."""
    cmudict = load_verified_dict(_dict_path(out_dir))
    bins    = build_bins(cmudict)

    total = sum(len(v) for v in bins.values())
    print("{0:,} unique words across {1} syllable bins:\n".format(
        total, len(bins)))

    fmt = "  {syl:>3} syllable{pl}  {count:>7,} words  {bar}"
    max_count = max(len(bins[n]) for n in bins) if bins else 1
    for n in sorted(bins.keys()):
        count  = len(bins[n])
        bar_w  = 30
        filled = int(round(float(count) / max_count * bar_w))
        bar    = "\u2588" * filled + "\u2591" * (bar_w - filled)
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

    Verifies the cached file before use. The _meta block includes the
    SHA256 of the source dictionary body so that downstream tools can
    confirm which corpus revision the bins were derived from.

    Output format:
    {
      "_meta": {
        "source":        "cmudict.dict",
        "source_sha256": "<sha256 of normalised dictionary body>",
        "generated":     "YYYY-MM-DD",
        "total_words":   N,
        "min_syllables": 1,
        "max_syllables": 9,
        "note":          "..."
      },
      "1": ["a", "ab", "ace", ...],
      "2": ["abbey", "abbot", ...],
      ...
    }

    Keys are string representations of syllable counts.
    Words are lowercase, alphabetically sorted within each bin.
    """
    if output_path is None:
        output_path = _bins_path(out_dir)

    dict_path = _dict_path(out_dir)

    # Single verification path: raises IOError on any failure.
    body_for_hash, sha256_actual = _load_verified_body(dict_path)

    cmudict = _parse_dict(body_for_hash)
    bins    = build_bins(cmudict)

    filtered = {
        str(n): words
        for n, words in bins.items()
        if min_syllables <= n <= max_syllables
    }

    total = sum(len(v) for v in filtered.values())
    filtered["_meta"] = {
        "source":        DEFAULT_FILE,
        "source_sha256": sha256_actual,
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

    # Ensure parent directory of the output path exists, whether inside
    # out_dir or a fully custom path.
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent and not os.path.exists(parent):
        os.makedirs(parent)

    with io.open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False,
                  indent=2, sort_keys=True)
        f.write("\n")

    print("Exported: {0}".format(output_path))
    print("Words:    {0:,} across {1} bins".format(
        total, len(filtered) - 1))   # -1 for _meta
    for n in sorted(bins.keys()):
        if min_syllables <= n <= max_syllables:
            print("  {0} syllable{1}: {2:,} words".format(
                n, "" if n == 1 else "s", len(bins[n])))
    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def positive_int(value):
    try:
        ivalue = int(value)
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError("must be an integer")
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
            "Cached files conform to the Crowsong Archivist Header Format\n"
            "(draft-darley-crowsong-archivist-03). Files produced by this\n"
            "tool are intended to be cross-verifiable by:\n"
            "    python tools/archivist/archivist.py verify <file>\n"
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
    # sub.required is unreliable on Python 2.7 argparse; main() handles it.

    pf = sub.add_parser("fetch",
        help="download and cache the CMU Pronouncing Dictionary")
    pf.add_argument("--force", action="store_true",
        help="re-fetch even if already cached")

    sub.add_parser("verify",
        help="verify CAHF SHA256 of cached file")

    ps = sub.add_parser("syllables",
        help="print syllable count for a word")
    ps.add_argument("word", help="word to look up (case-insensitive)")

    ph = sub.add_parser("phones",
        help="print phoneme transcription for a word")
    ph.add_argument("word", help="word to look up (case-insensitive)")

    pb = sub.add_parser("bin",
        help="list all words with exactly n syllables")
    pb.add_argument("n", type=positive_int, help="syllable count")

    sub.add_parser("bins",
        help="print word counts per syllable bin")

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
    parser = build_parser()
    args   = parser.parse_args()

    # Portable subcommand check -- sub.required is unreliable on Python 2.7.
    if not getattr(args, "command", None):
        parser.print_help()
        return 1

    out_dir = args.dir

    if args.command == "export" and args.min_syllables > args.max_syllables:
        print(
            "Error: --min-syllables ({0}) cannot exceed "
            "--max-syllables ({1})".format(
                args.min_syllables, args.max_syllables),
            file=sys.stderr)
        return 1

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
