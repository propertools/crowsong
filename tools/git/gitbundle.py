#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gitbundle.py: git bundle tool for FDS payload packaging

Creates, verifies, and unpacks git bundles for transmission as
FDS TYPE: git-bundle payloads over any channel.

A git bundle is a single self-contained binary file carrying a git
repository or a delta since a known commit. Combined with WIDTH/3
BINARY FDS encoding and CCL, a git repository becomes transmissible
over any channel the FDS stack supports: fax, Morse, printed page,
photographic microdot, human relay.

The Crowsong repository itself is the canonical example: the repo that
defines the encoding can be transmitted using the encoding. The toolchain
decodes itself on arrival. Keys reconstruct from memory and public
mathematics.

Usage:
    python gitbundle.py create   [--since REV] [--repo DIR] <output.bundle>
    python gitbundle.py unbundle <input.bundle> [--into DIR]
    python gitbundle.py verify   <input.bundle>
    python gitbundle.py ls       <input.bundle>

Examples:
    # Bundle the current repo
    python gitbundle.py create payload.bundle

    # Bundle only commits not reachable from a known revision (delta transmission)
    python gitbundle.py create --since abc123 delta.bundle

    # Verify a received bundle
    python gitbundle.py verify payload.bundle

    # List contents without unbundling
    python gitbundle.py ls payload.bundle

    # Unbundle into a directory (git clone; sets an 'origin' remote pointing to
    # the bundle file path -- if the bundle is moved or deleted, git fetch fails)
    python gitbundle.py unbundle payload.bundle --into /tmp/recovered

    # Full pipeline: bundle -> FDS encode -> transmit -> FDS decode -> unbundle
    python gitbundle.py create payload.bundle && \\
        python ucs_dec_tool.py --encode-binary payload.bundle > payload.txt
    # ... transmit payload.txt ...
    python ucs_dec_tool.py --decode-binary payload.txt > payload.bundle && \\
        python gitbundle.py unbundle payload.bundle --into recovered/
    # Note: --into sets an 'origin' remote pointing to the bundle file path.

Dependency chain (graceful degradation):
    system git   (preferred; almost always present)
    dulwich      (pure Python fallback; pip install dulwich, MIT licensed)
    [error]      clear message if neither available

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import binascii
import os
import subprocess
import sys

# ── Backend detection ─────────────────────────────────────────────────────────

def _find_git():
    """Return path to system git, or None."""
    try:
        with open(os.devnull, "wb") as devnull:
            subprocess.check_output(["git", "--version"], stderr=devnull)
        return "git"
    except (subprocess.CalledProcessError, OSError):
        return None

def _find_dulwich():
    """Return True if dulwich bundle support is available, False otherwise."""
    try:
        import dulwich.bundle  # noqa: F401
        return True
    except ImportError:
        return False

# Detected once at startup. Results are frozen for the process lifetime.
# If this module is imported (rather than run as a script), the subprocess
# and import probes still fire at import time.
GIT     = _find_git()
DULWICH = _find_dulwich()

def _require_backend():
    if GIT or DULWICH:
        return
    print(
        "Error: git bundle operations require either:\n"
        "  system git  (install via package manager)\n"
        "  dulwich     (pip install dulwich)\n"
        "Neither is available.",
        file=sys.stderr)
    sys.exit(1)


# ── Backend: system git ───────────────────────────────────────────────────────

def _git_create(output, repo=None, since=None):
    """Create a bundle using system git."""
    cmd = ["git"]
    if repo is not None:
        if not repo:
            raise ValueError("--repo requires a non-empty path")
        cmd += ["-C", repo]
    cmd += ["bundle", "create", os.path.abspath(output)]
    if since is not None:
        if not since:
            raise ValueError("--since requires a non-empty revision")
        # --all ^since: every ref not already reachable from the prerequisite.
        cmd += ["--all", "^{0}".format(since)]
    else:
        cmd.append("--all")
    subprocess.check_call(cmd)


def _git_unbundle(bundle, into=None):
    """Unbundle using system git."""
    bundle = os.path.abspath(bundle)
    if into is not None:
        # git clone handles init, ref setup, and checkout in one step.
        subprocess.check_call(["git", "clone", bundle, into])
    else:
        subprocess.check_call(["git", "bundle", "unbundle", bundle])


def _git_verify(bundle):
    """Verify a bundle using system git."""
    subprocess.check_call(
        ["git", "bundle", "verify", os.path.abspath(bundle)])


def _git_ls(bundle):
    """List bundle contents using system git."""
    subprocess.check_call(
        ["git", "bundle", "list-heads", os.path.abspath(bundle)])


# ── Backend: dulwich ──────────────────────────────────────────────────────────

