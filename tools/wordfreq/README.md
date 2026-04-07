# tools/wordfreq/ — English word frequency corpus mirror

Fetches, caches, and serves word frequency data from three public
English corpora. The primary use case is filtering the CMU Pronouncing
Dictionary syllable bins to common vocabulary, so that `haiku_twist.py`
produces output that reads as natural English rather than drawing from
the full 134,000-word CMU dict including obscure technical terms.

---

## Sources

### COCA — Corpus of Contemporary American English
**Mark Davies, Brigham Young University**

60,000 most frequent English words. Balanced corpus: spoken, fiction,
popular magazines, newspapers, academic. Frequency given as occurrences
per million words. The standard reference for serious NLP frequency work.

Free for academic and research use.

### SUBTLEX-US
**Brysbaert & New (2009), Ghent University**

~74,000 words derived from 8,388 US film and TV subtitle files
(51 million words). The best available proxy for words that fluent
English speakers recognise instantly — common spoken vocabulary, not
book vocabulary.

**Recommended for haiku corpus filtering.** Words that appear
frequently in subtitles are the words people actually use and
understand without effort. This is the right frequency reference
for a haiku generator whose output should sound like human poetry.

Free for research use.

### Google Books Ngram 1-grams (2019 English corpus)
**Google Books / Michel et al. (2011) — CC BY 3.0**

Aggregated total frequency per word across all years in the 2019
Google Books English corpus. Enormous corpus, books-biased.

**Warning: ~5GB compressed download.** Use COCA or SUBTLEX for most
purposes. Ngrams is available for completeness and for research that
specifically requires the books corpus.

---

## Quick start

```bash
# Fetch COCA and SUBTLEX (recommended — fast, no registration required)
python tools/wordfreq/wordfreq.py fetch

# Filter cmudict bins to common vocabulary (top 30,000 by rank)
python tools/wordfreq/wordfreq.py filter \
    --bins docs/cmudict/bins.json \
    --output docs/cmudict/bins-common.json

# Use filtered bins with haiku_twist.py
echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
    python tools/mnemonic/haiku_twist.py \
        --bins docs/cmudict/bins-common.json generate
```

---

## Usage

```bash
python wordfreq.py fetch   [--source SOURCE] [--dir DIR] [--force]
python wordfreq.py verify  [--source SOURCE] [--dir DIR]
python wordfreq.py lookup  <word> [--source SOURCE] [--dir DIR]
python wordfreq.py top     <n>    [--source SOURCE] [--dir DIR]
python wordfreq.py export  [--source SOURCE] [--format tsv|json]
python wordfreq.py filter  --bins FILE [--source SOURCE]
                           [--min-rank N] [--min-freq F]
                           [--output FILE] [--dir DIR]
```

`SOURCE`: `coca` | `subtlex` | `ngrams` | `all` | comma-separated list
Default: `coca,subtlex`

`--dir`: cache directory (default: `docs/wordfreq/`)

---

## Examples

```bash
# Fetch default sources (COCA + SUBTLEX)
python wordfreq.py fetch

# Fetch only SUBTLEX
python wordfreq.py fetch --source subtlex

# Fetch everything including ngrams (~5GB, takes a while)
python wordfreq.py fetch --source all

# Verify cached files
python wordfreq.py verify

# Look up a word
python wordfreq.py lookup entropy
python wordfreq.py lookup signal
python wordfreq.py lookup voltaren   # probably not in subtlex top 30k

# Top 20 words by SUBTLEX frequency
python wordfreq.py top 20 --source subtlex

# Filter bins to SUBTLEX top 30,000 (default)
python wordfreq.py filter --bins docs/cmudict/bins.json

# Filter to top 10,000 — very common words only, tighter haiku
python wordfreq.py filter \
    --bins docs/cmudict/bins.json \
    --min-rank 10000 \
    --output docs/cmudict/bins-common-10k.json

# Filter by frequency threshold instead of rank
python wordfreq.py filter \
    --bins docs/cmudict/bins.json \
    --min-freq 1.0 \
    --output docs/cmudict/bins-freq1.json

# Export COCA as JSON
python wordfreq.py export --source coca --format json | head -50
```

