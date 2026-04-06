# FDS/CCL Operator Worked Example

*How to encode, camouflage, reveal, and decode a message by hand.*

**Classification:** TLP:CLEAR
**Version:** 0.1
**Status:** Pre-normative worked example

---

## Before you begin

This document walks through a complete encode → camouflage → reveal →
decode cycle using only:

- A Unicode reference table (or the FDS quick reference card)
- A calculator (for base conversion)
- Pencil and paper
- This document

No software is required at any step. The procedure is deliberate:
every layer of the system must be operable by a human with patience
and appropriate reference material.

**What we will do:**

1. Choose a message and a key verse
2. Encode the message as UCS-DEC (FDS)
3. Derive a prime from the key verse
4. Apply one pass of CCL (Channel Camouflage Layer)
5. Record the twist-map for later reversal
6. Reverse the CCL (reveal)
7. Decode the UCS-DEC back to the original message

**The message:** `Signal survives.`

**The key verse:** `Signal survives.`

*(We are using the same text as both message and key for compactness.
In real use, they would be different.)*

---

## Part 1 — Encode the message as UCS-DEC

UCS-DEC encodes each character as its Unicode code point value,
zero-padded to five decimal digits (WIDTH/5).

### Step 1.1 — Write out each character

Take your message character by character. For each character, find its
Unicode code point in the reference table. Write the decimal value,
zero-padded to five digits.

| Position | Char | Unicode | Decimal | Token   |
|----------|------|---------|---------|---------|
| 0  | `S` | U+0053 |  83 | `00083` |
| 1  | `i` | U+0069 | 105 | `00105` |
| 2  | `g` | U+0067 | 103 | `00103` |
| 3  | `n` | U+006E | 110 | `00110` |
| 4  | `a` | U+0061 |  97 | `00097` |
| 5  | `l` | U+006C | 108 | `00108` |
| 6  | ` ` | U+0020 |  32 | `00032` |
| 7  | `s` | U+0073 | 115 | `00115` |
| 8  | `u` | U+0075 | 117 | `00117` |
| 9  | `r` | U+0072 | 114 | `00114` |
| 10 | `v` | U+0076 | 118 | `00118` |
| 11 | `i` | U+0069 | 105 | `00105` |
| 12 | `v` | U+0076 | 118 | `00118` |
| 13 | `e` | U+0065 | 101 | `00101` |
| 14 | `s` | U+0073 | 115 | `00115` |
| 15 | `.` | U+002E |  46 | `00046` |

### Step 1.2 — Write the token stream

Copy the tokens in order, separated by two spaces:

```
00083  00105  00103  00110  00097  00108  00032  00115
00117  00114  00118  00105  00118  00101  00115  00046
```

This is the **UCS-DEC payload**. It is human-readable. Anyone with a
Unicode table can decode it by reversing the lookup. That is the point.

---

## Part 2 — Derive the prime from the key verse

The key verse drives a deterministic computation that produces a large
prime number. The prime's digits become the key schedule for CCL.

In practice, a human operator does **not** perform this computation by
hand — it requires SHA256, which is not feasible with a calculator.
The operator uses `tools/mnemonic/verse_to_prime.py` on a device, or
receives the prime from a trusted source, or memorises the first
20 digits of the prime and uses a reference table for the rest.

For completeness, the full derivation is recorded here.

### Step 2.1 — NFC normalise the verse

`Signal survives.`

For ASCII text, NFC normalisation makes no changes. For text containing
accented characters or composed Unicode sequences, normalise to NFC
before proceeding. When in doubt, run the verse through a tool.

### Step 2.2 — UCS-DEC encode the verse (same as Part 1)

The verse is encoded identically to the message. The resulting token
stream is the input to SHA256.

Token stream of `Signal survives.`:
```
00083  00105  00103  00110  00097  00108  00032  00115  00117  00114  00118  00105  00118  00101  00115  00046
```

### Step 2.3 — SHA256 of the token stream

Treat the token stream (exactly as written above, with two spaces
between tokens) as a UTF-8 byte string. Compute SHA256.

```
SHA256 = 3447f77b91636c3608a28d7f87e2d27d03e76051482fa7e1b2446615c18f0b10
```

### Step 2.4 — Interpret the digest as an integer N

Read the 64-character hex string as a single base-16 integer:

```
N = 23647422330661397229815956071086967900913423707868686085431695892038403689267
```

(77 decimal digits.)

### Step 2.5 — Find the next prime ≥ N

In this case, N is already prime. The derived prime is:

```
P = 23647422330661397229815956071086967900913423707868686085431695892038403689267
```

