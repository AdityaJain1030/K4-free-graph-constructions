"""
k4free_tabu.py
==============
Tabu search for K4-free graphs on N vertices that minimise the size of their
largest triangle-free induced subgraph.

Goal: find a counterexample to the Erdős–Rogers conjecture, which says every
K4-free graph on N vertices contains a triangle-free induced subgraph of size
≥ C·√N·(log N)^c for some c > 0.  We want a graph whose best triangle-free
induced subgraph is SMALLER than this bound.

Score convention: LOWER IS BETTER (we want small triangle-free subgraphs).

Usage
-----
python k4free_tabu.py --N 57 --seed polarity --iters 50000 --tabu_tenure 40
python k4free_tabu.py --N 91 --seed random   --runs 8 --iters 100000

Requirements: Python ≥ 3.9, numpy, networkx  (no GPU needed)
"""

import argparse
import itertools
import json
import math
import os
import random
import time
from collections import deque
from typing import Optional

import networkx as nx
import numpy as np

# ---------------------------------------------------------------------------
# Theoretical bound (the target we are trying to beat)
# ---------------------------------------------------------------------------

def erdos_rogers_bound(N: int, c: float = 0.5) -> float:
    """
    Lower bound from the Erdős–Rogers conjecture:
        f_{3,4}(N) ≥ C · √N · (log N)^c
    We use c = 0.5 as the baseline exponent (the conjectured value with δ > 0
    is c = 0.5 + δ/2; we use 0.5 as the conservative target to beat).
    A counterexample needs score < this value.
    """
    return math.sqrt(N) * (math.log(N) ** c)


# ---------------------------------------------------------------------------
# Fast graph representation using adjacency sets
# ---------------------------------------------------------------------------

