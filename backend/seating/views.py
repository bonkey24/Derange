"""
seating/views.py
----------------
Production-ready DRF views for the seating allocation system.

Contains:
    1. RoomViewSet: Standard CRUD operations on physical rooms.
    2. StudentViewSet, ConstraintConflictPairViewSet, ConstraintForbiddenViewSet:
       Supporting CRUD viewsets for domain entities.
    3. generate_seating_chart (@api_view(['POST'])):
       Pulls room, student, and conflict constraints from DB, runs
       backtracking_seat_assignment(), saves SeatingResult, and returns JSON.
    4. generate_retest (@api_view(['POST'])):
       Enforces derangement constraints where no student can sit in their
       previous seat using generate_retest_seating(). Ensures previous seat
       assignments are passed in as forbidden constraints.
    5. train_risk_model_api (@api_view(['POST'])):
       Trains a Random Forest classifier on synthetic student feature vectors,
       evaluates pairwise risk, and returns high-risk pairs without persisting
       the model to disk.
    6. seating_results_by_room (@api_view(['GET'])):
       Retrieves seating history for a specified room.
"""

import math
import os

from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import (
    Room,
    Student,
    ConstraintForbidden,
    ConstraintConflictPair,
    SeatingResult,
)
from .serializers import (
    RoomSerializer,
    StudentSerializer,
    ConstraintForbiddenSerializer,
    ConstraintConflictPairSerializer,
    SeatingResultSerializer,
)

# Import math & ML engines via the sys.path bootstrap in engines/__init__.py
from seating.engines import (
    seating_board,
    ml_risk_model,
)
from seating.engines.rook_polynomial import rook_polynomial
from seating.engines.inclusion_exclusion import count_valid_arrangements_verbose
from seating.engines.derangements import derangement_count_formula


# =======================================================================
# 1. Model ViewSets (Standard CRUD)
# =======================================================================

class RoomViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD viewset for Room entities (name, rows, cols, total_seats).
    """
    queryset = Room.objects.all()
    serializer_class = RoomSerializer


class StudentViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD viewset for Student entities.
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


class ConstraintConflictPairViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD viewset for student adjacency conflict pairs (Layer 2).
    """
    queryset = ConstraintConflictPair.objects.all()
    serializer_class = ConstraintConflictPairSerializer


class ConstraintForbiddenViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD viewset for individual forbidden seat assignments (Layer 1).
    """
    queryset = ConstraintForbidden.objects.all()
    serializer_class = ConstraintForbiddenSerializer


# =======================================================================
# Helper: extract solver arguments from the database
# =======================================================================

def _extract_solver_inputs(room, requested_students=None):
    """
    Queries students, forbidden seat indices, and conflict pairs
    for a given Room to prepare inputs for the combinatorics engine.

    Returns:
        students (list[str]): Roll numbers of students to seat.
        forbidden (list[tuple[str, int]]): (roll_no, seat_index) pairs.
        conflicts (list[tuple[str, str]]): (roll_no_a, roll_no_b) pairs.
    """
    # 1. Determine student roster
    if requested_students:
        students = list(requested_students)
    else:
        # Default to all registered students in the database
        students = list(Student.objects.values_list('roll_no', flat=True))

    # 2. Individual forbidden seat constraints for this room (Layer 1)
    forbidden_qs = ConstraintForbidden.objects.filter(room=room).select_related('student')
    forbidden = [(item.student.roll_no, item.seat_index) for item in forbidden_qs]

    # 3. Adjacency conflict constraints for this room (Layer 2)
    conflict_qs = ConstraintConflictPair.objects.filter(room=room).select_related(
        'student_a', 'student_b'
    )
    conflicts = [(item.student_a.roll_no, item.student_b.roll_no) for item in conflict_qs]

    return students, forbidden, conflicts


# =======================================================================
# 2. Action: Generate Seating Chart (Normal Exam)
# =======================================================================

@api_view(['POST'])
def generate_seating_chart(request):
    """
    POST /api/generate-seating/

    Request Body:
        {
            "room_id": 1,
            "include_diagonal": true,       // optional, default true
            "student_ids": ["S1", "S2"]     // optional, defaults to all students
        }

    Extracts constraints from the database, executes the CSP backtracking
    solver, persists the arrangement in SeatingResult, and returns the JSON.
    """
    room_id = request.data.get('room_id')
    if not room_id:
        return Response(
            {"error": "Field 'room_id' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    room = get_object_or_404(Room, id=room_id)
    include_diagonal = bool(request.data.get('include_diagonal', True))
    student_ids = request.data.get('student_ids', None)

    students, forbidden, conflicts = _extract_solver_inputs(room, student_ids)

    if not students:
        return Response(
            {"error": "No students found to seat. Please register students first."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(students) > room.total_seats:
        return Response(
            {
                "error": f"Cannot seat {len(students)} students in a room with only {room.total_seats} seats."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Call the combinatorics backtracking solver
    assignment = seating_board.backtracking_seat_assignment(
        students=students,
        rows=room.rows,
        cols=room.cols,
        conflict_pairs=conflicts,
        individual_forbidden=forbidden,
        include_diagonal=include_diagonal,
    )

    if assignment is None:
        return Response(
            {"error": "No valid seating arrangement found under the current constraints."},
            status=status.HTTP_409_CONFLICT,
        )

    # Convert integer seat indices to string keys for clean JSON serialization
    assignment_json = {str(seat_idx): roll_no for seat_idx, roll_no in assignment.items()}

    # Save to SeatingResult model
    result = SeatingResult.objects.create(
        room=room,
        assignment=assignment_json,
        type='normal',
    )

    return Response(
        SeatingResultSerializer(result).data,
        status=status.HTTP_201_CREATED,
    )


# =======================================================================
# 3. Action: Generate Retest Seating (Derangement Constraint)
# =======================================================================

@api_view(['POST'])
def generate_retest(request):
    """
    POST /api/generate-retest/

    Request Body:
        {
            "room_id": 1,
            "previous_result_id": 1,        // ID of prior SeatingResult (OR provide previous_seats directly)
            "previous_seats": {"S1": 0},    // optional direct mapping {roll_no: seat_index}
            "include_diagonal": true        // optional, default true
        }

    Enforces the derangement constraint (!n): ensures each student is
    prohibited from occupying their previous seat from Exam 1, while
    simultaneously adhering to physical and adjacency conflicts.
    Previous seat assignments are passed in as forbidden constraints.
    """
    room_id = request.data.get('room_id')
    previous_result_id = request.data.get('previous_result_id')
    raw_previous_seats = request.data.get('previous_seats')

    if not room_id:
        return Response(
            {"error": "Field 'room_id' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    room = get_object_or_404(Room, id=room_id)
    include_diagonal = bool(request.data.get('include_diagonal', True))

    previous_seats = {}

    if previous_result_id:
        previous_result = get_object_or_404(SeatingResult, id=previous_result_id)
        # previous_result.assignment is stored as {"seat_index_str": "student_roll"}
        for seat_str, roll_no in previous_result.assignment.items():
            previous_seats[roll_no] = int(seat_str)
    elif raw_previous_seats and isinstance(raw_previous_seats, dict):
        # Support direct dictionary payload {student_roll: seat_index} or {seat_index_str: student_roll}
        for k, v in raw_previous_seats.items():
            try:
                # If key is digit, it's seat_index -> student
                if str(k).isdigit():
                    previous_seats[str(v)] = int(k)
                else:
                    previous_seats[str(k)] = int(v)
            except (ValueError, TypeError):
                pass
    else:
        return Response(
            {"error": "Either 'previous_result_id' or 'previous_seats' mapping must be provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not previous_seats:
        return Response(
            {"error": "Previous seat assignments could not be determined."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Extract room constraints for the students from the previous exam
    students, forbidden, conflicts = _extract_solver_inputs(room, list(previous_seats.keys()))

    # Ensure previous seat assignments are explicitly treated as forbidden constraints
    # (generate_retest_seating also folds previous_seats into its forbidden list)
    assignment = seating_board.generate_retest_seating(
        students=students,
        rows=room.rows,
        cols=room.cols,
        previous_seats=previous_seats,
        conflict_pairs=conflicts,
        individual_forbidden=forbidden,
        include_diagonal=include_diagonal,
    )

    if assignment is None:
        return Response(
            {"error": "No valid retest seating found. The derangement and conflict constraints may be too tight."},
            status=status.HTTP_409_CONFLICT,
        )

    assignment_json = {str(seat_idx): roll_no for seat_idx, roll_no in assignment.items()}

    # Save to SeatingResult model marked as retest
    result = SeatingResult.objects.create(
        room=room,
        assignment=assignment_json,
        type='retest',
    )

    return Response(
        SeatingResultSerializer(result).data,
        status=status.HTTP_201_CREATED,
    )


# =======================================================================
# 4. Action: Train Risk Model & Inference API
# =======================================================================

@api_view(['POST'])
def train_risk_model_api(request):
    """
    POST /api/train-risk-model/

    Request Body:
        {
            "room_id": 1,              // optional if student_ids is provided
            "student_ids": ["S1", ...],// optional if room_id is provided
            "threshold": 0.75,         // optional, default 0.75
            "num_pairs": 1000,         // optional, default 1000 synthetic samples
            "use_real_roster": true,   // optional, loads students_anonymized.csv for real proximity
            "strict_roster_check": true,// optional, default true. If false, unmatched IDs fall back to 0.5 proximity
            "pair_features": {         // optional real metrics per student pair
                "S1,S2": {
                    "past_incidents_together": 2,
                    "shared_classes_count": 3,
                    "academic_similarity_score": 0.85
                }
            }
        }

    Trains a Random Forest classifier on synthetic tabular data in-memory,
    performs pairwise conflict risk scoring on the student cohort, and
    returns the flagged high-risk pairs without persisting the model to disk.
    If use_real_roster is true, roll_number_proximity is computed from real
    student USNs in students_anonymized.csv.

    ROSTER VALIDATION & TRADE-OFF:
        - When strict_roster_check is true (default): Any student roll_no that
          cannot be found in students_anonymized.csv immediately returns HTTP 400
          with the list of unmatched student IDs.
        - When strict_roster_check is false: Unmatched student IDs do not fail
          the request; instead, pairs involving unmatched students fall back to
          a neutral proximity baseline (0.5), while pairs where both students
          match valid USNs still compute genuine real proximity.
    """
    threshold = float(request.data.get('threshold', 0.75))
    num_pairs = int(request.data.get('num_pairs', 1000))
    room_id = request.data.get('room_id')
    student_ids = request.data.get('student_ids')
    raw_pair_features = request.data.get('pair_features')
    use_real_roster = bool(request.data.get('use_real_roster', False))

    raw_strict = request.data.get('strict_roster_check', True)
    if isinstance(raw_strict, str):
        strict_roster_check = raw_strict.lower() not in ('false', '0', 'no')
    else:
        strict_roster_check = bool(raw_strict)

    if student_ids:
        students = list(student_ids)
    elif room_id:
        room = get_object_or_404(Room, id=room_id)
        students, _, _ = _extract_solver_inputs(room)
    else:
        students = list(Student.objects.values_list('roll_no', flat=True))

    if len(students) < 2:
        return Response(
            {"error": "At least 2 students are required to evaluate pairwise risk."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Parse optional pair_features into a frozenset-keyed dict
    student_features = None
    if raw_pair_features is not None:
        student_features = {}
        if isinstance(raw_pair_features, dict):
            for k, v in raw_pair_features.items():
                if isinstance(k, (frozenset, tuple, list, set)):
                    pair_key = frozenset(k)
                elif isinstance(k, str):
                    # Delimiters: "S1,S2", "S1-S2", "S1_S2", "S1:S2"
                    matched_sep = None
                    for sep in [',', '-', '_', ':', '|']:
                        if sep in k:
                            matched_sep = sep
                            break
                    if matched_sep:
                        parts = [p.strip() for p in k.split(matched_sep, 1)]
                        pair_key = frozenset(parts)
                    else:
                        pair_key = frozenset([k])
                else:
                    pair_key = frozenset([str(k)])

                student_features[pair_key] = v
        elif isinstance(raw_pair_features, list):
            for item in raw_pair_features:
                if isinstance(item, dict):
                    s_a = item.get('student_a') or item.get('student_1')
                    s_b = item.get('student_b') or item.get('student_2')
                    if not (s_a and s_b) and 'pair' in item and len(item['pair']) == 2:
                        s_a, s_b = item['pair']
                    if s_a and s_b:
                        feat = item.get('features', item)
                        student_features[frozenset({str(s_a), str(s_b)})] = {
                            'past_incidents_together': feat.get('past_incidents_together', 0),
                            'shared_classes_count': feat.get('shared_classes_count', 0),
                            'academic_similarity_score': feat.get('academic_similarity_score', 0.5),
                        }

    # Resolve real roster path if requested
    roster_csv_path = None
    if use_real_roster:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        roster_csv_path = os.path.join(app_dir, 'data', 'students_anonymized.csv')

    # 1. Generate synthetic tabular dataset for training the classifier
    simulated_data = ml_risk_model.generate_simulated_data(num_pairs=num_pairs)

    # 2. Train Random Forest model in-memory (not persisted to disk)
    trained_model = ml_risk_model.train_risk_model(simulated_data)

    # 3. Predict high-risk pairs among current students
    try:
        high_risk_pairs = ml_risk_model.get_high_risk_pairs(
            trained_model,
            students,
            threshold=threshold,
            student_features=student_features,
            roster_csv_path=roster_csv_path,
            strict_roster_check=strict_roster_check,
        )
    except ml_risk_model.RosterMismatchError as exc:
        return Response(
            {
                "error": "Roster mismatch: some student roll numbers don't match real USNs.",
                "unmatched_student_ids": exc.unmatched_ids,
                "hint": (
                    "Set each Student's roll_no to match a real USN from students_anonymized.csv, "
                    "or omit use_real_roster to use simulated proximity instead."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    feature_sources = getattr(high_risk_pairs, 'feature_sources', {
        "roll_number_proximity": "real" if use_real_roster else "simulated",
        "past_incidents_together": "simulated",
        "shared_classes_count": "simulated",
        "academic_similarity_score": "simulated",
    })

    pairs_with_real_evidence = getattr(high_risk_pairs, 'pairs_with_real_evidence', 0)

    return Response(
        {
            "threshold": threshold,
            "total_students": len(students),
            "high_risk_pairs": [
                {"student_a": a, "student_b": b}
                for a, b in high_risk_pairs
            ],
            "count": len(high_risk_pairs),
            "features_simulated": not use_real_roster and (student_features is None),
            "feature_sources": feature_sources,
            "pairs_with_real_evidence": pairs_with_real_evidence,
        },
        status=status.HTTP_200_OK,
    )


# =======================================================================
# 5. Supplementary Endpoint: View Seating History by Room
# =======================================================================

@api_view(['GET'])
def seating_results_by_room(request, room_id):
    """
    GET /api/seating-results/<room_id>/

    Returns all seating results associated with the given room, newest first.
    """
    room = get_object_or_404(Room, id=room_id)
    results = SeatingResult.objects.filter(room=room).order_by('-generated_at')
    serializer = SeatingResultSerializer(results, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# =======================================================================
# 6. Math Explainer: Rook Polynomial & Inclusion-Exclusion Visualization
# =======================================================================

@api_view(['GET'])
def math_explainer(request, room_id):
    """
    GET /api/math-explainer/<room_id>/

    Computes and returns the rook polynomial coefficients and
    inclusion-exclusion term-by-term breakdown for the active room's
    INDIVIDUAL forbidden-seat constraints (Layer 1 only -- adjacency
    conflict pairs are not rook-polynomial-representable).

    If the room has any past retest results, also includes derangement
    count D(n) vs n! for comparison.
    """
    room = get_object_or_404(Room, id=room_id)

    # Determine student roster (same logic as _extract_solver_inputs)
    students = list(Student.objects.values_list('roll_no', flat=True))
    n = len(students)

    if n == 0:
        return Response({
            "room_id": room.id,
            "n": 0,
            "rook_polynomial_coefficients": [1],
            "inclusion_exclusion_terms": [],
            "total_valid_arrangements": 0,
            "derangement_info": None,
        })

    # Build forbidden cells using the same pattern as _extract_solver_inputs:
    # (roll_no, seat_index) pairs -- rook_polynomial/inclusion_exclusion
    # treat these as (row, col) positions on the forbidden board.
    forbidden_qs = ConstraintForbidden.objects.filter(
        room=room
    ).select_related('student')
    forbidden_cells = [
        (item.student.roll_no, item.seat_index) for item in forbidden_qs
    ]

    # Compute rook polynomial of the forbidden board
    rook_coeffs = rook_polynomial(forbidden_cells)

    # Compute inclusion-exclusion term breakdown
    total, terms = count_valid_arrangements_verbose(n, forbidden_cells)

    # Check whether this room has any retest results
    has_retest = SeatingResult.objects.filter(
        room=room, type='retest'
    ).exists()

    derangement_info = None
    if has_retest:
        d_n = derangement_count_formula(n)
        n_factorial = math.factorial(n)
        derangement_info = {
            "D_n": d_n,
            "n_factorial": n_factorial,
            "ratio": round(d_n / n_factorial, 6) if n_factorial > 0 else 0,
        }

    return Response({
        "room_id": room.id,
        "n": n,
        "rook_polynomial_coefficients": rook_coeffs,
        "inclusion_exclusion_terms": terms,
        "total_valid_arrangements": total,
        "derangement_info": derangement_info,
    })

