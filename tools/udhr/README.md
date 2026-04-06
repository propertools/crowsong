# udhr

UDHR PDF corpus mirror.

Fetches and mirrors translations of the Universal Declaration of Human Rights
from OHCHR, organized on disk by Unicode script family. The UDHR is the most
translated document on earth — the same text in every language, professionally
rendered, freely redistributable, and recoverable from any library in the
world.

For Crowsong entropy analysis, the UDHR is the ideal corpus: same document,
every script, no domain noise. A Chinese UDHR and an Arabic UDHR and a Hindi
UDHR are directly comparable because the underlying text is identical.

---

## Quick start

```bash
# First run: discover all available language codes from OHCHR (560+)
python udhr.py discover

# Review what's available
python udhr.py list
python udhr.py list --script Arabic

# Fetch all PDFs — canonical archival copies
python udhr.py fetch --all

# Fetch PDFs and extract plain text alongside for analysis
python udhr.py fetch --all --extract

# Verify the corpus
python udhr.py verify
```

---

## Directory layout

```
docs/udhr/
    Arabic/
        urd_Urdu.pdf
    Armenian/
        arm_Armenian.pdf
    Bengali/
        asm_Assamese.pdf
        bng_Bengali.pdf
    CJK/
        chn_Chinese-Simplified.pdf
        jpn_Japanese.pdf
    Cyrillic/
        blg_Bulgarian.pdf
        khk_Mongolian.pdf
        rus_Russian.pdf
        ukr_Ukrainian.pdf
    Devanagari/
        hnd_Hindi.pdf
        mrt_Marathi.pdf
        nep_Nepali.pdf
    Ethiopic/
        amh_Amharic.pdf
    Georgian/
        geo_Georgian.pdf
    Greek/
        grk_Greek.pdf
    Gujarati/
        gjr_Gujarati.pdf
    Gurmukhi/
        pnj1_Punjabi-Gurmukhi.pdf
    Hebrew/
        hbr_Hebrew.pdf
        ydd_Yiddish.pdf
    Khmer/
        khm_Khmer.pdf
    Latin/
        dut_Dutch.pdf
        eng_English.pdf
        frn_French.pdf
        ger_German.pdf
        inz_Indonesian.pdf
        itn_Italian.pdf
        por_Portuguese.pdf
        spn_Spanish.pdf
        swa_Swahili.pdf
        trk_Turkish.pdf
        vie_Vietnamese.pdf
    Malayalam/
        mls_Malayalam.pdf
    Oriya/
        ory_Odia.pdf
    Sinhala/
        snh_Sinhala.pdf
    Tamil/
        tam_Tamil.pdf
    Thai/
        thj_Thai.pdf
    (one directory per script family; .txt alongside .pdf if --extract used)
```

Filenames are `{ohchr_code}_{Language}.pdf`. Both the retrieval code and
the human-readable name are visible in any file browser — no manifest
required. The script directory tells you at a glance which CCL mode is
appropriate for that document.

---

## Subcommands

### discover

Build or update `registry.json` by scraping the OHCHR translations index.

```bash
python udhr.py discover
python udhr.py discover --probe   # also probe each new code's PDF URL
```

`discover` fetches the OHCHR browse page, extracts all `LangID=` codes from
the HTML, and writes them to `registry.json`. Run once; re-run when you want
to pick up new translations OHCHR has added.

If the OHCHR browse page is unreachable, the tool falls back to the built-in
bootstrap registry (48 languages, confirmed codes).

### probe

For languages whose OHCHR code is unconfirmed, try candidate codes in order
until one serves a valid PDF. Updates `registry.json` in place.

```bash
python udhr.py probe              # probe all unconfirmed languages
python udhr.py probe kor lao mya  # probe specific languages
```

Run `probe` after `discover` if some languages are failing with 404. OHCHR
uses an internal code system unrelated to ISO 639; `probe` resolves
discrepancies by trying known alternative codes.

### list

List languages in the registry, grouped by script family.

```bash
python udhr.py list
python udhr.py list --script CJK
python udhr.py list --script Devanagari
```

### fetch

Fetch PDFs from OHCHR. Already-cached files are skipped unless `--force`.

