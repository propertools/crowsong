#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
archivist.py — Self-describing document framing tool

Wraps any plain text document in a self-describing header block
containing SHA256, metadata, and provenance. The result is a single
plain-text file that carries its own verification credentials.

The archivist doesn't care what your document contains. It will stamp
it, hash it, and file it. It will also tell you, quietly and without
drama, if someone has tampered with it since.

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
    -l, --lang LANG         Language / script (default: en)
    -T, --tags TAG[,TAG]    Comma-separated tags
    -o, --output FILE       Output file (default: stdout)
    --tlp LEVEL             TLP classification (CLEAR/GREEN/AMBER/RED)
    --no-date               Omit fetch date (for reproducible output)

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

    # Show metadata without verifying
    python archivist.py show docs/udhr/ara.txt

    # Strip the archivist header, recover the original body
    python archivist.py strip docs/udhr/ara.txt

    # Round-trip: stamp then verify
    echo "All human beings are born free." | \\
        python archivist.py stamp --title "UDHR Article 1" | \\
        python archivist.py verify -

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

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
    open      = io.open
else:
    text_type = str

__version__ = "1.0"

# ── Header format ─────────────────────────────────────────────────────────────
#
# The archivist header is a block of lines beginning with "# ".
# It is terminated by a blank line, after which the document body begins.
# The SHA256 is computed over the body only, after CRLF normalisation.
# This matches the format used by tools/texts/texts.py and tools/udhr/udhr.py.
#
# Fields:
#   ARCHIVIST   version marker — identifies this format
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
# Unknown fields are preserved by verify/show/strip.

HEADER_MARKER   = "# ARCHIVIST"
BODY_SEPARATOR  = ""  # blank line between header and body
FIELD_PREFIX    = "# "
SHA256_FIELD    = "SHA256"
VERSION_FIELD   = "ARCHIVIST"


