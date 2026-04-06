# tools/mnemonic/ — verse-derived keys and Channel Camouflage Layer

Six files sharing a common construction:

```
verse
  → NFC normalise
  → UCS-DEC encode (WIDTH/5, no wrapping)
  → SHA256 of token stream
  → interpret as 256-bit integer N
  → next_prime(N)
  → prime P
```

`mnemonic.py` is the shared library that owns this construction — the
single canonical implementation of primality testing, prime derivation,
and verse-to-prime. It is imported by the other tools; none duplicate
the construction logic.

`verse_to_prime.py` derives the prime and packages it as a self-describing
FDS Print Profile artifact. `prime_twist.py` uses a prime as a cyclic key
schedule to apply base-switching transforms to any FDS token stream.
`gloss_twist.py` applies a key-derived base-52 pre-encoding for non-Latin
scripts. `symbol_twist.py` applies a key-derived bijection for script
fingerprint camouflage. `crowsong-advisor.py` reads a UCS-DEC token stream
and recommends the optimal pipeline.

All six: Python 2.7+/3.x, no external dependencies, MIT licence.

**These are test implementations.** The CCL construction and artifact
format are not yet normatively specified. See
`drafts/draft-darley-fds-ccl-prime-twist-00.txt` for the pre-normative
specification and `docs/mnemonic-shamir-sketch.md` for the broader
Mnemonic Share Wrapping design.

---

## mnemonic.py

The shared construction library. Not a CLI tool — import only.

```python
from mnemonic import is_prime, next_prime, ucs_dec_encode, derive
```

| Export | Description |
|--------|-------------|
| `WITNESSES_SMALL` | Fixed Miller-Rabin witness tuple |
| `is_prime(n)` | Miller-Rabin primality test |
| `next_prime(n)` | Smallest prime ≥ n |
| `ucs_dec_encode(text, width)` | UCS-DEC token stream encoder |
| `derive(verse, width)` | Full verse-to-prime construction; returns dict with `normalised`, `token_stream`, `token_count`, `digest_hex`, `N`, `P`, `width` |

Primality: deterministic (no false positives) for n < ~3.3 × 10²⁴.
For larger n — including all SHA256-derived inputs (~77 digits) — this
is a well-tested heuristic using the fixed witness set. No counterexample
is known; inputs are not adversarially chosen.

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
- The prime need not be stored; it can be reconstructed deterministically
  from the verse at any time.
- Deterministic: the same verse always produces the same prime.
- The primality test is deterministic for n < ~3.3 × 10²⁴. For larger n,
  including all SHA256-derived inputs, a well-tested fixed-witness heuristic
  is used — no counterexample is known, and inputs are not adversarially
  chosen. See `mnemonic.py` for the single canonical implementation.
- The artifact carries both N and P in its RSRC block. It is a
  reproducibility artifact, not a secrecy wrapper. Confidentiality
  is a separate layer.

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

For non-Latin scripts, apply the Gloss layer before CCL — see
`gloss_twist.py` below.

### Steganographic injection

The twisted token stream consists of five-digit decimal integers.
These occur naturally in telemetry, log files, cross-reference lists,
and financial records. The stream may be injected into such containers
without modification. The receiver extracts the numeric field and pipes
it to `unstack`.

See `demo/ccl_demo.sh` for a full nine-step live demonstration.

---

## gloss_twist.py

The Gloss layer. Applies a key-derived base-52 pre-encoding to FDS token
streams before CCL. Designed for Arabic, CJK, Hangul, Hebrew, Devanagari,
Thai, and any script with code points above roughly U+0800 — scripts where
CCL's feasibility rule (base^WIDTH > token_value) structurally limits twist
rate and entropy gain.

**The problem:** For a CJK token at value 30,000, only bases 8 and 9 pass
the feasibility check. Twist rate is capped at ~22% per pass regardless of
the key schedule. Three passes of CCL add little.

**The construction:** Re-encode each token value in base 52 (A–Z a–z),
producing three output tokens per input. Output code points fall in the
ASCII letter range (65–122), where all CCL bases 3–9 are feasible on
every token.

**Key derivation:** The Gloss alphabet permutation is seeded from
SHA256 of the **reversed** digit sequence of the prime. This produces
a second independent schedule from the same prime — one prime, two
schedules, zero additional key material. 78% of digit positions differ
between the forward (CCL) and reversed (Gloss) schedules.

**Entropy gain (3-pass CCL):**

| Script | CCL3 alone | Gloss + CCL3 | Gain |
|--------|-----------|--------------|------|
| Chinese | 5.93 | **7.29** | +1.36 bits/token |
| Korean | 6.17 | **7.47** | +1.30 |
| Japanese | 6.11 | **7.24** | +1.13 |
| Arabic | 6.40 | **7.05** | +0.65 |
| Hebrew | 6.40 | **7.02** | +0.62 |
| Hindi | 6.61 | **7.09** | +0.48 |
| Russian | 6.83 | **7.28** | +0.45 |
| English | 8.16 | 7.56 | −0.60 (CCL alone preferred) |

AES-128 reference: ~7.95 bits/byte.

```bash
python gloss_twist.py gloss   [--prime P | --verse-file F] [--ref ID]
python gloss_twist.py ungloss <infile>
python gloss_twist.py info    <infile>
```

### Example pipeline (Arabic)

