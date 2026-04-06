# Mnemonic Share Wrapping and Channel Camouflage Layer

*Design sketch — for incorporation into `draft-darley-shard-bundle-01`*

**Version:** 0.4 (pre-normative)
**Classification:** TLP:CLEAR
**Status:** Working consensus, partially implemented. This document captures
architectural direction, separation of concerns, minimum viable scope, and
open questions gating normative specification.

This is not yet a normative specification.

---

## What has been built

| Component | Status | Location |
|-----------|--------|----------|
| Verse-to-prime derivation | ✅ implemented | `tools/mnemonic/verse_to_prime.py` |
| CCL prime-twist (single pass and stack) | ✅ implemented | `tools/mnemonic/prime_twist.py` |
| CCL pre-normative spec | ✅ drafted | `drafts/draft-darley-fds-ccl-prime-twist-00.txt` |
| Gloss layer (non-Latin script CCL restoration) | ✅ implemented | `tools/mnemonic/gloss_twist.py` |
| Symbol layer (script fingerprint camouflage) | ✅ implemented | `tools/mnemonic/symbol_twist.py` |
| Pipeline advisor with statistical analysis | ✅ implemented | `tools/mnemonic/crowsong-advisor.py` |
| Named constant digit tables | ✅ generated | `docs/constants/` |
| OEIS sequence mirror | ✅ implemented | `tools/sequences/sequences.py` |
| Miller-Rabin primality | ✅ implemented | `tools/primes/primes.py` |
| UDHR multilingual corpus | ✅ implemented | `tools/udhr/udhr.py` |
| Binary seed derivation | 🔄 designed | `tools/mnemonic/mnemonic.py` (pending) |
| Sparse offset-addressed CCL | 🔄 designed | `tools/mnemonic/prime_twist.py` (pending) |

**CCL entropy results** (Shannon H, bits/token, three passes, ±σ):

| Script | CCL3 alone | Gloss + CCL3 | Gain |
|--------|-----------|--------------|------|
| English (ASCII) | **8.16** ±0.04 | 7.56 | −0.60 (CCL alone preferred) |
| Russian | 6.83 | **7.28** | +0.45 |
| Hindi | 6.61 | **7.09** | +0.48 |
| Hebrew | 6.40 | **7.02** | +0.62 |
| Arabic | 6.40 | **7.05** | +0.65 |
| Japanese | 6.11 | **7.24** | +1.13 |
| Korean | 6.17 | **7.47** | +1.30 |
| Chinese | 5.93 | **7.29** | +1.36 |

AES-128 reference: ~7.95 bits/byte. Theoretical max (WIDTH/5): 9.97.

The Gloss layer resolves the structural CCL limitation for high-codepoint
scripts. See `docs/mnemonic/gloss-README.md` and `docs/entropy-analysis.md`
for the full analysis.

CCL is now substantially specified. This sketch focuses on the remaining
pre-normative work: **Mnemonic Share Wrapping**.

---

## The problem this solves

Key material must survive:

- infrastructure failure
- coercion and inspection
- the limits of human memory under stress
- degraded transmission environments (fax, Morse, human relay)

Raw key material fails these constraints.

A long integer is not memorable under duress.
A named mathematical constant is indestructible.
Poetry survives what numbers do not.

This design distributes trust across human memory, public mathematical
constants, and deterministic computation. These fail differently. That is
the point.

---

## Two mechanisms, strictly separated

1. **Mnemonic Share Wrapping** — anchors Shamir shares to human-memorable
   material (pre-normative; primary focus of this document)
2. **Channel Camouflage Layer (CCL)** — reduces the salience of FDS
   payloads in degraded channels (pre-normative spec exists; see
   `drafts/draft-darley-fds-ccl-prime-twist-00.txt`)

These MUST remain strictly separated in both specification and
implementation. No layer depends on another for its correctness or for
preserving its security guarantees.

---

## 1. Mnemonic Share Wrapping

### Core principle

The mnemonic does not become the share. It unlocks the share.

Shamir's guarantees remain intact. The mnemonic derives a wrapping key;
the underlying share is unchanged. Loss of the mnemonic prevents recovery.
It does not weaken the secret beyond the threshold.

### Construction

For each Shamir share `sᵢ`:

