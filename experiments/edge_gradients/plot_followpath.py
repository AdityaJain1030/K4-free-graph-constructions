"""
Plot α(t) trajectories per method from followpath_results.csv.
"""
from __future__ import annotations
import argparse, csv, os, statistics
from collections import defaultdict
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))


METHODS = [
    ("random",          "random",          "C7"),
    ("drop_alpha",      r"drop-$\alpha$ (exact)", "C0"),
    ("drop_e_max",      r"drop-$E_{\max}$ (global hardcore)", "C1"),
    ("drop_l_hc",       r"drop-$L_{HC}$ (local hardcore)", "C5"),
    ("hardcore_comarg", r"$\rho_{uw}$ (hardcore co-marginal)", "C2"),
    ("sdp_X_uw",        r"$X_{uw}$ (SDP $\vartheta$)", "C3"),
    ("lp_xu_plus_xw",   r"LP slack ($x_u + x_w - 1$)", "C4"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "followpath_results.csv"))
    ap.add_argument("--out", default=os.path.join(HERE, "followpath_alpha_trajectory.png"))
    args = ap.parse_args()

    rows = []
    with open(args.csv) as f:
        for r in csv.DictReader(f):
            if int(r["skipped"]):
                continue
            rows.append(r)

    grouped: dict[tuple[str, int], list[int]] = defaultdict(list)
    for r in rows:
        grouped[(r["method"], int(r["t"]))].append(int(r["alpha"]))

    fig, ax = plt.subplots(figsize=(10, 6))
    ts_max = max(int(r["t"]) for r in rows)
    for method, label, color in METHODS:
        ts = sorted({int(r["t"]) for r in rows if r["method"] == method})
        means, stds = [], []
        for t in ts:
            vs = grouped.get((method, t), [])
            if not vs:
                continue
            means.append(statistics.mean(vs))
            stds.append(statistics.stdev(vs) if len(vs) > 1 else 0.0)
        if not means:
            continue
        ax.plot(ts[:len(means)], means, color=color, lw=2, label=label, marker="o", ms=3)
        ax.fill_between(ts[:len(means)],
                        [m - s for m, s in zip(means, stds)],
                        [m + s for m, s in zip(means, stds)],
                        color=color, alpha=0.12)

    ax.set_xlabel("step $t$ (edges added)")
    ax.set_ylabel(r"average $\alpha(G_t)$ across saddles")
    ax.set_title("Saddle-escape gradient following (N=20, 15 α-flat starting graphs, T=20 add-only)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"[plot] wrote {args.out}")


if __name__ == "__main__":
    main()
