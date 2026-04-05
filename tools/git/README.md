# tools/git/ — git bundle tool for FDS payload packaging

Packages git repositories as self-contained binary bundles for
transmission over any channel the FDS stack supports — fax, Morse,
printed page, photographic microdot, human relay, or TCP/IP.

A git bundle is already content-addressable (commit hashes),
versioned (bundle format v2), and delta-capable (`--since`).
It is Structural Principles 14 and 15 implemented and battle-tested.

---

## The construction

```
git bundle create payload.bundle HEAD
  → binary blob
  → WIDTH/3 BINARY UCS-DEC encode
  → CCL3 (mod3 schedule, optional)
  → FDS-FRAME  TYPE: git-bundle  REF: <id>
  → transmit over any channel
```

Receipt:

```
FDS decode → CCL unstack → binary blob
  → git bundle unbundle → full repository
```

The receiver gets not just the current content but the full history,
all branches, and all commit messages. Provenance is intact.

---

## The recursive case

The Crowsong repository that defines the encoding can be transmitted
using the encoding. A git bundle of the entire Crowsong repo, encoded
as a WIDTH/3 BINARY FDS artifact, fits in a photographic microdot.
The toolchain decodes itself on arrival. Keys reconstruct from memory
and public mathematics.

This is not a hypothetical. It is a concrete capability.

---

## Usage

```bash
python gitbundle.py create   [--since HASH] [--repo DIR] <output.bundle>
python gitbundle.py unbundle <input.bundle> [--into DIR]
python gitbundle.py verify   <input.bundle>
python gitbundle.py ls       <input.bundle>
```

---

## Examples

```bash
# Bundle the current repo
python gitbundle.py create payload.bundle

# Bundle only commits since a known hash (delta transmission)
python gitbundle.py create --since abc123f delta.bundle

# Bundle a specific repo directory
python gitbundle.py create --repo /path/to/repo payload.bundle

# Verify a received bundle before unbundling
python gitbundle.py verify payload.bundle

# List refs and prerequisites without unbundling
python gitbundle.py ls payload.bundle

# Unbundle into a new directory
python gitbundle.py unbundle payload.bundle --into recovered/
```

---

## Full pipeline

```bash
# Sender
python gitbundle.py create payload.bundle
python tools/ucs-dec/ucs_dec_tool.py --encode-binary payload.bundle \
    --frame --ref REPO-001 > payload.txt
# ... transmit payload.txt over any channel ...

# Receiver
python tools/ucs-dec/ucs_dec_tool.py --decode-binary payload.txt \
    > payload.bundle
python gitbundle.py verify payload.bundle
python gitbundle.py unbundle payload.bundle --into recovered/
cd recovered/ && git log --oneline
```

---

## Delta transmission

Over a degraded channel, transmit only what has changed since the
last successful sync:

```bash
# Sender: bundle only new commits
python gitbundle.py create --since <last-known-hash> delta.bundle

# Receiver: apply delta to existing repo
python gitbundle.py unbundle delta.bundle
```

This is Structural Principle 15 (content identity is a hash) applied
at the repository level. The `--since` hash is the coordination
mechanism — no external state required.

---

## Dependency chain

The tool degrades gracefully depending on what is available:

| Backend | How to obtain | Notes |
|---------|--------------|-------|
| system git | package manager | Preferred; almost always present |
| dulwich | `pip install dulwich` | Pure Python, MIT licensed, ~800KB |
| neither | — | Tool fails with a clear message |

The tool detects available backends at startup and reports them
in `--help` output. No configuration required.

`dulwich` is a pure Python implementation of the git object model
and bundle format, suitable for environments where system git is
unavailable. It is an optional dependency — the tool works without it
if system git is present.

---

## FDS resource fork declaration

When packaging a git bundle as an FDS payload, declare in the
RSRC block:

```
RSRC: BEGIN
  TYPE:     git-bundle
  VERSION:  1
  REF:      <artifact reference ID>
  SINCE:    <prerequisite hash, if delta bundle>
  BRANCHES: <comma-separated list of included refs>
RSRC: END
```

The receiver uses `TYPE: git-bundle` to dispatch to this tool
automatically. See `docs/crowsong-mobile-architecture.md` for
the mobile payload dispatch table.

---

## Relationship to Structural Principles

**Principle 14 (every assumption must declare its version):**
The git bundle format is versioned (`# v2 git bundle`). Commit
hashes identify objects unambiguously. The format has a defined
upgrade path.

**Principle 15 (content identity is a hash, not a name):**
Git commit hashes are content-addressable identity. Two repos
with the same HEAD commit hash are identical by definition.
Delta transmission (`--since`) requires only the hash of the
last known state — no external coordination protocol.

---

## Companion tools

| Tool | Purpose |
|------|---------|
| `tools/ucs-dec/ucs_dec_tool.py` | FDS encode / decode / frame / verify |
| `tools/mnemonic/prime_twist.py` | CCL encode / decode (optional camouflage) |
| `tools/mnemonic/mnemonic.py` | Key derivation for CCL |

---

## Compatibility

Python 2.7+ / 3.x.

System git: any version supporting `git bundle` (git 1.6.0+, 2005).
Dulwich: 0.20+ recommended; install with `pip install dulwich`.

---

## Licence

MIT (this tool). Git bundle format is part of the git open source
project. Dulwich is MIT licensed.
