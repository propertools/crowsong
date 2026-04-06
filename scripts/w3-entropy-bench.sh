#!/usr/bin/env bash
# =============================================================================
# scripts/w3-entropy-bench.sh — WIDTH/3 BINARY entropy benchmark
#
# Runs the WIDTH/3 BINARY + CCL3 pipeline across input files, measuring
# Shannon entropy before and after CCL for each compressor (bzip2, zlib, raw).
#
# Usage:
#   bash scripts/w3-entropy-bench.sh --verse-file <path> [OPTIONS] <file>...
#
# Options:
#   --verse-file FILE   Key verses file for prime_twist (required)
#   --schedule SCHED    CCL schedule: mod3 (default) or standard
#   --outfile PATH      Write markdown results table to this file
#   --avalanche         Run avalanche test on docs/barking_floyd.png
#   --quiet             Suppress per-file progress output
#   -h / --help         Show usage
#
# Examples:
#   # Run on all UDHR PDFs
#   bash scripts/w3-entropy-bench.sh --verse-file verses.txt docs/udhr/**/*.pdf
#
#   # Run on specific files with both schedules
#   bash scripts/w3-entropy-bench.sh --verse-file v.txt docs/udhr/Latin/eng_English.pdf
#   bash scripts/w3-entropy-bench.sh --verse-file v.txt --schedule standard docs/udhr/Latin/eng_English.pdf
#
#   # Include avalanche test
#   bash scripts/w3-entropy-bench.sh --verse-file v.txt --avalanche docs/udhr/Latin/eng_English.pdf
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Tool paths ───────────────────────────────────────────────────────────────

UCS_DEC="$REPO_ROOT/tools/ucs-dec/ucs_dec_tool.py"
PRIME_TWIST="$REPO_ROOT/tools/mnemonic/prime_twist.py"
ADVISOR="$REPO_ROOT/tools/mnemonic/crowsong-advisor.py"
BARKING_FLOYD="$REPO_ROOT/docs/barking_floyd.png"

# ── Defaults ─────────────────────────────────────────────────────────────────

VERSE_FILE=""
SCHEDULE="mod3"
OUTFILE=""
DO_AVALANCHE=0
QUIET=0
FILES=()

# ── Python ───────────────────────────────────────────────────────────────────

if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "Error: python not found in PATH" >&2
    exit 1
fi

# ── Argument parsing ─────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verse-file)  VERSE_FILE="$2"; shift ;;
        --schedule)    SCHEDULE="$2"; shift ;;
        --outfile)     OUTFILE="$2"; shift ;;
        --avalanche)   DO_AVALANCHE=1 ;;
        --quiet)       QUIET=1 ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# ====/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            FILES+=("$1")
            ;;
    esac
    shift
done

if [[ -z "$VERSE_FILE" ]]; then
    echo "Error: --verse-file is required" >&2
    echo "Usage: bash $0 --verse-file <path> [OPTIONS] <file>..." >&2
    exit 1
fi

if [[ ! -f "$VERSE_FILE" ]]; then
    echo "Error: verse file not found: $VERSE_FILE" >&2
    exit 1
fi

if [[ ${#FILES[@]} -eq 0 && $DO_AVALANCHE -eq 0 ]]; then
    echo "Error: no input files specified" >&2
    echo "Usage: bash $0 --verse-file <path> [OPTIONS] <file>..." >&2
    exit 1
fi

# ── Pre-flight ───────────────────────────────────────────────────────────────

for tool in "$UCS_DEC" "$PRIME_TWIST" "$ADVISOR"; do
    if [[ ! -f "$tool" ]]; then
        echo "Error: tool not found: $tool" >&2
        exit 1
    fi
done

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

log() {
    if [[ $QUIET -eq 0 ]]; then
        echo "$@" >&2
    fi
}

# ── Helpers ──────────────────────────────────────────────────────────────────

compress_file() {
    local infile="$1" compressor="$2" outfile="$3"
    case "$compressor" in
        bzip2) bzip2 -9 -k -c "$infile" > "$outfile" ;;
        zlib)  $PYTHON -c "
import sys, zlib
data = open(sys.argv[1], 'rb').read()
sys.stdout.buffer.write(zlib.compress(data, 9))
" "$infile" > "$outfile" ;;
        raw)   cp "$infile" "$outfile" ;;
        *)     echo "Unknown compressor: $compressor" >&2; return 1 ;;
    esac
}

get_entropy() {
    # Extract Shannon entropy from advisor JSON output
    local w3_file="$1"
    $PYTHON "$ADVISOR" --analyse --width 3 --json < "$w3_file" 2>/dev/null \
        | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['H'])" 2>/dev/null \
        || echo "ERR"
}

get_tokens() {
    local w3_file="$1"
    $PYTHON "$ADVISOR" --analyse --width 3 --json < "$w3_file" 2>/dev/null \
        | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['n'])" 2>/dev/null \
        || echo "ERR"
}

get_unique() {
    local w3_file="$1"
    $PYTHON "$ADVISOR" --analyse --width 3 --json < "$w3_file" 2>/dev/null \
        | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(d['unique'])" 2>/dev/null \
        || echo "ERR"
}

