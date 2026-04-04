# constants.py — named mathematical constant digit generator

Generates digit strings for named mathematical constants, formatted for
human readability and archival storage.

Suitable for use as IV sources in the Channel Camouflage Layer and
Mnemonic Share Wrapping constructions. Also useful as standalone printed
reference material.

Requires `mpmath` at generation time. Generated files are plain text
with no runtime dependencies.

---

## Usage

```bash
python constants.py list
python constants.py digits <name> <count>
python constants.py show <name> <count>
python constants.py generate <name> <count> <outfile>
python constants.py verify <name> <infile>
```

## Examples

```bash
# List available constants
python constants.py list

# Print 100 digits of pi, plain (pipeable)
python constants.py digits pi 100

# Print 200 digits of phi, formatted for reading
python constants.py show phi 200

# Generate an archival file of 10,000 digits of e
python constants.py generate e 10000 docs/constants/e-10000.txt

# Verify a previously generated file
python constants.py verify pi docs/constants/pi-10000.txt
```

## Available constants

| Name | Symbol | OEIS | Notes |
|------|--------|------|-------|
| `pi` | π | A000796 | Ratio of circumference to diameter |
| `e` | e | A001113 | Base of the natural logarithm |
| `phi` | φ | A001622 | Golden ratio |
| `sqrt2` | √2 | A002193 | First known irrational number |
| `sqrt3` | √3 | A002194 | |
| `sqrt5` | √5 | A002163 | |
| `ln2` | ln(2) | A002162 | Natural logarithm of 2 |
| `apery` | ζ(3) | A002117 | Apery's constant |

## Generated file format

Generated files are self-describing plain text, designed to be readable
without software and suitable for inclusion in a Vesper archive:

```
# π — Pi
#
# Constant:  pi
# OEIS:      A000796
# Notes:     Ratio of circumference to diameter. Infinite, non-repeating.
#
# Digits:    10000
# Format:    decimal, 10 digits per group, 6 groups per line
# SHA256:    2a32257c1b63c17b152835a29b8f832c1beb4d04d1594e18632104cf29243309
# Generated: 2026-04-04
# Tool:      tools/constants.py (Proper Tools SRL)
#
# This file contains only decimal digits of π.
# No decimal point. Digits begin with the leading integer digit.
# Suitable for use as an IV source per draft-darley-shard-bundle-01.
#

3141592653 5897932384 6264338327 9502884197 1693993751 0582097494
4592307816 4062862089 9862803482 5342117067 9821480865 1328230664
...
```

SHA256 is computed over the raw digit string (no spaces, no newlines).
Verification recomputes from first principles and checks against the
declared hash.

## As a library

```python
from constants import get_digits, format_digits, get_constant_meta

# Raw digits
digits = get_digits("pi", 1000)        # "31415926535897..."

# Formatted for display
print(format_digits(digits))

# Registry metadata
key, meta = get_constant_meta("phi")
print(meta["symbol"], meta["oeis"])   # φ  A001622
```

## Generating the docs/constants/ reference files

```bash
for name in pi e phi sqrt2 sqrt3 ln2 apery; do
    python constants.py generate $name 10000 docs/constants/${name}-10000.txt
done
```

Pre-generated 10,000-digit files for all eight constants are committed
to `docs/constants/` and verified against their declared SHA256 values.
To regenerate and verify:

```bash
for name in pi e phi sqrt2 sqrt3 ln2 apery; do
    python constants.py verify $name docs/constants/${name}-10000.txt
done
```

## Connection to the Crowsong stack

Named constants serve as public, indestructible, offline-reproducible
initialisation vectors for:

- **Channel Camouflage Layer** — transformation schedule derived from
  digits of a named constant at a declared offset
- **Mnemonic Share Wrapping** — IV anchor for the 3/3 construction;
  the constant is the public share, specified by name not value

Declared in the resource fork header as:

```
IV: PI · OFFSET/1000 · BASE/10
```

See `docs/mnemonic-shamir-sketch.md` for the full construction.

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/primes/primes.py` | Primality testing and prime generation |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Requirements

`mpmath` is required at generation time:

```bash
pip install mpmath
```

Generated files have no runtime dependencies.

## Compatibility

Python 2.7+ / 3.x

## License

MIT. See `../../LICENSE` and `../../LICENSES.md`.

Data: digits of mathematical constants are not copyrightable. OEIS
sequence identifiers are used for reference only.
