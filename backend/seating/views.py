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

from rest_framework import viewsets, status, serializers
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
from .rosters import load_all_rosters
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
from seating.engines.brute_force_explainer import enumerate_arrangements


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
    Supports filtering by room: GET /api/students/?room=<id>
    """
    serializer_class = StudentSerializer

    def get_queryset(self):
        queryset = Student.objects.all()
        room_id = self.request.query_params.get('room')
        if room_id:
            queryset = queryset.filter(room_id=room_id)
        return queryset

    def perform_create(self, serializer):
        if 'room' in serializer.validated_data:
            serializer.save()
        else:
            room_id = self.request.data.get('room') or self.request.query_params.get('room')
            if room_id:
                room = get_object_or_404(Room, id=room_id)
                serializer.save(room=room)
            else:
                raise serializers.ValidationError({"room": "This field is required."})


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
        # Default to all registered students in this room
        students = list(room.students.values_list('roll_no', flat=True))

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
            "use_real_roster": true,   // optional, loads department rosters for real proximity
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
    student USNs in the department rosters.

    ROSTER VALIDATION & TRADE-OFF:
        - When strict_roster_check is true (default): Any student roll_no that
          cannot be found in the department rosters immediately returns HTTP 400
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
            strict_roster_check=strict_roster_check,
            use_real_roster=use_real_roster,
        )
    except ml_risk_model.RosterMismatchError as exc:
        return Response(
            {
                "error": "Roster mismatch: some student roll numbers don't match real USNs.",
                "unmatched_student_ids": exc.unmatched_ids,
                "hint": (
                    "Set each Student's roll_no to match a real USN from the department rosters, "
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
    scores_map = getattr(high_risk_pairs, 'pair_scores', {})

    feature_cols = [
        "past_incidents_together",
        "shared_classes_count",
        "academic_similarity_score",
        "roll_number_proximity",
    ]
    feature_importances = dict(zip(
        feature_cols,
        [round(float(imp), 4) for imp in trained_model.feature_importances_]
    ))

    # Build pairs list with score, sorted highest risk score first
    pairs_list = []
    for a, b in high_risk_pairs:
        raw_score = scores_map.get(frozenset({a, b}), threshold)
        pairs_list.append({
            "student_a": a,
            "student_b": b,
            "score": round(float(raw_score), 2),
        })
    pairs_list.sort(key=lambda x: -x["score"])

    return Response(
        {
            "threshold": threshold,
            "total_students": len(students),
            "high_risk_pairs": pairs_list,
            "count": len(high_risk_pairs),
            "features_simulated": not use_real_roster and (student_features is None),
            "feature_sources": feature_sources,
            "pairs_with_real_evidence": pairs_with_real_evidence,
            "feature_importances": feature_importances,
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

    Provides theoretical statistics including D(n) derangements vs n!,
    room geometry, and formatted string values for large integers.
    """
    room = get_object_or_404(Room, id=room_id)

    # Determine student roster (same logic as _extract_solver_inputs)
    students = list(room.students.values_list('roll_no', flat=True))
    n = len(students)

    forbidden_qs = ConstraintForbidden.objects.filter(
        room=room
    ).select_related('student')
    forbidden_cells = [
        (item.student.roll_no, item.seat_index) for item in forbidden_qs
    ]
    forbidden_seats = sorted(list(set(item.seat_index for item in forbidden_qs)))
    forbidden_details = [
        {"student": item.student.roll_no, "seat_index": item.seat_index}
        for item in forbidden_qs
    ]

    if n == 0:
        return Response({
            "room_id": room.id,
            "room_name": room.name,
            "rows": room.rows,
            "cols": room.cols,
            "total_seats": room.total_seats,
            "forbidden_seats": forbidden_seats,
            "forbidden_details": forbidden_details,
            "n": 0,
            "n_factorial": 1,
            "n_factorial_str": "1",
            "rook_polynomial_coefficients": [1],
            "inclusion_exclusion_terms": [],
            "total_valid_arrangements": 0,
            "total_valid_arrangements_str": "0",
            "derangement_info": None,
        })

    # Compute rook polynomial of the forbidden board
    rook_coeffs = rook_polynomial(forbidden_cells)

    # Compute inclusion-exclusion term breakdown
    total, terms = count_valid_arrangements_verbose(n, forbidden_cells)

    formatted_terms = []
    for t in terms:
        t_copy = dict(t)
        t_copy["factorial_term_str"] = str(t["factorial_term"])
        t_copy["contribution_str"] = str(t["contribution"])
        formatted_terms.append(t_copy)

    # Check whether this room has any retest results
    has_retest = SeatingResult.objects.filter(
        room=room, type='retest'
    ).exists()

    d_n = derangement_count_formula(n)
    n_factorial = math.factorial(n)
    ratio = round(d_n / n_factorial, 6) if n_factorial > 0 else 0
    percentage = round((d_n / n_factorial) * 100, 2) if n_factorial > 0 else 0

    derangement_info = {
        "D_n": d_n,
        "D_n_str": str(d_n),
        "n_factorial": n_factorial,
        "n_factorial_str": str(n_factorial),
        "ratio": ratio,
        "percentage": percentage,
        "has_retest": has_retest,
    }

    return Response({
        "room_id": room.id,
        "room_name": room.name,
        "rows": room.rows,
        "cols": room.cols,
        "total_seats": room.total_seats,
        "forbidden_seats": forbidden_seats,
        "forbidden_details": forbidden_details,
        "n": n,
        "n_factorial": n_factorial,
        "n_factorial_str": str(n_factorial),
        "rook_polynomial_coefficients": rook_coeffs,
        "inclusion_exclusion_terms": formatted_terms,
        "total_valid_arrangements": total,
        "total_valid_arrangements_str": str(total),
        "derangement_info": derangement_info,
    })


