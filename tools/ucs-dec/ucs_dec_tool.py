#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ucs_dec_tool.py — Fox Decimal Script encoder/decoder

Encodes text as zero-padded decimal Unicode code points.
Decodes zero-padded decimal Unicode code points back to text.

Reference implementation for draft-darley-fds-00.

Designed for degraded-channel transmission survivability:
fax, OCR, manual transcription, Morse.

Default format: UCS · DEC · COL/6 · PAD/00000 · WIDTH/5
Actual encoding parameters are artifact-specific; see ENC: header.
Informal name: Fox Decimal Script (FDS)

Compatibility: Python 2.7+ / 3.x
Note: shebang uses 'python' intentionally to support constrained environments.

Usage:
    echo "Signal survives." | python ucs_dec_tool.py --encode
    cat encoded.txt | python ucs_dec_tool.py --decode
    cat encoded.txt | python ucs_dec_tool.py --verify
    echo "Signal survives." | python ucs_dec_tool.py -e | python ucs_dec_tool.py -d

    # Produce a self-describing framed artifact:
    cat source.txt | python ucs_dec_tool.py -e --frame
    cat source.txt | python ucs_dec_tool.py -e --frame --ref SI-2084-FP-001 --med FLASH

    # Decode a framed artifact (partial frame-aware mode; supported parameters extracted automatically):
    cat framed.txt | python ucs_dec_tool.py -d

    # Verify a framed artifact (count + CRC32 + DESTROY semantics):
    cat framed.txt | python ucs_dec_tool.py -v

Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import re
import sys
import unicodedata

UNICODE_MAX  = 0x10FFFF
BOX_INNER    = 41         # interior width of Print Profile box
MIDDLE_DOT   = "\u00b7"   # U+00B7, the FDS field separator
DESTROY_FLAG = "IF COUNT FAILS: DESTROY IMMEDIATELY"

# Regex for the ENC: header line (inside or outside a box border)
_ENC_RE = re.compile(
    r"ENC:\s+UCS\s*[" + MIDDLE_DOT + r"\*\xb7]\s*DEC"
    r"(?:\s*[" + MIDDLE_DOT + r"\*\xb7]\s*COL/(\d+))?"
    r"(?:\s*[" + MIDDLE_DOT + r"\*\xb7]\s*PAD/(\w+))?"
    r"(?:\s*[" + MIDDLE_DOT + r"\*\xb7]\s*WIDTH/(\d+))?"
)

# Regex for WIDTH/N appearing on its own line (Print Profile splits it)
_WIDTH_RE = re.compile(r"\bWIDTH/(\d+)\b")

# Regex for the trailer line
_TRAILER_RE = re.compile(
    r"(\d+)\s+VALUES?\s*[" + MIDDLE_DOT + r"\*\xb7\s]\s*CRC32:([0-9A-Fa-f]+)"
)

PY2 = (sys.version_info[0] == 2)

if PY2:
    text_type = unicode  # noqa: F821
    to_chr = unichr      # noqa: F821
else:
    text_type = str
    to_chr = chr


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _read_stdin():
    """Read stdin as Unicode text, assuming UTF-8 on Python 2."""
    if PY2:
        data = sys.stdin.read()
        if not isinstance(data, unicode):  # noqa: F821
            data = data.decode("utf-8")
        return data
    return sys.stdin.read()


def _write_stdout(text):
    """Write Unicode text to stdout, encoding to UTF-8 on Python 2."""
    if PY2:
        if isinstance(text, unicode):  # noqa: F821
            sys.stdout.write(text.encode("utf-8"))
        else:
            sys.stdout.write(text)
    else:
        sys.stdout.write(text)


# ── Token helpers ─────────────────────────────────────────────────────────────

def _parse_int_token(token):
    """Parse a decimal token to int, returning None on failure."""
    try:
        return int(token)
    except ValueError:
        return None


def _is_valid_codepoint(value):
    """Return True if value is a valid Unicode code point."""
    return 0 <= value <= UNICODE_MAX


