#!/usr/bin/env python3
"""
scripts/build_highlights.py
============================
Emit a curated `highlights/` directory with the subset of the DB
a graph theorist would actually want to look at.

What makes it in (targeting ~25 graphs, roughly 5 archetypes):

  1. Paley(17) and its known blow-up chain (N=17, 34, 51, 68, 85).
     The benchmark + its cyclic lifts.
  2. SAT-certified optima (N=10..20). The small-N ground truth.
  3. Strict-frontier cayley_tabu_gap wins (N=28, 36, 40, 80, 92).
     Non-abelian / Frobenius constructions that beat circulants.
  4. Classical published constructions (Mattheus–Verstraete 2023,
     Brown, Clebsch, Shrikhande).
  5. Polarity graphs as larger-N reference points (N ∈ {57, 133, 307, 553}).

Output structure:
    highlights/
      README.md              # what this is + legend
      TABLE.md               # master curated table
      graphs/<slug>.md       # per-graph card (properties + construction)
      s6/<slug>.s6           # bare canonical sparse6 (one per line)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import networkx as nx

REPO = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(REPO))

from graph_db import DB


HIGHLIGHTS = REPO / "highlights"
GRAPHS_DIR = HIGHLIGHTS / "graphs"
S6_DIR = HIGHLIGHTS / "s6"


# ---------------------------------------------------------------------------
# Curation: explicit list of (slug, source, n, extra_filter, significance)
# ---------------------------------------------------------------------------

# (slug, source, n, description, tier)
# `extra` is an optional tiebreaker — dict matched against store metadata.
CURATED: list[dict] = [
    # Tier 1 — Paley(17) and its lifts
    {"slug": "paley17", "source": "cayley", "n": 17,
     "label": "Paley P(17) = Cay(Z_17, QR)", "tier": 1,
     "note": "30-year benchmark. c_log=0.679, α=ω=3, 8-regular, self-complementary SRG(17,8,3,4)."},
    {"slug": "paley17_lift_N34", "source": "cyclic_exhaustive_min", "n": 34,
     "label": "P(17) 2-lift = Cay(Z_34, QR(17)∪(QR(17)+17))", "tier": 1,
     "note": "2-fold cyclic lift of P(17). c_log=0.679 preserved — the plateau that has held for decades."},
    {"slug": "paley17_lift_N51", "source": "cyclic_exhaustive_min", "n": 51,
     "label": "P(17) 3-lift", "tier": 1,
     "note": "3-fold lift. α=9, still c=0.679."},
    {"slug": "paley17_frobenius_N68", "source": "cayley_tabu_gap", "n": 68,
     "label": "P(17) 4-lift realized as Cay(C_17 ⋊ C_4, —)", "tier": 1,
     "note": "Non-obvious Frobenius realisation: same spectrum as cyclic C_68 lift, α/Hoffman identical, but a non-abelian group presentation.",
     "group_match": "C17:C4"},
    {"slug": "paley17_lift_N85", "source": "circulant_fast", "n": 85,
     "label": "P(17) 5-lift", "tier": 1,
     "note": "5-fold lift of P(17). Plateau persists through N=85."},

    # Tier 1b — CR(19) plateau chain (cubic-residue Cayley)
    {"slug": "cr19_N19", "source": "cayley", "n": 19,
     "label": "CR(19) = Cay(Z_19, cubic_residues)", "tier": 1,
     "note": "Cubic-residue Cayley graph on F_19. c_log=0.705, α=4. Generalization of Paley for k=3 residue classes."},
    {"slug": "cr19_lift_N38", "source": "cyclic_exhaustive_min", "n": 38,
     "label": "CR(19) 2-lift", "tier": 1,
     "note": "2-fold cyclic lift of CR(19). α=8, same c_log=0.705."},
    {"slug": "cr19_lift_N57", "source": "cayley_tabu", "n": 57,
     "label": "CR(19) 3-lift", "tier": 1,
     "note": "3-fold lift. α=12, c=0.705 invariant — α/Hoffman ≈ 0.763 conserved."},
    {"slug": "cr19_lift_N76", "source": "cayley_tabu", "n": 76,
     "label": "CR(19) 4-lift", "tier": 1,
     "note": "4-fold lift. α=16, plateau persists."},

    # Tier 1c — N=22 plateau chain (dihedral-seeded, conserved α/Hoff)
    {"slug": "n22_D22", "source": "cayley_tabu", "n": 22,
     "label": "Cay(D_22, —) at N=22", "tier": 1,
     "note": "Dihedral group seed of the N=22 plateau. c_log=0.6995, α=4, α/H=0.574 (big slack, but plateau-conserved)."},
    {"slug": "n22_lift_N44", "source": "cyclic_exhaustive_min", "n": 44,
     "label": "N=22 plateau 2-lift at N=44", "tier": 1,
     "note": "2-fold lift. α=8, same c=0.6995."},
    {"slug": "n22_lift_N66", "source": "cayley_tabu", "n": 66,
     "label": "N=22 plateau 3-lift at N=66", "tier": 1,
     "note": "3-fold lift. α=12, plateau preserved."},
    {"slug": "n22_lift_N88", "source": "cayley_tabu_gap", "n": 88,
     "label": "N=22 plateau 4-lift at N=88 via C_2 × (C_11 ⋊ C_4)", "tier": 1,
     "note": "4-fold lift realized as a non-abelian Cayley. α=16."},

    # Tier 2 — SAT-certified optima (N=10..20, complete small-N ground truth)
    *[{
        "slug": f"sat_exact_N{n}",
        "source": "sat_exact",
        "n": n,
        "label": f"Certified-optimal K4-free graph, N={n}",
        "tier": 2,
        "note": f"CP-SAT-proven minimum c_log over ALL K4-free graphs on {n} vertices.",
    } for n in range(10, 21)],

    # Tier 3 — strict frontier wins from GAP sweep
    {"slug": "D28_N28_win", "source": "cayley_tabu_gap", "n": 28,
     "label": "Cay(D_28, —) beating circulants at N=28", "tier": 3,
     "note": "Dihedral group wins over cyclic on 28 vertices. c=0.7708 (was 0.7755 via circulant).",
     "group_match": "D28"},
    {"slug": "S3xS3_N36_win", "source": "cayley_tabu_gap", "n": 36,
     "label": "Cay(S_3 × S_3, —)", "tier": 3,
     "note": "Non-abelian group beats every abelian Cayley and circulant at N=36. Δ=−0.0203 — biggest win of the GAP sweep at small N.",
     "group_match": "S3xS3"},
    {"slug": "C4xD10_N40_win", "source": "cayley_tabu_gap", "n": 40,
     "label": "Cay(C_4 × D_10, —)", "tier": 3,
     "note": "c=0.7195 at N=40; realization of a plateau that recurs at N=60, 80, etc.",
     "group_match": "C4xD10"},
    {"slug": "C5_semi_C8xC2_N80_win", "source": "cayley_tabu_gap", "n": 80,
     "label": "Cay(C_5 ⋊ (C_8 × C_2), —) at N=80", "tier": 3,
     "note": "Semidirect product beats circulant_fast on 80 vertices.",
     "group_match": "C5:(C8xC2)"},
    {"slug": "C92_N92_win", "source": "cayley_tabu_gap", "n": 92,
     "label": "Cay(C_92, —)", "tier": 3,
     "note": "Cyclic group at N=92 — GAP sweep found a better connection set than circulant_fast. Δ=−0.084 — biggest win overall.",
     "group_match": "C92"},

    # Tier 3b — Frobenius / exotic smallgroup at other Ns
    {"slug": "C7xC3_N21_frobenius", "source": "cayley_tabu_gap", "n": 21,
     "label": "Cay(C_7 ⋊ C_3, —) — Frobenius F_21", "tier": 3,
     "note": "The Frobenius group of order 21 gives c=0.7328 — tied, but it was entirely outside the hand-coded search space until the GAP extension.",
     "group_match": "C7:C3"},

    # Tier 3c — sat_circulant_optimal unique-frontier records (Pareto-optimal
    # circulants where no other source ties).
    {"slug": "satcopt_N14", "source": "sat_circulant_optimal", "n": 14,
     "label": "Pareto-optimal circulant Cay(Z_14, —)", "tier": 3,
     "note": "Best circulant at N=14. Matches the SAT-certified overall optimum; the circulant extremum *is* the extremum."},
    {"slug": "satcopt_N15", "source": "sat_circulant_optimal", "n": 15,
     "label": "Pareto-optimal circulant Cay(Z_15, —)", "tier": 3,
     "note": "Best circulant at N=15. The SAT-certified overall extremum is *non-Cayley* here — this is the cyclic-group best, weaker than sat_exact."},
    {"slug": "satcopt_N61", "source": "sat_circulant_optimal", "n": 61,
     "label": "Pareto-optimal circulant Cay(Z_61, —)", "tier": 3,
     "note": "UNIQUE-frontier: at N=61 no other source (Cayley, polarity, GAP, etc.) reaches this c_log. c=0.8544."},
    {"slug": "satcopt_N62", "source": "sat_circulant_optimal", "n": 62,
     "label": "Pareto-optimal circulant Cay(Z_62, —)", "tier": 3,
     "note": "UNIQUE-frontier at N=62. c=0.7789, α=10, d=12."},
    {"slug": "satcopt_N71", "source": "sat_circulant_optimal", "n": 71,
     "label": "Pareto-optimal circulant Cay(Z_71, —)", "tier": 3,
     "note": "UNIQUE-frontier at N=71 (prime; only C_71 available, tabu can't compete)."},
    {"slug": "satcopt_N73", "source": "sat_circulant_optimal", "n": 73,
     "label": "Pareto-optimal circulant Cay(Z_73, —)", "tier": 3,
     "note": "UNIQUE-frontier at N=73 (prime). Beats polarity ER(8) same N."},
    {"slug": "satcopt_N79", "source": "sat_circulant_optimal", "n": 79,
     "label": "Pareto-optimal circulant Cay(Z_79, —)", "tier": 3,
     "note": "UNIQUE-frontier at N=79 (prime)."},

    # Tier 4 — classical published constructions
    {"slug": "brown_N125", "source": "brown", "n": 125,
     "label": "Brown graph (Reiman–Brown 1966)", "tier": 4,
     "note": "Classical extremal construction of R(3,k) lower bound. 30-regular on 125. K4-free but not optimal today (c=1.41)."},
    {"slug": "mattheus_verstraete_N12", "source": "mattheus_verstraete", "n": 12,
     "label": "Mattheus–Verstraete 2023 base construction (N=12)", "tier": 4,
     "note": "From the 2023 R(4,k) lower bound paper. Tiny example showing the construction template."},
    {"slug": "mattheus_verstraete_N63", "source": "mattheus_verstraete", "n": 63,
     "label": "Mattheus–Verstraete 2023 (N=63)", "tier": 4,
     "note": "Larger instance from the same paper. 22-regular, α=17/18, c≈1.92-2.03 — not c_log-optimal but structurally important."},

    # Tier 4b — classical SRGs realized as Cayley (from special_cayley)
    {"slug": "clebsch_N16", "source": "special_cayley", "n": 16,
     "label": "Clebsch graph = Cay(Z_2^4, {e_1..e_4, 1111})", "tier": 4,
     "note": "(16, 5, 0, 2) SRG. Folded 5-cube. K_4-free, α=5, Hoffman-saturated.",
     "name_contains": "Clebsch"},
    {"slug": "shrikhande_N16", "source": "special_cayley", "n": 16,
     "label": "Shrikhande graph = Cay(Z_4 × Z_4, ±{(1,0),(0,1),(1,1)})", "tier": 4,
     "note": "(16, 6, 2, 2) SRG. ω=3 (K_4-free). α=4 = Hoffman. One of the two SRGs of those parameters (other is the 4×4 rook graph).",
     "name_contains": "Shrikhande"},

    # Tier 5 — polarity graphs (new large-N records this session)
    {"slug": "polarity_ER7_N57", "source": "polarity", "n": 57,
     "label": "ER polarity ER(7), N=57", "tier": 5,
     "note": "Erdős–Rényi C4-free polarity graph over PG(2,7). Classical reference. K4-free by construction."},
    {"slug": "polarity_ER11_N133", "source": "polarity", "n": 133,
     "label": "ER polarity ER(11), N=133", "tier": 5,
     "note": "NEW-N: first record at N=133. c=1.05 — polarity sits well above frontier but provides baseline."},
    {"slug": "polarity_ER17_N307", "source": "polarity", "n": 307,
     "label": "ER polarity ER(17), N=307", "tier": 5,
     "note": "NEW-N: ER(17) over PG(2,17). 18-regular, α=55, α/H=0.876."},
    {"slug": "polarity_ER23_N553", "source": "polarity", "n": 553,
     "label": "ER polarity ER(23), N=553", "tier": 5,
     "note": "Largest polarity in DB. 24-regular, α=77, α/H=0.769 — most Hoffman-slack of the polarity family."},
]


TIER_NAMES = {
    1: "Plateau chains: Paley(17), CR(19), N=22 (lift-invariant families)",
    2: "SAT-certified optima, N=10..20 (small-N ground truth)",
    3: "Cayley / circulant frontier: non-abelian wins + Pareto-optimal circulants",
    4: "Classical / published constructions",
    5: "Polarity graphs at large N",
}


# ---------------------------------------------------------------------------


def _fmt(x, pat="{:.4f}"):
    return "—" if x is None else pat.format(x)


def _load_store(source: str) -> dict[str, dict]:
    path = REPO / "graphs" / f"{source}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return {rec["id"]: rec for rec in json.load(f)}


def _pick(db: DB, item: dict):
    rows = db.query(source=item["source"], n=item["n"])
    if not rows:
        return None
    store = _load_store(item["source"])
    def meta(r):
        return store.get(r["graph_id"], {}).get("metadata", {})
    # filter by group_match or similar if supplied
    for key in ("group_match", "family_match"):
        if key in item:
            field = "group" if key == "group_match" else "family"
            want = item[key]
            rows = [r for r in rows if want in str(meta(r).get(field, ""))]
    if "name_contains" in item:
        rows = [r for r in rows if item["name_contains"] in str(meta(r).get("name", ""))]
    if not rows:
        return None
    # best c_log
    rows = [r for r in rows if r.get("c_log") is not None]
    if not rows:
        return None
    best = min(rows, key=lambda r: r["c_log"])
    best["__meta__"] = meta(best)
    return best


def _properties(db: DB, row: dict) -> dict:
    gid = row["graph_id"]
    G = db.nx(gid)
    adj = nx.to_numpy_array(G, dtype=float)
    eigs = np.linalg.eigvalsh(adj)
    lam_max, lam_min = float(eigs.max()), float(eigs.min())
    n = G.number_of_nodes()
    m = G.number_of_edges()
    d = row["d_max"]
    H = n * (-lam_min) / (d - lam_min) if d != lam_min else float("inf")
    return {
        "n": n, "m": m, "d_max": d, "d_min": row.get("d_min"),
        "alpha": row["alpha"], "c_log": row["c_log"],
        "girth": row.get("girth"), "n_triangles": row.get("n_triangles"),
        "is_regular": row.get("is_regular"),
        "spectral_radius": lam_max, "lambda_min": lam_min, "hoffman": H,
        "alpha_over_H": row["alpha"] / H if H > 0 else None,
        "sparse6": db.sparse6(gid),
        "graph_id": gid,
    }


def _write_card(item: dict, row: dict, props: dict):
    slug = item["slug"]
    out = GRAPHS_DIR / f"{slug}.md"
    meta = row["__meta__"]
    lines = [
        f"# {item['label']}",
        "",
        f"**Slug:** `{slug}`",
        f"**Significance:** {item['note']}",
        "",
        "## Core properties",
        "",
        "| key | value |",
        "|---|---|",
        f"| N | {props['n']} |",
        f"| m (edges) | {props['m']} |",
        f"| d_max | {props['d_max']} |",
        f"| d_min | {_fmt(props['d_min'], '{:d}') if props['d_min'] is not None else '—'} |",
        f"| regular | {'yes' if props['is_regular'] else 'no'} |",
        f"| α | {props['alpha']} |",
        f"| c_log = α·d_max/(n·ln d_max) | **{_fmt(props['c_log'])}** |",
        f"| girth | {_fmt(props['girth'], '{:d}') if props['girth'] is not None else '—'} |",
        f"| triangles | {_fmt(props['n_triangles'], '{:d}') if props['n_triangles'] is not None else '—'} |",
        f"| spectral radius (λ_max) | {_fmt(props['spectral_radius'])} |",
        f"| λ_min | {_fmt(props['lambda_min'])} |",
        f"| Hoffman H = n(-λ_min)/(d - λ_min) | {_fmt(props['hoffman'])} |",
        f"| α / H (saturation ratio) | {_fmt(props['alpha_over_H'])} |",
        "",
        "## Construction metadata",
        "",
        "```json",
        json.dumps(meta, indent=2),
        "```",
        "",
        "## Canonical sparse6",
        "",
        "```",
        props["sparse6"],
        "```",
        "",
        f"([s6/{slug}.s6](../s6/{slug}.s6) has just the string.)",
        "",
        "## Source",
        "",
        f"- DB source tag: `{row['source']}`",
        f"- graph_id (sha256[:16] of canonical sparse6): `{props['graph_id']}`",
        "",
    ]
    out.write_text("\n".join(lines))
    (S6_DIR / f"{slug}.s6").write_text(props["sparse6"] + "\n")


def _write_manifest(rows: list):
    """Machine-readable manifest consumed by visualizer --highlights."""
    out = HIGHLIGHTS / "index.json"
    manifest = []
    for r in rows:
        i = r["__item__"]
        p = r["__props__"]
        manifest.append({
            "slug": i["slug"],
            "label": i["label"],
            "tier": i["tier"],
            "note": i["note"],
            "source": r["source"],
            "graph_id": r["graph_id"],
            "n": p["n"],
            "c_log": p["c_log"],
            "alpha": p["alpha"],
            "d_max": p["d_max"],
            "hoffman": p["hoffman"],
            "alpha_over_H": p["alpha_over_H"],
        })
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    return out


def _write_index(rows: list):
    # Master TABLE.md
    out = HIGHLIGHTS / "TABLE.md"
    lines = [
        "# Curated highlights — master table",
        "",
        f"{len(rows)} graphs, organized by tier. Full per-graph cards under `graphs/`.",
        "",
        "| tier | slug | label | N | d_max | α | c_log | α/H |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        p = r["__props__"]
        i = r["__item__"]
        lines.append(
            f"| {i['tier']} | [`{i['slug']}`](graphs/{i['slug']}.md) | {i['label']} | "
            f"{p['n']} | {p['d_max']} | {p['alpha']} | "
            f"**{_fmt(p['c_log'])}** | {_fmt(p['alpha_over_H'])} |"
        )
    out.write_text("\n".join(lines) + "\n")

    # README.md
    readme = HIGHLIGHTS / "README.md"
    text = f"""# Highlights — curated K4-free graphs