```
1. Select mnemonic material
      verse, stanza, or canonical text fragment

2. Canonicalise
      NFC normalisation (REQUIRED)
      whitespace: strip outer, collapse internal to single space
      line endings: normalise to LF before encoding
      punctuation and case: preserve

3. Encode to UCS-DEC
      per draft-darley-fds-00
      strip whitespace, concatenate tokens, treat as decimal literal

4. Derive wrapping key
      Kᵢ = PBKDF2-HMAC-SHA256(mnemonic_encoded, context=share_id)
      iteration count: 600,000 (NIST SP 800-132, 2023)

5. Wrap share
      wrapped_sᵢ = sᵢ XOR Kᵢ

6. Integrity check (REQUIRED)
      HMAC-SHA256 over unwrapped share, keyed with sub-key from Kᵢ
      detects incorrect mnemonic reconstruction before use

7. Package
      wrapped share
      share ID
      KDF parameters (algorithm, iteration count)
      HMAC value
      optional: IV parameters if CCL applied
```

### Resolved design decisions

**KDF:** PBKDF2-HMAC-SHA256. Defensible to a standards audience, available
in Python 2.7+ `hashlib`, no external dependencies.

**Iteration count:** 600,000 (NIST SP 800-132, 2023). Must be declared in
the RSRC block to allow future increases without breaking existing artifacts.

**Integer interpretation:** strip whitespace from the UCS-DEC token stream,
concatenate token values, treat as decimal literal. Canonical and
deterministic.

**Canonicalisation:** NFC normalisation required. Strip outer whitespace,
collapse internal runs to single spaces, preserve punctuation and case,
normalise line endings to LF before encoding. This is the minimum that
allows reasonable verse transcription tolerance without introducing
ambiguity.

**Mnemonic error tolerance:** strict matching for `-01`. Fuzzy matching
deferred to a later revision.

### Properties

- Shamir security intact — mnemonic ≠ share
- Human survivability — verse outlasts hardware
- No raw share is memorised or transmitted
- Improved deniability — "I don't remember which poem" is plausible and
  unverifiable
- Recovery possible from memory if share packet survives

### Coercion model

Coercion surface: *which mnemonic, which share packet, which reconstruction
context* — not the key itself.

The reconstruction key is never stored or transmitted directly. The mnemonic
and the key are semantically linked but computationally separated. This
separation is structural.

### Minimal 3/3 construction

| Share | Material | Character |
|-------|----------|-----------|
| 1 | Named constant (IV) | Public, indestructible |
| 2 | First verse → K₁ | Memorable, deniable |
| 3 | Second verse → K₂ | Memorable, deniable |

All three are required. The master key exists nowhere until reconstruction.

### Book code dimension

If mnemonics are drawn from published works, key material exists globally.
Destruction of devices does not destroy the mnemonic. Recovery remains
possible. The signal survives because the medium cannot erase literature.

The UDHR corpus (`docs/udhr/`, 560+ translations via `tools/udhr/udhr.py`)
is an operationally useful mnemonic source: the same text exists in every
language, professionally translated, memorisable in one's native tongue,
globally retrievable, and present in the internet archive. A verse memorised
from the UDHR in Amharic or Tibetan is genuinely obscure to a border agent —
and recoverable from any library in the world.

### Named constants as IV

The IV anchors the public component of the 3/3 construction. Pre-generated
digit tables for the following constants are in `docs/constants/`:

| Constant | OEIS | Notes |
|----------|------|-------|
| π | A000796 | Infinite, non-repeating |
| e | A001113 | Euler's number |
| φ | A001622 | Golden ratio |
| √2 | A002193 | First known irrational |
| √3 | A002194 | |
| ln(2) | A002162 | |
| ζ(3) | A002117 | Apery's constant |
| MM₇ | — | Fourth Double Mersenne prime (Serafina Tauform) |

The IV is specified by name, not value. Public. Deterministic. Offline
reproducible. Generated by `tools/constants/constants.py`.

```
IV: PI · OFFSET/1000 · BASE/10
```

### Binary seed: non-mnemonic key material

The verse-to-prime construction assumes a human-memorable mnemonic.
A parallel construction accepts raw bytes — any binary artifact — as
the seed:

```
bytes (PNG, audio, document, ...)
  → SHA256
  → integer N
  → next_prime(N)
  → prime P
```

No NFC normalisation. No UCS-DEC encoding. Bytes are bytes. The
construction is identical downstream.

| Property | Verse mnemonic | Binary seed |
|----------|---------------|-------------|
| Recovery mechanism | Human memory | Artifact possession |
| Ambiguity | Possible (transcription) | None (exact bytes) |
| Deniability | High ("I don't remember which poem") | Lower |
| Entropy of seed | Low (natural language) | High (image, audio) |
| Survives hardware loss | Yes — if memorised | Only if redundantly stored |

A binary seed is not a mnemonic. It is a **possession-based key
derivation object**. Call it that in both spec and implementation.
Do not treat it as equivalent to a verse.

### Sparse corpus addressing — the cross-border construction

