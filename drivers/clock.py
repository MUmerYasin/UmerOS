# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
UmerOS Clock Framework
======================
Kernel-like Common Clock Framework (CCF).
Implements clock providers, gates, muxes, dividers, PLLs,
and the full prepare/enable/disable lifecycle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Clock types
# ---------------------------------------------------------------------------

CLK_TYPE_FIXED = "fixed"
CLK_TYPE_GATE = "gate"
CLK_TYPE_MUX = "mux"
CLK_TYPE_DIV = "div"
CLK_TYPE_PLL = "pll"
CLK_TYPE_DIV_TABLE = "div_table"
CLK_TYPE_FIXED_FACTOR = "fixed_factor"
CLK_TYPE_COMPOSITE = "composite"

# ---------------------------------------------------------------------------
# Clock flags
# ---------------------------------------------------------------------------

CLK_SET_RATE_PARENT = 0x01
CLK_SET_RATE_NO_REPARENT = 0x02
CLK_SET_RATE_GATE = 0x04
CLK_SET_PARENT_GATE = 0x08
CLK_SET_RATE_UNCHANGED = 0x10
CLK_IGNORE_UNUSED = 0x20
CLK_GET_RATE_NOCACHE = 0x40
CLK_ENABLE_HAND_OFF = 0x80

# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------

_providers: dict[str, ClkProvider] = {}
_clocks: dict[str, Clk] = {}
_ref_counts: dict[str, int] = {}
_clk_get_users: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ClkRateRange:
    """Clock rate range (like struct clk_rate_range)."""

    min_rate: int = 0
    max_rate: int = 0


@dataclass
class ClkProvider:
    """Clock provider / clock chip."""

    name: str
    id: int
    clocks: dict[str, Clk] = field(default_factory=dict)
    _is_registered: bool = False

    def __post_init__(self) -> None:
        _providers[self.name] = self


@dataclass
class Clk:
    """Clock object (like struct clk)."""

    name: str
    parent: Optional[Clk] = None
    parent_name: str = ""
    rate: int = 0  # Hz
    accuracy: int = 0  # ppm
    phase: int = 0  # degrees
    prepare_count: int = 0
    enable_count: int = 0
    flags: int = 0
    clk_type: str = CLK_TYPE_GATE
    rate_range: ClkRateRange = field(default_factory=ClkRateRange)
    _is_prepared: bool = False
    _is_enabled: bool = False
    _ops: dict[str, Any] = field(default_factory=dict)
    _provider: Optional[ClkProvider] = None
    _fixed_mult: int = 1
    _fixed_div: int = 1
    _div_table: list[int] = field(default_factory=list)
    _mux_parents: list[str] = field(default_factory=list)
    _cached_rate: int = 0

    # -- helpers -----------------------------------------------------------

    def _resolve_parent(self) -> Optional[Clk]:
        if self.parent is not None:
            return self.parent
        if self.parent_name and self.parent_name in _clocks:
            self.parent = _clocks[self.parent_name]
            return self.parent
        return None


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def _register_clk(provider: ClkProvider, clk: Clk) -> None:
    """Register a single clock with the framework."""
    clk._provider = provider
    provider.clocks[clk.name] = clk
    _clocks[clk.name] = clk
    _ref_counts[clk.name] = 0
    _clk_get_users[clk.name] = 0


def _deregister_clk(provider: ClkProvider, clk: Clk) -> None:
    """Remove a clock from the framework."""
    provider.clocks.pop(clk.name, None)
    _clocks.pop(clk.name, None)
    _ref_counts.pop(clk.name, None)
    _clk_get_users.pop(clk.name, None)


# ---------------------------------------------------------------------------
# Clock registration API  (kernel-like)
# ---------------------------------------------------------------------------


