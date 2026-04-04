# baseconv.py — arbitrary base conversion

Convert integers between any base representation from base 2 to base 36.

No dependencies beyond the Python standard library.

---

## Usage

```bash
python baseconv.py <number> <from_base> <to_base>
```

## Examples

```bash
python baseconv.py 255 10 16        # decimal to hex:       FF
python baseconv.py FF 16 10         # hex to decimal:        255
python baseconv.py 11111111 2 10    # binary to decimal:     255
python baseconv.py 255 10 2         # decimal to binary:     11111111
python baseconv.py 255 10 8         # decimal to octal:      377
python baseconv.py 26716 10 36      # decimal to base-36:    KM4
python baseconv.py KM4 36 10        # base-36 to decimal:    26716
```

Input is case-insensitive. `ff`, `FF`, and `fF` are all valid for base 16.
Output is always uppercase.

## Supported bases

2–36. Digits above 9 are represented as `A`–`Z`.

## As a library

```python
from baseconv import convert, to_int, from_int

convert("FF", 16, 10)       # "255"
convert("255", 10, 2)       # "11111111"
convert("26716", 10, 36)    # "KM4"

to_int("FF", 16)            # 255  (string → int)
from_int(255, 16)           # "FF" (int → string)
```

## Connection to the Crowsong stack

UCS-DEC encodes Unicode code points as zero-padded decimal integers.
`baseconv.py` is the general-purpose companion: it handles the conversion
between numeric bases that underpins the Mnemonic Share Wrapping construction
(verse → UCS-DEC → large integer → prime derivation) and the Channel
Camouflage Layer (base-switching transforms driven by a named IV).

See `docs/mnemonic-shamir-sketch.md` for the full construction.

## Compatibility

Python 2.7+ / 3.x. No dependencies.

## License

MIT. See `../../LICENSE` and `../../LICENSES.md`.