```bash
python udhr.py fetch --all
python udhr.py fetch --all --extract      # fetch + extract text
python udhr.py fetch --all --force        # re-fetch everything
python udhr.py fetch eng arz chn jpn kor  # specific languages by ID
```

`--extract` runs `pdftotext -enc UTF-8 -nopgbrk` on each PDF immediately
after fetching. Requires `pdftotext` (Poppler). The `.txt` file lands beside
the `.pdf` in the same script directory.

### extract

Run `pdftotext` on already-cached PDFs to produce `.txt` files.

```bash
python udhr.py extract              # extract all cached
python udhr.py extract arz chn jpn  # specific languages
```

Useful if you fetched without `--extract` and want the text later, or if you
want to re-extract after updating pdftotext.

Note that some UDHR PDFs are image-only scans with no embedded text —
`pdftotext` will fail on these silently, and the `.txt` file will not be
created. This is a property of the OHCHR source document, not a tool error.

### verify

Verify that cached PDFs are valid (correct `%PDF` header, non-trivial size).

```bash
python udhr.py verify
python udhr.py verify chn jpn kor
```

---

## Entropy analysis pipeline

Once text is extracted, pipe it into the advisor:

```bash
# Arabic — advisor will recommend Gloss + CCL3
python udhr.py extract arz
cat docs/udhr/Arabic/arz_Arabic.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/crowsong-advisor.py

# Chinese — Gloss gain is largest (+1.36 bits/token)
python udhr.py extract chn
cat docs/udhr/CJK/chn_Chinese-Simplified.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/crowsong-advisor.py --analyse

# English — CCL3 alone wins (no Gloss needed)
cat docs/udhr/Latin/eng_English.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/crowsong-advisor.py
```

---

## Registry

Language codes and metadata live in `registry.json` (default location:
`tools/udhr/registry.json`). The registry is a JSON object mapping language
IDs to entries:

```json
{
  "chn": {
    "code": "chn",
    "name": "Chinese-Simplified",
    "script": "CJK",
    "region": "East-Asia"
  },
  ...
}
```

The registry is the source of truth for which code to use when fetching
from OHCHR. It is updated by `discover` and `probe` and can be hand-edited
for corrections.

If no `registry.json` exists, the tool falls back to the built-in bootstrap
(48 languages). Run `discover` once to build a full registry.

Specify a custom registry location with `--registry`:

```bash
python udhr.py --registry tools/udhr/registry.json fetch --all
```

---

## Known gaps

OHCHR uses an internal code system with no public documentation. Some
languages that exist on the OHCHR website cannot be fetched because the
correct code is unknown. As of April 2026, the following are unresolved:

| Language | Script | Status |
|----------|--------|--------|
| Arabic | Arabic | Returns empty body (code `arz` exists but PDF is blank) |
| Chinese Traditional | CJK | Code unknown |
| Kannada | Kannada | Code unknown |
| Korean | Hangul | Code unknown |
| Lao | Lao | Code unknown |
| Burmese | Myanmar | Code unknown |
| Persian | Arabic | Code unknown |
| Polish | Latin | Code unknown |
| Serbian | Cyrillic | Code unknown |
| Telugu | Telugu | Code unknown |
| Tibetan | Tibetan | Code unknown |

Run `python udhr.py probe` when new candidate codes become available. The
`PROBE_CANDIDATES` dict in `udhr.py` lists the codes already tried.

---

## Options

```
--dir PATH        root output directory (default: docs/udhr/)
--registry PATH   registry JSON file (default: registry.json)
```

---

## Requirements

- Python 2.7+ / 3.x
- `pdftotext` (Poppler) for `--extract` and `extract` subcommands
  - macOS: `brew install poppler`
  - Debian/Ubuntu: `apt install poppler-utils`
  - Not required for `fetch`, `list`, `discover`, `probe`, or `verify`

---

## Source

PDFs are fetched from OHCHR at:

```
https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/{code}.pdf
```

with a fallback to the older path:

```
https://www.ohchr.org/EN/UDHR/Documents/UDHR_Translations/{code}.pdf
```

The tool identifies itself with a `User-Agent` header and observes a 2-second
delay between requests. UDHR translations are freely redistributable; if you
reproduce them, OHCHR asks that you link back to their website as the source.
