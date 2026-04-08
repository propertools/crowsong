#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
crowsong-review.py — AI code review preparation tool

Recursively walks a path, concatenating target files into a single text
block prefixed by the Crowsong code review prompt. Output is designed
for pasting directly into an AI code review session.

Usage:
    python crowsong-review.py <path> [--ext .py .md .sh ...]
    python crowsong-review.py tools/haiku/
    python crowsong-review.py tools/wordfreq/ --ext .py
    python crowsong-review.py . --ext .py .sh .md --exclude __pycache__ .git
    python crowsong-review.py --prompt-only

Options:
    path            File or directory to review
    --ext           File extensions to include
                    (default: .py .sh .md .txt)
    --exclude       File or directory patterns to skip
                    (default: __pycache__ .git .mypy_cache .tox
                    node_modules .eggs dist build *.pyc *.pyo *.egg-info)
    --no-prompt     Omit the review prompt (output files only)
    --prompt-only   Print the review prompt and exit
    --dry-run       Print file list and char count without concatenating
    --max-kb N      Skip files larger than N KB (default: 500)
    -h, --help      Show this help

Output is written to stdout. Pipe to pbcopy (macOS), xclip (Linux),
or redirect to a file.

Examples:
    # Review haiku toolkit — copy to clipboard (macOS)
    python tools/review/crowsong-review.py tools/haiku/ | pbcopy

    # Check what would be included before copying
    python tools/review/crowsong-review.py tools/ --dry-run

    # Review everything Python in mnemonic tools
    python tools/review/crowsong-review.py tools/mnemonic/ --ext .py | pbcopy

    # Review a single file
    python tools/review/crowsong-review.py tools/haiku/haiku_grammar.py | pbcopy

    # Just the prompt
    python tools/review/crowsong-review.py --prompt-only

    # Save to file for later
    python tools/review/crowsong-review.py tools/ --ext .py > /tmp/review.txt

Compatibility:
    Python 2.7+ / 3.x

Dependencies:
    None

Author:
    Proper Tools SRL

License:
    MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import fnmatch
import io
import os
import sys

PY2 = (sys.version_info[0] == 2)
if PY2:
    range = xrange  # noqa: F821


# ── Review prompt ────────────────────────────────────────────────────────────

REVIEW_PROMPT = """
# Crowsong Suite — AI Code Review

You are reviewing a contribution to the Crowsong protocol suite
(github.com/propertools/crowsong). Please conduct a rigorous code
and documentation review covering all of the following dimensions.

-----

## About the Crowsong codebase

Crowsong is a signal survival protocol suite. It implements:

- UCS-DEC encoding (Unicode code points as zero-padded decimal integers)
- Channel Camouflage Layer (CCL) — prime-driven base-switching
- Word-space camouflage — haiku as encoded token stream
- Mnemonic key derivation (verse -> prime via SHA256 -> next_prime)
- Mathematical corpus tools (constants, sequences, primes)
- UDHR corpus mirror for cross-script entropy testing

Design constraints that matter for review:

- Python 2.7+ AND 3.x compatibility throughout (hard requirement)
- No external dependencies except where explicitly justified
- All file I/O via io.open() with explicit encoding (not open())
- Artifacts are self-describing plain text with RSRC blocks
- Tools composable via stdin/stdout pipelines
- CCL provides NO cryptographic confidentiality — never claim otherwise

-----

## Review dimensions

### 1. Correctness

- Logic bugs, off-by-one errors, incorrect algorithm implementation
- Edge cases: empty input, single token, maximum values, Unicode
  boundary conditions, non-ASCII input where ASCII is assumed
- Round-trip integrity: does encode -> decode recover the original exactly?
- CRC32 and SHA256 computations — are they applied to the right data,
  in the right encoding, at the right point in the pipeline?

### 2. Python 2.7 / 3.x compatibility

- All string literals that carry Unicode must be u"..." or
  from __future__ import unicode_literals
- Use io.open() everywhere, never bare open() for text files
- Integer division: use // not / where integer result is required
- print() must be a function (from __future__ import print_function)
- range() vs xrange() — use the PY2 compatibility pattern
- urllib: check that PY2/PY3 import paths are both handled
- Exception syntax: except Exception as e, not except Exception, e
- Division of large integers behaves differently in PY2 vs PY3

### 3. Security considerations

- No hardcoded secrets, keys, or verses
- Token injection / prompt injection surface: does this tool process
  untrusted input that could contain instruction-space content?
  Does it maintain separation between data and instruction registers?
- Shannon entropy claims: are they accurate and properly caveated?
- CCL layer: is it clearly documented as non-cryptographic?
  Does any code path accidentally imply confidentiality guarantees?
- DESTROY semantics: are they correctly triggered on verification failure?
- Resource fork / data fork separation: is the Von Neumann boundary
  respected in any artifact parsing code?

### 4. Pipeline composability

- Does the tool correctly read from stdin and write to stdout?
- Are error messages written to stderr, not stdout?
- Does the tool handle being in the middle of a pipeline gracefully?
  (stdin not a tty, stdout piped to another process)
- Are exit codes correct? (0 = success, 1 = failure, consistently)
- Does --help work without side effects?

### 5. Artifact format compliance

- RSRC blocks: are all required fields present and correctly formatted?
- VERSION field declared?
- TYPE field correctly identifies the artifact type?
- CRC32 computed over the correct data (encoded payload, not raw)?
- DESTROY / VERIFY COUNT BEFORE USE semantics present where required?
- Are archivist headers (SHA256, source, date) present in corpus files?

### 6. Crowsong conventions

- Tool follows the dual-schedule pattern where applicable:
  forward digits of P -> one schedule
  reversed digits of P -> independent schedule
- next_prime() and is_prime() imported from mnemonic.py, not reimplemented
- Word lists sorted alphabetically for determinism
- Fisher-Yates permutations seeded from SHA256(key), not random()
- Haiku syllable counts sum to [5, 7, 5] per template
- POS tag fallback chain defined and tested

### 7. README and documentation quality

- Does the README accurately describe what the tool does?
- Are all subcommands documented with examples?
- Are the examples actually correct and runnable?
- Is the connection to the broader Crowsong stack explained?
- Are dependencies (both required and optional) clearly stated?
- Is the Python version compatibility noted?
- Are corpus file licenses correctly attributed?
- Does the README explain what the tool does NOT do
  (e.g., CCL does not provide cryptographic confidentiality)?

### 8. Test coverage and verifiability

- Is there a canonical test vector that can be run to verify the tool?
- Can the output be reproduced deterministically from the same inputs?
- Are there known-good expected outputs committed to archive/?
- Is the round-trip (encode -> decode) verifiable from the CLI?

### 9. Style and maintainability

- Function and variable names consistent with the rest of the codebase?
- Docstrings present on public functions?
- No dead code, commented-out blocks, or TODO without a ticket?
- Magic numbers explained or named?
- Error messages actionable — do they tell the user what to do next?

-----

## What to produce

For each issue found, provide:

- **File and line number** (approximate is fine)
- **Severity**: critical / high / medium / low / nit
- **Description**: what is wrong and why it matters
- **Fix**: concrete suggestion or corrected code

At the end, provide:

- **Summary**: overall assessment, what works well, what needs attention
- **Blocking issues**: anything that must be fixed before merge
- **Suggested ISSUE-TRACKER entries**: for non-blocking issues worth tracking

Be rigorous. The people who depend on this code may be operating in
adversarial environments with degraded infrastructure. Correctness matters.

-----

## Files for review
""".strip()


