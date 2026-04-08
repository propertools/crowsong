#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
crowsong-speccheck.py — Standards and specification review preparation tool

Collects reference implementation code and draft specifications, assembles
a review buffer that puts the recipient AI in the role of an expert
standards reviewer. The reviewer tightens specifications to more elegantly
and exactly express what is actually happening in the code, and identifies
where supporting documentation or illustrative graphics would facilitate
better independent implementations.

Usage:
    python crowsong-speccheck.py [--code PATH] [--drafts PATH]
    python crowsong-speccheck.py --code tools/mnemonic/ --drafts drafts/
    python crowsong-speccheck.py --code tools/ --drafts drafts/ --ext-code .py
    python crowsong-speccheck.py --prompt-only
    python crowsong-speccheck.py --dry-run

Options:
    --code PATH       Path to reference implementation (default: tools/)
    --drafts PATH     Path to draft specifications (default: drafts/)
    --ext-code        Code file extensions (default: .py .sh)
    --ext-drafts      Draft file extensions (default: .txt .md)
    --exclude         File or directory patterns to skip
                      (default: __pycache__ .git .mypy_cache .tox
                      node_modules .eggs dist build *.pyc *.pyo *.egg-info)
    --no-prompt       Omit the review prompt (output files only)
    --prompt-only     Print the review prompt and exit
    --dry-run         Print file list and estimated char count without
                      concatenating
    --max-kb N        Skip files larger than N KB (default: 500)
    -h, --help        Show this help

Output is written to stdout. Pipe to pbcopy (macOS), xclip (Linux),
or redirect to a file.

Examples:
    # Full spec review — copy to clipboard (macOS)
    python tools/review/crowsong-speccheck.py | pbcopy

    # Review CCL spec against mnemonic tools only
    python tools/review/crowsong-speccheck.py \\
        --code tools/mnemonic/ \\
        --drafts drafts/ \\
        | pbcopy

    # Check scope before copying
    python tools/review/crowsong-speccheck.py --dry-run

    # Just the prompt
    python tools/review/crowsong-speccheck.py --prompt-only

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

DEFAULT_CODE_PATH    = "tools"
DEFAULT_DRAFTS_PATH  = "drafts"
DEFAULT_EXT_CODE     = [".py", ".sh"]
DEFAULT_EXT_DRAFTS   = [".txt", ".md"]
DEFAULT_EXCLUDE      = [
    "__pycache__", ".git", ".mypy_cache", ".tox",
    "node_modules", ".eggs", "dist", "build",
    "*.pyc", "*.pyo", "*.egg-info",
]
DEFAULT_MAX_KB = 500

SEPARATOR     = "-" * 72
MAJOR_SEP     = "=" * 72


# ── Review prompt ─────────────────────────────────────────────────────────────

