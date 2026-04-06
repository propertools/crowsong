# tools/cmudict/ — CMU Pronouncing Dictionary mirror

Fetches, caches, and serves the CMU Pronouncing Dictionary for offline
use, syllable counting, and haiku corpus bin generation.

The CMU Pronouncing Dictionary contains ~134,000 English words with their
phonemic transcriptions. Syllable count is exact for any in-dictionary word:
count the vowel phonemes (those ending in a digit).

This is the syllable lookup backend for `tools/haiku/haiku.py`.

---

## Quick start

```bash
# Fetch and cache the dictionary
python cmudict.py fetch

# Verify the cached file
python cmudict.py verify

# Export syllable bins for the haiku tool
python cmudict.py export
```

---

## Usage

```bash
python cmudict.py fetch              # download and cache
python cmudict.py verify             # verify SHA256 of cached file
python cmudict.py syllables <word>   # syllable count for a word
python cmudict.py phones <word>      # full phoneme transcription
python cmudict.py bin <n>            # all words with n syllables
python cmudict.py bins               # summary: count per bin
python cmudict.py export             # write bins.json for haiku tool
```

The `--dir` flag overrides the default cache directory (`docs/cmudict/`):

```bash
python cmudict.py --dir /path/to/cache fetch
```

---

## Examples

```bash
# Basic lookups
python cmudict.py syllables entropy      # entropy → 3 syllables
python cmudict.py syllables signal       # signal → 2 syllables
python cmudict.py syllables prime        # prime → 1 syllable
python cmudict.py syllables algorithm    # algorithm → 4 syllables

# Phoneme transcriptions
python cmudict.py phones entropy
# entropy → EH1 N T R AH0 P IY0  (3 syllables)

python cmudict.py phones read
# read → R IY1 D  (1 syllable)
# read (alternate 2) → R EH1 D  (1 syllable)

# List all 2-syllable words
python cmudict.py bin 2 | head -20

# Count words per bin
python cmudict.py bins

# Export bins for haiku generation
python cmudict.py export
python cmudict.py export --output docs/cmudict/bins.json
python cmudict.py export --min-syllables 1 --max-syllables 7
```

---

## Syllable counting

Each phoneme in the CMU dict ends in a digit if it is a vowel nucleus:

| Suffix | Meaning |
|--------|---------|
| `0` | unstressed |
| `1` | primary stress |
| `2` | secondary stress |

Syllable count = number of phonemes ending in a digit. This is exact
for any word in the dictionary — no heuristics, no approximations.

```
ENTROPY  EH1 N T R AH0 P IY0   → 3 vowels → 3 syllables
SIGNAL   S IH1 G N AH0 L       → 2 vowels → 2 syllables
PRIME    P R AY1 M              → 1 vowel  → 1 syllable
```

---

## Bins

The `bins` command shows the distribution of words across syllable counts:

```
134,373 unique words across 9 syllable bins:

    1 syllable   23,812 words  ██████████████░░░░░░░░░░░░░░░░
    2 syllables  44,210 words  ██████████████████████████████
    3 syllables  34,891 words  ████████████████████░░░░░░░░░░
    4 syllables  19,432 words  ████████████░░░░░░░░░░░░░░░░░░
    5 syllables   8,614 words  █████░░░░░░░░░░░░░░░░░░░░░░░░░
    6 syllables   2,891 words  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    7 syllables     423 words  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    8 syllables      71 words  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    9 syllables       9 words  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The haiku tool (`tools/haiku/haiku.py`) draws from these bins to
construct 5-7-5 syllable patterns driven by a prime key schedule.

---

## Cached file format

The cached file uses the archivist header format, consistent with
the rest of the Crowsong corpus tools:

```
# CMU Pronouncing Dictionary
#
# Source:   https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
# Fetched:  2026-04-06
# Entries:  134,373
# SHA256:   a1b2c3d4...
# License:  Public domain (Carnegie Mellon University)
#
# Format: WORD  PH1 PH2 ... PHn
# Vowel phonemes end in a digit (0=unstressed, 1=primary, 2=secondary).
# Syllable count = number of phonemes ending in a digit.
#
[dictionary entries]
```

SHA256 is computed over the raw dictionary body (excluding the header).
Verification recomputes and checks against the declared hash.

---

## Exported bins format

`cmudict.py export` produces a JSON file for use by `haiku.py`:

```json
{
  "_meta": {
    "source": "cmudict.dict",
    "generated": "2026-04-06",
    "total_words": 134212,
    "min_syllables": 1,
    "max_syllables": 9,
    "note": "Syllable counts from CMU Pronouncing Dictionary..."
  },
  "1": ["a", "ab", "ace", "ache", ...],
  "2": ["abbey", "abbot", "able", ...],
  "3": ["abandon", "abacus", ...],
  ...
}
```

Keys are string representations of syllable counts. Words are lowercase
and alphabetically sorted within each bin. The `_meta` key carries
provenance — the file is self-describing.

---

## Out-of-dictionary words

The tool returns `None` for words not in the dictionary. No heuristic
fallback is used. The haiku tool skips out-of-dictionary words when
building syllable bins — the ~134,000 in-dictionary words are sufficient.

For reference: the Gutenberg corpus filtered to in-dictionary words
still provides tens of thousands of candidates per syllable bin, more
than enough for prime-driven word selection.

---

## Alternate pronunciations

Some words have multiple pronunciations. The `phones` command shows all:

```bash
python cmudict.py phones read
# read → R IY1 D  (1 syllable)
# read (alternate 2) → R EH1 D  (1 syllable)
```

The haiku tool uses only the primary pronunciation for syllable counting.
This is consistent and deterministic — the same word always maps to the
same syllable bin.

---

## Connection to the Crowsong stack

`cmudict.py` is the syllable lookup backend for `tools/haiku/haiku.py`.

The haiku tool uses `bins.json` to construct prime-driven haiku:

```
verse → prime P
  forward digits  → syllable count schedule (digit mod 5 + 1)
                    drives which syllable bin to draw from at each step
  reversed digits → word selection index within the bin
                    Fisher-Yates seeded selection, same pattern as Gloss
```

One prime, two schedules, zero additional key material. The same
structural pattern as the Gloss layer.

The canonical test vector:

```
entropy always wins
signal strains but never gone
one prime, infinite
```

Generated from K1. Deterministically reversible given the prime and
the `bins.json` corpus. The format eats its own output.

---

## Polite use

The CMU dict is fetched once and cached indefinitely. The tool
identifies itself with a User-Agent header. Do not fetch repeatedly.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/haiku/haiku.py` | Prime-driven haiku generator (uses bins.json) |
| `tools/mnemonic/mnemonic.py` | Verse-to-prime construction |
| `tools/texts/texts.py` | Gutenberg canonical text corpus |

---

## Compatibility

Python 2.7+ / 3.x. No external dependencies.
Network access required for `fetch`; all other subcommands work offline.

---

## License

MIT (this tool). The CMU Pronouncing Dictionary is public domain,
released by Carnegie Mellon University.

Source: https://github.com/cmusphinx/cmudict
