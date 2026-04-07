# Crowsong Issue Tracker

Issues live here, with the code and the specs, not in a Microsoft-owned
SaaS database. This file is the authoritative bug and task registry for
the Crowsong protocol suite.

## How to use this file

**To claim an issue:** add your initials and a timestamp to the `Claimed`
field. One person per issue. If you abandon it, clear the field so
someone else can pick it up.

**To close an issue:** change `Status` to `closed`, add the `Closed`
date, and add a one-line note and the commit hash that fixed it.

**To open a new issue:** copy the template below, assign the next ID in
the relevant section, fill in the fields, set `Status: open`.

**Severity levels:** `critical` · `high` · `medium` · `low` · `trivial`

**Status values:** `open` · `claimed` · `closed` · `wontfix` · `deferred`

---

## Template

```
### XXX-NNN — Short descriptive title
| Field    | Value |
|----------|-------|
| Severity | |
| Status   | open |
| Claimed  | — |
| Opened   | YYYY-MM-DD |
| Closed   | — |
| Commit   | — |

**Description:**

**Fix:**
```

---

## archivist.py

### ARCH-001 — No `--version` flag
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The tool embeds `v1.0` in every document it stamps via
the `ARCHIVIST` header field, but there is no `--version` CLI flag to
query the running version.

**Fix:** Add `parser.add_argument('--version', action='version',
version='%(prog)s 1.0')` to `build_parser()`.

---

### ARCH-002 — SHA256 implementation duplicated across toolchain
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `archivist.py`, `udhr.py`, and `texts.py` each implement
their own `_sha256()` and `_normalise()` functions. Currently identical,
but will drift. The SHA256 header unification audit is already flagged as
pending for -01.

**Fix:** Extract to a shared `crowsong/hash.py` module. All three tools
import from it.

---

### ARCH-003 — Blank comment line in header may cause early parse termination
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `parse()` header detection breaks on the first non-`# `
line after entering header mode. A bare `#` line is handled by the
`or line == "#"` guard, but the interaction with the body_start
blank-line scan deserves an explicit test.

**Fix:** Add test case: stamped document where header contains a bare
`#` line. Verify body is correctly recovered.

---

## baseconv.py

### BCONV-001 — No zero-padding support in `from_int()` / `convert()`
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The CCL stack operates on WIDTH/5 zero-padded tokens
(e.g. `00083`). `from_int(83, 10)` returns `"83"`, not `"00083"`.
Anyone using `baseconv.py` for FDS token manipulation will get incorrect
output without additional padding logic.

**Fix:** Add optional `width=None` parameter to `from_int()` and
`convert()`. When set, output is left-padded with zeros to the specified
width. Raise `ValueError` if the converted value exceeds the requested
width.

```python
def from_int(value, base, width=None):
    ...
    result = "".join(out)
    if width is not None:
        if len(result) > width:
            raise ValueError(
                "value {0} in base {1} exceeds width {2}".format(
                    value, base, width))
        result = result.zfill(width)
    return result
```

---

### BCONV-002 — Dangling README reference to `mnemonic-shamir-sketch.md`
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** README references `docs/mnemonic-shamir-sketch.md`.
Verify this file exists; if not, the reference is dangling.

**Fix:** Either create the stub or update the reference to the correct
path.

---

### BCONV-003 — Double base validation in `convert()`
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `convert()` calls `to_int()` then `from_int()`, both of
which call `_validate_base()`. The from_base and to_base are each
validated twice. Not harmful; defensive validation is fine.

**Fix:** Optionally validate both bases at the top of `convert()` and
remove the internal calls, or leave as-is.

---

## mnemonic-shamir-sketch.md

### SKETCH-001 — Leading zeros in UCS-DEC integer interpretation underspecified
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** "Strip whitespace, concatenate token values, treat as
decimal literal" is ambiguous when the first token has leading zeros
(e.g. `00072 00101` → `0007200101` → `7200101` as a decimal literal).
This affects prime derivation deterministically but asymmetrically across
scripts — low code points (ASCII) are more likely to produce leading
zeros in the first token than high code points (CJK).

**Fix:** Add explicit statement: "Leading zeros in the concatenated token
stream are stripped before integer interpretation. This is canonical and
expected. The resulting integer is identical to
`int(concatenated_tokens, 10)`."

---

### SKETCH-002 — KDF status inconsistency between status table and open questions
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The status table marks KDF as ✅ resolved. Open question
§1 lists iteration count as still open. A reader scanning the table will
assume fully resolved.

