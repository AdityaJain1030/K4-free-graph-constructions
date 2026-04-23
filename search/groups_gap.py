"""
search/groups_gap.py
=====================
GAP SmallGroups bridge for Cayley-graph search.

For a given order n, shells out to GAP and enumerates every group in
the SmallGroups library at that order, emitting each group's full
multiplication table. Python then synthesises the existing
`search.groups.GroupSpec` — elements are integers 0..n-1, the group
operation is a lambda over a precomputed table, the identity and
inverse maps are derived from the table, and inversion orbits are
computed by the existing helper.

This is strictly a *superset* of `search.groups.families_of_order`: it
adds every non-abelian group we were previously missing (Q_8, SL(2,3),
the Frobenius Z_7 ⋊ Z_3, etc.), without changing the downstream tabu
path. `search/cayley_tabu_gap.py` consumes `families_of_order_gap(n)`
in place of the hand-coded enumeration; nothing else changes.

Cache layout: one JSON per order at
`graphs_src/gap_groups/n_XXXX.json`, regenerated on-demand.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from search.groups import GroupSpec


REPO = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO / "graphs_src" / "gap_groups"

# Safety cap. Orders with more than this many SmallGroups (n=256 has
# 56092, n=1024 has ~49e9) are refused. The first local pass stays well
# under this; the cluster sweep will revisit if needed.
MAX_GROUPS_PER_N = 500


# ── GAP binary + shell-out ─────────────────────────────────────────────────


def _gap_binary() -> str:
    """Locate the `gap` executable; raise a helpful error if missing."""
    path = shutil.which("gap")
    if path:
        return path
    raise RuntimeError(
        "GAP binary `gap` not found on PATH. Install via:\n"
        "    micromamba install -n k4free -c conda-forge gap-defaults\n"
        "and re-activate the env (`micromamba activate k4free`)."
    )


_GAP_SCRIPT_TEMPLATE = r"""
SizeScreen([32768, 32768]);;
n := {n};;
nsg := NumberSmallGroups(n);;
if nsg > {cap} then
    Print("CAP ", nsg, "\n");
    QUIT_GAP();
fi;
for k in [1..nsg] do
    g := SmallGroup(n, k);
    elts := Elements(g);
    sd := StructureDescription(g);
    Print("BEGIN\n");
    Print("ID ", n, " ", k, "\n");
    Print("SD ", sd, "\n");
    for i in [1..n] do
        Print("ROW");
        for j in [1..n] do
            Print(" ", Position(elts, elts[i] * elts[j]) - 1);
        od;
        Print("\n");
    od;
    Print("END\n");