def clk_register(
    provider: ClkProvider,
    name: str,
    rate: int,
    parent_name: str = "",
    flags: int = 0,
    clk_type: str = CLK_TYPE_GATE,
    *,
    fixed_mult: int = 1,
    fixed_div: int = 1,
    div_table: list[int] | None = None,
    mux_parents: list[str] | None = None,
) -> Clk:
    """Register a clock - like clk_register()."""
    if name in _clocks:
        raise ValueError(f"Clock '{name}' already registered")

    clk = Clk(
        name=name,
        rate=rate,
        parent_name=parent_name,
        flags=flags,
        clk_type=clk_type,
        _fixed_mult=fixed_mult,
        _fixed_div=fixed_div,
        _div_table=div_table or [],
        _mux_parents=mux_parents or [],
        _cached_rate=rate,
    )
    _register_clk(provider, clk)

    # Wire parent if it already exists
    if parent_name and parent_name in _clocks:
        clk.parent = _clocks[parent_name]

    return clk


def clk_unregister(provider_name: str, clock_name: str) -> None:
    """Unregister a clock."""
    provider = _providers.get(provider_name)
    if provider is None:
        raise KeyError(f"Provider '{provider_name}' not found")
    clk = provider.clocks.get(clock_name)
    if clk is None:
        raise KeyError(f"Clock '{clock_name}' not in provider '{provider_name}'")
    if clk.enable_count > 0 or clk.prepare_count > 0:
        raise RuntimeError(f"Cannot unregister active clock '{clock_name}'")
    _deregister_clk(provider, clk)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _get_clk(name: str) -> Clk:
    clk = _clocks.get(name)
    if clk is None:
        raise KeyError(f"Clock '{name}' not found")
    return clk


# ---------------------------------------------------------------------------
# Kernel clock API
# ---------------------------------------------------------------------------


def clk_get(dev_name: str, con_id: str = "") -> str:
    """Get clock - like clk_get(). Returns clock name for further calls."""
    target = con_id if con_id else dev_name
    if target not in _clocks:
        raise KeyError(f"Clock '{target}' not found")
    _clk_get_users[target] = _clk_get_users.get(target, 0) + 1
    return target


def clk_put(dev_name: str) -> None:
    """Put clock reference."""
    if dev_name in _clk_get_users and _clk_get_users[dev_name] > 0:
        _clk_get_users[dev_name] -= 1


def clk_prepare(clock_name: str) -> int:
    """Prepare clock - like clk_prepare(). Returns 0 on success."""
    clk = _get_clk(clock_name)
    if clk._is_prepared:
        return 0

    # Propagate prepare to parent
    parent = clk._resolve_parent()
    if parent and parent.prepare_count == 0 and not (clk.flags & CLK_SET_PARENT_GATE):
        clk_prepare(parent.name)

    clk.prepare_count += 1
    clk._is_prepared = True
    print(f"  [CLK] prepare '{clk.name}' (count={clk.prepare_count})")
    return 0


def clk_unprepare(clock_name: str) -> None:
    """Unprepare clock."""
    clk = _get_clk(clock_name)
    if clk.prepare_count == 0:
        return
    clk.prepare_count -= 1
    if clk.prepare_count == 0:
        clk._is_prepared = False
        # Unprepare children that were prepared on our behalf
        parent = clk._resolve_parent()
        if parent and parent.prepare_count > 0 and not (clk.flags & CLK_SET_PARENT_GATE):
            clk_unprepare(parent.name)
    print(f"  [CLK] unprepare '{clk.name}' (count={clk.prepare_count})")


def clk_enable(clock_name: str) -> int:
    """Enable clock - like clk_enable(). Returns 0 on success."""
    clk = _get_clk(clock_name)
    if not clk._is_prepared:
        raise RuntimeError(f"Cannot enable unprepared clock '{clock_name}'")
    if clk._is_enabled:
        clk.enable_count += 1
        return 0

    parent = clk._resolve_parent()
    if parent and not parent._is_enabled and not (clk.flags & CLK_SET_PARENT_GATE):
        clk_enable(parent.name)

    clk.enable_count += 1
    clk._is_enabled = True
    print(f"  [CLK] enable  '{clk.name}' (count={clk.enable_count})")
    return 0


def clk_disable(clock_name: str) -> None:
    """Disable clock."""
    clk = _get_clk(clock_name)
    if not clk._is_enabled:
        return
    clk.enable_count -= 1
    if clk.enable_count == 0:
        clk._is_enabled = False
        parent = clk._resolve_parent()
        if parent and parent.enable_count > 0 and not (clk.flags & CLK_SET_PARENT_GATE):
            clk_disable(parent.name)
    print(f"  [CLK] disable '{clk.name}' (count={clk.enable_count})")


