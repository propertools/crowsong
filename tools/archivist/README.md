# archivist

Self-describing document framing tool.

Wraps any plain text document in a self-describing header containing
SHA256, metadata, and provenance. The result is a single plain-text file
that carries its own verification credentials and can be read by any text
editor, transmitted over any channel, and verified offline without a
database, manifest, or network connection.

The archivist doesn't care what your document contains. It will stamp it,
hash it, and file it. It will also tell you, quietly and without drama, if
someone has tampered with it since.

---

## Format

A stamped document consists of a header block followed by a blank line
followed by the original body:

```
# ARCHIVIST   v1.0
# TITLE       Universal Declaration of Human Rights — Arabic
# AUTHOR      OHCHR
# LANG        ar
# SOURCE      https://www.ohchr.org/
# DATE        2026-04-06
# TLP         CLEAR
# CHARS       14,732
# LINES       312
# SHA256      3a7f91c2b04e8d6f1a2b3c4d5e6f7890...

[document body]
```

The SHA256 is computed over the body only, after CRLF normalisation to LF.
This matches the format used by `tools/texts/texts.py` and
`tools/udhr/udhr.py`, making archivist-stamped files round-trip compatible
with both corpora.

All fields are optional except SHA256. Unknown fields are preserved by all
subcommands.

---

## Usage

```
python archivist.py stamp   [options] [file]
python archivist.py verify  [file ...]
python archivist.py show    [file ...]
python archivist.py strip   [file ...]
```

### stamp

Wrap a document in an archivist header.

```bash
# Stamp a file
python archivist.py stamp --title "Signal Survives" --author "T. Darley" \
    --source "propertools.be" document.txt

# Stamp from stdin
echo "Signal survives." | python archivist.py stamp --title "Test" -

# Stamp with TLP classification and write to file
python archivist.py stamp \
    --title "Field Note #9" \
    --author "Trey Darley" \
    --source "propertools.be/field-notes/9" \
    --tlp CLEAR \
    --tags "crowsong,fds,field-note" \
    --output field-note-9-stamped.txt \
    field-note-9.txt
```

Options:

```
-t, --title TITLE       Document title
-a, --author AUTHOR     Author name
-s, --source SOURCE     URL or bibliographic reference
-n, --note NOTE         Freeform annotation
-l, --lang LANG         Language / script (e.g. en, ar, zh-Hans)
-T, --tags TAGS         Comma-separated tags
    --tlp LEVEL         TLP classification (CLEAR/GREEN/AMBER/RED)
-o, --output FILE       Output file (default: stdout)
    --no-date           Omit date field (for reproducible output)
```

### verify

Check SHA256 integrity of one or more stamped documents.

```bash
# Verify a single file
python archivist.py verify docs/udhr/Arabic/arz_Arabic.txt

# Verify everything in a directory
python archivist.py verify docs/udhr/CJK/*.txt

# Verify from stdin (e.g. after pipe)
cat stamped.txt | python archivist.py verify -

# Verify the whole corpus
python archivist.py verify docs/udhr/**/*.txt docs/texts/**/*.txt
```

Output:

```
  PASS   docs/udhr/Arabic/arz_Arabic.txt  — UDHR Arabic  (14,732 chars)
  PASS   docs/udhr/CJK/chn_Chinese-Simplified.txt  (8,419 chars)
  FAIL   docs/udhr/Thai/thj_Thai.txt  — SHA256 mismatch
         declared: 3a7f91c2...
         actual:   9b2e04d1...

Results: 2 passed, 1 failed, 0 unstamped
```

Exit code 0 if all verified files pass; 1 if any fail.

### show

Display metadata without verifying. Useful for inspection and scripting.

```bash
python archivist.py show docs/udhr/Devanagari/hnd_Hindi.txt

python archivist.py show docs/udhr/**/*.txt | grep LANG
```

### strip

Remove the archivist header and recover the original body.

```bash
# To stdout
python archivist.py strip stamped.txt

# To file
python archivist.py strip stamped.txt --output original.txt

# In a pipe
python archivist.py strip stamped.txt | wc -l
```

Unstamped files are passed through unchanged.

---

## Round-trip examples

```bash
# Stamp then verify in one pipe
echo "All human beings are born free." | \
    python archivist.py stamp --title "UDHR Article 1" - | \
    python archivist.py verify -

# Stamp, transmit (e.g. via fax or relay), strip, verify body
python archivist.py stamp --title "Operational note" note.txt > stamped.txt
# ... transmit stamped.txt ...
python archivist.py verify stamped.txt
python archivist.py strip stamped.txt > recovered.txt
diff note.txt recovered.txt  # empty — exact round-trip
```

---

## Compatibility

- Python 2.7+ / 3.x
- No external dependencies
- Encoding: UTF-8 throughout
- Line endings: CRLF normalised to LF before hashing — safe across platforms

---

## Integration with Crowsong corpora

The archivist header format is shared across the Crowsong toolchain:

| Tool | Uses archivist format |
|------|-----------------------|
| `tools/texts/texts.py` | ✅ SHA256 header on all Gutenberg texts |
| `tools/udhr/udhr.py` | ✅ SHA256 header on extracted UDHR texts |
| `tools/archivist/archivist.py` | ✅ General-purpose stamping and verification |

Any file stamped by one tool can be verified by another. The format is
intentionally minimal — a text editor and a SHA256 calculator are sufficient
to verify by hand.

---

## Design notes

**Why plain text headers?** Because the document must be readable without
software. A border agent, a relay operator, a future archivist with no access
to this codebase — all can read the header, extract the body, and verify the
hash using any SHA256 tool. The format is its own documentation.

**Why SHA256 over the body only?** So the header fields (title, author, date)
can be amended without invalidating the hash. The body is what matters. The
header is metadata.

**Why CRLF normalisation?** Because the same document travelling through
different operating systems and transmission channels will acquire different
line endings. The hash must be stable. Normalise first, always.

**TLP support:** the Traffic Light Protocol classification field is a
declaration, not enforcement. The archivist records what you declare; it does
not restrict distribution. Operators are responsible for honouring the
declared classification.
