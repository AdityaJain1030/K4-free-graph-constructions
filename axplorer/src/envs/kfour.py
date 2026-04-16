"""
KFour environment for Axplorer.

Primal formulation of the K₄-free independence conjecture.

We build G on N vertices and minimize |E(G)| subject to:
  1. G is K₄-free          (no 4-clique)
  2. α(G) ≤ t-1            (no independent set of size t)

self.data stores H = complement(G) for framework compatibility.
Score = |E(H)| = C(N,2) - |E(G)|, maximized by the framework.

Higher score → fewer edges in G → smaller d_avg(G) → tighter lower bound on c:
    c_lb = (t-1) * d_avg / (N * ln(d_avg))
"""

import numpy as np

from src.envs.environment import BaseEnvironment, DataPoint
from src.envs.tokenizers import DenseTokenizer, SparseTokenizerSequenceKTokens, SparseTokenizerSingleInteger
from src.envs.utils import random_symmetry_adj_matrix, sort_graph_based_on_degree
from src.utils import bool_flag


# ─────────────────────────────────────────────────────────────────────────────
# Bitmask helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_nbr_masks(adj: np.ndarray):
    """Build integer bitmask neighbor list from adjacency matrix."""
    N = adj.shape[0]
    nbr = [0] * N
    for i in range(N):
        for j in np.nonzero(adj[i])[0]:
            nbr[i] |= 1 << int(j)
    return nbr


def _has_clique(size: int, candidates: int, nbr: list) -> bool:
    """
    Return True iff the subgraph induced by `candidates` (a bitmask) contains
    a clique of `size` vertices, using the provided neighbor masks.

    Edge cases:
      size=0  → True  (vacuously)
      size=1  → True iff candidates is non-empty
    """
    if size == 0:
        return True
    tmp = candidates
    while tmp:
        lsb = tmp & -tmp
        v = lsb.bit_length() - 1
        tmp ^= lsb
        if _has_clique(size - 1, nbr[v] & tmp, nbr):
            return True
    return False


def _find_all_kt(t: int, nbr: list, N: int) -> list:
    """Return all K_t cliques as sorted t-tuples of vertex indices."""
    result = []

    def collect(size, path, candidates):
        if size == 0:
            result.append(tuple(path))
            return
        tmp = candidates
        while tmp:
            lsb = tmp & -tmp
            v = lsb.bit_length() - 1
            tmp ^= lsb
            collect(size - 1, path + [v], nbr[v] & tmp)

    collect(t, [], (1 << N) - 1)
    return result


def _find_one_kt(t: int, nbr: list, N: int):
    """Return one K_t as a tuple of vertex indices, or None if none exists."""
    found = [None]

    def search(size, path, candidates):
        if size == 0:
            found[0] = tuple(path)
            return True
        tmp = candidates
        while tmp:
            lsb = tmp & -tmp
            v = lsb.bit_length() - 1
            tmp ^= lsb
            if search(size - 1, path + [v], nbr[v] & tmp):
                return True
        return False

    search(t, [], (1 << N) - 1)
    return found[0]


def _complement_adj(adj: np.ndarray, N: int) -> np.ndarray:
    """Return complement adjacency matrix (flip edges, keep diagonal 0)."""
    comp = (1 - adj).astype(np.uint8)
    np.fill_diagonal(comp, 0)
    return comp


def _has_g_edge_in_mask(mask: int, g_nbr: list) -> bool:
    """Return True iff the induced subgraph on `mask` contains any edge in G."""
    tmp = mask
    while tmp:
        lsb = tmp & -tmp
        v = lsb.bit_length() - 1
        tmp ^= lsb
        if g_nbr[v] & mask & ~((1 << (v + 1)) - 1):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# DataPoint
# ─────────────────────────────────────────────────────────────────────────────

