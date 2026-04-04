# Crowsong release/crowsong-01 — QA Plan

*Run this on a virgin laptop. Every expected output is stated explicitly.
If you see something different, that is the finding.*

---

## Prerequisites

Fresh clone. Python 3.x. Nothing else required except where noted.

```bash
git clone https://github.com/propertools/crowsong
cd crowsong
git checkout release/crowsong-01
```

Confirm branch:

```bash
git branch --show-current
# Expected: release/crowsong-01
```

---

## Section 1 — Environment

### 1.1 Python version

```bash
python3 --version
```

Expected: Python 3.8 or higher. (2.7 should also work but is not the
primary target.)

### 1.2 Tool inventory

```bash
for f in \
    tools/ucs-dec/ucs_dec_tool.py \
    tools/mnemonic/verse_to_prime.py \
    tools/mnemonic/prime_twist.py \
    tools/quickref/quickref.py \
    tools/primes/primes.py \
    tools/constants/constants.py \
    tools/sequences/sequences.py \
    tools/baseconv/baseconv.py \
    scripts/generate_numbers.sh \
    demo/ccl_demo.sh; do
  [ -f "$f" ] && echo "OK  $f" || echo "MISSING  $f"
done
```

Expected: all OK.

### 1.3 No external dependencies (stdlib-only tools)

```bash
python3 -c "
import unicodedata, hashlib, binascii, argparse, collections, math
print('stdlib OK')
"
```

Expected: `stdlib OK`

### 1.4 mpmath (required for constants generation only)

```bash
python3 -c "import mpmath; print('mpmath', mpmath.__version__)"
```

Expected: `mpmath 1.x.x`

If missing: `pip install mpmath`  — only needed for Section 6.

---

## Section 2 — FDS encoding core

### 2.1 Basic encode

```bash
echo "Signal survives." | python3 tools/ucs-dec/ucs_dec_tool.py --encode
```

Expected (exact):
```
00083  00105  00103  00110  00097  00108
00032  00115  00117  00114  00118  00105
00118  00101  00115  00046  00010
```

### 2.2 Basic decode

```bash
echo "00083 00105 00103 00110 00097 00108 00032 00115 00117 \
      00114 00118 00105 00118 00101 00115 00046 00010" | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode
```

Expected: `Signal survives.`

### 2.3 Decode canonical test vector

```bash
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/ucs-dec/ucs_dec_tool.py --decode | head -4
```

Expected (first 4 lines):
```
桜稲荷
Second Law Blues

(Or, Espresso-Fueled Eigenstates)
```

### 2.4 Canonical payload token count and first tokens

```bash
head -1 archive/flash-paper-SI-2084-FP-001-payload.txt
wc -w archive/flash-paper-SI-2084-FP-001-payload.txt
```

Expected first line: `26716  31282  33655  00010  00083  00101`
Expected token count: `534`

The first three tokens — 26716 · 31282 · 33655 — decode to 桜稲荷 (Sakura
Inari). The encoding carries its own attribution in the first three values.

### 2.5 Verify framed artifact (count + CRC32 + DESTROY semantics)

```bash
python3 tools/ucs-dec/ucs_dec_tool.py -v \
  < archive/flash-paper-SI-2084-FP-001-framed.txt
```

Expected output contains:
```
Count  : declared 531, actual 531 — OK
CRC32  : declared E8DC9BF3, actual E8DC9BF3 — OK
DESTROY flag: present
```

### 2.6 Roundtrip encode/diff

```bash
python3 tools/ucs-dec/ucs_dec_tool.py -e \
  < archive/second-law-blues.txt | \
  diff - archive/flash-paper-SI-2084-FP-001-payload.txt
```

Expected: silence (no output). Any output is a failure.

### 2.7 Full test suite

```bash
bash tests/roundtrip/run_tests.sh
```

Expected final lines:
```
=== Results: 8 passed, 0 failed ===

531 VALUES · CRC32:E8DC9BF3 · VERIFIED
Signal survives.
```

---

## Section 3 — Mnemonic prime derivation

### 3.1 Derive prime from verse K1

```bash
echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
  python3 tools/mnemonic/verse_to_prime.py derive --show-steps 2>&1 | \
  grep "^Prime P"
```

Expected: `Prime P (78 digits):`

