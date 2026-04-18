#!/usr/bin/env python3
"""Rankings over results.jsonl. Prints to stdout and writes leaderboard.md."""

import json
import math
import re
import signal
from collections import Counter
from pathlib import Path

# Exit quietly when piped to `head` etc.
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.jsonl"
MD_PATH = HERE / "leaderboard.md"

N_FAST = [20, 25, 30, 40, 50, 60]
PALEY_17_BASELINE = 0.6789

# Canonical family list — drives the UNEXPLORED marker. Order is display order.
KNOWN_FAMILIES = [
    "cayley_cyclic", "circulant", "cayley_product", "cayley_dihedral",
    "product", "polarity", "gq_incidence", "kneser", "hamming",
    "grassmann", "peisert", "mathon_srg", "blowup", "random_lift",
    "hash", "latin_square", "random_greedy", "crossover", "unknown",
]

# Filename-substring fallback when source has no `# Family:` tag.
# Order matters: first match wins.
_FAMILY_KEYWORDS = [
    ("hybrid",           "crossover"),
    ("crossover",        "crossover"),
    ("paley",            "cayley_cyclic"),
    ("quad_res",         "cayley_cyclic"),
    ("qr",               "cayley_cyclic"),
    ("cubic",            "cayley_cyclic"),
    ("cayley_z_mod_p",   "cayley_cyclic"),
    ("zp_zq",            "cayley_product"),
    ("cayley_product",   "cayley_product"),
    ("dihedral",         "cayley_dihedral"),
    ("circulant",        "circulant"),
    ("strong_product",   "product"),
    ("tensor",           "product"),
    ("lex_product",      "product"),
    ("polarity",         "polarity"),
    ("projective_plane", "polarity"),
    ("mv_",              "polarity"),
    ("gq_",              "gq_incidence"),
    ("generalized_quad", "gq_incidence"),
    ("kneser",           "kneser"),
    ("hamming",          "hamming"),
    ("grassmann",        "grassmann"),
    ("peisert",          "peisert"),
    ("mathon",           "mathon_srg"),
    ("paulus",           "mathon_srg"),
    ("blowup",           "blowup"),
    ("random_lift",      "random_lift"),
    ("hash",             "hash"),
    ("latin_square",     "latin_square"),
    ("random",           "random_greedy"),
    ("greedy",           "random_greedy"),
]

_FAMILY_TAG_RE = re.compile(r"^\s*#\s*Family\s*:\s*([A-Za-z0-9_\-]+)", re.MULTILINE)


def family_of(record):
    """Detect family from `# Family:` tag in source; fall back to gen_id keywords."""
    src = record.get("source_code") or ""
    m = _FAMILY_TAG_RE.search(src)
    if m:
        return m.group(1).strip().lower()
    gen_id = (record.get("gen_id") or "").lower()
    for kw, fam in _FAMILY_KEYWORDS:
        if kw in gen_id:
            return fam
    return "unknown"


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

    # -------- Family status (saturation detection) --------
    # Group records by family, walk in timestamp order, track stale counter
    # (attempts since the family's running best improved).
    by_fam = {}
    for r in sorted(records, key=lambda x: x.get("timestamp", "")):
        by_fam.setdefault(family_of(r), []).append(r)

    def _stats(fam_records):
        best = math.inf
        best_rec = None
        stale = 0
        for r in fam_records:
            s = r.get("score", math.inf)
            if not isinstance(s, (int, float)):
                s = math.inf
            if s < best:
                best = s
                best_rec = r
                stale = 0
            else:
                stale += 1
        return best, best_rec, stale, len(fam_records)

    fam_summary = {}  # family -> (best, best_rec, stale, attempts, status)
    for fam in set(list(by_fam.keys()) + KNOWN_FAMILIES):
        recs = by_fam.get(fam, [])
        if not recs:
            fam_summary[fam] = (math.inf, None, 0, 0, "UNEXPLORED")
            continue
        best, best_rec, stale, n = _stats(recs)
        if math.isinf(best):
            status = "ACTIVE (underexplored)" if n <= 1 else "ACTIVE"
        elif stale >= 3:
            status = "SATURATED"
        elif n <= 1:
            status = "ACTIVE (underexplored)"
        else:
            status = "ACTIVE"
        fam_summary[fam] = (best, best_rec, stale, n, status)

    emit("## Family status")
    emit()
    emit("```")
    # Sort: SATURATED last-ish, UNEXPLORED first (nudge the agent), then by best score
    status_order = {"UNEXPLORED": 0, "ACTIVE (underexplored)": 1, "ACTIVE": 2, "SATURATED": 3}
    def _sort_key(item):
        fam, (best, _, _, n, status) = item
        return (status_order.get(status, 2), best if math.isfinite(best) else 9e9, fam)

    for fam, (best, best_rec, stale, n, status) in sorted(fam_summary.items(), key=_sort_key):
        if n == 0:
            emit(f"{fam:<22} (no attempts)                           -> {status}")
        else:
            best_str = "inf" if math.isinf(best) else f"{best:.4f}"
            gen = best_rec["gen_id"] if best_rec else "-"
            emit(f"{fam:<22} best={best_str:<7} attempts={n:<3} stale={stale:<3} -> {status}  [{gen}]")
    emit("```")
    emit()

    # Inline source for each SATURATED family's best so the agent sees the ceiling.
    saturated = [(f, s) for f, s in fam_summary.items() if s[4] == "SATURATED" and s[1]]
    if saturated:
        emit("### Saturated families — best candidate source (the ceiling)")
        emit()
        for fam, (best, best_rec, stale, n, _) in sorted(saturated, key=lambda x: x[1][0]):
            src = (best_rec.get("source_code") or "").strip()
            if len(src) > 2000:
                src = src[:2000] + "\n# ... (truncated)"
            emit(f"**{fam}** — {best_rec['gen_id']}  (best={best:.4f}, {n} attempts, stale={stale})")
            emit()
            emit("```python")
            emit(src)
            emit("```")
            emit()

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
