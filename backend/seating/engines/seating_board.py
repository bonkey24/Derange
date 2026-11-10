"""
seating_board.py
-----------------
Models a real classroom seating grid (rows x cols) and connects it to the
combinatorics core (rook polynomials, inclusion-exclusion, derangements).

DESIGN -- TWO SEPARATE CONSTRAINT LAYERS:

  Layer 1 -- "Individual forbidden" (analytic):
      Each forbidden pair (student, seat) is an independent, one-to-one
      constraint.  Rook polynomials count placements on the board of these
      forbidden cells; inclusion-exclusion then gives the EXACT count of
      permutations that respect them all.
      -> count_valid_ignoring_adjacency()

  Layer 2 -- "Pairwise adjacency conflicts" (search-based):
      "Students A and B must NOT sit adjacent (horizontally, vertically, and
      optionally diagonally)."  This is a RELATIONAL constraint between two
      items' POSITIONS -- it can't be expressed as a single forbidden (item,
      position) cell, so rook polynomials don't cover it.  Instead, we use
      a standard backtracking search that assigns students to seats one at a
      time and prunes early whenever a partial assignment violates adjacency.
      -> backtracking_seat_assignment()

  Brute-force enumeration (for small rooms) verifies that the backtracking
  layer produces correct results.
      -> brute_force_count_valid_full()

  RETEST RE-SEATING (new feature -- combines both layers + derangements):
      When the same cohort takes a retest, every student must change seats
      (a derangement constraint), while still respecting both individual
      forbidden pairs AND adjacency conflict pairs.  This is solved by
      modifying the backtracking solver to treat each student's previous
      seat as an additional forbidden position -- effectively INTEGRATING
      the derangement requirement into the constraint-propagation search.
      -> generate_retest_seating()

Author: (your name here)
"""

import random
from itertools import permutations

# -- Project-internal imports -------------------------------------------------
try:
    from .inclusion_exclusion import count_valid_arrangements
    from .derangements import derangement_count_formula
    from .ml_risk_model import generate_simulated_data, train_risk_model, get_high_risk_pairs
except ImportError:
    from inclusion_exclusion import count_valid_arrangements
    from derangements import derangement_count_formula
    from ml_risk_model import generate_simulated_data, train_risk_model, get_high_risk_pairs


# =======================================================================
#  UTILITIES -- seat geometry helpers
# =======================================================================

def seat_label(row, col):
    """Human-readable label for a physical seat.  Row 1-indexed, col as letter."""
    return f"R{row + 1}C{chr(65 + col)}"


def seat_index(row, col, cols):
    """
    Map a (row, col) grid position to a linear seat index.
    This linear index is what appears in (student, seat) tuples for the
    rook polynomial board.
    """
    return row * cols + col


def seat_coords(seat_idx, cols):
    """Inverse of seat_index: linear index -> (row, col)."""
    return divmod(seat_idx, cols)


def get_neighbors(seat_idx, rows, cols, include_diagonal=True):
    """
    Return the set of linear seat indices adjacent to `seat_idx` in a
    `rows x cols` grid.

    Why include diagonals by default?  In most real exam halls, students
    seated diagonally behind each other can still glance at answers.  Making
    diagonal adjacency optional lets you model both strict and relaxed
    proctoring policies.
    """
    r, c = seat_coords(seat_idx, cols)
    neighbors = set()

    # Offsets: up/down/left/right, plus diagonals if requested
    # The 4 cardinal directions always count as adjacent.
    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if include_diagonal:
        offsets += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

    for dr, dc in offsets:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbors.add(seat_index(nr, nc, cols))

    return neighbors


# =======================================================================
#  LAYER 1 -- Analytic: individual forbidden pairs via rook + I-E
# =======================================================================