Write down the digits of P. These are your **key schedule**:

```
2 3 6 4 7 4 2 2 3 3 0 6 6 1 3 9 7 2 2 9 8 1 5 9 5 6 0 7 1 0 8 6 9 6 7 9 0 0 9 1 3 4 2 3 7 0 7 8 6 8 6 8 6 0 8 5 4 3 1 6 9 5 8 9 2 0 3 8 4 0 3 6 8 9 2 6 7
```

---

## Part 3 — Apply CCL (Channel Camouflage Layer)

CCL re-expresses each token in a different numeric base, determined by
the corresponding digit of the key prime. The key cycles: once you reach
the last digit of P, wrap back to the first.

### The base selection rule (standard schedule)

For each token at position i:

1. Take the key digit: `d = P_digits[i mod 77]`
2. Select the candidate base:
   - If `d = 0` or `d = 1`: candidate base = **10** (no change)
   - Otherwise: candidate base = **d**
3. Check feasibility: can the token value be expressed in `d` digits
   in the candidate base?
   - Feasibility test: `base^5 > token_value`
   - If yes: use the candidate base
   - If no: use base **10** (fallback — token unchanged)
4. Convert the token value to the chosen base, zero-padded to 5 digits
5. Record the base used in the twist-map

### Base powers reference (feasibility check)

| Base | Base^5 | Max representable in 5 digits |
|------|--------|-------------------------------|
| 2 | 32 | 31 |
| 3 | 243 | 242 |
| 4 | 1024 | 1023 |
| 5 | 3125 | 3124 |
| 6 | 7776 | 7775 |
| 7 | 16807 | 16806 |
| 8 | 32768 | 32767 |
| 9 | 59049 | 59048 |

If the token value exceeds the maximum for the scheduled base, the base
falls back to 10.

### Step 3.1 — Work through each token

Process each token in order. Use the key schedule digits from Step 2.5.

| Pos | Key digit | Candidate base | Token value | Feasible? | Base used | Input | Output |
|-----|-----------|---------------|------------|-----------|-----------|-------|--------|
| 0 | 2 | 2 | 83 | No (2^5=32 ≤ 83) | 10 | `00083` | `00083` |
| 1 | 3 | 3 | 105 | Yes (3^5=243 > 105) | 3 | `00105` | `10220` |
| 2 | 6 | 6 | 103 | Yes (6^5=7776 > 103) | 6 | `00103` | `00251` |
| 3 | 4 | 4 | 110 | Yes (4^5=1024 > 110) | 4 | `00110` | `01232` |
| 4 | 7 | 7 | 97 | Yes (7^5=16807 > 97) | 7 | `00097` | `00166` |
| 5 | 4 | 4 | 108 | Yes (4^5=1024 > 108) | 4 | `00108` | `01230` |
| 6 | 2 | 2 | 32 | No (2^5=32 ≤ 32) | 10 | `00032` | `00032` |
| 7 | 2 | 2 | 115 | No (2^5=32 ≤ 115) | 10 | `00115` | `00115` |
| 8 | 3 | 3 | 117 | Yes (3^5=243 > 117) | 3 | `00117` | `11100` |
| 9 | 3 | 3 | 114 | Yes (3^5=243 > 114) | 3 | `00114` | `11020` |
| 10 | 0 | 10 | 118 | — (digit 0 → base 10) | 10 | `00118` | `00118` |
| 11 | 6 | 6 | 105 | Yes (6^5=7776 > 105) | 6 | `00105` | `00253` |
| 12 | 6 | 6 | 118 | Yes (6^5=7776 > 118) | 6 | `00118` | `00314` |
| 13 | 1 | 10 | 101 | — (digit 1 → base 10) | 10 | `00101` | `00101` |
| 14 | 3 | 3 | 115 | Yes (3^5=243 > 115) | 3 | `00115` | `11021` |
| 15 | 9 | 9 | 46 | Yes (9^5=59049 > 46) | 9 | `00046` | `00051` |

### Step 3.2 — How to convert to a non-decimal base

For the conversions above, use the repeated division method.

**Example: convert 105 to base 3**

```
105 ÷ 3 = 35 remainder 0   → least significant digit: 0
 35 ÷ 3 = 11 remainder 2   → next digit: 2
 11 ÷ 3 =  3 remainder 2   → next digit: 2
  3 ÷ 3 =  1 remainder 0   → next digit: 0
  1 ÷ 3 =  0 remainder 1   → most significant digit: 1

Read remainders from bottom to top: 1 0 2 2 0
Zero-pad to 5 digits: 10220 ✓
```

**Example: convert 118 to base 6**

