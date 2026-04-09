#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
archivist.py -- Self-describing document framing tool

Wraps any plain text document in a self-describing header block
containing SHA256, metadata, and provenance. The result is a single
plain-text file that carries its own verification credentials.

The archivist doesn't care what your document contains. It will stamp
it, hash it, and file it. It will also tell you, quietly and without
drama, if someone has tampered with it since.

Note: archivist provides content integrity checking, not cryptographic
authenticity. Anyone can restamp a document with a new header and hash
unless the file is additionally signed by an external mechanism.

Usage:
    python archivist.py stamp [options] [file]
    python archivist.py verify [file ...]
    python archivist.py show   [file ...]
    python archivist.py strip  [file ...]

Options (stamp):
    -t, --title TITLE       Document title
    -a, --author AUTHOR     Author name
    -s, --source SOURCE     Source URL or reference
    -n, --note NOTE         Freeform note
    -l, --lang LANG         Language / script
    -T, --tags TAG[,TAG]    Comma-separated tags
    -o, --output FILE       Output file (default: stdout)
    --tlp LEVEL             TLP classification (CLEAR/GREEN/AMBER/RED)
    --no-date               Omit stamp date (for reproducible output)

Note on round-trips: archivist normalises line endings to LF and
strips trailing newlines during stamping. Strip output always ends
with a single newline. This is a canonical-text round-trip, not a
byte-for-byte round-trip.