class K4FreeGraph:
    """
    Adjacency-set graph representation optimised for:
      - O(d) K4 detection on edge insertion
      - O(d²) triangle counting in a neighbourhood
      - Fast tabu-move generation
    """

    def __init__(self, N: int):
        self.N = N
        self.adj = [set() for _ in range(N)]   # adj[u] = set of neighbours
        self.edge_set = set()                   # frozenset {u,v} pairs as tuples (u<v)
        self.num_edges = 0

    def copy(self) -> "K4FreeGraph":
        g = K4FreeGraph(self.N)
        for u in range(self.N):
            g.adj[u] = set(self.adj[u])
        g.edge_set = set(self.edge_set)
        g.num_edges = self.num_edges
        return g

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def has_edge(self, u: int, v: int) -> bool:
        return v in self.adj[u]

    def _add_edge_unsafe(self, u: int, v: int):
        """Add edge without K4 check (used during construction)."""
        if v not in self.adj[u]:
            self.adj[u].add(v)
            self.adj[v].add(u)
            self.edge_set.add((min(u, v), max(u, v)))
            self.num_edges += 1

    def remove_edge(self, u: int, v: int):
        if v in self.adj[u]:
            self.adj[u].discard(v)
            self.adj[v].discard(u)
            self.edge_set.discard((min(u, v), max(u, v)))
            self.num_edges -= 1

    def would_create_k4(self, u: int, v: int) -> bool:
        """
        Adding edge (u,v) creates a K4 iff there exist two common neighbours
        w1, w2 of u and v such that (w1,w2) is also an edge.
        i.e. the common neighbourhood of u,v contains a triangle.

        Cost: O(|common_nbrs|²) ≤ O(d²)
        """
        common = self.adj[u] & self.adj[v]
        if len(common) < 2:
            return False
        common = list(common)
        for i in range(len(common)):
            for j in range(i + 1, len(common)):
                if common[j] in self.adj[common[i]]:
                    return True
        return False

    def try_add_edge(self, u: int, v: int) -> bool:
        """Add edge if it doesn't create K4.  Returns True if added."""
        if v in self.adj[u]:
            return False  # already exists
        if self.would_create_k4(u, v):
            return False
        self._add_edge_unsafe(u, v)
        return True

    # ------------------------------------------------------------------
    # Scoring: size of largest triangle-free induced subgraph
    # ------------------------------------------------------------------

    def triangle_count_in_subgraph(self, vertices: list[int]) -> int:
        """Count triangles in the subgraph induced by `vertices`."""
        vset = set(vertices)
        count = 0
        for u in vertices:
            nbrs_in = [w for w in self.adj[u] if w in vset and w > u]
            for i in range(len(nbrs_in)):
                for j in range(i + 1, len(nbrs_in)):
                    if nbrs_in[j] in self.adj[nbrs_in[i]]:
                        count += 1
        return count

    def greedy_triangle_free_subgraph(self) -> list[int]:
        """
        Greedy vertex-deletion heuristic:
          While the induced subgraph has triangles,
          remove the vertex participating in the most triangles.
        Returns the surviving vertex set (triangle-free induced subgraph).

        This gives a LOWER BOUND on the true maximum triangle-free induced
        subgraph size — sufficient for a consistent score signal.

        Cost: O(n · d²) per call.
        """
        active = list(range(self.N))
        active_set = set(active)

        while True:
            # Count triangles per vertex within active subgraph
            tri_count = {v: 0 for v in active_set}
            found_triangle = False

            for u in active:
                if u not in active_set:
                    continue
                nbrs = [w for w in self.adj[u] if w in active_set and w > u]
                for i in range(len(nbrs)):
                    for j in range(i + 1, len(nbrs)):
                        if nbrs[j] in self.adj[nbrs[i]]:
                            # triangle: u, nbrs[i], nbrs[j]
                            tri_count[u] += 1
                            tri_count[nbrs[i]] += 1
                            tri_count[nbrs[j]] += 1
                            found_triangle = True

            if not found_triangle:
                break

            # Remove vertex with highest triangle count
            worst = max(active_set, key=lambda v: tri_count[v])
            active_set.discard(worst)
            active = [v for v in active if v in active_set]

        return list(active_set)

    def score(self) -> int:
        """
        Score = size of greedy triangle-free induced subgraph.
        LOWER = BETTER (we want small triangle-free subgraphs).
        """
        return len(self.greedy_triangle_free_subgraph())

    def fast_score_upper(self) -> int:
        """
        Fast upper bound on triangle-free subgraph size using the two-case
        argument from the theory — O(n + m), usable for quick filtering.

        Case 1: max degree d ≥ √N  →  neighbourhood of max-degree vertex is
                K3-free (since graph is K4-free), size = d.
        Case 2: max degree d < √N  →  greedy independent set gives ≥ N/(d+1).

        Returns min of the two bounds — a fast proxy for the true score.
        """
        if self.N == 0:
            return 0
        degrees = [len(self.adj[v]) for v in range(self.N)]
        max_deg = max(degrees)
        sqrt_n = math.sqrt(self.N)

        if max_deg >= sqrt_n:
            # Neighbourhood of highest-degree vertex is triangle-free
            return max_deg
        else:
            # Greedy independent set bound
            return math.ceil(self.N / (max_deg + 1))

    def to_networkx(self) -> nx.Graph:
        G = nx.Graph()
        G.add_nodes_from(range(self.N))
        for u, v in self.edge_set:
            G.add_edge(u, v)
        return G

    def edge_list(self) -> list[tuple[int, int]]:
        return list(self.edge_set)


# ---------------------------------------------------------------------------
# Seed graph generators
# ---------------------------------------------------------------------------

def polarity_graph(q: int) -> K4FreeGraph:
    """
    Erdős–Rényi polarity graph over GF(q), q a prime power.
    Vertices = points of PG(2,q), N = q²+q+1.
    Two points are adjacent iff they are conjugate w.r.t. a non-degenerate
    conic (polarity).  This graph is K4-free and has ~q³/2 edges.
    It is the canonical hard instance for f_{3,4}(n).

    For simplicity we implement the algebraic version for prime q only
    (not prime powers), which covers q = 2,3,5,7,11,13,...
    giving N = 7, 13, 31, 57, 133, 183, ...

    Construction: vertices are triples (x0:x1:x2) in PG(2,Fp).
    Polarity: (x0:x1:x2) ~ (y0:y1:y2) iff x0*y0 + x1*y1 + x2*y2 ≡ 0 (mod q)
    (standard orthogonal polarity — gives a K4-free Ramsey graph).
    """
    # Generate all projective points over GF(q)
    points = []
    for x0 in range(q):
        for x1 in range(q):
            for x2 in range(q):
                if (x0, x1, x2) == (0, 0, 0):
                    continue
                # Canonical representative: first nonzero coord = 1
                for i, c in enumerate((x0, x1, x2)):
                    if c != 0:
                        inv_c = pow(c, q - 2, q)  # modular inverse
                        rep = tuple(
                            (v * inv_c) % q for v in (x0, x1, x2)
                        )
                        break
                points.append(rep)

    # Deduplicate
    points = list(set(points))
    N = len(points)
    assert N == q * q + q + 1, f"Expected {q*q+q+1} points, got {N}"

    point_idx = {p: i for i, p in enumerate(points)}
    g = K4FreeGraph(N)

    for i, (x0, x1, x2) in enumerate(points):
        for j, (y0, y1, y2) in enumerate(points):
            if j <= i:
                continue
            # Adjacent iff x·y = 0 mod q (orthogonal polarity)
            if (x0 * y0 + x1 * y1 + x2 * y2) % q == 0:
                g._add_edge_unsafe(i, j)

    return g


