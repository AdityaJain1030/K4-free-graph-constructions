"""
experiments/fragility/move_taxonomy.py
======================================
Move-family primitives for the fragility experiments.

Each move is a transformation `adj -> adj'` on a K4-free graph. The
move set is the adjacency relation that defines the graph
G_N = (K4-free graphs on N vertices, M-moves) on which the energy
c_log lives. Different moves give different landscapes — they're
not interchangeable.

The taxonomy:

| Move       | Δ|E| | Preserves                |
|------------|------|--------------------------|
| add        | +1   | nothing                  |
| delete     | -1   |  nothing                 |
| flip       |  0   | |E|                      |
| slide      |  0   | deg(u) for shared vertex |
| switch     |  0   | full degree sequence     |

For each move we expose three functions:
    * `enumerate_<move>(adj)`     -> list of legal proposals (for Test A
                                     distributional probes; full enumeration
                                     when feasible)
    * `sample_<move>(adj, rng)`   -> a single random legal proposal or None
    * `best_<move>(adj, score_fn)` -> argmin over proposals' c_log delta
                                      (for Test E greedy descent)

`slide` and `switch` defer to existing `utils/edge_switch.py` for the
single-sample primitive, but provide enumeration helpers locally.

All adjacency matrices are uint8 numpy arrays, symmetric, zero diagonal.
A "proposal" is the new adjacency matrix; we never return the move
description separately.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator

import numpy as np

from utils.edge_switch import (
    random_switch,
    random_walk_move as _random_slide,
    safe_switch,
)
from utils.graph_props import (
    adding_induces_k4,
    find_k4,
    is_k4_free,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _edges(adj: np.ndarray) -> list[tuple[int, int]]:
    n = adj.shape[0]
    return [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]


def _non_edges(adj: np.ndarray) -> list[tuple[int, int]]:
    n = adj.shape[0]
    return [(i, j) for i in range(n) for j in range(i + 1, n) if not adj[i, j]]


def _toggle(adj: np.ndarray, edges_off: Iterable[tuple[int, int]],
            edges_on: Iterable[tuple[int, int]]) -> np.ndarray:
    new = adj.copy()
    for u, v in edges_off:
        new[u, v] = new[v, u] = 0
    for u, v in edges_on:
        new[u, v] = new[v, u] = 1
    return new


# ---------------------------------------------------------------------------
# add: G + e for a non-edge e that does not create K4
# ---------------------------------------------------------------------------

def enumerate_add(adj: np.ndarray) -> list[np.ndarray]:
    out = []
    for u, v in _non_edges(adj):
        if not adding_induces_k4(adj, u, v):
            new = adj.copy()
            new[u, v] = new[v, u] = 1
            out.append(new)
    return out


def sample_add(adj: np.ndarray, rng: _random.Random,
               max_attempts: int = 50) -> np.ndarray | None:
    nes = _non_edges(adj)
    if not nes:
        return None
    rng.shuffle(nes)
    for u, v in nes[:max_attempts]:
        if not adding_induces_k4(adj, u, v):
            new = adj.copy()
            new[u, v] = new[v, u] = 1
            return new
    return None


# ---------------------------------------------------------------------------
# delete: G - e — always K4-free-preserving
# ---------------------------------------------------------------------------

def enumerate_delete(adj: np.ndarray) -> list[np.ndarray]:
    out = []
    for u, v in _edges(adj):
        new = adj.copy()
        new[u, v] = new[v, u] = 0
        out.append(new)
    return out


def sample_delete(adj: np.ndarray, rng: _random.Random) -> np.ndarray | None:
    es = _edges(adj)
    if not es:
        return None
    u, v = rng.choice(es)
    new = adj.copy()
    new[u, v] = new[v, u] = 0
    return new


# ---------------------------------------------------------------------------
# flip: G - e1 + e2 on disjoint edge / non-edge pair, preserves |E|
# ---------------------------------------------------------------------------

def enumerate_flip(adj: np.ndarray, *,
                   max_proposals: int | None = None) -> list[np.ndarray]:
    """Cartesian product of (delete one edge) × (add one non-edge that
    does not create K4 in the deleted graph). At N=20 this is ~|E|·|non-edge|
    which can be large; cap with `max_proposals` if needed."""
    out = []
    es = _edges(adj)
    nes = _non_edges(adj)
    for u1, v1 in es:
        adj_minus = adj.copy()
        adj_minus[u1, v1] = adj_minus[v1, u1] = 0
        for u2, v2 in nes:
            if not adding_induces_k4(adj_minus, u2, v2):
                new = adj_minus.copy()
                new[u2, v2] = new[v2, u2] = 1
                out.append(new)
                if max_proposals is not None and len(out) >= max_proposals:
                    return out
    return out


def sample_flip(adj: np.ndarray, rng: _random.Random,
                max_attempts: int = 50) -> np.ndarray | None:
    es = _edges(adj)
    nes = _non_edges(adj)
    if not es or not nes:
        return None
    for _ in range(max_attempts):
        u1, v1 = rng.choice(es)
        u2, v2 = rng.choice(nes)
        adj_minus = adj.copy()
        adj_minus[u1, v1] = adj_minus[v1, u1] = 0
        if not adding_induces_k4(adj_minus, u2, v2):
            adj_minus[u2, v2] = adj_minus[v2, u2] = 1
            return adj_minus
    return None


# ---------------------------------------------------------------------------
# slide: G - uv + uw with u shared, w non-neighbour of u (deg(u) preserved)
# ---------------------------------------------------------------------------

def enumerate_slide(adj: np.ndarray, *,
                    max_degree_spread: int | None = None) -> list[np.ndarray]:
    """All single-edge slides. Optionally filter by degree-spread cap.
    The v0 fragility used spread cap = 2; we expose it as a parameter."""
    n = adj.shape[0]
    out = []
    for u, v in _edges(adj):
        for orient in (0, 1):
            uu, vv = (u, v) if orient == 0 else (v, u)
            for w in range(n):
                if w == uu or w == vv or adj[uu, w]:
                    continue
                new = adj.copy()
                new[uu, vv] = new[vv, uu] = 0
                new[uu, w] = new[w, uu] = 1
                if find_k4(new) is not None:
                    continue
                if max_degree_spread is not None:
                    degs = new.sum(axis=1)
                    if int(degs.max()) - int(degs.min()) > max_degree_spread:
                        continue
                out.append(new)
    return out


def sample_slide(adj: np.ndarray, rng: _random.Random,
                 *, max_degree_spread: int = 2,
                 max_attempts: int = 50) -> np.ndarray | None:
    """Defer to the existing v0 primitive for compatibility."""
    return _random_slide(adj, rng,
                         max_degree_spread=max_degree_spread,
                         max_attempts=max_attempts)


# ---------------------------------------------------------------------------
# switch: G - e1 - e2 + f1 + f2, preserves the full degree sequence
# ---------------------------------------------------------------------------

def enumerate_switch(adj: np.ndarray, *,
                     max_proposals: int | None = None) -> list[np.ndarray]:
    """All legal K4-free 2-edge switches. For each ordered pair of disjoint
    edges (a,b),(c,d) we try both rewirings (a,c),(b,d) and (a,d),(b,c).
    Cost ~|E|² per graph; cap with `max_proposals`."""
    es = _edges(adj)
    out = []
    seen = set()  # canonicalize: store frozenset of new edge set per result
    for i, e1 in enumerate(es):
        for j in range(i + 1, len(es)):
            e2 = es[j]
            if len({*e1, *e2}) != 4:
                continue
            for rew in ("ac_bd", "ad_bc"):
                new = safe_switch(adj, e1, e2, rewiring=rew)
                if new is None:
                    continue
                # cheap dedup via byte hash of upper triangle
                h = new[np.triu_indices_from(new, k=1)].tobytes()
                if h in seen:
                    continue
                seen.add(h)
                out.append(new)
                if max_proposals is not None and len(out) >= max_proposals:
                    return out
    return out


def sample_switch(adj: np.ndarray, rng: _random.Random,
                  max_attempts: int = 50) -> np.ndarray | None:
    return random_switch(adj, rng, max_attempts=max_attempts)


# ---------------------------------------------------------------------------
# Best-improving proposal under a score function (Test E descent)
# ---------------------------------------------------------------------------

@dataclass
class DescentStep:
    """One step of best-improving descent. `delta` is score(new) - score(old).
    `kind` is 'improve' if delta < 0, 'plateau' if delta == 0, 'stuck' if no
    legal move at all."""
    new_adj: np.ndarray | None
    delta: float
    kind: str  # 'improve' | 'plateau' | 'stuck'


_ENUMERATORS: dict[str, Callable[[np.ndarray], list[np.ndarray]]] = {
    "add":    enumerate_add,
    "delete": enumerate_delete,
    "flip":   enumerate_flip,
    "slide":  enumerate_slide,
    "switch": enumerate_switch,
}


_SAMPLERS: dict[str, Callable[[np.ndarray, _random.Random], np.ndarray | None]] = {
    "add":    sample_add,
    "delete": sample_delete,
    "flip":   sample_flip,
    "slide":  sample_slide,
    "switch": sample_switch,
}


def sample_n_proposals(adj: np.ndarray, kind: str, k: int,
                       rng: _random.Random,
                       *, max_attempts_per: int = 5,
                       dedup: bool = True) -> list[np.ndarray]:
    """Sample up to k legal `kind`-move proposals from `adj` without
    paying the full enumeration cost.

    For each desired sample, calls the per-move single-sampler up to
    `max_attempts_per` times. The samplers are O(|E|) or O(|N(u)|),
    far cheaper than the O(|E|²) full enumerator. Returns *up to* k
    distinct proposals (deduplicated by upper-triangle byte hash if
    `dedup`). Useful for descent loops that want bounded cost per
    step independent of |E|.
    """
    sampler = _SAMPLERS[kind]
    out: list[np.ndarray] = []
    seen: set[bytes] = set()
    for _ in range(k):
        for _ in range(max_attempts_per):
            prop = sampler(adj, rng)
            if prop is None:
                continue
            if dedup:
                h = prop[np.triu_indices_from(prop, k=1)].tobytes()
                if h in seen:
                    continue
                seen.add(h)
            out.append(prop)
            break
    return out


def best_step(adj: np.ndarray,
              score_fn: Callable[[np.ndarray], float | None],
              moves: Iterable[str],
              *,
              rng: _random.Random,
              plateau_eps: float = 1e-12) -> DescentStep:
    """
    Best-improving step over the union of `moves`.

    Returns a DescentStep with kind:
      * 'improve' — found a strictly improving move (delta < -plateau_eps);
                    new_adj is the best one (uniform tie-break among ties).
      * 'plateau' — no improving move, but at least one zero-delta move
                    exists; new_adj is one of them, sampled uniformly.
      * 'stuck'   — no legal proposal at all under any of the moves.

    score_fn is responsible for invalid scores (returns None) — those
    proposals are skipped. For c_log this happens when d_max ≤ 1.
    """
    base = score_fn(adj)
    if base is None:
        return DescentStep(None, 0.0, "stuck")

    best_delta = float("inf")
    best_pool: list[np.ndarray] = []
    plateau_pool: list[np.ndarray] = []
    any_legal = False

    for kind in moves:
        for prop in _ENUMERATORS[kind](adj):
            s = score_fn(prop)
            if s is None:
                continue
            any_legal = True
            d = s - base
            if d < -plateau_eps:
                if d < best_delta - plateau_eps:
                    best_delta = d
                    best_pool = [prop]
                elif abs(d - best_delta) <= plateau_eps:
                    best_pool.append(prop)
            elif abs(d) <= plateau_eps:
                plateau_pool.append(prop)

    if best_pool:
        return DescentStep(rng.choice(best_pool), best_delta, "improve")
    if plateau_pool:
        return DescentStep(rng.choice(plateau_pool), 0.0, "plateau")
    if not any_legal:
        return DescentStep(None, 0.0, "stuck")
    return DescentStep(None, 0.0, "stuck")


# ---------------------------------------------------------------------------
# Move-graph in-degree (used by indicators.py and Test C)
# ---------------------------------------------------------------------------

def move_in_degree(adj: np.ndarray, kind: str) -> int:
    """Number of legal proposals from `adj` under move `kind`."""
    return len(_ENUMERATORS[kind](adj))


def all_move_kinds() -> list[str]:
    return list(_ENUMERATORS.keys())
