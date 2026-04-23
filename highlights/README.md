# Highlights — curated K4-free graphs

This directory is a hand-picked slice of the project's graph database
(46 graphs out of ~1200), chosen for what a graph
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

1. **Plateau chains: Paley(17), CR(19), N=22 (lift-invariant families)**
2. **SAT-certified optima, N=10..20 (small-N ground truth)**
3. **Cayley / circulant frontier: non-abelian wins + Pareto-optimal circulants**
4. **Classical / published constructions**
5. **Polarity graphs at large N**

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