# Extract all needed fields in one advisor call
analyse() {
    local w3_file="$1"
    $PYTHON "$ADVISOR" --analyse --width 3 --json < "$w3_file" 2>/dev/null
}

# ── Run one file through the pipeline ────────────────────────────────────────

COMPRESSORS=(bzip2 zlib raw)

# Header for results table
HEADER="| File | Compressor | Schedule | H_pre | H_post | delta_H | Tokens | Unique_pre | Unique_post |"
SEPARATOR="|------|------------|----------|-------|--------|---------|--------|------------|-------------|"

RESULTS=()

run_pipeline() {
    local infile="$1" compressor="$2" schedule="$3"
    local basename
    basename="$(basename "$infile")"

    local compressed="$TMPDIR/payload.compressed"
    local w3_pre="$TMPDIR/payload.w3"
    local ccl_out="$TMPDIR/payload.ccl"
    local roundtrip="$TMPDIR/payload.roundtrip"

    # Compress
    if ! compress_file "$infile" "$compressor" "$compressed"; then
        log "  FAIL: compression ($compressor) failed for $basename"
        return 1
    fi

    # Encode as WIDTH/3 BINARY (COL/0: no padding, so bare roundtrip
    # through CCL preserves null bytes without needing a BYTES trailer)
    if ! $PYTHON "$UCS_DEC" -e --binary --cols 0 < "$compressed" > "$w3_pre"; then
        log "  FAIL: WIDTH/3 encode failed for $basename"
        return 1
    fi

    # Measure pre-CCL
    local pre_json
    pre_json=$(analyse "$w3_pre")
    local h_pre unique_pre tokens
    h_pre=$(echo "$pre_json" | $PYTHON -c "import sys,json; print('{:.6f}'.format(json.load(sys.stdin)['H']))" 2>/dev/null || echo "ERR")
    unique_pre=$(echo "$pre_json" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['unique'])" 2>/dev/null || echo "ERR")
    tokens=$(echo "$pre_json" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['n'])" 2>/dev/null || echo "ERR")

    # Apply CCL
    local ccl_err="$TMPDIR/ccl_err.txt"
    if ! $PYTHON "$PRIME_TWIST" stack \
            --verse-file "$VERSE_FILE" --schedule "$schedule" --width 3 \
            < "$w3_pre" > "$ccl_out" 2>"$ccl_err"; then
        log "  FAIL: CCL stack failed for $basename ($compressor, $schedule)"
        log "  $(cat "$ccl_err")"
        return 1
    fi

    # Extract the CCL payload for entropy measurement
    # unstack gives us the bare token stream back; we need the stacked
    # payload's entropy, so measure the ccl_out directly.
    # But ccl_out is a stack file with headers — extract payload tokens.
    # The advisor can handle this if we pass the right width.
    local h_post unique_post
    local post_json
    post_json=$($PYTHON "$ADVISOR" --analyse --width 3 --json < "$ccl_out" 2>/dev/null || echo "{}")
    h_post=$(echo "$post_json" | $PYTHON -c "import sys,json; print('{:.6f}'.format(json.load(sys.stdin)['H']))" 2>/dev/null || echo "ERR")
    unique_post=$(echo "$post_json" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['unique'])" 2>/dev/null || echo "ERR")

    # Delta
    local delta_h
    if [[ "$h_pre" != "ERR" && "$h_post" != "ERR" ]]; then
        delta_h=$($PYTHON -c "print('{:.6f}'.format($h_post - $h_pre))")
    else
        delta_h="ERR"
    fi

    # Roundtrip verify
    local rt_status="PASS"
    if $PYTHON "$PRIME_TWIST" unstack "$ccl_out" 2>/dev/null \
            | $PYTHON "$UCS_DEC" -d --binary --keep-null > "$roundtrip" 2>/dev/null; then
        if ! diff -q "$compressed" "$roundtrip" >/dev/null 2>&1; then
            rt_status="FAIL"
            log "  WARN: roundtrip mismatch for $basename ($compressor, $schedule)"
        fi
    else
        rt_status="FAIL"
        log "  WARN: roundtrip pipeline failed for $basename ($compressor, $schedule)"
    fi

    local row="| $basename | $compressor | $schedule | $h_pre | $h_post | $delta_h | $tokens | $unique_pre | $unique_post |"
    RESULTS+=("$row")

    log "  $basename  $compressor  $schedule  H=$h_pre→$h_post  rt=$rt_status"
}

# ── Main loop ────────────────────────────────────────────────────────────────

log ""
log "WIDTH/3 BINARY Entropy Benchmark"
log "  Schedule:   $SCHEDULE"
log "  Verse file: $VERSE_FILE"
log "  Files:      ${#FILES[@]}"
log ""

for f in "${FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        log "  SKIP: file not found: $f"
        continue
    fi
    log "── $(basename "$f") ──"
    for comp in "${COMPRESSORS[@]}"; do
        run_pipeline "$f" "$comp" "$SCHEDULE"
    done
    log ""
