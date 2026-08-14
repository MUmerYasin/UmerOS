"""
UmerOS IIO Subsystem
====================
Kernel-like Industrial I/O framework for ADCs,
sensors, triggers, and buffered data acquisition.
"""

from __future__ import annotations

import time
import random
import struct
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Channel type constants
# ---------------------------------------------------------------------------

IIO_VOLTAGE = "voltage"
IIO_CURRENT = "current"
IIO_TEMP = "temperature"
IIO_PRESSURE = "pressure"
IIO_ACCEL = "accel"
IIO_GYRO = "gyro"
IIO_MAGN = "magnetic"
IIO_LIGHT = "light"
IIO_PROXIMITY = "proximity"
IIO_HUMIDITY = "humidity"
IIO_ROT = "rotation"
IIO_ANGL = "angle"
IIO_TIMESTAMP = "timestamp"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class IioInfo:
    """IIO device info"""
    name: str
    manufacturer: str = ""
    model: str = ""
    serial: str = ""
    label: str = ""


@dataclass
class IioChannel:
    """IIO channel (one measurement axis)"""
    name: str
    index: int
    type: str  # "voltage", "current", "temperature", "pressure", "accel", "gyro"
    unit: str  # "mV", "mA", "celsius", "hPa", "mg", "dps"
    scale: float = 1.0
    offset: float = 0.0
    bits: int = 12  # ADC resolution
    sign: str = 'u'  # 'u' unsigned, 's' signed
    ext_info: dict = field(default_factory=dict)

    def max_value(self) -> int:
        if self.sign == 's':
            return (1 << (self.bits - 1)) - 1
        return (1 << self.bits) - 1

    def min_value(self) -> int:
        if self.sign == 's':
            return -(1 << (self.bits - 1))
        return 0

    def scale_value(self, raw: int) -> float:
        """Apply scale and offset to a raw reading."""
        return raw * self.scale + self.offset


@dataclass
class IioTrigger:
    """IIO trigger source"""
    name: str
    id: int
    type: str  # "timer", "gpio", "irq", "data_ready"
    frequency: int = 100  # Hz
    _is_enabled: bool = False

    @property
    def period_us(self) -> float:
        """Period in microseconds."""
        if self.frequency == 0:
            return 0.0
        return 1_000_000.0 / self.frequency


@dataclass
class IioBuffer:
    """IIO scan buffer"""
    length: int = 128  # number of samples
    enabled: bool = False
    scan_mask: list = field(default_factory=list)
    data: list = field(default_factory=list)
    watermark: int = 1


@dataclass
class IioDevice:
    """Industrial I/O device (ADC, sensor, etc.)"""
    name: str
    id: int
    mode: str  # "polling", "buffered", "triggered"
    channels: list = field(default_factory=list)
    triggers: list = field(default_factory=list)
    buffer: IioBuffer = None
    _is_registered: bool = False
    _scan_mask: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.buffer is None:
            self.buffer = IioBuffer()

    def channel_by_index(self, idx: int) -> Optional[IioChannel]:
        for ch in self.channels:
            if ch.index == idx:
                return ch
        return None

    def channel_by_name(self, name: str) -> Optional[IioChannel]:
        for ch in self.channels:
            if ch.name == name:
                return ch
        return None

    def read_raw_channel(self, idx: int) -> int:
        """Read a raw value from a channel. Subclasses may override."""
        ch = self.channel_by_index(idx)
        if ch is None:
            raise IndexError(f"Channel index {idx} not found in device {self.name!r}")
        return random.randint(ch.min_value(), ch.max_value())

    def status_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.id,
            "mode": self.mode,
            "registered": self._is_registered,
            "channels": len(self.channels),
            "triggers": [t.name for t in self.triggers],
            "buffer_enabled": self.buffer.enabled,
            "scan_mask": self._scan_mask,
        }


# ---------------------------------------------------------------------------
# Global registries
# ---------------------------------------------------------------------------

_device_registry: dict[int, IioDevice] = {}
_device_name_index: dict[str, int] = {}
_trigger_registry: dict[str, IioTrigger] = {}
_event_log: list[dict] = []
_next_device_id: int = 1
_next_trigger_id: int = 1


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------

