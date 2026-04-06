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

## The stack

```
L5  Content    →  Meridian Protocol
L4  Trust      →  SHARD-BUNDLE · MIRROR-ATTESTATION
L3  Routing    →  Delay-Tolerant Networking (RFC 4838)
L2  Encoding   →  Fox Decimal Script (FDS / UCS-DEC)
L1  Physical   →  LoRa · Morse · Fax · RF · Kite-borne relay · Print · Human relay
```

---

## The drafts and how they fit together

```
draft-darley-meridian-protocol-01
  ↑ consumes
draft-darley-crowsong-00
  ↑ composes
draft-darley-fds-00              draft-darley-shard-bundle-00
  ↑ implements                     ↑ implements
tools/ucs-dec/ucs_dec_tool.py    tools/mnemonic/
  + tools/primes/                  verse_to_prime.py
  + tools/constants/               prime_twist.py
  + tools/sequences/
  + tools/baseconv/

draft-darley-fds-ccl-prime-twist-00   (pre-normative)
  ↑ specifies
tools/mnemonic/prime_twist.py
```

### Where to start

- **Start with `draft-darley-fds-00`**
  If you want to implement something immediately.
  Self-contained. No dependencies. Reference implementation included.
  Eight-test roundtrip suite passing.

- **Read `draft-darley-crowsong-00`**
  For the architecture: how the layers compose and why.

- **Read `draft-darley-shard-bundle-00`**
  For the trust model: distributing key material and verifying integrity
  without assuming working infrastructure.

- **Read `draft-darley-meridian-protocol-01`**
  For the content layer: preserving addressability and continuity of
  web artifacts beyond origin failure.

- **Read `draft-darley-fds-ccl-prime-twist-00`** *(pre-normative)*
  For the Channel Camouflage Layer: prime-derived base-switching that
  raises FDS payload entropy above the AES-128 ciphertext reference
  without any cryptographic dependencies.

- **Run `demo/ccl_demo.sh`**
  Nine-step live demonstration of the full CCL pipeline.
  One terminal window. No setup beyond the tools.

---

## The design in one sentence

Every layer of the system must be operable by a human with patience
and appropriate reference material.

---

## The design principles

Thirteen structural principles govern every design decision in the stack.
The most important for new readers:

**Principle 1:** Design for the failure case. The normal case takes care
of itself.

**Principle 3:** Human legibility is a hard requirement. Any layer that
cannot be operated by a patient human with reference material has a single
point of failure in software.

**Principle 11:** SHOULD is a design smell. There is MUST, MUST NOT, and
design work still to be done.

**Principle 13:** Availability and integrity before confidentiality. The
CIA triad is deliberately inverted. Confidentiality is a separable layer,
never a precondition for system function.

Full text: `docs/structural-principles.md`

---

## The test vector

The canonical test vector is a poem: *Second Law Blues* by T. Darley,
attributed 桜稲荷 (Sakura Inari). It is encoded as an FDS flash paper
artifact.

```
archive/flash-paper-SI-2084-FP-001-framed.txt   (framed)
archive/flash-paper-SI-2084-FP-001-payload.txt  (payload)
archive/second-law-blues.txt                    (source)
```

Properties:
- 531 VALUES · CRC32:E8DC9BF3
- WIDTH/5 · COL/6 · PAD/00000 · NFC
- First three tokens: 26716 · 31282 · 33655 → 桜稲荷
- The encoding carries its own attribution

Suggested exercise:

```bash
# Decode
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
    python tools/ucs-dec/ucs_dec_tool.py --decode

# Verify framed artifact
python tools/ucs-dec/ucs_dec_tool.py -v \
    < archive/flash-paper-SI-2084-FP-001-framed.txt
# Expected: 531 OK, E8DC9BF3 OK

# Run full test suite
bash tests/roundtrip/run_tests.sh
# Expected: 8 passed, 0 failed

# Apply CCL3 — raises entropy from 4.78 to 8.37 bits/token
python tools/mnemonic/prime_twist.py stack \
    --verse-file verses.txt --ref CCL3 \
    < archive/flash-paper-SI-2084-FP-001-payload.txt \
    > /tmp/stacked.txt

# Recover
python tools/mnemonic/prime_twist.py unstack /tmp/stacked.txt | \
    python tools/ucs-dec/ucs_dec_tool.py -d
# Expected: the poem, intact
```

---

## How prime-twisting works

Imagine you have a message encoded as a stream of five-digit decimal
numbers — the FDS encoding. Something like:

```
00084 00104 00101 00032 00115 00105 00103 00110 00097 00108 ...
```

To a trained eye, this is recognisable. The values cluster in a
predictable range. The entropy is low. A passive observer scanning
for unusual traffic might notice it.

CCL — the Channel Camouflage Layer — disguises this by re-encoding
each token in a different numeric base, driven by a key.

