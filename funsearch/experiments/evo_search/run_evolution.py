#!/usr/bin/env python3
"""
Evolutionary search for K₄-free graphs minimizing c = α·d_max / (N·ln d_max).

Runs 4 independent populations (N=30, 40, 50, 60) round-robin indefinitely
until Ctrl+C. Saves checkpoints every 10 gens, best graphs every 100 gens.

Usage:
    micromamba run -n funsearch python experiments/evo_search/run_evolution.py
"""

import csv
import importlib.util
import json
import math
import os
import random
import signal
import sys
import time
from collections import defaultdict

import numpy as np

sys.stdout.reconfigure(line_buffering=True)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bd = _load_module(
    "block_decomp",
    os.path.join(_HERE, "..", "block_decomposition", "run_experiment.py"),
)
alpha_sat = _bd.alpha_sat
alpha_exact = _bd.alpha_exact
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value
adj_to_graph6 = _bd.adj_to_graph6


TARGET_NS = [30, 40, 50, 60]
POP_SIZE = 20
OFFSPRING_PER_PARENT = 2
P17_BASELINE = 0.6789
OUTDIR = _HERE
TRAJECTORY_PATH = os.path.join(OUTDIR, "trajectory.csv")


# =============================================================================
# K₄-free primitives
# =============================================================================

def compute_nbr_masks(adj):
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        m = 0
        for j in range(n):
            if adj[i, j]:
                m |= 1 << j
        nbr[i] = m
    return nbr


def would_create_k4(nbr, u, v):
    """Adding (u,v) creates K4 iff N(u) ∩ N(v) contains an edge."""
    common = nbr[u] & nbr[v]
    tmp = common
    while tmp:
        c = (tmp & -tmp).bit_length() - 1
        if nbr[c] & (common & ~(1 << c)):
            return True
        tmp &= tmp - 1
    return False


def adj_edges(adj):
    N = adj.shape[0]
    return [(u, v) for u in range(N) for v in range(u + 1, N) if adj[u, v]]


def adj_non_edges(adj):
    N = adj.shape[0]
    return [(u, v) for u in range(N) for v in range(u + 1, N) if not adj[u, v]]


# =============================================================================
# Seeding
# =============================================================================

def paley17_adj():
    """Paley graph P(17): vertices 0..16, edge (i,j) iff (j-i) is QR mod 17."""
    p = 17
    qr = {pow(i, 2, p) for i in range(1, p)}
    adj = np.zeros((p, p), dtype=np.bool_)
    for i in range(p):
        for j in range(i + 1, p):
            if (j - i) % p in qr:
                adj[i, j] = adj[j, i] = True
    return adj


def seed_paley_padded(N):
    """Disjoint copies of P(17) padded with isolated vertices to size N."""
    p = 17
    pal = paley17_adj()
    adj = np.zeros((N, N), dtype=np.bool_)
    n_copies = N // p
    for c in range(n_copies):
        off = c * p
        for i in range(p):
            for j in range(i + 1, p):
                if pal[i, j]:
                    adj[off + i, off + j] = adj[off + j, off + i] = True
    return adj


def seed_random_dcap(N, d_cap, rng):
    """Random edge addition with K₄-free + degree cap."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    degs = [0] * N
    pairs = [(u, v) for u in range(N) for v in range(u + 1, N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if degs[u] >= d_cap or degs[v] >= d_cap:
            continue
        if would_create_k4(nbr, u, v):
            continue
        adj[u, v] = adj[v, u] = True
        nbr[u] |= 1 << v
        nbr[v] |= 1 << u
        degs[u] += 1
        degs[v] += 1
    return adj


def seed_random_k4free(N, rng):
    """Random K₄-free graph: shuffle all edges, add if K₄-free."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    pairs = [(u, v) for u in range(N) for v in range(u + 1, N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if would_create_k4(nbr, u, v):
            continue
        adj[u, v] = adj[v, u] = True
        nbr[u] |= 1 << v
        nbr[v] |= 1 << u
    return adj


def build_seeds(N, rng):
    """5 Paley-padded, 5 random d_cap=6, 5 random d_cap=10, 5 random K₄-free."""
    seeds = []
    for _ in range(5):
        seeds.append(seed_paley_padded(N))
    for _ in range(5):
        seeds.append(seed_random_dcap(N, 6, rng))
    for _ in range(5):
        seeds.append(seed_random_dcap(N, 10, rng))
    for _ in range(5):
        seeds.append(seed_random_k4free(N, rng))
    assert len(seeds) == POP_SIZE
    return seeds