def iio_device_register(device: IioDevice) -> IioDevice:
    """Register IIO device – like iio_device_register()."""
    global _next_device_id
    if device.id == -1:
        device.id = _next_device_id
        _next_device_id += 1
    if device.id in _device_registry:
        raise ValueError(f"Device id {device.id} already registered")
    if device.name in _device_name_index:
        raise ValueError(f"Device name {device.name!r} already registered")
    device._is_registered = True
    _device_registry[device.id] = device
    _device_name_index[device.name] = device.id
    print(f"  [IIO] Registered device {device.name!r} (id={device.id}, mode={device.mode})")
    return device


def iio_device_unregister(device_id: int) -> None:
    """Unregister IIO device."""
    device = _device_registry.pop(device_id, None)
    if device is None:
        raise KeyError(f"No device with id {device_id}")
    device._is_registered = False
    _device_name_index.pop(device.name, None)
    print(f"  [IIO] Unregistered device {device.name!r} (id={device_id})")


def iio_device_get(device_id: int) -> IioDevice:
    """Get IIO device by id."""
    dev = _device_registry.get(device_id)
    if dev is None:
        raise KeyError(f"No device with id {device_id}")
    return dev


def iio_device_get_by_name(name: str) -> IioDevice:
    """Get IIO device by name."""
    did = _device_name_index.get(name)
    if did is None:
        raise KeyError(f"No device with name {name!r}")
    return _device_registry[did]


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------

def iio_read_raw(device_id: int, channel_index: int) -> int:
    """Read raw value from channel."""
    dev = iio_device_get(device_id)
    return dev.read_raw_channel(channel_index)


def iio_read_channel(device_id: int, channel_name: str) -> dict:
    """Read channel with scale/offset applied."""
    dev = iio_device_get(device_id)
    ch = dev.channel_by_name(channel_name)
    if ch is None:
        raise ValueError(f"Channel {channel_name!r} not found on device {dev.name!r}")
    raw = dev.read_raw_channel(ch.index)
    scaled = ch.scale_value(raw)
    return {
        "device": dev.name,
        "channel": ch.name,
        "raw": raw,
        "scaled": round(scaled, 4),
        "unit": ch.unit,
    }


def iio_write_raw(device_id: int, channel_index: int, value: int) -> None:
    """Write raw value (for DACs)."""
    dev = iio_device_get(device_id)
    ch = dev.channel_by_index(channel_index)
    if ch is None:
        raise IndexError(f"Channel index {channel_index} not found")
    ch.ext_info["last_written"] = value
    print(f"  [IIO] Wrote raw {value} to {dev.name!r} channel {ch.name!r}")


def iio_get_scale(channel: IioChannel) -> dict:
    """Get channel scale factor."""
    return {
        "scale": channel.scale,
        "offset": channel.offset,
        "unit": channel.unit,
        "bits": channel.bits,
        "sign": channel.sign,
        "max_raw": channel.max_value(),
        "min_raw": channel.min_value(),
    }


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def iio_push_event(device_id: int, event_code: str, data: dict) -> None:
    """Push event to userspace."""
    dev = iio_device_get(device_id)
    event = {
        "device": dev.name,
        "device_id": device_id,
        "code": event_code,
        "data": data,
        "timestamp": time.time(),
    }
    _event_log.append(event)
    print(f"  [IIO] Event: device={dev.name!r} code={event_code!r} data={data}")


def iio_enable_events(device_id: int) -> None:
    """Enable IIO events."""
    dev = iio_device_get(device_id)
    dev.ext_info = getattr(dev, "ext_info", {})
    dev.ext_info["events_enabled"] = True
    print(f"  [IIO] Events enabled for {dev.name!r}")


def iio_disable_events(device_id: int) -> None:
    """Disable IIO events."""
    dev = iio_device_get(device_id)
    dev.ext_info = getattr(dev, "ext_info", {})
    dev.ext_info["events_enabled"] = False
    print(f"  [IIO] Events disabled for {dev.name!r}")