# ── File collection ──────────────────────────────────────────────────────────

DEFAULT_EXTENSIONS = [".py", ".sh", ".md", ".txt"]
DEFAULT_EXCLUDE = [
    "__pycache__", ".git", ".mypy_cache", ".tox",
    "node_modules", ".eggs", "dist", "build",
    "*.pyc", "*.pyo", "*.egg-info",
]
DEFAULT_MAX_KB = 500

SEPARATOR = "-" * 72


def _matches_any(path_fragment, patterns):
    """
    Return True if path_fragment or its basename matches any pattern.
    Supports exact names and shell-style globs.
    """
    basename = os.path.basename(path_fragment)
    for pat in patterns:
        if (
            fnmatch.fnmatch(path_fragment, pat) or
            fnmatch.fnmatch(basename, pat) or
            path_fragment == pat or
            basename == pat
        ):
            return True
    return False


def _normalise_extensions(exts):
    """Normalise a list of extensions to lowercase dotted form."""
    results = []
    for ext in exts:
        ext = ext.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        results.append(ext.lower())
    return results


def _should_include_file(fpath, extensions, exclude_patterns, max_kb):
    """
    Return (include_bool, reason_string) for a candidate file.
    reason_string is None on inclusion, or one of:
      'excluded', 'extension', 'stat', 'size'
    """
    basename = os.path.basename(fpath)

    if _matches_any(fpath, exclude_patterns) or _matches_any(basename, exclude_patterns):
        return False, "excluded"

    _, ext = os.path.splitext(basename)
    if ext.lower() not in extensions:
        return False, "extension"

    try:
        size_kb = os.path.getsize(fpath) / 1024.0
    except OSError:
        return False, "stat"

    if size_kb > max_kb:
        return False, "size"

    return True, None


def collect_files(path, extensions, exclude_patterns, max_kb):
    """
    Recursively collect files matching extensions under path.
    Returns a sorted list of absolute file paths.
    """
    path = os.path.abspath(path)
    results = []

    if os.path.isfile(path):
        ok, reason = _should_include_file(path, extensions, exclude_patterns, max_kb)
        if ok:
            return [path]
        if reason == "size":
            print("# SKIPPED (>{0}KB): {1}".format(max_kb, path), file=sys.stderr)
        return []

    for root, dirs, files in os.walk(path):
        dirs[:] = sorted([
            d for d in dirs
            if not _matches_any(d, exclude_patterns)
            and not _matches_any(os.path.join(root, d), exclude_patterns)
        ])

        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            ok, reason = _should_include_file(fpath, extensions, exclude_patterns, max_kb)
            if not ok:
                if reason == "size":
                    print("# SKIPPED (>{0}KB): {1}".format(max_kb, fpath),
                          file=sys.stderr)
                continue
            results.append(fpath)

    return sorted(results)


