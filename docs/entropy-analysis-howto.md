# Reproducing the Crowsong Entropy Analysis

*A complete guide for a new contributor to rerun the 20-language entropy
analysis from scratch, understand the results, and extend the corpus.*

---

## What this document covers

The Crowsong entropy analysis measures how effectively the CCL prime-twist
pipeline raises the Shannon entropy of UCS-DEC token streams across 20
languages and scripts. It quantifies:

- The entropy floor and ceiling for CCL3 alone (no pre-processing)
- Which scripts benefit from the Gloss layer and by how much
- Which modes exceed the AES-128 ciphertext entropy reference (~7.95 bits/byte)

The full results are in `docs/entropy-analysis.md`. This document explains
how to reproduce them, extend them to new languages, and interpret the
output of the tooling.

---

## Prerequisites

```bash
# Clone the repository
git clone https://github.com/propertools/crowsong
cd crowsong

# Python 2.7+ or 3.x, no external dependencies
python3 --version

# Verify the test suite passes
bash tests/roundtrip/run_tests.sh
# Expected: 8 passed, 0 failed
```

---

## Step 1 — Fetch the UDHR corpus

The UDHR (Universal Declaration of Human Rights) is the ideal entropy
analysis corpus: the same document in every language, professionally
translated, covering every major Unicode script, and available as clean
plain UTF-8 text from the Unicode Consortium.

```bash
# See available languages (50 languages, 25 scripts)
python tools/udhr/udhr.py list

# Filter by script
python tools/udhr/udhr.py list --script Arabic
python tools/udhr/udhr.py list --script CJK
python tools/udhr/udhr.py list --script Devanagari

# Fetch the 20 languages used in the original analysis
python tools/udhr/udhr.py fetch \
    eng fra deu spa         \  # Latin
    rus ukr bul             \  # Cyrillic
    ara fas heb             \  # Semitic
    hin ben tam             \  # Indic
    zho jpn kor             \  # CJK / Hangul
    tha kat amh ell            # Thai / Georgian / Ethiopic / Greek

# Or fetch everything (50 languages, ~5 minutes with polite delays)
python tools/udhr/udhr.py fetch --all

# Verify SHA256 of all cached files
python tools/udhr/udhr.py verify
# Expected: N passed, 0 failed
```

Files are cached in `docs/udhr/` as self-describing plain UTF-8 with
SHA256 headers, using the same format as `docs/texts/`.

---

## Step 2 — Prepare your key verses

The entropy measurements use three verse-derived primes as CCL keys.
The published results used these canonical verses:

```
K1: Factoring primes in the hot sun, I fought Entropy — and Entropy won.
K2: Every sequence slips. Every clock will lie.
K3: The signal strains, but never gone — I fought Entropy, and I forged on.
```

Create `verses.txt` with one verse per line:

```bash
cat > verses.txt << 'EOF'
Factoring primes in the hot sun, I fought Entropy — and Entropy won.
Every sequence slips. Every clock will lie.
The signal strains, but never gone — I fought Entropy, and I forged on.
EOF
```

Or derive your own primes from any memorable verses:

```bash
echo "Your verse here." | python tools/mnemonic/verse_to_prime.py derive
```

---

## Step 3 — Encode a UDHR text as UCS-DEC

Each UDHR text must be encoded as a UCS-DEC token stream before the
pipeline can process it.

```bash
# Encode Arabic UDHR
python tools/ucs-dec/ucs_dec_tool.py --encode \
    < docs/udhr/ara.txt \
    > /tmp/ara_tokens.txt

# Check the token count and first few tokens
wc -w /tmp/ara_tokens.txt
head -c 200 /tmp/ara_tokens.txt
```

The token stream is whitespace-separated five-digit decimal integers,
one per Unicode code point. Arabic text will produce tokens in the
range `01536`–`01791`.

---

## Step 4 — Analyse the input

The advisor tool analyses the raw token stream and explains what it
contains before any CCL is applied:

```bash
python tools/mnemonic/crowsong-advisor.py --analyse \
    < /tmp/ara_tokens.txt
```

Expected output for Arabic:

```
  Script:  HIGH (100% non-ASCII, dominant: Arabic / Farsi)

  CCL feasibility profile  (WIDTH/5)
    base 2:    0.0%  ← low — fallback to base 10 dominates
    base 3:    0.0%  ← low — fallback to base 10 dominates
    ...
    base 9:  100.0%  ← excellent

  ⚠ Most bases infeasible: high-codepoint script detected.
    Apply Gloss layer before CCL for best entropy.
```

This is the structural problem the Gloss layer solves: Arabic token values
(01536–01791) exceed `base^5` for all bases except 9. CCL can only
use one base for the entire stream.

---

## Step 5 — Get pipeline recommendations

```bash
python tools/mnemonic/crowsong-advisor.py \
    --verse-file verses.txt \
    < /tmp/ara_tokens.txt
```

The advisor evaluates all available pipeline modes and ranks them by
predicted output entropy:

```
  Rank  Mode                            H₃ (CCL3)      ±σ  Tokens   ×exp
     1  Gloss + CCL3                     7.0458  0.0723    639     3×  ★★☆
     2  CCL3 (standard schedule)         7.0556  0.0576    213     1×  ★★☆
     3  Gloss + CCL3 (mod3)              6.5xxx  ...
     4  CCL3 (mod3 schedule)             ...
     5  Symbol (deepcut-v1) + CCL3       ...
```

And provides copy-paste bash pipelines for each mode.

---

## Step 6 — Run the full pipeline

Using the top recommended mode:

```bash
# Gloss + CCL3 for Arabic
cat docs/udhr/ara.txt | \
    python tools/ucs-dec/ucs_dec_tool.py --encode | \
    python tools/mnemonic/gloss_twist.py gloss \
        --verse "$(head -1 verses.txt)" --ref GLOSS | \
    python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt --no-symbol-check --ref CCL3 \
    > /tmp/ara_artifact.txt

# Inspect the artifact
python tools/mnemonic/prime_twist.py info /tmp/ara_artifact.txt

# Recover (Gloss + CCL pipeline reversal)
python tools/mnemonic/prime_twist.py unstack /tmp/ara_artifact.txt | \
    python tools/mnemonic/gloss_twist.py ungloss /dev/stdin | \
    python tools/ucs-dec/ucs_dec_tool.py --decode | \
    head -3
```

---

## Step 7 — Batch analysis across all UDHR languages

```bash
# Quick entropy summary across all cached UDHR texts
python tools/udhr/udhr.py analyse --all
```

This prints a table of H₀ (pre-transform entropy) and script risk
for every cached language. Pipe to the advisor for full pipeline
recommendations on any row.

For the full multi-language entropy comparison used in
`docs/entropy-analysis.md`:

```bash
# Run advisor on each language and collect results
for lang in eng fra deu spa rus ara fas heb hin ben zho jpn kor tha kat amh ell; do
    echo "=== $lang ==="
    python tools/ucs-dec/ucs_dec_tool.py --encode \
        < docs/udhr/${lang}.txt | \
    python tools/mnemonic/crowsong-advisor.py \
        --verse-file verses.txt --quiet
    echo ""
done
```

---

## Understanding the results

### Why English scores highest (CCL3 alone ~8.16 bits/token)

ASCII token values (32–126) satisfy `base^5 > value` for all bases
3–9. CCL can apply any scheduled base at any position. Twist rate on
pass 1 is ~76%. Three passes compound the entropy gain.

### Why Chinese scores lowest without the Gloss layer (~6.19 bits/token)

CJK token values (19,968–40,959) satisfy `base^5 > value` only for
bases 8 and 9. CCL twist rate is structurally capped at ~22% per pass
(positions where the key digit happens to be 8 or 9). Three passes
of CCL add very little.

### Why the Gloss layer helps CJK (+1.36 bits/token)

The Gloss layer re-encodes each token value in base 52 (A–Z a–z),
producing 3 output tokens per input. The output code points are ASCII
letters (65–122). At these values, CCL bases 3–9 are ALL feasible.
CCL then achieves high twist rates and full entropy gain.

### The AES-128 reference

~7.95 bits/byte is the approximate Shannon entropy of AES-128 ciphertext.
A passive observer cannot distinguish payload entropy above this threshold
from encrypted data on entropy alone. CCL3 exceeds this reference for
Latin scripts. Gloss+CCL3 approaches it for CJK and Semitic scripts.

### Standard error (±σ)

