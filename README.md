# Crowsong 🐦‍⬛

*What the passive listeners hear.*

A protocol suite for signals that must survive.

---

## What this is

Crowsong is a family of Internet-Drafts defining a layered communications architecture that degrades gracefully to human legibility at every layer.

**The defining requirement:** messages MUST remain interpretable, verifiable, and transmissible even when reduced to manual transcription over non-binary channels.

This is not a fallback property. It is a design constraint.

---

## Repository layout

```
drafts/                       Internet-Drafts and companion specifications
drafts/meridian-protocol/     linked submodule for the Meridian Protocol
tools/ucs-dec/                reference implementation for FDS / UCS-DEC
docs/                         quick reference material and supplementary notes
archive/                      canonical test vectors and historical artifacts
tests/roundtrip/              basic roundtrip verification
```

---

## Suggested reading order

**For the specifications:**

1. `drafts/draft-darley-crowsong-00.txt`
2. `drafts/draft-darley-fds-00.txt`
3. `drafts/draft-darley-shard-bundle-00.txt`
4. `drafts/meridian-protocol/draft-darley-meridian-protocol-01.txt`

**For implementation:**

1. `tools/ucs-dec/ucs_dec_tool.py`
2. `tests/roundtrip/run_tests.sh`

**For the canonical "Second Law Blues":**

1. `archive/second-law-blues.txt`

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

L1  Physical   →  LoRa · Morse · Fax · RF · Acoustic
                  Print · OCR · USB · Human relay · Kite-borne relay
```

| Draft | Description | Status |
|---|---|---|
| `draft-darley-crowsong-00` | Architecture and layer interfaces | -00 |
| `draft-darley-fds-00` | Fox Decimal Script encoding spec | -00 |
| `draft-darley-shard-bundle-00` | Threshold trust primitives | -00 |
| `draft-darley-meridian-protocol-01` | Content sovereignty layer | -01 |

---

## Quick start

The reference implementation has no dependencies beyond the Python 3 standard library.

```bash
# Encode a short message
echo "Signal survives." | python3 tools/ucs-dec/ucs_dec_tool.py --encode

# Decode a short sample
echo "00083 00105 00103 00110 00097 00108" | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode

# Decode the canonical test vector
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode

# Run roundtrip tests
bash tests/roundtrip/run_tests.sh
```

---

## Fox Decimal Script (FDS)

FDS encodes any Unicode text as zero-padded decimal integers — one per Unicode code point, space-separated, with six values per row by default.

*In extremis: operable with a Unicode table and patience.*

```
Input:   Hello
Encoded: 00072  00101  00108  00108  00111  00010
```

Any person with a Unicode table can decode this by hand. No software required. A corrupted value affects only that character. The format degrades gracefully because degraded channels are the point.

### The Unicode quick reference table

`docs/fds-unicode-reference.txt` is a 314-line (π × 100) human-readable reference covering eight sections:

| § | Section | Contents |
|---|---|---|
| 1 | Control and whitespace | null, tab, LF, CR, space |
| 2 | ASCII printable (32–126) | full named entries + compact grid |
| 3 | Extended Latin | diacritics: French, German, Spanish… |
| 4 | General punctuation | em dash, curly quotes, ellipsis, · |
| 5 | Utility symbols | arrows, math, ✓ ✗ ⚠ ★ ☐ |
| 6 | CJK and attribution | 桜稲荷 named + range notes |
| 7 | Emoji (WIDTH/7 required) | worked example below |
| 8 | Quick decode grid | compact ASCII 32–126 for hand use |

Designed to fit on two sides of A4, printable on archival paper, legible without magnification. Include it in any physical archive or SHARD-BUNDLE that may need to be decoded without software.

### Worked example — The Fox, the Chicken, and the Grain

The classic river-crossing problem, encoded in FDS.

| Glyph | Unicode | Decimal | FDS (WIDTH/7) | Role |
|---|---|---|---|---|
| 🚣 | U+1F6A3 | 128675 | 0128675 | the farmer / operator |
| 🐓 | U+1F413 | 128019 | 0128019 | the chicken |
| 🦊 | U+1F98A | 129418 | 0129418 | the fox |
| 🌾 | U+1F33E | 127806 | 0127806 | the grain |

All four exceed 99999. WIDTH/7 is required.

```
ENC: UCS · DEC · COL/4 · PAD/0000000 · WIDTH/7
0128675  0128019  0129418  0127806
4 VALUES · VERIFY COUNT BEFORE USE

Decoded: 🚣🐓🦊🌾
```

The fox cannot be left with the chicken. The chicken cannot be left with the grain. The farmer must make multiple crossings, not just one.

Store-and-forward. Routing around constraints. The mesh does not require you to cross everything at once.

---

## The canonical test vector

The test vector for `draft-darley-fds-00` is a poem.

```
archive/flash-paper-SI-2084-FP-001-framed.txt
archive/flash-paper-SI-2084-FP-001-payload.txt
archive/flash-paper-SI-2084-FP-001.md
archive/second-law-blues.txt
```

The first three values decode to 桜稲荷. The artifact begins with its own attribution.

```bash
# Roundtrip test (expected: all pass)
bash tests/roundtrip/run_tests.sh

# Decode the payload
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode
```

---

## On the name

In the Aeolian Layer — a kite-borne delay-tolerant mesh network, described in the in-progress `draft-darley-aeolian-dtn-arch-01` — the passive listeners are called Crows.

A crowsong is what they hear.

It is what FDS produces on a degraded channel. What arrives eleven days late with verified integrity. The signal that comes through after the wind and the earthquake and the fire have gone quiet.

The mesh does not require you to know who someone is. It requires you to know that their signal is consistent.

---

## Provenance

| Date | Project | Notes |
|---|---|---|
| 2012-06-23 | `credmgr` | First commit. Shamir secret sharing over GPG-encrypted email. The trust layer, fourteen years before it had that name. [github.com/treyka/credmgr](https://github.com/treyka/credmgr) |
| 2026 | Fox Decimal Script | encoding for any channel |
| 2026 | Meridian Protocol | content sovereignty, URL continuity |
| 2026 | Crowsong suite | the stack formalised. [github.com/propertools/crowsong](https://github.com/propertools/crowsong) |
| draft | Aeolian Layer *(in progress)* | the stack at national scale — kite-borne DTN, Brussels |
| 2084 | Ghost Line | an unknown node, still transmitting |
| 2084 | Fifty mirrors | the Mundaneum, finally distributed |
| 2084 | SI-2084-FP-001 | encoded in its own format, inside the back of a book, at Atlanta Greyhound. **RESERVED — SINGLE USE** |

The SHARD-BUNDLE specification in `draft-darley-shard-bundle-00` is the formal descendant of `credmgr`. The jump from GPG-encrypted email to FDS-encoded physical archives is smaller than it appears: both are answers to the same question, which is how to carry a secret across a gap in the infrastructure to someone who needs it on the other side.

*The 314-line count of the reference table is entirely accidental.*

---

## Licensing

See `LICENSES.md` for the complete licensing picture.

- `tools/` — MIT
- `drafts/` — IETF Trust / authors
- `archive/` — CC0 unless otherwise noted

---

## Status and comments

These are -00 drafts, except Meridian, which is currently -01. Everything is subject to revision.

Comments welcome via:

- GitHub Issues (preferred)
- Email: trey@propertools.be
- IETF DTNWG or DISPATCH mailing lists
- Any surviving internet exchange point

---

> *"The signal strains, but never gone — I fought Entropy, and I forged on."*
> — Second Law Blues, SI-2084-FP-001
