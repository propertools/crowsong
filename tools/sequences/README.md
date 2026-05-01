# sequences.py - OEIS sequence mirror and quick reference tool

Fetches, caches, and serves terms from a curated subset of the
On-Line Encyclopedia of Integer Sequences (OEIS), for offline use,
Vesper archival, and IV generation.

Each cached file is self-describing plain text, readable without software,
and suitable for inclusion in a Vesper archive.

---

## Usage

```bash
python sequences.py list
python sequences.py show <id>
python sequences.py terms <id> [--count N]
python sequences.py sync [<id> ...] [--all] [--force]
python sequences.py verify [<id> ...]
```

The `--dir` flag (before the subcommand) overrides the default cache
directory (`docs/sequences/`):

```bash
python sequences.py --dir /path/to/cache list
```

## Examples

```bash
# List all sequences in the curated registry
python sequences.py list

# Show metadata and cache status for a sequence
python sequences.py show A000796

# Print the first 50 terms of a cached sequence
python sequences.py terms A000040 --count 50

# Sync specific sequences from OEIS
python sequences.py sync A000796 A000040

# Sync all sequences not yet cached
python sequences.py sync

# Sync all sequences in the registry (skip already cached)
python sequences.py sync --all

# Re-fetch a specific sequence even if cached
python sequences.py sync A000796 --force

# Verify SHA256 of all cached files
python sequences.py verify

# Verify specific sequences
python sequences.py verify A000796 A000040
```

## Curated registry

15 sequences across four categories:

**Primes and prime-adjacent**

| ID | Name | Tags |
|----|------|------|
| A000040 | Prime numbers | primes, reference |
| A005384 | Sophie Germain primes | primes, crypto |
| A000225 | Mersenne numbers | primes, mersenne |
| A000668 | Mersenne primes | primes, mersenne |

**Constants as digit sequences**

| ID | Name | Tags |
|----|------|------|
| A000796 | Decimal expansion of π | constant, iv-source |
| A001113 | Decimal expansion of e | constant, iv-source |
| A001622 | Decimal expansion of φ | constant, iv-source |
| A002193 | Decimal expansion of √2 | constant, iv-source |
| A002117 | Decimal expansion of ζ(3) | constant, iv-source |

**Foundational sequences**

| ID | Name | Tags |
|----|------|------|
| A000045 | Fibonacci numbers | reference |
| A000142 | Factorial numbers n! | reference |
| A000108 | Catalan numbers | reference, combinatorics |

**Number theory and combinatorics**

| ID | Name | Tags |
|----|------|------|
| A000010 | Euler's totient function φ(n) | number-theory, crypto |
| A001065 | Sum of proper divisors of n | number-theory |
| A000110 | Bell numbers | combinatorics |

To add a sequence: add an entry to the `SEQUENCES` dict in the source,
then run `python sequences.py sync <id>`.

## Cached file format

Cached files are self-describing plain text:

```
# A000796 - Decimal expansion of Pi
#
# OEIS:     https://oeis.org/A000796
# Fetched:  2026-04-04
# Terms:    10000
# Offset:   1,1
# Keywords: nonn,cons,nice,...
# SHA256:   a1b2c3...
# Tags:     constant, iv-source
# Notes:    3, 1, 4, 1, 5, 9, ... Digits of pi. IV source.
#
# Data copyright OEIS Foundation Inc. - https://oeis.org
# Used with attribution per OEIS End-User License Agreement.
#

3, 1, 4, 1, 5, 9, 2, 6, 5, 3, ...
```

SHA256 is computed over the comma-separated term string.
Verification recomputes and checks against the declared hash.

## Polite use

The tool sleeps 2 seconds between each HTTP request (metadata fetch,
b-file fetch, and between sequences) and identifies itself in the
User-Agent header. OEIS is a free public resource maintained by a
non-profit. Do not run `sync --all --force` repeatedly.

OEIS data is copyright OEIS Foundation Inc. and used with attribution
per the OEIS End-User License Agreement:
https://oeis.org/wiki/The_OEIS_End-User_License_Agreement

## Connection to the Crowsong stack

Sequences tagged `iv-source` (the constant digit sequences) are the
OEIS-sourced counterpart to `tools/constants/constants.py`. They serve
as IV sources for:

- **Channel Camouflage Layer**: transformation schedule derived from
  sequence terms at a declared offset
- **Mnemonic Share Wrapping**: public IV anchor in the 3/3 construction

Declared in the resource fork header as:

```
IV: PI · OFFSET/1000 · BASE/10
```

The full synced corpus (`docs/sequences/`) is also suitable for
inclusion in a Vesper archive as a quick-reference library; the
prime and Fibonacci sequences in particular are useful for Class D
channel work where a human operator may need to verify values by hand.

See `docs/mnemonic-shamir-sketch.md` for the full construction.

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/primes/primes.py` | Primality testing and prime generation |
| `tools/constants/constants.py` | Named constant digit generation |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Compatibility

Python 2.7+ / 3.x. No dependencies beyond the standard library.
Network access required for `sync`; all other subcommands work offline.

## License

MIT (this tool). Sequence data copyright OEIS Foundation Inc.
