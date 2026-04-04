# scripts/generate_numbers.sh — local mathematical corpus generator

Generates and verifies the full Crowsong mathematical reference corpus
in one command. Composable, idempotent, and git-free: it generates
outputs and tells you what to commit; it does not commit anything.

Run it whenever you need to regenerate the corpus from scratch — on a
new machine, after a tools update, or to produce a Vesper archive copy
at a custom digit count.

---

## What it generates

| Step | Output | Notes |
|------|--------|-------|
| 1 | `docs/constants/{name}-{N}.txt` | π, e, φ, √2, √3, ln2, ζ(3) — N digits each |
| 2 | `docs/sequences/primes-10000.txt` | First 10,000 primes |
| 3 | `docs/sequences/A*.txt` | 15 curated OEIS sequences |
| 4 | `archive/flash-paper-SI-2084-FP-001-payload.txt` | Canonical test vector |
| 4 | `archive/flash-paper-SI-2084-FP-001-framed.txt` | Framed artifact |

All outputs are SHA256-verified or CRC32-verified before the script
reports success.

---

## Usage

```bash
bash scripts/generate_numbers.sh [OPTIONS]
```

### Options

```
--constants-only    Generate and verify constant digit files only
--sequences-only    Generate primes table and sync OEIS only
--artifacts-only    Regenerate canonical test vector artifacts only
--no-oeis           Skip OEIS network sync (useful offline)
--no-verify         Skip all verification passes
--digits N          Digits per constant file (default: 10000)
--dir PATH          Output root directory (default: repo root)
--quiet             Suppress progress output
-h / --help         Show usage
```

### Examples

```bash
# Full run from repo root (requires network for OEIS)
bash scripts/generate_numbers.sh

# Skip OEIS — all other steps run offline
bash scripts/generate_numbers.sh --no-oeis

# Constants only, at 50,000 digits (for Vesper archival)
bash scripts/generate_numbers.sh --constants-only --digits 50000

# Just regenerate the test vector artifacts
bash scripts/generate_numbers.sh --artifacts-only

# Output to a custom path (e.g. a mounted archive volume)
bash scripts/generate_numbers.sh --dir /mnt/archive/crowsong

# Quick — skip both OEIS and verification
bash scripts/generate_numbers.sh --no-oeis --no-verify

# Quiet mode — only print errors
bash scripts/generate_numbers.sh --quiet
```

---

## Requirements

**Python:** `python3` or `python` in PATH.

**mpmath:** required for Step 1 (constant digit generation) only.

```bash
pip install mpmath
```

All other steps use Python stdlib only. Steps 2–4 have no external
dependencies.

**Network:** required for Step 3 (OEIS sync) only. Pass `--no-oeis`
to run fully offline. The OEIS sync sleeps 2 seconds between requests
and takes 2–3 minutes total.

---

## Output

On success:

```
────────────────────────────────────────────────────────────
  Pre-flight
────────────────────────────────────────────────────────────
  Python:   python3 (Python 3.x.x)
  Repo:     /path/to/crowsong
  Output:   /path/to/crowsong
  Digits:   10000
  mpmath:   available
  All tools found.

────────────────────────────────────────────────────────────
  Step 1 — Named mathematical constants (10000 digits each)
────────────────────────────────────────────────────────────
  Generating pi...
  PASS  pi → docs/constants/pi-10000.txt
  ...
  PASS  pi verified
  ...

  Results: N passed, 0 failed

  All outputs are in:
    docs/constants/
    docs/sequences/
    archive/

  To commit (from repo root, on release/crowsong-01):

    git add docs/constants/ docs/sequences/ \
            archive/flash-paper-SI-2084-FP-001-payload.txt \
            archive/flash-paper-SI-2084-FP-001-framed.txt
    git commit -m "chore: generate and commit programmatic outputs"
```

The git command is printed as a reminder. The script never commits
anything.

---

## Idempotency

Running the script twice produces identical outputs. Constant files
and OEIS sequence files include SHA256 checksums in their headers;
the script verifies these on each run.

OEIS sequences already in the cache are skipped on re-runs unless
`--force` is passed to the sync step directly.

---

## Vesper archival use

To generate a high-resolution constant corpus for inclusion in a
Vesper physical archive:

```bash
# 50,000 digits — fits on ~35 A4 pages per constant
bash scripts/generate_numbers.sh \
    --constants-only \
    --digits 50000 \
    --dir /path/to/vesper-archive-prep \
    --no-verify
```

The resulting files are self-describing plain text, readable without
software, and suitable for archival printing on cotton-rag paper.
See `docs/vesper-archive-protocol.md` for the full archival procedure.

---

## Connection to tools

The script is a thin orchestration wrapper around:

| Tool | Purpose |
|------|---------|
| `tools/constants/constants.py` | Constant digit generation and verification |
| `tools/primes/primes.py` | Prime number generation |
| `tools/sequences/sequences.py` | OEIS sequence sync and verification |
| `tools/ucs-dec/ucs_dec_tool.py` | Test vector artifact generation |
| `tests/roundtrip/run_tests.sh` | Full roundtrip test suite |

Each tool can be run independently. This script coordinates them in
the correct order with consistent output paths.
