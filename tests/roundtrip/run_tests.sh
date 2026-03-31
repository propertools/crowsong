#!/usr/bin/env bash
# Crowsong roundtrip test suite
# Verifies conformant FDS implementation against canonical test vector

set -e

TOOL="../../tools/ucs-dec/ucs_dec_tool.py"
RAW="../../archive/second-law-blues-raw.txt"
ARTIFACT="../../archive/flash-paper-SI-2084-FP-001-payload.txt"

echo "=== Crowsong FDS Roundtrip Tests ==="
echo ""

# Test 1: Decode the canonical artifact
echo "[1/4] Decoding canonical artifact..."
DECODED=$(python3 "$TOOL" --decode < "$ARTIFACT")
if [ -z "$DECODED" ]; then
  echo "FAIL: empty output"
  exit 1
fi
echo "PASS: decoded $(echo "$DECODED" | wc -c) bytes"

# Test 2: Verify value count
echo "[2/4] Verifying value count..."
python3 "$TOOL" --verify < "$ARTIFACT"
echo "PASS"

# Test 3: Re-encode and compare
echo "[3/4] Roundtrip encode/decode..."
REENCODED=$(python3 "$TOOL" --encode < "$RAW")
ARTIFACT_PAYLOAD=$(cat "$ARTIFACT")
if [ "$REENCODED" = "$ARTIFACT_PAYLOAD" ]; then
  echo "PASS: re-encoded output matches canonical artifact byte-for-byte"
else
  echo "FAIL: re-encoded output differs from canonical artifact"
  diff <(echo "$REENCODED") <(echo "$ARTIFACT_PAYLOAD") | head -20
  exit 1
fi

# Test 4: Verify attribution (first three values decode to 桜稲荷)
echo "[4/4] Verifying attribution encoding..."
ATTRIBUTION=$(echo "26716 31282 33655" | python3 "$TOOL" --decode)
if [ "$ATTRIBUTION" = "桜稲荷" ]; then
  echo "PASS: 26716 · 31282 · 33655 → 桜稲荷"
else
  echo "FAIL: attribution mismatch (got: $ATTRIBUTION)"
  exit 1
fi

echo ""
echo "=== All tests passed ==="
echo ""
echo "530 VALUES · VERIFIED"
echo "Signal survives."
