"""Run the full greedy search pipeline and consolidate results."""
import csv
import json
import math
import os
import sys

sys.stdout.reconfigure(line_buffering=True)

from k4free_greedy import search_for_n, compute_c_value

def main():
    os.makedirs("results", exist_ok=True)

    all_results = []
    min_c_per_n = {}

    # Small n: more trials since it's cheap
    configs = [
        (10, 500, 2000),
        (15, 400, 2000),
        (20, 300, 2000),
        (25, 200, 1500),
        (30, 150, 1500),
        (35, 100, 1000),
        (40, 80, 1000),
    ]

    for n, trials, sa_iters in configs:
        print(f"\n>>> Starting n={n} with {trials} trials", flush=True)
        results = search_for_n(n, trials=trials, sa_iters=sa_iters, seed=42)
        all_results.extend(results)

        for r in results:
            key = r['n']
            if key not in min_c_per_n or r['c_value'] < min_c_per_n[key]['c_value']:
                min_c_per_n[key] = r

    # Write CSV
    csv_path = "results/greedy_results.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'n', 'alpha_target', 'alpha_achieved', 'd_max',
            'num_edges', 'c_value', 'trials', 'time_seconds', 'phase'
        ])
        writer.writeheader()
        for r in all_results:
            writer.writerow(r)
    print(f"\nAll results saved to {csv_path}")

    # Print final summary
    print("\n" + "=" * 60)
    print("  MIN C VALUES BY N")
    print("=" * 60)
    for n in sorted(min_c_per_n.keys()):
        r = min_c_per_n[n]
        print(f"  n={n:>3}:  c={r['c_value']:.4f}  "
              f"(alpha={r['alpha_achieved']}, d={r['d_max']})")

    # Also save summary JSON
    summary = {}
    for n in sorted(min_c_per_n.keys()):
        r = min_c_per_n[n]
        summary[str(n)] = {
            'min_c': round(r['c_value'], 6),
            'alpha': r['alpha_achieved'],
            'd_max': r['d_max'],
            'num_edges': r['num_edges'],
        }
    with open("results/summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
