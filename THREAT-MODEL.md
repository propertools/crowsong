# Crowsong Threat Model

*Working document — for incorporation into `draft-darley-crowsong-01`*

**Version:** 0.1 (pre-normative)
**Classification:** TLP:CLEAR
**Status:** Design consensus. Captures the threat model assumptions,
adversary classes, and system properties that govern architectural
decisions across the Crowsong suite.

This is not yet a normative specification.

---

## What this system is designed to survive

The Crowsong stack is not designed for the world as it is. It is designed
for the world after something has gone wrong.

| Threat | Mechanism |
|--------|-----------|
| Infrastructure failure | FDS encoding + physical archive + DTN routing |
| Channel degradation | Human legibility + graceful error tolerance |
| Hardware loss | Mnemonic reconstruction from memory |
| Border crossing and inspection | Deniable seeds + no stored key material |
| Coercion and compelled decryption | Multi-fork staged release + decoy payloads |
| Regulatory pressure | Zero cryptographic claims + open standards process |
| Network loss | Local mirror + air-gap capability |
| Time | Archival materials + self-describing artifacts + provenance |

The system was designed to survive infrastructure failure. It turns out
it was also designed, almost accidentally, to survive borders,
confiscation, censorship, and coercion.

---

## Adversary classes

### Class A — Passive observer

**Capability:** monitors the channel; cannot modify traffic; performs
statistical analysis on intercepted data.

**Goal:** identify that a covert signal is present; determine payload
content.

**System response:**
- CCL3 output is statistically indistinguishable from AES-128 ciphertext
  (8.37 bits/token, exceeding the AES-128 reference of ~7.9–8.0 bits/byte)
- Five-digit decimal tokens are indistinguishable from telemetry, log
  files, financial reference numbers, or cross-reference lists
- The passive observer cannot distinguish CCL3 output from noise on the
  basis of entropy alone

**Limitation:** CCL provides no cryptographic confidentiality. A passive
observer who obtains the artifact and the key can decrypt. CCL raises the
cost of *attention*, not the cost of *decryption given attention*.

---

### Class B — Active inspector with physical access

**Capability:** searches the operator; inspects devices, printed material,
and personal effects; may compel disclosure.

**Goal:** obtain key material; access payload.

**System response:**

*No key material need be carried.* The key is one or more of:

- A verse held in memory ("I don't remember which poem" is genuine
  deniability)