@api_view(['GET'])
def tiny_proof_explainer(request, room_id):
    """
    GET /api/math-explainer/<room_id>/tiny-proof/
    Provides a brute-force permutation listing proof for small rooms (n <= 5)
    or a built-in mini example for larger rooms.
    Uses generic labels only (S1..Sn, Seat 1..n). Never exposes real student names.
    """
    room = get_object_or_404(Room, id=room_id)
    students = list(room.students.values_list('roll_no', flat=True))
    n = len(students)

    if 1 <= n <= 5:
        # Real room structure using generic labels
        student_map = {roll: i for i, roll in enumerate(students)}
        forbidden_qs = ConstraintForbidden.objects.filter(room=room).select_related('student')
        forbidden_cells = []
        for item in forbidden_qs:
            if item.student.roll_no in student_map:
                s_idx = student_map[item.student.roll_no]
                # Map seat_index within the n available student seats
                c_idx = item.seat_index if item.seat_index < n else (item.seat_index % n)
                forbidden_cells.append((s_idx, c_idx))

        seating_proof = enumerate_arrangements(n, forbidden_cells, mode='seating')
        retest_proof = enumerate_arrangements(n, [], mode='retest')
        retest_n3 = enumerate_arrangements(3, [], mode='retest') if n != 3 else retest_proof
        retest_n4 = enumerate_arrangements(4, [], mode='retest') if n != 4 else retest_proof

        return Response({
            "room_id": room.id,
            "room_name": room.name,
            "room_students_count": n,
            "is_mini_example": False,
            "reason": None,
            "seating": seating_proof,
            "retest": retest_proof,
            "retest_n3": retest_n3,
            "retest_n4": retest_n4,
        })
    else:
        # Fallback built-in mini example
        reason = (
            "your room is larger than 5 students, so here is the same idea on a small room"
            if n > 5
            else "your room currently has 0 students, so here is the same idea on a small room"
        )
        # Built-in mini example: n = 4 with 2 forbidden cells in different rows and columns
        mini_seating = enumerate_arrangements(4, [(0, 0), (1, 1)], mode='seating')
        # Derangement mode: n = 3 (D3 = 2) and n = 4 (D4 = 9)
        mini_d3 = enumerate_arrangements(3, [], mode='retest')
        mini_d4 = enumerate_arrangements(4, [], mode='retest')

        return Response({
            "room_id": room.id,
            "room_name": room.name,
            "room_students_count": n,
            "is_mini_example": True,
            "reason": reason,
            "seating": mini_seating,
            "retest": mini_d3,
            "retest_n3": mini_d3,
            "retest_n4": mini_d4,
        })