def count_valid_ignoring_adjacency(n_students, rows, cols, individual_forbidden):
    """
    Count how many ways to assign `n_students` students to `rows*cols` seats
    such that no student lands in their individually-forbidden seat(s),
    ignoring any pairwise adjacency conflicts.

    individual_forbidden: list of (student_idx, seat_idx) pairs

    This is an EXACT computation using the rook polynomial of the forbidden
    board, followed by inclusion-exclusion.

    Precondition: n_students <= rows * cols  (there must be enough seats).
    """
    n_seats = rows * cols
    if n_students > n_seats:
        return 0

    # For the standard "arrangements with forbidden positions" formula,
    # we need n_students == n_seats (a square board).  If there are more
    # seats than students, we conceptually add "phantom students" who can
    # go anywhere -- the forbidden board stays the same, but the dimension
    # of the permutation grows.  For this project's scope, we handle the
    # simple square case directly.
    if n_students != n_seats:
        # General rectangular case is more involved (permanent of a matrix).
        # For now, fall back to brute force for non-square setups.
        raise NotImplementedError(
            "Analytic rook-polynomial counting currently requires "
            "n_students == rows*cols.  Use brute_force_count_valid_full "
            "for non-square rooms."
        )

    return count_valid_arrangements(n_students, individual_forbidden)


# =======================================================================
#  LAYER 2 -- Search-based: backtracking with adjacency conflicts
# =======================================================================

def is_seat_valid(student, seat, assignment, conflict_pairs,
                  individual_forbidden_set, rows, cols,
                  include_diagonal=True):
    """
    Check whether assigning `student` to `seat` is compatible with:

      1. Individual forbidden pairs -- (student, seat) must not be forbidden.
      2. Pairwise adjacency conflicts -- for every already-assigned student
         who forms a conflict pair with `student`, they must NOT be seated
         in adjacent cells.

    assignment: dict {seat_idx: student_idx} of assignments made so far
    conflict_pairs: set of frozenset({studentA, studentB}) pairs
    individual_forbidden_set: set of (student_idx, seat_idx) tuples

    Returns True if the proposed assignment is valid, False otherwise.
    """
    # -- Check 1: individual forbidden ----------------------------------------
    if (student, seat) in individual_forbidden_set:
        return False

    # -- Check 2: adjacency conflicts -----------------------------------------
    # We only need to check students who (a) are already assigned AND
    # (b) form a conflict pair with the current student.  This makes the
    # check O(degree) in the conflict graph, not O(n).
    neighbors = get_neighbors(seat, rows, cols, include_diagonal)

    for neighbor_seat in neighbors:
        if neighbor_seat in assignment:
            neighbor_student = assignment[neighbor_seat]
            # frozenset makes the pair order-independent
            if frozenset({student, neighbor_student}) in conflict_pairs:
                return False

    return True


def backtracking_seat_assignment(students, rows, cols, conflict_pairs,
                                 individual_forbidden=None,
                                 include_diagonal=True,
                                 find_all=False):
    """
    Assign `students` to seats in a `rows x cols` grid via backtracking,
    respecting both individual forbidden pairs and pairwise adjacency
    conflicts.

    students: list of student identifiers
    conflict_pairs: list of (studentA, studentB) pairs that must NOT be adjacent
    individual_forbidden: list of (student, seat_idx) tuples
    include_diagonal: whether diagonally-adjacent seats count as "adjacent"
    find_all: if True, return ALL valid assignments; if False, return the
              first valid assignment found (faster for large rooms)

    Returns:
        If find_all=False: a single dict {seat_idx: student} or None
        If find_all=True:  a list of all valid dicts [{seat_idx: student}, ...]
    """
    n_seats = rows * cols
    if len(students) > n_seats:
        return [] if find_all else None

    # Pre-process conflict pairs into a set of frozensets for O(1) lookup
    conflict_set = {frozenset(pair) for pair in conflict_pairs}

    # Pre-process individual forbidden into a set for O(1) lookup
    forbidden_set = set()
    if individual_forbidden:
        forbidden_set = set(individual_forbidden)

    all_seats = list(range(n_seats))
    results = []

    def _backtrack(student_idx, assignment, used_seats):
        """
        Recursive backtracking: assign students[student_idx] to some seat.

        WHY backtracking works well here:
        Adjacency conflicts create a CONSTRAINT SATISFACTION PROBLEM (CSP).
        Backtracking prunes entire subtrees the moment a partial assignment
        violates a constraint.  For typical class sizes (20-60 students)
        with a moderate number of conflict pairs, this runs in well under
        a second.  For very dense conflict graphs, this could be slow --
        but that corresponds to an over-constrained real-world scenario that
        probably has no solution anyway.
        """
        if student_idx == len(students):
            # All students assigned -- valid solution found
            results.append(dict(assignment))
            return not find_all  # return True to stop early if not find_all

        student = students[student_idx]

        # Randomize seat order to avoid bias and produce varied solutions
        # across runs.  This is particularly useful for the retest feature.
        shuffled_seats = list(all_seats)
        random.shuffle(shuffled_seats)

        for seat in shuffled_seats:
            if seat in used_seats:
                continue
            if is_seat_valid(student, seat, assignment, conflict_set,
                             forbidden_set, rows, cols, include_diagonal):
                # Tentatively assign this student to this seat
                assignment[seat] = student
                used_seats.add(seat)

                if _backtrack(student_idx + 1, assignment, used_seats):
                    return True  # Early stop (only when find_all=False)

                # Backtrack: undo the assignment
                del assignment[seat]
                used_seats.remove(seat)

        return False  # No valid seat found for this student -> backtrack

    _backtrack(0, {}, set())

    if find_all:
        return results
    else:
        return results[0] if results else None


