# ---------------------------------------------------------------------------
# UmerOS — H173 regression tests
#
# `mnt/fstab.py:_parse_line` called ``int()`` on the `dump` and fsck
# `passno` columns without a guard.  A single non-numeric value raised an
# uncaught ``ValueError`` out of ``Fstab.from_file()`` /
# ``Fstab.from_string()``, aborting the whole parse loop so every entry
# after the bad line was silently dropped.
#
# These tests pin the fix: the row is kept, the bad field degrades to 0,
# and the loop keeps going.
# ---------------------------------------------------------------------------

import logging
import os
import tempfile

import pytest

from mnt.fstab import (
    Fstab,
    FstabEntry,
    _parse_advisory_int,
    _parse_line,
    make_user_mount,
)

# Four clean rows bracketing one malformed row.  Pre-fix only the two
# entries *above* the bad line survived.
GOOD_ABOVE = "/dev/sda1 / ext4 defaults 0 1"
MALFORMED_DUMP = "/dev/sdb1 /mnt/usb vfat defaults junk 2"
MALFORMED_PASS = "/dev/sdc1 /mnt/last ext4 defaults 0 junk"
GOOD_BELOW = "/dev/sdd1 /mnt/data ext4 defaults 1 2"

MULTI = "\n".join(
    ["# /etc/fstab", GOOD_ABOVE, MALFORMED_DUMP, MALFORMED_PASS, GOOD_BELOW]
)


@pytest.fixture
def fstab():
    return Fstab.from_string(MULTI)


# -- the parse must survive ------------------------------------------------


def test_entry_after_a_malformed_row_is_not_lost(fstab):
    """The core bug: entries after the bad line were silently dropped."""
    points = [e.mount_point for e in fstab.entries]
    assert points == ["/", "/mnt/usb", "/mnt/last", "/mnt/data"]


def test_entry_count_is_complete(fstab):
    assert len(fstab.entries) == 4


def test_clean_rows_are_untouched(fstab):
    root = fstab.find_by_mount("/")
    assert (root.dump, root.pass_num) == (0, 1)
    data = fstab.find_by_mount("/mnt/data")
    assert (data.dump, data.pass_num) == (1, 2)


def test_comments_are_preserved(fstab):
    assert fstab._comments == ["# /etc/fstab"]


def test_no_exception_is_raised_directly():
    """``_parse_line`` used to raise; it must now always return an entry."""
    entry = _parse_line(MALFORMED_DUMP, line_num=2)
    assert isinstance(entry, FstabEntry)


# -- the malformed fields degrade to 0 -------------------------------------


def test_bad_dump_field_becomes_zero(fstab):
    assert fstab.find_by_mount("/mnt/usb").dump == 0


def test_bad_pass_field_becomes_zero(fstab):
    assert fstab.find_by_mount("/mnt/last").pass_num == 0


def test_good_field_on_a_bad_row_is_kept(fstab):
    """Only the offending column degrades -- its sibling survives."""
    bad = fstab.find_by_mount("/mnt/usb")
    assert bad.dump == 0
    assert bad.pass_num == 2


def test_both_fields_bad(fstab):
    entry = _parse_line("/dev/x /mnt/both ext4 defaults a b", line_num=7)
    assert (entry.dump, entry.pass_num) == (0, 0)


def test_missing_optional_fields_still_default_to_zero():
    entry = _parse_line("/dev/x /mnt/now ext4 defaults", line_num=1)
    assert (entry.dump, entry.pass_num) == (0, 0)


@pytest.mark.parametrize(
    "value",
    ["junk", "", "0x10", "1e3", "  ", "None", "++", "1,2", "-", "nan"],
)
def test_parse_advisory_int_rejects_nonsense(value):
    assert _parse_advisory_int(value, "dump", 1) == 0


def test_parse_advisory_int_accepts_numerals():
    assert _parse_advisory_int("0", "dump", 1) == 0
    assert _parse_advisory_int("1", "dump", 1) == 1
    assert _parse_advisory_int("  7  ", "dump", 1) == 7
    assert _parse_advisory_int("+3", "dump", 1) == 3


def test_parse_advisory_int_tolerates_none():
    """``None`` (a truncated row) must not raise either."""
    assert _parse_advisory_int(None, "dump", 1) == 0


def test_parse_advisory_int_reports_the_offending_value(caplog):
    with caplog.at_level(logging.WARNING, logger="UmerOS.Mnt.Fstab"):
        assert _parse_advisory_int("junk", "dump", 42) == 0
    msg = caplog.text
    assert "line 42" in msg
    assert "dump" in msg
    assert "junk" in msg


def test_degradation_is_logged_as_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="UmerOS.Mnt.Fstab"):
        Fstab.from_string(MALFORMED_DUMP)
    assert "not an integer" in caplog.text


def test_clean_row_does_not_log_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="UmerOS.Mnt.Fstab"):
        Fstab.from_string(GOOD_ABOVE)
    assert "not an integer" not in caplog.text


# -- round-trip and downstream behaviour -----------------------------------


def test_malformed_row_round_trips_verbatim(fstab):
    out = fstab.to_string()
    reparsed = Fstab.from_string(out)
    assert len(reparsed.entries) == 4
    assert reparsed.find_by_mount("/mnt/usb").dump == 0
    assert reparsed.find_by_mount("/mnt/last").pass_num == 0


def test_fsck_order_still_works_with_degraded_fields(fstab):
    """pass=0 (degraded) sorts last, exactly like an explicit 0."""
    order = [e.mount_point for e in fstab.find_by_fsck_order()]
    assert order[-1] == "/mnt/last"  # dump/passno degraded to 0 -> skipped last
    assert set(order[:-1]) == {"/", "/mnt/usb", "/mnt/data"}
    assert order[0] == "/"  # pass_num == 1 sorts first


def test_malformed_row_is_still_queryable(fstab):
    """Degrading the field must not also degrade the row."""
    bad = fstab.find_by_mount("/mnt/usb")
    assert bad.device == "/dev/sdb1"
    assert bad.fstype == "vfat"
    assert bad.options == "defaults"
    assert bad._raw_line == MALFORMED_DUMP


def test_user_mount_helper_still_parses_cleanly():
    entry = make_user_mount("/dev/fd0", "/mnt/flop", "msdos")
    reparsed = _parse_line(entry.to_line(), line_num=1)
    assert reparsed.device == "/dev/fd0"
    assert isinstance(reparsed.dump, int)
    assert isinstance(reparsed.pass_num, int)


def test_from_file_survives_a_malformed_row():
    """Same loop, different entry point -- ``from_file`` must survive too."""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "fstab")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(MULTI + "\n")
        f = Fstab.from_file(p)
        assert len(f.entries) == 4


def test_a_row_of_garbage_after_good_rows():
    text = "\n".join([GOOD_ABOVE, GOOD_BELOW, "/junk", "x", "y"])
    # "x" and "y" are too few fields -> skipped with a warning, not raised.
    f = Fstab.from_string(text)
    assert [e.mount_point for e in f.entries] == ["/", "/mnt/data"]
