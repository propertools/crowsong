# baseconv.py — arbitrary base conversion

Convert non-negative integers between any base representation from base 2
to base 36.

No dependencies beyond the Python standard library.

---

## Usage

```bash
python baseconv.py <number> <from_base> <to_base>
python baseconv.py -h | --help
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

Invalid input exits with status 1 and writes a diagnostic to stderr:

```bash
python baseconv.py G 16 10
# stderr: Error: invalid digit at offset 0 for base 16: G
# exit:   1
```

Input is case-insensitive. `ff`, `FF`, and `fF` are all valid for base 16.
Output is always uppercase.

## Behavior and constraints

- Supports bases 2 through 36 inclusive
- Accepts non-empty, unsigned integers only
- Input is case-insensitive for alphabetic digits
- Output is always uppercase and contains no base prefixes
- Negative numbers and signed forms (`+123`, `-123`) are rejected
- Surrounding whitespace is rejected — strip before passing if needed
- No floating-point, fractional, or exponent forms are supported

## Supported bases

2–36. Digits above 9 are represented as `A`–`Z`.

## As a library

```python
from baseconv import convert, to_int, from_int

convert("FF", 16, 10)       # "255"
convert("255", 10, 2)       # "11111111"
convert("26716", 10, 36)    # "KM4"

to_int("FF", 16)            # 255  (string -> int)
from_int(255, 16)           # "FF" (int -> string)
```

All three functions raise `ValueError` with an actionable message on
invalid input.

## Connection to the Crowsong stack

`baseconv.py` is a small general-purpose helper for deterministic conversion
between unsigned integer representations in bases 2–36. Within the broader
Crowsong stack, utilities like this can support constructions that serialize
large integers across textual representations, including mnemonic and
base-switching workflows. **This tool itself performs only base conversion.**

See `docs/mnemonic-shamir-sketch.md` for the full Mnemonic Share Wrapping
construction.

## What this does not do

- Does not perform encryption or provide any confidentiality guarantee
- Does not validate or parse RSRC artifacts
- Does not implement the Channel Camouflage Layer (CCL) by itself
- Does not preserve formatting, base prefixes, or signed numeric notation
- Does not accept floating-point, fractional, or exponent notation

## Deterministic verification

Run the canonical test suite on both interpreters before merging:

```bash
python2 test_baseconv.py
python3 test_baseconv.py
```

Expected output: `68 passed, 0 failed` on each. Exit status 0 on success,
1 on any failure.

The suite covers:

- Round-trip conversions across bases 2, 8, 10, 16, and 36
- Zero handling at all bases
- Boundary bases (2 and 36)
- Case-insensitive input / uppercase output
- Return type consistency (`unicode`, not `bytes`) across Py2/Py3
- Invalid base values (0, 1, 37)
- Empty input
- Signed input (`+` and `-` rejected symmetrically)
- Surrounding whitespace (space, tab, newline) rejected
- Invalid digit detection with offset and character in error message
- `main()` exit codes (0 on success or `--help`, 1 on any error)

Canonical spot-check vectors (must hold in both interpreters):

```bash
python baseconv.py FF 16 10         # 255
python baseconv.py 255 10 16        # FF
python baseconv.py 0 10 2           # 0
python baseconv.py KM4 36 10        # 26716
python baseconv.py 26716 10 36      # KM4
python baseconv.py 11111111 2 10    # 255
python baseconv.py 255 10 2         # 11111111
```

Expected outputs should be committed under `archive/` as the suite grows.

## Compatibility

Python 2.7+ / 3.x. No dependencies.

Invoke explicitly with the desired interpreter where reproducibility matters:

```bash
python2 baseconv.py FF 16 10
python3 baseconv.py FF 16 10
```

## License

MIT. See the repository root `LICENSE` and `LICENSES.md`.