```
118 ÷ 6 = 19 remainder 4   → 4
 19 ÷ 6 =  3 remainder 1   → 1
  3 ÷ 6 =  0 remainder 3   → 3

Read bottom to top: 3 1 4
Zero-pad to 5 digits: 00314 ✓
```

### Step 3.3 — Write the twisted token stream

```
00083  10220  00251  01232  00166  01230  00032  00115
11100  11020  00118  00253  00314  00101  11021  00051
```

### Step 3.4 — Record the twist-map

The twist-map records only the positions where the base changed from 10.
Positions using base 10 (no change) are implicit.

```
TWIST-MAP: 1:3, 2:6, 3:4, 4:7, 5:4, 8:3, 9:3, 11:6, 12:6, 14:3, 15:9
```

Format: `position:base` pairs, separated by commas.

**The twist-map must be transmitted to the receiver alongside the
twisted token stream.** Without it, the message cannot be recovered.
In a CCL artifact, the twist-map travels in the RSRC block.

---

## Part 4 — The camouflaged artifact

The receiver receives the twisted token stream. Without knowing the
key prime or the twist-map, it appears to be a stream of arbitrary
five-digit decimal numbers:

```
00083  10220  00251  01232  00166  01230  00032  00115
11100  11020  00118  00253  00314  00101  11021  00051
```

These values could be sensor readings, cross-references, telemetry,
or financial data. They are valid FDS tokens — five decimal digits each.
A passive observer has no basis to distinguish this from noise.

---

## Part 5 — Reveal (reverse the CCL)

The receiver has:
- The twisted token stream (above)
- The twist-map: `1:3, 2:6, 3:4, 4:7, 5:4, 8:3, 9:3, 11:6, 12:6, 14:3, 15:9`

### Step 5.1 — Build the full base list

For each position 0–15, look up the base in the twist-map. Positions
not listed use base 10.

| Position | Base |
|----------|------|
| 0 | 10 |
| 1 | 3 |
| 2 | 6 |
| 3 | 4 |
| 4 | 7 |
| 5 | 4 |
| 6 | 10 |
| 7 | 10 |
| 8 | 3 |
| 9 | 3 |
| 10 | 10 |
| 11 | 6 |
| 12 | 6 |
| 13 | 10 |
| 14 | 3 |
| 15 | 9 |

### Step 5.2 — Convert each token back to base 10

For positions with base 10, read the token directly.
For other positions, convert from the recorded base to base 10.

**How to convert from a non-decimal base to base 10:**

Multiply each digit by the base raised to its position power,
then sum.

**Example: `10220` from base 3 back to decimal**

```
Position (right to left): 0  1  2  3  4
Digit:                     0  2  2  0  1

Value = (0 × 3⁰) + (2 × 3¹) + (2 × 3²) + (0 × 3³) + (1 × 3⁴)
      = (0 × 1)  + (2 × 3)  + (2 × 9)  + (0 × 27) + (1 × 81)
      = 0 + 6 + 18 + 0 + 81
      = 105 ✓
```

**Example: `00314` from base 6 back to decimal**

```
Position (right to left): 0  1  2  3  4
Digit:                     4  1  3  0  0

Value = (4 × 6⁰) + (1 × 6¹) + (3 × 6²) + (0 × 6³) + (0 × 6⁴)
      = (4 × 1)  + (1 × 6)  + (3 × 36) + 0 + 0
      = 4 + 6 + 108
      = 118 ✓
```

### Step 5.3 — Write the recovered token stream

| Pos | Base | Twisted | Recovered |
|-----|------|---------|-----------|
| 0 | 10 | `00083` | `00083` |
| 1 | 3 | `10220` | `00105` |
| 2 | 6 | `00251` | `00103` |
| 3 | 4 | `01232` | `00110` |
| 4 | 7 | `00166` | `00097` |
| 5 | 4 | `01230` | `00108` |
| 6 | 10 | `00032` | `00032` |
| 7 | 10 | `00115` | `00115` |
| 8 | 3 | `11100` | `00117` |
| 9 | 3 | `11020` | `00114` |
| 10 | 10 | `00118` | `00118` |
| 11 | 6 | `00253` | `00105` |
| 12 | 6 | `00314` | `00118` |
| 13 | 10 | `00101` | `00101` |
| 14 | 3 | `11021` | `00115` |
| 15 | 9 | `00051` | `00046` |

Recovered token stream:

```
00083  00105  00103  00110  00097  00108  00032  00115
00117  00114  00118  00105  00118  00101  00115  00046
```

This matches the original UCS-DEC payload from Part 1. ✓

