# primes.py — prime utilities with deterministic Miller-Rabin

Primality testing, next-prime derivation, and prime generation.
No dependencies beyond the Python standard library.

The primality test is deterministic for all integers below
3,317,044,064,679,887,385,961,981 — well beyond the range of any
input you will realistically generate from a UCS-DEC encoded verse.

---

## Usage

```bash
python primes.py is-prime <n>
python primes.py next-prime <n>
python primes.py first <count>
python primes.py range <start> <end>
```

## Examples

```bash
# Test primality
python primes.py is-prime 17          # true
python primes.py is-prime 18          # false

# Find the next prime at or above n
python primes.py next-prime 1000      # 1009
python primes.py next-prime 2038      # 2039

# Generate the first N primes
python primes.py first 10             # 2 3 5 7 11 13 17 19 23 29
python primes.py first 10000          # first 10,000 primes

# All primes in a range
python primes.py range 100 200
```

## As a library

```python
from primes import is_prime, next_prime, generate_first_primes, generate_primes_in_range

is_prime(104729)          # True
next_prime(1000)          # 1009

list(generate_first_primes(10))
# [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

list(generate_primes_in_range(100, 150))
# [101, 103, 107, 109, 113, 127, 131, 137, 139, 149]
```

## How the primality test works

Miller-Rabin with the fixed witness set
`{2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37}`.

This is deterministic — not probabilistic — for all n below
3,317,044,064,679,887,385,961,981. For the intended use case
(testing primes derived from UCS-DEC encoded verse) this bound
is more than sufficient.

The test runs in O(k log² n) time where k is the number of
witnesses (12). For large inputs, `next_prime` may take a
moment — this is expected.

## Connection to the Crowsong stack

`next_prime` is the key derivation step in the Mnemonic Share
Wrapping construction:

```
verse
  → NFC normalise
  → encode to UCS-DEC (draft-darley-fds-00)
  → interpret as integer N
  → next_prime(N)          ← this tool
  → wrapping key Kᵢ
```

The resulting prime is used to wrap a Shamir share, not as the
share itself. See `docs/mnemonic-shamir-sketch.md` for the full
construction.

`primes first 10000 > docs/sequences/primes-10000.txt` generates
a printed quick-reference table suitable for inclusion in a Vesper
archive — useful for Class D channel work where a human operator
may need to verify a prime by hand.

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/constants/constants.py` | Named constant digit generation |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Compatibility

Python 2.7+ / 3.x. No dependencies.

## License

MIT. See `../../LICENSE` and `../../LICENSES.md`.
