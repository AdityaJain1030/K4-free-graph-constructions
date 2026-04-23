"""
Pull the c_log frontier graph per N (the best graph at each vertex
count) and show α / θ / Hoffman together. Uses the freshly-cached
lovasz_theta column.
"""
import json
import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from graph_db import DB  # noqa: E402


def main():
    with DB(auto_sync=False) as db:
        # minimum c_log per n, pick the record that hits that min.
        rows = db.raw_execute("""
            SELECT c.n, c.alpha, c.lovasz_theta, c.c_log, c.source,
                   c.d_max, c.regularity_d, c.is_regular,
                   c.eigenvalues_adj, c.graph_id
            FROM cache c
            INNER JOIN (
                SELECT n, MIN(c_log) AS best_c
                FROM cache
                WHERE is_k4_free=1 AND c_log IS NOT NULL
                GROUP BY n
            ) b ON b.n = c.n AND b.best_c = c.c_log
            WHERE c.is_k4_free=1
            ORDER BY c.n
        """)
        seen_n = set()
        front = []
        for r in rows:
            if r["n"] in seen_n: continue
            seen_n.add(r["n"])
            front.append(r)

    print(f"{'N':>4s} {'α':>4s} {'θ':>8s} {'H':>8s} "
          f"{'θ−α':>6s} {'α/θ':>6s} {'θ/H':>6s} {'c_log':>7s} "
          f"{'src':<22s} status")
    print("-" * 100)

    n_theta_exact = 0
    n_theta_hoff = 0
    below_plateau = []

    for r in front:
        alpha = r["alpha"]
        theta = r["lovasz_theta"]
        n = r["n"]
        ev = r["eigenvalues_adj"]
        if isinstance(ev, str):
            ev = json.loads(ev)
        lam_min = min(ev)
        d = r["regularity_d"] if r["is_regular"] else r["d_max"]
        if d > lam_min:
            hoff = n * (-lam_min) / (d - lam_min)
            theta_over_hoff = theta / hoff
        else:
            hoff = float("nan")
            theta_over_hoff = float("nan")
        alpha_over_theta = alpha / theta if theta else float("nan")

        status = []
        if abs(theta - alpha) < 0.01:
            status.append("α=θ")
            n_theta_exact += 1
        if not math.isnan(theta_over_hoff) and abs(theta - hoff) < 1e-3:
            status.append("θ=H")
            n_theta_hoff += 1
        if r["c_log"] is not None and r["c_log"] < 0.679:
            status.append("<P(17)")
            below_plateau.append(r)

        print(f"{n:>4d} {alpha:>4d} {theta:>8.3f} {hoff:>8.3f} "
              f"{theta-alpha:>6.2f} {alpha_over_theta:>6.3f} "
              f"{theta_over_hoff:>6.3f} {r['c_log']:>7.4f} "
              f"{r['source'][:22]:<22s} {', '.join(status)}")

    print("-" * 100)
    print(f"Frontier graphs: {len(front)}, α=θ exact on {n_theta_exact}, "
          f"θ=H exact on {n_theta_hoff}")
    if below_plateau:
        print(f"Below P(17) plateau (c_log<0.679): {len(below_plateau)} — "
              f"{[r['n'] for r in below_plateau]}")
    else:
        print("No frontier graph sits below P(17) plateau (c_log=0.679).")

    # Now look specifically at the P(17) plateau and known extremal
    # benchmark graphs
    print("\n=== SDP tightness on specific benchmark N's ===")
    bench_ns = [17, 19, 22, 25, 28, 36, 40, 45, 60, 64, 80, 85, 92]
    for n in bench_ns:
        r = next((x for x in front if x["n"] == n), None)
        if not r: continue
        alpha = r["alpha"]
        theta = r["lovasz_theta"]
        # Hoffman already in-loop but redo for print
        ev = r["eigenvalues_adj"]
        if isinstance(ev, str): ev = json.loads(ev)
        lam_min = min(ev)
        d = r["regularity_d"] if r["is_regular"] else r["d_max"]
        hoff = n * (-lam_min) / (d - lam_min) if d > lam_min else float("nan")
        # Integer-rounded θ (bound on α)
        print(f"  N={n:3d}: α={alpha:3d}, θ={theta:.3f}, ⌊θ⌋={int(theta):3d}, "
              f"H={hoff:.3f}, c_log={r['c_log']:.4f}  [src={r['source']}]")


if __name__ == "__main__":
    main()
