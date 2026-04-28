# Canonical IDs — why we shell out to `labelg` and not pynauty

## TL;DR

`canonical_id(G)` (in `utils/nauty.py`, re-exported as
`graph_db.encoding.canonical_id`) shells out to nauty's `labelg` binary
rather than calling `pynauty.certificate()` in-process. One subprocess
per call (~3 ms), or one per batch via `canonical_ids(list[G])`.

This is a **deliberate choice**, not a stopgap. The rest of this doc
explains why, so future-us doesn't reflexively try to "optimize" this
back to pynauty.

## Background — what canonical_id does

For every graph saved into `graph_db`, we compute

```
canonical_id = SHA-256[:16]( canonical_sparse6(G) )
```

where `canonical_sparse6` is the graph's canonical labelling under
nauty. Two isomorphic graphs → same id → same row in `cache.db`. This
is how we detect that SAT and circulant both rediscovered P(17), how
`clean` repairs rows with wrong ids, and how the cache stays consistent
across reruns. See `graph_db/DESIGN.md` §"Why canonical_id" for the
full rationale.

## Why not pynauty

pynauty is a Python C-extension that ships with a **bundled copy of
nauty sources** inside its sdist (`src/nauty2_8_8/` in pynauty
2.8.8.1). `pip install pynauty` builds that bundled nauty into
`pynauty/nautywrap.so` with whatever `CFLAGS` the Python sysconfig /
wheel-builder chose. In practice that means `-march=native` on the
build host, which produces a `.so` that will `SIGILL` on any CPU that
isn't a strict superset of the build host's instruction set.

On the Illinois CS HTCondor pool this bit us: jobs submitted to
`vision-c23.cs.illinois.edu` landed on an execute host that did not
implement the AVX-class instructions pynauty's `nautywrap.so` had been
compiled with, and the proof pipeline crashed the moment it tried to
compute a canonical id:

```
Fatal Python error: Illegal instruction
  File ".../pynauty/graph.py", line 196 in certificate
  File ".../utils/pynauty.py", line 65 in _canonical_sparse6_pynauty
  ...
```

The nauty we built ourselves (`scripts/setup_nauty.sh` → `geng`,
`labelg`, …) worked fine across the whole pool — those are **separately
compiled binaries**, not the bundled-into-pynauty copy.

## Why `labelg` is the right escape hatch

- **Separation of concerns.** pynauty = one Python extension that
  bundles and recompiles nauty; labelg = standalone CLI, part of
  nauty itself. Keeping only the latter means one build path
  (`setup_nauty.sh`) produces one set of artifacts, used for both
  `geng` (brute-force enumeration) and `labelg` (canonical ids).
- **No C extension to portability-harden.** The SIGILL failure mode
  goes away. Whatever CPU extensions nauty was compiled against, it's
  the same binary exec'd by the same user on the same execute host.
- **Same underlying algorithm.** labelg and pynauty both call nauty's
  canonical labelling with default options. Verified byte-for-byte
  agreement over 253/253 committed records in `graphs/*.json` and
  80/80 random graphs spanning n = 3 … 150 (including the n = 64/65
  setword-boundary that previously tripped our pynauty decoder; see
  the historical note in `experiments/alpha/ALPHA_PERFORMANCE.md`).

## Performance

Per-call (n ≤ 30, local WSL2):

| mode                        | time/graph |
|-----------------------------|------------|
| pynauty in-process          | ≈ 30 µs    |
| labelg subprocess (single)  | ≈ 3 ms     |
| labelg subprocess (batched) | ≈ 1.5 ms   |

Where this matters in the codebase:

| call site                                       | volume            | verdict                     |
|-------------------------------------------------|-------------------|-----------------------------|
| `graph_db/store.py::add_graph` (proof pipeline) | tens/run          | irrelevant                  |
| `graph_db/clean.py`                             | one-shot repair   | irrelevant                  |
| `funsearch/experiments/.../canonical_cert`      | per-candidate     | use `canonical_ids` batched |
| `utils/nauty.py::graphs_via_python`             | only n ≤ 6        | irrelevant                  |

The recommended idiom for hot paths is the batched form:

```python
from utils.nauty import canonical_ids
ids = canonical_ids(list_of_graphs)   # one labelg subprocess total
```

## Could we rebuild pynauty against our nauty 2.9.3?

Asked, answered, doesn't help. Summary:

- pynauty's `setup.py` hardcodes `src/nauty2_8_8/` as the directory it
  links against (via the `_nauty_dir` constant in
  `src/pynauty/__init__.py`). You can point it at our `nauty2_9_3/`:

  ```bash
  pip download --no-binary pynauty --no-deps pynauty==2.8.8.1 -d /tmp/pyn
  tar -xzf /tmp/pyn/pynauty-2.8.8.1.tar.gz -C /tmp/pyn
  cd /tmp/pyn/pynauty-2.8.8.1
  rm -r src/nauty2_8_8
  ln -s "$CONDA_PREFIX/src/nauty2_9_3" src/nauty2_9_3
  sed -i "s/nauty2_8_8/nauty2_9_3/g" src/pynauty/__init__.py
  CFLAGS="-O3 -march=x86-64-v2 -mtune=generic" pip install --no-binary pynauty .
  ```

- The nauty API is near-identical between 2.8.8 and 2.9.3 — the 5 `.c`
  files pynauty links (`nauty.c`, `nautil.c`, `naugraph.c`,
  `schreier.c`, `naurng.c`) differ by at most a handful of lines.
- **But this doesn't solve the portability problem.** nauty 2.9.3's
  default `./configure` emits `CFLAGS="-O4 -march=native -mtune=native"`,
  so `nauty.o`/etc. would still be hardware-specific. You'd need
  `--enable-generic` + portable CFLAGS on the nauty build too. At which
  point you've reinvented "portable pynauty install", with extra
  plumbing and a forked build recipe to maintain, gaining only ≈3 ms
  per canonical_id call — already close to zero relative to the
  per-graph SAT work.

Net: **not worth it**.

## If `labelg` ever becomes the bottleneck

Batching via `canonical_ids()` should be the first lever. If that
still isn't enough, the right escape hatch is **not** pynauty; it's
ctypes/cffi bindings against `libnauty.a` from our nauty 2.9.3 —
genuinely in-process, no pynauty fork, still exactly one nauty build
to care about. That would be a ~100-line bindings module; propose it
if profiling demands.

## Minimal repro for the original SIGILL

For future debugging. On the affected execute host, with the k4free
env active:

```
python -c "import pynauty as p; g=p.Graph(3); g.connect_vertex(0,[1,2]); print(p.certificate(g))"
```

If that SIGILLs, it's a pynauty-on-this-CPU compile-flag mismatch. The
labelg pipeline does not rely on pynauty, so the proof pipeline is
unaffected.

## Related

- `utils/nauty.py` — implementation.
- `graph_db/DESIGN.md` — why canonical_id is the graph-db primary key.
- `experiments/alpha/ALPHA_PERFORMANCE.md` — historical bug in the previous pynauty
  certificate decoder at n ≥ 65 (fully moot now).
- `scripts/setup_nauty.sh` — builds nauty 2.9.3 and puts `labelg` +
  `geng` on `PATH` via a conda activation hook.