def _is_payload_line(line):
    """
    Return True if line contains only decimal tokens and whitespace.

    Used to distinguish payload rows from frame structure lines
    (box borders, banners, field lines) during frame parsing.
    """
    s = line.strip()
    if not s:
        return False
    return all(t.isdigit() for t in s.split())


def _strip_box(line):
    """Strip Print Profile box border characters from a line."""
    return line.strip().strip("|+").strip()


# ── Frame parser ──────────────────────────────────────────────────────────────

def parse_frame(text):
    """
    Parse an FDS-FRAME or FDS Print Profile artifact.

    Handles both bare FDS-FRAME (linear header/payload/trailer) and
    Print Profile artifacts (boxed header, payload, boxed footer).

    WIDTH may appear on a separate line from ENC: in Print Profile
    artifacts; both forms are detected.

    CRC32 is computed over the payload string exactly as extracted,
    with leading/trailing whitespace stripped, matching the computation
    performed by frame() at generation time.

    Signature lines are detected and preserved, but signature
    verification is not yet implemented.

    Args:
        text: Full artifact text (header + payload + trailer)

    Returns:
        dict with keys:
            header_found    (bool)
            width           (int, default 5)
            cols            (int, default 6)
            pad_token       (str)
            payload_str     (str)
            trailer_found   (bool)
            declared_count  (int or None)
            declared_crc    (str or None, uppercase hex)
            destroy_flag    (bool)
            sig_line        (str or None)
    """
    result = {
        "header_found":   False,
        "width":          5,
        "cols":           6,
        "pad_token":      None,
        "payload_str":    "",
        "trailer_found":  False,
        "declared_count": None,
        "declared_crc":   None,
        "destroy_flag":   False,
        "sig_line":       None,
    }

    payload_lines = []
    header_seen = False

    for line in text.splitlines():
        clean = _strip_box(line)

        m = _ENC_RE.match(clean)
        if m:
            result["header_found"] = True
            header_seen = True
            if m.group(1) is not None:
                result["cols"] = int(m.group(1))
            if m.group(2) is not None:
                result["pad_token"] = m.group(2)
            if m.group(3) is not None:
                result["width"] = int(m.group(3))
            continue

        if header_seen and not result["payload_str"] and not payload_lines:
            mw = _WIDTH_RE.search(clean)
            if mw and not clean.startswith("ENC:"):
                result["width"] = int(mw.group(1))
                if result["pad_token"] is None:
                    result["pad_token"] = "0" * result["width"]
                continue

        if header_seen and clean.startswith("SIG:") and not payload_lines:
            result["sig_line"] = clean
            continue

        if DESTROY_FLAG in line:
            result["destroy_flag"] = True

        mt = _TRAILER_RE.search(clean)
        if mt:
            result["trailer_found"] = True
            result["declared_count"] = int(mt.group(1))
            result["declared_crc"] = mt.group(2).upper()
            continue

        if header_seen and _is_payload_line(line):
            payload_lines.append(line)

    if result["pad_token"] is None:
        result["pad_token"] = "0" * result["width"]

    result["payload_str"] = "\n".join(payload_lines)
    return result


def verify_frame(parsed):
    """
    Verify count and CRC32 of a parsed frame.

    Args:
        parsed: dict returned by parse_frame()

    Returns:
        dict with keys:
            count_ok     (bool)
            crc_ok       (bool)
            actual_count (int)
            actual_crc   (str, uppercase hex)
    """
    pad = parsed["pad_token"]
    payload = parsed["payload_str"].strip()
    tokens = payload.split()

    actual_count = len([t for t in tokens if t != pad])
    crc = binascii.crc32(payload.encode("utf-8")) & 0xFFFFFFFF
    actual_crc = format(crc, "08X")

    return {
        "count_ok":     (actual_count == parsed["declared_count"]),
        "crc_ok":       (actual_crc == parsed["declared_crc"]),
        "actual_count": actual_count,
        "actual_crc":   actual_crc,
    }


# ── Core encode / decode ──────────────────────────────────────────────────────

