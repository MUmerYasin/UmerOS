# ---------------------------------------------------------------------------
# UmerOS — H174 regression tests
#
# `mnt/fstab.py:to_string()` used to emit **all** comments as one hoisted
# block above **all** entries, so a mid-file note such as
# ``# --- removable media below ---`` lost the section it documented.  That
# was the residual defect after the H168 family, which had already stopped
# comments from being dropped outright.
#
# `Fstab._header` was also a dead attribute -- declared, read once, never
# assigned.
#
# These tests pin both halves: comments keep their position, and the dead
# attribute is gone.
# ---------------------------------------------------------------------------

import logging

import pytest

from mnt.fstab import Fstab, FstabEntry, _parse_line, make_fstab_entry

HEADER = "# /etc/fstab: managed by hand"
NOTE = "# --- removable media below ---"
TRAILING = "# swap goes at the end"

POSITIONED = "\n".join(
    [
        HEADER,
        "# see also fstab(5)",
        "",
        "/dev/sda1 / ext4 defaults 0 1",
        NOTE,
        "/dev/sdb1 /mnt/usb vfat defaults 0 0",
        "",
        TRAILING,
        "/dev/sdc1 none swap swap defaults 0 0",
    ]
)


@pytest.fixture
def fstab():
    return Fstab.from_string(POSITIONED)


def _lines(text):
    return [l for l in text.splitlines() if l.strip()]


def _line_of(lines, needle):
    return next(i for i, l in enumerate(lines) if needle in l)


# -- position is preserved -------------------------------------------------


def test_mid_file_comment_keeps_its_position(fstab):
    lines = _lines(fstab.to_string())
    comment = _line_of(lines, "removable media below")
    root = _line_of(lines, "/dev/sda1")
    entry = _line_of(lines, "/mnt/usb")
    assert root < comment < entry


def test_trailing_comment_keeps_its_position(fstab):
    lines = _lines(fstab.to_string())
    comment = _line_of(lines, "swap goes at the end")
    entry = _line_of(lines, "/dev/sdc1")
    assert comment < entry


def test_header_block_stays_at_the_top(fstab):
    lines = _lines(fstab.to_string())
    assert lines[0] == HEADER
    assert lines[1].startswith("# see also")


def test_no_comment_is_hoisted_above_the_first_entry(fstab):
    """Pre-fix, every comment came before every entry."""
    lines = _lines(fstab.to_string())
    first_entry = _line_of(lines, "/dev/sda1")
    assert first_entry == 2  # exactly the two header lines precede it


def test_comment_order_is_stable(fstab):
    lines = _lines(fstab.to_string())
    assert [l for l in lines if l.startswith("#")] == [
        HEADER,
        "# see also fstab(5)",
        NOTE,
        TRAILING,
    ]


# -- round-trip fidelity ---------------------------------------------------


def test_round_trip_is_idempotent(fstab):
    once = fstab.to_string()
    assert Fstab.from_string(once).to_string() == once


def test_round_trip_preserves_comments(fstab):
    reparsed = Fstab.from_string(fstab.to_string())
    assert reparsed._comments == fstab._comments


def test_round_trip_preserves_entries(fstab):
    reparsed = Fstab.from_string(fstab.to_string())
    assert [e.mount_point for e in reparsed.entries] == [
        e.mount_point for e in fstab.entries
    ]


def test_round_trip_from_file_survives_write(tmp_path, fstab):
    p = tmp_path / "fstab"
    p.write_text(fstab.to_string(), encoding="utf-8")
    again = Fstab.from_file(str(p))
    assert again._comments == fstab._comments


def test_empty_fstab_renders_empty():
    assert Fstab().to_string() == ""


def test_fstab_with_only_comments():
    f = Fstab.from_string("# just a note\n")
    assert f.to_string() == "# just a note\n"


# -- programmatic edits must not reorder sourced content --------------------


def test_added_entry_sinks_to_the_bottom(fstab):
    fstab.add(make_fstab_entry("/dev/sdd1", "/mnt/new", "ext4"))
    lines = _lines(fstab.to_string())
    assert _line_of(lines, "/dev/sdd1") == len(lines) - 1


def test_add_does_not_reorder_existing_lines(fstab):
    before = _lines(fstab.to_string())
    fstab.add(make_fstab_entry("/dev/sdd1", "/mnt/new", "ext4"))
    assert _lines(fstab.to_string())[: len(before)] == before


def test_add_does_not_displace_comments(fstab):
    before = fstab._comments[:]
    fstab.add(make_fstab_entry("/dev/sdd1", "/mnt/new", "ext4"))
    assert fstab._comments == before


def test_added_entry_reparse_keeps_comments(fstab):
    fstab.add(make_fstab_entry("/dev/sdd1", "/mnt/new", "ext4"))
    reparsed = Fstab.from_string(fstab.to_string())
    assert reparsed._comments == fstab._comments


def test_remove_does_not_orphan_its_comment():
    f = Fstab.from_string(
        "# header\n"
        "/dev/sda1 / ext4 defaults 0 1\n"
        "# usb\n"
        "/dev/sdb1 /mnt/usb vfat defaults 0 0\n"
    )
    f.remove("/mnt/usb")
    assert f._comments == ["# header", "# usb"]


# -- `_header` is gone (dead attribute removed) -----------------------------


def test_dead_header_attribute_is_removed(fstab):
    """``_header`` existed but was never assigned; a live header would be a lie."""
    assert not hasattr(fstab, "_header")


def test_header_block_is_not_reified_as_a_separate_field(fstab):
    """The header is just the first comments -- no duplicated storage."""
    assert not any(getattr(fstab, name, None) for name in ("_header", "header"))


def test_h173_and_h174_compose(fstab):
    """A malformed dump column and mispositioned comments are independent."""
    messy = Fstab.from_string(
        "# header\n"
        "/dev/sda1 / ext4 defaults 0 1\n"
        "# note\n"
        "/dev/sdb1 /mnt/usb vfat defaults junk 2\n"
        "/dev/sdc1 /mnt/last ext4 defaults 0 2\n"
    )
    assert len(messy.entries) == 3
    assert messy.find_by_mount("/mnt/usb").dump == 0
    lines = _lines(messy.to_string())
    assert _line_of(lines, "# note") == 2
    assert _line_of(lines, "/mnt/usb") == 3


def test_parse_line_still_independent_of_comment_tracking():
    """``_parse_line`` never saw comments; unchanged by H174."""
    entry = _parse_line("/dev/sda1 / ext4 defaults 0 1", line_num=1)
    assert isinstance(entry, FstabEntry)


def test_no_warning_for_clean_positioned_file(fstab, caplog):
    with caplog.at_level(logging.WARNING, logger="UmerOS.Mnt.Fstab"):
        fstab.to_string()
    assert "not an integer" not in caplog.text
