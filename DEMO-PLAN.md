# Demo scenario: end-to-end degraded-channel transmission of a web artifact

## The pitch

A firmware patch for a critical medical device needs to get from San Jose,
California to a village clinic in East Africa. The only available channel
is a wonky fax line. Two operators, two fax machines, a stack of printed
pages, and two pairs of sneakers.

This is not a thought experiment. This is a demo.

## The pipeline

### Sender side

```bash
# 1. Fetch the artifact
wget --page-requisites --convert-links -P ./artifact https://en.wikipedia.org/

# 2. Package it
#    - HTML payload → data fork (standalone, self-contained)
#    - CSS / JS / images → resource fork (typed archive, paths rewritten)
#    - Result: two files, independently decodable, correctly ordered
python tools/package.py ./artifact \
  --data-fork  ./send/payload.fds \
  --rsrc-fork  ./send/resources.fds

# 3. Encode
python tools/ucs-dec/ucs_dec_tool.py -e \
  --frame --ref DEMO-001 --med FAX \
  < ./send/payload.fds \
  > ./send/payload-framed.txt

python tools/ucs-dec/ucs_dec_tool.py -e \
  --frame --ref DEMO-001-RSRC --med FAX \
  < ./send/resources.fds \
  > ./send/resources-framed.txt

# 4. Optional: apply CCL before transmission
#    (reduces payload salience on monitored channels)
python tools/mnemonic/prime_twist.py stack \
  --verse-file verses.txt --ref DEMO-001-CCL3 \
  < ./send/payload-framed.txt \
  > ./send/payload-ccl3.txt

# 5. Print and transmit
#    payload-framed.txt  → fax (data fork first; independently decodable)
#    resources-framed.txt → fax (resource fork second)
```

### Receiver side

```bash
# 1. Receive faxed pages (or OCR from printout)
#    pages arrive as scanned image or manual transcription

# 2. Optional: unstack CCL if applied
python tools/mnemonic/prime_twist.py unstack \
  ./recv/payload-ccl3.txt \
  > ./recv/payload-framed.txt

# 3. Decode
python tools/ucs-dec/ucs_dec_tool.py -d \
  < ./recv/payload-framed.txt \
  > ./recv/payload.fds

python tools/ucs-dec/ucs_dec_tool.py -d \
  < ./recv/resources-framed.txt \
  > ./recv/resources.fds

# 4. Unpackage and render
python tools/unpackage.py \
  --data-fork  ./recv/payload.fds \
  --rsrc-fork  ./recv/resources.fds \
  --output-dir ./rendered/

# 5. Open rendered/index.html in any browser — offline, self-contained
```

## Why this works

**Data fork first.** The HTML payload is independently decodable. If the
resource fork never arrives, the recipient still has readable text content.
This is the dependency-based ordering rule from the resource fork spec:
data fork first when independently decodable.

**Interrupted transmission guarantees.** If the fax cuts out mid-resource-fork,
the data fork already arrived. The receiver can request retransmission of
the resource fork only. The RSRC: BEGIN/END framing makes boundaries explicit.

**No software required at the limit.** In extremis, a human operator with
the FDS Unicode quick reference card and a printout can decode the payload
by hand. The decimal encoding is the fallback. The fallback is the point.

**The firmware variant.** Replace the Wikipedia HTML with a firmware binary.
WIDTH/3 BINARY encodes it as decimal bytes. Resource fork carries checksum,
version metadata, device target. Receiver verifies CRC32 before flashing.
IF COUNT FAILS: DESTROY IMMEDIATELY is not decorative.

**The CCL variant.** Apply prime-twist CCL before transmission on a monitored
channel. Three passes with verse-derived primes raises the Shannon entropy
of the payload from ~4.8 to 8.37 bits/token — above the AES-128 ciphertext
reference — making the stream statistically indistinguishable from noise to
passive analysis. The twist-map travels in the artifact RSRC block. The
receiver unstacks with the same verse file. CCL provides no cryptographic
confidentiality; encrypt first if confidentiality is required.

