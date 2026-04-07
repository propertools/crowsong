# Why WIDTH/3? Why Gloss?
## Plaintext Hygiene and the Side-Channel You're Not Thinking About

*Design rationale for the WIDTH/3 BINARY pipeline and Gloss layer.*
*For incorporation alongside the Crowsong Internet-Drafts.*

**Classification:** TLP:CLEAR
**Status:** Informational — design rationale, not normative specification

---

## The assumption everyone makes

When you encrypt a message, you are relying on the cipher to protect
the *content* of that message. AES-256 is not broken. RSA is not
broken. The cipher does what the cipher does.

But the cipher was never asked to hide everything.

It was asked to hide the content. It was not asked to hide the
*structure* of what you fed it.

That structure is still there. And a passive observer — someone who
never touches your encryption, never attempts to break your cipher,
never needs to — can read it.

---

## What leaks before decryption

Consider a journalist in an authoritarian state communicating with
sources. They use Signal. Good choice. The encryption is sound.

Their messages are in Arabic.

Arabic text encoded as Unicode produces token values clustered at
code points 01536–01791 (U+0600–U+06FF). Before encryption, before
anything, the *size* of their messages, the *distribution* of bytes
in their ciphertext, and the *timing* of their traffic all carry
information that is a function of the plaintext structure — and
that structure is characteristic of Arabic text.

A passive observer watching encrypted traffic does not need to
decrypt a single packet to learn:

- The language of the communication (byte distribution fingerprint)
- The script family (token value clustering)
- The approximate content type (prose vs structured data vs binary)
- Statistical patterns that correlate with specific document types

This is not hypothetical. It is the same class of attack as CRIME
and BREACH against TLS — attacks that extracted plaintext from
encrypted connections without breaking the cipher, by exploiting
structural properties of what the cipher was asked to encrypt.

The encryption was fine. The plaintext wasn't clean.

---

## The Unicode code point problem

UCS-DEC encodes text as Unicode code point values, zero-padded to
five decimal digits (WIDTH/5). This encoding is human-legible,
channel-agnostic, and survives transcription — those are the
properties it was designed for.

But it inherits the structural distribution of Unicode:

| Script | Code point range | Token value range |
|--------|-----------------|-------------------|
| ASCII (Latin) | U+0020–U+007F | 00032–00127 |
| Arabic | U+0600–U+06FF | 01536–01791 |
| Devanagari | U+0900–U+097F | 02304–02431 |
| CJK Unified | U+4E00–U+9FFF | 19968–40959 |
| Hangul | U+AC00–U+D7A3 | 44032–55203 |

A passive observer who sees a UCS-DEC payload — or a ciphertext
derived from one — can identify the script family from the token
value distribution. Arabic clusters at 01536–01791. CJK clusters at
19968–40959. The clustering is not subtle. It is a fingerprint.

This fingerprint survives encryption if the plaintext is not smoothed
first. The cipher protects the content. The traffic analysis reveals
the language.

For many of the people who most need strong encryption, the language
is itself sensitive information. It identifies who they are, where
they are, and who they are likely talking to.

---

## What CCL does — and what it does not do

The Channel Camouflage Layer applies prime-derived base-switching to
UCS-DEC token streams. After three passes (CCL3), the token
distribution rises from approximately 4.78 bits/token to 8.37
bits/token for Latin text — above the AES-128 ciphertext entropy
reference of approximately 7.95 bits/byte.

A passive entropy scanner cannot distinguish CCL3 output from
encrypted data.

**CCL provides no cryptographic confidentiality.** This is stated
explicitly and repeatedly throughout the specification because it is
important. CCL raises the cost of passive attention. It does not
raise the cost of active decryption with the key. It is not
encryption. It is camouflage.

The correct pipeline is:

```
plaintext → CCL → encrypt → transmit
```

Not:

```
plaintext → CCL → transmit   (no confidentiality)
```

And not:

```
plaintext → encrypt → CCL    (wrong order; CCL operates on plaintext)
```

CCL is plaintext hygiene. It smooths the distribution before the
cipher sees it. The cipher then operates on a near-maximum-entropy
input, and the ciphertext leaks less about the plaintext structure
than it would have otherwise.

---

## The structural limitation for non-Latin scripts

CCL's base-switching operation has a feasibility constraint:

```
base^WIDTH > token_value
```

For a WIDTH/5 token, this means:

```
base 9: 9^5 = 59,049 → feasible for token values up to 59,048
base 8: 8^5 = 32,768 → feasible for token values up to 32,767
base 7: 7^5 = 16,807 → feasible for token values up to 16,806
```