The prime derived from any seed (verse or binary) can be used to address
specific byte offsets within a named public corpus — the mathematical
constants and OEIS sequences in `docs/constants/` and `docs/sequences/`.

**The construction:**

```
prime P (from verse or binary seed)
  + named sequence (e.g. π, A000796)
  + window size k
  → deterministic sparse address walk over the sequence
  → extracts one byte per step at addressed positions
  → those bytes → key material for share reconstruction
```

The address walk:

```
digits of P taken in windows of k
  each window W → integer offset into sequence
  sequence[offset : offset+1] → byte extracted
  collision (already visited) → skip, continue
  repeat until floor(len(P_digits) / k) steps exhausted
```

The key material is already out there. It is inaccessible without knowing
which prime, which sequence, which window size.

**The cross-border 3/3 construction:**

```
Share 1: named constant (IV)                  public, indestructible
Share 2: verse memorised before travel        → prime P₁
                                              → addresses bytes in π
Share 3: image posted publicly years ago      → prime P₂ (binary seed)
                                              → addresses bytes in A000796
```

The adversary at the border sees:
- No key material (it is in memory and on a public server)
- No share (it is derived on demand)
- No prime (it exists nowhere until derived)
- The corpus is public — possessing it proves nothing

The coercion surface is: *which verse, which image, which sequence,
which offset.* Not the key itself.

**Empirical results (The Barking Floyd test):**

Binary seed: a 2.1MB PNG → SHA256 → prime `16854375336399765067...`
(77 digits). Applied as sparse addressing (k=3, first-hit) over a
canonical FDS payload:

- 25 addressing steps from 77 prime digits
- 24 positions hit (4.5% coverage), 1 collision skipped
- Deterministic: same image always produces same prime and same address
  pattern
- Avalanche: one flipped byte → 71% divergence in addressed positions

Sparse addressing alone is not a workhorse for entropy. It is a
**key-dependent extraction function**. The right pipeline is:

```
sparse addressing (keyed corpus extraction) → key material
sequential CCL (entropy redistribution)     → camouflage
```

These serve different purposes and are independently useful.

**Declared parameters (RSRC block):**

```
ADDRESSING:  sparse-offset
SEED-TYPE:   verse | binary-seed
SEQUENCE:    PI | A000796 | ...   (named corpus source)
WINDOW:      3                    (digits per addressing step)
COLLISION:   first-hit
STEPS:       25                   (floor(len(P_digits) / k))
```

**Concrete example — corporate logos as binary seeds:**

```
SHA256(microsoft_logo.png) → P₁ → addresses bytes in π
SHA256(google_logo.png)    → P₂ → addresses bytes in e
SHA256(apple_logo.png)     → P₃ → addresses bytes in φ
P₁ + P₂ + P₃ → three Shamir shares → master key
```

The logos are public, on every website, retrievable from the internet
archive. Possessing them proves nothing. Everyone has them.

The secret is: *which logos, which versions, which order, which sequence,
which offset.* That is knowledge, not data. It is not written down
anywhere. It is recoverable from memory and from the internet archive.

The Google logo changed in 2015. The Microsoft logo changed in 2012.
Which version is part of the secret.

Properties of this construction:
- Publicly available seeds — retrievable by anyone
- Culturally indestructible — these files will exist for decades
- Version-sensitive — which revision is the secret
- Order-sensitive — P₁, P₂, P₃ in a specific sequence
- Individually unremarkable — possessing any one proves nothing
- Jointly specific — the combination is held only in memory
- Deniable — "I just had some logo files" is entirely plausible

**Status:** binary seed derivation implemented in `mnemonic.py`
(pending). Sparse addressing construction designed; implementation
in progress. Normative specification deferred pending empirical
validation of coverage and extraction quality.

### Connection to Principle 12 (timestamps as claims)

If timestamps are used as offsets into the named constant, they live in
the discardable outer layer per Structural Principle 12. A bad clock
degrades security, not recoverability. Fallback: `OFFSET/0`. The system
degrades gracefully.

---

## 2. Channel Camouflage Layer (CCL)

The prime-twist CCL construction has been implemented and is pre-normatively
specified. This section summarises the key properties; the full specification
is in `drafts/draft-darley-fds-ccl-prime-twist-00.txt`.

**What CCL does:** applies prime-derived base-switching to FDS token streams,
cycling through the prime's digit sequence as a key schedule (the ouroboros).
Output remains valid UCS-DEC. The twist-map is stored in the artifact RSRC
block and is required for reversal.

**What CCL does not provide:** confidentiality, integrity, authentication.
CCL MUST NOT be relied upon for cryptographic protection of any kind.

