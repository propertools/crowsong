#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
crowsong-advisor.py — Pipeline recommendation tool for Crowsong / FDS+CCL

Reads a UCS-DEC token stream on stdin, performs statistical analysis,
and recommends available encoding pipelines in decreasing order of
expected output entropy (best to worst), with copy-paste bash commands.

Usage:
    cat payload.txt | python crowsong-advisor.py
    cat payload.txt | python crowsong-advisor.py --verse-file verses.txt
    cat payload.txt | python crowsong-advisor.py --quiet
    cat payload.txt | python crowsong-advisor.py --json

Options:
    --verse-file FILE   File containing key verses (one per line, up to 3).
                        If omitted, canonical test verses are used for
                        measurement. Your actual verses will be used in the
                        generated pipeline commands.
    --verses V1,V2,V3  Comma-separated verses (quoted if they contain spaces).
    --width N           FDS token field width (default: 5).
    --quiet             Summary table only, no explanations.
    --json              Machine-readable JSON output.
    --ref ID            Artifact reference ID for generated commands.

Examples:
    # Quick recommendation for an Arabic payload
    cat arabic.txt | python crowsong-advisor.py

    # With your actual key file
    cat chinese.txt | python crowsong-advisor.py --verse-file keys.txt

    # JSON output for scripting
    cat payload.txt | python crowsong-advisor.py --json | jq '.modes[0].pipeline'

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import collections
import hashlib
import io
import json
import math
import random
import sys
import unicodedata

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode   # noqa: F821
    input     = raw_input # noqa: F821
else:
    text_type = str

# ── Prime derivation ──────────────────────────────────────────────────────────

def _next_prime(n):
    w = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    def _ip(n):
        if n < 2: return False
        for p in w:
            if n == p: return True
            if n % p == 0: return False
        d, r = n - 1, 0
        while d % 2 == 0: d //= 2; r += 1
        for a in w:
            if a >= n: continue
            x = pow(a, d, n)
            if x == 1 or x == n - 1: continue
            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1: break
            else: return False
        return True
    if n <= 2: return 2
    n = n | 1
    while not _ip(n): n += 2
    return n

def _derive_prime(verse):
    norm = unicodedata.normalize("NFC", verse.strip())
    ts   = "  ".join("{:05d}".format(ord(c)) for c in norm)
    return _next_prime(int(hashlib.sha256(ts.encode("utf-8")).hexdigest(), 16))

# Canonical measurement primes (used when no verses supplied)
_CANON_VERSES = [
    "Factoring primes in the hot sun, I fought Entropy \u2014 and Entropy won.",
    "Every sequence slips. Every clock will lie.",
    "The signal strains, but never gone \u2014 I fought Entropy, and I forged on.",
]
_CANON_PRIMES = [str(_derive_prime(v)) for v in _CANON_VERSES]


# ── Statistical helpers ───────────────────────────────────────────────────────

def _H(tokens):
    c = collections.Counter(tokens)
    n = len(tokens)
    if n == 0: return 0.0
    return -sum((v / n) * math.log(v / n, 2) for v in c.values())

def _H_se(tokens):
    """Standard error of Shannon entropy estimate."""
    c = collections.Counter(tokens)
    n = len(tokens)
    if n == 0: return 0.0
    probs = [v / n for v in c.values()]
    h     = _H(tokens)
    var   = sum(p * (math.log(p, 2) ** 2) for p in probs) - h ** 2
    return math.sqrt(max(var, 0.0) / n)

def _twist_rate(tokens, prime_str, width=5, schedule="standard"):
    """Fraction of tokens twisted to a non-base-10 representation."""
    pd  = [int(d) for d in prime_str]
    pl  = len(pd)
    twisted = 0
    for i, tok in enumerate(tokens):
        v = int(tok)
        d = pd[i % pl]
        if schedule == "mod3":
            b = 7 + (d % 3)
        else:
            b = 10 if d <= 1 else d
        feasible = (b ** width) > v
        if b != 10 and feasible:
            twisted += 1
    return twisted / len(tokens) if tokens else 0.0


# ── Script analysis ───────────────────────────────────────────────────────────

_SCRIPT_BLOCKS = [
    (592,   687,   "Latin Extended / IPA"),
    (880,   1023,  "Greek"),
    (1024,  1279,  "Cyrillic"),
    (1424,  1535,  "Hebrew"),
    (1536,  1791,  "Arabic / Farsi"),
    (2304,  2431,  "Devanagari"),
    (2432,  2559,  "Bengali"),
    (3584,  3711,  "Thai"),
    (4352,  4607,  "Hangul Jamo"),
    (4608,  4991,  "Ethiopic"),
    (6144,  6319,  "Khmer"),
    (7680,  7935,  "Latin Extended Additional"),
    (19968, 40959, "CJK Unified Ideographs"),
    (40960, 42127, "Yi"),
    (44032, 55203, "Hangul Syllables"),
]

