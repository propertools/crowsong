#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
quickref.py - FDS Unicode quick reference card generator

Generates human-readable Unicode quick reference tables formatted
for printing and archival, suitable for use as FDS decoding aids.
No external dependencies: uses Python stdlib unicodedata.

Usage:
    python quickref.py list
    python quickref.py block <name>
    python quickref.py range <start> <end> [--name NAME]
    python quickref.py preset <name>
    python quickref.py full [--blocks tags] [--output FILE]

Presets: ascii, crowsong, vesper, emoji, math, european, cjk

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""
from __future__ import print_function, unicode_literals
import argparse, binascii, sys, time, unicodedata

PY2 = (sys.version_info[0] == 2)

BLOCKS = [
    (0x0000,0x007F,"Basic Latin",["ascii","crowsong","vesper"]),
    (0x0080,0x00FF,"Latin-1 Supplement",["latin","crowsong","vesper"]),
    (0x0100,0x017F,"Latin Extended-A",["latin","vesper"]),
    (0x0180,0x024F,"Latin Extended-B",["latin","vesper"]),
    (0x0250,0x02AF,"IPA Extensions",["latin","vesper"]),
    (0x0300,0x036F,"Combining Diacritical Marks",["latin"]),
    (0x0370,0x03FF,"Greek and Coptic",["european","math","crowsong","vesper"]),
    (0x0400,0x04FF,"Cyrillic",["european","crowsong","vesper"]),
    (0x0500,0x052F,"Cyrillic Supplement",["european"]),
    (0x0530,0x058F,"Armenian",["european","vesper"]),
    (0x0590,0x05FF,"Hebrew",["european","vesper"]),
    (0x0600,0x06FF,"Arabic",["middle-eastern","vesper"]),
    (0x0700,0x074F,"Syriac",["middle-eastern","vesper"]),
    (0x0900,0x097F,"Devanagari",["south-asian","vesper"]),
    (0x0980,0x09FF,"Bengali",["south-asian","vesper"]),
    (0x0A00,0x0A7F,"Gurmukhi",["south-asian"]),
    (0x0A80,0x0AFF,"Gujarati",["south-asian"]),
    (0x0B00,0x0B7F,"Oriya",["south-asian"]),
    (0x0B80,0x0BFF,"Tamil",["south-asian","vesper"]),
    (0x0C00,0x0C7F,"Telugu",["south-asian"]),
    (0x0C80,0x0CFF,"Kannada",["south-asian"]),
    (0x0D00,0x0D7F,"Malayalam",["south-asian"]),
    (0x0E00,0x0E7F,"Thai",["south-asian","vesper"]),
    (0x0E80,0x0EFF,"Lao",["south-asian"]),
    (0x0F00,0x0FFF,"Tibetan",["south-asian"]),
    (0x1000,0x109F,"Myanmar",["south-asian"]),
    (0x10A0,0x10FF,"Georgian",["european","vesper"]),
    (0x1100,0x11FF,"Hangul Jamo",["east-asian"]),
    (0x2000,0x206F,"General Punctuation",["symbol","crowsong","vesper"]),
    (0x2070,0x209F,"Superscripts and Subscripts",["math","symbol"]),
    (0x20A0,0x20CF,"Currency Symbols",["symbol","crowsong","vesper"]),
    (0x2100,0x214F,"Letterlike Symbols",["symbol","math","vesper"]),
    (0x2150,0x218F,"Number Forms",["math"]),
    (0x2190,0x21FF,"Arrows",["symbol","math","crowsong","vesper"]),
    (0x2200,0x22FF,"Mathematical Operators",["math","crowsong","vesper"]),
    (0x2300,0x23FF,"Miscellaneous Technical",["symbol","vesper"]),
    (0x2460,0x24FF,"Enclosed Alphanumerics",["symbol"]),
    (0x2500,0x257F,"Box Drawing",["symbol","vesper"]),
    (0x2580,0x259F,"Block Elements",["symbol"]),
    (0x25A0,0x25FF,"Geometric Shapes",["symbol","crowsong","vesper"]),
    (0x2600,0x26FF,"Miscellaneous Symbols",["symbol","crowsong","vesper"]),
    (0x2700,0x27BF,"Dingbats",["symbol","vesper"]),
    (0x2E80,0x2EFF,"CJK Radicals Supplement",["east-asian"]),
    (0x3000,0x303F,"CJK Symbols and Punctuation",["east-asian","crowsong","vesper"]),
    (0x3040,0x309F,"Hiragana",["east-asian","crowsong","vesper"]),
    (0x30A0,0x30FF,"Katakana",["east-asian","crowsong","vesper"]),
    (0x4E00,0x9FFF,"CJK Unified Ideographs",["east-asian","crowsong","vesper"]),
    (0xAC00,0xD7AF,"Hangul Syllables",["east-asian","vesper"]),
    (0x1F300,0x1F5FF,"Misc Symbols and Pictographs",["emoji","crowsong"]),
    (0x1F600,0x1F64F,"Emoticons",["emoji","crowsong"]),
    (0x1F680,0x1F6FF,"Transport and Map Symbols",["emoji","crowsong"]),
    (0x1F900,0x1F9FF,"Supplemental Symbols and Pictographs",["emoji","crowsong"]),
    (0x1FA70,0x1FAFF,"Symbols and Pictographs Extended-A",["emoji"]),
]