# ---------------------------------------------------------------------------
# Buffer operations
# ---------------------------------------------------------------------------

def iio_buffer_enable(device_id: int) -> None:
    """Enable scan buffer."""
    dev = iio_device_get(device_id)
    dev.buffer.enabled = True
    dev.mode = "buffered"
    print(f"  [IIO] Buffer enabled for {dev.name!r} (length={dev.buffer.length})")


def iio_buffer_disable(device_id: int) -> None:
    """Disable scan buffer."""
    dev = iio_device_get(device_id)
    dev.buffer.enabled = False
    dev.mode = "polling"
    dev.buffer.data.clear()
    print(f"  [IIO] Buffer disabled for {dev.name!r}")


def iio_buffer_push_samples(device_id: int, data: list) -> None:
    """Push samples to buffer."""
    dev = iio_device_get(device_id)
    if not dev.buffer.enabled:
        raise RuntimeError(f"Buffer not enabled on {dev.name!r}")
    dev.buffer.data.extend(data)
    if len(dev.buffer.data) > dev.buffer.length:
        dev.buffer.data = dev.buffer.data[-dev.buffer.length:]


def iio_buffer_read_samples(device_id: int, count: int) -> list:
    """Read samples from buffer."""
    dev = iio_device_get(device_id)
    if not dev.buffer.enabled:
        raise RuntimeError(f"Buffer not enabled on {dev.name!r}")
    available = len(dev.buffer.data)
    to_read = min(count, available)
    samples = dev.buffer.data[:to_read]
    dev.buffer.data = dev.buffer.data[to_read:]
    return samples


# ---------------------------------------------------------------------------
# Trigger operations
# ---------------------------------------------------------------------------

def iio_trigger_register(trigger: IioTrigger) -> IioTrigger:
    """Register trigger."""
    global _next_trigger_id
    if trigger.id == -1:
        trigger.id = _next_trigger_id
        _next_trigger_id += 1
    if trigger.name in _trigger_registry:
        raise ValueError(f"Trigger {trigger.name!r} already registered")
    _trigger_registry[trigger.name] = trigger
    print(f"  [IIO] Registered trigger {trigger.name!r} (type={trigger.type}, freq={trigger.frequency}Hz)")
    return trigger


def iio_trigger_unregister(trigger_name: str) -> None:
    """Unregister trigger."""
    if trigger_name not in _trigger_registry:
        raise KeyError(f"No trigger with name {trigger_name!r}")
    del _trigger_registry[trigger_name]
    print(f"  [IIO] Unregistered trigger {trigger_name!r}")


def iio_trigger_enable(trigger_name: str) -> None:
    """Enable trigger."""
    trig = _trigger_registry.get(trigger_name)
    if trig is None:
        raise KeyError(f"No trigger with name {trigger_name!r}")
    trig._is_enabled = True
    print(f"  [IIO] Trigger {trigger_name!r} enabled")


def iio_trigger_disable(trigger_name: str) -> None:
    """Disable trigger."""
    trig = _trigger_registry.get(trigger_name)
    if trig is None:
        raise KeyError(f"No trigger with name {trigger_name!r}")
    trig._is_enabled = False
    print(f"  [IIO] Trigger {trigger_name!r} disabled")


def iio_set_trigger(device_id: int, trigger_name: str) -> None:
    """Associate trigger with device."""
    dev = iio_device_get(device_id)
    trig = _trigger_registry.get(trigger_name)
    if trig is None:
        raise KeyError(f"No trigger with name {trigger_name!r}")
    if trig not in dev.triggers:
        dev.triggers.append(trig)
    dev.mode = "triggered"
    print(f"  [IIO] Set trigger {trigger_name!r} on device {dev.name!r}")


# ---------------------------------------------------------------------------
# Scan mask helpers
# ---------------------------------------------------------------------------

def iio_scan_mask_set(device_id: int, channel_indices: list[int]) -> None:
    """Set scan mask for buffered reads."""
    dev = iio_device_get(device_id)
    dev._scan_mask = sorted(set(channel_indices))
    dev.buffer.scan_mask = dev._scan_mask[:]
    print(f"  [IIO] Scan mask set for {dev.name!r}: {dev._scan_mask}")