# ── Core ──────────────────────────────────────────────────────────────────────

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
    line_count = body.count("\n")
    digest     = _sha256(body)

    lines = []

    def field(key, value):
        if value is not None and str(value).strip():
            lines.append("{}{:<10}  {}".format(FIELD_PREFIX, key, value))

    field(VERSION_FIELD,  "v{}".format(__version__))
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
    as a string, ready to write to file or stdout.
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
        }
    """
    text   = _normalise(text)
    lines  = text.splitlines()

    # Find where the header ends (first non-"# " line after at least one "# " line)
    header_lines = []
    body_start   = 0
    in_header    = False

    for i, line in enumerate(lines):
        if line.startswith(FIELD_PREFIX) or line == "#":
            header_lines.append(line)
            in_header = True
        elif in_header:
            # First non-header line — skip blank lines used as separator
            body_start = i
            while body_start < len(lines) and lines[body_start].strip() == "":
                body_start += 1
            break

    is_stamped = any(VERSION_FIELD in l for l in header_lines)

    # Parse fields
    fields = {}
    for line in header_lines:
        if line.startswith(FIELD_PREFIX):
            rest = line[len(FIELD_PREFIX):]
            if "  " in rest:
                key, _, val = rest.partition("  ")
                fields[key.strip()] = val.strip()
            elif ":" in rest:
                # Legacy single-space or colon separator
                key, _, val = rest.partition(":")
                fields[key.strip()] = val.strip()

    body             = "\n".join(lines[body_start:]).rstrip("\n")
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
        "line_count":      body.count("\n"),
    }


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read(path_or_dash):
    """Read text from a file path or '-' for stdin."""
    if path_or_dash == "-" or path_or_dash is None:
        if PY2:
            data = sys.stdin.read()
            if not isinstance(data, text_type):
                data = data.decode("utf-8", errors="replace")
            return data
        return sys.stdin.read()
    with open(path_or_dash, "r", encoding="utf-8") as f:
        return f.read()


def _write(text, path):
    """Write text to a file path or stdout if path is None."""
    if path is None:
        if PY2:
            if isinstance(text, text_type):
                sys.stdout.write(text.encode("utf-8"))
            else:
                sys.stdout.write(text)
        else:
            sys.stdout.write(text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def _label(path_or_dash):
    if path_or_dash == "-" or path_or_dash is None:
        return "<stdin>"
    return path_or_dash


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_stamp(args):
    src  = args.file if args.file else "-"
    body = _read(src)

    if not body.strip():
        print("Error: empty input.", file=sys.stderr)
        return 1

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

    # Confirmation to stderr (so it doesn't contaminate piped output)
    parsed = parse(result)
    print("Stamped: {} chars  SHA256: {}".format(
        parsed["char_count"], parsed["sha256_actual"][:16] + "..."),
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
            print("  ERROR  {}  — {}".format(label, err))
            failed += 1
            continue

        if not parsed["is_stamped"]:
            print("  SKIP   {}  — no archivist header".format(label))
            unstamped += 1
            continue

        if parsed["sha256_ok"]:
            title = parsed["fields"].get("TITLE", "")
            print("  PASS   {}  {}  ({:,} chars)".format(
                label,
                ("— " + title) if title else "",
                parsed["char_count"]))
            passed += 1
        else:
            print("  FAIL   {}  — SHA256 mismatch".format(label))
            print("         declared: {}".format(parsed["sha256_declared"]))
            print("         actual:   {}".format(parsed["sha256_actual"]))
            failed += 1

    if len(sources) > 1:
        print()
        print("Results: {} passed, {} failed, {} unstamped".format(
            passed, failed, unstamped))

    return 0 if failed == 0 else 1


def cmd_show(args):
    sources = args.files if args.files else ["-"]

    for src in sources:
        label  = _label(src)
        text   = _read(src)
        parsed = parse(text)

        if not parsed["is_stamped"]:
            print("{}: no archivist header".format(label))
            continue

        if len(sources) > 1:
            print("─── {} ───".format(label))

        f = parsed["fields"]
        for key in [VERSION_FIELD, "TITLE", "AUTHOR", "LANG", "SOURCE",
                    "DATE", "TAGS", "TLP", "NOTE", "CHARS", "LINES",
                    SHA256_FIELD]:
            if key in f:
                print("  {:<10}  {}".format(key, f[key]))

        # Any extra unknown fields
        known = {VERSION_FIELD, "TITLE", "AUTHOR", "LANG", "SOURCE",
                 "DATE", "TAGS", "TLP", "NOTE", "CHARS", "LINES",
                 SHA256_FIELD}
        for key, val in f.items():
            if key not in known:
                print("  {:<10}  {}".format(key, val))

        status = "✓ verified" if parsed["sha256_ok"] else "✗ MISMATCH"
        print("  {:<10}  {}".format("STATUS", status))

        if len(sources) > 1:
            print()

    return 0


def cmd_strip(args):
    sources = args.files if args.files else ["-"]

    for src in sources:
        text   = _read(src)
        parsed = parse(text)

        if args.output and len(sources) > 1:
            print("Error: --output cannot be used with multiple files.",
                  file=sys.stderr)
            return 1

        if not parsed["is_stamped"]:
            # Not stamped — pass through unchanged
            _write(text, args.output)
        else:
            _write(parsed["body"] + "\n", args.output)

        if args.output:
            print("Stripped: {:,} chars written to {}".format(
                parsed["char_count"], args.output), file=sys.stderr)

    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="archivist",
        description=(
            "Self-describing document framing tool.\n"
            "\n"
            "Stamps plain text documents with SHA256, metadata, and\n"
            "provenance. Verifies integrity on demand. Strips the header\n"
            "to recover the original body.\n"
            "\n"
            "The archivist doesn't care what your document contains.\n"
            "It will stamp it, hash it, and file it. It will also tell\n"
            "you, quietly and without drama, if someone has tampered\n"
            "with it since."
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
    sub.required = True

    # ── stamp ─────────────────────────────────────────────────────────────────
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
        help="omit date field (for reproducible output)")

    # ── verify ────────────────────────────────────────────────────────────────
    pv = sub.add_parser("verify",
        help="verify SHA256 of one or more stamped documents",
        description="Verify the SHA256 of stamped documents.")
    pv.add_argument("files", nargs="*", default=["-"],
        help="files to verify (default: stdin)")

    # ── show ──────────────────────────────────────────────────────────────────
    ph = sub.add_parser("show",
        help="show metadata from a stamped document",
        description="Display the archivist header fields without verifying.")
    ph.add_argument("files", nargs="*", default=["-"],
        help="files to inspect (default: stdin)")

    # ── strip ─────────────────────────────────────────────────────────────────
    px = sub.add_parser("strip",
        help="remove the archivist header, recover original body",
        description="Strip the archivist header. Output is the original body.")
    px.add_argument("files", nargs="*", default=["-"],
        help="files to strip (default: stdin)")
    px.add_argument("-o", "--output", metavar="FILE", default=None,
        help="output file (default: stdout)")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "stamp":  return cmd_stamp(args)
        if args.command == "verify": return cmd_verify(args)
        if args.command == "show":   return cmd_show(args)
        if args.command == "strip":  return cmd_strip(args)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {}".format(err), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