class KFourDataPoint(DataPoint):
    MAKE_OBJECT_CANONICAL = False
    T = 4  # α(G) ≤ T-1; set at class level for multiprocessing

    def __init__(self, N, t=None, init=False):
        super().__init__()
        self.N = N
        self.t = self.__class__.T if t is None else t
        self.data = np.zeros((N, N), dtype=np.uint8)  # H = complement(G)

        if init:
            self._add_edges_greedily()
            if self.MAKE_OBJECT_CANONICAL:
                self.data = sort_graph_based_on_degree(self.data)
            self.calc_features()
            self.calc_score()

    # ── scoring ───────────────────────────────────────────────────────────────

    def calc_score(self):
        N = self.N
        all_mask = (1 << N) - 1

        # G = complement(H = self.data)
        g_adj = _complement_adj(self.data, N)
        g_nbr = _build_nbr_masks(g_adj)

        # Constraint 1: G must be K₄-free
        if _has_clique(4, all_mask, g_nbr):
            self.score = -1
            return -1

        # Constraint 2: α(G) ≤ t-1  ↔  H is K_t-free
        h_nbr = _build_nbr_masks(self.data)
        if _has_clique(self.t, all_mask, h_nbr):
            self.score = -1
            return -1

        # Score = |E(H)| (positive, maximized by the framework)
        self.score = int(self.data.sum()) // 2
        return self.score

    def calc_features(self):
        w = []
        for i in range(self.N):
            for j in range(i + 1, self.N):
                w.append(self.data[i, j])
        self.features = ",".join(map(str, w))

    def local_search(self, improve_with_local_search):
        N = self.N
        all_mask = (1 << N) - 1

        repaired = False
        for _ in range(200):
            g_adj = _complement_adj(self.data, N)
            g_nbr = _build_nbr_masks(g_adj)
            h_nbr = _build_nbr_masks(self.data)

            # ── Phase 1a: repair K₄ in G by removing edges ────────────────
            # Removing edge (i,j) from G = adding (i,j) to H.
            # Remove the edge appearing in the most K₄s until G is K₄-free.
            # Note: removing G-edges can only increase α(G), so α repair
            # follows in Phase 1b.
            while _has_clique(4, all_mask, g_nbr):
                k4s = _find_all_kt(4, g_nbr, N)
                edge_count = {}
                for clique in k4s:
                    for a in range(len(clique)):
                        for b in range(a + 1, len(clique)):
                            e = (clique[a], clique[b])
                            edge_count[e] = edge_count.get(e, 0) + 1
                i, j = max(edge_count, key=edge_count.get)
                g_nbr[i] &= ~(1 << j)
                g_nbr[j] &= ~(1 << i)
                self.data[i, j] = 1
                self.data[j, i] = 1
                h_nbr[i] |= 1 << j
                h_nbr[j] |= 1 << i

            # ── Phase 1b: repair α(G) > t-1 (= K_t in H) ─────────────────
            # Add edges to G (= remove from H) until H is K_t-free.
            # Adding (i,j) to G is K₄-safe iff G's common neighborhood of
            # (i,j) contains no edge — a local, cheap check.
            stuck = False
            while _has_clique(self.t, all_mask, h_nbr):
                kt = _find_one_kt(self.t, h_nbr, N)
                added = False
                for a in range(len(kt)):
                    for b in range(a + 1, len(kt)):
                        i, j = kt[a], kt[b]
                        if g_nbr[i] & (1 << j):
                            continue  # already a G-edge
                        # K₄-safety: common G-neighborhood must have no edge
                        if not _has_g_edge_in_mask(g_nbr[i] & g_nbr[j], g_nbr):
                            g_nbr[i] |= 1 << j
                            g_nbr[j] |= 1 << i
                            self.data[i, j] = 0
                            self.data[j, i] = 0
                            h_nbr[i] &= ~(1 << j)
                            h_nbr[j] &= ~(1 << i)
                            added = True
                            break
                    if added:
                        break
                if not added:
                    stuck = True
                    break  # can't repair α without creating K₄ — restart

            if not stuck:
                repaired = True
                break

            # Restart with a fresh random K₄-free construction
            self.data = np.zeros((N, N), dtype=np.uint8)
            self._add_edges_greedily()

        # ── Phase 2: greedy edge removal from G (= addition to H) ─────────
        # For each G-edge (i,j): removing it adds (i,j) to H.
        # This is safe iff the new H-edge does not complete a K_t in H.
        # Fast incremental check: adding (i,j) to H creates K_t iff
        # K_{t-2} already exists in the common H-neighborhood of i and j.
        if improve_with_local_search:
            # Rebuild to ensure g_nbr/h_nbr are current after repair
            g_adj = _complement_adj(self.data, N)
            g_nbr = _build_nbr_masks(g_adj)
            h_nbr = _build_nbr_masks(self.data)

            g_edges = []
            for i in range(N):
                tmp = g_nbr[i] & ~((1 << (i + 1)) - 1)
                while tmp:
                    lsb = tmp & -tmp
                    j = lsb.bit_length() - 1
                    tmp ^= lsb
                    g_edges.append((i, j))
            np.random.shuffle(g_edges)

            for i, j in g_edges:
                if not (g_nbr[i] & (1 << j)):
                    continue  # edge already removed earlier in this pass
                # Reject if adding (i,j) to H would create K_t
                if _has_clique(self.t - 2, h_nbr[i] & h_nbr[j], h_nbr):
                    continue
                # Safe: remove (i,j) from G, add to H
                g_nbr[i] &= ~(1 << j)
                g_nbr[j] &= ~(1 << i)
                self.data[i, j] = 1
                self.data[j, i] = 1
                h_nbr[i] |= 1 << j
                h_nbr[j] |= 1 << i

        if self.MAKE_OBJECT_CANONICAL:
            self.data = sort_graph_based_on_degree(self.data)
        self.calc_features()
        self.calc_score()

    # ── greedy construction ───────────────────────────────────────────────────

    def _add_edges_greedily(self):
        """
        Build a maximal K₄-free G on N vertices in random edge order.
        Adding (i,j) creates K₄ iff G's common neighborhood of (i,j)
        contains any edge — a purely local check.
        Stores H = complement(G) in self.data.
        """
        N = self.N
        g_nbr = [0] * N
        self.data = np.zeros((N, N), dtype=np.uint8)

        candidates = [(i, j) for i in range(N) for j in range(i + 1, N)]
        np.random.shuffle(candidates)

        for i, j in candidates:
            if not _has_g_edge_in_mask(g_nbr[i] & g_nbr[j], g_nbr):
                g_nbr[i] |= 1 << j
                g_nbr[j] |= 1 << i

        # Store H = complement(G)
        for i in range(N):
            for j in range(i + 1, N):
                if not (g_nbr[i] & (1 << j)):
                    self.data[i, j] = 1
                    self.data[j, i] = 1

    # ── class-level params (process pool) ────────────────────────────────────

    @classmethod
    def _batch_generate_and_score(cls, batch_size, N, pars=None):
        if pars is not None:
            cls._update_class_params(pars)
        out = []
        for _ in range(batch_size):
            d = cls(N=N, init=True)
            d.local_search(improve_with_local_search=True)
            if d.score >= 0:
                out.append(d)
        return out

    @classmethod
    def _update_class_params(cls, pars):
        cls.MAKE_OBJECT_CANONICAL, cls.T = pars

    @classmethod
    def _save_class_params(cls):
        return (cls.MAKE_OBJECT_CANONICAL, cls.T)