- A publicly available image (a meme, a logo, a flag — "I just had
  some logo files")
- A folk melody as a semitone interval sequence ("I was humming something")
- A named mathematical constant at a declared offset (π is not contraband)

None of these are key material in the conventional sense. They are
unremarkable objects — cultural, public, and indestructible — that
become key material only through a deterministic computation performed
on demand.

*No payload need be present on the device.* The artifact may have been
pre-positioned via a prior transmission. The operator travels with
nothing but memory.

*The artifact, if present, is noise.* CCL3 output is statistically
indistinguishable from random data. A physical search finds decimal
numbers. Every digital device contains decimal numbers.

---

### Class C — Compelled decryption

**Capability:** legally or physically compels the operator to reveal keys
and decrypt content.

**Goal:** access the real payload; demonstrate that a covert payload exists.

**System response — duress decoy forks:**

A single artifact may contain multiple independently unlockable forks.
Under duress, the operator reveals a decoy key, which decrypts to a
plausible but non-sensitive payload. The real payload decrypts only under
a key the operator does not reveal.

Properties:
- Fork count is not detectable from the artifact exterior
- The decoy payload must be genuinely plausible (a poem, a field note,
  a key fragment — not obviously empty)
- "I have memorised two poems" is more deniable than a verse that is
  obviously constructed for the purpose
- Each fork fails independently — a failed unlock of one fork does not
  compromise others

**System response — multi-stakeholder staged release:**

Forks need not be decoy/real pairs. They can be functionally distinct
payloads with independent release gates held by different people:

```
Fork 1: firmware binary      → field engineer's verse
Fork 2: firmware source      → technical lead's binary seed
Fork 3: signing keys         → security officer's melody
```

No single person can unlock everything. Coercion of one person yields
one fork. The others remain inaccessible.

**Limitation:** duress decoy forks require actual encryption of fork
content. CCL alone is insufficient. This layer depends on a separate
encryption mechanism not yet specified in this suite.

---

### Class D — Regulatory adversary

**Capability:** legal authority to prohibit, restrict, or regulate
technologies; export control enforcement.

**Goal:** classify the system as a controlled cryptographic technology;
restrict distribution or use.

**System response:**

The regulatory attack surface is essentially zero.

UCS-DEC is:
- A subset of the decimal number system, which predates every government
  currently in existence
- A reference to the Unicode Standard, maintained by a consortium of the
  world's largest technology companies and load-bearing for essentially
  all modern computing
- Implemented in a Python script that does arithmetic a child could do
  by hand
- Owned by no one, patented by no one, funded by no one, depended upon
  by nothing

CCL is base conversion. The mathematical relationship between base 10
and base 7 has been known since there were bases. It is not possible to
make it illegal to represent 65 in base 8 without making arithmetic a
controlled technology.

The closest legal hook is export control on cryptography. The
specification explicitly and loudly states:

> *CCL provides no cryptographic confidentiality or integrity guarantees
> and MUST NOT be relied upon for cryptographic protection of any kind.*

This is not a loophole. It is accurate. It is documented that way
because it is true.

The practical test: load-bearing for nothing, used by no existing
applications, no commercial interest, no vendor, no revenue. Regulators
follow harm and they follow money. This system has neither.

See `EU_DECLARATION_OF_CONFORMITY.md`.

---

### Class E — Sophisticated cryptanalyst

**Capability:** full knowledge of the CCL construction; access to the
artifact including the RSRC block and twist-map; unlimited computation.

**Goal:** recover the payload without the key.

**System response:**

CCL makes no cryptographic claims and provides no security against this
adversary. The twist-map is stored in the artifact. A receiver who
obtains the complete artifact can reverse the transform without the key.

This is intentional and documented. CCL is a salience reduction
mechanism, not a confidentiality mechanism. Against a sophisticated
cryptanalyst who already has the artifact, CCL provides nothing.

Against this adversary, the correct tool is encryption, applied before
CCL. The pipeline is: encrypt → FDS encode → CCL. Encryption is a
separable layer; it is always available and never a precondition for
system function (Structural Principle 13).

---

## The coercion surface

Across all adversary classes, the coercion surface is consistently:

**which verse, which image, which melody, which sequence, which offset**

Not the key itself. Not the prime. Not the share. These exist nowhere
until derived on demand from unremarkable inputs that are either:
- Held in memory (verse, melody)
- Publicly available (image, named constant)
- In the cultural record (folk tune, published logo, canonical sequence)

The reconstruction key is never stored or transmitted directly. The
mnemonic and the key are semantically linked but computationally
separated. This separation is structural.

---

## Asynchronous key separation

Payload and key have fundamentally different transport requirements.
The system exploits this deliberately.

**Phase 1 — payload transfer** (bandwidth-sensitive, timing-flexible)

The artifact is transmitted whenever the link is available. It is
statistically indistinguishable from noise. Interception reveals nothing.
Pre-positioning is possible: transmit to all recipients when the
satellite window is open. The artifacts sit inert until the key arrives.

**Phase 2 — key transfer** (minimal bandwidth, timing-critical)

A verse and a sequence name. Transmissible as a voice call, a single
SMS, a Morse burst, a postcard, or spoken to a courier. The entire key
transfer is under 30 seconds of speech.

The key is released only when the operator is confident the recipient
is legitimate and the situation is right.

**The vulnerability inversion:**

Normally payload and key travel together — intercept one transmission,
get everything. Here:
- Payload intercepted alone: noise, no key
- Key intercepted alone: a poem, no artifact
- Both intercepted independently: attacker still needs to know *which*
  artifact, *which* sequence, *which* offset

---

## What the system does not claim

- **Confidentiality** — CCL provides no cryptographic confidentiality.
  Encrypt before applying CCL if confidentiality is required.
- **Authentication** — FDS provides integrity (CRC32) but not
  authentication. Ed25519 signatures are available but not mandatory.
- **Anonymity** — the system makes no claims about traffic analysis
  resistance or metadata protection.
- **Perfect forward secrecy** — the system makes no claims about key
  compromise affecting past sessions.
- **Quantum resistance** — the system makes no claims about resistance
  to quantum computation.

The system claims only what it delivers: signal survival across
infrastructure failure, channel degradation, and human-mediated
transmission. Confidentiality, when needed, is a separable layer
applied on top.

---

## Design axioms

These are the assumptions that govern every architectural decision.

**1. The network may not exist.**
Not degraded. Not congested. *Gone.* Every layer must be operable
without it.

**2. Software may not be available.**
Every layer must be operable by a human with patience and a printed
reference card.

**3. Hardware will be lost.**
Key material must be reconstructable from memory and public sources.
Nothing critical should exist only on a device.

**4. Adversaries observe everything transmitted.**
Design for a fully observed channel. Assume interception.

**5. Coercion is a real threat.**
The operator may be compelled to reveal keys. The system must degrade
gracefully under coercion — revealing a decoy without compromising
the real payload.

**6. Availability and integrity before confidentiality.**
The CIA triad is deliberately inverted. Confidentiality is always a
separable layer and never a precondition for system function.
(Structural Principle 13)

**7. The cultural record is indestructible.**
Poetry survives what numbers do not. Folk tunes survive civilisations.
Corporate logos are on every server. π has been known for millennia.
Key material anchored to the cultural record survives hardware loss,
border crossings, and coercion.

---

## One-line summary

The attack surface is the human, not the system. The system was designed knowing that.

---

*531 VALUES · CRC32:E8DC9BF3 · SIGNAL SURVIVES*
