#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
texts.py — Project Gutenberg canonical text mirror

Fetches, caches, and serves a curated corpus of canonical texts from
Project Gutenberg for offline use, Vesper archival, and mnemonic anchor
purposes.

A memorised line from any of these texts — the Bible, the complete works
of Shakespeare, the Tao Te Ching, the Analects, the Mahabharata — can
serve as a verse mnemonic for prime derivation. The texts are the key
corpus. They are indestructible.

Usage:
    python texts.py list
    python texts.py show <id>
    python texts.py fetch [<id> ...] [--all] [--force]
    python texts.py verify [<id> ...]
    python texts.py search <query>
    python texts.py excerpt <id> --lines N [--offset N]

Examples:
    python texts.py list
    python texts.py show bible-kjv
    python texts.py fetch bible-kjv shakespeare
    python texts.py fetch --all
    python texts.py verify
    python texts.py search "Tao"
    python texts.py excerpt bible-kjv --lines 3 --offset 1000

Fetched texts are stored in docs/texts/ as plain UTF-8 files.
Each file is self-describing and suitable for Vesper archival.

Project Gutenberg Terms of Use: https://www.gutenberg.org/policy/terms_of_use
Texts used with attribution per Gutenberg terms. Most are public domain.
Be polite — the tool sleeps between requests.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT (this tool); texts copyright their respective authors/translators
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import os
import re
import sys
import time

PY2 = (sys.version_info[0] == 2)

if PY2:
    from urllib2 import urlopen, Request, URLError, HTTPError  # noqa
    import io
    open = io.open
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError               # noqa

# ── Curated text registry ─────────────────────────────────────────────────────
#
# Selection criteria:
#   - Canonical, widely-known texts with high cultural durability
#   - Geographically and linguistically diverse
#   - Suitable as mnemonic anchors (memorable, widely memorised)
#   - Public domain on Project Gutenberg
#   - Stable Gutenberg IDs (not recently added)
#
# The Gutenberg cache URL pattern is:
#   https://www.gutenberg.org/cache/epub/<ID>/pg<ID>.txt
#
# To add a text: add an entry here, then run: python texts.py fetch <id>