def encode(text, width=5, cols=6):
    """
    Encode text into zero-padded decimal Unicode code points.

    Input is NFC-normalised before encoding, per Section 2.1 of
    draft-darley-fds-00.

    Args:
        text: Input string (any Unicode)
        width: Zero-padding width per value (default: 5)
        cols: Values per row (default: 6, 0 = no wrapping)

    Returns:
        Encoded string — whitespace-separated values, newline-wrapped at cols.
    """
    text = unicodedata.normalize("NFC", text)
    values = ["{0:0{1}d}".format(ord(ch), width) for ch in text]

    if cols == 0:
        return " ".join(values)

    pad = "0" * width
    lines = []

    for start in range(0, len(values), cols):
        chunk = values[start:start + cols]
        chunk.extend([pad] * (cols - len(chunk)))
        lines.append("  ".join(chunk))

    return "\n".join(lines)


def decode(data, width=5, skip_null=True):
    """
    Decode zero-padded decimal Unicode code points back to text.

    If data contains an FDS-FRAME or Print Profile header, supported
    framing parameters are extracted automatically and may override
    the width argument.

    Args:
        data: Input string — bare payload or framed artifact
        width: Default field width if no frame header present (default: 5)
        skip_null: If True, skip codepoint 0 / padding tokens (default: True)

    Returns:
        Decoded Unicode string.

    Invalid tokens are silently ignored by design.
    """
    parsed = parse_frame(data)

    if parsed["header_found"]:
        width = parsed["width"]
        payload = parsed["payload_str"]
    else:
        payload = data

    pad = "0" * width
    chars = []

    for token in payload.split():
        value = _parse_int_token(token)
        if value is None or not _is_valid_codepoint(value):
            continue
        if skip_null and token == pad:
            continue
        chars.append(to_chr(value))

    return "".join(chars)


def verify(data, width=5):
    """
    Validate token shape and count tokens in encoded data.

    If data contains an FDS-FRAME or Print Profile header, encoding
    parameters and declared count/CRC32 are verified automatically.

    For bare payloads (no frame header), validates token shape only —
    checks that each token has the expected field width and represents
    a valid Unicode code point.

    For framed artifacts, verifies declared count and CRC32 when present.
    Signature verification is not yet implemented.

    For WIDTH/7 bare artifacts, pass --width 7 explicitly.

    Args:
        data: Input string — bare payload or framed artifact
        width: Default field width if no frame header present (default: 5)

    Returns:
        Tuple of (total_count, valid_count, invalid_tokens, frame_result)
        where frame_result is None for bare payloads, or the dict
        returned by verify_frame() for framed artifacts.
    """
    parsed = parse_frame(data)

    if parsed["header_found"]:
        width = parsed["width"]
        payload = parsed["payload_str"]
    else:
        payload = data

    tokens = payload.split()
    invalid = []

    for token in tokens:
        value = _parse_int_token(token)
        if value is None or len(token) != width or not _is_valid_codepoint(value):
            invalid.append(token)

    total = len(tokens)
    valid = total - len(invalid)
    frame_result = verify_frame(parsed) if parsed["header_found"] else None

    return total, valid, invalid, frame_result


# ── Print Profile frame generation ────────────────────────────────────────────

def _box_rule():
    """Return a horizontal rule for the Print Profile box."""
    return "+" + "-" * BOX_INNER + "+"


def _box_line(content):
    """Return a content line padded to BOX_INNER width."""
    inner = "  " + content
    return "|" + inner.ljust(BOX_INNER) + "|"