od;
QUIT_GAP();
"""


def _gap_dump_order(n: int) -> list[dict]:
    """
    Shell out to GAP, return a list of `{id: [n,k], sd: str, mult:
    n-by-n list[list[int]]}` dicts (one per SmallGroup of order n).

    GAP 4.15 does not execute scripts piped via stdin under `-q -b`;
    we write the script to a temp file and pass it as a positional arg.
    """
    if n <= 0:
        return []
    import tempfile

    script = _GAP_SCRIPT_TEMPLATE.format(n=n, cap=MAX_GROUPS_PER_N)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".g", delete=False, prefix=f"gap_n{n}_"
    ) as fh:
        fh.write(script)
        script_path = fh.name
    try:
        proc = subprocess.run(
            [_gap_binary(), "-q", "-b", script_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(
            f"GAP failed (rc={proc.returncode}) for n={n}:\n"
            f"stderr:\n{proc.stderr}\nstdout head:\n{proc.stdout[:500]}"
        )
    return _parse_gap_output(n, proc.stdout)


def _parse_gap_output(n: int, text: str) -> list[dict]:
    groups: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("CAP "):
            nsg = int(line.split()[1])
            print(
                f"[groups_gap] skipping n={n}: {nsg} SmallGroups exceeds "
                f"cap MAX_GROUPS_PER_N={MAX_GROUPS_PER_N}. "
                f"Raise the cap in groups_gap.py to include it.",
                flush=True,
            )
            return []
        if line == "BEGIN":
            current = {"id": None, "sd": None, "mult": []}
            continue
        if current is None:
            # pre-first-BEGIN noise (shouldn't happen with -q -b)
            continue
        if line.startswith("ID "):
            _, nn, kk = line.split()
            current["id"] = [int(nn), int(kk)]
        elif line.startswith("SD "):
            # keep the rest of the line verbatim (may contain spaces / x / :)
            current["sd"] = line[3:].strip()
        elif line.startswith("ROW"):
            row = [int(x) for x in line[3:].split()]
            if len(row) != n:
                raise RuntimeError(
                    f"GAP emitted row of length {len(row)} != n={n} for "
                    f"id={current.get('id')}"
                )
            current["mult"].append(row)
        elif line == "END":
            if len(current["mult"]) != n:
                raise RuntimeError(
                    f"GAP emitted {len(current['mult'])} rows != n={n} "
                    f"for id={current.get('id')}"
                )
            groups.append(current)
            current = None
    return groups


# ── cache ──────────────────────────────────────────────────────────────────


def _cache_path(n: int) -> Path:
    return CACHE_DIR / f"n_{n:04d}.json"


def load_order(n: int, *, force: bool = False) -> list[dict]:
    """
    Return the cached GAP dump for order n, regenerating if missing or
    `force=True`. Writes the cache file atomically.
    """
    path = _cache_path(n)
    if path.exists() and not force:
        with path.open() as fh:
            return json.load(fh)
    groups = _gap_dump_order(n)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as fh:
        json.dump(groups, fh)
    tmp.replace(path)
    return groups


# ── GroupSpec synthesis ─────────────────────────────────────────────────────


def to_group_spec(entry: dict) -> GroupSpec:
    """
    Build the existing search.groups.GroupSpec from a GAP-dumped entry.

    Elements are integers 0..n-1. The identity is the unique i with
    mult[i][j] == j for all j. Inverse_of[i] is the unique j with
    mult[i][j] == identity. The group op is a closure over the table.
    """
    n_k = entry["id"]
    n = n_k[0]
    sd = entry["sd"]
    mult = entry["mult"]

    # Identity: row i such that mult[i] == [0, 1, ..., n-1].
    identity = -1
    for i, row in enumerate(mult):
        if row == list(range(n)):
            identity = i
            break
    if identity < 0:
        raise RuntimeError(f"no identity row in GAP dump for SmallGroup{tuple(n_k)}")

    # Inverse: for each i, the j such that mult[i][j] == identity.
    inverse_of: dict[int, int] = {}
    for i in range(n):
        row = mult[i]
        j = None
        for jj in range(n):
            if row[jj] == identity:
                j = jj
                break
        if j is None:
            raise RuntimeError(
                f"no inverse for element {i} in SmallGroup{tuple(n_k)}"
            )
        inverse_of[i] = j

    # Closures capture the mult table by reference.
    def op(a: int, b: int, _mult=mult) -> int:
        return _mult[a][b]

    name = _spec_name(n_k, sd)
    return GroupSpec(
        name=name,
        order=n,
        elements=list(range(n)),
        identity=identity,
        inverse_of=inverse_of,
        op=op,
    )


def _spec_name(n_k: Iterable[int], sd: str) -> str:
    n, k = int(n_k[0]), int(n_k[1])
    # Sanitize SD: strip spaces, replace separators with ascii-safe chars.
    # "C4 x C2" -> "C4xC2"; "(C3 x C3) : C4" -> "(C3xC3):C4".
    safe = sd.replace(" ", "")
    return f"SG_{n}_{k}_{safe}"


# ── public entrypoint ──────────────────────────────────────────────────────


def families_of_order_gap(n: int, *, force: bool = False) -> list[GroupSpec]:
    """
    Drop-in replacement for `search.groups.families_of_order(n)` backed
    by GAP's SmallGroups library. Returns every finite group of order n
    in the library, as GroupSpec instances, with deterministic ordering
    (SmallGroup id 1, 2, …, nsg).
    """
    entries = load_order(n, force=force)
    return [to_group_spec(e) for e in entries]


# ── self-check ─────────────────────────────────────────────────────────────


def _self_check(orders: Iterable[int] = (6, 8, 12, 21)) -> None:
    """
    Algebraic sanity check: for each order, dump GAP, build every
    GroupSpec, and verify identity/inverse/closure/orbit coverage.
    Also prints one line per order summarising group counts.
    """
    from search.groups import families_of_order as _handcoded

    for n in orders:
        fams = families_of_order_gap(n)
        hc = _handcoded(n)
        for fam in fams:
            # identity
            for i in range(fam.order):
                assert fam.op(fam.identity, i) == i, f"id.left fail {fam.name}:{i}"
                assert fam.op(i, fam.identity) == i, f"id.right fail {fam.name}:{i}"
            # inverse
            for i in range(fam.order):
                assert fam.op(i, fam.inverse_of[i]) == fam.identity, (
                    f"inverse fail {fam.name}:{i}"
                )
            # associativity spot-check
            for a in range(min(fam.order, 5)):
                for b in range(min(fam.order, 5)):
                    for c in range(min(fam.order, 5)):
                        lhs = fam.op(fam.op(a, b), c)
                        rhs = fam.op(a, fam.op(b, c))
                        assert lhs == rhs, (
                            f"assoc fail {fam.name}:({a},{b},{c})"
                        )
            # inversion orbits partition Γ \ {e}
            covered: set[int] = set()
            for orb in fam.inversion_orbits:
                for g in orb:
                    assert g != fam.identity
                    assert g not in covered, f"orbit dup {fam.name}:{g}"
                    covered.add(g)
            assert len(covered) == fam.order - 1, (
                f"orbit coverage {fam.name}: {len(covered)} vs {fam.order-1}"
            )
        print(
            f"n={n:>3}: gap_groups={len(fams):>3}  hand_coded={len(hc):>2}  "
            f"gap_names=[{', '.join(f.name for f in fams[:4])}{'…' if len(fams) > 4 else ''}]"
        )


if __name__ == "__main__":
    _self_check()
