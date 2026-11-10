"""
test_rook_polynomial.py
------------------------
Tests for the rook polynomial engine against known textbook results.
"""

from seating.engines.rook_polynomial import rook_polynomial, full_board


class TestRookPolynomialKnownValues:
    """Validate rook_polynomial() against exact known results."""

    def test_1x1_full_board(self):
        """R(x) of a full 1x1 board = 1 + x  ->  [1, 1]."""
        assert rook_polynomial(full_board(1)) == [1, 1]

    def test_2x2_full_board(self):
        """R(x) of a full 2x2 board = 1 + 4x + 2x^2  ->  [1, 4, 2]."""
        assert rook_polynomial(full_board(2)) == [1, 4, 2]

    def test_3x3_l_shape_forbidden(self):
        """
        Classic textbook example: an L-shaped board with cells
        (0,0), (0,1), (1,0) has rook polynomial [1, 3, 1].
        """
        forbidden_board = [(0, 0), (0, 1), (1, 0)]
        assert rook_polynomial(forbidden_board) == [1, 3, 1]