**Fix:** Split the status table entry into two rows: "KDF algorithm"
(✅) and "KDF iteration count" (🔄).

---

### SKETCH-003 — Sparse addressing coverage floor urgency underframed
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The Barking Floyd test shows 4.5% coverage (24 positions
from a 77-digit prime, k=3). Open question §4 acknowledges this is
unresolved but frames it as deferred. For a construction used as key
material extraction, 4.5% is thin and the minimum safe threshold needs a
number before -01.

**Fix:** Add explicit coverage floor analysis to definition of done.
Block -01 on this. Candidate threshold: minimum 15% coverage, or minimum
64 bits of extracted material, whichever is larger.

---

### SKETCH-004 — Dangling reference to `docs/mnemonic/gloss-README.md`
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** Document references `docs/mnemonic/gloss-README.md`.
This may be the same file as `docs/mnemonic/README.md` (now unified) or
a separate file.

**Fix:** Verify path. If file is `docs/mnemonic/README.md`, update all
references accordingly.

---

## constants.py

### CONST-001 — Verify truncation bypass in `cmd_verify()`
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `cmd_verify()` sets `count = len(digits)` from the
file, then calls `get_digits(key, count)`. If the file is corrupt in a
way that silently drops digit characters, `count` will be less than
`count_declared`, `get_digits()` recomputes the shorter prefix, and
`digits_ok` reports True on a truncated file.

**Fix:**
```python
if parsed["count_declared"] is not None and len(digits) != parsed["count_declared"]:
    print("Verification: FAIL — digit count mismatch "
          "(declared {0}, found {1})".format(parsed["count_declared"], len(digits)))
    return 1
```

---

