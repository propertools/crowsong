#!/usr/bin/env python3
"""
ucs_dec_tool.py — Fox Decimal Script encoder/decoder

Encodes text as zero-padded decimal Unicode code points.
Decodes zero-padded decimal Unicode code points back to text.

Reference implementation for draft-darley-fds-00.

Designed for degraded-channel transmission survivability:
fax, OCR, manual transcription, Morse.

Format: UCS · DEC · COL/6 · PAD/00000
Informal name: Fox Decimal Script (FDS)

Usage:
    echo "Signal survives." | python3 ucs_dec_tool.py --encode
    cat encoded.txt | python3 ucs_dec_tool.py --decode
    echo "Signal survives." | python3 ucs_dec_tool.py -e | python3 ucs_dec_tool.py -d

Author: Proper Tools SRL
License: MIT
"""

import sys
import argparse


def encode(text, width=5, cols=6):
    """
    Encode text into zero-padded decimal Unicode code points.

    Args:
        text:  Input string (any Unicode)
        width: Zero-padding width per value (default: 5)
        cols:  Values per row (default: 6, set 0 for no wrapping)

    Returns:
        Encoded string — space-separated values, newline-wrapped at cols.
    """
    values = [f"{ord(ch):0{width}d}" for ch in text]

    if cols <= 0:
        return " ".join(values)

    lines = []
    for i in range(0, len(values), cols):
        chunk = values[i:i + cols]
        # Pad final row to full width for visual alignment
        while len(chunk) < cols:
            chunk.append("0" * width)
        lines.append("  ".join(chunk))

    return "\n".join(lines)


def decode(data, skip_null=True):
    """
    Decode zero-padded decimal Unicode code points back to text.

    Args:
        data:       Input string of space/newline-separated decimal values
        skip_null:  If True, skip codepoint 0 (padding) — by design, not accident

    Returns:
        Decoded string.

    Invalid tokens are silently ignored — this is intentional.
    The format is designed to survive transcription errors gracefully.
    """
    tokens = data.split()
    chars = []

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        try:
            codepoint = int(tok)
            if skip_null and codepoint == 0:
                continue  # Skip null padding — by design, not by accident
            chars.append(chr(codepoint))
        except (ValueError, OverflowError):
            continue  # Ignore malformed tokens — degrade gracefully

    return "".join(chars)


def verify(data, width=5):
    """
    Count and validate tokens in encoded data.

    Args:
        data:   Input string of encoded values
        width:  Expected padding width (default: 5)

    Returns:
        Tuple of (total_count, valid_count, invalid_tokens)
    """
    tokens = data.split()
    valid = []
    invalid = []

    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        try:
            val = int(tok)
            if len(tok) == width and val >= 0:
                valid.append(tok)
            else:
                invalid.append(tok)
        except ValueError:
            invalid.append(tok)

    return len(tokens), len(valid), invalid


def main():
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
            "  echo 'Hello' | python3 ucs_dec_tool.py --encode\n"
            "  cat encoded.txt | python3 ucs_dec_tool.py --decode\n"
            "  cat encoded.txt | python3 ucs_dec_tool.py --verify\n"
            "  echo 'Signal.' | python3 ucs_dec_tool.py -e | python3 ucs_dec_tool.py -d\n"
        )
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-e", "--encode",
        action="store_true",
        help="Encode stdin text to FDS format"
    )
    mode.add_argument(
        "-d", "--decode",
        action="store_true",
        help="Decode FDS format to text"
    )
    mode.add_argument(
        "-v", "--verify",
        action="store_true",
        help="Count and validate tokens without decoding"
    )

    parser.add_argument(
        "--width",
        type=int,
        default=5,
        metavar="N",
        help="Zero-padding width per value (default: 5)"
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=6,
        metavar="N",
        help="Values per row when encoding (default: 6, 0 = no wrapping)"
    )
    parser.add_argument(
        "--keep-null",
        action="store_true",
        help="Preserve null (00000) codepoints during decode (default: skip)"
    )

    args = parser.parse_args()
    data = sys.stdin.read()

    if args.encode:
        output = encode(data, width=args.width, cols=args.cols)
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")

    elif args.decode:
        output = decode(data, skip_null=not args.keep_null)
        sys.stdout.write(output)

    elif args.verify:
        total, valid, invalid = verify(data, width=args.width)
        print(f"Total tokens : {total}")
        print(f"Valid tokens : {valid}")
        print(f"Invalid      : {len(invalid)}")
        if invalid:
            print(f"Bad tokens   : {invalid[:10]}")
            if len(invalid) > 10:
                print(f"               ... and {len(invalid) - 10} more")
        if invalid:
            sys.exit(1)


if __name__ == "__main__":
    main()
