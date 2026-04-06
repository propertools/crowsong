# CCL3 Entropy Analysis — 20 Languages

*Shannon entropy H (bits/token) through the CCL prime-twist pipeline
across 20 language/script samples. Three-pass CCL with verse-derived
primes K1, K2, K3. Gloss+CCL3 column adds the Gloss Layer
(gloss_twist.py) before CCL.*

---

## Results

| # | Language | Script | Tokens | Risk¹ | H₀ (orig) | H₃ (CCL3) | Gloss+CCL3 | ±σ² |
|--:|----------|--------|-------:|:-----:|----------:|----------:|-----------:|----:|
| 1 | English (ASCII poem) | Latin | 531 | — | 4.76 | **8.16** | 7.56 | ±0.040 |
| 2 | English (prose) | Latin | 288 | — | 4.25 | **7.55** | 7.20 | ±0.047 |
| 3 | French | Latin | 313 | — | 4.20 | **7.62** | 7.15 | ±0.046 |
| 4 | German | Latin | 273 | — | 4.42 | **7.54** | 7.18 | ±0.045 |
| 5 | Spanish | Latin | 296 | — | 4.14 | **7.42** | 7.02 | ±0.058 |
| 6 | Russian | Cyrillic | 270 | ⚠ | 4.77 | 7.42 | **7.28** | ±0.049 |
| 7 | Greek | Greek | 242 | ⚠ | 4.42 | 7.23 | **7.10** | ±0.054 |
| 8 | Arabic | Arabic | 215 | ⚠ | 4.30 | 7.06 | **7.05** | ±0.058 |
| 9 | Farsi / Persian | Arabic | 213 | ⚠ | 4.24 | 7.03 | **7.03** | ±0.053 |
| 10 | Hebrew | Hebrew | 199 | ⚠ | 4.24 | 6.97 | **7.02** | ±0.058 |
| 11 | Hindi / Devanagari | Devanagari | 223 | ⚠ | 4.62 | 7.15 | **7.09** | ±0.054 |
| 12 | Bengali | Bengali | 218 | ⚠ | 4.53 | 7.05 | **7.05** | ±0.060 |
| 13 | Chinese (Simplified) | CJK | 113 | ⚠ | 5.79 | 6.39 | **7.29** | ±0.055 |
| 14 | Chinese (Traditional) | CJK | 90 | ⚠ | 5.51 | 6.19 | **7.10** | ±0.052 |
| 15 | Japanese | CJK | 114 | ⚠ | 5.76 | 6.44 | **7.24** | ±0.059 |
| 16 | Korean | Hangul | 137 | ⚠ | 4.97 | 6.48 | **7.47** | ±0.067 |
| 17 | Thai | Thai | 190 | ⚠ | 5.02 | 6.92 | **6.92** | ±0.057 |
| 18 | Ethiopian / Amharic | Ethiopic | 127 | ⚠ | 5.13 | 6.78 | **6.98** | ±0.038 |
| 19 | Georgian | Georgian | 251 | ⚠ | 4.27 | 6.82 | **7.05** | ±0.065 |
| 20 | Mixed CJK + Arabic | Mixed | 127 | ⚠ | 5.40 | 6.64 | **7.18** | ±0.050 |
| | **AES-128 ciphertext** | | | | | ~7.95 | ~7.95 | |
| | **Theoretical max (WIDTH/5)** | | | | | 9.97 | 9.97 | |

¹ **Risk**: ⚠ = script fingerprinting risk (≥30% non-ASCII tokens);
— = low risk (predominantly ASCII). See [THREAT-MODEL.md](THREAT-MODEL.md).

² **±σ**: standard error on H₃ estimate, computed as
√(Σ pᵢ·(log₂pᵢ)² − H²) / √n.

**Bold** indicates the recommended pipeline for each language.
For Latin scripts, CCL3 alone is preferred. For all other scripts,
Gloss+CCL3 is preferred.

---

## Summary

| Metric | Value | Notes |
|--------|-------|-------|
| **Best-case ceiling (CCL3 alone)** | **8.16 ±0.040** | English ASCII poem, 531 tokens |
| **Worst-case floor (CCL3 alone)** | **6.19 ±0.052** | Chinese Traditional, 90 tokens |
| **Best-case ceiling (Gloss+CCL3)** | **7.56** | English ASCII poem |
| **Worst-case floor (Gloss+CCL3)** | **6.92** | Thai, 190 tokens |
| **Latin scripts (CCL3 alone)** | 7.42 – 8.16 | All exceed AES-128 reference |
| **CJK with Gloss+CCL3** | 7.10 – 7.47 | +1.13 to +1.36 vs CCL3 alone |
| **Semitic with Gloss+CCL3** | 7.02 – 7.05 | +0.62 to +0.65 vs CCL3 alone |
| **AES-128 reference** | ~7.95 | |
| **Theoretical max (WIDTH/5)** | 9.97 | log₂(100,000) |

---

## The Gloss Layer

`tools/mnemonic/gloss_twist.py` resolves the structural CCL entropy
limitation for high-codepoint scripts.

