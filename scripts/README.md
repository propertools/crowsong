# scripts/

Operational scripts for the Crowsong project. Two scripts, two
concerns: generating the mathematical corpus locally, and mirroring
the repository against the day it disappears.

-----

## Why mirroring matters

Someone will probably try to take this repository offline at some
point. The work it describes — tools for signal survival under
adversarial conditions, designed for people whose language is
sensitive information — is exactly the kind of work that attracts
that kind of attention.

The correct response is to make the repository uncensorable by making
it redundant. Run `crowsong-backup.sh` frequently. Keep a local
mirror. Keep it updated. If propertools/crowsong goes dark, you
have everything — all branches, all forks, all history.

The repository can also be transmitted using the encoding it
describes. A UCS-DEC tarball of the entire Crowsong codebase fits
in a photographic microdot. The tools bootstrap themselves on
arrival. The keys come from memory and from public mathematics.

Run the backup script. Keep it current. The signal survives if
enough people are carrying it.

-----

## scripts/crowsong-backup.sh — git mirror of Crowsong and all forks

Clones or updates a bare mirror of `propertools/crowsong` and all
reachable public forks, organised on disk by owner. Designed to run
unattended via crontab. Logs to a rotating logfile. Sends a summary
to stdout (mailed by cron if `MAILTO` is set).

**Run this frequently.** Weekly at minimum. Daily is better.

-----

### Usage

```bash
bash scripts/crowsong-backup.sh [OPTIONS]
```

### Options

```
--dest DIR        Backup root directory (default: ~/crowsong-backup)
--token TOKEN     GitHub personal access token (or set GITHUB_TOKEN env)
--upstream REPO   GitHub repo to mirror (default: propertools/crowsong)
--no-forks        Skip fork discovery and backup
--dry-run         Print what would be done without doing it
--log FILE        Log file path (default: DEST/backup.log)
--keep-logs N     Number of rotated log files to keep (default: 14)
-h / --help       Show this help
```

### Crontab setup

```crontab
# Mirror Crowsong daily at 03:17 — summary mailed by cron
MAILTO=you@example.com
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
17 3 * * * /path/to/scripts/crowsong-backup.sh --dest /srv/crowsong-backup

# Silent variant — log file only, no mail
17 3 * * * /path/to/scripts/crowsong-backup.sh --dest /srv/crowsong-backup >/dev/null
```

### Examples

```bash
# First run — clone upstream and all forks
bash scripts/crowsong-backup.sh --dest /srv/crowsong-backup

# With GitHub token (raises API rate limit from 60 to 5000 req/hr)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx \
    bash scripts/crowsong-backup.sh --dest /srv/crowsong-backup

# Upstream only, no forks
bash scripts/crowsong-backup.sh --dest ~/backup --no-forks

# Dry run — see what would happen
bash scripts/crowsong-backup.sh --dest ~/backup --dry-run

# Custom upstream (if you want to mirror a fork as primary)
bash scripts/crowsong-backup.sh \
    --upstream trey-darley/crowsong \
    --dest ~/backup
```

### Authentication

A GitHub personal access token is optional for public repositories
but strongly recommended — it raises the API rate limit from 60 to
5,000 requests per hour, which matters if the fork count grows.

Set via environment variable (preferred for crontab — not visible
in process list):

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

The token requires no scopes for public repositories. Grant `repo`
scope only if you also want to mirror private forks you own.

### Disk layout after first run

```
DEST/
  propertools/
    crowsong.git/         bare mirror of upstream
  trey-darley/
    crowsong.git/         bare mirror of fork
  cvoid/
    crowsong.git/         bare mirror of fork
  ...
  backup.log              current log
  backup.log.1            rotated (yesterday)
  forks.json              cached fork list from last API call
  LAST_RUN                timestamp and summary of last run
```

Each `.git` directory is a complete bare clone containing all
branches, all tags, and full history.

### Recovery

To work with a mirrored repository:

```bash
# Clone from mirror
git clone /srv/crowsong-backup/propertools/crowsong.git crowsong

# Inspect directly without cloning
git --git-dir=/srv/crowsong-backup/propertools/crowsong.git log --oneline -10
git --git-dir=/srv/crowsong-backup/propertools/crowsong.git branch -a
```

To transmit the mirror over a degraded channel, see
`docs/vesper-archive-protocol.md` and
`docs/vesper-mirror-architecture.md`.

### Exit codes

`0` — all repositories updated successfully.
`1` — one or more repositories failed. Check `LAST_RUN` and the
log file. Failed repos are listed in the summary.

### Dependencies

`git`, `curl`, `python3`. All standard. No external packages.

-----

## scripts/generate_numbers.sh — local mathematical corpus generator

Generates and verifies the full Crowsong mathematical reference corpus
in one command. Composable, idempotent, and git-free: it generates
outputs and tells you what to commit; it does not commit anything.

Run it whenever you need to regenerate the corpus from scratch — on a
new machine, after a tools update, or to produce a Vesper archive copy
at a custom digit count.

-----

### What it generates

|Step|Output                                          |Notes                                     |
|----|------------------------------------------------|------------------------------------------|
|1   |`docs/constants/{name}-{N}.txt`                 |π, e, φ, √2, √3, ln2, ζ(3) — N digits each|
|2   |`docs/sequences/primes-10000.txt`               |First 10,000 primes                       |
|3   |`docs/sequences/A*.txt`                         |15 curated OEIS sequences                 |
|4   |`archive/flash-paper-SI-2084-FP-001-payload.txt`|Canonical test vector                     |
|4   |`archive/flash-paper-SI-2084-FP-001-framed.txt` |Framed artifact                           |

All outputs are SHA256-verified or CRC32-verified before the script
reports success.

-----

### Usage

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

-----

### Requirements

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

-----

### Output

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

-----

### Idempotency

Running the script twice produces identical outputs. Constant files
and OEIS sequence files include SHA256 checksums in their headers;
the script verifies these on each run.

OEIS sequences already in the cache are skipped on re-runs unless
`--force` is passed to the sync step directly.

-----

### Vesper archival use

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

-----

### Connection to tools

The script is a thin orchestration wrapper around:

|Tool                           |Purpose                                   |
|-------------------------------|------------------------------------------|
|`tools/constants/constants.py` |Constant digit generation and verification|
|`tools/primes/primes.py`       |Prime number generation                   |
|`tools/sequences/sequences.py` |OEIS sequence sync and verification       |
|`tools/ucs-dec/ucs_dec_tool.py`|Test vector artifact generation           |
|`tests/roundtrip/run_tests.sh` |Full roundtrip test suite                 |

Each tool can be run independently. This script coordinates them in
the correct order with consistent output paths.

-----

*Signal survives if enough people are carrying it.*