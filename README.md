# Crowsong 🐦‍⬛

*What the passive listeners hear.*

A protocol suite for signals that must survive.

---

## What this is

Crowsong is a family of Internet-Drafts defining a layered communications architecture that remains **interpretable, verifiable, and transmissible** even when reduced to manual transcription over non-binary channels.

This is not a fallback property. It is a design constraint.

---

## The problem

When infrastructure fails, the channels that remain — fax, Morse, printed page, human relay — cannot reliably carry binary data.

Most “resilient” protocols assume a degraded IP network.

Crowsong assumes the network may not exist at all.

---

## The stack

```
L5  Content    →  Meridian Protocol
L4  Trust      →  SHARD-BUNDLE · MIRROR-ATTESTATION
L3  Routing    →  Delay-Tolerant Networking (RFC 4838)
L2  Encoding   →  Fox Decimal Script (FDS / UCS-DEC)
L1  Physical   →  LoRa · Morse · Fax · RF · Print · Human relay
```

---

## The drafts

```
draft-darley-meridian-protocol-01
  ↑ consumes
draft-darley-crowsong-00
  ↑ composes
draft-darley-fds-00           draft-darley-shard-bundle-00
  ↑ implements                  ↑ implements
tools/ucs-dec/ucs_dec_tool.py
```

| Draft                               | Description                                    |
| ----------------------------------- | ---------------------------------------------- |
| `draft-darley-fds-00`               | Encoding — human-transcribable Unicode decimal |
| `draft-darley-shard-bundle-00`      | Trust — threshold key distribution             |
| `draft-darley-crowsong-00`          | Architecture — how the system composes         |
| `draft-darley-meridian-protocol-01` | Content — continuity of web artifacts          |

---

## Repository layout

```
drafts/                       Internet-Drafts
drafts/meridian-protocol/     Meridian Protocol (submodule)
tools/ucs-dec/                reference implementation (FDS)
docs/                         supporting material and guides
archive/                      canonical test vectors
tests/roundtrip/              verification scripts
bible/                        structural principles (design doctrine)
```

---

## Quick start

```bash
# Encode
echo "Signal survives." | python3 tools/ucs-dec/ucs_dec_tool.py --encode

# Decode
echo "00083 00105 00103 00110 00097 00108" | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode

# Decode the canonical test vector
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode

# Verify
bash tests/roundtrip/run_tests.sh
```

---

## The design in one sentence

Every layer of the system must be operable by a human with patience and appropriate reference material.

---

## The test vector

The canonical test vector is a poem:

```
archive/flash-paper-SI-2084-FP-001-framed.txt
archive/flash-paper-SI-2084-FP-001-payload.txt
archive/second-law-blues.txt
```

```bash
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode
```

Expected result: legible text.

---

## Where to go next

* **Start here (implementation):**
  `drafts/draft-darley-fds-00.txt`

* **Architecture:**
  `drafts/draft-darley-crowsong-00.txt`

* **Trust layer:**
  `drafts/draft-darley-shard-bundle-00.txt`

* **Content continuity:**
  `drafts/meridian-protocol/draft-darley-meridian-protocol-01.txt`

* **Design doctrine:**
  `bible/structural-principles.md`

* **Full suite overview:**
  `docs/crowsong-suite-overview.md`

---

## On the name

In the Aeolian Layer — a kite-borne delay-tolerant mesh network, described in the in-progress `draft-darley-aeolian-dtn-arch-01` — the passive listeners are called Crows.

A crowsong is what they hear.

---

## Status

Early drafts. Subject to revision.

Feedback welcome via:

* GitHub Issues
* Email: [trey@propertools.be](mailto:trey@propertools.be)
* IETF DTNWG / DISPATCH

---

*"The signal strains, but never gone —
I fought Entropy, and I forged on."*

---