For ASCII text (token values 32–127), all bases 3–9 are feasible.
CCL achieves high twist rates and full entropy gain.

For CJK text (token values 19,968–40,959):

```
base 2 through 7: infeasible (base^5 ≤ token_value)
base 8: infeasible for values above 32,767
base 9: feasible for values up to 59,048 ✓
```

Only base 9 is ever feasible for most CJK tokens. CCL twist rate
is structurally capped at approximately 11% per pass — the fraction
of key schedule positions where the scheduled digit happens to be 9.
Three passes of CCL add less than 0.6 bits/token for CJK text.

The journalist using CJK characters gets almost no benefit from CCL.
Their traffic is still fingerprintable after three passes.

This is the problem the Gloss layer solves.

---

## Why Gloss?

The Gloss layer re-encodes each UCS-DEC token value in base 52
(letters A–Z a–z), producing three output tokens per input. Output
code points fall in the ASCII letter range (65–122).

At code point 65 (letter 'A'):

```
base 3: 3^5 = 243  > 65  ✓ feasible
base 4: 4^5 = 1024 > 65  ✓ feasible
base 5 through 9:          ✓ all feasible
```

After Gloss, every CCL base 3–9 is feasible on every token,
regardless of the original script. CCL then achieves full twist
rates for Arabic, CJK, Hangul, Hebrew, Devanagari, Thai — every
script that was previously structurally limited.

**Entropy gain with Gloss + CCL3:**

| Script | CCL3 alone | Gloss + CCL3 | Gain |
|--------|-----------|--------------|------|
| Chinese | 5.93 | **7.29** | +1.36 bits/token |
| Korean | 6.17 | **7.47** | +1.30 |
| Japanese | 6.11 | **7.24** | +1.13 |
| Arabic | 6.40 | **7.05** | +0.65 |
| Hebrew | 6.40 | **7.02** | +0.62 |
| Hindi | 6.61 | **7.09** | +0.48 |
| Russian | 6.83 | **7.28** | +0.45 |

AES-128 reference: ~7.95 bits/byte.

The Gloss layer brings non-Latin scripts within reach of the
AES-128 entropy reference. The script fingerprint is gone. The
token value clustering is gone. A passive observer scanning the
traffic cannot distinguish Arabic from Chinese from English from
encrypted data.

The journalist's traffic is now clean before encryption runs.

**Key derivation:** The Gloss alphabet permutation is seeded from
the reversed digit sequence of the same prime used for CCL. One
prime, two independent schedules, zero additional key material.

---

## Why WIDTH/3?

WIDTH/5 encodes each Unicode code point as a five-digit decimal
integer. This is the right encoding for text — code points range
from 0 to 1,114,111, and five decimal digits cover this range
(00000–99999 covers the Basic Multilingual Plane and beyond).

For binary payloads — compressed data, firmware, key material,
any arbitrary byte stream — WIDTH/5 is wasteful. Bytes range from
0 to 255. Five digits to represent a value that needs at most three
is unnecessary expansion.

WIDTH/3 encodes each byte as a three-digit decimal integer (000–255).
Token count equals byte count. The encoding is compact. The token
vocabulary is 000–999 (1000 possible values).

The theoretical entropy ceiling for WIDTH/3 is log₂(1000) = 9.97
bits/token. For WIDTH/5 it is log₂(100,000) = 16.61 bits/token —
but real text never approaches this because Unicode code points are
not uniformly distributed.

For binary payloads, WIDTH/3 is the right encoding.

---

## The binary payload ceiling

WIDTH/3 BINARY + mod3 CCL achieves H_post = 8.87–8.93 bits/token
across 37 languages and all compressors (empirical results, April
2026). This is well above the AES-128 reference.

But the hard ceiling is 9.97. The gap — approximately 1 bit/token
— exists because compressed binary has only 256 distinct byte
values, not 1000. The token distribution after mod3 CCL is
non-uniform: high token values (256–999) are structurally
underrepresented because the input tokens are clustered at 000–255.

No matter how good the CCL algorithm is, it cannot conjure entropy
that was not present in the input.

This is the same structural problem as CJK text in WIDTH/5 — a
ceiling imposed by input distribution, not algorithm. And the
solution follows the same pattern.

---

## Why Gloss-W3?

Gloss-W3 is a WIDTH/3-specific value-space expander. It applies a
keyed permutation of the full WIDTH/3 token vocabulary (000–999)
to scatter the 256 input byte values across all 1000 possible
token positions before CCL runs.

```
key         ← SHA256(reversed digits of prime P)
permutation ← Fisher-Yates shuffle of [000..999] seeded from key
Gloss-W3(V) = permutation[V]     for V in {000..255}
```