# =============================================================================
# Mutation operators
# =============================================================================

MUTATION_OPS = ["add", "remove", "swap", "rewire", "equalize", "multi_swap"]


def _add_edge(adj, nbr, degs, u, v):
    adj[u, v] = adj[v, u] = True
    nbr[u] |= 1 << v
    nbr[v] |= 1 << u
    degs[u] += 1
    degs[v] += 1


def _remove_edge(adj, nbr, degs, u, v):
    adj[u, v] = adj[v, u] = False
    nbr[u] &= ~(1 << v)
    nbr[v] &= ~(1 << u)
    degs[u] -= 1
    degs[v] -= 1


def op_add(adj, nbr, degs, rng):
    non_edges = adj_non_edges(adj)
    rng.shuffle(non_edges)
    for u, v in non_edges:
        if not would_create_k4(nbr, u, v):
            _add_edge(adj, nbr, degs, u, v)
            return True
    return False


def op_remove(adj, nbr, degs, rng):
    edges = adj_edges(adj)
    if not edges:
        return False
    u, v = rng.choice(edges)
    _remove_edge(adj, nbr, degs, u, v)
    return True


def op_swap(adj, nbr, degs, rng):
    if not op_remove(adj, nbr, degs, rng):
        return False
    op_add(adj, nbr, degs, rng)
    return True


def op_rewire(adj, nbr, degs, rng):
    N = adj.shape[0]
    edges = adj_edges(adj)
    if not edges:
        return False
    u, v = rng.choice(edges)
    _remove_edge(adj, nbr, degs, u, v)
    cands = [w for w in range(N) if w != u and not adj[u, w]
             and not would_create_k4(nbr, u, w)]
    if cands:
        w = rng.choice(cands)
        _add_edge(adj, nbr, degs, u, w)
    return True


def op_equalize(adj, nbr, degs, rng):
    N = adj.shape[0]
    if N == 0 or max(degs) == min(degs):
        return False
    max_deg, min_deg = max(degs), min(degs)
    highs = [v for v in range(N) if degs[v] == max_deg]
    lows = [v for v in range(N) if degs[v] == min_deg]
    v_low = rng.choice(lows)
    v_high = rng.choice(highs)
    add_cands = [w for w in range(N) if w != v_low and not adj[v_low, w]
                 and not would_create_k4(nbr, v_low, w)]
    rem_cands = [w for w in range(N) if adj[v_high, w]]
    if not add_cands or not rem_cands:
        return False
    w_add = rng.choice(add_cands)
    w_rem = rng.choice(rem_cands)
    _add_edge(adj, nbr, degs, v_low, w_add)
    _remove_edge(adj, nbr, degs, v_high, w_rem)
    return True


def op_multi_swap(adj, nbr, degs, rng):
    applied = False
    for _ in range(3):
        if op_swap(adj, nbr, degs, rng):
            applied = True
    return applied


def mutate(parent_adj, rng):
    adj = parent_adj.copy()
    nbr = compute_nbr_masks(adj)
    degs = adj.sum(axis=1).astype(int).tolist()
    op = rng.choice(MUTATION_OPS)
    if op == "add":
        op_add(adj, nbr, degs, rng)
    elif op == "remove":
        op_remove(adj, nbr, degs, rng)
    elif op == "swap":
        op_swap(adj, nbr, degs, rng)
    elif op == "rewire":
        op_rewire(adj, nbr, degs, rng)
    elif op == "equalize":
        op_equalize(adj, nbr, degs, rng)
    elif op == "multi_swap":
        op_multi_swap(adj, nbr, degs, rng)
    return adj


# =============================================================================
# Fitness
# =============================================================================

def sat_timeout_for(N):
    return 30 if N > 50 else 10


def evaluate(adj, N):
    """Return dict with adj, c, alpha, d_max."""
    degs = adj.sum(axis=1).astype(int)
    d_max = int(degs.max()) if len(degs) > 0 else 0
    if d_max < 2:
        return {"adj": adj, "c": float("inf"), "alpha": 0,
                "d_max": d_max, "timed_out": False}
    timeout = sat_timeout_for(N)
    alpha, _, to = alpha_sat(adj, timeout=timeout)
    if to:
        return {"adj": adj, "c": float("inf"), "alpha": int(alpha),
                "d_max": d_max, "timed_out": True}
    c = compute_c_value(int(alpha), N, d_max)
    return {"adj": adj, "c": c, "alpha": int(alpha),
            "d_max": d_max, "timed_out": False}


