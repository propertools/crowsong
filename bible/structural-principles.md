# Structural Principles

*Working document — governing design principles for Meridian and Crowsong*

---

These principles govern the design of the Crowsong stack, the Meridian
Protocol, and related continuity systems.

They are intended to describe architectural commitments rather than
implementation details.

---

## On the choices this stack makes

The Crowsong stack makes several choices that may appear eccentric. They are not.

**Why Unicode?** Unicode is the closest thing humanity has to a universal
agreement on the representation of written language. It is an open standard,
maintained by a stable consortium, with broad implementation across platforms,
decades, and languages. A system intended to survive infrastructure disruption
should encode against a standard that is itself resilient and widely understood
— not a proprietary format or a compression scheme optimised for conditions
that may not obtain at the time of recovery.

**Why decimal representation?** Decimal integers are legible to any person
with basic numeracy, regardless of technical background, language, or available
tooling. Hexadecimal requires learned conversion. Binary is impractical at
scale. Decimal, combined with a Unicode lookup table, reduces the decoding
operation to something a patient person can perform with paper and a reference
sheet. That is the point.

**Why fax, Morse, kite-borne relays?** Because infrastructure fails
asymmetrically and unpredictably. Internet exchange points go dark. Power grids
fail. Radio still propagates. Kites still fly. Fax machines persist in
hospitals, law firms, and government offices long after they are declared
obsolete, precisely because they are simple, standardised, and do not require
software updates. A signal architecture that depends on the full stack being
operational is not a resilient signal architecture. The physical layer choices
are not nostalgia or whimsy: they are the honest answer to the question of what
channels remain when the preferred ones are unavailable.

---

## Principle 1: Design for the failure case.

The normal case usually takes care of itself.

Systems that matter should be designed first for degraded,
disrupted, or adversarial conditions. The edge case is where
architecture reveals itself.

---

## Principle 2: Graceful degradation is a primary property.

Graceful degradation is not an emergency mode added after the fact.
It is a core design requirement.

A system that continues to operate, at reduced capability, under
degraded conditions is categorically more resilient than one that
fails completely outside nominal assumptions.

Design the degraded mode first.

---

## Principle 3: Human legibility is a hard requirement.

Any layer that cannot, in principle, be operated by a human with
sufficient patience and appropriate reference material has a single
point of failure in software.

For infrastructure intended to survive disruption, that is
unacceptable.

Human legibility is not nostalgia. It is a resilience property.

---

## Principle 4: Encoding determines survivability.

When the fundamental operations of a system can be performed by a
human using a lookup table or equivalent reference, the system can
survive the loss of complex tooling.

Encoding is therefore not a secondary implementation detail. It is
part of the protocol's resilience model.

Optimise for survivability, not only for bandwidth or elegance under
ideal conditions.

---

## Principle 5: Trust must be explicit.

Implicit trust in infrastructure is not trust. It is dependency.

Trust relationships should be named, bounded, and verifiable.
Where possible, they should be supported by cryptographic means and
designed to degrade in a controlled manner when infrastructure
assumptions fail.

---

## Principle 6: Store-and-forward is a design posture.

Store-and-forward is not merely a transport feature. It is a way of
treating messages as worth preserving across delay, fragmentation,
and interruption.

A resilient system must be willing to hold state long enough for
conditions to permit delivery.

This principle applies equally to packets, archives, manifests,
shards, and physical media.

---

## Principle 7: Redundancy requires independence of failure modes.

Two copies on the same medium are not sufficient redundancy.
Two copies in the same location are not sufficient redundancy.
Two copies over the same channel are not sufficient redundancy.
Two copies made at the same time from the same source are not sufficient redundancy.

Meaningful redundancy requires independence across failure modes,
including spatial, material, operational, channel, and temporal diversity.

---

## Principle 8: Context is part of the payload.

A message without context may be uninterpretable.
A key without instructions may be unusable.
An archive without framing may be indistinguishable from noise.

Systems intended for long-horizon survivability must carry enough
context for a recipient without prior operational knowledge to
understand what they have received and what should be done with it.

Context is not auxiliary. It is part of the signal.

---

## Principle 9: Time is a first-class design dimension.

Some participants in a system may be delayed, unavailable, offline,
or permanently unable to update. Systems must tolerate this.

Resilient protocols should accommodate long and uneven time horizons,
including delayed delivery, archival recovery, succession, and
interactions with stale but still trusted state.

A message recovered years later is still a message.

---

## Principle 10: Provenance should be legible within the system.

A resilient system should make its own origin, framing, and authorship
as legible as possible from within the system itself.

Where practical, artifacts should identify their format, parameters,
and provenance in forms recoverable without external infrastructure.

Self-description supports verification, recovery, and continuity.

---

## Principle 11: Optionality is a design problem, not a keyword.

SHOULD is a design smell.

When a specification reaches for SHOULD, it is usually avoiding one of
two harder commitments: either the behaviour is required for
interoperability and should be stated as MUST, or it is genuinely
optional and should be extracted into a composable component with its
own minimal specification.

Vague recommendations accumulate. Implementors treat them as permission
to skip. Systems drift apart.

The discipline: when you find yourself writing SHOULD, stop. Ask
whether this is a MUST that lacks the courage to declare itself, or an
optional capability that deserves its own coherent spec. If it is
genuinely advisory — operational wisdom that cannot be mandated — say
so plainly in prose. Do not hide it in a keyword.

There is no SHOULD. There is MUST, MUST NOT, and design work still to
be done.

---

## Principle 12: Timestamps are claims, not ground truth.

A timestamp carried in a message is an assertion made by the sender
at the time of sending, under conditions the receiver cannot verify.

Clocks drift. Clocks lie. Clocks roll over. A message recovered from
archival storage, forwarded through a delay-tolerant mesh, or
transcribed by a human courier may carry a timestamp that is
meaningless, inconsistent, or actively wrong relative to the
receiver's local wall clock.

Timestamps must therefore be carried in a discardable outer layer —
structurally separable from the payload, never load-bearing for
decoding or integrity verification.

The rule: if a received timestamp is locally nonsensical — outside
acceptable bounds, internally inconsistent, or absent — log the
anomaly, discard the timestamp, and proceed using local wall clock
time. Do not fail. Do not block. Do not propagate the bad clock.

A message with a wrong timestamp is still a message.
A system that refuses to process it has failed the signal.

---

## Principle 13: Availability and integrity before confidentiality.

The classical security triad — Confidentiality, Integrity,
Availability — is typically prioritised in that order. This stack
inverts it deliberately.

A signal that cannot be delivered is worthless regardless of how well
it is protected. A signal whose integrity cannot be verified is
dangerous regardless of how well it is encrypted. Confidentiality
matters, but it is a separable concern — a layer added when needed,
not a precondition for the system to function.

Design for delivery first. Design for verifiability second. Add
confidentiality where the threat model requires it, using components
that do not compromise the first two properties.

The corollary: a system that sacrifices availability or integrity in
service of confidentiality has made the wrong trade. An encrypted
message that cannot be decoded under degraded conditions is not more
secure — it is lost.

Confidentiality is a layer. Availability and integrity are the
foundation.

---

A contribution is useful if it makes the system more likely to carry a
signal across a gap.

That is the test.
