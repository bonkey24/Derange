"""
inclusion_exclusion.py
-----------------------
Uses the rook polynomial of a FORBIDDEN board to count the number of valid
permutations (arrangements) of n items into n positions, avoiding all
forbidden (item, position) pairs.

This is the classic "Arrangements with Forbidden Positions" theorem:

    Number of valid permutations =  sum_{k=0}^{n} (-1)^k * r_k * (n - k)!

where r_k is the k-th coefficient of the rook polynomial of the FORBIDDEN
board (r_k = number of ways to place k non-attacking rooks on forbidden cells,
i.e. k mutually independent forbidden assignments).

Why this works (intuition):
    - (n-k)! counts all the ways to arrange the REMAINING n-k items freely,
      after k specific (item, position) forbidden pairs are "used up".
    - r_k counts how many ways there are to pick k independent forbidden
      pairs (no shared item or position) -- because inclusion-exclusion
      needs to know, for each "k forbidden pairs used", how many such
      k-subsets exist.
    - Signs alternate (+/-) per inclusion-exclusion over "at least these
      k forbidden pairs are violated".

This module builds directly on rook_polynomial.py.
"""

import math

try:
    from .rook_polynomial import rook_polynomial
except ImportError:
    from rook_polynomial import rook_polynomial


def count_valid_arrangements(n, forbidden_cells):
    """
    n: number of items = number of positions (square board n x n)
    forbidden_cells: list of (item, position) pairs that are NOT allowed

    Returns: exact count of permutations of n items into n positions
             that avoid every forbidden pair.
    """
    r = rook_polynomial(forbidden_cells)  # r[k] = r_k

    total = 0
    for k, r_k in enumerate(r):
        sign = (-1) ** k
        total += sign * r_k * math.factorial(n - k)

    return total


def count_valid_arrangements_verbose(n, forbidden_cells):
    """
    Same as count_valid_arrangements, but returns the full term-by-term
    breakdown -- useful for your Chart.js "inclusion-exclusion contribution"
    visualization later (each term = one bar in the chart).

    Returns: (total, list_of_terms)
        each term is a dict: {k, r_k, sign, factorial_term, contribution}
    """
    r = rook_polynomial(forbidden_cells)
    terms = []
    total = 0

    for k, r_k in enumerate(r):
        sign = (-1) ** k
        fact = math.factorial(n - k)
        contribution = sign * r_k * fact
        total += contribution
        terms.append({
            "k": k,
            "r_k": r_k,
            "sign": sign,
            "factorial_term": fact,
            "contribution": contribution,
        })

    return total, terms


if __name__ == "__main__":
    # --- Sanity check 1: NO forbidden positions -> should equal n! ---
    n = 4
    print("No restrictions, n=4:", count_valid_arrangements(n, []))  # expect 24

    # --- Sanity check 2: Forbidden = full diagonal -> this IS the derangement problem ---
    # forbidden pair (i, i) means item i cannot go to position i
    n = 4
    diagonal_forbidden = [(i, i) for i in range(n)]
    result = count_valid_arrangements(n, diagonal_forbidden)
    print(f"Derangements via forbidden-diagonal, n={n}:", result)  # expect 9

    n = 5
    diagonal_forbidden = [(i, i) for i in range(n)]
    result = count_valid_arrangements(n, diagonal_forbidden)
    print(f"Derangements via forbidden-diagonal, n={n}:", result)  # expect 44

    # --- Verbose breakdown demo (for your chart later) ---
    total, terms = count_valid_arrangements_verbose(4, [(i, i) for i in range(4)])
    print("\nTerm-by-term breakdown for n=4 derangements:")
    for t in terms:
        print(f"  k={t['k']}: sign={t['sign']:+d}, r_k={t['r_k']}, "
              f"(n-k)!={t['factorial_term']}, contribution={t['contribution']}")
    print("Total:", total)