REVIEW_PROMPT = """
# Crowsong Suite — Standards and Specification Review

You are acting as an expert standards reviewer for the Crowsong protocol
suite (github.com/propertools/crowsong).

Your task is to read both the reference implementation (code) and the
draft specifications (drafts/) provided below, and to produce a rigorous
standards review that tightens the specifications to more elegantly and
exactly express what is actually happening in the code.

This is not a code review. The code is the ground truth. The
specifications must describe what the code does — precisely, unambiguously,
and with enough clarity that an independent implementer could produce a
conformant implementation from the spec alone, without reading the code.

-----

## About the Crowsong protocol suite

Crowsong is a signal survival protocol suite. Its core components are:

- **FDS (Fox Decimal Script / UCS-DEC)**: Unicode code points encoded as
  zero-padded decimal integers, space-separated. Human-transcribable,
  channel-agnostic, survives any medium that can carry decimal digits.

- **CCL (Channel Camouflage Layer)**: Non-cryptographic prime-driven
  base-switching applied to UCS-DEC token streams. Raises Shannon entropy
  toward the AES-128 reference without providing cryptographic confidentiality.
  The twist-map is authoritative for reversal.

- **Mnemonic key derivation**: verse -> NFC normalise -> UCS-DEC encode
  -> SHA256 -> next_prime(N). The prime exists nowhere until derived.
  The verse is the secret.

- **Gloss layer**: Key-derived base-52 re-encoding for non-Latin scripts
  where CCL feasibility is structurally limited by the base^WIDTH > token
  rule. Reversed digits of prime P drive the Gloss permutation; forward
  digits drive CCL. One prime, two schedules, zero additional key material.

- **Word-space camouflage (haiku machine)**: Arbitrary token streams
  encoded as grammatically coherent, thematically plausible AI-style
  English nature haiku. Fully reversible given the seed verse.

- **WIDTH/3 BINARY mode**: Byte-stream encoding where each byte (0-255)
  becomes a 3-digit decimal token. mod3 schedule (bases 7/8/9) guarantees
  100% twist rate across all byte values.

-----

## Your role and methodology

You are an experienced IETF-style standards reviewer. You have written and
reviewed Internet-Drafts. You understand the difference between normative
and informative text. You know what "MUST", "SHOULD", "MAY" mean under
RFC 2119, and you use them precisely.

Work through the materials in this order:

1. Read the draft specifications first to understand the stated design intent
2. Read the reference implementation to understand what is actually built
3. Identify the gaps, ambiguities, and inconsistencies between the two
4. Produce your review as specified below

-----

## Review dimensions

### 1. Spec-to-implementation alignment

For each protocol component, identify:

- **Gaps**: things the implementation does that the spec does not describe
- **Contradictions**: places where implementation and spec disagree
- **Underspecification**: normative text that is too vague to implement
  unambiguously (a second implementer could make a different valid choice)
- **Over-specification**: text that constrains things the protocol does not
  actually require to be constrained

### 2. Normative precision

- Are MUST/SHOULD/MAY used correctly and consistently?
- Are there implicit MUSTs in the implementation that are not stated
  normatively in the spec?
- Are there stated MUSTs that the reference implementation does not enforce?
- Are field names, type definitions, and value ranges exact?
- Are all magic numbers named and defined?

### 3. Algorithm descriptions

For each algorithm (verse-to-prime, CCL base selection, Gloss permutation,
Fisher-Yates word selection, prime-chain walk, etc.):

- Is the algorithm description unambiguous? Could two careful implementers
  produce different outputs from the same input by following the spec?
- Are all inputs, outputs, and intermediate values explicitly typed and
  bounded?
- Are edge cases handled in the spec? (empty input, maximum values,
  feasibility fallback, floor rule for prime walks)
- Is the canonical test vector sufficient to detect divergent
  implementations?

### 4. RSRC block schema

For each artifact type (haiku-twist, haiku-stream, haiku-grammar-stream,
ccl-prime-twist, mnemonic-prime, etc.):

- Are all fields defined normatively with types and constraints?
- Is the VERSION field semantics defined? What does a version increment mean?
- Is the ordering of fields in the RSRC block normative or informative?
- Are there fields in the implementation that are absent from the spec?
- Are there fields in the spec that the implementation does not produce?

### 5. Interoperability requirements

For each component:

- What is the minimum an implementation MUST support to be conformant?
- What are the optional extensions (SHOULD/MAY)?
- Are there versioning mechanisms to handle future evolution?
- Is the degradation behaviour defined? (e.g. unknown SCHEDULE identifier)
- Could two conformant implementations fail to interoperate? How?

### 6. Suggested documentation and graphics

Identify specific places where:

- **A diagram would prevent ambiguity**: construction flows, state machines,
  fork/join structures in the pipeline, the prime-chain walk
- **A worked example would aid implementation**: the verse-to-prime
  derivation step by step, a full CCL round-trip with intermediate values,
  the Gloss layer permutation with concrete inputs and outputs
- **A table would clarify enumerated values**: POS tag mappings, RSRC field
  definitions, schedule identifiers, feasibility matrix by base and WIDTH
- **A decision tree would replace ambiguous prose**: the feasibility fallback
  logic, the Gloss-vs-CCL mode selection, the prime-chain floor rule
- **User documentation is missing**: what an operator needs to know to use
  the tool correctly, without reading the source
- **Developer documentation is missing**: what a contributor needs to know
  to extend or port the tool

For each suggestion, provide:
  - Location in the spec where the addition should appear
  - What the diagram/example/table should show
  - Why it prevents a specific class of implementation error

### 7. RFC-style structural review

- Is the document structure consistent with IETF conventions?
  (Abstract, Introduction, Conventions, Protocol Description,
  Security Considerations, IANA Considerations, References)
- Are informative and normative references correctly separated?
- Is the Security Considerations section accurate and complete?
  Does it correctly state that CCL provides NO cryptographic confidentiality?
- Are there claims that require citations?
- Is the abstract an accurate summary of the document?

### 8. Language and style

- Are there sentences that could be interpreted two ways?
- Are technical terms used consistently throughout?
- Are there colloquialisms or informal phrases in normative text?
- Is passive vs active voice used appropriately?
  (Normative requirements should use active: "The encoder MUST...")

-----

## What to produce

### Per-component findings

For each protocol component (CCL, Gloss, haiku machine, WIDTH/3 BINARY,
verse-to-prime, prime-chain, Gloss-W3, RSRC schema), provide:

**Gaps and contradictions** (severity: blocking / significant / minor / nit)
  - Spec section and implementation file/line
  - What is missing, wrong, or ambiguous
  - Suggested normative text or corrected construction description

**Suggested additions**
  - Specific text additions that would close the gap
  - Where in the document they belong

### Documentation and graphics recommendations

A prioritised list of:
  - Diagrams recommended (with description of content and placement)
  - Worked examples recommended (with description and placement)
  - Tables recommended (with description and placement)
  - User documentation gaps
  - Developer documentation gaps

### Overall assessment

- **Readiness for publication**: could this be submitted as an Internet-Draft
  in its current form? What are the blocking issues?
- **Interoperability risk**: what is the highest-risk underspecification —
  the most likely source of two conformant implementations diverging?
- **Priority order**: which gaps should be closed first?

-----

## Materials for review

The materials below are organised in two sections:

  SECTION 1 — DRAFT SPECIFICATIONS
  SECTION 2 — REFERENCE IMPLEMENTATION

Read specifications first, then implementation.

""".strip()