# -- combined helpers -------------------------------------------------------


def clk_prepare_enable(clock_name: str) -> int:
    """Prepare and enable - like clk_prepare_enable()."""
    ret = clk_prepare(clock_name)
    if ret:
        return ret
    return clk_enable(clock_name)


def clk_disable_unprepare(clock_name: str) -> None:
    """Disable and unprepare."""
    clk_disable(clock_name)
    clk_unprepare(clock_name)


# ---------------------------------------------------------------------------
# Rate helpers
# ---------------------------------------------------------------------------


def _round_rate(rate: int, target: int) -> int:
    """Round to nearest multiple of *target*."""
    if target == 0:
        return rate
    return round(rate / target) * target


def clk_set_rate(clock_name: str, rate: int) -> int:
    """Set clock rate - like clk_set_rate(). Returns actual rate."""
    clk = _get_clk(clock_name)

    # Fixed clocks cannot change rate
    if clk.clk_type == CLK_TYPE_FIXED:
        print(f"  [CLK] set_rate '{clk.name}' blocked (fixed clock, rate={clk.rate})")
        return clk.rate

    # Clamp to range
    if clk.rate_range.max_rate and rate > clk.rate_range.max_rate:
        rate = clk.rate_range.max_rate
    if clk.rate_range.min_rate and rate < clk.rate_range.min_rate:
        rate = clk.rate_range.min_rate

    if clk.flags & CLK_SET_RATE_UNCHANGED:
        if rate != clk.rate:
            print(f"  [CLK] set_rate '{clk.name}' rejected (UNCHANGED flag, want={rate}, have={clk.rate})")
            return clk.rate

    old_rate = clk.rate
    new_rate = rate

    # Apply type-specific rounding
    if clk.clk_type == CLK_TYPE_FIXED_FACTOR:
        parent = clk._resolve_parent()
        if parent:
            new_rate = round(parent.rate * clk._fixed_mult / clk._fixed_div)
        else:
            new_rate = round(rate * clk._fixed_mult / clk._fixed_div)

    elif clk.clk_type == CLK_TYPE_DIV:
        parent = clk._resolve_parent()
        if parent and parent.rate:
            divisors = list(range(1, 64))  # linear divider 1..63
            best_div = min(divisors, key=lambda d: abs(parent.rate / d - rate))
            new_rate = parent.rate // best_div
        else:
            new_rate = rate

    elif clk.clk_type == CLK_TYPE_DIV_TABLE:
        parent = clk._resolve_parent()
        if parent and parent.rate and clk._div_table:
            best_div = min(clk._div_table, key=lambda d: abs(parent.rate / d - rate))
            new_rate = parent.rate // best_div
        else:
            new_rate = rate

    elif clk.clk_type == CLK_TYPE_PLL:
        parent = clk._resolve_parent()
        if parent:
            mult = max(1, round(rate / parent.rate))
            new_rate = parent.rate * mult
        else:
            new_rate = rate

    elif clk.clk_type == CLK_TYPE_MUX:
        # For mux, changing rate effectively changes parent
        new_rate = rate

    else:
        new_rate = rate

    # Propagate to parent if allowed
    if clk.flags & CLK_SET_RATE_PARENT:
        parent = clk._resolve_parent()
        if parent:
            clk_set_rate(parent.name, new_rate)

    clk.rate = new_rate
    clk._cached_rate = new_rate

    if new_rate != old_rate:
        print(f"  [CLK] set_rate '{clk.name}': {old_rate} -> {new_rate} Hz")
    else:
        print(f"  [CLK] set_rate '{clk.name}': unchanged at {new_rate} Hz")

    return new_rate


def clk_get_rate(clock_name: str) -> int:
    """Get clock rate - like clk_get_rate()."""
    clk = _get_clk(clock_name)

    if clk.flags & CLK_GET_RATE_NOCACHE:
        # Recalculate from parent chain
        parent = clk._resolve_parent()
        if parent:
            if clk.clk_type == CLK_TYPE_FIXED_FACTOR:
                return round(parent.rate * clk._fixed_mult / clk._fixed_div)
            return parent.rate

    return clk._cached_rate if clk._cached_rate else clk.rate


