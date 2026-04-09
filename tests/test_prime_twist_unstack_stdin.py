"""
Tests for prime_twist.py unstack stdin support (PIPE-002).

`prime_twist.py unstack` historically required a positional file path
and could not participate in a pipeline without an intermediate file.
PIPE-002 fixes this by treating `-` as stdin, matching the convention
already used by archivist.py and ucs_dec_tool.py.

These tests cover:
  - the in-process command function with `infile="-"` and a stubbed stdin
  - the CLI surface via subprocess (the actual bug was a CLI ergonomics
    failure, so we exercise the real argv path too)
  - parity between `unstack <file>` and `unstack -` for the same input
"""

import io
import os
import subprocess
import sys

import pytest

# Make `tools/mnemonic/prime_twist.py` importable as a module.
TOOL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tools", "mnemonic")
sys.path.insert(0, TOOL_DIR)
import prime_twist  # noqa: E402


PRIME_TWIST_PATH = os.path.abspath(
    os.path.join(TOOL_DIR, "prime_twist.py"))

# Two small primes — enough to exercise both passes without slow
# verse derivation. Stack output is deterministic for fixed input + primes.
PRIMES = "7727,4943"
INPUT_TOKENS = "00065 00066 00067 00068"  # ASCII A B C D in WIDTH/5 UCS-DEC
EXPECTED_OUT = "00065  00066  00067  00068"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def stack_file(tmp_path):
    """Build a real stack file by running `stack` once, return its path."""
    out = tmp_path / "stack.txt"
    proc = subprocess.run(
        [sys.executable, PRIME_TWIST_PATH, "stack",
         "--primes", PRIMES, "--ref", "TEST", "--no-symbol-check"],
        input=INPUT_TOKENS,
        capture_output=True,
        text=True,
        check=True,
    )
    out.write_text(proc.stdout, encoding="utf-8")
    return out


@pytest.fixture
def stack_text(stack_file):
    """The stack file contents as a string."""
    return stack_file.read_text(encoding="utf-8")


# ── In-process: cmd_unstack honours infile == "-" ────────────────────────────


class TestCmdUnstackStdin:
    """Direct tests against prime_twist.cmd_unstack with infile='-'."""

    def test_dash_reads_stdin(self, stack_text, monkeypatch, capsys):
        """When infile is '-', cmd_unstack must read content from stdin."""
        monkeypatch.setattr("sys.stdin", io.StringIO(stack_text))

        class Args:
            infile = "-"

        rc = prime_twist.cmd_unstack(Args())
        captured = capsys.readouterr()
        assert rc == 0
        assert captured.out.strip() == EXPECTED_OUT

    def test_dash_does_not_open_file_named_dash(
            self, stack_text, monkeypatch, capsys):
        """'-' must NOT be interpreted as a literal filename."""
        def _no_open(*a, **kw):
            raise AssertionError(
                "io.open should not be called when infile == '-'")
        monkeypatch.setattr(prime_twist.io, "open", _no_open)
        monkeypatch.setattr("sys.stdin", io.StringIO(stack_text))

        class Args:
            infile = "-"

        rc = prime_twist.cmd_unstack(Args())
        assert rc == 0
        assert capsys.readouterr().out.strip() == EXPECTED_OUT

    def test_file_path_still_works(self, stack_file, capsys):
        """Regression: passing a real file path must continue to work."""

        class Args:
            infile = str(stack_file)

        rc = prime_twist.cmd_unstack(Args())
        assert rc == 0
        assert capsys.readouterr().out.strip() == EXPECTED_OUT

    def test_empty_stdin_errors_cleanly(self, monkeypatch, capsys):
        """Empty stdin must produce a parse error, not a traceback."""
        monkeypatch.setattr("sys.stdin", io.StringIO(""))

        class Args:
            infile = "-"

        rc = prime_twist.cmd_unstack(Args())
        captured = capsys.readouterr()
        assert rc == 1
        assert "no stack passes" in captured.err


# ── CLI: subprocess against the real argv path ──────────────────────────────


class TestUnstackCliStdin:
    """End-to-end CLI tests — the bug was a CLI ergonomics failure."""

    def test_cli_dash_reads_stdin(self, stack_text):
        """`prime_twist.py unstack -` consumes stdin and writes tokens."""
        proc = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "unstack", "-"],
            input=stack_text,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == EXPECTED_OUT

    def test_cli_file_and_stdin_match(self, stack_file, stack_text):
        """`unstack <file>` and `unstack -` produce identical stdout."""
        from_file = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "unstack", str(stack_file)],
            capture_output=True, text=True, check=True,
        )
        from_stdin = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "unstack", "-"],
            input=stack_text,
            capture_output=True, text=True, check=True,
        )
        assert from_file.stdout == from_stdin.stdout

    def test_cli_pipeline_stack_then_unstack(self):
        """Full pipe: stack | unstack - returns the original tokens."""
        stack_proc = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "stack",
             "--primes", PRIMES, "--ref", "PIPE", "--no-symbol-check"],
            input=INPUT_TOKENS,
            capture_output=True, text=True, check=True,
        )
        unstack_proc = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "unstack", "-"],
            input=stack_proc.stdout,
            capture_output=True, text=True, check=True,
        )
        assert unstack_proc.stdout.strip() == EXPECTED_OUT

    def test_cli_help_documents_stdin(self):
        """`unstack --help` must mention that `-` means stdin."""
        proc = subprocess.run(
            [sys.executable, PRIME_TWIST_PATH, "unstack", "--help"],
            capture_output=True, text=True, check=True,
        )
        assert "-" in proc.stdout and "stdin" in proc.stdout.lower()
