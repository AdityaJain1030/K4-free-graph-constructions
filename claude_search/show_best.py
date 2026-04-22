#!/usr/bin/env python3
"""Print source and detailed metrics for top 3 constructions by primary score."""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
PALEY_17_BASELINE = 0.6789


def _load():
    out = []
    if not RESULTS_PATH.exists():
        return out
    for line in RESULTS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            for k in ("score", "score_mean", "best_c", "score_full"):
                if r.get(k) == "Infinity":
                    r[k] = float("inf")
            out.append(r)
        except Exception:
            pass
    return out


def _score_of(r):
    v = r.get("score")
    if isinstance(v, (int, float)):
        return v
    bc = r.get("best_c")
    if isinstance(bc, (int, float)):
        return bc
    return math.inf


def main():
    records = _load()
    records.sort(key=_score_of)
    top = records[:3]
    if not top:
        print("No records.")
        return
    for rank, r in enumerate(top, 1):
        print("=" * 72)
        bc = r.get("best_c", float("inf"))
        beats = " *** BEATS P(17) ***" if isinstance(bc, (int, float)) and math.isfinite(bc) and bc < PALEY_17_BASELINE else ""
        print(f"# Rank {rank}: {r['gen_id']}  (best_c={bc:.4f} @ N={r.get('best_c_N')}){beats}")
        print("=" * 72)
        if r.get("family"):
            print(f"Family: {r['family']}")
        if r.get("parent"):
            print(f"Parent: {r['parent']}")
        if r.get("hypothesis"):
            print(f"Hypothesis: {r['hypothesis']}")
        if r.get("why_non_vt"):
            print(f"Why non-VT: {r['why_non_vt']}")
        print(f"valid_N = {r.get('n_valid_N', 0)}  "
              f"code_length = {r.get('code_length', 0)}  "
              f"regularity = {r.get('score_regularity', 0):.3f}")
        pct = 100.0 * bc / PALEY_17_BASELINE if isinstance(bc, (int, float)) and math.isfinite(bc) else float("inf")
        if math.isfinite(pct):
            print(f"{pct:.1f}% of P(17) baseline ({PALEY_17_BASELINE})")
        print()
        print("--- Source ---")
        print(r.get("source_code", "").rstrip())
        print()
        print("--- Per-N metrics ---")
        per_N = r.get("per_N", {})
        headers = ["N", "d_max", "d_min", "regularity", "α", "exact", "c", "edges", "tri", "conn"]
        rows = []
        for Nk in sorted(per_N.keys(), key=int):
            rec = per_N[Nk]
            rows.append([
                Nk, rec.get("d_max"), rec.get("d_min"),
                f"{rec.get('regularity_score', 0):.3f}" if rec.get("regularity_score") is not None else "-",
                rec.get("alpha"), rec.get("alpha_exact"),
                f"{rec['c']:.4f}" if isinstance(rec.get("c"), (int, float)) and math.isfinite(rec["c"]) else "inf",
                rec.get("edge_count"), rec.get("triangle_count"),
                rec.get("is_connected"),
            ])
        _print_table(headers, rows)

        # Degree sequence at best_c_N
        bN = r.get("best_c_N")
        if bN is not None:
            rec = per_N.get(str(bN))
            if rec and rec.get("degree_sequence"):
                ds = rec["degree_sequence"]
                # Truncate if long
                dstr = ", ".join(map(str, ds[:40]))
                if len(ds) > 40:
                    dstr += f", ... ({len(ds)} total)"
                print(f"\nDegree sequence @ N={bN}: [{dstr}]")
                dmax, dmin = rec.get("d_max"), rec.get("d_min")
                vt_hint = "likely vertex-transitive" if dmax == dmin else "irregular (not vertex-transitive)"
                print(f"Structure hint: {vt_hint}")
        print()


def _print_table(headers, rows):
    widths = [len(h) for h in headers]
    strs = []
    for r in rows:
        cells = ["-" if v is None else str(v) for v in r]
        for i, c in enumerate(cells):
            widths[i] = max(widths[i], len(c))
        strs.append(cells)
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for r in strs:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))


if __name__ == "__main__":
    main()
