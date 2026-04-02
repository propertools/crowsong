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

Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import sys

UNICODE_MAX = 0x10FFFF

PY2 = (sys.version_info[0] == 2)

if PY2:
    text_type = unicode  # noqa: F821
    to_chr = unichr      # noqa: F821
else:
    text_type = str
    to_chr = chr


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


def _parse_int_token(token):
    """Parse a decimal token to int, returning None on failure."""
    try:
        return int(token)
    except ValueError:
        return None


def _is_valid_codepoint(value):
    """Return True if value is a valid Unicode code point."""
    return 0 <= value <= UNICODE_MAX


def encode(text, width=5, cols=6):
    """
    Encode text into zero-padded decimal Unicode code points.

    Args:
        text:  Input string (any Unicode)
        width: Zero-padding width per value (default: 5)
        cols:  Values per row (default: 6, 0 = no wrapping)

    Returns:
        Encoded string — whitespace-separated values, newline-wrapped at cols.
    """
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


def decode(data, skip_null=True):
    """
    Decode zero-padded decimal Unicode code points back to text.

    Args:
        data:      Input string of whitespace-separated decimal values
        skip_null: If True, skip codepoint 0 (padding)

    Returns:
        Decoded Unicode string.

    Invalid tokens are silently ignored by design.
    """
    chars = []

    for token in data.split():
        value = _parse_int_token(token)
        if value is None or not _is_valid_codepoint(value):
            continue
        if skip_null and value == 0:
            continue
        chars.append(to_chr(value))

    return "".join(chars)


def verify(data, width=5):
    """
    Validate token shape and count tokens in encoded data.

    Checks token width and Unicode range only — this validates token shape
    for a given WIDTH, not semantic equivalence to a framed artifact.
    For WIDTH/7 artifacts, pass --width 7 explicitly.

    Args:
        data:  Input string of encoded values
        width: Expected field width (default: 5)

    Returns:
        Tuple of (total_count, valid_count, invalid_tokens)
    """
    tokens = data.split()
    invalid = []

    for token in tokens:
        value = _parse_int_token(token)
        if value is None or len(token) != width or not _is_valid_codepoint(value):
            invalid.append(token)

    total = len(tokens)
    valid = total - len(invalid)
    return total, valid, invalid


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
        )
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("-e", "--encode", action="store_true", help="Encode stdin text to FDS format")
    mode.add_argument("-d", "--decode", action="store_true", help="Decode FDS format to text")
    mode.add_argument(
        "-v", "--verify",
        action="store_true",
        help="Validate token shape and count tokens without decoding"
    )

    parser.add_argument(
        "--width",
        type=_positive_int,
        default=5,
        metavar="N",
        help="Zero-padding width per value (default: 5)"
    )
    parser.add_argument(
        "--cols",
        type=_nonnegative_int,
        default=6,
        metavar="N",
        help="Values per row when encoding (default: 6, 0 = no wrapping)"
    )
    parser.add_argument(
        "--keep-null",
        action="store_true",
        help="Preserve null (00000) codepoints during decode (default: skip)"
    )

    return parser


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()
    data = _read_stdin()

    if args.encode:
        output = encode(data, width=args.width, cols=args.cols)
        _write_stdout(output)
        if not output.endswith("\n"):
            _write_stdout("\n")
        return 0

    if args.decode:
        _write_stdout(decode(data, skip_null=not args.keep_null))
        return 0

    total, valid, invalid = verify(data, width=args.width)
    print("Total tokens : {0}".format(total))
    print("Valid tokens : {0}".format(valid))
    print("Invalid      : {0}".format(len(invalid)))
    if invalid:
        print("Bad tokens   : {0}".format(invalid[:10]))
        if len(invalid) > 10:
            print("               ... and {0} more".format(len(invalid) - 10))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