def _analyse_script(tokens):
    values   = [int(t) for t in tokens if t.isdigit()]
    total    = len(values)
    if total == 0:
        return {"risk": "low", "high_fraction": 0.0,
                "dominant": "None", "clusters": {}}

    ascii_ct = sum(1 for v in values if 32 <= v <= 126)
    high     = sum(1 for v in values if v > 591)

    clusters = collections.Counter()
    for v in values:
        if v <= 591: continue
        label = "Other non-ASCII"
        for lo, hi, name in _SCRIPT_BLOCKS:
            if lo <= v <= hi:
                label = name; break
        clusters[label] += 1

    frac     = high / total
    dominant = clusters.most_common(1)[0][0] if clusters else "None"
    risk     = ("high"   if frac >= 0.30 else
                "medium" if frac >= 0.10 else "low")

    return {
        "total":          total,
        "ascii":          ascii_ct,
        "high":           high,
        "high_fraction":  frac,
        "dominant":       dominant,
        "risk":           risk,
        "clusters":       dict(clusters),
    }


# ── Full statistical analysis ────────────────────────────────────────────────

_UNICODE_BLOCKS = [
    (0,     31,    "Control characters"),
    (32,    126,   "ASCII printable"),
    (127,   255,   "Latin-1 Supplement"),
    (256,   591,   "Latin Extended"),
    (592,   687,   "IPA Extensions"),
    (688,   879,   "Spacing Modifiers / Combining"),
    (880,   1023,  "Greek and Coptic"),
    (1024,  1279,  "Cyrillic"),
    (1280,  1423,  "Armenian / Cyrillic Supplement"),
    (1424,  1535,  "Hebrew"),
    (1536,  1791,  "Arabic"),
    (1792,  2047,  "Syriac / Thaana / NKo"),
    (2304,  2431,  "Devanagari"),
    (2432,  2559,  "Bengali"),
    (2560,  2815,  "Gurmukhi / Gujarati"),
    (2816,  3071,  "Oriya / Tamil"),
    (3072,  3327,  "Telugu / Kannada"),
    (3328,  3583,  "Malayalam / Sinhala"),
    (3584,  3711,  "Thai"),
    (3712,  4095,  "Lao / Tibetan"),
    (4096,  4351,  "Myanmar / Georgian"),
    (4352,  4607,  "Hangul Jamo"),
    (4608,  4991,  "Ethiopic"),
    (5120,  6399,  "Cherokee / Unified Canadian / Ogham / Runic / Khmer"),
    (6400,  7679,  "Mongolian / Other"),
    (7680,  8191,  "Latin Extended Additional / Greek Extended"),
    (8192,  8703,  "General Punctuation / Letterlike / Arrows"),
    (8704,  9215,  "Mathematical Operators / Miscellaneous Technical"),
    (9216,  9983,  "Control Pictures / Box Drawing / Geometric / Symbols"),
    (9984,  10175, "Dingbats"),
    (10176, 12287, "Braille / CJK Radicals / Kangxi / Other"),
    (12288, 12543, "CJK Symbols / Hiragana / Katakana"),
    (12544, 13311, "Bopomofo / Hangul Compat / Enclosed CJK / CJK Compat"),
    (13312, 19967, "CJK Extension A"),
    (19968, 40959, "CJK Unified Ideographs"),
    (40960, 44031, "Yi / Other"),
    (44032, 55295, "Hangul Syllables"),
    (55296, 65535, "Surrogates / Private Use / Presentation / Halfwidth"),
    (65536, 131071,"SMP: Linear B / Old Italic / Gothic / Deseret / Music"),
    (131072,196607,"SIP: CJK Extension B / C / D / E / F"),
    (196608,1114111,"TIP / Other supplementary"),
]


