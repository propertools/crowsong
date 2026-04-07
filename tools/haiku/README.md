# tools/haiku/ — The Haiku Machine

Prime-driven haiku generation and word-space camouflage.
Arbitrary data encoded as eerily plausible AI-style English nature poetry.

**Dedicated to Felix 'FX' Lindner (1975–2026).**
*The signal strains, but never gone.*

---

## What this is

The haiku machine encodes arbitrary data as English words structured
as 5-7-5 haiku stanzas. The output looks like the kind of mediocre
AI-generated nature poetry that was everywhere in 2022-2024 — the
kind you scroll past without a second thought.

That is the point.

Two modes:

**Grammar mode** (`grammar-encode-stream`) — grammatically coherent,
thematically plausible, eerily convincing. Uses POS templates and
semantic fields to produce output that reads like a human prompt to
GPT-3: correct grammar, seasonal imagery, slightly over-earnest,
not quite right in the way AI poetry is not quite right.

**Raw mode** (`encode-stream`) — syllable-correct word selection
from the keyed corpus permutation. Faster, simpler, no POS data
required. Output reads as word-salad haiku — correct syllable counts,
no grammatical coherence. Useful for testing and for cases where
plausibility is not required.

Both modes are fully deterministic and reversible given the seed verse.

---

## The construction

```
verse → prime P
  forward digits  → template selection (grammar mode)
                  → syllable count schedule (raw mode)
  reversed digits → semantic field selection (grammar mode)
                  → word selection within bin (raw mode)
```

One verse. One prime. Two schedules. Zero additional key material.
The same structural pattern as the Gloss layer, applied to word-space.

---

## Files

```
tools/haiku/
    haiku_twist.py      prime-driven haiku generator + stream encoder
    haiku_grammar.py    POS-indexed bins + template engine
    templates.json      48 POS templates (haiku-templates-v1)
    fields.json         28 semantic fields (haiku-fields-v1)
    README.md           this file
```

---

## Quick start

```bash
# Step 1: build syllable bins
python tools/cmudict/cmudict.py fetch
python tools/cmudict/cmudict.py export

# Step 2: filter bins to common vocabulary (recommended)
python tools/wordfreq/wordfreq.py fetch --source coca
python tools/wordfreq/wordfreq.py filter \
    --bins docs/cmudict/bins.json \
    --output docs/cmudict/bins-common.json

# Step 3: build POS index (grammar mode only)
python tools/wordfreq/wordfreq.py export-pos
# → docs/wordfreq/pos-index.json

# Step 4: generate a test haiku (raw mode)
echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
    python tools/haiku/haiku_twist.py \
        --bins docs/cmudict/bins-common.json generate

# Step 5: encode arbitrary text as grammar-mode haiku
cat archive/second-law-blues.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/haiku/haiku_twist.py \
        --bins docs/cmudict/bins-common.json \
        grammar-encode-stream --verse verses.txt \
    > archive/second-law-blues-haiku.txt

# Step 6: decode it back
python tools/haiku/haiku_twist.py \
    --bins docs/cmudict/bins-common.json \
    grammar-decode-stream archive/second-law-blues-haiku.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --decode
```

---

## haiku_twist.py — subcommand reference

```bash
python haiku_twist.py [--bins FILE] <subcommand> [options]
```

`--bins` must precede the subcommand. Default: `docs/cmudict/bins.json`

### Haiku generation

```bash
# Generate from verse on stdin
echo "verse" | python haiku_twist.py --bins FILE generate [--ref ID]

# Ouroboros chain: each haiku seeds the next
echo "verse" | python haiku_twist.py --bins FILE chain [--steps N] [--output FILE]

# Verify a haiku artifact
python haiku_twist.py --bins FILE verify <artifact>

# Print just the haiku text
python haiku_twist.py decode <artifact>
```

### Raw word-space encoding

```bash
# Encode token stream as syllable-correct haiku words
<tokens> | python haiku_twist.py --bins FILE \
    encode-stream [--prime P | --verse FILE] [--ref ID]

# Decode back to token stream
python haiku_twist.py --bins FILE decode-stream <artifact>
```

### Grammar mode (eerily plausible AI nature poetry)

```bash
# Encode token stream as grammatically coherent AI-style haiku
<tokens> | python haiku_twist.py --bins FILE \
    grammar-encode-stream [--prime P | --verse FILE] [--ref ID] \
    [--templates FILE] [--fields FILE] [--pos FILE]

# Decode back to token stream
python haiku_twist.py --bins FILE \
    grammar-decode-stream <artifact> \
    [--templates FILE] [--fields FILE] [--pos FILE]
```

Grammar mode degrades gracefully: if `haiku_grammar.py` is not found,
a clear error is shown. If the POS index is not found, heuristic POS
assignment is used with a warning.

---

## haiku_grammar.py — standalone inspection

