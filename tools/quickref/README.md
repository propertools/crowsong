# tools/quickref/ — FDS Unicode quick reference card generator

Generates human-readable Unicode lookup tables for FDS decoding,
formatted for printing and archival. No external dependencies.

A person with one of these cards and an FDS-encoded message can decode
it by hand, without software, indefinitely. That is the point.

---

## Usage

```bash
python quickref.py list
python quickref.py block <name>
python quickref.py range <start> <end> [--name NAME]
python quickref.py preset <name>
python quickref.py full [--blocks TAGS] [--output FILE]
```

All subcommands accept `--output FILE` to write to a file instead of
stdout.

## Examples

```bash
# List all 53 blocks and 7 presets
python quickref.py list

# Reference card for a named block
python quickref.py block Greek
python quickref.py block CJK
python quickref.py block Hiragana
python quickref.py block Arabic

# Reference card for an arbitrary code point range
python quickref.py range 0x1F600 0x1F64F --name "Emoticons"
python quickref.py range 19968 40959 --name "CJK Unified Ideographs"

# Named preset cards
python quickref.py preset ascii                           # 82 lines
python quickref.py preset crowsong                        # ~3200 lines
python quickref.py preset vesper                          # ~4700 lines
python quickref.py preset emoji                           # WIDTH/7 required

# Save to file
python quickref.py preset crowsong --output docs/quickref-crowsong.txt
python quickref.py preset vesper   --output docs/quickref-vesper.txt

# Full reference — all 53 blocks
python quickref.py full --output docs/quickref-full.txt

# Full reference, specific tag group
python quickref.py full --blocks math,symbol --output docs/quickref-math.txt
```

## Presets

| Preset | Title | Lines | Description |
|--------|-------|-------|-------------|
| `ascii` | FDS ASCII Quick Reference | ~82 | Essential card — ASCII printable only |
| `crowsong` | FDS Crowsong Deployment Reference | ~3200 | Blocks for operational FDS environments |
| `vesper` | FDS Vesper Archive Edition | ~4700 | Broad script coverage for long-horizon archival |
| `emoji` | FDS Emoji Quick Reference | ~800 | All emoji blocks; WIDTH/7 required |
| `math` | FDS Mathematical Symbols | ~600 | Operators, arrows, letterlike symbols |
| `european` | FDS European Scripts | ~2000 | Latin, Greek, Cyrillic, Armenian, Hebrew |
| `cjk` | FDS CJK Reference | ~3500 | CJK ideographs, Hiragana, Katakana, Hangul |

## Block registry

53 Unicode blocks across all planes, tagged for preset selection.
Tags: `ascii`, `latin`, `european`, `middle-eastern`, `south-asian`,
`east-asian`, `math`, `symbol`, `emoji`, `crowsong`, `vesper`.

Selected highlights:

| Block | Range | Tag(s) |
|-------|-------|--------|
| Basic Latin | U+0000–U+007F | ascii, crowsong, vesper |
| Greek and Coptic | U+0370–U+03FF | european, math, crowsong, vesper |
| Cyrillic | U+0400–U+04FF | european, crowsong, vesper |
| Arabic | U+0600–U+06FF | middle-eastern, vesper |
| Devanagari | U+0900–U+097F | south-asian, vesper |
| Hiragana | U+3040–U+309F | east-asian, crowsong, vesper |
| Katakana | U+30A0–U+30FF | east-asian, crowsong, vesper |
| CJK Unified Ideographs | U+4E00–U+9FFF | east-asian, crowsong, vesper |
| Emoticons | U+1F600–U+1F64F | emoji, crowsong |

Add a block to a preset by adding its tag to the `BLOCKS` registry
entry in `quickref.py`.

## Output format

Each section shows the block name, code point range, and assigned
character count. Small blocks (≤48 chars) use detail format — one
entry per line with Unicode name:

```
========================================================================
  General Punctuation (U+2000–U+206F)  111 assigned
========================================================================

  08192     En space
  08193     Em space
  08194     Three-per-em space
  08211  –  En dash
  08212  —  Em dash
  08216  '  Left single quotation mark
  08217  '  Right single quotation mark
  ...
```

Large blocks use compact grid format — 8 characters per row:

```
========================================================================
  CJK Unified Ideographs (U+4E00–U+9FFF)  20992 assigned
========================================================================

  19968=一  19969=丁  19970=丂  19971=七  19972=丄  19973=丅  19974=丆  19975=万
  19976=丈  19977=三  19978=上  19979=下  19980=丌  19981=不  19982=与  19983=丏
  ...
```

Emoji blocks (WIDTH/7) auto-declare the required header format:

```
========================================================================
  Emoticons (U+1F600–U+1F64F)  80 assigned  WIDTH/7 REQUIRED
========================================================================

  Header: ENC: UCS · DEC · COL/6 · PAD/0000000 · WIDTH/7

   128512=😀   128513=😁   128514=😂   128515=😃  ...
```

## Connection to the Crowsong stack

The quick reference card is the physical-layer fallback for FDS
decoding. When software is unavailable, a printed card is the
reference material that makes Structural Principle 3 concrete:

> Any layer that cannot, in principle, be operated by a human with
> sufficient patience and appropriate reference material has a single
> point of failure in software.

The `vesper` preset is specifically designed for inclusion in a Vesper
physical archive capsule alongside FDS-encoded documents. A reader
who recovers the capsule decades hence has everything needed to decode
the contents by hand.

The `crowsong` preset covers the scripts and symbols most likely to
appear in operational Crowsong traffic.

## Generating and committing the full card set

To regenerate all reference cards and commit them to the repository:

```bash
mkdir -p docs/quickref
for preset in ascii crowsong vesper emoji math european cjk; do
    python tools/quickref/quickref.py preset $preset \
        --output docs/quickref/quickref-${preset}.txt
done
python tools/quickref/quickref.py full \
    --output docs/quickref/quickref-full.txt
```

Then commit:

```bash
git add docs/quickref/
git commit -m "chore(docs): regenerate Unicode quick reference cards"
```

Pre-generated cards live in `docs/quickref/`. They are plain UTF-8
text, human-readable without software, and suitable for printing and
Vesper archival. The `ascii` card (82 lines) is the essential field
reference. The `vesper` card (4700+ lines) is the archival edition.

Cards are regenerated by running the above — they are outputs of
`tools/quickref/quickref.py`, not source files. If the tool or the
Unicode version changes, regenerate and commit.

## Compatibility

Python 2.7+ / 3.x. No dependencies beyond the standard library.
`unicodedata` is used for character names and categories.

Generated output files are plain UTF-8 text with no dependencies.

## License

MIT. See `../../LICENSE` and `../../LICENSES.md`.