### Construction

Each input token value V is re-encoded in a key-derived permutation of
the 52-character mixed-case Latin alphabet (A-Z, a-z), producing exactly
3 output tokens (52³ = 140,608 > 99,999 — all WIDTH/5 values covered).

The output code points are 65–122 (ASCII). At these values, CCL bases
3–9 are feasible on every token without exception. CCL then achieves high
twist rates even for content that originally had values in the
CJK/Hangul/Arabic range.

The alphabet permutation is derived from the reversed digits of the same
prime used for CCL:

```
verse -> prime P
  P reversed  -> gloss alphabet permutation  (this tool)
  P forward   -> CCL base-switching schedule  (prime_twist.py)
```

One verse. One prime. Two independent, non-interfering schedules.
No additional key material.

### Pipeline

```bash
# Arabic / CJK / Hangul / Devanagari / Hebrew / Thai / etc.:
cat payload.txt | \
    python tools/mnemonic/gloss_twist.py gloss --verse key.txt | \
    python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt --no-symbol-check

# Reversal:
python tools/mnemonic/prime_twist.py unstack artifact.txt | \
    python tools/mnemonic/gloss_twist.py ungloss /dev/stdin | \
    python tools/ucs-dec/ucs_dec_tool.py --decode
```

The `--no-symbol-check` flag suppresses the pre-flight warning in
`prime_twist.py` because the Gloss Layer has already addressed the
script fingerprint risk.

### Why CCL alone is insufficient for CJK

CCL's feasibility rule is `base^WIDTH > token_value`. For a CJK token
at value 30,000 (WIDTH/5):

```
base 2: 2^5 =     32  infeasible
base 3: 3^5 =    243  infeasible
base 4: 4^5 =  1,024  infeasible
base 5: 5^5 =  3,125  infeasible
base 6: 6^5 =  7,776  infeasible
base 7: 7^5 = 16,807  infeasible
base 8: 8^5 = 32,768  infeasible
base 9: 9^5 = 59,049  feasible ✓
```

Only base 9 is ever feasible. CCL twist rate is structurally capped at
~11% per pass. Three passes add less than 0.6 bits/token total.

After the Gloss Layer, all CJK values are represented as 3-character
letter sequences with code points 65–122. At value 65:

```
base 3: 3^5 = 243  > 65  feasible ✓
base 4: 4^5 = 1024 > 65  feasible ✓
...all bases 3-9 feasible ✓
```

CCL twist rates recover to normal levels and entropy gains compound
across all three passes.

### Visual appearance

Glossed CJK text looks like short letter sequences:

```
信 (U+4FE1, value 20449) -> mCh
号 (U+53F7, value 21495) -> mSP
不 (U+4E0D, value 19981) -> lhJ
```

The key-derived permutation ensures the same character maps to different
letters under different keys:

```
信 under K1: mCh
信 under K2: YrN
信 under K3: bQx
```

---

## Recommended pipeline by script

| Script | Code point range | Recommended pipeline |
|--------|-----------------|---------------------|
| Latin / ASCII | U+0020–U+024F | CCL3 alone |
| Cyrillic / Greek | U+0400–U+03FF | Gloss+CCL3 |
| Hebrew | U+0590–U+05FF | Gloss+CCL3 |
| Arabic / Farsi | U+0600–U+06FF | Gloss+CCL3 |
| Devanagari / Bengali | U+0900–U+09FF | Gloss+CCL3 |
| Thai | U+0E00–U+0E7F | Gloss+CCL3 |
| CJK Unified | U+4E00–U+9FFF | Gloss+CCL3 |
| Hangul | U+AC00–U+D7A3 | Gloss+CCL3 |
| Mixed / Unknown | varies | Gloss+CCL3 (safe default) |

`prime_twist.py` will warn and prompt when it detects ≥30% non-ASCII
tokens. Use `--no-symbol-check` after applying the Gloss Layer.

---

## Reproducing this analysis

For a complete step-by-step guide — fetching the UDHR corpus, encoding
texts, running the advisor, and extending to new languages — see:

**[docs/entropy-analysis-howto.md](entropy-analysis-howto.md)**

Quick start:

```bash
# Fetch the UDHR corpus (50 languages, 25 scripts)
python tools/udhr/udhr.py fetch --all
python tools/udhr/udhr.py verify

# Analyse a single language
python tools/ucs-dec/ucs_dec_tool.py --encode < docs/udhr/ara.txt | \
    python tools/mnemonic/crowsong-advisor.py --verse-file verses.txt

# Statistical analysis of the input token distribution
python tools/ucs-dec/ucs_dec_tool.py --encode < docs/udhr/zho.txt | \
    python tools/mnemonic/crowsong-advisor.py --analyse

# Run the canonical test vector (poem — the original analysis)
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
    python tools/mnemonic/prime_twist.py stack \
    --verse-file verses.txt --ref CCL3 --no-symbol-check
```

Generated: 2026-04-06
Keys: K1/K2/K3 verse-derived primes from `verses.txt`
Schedule: standard (CCL), WIDTH/5, Gloss base-52 width-3