def _dulwich_create(output, repo=None, since=None):
    """Create a bundle using dulwich (not yet implemented)."""
    raise NotImplementedError(
        "dulwich bundle creation is not yet implemented "
        "(pack-data population required). Install system git."
    )


def _dulwich_verify(bundle):
    """Verify a bundle using dulwich (header parse only; not a full integrity check)."""
    from dulwich.bundle import read_bundle
    with open(bundle, "rb") as f:
        b = read_bundle(f)
    print("Header parsed: {0} reference(s), {1} prerequisite(s)".format(
        len(b.references), len(b.prerequisites)))
    print("Note: pack integrity not verified. Install git for a full verification.")


def _dulwich_ls(bundle):
    """List bundle contents using dulwich."""
    from dulwich.bundle import read_bundle
    with open(bundle, "rb") as f:
        b = read_bundle(f)
    for ref, sha in sorted(b.references.items()):
        ref_str = ref.decode("ascii", errors="replace") if isinstance(ref, bytes) else ref
        if isinstance(sha, bytes):
            # Raw 20-byte binary SHA must be hex-encoded; 40-byte hex is fine as-is.
            sha_str = (binascii.hexlify(sha).decode("ascii")
                       if len(sha) == 20 else sha.decode("ascii", errors="replace"))
        else:
            sha_str = sha
        print("{0}  {1}".format(sha_str, ref_str))


# ── Dispatch ──────────────────────────────────────────────────────────────────

def cmd_create(args):
    _require_backend()
    if GIT:
        _git_create(args.output, repo=args.repo, since=args.since)
    else:
        print(
            "Error: 'create' requires system git.\n"
            "  dulwich does not yet support bundle creation.\n"
            "  Install git via your package manager.",
            file=sys.stderr)
        return 1
    abspath = os.path.abspath(args.output)
    size = os.path.getsize(abspath)
    print("Bundle: {0} ({1:,} bytes)".format(abspath, size),
          file=sys.stderr)
    print("Encode: python ucs_dec_tool.py --encode-binary {0}".format(
        abspath), file=sys.stderr)
    return 0


def cmd_unbundle(args):
    _require_backend()
    if GIT:
        _git_unbundle(args.bundle, into=args.into)
    else:
        print("Error: unbundle requires system git (dulwich fallback "
              "not yet implemented for unbundle)", file=sys.stderr)
        return 1
    return 0


def cmd_verify(args):
    _require_backend()
    if GIT:
        _git_verify(args.bundle)
    else:
        _dulwich_verify(args.bundle)
    return 0


def cmd_ls(args):
    _require_backend()
    if GIT:
        _git_ls(args.bundle)
    else:
        _dulwich_ls(args.bundle)
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        description=(
            "git bundle tool for FDS TYPE:git-bundle payload packaging.\n"
            "Bundles git repositories for transmission over any FDS channel."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Backend detection:\n"
            "  system git: {git}\n"
            "  dulwich:    {dulwich}\n"
            "\n"
            "Install dulwich: pip install dulwich\n"
        ).format(
            git="available" if GIT else "NOT FOUND",
            dulwich="available" if DULWICH else "NOT FOUND"
        )
    )

    sub = p.add_subparsers(dest="command")
    sub.required = True

    # create
    pc = sub.add_parser("create",
        help="create a git bundle from the current or specified repo")
    pc.add_argument("output", help="output bundle file path")
    pc.add_argument("--repo", default=None, metavar="DIR",
        help="repo directory (default: current directory)")
    pc.add_argument("--since", default=None, metavar="REV",
        help="only include commits not reachable from REV (any git revision: hash, branch, tag)")

    # unbundle
    pu = sub.add_parser("unbundle",
        help="unpack a bundle into a git repository")
    pu.add_argument("bundle", help="bundle file to unpack")
    pu.add_argument("--into", default=None, metavar="DIR",
        help="clone bundle into DIR (new directory; full bundles only; "
             "delta bundles must be applied to an existing repo without --into); "
             "without --into, must be run from inside an existing git repository")

    # verify
    pv = sub.add_parser("verify",
        help="verify bundle integrity")
    pv.add_argument("bundle", help="bundle file to verify")

    # ls
    pl = sub.add_parser("ls",
        help="list bundle contents (refs and prerequisites)")
    pl.add_argument("bundle", help="bundle file to inspect")

    return p


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "create":   return cmd_create(args)
        if args.command == "unbundle": return cmd_unbundle(args)
        if args.command == "verify":   return cmd_verify(args)
        if args.command == "ls":       return cmd_ls(args)
    except (subprocess.CalledProcessError, IOError, OSError, ValueError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
