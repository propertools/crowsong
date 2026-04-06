"""
Tests for WIDTH/3 BINARY mode in ucs_dec_tool.py.

WIDTH/3 BINARY encodes raw byte streams as 3-digit zero-padded decimals.
Each token represents a single byte (0-255).  The BINARY flag in the
ENC: header signals that the decoder should emit raw bytes, not Unicode
code points.

Per draft-darley-fds-01 Section 6.2:
- The trailer uses BYTES (not VALUES) for binary frames.
- The BYTES count is the exact original byte count, including 0x00.
- Null-skip MUST NOT be applied in BINARY mode when a BYTES trailer
  is present; the BYTES count is the sole data/padding boundary.
"""

import binascii
import os
import subprocess
import sys

import pytest

# Import the tool module directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "ucs-dec"))
import ucs_dec_tool


# ── Encoding ─────────────────────────────────────────────────────────────────


class TestEncodeBinary:
    """Tests for binary encoding (bytes -> WIDTH/3 decimal tokens)."""

    def test_encode_simple_ascii(self):
        """ASCII bytes encode to their decimal code point values."""
        data = b"Hi"
        result = ucs_dec_tool.encode_binary(data)
        # H=72, i=105
        assert "072" in result
        assert "105" in result

    def test_encode_single_byte_zero(self):
        """Byte 0x00 encodes to 000."""
        result = ucs_dec_tool.encode_binary(b"\x00")
        tokens = result.split()
        assert tokens[0] == "000"

    def test_encode_max_byte(self):
        """Byte 0xFF (255) encodes to 255."""
        result = ucs_dec_tool.encode_binary(b"\xff")
        tokens = result.split()
        assert tokens[0] == "255"

    def test_encode_all_zeros(self):
        """All-zero input produces all-000 tokens."""
        result = ucs_dec_tool.encode_binary(b"\x00\x00\x00")
        tokens = result.split()
        assert all(t == "000" for t in tokens)

    def test_encode_width_is_3(self):
        """Every token must be exactly 3 digits wide."""
        data = b"Signal survives."
        result = ucs_dec_tool.encode_binary(data)
        for token in result.split():
            assert len(token) == 3
            assert token.isdigit()

    def test_encode_col_formatting(self):
        """Default COL/6: rows contain 6 tokens, padding with 000."""
        data = b"ABCDEFGH"  # 8 bytes -> 2 rows, second row padded
        result = ucs_dec_tool.encode_binary(data, cols=6)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        # First row: 6 tokens
        assert len(lines[0].split()) == 6
        # Second row: 2 real + 4 pad
        row2_tokens = lines[1].split()
        assert len(row2_tokens) == 6
        assert row2_tokens[2:] == ["000"] * 4

    def test_encode_col_zero_no_wrapping(self):
        """COL/0 disables wrapping: all tokens on one line."""
        data = b"ABCDEFGHIJ"
        result = ucs_dec_tool.encode_binary(data, cols=0)
        assert "\n" not in result.strip()
        assert len(result.split()) == 10

    def test_encode_empty_input(self):
        """Empty bytes produces empty output."""
        result = ucs_dec_tool.encode_binary(b"")
        assert result.strip() == ""

    def test_encode_full_byte_range(self):
        """All 256 byte values encode correctly."""
        data = bytes(range(256))
        result = ucs_dec_tool.encode_binary(data)
        tokens = result.split()
        # Filter out padding tokens from column formatting
        real_tokens = [t for t in tokens if int(t) < 256 or t == "000"]
        # We should have at least 256 tokens (some 000 may be padding)
        # Check that bytes 1-255 all appear
        values = [int(t) for t in tokens]
        for b in range(256):
            assert b in values, f"byte {b} not found in encoded output"

    def test_encode_returns_string(self):
        """encode_binary returns a str, not bytes."""
        result = ucs_dec_tool.encode_binary(b"\x01\x02")
        assert isinstance(result, str)


# ── Decoding ─────────────────────────────────────────────────────────────────


