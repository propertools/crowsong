#!/usr/bin/env bash
# =============================================================================
# scripts/generate_numbers.sh — generate and verify local mathematical corpus
#
# Generates and verifies:
#   - Named mathematical constant digit files (π, e, φ, √2, √3, ln2, ζ(3))
#   - First 10,000 primes quick-reference table
#   - OEIS sequence mirror (15 curated sequences)
#   - Canonical Crowsong test vector artifacts
#
# This script is composable and idempotent. It can be run standalone,
# without git, on any machine with the Crowsong tools installed.
# It is also the basis for the commit workflow documented in the README.
#
# Usage:
#   bash scripts/generate_numbers.sh [OPTIONS]
#
# Options:
#   --constants-only    Generate and verify constants only
#   --sequences-only    Generate primes and sync OEIS only
#   --artifacts-only    Regenerate canonical test vector only
#   --no-oeis           Skip OEIS sync (useful offline)
#   --no-verify         Skip verification passes
#   --digits N          Digits per constant file (default: 10000)
#   --dir PATH          Output root (default: current directory)
#   --quiet             Suppress progress output
#
# Examples:
#   # Full run from repo root
#   bash scripts/generate_numbers.sh
#
#   # Constants only, 50,000 digits each
#   bash scripts/generate_numbers.sh --constants-only --digits 50000
#
#   # No network (skip OEIS)
#   bash scripts/generate_numbers.sh --no-oeis
#
#   # Output to a custom archive directory
#   bash scripts/generate_numbers.sh --dir /mnt/archive/crowsong
#
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT"
DIGITS=10000
DO_CONSTANTS=1
DO_SEQUENCES=1
DO_ARTIFACTS=1
DO_OEIS=1
DO_VERIFY=1
QUIET=0

# ── Argument parsing ──────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --constants-only) DO_SEQUENCES=0; DO_ARTIFACTS=0 ;;
        --sequences-only) DO_CONSTANTS=0; DO_ARTIFACTS=0 ;;
        --artifacts-only) DO_CONSTANTS=0; DO_SEQUENCES=0 ;;
        --no-oeis)        DO_OEIS=0 ;;
        --no-verify)      DO_VERIFY=0 ;;
        --digits)         DIGITS="$2"; shift ;;
        --dir)            OUTPUT_DIR="$2"; shift ;;
        --quiet)          QUIET=1 ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# ====/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

# ── Tool paths ────────────────────────────────────────────────────────────────

CONSTANTS_PY="$REPO_ROOT/tools/constants/constants.py"
PRIMES_PY="$REPO_ROOT/tools/primes/primes.py"
SEQUENCES_PY="$REPO_ROOT/tools/sequences/sequences.py"
UCS_DEC_PY="$REPO_ROOT/tools/ucs-dec/ucs_dec_tool.py"
TEST_SUITE="$REPO_ROOT/tests/roundtrip/run_tests.sh"
ARCHIVE_DIR="$REPO_ROOT/archive"

CONSTANTS_DIR="$OUTPUT_DIR/docs/constants"
SEQUENCES_DIR="$OUTPUT_DIR/docs/sequences"

# ── Helpers ───────────────────────────────────────────────────────────────────

log() {
    if [[ $QUIET -eq 0 ]]; then
        echo "$@"
    fi
}

log_section() {
    if [[ $QUIET -eq 0 ]]; then
        echo ""
        printf '%.0s─' {1..60}
        echo ""
        echo "  $1"
        printf '%.0s─' {1..60}
        echo ""
    fi
}

check_tool() {
    if [[ ! -f "$1" ]]; then
        echo "Error: tool not found: $1" >&2
        exit 1
    fi
}

require_python() {
    if command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
        echo "python"
    else
        echo "Error: python not found in PATH" >&2
        exit 1
    fi
}

PYTHON=$(require_python)

ERRORS=0
PASSES=0

