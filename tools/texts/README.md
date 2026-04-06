# tools/texts/ — Project Gutenberg canonical text mirror

Fetches, caches, and serves a curated corpus of 42 canonical texts from
Project Gutenberg for offline use, Vesper archival, and mnemonic anchor
purposes.

A memorised line from any of these texts can serve as a verse mnemonic
for prime derivation. The key exists nowhere until derived. The texts are
indestructible. They have survived civilisations. They will survive this one.

---

## Usage

```bash
python texts.py list
python texts.py show <id>
python texts.py fetch [<id> ...] [--all] [--force]
python texts.py verify [<id> ...]
python texts.py search <query>
python texts.py excerpt <id> [--lines N] [--offset N]
```

The `--dir` flag overrides the default cache directory (`docs/texts/`):

```bash
python texts.py --dir /path/to/cache list
```

## Examples

```bash
# List all 42 texts in the registry
python texts.py list

# Show metadata and cache status for a text
python texts.py show shakespeare

# Fetch specific texts
python texts.py fetch bible-kjv shakespeare laozi-tao

# Fetch the entire corpus (~25MB, ~15 min with polite delays)
python texts.py fetch --all

# Re-fetch everything (e.g. after a bug fix to the stripping logic)
python texts.py fetch --all --force

# Verify SHA256 of all cached files
python texts.py verify

# Search registry metadata
python texts.py search persian
python texts.py search mnemonic-anchor

# Print an excerpt from a cached text
python texts.py excerpt aurelius-meditations --lines 5
python texts.py excerpt bible-kjv --lines 3 --offset 1000
python texts.py excerpt shakespeare --lines 4 --offset 5000
```

---

## The corpus

42 texts across 16 regions. Selected for cultural durability, geographic
diversity, and mnemonic anchor value.

**Scripture**

| ID | Title | Notes |
|----|-------|-------|
| `bible-kjv` | The Bible (King James Version) | Billions of memorised lines |
| `quran-english` | The Koran (Rodwell translation) | Arabic original memorised by hundreds of millions |
| `upanishads` | The Upanishads (selections) | Max Müller translation |

**Epic and classical**

| ID | Title | Notes |
|----|-------|-------|
| `homer-iliad` | The Iliad | *Sing, O goddess, the anger of Achilles* |
| `homer-odyssey` | The Odyssey | *Tell me, O muse, of that ingenious hero* |
| `virgil-aeneid` | The Aeneid | *Arms, and the man I sing* |
| `dante-inferno` | Inferno (Divine Comedy Part I) | Longfellow translation |
| `chaucer-tales` | The Canterbury Tales | Middle English |
| `kalidasa-shakuntala` | Shakuntala | Jones translation |

**Philosophy**

| ID | Title | Notes |
|----|-------|-------|
| `plato-republic` | The Republic | Jowett translation |
| `aristotle-nicomachean` | Nicomachean Ethics | Ross translation |
| `aurelius-meditations` | Meditations | *You have power over your mind, not outside events* |
| `machiavelli-prince` | The Prince | Marriott translation |
| `confucius-analects` | The Analects of Confucius | Legge translation |
| `laozi-tao` | Tao Te Ching | *The Tao that can be told is not the eternal Tao* |
| `sunzi-art-war` | The Art of War | Lionel Giles translation |

**Novel**

| ID | Title | Notes |
|----|-------|-------|
| `shakespeare` | The Complete Works of William Shakespeare | ~5MB — the largest single anchor |
| `cervantes-quixote` | Don Quixote | *In a village of La Mancha...* |
| `hugo-miserables` | Les Misérables | Hapgood translation |
| `dostoevsky-brothers` | The Brothers Karamazov | Garnett translation |
| `tolstoy-war-peace` | War and Peace | Maude translation |
| `austen-pride` | Pride and Prejudice | *It is a truth universally acknowledged* |
| `dickens-tale` | A Tale of Two Cities | *It was the best of times* |
| `melville-moby` | Moby Dick | *Call me Ishmael* |
| `shelley-frankenstein` | Frankenstein | 1818 first edition |
| `twain-huckleberry` | Adventures of Huckleberry Finn | |
| `murasaki-genji` | The Tale of Genji | The world's first novel |
| `kafka-metamorphosis` | Metamorphosis | Wyllie translation |

**Poetry**