### 3.2 Verify prime starts with known digits

```bash
echo "Factoring primes in the hot sun, I fought Entropy — and Entropy won." | \
  python3 tools/mnemonic/verse_to_prime.py derive 2>/dev/null | \
  grep "^  P:"
```

Expected: `  P:        11105665647563463056...`
(First 20 digits must be: `11105665647563463056`)

### 3.3 Verify all three CCL key primes

```bash
for verse in \
  "Factoring primes in the hot sun, I fought Entropy — and Entropy won." \
  "Every sequence slips. Every clock will lie." \
  "The signal strains, but never gone — I fought Entropy, and I forged on."; do
  echo "$verse" | python3 tools/mnemonic/verse_to_prime.py derive 2>/dev/null | \
    grep "^  P:" | cut -c1-30
done
```

Expected first 20 digits of each prime:
```
K1:  11105665647563463056
K2:  40312011128746634215
K3:  30018333790021100698
```

### 3.4 Determinism check

Run the K1 derivation twice and compare:

```bash
V="Factoring primes in the hot sun, I fought Entropy — and Entropy won."
P1=$(echo "$V" | python3 tools/mnemonic/verse_to_prime.py derive 2>/dev/null | grep "^  P:")
P2=$(echo "$V" | python3 tools/mnemonic/verse_to_prime.py derive 2>/dev/null | grep "^  P:")
[ "$P1" = "$P2" ] && echo "PASS: deterministic" || echo "FAIL: non-deterministic"
```

Expected: `PASS: deterministic`

---

## Section 4 — CCL prime-twist

### 4.1 Single pass (standard schedule)

```bash
cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/mnemonic/prime_twist.py twist \
    --prime 11105665647563463056890806407849464863469613397607745515368284248187410958110711 \
    --ref CCL1-QA 2>&1 | grep "Tokens:"
```

Expected: `Tokens: 534, twisted: NNN (NN.N%)  schedule: standard`
(twist count should be ~400, around 75%)

### 4.2 Triple stack via verse file

```bash
cat > /tmp/qa_verses.txt << 'EOF'
Factoring primes in the hot sun, I fought Entropy — and Entropy won.
Every sequence slips. Every clock will lie.
The signal strains, but never gone — I fought Entropy, and I forged on.
EOF

cat archive/flash-paper-SI-2084-FP-001-payload.txt | \
  python3 tools/mnemonic/prime_twist.py stack \
    --verse-file /tmp/qa_verses.txt \
    --ref CCL3-QA \
    > /tmp/qa_stack.txt 2>&1

tail -5 /tmp/qa_stack.txt
```

Expected last line: `=== CCL STACK END · REF/CCL3-QA ===`
Expected stderr to show:
```
Stack depth: 3
  Pass 1/3: 534 tokens, NNN twisted (NN.N%)
  Pass 2/3: 534 tokens, NNN twisted (NN.N%)
  Pass 3/3: 534 tokens, NNN twisted (NN.N%)
```

### 4.3 SCHEDULE field in RSRC block

```bash
grep "SCHEDULE" /tmp/qa_stack.txt | head -3
```

Expected: three lines reading `SCHEDULE:   standard`

### 4.4 Entropy check (CCL3 must exceed AES-128 reference)

```bash
python3 - << 'EOF'
import math, collections

def H(tokens):
    c = collections.Counter(tokens)
    n = len(tokens)
    return -sum((v/n)*math.log2(v/n) for v in c.values()) if n else 0.0

with open('archive/flash-paper-SI-2084-FP-001-payload.txt') as f:
    orig = f.read().split()

# Extract final pass tokens from stack file
artifacts = []
current = []
in_stack = False
with open('/tmp/qa_stack.txt') as f:
    for line in f:
        if line.startswith('=== CCL STACK BEGIN'): in_stack=True; current=[]; continue
        if line.startswith('=== CCL STACK PASS'):
            if current: artifacts.append('\n'.join(current))
            current=[]; continue
        if line.startswith('=== CCL STACK END'):
            if current: artifacts.append('\n'.join(current))
            break
        if in_stack: current.append(line)

final = []
in_payload = False
for line in artifacts[-1].splitlines():
    s = line.strip()
    if 'RSRC: END' in s: in_payload=True; continue
    if in_payload and s and all(t.isdigit() for t in s.split()):
        final.extend(s.split())
    elif in_payload and s.startswith('+'): break

h0 = H(orig)
h3 = H(final)
print("Original:  {:.4f} bits/token  ({} unique)".format(h0, len(set(orig))))
print("CCL3:      {:.4f} bits/token  ({} unique)".format(h3, len(set(final))))
print("AES-128 ref: ~7.90 bits/byte")
print("CCL3 exceeds AES-128: {}".format("PASS" if h3 > 7.9 else "FAIL"))
EOF
```

