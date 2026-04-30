#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_gitbundle.py: tests for gitbundle.py

Run with:
    python -m pytest test_gitbundle.py -v
    python test_gitbundle.py

Requires: Python 3.3+ (uses subprocess.DEVNULL in integration tests)
"""

import binascii
import os
import subprocess
import sys
import tempfile
import unittest

# ---------------------------------------------------------------------------
# Load gitbundle as a module rather than running it as __main__.
# Module-level detection (GIT, DULWICH) still fires on load; that is
# expected and unavoidable. What this avoids is sys.exit(main()) running.
# ---------------------------------------------------------------------------

def _load_gitbundle():
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "gitbundle.py")
    import importlib.util as ilu
    spec = ilu.spec_from_file_location("gitbundle", target)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

gb = _load_gitbundle()

from unittest import mock


# ── _find_git ─────────────────────────────────────────────────────────────────

class TestFindGit(unittest.TestCase):

    def test_returns_git_string_when_available(self):
        with mock.patch("subprocess.check_output"):
            result = gb._find_git()
        self.assertEqual(result, "git")

    def test_returns_none_on_oserror(self):
        with mock.patch("subprocess.check_output", side_effect=OSError):
            result = gb._find_git()
        self.assertIsNone(result)

    def test_returns_none_on_calledprocesserror(self):
        err = subprocess.CalledProcessError(1, "git")
        with mock.patch("subprocess.check_output", side_effect=err):
            result = gb._find_git()
        self.assertIsNone(result)

    def test_does_not_use_subprocess_devnull_directly(self):
        """Regression: subprocess.DEVNULL is Python 3.3+ only; must use open()."""
        import inspect
        src = inspect.getsource(gb._find_git)
        self.assertNotIn("subprocess.DEVNULL", src,
                         "_find_git must not use subprocess.DEVNULL (Python 2 compat)")


# ── _require_backend ──────────────────────────────────────────────────────────

class TestRequireBackend(unittest.TestCase):

    def test_passes_when_git_available(self):
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False):
            gb._require_backend()  # must not raise or exit

    def test_passes_when_dulwich_available(self):
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", True):
            gb._require_backend()

    def test_exits_when_neither_available(self):
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", False):
            with self.assertRaises(SystemExit) as ctx:
                gb._require_backend()
        self.assertEqual(ctx.exception.code, 1)


# ── build_parser ──────────────────────────────────────────────────────────────

class TestBuildParser(unittest.TestCase):

    def setUp(self):
        self.p = gb.build_parser()

    # --- create subcommand ---

    def test_create_positional(self):
        args = self.p.parse_args(["create", "out.bundle"])
        self.assertEqual(args.command, "create")
        self.assertEqual(args.output, "out.bundle")

    def test_create_defaults(self):
        args = self.p.parse_args(["create", "out.bundle"])
        self.assertIsNone(args.repo)
        self.assertIsNone(args.since)

    def test_create_with_since(self):
        args = self.p.parse_args(["create", "--since", "abc123f", "out.bundle"])
        self.assertEqual(args.since, "abc123f")

    def test_create_with_repo(self):
        args = self.p.parse_args(["create", "--repo", "/srv/repo", "out.bundle"])
        self.assertEqual(args.repo, "/srv/repo")

    def test_create_all_options(self):
        args = self.p.parse_args(
            ["create", "--since", "deadbeef", "--repo", "/srv/repo", "delta.bundle"])
        self.assertEqual(args.output, "delta.bundle")
        self.assertEqual(args.since, "deadbeef")
        self.assertEqual(args.repo, "/srv/repo")

    # --- unbundle subcommand ---

    def test_unbundle_positional(self):
        args = self.p.parse_args(["unbundle", "in.bundle"])
        self.assertEqual(args.command, "unbundle")
        self.assertEqual(args.bundle, "in.bundle")

    def test_unbundle_default_into(self):
        args = self.p.parse_args(["unbundle", "in.bundle"])
        self.assertIsNone(args.into)

    def test_unbundle_with_into(self):
        args = self.p.parse_args(["unbundle", "in.bundle", "--into", "/tmp/repo"])
        self.assertEqual(args.into, "/tmp/repo")

    # --- verify subcommand ---

    def test_verify_positional(self):
        args = self.p.parse_args(["verify", "payload.bundle"])
        self.assertEqual(args.command, "verify")
        self.assertEqual(args.bundle, "payload.bundle")

    # --- ls subcommand ---

    def test_ls_positional(self):
        args = self.p.parse_args(["ls", "payload.bundle"])
        self.assertEqual(args.command, "ls")
        self.assertEqual(args.bundle, "payload.bundle")

    # --- missing command ---

    def test_no_command_exits(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args([])

    def test_unknown_command_exits(self):
        with self.assertRaises(SystemExit):
            self.p.parse_args(["frobnicate", "x.bundle"])


# ── _git_create ───────────────────────────────────────────────────────────────

class TestGitCreate(unittest.TestCase):

    def test_basic_create_uses_all_flag(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_create("/out/payload.bundle")
        cmd = m.call_args[0][0]
        self.assertIn("bundle", cmd)
        self.assertIn("create", cmd)
        self.assertIn("--all", cmd)

    def test_since_uses_all_with_exclusion(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_create("/out/delta.bundle", since="abc123")
        cmd = m.call_args[0][0]
        self.assertIn("--all", cmd)
        self.assertTrue(any("^abc123" in a for a in cmd),
                        "Expected '^abc123' exclusion in command: {0}".format(cmd))

    def test_since_empty_string_raises_value_error(self):
        # Empty string is not None but is not a valid revision; must raise.
        with self.assertRaises(ValueError):
            with mock.patch("subprocess.check_call"):
                gb._git_create("/out/delta.bundle", since="")

    def test_repo_empty_string_raises_value_error(self):
        # Empty string is not None but is not a valid path; must raise.
        with self.assertRaises(ValueError):
            with mock.patch("subprocess.check_call"):
                gb._git_create("/out/payload.bundle", repo="")

    def test_since_none_produces_no_exclusion(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_create("/out/payload.bundle", since=None)
        cmd = m.call_args[0][0]
        self.assertFalse(any(a.startswith("^") for a in cmd),
                         "since=None should not produce an exclusion: {0}".format(cmd))

    def test_repo_flag_passes_dash_c(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_create("/out/payload.bundle", repo="/my/repo")
        cmd = m.call_args[0][0]
        self.assertIn("-C", cmd)
        self.assertIn("/my/repo", cmd)

    def test_output_path_is_absolute(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_create("relative.bundle")
        cmd = m.call_args[0][0]
        bundle_arg = [a for a in cmd if a.endswith(".bundle")][0]
        self.assertTrue(os.path.isabs(bundle_arg),
                        "Bundle path must be absolute: {0}".format(bundle_arg))


# ── _git_unbundle ─────────────────────────────────────────────────────────────

class TestGitUnbundle(unittest.TestCase):

    def test_no_into_calls_unbundle(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("/path/to/payload.bundle")
        m.assert_called_once()
        cmd = m.call_args[0][0]
        self.assertIn("unbundle", cmd)

    def test_into_uses_git_clone(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("/path/to/payload.bundle", into="/tmp/recovered")
        m.assert_called_once()
        cmd = m.call_args[0][0]
        self.assertEqual(cmd[0], "git")
        self.assertEqual(cmd[1], "clone")

    def test_into_passes_destination(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("/path/to/payload.bundle", into="/tmp/recovered")
        cmd = m.call_args[0][0]
        self.assertIn("/tmp/recovered", cmd)

    def test_into_does_not_call_git_init(self):
        """git clone handles init; no separate init step should be called."""
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("/path/to/payload.bundle", into="/tmp/recovered")
        for call in m.call_args_list:
            cmd = call[0][0]
            self.assertFalse(
                cmd[0] == "git" and "init" in cmd,
                "git init must not be called; git clone handles init")

    def test_bundle_path_is_absolute_for_unbundle(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("relative.bundle")
        cmd = m.call_args[0][0]
        bundle_arg = [a for a in cmd if a.endswith(".bundle")][0]
        self.assertTrue(os.path.isabs(bundle_arg))

    def test_bundle_path_is_absolute_for_clone(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_unbundle("relative.bundle", into="/tmp/out")
        cmd = m.call_args[0][0]
        bundle_arg = [a for a in cmd if a.endswith(".bundle")][0]
        self.assertTrue(os.path.isabs(bundle_arg))


# ── _git_verify / _git_ls ─────────────────────────────────────────────────────

class TestGitVerify(unittest.TestCase):

    def test_calls_git_bundle_verify(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_verify("/path/to/payload.bundle")
        m.assert_called_once()
        cmd = m.call_args[0][0]
        self.assertIn("verify", cmd)

    def test_bundle_path_is_absolute(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_verify("relative.bundle")
        cmd = m.call_args[0][0]
        bundle_arg = [a for a in cmd if a.endswith(".bundle")][0]
        self.assertTrue(os.path.isabs(bundle_arg))


class TestGitLs(unittest.TestCase):

    def test_calls_git_bundle_list_heads(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_ls("/path/to/payload.bundle")
        m.assert_called_once()
        cmd = m.call_args[0][0]
        self.assertIn("list-heads", cmd)

    def test_bundle_path_is_absolute(self):
        with mock.patch("subprocess.check_call") as m:
            gb._git_ls("relative.bundle")
        cmd = m.call_args[0][0]
        bundle_arg = [a for a in cmd if a.endswith(".bundle")][0]
        self.assertTrue(os.path.isabs(bundle_arg))


# ── _dulwich_create ───────────────────────────────────────────────────────────

class TestDulwichCreate(unittest.TestCase):

    def test_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            gb._dulwich_create("/tmp/out.bundle")

    def test_error_message_mentions_git(self):
        try:
            gb._dulwich_create("/tmp/out.bundle")
        except NotImplementedError as e:
            self.assertIn("git", str(e).lower())


class TestDulwichVerify(unittest.TestCase):

    def _run_dulwich_verify(self, prereq_count, ref_count):
        bundle_mock = mock.Mock()
        bundle_mock.prerequisites = [None] * prereq_count
        bundle_mock.references = {str(i): str(i) for i in range(ref_count)}

        dulwich_bundle_mod = mock.MagicMock()
        dulwich_bundle_mod.read_bundle.return_value = bundle_mock
        printed = []
        with mock.patch.dict("sys.modules", {
                "dulwich": mock.MagicMock(),
                "dulwich.bundle": dulwich_bundle_mod}), \
             mock.patch("builtins.open", mock.mock_open(read_data=b"")), \
             mock.patch("builtins.print",
                        side_effect=lambda *a, **k: printed.append(a[0] if a else "")):
            gb._dulwich_verify("/fake/bundle")
        return printed

    def test_output_includes_ref_and_prereq_counts(self):
        printed = self._run_dulwich_verify(prereq_count=2, ref_count=3)
        combined = " ".join(printed)
        self.assertIn("3", combined)
        self.assertIn("2", combined)

    def test_output_does_not_claim_full_integrity(self):
        printed = self._run_dulwich_verify(prereq_count=0, ref_count=1)
        combined = " ".join(printed).lower()
        self.assertNotIn("bundle ok", combined,
            "Must not print 'Bundle OK' -- dulwich only parses the header")

    def test_output_mentions_install_git(self):
        printed = self._run_dulwich_verify(prereq_count=0, ref_count=1)
        combined = " ".join(printed).lower()
        self.assertIn("git", combined)


# ── _dulwich_ls SHA encoding ──────────────────────────────────────────────────

class TestDulwichLsShaEncoding(unittest.TestCase):
    """Verify _dulwich_ls handles both 20-byte binary and 40-byte hex SHAs."""

    def _make_bundle_mock(self, sha_value):
        bundle = mock.Mock()
        bundle.references = {b"refs/heads/main": sha_value}
        return bundle

    def _run_dulwich_ls(self, bundle_mock):
        """Run _dulwich_ls with a fully mocked dulwich (no real install required)."""
        dulwich_bundle_mod = mock.MagicMock()
        dulwich_bundle_mod.read_bundle.return_value = bundle_mock
        printed = []
        with mock.patch.dict("sys.modules", {
                "dulwich": mock.MagicMock(),
                "dulwich.bundle": dulwich_bundle_mod}), \
             mock.patch("builtins.open", mock.mock_open(read_data=b"")), \
             mock.patch("builtins.print",
                        side_effect=lambda *a, **k: printed.append(a[0] if a else "")):
            gb._dulwich_ls("/fake/bundle")
        return printed

    def test_raw_20_byte_sha_is_hex_encoded(self):
        raw_sha = b"\xde\xad\xbe\xef" + b"\x00" * 16  # 20 raw bytes
        printed = self._run_dulwich_ls(self._make_bundle_mock(raw_sha))
        self.assertTrue(len(printed) > 0, "Expected at least one printed line")
        # Output format: "<sha40>  <ref>" -- full 40-char SHA, no truncation
        sha_part = printed[0].split("  ")[0]
        self.assertEqual(len(sha_part), 40, "Full 40-char SHA expected: {0!r}".format(sha_part))
        self.assertTrue(
            all(c in "0123456789abcdef" for c in sha_part),
            "SHA should be printable hex, got: {0!r}".format(sha_part))
        self.assertTrue(sha_part.startswith("deadbeef"))

    def test_40_byte_hex_sha_decoded_directly(self):
        hex_sha = b"deadbeef" + b"00" * 16  # 40 ASCII hex bytes
        printed = self._run_dulwich_ls(self._make_bundle_mock(hex_sha))
        self.assertTrue(len(printed) > 0, "Expected at least one printed line")
        sha_part = printed[0].split("  ")[0]
        self.assertEqual(len(sha_part), 40)
        self.assertIn("deadbeef", sha_part)

    def test_sha_length_20_triggers_hexlify(self):
        """Unit test the branching logic directly, without dulwich."""
        raw = b"\xca\xfe\xba\xbe" + b"\x01" * 16
        self.assertEqual(len(raw), 20)
        expected = binascii.hexlify(raw).decode("ascii")
        # Reproduce the logic from _dulwich_ls
        sha_str = (binascii.hexlify(raw).decode("ascii")
                   if len(raw) == 20 else raw.decode("ascii", errors="replace"))
        self.assertEqual(sha_str, expected)
        self.assertEqual(len(sha_str), 40)

    def test_sha_length_40_decoded_directly(self):
        hex_bytes = b"cafe0000" * 5  # 40 bytes
        self.assertEqual(len(hex_bytes), 40)
        sha_str = (binascii.hexlify(hex_bytes).decode("ascii")
                   if len(hex_bytes) == 20 else hex_bytes.decode("ascii", errors="replace"))
        self.assertEqual(sha_str, hex_bytes.decode("ascii"))


# ── cmd_create ────────────────────────────────────────────────────────────────

class TestCmdCreate(unittest.TestCase):

    def _args(self, output="/tmp/test.bundle", repo=None, since=None):
        a = mock.Mock()
        a.output = output
        a.repo = repo
        a.since = since
        return a

    def test_git_path_returns_zero(self):
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False), \
             mock.patch("subprocess.check_call"), \
             mock.patch("os.path.getsize", return_value=1024):
            rc = gb.cmd_create(self._args())
        self.assertEqual(rc, 0)

    def test_dulwich_only_returns_one(self):
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", True):
            rc = gb.cmd_create(self._args())
        self.assertEqual(rc, 1)

    def test_git_forwards_since(self):
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False), \
             mock.patch("subprocess.check_call") as m, \
             mock.patch("os.path.getsize", return_value=512):
            gb.cmd_create(self._args(since="abc123"))
        cmd = m.call_args[0][0]
        self.assertIn("--all", cmd)
        self.assertTrue(any("^abc123" in a for a in cmd))

    def test_cmd_create_encode_hint_uses_absolute_path(self):
        import io
        args = self._args(output="relative.bundle")
        buf = io.StringIO()
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False), \
             mock.patch("subprocess.check_call"), \
             mock.patch("os.path.getsize", return_value=512), \
             mock.patch("sys.stderr", buf):
            gb.cmd_create(args)
        output = buf.getvalue()
        self.assertIn(os.path.abspath("relative.bundle"), output)

    def test_git_forwards_repo(self):
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False), \
             mock.patch("subprocess.check_call") as m, \
             mock.patch("os.path.getsize", return_value=512):
            gb.cmd_create(self._args(repo="/srv/repo"))
        cmd = m.call_args[0][0]
        self.assertIn("-C", cmd)
        self.assertIn("/srv/repo", cmd)


# ── cmd_unbundle ──────────────────────────────────────────────────────────────

class TestCmdUnbundle(unittest.TestCase):

    def test_git_no_into_returns_zero(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        args.into = None
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.cmd_unbundle(args)
        self.assertEqual(rc, 0)

    def test_git_with_into_returns_zero(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        args.into = "/tmp/recovered"
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.cmd_unbundle(args)
        self.assertEqual(rc, 0)

    def test_dulwich_only_returns_one(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        args.into = None
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", True):
            rc = gb.cmd_unbundle(args)
        self.assertEqual(rc, 1)


# ── cmd_verify ────────────────────────────────────────────────────────────────

class TestCmdVerify(unittest.TestCase):

    def test_git_returns_zero(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.cmd_verify(args)
        self.assertEqual(rc, 0)

    def test_dulwich_verify_called_when_no_git(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", True), \
             mock.patch.object(gb, "_dulwich_verify") as m:
            gb.cmd_verify(args)
        m.assert_called_once_with(args.bundle)


# ── cmd_ls ────────────────────────────────────────────────────────────────────

class TestCmdLs(unittest.TestCase):

    def test_git_returns_zero(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.cmd_ls(args)
        self.assertEqual(rc, 0)

    def test_dulwich_ls_called_when_no_git(self):
        args = mock.Mock()
        args.bundle = "/tmp/payload.bundle"
        with mock.patch.object(gb, "GIT", None), \
             mock.patch.object(gb, "DULWICH", True), \
             mock.patch.object(gb, "_dulwich_ls") as m:
            gb.cmd_ls(args)
        m.assert_called_once_with(args.bundle)


# ── main error handling ───────────────────────────────────────────────────────

class TestMainErrors(unittest.TestCase):

    def test_calledprocesserror_returns_one(self):
        err = subprocess.CalledProcessError(1, "git")
        with mock.patch("sys.argv", ["gitbundle.py", "verify", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call", side_effect=err):
            rc = gb.main()
        self.assertEqual(rc, 1)

    def test_ioerror_returns_one(self):
        with mock.patch("sys.argv", ["gitbundle.py", "verify", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call", side_effect=IOError("no such file")):
            rc = gb.main()
        self.assertEqual(rc, 1)

    def test_oserror_returns_one(self):
        with mock.patch("sys.argv", ["gitbundle.py", "verify", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call", side_effect=OSError("gone")):
            rc = gb.main()
        self.assertEqual(rc, 1)

    def test_valueerror_from_empty_since_returns_one(self):
        with mock.patch("sys.argv",
                        ["gitbundle.py", "create", "--since", "", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False):
            rc = gb.main()
        self.assertEqual(rc, 1)

    def test_successful_verify_returns_zero(self):
        with mock.patch("sys.argv", ["gitbundle.py", "verify", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.main()
        self.assertEqual(rc, 0)

    def test_successful_ls_returns_zero(self):
        with mock.patch("sys.argv", ["gitbundle.py", "ls", "/tmp/x.bundle"]), \
             mock.patch.object(gb, "GIT", "git"), \
             mock.patch("subprocess.check_call"):
            rc = gb.main()
        self.assertEqual(rc, 0)


# ── integration: round-trip against live git (skipped when git absent) ────────

@unittest.skipUnless(
    gb.GIT, "system git not available; skipping integration tests")
class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="gitbundle_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_repo(self, name="src"):
        repo_dir = os.path.join(self.tmpdir, name)
        # Avoid -b/--initial-branch: that flag requires git 2.28+. The tool
        # itself only needs git 1.6.0+ and _git_create uses --all, so the
        # default branch name does not matter for any test assertion.
        subprocess.check_call(["git", "init", repo_dir],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        subprocess.check_call(
            ["git", "-C", repo_dir, "config", "user.email", "test@example.com"])
        subprocess.check_call(
            ["git", "-C", repo_dir, "config", "user.name", "Test"])
        sentinel = os.path.join(repo_dir, "hello.txt")
        with open(sentinel, "w") as f:
            f.write("hello from gitbundle integration test\n")
        subprocess.check_call(["git", "-C", repo_dir, "add", "hello.txt"])
        subprocess.check_call(
            ["git", "-C", repo_dir, "commit", "-m", "initial commit"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        return repo_dir

    def test_create_produces_file(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        gb._git_create(bundle, repo=repo)
        self.assertTrue(os.path.exists(bundle))
        self.assertGreater(os.path.getsize(bundle), 0)

    def test_verify_passes_on_valid_bundle(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        gb._git_create(bundle, repo=repo)
        gb._git_verify(bundle)  # raises CalledProcessError on failure

    def test_ls_prints_refs(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        gb._git_create(bundle, repo=repo)
        # Should not raise; output goes to stdout.
        gb._git_ls(bundle)

    def test_unbundle_into_creates_repo(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        gb._git_create(bundle, repo=repo)
        dest = os.path.join(self.tmpdir, "recovered")
        gb._git_unbundle(bundle, into=dest)
        self.assertTrue(os.path.isdir(os.path.join(dest, ".git")),
                        "Recovered directory should contain a .git folder")
        self.assertTrue(
            os.path.exists(os.path.join(dest, "hello.txt")),
            "Recovered directory should contain committed files")

    def test_round_trip_file_contents(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        gb._git_create(bundle, repo=repo)
        dest = os.path.join(self.tmpdir, "recovered")
        gb._git_unbundle(bundle, into=dest)
        with open(os.path.join(dest, "hello.txt")) as f:
            contents = f.read()
        self.assertIn("hello from gitbundle integration test", contents)

    def test_delta_bundle_since(self):
        repo = self._make_repo()
        # Grab HEAD hash before second commit
        first_hash = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "HEAD"]).decode().strip()
        # Add a second commit
        with open(os.path.join(repo, "second.txt"), "w") as f:
            f.write("second commit\n")
        subprocess.check_call(["git", "-C", repo, "add", "second.txt"])
        subprocess.check_call(
            ["git", "-C", repo, "commit", "-m", "second commit"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Create a delta bundle since first_hash
        delta = os.path.join(self.tmpdir, "delta.bundle")
        gb._git_create(delta, repo=repo, since=first_hash)
        self.assertTrue(os.path.exists(delta))
        self.assertGreater(os.path.getsize(delta), 0)
        # Verify from the source repo; delta bundles require the prerequisite
        # commits to be present in the repo used for verification.
        subprocess.check_call(
            ["git", "-C", repo, "bundle", "verify", delta])

    def test_cmd_create_returns_zero(self):
        repo = self._make_repo()
        bundle = os.path.join(self.tmpdir, "payload.bundle")
        args = mock.Mock()
        args.output = bundle
        args.repo = repo
        args.since = None
        with mock.patch.object(gb, "GIT", "git"), \
             mock.patch.object(gb, "DULWICH", False):
            rc = gb.cmd_create(args)
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(bundle))


if __name__ == "__main__":
    unittest.main(verbosity=2)
