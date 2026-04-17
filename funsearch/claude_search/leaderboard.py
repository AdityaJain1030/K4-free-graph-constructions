#!/usr/bin/env python3
"""Rankings over results.jsonl. Prints to stdout and writes leaderboard.md."""

import json
import math
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
MD_PATH = HERE / "leaderboard.md"

N_FAST = [20, 25, 30, 40, 50, 60]
PALEY_17_BASELINE = 0.6789


def _load():
    records = []
    if not RESULTS_PATH.exists():
        return records
    for line in RESULTS_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            # "Infinity" string sentinels from _json_default
            for k in ("score", "best_c", "score_full"):
                if r.get(k) == "Infinity":
                    r[k] = float("inf")
            records.append(r)
        except Exception:
            pass
    return records


def _fmt_num(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        if math.isinf(v):
            return "inf"
        return f"{v:.4f}"
    return str(v)


def _table(headers, rows):
    widths = [len(h) for h in headers]
    str_rows = []
    for r in rows:
        cells = [_fmt_num(v) for v in r]
        for i, s in enumerate(cells):
            widths[i] = max(widths[i], len(s))
        str_rows.append(cells)
    lines = []
    lines.append("| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |")
    lines.append("|" + "|".join("-" * (widths[i] + 2) for i in range(len(headers))) + "|")
    for r in str_rows:
        lines.append("| " + " | ".join(r[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    return "\n".join(lines)


def main():
    records = _load()
    out_lines = []

    def emit(s=""):
        out_lines.append(s)
        print(s)

    emit(f"# Leaderboard ({len(records)} evaluations)")
    emit()

    if not records:
        emit("_No records yet._")
        MD_PATH.write_text("\n".join(out_lines))
        return

    # Top 20 by primary score
    by_score = sorted(records, key=lambda r: r["score"])[:20]
    emit("## Top 20 by primary score")
    emit()
    rows = []
    for i, r in enumerate(by_score, 1):
        rows.append([
            i, r["gen_id"], r["score"], r["best_c"], r["best_c_N"],
            r.get("score_regularity", 0.0), r.get("code_length", 0),
        ])
    emit(_table(["rank", "gen_id", "score", "best_c", "best_c_N", "regularity", "code_len"], rows))
    emit()

    # Top 10 by regularity
    by_reg = sorted(records, key=lambda r: -r.get("score_regularity", 0.0))[:10]
    emit("## Top 10 by regularity score")
    emit()
    rows = []
    for i, r in enumerate(by_reg, 1):
        rows.append([i, r["gen_id"], r.get("score_regularity", 0.0), r["score"], r["best_c"]])
    emit(_table(["rank", "gen_id", "regularity", "score", "best_c"], rows))
    emit()

    # Per-N breakdown for top 5
    emit("## Per-N breakdown (top 5 by score)")
    emit()
    headers = ["gen_id"] + [f"N={N}" for N in N_FAST]
    rows = []
    for r in by_score[:5]:
        row = [r["gen_id"]]
        for N in N_FAST:
            rec = r.get("per_N", {}).get(str(N))
            if rec and isinstance(rec.get("c"), (int, float)) and math.isfinite(rec["c"]):
                row.append(rec["c"])
            else:
                row.append(None)
        rows.append(row)
    emit(_table(headers, rows))
    emit()

    # Per-N frontier
    emit("## Frontier: best c at each N across all evaluations")
    emit()
    frontier = {}
    for r in records:
        for Nk, rec in r.get("per_N", {}).items():
            c = rec.get("c")
            if isinstance(c, (int, float)) and math.isfinite(c):
                cur = frontier.get(int(Nk))
                if cur is None or c < cur[0]:
                    frontier[int(Nk)] = (c, r["gen_id"])
    rows = [[N, v[0], v[1]] for N, v in sorted(frontier.items())]
    emit(_table(["N", "best_c", "gen_id"], rows))
    emit()

    # Summary
    emit("## Summary stats")
    emit()
    stage1_pass = sum(1 for r in records if r.get("stage1_passed"))
    under_one = sum(1 for r in records
                    if isinstance(r.get("best_c"), (int, float)) and r["best_c"] < 1.0)
    times = [r["timestamp"] for r in records if "timestamp" in r]
    emit(f"- Total evaluations: **{len(records)}**")
    emit(f"- Stage 1 passed: **{stage1_pass}**")
    emit(f"- Achieved best_c < 1.0: **{under_one}**")
    if times:
        emit(f"- Timestamp range: {min(times)} → {max(times)}")
    emit()

    # Failure analysis
    emit("## Failure analysis")
    emit()
    fail_buckets = Counter()
    total_N_evals = 0
    for r in records:
        for rec in r.get("per_N", {}).values():
            total_N_evals += 1
            fr = rec.get("failure_reason")
            if fr:
                bucket = fr.split(":")[0].strip().split()[0]
                fail_buckets[bucket] += 1
    if fail_buckets:
        rows = [[k, v, f"{100 * v / total_N_evals:.1f}%"]
                for k, v in fail_buckets.most_common()]
        emit(_table(["reason", "count", "% of all per-N evals"], rows))
    else:
        emit("_No per-N failures recorded._")

    MD_PATH.write_text("\n".join(out_lines))


if __name__ == "__main__":
    main()
