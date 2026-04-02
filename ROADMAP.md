# Crowsong — FDS `-01` Roadmap

*Working document — defines scope and execution plan for `draft-darley-fds-01`*

---

## Status

`-00` is tagged.

This document defines what goes into `-01`, what is explicitly deferred,
and what constitutes a complete release.

---

## Design intent

`-01` is not an expansion release. It is a **coherence release**.

The goal is to eliminate the gap between:

* what the specification claims, and
* what the reference implementation actually does.

Where new functionality is introduced, it is because the system is
incomplete without it.

---

## Scope

### Implementation (normative alignment)

#### 1. NFC normalisation in `encode()`

Add:

```python
unicodedata.normalize("NFC", text)
```

as the first operation in `encode()`.

**Rationale:** Required for canonical reproducibility and compliance
with Section 2.1.

---

#### 2. Full FDS-FRAME parser

Implement frame-aware decoding and verification per Section 8.1.

**Capabilities:**

* Parse `ENC:` header
* Extract `WIDTH`, `COL`, `PAD` (apply defaults if absent)
* Detect and parse optional `SIG:` line
* Use extracted parameters during decode (no hardcoded defaults)
* Verify value count and CRC32 (over encoded payload string)
* Enforce `IF COUNT FAILS: DESTROY IMMEDIATELY`

**CLI considerations:**

* Introduce `--strict`, or
* Extend `--verify` + `--frame` interaction

Decision must be made at the start of Phase 1, before test suite work
begins.

**Full cycle requirement:** Once the frame parser exists, the tool must
support the complete generate-and-parse cycle. `--frame` produces a
framed artifact; `--decode` on that artifact must recover the original
payload exactly. This must be explicitly tested.

**Rationale:** This is the primary gap between spec and tool.

---

#### 3. Test suite expansion

Add:

* NFC normalisation stability test
* Frame-aware roundtrip test: `--frame` → `--decode` → diff against
  source (exercises full generate-and-parse cycle)
* `--verify` correctness on framed artifacts (count + CRC32)
* Corruption test: non-zero exit when DESTROY flag present and
  verification fails
* Confirm canonical test vector unchanged post-NFC

---

### Specification (targeted additions)

#### 4. Resource fork (minimal viable spec)

Introduce a minimal resource fork definition:

* `RSRC: BEGIN` / `RSRC: END`
* Dependency-based ordering rule:
  * resource-first when data fork is not independently decodable
  * data-first when data fork is independently decodable
* Interrupted transmission guarantees for each ordering case
* Physical mapping:
  * data fork → payload pages
  * resource fork → context page

Ordering is determined by dependency, not convention. This is the key
insight and should be stated plainly before the formal spec language.

**Constraint:** Keep this tight. Full FDS-FTP is deferred.

---

#### 5. WIDTH/3 BINARY mode

Add binary encoding mode:

* 1 byte → 3-digit decimal (000–255)
* `BINARY` flag in `ENC:` header
* Decoder outputs raw bytes (no `chr()`)
* Implement in tool alongside the spec section

**Rationale:**

* Reduces operator burden on Class D channels (Morse, human relay)
* Avoids Base64 symbol complexity
* Aligns with FDS philosophy: decimal-only survivability

---

#### 6. Spec housekeeping

* Fix section cross-references
* Update reference implementation section to reflect NFC and frame
  parsing
* Extend transport compatibility matrix to include BINARY mode

---

### Cross-document addition

#### 7. Human coordination layer *(Crowsong draft, not FDS)*

Add to `draft-darley-crowsong-01`:

* Talking stick model
* Priority signalling: EMERGENCY / URGENT / ROUTINE
* Distributed moderation
* Operator attestation signals

**Status:** Informative section (1–2 pages).

---

## Explicitly deferred

These are valid. They are not `-01` work.

* Full FDS-FTP (multipart, resumability, retransmission)
* MIME type quick reference appendix
* Aeolian Layer draft (`draft-darley-aeolian-dtn-arch-01`)
* Story infrastructure (`story/ghost-line.md`, prose PR model) —
  develop in parallel, not as a release dependency

---

## Definition of done

Before tagging `-01`:

* [ ] NFC normalisation implemented
* [ ] Frame parser implemented; `--decode` uses extracted parameters
* [ ] Full generate-and-parse cycle tested (`--frame` → `--decode` → diff)
* [ ] `--verify` enforces count + CRC32 + DESTROY semantics
* [ ] Test suite expanded and passing
* [ ] Canonical artifacts verified unchanged post-NFC
* [ ] Resource fork section complete
* [ ] WIDTH/3 BINARY section and implementation complete
* [ ] Human coordination section added to Crowsong draft
* [ ] Cross-references verified
* [ ] RFC `.txt` regenerated
* [ ] Tag created (`v0.1-crowsong-01`)

---

## Execution plan

```
Phase 1 — Implementation (~3 hours)
  Resolve --strict / --verify CLI decision
  NFC normalisation
  Frame parser
  Full cycle test (--frame -> --decode -> diff)
  Test suite updates
  Verify canonical artifacts unchanged

Phase 2 — Specification (~2 hours)
  Resource fork section
  WIDTH/3 BINARY section
  Housekeeping pass

Phase 3 — Crowsong integration (~1 hour)
  Human coordination layer
  Terminology alignment

Phase 4 — Release (~30 min)
  RFC generation
  README updates
  Tagging
```

---

## Notes

* The reference implementation remains intentionally minimal, but must
  no longer contradict the spec.
* Resource fork ordering is the key conceptual addition: dependency
  determines ordering, not convention.
* WIDTH/3 BINARY should be implemented alongside its specification, not
  after.
* Story-driven engagement (Ghost Line, prose PR model) should be
  scaffolded in parallel with `-01` work, not gated on the tag.

---

## One-line summary

`-01` makes the system honest: what is specified is what exists.