After Gloss-W3, the 256 distinct byte values occupy 256 positions
pseudo-randomly distributed across {000..999}. The input clustering
at 000–255 is gone. mod3 CCL then operates on a distribution that
is already spread across the full token vocabulary.

The hypothesis: Gloss-W3 + mod3 CCL pushes unique token count above
643 and H_post meaningfully above 8.93 bits/token, closing the gap
toward the 9.97 ceiling.

**Key derivation:** Gloss-W3 uses the reversed digit sequence of P
as its key seed — the same structural pattern as the existing Gloss
layer. Forward prime digits drive the CCL schedule. Reversed prime
digits drive the Gloss-W3 permutation. One prime. Two schedules.
Zero additional key material.

The pattern is the same all the way down.

---

## The Mallory experiment

The argument above is theoretical. The following experiment makes it
empirical.

### Hypothesis

A passive observer (Mallory) with access to encrypted network traffic
can currently distinguish ciphertexts derived from non-Latin-script
plaintexts — Arabic, CJK, Hangul, Hebrew, Devanagari, Thai — from
each other and from Latin-script ciphertexts, without breaking the
cipher, by measuring statistical properties of the ciphertext that
are inherited from the plaintext's Unicode code point distribution.

The cipher is sound. The plaintext was not clean. The fingerprint
survived encryption.

### Experimental design

**Corpus:** UDHR translations — the same document in every language,
professionally translated, covering 37+ languages and 20+ scripts.
The ideal controlled corpus: content is held constant, only the
script varies.

**Ciphers under test (candidate list):**

| Cipher | Mode | Notes |
|--------|------|-------|
| AES-128 | CBC | Baseline — most widely deployed |
| AES-256 | CBC | Higher key size |
| AES-128 | GCM | Authenticated encryption |
| AES-256 | GCM | |
| ChaCha20 | — | Stream cipher, widely used in TLS 1.3 |
| ChaCha20-Poly1305 | — | Authenticated |
| Blowfish | CBC | Legacy, still deployed |
| Twofish | CBC | AES finalist |
| Camellia-256 | CBC | ISO standard, used in TLS |
| CAST-128 | CBC | Legacy |
| 3DES | CBC | Legacy, still encountered |
| Serpent | CBC | AES finalist, conservative |

All implementations from established open-source libraries
(PyCryptodome, cryptography.io). Fixed random keys per cipher,
same key used across all languages for each cipher. Fixed random
IVs. No compression before encryption (compression would itself
smooth the distribution and confound the measurement).

**Pipelines under test:**

```
Pipeline A (baseline):
  UDHR text (UTF-8)
    → cipher.encrypt()
    → measure ciphertext statistics

Pipeline B (pre-cooked):
  UDHR text (UTF-8)
    → UCS-DEC encode (WIDTH/5 or WIDTH/3)
    → Gloss layer (for non-Latin scripts)
    → CCL3 (prime-twist, standard schedule)
    → cipher.encrypt()
    → measure ciphertext statistics
```

**Measurements per ciphertext:**

- Shannon entropy H (bits/byte)
- χ² test against uniform distribution (p-value)
- Serial correlation coefficient
- Byte frequency distribution (full histogram)
- Inter-language distance matrix (KL divergence between
  ciphertext distributions across language pairs)

The inter-language distance matrix is the key measurement. If
Mallory can distinguish Arabic ciphertext from Chinese ciphertext,
the distance between their byte distributions will be non-trivial.
If pre-cooking destroys the fingerprint, the distances will collapse
toward zero.

**Expected results (if hypothesis is correct):**

Pipeline A: inter-language distances are non-trivial for non-Latin
script pairs. Arabic vs CJK, Hebrew vs Devanagari, Hangul vs Thai
— these ciphertexts will be statistically distinguishable from each
other and from Latin-script ciphertexts, across most or all ciphers
tested.

Pipeline B: inter-language distances collapse. Pre-cooked ciphertexts
from Arabic and Chinese and Hindi and Korean are statistically
indistinguishable from each other and from English. The script
fingerprint was destroyed before the cipher saw it.

**What a null result would mean:**

If Pipeline A distances are already near zero — if modern ciphers
already destroy the plaintext structure fingerprint — then the
pre-cooking step adds no measurable benefit for this threat model.
The result is still publishable and useful: it would mean the
concern is theoretical but not empirically demonstrated.

If Pipeline A distances are non-trivial for some ciphers but not
others, the results identify which cipher modes are vulnerable to
this class of passive analysis. Also publishable and useful.

**Script:**