# ─────────────────────────────────────────────────────────────────────────────
# Environment
# ─────────────────────────────────────────────────────────────────────────────

class KFourEnvironment(BaseEnvironment):
    k = 2
    are_coordinates_symmetric = True
    data_class = KFourDataPoint

    def __init__(self, params):
        super().__init__(params)
        self.data_class.T = params.t
        self.data_class.MAKE_OBJECT_CANONICAL = params.make_object_canonical

        encoding_augmentation = random_symmetry_adj_matrix if params.augment_data_representation else None

        if params.encoding_tokens == "single_integer":
            self.tokenizer = SparseTokenizerSingleInteger(
                self.data_class, params.N, self.k, self.are_coordinates_symmetric,
                self.SPECIAL_SYMBOLS, encoding_augmentation=encoding_augmentation,
            )
        elif params.encoding_tokens == "sequence_k_tokens":
            self.tokenizer = SparseTokenizerSequenceKTokens(
                self.data_class, params.N, self.k, self.are_coordinates_symmetric,
                self.SPECIAL_SYMBOLS, encoding_augmentation=encoding_augmentation,
            )
        elif params.encoding_tokens == "adjacency":
            self.tokenizer = DenseTokenizer(
                self.data_class, params.N, self.k, self.are_coordinates_symmetric,
                self.SPECIAL_SYMBOLS, pow2base=params.pow2base,
                encoding_augmentation=encoding_augmentation,
            )
        else:
            raise ValueError(f"Invalid encoding_tokens: {params.encoding_tokens}")

    @staticmethod
    def register_args(parser):
        parser.add_argument("--N", type=int, default=10,
                            help="Number of vertices")
        parser.add_argument("--t", type=int, default=4,
                            help="Independence number bound: alpha(G) <= t-1")
        parser.add_argument("--encoding_tokens", type=str, default="single_integer",
                            help="single_integer | sequence_k_tokens | adjacency")
        parser.add_argument("--make_object_canonical", type=bool_flag, default="false",
                            help="Sort nodes by degree for canonical deduplication")
        parser.add_argument("--augment_data_representation", type=bool_flag, default="false",
                            help="Augment with random symmetry relabelling during training")
        parser.add_argument("--pow2base", type=int, default=1,
                            help="Bits per token for adjacency encoding")