# =======================================================================
#  BRUTE FORCE -- exhaustive enumeration for correctness testing
# =======================================================================

def brute_force_count_valid_full(students, rows, cols, conflict_pairs,
                                 individual_forbidden=None,
                                 include_diagonal=True):
    """
    Enumerate ALL permutations of students into seats and count how many
    satisfy BOTH individual forbidden AND adjacency constraints.

    This is O(n!), so it's only feasible for tiny rooms (<= ~8 seats).
    Its purpose is to VALIDATE the backtracking search: if
    brute_force_count == len(backtracking results with find_all=True),
    then the backtracking code is correct.
    """
    n_seats = rows * cols
    if len(students) > n_seats:
        return 0

    conflict_set = {frozenset(pair) for pair in conflict_pairs}
    forbidden_set = set(individual_forbidden) if individual_forbidden else set()

    count = 0

    for perm in permutations(range(n_seats), len(students)):
        # perm[i] = seat assigned to students[i]
        valid = True

        for i, seat in enumerate(perm):
            student = students[i]

            # Check individual forbidden
            if (student, seat) in forbidden_set:
                valid = False
                break

            # Check adjacency conflicts with all previously assigned students
            for j in range(i):
                other_student = students[j]
                other_seat = perm[j]
                if frozenset({student, other_student}) in conflict_set:
                    neighbors = get_neighbors(seat, rows, cols, include_diagonal)
                    if other_seat in neighbors:
                        valid = False
                        break
            if not valid:
                break

        if valid:
            count += 1

    return count


# =======================================================================
#  RETEST RE-SEATING -- derangement + adjacency, combined via backtracking
# =======================================================================