Expected:
```
Original:  4.7830 bits/token  (53 unique)
CCL3:      8.3714 bits/token  (375 unique)
AES-128 ref: ~7.90 bits/byte
CCL3 exceeds AES-128: PASS
```

### 4.5 Round-trip recovery (exact match)

```bash
python3 tools/mnemonic/prime_twist.py unstack /tmp/qa_stack.txt 2>/dev/null | \
  python3 - << 'EOF'
import sys
recovered = sys.stdin.read().split()
with open('archive/flash-paper-SI-2084-FP-001-payload.txt') as f:
    original = f.read().split()
if recovered == original:
    print("PASS: {0} tokens, exact match".format(len(recovered)))
else:
    print("FAIL: recovered {0} tokens, expected {1}".format(
        len(recovered), len(original)))
    for i,(a,b) in enumerate(zip(recovered,original)):
        if a!=b:
            print("First mismatch at token {0}: got {1}, expected {2}".format(i,a,b))
            break
EOF
```

Expected: `PASS: 534 tokens, exact match`

### 4.6 mod3 schedule — 100% twist rate at WIDTH/3

```bash
python3 -c "
import zlib
with open('archive/second-law-blues.txt','rb') as f:
    data = f.read()
comp = zlib.compress(data, 9)
print(' '.join(str(b).zfill(3) for b in comp[:60]))
" | python3 tools/mnemonic/prime_twist.py twist \
    --prime 11105665647563463056890806407849464863469613397607745515368284248187410958110711 \
    --schedule mod3 \
    --width 3 \
    --ref MOD3-QA 2>&1 | grep "Tokens:"
```

Expected: `Tokens: 60, twisted: 60 (100.0%)  schedule: mod3`
(Exactly 100% twist rate — no feasibility fallback)

---

## Section 5 — Live demo

### 5.1 Full CCL demo (fast mode)

```bash
bash demo/ccl_demo.sh --fast 2>&1 | tail -20
```

Expected last block:
```
  Input:   534 tokens  ·  4.78 bits/token  ·  53 unique values
  Output:  534 tokens  ·  8.37 bits/token  ·  375 unique values
  Gain:    +75.0%  ·  above AES-128 reference  ·  no information lost

  Three verses, held in memory.
  Three primes, derived on demand.
  One stack file, self-describing, self-contained.
  Two commands to recover.
```

Expected final lines include `Signal survives.` or similar closing.

Expected exit code: 0

```bash
echo "Exit: $?"
```

---

## Section 6 — Number generation (requires mpmath + ~5 min)

### 6.1 Constants only, offline

```bash
bash scripts/generate_numbers.sh --constants-only --no-verify 2>&1 | \
  grep -E "PASS|FAIL|Error"
```

Expected: 7 PASS lines (one per constant: pi, e, phi, sqrt2, sqrt3, ln2, apery)
No FAIL lines.

### 6.2 Verify a generated constant

```bash
python3 tools/constants/constants.py verify pi \
  docs/constants/pi-10000.txt 2>&1 | tail -3
```

Expected: contains `PASS` and the SHA256 digest.

### 6.3 Artifacts only (no network, no mpmath)

```bash
bash scripts/generate_numbers.sh --artifacts-only 2>&1 | \
  grep -E "PASS|FAIL|Results"
```

Expected:
```
  PASS  payload regenerated (534 tokens)
  PASS  framed artifact regenerated
  PASS  framed artifact verified (CRC32:E8DC9BF3)
  PASS  8/8 roundtrip tests passing

  Results: 4 passed, 0 failed
```

---

## Section 7 — Unicode quick reference

### 7.1 List blocks and presets

```bash
python3 tools/quickref/quickref.py list | head -10
python3 tools/quickref/quickref.py list | grep "Presets:"
```

