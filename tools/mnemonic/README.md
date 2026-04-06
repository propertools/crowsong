# tools/mnemonic/ — verse-derived keys, Channel Camouflage Layer, and Haiku Machine

Seven files sharing a common construction:

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

All seven tools use one prime, two schedules, zero additional key material:

| Tool | Forward digits | Reversed digits |
|------|----------------|-----------------|
| `prime_twist.py` | CCL base-switching schedule | — |
| `gloss_twist.py` | (uses prime_twist.py for CCL) | Gloss alphabet permutation |
| `haiku_twist.py` generate | Syllable count schedule | Word selection seed |
| `haiku_twist.py` encode-stream | Fisher-Yates corpus permutation (SHA256 of P) | — |

The pattern is the same throughout the stack. Different purposes, same
construction discipline.

All seven: Python 2.7+/3.x, no external dependencies, MIT licence.

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
  GENERATED:2026-04-06
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

### Stacking

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

For non-Latin scripts, apply the Gloss layer before CCL.

### Schedules

| Schedule | Rule | Use case |
|----------|------|---------|
| `standard` | `d → base d` (2–9), fallback base 10 | WIDTH/5 natural language |
| `mod3` | `d → 7 + (d mod 3)`, always 7–9 | WIDTH/3 binary payloads |

---

## gloss_twist.py

The Gloss layer. Applies a key-derived base-52 pre-encoding to FDS token
streams before CCL. Required for Arabic, CJK, Hangul, Hebrew, Devanagari,
Thai, and any script with code points above roughly U+0800.

**The problem:** For a CJK token at value 30,000, only bases 8–9 pass
the feasibility check. Twist rate is capped at ~22% per pass regardless
of the key schedule. Three passes of CCL add little.

**The construction:** Re-encode each token value in base 52 (A–Z a–z),
producing three output tokens per input. Output code points fall in the
ASCII letter range (65–122), where all CCL bases 3–9 are feasible on
every token.

**Key derivation:** The Gloss alphabet permutation is seeded from
SHA256 of the **reversed** digit sequence of the prime. One prime, two
schedules, zero additional key material.

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
python gloss_twist.py gloss   [--prime P | --verse FILE] [--ref ID]
python gloss_twist.py ungloss <infile>
python gloss_twist.py info    <infile>
```

### Example pipeline (Arabic)

```bash
cat docs/udhr/Arabic/arz_Arabic.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python gloss_twist.py gloss --verse verses.txt \
    | python prime_twist.py stack --verse-file verses.txt --ref CCL3 \
    > arabic_ccl3.txt
```

---

## symbol_twist.py

The Symbol layer. Applies a key-derived bijection for script fingerprint
camouflage before CCL runs.

**The threat:** UCS-DEC token value distributions leak script identity.
Arabic clusters at 01536–01791. CJK at 19968–40959. A passive observer
can identify the script from traffic analysis alone.

**Distinct from the Gloss layer:**

| Layer | Purpose |
|-------|---------|
| Gloss | Entropy tool — restores CCL feasibility for high-codepoint scripts |
| Symbol | Camouflage tool — masks script fingerprints in token distribution |

```bash
python symbol_twist.py twist   [--key-prime P | --key-verse FILE] [--ref ID]
python symbol_twist.py untwist <infile>
python symbol_twist.py info    <infile>
```

---

## haiku_twist.py

The Haiku Machine. Two modes:

**generate / chain / verify / decode** — prime-driven haiku generation.
The verse-derived prime drives syllable count selection and word selection
within bins. Output is a self-describing haiku artifact. The format eats
its own output (ouroboros chain).

**encode-stream / decode-stream** — word-space camouflage of arbitrary
token streams. Any UCS-DEC token stream (e.g. CCL3 output) is encoded as
real English words structured as repeating 5-7-5 haiku stanzas. Output
looks like poetry. Reversal is exact.

**Dedicated to Felix 'FX' Lindner (1975–2026).**
*The signal strains, but never gone.*

### Construction: generate

```
verse -> prime P
  forward digits  -> syllable count schedule  (digit mod 5 + 1)
  reversed digits -> word selection within bin (SHA256-seeded)
```

For each word slot `i`:

```
s    = (P_digits_forward[i mod len(P)] mod 5) + 1   # syllable count [1-6]
seed = SHA256(P_digits_reversed[i mod len(P)] : i : s)
word = bins[s][seed mod len(bins[s])]
```

### Construction: encode-stream

```
prime P -> SHA256(P) -> Fisher-Yates permutation of corpus (~134k words)
token value V -> permuted_index[V % corpus_size]
reversal: word -> position in permuted_index -> token value
```

The corpus is public. The prime is the secret. Output is structured as
repeating 5-7-5 stanzas using each word's natural syllable count.

### The ouroboros

```
verse₁ → P₁ → haiku₁
haiku₁ → (as verse) → P₂ → haiku₂
haiku₂ → P₃ → haiku₃  ...
```

### Canonical test vector

Verse (K1):
```
Factoring primes in the hot sun, I fought Entropy — and Entropy won.
```

The first verse of "Second Law Blues" by T. Darley — the poem dedicated
to FX. K1 is the canonical CCL test prime throughout the Crowsong stack.
The same prime generates both the canonical CCL test artifacts and the
canonical haiku. The encoding eats its own attribution. This seemed
appropriate.

Canonical test haiku: `archive/haiku-canonical-001.txt`

### Usage

```bash
# Haiku generation
python haiku_twist.py --bins FILE generate [--prime P] [--ref ID]
python haiku_twist.py --bins FILE chain    [--steps N] [--output FILE]
python haiku_twist.py --bins FILE verify   <artifact>
python haiku_twist.py         decode       <artifact>