The key is a prime number. You derive the prime from something
memorable: a line of poetry, a folk melody, a specific image. The
prime's decimal digits become the key schedule — one digit per token,
cycling through the prime's digits like a wheel (the ouroboros).

For each token, the scheduled digit tells you which base to use:
digit 5 means base 5, digit 8 means base 8, and so on. The token
value is re-expressed in that base, still zero-padded to five digits.
The output is still decimal digits — still valid FDS — but the
distribution looks completely different.

The result after three passes (CCL3), using three different verse-
derived primes as keys:

- The original 53 distinct token values become 375
- Entropy rises from 4.78 to 8.37 bits/token
- Statistical analysis cannot distinguish the output from AES-128
  ciphertext

Everything needed to reverse the operation — which base was used at
each position — is recorded in the artifact's resource block (the
twist-map). The receiver unstacks the passes in reverse order and
recovers the original token stream exactly.

The keys live nowhere until needed. Recite the verse. Derive the
prime. Untwist the artifact. The signal was always there.

CCL provides no cryptographic confidentiality — it raises the cost
of passive attention, not the cost of active decryption. For
confidentiality, encrypt before encoding. For camouflage, apply CCL
after. The layers are independent and composable.

![CCL prime-twist construction](./ccl-prime-twist-construction.png)

*Figure: The prime-twist construction. The prime's digits drive a
cyclic key schedule (the ouroboros). Each digit selects a candidate
base; the feasibility rule applies the fallback; the twist-map
records what actually happened. The twist-map — not the schedule —
is authoritative for reversal.*

---

## The CCL result

Triple-pass prime-twist CCL on the canonical 534-token payload:

| Stage | Entropy | Unique tokens |
|-------|---------|---------------|
| Original UCS-DEC | 4.78 bits/token | 53 |
| CCL1 | 6.96 bits/token | 172 |
| CCL2 | 7.82 bits/token | 282 |
| CCL3 | **8.37 bits/token** | 375 |
| AES-128 reference | ~7.9–8.0 bits/byte | — |

Keys are verses. Verses live in memory. The prime exists nowhere until
the moment of derivation. The twist-map travels in the artifact.
CCL provides no cryptographic confidentiality — it raises the cost of
passive attention.

---

## The local knowledge layer

The Vesper system provides the long-horizon physical infrastructure:

- **Vesper Archive** — archival paper, Mylar microclimate, silica gel,
  Pelican case, 80cm depth, two sites minimum. Designed to carry the
  signal forward 50+ years without electricity or software.
  `docs/vesper-archive-protocol.md`

- **Vesper Mirror** — local knowledge and package infrastructure.
  Air-gapped for availability, not secrecy. ~360GB: packages, RFCs,
  Wikipedia, Gutenberg, legal corpus, local AI inference (Ollama +
  Meilisearch). Zero bytes leave the network.
  `docs/vesper-mirror-architecture.md`

Both are concrete instantiations of Structural Principle 13:
availability and integrity before confidentiality. All the way down.

---

## The provenance chain

```
2012  credmgr              Shamir over GPG email
                           trusted humans, shard distribution
2026  Fox Decimal Script   encoding for any channel
      Meridian Protocol    content continuity and authorship
      Crowsong suite       the stack formalised
      CCL prime-twist      statistical camouflage, verse-derived keys
      Vesper               physical archival and local mirror
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

## What the system is capable of

The repo that defines the encoding can be transmitted using the encoding.

A UCS-DEC tarball of the entire Crowsong repository fits in a
photographic microdot — invisible to casual inspection, printable on
any photograph, recoverable with a magnifier and patience. The toolchain
decodes itself on arrival. The keys reconstruct from memory and from
public mathematics that has existed for centuries.

There is nothing preventing someone from carrying the entire Crowsong
system across a border as a microdot on a tourist snapshot. On the
other side: a git checkout, an old Android phone, an embedded Python
interpreter, and the system is operational. The keys come from a poem
held in memory and a meme posted publicly years ago. The key material
was already encoded in π before the operator was born.

The adversary's options are:

- Confiscate all photographs — impractical at scale
- Confiscate all printed material — impractical at scale
- Prevent memorisation of poetry — impossible
- Erase π — impossible

The attack surface is the human, not the system. The system was
designed knowing that.

This means the Vesper archive is not only long-horizon storage. It is
a deployment mechanism. The FDS quick reference card tells you how to
decode what you find. The encoding is human-operable without software.
The camouflage is indistinguishable from AES output. The keys are
distributed across memory, mathematics, and the cultural record.

The system was designed for the network not existing at all. It turns
out it was also designed for borders, confiscation, censorship, and
the specific category of adversary who can observe everything except
what has already been memorised and what is already in the cultural
record.

---

## On the name

In the Aeolian Layer — a delay-tolerant mesh operating over
non-standard physical channels — passive listeners are called Crows.

A *crowsong* is what they receive.

It is the signal that arrives intact despite delay, degradation,
and loss of infrastructure.

The system does not require identity.

It requires consistency.