This directory is a hand-picked slice of the project's graph database
({sum(1 for _ in rows)} graphs out of ~1200), chosen for what a graph
theorist would actually want to look at. The rest of the repo
(`graph_db/`, `search/`, `funsearch/`, etc.) is machinery; this directory
is the endpoints.

## Legend

The single metric every graph here minimises is

```
c_log = α · d_max / (N · ln d_max)
```

where α is the independence number and d_max is max degree.
Lower c_log is a stronger construction. Benchmark is
**Paley(17): c_log ≈ 0.679**, still unbeaten after 30 years.

## Tiers

{chr(10).join(f"{t}. **{TIER_NAMES[t]}**" for t in sorted(TIER_NAMES))}

## How to read a card

Each graph has:
- `graphs/<slug>.md` — properties, spectrum, Hoffman saturation
  ratio α/H, and the canonical sparse6 string.
- `s6/<slug>.s6` — bare sparse6, ready for `nauty/geng/labelg` or
  `networkx.from_sparse6_bytes`.

Start at [TABLE.md](TABLE.md).

## Interactive visualizer

The project's tkinter explorer has a `--highlights` mode that loads
exactly this manifest instead of the full 1200-row DB:

```bash
micromamba run -n k4free python visualizer/visualizer.py --highlights
```

