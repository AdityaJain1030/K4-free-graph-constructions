"""
search_N/logger.py
==================
Human-readable structured logger for search runs.

One file per run: logs/<algo>_n<N>_<YYYYMMDD_HHMMSS>.log

Line format:
    [HH:MM:SS.mmm] EVENT_NAME  key=value  key=value  ...

Standard events (used by Search base class and concrete algorithms)
--------------------------------------------------------------------
search_start   Start of run. Includes algo config/params.
search_end     End of run. Includes status, n_results, best_c_log, elapsed_s.
new_best       A better c_log was found. Includes c_log, alpha, d_max, elapsed_s.
attempt        One solver call / one (D, alpha) pair tried. SAT/ILP specific.
infeasible     Solver *proved* no solution exists for given params.
timeout        Time limit reached without a solution.
error          Unexpected exception. Includes exc (str).
"""

import os
from datetime import datetime

_LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_EVENT_WIDTH = 12  # column width for the event name


class SearchLogger:
    """
    Writes human-readable log lines for one search run.
    The file is opened lazily on first write and closed via .close().
    """

    def __init__(self, algo: str, n: int):
        self.algo  = algo
        self.n     = n
        self._file = None
        self.path  = None

    def _ensure_open(self):
        if self._file is None:
            os.makedirs(_LOGS_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path  = os.path.join(_LOGS_DIR, f"{self.algo}_n{self.n}_{ts}.log")
            self._file = open(self.path, "a")

    def write(self, event: str, **data):
        self._ensure_open()
        now = datetime.now()
        ts  = now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"
        label = event.upper().ljust(_EVENT_WIDTH)
        kv    = "  ".join(f"{k}={v}" for k, v in data.items())
        line  = f"[{ts}] {label}  {kv}\n" if kv else f"[{ts}] {label}\n"
        self._file.write(line)
        self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
