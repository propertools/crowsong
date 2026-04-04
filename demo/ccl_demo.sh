#!/usr/bin/env bash
# =============================================================================
# demo/ccl_demo.sh — Channel Camouflage Layer demonstration
#
# A minimal end-to-end demo of prime-twist CCL for live presentation.
# Runs in a single terminal window. No dependencies beyond the Crowsong stack.
#
# Usage:
#   bash demo/ccl_demo.sh
#   bash demo/ccl_demo.sh --fast    # skip dramatic pauses
#
# Scenario:
#   Alice wants to send Bob an urgent message over a monitored Morse channel.
#   The message is operationally sensitive. It must not look like a message.
#   Alice and Bob share a verse — nothing written down, nothing transmitted.
#   The verse is the key.
#
# =============================================================================

set -e

TOOLS_DIR="$(dirname "$0")/.."
UCS_DEC="$TOOLS_DIR/tools/ucs-dec/ucs_dec_tool.py"
VERSE_PRIME="$TOOLS_DIR/tools/mnemonic/verse_to_prime.py"
PRIME_TWIST="$TOOLS_DIR/tools/mnemonic/prime_twist.py"

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

# ── The scenario ──────────────────────────────────────────────────────────────

clear
hr
banner "Crowsong · Channel Camouflage Layer · Demo"
hr
echo ""
echo "  SCENARIO"
echo ""
echo "  Alice needs to reach Bob. The only channel is a Morse relay"
echo "  operating under passive monitoring. Alice and Bob share one"
echo "  thing: a verse. Nothing written down. Nothing transmitted."
echo ""
echo "  The verse is the key."
echo ""
pause 3

# ── The message ───────────────────────────────────────────────────────────────

hr
banner "STEP 1 — The message"
hr
echo ""

MSG="HELP WATER PUMP BROKEN SEND PARTS"
echo "  Alice's message:"
echo ""
echo "    $MSG"
echo ""
pause 2

# ── Encode to UCS-DEC ─────────────────────────────────────────────────────────

hr
banner "STEP 2 — Encode to UCS-DEC"
hr
echo ""
echo "  UCS-DEC represents each character as its Unicode code point,"
echo "  zero-padded to five decimal digits."
echo ""
echo "    $ echo \"$MSG\" | python ucs_dec_tool.py -e"
echo ""
pause 1

ENCODED=$(echo "$MSG" | python3 "$UCS_DEC" -e --cols 0)
echo "  Output:"
echo ""
echo "    $ENCODED"
echo ""
echo "  Recognisable. Repetitive. Structured."
echo "  A passive observer sees five-digit groups — regular, ordered."
echo "  This is what the Morse operator taps out."
echo ""
pause 3

# ── Derive the key ────────────────────────────────────────────────────────────

hr
banner "STEP 3 — Derive the key from the shared verse"
hr
echo ""

VERSE="We are all just walking each other home."
echo "  The shared verse (memorised, never written):"
echo ""
echo "    \"$VERSE\""
echo ""
echo "    $ echo \"$VERSE\" | python verse_to_prime.py derive --ref K1"
echo ""
pause 1

echo "  Deriving prime..." >&2
PRIME=$(echo "$VERSE" | python3 "$VERSE_PRIME" derive --ref K1 2>/dev/null \
    | grep "^  P:" | awk '{print $2}')

echo "  Derived prime P (77 digits):"
echo ""
echo "    ${PRIME:0:38}"
echo "    ${PRIME:38}"
echo ""
echo "  The verse and the key are semantically linked."
echo "  They are computationally separated."
echo "  The prime exists nowhere until this moment."
echo ""
pause 3

# ── Apply CCL ─────────────────────────────────────────────────────────────────

hr
banner "STEP 4 — Apply Channel Camouflage Layer"
hr
echo ""
echo "  For each token, a digit of P determines the output base."
echo "  The key schedule cycles — the prime is the ouroboros."
echo ""
echo "    $ cat encoded.txt | python prime_twist.py twist --prime P"
echo ""
pause 1

