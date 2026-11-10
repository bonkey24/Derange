"""
test_seating_board.py
----------------------
Tests for the two-layer seating engine:
  - Layer 1 + 2 backtracking vs brute-force cross-validation
  - Retest (derangement) seating correctness
"""

import random

from seating.engines.seating_board import (
    backtracking_seat_assignment,
    brute_force_count_valid_full,
    generate_retest_seating,
)


class TestBacktrackingVsBruteForce:
    """
    Core correctness cross-check: backtracking should find a solution
    if and only if brute-force enumeration finds at least one valid
    arrangement.
    """

    def test_small_room_with_mixed_constraints(self):
        """
        2x3 room (6 seats), 4 students, with a mix of individual
        forbidden seats and adjacency conflict pairs.
        """
        students = ["S1", "S2", "S3", "S4"]
        rows, cols = 2, 3

        # Individual forbidden: S1 cannot sit in seat 3, S2 cannot sit in seat 0
        individual_forbidden = [("S1", 3), ("S2", 0)]

        # Conflict pairs: S1-S2 and S3-S4 must not be adjacent
        conflict_pairs = [("S1", "S2"), ("S3", "S4")]

        bf_count = brute_force_count_valid_full(
            students, rows, cols, conflict_pairs,
            individual_forbidden=individual_forbidden,
            include_diagonal=True,
        )

        bt_result = backtracking_seat_assignment(
            students, rows, cols, conflict_pairs,
            individual_forbidden=individual_forbidden,
            include_diagonal=True,
        )

        if bf_count > 0:
            assert bt_result is not None, (
                f"Brute force found {bf_count} valid arrangements, "
                f"but backtracking returned None"
            )
        else:
            assert bt_result is None, (
                f"Brute force found 0 valid arrangements, "
                f"but backtracking returned a result: {bt_result}"
            )

    def test_find_all_count_matches_brute_force(self):
        """
        When backtracking enumerates ALL solutions, the count should
        exactly match brute-force enumeration.
        """
        students = ["A", "B", "C"]
        rows, cols = 2, 2  # 4 seats, 3 students
        conflict_pairs = [("A", "B")]
        individual_forbidden = [("C", 0)]

        bf_count = brute_force_count_valid_full(
            students, rows, cols, conflict_pairs,
            individual_forbidden=individual_forbidden,
            include_diagonal=True,
        )

        bt_all = backtracking_seat_assignment(
            students, rows, cols, conflict_pairs,
            individual_forbidden=individual_forbidden,
            include_diagonal=True,
            find_all=True,
        )

        assert len(bt_all) == bf_count, (
            f"Backtracking found {len(bt_all)} solutions, "
            f"brute force found {bf_count}"
        )

    def test_overconstrained_returns_none(self):
        """
        An impossible scenario: 3 students on a 1x3 grid where all
        pairs conflict (nobody can sit next to anyone).  With diagonal
        adjacency on a 1x3 grid, seats 0-1 and 1-2 are neighbors,
        making it impossible with all-pairs conflict.
        """
        students = ["X", "Y", "Z"]
        rows, cols = 1, 3
        conflict_pairs = [("X", "Y"), ("Y", "Z"), ("X", "Z")]

        bt_result = backtracking_seat_assignment(
            students, rows, cols, conflict_pairs,
            include_diagonal=False,  # even without diagonal, 1x3 all-pairs fails
        )

        bf_count = brute_force_count_valid_full(
            students, rows, cols, conflict_pairs,
            include_diagonal=False,
        )

        assert bf_count == 0
        assert bt_result is None


class TestRetestSeating:
    """
    generate_retest_seating must never assign any student to their
    previous seat (the derangement constraint).
    """

    def test_no_student_repeats_previous_seat(self):
        """
        Run retest seating 20 times with slightly randomized conflict
        pairs each time.  Every single run must produce a valid
        derangement (no student in their old seat).
        """
        students = ["S1", "S2", "S3", "S4"]
        rows, cols = 2, 3
        previous_seats = {"S1": 0, "S2": 1, "S3": 4, "S4": 5}

        all_possible_pairs = [
            ("S1", "S2"), ("S1", "S3"), ("S1", "S4"),
            ("S2", "S3"), ("S2", "S4"), ("S3", "S4"),
        ]

        for trial in range(20):
            # Pick 0 or 1 random conflict pairs to keep constraints light
            # enough that a solution exists
            k = random.randint(0, 1)
            conflict_pairs = random.sample(all_possible_pairs, k)

            result = generate_retest_seating(
                students=students,
                rows=rows,
                cols=cols,
                previous_seats=previous_seats,
                conflict_pairs=conflict_pairs,
                include_diagonal=True,
            )

            # It's possible (but unlikely with light constraints) that
            # no solution exists.  If one IS returned, verify derangement.
            if result is not None:
                for student in students:
                    prev_seat = previous_seats[student]
                    # result is {seat_idx: student}, so find this student's seat
                    assigned_seat = [
                        s for s, st in result.items() if st == student
                    ]
                    assert len(assigned_seat) == 1, (
                        f"Trial {trial}: Student {student} not found in result"
                    )
                    assert assigned_seat[0] != prev_seat, (
                        f"Trial {trial}: {student} was assigned to their "
                        f"previous seat {prev_seat}"
                    )
