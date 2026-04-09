#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_baseconv.py — canonical test vectors for baseconv.py

Covers:
  - Round-trip conversions (forward and inverse)
  - Zero handling
  - Case-insensitivity of input
  - All boundary bases (2 and 36)
  - Invalid base values
  - Empty input
  - Signed input (both + and -)
  - Surrounding whitespace
  - Invalid digits with offset reporting
  - from_int() return type consistency (text, not bytes) across Py2/Py3
  - main() exit codes via argv injection

Run with:
    python2 test_baseconv.py
    python3 test_baseconv.py

All tests must pass on both interpreters.

Compatibility: Python 2.7+ / 3.x
Author: Proper Tools SRL
License: MIT
"""
from __future__ import print_function, unicode_literals

import sys

# ---------------------------------------------------------------------------
# Minimal test harness — no external deps, no unittest required
# ---------------------------------------------------------------------------

_PASS = 0
_FAIL = 0


def ok(label, condition):
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(u"  PASS  {0}".format(label))
    else:
        _FAIL += 1
        print(u"  FAIL  {0}".format(label))


def raises(label, exc_type, fn, *args, **kwargs):
    global _PASS, _FAIL
    try:
        fn(*args, **kwargs)
        _FAIL += 1
        print(u"  FAIL  {0}  (no exception raised)".format(label))
    except exc_type as e:
        _PASS += 1
        print(u"  PASS  {0}  [{1}]".format(label, e))
    except Exception as e:
        _FAIL += 1
        print(u"  FAIL  {0}  (wrong exception: {1})".format(label, e))


def section(title):
    print(u"\n-- {0}".format(title))


# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------

try:
    from baseconv import convert, to_int, from_int, main
except ImportError as e:
    print(u"ERROR: could not import baseconv: {0}".format(e))
    sys.exit(2)


# ---------------------------------------------------------------------------
# 1. Round-trip conversions — canonical vectors
# ---------------------------------------------------------------------------

section(u"Round-trip: decimal <-> hex")
ok(u"255  dec->hex          == FF",       convert(u"255", 10, 16) == u"FF")
ok(u"FF   hex->dec          == 255",      convert(u"FF",  16, 10) == u"255")
ok(u"ff   hex->dec (lower)  == 255",      convert(u"ff",  16, 10) == u"255")
ok(u"fF   hex->dec (mixed)  == 255",      convert(u"fF",  16, 10) == u"255")

section(u"Round-trip: decimal <-> binary")
ok(u"255  dec->bin          == 11111111", convert(u"255",      10,  2) == u"11111111")
ok(u"11111111 bin->dec      == 255",      convert(u"11111111",  2, 10) == u"255")

section(u"Round-trip: decimal <-> octal")
ok(u"255  dec->oct          == 377",      convert(u"255", 10,  8) == u"377")
ok(u"377  oct->dec          == 255",      convert(u"377",  8, 10) == u"255")

section(u"Round-trip: decimal <-> base-36")
ok(u"26716 dec->b36         == KM4",      convert(u"26716", 10, 36) == u"KM4")
ok(u"KM4   b36->dec         == 26716",    convert(u"KM4",   36, 10) == u"26716")
ok(u"km4   b36->dec (lower) == 26716",    convert(u"km4",   36, 10) == u"26716")

section(u"Round-trip: binary <-> base-36")
ok(u"11111111 bin->b36 matches 255 dec->b36",
   convert(u"11111111", 2, 36) == convert(u"255", 10, 36))

# ---------------------------------------------------------------------------
# 2. Zero handling
# ---------------------------------------------------------------------------

section(u"Zero handling")
ok(u"0  dec->bin  == 0",                  convert(u"0", 10,  2) == u"0")
ok(u"0  dec->hex  == 0",                  convert(u"0", 10, 16) == u"0")
ok(u"0  dec->b36  == 0",                  convert(u"0", 10, 36) == u"0")
ok(u"0  bin->dec  == 0",                  convert(u"0",  2, 10) == u"0")
ok(u"from_int(0,  2) == '0'",             from_int(0,  2) == u"0")
ok(u"from_int(0, 16) == '0'",             from_int(0, 16) == u"0")
ok(u"from_int(0, 36) == '0'",             from_int(0, 36) == u"0")

# ---------------------------------------------------------------------------
# 3. Boundary bases (2 and 36)
# ---------------------------------------------------------------------------

section(u"Boundary bases: base 2 and base 36")
ok(u"to_int('1',  2)   == 1",             to_int(u"1",   2) == 1)
ok(u"to_int('10', 2)   == 2",             to_int(u"10",  2) == 2)
ok(u"from_int(1,  2)   == '1'",           from_int(1,  2) == u"1")
ok(u"from_int(2,  2)   == '10'",          from_int(2,  2) == u"10")
ok(u"to_int('Z',  36)  == 35",            to_int(u"Z",  36) == 35)
ok(u"from_int(35, 36)  == 'Z'",           from_int(35, 36) == u"Z")

# ---------------------------------------------------------------------------
# 4. Output is always uppercase
# ---------------------------------------------------------------------------

section(u"Output is always uppercase")
ok(u"hex output uppercase",               convert(u"255",   10, 16) == u"FF")
ok(u"b36 output uppercase",               convert(u"26716", 10, 36) == u"KM4")
ok(u"from_int(255, 16) uppercase",        from_int(255, 16) == u"FF")

# ---------------------------------------------------------------------------
# 5. Return type is always text (unicode) — Py2/Py3 consistency
#    This is the bug fixed during review: str(value) in the old base-10
#    fast path returned bytes under Python 2.
# ---------------------------------------------------------------------------

section(u"Return type consistency (text, not bytes) — Py2/Py3")
text_type = type(u"")
ok(u"from_int(255, 10) is text",          isinstance(from_int(255, 10), text_type))
ok(u"from_int(255, 16) is text",          isinstance(from_int(255, 16), text_type))
ok(u"from_int(0,   10) is text",          isinstance(from_int(0,   10), text_type))
ok(u"from_int(1,    2) is text",          isinstance(from_int(1,    2), text_type))
ok(u"convert() result is text",           isinstance(convert(u"FF", 16, 10), text_type))

# ---------------------------------------------------------------------------
# 6. Invalid base values
# ---------------------------------------------------------------------------

section(u"Invalid base values")
raises(u"base 1  rejected (to_int)",      ValueError, to_int,    u"1",  1)
raises(u"base 37 rejected (to_int)",      ValueError, to_int,    u"1", 37)
raises(u"base 0  rejected (to_int)",      ValueError, to_int,    u"1",  0)
raises(u"base 1  rejected (from_int)",    ValueError, from_int,   1,    1)
raises(u"base 37 rejected (from_int)",    ValueError, from_int,   1,   37)
raises(u"base 0  rejected (from_int)",    ValueError, from_int,   1,    0)

# ---------------------------------------------------------------------------
# 7. Empty input
# ---------------------------------------------------------------------------

section(u"Empty input")
raises(u"empty string (to_int)",          ValueError, to_int,   u"",   10)
raises(u"empty string (convert)",         ValueError, convert,  u"",   10, 16)

# ---------------------------------------------------------------------------
# 8. Signed input — both + and - rejected symmetrically
#    Bug fixed: original code only checked for '-'; '+' slipped through.
# ---------------------------------------------------------------------------

section(u"Signed input rejected symmetrically")
raises(u"negative '-1' (to_int)",         ValueError, to_int,   u"-1",   10)
raises(u"positive '+1' (to_int)",         ValueError, to_int,   u"+1",   10)
raises(u"negative via convert",           ValueError, convert,  u"-255", 10, 16)
raises(u"positive via convert",           ValueError, convert,  u"+255", 10, 16)

# ---------------------------------------------------------------------------
# 9. Surrounding whitespace rejected explicitly
#    Bug fixed: original code inherited int()'s silent whitespace tolerance.
# ---------------------------------------------------------------------------

section(u"Surrounding whitespace rejected")
raises(u"leading space",                  ValueError, to_int,   u" 1",   10)
raises(u"trailing space",                 ValueError, to_int,   u"1 ",   10)
raises(u"both sides",                     ValueError, to_int,   u" 1 ",  10)
raises(u"tab character",                  ValueError, to_int,   u"\t1",  10)
raises(u"newline character",              ValueError, to_int,   u"1\n",  10)

# ---------------------------------------------------------------------------
# 10. Invalid digit reporting — offset in error message
#     Improvement: old code reported the whole string; new code reports
#     the exact offset and character of the first bad digit.
# ---------------------------------------------------------------------------

section(u"Invalid digit — offset and character reporting")


def _err(fn, *args):
    try:
        fn(*args)
        return u""
    except ValueError as e:
        return u"{0}".format(e)


err_G_b16  = _err(to_int, u"G",   16)   # G is invalid in hex
err_1G_b16 = _err(to_int, u"1G",  16)   # G at offset 1
err_2_b2   = _err(to_int, u"2",    2)   # 2 invalid in binary at offset 0

ok(u"'G' base-16: offset 0 in message",   u"offset 0" in err_G_b16)
ok(u"'G' base-16: char G in message",     u"G" in err_G_b16)
ok(u"'1G' base-16: offset 1 in message",  u"offset 1" in err_1G_b16)
ok(u"'1G' base-16: char G in message",    u"G" in err_1G_b16)
ok(u"'2' base-2: offset 0 in message",    u"offset 0" in err_2_b2)

# ---------------------------------------------------------------------------
# 11. Negative value into from_int
# ---------------------------------------------------------------------------

section(u"Negative value into from_int")
raises(u"from_int(-1, 10) rejected",      ValueError, from_int, -1, 10)
raises(u"from_int(-1,  2) rejected",      ValueError, from_int, -1,  2)

# ---------------------------------------------------------------------------
# 12. main() exit codes via argv injection
#     Improvement: main(argv=None) pattern makes this testable without
#     subprocess; original main() read sys.argv directly.
# ---------------------------------------------------------------------------

section(u"main() exit codes via argv injection")
ok(u"valid conversion exits 0",           main([u"FF", u"16", u"10"]) == 0)
ok(u"invalid digit exits 1",              main([u"G",  u"16", u"10"]) == 1)
ok(u"bad base (non-int) exits 1",         main([u"FF", u"xx", u"10"]) == 1)
ok(u"out-of-range base exits 1",          main([u"FF", u"16", u"37"]) == 1)
ok(u"too few args exits 1",               main([u"FF", u"16"])         == 1)
ok(u"too many args exits 1",              main([u"FF", u"16", u"10", u"x"]) == 1)
ok(u"--help exits 0",                     main([u"--help"])            == 0)
ok(u"-h exits 0",                         main([u"-h"])                == 0)
ok(u"no args exits 1",                    main([])                     == 1)
ok(u"signed input exits 1",               main([u"+255", u"10", u"16"]) == 1)
ok(u"whitespace input exits 1",           main([u" 255", u"10", u"16"]) == 1)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(u"\n" + u"=" * 54)
print(u"Results: {0} passed, {1} failed".format(_PASS, _FAIL))
if _FAIL:
    sys.exit(1)
else:
    sys.exit(0)
