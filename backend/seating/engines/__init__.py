"""
engines/__init__.py
--------------------
Exposes the core combinatorial, graph-theoretic, and ML risk modules
for the seating allocation system.
"""

from . import (
    derangements,
    generating_functions,
    inclusion_exclusion,
    ml_risk_model,
    rook_polynomial,
    seating_board,
)

__all__ = [
    'derangements',
    'generating_functions',
    'inclusion_exclusion',
    'ml_risk_model',
    'rook_polynomial',
    'seating_board',
]
