"""
Summarise results/cayley_gap_theta.csv: α vs θ vs Hoffman across
the cayley_tabu_gap sweep.
"""
import csv
import math
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(os.path.dirname(HERE), "results", "cayley_gap_theta.csv")


def main():
    rows = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            for k in ("n",):
                r[k] = int(r[k])
            for k in ("d", "alpha", "lam_min", "hoffman", "theta",
                     "theta_over_alpha", "theta_over_hoff",
                     "alpha_over_hoff", "theta_minus_alpha", "c_log"):
                r[k] = float(r[k]) if r[k] not in ("", None) else None
            rows.append(r)
    N = len(rows)
    print(f"Records: {N}\n")

    def buckets(key, bins):
        out = defaultdict(int)
        for r in rows:
            v = r[key]
            for lo, hi, lbl in bins:
                if lo <= v < hi:
                    out[lbl] += 1
                    break
        return out

    # θ vs Hoffman
    theta_eq_hoff = sum(1 for r in rows if abs(r["theta"] - r["hoffman"]) < 1e-3)
    theta_lt_hoff = sum(1 for r in rows if r["theta"] < r["hoffman"] - 1e-3)
    print(f"θ = Hoffman (to 1e-3): {theta_eq_hoff}/{N} "
          f"({100*theta_eq_hoff/N:.1f}%)")
    print(f"θ < Hoffman strictly: {theta_lt_hoff}/{N} "
          f"({100*theta_lt_hoff/N:.1f}%)\n")

    # α vs θ
    alpha_eq_theta = sum(1 for r in rows
                         if abs(r["theta"] - r["alpha"]) < 1e-2)
    alpha_lt_theta = sum(1 for r in rows
                         if r["theta"] > r["alpha"] + 1e-2)
    print(f"α = θ (to 1e-2): {alpha_eq_theta}/{N} "
          f"({100*alpha_eq_theta/N:.1f}%)  "
          f"→ SDP proves α exact for these graphs")
    print(f"α < θ strictly: {alpha_lt_theta}/{N} "
          f"({100*alpha_lt_theta/N:.1f}%)\n")

    # Distribution of θ/H
    print("θ/Hoffman distribution:")
    hist = buckets("theta_over_hoff", [
        (0.0, 0.70, "< 0.70"),
        (0.70, 0.80, "0.70–0.80"),
        (0.80, 0.90, "0.80–0.90"),
        (0.90, 0.99, "0.90–0.99"),
        (0.99, 1.001, "= 1.00"),
        (1.001, 99, "> 1.00 (numerical)"),
    ])
    for lbl in ["< 0.70", "0.70–0.80", "0.80–0.90", "0.90–0.99",
                "= 1.00", "> 1.00 (numerical)"]:
        print(f"  {lbl:20s} {hist[lbl]:4d}")
    print()

    # Distribution of α/θ
    print("α/θ (tightness of SDP ceiling):")
    hist = buckets("theta_over_alpha", [
        (0.0, 1.01, "θ ≈ α (SDP tight)"),
        (1.01, 1.10, "θ within 10%"),
        (1.10, 1.25, "θ within 25%"),
        (1.25, 1.50, "θ within 50%"),
        (1.50, 99, "θ ≥ 1.5α"),
    ])
    for lbl in ["θ ≈ α (SDP tight)", "θ within 10%",
                "θ within 25%", "θ within 50%", "θ ≥ 1.5α"]:
        print(f"  {lbl:22s} {hist[lbl]:4d}")
    print()

    # Hoffman-saturated records (α = H): ask what θ does
    print("Graphs at Hoffman ceiling (α/H ≥ 0.999):")
    print("  n    α     θ      H      group")
    sat = [r for r in rows if r["alpha_over_hoff"] >= 0.999]
    for r in sorted(sat, key=lambda x: x["n"])[:20]:
        print(f"  {r['n']:3d}  {int(r['alpha']):3d}  {r['theta']:6.3f} "
              f"{r['hoffman']:6.3f}  {r['group']}")
    print(f"  ... {len(sat)} total Hoffman-saturated\n")

    # Graphs where θ gap is biggest (α << θ << H)
    print("Top 15 largest (H − θ) gaps (SDP tightens Hoffman the most):")
    print("   n    α       θ        H     H−θ   θ−α    group")
    by_gap = sorted(rows, key=lambda r: -(r["hoffman"] - r["theta"]))
    for r in by_gap[:15]:
        print(f"  {r['n']:3d}  {int(r['alpha']):3d}  {r['theta']:7.3f} "
              f"{r['hoffman']:7.3f}  {r['hoffman']-r['theta']:5.2f}  "
              f"{r['theta']-r['alpha']:5.2f}  {r['group']}")
    print()

    # Graphs where α is exact (SDP reaches ground truth)
    print("Top 15 smallest θ−α (SDP proves α optimal or near-optimal):")
    print("   n    α       θ        H     θ−α   α/H    group")
    by_sdp_tight = sorted(rows, key=lambda r: r["theta"] - r["alpha"])
    for r in by_sdp_tight[:15]:
        print(f"  {r['n']:3d}  {int(r['alpha']):3d}  {r['theta']:7.3f} "
              f"{r['hoffman']:7.3f}  {r['theta']-r['alpha']:5.2f}  "
              f"{r['alpha_over_hoff']:.3f}  {r['group']}")
    print()

    # Plateau families from the doc
    print("Plateau families — α, θ, H along lift chains:")
    plateaus = {
        "P(17)":    [17, 34, 51, 68, 85],
        "N=22 fam": [22, 44, 66, 88],
        "CR(19)":   [19, 38, 57, 76],
        "N=20 fam": [20, 40, 60, 80],
        "F_21":     [21, 42, 63, 84],
    }
    by_n = defaultdict(list)
    for r in rows:
        by_n[r["n"]].append(r)

    for name, Ns in plateaus.items():
        print(f"  {name}:")
        for n in Ns:
            # pick the record with α/H closest to 1 (the "plateau" record)
            recs = by_n.get(n, [])
            if not recs:
                print(f"    N={n}: no record")
                continue
            best = max(recs, key=lambda x: x["alpha_over_hoff"])
            ratio_ath = best["alpha"] / best["theta"]
            print(f"    N={n}:  α={int(best['alpha'])}  "
                  f"θ={best['theta']:6.2f}  H={best['hoffman']:6.2f}  "
                  f"α/θ={ratio_ath:.3f}  α/H={best['alpha_over_hoff']:.3f}  "
                  f"({best['group']})")
    print()

    # Compute c_log using theta and compare
    print("c_log-via-θ vs c_log-via-α on frontier improvement N's:")
    focus = [28, 36, 40, 80, 92]
    for n in focus:
        recs = by_n.get(n, [])
        if not recs: continue
        best = min(recs, key=lambda x: x["c_log"])
        alpha, theta, d, N_ = best["alpha"], best["theta"], best["d"], best["n"]
        c_alpha = best["c_log"]
        # c_log = α · ln d / (n · d)? — use project's definition from
        # doc: we just report α vs θ side-by-side, and the "θ-c_log"
        # derived by substituting θ for α. Scope: this is a per-graph
        # *upper bound* derivation; if θ-c_log drops below the P(17)
        # plateau, it means even the SDP ceiling can't prove a c-bound
        # that low via this graph.
        if d >= 2 and N_ > 0:
            # c_log as stored appears to be alpha-based. Replicate:
            c_via_theta = theta * d / (N_ * math.log(d))
        else:
            c_via_theta = None
        print(f"   N={n}  group={best['group']}")
        print(f"         α={int(alpha)}  c_log(α)={c_alpha:.4f}")
        print(f"         θ={theta:.2f}  c_log(θ)={c_via_theta:.4f}  "
              f"(SDP ceiling on c_log for this graph)")
    print()


if __name__ == "__main__":
    main()