# =============================================================================
# Evolution step
# =============================================================================

def run_generation(population, best_ever, N, rng, gen):
    """One generation: 40 offspring → top 20 + elitism. Returns (new_pop, new_best, evals)."""
    offspring_adjs = []
    for parent in population:
        for _ in range(OFFSPRING_PER_PARENT):
            offspring_adjs.append(mutate(parent["adj"], rng))

    evaluated = [evaluate(adj, N) for adj in offspring_adjs]
    evaluated.sort(key=lambda x: (x["c"], -x["d_max"]))

    new_pop = evaluated[:POP_SIZE]
    new_best = best_ever

    # Track new best_ever from this gen's offspring
    gen_best = new_pop[0]
    if gen_best["c"] < new_best["c"]:
        new_best = dict(gen_best)
        new_best["generation_found"] = gen
        # Save immediately when all-time best is beaten
        save_best(N, new_best)

    # Elitism: ensure best_ever present in population
    worst_in_pop = new_pop[-1]
    if new_best["c"] < worst_in_pop["c"]:
        new_pop[-1] = {
            "adj": new_best["adj"].copy(),
            "c": new_best["c"],
            "alpha": new_best["alpha"],
            "d_max": new_best["d_max"],
            "timed_out": False,
        }
        new_pop.sort(key=lambda x: (x["c"], -x["d_max"]))

    return new_pop, new_best, len(evaluated)


# =============================================================================
# I/O
# =============================================================================

def adj_to_edgelist(adj):
    N = adj.shape[0]
    return [[int(i), int(j)] for i in range(N) for j in range(i + 1, N) if adj[i, j]]


def _ind_to_json(ind):
    return {
        "edges": adj_to_edgelist(ind["adj"]),
        "c": None if not math.isfinite(ind["c"]) else round(ind["c"], 6),
        "alpha": ind["alpha"],
        "d_max": ind["d_max"],
    }


def save_checkpoint(N, population, best_ever, generation):
    path = os.path.join(OUTDIR, f"checkpoint_N{N}.json")
    tmp = path + ".tmp"
    data = {
        "N": N,
        "generation": generation,
        "timestamp": time.time(),
        "population": [_ind_to_json(ind) for ind in population],
        "best_ever": _best_to_json(best_ever),
    }
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _best_to_json(best):
    return {
        "edges": adj_to_edgelist(best["adj"]),
        "g6": adj_to_graph6(best["adj"]),
        "alpha": best["alpha"],
        "d_max": best["d_max"],
        "c": None if not math.isfinite(best["c"]) else round(best["c"], 6),
        "generation_found": best.get("generation_found", 0),
    }


def save_best(N, best):
    path = os.path.join(OUTDIR, f"best_N{N}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"N": N, **_best_to_json(best)}, f, indent=2)
    os.replace(tmp, path)


def append_trajectory(row):
    exists = os.path.isfile(TRAJECTORY_PATH)
    with open(TRAJECTORY_PATH, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "generation", "N",
                        "best_c", "mean_c", "std_c", "best_ever_c"])
        w.writerow(row)


# =============================================================================
# Logging
# =============================================================================

def log_generation(N, gen, population, best_ever, total_evals, start_time):
    cs = [ind["c"] for ind in population if math.isfinite(ind["c"])]
    best_in_pop = min((ind["c"] for ind in population if math.isfinite(ind["c"])),
                     default=float("inf"))
    mean_c = float(np.mean(cs)) if cs else float("inf")
    std_c = float(np.std(cs)) if cs else 0.0
    elapsed = time.time() - start_time
    eps = total_evals / elapsed if elapsed > 0 else 0.0
    be_c = best_ever["c"] if math.isfinite(best_ever["c"]) else float("inf")
    print(f"  [N={N:2d} gen={gen:5d}] "
          f"best_pop={best_in_pop:.4f} mean={mean_c:.4f} std={std_c:.4f} "
          f"best_ever={be_c:.4f} (α={best_ever['alpha']} "
          f"d={best_ever['d_max']} gen={best_ever.get('generation_found', 0)}) "
          f"elapsed={elapsed/60:.1f}min evals/s={eps:.2f}")


