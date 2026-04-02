#!/usr/bin/env bash
# tests/roundtrip/run_tests.sh
#
# Crowsong FDS roundtrip test suite.
# Verifies conformant FDS implementation against canonical test vector
# SI-2084-FP-001.
#
# Run from repo root:
#   bash tests/roundtrip/run_tests.sh

set -e

TOOL="python tools/ucs-dec/ucs_dec_tool.py"
RAW="archive/second-law-blues.txt"
PAYLOAD="archive/flash-paper-SI-2084-FP-001-payload.txt"
FRAMED="archive/flash-paper-SI-2084-FP-001-framed.txt"

EXPECTED_COUNT=531
EXPECTED_CRC="E8DC9BF3"

PASS=0
FAIL=0

ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "=== Crowsong FDS Roundtrip Test Suite ==="
echo "    Artifact: SI-2084-FP-001"
echo ""

# ── Test 1: Decode payload — non-empty output ─────────────────────────────────
echo "[1] Decode canonical payload"
DECODED=$(${TOOL} --decode < "$PAYLOAD")
if [ -n "$DECODED" ]; then
    ok "decoded output is non-empty ($(echo "$DECODED" | wc -c | tr -d ' ') bytes)"
else
    fail "decoded output is empty"
fi

# ── Test 2: First three values decode to 桜稲荷 ───────────────────────────────
echo "[2] Attribution encoding (first three values → 桜稲荷)"
ATTR=$(head -1 "$PAYLOAD" | awk '{print $1, $2, $3}' | ${TOOL} --decode)
if [ "$ATTR" = "桜稲荷" ]; then
    ok "26716 · 31282 · 33655 → 桜稲荷"
else
    fail "first three values decoded to: $ATTR"
fi

# ── Test 3: Verify token count and validity ───────────────────────────────────
echo "[3] Verify token count and format"
if ${TOOL} --verify < "$PAYLOAD" > /dev/null 2>&1; then
    ok "zero invalid tokens"
else
    fail "invalid tokens found in payload"
fi

# ── Test 4: Roundtrip — re-encode raw text and diff against payload ───────────
echo "[4] Roundtrip encode/diff"
REENCODED=$(${TOOL} --encode < "$RAW")
CANONICAL=$(cat "$PAYLOAD")
if [ "$REENCODED" = "$CANONICAL" ]; then
    ok "re-encoded output matches canonical payload byte-for-byte"
else
    fail "re-encoded output differs from canonical payload"
fi

# ── Test 5: Framed artifact — structural integrity ────────────────────────────
echo "[5] Framed artifact structural integrity"
if grep -q "ENC: UCS" "$FRAMED" && \
   grep -q "VERIFY COUNT BEFORE USE" "$FRAMED" && \
   grep -q "IF COUNT FAILS: DESTROY IMMEDIATELY" "$FRAMED" && \
   grep -q "桜稲荷" "$FRAMED"; then
    ok "framed artifact contains header, trailer, and attribution"
else
    fail "framed artifact missing required fields"
fi

# ── Test 6: Framed artifact — frame-aware verify (count + CRC32) ──────────────
echo "[6] Framed artifact frame verification (count + CRC32)"
VERIFY_OUT=$(${TOOL} -v < "$FRAMED" 2>&1)
COUNT_OK=$(echo "$VERIFY_OUT" | grep -c "Count.*OK" || true)
CRC_OK=$(echo "$VERIFY_OUT"   | grep -c "CRC32.*OK" || true)
if [ "$COUNT_OK" -ge 1 ] && [ "$CRC_OK" -ge 1 ]; then
    ok "declared ${EXPECTED_COUNT} VALUES · CRC32:${EXPECTED_CRC} — verified"
else
    fail "frame verification failed"
    echo "$VERIFY_OUT" | sed 's/^/    /'
fi

# ── Test 7: Framed artifact — decode matches payload decode ───────────────────
echo "[7] Decode framed artifact (frame-aware)"
FRAMED_DECODED=$(${TOOL} --decode < "$FRAMED")
if [ "$FRAMED_DECODED" = "$DECODED" ]; then
    ok "framed artifact decodes identically to bare payload"
else
    fail "framed artifact decode differs from payload decode"
fi

# ── Test 8: Corruption — tampered framed artifact exits non-zero ──────────────
echo "[8] Corruption detection"
CORRUPTED=$(sed 's/26716/99999/' "$FRAMED")
if echo "$CORRUPTED" | ${TOOL} -v > /dev/null 2>&1; then
    fail "corrupted artifact should have failed verification"
else
    ok "corrupted artifact correctly rejected (non-zero exit)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo "${EXPECTED_COUNT} VALUES · CRC32:${EXPECTED_CRC} · VERIFIED"
    echo "Signal survives."
    exit 0
else
    echo "IF COUNT FAILS: DESTROY IMMEDIATELY"
    exit 1
fi