def iio_get_scan_mask(device_id: int) -> list[int]:
    """Get current scan mask."""
    dev = iio_device_get(device_id)
    return dev._scan_mask[:]


def iio_calc_scan_time(device_id: int) -> dict:
    """Calculate scan time based on mask."""
    dev = iio_device_get(device_id)
    active = len(dev._scan_mask)
    if active == 0:
        active = len(dev.channels)
    bits_per_sample = sum(
        dev.channel_by_index(i).bits for i in dev._scan_mask
    ) if dev._scan_mask else sum(ch.bits for ch in dev.channels)
    bytes_per_scan = (bits_per_sample + 7) // 8
    return {
        "device": dev.name,
        "active_channels": active,
        "bits_per_sample": bits_per_sample,
        "bytes_per_scan": bytes_per_scan,
        "watermark": dev.buffer.watermark,
    }


# ---------------------------------------------------------------------------
# Built-in devices
# ---------------------------------------------------------------------------

class Ads1115Device(IioDevice):
    """ADS1115 16-bit ADC (4 channels, I2C)"""

    def __init__(self, name: str = "ads1115", dev_id: int = -1) -> None:
        super().__init__(
            name=name,
            id=dev_id,
            mode="polling",
        )
        self.info = IioInfo(
            name=name, manufacturer="Texas Instruments", model="ADS1115",
            serial="", label="16-bit 4-ch ADC",
        )
        self.channels = [
            IioChannel(name="ain0", index=0, type=IIO_VOLTAGE, unit="mV",
                       scale=0.1875, offset=0.0, bits=16, sign='s'),
            IioChannel(name="ain1", index=1, type=IIO_VOLTAGE, unit="mV",
                       scale=0.1875, offset=0.0, bits=16, sign='s'),
            IioChannel(name="ain2", index=2, type=IIO_VOLTAGE, unit="mV",
                       scale=0.1875, offset=0.0, bits=16, sign='s'),
            IioChannel(name="ain3", index=3, type=IIO_VOLTAGE, unit="mV",
                       scale=0.1875, offset=0.0, bits=16, sign='s'),
        ]


class Bmp280Device(IioDevice):
    """BMP280 temperature/pressure sensor"""

    def __init__(self, name: str = "bmp280", dev_id: int = -1) -> None:
        super().__init__(
            name=name,
            id=dev_id,
            mode="triggered",
        )
        self.info = IioInfo(
            name=name, manufacturer="Bosch", model="BMP280",
            serial="", label="Temp+Pressure",
        )
        self.channels = [
            IioChannel(name="temp", index=0, type=IIO_TEMP, unit="celsius",
                       scale=0.005, offset=-50.0, bits=20, sign='s'),
            IioChannel(name="pressure", index=1, type=IIO_PRESSURE, unit="hPa",
                       scale=0.00244140625, offset=0.0, bits=20, sign='u'),
        ]


class Mpu6050Device(IioDevice):
    """MPU6050 6-axis IMU (accel + gyro)"""

    def __init__(self, name: str = "mpu6050", dev_id: int = -1) -> None:
        super().__init__(
            name=name,
            id=dev_id,
            mode="buffered",
        )
        self.info = IioInfo(
            name=name, manufacturer="InvenSense", model="MPU6050",
            serial="", label="6-axis IMU",
        )
        self.channels = [
            IioChannel(name="accel_x", index=0, type=IIO_ACCEL, unit="mg",
                       scale=0.061, offset=0.0, bits=16, sign='s'),
            IioChannel(name="accel_y", index=1, type=IIO_ACCEL, unit="mg",
                       scale=0.061, offset=0.0, bits=16, sign='s'),
            IioChannel(name="accel_z", index=2, type=IIO_ACCEL, unit="mg",
                       scale=0.061, offset=0.0, bits=16, sign='s'),
            IioChannel(name="gyro_x", index=3, type=IIO_GYRO, unit="dps",
                       scale=0.00762939453125, offset=0.0, bits=16, sign='s'),
            IioChannel(name="gyro_y", index=4, type=IIO_GYRO, unit="dps",
                       scale=0.00762939453125, offset=0.0, bits=16, sign='s'),
            IioChannel(name="gyro_z", index=5, type=IIO_GYRO, unit="dps",
                       scale=0.00762939453125, offset=0.0, bits=16, sign='s'),
        ]


