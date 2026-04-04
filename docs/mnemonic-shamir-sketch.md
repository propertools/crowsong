# Mnemonic Share Wrapping and Channel Camouflage Layer

*Design sketch — for incorporation into `draft-darley-shard-bundle-01`*

**Version:** 0.2 (pre-normative)
**Classification:** TLP:CLEAR
**Status:** Working consensus, partially implemented. This document captures
architectural direction, separation of concerns, minimum viable scope, and
open questions gating normative specification.

This is not yet a normative specification.

---

## What has been built

Since version 0.1 of this sketch the following have been implemented
as test implementations and are marked accordingly in all generated
artifacts:

| Component | Status | Location |
|-----------|--------|----------|
| Verse-to-prime derivation | ✅ implemented | `tools/mnemonic/verse_to_prime.py` |
| CCL prime-twist (single pass) | ✅ implemented | `tools/mnemonic/prime_twist.py` |
| CCL prime-twist (stack, max 10) | ✅ implemented | `tools/mnemonic/prime_twist.py` |
| CCL pre-normative spec | ✅ drafted | `drafts/draft-darley-fds-ccl-prime-twist-00.txt` |
| Named constant digit tables | ✅ generated | `docs/constants/` |
| OEIS sequence mirror | ✅ implemented | `tools/sequences/sequences.py` |
| Miller-Rabin primality | ✅ implemented | `tools/primes/primes.py` |
| CCL live demo | ✅ built | `demo/ccl_demo.sh` |

**CCL empirical results** (canonical 534-token payload, three passes):

| Stage | Entropy | Unique tokens |
|-------|---------|---------------|
| Original UCS-DEC | 4.78 bits/token | 53 |
| CCL1 | 6.96 bits/token | 172 |
| CCL2 | 7.82 bits/token | 282 |
| CCL3 | **8.37 bits/token** | 375 |
| AES-128 reference | ~7.9–8.0 bits/byte | — |

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
      additional rules: see Open Questions

3. Encode to UCS-DEC
      per draft-darley-fds-00

4. Interpret as integer
      canonical method REQUIRED (see Open Questions)

5. Derive wrapping key
      Kᵢ = KDF(mnemonic_encoded, context=share_id)

6. Wrap share
      wrapped_sᵢ = sᵢ XOR Kᵢ

7. Integrity check (REQUIRED)
      MAC or checksum over unwrapped share
      detects incorrect mnemonic reconstruction before use

8. Package
      wrapped share
      share ID
      KDF parameters
      integrity check
      optional: IV parameters if CCL applied
```

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
| MM₇ | — | Fourth Double Mersenne prime |

The IV is specified by name, not value. Public. Deterministic. Offline
reproducible. Generated by `tools/constants/constants.py`.

```
IV: PI · OFFSET/1000 · BASE/10
```

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

### Layer model

| Layer | Responsibility |
|-------|---------------|
| Shamir | Threshold security |
| Mnemonic wrapping | Human recovery |
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

### 1. KDF selection (primary gate)

Everything else waits on this.

| Candidate | Notes |
|-----------|-------|
| PBKDF2-HMAC-SHA256 | Portable, Python 2.7+, well-understood |
| HKDF | Cleaner derivation, requires HMAC |
| Minimal SHA | Simplest, lowest dependency |

**Recommendation:** PBKDF2-HMAC-SHA256. Defensible to a standards audience,
available in Python 2.7+ `hashlib`, no external dependencies.

### 2. Integer interpretation of UCS-DEC output

Must be canonical — either concatenation of token values as a decimal
string, or the token string with whitespace stripped. Both produce the same
result. Must be documented explicitly.

**Recommendation:** strip whitespace, concatenate, treat as decimal literal.

### 3. Canonicalisation rules for mnemonic input

NFC normalisation is required. Beyond that:

- Whitespace: strip outer, collapse internal to single spaces
- Punctuation: preserve
- Case: preserve
- Line endings: normalise to LF before encoding

**Recommendation:** the above. This is the minimum that allows reasonable
verse transcription tolerance without introducing ambiguity.

### 4. Mnemonic error tolerance

Strict matching is deterministic and auditable. Fuzzy matching is risky,
ambiguous, and hard to specify.

**Recommendation:** strict for `-01`. Fuzzy matching deferred.

### 5. Share packet format

Where does the wrapped share live?

- Embedded in an FDS-FRAME as a structured field
- In an `RSRC:` fork alongside an FDS payload
- As a standalone FDS artifact with its own framing

Unresolved. Likely: standalone FDS artifact with RSRC block, parallel to
the `verse_to_prime.py` artifact format.

---

## Definition of done

- [x] Verse-to-prime construction implemented and verified
- [x] CCL prime-twist implemented and verified (single pass and stack)
- [x] CCL pre-normative spec drafted
- [x] CCL transform example with test vector (canonical 534-token payload)
- [x] Named constant digit tables generated and committed
- [x] Layer separation explicit in spec and implementation
- [ ] KDF selected and documented
- [ ] Integer interpretation canonical and documented
- [ ] Canonicalisation rules specified normatively
- [ ] Mnemonic wrapping specified normatively
- [ ] Integrity check mechanism (MAC vs checksum) resolved
- [ ] Share packet format specified
- [ ] All open questions resolved or explicitly tracked in final draft

---

## One-line summary

Secrets are reconstructed, not stored.
Memory carries meaning.
Math provides coordination.
Camouflage keeps the signal from being noticed.