PRESETS = {
    "ascii":    {"title":"FDS ASCII Quick Reference",
                 "tags":["ascii"],"grid":True,"proc":True},
    "crowsong": {"title":"FDS Crowsong Deployment Quick Reference",
                 "tags":["crowsong"],"grid":True,"proc":True},
    "vesper":   {"title":"FDS Vesper Archive Edition",
                 "tags":["vesper"],"grid":True,"proc":True},
    "emoji":    {"title":"FDS Emoji Quick Reference (WIDTH/7)",
                 "tags":["emoji"],"grid":False,"proc":False},
    "math":     {"title":"FDS Mathematical Symbols Reference",
                 "tags":["math"],"grid":False,"proc":False},
    "european": {"title":"FDS European Scripts Reference",
                 "tags":["european","latin"],"grid":True,"proc":False},
    "cjk":      {"title":"FDS CJK Reference",
                 "tags":["east-asian"],"grid":False,"proc":False},
}

LW = 72

def hrule():  return "=" * LW
def brule():  return "+" + "=" * (LW-2) + "+"
def bline(s=""): return "|" + s.ljust(LW-2) + "|"

def field_width(end_cp):
    return 7 if end_cp > 99999 else 5

def assigned(start, end):
    out = []
    for cp in range(start, min(end+1, 0x110000)):
        try:
            ch = chr(cp)
            n  = unicodedata.name(ch, "")
            c  = unicodedata.category(ch)
            if n and c not in ("Cs","Co","Cn"):
                if c == "Cc" and cp not in (9,10,13,32): continue
                out.append((cp, ch, n))
        except: pass
    return out

def render_block(start, end, name, max_detail=48):
    entries = assigned(start, end)
    if not entries: return ""
    w   = field_width(end)
    pad = "0" * w
    out = []
    needs7 = end > 99999
    tag = "  WIDTH/7 REQUIRED" if needs7 else ""
    out.append(hrule())
    out.append("  {0} (U+{1:04X}\u2013U+{2:04X})  {3} assigned{4}".format(
        name, start, end, len(entries), tag))
    out.append(hrule())
    out.append("")
    if needs7:
        out.append("  Header: ENC: UCS \u00b7 DEC \u00b7 COL/6 \u00b7 PAD/{0} \u00b7 WIDTH/7".format(pad))
        out.append("")
    if len(entries) <= max_detail:
        for cp, ch, n in entries:
            out.append("  {0}  {1}  {2}".format("{0:0{1}d}".format(cp,w), ch, n[:45]))
    else:
        cols = 8
        for i in range(0, len(entries), cols):
            row = entries[i:i+cols]
            out.append("  " + "  ".join("{0:>7}={1}".format(cp,ch) for cp,ch,_ in row))
    out.append("")
    return "\n".join(out)

def render_grid():
    out = [hrule(), "  QUICK DECODE GRID \u2014 ASCII 32\u2013126", "-"*LW, ""]
    out.append("   Val  Ch    Val  Ch    Val  Ch    Val  Ch    Val  Ch")
    out.append("  " + "-"*58)
    entries = [(cp, chr(cp)) for cp in range(32, 127)]
    for i in range(0, len(entries), 5):
        row = entries[i:i+5]
        out.append("  " + "    ".join("{0:>6}  {1}".format(cp,ch) for cp,ch in row))
    out.append("")
    return "\n".join(out)

def render_proc():
    return "\n".join([
        hrule(),
        "  DECODING PROCEDURE (no software required)",
        hrule(), "",
        "  1. Read tokens left to right, top to bottom.",
        "  2. Skip any token equal to the padding value (00000 / 0000000).",
        "  3. For each remaining token:",
        "       a. Find the decimal value in this table.",
        "       b. Write the character shown.",
        "       c. If not found: write [?TOKEN] and continue.",
        "  4. Newline (00010) = start a new line.",
        "  5. A corrupted token affects only that character. Continue.",
        "  6. Verify: total non-padding token count must match trailer.",
        "",
        "  Field widths:",
        "    WIDTH/5  (default)  5-digit tokens, range 00000\u201399999",
        "    WIDTH/7  (extended) 7-digit tokens, range 0000000\u20131114111",
        "                        Required for emoji and supplementary planes.",
        "",
    ])