# Word-space stream encoding
python haiku_twist.py --bins FILE encode-stream [--prime P | --verse FILE] [--ref ID]
python haiku_twist.py --bins FILE decode-stream <artifact>
```

`--bins` is a global flag and must come before the subcommand.
Default: `docs/cmudict/bins.json`

### Quick start: haiku generation

```bash
python tools/cmudict/cmudict.py fetch
python tools/cmudict/cmudict.py export

echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
    python haiku_twist.py --bins docs/cmudict/bins.json generate --ref HAIKU-K1 \
    > archive/haiku-canonical-001.txt

python haiku_twist.py --bins docs/cmudict/bins.json \
    verify archive/haiku-canonical-001.txt

echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
    python haiku_twist.py --bins docs/cmudict/bins.json chain --steps 7
```

### Full pipeline: arbitrary text → haiku poetry → back

```bash
# Encode
cat archive/second-law-blues.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt --no-symbol-check --ref CCL3 \
    | python tools/mnemonic/haiku_twist.py --bins docs/cmudict/bins.json \
        encode-stream --verse verses.txt --ref STREAM-001 \
    > archive/second-law-blues-haiku.txt

# Decode
python tools/mnemonic/haiku_twist.py --bins docs/cmudict/bins.json \
    decode-stream archive/second-law-blues-haiku.txt \
    | python tools/mnemonic/prime_twist.py unstack - \
    | python tools/ucs-dec/ucs_dec_tool.py --decode
```

### Artifact formats

**haiku-twist** (generate):
```
RSRC: BEGIN
  TYPE:         haiku-twist
  PRIME:        11527664883411634260504727650961...
  CORPUS:       bins.json
  PATTERN:      5-7-5
  SYLLABLES:    2 3 1 2 2 3 1 2 2 1 2 2 1
  WORD-INDEX:   2:1847 3:4201 1:892 ...
  DEDICATION:   Dedicated to Felix 'FX' Lindner (1975-2026).
RSRC: END
```

**haiku-stream** (encode-stream):
```
RSRC: BEGIN
  TYPE:         haiku-stream
  PRIME:        11527664883411634260504727650961...
  CORPUS:       bins.json
  CORPUS-SIZE:  134212
  ENCODING:     keyed-permutation / Fisher-Yates / SHA256(P)
  TOKENS:       534
  CRC32-TOKENS: E8DC9BF3
  DEDICATION:   Dedicated to Felix 'FX' Lindner (1975-2026).
RSRC: END
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
    ▼ next_prime(N)                  ← mnemonic.py boundary
    │   prime P (77 digits)
    │
    ├─ forward digits of P
    │   ├─ CCL key schedule          ← prime_twist.py
    │   └─ Syllable count schedule   ← haiku_twist.py generate
    │
    └─ reversed digits of P
        ├─ Gloss alphabet permutation  ← gloss_twist.py
        └─ Word selection seed         ← haiku_twist.py generate

    SHA256(P) → Fisher-Yates corpus permutation ← haiku_twist.py encode-stream
        token value V → permuted_index[V % corpus_size]


Encoding pipeline (FDS):
    [optional] gloss_twist.py    — base-52 pre-encoding (non-Latin scripts)
    [optional] symbol_twist.py   — script fingerprint camouflage
    prime_twist.py               — CCL base-switching
    [optional] haiku_twist.py    — word-space camouflage (encode-stream)
    → self-describing artifact with RSRC block

Haiku generation pipeline:
    haiku_twist.py generate      — 5-7-5 from prime + cmudict bins
    haiku_twist.py chain         — ouroboros chain, N steps
    → self-describing artifact with RSRC block
```

Use `crowsong-advisor.py` to determine which encoding pipeline layers
to apply for a given input.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/mnemonic/mnemonic.py` | Shared library: primality, verse-to-prime |
| `tools/mnemonic/crowsong-advisor.py` | Pipeline advisor with statistical analysis |
| `tools/cmudict/cmudict.py` | CMU dict mirror; syllable bins for haiku_twist |
| `tools/ucs-dec/ucs_dec_tool.py` | FDS encode / decode / frame / verify |
| `tools/udhr/udhr.py` | UDHR multilingual corpus (37 languages, 20 scripts) |
| `tools/primes/primes.py` | Primality testing and prime generation |
| `tools/constants/constants.py` | Named constant digit generation (IV sources) |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/baseconv/baseconv.py` | Base conversion utility |

## Further reading

| Document | Notes |
|----------|-------|
| `drafts/draft-darley-fds-ccl-prime-twist-00.txt` | Pre-normative CCL spec |
| `docs/mnemonic/gloss-README.md` | Gloss layer design rationale |
| `docs/entropy-analysis.md` | Shannon entropy measurements across 20+ languages |
| `docs/operator-worked-example.md` | Complete encode/camouflage/reveal by hand |
| `docs/mnemonic-shamir-sketch.md` | Mnemonic Share Wrapping design sketch |
| `docs/structural-principles.md` | Governing design principles |
| `demo/ccl_demo.sh` | Nine-step live demonstration |

## Compatibility

Python 2.7+ / 3.x. No external dependencies.
All tools import from `mnemonic.py` in the same directory.
`haiku_twist.py` additionally requires `docs/cmudict/bins.json`.

## Licence

MIT. See `../../LICENSE` and `../../LICENSES.md`.

*One prime. Two schedules. Infinite poems.*
*Signal survives. 🦊🌻*
