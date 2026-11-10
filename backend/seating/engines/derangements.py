"""
derangements.py
-----------------
Direct derangement theory: counting formula, recurrence, and ACTUAL generation
of a random derangement (needed for your retest re-seating feature, where a
student must NOT get their previous seat).

Three independent ways to compute D(n) are included so you can cross-check:
    1. Direct inclusion-exclusion formula: D(n) = n! * sum_{k=0}^{n} (-1)^k / k!
    2. Recurrence relation: D(n) = (n-1) * (D(n-1) + D(n-2))
    3. (cross-checked separately in generating_functions.py via the EGF)
"""

import math
import random


def derangement_count_formula(n):
    """Direct inclusion-exclusion formula: D(n) = n! * sum_{k=0}^{n} (-1)^k / k!"""
    total = sum((-1) ** k / math.factorial(k) for k in range(n + 1))
    return round(math.factorial(n) * total)


def derangement_count_recurrence(n):
    """D(n) = (n-1) * (D(n-1) + D(n-2)), with D(0)=1, D(1)=0."""
    if n == 0:
        return 1
    if n == 1:
        return 0
    d_prev2, d_prev1 = 1, 0  # D(0), D(1)
    for i in range(2, n + 1):
        d_curr = (i - 1) * (d_prev1 + d_prev2)
        d_prev2, d_prev1 = d_prev1, d_curr
    return d_prev1


def generate_random_derangement(items):
    """
    Generate one uniformly random derangement of `items` (a list).
    Uses rejection sampling: shuffle, check no fixed points, retry if any exist.
    Simple and provably uniform, and fast enough for realistic class sizes
    (expected ~e ≈ 2.718 tries on average).

    Returns: a new list, same elements as `items` but rearranged so that
             no element stays in its original index.
    """
    n = len(items)
    original = list(items)
    attempt = list(items)

    while True:
        random.shuffle(attempt)
        if all(attempt[i] != original[i] for i in range(n)):
            return attempt


def generate_derangement_mapping(students, previous_seats):
    """
    Real-world use case: retest re-seating.

    students: list of student IDs
    previous_seats: dict {student_id: previous_seat_id}, same keys as students

    Returns: dict {student_id: new_seat_id} such that no student gets their
             previous seat back.
    """
    seat_list = [previous_seats[s] for s in students]
    deranged_seats = generate_random_derangement(seat_list)
    return dict(zip(students, deranged_seats))


if __name__ == "__main__":
    print("Cross-checking formula vs recurrence:")
    for n in range(0, 10):
        f = derangement_count_formula(n)
        r = derangement_count_recurrence(n)
        match = "OK" if f == r else "MISMATCH"
        print(f"  n={n}: formula={f}, recurrence={r}  [{match}]")

    print("\nExample random derangement of 6 students' seats:")
    students = ["S1", "S2", "S3", "S4", "S5", "S6"]
    previous = {s: f"Seat{i+1}" for i, s in enumerate(students)}
    new_assignment = generate_derangement_mapping(students, previous)
    for s in students:
        print(f"  {s}: was {previous[s]} -> now {new_assignment[s]}")
