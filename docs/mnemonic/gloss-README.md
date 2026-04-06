# tools/mnemonic/gloss_twist.py — The Gloss Layer

*A philological gloss renders one text in the characters of another.
This layer glosses your input script into a key-derived Latin alphabet
before CCL runs.*

---

## The problem it solves

CCL prime-twist works by re-expressing token values in non-decimal bases.
Its feasibility rule is `base^WIDTH > token_value`. For a CJK token at
value 30,000 (WIDTH/5):

```
base 2: 2^5 =    32  ≤ 30,000  infeasible
base 3: 3^5 =   243  ≤ 30,000  infeasible
base 4: 4^5 = 1,024  ≤ 30,000  infeasible
base 5: 5^5 = 3,125  ≤ 30,000  infeasible
base 6: 6^5 = 7,776  ≤ 30,000  infeasible
base 7: 7^5 = 16,807 ≤ 30,000  infeasible
base 8: 8^5 = 32,768 > 30,000  feasible ✓
base 9: 9^5 = 59,049 > 30,000  feasible ✓
```

Only bases 8 and 9 are ever feasible. CCL twist rate is structurally
capped at ~22% per pass for CJK text. Three passes of CCL add little.

The same structural problem affects Arabic (01536–01791), Hangul
(44032–55203), Hebrew (01424–01535), Devanagari (02304–02431), and
Thai (03584–03711).

## The construction

The Gloss Layer re-encodes each token value in base 52 (A–Z a–z),
producing 3 output tokens per input token (52³ = 140,608 > 99,999).

The 52-letter alphabet is a **key-derived permutation**: it is shuffled
using SHA256 of the **reversed digit sequence** of the prime as the seed.
The reversed prime is a completely independent schedule from the forward
prime — 78% of digit positions differ — while requiring no additional
key material.

```
One verse  →  One prime P
             ├─ Forward digits of P   →  CCL key schedule
             └─ Reversed digits of P  →  Gloss alphabet permutation
```

Output code points are ASCII letters (65–122). At these values, CCL
bases 3–9 are **all feasible** on every token. CCL twist rate on the
glossed stream is no longer structurally capped.

## Entropy impact

Measured on representative texts, 3-pass CCL:

| Script | CCL3 alone | Gloss + CCL3 | Delta |
|--------|-----------|-------------|-------|
| English (poem) | **8.16** | 7.56 | −0.60 (CCL alone preferred) |
| Russian | 6.83 | **7.28** | +0.45 |
| Arabic | 6.40 | **7.05** | +0.65 |
| Hebrew | 6.40 | **7.02** | +0.62 |
| Hindi | 6.61 | **7.09** | +0.48 |
| Chinese | 5.93 | **7.29** | +1.36 |
| Japanese | 6.11 | **7.24** | +1.13 |
| Korean | 6.17 | **7.47** | +1.30 |

**Operational rule:**

- ASCII/Latin payloads: use CCL3 alone. Gloss adds 3× token expansion
  for no entropy gain.
- Arabic, CJK, Hangul, Hebrew, Devanagari, Thai, or any script with
  code points above U+0800: apply Gloss before CCL. The entropy gain
  is substantial (up to +1.36 bits/token for Chinese).

`prime_twist.py` will warn and prompt when it detects ≥30% non-ASCII
tokens. Use `--no-symbol-check` to suppress for known-ASCII pipelines.

## Usage

```bash
# Apply Gloss layer then CCL3 (recommended for Arabic/CJK/etc.)
cat arabic_payload.txt | \
    python tools/mnemonic/gloss_twist.py gloss --verse key.txt \
        --ref GLOSS1 | \
    python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt --no-symbol-check --ref CCL3 \
    > artifact.txt

# Reverse: CCL unstack, then Gloss ungloss
python tools/mnemonic/prime_twist.py unstack artifact.txt | \
    python tools/mnemonic/gloss_twist.py ungloss /dev/stdin | \
    python tools/ucs-dec/ucs_dec_tool.py --decode

# Inspect artifact parameters
python tools/mnemonic/gloss_twist.py info artifact.txt
```

## RSRC block

```
RSRC: BEGIN
  TYPE:         gloss-twist
  VERSION:      1
  NOTE:         TEST IMPLEMENTATION -- not normatively specified
  GLOSS-BASE:   52
  GLOSS-WIDTH:  3
  GLOSS-ALPHA:  kGeuwMzhjgCaSAsqntdcXxEoBlprYbWNKTQDRUvHLfPOIyFVimJZ
  PRIME:        11105665647563463056...
  INPUT-TOKENS: 534
  OUTPUT-TOKENS:1602
  FDS-WIDTH:    5
  GENERATED:    2026-04-06
RSRC: END
```

`GLOSS-ALPHA` is the permuted alphabet. The receiver reconstructs it
independently from the prime — the field is informational and serves as
a verification check.

## What a glossed token looks like

Input: `桜` (U+685C, value 26716)

```
26716 in base 52 = 9 × 52² + 48 × 52 + 44
                 = 9, 48, 44  (digit values)

Alphabet:  k G e u w M z h j g C a S A s q n t d c X x E o B l p r Y b W N K T Q D R U v H L f P O I y F V i m J Z
Index:     0 1 2 3 4 5 6 7 8 9 ...

digit 9  → alpha[9]  = g
digit 48 → alpha[48] = i
digit 44 → alpha[44] = y

26716 (桜) → "giy"
```

The output tokens `00103  00105  00121` (code points of `g`, `i`, `y`)
go into the CCL stream. At those values, all bases 3–9 are feasible.

## Naming

A **gloss** (philology) is a marginal note that renders a difficult word
in a text into a more familiar one — a scholar's annotation translating
obscure vocabulary into legible script. This layer does exactly that:
it glosses your input script into a key-derived Latin alphabet before
CCL runs, making the stream legible to CCL's feasibility rule.

## Companion tools

| Tool | Role |
|------|------|
| `tools/mnemonic/prime_twist.py` | CCL prime-twist (apply after Gloss) |
| `tools/mnemonic/mnemonic.py` | Prime derivation shared library |
| `tools/mnemonic/verse_to_prime.py` | Derive and record a prime from a verse |
| `tools/mnemonic/symbol_twist.py` | Alternative: symbolic camouflage layer |

## Compatibility

Python 2.7+ / 3.x. No external dependencies beyond `mnemonic.py`.