TEXTS = {

    # ── Abrahamic scripture ───────────────────────────────────────────────────
    "bible-kjv": {
        "gutenberg_id": 10,
        "title":        "The Bible (King James Version)",
        "author":       "Various",
        "language":     "en",
        "region":       "Middle East / global",
        "notes":        "The KJV. Billions of memorised lines. Strongest mnemonic anchor in the corpus.",
        "tags":         ["scripture", "english", "mnemonic-anchor"],
    },
    "quran-english": {
        "gutenberg_id": 2800,
        "title":        "The Koran (Rodwell translation)",
        "author":       "J.M. Rodwell (trans.)",
        "language":     "en",
        "region":       "Middle East / global",
        "notes":        "English translation. Arabic original memorised by hundreds of millions.",
        "tags":         ["scripture", "english", "mnemonic-anchor"],
    },

    # ── European literature ───────────────────────────────────────────────────
    "shakespeare": {
        "gutenberg_id": 100,
        "title":        "The Complete Works of William Shakespeare",
        "author":       "William Shakespeare",
        "language":     "en",
        "region":       "England",
        "notes":        "Complete works. ~5MB. The largest single mnemonic anchor in the corpus.",
        "tags":         ["literature", "english", "drama", "poetry", "mnemonic-anchor"],
    },
    "dante-inferno": {
        "gutenberg_id": 8800,
        "title":        "Inferno (Divine Comedy Part I)",
        "author":       "Dante Alighieri",
        "language":     "en",
        "region":       "Italy",
        "notes":        "Longfellow translation. Nel mezzo del cammin di nostra vita.",
        "tags":         ["literature", "italian", "poetry"],
    },
    "goethe-faust": {
        "gutenberg_id": 14591,
        "title":        "Faust (Part I)",
        "author":       "Johann Wolfgang von Goethe",
        "language":     "en",
        "region":       "Germany",
        "notes":        "Bayard Taylor translation.",
        "tags":         ["literature", "german", "drama"],
    },
    "cervantes-quixote": {
        "gutenberg_id": 996,
        "title":        "Don Quixote",
        "author":       "Miguel de Cervantes",
        "language":     "en",
        "region":       "Spain",
        "notes":        "Ormsby translation. In a village of La Mancha...",
        "tags":         ["literature", "spanish", "novel"],
    },
    "hugo-miserables": {
        "gutenberg_id": 135,
        "title":        "Les Misérables",
        "author":       "Victor Hugo",
        "language":     "en",
        "region":       "France",
        "notes":        "Hapgood translation.",
        "tags":         ["literature", "french", "novel"],
    },
    "dostoevsky-brothers": {
        "gutenberg_id": 28054,
        "title":        "The Brothers Karamazov",
        "author":       "Fyodor Dostoevsky",
        "language":     "en",
        "region":       "Russia",
        "notes":        "Garnett translation.",
        "tags":         ["literature", "russian", "novel"],
    },
    "tolstoy-war-peace": {
        "gutenberg_id": 2600,
        "title":        "War and Peace",
        "author":       "Leo Tolstoy",
        "language":     "en",
        "region":       "Russia",
        "notes":        "Maude translation. ~3MB.",
        "tags":         ["literature", "russian", "novel"],
    },
    "homer-iliad": {
        "gutenberg_id": 2199,
        "title":        "The Iliad",
        "author":       "Homer",
        "language":     "en",
        "region":       "Ancient Greece",
        "notes":        "Samuel Butler translation. Sing, O goddess, the anger of Achilles.",
        "tags":         ["literature", "greek", "epic", "mnemonic-anchor"],
    },
    "homer-odyssey": {
        "gutenberg_id": 1727,
        "title":        "The Odyssey",
        "author":       "Homer",
        "language":     "en",
        "region":       "Ancient Greece",
        "notes":        "Samuel Butler translation. Tell me, O muse, of that ingenious hero.",
        "tags":         ["literature", "greek", "epic", "mnemonic-anchor"],
    },
    "virgil-aeneid": {
        "gutenberg_id": 228,
        "title":        "The Aeneid",
        "author":       "Virgil",
        "language":     "en",
        "region":       "Ancient Rome",
        "notes":        "Dryden translation. Arms, and the man I sing.",
        "tags":         ["literature", "latin", "epic"],
    },
    "chaucer-tales": {
        "gutenberg_id": 2383,
        "title":        "The Canterbury Tales",
        "author":       "Geoffrey Chaucer",
        "language":     "en",
        "region":       "England",
        "notes":        "Middle English. Whan that Aprill with his shoures soote.",
        "tags":         ["literature", "english", "poetry"],
    },

    # ── British and American novel ────────────────────────────────────────────
    "austen-pride": {
        "gutenberg_id": 1342,
        "title":        "Pride and Prejudice",
        "author":       "Jane Austen",
        "language":     "en",
        "region":       "England",
        "notes":        "It is a truth universally acknowledged.",
        "tags":         ["literature", "english", "novel", "mnemonic-anchor"],
    },
    "dickens-tale": {
        "gutenberg_id": 98,
        "title":        "A Tale of Two Cities",
        "author":       "Charles Dickens",
        "language":     "en",
        "region":       "England",
        "notes":        "It was the best of times, it was the worst of times.",
        "tags":         ["literature", "english", "novel", "mnemonic-anchor"],
    },
    "melville-moby": {
        "gutenberg_id": 2701,
        "title":        "Moby Dick",
        "author":       "Herman Melville",
        "language":     "en",
        "region":       "USA",
        "notes":        "Call me Ishmael.",
        "tags":         ["literature", "english", "novel", "mnemonic-anchor"],
    },
    "shelley-frankenstein": {
        "gutenberg_id": 84,
        "title":        "Frankenstein",
        "author":       "Mary Shelley",
        "language":     "en",
        "region":       "England",
        "notes":        "1818 first edition text.",
        "tags":         ["literature", "english", "novel"],
    },
    "twain-huckleberry": {
        "gutenberg_id": 76,
        "title":        "Adventures of Huckleberry Finn",
        "author":       "Mark Twain",
        "language":     "en",
        "region":       "USA",
        "notes":        "You don't know about me without you have read a book.",
        "tags":         ["literature", "english", "novel"],
    },

    # ── East Asian literature and philosophy ──────────────────────────────────
    "confucius-analects": {
        "gutenberg_id": 4094,
        "title":        "The Analects of Confucius",
        "author":       "Confucius",
        "language":     "en",
        "region":       "China",
        "notes":        "Legge translation. Is he not a man of complete virtue?",
        "tags":         ["philosophy", "chinese", "mnemonic-anchor"],
    },
    "laozi-tao": {
        "gutenberg_id": 216,
        "title":        "Tao Te Ching",
        "author":       "Laozi",
        "language":     "en",
        "region":       "China",
        "notes":        "The Tao that can be told is not the eternal Tao.",
        "tags":         ["philosophy", "chinese", "poetry", "mnemonic-anchor"],
    },
    "sunzi-art-war": {
        "gutenberg_id": 132,
        "title":        "The Art of War",
        "author":       "Sun Tzu",
        "language":     "en",
        "region":       "China",
        "notes":        "Lionel Giles translation.",
        "tags":         ["philosophy", "chinese", "strategy", "mnemonic-anchor"],
    },
    "murasaki-genji": {
        "gutenberg_id": 5125,
        "title":        "The Tale of Genji",
        "author":       "Murasaki Shikibu",
        "language":     "en",
        "region":       "Japan",
        "notes":        "Suematsu translation. The world's first novel.",
        "tags":         ["literature", "japanese", "novel"],
    },

    # ── South Asian literature ────────────────────────────────────────────────
    "tagore-gitanjali": {
        "gutenberg_id": 7164,
        "title":        "Gitanjali (Song Offerings)",
        "author":       "Rabindranath Tagore",
        "language":     "en",
        "region":       "India",
        "notes":        "Nobel Prize 1913. Thou hast made me endless.",
        "tags":         ["literature", "bengali", "poetry", "mnemonic-anchor"],
    },
    "upanishads": {
        "gutenberg_id": 3283,
        "title":        "The Upanishads (selections)",
        "author":       "Various",
        "language":     "en",
        "region":       "India",
        "notes":        "Max Müller translation.",
        "tags":         ["scripture", "sanskrit", "philosophy"],
    },
    "kalidasa-shakuntala": {
        "gutenberg_id": 7785,
        "title":        "Shakuntala",
        "author":       "Kalidasa",
        "language":     "en",
        "region":       "India",
        "notes":        "Jones translation.",
        "tags":         ["literature", "sanskrit", "drama"],
    },

    # ── African and Middle Eastern literature ─────────────────────────────────
    "arabian-nights": {
        "gutenberg_id": 128,
        "title":        "One Thousand and One Nights (Arabian Nights)",
        "author":       "Various",
        "language":     "en",
        "region":       "Middle East / South Asia",
        "notes":        "Lane translation selections.",
        "tags":         ["literature", "arabic", "narrative"],
    },
    "omar-khayyam": {
        "gutenberg_id": 246,
        "title":        "The Rubaiyat of Omar Khayyam",
        "author":       "Omar Khayyam",
        "language":     "en",
        "region":       "Persia",
        "notes":        "FitzGerald translation. A Jug of Wine, a Loaf of Bread—and Thou.",
        "tags":         ["literature", "persian", "poetry", "mnemonic-anchor"],
    },
    "rumi-masnavi": {
        "gutenberg_id": 46328,
        "title":        "The Masnavi (Book I)",
        "author":       "Jalal ad-Din Rumi",
        "language":     "en",
        "region":       "Persia",
        "notes":        "Whinfield translation.",
        "tags":         ["literature", "persian", "poetry", "mnemonic-anchor"],
    },

    # ── Philosophy ────────────────────────────────────────────────────────────
    "plato-republic": {
        "gutenberg_id": 1497,
        "title":        "The Republic",
        "author":       "Plato",
        "language":     "en",
        "region":       "Ancient Greece",
        "notes":        "Jowett translation.",
        "tags":         ["philosophy", "greek"],
    },
    "aristotle-nicomachean": {
        "gutenberg_id": 8438,
        "title":        "Nicomachean Ethics",
        "author":       "Aristotle",
        "language":     "en",
        "region":       "Ancient Greece",
        "notes":        "Ross translation.",
        "tags":         ["philosophy", "greek"],
    },
    "aurelius-meditations": {
        "gutenberg_id": 2680,
        "title":        "Meditations",
        "author":       "Marcus Aurelius",
        "language":     "en",
        "region":       "Ancient Rome",
        "notes":        "Long translation. You have power over your mind, not outside events.",
        "tags":         ["philosophy", "latin", "stoic", "mnemonic-anchor"],
    },
    "machiavelli-prince": {
        "gutenberg_id": 1232,
        "title":        "The Prince",
        "author":       "Niccolò Machiavelli",
        "language":     "en",
        "region":       "Italy",
        "notes":        "Marriott translation.",
        "tags":         ["philosophy", "italian", "politics"],
    },

    # ── Science and mathematics ───────────────────────────────────────────────
    "darwin-origin": {
        "gutenberg_id": 1228,
        "title":        "On the Origin of Species",
        "author":       "Charles Darwin",
        "language":     "en",
        "region":       "England",
        "notes":        "6th edition. There is grandeur in this view of life.",
        "tags":         ["science", "english", "mnemonic-anchor"],
    },
    "wells-time-machine": {
        "gutenberg_id": 35,
        "title":        "The Time Machine",
        "author":       "H.G. Wells",
        "language":     "en",
        "region":       "England",
        "notes":        "The first great time travel story. The Eloi and the Morlocks.",
        "tags":         ["literature", "science-fiction", "english"],
    },
    "kafka-metamorphosis": {
        "gutenberg_id": 5200,
        "title":        "Metamorphosis",
        "author":       "Franz Kafka",
        "language":     "en",
        "region":       "Czech Republic / Austria",
        "notes":        "Wyllie translation. As Gregor Samsa awoke one morning from "
                        "uneasy dreams he found himself transformed into a gigantic insect.",
        "tags":         ["literature", "german", "novella", "mnemonic-anchor"],
    },
    "ibn-battuta-travels": {
        "gutenberg_id": 37279,
        "title":        "Travels in Asia and Africa (selections)",
        "author":       "Ibn Battuta",
        "language":     "en",
        "region":       "Morocco / global",
        "notes":        "Gibb translation. The greatest medieval traveller — covered "
                        "75,000 miles across the Islamic world, Africa, and Asia.",
        "tags":         ["travel", "arabic", "history"],
    },
    "poe-tales": {
        "gutenberg_id": 2148,
        "title":        "Tales of Mystery and Imagination",
        "author":       "Edgar Allan Poe",
        "language":     "en",
        "region":       "USA",
        "notes":        "True — nervous — very, very dreadfully nervous I had been.",
        "tags":         ["literature", "english", "short-fiction", "mnemonic-anchor"],
    },
    "stapledon-starmaker": {
        "gutenberg_id": None,
        "url":          "https://gutenberg.net.au/ebooks06/0601841.txt",
        "title":        "Star Maker",
        "author":       "Olaf Stapledon",
        "language":     "en",
        "region":       "England",
        "notes":        "Project Gutenberg Australia. One tremulous arrow of light, "
                        "projected how many thousands of years ago, now stung my nerves "
                        "with vision, and my heart with fear. Freeman Dyson credited this "
                        "book with inspiring the Dyson sphere.",
        "tags":         ["literature", "science-fiction", "philosophy", "cosmology",
                         "mnemonic-anchor"],
    },

    # ── Poetry ────────────────────────────────────────────────────────────────
    "whitman-leaves": {
        "gutenberg_id": 1322,
        "title":        "Leaves of Grass",
        "author":       "Walt Whitman",
        "language":     "en",
        "region":       "USA",
        "notes":        "I sing myself. And what I assume you shall assume.",
        "tags":         ["poetry", "english", "mnemonic-anchor"],
    },
    "dickinson-poems": {
        "gutenberg_id": 12242,
        "title":        "Poems by Emily Dickinson",
        "author":       "Emily Dickinson",
        "language":     "en",
        "region":       "USA",
        "notes":        "Because I could not stop for Death.",
        "tags":         ["poetry", "english", "mnemonic-anchor"],
    },
    "blake-songs": {
        "gutenberg_id": 1934,
        "title":        "Songs of Innocence and Experience",
        "author":       "William Blake",
        "language":     "en",
        "region":       "England",
        "notes":        "Tyger, Tyger, burning bright.",
        "tags":         ["poetry", "english", "mnemonic-anchor"],
    },
    "keats-poems": {
        "gutenberg_id": 23,
        "title":        "Poems of John Keats",
        "author":       "John Keats",
        "language":     "en",
        "region":       "England",
        "notes":        "A thing of beauty is a joy for ever.",
        "tags":         ["poetry", "english", "mnemonic-anchor"],
    },
}

