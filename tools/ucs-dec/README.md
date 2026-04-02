# ucs_dec_tool.py — Fox Decimal Script encoder/decoder

Reference implementation for `draft-darley-fds-00`.

No dependencies beyond the Python 2.7 standard library.

---

## Usage

```bash
# Encode
echo "Signal survives." | python3 ucs_dec_tool.py --encode

# Decode
cat encoded.txt | python3 ucs_dec_tool.py --decode

# Verify token shape (exits non-zero if invalid tokens are present)
cat encoded.txt | python3 ucs_dec_tool.py --verify

# Full roundtrip
echo "Signal." | python3 ucs_dec_tool.py -e | python3 ucs_dec_tool.py -d
```

---

## Options

| Flag             | Description                                |
| ---------------- | ------------------------------------------ |
| `-e`, `--encode` | Encode stdin to FDS format                 |
| `-d`, `--decode` | Decode FDS to text                         |
| `-v`, `--verify` | Validate token shape and count tokens      |
| `--width N`      | Field width (default: 5)                   |
| `--cols N`       | Values per row (default: 6, `0` = no wrap) |
| `--keep-null`    | Preserve null tokens during decode         |

---

## Canonical test vector

```bash
# Verify against canonical payload artifact
cat ../../archive/second-law-blues.txt | python3 ucs_dec_tool.py -e | \
  diff - ../../archive/flash-paper-SI-2084-FP-001-payload.txt
# Expected: no output
```

For WIDTH/7 artifacts, pass `--width 7` explicitly.

---

## Notes

- Encoding pads the final row with null values (`00000` by default) when column wrapping is enabled.
- Decoding skips null padding unless `--keep-null` is specified.
- Decoding is intentionally forgiving: malformed tokens are ignored.
- Verification is intentionally stricter: malformed or width-mismatched tokens cause a non-zero exit.

---

## License

MIT. See `../../LICENSE` and `../../LICENSES.md`.

*Signal carries.*
