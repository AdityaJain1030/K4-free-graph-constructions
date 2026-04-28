from .base import Search, SearchResult
from .logger import SearchLogger, AggregateLogger
from .algebraic_explicit import (
    A5DoubleTranspositionsSearch,
    BrownSearch,
    FoldedCubeSearch,
    HammingSearch,
    LexBlowupSearch,
    MattheusVerstraeteSearch,
    NormGraphSearch,
    PolaritySearch,
    PrimeCirculantSearch,
    PSLInvolutionsSearch,
    ShrikhandeSearch,
    TensorBlowupSearch,
)
from .brute_force import BruteForce
from .stochastic_walk.cayley_tabu import CayleyTabuSearch
from .stochastic_walk.cayley_tabu_gap import CayleyTabuGapSearch
from .circulant import CirculantSearch
from .circulant_fast import CirculantSearchFast
from .stochastic_walk.random_regular_switch import RandomRegularSwitchSearch
from .stochastic_walk.alpha_targeted import AlphaTargetedSearch
from .sat_circulant import SATCirculant
from .sat_circulant_exact import SATCirculantExact
from .sat_exact import SATExact
from .sat_near_regular_nonreg import SATNearRegularNonReg

__all__ = [
    "Search",
    "SearchResult",
    "SearchLogger",
    "AggregateLogger",
    "A5DoubleTranspositionsSearch",
    "BrownSearch",
    "FoldedCubeSearch",
    "HammingSearch",
    "LexBlowupSearch",
    "PSLInvolutionsSearch",
    "ShrikhandeSearch",
    "TensorBlowupSearch",
    "BruteForce",
    "CayleyResidueSearch",
    "CayleyTabuSearch",
    "CayleyTabuGapSearch",
    "CirculantSearch",
    "CirculantSearchFast",
    "RandomRegularSwitchSearch",
    "AlphaTargetedSearch",
    "MattheusVerstraeteSearch",
    "NormGraphSearch",
    "PolaritySearch",
    "SATCirculant",
    "SATCirculantExact",
    "SATExact",
    "SATNearRegularNonReg",
]