GUTENBERG_BASE     = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
GUTENBERG_BASE_ALT = "https://www.gutenberg.org/files/{id}/{id}-0.txt"
USER_AGENT         = "Crowsong/1.0 (trey@propertools.be; Gutenberg mirror for offline use)"
REQUEST_DELAY      = 3.0   # seconds between requests — be polite
DEFAULT_DIR        = os.path.join("docs", "texts")


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch(url, retries=3):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                response = urlopen(req, timeout=60)
                body = response.read()
                return body.decode("utf-8", errors="replace")
            else:
                with urlopen(req, timeout=60) as response:
                    return response.read().decode("utf-8", errors="replace")
        except (URLError, HTTPError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed to fetch {0}: {1}".format(url, last_err))


# ── Gutenberg text cleaning ───────────────────────────────────────────────────

def _strip_gutenberg_header_footer(text):
    """
    Strip the standard Project Gutenberg header and footer boilerplate.
    The actual text lives between these markers.
    """
    # Header ends at the first occurrence of one of these markers
    header_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "***START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
        "*END*THE SMALL PRINT",
    ]
    # Footer begins at the first occurrence of one of these markers
    footer_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "***END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
        "End of the Project Gutenberg",
        "End of Project Gutenberg",
    ]

    start = 0
    for marker in header_markers:
        idx = text.find(marker)
        if idx != -1:
            # Advance past the marker line
            start = text.find("\n", idx) + 1
            break

    end = len(text)
    for marker in footer_markers:
        idx = text.find(marker, start)
        if idx != -1:
            end = idx
            break

    # Normalise line endings before returning — Gutenberg files often use
    # CRLF. Python's open(..., "r") normalises CRLF->LF on read, so we
    # must normalise here too, otherwise the SHA256 computed at write time
    # won't match the SHA256 computed at verify time.
    return text[start:end].replace("\r\n", "\n").replace("\r", "\n").strip()