TWISTED_FILE=$(mktemp /tmp/ccl_demo_XXXXXX.txt)
STATS=$(echo "$ENCODED" \
    | python3 "$PRIME_TWIST" twist --prime "$PRIME" --ref CCL-DEMO 2>&1 \
    | tee "$TWISTED_FILE" \
    | head -1)

# Extract twisted token line from artifact
echo "  Twisted output:"
echo ""
python3 -c "
in_payload = False
tokens = []
with open('$TWISTED_FILE') as f:
    for line in f:
        stripped = line.strip()
        if 'RSRC: END' in stripped:
            in_payload = True
            continue
        if in_payload and stripped and all(t.isdigit() for t in stripped.split()):
            tokens.extend(stripped.split())
        elif in_payload and stripped.startswith('+'):
            break
# Print as rows of 6
for i in range(0, len(tokens), 6):
    print('    ' + '  '.join(tokens[i:i+6]))
"
echo ""
echo "  $STATS"
echo ""
echo "  The token stream is still UCS-DEC. Still decimal. Still fixed width."
echo "  The Morse operator taps the same rhythm."
echo "  The observer sees noise."
echo ""
pause 3

# ── Shannon entropy ────────────────────────────────────────────────────────────

hr
banner "STEP 5 — Shannon entropy"
hr
echo ""

python3 - << PYEOF
import math, collections

def entropy(tokens):
    counts = collections.Counter(tokens)
    total = len(tokens)
    if total == 0: return 0.0
    return -sum((c/total)*math.log2(c/total) for c in counts.values())

orig = "$ENCODED".split()

twisted_tokens = []
in_payload = False
with open('$TWISTED_FILE') as f:
    for line in f:
        stripped = line.strip()
        if 'RSRC: END' in stripped:
            in_payload = True
            continue
        if in_payload and stripped and all(t.isdigit() for t in stripped.split()):
            twisted_tokens.extend(stripped.split())
        elif in_payload and stripped.startswith('+'):
            break

h_orig    = entropy(orig)
h_twisted = entropy(twisted_tokens)
gain      = 100.0 * (h_twisted - h_orig) / h_orig if h_orig > 0 else 0

print("  Original UCS-DEC:   {0:.2f} bits/token  ({1} unique values)".format(
    h_orig, len(set(orig))))
print("  CCL prime-twisted:  {0:.2f} bits/token  ({1} unique values)".format(
    h_twisted, len(set(twisted_tokens))))
print("")
print("  Entropy gain: +{0:.0f}%".format(gain))
print("")
print("  This is consistent with compressed or encrypted data.")
print("  A passive heuristic filter sees nothing worth examining.")
PYEOF

pause 3

# ── Bob receives ──────────────────────────────────────────────────────────────

hr
banner "STEP 6 — Bob receives and decodes"
hr
echo ""
echo "  Bob has the same verse. He derives the same prime."
echo "  The twist-map is in the artifact's resource fork."
echo "  He runs two commands."
echo ""
echo "    $ python prime_twist.py untwist received.txt | python ucs_dec_tool.py -d"
echo ""
pause 1

RECOVERED=$(python3 "$PRIME_TWIST" untwist "$TWISTED_FILE" 2>/dev/null \
    | python3 "$UCS_DEC" -d)

echo "  Recovered:"
echo ""
echo "    $RECOVERED"
echo ""

if [ "$RECOVERED" = "$MSG" ]; then
    echo "  Exact match. ✓"
else
    echo "  MISMATCH — something went wrong."
    exit 1
fi

pause 2

# ── Summary ───────────────────────────────────────────────────────────────────

hr
banner "Summary"
hr
echo ""
echo "  The channel between them could be a Morse relay in a monitored room."
echo "  It could be a fax line in East Africa."
echo "  It could be a human courier with a printed stack of flash paper."
echo "  It could be someone blinking Morse in a meeting."
echo ""
echo "  The stack does not care."
echo "  The stack was designed for this."
echo ""
hr
echo ""
echo "  CCL provides no cryptographic confidentiality."
echo "  It reduces salience. It raises the cost of attention."
echo "  The key is a verse. The verse lives in memory."
echo "  The prime exists nowhere until the moment of need."
echo ""
hr
echo ""

# Cleanup
rm -f "$TWISTED_FILE"
