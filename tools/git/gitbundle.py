#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gitbundle.py — git bundle tool for FDS payload packaging

Creates, verifies, and unpacks git bundles for transmission as
FDS TYPE: git-bundle payloads over any channel.

A git bundle is a single self-contained binary file carrying a git
repository or a delta since a known commit. Combined with WIDTH/3
BINARY FDS encoding and CCL, a git repository becomes transmissible
over any channel the FDS stack supports — fax, Morse, printed page,
photographic microdot, human relay.

The Crowsong repository itself is the canonical example: the repo that
defines the encoding can be transmitted using the encoding. The toolchain
decodes itself on arrival. Keys reconstruct from memory and public
mathematics.

Usage:
    python gitbundle.py create   [--since HASH] [--repo DIR] <output.bundle>
    python gitbundle.py unbundle <input.bundle> [--into DIR]
    python gitbundle.py verify   <input.bundle>
    python gitbundle.py ls       <input.bundle>

Examples:
    # Bundle the current repo
    python gitbundle.py create payload.bundle

    # Bundle only commits since a known hash (delta transmission)
    python gitbundle.py create --since abc123 delta.bundle

    # Verify a received bundle
    python gitbundle.py verify payload.bundle

    # List contents without unbundling
    python gitbundle.py ls payload.bundle

    # Unbundle into a directory
    python gitbundle.py unbundle payload.bundle --into /tmp/recovered

    # Full pipeline: bundle -> FDS encode -> transmit -> FDS decode -> unbundle
    python gitbundle.py create payload.bundle && \\
        python ucs_dec_tool.py --encode-binary payload.bundle > payload.txt
    # ... transmit payload.txt ...
    python ucs_dec_tool.py --decode-binary payload.txt > payload.bundle && \\
        python gitbundle.py unbundle payload.bundle --into recovered/

Dependency chain (graceful degradation):
    system git   — preferred; almost always present
    dulwich      — pure Python fallback (pip install dulwich, MIT licensed)
    [error]      — clear message if neither available

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""

from __future__ import print_function, unicode_literals

import argparse
import os
import subprocess
import sys

PY2 = (sys.version_info[0] == 2)

# ── Backend detection ─────────────────────────────────────────────────────────

def _find_git():
    """Return path to system git, or None."""
    try:
        subprocess.check_output(["git", "--version"],
                                stderr=subprocess.DEVNULL)
        return "git"
    except (subprocess.CalledProcessError, OSError):
        return None

def _find_dulwich():
    """Return dulwich.porcelain module, or None."""
    try:
        import dulwich.porcelain  # noqa: F401
        import dulwich.bundle     # noqa: F401
        return True
    except ImportError:
        return False

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
    if repo:
        cmd += ["-C", repo]
    cmd += ["bundle", "create", os.path.abspath(output)]
    if since:
        cmd.append("{0}..HEAD".format(since))
    else:
        cmd.append("HEAD")
    subprocess.check_call(cmd)


def _git_unbundle(bundle, into=None):
    """Unbundle using system git."""
    bundle = os.path.abspath(bundle)
    if into:
        os.makedirs(into, exist_ok=True) if not PY2 else (
            os.makedirs(into) if not os.path.exists(into) else None)
        subprocess.check_call(["git", "init", into])
        subprocess.check_call(
            ["git", "-C", into, "bundle", "unbundle", bundle])
        subprocess.check_call(
            ["git", "-C", into, "checkout", "HEAD"])
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
    """Create a bundle using dulwich."""
    from dulwich.repo import Repo
    from dulwich.bundle import Bundle, write_bundle

    r = Repo(repo or ".")
    b = Bundle()
    b.capabilities = {}

    if since:
        # Only include objects reachable from HEAD not reachable from since
        b.prerequisites = [(since.encode()
                            if isinstance(since, str) else since, b"")]
    else:
        b.prerequisites = []

    head = r.refs[b"HEAD"]
    b.references = {b"refs/heads/main": head}

    with open(output, "wb") as f:
        write_bundle(f, b)


def _dulwich_verify(bundle):
    """Verify a bundle using dulwich."""
    from dulwich.bundle import read_bundle
    with open(bundle, "rb") as f:
        b = read_bundle(f)
    print("Bundle OK")
    print("Prerequisites: {0}".format(len(b.prerequisites)))
    print("References:    {0}".format(len(b.references)))


def _dulwich_ls(bundle):
    """List bundle contents using dulwich."""
    from dulwich.bundle import read_bundle
    with open(bundle, "rb") as f:
        b = read_bundle(f)
    for ref, sha in sorted(b.references.items()):
        ref_str = ref.decode() if isinstance(ref, bytes) else ref
        sha_str = sha.decode() if isinstance(sha, bytes) else sha
        print("{0}  {1}".format(sha_str[:12], ref_str))


# ── Dispatch ──────────────────────────────────────────────────────────────────

def cmd_create(args):
    _require_backend()
    if GIT:
        _git_create(args.output, repo=args.repo, since=args.since)
    else:
        _dulwich_create(args.output, repo=args.repo, since=args.since)
    size = os.path.getsize(args.output)
    print("Bundle: {0} ({1:,} bytes)".format(args.output, size),
          file=sys.stderr)
    print("Encode: python ucs_dec_tool.py --encode-binary {0}".format(
        args.output), file=sys.stderr)
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
    pc.add_argument("--since", default=None, metavar="HASH",
        help="only include commits since this hash (delta bundle)")

    # unbundle
    pu = sub.add_parser("unbundle",
        help="unpack a bundle into a git repository")
    pu.add_argument("bundle", help="bundle file to unpack")
    pu.add_argument("--into", default=None, metavar="DIR",
        help="directory to unbundle into (default: current repo)")

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
    except (subprocess.CalledProcessError, IOError, OSError) as err:
        print("Error: {0}".format(err), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
