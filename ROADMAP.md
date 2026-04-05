# Crowsong — Roadmap

*Working document — updated as scope is confirmed.*

---

## Design intent

This is not a feature list. It is a sequencing discipline.

Each horizon has a single governing constraint:

| Horizon | Constraint |
|---------|-----------|
| Near (`-01`) | Make the system honest: what is specified must exist |
| Mid (`-02`) | Make the system complete: what is implied must be specified |
| Far (future drafts) | Make the system extensible: what is needed must be designed |

---

## Near horizon — `draft-darley-fds-01`

**Theme: coherence release.** Close the gap between spec and implementation.

No expansion. New functionality only where the system is incomplete without it.

### Implementation

| # | Item | Status | Rationale |
|---|------|--------|-----------|
| 1 | NFC normalisation in `encode()` | ✅ done (`-00`) | Required for canonical reproducibility; compliance with §2.1 |
| 2 | Frame-aware FDS-FRAME parser | ✅ done (`-00`) | Primary gap between spec and tool; §8.1 steps 1 and 4 |
| 3 | Frame-aware `--decode` | ✅ done (`-00`) | Uses extracted WIDTH/COL/PAD, not hardcoded defaults |
| 4 | `--verify` enforcement | ✅ done (`-00`) | Count + CRC32 + DESTROY semantics per §3.4 |
| 5 | WIDTH/3 BINARY mode | ⬜ todo | Implement alongside spec section; Class D channel requirement; CCL schedule for WIDTH/3 must be resolved first (draft-darley-fds-ccl-prime-twist-00 §11.4) |

**CLI decision:** resolved. Frame awareness is automatic in `--decode` and
`--verify`; no `--strict` flag needed.

**Full cycle requirement:** ✅ verified — `--frame` → `--decode` → diff
round-trips cleanly; tested in suite.

### Specification

| # | Item | Status | Rationale |
|---|------|--------|-----------|
| 6 | Resource fork (minimal) | ⬜ todo | `RSRC: BEGIN/END`, dependency-based ordering, interrupted transmission guarantees |
| 7 | WIDTH/3 BINARY mode | ⬜ todo | Byte-stream encoding; `BINARY` flag in `ENC:` header; decoder emits raw bytes; CCL base schedule requires separate resolution (see CCL draft §11.4) |
| 7a | Content-addressable artifact identity | ⬜ todo | SHA256 of UCS-DEC body in header as version identifier; enables diff/delta transmission at the representation layer |
| 7b | Delta transmission format | ⬜ todo | Token-level diff (FROM: sha256, TO: sha256, DELTA: UCS-DEC encoded diff); human-applicable by hand on Class D channels; receiver verifies arrival hash |
| 8 | Structural Principles: Principle 11 | ✅ done (`-00`) | SHOULD as design smell; optionality via composable components |
| 9 | Structural Principles: Principle 12 | ✅ done (`-00`) | Timestamps as claims; discardable outer layer |
| 10 | Structural Principles: Principle 13 | ✅ done (`-00`) | Availability and integrity before confidentiality |
| 11 | Housekeeping pass | ⬜ todo | Cross-references, implementation section, transport matrix |

### Cross-document

| # | Item | Status | Target draft |
|---|------|--------|-------------|
| 12 | Human coordination layer | ⬜ todo | `draft-darley-crowsong-01` |

Covers: talking stick model, priority signalling (EMERGENCY / URGENT / ROUTINE),
distributed moderation, operator attestation.
Status: informative section, 1–2 pages.

### Test suite

| Test | Status |
|------|--------|
| NFC normalisation stability | ✅ done (`-00`) |
| Full generate-and-parse cycle (`--frame` → `--decode` → diff) | ✅ done (`-00`) |
| `--verify` on framed artifacts (count + CRC32) | ✅ done (`-00`) |
| Corruption test (DESTROY flag + verification failure → non-zero exit) | ✅ done (`-00`) |
| WIDTH/3 BINARY roundtrip | ⬜ todo |
| Resource fork roundtrip | ⬜ todo |

### Protocol versioning — design principle

The 2038 problem exists because a design assumption (32-bit time_t)
was baked into implementations without a versioning or replacement
mechanism. When the assumption became wrong there was no graceful
path — only flag day or flag decade.

