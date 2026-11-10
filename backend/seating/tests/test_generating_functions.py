"""
test_generating_functions.py
------------------------------
Tests that the EGF-based derangement count agrees with the recurrence
and (implicitly) with the inclusion-exclusion count via the rook
polynomial, providing a three-way cross-check of the math core.
"""

from seating.engines.generating_functions import derangement_count_via_egf
from seating.engines.derangements import derangement_count_recurrence


class TestEGFAgreesWithRecurrence:
    """D(n) via EGF expansion must match D(n) via recurrence for n=0..10."""

    def test_egf_matches_recurrence_n0_through_n10(self):
        for n in range(11):
            egf_val = derangement_count_via_egf(n)
            rec_val = derangement_count_recurrence(n)
            assert egf_val == rec_val, (
                f"Mismatch at n={n}: EGF={egf_val}, recurrence={rec_val}"
            )
