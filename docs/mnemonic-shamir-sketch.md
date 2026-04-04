# Mnemonic Share Wrapping and Channel Camouflage Layer

*Design sketch — for incorporation into `draft-darley-shard-bundle-01`*

**Version:** 0.1 (pre-normative)
**Classification:** TLP:CLEAR
**Status:** Working consensus. Captures architectural direction, separation
of concerns, minimum viable scope, and open questions gating normative
specification.

This is not yet a normative specification.

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
   material
2. **Channel Camouflage Layer (CCL)** — reduces the salience of FDS
   payloads in degraded channels

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
      detects incorrect mnemonic reconstruction

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
- Improved deniability — "I don't remember which poem" is plausible
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

| Constant | Notes |
|----------|-------|
| π | Infinite, non-repeating |
| e | Euler's number |
| φ | Golden ratio |
| √2, √3 | Algebraic irrationals |
| MM₇ | Double Mersenne prime |
| OEIS sequences | Referenced by canonical ID |

The IV is specified by name, not value. Public. Deterministic. Offline
reproducible.

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

### Non-goals

CCL does not provide confidentiality, cryptographic integrity, or
authentication.

**CCL MUST NOT be relied upon for cryptographic protection of any kind.**

### Core principle

Do not hide the signal. Lower its salience.

Goal: reduce detection by passive observers, avoid prioritisation for
inspection, avoid obvious structure. Not: defeat determined adversaries.

### Construction

Input: valid UCS-DEC token stream.
Output: valid UCS-DEC token stream with the same information content.

For token `i`:

```
1. Derive schedule
      Tᵢ = f(IV_name, offset, i)

2. Apply reversible transform
      base switching
      digit regrouping
      mixed-radix encoding

3. Emit token
      MUST remain decimal
      MUST remain whitespace-delimited
      MUST remain human-transcribable
```

Transforms MUST be reversible using only declared IV parameters. MUST NOT
require external state. MUST preserve transcription stability. MUST NOT
significantly increase operator error rate.

```
IV: PI · OFFSET/1000 · BASESET/10,11,12
```

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

These gate normative specification. They are tracked here, not silently
decided.

### 1. KDF selection (primary gate)

| Candidate | Notes |
|-----------|-------|
| PBKDF2-HMAC-SHA256 | Portable, Python 2.7+, well-understood |
| HKDF | Cleaner derivation, requires HMAC |
| Minimal SHA | Simplest, lowest dependency |

**Recommendation:** PBKDF2-HMAC-SHA256.

### 2. Integer interpretation

Must be canonical — either concatenation of tokens or full decimal string.
This directly affects derived keys.

### 3. Canonicalisation rules

NFC required. Additional decisions: whitespace, punctuation, case, line
endings.

**Recommendation:** strip outer whitespace, collapse internal whitespace,
preserve punctuation, preserve case.

### 4. Mnemonic error tolerance

Strict matching is deterministic and auditable. Fuzzy matching is risky
and ambiguous.

**Recommendation:** strict for `-01`.

### 5. Share packet format

Options: FDS-FRAME embedding, `RSRC:` fork, standalone artifact.

### 6. CCL transform set

Allowed bases, scheduling strategy, degradation behaviour under error.

---

## Definition of done

- [ ] KDF selected
- [ ] Integer interpretation fixed
- [ ] Canonicalisation rules defined
- [ ] Mnemonic wrapping specified normatively
- [ ] CCL defined as non-cryptographic informative profile
- [ ] Layer separation explicit in spec
- [ ] Share packet format sketched
- [ ] CCL transform example with test vector
- [ ] All open questions resolved or explicitly tracked

---

## One-line summary

Secrets are reconstructed, not stored.
Memory carries meaning.
Math provides coordination.
Camouflage keeps the signal from being noticed.
