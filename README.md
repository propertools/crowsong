# Crowsong

*What the passive listeners hear.*

A protocol suite for signals that must survive.

---

## What this is

Crowsong is a family of Internet-Drafts defining a layered
communications architecture that degrades gracefully to human
legibility at every layer.

The defining requirement: messages MUST remain interpretable,
verifiable, and transmissible even when reduced to manual
transcription over non-binary channels.

This is not a fallback property. It is a design constraint.

---

## The stack

```
L5  Content    →  Meridian Protocol
                  Signed manifests, asset graphs, succession terms
                  Author sovereignty, URL continuity

L4  Trust      →  SHARD-BUNDLE · MIRROR-ATTESTATION
                  Shamir secret sharing, Ed25519 signing
                  Multi-party attestation, key custody
                  Operable over physical media

L3  Routing    →  Delay-Tolerant Networking (RFC 4838)
                  Store-and-forward, bundle protocol
                  DTN-BUNDLE-FDS for non-binary channels

L2  Encoding   →  Fox Decimal Script (FDS / UCS-DEC)
                  Physical-layer agnostic serialisation
                  Human-transcribable, machine-verifiable
                  Operable with a Unicode table and patience

L1  Physical   →  LoRa · Morse · Fax · RF · Acoustic
                  Print · OCR · USB · Human relay · Kite
```

---

## Drafts

| Draft | Description | Status |
|-------|-------------|--------|
| [draft-darley-resilient-signal-stack-00](drafts/draft-darley-resilient-signal-stack-00.txt) | Architecture and layer interfaces | -00 |
| [draft-darley-fds-00](drafts/draft-darley-fds-00.txt) | Fox Decimal Script encoding spec | -00 |
| [draft-darley-shard-bundle-00](drafts/draft-darley-shard-bundle-00.txt) | Threshold trust primitives | -00 |
| [draft-darley-meridian-protocol-01](drafts/draft-darley-meridian-protocol-01.txt) | Content sovereignty layer | -01 |

---

## Quick start

No dependencies beyond Python 3 standard library.

```bash
# Encode
echo "Signal survives." | python3 tools/ucs-dec/ucs_dec_tool.py --encode

# Decode
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode

# Verify the canonical test vector
bash tests/roundtrip/run_tests.sh
```

---

## The canonical test vector

The test vector for `draft-darley-fds-00` is a poem.

`archive/flash-paper-SI-2084-FP-001.md` is the canonical encoded
artifact — 530 values, COL/6, WIDTH/5. The first three values
decode to 桜稲荷. The encoding eats its own attribution.

`archive/second-law-blues.md` is the poem in plain text.

A conformant FDS implementation MUST roundtrip the poem
byte-for-byte against the canonical artifact.

```bash
# Roundtrip test
cat archive/second-law-blues-raw.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --encode | \
  diff - archive/flash-paper-SI-2084-FP-001-payload.txt
# Expected: no output
```

---

## On the name

In the Aeolian Layer — a kite-borne delay-tolerant mesh network
described in `draft-darley-aeolian-dtn-arch-00`, a work in progress
of the Royal Society for the Orderly Management of Unruly Phenomena,
and the Experimental Pursuit of Sobriety (with Light Refreshment) —
the passive listeners are called Crows.

A crowsong is what the passive listeners hear.

It is what FDS produces on a degraded channel. It is what arrives
eleven days late with verified integrity. It is the signal that
comes through after the wind and the earthquake and the fire have
gone quiet.

The mesh does not require you to know who someone is.
It requires you to know that their signal is consistent.

---

## Provenance

The `tools/ucs-dec/` reference implementation descends from work
begun in 2026. The `drafts/` descend from Meridian
(`draft-darley-meridian-protocol-01`), first published March 2026.
The trust layer descends from `credmgr` (2012), available at
`github.com/treyka/credmgr`. The routing layer is RFC 4838 (2007).

The canonical test vector was instantiated on flash paper in 2026.
It appears, described as found in the back of a book at Atlanta
Greyhound terminal in September 2013, in the novel *2084*.

The 530-value count is not accidental.

---

## Status and comments

These are -00 drafts. Everything is subject to revision.

Comments welcome via:
- GitHub Issues (preferred)
- Email: trey@propertools.be
- IETF DTNWG or DISPATCH mailing lists
- Any surviving internet exchange point

---

## License

Drafts: IETF Trust (see individual documents)
Tools: MIT
Archive: CC0 (public domain)

---

*"The signal strains, but never gone —*
*I fought Entropy, and I forged on."*

— Second Law Blues, SI-2084-FP-001