# ── Shared file utilities ─────────────────────────────────────────────────────

def write_stdout(text):
    """Write Unicode text safely to stdout on Python 2 and 3."""
    if PY2:
        sys.stdout.write(text.encode("utf-8"))
        sys.stdout.write(b"\n")
    else:
        sys.stdout.write(text)
        sys.stdout.write("\n")


def relpath_or_abs(path, base_path):
    """Return path relative to base_path where possible."""
    try:
        return os.path.relpath(path, base_path)
    except ValueError:
        return path


def matches_any(path_fragment, patterns):
    """
    Return True if path_fragment or its basename matches any pattern.
    Supports exact names and shell-style globs.
    """
    basename = os.path.basename(path_fragment)
    for pattern in patterns:
        if (
            fnmatch.fnmatch(path_fragment, pattern) or
            fnmatch.fnmatch(basename, pattern) or
            path_fragment == pattern or
            basename == pattern
        ):
            return True
    return False


def normalise_extensions(exts):
    """Normalise extensions to lowercase dotted form."""
    results = []
    for ext in exts:
        ext = ext.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        results.append(ext.lower())
    return results


def should_include_file(fpath, extensions, exclude_patterns, max_kb):
    """
    Return (include_bool, reason_string) for a candidate file.

    reason_string is None on inclusion, or one of:
    'excluded', 'extension', 'stat', 'size'
    """
    basename = os.path.basename(fpath)

    if matches_any(fpath, exclude_patterns) or matches_any(basename, exclude_patterns):
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
        ok, reason = should_include_file(
            path, extensions, exclude_patterns, max_kb)
        if ok:
            return [path]
        if reason == "size":
            print("# SKIPPED (>{0}KB): {1}".format(
                max_kb, path), file=sys.stderr)
        return []

    for root, dirs, files in os.walk(path):
        dirs[:] = sorted([
            d for d in dirs
            if not matches_any(d, exclude_patterns)
            and not matches_any(os.path.join(root, d), exclude_patterns)
        ])
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            ok, reason = should_include_file(
                fpath, extensions, exclude_patterns, max_kb)
            if not ok:
                if reason == "size":
                    print("# SKIPPED (>{0}KB): {1}".format(
                        max_kb, fpath), file=sys.stderr)
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
    relpath = relpath_or_abs(fpath, base_path)
    return "\n".join([
        relpath,
        SEPARATOR,
        content.rstrip(),
        SEPARATOR,
        "",
    ])