The structural lesson: every component that makes an assumption about
representation, encoding, or protocol semantics must declare that
assumption explicitly and version it, such that a replacement
component can be introduced without requiring simultaneous upgrade of
everything that depends on it.

For Crowsong this means every artifact carries machine-readable version
fields for every component it references:

```
VERSION:  1
ENCODING: UCS-DEC/1
CCL:      prime-twist/1
SCHEDULE: standard/1
```

A tool that encounters `CCL: prime-twist/2` it does not understand
MUST fail loudly and explicitly, not silently misinterpret.

**The modular composability guarantee:** if each layer declares its
version and each tool checks it, the CCL construction can be upgraded
without touching FDS, the schedule can be upgraded without touching
CCL, the prime derivation can be upgraded without touching anything
downstream. The interfaces are the stable thing; the implementations
behind them are replaceable.

The RSRC block is the right mechanism — it is a self-describing
metadata layer that carries version information for every component
it references. An artifact found in a Vesper archive in 2038 can be
read by looking at the RSRC block to determine exactly what version
of every component was used to produce it.

This is not just documentation hygiene. It is the structural design
pattern that avoids repeating 2038.

**Implementation requirement:** all reference implementations MUST
be versioning-aware from the first release. Retrofitting versioning
is exactly the failure mode we are designing around.

### Definition of done

- [x] NFC normalisation implemented and tested
- [x] Frame parser implemented; `--decode` uses extracted parameters
- [x] Full generate-and-parse cycle tested
- [x] `--verify` enforces count + CRC32 + DESTROY semantics
- [x] Test suite expanded and passing
- [x] Canonical artifacts verified unchanged post-NFC
- [x] Structural Principles updated (Principles 11, 12, and 13)
- [ ] Resource fork section complete
- [ ] WIDTH/3 BINARY section and implementation complete
- [ ] Human coordination section added to Crowsong draft
- [ ] Cross-references verified
- [ ] RFC `.txt` regenerated
- [ ] Tag: `v0.1-crowsong-01`

### Execution plan

```text
Phase 1 — Implementation (complete)
  ✅ NFC normalisation
  ✅ Frame parser + frame-aware --decode
  ✅ Full cycle test
  ✅ Test suite updates
  ✅ Canonical artifacts verified unchanged

Phase 2 — Specification (~2 hours)
  Resource fork section
  WIDTH/3 BINARY section + implementation
  Housekeeping pass

Phase 3 — Crowsong integration (~1 hour)
  Human coordination layer
  Terminology alignment with fds-01

Phase 4 — Release (~30 min)
  RFC .txt regeneration
  README updates
  Tag
```

---

## Mid horizon — `draft-darley-fds-02` and peers

**Theme: completeness release.** Specify what the near horizon implies but defers.

| Item | Notes |
|------|-------|
| Full FDS-FTP spec | Multipart, resumability, retransmission request format |
| MIME type quick reference appendix | Companion to FDS Unicode reference table |
| Morse grouping conventions for WIDTH/3 BINARY | Prosign-friendly chunking; operator fatigue; error recovery |
| Story infrastructure | `story/ghost-line.md`, prose PR model, decomposition log — develop in parallel with `-01`, not gated on tag |
| Aeolian Layer draft | `draft-darley-aeolian-dtn-arch-01` — its own document, its own timeline |
| Mnemonic Share Wrapping | `draft-darley-shard-bundle-01` — verse-derived KDF unlocks Shamir shares; see design sketch |
| Channel Camouflage Layer (CCL) | Informative profile; prime-twist test implementation complete; normative spec pending KDF selection |
| Duress decoy forks | Multi-fork FDS artifacts with per-fork verse-derived keys; plausible deniability at hostile border crossings; see design note below |

### Mnemonic Share Wrapping and CCL — design status

Working consensus: two mechanisms, strictly separated.

**Mnemonic Share Wrapping** (normative, `draft-darley-shard-bundle-01`)

Anchors Shamir share recovery to human-memorable material. The mnemonic
unlocks the share; it does not become the share. Shamir security guarantees
remain intact.

```
Secret S → Shamir split → share sᵢ
                               ↓
                    mnemonic input (verse, NFC-normalised)
                               ↓
                    Kᵢ = KDF(mnemonic, context=share_id)
                               ↓
                    wrapped_sᵢ = sᵢ XOR Kᵢ
```

