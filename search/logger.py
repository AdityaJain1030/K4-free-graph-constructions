"""
search_N/logger.py
==================
Human-readable structured logger for search runs.

Per-run file: logs/search_N/<algo>_n<N>_<YYYYMMDD_HHMMSS>.log
Aggregate file (opt-in): logs/search_N/<name>_<YYYYMMDD_HHMMSS>.agg.log

Line format (per-run):
    [HH:MM:SS.mmm] EVENT_NAME   key=value  key=value  ...

Line format (aggregate, with child tag):
    [HH:MM:SS.mmm] EVENT_NAME   [<algo>_n<N>]   key=value  ...
"""

import os
from datetime import datetime

_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "search_N",
)
_EVENT_WIDTH = 12


def _now_ts() -> str:
    now = datetime.now()
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _fmt_kv(data: dict) -> str:
    return "  ".join(f"{k}={v}" for k, v in data.items())


class AggregateLogger:
    """
    Tees log lines from every child SearchLogger into one aggregate file.

    Nesting is flat: an AggregateLogger can itself have a parent_logger,
    and every line teed into it is also teed up the chain. Child runs
    stamp the `[<algo>_n<N>]` tag onto their writes so aggregate files
    interleave cleanly.

    Usage::

        with AggregateLogger(name="sweep") as agg:
            for n in range(6, 11):
                BruteForce(n=n, parent_logger=agg).run()
    """

    def __init__(self, name: str, parent_logger: "AggregateLogger | None" = None):
        self.name = name
        self.parent_logger = parent_logger
        self._file = None
        self.path = None

    def _ensure_open(self):
        if self._file is None:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = os.path.join(_LOGS_DIR, f"{self.name}_{ts}.agg.log")
            self._file = open(self.path, "a")

    def tee(self, ts: str, event: str, child_tag: str, kv_str: str):
        """Called by SearchLogger (or a nested AggregateLogger) on every write."""
        self._ensure_open()
        label = event.upper().ljust(_EVENT_WIDTH)
        tag = f"[{child_tag}]"
        line = (
            f"[{ts}] {label}  {tag}   {kv_str}\n"
            if kv_str
            else f"[{ts}] {label}  {tag}\n"
        )
        self._file.write(line)
        self._file.flush()
        if self.parent_logger is not None:
            self.parent_logger.tee(ts, event, child_tag, kv_str)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class SearchLogger:
    """
    Writes per-run log lines. Opens lazily on first write.

    If `parent_logger` is given, every line is also teed into that
    aggregate logger, prefixed with `[<algo>_n<N>]` so the aggregate
    output remains readable across many concurrent child runs.
    """

    def __init__(
        self,
        algo: str,
        n: int,
        parent_logger: "AggregateLogger | None" = None,
    ):
        self.algo = algo
        self.n = n
        self.parent_logger = parent_logger
        self._file = None
        self.path = None

    def _ensure_open(self):
        if self._file is None:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = os.path.join(_LOGS_DIR, f"{self.algo}_n{self.n}_{ts}.log")
            self._file = open(self.path, "a")

    def write(self, event: str, **data):
        self._ensure_open()
        ts = _now_ts()
        label = event.upper().ljust(_EVENT_WIDTH)
        kv = _fmt_kv(data)
        line = f"[{ts}] {label}  {kv}\n" if kv else f"[{ts}] {label}\n"
        self._file.write(line)
        self._file.flush()

        if self.parent_logger is not None:
            self.parent_logger.tee(ts, event, f"{self.algo}_n{self.n}", kv)

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None
