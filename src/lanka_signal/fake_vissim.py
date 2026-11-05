"""Minimal stand-in for the PTV VISSIM COM object model.

It implements only the calls made by the legacy controller so its unmodified
``main()`` can be executed deterministically. It **does not simulate traffic**:
queue-counter values are whatever the caller's ``queue_fn`` returns. Use it to
study the controller's *timing logic* (green durations, cycle lengths, run
length) under stated assumptions about what ``QLen`` returns.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Optional

QueueFn = Callable[[int, float, str], Optional[float]]
STATE_NAMES = {1: "RED", 3: "GREEN", 4: "AMBER"}


@dataclass
class _Clock:
    sim_res: int = 10
    ticks: int = 0
    sim_period: float = 99999.0
    overrun_ticks: int = 0

    @property
    def second(self) -> float:
        return self.ticks / self.sim_res


class _Simulation:
    def __init__(self, clock: _Clock):
        self._c = clock
        self.attrs: dict = {}
        self.stopped_at: Optional[float] = None

    def SetAttValue(self, name, value):
        self.attrs[name] = value
        if name == "SimRes":
            self._c.sim_res = int(value)
        if name == "SimPeriod":
            self._c.sim_period = float(value)

    @property
    def SimulationSecond(self) -> float:
        return self._c.second

    def RunSingleStep(self):
        self._c.ticks += 1
        if self._c.second > self._c.sim_period:
            # Real VISSIM behaviour beyond SimPeriod is not known here; we record it.
            self._c.overrun_ticks += 1

    def Stop(self):
        self.stopped_at = self._c.second


class _SignalGroup:
    def __init__(self, no: int, log: list, clock: _Clock):
        self.no, self._log, self._c = no, log, clock

    def SetAttValue(self, name, value):
        if name != "SigState":
            raise AttributeError(name)
        self._log.append((self._c.second, self.no, int(value)))


class _Collection:
    def __init__(self, factory):
        self._f, self._items = factory, {}

    def ItemByKey(self, key):
        if key not in self._items:
            self._items[key] = self._f(key)
        return self._items[key]


class _SignalController:
    def __init__(self, log, clock):
        self.SGs = _Collection(lambda k: _SignalGroup(k, log, clock))


class _QueueCounter:
    def __init__(self, no: int, fn: QueueFn, clock: _Clock, reads: list):
        self.no, self._fn, self._c, self._reads = no, fn, clock, reads

    def AttValue(self, attr):
        v = self._fn(self.no, self._c.second, attr)
        self._reads.append((self._c.second, self.no, attr, v))
        return v


@dataclass
class FakeVissim:
    queue_fn: QueueFn
    sig_log: list = field(default_factory=list)
    qlen_reads: list = field(default_factory=list)

    def __post_init__(self):
        self.clock = _Clock()
        self.Simulation = _Simulation(self.clock)
        log, clock, fn, reads = self.sig_log, self.clock, self.queue_fn, self.qlen_reads

        class _Net:
            SignalControllers = _Collection(lambda k: _SignalController(log, clock))
            QueueCounters = _Collection(lambda k: _QueueCounter(k, fn, clock, reads))

        self.Net = _Net()
        self.loaded_net = None

    def LoadNet(self, path):
        self.loaded_net = path

    def LoadLayout(self, path):
        pass


def replay_legacy_main(queue_fn: QueueFn):
    """Run the unmodified legacy ``main()`` against a :class:`FakeVissim`.

    Returns the FakeVissim instance (signal-state log, queue reads, clock) or
    raises whatever the legacy code raises.
    """
    from .legacy_logic import load_legacy

    fake = FakeVissim(queue_fn)
    mod = load_legacy(dispatch=lambda _progid: fake, module_name="lanka_legacy_replay")
    with tempfile.NamedTemporaryFile(suffix=".inpx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        mod.INPX_PATH = tmp_path  # only the path is changed; no algorithm constant is touched
        mod.print = lambda *a, **k: None  # silence progress prints
        mod.main()
    finally:
        os.unlink(tmp_path)
    return fake


def green_intervals(sig_log, sg_no: int):
    """Return [(start, end)] intervals during which ``sg_no`` was commanded GREEN."""
    out, start = [], None
    for t, sg, state in sig_log:
        if sg != sg_no:
            continue
        if state == 3 and start is None:
            start = t
        elif state != 3 and start is not None:
            out.append((start, t))
            start = None
    return out
