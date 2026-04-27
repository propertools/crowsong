# harvester

Local-walk HTML extraction tool.

Walks a directory tree of HTML documents, applies a config-driven extractor,
and emits canonical artefacts: plain text suitable for archivist stamping,
HTML fragments suitable for RSS embedding, standalone HTML documents
suitable for offline reading, and metadata sidecars suitable for downstream
aggregation.

Optionally aggregates harvested artefacts into an RSS 2.0 feed.

The harvester does not fetch over the network. It does not rewrite assets.
It does not preserve images or stylesheets. Those concerns belong to the
crawler tool (see `roadmap.md`). The harvester treats the local filesystem
as ground truth and assumes the canonical site remains eventually reachable.

---

## What it produces

For each input HTML file matching the configured pattern, the harvester
writes four artefacts to the output directory:

```
<slug>.txt          Canonical plain text. UTF-8, LF line endings.
                    Stable across runs. Ready for archivist stamping.

<slug>.fragment     Clean HTML fragment. The body content with
                    document chrome (<html>, <head>, <body>) and
                    configured strip targets removed. Suitable
                    for embedding in RSS content:encoded.

<slug>.standalone   Minimal HTML5 document wrapping the fragment.
                    Carries an absolute reference to the canonical
                    CSS plus a tiny embedded fallback. Renders
                    cleanly when the canonical site is reachable
                    and degrades to readable plain text when it isn't.

<slug>.meta         Metadata sidecar in plain text key=value format.
                    Round-trippable, archivist-stampable, human-
                    readable without any tooling.
```

The slug is derived from the input path. For the convention
`fieldwork/field-note-10/index.html`, slug is `field-note-10`. For flat
files like `posts/my-post.html`, slug is `my-post`.

---

## Format

A metadata sidecar looks like this:

```
canonical_url=https://propertools.be/fieldwork/field-note-10-on-trusting-trust-revisited/
description=On Ken Thompson's 1984 lecture, the fast16 sabotage framework, and the discipline of making trust commitments visible.
published=2026-04-27
slug=field-note-10
source_path=fieldwork/field-note-10/index.html
title=Field Note #10 ∷ On Trusting Trust, Revisited
```

Multi-line values are folded with a four-space continuation indent.
Empty and `None` values are omitted from the sidecar entirely.

The sidecar is the harvester's interchange format. The `feed` subcommand
reads sidecars and fragments to assemble RSS. Other tools can read the
sidecars to learn what the harvester found without reparsing the source HTML.

---

## Usage

```
python harvester.py walk    [options] <input-dir> <output-dir>
python harvester.py extract [options] <html-file>
python harvester.py feed    [options] <harvested-dir>
```

### walk

Traverse a directory of HTML files and emit canonical artefacts.

```bash
# Harvest a Field Notes directory tree
python harvester.py walk fieldwork/ harvested/

# Use a specific config
python harvester.py walk fieldwork/ harvested/ --config harvester.cfg

# Override the file-matching pattern
python harvester.py walk fieldwork/ harvested/ --pattern '*/index.html'

# Cron-friendly: silence on success, non-zero exit on error
python harvester.py walk fieldwork/ harvested/ --quiet

# Parse without writing anything
python harvester.py walk fieldwork/ harvested/ --dry-run
```

Options:

```
-c, --config FILE     Extractor config (default: ./harvester.cfg)
-p, --pattern GLOB    Restrict to files matching glob (default: from config)
-q, --quiet           Suppress progress messages (cron-friendly)
-n, --dry-run         Parse but do not write output
```

### extract

Render a single HTML file to canonical plain text on stdout.

```bash
# Extract one document
python harvester.py extract fieldwork/field-note-10/index.html

# Extract from stdin
cat document.html | python harvester.py extract -

# Pipe straight into archivist
python harvester.py extract document.html | \
    python ../archivist/archivist.py stamp --title "Notes" -
```

### feed

Aggregate harvested artefacts into an RSS 2.0 feed.

```bash
# Emit RSS to stdout
python harvester.py feed harvested/

# Write to a file (atomic; cron-safe)
python harvester.py feed harvested/ --output feed.xml

# Cron pipeline: harvest then emit feed, both silent on success
python harvester.py walk fieldwork/ harvested/ --quiet && \
    python harvester.py feed harvested/ --output feed.xml --quiet
```

Items are sorted newest first by their `published` field. The harvester
assumes ISO 8601 dates (`YYYY-MM-DD` or full RFC 3339) which sort
lexicographically without parsing.

Options:

```
-o, --output FILE     Output file (default: stdout)
-c, --config FILE     Config file (for feed channel metadata)
-q, --quiet           Suppress progress messages
```

---

## Configuration

The harvester is config-driven. The default config path is `./harvester.cfg`.
Override with `--config`.

The config is plain INI text. It is itself archivist-stampable. Sections:

```ini
[walk]
pattern = */index.html

[extractor]
container_tag    = article
container_class  = essay
strip            = h1, div.meta, p.archive-note

[output]
canonical_base   = https://propertools.be/fieldwork
canonical_css    = https://propertools.be/assets/css/main.css

[feed]
title            = Proper Tools — Field Notes
description      = Hard Problems Made Legible
site_url         = https://propertools.be
link             = https://propertools.be/fieldwork/
feed_url         = https://propertools.be/feed.xml
language         = en
copyright        = Proper Tools SRL
editor           = hello@propertools.be (Trey)
author           = hello@propertools.be (Trey Darley)
image            = https://propertools.be/assets/img/propertools-logo.png
archive_footer   = <hr><p><em>Canonical archive: <a href="{url}">{url_short}</a></em></p>
```

`harvester-example.cfg` ships alongside the tool as a working template.

### Strip rules

The `strip` directive in `[extractor]` is a comma-separated list of
elements to remove from the extracted fragment. Format:

```
strip = tag, tag.class, tag, tag.class
```

A bare `tag` matches all elements of that name. A `tag.class` matches
only elements with the named class. Strip rules apply within the
container; nested matching elements are removed entirely with their
contents. The container itself is never stripped.

### Class hygiene

The harvester discriminates strip targets by class name. If two
semantically distinct elements share a class, the harvester cannot
tell them apart. In particular: the canonical-archive footer at the
end of a Field Note and any in-body editorial asides MUST use
different classes if you want to strip the former and preserve the
latter.

The convention this project adopts:

```
class="archive-note"     Trailing canonical-archive footer.
                         Stripped by the harvester.

class="note"             In-body editorial aside (manicule asides
                         marked with ☞, footnote-style remarks).
                         Preserved by the harvester.
```

Apply the same convention if you adapt this tool to a different corpus.

---

## Round-trip behaviour

The harvester is a **canonical-extraction** tool, not a byte-for-byte
preservation tool. During extraction:

- Line endings are normalised to LF
- HTML comments are dropped
- Whitespace inside HTML fragments is preserved (modulo parser-level normalisation)
- Whitespace inside plain text is collapsed (paragraphs separated by `\n\n`,
  intra-paragraph whitespace collapsed to single spaces)
- Document chrome (`<html>`, `<head>`, `<body>`, `<link>`, `<script>`,
  `<style>`) is stripped from fragments
- HTML entities are decoded into their corresponding Unicode characters
  when rendering plain text; preserved verbatim in HTML fragments

The output is deterministic given the same input HTML and config. Running
the harvester twice produces identical artefacts.

To confirm round-trip:

```bash
# Harvest and verify all artefacts are produced
python harvester.py walk fieldwork/ harvested/
ls harvested/

# Diff successive runs to confirm determinism
python harvester.py walk fieldwork/ harvested-a/
python harvester.py walk fieldwork/ harvested-b/
diff -r harvested-a harvested-b   # should be empty
```

---

## Compatibility

- Python 2.7+ / 3.x
- No mandatory external dependencies
- Optional: `lxml` for malformed-HTML tolerance and faster parsing
- Encoding: UTF-8 throughout; stdin/stdout handled explicitly, not locale-dependent
- Line endings: CRLF normalised to LF before processing — safe across platforms

The HTML parsing backend is selected at runtime. If `lxml` is installed,
it is used preferentially. If not, the stdlib `HTMLParser` is used. Both
backends produce equivalent output for well-formed HTML.

For Crowsong deployments targeting embedded Python 2.7, only the stdlib
backend is required. `lxml` is purely an optional acceleration.

---

## Cron behaviour

The harvester is designed to be safe under cron invocation:

- Idempotent: running twice produces the same result
- Atomic writes: each output file is written to `<path>.tmp` and renamed
  into place. An interrupted run does not leave partial files in the
  output directory
- `--quiet` mode silences all progress output; only errors go to stderr
- Exit codes: 0 on success, 1 on any error
- No state outside the output directory; no lockfiles, no databases

A typical cron invocation:

```bash
# Once daily, regenerate the feed if anything has changed
0 3 * * *  cd /home/me/site && \
           python3 tools/harvester/harvester.py walk fieldwork/ harvested/ --quiet && \
           python3 tools/harvester/harvester.py feed harvested/ --output feed.xml --quiet
```

For most use cases, manual invocation as part of a publish workflow is
preferable to scheduled cron. The harvester is fast (sub-second for ten
documents) and integrating it into a `make publish` target gives you
conscious control over when the public feed updates.

---

## Tests

A test suite is provided in `test_harvester.py`. Run it with:

```bash
python test_harvester.py
python -m pytest test_harvester.py -v   # if pytest is available
```

The suite covers:

- Fragment extraction with strip rules: tag-only, tag.class, nested targets
- Manicule preservation regression: in-body `p.note` survives stripping
  of `p.archive-note` footer
- Site chrome exclusion: content outside the configured container is
  not present in the fragment
- Metadata extraction: title, h1, meta description, published date,
  canonical URL all populated correctly
- Plain text rendering: paragraph separation, inline element preservation,
  whitespace collapse, HTML entity decoding (named and numeric),
  script-tag exclusion
- Standalone HTML wrapper: doctype, embedded minimal CSS, canonical link,
  XML escaping in title
- Metadata sidecar: serialise/parse round-trip, empty value omission,
  Unicode preservation, multi-line value folding
- CRLF normalisation: CRLF, bare CR, LF input all produce LF output
- Slug derivation: `index.html` convention vs flat-file basename
- End-to-end pipeline: walk produces all four artefacts, feed aggregates
  them correctly, atomic writes leave no `.tmp` files behind
- lxml / stdlib backend parity for well-formed HTML
- Config parsing: sections, defaults, strip rule parsing
- RFC 822 date formatting from ISO inputs
- CDATA escape: the `]]>` terminator is split across two CDATA sections;
  end-to-end RSS containing the terminator parses as well-formed XML

---

## Composition with the toolchain

The harvester sits between source HTML and downstream consumers. It
composes cleanly with the rest of the Crowsong toolchain:

```
HTML source                                                 [input]
   ↓
harvester walk                                              [this tool]
   ↓
canonical text (.txt) + HTML fragment (.fragment)
+ standalone HTML (.standalone) + metadata (.meta)
   ↓                ↓                    ↓
archivist stamp    harvester feed      offline archive
   ↓                ↓                    ↓
verifiable          RSS feed             physical capsule
artefact            (feed.xml)           (e.g. Vesper Archive)
```

The text artefact is archivist-stampable. The fragment is RSS-ready.
The standalone is offline-readable. The sidecar is the interchange
format that lets downstream tools read what the harvester found
without reparsing the source.

---

## What harvester does NOT provide

- **Network fetch.** The harvester reads from the local filesystem only.
  Use the crawler (future tool) to fetch from remote URLs.

- **Asset preservation.** Images, stylesheets, fonts, embedded media,
  and PDFs referenced by the HTML are not fetched, copied, or rewritten.
  The standalone HTML carries an absolute reference to the canonical CSS
  and a tiny embedded fallback; that is the entirety of the asset story.
  Comprehensive asset archival belongs in the crawler.

- **Cryptographic verification.** The harvester does not stamp its output
  with hashes or signatures. Pipe the canonical text artefact through
  archivist to add SHA256 framing.

- **Mutation of source HTML.** The harvester is read-only with respect
  to the input directory. Output is written only to the configured
  output directory.

- **Feed reader-specific tweaks.** The RSS output is plain RSS 2.0 with
  `content:encoded` for full-text. It does not target any particular
  reader's idiosyncrasies.

---

## Design notes

**Why two-stage (walk then feed)?** Because they fail differently.
Walk failures are about source HTML — malformed input, missing files,
bad config. Feed failures are about aggregation — missing sidecars,
inconsistent dates, encoding errors. Separating the stages means each
can be debugged independently. It also means the intermediate artefacts
are inspectable and re-aggregatable: you can change the feed channel
metadata and rerun `feed` without re-walking.

**Why a metadata sidecar instead of inlining metadata in the fragment?**
Because the fragment is consumed by feed readers, which mostly ignore
inline metadata. The sidecar keeps the fragment clean and makes the
metadata available to other tools (archivist, future feed formats,
build systems) without HTML reparsing.

**Why config-driven instead of code-driven extractors?** Because the
extraction rules are data, not code. A new corpus needs a new config,
not new Python. The config file is plain text, archivist-stampable,
and survives the toolchain. Code-driven extractors require Python on
every machine that needs to run them; config-driven extractors can
be applied by any tool that reads the format.

**Why allow `lxml` if available?** Because real-world HTML is messy.
Stdlib `HTMLParser` is fine for well-formed input but stumbles on
malformed pages. `lxml` is faster and more tolerant. For Crowsong
deployments, `lxml` may not be available; the stdlib path remains
fully functional.

**Why atomic writes?** Because cron jobs get interrupted. A run that
fails halfway through must not leave a half-written `feed.xml` for the
web server to serve. Writing to `<path>.tmp` and renaming into place
gives us crash-consistency on POSIX filesystems.

**What harvester does NOT do that you might expect:** rewrite asset
URLs to relative paths, fetch and embed images as base64 data URIs,
preserve original `<link>` and `<style>` tags, generate Atom or JSON
feed formats, paginate output, support incremental updates. All of
these are reasonable extensions; none are in scope for this iteration.

The harvester is a small tool with bounded responsibility. The
toolchain extends it through composition, not feature accretion.