class TestDecodeBinary:
    """Tests for binary decoding (WIDTH/3 tokens -> bytes)."""

    def test_decode_simple(self):
        """Basic decode of WIDTH/3 tokens back to bytes."""
        encoded = "072  105"  # H=72, i=105
        result = ucs_dec_tool.decode_binary(encoded)
        assert result == b"Hi"

    def test_decode_skips_null_padding(self):
        """Null tokens (000) are skipped by default."""
        encoded = "072  105  000  000  000  000"
        result = ucs_dec_tool.decode_binary(encoded)
        assert result == b"Hi"

    def test_decode_keeps_null_when_requested(self):
        """Null tokens preserved when skip_null=False."""
        encoded = "072  105  000"
        result = ucs_dec_tool.decode_binary(encoded, skip_null=False)
        assert result == b"Hi\x00"

    def test_decode_rejects_over_255(self):
        """Tokens > 255 are silently skipped (not valid bytes)."""
        encoded = "072  256  105"
        result = ucs_dec_tool.decode_binary(encoded)
        assert result == b"Hi"

    def test_decode_max_byte(self):
        """Token 255 decodes to byte 0xFF."""
        encoded = "255"
        result = ucs_dec_tool.decode_binary(encoded)
        assert result == b"\xff"

    def test_decode_multiline(self):
        """Tokens spanning multiple lines decode correctly."""
        encoded = "083  105  103  110  097  108\n046  000  000  000  000  000"
        result = ucs_dec_tool.decode_binary(encoded)
        assert result == b"Signal."

    def test_decode_returns_bytes(self):
        """decode_binary returns bytes, not str."""
        result = ucs_dec_tool.decode_binary("065")
        assert isinstance(result, bytes)

    def test_decode_empty_input(self):
        """Empty input produces empty bytes."""
        result = ucs_dec_tool.decode_binary("")
        assert result == b""


# ── Roundtrip ────────────────────────────────────────────────────────────────


class TestRoundtripBinary:
    """Roundtrip: encode_binary -> decode_binary produces original bytes."""

    def test_roundtrip_ascii(self):
        data = b"Signal survives."
        encoded = ucs_dec_tool.encode_binary(data)
        decoded = ucs_dec_tool.decode_binary(encoded)
        assert decoded == data

    def test_roundtrip_all_bytes(self):
        """Full byte range roundtrips correctly (no column padding)."""
        data = bytes(range(256))
        encoded = ucs_dec_tool.encode_binary(data, cols=0)
        decoded = ucs_dec_tool.decode_binary(encoded, skip_null=False)
        assert decoded == data

    def test_roundtrip_non_null_bytes(self):
        """Non-zero bytes roundtrip with default null-skip."""
        data = bytes(range(1, 256))
        encoded = ucs_dec_tool.encode_binary(data)
        decoded = ucs_dec_tool.decode_binary(encoded)
        assert decoded == data

    def test_roundtrip_binary_payload(self):
        """Arbitrary binary data (not valid UTF-8) roundtrips."""
        data = b"\x80\x81\xfe\xff\x00\x01\x7f"
        encoded = ucs_dec_tool.encode_binary(data, cols=0)
        decoded = ucs_dec_tool.decode_binary(encoded, skip_null=False)
        assert decoded == data

    def test_roundtrip_empty(self):
        encoded = ucs_dec_tool.encode_binary(b"")
        decoded = ucs_dec_tool.decode_binary(encoded)
        assert decoded == b""


# ── Frame integration ────────────────────────────────────────────────────────