# ── File format ───────────────────────────────────────────────────────────────

def make_text_file(text_id, body, local_meta):
    fetched   = time.strftime("%Y-%m-%d")
    sha256    = hashlib.sha256(body.encode("utf-8")).hexdigest()
    char_count = len(body)
    line_count = body.count("\n")

    lines = [
        "# {title}".format(**local_meta),
        "#",
        "# Author:    {author}".format(**local_meta),
        "# Language:  {language}".format(**local_meta),
        "# Region:    {region}".format(**local_meta),
        "# Source:    Project Gutenberg #{gutenberg_id}".format(**local_meta),
        "#            https://www.gutenberg.org/ebooks/{gutenberg_id}".format(
            **local_meta),
        "# Fetched:   {fetched}".format(fetched=fetched),
        "# Chars:     {chars:,}".format(chars=char_count),
        "# Lines:     {lines:,}".format(lines=line_count),
        "# SHA256:    {sha256}".format(sha256=sha256),
        "# Tags:      {tags}".format(tags=", ".join(local_meta.get("tags", []))),
        "# Notes:     {notes}".format(**local_meta),
        "#",
        "# Text is in the public domain per Project Gutenberg.",
        "# https://www.gutenberg.org/policy/terms_of_use",
        "#",
        "",
    ]
    return "\n".join(lines) + body + "\n"