Examples:
    # Stamp a file
    python archivist.py stamp --title "Signal Survives" --author "T. Darley" \
        --source "propertools.be" document.txt

    # Stamp from stdin
    echo "Signal survives." | python archivist.py stamp --title "Test" -

    # Verify one or more stamped files
    python archivist.py verify docs/udhr/ara.txt docs/texts/shakespeare.txt

    # Verify everything in a directory
    python archivist.py verify docs/udhr/*.txt

    # Show metadata and verification status
    python archivist.py show docs/udhr/ara.txt

    # Strip the archivist header, recover the normalised body
    python archivist.py strip docs/udhr/ara.txt

    # Round-trip: stamp then verify
    echo "All human beings are born free." | \
        python archivist.py stamp --title "UDHR Article 1" - | \
        python archivist.py verify -

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import sys
import time

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
else:
    text_type = str

__version__ = "1.0"

# -- Header format -------------------------------------------------------------
#
# The archivist header is a block of lines beginning with "# ".
# It is terminated by a blank line, after which the document body begins.
# The SHA256 is computed over the body only, after CRLF normalisation.
# This matches the format used by tools/texts/texts.py and tools/udhr/udhr.py.
#
# Fields:
#   ARCHIVIST   version marker -- identifies this format
#   TITLE       document title
#   AUTHOR      author name(s)
#   LANG        language / script
#   SOURCE      URL or bibliographic reference
#   DATE        ISO date stamped (YYYY-MM-DD)
#   TAGS        comma-separated tags
#   TLP         Traffic Light Protocol classification
#   NOTE        freeform annotation
#   CHARS       character count of body
#   LINES       line count of body
#   SHA256      hex digest of body (UTF-8, LF-normalised)
#
# All fields are optional except SHA256.
# On parsing, unknown header fields are displayed by `show` and ignored
# by `verify`. `strip` removes the header entirely.

HEADER_MARKER   = "# ARCHIVIST"
FIELD_PREFIX    = "# "
SHA256_FIELD    = "SHA256"
MARKER_FIELD    = "ARCHIVIST"   # field name for the format-marker / version line


# -- Helpers -------------------------------------------------------------------

def _to_text(value):
    """
    Safely coerce value to unicode text on both Python 2 and 3.
    Avoids UnicodeEncodeError when str() is called on unicode in Python 2.
    """
    if value is None:
        return None
    if isinstance(value, text_type):
        return value
    if PY2 and isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return text_type(value)


def _line_count(text):
    """
    Count lines the way a user expects: empty string = 0, one line = 1.
    """
    if text == "":
        return 0
    return text.count("\n") + 1


# -- Core ----------------------------------------------------------------------

def _normalise(text):
    """Normalise line endings to LF. Required for stable SHA256."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _sha256(body):
    """SHA256 of body text encoded as UTF-8."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _make_header(body, meta):
    """
    Build the archivist header block for the given body and metadata dict.
    Returns a list of lines (without trailing newline on each).
    """
    char_count = len(body)
    line_count = _line_count(body)
    digest     = _sha256(body)

    lines = []

    def field(key, value):
        value = _to_text(value)
        if value is not None and value.strip():
            lines.append(u"{}{:<10}  {}".format(FIELD_PREFIX, key, value))

    field(MARKER_FIELD,  "v{}".format(__version__))
    field("TITLE",        meta.get("title"))
    field("AUTHOR",       meta.get("author"))
    field("LANG",         meta.get("lang"))
    field("SOURCE",       meta.get("source"))
    if not meta.get("no_date"):
        field("DATE",     time.strftime("%Y-%m-%d"))
    field("TAGS",         meta.get("tags"))
    field("TLP",          meta.get("tlp"))
    field("NOTE",         meta.get("note"))
    field("CHARS",        "{:,}".format(char_count))
    field("LINES",        "{:,}".format(line_count))
    field(SHA256_FIELD,   digest)

    return lines


def stamp(body, meta):
    """
    Wrap body in an archivist header. Returns the complete stamped document
    as a unicode string, ready to write to file or stdout.

    Line endings are normalised to LF and trailing newlines stripped before
    hashing. Strip output always ends with exactly one newline. This is a
    canonical-text round-trip, not byte-for-byte preservation.
    """
    body   = _normalise(body).rstrip("\n")
    header = _make_header(body, meta)
    return "\n".join(header) + "\n\n" + body + "\n"


def parse(text):
    """
    Parse a stamped document. Returns:
        {
            "header_lines": [...],   # raw header lines (with "# " prefix)
            "fields":       {...},   # parsed key: value pairs
            "body":         str,     # document body
            "sha256_declared": str,
            "sha256_actual":   str,
            "sha256_ok":       bool,
            "is_stamped":      bool,
            "char_count":      int,
            "line_count":      int,
        }
    """
    text  = _normalise(text)

    # Gate on the first non-empty line: must be "# ARCHIVIST ..." or we treat
    # the whole document as an unstamped body immediately.
    first_content = next((l for l in text.splitlines() if l.strip()), "")
    if not first_content.startswith(HEADER_MARKER):
        body = text.rstrip("\n")
        return {
            "header_lines":    [],
            "fields":          {},
            "body":            body,
            "sha256_declared": None,
            "sha256_actual":   _sha256(body),
            "sha256_ok":       False,
            "is_stamped":      False,
            "char_count":      len(body),
            "line_count":      _line_count(body),
        }

    # Split header block from body on the first blank-line separator (\n\n).
    # This operates directly on the normalised string, so there is no offset
    # reconstruction or splitlines() structural ambiguity.
    if "\n\n" in text:
        header_text, body_text = text.split("\n\n", 1)
    else:
        header_text, body_text = text, ""

    header_lines = header_text.split("\n")

    # Known field names -- used to restrict the legacy colon-separator fallback
    # so that malformed lines with arbitrary colons are not over-interpreted.
    _KNOWN_FIELDS = {
        MARKER_FIELD, "TITLE", "AUTHOR", "LANG", "SOURCE",
        "DATE", "TAGS", "TLP", "NOTE", "CHARS", "LINES", SHA256_FIELD,
    }

    fields = {}
    for line in header_lines:
        if line.startswith(FIELD_PREFIX):
            rest = line[len(FIELD_PREFIX):]
            if "  " in rest:
                key, _, val = rest.partition("  ")
                fields[key.strip()] = val.strip()
            elif ":" in rest:
                # Legacy colon separator -- restricted to known fields only so
                # that arbitrary colons in free-form lines are not misread.
                key, _, val = rest.partition(":")
                key = key.strip()
                if key in _KNOWN_FIELDS:
                    fields[key] = val.strip()

    # is_stamped: the first-line gate guarantees HEADER_MARKER is present;
    # additionally require SHA256 so a truncated/damaged header is flagged
    # rather than silently verified against an absent digest.
    is_stamped = (
        len(header_lines) > 0 and
        header_lines[0].startswith(HEADER_MARKER) and
        SHA256_FIELD in fields
    )

    body             = body_text.rstrip("\n")
    sha256_declared  = fields.get(SHA256_FIELD)
    sha256_actual    = _sha256(body)

    return {
        "header_lines":    header_lines,
        "fields":          fields,
        "body":            body,
        "sha256_declared": sha256_declared,
        "sha256_actual":   sha256_actual,
        "sha256_ok":       sha256_actual == sha256_declared,
        "is_stamped":      is_stamped,
        "char_count":      len(body),
        "line_count":      _line_count(body),
    }


# -- I/O -----------------------------------------------------------------------

def _read(path_or_dash):
    """Read text (unicode) from a file path or '-' for stdin."""
    if path_or_dash == "-" or path_or_dash is None:
        if PY2:
            data = sys.stdin.read()
            if not isinstance(data, text_type):
                data = data.decode("utf-8", "replace")
            return data
        # Python 3: read raw bytes and decode explicitly -- do not rely on locale
        return sys.stdin.buffer.read().decode("utf-8", "replace")
    with io.open(path_or_dash, "r", encoding="utf-8") as f:
        return f.read()


def _stdout_write_utf8(text):
    """
    Write unicode text to stdout as UTF-8 bytes, regardless of locale.
    Uses the binary buffer when available (Python 3 and some Python 2
    wrappers); falls back to writing raw bytes on plain Python 2 stdout.
    Centralising all stdout encoding here removes text/bytes ambiguity
    across runtimes, redirections, and test harnesses.
    """
    data   = text.encode("utf-8")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(data)
    else:
        # Python 2: sys.stdout accepts bytes directly
        sys.stdout.write(data)


def _write(text, path):
    """Write unicode text to a file path, or to stdout if path is None."""
    if path is None:
        _stdout_write_utf8(text)
    else:
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def _label(path_or_dash):
    if path_or_dash == "-" or path_or_dash is None:
        return "<stdin>"
    return path_or_dash


# -- CLI commands --------------------------------------------------------------

def cmd_stamp(args):
    src  = args.file if args.file else "-"
    body = _read(src)

    meta = {
        "title":   args.title,
        "author":  args.author,
        "lang":    args.lang,
        "source":  args.source,
        "note":    args.note,
        "tags":    args.tags,
        "tlp":     args.tlp,
        "no_date": args.no_date,
    }

    result = stamp(body, meta)
    _write(result, args.output)

    # Confirmation to stderr (does not contaminate piped output)
    parsed = parse(result)
    print("Stamped: {} chars  SHA256: {}...".format(
        parsed["char_count"], parsed["sha256_actual"][:16]),
        file=sys.stderr)
    return 0


def cmd_verify(args):
    sources = args.files if args.files else ["-"]
    passed = failed = unstamped = 0

    for src in sources:
        label = _label(src)
        try:
            text   = _read(src)
            parsed = parse(text)
        except (IOError, OSError) as err:
            print("  ERROR  {}  - {}".format(label, err), file=sys.stderr)
            failed += 1
            continue

        if not parsed["is_stamped"]:
            print("  SKIP   {}  - no archivist header".format(label))
            unstamped += 1
            continue

        if parsed["sha256_ok"]:
            title = parsed["fields"].get("TITLE", "")
            print("  PASS   {}  {}  ({:,} chars)".format(
                label,
                ("- " + title) if title else "",
                parsed["char_count"]))
            passed += 1
        else:
            print("  FAIL   {}  - SHA256 mismatch".format(label))
            print("         declared: {}".format(parsed["sha256_declared"]))
            print("         actual:   {}".format(parsed["sha256_actual"]))
            failed += 1

    if len(sources) > 1:
        print()
        print("Results: {} passed, {} failed, {} unstamped".format(
            passed, failed, unstamped))

    return 0 if failed == 0 else 1


def cmd_show(args):
    sources   = args.files if args.files else ["-"]
    had_error = False

    for src in sources:
        label = _label(src)
        try:
            text   = _read(src)
            parsed = parse(text)
        except (IOError, OSError) as err:
            print("  ERROR  {}  - {}".format(label, err), file=sys.stderr)
            had_error = True
            continue

        if not parsed["is_stamped"]:
            print("{}: no archivist header".format(label))
            continue

        if len(sources) > 1:
            print("--- {} ---".format(label))

        f = parsed["fields"]
        for key in [MARKER_FIELD, "TITLE", "AUTHOR", "LANG", "SOURCE",
                    "DATE", "TAGS", "TLP", "NOTE", "CHARS", "LINES",
                    SHA256_FIELD]:
            if key in f:
                print("  {:<10}  {}".format(key, f[key]))

        # Any extra unknown fields
        known = {MARKER_FIELD, "TITLE", "AUTHOR", "LANG", "SOURCE",
                 "DATE", "TAGS", "TLP", "NOTE", "CHARS", "LINES",
                 SHA256_FIELD}
        for key, val in f.items():
            if key not in known:
                print("  {:<10}  {}".format(key, val))

        # show computes and reports verification status
        status = "OK" if parsed["sha256_ok"] else "MISMATCH"
        print("  {:<10}  {}".format("STATUS", status))

        if len(sources) > 1:
            print()

    return 1 if had_error else 0


def cmd_strip(args):
    sources = args.files if args.files else ["-"]

    if args.output and len(sources) > 1:
        print("Error: --output cannot be used with multiple files.",
              file=sys.stderr)
        return 1

    for src in sources:
        try:
            text   = _read(src)
            parsed = parse(text)
        except (IOError, OSError) as err:
            print("Error: {}".format(err), file=sys.stderr)
            return 1

        if not parsed["is_stamped"]:
            # Not stamped -- pass through as normalised text (not byte-for-byte)
            _write(text, args.output)
        else:
            _write(parsed["body"] + "\n", args.output)

        if args.output:
            print("Stripped: {:,} chars written to {}".format(
                parsed["char_count"], args.output), file=sys.stderr)

    return 0


# -- CLI parser ----------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="archivist",
        description=(
            "Self-describing document framing tool.\n"
            "\n"
            "Stamps plain text documents with SHA256, metadata, and\n"
            "provenance. Verifies integrity on demand. Strips the header\n"
            "to recover the normalised body.\n"
            "\n"
            "The archivist doesn't care what your document contains.\n"
            "It will stamp it, hash it, and file it. It will also tell\n"
            "you, quietly and without drama, if someone has tampered\n"
            "with it since.\n"
            "\n"
            "Note: provides content integrity checking only, not\n"
            "cryptographic authenticity or non-repudiation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python archivist.py stamp --title 'Signal Survives' \\\n"
            "      --author 'T. Darley' document.txt\n"
            "\n"
            "  echo 'All human beings are born free.' | \\\n"
            "      python archivist.py stamp --title 'UDHR Article 1' -\n"
            "\n"
            "  python archivist.py verify docs/udhr/*.txt\n"
            "\n"
            "  python archivist.py strip stamped.txt | less\n"
            "\n"
            "  python archivist.py stamp - | python archivist.py verify -\n"
        )
    )

    sub = p.add_subparsers(dest="command")
    # sub.required is unreliable on Python 2.7; main() handles missing command.

    # -- stamp -----------------------------------------------------------------
    ps = sub.add_parser("stamp",
        help="stamp a document with SHA256 and metadata",
        description="Wrap a document in a self-describing archivist header.")
    ps.add_argument("file", nargs="?", default="-",
        help="input file (default: stdin, use - explicitly for stdin)")
    ps.add_argument("-t", "--title",  metavar="TITLE",  default=None)
    ps.add_argument("-a", "--author", metavar="AUTHOR", default=None)
    ps.add_argument("-s", "--source", metavar="SOURCE", default=None,
        help="URL or bibliographic reference")
    ps.add_argument("-n", "--note",   metavar="NOTE",   default=None)
    ps.add_argument("-l", "--lang",   metavar="LANG",   default=None,
        help="language / script (e.g. en, ar, zh-Hans)")
    ps.add_argument("-T", "--tags",   metavar="TAGS",   default=None,
        help="comma-separated tags")
    ps.add_argument("--tlp",          metavar="LEVEL",  default=None,
        choices=["CLEAR", "GREEN", "AMBER", "AMBER+STRICT", "RED"],
        help="TLP classification")
    ps.add_argument("-o", "--output", metavar="FILE",   default=None,
        help="output file (default: stdout)")
    ps.add_argument("--no-date", action="store_true",
        help="omit stamp date field (for reproducible output)")
    ps.set_defaults(func=cmd_stamp)

    # -- verify ----------------------------------------------------------------
    pv = sub.add_parser("verify",
        help="verify SHA256 of one or more stamped documents",
        description="Verify the SHA256 of stamped documents.")
    pv.add_argument("files", nargs="*", default=["-"],
        help="files to verify (default: stdin)")
    pv.set_defaults(func=cmd_verify)

    # -- show ------------------------------------------------------------------
    ph = sub.add_parser("show",
        help="show metadata and verification status from a stamped document",
        description=(
            "Display the archivist header fields and verification status.\n"
            "Note: show computes and reports the SHA256 status."))
    ph.add_argument("files", nargs="*", default=["-"],
        help="files to inspect (default: stdin)")
    ph.set_defaults(func=cmd_show)

    # -- strip -----------------------------------------------------------------
    px = sub.add_parser("strip",
        help="remove the archivist header, recover normalised body",
        description=(
            "Strip the archivist header. Output is the normalised body.\n"
            "Unstamped files are passed through as normalised text\n"
            "(LF line endings, UTF-8). Not a byte-for-byte passthrough."))
    px.add_argument("files", nargs="*", default=["-"],
        help="files to strip (default: stdin)")
    px.add_argument("-o", "--output", metavar="FILE", default=None,
        help="output file (default: stdout)")
    px.set_defaults(func=cmd_strip)

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {}".format(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