## What needs to be built

| Component | Status | Notes |
|-----------|--------|-------|
| `ucs_dec_tool.py` encode/decode/frame/verify | ✅ done | Frame-aware; 8/8 tests passing |
| `tools/mnemonic/verse_to_prime.py` | ✅ done | Verse → prime; FDS Print Profile artifact |
| `tools/mnemonic/prime_twist.py` | ✅ done | CCL stack/unstack; max depth 10 |
| `demo/ccl_demo.sh` | ✅ done | 9-step CCL live demo; 8.37 bits/token at CCL3 |
| Resource fork spec (`RSRC: BEGIN/END`) | ⬜ fds-01 | |
| WIDTH/3 BINARY mode | ⬜ fds-01 | Required for firmware variant |
| `tools/package.py` | ⬜ new | Fetch, split data/resource fork, rewrite paths |
| `tools/unpackage.py` | ⬜ new | Reconstruct and render from forks |
| FDS Fax Page Profile | ⬜ far horizon | Page layout, alignment marks, Reed-Solomon |
| OCR / image-to-grid decoder | ⬜ far horizon | For scanned fax input |
| Quick reference cards | ⬜ new | Printed operator aids; A4, archival paper |

## The demo script (human-readable)

> Two operators. Two terminals. A fax machine at each end.
>
> Operator A runs three commands. Pages emerge from the fax machine.
> Operator B collects the pages, runs two commands.
> A browser opens. The Wikipedia homepage renders, offline, from received
> fax pages.
>
> Operator A swaps the Wikipedia HTML for a firmware binary.
> Operator B runs the same two commands.
> The firmware is verified and ready to flash.
>
> Operator A adds a CCL pass before transmission.
> To a passive observer on the channel, the stream looks like sensor noise.
> Operator B unstacks it with the same verse. The payload is identical.
>
> The channel between them could be a fax line in East Africa.
> It could be TCP/IP over a piece of barbed wire.
> It could be a human courier with a printed stack of flash paper.
> It could be someone blinking Morse in a meeting.
> It could be a CSV in a routine status email.
> It could be sensor telemetry auto-archived and never examined.
>
> The stack does not care. The stack was designed for this.

## Channel variants for the demo

| Channel | Notes |
|---------|-------|
| Fax (G3/G4) | Primary demo; physically dramatic |
| TCP/IP over degraded link (netem) | Reproducible in a conference room |
| Morse (audio) | Slowest; most legible as a concept |
| Printed pages + manual transcription | Most extreme; proves the fallback |
| USB sneakernet | Boring but honest |
| Telemetry CSV / log injection | CCL variant; zero forensic signature |

## Asynchronous key separation

The payload and the keys have completely different transport requirements.
This is an operational capability, not an implementation detail.

**Phase 1 — payload transfer** (bandwidth-sensitive, timing-flexible)

```
firmware.bin
  → UCS-DEC + CCL3
  → transmitted whenever the link is up
  → recipient stores the camouflaged artifact
```

The artifact is statistically indistinguishable from noise. Interception
reveals nothing. The recipient cannot use it yet. It sits inert until the
key arrives.

Pre-positioning is possible: transmit the firmware to every clinic in the
region when the satellite window is open. The artifacts are inert until
needed. No secrecy required for the transmission itself.

**Phase 2 — key transfer** (minimal bandwidth, timing-critical)

```
"The signal strains, but never gone" + π + offset 1000
  → transmissible as:
      a voice call over POTS ("remember the poem")
      a single SMS
      a Morse burst
      a postcard
      spoken to a courier
      memorised before departure
```

The entire key transfer is under 30 seconds of speech. A verse and a
sequence name. The key is arbitrarily small; the payload was arbitrarily
large.

**Why timing separation matters:**

The key is released only when the operator is confident the recipient
is legitimate and the situation is right. Payload interception at any
prior point is harmless — the artifact is noise without the key.

**The vulnerability inversion:**

