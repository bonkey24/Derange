"""
brute_force_explainer.py
-------------------------
Tiny-room brute force permutation generator and verifier for the Derange Math Explainer.

Lists all n! permutations for small n (n <= 5) using itertools.permutations.
For each permutation, constructs the student-to-seat assignment using generic labels
(S1..Sn -> Seat 1..n), tests its validity under individual forbidden seats or derangement
fixed-point constraints, and cross-checks the total against the inclusion-exclusion
and derangement theoretical formulas.
"""

import itertools
import math

try:
    from .inclusion_exclusion import count_valid_arrangements_verbose
    from .derangements import derangement_count_formula
except ImportError:
    from inclusion_exclusion import count_valid_arrangements_verbose
    from derangements import derangement_count_formula


def _normalize_forbidden_cell(cell, n):
    """
    Normalizes a forbidden cell tuple to 0-indexed (student_idx, seat_idx).
    Accepts:
      - (0, 1) -> 0-indexed ints
      - ("S1", 2) -> 1-indexed student label, 1-indexed seat
      - ("S1", "Seat 2") -> string labels
    """
    student_raw, seat_raw = cell

    if isinstance(student_raw, int):
        s_idx = student_raw
    else:
        s_str = str(student_raw).strip().upper()
        if s_str.startswith("S") and s_str[1:].isdigit():
            s_idx = int(s_str[1:]) - 1
        elif s_str.isdigit():
            s_idx = int(s_str) - 1
        else:
            raise ValueError(f"Unrecognized student label: {student_raw}")

    if isinstance(seat_raw, int):
        # If integer is already 0-indexed (0 <= seat_raw < n), keep it
        # If integer is 1-indexed (1 <= seat_raw <= n) and not 0, standardise to 0-index
        # Note: if seat_raw is 0, it is 0-indexed seat 0.
        c_idx = seat_raw
    else:
        c_str = str(seat_raw).strip().lower().replace("seat", "").strip()
        if c_str.isdigit():
            c_idx = int(c_str) - 1
        else:
            raise ValueError(f"Unrecognized seat label: {seat_raw}")

    if not (0 <= s_idx < n):
        raise ValueError(f"Student index {s_idx} out of range for n={n}")
    if not (0 <= c_idx < n):
        # In case seat was given as 1-indexed integer, e.g. seat 4 for n=4
        if 1 <= c_idx <= n:
            c_idx -= 1
        else:
            raise ValueError(f"Seat index {c_idx} out of range for n={n}")

    return s_idx, c_idx


