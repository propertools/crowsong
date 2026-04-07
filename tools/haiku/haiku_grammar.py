#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
haiku_grammar.py — Grammar-aware haiku encoding engine

Extends the prime-driven haiku construction with:
  - Part-of-speech indexed syllable bins (POS × syllable_count → words)
  - Semantic field vocabulary for thematic coherence
  - POS template library for grammatically plausible surface structure

The result is haiku that reads as eerily plausible AI-generated nature
poetry from circa 2022-2024 — grammatically coherent, thematically
adjacent, slightly over-earnest, not quite right in the way AI poetry
is not quite right.

Construction:
    verse → prime P
      forward digits  → template selection + word selection within slots
      reversed digits → semantic field selection + slot-level word choice

    For each token value V to encode:
      1. Forward digits → select template T from template library
      2. Reversed digits → select semantic field F
      3. For each (POS, syllables) slot in T:
           candidates = POS_bins[POS][syllables] ∩ field_words[F]
           fallback   = POS_bins[POS][syllables]
           forward digits → select word from candidates
           word's index in POS_bins[POS][syllables] encodes V

This module provides:
    build_pos_bins(bins, pos_data)    POS-indexed syllable bins
    load_templates(path)              template library
    load_fields(path)                 semantic field vocabulary
    GrammarEngine                     the encoding/decoding engine

The module is imported by haiku_twist.py for use in --grammar mode.
It can also be used standalone for corpus analysis and bin inspection.

Usage (standalone):
    python haiku_grammar.py info      [--bins FILE] [--pos FILE]
    python haiku_grammar.py pos-bins  [--bins FILE] [--pos FILE] [--pos-tag TAG]
    python haiku_grammar.py generate  --verse TEXT [--bins FILE] [--pos FILE]
                                      [--templates FILE] [--fields FILE]
    python haiku_grammar.py analyse   [--templates FILE]

Compatibility: Python 2.7+ / 3.x
Dependencies:  cmudict bins.json (tools/cmudict/cmudict.py export)
               wordfreq POS data (tools/wordfreq/wordfreq.py)
               templates.json, fields.json (tools/haiku/)
               mnemonic.py (tools/mnemonic/)
Author: Proper Tools SRL
License: MIT