def parse_text_file(path):
    sha256_declared = None
    char_declared   = None
    title           = None

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    for line in raw.splitlines():
        if line.startswith("# ") and title is None and " — " not in line \
                and not any(k in line for k in
                            ["Author", "Language", "Region", "Source",
                             "Fetched", "Chars", "Lines", "SHA256",
                             "Tags", "Notes", "Text", "http"]):
            title = line[2:].strip()
        if "SHA256:" in line:
            sha256_declared = line.split("SHA256:")[-1].strip()

    # Body starts after the header block (first blank line after comments)
    in_header = True
    body_lines = []
    for line in raw.splitlines():
        if in_header and not line.startswith("#"):
            in_header = False
        if not in_header:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    sha256_actual = hashlib.sha256(body.encode("utf-8")).hexdigest()

    return {
        "title":           title,
        "sha256_declared": sha256_declared,
        "sha256_actual":   sha256_actual,
        "sha256_ok":       sha256_actual == sha256_declared,
        "char_count":      len(body),
        "line_count":      body.count("\n"),
    }


# ── File paths ────────────────────────────────────────────────────────────────

def text_path(text_id, out_dir):
    return os.path.join(out_dir, "{0}.txt".format(text_id))

def is_cached(text_id, out_dir):
    return os.path.isfile(text_path(text_id, out_dir))


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_list():
    fmt = "{:<30}  {:<45}  {}"
    print(fmt.format("ID", "Title", "Tags"))
    print("-" * 90)
    for text_id, meta in sorted(TEXTS.items()):
        tags = ", ".join(meta.get("tags", []))
        print(fmt.format(
            text_id,
            meta["title"][:44],
            tags[:35]))
    print()
    print("{0} texts in registry.".format(len(TEXTS)))
    print()
    regions = sorted(set(m["region"].split(" /")[0] for m in TEXTS.values()))
    print("Regions: " + ", ".join(regions))


