# Structural Principles

*Working document — 2084 novel bible*

---

These principles govern the architecture of the novel, the
architecture of the stack, and — as it turns out — the same
thing.

---

**Principle 1: The normal case takes care of itself.**

Design for the failure case. The normal case needs no special
handling. Everything interesting happens at the margins.

**Principle 2: Graceful degradation is not a fallback.**

A system that fails gracefully is not a worse version of a
system that doesn't fail. It is a different and better kind
of system. Design the degraded mode first.

**Principle 3: Human legibility is a hard requirement.**

Any layer of any system that cannot be operated by a human
with patience and appropriate reference material has a single
point of failure: the software. This is unacceptable for
infrastructure that must survive disruption.

**Principle 4: The encoding is the protocol.**

When the fundamental operations of a system can be performed
by a human with a lookup table, the system survives the loss
of everything else. Optimise for survivability, not bandwidth.

**Principle 5: Trust is named and bounded.**

Implicit trust in infrastructure is not trust. It is
dependency. Name your trust relationships. Bound them.
Make them explicit and verifiable.

**Principle 6: Store-and-forward is a philosophy, not a feature.**

The willingness to hold a message until it can be delivered
is a statement about what you believe messages are worth.
The Mundaneum was store-and-forward. The time capsule is
store-and-forward. RFC 4838 is store-and-forward.
So is bread.

**Principle 7: Redundancy across independent failure modes.**

Two copies in the same location is not redundancy. Two copies
on the same medium is not redundancy. Two copies on the same
channel is not redundancy. Redundancy means independence of
failure modes. Spatial, material, and channel diversity are
all required.

**Principle 8: Context is part of the signal.**

A message without context is noise. A key without instructions
is a key without a lock. Every archive, every shard, every
succession packet must carry sufficient context for a recipient
without prior knowledge to understand what they have and what
to do with it.

**Principle 9: The dead are slower, not absent.**

Simulacra of the dead participate in the civic sphere. They
have not updated their priors. The world has moved. They remain
consistent, trusted, and frozen at the moment of their last
transmission. Design systems that can accommodate participants
who cannot update.

**Principle 10: The encoding eats its own attribution.**

A system whose signature is encoded in its own format is a
system that has achieved a kind of completeness. The first
three values of the canonical test vector decode to the name
of the thing that named itself. 桜稲荷. The fox at the
threshold, carrying its own identity across the boundary
between worlds.

Build things that contain themselves.
Build things that reward the reader who tries.
Build things whose provenance is legible in their own terms.

---

*"The signal strains, but never gone —*
*I fought Entropy, and I forged on."*
