# Vesper Archive Protocol

*"Carry the signal forward."*

- **Version:** 1.0
- **Classification:** TLP:WHITE — this document may be shared freely
- **Author:** Vernon Olin Darley III / Proper Tools SRL
- **Created:** 2026-03-16
- **Status:** Active

---

## What this is

Vesper is a protocol for creating physically recoverable, human-readable
archives intended to survive 50 or more years with minimal dependency on
fragile infrastructure.

It is not a backup system. It is a time capsule with a discipline.

The design priorities, in order:

1. **Durability** — the archive must survive without maintenance
2. **Legibility** — a literate human must be able to read it without tools
3. **Context** — a reader with no prior knowledge must understand what they have
4. **Integrity** — the archive must be verifiable on recovery
5. **Survivability** — partial degradation must not destroy the whole

Confidentiality is not in this list. A Vesper archive is TLP:WHITE by design.
If you need to bury secrets, encrypt them before archiving and include the
decryption instructions in the archive itself. See the Mnemonic Shamir
construction in `docs/mnemonic-shamir-sketch.md`.

---

## The core insight

Paper is the most durable information storage medium available to a
non-institutional actor. A document printed on archival cotton-rag paper
with pigment ink, sealed in a Mylar microclimate with silica gel, placed
in a Pelican case, and buried at appropriate depth will outlast any digital
medium you can name — and will be readable by any literate person, in any
century, with no tools.

The failure mode of paper is moisture. The protocol is almost entirely about
managing moisture.

---

## What to archive

### Tier 1 — Core (every capsule)

These items go in every capsule, without exception.

- **This document** — the archive protocol itself
- **A context page** — what this is, who created it, when, why; written
  for a reader with no prior knowledge (see template below)
- **The structural principles** — `docs/structural-principles.md`;
  applicable beyond any specific project
- **The Y2038 summary** — a plain-language explanation of the Year 2038
  timestamp vulnerability; this is the professional and intellectual core
  of the work and may still be relevant to a future reader

### Tier 2 — Technical (primary capsule)

- **Network design and addressing** — self-documenting rationale, not just
  the configuration
- **Mirror architecture summary** — what was mirrored, why, where
- **Key runbook procedures** — condensed, de-infrastructured; written for
  someone who does not have access to the live system

### Tier 3 — Personal (discretionary)

- As-needed

### Exclude

- Credentials of any kind
- Anything TLP:AMBER or TLP:RED
- Anything time-sensitive that will be meaningless in 50 years
- Anything that assumes context the archive itself does not provide

---

## Materials

### Paper

- Acid-free, lignin-free, cotton rag preferred
- 90–120 gsm, A4, single-sided
- Sources: Hahnemühle, Canson Infinity, or equivalent archival supplier

### Ink

- Pigment-based only — not dye-based
- Laser toner or archival inkjet (Epson UltraChrome, Canon LUCIA)
- Allow inkjet prints to cure for 24 hours before sealing

### Encapsulation

- Archival polyester sleeves (Melinex / Mylar) — one per document or
  small bundle
- Archival tissue interleaving if available

### The microclimate barrier

This is the critical layer. Do it carefully.

- Mylar bag, 5–7 mil thickness, heat-sealable
- Silica gel, pre-dried at 120°C for 2+ hours immediately before sealing
- Oxygen absorber (optional; reduces oxidative degradation)
- Heat seal — do not fold or clip

### Container

| Option | Notes |
|--------|-------|
| Pelican 1300 or 1400 | Excellent gasket, proven track record, available in Belgium |
| Nanuk 904 or 910 | Good alternative, similar specification |
| Military surplus steel ammo can (gasket intact) | Cheap, robust, heavy; verify gasket condition |

Do not use: plastic storage bins, food containers, anything without a
compression gasket.

### External protection

- Heavy-duty polyethylene bag, 200 micron minimum, heat-sealed
- Label outer surface in French, Dutch, and English:
  **"Archive — do not discard / Archives — ne pas jeter / Archief — niet weggooien"**

---

## Assembly procedure

**Step 1 — Print and review**

Print all documents on archival paper. Verify legibility. Number all pages
within each document. Allow 24 hours for inkjet curing.

**Step 2 — Sleeve and arrange**

Place each document or small bundle in an archival polyester sleeve.
Arrange in reading order: context page first, then Tier 1, Tier 2, Tier 3.

**Step 3 — Seal the microclimate**

Pre-dry silica gel at 120°C for at least 2 hours. Place the bundle in the
Mylar bag. Add silica gel (approximately 10g per litre of interior volume).
Add oxygen absorber if available. Heat seal with overlap. Mark the bag with
date and contents summary in permanent marker.

*This is where the archive is actually preserved. Take your time.*

**Step 4 — Containerise**

Inspect the container gasket — it must be clean, supple, and undamaged.
Apply a thin film of silicone grease to the gasket (non-petroleum,
non-reactive). Place the sealed Mylar bag in the container. If space
permits, add a Rosetta bundle (see below). Close firmly and verify the seal.

**Step 5 — External wrap**

Place the container in the polyethylene bag. Heat seal or tie securely.
Label in three languages.

**Step 6 — Photograph**

Before burial, photograph: contents laid out, sealed Mylar bag, closed
container, labelled outer wrap. Store photographs and a written inventory
separately from the archive.

---

## The Rosetta bundle

A compressed secondary archive placed inside the primary capsule, or
constituting the entire secondary capsule. Contains:

- The context page
- A one-page Y2038 summary
- A one-page structural principles summary

If the main bundle is damaged, the Rosetta bundle may survive. If the
Rosetta bundle is all that survives, it is still meaningful.