def _full_analysis(tokens, width=5):
    """
    Compute comprehensive statistics on a UCS-DEC token stream.
    Returns a dict suitable for both human-readable and JSON output.
    """
    values  = [int(t) for t in tokens if t.isdigit()]
    n       = len(values)
    if n == 0:
        return {"error": "empty token stream"}

    counter = collections.Counter(values)
    unique  = len(counter)
    padding = counter.get(0, 0)

    # Shannon entropy + standard error
    H   = _H(tokens)
    H_se = _H_se(tokens)

    # Value statistics
    vmin    = min(values)
    vmax    = max(values)
    vmean   = sum(values) / n
    vsorted = sorted(values)
    vmedian = vsorted[n // 2]
    vmode, vmode_count = counter.most_common(1)[0]

    # Script / Unicode block breakdown
    script_counts = {}
    unclassified  = 0
    for v in values:
        placed = False
        for lo, hi, name in _UNICODE_BLOCKS:
            if lo <= v <= hi:
                script_counts[name] = script_counts.get(name, 0) + 1
                placed = True
                break
        if not placed:
            unclassified += 1
    if unclassified:
        script_counts["Other / Unclassified"] = unclassified

    # CCL feasibility profile (what fraction of tokens can be twisted
    # at each base, given the feasibility rule base^width > token_value)
    feasibility = {}
    for base in range(2, 10):
        feasible = sum(1 for v in values if base ** width > v)
        feasibility[base] = round(feasible / n, 6)

    # Top 15 most frequent tokens, decoded to characters
    top15 = []
    for v, count in counter.most_common(15):
        try:
            ch   = chr(v)
            name = unicodedata.name(ch, "UNNAMED")[:28]
            if v < 32 or v == 127:
                disp = repr(ch)
            else:
                disp = ch
        except (ValueError, OverflowError):
            disp = "?"; name = "INVALID CODE POINT"
        top15.append({
            "value":    v,
            "token":    "{:0{w}d}".format(v, w=width),
            "count":    count,
            "pct":      round(100 * count / n, 2),
            "char":     disp,
            "name":     name,
        })

    # Approximate compression ratio proxy:
    # high H (> 7.0) suggests already-compressed or encrypted data
    already_compressed = H > 7.0

    # Normalised entropy (H / log2(unique)) — how close to uniform?
    h_norm = H / math.log(unique, 2) if unique > 1 else 1.0

    return {
        "n":                  n,
        "unique":             unique,
        "padding":            padding,
        "H":                  round(H, 6),
        "H_se":               round(H_se, 6),
        "H_normalised":       round(h_norm, 6),
        "vmin":               vmin,
        "vmax":               vmax,
        "vmean":              round(vmean, 2),
        "vmedian":            vmedian,
        "vmode":              vmode,
        "vmode_count":        vmode_count,
        "script_counts":      script_counts,
        "feasibility":        feasibility,
        "top15":              top15,
        "already_compressed": already_compressed,
        "width":              width,
    }


def _format_analysis(a, tokens):
    """Format a full analysis dict as a human-readable report."""
    n     = a["n"]
    lines = []
    W     = 72

    def rule(ch="─"): return ch * W
    def head(t):       return "  ┌─ {} {}".format(t, "─"*(W-4-len(t)))
    def row(k, v):     return "  │  {:<30}  {}".format(k, v)
    def blank():       return "  │"

    lines += [
        "",
        "╔" + "═"*(W-2) + "╗",
        "║{:^{w}}║".format(" Crowsong Payload Analysis ", w=W-2),
        "╚" + "═"*(W-2) + "╝",
        "",
    ]

    # ── Overview ──────────────────────────────────────────────────────────────
    lines.append(head("Overview"))
    lines.append(row("Token count",
        "{:,}".format(n)))
    lines.append(row("Unique token values",
        "{:,}  ({:.1f}% of total)".format(
            a["unique"], 100*a["unique"]/n)))
    lines.append(row("Padding tokens (00000)",
        "{:,}  ({:.1f}%)".format(
            a["padding"], 100*a["padding"]/n) if a["padding"] else "none"))
    lines.append(row("FDS field width",
        "WIDTH/{}".format(a["width"])))
    lines.append(blank())

    # ── Entropy ───────────────────────────────────────────────────────────────
    lines.append(head("Entropy"))

    H     = a["H"]
    H_se  = a["H_se"]
    H_n   = a["H_normalised"]

    stars  = ("★★★ exceeds AES-128 ref" if H >= 7.95 else
               "★★☆ near AES-128 ref"   if H >= 7.45 else
               "★☆☆ below AES-128 ref"  if H >= 6.00 else
               "☆☆☆ well below AES-128")
    bar_w  = 28
    filled = int(min(1.0, H / math.log(100000,2)) * bar_w)
    bar    = "█"*filled + "░"*(bar_w-filled)

    lines.append(row("Shannon entropy H₀",
        "{:.4f} ±{:.4f} bits/token  {}".format(H, H_se, stars)))
    lines.append(row("Entropy bar (of 9.97 max)",
        "[{}]".format(bar)))
    lines.append(row("Normalised entropy H/log₂(K)",
        "{:.4f}  ({:.1f}% of max for {} unique values)".format(
            H_n, 100*H_n, a["unique"])))
    lines.append(row("AES-128 ciphertext reference",
        "~7.95 bits/byte"))
    lines.append(row("Theoretical max (WIDTH/{})".format(a["width"]),
        "{:.4f} bits/token  (log₂(10^{}))".format(
            math.log(10**a["width"],2), a["width"])))
    if a["already_compressed"]:
        lines.append(row("⚠ Note",
            "H₀ > 7.0: payload may already be compressed or encrypted."))
        lines.append(row("",
            "CCL entropy gain will be limited. Consider plain UCS-DEC."))
    lines.append(blank())

    # ── Token value distribution ───────────────────────────────────────────────
    lines.append(head("Token value distribution"))
    lines.append(row("Minimum value",
        "{:,}  (U+{:04X}  {})".format(
            a["vmin"], a["vmin"],
            _safe_name(a["vmin"]))))
    lines.append(row("Maximum value",
        "{:,}  (U+{:04X}  {})".format(
            a["vmax"], a["vmax"],
            _safe_name(a["vmax"]))))
    lines.append(row("Mean value",
        "{:.1f}".format(a["vmean"])))
    lines.append(row("Median value",
        "{:,}  (U+{:04X}  {})".format(
            a["vmedian"], a["vmedian"],
            _safe_name(a["vmedian"]))))
    lines.append(row("Mode (most frequent value)",
        "{:,} × {:,}  ({:.1f}%)  U+{:04X}  {}".format(
            a["vmode_count"], a["vmode"],
            100*a["vmode_count"]/n,
            a["vmode"],
            _safe_name(a["vmode"]))))
    lines.append(blank())

    # ── Script breakdown ──────────────────────────────────────────────────────
    lines.append(head("Unicode script distribution"))
    sc = sorted(a["script_counts"].items(), key=lambda x: -x[1])
    for name, count in sc:
        pct    = 100 * count / n
        bar_w  = 20
        filled = int(min(1.0, pct/100) * bar_w)
        bar    = "█"*filled + "░"*(bar_w-filled)
        lines.append("  │  {:38s}  {:5.1f}%  {}".format(
            name[:37], pct, bar))
    lines.append(blank())

    # ── CCL feasibility ────────────────────────────────────────────────────────
    lines.append(head("CCL feasibility profile  (WIDTH/{})".format(a["width"])))
    lines.append("  │  {:8s}  {:7s}  {}".format(
        "Base", "Feasible", "Twist potential"))
    for base, frac in sorted(a["feasibility"].items()):
        bar_w  = 28
        filled = int(frac * bar_w)
        bar    = "█"*filled + "░"*(bar_w-filled)
        pct    = 100 * frac
        flag   = ""
        if frac < 0.20: flag = "  ← low — fallback to base 10 dominates"
        if frac > 0.95: flag = "  ← excellent"
        lines.append("  │  base {:1d}      {:6.1f}%  {}{}".format(
            base, pct, bar, flag))
    lines.append(blank())
    # Interpretation
    low_bases = [b for b,f in a["feasibility"].items() if f < 0.20]
    if len(low_bases) >= 6:
        lines.append("  │  ⚠ Most bases infeasible: high-codepoint script detected.")
        lines.append("  │    Apply Gloss layer before CCL for best entropy.")
    elif len(low_bases) >= 3:
        lines.append("  │  ⚠ Mixed feasibility: consider Gloss layer.")
    else:
        lines.append("  │  ✓ Good feasibility across most bases.")
        lines.append("  │    CCL3 (standard schedule) will be effective.")
    lines.append(blank())

    # ── Top 15 tokens ─────────────────────────────────────────────────────────
    lines.append(head("Most frequent tokens (top 15)"))
    lines.append("  │  {:>7}  {:>5}  {:>6}  {:4s}  {}".format(
        "Token", "Count", "Pct", "Char", "Unicode name"))
    lines.append("  │  " + "─"*56)
    for t in a["top15"]:
        lines.append("  │  {:>7}  {:>5,}  {:>5.1f}%  {:4s}  {}".format(
            t["token"], t["count"], t["pct"],
            t["char"] if isinstance(t["char"], str) else "?",
            t["name"][:28]))
    lines.append(blank())

    lines.append("  └" + "─"*(W-3))
    lines.append("")

    return "\n".join(lines)


def _safe_name(v):
    try:
        return unicodedata.name(chr(v), "?")[:28]
    except (ValueError, OverflowError):
        return "?"


# ── CCL pass ─────────────────────────────────────────────────────────────────

def _ccl_pass(tokens, prime_str, width=5, schedule="standard"):
    pd = [int(d) for d in prime_str]
    pl = len(pd)
    out = []
    for i, tok in enumerate(tokens):
        v = int(tok)
        d = pd[i % pl]
        if schedule == "mod3":
            b = 7 + (d % 3)
        else:
            b = 10 if d <= 1 else d
        feasible = (b ** width) > v
        if b != 10 and feasible:
            tmp = v; dv = []
            while tmp > 0: dv.append(tmp % b); tmp //= b
            while len(dv) < width: dv.append(0)
            out.append("".join(str(x) for x in reversed(dv)))
        else:
            out.append(tok)
    return out

def _ccl3(tokens, primes, width=5, schedule="standard"):
    t = tokens
    for p in primes[:3]:
        t = _ccl_pass(t, p, width=width, schedule=schedule)
    return t


# ── Gloss layer ───────────────────────────────────────────────────────────────

_BASE_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_GLOSS_BASE  = 52
_GLOSS_WIDTH = 3   # 52^3 = 140,608 > 99,999

def _make_gloss_alpha(prime_str):
    seed = int(hashlib.sha256(prime_str[::-1].encode("utf-8")).hexdigest(), 16)
    rng  = random.Random(seed)
    alpha = list(_BASE_ALPHA)
    rng.shuffle(alpha)
    return alpha

def _gloss(tokens, prime_str):
    alpha = _make_gloss_alpha(prime_str)
    out   = []
    for tok in tokens:
        v = int(tok)
        dv = []
        tmp = v
        if tmp == 0:
            dv = [alpha[0]] * _GLOSS_WIDTH
        else:
            while tmp > 0: dv.append(alpha[tmp % _GLOSS_BASE]); tmp //= _GLOSS_BASE
            while len(dv) < _GLOSS_WIDTH: dv.append(alpha[0])
            dv = list(reversed(dv))
        for ch in dv:
            out.append("{:05d}".format(ord(ch)))
    return out


# ── Symbol layer ──────────────────────────────────────────────────────────────

_DEEPCUT = [
    0x00B6, 0x00A7, 0x2020, 0x2021, 0x2042,
    0x2609, 0x204A, 0x203D, 0x2726, 0x263F,
]

def _symbolise(tokens):
    """Base-10 digit substitution using deepcut-v1 alphabet. 5x expansion."""
    out = []
    for tok in tokens:
        v = int(tok)
        dv = []
        tmp = v
        if tmp == 0:
            dv = [0] * 5
        else:
            while tmp > 0: dv.append(tmp % 10); tmp //= 10
            while len(dv) < 5: dv.append(0)
            dv = list(reversed(dv))
        for d in dv:
            out.append("{:05d}".format(_DEEPCUT[d]))
    return out


# ── Mode evaluation ───────────────────────────────────────────────────────────

def _evaluate_modes(tokens, primes, width=5):
    """
    Evaluate all available pipeline modes on the given token stream.
    Returns list of dicts, unsorted.
    """
    results = []
    n = len(tokens)

    # ── 1. CCL3 standard ─────────────────────────────────────────────────────
    t = _ccl3(tokens, primes, width=width, schedule="standard")
    tw = _twist_rate(tokens, primes[0], width=width, schedule="standard")
    results.append({
        "id":       "ccl3-standard",
        "label":    "CCL3 (standard schedule)",
        "H":        _H(t),
        "se":       _H_se(t),
        "tokens":   len(t),
        "unique":   len(set(t)),
        "twist1":   tw,
        "expansion": 1.0,
        "layers":   ["CCL×3"],
        "note":     "Baseline. Best for ASCII/Latin text.",
    })

    # ── 2. CCL3 mod3 ─────────────────────────────────────────────────────────
    t = _ccl3(tokens, primes, width=width, schedule="mod3")
    tw = _twist_rate(tokens, primes[0], width=width, schedule="mod3")
    results.append({
        "id":       "ccl3-mod3",
        "label":    "CCL3 (mod3 schedule)",
        "H":        _H(t),
        "se":       _H_se(t),
        "tokens":   len(t),
        "unique":   len(set(t)),
        "twist1":   tw,
        "expansion": 1.0,
        "layers":   ["CCL×3/mod3"],
        "note":     "100% twist rate for WIDTH/3 binary payloads. "
                    "Bases always 7, 8, or 9.",
    })

    # ── 3. Gloss + CCL3 ──────────────────────────────────────────────────────
    g  = _gloss(tokens, primes[0])
    t  = _ccl3(g, primes, width=width, schedule="standard")
    tw = _twist_rate(g, primes[0], width=width, schedule="standard")
    results.append({
        "id":       "gloss-ccl3",
        "label":    "Gloss + CCL3",
        "H":        _H(t),
        "se":       _H_se(t),
        "tokens":   len(t),
        "unique":   len(set(t)),
        "twist1":   tw,
        "expansion": _GLOSS_WIDTH,
        "layers":   ["Gloss/52", "CCL×3"],
        "note":     "Key-derived base-52 re-encoding before CCL. "
                    "Eliminates CCL feasibility problem for CJK/Arabic/Hangul. "
                    "One prime drives both layers (reversed digits = Gloss key, "
                    "forward digits = CCL key).",
    })

    # ── 4. Symbol (deepcut-v1) + CCL3 ────────────────────────────────────────
    s  = _symbolise(tokens)
    t  = _ccl3(s, primes, width=width, schedule="standard")
    tw = _twist_rate(s, primes[0], width=width, schedule="standard")
    results.append({
        "id":       "symbol-ccl3",
        "label":    "Symbol (deepcut-v1) + CCL3",
        "H":        _H(t),
        "se":       _H_se(t),
        "tokens":   len(t),
        "unique":   len(set(t)),
        "twist1":   tw,
        "expansion": 5.0,
        "layers":   ["Symbol/deepcut-v1", "CCL×3"],
        "note":     "Typographic camouflage: ¶ § † ‡ ⁂ ☉ ⁊ ‽ ✦ ☿. "
                    "5x token expansion. Optimised for visual deniability "
                    "rather than entropy. Output looks like editorial markup.",
    })

    # ── 5. Gloss + CCL3 mod3 ─────────────────────────────────────────────────
    g  = _gloss(tokens, primes[0])
    t  = _ccl3(g, primes, width=width, schedule="mod3")
    tw = _twist_rate(g, primes[0], width=width, schedule="mod3")
    results.append({
        "id":       "gloss-ccl3-mod3",
        "label":    "Gloss + CCL3 (mod3)",
        "H":        _H(t),
        "se":       _H_se(t),
        "tokens":   len(t),
        "unique":   len(set(t)),
        "twist1":   tw,
        "expansion": _GLOSS_WIDTH,
        "layers":   ["Gloss/52", "CCL×3/mod3"],
        "note":     "Gloss re-encoding + mod3 schedule. "
                    "Experimental. May help for mixed binary/non-Latin payloads.",
    })

    return results


# ── Pipeline command generation ───────────────────────────────────────────────

def _pipeline_cmd(mode_id, verse_file=None, ref="ADV"):
    """Generate a copy-paste bash pipeline for the given mode."""

    verse_arg = (
        "--verse-file {}".format(verse_file)
        if verse_file else "--verse-file verses.txt"
    )

    cmds = {
        "ccl3-standard": (
            "cat payload.txt | \\\n"
            "    python tools/mnemonic/prime_twist.py stack \\\n"
            "        {vf} --ref {ref} \\\n"
            "    > artifact.txt"
        ),
        "ccl3-mod3": (
            "cat payload.txt | \\\n"
            "    python tools/mnemonic/prime_twist.py stack \\\n"
            "        {vf} --schedule mod3 --ref {ref} \\\n"
            "    > artifact.txt"
        ),
        "gloss-ccl3": (
            "cat payload.txt | \\\n"
            "    python tools/mnemonic/gloss_twist.py gloss \\\n"
            "        --verse {vf_single} --ref GLOSS | \\\n"
            "    python tools/mnemonic/prime_twist.py stack \\\n"
            "        {vf} --no-symbol-check --ref {ref} \\\n"
            "    > artifact.txt"
        ),
        "symbol-ccl3": (
            "cat payload.txt | \\\n"
            "    python tools/mnemonic/symbol_twist.py twist \\\n"
            "        --key-verse {vf_single} --ref SYM | \\\n"
            "    python tools/mnemonic/prime_twist.py stack \\\n"
            "        {vf} --no-symbol-check --ref {ref} \\\n"
            "    > artifact.txt"
        ),
        "gloss-ccl3-mod3": (
            "cat payload.txt | \\\n"
            "    python tools/mnemonic/gloss_twist.py gloss \\\n"
            "        --verse {vf_single} --ref GLOSS | \\\n"
            "    python tools/mnemonic/prime_twist.py stack \\\n"
            "        {vf} --schedule mod3 --no-symbol-check --ref {ref} \\\n"
            "    > artifact.txt"
        ),
    }

    vf_single = (
        "$(head -1 {})".format(verse_file)
        if verse_file else "$(head -1 verses.txt)"
    )

    template = cmds.get(mode_id, "# Unknown mode: {}".format(mode_id))
    return template.format(
        vf=verse_arg,
        vf_single=vf_single,
        ref=ref,
    )


# ── Formatting ────────────────────────────────────────────────────────────────

_AES_REF   = 7.95
_MAX_W5    = math.log(100000, 2)   # 16.61
_SEPARATOR = "-" * 72

def _stars(h):
    """Visual quality indicator."""
    if h >= _AES_REF:        return "★★★  exceeds AES-128"
    if h >= _AES_REF - 0.5:  return "★★☆  near AES-128"
    if h >= _AES_REF - 1.5:  return "★☆☆  below AES-128"
    return                          "☆☆☆  well below AES-128"

def _bar(h, width=20):
    pct = min(1.0, h / _MAX_W5)
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)

