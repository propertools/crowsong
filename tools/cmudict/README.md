# tools/cmudict/ -- CMU Pronouncing Dictionary mirror

Fetches, caches, and serves the CMU Pronouncing Dictionary for offline
use, syllable counting, and haiku corpus bin generation.

The CMU Pronouncing Dictionary contains ~134,000 English words with their
phonemic transcriptions. Syllable count is exact with respect to the
dictionary's phoneme transcription for any in-dictionary word: count the
vowel phonemes (those ending in a digit).

This is the syllable lookup backend for `tools/haiku/haiku.py`.

---

## Quick start

```bash
python cmudict.py fetch    # download, normalise, stamp with CAHF header
python cmudict.py verify   # verify SHA256 of cached file
python cmudict.py export   # write bins.json for the haiku tool
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
python cmudict.py syllables entropy      # entropy -> 3 syllables
python cmudict.py syllables signal       # signal -> 2 syllables
python cmudict.py syllables prime        # prime -> 1 syllable
python cmudict.py syllables algorithm    # algorithm -> 4 syllables

# Phoneme transcriptions
python cmudict.py phones entropy
# entropy -> EH1 N T R AH0 P IY0  (3 syllables)

python cmudict.py phones read
# read -> R IY1 D  (1 syllable)
# read (alternate 2) -> R EH1 D  (1 syllable)

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
with respect to the dictionary's phoneme transcription -- no heuristics,
no approximations.

```
ENTROPY  EH1 N T R AH0 P IY0   -> 3 vowels -> 3 syllables
SIGNAL   S IH1 G N AH0 L       -> 2 vowels -> 2 syllables
PRIME    P R AY1 M              -> 1 vowel  -> 1 syllable
```

---

## Bins

The `bins` command shows the distribution of words across syllable counts.
Counts below are illustrative; run `python cmudict.py bins` for live numbers
from your cached copy of the dictionary.

```
~134,000 unique words across 9 syllable bins:

    1 syllable   ~23,000 words
    2 syllables  ~44,000 words
    3 syllables  ~35,000 words
    4 syllables  ~19,000 words
    5 syllables   ~8,600 words
    6 syllables   ~2,900 words
    7 syllables     ~420 words
    8 syllables      ~70 words
    9 syllables       ~9 words
```

The bar chart produced by `bins` scales each bar relative to the largest
bin, giving a truthful picture of the distribution rather than saturating
at an arbitrary threshold.

The haiku tool (`tools/haiku/haiku.py`) draws from these bins to construct
5-7-5 syllable patterns driven by a prime key schedule.

---

## Cached file format

The cached file conforms to the **Crowsong Archivist Header Format (CAHF)**,
`draft-darley-crowsong-archivist-02`. It is a self-describing plain-text file
readable by any text editor and verifiable with any SHA256 calculator, with
no Crowsong software required.

```
# ARCHIVIST   v1.0
#
# SOURCE      https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict
# FETCHED     2026-04-06
# ENTRIES     134373
# CHARS       7432891
# LINES       134373
# LICENSE     Public domain (Carnegie Mellon University)
# TOOL        tools/cmudict/cmudict.py (Proper Tools SRL)
#
# Format: WORD  PH1 PH2 ... PHn
# Vowel phonemes end in a digit (0=unstressed, 1=primary, 2=secondary).
# Syllable count = number of phonemes ending in a digit.
#
# SHA256      <lowercase hex, 64 chars>
# ---END-HEADER---
A  EY1
A(2)  EY1
...
```

**Field format:** canonical CAHF double-space separator. Numeric fields
(`ENTRIES`, `CHARS`, `LINES`) are plain decimal digits with no punctuation,
for machine parseability. A legacy colon separator is accepted on read but
never written.

**Sentinel:** `# ---END-HEADER---` marks the exact header/body boundary.
Files without this line are classified as legacy and fail verification.

**SHA256 semantics (CAHF `§4.4` hashing contract):**

- At fetch time: CRLF is normalised to LF, trailing newlines are stripped,
  SHA256 is computed over `body.encode("utf-8")`.
- At write time: the normalised body is stored followed by exactly one
  trailing LF.
- At verify time: the body after the sentinel has that trailing LF stripped
  before recomputing, so stamp and verify hash the same bytes.
- Uppercase hex in a declared `SHA256` field is accepted and normalised to
  lowercase before comparison, per CAHF `§4.3`.

**HTTPS only:** plain HTTP sources are not used. A MITM on a first HTTP
fetch would control both the body and the hash written into the header,
defeating provenance entirely.

**Cross-tool compatibility:** files produced by this tool are intended to
be cross-verifiable by `tools/archivist/archivist.py` under the shared
CAHF specification:

```bash
python tools/archivist/archivist.py verify docs/cmudict/cmudict.dict
```

This tool uses a documented CAHF field subset (spec `§8.3`): `ARCHIVIST`,
`SOURCE`, `FETCHED`, `ENTRIES`, `CHARS`, `LINES`, `LICENSE`, `TOOL`, and
`SHA256`. Verification behaviour is fully conformant.

---

## Cache integrity and verified loading

All CLI commands that read the cache (`syllables`, `phones`, `bin`, `bins`,
`export`) call `load_verified_dict()`, which verifies the SHA256 before
returning any content. This is not optional and cannot be bypassed from
the CLI.

If the cache file fails verification, the command exits with a descriptive
error message and exit code 1. Re-fetch with `--force` to recover:

```bash
python cmudict.py fetch --force
```

`verify` reports status using the CAHF taxonomy:

| Output | Meaning |
|--------|---------|
| `Verification: PASS` | SHA256 matched; file is intact |
| `Verification: FAIL (damaged)` | SHA256 absent, invalid syntax, or mismatch |
| `Verification: FAIL (malformed)` | Duplicate required field detected |
| `Verification: FAIL (legacy)` | CAHF-family file but sentinel absent |
| `Verification: UNSUPPORTED` | CAHF-family file, unrecognised version |
| `Verification: UNSTAMPED` | Not a CAHF-family file |

The library function `load_unverified_dict()` skips verification and is
provided as an explicit escape hatch for callers that have already verified
externally. Its name is intentionally hard to misuse. All internal CLI paths
use `load_verified_dict()`.

---

## Exported bins format

`cmudict.py export` produces a JSON file for use by `haiku.py`. The
`source_sha256` field records which dictionary revision the bins were
derived from, allowing downstream tools to detect corpus drift.

```json
{
  "_meta": {
    "source":        "cmudict.dict",
    "source_sha256": "<sha256 of normalised dictionary body>",
    "generated":     "2026-04-06",
    "total_words":   134373,
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
and alphabetically sorted within each bin. The export command verifies the
cached dictionary before use and embeds `source_sha256` so that the
provenance of any `bins.json` is traceable to a specific upstream revision.

---

## Out-of-dictionary words

The tool returns `None` for words not in the dictionary. No heuristic
fallback is used. The haiku tool skips out-of-dictionary words when
building syllable bins.

Lookup is case-insensitive. No punctuation normalisation, apostrophe
normalisation, or Unicode normalisation is performed -- the lookup token
must otherwise match the dictionary's tokenisation exactly.

---

## Alternate pronunciations

Some words have multiple pronunciations. The `phones` command shows all:

```bash
python cmudict.py phones read
# read -> R IY1 D  (1 syllable)
# read (alternate 2) -> R EH1 D  (1 syllable)
```

The haiku tool uses only the primary pronunciation for syllable counting.
This is deterministic -- the same word always maps to the same syllable bin.

---

## Connection to the Crowsong stack

`cmudict.py` is the syllable lookup backend for `tools/haiku/haiku.py`.

The haiku tool uses `bins.json` to construct prime-driven haiku:

```
verse -> prime P
  forward digits  -> syllable count schedule (digit mod 5 + 1)
                     drives which syllable bin to draw from at each step
  reversed digits -> word selection index within the bin
                     Fisher-Yates seeded selection, same pattern as Gloss
```

One prime, two schedules, zero additional key material.

This tool's guarantees are:

- **Deterministic corpus export:** the same cached dictionary always
  produces the same `bins.json`, and `source_sha256` in `_meta` records
  exactly which revision it was derived from.
- **Sorted bins:** words within each bin are alphabetically sorted,
  giving downstream tools a stable, reproducible index.
- **Stable syllable lookup:** a given word always maps to the same
  count (primary pronunciation only).
- **Verified loading:** all CLI commands verify the cache SHA256 before
  use. Tampered or corrupted cache files are rejected, not silently consumed.

Reversibility claims (encode -> decode recovering the original) belong
to `tools/haiku/haiku.py`, where the full transformation is implemented.

---

## Tests

A canonical test suite is provided in `test_cmudict.py`. Run it with:

```bash
python test_cmudict.py
python -m pytest test_cmudict.py -v   # if pytest is available
```

The suite covers the CAHF format layer (header generation, parsing,
sentinel splitting, hashing contract, verification taxonomy), the core
dictionary parser, syllable counting, bin building, and export provenance.
It runs entirely offline with no network access and no cached file required.

---

## Polite use

The CMU dict is fetched once and cached indefinitely. The tool identifies
itself with a User-Agent header. Do not fetch repeatedly.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/archivist/archivist.py` | CAHF stamping and verification (can verify cmudict.dict) |
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

Format specification: `draft-darley-crowsong-archivist-02`