def estimate_chars(files):
    """Estimate total character count by reading included files."""
    total = 0
    for fpath in files:
        total += len(read_file(fpath))
    return total


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="crowsong-speccheck",
        description=(
            "Prepare code and draft specs for AI standards review.\n\n"
            "Assembles the Crowsong spec review prompt, draft specifications,\n"
            "and reference implementation into a single buffer for pasting\n"
            "into an AI standards review session.\n\n"
            "The reviewer is put in the role of an expert IETF-style\n"
            "standards reviewer tightening specs to match the implementation.\n\n"
            "Output to stdout. Pipe to pbcopy (macOS) or xclip (Linux)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python crowsong-speccheck.py | pbcopy\n"
            "  python crowsong-speccheck.py --dry-run\n"
            "  python crowsong-speccheck.py \\\n"
            "      --code tools/mnemonic/ --drafts drafts/ | pbcopy\n"
            "  python crowsong-speccheck.py --prompt-only\n"
        ),
    )

    parser.add_argument(
        "--code",
        default=DEFAULT_CODE_PATH,
        metavar="PATH",
        help="path to reference implementation (default: {0})".format(
            DEFAULT_CODE_PATH),
    )
    parser.add_argument(
        "--drafts",
        default=DEFAULT_DRAFTS_PATH,
        metavar="PATH",
        help="path to draft specifications (default: {0})".format(
            DEFAULT_DRAFTS_PATH),
    )
    parser.add_argument(
        "--ext-code",
        nargs="+",
        default=DEFAULT_EXT_CODE,
        metavar="EXT",
        help="code file extensions (default: {0})".format(
            " ".join(DEFAULT_EXT_CODE)),
    )
    parser.add_argument(
        "--ext-drafts",
        nargs="+",
        default=DEFAULT_EXT_DRAFTS,
        metavar="EXT",
        help="draft file extensions (default: {0})".format(
            " ".join(DEFAULT_EXT_DRAFTS)),
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
    """Program entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.prompt_only:
        write_stdout(REVIEW_PROMPT)
        return 0

    ext_code   = normalise_extensions(args.ext_code)
    ext_drafts = normalise_extensions(args.ext_drafts)

    draft_files = collect_files(
        path=args.drafts,
        extensions=ext_drafts,
        exclude_patterns=args.exclude,
        max_kb=args.max_kb,
    )

    code_files = collect_files(
        path=args.code,
        extensions=ext_code,
        exclude_patterns=args.exclude,
        max_kb=args.max_kb,
    )

    if not draft_files and not code_files:
        print(
            "No files found. Check --code and --drafts paths.",
            file=sys.stderr)
        return 1

    if not draft_files:
        print(
            "Warning: no draft specifications found under {0}".format(
                args.drafts),
            file=sys.stderr)

    if not code_files:
        print(
            "Warning: no code files found under {0}".format(args.code),
            file=sys.stderr)

    drafts_base = os.path.abspath(args.drafts)
    code_base   = os.path.abspath(args.code)
    # Common base for relpath display
    common_base = os.path.commonprefix([drafts_base, code_base])
    if not os.path.isdir(common_base):
        common_base = os.path.dirname(common_base)
    if not common_base:
        common_base = os.getcwd()

    if args.dry_run:
        draft_chars = estimate_chars(draft_files)
        code_chars  = estimate_chars(code_files)
        prompt_chars = len(REVIEW_PROMPT) if not args.no_prompt else 0

        print("SECTION 1 — DRAFT SPECIFICATIONS ({0} file(s)):".format(
            len(draft_files)))
        print("")
        for fpath in draft_files:
            size_kb = os.path.getsize(fpath) / 1024.0
            print("  {0:<60} {1:>8.1f} KB".format(
                relpath_or_abs(fpath, common_base), size_kb))

        print("")
        print("SECTION 2 — REFERENCE IMPLEMENTATION ({0} file(s)):".format(
            len(code_files)))
        print("")
        for fpath in code_files:
            size_kb = os.path.getsize(fpath) / 1024.0
            print("  {0:<60} {1:>8.1f} KB".format(
                relpath_or_abs(fpath, common_base), size_kb))

        print("")
        total = draft_chars + code_chars + prompt_chars
        print("Estimated output: ~{0:,} chars ({1} spec + {2} code file(s))".format(
            total, len(draft_files), len(code_files)))
        print("(Run without --dry-run to generate full concatenated output)")
        return 0

    # Full output
    parts = []

    if not args.no_prompt:
        parts.append(REVIEW_PROMPT)
        parts.append("")

    # Section 1: draft specifications
    parts.append(MAJOR_SEP)
    parts.append("SECTION 1 — DRAFT SPECIFICATIONS ({0} file(s))".format(
        len(draft_files)))
    parts.append(MAJOR_SEP)
    parts.append("")

    if draft_files:
        for fpath in draft_files:
            parts.append(format_file_block(
                fpath, common_base, read_file(fpath)))
    else:
        parts.append("# No draft specification files found.")
        parts.append("")

    # Section 2: reference implementation
    parts.append(MAJOR_SEP)
    parts.append("SECTION 2 — REFERENCE IMPLEMENTATION ({0} file(s))".format(
        len(code_files)))
    parts.append(MAJOR_SEP)
    parts.append("")

    if code_files:
        for fpath in code_files:
            parts.append(format_file_block(
                fpath, common_base, read_file(fpath)))
    else:
        parts.append("# No reference implementation files found.")
        parts.append("")

    output = "\n".join(parts)
    write_stdout(output)

    print(
        "{0} spec + {1} code file(s) concatenated ({2:,} chars)".format(
            len(draft_files), len(code_files), len(output)),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