def _format_report(tokens, modes_sorted, script_info,
                   verse_file=None, ref="ADV", quiet=False):
    lines = []
    n = len(tokens)

    if not quiet:
        lines.append("")
        lines.append("╔══════════════════════════════════════════════════════════════════════╗")
        lines.append("║            Crowsong Pipeline Advisor — Entropy Analysis              ║")
        lines.append("╚══════════════════════════════════════════════════════════════════════╝")
        lines.append("")
        lines.append("  Input:   {:,} tokens   {:d} unique values".format(
            n, len(set(tokens))))
        lines.append("  H₀:      {:.4f} bits/token  (before any transform)".format(
            _H(tokens)))
        lines.append("  Script:  {} ({:.0f}% non-ASCII, dominant: {})".format(
            script_info["risk"].upper(),
            100 * script_info["high_fraction"],
            script_info["dominant"]))

        if script_info["risk"] in ("high", "medium"):
            lines.append("")
            lines.append("  ⚠  Script fingerprinting risk detected.")
            lines.append("     A passive observer can identify the script from token")
            lines.append("     value distribution. Modes using the Gloss layer are")
            lines.append("     strongly recommended for this payload.")

        lines.append("")
        lines.append("  Reference:  AES-128 ciphertext  ≈ 7.95 bits/byte")
        lines.append("              Theoretical max (WIDTH/5)  = 9.97 bits/token")
        lines.append("")
        lines.append(_SEPARATOR)

    # Table header
    lines.append("")
    lines.append("  {:>3}  {:<30}  {:>7}  {:>6}  {:>6}  {:>5}  {}".format(
        "Rank", "Mode", "H₃ (CCL3)", "±σ", "Tokens", "×exp", "Quality"))
    lines.append("  " + "-" * 68)

    for i, m in enumerate(modes_sorted, 1):
        bar = _bar(m["H"])
        lines.append("  {:>3}  {:<30}  {:>7.4f}  {:>6.4f}  {:>6,}  {:>4.0f}×  {}".format(
            i,
            m["label"][:30],
            m["H"],
            m["se"],
            m["tokens"],
            m["expansion"],
            _stars(m["H"])))

    lines.append("")

    if not quiet:
        lines.append(_SEPARATOR)
        lines.append("")
        lines.append("  RECOMMENDED PIPELINES  (best → worst entropy)")
        lines.append("")

        for i, m in enumerate(modes_sorted, 1):
            lines.append("  ── #{}: {}  (H₃ = {:.4f} ±{:.4f}) ──".format(
                i, m["label"], m["H"], m["se"]))
            lines.append("")
            # Indent the pipeline command
            cmd = _pipeline_cmd(m["id"], verse_file=verse_file, ref=ref)
            for line in cmd.splitlines():
                lines.append("     " + line)
            lines.append("")
            if m["note"]:
                for chunk in _wrap(m["note"], 64):
                    lines.append("     " + chunk)
            lines.append("")

        lines.append(_SEPARATOR)
        lines.append("")
        lines.append("  NOTES")
        lines.append("")
        lines.append("  ±σ  Standard error of entropy estimate. Larger with smaller")
        lines.append("      token counts. For n ≥ 300, ±σ < 0.06 in all scripts.")
        lines.append("")
        lines.append("  ×exp  Token count expansion factor relative to input.")
        lines.append("        Gloss: 3×   Symbol: 5×   CCL: 1×")
        lines.append("")
        lines.append("  Twist rates and entropy are measured using canonical")
        lines.append("  test primes. Your actual verses may produce slightly")
        lines.append("  different results.")
        lines.append("")

    return "\n".join(lines)