def cmd_show(text_id, out_dir):
    meta = TEXTS.get(text_id)
    if not meta:
        print("Error: unknown text ID '{0}'".format(text_id), file=sys.stderr)
        print("Run: python texts.py list", file=sys.stderr)
        return 1

    print("ID:         {0}".format(text_id))
    print("Title:      {0}".format(meta["title"]))
    print("Author:     {0}".format(meta["author"]))
    print("Language:   {0}".format(meta["language"]))
    print("Region:     {0}".format(meta["region"]))
    if meta.get("url"):
        print("Source:     {0}".format(meta["url"]))
    elif meta.get("gutenberg_id"):
        print("Gutenberg:  https://www.gutenberg.org/ebooks/{0}".format(
            meta["gutenberg_id"]))
    print("Tags:       {0}".format(", ".join(meta.get("tags", []))))
    print("Notes:      {0}".format(meta["notes"]))

    path = text_path(text_id, out_dir)
    if is_cached(text_id, out_dir):
        parsed = parse_text_file(path)
        print("Cached:     yes ({0:,} chars, {1:,} lines)".format(
            parsed["char_count"], parsed["line_count"]))
        print("SHA256:     {0}".format(parsed["sha256_actual"]))
        print("Valid:      {0}".format("yes" if parsed["sha256_ok"] else "NO — MISMATCH"))
    else:
        print("Cached:     no  (run: python texts.py fetch {0})".format(text_id))
    return 0


def cmd_fetch(ids, out_dir, force=False, fetch_all=False):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    if fetch_all or not ids:
        targets = list(TEXTS.keys())
    else:
        targets = ids

    unknown = [i for i in targets if i not in TEXTS]
    if unknown:
        print("Error: unknown text IDs: {0}".format(", ".join(unknown)),
              file=sys.stderr)
        return 1

    errors = 0
    for i, text_id in enumerate(sorted(targets)):
        path = text_path(text_id, out_dir)

        if is_cached(text_id, out_dir) and not force:
            print("  SKIP  {0} (cached; use --force to re-fetch)".format(text_id))
            continue

        meta = TEXTS[text_id]
        if meta.get("url"):
            url = meta["url"]
        else:
            url = GUTENBERG_BASE.format(id=meta["gutenberg_id"])
        print("  FETCH {0} ({1}) ...".format(text_id, meta["title"][:40]),
              end="")
        sys.stdout.flush()

        try:
            raw  = _fetch(url)
            body = _strip_gutenberg_header_footer(raw)

            if len(body) < 1000:
                raise ValueError(
                    "suspiciously short after stripping ({0} chars)".format(
                        len(body)))

            content = make_text_file(text_id, body, meta)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            print(" {0:,} chars".format(len(body)))
            if i < len(targets) - 1:
                time.sleep(REQUEST_DELAY)

        except (IOError, ValueError) as err:
            print(" FAIL: {0}".format(err))
            errors += 1

    return 0 if errors == 0 else 1


def cmd_verify(ids, out_dir):
    if ids:
        targets = ids
    else:
        if not os.path.isdir(out_dir):
            print("No cached texts to verify.")
            return 0
        targets = sorted(
            f[:-4] for f in os.listdir(out_dir)
            if f.endswith(".txt") and f in
            {k + ".txt" for k in TEXTS})

    if not targets:
        print("No cached texts to verify.")
        return 0

    passed = 0
    failed = 0
    for text_id in sorted(targets):
        path = text_path(text_id, out_dir)
        if not os.path.isfile(path):
            print("  MISS  {0}".format(text_id))
            failed += 1
            continue
        parsed = parse_text_file(path)
        if parsed["sha256_ok"]:
            print("  PASS  {0} ({1:,} chars)".format(
                text_id, parsed["char_count"]))
            passed += 1
        else:
            print("  FAIL  {0} — SHA256 mismatch".format(text_id))
            print("        declared: {0}".format(parsed["sha256_declared"]))
            print("        actual:   {0}".format(parsed["sha256_actual"]))
            failed += 1

    print()
    print("Results: {0} passed, {1} failed".format(passed, failed))
    return 0 if failed == 0 else 1