Coercion surface: *which verse, which share packet, which context* — not
the key itself. The reconstruction key is never stored or transmitted
directly.

A checksum or MAC over the unwrapped share is REQUIRED to detect incorrect
mnemonic reconstruction.

**Channel Camouflage Layer** (informative, CCL)

CCL provides no confidentiality or integrity guarantees and MUST NOT be
relied upon for cryptographic protection. CCL transforms MUST be reversible
without external state beyond the declared IV parameters. Reduces the visual
and statistical salience of FDS payloads. Reversible deterministic transforms
driven by a named public IV. Output remains valid UCS-DEC. Transforms MUST
preserve transcription stability; increased apparent entropy MUST NOT
significantly increase operator error rates.

```
IV: PI · OFFSET/1000 · BASESET/10,11,12 (public, deterministic)
```

Layer separation is strict and MUST be maintained in both spec and
implementation:

| Layer | Responsibility |
|-------|---------------|
| Shamir | Threshold security |
| Mnemonic wrapping | Human recovery |
| CCL | Visual/statistical camouflage |
| FDS | Transport encoding |

No layer depends on another for its correctness or for preserving its
security guarantees.

**Key open question (gates everything else):** KDF selection. PBKDF2 is
the leading candidate due to portability and Python 2.7 compatibility.
Must be resolved before mnemonic wrapping can be specified normatively.

**One-line summary:**
*Secrets are reconstructed, not stored. Memory carries meaning.
Math provides coordination. Camouflage keeps the signal from being noticed.*

### Mnemonic and CCL toolchain — implementation status

Pre-normative test implementations exist and are verified.
Marked `TEST IMPLEMENTATION — not normatively specified` in all artifacts.
Refactor into reference implementation pending normative spec.

| Tool | Status | Notes |
|------|--------|-------|
| `tools/primes/primes.py` | ✅ done | Deterministic Miller-Rabin; `is-prime`, `next-prime`, `first`, `range` |
| `tools/constants/constants.py` | ✅ done | 8 named constants; `list`, `digits`, `show`, `generate`, `verify` |
| `tools/sequences/sequences.py` | ✅ done | 15 OEIS sequences; `list`, `show`, `terms`, `sync`, `verify` |
| `tools/baseconv/baseconv.py` | ✅ done | Bases 2–36; CLI and library |
| `tools/mnemonic/mnemonic.py` | ✅ done | Shared library: `is_prime`, `next_prime`, `ucs_dec_encode`, `derive`; single canonical construction |
| `tools/mnemonic/verse_to_prime.py` | ✅ done | verse → NFC → UCS-DEC → SHA256 → next\_prime → FDS artifact; imports from `mnemonic.py` |
| `tools/mnemonic/prime_twist.py` | ✅ done | CCL prime-twist; `twist`, `untwist`, `stack` (max 10), `unstack`; imports from `mnemonic.py` |
| `demo/ccl_demo.sh` | ✅ done | 9-step live demo; canonical payload; CCL3 achieves 8.37 bits/token |
| `docs/constants/` | ✅ done | Pre-generated 10,000-digit files for all 8 constants |
| `docs/sequences/` | ✅ done | Cached OEIS sequences, SHA256-verified |
| `docs/mnemonic-shamir-sketch.md` | ✅ done | Pre-normative design sketch; open questions tracked |

**CCL3 entropy results on canonical 534-token payload (WIDTH/5):**

| Stage | Entropy | Unique tokens |
|-------|---------|---------------|
| Original UCS-DEC | 4.78 bits/token | 53 |
| CCL1 | 6.96 bits/token | 172 |
| CCL2 | 7.82 bits/token | 282 |
| CCL3 | **8.37 bits/token** | 375 |
| AES-128 reference | ~7.9–8.0 bits/byte | — |

CCL3 exceeds the AES-128 reference. Output is statistically
indistinguishable from professional cryptographic output to heuristic
analysis. Five-digit decimal tokens are injected directly into plausible
side-channel containers (telemetry CSV, log files, cross-reference lists)
without modification.

