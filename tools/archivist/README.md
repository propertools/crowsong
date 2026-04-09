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
followed by the normalised body:

```
# ARCHIVIST   v1.0
# TITLE       Universal Declaration of Human Rights -- Arabic
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

All fields are optional except SHA256. On parsing, unknown header fields
are displayed by `show` and ignored by `verify`. `strip` removes the
header entirely.

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
    --tlp LEVEL         TLP classification (CLEAR/GREEN/AMBER/AMBER+STRICT/RED)
-o, --output FILE       Output file (default: stdout)
    --no-date           Omit stamp date field (for reproducible output)
```

### verify

Check SHA256 integrity of one or more stamped documents.

```bash
# Verify a single file
python archivist.py verify docs/udhr/Arabic/arz_Arabic.txt

# Verify a set of files
python archivist.py verify docs/udhr/CJK/*.txt

# Verify from stdin (e.g. after pipe)
cat stamped.txt | python archivist.py verify -

# Verify a whole directory tree
find docs/udhr docs/texts -name '*.txt' | xargs python archivist.py verify
```

Output:

```
  PASS   docs/udhr/Arabic/arz_Arabic.txt  - UDHR Arabic  (14,732 chars)
  PASS   docs/udhr/CJK/chn_Chinese-Simplified.txt  (8,419 chars)
  FAIL   docs/udhr/Thai/thj_Thai.txt  - SHA256 mismatch
         declared: 3a7f91c2...
         actual:   9b2e04d1...

Results: 2 passed, 1 failed, 0 unstamped
```

Exit code 0 if all verified files pass; 1 if any fail.

### show

Display metadata and verification status. Note that `show` does compute
the SHA256 of the body and reports whether it matches.

```bash
python archivist.py show docs/udhr/Devanagari/hnd_Hindi.txt

find docs/udhr -name '*.txt' | xargs python archivist.py show | grep LANG
```

### strip

Remove the archivist header and recover the normalised body.

```bash
# To stdout
python archivist.py strip stamped.txt

# To file
python archivist.py strip stamped.txt --output original.txt

# In a pipe
python archivist.py strip stamped.txt | wc -l
```

Unstamped files are passed through as normalised text (LF line endings,
UTF-8). This is not a byte-for-byte passthrough.

---

## Round-trip behaviour

Archivist is a **canonical-text** wrapper, not a byte-for-byte wrapper.
During stamping, line endings are normalised to LF and trailing newlines
are stripped. Strip output always ends with exactly one newline. This
means:

- CRLF input becomes LF
- Multiple trailing newlines collapse to one
- Input with no final newline gains one

The hash in the header is computed over this normalised form, so
stamp-then-verify is always consistent. To confirm round-trip:

```bash
# Stamp then verify in one pipe
echo "All human beings are born free." | \
    python archivist.py stamp --title "UDHR Article 1" - | \
    python archivist.py verify -

# Stamp, strip, compare normalised forms
python archivist.py stamp --title "Operational note" note.txt > stamped.txt
python archivist.py verify stamped.txt
python archivist.py strip stamped.txt > recovered.txt
# recovered.txt contains the LF-normalised body with one trailing newline
```

---

## Compatibility

- Python 2.7+ / 3.x
- No external dependencies
- Encoding: UTF-8 throughout; stdin/stdout handled explicitly, not locale-dependent
- Line endings: CRLF normalised to LF before hashing -- safe across platforms

---

## Tests

A canonical test suite is provided in `test_archivist.py`. Run it with:

```bash
python test_archivist.py
python -m pytest test_archivist.py -v   # if pytest is available
```

The suite covers:

- Round-trip integrity (stamp -> parse -> verify) for ASCII and Unicode bodies
- Non-ASCII metadata in all fields (title, author, note) -- Py2 regression
- Line-count correctness: empty body, single line, multi-line
- CRLF, bare CR, and mixed line-ending normalisation
- Multiple trailing newlines collapse to one; no-final-newline gains one
- Empty body stamps, verifies, and produces the known SHA256 constant
- Header-only stamped file (no body section) does not crash
- Unstamped passthrough: plain text, empty file, whitespace-only
- Comment-prefixed files not misidentified as stamped -- detection regression
- Truncated/damaged header (no SHA256 field) correctly flagged as unstamped
- Tampered body correctly fails verification and exposes both hashes
- Field parsing: canonical double-space format and legacy colon fallback
- Malformed colon lines with unknown field names not over-interpreted
- CHARS field matches `len(body)` for ASCII and Unicode content

---

## Changelog

### v1.0 (crowsong-01 pre-release review)

**Correctness fixes**

- `parse()` body extraction: replaced loop-plus-offset-reconstruction with a
  direct `text.split("\n\n", 1)` on the normalised string. Eliminates an entire
  class of structural ambiguity from `splitlines()` offset arithmetic.