Each graph's sidebar then shows its curated slug, tier, label, and
significance note alongside the standard properties (n, α, c_log,
Hoffman bound H, and α/H saturation ratio). Highlight mode sorts by
(tier, c_log) so the first graph in the list is the headline Paley
benchmark. Layouts supported: spring, circular, shell, Kamada-Kawai.
Highlights supported: MIS vertices, triangles, high-degree nodes,
click-to-select a vertex and its neighborhood.

## Hoffman saturation ratio (α/H)

For a regular graph with smallest adjacency eigenvalue λ_min,
Hoffman's ratio bound gives `α ≤ H := n·(−λ_min) / (d − λ_min)`. A
ratio α/H = 1.000 means the spectrum forces α exactly — no slack to
tighten. Ratio < 1 means there's spectrum-permitted headroom; whether
a different graph with the same spectrum achieves it is the open
question the repo's sweeps keep banging on.

## Manifest

`index.json` is the machine-readable manifest (slug, graph_id,
source, n, c_log, α, d_max, Hoffman, α/H, tier, label, note). The
visualizer's `--highlights` flag reads it; custom tools can too.
"""
    readme.write_text(text)


def main():
    HIGHLIGHTS.mkdir(exist_ok=True)
    GRAPHS_DIR.mkdir(exist_ok=True)
    S6_DIR.mkdir(exist_ok=True)

    selected = []
    with DB() as db:
        for item in CURATED:
            row = _pick(db, item)
            if row is None:
                print(f"  SKIP (no match): {item['slug']}  (source={item['source']}, n={item['n']})")
                continue
            props = _properties(db, row)
            row["__props__"] = props
            row["__item__"] = item
            selected.append(row)
            _write_card(item, row, props)
            print(f"  wrote graphs/{item['slug']}.md  (c_log={_fmt(props['c_log'])})")

    _write_index(selected)
    man = _write_manifest(selected)
    print(f"\nWrote {len(selected)} cards + s6 + TABLE.md + README.md + index.json to {HIGHLIGHTS}")
    print(f"Manifest for visualizer: {man}")


if __name__ == "__main__":
    main()