**Compression interaction (WIDTH/5):** Prior compression via base64 yields
marginal gains (+0.13 to +0.19 bits/token) due to the base64 alphabet ceiling
at log₂(65) ≈ 6.02 bits/token. For natural language, skip compression. For
binary payloads, use the FDS B64 pipeline. See CCL draft §8.3.

**WIDTH/3 BINARY + CCL — open question (gates implementation):**

The standard CCL base schedule (bases 2–9) performs poorly at WIDTH/3
because scheduled bases 2–6 fail the feasibility check for most byte values
(base^3 ≤ 255), collapsing the effective twist rate to ~50% or less.

Empirical results with proposed `mod3` schedule (digit mod 3 → base 7/8/9,
100% twist guaranteed):

| Pipeline | H(CCL3) standard | H(CCL3) mod3 |
|----------|-----------------|--------------|
| zlib → W3/BIN → CCL3 | 7.7572 | **8.0727** |
| bz2  → W3/BIN → CCL3 | 7.7167 | **7.9594** |

The mod3 schedule clears the AES-128 reference on compressed binary
payloads. This requires a WIDTH/3-specific CCL base schedule, tracked as
an open question in `draft-darley-fds-ccl-prime-twist-00` §11.4 and gating
normative WIDTH/3 CCL specification.

**CCL schedule architecture — working consensus (from ChatGPT review):**

Keep a small closed enumeration of named schedules. Each schedule is
defined normatively as a profile over a shared conceptual model:

- **Candidate-base function** `f(digit)` — maps each prime digit to a
  candidate base
- **Generic feasibility rule** — if `candidate_base^WIDTH ≤ token_value`,
  use base 10 instead; otherwise use candidate base
- **Authoritative twist-map** — records the actual base used per position;
  used for reversal, not the schedule

The schedule field in the artifact describes the **generation profile**.
It is not needed for reversal. The twist-map is authoritative for reversal.
Receivers MUST treat the twist-map as authoritative and MUST NOT attempt
to reconstruct actual bases from the schedule field alone.

Current named schedules:

| Name | Candidate-base function | Notes |
|------|------------------------|-------|
| `standard` | `d ≤ 1 → 10; else → d` | Default; suits WIDTH/5 natural language |
| `mod3` | `7 + (d mod 3)` | 100% twist; suits WIDTH/3 BINARY |

Fallback is **implicit and global** for all schedules — it is a
representation constraint, not a schedule parameter. No `FALLBACK:` field
is needed in artifacts.

Parameterisation deferred: a literal mapping syntax (`SCHEDULE: cycle/7,8,9`)
is the candidate if a third validated case forces it. Not before then.

Proposed normative sentence for the spec:

> A CCL schedule defines a candidate base for each key-schedule digit;
> the actual base used is determined by the generic feasibility rule,
> with base 10 used whenever the candidate base cannot represent the
> token value within the declared WIDTH. The twist-map is authoritative
> for reversal.

---

## Duress decoy forks — design note

**Threat model:** an operator is compelled at a hostile border crossing to
reveal the key to an FDS artifact. The adversary may recognise UCS-DEC
encoding and demand decryption. The operator needs to be able to produce
a plausible plaintext without revealing the real payload.

**The pattern:** a single artifact contains multiple encrypted data forks,
each wrapped under a distinct verse-derived key. Under duress the operator
reveals the decoy verse, which decrypts to a convincing but non-sensitive
payload. The real payload decrypts only under a verse the operator does not
reveal. The artifact must be indistinguishable whether it contains one fork
or N forks.

**Key design constraints (unresolved):**

- Fork count MUST NOT be detectable from the artifact exterior. If the
  format leaks the number of forks, duress is immediately obvious.
- The outer wrapper must be uniform regardless of fork count. The CCL
  twist layer is a candidate outer wrapper: a CCL-twisted stream looks
  like noise whether one or multiple forks are present inside.
- Per-fork RSRC blocks (TOKENS, CRC32, TWIST-MAP) leak structural
  information. Deniable forks require either a shared outer RSRC or
  no RSRC at all at the outer layer, with per-fork metadata inside the
  encrypted payload.
- Decoy payloads must be operationally convincing. A trivial or empty
  decoy defeats the purpose. The decoy should be a real artifact — a
  poem, a key fragment, a field note — that makes sense in context.
- The decoy verse must be plausibly memorable independently of the real
  verse. "I have memorised two poems" is more deniable than a verse that
  is obviously constructed for the purpose.