- Line counts were off by one for all non-empty bodies. A one-line body
  returned 0; N-line body returned N-1. Fixed by `_line_count()` helper:
  empty string = 0, everything else = `count("\n") + 1`.
- Empty input is now accepted. SHA256 of an empty body is well-defined
  (`e3b0c44...`); there is no protocol reason to reject it.

**Python 2 / 3 compatibility fixes**

- Non-ASCII metadata (`--title`, `--author`, `--note`, etc.) crashed on
  Python 2 with `UnicodeEncodeError` because `str(unicode_value)` attempts
  ASCII encoding. Fixed by `_to_text()` helper used in `_make_header()`.
- `sys.stdout` write path was branched and mixed text/bytes assumptions in
  ways that could fail under redirections or test harnesses. Replaced with
  `_stdout_write_utf8()` which calls `getattr(sys.stdout, "buffer", None)`
  and writes encoded bytes, giving one consistent path for both runtimes.
- `sys.stdin` on Python 3 now uses `sys.stdin.buffer.read().decode("utf-8")`
  rather than relying on locale.
- All file I/O uses `io.open()` directly; the `open = io.open` Py2 alias is
  gone.
- `sub.required = True` is unreliable on Python 2.7 argparse. Replaced with
  `set_defaults(func=...)` on each subparser and `hasattr(args, "func")`
  guard in `main()`.

**Header detection hardening**

- `is_stamped` previously matched any leading comment block containing the
  substring `ARCHIVIST`. Now requires: (1) first non-empty line starts with
  `# ARCHIVIST`, AND (2) a `SHA256` field is present. A truncated or damaged
  header is flagged as unstamped rather than silently verified against nothing.
- An up-front first-line gate short-circuits `parse()` for unstamped files
  without entering header-processing logic at all.

**Field parsing**

- Legacy colon-separator fallback is now restricted to the set of known field
  names. Lines with arbitrary colons (URLs, freeform comments) are no longer
  misinterpreted as metadata fields.
- `VERSION_FIELD` renamed to `MARKER_FIELD` to accurately describe what the
  constant represents (the format-marker field name, not a version number).
- Dead constant `BODY_SEPARATOR = ""` removed.

**CLI and error handling**

- `cmd_show()` now returns exit code 1 if any file fails to read, instead of
  always returning 0. Consistent with `cmd_verify()` behaviour.
- All per-file errors in `verify`, `show`, and `strip` are written to stderr.
- `--no-date` help text corrected from "fetch date" to "stamp date".
- Unused `import os` removed.

**Documentation**

- README and module docstring now clearly state this is a **canonical-text**
  wrapper, not byte-for-byte. Round-trip examples updated accordingly.
- `show` documented as computing and reporting verification status (previously
  claimed "without verifying").
- `strip` passthrough documented as "normalised text, not byte-for-byte".
- Shell globstar examples replaced with portable `find ... | xargs` form.
- Security framing added: archivist provides integrity checking only, not
  cryptographic authenticity or non-repudiation. Explicit note that anyone
  can restamp a document unless an external signing layer is applied.

---

## Integration with Crowsong corpora

The archivist header format is shared across the Crowsong toolchain:

| Tool | Uses archivist format |
|------|-----------------------|
| `tools/texts/texts.py` | SHA256 header on all Gutenberg texts |
| `tools/udhr/udhr.py` | SHA256 header on extracted UDHR texts |
| `tools/archivist/archivist.py` | General-purpose stamping and verification |

Any file stamped by one tool can be verified by another. The format is
intentionally minimal -- a text editor and a SHA256 calculator are
sufficient to verify by hand.

---

## Design notes

**Why plain text headers?** Because the document must be readable without
software. A border agent, a relay operator, a future archivist with no
access to this codebase -- all can read the header, extract the body, and
verify the hash using any SHA256 tool. The format is its own documentation.

**Why SHA256 over the body only?** So the header fields (title, author,
date) can be amended without invalidating the hash. The body is what
matters. The header is metadata.

**Why CRLF normalisation?** Because the same document travelling through
different operating systems and transmission channels will acquire different
line endings. The hash must be stable. Normalise first, always.

**What archivist does NOT provide:** Archivist provides content integrity
checking, not cryptographic authenticity. A SHA256 in the header proves
that the current body matches the declared digest -- it does not prove who
created the document or that the header has not been replaced. If
authenticity or non-repudiation is required, layer an external signing
mechanism (e.g. GPG) on top of the stamped file.

**TLP support:** the Traffic Light Protocol classification field is a
declaration, not enforcement. The archivist records what you declare; it
does not restrict distribution. Operators are responsible for honouring
the declared classification.