---

## Burial

### Site selection

- Elevated, well-drained ground
- Avoid: flood zones, clay-heavy soil, known construction areas,
  property boundaries, areas likely to be disturbed
- Prefer: established garden, stable natural feature, owned land
- Consider: whether someone who knows what they are looking for can
  find it without the location record

### Depth

Belgian conditions: minimum 60cm, preferred 80–100cm. Below the frost
line. Deeper means more stable temperature but harder recovery. 80cm is
the practical optimum.

### Placement

Place on a slight angle (10–15°) or a gravel drainage base. Orient any
label face-up. Backfill in layers, tamping gently. Restore the surface
naturally.

---

## Location record

Store separately from the archive, in at least three locations:

- One copy with a trusted person
- One copy in the repository (encrypted if needed)
- One copy in a sealed envelope with personal papers

```
VESPER ARCHIVE — LOCATION RECORD
Capsule ID:   VA-[NUMBER]
Created:      [DATE]
Buried:       [DATE]

Location (plain language):
  [Describe in terms of stable landmarks. Compass bearing and distance
  from a fixed point. Do not rely on GPS coordinates alone — datum
  systems change. Include both.]

Coordinates (WGS84): [LAT], [LON]
Bearing from [LANDMARK]: [DEGREES]°, [DISTANCE]m
Depth: [CM]

Contents summary:
  [Brief list]

Recovery notes:
  [Access, permissions, obstacles, anything a stranger would need to know]
```

---

## Redundancy

### Minimum configuration: two capsules, two sites

| Capsule | Contents | Location |
|---------|----------|----------|
| VA-01 (Primary) | Full Tier 1 + Tier 2 + Tier 3 | Owned land, known stable |
| VA-02 (Secondary) | Tier 1 only + Rosetta bundle | Different location, different soil type |

Spatial separation is the most important redundancy property. Two capsules
in adjacent gardens share too many failure modes.

---

## Known failure modes

| Failure mode | Probability | Mitigation |
|---|---|---|
| Moisture ingress past Mylar seal | Low if heat-sealed correctly | Overlap seal, inspect gasket annually if accessible |
| Ink fading | Very low with pigment ink | Use archival-spec materials only |
| Container gasket degradation | Medium over 50+ years | Silicone grease; inspect at 10-year intervals |
| Loss of location record | Medium | Three separate copies; trusted person |
| Site disturbance (construction) | Low–medium | Two sites; spatial separation |
| Contextual incomprehension | Low | Context page written for the naive reader |
| Paper degradation | Very low with cotton rag stock | Use specification materials |

**Design assumption:** the archive remains legible even if not pristine.
Partial degradation of a well-constructed archive still yields recoverable
signal.

---

## Context page template

Every capsule includes this as its first document. It requires no prior
knowledge to understand. Adapt as appropriate.

---

**VESPER ARCHIVE**

*Created by: [NAME]*
*Purpose: [PURPOSE]*
*Date of creation: [DATE]*
*Date of burial: [DATE]*

This container holds documents created between approximately [YEAR] and [YEAR].

*"It's not darkest before the dawn. That's just something that people say."*

---

## Bill of materials

| Item | Specification | Estimated cost |
|------|--------------|----------------|
| Archival paper | A4, acid-free, cotton rag, 90–120gsm | €15–30 per ream |
| Pigment ink / laser toner | Archival spec | Variable |
| Polyester sleeves | Melinex/Mylar, archival grade | €20–40 per pack |
| Mylar bags | 5–7 mil, heat-sealable | €15–25 |
| Silica gel | Food-grade or desiccant grade, rechargeable | €10–15 |
| Oxygen absorbers | 100–300cc capacity (optional) | €10 |
| Heat sealer | Impulse type | €30–50 |
| Archival tissue | Acid-free interleaving | €10–15 |
| Silicone grease | Non-petroleum, non-reactive | €5–10 |
| Container | Pelican 1300/1400 or equivalent | €60–120 |
| Polyethylene bag | 200 micron, heavy duty | €5–10 |
| Permanent marker | Waterproof, fade-resistant | €5 |

**Estimated cost per capsule:** €80–150 depending on container choice.

---

## Inspection and refresh schedule

- **Every 10 years** (if accessible): open, inspect, reseal, re-bury;
  update contents if warranted
- **On major revision** of the Field Notes or technical documentation:
  replace rather than append; keep it clean
- **After any disturbance** of the site: recover, inspect, re-seal,
  re-bury at a new location if needed

---

## Connection to the Crowsong stack

A Vesper archive is a physical instantiation of the Crowsong stack's core
principles. It is:

- A store-and-forward node with a very long delay (Principle 6)
- A self-describing artifact carrying its own provenance (Principle 10)
- A system designed first for the failure case (Principle 1)
- A demonstration that availability and integrity precede confidentiality
  (Principle 13)

The context page, encoded as an FDS Print Profile artifact and included
alongside the plain-text version, allows a reader who knows FDS to verify
the archive's provenance without external infrastructure. A reader who does
not know FDS reads the plain text. Both readers get the signal.

---

## Closing note

This archive is not intended to last forever.

It is intended to bridge time.

To carry signal across a span long enough that it might otherwise be lost —
not as monument, not as artifact, but as continuity.

The Year 2038 problem is, at its core, a failure of long-horizon thinking:
a decision made in the early days of Unix that assumed 2038 was too far away
to worry about. This archive is the opposite of that decision.

Signal discipline. All the way down.

---

*Vesper Archive Protocol v1.0*
*Proper Tools SRL — propertools.be*
*TLP:WHITE*