The ±σ values are standard errors on the entropy estimate:
√(Σ pᵢ·(log₂pᵢ)² − H²) / √n. They reflect token count, not model
uncertainty. For n ≥ 300, ±σ < 0.06 bits/token in all scripts. Short
samples (< 100 tokens) have ±σ > 0.05 and results should be treated
as indicative only.

---

## Extending the analysis

### Adding a new language to the UDHR corpus

```bash
# Check if the language is in the registry
python tools/udhr/udhr.py list | grep -i swahili

# If not, add it to UDHR dict in tools/udhr/udhr.py:
# Find the correct code at https://www.unicode.org/udhr/d/
# (browse the directory for udhr_XXX.txt files)

python tools/udhr/udhr.py fetch swa
python tools/udhr/udhr.py verify swa
```

### Adding a language to the entropy analysis table

Once cached, run the full advisor pipeline and add the results to
`docs/entropy-analysis.md`. The table format is:

```markdown
| N | Language | Script | Tokens | Risk | H₀ | H₁ | H₂ | H₃ | ±σ |
```

where H₀–H₃ are entropy at each CCL pass and ±σ is the standard error
on H₃.

### Using the Gutenberg corpus instead

The Gutenberg canonical text corpus (`docs/texts/`, `tools/texts/texts.py`)
provides longer samples in fewer languages. For scripts where the UDHR
is short (< 200 tokens after encoding), the Gutenberg text may give a
more stable entropy estimate. Use whichever gives n ≥ 300 tokens.

```bash
# Check token count for a Gutenberg text
python tools/ucs-dec/ucs_dec_tool.py --encode \
    < docs/texts/rumi-masnavi.txt | wc -w

# Run advisor on it
python tools/ucs-dec/ucs_dec_tool.py --encode \
    < docs/texts/rumi-masnavi.txt | \
    python tools/mnemonic/crowsong-advisor.py --verse-file verses.txt
```

---

## Tool reference

| Tool | Purpose |
|------|---------|
| `tools/udhr/udhr.py` | Fetch, verify, and analyse UDHR multilingual corpus |
| `tools/texts/texts.py` | Fetch, verify, and serve Gutenberg canonical texts |
| `tools/ucs-dec/ucs_dec_tool.py` | Encode/decode UCS-DEC (FDS) |
| `tools/mnemonic/crowsong-advisor.py` | Pipeline recommendations and analysis |
| `tools/mnemonic/prime_twist.py` | CCL prime-twist (apply after Gloss) |
| `tools/mnemonic/gloss_twist.py` | Gloss layer for non-Latin scripts |
| `tools/mnemonic/symbol_twist.py` | Symbol camouflage layer |
| `tools/mnemonic/verse_to_prime.py` | Derive a prime from a key verse |

---

## Quick reference: one-line pipeline per script family

```bash
# Latin / ASCII (CCL3 alone is optimal)
cat docs/udhr/eng.txt | ucs_dec_tool.py -e | \
    prime_twist.py stack --verse-file verses.txt

# Arabic / Hebrew / Farsi (Gloss + CCL3)
cat docs/udhr/ara.txt | ucs_dec_tool.py -e | \
    gloss_twist.py gloss --verse "$(head -1 verses.txt)" | \
    prime_twist.py stack --verse-file verses.txt --no-symbol-check

# CJK / Hangul / Japanese (Gloss + CCL3, largest gain)
cat docs/udhr/zho.txt | ucs_dec_tool.py -e | \
    gloss_twist.py gloss --verse "$(head -1 verses.txt)" | \
    prime_twist.py stack --verse-file verses.txt --no-symbol-check

# Thai / Devanagari / Bengali (Gloss + CCL3)
cat docs/udhr/tha.txt | ucs_dec_tool.py -e | \
    gloss_twist.py gloss --verse "$(head -1 verses.txt)" | \
    prime_twist.py stack --verse-file verses.txt --no-symbol-check

# Unknown script — let the advisor decide
cat your_payload.txt | ucs_dec_tool.py -e | \
    crowsong-advisor.py --verse-file verses.txt
```

---

*Generated: 2026-04-06*
*Tools: tools/udhr/udhr.py, tools/mnemonic/crowsong-advisor.py*
*Results: docs/entropy-analysis.md*
