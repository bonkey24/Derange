"""
test_inclusion_exclusion.py
----------------------------
Tests for the inclusion-exclusion counting engine.
"""

import math

from seating.engines.inclusion_exclusion import count_valid_arrangements


class TestNoRestrictions:
    """With no forbidden cells, the count should equal n!."""

    def test_no_restrictions_equals_factorial(self):
        for n in [1, 3, 5, 7]:
            result = count_valid_arrangements(n, [])
            assert result == math.factorial(n), (
                f"Expected {math.factorial(n)} for n={n}, got {result}"
            )


class TestForbiddenDiagonalReproducesDerangements:
    """
    Forbidding the diagonal (i, i) for i in 0..n-1 is exactly the
    derangement problem. Validate against known D(n) values.
    """

    def test_derangement_n4(self):
        diagonal = [(i, i) for i in range(4)]
        assert count_valid_arrangements(4, diagonal) == 9

    def test_derangement_n5(self):
        diagonal = [(i, i) for i in range(5)]
        assert count_valid_arrangements(5, diagonal) == 44

    def test_derangement_n6(self):
        diagonal = [(i, i) for i in range(6)]
        assert count_valid_arrangements(6, diagonal) == 265
