#!/usr/bin/env bash
# =============================================================================
# crowsong-backup.sh — local git mirror of Crowsong and all public forks
#
# Clones or updates a bare mirror of propertools/crowsong and all reachable
# public forks, organised on disk by owner. Designed to run unattended via
# crontab. Logs to a rotating logfile. Sends a summary to stdout (captured
# by cron and mailed if MAILTO is set).
#
# Usage:
#   bash crowsong-backup.sh [OPTIONS]
#
# Options:
#   --dest DIR        Backup root directory (default: ~/crowsong-backup)
#   --token TOKEN     GitHub personal access token (or set GITHUB_TOKEN env)
#   --upstream REPO   GitHub repo to mirror (default: propertools/crowsong)
#   --no-forks        Skip fork discovery and backup
#   --dry-run         Print what would be done without doing it
#   --log FILE        Log file path (default: DEST/backup.log)
#   --keep-logs N     Number of rotated log files to keep (default: 14)
#   -h / --help       Show this help
#
# Crontab example (daily at 03:17, summary mailed by cron):
#   MAILTO=trey@propertools.be
#   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
#   17 3 * * * /path/to/crowsong-backup.sh --dest /srv/crowsong-backup
#
# Crontab example (silent, log file only):
#   17 3 * * * /path/to/crowsong-backup.sh --dest /srv/crowsong-backup >/dev/null
#
# Authentication:
#   A GitHub personal access token is optional for public repositories but
#   recommended — it raises the API rate limit from 60 to 5000 req/hour.
#   The token requires no scopes for public repos. Grant 'repo' scope only
#   if you also want to mirror private forks you own.
#
#   Set via environment (preferred for crontab):
#     GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
#   Or via flag (visible in process list — use with care):
#     --token ghp_xxxxxxxxxxxxxxxxxxxx
#
# Disk layout after first run:
#   DEST/
#     propertools/
#       crowsong.git/           bare mirror of upstream
#     trey-darley/
#       crowsong.git/           bare mirror of fork
#     cvoid/
#       crowsong.git/           bare mirror of fork
#     ...
#     backup.log                current log
#     backup.log.1              rotated (yesterday)
#     backup.log.2              ...
#     forks.json                cached fork list from last API call
#     LAST_RUN                  timestamp and summary of last run
#
# Recovery:
#   Each .git directory is a complete bare clone. To work with it:
#     git clone DEST/propertools/crowsong.git crowsong
#   Or inspect directly:
#     git --git-dir=DEST/propertools/crowsong.git log --oneline -10
#     git --git-dir=DEST/propertools/crowsong.git branch -a
#
# Dependencies: git, curl, python3 (or python). All standard.
#
# Signal survives.
# =============================================================================
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
UPSTREAM="propertools/crowsong"
DEST="${HOME}/crowsong-backup"
TOKEN="${GITHUB_TOKEN:-}"
DO_FORKS=1
DRY_RUN=0
KEEP_LOGS=14
LOG_FILE=""           # resolved after DEST is known

GITHUB_API="https://api.github.com"
UA="crowsong-backup/1.0 (trey@propertools.be)"

# ── Counters ──────────────────────────────────────────────────────────────────
COUNT_OK=0
COUNT_FAIL=0
COUNT_SKIP=0
FAILED_REPOS=()
START_TIME=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dest)       DEST="$2";       shift ;;
        --token)      TOKEN="$2";      shift ;;
        --upstream)   UPSTREAM="$2";   shift ;;
        --no-forks)   DO_FORKS=0             ;;
        --dry-run)    DRY_RUN=1              ;;
        --log)        LOG_FILE="$2";   shift ;;
        --keep-logs)  KEEP_LOGS="$2";  shift ;;
        -h|--help)
            sed -n '2,/^# ====/p' "$0" | sed 's/^# \{0,1\}//' | head -60
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

# ── Resolve paths ─────────────────────────────────────────────────────────────
# Use pwd-relative expansion rather than realpath for portability
DEST="${DEST/#\~/$HOME}"
LOG_FILE="${LOG_FILE:-${DEST}/backup.log}"
FORKS_CACHE="${DEST}/forks.json"
LAST_RUN_FILE="${DEST}/LAST_RUN"

# ── Python ────────────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "Error: python3 not found in PATH." >&2; exit 1
fi

# ── Logging ───────────────────────────────────────────────────────────────────
_log() {
    local level="$1"; shift
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    local line="[${ts}] [${level}] $*"
    echo "$line"
    if [[ $DRY_RUN -eq 0 ]]; then
        echo "$line" >> "$LOG_FILE"
    fi
}

