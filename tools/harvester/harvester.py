#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
harvester.py -- Local-walk HTML extraction tool

Walks a directory tree of HTML documents, applies a config-driven
extractor, and emits canonical artefacts: plain text (archivist-stampable),
HTML fragment (RSS-embeddable), HTML standalone (archive-readable), and
a metadata sidecar (key=value plain text).

Optionally aggregates harvested artefacts into an RSS 2.0 feed.

The harvester does not fetch over the network. It does not rewrite assets.
It does not preserve images or stylesheets. Those concerns belong to the
crawler tool (see roadmap.md). The harvester treats the local filesystem
as ground truth and the canonical site as eventually reachable.

Usage:
    python harvester.py walk    [options] <input-dir> <output-dir>
    python harvester.py extract [options] <html-file>
    python harvester.py feed    [options] <harvested-dir>

Options (walk):
    -c, --config FILE       Extractor config (default: ./harvester.cfg)
    -p, --pattern GLOB      Restrict to files matching glob (default: from config)
    -q, --quiet             Suppress progress messages (cron-friendly)
    -n, --dry-run           Parse but do not write output

Options (feed):
    -o, --output FILE       Output path (default: stdout)
    -c, --config FILE       Extractor config (for feed channel metadata)
    -q, --quiet             Suppress progress messages

Note on round-trips: harvester normalises whitespace and line endings to
LF in canonical text output. HTML fragments preserve internal whitespace
but strip the document chrome (<html>, <head>, <body>, <link>, <script>).
This is a canonical-extraction round-trip, not byte-for-byte preservation.

Examples:
    # Walk a Field Notes directory tree, emit canonical artefacts
    python harvester.py walk fieldwork/ harvested/

    # Aggregate harvested artefacts into RSS
    python harvester.py feed harvested/ --output feed.xml

    # Extract a single document to stdout
    python harvester.py extract fieldwork/field-note-10/index.html

    # Cron-friendly: walk and feed in one pass, silent on success
    python harvester.py walk fieldwork/ harvested/ --quiet && \
        python harvester.py feed harvested/ --output feed.xml --quiet

Compatibility: Python 2.7+ / 3.x
HTML backend: lxml if available, fall back to stdlib HTMLParser
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import io
import os
import re
import sys
import fnmatch
from datetime import datetime

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
    string_types = (str, unicode)  # noqa: F821
    from ConfigParser import RawConfigParser
    from HTMLParser import HTMLParser as _StdlibHTMLParser
    from htmlentitydefs import name2codepoint
else:
    text_type = str
    string_types = (str,)
    from configparser import RawConfigParser
    from html.parser import HTMLParser as _StdlibHTMLParser
    from html.entities import name2codepoint

# Optional lxml backend.
try:
    from lxml import etree, html as lxml_html
    HAVE_LXML = True
except ImportError:
    HAVE_LXML = False

__version__ = "1.0"


# -- Helpers (lifted from archivist) -------------------------------------------

def _to_text(value):
    """Coerce value to unicode text on both Python 2 and 3."""
    if value is None:
        return None
    if isinstance(value, text_type):
        return value
    if PY2 and isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return text_type(value)