# ---------------------------------------------------------------------------
# Parent helpers
# ---------------------------------------------------------------------------


def clk_set_parent(clock_name: str, parent_name: str) -> int:
    """Set parent clock. Returns 0 on success."""
    clk = _get_clk(clock_name)
    if parent_name not in _clocks:
        raise KeyError(f"Parent clock '{parent_name}' not found")

    if clk.flags & CLK_SET_RATE_NO_REPARENT:
        print(f"  [CLK] set_parent '{clk.name}' -> '{parent_name}' rejected (NO_REPARENT)")
        return -1

    old_parent = clk.parent_name
    new_parent_clk = _clocks[parent_name]

    if clk.flags & CLK_SET_PARENT_GATE:
        # Gate before switch
        if clk._is_enabled:
            clk_disable(clock_name)

    clk.parent_name = parent_name
    clk.parent = new_parent_clk

    if clk.flags & CLK_SET_PARENT_GATE:
        # Un-gate after switch
        if clk._is_enabled:
            clk_enable(clock_name)

    # Recalculate rate from new parent
    if clk.clk_type == CLK_TYPE_FIXED_FACTOR:
        clk.rate = round(new_parent_clk.rate * clk._fixed_mult / clk._fixed_div)
        clk._cached_rate = clk.rate
    elif clk.clk_type == CLK_TYPE_DIV:
        # Keep current divider ratio
        if clk.rate and new_parent_clk.rate:
            div = max(1, new_parent_clk.rate // clk.rate)
            clk.rate = new_parent_clk.rate // div
            clk._cached_rate = clk.rate

    print(f"  [CLK] set_parent '{clk.name}': '{old_parent}' -> '{parent_name}'")
    return 0


def clk_get_parent(clock_name: str) -> Optional[str]:
    """Get parent clock name."""
    clk = _get_clk(clock_name)
    return clk.parent_name if clk.parent_name else None


def clk_get_parent_names(clock_name: str) -> list[str]:
    """Get list of parent names for mux clocks."""
    clk = _get_clk(clock_name)
    if clk.clk_type == CLK_TYPE_MUX and clk._mux_parents:
        return list(clk._mux_parents)
    parent = clk._resolve_parent()
    return [parent.name] if parent else []


# ---------------------------------------------------------------------------
# Phase / accuracy
# ---------------------------------------------------------------------------


def clk_set_phase(clock_name: str, degrees: int) -> int:
    """Set clock phase (0-359 degrees)."""
    clk = _get_clk(clock_name)
    if not (0 <= degrees <= 359):
        raise ValueError(f"Phase must be 0-359, got {degrees}")
    old = clk.phase
    clk.phase = degrees
    print(f"  [CLK] set_phase '{clk.name}': {old} -> {degrees} deg")
    return 0


def clk_get_phase(clock_name: str) -> int:
    """Get clock phase."""
    return _get_clk(clock_name).phase


def clk_get_accuracy(clock_name: str) -> int:
    """Get clock accuracy (ppm)."""
    return _get_clk(clock_name).accuracy


# ---------------------------------------------------------------------------
# Rate range
# ---------------------------------------------------------------------------


def clk_set_rate_range(clock_name: str, min_rate: int, max_rate: int) -> None:
    """Set allowed rate range."""
    clk = _get_clk(clock_name)
    clk.rate_range = ClkRateRange(min_rate=min_rate, max_rate=max_rate)
    print(f"  [CLK] set_rate_range '{clk.name}': [{min_rate}, {max_rate}] Hz")


# ---------------------------------------------------------------------------
# Status queries
# ---------------------------------------------------------------------------


def clk_is_enabled(clock_name: str) -> bool:
    """Check if clock is enabled."""
    return _get_clk(clock_name)._is_enabled


def clk_is_prepared(clock_name: str) -> bool:
    """Check if clock is prepared."""
    return _get_clk(clock_name)._is_prepared


# ---------------------------------------------------------------------------
# Div-table helpers
# ---------------------------------------------------------------------------


def clk_list_rates(clock_name: str) -> list[int]:
    """List available rates for divider / fixed-factor clocks."""
    clk = _get_clk(clock_name)
    parent = clk._resolve_parent()

    if clk.clk_type == CLK_TYPE_DIV_TABLE and clk._div_table and parent:
        return sorted({parent.rate // d for d in clk._div_table if d > 0})

    if clk.clk_type == CLK_TYPE_DIV and parent:
        return sorted({parent.rate // d for d in range(1, 64)})

    if clk.clk_type == CLK_TYPE_FIXED_FACTOR and parent:
        r = round(parent.rate * clk._fixed_mult / clk._fixed_div)
        return [r]

    return [clk.rate]


# ---------------------------------------------------------------------------
# Clock tree dump
# ---------------------------------------------------------------------------


def clk_dump() -> str:
    """Pretty-print the full clock tree."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  UmerOS Clock Tree")
    lines.append("=" * 72)

    # Group clocks by provider
    provider_clocks: dict[str, list[Clk]] = {}
    for clk in _clocks.values():
        pname = clk._provider.name if clk._provider else "(orphan)"
        provider_clocks.setdefault(pname, []).append(clk)

    for pname, clk_list in provider_clocks.items():
        lines.append(f"\n  Provider: {pname}")
        lines.append("  " + "-" * 68)
        for clk in sorted(clk_list, key=lambda c: c.name):
            status = ""
            if clk._is_prepared:
                status += "[PREPARED]"
            if clk._is_enabled:
                status += "[ENABLED]"
            if not status:
                status = "[off]"

            parent_str = f" (parent={clk.parent_name})" if clk.parent_name else ""
            lines.append(
                f"    {clk.name:<16} {clk.rate:>10,} Hz  {clk.clk_type:<14} {status}{parent_str}"
            )

    lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------


class OscillatorProvider(ClkProvider):
    """Crystal oscillator provider (e.g. 8, 12, 16, 24 MHz)."""

    def __init__(self, name: str = "osc", *, frequencies: list[int] | None = None) -> None:
        super().__init__(name=name, id=0)
        self._frequencies = frequencies or [8_000_000, 12_000_000, 16_000_000, 24_000_000]
        for i, freq in enumerate(self._frequencies):
            clk_register(
                self,
                name=f"osc{i}",
                rate=freq,
                clk_type=CLK_TYPE_FIXED,
                flags=CLK_SET_RATE_UNCHANGED,
            )


class PllProvider(ClkProvider):
    """PLL provider with configurable multiplier/divider."""

    def __init__(self, name: str = "pll", *, parent_name: str = "", default_rate: int = 96_000_000) -> None:
        super().__init__(name=name, id=1)
        clk_register(
            self,
            name=f"{name}_default",
            rate=default_rate,
            parent_name=parent_name,
            clk_type=CLK_TYPE_PLL,
            flags=CLK_SET_RATE_PARENT,
        )


class McuClockProvider(ClkProvider):
    """MCU clock tree (SYSCLK, AHB, APB1, APB2)."""

    def __init__(self, name: str = "mcu") -> None:
        super().__init__(name=name, id=2)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def demo() -> None:
    """Interactive demonstration of the UmerOS Clock Framework."""
    print()
    print("=" * 72)
    print("  UmerOS Clock Framework  --  CCF")
    print("=" * 72)
    print()

    # -- 1. Create providers -------------------------------------------------

    print("[1] Creating oscillator provider (8 / 12 / 16 / 24 MHz) ...")
    osc = OscillatorProvider("osc", frequencies=[8_000_000, 12_000_000, 16_000_000, 24_000_000])
    print()

    print("[2] Creating PLL provider (PLL1: CPU, PLL2: USB, PLL3: UART) ...")
    pll = PllProvider("pll", parent_name="osc0", default_rate=96_000_000)
    # Override the default PLL clocks with proper names
    clk_unregister("pll", "pll_default")
    clk_register(pll, "pll1", rate=96_000_000, parent_name="osc0", clk_type=CLK_TYPE_PLL, flags=CLK_SET_RATE_PARENT)
    clk_register(pll, "pll2", rate=48_000_000, parent_name="osc0", clk_type=CLK_TYPE_PLL, flags=CLK_SET_RATE_PARENT)
    clk_register(pll, "pll3", rate=115_200_000, parent_name="osc0", clk_type=CLK_TYPE_PLL, flags=CLK_SET_RATE_PARENT)
    print()

    print("[3] Creating MCU clock tree ...")
    mcu = McuClockProvider("mcu")

    # HSI - High Speed Internal oscillator (16 MHz)
    hsi = clk_register(mcu, "hsi", rate=16_000_000, clk_type=CLK_TYPE_FIXED, flags=CLK_SET_RATE_UNCHANGED)

    # HSE - High Speed External oscillator (8 MHz)
    hse = clk_register(mcu, "hse", rate=8_000_000, clk_type=CLK_TYPE_FIXED, flags=CLK_SET_RATE_UNCHANGED)

    # PLL1 CPU clock = HSI * 6 = 96 MHz (re-use the existing pll1 registration)
    # The PLL was already registered above; set its parent to HSI
    _clocks["pll1"].parent_name = "hsi"
    _clocks["pll1"].parent = _clocks["hsi"]
    _clocks["pll1"].rate = 16_000_000 * 6  # 96 MHz

    # AHB bus clock = PLL1 / 1 = 96 MHz
    ahb = clk_register(
        mcu, "ahb", rate=96_000_000,
        parent_name="pll1", clk_type=CLK_TYPE_DIV,
        flags=CLK_SET_RATE_PARENT,
    )

    # APB1 bus clock = AHB / 2 = 48 MHz
    apb1 = clk_register(
        mcu, "apb1", rate=48_000_000,
        parent_name="ahb", clk_type=CLK_TYPE_DIV,
        flags=CLK_SET_RATE_PARENT,
    )

    # APB2 bus clock = AHB / 1 = 96 MHz
    apb2 = clk_register(
        mcu, "apb2", rate=96_000_000,
        parent_name="ahb", clk_type=CLK_TYPE_DIV,
        flags=CLK_SET_RATE_PARENT,
    )

    # UART1 = PLL2 / 12 = 4 MHz
    uart1 = clk_register(
        mcu, "uart1", rate=4_000_000,
        parent_name="pll2", clk_type=CLK_TYPE_DIV,
        flags=CLK_SET_RATE_PARENT,
    )

    # GPIO1 gate
    gpio1 = clk_register(mcu, "gpio1", rate=96_000_000, parent_name="ahb", clk_type=CLK_TYPE_GATE)

    # I2C1 mux between HSI and PLL3
    i2c1 = clk_register(
        mcu, "i2c1", rate=16_000_000,
        parent_name="hsi", clk_type=CLK_TYPE_MUX,
        mux_parents=["hsi", "pll3"],
        flags=CLK_SET_RATE_PARENT,
    )

    # Timer with fixed factor: parent * 2 / 3
    tim1 = clk_register(
        mcu, "tim1", rate=0,
        parent_name="ahb", clk_type=CLK_TYPE_FIXED_FACTOR,
        fixed_mult=2, fixed_div=3,
    )
    # Calculate initial rate
    _clocks["tim1"].rate = round(96_000_000 * 2 / 3)
    _clocks["tim1"]._cached_rate = _clocks["tim1"].rate

    # SPI with div-table [1, 2, 4, 8, 16, 32, 64, 128]
    spi1 = clk_register(
        mcu, "spi1", rate=96_000_000 // 2,
        parent_name="apb2", clk_type=CLK_TYPE_DIV_TABLE,
        div_table=[1, 2, 4, 8, 16, 32, 64, 128],
        flags=CLK_SET_RATE_PARENT,
    )
    print()

    # -- 2. Lifecycle demo ---------------------------------------------------

    print("[4] Prepare / Enable / Disable / Unprepare lifecycle ...")
    print()

    print("  -- Prepare & enable HSE --")
    clk_prepare_enable("hse")
    print()

    print("  -- Prepare & enable PLL1 --")
    clk_prepare_enable("pll1")
    print()

    print("  -- Prepare & enable AHB --")
    clk_prepare_enable("ahb")
    print()

    print("  -- Prepare & enable APB1 --")
    clk_prepare_enable("apb1")
    print()

    print("  -- Prepare & enable UART1 --")
    clk_prepare_enable("uart1")
    print()

    print("  -- Disable & unprepare UART1 --")
    clk_disable_unprepare("uart1")
    print()

    print("  -- Disable & unprepare APB1 --")
    clk_disable_unprepare("apb1")
    print()

    print()

    # -- 3. Rate setting with parent propagation ----------------------------

    print("[5] Rate setting with parent propagation ...")
    print()

    print("  -- Set AHB to 72 MHz (propagate from PLL1) --")
    clk_set_rate("ahb", 72_000_000)
    print()

    print("  -- Set APB1 (AHB/2) --")
    clk_set_rate("apb1", 36_000_000)
    print()

    print("  -- Query rates --")
    print(f"     hsi   = {clk_get_rate('hsi'):>10,} Hz")
    print(f"     hse   = {clk_get_rate('hse'):>10,} Hz")
    print(f"     pll1  = {clk_get_rate('pll1'):>10,} Hz")
    print(f"     ahb   = {clk_get_rate('ahb'):>10,} Hz")
    print(f"     apb1  = {clk_get_rate('apb1'):>10,} Hz")
    print(f"     apb2  = {clk_get_rate('apb2'):>10,} Hz")
    print(f"     uart1 = {clk_get_rate('uart1'):>10,} Hz")
    print(f"     tim1  = {clk_get_rate('tim1'):>10,} Hz")
    print(f"     spi1  = {clk_get_rate('spi1'):>10,} Hz")
    print()

    # -- 4. Mux switching ----------------------------------------------------

    print("[6] Mux switching (I2C1: HSI -> PLL3) ...")
    print()

    print(f"  I2C1 parents: {clk_get_parent_names('i2c1')}")
    print(f"  I2C1 current parent: {clk_get_parent('i2c1')}")
    print(f"  I2C1 rate before:    {clk_get_rate('i2c1'):,} Hz")
    print()

    clk_set_parent("i2c1", "pll3")

    # Recalc rate: PLL3 = 115.2 MHz, I2C divider = 115.2 / 9.6 = 12
    _clocks["i2c1"].rate = round(115_200_000 / 12)
    _clocks["i2c1"]._cached_rate = _clocks["i2c1"].rate

    print(f"  I2C1 new parent: {clk_get_parent('i2c1')}")
    print(f"  I2C1 rate after: {clk_get_rate('i2c1'):,} Hz")
    print()

    # -- 5. Div table operations ---------------------------------------------

    print("[7] Div table operations (SPI1) ...")
    print()

    spi_rates = clk_list_rates("spi1")
    print(f"  SPI1 available rates (parent=APB2 @ {clk_get_rate('apb2'):,} Hz):")
    for r in spi_rates:
        print(f"    {r:>10,} Hz")
    print()

    print("  -- Set SPI1 to fastest available rate --")
    clk_set_rate("spi1", max(spi_rates))
    print()

    # -- 6. Phase setting ----------------------------------------------------

    print("[8] Phase setting ...")
    print()

    clk_set_phase("uart1", 90)
    print(f"  UART1 phase: {clk_get_phase('uart1')} degrees")

    clk_set_phase("uart1", 180)
    print(f"  UART1 phase: {clk_get_phase('uart1')} degrees")
    print()

    # -- 7. Rate range -------------------------------------------------------

    print("[9] Rate range constraints ...")
    print()

    clk_set_rate_range("apb1", min_rate=36_000_000, max_rate=48_000_000)
    print(f"  APB1 rate range: [{_clocks['apb1'].rate_range.min_rate:,}, {_clocks['apb1'].rate_range.max_rate:,}] Hz")
    print()

    print("  -- Try to set APB1 below minimum --")
    clk_set_rate("apb1", 10_000_000)
    print()

    print("  -- Try to set APB1 above maximum --")
    clk_set_rate("apb1", 60_000_000)
    print()

    # -- 8. Status queries ---------------------------------------------------

    print("[10] Status queries ...")
    print()

    for name in ["hsi", "hse", "pll1", "ahb", "apb1", "apb2", "uart1", "gpio1", "i2c1", "tim1", "spi1"]:
        prepared = "PREPARED" if clk_is_prepared(name) else "       -"
        enabled = " ENABLED" if clk_is_enabled(name) else "       -"
        print(f"  {name:<10}  {prepared}  {enabled}")
    print()

    # -- 9. Clock tree dump --------------------------------------------------

    print("[11] Full clock tree dump ...")
    print()
    print(clk_dump())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo()
