"""
test_derangements.py
---------------------
Tests for derangement counting and generation functions.
"""

from seating.engines.derangements import (
    derangement_count_formula,
    derangement_count_recurrence,
    generate_random_derangement,
)


class TestFormulaVsRecurrence:
    """The two independent D(n) implementations must agree for all n."""

    def test_formula_equals_recurrence_n0_through_n15(self):
        for n in range(16):
            f = derangement_count_formula(n)
            r = derangement_count_recurrence(n)
            assert f == r, (
                f"Mismatch at n={n}: formula={f}, recurrence={r}"
            )


class TestGenerateRandomDerangement:
    """
    generate_random_derangement must produce a permutation with
    ZERO fixed points (no element stays in its original position).
    """

    def test_no_fixed_points_200_trials(self):
        original = list(range(10))  # [0, 1, 2, ..., 9]

        for trial in range(200):
            result = generate_random_derangement(original)

            # Must be a permutation (same elements)
            assert sorted(result) == original, (
                f"Trial {trial}: result is not a permutation of the original"
            )

            # Must have zero fixed points
            fixed_points = [
                i for i in range(len(original)) if result[i] == original[i]
            ]
            assert len(fixed_points) == 0, (
                f"Trial {trial}: found fixed points at indices {fixed_points}"
            )