def _wrap(text, width):
    """Simple word-wrap."""
    words = text.split()
    lines = []
    line  = []
    length = 0
    for w in words:
        if length + len(w) + 1 > width and line:
            lines.append(" ".join(line))
            line = [w]; length = len(w)
        else:
            line.append(w); length += len(w) + 1
    if line:
        lines.append(" ".join(line))
    return lines


# ── I/O ───────────────────────────────────────────────────────────────────────

def _read_stdin():
    if PY2:
        data = sys.stdin.read()
        if not isinstance(data, text_type):
            data = data.decode("utf-8", errors="replace")
        return data
    return sys.stdin.read()

def _load_verses(verse_file=None, verses_str=None):
    if verse_file:
        with io.open(verse_file, "r", encoding="utf-8") as f:
            lines = [l.rstrip("\r\n") for l in f if l.strip()]
        return [str(_derive_prime(v)) for v in lines[:3]]
    if verses_str:
        vv = [v.strip() for v in verses_str.split(",") if v.strip()]
        return [str(_derive_prime(v)) for v in vv[:3]]
    return _CANON_PRIMES


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "Crowsong Pipeline Advisor.\n"
            "Reads a UCS-DEC token stream on stdin and recommends\n"
            "encoding pipelines in decreasing order of output entropy."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  cat payload.txt | python crowsong-advisor.py\n"
            "  cat arabic.txt  | python crowsong-advisor.py "
            "--verse-file keys.txt\n"
            "  cat payload.txt | python crowsong-advisor.py --json\n"
        )
    )
    vg = p.add_mutually_exclusive_group()
    vg.add_argument("--verse-file", metavar="FILE",
        help="file of key verses (one per line, up to 3)")
    vg.add_argument("--verses", metavar="V1,V2,V3",
        help="comma-separated verses")
    p.add_argument("--width", type=int, default=5, metavar="N",
        help="FDS token field width (default: 5)")
    p.add_argument("--ref", default="ADV", metavar="ID",
        help="artifact reference ID for generated commands")
    p.add_argument("--quiet", action="store_true",
        help="summary table only")
    p.add_argument("--json", action="store_true",
        help="machine-readable JSON output")
    p.add_argument("--analyse", "--analyze", dest="analyse",
        action="store_true",
        help="print full statistical analysis of the input and exit "
             "(no pipeline recommendations)")
    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    data = _read_stdin().strip()
    if not data:
        print("Error: no input on stdin.", file=sys.stderr)
        print("Usage: cat payload.txt | python crowsong-advisor.py",
              file=sys.stderr)
        return 1

    tokens = data.split()
    if not tokens:
        print("Error: no tokens found in input.", file=sys.stderr)
        return 1

    # Validate: are these UCS-DEC tokens?
    bad = [t for t in tokens[:20] if not t.isdigit()]
    if bad:
        print("Warning: non-numeric tokens found in input: {}".format(
            bad[:5]), file=sys.stderr)
        print("Input should be a UCS-DEC token stream (decimal integers,",
              file=sys.stderr)
        print("whitespace-separated). Encode first with ucs_dec_tool.py.",
              file=sys.stderr)

    primes = _load_verses(
        verse_file=args.verse_file,
        verses_str=args.verses)

    # Pad primes to at least 3
    while len(primes) < 3:
        primes.append(primes[-1])

    # Analysis-only mode: print statistics and exit
    if getattr(args, "analyse", False):
        a = _full_analysis(tokens, width=args.width)
        if args.json:
            print(json.dumps(a, indent=2, ensure_ascii=False))
        else:
            print(_format_analysis(a, tokens))
        return 0

    script_info = _analyse_script(tokens)
    modes       = _evaluate_modes(tokens, primes, width=args.width)
    modes_sorted = sorted(modes, key=lambda m: m["H"], reverse=True)

    if args.json:
        out = {
            "input_tokens":  len(tokens),
            "input_unique":  len(set(tokens)),
            "H0":            _H(tokens),
            "script":        script_info,
            "modes":         [
                {
                    "rank":      i + 1,
                    "id":        m["id"],
                    "label":     m["label"],
                    "H":         round(m["H"], 6),
                    "se":        round(m["se"], 6),
                    "tokens":    m["tokens"],
                    "unique":    m["unique"],
                    "expansion": m["expansion"],
                    "twist1":    round(m["twist1"], 4),
                    "layers":    m["layers"],
                    "note":      m["note"],
                    "pipeline":  _pipeline_cmd(
                        m["id"],
                        verse_file=args.verse_file,
                        ref=args.ref),
                }
                for i, m in enumerate(modes_sorted)
            ],
            "aes128_ref":    _AES_REF,
            "theoretical_max_w5": _MAX_W5,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    report = _format_report(
        tokens, modes_sorted, script_info,
        verse_file=args.verse_file,
        ref=args.ref,
        quiet=args.quiet)

    if PY2:
        if isinstance(report, text_type):
            sys.stdout.write(report.encode("utf-8"))
        else:
            sys.stdout.write(report)
        sys.stdout.write("\n")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