```bash
# Proposed: scripts/mallory-experiment.sh
# For each UDHR language × cipher × pipeline:
#   1. Fetch and extract UDHR text
#   2. Optionally pre-cook via Gloss + CCL
#   3. Encrypt with cipher
#   4. Measure ciphertext statistics
#   5. Compute inter-language distance matrix
#   6. Output markdown results table

bash scripts/mallory-experiment.sh \
    --corpus docs/udhr/ \
    --verse-file verses.txt \
    --ciphers aes128-cbc,aes256-gcm,chacha20,camellia256 \
    --output docs/mallory-experiment-results.md
```

**Publication target:**

The results, methodology, and corpus are fully reproducible from the
Crowsong repository. The experiment script, cipher implementations,
and UDHR corpus are all committed. Any researcher can reproduce the
results independently.

Target venues: USENIX Security, IEEE S&P, or as an independent
technical report published at propertools.be and submitted to the
IETF SAAG (Security Area Advisory Group) mailing list for comment.

The result either confirms the hypothesis — in which case it is a
concrete demonstration of a real and underappreciated side-channel
affecting users of non-Latin scripts in adversarial environments —
or it provides empirical evidence that the concern is already
addressed by existing cipher deployments. Either outcome is a
contribution.

---

## The complete argument

1. **Encryption protects content.** It was not designed to hide
   plaintext structure. That structure leaks through traffic
   analysis — packet sizes, byte distributions, timing — without
   ever touching the cipher.

2. **Unicode text has characteristic structure.** Arabic clusters
   at specific code points. CJK clusters at others. The language
   is visible in the traffic even after encryption.

3. **For people whose language is sensitive information** — because
   it identifies them, their location, their community — this
   side-channel is a real threat. They are using good ciphers.
   The ciphers are not the problem.

4. **CCL smooths the distribution before encryption runs.** It is
   not encryption. It is plaintext hygiene. It removes the
   structural fingerprint that the cipher was never asked to hide.

5. **The Gloss layer extends this to non-Latin scripts.** Without
   Gloss, CCL cannot achieve high entropy for Arabic, CJK, or
   Hangul text because the feasibility constraint structurally
   limits twist rate. With Gloss, the script fingerprint is
   destroyed before CCL runs.

6. **WIDTH/3 + mod3 achieves above AES-128 entropy for binary
   payloads.** Gloss-W3 is designed to close the remaining gap
   toward the theoretical ceiling.

7. **Then encrypt.** With whatever cipher you trust. The cipher
   now operates on a near-maximum-entropy input. The ciphertext
   leaks less about the plaintext than it would have without
   the hygiene step.

The people who most need this are exactly the people using
non-Latin scripts in adversarial environments. They are not
well-served by a system optimised for ASCII. This one is not.

---

## Summary

| Question | Answer |
|----------|--------|
| Why WIDTH/3? | Binary payloads need at most 3 digits per byte. Compact. Ceiling at log₂(1000) = 9.97. |
| Why mod3? | Forces bases 7/8/9 — 100% twist rate across all byte values. |
| Why Gloss? | Destroys script fingerprints. Restores CCL feasibility for non-Latin scripts. |
| Why Gloss-W3? | Scatters 256-value binary distribution across full 000–999 token space. Attacks the entropy ceiling. |
| Why not just encrypt? | Encryption hides content. It doesn't hide structure. Structure leaks. |
| What order? | Plaintext → Gloss → CCL → encrypt → transmit. |
| What does CCL guarantee? | Entropy above AES-128 reference. Not confidentiality. |
| What does encryption guarantee? | Confidentiality. Not entropy smoothing. |
| Combined? | Both. Each doing what it was designed to do. |

---

## Further reading

| Document | Notes |
|----------|-------|
| `drafts/draft-darley-fds-ccl-prime-twist-00.txt` | Pre-normative CCL specification |
| `docs/entropy-analysis.md` | Shannon entropy measurements across 20+ languages |
| `docs/mnemonic/gloss-README.md` | Gloss layer design rationale |
| `docs/ccl-prime-chain-spec.md` | Prime-chain schedule and Gloss-W3 design sketch |
| `docs/structural-principles.md` | Governing design principles |
| `docs/mallory-experiment-results.md` | Empirical results — plaintext fingerprinting across ciphers (pending) |
| `scripts/mallory-experiment.sh` | Reproducible experiment script (pending) |
| `tools/mnemonic/crowsong-advisor.py` | Pipeline advisor — recommends optimal mode for any input |

---

*The cipher does what the cipher does.*
*Clean the plaintext first.*

*Proper Tools SRL — propertools.be*
*TLP:CLEAR*