def frame(payload, ref="", page="1/1", med="FLASH", attribution="",
          width=5, cols=6):
    """
    Wrap an encoded payload in a self-describing Print Profile artifact.

    The frame records encoding parameters, value count, and CRC32 in a
    human-readable box border suitable for printing on physical media.

    CRC32 is computed over the payload string exactly as transmitted
    (post-encode, pre-frame, trailing whitespace stripped).
    Value count excludes padding null tokens.

    Args:
        payload: Encoded FDS payload string (output of encode())
        ref: Artifact reference ID, e.g. 'SI-2084-FP-001' (optional)
        page: Page designation, e.g. '1/1' (default: '1/1')
        med: Medium designation, e.g. 'FLASH', 'PAPER' (default: FLASH)
        attribution: Attribution string for footer, e.g. 'Sakura Inari' (optional)
        width: Field width used for encoding (default: 5)
        cols: Columns used for encoding (default: 6)

    Returns:
        Complete Print Profile artifact as a string.
    """
    pad = "0" * width
    tokens = payload.split()
    real_count = len([t for t in tokens if t != pad])
    crc = binascii.crc32(payload.strip().encode("utf-8")) & 0xFFFFFFFF
    crc_str = format(crc, "08X")

    enc_line = "ENC: UCS {d} DEC {d} COL/{c} {d} PAD/{p}".format(
        d=MIDDLE_DOT, c=cols, p=pad)
    wid_line = "WIDTH/{w} {d} MED: {m}".format(
        d=MIDDLE_DOT, w=width, m=med)
    cnt_line = "{n} VALUES {d} CRC32:{crc}".format(
        d=MIDDLE_DOT, n=real_count, crc=crc_str)

    header_lines = [_box_rule()]
    if ref:
        header_lines.append(_box_line(
            "REF: {0}  PAGE {1}".format(ref, page)))
    header_lines.append(_box_line(enc_line))
    header_lines.append(_box_line(wid_line))
    header_lines.append(_box_line("DESTROY AFTER READING"))
    header_lines.append(_box_rule())

    footer_lines = [
        _box_rule(),
        _box_line(cnt_line),
        _box_line("VERIFY COUNT BEFORE USE"),
        _box_line(DESTROY_FLAG),
    ]
    if attribution:
        footer_lines.append(_box_line(attribution))
    footer_lines.append(_box_rule())

    parts = [
        "RESERVED -- SINGLE USE",
        "\n".join(header_lines),
        "",
        payload,
        "",
        "\n".join(footer_lines),
        "",
        "                   RESERVED -- SINGLE USE",
    ]

    return "\n".join(parts)


# ── argparse helpers ──────────────────────────────────────────────────────────

def _positive_int(value):
    """argparse type: integer >= 1"""
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return ivalue