def generate_retest_seating(students, rows, cols, previous_seats,
                            conflict_pairs, individual_forbidden=None,
                            include_diagonal=True):
    """
    Generate a new seating arrangement for a RETEST where:

        1. NO student is assigned to their previous seat (derangement
           constraint -- this is mathematically equivalent to requiring a
           derangement of the seat assignment, the same concept computed in
           derangements.py).
        2. All pairwise adjacency conflicts are respected (same constraint
           as backtracking_seat_assignment).
        3. All individual forbidden (student, seat) pairs are respected.

    HOW IT WORKS -- and why we don't just call generate_random_derangement:

        The naive approach would be:
            Step 1: generate a random derangement of seat assignments
            Step 2: check if it also satisfies adjacency
            Step 3: if not, retry

        This is REJECTION SAMPLING over the intersection of two constraint
        sets.  It works, but can be very slow if the adjacency constraints
        are tight (most derangements would be rejected).

        Instead, we take the smarter approach of FOLDING the derangement
        constraint directly into the backtracking search.  Each student's
        previous seat is simply added to their individual forbidden set.
        The backtracker then searches for an assignment that avoids ALL
        forbidden seats (including previous ones) AND all adjacency
        conflicts, in a single unified search.

        This is equivalent to adding the diagonal of the "previous seat"
        matrix to the forbidden board and running the combined constraint
        solver.  It's the natural generalization of derangements to a
        constrained combinatorial setting -- exactly the kind of thing you'd
        discuss in a Discrete Mathematics viva.

    PARAMETERS:
        students:             list of student identifiers
        rows, cols:           classroom grid dimensions
        previous_seats:       dict {student: seat_idx} -- each student's
                              previous seat as a linear seat index
        conflict_pairs:       list of (studentA, studentB) -- pairs that
                              must NOT sit adjacent
        individual_forbidden: list of (student, seat_idx) -- additional
                              forbidden pairs (optional)
        include_diagonal:     whether diagonals count as adjacent

    RETURNS:
        dict {seat_idx: student} if a valid retest seating exists,
        None if the constraints are infeasible (no valid seating possible).

    MATHEMATICAL NOTE (for your viva):
        The total number of valid retest seatings is bounded above by the
        number of derangements D(n) (since the derangement constraint alone
        already eliminates ~1/e ~ 36.8% of all permutations), and further
        reduced by adjacency and individual forbidden constraints.  For a
        room with very dense conflict graphs, there may be NO valid retest
        seating at all, in which case this function returns None.  This
        connects to the idea of D(n)/n! ~ 1/e from derangements.py.
    """
    # -- Build the combined forbidden set -------------------------------------
    # Start with any user-specified individually-forbidden pairs
    combined_forbidden = list(individual_forbidden) if individual_forbidden else []

    # Add the derangement constraint: student X must NOT sit in their
    # previous seat.  This is the key insight -- a derangement is just a
    # permutation that avoids the diagonal {(i, sigma(i))} of the previous
    # assignment.  By adding (student, previous_seat) to the forbidden
    # set, we force the backtracker to find a permutation that avoids
    # these fixed points, i.e., a constrained derangement.
    for student in students:
        if student in previous_seats:
            combined_forbidden.append((student, previous_seats[student]))

    # -- Delegate to the existing backtracking solver -------------------------
    # This is clean code reuse: the backtracker already handles individual
    # forbidden pairs and adjacency conflicts.  By augmenting the forbidden
    # set, we get the derangement constraint "for free" without duplicating
    # search logic.
    result = backtracking_seat_assignment(
        students=students,
        rows=rows,
        cols=cols,
        conflict_pairs=conflict_pairs,
        individual_forbidden=combined_forbidden,
        include_diagonal=include_diagonal,
        find_all=False,  # We only need one valid assignment
    )

    return result  # dict {seat_idx: student} or None


# =======================================================================
#  DISPLAY HELPERS
# =======================================================================

def print_seating_grid(assignment, rows, cols, title="Seating Grid"):
    """
    Pretty-print a seating assignment as a 2D classroom grid.
    assignment: dict {seat_idx: student_identifier}
    """
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")
    # Column headers
    header = "      " + "  ".join(f" {chr(65 + c)}  " for c in range(cols))
    print(header)
    print("      " + "  ".join("-----" for _ in range(cols)))

    for r in range(rows):
        row_str = f"  R{r + 1}  "
        cells = []
        for c in range(cols):
            seat = seat_index(r, c, cols)
            occupant = assignment.get(seat, "...")
            cells.append(f"[{str(occupant):^3s}]")
        row_str += "  ".join(cells)
        print(row_str)

    print(f"{'=' * 50}\n")


# =======================================================================
#  DEMO / MAIN -- exercises both existing layers + the new retest feature
# =======================================================================

