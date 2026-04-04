# tools/mnemonic/ — verse-derived keys and Channel Camouflage Layer

Two tools sharing a common construction:

```
verse
  → NFC normalise
  → UCS-DEC encode (WIDTH/5, no wrapping)
  → SHA256 of token stream
  → interpret as 256-bit integer N
  → next_prime(N)
  → prime P
```

`verse_to_prime.py` derives the prime and packages it as a self-describing
FDS Print Profile artifact. `prime_twist.py` uses a prime as a cyclic key
schedule to apply base-switching transforms to any FDS token stream.

Both tools: Python 2.7+/3.x, no external dependencies, MIT licence.

**These are test implementations.** The CCL construction and artifact
format are not yet normatively specified. See
`drafts/draft-darley-fds-ccl-prime-twist-00.txt` for the pre-normative
specification and `docs/mnemonic-shamir-sketch.md` for the broader
Mnemonic Share Wrapping design.

---

## verse_to_prime.py

Derives a prime from a verse and outputs a self-describing FDS Print
Profile artifact whose payload is the UCS-DEC encoding of that prime.

```bash
python verse_to_prime.py derive [--show-steps] [--ref ID] [--med M]
python verse_to_prime.py verify <infile>
```

### Examples

```bash
# Basic derivation
echo "The signal strains, but never gone." | \
    python verse_to_prime.py derive

# With construction steps printed to stderr
cat verse.txt | python verse_to_prime.py derive --show-steps

# Save artifact with reference ID
cat verse.txt | python verse_to_prime.py derive --ref K1 > k1.txt

# Verify a saved artifact
python verse_to_prime.py verify k1.txt
```

### Output

The artifact is a self-describing FDS Print Profile. Its RSRC block
carries the full construction trace:

```
RSRC: BEGIN
  TYPE:     mnemonic-prime
  METHOD:   UCS-DEC / SHA256 / next-prime / Miller-Rabin
  DIGEST:   SHA256:<hex>
  N:        <256-bit integer>
  P:        <derived prime>
  DIGITS:   77
  GENERATED:2026-04-04
RSRC: END

<UCS-DEC encoding of the prime's digits>
```

The payload encodes the prime itself in UCS-DEC. The format eats its
own output: the prime is encoded in the same format used to derive it.

### Properties

- The verse may be any length. SHA256 normalises to ~77 digits.
- The prime exists nowhere until derived. Recite the verse to recover it.
- Deterministic: the same verse always produces the same prime.
- The primality test is deterministic for n < 3.3 × 10²⁴ and
  probabilistic (error ≤ 4⁻⁶⁴) for larger inputs including all
  SHA256-derived values.

---

## prime_twist.py

Applies prime-derived base-switching transforms to an FDS token stream.
The prime's decimal digits drive a cyclic key schedule (the ouroboros).
For each token, the scheduled digit determines the output base (2–9),
falling back to base 10 where the value exceeds the representable range.

The twist-map — recording the actual base used per position — is stored
in the artifact RSRC block and is required for reversal.

**CCL provides no cryptographic confidentiality or integrity.**
It reduces statistical salience. It raises the cost of passive attention.

```bash
python prime_twist.py twist   --prime <P> [--width N] [--ref ID] [--med M]
python prime_twist.py untwist <infile>
python prime_twist.py stack   --primes P1,P2,... [--ref ID] [--med M]
python prime_twist.py stack   --verse-file <file> [--ref ID] [--med M]
python prime_twist.py unstack <infile>
```

### Examples

```bash
# Single pass — provide a prime directly
cat payload.txt | \
    python prime_twist.py twist --prime 748...701 > twisted.txt

# Untwist
python prime_twist.py untwist twisted.txt | python ucs_dec_tool.py -d

# Triple stack — three primes comma-separated
cat payload.txt | \
    python prime_twist.py stack --primes P1,P2,P3 --ref CCL3

# Triple stack — derive primes from a verse file (one verse per line)
cat payload.txt | \
    python prime_twist.py stack --verse-file verses.txt --ref CCL3

# Unstack and decode
python prime_twist.py unstack stacked.txt | python ucs_dec_tool.py -d
```

### Full pipeline: verse → prime → twist

```bash
# Derive the key from a verse
echo "The signal strains, but never gone." | \
    python verse_to_prime.py derive --ref K1 > k1.txt

# Extract the prime
PRIME=$(grep "^  P:" k1.txt | awk '{print $2}')

# Apply CCL
cat payload.txt | \
    python prime_twist.py twist --prime "$PRIME" --ref CCL1 > twisted.txt

# Recover
python prime_twist.py untwist twisted.txt | python ucs_dec_tool.py -d
```

### Stacking

Multiple passes applied sequentially with distinct primes. Each pass
takes the token stream output of the previous pass as input. Output is
a single self-describing stack file containing all pass artifacts.

Maximum depth: 10. Diminishing returns beyond CCL3:

| Pass | Entropy (canonical 534-token payload) | Unique tokens |
|------|---------------------------------------|---------------|
| Original | 4.78 bits/token | 53 |
| CCL1 | 6.96 bits/token | 172 |
| CCL2 | 7.82 bits/token | 282 |
| CCL3 | **8.37 bits/token** | 375 |
| AES-128 reference | ~7.9–8.0 bits/byte | — |

CCL3 exceeds the AES-128 ciphertext entropy reference. A passive
entropy scanner cannot distinguish it from encrypted data.

### Steganographic injection

The twisted token stream consists of five-digit decimal integers.
These occur naturally in telemetry, log files, cross-reference lists,
and financial records. The stream may be injected into such containers
without modification. The receiver extracts the numeric field and pipes
it to `unstack`.

See `demo/ccl_demo.sh` for a full nine-step live demonstration.

---

## The construction in one diagram

```
verse (any length, any Unicode)
    │
    ▼ NFC normalise
    │
    ▼ UCS-DEC encode (WIDTH/5)
    │   "00084 00104 00101 ..."
    │
    ▼ SHA256 of token stream (UTF-8)
    │   → 256-bit digest → ~77-digit integer N
    │
    ▼ next_prime(N)        ← verse_to_prime.py stops here
    │   prime P (77 digits)
    │
    ▼ use digits of P as key schedule (ouroboros)
    │
    ▼ for each FDS token tᵢ:       ← prime_twist.py
    │   digit d = P_digits[i mod len(P)]
    │   base  b = d  if d ≥ 2 and b^width > tᵢ
    │           = 10 otherwise (fallback)
    │   output  = repr(tᵢ, base=b, width=5)
    │   record  twist_map[i] = b
    │
    ▼ twisted FDS token stream
        + RSRC block with PRIME and TWIST-MAP
        → self-describing artifact
```

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/ucs-dec/ucs_dec_tool.py` | FDS encode / decode / frame / verify |
| `tools/primes/primes.py` | Primality testing and prime generation |
| `tools/constants/constants.py` | Named constant digit generation (IV sources) |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Further reading

| Document | Notes |
|----------|-------|
| `drafts/draft-darley-fds-ccl-prime-twist-00.txt` | Pre-normative CCL spec |
| `docs/mnemonic-shamir-sketch.md` | Mnemonic Share Wrapping design sketch |
| `docs/structural-principles.md` | Governing design principles |
| `demo/ccl_demo.sh` | Nine-step live demonstration |

## Compatibility

Python 2.7+ / 3.x. No dependencies.

## Licence

MIT. See `../../LICENSE` and `../../LICENSES.md`.

Data: digits of mathematical constants are not copyrightable.
OEIS sequence identifiers used for reference only.