```bash
# Corpus and library summary
python haiku_grammar.py info

# POS-indexed bin summary
python haiku_grammar.py pos-bins
python haiku_grammar.py pos-bins --pos-tag VBG   # gerunds only

# Generate a sample haiku
python haiku_grammar.py generate \
    --verse "Factoring primes in the hot sun, I fought Entropy — and Entropy won."

# Generate 5 haiku
python haiku_grammar.py generate \
    --verse "Every sequence slips. Every clock will lie." \
    --count 5

# Template library analysis
python haiku_grammar.py analyse
```

---

## The template library (haiku-templates-v1)

48 POS templates covering the main English haiku surface structures,
drawn from classical haiku analysis and 2022-2024 AI haiku observation.

Selected templates and their `ai_likelihood` ratings:

| ID | Name | ai_likelihood |
|----|------|---------------|
| T001 | imagist-classic | very high |
| T002 | gerund-opening | very high |
| T006 | prepositional-meditation | very high |
| T009 | negation-structure | very high |
| T011 | colour-noun-verb | very high |
| T017 | nothing-and-everything | very high |
| T031 | the-interior-weather | very high |
| T033 | existential-pivot | very high |
| T042 | the-reader-addressed | very high |
| T047 | the-self-aware | very high |
| T003 | the-noun-stack | high |
| T007 | past-participle-opener | high |
| T034 | the-verb-of-light | very high |
| T048 | the-kigo-pivot-modern | high |

Template selection is driven by forward digits of the prime.
Reversal requires the same template library — versioned as `v1`.

---

## The semantic fields (haiku-fields-v1)

28 semantic fields with POS-categorised vocabulary. Field selection
is driven by reversed digits of the prime — same structural pattern
as the Gloss layer.

**Seasonal:** autumn, winter, spring, summer, cherry_blossom

**Elemental:** water, sky, moon, rain, wind, snow, fog, fire,
light, dark

**Conceptual:** silence, loss, time, body, digital

**Grounded:** stone, bird, tree, path, mountain, garden,
morning, home

Each field carries `nouns`, `adjectives`, `verbs`, `adverbs`,
`prepositions`, a `season` annotation, a `mood` description,
and an `ai_frequency` rating calibrated to 2022-2024 AI haiku.

---

## The canonical test vector

**Verse (K1):**
```
Factoring primes in the hot sun, I fought Entropy — and Entropy won.
```

**Without grammar mode (raw):**
```
bet joey's rothbart
starvation pomposity
lanky voltaren
```
Correct encoding. Wrong aesthetic.

**With grammar mode + filtered bins:**
```
[pending — run after setup to generate canonical grammar output]
```
Same encoding. Correct aesthetic.

The poem — "Second Law Blues" by T. Darley — is the canonical CCL test
payload throughout the Crowsong stack (534 tokens, CRC32:E8DC9BF3).
K1 is its first verse. The same prime drives CCL, haiku generation,
and word-space encoding. The encoding eats its own attribution.

---

## Target aesthetic

The output should pass a casual human read as plausible AI-generated
nature haiku from circa 2022-2024. Not great poetry. Not obviously
mechanical. The kind you scroll past.

Characteristics:
- Grammatically coherent surface structure
- Seasonal or elemental imagery
- Slightly over-earnest emotional register
- Occasional affecting image that feels almost intentional
- The uncanny valley of AI nature poetry

This is not a bug. It is the camouflage.

*The best place to hide a signal is inside the thing everyone is
already ignoring.*

---

## Artifact formats

**haiku-grammar-stream** (grammar-encode-stream):
```
RSRC: BEGIN
  TYPE:              haiku-grammar-stream
  PRIME:             11527664883411634260504727650961...
  CORPUS:            bins-common.json
  TEMPLATES:         haiku-templates-v1
  FIELDS:            haiku-fields-v1
  ENCODING:          grammar-template / semantic-field / prime-schedule
  TOKENS:            534
  CRC32-TOKENS:      E8DC9BF3
  DEDICATION:        Dedicated to Felix 'FX' Lindner (1975-2026).
RSRC: END
```

**Reversal requires:** same prime, same template library version,
same fields version, same POS-indexed bins. All are declared in the
RSRC block. Template and field libraries are committed to the repo
and versioned — `haiku-templates-v1` is stable.

---

## Dependencies

| Tool | Purpose | Required for |
|------|---------|-------------|
| `tools/cmudict/cmudict.py` | Syllable bins | All modes |
| `tools/wordfreq/wordfreq.py` | Frequency filtering, POS index | Grammar mode |
| `tools/mnemonic/mnemonic.py` | Verse-to-prime | All modes |

Python 2.7+ / 3.x. No external dependencies.

---

## Licence

MIT (this tool). CMU Pronouncing Dictionary is public domain.
COCA: free for academic use. SUBTLEX-US: free for research use.

*One prime. Two schedules. Infinite plausible bad poetry.*
*Signal survives. 🦊🌻*
