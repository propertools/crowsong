# ucs_dec_tool.py — Fox Decimal Script encoder/decoder

Reference implementation for `draft-darley-fds-00`.

No dependencies beyond Python 3 standard library.

## Usage

```bash
# Encode
echo "Signal survives." | python3 ucs_dec_tool.py --encode

# Decode
cat encoded.txt | python3 ucs_dec_tool.py --decode

# Verify (exits non-zero if invalid tokens)
cat encoded.txt | python3 ucs_dec_tool.py --verify

# Full roundtrip
echo "Signal." | python3 ucs_dec_tool.py -e | python3 ucs_dec_tool.py -d
```

## Options

| Flag | Description |
|------|-------------|
| `-e`, `--encode` | Encode stdin to FDS format |
| `-d`, `--decode` | Decode FDS to text |
| `-v`, `--verify` | Count and validate tokens |
| `--width N` | Field width (default: 5) |
| `--cols N` | Values per row (default: 6, 0=no wrap) |
| `--keep-null` | Preserve null tokens during decode |

## Canonical test vector

```bash
# Verify against canonical artifact
cat ../../archive/second-law-blues-raw.txt | python3 ucs_dec_tool.py -e | \
  diff - ../../archive/flash-paper-SI-2084-FP-001-payload.txt
# Expected: no output
```

## License

MIT. Do what you like with it.

*Signal carries.*