**Relationship to Mnemonic Share Wrapping:** CCL and Mnemonic Share Wrapping
are composable but strictly independent. A verse used as a CCL key via
`verse_to_prime.py` may also serve as a mnemonic for Share Wrapping, but
the two constructions MUST NOT be conflated. Wrap shares first; apply CCL
to the encoded output independently.

### Gloss layer

For Arabic, CJK, Hangul, Hebrew, Devanagari, Thai, and any script with
code points above roughly U+0800, apply the Gloss layer before CCL. The
Gloss layer re-encodes each UCS-DEC token value in base 52 (A–Z a–z),
producing three output tokens per input. Output code points fall in the
ASCII letter range (65–122), where all CCL bases 3–9 are feasible on
every token.

Key derivation for the Gloss alphabet permutation uses the **reversed**
digit sequence of the prime — producing a second independent schedule
from the same prime with zero additional key material. 78% of digit
positions differ between the forward (CCL) and reversed (Gloss) schedules.

Use `tools/mnemonic/crowsong-advisor.py` to determine the optimal pipeline
for a given input:

```bash
cat docs/udhr/Arabic/arz_Arabic.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/crowsong-advisor.py
```

### Layer model

| Layer | Responsibility |
|-------|---------------|
| Shamir | Threshold security |
| Mnemonic wrapping | Human recovery |
| Gloss | CCL feasibility for non-Latin scripts |
| CCL | Salience reduction |
| FDS | Transport encoding |

No layer depends on another for correctness or security guarantees.

---

## Provenance

Derived from `credmgr` (2012): Shamir sharing, GPG transport, human-held
trust. The evolution is from encrypted transport to human-survivable
reconstruction. Same problem. Cleaner expression.

---

## Open questions

The following gate normative specification of Mnemonic Share Wrapping.
CCL open questions are tracked in `drafts/draft-darley-fds-ccl-prime-twist-00.txt`
§11.

### 1. KDF iteration count

KDF selection is resolved (PBKDF2-HMAC-SHA256). The open question is
iteration count. Recommendation: 600,000 (NIST SP 800-132, 2023). Must be
declared in the RSRC block to allow future increases without breaking
existing artifacts. Final value must be documented normatively in `-01`.

### 2. Integrity check mechanism

| Option | Notes |
|--------|-------|
| HMAC-SHA256 | Cryptographically strong; requires key material |
| BLAKE3 | Fast, keyed mode available; no Python stdlib |
| SHA256 truncated | Simple; not a MAC; no authentication |

**Recommendation:** HMAC-SHA256 over the unwrapped share, keyed with a
sub-key derived from Kᵢ. This is the minimum that detects incorrect
mnemonic reconstruction before use. Needs formal specification.

### 3. Share packet format

Where does the wrapped share live?

- Embedded in an FDS-FRAME as a structured field
- In an `RSRC:` fork alongside an FDS payload
- As a standalone FDS artifact with its own framing

Unresolved. Likely: standalone FDS artifact with RSRC block, parallel to
the `verse_to_prime.py` artifact format.

### 4. Sparse addressing coverage floor

The Barking Floyd test showed 4.5% coverage (24/25 positions hit, k=3,
77 prime digits). Is this sufficient for key material? What is the minimum
coverage floor for safe use? Deferred pending empirical validation over
larger corpora and a range of prime lengths.

---

## Definition of done

- [x] Verse-to-prime construction implemented and verified
- [x] CCL prime-twist implemented and verified (single pass and stack)
- [x] CCL pre-normative spec drafted
- [x] Gloss layer implemented (non-Latin scripts, +0.45–+1.36 bits/token)
- [x] Symbol layer implemented (script fingerprint camouflage)
- [x] Entropy analysis across 20+ languages documented
- [x] Named constant digit tables generated and committed
- [x] Binary seed construction designed and empirically tested
- [x] Sparse corpus addressing construction designed
- [x] UDHR multilingual corpus operational (560+ translations, 25+ scripts)
- [x] Layer separation explicit in spec and implementation
- [x] KDF selection resolved (PBKDF2-HMAC-SHA256)
- [x] Integer interpretation canonical and documented
- [x] Canonicalisation rules specified
- [ ] KDF iteration count finalised and declared in RSRC schema
- [ ] Mnemonic wrapping specified normatively
- [ ] Integrity check mechanism specified normatively
- [ ] Share packet format specified
- [ ] Sparse addressing normative coverage floor established
- [ ] All remaining open questions resolved or explicitly tracked in draft

---

## One-line summary

Secrets are reconstructed, not stored.
Memory carries meaning.
Math provides coordination.
Camouflage keeps the signal from being noticed.
