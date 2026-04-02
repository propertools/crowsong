#!/usr/bin/env bash
# Crowsong roundtrip test suite
# Verifies conformant FDS implementation against canonical test vector
# SI-2084-FP-001

set -e

TOOL="./tools/ucs-dec/ucs_dec_tool.py"
RAW="./archive/second-law-blues.txt"
PAYLOAD="./archive/flash-paper-SI-2084-FP-001-payload.txt"
FRAMED="./archive/flash-paper-SI-2084-FP-001-framed.txt"

PASS=0
FAIL=0

check() {
  if [ $? -eq 0 ]; then
    echo "  PASS: $1"
    PASS=$((PASS+1))
  else
    echo "  FAIL: $1"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Crowsong FDS Roundtrip Test Suite ==="
echo "    Artifact: SI-2084-FP-001"
echo ""

# Test 1: Decode payload — non-empty output
echo "[1] Decode canonical payload"
DECODED=$(python3 "$TOOL" --decode < "$PAYLOAD")
[ -n "$DECODED" ]
check "decoded output is non-empty ($(echo "$DECODED" | wc -c) bytes)"

# Test 2: First three values decode to 桜稲荷
echo "[2] Attribution encoding (first three values → 桜稲荷)"
ATTR=$(head -1 "$PAYLOAD" | awk '{print $1, $2, $3}' | python3 "$TOOL" --decode)
[ "$ATTR" = "桜稲荷" ]
check "26716 · 31282 · 33655 → 桜稲荷"

# Test 3: Verify token count and validity
echo "[3] Verify token count and format"
python3 "$TOOL" --verify < "$PAYLOAD" > /dev/null
check "zero invalid tokens"

# Test 4: Roundtrip — re-encode raw text and diff against payload
echo "[4] Roundtrip encode/diff"
REENCODED=$(python3 "$TOOL" --encode < "$RAW")
CANONICAL=$(cat "$PAYLOAD")
[ "$REENCODED" = "$CANONICAL" ]
check "re-encoded output matches canonical payload byte-for-byte"

# Test 5: Framed artifact exists and contains header and trailer markers
echo "[5] Framed artifact integrity"
grep -q "ENC: UCS" "$FRAMED" && \
grep -q "VERIFY COUNT BEFORE USE" "$FRAMED" && \
grep -q "IF COUNT FAILS: DESTROY IMMEDIATELY" "$FRAMED" && \
grep -q "桜稲荷" "$FRAMED"
check "framed artifact contains header, trailer, and attribution"

# Test 6: Decode the framed artifact (strip non-value lines) and compare
echo "[6] Decode framed artifact"
FRAMED_DECODED=$(grep -E "^[0-9]" "$FRAMED" | python3 "$TOOL" --decode)
[ "$FRAMED_DECODED" = "$DECODED" ]
check "framed artifact decodes identically to payload"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""
if [ $FAIL -eq 0 ]; then
  echo "531 VALUES · CRC32:E8DC9BF3"
  echo "Signal survives."
  exit 0
else
  echo "IF COUNT FAILS: DESTROY IMMEDIATELY"
  exit 1
fi