### CONST-002 — MM₇ absent from constants registry
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `mnemonic-shamir-sketch.md` lists MM₇ (Serafina
Tauform, Édouard Lucas's 1876 double Mersenne prime) in the named
constants table as an IV source. It is absent from `constants.py`.
MM₇ is a finite integer, not a transcendental, so `mpmath` is not
needed.

**Fix:** Add MM₇ as a special-cased finite constant (return the
integer's digit string directly, no mpmath required), or add an explicit
comment noting the omission and the reason. She deserves to be in the
registry.

---

### CONST-003 — README bash loop omits `sqrt5`
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The README generation loop reads
`for name in pi e phi sqrt2 sqrt3 ln2 apery` — omits `sqrt5`, which is
in the registry and the constants table.

**Fix:** `for name in pi e phi sqrt2 sqrt3 sqrt5 ln2 apery`

---

## gitbundle.py

### GIT-001 — `subprocess.DEVNULL` not available in Python 2.7
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_find_git()` uses `stderr=subprocess.DEVNULL`, added
in Python 3.3. On Python 2.7 this raises `AttributeError` at backend
detection time, causing the entire tool to fail at import.

**Fix:**
```python
devnull = open(os.devnull, 'wb')
subprocess.check_output(["git", "--version"], stderr=devnull)
```

---

### GIT-002 — `_dulwich_create()` hardcodes `refs/heads/main`
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_dulwich_create()` sets
`b.references = {b"refs/heads/main": head}` unconditionally. Repos using
`master` or any other branch name will silently bundle the wrong ref.

**Fix:**
```python
head_ref = r.refs.get_symrefs().get(b"HEAD", b"refs/heads/main")
b.references = {head_ref: head}
```

---

### GIT-003 — `os.makedirs` PY2 compat block is fragile
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The inline ternary for `os.makedirs` in
`_git_unbundle()` uses a load-bearing `else None`. Not a correctness bug
currently but easy to break on modification.

**Fix:**
```python
if not os.path.exists(into):
    os.makedirs(into)
```

---

### GIT-004 — dulwich unbundle limitation undocumented in README
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** README implies dulwich is a full fallback for all
operations. `cmd_unbundle()` with dulwich hard-fails with "unbundle
requires system git." This asymmetry is not mentioned in the README.

**Fix:** Add to README dependency table: "unbundle requires system git;
dulwich fallback not yet implemented for this subcommand."

---

### GIT-005 — `create` silently bundles HEAD only; multi-branch repos lose refs
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `create` bundles only `HEAD`. Repos with multiple
branches silently drop everything except HEAD. Acceptable for the
Crowsong release branch use case, but undocumented.

**Fix:** Add note to README and `--help`: "Bundles HEAD only. Use
`git bundle create` directly for multi-branch bundles."

---

## mnemonic.py

### MNEM-001 — `text_type` definition contains dead code
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `text_type = bytes if False else (str if not PY2 else
type(u""))` — the `bytes if False` branch is unreachable and confuses
readers.

**Fix:**
```python
if PY2:
    text_type = unicode  # noqa: F821
else:
    text_type = str
```

---

### MNEM-002 — `derive_from_melody()` undocumented in README exports table
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `mnemonic.py` exports `derive_from_melody()` and related
melody functions but the README only lists `is_prime`, `next_prime`,
`ucs_dec_encode`, and `derive`.

**Fix:** Either add melody functions to the exports table, or move to
`tools/mnemonic/melody.py` and import from there.

---

### MNEM-003 — `midi` representation silently converts to intervals; no test
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `derive_from_melody(midi=[...])` converts MIDI pitches
to intervals before hashing, making the construction
transposition-invariant. Documented but has no explicit test.

**Fix:** Add test: `derive_from_melody(midi=[60,62,64])` and
`derive_from_melody(midi=[62,64,66])` produce the same prime.

---

## verse_to_prime.py

### VTP-001 — CRC32 check fragile under line-wrapping in transit
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `cmd_verify()` collects payload lines via
`"\n".join(payload_lines)` and computes CRC32 over that string. The
original CRC was computed over `prime_tokens` (a single space-separated
string with no newlines). If the artifact is reformatted in transit
(line-wrapped by a fax relay or text editor), the CRC fails even though
the token values are intact. This is directly in the fax/relay use case.

**Fix:** Normalise before CRC: strip all whitespace from payload tokens,
rejoin as a canonical space-separated string, compute CRC over that.
Match the generation-time computation exactly.

---

## prime_twist.py / symbol_twist.py / verse_to_prime.py

### TWIST-001 — Bare `unicode` reference in `_read_stdin()` without PY2 guard
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_read_stdin()` in `prime_twist.py`, `symbol_twist.py`,
and `verse_to_prime.py` contains `if not isinstance(data, unicode)` with
only a `# noqa: F821` suppression. On Python 3 this raises `NameError`
if the code path is reached. `text_type` is already defined in each file.

**Fix:** Replace `unicode` with `text_type` in all three
`_read_stdin()` functions. One-character-class change per file.

---

## crowsong-advisor.py

### ADV-001 — Duplicate gloss alphabet derivation vs. gloss_twist.py
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `crowsong-advisor.py` implements `_make_gloss_alpha()`
independently of `gloss_twist.py`'s `_prime_to_alphabet()`. Both use the
same construction but are separate implementations that will drift.

**Fix:** Import `_prime_to_alphabet` from `gloss_twist` in the advisor,
or extract to `mnemonic.py`. Consistent with ARCH-002.

---

## symbol_twist.py

### SYM-001 — Full bijection construction documented but not implemented
| Field    | Value |
|----------|-------|
| Severity | high |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The module docstring and README describe a "keyed
Fisher-Yates bijection over 62,584 eligible Unicode code points" as the
primary construction for script fingerprint resistance. The actual
implementation only provides the `deepcut-v1` 10-symbol digit-substitution
alphabet. The bijection is entirely absent. A user expecting script
fingerprint resistance from the bijection construction will not get it.

**Fix:** Either implement the bijection construction (enumerate eligible
code points, keyed Fisher-Yates shuffle, map token values directly) or
update the documentation to clearly state that only `deepcut-v1` is
currently implemented and the bijection is planned.

---

## primes.py

### PRIME-001 — Duplicate `is_prime` / `next_prime` vs. `mnemonic.py`
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `primes.py` implements `is_prime()` and `next_prime()`
independently of `mnemonic.py`. Witness sets are currently identical.
Standalone utility design is intentional, but drift risk is real.

**Fix:** Add a comment explicitly noting that the witness set must be
kept in sync with `mnemonic.py:WITNESSES_SMALL`. Consider a CI check.
Do not import from `mnemonic.py` — standalone utility should remain
dependency-free.

---

### PRIME-002 — README describes output as "table" but output is one-per-line
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** README says `primes first 10000` generates "a printed
quick-reference table." `generate_first_primes()` yields one prime per
line — 10,000 unformatted lines. "Table" implies grouped output.

**Fix:** Either add a `--format table` option, or update the README to
say "list" instead of "table."

---

### PRIME-003 — No `verify` subcommand for generated prime files
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `constants.py` includes SHA256 verification for
generated constant files. `primes.py` has no equivalent. For the Vesper
archive use case, this is an inconsistency.

**Fix:** Add `python primes.py verify <file>` that recomputes and checks
a declared SHA256 header if present. Consistent with archivist format.

---

## quickref.py

### QREF-001 — `write_out()` uses `open()` with `encoding=` kwarg, not PY2-compatible
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `write_out()` calls `open(outfile, "w", encoding="utf-8")`.
Python 2.7's `open()` does not accept `encoding=` and raises `TypeError`.
`io` is not imported. This breaks the most common use case (`--output FILE`).
The same issue exists in `sequences.py` (two occurrences) and `udhr.py`
(three occurrences). `texts.py` already has the correct pattern — use it
as the template (`open = io.open` in the PY2 branch).

**Fix:** Add `import io` and replace with `io.open()` throughout.

---

### QREF-002 — `range` command does not validate `start <= end`
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** A reversed range silently produces an empty card with
no error message.

**Fix:**
```python
if s > e:
    print("Error: start must be <= end", file=sys.stderr)
    return 1
```

---

### QREF-003 — Bare `except: pass` in `assigned()` swallows all exceptions
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `assigned()` uses a bare `except: pass` which swallows
`KeyboardInterrupt` and `SystemExit`.

**Fix:** Replace with `except (ValueError, TypeError): pass`.

---

### QREF-004 — README states 53 blocks but BLOCKS list has 59 entries
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** README says "53 Unicode blocks across all planes." The
`BLOCKS` list has 59 entries (the `deepcut` tag blocks were added after
the README was written).

**Fix:** Update README block count to match actual `len(BLOCKS)`.

---

### QREF-005 — Dead import: `binascii` imported but never used
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `import argparse, binascii, sys, time, unicodedata` —
`binascii` is not used anywhere in `quickref.py`.

**Fix:** Remove `binascii` from the import line.

---

## sequences.py

### SEQ-001 — Dead URL construction in `fetch_bfile()`
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `fetch_bfile()` constructs the b-file URL twice — the
first assignment (with `lstrip("0")`) is immediately overwritten by the
second. The first line is dead code with a misleading comment.

**Fix:** Remove the first URL assignment and the misleading comment.

---

### SEQ-002 — `open()` with `encoding=` kwarg not PY2-compatible (two occurrences)
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `parse_sequence_file()` and `cmd_sync()` both use
`open(path, encoding="utf-8")`. Python 2.7 raises `TypeError`. `io` is
not imported. See QREF-001 for the codebase-wide pattern.

**Fix:** Add `import io` and replace with `io.open()`.

---

### SEQ-003 — `sync --all` without `--force` is identical to `sync`
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `cmd_sync()` has two consecutive skip checks. When
`sync_all=True` and `force=False`, the second check skips all
already-cached files, making `sync --all` identical to `sync`. README
says `--all` syncs "all sequences in registry, even if cached" — the
implementation contradicts this.

**Fix:** Either remove the second skip check when `sync_all=True`
(making `--all` re-fetch everything), or update the README to state
that `--all` still skips cached files (requiring `--force` to re-fetch).
Pick one semantic and enforce it.

---

### SEQ-004 — `cmd_verify()` silent on missing cache directory
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** When `out_dir` doesn't exist, `cmd_verify()` silently
prints "No cached sequences to verify" rather than informing the user
the directory is missing.

**Fix:**
```python
if not os.path.isdir(out_dir):
    print("Error: cache directory does not exist: {0}".format(out_dir),
          file=sys.stderr)
    return 1
```

---

### SEQ-005 — No `--count` option on `sync` for term count control
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `sync` fetches whatever the OEIS b-file provides. For
the Vesper/IV use case where exactly N digits of a constant are needed,
there is no way to request a specific term count.

**Fix:** Add `--count N` to `sync`, truncating the term list to exactly
N terms after fetch.

---

## texts.py

### TEXT-001 — `make_text_file()` renders `gutenberg_id: None` literally
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** For `stapledon-starmaker` (and any future entry with
`gutenberg_id: None`), `make_text_file()` renders `Project Gutenberg
#None` and `https://www.gutenberg.org/ebooks/None` in the header.

**Fix:**
```python
if local_meta.get("gutenberg_id"):
    lines.append("# Source:    Project Gutenberg #{gutenberg_id}".format(**local_meta))
elif local_meta.get("url"):
    lines.append("# Source:    {url}".format(**local_meta))
```

---

### TEXT-002 — `parse_text_file()` body detection fragile on blank line handling
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** Body detection relies on finding the first non-`#` line
after the header. If the blank separator line is ever omitted or doubled
in transit, `in_header` goes False on the wrong line and SHA256 fails
silently.

**Fix:** Use a more robust sentinel — detect the last `#`-prefixed line
explicitly, rather than the first non-`#` line.

---

### TEXT-003 — Dead import: `re` imported but never used
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `import re` appears in the imports but `re` is not used
anywhere in `texts.py`.

**Fix:** Remove the `re` import.

---

## ucs_dec_tool.py

### UCS-001 — Bare `unicode` reference in `_read_stdin()`
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_read_stdin()` uses `if not isinstance(data, unicode)`
with `# noqa: F821`. On Python 3, `unicode` is undefined and raises
`NameError` if reached. `text_type` is already defined. See TWIST-001.

**Fix:** Replace `unicode` with `text_type`.

---

### UCS-002 — Silent empty decode when header found but payload empty
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** If `parse_frame()` finds a header but `payload_str` is
empty (truncated artifact, transmission error), `decode()` returns an
empty string with no warning. The `--decode` path silently produces no
output and exits 0.

**Fix:**
```python
if parsed["header_found"] and not parsed["payload_str"].strip():
    print("Warning: frame header found but payload is empty",
          file=sys.stderr)
```

---

### UCS-003 — CRC32 mismatch risk between `frame()` and `verify_frame()`
| Field    | Value |
|----------|-------|
| Severity | high |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `frame()` computes CRC32 over `payload.strip()`.
`verify_frame()` computes CRC32 over `parsed["payload_str"].strip()`
where `payload_str = "\n".join(payload_lines)`. If `encode()` produces
rows with trailing spaces (the `"  ".join(chunk)` pattern does), the
strip behaviour at verify time may differ from generation time after
transmission through a channel that modifies trailing whitespace. This is
a latent mismatch that surfaces in exactly the fax/relay use case the
tool was built for.

**Fix:** Normalise both sides to the same canonical form before CRC
computation: strip each row individually, then rejoin. Document the
canonical form explicitly in the spec.

---

### UCS-004 — `parse_frame()` called unconditionally on encode path
| Field    | Value |
|----------|-------|
| Severity | trivial |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `parsed = parse_frame(data)` is called at the top of
`main()` regardless of mode. On `--encode` the parse result is unused.

**Fix:** Move `parsed = parse_frame(data)` inside the `--decode` and
`--verify` branches only.

---

## udhr.py

### UDHR-001 — `open()` with `encoding=` kwarg not PY2-compatible
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_load_registry()`, `_save_registry()`, and
`_extract_text()` all use `open(..., encoding="utf-8")`. Python 2.7
raises `TypeError`. `io` is not imported. See QREF-001.

**Fix:** Add `import io` and replace with `io.open()`.

---

### UDHR-002 — `subprocess.DEVNULL` not available in Python 2.7
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `_extract_text()` uses `stderr=subprocess.DEVNULL`.
Same issue as GIT-001.

**Fix:** Replace with `open(os.devnull, 'wb')` as the stderr target.

---

### UDHR-003 — `cmd_discover()` hard-fails rather than falling back to bootstrap
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** When OHCHR scraping fails, `cmd_discover()` returns 1
with "Could not retrieve language list from OHCHR." The bootstrap
registry (48 languages) is available but not used as a fallback.

**Fix:** Fall back to bootstrap registry with a note: "Network
unavailable; using built-in bootstrap (48 languages). Run discover again
when connected."

---

### UDHR-004 — Registry outer key vs. inner `code` field distinction undocumented
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** Several registry entries have outer key ≠ inner `code`
field (e.g. `"bul": {"code": "blg", ...}`). Correct and intentional but
unexplained. New contributors will be confused.

**Fix:** Add to README: "The outer key is the registry identifier; `code`
is the OHCHR internal code used to construct the PDF URL. These may
differ."

---

## entropy-analysis-howto.md

### HOWTO-001 — UDHR file paths don't match actual directory layout
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The howto references files as `docs/udhr/ara.txt` (flat
filenames). The actual layout is `docs/udhr/Arabic/arz_Arabic.txt`. A
new contributor following the howto will get file-not-found errors on
every command.

**Fix:** Update all file path references to match the actual directory
layout.

---

### HOWTO-002 — `udhr.py analyse --all` subcommand referenced but not implemented
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The howto references `python tools/udhr/udhr.py analyse
--all`. The `analyse` subcommand does not exist in `udhr.py`.

**Fix:** Either implement the `analyse` subcommand, or update the howto
to use the correct manual pipeline shown later in the document.

---

### PRIME-CHAIN-002 — VALUE-SPACE EXPANDER: Gloss variant for WIDTH/3 BINARY entropy ceiling attack
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-07 |
| Closed   | — |
| Commit   | — |

**Background:**

WIDTH/3 BINARY + mod3 CCL achieves H_post = 8.87–8.93 bits/token
across 37 languages and all compressors (Void's results, April 2026).
The ceiling is not the algorithm — it is the input distribution.
Compressed binary has 256 distinct byte values. After CCL, unique
token count reaches ~643. The theoretical ceiling for a uniform
distribution over 643 values is log₂(643) ≈ 9.33. The hard WIDTH/3
ceiling is log₂(1000) = 9.97. The gap between current results and
the hard ceiling is approximately 1 bit/token.

**The insight:**

The Gloss layer was designed to solve a structurally similar problem:
CCL feasibility was capped by the input value distribution (CJK tokens
clustered at high code points where few bases are feasible). The
solution was a value-space re-encoding that moved tokens into a range
where CCL could work effectively.

For WIDTH/3 BINARY the problem is different but related: the output
distribution is non-uniform across the 1000 possible token values
(000–999). Closing the gap to the 9.97 ceiling requires making the
distribution more uniform — more distinct token values, more evenly
distributed.

**Proposed construction: Gloss-W3 (working name)**

A WIDTH/3-specific value-space expander, keyed from the same prime
as CCL (reversed digits, same pattern as the existing Gloss layer):

```
compressed binary payload
  → WIDTH/3 encode              (256 distinct values → tokens 000–255)
  → Gloss-W3                    (value-space expansion, key = rev(P))
  → prime-chain twist           (walk-based schedule, standard)
  → mod3 CCL stack              (100% twist rate, bases 7/8/9)
  → artifact
```

**Gloss-W3 construction:**

The existing Gloss layer maps each token value V to a 3-token
base-52 representation in the ASCII letter range (65–122). This
*narrows* the value space (58 distinct values per output token vs
256 input values) and is therefore wrong for this use case.

Gloss-W3 instead maps each WIDTH/3 input token (000–255) to a
deterministically selected token in the range 000–999, using a
keyed permutation of the full WIDTH/3 token space:

```
key ← reversed digits of prime P (same as Gloss layer pattern)
permutation ← Fisher-Yates shuffle of [000..999] seeded from SHA256(key)
Gloss-W3(V) = permutation[V]
```

Properties:
- Bijection from {000..255} → {000..999} (injective, not surjective)
- Keyed: different primes produce different permutations
- Reversal: inverse permutation, trivially computable from key
- Value-space: 256 input values now occupy 256 positions scattered
  across the full 000–999 range, rather than clustered at 000–255
- Distribution: the 256 selected positions are determined by the key,
  not by the byte values — positions are pseudo-random across 000–999

After Gloss-W3, the token stream still has 256 distinct values, but
they are distributed across the full WIDTH/3 space rather than
clustered at the low end. CCL mod3 then applies to a distribution
that is already spread across the full token vocabulary.

**Why this might raise the ceiling:**

mod3 CCL re-expresses each token in base 7, 8, or 9. The output
value of a token T expressed in base b is a function of both T and b.
If input tokens are clustered at 000–255, the output values after
base conversion are also clustered — high values (256–999) are
underrepresented in the output even after CCL. If input tokens are
scattered across 000–999 via Gloss-W3, the output after base
conversion is more uniformly distributed across the full WIDTH/3
output vocabulary.

The hypothesis: Gloss-W3 + prime-chain + mod3 pushes unique token
count beyond 643 and H_post meaningfully above 8.93, toward the
9.97 ceiling.

**What to measure:**

Add to `scripts/w3-entropy-bench.sh`:

```bash
# Pipeline variant: Gloss-W3 + prime-chain + mod3
cat compressed_payload \
    | python tools/ucs-dec/ucs_dec_tool.py --encode --binary \
    | python tools/mnemonic/gloss_twist.py gloss-w3 \
        --verse verses.txt \
    | python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt \
        --schedule prime-chain \
    | python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt \
        --schedule mod3 --width 3 \
    > artifact.txt
```

Report H_post, unique token count post-CCL, and delta vs baseline
mod3 results. Run across the same 37-language UDHR PDF corpus as
Void's original benchmark.

**Acceptance criterion:**

H_post > 8.93 bits/token on at least one compressor/language
combination, with unique token count > 643. If the hypothesis is
correct, results should cluster above the current ceiling across
most of the corpus.

**Implementation required:**

1. `gloss_twist.py`: add `gloss-w3` subcommand
   - `Fisher-Yates permutation of [0..999] seeded from SHA256(rev(P))`
   - `gloss-w3` and `ungloss-w3` subcommands
   - RSRC block: `LAYER: gloss-w3/1`

2. `prime_twist.py`: implement `prime-chain/1` schedule
   (see PRIME-CHAIN-001)

3. `w3-entropy-bench.sh`: add Gloss-W3 + prime-chain + mod3 pipeline
   variant alongside existing benchmarks

**Note for Void:**

This is the next research direction after the WIDTH/3 mod3 results.
The current ceiling (~8.93) is real and bounded by input distribution,
not algorithm. Gloss-W3 is the proposed mechanism to attack that
ceiling by spreading the input distribution across the full WIDTH/3
token vocabulary before CCL runs. Prime-chain is the proposed
mechanism to make the per-position schedule less characterisable.
The combination has not been empirically tested. This issue captures
the design so the hypothesis can be evaluated.

The key insight: same structural pattern as the existing Gloss layer
(reversed prime digits → keyed permutation → value-space
transformation), applied to the WIDTH/3 domain instead of the
WIDTH/5 non-Latin script domain. One design pattern, two applications.

**Blocking:** PRIME-CHAIN-001 (prime-chain schedule implementation)

---

## prime_twist.py — prime-chain schedule

### PRIME-CHAIN-001 — Implement prime-chain/1 schedule variant
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-07 |
| Closed   | — |
| Commit   | — |

**Description:** The standard CCL schedule wastes ~20% of key schedule
positions — digits 0 and 1 fall back to base 10 and produce no twist.
The prime-chain schedule repurposes these digits as prime hop triggers:

- `d = 0` → hop to next_prime(Pₐ); draw base from destination prime's
  digit at current position; apply twist; update active prime
- `d = 1` → hop to prev_prime(Pₐ) (subject to floor rule); draw base
  from destination prime's digit at current position; apply twist;
  update active prime
- `d = 2–9` → twist in place using current prime, base = d (as standard)

Every digit drives real work. Hop positions are invisible in the
twist-map — the base drawn from the destination prime is
indistinguishable from an in-place twist of the same base. The walk
is fully deterministic from the seed prime P₀ and requires no
additional key material.

**Spec:** `docs/ccl-prime-chain-spec.md` (pre-normative)

**Fix:** Implement `prime-chain/1` as a new `--schedule` option in
`prime_twist.py`, alongside the existing `standard` and `mod3` schedules.

Required additions to `prime_twist.py`:
- `prev_prime(n)` function (symmetric to `next_prime`)
- `WALK_FLOOR` constant (smallest prime > 2^255)
- `_chain_schedule_step(Pa, pos)` → (base, new_Pa)
- `stack --schedule prime-chain` support
- RSRC block: `SCHEDULE: prime-chain/1`

Required additions to `mnemonic.py`:
- `prev_prime(n)` export (mirrors `next_prime`)

**Canonical test vector:** to be generated after implementation using
K1 verse and `archive/second-law-blues.txt`. Commit to
`archive/second-law-blues-prime-chain.txt`.

**Verification:** roundtrip test — encode with prime-chain/1, decode,
diff against original. CRC32 must match. Walk must be deterministic
across two independent implementations.

---

## Pipeline composability (stdin / stdout / tee)

The Crowsong toolchain is designed to be composable via Unix pipelines.
All tools that read encoded data MUST accept stdin. All tools that write
encoded data MUST write to stdout. The following issues break this
contract and must be resolved before the full encode→camouflage→decode
pipeline works without temporary files.

### PIPE-001 — `encode-stream` accepts only bare token streams; drops CCL stack structure
| Field    | Value |
|----------|-------|
| Severity | high |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `encode-stream` is fed the entire CCL stack artifact
(including `=== CCL STACK BEGIN ===` markers, RSRC blocks, box borders)
but only knows how to encode numeric token lines. Structural lines are
silently dropped or fail corpus lookup. Result: 1,915 tokens fed in,
only 1,620 words written to payload. Twist-maps are lost, making CCL
reversal impossible.

**Fix (Option B — recommended):** Require bare token streams into
`encode-stream`. Document that callers must pipe through
`prime_twist.py unstack -` first to strip stack structure. Each tool
does one thing. Add to `encode-stream` help text: "Input must be a bare
UCS-DEC token stream. If starting from a CCL stack artifact, pipe
through `prime_twist.py unstack -` first."

---

### PIPE-002 — `prime_twist.py unstack` does not accept stdin (`-`)
| Field    | Value |
|----------|-------|
| Severity | high |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `prime_twist.py unstack` requires a file path argument.
It cannot read from stdin, so it cannot participate in a pipeline without
a temporary file. This breaks the composability contract. Pattern already
used correctly in `archivist.py` and `ucs_dec_tool.py`.

**Fix:**
```python
# In cmd_unstack():
if args.infile == "-":
    content = _read_stdin()
else:
    with io.open(args.infile, "r", encoding="utf-8") as f:
        content = f.read()
```

Update `infile` argparse definition:
`help="stack file (use - for stdin)"`

---

### PIPE-003 — `haiku_twist.py --bins` flag must precede subcommand
| Field    | Value |
|----------|-------|
| Severity | medium |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `--bins` is defined as a global flag on the parent
parser, so it must appear before the subcommand. Users naturally write
it after the subcommand (`haiku_twist.py generate --bins FILE`), which
fails with "unrecognized arguments". Every other tool in the stack puts
flags after the subcommand.

**Fix:** Add `--bins` to each subparser that needs it (`generate`,
`chain`, `verify`, `encode-stream`, `decode-stream`) in addition to
the parent parser.

---

### PIPE-004 — `encode-stream` TOKENS count in RSRC block is wrong
| Field    | Value |
|----------|-------|
| Severity | high |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** The `TOKENS` field in the haiku-stream RSRC block
records 1,620 (words written to payload) but the CRC is computed over
the input token stream (1,915 tokens). These are counts of different
things. The CRC check always fails on decode because the recovered token
stream has a different count than declared.

**Fix:** Separate counts in the RSRC block:
```
TOKENS-IN:    1915   # input token count (what CRC covers)
WORDS-OUT:    1915   # output word count (equals TOKENS-IN once PIPE-001 fixed)
CRC32-TOKENS: xxxx   # CRC over input token stream
```

---

### PIPE-005 — Document that `unstack` stdout is bare tokens, pipe-ready
| Field    | Value |
|----------|-------|
| Severity | low |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** `unstack` stdout is already a bare space-separated
token stream suitable for piping. This is not documented, so callers
don't know they can pipe directly without an intermediate file.

**Fix:** Add to `unstack` help text: "Output is a bare UCS-DEC token
stream, suitable for piping to `ucs_dec_tool.py --decode` or
`haiku_twist.py encode-stream`."

---

### PIPE-006 — Target state: full composable pipeline (acceptance test)
| Field    | Value |
|----------|-------|
| Severity | n/a — specification |
| Status   | open |
| Claimed  | — |
| Opened   | 2026-04-06 |
| Closed   | — |
| Commit   | — |

**Description:** Once PIPE-001 through PIPE-004 are resolved, the full
pipeline should work without temporary files:

```bash
# Encode: poem → FDS → CCL3 → haiku word stream
cat archive/second-law-blues.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --encode \
    | python tools/mnemonic/prime_twist.py stack \
        --verse-file verses.txt --no-symbol-check --ref CCL3 \
    | python tools/mnemonic/prime_twist.py unstack - \
    | python tools/mnemonic/haiku_twist.py --bins docs/cmudict/bins.json \
        encode-stream --verse verses.txt --ref STREAM-001 \
    > archive/second-law-blues-haiku.txt

# Decode: haiku word stream → bare tokens → FDS → poem
python tools/mnemonic/haiku_twist.py --bins docs/cmudict/bins.json \
    decode-stream archive/second-law-blues-haiku.txt \
    | python tools/ucs-dec/ucs_dec_tool.py --decode
```

Note: this pipeline bypasses CCL on the decode side. If CCL reversal is
also required, the CCL stack artifact must be preserved separately on
disk. The twist-maps live in the stack artifact; the caller keeps it.

**Blocking:** PIPE-001, PIPE-002, PIPE-003, PIPE-004.