# =============================================================================
# Main
# =============================================================================

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    rng = random.Random(42)
    print("=" * 70)
    print("Evolutionary search for K₄-free graphs — minimize c")
    print(f"  Populations: N in {TARGET_NS}, pop_size={POP_SIZE}")
    print(f"  Offspring/parent={OFFSPRING_PER_PARENT}, 40 offspring/gen/N")
    print(f"  SAT timeouts: 10s (N≤50), 30s (N>50)")
    print(f"  Ctrl+C to stop and save summary")
    print("=" * 70)

    populations = {}
    best_evers = {}
    alerted = {N: False for N in TARGET_NS}
    gen_counts = {N: 0 for N in TARGET_NS}
    start_time = time.time()
    total_evals = 0

    for N in TARGET_NS:
        print(f"\n[init N={N}] seeding population...")
        t0 = time.time()
        seeds = build_seeds(N, rng)
        evaluated = [evaluate(adj, N) for adj in seeds]
        total_evals += len(evaluated)
        evaluated.sort(key=lambda x: (x["c"], -x["d_max"]))
        populations[N] = evaluated
        best = dict(evaluated[0])
        best["generation_found"] = 0
        best_evers[N] = best
        save_best(N, best)
        be_c = best["c"] if math.isfinite(best["c"]) else float("inf")
        print(f"[init N={N}] done in {time.time()-t0:.1f}s, "
              f"best seed c={be_c:.4f} α={best['alpha']} d={best['d_max']}")

    interrupted = [False]

    def handler(sig, frame):
        if interrupted[0]:
            print("\n[Ctrl+C again] forcing immediate exit")
            sys.exit(1)
        interrupted[0] = True
        print("\n[Ctrl+C] finishing current generation then saving...")

    signal.signal(signal.SIGINT, handler)

    print("\n" + "=" * 70)
    print("Starting evolution")
    print("=" * 70)

    try:
        while not interrupted[0]:
            for N in TARGET_NS:
                if interrupted[0]:
                    break
                gen_counts[N] += 1
                gen = gen_counts[N]
                populations[N], best_evers[N], evals = run_generation(
                    populations[N], best_evers[N], N, rng, gen
                )
                total_evals += evals

                # Breakthrough check
                if (not alerted[N] and math.isfinite(best_evers[N]["c"])
                        and best_evers[N]["c"] < P17_BASELINE):
                    print(f"\n{'*' * 70}")
                    print(f"*** BREAKTHROUGH N={N}: c={best_evers[N]['c']:.4f} "
                          f"< P(17) baseline {P17_BASELINE} at gen {gen} ***")
                    print(f"*** α={best_evers[N]['alpha']} "
                          f"d_max={best_evers[N]['d_max']} ***")
                    print(f"{'*' * 70}\n")
                    alerted[N] = True

                if gen % 10 == 0:
                    log_generation(N, gen, populations[N], best_evers[N],
                                   total_evals, start_time)
                    save_checkpoint(N, populations[N], best_evers[N], gen)

                if gen % 100 == 0:
                    save_best(N, best_evers[N])
                    cs = [ind["c"] for ind in populations[N]
                          if math.isfinite(ind["c"])]
                    best_pop_c = min(cs) if cs else float("inf")
                    mean_c = float(np.mean(cs)) if cs else float("inf")
                    std_c = float(np.std(cs)) if cs else 0.0
                    be_c = (best_evers[N]["c"]
                            if math.isfinite(best_evers[N]["c"]) else float("inf"))
                    append_trajectory([
                        round(time.time(), 2), gen, N,
                        round(best_pop_c, 6) if math.isfinite(best_pop_c) else "",
                        round(mean_c, 6) if math.isfinite(mean_c) else "",
                        round(std_c, 6),
                        round(be_c, 6) if math.isfinite(be_c) else "",
                    ])
    except KeyboardInterrupt:
        interrupted[0] = True

    print("\n" + "=" * 70)
    print("Final summary")
    print("=" * 70)
    for N in TARGET_NS:
        save_checkpoint(N, populations[N], best_evers[N], gen_counts[N])
        save_best(N, best_evers[N])
        b = best_evers[N]
        be_c = b["c"] if math.isfinite(b["c"]) else float("inf")
        print(f"  N={N:2d}: best c={be_c:.4f}  α={b['alpha']}  d_max={b['d_max']}  "
              f"(gen {b.get('generation_found', 0)} / total {gen_counts[N]} gens)")
    total_time = time.time() - start_time
    print(f"\n  Total runtime: {total_time/60:.1f} min ({total_time/3600:.2f} h)")
    print(f"  Total evaluations: {total_evals}")
    if total_time > 0:
        print(f"  Avg evaluations/sec: {total_evals/total_time:.2f}")
    print(f"  Artifacts in: {OUTDIR}")


if __name__ == "__main__":
    main()
