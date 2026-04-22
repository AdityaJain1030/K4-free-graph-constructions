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

N_DISPLAY = [17, 30, 34, 40, 51, 60, 68, 85, 100]
PALEY_17_BASELINE = 0.6789

# Canonical family list. Non-VT families come first (they are the actual
# target under the current RULES.md). VT families are kept for labelling
# historical candidates but the agent should not be submitting to them.
NON_VT_FAMILIES = [
    "asymmetric_lift", "perturbed_paley", "core_periphery", "two_orbit",
    "srg_perturbed", "structure_plus_noise", "voltage_partial",
    "sat_seeded", "invented", "crossover",
]
VT_FAMILIES = [
    "cayley_cyclic", "circulant", "cayley_product", "cayley_dihedral",
    "product", "polarity", "gq_incidence", "kneser", "hamming",
    "grassmann", "peisert", "mathon_srg", "blowup", "random_lift",
    "hash", "latin_square", "random_greedy",
]
KNOWN_FAMILIES = NON_VT_FAMILIES + VT_FAMILIES + ["unknown"]

# Filename-substring fallback when source has no `# Family:` tag.
# Order matters: first match wins.
_FAMILY_KEYWORDS = [
    ("asymmetric_lift",  "asymmetric_lift"),
    ("perturbed_paley",  "perturbed_paley"),
    ("core_periphery",   "core_periphery"),
    ("two_orbit",        "two_orbit"),
    ("srg_perturb",      "srg_perturbed"),
    ("noise",            "structure_plus_noise"),
    ("voltage",          "voltage_partial"),
    ("sat_seeded",       "sat_seeded"),
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
            for k in ("score", "score_mean", "best_c", "score_full"):
                if r.get(k) == "Infinity":
                    r[k] = float("inf")
            records.append(r)
        except Exception:
            pass
    return records


def _score_of(r):
    """Primary ranking: best_c (with the code-length tiebreaker built
    into `score`). Falls back to inf for records from old runs."""
    v = r.get("score")
    if isinstance(v, (int, float)):
        return v
    bc = r.get("best_c")
    if isinstance(bc, (int, float)):
        return bc
    return math.inf


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
            s = _score_of(r)
            if s < best:
                best = s
                best_rec = r
                stale = 0
            else:
                stale += 1
        return best, best_rec, stale, len(fam_records)

    # Under singular-N-winner scoring, "SATURATED" is a much looser
    # concept — stale counts across the full history, not consecutive —
    # and UNEXPLORED is just informational, not a hard gate.
    fam_summary = {}  # family -> (best, best_rec, stale, attempts, is_non_vt, status)
    for fam in set(list(by_fam.keys()) + KNOWN_FAMILIES):
        is_non_vt = fam in NON_VT_FAMILIES
        recs = by_fam.get(fam, [])
        if not recs:
            fam_summary[fam] = (math.inf, None, 0, 0, is_non_vt, "UNEXPLORED")
            continue
        best, best_rec, stale, n = _stats(recs)
        if math.isinf(best):
            status = "ACTIVE (no finite c yet)" if n <= 2 else "ACTIVE (all-fail)"
        elif stale >= 10:
            status = "STALE"
        elif n <= 2:
            status = "ACTIVE (underexplored)"
        else:
            status = "ACTIVE"
        fam_summary[fam] = (best, best_rec, stale, n, is_non_vt, status)

    emit("## Family status (non-VT families are the target — VT is informational only)")
    emit()
    emit("```")

    def _sort_key(item):
        fam, (best, _, _, n, is_non_vt, _status) = item
        # Non-VT first; within a group, best score first.
        return (0 if is_non_vt else 1, best if math.isfinite(best) else 9e9, fam)

    emit("# --- non-VT families ---")
    for fam, (best, best_rec, stale, n, is_non_vt, status) in sorted(
        fam_summary.items(), key=_sort_key
    ):
        if not is_non_vt:
            continue
        best_str = "inf" if math.isinf(best) else f"{best:.4f}"
        gen = best_rec["gen_id"] if best_rec else "-"
        if n == 0:
            emit(f"{fam:<22} (no attempts)                         -> {status}")
        else:
            emit(f"{fam:<22} best={best_str:<7} attempts={n:<3} stale={stale:<3} -> {status}  [{gen}]")

    emit("# --- VT families (historical; not to be targeted) ---")
    for fam, (best, best_rec, stale, n, is_non_vt, status) in sorted(
        fam_summary.items(), key=_sort_key
    ):
        if is_non_vt:
            continue
        if n == 0:
            # Don't bother printing unexplored VT families — we don't want them targeted.
            continue
        best_str = "inf" if math.isinf(best) else f"{best:.4f}"
        gen = best_rec["gen_id"] if best_rec else "-"
        emit(f"{fam:<22} best={best_str:<7} attempts={n:<3} stale={stale:<3} -> {status}  [{gen}]")
    emit("```")
    emit()

    # --- Recent thoughts log: dump the last 10 candidates' hypotheses so
    # the agent has a window into what was just tried without having to
    # grep thoughts.md or cat individual files.
    emit("## Recent thoughts (last 10 candidates)")
    emit()
    recent = sorted(records, key=lambda x: x.get("timestamp", ""))[-10:]
    if recent:
        for r in recent:
            gen = r.get("gen_id", "-")
            fam = r.get("family") or family_of(r)
            bc = r.get("best_c")
            bc_str = "inf" if not isinstance(bc, (int, float)) or math.isinf(bc) else f"{bc:.4f}"
            hyp = (r.get("hypothesis") or "").strip()
            wnv = (r.get("why_non_vt") or "").strip()
            emit(f"- **{gen}** [{fam}, best_c={bc_str}]")
            if hyp:
                emit(f"    hyp: {hyp}")
            if wnv:
                emit(f"    non-VT: {wnv}")
    else:
        emit("_No records._")
    emit()

    # Top 20 by primary score (= best_c + 0.001 * code_length).
    by_score = sorted(records, key=_score_of)[:20]
    emit("## Top 20 by best_c")
    emit()
    rows = []
    for i, r in enumerate(by_score, 1):
        fam = r.get("family") or family_of(r)
        bc = r.get("best_c")
        bc_N = r.get("best_c_N")
        beats = "*" if isinstance(bc, (int, float)) and math.isfinite(bc) and bc < PALEY_17_BASELINE else ""
        rows.append([
            i, r["gen_id"], fam, bc, bc_N, beats,
            r.get("n_valid_N", 0), r.get("code_length", 0),
        ])
    emit(_table(
        ["rank", "gen_id", "family", "best_c", "best_c_N", "beats_P17", "valid_N", "code_len"],
        rows,
    ))
    emit()

    # Per-N breakdown for top 5 at the headline N values (17-lift tower etc.)
    emit(f"## Per-N breakdown (top 5 by best_c, showing N={N_DISPLAY})")
    emit()
    headers = ["gen_id"] + [f"N={N}" for N in N_DISPLAY]
    rows = []
    for r in by_score[:5]:
        row = [r["gen_id"]]
        for N in N_DISPLAY:
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
    beats_paley = sum(1 for r in records
                      if isinstance(r.get("best_c"), (int, float)) and r["best_c"] < PALEY_17_BASELINE)
    non_vt_count = sum(1 for r in records
                       if (r.get("family") or family_of(r)) in NON_VT_FAMILIES)
    times = [r["timestamp"] for r in records if "timestamp" in r]
    emit(f"- Total evaluations: **{len(records)}**")
    emit(f"- Non-VT candidates: **{non_vt_count}** / {len(records)}")
    emit(f"- Stage 2 triggered (best_c<1.0 in Stage 1): **{stage1_pass}**")
    emit(f"- Achieved best_c < 1.0: **{under_one}**")
    emit(f"- **Beat P(17) (best_c < {PALEY_17_BASELINE}): {beats_paley}**")
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