Expected: 53 blocks listed, then `Presets: ascii, cjk, crowsong, european, math, emoji, vesper`

### 7.2 ASCII preset (82 lines)

```bash
python3 tools/quickref/quickref.py preset ascii | wc -l
python3 tools/quickref/quickref.py preset ascii | grep "SIGNAL SURVIVES"
```

Expected: `82` lines, and `SIGNAL SURVIVES` present in footer.

### 7.3 Named block

```bash
python3 tools/quickref/quickref.py block Greek | grep "Greek and Coptic"
```

Expected: `  Greek and Coptic (U+0370–U+03FF)  135 assigned`

### 7.4 Emoji range (WIDTH/7 declaration)

```bash
python3 tools/quickref/quickref.py range 0x1F600 0x1F64F --name Emoticons | \
  grep -E "WIDTH/7|Header:"
```

Expected: `WIDTH/7 REQUIRED` and `Header: ENC: UCS · DEC · COL/6 · PAD/0000000 · WIDTH/7`

### 7.5 Crowsong preset (spot check size)

```bash
python3 tools/quickref/quickref.py preset crowsong | wc -l
```

Expected: approximately 3200 lines (±100).

---

## Section 8 — Primes and baseconv

### 8.1 Primality testing

```bash
python3 tools/primes/primes.py is-prime 748517
python3 tools/primes/primes.py is-prime 748518
```

Expected: `true` then `false`

### 8.2 Next prime

```bash
python3 tools/primes/primes.py next-prime 1000000
```

Expected: `1000003`

### 8.3 First N primes

```bash
python3 tools/primes/primes.py first 5
```

Expected:
```
2
3
5
7
11
```

### 8.4 Base conversion

```bash
python3 tools/baseconv/baseconv.py 255 10 16
python3 tools/baseconv/baseconv.py ff 16 10
```

Expected: `ff` then `255`

---

## Section 9 — Structural integrity

### 9.1 Git log (confirm commits on branch)

```bash
git log --oneline -10
```

Expected: at least 10 commits visible, most recent at top.

### 9.2 Draft line length compliance

```bash
awk 'length > 72 {print NR": "length" chars: "$0}' \
  drafts/draft-darley-fds-00.txt | head -5
awk 'length > 72 {print NR": "length" chars: "$0}' \
  drafts/draft-darley-fds-ccl-prime-twist-00.txt | head -5
```

Expected: no output from either command.

### 9.3 CCL draft section count

```bash
grep -c "^[0-9][0-9]*\." drafts/draft-darley-fds-ccl-prime-twist-00.txt
```

Expected: 12 or more top-level sections.

### 9.4 Structural principles count

```bash
grep -c "^## Principle" docs/structural-principles.md
```

Expected: `13`

---

## Section 10 — Known gaps (do not fail QA)

These are tracked open items, not regressions. Note them but do not
count them as failures.

| Item | Status | Tracked in |
|------|--------|-----------|
| WIDTH/3 BINARY mode | Not yet implemented | roadmap fds-01, CCL draft §11.4 |
| Resource fork spec (RSRC: BEGIN/END) | Not yet specified | roadmap fds-01 |
| `tools/package.py` | Not yet built | demo scenario |
| `tools/unpackage.py` | Not yet built | demo scenario |
| OEIS sync (Section 6, --sequences-only) | Requires network | expected |
| WIDTH/3 CCL base schedule | Open question | CCL draft §11.4 |

---

## QA sign-off

Fill in after completing all sections.

```
Date:
Machine:
OS:
Python version:
Git commit (git rev-parse HEAD):

Section 1  Environment:           PASS / FAIL / PARTIAL
Section 2  FDS encoding core:     PASS / FAIL / PARTIAL
Section 3  Mnemonic derivation:   PASS / FAIL / PARTIAL
Section 4  CCL prime-twist:       PASS / FAIL / PARTIAL
Section 5  Live demo:             PASS / FAIL / PARTIAL
Section 6  Number generation:     PASS / FAIL / PARTIAL / SKIPPED
Section 7  Unicode quick ref:     PASS / FAIL / PARTIAL
Section 8  Primes and baseconv:   PASS / FAIL / PARTIAL
Section 9  Structural integrity:  PASS / FAIL / PARTIAL

Findings:


Overall: PASS / FAIL
```

---

*Signal survives.*
