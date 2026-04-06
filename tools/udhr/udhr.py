#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
udhr.py — UDHR PDF corpus mirror

Fetches and mirrors UDHR translation PDFs from OHCHR, organized on disk
by Unicode script family and language. Optionally extracts plain text
alongside each PDF using pdftotext (Poppler).

The registry of languages is built from a local registry.json, which is
populated by the `discover` subcommand. Run `discover` first to pull the
full language list (560+ translations) from OHCHR, then `fetch --all`.

Directory layout:

    docs/udhr/
        Latin/
            eng_English.pdf
            eng_English.txt         (if --extract)
            frn_French.pdf
            ...
        CJK/
            chn_Chinese-Simplified.pdf
            jpn_Japanese.pdf
            ...
        Arabic/
            arz_Arabic.pdf
            per_Persian.pdf
            ...

Filenames: {ohchr_code}_{Language-Name}.pdf

Source:
    https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/{code}.pdf
    Office of the High Commissioner for Human Rights (OHCHR)

Usage:
    python udhr.py discover [--registry PATH]   # build/update registry.json
    python udhr.py list [--script SCRIPT]
    python udhr.py fetch [<id> ...] [--all] [--force] [--extract]
    python udhr.py extract [<id> ...]
    python udhr.py verify [<id> ...]

Quick start:
    python udhr.py discover
    python udhr.py list
    python udhr.py fetch --all
    python udhr.py fetch --all --extract

