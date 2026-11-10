"""
rook_polynomial.py
-------------------
Core engine for computing the rook polynomial of a board with forbidden
(or allowed) positions, using the classic DELETION-CONTRACTION recursion:

    R(C, x) = R(C - {cell}, x) + x * R(C - row(cell) - col(cell), x)

Where:
    - C - {cell}          : board with just that one cell removed
    - C - row - col       : board with the cell's entire row AND column removed
                             (because placing a rook there blocks that row & column)

A "board" here is the set of cells where a rook is ALLOWED to be placed
(i.e. the set of (student, seat)-style compatible pairs, NOT the forbidden ones).
This matches the standard "arrangements with forbidden positions" formulation
from combinatorics: you build the board of *forbidden* cells, compute its rook
polynomial r_0, r_1, ..., r_n, then plug those into inclusion-exclusion.

Author: (your name here)
"""

from functools import lru_cache


def normalize_board(board):
    """Convert board (iterable of (row, col) tuples) into a frozenset for hashing/caching."""
    return frozenset((r, c) for r, c in board)


@lru_cache(maxsize=None)
def _rook_polynomial_cached(board_frozen):
    """
    Internal recursive worker. Returns a tuple of coefficients
    (r_0, r_1, r_2, ...) representing the rook polynomial:
        R(x) = r_0 + r_1*x + r_2*x^2 + ...
    where r_k = number of ways to place k non-attacking rooks on `board`.

    board_frozen: frozenset of (row, col) cells where a rook MAY be placed.
    """
    board = board_frozen

    # Base case: empty board -> only 0 rooks can be placed -> R(x) = 1
    if not board:
        return (1,)

    # Pick any one cell to recurse on (order doesn't matter, result is the same)
    cell = next(iter(board))
    r, c = cell

    # Term 1: R(C - {cell})  -> board without this single cell
    board_minus_cell = board - {cell}
    poly_without_cell = _rook_polynomial_cached(normalize_board(board_minus_cell))

    # Term 2: x * R(C - row(cell) - col(cell)) -> remove entire row & column of cell
    board_minus_row_col = frozenset(
        (rr, cc) for (rr, cc) in board if rr != r and cc != c
    )
    poly_with_cell = _rook_polynomial_cached(board_minus_row_col)

    # Combine: poly_without_cell + x * poly_with_cell
    # "x * poly_with_cell" shifts every coefficient up by one degree
    max_len = max(len(poly_without_cell), len(poly_with_cell) + 1)
    result = [0] * max_len

    for i, val in enumerate(poly_without_cell):
        result[i] += val

    for i, val in enumerate(poly_with_cell):
        result[i + 1] += val

    return tuple(result)


def rook_polynomial(board):
    """
    Public entry point.

    board: iterable of (row, col) tuples -- the cells where a rook CAN be placed.

    Returns: list of coefficients [r_0, r_1, r_2, ..., r_k]
             r_k = number of ways to place k non-attacking rooks on this board.
    """
    board_frozen = normalize_board(board)
    return list(_rook_polynomial_cached(board_frozen))


def full_board(n, m=None):
    """Convenience: every cell of an n x m board is allowed (default m = n)."""
    if m is None:
        m = n
    return [(r, c) for r in range(n) for c in range(m)]


def complement_board(n, m, forbidden_cells):
    """
    Given the FULL board size (n x m) and a list of forbidden cells,
    return the ALLOWED board (complement) -- this is what rook_polynomial()
    for feasibility-style problems is usually run on, OR you run it directly
    on the forbidden cells for the inclusion-exclusion "forbidden positions" method.
    Provided here for convenience/flexibility.
    """
    forbidden = normalize_board(forbidden_cells)
    return [(r, c) for r in range(n) for c in range(m) if (r, c) not in forbidden]


if __name__ == "__main__":
    # --- Sanity checks against known textbook results ---

    # 1) Rook polynomial of a full 1x1 board -> R(x) = 1 + x
    print("1x1 full board:", rook_polynomial(full_board(1)))  # expect [1, 1]

    # 2) Rook polynomial of a full 2x2 board -> R(x) = 1 + 4x + 2x^2
    print("2x2 full board:", rook_polynomial(full_board(2)))  # expect [1, 4, 2]

    # 3) Classic textbook example: forbidden positions on a 3x3 board
    #    forming an "L" shape (cells (0,0), (0,1), (1,0))
    forbidden = [(0, 0), (0, 1), (1, 0)]
    print("Forbidden L-shape rook poly:", rook_polynomial(forbidden))
