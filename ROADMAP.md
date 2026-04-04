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
| 5 | WIDTH/3 BINARY mode | ⬜ todo | Implement alongside spec section; Class D channel requirement |

**CLI decision:** resolved. Frame awareness is automatic in `--decode` and
`--verify`; no `--strict` flag needed.

**Full cycle requirement:** ✅ verified — `--frame` → `--decode` → diff
round-trips cleanly; tested in suite.

### Specification

| # | Item | Status | Rationale |
|---|------|--------|-----------|
| 6 | Resource fork (minimal) | ⬜ todo | `RSRC: BEGIN/END`, dependency-based ordering, interrupted transmission guarantees |
| 7 | WIDTH/3 BINARY mode | ⬜ todo | Byte-stream encoding; `BINARY` flag in `ENC:` header; decoder emits raw bytes |
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
| Channel Camouflage Layer (CCL) | Informative profile; representation schedule to reduce payload salience in degraded channels |

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

The stack does not care. The stack was designed for this.

**Dependencies:** `tools/package.py`, `tools/unpackage.py`, WIDTH/3 BINARY
(`fds-01`), resource fork spec (`fds-01`), FDS Fax Page Profile (optional
for initial demo).

---

## One-line summaries

| Horizon | Summary |
|---------|---------|
| `-01` | What is specified must exist |
| `-02` | What is implied must be specified |
| Far | What is needed must be designed |
