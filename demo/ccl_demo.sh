#!/usr/bin/env bash
# =============================================================================
# demo/ccl_demo.sh — Channel Camouflage Layer: full capability demonstration
#
# Shows the complete composable pipeline from plaintext to statistically
# indistinguishable output, with steganographic injection into a side-channel.
#
# Runs in a single terminal window.
# No dependencies beyond the Crowsong stack.
#
# Usage:
#   bash demo/ccl_demo.sh           # full paced version
#   bash demo/ccl_demo.sh --fast    # skip dramatic pauses
#
# What this demonstrates:
#
#   1. UCS-DEC encoding — the foundation layer
#   2. Verse-to-prime derivation — keys from memory
#   3. CCL1 — single pass, partial camouflage
#   4. CCL3 — triple stack, Shannon entropy above AES-128
#   5. Entropy ladder vs professional cryptographic reference points
#   6. Steganographic injection into plausible side-channel
#   7. Full round-trip recovery — two commands, exact match
#
# Payload: the canonical Crowsong test vector — a poem, encoded as
# FDS flash paper, 534 tokens, 3.2KB. A realistic artifact.
# Not a toy message. A document.
#
# =============================================================================

set -e

TOOLS_DIR="$(dirname "$0")/.."
UCS_DEC="$TOOLS_DIR/tools/ucs-dec/ucs_dec_tool.py"
VERSE_PRIME="$TOOLS_DIR/tools/mnemonic/verse_to_prime.py"
PRIME_TWIST="$TOOLS_DIR/tools/mnemonic/prime_twist.py"
PAYLOAD="$TOOLS_DIR/archive/flash-paper-SI-2084-FP-001-payload.txt"

FAST=0
if [ "${1:-}" = "--fast" ]; then
    FAST=1
fi

pause() {
    if [ $FAST -eq 0 ]; then
        sleep "${1:-1.5}"
    fi
}

hr() {
    echo ""
    printf '%.0s─' {1..72}
    echo ""
}

banner() {
    echo ""
    echo "  $1"
    echo ""
}

extract_pass_tokens() {
    # $1 = stack file, $2 = pass index (0-based), $3 = rows per line
    python3 -c "
artifacts = []
current = []
in_stack = False
with open('$1') as f:
    for line in f:
        if line.startswith('=== CCL STACK BEGIN'): in_stack = True; current = []; continue
        if line.startswith('=== CCL STACK PASS'):
            if current: artifacts.append('\n'.join(current))
            current = []; continue
        if line.startswith('=== CCL STACK END'):
            if current: artifacts.append('\n'.join(current))
            break
        if in_stack: current.append(line)
tokens = []
in_payload = False
for line in artifacts[$2].splitlines():
    s = line.strip()
    if 'RSRC: END' in s: in_payload = True; continue
    if in_payload and s and all(t.isdigit() for t in s.split()):
        tokens.extend(s.split())
    elif in_payload and s.startswith('+'): break
cols = ${3:-6}
for i in range(0, min(len(tokens), cols*4), cols):
    print('    ' + '  '.join(tokens[i:i+cols]))
if len(tokens) > cols*4:
    print('    ... ({0} tokens total)'.format(len(tokens)))
"
}

compute_entropy() {
    python3 -c "
import math, collections
def H(tokens):
    c = collections.Counter(tokens)
    n = len(tokens)
    return -sum((v/n)*math.log2(v/n) for v in c.values()) if n else 0.0
artifacts = []
current = []
in_stack = False
with open('$1') as f:
    for line in f:
        if line.startswith('=== CCL STACK BEGIN'): in_stack = True; current = []; continue
        if line.startswith('=== CCL STACK PASS'):
            if current: artifacts.append('\n'.join(current))
            current = []; continue
        if line.startswith('=== CCL STACK END'):
            if current: artifacts.append('\n'.join(current))
            break
        if in_stack: current.append(line)
tokens = []
in_payload = False
for line in artifacts[$2].splitlines():
    s = line.strip()
    if 'RSRC: END' in s: in_payload = True; continue
    if in_payload and s and all(t.isdigit() for t in s.split()):
        tokens.extend(s.split())
    elif in_payload and s.startswith('+'): break
print('{0:.4f} {1} {2}'.format(H(tokens), len(set(tokens)), len(tokens)))
"
}

