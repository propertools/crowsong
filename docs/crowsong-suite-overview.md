# The Crowsong Suite — Overview

*For reviewers, implementers, and passive listeners.*

---

## What problem this solves

Infrastructure fails.

When it does, the channels that remain — fax, Morse, printed page,
human relay, shortwave voice — share a constraint: they cannot
reliably carry binary data.

Most "resilient" communication systems assume a degraded IP network.

Crowsong assumes the network may not exist at all, and builds upward
from human legibility.

---

## The system

Crowsong is a set of Internet-Drafts describing a layered signal
architecture with one defining constraint:

> Messages must remain interpretable, verifiable, and transmissible
> even when reduced to manual transcription over non-binary channels.

This constraint is applied at every layer.

---

## The drafts and how they fit together

```
draft-darley-meridian-protocol-01
  ↑ consumes
draft-darley-crowsong-00
  ↑ composes
draft-darley-fds-00           draft-darley-shard-bundle-00
  ↑ implements                  ↑ implements
tools/ucs-dec/ucs_dec_tool.py  [credmgr lineage, 2012]
```

### Where to start

- **Start with `draft-darley-fds-00`**
  If you want to implement something immediately.
  Self-contained. No dependencies. Reference implementation included.

- **Read `draft-darley-crowsong-00`**
  For the architecture: how the layers compose and why.

- **Read `draft-darley-shard-bundle-00`**
  For the trust model: distributing key material and verifying integrity
  without assuming working infrastructure.

- **Read `draft-darley-meridian-protocol-01`**
  For the content layer: preserving addressability and continuity of
  web artifacts beyond origin failure.

---

## The design in one sentence

Every layer of the system must be operable by a human with patience
and appropriate reference material.

---

## The test vector

The canonical test vector is a poem, encoded as Fox Decimal Script.

COL/6 · WIDTH/5 · PAD/00000
- 530 values
- The first three decode to 桜稲荷
- The encoding contains its own attribution

Suggested exercise:

1. Decode it
2. Verify the value count
3. Re-encode it
4. Compare output

Expected result: no difference.

---

## The provenance chain

```
2012  credmgr              Shamir over GPG email
                           trusted humans, shard distribution
2026  Fox Decimal Script   encoding for any channel
      Meridian Protocol    content continuity and authorship
      Crowsong suite       the stack formalised
draft Aeolian Layer        delay-tolerant mesh over non-standard media
      (in progress)
2084  Ghost Line           an unknown node, still transmitting
      Fifty mirrors        distributed continuity
      Second Law Blues     encoded in its own format
                           inside the back of a book
                           at Atlanta Greyhound
                           RESERVED — SINGLE USE
```

---

## On the name

In the Aeolian Layer — a delay-tolerant mesh operating over
non-standard physical channels — passive listeners are called Crows.

A *crowsong* is what they receive.

It is the signal that arrives intact despite delay, degradation,
and loss of infrastructure.

The system does not require identity.

It requires consistency.
