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

| # | Item | Rationale |
|---|------|-----------|
| 1 | NFC normalisation in `encode()` | Required for canonical reproducibility; compliance with §2.1 |
| 2 | Frame-aware FDS-FRAME parser | Primary gap between spec and tool; §8.1 steps 1 and 4 |
| 3 | Frame-aware `--decode` | Must use extracted WIDTH/COL/PAD, not hardcoded defaults |
| 4 | `--verify` enforcement | Count + CRC32 + DESTROY semantics per §3.4 |
| 5 | WIDTH/3 BINARY mode | Implement alongside spec section; Class D channel requirement |

**CLI decision:** resolve before test suite work begins.  
Introduce `--strict`, or extend `--verify` + `--frame` interaction.

**Full cycle requirement:**  
`--frame` → `--decode` → diff must round-trip cleanly and be explicitly tested.

### Specification

| # | Item | Rationale |
|---|------|-----------|
| 6 | Resource fork (minimal) | `RSRC: BEGIN/END`, dependency-based ordering, interrupted transmission guarantees |
| 7 | WIDTH/3 BINARY mode | Byte-stream encoding; `BINARY` flag in `ENC:` header; decoder emits raw bytes |
| 8 | Housekeeping pass | Cross-references, implementation section, transport matrix |

### Cross-document

| # | Item | Target draft |
|---|------|-------------|
| 9 | Human coordination layer | `draft-darley-crowsong-01` |

Covers: talking stick model, priority signalling (EMERGENCY / URGENT / ROUTINE), distributed moderation, operator attestation.  
Status: informative section, 1–2 pages.

### Test suite additions

- NFC normalisation stability (canonical vector must be unchanged)
- Full generate-and-parse cycle (`--frame` → `--decode` → diff)
- `--verify` on framed artifacts (count + CRC32)
- Corruption test (DESTROY flag present, verification fails → non-zero exit)

### Definition of done

- [ ] NFC normalisation implemented and tested
- [ ] Frame parser implemented; `--decode` uses extracted parameters
- [ ] Full generate-and-parse cycle tested
- [ ] `--verify` enforces count + CRC32 + DESTROY semantics
- [ ] Test suite expanded and passing
- [ ] Canonical artifacts verified unchanged post-NFC
- [ ] Resource fork section complete
- [ ] WIDTH/3 BINARY section and implementation complete
- [ ] Human coordination section added to Crowsong draft
- [ ] Cross-references verified
- [ ] RFC `.txt` regenerated
- [ ] Tag: `v0.1-crowsong-01`

### Execution plan

```text
Phase 1 — Implementation (~3 hours)
  Resolve CLI decision (--strict vs --verify + --frame)
  NFC normalisation
  Frame parser + frame-aware --decode
  Full cycle test
  Test suite updates
  Verify canonical artifacts unchanged

Phase 2 — Specification (~2 hours)
  Resource fork section
  WIDTH/3 BINARY section
  Housekeeping pass

Phase 3 — Crowsong integration (~1 hour)
  Human coordination layer
  Terminology alignment with fds-01

Phase 4 — Release (~30 min)
  RFC .txt regeneration
  README updates
  Tag
````

---

## Mid horizon — `draft-darley-fds-02` and peers

**Theme: completeness release.** Specify what the near horizon implies but defers.

| Item                                          | Notes                                                                                                       |
| --------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Full FDS-FTP spec                             | Multipart, resumability, retransmission request format                                                      |
| MIME type quick reference appendix            | Companion to FDS Unicode reference table                                                                    |
| Morse grouping conventions for WIDTH/3 BINARY | Prosign-friendly chunking; operator fatigue; error recovery                                                 |
| Story infrastructure                          | `story/ghost-line.md`, prose PR model, decomposition log — develop in parallel with `-01`, not gated on tag |
| Aeolian Layer draft                           | `draft-darley-aeolian-dtn-arch-01` — its own document, its own timeline                                     |

---

## Far horizon — future drafts

**Theme: extensibility.** Design what the system will need to become.

### FDS Fax Page Profile

**Target:** `draft-darley-fds-fax-profile-00`

**Functional requirement:**

```text
# Sender
tar czf - ./spec/ | <encode> > pages.tiff && fax send pages.tiff

# Receiver
fax receive > pages.tiff && <decode> pages.tiff | tar xzf -
```

Two pipelines. Two fax machines. Two pairs of sneakers. No intermediate manual steps.

**Design constraints:**

* G3/G4 fax is lossy on fine detail; visual encoding must survive fax compression artifacts
* Encoding must remain human-legible as fallback; a pure QR code does not satisfy this
* Recovery via image-to-text, not full OCR
* Row-level checksums for partial recovery across damaged or reordered pages
* Resource fork travels as separate fax page or cover sheet per ordering rules

**Proposed elements:**

* Fixed-width decimal grid at specified point size and page margin
* Alignment marks (corners + midpoints) for image registration
* Row number and row CRC32 in margin
* Page number and artifact REF in header
* WIDTH/3 BINARY as encoding mode for binary payloads
* Reed-Solomon redundancy across rows and pages

**Dependencies:**

* WIDTH/3 BINARY (`fds-01`)
* Resource fork spec (`fds-01`)
* Physical page layout tooling (new)
* Image-to-grid decoder (new)

---

## One-line summaries

| Horizon | Summary                           |
| ------- | --------------------------------- |
| `-01`   | What is specified must exist      |
| `-02`   | What is implied must be specified |
| Far     | What is needed must be designed   |