| ID | Title | Notes |
|----|-------|-------|
| `whitman-leaves` | Leaves of Grass | *I sing myself* |
| `dickinson-poems` | Poems by Emily Dickinson | *Because I could not stop for Death* |
| `blake-songs` | Songs of Innocence and Experience | *Tyger, Tyger, burning bright* |
| `keats-poems` | Poems of John Keats | *A thing of beauty is a joy for ever* |
| `omar-khayyam` | The Rubaiyat of Omar Khayyam | FitzGerald translation |
| `rumi-masnavi` | The Masnavi (Book I) | Whinfield translation |
| `tagore-gitanjali` | Gitanjali (Song Offerings) | Nobel Prize 1913 |

**Narrative and travel**

| ID | Title | Notes |
|----|-------|-------|
| `arabian-nights` | One Thousand and One Nights | Lane translation |
| `ibn-battuta-travels` | Travels in Asia and Africa | 75,000 miles across three continents |
| `poe-tales` | Tales of Mystery and Imagination | *True — nervous — very, very dreadfully nervous* |
| `wells-time-machine` | The Time Machine | The Eloi and the Morlocks |
| `stapledon-starmaker` | Star Maker | Gutenberg Australia; Freeman Dyson credited this book with inspiring the Dyson sphere |

**Science**

| ID | Title | Notes |
|----|-------|-------|
| `darwin-origin` | On the Origin of Species | *There is grandeur in this view of life* |
| `goethe-faust` | Faust (Part I) | Bayard Taylor translation |

---

## Cached file format

Each file is self-describing plain UTF-8 text, human-readable without
software, and suitable for Vesper archival:

```
# The Bible (King James Version)
#
# Author:    Various
# Language:  en
# Region:    Middle East / global
# Source:    Project Gutenberg #10
#            https://www.gutenberg.org/ebooks/10
# Fetched:   2026-04-06
# Chars:     4,332,583
# Lines:     99,997
# SHA256:    f05490ad96d7a8f386586b48811eb3de...
# Tags:      scripture, english, mnemonic-anchor
# Notes:     The KJV. Billions of memorised lines...
#
# Text is in the public domain per Project Gutenberg.
# https://www.gutenberg.org/policy/terms_of_use
#

[text body]
```

SHA256 is computed over the body only (after Gutenberg header/footer
stripping and CRLF normalisation). Verification recomputes and checks
against the declared hash.

---

## Generating and committing the full corpus

```bash
mkdir -p docs/texts
python tools/texts/texts.py fetch --all
python tools/texts/texts.py verify
git add docs/texts/
git commit -m "chore(docs): mirror Project Gutenberg canonical text corpus"
```

The full corpus is approximately 25MB and takes around 15 minutes to
fetch with the built-in politeness delay (3 seconds between requests).
Do not run `fetch --all --force` repeatedly — OEIS is a free public
resource maintained by volunteers. Gutenberg is not OEIS, but the
principle holds.

---

## Connection to the Crowsong stack

The texts serve two roles:

**Mnemonic anchor corpus** — any memorised line from any of these texts
is a verse input for `tools/mnemonic/verse_to_prime.py`. The verse
derives a prime; the prime derives a CCL key schedule or a Shamir share
wrapping key. The key exists nowhere until derived from the verse.

**Sparse corpus addressing** — the texts can serve as the target corpus
for the sparse offset-addressed CCL construction: a verse-derived prime
addresses specific byte offsets within a named text, extracting key
material. "Which line of which text" is the secret; the texts themselves
are public. See `docs/mnemonic-shamir-sketch.md` for the full
construction.

**Vesper archival** — the cached files are plain UTF-8, self-describing,
and suitable for inclusion in a Vesper archive capsule. A reader who
recovers the archive decades hence has both the encoded documents and the
reference corpus needed to reconstruct any verse-derived keys.

---

## Polite use

The tool sleeps 3 seconds between requests and identifies itself in the
User-Agent header. Project Gutenberg is a free public resource maintained
by volunteers. Do not hammer it.

Most texts are fetched from `https://www.gutenberg.org/cache/epub/<ID>/pg<ID>.txt`.
Star Maker is fetched from Project Gutenberg Australia
(`https://gutenberg.net.au/`) — the only exception in the corpus.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/mnemonic/mnemonic.py` | Verse-to-prime derivation |
| `tools/mnemonic/verse_to_prime.py` | Prime derivation artifact |
| `tools/sequences/sequences.py` | OEIS sequence mirror |
| `tools/constants/constants.py` | Named mathematical constants |

---

## Compatibility

Python 2.7+ / 3.x. No dependencies beyond the standard library.
Network access required for `fetch`; all other subcommands work offline.

---

## Licence

MIT (this tool). Text copyright their respective authors and translators.
All texts are in the public domain per Project Gutenberg terms of use.
See: https://www.gutenberg.org/policy/terms_of_use