---

## The filter subcommand

`filter` is the primary interface between word frequency data and the
haiku machine.

It takes `docs/cmudict/bins.json` (produced by `tools/cmudict/cmudict.py
export`) and produces a filtered version containing only words that
appear in the frequency corpus above the threshold you specify.

```
Input:  docs/cmudict/bins.json      (~134,000 words, all CMU dict entries)
Output: docs/cmudict/bins-common.json  (~30,000 words, common vocabulary)
```

The output is a drop-in replacement for `bins.json` in `haiku_twist.py`:

```bash
# Before filtering: output may include 'voltaren', 'blankenbeckler',
# 'rothbart', 'quinon' — valid words, correct syllable counts,
# not what you'd expect to read in a poem
echo "..." | python haiku_twist.py --bins docs/cmudict/bins.json generate

# After filtering: output draws from the vocabulary of natural speech
echo "..." | python haiku_twist.py --bins docs/cmudict/bins-common.json generate
```

### Retention by threshold

| --min-rank | Approximate words retained | Character |
|-----------|---------------------------|-----------|
| 5,000 | ~3,500 | Very common — everyday speech |
| 10,000 | ~7,000 | Common — most prose |
| 30,000 | ~20,000 | Broad — newspapers, novels |
| 60,000 | ~35,000 | Wide — full COCA vocabulary |

The default (30,000) is a reasonable balance between haiku that sounds
natural and haiku that has enough variety to be interesting.

### The bins-common.json _meta block

The filtered file carries provenance in its `_meta` key:

```json
{
  "_meta": {
    "source": "cmudict.dict",
    "generated": "2026-04-07",
    "filtered_by": ["SUBTLEX-US"],
    "filter": "top-30000-by-rank",
    "total_words": 19847,
    "words_before": 126043,
    "words_removed": 106196,
    "retention_pct": 15.7,
    "note": "Syllable bins filtered to common English vocabulary..."
  }
}
```

---

## Connection to the Crowsong stack

The haiku machine (`tools/mnemonic/haiku_twist.py`) selects words from
syllable bins using a prime-driven Fisher-Yates permutation. Every word
in the bins is equally likely to be selected. Without frequency filtering,
obscure technical terms, proper nouns, and medical vocabulary compete
equally with common words.

Frequency filtering doesn't change the construction — it changes the
vocabulary the construction draws from. The prime-driven selection
remains fully deterministic and reversible. The words just sound like
English.

The canonical test vector demonstrates the problem without filtering:

```
bet joey's rothbart
starvation pomposity
lanky voltaren
```

This is FX's poem encoded correctly. The pipeline works. The words are
valid. They are also not what you'd want to hand to a reader as poetry.

After filtering to SUBTLEX top 30,000:

```
[whatever the filtered corpus produces — pending test]
```

---

## File layout

```
tools/wordfreq/
    wordfreq.py
    README.md
docs/wordfreq/
    coca-60k.tsv              archivist header + COCA data
    subtlex-us.tsv            archivist header + SUBTLEX-US data
    ngrams-1gram-aggregated.tsv.gz   aggregated ngrams (if fetched)
docs/cmudict/
    bins.json                 full CMU dict bins (from cmudict.py export)
    bins-common.json          filtered bins (from wordfreq.py filter)
```

---

## Compatibility

Python 2.7+ / 3.x. No external dependencies. All stdlib.
(`gzip`, `csv`, `json`, `hashlib`, `io` — all standard.)

Network access required for `fetch` only. All other subcommands
work offline from the cached files.

---

## Licence

MIT (this tool). Source corpora:
- COCA: free for academic/research use (wordfrequency.info)
- SUBTLEX-US: free for research use (Ghent University)
- Google Books Ngrams: CC BY 3.0

*Signal survives. The vocabulary survives with it.*