def _nonnegative_int(value):
    """argparse type: integer >= 0"""
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return ivalue


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    """Construct and return the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Fox Decimal Script (FDS) — UCS decimal encoder/decoder.\n"
            "Reference implementation for draft-darley-fds-00.\n"
            "Encodes any Unicode text as zero-padded decimal code points.\n"
            "Designed for degraded-channel transmission survivability."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  echo 'Hello' | python ucs_dec_tool.py --encode\n"
            "  cat encoded.txt | python ucs_dec_tool.py --decode\n"
            "  cat encoded.txt | python ucs_dec_tool.py --verify\n"
            "  echo 'Signal.' | python ucs_dec_tool.py -e | python ucs_dec_tool.py -d\n"
            "\n"
            "  # Produce a Print Profile artifact:\n"
            "  python ucs_dec_tool.py -e \\\n"
            "    --frame --ref SI-2084-FP-001 --med FLASH --attribution 'Sakura Inari' \\\n"
            "    < archive/second-law-blues.txt \\\n"
            "    > archive/flash-paper-SI-2084-FP-001-framed.txt\n"
            "\n"
            "  # Produce payload only:\n"
            "  python ucs_dec_tool.py -e \\\n"
            "    < archive/second-law-blues.txt \\\n"
            "    > archive/flash-paper-SI-2084-FP-001-payload.txt\n"
            "\n"
            "  # Decode a framed artifact (parameters extracted automatically):\n"
            "  python ucs_dec_tool.py -d \\\n"
            "    < archive/flash-paper-SI-2084-FP-001-framed.txt\n"
            "\n"
            "  # Verify a framed artifact (count + CRC32 + DESTROY semantics):\n"
            "  python ucs_dec_tool.py -v \\\n"
            "    < archive/flash-paper-SI-2084-FP-001-framed.txt\n"
        )
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-e", "--encode", action="store_true",
                      help="Encode stdin text to FDS format")
    mode.add_argument("-d", "--decode", action="store_true",
                      help="Decode FDS payload or framed artifact to text")
    mode.add_argument("-v", "--verify", action="store_true",
                      help="Validate token shape; verify count + CRC32 if framed")

    parser.add_argument(
        "--width", type=_positive_int, default=5, metavar="N",
        help="Zero-padding width per value (default: 5; overridden by frame header)")
    parser.add_argument(
        "--cols", type=_nonnegative_int, default=6, metavar="N",
        help="Values per row when encoding (default: 6, 0 = no wrapping)")
    parser.add_argument(
        "--keep-null", action="store_true",
        help="Preserve null codepoints during decode (default: skip)")
    parser.add_argument(
        "--frame", action="store_true",
        help="Wrap encoded output in a Print Profile artifact")
    parser.add_argument(
        "--ref", default="", metavar="ID",
        help="Artifact reference ID for Print Profile, e.g. SI-2084-FP-001")
    parser.add_argument(
        "--page", default="1/1", metavar="N/T",
        help="Page designation for Print Profile (default: 1/1)")
    parser.add_argument(
        "--med", default="FLASH", metavar="MEDIUM",
        help="Medium designation for Print Profile (default: FLASH)")
    parser.add_argument(
        "--attribution", default="", metavar="TEXT",
        help="Attribution string for Print Profile footer")

    return parser


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    data = _read_stdin()
    parsed = parse_frame(data)

    # ── encode ────────────────────────────────────────────────────────────────
    if args.encode:
        payload = encode(data, width=args.width, cols=args.cols)
        if args.frame:
            output = frame(payload, ref=args.ref, page=args.page,
                           med=args.med, attribution=args.attribution,
                           width=args.width, cols=args.cols)
        else:
            output = payload
        _write_stdout(output)
        if not output.endswith("\n"):
            _write_stdout("\n")
        return 0

    # ── decode ────────────────────────────────────────────────────────────────
    if args.decode:
        if parsed["header_found"] and parsed["trailer_found"]:
            vr = verify_frame(parsed)
            if parsed["destroy_flag"] and not (vr["count_ok"] and vr["crc_ok"]):
                print("ERROR: frame verification failed — DESTROY IMMEDIATELY",
                      file=sys.stderr)
                if not vr["count_ok"]:
                    print("  count:  declared {0}, actual {1}".format(
                        parsed["declared_count"], vr["actual_count"]),
                        file=sys.stderr)
                if not vr["crc_ok"]:
                    print("  CRC32:  declared {0}, actual {1}".format(
                        parsed["declared_crc"], vr["actual_crc"]),
                        file=sys.stderr)
                return 1

        output = decode(data, width=args.width,
                        skip_null=not args.keep_null)
        _write_stdout(output)
        return 0

    # ── verify ────────────────────────────────────────────────────────────────
    total, valid, invalid, frame_result = verify(data, width=args.width)

    print("Total tokens : {0}".format(total))
    print("Valid tokens : {0}".format(valid))
    print("Invalid      : {0}".format(len(invalid)))
    if invalid:
        print("Bad tokens   : {0}".format(invalid[:10]))
        if len(invalid) > 10:
            print("               ... and {0} more".format(len(invalid) - 10))

    if frame_result is not None:
        print("")
        print("Frame verification:")
        print("  Count  : declared {0}, actual {1} — {2}".format(
            parsed["declared_count"],
            frame_result["actual_count"],
            "OK" if frame_result["count_ok"] else "FAIL"))
        print("  CRC32  : declared {0}, actual {1} — {2}".format(
            parsed["declared_crc"],
            frame_result["actual_crc"],
            "OK" if frame_result["crc_ok"] else "FAIL"))
        if parsed["destroy_flag"]:
            print("  DESTROY flag: present")

        if not (frame_result["count_ok"] and frame_result["crc_ok"]):
            return 1

    if invalid:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