Dedicated to Felix 'FX' Lindner (1975-2026).
The signal strains, but never gone.
"""

from __future__ import print_function, unicode_literals

import argparse
import hashlib
import io
import json
import os
import sys
import time

PY2 = (sys.version_info[0] == 2)
if PY2:
    text_type = unicode  # noqa: F821
    range     = xrange   # noqa: F821
else:
    text_type = str

# ── Default paths ─────────────────────────────────────────────────────────────

DEFAULT_BINS      = os.path.join("docs", "cmudict", "bins-common.json")
DEFAULT_BINS_FULL = os.path.join("docs", "cmudict", "bins.json")
DEFAULT_TEMPLATES = os.path.join("tools", "haiku", "templates.json")
DEFAULT_FIELDS    = os.path.join("tools", "haiku", "fields.json")
DEFAULT_POS_DATA  = os.path.join("docs", "wordfreq", "pos-index.json")

# POS tag groups for fallback resolution
POS_GROUPS = {
    "NN":  ["NN", "NNS", "NNP", "NNPS"],
    "NNS": ["NNS", "NN"],
    "JJ":  ["JJ", "JJR", "JJS"],
    "VB":  ["VB", "VBZ", "VBG", "VBN", "VBD", "VBP"],
    "VBZ": ["VBZ", "VB", "VBP"],
    "VBG": ["VBG", "VB"],
    "VBN": ["VBN", "VB"],
    "VBD": ["VBD", "VB"],
    "RB":  ["RB", "RBR", "RBS"],
    "IN":  ["IN"],
    "DT":  ["DT"],
    "PRP": ["PRP"],
    "PRP$":["PRP$"],
    "CC":  ["CC"],
    "CD":  ["CD"],
    "MD":  ["MD"],
    "TO":  ["TO"],
    "WP":  ["WP"],
    "WDT": ["WDT"],
    "EX":  ["EX"],
}

# Short POS tag descriptions for display
POS_NAMES = {
    "NN":   "noun (singular)",
    "NNS":  "noun (plural)",
    "NNP":  "proper noun",
    "JJ":   "adjective",
    "JJR":  "adjective (comparative)",
    "VB":   "verb (base)",
    "VBZ":  "verb (3sg present)",
    "VBG":  "verb (gerund)",
    "VBN":  "verb (past participle)",
    "VBD":  "verb (past tense)",
    "VBP":  "verb (non-3sg present)",
    "RB":   "adverb",
    "IN":   "preposition",
    "DT":   "determiner",
    "PRP":  "pronoun",
    "PRP$": "possessive pronoun",
    "CC":   "conjunction",
    "CD":   "cardinal number",
    "MD":   "modal",
    "TO":   "to",
    "WP":   "wh-pronoun",
    "WDT":  "wh-determiner",
    "EX":   "existential there",
}

# Small closed-class word lists that don't need corpus lookup
# These are always available regardless of wordfreq corpus state
CLOSED_CLASS = {
    "DT": {
        1: ["a", "an", "the", "no", "my", "our", "its", "her", "his", "your"],
        2: ["every", "either", "neither"],
        3: ["another"],
    },
    "IN": {
        1: ["in", "on", "at", "by", "of", "to", "up", "as", "if", "or"],
        2: ["into", "onto", "upon", "above", "below", "through",
            "after", "before", "behind", "beside", "between",
            "across", "along", "among", "around", "beyond",
            "within", "without", "against", "under", "toward",
            "over", "past", "since", "until", "during"],
        3: ["beneath", "alongside", "throughout", "underneath"],
    },
    "CC": {
        1: ["and", "but", "or", "nor", "yet", "so"],
        2: ["either", "neither"],
    },
    "PRP": {
        1: ["i", "you", "he", "she", "it", "we", "they", "me",
            "him", "her", "us", "them"],
    },
    "PRP$": {
        1: ["my", "your", "his", "her", "its", "our"],
        2: ["their"],
    },
    "MD": {
        1: ["can", "may", "will", "shall"],
        2: ["could", "might", "would", "should"],
    },
    "TO": {
        1: ["to"],
    },
    "EX": {
        1: ["there"],
    },
    "WP": {
        1: ["who", "what", "whom"],
        2: ["whose"],
    },
    "WDT": {
        1: ["that", "which"],
    },
    "CD": {
        1: ["one", "two", "three", "four", "five", "six",
            "seven", "eight", "nine", "ten"],
        2: ["seven", "eleven", "dozen"],
        3: ["seventeen", "nineteen"],
    },
}


# ── mnemonic import ───────────────────────────────────────────────────────────

def _import_mnemonic():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        script_dir,
        os.path.join(script_dir, "..", "mnemonic"),
        os.path.join(script_dir, "..", "..", "tools", "mnemonic"),
    ]
    for path in candidates:
        abs_path = os.path.abspath(path)
        if os.path.isfile(os.path.join(abs_path, "mnemonic.py")):
            if abs_path not in sys.path:
                sys.path.insert(0, abs_path)
            break
    try:
        from mnemonic import derive
        return derive
    except ImportError:
        return None

_derive = _import_mnemonic()


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_bins(bins_path):
    """
    Load syllable bins from bins.json.
    Returns dict: int -> list of words.
    Falls back to DEFAULT_BINS_FULL if bins_path not found.
    """
    paths = [bins_path, DEFAULT_BINS, DEFAULT_BINS_FULL]
    for path in paths:
        if path and os.path.isfile(path):
            with io.open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            bins = {}
            for key, words in raw.items():
                if key == "_meta":
                    continue
                try:
                    bins[int(key)] = words
                except ValueError:
                    pass
            if bins:
                return bins, path
    raise IOError(
        "Syllable bins not found. Run:\n"
        "  python tools/cmudict/cmudict.py fetch\n"
        "  python tools/cmudict/cmudict.py export\n"
        "  python tools/wordfreq/wordfreq.py filter --bins docs/cmudict/bins.json")


def load_templates(templates_path=None):
    """
    Load haiku template library.
    Returns list of template dicts.
    """
    path = templates_path or DEFAULT_TEMPLATES
    if not os.path.isfile(path):
        raise IOError(
            "Template library not found: {0}\n"
            "Expected at tools/haiku/templates.json".format(path))
    with io.open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    templates = data.get("templates", [])
    if not templates:
        raise ValueError("Template library is empty.")
    return templates, data.get("_meta", {})


def load_fields(fields_path=None):
    """
    Load semantic field vocabulary.
    Returns dict: field_name -> field_data.
    """
    path = fields_path or DEFAULT_FIELDS
    if not os.path.isfile(path):
        raise IOError(
            "Semantic fields not found: {0}\n"
            "Expected at tools/haiku/fields.json".format(path))
    with io.open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    fields = {k: v for k, v in data.items() if k != "_meta"}
    if not fields:
        raise ValueError("Semantic fields file is empty.")
    return fields, data.get("_meta", {})


def load_pos_data(pos_path=None):
    """
    Load POS index: word -> list of POS tags.
    Returns dict or None if not available.

    The POS index is generated by wordfreq.py from COCA/SUBTLEX POS annotations.
    If not available, falls back to heuristic POS assignment.
    """
    path = pos_path or DEFAULT_POS_DATA
    if not os.path.isfile(path):
        return None
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── POS bin construction ──────────────────────────────────────────────────────

def build_pos_bins(syllable_bins, pos_index=None):
    """
    Build POS-indexed syllable bins.

    Structure:
        pos_bins[POS_tag][syllable_count] = [word, word, ...]

    If pos_index is None, uses heuristic suffix-based POS assignment
    as a fallback. This is less accurate but requires no corpus.

    Args:
        syllable_bins: dict int -> list of words (from load_bins)
        pos_index:     dict word -> [POS tags] or None

    Returns:
        dict: POS_tag -> {syllable_count -> [words]}
    """
    pos_bins = {}

    # Always populate closed-class words first
    for pos_tag, syl_dict in CLOSED_CLASS.items():
        if pos_tag not in pos_bins:
            pos_bins[pos_tag] = {}
        for syls, words in syl_dict.items():
            if syls not in pos_bins[pos_tag]:
                pos_bins[pos_tag][syls] = []
            for w in words:
                if w not in pos_bins[pos_tag][syls]:
                    pos_bins[pos_tag][syls].append(w)

    # Build syllable lookup
    word_syllables = {}
    for syls, words in syllable_bins.items():
        for word in words:
            word_syllables[word] = syls

    if pos_index is not None:
        # Use corpus POS data
        for word, pos_tags in pos_index.items():
            word_lower = word.lower()
            syls = word_syllables.get(word_lower)
            if syls is None:
                continue
            for tag in pos_tags:
                if tag not in pos_bins:
                    pos_bins[tag] = {}
                if syls not in pos_bins[tag]:
                    pos_bins[tag][syls] = []
                if word_lower not in pos_bins[tag][syls]:
                    pos_bins[tag][syls].append(word_lower)
    else:
        # Heuristic POS assignment from syllable bins
        for syls, words in syllable_bins.items():
            for word in words:
                for tag in _heuristic_pos(word):
                    if tag not in pos_bins:
                        pos_bins[tag] = {}
                    if syls not in pos_bins[tag]:
                        pos_bins[tag][syls] = []
                    if word not in pos_bins[tag][syls]:
                        pos_bins[tag][syls].append(word)

    # Sort all word lists alphabetically for determinism
    for tag in pos_bins:
        for syls in pos_bins[tag]:
            pos_bins[tag][syls].sort()

    return pos_bins


def _heuristic_pos(word):
    """
    Assign likely POS tags to a word based on suffix heuristics.
    Very rough — used only when no corpus POS data is available.
    Returns a list of likely POS tags.
    """
    w = word.lower()
    tags = []

    # Verb gerunds
    if w.endswith("ing") and len(w) > 5:
        tags.append("VBG")
    # Verb past participles / past tense
    if w.endswith("ed") and len(w) > 4:
        tags.append("VBN")
        tags.append("VBD")
    # Adjectives
    if w.endswith(("ful", "less", "ous", "ive", "al", "ent", "ant",
                    "ble", "ic", "ish", "ly")):
        tags.append("JJ")
    # Adverbs
    if w.endswith("ly") and len(w) > 4:
        tags.append("RB")
    # Nouns (plural)
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        tags.append("NNS")
    # Nouns (general — most words are nouns)
    if not tags or "VBG" not in tags:
        tags.append("NN")

    return tags or ["NN"]


# ── Semantic field integration ────────────────────────────────────────────────

def build_field_word_sets(fields):
    """
    Build a flat set of words for each field, combining all POS lists.
    Returns dict: field_name -> set of words.
    """
    field_sets = {}
    pos_lists = ["nouns", "adjectives", "verbs", "adverbs", "prepositions"]
    for field_name, field_data in fields.items():
        words = set()
        for pos_list in pos_lists:
            for w in field_data.get(pos_list, []):
                words.add(w.lower())
        field_sets[field_name] = words
    return field_sets


def field_candidates(pos_bins, pos_tag, syllables, field_words):
    """
    Get words matching POS tag, syllable count, and semantic field.

    Args:
        pos_bins:    POS-indexed syllable bins
        pos_tag:     required POS tag string
        syllables:   required syllable count
        field_words: set of words in the selected semantic field

    Returns:
        (candidates, fallback)
        candidates: words matching all three criteria (may be empty)
        fallback:   words matching POS + syllables only
    """
    # Try exact POS tag
    fallback = (pos_bins.get(pos_tag, {}).get(syllables, [])
                or _pos_fallback(pos_bins, pos_tag, syllables))

    # Field intersection
    candidates = [w for w in fallback if w in field_words]

    return candidates, fallback


def _pos_fallback(pos_bins, pos_tag, syllables):
    """
    Fallback word list: try related POS tags in order of preference.
    """
    for fallback_tag in POS_GROUPS.get(pos_tag, [pos_tag]):
        words = pos_bins.get(fallback_tag, {}).get(syllables, [])
        if words:
            return words
    return []


# ── Prime schedule ────────────────────────────────────────────────────────────

def _prime_digits(prime_str):
    return [int(d) for d in str(prime_str)]


def _prime_rev_digits(prime_str):
    return [int(d) for d in reversed(str(prime_str))]


def _sha256_seed(components):
    """Deterministic seed from a list of components."""
    s = ":".join(str(c) for c in components)
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)


# ── Grammar Engine ────────────────────────────────────────────────────────────

class GrammarEngine(object):
    """
    Grammar-aware haiku encoding/decoding engine.

    Encodes arbitrary data as eerily plausible AI-style nature haiku.
    Decoding recovers the original data exactly given the same prime,
    template library, field vocabulary, and POS bins.

    Usage:
        engine = GrammarEngine(
            pos_bins=pos_bins,
            templates=templates,
            fields=fields,
            prime_str=prime_str)

        haiku = engine.generate_haiku(position=0)
        lines = haiku['lines']
    """

    HAIKU_PATTERN = [5, 7, 5]

    def __init__(self, pos_bins, templates, fields, prime_str,
                 templates_version="haiku-templates-v1",
                 fields_version="haiku-fields-v1"):
        self.pos_bins           = pos_bins
        self.templates          = templates
        self.fields             = fields
        self.prime_str          = prime_str
        self.templates_version  = templates_version
        self.fields_version     = fields_version

        self._fwd  = _prime_digits(prime_str)
        self._rev  = _prime_rev_digits(prime_str)
        self._flen = len(self._fwd)
        self._rlen = len(self._rev)

        self._field_sets = build_field_word_sets(fields)
        self._field_names = sorted(self._field_sets.keys())

    # ── Schedule access ───────────────────────────────────────────────────────

    def _fwd_digit(self, pos):
        return self._fwd[pos % self._flen]

    def _rev_digit(self, pos):
        return self._rev[pos % self._rlen]

    # ── Template selection ────────────────────────────────────────────────────

    def select_template(self, global_pos):
        """
        Select a template from the library using forward digits.
        Returns template dict.
        """
        seed  = _sha256_seed(["template", global_pos,
                               self._fwd_digit(global_pos)])
        idx   = seed % len(self.templates)
        return self.templates[idx]

    # ── Field selection ───────────────────────────────────────────────────────

    def select_field(self, global_pos):
        """
        Select a semantic field using reversed digits.
        Returns (field_name, field_word_set).
        """
        seed  = _sha256_seed(["field", global_pos,
                               self._rev_digit(global_pos)])
        idx   = seed % len(self._field_names)
        name  = self._field_names[idx]
        return name, self._field_sets[name]

    # ── Word selection ────────────────────────────────────────────────────────

    def select_word(self, pos_tag, syllables, field_words, slot_pos):
        """
        Select a word for a given POS+syllable slot.

        Tries field-constrained candidates first; falls back to
        full POS+syllable bin if field intersection is empty.

        Returns (word, bin_index, used_field) or (None, None, False).
        """
        candidates, fallback = field_candidates(
            self.pos_bins, pos_tag, syllables, field_words)

        word_list = candidates if candidates else fallback
        if not word_list:
            return None, None, bool(candidates)

        seed     = _sha256_seed(["word", slot_pos,
                                  self._fwd_digit(slot_pos),
                                  self._rev_digit(slot_pos),
                                  pos_tag, syllables])
        idx      = seed % len(word_list)
        word     = word_list[idx]

        # Record index in the full fallback list for reversal
        try:
            bin_idx = fallback.index(word)
        except ValueError:
            bin_idx = idx

        return word, bin_idx, bool(candidates)

    # ── Haiku generation ──────────────────────────────────────────────────────

    def generate_haiku(self, global_pos=0):
        """
        Generate one haiku starting at global_pos in the prime schedule.

        Returns dict:
            lines           list of 3 strings
            words           list of all words in order
            slots           list of (pos_tag, syllables) per word
            bin_indices     list of bin indices per word (for reversal)
            template_id     template ID used
            field_name      semantic field used
            global_pos      starting position
            next_pos        position after last word
        """
        template            = self.select_template(global_pos)
        field_name, f_words = self.select_field(global_pos)

        lines       = []
        all_words   = []
        all_slots   = []
        all_indices = []
        slot_pos    = global_pos + 1   # +1: position 0 used for template+field

        for line_slots in template["lines"]:
            line_words = []
            for (pos_tag, syllables) in line_slots:
                word, bin_idx, used_field = self.select_word(
                    pos_tag, syllables, f_words, slot_pos)

                if word is None:
                    # Emergency fallback: any word from any bin
                    any_words = []
                    for syls in range(1, 7):
                        any_words = self.pos_bins.get("NN", {}).get(syls, [])
                        if any_words:
                            break
                    if any_words:
                        seed  = _sha256_seed(["fallback", slot_pos])
                        word  = any_words[seed % len(any_words)]
                        bin_idx = any_words.index(word)
                    else:
                        word    = "the"
                        bin_idx = 0

                line_words.append(word)
                all_words.append(word)
                all_slots.append((pos_tag, syllables))
                all_indices.append(bin_idx)
                slot_pos += 1

            lines.append(" ".join(line_words))

        return {
            "lines":        lines,
            "words":        all_words,
            "slots":        all_slots,
            "bin_indices":  all_indices,
            "template_id":  template["id"],
            "template_name":template["name"],
            "field_name":   field_name,
            "global_pos":   global_pos,
            "next_pos":     slot_pos,
        }

    # ── Verification ──────────────────────────────────────────────────────────

    def verify_haiku(self, haiku_result):
        """
        Verify that a haiku is correctly generated from the stored prime.

        Re-generates from global_pos and compares words.
        Returns (ok, errors).
        """
        recomputed = self.generate_haiku(haiku_result["global_pos"])
        errors = []

        if recomputed["template_id"] != haiku_result["template_id"]:
            errors.append("Template mismatch: expected {0}, got {1}".format(
                haiku_result["template_id"], recomputed["template_id"]))

        if recomputed["field_name"] != haiku_result["field_name"]:
            errors.append("Field mismatch: expected {0}, got {1}".format(
                haiku_result["field_name"], recomputed["field_name"]))

        if recomputed["words"] != haiku_result["words"]:
            for i, (w1, w2) in enumerate(
                    zip(recomputed["words"], haiku_result["words"])):
                if w1 != w2:
                    errors.append(
                        "Word mismatch at slot {0}: expected '{1}', got '{2}'".format(
                            i, w1, w2))

        return len(errors) == 0, errors


# ── Standalone CLI ────────────────────────────────────────────────────────────

def cmd_info(args):
    """Print summary of loaded bins, templates, and fields."""
    print("Haiku Grammar Engine — corpus summary")
    print("")

    # Bins
    bins_path = getattr(args, "bins", None) or DEFAULT_BINS
    try:
        bins, actual_path = load_bins(bins_path)
        total = sum(len(v) for v in bins.values())
        print("Syllable bins: {0}".format(actual_path))
        print("  {0:,} words across {1} bins".format(total, len(bins)))
        for n in sorted(bins.keys()):
            print("  {0} syllable{1}: {2:,} words".format(
                n, "" if n == 1 else "s", len(bins[n])))
    except IOError as e:
        print("Bins: NOT AVAILABLE — {0}".format(e))

    print("")

    # POS data
    pos_path = getattr(args, "pos", None) or DEFAULT_POS_DATA
    pos_data = load_pos_data(pos_path)
    if pos_data:
        print("POS index: {0}".format(pos_path))
        print("  {0:,} words with POS annotations".format(len(pos_data)))
    else:
        print("POS index: NOT AVAILABLE (using heuristic assignment)")
        print("  Run: python tools/wordfreq/wordfreq.py fetch")
        print("       python tools/wordfreq/wordfreq.py export --pos")

    print("")

    # Templates
    try:
        templates, tmeta = load_templates(getattr(args, "templates", None))
        print("Templates: {0}".format(
            getattr(args, "templates", None) or DEFAULT_TEMPLATES))
        print("  Version: {0}".format(tmeta.get("name", "unknown")))
        print("  {0} templates".format(len(templates)))
        for likelihood in ["very high", "high", "medium"]:
            count = sum(1 for t in templates
                        if t.get("ai_likelihood") == likelihood)
            print("  ai_likelihood={0}: {1}".format(likelihood, count))
    except IOError as e:
        print("Templates: NOT AVAILABLE — {0}".format(e))

    print("")

    # Fields
    try:
        fields, fmeta = load_fields(getattr(args, "fields", None))
        print("Semantic fields: {0}".format(
            getattr(args, "fields", None) or DEFAULT_FIELDS))
        print("  Version: {0}".format(fmeta.get("name", "unknown")))
        print("  {0} fields".format(len(fields)))
        seasonal = [k for k, v in fields.items() if v.get("season")]
        print("  Seasonal: {0}".format(", ".join(sorted(seasonal))))
    except IOError as e:
        print("Fields: NOT AVAILABLE — {0}".format(e))

    return 0


def cmd_pos_bins(args):
    """Print POS-indexed bin summary or words for a specific tag."""
    bins_path = getattr(args, "bins", None) or DEFAULT_BINS
    pos_path  = getattr(args, "pos",  None) or DEFAULT_POS_DATA
    tag_filter = getattr(args, "pos_tag", None)

    try:
        bins, _ = load_bins(bins_path)
    except IOError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    pos_data = load_pos_data(pos_path)
    pos_bins = build_pos_bins(bins, pos_data)

    if pos_data is None:
        print("(Using heuristic POS assignment — no corpus POS data found)")
        print("")

    if tag_filter:
        tag = tag_filter.upper()
        if tag not in pos_bins:
            print("POS tag '{0}' not found in bins.".format(tag),
                  file=sys.stderr)
            return 1
        print("POS: {0} — {1}".format(tag, POS_NAMES.get(tag, "")))
        print("")
        for syls in sorted(pos_bins[tag].keys()):
            words = pos_bins[tag][syls]
            print("  {0} syllable{1} ({2:,} words):".format(
                syls, "" if syls == 1 else "s", len(words)))
            sample = words[:10]
            print("    {0}{1}".format(
                ", ".join(sample),
                " ..." if len(words) > 10 else ""))
    else:
        print("POS-indexed syllable bins:")
        print("")
        for tag in sorted(pos_bins.keys()):
            total = sum(len(v) for v in pos_bins[tag].values())
            print("  {0:<6} {1:<28} {2:>6,} words".format(
                tag, POS_NAMES.get(tag, ""), total))

    return 0


def cmd_generate(args):
    """Generate a sample haiku using the grammar engine."""
    if _derive is None:
        print("Error: mnemonic.py not found. Cannot derive prime.",
              file=sys.stderr)
        return 1

    verse = getattr(args, "verse", None)
    if not verse:
        print("Error: --verse required.", file=sys.stderr)
        return 1

    result = _derive(verse.strip())
    prime_str = str(result["P"])

    bins_path = getattr(args, "bins", None) or DEFAULT_BINS
    pos_path  = getattr(args, "pos",  None) or DEFAULT_POS_DATA

    try:
        bins, _ = load_bins(bins_path)
    except IOError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    try:
        templates, tmeta = load_templates(getattr(args, "templates", None))
        fields, fmeta    = load_fields(getattr(args, "fields", None))
    except IOError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    pos_data = load_pos_data(pos_path)
    pos_bins = build_pos_bins(bins, pos_data)

    engine = GrammarEngine(
        pos_bins=pos_bins,
        templates=templates,
        fields=fields,
        prime_str=prime_str,
        templates_version=tmeta.get("name", "haiku-templates-v1"),
        fields_version=fmeta.get("name", "haiku-fields-v1"))

    n = getattr(args, "count", 1)
    pos = 0

    for i in range(n):
        haiku = engine.generate_haiku(global_pos=pos)
        print("")
        if n > 1:
            print("── Haiku {0}/{1} (template: {2}, field: {3}) ──".format(
                i+1, n, haiku["template_id"], haiku["field_name"]))
        else:
            print("Template: {0} ({1})".format(
                haiku["template_id"], haiku["template_name"]))
            print("Field:    {0}".format(haiku["field_name"]))
            print("")
        for line in haiku["lines"]:
            print("  {0}".format(line))
        pos = haiku["next_pos"]

    print("")
    return 0


def cmd_analyse(args):
    """Analyse the template library — slot distribution, syllable coverage."""
    try:
        templates, tmeta = load_templates(getattr(args, "templates", None))
    except IOError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    print("Template library analysis: {0}".format(
        tmeta.get("name", "unknown")))
    print("{0} templates".format(len(templates)))
    print("")

    # Count POS tag usage
    pos_counts = {}
    syl_counts = {}
    for t in templates:
        for line in t["lines"]:
            for (pos, syls) in line:
                pos_counts[pos]  = pos_counts.get(pos, 0) + 1
                syl_counts[syls] = syl_counts.get(syls, 0) + 1

    print("POS tag frequency across all slots:")
    for pos, count in sorted(pos_counts.items(),
                              key=lambda x: x[1], reverse=True):
        print("  {0:<6} {1:>4} slots   {2}".format(
            pos, count, POS_NAMES.get(pos, "")))

    print("")
    print("Syllable count frequency across all slots:")
    for syls, count in sorted(syl_counts.items()):
        bar = "█" * min(count, 40)
        print("  {0} syllable{1}: {2:>3} slots  {3}".format(
            syls, "" if syls == 1 else "s", count, bar))

    print("")
    print("ai_likelihood distribution:")
    for likelihood in ["very high", "high", "medium", "low"]:
        count = sum(1 for t in templates
                    if t.get("ai_likelihood") == likelihood)
        if count:
            print("  {0:<12}: {1} templates".format(likelihood, count))

    return 0


# ── CLI parser ────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="haiku_grammar",
        description=(
            "Grammar-aware haiku encoding engine.\n"
            "\n"
            "Builds POS-indexed syllable bins from cmudict + wordfreq data,\n"
            "loads haiku template and semantic field libraries, and provides\n"
            "the GrammarEngine for use by haiku_twist.py --grammar mode.\n"
            "\n"
            "Also usable standalone for corpus inspection and sample generation.\n"
            "\n"
            "TEST IMPLEMENTATION — not yet normatively specified.\n"
            "\n"
            "Dedicated to Felix 'FX' Lindner (1975-2026)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument("--bins", default=None, metavar="FILE",
        help="syllable bins JSON (default: docs/cmudict/bins-common.json)")
    p.add_argument("--pos", default=None, metavar="FILE",
        help="POS index JSON (default: docs/wordfreq/pos-index.json)")
    p.add_argument("--templates", default=None, metavar="FILE",
        help="template library JSON (default: tools/haiku/templates.json)")
    p.add_argument("--fields", default=None, metavar="FILE",
        help="semantic fields JSON (default: tools/haiku/fields.json)")

    sub = p.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("info",
        help="print corpus and library summary")

    pp = sub.add_parser("pos-bins",
        help="print POS-indexed bin summary")
    pp.add_argument("--pos-tag", default=None, metavar="TAG",
        help="show words for specific POS tag (e.g. VBG, JJ, NN)")

    pg = sub.add_parser("generate",
        help="generate sample haiku using the grammar engine")
    pg.add_argument("--verse", required=True, metavar="TEXT",
        help="key verse for prime derivation")
    pg.add_argument("--count", type=int, default=1, metavar="N",
        help="number of haiku to generate (default: 1)")

    sub.add_parser("analyse",
        help="analyse template library slot distribution")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    try:
        if args.command == "info":     return cmd_info(args)
        if args.command == "pos-bins": return cmd_pos_bins(args)
        if args.command == "generate": return cmd_generate(args)
        if args.command == "analyse":  return cmd_analyse(args)
    except (IOError, ValueError, KeyboardInterrupt) as e:
        print("Error: {0}".format(e), file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
