# The Crowsong Suite — Overview

*For reviewers, implementors, and passive listeners.*

---

## What problem this solves

The internet fails. When it does, the channels that remain —
fax, Morse, printed page, human courier, shortwave voice —
share one property: they cannot carry binary data.

Existing resilient communications protocols assume a degraded
IP stack. This suite assumes IP may not exist at all, and
builds upward from human legibility.

## The four drafts and how they fit together

```
draft-darley-meridian-protocol-01
  ↑ consumes
draft-darley-resilient-signal-stack-00
  ↑ references
draft-darley-fds-00           draft-darley-shard-bundle-00
  ↑ implements                  ↑ implements
tools/ucs-dec/ucs_dec_tool.py  [credmgr lineage, 2012]
```

**Start with `draft-darley-fds-00`** if you want to implement
something today. It is fully self-contained. The reference
implementation is 150 lines of Python with no dependencies.
The test vector is a poem.

**Read `draft-darley-resilient-signal-stack-00`** for the
architecture. It tells you how the pieces fit together and
why the layering is the way it is.

**Read `draft-darley-shard-bundle-00`** for the trust layer.
If you need to distribute key material over degraded channels,
or verify content integrity without a working DNS, this is
the document.

**Read `draft-darley-meridian-protocol-01`** for the content
layer. If you want a site to survive the death of its author,
this is the document.

## The design in one sentence

Every layer of the stack must be operable by a human with
patience and appropriate reference material, without software.

## The test vector

A poem, encoded as flash paper.

530 values. COL/6. WIDTH/5. PAD/00000. The first three values
decode to 桜稲荷. The encoding eats its own attribution.

Decode it. Verify the count. Re-encode it. Check the diff.

Expected output: silence.

## The provenance chain

```
2012  credmgr              Shamir over GPG email
                           trusted humans, shard distribution

2026  Fox Decimal Script   encoding for any channel
      Meridian Protocol    content sovereignty, URL continuity
      Crowsong suite       the stack formalised

draft Aeolian Layer        the stack instantiated at national scale
      (in progress)        kite-borne DTN mesh, Belgium

2084  Ghost Line           an unknown node, still transmitting
      Fifty mirrors        the Mundaneum, finally distributed
      Second Law Blues     encoded in its own format
                           inside the back of a book
                           at Atlanta Greyhound
                           RESERVED — SINGLE USE
```

## On the name

Crows are the passive listeners in the Aeolian Layer.

A crowsong is what they hear.

It is what FDS produces on a degraded channel. What arrives
eleven days late with verified integrity. The signal that
comes through after the wind and the earthquake and the fire
have gone quiet.

The mesh does not require you to know who someone is.
It requires you to know that their signal is consistent.