class TestBinaryFrame:
    """Tests for BINARY flag in FDS-FRAME and Print Profile."""

    def test_frame_header_contains_binary_flag(self):
        """Framed binary artifact has BINARY in the ENC: header."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        assert "BINARY" in framed

    def test_frame_header_contains_width_3(self):
        """Framed binary artifact declares WIDTH/3."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        assert "WIDTH/3" in framed

    def test_frame_header_contains_pad_000(self):
        """Framed binary artifact declares PAD/000."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        assert "PAD/000" in framed

    def test_frame_trailer_says_bytes_not_values(self):
        """BINARY frames use BYTES in trailer, not VALUES."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        assert "4 BYTES" in framed
        assert "VALUES" not in framed

    def test_frame_bytes_count_includes_null_bytes(self):
        """BYTES count includes 0x00 data bytes."""
        data = b"\x48\x00\x65\x6c\x00\x6c\x6f\x0a"  # spec worked example
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        assert "8 BYTES" in framed

    def test_parse_frame_detects_binary(self):
        """parse_frame extracts the BINARY flag."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        parsed = ucs_dec_tool.parse_frame(framed)
        assert parsed["binary"] is True
        assert parsed["width"] == 3

    def test_parse_frame_bytes_trailer(self):
        """parse_frame extracts BYTES trailer keyword."""
        data = b"test"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        parsed = ucs_dec_tool.parse_frame(framed)
        assert parsed["trailer_keyword"] == "BYTES"
        assert parsed["declared_count"] == 4

    def test_parse_frame_non_binary_default(self):
        """parse_frame returns binary=False for standard text artifacts."""
        payload = ucs_dec_tool.encode("Hello", width=5, cols=6)
        framed = ucs_dec_tool.frame(payload, width=5, cols=6)
        parsed = ucs_dec_tool.parse_frame(framed)
        assert parsed["binary"] is False

    def test_verify_binary_frame(self):
        """verify_frame works correctly with WIDTH/3 BINARY artifacts."""
        data = b"\x01\x02\x03\x04"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    ref="TEST-001", byte_count=len(data))
        parsed = ucs_dec_tool.parse_frame(framed)
        vr = ucs_dec_tool.verify_frame(parsed)
        assert vr["count_ok"]
        assert vr["crc_ok"]

    def test_verify_binary_frame_with_null_bytes(self):
        """verify_frame counts 0x00 data bytes correctly via BYTES."""
        data = b"\x48\x00\x65\x6c\x00\x6c\x6f\x0a"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        parsed = ucs_dec_tool.parse_frame(framed)
        vr = ucs_dec_tool.verify_frame(parsed)
        assert vr["count_ok"]
        assert vr["crc_ok"]

    def test_verify_binary_frame_corruption_detected(self):
        """Corrupted binary frame fails verification."""
        data = b"\x01\x02\x03\x04"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        # Corrupt a token
        corrupted = framed.replace("001", "099", 1)
        parsed = ucs_dec_tool.parse_frame(corrupted)
        if parsed["trailer_found"]:
            vr = ucs_dec_tool.verify_frame(parsed)
            assert not vr["crc_ok"]

    def test_verify_rejects_binary_header_values_trailer(self):
        """BINARY header with VALUES trailer is malformed — count fails."""
        data = b"\x01\x02\x03\x04"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        # Replace BYTES with VALUES in the trailer
        mangled = framed.replace("BYTES", "VALUES")
        parsed = ucs_dec_tool.parse_frame(mangled)
        assert parsed["binary"] is True
        assert parsed["trailer_keyword"] == "VALUES"
        vr = ucs_dec_tool.verify_frame(parsed)
        assert not vr["count_ok"]

    def test_verify_rejects_text_header_bytes_trailer(self):
        """Non-BINARY header with BYTES trailer is malformed — count fails."""
        payload = ucs_dec_tool.encode("Hi", width=5, cols=6)
        framed = ucs_dec_tool.frame(payload, width=5, cols=6)
        # Replace VALUES with BYTES in the trailer
        mangled = framed.replace("VALUES", "BYTES")
        parsed = ucs_dec_tool.parse_frame(mangled)
        assert parsed["binary"] is False
        assert parsed["trailer_keyword"] == "BYTES"
        vr = ucs_dec_tool.verify_frame(parsed)
        assert not vr["count_ok"]


# ── Frame-aware decode integration ───────────────────────────────────────────


class TestFrameAwareBinaryDecode:
    """decode_binary() uses BYTES count from trailer, not null-skip."""

    def test_decode_binary_framed(self):
        """decode_binary on a framed artifact uses BYTES count."""
        data = b"Hello"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        result = ucs_dec_tool.decode_binary(framed)
        assert result == data

    def test_decode_binary_roundtrip_through_frame(self):
        """Full cycle: bytes -> encode_binary -> frame -> decode_binary."""
        data = b"\x80\x81\xfe\xff\x01\x7f"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        result = ucs_dec_tool.decode_binary(framed)
        assert result == data

    def test_decode_binary_null_bytes_preserved_via_bytes_count(self):
        """0x00 data bytes survive roundtrip through framed artifact.

        This is the central test for the BYTES trailer design.
        The spec worked example: 8 bytes including two 0x00s.
        """
        data = b"\x48\x00\x65\x6c\x00\x6c\x6f\x0a"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        result = ucs_dec_tool.decode_binary(framed)
        assert result == data
        assert result[1] == 0x00  # first null byte preserved
        assert result[4] == 0x00  # second null byte preserved

    def test_decode_binary_trailing_null_bytes_preserved(self):
        """Data ending with 0x00 bytes roundtrips correctly."""
        data = b"test\x00\x00\x00"
        payload = ucs_dec_tool.encode_binary(data)
        framed = ucs_dec_tool.frame(payload, width=3, cols=6, binary=True,
                                    byte_count=len(data))
        result = ucs_dec_tool.decode_binary(framed)
        assert result == data


# ── CLI integration ──────────────────────────────────────────────────────────


TOOL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tools", "ucs-dec", "ucs_dec_tool.py"
)


class TestCLIBinary:
    """CLI tests for --binary flag."""

    def _run(self, args, stdin_bytes=b""):
        """Run the tool as a subprocess, passing binary stdin."""
        result = subprocess.run(
            [sys.executable, TOOL_PATH] + args,
            input=stdin_bytes,
            capture_output=True,
            timeout=10,
        )
        return result

    def test_cli_encode_binary(self):
        """--encode --binary produces WIDTH/3 output."""
        r = self._run(["--encode", "--binary"], stdin_bytes=b"Hi")
        assert r.returncode == 0
        output = r.stdout.decode("utf-8")
        tokens = output.split()
        # H=72, i=105
        assert "072" in tokens
        assert "105" in tokens

    def test_cli_encode_binary_framed(self):
        """--encode --binary --frame produces a BINARY-flagged frame."""
        r = self._run(["--encode", "--binary", "--frame"], stdin_bytes=b"Hi")
        assert r.returncode == 0
        output = r.stdout.decode("utf-8")
        assert "BINARY" in output
        assert "WIDTH/3" in output

    def test_cli_decode_binary(self):
        """--decode --binary reads WIDTH/3 tokens and emits raw bytes."""
        payload = b"072  105  000  000  000  000\n"
        r = self._run(["--decode", "--binary"], stdin_bytes=payload)
        assert r.returncode == 0
        assert r.stdout == b"Hi"

    def test_cli_roundtrip_binary(self):
        """Pipe: --encode --binary | --decode --binary roundtrips."""
        data = b"Signal survives."
        r_enc = self._run(["--encode", "--binary"], stdin_bytes=data)
        assert r_enc.returncode == 0
        r_dec = self._run(["--decode", "--binary"], stdin_bytes=r_enc.stdout)
        assert r_dec.returncode == 0
        assert r_dec.stdout == data

    def test_cli_verify_binary_frame(self):
        """--verify on a BINARY-framed artifact succeeds."""
        r_enc = self._run(
            ["--encode", "--binary", "--frame", "--ref", "TEST-BIN-001"],
            stdin_bytes=b"binary test data",
        )
        assert r_enc.returncode == 0
        r_ver = self._run(["--verify"], stdin_bytes=r_enc.stdout)
        assert r_ver.returncode == 0

    def test_cli_decode_binary_rejects_corrupt_frame(self):
        """--decode --binary on a corrupt BINARY frame exits non-zero."""
        r_enc = self._run(
            ["--encode", "--binary", "--frame"],
            stdin_bytes=b"test",
        )
        assert r_enc.returncode == 0
        # Corrupt a payload token
        corrupted = r_enc.stdout.replace(b"116", b"999", 1)
        r_dec = self._run(["--decode", "--binary"], stdin_bytes=corrupted)
        # Should fail due to CRC/count mismatch
        assert r_dec.returncode != 0


# ── Existing text mode unaffected ────────────────────────────────────────────


class TestTextModeUnchanged:
    """WIDTH/3 BINARY must not break existing WIDTH/5 text behaviour."""

    def test_text_encode_unchanged(self):
        """Standard text encode still works as before."""
        result = ucs_dec_tool.encode("Hi", width=5, cols=6)
        assert "00072" in result
        assert "00105" in result

    def test_text_decode_unchanged(self):
        """Standard text decode still works as before."""
        result = ucs_dec_tool.decode("00072  00105")
        assert result == "Hi"

    def test_text_frame_no_binary_flag(self):
        """Standard text frames do not include BINARY."""
        payload = ucs_dec_tool.encode("Hi", width=5, cols=6)
        framed = ucs_dec_tool.frame(payload, width=5, cols=6)
        assert "BINARY" not in framed

    def test_text_frame_uses_values_not_bytes(self):
        """Standard text frames use VALUES in trailer, not BYTES."""
        payload = ucs_dec_tool.encode("Hi", width=5, cols=6)
        framed = ucs_dec_tool.frame(payload, width=5, cols=6)
        assert "VALUES" in framed
        assert "BYTES" not in framed

    def test_existing_canonical_roundtrip(self):
        """Canonical test vector roundtrip is unaffected."""
        raw_path = os.path.join(
            os.path.dirname(__file__), "..", "archive", "second-law-blues.txt"
        )
        payload_path = os.path.join(
            os.path.dirname(__file__), "..",
            "archive", "flash-paper-SI-2084-FP-001-payload.txt"
        )
        if not os.path.exists(raw_path) or not os.path.exists(payload_path):
            pytest.skip("canonical test vector not available")

        with open(raw_path, "r", encoding="utf-8") as f:
            raw = f.read()
        with open(payload_path, "r", encoding="utf-8") as f:
            canonical_payload = f.read().rstrip("\n")

        re_encoded = ucs_dec_tool.encode(raw, width=5, cols=6)
        assert re_encoded == canonical_payload