log()  { _log "INFO " "$@"; }
warn() { _log "WARN " "$@"; }
err()  { _log "ERROR" "$@"; }
ok()   { _log "OK   " "$@"; }

# ── Pre-flight ────────────────────────────────────────────────────────────────
preflight() {
    local missing=()
    command -v git  &>/dev/null || missing+=(git)
    command -v curl &>/dev/null || missing+=(curl)
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Error: missing required tools: ${missing[*]}" >&2
        exit 1
    fi

    if [[ $DRY_RUN -eq 0 ]]; then
        mkdir -p "$DEST"
        touch "$LOG_FILE"
    fi
}

# ── Log rotation ──────────────────────────────────────────────────────────────
rotate_logs() {
    [[ $DRY_RUN -eq 1 ]] && return
    [[ ! -f "$LOG_FILE" ]] && return

    local i
    for (( i=KEEP_LOGS-1; i>=1; i-- )); do
        [[ -f "${LOG_FILE}.${i}" ]] && mv "${LOG_FILE}.${i}" "${LOG_FILE}.$((i+1))"
    done
    if [[ -s "$LOG_FILE" ]]; then
        cp "$LOG_FILE" "${LOG_FILE}.1"
        : > "$LOG_FILE"
    fi
    # Prune beyond KEEP_LOGS
    for (( i=KEEP_LOGS+1; i<=KEEP_LOGS+10; i++ )); do
        [[ -f "${LOG_FILE}.${i}" ]] && rm -f "${LOG_FILE}.${i}"
    done
}

# ── GitHub API ────────────────────────────────────────────────────────────────
gh_api() {
    local endpoint="$1"
    local url="${GITHUB_API}${endpoint}"

    local curl_args=(
        --silent --fail
        --user-agent "$UA"
        -H "Accept: application/vnd.github+json"
    )
    [[ -n "$TOKEN" ]] && curl_args+=(-H "Authorization: token ${TOKEN}")

    curl "${curl_args[@]}" "$url"
}

# Fetch all pages of forks
fetch_forks() {
    local repo="$1"
    local page=1
    local accumulated="[]"

    log "Fetching fork list for ${repo} ..."

    while true; do
        local response
        response="$(gh_api "/repos/${repo}/forks?per_page=100&page=${page}" 2>/dev/null || echo "[]")"

        local count
        count="$($PYTHON -c "
import sys, json
try:
    print(len(json.loads(sys.stdin.read())))
except Exception:
    print(0)
" <<< "$response")"

        [[ "$count" -eq 0 ]] && break

        # Accumulate pages
        accumulated="$($PYTHON -c "
import sys, json
a = json.loads('$( echo "$accumulated" | sed "s/'/\\\\'/" )')
b = json.loads(sys.stdin.read())
a.extend(b)
print(json.dumps(a))
" <<< "$response" 2>/dev/null || echo "$accumulated")"

        log "  Page ${page}: ${count} fork(s)"
        (( page++ ))
        sleep 1   # polite pacing
    done

    echo "$accumulated"
}

# Print "owner name clone_url" lines from fork JSON on stdin
extract_fork_lines() {
    $PYTHON -c "
import sys, json
try:
    forks = json.load(sys.stdin)
    for f in forks:
        owner = (f.get('owner') or {}).get('login', '')
        name  = f.get('name', '')
        url   = f.get('clone_url', '')
        if owner and name and url:
            print('{} {} {}'.format(owner, name, url))
except Exception as e:
    sys.stderr.write('JSON parse error: {}\n'.format(e))
"
}

# ── Git mirror operations ─────────────────────────────────────────────────────
clone_or_update() {
    local owner="$1"
    local name="$2"
    local clone_url="$3"
    local label="${owner}/${name}"
    local repo_dir="${DEST}/${owner}/${name}.git"

    # Inject token into HTTPS URL (never echoed to log)
    local auth_url="$clone_url"
    if [[ -n "$TOKEN" ]]; then
        auth_url="${clone_url/https:\/\//https:\/\/${TOKEN}@}"
    fi

    if [[ $DRY_RUN -eq 1 ]]; then
        log "  [dry-run] would mirror ${label} → ${repo_dir}"
        (( COUNT_SKIP++ )) || true
        return 0
    fi

    mkdir -p "${DEST}/${owner}"

    if [[ -d "$repo_dir" ]]; then
        log "  Updating ${label} ..."
        local git_out
        if git_out="$(git --git-dir="$repo_dir" remote update --prune 2>&1)"; then
            echo "$git_out" >> "$LOG_FILE"
            ok "  Updated ${label}"
            (( COUNT_OK++ )) || true
        else
            echo "$git_out" >> "$LOG_FILE"
            warn "  Update failed: ${label}"
            FAILED_REPOS+=("$label")
            (( COUNT_FAIL++ )) || true
        fi
    else
        log "  Cloning ${label} ..."
        local git_out
        if git_out="$(git clone --mirror "$auth_url" "$repo_dir" 2>&1)"; then
            echo "$git_out" >> "$LOG_FILE"
            ok "  Cloned ${label}"
            (( COUNT_OK++ )) || true
        else
            echo "$git_out" >> "$LOG_FILE"
            warn "  Clone failed: ${label}"
            [[ -d "$repo_dir" ]] && rm -rf "$repo_dir"
            FAILED_REPOS+=("$label")
            (( COUNT_FAIL++ )) || true
        fi
    fi
}