def read_file(fpath):
    """Read a file as UTF-8 text, replacing decode errors."""
    try:
        with io.open(fpath, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except (IOError, OSError) as exc:
        return "# ERROR READING FILE: {0}\n".format(exc)


def format_file_block(fpath, base_path, content):
    """Format one file as a labelled review block."""
    try:
        relpath = os.path.relpath(fpath, base_path)
    except ValueError:
        relpath = fpath

    return "\n".join([
        relpath,
        SEPARATOR,
        content.rstrip(),
        SEPARATOR,
        "",
    ])


def write_stdout(text):
    """Write Unicode text safely to stdout on Python 2 and 3."""
    if PY2:
        sys.stdout.write(text.encode("utf-8"))
        sys.stdout.write(b"\n")
    else:
        sys.stdout.write(text)
        sys.stdout.write("\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="crowsong-review",
        description=(
            "Prepare files for AI code review.\n\n"
            "Concatenate target files with the Crowsong review prompt,\n"
            "ready for pasting into an AI code review session.\n\n"
            "Output to stdout. Pipe to pbcopy (macOS) or xclip (Linux)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python crowsong-review.py tools/haiku/ | pbcopy\n"
            "  python crowsong-review.py tools/ --dry-run\n"
            "  python crowsong-review.py tools/mnemonic/ --ext .py | pbcopy\n"
            "  python crowsong-review.py tools/haiku/haiku_grammar.py | pbcopy\n"
            "  python crowsong-review.py --prompt-only\n"
        ),
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="file or directory to review (default: current directory)",
    )
    parser.add_argument(
        "--ext",
        nargs="+",
        default=DEFAULT_EXTENSIONS,
        metavar="EXT",
        help="file extensions to include (default: {0})".format(
            " ".join(DEFAULT_EXTENSIONS)
        ),
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=DEFAULT_EXCLUDE,
        metavar="PAT",
        help="directory/file patterns to exclude",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="omit the review prompt; output files only",
    )
    parser.add_argument(
        "--prompt-only",
        action="store_true",
        help="print the review prompt and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print file list and estimated char count without concatenating",
    )
    parser.add_argument(
        "--max-kb",
        type=int,
        default=DEFAULT_MAX_KB,
        metavar="N",
        help="skip files larger than N KB (default: {0})".format(DEFAULT_MAX_KB),
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    extensions = _normalise_extensions(args.ext)

    if args.prompt_only:
        write_stdout(REVIEW_PROMPT)
        return 0

    path = args.path or "."
    files = collect_files(
        path=path,
        extensions=extensions,
        exclude_patterns=args.exclude,
        max_kb=args.max_kb,
    )

    if not files:
        print(
            "No files found matching {0} under {1}".format(extensions, path),
            file=sys.stderr,
        )
        return 1

    abs_path = os.path.abspath(path)
    base_path = abs_path if os.path.isdir(abs_path) else (
        os.path.dirname(abs_path) or os.getcwd())

    # Dry run — print manifest only
    if args.dry_run:
        total_bytes = 0
        print("Files that would be included ({0}):".format(len(files)))
        print("")
        for fpath in files:
            try:
                relpath = os.path.relpath(fpath, base_path)
            except ValueError:
                relpath = fpath
            size_kb = os.path.getsize(fpath) / 1024.0
            total_bytes += os.path.getsize(fpath)
            print("  {0:<60} {1:.1f}KB".format(relpath, size_kb))
        print("")
        prompt_chars = len(REVIEW_PROMPT) if not args.no_prompt else 0
        estimated = total_bytes + prompt_chars
        print("Estimated output: ~{0:,} chars across {1} file(s)".format(
            estimated, len(files)))
        print("(Run without --dry-run to generate and pipe to pbcopy)")
        return 0

    # Full run
    parts = []

    if not args.no_prompt:
        parts.append(REVIEW_PROMPT)
        parts.append("")
        parts.append("**{0} file(s) for review:**".format(len(files)))
        parts.append("")
        for fpath in files:
            try:
                relpath = os.path.relpath(fpath, base_path)
            except ValueError:
                relpath = fpath
            parts.append("- {0}".format(relpath))
        parts.append("")
        parts.append("=" * 72)
        parts.append("")

    for fpath in files:
        content = read_file(fpath)
        parts.append(format_file_block(fpath, base_path, content))

    output = "\n".join(parts)
    write_stdout(output)

    print(
        "{0} file(s) concatenated ({1:,} chars)".format(len(files), len(output)),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