# =======================================================================
# 7. Department Rosters Endpoints
# =======================================================================

@api_view(['GET'])
def list_rosters(request):
    """
    GET /api/rosters/
    Returns summary list of all department rosters with slug, department label,
    student count, plus an errors list.
    """
    rosters_dict, errors = load_all_rosters()
    roster_list = [
        {
            "slug": r["slug"],
            "department": r["department"],
            "count": r["count"],
        }
        for r in rosters_dict.values()
    ]
    return Response({
        "rosters": roster_list,
        "errors": errors,
    })


@api_view(['GET'])
def get_roster_detail(request, slug):
    """
    GET /api/rosters/<slug>/
    Returns:
        { "department": "...", "students": [{ "usn": "...", "name": "..." }, ...] }
    Returns 404 if unknown slug.
    """
    rosters_dict, _ = load_all_rosters()
    if slug not in rosters_dict:
        return Response(
            {"error": f"Roster '{slug}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    roster = rosters_dict[slug]
    return Response({
        "department": roster["department"],
        "students": roster["students"],
    })


@api_view(['POST'])
def add_roster_students_to_room(request, room_id):
    """
    POST /api/rooms/<room_id>/add-roster-students/
    Body:
        { "slug": "cse-aidd", "usns": ["25BTRA0001", ...] }

    Creates Student records using the roster name and USN.
    Skips USNs already in the room.
    Rejects unknown USNs with HTTP 400.
    Returns HTTP 400 if room capacity (rows * cols) would be exceeded.
    """
    room = get_object_or_404(Room, id=room_id)
    slug = request.data.get('slug')
    usns = request.data.get('usns')

    if not slug:
        return Response(
            {"error": "Field 'slug' is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(usns, list):
        return Response(
            {"error": "Field 'usns' must be a list of USN strings."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rosters_dict, _ = load_all_rosters()
    if slug not in rosters_dict:
        return Response(
            {"error": f"Roster '{slug}' not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    roster = rosters_dict[slug]
    roster_map = {s['usn']: s['name'] for s in roster['students']}

    # Reject unknown USNs
    unknown_usns = [u for u in usns if u not in roster_map]
    if unknown_usns:
        return Response(
            {
                "error": f"Unknown USN(s) for roster '{slug}': {unknown_usns}",
                "unknown_usns": unknown_usns,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Deduplicate requested USNs while preserving order
    unique_requested_usns = list(dict.fromkeys(usns))

    # Identify USNs already created / present in DB for this room
    existing_usns = set(
        Student.objects.filter(room=room, roll_no__in=unique_requested_usns).values_list('roll_no', flat=True)
    )

    new_usns = [u for u in unique_requested_usns if u not in existing_usns]
    skipped_usns = [u for u in unique_requested_usns if u in existing_usns]

    # Capacity check: room capacity is rows * cols
    room_capacity = room.rows * room.cols
    current_students_count = room.students.count()

    if current_students_count + len(new_usns) > room_capacity:
        return Response(
            {
                "error": (
                    f"Room capacity exceeded. Room '{room.name}' has capacity {room_capacity} "
                    f"({room.rows}x{room.cols}). Current students: {current_students_count}, "
                    f"attempting to add {len(new_usns)} new students."
                ),
                "room_capacity": room_capacity,
                "current_students": current_students_count,
                "attempted_to_add": len(new_usns),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    created_students = []
    for u in new_usns:
        student = Student.objects.create(
            room=room,
            roll_no=u,
            name=roster_map[u],
        )
        created_students.append(student)

    return Response(
        {
            "message": f"Successfully added {len(created_students)} student(s). Skipped {len(skipped_usns)} already present.",
            "added_count": len(created_students),
            "skipped_count": len(skipped_usns),
            "added": [{"roll_no": s.roll_no, "name": s.name} for s in created_students],
            "skipped": skipped_usns,
        },
        status=status.HTTP_201_CREATED,
    )