pass() { PASSES=$((PASSES + 1)); log "  PASS  $1"; }
fail() { ERRORS=$((ERRORS + 1)); echo "  FAIL  $1" >&2; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────

log_section "Pre-flight"
log "  Python:   $PYTHON ($($PYTHON --version 2>&1))"
log "  Repo:     $REPO_ROOT"
log "  Output:   $OUTPUT_DIR"
log "  Digits:   $DIGITS"

check_tool "$CONSTANTS_PY"
check_tool "$PRIMES_PY"
check_tool "$SEQUENCES_PY"
check_tool "$UCS_DEC_PY"

# Check mpmath for constants generation
if [[ $DO_CONSTANTS -eq 1 ]]; then
    if ! $PYTHON -c "import mpmath" 2>/dev/null; then
        echo "Error: mpmath is required for constant generation." >&2
        echo "Install with: pip install mpmath" >&2
        exit 1
    fi
    log "  mpmath:   available"
fi

log "  All tools found."

# ── 1. Named mathematical constants ───────────────────────────────────────────

if [[ $DO_CONSTANTS -eq 1 ]]; then
    log_section "Step 1 — Named mathematical constants ($DIGITS digits each)"

    mkdir -p "$CONSTANTS_DIR"

    CONSTANTS="pi e phi sqrt2 sqrt3 ln2 apery"

    for name in $CONSTANTS; do
        outfile="$CONSTANTS_DIR/${name}-${DIGITS}.txt"
        log "  Generating $name..."
        if $PYTHON "$CONSTANTS_PY" generate "$name" "$DIGITS" "$outfile"; then
            pass "$name → $outfile"
        else
            fail "$name generation failed"
        fi
    done

    if [[ $DO_VERIFY -eq 1 ]]; then
        log ""
        log "  Verifying..."
        for name in $CONSTANTS; do
            outfile="$CONSTANTS_DIR/${name}-${DIGITS}.txt"
            if [[ -f "$outfile" ]]; then
                if $PYTHON "$CONSTANTS_PY" verify "$name" "$outfile" \
                        2>/dev/null | grep -q "PASS"; then
                    pass "$name verified"
                else
                    fail "$name verification failed"
                fi
            fi
        done
    fi
fi

# ── 2. Primes quick-reference table ───────────────────────────────────────────

if [[ $DO_SEQUENCES -eq 1 ]]; then
    log_section "Step 2 — Primes quick-reference table"

    mkdir -p "$SEQUENCES_DIR"
    PRIMES_FILE="$SEQUENCES_DIR/primes-10000.txt"

    log "  Generating first 10,000 primes..."
    if $PYTHON "$PRIMES_PY" first 10000 > "$PRIMES_FILE"; then
        COUNT=$(wc -l < "$PRIMES_FILE")
        pass "primes-10000.txt ($COUNT primes)"
    else
        fail "prime generation failed"
    fi

    # ── 3. OEIS sequences ──────────────────────────────────────────────────────

    log_section "Step 3 — OEIS sequence mirror"

    if [[ $DO_OEIS -eq 1 ]]; then
        log "  Syncing curated OEIS sequences (~2-3 min, 2s between requests)..."
        log ""

        if $PYTHON "$SEQUENCES_PY" \
                --dir "$SEQUENCES_DIR" sync; then
            pass "OEIS sync complete"
        else
            fail "OEIS sync had errors (check output above)"
        fi

        if [[ $DO_VERIFY -eq 1 ]]; then
            log ""
            log "  Verifying cached sequences..."
            if $PYTHON "$SEQUENCES_PY" \
                    --dir "$SEQUENCES_DIR" verify; then
                pass "OEIS sequences verified"
            else
                fail "OEIS verification had errors"
            fi
        fi
    else
        log "  Skipping OEIS sync (--no-oeis)."
        log "  To sync later: python tools/sequences/sequences.py sync --all"
    fi
fi

# ── 4. Canonical test vector artifacts ────────────────────────────────────────

if [[ $DO_ARTIFACTS -eq 1 ]]; then
    log_section "Step 4 — Canonical test vector artifacts"

    SOURCE="$ARCHIVE_DIR/second-law-blues.txt"
    PAYLOAD="$ARCHIVE_DIR/flash-paper-SI-2084-FP-001-payload.txt"
    FRAMED="$ARCHIVE_DIR/flash-paper-SI-2084-FP-001-framed.txt"

    if [[ ! -f "$SOURCE" ]]; then
        echo "Error: source poem not found: $SOURCE" >&2
        echo "This script must be run from within the Crowsong repository." >&2
        exit 1
    fi

    log "  Regenerating payload..."
    if $PYTHON "$UCS_DEC_PY" -e < "$SOURCE" > "$PAYLOAD"; then
        TOKENS=$(wc -w < "$PAYLOAD")
        pass "payload regenerated ($TOKENS tokens)"
    else
        fail "payload generation failed"
    fi

    log "  Regenerating framed artifact..."
    if $PYTHON "$UCS_DEC_PY" -e \
            --frame --ref SI-2084-FP-001 --med FLASH \
            --attribution '桜稲荷' \
            < "$SOURCE" > "$FRAMED"; then
        pass "framed artifact regenerated"
    else
        fail "framed artifact generation failed"
    fi

    if [[ $DO_VERIFY -eq 1 ]]; then
        log ""
        log "  Verifying framed artifact (count + CRC32)..."
        VERIFY_OUT=$($PYTHON "$UCS_DEC_PY" -v < "$FRAMED" 2>&1)
        if echo "$VERIFY_OUT" | grep -q "OK"; then
            CRC=$(echo "$VERIFY_OUT" | grep -o "[A-F0-9]\{8\}" | head -1)
            pass "framed artifact verified (CRC32:${CRC})"
        else
            fail "framed artifact verification failed"
        fi

        log ""
        log "  Running full test suite..."
        if bash "$TEST_SUITE" 2>/dev/null | grep -q "8 passed.*0 failed"; then
            pass "8/8 roundtrip tests passing"
        else
            fail "test suite had failures — run manually: bash tests/roundtrip/run_tests.sh"
        fi
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────

log ""
printf '%.0s─' {1..60}
log ""
log ""
log "  Results: $PASSES passed, $ERRORS failed"
log ""

if [[ $ERRORS -gt 0 ]]; then
    echo "  Some steps failed. Check output above." >&2
    exit 1
fi

log "  All outputs are in:"
[[ $DO_CONSTANTS -eq 1 ]] && log "    $CONSTANTS_DIR/"
[[ $DO_SEQUENCES -eq 1 ]] && log "    $SEQUENCES_DIR/"
[[ $DO_ARTIFACTS -eq 1 ]] && log "    $ARCHIVE_DIR/"
log ""
log "  To commit (from repo root, on release/crowsong-01):"
log ""
log "    git add docs/constants/ docs/sequences/ \\"
log "            archive/flash-paper-SI-2084-FP-001-payload.txt \\"
log "            archive/flash-paper-SI-2084-FP-001-framed.txt"
log "    git commit -m \"chore: generate and commit programmatic outputs\""
log ""