def _normalise(text):
    """Normalise line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _rewrite_relative_urls(fragment, canonical_base):
    """
    Rewrite root-relative URLs in HTML attributes to absolute URLs.

    Some feed readers do not resolve relative links against the canonical
    URL of the feed item. Rewriting ``/path`` to ``https://example.com/path``
    inside ``content:encoded`` ensures cross-references survive embedding.

    Only root-relative URLs (starting with ``/`` but not ``//``) are
    rewritten. Protocol-relative (``//cdn.example.com/...``) and absolute
    (``https://...``) URLs are left alone.

    Operates on ``href`` and ``src`` attributes only. Both double-quoted
    (``href="/path"``) and single-quoted (``href='/path'``) attribute
    values are supported. Path-relative URLs (``../foo``, ``foo/bar``)
    are not rewritten because their resolution depends on the source
    document's URL, which the harvester does not know at this layer.
    """
    if not canonical_base:
        return fragment
    # Strip trailing slash from base so we don't produce ``//path``.
    base = canonical_base.rstrip("/")
    # Match href=QUOTE/...QUOTE and src=QUOTE/...QUOTE where QUOTE is
    # either ``"`` or ``'`` (matched consistently via backreference).
    # The negative lookahead (?!/) excludes protocol-relative URLs.
    pattern = re.compile(r"""(href|src)=(["'])(/(?!/)[^"']*)\2""")
    return pattern.sub(r"\1=\2" + base + r"\3\2", fragment)


def _read(path_or_dash):
    """Read text (unicode) from a file path or '-' for stdin."""
    if path_or_dash == "-" or path_or_dash is None:
        if PY2:
            data = sys.stdin.read()
            if not isinstance(data, text_type):
                data = data.decode("utf-8", "replace")
            return data
        return sys.stdin.buffer.read().decode("utf-8", "replace")
    with io.open(path_or_dash, "r", encoding="utf-8") as f:
        return f.read()


def _stdout_write_utf8(text):
    """Write unicode text to stdout as UTF-8 bytes."""
    data = text.encode("utf-8")
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(data)
    else:
        sys.stdout.write(data)


def _write_atomic(text, path):
    """Atomic write: write to .tmp, then rename. Cron-safe."""
    if path is None:
        _stdout_write_utf8(text)
        return
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    # On Windows, os.rename fails if dest exists; remove first.
    if os.path.exists(path) and os.name == "nt":
        os.remove(path)
    os.rename(tmp, path)


def _label(path_or_dash):
    if path_or_dash == "-" or path_or_dash is None:
        return "<stdin>"
    return path_or_dash


# -- HTML parsing backends -----------------------------------------------------

class _StripExtractor(_StdlibHTMLParser):
    """
    Stdlib HTMLParser-based body extractor.

    Walks an HTML document, finds the container element matching the
    configured selector (tag + class), then emits inner HTML while
    skipping any elements matching the strip rules.

    Strip rules are matched by tag name + class. A rule like
    ('div', 'meta') strips <div class="meta">...</div> entirely
    including its nested content.
    """

    def __init__(self, container_tag, container_class, strip_rules):
        # convert_charrefs=False so we can preserve entities verbatim.
        # On Python 2.7 HTMLParser does not accept this kwarg.
        if PY2:
            _StdlibHTMLParser.__init__(self)
        else:
            _StdlibHTMLParser.__init__(self, convert_charrefs=False)
        self.container_tag = container_tag
        self.container_class = container_class
        self.strip_rules = strip_rules  # list of (tag, class_or_None)
        self._buffer = []
        self._in_container = False
        self._container_depth = 0
        self._skipping = False
        self._skip_tag = None
        self._skip_depth = 0

    def _matches_container(self, tag, attrs_dict):
        if tag != self.container_tag:
            return False
        if self.container_class is None:
            return True
        cls_attr = attrs_dict.get("class", "")
        return self.container_class in cls_attr.split()

    def _matches_strip(self, tag, attrs_dict):
        cls_attr = attrs_dict.get("class", "")
        cls_set = set(cls_attr.split())
        for strip_tag, strip_class in self.strip_rules:
            if tag != strip_tag:
                continue
            if strip_class is None:
                return True
            if strip_class in cls_set:
                return True
        return False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if not self._in_container:
            if self._matches_container(tag, attrs_dict):
                self._in_container = True
                self._container_depth = 1
            return

        # Track nested container tags.
        if tag == self.container_tag:
            self._container_depth += 1

        if self._skipping:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return

        if self._matches_strip(tag, attrs_dict):
            self._skipping = True
            self._skip_tag = tag
            self._skip_depth = 1
            return

        self._buffer.append(_format_starttag(tag, attrs))

    def handle_startendtag(self, tag, attrs):
        if not self._in_container or self._skipping:
            return
        attrs_dict = dict(attrs)
        if self._matches_strip(tag, attrs_dict):
            return
        self._buffer.append(_format_starttag(tag, attrs, self_closing=True))

    def handle_endtag(self, tag):
        if not self._in_container:
            return

        if self._skipping:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skipping = False
                    self._skip_tag = None
            return

        if tag == self.container_tag:
            self._container_depth -= 1
            if self._container_depth == 0:
                self._in_container = False
                return

        self._buffer.append("</{}>".format(tag))

    def handle_data(self, data):
        if self._in_container and not self._skipping:
            self._buffer.append(data)

    def handle_entityref(self, name):
        if self._in_container and not self._skipping:
            self._buffer.append("&{};".format(name))

    def handle_charref(self, name):
        if self._in_container and not self._skipping:
            self._buffer.append("&#{};".format(name))

    def handle_comment(self, data):
        # Drop HTML comments (e.g. <!-- FOOTNOTES -->).
        pass

    def get_fragment(self):
        return "".join(self._buffer).strip()


def _format_starttag(tag, attrs, self_closing=False):
    """Reconstruct a start tag from parser-emitted attrs."""
    if attrs:
        parts = []
        for k, v in attrs:
            if v is None:
                parts.append(k)
            else:
                # Escape double quotes in attribute values.
                v_escaped = v.replace("&", "&amp;").replace('"', "&quot;")
                parts.append('{}="{}"'.format(k, v_escaped))
        attr_str = " " + " ".join(parts)
    else:
        attr_str = ""
    if self_closing:
        return "<{}{} />".format(tag, attr_str)
    return "<{}{}>".format(tag, attr_str)


class _MetaExtractor(_StdlibHTMLParser):
    """Pull <meta> tags, <title>, and the first <h1> from <head> and <body>."""

    def __init__(self, h1_container_tag, h1_container_class):
        if PY2:
            _StdlibHTMLParser.__init__(self)
        else:
            _StdlibHTMLParser.__init__(self, convert_charrefs=False)
        self.meta = {}
        self.title = None
        self.h1 = None
        self.h1_container_tag = h1_container_tag
        self.h1_container_class = h1_container_class
        self._in_title = False
        self._title_buffer = []
        self._in_h1_container = False
        self._h1_container_depth = 0
        self._in_h1 = False
        self._h1_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == "meta":
            name = attrs_dict.get("name", "")
            prop = attrs_dict.get("property", "")
            content = attrs_dict.get("content", "")
            if name and name not in self.meta:
                self.meta[name] = content
            if prop and prop not in self.meta:
                self.meta[prop] = content
            return

        if tag == "title":
            self._in_title = True
            return

        # Track h1 container.
        if (self.h1_container_tag is not None and
                tag == self.h1_container_tag):
            cls_attr = attrs_dict.get("class", "")
            if (self.h1_container_class is None or
                    self.h1_container_class in cls_attr.split()):
                self._in_h1_container = True
                self._h1_container_depth = 1
            elif self._in_h1_container:
                self._h1_container_depth += 1

        if tag == "h1" and self._in_h1_container and not self.h1:
            self._in_h1 = True

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            if not self.title:
                self.title = "".join(self._title_buffer).strip()
        elif tag == "h1" and self._in_h1:
            self._in_h1 = False
            self.h1 = "".join(self._h1_buffer).strip()
        elif (self.h1_container_tag is not None and
                tag == self.h1_container_tag and self._in_h1_container):
            self._h1_container_depth -= 1
            if self._h1_container_depth == 0:
                self._in_h1_container = False

    def handle_data(self, data):
        if self._in_title:
            self._title_buffer.append(data)
        elif self._in_h1:
            self._h1_buffer.append(data)

    def handle_entityref(self, name):
        if self._in_title or self._in_h1:
            cp = name2codepoint.get(name)
            if cp:
                ch = _unichr(cp)
                if self._in_title:
                    self._title_buffer.append(ch)
                if self._in_h1:
                    self._h1_buffer.append(ch)

    def handle_charref(self, name):
        if self._in_title or self._in_h1:
            try:
                if name.startswith(("x", "X")):
                    cp = int(name[1:], 16)
                else:
                    cp = int(name)
                ch = _unichr(cp)
                if self._in_title:
                    self._title_buffer.append(ch)
                if self._in_h1:
                    self._h1_buffer.append(ch)
            except (ValueError, OverflowError):
                pass


def _unichr(cp):
    """Cross-version unichr."""
    if PY2:
        return unichr(cp)  # noqa: F821
    return chr(cp)


# -- Backend dispatch ----------------------------------------------------------

def _extract_with_lxml(html_text, container_tag, container_class, strip_rules):
    """
    lxml-based body extraction. Used when lxml is available; produces the
    same structural output as the stdlib path for well-formed HTML, with
    better tolerance for malformed input.
    """
    parser = lxml_html.HTMLParser(encoding="utf-8")
    tree = lxml_html.fromstring(html_text.encode("utf-8"), parser=parser)

    # Find container by tag and class.
    if container_class:
        xpath = ".//{}[contains(concat(' ', normalize-space(@class), ' '), ' {} ')]".format(
            container_tag, container_class)
    else:
        xpath = ".//{}".format(container_tag)
    containers = tree.xpath(xpath)
    if not containers:
        return ""
    container = containers[0]

    # Strip configured elements (in place).
    #
    # NOTE: ``getparent().remove(el)`` drops ``el.tail`` along with the
    # element. This is correct for block-level strip rules (h1, div.meta,
    # p.archive-note) where tail text is whitespace. If inline strip rules
    # are added in future, switch to a tail-preserving removal:
    #
    #     parent = el.getparent()
    #     idx = parent.index(el)
    #     if el.tail:
    #         if idx == 0:
    #             parent.text = (parent.text or "") + el.tail
    #         else:
    #             prev = parent[idx - 1]
    #             prev.tail = (prev.tail or "") + el.tail
    #     parent.remove(el)
    for strip_tag, strip_class in strip_rules:
        if strip_class:
            strip_xpath = ".//{}[contains(concat(' ', normalize-space(@class), ' '), ' {} ')]".format(
                strip_tag, strip_class)
        else:
            strip_xpath = ".//{}".format(strip_tag)
        for el in container.xpath(strip_xpath):
            el.getparent().remove(el)

    # Serialise inner HTML.
    parts = []
    if container.text:
        parts.append(container.text)
    for child in container:
        parts.append(lxml_html.tostring(child, encoding="unicode"))
    return "".join(parts).strip()


def extract_fragment(html_text, container_tag, container_class, strip_rules,
                     prefer_lxml=True):
    """
    Extract the inner HTML of the configured container, with strip rules
    applied. Returns a unicode string suitable for embedding in RSS
    content:encoded or wrapping in a standalone HTML document.
    """
    if prefer_lxml and HAVE_LXML:
        return _extract_with_lxml(html_text, container_tag, container_class,
                                  strip_rules)
    extractor = _StripExtractor(container_tag, container_class, strip_rules)
    extractor.feed(html_text)
    return extractor.get_fragment()


def extract_metadata(html_text, h1_container_tag, h1_container_class):
    """Extract meta tags, title, and h1 from an HTML document."""
    extractor = _MetaExtractor(h1_container_tag, h1_container_class)
    extractor.feed(html_text)
    return {
        "meta": extractor.meta,
        "title": extractor.title,
        "h1": extractor.h1,
    }


# -- Canonical text rendering --------------------------------------------------

class _TextRenderer(_StdlibHTMLParser):
    """
    Render HTML fragment to plain text.

    Block elements produce paragraph breaks. Inline elements pass through.
    Whitespace is normalised. The output is suitable for archivist stamping.
    """

    BLOCK_TAGS = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "li", "tr", "hr",
    }
    SKIP_TAGS = {"script", "style"}

    def __init__(self):
        if PY2:
            _StdlibHTMLParser.__init__(self)
        else:
            _StdlibHTMLParser.__init__(self, convert_charrefs=False)
        self._buffer = []
        self._skipping = False
        self._skip_tag = None
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self._skipping:
            if tag == self._skip_tag:
                self._skip_depth += 1
            return
        if tag in self.SKIP_TAGS:
            self._skipping = True
            self._skip_tag = tag
            self._skip_depth = 1
            return
        if tag in self.BLOCK_TAGS:
            self._buffer.append("\n\n")
        elif tag == "br":
            self._buffer.append("\n")

    def handle_startendtag(self, tag, attrs):
        if self._skipping:
            return
        if tag == "br":
            self._buffer.append("\n")
        elif tag == "hr":
            self._buffer.append("\n\n")

    def handle_endtag(self, tag):
        if self._skipping:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth == 0:
                    self._skipping = False
                    self._skip_tag = None
            return
        if tag in self.BLOCK_TAGS:
            self._buffer.append("\n\n")

    def handle_data(self, data):
        if not self._skipping:
            self._buffer.append(data)

    def handle_entityref(self, name):
        if self._skipping:
            return
        cp = name2codepoint.get(name)
        if cp:
            self._buffer.append(_unichr(cp))

    def handle_charref(self, name):
        if self._skipping:
            return
        try:
            if name.startswith(("x", "X")):
                cp = int(name[1:], 16)
            else:
                cp = int(name)
            self._buffer.append(_unichr(cp))
        except (ValueError, OverflowError):
            pass

    def get_text(self):
        text = "".join(self._buffer)
        # Collapse runs of whitespace within lines, preserve paragraph breaks.
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def render_text(html_fragment):
    """Render an HTML fragment to plain UTF-8 text."""
    renderer = _TextRenderer()
    renderer.feed(html_fragment)
    return renderer.get_text()


# -- Standalone HTML wrapper ---------------------------------------------------

MINIMAL_CSS = """
body { max-width: 36em; margin: 2em auto; padding: 0 1em;
       font-family: Georgia, 'Times New Roman', serif;
       line-height: 1.5; color: #222; }
h1, h2, h3 { font-family: Helvetica, Arial, sans-serif; }
h1 { font-size: 1.6em; }
h2 { font-size: 1.25em; margin-top: 2em; }
blockquote { margin: 1em 0; padding-left: 1em;
             border-left: 3px solid #ccc; color: #555; }
hr { border: 0; border-top: 1px solid #ccc; margin: 2em 0; }
.note { font-size: 0.95em; color: #555; padding-left: 1.5em;
        border-left: 2px solid #ddd; }
.lede { font-style: italic; color: #555; }
em { font-style: italic; }
a { color: #335; }
"""


def render_standalone(title, fragment, canonical_url, canonical_css_url):
    """Wrap an HTML fragment in a minimal standalone document."""
    title_escaped = _escape_xml(title or "")
    return (
        '<!doctype html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>{title}</title>\n'
        '<link rel="canonical" href="{canonical}">\n'
        '<link rel="stylesheet" href="{css}">\n'
        '<style>{minimal_css}</style>\n'
        '</head>\n'
        '<body>\n'
        '<article>\n'
        '<h1>{title}</h1>\n'
        '{fragment}\n'
        '<hr>\n'
        '<p><em>Canonical: <a href="{canonical}">{canonical}</a></em></p>\n'
        '</article>\n'
        '</body>\n'
        '</html>\n'
    ).format(
        title=title_escaped,
        canonical=_escape_xml(canonical_url),
        css=_escape_xml(canonical_css_url),
        minimal_css=MINIMAL_CSS,
        fragment=fragment,
    )


# -- Metadata sidecar ----------------------------------------------------------

def render_meta_sidecar(meta):
    """Render a metadata dict as plain text key=value lines."""
    lines = []
    for key in sorted(meta.keys()):
        value = meta[key]
        if value is None or value == "":
            continue
        # _to_text() handles Py2 unicode coercion safely; multi-line
        # values are folded with a four-space continuation indent.
        value = _normalise(_to_text(value)).replace("\n", "\n    ")
        lines.append("{}={}".format(key, value))
    return "\n".join(lines) + "\n"


def parse_meta_sidecar(text):
    """Parse a metadata sidecar into a dict."""
    meta = {}
    current_key = None
    for line in _normalise(text).split("\n"):
        if line.startswith("    ") and current_key is not None:
            meta[current_key] += "\n" + line[4:]
        elif "=" in line:
            key, _, value = line.partition("=")
            current_key = key.strip()
            meta[current_key] = value
        else:
            current_key = None
    return meta


# -- XML helpers ---------------------------------------------------------------

def _escape_xml(text):
    """XML-escape text for safe attribute and element content embedding."""
    if text is None:
        return ""
    return (text_type(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def _cdata(text):
    """
    Escape text for safe embedding inside a CDATA section.

    CDATA sections terminate at ``]]>``. If the text contains that sequence,
    we split it across two CDATA sections so the literal terminator never
    appears inside one. The result is still embedded in a single
    ``<![CDATA[...]]>`` wrapper at the call site.
    """
    if text is None:
        return ""
    return text_type(text).replace("]]>", "]]]]><![CDATA[>")


def _rfc822(dt_str):
    """
    Format an ISO date string as RFC 822 for RSS pubDate.

    Currently assumes UTC. Date-only inputs (``2026-04-27``) are interpreted
    as midnight UTC. ISO strings with a timezone offset are accepted, but
    the offset is discarded -- output always carries ``+0000``. Callers
    that need timezone-aware output must normalise inputs before calling.
    """
    if not dt_str:
        return ""
    # Try full ISO with timezone.
    try:
        normalised = dt_str.replace("Z", "+00:00")
        if PY2:
            # Python 2 has no datetime.fromisoformat.
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", normalised)
            if m:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d")
            else:
                return ""
        else:
            try:
                dt = datetime.fromisoformat(normalised)
            except ValueError:
                dt = datetime.strptime(normalised[:10], "%Y-%m-%d")
    except (ValueError, AttributeError):
        return ""
    # Strip tzinfo for portable formatting; assume UTC.
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


# -- Config --------------------------------------------------------------------

class Config(object):
    """
    Harvester config. Loaded from an INI-style file.

    Required sections:
        [extractor]   - body extraction rules
        [feed]        - feed channel metadata (only required for `feed` mode)

    Optional sections:
        [walk]        - file matching patterns
        [output]      - output naming conventions
    """

    def __init__(self, path):
        self.path = path
        self._cp = RawConfigParser()
        if path and os.path.exists(path):
            with io.open(path, "r", encoding="utf-8") as f:
                if PY2:
                    self._cp.readfp(f)
                else:
                    self._cp.read_file(f)
        self._loaded = bool(path and os.path.exists(path))

    @property
    def loaded(self):
        return self._loaded

    def get(self, section, option, default=None):
        if self._cp.has_option(section, option):
            return self._cp.get(section, option)
        return default

    def get_list(self, section, option, default=None):
        """Get a comma-separated list option, with optional class qualifiers."""
        raw = self.get(section, option, default)
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def get_strip_rules(self):
        """
        Parse strip rules from the [extractor] section.
        Format: 'tag.class, tag.class, tag' (class optional).
        """
        raw_rules = self.get_list("extractor", "strip", "")
        rules = []
        for rule in raw_rules:
            if "." in rule:
                tag, cls = rule.split(".", 1)
                rules.append((tag.strip(), cls.strip()))
            else:
                rules.append((rule.strip(), None))
        return rules


# -- Walker --------------------------------------------------------------------

def find_html_files(root, pattern):
    """Walk root and yield paths matching pattern (glob)."""
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(fn, pattern):
                yield full


def derive_slug(html_path, root):
    """
    Derive a slug from an HTML path. For paths like
    'fieldwork/field-note-10/index.html', slug is 'field-note-10'.
    For paths like 'foo/bar.html', slug is 'bar'.
    """
    rel = os.path.relpath(html_path, root)
    parts = rel.split(os.sep)
    if parts[-1] == "index.html" and len(parts) > 1:
        return parts[-2]
    base = os.path.splitext(parts[-1])[0]
    return base


def harvest_one(html_path, slug, config, output_dir, dry_run=False):
    """Process a single HTML file and emit canonical artefacts."""
    raw = _read(html_path)

    container_tag = config.get("extractor", "container_tag", "article")
    container_class = config.get("extractor", "container_class", None)
    h1_container_tag = config.get("extractor", "h1_container_tag",
                                  container_tag)
    h1_container_class = config.get("extractor", "h1_container_class",
                                    container_class)
    strip_rules = config.get_strip_rules()
    canonical_base = config.get("output", "canonical_base", "")
    canonical_css = config.get("output", "canonical_css",
                               canonical_base + "/assets/css/main.css")
    # site_base is used to rewrite root-relative URLs (/path) to absolute
    # in the emitted fragment. Defaults to the feed's site_url so most
    # configs do not need to set it explicitly.
    site_base = config.get("output", "site_base",
                           config.get("feed", "site_url", ""))

    # Extract metadata.
    md = extract_metadata(raw, h1_container_tag, h1_container_class)
    meta = {
        "slug": slug,
        "title": md["h1"] or md["title"] or slug,
        "description": md["meta"].get("description", ""),
        "published": md["meta"].get("article:published_time", ""),
        "canonical_url": md["meta"].get("og:url",
                          canonical_base + "/" + slug + "/"),
        "source_path": os.path.relpath(html_path),
    }

    # Extract body fragment.
    fragment = extract_fragment(raw, container_tag, container_class,
                                strip_rules)
    # Rewrite root-relative URLs to absolute, so cross-references survive
    # embedding in feed readers that don't resolve relative URLs.
    fragment = _rewrite_relative_urls(fragment, site_base)

    # Render plain text and standalone.
    text = render_text(fragment)
    standalone = render_standalone(meta["title"], fragment,
                                   meta["canonical_url"], canonical_css)
    sidecar = render_meta_sidecar(meta)

    if dry_run:
        return meta, fragment, text, standalone

    # Write artefacts atomically.
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    _write_atomic(text + "\n", os.path.join(output_dir, slug + ".txt"))
    _write_atomic(fragment + "\n",
                  os.path.join(output_dir, slug + ".fragment"))
    _write_atomic(standalone,
                  os.path.join(output_dir, slug + ".standalone"))
    _write_atomic(sidecar, os.path.join(output_dir, slug + ".meta"))

    return meta, fragment, text, standalone


# -- RSS aggregation -----------------------------------------------------------

def build_feed(harvested_dir, config):
    """Build an RSS 2.0 feed from a directory of harvested artefacts."""
    items = []
    for fn in sorted(os.listdir(harvested_dir)):
        if not fn.endswith(".meta"):
            continue
        slug = fn[:-5]
        meta_path = os.path.join(harvested_dir, fn)
        fragment_path = os.path.join(harvested_dir, slug + ".fragment")
        if not os.path.exists(fragment_path):
            continue
        meta = parse_meta_sidecar(_read(meta_path))
        fragment = _read(fragment_path).strip()
        items.append({
            "slug": slug,
            "meta": meta,
            "fragment": fragment,
        })

    # Sort newest first.
    # NOTE: this uses lexicographic comparison on the ``published`` field,
    # which is correct for ISO 8601 dates (YYYY-MM-DD or full RFC 3339)
    # because the format is designed to sort lexicographically. Human-
    # readable date formats ("April 27, 2026") would sort incorrectly.
    items.sort(key=lambda i: i["meta"].get("published", ""), reverse=True)

    site_url = config.get("feed", "site_url", "")
    feed_url = config.get("feed", "feed_url", site_url + "/feed.xml")
    feed_link = config.get("feed", "link", site_url)
    feed_title = config.get("feed", "title", "Untitled Feed")
    feed_desc = config.get("feed", "description", "")
    feed_lang = config.get("feed", "language", "en")
    feed_copyright = config.get("feed", "copyright", "")
    feed_editor = config.get("feed", "editor", "")
    feed_author = config.get("feed", "author", feed_editor)
    feed_image = config.get("feed", "image", "")
    feed_ttl = config.get("feed", "ttl", "")
    archive_footer_template = config.get("feed", "archive_footer",
        '<hr><p><em>Canonical archive version: '
        '<a href="{url}">{url_short}</a></em></p>')

    most_recent = items[0]["meta"].get("published", "") if items else ""
    last_build = _rfc822(most_recent) or _rfc822(
        datetime.utcnow().strftime("%Y-%m-%d"))

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">')
    lines.append("  <channel>")
    lines.append("    <title>{}</title>".format(_escape_xml(feed_title)))
    lines.append("    <link>{}</link>".format(_escape_xml(feed_link)))
    lines.append("    <description>{}</description>".format(
        _escape_xml(feed_desc)))
    lines.append("    <language>{}</language>".format(_escape_xml(feed_lang)))
    if feed_copyright:
        lines.append("    <copyright>{}</copyright>".format(
            _escape_xml(feed_copyright)))
    if feed_editor:
        lines.append("    <managingEditor>{}</managingEditor>".format(
            _escape_xml(feed_editor)))
    lines.append("    <lastBuildDate>{}</lastBuildDate>".format(last_build))
    if feed_ttl:
        lines.append("    <ttl>{}</ttl>".format(_escape_xml(feed_ttl)))
    if feed_image:
        lines.append("    <image>")
        lines.append("      <url>{}</url>".format(_escape_xml(feed_image)))
        lines.append("      <title>{}</title>".format(_escape_xml(feed_title)))
        lines.append("      <link>{}</link>".format(_escape_xml(feed_link)))
        lines.append("    </image>")
    lines.append('    <atom:link href="{}" rel="self" '
                 'type="application/rss+xml"/>'.format(_escape_xml(feed_url)))
    lines.append("")

    for item in items:
        meta = item["meta"]
        title = meta.get("title", item["slug"])
        url = meta.get("canonical_url", "")
        pub_date = _rfc822(meta.get("published", ""))
        description = meta.get("description", "")
        url_short = url.replace("https://", "").replace("http://", "")
        archive_footer = archive_footer_template.format(
            url=url, url_short=url_short)

        lines.append("    <item>")
        lines.append("      <title>{}</title>".format(_escape_xml(title)))
        lines.append("      <link>{}</link>".format(_escape_xml(url)))
        lines.append('      <guid isPermaLink="true">{}</guid>'.format(
            _escape_xml(url)))
        if pub_date:
            lines.append("      <pubDate>{}</pubDate>".format(pub_date))
        if feed_author:
            lines.append("      <author>{}</author>".format(
                _escape_xml(feed_author)))
        lines.append("      <description><![CDATA[{}]]></description>".format(
            _cdata(description)))
        lines.append("      <content:encoded><![CDATA[")
        lines.append(_cdata(item["fragment"]))
        lines.append(_cdata(archive_footer))
        lines.append("      ]]></content:encoded>")
        lines.append("    </item>")
        lines.append("")

    lines.append("  </channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"


# -- CLI commands --------------------------------------------------------------

def cmd_walk(args):
    config = Config(args.config)
    if not config.loaded:
        print("Warning: config file not found: {}".format(args.config),
              file=sys.stderr)

    pattern = args.pattern or config.get("walk", "pattern", "*.html")

    if not os.path.isdir(args.input_dir):
        print("Error: not a directory: {}".format(args.input_dir),
              file=sys.stderr)
        return 1

    files = list(find_html_files(args.input_dir, pattern))
    if not files:
        print("Error: no files matching '{}' in {}".format(
            pattern, args.input_dir), file=sys.stderr)
        return 1

    if not args.quiet:
        print("Found {} file(s) matching '{}'".format(len(files), pattern),
              file=sys.stderr)

    errors = 0
    for html_path in sorted(files):
        slug = derive_slug(html_path, args.input_dir)
        if not args.quiet:
            print("  harvesting {} -> {}".format(
                _label(html_path), slug), file=sys.stderr)
        try:
            harvest_one(html_path, slug, config, args.output_dir,
                        dry_run=args.dry_run)
        except (IOError, OSError) as err:
            print("  ERROR  {} - {}".format(_label(html_path), err),
                  file=sys.stderr)
            errors += 1

    if not args.quiet:
        if errors:
            print("Completed with {} error(s)".format(errors), file=sys.stderr)
        else:
            print("Done.", file=sys.stderr)

    return 1 if errors else 0


def cmd_extract(args):
    """
    Render a single HTML file to canonical plain text on stdout.

    NOTE: relative URLs are NOT rewritten by this command. The rewriter
    is applied only in the ``walk`` path, where output fragments are
    embedded in feed readers that may not resolve relative links. The
    ``extract`` command emits canonical plain text via ``render_text()``,
    which strips all HTML attributes including URLs, so rewriting would
    be a no-op. If a future variant of ``extract`` emits HTML fragments
    instead of plain text, URL rewriting must be applied there as well.
    """
    config = Config(args.config)
    container_tag = config.get("extractor", "container_tag", "article")
    container_class = config.get("extractor", "container_class", None)
    strip_rules = config.get_strip_rules()

    raw = _read(args.file)
    fragment = extract_fragment(raw, container_tag, container_class,
                                strip_rules)
    text = render_text(fragment)
    _stdout_write_utf8(text + "\n")
    return 0


def cmd_feed(args):
    config = Config(args.config)
    if not config.loaded:
        print("Warning: config file not found: {}".format(args.config),
              file=sys.stderr)

    if not os.path.isdir(args.harvested_dir):
        print("Error: not a directory: {}".format(args.harvested_dir),
              file=sys.stderr)
        return 1

    rss = build_feed(args.harvested_dir, config)

    if args.output:
        _write_atomic(rss, args.output)
        if not args.quiet:
            print("Wrote {}".format(args.output), file=sys.stderr)
    else:
        _stdout_write_utf8(rss)

    return 0


# -- CLI parser ----------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="harvester",
        description=(
            "Local-walk HTML extraction tool.\n"
            "\n"
            "Walks a directory tree of HTML, applies a config-driven\n"
            "extractor, and emits canonical artefacts: plain text\n"
            "(archivist-stampable), HTML fragment (RSS-embeddable),\n"
            "HTML standalone (archive-readable), and a metadata sidecar.\n"
            "\n"
            "Optionally aggregates harvested artefacts into RSS 2.0.\n"
            "\n"
            "The harvester does not fetch over the network or rewrite\n"
            "assets. Those concerns belong to the crawler tool."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = p.add_subparsers(dest="command")

    pw = sub.add_parser("walk",
        help="harvest a directory tree of HTML files",
        description="Walk a directory and emit canonical artefacts.")
    pw.add_argument("input_dir", help="directory to walk")
    pw.add_argument("output_dir", help="directory to write artefacts to")
    pw.add_argument("-c", "--config", default="harvester.cfg",
        help="extractor config (default: ./harvester.cfg)")
    pw.add_argument("-p", "--pattern", default=None,
        help="restrict to files matching glob (default: from config)")
    pw.add_argument("-q", "--quiet", action="store_true",
        help="suppress progress messages (cron-friendly)")
    pw.add_argument("-n", "--dry-run", action="store_true",
        help="parse but do not write output")
    pw.set_defaults(func=cmd_walk)

    pe = sub.add_parser("extract",
        help="extract canonical text from a single HTML file",
        description="Extract canonical text from one file to stdout.")
    pe.add_argument("file", help="HTML file (or - for stdin)")
    pe.add_argument("-c", "--config", default="harvester.cfg")
    pe.set_defaults(func=cmd_extract)

    pf = sub.add_parser("feed",
        help="aggregate harvested artefacts into RSS 2.0",
        description="Build an RSS feed from a harvested directory.")
    pf.add_argument("harvested_dir", help="directory of harvested artefacts")
    pf.add_argument("-o", "--output", default=None,
        help="output file (default: stdout)")
    pf.add_argument("-c", "--config", default="harvester.cfg")
    pf.add_argument("-q", "--quiet", action="store_true")
    pf.set_defaults(func=cmd_feed)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {}".format(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