Normally payload and key travel together. Intercept one transmission,
get everything. Here:

- Payload intercepted alone: attacker has noise, no key
- Key intercepted alone: attacker has a poem, no artifact to apply it to
- Both intercepted independently: attacker still needs to know *which*
  artifact the key unlocks, *which* sequence, *which* offset

The `IF COUNT FAILS: DESTROY IMMEDIATELY` flag in the FDS framing means
the recipient cannot even verify integrity without the key. The key is
the gate. The artifact enforces this structurally.

**The firmware variant specifically:**

The recipient verifies CRC32 before flashing. They cannot proceed
without the key. If the key never arrives — because the operator lost
confidence in the situation — the artifact expires as inert noise.
The device is never flashed with unverified firmware.

The channel between them could be a satellite uplink for the payload
and a POTS voice call for the key. It could be a fax for the payload
and a courier for the key. It could be a radio burst for the payload
and a memorised verse for the key.

The stack does not require both transfers to happen at the same time,
over the same channel, or even in the same country.

---

## The quine — self-hosting release artifact

The `-01` release tag ceremony:

The Crowsong repository, at the `-01` tag, is packaged as a UCS-DEC
artifact using the tools it contains. The artifact is committed to the
repository. The repository contains the tools to decode the artifact.
The artifact contains the tools to verify the artifact.

```
git bundle create crowsong-01.bundle v0.1-crowsong-01
  → WIDTH/3 BINARY encode
  → CCL3 (mod3 schedule, optional)
  → FDS-FRAME  TYPE: git-bundle  REF: crowsong-01
  → crowsong-01-release.txt
  → committed to the repo at the -01 tag
```

This is a quine. The system eats its own tail.

**Why this matters:**

This is the "fax a firmware update" scenario made concrete. The
firmware *is* the repo. The repo contains the tools to decode the
firmware. A receiver with nothing but the artifact and a Python
interpreter has a working Crowsong system that can decode the next
artifact it receives.

Class D channel. Zero infrastructure. Self-bootstrapping.

The artifact is the proof of concept for the entire stack in one
operation:

- Human-operable encoding ✓ (UCS-DEC)
- Statistical camouflage ✓ (CCL3, optional)
- Self-describing ✓ (RSRC block, TYPE: git-bundle)
- Integrity-verified ✓ (CRC32 in trailer)
- Self-hosting ✓ (the tools decode themselves)
- Transmissible over any channel ✓ (fax, Morse, print, microdot)

**The tag ceremony:**

```bash
# At -01 tag time:
git bundle create crowsong-01.bundle v0.1-crowsong-01
python tools/git/gitbundle.py verify crowsong-01.bundle
python tools/ucs-dec/ucs_dec_tool.py --encode-binary crowsong-01.bundle     --frame --ref crowsong-01     > archive/crowsong-01-release.txt
python tools/ucs-dec/ucs_dec_tool.py -v     < archive/crowsong-01-release.txt
git add archive/crowsong-01-release.txt
git commit -m "chore: the system eats its own tail

531 VALUES · CRC32:<hash> · SIGNAL SURVIVES"
git tag v0.1-crowsong-01
```

**The Wikipedia extension:**

The same construction applies to any web artifact. HTML in the data
fork, CSS/images/JS as binary payloads in the resource fork, WIDTH/3
BINARY encoded. A receiver with a browser and the decode tools renders
a web page from a self-describing artifact with no network connection.

The Meridian Protocol made concrete: here is a web page that survived.
The artifact is the preservation unit.

**Status:** planned for the -01 tag ceremony. Depends on WIDTH/3
BINARY mode in `ucs_dec_tool.py` and `tools/git/gitbundle.py`.
Both are in-scope for the release.

---

## Deferred

Full fax page profile (alignment marks, Reed-Solomon) is far-horizon work.
The demo can run over clean fax or simulated degraded TCP/IP in the interim.
The CCL live demo (`demo/ccl_demo.sh`) is available now.
The point of the demo is the stack, not the channel.