def random_k4free_graph(N: int, target_density: float = 0.3) -> K4FreeGraph:
    """
    Random K4-free graph via random edge insertion with rejection.
    target_density: fraction of N^{3/2} edges to aim for (Kővári–Sós–Turán
    bound for K4-free is O(n^{5/3}), but density ~n^{1/2} per vertex is the
    interesting regime for the Erdős–Rogers bound).
    """
    g = K4FreeGraph(N)
    edges = [(u, v) for u in range(N) for v in range(u + 1, N)]
    random.shuffle(edges)

    target_edges = int(target_density * (N ** 1.5))
    for u, v in edges:
        if g.num_edges >= target_edges:
            break
        g.try_add_edge(u, v)

    return g


def k4free_process_graph(N: int) -> K4FreeGraph:
    """
    The K4-free random process: add uniformly random edges, rejecting any
    that complete a K4, until no more edges can be added (maximal K4-free).
    This is the natural random model for this problem.
    Produces graphs with degree ~ N^{2/5} · polylog, independence ~ N^{2/5}.
    """
    g = K4FreeGraph(N)
    edges = [(u, v) for u in range(N) for v in range(u + 1, N)]
    random.shuffle(edges)
    for u, v in edges:
        g.try_add_edge(u, v)
    return g


def near_turan_graph(N: int, parts: int = 3) -> K4FreeGraph:
    """
    Complete k-partite graph T(N, parts) — densest K_{parts+1}-free graph
    by Turán's theorem.  For parts=3 gives a K4-free graph with ~2N²/9 edges
    and independence number N/3.  Useful as a baseline seed.
    """
    g = K4FreeGraph(N)
    sizes = [(N + i) // parts for i in range(parts)]  # roughly equal parts
    # Fix sizes to sum to N
    sizes[-1] = N - sum(sizes[:-1])

    part_of = []
    for p, sz in enumerate(sizes):
        part_of.extend([p] * sz)

    for u in range(N):
        for v in range(u + 1, N):
            if part_of[u] != part_of[v]:
                g._add_edge_unsafe(u, v)

    return g


SEED_GENERATORS = {
    "polarity": None,      # requires prime q, handled separately
    "random":   random_k4free_graph,
    "process":  k4free_process_graph,
    "turan":    near_turan_graph,
}


# ---------------------------------------------------------------------------
# Tabu Search
# ---------------------------------------------------------------------------

class TabuSearch:
    """
    Tabu search over the space of K4-free graphs on N vertices.

    Move space: edge flips — either ADD a non-present edge (if K4-free) or
    REMOVE a present edge.

    Tabu list: the last `tenure` flipped edges are forbidden from being
    flipped back (standard edge-flip tabu).

    Aspiration criterion: a tabu move is accepted if it produces a score
    strictly better than the best seen so far (overrides tabu status).

    Neighbourhood sampling: for efficiency we don't enumerate all O(n²) 
    possible flips each iteration — we sample a random subset of candidates
    and pick the best non-tabu one.  Full neighbourhood search is available
    via --full_neighborhood flag but is expensive for large N.
    """

    def __init__(
        self,
        graph: K4FreeGraph,
        tabu_tenure: int = 30,
        neighborhood_sample: int = 200,
        full_neighborhood: bool = False,
        aspiration: bool = True,
        verbose: bool = True,
    ):
        self.graph = graph.copy()
        self.best_graph = graph.copy()
        self.best_score = self.graph.score()

        self.tabu_tenure = tabu_tenure
        self.neighborhood_sample = neighborhood_sample
        self.full_neighborhood = full_neighborhood
        self.aspiration = aspiration
        self.verbose = verbose

        # Tabu list: deque of (u,v) edges recently flipped
        self.tabu_list: deque[tuple[int, int]] = deque()
        self.tabu_set: set[tuple[int, int]] = set()

        self.current_score = self.best_score
        self.iteration = 0
        self.history: list[dict] = []

    def _make_tabu(self, edge: tuple[int, int]):
        u, v = min(edge), max(edge)
        canon = (u, v)
        self.tabu_list.append(canon)
        self.tabu_set.add(canon)
        if len(self.tabu_list) > self.tabu_tenure:
            old = self.tabu_list.popleft()
            self.tabu_set.discard(old)

    def _is_tabu(self, u: int, v: int) -> bool:
        return (min(u, v), max(u, v)) in self.tabu_set

    def _candidate_moves(self) -> list[tuple[str, int, int]]:
        """
        Generate candidate moves as (action, u, v) where action ∈ {add, remove}.
        """
        N = self.graph.N
        candidates = []

        if self.full_neighborhood:
            # All possible adds (respecting K4-free) and all removes
            for u in range(N):
                for v in range(u + 1, N):
                    if self.graph.has_edge(u, v):
                        candidates.append(("remove", u, v))
                    else:
                        candidates.append(("add", u, v))
        else:
            # Sample random subset of edges and non-edges
            all_edges = list(self.graph.edge_set)
            all_non_edges = [
                (u, v)
                for u in range(N)
                for v in range(u + 1, N)
                if not self.graph.has_edge(u, v)
            ]

            # Sample proportionally: half adds, half removes
            k = self.neighborhood_sample // 2
            sample_edges = random.sample(all_edges, min(k, len(all_edges)))
            sample_non_edges = random.sample(
                all_non_edges, min(k, len(all_non_edges))
            )

            for u, v in sample_edges:
                candidates.append(("remove", u, v))
            for u, v in sample_non_edges:
                candidates.append(("add", u, v))

        return candidates

    def _apply_move(self, action: str, u: int, v: int) -> bool:
        """Apply move, return True if successful (add may fail K4 check)."""
        if action == "remove":
            self.graph.remove_edge(u, v)
            return True
        else:  # add
            return self.graph.try_add_edge(u, v)

    def _undo_move(self, action: str, u: int, v: int):
        if action == "remove":
            self.graph._add_edge_unsafe(u, v)
        else:
            self.graph.remove_edge(u, v)

    def step(self) -> dict:
        """Execute one tabu search iteration.  Returns iteration info."""
        candidates = self._candidate_moves()
        random.shuffle(candidates)

        best_move = None
        best_move_score = float("inf")
        best_tabu_override = None
        best_tabu_override_score = float("inf")

        for action, u, v in candidates:
            # Try move
            applied = self._apply_move(action, u, v)
            if not applied:
                continue

            move_score = self.graph.score()
            self._undo_move(action, u, v)

            is_tabu = self._is_tabu(u, v)

            if is_tabu:
                # Aspiration: override tabu if strictly improves global best
                if self.aspiration and move_score < self.best_score:
                    if move_score < best_tabu_override_score:
                        best_tabu_override = (action, u, v)
                        best_tabu_override_score = move_score
            else:
                if move_score < best_move_score:
                    best_move = (action, u, v)
                    best_move_score = move_score

        # Choose move: prefer non-tabu, fall back to aspiration override
        chosen_move = None
        chosen_score = float("inf")

        if best_move is not None and best_tabu_override is not None:
            if best_tabu_override_score < best_move_score:
                chosen_move = best_tabu_override
                chosen_score = best_tabu_override_score
            else:
                chosen_move = best_move
                chosen_score = best_move_score
        elif best_move is not None:
            chosen_move = best_move
            chosen_score = best_move_score
        elif best_tabu_override is not None:
            chosen_move = best_tabu_override
            chosen_score = best_tabu_override_score

        if chosen_move is not None:
            action, u, v = chosen_move
            self._apply_move(action, u, v)
            self._make_tabu((u, v))
            self.current_score = chosen_score

            if chosen_score < self.best_score:
                self.best_score = chosen_score
                self.best_graph = self.graph.copy()
        else:
            # No valid move found — randomise to escape
            self._random_restart_partial()
            self.current_score = self.graph.score()

        self.iteration += 1
        info = {
            "iteration": self.iteration,
            "current_score": self.current_score,
            "best_score": self.best_score,
            "num_edges": self.graph.num_edges,
            "tabu_size": len(self.tabu_set),
        }
        self.history.append(info)
        return info

    def _random_restart_partial(self):
        """
        When stuck, flip a random batch of edges to escape the local basin.
        Maintains K4-free constraint.
        """
        all_edges = list(self.graph.edge_set)
        if all_edges:
            n_remove = random.randint(1, max(1, len(all_edges) // 10))
            to_remove = random.sample(all_edges, min(n_remove, len(all_edges)))
            for u, v in to_remove:
                self.graph.remove_edge(u, v)

        N = self.graph.N
        non_edges = [
            (u, v)
            for u in range(N)
            for v in range(u + 1, N)
            if not self.graph.has_edge(u, v)
        ]
        n_add = random.randint(1, max(1, len(non_edges) // 20))
        random.shuffle(non_edges)
        for u, v in non_edges[:n_add]:
            self.graph.try_add_edge(u, v)

        self.current_score = self.graph.score()

    def run(self, n_iterations: int, log_every: int = 500) -> K4FreeGraph:
        """Run tabu search for n_iterations steps."""
        t0 = time.time()
        for i in range(n_iterations):
            info = self.step()
            if self.verbose and (i + 1) % log_every == 0:
                elapsed = time.time() - t0
                bound = erdos_rogers_bound(self.graph.N)
                ratio = info["best_score"] / math.sqrt(self.graph.N)
                print(
                    f"  iter {i+1:6d} | best={info['best_score']:4d} "
                    f"| bound≈{bound:.1f} | score/√N={ratio:.3f} "
                    f"| edges={info['num_edges']:5d} "
                    f"| {elapsed:.1f}s"
                )
        return self.best_graph


# ---------------------------------------------------------------------------
# Multi-run harness
# ---------------------------------------------------------------------------

def run_experiment(args) -> dict:
    N = args.N
    bound = erdos_rogers_bound(N, c=args.bound_exponent)
    sqrt_N = math.sqrt(N)

    print(f"\n{'='*60}")
    print(f"K4-free Erdős–Rogers Tabu Search")
    print(f"N = {N} vertices")
    print(f"Target bound = √N · (log N)^{args.bound_exponent:.2f} ≈ {bound:.2f}")
    print(f"Need best_score < {bound:.1f} for a counterexample")
    print(f"Seed: {args.seed} | Runs: {args.runs} | Iters/run: {args.iters}")
    print(f"Tabu tenure: {args.tabu_tenure} | Neighborhood sample: {args.neighborhood_sample}")
    print(f"{'='*60}\n")

    all_results = []
    global_best_score = float("inf")
    global_best_graph = None

    for run_idx in range(args.runs):
        print(f"--- Run {run_idx + 1}/{args.runs} ---")

        # Build seed graph
        if args.seed == "polarity":
            # Find prime q such that q²+q+1 ≈ N
            q = int(round((-1 + math.sqrt(1 + 4 * N)) / 2))
            # verify q is prime and q²+q+1 == N
            def is_prime(n):
                if n < 2: return False
                for i in range(2, int(n**0.5) + 1):
                    if n % i == 0: return False
                return True
            if is_prime(q) and q * q + q + 1 == N:
                print(f"  Building polarity graph GF({q}), N={N}")
                seed = polarity_graph(q)
            else:
                print(f"  N={N} is not of form q²+q+1 for prime q, falling back to k4free process")
                seed = k4free_process_graph(N)
        elif args.seed == "random":
            seed = random_k4free_graph(N, target_density=args.density)
        elif args.seed == "process":
            seed = k4free_process_graph(N)
        elif args.seed == "turan":
            seed = near_turan_graph(N)
        else:
            raise ValueError(f"Unknown seed: {args.seed}")

        initial_score = seed.score()
        print(f"  Seed: {seed.num_edges} edges, initial score = {initial_score} "
              f"(bound = {bound:.1f}, ratio = {initial_score/sqrt_N:.3f})")

        ts = TabuSearch(
            graph=seed,
            tabu_tenure=args.tabu_tenure,
            neighborhood_sample=args.neighborhood_sample,
            full_neighborhood=args.full_neighborhood,
            aspiration=not args.no_aspiration,
            verbose=True,
        )

        best_graph = ts.run(args.iters, log_every=args.log_every)
        best_score = ts.best_score

        ratio = best_score / sqrt_N
        beats_bound = best_score < bound

        result = {
            "run": run_idx + 1,
            "N": N,
            "best_score": best_score,
            "ratio_to_sqrt_N": ratio,
            "erdos_rogers_bound": bound,
            "beats_conjecture_bound": beats_bound,
            "num_edges": best_graph.num_edges,
            "seed": args.seed,
            "iters": args.iters,
        }
        all_results.append(result)

        print(f"  ✓ Run {run_idx+1} done: best_score={best_score}, "
              f"score/√N={ratio:.4f}, bound/√N={(bound/sqrt_N):.4f}, "
              f"BEATS={'YES ← !!!' if beats_bound else 'no'}")

        if best_score < global_best_score:
            global_best_score = best_score
            global_best_graph = best_graph

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY over {args.runs} runs")
    print(f"  N = {N}")
    print(f"  Erdős–Rogers bound ≈ {bound:.2f}")
    print(f"  Best score found: {global_best_score}")
    print(f"  Best score / √N: {global_best_score/sqrt_N:.4f}")
    print(f"  log(N)^{args.bound_exponent:.2f} factor: {(math.log(N)**args.bound_exponent):.4f}")
    print(f"  Beats bound: {'YES — POTENTIAL COUNTEREXAMPLE' if global_best_score < bound else 'No'}")
    if global_best_graph:
        print(f"  Best graph edges: {global_best_graph.num_edges}")

    # Save results
    if args.output:
        out = {
            "args": vars(args),
            "bound": bound,
            "global_best_score": global_best_score,
            "global_best_score_ratio": global_best_score / sqrt_N,
            "beats_bound": global_best_score < bound,
            "runs": all_results,
        }
        if global_best_graph:
            out["best_graph_edges"] = list(global_best_graph.edge_set)
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n  Results saved to {args.output}")

    return {
        "global_best_score": global_best_score,
        "global_best_graph": global_best_graph,
        "bound": bound,
        "results": all_results,
    }


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def get_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tabu search for Erdős–Rogers K4-free counterexample",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Problem
    p.add_argument("--N", type=int, default=57,
        help="Number of vertices. Best to use q²+q+1 for prime q "
             "(7, 13, 31, 57, 91, 133, 183) to enable polarity graph seeds.")
    p.add_argument("--bound_exponent", type=float, default=0.5,
        help="Exponent c in the bound √N·(log N)^c. "
             "Set to 0.5 for the conservative target; "
             "true conjecture has c=0.5+δ/2 for some δ>0.")

    # Seed
    p.add_argument("--seed", choices=["polarity", "random", "process", "turan"],
        default="polarity",
        help="Seed graph type. 'polarity' = Erdős–Rényi polarity graph "
             "(canonical hard instance, requires N=q²+q+1 for prime q). "
             "'process' = K4-free random process graph. "
             "'random' = random edge insertion. "
             "'turan' = complete 3-partite (Turán) graph.")
    p.add_argument("--density", type=float, default=0.3,
        help="Edge density target for --seed random, as multiple of N^1.5.")

    # Search
    p.add_argument("--runs", type=int, default=4,
        help="Number of independent tabu search runs.")
    p.add_argument("--iters", type=int, default=20000,
        help="Tabu search iterations per run.")
    p.add_argument("--tabu_tenure", type=int, default=30,
        help="Number of iterations an edge flip is forbidden. "
             "Rule of thumb: √(N) to N/5.")
    p.add_argument("--neighborhood_sample", type=int, default=300,
        help="Number of candidate moves sampled per iteration "
             "(ignored if --full_neighborhood).")
    p.add_argument("--full_neighborhood", action="store_true",
        help="Evaluate all O(n²) possible moves per iteration. "
             "Exact but O(n⁴) per iteration — only feasible for N≤30.")
    p.add_argument("--no_aspiration", action="store_true",
        help="Disable aspiration criterion (tabu moves never override).")

    # Logging / output
    p.add_argument("--log_every", type=int, default=1000,
        help="Print progress every this many iterations.")
    p.add_argument("--output", type=str, default="results.json",
        help="Path to save JSON results (edge list of best graph + scores).")
    p.add_argument("--seed_rng", type=int, default=None,
        help="Random seed for reproducibility.")

    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = get_parser()
    args = parser.parse_args()

    if args.seed_rng is not None:
        random.seed(args.seed_rng)
        np.random.seed(args.seed_rng)

    run_experiment(args)