class Hx711Device(IioDevice):
    """HX711 load cell ADC"""

    def __init__(self, name: str = "hx711", dev_id: int = -1) -> None:
        super().__init__(
            name=name,
            id=dev_id,
            mode="polling",
        )
        self.info = IioInfo(
            name=name, manufacturer="Avia Semiconductor", model="HX711",
            serial="", label="24-bit load cell ADC",
        )
        self.channels = [
            IioChannel(name="load_raw", index=0, type=IIO_VOLTAGE, unit="counts",
                       scale=1.0, offset=0.0, bits=24, sign='s'),
        ]


class Max44009Device(IioDevice):
    """MAX44009 ambient light sensor"""

    def __init__(self, name: str = "max44009", dev_id: int = -1) -> None:
        super().__init__(
            name=name,
            id=dev_id,
            mode="polling",
        )
        self.info = IioInfo(
            name=name, manufacturer="Analog Devices", model="MAX44009",
            serial="", label="Ambient light sensor",
        )
        self.channels = [
            IioChannel(name="lux", index=0, type=IIO_LIGHT, unit="lux",
                       scale=0.045, offset=0.0, bits=16, sign='u'),
        ]


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo() -> None:
    print("=" * 68)
    print("  UmerOS IIO Subsystem — Demo")
    print("=" * 68)

    # ---- Create built-in devices ------------------------------------------------
    print("\n--- Creating devices ---")
    ads = Ads1115Device()
    bmp = Bmp280Device()
    mpu = Mpu6050Device()
    hx = Hx711Device()
    als = Max44009Device()

    iio_device_register(ads)
    iio_device_register(bmp)
    iio_device_register(mpu)
    iio_device_register(hx)
    iio_device_register(als)

    # ---- Register triggers ------------------------------------------------------
    print("\n--- Creating triggers ---")
    trig_timer = IioTrigger(name="timer_100hz", id=1, type="timer", frequency=100)
    trig_ready = IioTrigger(name="data_ready", id=2, type="data_ready", frequency=0)
    trig_gpio = IioTrigger(name="gpio_17", id=3, type="gpio", frequency=0)

    iio_trigger_register(trig_timer)
    iio_trigger_register(trig_ready)
    iio_trigger_register(trig_gpio)

    # ---- Set triggers on devices ------------------------------------------------
    print("\n--- Associating triggers ---")
    iio_set_trigger(bmp.id, "timer_100hz")
    iio_set_trigger(mpu.id, "data_ready")

    # ---- Read raw values --------------------------------------------------------
    print("\n--- Reading raw values ---")
    for ch in ads.channels:
        raw = iio_read_raw(ads.id, ch.index)
        print(f"  {ads.name!r} / {ch.name!r}: raw={raw}")

    raw_t = iio_read_raw(bmp.id, 0)
    raw_p = iio_read_raw(bmp.id, 1)
    print(f"  {bmp.name!r} / temp:   raw={raw_t}")
    print(f"  {bmp.name!r} / press:  raw={raw_p}")

    raw_lux = iio_read_raw(als.id, 0)
    print(f"  {als.name!r} / lux:    raw={raw_lux}")

    # ---- Channel read with scale/offset -----------------------------------------
    print("\n--- Scaled readings ---")
    reading = iio_read_channel(bmp.id, "temp")
    print(f"  {reading}")

    reading = iio_read_channel(bmp.id, "pressure")
    print(f"  {reading}")

    reading = iio_read_channel(ads.id, "ain0")
    print(f"  {reading}")

    reading = iio_read_channel(als.id, "lux")
    print(f"  {reading}")

    for name in ("accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"):
        reading = iio_read_channel(mpu.id, name)
        print(f"  {reading}")

    # ---- Scale info -------------------------------------------------------------
    print("\n--- Channel scale info ---")
    for dev_id in (ads.id, bmp.id, mpu.id):
        dev = iio_device_get(dev_id)
        for ch in dev.channels:
            info = iio_get_scale(ch)
            print(f"  {dev.name!r} / {ch.name!r}: {info}")

    # ---- DAC write (HX711 example) ---------------------------------------------
    print("\n--- Raw write (DAC example) ---")
    iio_write_raw(hx.id, 0, 42_000_000)

    # ---- Buffer operations (MPU6050) --------------------------------------------
    print("\n--- Buffered mode (MPU6050) ---")
    iio_scan_mask_set(mpu.id, [0, 1, 2, 3, 4, 5])
    iio_buffer_enable(mpu.id)

    print("  Pushing 6 samples ...")
    for i in range(6):
        sample = [random.randint(-32768, 32767) for _ in mpu.channels]
        iio_buffer_push_samples(mpu.id, sample)

    print("  Reading 4 samples ...")
    samples = iio_buffer_read_samples(mpu.id, 4)
    for idx, s in enumerate(samples):
        print(f"    sample[{idx}]: {s}")

    scan_info = iio_calc_scan_time(mpu.id)
    print(f"  Scan info: {scan_info}")

    iio_buffer_disable(mpu.id)

    # ---- Buffer operations (BMP280) ---------------------------------------------
    print("\n--- Buffered mode (BMP280) ---")
    iio_scan_mask_set(bmp.id, [0, 1])
    iio_buffer_enable(bmp.id)

    for i in range(4):
        sample = [random.randint(0, 1_000_000) for _ in bmp.channels]
        iio_buffer_push_samples(bmp.id, sample)

    samples = iio_buffer_read_samples(bmp.id, 3)
    for idx, s in enumerate(samples):
        print(f"    sample[{idx}]: {s}")

    iio_buffer_disable(bmp.id)

    # ---- Events -----------------------------------------------------------------
    print("\n--- Events ---")
    iio_enable_events(ads.id)
    iio_push_event(ads.id, "thresh_rising", {"channel": 0, "threshold": 2048})
    iio_push_event(ads.id, "thresh_falling", {"channel": 0, "threshold": -2048})
    iio_push_event(mpu.id, "data_ready", {"axis": "xyz"})
    iio_disable_events(ads.id)
    print(f"  Total events logged: {len(_event_log)}")

    # ---- Trigger operations -----------------------------------------------------
    print("\n--- Trigger details ---")
    for trig_name in ("timer_100hz", "data_ready", "gpio_17"):
        trig = _trigger_registry[trig_name]
        print(f"  {trig.name!r}: type={trig.type}, freq={trig.frequency}Hz, "
              f"period={trig.period_us:.0f}us, enabled={trig._is_enabled}")

    iio_trigger_enable("timer_100hz")
    iio_trigger_enable("gpio_17")
    iio_trigger_disable("gpio_17")

    # ---- Device status ----------------------------------------------------------
    print("\n--- Device status ---")
    for dev_id in sorted(_device_registry):
        dev = iio_device_get(dev_id)
        st = dev.status_dict()
        print(f"  {st['name']!r}:")
        print(f"    id={st['id']}  mode={st['mode']!r}  "
              f"registered={st['registered']}  channels={st['channels']}")
        print(f"    triggers={st['triggers']}  buffer_enabled={st['buffer_enabled']}  "
              f"scan_mask={st['scan_mask']}")

    # ---- Unregister one device --------------------------------------------------
    print("\n--- Unregistering HX711 ---")
    iio_device_unregister(hx.id)

    # ---- Final device list ------------------------------------------------------
    print("\n--- Remaining devices ---")
    for dev_id in sorted(_device_registry):
        dev = iio_device_get(dev_id)
        print(f"  id={dev.id}  name={dev.name!r}  mode={dev.mode!r}")

    print("\n" + "=" * 68)
    print("  IIO subsystem demo complete.")
    print("=" * 68)


if __name__ == "__main__":
    _demo()
