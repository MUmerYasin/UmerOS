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

"""Pulse-level quantum control.

Provides hardware-level pulse scheduling for trapped-ion and superconducting
qubit architectures, including waveform generation, frame tracking, and
real-time pulse sequencing.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional, Sequence, Tuple, Union,
)

import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Waveforms
# ---------------------------------------------------------------------------

class WaveformType(Enum):
    CONSTANT = auto()
    GAUSSIAN = auto()
    DRAG = auto()
    HARMONIC = auto()
    ARBITRARY = auto()


@dataclass
class Waveform:
    """Parametric or arbitrary waveform definition."""

    name: str
    waveform_type: WaveformType
    duration: float  # nanoseconds
    params: Dict[str, float] = field(default_factory=dict)
    samples: Optional[NDArray[np.float64]] = None
    channel: Optional[str] = None

    def sample(self, dt: float = 1.0) -> NDArray[np.float64]:
        """Generate time-domain samples at the given resolution *dt*."""
        n_samples = max(1, int(np.ceil(self.duration / dt)))
        t = np.linspace(0, self.duration, n_samples, endpoint=False)

        if self.waveform_type == WaveformType.ARBITRARY and self.samples is not None:
            return self.samples[:n_samples]

        amp = self.params.get("amp", 1.0)

        if self.waveform_type == WaveformType.CONSTANT:
            return np.full(n_samples, amp)
        if self.waveform_type == WaveformType.GAUSSIAN:
            sigma = self.params.get("sigma", self.duration / 6.0)
            return amp * np.exp(-0.5 * ((t - self.duration / 2.0) / sigma) ** 2)
        if self.waveform_type == WaveformType.DRAG:
            sigma = self.params.get("sigma", self.duration / 6.0)
            alpha = self.params.get("alpha", 0.2)
            gauss = amp * np.exp(-0.5 * ((t - self.duration / 2.0) / sigma) ** 2)
            deriv = -alpha * (t - self.duration / 2.0) / sigma**2 * gauss
            return gauss + 1j * deriv  # type: ignore[return-value]
        if self.waveform_type == WaveformType.HARMONIC:
            freq = self.params.get("freq", 1.0 / self.duration)
            phase = self.params.get("phase", 0.0)
            return amp * np.sin(2 * np.pi * freq * t + phase)

        return np.zeros(n_samples)


@dataclass
class ConstantWaveform(Waveform):
    """Convenience constant-amplitude pulse."""

    def __init__(self, name: str, duration: float, amp: float = 1.0, channel: Optional[str] = None):
        super().__init__(
            name=name,
            waveform_type=WaveformType.CONSTANT,
            duration=duration,
            params={"amp": amp},
            channel=channel,
        )


@dataclass
class GaussianWaveform(Waveform):
    """Convenience Gaussian envelope."""

    def __init__(self, name: str, duration: float, amp: float = 1.0,
                 sigma: Optional[float] = None, channel: Optional[str] = None):
        super().__init__(
            name=name,
            waveform_type=WaveformType.GAUSSIAN,
            duration=duration,
            params={"amp": amp, "sigma": sigma or duration / 6.0},
            channel=channel,
        )


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    """Named phase/frequency reference for a channel."""

    name: str
    qubit: int
    frequency: float = 0.0  # Hz
    phase: float = 0.0  # radians
    backend: Optional[str] = None

    def shift_phase(self, delta: float) -> None:
        self.phase += delta

    def set_frequency(self, freq: float) -> None:
        self.frequency = freq


# ---------------------------------------------------------------------------
# Pulses
# ---------------------------------------------------------------------------

@dataclass
class Pulse:
    """A single pulse anchored to a frame with a waveform."""

    frame: Frame
    waveform: Waveform
    t0: float = 0.0  # start time (ns)
    name: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.waveform.duration

    @property
    def t_end(self) -> float:
        return self.t0 + self.duration

    def sample(self, dt: float = 1.0) -> NDArray[np.float64]:
        return self.waveform.sample(dt)

    def shift(self, delta: float) -> Pulse:
        """Return a copy shifted in time."""
        return Pulse(
            frame=self.frame,
            waveform=self.waveform,
            t0=self.t0 + delta,
            name=self.name,
        )


# ---------------------------------------------------------------------------
# Pulse Sequence
# ---------------------------------------------------------------------------

class PulseScheduleType(Enum):
    IMMEDIATE = auto()
    CANONICAL = auto()


@dataclass
class PulseSequence:
    """Ordered collection of pulses for one execution."""

    name: Optional[str] = None
    pulses: List[Pulse] = field(default_factory=list)
    schedule_type: PulseScheduleType = PulseScheduleType.CANONICAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---- construction ---------------------------------------------------

    def add(self, pulse: Pulse) -> PulseSequence:
        self.pulses.append(pulse)
        return self

    def add_native(self, frame: Frame, waveform: Waveform, t0: float = 0.0) -> Pulse:
        p = Pulse(frame=frame, waveform=waveform, t0=t0)
        self.pulses.append(p)
        return p

    def append(self, other: PulseSequence) -> PulseSequence:
        self.pulses.extend(other.pulses)
        return self

    # ---- queries --------------------------------------------------------

    @property
    def duration(self) -> float:
        if not self.pulses:
            return 0.0
        return max(p.t_end for p in self.pulses)

    @property
    def channels(self) -> List[str]:
        seen: list[str] = []
        for p in self.pulses:
            name = p.frame.name
            if name not in seen:
                seen.append(name)
        return seen

    def pulses_on_channel(self, channel: str) -> List[Pulse]:
        return [p for p in self.pulses if p.frame.name == channel]

    # ---- scheduling -----------------------------------------------------

    def sort(self) -> PulseSequence:
        """Sort pulses by start time."""
        self.pulses.sort(key=lambda p: p.t0)
        return self

    def resolve_overlaps(self) -> PulseSequence:
        """Push overlapping pulses later on the same channel."""
        by_channel: Dict[str, list[Pulse]] = {}
        for p in self.pulses:
            by_channel.setdefault(p.frame.name, []).append(p)

        self.pulses.clear()
        for pulses in by_channel.values():
            pulses.sort(key=lambda p: p.t0)
            for p in pulses:
                while any(
                    p.t0 < ex.t_end and p.frame.name == ex.frame.name
                    for ex in self.pulses
                ):
                    p = p.shift(1.0)
                self.pulses.append(p)

        self.sort()
        return self

    # ---- serialisation --------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schedule_type": self.schedule_type.name,
            "pulses": [
                {
                    "frame": p.frame.name,
                    "qubit": p.frame.qubit,
                    "waveform": p.waveform.name,
                    "waveform_type": p.waveform.waveform_type.name,
                    "duration": p.waveform.duration,
                    "t0": p.t0,
                    "params": p.waveform.params,
                }
                for p in self.pulses
            ],
            "duration": self.duration,
            "metadata": self.metadata,
        }

    def sample(self, dt: float = 1.0) -> Dict[str, NDArray[np.float64]]:
        """Return time-domain samples per channel."""
        out: Dict[str, NDArray[np.float64]] = {}
        for ch in self.channels:
            total = max(int(np.ceil(self.duration / dt)), 1)
            buf = np.zeros(total, dtype=complex)
            for p in self.pulses_on_channel(ch):
                s = p.sample(dt)
                start = int(p.t0 / dt)
                end = min(start + len(s), total)
                buf[start:end] += s[: end - start]
            out[ch] = buf
        return out


# ---------------------------------------------------------------------------
# Pulse Scheduler
# ---------------------------------------------------------------------------

class SchedulingStrategy(Enum):
    AS_SOON_AS_POSSIBLE = auto()
    AS_LATE_AS_POSSIBLE = auto()
    NO_OVERLAPS = auto()


@dataclass
class PulseScheduler:
    """Schedules PulseSequences onto hardware time-slots."""

    strategy: SchedulingStrategy = SchedulingStrategy.NO_OVERLAPS
    dt: float = 1.0  # hardware clock cycle (ns)

    def schedule(self, seq: PulseSequence) -> PulseSequence:
        if self.strategy == SchedulingStrategy.NO_OVERLAPS:
            seq.resolve_overlaps()
        elif self.strategy == SchedulingStrategy.AS_SOON_AS_POSSIBLE:
            seq.sort()
        elif self.strategy == SchedulingStrategy.AS_LATE_AS_POSSIBLE:
            self._schedule_alap(seq)
        seq.sort()
        return seq

    # ---- internal -------------------------------------------------------

    def _schedule_alap(self, seq: PulseSequence) -> None:
        """Schedule as late as possible while respecting duration."""
        by_channel: Dict[str, list[Pulse]] = {}
        for p in seq.pulses:
            by_channel.setdefault(p.frame.name, []).append(p)

        seq.pulses.clear()
        for channel, pulses in by_channel.items():
            pulses.sort(key=lambda p: p.t0, reverse=True)
            cursor = max(p.t_end for p in pulses) if pulses else 0.0
            for p in pulses:
                cursor -= p.duration
                seq.pulses.append(Pulse(frame=p.frame, waveform=p.waveform, t0=cursor, name=p.name))

    # ---- validation -----------------------------------------------------

    @staticmethod
    def validate(seq: PulseSequence) -> List[str]:
        warnings: list[str] = []
        for p in seq.pulses:
            if p.waveform.duration <= 0:
                warnings.append(f"Pulse '{p.name}' on '{p.frame.name}' has non-positive duration")
            if p.t0 < 0:
                warnings.append(f"Pulse '{p.name}' starts before t=0")
        return warnings
