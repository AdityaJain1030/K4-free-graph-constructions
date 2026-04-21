#!/usr/bin/env python3
"""
scripts/compare_cayley_tabu.py
==============================
Compare Cayley-tabu db entries to the existing baseline records.

Reads the SQLite property cache for (n, alpha, d_max, c_log) — those
are canonical, computed by DB.sync() from sparse6. Group name for
tabu rows is read from the record metadata.

Writes:
  * results/cayley_tabu/comparison.md
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB


def _scan() -> tuple[dict[int, dict], dict[int, tuple[float, str]]]:
    """Return (best-tabu-per-N, best-baseline-per-N-with-source)."""
    tabu: dict[int, dict] = {}
    baseline: dict[int, tuple[float, str]] = {}
    with DB() as db:
        cur = db.cache._conn.execute(
            "SELECT graph_id, source, n, alpha, d_max, c_log, metadata "
            "FROM cache WHERE c_log IS NOT NULL"
        )
        for row in cur:
            n = row["n"]
            c = row["c_log"]
            src = row["source"]
            if src == "cayley_tabu":
                # Need group name from the record metadata column.
                md = json.loads(row["metadata"] or "{}")
                if n not in tabu or c < tabu[n]["c_log"]:
                    tabu[n] = {
                        "c_log": c,
                        "alpha": row["alpha"],
                        "d_max": row["d_max"],
                        "group": md.get("group", ""),
                    }
            else:
                if n not in baseline or c < baseline[n][0]:
                    baseline[n] = (c, src)
    return tabu, baseline


def main() -> int:
    sweep, baseline = _scan()

    rows = []
    for n in sorted(sweep):
        s = sweep[n]
        sc = s["c_log"]
        bc, bsrc = baseline.get(n, (None, "—"))
        delta = None
        if sc is not None and bc is not None:
            delta = sc - bc
            if delta < -1e-6:
                verdict = "tabu BEATS baseline"
            elif delta > 1e-6:
                verdict = "baseline better"
            else:
                verdict = "match"
        else:
            verdict = "no baseline"
        rows.append({
            "n": n,
            "tabu_c": sc,
            "tabu_group": s["group"] or "",
            "tabu_alpha": s["alpha"],
            "tabu_d_max": s["d_max"],
            "baseline_c": bc,
            "baseline_src": bsrc,
            "delta": delta,
            "verdict": verdict,
        })

    out_root = Path(REPO) / "results" / "cayley_tabu"
    out_root.mkdir(parents=True, exist_ok=True)
    md_path = out_root / "comparison.md"
    lines = ["# Cayley-tabu vs baseline", ""]
    lines.append("| N  | tabu c | group | α | d | baseline c | src | Δc | verdict |")
    lines.append("|----|--------|-------|---|---|------------|-----|----|---------|")
    for r in rows:
        tabu_c = f"{r['tabu_c']:.4f}" if r["tabu_c"] is not None else "—"
        base_c = f"{r['baseline_c']:.4f}" if r["baseline_c"] is not None else "—"
        delta = f"{r['delta']:+.4f}" if r["delta"] is not None else "—"
        a = r["tabu_alpha"] if r["tabu_alpha"] is not None else "—"
        d = r["tabu_d_max"] if r["tabu_d_max"] is not None else "—"
        lines.append(
            f"| {r['n']:>2} | {tabu_c} | {r['tabu_group']} | "
            f"{a} | {d} | {base_c} | {r['baseline_src']} | {delta} | {r['verdict']} |"
        )

    matches = sum(1 for r in rows if r["verdict"] == "match")
    beats = sum(1 for r in rows if r["verdict"] == "tabu BEATS baseline")
    worse = sum(1 for r in rows if r["verdict"] == "baseline better")
    no_base = sum(1 for r in rows if r["verdict"] == "no baseline")
    lines += ["", "## Totals", ""]
    lines.append(f"- match:             {matches}")
    lines.append(f"- tabu beats:        {beats}")
    lines.append(f"- baseline better:   {worse}")
    lines.append(f"- no baseline:       {no_base}")

    md_path.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