- This relates to deniable encryption (Canetti et al., 1997) and hidden
  volume designs (cf. VeraCrypt). Prior art should be reviewed before
  normative specification.

**Relationship to existing layers:**

- FDS-FRAME framing and CRC32 verification operate on a single fork.
  Multi-fork support requires a new outer framing layer or a defined
  multi-fork container format.
- CCL provides statistical camouflage but not confidentiality. Duress
  decoy forks require actual encryption of fork content; CCL alone is
  insufficient.
- Mnemonic Share Wrapping (draft-darley-shard-bundle-01) addresses a
  related but distinct problem: distributing key material across shares.
  Duress forks address single-operator coercion resistance at the
  artifact level.

**Generalisation — multi-stakeholder staged release:**

The multi-fork pattern is not limited to decoy/real pairs. Forks can be
functionally distinct payloads with independent release gates:

```
Fork 1: firmware binary (compiled)
        key: verse held by field engineer
        released: when device is ready to flash

Fork 2: firmware source code
        key: SHA256(official_logo.png) held by technical lead
        released: when downstream audit is complete

Fork 3: signing keys and build instructions
        key: SHA256(internal_document.pdf) held by security officer
        released: only if fork 2 recipient requests it
```

Single artifact. Three independently unlockable payloads. Each release
gate held by a different person in a different role. No single person
can unlock everything. The artifact travels once.

This is **threshold release**, not threshold reconstruction. Shamir
splits a secret so N-of-M holders can reconstruct it. This splits a
payload so each fork is independently accessible to its designated
keyholder, on its own timeline, under its own conditions.

Operational properties:

- **Role separation** — the engineer who flashes firmware never sees
  source code; the auditor who reviews source never touches the binary
- **Temporal separation** — firmware can be flashed before source is
  released; source can be audited after deployment
- **Jurisdictional separation** — different forks unlockable in different
  countries under different legal regimes
- **Deniability by design** — a fork that has not been unlocked does not
  demonstrably exist from the artifact's exterior

This composes with asynchronous key separation: the artifact
pre-positions everywhere via the high-bandwidth channel, then each
keyholder releases their fork independently via the low-bandwidth
channel — a voice call, a verse, a poem over POTS — when their
conditions are met.

The `IF COUNT FAILS: DESTROY IMMEDIATELY` flag on each fork means a
failed unlock attempt does not compromise the others. Each fork fails
independently.

The coercion resistance (decoy/real) pattern is a special case of this
more general capability. The general capability is multi-stakeholder
staged release of functionally distinct payloads from a single artifact.

**Status:** design intent recorded. No implementation. Normative
specification requires resolution of the outer framing design and the
fork-count concealment mechanism. Tracked here pending a dedicated
design sketch.

---

## Far horizon — future drafts

**Theme: extensibility.** Design what the system will need to become.

### Principle 13 in practice: Availability and Integrity over Confidentiality

The full picture of the stack, when complete, is a layered system that
embodies Structural Principle 13 at every level. Confidentiality is
available throughout, but it is always a separable layer and never a
precondition for system function.

```
Physical archive (Vesper)
  ↓ durability, human legibility, no decoding required
Local mirror (Vesper mirror)
  ↓ availability without upstream dependency
  ↓ filesystem integrity, cryptographic verification before publication
FDS encoding layer
  ↓ transport encoding, human-transcribable, integrity via CRC32
Resource fork / FDS-FTP
  ↓ metadata, ordering, interrupted transmission guarantees
SHARD-BUNDLE / Mnemonic Shamir
  ↓ threshold trust, human-recoverable key material
CCL (optional)
  ↓ statistical camouflage — adds no cryptographic guarantees
```

The Vesper Archive Protocol (TLP:CLEAR by design) and the Mirror
Architecture (air-gapped for availability, not secrecy) are the concrete
instantiation of this principle. The sovereign computing demonstration —
zero bytes leave the local network, answer generated entirely from local
corpus — is an availability and integrity guarantee, not primarily a
confidentiality one.

**What the complete system provides:**