if __name__ == "__main__":

    # -- DEMO SETUP -----------------------------------------------------------
    # A small 2x3 classroom (6 seats) with 4 students.
    #
    #       A     B     C
    #  R1 [ 0 ] [ 1 ] [ 2 ]
    #  R2 [ 3 ] [ 4 ] [ 5 ]
    #
    # (numbers are linear seat indices)

    ROWS, COLS = 2, 3
    students = ["S1", "S2", "S3", "S4"]

    # Previous seats (from the first exam):
    #   S1 -> seat 0 (R1A), S2 -> seat 1 (R1B),
    #   S3 -> seat 4 (R2B), S4 -> seat 5 (R2C)
    previous_seats = {"S1": 0, "S2": 1, "S3": 4, "S4": 5}

    # Conflict pairs: S1-S2 and S3-S4 must NOT sit adjacent
    conflict_pairs = [("S1", "S2"), ("S3", "S4")]

    # Individual forbidden: S1 is banned from seat 3 (say, accessibility issue)
    individual_forbidden = [("S1", 3)]

    # -- PART 1: Show the original seating ------------------------------------
    original_assignment = {v: k for k, v in previous_seats.items()}
    print_seating_grid(original_assignment, ROWS, COLS,
                       title="ORIGINAL EXAM SEATING")

    # -- PART 2: Layer 1 demo -- analytic count (rook polynomial) -------------
    # Count arrangements that avoid ONLY the individual forbidden pairs,
    # ignoring adjacency.  This requires n_students == n_seats, so we
    # demonstrate on a 4x1 sub-problem (4 students, 4 positions).
    print("--- Layer 1: Analytic (Rook Polynomial + Inclusion-Exclusion) ---")
    small_n = 4
    # Forbidden: student i cannot go to position i (diagonal = derangement)
    small_forbidden = [(i, i) for i in range(small_n)]
    analytic_count = count_valid_arrangements(small_n, small_forbidden)
    derangement_Dn = derangement_count_formula(small_n)
    print(f"  Permutations of {small_n} students avoiding the diagonal")
    print(f"  (i.e., derangements): rook+I-E = {analytic_count}, "
          f"D({small_n}) = {derangement_Dn}  "
          f"[{'MATCH' if analytic_count == derangement_Dn else 'MISMATCH'}]")

    # -- PART 3: Layer 2 demo -- backtracking with adjacency conflicts --------
    print("\n--- Layer 2: Backtracking with Adjacency Conflicts ---")
    assignment = backtracking_seat_assignment(
        students, ROWS, COLS, conflict_pairs,
        individual_forbidden=individual_forbidden,
        include_diagonal=True,
    )
    if assignment:
        print_seating_grid(assignment, ROWS, COLS,
                           title="LAYER 2: CONFLICT-AWARE SEATING")
    else:
        print("  No valid assignment found (constraints too tight).")

    # -- PART 4: Brute force validation ---------------------------------------
    print("--- Brute Force Validation ---")
    bf_count = brute_force_count_valid_full(
        students, ROWS, COLS, conflict_pairs,
        individual_forbidden=individual_forbidden,
        include_diagonal=True,
    )
    bt_count = len(backtracking_seat_assignment(
        students, ROWS, COLS, conflict_pairs,
        individual_forbidden=individual_forbidden,
        include_diagonal=True,
        find_all=True,
    ))
    print(f"  Brute force found: {bf_count} valid assignments")
    print(f"  Backtracking found: {bt_count} valid assignments")
    print(f"  Match: {'YES' if bf_count == bt_count else 'MISMATCH'}")

    # -- PART 5: RETEST RE-SEATING (NEW FEATURE) ------------------------------
    print("\n" + "=" * 60)
    print("  RETEST RE-SEATING (Derangement + Adjacency Constraints)")
    print("=" * 60)

    print(f"\n  Students: {students}")
    print("  Previous seats: " + ", ".join(
        f"{s} -> {seat_label(*seat_coords(previous_seats[s], COLS))}"
        for s in students))
    print(f"  Conflict pairs: {conflict_pairs}")
    print(f"  Individual forbidden: {individual_forbidden}")
    print(f"  Derangement count D({len(students)}) = "
          f"{derangement_count_formula(len(students))}  "
          f"(upper bound before adjacency/forbidden constraints)")

    retest_result = generate_retest_seating(
        students=students,
        rows=ROWS,
        cols=COLS,
        previous_seats=previous_seats,
        conflict_pairs=conflict_pairs,
        individual_forbidden=individual_forbidden,
        include_diagonal=True,
    )

    if retest_result:
        print_seating_grid(retest_result, ROWS, COLS,
                           title="RETEST SEATING RESULT")

        # -- Verification: no student got their previous seat -----------------
        print("  VERIFICATION:")
        all_deranged = True
        for student in students:
            prev_seat = previous_seats[student]
            # Find where this student was assigned in the retest
            new_seat = [s for s, st in retest_result.items() if st == student][0]
            same = (new_seat == prev_seat)
            if same:
                all_deranged = False
            prev_label = seat_label(*seat_coords(prev_seat, COLS))
            new_label = seat_label(*seat_coords(new_seat, COLS))
            status = "SAME [X]" if same else "different [OK]"
            print(f"    {student}: was {prev_label} -> now {new_label}  [{status}]")

        print(f"\n    Derangement check: "
              f"{'PASS -- no student repeated their seat' if all_deranged else 'FAIL'}")

        # -- Verification: no conflict pair is adjacent -----------------------
        all_nonadjacent = True
        for s_a, s_b in conflict_pairs:
            seat_a = [s for s, st in retest_result.items() if st == s_a][0]
            seat_b = [s for s, st in retest_result.items() if st == s_b][0]
            neighbors_a = get_neighbors(seat_a, ROWS, COLS, include_diagonal=True)
            adjacent = seat_b in neighbors_a
            if adjacent:
                all_nonadjacent = False
            label_a = seat_label(*seat_coords(seat_a, COLS))
            label_b = seat_label(*seat_coords(seat_b, COLS))
            status = "ADJACENT [X]" if adjacent else "not adjacent [OK]"
            print(f"    Conflict pair ({s_a}, {s_b}): "
                  f"{label_a} & {label_b}  [{status}]")

        print(f"\n    Adjacency check: "
              f"{'PASS -- no conflict pair is adjacent' if all_nonadjacent else 'FAIL'}")

        # -- Verification: no individual forbidden pair violated --------------
        all_forbidden_ok = True
        for student, seat in (individual_forbidden or []):
            assigned_seat = [s for s, st in retest_result.items() if st == student][0]
            violated = (assigned_seat == seat)
            if violated:
                all_forbidden_ok = False
            status = "VIOLATED [X]" if violated else "respected [OK]"
            print(f"    Forbidden ({student}, {seat_label(*seat_coords(seat, COLS))}): "
                  f"{student} assigned to "
                  f"{seat_label(*seat_coords(assigned_seat, COLS))}  [{status}]")

        print(f"\n    Forbidden-pairs check: "
              f"{'PASS' if all_forbidden_ok else 'FAIL'}")

        # -- Overall verdict --------------------------------------------------
        overall = all_deranged and all_nonadjacent and all_forbidden_ok
        print(f"\n  +=============================================+")
        print(f"  |  OVERALL VERDICT: {'ALL CHECKS PASSED' if overall else 'SOME CHECKS FAILED':^25s}  |")
        print(f"  +=============================================+")

    else:
        print("\n  Result: None -- no valid retest seating exists under these "
              "constraints.")
        print("  (This can happen if the room is too small or conflicts are "
              "too dense.)")

    # -- PART 6: ML RISK MODEL INTEGRATION ------------------------------------
    print("\n" + "=" * 60)
    print("  PART 6: ML RISK-GUIDED SEATING")
    print("=" * 60)

    # Train model on synthetic pairs
    data = generate_simulated_data(num_pairs=1000)
    risk_model = train_risk_model(data)

    # Generate predicted conflicts for current demo cohort
    ai_conflicts = get_high_risk_pairs(risk_model, students, threshold=0.75)
    print(f"  AI-flagged high-risk pairs: {ai_conflicts}")

    # Merge explicit domain conflicts with AI-inferred conflicts
    active_conflicts = list(set(conflict_pairs + ai_conflicts))

    ml_assignment = backtracking_seat_assignment(
        students=students,
        rows=ROWS,
        cols=COLS,
        conflict_pairs=active_conflicts,
        individual_forbidden=individual_forbidden,
        include_diagonal=True,
    )

    if ml_assignment:
        print_seating_grid(ml_assignment, ROWS, COLS, title="AI CONFLICT-AWARE SEATING")
    else:
        print("  No arrangement feasible with current AI risk threshold.")