def enumerate_arrangements(n, forbidden_cells=None, mode="seating"):
    """
    Enumerate all n! student-to-seat permutations for small n (n <= 5).

    Parameters
    ----------
    n : int
        Number of students and available seats (1 <= n <= 5).
    forbidden_cells : list of tuple, optional
        Forbidden (student, seat) pairs. Can be 0-indexed or 1-indexed generic labels.
    mode : str, optional
        'seating' (default): checks against forbidden cells.
        'retest': checks for zero fixed points (nobody keeps seat i).

    Returns
    -------
    dict:
        {
            "n": int,
            "mode": str,
            "all": int,
            "total_arrangements": int,
            "valid": int,
            "valid_count": int,
            "invalid": int,
            "invalid_count": int,
            "formula_value": int,
            "formula_str": str,
            "matches": bool,
            "forbidden_cells": list of dict,
            "arrangements": list of dict,
        }
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    if n > 5:
        raise ValueError(f"Brute-force proof is restricted to n <= 5 (received n={n}).")

    mode = mode.lower()
    if mode not in ("seating", "retest", "derangement"):
        raise ValueError(f"Unknown mode '{mode}'. Choose 'seating' or 'retest'.")

    # Normalize forbidden cells
    normalized_forbidden = set()
    if forbidden_cells:
        for cell in forbidden_cells:
            s_idx, c_idx = _normalize_forbidden_cell(cell, n)
            normalized_forbidden.add((s_idx, c_idx))

    forbidden_display = [
        {"student": f"S{s + 1}", "seat": c + 1}
        for s, c in sorted(normalized_forbidden)
    ]

    # Generate all n! permutations
    arrangements = []
    student_indices = list(range(n))

    for idx, perm in enumerate(itertools.permutations(range(n)), start=1):
        # perm[i] is the seat index (0..n-1) assigned to student i
        assignment_pairs = []
        assignment_items = []
        for s_idx in student_indices:
            seat_num = perm[s_idx] + 1
            assignment_pairs.append(f"S{s_idx + 1}->{seat_num}")
            assignment_items.append({"student": f"S{s_idx + 1}", "seat": seat_num})

        assignment_str = ", ".join(assignment_pairs)

        if mode == "seating":
            violating_students = []
            reasons = []
            for s_idx in student_indices:
                seat_idx = perm[s_idx]
                if (s_idx, seat_idx) in normalized_forbidden:
                    violating_students.append(f"S{s_idx + 1}")
                    reasons.append(f"S{s_idx + 1} is in a forbidden seat")

            is_valid = len(violating_students) == 0
            reason = "; ".join(reasons) if not is_valid else "Valid seating (no rules broken)"
            fixed_points = []
        else:
            # Retest derangement: student i had previous seat i
            fixed_students = []
            for s_idx in student_indices:
                if perm[s_idx] == s_idx:
                    fixed_students.append(f"S{s_idx + 1}")

            is_valid = len(fixed_students) == 0
            if is_valid:
                reason = "Valid derangement (0 fixed points)"
            else:
                reason = ", ".join([f"{s} kept seat {s[1:]}" for s in fixed_students])
            fixed_points = fixed_students
            violating_students = fixed_students

        arrangements.append({
            "id": idx,
            "assignment": assignment_str,
            "assignment_items": assignment_items,
            "is_valid": is_valid,
            "reason": reason,
            "fixed_points": fixed_points,
            "violating_students": violating_students,
        })

    total_arrangements = len(arrangements)
    valid_count = sum(1 for a in arrangements if a["is_valid"])
    invalid_count = total_arrangements - valid_count

    # Calculate formula value and formula string
    if mode == "seating":
        formula_total, terms = count_valid_arrangements_verbose(n, list(normalized_forbidden))
        formula_value = formula_total

        # Build clean formula string, e.g. "4! - 2×3! + 1×2! = 24 - 12 + 2 = 14"
        symbolic_terms = []
        numeric_terms = []
        for t in terms:
            k = t["k"]
            r_k = t["r_k"]
            sign = t["sign"]
            sign_char = "-" if sign < 0 else "+"

            if k == 0:
                symbolic_terms.append(f"{n}!")
                numeric_terms.append(str(t["factorial_term"]))
            elif r_k > 0:
                sym = f"{sign_char} {r_k}×({n}−{k})!"
                num = f"{sign_char} {abs(t['contribution'])}"
                symbolic_terms.append(sym)
                numeric_terms.append(num)

        if len(symbolic_terms) > 1:
            formula_str = (
                f"{' '.join(symbolic_terms)} = {' '.join(numeric_terms)} = {formula_value}"
            )
        else:
            formula_str = f"{n}! = {formula_value}"
    else:
        formula_value = derangement_count_formula(n)
        # Build derangement formula string
        # D(n) = n! * sum_{k=0}^n (-1)^k / k!
        formula_str = f"D({n}) = !{n} = {formula_value}"

    matches = (valid_count == formula_value)

    return {
        "n": n,
        "mode": "retest" if mode in ("retest", "derangement") else "seating",
        "all": total_arrangements,
        "total_arrangements": total_arrangements,
        "valid": valid_count,
        "valid_count": valid_count,
        "invalid": invalid_count,
        "invalid_count": invalid_count,
        "formula_value": formula_value,
        "formula_str": formula_str,
        "matches": matches,
        "forbidden_cells": forbidden_display,
        "arrangements": arrangements,
    }