# ── Summary ───────────────────────────────────────────────────────────────────
print_summary() {
    local t_start="$1"
    local t_end
    t_end="$(date +%s)"
    local duration=$(( t_end - t_start ))
    local total=$(( COUNT_OK + COUNT_FAIL + COUNT_SKIP ))
    local finish
    finish="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

    local lines=()
    lines+=("Crowsong backup — ${finish}")
    lines+=("  Started:   ${START_TIME}")
    lines+=("  Duration:  ${duration}s")
    lines+=("  Upstream:  ${UPSTREAM}")
    lines+=("  Dest:      ${DEST}")
    lines+=("  Repos:     ${total} total — ${COUNT_OK} OK, ${COUNT_FAIL} failed, ${COUNT_SKIP} skipped")

    if [[ ${#FAILED_REPOS[@]} -gt 0 ]]; then
        lines+=("  FAILED:")
        for r in "${FAILED_REPOS[@]}"; do
            lines+=("    ✗ ${r}")
        done
    fi

    echo ""
    echo "======================================================"
    for l in "${lines[@]}"; do echo "$l"; done
    echo "======================================================"
    echo ""

    if [[ $DRY_RUN -eq 0 ]]; then
        printf '%s\n' "${lines[@]}" > "$LAST_RUN_FILE"
        echo "" >> "$LAST_RUN_FILE"
        echo "Log: ${LOG_FILE}" >> "$LAST_RUN_FILE"
    fi

    [[ $COUNT_FAIL -eq 0 ]]   # exit 0 on clean, 1 on any failure
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    START_TIME="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    local t_start
    t_start="$(date +%s)"

    preflight
    rotate_logs

    log "======================================================"
    log "Crowsong backup starting"
    log "  Upstream:  ${UPSTREAM}"
    log "  Dest:      ${DEST}"
    log "  Forks:     $( [[ $DO_FORKS -eq 1 ]] && echo yes || echo no )"
    log "  Dry run:   $( [[ $DRY_RUN  -eq 1 ]] && echo yes || echo no )"
    log "  Auth:      $( [[ -n "$TOKEN" ]]      && echo 'token set' || echo 'unauthenticated (60 req/hr limit)' )"
    log "======================================================"

    # 1. Upstream
    log ""
    log "── Upstream ──────────────────────────────────────────"
    local up_owner up_name
    up_owner="$(cut -d'/' -f1 <<< "$UPSTREAM")"
    up_name="$(cut -d'/' -f2 <<< "$UPSTREAM")"
    clone_or_update "$up_owner" "$up_name" "https://github.com/${UPSTREAM}.git" || true

    # 2. Forks
    if [[ $DO_FORKS -eq 1 ]]; then
        log ""
        log "── Forks ─────────────────────────────────────────────"

        local forks_json
        forks_json="$(fetch_forks "$UPSTREAM")"

        if [[ $DRY_RUN -eq 0 ]]; then
            echo "$forks_json" > "$FORKS_CACHE"
            log "Fork list cached: ${FORKS_CACHE}"
        fi

        local fork_count
        fork_count="$($PYTHON -c "
import sys,json
try: print(len(json.loads(sys.stdin.read())))
except: print(0)
" <<< "$forks_json")"

        log "Found ${fork_count} public fork(s)"

        if [[ "$fork_count" -gt 0 ]]; then
            while IFS=' ' read -r owner name url; do
                [[ -z "$owner" ]] && continue
                log ""
                log "── Fork: ${owner}/${name} ──"
                clone_or_update "$owner" "$name" "$url" || true
                sleep 2   # polite pacing between forks
            done < <(echo "$forks_json" | extract_fork_lines)
        fi
    fi

    # 3. Summary and exit code
    log ""
    print_summary "$t_start"
}

main "$@"