| Property | Mechanism |
|----------|-----------|
| Signal survives infrastructure failure | FDS + physical archive + DTN routing |
| Signal survives channel degradation | Human legibility + graceful error tolerance |
| Signal survives time | Archival materials + self-describing artifacts + provenance |
| Signal survives coercion | Mnemonic Shamir + separable confidentiality layer |
| Signal survives network loss | Local mirror + air-gap capability |
| Signal integrity verifiable | CRC32 + Ed25519 + value count |
| Signal confidentiality available | CCL + mnemonic wrapping + encryption (external) |

Confidentiality is a layer.
Availability and integrity are the foundation.

### FDS Fax Page Profile

**Target:** `draft-darley-fds-fax-profile-00`

**Functional requirement:**

```text
# Sender
tar czf - ./spec/ | <encode> > pages.tiff && fax send pages.tiff

# Receiver
fax receive > pages.tiff && <decode> pages.tiff | tar xzf -
```

Two pipelines. Two fax machines. Two pairs of sneakers. No intermediate
manual steps.

**Design constraints:**

- G3/G4 fax is lossy on fine detail; visual encoding must survive fax
  compression artifacts
- Encoding must remain human-legible as fallback; a pure QR code does
  not satisfy this
- Recovery via image-to-text, not full OCR
- Row-level checksums for partial recovery across damaged or reordered pages
- Resource fork travels as separate fax page or cover sheet per ordering rules

**Proposed elements:**

- Fixed-width decimal grid at specified point size and page margin
- Alignment marks (corners + midpoints) for image registration
- Row number and row CRC32 in margin
- Page number and artifact REF in header
- WIDTH/3 BINARY as encoding mode for binary payloads
- Reed-Solomon redundancy across rows and pages

**Dependencies:** WIDTH/3 BINARY (`fds-01`), resource fork spec (`fds-01`),
physical page layout tooling (new), image-to-grid decoder (new).

### Vesper Archive integration

**Target:** `docs/vesper-integration.md` + `tools/archive/`

The Vesper Archive Protocol and Mirror Architecture are the long-horizon
physical instantiation of the Crowsong stack's core principles.
Integration work includes:

- `tools/archive/package.py` — render Field Notes and technical docs to
  archival-ready PDF with correct metadata
- `tools/archive/verify.py` — verify printed archive contents against
  canonical hashes before sealing
- Mirror corpus as RAG source for local AI inference (Ollama +
  Meilisearch + nomic-embed-text) — sovereign computing, zero egress
- Vesper context page as a canonical FDS Print Profile artifact — the
  archive's own provenance, encoded in its own format

The context page encoding: the Vesper context page, encoded as a UCS-DEC
Print Profile artifact, printed on archival paper and included in every
capsule. A reader who can decode FDS can verify the archive's provenance
without any external infrastructure. A reader who cannot decode FDS can
still read the plain-text context page. Both readers get the signal.

### End-to-end demo scenario

**Target:** `tools/demo/`

Two operators. Two terminals. A fax machine at each end.

Operator A fetches a web artifact, packages it into data and resource forks,
encodes, and transmits. Operator B receives, decodes, unpacks, and renders
in a browser — offline, from received pages.

The firmware variant: replace the web artifact with a binary patch. Receiver
verifies CRC32 before flashing. `IF COUNT FAILS: DESTROY IMMEDIATELY` is not
decorative.

The channel between them could be a fax line in East Africa.
It could be TCP/IP over a piece of barbed wire.
It could be a human courier with a printed stack of flash paper.
It could be someone blinking Morse in a meeting.
It could be a CSV in a routine status email.
It could be sensor telemetry auto-archived and never examined.

The stack does not care. The stack was designed for this.

**Dependencies:** `tools/package.py`, `tools/unpackage.py`, WIDTH/3 BINARY
(`fds-01`), resource fork spec (`fds-01`), FDS Fax Page Profile (optional
for initial demo).

**CCL demo (`demo/ccl_demo.sh`):** ✅ done. Nine-step live demonstration
of the full CCL pipeline. Canonical 534-token payload. Triple-pass stack.
Entropy ladder from 4.78 to 8.37 bits/token. Steganographic injection into
network telemetry CSV. Full round-trip recovery. Runs in one terminal window.

---

## One-line summaries

| Horizon | Summary |
|---------|---------|
| `-01` | What is specified must exist |
| `-02` | What is implied must be specified |
| Far | What is needed must be designed |