done

# ── Avalanche test ───────────────────────────────────────────────────────────

AVALANCHE_RESULTS=()

if [[ $DO_AVALANCHE -eq 1 ]]; then
    log "── Avalanche test: $(basename "$BARKING_FLOYD") ──"

    if [[ ! -f "$BARKING_FLOYD" ]]; then
        echo "Error: Barking Floyd not found: $BARKING_FLOYD" >&2
        exit 1
    fi

    # Baseline
    local_compressed="$TMPDIR/avalanche_base.bz2"
    bzip2 -9 -k -c "$BARKING_FLOYD" > "$local_compressed"

    local_w3="$TMPDIR/avalanche_base.w3"
    $PYTHON "$UCS_DEC" -e --binary --cols 0 < "$local_compressed" > "$local_w3"

    local_ccl="$TMPDIR/avalanche_base.ccl"
    $PYTHON "$PRIME_TWIST" stack \
        --verse-file "$VERSE_FILE" --schedule "$SCHEDULE" --width 3 \
        < "$local_w3" > "$local_ccl" 2>/dev/null

    baseline_json=$(analyse "$local_w3")
    baseline_h=$(echo "$baseline_json" | $PYTHON -c "import sys,json; print('{:.6f}'.format(json.load(sys.stdin)['H']))" 2>/dev/null)

    log "  Baseline H_pre: $baseline_h"

    # Flip single bytes at different positions and measure divergence
    filesize=$(wc -c < "$BARKING_FLOYD")
    # Pick 5 positions spread across the file
    positions=()
    for frac in 10 25 50 75 90; do
        pos=$(( filesize * frac / 100 ))
        positions+=("$pos")
    done

    AVALANCHE_HEADER="| Position | Pct | H_pre_flipped | H_delta | Tokens_changed |"
    AVALANCHE_SEP="|----------|-----|---------------|---------|----------------|"
    AVALANCHE_RESULTS+=("$AVALANCHE_HEADER")
    AVALANCHE_RESULTS+=("$AVALANCHE_SEP")

    for pos in "${positions[@]}"; do
        flipped="$TMPDIR/avalanche_flip_${pos}.png"
        # Flip one byte using python
        $PYTHON -c "
import sys
data = bytearray(open(sys.argv[1], 'rb').read())
pos = int(sys.argv[2])
if pos < len(data):
    data[pos] ^= 0xFF
sys.stdout.buffer.write(bytes(data))
" "$BARKING_FLOYD" "$pos" > "$flipped"

        flip_compressed="$TMPDIR/avalanche_flip_${pos}.bz2"
        bzip2 -9 -k -c "$flipped" > "$flip_compressed"

        flip_w3="$TMPDIR/avalanche_flip_${pos}.w3"
        $PYTHON "$UCS_DEC" -e --binary --cols 0 < "$flip_compressed" > "$flip_w3"

        flip_json=$(analyse "$flip_w3")
        flip_h=$(echo "$flip_json" | $PYTHON -c "import sys,json; print('{:.6f}'.format(json.load(sys.stdin)['H']))" 2>/dev/null || echo "ERR")

        # Count differing tokens between baseline and flipped
        tokens_changed=$(diff <(cat "$local_w3") <(cat "$flip_w3") | grep -c "^[<>]" || true)

        pct=$(( pos * 100 / filesize ))
        h_delta="ERR"
        if [[ "$flip_h" != "ERR" ]]; then
            h_delta=$($PYTHON -c "print('{:.6f}'.format($flip_h - $baseline_h))")
        fi

        AVALANCHE_RESULTS+=("| $pos | ${pct}% | $flip_h | $h_delta | $tokens_changed |")
        log "  pos=$pos (${pct}%)  H=$flip_h  delta=$h_delta  changed=$tokens_changed"
    done
    log ""
fi

# ── Output ───────────────────────────────────────────────────────────────────

output_table() {
    echo ""
    echo "## WIDTH/3 BINARY Entropy Analysis"
    echo ""
    echo "Schedule: \`$SCHEDULE\`"
    echo ""
    echo "$HEADER"
    echo "$SEPARATOR"
    for row in "${RESULTS[@]}"; do
        echo "$row"
    done
    echo ""
    echo "Target: H_post >= 8.07 for bzip2.  Ceiling: log2(1000) = 9.97."
    echo "The ceiling is bounded by the input distribution (256 distinct byte values), not the token space."
    echo ""

    if [[ ${#AVALANCHE_RESULTS[@]} -gt 0 ]]; then
        echo "## Avalanche Test: $(basename "$BARKING_FLOYD")"
        echo ""
        echo "Single-byte flip at varying positions, bzip2-9 compressed, WIDTH/3 encoded."
        echo ""
        for row in "${AVALANCHE_RESULTS[@]}"; do
            echo "$row"
        done
        echo ""
    fi
}

# Print to stdout
output_table

# Write to file if requested
if [[ -n "$OUTFILE" ]]; then
    output_table > "$OUTFILE"
    log "Results written to: $OUTFILE"
fi