def render_header(title, generated):
    return "\n".join([
        brule(),
        bline("  " + title),
        bline("  Unicode Quick Reference Table for FDS Decoding"),
        bline(),
        bline("  Format: UCS \u00b7 DEC \u00b7 COL/6 \u00b7 PAD/00000 \u00b7 WIDTH/5"),
        bline("  Extended: WIDTH/7 required for code points above 99999"),
        bline(),
        bline("  Generated: " + generated),
        bline("  draft-darley-fds-00  \u00b7  github.com/propertools/crowsong"),
        brule(),
    ])

def render_footer():
    return "\n".join([
        brule(),
        bline(),
        bline("  Full Unicode reference: https://unicode.org/charts/"),
        bline("  FDS specification:      draft-darley-fds-00"),
        bline("  Repository:             github.com/propertools/crowsong"),
        bline(),
        bline("  SIGNAL SURVIVES"),
        brule(),
    ])

def blocks_for_tags(tags):
    seen, result = set(), []
    for s,e,n,t in BLOCKS:
        if any(x in t for x in tags) and n not in seen:
            result.append((s,e,n)); seen.add(n)
    return result

def build_card(block_list, title, proc=True, grid=True):
    generated = time.strftime("%Y-%m-%d")
    parts = [render_header(title, generated), ""]
    if proc: parts.append(render_proc())
    for s,e,n in block_list:
        sec = render_block(s,e,n)
        if sec: parts.append(sec)
    if grid: parts.append(render_grid())
    parts += ["", render_footer(), ""]
    return "\n".join(parts)

def write_out(content, outfile=None):
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(content)
        print("Written: " + outfile, file=sys.stderr)
    else:
        if PY2: sys.stdout.write(content.encode("utf-8"))
        else:   sys.stdout.write(content)

def build_parser():
    p = argparse.ArgumentParser(
        description="FDS Unicode quick reference card generator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python quickref.py list\n"
            "  python quickref.py block Greek\n"
            "  python quickref.py block CJK\n"
            "  python quickref.py range 0x1F600 0x1F64F --name Emoticons\n"
            "  python quickref.py preset ascii\n"
            "  python quickref.py preset crowsong > quickref-crowsong.txt\n"
            "  python quickref.py preset vesper   > quickref-vesper.txt\n"
            "  python quickref.py full            > quickref-full.txt\n"
        )
    )
    sub = p.add_subparsers(dest="command"); sub.required = True

    sub.add_parser("list", help="list all blocks and presets")

    pb = sub.add_parser("block", help="reference card for a named block")
    pb.add_argument("name"); pb.add_argument("--output","-o",metavar="FILE")

    pr = sub.add_parser("range", help="reference card for a code point range")
    pr.add_argument("start"); pr.add_argument("end")
    pr.add_argument("--name",default="Custom Range")
    pr.add_argument("--output","-o",metavar="FILE")

    pp = sub.add_parser("preset", help="named preset card")
    pp.add_argument("name", choices=sorted(PRESETS.keys()))
    pp.add_argument("--output","-o",metavar="FILE")

    pf = sub.add_parser("full", help="complete multi-block reference")
    pf.add_argument("--blocks",metavar="TAGS")
    pf.add_argument("--output","-o",metavar="FILE")

    return p

def main():
    args = build_parser().parse_args()
    try:
        if args.command == "list":
            print("Blocks ({0}):".format(len(BLOCKS)))
            for s,e,n,t in BLOCKS:
                print("  {0:<45} U+{1:04X}-U+{2:04X}  {3}".format(
                    n, s, e, ",".join(t[:3])))
            print("\nPresets: " + ", ".join(sorted(PRESETS.keys())))
            return 0

        if args.command == "block":
            q = args.name.lower()
            matches = [(s,e,n) for s,e,n,_ in BLOCKS if q in n.lower()]
            if not matches:
                print("Error: no block matching '{0}'".format(args.name), file=sys.stderr)
                return 1
            write_out(build_card(matches, "FDS Reference \u2014 " + args.name,
                                 proc=len(matches)==1, grid=False), args.output)
            return 0

        if args.command == "range":
            s,e = int(args.start,0), int(args.end,0)
            write_out(build_card([(s,e,args.name)],
                                 "FDS Reference \u2014 " + args.name,
                                 proc=True, grid=False), args.output)
            return 0

        if args.command == "preset":
            cfg = PRESETS[args.name]
            bl  = blocks_for_tags(cfg["tags"])
            write_out(build_card(bl, cfg["title"],
                                 proc=cfg["proc"], grid=cfg["grid"]),
                      args.output)
            return 0

        if args.command == "full":
            if args.blocks:
                tags = [t.strip() for t in args.blocks.split(",")]
                bl   = blocks_for_tags(tags)
            else:
                bl = [(s,e,n) for s,e,n,_ in BLOCKS]
            write_out(build_card(bl, "FDS Complete Unicode Quick Reference",
                                 proc=True, grid=True), args.output)
            return 0

    except (IOError, ValueError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1
    return 1

if __name__ == "__main__":
    sys.exit(main())