```bash
# Fetch UDHR Arabic and extract text
python tools/udhr/udhr.py extract arz

# Encode, gloss, twist, analyse
cat docs/udhr/Arabic/arz_Arabic.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python gloss_twist.py gloss --verse-file verses.txt \
    | python prime_twist.py stack --verse-file verses.txt --ref CCL3 \
    > arabic_ccl3.txt

# Or let the advisor choose for you
cat docs/udhr/Arabic/arz_Arabic.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python crowsong-advisor.py
```

Round-trip verified. See `docs/mnemonic/gloss-README.md` for the full
design rationale and construction details.

---

## symbol_twist.py

The Symbol layer. Applies a key-derived bijection over 62,584 eligible
Unicode code points to the FDS token value distribution. Primary purpose:
destroy script fingerprints before CCL runs.

**The threat:** UCS-DEC token value distributions leak script identity.
Arabic clusters at 01536–01791. CJK at 19968–40959. A passive observer
can identify the script — language, likely origin, subject matter — from
traffic analysis alone, before CCL is applied.

**The construction:** Keyed Fisher-Yates shuffle of 62,584 eligible Unicode
code points, seeded from SHA256(P). Each token value V maps to
`shuffled_candidates[V]`. 1:1 bijection — no expansion.

**Distinct from the Gloss layer:**

| Layer | Purpose |
|-------|---------|
| Gloss | Entropy tool — restores CCL feasibility for high-codepoint scripts |
| Symbol | Camouflage tool — masks script fingerprints in the token distribution |

```bash
python symbol_twist.py twist   [--prime P | --verse-file F] [--ref ID]
python symbol_twist.py untwist <infile>
```

---

## crowsong-advisor.py

Pipeline recommendation tool. Reads a UCS-DEC token stream on stdin,
evaluates all available pipeline modes, and outputs a ranked list from
highest to lowest predicted output entropy with copy-paste bash pipelines.

```bash
cat payload.txt | python crowsong-advisor.py
cat payload.txt | python crowsong-advisor.py --analyse
cat payload.txt | python crowsong-advisor.py --analyse --json | jq .
cat payload.txt | python crowsong-advisor.py --quiet
```

**Modes evaluated:**

1. CCL3 (standard schedule)
2. CCL3 (mod3 schedule)
3. Gloss + CCL3
4. Symbol + CCL3
5. Gloss + CCL3 (mod3)

For English, CCL3 standard wins. For Chinese, Gloss + CCL3 wins. The
advisor knows the difference and says so.

**`--analyse` flag:** Full statistical analysis of the input:
- Shannon entropy H₀ ±σ with visual bar graph
- Unicode script distribution (50+ blocks) with % bars
- CCL feasibility profile per base 2–9 with interpretation
- Token value statistics (min/max/mean/median/mode)
- Top 15 most frequent tokens decoded to characters
- ⚠ warning when most CCL bases are infeasible (Gloss recommended)

Output formats: human-readable (default), `--quiet` (table),
`--json` (pipeable to jq).

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
    ▼ next_prime(N)              ← mnemonic.py boundary
    │   prime P (77 digits)        (verse_to_prime.py packages the artifact)
    │
    ├─ forward digits of P  →  CCL key schedule (ouroboros)   ← prime_twist.py
    │
    └─ reversed digits of P →  Gloss alphabet permutation     ← gloss_twist.py
    │
    ▼ [optional] gloss_twist.py — base-52 pre-encoding
    │   for Arabic/CJK/Hangul/Hebrew/Devanagari/Thai
    │   output: ASCII letter range (65-122), all CCL bases feasible
    │
    ▼ [optional] symbol_twist.py — script fingerprint masking
    │   bijection over 62,584 eligible code points
    │
    ▼ prime_twist.py — CCL base-switching
    │   for each FDS token tᵢ:
    │     digit d = P_digits[i mod len(P)]
    │     base  b = d  if d ≥ 2 and b^width > tᵢ
    │             = 10 otherwise (fallback)
    │     output  = repr(tᵢ, base=b, width=5)
    │     record  twist_map[i] = b
    │
    ▼ twisted FDS token stream
        + RSRC block with PRIME and TWIST-MAP
        → self-describing artifact
```

Use `crowsong-advisor.py` to determine which optional layers to apply
for a given input.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/mnemonic/mnemonic.py` | Shared library: primality, verse-to-prime construction |
| `tools/mnemonic/crowsong-advisor.py` | Pipeline advisor with statistical analysis |
| `tools/ucs-dec/ucs_dec_tool.py` | FDS encode / decode / frame / verify |
| `tools/udhr/udhr.py` | UDHR multilingual corpus (37 languages, 20 scripts) |
| `tools/primes/primes.py` | Primality testing and prime generation |
| `tools/constants/constants.py` | Named constant digit generation (IV sources) |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Further reading

| Document | Notes |
|----------|-------|
| `drafts/draft-darley-fds-ccl-prime-twist-00.txt` | Pre-normative CCL spec, including §8.5 per-script entropy results |
| `docs/mnemonic/gloss-README.md` | Gloss layer design rationale and construction |
| `docs/entropy-analysis.md` | Shannon entropy measurements across 20+ languages |
| `docs/operator-worked-example.md` | Complete encode/camouflage/reveal by hand |
| `docs/mnemonic-shamir-sketch.md` | Mnemonic Share Wrapping design sketch |
| `docs/structural-principles.md` | Governing design principles |
| `demo/ccl_demo.sh` | Nine-step live demonstration |

## Compatibility

Python 2.7+ / 3.x. No external dependencies.
All tools import from `mnemonic.py` in the same directory.

## Licence

MIT. See `../../LICENSE` and `../../LICENSES.md`.

Data: digits of mathematical constants are not copyrightable.
OEIS sequence identifiers used for reference only.
