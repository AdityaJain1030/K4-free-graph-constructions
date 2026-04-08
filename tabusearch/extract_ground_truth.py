"""Extract ground truth from k4free_db pkl files into ground_truth.json."""
import json
import math
import os
import pickle
import sys


def main():
    db_dir = sys.argv[1] if len(sys.argv) > 1 else "./k4free_db"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "ground_truth.json"

    gt = {}  # "(n, d)" -> {"min_alpha": ..., "c_value": ...}

    for fname in sorted(os.listdir(db_dir)):
        if not fname.endswith(".pkl"):
            continue
        with open(os.path.join(db_dir, fname), "rb") as f:
            data = pickle.load(f)

        n = data["n"]
        # data["graphs"] is {(d, alpha): [sparse6_str, ...]}
        # Find min alpha for each d
        min_alpha_by_d = {}
        for (d, a), graphs in data["graphs"].items():
            if d not in min_alpha_by_d or a < min_alpha_by_d[d]:
                min_alpha_by_d[d] = a

        for d, a in min_alpha_by_d.items():
            if d <= 1:
                continue
            c_val = a * d / (n * math.log(d))
            gt[f"({n}, {d})"] = {
                "min_alpha": a,
                "c_value": round(c_val, 6),
                "n": n,
                "d": d,
            }

    with open(out_path, "w") as f:
        json.dump(gt, f, indent=2, sort_keys=True)

    print(f"Saved {len(gt)} (n,d) pairs to {out_path}")

    # Print summary
    print(f"\n{'n':>3}  {'d':>3}  {'min_alpha':>9}  {'c_value':>8}")
    print("-" * 30)
    for key in sorted(gt.keys(), key=lambda k: eval(k)):
        info = gt[key]
        print(f"{info['n']:>3}  {info['d']:>3}  {info['min_alpha']:>9}  {info['c_value']:>8.4f}")


if __name__ == "__main__":
    main()
