# Structural Principles

*Working document — governing design principles for Meridian and Crowsong*

---

These principles govern the design of the Crowsong stack, the Meridian Protocol, and related continuity infrastructure.

They describe architectural commitments rather than implementation details.

---

## On the choices this stack makes

The Crowsong stack makes several choices that may appear eccentric. They are not.

**Why Unicode?**
Unicode is the closest thing humanity has to a universal agreement on the representation of written language. It is an open standard, maintained by a stable consortium, with broad implementation across platforms, decades, and languages. A system intended to survive infrastructure disruption should encode against a standard that is itself resilient and widely understood—not a proprietary format or a compression scheme optimised for conditions that may not obtain at the time of recovery.

**Why decimal representation?**
Decimal integers are legible to any person with basic numeracy, regardless of technical background, language, or available tooling. Hexadecimal requires learned conversion. Binary is impractical at scale. Decimal, combined with a Unicode lookup table, reduces decoding to something a patient person can perform with paper and a reference sheet. That is the point.

**Why fax, Morse, kite-borne relays?**
Infrastructure fails asymmetrically and unpredictably. Internet exchange points go dark. Power grids fail. Radio still propagates. Kites still fly. Fax machines persist in hospitals, law firms, and government offices long after they are declared obsolete, precisely because they are simple, standardised, and do not require software updates. A signal architecture that depends on the full stack being operational is not a resilient signal architecture. These physical-layer choices are not nostalgia or whimsy; they are an honest answer to the question of what channels remain when preferred ones are unavailable.

---

## Principle 1: Design for the failure case.

The normal case usually takes care of itself.

Systems that matter should be designed first for degraded, disrupted, or adversarial conditions.

The normal case rarely requires special handling.
The edge case is where architecture reveals itself.

---

## Principle 2: Graceful degradation is a primary property.

Graceful degradation is not an emergency mode added after the fact. It is a core design requirement.

A system that continues to operate, at reduced capability, under degraded conditions is categorically more resilient than one that fails completely outside nominal assumptions.

Design the degraded mode first.

---

## Principle 3: Human legibility is a hard requirement.

Any layer that cannot, in principle, be operated by a human with sufficient patience and appropriate reference material has a single point of failure in software.

For infrastructure intended to survive disruption, that is unacceptable.

Human legibility is not nostalgia. It is a resilience property.

---

## Principle 4: Encoding is part of the resilience model.

When the fundamental operations of a system can be performed by a human using a lookup table or equivalent reference, the system can survive the loss of complex tooling.

Encoding is not a secondary implementation detail. It is part of the protocol’s resilience model.

Optimise for survivability, not only for bandwidth or elegance under ideal conditions.

---

## Principle 5: Trust must be explicit.

Implicit trust in infrastructure is not trust. It is dependency.

Trust relationships should be named, bounded, and verifiable. Where possible, they should be supported by cryptographic means and designed to degrade in a controlled manner when infrastructure assumptions fail.

---

## Principle 6: Store-and-forward is a design posture.

Store-and-forward is not merely a transport feature. It is a way of treating messages as worth preserving across delay, fragmentation, and interruption.

A resilient system must be willing to hold state long enough for conditions to permit delivery.

This principle applies equally to packets, archives, manifests, shards, and physical media.

---

## Principle 7: Redundancy requires independence of failure modes.

Two copies on the same medium are not sufficient redundancy.
Two copies in the same location are not sufficient redundancy.
Two copies over the same channel are not sufficient redundancy.
Two copies made at the same time from the same source are not sufficient redundancy.

Meaningful redundancy requires independence across failure modes, including spatial, material, operational, channel, and temporal diversity.

---

## Principle 8: Context is part of the payload.

A message without context may be uninterpretable.
A key without instructions may be unusable.
An archive without framing may be indistinguishable from noise.

Systems intended for long-horizon survivability must carry enough context for a recipient without prior operational knowledge to understand what they have received and what should be done with it.

Context is not auxiliary. It is part of the signal.

---

## Principle 9: Time is a first-class design dimension.

Some participants may be delayed, unavailable, offline, or permanently unable to update. Systems must tolerate this.

Resilient protocols should accommodate long and uneven time horizons, including delayed delivery, archival recovery, succession, and interaction with stale but still trusted state.

A message recovered years later is still a message.

---

## Principle 10: Provenance should be legible within the system.

A resilient system should make its own origin, framing, and authorship as legible as possible from within the system itself.

Where practical, artifacts should identify their format, parameters, and provenance in forms recoverable without external infrastructure.

Self-description supports verification, recovery, and continuity.

---

A contribution is useful if it makes the system more likely to carry a signal across a gap.

That is the test.

---