Compatibility: Python 2.7+ / 3.x
Dependencies:  pdftotext (Poppler) for --extract / extract subcommand
Author: Proper Tools SRL
License: MIT (this tool); UDHR PDFs (c) OHCHR, freely redistributable
"""

from __future__ import print_function, unicode_literals

import argparse
import json
import os
import re
import subprocess
import sys
import time

PY2 = (sys.version_info[0] == 2)
if PY2:
    from urllib2 import urlopen, Request, URLError, HTTPError  # noqa
    string_types = (str, unicode)                               # noqa
else:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError               # noqa
    string_types = (str,)

OHCHR_PRIMARY   = ("https://www.ohchr.org/sites/default/files/"
                   "UDHR/Documents/UDHR_Translations/{code}.pdf")
OHCHR_SECONDARY = ("https://www.ohchr.org/EN/UDHR/Documents/"
                   "UDHR_Translations/{code}.pdf")

# OHCHR translations browse pages (A-D, E-H, etc.)
OHCHR_BROWSE = [
    "https://www.ohchr.org/EN/UDHR/Pages/SearchByLang.aspx",
    # Individual language pages follow the pattern:
    # https://www.ohchr.org/EN/UDHR/Pages/Language.aspx?LangID={code}
    # The PDF URL is always:
    # https://www.ohchr.org/EN/UDHR/Documents/UDHR_Translations/{code}.pdf
]

USER_AGENT    = ("Crowsong/1.0 (trey@propertools.be; "
                 "UDHR corpus for entropy analysis)")
REQUEST_DELAY = 2.0
DEFAULT_DIR   = os.path.join("docs", "udhr")
DEFAULT_REG   = "registry.json"

# ── Script classification heuristic ───────────────────────────────────────────
# Maps OHCHR language codes to script families for directory organisation.
# This is used when building from the discovered registry. We infer script
# from the Unicode block of the first non-ASCII character in the PDF, but
# for common languages we hard-code the answer to avoid a pdftotext dependency
# at discovery time.

KNOWN_SCRIPTS = {
    # Latin
    "eng": "Latin", "frn": "Latin", "spn": "Latin", "ger": "Latin",
    "por": "Latin", "ita": "Latin", "dut": "Latin", "pol": "Latin",
    "tur": "Latin", "vie": "Latin", "ind": "Latin", "swk": "Latin",
    "cze": "Latin", "slo": "Latin", "hun": "Latin", "ron": "Latin",
    "hrv": "Latin", "slv": "Latin", "fin": "Latin", "est": "Latin",
    "lat": "Latin", "lit": "Latin", "alb": "Latin", "mlt": "Latin",
    "afr": "Latin", "wel": "Latin", "gle": "Latin", "cat": "Latin",
    "glg": "Latin", "bsq": "Latin", "oci": "Latin", "isl": "Latin",
    "dan": "Latin", "nor": "Latin", "swe": "Latin",
    # Cyrillic
    "rus": "Cyrillic", "ukr": "Cyrillic", "bul": "Cyrillic",
    "srp": "Cyrillic", "mon": "Cyrillic", "bel": "Cyrillic",
    "mkd": "Cyrillic", "kaz": "Cyrillic", "kir": "Cyrillic",
    "uzb": "Cyrillic", "taj": "Cyrillic", "tuk": "Cyrillic",
    # Arabic script
    "arz": "Arabic",  "per": "Arabic",  "urd": "Arabic",
    "pus": "Arabic",  "kur": "Arabic",  "arb": "Arabic",
    # Hebrew
    "hbr": "Hebrew",  "ydd": "Hebrew",
    # Devanagari
    "hnd": "Devanagari", "nep": "Devanagari", "mar": "Devanagari",
    "san": "Devanagari",
    # Bengali / Assamese
    "bng": "Bengali", "asm": "Bengali",
    # South Indian
    "tam": "Tamil", "tel": "Telugu", "kan": "Kannada", "mal": "Malayalam",
    # Other Indic
    "gjr": "Gujarati", "pnj1": "Gurmukhi", "ory": "Oriya",
    "sin": "Sinhala",
    # Southeast Asian
    "tha": "Thai", "lao": "Lao", "khm": "Khmer", "mya": "Myanmar",
    # CJK
    "chn": "CJK", "cht": "CJK", "jpn": "CJK",
    # Hangul
    "kor": "Hangul",
    # Caucasian
    "kat": "Georgian", "arm": "Armenian",
    # Ethiopic
    "amh": "Ethiopic",
    # Greek
    "grk": "Greek",
    # Tibetan
    "tib": "Tibetan",
}

# ── Bootstrap registry (verified codes, used before discover is run) ──────────
BOOTSTRAP = [
    # (id, ohchr_code, display_name, script, region)
    ("eng",  "eng",  "English",             "Latin",      "Global"),
    ("frn",  "frn",  "French",              "Latin",      "Global"),
    ("spn",  "spn",  "Spanish",             "Latin",      "Global"),
    ("rus",  "rus",  "Russian",             "Cyrillic",   "Global"),
    ("chn",  "chn",  "Chinese-Simplified",  "CJK",        "East-Asia"),
    ("arz",  "arz",  "Arabic",              "Arabic",     "Global"),
    ("ger",  "ger",  "German",              "Latin",      "Europe"),
    ("por",  "por",  "Portuguese",          "Latin",      "Global"),
    ("ita",  "itn",  "Italian",             "Latin",      "Europe"),   # itn confirmed
    ("dut",  "dut",  "Dutch",               "Latin",      "Europe"),
    ("pol",  "pol",  "Polish",              "Latin",      "Europe"),   # unconfirmed; try pls
    ("tur",  "tur",  "Turkish",             "Latin",      "Middle-East"),  # unconfirmed; try trk
    ("vie",  "vie",  "Vietnamese",          "Latin",      "Southeast-Asia"),
    ("ind",  "ind",  "Indonesian",          "Latin",      "Southeast-Asia"),  # unconfirmed; try idn
    ("swk",  "swk",  "Swahili",             "Latin",      "East-Africa"),  # unconfirmed; try swa
    ("ukr",  "ukr",  "Ukrainian",           "Cyrillic",   "Europe"),
    ("bul",  "blg",  "Bulgarian",           "Cyrillic",   "Europe"),   # blg confirmed
    ("srp",  "srp",  "Serbian",             "Cyrillic",   "Europe"),   # unconfirmed; try src
    ("mon",  "mon",  "Mongolian",           "Cyrillic",   "Central-Asia"),  # unconfirmed; try mng
    ("per",  "per",  "Persian",             "Arabic",     "Middle-East"),   # unconfirmed; try prn
    ("urd",  "urd",  "Urdu",                "Arabic",     "South-Asia"),
    ("hbr",  "hbr",  "Hebrew",              "Hebrew",     "Middle-East"),
    ("ydd",  "ydd",  "Yiddish",             "Hebrew",     "Global"),
    ("hnd",  "hnd",  "Hindi",               "Devanagari", "South-Asia"),
    ("nep",  "nep",  "Nepali",              "Devanagari", "South-Asia"),
    ("mar",  "mar",  "Marathi",             "Devanagari", "South-Asia"),  # unconfirmed; try mrt
    ("bng",  "bng",  "Bengali",             "Bengali",    "South-Asia"),
    ("asm",  "asm",  "Assamese",            "Bengali",    "South-Asia"),
    ("tam",  "tam",  "Tamil",               "Tamil",      "South-Asia"),
    ("tel",  "tel",  "Telugu",              "Telugu",     "South-Asia"),   # unconfirmed; try tln
    ("kan",  "kan",  "Kannada",             "Kannada",    "South-Asia"),   # unconfirmed; try knd
    ("mal",  "mal",  "Malayalam",           "Malayalam",  "South-Asia"),   # unconfirmed; try mls
    ("gjr",  "gjr",  "Gujarati",            "Gujarati",   "South-Asia"),
    ("pnj1", "pnj1", "Punjabi-Gurmukhi",    "Gurmukhi",   "South-Asia"),
    ("ory",  "ory",  "Odia",                "Oriya",      "South-Asia"),
    ("sin",  "snh",  "Sinhala",             "Sinhala",    "South-Asia"),   # snh confirmed
    ("tha",  "thj",  "Thai",                "Thai",       "Southeast-Asia"),  # thj confirmed
    ("lao",  "lao",  "Lao",                 "Lao",        "Southeast-Asia"),  # unconfirmed; try lo1
    ("khm",  "khm",  "Khmer",               "Khmer",      "Southeast-Asia"),
    ("mya",  "mya",  "Burmese",             "Myanmar",    "Southeast-Asia"),  # unconfirmed; try brm
    ("cht",  "cht",  "Chinese-Traditional", "CJK",        "East-Asia"),   # unconfirmed; try zht
    ("jpn",  "jpn",  "Japanese",            "CJK",        "East-Asia"),
    ("kor",  "kor",  "Korean",              "Hangul",     "East-Asia"),   # unconfirmed; try krn
    ("kat",  "geo",  "Georgian",            "Georgian",   "Caucasus"),    # geo confirmed
    ("arm",  "arm",  "Armenian",            "Armenian",   "Caucasus"),
    ("amh",  "amh",  "Amharic",             "Ethiopic",   "East-Africa"),
    ("grk",  "grk",  "Greek",               "Greek",      "Europe"),
    ("tib",  "tib",  "Tibetan",             "Tibetan",    "Central-Asia"),
]


# ── Registry load/save ─────────────────────────────────────────────────────────

def _load_registry(reg_path):
    """
    Returns dict: id -> {code, name, script, region}.
    Falls back to BOOTSTRAP if registry.json doesn't exist.
    """
    if os.path.isfile(reg_path):
        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    # Bootstrap
    reg = {}
    for lang_id, code, name, script, region in BOOTSTRAP:
        reg[lang_id] = {"code": code, "name": name,
                        "script": script, "region": region}
    return reg


def _save_registry(reg, reg_path):
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=2, sort_keys=True)


# ── File paths ────────────────────────────────────────────────────────────────

def _pdf_path(entry, out_dir):
    return os.path.join(out_dir, entry["script"],
                        "{}_{}.pdf".format(entry["code"], entry["name"]))

def _txt_path(entry, out_dir):
    return _pdf_path(entry, out_dir)[:-4] + ".txt"

def _is_cached(entry, out_dir):
    return os.path.isfile(_pdf_path(entry, out_dir))

def _ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d)


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_url(url, retries=3, as_text=False):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            if PY2:
                r = urlopen(req, timeout=60)
                data = r.read()
            else:
                with urlopen(req, timeout=60) as r:
                    data = r.read()
            if as_text:
                return data.decode("utf-8", errors="replace")
            return data
        except (URLError, HTTPError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(REQUEST_DELAY * (attempt + 1))
    raise IOError("Failed: {} {}".format(url, last_err))


def _fetch_pdf(code):
    errors = []
    for pattern in (OHCHR_PRIMARY, OHCHR_SECONDARY):
        url = pattern.format(code=code)
        try:
            data = _fetch_url(url)
            if data[:4] == b"%PDF":
                return data, url
            errors.append("{}: not a PDF".format(url))
        except IOError as e:
            errors.append("{}: {}".format(url, e))
    raise IOError("Could not fetch PDF for code '{}'.\n  {}".format(
        code, "\n  ".join(errors)))


# ── Discovery ─────────────────────────────────────────────────────────────────

def _discover_from_ohchr(existing_reg):
    """
    Fetch the OHCHR browse-by-language page and extract (code, name) pairs.

    Strategy: OHCHR's SearchByLang page links to individual language pages
    at /EN/UDHR/Pages/Language.aspx?LangID={code}. We extract LangID values
    from the HTML and use those as the PDF codes.

    We try several OHCHR entry points in sequence.
    """
    found = {}   # code -> name

    sources = [
        "https://www.ohchr.org/EN/UDHR/Pages/SearchByLang.aspx",
        "https://www.ohchr.org/en/human-rights/universal-declaration/translations",
    ]

    for url in sources:
        try:
            html = _fetch_url(url, as_text=True)
            # Extract LangID=xxx from links
            codes = re.findall(r'LangID=([a-zA-Z0-9_]+)', html)
            if codes:
                print("  Found {} code references in {}".format(len(codes), url))
                for code in set(codes):
                    if code not in found:
                        found[code] = code  # name TBD
                break
        except IOError as e:
            print("  Could not reach {}: {}".format(url, e))

    return found


def _probe_codes(candidates, existing_reg, delay=REQUEST_DELAY):
    """
    For each candidate code, HEAD-request the primary PDF URL to confirm it
    exists. Returns dict: code -> True/False.
    Returns list of (code, confirmed) pairs.
    """
    results = {}
    known = {v["code"] for v in existing_reg.values()}
    to_probe = [c for c in candidates if c not in known]

    if not to_probe:
        print("  All candidates already in registry.")
        return results

    print("  Probing {} new codes...".format(len(to_probe)))
    for i, code in enumerate(sorted(to_probe)):
        url = OHCHR_PRIMARY.format(code=code)
        try:
            # Use HEAD to avoid downloading — but OHCHR doesn't always support HEAD
            # so we fetch just the first 8 bytes
            req = Request(url, headers={"User-Agent": USER_AGENT,
                                        "Range": "bytes=0-7"})
            if PY2:
                r = urlopen(req, timeout=15)
                data = r.read(8)
            else:
                with urlopen(req, timeout=15) as r:
                    data = r.read(8)
            results[code] = data[:4] == b"%PDF"
        except (URLError, HTTPError):
            results[code] = False

        if (i + 1) % 10 == 0:
            print("    {}/{}...".format(i + 1, len(to_probe)))
        if i < len(to_probe) - 1:
            time.sleep(delay)

    return results


# ── Probe candidates for unconfirmed codes ────────────────────────────────────
# For each registry ID whose OHCHR code is unconfirmed, list candidate codes
# to try in order. `python udhr.py probe` tries each candidate and updates the
# registry with the first one that serves a valid PDF.

PROBE_CANDIDATES = {
    "arz": ["arb", "ara", "arz"],       # Arabic: arz returns empty body
    "cht": ["zht", "tch", "cht"],       # Chinese Traditional
    "ind": ["idn", "inz", "ind"],       # Indonesian
    "kan": ["knd", "kan"],              # Kannada
    "kor": ["krn", "kor"],              # Korean
    "lao": ["lo1", "law", "lao"],       # Lao
    "mal": ["mls", "mlm", "mal"],       # Malayalam
    "mar": ["mrt", "mhi", "mar"],       # Marathi
    "mon": ["mng", "khk", "mon"],       # Mongolian
    "mya": ["brm", "bur", "mya"],       # Burmese
    "per": ["prn", "far", "per"],       # Persian
    "pol": ["pls", "pol"],              # Polish
    "srp": ["src", "scc", "srp"],       # Serbian (Cyrillic)
    "swk": ["swa", "swh", "swk"],       # Swahili
    "tel": ["tln", "tlg", "tel"],       # Telugu
    "tib": ["tbt", "bod", "tib"],       # Tibetan
    "tur": ["trk", "tuk", "tur"],       # Turkish
}


def cmd_probe(ids, reg, reg_path, delay=2.0):
    """
    For each language ID in PROBE_CANDIDATES (or the given ids), try each
    candidate code in order against both OHCHR URL patterns. Update the
    registry with the first confirmed code and save registry.json.
    """
    targets = ids if ids else sorted(PROBE_CANDIDATES.keys())
    unknown = [i for i in targets if i not in PROBE_CANDIDATES and i not in reg]
    if unknown:
        print("Unknown IDs: {}".format(", ".join(unknown)), file=sys.stderr)
        return 1

    updated = 0
    errors  = 0

    for lang_id in targets:
        candidates = PROBE_CANDIDATES.get(lang_id, [])
        if not candidates:
            print("  SKIP  {}  (no candidates defined)".format(lang_id))
            continue

        name   = reg[lang_id]["name"]   if lang_id in reg else lang_id
        script = reg[lang_id]["script"] if lang_id in reg else "Unknown"
        print("  PROBE {}  ({})  candidates: {}".format(
            lang_id, name, candidates))
        sys.stdout.flush()

        found = None
        for code in candidates:
            for pattern in (OHCHR_PRIMARY, OHCHR_SECONDARY):
                url = pattern.format(code=code)
                try:
                    req = Request(url, headers={
                        "User-Agent": USER_AGENT,
                        "Range": "bytes=0-7",
                    })
                    if PY2:
                        r = urlopen(req, timeout=15)
                        data = r.read(8)
                    else:
                        with urlopen(req, timeout=15) as r:
                            data = r.read(8)
                    if data[:4] == b"%PDF":
                        found = code
                        break
                except (URLError, HTTPError):
                    pass
            if found:
                break
            time.sleep(delay)

        if found:
            old_code = reg[lang_id]["code"] if lang_id in reg else "?"
            reg[lang_id]["code"] = found
            if old_code != found:
                print("    → {}  (was {})  ✓".format(found, old_code))
            else:
                print("    → {}  (unchanged)  ✓".format(found))
            updated += 1
        else:
            print("    → FAIL  (none of {} resolved)".format(candidates))
            errors += 1

    if updated:
        _save_registry(reg, reg_path)
        print()
        print("Registry updated: {} confirmed, {} failed → {}".format(
            updated, errors, reg_path))
    else:
        print()
        print("No updates. {} failed.".format(errors))

    return 0 if errors == 0 else 1


def cmd_discover(reg_path, out_dir, probe=False):
    """
    Build/update registry.json by scraping OHCHR.

    Phase 1: Fetch OHCHR browse page, extract LangID codes.
    Phase 2: For each new code, optionally probe the PDF URL.
    Phase 3: Save registry.json.

    The script family is inferred from KNOWN_SCRIPTS; unknown languages
    get script="Unknown" and can be hand-corrected in registry.json.
    """
    existing = _load_registry(reg_path)
    print("Existing registry: {} entries".format(len(existing)))

    print("Fetching OHCHR language index...")
    found = _discover_from_ohchr(existing)

    if not found:
        print("Could not retrieve language list from OHCHR.")
        print("Tip: run with network access, or add entries to registry.json manually.")
        return 1

    # Merge: codes already in registry are kept as-is
    existing_codes = {v["code"] for v in existing.values()}
    new_codes = [c for c in found if c not in existing_codes]
    print("New codes found: {}".format(len(new_codes)))

    if probe and new_codes:
        print("Probing PDF URLs for new codes (this takes a while)...")
        probe_results = _probe_codes(new_codes, existing)
        confirmed = [c for c, ok in probe_results.items() if ok]
        rejected  = [c for c, ok in probe_results.items() if not ok]
        print("  Confirmed: {}  Rejected: {}".format(
            len(confirmed), len(rejected)))
        new_codes = confirmed

    added = 0
    for code in new_codes:
        lang_id = code  # use code as id unless collision
        if lang_id in existing:
            lang_id = code + "_discovered"
        script = KNOWN_SCRIPTS.get(code, "Unknown")
        name   = found.get(code, code)
        existing[lang_id] = {
            "code": code, "name": name,
            "script": script, "region": "Unknown",
        }
        added += 1

    _save_registry(existing, reg_path)
    print("Registry saved: {} total entries ({} added) → {}".format(
        len(existing), added, reg_path))
    print()
    print("Next steps:")
    print("  python udhr.py list                    # review")
    print("  python udhr.py fetch --all             # download all PDFs")
    print("  python udhr.py fetch --all --extract   # + pdftotext")
    return 0


# ── pdftotext ─────────────────────────────────────────────────────────────────

def _pdftotext_ok():
    try:
        subprocess.check_output(["pdftotext", "-v"], stderr=subprocess.STDOUT)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def _extract_text(pdf_path, txt_path):
    try:
        subprocess.check_call(
            ["pdftotext", "-enc", "UTF-8", "-nopgbrk", pdf_path, txt_path],
            stderr=subprocess.DEVNULL)
        if os.path.isfile(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
                return len(f.read().strip()) > 100
        return False
    except (subprocess.CalledProcessError, OSError):
        return False


# ── CLI commands ──────────────────────────────────────────────────────────────

def cmd_list(reg, script_filter=None):
    by_script = {}
    for lang_id, entry in sorted(reg.items()):
        script = entry.get("script", "Unknown")
        if script_filter and script_filter.lower() not in script.lower():
            continue
        by_script.setdefault(script, []).append(
            (lang_id, entry["code"], entry["name"],
             entry.get("region", "")))

    total = 0
    for script in sorted(by_script):
        print("  {}".format(script))
        for lang_id, code, name, region in sorted(by_script[script],
                                                   key=lambda x: x[2]):
            print("    {:<8}  {:<32}  {}".format(lang_id, name, region))
            total += 1
        print()
    print("{} languages, {} scripts.".format(total, len(by_script)))


def cmd_fetch(ids, reg, out_dir, force=False, fetch_all=False, extract=False):
    targets = sorted(reg.keys()) if (fetch_all or not ids) else ids
    unknown = [i for i in targets if i not in reg]
    if unknown:
        print("Unknown IDs: {}".format(", ".join(unknown)), file=sys.stderr)
        return 1

    if extract and not _pdftotext_ok():
        print("Warning: pdftotext not found; --extract skipped.", file=sys.stderr)
        extract = False

    errors = 0
    for i, lang_id in enumerate(targets):
        entry = reg[lang_id]
        code  = entry["code"]
        name  = entry["name"]
        script = entry.get("script", "Unknown")
        pdf   = _pdf_path(entry, out_dir)
        label = "{}/{}_{}".format(script, code, name)

        if _is_cached(entry, out_dir) and not force:
            txt = _txt_path(entry, out_dir)
            if extract and not os.path.isfile(txt):
                _extract_text(pdf, txt)
                print("  EXTRACT  {}  (txt only)".format(label))
            else:
                print("  SKIP     {}  (cached)".format(label))
            continue

        print("  FETCH    {}  ...".format(label), end="")
        sys.stdout.flush()

        try:
            pdf_bytes, _url = _fetch_pdf(code)
            _ensure_dir(pdf)
            with open(pdf, "wb") as f:
                f.write(pdf_bytes)
            size_kb = len(pdf_bytes) // 1024

            txt_note = ""
            if extract:
                ok = _extract_text(pdf, _txt_path(entry, out_dir))
                txt_note = " + txt" if ok else " + txt:FAILED"

            print("  {:,} KB{}".format(size_kb, txt_note))

            if i < len(targets) - 1:
                time.sleep(REQUEST_DELAY)

        except IOError as err:
            print("  FAIL: {}".format(err))
            errors += 1

    return 0 if errors == 0 else 1


def cmd_extract(ids, reg, out_dir):
    if not _pdftotext_ok():
        print("Error: pdftotext not found. Install poppler-utils.", file=sys.stderr)
        return 1

    targets = ids if ids else [i for i in sorted(reg.keys())
                                if _is_cached(reg[i], out_dir)]
    unknown = [i for i in targets if i not in reg]
    if unknown:
        print("Unknown IDs: {}".format(", ".join(unknown)), file=sys.stderr)
        return 1

    errors = 0
    for lang_id in targets:
        entry = reg[lang_id]
        pdf   = _pdf_path(entry, out_dir)
        txt   = _txt_path(entry, out_dir)
        label = "{}/{}_{}".format(entry.get("script","Unknown"),
                                   entry["code"], entry["name"])

        if not os.path.isfile(pdf):
            print("  MISS     {}  (fetch first)".format(label))
            errors += 1; continue

        print("  EXTRACT  {}  ...".format(label), end="")
        sys.stdout.flush()
        ok = _extract_text(pdf, txt)
        if ok:
            print("  {:,} bytes".format(os.path.getsize(txt)))
        else:
            print("  FAIL (scanned/image PDF or no embedded text)")
            errors += 1

    return 0 if errors == 0 else 1


def cmd_verify(ids, reg, out_dir):
    targets = ids if ids else [i for i in sorted(reg.keys())
                                if _is_cached(reg[i], out_dir)]
    if not targets:
        print("No cached PDFs. Run: python udhr.py fetch --all")
        return 0

    passed = failed = 0
    for lang_id in sorted(targets):
        entry = reg[lang_id]
        pdf   = _pdf_path(entry, out_dir)
        label = "{}/{}_{}".format(entry.get("script","Unknown"),
                                   entry["code"], entry["name"])

        if not os.path.isfile(pdf):
            print("  MISS  {}".format(label)); failed += 1; continue

        with open(pdf, "rb") as f:
            header = f.read(4)
            f.seek(0, 2)
            size = f.tell()

        if header == b"%PDF" and size > 1024:
            txt  = _txt_path(entry, out_dir)
            note = " +txt" if os.path.isfile(txt) else ""
            print("  PASS  {}  ({:,} KB{})".format(label, size // 1024, note))
            passed += 1
        else:
            print("  FAIL  {}  (bad header or {:,} bytes)".format(label, size))
            failed += 1

    print()
    print("Results: {} passed, {} failed".format(passed, failed))
    return 0 if failed == 0 else 1


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="udhr",
        description=(
            "UDHR PDF corpus mirror — 560+ translations from OHCHR.\n"
            "Run 'discover' first to build the language registry, then 'fetch'."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Quick start:\n"
            "  python udhr.py discover\n"
            "  python udhr.py list\n"
            "  python udhr.py fetch --all\n"
            "  python udhr.py fetch --all --extract\n"
            "\n"
            "Layout: docs/udhr/{Script}/{code}_{Language}.pdf\n"
            "        docs/udhr/{Script}/{code}_{Language}.txt  (if extracted)\n"
            "\n"
            "Entropy analysis:\n"
            "  python tools/ucs-dec/ucs_dec_tool.py --encode \\\n"
            "      < docs/udhr/Arabic/arz_Arabic.txt \\\n"
            "      | python tools/mnemonic/crowsong-advisor.py\n"
        )
    )
    p.add_argument("--dir", default=DEFAULT_DIR, metavar="PATH",
        help="root output directory (default: docs/udhr/)")
    p.add_argument("--registry", default=DEFAULT_REG, metavar="PATH",
        help="registry JSON file (default: registry.json)")

    sub = p.add_subparsers(dest="command")
    sub.required = True

    pp = sub.add_parser("probe",
        help="probe OHCHR to find correct codes for unconfirmed languages")
    pp.add_argument("ids", nargs="*",
        help="language IDs to probe (default: all with candidates)")

    pd = sub.add_parser("discover",
        help="build/update registry.json from OHCHR language index")
    pd.add_argument("--probe", action="store_true",
        help="probe each new code's PDF URL before adding to registry")

    pl = sub.add_parser("list", help="list languages, grouped by script")
    pl.add_argument("--script", default=None, metavar="SCRIPT",
        help="filter by script family")

    pf = sub.add_parser("fetch", help="fetch PDFs from OHCHR")
    pf.add_argument("ids", nargs="*", help="language IDs to fetch")
    pf.add_argument("--all", dest="fetch_all", action="store_true",
        help="fetch all languages in registry")
    pf.add_argument("--force", action="store_true",
        help="re-fetch even if cached")
    pf.add_argument("--extract", action="store_true",
        help="also run pdftotext alongside each PDF")

    pe = sub.add_parser("extract",
        help="run pdftotext on cached PDFs to produce .txt files")
    pe.add_argument("ids", nargs="*",
        help="language IDs (default: all cached)")

    pv = sub.add_parser("verify",
        help="verify cached PDFs are valid (%%PDF header, non-trivial size)")
    pv.add_argument("ids", nargs="*",
        help="language IDs (default: all cached)")

    return p


def main():
    args    = build_parser().parse_args()
    out_dir = args.dir
    reg_path = args.registry

    try:
        if args.command == "discover":
            return cmd_discover(reg_path, out_dir, probe=args.probe)

        reg = _load_registry(reg_path)

        if args.command == "probe":
            return cmd_probe(args.ids, reg, reg_path)
        if args.command == "list":
            return cmd_list(reg, script_filter=args.script)
        if args.command == "fetch":
            return cmd_fetch(args.ids, reg, out_dir,
                             force=args.force,
                             fetch_all=args.fetch_all,
                             extract=args.extract)
        if args.command == "extract":
            return cmd_extract(args.ids, reg, out_dir)
        if args.command == "verify":
            return cmd_verify(args.ids, reg, out_dir)

    except (IOError, KeyboardInterrupt) as err:
        print("Error: {}".format(err), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