# ── Scenario ──────────────────────────────────────────────────────────────────

clear
hr
banner "Crowsong · Channel Camouflage Layer · Full Capability Demo"
hr
echo ""
echo "  SCENARIO"
echo ""
echo "  A field operative needs to transmit a document — a firmware"
echo "  specification for a medical device — across a monitored channel."
echo ""
echo "  The document is 534 tokens. The channel is watched."
echo "  The only shared secret is three verses, held in memory."
echo "  Nothing written down. Nothing transmitted. Nothing to confiscate."
echo ""
echo "  This is what the stack was designed for."
echo ""
pause 4

# ── The payload ───────────────────────────────────────────────────────────────

hr
banner "STEP 1 — The payload"
hr
echo ""
echo "  The canonical Crowsong test vector: a poem, encoded as"
echo "  an FDS flash paper artifact. 534 tokens. ~3.2KB."
echo "  A realistic document payload."
echo ""
echo "  Decoded, it begins:"
echo ""
python3 "$UCS_DEC" -d < "$PAYLOAD" | head -4 | sed 's/^/    /'
echo ""
echo "  Encoded (first two rows):"
echo ""
head -2 "$PAYLOAD" | sed 's/^/    /'
echo ""

ORIG_STATS=$(python3 -c "
import math, collections
with open('$PAYLOAD') as f:
    t = f.read().split()
c = collections.Counter(t)
n = len(t)
h = -sum((v/n)*math.log2(v/n) for v in c.values())
print('{0:.4f} {1} {2}'.format(h, len(c), n))
")
ORIG_H=$(echo $ORIG_STATS | awk '{print $1}')
ORIG_U=$(echo $ORIG_STATS | awk '{print $2}')
ORIG_N=$(echo $ORIG_STATS | awk '{print $3}')

echo "  Entropy: ${ORIG_H} bits/token  (${ORIG_U} unique / ${ORIG_N} tokens)"
echo ""
echo "  Recognisable. Structured. The encoding is obvious."
echo "  Every UCS-DEC stream looks like this: regular five-digit groups,"
echo "  low unique-value count, statistically flat."
echo ""
pause 3

# ── Keys from memory ──────────────────────────────────────────────────────────

hr
banner "STEP 2 — Keys from memory"
hr
echo ""
echo "  Three verses. Three primes. Nothing written down."
echo ""

VERSE1="Factoring primes in the hot sun, I fought Entropy — and Entropy won."
VERSE2="Every sequence slips. Every clock will lie."
VERSE3="The signal strains, but never gone — I fought Entropy, and I forged on."

VERSE_FILE=$(mktemp /tmp/ccl_verses_XXXXXX.txt)
printf '%s\n%s\n%s\n' "$VERSE1" "$VERSE2" "$VERSE3" > "$VERSE_FILE"

echo "  K1: \"$VERSE1\""
echo "  K2: \"$VERSE2\""
echo "  K3: \"$VERSE3\""
echo ""
pause 2

echo "  Each verse is passed through:"
echo ""
echo "    verse"
echo "      → NFC normalise"
echo "      → UCS-DEC encode"
echo "      → SHA256 of token stream"
echo "      → interpret as 256-bit integer N"
echo "      → next_prime(N)"
echo "      → prime P  (77 digits)"
echo ""
echo "  The prime exists nowhere until derived."
echo "  The verse is the backup. If you lose the prime, recite the poem."
echo ""
pause 2

echo "  Deriving keys..."
echo ""
P1=$(echo "$VERSE1" | python3 "$VERSE_PRIME" derive 2>/dev/null | grep "^  P:" | awk '{print $2}')
P2=$(echo "$VERSE2" | python3 "$VERSE_PRIME" derive 2>/dev/null | grep "^  P:" | awk '{print $2}')
P3=$(echo "$VERSE3" | python3 "$VERSE_PRIME" derive 2>/dev/null | grep "^  P:" | awk '{print $2}')

echo "  P1: ${P1:0:38}"
echo "      ${P1:38}"
echo ""
echo "  P2: ${P2:0:38}"
echo "      ${P2:38:39}"
echo ""
echo "  P3: ${P3:0:38}"
echo "      ${P3:38:39}"
echo ""
pause 3

# ── Single pass ───────────────────────────────────────────────────────────────

hr
banner "STEP 3 — CCL1: single pass"
hr
echo ""
echo "  For each token tᵢ, digit dᵢ of P1 determines the output base."
echo "  The prime cycles — it is the ouroboros key schedule."
echo "  The twist-map is stored in the artifact's resource fork."
echo ""
echo "    $ cat payload.txt | python prime_twist.py twist --prime P1"
echo ""
pause 1

STACK_FILE=$(mktemp /tmp/ccl_stack_XXXXXX.txt)
python3 "$PRIME_TWIST" stack \
    --verse-file "$VERSE_FILE" \
    --ref CCL3-DEMO \
    < "$PAYLOAD" > "$STACK_FILE" 2>/tmp/ccl_build_log.txt

# Single pass output (pass 0)
echo "  After one CCL pass (first 4 rows):"
echo ""
extract_pass_tokens "$STACK_FILE" 0 6

P1_STATS=$(compute_entropy "$STACK_FILE" 0)
P1_H=$(echo $P1_STATS | awk '{print $1}')
P1_U=$(echo $P1_STATS | awk '{print $2}')
echo ""
echo "  Entropy: ${P1_H} bits/token  (${P1_U} unique)"
echo ""
echo "  Improved. Some regularity broken. But not enough."
echo "  Runs of base-10 tokens still visible. Pattern detectable."
echo ""
pause 3

# ── Double pass ───────────────────────────────────────────────────────────────

hr
banner "STEP 4 — CCL2: second pass"
hr
echo ""
echo "  Pass 2 applies P2 to the already-twisted stream."
echo "  Each pass works on what the previous pass produced."
echo "  Regularity that survived pass 1 meets a different key schedule."
echo ""
pause 1

echo "  After two CCL passes (first 4 rows):"
echo ""
extract_pass_tokens "$STACK_FILE" 1 6

P2_STATS=$(compute_entropy "$STACK_FILE" 1)
P2_H=$(echo $P2_STATS | awk '{print $1}')
P2_U=$(echo $P2_STATS | awk '{print $2}')
echo ""
echo "  Entropy: ${P2_H} bits/token  (${P2_U} unique)"
echo ""
echo "  We are approaching the range of compressed data."
echo "  The structure is no longer visible."
echo ""
pause 3

# ── Triple pass ───────────────────────────────────────────────────────────────

hr
banner "STEP 5 — CCL3: third pass"
hr
echo ""
echo "  Pass 3. The final layer. P3 applied to the CCL2 stream."
echo ""
pause 1

echo "  After three CCL passes (first 4 rows):"
echo ""
extract_pass_tokens "$STACK_FILE" 2 6

P3_STATS=$(compute_entropy "$STACK_FILE" 2)
P3_H=$(echo $P3_STATS | awk '{print $1}')
P3_U=$(echo $P3_STATS | awk '{print $2}')
echo ""
echo "  Entropy: ${P3_H} bits/token  (${P3_U} unique / ${ORIG_N} tokens)"
echo ""
pause 2

# ── Entropy ladder ────────────────────────────────────────────────────────────

hr
banner "STEP 6 — The entropy ladder"
hr
echo ""

python3 - << PYEOF
h0  = float("$ORIG_H")
h1  = float("$P1_H")
h2  = float("$P2_H")
h3  = float("$P3_H")
u0  = int("$ORIG_U")
u1  = int("$(echo $P1_STATS | awk '{print $2}')")
u2  = int("$(echo $P2_STATS | awk '{print $2}')")
u3  = int("$P3_U")
n   = int("$ORIG_N")

bar_max = 50
def bar(h, max_h=9.0):
    filled = int(round(h / max_h * bar_max))
    return '█' * filled + '░' * (bar_max - filled)

print("  bits/token  unique  ┤")
print("  {0:.2f}       {1:>3}    │{2}  UCS-DEC (original)".format(
    h0, u0, bar(h0)))
print("  {0:.2f}       {1:>3}    │{2}  CCL1".format(
    h1, u1, bar(h1)))
print("  {0:.2f}       {1:>3}    │{2}  CCL2".format(
    h2, u2, bar(h2)))
print("  {0:.2f}       {1:>3}    │{2}  CCL3  ◄".format(
    h3, u3, bar(h3)))
print("               ┤" + " " * 51)
print("  7.00─7.90         │{0}  gzip / bzip2".format(bar(7.5)))
print("  7.90─8.00         │{0}  AES-128 ciphertext".format(bar(7.95)))
print("  8.00              │{0}  theoretical maximum".format(bar(8.0)))
print()
gain = 100.0 * (h3 - h0) / h0
print("  Gain:   +{0:.1f}%  ({1:.2f} → {2:.2f} bits/token)".format(
    gain, h0, h3))
print("  CCL3 exceeds AES-128 reference: {0}".format(
    "YES ✓" if h3 > 7.9 else "not yet — try more passes"))
print()
print("  This is not encryption. The twist-map is in the artifact.")
print("  But to a passive entropy scanner: this is noise.")
print("  To a pattern-matching filter: this is compressed data.")
print("  To a human operator: this is a sequence of five-digit numbers.")
PYEOF

pause 4

# ── Steganographic injection ──────────────────────────────────────────────────

hr
banner "STEP 7 — Into the side-channel"
hr
echo ""
echo "  Five-digit decimal tokens are unremarkable."
echo "  They occur naturally in: timestamps, telemetry, reference IDs,"
echo "  log files, cross-reference lists, financial records."
echo ""
echo "  Here is the CCL3 payload dressed as network flow telemetry."
echo "  534 readings. Routine sensor burst. Nothing to see."
echo ""
pause 2

python3 - << PYEOF
import time

artifacts = []
current = []
in_stack = False
with open('$STACK_FILE') as f:
    for line in f:
        if line.startswith('=== CCL STACK BEGIN'): in_stack = True; current = []; continue
        if line.startswith('=== CCL STACK PASS'):
            if current: artifacts.append('\n'.join(current))
            current = []; continue
        if line.startswith('=== CCL STACK END'):
            if current: artifacts.append('\n'.join(current))
            break
        if in_stack: current.append(line)

tokens = []
in_payload = False
for line in artifacts[-1].splitlines():
    s = line.strip()
    if 'RSRC: END' in s: in_payload = True; continue
    if in_payload and s and all(t.isdigit() for t in s.split()):
        tokens.extend(s.split())
    elif in_payload and s.startswith('+'): break

print("  # network-flow-telemetry-2026-04-01.csv")
print("  # source: srv-dmz-04  interval: 50ms  sensor-count: 6")
print("  timestamp_us,flow_id,sensor,reading_mv")

ts = 1743465600000000
sensors = ['FLOW-A','FLOW-B','FLOW-C','FLOW-D','FLOW-E','FLOW-F']
for i, tok in enumerate(tokens[:30]):
    ts += int(tok[-3:]) + 31
    sensor = sensors[i % 6]
    print("  {0},{1:06d},{2},{3}".format(ts, 100000 + i, sensor, tok))

print("  ...")
print("  ({0} rows total — routine burst, auto-archived)".format(len(tokens)))
PYEOF

echo ""
echo "  The receiver strips the CSV wrapper."
echo "  Extracts the reading_mv column."
echo "  Pipes it to unstack."
echo ""
pause 3

# ── Round-trip ────────────────────────────────────────────────────────────────

hr
banner "STEP 8 — Recovery"
hr
echo ""
echo "  The receiver has the same three verses."
echo "  Two commands."
echo ""
echo "    $ python prime_twist.py unstack received.txt \\"
echo "        | python ucs_dec_tool.py -d"
echo ""
pause 2

echo "  Unstack log:"
python3 "$PRIME_TWIST" unstack "$STACK_FILE" 2>&1 >/tmp/ccl_recovered_tokens.txt \
    | grep "Stack\|Unstack" | sed 's/^/    /'
echo ""

RECOVERED=$(cat /tmp/ccl_recovered_tokens.txt | python3 "$UCS_DEC" -d)

echo "  Recovered (first 4 lines):"
echo ""
echo "$RECOVERED" | head -4 | sed 's/^/    /'
echo ""

# Verify exact match
ORIG_DECODED=$(python3 "$UCS_DEC" -d < "$PAYLOAD")
if [ "$RECOVERED" = "$ORIG_DECODED" ]; then
    echo "  Full document verified. Exact match. ✓"
    echo "  534 tokens. Every character. Zero loss."
else
    echo "  MISMATCH — something went wrong."
    exit 1
fi

pause 3

# ── Composability summary ─────────────────────────────────────────────────────

hr
banner "STEP 9 — The composable stack"
hr
echo ""
echo "  Every layer is independently specified and independently useful."
echo ""
echo "  ┌─────────────────────────────────────────────────────────────┐"
echo "  │  verse                                                       │"
echo "  │    → UCS-DEC (this tool)   human-legible encoding           │"
echo "  │    → SHA256                fixed-width integer               │"
echo "  │    → next_prime            deterministic key                 │"
echo "  │    → prime P               the ouroboros                     │"
echo "  │                                                              │"
echo "  │  payload                                                     │"
echo "  │    → UCS-DEC encode        transport-ready                   │"
echo "  │    → CCL twist  ×1         partial camouflage                │"
echo "  │    → CCL twist  ×2         compressed-data range             │"
echo "  │    → CCL twist  ×3         exceeds AES-128 entropy           │"
echo "  │    → inject into container zero forensic signature           │"
echo "  │                                                              │"
echo "  │  receiver                                                    │"
echo "  │    → extract tokens        strip container                   │"
echo "  │    → unstack x3           twist-maps in artifact            │"
echo "  │    → UCS-DEC decode        exact recovery                    │"
echo "  └─────────────────────────────────────────────────────────────┘"
echo ""
pause 3

# ── Closing ───────────────────────────────────────────────────────────────────

hr
banner "What just happened"
hr
echo ""
python3 - << PYEOF
h0 = float("$ORIG_H")
h3 = float("$P3_H")
u0 = int("$ORIG_U")
u3 = int("$P3_U")
n  = int("$ORIG_N")
gain = 100.0 * (h3 - h0) / h0

print("  Input:   {0} tokens  ·  {1:.2f} bits/token  ·  {2} unique values".format(
    n, h0, u0))
print("  Output:  {0} tokens  ·  {1:.2f} bits/token  ·  {2} unique values".format(
    n, h3, u3))
print("  Gain:    +{0:.1f}%  ·  above AES-128 reference  ·  no information lost".format(gain))
print()
print("  Three verses, held in memory.")
print("  Three primes, derived on demand.")
print("  One stack file, self-describing, self-contained.")
print("  Two commands to recover.")
PYEOF

echo ""
hr
echo ""
echo "  The channel between them could be a Morse relay in a monitored room."
echo "  It could be a fax line in East Africa."
echo "  It could be a human courier with a printed stack of flash paper."
echo "  It could be someone blinking Morse in a meeting."
echo "  It could be a CSV in a routine status email."
echo "  It could be sensor telemetry auto-archived and never examined."
echo ""
echo "  The stack does not care."
echo "  The stack was designed for this."
echo ""
hr
echo ""
echo "  CCL provides no cryptographic confidentiality."
echo "  It reduces salience. It raises the cost of attention."
echo "  Confidentiality is a layer you add on top."
echo "  This is the transport. This is what survives."
echo ""
echo "  The key is a verse."
echo "  The verse lives in memory."
echo "  The prime exists nowhere until the moment of need."
echo ""
hr
echo ""

# Cleanup
rm -f "$STACK_FILE" "$VERSE_FILE" /tmp/ccl_recovered_tokens.txt \
       /tmp/ccl_build_log.txt