---

## Part 6 — Decode the UCS-DEC

Look up each token value in the Unicode reference table.
Skip any token equal to the padding value `00000`.

| Token | Decimal | Character |
|-------|---------|-----------|
| `00083` | 83 | `S` |
| `00105` | 105 | `i` |
| `00103` | 103 | `g` |
| `00110` | 110 | `n` |
| `00097` | 97 | `a` |
| `00108` | 108 | `l` |
| `00032` | 32 | ` ` (space) |
| `00115` | 115 | `s` |
| `00117` | 117 | `u` |
| `00114` | 114 | `r` |
| `00118` | 118 | `v` |
| `00105` | 105 | `i` |
| `00118` | 118 | `v` |
| `00101` | 101 | `e` |
| `00115` | 115 | `s` |
| `00046` | 46 | `.` |

Read the characters in order:

```
Signal survives.
```

The message has been recovered exactly. ✓

---

## Summary

```
MESSAGE:        Signal survives.
                    ↓
ENCODE (UCS-DEC):
                00083  00105  00103  00110  00097  00108
                00032  00115  00117  00114  00118  00105
                00118  00101  00115  00046
                    ↓
KEY VERSE →     P = 23647422330661397229815956071...
PRIME P         (77 digits; digits become the key schedule)
                    ↓
CCL (twist):
                00083  10220  00251  01232  00166  01230
                00032  00115  11100  11020  00118  00253
                00314  00101  11021  00051
                    ↓
TWIST-MAP:      1:3, 2:6, 3:4, 4:7, 5:4, 8:3, 9:3,
                11:6, 12:6, 14:3, 15:9
                    ↓
[transmit twisted stream + twist-map]
                    ↓
CCL (untwist):
                00083  00105  00103  00110  00097  00108
                00032  00115  00117  00114  00118  00105
                00118  00101  00115  00046
                    ↓
DECODE (UCS-DEC):
                Signal survives.
```

---

## What this demonstrates

**The encoding** is reversible without software, given a Unicode table
and arithmetic. A human with patience can perform every step.

**The camouflage** is driven by the prime's digits. A different verse
produces a different prime, producing a completely different twisted
stream from the same message. A passive observer cannot distinguish the
twisted stream from arbitrary decimal data.

**The twist-map is the reversal key.** The receiver does not need the
original prime to untwist — only the twist-map. The twist-map is stored
in the artifact's RSRC block and transmitted with the payload. The prime
is needed only to generate the twist-map in the first place.

**The key lives nowhere.** The prime exists only during derivation. The
verse lives in memory. After derivation, the prime may be discarded. To
reverse the CCL, the receiver needs only the twist-map — not the prime,
not the verse.

---

## Reference: base conversion tables

### Powers of small bases

| n | 2^n | 3^n | 4^n | 5^n | 6^n | 7^n | 8^n | 9^n |
|---|-----|-----|-----|-----|-----|-----|-----|-----|
| 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| 2 | 4 | 9 | 16 | 25 | 36 | 49 | 64 | 81 |
| 3 | 8 | 27 | 64 | 125 | 216 | 343 | 512 | 729 |
| 4 | 16 | 81 | 256 | 625 | 1296 | 2401 | 4096 | 6561 |
| 5 | 32 | 243 | 1024 | 3125 | 7776 | 16807 | 32768 | 59049 |

### Feasibility quick reference (WIDTH/5, token values 32–127)

For ASCII text (code points 32–127), bases 3–9 are almost always
feasible. The only exception is base 2 (max value 31), which is always
infeasible for printable ASCII.

Bases 3–9 are all feasible for code points up to:
- Base 3: up to 242
- Base 4: up to 1023
- Base 5: up to 3124
- Base 6: up to 7775
- Base 7: up to 16806
- Base 8: up to 32767
- Base 9: up to 59048

For Unicode text outside the ASCII range, check the token value against
the base^5 ceiling before applying the twist.

---

## Error recovery

**If a token looks wrong during decode:** a transcription error affects
only that token. Write `[?TOKEN]` and continue. The remaining tokens are
unaffected.

**If the twist-map is incomplete:** any position not listed in the
twist-map uses base 10. A missing entry causes a decoding error only
at that position.

**If a base conversion gives a non-integer result:** the token was
transcribed incorrectly. Re-examine the original and retry.

**IF COUNT FAILS: DESTROY IMMEDIATELY.** If the token count in the
artifact trailer does not match the actual token count, the artifact
may be corrupted or tampered with. Do not use.

---

*531 VALUES · CRC32:E8DC9BF3 · SIGNAL SURVIVES*
