"""
generating_functions.py
-------------------------
Independent verification of the derangement counts using the
EXPONENTIAL GENERATING FUNCTION (EGF) for derangements:

    D(x) = e^(-x) / (1 - x) = sum_{n=0}^{inf} D(n) * x^n / n!

We expand this as a Taylor/Maclaurin series with sympy, extract the
coefficient of x^n, multiply by n! to "un-normalize" it (since it's an
EXPONENTIAL generating function, not ordinary), and compare against the
values from derangements.py and inclusion_exclusion.py.

If all three independent methods (inclusion-exclusion + rook polynomial,
direct recurrence, and this EGF) agree, that's strong evidence the whole
math core is correct.
"""

import sympy as sp

x = sp.symbols("x")


def derangement_count_via_egf(n, expansion_order=None):
    """
    Extract D(n) from the EGF D(x) = e^(-x)/(1-x).

    n: which derangement count to extract
    expansion_order: how many terms of the series to compute (defaults to n+2
                      for safety margin)
    """
    if expansion_order is None:
        expansion_order = n + 2

    egf = sp.exp(-x) / (1 - x)
    series = sp.series(egf, x, 0, expansion_order).removeO()
    poly = sp.Poly(series, x)

    coeff_of_xn = poly.coeff_monomial(x ** n) if n > 0 else poly.coeff_monomial(1)
    d_n = coeff_of_xn * sp.factorial(n)
    return int(d_n)


def show_egf_symbolically():
    """Prints the symbolic EGF and its series expansion for the report/demo."""
    egf = sp.exp(-x) / (1 - x)
    print("Exponential Generating Function for derangements:")
    sp.pprint(egf)
    print("\nSeries expansion (first 8 terms):")
    series = sp.series(egf, x, 0, 8)
    sp.pprint(series)


if __name__ == "__main__":
    try:
        from .derangements import derangement_count_recurrence
        from .inclusion_exclusion import count_valid_arrangements
    except ImportError:
        from derangements import derangement_count_recurrence
        from inclusion_exclusion import count_valid_arrangements

    show_egf_symbolically()

    print("\nCross-checking THREE independent methods:")
    print(f"{'n':>3} | {'EGF':>8} | {'Recurrence':>10} | {'Rook+I-E':>10} | Match")
    print("-" * 55)
    for n in range(0, 9):
        egf_val = derangement_count_via_egf(n)
        rec_val = derangement_count_recurrence(n)
        rook_ie_val = count_valid_arrangements(n, [(i, i) for i in range(n)])
        match = "YES" if egf_val == rec_val == rook_ie_val else "MISMATCH"
        print(f"{n:>3} | {egf_val:>8} | {rec_val:>10} | {rook_ie_val:>10} | {match}")
