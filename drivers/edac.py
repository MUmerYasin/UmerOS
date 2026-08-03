"""
UmerOS EDAC Framework
=====================
Linux kernel Error Detection And Correction (EDAC) framework.
Implements memory controllers, DIMMs, channels, error reporting,
error thresholds, and EDAC policies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EdacErrorType:
    """Type of memory error"""
    name: str
    severity: str  # "corrected", "uncorrected", "fatal"
    description: str


ERROR_CE = EdacErrorType("CE", "corrected", "Corrected Error - single bit")
ERROR_UE = EdacErrorType("UE", "uncorrected", "Uncorrected Error - multi bit")
ERROR_FE = EdacErrorType("FE", "fatal", "Fatal Error - multiple bits")
ERROR_DMCE = EdacErrorType("DMCE", "corrected", "Data Memory CE")
ERROR_DUCE = EdacErrorType("DUCE", "uncorrected", "Data Memory UE")
ERROR_BUSCE = EdacErrorType("BUSCE", "corrected", "Bus Error CE")
ERROR_BUSUE = EdacErrorType("BUSUE", "uncorrected", "Bus Error UE")

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------

_mcs: dict[int, EdacMc] = {}
_mc_counter: int = 0


def _next_mc_id() -> int:
    global _mc_counter
    _mc_counter += 1
    return _mc_counter


def _get_mc(mc_id: int) -> EdacMc:
    mc = _mcs.get(mc_id)
    if mc is None:
        raise KeyError(f"Memory controller {mc_id} not found")
    return mc


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EdacErrorRecord:
    """Single error record"""
    timestamp: float
    error_type: EdacErrorType
    dimm: str  # e.g. "dimm0", "dimm1"
    channel: int  # memory channel
    rank: int  # memory rank
    page: int  # physical page address
    offset: int  # offset within page
    count: int = 1  # error count
    grain: int = 1  # error granularity (bytes)
    message: str = ""


@dataclass
class EdacDimm:
    """DIMM (Dual Inline Memory Module)"""
    id: int
    label: str
    memory_type: str  # "DDR3", "DDR4", "DDR5"
    size_mb: int
    num_rank: int
    num_row: int
    num_col: int
    is_populated: bool = True
    error_count_corrected: int = 0
    error_count_uncorrected: int = 0


@dataclass
class EdacChannel:
    """Memory channel"""
    id: int
    label: str  # "ch0", "ch1"
    dimms: list[EdacDimm] = field(default_factory=list)


@dataclass
class EdacMc:
    """Memory controller"""
    id: int
    name: str
    channels: list[EdacChannel] = field(default_factory=list)
    is_active: bool = True
    total_errors: int = 0
    corrected_errors: int = 0
    uncorrected_errors: int = 0
    ce_count: int = 0  # corrected error count
    ue_count: int = 0  # uncorrected error count
    panic_on_ue: bool = False
    log_ue: bool = True
    log_ce: bool = True
    error_log: list[EdacErrorRecord] = field(default_factory=list)  # recent errors


@dataclass
class EdacPolicy:
    """EDAC policy configuration"""
    name: str
    check_interval_sec: float = 10.0
    poll_count: int = 1000
    panic_on_ue: bool = False
    log_ce: bool = True
    log_ue: bool = True
    ce_threshold: int = 100  # log CE every N errors
    ue_threshold: int = 1  # log every UE
    disable_ce_poll: bool = False
    disable_ue_poll: bool = False


# ---------------------------------------------------------------------------
# Registration functions
# ---------------------------------------------------------------------------


def edac_mc_register(name: str, num_channels: int) -> int:
    """Register a memory controller"""
    mc_id = _next_mc_id()
    mc = EdacMc(id=mc_id, name=name)
    for ch_id in range(num_channels):
        mc.channels.append(EdacChannel(id=ch_id, label=f"ch{ch_id}"))
    _mcs[mc_id] = mc
    return mc_id


def edac_mc_unregister(mc_id: int) -> None:
    """Unregister memory controller"""
    _mcs.pop(mc_id, None)


def edac_mc_add_dimm(
    mc_id: int,
    channel_id: int,
    label: str,
    memory_type: str,
    size_mb: int,
    num_rank: int = 1,
    num_row: int = 1024,
    num_col: int = 64,
) -> EdacDimm:
    """Add DIMM to memory controller"""
    mc = _get_mc(mc_id)
    if channel_id >= len(mc.channels):
        raise IndexError(f"Channel {channel_id} does not exist on MC {mc_id}")
    ch = mc.channels[channel_id]
    dimm = EdacDimm(
        id=len(ch.dimms),
        label=label,
        memory_type=memory_type,
        size_mb=size_mb,
        num_rank=num_rank,
        num_row=num_row,
        num_col=num_col,
    )
    ch.dimms.append(dimm)
    return dimm


# ---------------------------------------------------------------------------
# Error reporting
# ---------------------------------------------------------------------------


def edac_mc_report_error(
    mc_id: int,
    error_type: EdacErrorType,
    dimm_label: str = "",
    channel: int = 0,
    rank: int = 0,
    page: int = 0,
    offset: int = 0,
    grain: int = 1,
    message: str = "",
) -> EdacErrorRecord:
    """Report an error - like edac_mc_handle_error()"""
    mc = _get_mc(mc_id)
    record = EdacErrorRecord(
        timestamp=time.time(),
        error_type=error_type,
        dimm=dimm_label,
        channel=channel,
        rank=rank,
        page=page,
        offset=offset,
        grain=grain,
        message=message,
    )
    mc.total_errors += 1
    mc.error_log.append(record)

    if error_type.severity == "corrected":
        mc.corrected_errors += 1
        mc.ce_count += 1
        # Update per-DIMM counter
        _update_dimm_counter(mc, channel, dimm_label, corrected=True)
        if mc.log_ce and (mc.ce_count % max(1, _get_policy(mc_id).ce_threshold) == 0):
            print(f"  [EDAC] MC{mc_id}: CE threshold reached: count={mc.ce_count}")
    elif error_type.severity in ("uncorrected", "fatal"):
        mc.uncorrected_errors += 1
        mc.ue_count += 1
        _update_dimm_counter(mc, channel, dimm_label, corrected=False)
        if mc.log_ue:
            print(f"  [EDAC] MC{mc_id}: UE reported: {error_type.name} {message or ''}")
        if mc.panic_on_ue:
            print(f"  [EDAC] PANIC: uncorrected error on MC{mc_id}!")

    return record


def _update_dimm_counter(
    mc: EdacMc, channel: int, dimm_label: str, *, corrected: bool
) -> None:
    """Increment per-DIMM error counter."""
    if channel >= len(mc.channels):
        return
    ch = mc.channels[channel]
    for dimm in ch.dimms:
        if not dimm_label or dimm.label == dimm_label:
            if corrected:
                dimm.error_count_corrected += 1
            else:
                dimm.error_count_uncorrected += 1


# ---------------------------------------------------------------------------
# Error summaries
# ---------------------------------------------------------------------------


def edac_mc_get_error_summary(mc_id: int) -> dict[str, Any]:
    """Get error summary for a memory controller"""
    mc = _get_mc(mc_id)
    return {
        "mc_id": mc.id,
        "name": mc.name,
        "total_errors": mc.total_errors,
        "corrected_errors": mc.corrected_errors,
        "uncorrected_errors": mc.uncorrected_errors,
        "ce_count": mc.ce_count,
        "ue_count": mc.ue_count,
        "channels": len(mc.channels),
        "dimms": sum(len(ch.dimms) for ch in mc.channels),
        "error_log_size": len(mc.error_log),
    }


def edac_mc_get_ce_summary(mc_id: int) -> dict[str, Any]:
    """Get corrected error summary"""
    mc = _get_mc(mc_id)
    per_dimm: dict[str, int] = {}
    for ch in mc.channels:
        for dimm in ch.dimms:
            if dimm.error_count_corrected > 0:
                per_dimm[dimm.label] = dimm.error_count_corrected
    return {
        "mc_id": mc.id,
        "ce_count": mc.ce_count,
        "per_dimm": per_dimm,
    }


def edac_mc_get_ue_summary(mc_id: int) -> dict[str, Any]:
    """Get uncorrected error summary"""
    mc = _get_mc(mc_id)
    per_dimm: dict[str, int] = {}
    for ch in mc.channels:
        for dimm in ch.dimms:
            if dimm.error_count_uncorrected > 0:
                per_dimm[dimm.label] = dimm.error_count_uncorrected
    return {
        "mc_id": mc.id,
        "ue_count": mc.ue_count,
        "per_dimm": per_dimm,
    }


# ---------------------------------------------------------------------------
# Policy management
# ---------------------------------------------------------------------------


_policies: dict[int, EdacPolicy] = {}


def edac_mc_set_policy(mc_id: int, policy: EdacPolicy) -> None:
    """Set EDAC policy"""
    mc = _get_mc(mc_id)
    _policies[mc_id] = policy
    mc.panic_on_ue = policy.panic_on_ue
    mc.log_ce = policy.log_ce
    mc.log_ue = policy.log_ue


def edac_mc_get_policy(mc_id: int) -> EdacPolicy:
    """Get EDAC policy"""
    if mc_id not in _policies:
        _policies[mc_id] = EdacPolicy(name="default")
    return _policies[mc_id]


def _get_policy(mc_id: int) -> EdacPolicy:
    return edac_mc_get_policy(mc_id)


# ---------------------------------------------------------------------------
# Counter management
# ---------------------------------------------------------------------------


def edac_mc_reset_counters(mc_id: int) -> None:
    """Reset error counters"""
    mc = _get_mc(mc_id)
    mc.total_errors = 0
    mc.corrected_errors = 0
    mc.uncorrected_errors = 0
    mc.ce_count = 0
    mc.ue_count = 0
    for ch in mc.channels:
        for dimm in ch.dimms:
            dimm.error_count_corrected = 0
            dimm.error_count_uncorrected = 0
    mc.error_log.clear()


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------


def edac_mc_poll_errors(mc_id: int | None = None) -> dict[int, dict[str, int]]:
    """Poll for errors (periodic check)

    Returns a dict mapping mc_id -> {"ce": N, "ue": N} for each controller
    that has accumulated errors since the last poll (simulated by returning
    the current snapshot).
    """
    results: dict[int, dict[str, int]] = {}
    targets = [mc_id] if mc_id is not None else list(_mcs.keys())
    for mid in targets:
        mc = _mcs.get(mid)
        if mc is None or not mc.is_active:
            continue
        policy = _get_policy(mid)
        if policy.disable_ce_poll and policy.disable_ue_poll:
            continue
        results[mid] = {
            "ce": mc.ce_count if not policy.disable_ce_poll else 0,
            "ue": mc.ue_count if not policy.disable_ue_poll else 0,
        }
    return results


# ---------------------------------------------------------------------------
# Threshold checks
# ---------------------------------------------------------------------------


def edac_mc_ce_threshold_reached(mc_id: int) -> bool:
    """Check if CE threshold reached"""
    mc = _get_mc(mc_id)
    policy = _get_policy(mc_id)
    return mc.ce_count >= policy.ce_threshold


def edac_mc_ue_threshold_reached(mc_id: int) -> bool:
    """Check if UE threshold reached"""
    mc = _get_mc(mc_id)
    policy = _get_policy(mc_id)
    return mc.ue_count >= policy.ue_threshold


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def edac_mc_get_all() -> list[EdacMc]:
    """Get all memory controllers"""
    return list(_mcs.values())


def edac_mc_dump(mc_id: int) -> str:
    """Dump memory controller info"""
    mc = _get_mc(mc_id)
    lines: list[str] = []
    lines.append(f"Memory Controller {mc.id}: {mc.name}")
    lines.append(f"  Active: {mc.is_active}")
    lines.append(f"  Panic on UE: {mc.panic_on_ue}")
    lines.append(f"  Total errors: {mc.total_errors}")
    lines.append(f"  CE count: {mc.ce_count}")
    lines.append(f"  UE count: {mc.ue_count}")
    lines.append(f"  Channels: {len(mc.channels)}")
    for ch in mc.channels:
        lines.append(f"    Channel {ch.id} ({ch.label}): {len(ch.dimms)} DIMMs")
        for dimm in ch.dimms:
            lines.append(
                f"      DIMM {dimm.id} ({dimm.label}): {dimm.memory_type} "
                f"{dimm.size_mb}MB, ranks={dimm.num_rank}, "
                f"rows={dimm.num_row}, cols={dimm.num_col}, "
                f"populated={dimm.is_populated}, "
                f"CE={dimm.error_count_corrected}, UE={dimm.error_count_uncorrected}"
            )
    if mc.error_log:
        lines.append(f"  Recent errors ({len(mc.error_log)}):")
        for rec in mc.error_log[-5:]:
            lines.append(
                f"    [{rec.error_type.name}] dimm={rec.dimm} ch={rec.channel} "
                f"rank={rec.rank} page=0x{rec.page:x} offset=0x{rec.offset:x} "
                f"grain={rec.grain} msg={rec.message}"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Built-in drivers
# ---------------------------------------------------------------------------


class SimEdacDriver:
    """Simulated EDAC driver for testing"""

    def __init__(self) -> None:
        self.name = "sim-edac"
        self.version = "1.0"

    def create_mc(self, name: str, channels: int) -> int:
        """Create simulated memory controller"""
        mc_id = edac_mc_register(name, channels)
        # Create DDR4 DIMMs
        for ch in range(channels):
            edac_mc_add_dimm(mc_id, ch, f"dimm{ch}", "DDR4", 8192, num_rank=2)
        return mc_id

    def inject_ce(self, mc_id: int, dimm_label: str = "", count: int = 1) -> None:
        """Inject corrected errors"""
        for _ in range(count):
            edac_mc_report_error(mc_id, ERROR_CE, dimm_label)

    def inject_ue(self, mc_id: int, dimm_label: str = "", count: int = 1) -> None:
        """Inject uncorrected errors"""
        for _ in range(count):
            edac_mc_report_error(mc_id, ERROR_UE, dimm_label)


class EccEdacDriver:
    """ECC-based EDAC driver"""

    def __init__(self) -> None:
        self.name = "ecc-edac"
        self.version = "1.0"


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def demo() -> None:
    """Interactive demonstration of the UmerOS EDAC Framework."""
    print()
    print("=" * 72)
    print("  UmerOS EDAC Framework  --  Linux EDAC Demo")
    print("=" * 72)
    print()

    # -- 1. Create memory controllers -------------------------------------------

    print("[1] Creating memory controllers ...")
    mc0 = edac_mc_register("intel_edac_mc0", num_channels=2)
    mc1 = edac_mc_register("amd_edac_mc0", num_channels=4)
    print(f"  MC0 id={mc0}, MC1 id={mc1}")
    print()

    # -- 2. Add DIMMs -----------------------------------------------------------

    print("[2] Adding DIMMs ...")
    edac_mc_add_dimm(mc0, 0, "dimm0", "DDR4", 8192, num_rank=2)
    edac_mc_add_dimm(mc0, 1, "dimm1", "DDR4", 8192, num_rank=2)
    edac_mc_add_dimm(mc1, 0, "dimm0", "DDR5", 16384, num_rank=2)
    edac_mc_add_dimm(mc1, 1, "dimm1", "DDR5", 16384, num_rank=2)
    edac_mc_add_dimm(mc1, 2, "dimm2", "DDR5", 16384, num_rank=2)
    edac_mc_add_dimm(mc1, 3, "dimm3", "DDR5", 16384, num_rank=2)
    print("  MC0: 2x DDR4 8GB DIMMs")
    print("  MC1: 4x DDR5 16GB DIMMs")
    print()

    # -- 3. Set policies --------------------------------------------------------

    print("[3] Setting EDAC policies ...")
    policy0 = EdacPolicy(
        name="strict",
        check_interval_sec=1.0,
        panic_on_ue=True,
        log_ce=True,
        log_ue=True,
        ce_threshold=50,
        ue_threshold=1,
    )
    policy1 = EdacPolicy(
        name="relaxed",
        check_interval_sec=30.0,
        panic_on_ue=False,
        log_ce=True,
        log_ue=True,
        ce_threshold=100,
        ue_threshold=3,
    )
    edac_mc_set_policy(mc0, policy0)
    edac_mc_set_policy(mc1, policy1)
    p0 = edac_mc_get_policy(mc0)
    p1 = edac_mc_get_policy(mc1)
    print(f"  MC0 policy: {p0.name}, panic_on_ue={p0.panic_on_ue}, ce_threshold={p0.ce_threshold}")
    print(f"  MC1 policy: {p1.name}, panic_on_ue={p1.panic_on_ue}, ce_threshold={p1.ce_threshold}")
    print()

    # -- 4. Inject corrected errors ---------------------------------------------

    print("[4] Injecting corrected errors ...")
    driver = SimEdacDriver()
    driver.inject_ce(mc0, "dimm0", count=5)
    driver.inject_ce(mc0, "dimm1", count=3)
    driver.inject_ce(mc1, "dimm0", count=10)
    driver.inject_ce(mc1, "dimm2", count=7)
    print(f"  MC0 CE count: {_mcs[mc0].ce_count}")
    print(f"  MC1 CE count: {_mcs[mc1].ce_count}")
    print()

    # -- 5. Inject uncorrected errors -------------------------------------------

    print("[5] Injecting uncorrected errors ...")
    driver.inject_ue(mc0, "dimm0", count=2)
    driver.inject_ue(mc1, "dimm1", count=1)
    print(f"  MC0 UE count: {_mcs[mc0].ue_count}")
    print(f"  MC1 UE count: {_mcs[mc1].ue_count}")
    print()

    # -- 6. Error summaries -----------------------------------------------------

    print("[6] Error summaries ...")
    summary0 = edac_mc_get_error_summary(mc0)
    summary1 = edac_mc_get_error_summary(mc1)
    print(f"  MC0: {summary0}")
    print(f"  MC1: {summary1}")
    print()

    ce0 = edac_mc_get_ce_summary(mc0)
    ue0 = edac_mc_get_ue_summary(mc0)
    print(f"  MC0 CE summary: {ce0}")
    print(f"  MC0 UE summary: {ue0}")
    print()

    # -- 7. Threshold checks ----------------------------------------------------

    print("[7] Threshold checks ...")
    print(f"  MC0 CE threshold reached: {edac_mc_ce_threshold_reached(mc0)}")
    print(f"  MC0 UE threshold reached: {edac_mc_ue_threshold_reached(mc0)}")
    print(f"  MC1 CE threshold reached: {edac_mc_ce_threshold_reached(mc1)}")
    print(f"  MC1 UE threshold reached: {edac_mc_ue_threshold_reached(mc1)}")
    print()

    # -- 8. Poll errors ---------------------------------------------------------

    print("[8] Polling errors ...")
    poll_results = edac_mc_poll_errors()
    for mid, counts in poll_results.items():
        print(f"  MC{mid}: CE={counts['ce']}, UE={counts['ue']}")
    print()

    # -- 9. Error log with timestamps -------------------------------------------

    print("[9] Error log (MC0, last 5 entries) ...")
    for rec in _mcs[mc0].error_log[-5:]:
        ts = time.strftime("%H:%M:%S", time.localtime(rec.timestamp))
        print(
            f"  [{ts}] {rec.error_type.name:4s} dimm={rec.dimm} "
            f"ch={rec.channel} rank={rec.rank}"
        )
    print()

    # -- 10. Dump memory controller ---------------------------------------------

    print("[10] Dump MC0 ...")
    print(edac_mc_dump(mc0))
    print()

    # -- 11. Reset counters -----------------------------------------------------

    print("[11] Resetting MC0 counters ...")
    edac_mc_reset_counters(mc0)
    print(f"  MC0 after reset: CE={_mcs[mc0].ce_count}, UE={_mcs[mc0].ue_count}")
    print()

    # -- 12. List all memory controllers ----------------------------------------

    print("[12] All memory controllers ...")
    all_mcs = edac_mc_get_all()
    for mc in all_mcs:
        dimm_count = sum(len(ch.dimms) for ch in mc.channels)
        print(f"  MC{mc.id}: {mc.name}, channels={len(mc.channels)}, dimms={dimm_count}")
    print()

    # -- 13. Simulated driver with more injections ------------------------------

    print("[13] SimEdacDriver: bulk error injection ...")
    driver2 = SimEdacDriver()
    mc2 = driver2.create_mc("sim_mc", channels=2)
    driver2.inject_ce(mc2, count=25)
    driver2.inject_ue(mc2, count=3)
    s = edac_mc_get_error_summary(mc2)
    print(f"  sim_mc: total={s['total_errors']}, CE={s['ce_count']}, UE={s['ue_count']}")
    print(f"  CE threshold reached: {edac_mc_ce_threshold_reached(mc2)}")
    print(f"  UE threshold reached: {edac_mc_ue_threshold_reached(mc2)}")
    print()

    # -- 14. Unregister ---------------------------------------------------------

    print("[14] Unregistering MC1 ...")
    edac_mc_unregister(mc1)
    remaining = edac_mc_get_all()
    print(f"  Remaining MCs: {[mc.id for mc in remaining]}")
    print()

    print("=" * 72)
    print("  Demo Complete")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo()