def cmd_search(query, out_dir):
    """Search registry metadata (not full text)."""
    q = query.lower()
    results = []
    for text_id, meta in sorted(TEXTS.items()):
        haystack = " ".join([
            text_id,
            meta["title"],
            meta["author"],
            meta["language"],
            meta["region"],
            meta["notes"],
            " ".join(meta.get("tags", [])),
        ]).lower()
        if q in haystack:
            results.append((text_id, meta))

    if not results:
        print("No results for '{0}'.".format(query))
        return 0

    for text_id, meta in results:
        cached = "✓" if is_cached(text_id, out_dir) else " "
        print("[{cached}] {id:<30}  {title}".format(
            cached=cached, id=text_id, title=meta["title"]))
    print()
    print("{0} result(s). [✓] = cached locally.".format(len(results)))
    return 0


def cmd_excerpt(text_id, out_dir, lines=10, offset=0):
    """Print a short excerpt from a cached text."""
    path = text_path(text_id, out_dir)
    if not is_cached(text_id, out_dir):
        print("Error: {0} not cached. Run: python texts.py fetch {0}".format(
            text_id), file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        all_lines = [l for l in f.read().splitlines()
                     if not l.startswith("#") and l.strip()]

    excerpt = all_lines[offset:offset + lines]
    meta    = TEXTS.get(text_id, {})
    print("# {0}".format(meta.get("title", text_id)))
    print("# Lines {0}–{1}".format(offset, offset + len(excerpt) - 1))
    print()
    for line in excerpt:
        print(line)
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Project Gutenberg canonical text mirror.\n"
            "Fetches and caches a curated corpus of canonical texts\n"
            "for offline use, Vesper archival, and mnemonic anchor purposes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python texts.py list\n"
            "  python texts.py show shakespeare\n"
            "  python texts.py fetch bible-kjv shakespeare\n"
            "  python texts.py fetch --all\n"
            "  python texts.py verify\n"
            "  python texts.py search Tao\n"
            "  python texts.py excerpt aurelius-meditations --lines 5\n"
        )
    )

    p.add_argument("--dir", default=DEFAULT_DIR, metavar="PATH",
        help="directory for cached text files (default: docs/texts/)")

    sub = p.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("list", help="list all texts in the registry")

    ps = sub.add_parser("show", help="show metadata for a text")
    ps.add_argument("id", help="text ID, e.g. shakespeare")

    pf = sub.add_parser("fetch",
        help="fetch texts from Project Gutenberg")
    pf.add_argument("ids", nargs="*",
        help="text IDs to fetch (default: fetch missing only)")
    pf.add_argument("--all", dest="fetch_all", action="store_true",
        help="fetch all texts in registry")
    pf.add_argument("--force", action="store_true",
        help="re-fetch even if cached")

    pv = sub.add_parser("verify",
        help="verify SHA256 of cached text files")
    pv.add_argument("ids", nargs="*",
        help="text IDs to verify (default: all cached)")

    pq = sub.add_parser("search",
        help="search registry metadata")
    pq.add_argument("query", help="search term")

    pe = sub.add_parser("excerpt",
        help="print a short excerpt from a cached text")
    pe.add_argument("id", help="text ID")
    pe.add_argument("--lines", type=int, default=10,
        help="number of lines to print (default: 10)")
    pe.add_argument("--offset", type=int, default=0,
        help="line offset into text (default: 0)")

    return p


def main():
    args   = build_parser().parse_args()
    out_dir = args.dir

    try:
        if args.command == "list":
            return cmd_list()
        if args.command == "show":
            return cmd_show(args.id, out_dir)
        if args.command == "fetch":
            return cmd_fetch(args.ids, out_dir,
                             force=args.force,
                             fetch_all=args.fetch_all)
        if args.command == "verify":
            return cmd_verify(args.ids, out_dir)
        if args.command == "search":
            return cmd_search(args.query, out_dir)
        if args.command == "excerpt":
            return cmd_excerpt(args.id, out_dir,
                               lines=args.lines,
                               offset=args.offset)
    except (IOError, KeyboardInterrupt) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
